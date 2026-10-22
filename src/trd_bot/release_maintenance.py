import hashlib
import json
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from trd_bot.alerts import AlertExpirySummary
from trd_bot.market_data import (
    MarketDataRetentionMode,
    MarketDataRetentionOutcome,
    MarketDataRetentionRun,
)

RELEASE_MAINTENANCE_POLICY_VERSION = "release-maintenance-policy-v1"
RELEASE_MAINTENANCE_SCHEMA_VERSION = "release-maintenance-plan-v1"


class ReleaseMaintenanceActionCode(StrEnum):
    MARKET_DATA_RETENTION = "market_data_retention"
    DATASET_STAGE_CLEANUP = "dataset_stage_cleanup"
    ALERT_EXPIRY_MATERIALIZATION = "alert_expiry_materialization"
    CANDIDATE_PROJECTION_REBUILD = "candidate_projection_rebuild"


class ReleaseMaintenanceDisposition(StrEnum):
    NOT_REQUIRED = "not_required"
    REQUIRED = "required"
    REVIEW = "review"
    BLOCKED = "blocked"


class ReleaseMaintenanceReasonCode(StrEnum):
    NO_RETENTION_ELIGIBLE = "no_retention_eligible"
    RETENTION_ELIGIBLE = "retention_eligible"
    RETENTION_HOLD_ACTIVE = "retention_hold_active"
    RETENTION_PLAN_FAILED = "retention_plan_failed"
    NO_EXPIRED_DATASET_STAGES = "no_expired_dataset_stages"
    EXPIRED_DATASET_STAGES_PRESENT = "expired_dataset_stages_present"
    NO_ALERT_EXPIRY_PENDING = "no_alert_expiry_pending"
    ALERT_EXPIRY_PENDING = "alert_expiry_pending"
    PROJECTION_CURRENT = "projection_current"
    PROJECTION_LAGGING = "projection_lagging"
    PROJECTION_WITHOUT_JOURNAL = "projection_without_journal"


class ReleaseMaintenancePolicy(BaseModel):
    """Frozen operational limits; this policy never authorizes automatic execution."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["release-maintenance-policy-v1"] = "release-maintenance-policy-v1"
    market_data_batch_limit: int = Field(ge=1, le=500)
    dataset_stage_batch_limit: int = Field(ge=1, le=500)
    alert_expiry_batch_limit: int = Field(ge=1, le=1000)
    automatic_execution_allowed: Literal[False] = False
    immutable_evidence_deletion_allowed: Literal[False] = False

    @property
    def definition_checksum(self) -> str:
        return _checksum(self.model_dump(mode="json"))


class ReleaseMaintenanceSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    evaluated_at: datetime
    market_data_retention_plan: MarketDataRetentionRun
    expired_dataset_stages: int = Field(ge=0)
    alert_expiry: AlertExpirySummary
    candidate_journals: int = Field(ge=0)
    candidate_projections: int = Field(ge=0)
    latest_candidate_journal_at: datetime | None = None
    latest_candidate_projection_at: datetime | None = None

    @field_validator(
        "evaluated_at",
        "latest_candidate_journal_at",
        "latest_candidate_projection_at",
    )
    @classmethod
    def normalize_timestamps(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("release maintenance timestamps must include timezone")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_snapshot(self) -> Self:
        retention = self.market_data_retention_plan
        if retention.mode is not MarketDataRetentionMode.DRY_RUN or retention.deleted_count != 0:
            raise ValueError("release maintenance snapshot requires a retention dry-run")
        if retention.requested_at != self.evaluated_at:
            raise ValueError("retention plan timestamp does not match maintenance snapshot")
        if self.alert_expiry.evaluated_at != self.evaluated_at:
            raise ValueError("alert expiry timestamp does not match maintenance snapshot")
        if (self.candidate_journals == 0) is not (self.latest_candidate_journal_at is None):
            raise ValueError("candidate journal timestamp is inconsistent")
        if (self.candidate_projections == 0) is not (self.latest_candidate_projection_at is None):
            raise ValueError("candidate projection timestamp is inconsistent")
        return self


class ReleaseMaintenanceAction(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    code: ReleaseMaintenanceActionCode
    disposition: ReleaseMaintenanceDisposition
    reason_code: ReleaseMaintenanceReasonCode
    observed_count: int = Field(ge=0)
    batch_limit: int | None = Field(default=None, ge=1)


class ReleaseMaintenancePlan(BaseModel):
    """Commit-bound operations plan with no automatic destructive execution."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["release-maintenance-plan-v1"] = "release-maintenance-plan-v1"
    environment_label: str = Field(min_length=1, max_length=64)
    commit_sha: str = Field(pattern=r"^[a-f0-9]{40}$")
    generated_at: datetime
    policy: ReleaseMaintenancePolicy
    snapshot: ReleaseMaintenanceSnapshot
    actions: tuple[ReleaseMaintenanceAction, ...]
    human_approval_required: bool
    retention_dry_run_audit_written: Literal[True] = True
    automatic_maintenance_executed: Literal[False] = False
    immutable_evidence_deletion_allowed: Literal[False] = False
    external_order_submission_allowed: Literal[False] = False

    @field_validator("generated_at")
    @classmethod
    def normalize_generated_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("release maintenance generation time must include timezone")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_derived_plan(self) -> Self:
        if self.generated_at != self.snapshot.evaluated_at:
            raise ValueError("maintenance plan generation time is inconsistent")
        expected = derive_release_maintenance_actions(self.policy, self.snapshot)
        if self.actions != expected:
            raise ValueError("release maintenance actions are inconsistent")
        approval = any(
            action.disposition is not ReleaseMaintenanceDisposition.NOT_REQUIRED
            for action in expected
        )
        if self.human_approval_required is not approval:
            raise ValueError("release maintenance approval flag is inconsistent")
        return self

    @property
    def report_checksum(self) -> str:
        return _checksum(self.model_dump(mode="json"))


