import hashlib
import json
from datetime import UTC, datetime
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from trd_bot.research.datasets import DatasetSnapshot


class WalkForwardMode(StrEnum):
    """Supported training-window behaviors."""

    ROLLING = "rolling"
    EXPANDING = "expanding"


class WalkForwardConfig(BaseModel):
    """Configuration for chronological train and test folds."""

    model_config = ConfigDict(frozen=True)

    train_candles: int = Field(ge=2)
    test_candles: int = Field(ge=1)
    step_candles: int = Field(ge=1)
    gap_candles: int = Field(default=0, ge=0)
    mode: WalkForwardMode = WalkForwardMode.ROLLING

    @model_validator(mode="after")
    def prevent_overlapping_test_windows(self) -> Self:
        if self.step_candles < self.test_candles:
            raise ValueError("step candles must be at least test candles")
        return self


class WalkForwardFold(BaseModel):
    """One chronological train-gap-test split using exclusive end indexes."""

    model_config = ConfigDict(frozen=True)

    fold_number: int = Field(ge=1)
    train_start_index: int = Field(ge=0)
    train_end_index: int = Field(ge=1)
    test_start_index: int = Field(ge=1)
    test_end_index: int = Field(ge=1)
    train_start_time: datetime
    train_end_time: datetime
    test_start_time: datetime
    test_end_time: datetime

    @field_validator(
        "train_start_time",
        "train_end_time",
        "test_start_time",
        "test_end_time",
    )
    @classmethod
    def timestamp_must_be_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must include timezone information")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_chronology(self) -> Self:
        if self.train_start_index >= self.train_end_index:
            raise ValueError("training window must contain at least one candle")
        if self.train_end_index > self.test_start_index:
            raise ValueError("training window cannot overlap test window")
        if self.test_start_index >= self.test_end_index:
            raise ValueError("test window must contain at least one candle")
        if self.train_start_time >= self.train_end_time:
            raise ValueError("training timestamps must be chronological")
        if self.train_end_time > self.test_start_time:
            raise ValueError("training time cannot extend into test time")
        if self.test_start_time >= self.test_end_time:
            raise ValueError("test timestamps must be chronological")
        return self


class WalkForwardPlan(BaseModel):
    """Deterministic collection of walk-forward folds for one dataset."""

    model_config = ConfigDict(frozen=True)

    plan_id: str = Field(pattern=r"^walk-forward-[a-f0-9]{16}$")
    dataset_id: str = Field(min_length=1)
    candle_count: int = Field(gt=0)
    config: WalkForwardConfig
    folds: tuple[WalkForwardFold, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_plan(self) -> Self:
        expected_plan_id = build_walk_forward_plan_id(
            dataset_id=self.dataset_id,
            config=self.config,
        )
        if self.plan_id != expected_plan_id:
            raise ValueError("walk-forward plan ID is inconsistent")

        previous_test_start: int | None = None
        for expected_number, fold in enumerate(self.folds, start=1):
            if fold.fold_number != expected_number:
                raise ValueError("walk-forward fold numbers must be continuous")
            if fold.test_end_index > self.candle_count:
                raise ValueError("walk-forward fold exceeds dataset size")
            if fold.test_end_index - fold.test_start_index != self.config.test_candles:
                raise ValueError("test window size does not match config")
            if fold.test_start_index - fold.train_end_index != self.config.gap_candles:
                raise ValueError("fold gap does not match config")

            train_size = fold.train_end_index - fold.train_start_index
            if self.config.mode == WalkForwardMode.ROLLING:
                if train_size != self.config.train_candles:
                    raise ValueError("rolling training window size does not match config")
            else:
                if fold.train_start_index != 0:
                    raise ValueError("expanding training window must start at index zero")
                if train_size < self.config.train_candles:
                    raise ValueError("expanding training window is smaller than config")

            if (
                previous_test_start is not None
                and fold.test_start_index - previous_test_start != self.config.step_candles
            ):
                raise ValueError("fold step does not match config")
            previous_test_start = fold.test_start_index

        return self


def build_walk_forward_plan_id(
    *,
    dataset_id: str,
    config: WalkForwardConfig,
) -> str:
    """Build a deterministic identifier for one fold configuration."""

    config_payload = json.dumps(
        config.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    )
    identity = "::".join([dataset_id, config_payload])
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    return f"walk-forward-{digest[:16]}"


class WalkForwardPlanner:
    """Create chronological folds without using future candles for training."""

    def plan(
        self,
        *,
        dataset: DatasetSnapshot,
        config: WalkForwardConfig,
    ) -> WalkForwardPlan:
        folds: list[WalkForwardFold] = []
        test_start_index = config.train_candles + config.gap_candles

        while test_start_index + config.test_candles <= dataset.candle_count:
            train_end_index = test_start_index - config.gap_candles
            train_start_index = (
                0
                if config.mode == WalkForwardMode.EXPANDING
                else train_end_index - config.train_candles
            )
            test_end_index = test_start_index + config.test_candles

            train_start_candle = dataset.candles[train_start_index]
            train_end_candle = dataset.candles[train_end_index - 1]
            test_start_candle = dataset.candles[test_start_index]
            test_end_candle = dataset.candles[test_end_index - 1]

            folds.append(
                WalkForwardFold(
                    fold_number=len(folds) + 1,
                    train_start_index=train_start_index,
                    train_end_index=train_end_index,
                    test_start_index=test_start_index,
                    test_end_index=test_end_index,
                    train_start_time=train_start_candle.open_time,
                    train_end_time=train_end_candle.close_time,
                    test_start_time=test_start_candle.open_time,
                    test_end_time=test_end_candle.close_time,
                )
            )
            test_start_index += config.step_candles

        if not folds:
            required_candles = config.train_candles + config.gap_candles + config.test_candles
            raise ValueError(f"dataset requires at least {required_candles} candles for one fold")

        return WalkForwardPlan(
            plan_id=build_walk_forward_plan_id(
                dataset_id=dataset.dataset_id,
                config=config,
            ),
            dataset_id=dataset.dataset_id,
            candle_count=dataset.candle_count,
            config=config,
            folds=tuple(folds),
        )
