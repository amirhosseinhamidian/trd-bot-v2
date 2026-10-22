from sqlalchemy.orm import Session

from trd_bot.db.market_context_repositories import SqlAlchemyMarketContextStore
from trd_bot.db.models import MarketDataWindowVersionRow
from trd_bot.market_context import (
    MarketContextFeatureSnapshot,
    calculate_market_context_feature_snapshot_v1,
)
from trd_bot.market_data.events import MarketDataWindowSnapshot


class SqlAlchemyMarketContextFeatureCalculator:
    """Calculate and stage v1 features from one persisted input manifest."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._store = SqlAlchemyMarketContextStore(session)

    def calculate_and_stage(
        self,
        *,
        manifest_id: str,
    ) -> tuple[MarketContextFeatureSnapshot, bool]:
        manifest = self._store.get_input_manifest(manifest_id)
        if manifest is None:
            raise ValueError("market-context input manifest does not exist")

        windows: list[MarketDataWindowSnapshot] = []
        for reference in manifest.windows:
            row = self._session.get(
                MarketDataWindowVersionRow,
                (reference.window_id, reference.version),
            )
            if row is None:
                raise ValueError("market-context input window version does not exist")
            windows.append(MarketDataWindowSnapshot.model_validate_json(row.payload_json))

        snapshot = calculate_market_context_feature_snapshot_v1(
            manifest=manifest,
            windows=tuple(windows),
        )
        return self._store.stage_feature_snapshot(snapshot)
