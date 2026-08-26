from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Self

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from trd_bot.api.dependencies import (
    get_dataset_repository,
    get_simulated_portfolio_repository,
)
from trd_bot.api.pagination import Page, PaginationParams, build_page
from trd_bot.paper import (
    PortfolioStatus,
    PortfolioTimelineEvent,
    SimulatedPortfolio,
    SimulatedPortfolioLedger,
    SimulatedPortfolioRepository,
    SimulatedPosition,
    SimulationMode,
)
from trd_bot.research import DatasetRepository

router = APIRouter(
    prefix="/research/portfolios",
    tags=["Offline simulated portfolios"],
)

DatasetRepositoryDependency = Annotated[
    DatasetRepository,
    Depends(get_dataset_repository),
]
PortfolioRepositoryDependency = Annotated[
    SimulatedPortfolioRepository,
    Depends(get_simulated_portfolio_repository),
]
PaginationQuery = Annotated[
    PaginationParams,
    Query(),
]


class SimulatedPortfolioCreateRequest(BaseModel):
    """Configuration for an empty historical-simulation portfolio."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    dataset_id: str = Field(min_length=1, max_length=100)
    mode: SimulationMode = SimulationMode.PAPER
    starting_cash: Decimal = Field(default=Decimal("10000"), gt=0)
    fee_rate: Decimal = Field(default=Decimal("0"), ge=0, lt=1)

    @field_validator("dataset_id")
    @classmethod
    def normalize_dataset_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("dataset ID cannot be empty")
        return normalized


class SimulatedPortfolioSummary(BaseModel):
    """Lightweight portfolio catalog item without aggregate payloads."""

    model_config = ConfigDict(frozen=True)

    portfolio_id: str
    mode: SimulationMode
    status: PortfolioStatus
    dataset_id: str
    created_at: datetime
    updated_at: datetime
    starting_cash: Decimal
    cash: Decimal
    equity: Decimal
    fees_paid: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    position_count: int = Field(ge=0)
    event_count: int = Field(ge=1)

    @classmethod
    def from_portfolio(cls, portfolio: SimulatedPortfolio) -> Self:
        return cls(
            portfolio_id=portfolio.portfolio_id,
            mode=portfolio.mode,
            status=portfolio.status,
            dataset_id=portfolio.dataset_id,
            created_at=portfolio.created_at,
            updated_at=portfolio.updated_at,
            starting_cash=portfolio.starting_cash,
            cash=portfolio.cash,
            equity=portfolio.equity,
            fees_paid=portfolio.fees_paid,
            realized_pnl=portfolio.realized_pnl,
            unrealized_pnl=portfolio.unrealized_pnl,
            position_count=len(portfolio.positions),
            event_count=len(portfolio.timeline),
        )

    @model_validator(mode="after")
    def validate_counts(self) -> Self:
        if self.status is PortfolioStatus.COMPLETED and self.event_count < 2:
            raise ValueError("completed portfolio summary requires lifecycle events")
        return self


def _get_portfolio_or_404(
    portfolio_id: str,
    repository: SimulatedPortfolioRepository,
) -> SimulatedPortfolio:
    portfolio = repository.get(portfolio_id)
    if portfolio is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="simulated portfolio not found",
        )
    return portfolio


@router.post(
    "",
    response_model=SimulatedPortfolio,
    status_code=status.HTTP_201_CREATED,
)
def create_simulated_portfolio(
    request: SimulatedPortfolioCreateRequest,
    datasets: DatasetRepositoryDependency,
    portfolios: PortfolioRepositoryDependency,
) -> SimulatedPortfolio:
    """Create an offline portfolio bound to an existing historical dataset."""

    if datasets.get(request.dataset_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="dataset not found",
        )

    portfolio = SimulatedPortfolioLedger().create(
        mode=request.mode,
        dataset_id=request.dataset_id,
        starting_cash=request.starting_cash,
        fee_rate=request.fee_rate,
        created_at=datetime.now(UTC),
    )
    return portfolios.save(portfolio)


@router.get(
    "",
    response_model=Page[SimulatedPortfolioSummary],
)
def list_simulated_portfolios(
    portfolios: PortfolioRepositoryDependency,
    pagination: PaginationQuery,
) -> Page[SimulatedPortfolioSummary]:
    """List lightweight offline portfolio summaries newest first."""

    items = portfolios.list_page(
        limit=pagination.limit,
        offset=pagination.offset,
    )
    summaries = tuple(SimulatedPortfolioSummary.from_portfolio(item) for item in items)
    return build_page(
        summaries,
        total=portfolios.count(),
        pagination=pagination,
    )


@router.get(
    "/{portfolio_id}/positions",
    response_model=Page[SimulatedPosition],
)
def list_simulated_positions(
    portfolio_id: str,
    portfolios: PortfolioRepositoryDependency,
    pagination: PaginationQuery,
) -> Page[SimulatedPosition]:
    """List positions recorded by one historical simulation."""

    _get_portfolio_or_404(portfolio_id, portfolios)
    positions = portfolios.list_positions(
        portfolio_id=portfolio_id,
        limit=pagination.limit,
        offset=pagination.offset,
    )
    return build_page(
        positions,
        total=portfolios.count_positions(portfolio_id),
        pagination=pagination,
    )


@router.get(
    "/{portfolio_id}/positions/{position_id}",
    response_model=SimulatedPosition,
)
def get_simulated_position(
    portfolio_id: str,
    position_id: str,
    portfolios: PortfolioRepositoryDependency,
) -> SimulatedPosition:
    """Return one position from the requested simulated portfolio."""

    _get_portfolio_or_404(portfolio_id, portfolios)
    position = portfolios.get_position(position_id)
    if position is None or position.portfolio_id != portfolio_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="simulated position not found",
        )
    return position


@router.get(
    "/{portfolio_id}/timeline",
    response_model=Page[PortfolioTimelineEvent],
)
def list_portfolio_timeline(
    portfolio_id: str,
    portfolios: PortfolioRepositoryDependency,
    pagination: PaginationQuery,
) -> Page[PortfolioTimelineEvent]:
    """List the ordered audit timeline of one historical simulation."""

    _get_portfolio_or_404(portfolio_id, portfolios)
    events = portfolios.list_timeline(
        portfolio_id=portfolio_id,
        limit=pagination.limit,
        offset=pagination.offset,
    )
    return build_page(
        events,
        total=portfolios.count_timeline(portfolio_id),
        pagination=pagination,
    )


@router.get(
    "/{portfolio_id}",
    response_model=SimulatedPortfolio,
)
def get_simulated_portfolio(
    portfolio_id: str,
    portfolios: PortfolioRepositoryDependency,
) -> SimulatedPortfolio:
    """Return one complete offline portfolio aggregate."""

    return _get_portfolio_or_404(portfolio_id, portfolios)
