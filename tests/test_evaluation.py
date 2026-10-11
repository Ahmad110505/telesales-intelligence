"""
Unit tests for evaluation metrics and benchmark runner.
"""

from app.evaluation.metrics import compute_prf1, evaluate_objections, evaluate_leakages
from app.evaluation.benchmark import run_benchmark
from app.schemas.analysis import ObjectionFinding, ObjectionCategory, AddressedStatus, LeakageFinding, LeakageCategory, LeakageSeverity, EvidenceClass


def test_compute_prf1():
    # 2 TP, 1 FP, 1 FN
    score = compute_prf1(tp=2, fp=1, fn=1)
    assert score.precision == round(2 / 3, 4)
    assert score.recall == round(2 / 3, 4)
    assert score.f1 == round(2 / 3, 4)


def test_evaluate_objections_matching():
    preds = [
        ObjectionFinding(
            finding_id="OBJ-01",
            category=ObjectionCategory.PRICE,
            customer_excerpt="غالي كتير السعر",
            addressed_status=AddressedStatus.PARTIALLY,
            explanation="Price objection."
        )
    ]
    gt = [
        {
            "category": "price",
            "customer_excerpt": "غالي كتير السعر علي"
        }
    ]

    score, breakdown = evaluate_objections(preds, gt)
    assert score.precision == 1.0
    assert score.recall == 1.0
    assert score.f1 == 1.0


def test_run_benchmark_suite(db_session):
    report = run_benchmark(persist_results=False)
    assert report.total_calls_evaluated >= 3
    assert report.objection_metrics.f1 > 0.0
    assert report.excerpt_groundedness_rate > 0.8
