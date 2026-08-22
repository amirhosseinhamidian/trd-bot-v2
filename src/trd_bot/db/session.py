from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from trd_bot.core.config import get_settings


def create_database_engine(
    database_url: str,
    *,
    echo: bool = False,
) -> Engine:
    """Create a synchronous SQLAlchemy engine for research persistence."""

    if not database_url.strip():
        raise ValueError("database URL cannot be empty")

    url = make_url(database_url)
    connect_args: dict[str, object] = {}
    if url.get_backend_name() == "sqlite":
        connect_args["check_same_thread"] = False

    return create_engine(
        url,
        echo=echo,
        pool_pre_ping=True,
        connect_args=connect_args,
    )


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Create a typed session factory bound to one database engine."""

    return sessionmaker(
        bind=engine,
        class_=Session,
        autoflush=False,
        expire_on_commit=False,
    )


@lru_cache
def get_database_engine() -> Engine:
    """Return the process-wide configured database engine."""

    settings = get_settings()
    return create_database_engine(
        settings.database_url,
        echo=settings.debug,
    )


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    """Return the process-wide configured session factory."""

    return create_session_factory(get_database_engine())


def get_database_session() -> Iterator[Session]:
    """Yield one transaction-scoped database session for API dependencies."""

    with get_session_factory()() as session:
        yield session
