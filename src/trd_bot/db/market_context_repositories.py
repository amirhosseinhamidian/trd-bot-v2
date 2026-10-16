from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from trd_bot.db.models import (
    MarketContextFeatureSnapshotRow,
    MarketContextInputManifestRow,
    MarketContextInputWindowRow,
    MarketDataWindowVersionRow,
    MarketRegimeAssessmentRow,
)
from trd_bot.domain.market_data import TradingPair
from trd_bot.market_context import (
    MarketContextAssessmentStatus,
    MarketContextFeatureSnapshot,
    MarketContextInputManifest,
    MarketContextWindowReference,
    MarketRegimeAssessment,
)
from trd_bot.market_data.events import MarketDataWindowSnapshot


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("market-context query time must include timezone information")
    return value.astimezone(UTC)


class SqlAlchemyMarketContextStore:
    """Stage and query immutable market-context records without owning commits."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def stage_input_manifest(
        self,
        manifest: MarketContextInputManifest,
    ) -> tuple[MarketContextInputManifest, bool]:
        existing = self.get_input_manifest(manifest.manifest_id)
        if existing is not None:
            if existing != manifest:
                raise ValueError("market-context manifest ID exists with different content")
            return existing, False

        by_checksum = self.get_input_manifest_by_checksum(manifest.input_checksum)
        if by_checksum is not None:
            if by_checksum != manifest:
                raise ValueError("market-context input checksum belongs to another manifest")
            return by_checksum, False

        self._validate_manifest_window_lineage(manifest)
        self._session.add(
            MarketContextInputManifestRow(
                manifest_id=manifest.manifest_id,
                schema_version=manifest.schema_version,
                policy_version=manifest.policy_version,
                source=manifest.source,
                base_asset=manifest.pair.base_asset,
                quote_asset=manifest.pair.quote_asset,
                market_type=manifest.pair.market_type.value,
                as_of=manifest.as_of,
                input_checksum=manifest.input_checksum,
                window_count=len(manifest.windows),
                payload_json=manifest.model_dump_json(),
                created_at=manifest.created_at,
            )
        )
        for ordinal, window in enumerate(manifest.windows, start=1):
            self._session.add(
                MarketContextInputWindowRow(
                    manifest_id=manifest.manifest_id,
                    ordinal=ordinal,
                    window_id=window.window_id,
                    window_version=window.version,
                    timeframe=window.timeframe.value,
                    window_start=window.window_start,
                    window_end=window.window_end,
                    reference_checksum=window.reference_checksum,
                )
            )
        self._session.flush()
        return manifest, True

    def get_input_manifest(self, manifest_id: str) -> MarketContextInputManifest | None:
        row = self._session.get(MarketContextInputManifestRow, manifest_id)
        return None if row is None else self._manifest_from_row(row)

    def get_input_manifest_by_checksum(
        self,
        input_checksum: str,
    ) -> MarketContextInputManifest | None:
        row = self._session.scalar(
            select(MarketContextInputManifestRow).where(
                MarketContextInputManifestRow.input_checksum == input_checksum
            )
        )
        return None if row is None else self._manifest_from_row(row)

    def stage_feature_snapshot(
        self,
        snapshot: MarketContextFeatureSnapshot,
    ) -> tuple[MarketContextFeatureSnapshot, bool]:
        existing = self.get_feature_snapshot(snapshot.snapshot_id)
        if existing is not None:
            if existing != snapshot:
                raise ValueError("market-context feature snapshot ID exists with different content")
            return existing, False

        by_manifest = self.get_feature_snapshot_for_manifest(
            manifest_id=snapshot.input_manifest_id,
            feature_set_version=snapshot.feature_set_version,
        )
        if by_manifest is not None:
            if by_manifest != snapshot:
                raise ValueError("manifest and feature-set already produced another snapshot")
            return by_manifest, False

        manifest = self.get_input_manifest(snapshot.input_manifest_id)
        if manifest is None:
            raise ValueError("feature snapshot input manifest does not exist")
        self._require_same_input(
            source=snapshot.source,
            pair=snapshot.pair,
            as_of=snapshot.as_of,
            input_checksum=snapshot.input_checksum,
            manifest=manifest,
        )

        self._session.add(
            MarketContextFeatureSnapshotRow(
                snapshot_id=snapshot.snapshot_id,
                schema_version=snapshot.schema_version,
                manifest_id=snapshot.input_manifest_id,
                source=snapshot.source,
                base_asset=snapshot.pair.base_asset,
                quote_asset=snapshot.pair.quote_asset,
                market_type=snapshot.pair.market_type.value,
                as_of=snapshot.as_of,
                input_checksum=snapshot.input_checksum,
                feature_set_version=snapshot.feature_set_version,
                feature_set_checksum=snapshot.feature_set_checksum,
                feature_count=len(snapshot.features),
                snapshot_checksum=snapshot.snapshot_checksum,
                payload_json=snapshot.model_dump_json(),
                calculated_at=snapshot.calculated_at,
            )
        )
        self._session.flush()
        return snapshot, True

    def get_feature_snapshot(self, snapshot_id: str) -> MarketContextFeatureSnapshot | None:
        row = self._session.get(MarketContextFeatureSnapshotRow, snapshot_id)
        return None if row is None else self._feature_snapshot_from_row(row)

    def get_feature_snapshot_for_manifest(
        self,
        *,
        manifest_id: str,
        feature_set_version: str,
    ) -> MarketContextFeatureSnapshot | None:
        row = self._session.scalar(
            select(MarketContextFeatureSnapshotRow).where(
                MarketContextFeatureSnapshotRow.manifest_id == manifest_id,
                MarketContextFeatureSnapshotRow.feature_set_version == feature_set_version,
            )
        )
        return None if row is None else self._feature_snapshot_from_row(row)

    def stage_assessment(
        self,
        assessment: MarketRegimeAssessment,
    ) -> tuple[MarketRegimeAssessment, bool]:
        existing = self.get_assessment(assessment.assessment_id)
        if existing is not None:
            if existing != assessment:
                raise ValueError("market-regime assessment ID exists with different content")
            return existing, False

        by_manifest = self.get_assessment_for_manifest(
            manifest_id=assessment.input_manifest_id,
            feature_set_version=assessment.feature_set_version,
            algorithm_version=assessment.algorithm_version,
        )
        if by_manifest is not None:
            if by_manifest != assessment:
                raise ValueError("manifest and algorithm already produced another assessment")
            return by_manifest, False

        manifest = self.get_input_manifest(assessment.input_manifest_id)
        if manifest is None:
            raise ValueError("assessment input manifest does not exist")
        self._require_same_input(
            source=assessment.source,
            pair=assessment.pair,
            as_of=assessment.as_of,
            input_checksum=assessment.input_checksum,
            manifest=manifest,
        )

        if assessment.status is MarketContextAssessmentStatus.READY:
            if assessment.feature_snapshot_id is None:
                raise ValueError("ready assessment is missing its feature snapshot")
            snapshot = self.get_feature_snapshot(assessment.feature_snapshot_id)
            if snapshot is None:
                raise ValueError("assessment feature snapshot does not exist")
            self._validate_assessment_feature_lineage(assessment, snapshot)

        self._session.add(
            MarketRegimeAssessmentRow(
                assessment_id=assessment.assessment_id,
                schema_version=assessment.schema_version,
                manifest_id=assessment.input_manifest_id,
                feature_snapshot_id=assessment.feature_snapshot_id,
                source=assessment.source,
                base_asset=assessment.pair.base_asset,
                quote_asset=assessment.pair.quote_asset,
                market_type=assessment.pair.market_type.value,
                as_of=assessment.as_of,
                input_checksum=assessment.input_checksum,
                feature_set_version=assessment.feature_set_version,
                feature_set_checksum=assessment.feature_set_checksum,
                feature_snapshot_checksum=assessment.feature_snapshot_checksum,
                algorithm_version=assessment.algorithm_version,
                status=assessment.status.value,
                trend=assessment.trend.value,
                volatility=assessment.volatility.value,
                confidence=assessment.confidence,
                evidence_count=len(assessment.evidence),
                issue_count=len(assessment.issue_codes),
                payload_json=assessment.model_dump_json(),
                assessed_at=assessment.assessed_at,
                expires_at=assessment.expires_at,
            )
        )
        self._session.flush()
        return assessment, True

    def get_assessment(self, assessment_id: str) -> MarketRegimeAssessment | None:
        row = self._session.get(MarketRegimeAssessmentRow, assessment_id)
        return None if row is None else self._assessment_from_row(row)

    def get_assessment_for_manifest(
        self,
        *,
        manifest_id: str,
        feature_set_version: str,
        algorithm_version: str,
    ) -> MarketRegimeAssessment | None:
        row = self._session.scalar(
            select(MarketRegimeAssessmentRow).where(
                MarketRegimeAssessmentRow.manifest_id == manifest_id,
                MarketRegimeAssessmentRow.feature_set_version == feature_set_version,
                MarketRegimeAssessmentRow.algorithm_version == algorithm_version,
            )
        )
        return None if row is None else self._assessment_from_row(row)

    def get_latest_assessment(
        self,
        *,
        source: str,
        pair: TradingPair,
        as_of_or_before: datetime | None = None,
    ) -> MarketRegimeAssessment | None:
        normalized_source = source.strip()
        if not normalized_source:
            raise ValueError("market-context source cannot be empty")
        statement = select(MarketRegimeAssessmentRow).where(
            MarketRegimeAssessmentRow.source == normalized_source,
            MarketRegimeAssessmentRow.base_asset == pair.base_asset,
            MarketRegimeAssessmentRow.quote_asset == pair.quote_asset,
            MarketRegimeAssessmentRow.market_type == pair.market_type.value,
        )
        if as_of_or_before is not None:
            statement = statement.where(MarketRegimeAssessmentRow.as_of <= _as_utc(as_of_or_before))
        row = self._session.scalar(
            statement.order_by(
                MarketRegimeAssessmentRow.as_of.desc(),
                MarketRegimeAssessmentRow.assessed_at.desc(),
                MarketRegimeAssessmentRow.assessment_id.desc(),
            ).limit(1)
        )
        return None if row is None else self._assessment_from_row(row)

    def _validate_manifest_window_lineage(self, manifest: MarketContextInputManifest) -> None:
        for reference in manifest.windows:
            row = self._session.get(
                MarketDataWindowVersionRow,
                (reference.window_id, reference.version),
            )
            if row is None:
                raise ValueError("market-context input window version does not exist")
            snapshot = MarketDataWindowSnapshot.model_validate_json(row.payload_json)
            persisted_reference = MarketContextWindowReference.from_snapshot(snapshot)
            if persisted_reference != reference:
                raise ValueError("market-context input window lineage does not match persistence")

    @staticmethod
    def _require_same_input(
        *,
        source: str,
        pair: TradingPair,
        as_of: datetime,
        input_checksum: str,
        manifest: MarketContextInputManifest,
    ) -> None:
        if (
            source != manifest.source
            or pair != manifest.pair
            or as_of != manifest.as_of
            or input_checksum != manifest.input_checksum
        ):
            raise ValueError("market-context record does not match its input manifest")

    @staticmethod
    def _validate_assessment_feature_lineage(
        assessment: MarketRegimeAssessment,
        snapshot: MarketContextFeatureSnapshot,
    ) -> None:
        if (
            snapshot.input_manifest_id != assessment.input_manifest_id
            or snapshot.input_checksum != assessment.input_checksum
            or snapshot.feature_set_version != assessment.feature_set_version
            or snapshot.feature_set_checksum != assessment.feature_set_checksum
            or snapshot.snapshot_checksum != assessment.feature_snapshot_checksum
            or snapshot.features != assessment.evidence
        ):
            raise ValueError("assessment does not match its persisted feature snapshot")

    @staticmethod
    def _manifest_from_row(row: MarketContextInputManifestRow) -> MarketContextInputManifest:
        return MarketContextInputManifest.model_validate_json(row.payload_json)

    @staticmethod
    def _feature_snapshot_from_row(
        row: MarketContextFeatureSnapshotRow,
    ) -> MarketContextFeatureSnapshot:
        return MarketContextFeatureSnapshot.model_validate_json(row.payload_json)

    @staticmethod
    def _assessment_from_row(row: MarketRegimeAssessmentRow) -> MarketRegimeAssessment:
        return MarketRegimeAssessment.model_validate_json(row.payload_json)
