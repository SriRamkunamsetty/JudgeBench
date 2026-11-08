"""Statistical calibration, reliability metrics, and evaluator bias detection."""

import math

from app.models import (
    AdjudicationCase,
    AgreementMetrics,
    BiasMetrics,
    CalibrationReport,
    CalibrationRequest,
)


def _pearson(x: list[float], y: list[float]) -> float | None:
    if len(x) != len(y) or len(x) < 2:
        return None
    n = len(x)
    mean_x = sum(x) / n
    mean_y = sum(y) / n
    var_x = sum((xi - mean_x) ** 2 for xi in x)
    var_y = sum((yi - mean_y) ** 2 for yi in y)
    cov = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y, strict=True))
    if var_x > 0 and var_y > 0:
        return round(cov / math.sqrt(var_x * var_y), 4)
    return None


def _quadratic_weighted_kappa(human: list[float], judge: list[float], scale: float) -> float | None:
    """Compute quadratic weighted kappa for continuous/ordinal ratings."""
    if len(human) < 2:
        return None
    n = len(human)
    # Disagreement weight: (i - j)^2 / (scale^2)
    observed_disagreement = sum(
        ((h - j) ** 2) / (scale**2) for h, j in zip(human, judge, strict=True)
    ) / n

    # Expected disagreement by chance
    expected_disagreement = sum(
        ((h - j) ** 2) / (scale**2) for h in human for j in judge
    ) / (n * n)

    if expected_disagreement <= 0:
        return 1.0 if observed_disagreement == 0 else 0.0

    kappa = 1.0 - (observed_disagreement / expected_disagreement)
    return round(max(-1.0, min(1.0, kappa)), 4)


def compute_calibration(req: CalibrationRequest) -> CalibrationReport:
    human_scores = [p.human_score for p in req.pairs]
    judge_scores = [p.judge_score for p in req.pairs]
    n = len(human_scores)

    # Calculate differences
    errors = [j - h for h, j in zip(human_scores, judge_scores, strict=True)]
    abs_errors = [abs(e) for e in errors]

    mae = round(sum(abs_errors) / n, 4)
    rmse = round(math.sqrt(sum(e**2 for e in errors) / n), 4)
    exact_match = round(sum(e == 0 for e in abs_errors) / n, 4)
    within_one = round(sum(e <= 1.0 for e in abs_errors) / n, 4)
    pearson_r = _pearson(human_scores, judge_scores)
    kappa = _quadratic_weighted_kappa(human_scores, judge_scores, req.scale)

    agreement = AgreementMetrics(
        pair_count=n,
        mean_absolute_error=mae,
        root_mean_square_error=rmse,
        exact_match_ratio=exact_match,
        within_one_point_ratio=within_one,
        pearson_correlation=pearson_r,
        cohen_weighted_kappa=kappa,
    )

    # Bias analysis
    word_counts = [
        p.response_length_words if p.response_length_words is not None else len(p.response.split())
        for p in req.pairs
    ]
    float_words = [float(w) for w in word_counts]
    verbosity_corr = _pearson(float_words, judge_scores)
    systematic_inflation = round(sum(errors) / n, 4)

    adjudication_queue = []
    severe_threshold = max(1.5, req.scale * 0.3)
    for p in req.pairs:
        gap = abs(p.human_score - p.judge_score)
        if gap >= severe_threshold:
            adjudication_queue.append(
                AdjudicationCase(
                    pair_id=p.pair_id,
                    prompt=p.prompt[:200],
                    human_score=p.human_score,
                    judge_score=p.judge_score,
                    absolute_gap=round(gap, 2),
                    severity_note=(
                        f"Judge scored {p.judge_score} while human rated {p.human_score} "
                        f"(gap: {gap:.1f}). Human adjudication required."
                    ),
                )
            )

    bias = BiasMetrics(
        verbosity_bias_correlation=verbosity_corr,
        judge_systematic_inflation=systematic_inflation,
        severe_disagreements=len(adjudication_queue),
    )

    # Reliability Tier
    if mae <= 0.4 and (pearson_r is not None and pearson_r >= 0.85) and not adjudication_queue:
        tier = "EXCELLENT_AUTOMATION_READY"
    elif mae <= 0.8 and (pearson_r is not None and pearson_r >= 0.65):
        tier = "MODERATE_REQUIRES_HUMAN_AUDIT"
    else:
        tier = "POOR_HUMAN_IN_THE_LOOP_MANDATORY"

    return CalibrationReport(
        human_rater_id=req.human_rater_id,
        judge_model_id=req.judge_model_id,
        scale=req.scale,
        agreement=agreement,
        bias=bias,
        reliability_tier=tier,
        adjudication_queue=adjudication_queue,
    )
