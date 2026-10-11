"""
Unit tests for Pydantic transcript and analysis schemas.
"""

from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from app.schemas.transcript import TranscriptInput, TranscriptTurn
from app.schemas.analysis import (
    ObjectionFinding,
    ObjectionCategory,
    AddressedStatus,
    SpeakerAttribution,
    LeakageFinding,
    LeakageCategory,
    LeakageSeverity,
    EvidenceClass,
    CoachingAction,
    CoachingPriority,
    CallAssessment,
    ReviewStatus
)


def test_transcript_input_valid():
    inp = TranscriptInput(
        call_id="CALL-001",
        transcript="[00:01] الموظف: ألو مرحبا\n[00:05] العميل: يا هلا أهلاً وسهلاً",
        agent_id="AGT-01",
        call_objective="fiber_upgrade"
    )
    assert inp.call_id == "CALL-001"
    assert inp.agent_id == "AGT-01"
    assert inp.call_date is not None
    assert len(inp.transcript) > 10


def test_transcript_input_validation_errors():
    with pytest.raises(ValidationError):
        TranscriptInput(call_id="", transcript="Valid text that is long enough")

    with pytest.raises(ValidationError):
        TranscriptInput(call_id="CALL-002", transcript="short")


def test_transcript_turn_parser():
    raw = """[00:05] الموظف: مرحبا كيف صحتك؟
[00:12] العميل: يا هلا، كتير غالي علي هالسعر
(00:20) Agent: رح نعملك ديسكاونت 10%
Customer: تمام بجرب"""

    inp = TranscriptInput(call_id="CALL-003", transcript=raw)
    turns = inp.parse_turns()

    assert len(turns) == 4
    assert turns[0].turn_index == 1
    assert turns[0].speaker == "agent"
    assert turns[0].timestamp == "00:05"

    assert turns[1].turn_index == 2
    assert turns[1].speaker == "customer"
    assert turns[1].timestamp == "00:12"
    assert "كتير غالي" in turns[1].text

    assert turns[2].speaker == "agent"
    assert turns[3].speaker == "customer"


def test_objection_finding_schema():
    obj = ObjectionFinding(
        finding_id="OBJ-001",
        call_id="CALL-001",
        category=ObjectionCategory.PRICE,
        customer_excerpt="كتير غالي علي هالأيام",
        turn_reference="Turn 3",
        addressed_status=AddressedStatus.YES,
        explanation="Customer expressed price sensitivity."
    )
    assert obj.category == ObjectionCategory.PRICE
    assert obj.review_status == ReviewStatus.PENDING
    assert obj.confidence == 1.0


def test_leakage_finding_schema():
    leak = LeakageFinding(
        finding_id="LEAK-001",
        call_id="CALL-001",
        category=LeakageCategory.MISSED_DISCOVERY,
        severity=LeakageSeverity.HIGH,
        evidence_class=EvidenceClass.OBSERVED_FAILURE,
        transcript_excerpt="باقة الـ 300 ميجا بـ 25 دينار",
        expected_behavior="Ask open needs discovery questions",
        missing_behavior="Pitched price directly without qualifying usage"
    )
    assert leak.severity == LeakageSeverity.HIGH
    assert leak.evidence_class == EvidenceClass.OBSERVED_FAILURE


def test_call_assessment_schema():
    assess = CallAssessment(
        call_id="CALL-001",
        overall_score=85.5,
        objection_count=1,
        objections_addressed_count=1,
        leakage_count=0,
        summary_assessment="أداء ممتاز للمكالمة",
        model_id="command-r-plus-08-2024"
    )
    assert assess.overall_score == 85.5
    assert assess.objection_count == 1
    assert assess.leakage_count == 0
