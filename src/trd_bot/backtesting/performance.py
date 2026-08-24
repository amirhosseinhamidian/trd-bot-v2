from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from trd_bot.backtesting.models import (
    BacktestConfig,
    BacktestEvent,
    BacktestEventType,
    ExitReason,
    PositionSide,
)
from trd_bot.domain.market_data import TradingPair

MONEY_QUANTUM = Decimal("0.00000001")


def quantize_money(value: Decimal) -> Decimal:
    """Normalize simulated monetary values to eight decimal places."""

    return value.quantize(
        MONEY_QUANTUM,
        rounding=ROUND_HALF_EVEN,
    )


class ClosedBacktestTrade(BaseModel):
    """One completed simulated trade reconstructed from backtest events."""

    model_config = ConfigDict(frozen=True)

    trade_number: int = Field(ge=1)
    pair: TradingPair
    side: PositionSide
    entry_time: datetime
    exit_time: datetime
    entry_price: Decimal = Field(gt=0)
    exit_price: Decimal = Field(gt=0)
    quantity: Decimal = Field(gt=0)
    gross_pnl: Decimal
    fees: Decimal = Field(ge=0)
    net_pnl: Decimal
    exit_reason: ExitReason

    @field_validator("entry_time", "exit_time")
    @classmethod
    def timestamp_must_be_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must include timezone information")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_trade(self) -> Self:
        if self.exit_time <= self.entry_time:
            raise ValueError("trade exit time must be after entry time")
        if self.net_pnl != self.gross_pnl - self.fees:
            raise ValueError("trade net PnL must equal gross PnL minus fees")
        return self


class EquityPoint(BaseModel):
    """Realized account equity after one closed simulated trade."""

    model_config = ConfigDict(frozen=True)

    trade_number: int = Field(ge=1)
    timestamp: datetime
    balance: Decimal
    peak_balance: Decimal = Field(gt=0)
    drawdown: Decimal = Field(ge=0)
    drawdown_fraction: Decimal = Field(ge=0)

    @field_validator("timestamp")
    @classmethod
    def timestamp_must_be_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must include timezone information")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_point(self) -> Self:
        if self.drawdown != self.peak_balance - self.balance:
            raise ValueError("drawdown must equal peak balance minus current balance")
        if self.drawdown_fraction != self.drawdown / self.peak_balance:
            raise ValueError("drawdown fraction is inconsistent with drawdown")
        return self


