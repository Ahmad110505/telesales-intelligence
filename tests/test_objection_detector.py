"""
Unit tests for objection detection service with Jordanian dialect nuances.
"""

from app.schemas.transcript import TranscriptInput
from app.services.objection_detector import ObjectionDetector
from app.schemas.analysis import ObjectionCategory, AddressedStatus


def test_detect_price_and_authority_objections(mock_llm_client, sales_knowledge_base, sample_jordanian_transcript):
    detector = ObjectionDetector(mock_llm_client, sales_knowledge_base)
    inp = TranscriptInput(
        call_id="CALL-TEST-001",
        transcript=sample_jordanian_transcript,
        call_objective="fiber_subscription_upgrade"
    )
    turns = inp.parse_turns()

    objections = detector.detect_objections(inp, turns)

    assert len(objections) >= 1
    # Check that price objection was identified
    categories = [o.category for o in objections]
    assert ObjectionCategory.PRICE in categories

    price_obj = next(o for o in objections if o.category == ObjectionCategory.PRICE)
    assert "غالي" in price_obj.customer_excerpt
    assert price_obj.company_guidance_ref == "RULE-PRICE-01"


def test_zero_objection_call(mock_llm_client, sales_knowledge_base):
    detector = ObjectionDetector(mock_llm_client, sales_knowledge_base)
    clean_transcript = """[00:01] الموظف: ألو مرحبا أستاذ طارق.
[00:04] العميل: يا هلا أهلاً وسهلاً.
[00:08] الموظف: بخصوص طلب الفايبر، الفني رح يجي بكرة الساعة 10.
[00:15] العميل: تمام ممتاز، بانتظار الفني وشكراً إلك."""

    inp = TranscriptInput(call_id="CALL-ZERO-001", transcript=clean_transcript)
    turns = inp.parse_turns()

    objections = detector.detect_objections(inp, turns)
    assert len(objections) == 0
