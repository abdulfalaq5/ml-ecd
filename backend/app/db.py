from collections.abc import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings

engine = create_engine(get_settings().database_url, pool_pre_ping=True, pool_size=10, max_overflow=10)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Buat tabel + hypertable TimescaleDB (idempotent)."""
    from . import models  # noqa: F401  (registrasi model)

    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb"))
    Base.metadata.create_all(engine)
    with engine.begin() as conn:  # kolom baru pada tabel lama (create_all tidak menambah kolom)
        conn.execute(text("ALTER TABLE wells ADD COLUMN IF NOT EXISTS rathole JSON"))
        conn.execute(text("ALTER TABLE wells ADD COLUMN IF NOT EXISTS sections JSON"))
        conn.execute(text("ALTER TABLE mud_weight_change ADD COLUMN IF NOT EXISTS hole_md DOUBLE PRECISION"))
    with engine.begin() as conn:
        conn.execute(text(
            "SELECT create_hypertable('ts_data', 'ts', if_not_exists => TRUE, "
            "migrate_data => TRUE, chunk_time_interval => INTERVAL '7 days')"
        ))
