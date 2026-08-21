import hashlib
import json
from datetime import UTC, datetime
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from trd_bot.research.datasets import DatasetBuilder, DatasetSnapshot


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


class WalkForwardDatasetSplit(BaseModel):
    """Materialized train and test datasets for one walk-forward fold."""

    model_config = ConfigDict(frozen=True)

    split_id: str = Field(pattern=r"^walk-forward-split-[a-f0-9]{16}$")
    source_dataset_id: str = Field(min_length=1)
    plan_id: str = Field(pattern=r"^walk-forward-[a-f0-9]{16}$")
    fold: WalkForwardFold
    train_dataset: DatasetSnapshot
    test_dataset: DatasetSnapshot

    @model_validator(mode="after")
    def validate_split(self) -> Self:
        expected_split_id = build_walk_forward_split_id(
            source_dataset_id=self.source_dataset_id,
            plan_id=self.plan_id,
            fold_number=self.fold.fold_number,
            train_dataset_id=self.train_dataset.dataset_id,
            test_dataset_id=self.test_dataset.dataset_id,
        )
        if self.split_id != expected_split_id:
            raise ValueError("walk-forward split ID is inconsistent")

        train_size = self.fold.train_end_index - self.fold.train_start_index
        test_size = self.fold.test_end_index - self.fold.test_start_index
        if self.train_dataset.candle_count != train_size:
            raise ValueError("training dataset size does not match fold")
        if self.test_dataset.candle_count != test_size:
            raise ValueError("test dataset size does not match fold")

        if self.train_dataset.start_time != self.fold.train_start_time:
            raise ValueError("training dataset start time does not match fold")
        if self.train_dataset.end_time != self.fold.train_end_time:
            raise ValueError("training dataset end time does not match fold")
        if self.test_dataset.start_time != self.fold.test_start_time:
            raise ValueError("test dataset start time does not match fold")
        if self.test_dataset.end_time != self.fold.test_end_time:
            raise ValueError("test dataset end time does not match fold")

        if self.train_dataset.end_time > self.test_dataset.start_time:
            raise ValueError("training dataset cannot overlap test dataset")
        if self.train_dataset.source != self.test_dataset.source:
            raise ValueError("training and test datasets must use the same source")
        if self.train_dataset.pair != self.test_dataset.pair:
            raise ValueError("training and test datasets must use the same pair")
        if self.train_dataset.timeframe != self.test_dataset.timeframe:
            raise ValueError("training and test datasets must use the same timeframe")
        return self


class WalkForwardMaterialization(BaseModel):
    """All materialized datasets produced from one walk-forward plan."""

    model_config = ConfigDict(frozen=True)

    source_dataset_id: str = Field(min_length=1)
    plan: WalkForwardPlan
    splits: tuple[WalkForwardDatasetSplit, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_materialization(self) -> Self:
        if self.source_dataset_id != self.plan.dataset_id:
            raise ValueError("source dataset does not match walk-forward plan")
        if len(self.splits) != len(self.plan.folds):
            raise ValueError("materialized split count does not match plan")

        for fold, split in zip(self.plan.folds, self.splits, strict=True):
            if split.source_dataset_id != self.source_dataset_id:
                raise ValueError("split source dataset does not match materialization")
            if split.plan_id != self.plan.plan_id:
                raise ValueError("split plan ID does not match materialization")
            if split.fold != fold:
                raise ValueError("materialized split does not match plan fold")
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


def build_walk_forward_split_id(
    *,
    source_dataset_id: str,
    plan_id: str,
    fold_number: int,
    train_dataset_id: str,
    test_dataset_id: str,
) -> str:
    """Build a deterministic identifier for one materialized fold."""

    identity = "::".join(
        [
            source_dataset_id,
            plan_id,
            str(fold_number),
            train_dataset_id,
            test_dataset_id,
        ]
    )
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    return f"walk-forward-split-{digest[:16]}"


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


class WalkForwardDatasetMaterializer:
    """Create deterministic train and test datasets for every planned fold."""

    def __init__(self, dataset_builder: DatasetBuilder | None = None) -> None:
        self._dataset_builder = dataset_builder or DatasetBuilder()

    def materialize(
        self,
        *,
        dataset: DatasetSnapshot,
        plan: WalkForwardPlan,
    ) -> WalkForwardMaterialization:
        if plan.dataset_id != dataset.dataset_id:
            raise ValueError("walk-forward plan does not belong to dataset")
        if plan.candle_count != dataset.candle_count:
            raise ValueError("walk-forward plan candle count does not match dataset")

        splits: list[WalkForwardDatasetSplit] = []

        for fold in plan.folds:
            train_dataset = self._dataset_builder.build(
                name=f"walk-forward fold {fold.fold_number} train",
                candles=dataset.candles[fold.train_start_index : fold.train_end_index],
                created_at=dataset.created_at,
            )
            test_dataset = self._dataset_builder.build(
                name=f"walk-forward fold {fold.fold_number} test",
                candles=dataset.candles[fold.test_start_index : fold.test_end_index],
                created_at=dataset.created_at,
            )

            splits.append(
                WalkForwardDatasetSplit(
                    split_id=build_walk_forward_split_id(
                        source_dataset_id=dataset.dataset_id,
                        plan_id=plan.plan_id,
                        fold_number=fold.fold_number,
                        train_dataset_id=train_dataset.dataset_id,
                        test_dataset_id=test_dataset.dataset_id,
                    ),
                    source_dataset_id=dataset.dataset_id,
                    plan_id=plan.plan_id,
                    fold=fold,
                    train_dataset=train_dataset,
                    test_dataset=test_dataset,
                )
            )

        return WalkForwardMaterialization(
            source_dataset_id=dataset.dataset_id,
            plan=plan,
            splits=tuple(splits),
        )
