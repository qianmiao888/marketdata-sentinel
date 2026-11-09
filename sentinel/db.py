from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

load_dotenv()


class Base(DeclarativeBase):
    pass


_engine = None
_url = None


def get_engine():
    global _engine, _url
    url = os.getenv("DATABASE_URL", "sqlite:///./data/sentinel.db")
    if _engine is None or _url != url:
        if _engine is not None:
            _engine.dispose()
        if url.startswith("sqlite:///"):
            path = url.removeprefix("sqlite:///")
            if path != ":memory:":
                Path(path).parent.mkdir(parents=True, exist_ok=True)
        kwargs = {"connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {}
        _engine = create_engine(url, pool_pre_ping=True, **kwargs)
        _url = url
    return _engine


def SessionLocal():
    return sessionmaker(bind=get_engine(), expire_on_commit=False)()


def init_db():
    from sentinel import models  # noqa: F401

    Base.metadata.create_all(get_engine())
