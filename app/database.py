from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings


class Base(DeclarativeBase):
    pass


def _database_url() -> str:
    url = get_settings().database_url
    if url.startswith("sqlite:///./"):
        db_path = Path(url.removeprefix("sqlite:///./"))
        db_path.parent.mkdir(parents=True, exist_ok=True)
    return url


connect_args = {"check_same_thread": False} if _database_url().startswith("sqlite") else {}
engine = create_engine(_database_url(), connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


@contextmanager
def session_scope() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
