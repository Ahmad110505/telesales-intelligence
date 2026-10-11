"""
Integration tests for the end-to-end analysis pipeline.
"""

from app.schemas.transcript import TranscriptInput
from app.services.analysis_pipeline import AnalysisPipeline


def test_pipeline_end_to_end(db_session, mock_llm_client, sales_knowledge_base, sample_jordanian_transcript):
    pipeline = AnalysisPipeline(
        llm_client=mock_llm_client,
        db_session=db_session,
        knowledge_base=sales_knowledge_base
    )

    inp = TranscriptInput(
        call_id="CALL-PIPE-001",
        agent_id="AGT-OMAR-04",
        call_objective="fiber_subscription_upgrade",
        transcript=sample_jordanian_transcript
    )

    result = pipeline.analyze_call(inp, persist=True)

    # 1. Check assessment
    assert result.call_id == "CALL-PIPE-001"
    assert result.assessment.overall_score > 0
    assert result.assessment.objection_count >= 1

    # 2. Check evidence grounding
    for obj in result.objections:
        assert obj.customer_excerpt in sample_jordanian_transcript

    # 3. Check coaching generation
    assert len(result.coaching_actions) >= 1
    for coach in result.coaching_actions:
        assert coach.call_id == "CALL-PIPE-001"


def test_pipeline_idempotency(db_session, mock_llm_client, sales_knowledge_base, sample_jordanian_transcript):
    pipeline = AnalysisPipeline(
        llm_client=mock_llm_client,
        db_session=db_session,
        knowledge_base=sales_knowledge_base
    )

    inp = TranscriptInput(
        call_id="CALL-IDEMPOTENT-001",
        transcript=sample_jordanian_transcript
    )

    # Run 1
    res1 = pipeline.analyze_call(inp, persist=True)
    # Run 2 with same call_id
    res2 = pipeline.analyze_call(inp, persist=True)

    assert res1.call_id == res2.call_id
    assert res1.assessment.overall_score == res2.assessment.overall_score
