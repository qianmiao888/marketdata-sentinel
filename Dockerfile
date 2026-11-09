FROM python:3.12-slim
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:0.6.8 /uv /uvx /bin/
COPY pyproject.toml uv.lock README.md ./
COPY sentinel ./sentinel
RUN uv sync --frozen --no-dev
COPY alembic.ini ./
COPY alembic ./alembic
COPY fixtures ./fixtures
ENV PATH="/app/.venv/bin:$PATH"
CMD ["uvicorn", "sentinel.api:app", "--host", "0.0.0.0", "--port", "8000"]
