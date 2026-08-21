from trd_bot.research import InMemoryExperimentRegistry

_experiment_registry = InMemoryExperimentRegistry()


def get_experiment_registry() -> InMemoryExperimentRegistry:
    """Return the application experiment registry."""

    return _experiment_registry
