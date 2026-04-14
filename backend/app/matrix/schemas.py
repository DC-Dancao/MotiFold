from typing import Any, Dict, List, Optional, Literal
from pydantic import BaseModel, Field, field_validator


MAX_MORPHOLOGICAL_PARAMETERS = 7
MAX_MORPHOLOGICAL_STATES = 7


def normalize_morphological_text(value: Any) -> str:
    return " ".join(str(value).split()).strip()


# --- Keyword Schemas ---

class GenerateKeywordsRequest(BaseModel):
    prompt: str

class GenerateKeywordsResponse(BaseModel):
    words: List[str]

class ModifyKeywordRequest(BaseModel):
    word: str
    context_prompt: Optional[str] = None

class ModifyKeywordResponse(BaseModel):
    new_word: str

class KeywordSchema(BaseModel):
    id: int
    word: str
    source_prompt: Optional[str] = None
    created_at: str

    class Config:
        from_attributes = True

class SaveKeywordRequest(BaseModel):
    words: List[str]
    source_prompt: Optional[str] = None


# --- Morphological Parameter Schemas ---

class MorphologicalParameter(BaseModel):
    name: str = Field(min_length=1)
    states: List[str]

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        normalized = normalize_morphological_text(value)
        if not normalized:
            raise ValueError("Parameter name cannot be empty")
        return normalized


class LLMMorphologicalParameter(BaseModel):
    name: str
    states: List[str]


class LLMGenerateMorphologicalResponse(BaseModel):
    parameters: List[LLMMorphologicalParameter]


class ExtractQuestionRequest(BaseModel):
    problem_description: str

class ExtractQuestionResponse(BaseModel):
    focus_question: str

class GenerateMorphologicalRequest(BaseModel):
    focus_question: str
    workspace_id: Optional[int] = None

class GenerateMorphologicalResponse(BaseModel):
    id: int
    focus_question: str
    status: str

class GenerateMorphologicalLLMResponse(BaseModel):
    parameters: List[MorphologicalParameter]


# --- Consistency Evaluation Schemas ---

class EvaluateConsistencyRequest(BaseModel):
    analysis_id: int

class EvaluationResult(BaseModel):
    red: List[List[int]] = []
    yellow: List[List[int]] = []
    reasons: Dict[str, Dict[str, str]] = {}  # "red"/"yellow" -> {[s1,s2]: reason}
    types: Dict[str, Literal['L', 'E', 'N']] = {}  # {[s1,s2]: type}

class PairEvaluateConsistencyResponse(BaseModel):
    pair: List[int]  # [param1_idx, param2_idx]
    results: EvaluationResult

class BatchEvaluateConsistencyResponse(BaseModel):
    evaluations: List[PairEvaluateConsistencyResponse]

class EvaluateConsistencyResponse(BaseModel):
    id: int
    status: str


# --- Save/Read Schemas ---

class SaveMorphologicalRequest(BaseModel):
    id: Optional[int] = None
    focus_question: str
    parameters: List[MorphologicalParameter]
    matrix: dict

class MorphologicalAnalysisSchema(BaseModel):
    id: int
    focus_question: str
    parameters: List[MorphologicalParameter]
    matrix: dict
    status: str
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


# --- Normalization Helpers ---

def normalize_morphological_response(raw_response: Any) -> GenerateMorphologicalLLMResponse:
    raw_parameters = getattr(raw_response, "parameters", [])

    if not isinstance(raw_parameters, list):
        raise ValueError("LLM response parameters must be a list")

    normalized_parameters: List[MorphologicalParameter] = []
    seen_names = set()

    for raw_parameter in raw_parameters:
        if not isinstance(raw_parameter, dict):
            raw_parameter = raw_parameter.model_dump()

        raw_name = raw_parameter.get("name", "")
        normalized_name_text = normalize_morphological_text(raw_name)
        if not normalized_name_text:
            continue

        normalized_name_lower = normalized_name_text.casefold()
        if normalized_name_lower in seen_names:
            continue

        raw_states = raw_parameter.get("states", [])
        if not isinstance(raw_states, list):
            continue

        normalized_states = []
        seen_states = set()
        for state in raw_states:
            normalized_state = normalize_morphological_text(state)
            if not normalized_state:
                continue
            normalized_state_lower = normalized_state.casefold()
            if normalized_state_lower in seen_states:
                continue
            normalized_states.append(normalized_state)
            seen_states.add(normalized_state_lower)

        if not normalized_states:
            continue

        candidate = MorphologicalParameter(
            name=normalized_name_text,
            states=normalized_states
        )

        normalized_parameters.append(candidate)
        seen_names.add(normalized_name_lower)

    if len(normalized_parameters) < 2:
        raise ValueError(f"Too few usable parameters (got {len(normalized_parameters)}, need at least 2)")

    return GenerateMorphologicalLLMResponse(parameters=normalized_parameters)


# --- Enhanced Matrix & Clustering Schemas ---

class MatrixCellSchema(BaseModel):
    status: Literal['green', 'yellow', 'red']
    contradiction_type: Optional[Literal['L', 'E', 'N']] = None
    reason: Optional[str] = None

class EnhancedMatrixData(Dict[str, Dict[str, MatrixCellSchema]]):
    pass

class ClusterRequest(BaseModel):
    analysis_id: int
    max_clusters: int = Field(default=5, ge=2, le=10)
    # max_solutions_per_cluster removed - was never used

class ClusterSolution(BaseModel):
    name: str
    description: Optional[str] = None
    solution_indices: List[int]

class ClusterResponse(BaseModel):
    clusters: List[ClusterSolution]

class AHPSuggestRequest(BaseModel):
    analysis_id: int
    num_criteria: int = Field(default=4, ge=3, le=6)

class AHPCriteriaResponse(BaseModel):
    criteria: List[Dict[str, float]]

class AHPSuggestResponse(BaseModel):
    criteria: List[Dict[str, float]]

class ScoreRequest(BaseModel):
    analysis_id: int
    cluster_id: Optional[str] = None
    weights: List[Dict[str, float]]

class ScoredSolution(BaseModel):
    rank: int
    solution_index: int
    solution: List[str]
    score: float
    ratings: Dict[str, int]
    summary: str

class ScoreResponse(BaseModel):
    ranked_solutions: List[ScoredSolution]
