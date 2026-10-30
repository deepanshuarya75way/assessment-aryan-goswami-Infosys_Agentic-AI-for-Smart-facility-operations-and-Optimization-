from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base

from app.core.config import settings

connect_args = {"check_same_thread": False, "timeout": 15} if settings.DATABASE_URL.startswith("sqlite") else {}
# Default pool_size(5)+max_overflow(10)=15 concurrent connections is too
# tight for this app's real usage pattern: 4 dashboards each polling every
# 30s, plus manual investigate/add/delete calls layered on top, can burst
# past 15 simultaneous DB-touching requests and start timing out with
# "QueuePool limit ... reached" — which the browser also just sees as a
# failed request. Widened generously since SQLite handles concurrent
# readers fine under WAL (set below).
engine = create_engine(settings.DATABASE_URL, connect_args=connect_args, pool_size=20, max_overflow=20, pool_timeout=30)

if settings.DATABASE_URL.startswith("sqlite"):
    # SQLite's default journal mode serializes writers hard enough that
    # ordinary concurrent traffic — the dashboard's 30s background poll
    # firing in 4 open tabs, an agent investigation writing an alert,
    # someone adding/deleting a record in Manage Dataset — can trip
    # "database is locked" errors that surface to the browser as a
    # random, intermittent failure even though nothing is actually
    # broken. WAL mode lets reads and writes run concurrently instead
    # of blocking each other, and busy_timeout makes any write that
    # still collides retry for 15s instead of failing immediately.
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=15000")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from app.models import anomaly_models  # noqa
    # Import models so they're registered on Base before create_all
    from app.models import energy_models  # noqa
    from app.models import maintenance_models  # noqa
    from app.models import occupancy_models  # noqa
    from app.models import security_models  # noqa
    from app.models import cost_models  # noqa
    from app.models import auth_models  # noqa
    Base.metadata.create_all(bind=engine)
