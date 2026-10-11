"""
Repeatable benchmark evaluation runner.
Executes pipeline against human-annotated reference transcripts,
evaluates performance metrics, and logs results to PostgreSQL for longitudinal reporting.
"""

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import sys
from typing import Dict, List, Optional
import uuid

# Ensure project root is in sys.path
project_root = str(Path(__file__).resolve().parent.parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import BenchmarkRunModel
from app.db.session import SessionLocal, engine
from app.db.repository import DatabaseRepository
from app.evaluation.metrics import (
    BenchmarkEvaluationReport,
    evaluate_objections,
    evaluate_leakages
)
from app.schemas.transcript import TranscriptInput
from app.services.analysis_pipeline import AnalysisPipeline

logger = logging.getLogger("benchmark")


def run_benchmark(
    ground_truth_path: Optional[str] = None,
    persist_results: bool = True
) -> BenchmarkEvaluationReport:
    """
    Executes benchmark evaluation against annotated dataset.
    """
    if ground_truth_path is None:
        ground_truth_path = str(
            Path(__file__).resolve().parent.parent.parent / "data" / "benchmark_ground_truth.json"
        )

    gt_file = Path(ground_truth_path)
    if not gt_file.exists():
        raise FileNotFoundError(f"Benchmark ground truth file not found: {gt_file}")

    with open(gt_file, "r", encoding="utf-8") as f:
        benchmark_data: List[Dict] = json.load(f)

    db: Session = SessionLocal()
    pipeline = AnalysisPipeline(db_session=db)

    all_predicted_objections = []
    all_gt_objections = []
    all_predicted_leakages = []
    all_gt_leakages = []
    grounded_excerpt_count = 0
    total_excerpts = 0

    print(f"\n--- Running Benchmark Suite on {len(benchmark_data)} Reference Transcripts ---")

    try:
        for idx, sample in enumerate(benchmark_data, start=1):
            call_input = TranscriptInput(
                call_id=sample["call_id"],
                transcript=sample["transcript"],
                agent_id=sample.get("agent_id"),
                call_objective=sample.get("call_objective"),
                source="benchmark"
            )

            # Analyze without persisting standard calls if we only want evaluation
            result = pipeline.analyze_call(call_input, persist=False)

            all_predicted_objections.extend(result.objections)
            all_gt_objections.extend(sample.get("expected_objections", []))

            all_predicted_leakages.extend(result.leakage_findings)
            all_gt_leakages.extend(sample.get("expected_leakages", []))

            # Groundedness calculation
            for obj in result.objections:
                total_excerpts += 1
                if obj.customer_excerpt in sample["transcript"]:
                    grounded_excerpt_count += 1

            for leak in result.leakage_findings:
                total_excerpts += 1
                if leak.transcript_excerpt in sample["transcript"]:
                    grounded_excerpt_count += 1

            print(f"[{idx}/{len(benchmark_data)}] Call {sample['call_id']}: {len(result.objections)} objections, {len(result.leakage_findings)} leakages.")

        obj_score, cat_breakdown = evaluate_objections(all_predicted_objections, all_gt_objections)
        leak_score = evaluate_leakages(all_predicted_leakages, all_gt_leakages)
        groundedness_rate = (
            round(grounded_excerpt_count / max(1, total_excerpts), 4)
            if total_excerpts > 0
            else 1.0
        )

        report = BenchmarkEvaluationReport(
            total_calls_evaluated=len(benchmark_data),
            objection_metrics=obj_score,
            leakage_metrics=leak_score,
            excerpt_groundedness_rate=groundedness_rate,
            category_breakdown=cat_breakdown
        )

        print("\n" + "=" * 65)
        print("  BENCHMARK EVALUATION RESULTS")
        print("=" * 65)
        print(f"Objection Precision:     {obj_score.precision * 100:.1f}%")
        print(f"Objection Recall:        {obj_score.recall * 100:.1f}%")
        print(f"Objection F1-Score:      {obj_score.f1 * 100:.1f}%")
        print("-" * 65)
        print(f"Leakage Precision:       {leak_score.precision * 100:.1f}%")
        print(f"Leakage Recall:          {leak_score.recall * 100:.1f}%")
        print(f"Leakage F1-Score:        {leak_score.f1 * 100:.1f}%")
        print("-" * 65)
        print(f"Excerpt Groundedness:    {groundedness_rate * 100:.1f}%")
        print("=" * 65)

        # Persist benchmark results to database
        if persist_results:
            run_row = BenchmarkRunModel(
                run_id=f"RUN-{uuid.uuid4().hex[:8].upper()}",
                model_id=settings.COHERE_MODEL if not settings.is_mock_llm else "mock-jordanian-cohere",
                prompt_version="v2.0",
                sample_count=len(benchmark_data),
                objection_precision=obj_score.precision,
                objection_recall=obj_score.recall,
                objection_f1=obj_score.f1,
                leakage_precision=leak_score.precision,
                leakage_recall=leak_score.recall,
                leakage_f1=leak_score.f1,
                excerpt_groundedness=groundedness_rate,
                created_at=datetime.now(timezone.utc)
            )
            db.add(run_row)
            db.commit()
            print(f"Logged benchmark run results with ID {run_row.run_id} to database.")

        return report
    finally:
        db.close()


if __name__ == "__main__":
    run_benchmark()
