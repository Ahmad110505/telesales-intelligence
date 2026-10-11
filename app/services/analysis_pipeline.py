"""
End-to-end analysis pipeline orchestrating ingestion validation, objection detection,
evidence grounding checks, leakage detection, deterministic rubric scoring,
coaching generation, and atomic persistence.
"""

from datetime import datetime, timezone
import logging
import re
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session

from app.config import settings
from app.db.repository import DatabaseRepository
from app.schemas.transcript import TranscriptInput, TranscriptTurn
from app.schemas.analysis import (
    CallAnalysisResult,
    CallAssessment,
    ObjectionFinding,
    LeakageFinding,
    CoachingAction,
    ReviewStatus,
    AddressedStatus,
    EvidenceClass
)
from app.services.llm_client import BaseLLMClient, get_llm_client
from app.services.objection_detector import ObjectionDetector
from app.services.leakage_detector import LeakageDetector
from app.services.coaching_generator import CoachingGenerator
from app.retrieval.knowledge_base import SalesKnowledgeBase

logger = logging.getLogger(__name__)


def normalize_for_matching(text: str) -> str:
    """Normalizes text for evidence excerpt verification against transcript."""
    # Remove punctuation and normalize spaces
    cleaned = re.sub(r"[^\w\s\u0621-\u064A]", " ", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip().lower()
    return cleaned


class AnalysisPipeline:
    def __init__(
        self,
        llm_client: Optional[BaseLLMClient] = None,
        db_session: Optional[Session] = None,
        knowledge_base: Optional[SalesKnowledgeBase] = None
    ):
        self.llm = llm_client or get_llm_client()
        self.db = db_session
        self.kb = knowledge_base or SalesKnowledgeBase()

        self.objection_detector = ObjectionDetector(self.llm, self.kb)
        self.leakage_detector = LeakageDetector(self.llm, self.kb)
        self.coaching_generator = CoachingGenerator(self.llm, self.kb)

    def analyze_call(
        self,
        transcript_input: TranscriptInput,
        persist: bool = True
    ) -> CallAnalysisResult:
        """
        Executes the complete headless analysis pipeline for a single call transcript.
        """
        logger.info("Starting analysis for call_id: %s", transcript_input.call_id)

        # 1. Parse turns and validate transcript structure
        turns = transcript_input.parse_turns()
        turn_count = len(turns)
        full_transcript = transcript_input.transcript
        norm_full = normalize_for_matching(full_transcript)

        # 2. Objection Detection
        raw_objections = self.objection_detector.detect_objections(transcript_input, turns)
        
        # Validate objection evidence excerpts
        verified_objections: List[ObjectionFinding] = []
        for obj in raw_objections:
            norm_excerpt = normalize_for_matching(obj.customer_excerpt)
            # Check excerpt exists in raw text
            if norm_excerpt in norm_full or any(norm_excerpt in normalize_for_matching(t.text) for t in turns):
                verified_objections.append(obj)
            else:
                logger.warning(
                    "Objection %s excerpt '%s' could not be grounded in transcript text; rejecting finding.",
                    obj.finding_id,
                    obj.customer_excerpt
                )

        # 3. Leakage Detection
        raw_leakages = self.leakage_detector.detect_leakages(
            transcript_input,
            turns,
            verified_objections
        )

        # Validate leakage evidence excerpts
        verified_leakages: List[LeakageFinding] = []
        for leak in raw_leakages:
            norm_excerpt = normalize_for_matching(leak.transcript_excerpt)
            if norm_excerpt in norm_full or any(norm_excerpt in normalize_for_matching(t.text) for t in turns):
                verified_leakages.append(leak)
            else:
                # If excerpt cannot be verified, reclassify to insufficient_evidence
                logger.warning(
                    "Leakage %s excerpt '%s' not found verbatim; flagging as insufficient_evidence.",
                    leak.finding_id,
                    leak.transcript_excerpt
                )
                leak.evidence_class = EvidenceClass.INSUFFICIENT_EVIDENCE
                leak.recommended_human_review = True
                verified_leakages.append(leak)

        # 4. Deterministic Rubric Scoring (Separating LLM from business calculation)
        assessment = self._calculate_assessment(
            transcript_input=transcript_input,
            objections=verified_objections,
            leakages=verified_leakages
        )

        # 5. Coaching Generation (runs only on verified findings)
        coaching_actions = self.coaching_generator.generate_coaching(
            transcript_input=transcript_input,
            verified_objections=verified_objections,
            verified_leakages=verified_leakages
        )

        # Guarantee global uniqueness of IDs across the database
        cid = transcript_input.call_id
        for obj in verified_objections:
            if not obj.finding_id.startswith(f"{cid}_"):
                obj.finding_id = f"{cid}_{obj.finding_id}"

        for leak in verified_leakages:
            if not leak.finding_id.startswith(f"{cid}_"):
                leak.finding_id = f"{cid}_{leak.finding_id}"
            if leak.related_objection_id and not leak.related_objection_id.startswith(f"{cid}_"):
                leak.related_objection_id = f"{cid}_{leak.related_objection_id}"

        for coach in coaching_actions:
            if not coach.action_id.startswith(f"{cid}_"):
                coach.action_id = f"{cid}_{coach.action_id}"
            if not coach.related_finding_id.startswith(f"{cid}_"):
                coach.related_finding_id = f"{cid}_{coach.related_finding_id}"

        result = CallAnalysisResult(
            call_id=transcript_input.call_id,
            assessment=assessment,
            objections=verified_objections,
            leakage_findings=verified_leakages,
            coaching_actions=coaching_actions
        )

        # 6. Atomic Persistence
        if persist and self.db is not None:
            repo = DatabaseRepository(self.db)
            repo.persist_call_analysis_transaction(
                transcript_input=transcript_input,
                analysis_result=result,
                turn_count=turn_count
            )
            logger.info("Call %s persisted successfully in atomic transaction.", transcript_input.call_id)

        return result

    def _calculate_assessment(
        self,
        transcript_input: TranscriptInput,
        objections: List[ObjectionFinding],
        leakages: List[LeakageFinding]
    ) -> CallAssessment:
        """
        Calculates deterministic rubric score (0 - 100) and counts.
        """
        objection_count = len(objections)
        obj_addressed = sum(1 for o in objections if o.addressed_status == AddressedStatus.YES)
        obj_partially = sum(1 for o in objections if o.addressed_status == AddressedStatus.PARTIALLY)
        obj_unaddressed = sum(1 for o in objections if o.addressed_status == AddressedStatus.NO)

        leakage_count = len(leakages)
        crit_count = sum(1 for l in leakages if l.severity.value == "critical")
        high_count = sum(1 for l in leakages if l.severity.value == "high")
        med_count = sum(1 for l in leakages if l.severity.value == "medium")
        low_count = sum(1 for l in leakages if l.severity.value == "low")

        # Rubric base calculation
        base_score = 100.0

        # Penalties for unhandled objections
        base_score -= (obj_unaddressed * 25.0)
        base_score -= (obj_partially * 10.0)

        # Penalties for sales leakages
        base_score -= (crit_count * 30.0)
        base_score -= (high_count * 15.0)
        base_score -= (med_count * 8.0)
        base_score -= (low_count * 3.0)

        # Clamp between 0 and 100
        overall_score = max(0.0, min(100.0, round(base_score, 1)))

        # Construct objective summary assessment
        summary_parts = []
        if overall_score >= 85:
            summary_parts.append("أداء ممتاز للمكالمة مع التزام عالي بمعايير المبيعات.")
        elif overall_score >= 65:
            summary_parts.append("أداء جيد مع وجود بعض الملاحظات على معالجة الاعتراضات أو اكتشاف الاحتياج.")
        else:
            summary_parts.append("مكالمة بحاجة إلى مراجعة وتدريب عاجل لوجود تسرب مبيعات واعتراضات غير معالجة.")

        if objection_count > 0:
            summary_parts.append(
                f"تم رصد {objection_count} اعتراض، تم حل {obj_addressed} بنجاح، و{obj_partially} جزئياً، و{obj_unaddressed} دون معالجة."
            )
        else:
            summary_parts.append("لم يتم رصد أي اعتراضات صريحة من العميل خلال المكالمة.")

        if leakage_count > 0:
            summary_parts.append(f"تم رصد {leakage_count} فرصة تسرب مبيعات (منها {crit_count} حرجة).")

        summary_text = " ".join(summary_parts)

        # Flag for human review if critical leakage or unaddressed objection exists
        review_status = ReviewStatus.PENDING
        if crit_count > 0 or obj_unaddressed > 0:
            review_status = ReviewStatus.PENDING

        return CallAssessment(
            call_id=transcript_input.call_id,
            overall_score=overall_score,
            objection_count=objection_count,
            objections_addressed_count=obj_addressed,
            objections_partially_count=obj_partially,
            objections_unaddressed_count=obj_unaddressed,
            leakage_count=leakage_count,
            critical_leakage_count=crit_count,
            high_leakage_count=high_count,
            medium_leakage_count=med_count,
            low_leakage_count=low_count,
            summary_assessment=summary_text,
            review_status=review_status,
            model_id=settings.COHERE_MODEL if not settings.is_mock_llm else "mock-jordanian-cohere",
            prompt_version="v2.0",
            analyzed_at=datetime.now(timezone.utc)
        )
