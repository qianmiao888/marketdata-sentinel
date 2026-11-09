"""Local HTTP interface. All dataset selectors are validated by the query service."""

from datetime import datetime
from pathlib import Path
from typing import Literal

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import inspect, text

from sentinel import db, service

load_dotenv()

app = FastAPI(
    title="MarketData Sentinel",
    version="0.1.0",
    description="Rule diagnosis + model evidence organization. Model fallback does not count as a live-model success.",
)


@app.exception_handler(ValueError)
async def bad_value(_request, exc):
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=422, content={"detail": str(exc)[:500]})


def context(
    source: Literal["cex", "dex"], snapshot_id: str, start: datetime, end: datetime
) -> service.Context:
    return service.Context(source=source, snapshot_id=snapshot_id, start=start, end=end)


@app.get("/health")
def health():
    return {"status": "ok", "service": "MarketData Sentinel"}


@app.get("/ready")
def ready():
    try:
        with db.SessionLocal() as session:
            session.execute(text("SELECT 1"))
            tables = inspect(session.get_bind()).get_table_names()
            if "alembic_version" not in tables:
                raise RuntimeError("Run alembic upgrade head first")
            with db.get_engine().connect() as connection:
                current = MigrationContext.configure(connection).get_current_revision()
                config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
                head = ScriptDirectory.from_config(config).get_current_head()
                if current != head:
                    raise RuntimeError("Database migration is behind head")
    except Exception:
        raise HTTPException(status_code=503, detail="Database unavailable or migrations missing")
    return {"status": "ready"}


@app.get("/sources")
def sources():
    return service.sources()


@app.get("/snapshots")
def snapshots(limit: int = Query(50, ge=1, le=200)):
    return service.list_snapshots()[:limit]


@app.get("/ingestion")
def ingestion(source: Literal["cex", "dex"], snapshot_id: str, start: datetime, end: datetime):
    return service.ingestion_status(context(source, snapshot_id, start, end))


@app.get("/quality")
def quality(source: Literal["cex", "dex"], snapshot_id: str, start: datetime, end: datetime):
    return service.quality_findings(context(source, snapshot_id, start, end))


@app.get("/metrics")
def metrics(source: Literal["cex", "dex"], snapshot_id: str, start: datetime, end: datetime):
    return service.window_metrics(context(source, snapshot_id, start, end))


@app.get("/chart")
def chart(source: Literal["cex", "dex"], snapshot_id: str, start: datetime, end: datetime):
    return service.chart(context(source, snapshot_id, start, end))


@app.get("/raw-samples")
def raw_samples(source: Literal["cex", "dex"], snapshot_id: str, start: datetime, end: datetime):
    return service.raw_samples(context(source, snapshot_id, start, end))


@app.get("/evidence")
def evidence(snapshot_id: str, ids: list[str] = Query(min_length=1, max_length=30)):
    return service.evidence(ids, snapshot_id)


@app.get("/runs")
def runs(limit: int = Query(50, ge=1, le=200)):
    return service.list_runs(limit)


class InvestigationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    context: service.Context
    question: str = Field(min_length=3, max_length=2000)
    mode: Literal["deterministic", "live_llm"] = "deterministic"
    baseline: Literal["A", "B", "C"] = "A"


@app.post("/investigations")
def create_investigation(request: InvestigationRequest):
    from sentinel.investigation import investigate

    # A missing source/version is a clear input error, not a failed database write.
    service.window_metrics(request.context)
    return investigate(
        request.context, request.question, mode=request.mode, baseline=request.baseline
    )


@app.get("/investigations")
def investigations(limit: int = Query(50, ge=1, le=200)):
    from sentinel.investigation import list_investigations

    return list_investigations(limit)


@app.get("/investigations/{run_id}")
def investigation(run_id: str):
    from sentinel.investigation import get_run

    try:
        result = get_run(run_id)
        if result is None:
            raise ValueError("Unknown investigation")
        return result
    except (KeyError, ValueError):
        raise HTTPException(status_code=404, detail="Unknown investigation")
