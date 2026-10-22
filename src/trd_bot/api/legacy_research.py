from typing import Literal, NamedTuple

from fastapi import HTTPException, Request
from pydantic import BaseModel, ConfigDict


class LegacyResearchReplacement(NamedTuple):
    endpoint: str
    migration_steps: tuple[str, ...]


EXPERIMENT_EXECUTION_ENDPOINT = "/api/v1/research/experiment-executions"
WALK_FORWARD_EXECUTION_ENDPOINT = "/api/v1/research/walk-forward-executions"

_PERSIST_DATASET_STEP = "Persist or import the historical dataset before requesting execution."
_SUBMIT_EXPERIMENT_STEP = (
    "Submit the stored dataset ID and versioned strategy parameters to the durable "
    "experiment execution endpoint."
)
_SUBMIT_WALK_FORWARD_STEP = (
    "Submit the stored dataset ID, versioned strategy parameters, and fold configuration "
    "to the durable walk-forward execution endpoint."
)

LEGACY_SYNCHRONOUS_RESEARCH_ROUTES: dict[str, LegacyResearchReplacement] = {
    "/api/v1/research/ema-crossover": LegacyResearchReplacement(
        endpoint=EXPERIMENT_EXECUTION_ENDPOINT,
        migration_steps=(_PERSIST_DATASET_STEP, _SUBMIT_EXPERIMENT_STEP),
    ),
    "/api/v1/research/experiments/ema-crossover": LegacyResearchReplacement(
        endpoint=EXPERIMENT_EXECUTION_ENDPOINT,
        migration_steps=(_PERSIST_DATASET_STEP, _SUBMIT_EXPERIMENT_STEP),
    ),
    "/api/v1/research/experiments/ema-crossover/from-dataset": LegacyResearchReplacement(
        endpoint=EXPERIMENT_EXECUTION_ENDPOINT,
        migration_steps=(_SUBMIT_EXPERIMENT_STEP,),
    ),
    "/api/v1/research/walk-forward/ema-crossover": LegacyResearchReplacement(
        endpoint=WALK_FORWARD_EXECUTION_ENDPOINT,
        migration_steps=(_PERSIST_DATASET_STEP, _SUBMIT_WALK_FORWARD_STEP),
    ),
    "/api/v1/research/walk-forward/runs/ema-crossover": LegacyResearchReplacement(
        endpoint=WALK_FORWARD_EXECUTION_ENDPOINT,
        migration_steps=(_PERSIST_DATASET_STEP, _SUBMIT_WALK_FORWARD_STEP),
    ),
    "/api/v1/research/walk-forward/runs/ema-crossover/from-dataset": (
        LegacyResearchReplacement(
            endpoint=WALK_FORWARD_EXECUTION_ENDPOINT,
            migration_steps=(_SUBMIT_WALK_FORWARD_STEP,),
        )
    ),
}


class LegacyResearchRetirementDetail(BaseModel):
    """Machine-readable migration response for a retired synchronous route."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    code: Literal["legacy_synchronous_research_route_retired"]
    message: str
    replacement_endpoint: str
    migration_steps: tuple[str, ...]


class LegacyResearchRetirementResponse(BaseModel):
    """FastAPI error envelope for retired synchronous research execution."""

    detail: LegacyResearchRetirementDetail


def enforce_legacy_research_route_retirement(request: Request) -> None:
    """Reject synchronous heavy execution while preserving a migration tombstone."""

    replacement = LEGACY_SYNCHRONOUS_RESEARCH_ROUTES.get(request.url.path)
    if replacement is None:
        raise RuntimeError("legacy research retirement gate used by an unknown route")

    detail = LegacyResearchRetirementDetail(
        code="legacy_synchronous_research_route_retired",
        message=(
            "Synchronous research execution is retired. Submit a durable background job "
            "and poll its execution resource instead."
        ),
        replacement_endpoint=replacement.endpoint,
        migration_steps=replacement.migration_steps,
    )
    raise HTTPException(
        status_code=410,
        detail=detail.model_dump(mode="json"),
        headers={
            "Cache-Control": "no-store",
            "Deprecation": "@1791676800",
            "Sunset": "Sun, 11 Oct 2026 00:00:00 GMT",
            "Link": f'<{replacement.endpoint}>; rel="successor-version"',
        },
    )
