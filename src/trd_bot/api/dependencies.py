from trd_bot.research import (
    InMemoryExperimentRegistry,
    InMemoryWalkForwardRunRegistry,
)

_experiment_registry = InMemoryExperimentRegistry()
_walk_forward_run_registry = InMemoryWalkForwardRunRegistry()


def get_experiment_registry() -> InMemoryExperimentRegistry:
    """Return the application experiment registry."""

    return _experiment_registry


def get_walk_forward_run_registry() -> InMemoryWalkForwardRunRegistry:
    """Return the application walk-forward run registry."""

    return _walk_forward_run_registry
