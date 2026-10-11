"""
Unit tests for actionable coaching generation service.
"""

from app.schemas.transcript import TranscriptInput
from app.services.coaching_generator import CoachingGenerator
from app.schemas.analysis import (
    ObjectionFinding,
    ObjectionCategory,
    AddressedStatus,
    LeakageFinding,
    LeakageCategory,
    LeakageSeverity,
    EvidenceClass
)


def test_coaching_linked_to_verified_findings(mock_llm_client, sales_knowledge_base):
    generator = CoachingGenerator(mock_llm_client, sales_knowledge_base)
    inp = TranscriptInput(
        call_id="CALL-COACH-TEST",
        transcript="[00:01] الموظف: مرحبا\n[00:05] العميل: غالي كتير"
    )

    verified_objections = [
        ObjectionFinding(
            finding_id="OBJ-001",
            call_id="CALL-COACH-TEST",
            category=ObjectionCategory.PRICE,
            customer_excerpt="غالي كتير",
            addressed_status=AddressedStatus.PARTIALLY,
            explanation="Price resistance."
        )
    ]

    verified_leakages = [
        LeakageFinding(
            finding_id="LEAK-001",
            call_id="CALL-COACH-TEST",
            category=LeakageCategory.MISSED_DISCOVERY,
            severity=LeakageSeverity.HIGH,
            evidence_class=EvidenceClass.OBSERVED_FAILURE,
            transcript_excerpt="العرض عنا اليوم باقة 300 ميجا بـ 25 دينار",
            expected_behavior="Ask open needs questions",
            missing_behavior="Direct pitch without discovery"
        )
    ]

    coaching_actions = generator.generate_coaching(inp, verified_objections, verified_leakages)

    assert len(coaching_actions) >= 1
    # Ensure all actions link to verified finding IDs
    valid_ids = {"OBJ-001", "LEAK-001"}
    for action in coaching_actions:
        assert action.related_finding_id in valid_ids
        assert action.example_phrase is not None
        assert len(action.example_phrase) > 5


def test_no_coaching_for_perfect_call(mock_llm_client, sales_knowledge_base):
    generator = CoachingGenerator(mock_llm_client, sales_knowledge_base)
    inp = TranscriptInput(call_id="CALL-PERFECT", transcript="[00:01] Call with zero issues")

    # Fully resolved objection and zero leakages
    perfect_objections = [
        ObjectionFinding(
            finding_id="OBJ-001",
            call_id="CALL-PERFECT",
            category=ObjectionCategory.PRICE,
            customer_excerpt="غالي",
            addressed_status=AddressedStatus.YES,
            explanation="Handled effectively."
        )
    ]
    no_leakages = []

    actions = generator.generate_coaching(inp, perfect_objections, no_leakages)
    # Fully resolved objections do not trigger coaching
    assert len(actions) == 0
