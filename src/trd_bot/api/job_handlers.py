from collections.abc import Mapping

from trd_bot.api.background_jobs import (
    run_experiment_execution_job,
    run_walk_forward_execution_job,
)
from trd_bot.jobs import (
    BackgroundJobContext,
    BackgroundJobHandlerRegistry,
    BackgroundJobKind,
)


def _required_string(payload: Mapping[str, object], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'background job payload requires string field "{field}"')
    return value.strip()


def run_experiment_job(
    context: BackgroundJobContext,
    payload: Mapping[str, object],
) -> str:
    execution_id = _required_string(payload, "execution_id")
    if context.cancellation_requested():
        return execution_id
    run_experiment_execution_job(execution_id)
    return execution_id


def run_walk_forward_job(
    context: BackgroundJobContext,
    payload: Mapping[str, object],
) -> str:
    execution_id = _required_string(payload, "execution_id")
    if context.cancellation_requested():
        return execution_id
    run_walk_forward_execution_job(execution_id)
    return execution_id


def build_background_job_handler_registry() -> BackgroundJobHandlerRegistry:
    """Build the production allowlist; later stages add import and optimization handlers."""

    return BackgroundJobHandlerRegistry(
        {
            BackgroundJobKind.EXPERIMENT_EXECUTION: run_experiment_job,
            BackgroundJobKind.WALK_FORWARD_EXECUTION: run_walk_forward_job,
        }
    )