class BacktestPerformanceReport(BaseModel):
    """Aggregated realized performance for one simulated backtest run."""

    model_config = ConfigDict(frozen=True)

    run_id: str = Field(min_length=1, max_length=200)
    dataset_id: str = Field(min_length=1)
    starting_balance: Decimal = Field(gt=0)
    ending_balance: Decimal
    gross_pnl: Decimal
    total_fees: Decimal = Field(ge=0)
    net_pnl: Decimal
    total_return: Decimal
    gross_profit: Decimal = Field(ge=0)
    gross_loss: Decimal = Field(ge=0)
    profit_factor: Decimal | None = Field(default=None, ge=0)
    peak_balance: Decimal = Field(gt=0)
    max_drawdown: Decimal = Field(ge=0)
    max_drawdown_fraction: Decimal = Field(ge=0)
    total_trades: int = Field(ge=0)
    winning_trades: int = Field(ge=0)
    losing_trades: int = Field(ge=0)
    flat_trades: int = Field(ge=0)
    win_rate: Decimal | None = Field(default=None, ge=0, le=1)
    trades: tuple[ClosedBacktestTrade, ...] = ()
    equity_curve: tuple[EquityPoint, ...] = ()

    @model_validator(mode="after")
    def validate_report(self) -> Self:
        if self.total_trades != len(self.trades):
            raise ValueError("total trades must match the trade collection")
        if self.total_trades != len(self.equity_curve):
            raise ValueError("total trades must match the equity curve")
        outcomes = self.winning_trades + self.losing_trades + self.flat_trades
        if outcomes != self.total_trades:
            raise ValueError("trade outcome counts must equal total trades")
        if self.ending_balance != self.starting_balance + self.net_pnl:
            raise ValueError("ending balance must equal starting balance plus net PnL")
        if self.net_pnl != self.gross_pnl - self.total_fees:
            raise ValueError("net PnL must equal gross PnL minus fees")
        if self.net_pnl != self.gross_profit - self.gross_loss:
            raise ValueError("net PnL must equal gross profit minus gross loss")
        if self.total_return != self.net_pnl / self.starting_balance:
            raise ValueError("total return must equal net PnL divided by starting balance")

        expected_profit_factor = (
            self.gross_profit / self.gross_loss if self.gross_loss > 0 else None
        )
        if self.profit_factor != expected_profit_factor:
            raise ValueError("profit factor is inconsistent with profit and loss")

        expected_peak_balance = max(
            (point.peak_balance for point in self.equity_curve),
            default=self.starting_balance,
        )
        if self.peak_balance != expected_peak_balance:
            raise ValueError("peak balance is inconsistent with the equity curve")

        expected_max_drawdown = max(
            (point.drawdown for point in self.equity_curve),
            default=Decimal("0"),
        )
        if self.max_drawdown != expected_max_drawdown:
            raise ValueError("maximum drawdown is inconsistent with the equity curve")

        expected_max_drawdown_fraction = max(
            (point.drawdown_fraction for point in self.equity_curve),
            default=Decimal("0"),
        )
        if self.max_drawdown_fraction != expected_max_drawdown_fraction:
            raise ValueError("maximum drawdown fraction is inconsistent with the equity curve")

        for expected_trade_number, point in enumerate(self.equity_curve, start=1):
            if point.trade_number != expected_trade_number:
                raise ValueError("equity curve trade numbers must be continuous")

        if self.equity_curve and self.equity_curve[-1].balance != self.ending_balance:
            raise ValueError("final equity point must match ending balance")
        if self.total_trades == 0 and self.win_rate is not None:
            raise ValueError("an empty report cannot have a win rate")
        if self.total_trades > 0:
            expected_win_rate = Decimal(self.winning_trades) / Decimal(self.total_trades)
            if self.win_rate != expected_win_rate:
                raise ValueError("win rate is inconsistent with trade outcomes")
        return self


