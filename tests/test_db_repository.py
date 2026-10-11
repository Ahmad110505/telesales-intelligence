"""
Unit tests for database repository operations and transactional persistence.
"""

from app.db.models import CallModel, CategoryLookupModel
from app.db.repository import DatabaseRepository
from app.schemas.transcript import TranscriptInput
from app.schemas.analysis import (
    CallAnalysisResult,
    CallAssessment,
    ObjectionFinding,
    ObjectionCategory,
    AddressedStatus,
    ReviewStatus
)


def test_persist_call_analysis_transaction(db_session, sample_jordanian_transcript):
    repo = DatabaseRepository(db_session)

    transcript_inp = TranscriptInput(
        call_id="CALL-REPO-001",
        agent_id="AGT-TEST",
        call_objective="fiber_upgrade",
        transcript=sample_jordanian_transcript
    )

    assessment = CallAssessment(
        call_id="CALL-REPO-001",
        overall_score=82.0,
        objection_count=1,
        objections_addressed_count=1,
        leakage_count=0,
        summary_assessment="مكالمة ممتازة",
        model_id="command-r-plus-08-2024"
    )

    objection = ObjectionFinding(
        finding_id="OBJ-REPO-001",
        call_id="CALL-REPO-001",
        category=ObjectionCategory.PRICE,
        customer_excerpt="كتير غالي علي هالأيام",
        addressed_status=AddressedStatus.YES,
        explanation="Customer questioned price."
    )

    result = CallAnalysisResult(
        call_id="CALL-REPO-001",
        assessment=assessment,
        objections=[objection],
        leakage_findings=[],
        coaching_actions=[]
    )

    repo.persist_call_analysis_transaction(transcript_inp, result, turn_count=8)

    # Verify retrieval
    stored_call = repo.get_call_by_id("CALL-REPO-001")
    assert stored_call is not None
    assert stored_call.turn_count == 8

    res = repo.get_call_analysis_result("CALL-REPO-001")
    assert res is not None
    assert res.assessment.overall_score == 82.0
    assert len(res.objections) == 1
    assert res.objections[0].category == ObjectionCategory.PRICE


def test_category_lookups_seeded(db_session):
    lookups = db_session.query(CategoryLookupModel).all()
    assert len(lookups) >= 20
    # Check bilingual presence
    price_lookup = next(l for l in lookups if l.code == "price")
    assert price_lookup.label_en == "Price / Cost"
    assert "السعر" in price_lookup.label_ar
