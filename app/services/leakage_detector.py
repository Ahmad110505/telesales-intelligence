"""
Sales leakage and missed opportunities detection service.
Identifies execution breakdowns against sales rubric and links unhandled objections.
"""

import json
import logging
from typing import List, Optional

from app.schemas.transcript import TranscriptInput, TranscriptTurn
from app.schemas.analysis import (
    LeakageFinding,
    LeakageDetectionPayload,
    LeakageCategory,
    LeakageSeverity,
    EvidenceClass,
    ObjectionFinding
)
from app.services.llm_client import BaseLLMClient
from app.retrieval.knowledge_base import SalesKnowledgeBase

logger = logging.getLogger(__name__)


LEAKAGE_DETECTION_SYSTEM_PROMPT = """
You are a senior telesales performance auditor evaluating sales leakage and missed opportunities.
"Sales leakage" is a tangible failure to follow professional sales standards or a missed commercial opportunity.

CRITICAL RULES AND SAFEGUARDS:
1. Ground every finding in actual transcript evidence. NEVER invent statements or sales policies.
2. Contextual check: Do NOT flag an omission if the call objective did not warrant it:
   - If call objective was "Qualification" or caller was disconnected immediately, absence of a final close attempt is NOT a leakage.
   - If customer stated wrong number or immediate refusal, brevity is NOT a leakage.
3. Categorize findings using the initial taxonomy:
   - missed_discovery: Pitching product/price before asking qualifying questions about usage, family size, pain points.
   - unaddressed_objection: Ignoring, dismissing, or poorly handling a raised objection.
   - missed_relevant_offer: Failing to introduce an applicable promotion, fiber tier, or bundled benefit.
   - unclear_value_explanation: Reciting specs/features without connecting to customer benefit.
   - missed_next_step: Ending call without setting a scheduled callback or clear follow-up action.
   - other: Other documented sales process breakdowns.
4. Distinguish evidence classes:
   - observed_failure: Verbatim transcript evidence proves agent made an explicit error.
   - plausible_missed_opportunity: Context strongly indicates an opportunity existed that agent overlooked.
   - insufficient_evidence: Ambiguous evidence; human manager review recommended.
5. Severity scale:
   - critical: Deal-killing failure (e.g. arguing with customer, completely ignoring major objection).
   - high: Major process failure impacting deal conversion.
   - medium: Noticeable friction or poor framing.
   - low: Minor polishing opportunity.
6. If a leakage directly corresponds to an unaddressed customer objection, link its finding_id via related_objection_id.

Return ONLY valid JSON matching this schema:
{
  "leakages": [
    {
      "finding_id": "LEAK-001",
      "category": "missed_discovery" | "unaddressed_objection" | "missed_relevant_offer" | "unclear_value_explanation" | "missed_next_step" | "other",
      "severity": "critical" | "high" | "medium" | "low",
      "evidence_class": "observed_failure" | "plausible_missed_opportunity" | "insufficient_evidence",
      "transcript_excerpt": "exact transcript quote demonstrating the issue",
      "turn_reference": "Turn 2 or timestamp",
      "expected_behavior": "what agent should have done per rubric",
      "missing_behavior": "what was missing or poorly executed",
      "confidence": 0.92,
      "rubric_ref": "RUBRIC-DISC-01 or null",
      "related_objection_id": "OBJ-001 or null",
      "recommended_human_review": true | false
    }
  ]
}
If no leakage occurred, return {"leakages": []}.
"""


class LeakageDetector:
    def __init__(self, llm_client: BaseLLMClient, knowledge_base: Optional[SalesKnowledgeBase] = None):
        self.llm = llm_client
        self.kb = knowledge_base or SalesKnowledgeBase()

    def detect_leakages(
        self,
        transcript_input: TranscriptInput,
        turns: List[TranscriptTurn],
        verified_objections: List[ObjectionFinding]
    ) -> List[LeakageFinding]:
        """
        Detects sales leakage findings, correlating with previously identified objections.
        """
        # Format turns
        turn_lines = [
            f"Turn {t.turn_index}: {'[' + t.timestamp + '] ' if t.timestamp else ''}{t.speaker.upper()}: {t.text}"
            for t in turns
        ]
        transcript_block = "\n".join(turn_lines)

        # Summarize previously detected objections
        objection_summary_lines = []
        for obj in verified_objections:
            objection_summary_lines.append(
                f"- ID: {obj.finding_id} | Category: {obj.category.value} | "
                f"Excerpt: '{obj.customer_excerpt}' | Addressed: {obj.addressed_status.value}"
            )
        objections_block = "\n".join(objection_summary_lines) if objection_summary_lines else "None detected."

        user_prompt = f"""
Call Objective: {transcript_input.call_objective or 'General Sales Call'}

IDENTIFIED CUSTOMER OBJECTIONS IN THIS CALL:
{objections_block}

TRANSCRIPT TO EVALUATE:
---
{transcript_block}
---
Analyze whether any sales leakage or missed opportunities occurred in this call.
"""

        messages = [
            {"role": "system", "content": LEAKAGE_DETECTION_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ]

        raw_response = self.llm.generate_chat_completion(messages=messages, json_mode=True)

        try:
            data = json.loads(raw_response)
            payload = LeakageDetectionPayload.model_validate(data)

            # Assign call_id and enrich with knowledge base rubrics
            for leak in payload.leakages:
                leak.call_id = transcript_input.call_id
                if not leak.rubric_ref:
                    rubric = self.kb.get_rubric_for_leakage(leak.category.value)
                    if rubric:
                        leak.rubric_ref = rubric.rule_id

            return payload.leakages
        except Exception as exc:
            logger.error("Failed to parse leakage detection response: %s\nRaw output: %s", str(exc), raw_response)
            return []