class BacktestPerformanceAnalyzer:
    """Reconstruct closed trades and calculate realized backtest performance."""

    def analyze(
        self,
        *,
        run_id: str,
        dataset_id: str,
        events: Sequence[BacktestEvent],
        config: BacktestConfig,
    ) -> BacktestPerformanceReport:
        if not run_id.strip():
            raise ValueError("run ID cannot be empty")
        if not dataset_id.strip():
            raise ValueError("dataset ID cannot be empty")

        self._validate_sequence(events)
        trades: list[ClosedBacktestTrade] = []
        opened_event: BacktestEvent | None = None

        for event in events:
            if event.event_type == BacktestEventType.POSITION_OPENED:
                if opened_event is not None:
                    raise ValueError("cannot open a position while another position is open")
                opened_event = event
                continue
            if opened_event is None:
                raise ValueError("cannot close a position before it is opened")
            trades.append(
                self._build_trade(
                    trade_number=len(trades) + 1,
                    opened_event=opened_event,
                    closed_event=event,
                    fee_rate=config.fee_rate,
                )
            )
            opened_event = None

        if opened_event is not None:
            raise ValueError("backtest events contain an unclosed position")

        gross_pnl = sum(
            (trade.gross_pnl for trade in trades),
            start=Decimal("0"),
        )

        total_fees = sum(
            (trade.fees for trade in trades),
            start=Decimal("0"),
        )

        net_pnl = sum(
            (trade.net_pnl for trade in trades),
            start=Decimal("0"),
        )
        gross_profit = sum(
            (trade.net_pnl for trade in trades if trade.net_pnl > 0),
            start=Decimal("0"),
        )
        gross_loss = sum(
            (-trade.net_pnl for trade in trades if trade.net_pnl < 0),
            start=Decimal("0"),
        )
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else None
        equity_curve = self._build_equity_curve(
            trades=trades,
            starting_balance=config.starting_balance,
        )
        peak_balance = max(
            (point.peak_balance for point in equity_curve),
            default=config.starting_balance,
        )
        max_drawdown = max(
            (point.drawdown for point in equity_curve),
            default=Decimal("0"),
        )
        max_drawdown_fraction = max(
            (point.drawdown_fraction for point in equity_curve),
            default=Decimal("0"),
        )
        winning_trades = sum(trade.net_pnl > 0 for trade in trades)
        losing_trades = sum(trade.net_pnl < 0 for trade in trades)
        flat_trades = sum(trade.net_pnl == 0 for trade in trades)
        total_trades = len(trades)
        win_rate = Decimal(winning_trades) / Decimal(total_trades) if total_trades else None

        return BacktestPerformanceReport(
            run_id=run_id,
            dataset_id=dataset_id,
            starting_balance=config.starting_balance,
            ending_balance=config.starting_balance + net_pnl,
            gross_pnl=gross_pnl,
            total_fees=total_fees,
            net_pnl=net_pnl,
            total_return=net_pnl / config.starting_balance,
            gross_profit=gross_profit,
            gross_loss=gross_loss,
            profit_factor=profit_factor,
            peak_balance=peak_balance,
            max_drawdown=max_drawdown,
            max_drawdown_fraction=max_drawdown_fraction,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            flat_trades=flat_trades,
            win_rate=win_rate,
            trades=tuple(trades),
            equity_curve=equity_curve,
        )

    @staticmethod
    def _build_equity_curve(
        *,
        trades: Sequence[ClosedBacktestTrade],
        starting_balance: Decimal,
    ) -> tuple[EquityPoint, ...]:
        balance = starting_balance
        peak_balance = starting_balance
        points: list[EquityPoint] = []

        for trade in trades:
            balance += trade.net_pnl
            peak_balance = max(peak_balance, balance)
            drawdown = peak_balance - balance

            points.append(
                EquityPoint(
                    trade_number=trade.trade_number,
                    timestamp=trade.exit_time,
                    balance=balance,
                    peak_balance=peak_balance,
                    drawdown=drawdown,
                    drawdown_fraction=drawdown / peak_balance,
                )
            )

        return tuple(points)

    @staticmethod
    def _validate_sequence(events: Sequence[BacktestEvent]) -> None:
        for expected_sequence, event in enumerate(events, start=1):
            if event.sequence_number != expected_sequence:
                raise ValueError("backtest event sequence must be continuous and ordered")

    @staticmethod
    def _build_trade(
        *,
        trade_number: int,
        opened_event: BacktestEvent,
        closed_event: BacktestEvent,
        fee_rate: Decimal,
    ) -> ClosedBacktestTrade:
        if closed_event.event_type != BacktestEventType.POSITION_CLOSED:
            raise ValueError("expected a position-closed event")
        if opened_event.pair != closed_event.pair:
            raise ValueError("trade events must use the same pair")
        if opened_event.side != closed_event.side:
            raise ValueError("trade events must use the same position side")
        if opened_event.quantity != closed_event.quantity:
            raise ValueError("trade events must use the same quantity")
        if closed_event.exit_reason is None:
            raise ValueError("closed trade requires an exit reason")

        if opened_event.side == PositionSide.LONG:
            raw_gross_pnl = (closed_event.price - opened_event.price) * opened_event.quantity
        else:
            raw_gross_pnl = (opened_event.price - closed_event.price) * opened_event.quantity

        raw_entry_fee = opened_event.price * opened_event.quantity * fee_rate

        raw_exit_fee = closed_event.price * closed_event.quantity * fee_rate

        gross_pnl = quantize_money(raw_gross_pnl)

        fees = quantize_money(raw_entry_fee + raw_exit_fee)

        net_pnl = quantize_money(gross_pnl - fees)

        return ClosedBacktestTrade(
            trade_number=trade_number,
            pair=opened_event.pair,
            side=opened_event.side,
            entry_time=opened_event.timestamp,
            exit_time=closed_event.timestamp,
            entry_price=opened_event.price,
            exit_price=closed_event.price,
            quantity=opened_event.quantity,
            gross_pnl=gross_pnl,
            fees=fees,
            net_pnl=net_pnl,
            exit_reason=closed_event.exit_reason,
        )
