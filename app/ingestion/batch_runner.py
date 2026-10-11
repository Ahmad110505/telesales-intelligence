"""
Batch Runner CLI for the Telesales Intelligence System.
Processes pending transcripts with bounded concurrency, per-call error isolation,
idempotent transactions, and run summary reporting.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import logging
from pathlib import Path
import sys
import time
from typing import Dict, List, Optional

# Ensure project root is in sys.path
project_root = str(Path(__file__).resolve().parent.parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app.config import settings
from app.db.session import SessionLocal, engine
from app.db.repository import DatabaseRepository
from app.ingestion.sources import (
    BaseTranscriptSource,
    FolderTranscriptSource,
    DatabaseTranscriptSource,
    get_transcript_source
)
from app.schemas.transcript import TranscriptInput
from app.schemas.analysis import CallAnalysisResult
from app.services.analysis_pipeline import AnalysisPipeline
from app.reporting.powerbi_refresh import trigger_powerbi_refresh_sync

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("batch_runner")


def process_single_call(transcript_input: TranscriptInput) -> Dict:
    """
    Worker function executed in thread pool for a single call.
    Uses dedicated database session to ensure transaction isolation.
    """
    start_time = time.time()
    db = SessionLocal()
    try:
        pipeline = AnalysisPipeline(db_session=db)
        result: CallAnalysisResult = pipeline.analyze_call(transcript_input, persist=True)
        elapsed = time.time() - start_time
        return {
            "call_id": transcript_input.call_id,
            "success": True,
            "score": result.assessment.overall_score,
            "objections": len(result.objections),
            "leakages": len(result.leakage_findings),
            "coaching": len(result.coaching_actions),
            "elapsed_seconds": round(elapsed, 2),
            "error": None
        }
    except Exception as exc:
        db.rollback()
        elapsed = time.time() - start_time
        logger.error("Call %s failed during analysis: %s", transcript_input.call_id, str(exc), exc_info=True)
        return {
            "call_id": transcript_input.call_id,
            "success": False,
            "score": 0.0,
            "objections": 0,
            "leakages": 0,
            "coaching": 0,
            "elapsed_seconds": round(elapsed, 2),
            "error": str(exc)
        }
    finally:
        db.close()


def run_batch(
    source_type: str = "folder",
    folder_path: Optional[str] = None,
    concurrency: int = 4,
    trigger_refresh: bool = False
) -> Dict:
    """
    Executes the batch run across all pending transcripts.
    """
    print("=" * 70)
    print("  TELESALES INTELLIGENCE SYSTEM - BATCH INGESTION RUNNER")
    print("=" * 70)
    print(f"Source Type:       {source_type}")
    print(f"Folder / Ref:      {folder_path or settings.TRANSCRIPTS_FOLDER_PATH}")
    print(f"Concurrency:       {concurrency} threads")
    print(f"Database:          {settings.DATABASE_URL.split('@')[-1]}")
    print(f"Model ID:          {settings.COHERE_MODEL} (Mock: {settings.is_mock_llm})")
    print("=" * 70)

    # Initialize schema, lookups, and reporting views
    DatabaseRepository.initialize_schema_and_views(engine)

    # Resolve source
    db_for_source = SessionLocal() if source_type == "database" else None
    try:
        source = get_transcript_source(
            source_type=source_type,
            folder_path=folder_path or settings.TRANSCRIPTS_FOLDER_PATH,
            db_session=db_for_source
        )
        pending_calls: List[TranscriptInput] = source.get_pending_transcripts()
    finally:
        if db_for_source:
            db_for_source.close()

    total_pending = len(pending_calls)
    if total_pending == 0:
        print("\nNo pending transcripts found to process. Exiting.")
        return {"total": 0, "succeeded": 0, "failed": 0}

    print(f"\nDiscovered {total_pending} pending transcripts. Starting parallel execution...\n")
    batch_start = time.time()

    results: List[Dict] = []
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        future_to_call = {
            executor.submit(process_single_call, call_input): call_input
            for call_input in pending_calls
        }

        for idx, future in enumerate(as_completed(future_to_call), start=1):
            call_input = future_to_call[future]
            res = future.result()
            results.append(res)

            # Update status in source
            source.mark_processed(
                call_id=res["call_id"],
                success=res["success"],
                error_message=res["error"]
            )

            status_icon = "✓" if res["success"] else "✗"
            print(
                f"[{idx}/{total_pending}] {status_icon} Call: {res['call_id']:<20} | "
                f"Score: {res['score']:>5.1f} | Objections: {res['objections']} | "
                f"Leakages: {res['leakages']} | Time: {res['elapsed_seconds']}s"
            )

    total_time = round(time.time() - batch_start, 2)
    succeeded = sum(1 for r in results if r["success"])
    failed = total_pending - succeeded
    total_objections = sum(r["objections"] for r in results)
    total_leakages = sum(r["leakages"] for r in results)
    total_coaching = sum(r["coaching"] for r in results)
    avg_score = (
        round(sum(r["score"] for r in results if r["success"]) / max(1, succeeded), 1)
        if succeeded > 0
        else 0.0
    )

    print("\n" + "=" * 70)
    print("  BATCH RUN SUMMARY REPORT")
    print("=" * 70)
    print(f"Total Calls Processed:     {total_pending}")
    print(f"Successfully Analyzed:     {succeeded}")
    print(f"Failed Calls:              {failed}")
    print(f"Average Rubric Score:      {avg_score} / 100.0")
    print(f"Total Objections Found:    {total_objections}")
    print(f"Total Leakages Detected:   {total_leakages}")
    print(f"Total Coaching Actions:    {total_coaching}")
    print(f"Total Duration:            {total_time} seconds")
    print("=" * 70)

    # Trigger Power BI refresh if requested
    if trigger_refresh or settings.POWERBI_REFRESH_ENABLED:
        print("\nTriggering Microsoft Power BI semantic model refresh...")
        refresh_res = trigger_powerbi_refresh_sync()
        print(f"Power BI Refresh Result: {refresh_res}")

    return {
        "total": total_pending,
        "succeeded": succeeded,
        "failed": failed,
        "avg_score": avg_score,
        "total_objections": total_objections,
        "total_leakages": total_leakages,
        "total_coaching": total_coaching,
        "elapsed_seconds": total_time
    }


def main():
    parser = argparse.ArgumentParser(description="Telesales Intelligence Batch Runner")
    parser.add_argument(
        "--source",
        choices=["folder", "database"],
        default="folder",
        help="Transcript source type ('folder' or 'database')"
    )
    parser.add_argument(
        "--folder",
        type=str,
        default=None,
        help="Custom folder path containing transcripts (default: from settings)"
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=settings.BATCH_CONCURRENCY,
        help="Worker thread concurrency limit"
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Trigger Power BI dataset refresh after batch completes"
    )

    args = parser.parse_args()
    summary = run_batch(
        source_type=args.source,
        folder_path=args.folder,
        concurrency=args.concurrency,
        trigger_refresh=args.refresh
    )
    if summary["failed"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
