"""
Headless REST API endpoints for transcript ingestion, call retrieval,
review status updates, and operational tasks.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.repository import DatabaseRepository
from app.schemas.transcript import TranscriptInput
from app.schemas.analysis import CallAnalysisResult, ReviewStatus
from app.services.analysis_pipeline import AnalysisPipeline
from app.ingestion.batch_runner import run_batch
from app.reporting.powerbi_refresh import PowerBIRefreshClient

router = APIRouter(prefix="/calls", tags=["Calls & Analysis"])


class ReviewUpdateRequest(BaseModel):
    finding_type: str  # "assessment", "objection", "leakage", "coaching"
    finding_id: str
    new_status: ReviewStatus
    reviewer_notes: Optional[str] = None


class BatchTriggerRequest(BaseModel):
    source_type: str = "folder"
    folder_path: Optional[str] = None
    concurrency: int = 4
    refresh_powerbi: bool = False


@router.post(
    "/analyze",
    response_model=CallAnalysisResult,
    status_code=status.HTTP_201_CREATED,
    summary="Programmatic transcript submission and real-time analysis"
)
def analyze_call_endpoint(
    transcript_input: TranscriptInput,
    db: Session = Depends(get_db)
) -> CallAnalysisResult:
    """
    Submits a call transcript for immediate end-to-end analysis.
    Validates evidence, scores against rubric, generates coaching,
    and commits atomically to PostgreSQL.
    """
    try:
        pipeline = AnalysisPipeline(db_session=db)
        result = pipeline.analyze_call(transcript_input, persist=True)
        return result
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analysis pipeline error: {str(exc)}"
        )


@router.get(
    "/{call_id}",
    response_model=CallAnalysisResult,
    summary="Retrieve verified analysis result for a call"
)
def get_call_analysis_endpoint(
    call_id: str,
    db: Session = Depends(get_db)
) -> CallAnalysisResult:
    """
    Retrieves the complete analysis, objections, leakages, and coaching actions for a call.
    """
    repo = DatabaseRepository(db)
    result = repo.get_call_analysis_result(call_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Call '{call_id}' not found or has not been analyzed yet."
        )
    return result


@router.get(
    "/{call_id}/dashboard-data",
    summary="Get pre-formatted dashboard view payload for Power BI deep-linking"
)
def get_call_dashboard_data_endpoint(
    call_id: str,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Provides the exact structured payload matching the Power BI call-level dashboard page.
    """
    repo = DatabaseRepository(db)
    call = repo.get_call_by_id(call_id)
    if not call or not call.assessment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Call dashboard data not found.")

    res = repo.get_call_analysis_result(call_id)
    return {
        "call_id": call.call_id,
        "agent_id": call.agent_id,
        "call_date": call.call_date.isoformat(),
        "call_objective": call.call_objective,
        "turn_count": call.turn_count,
        "kpis": {
            "overall_score": call.assessment.overall_score,
            "objection_count": call.assessment.objection_count,
            "objections_addressed": call.assessment.objections_addressed_count,
            "objections_unaddressed": call.assessment.objections_unaddressed_count,
            "leakage_count": call.assessment.leakage_count,
            "critical_leakage_count": call.assessment.critical_leakage_count
        },
        "summary_assessment": call.assessment.summary_assessment,
        "objections": [o.model_dump() for o in res.objections] if res else [],
        "leakages": [l.model_dump() for l in res.leakage_findings] if res else [],
        "coaching": [c.model_dump() for c in res.coaching_actions] if res else [],
        "transcript_raw": call.transcript_raw
    }


@router.post(
    "/{call_id}/review",
    summary="Record supervisor review decision for a call or finding"
)
def update_review_endpoint(
    call_id: str,
    req: ReviewUpdateRequest,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Allows supervisors to record accepted/rejected/modified dispositions
    without needing a dedicated frontend.
    """
    repo = DatabaseRepository(db)
    success = repo.update_review_status(
        finding_type=req.finding_type,
        finding_id=req.finding_id,
        new_status=req.new_status,
        reviewer_notes=req.reviewer_notes
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target {req.finding_type} with ID '{req.finding_id}' not found."
        )
    return {"status": "updated", "finding_id": req.finding_id, "new_status": req.new_status}


# Operations Router
ops_router = APIRouter(prefix="/operations", tags=["Operations"])


@ops_router.post("/batch", summary="Trigger batch ingestion run")
def trigger_batch_endpoint(req: BatchTriggerRequest) -> Dict[str, Any]:
    summary = run_batch(
        source_type=req.source_type,
        folder_path=req.folder_path,
        concurrency=req.concurrency,
        trigger_refresh=req.refresh_powerbi
    )
    return {"status": "completed", "summary": summary}


@ops_router.post("/powerbi/refresh", summary="Manually trigger Power BI semantic model refresh")
async def trigger_pbi_refresh_endpoint() -> Dict[str, Any]:
    client = PowerBIRefreshClient()
    res = await client.trigger_dataset_refresh()
    return res
