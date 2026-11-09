"""Bounded Chat Completions tool-calling transport.

Protocol checked against official documentation, 2026-11-01:
https://developers.openai.com/api/docs/guides/function-calling
https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create
No default model or price is assumed. Other compatible providers require user verification.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from urllib.parse import urlsplit

import httpx


class ModelUnavailable(RuntimeError):
    """A safe error which never contains credentials or remote response bodies."""


@dataclass(frozen=True)
class ModelSettings:
    provider: str
    base_url: str
    model: str
    key: str
    timeout_seconds: float = 10.0
    max_calls: int = 4
    max_tool_steps: int = 6
    max_output_tokens: int = 1200
    total_timeout_seconds: float = 45.0
    input_price_per_million: Decimal | None = None
    output_price_per_million: Decimal | None = None

    @classmethod
    def from_env(cls) -> ModelSettings:
        from dotenv import load_dotenv

        load_dotenv()
        required = {
            name: os.getenv(name, "").strip()
            for name in ("LLM_PROVIDER", "LLM_BASE_URL", "LLM_MODEL", "LLM_API_KEY")
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ModelUnavailable("Model is not configured: " + ", ".join(missing))
        parsed = urlsplit(required["LLM_BASE_URL"])
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ModelUnavailable("LLM_BASE_URL must not contain credentials or a query")
        if parsed.scheme != "https" and not (
            parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost", "::1"}
        ):
            raise ModelUnavailable("LLM_BASE_URL must use HTTPS (HTTP allowed for localhost)")
        if not parsed.hostname:
            raise ModelUnavailable("LLM_BASE_URL requires a host")

        def price(name: str) -> Decimal | None:
            raw = os.getenv(name)
            if raw is None or not raw.strip():
                return None
            amount = Decimal(raw)
            if not amount.is_finite() or amount < 0:
                raise ModelUnavailable("Invalid configured price")
            return amount

        return cls(
            provider=required["LLM_PROVIDER"],
            base_url=required["LLM_BASE_URL"].rstrip("/"),
            model=required["LLM_MODEL"],
            key=required["LLM_API_KEY"],
            input_price_per_million=price("LLM_INPUT_USD_PER_MILLION"),
            output_price_per_million=price("LLM_OUTPUT_USD_PER_MILLION"),
        )

    def public_config(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "base_url": self.base_url,
            "model": self.model,
            "temperature": 0,
            "max_calls": self.max_calls,
            "max_tool_steps": self.max_tool_steps,
            "max_output_tokens": self.max_output_tokens,
            "total_timeout_seconds": self.total_timeout_seconds,
        }


class ChatAdapter:
    """A true configurable HTTP adapter; not a simulated model result."""

    def __init__(self, settings: ModelSettings, client: httpx.Client | None = None):
        self.settings = settings
        self.client = client
        self.calls = 0
        self.http_attempts = 0
        self.usage: dict[str, int] | None = None
        self._usage_incomplete = False

    def complete(self, messages: list[dict], tools: list[dict], deadline: float) -> dict:
        if self.calls >= self.settings.max_calls:
            raise ModelUnavailable("Model call budget exhausted")
        self.calls += 1
        payload: dict[str, Any] = {
            "model": self.settings.model,
            "messages": messages,
            "temperature": 0,
            "max_completion_tokens": self.settings.max_output_tokens,
        }
        if tools:
            payload.update(tools=tools, tool_choice="auto", parallel_tool_calls=False)
        client = self.client or httpx.Client(follow_redirects=False)
        try:
            for attempt in range(2):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise ModelUnavailable("Investigation deadline exceeded")
                try:
                    self.http_attempts += 1
                    response = client.post(
                        self.settings.base_url + "/chat/completions",
                        json=payload,
                        headers={"Authorization": "Bearer " + self.settings.key},
                        timeout=min(remaining, self.settings.timeout_seconds),
                    )
                except httpx.TimeoutException as exc:
                    raise ModelUnavailable("Model request timed out") from exc
                except httpx.HTTPError as exc:
                    raise ModelUnavailable("Model transport failed") from exc
                if response.status_code in {429, 500, 502, 503, 504} and attempt == 0:
                    try:
                        delay = min(
                            1.0, max(0.0, float(response.headers.get("retry-after", "0.2")))
                        )
                    except ValueError:
                        delay = 0.2
                    if time.monotonic() + delay >= deadline:
                        raise ModelUnavailable("Investigation deadline exceeded")
                    time.sleep(delay)
                    continue
                if response.status_code >= 300:
                    raise ModelUnavailable(f"Model HTTP status {response.status_code}")
                if len(response.content) > 1_000_000:
                    raise ModelUnavailable("Model response exceeded size limit")
                try:
                    body = response.json()
                    choice = body["choices"][0]
                    if choice.get("finish_reason") in {"length", "content_filter"}:
                        raise ModelUnavailable("Model output incomplete or filtered")
                    message = choice["message"]
                    if not isinstance(message, dict):
                        raise ValueError("not an object")
                    usage = body.get("usage")
                    if (
                        not self._usage_incomplete
                        and usage
                        and all(
                            isinstance(usage.get(k), int) and usage[k] >= 0
                            for k in ("prompt_tokens", "completion_tokens")
                        )
                    ):
                        if self.usage is None:
                            self.usage = {"prompt_tokens": 0, "completion_tokens": 0}
                        for k in self.usage:
                            self.usage[k] += usage[k]
                    else:
                        self._usage_incomplete = True
                        self.usage = None
                    return message
                except (KeyError, ValueError, TypeError, IndexError) as exc:
                    raise ModelUnavailable("Model response had an invalid protocol shape") from exc
            raise ModelUnavailable("Model retry budget exhausted")
        finally:
            if self.client is None:
                client.close()

    def cost_usd(self) -> str | None:
        cfg = self.settings
        if (
            self.usage is None
            or cfg.input_price_per_million is None
            or cfg.output_price_per_million is None
        ):
            return None
        amount = (
            Decimal(self.usage["prompt_tokens"]) * cfg.input_price_per_million
            + Decimal(self.usage["completion_tokens"]) * cfg.output_price_per_million
        ) / 1_000_000
        return str(amount)