def default_release_maintenance_policy() -> ReleaseMaintenancePolicy:
    return ReleaseMaintenancePolicy(
        market_data_batch_limit=100,
        dataset_stage_batch_limit=100,
        alert_expiry_batch_limit=100,
    )


def derive_release_maintenance_actions(
    policy: ReleaseMaintenancePolicy,
    snapshot: ReleaseMaintenanceSnapshot,
) -> tuple[ReleaseMaintenanceAction, ...]:
    retention = snapshot.market_data_retention_plan
    if retention.outcome is MarketDataRetentionOutcome.FAILED:
        retention_disposition = ReleaseMaintenanceDisposition.BLOCKED
        retention_reason = ReleaseMaintenanceReasonCode.RETENTION_PLAN_FAILED
        retention_count = 0
    elif retention.outcome is MarketDataRetentionOutcome.BLOCKED:
        retention_disposition = ReleaseMaintenanceDisposition.BLOCKED
        retention_reason = ReleaseMaintenanceReasonCode.RETENTION_HOLD_ACTIVE
        retention_count = len(retention.blocking_hold_ids)
    elif retention.selected.total:
        retention_disposition = ReleaseMaintenanceDisposition.REQUIRED
        retention_reason = ReleaseMaintenanceReasonCode.RETENTION_ELIGIBLE
        retention_count = retention.selected.total
    else:
        retention_disposition = ReleaseMaintenanceDisposition.NOT_REQUIRED
        retention_reason = ReleaseMaintenanceReasonCode.NO_RETENTION_ELIGIBLE
        retention_count = 0

    actions = [
        ReleaseMaintenanceAction(
            code=ReleaseMaintenanceActionCode.MARKET_DATA_RETENTION,
            disposition=retention_disposition,
            reason_code=retention_reason,
            observed_count=retention_count,
            batch_limit=policy.market_data_batch_limit,
        ),
        ReleaseMaintenanceAction(
            code=ReleaseMaintenanceActionCode.DATASET_STAGE_CLEANUP,
            disposition=(
                ReleaseMaintenanceDisposition.REQUIRED
                if snapshot.expired_dataset_stages
                else ReleaseMaintenanceDisposition.NOT_REQUIRED
            ),
            reason_code=(
                ReleaseMaintenanceReasonCode.EXPIRED_DATASET_STAGES_PRESENT
                if snapshot.expired_dataset_stages
                else ReleaseMaintenanceReasonCode.NO_EXPIRED_DATASET_STAGES
            ),
            observed_count=snapshot.expired_dataset_stages,
            batch_limit=policy.dataset_stage_batch_limit,
        ),
        ReleaseMaintenanceAction(
            code=ReleaseMaintenanceActionCode.ALERT_EXPIRY_MATERIALIZATION,
            disposition=(
                ReleaseMaintenanceDisposition.REQUIRED
                if snapshot.alert_expiry.pending_total
                else ReleaseMaintenanceDisposition.NOT_REQUIRED
            ),
            reason_code=(
                ReleaseMaintenanceReasonCode.ALERT_EXPIRY_PENDING
                if snapshot.alert_expiry.pending_total
                else ReleaseMaintenanceReasonCode.NO_ALERT_EXPIRY_PENDING
            ),
            observed_count=snapshot.alert_expiry.pending_total,
            batch_limit=policy.alert_expiry_batch_limit,
        ),
        _projection_action(snapshot),
    ]
    return tuple(actions)


