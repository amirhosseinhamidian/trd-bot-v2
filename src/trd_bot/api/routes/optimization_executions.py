from fastapi import APIRouter, Depends, HTTPException

from trd_bot.api.dependencies import (
    get_optimization_execution_repository as provide_optimization_execution_repository,
)
from trd_bot.api.dependencies import (
    get_optimization_runner,
)
from trd_bot.research.optimization_executions import (
    OptimizationExecution,
    OptimizationExecutionRepository,
)
from trd_bot.research.optimization_runner import OptimizationRunner

router = APIRouter(
    prefix="/optimization-executions",
    tags=["optimization"],
)


def _missing_execution(execution_id: str) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail=f"optimization execution {execution_id} not found",
    )


@router.post("/{execution_id}/start", response_model=OptimizationExecution)
def start_optimization_execution(
    execution_id: str,
    runner: OptimizationRunner = Depends(get_optimization_runner),  # noqa: B008
    repository: OptimizationExecutionRepository = Depends(  # noqa: B008
        provide_optimization_execution_repository
    ),
) -> OptimizationExecution:
    execution = repository.get(execution_id)
    if execution is None:
        raise _missing_execution(execution_id)

    return runner.start(execution)


@router.post("/{execution_id}/complete", response_model=OptimizationExecution)
def complete_optimization_execution(
    execution_id: str,
    runner: OptimizationRunner = Depends(get_optimization_runner),  # noqa: B008
    repository: OptimizationExecutionRepository = Depends(  # noqa: B008
        provide_optimization_execution_repository
    ),
) -> OptimizationExecution:
    execution = repository.get(execution_id)
    if execution is None:
        raise _missing_execution(execution_id)

    if execution.best_experiment_id is None:
        raise HTTPException(
            status_code=400,
            detail="best experiment id is required",
        )

    return runner.complete(
        execution,
        best_experiment_id=execution.best_experiment_id,
    )


@router.post("/{execution_id}/fail", response_model=OptimizationExecution)
def fail_optimization_execution(
    execution_id: str,
    runner: OptimizationRunner = Depends(get_optimization_runner),  # noqa: B008
    repository: OptimizationExecutionRepository = Depends(  # noqa: B008
        provide_optimization_execution_repository
    ),
) -> OptimizationExecution:
    execution = repository.get(execution_id)
    if execution is None:
        raise _missing_execution(execution_id)

    return runner.fail(
        execution,
        error_code="execution_failed",
        error_message="optimization execution failed",
    )


@router.post("", response_model=OptimizationExecution)
def create_optimization_execution(
    execution: OptimizationExecution,
    runner: OptimizationRunner = Depends(get_optimization_runner),  # noqa: B008
) -> OptimizationExecution:
    return runner.create(execution)


@router.get("/{execution_id}", response_model=OptimizationExecution)
def get_optimization_execution(
    execution_id: str,
    repository: OptimizationExecutionRepository = Depends(  # noqa: B008
        provide_optimization_execution_repository
    ),
) -> OptimizationExecution:
    execution = repository.get(execution_id)
    if execution is None:
        raise _missing_execution(execution_id)

    return execution
