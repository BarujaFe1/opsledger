from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import get_settings

settings = get_settings()

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _migrate_payments_kind()


def _migrate_payments_kind() -> None:
    """Idempotently add the `kind` column to payments (no Alembic in this project).

    `Base.metadata.create_all` only creates missing tables, never alters existing
    ones, so existing deployments (SQLite locally, Postgres in prod) need this
    additive, idempotent migration. The column is NOT NULL with a 'payment'
    default, which is safe for data already persisted (all legacy rows are
    ordinary payments).
    """
    inspector = inspect(engine)
    existing = {c["name"] for c in inspector.get_columns("payments")}
    if "kind" in existing:
        return
    with engine.begin() as conn:
        conn.execute(
            text("ALTER TABLE payments ADD COLUMN kind VARCHAR(16) NOT NULL DEFAULT 'payment'")
        )
