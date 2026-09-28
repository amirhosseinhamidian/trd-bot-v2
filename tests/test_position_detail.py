from tests.test_candidate_journal import build_closed_lifecycle
from trd_bot.research.candidate_journal import CandidateJournalBuilder
from trd_bot.research.position_lineage import PositionDetailBuilder, PositionLineageStatus


def test_position_detail_reconciles_accounting_events_and_complete_lineage() -> None:
    journal = CandidateJournalBuilder.from_lifecycle(build_closed_lifecycle())
    portfolio = journal.lifecycle.portfolio
    position = next(item for item in portfolio.positions if item.position_id == journal.position_id)
    before = portfolio.model_dump_json()

    report = PositionDetailBuilder.build(
        portfolio=portfolio,
        position=position,
        journals=(journal, journal),
    )

    assert report.position_detail_version == "position-detail-v1"
    assert report.lineage_status is PositionLineageStatus.COMPLETE
    assert report.journal_id == journal.journal_id
    assert report.candidate is not None
    assert report.candidate.candidate_id == journal.selected_candidate_id
    assert report.decision_evidence is not None
    assert [node.kind.value for node in report.nodes] == [
        "dataset",
        "experiment",
        "signal",
        "candidate",
        "risk",
        "position",
        "exit",
    ]
    assert report.nodes[4].outcome == "approved"
    assert report.nodes[-1].outcome == "target"
    assert [event.event_type.value for event in report.events] == [
        "position_opened",
        "position_closed",
    ]
    assert report.events[-1].realized_pnl == position.realized_pnl
    assert portfolio.model_dump_json() == before


def test_position_detail_marks_missing_and_conflicting_journal_evidence() -> None:
    journal = CandidateJournalBuilder.from_lifecycle(build_closed_lifecycle())
    portfolio = journal.lifecycle.portfolio
    position = next(item for item in portfolio.positions if item.position_id == journal.position_id)
    builder = PositionDetailBuilder()

    unavailable = builder.build(portfolio=portfolio, position=position, journals=())
    assert unavailable.lineage_status is PositionLineageStatus.UNAVAILABLE
    assert unavailable.journal_id is None
    assert unavailable.candidate is None
    assert unavailable.nodes[0].status.value == "available"
    assert unavailable.nodes[1].reason == "lineage_evidence_unavailable"
    assert unavailable.nodes[-1].status.value == "unavailable"

    second = journal.model_copy(update={"journal_id": "journal-0000000000000000"})
    conflict = builder.build(
        portfolio=portfolio,
        position=position,
        journals=(journal, second),
    )
    assert conflict.lineage_status is PositionLineageStatus.CONFLICT
    assert conflict.nodes[1].reason == "conflicting_lineage_evidence"


def test_position_detail_ignores_foreign_portfolio_journals() -> None:
    journal = CandidateJournalBuilder.from_lifecycle(build_closed_lifecycle())
    portfolio = journal.lifecycle.portfolio
    position = next(item for item in portfolio.positions if item.position_id == journal.position_id)
    foreign = journal.model_copy(update={"portfolio_id": "portfolio-0000000000000000"})

    report = PositionDetailBuilder.build(
        portfolio=portfolio,
        position=position,
        journals=(foreign,),
    )

    assert report.lineage_status is PositionLineageStatus.UNAVAILABLE
