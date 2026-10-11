"""
Pydantic schemas for validated analysis outputs:
- Customer Objections
- Sales Leakage Findings
- Actionable Coaching Actions
- Call-Level Assessments
Designed for Power BI consumption: typed columns, stable categorical codes, and strict traceability.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import List, Literal, Optional
from pydantic import BaseModel, Field, field_validator


# ==============================================================================
# Stable Categorical Taxonomies
# ==============================================================================

class ObjectionCategory(str, Enum):
    PRICE = "price"
    TIMING = "timing"
    TRUST = "trust"
    PRODUCT_FIT = "product_fit"
    NEED = "need"
    COMPETITOR = "competitor"
    AUTHORITY = "authority"
    INFORMATION_REQUEST = "information_request"
    OTHER = "other"


class AddressedStatus(str, Enum):
    YES = "yes"
    PARTIALLY = "partially"
    NO = "no"
    NOT_APPLICABLE = "not_applicable"


class SpeakerAttribution(str, Enum):
    LABELED = "labeled"
    INFERRED = "inferred"


class LeakageCategory(str, Enum):
    MISSED_DISCOVERY = "missed_discovery"
    UNADDRESSED_OBJECTION = "unaddressed_objection"
    MISSED_RELEVANT_OFFER = "missed_relevant_offer"
    UNCLEAR_VALUE_EXPLANATION = "unclear_value_explanation"
    MISSED_NEXT_STEP = "missed_next_step"
    OTHER = "other"


class LeakageSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class EvidenceClass(str, Enum):
    OBSERVED_FAILURE = "observed_failure"
    PLAUSIBLE_MISSED_OPPORTUNITY = "plausible_missed_opportunity"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class CoachingPriority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ReviewStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    MODIFIED = "modified"


# ==============================================================================
# Finding Entities
# ==============================================================================

class ObjectionFinding(BaseModel):
    """
    Identified customer objection grounded in transcript evidence.
    """
    finding_id: str = Field(..., description="Unique finding ID (e.g. 'OBJ-001')")
    call_id: Optional[str] = Field(None, description="Associated call identifier")
    category: ObjectionCategory = Field(..., description="Standardized objection classification code")
    customer_excerpt: str = Field(..., min_length=2, description="Exact verbatim excerpt from customer in original Jordanian Arabic")
    turn_reference: Optional[str] = Field(None, description="Turn index (e.g. 'Turn 5') or timestamp (e.g. '01:14')")
    agent_response_excerpt: Optional[str] = Field(None, description="Verbatim response of sales agent, if present")
    addressed_status: AddressedStatus = Field(..., description="Effectiveness evaluation of the agent response")
    speaker_attribution: SpeakerAttribution = Field(default=SpeakerAttribution.LABELED, description="Explicit or inferred attribution")
    explanation: str = Field(..., min_length=5, description="Evidence-grounded rationale for classification")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence score [0.0 - 1.0]")
    company_guidance_ref: Optional[str] = Field(None, description="Reference code to company sales policy or playbook")
    review_status: ReviewStatus = Field(default=ReviewStatus.PENDING, description="Human review disposition status")


class LeakageFinding(BaseModel):
    """
    Identified sales leakage or missed opportunity according to sales rubric.
    """
    finding_id: str = Field(..., description="Unique leakage finding ID (e.g. 'LEAK-001')")
    call_id: Optional[str] = Field(None, description="Associated call identifier")
    category: LeakageCategory = Field(..., description="Standardized leakage classification code")
    severity: LeakageSeverity = Field(..., description="Severity impact rating")
    evidence_class: EvidenceClass = Field(..., description="Strength of supporting evidence in transcript")
    transcript_excerpt: str = Field(..., min_length=2, description="Exact verbatim transcript excerpt demonstrating the issue")
    turn_reference: Optional[str] = Field(None, description="Turn index or timestamp reference")
    expected_behavior: str = Field(..., min_length=5, description="What the sales agent was expected to do per rubric")
    missing_behavior: str = Field(..., min_length=5, description="What was missing or inadequately executed")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence score [0.0 - 1.0]")
    rubric_ref: Optional[str] = Field(None, description="Sales methodology / rubric item ID")
    related_objection_id: Optional[str] = Field(None, description="Linked objection finding_id if leakage relates to an objection")
    recommended_human_review: bool = Field(default=False, description="Flag indicating managerial review is recommended")
    review_status: ReviewStatus = Field(default=ReviewStatus.PENDING, description="Human review disposition status")


class CoachingAction(BaseModel):
    """
    Specific, practical coaching recommendation tied to a verified finding.
    """
    action_id: str = Field(..., description="Unique coaching action ID (e.g. 'COACH-001')")
    call_id: Optional[str] = Field(None, description="Associated call identifier")
    related_finding_id: str = Field(..., description="Finding ID (Objection or Leakage) that triggered this coaching")
    skill_domain: str = Field(..., description="Sales competency domain (e.g. 'Active Listening', 'Value Framing')")
    priority: CoachingPriority = Field(..., description="Action priority level")
    evidence_excerpt: str = Field(..., description="Transcript excerpt demonstrating the coaching context")
    recommended_behavior: str = Field(..., min_length=5, description="Actionable guideline for the agent")
    example_phrase: Optional[str] = Field(None, description="Concrete conversational script phrase in Jordanian Arabic or English")
    coaching_guideline_ref: Optional[str] = Field(None, description="Official company playbook guidance ID")
    language: str = Field(default="ar", description="Language of recommendation ('ar' or 'en')")
    review_status: ReviewStatus = Field(default=ReviewStatus.PENDING, description="Supervisor sign-off status")


class CallAssessment(BaseModel):
    """
    Summary score and aggregations for a single call.
    Designed for Power BI call-level KPI cards and dashboards.
    """
    call_id: str = Field(..., description="Call identifier")
    overall_score: float = Field(..., ge=0.0, le=100.0, description="Rubric score 0-100 calculated deterministically")
    objection_count: int = Field(default=0, ge=0, description="Total objections detected (explicit 0 if none)")
    objections_addressed_count: int = Field(default=0, ge=0)
    objections_partially_count: int = Field(default=0, ge=0)
    objections_unaddressed_count: int = Field(default=0, ge=0)
    leakage_count: int = Field(default=0, ge=0, description="Total sales leakage findings")
    critical_leakage_count: int = Field(default=0, ge=0)
    high_leakage_count: int = Field(default=0, ge=0)
    medium_leakage_count: int = Field(default=0, ge=0)
    low_leakage_count: int = Field(default=0, ge=0)
    summary_assessment: str = Field(..., description="Grounded, objective executive summary of the call")
    review_status: ReviewStatus = Field(default=ReviewStatus.PENDING)
    reviewer_notes: Optional[str] = Field(None, description="Notes added by sales manager")
    model_id: str = Field(..., description="Cohere model version used")
    prompt_version: str = Field(default="v2.0", description="Prompt template version")
    analyzed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ==============================================================================
# Composite Analysis Pipeline Result
# ==============================================================================

class CallAnalysisResult(BaseModel):
    """
    Complete analysis result for a call, encapsulating assessment,
    objections, leakage findings, and coaching actions.
    """
    call_id: str
    assessment: CallAssessment
    objections: List[ObjectionFinding] = Field(default_factory=list)
    leakage_findings: List[LeakageFinding] = Field(default_factory=list)
    coaching_actions: List[CoachingAction] = Field(default_factory=list)


# Models used for structured parsing from LLM responses
class ObjectionDetectionPayload(BaseModel):
    objections: List[ObjectionFinding] = Field(default_factory=list)


class LeakageDetectionPayload(BaseModel):
    leakages: List[LeakageFinding] = Field(default_factory=list)


class CoachingGenerationPayload(BaseModel):
    coaching: List[CoachingAction] = Field(default_factory=list)
