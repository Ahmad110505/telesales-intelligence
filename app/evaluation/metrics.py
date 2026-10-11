"""
Evaluation metrics comparing model output against human-reviewed reference annotations.
Computes Precision, Recall, F1, dialect groundedness, and category accuracy.
"""

from typing import Dict, List, Set, Tuple
from pydantic import BaseModel, Field

from app.schemas.analysis import ObjectionFinding, LeakageFinding


class MetricScore(BaseModel):
    precision: float = Field(..., ge=0.0, le=1.0)
    recall: float = Field(..., ge=0.0, le=1.0)
    f1: float = Field(..., ge=0.0, le=1.0)
    true_positives: int
    false_positives: int
    false_negatives: int


class BenchmarkEvaluationReport(BaseModel):
    total_calls_evaluated: int
    objection_metrics: MetricScore
    leakage_metrics: MetricScore
    excerpt_groundedness_rate: float = Field(..., ge=0.0, le=1.0)
    category_breakdown: Dict[str, Dict[str, float]] = Field(default_factory=dict)


def compute_prf1(tp: int, fp: int, fn: int) -> MetricScore:
    prec = tp / (tp + fp) if (tp + fp) > 0 else (1.0 if fn == 0 else 0.0)
    rec = tp / (tp + fn) if (tp + fn) > 0 else (1.0 if fp == 0 else 0.0)
    f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0
    return MetricScore(
        precision=round(prec, 4),
        recall=round(rec, 4),
        f1=round(f1, 4),
        true_positives=tp,
        false_positives=fp,
        false_negatives=fn
    )


def evaluate_objections(
    predicted: List[ObjectionFinding],
    ground_truth: List[Dict]
) -> Tuple[MetricScore, Dict[str, Dict[str, float]]]:
    """
    Evaluates objection classification against annotated reference labels.
    A match occurs when predicted category matches reference category and excerpts overlap.
    """
    pred_cats = [o.category.value for o in predicted]
    gt_cats = [g.get("category") for g in ground_truth]

    matched_gt = set()
    tp = 0
    fp = 0

    category_stats: Dict[str, Dict[str, int]] = {}

    for pred in predicted:
        cat = pred.category.value
        if cat not in category_stats:
            category_stats[cat] = {"tp": 0, "fp": 0, "fn": 0}

        match_found = False
        for idx, gt in enumerate(ground_truth):
            if idx not in matched_gt and gt.get("category") == cat:
                # Check excerpt overlap
                p_exc = pred.customer_excerpt.lower()
                g_exc = str(gt.get("customer_excerpt", "")).lower()
                if p_exc in g_exc or g_exc in p_exc or len(set(p_exc.split()) & set(g_exc.split())) >= 2:
                    matched_gt.add(idx)
                    match_found = True
                    break

        if match_found:
            tp += 1
            category_stats[cat]["tp"] += 1
        else:
            fp += 1
            category_stats[cat]["fp"] += 1

    fn = len(ground_truth) - len(matched_gt)
    for idx, gt in enumerate(ground_truth):
        if idx not in matched_gt:
            cat = gt.get("category", "other")
            if cat not in category_stats:
                category_stats[cat] = {"tp": 0, "fp": 0, "fn": 0}
            category_stats[cat]["fn"] += 1

    overall = compute_prf1(tp, fp, fn)

    cat_breakdown = {}
    for c, stats in category_stats.items():
        score = compute_prf1(stats["tp"], stats["fp"], stats["fn"])
        cat_breakdown[c] = {"precision": score.precision, "recall": score.recall, "f1": score.f1}

    return overall, cat_breakdown


def evaluate_leakages(
    predicted: List[LeakageFinding],
    ground_truth: List[Dict]
) -> MetricScore:
    """
    Evaluates leakage classification against reference labels.
    """
    matched_gt = set()
    tp = 0
    fp = 0

    for pred in predicted:
        cat = pred.category.value
        match_found = False
        for idx, gt in enumerate(ground_truth):
            if idx not in matched_gt and gt.get("category") == cat:
                matched_gt.add(idx)
                match_found = True
                break
        if match_found:
            tp += 1
        else:
            fp += 1

    fn = len(ground_truth) - len(matched_gt)
    return compute_prf1(tp, fp, fn)