def build_release_maintenance_plan(
    *,
    environment_label: str,
    commit_sha: str,
    generated_at: datetime,
    snapshot: ReleaseMaintenanceSnapshot,
    policy: ReleaseMaintenancePolicy | None = None,
) -> ReleaseMaintenancePlan:
    active_policy = policy or default_release_maintenance_policy()
    actions = derive_release_maintenance_actions(active_policy, snapshot)
    return ReleaseMaintenancePlan(
        environment_label=environment_label,
        commit_sha=commit_sha,
        generated_at=generated_at,
        policy=active_policy,
        snapshot=snapshot,
        actions=actions,
        human_approval_required=any(
            action.disposition is not ReleaseMaintenanceDisposition.NOT_REQUIRED
            for action in actions
        ),
    )


def release_maintenance_plan_to_dict(plan: ReleaseMaintenancePlan) -> dict[str, object]:
    payload = plan.model_dump(mode="json")
    payload["policy_checksum"] = plan.policy.definition_checksum
    payload["report_checksum"] = plan.report_checksum
    return payload


def serialize_release_maintenance_plan(plan: ReleaseMaintenancePlan) -> str:
    return json.dumps(
        release_maintenance_plan_to_dict(plan),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )


def parse_release_maintenance_plan(value: str | bytes) -> ReleaseMaintenancePlan:
    try:
        raw = json.loads(value)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("release maintenance plan is not valid JSON") from exc
    if not isinstance(raw, dict):
        raise ValueError("release maintenance plan must be a JSON object")
    payload = dict(raw)
    policy_checksum = payload.pop("policy_checksum", None)
    report_checksum = payload.pop("report_checksum", None)
    plan = ReleaseMaintenancePlan.model_validate(payload)
    if policy_checksum is not None and policy_checksum != plan.policy.definition_checksum:
        raise ValueError("release maintenance policy checksum is inconsistent")
    if report_checksum is not None and report_checksum != plan.report_checksum:
        raise ValueError("release maintenance report checksum is inconsistent")
    return plan


def _projection_action(snapshot: ReleaseMaintenanceSnapshot) -> ReleaseMaintenanceAction:
    if snapshot.candidate_journals == 0 and snapshot.candidate_projections > 0:
        return ReleaseMaintenanceAction(
            code=ReleaseMaintenanceActionCode.CANDIDATE_PROJECTION_REBUILD,
            disposition=ReleaseMaintenanceDisposition.REVIEW,
            reason_code=ReleaseMaintenanceReasonCode.PROJECTION_WITHOUT_JOURNAL,
            observed_count=snapshot.candidate_projections,
        )
    projection_lagging = snapshot.candidate_journals > 0 and (
        snapshot.latest_candidate_projection_at is None
        or (
            snapshot.latest_candidate_journal_at is not None
            and snapshot.latest_candidate_projection_at < snapshot.latest_candidate_journal_at
        )
    )
    return ReleaseMaintenanceAction(
        code=ReleaseMaintenanceActionCode.CANDIDATE_PROJECTION_REBUILD,
        disposition=(
            ReleaseMaintenanceDisposition.REQUIRED
            if projection_lagging
            else ReleaseMaintenanceDisposition.NOT_REQUIRED
        ),
        reason_code=(
            ReleaseMaintenanceReasonCode.PROJECTION_LAGGING
            if projection_lagging
            else ReleaseMaintenanceReasonCode.PROJECTION_CURRENT
        ),
        observed_count=snapshot.candidate_journals,
    )


def _checksum(value: object) -> str:
    serialized = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
