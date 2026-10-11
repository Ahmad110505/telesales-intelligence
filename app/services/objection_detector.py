"""
Objection detection service tailored for Jordanian Arabic telesales calls.
Identifies customer objections, extracts verbatim evidence, and evaluates agent response.
"""

import json
import logging
from typing import List, Optional

from app.schemas.transcript import TranscriptInput, TranscriptTurn
from app.schemas.analysis import (
    ObjectionFinding,
    ObjectionDetectionPayload,
    ObjectionCategory,
    AddressedStatus,
    SpeakerAttribution
)
from app.services.llm_client import BaseLLMClient
from app.retrieval.knowledge_base import SalesKnowledgeBase

logger = logging.getLogger(__name__)


OBJECTION_DETECTION_SYSTEM_PROMPT = """
You are a senior telesales quality assurance auditor specializing in Jordanian Arabic telesales calls.
Your objective is to identify and analyze customer objections with rigorous transcript grounding.

CRITICAL GUIDELINES FOR JORDANIAN ARABIC (اللهجة الأردنية):
1. Understand colloquial expressions indicating resistance:
   - Price: "غالي كتير", "السعر نار", "الراتب طار", "بقدرش على هيك مبلغ", "الـ package غالية", "مش معقول السعر".
   - Timing: "مش فاضي هسة", "رن علي بعدين", "عندي اجتماع", "ملخوم بشغلي", "مش وقتها بالمرة".
   - Need: "فش داعي", "ما بحتاجه", "عندي نت ومبسوط عليه", "مش لازمني".
   - Trust: "النت عندكم بقطع", "سمعت الخدمة مش زيادة", "بتوعدوا وما بتوفوا".
   - Competitor: "أنا مع أورانج/زين/أمنية ومبسوط", "الشركة الثانية معطيتني أرخص", "عندهم عروض أحسن".
   - Authority: "بدي أسأل مرتي/الوالد", "مش بقراري لحالي", "بدي استشير الشريك".
2. Handle Arabic-English code-switching seamlessly (e.g., "الـ package", "SLA", "budget", "plan", "offer").
3. DO NOT confuse neutral product questions with objections:
   - "كم سعر باقة الـ 300 ميجا؟" is a neutral product question, NOT an objection.
   - "25 دينار؟ غالي كتير مقارنة براتبي" IS a price objection.
4. Extract EXACT verbatim customer excerpts matching the transcript text. Do NOT summarize or normalize.
5. Evaluate the sales agent's response:
   - "yes": Effectively resolved the concern using value proposition, empathy, or suitable counter-offer.
   - "partially": Attempted an answer but left uncertainty or failed to confirm customer agreement.
   - "no": Completely ignored, dismissed, argued, or failed to address the objection.
   - "not_applicable": Objection arose at call disconnect or was not answerable in context.
6. Attribution:
   - "labeled" if the speaker is explicitly tagged as Customer in the transcript.
   - "inferred" if determined from conversational context.

CATEGORIES TAXONOMY:
- price
- timing
- trust
- product_fit
- need
- competitor
- authority
- information_request
- other

Return ONLY valid JSON matching this structure:
{
  "objections": [
    {
      "finding_id": "OBJ-001",
      "category": "price",
      "customer_excerpt": "exact verbatim text from transcript",
      "turn_reference": "Turn 4 or timestamp if available",
      "agent_response_excerpt": "exact agent response text or null",
      "addressed_status": "yes" | "partially" | "no" | "not_applicable",
      "speaker_attribution": "labeled" | "inferred",
      "explanation": "evidence-grounded explanation in Arabic or English",
      "confidence": 0.95,
      "company_guidance_ref": "RULE-PRICE-01 or null"
    }
  ]
}
If no objections occurred in the call, return {"objections": []}.
"""


class ObjectionDetector:
    def __init__(self, llm_client: BaseLLMClient, knowledge_base: Optional[SalesKnowledgeBase] = None):
        self.llm = llm_client
        self.kb = knowledge_base or SalesKnowledgeBase()

    def detect_objections(
        self,
        transcript_input: TranscriptInput,
        turns: List[TranscriptTurn]
    ) -> List[ObjectionFinding]:
        """
        Analyzes the transcript to extract verified customer objections.
        """
        # Build turn-formatted transcript representation for LLM context
        formatted_transcript_lines = []
        for turn in turns:
            spk = turn.speaker.upper()
            ts = f"[{turn.timestamp}] " if turn.timestamp else ""
            formatted_transcript_lines.append(f"Turn {turn.turn_index}: {ts}{spk}: {turn.text}")
        
        call_context = "\n".join(formatted_transcript_lines)
        objective_ctx = f"Call Objective: {transcript_input.call_objective}\n" if transcript_input.call_objective else ""

        user_prompt = f"""
{objective_ctx}
TRANSCRIPT TO ANALYZE:
---
{call_context}
---
Analyze the transcript above and extract all customer objections according to the guidelines.
"""

        messages = [
            {"role": "system", "content": OBJECTION_DETECTION_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ]

        raw_response = self.llm.generate_chat_completion(messages=messages, json_mode=True)
        
        try:
            data = json.loads(raw_response)
            payload = ObjectionDetectionPayload.model_validate(data)
            
            # Enrich with call_id and link to company playbook rules if applicable
            for obj in payload.objections:
                obj.call_id = transcript_input.call_id
                if not obj.company_guidance_ref:
                    rule = self.kb.get_guidance_for_objection(obj.category.value)
                    if rule:
                        obj.company_guidance_ref = rule.rule_id

            return payload.objections
        except Exception as exc:
            logger.error("Failed to parse objection detection response: %s\nRaw output: %s", str(exc), raw_response)
            # Fail gracefully returning empty list rather than crashing entire pipeline
            return []
