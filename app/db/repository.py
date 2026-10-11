"""
Database repository providing transactional persistence, idempotent call registration,
lookup seeding, and query operations.
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple
from sqlalchemy import text, select, update
from sqlalchemy.orm import Session

from app.db.models import (
    Base,
    CallModel,
    CallAssessmentModel,
    ObjectionFindingModel,
    LeakageFindingModel,
    CoachingActionModel,
    CategoryLookupModel,
    SourceCallsStagingModel,
    BenchmarkRunModel
)
from app.schemas.transcript import TranscriptInput
from app.schemas.analysis import (
    CallAnalysisResult,
    CallAssessment,
    ObjectionFinding,
    LeakageFinding,
    CoachingAction,
    ReviewStatus
)


DEFAULT_CATEGORY_LOOKUPS = [
    # Objection categories
    {"category_type": "objection", "code": "price", "label_en": "Price / Cost", "label_ar": "السعر والتكلفة", "description": "High price, lack of budget, or expensive package"},
    {"category_type": "objection", "code": "timing", "label_en": "Timing / Postponement", "label_ar": "التوقيت / لاحقاً", "description": "Customer busy, asks to call back later, or wrong time"},
    {"category_type": "objection", "code": "trust", "label_en": "Trust / Reputation", "label_ar": "الثقة والسمعة", "description": "Concerns about reliability, previous bad experience, network coverage"},
    {"category_type": "objection", "code": "product_fit", "label_en": "Product Fit / Feature", "label_ar": "ملاءمة المنتج / المواصفات", "description": "Product does not meet specific customer technical needs"},
    {"category_type": "objection", "code": "need", "label_en": "Lack of Need", "label_ar": "عدم الحاجة", "description": "Customer states they do not need the service or are satisfied with current"},
    {"category_type": "objection", "code": "competitor", "label_en": "Competitor Preference", "label_ar": "تفضيل المنافس", "description": "Customer has better offer or prefers competitor (e.g., Orange, Zain, Umniah)"},
    {"category_type": "objection", "code": "authority", "label_en": "Decision Authority", "label_ar": "سلطة اتخاذ القرار", "description": "Customer needs to consult spouse, parents, or business partner"},
    {"category_type": "objection", "code": "information_request", "label_en": "Information / Doubts", "label_ar": "طلب معلومات إضافية", "description": "Requests more details or contract clauses before committing"},
    {"category_type": "objection", "code": "other", "label_en": "Other Objection", "label_ar": "اعتراض آخر", "description": "Miscellaneous objection"},

    # Addressed status
    {"category_type": "addressed_status", "code": "yes", "label_en": "Fully Addressed", "label_ar": "تمت معالجته بنجاح", "description": "Agent effectively addressed customer concern with clear rebuttal/value"},
    {"category_type": "addressed_status", "code": "partially", "label_en": "Partially Addressed", "label_ar": "معالجة جزئية", "description": "Agent attempted response but left lingering doubts or didn't confirm fit"},
    {"category_type": "addressed_status", "code": "no", "label_en": "Unaddressed / Ignored", "label_ar": "غير معالج / تم تجاهله", "description": "Agent ignored or failed to answer the objection"},
    {"category_type": "addressed_status", "code": "not_applicable", "label_en": "Not Applicable", "label_ar": "غير منطبق", "description": "Not applicable in context"},

    # Leakage categories
    {"category_type": "leakage", "code": "missed_discovery", "label_en": "Missed Discovery", "label_ar": "إغفال استكشاف الاحتياج", "description": "Failed to ask open qualifying questions to uncover needs"},
    {"category_type": "leakage", "code": "unaddressed_objection", "label_en": "Unaddressed Objection", "label_ar": "اعتراض لم تتم معالجته", "description": "Left a critical objection open without handling"},
    {"category_type": "leakage", "code": "missed_relevant_offer", "label_en": "Missed Relevant Offer / Upsell", "label_ar": "تفويت عرض مناسب / ترقية", "description": "Failed to offer relevant product or promotional bundle"},
    {"category_type": "leakage", "code": "unclear_value_explanation", "label_en": "Unclear Value Proposition", "label_ar": "عدم وضوح القيمة المضافة", "description": "Recited features without linking to customer benefits"},
    {"category_type": "leakage", "code": "missed_next_step", "label_en": "Missed Next Step / Close", "label_ar": "إغفال تحديد الخطوة التالية", "description": "Ended call without securing commitment, callback, or clear next action"},
    {"category_type": "leakage", "code": "other", "label_en": "Other Leakage", "label_ar": "تسرب مبيعات آخر", "description": "Other sales process failure"},

    # Severity
    {"category_type": "severity", "code": "critical", "label_en": "Critical", "label_ar": "حرج", "description": "Directly led to lost deal or immediate churn risk"},
    {"category_type": "severity", "code": "high", "label_en": "High", "label_ar": "مرتفع", "description": "Major flaw in sales process with high deal impact"},
    {"category_type": "severity", "code": "medium", "label_en": "Medium", "label_ar": "متوسط", "description": "Notable friction or suboptimal pitch"},
    {"category_type": "severity", "code": "low", "label_en": "Low", "label_ar": "منخفض", "description": "Minor refinement opportunity"},

    # Evidence class
    {"category_type": "evidence_class", "code": "observed_failure", "label_en": "Observed Failure", "label_ar": "فشل مثبت بالنص", "description": "Direct verbatim evidence of failure in transcript"},
    {"category_type": "evidence_class", "code": "plausible_missed_opportunity", "label_en": "Plausible Missed Opportunity", "label_ar": "فرصة ضائعة محتملة", "description": "Logical opportunity indicated by context but not fully explored"},
    {"category_type": "evidence_class", "code": "insufficient_evidence", "label_en": "Insufficient Evidence", "label_ar": "أدلة غير كافية", "description": "Uncertain evidence in transcript"},

    # Coaching Priority
    {"category_type": "priority", "code": "high", "label_en": "High Priority", "label_ar": "أولوية قصوى", "description": "Immediate coaching required before next shift"},
    {"category_type": "priority", "code": "medium", "label_en": "Medium Priority", "label_ar": "أولوية متوسطة", "description": "Targeted skill development area"},
    {"category_type": "priority", "code": "low", "label_en": "Low Priority", "label_ar": "أولوية اعتيادية", "description": "Continuous improvement tip"}
]


class DatabaseRepository:
    def __init__(self, db_session: Session):
        self.db = db_session

    @classmethod
    def initialize_schema_and_views(cls, engine, views_sql_path: Optional[str] = None):
        """
        Creates all database tables and executes views.sql to ensure Power BI reporting views exist.
        Also seeds category lookups.
        """
        Base.metadata.create_all(bind=engine)

        # Execute reporting views
        if views_sql_path is None:
            views_sql_path = str(Path(__file__).resolve().parent.parent / "reporting" / "views.sql")

        p = Path(views_sql_path)
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                sql_content = f.read()
            
            is_sqlite = engine.dialect.name == "sqlite"
            with engine.connect() as conn:
                if is_sqlite:
                    # SQLite cannot execute multi-statement string via normal execute,
                    # and does not support CREATE OR REPLACE VIEW
                    statements = [stmt.strip() for stmt in sql_content.split(";") if stmt.strip()]
                    raw_conn = conn.connection
                    cursor = raw_conn.cursor()
                    for stmt in statements:
                        cleaned = stmt.replace("CREATE OR REPLACE VIEW", "CREATE VIEW")
                        view_name_match = re.search(r"CREATE\s+VIEW\s+(\w+)", cleaned, re.IGNORECASE)
                        if view_name_match:
                            vname = view_name_match.group(1)
                            cursor.execute(f"DROP VIEW IF EXISTS {vname}")
                        cursor.execute(cleaned)
                    raw_conn.commit()
                else:
                    conn.execute(text(sql_content))
                    conn.commit()

        # Seed category lookups
        with Session(engine) as session:
            existing_count = session.query(CategoryLookupModel).count()
            if existing_count == 0:
                for item in DEFAULT_CATEGORY_LOOKUPS:
                    session.add(CategoryLookupModel(**item))
                session.commit()

    def persist_call_analysis_transaction(
        self,
        transcript_input: TranscriptInput,
        analysis_result: CallAnalysisResult,
        turn_count: int
    ) -> None:
        """
        Writes validated call analysis results to PostgreSQL in one atomic transaction.
        Idempotent: If call_id already exists, updates call details and replaces prior analysis.
        """
        call_id = transcript_input.call_id
        meta_str = json.dumps(transcript_input.metadata, ensure_ascii=False) if transcript_input.metadata else None

        # Check existing call
        existing_call = self.db.query(CallModel).filter(CallModel.call_id == call_id).first()
        if existing_call:
            # Update call attributes
            existing_call.agent_id = transcript_input.agent_id
            existing_call.call_date = transcript_input.call_date or datetime.now(timezone.utc)
            existing_call.call_objective = transcript_input.call_objective
            existing_call.source = transcript_input.source
            existing_call.source_ref = transcript_input.source_ref
            existing_call.transcript_raw = transcript_input.transcript
            existing_call.turn_count = turn_count
            existing_call.metadata_json = meta_str
            existing_call.status = "analyzed"

            # Remove previous related findings to ensure atomic clean replacement
            self.db.query(CallAssessmentModel).filter(CallAssessmentModel.call_id == call_id).delete()
            self.db.query(ObjectionFindingModel).filter(ObjectionFindingModel.call_id == call_id).delete()
            self.db.query(LeakageFindingModel).filter(LeakageFindingModel.call_id == call_id).delete()
            self.db.query(CoachingActionModel).filter(CoachingActionModel.call_id == call_id).delete()
            self.db.flush()
        else:
            new_call = CallModel(
                call_id=call_id,
                agent_id=transcript_input.agent_id,
                call_date=transcript_input.call_date or datetime.now(timezone.utc),
                call_objective=transcript_input.call_objective,
                source=transcript_input.source,
                source_ref=transcript_input.source_ref,
                transcript_raw=transcript_input.transcript,
                turn_count=turn_count,
                duration_seconds=transcript_input.metadata.get("duration_seconds") if transcript_input.metadata else None,
                metadata_json=meta_str,
                status="analyzed"
            )
            self.db.add(new_call)
            self.db.flush()

        # Insert Assessment
        assess = analysis_result.assessment
        assessment_row = CallAssessmentModel(
            call_id=call_id,
            overall_score=assess.overall_score,
            objection_count=assess.objection_count,
            objections_addressed_count=assess.objections_addressed_count,
            objections_partially_count=assess.objections_partially_count,
            objections_unaddressed_count=assess.objections_unaddressed_count,
            leakage_count=assess.leakage_count,
            critical_leakage_count=assess.critical_leakage_count,
            high_leakage_count=assess.high_leakage_count,
            medium_leakage_count=assess.medium_leakage_count,
            low_leakage_count=assess.low_leakage_count,
            summary_assessment=assess.summary_assessment,
            review_status=assess.review_status.value if hasattr(assess.review_status, "value") else str(assess.review_status),
            reviewer_notes=assess.reviewer_notes,
            model_id=assess.model_id,
            prompt_version=assess.prompt_version,
            analyzed_at=assess.analyzed_at
        )
        self.db.add(assessment_row)

        # Insert Objections
        for obj in analysis_result.objections:
            obj_row = ObjectionFindingModel(
                finding_id=obj.finding_id,
                call_id=call_id,
                category_code=obj.category.value if hasattr(obj.category, "value") else str(obj.category),
                customer_excerpt=obj.customer_excerpt,
                turn_reference=obj.turn_reference,
                agent_response_excerpt=obj.agent_response_excerpt,
                addressed_status=obj.addressed_status.value if hasattr(obj.addressed_status, "value") else str(obj.addressed_status),
                speaker_attribution=obj.speaker_attribution.value if hasattr(obj.speaker_attribution, "value") else str(obj.speaker_attribution),
                explanation=obj.explanation,
                confidence=obj.confidence,
                company_guidance_ref=obj.company_guidance_ref,
                review_status=obj.review_status.value if hasattr(obj.review_status, "value") else str(obj.review_status)
            )
            self.db.add(obj_row)

        # Insert Leakages
        for leak in analysis_result.leakage_findings:
            leak_row = LeakageFindingModel(
                finding_id=leak.finding_id,
                call_id=call_id,
                category_code=leak.category.value if hasattr(leak.category, "value") else str(leak.category),
                severity=leak.severity.value if hasattr(leak.severity, "value") else str(leak.severity),
                evidence_class=leak.evidence_class.value if hasattr(leak.evidence_class, "value") else str(leak.evidence_class),
                transcript_excerpt=leak.transcript_excerpt,
                turn_reference=leak.turn_reference,
                expected_behavior=leak.expected_behavior,
                missing_behavior=leak.missing_behavior,
                confidence=leak.confidence,
                rubric_ref=leak.rubric_ref,
                related_objection_id=leak.related_objection_id,
                recommended_human_review=leak.recommended_human_review,
                review_status=leak.review_status.value if hasattr(leak.review_status, "value") else str(leak.review_status)
            )
            self.db.add(leak_row)

        # Insert Coaching
        for coach in analysis_result.coaching_actions:
            coach_row = CoachingActionModel(
                action_id=coach.action_id,
                call_id=call_id,
                related_finding_id=coach.related_finding_id,
                skill_domain=coach.skill_domain,
                priority=coach.priority.value if hasattr(coach.priority, "value") else str(coach.priority),
                evidence_excerpt=coach.evidence_excerpt,
                recommended_behavior=coach.recommended_behavior,
                example_phrase=coach.example_phrase,
                coaching_guideline_ref=coach.coaching_guideline_ref,
                language=coach.language,
                review_status=coach.review_status.value if hasattr(coach.review_status, "value") else str(coach.review_status)
            )
            self.db.add(coach_row)

        # Single transaction commit
        self.db.commit()

    def get_call_by_id(self, call_id: str) -> Optional[CallModel]:
        return self.db.query(CallModel).filter(CallModel.call_id == call_id).first()

    def get_call_analysis_result(self, call_id: str) -> Optional[CallAnalysisResult]:
        call = self.get_call_by_id(call_id)
        if not call or not call.assessment:
            return None

        ca = call.assessment
        assessment = CallAssessment(
            call_id=call_id,
            overall_score=ca.overall_score,
            objection_count=ca.objection_count,
            objections_addressed_count=ca.objections_addressed_count,
            objections_partially_count=ca.objections_partially_count,
            objections_unaddressed_count=ca.objections_unaddressed_count,
            leakage_count=ca.leakage_count,
            critical_leakage_count=ca.critical_leakage_count,
            high_leakage_count=ca.high_leakage_count,
            medium_leakage_count=ca.medium_leakage_count,
            low_leakage_count=ca.low_leakage_count,
            summary_assessment=ca.summary_assessment,
            review_status=ReviewStatus(ca.review_status),
            reviewer_notes=ca.reviewer_notes,
            model_id=ca.model_id,
            prompt_version=ca.prompt_version,
            analyzed_at=ca.analyzed_at
        )

        objections = [
            ObjectionFinding(
                finding_id=o.finding_id,
                call_id=o.call_id,
                category=o.category_code,
                customer_excerpt=o.customer_excerpt,
                turn_reference=o.turn_reference,
                agent_response_excerpt=o.agent_response_excerpt,
                addressed_status=o.addressed_status,
                speaker_attribution=o.speaker_attribution,
                explanation=o.explanation,
                confidence=o.confidence,
                company_guidance_ref=o.company_guidance_ref,
                review_status=ReviewStatus(o.review_status)
            )
            for o in call.objections
        ]

        leakages = [
            LeakageFinding(
                finding_id=l.finding_id,
                call_id=l.call_id,
                category=l.category_code,
                severity=l.severity,
                evidence_class=l.evidence_class,
                transcript_excerpt=l.transcript_excerpt,
                turn_reference=l.turn_reference,
                expected_behavior=l.expected_behavior,
                missing_behavior=l.missing_behavior,
                confidence=l.confidence,
                rubric_ref=l.rubric_ref,
                related_objection_id=l.related_objection_id,
                recommended_human_review=l.recommended_human_review,
                review_status=ReviewStatus(l.review_status)
            )
            for l in call.leakages
        ]

        coaching = [
            CoachingAction(
                action_id=c.action_id,
                call_id=c.call_id,
                related_finding_id=c.related_finding_id,
                skill_domain=c.skill_domain,
                priority=c.priority,
                evidence_excerpt=c.evidence_excerpt,
                recommended_behavior=c.recommended_behavior,
                example_phrase=c.example_phrase,
                coaching_guideline_ref=c.coaching_guideline_ref,
                language=c.language,
                review_status=ReviewStatus(c.review_status)
            )
            for c in call.coaching
        ]

        return CallAnalysisResult(
            call_id=call_id,
            assessment=assessment,
            objections=objections,
            leakage_findings=leakages,
            coaching_actions=coaching
        )

    def update_review_status(
        self,
        finding_type: str,
        finding_id: str,
        new_status: ReviewStatus,
        reviewer_notes: Optional[str] = None
    ) -> bool:
        """
        Enables supervisor review recording without a custom UI (via script/API).
        """
        status_val = new_status.value if hasattr(new_status, "value") else str(new_status)
        if finding_type == "assessment":
            row = self.db.query(CallAssessmentModel).filter(CallAssessmentModel.call_id == finding_id).first()
            if row:
                row.review_status = status_val
                if reviewer_notes:
                    row.reviewer_notes = reviewer_notes
                self.db.commit()
                return True
        elif finding_type == "objection":
            row = self.db.query(ObjectionFindingModel).filter(ObjectionFindingModel.finding_id == finding_id).first()
            if row:
                row.review_status = status_val
                self.db.commit()
                return True
        elif finding_type == "leakage":
            row = self.db.query(LeakageFindingModel).filter(LeakageFindingModel.finding_id == finding_id).first()
            if row:
                row.review_status = status_val
                self.db.commit()
                return True
        elif finding_type == "coaching":
            row = self.db.query(CoachingActionModel).filter(CoachingActionModel.action_id == finding_id).first()
            if row:
                row.review_status = status_val
                self.db.commit()
                return True
        return False
