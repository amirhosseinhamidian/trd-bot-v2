from datetime import UTC, datetime
from typing import Annotated, Self

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from trd_bot.api.dependencies import (
    get_candidate_journal_repository,
    get_simulated_portfolio_repository,
)
from trd_bot.db import SqlAlchemyCandidateJournalRepository
from trd_bot.paper import SimulatedPortfolio, SimulatedPortfolioRepository
from trd_bot.research import RiskDashboardBuilder, RiskDashboardReport
from trd_bot.research.candidate_journal import CandidateJournalEntry

router = APIRouter(
    prefix="/research/risk",
    tags=["Historical risk dashboard"],
)

CandidateJournalRepositoryDependency = Annotated[
    SqlAlchemyCandidateJournalRepository,
    Depends(get_candidate_journal_repository),
]
PortfolioRepositoryDependency = Annotated[
    SimulatedPortfolioRepository,
    Depends(get_simulated_portfolio_repository),
]


class RiskDashboardParams(BaseModel):
    """Inclusive risk-decision window and optional simulated portfolio scope."""

    model_config = ConfigDict(extra="forbid")

    from_time: datetime | None = None
    to_time: datetime | None = None
    portfolio_id: str | None = Field(
        default=None,
        pattern=r"^portfolio-[a-f0-9]{16}$",
    )

    @field_validator("from_time", "to_time")
    @classmethod
    def time_must_be_timezone_aware(
        cls,
        value: datetime | None,
    ) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("risk dashboard time must include timezone information")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_time_range(self) -> Self:
        if (
            self.from_time is not None
            and self.to_time is not None
            and self.to_time < self.from_time
        ):
            raise ValueError("to_time must be on or after from_time")
        return self


RiskDashboardParamsQuery = Annotated[RiskDashboardParams, Query()]


def _all_journals(
    repository: SqlAlchemyCandidateJournalRepository,
) -> tuple[CandidateJournalEntry, ...]:
    total = repository.count()
    if total == 0:
        return ()
    return repository.list_page(limit=total, offset=0)


def _selected_portfolios(
    repository: SimulatedPortfolioRepository,
    *,
    portfolio_id: str | None,
) -> tuple[SimulatedPortfolio, ...]:
    if portfolio_id is not None:
        portfolio = repository.get(portfolio_id)
        if portfolio is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="simulated portfolio not found",
            )
        return (portfolio,)

    total = repository.count()
    if total == 0:
        return ()
    return repository.list_page(limit=total, offset=0)


@router.get(
    "",
    response_model=RiskDashboardReport,
)
def get_risk_dashboard(
    journals: CandidateJournalRepositoryDependency,
    portfolios: PortfolioRepositoryDependency,
    params: RiskDashboardParamsQuery,
) -> RiskDashboardReport:
    """Return a read-only risk projection from persisted simulation events."""

    return RiskDashboardBuilder().build(
        journals=_all_journals(journals),
        portfolios=_selected_portfolios(
            portfolios,
            portfolio_id=params.portfolio_id,
        ),
        from_time=params.from_time,
        to_time=params.to_time,
        portfolio_id=params.portfolio_id,
    )
