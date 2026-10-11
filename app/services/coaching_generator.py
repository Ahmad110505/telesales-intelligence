"""
Actionable coaching generation service.
Generates targeted coaching actions strictly tied to verified findings (objections and leakages).
Guarantees that unverified or rejected findings never produce coaching.
"""

import json
import logging
from typing import List, Optional, Union

from app.config import settings
from app.schemas.transcript import TranscriptInput
from app.schemas.analysis import (
    CoachingAction,
    CoachingGenerationPayload,
    CoachingPriority,
    ObjectionFinding,
    LeakageFinding
)
from app.services.llm_client import BaseLLMClient
from app.retrieval.knowledge_base import SalesKnowledgeBase

logger = logging.getLogger(__name__)


COACHING_GENERATION_SYSTEM_PROMPT = """
You are a senior telesales executive coach. Your job is to produce concrete, high-impact coaching recommendations
for sales agents based EXCLUSIVELY on verified audit findings.

CRITICAL RULES:
1. Coaching actions must be strictly tied to verified findings via related_finding_id.
2. Provide practical, immediate behavioral advice the agent or manager can read and execute.
3. Include a concrete conversational example phrase in the requested coaching language:
   - For Jordanian Arabic ('ar'): use authentic, natural conversational phrasing (e.g., "أكيد ولا يهمك، مقدر وقتك تماماً...").
   - For English ('en'): use professional, direct telesales phrasing.
4. Priority scale:
   - high: Critical behavior needing immediate correction.
   - medium: Core sales technique enhancement.
   - low: Minor phrasing refinement.
5. Do NOT over-promise results or fabricate non-existent company procedures.
6. If a finding does not warrant a distinct coaching tip, do not fabricate one.

JSON OUTPUT SCHEMA:
{
  "coaching": [
    {
      "action_id": "COACH-001",
      "related_finding_id": "LEAK-001 or OBJ-001",
      "skill_domain": "Needs Discovery" | "Objection Handling" | "Value Framing" | "Active Listening" | "Closing Discipline",
      "priority": "high" | "medium" | "low",
      "evidence_excerpt": "exact excerpt from transcript",
      "recommended_behavior": "specific actionable guidance",
      "example_phrase": "suggested script line for the agent to say next time",
      "coaching_guideline_ref": "rule code or null"
    }
  ]
}
"""


class CoachingGenerator:
    def __init__(self, llm_client: BaseLLMClient, knowledge_base: Optional[SalesKnowledgeBase] = None):
        self.llm = llm_client
        self.kb = knowledge_base or SalesKnowledgeBase()

    def generate_coaching(
        self,
        transcript_input: TranscriptInput,
        verified_objections: List[ObjectionFinding],
        verified_leakages: List[LeakageFinding]
    ) -> List[CoachingAction]:
        """
        Generates coaching recommendations only for verified findings.
        """
        # Collect findings that need coaching (unaddressed/partially addressed objections + all leakages)
        target_findings: List[Union[ObjectionFinding, LeakageFinding]] = []

        for obj in verified_objections:
            if obj.addressed_status.value in ("no", "partially"):
                target_findings.append(obj)

        for leak in verified_leakages:
            target_findings.append(leak)

        if not target_findings:
            return []

        # Build context
        findings_summary = []
        for f in target_findings:
            if isinstance(f, ObjectionFinding):
                findings_summary.append(
                    f"- Type: Objection | ID: {f.finding_id} | Category: {f.category.value} | "
                    f"Excerpt: '{f.customer_excerpt}' | Addressed: {f.addressed_status.value}"
                )
            else:
                findings_summary.append(
                    f"- Type: Leakage | ID: {f.finding_id} | Category: {f.category.value} | "
                    f"Severity: {f.severity.value} | Excerpt: '{f.transcript_excerpt}' | "
                    f"Missing: '{f.missing_behavior}'"
                )

        findings_block = "\n".join(findings_summary)
        lang_instruction = (
            "Generate recommendations and example phrases in authentic Jordanian Arabic ('ar')."
            if settings.COACHING_LANGUAGE == "ar"
            else "Generate recommendations and example phrases in English ('en')."
        )

        user_prompt = f"""
Language Requirement: {lang_instruction}

VERIFIED AUDIT FINDINGS:
{findings_block}

Generate targeted coaching actions for these verified findings.
"""

        messages = [
            {"role": "system", "content": COACHING_GENERATION_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ]

        raw_response = self.llm.generate_chat_completion(messages=messages, json_mode=True)

        try:
            data = json.loads(raw_response)
            payload = CoachingGenerationPayload.model_validate(data)

            # Ensure valid links to verified finding IDs
            verified_ids = {f.finding_id for f in target_findings}
            valid_actions: List[CoachingAction] = []

            for coach in payload.coaching:
                coach.call_id = transcript_input.call_id
                coach.language = settings.COACHING_LANGUAGE
                
                # If related finding is verified, keep it
                if coach.related_finding_id in verified_ids:
                    valid_actions.append(coach)
                elif len(target_findings) == 1:
                    # Fixup single finding link if model slightly hallucinated id prefix
                    coach.related_finding_id = target_findings[0].finding_id
                    valid_actions.append(coach)
                else:
                    logger.warning(
                        "Dropping ungrounded coaching action %s linked to unknown finding %s",
                        coach.action_id,
                        coach.related_finding_id
                    )

            return valid_actions
        except Exception as exc:
            logger.error("Failed to parse coaching generation response: %s\nRaw output: %s", str(exc), raw_response)
            return []
