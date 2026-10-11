"""
SQLAlchemy relational models designed for PostgreSQL and Power BI consumption.
Strictly typed columns, foreign key cascades, and language-independent stable codes.
"""

from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class CallModel(Base):
    __tablename__ = "calls"

    call_id = Column(String(128), primary_key=True, index=True)
    agent_id = Column(String(64), nullable=True, index=True)
    call_date = Column(DateTime(timezone=True), nullable=False, index=True, default=lambda: datetime.now(timezone.utc))
    call_objective = Column(String(256), nullable=True)
    source = Column(String(64), nullable=False, default="batch_folder")
    source_ref = Column(String(512), nullable=True)
    transcript_raw = Column(Text, nullable=False)
    turn_count = Column(Integer, nullable=False, default=0)
    duration_seconds = Column(Integer, nullable=True)
    metadata_json = Column(Text, nullable=True)
    status = Column(String(32), nullable=False, default="analyzed")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    assessment = relationship("CallAssessmentModel", back_populates="call", uselist=False, cascade="all, delete-orphan")
    objections = relationship("ObjectionFindingModel", back_populates="call", cascade="all, delete-orphan")
    leakages = relationship("LeakageFindingModel", back_populates="call", cascade="all, delete-orphan")
    coaching = relationship("CoachingActionModel", back_populates="call", cascade="all, delete-orphan")


class CallAssessmentModel(Base):
    __tablename__ = "call_assessments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    call_id = Column(String(128), ForeignKey("calls.call_id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    overall_score = Column(Float, nullable=False)
    objection_count = Column(Integer, nullable=False, default=0)
    objections_addressed_count = Column(Integer, nullable=False, default=0)
    objections_partially_count = Column(Integer, nullable=False, default=0)
    objections_unaddressed_count = Column(Integer, nullable=False, default=0)
    leakage_count = Column(Integer, nullable=False, default=0)
    critical_leakage_count = Column(Integer, nullable=False, default=0)
    high_leakage_count = Column(Integer, nullable=False, default=0)
    medium_leakage_count = Column(Integer, nullable=False, default=0)
    low_leakage_count = Column(Integer, nullable=False, default=0)
    summary_assessment = Column(Text, nullable=False)
    review_status = Column(String(32), nullable=False, default="pending")
    reviewer_notes = Column(Text, nullable=True)
    model_id = Column(String(128), nullable=False)
    prompt_version = Column(String(32), nullable=False, default="v2.0")
    analyzed_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    call = relationship("CallModel", back_populates="assessment")


class ObjectionFindingModel(Base):
    __tablename__ = "objection_findings"

    finding_id = Column(String(128), primary_key=True)
    call_id = Column(String(128), ForeignKey("calls.call_id", ondelete="CASCADE"), nullable=False, index=True)
    category_code = Column(String(64), nullable=False, index=True)
    customer_excerpt = Column(Text, nullable=False)
    turn_reference = Column(String(64), nullable=True)
    agent_response_excerpt = Column(Text, nullable=True)
    addressed_status = Column(String(32), nullable=False, index=True)
    speaker_attribution = Column(String(32), nullable=False, default="labeled")
    explanation = Column(Text, nullable=False)
    confidence = Column(Float, nullable=False, default=1.0)
    company_guidance_ref = Column(String(128), nullable=True)
    review_status = Column(String(32), nullable=False, default="pending")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    call = relationship("CallModel", back_populates="objections")


class LeakageFindingModel(Base):
    __tablename__ = "leakage_findings"

    finding_id = Column(String(128), primary_key=True)
    call_id = Column(String(128), ForeignKey("calls.call_id", ondelete="CASCADE"), nullable=False, index=True)
    category_code = Column(String(64), nullable=False, index=True)
    severity = Column(String(32), nullable=False, index=True)
    evidence_class = Column(String(64), nullable=False)
    transcript_excerpt = Column(Text, nullable=False)
    turn_reference = Column(String(64), nullable=True)
    expected_behavior = Column(Text, nullable=False)
    missing_behavior = Column(Text, nullable=False)
    confidence = Column(Float, nullable=False, default=1.0)
    rubric_ref = Column(String(128), nullable=True)
    related_objection_id = Column(String(128), nullable=True)
    recommended_human_review = Column(Boolean, nullable=False, default=False)
    review_status = Column(String(32), nullable=False, default="pending")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    call = relationship("CallModel", back_populates="leakages")


class CoachingActionModel(Base):
    __tablename__ = "coaching_actions"

    action_id = Column(String(128), primary_key=True)
    call_id = Column(String(128), ForeignKey("calls.call_id", ondelete="CASCADE"), nullable=False, index=True)
    related_finding_id = Column(String(128), nullable=False, index=True)
    skill_domain = Column(String(128), nullable=False)
    priority = Column(String(32), nullable=False, index=True)
    evidence_excerpt = Column(Text, nullable=False)
    recommended_behavior = Column(Text, nullable=False)
    example_phrase = Column(Text, nullable=True)
    coaching_guideline_ref = Column(String(128), nullable=True)
    language = Column(String(8), nullable=False, default="ar")
    review_status = Column(String(32), nullable=False, default="pending")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    call = relationship("CallModel", back_populates="coaching")


class CategoryLookupModel(Base):
    __tablename__ = "category_lookups"

    id = Column(Integer, primary_key=True, autoincrement=True)
    category_type = Column(String(64), nullable=False, index=True)
    code = Column(String(64), nullable=False, index=True)
    label_en = Column(String(128), nullable=False)
    label_ar = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)


class SourceCallsStagingModel(Base):
    __tablename__ = "source_calls_staging"

    staging_id = Column(Integer, primary_key=True, autoincrement=True)
    call_id = Column(String(128), unique=True, nullable=False, index=True)
    transcript_text = Column(Text, nullable=False)
    agent_id = Column(String(64), nullable=True)
    call_date = Column(DateTime(timezone=True), nullable=True)
    call_objective = Column(String(256), nullable=True)
    metadata_json = Column(Text, nullable=True)
    status = Column(String(32), nullable=False, default="pending")  # pending, processing, completed, failed
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    processed_at = Column(DateTime(timezone=True), nullable=True)


class BenchmarkRunModel(Base):
    __tablename__ = "benchmark_runs"

    run_id = Column(String(128), primary_key=True)
    model_id = Column(String(128), nullable=False)
    prompt_version = Column(String(32), nullable=False)
    sample_count = Column(Integer, nullable=False)
    objection_precision = Column(Float, nullable=False)
    objection_recall = Column(Float, nullable=False)
    objection_f1 = Column(Float, nullable=False)
    leakage_precision = Column(Float, nullable=False)
    leakage_recall = Column(Float, nullable=False)
    leakage_f1 = Column(Float, nullable=False)
    excerpt_groundedness = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
