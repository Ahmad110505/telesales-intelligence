"""
Unit tests for sales leakage detection service.
"""

from app.schemas.transcript import TranscriptInput
from app.services.leakage_detector import LeakageDetector
from app.schemas.analysis import (
    ObjectionFinding,
    ObjectionCategory,
    AddressedStatus,
    LeakageCategory,
    LeakageSeverity,
    EvidenceClass
)


def test_detect_missed_discovery_leakage(mock_llm_client, sales_knowledge_base, sample_jordanian_transcript):
    detector = LeakageDetector(mock_llm_client, sales_knowledge_base)
    inp = TranscriptInput(
        call_id="CALL-TEST-002",
        transcript=sample_jordanian_transcript,
        call_objective="fiber_subscription_upgrade"
    )
    turns = inp.parse_turns()

    sample_objections = [
        ObjectionFinding(
            finding_id="OBJ-001",
            call_id="CALL-TEST-002",
            category=ObjectionCategory.PRICE,
            customer_excerpt="كتير غالي علي هالأيام",
            addressed_status=AddressedStatus.PARTIALLY,
            explanation="Customer voiced concern."
        )
    ]

    leakages = detector.detect_leakages(inp, turns, sample_objections)

    assert len(leakages) >= 1
    categories = [l.category for l in leakages]
    assert LeakageCategory.MISSED_DISCOVERY in categories

    disc_leak = next(l for l in leakages if l.category == LeakageCategory.MISSED_DISCOVERY)
    assert disc_leak.evidence_class == EvidenceClass.OBSERVED_FAILURE
    assert disc_leak.severity == LeakageSeverity.HIGH
    assert disc_leak.rubric_ref == "RUBRIC-DISC-01"


def test_unaddressed_timing_objection_leakage(mock_llm_client, sales_knowledge_base):
    detector = LeakageDetector(mock_llm_client, sales_knowledge_base)
    timing_transcript = """[00:01] الموظف: ألو مرحبا معك سارة.
[00:05] العميل: مش فاضي هسة وعندي شغل وملخوم بالدوام رن علي بعدين.
[00:10] الموظف: اسمعني بس دقيقة مش رح أطول عليك."""

    inp = TranscriptInput(call_id="CALL-TIMING", transcript=timing_transcript)
    turns = inp.parse_turns()

    objections = [
        ObjectionFinding(
            finding_id="OBJ-002",
            call_id="CALL-TIMING",
            category=ObjectionCategory.TIMING,
            customer_excerpt="مش فاضي هسة وعندي شغل",
            addressed_status=AddressedStatus.NO,
            explanation="Customer rushed."
        )
    ]

    leakages = detector.detect_leakages(inp, turns, objections)

    assert any(l.category == LeakageCategory.UNADDRESSED_OBJECTION for l in leakages)
    crit_leak = next(l for l in leakages if l.category == LeakageCategory.UNADDRESSED_OBJECTION)
    assert crit_leak.severity == LeakageSeverity.CRITICAL
    assert crit_leak.related_objection_id == "OBJ-002"
