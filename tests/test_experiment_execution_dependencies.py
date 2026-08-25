from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from trd_bot.api.dependencies import (
    get_experiment_execution_repository,
)
from trd_bot.db.base import DatabaseBase
from trd_bot.db.experiment_execution_repositories import (
    SqlAlchemyExperimentExecutionRepository,
)
from trd_bot.db.session import get_database_session
from trd_bot.main import app


def test_returns_sqlalchemy_execution_repository() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")

    DatabaseBase.metadata.create_all(engine)

    session_factory = sessionmaker(
        bind=engine,
        class_=Session,
        expire_on_commit=False,
    )

    def override_database_session() -> Iterator[Session]:
        with session_factory() as session:
            yield session

    previous_overrides = app.dependency_overrides.copy()

    app.dependency_overrides[get_database_session] = override_database_session

    try:
        dependency = app.dependency_overrides[get_database_session]
        session_iterator = dependency()
        session = next(session_iterator)

        repository = get_experiment_execution_repository(session)

        assert isinstance(
            repository,
            SqlAlchemyExperimentExecutionRepository,
        )

        session_iterator.close()
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)
        engine.dispose()
