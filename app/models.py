from pydantic import BaseModel, Field


class RatingPair(BaseModel):
    pair_id: str = Field(min_length=1, max_length=80)
    prompt: str = Field(min_length=1, max_length=4000)
    response: str = Field(min_length=1, max_length=10000)
    human_score: float = Field(ge=0.0, le=10.0)
    judge_score: float = Field(ge=0.0, le=10.0)
    human_rationale: str | None = None
    judge_rationale: str | None = None
    rubric_criterion: str | None = None
    model_evaluated: str | None = None
    response_length_words: int | None = None


class CalibrationRequest(BaseModel):
    scale: float = Field(default=5.0, gt=0.0, le=10.0)
    human_rater_id: str = Field(default="human-expert-consensus", max_length=80)
    judge_model_id: str = Field(default="gpt-4o-judge", max_length=80)
    pairs: list[RatingPair] = Field(min_length=2, max_length=200)


class AgreementMetrics(BaseModel):
    pair_count: int
    mean_absolute_error: float
    root_mean_square_error: float
    exact_match_ratio: float
    within_one_point_ratio: float
    pearson_correlation: float | None
    cohen_weighted_kappa: float | None


class BiasMetrics(BaseModel):
    verbosity_bias_correlation: float | None
    judge_systematic_inflation: float
    severe_disagreements: int


class AdjudicationCase(BaseModel):
    pair_id: str
    prompt: str
    human_score: float
    judge_score: float
    absolute_gap: float
    severity_note: str


class CalibrationReport(BaseModel):
    human_rater_id: str
    judge_model_id: str
    scale: float
    agreement: AgreementMetrics
    bias: BiasMetrics
    reliability_tier: str
    adjudication_queue: list[AdjudicationCase]
