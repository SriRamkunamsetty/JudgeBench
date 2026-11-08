from fastapi.testclient import TestClient

from app.calibration import compute_calibration
from app.main import app
from app.models import CalibrationRequest, RatingPair

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "judgebench"}


def test_benchmark_dataset_endpoint():
    response = client.get("/api/benchmark-dataset")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert len(data["items"]) >= 5


def test_perfect_calibration_math():
    pairs = [
        RatingPair(
            pair_id=f"p-{i}",
            prompt=f"Prompt {i}",
            response="Standard response",
            human_score=float(i),
            judge_score=float(i),
        )
        for i in range(1, 6)
    ]
    req = CalibrationRequest(scale=5.0, pairs=pairs)
    report = compute_calibration(req)

    assert report.agreement.pair_count == 5
    assert report.agreement.pearson_correlation == 1.0
    assert report.agreement.mean_absolute_error == 0.0
    assert report.agreement.root_mean_square_error == 0.0
    assert len(report.adjudication_queue) == 0


def test_disagreement_detection_and_bias():
    pairs = [
        RatingPair(
            pair_id="p-1",
            prompt="Simple query",
            response="Very short answer.",
            human_score=5.0,
            judge_score=2.0,  # AI penalized short text
            human_rationale="Direct and accurate",
            judge_rationale="Too concise, missing elaboration",
        ),
        RatingPair(
            pair_id="p-2",
            prompt="Query two",
            response="Comprehensive detailed elaboration with numerous explanatory clauses. " * 20,
            human_score=2.5,
            judge_score=5.0,  # AI loved verbosity
            human_rationale="Overly verbose padding",
            judge_rationale="Comprehensive and detailed",
        ),
        RatingPair(
            pair_id="p-3",
            prompt="Query three",
            response="Moderate response text with reasonable length.",
            human_score=4.0,
            judge_score=4.1,
        ),
    ]
    req = CalibrationRequest(scale=5.0, pairs=pairs)
    report = compute_calibration(req)

    assert report.agreement.pair_count == 3
    # Both p-1 and p-2 have gap >= 1.5
    assert len(report.adjudication_queue) == 2
    assert report.adjudication_queue[0].pair_id in ["p-1", "p-2"]
    # Verbosity bias should detect positive correlation between length and judge score
    assert report.bias.verbosity_bias_correlation is not None
    assert report.bias.verbosity_bias_correlation > 0.0


def test_calibrate_api_and_markdown_export():
    payload = {
        "scale": 5.0,
        "human_rater_id": "human-reviewer-1",
        "judge_model_id": "gpt-4o",
        "pairs": [
            {
                "pair_id": "t-1",
                "prompt": "Explain recursion.",
                "response": "Recursion is when a function calls itself until a base condition.",
                "human_score": 4.5,
                "judge_score": 4.6,
            },
            {
                "pair_id": "t-2",
                "prompt": "Explain deadlocks.",
                "response": "A deadlock happens when processes hold resources and wait for each other.",
                "human_score": 4.8,
                "judge_score": 4.7,
            },
        ],
    }

    cal_res = client.post("/api/calibrate", json=payload)
    assert cal_res.status_code == 200
    report_json = cal_res.json()
    assert report_json["agreement"]["pair_count"] == 2
    assert "agreement" in report_json
    assert "bias" in report_json

    md_res = client.post("/api/reports/markdown", json=payload)
    assert md_res.status_code == 200
    md_content = md_res.text
    assert "# JudgeBench - Evaluator Calibration & Reliability Audit" in md_content
    assert "human-reviewer-1" in md_content
    assert "Pearson Correlation (r)" in md_content
