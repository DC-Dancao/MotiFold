from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import Any, List, Optional, Dict, Tuple
from pydantic import BaseModel, Field, ValidationError, field_validator
from langchain_core.messages import SystemMessage, HumanMessage
import json

from app.llm import get_llm

from app.database import get_db
from app.models import User, Keyword, MorphologicalAnalysis
from app.auth import get_current_user
from app.config import settings

router = APIRouter(prefix="/matrix", tags=["matrix"])

MAX_MORPHOLOGICAL_PARAMETERS = 7
MAX_MORPHOLOGICAL_STATES = 7


def normalize_morphological_text(value: Any) -> str:
    return " ".join(str(value).split()).strip()


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


class EvaluateConsistencyRequest(BaseModel):
    analysis_id: int


class EvaluateConsistencyReasons(BaseModel):
    red: str
    yellow: str


class EvaluateConsistencyResults(BaseModel):
    red: List[List[int]]
    yellow: List[List[int]]
    reasons: EvaluateConsistencyReasons


class PairEvaluateConsistencyResponse(BaseModel):
    pair: List[int]
    results: EvaluateConsistencyResults


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


@router.post("/morphological/extract-question", response_model=ExtractQuestionResponse)
async def extract_question(
    req: ExtractQuestionRequest,
    current_user: User = Depends(get_current_user),
):
    try:
        llm = get_llm(model_name=settings.OPENAI_MODEL_MINI, temperature=0, streaming=True)
        prompt = (
            "Summarize the following problem description into a single, concise focus question "
            "(a complete sentence, under 20 words). Return ONLY the question itself, "
            "with no quotes, no introductory text, and NO trailing ellipses (...).\n\n"
            f"Problem: {req.problem_description}"
        )
        messages = [
            SystemMessage(content="You are an expert analyst."),
            HumanMessage(content=prompt)
        ]
        response = await llm.ainvoke(messages)
        focus_question = response.content.strip().strip('"').strip("'")
        
        # Clean up any trailing ellipses or periods that the LLM might have generated
        while focus_question.endswith(".") or focus_question.endswith("。") or focus_question.endswith("…"):
            focus_question = focus_question[:-1]
        
        focus_question = focus_question.strip()
        
        if not focus_question:
            focus_question = req.problem_description[:50]
            
        return ExtractQuestionResponse(focus_question=focus_question)
    except Exception as e:
        print(f"Error extracting question: {e}")
        raise HTTPException(status_code=500, detail="Failed to extract question")


@router.post("/morphological/generate", response_model=GenerateMorphologicalResponse)
async def generate_morphological(
    req: GenerateMorphologicalRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        from app.worker import generate_morphological_task
        
        # Create a pending analysis record
        analysis = MorphologicalAnalysis(
            user_id=current_user.id,
            workspace_id=req.workspace_id,
            focus_question=req.focus_question,
            parameters_json="[]",
            matrix_json="{}",
            status="generating_parameters"
        )
        db.add(analysis)
        await db.commit()
        await db.refresh(analysis)
        
        # Enqueue the Celery task
        generate_morphological_task.delay(analysis.id)
        
        return GenerateMorphologicalResponse(
            id=analysis.id,
            focus_question=analysis.focus_question,
            status=analysis.status
        )
    except Exception as e:
        print(f"Error starting morphological generation: {e}")
        raise HTTPException(status_code=500, detail="Failed to start generation")

class BatchEvaluateConsistencyResponse(BaseModel):
    evaluations: List[PairEvaluateConsistencyResponse]


class EvaluateConsistencyResponse(BaseModel):
    id: int
    status: str


def build_consistency_table(parameters: List[MorphologicalParameter]) -> Tuple[str, List[Tuple[int, int]]]:
    sections: List[str] = []
    pair_order: List[Tuple[int, int]] = []

    for p1_idx in range(len(parameters)):
        for p2_idx in range(p1_idx + 1, len(parameters)):
            p1 = parameters[p1_idx]
            p2 = parameters[p2_idx]
            pair_order.append((p1_idx, p2_idx))

            lines = [
                f"Pair [{p1_idx}, {p2_idx}]",
                f"Parameter {p1_idx}: {p1.name}",
                ", ".join(f"({idx}) {state}" for idx, state in enumerate(p1.states)),
                f"Parameter {p2_idx}: {p2.name}",
                ", ".join(f"({idx}) {state}" for idx, state in enumerate(p2.states)),
                "Indexed comparison rows:"
            ]

            row_index = 0
            for s1_idx, s1 in enumerate(p1.states):
                for s2_idx, s2 in enumerate(p2.states):
                    lines.append(
                        f"[{row_index}] [{s1_idx}, {s2_idx}] ({s1}) vs ({s2})"
                    )
                    row_index += 1

            sections.append("\n".join(lines))

    return "\n\n".join(sections), pair_order


def build_default_matrix(parameters: List[MorphologicalParameter]) -> Dict[str, Dict[str, str]]:
    matrix: Dict[str, Dict[str, str]] = {}

    for p1_idx in range(len(parameters)):
        for p2_idx in range(p1_idx + 1, len(parameters)):
            pair_key = f"{p1_idx}_{p2_idx}"
            matrix[pair_key] = {}
            for s1_idx in range(len(parameters[p1_idx].states)):
                for s2_idx in range(len(parameters[p2_idx].states)):
                    matrix[pair_key][f"{s1_idx}_{s2_idx}"] = "green"

    return matrix


def apply_consistency_results(
    parameters: List[MorphologicalParameter],
    response: BatchEvaluateConsistencyResponse
) -> Tuple[Dict[str, Dict[str, str]], List[PairEvaluateConsistencyResponse]]:
    matrix_data = build_default_matrix(parameters)
    expected_pairs = set(matrix_data.keys())
    seen_pairs = set()
    normalized_results: List[PairEvaluateConsistencyResponse] = []

    for evaluation in response.evaluations:
        if len(evaluation.pair) != 2:
            raise ValueError("Invalid pair identifier returned by LLM")

        p1_idx, p2_idx = evaluation.pair
        pair_key = f"{p1_idx}_{p2_idx}"

        if pair_key not in matrix_data:
            raise ValueError(f"Unexpected pair returned by LLM: {evaluation.pair}")

        seen_pairs.add(pair_key)

        p1 = parameters[p1_idx]
        p2 = parameters[p2_idx]

        red_pairs = {
            f"{row[0]}_{row[1]}"
            for row in evaluation.results.red
            if len(row) == 2 and 0 <= row[0] < len(p1.states) and 0 <= row[1] < len(p2.states)
        }
        yellow_pairs = {
            f"{row[0]}_{row[1]}"
            for row in evaluation.results.yellow
            if len(row) == 2 and 0 <= row[0] < len(p1.states) and 0 <= row[1] < len(p2.states)
        }

        for state_key in red_pairs:
            matrix_data[pair_key][state_key] = "red"

        for state_key in yellow_pairs:
            if state_key not in red_pairs:
                matrix_data[pair_key][state_key] = "yellow"

        normalized_results.append(evaluation)

    if seen_pairs != expected_pairs:
        missing_pairs = sorted(expected_pairs - seen_pairs)
        raise ValueError(f"LLM response is missing pair evaluations: {missing_pairs}")

    return matrix_data, normalized_results


from sqlalchemy import update

@router.post("/morphological/evaluate", response_model=EvaluateConsistencyResponse)
async def evaluate_consistency(
    req: EvaluateConsistencyRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        from app.worker import evaluate_consistency_task
        
        stmt = update(MorphologicalAnalysis).where(
            MorphologicalAnalysis.id == req.analysis_id, 
            MorphologicalAnalysis.user_id == current_user.id,
            MorphologicalAnalysis.status.in_(["parameters_ready", "matrix_ready", "evaluate_failed"])
        ).values(status="evaluating_matrix").returning(MorphologicalAnalysis)
        
        result = await db.execute(stmt)
        analysis = result.scalars().first()
        
        if not analysis:
            raise HTTPException(status_code=409, detail="Morphological analysis not found or not in a valid state for evaluation")
            
        await db.commit()
        
        evaluate_consistency_task.delay(analysis.id)
        
        return EvaluateConsistencyResponse(
            id=analysis.id,
            status=analysis.status
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error starting evaluation: {e}")
        raise HTTPException(status_code=500, detail="Failed to start evaluation")


@router.post("/morphological", response_model=MorphologicalAnalysisSchema)
async def save_morphological_analysis(
    req: SaveMorphologicalRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        parameters_json = json.dumps([p.model_dump() for p in req.parameters])
        matrix_json = json.dumps(req.matrix)

        if req.id:
            stmt = select(MorphologicalAnalysis).where(MorphologicalAnalysis.id == req.id, MorphologicalAnalysis.user_id == current_user.id)
            result = await db.execute(stmt)
            analysis = result.scalars().first()
            
            if not analysis:
                raise HTTPException(status_code=404, detail="Analysis not found")
                
            analysis.focus_question = req.focus_question
            analysis.parameters_json = parameters_json
            analysis.matrix_json = matrix_json
        else:
            analysis = MorphologicalAnalysis(
                user_id=current_user.id,
                focus_question=req.focus_question,
                parameters_json=parameters_json,
                matrix_json=matrix_json
            )
            db.add(analysis)
            
        await db.commit()
        await db.refresh(analysis)

        return MorphologicalAnalysisSchema(
            id=analysis.id,
            focus_question=analysis.focus_question,
            parameters=json.loads(analysis.parameters_json),
            matrix=json.loads(analysis.matrix_json),
            status=analysis.status,
            created_at=analysis.created_at.isoformat() if analysis.created_at else "",
            updated_at=analysis.updated_at.isoformat() if analysis.updated_at else ""
        )
    except Exception as e:
        print(f"Error saving morphological analysis: {e}")
        raise HTTPException(status_code=500, detail="Failed to save morphological analysis")


@router.get("/morphological", response_model=List[MorphologicalAnalysisSchema])
async def get_morphological_analyses(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(MorphologicalAnalysis).where(MorphologicalAnalysis.user_id == current_user.id).order_by(MorphologicalAnalysis.updated_at.desc())
    result = await db.execute(stmt)
    analyses = result.scalars().all()

    resp = []
    for a in analyses:
        resp.append(MorphologicalAnalysisSchema(
            id=a.id,
            focus_question=a.focus_question,
            parameters=json.loads(a.parameters_json),
            matrix=json.loads(a.matrix_json),
            status=a.status,
            created_at=a.created_at.isoformat() if a.created_at else "",
            updated_at=a.updated_at.isoformat() if a.updated_at else ""
        ))
    return resp


@router.get("/morphological/{analysis_id}", response_model=MorphologicalAnalysisSchema)
async def get_morphological_analysis(
    analysis_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(MorphologicalAnalysis).where(MorphologicalAnalysis.id == analysis_id, MorphologicalAnalysis.user_id == current_user.id)
    result = await db.execute(stmt)
    analysis = result.scalars().first()

    if not analysis:
        raise HTTPException(status_code=404, detail="Morphological analysis not found")

    return MorphologicalAnalysisSchema(
        id=analysis.id,
        focus_question=analysis.focus_question,
        parameters=json.loads(analysis.parameters_json),
        matrix=json.loads(analysis.matrix_json),
        status=analysis.status,
        created_at=analysis.created_at.isoformat() if analysis.created_at else "",
        updated_at=analysis.updated_at.isoformat() if analysis.updated_at else ""
    )


@router.delete("/morphological/{analysis_id}")
async def delete_morphological_analysis(
    analysis_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(MorphologicalAnalysis).where(MorphologicalAnalysis.id == analysis_id, MorphologicalAnalysis.user_id == current_user.id)
    result = await db.execute(stmt)
    analysis = result.scalars().first()

    if not analysis:
        raise HTTPException(status_code=404, detail="Morphological analysis not found")

    await db.delete(analysis)
    await db.commit()
    return {"status": "success"}


@router.post("/keywords/generate", response_model=GenerateKeywordsResponse)
async def generate_keywords(
    req: GenerateKeywordsRequest,
    current_user: User = Depends(get_current_user)
):
    try:
        llm = get_llm(model_name=settings.OPENAI_MODEL_MINI)
        structured_llm = llm.with_structured_output(GenerateKeywordsResponse, method="json_schema", strict=True)

        system_prompt = "You are a creative brainstorming assistant. Based on the user's prompt, generate a list of 5-10 concise, highly relevant keywords or short phrases."

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Prompt: {req.prompt}")
        ]

        response = await structured_llm.ainvoke(messages)
        return response
    except Exception as e:
        print(f"Error generating keywords: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate keywords")


@router.post("/keywords/ai-modify", response_model=ModifyKeywordResponse)
async def ai_modify_keyword(
    req: ModifyKeywordRequest,
    current_user: User = Depends(get_current_user)
):
    try:
        llm = get_llm(model_name=settings.OPENAI_MODEL_MINI)

        system_prompt = "You are a creative assistant. You are given a specific keyword and its original context prompt. Suggest a SINGLE new alternative keyword that is similar in intent but distinct. Return ONLY the new keyword."
        user_prompt = f"Original Word: {req.word}\n"
        if req.context_prompt:
            user_prompt += f"Context Prompt: {req.context_prompt}\n"

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]

        response = await llm.ainvoke(messages)
        new_word = response.content.strip()
        new_word = new_word.strip('"').strip("'")

        return ModifyKeywordResponse(new_word=new_word)
    except Exception as e:
        print(f"Error modifying keyword: {e}")
        raise HTTPException(status_code=500, detail="Failed to modify keyword")


@router.get("/keywords", response_model=List[KeywordSchema])
async def get_keywords(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Keyword).where(Keyword.user_id == current_user.id).order_by(Keyword.created_at.desc())
    result = await db.execute(stmt)
    keywords = result.scalars().all()

    resp = []
    for k in keywords:
        resp.append(KeywordSchema(
            id=k.id,
            word=k.word,
            source_prompt=k.source_prompt,
            created_at=k.created_at.isoformat() if k.created_at else ""
        ))
    return resp


@router.post("/keywords", response_model=List[KeywordSchema])
async def save_keywords(
    req: SaveKeywordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    saved = []
    for word in req.words:
        kw = Keyword(
            user_id=current_user.id,
            word=word,
            source_prompt=req.source_prompt
        )
        db.add(kw)
        saved.append(kw)

    await db.commit()
    for kw in saved:
        await db.refresh(kw)

    resp = []
    for k in saved:
        resp.append(KeywordSchema(
            id=k.id,
            word=k.word,
            source_prompt=k.source_prompt,
            created_at=k.created_at.isoformat() if k.created_at else ""
        ))
    return resp


@router.delete("/keywords/{keyword_id}")
async def delete_keyword(
    keyword_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Keyword).where(Keyword.id == keyword_id, Keyword.user_id == current_user.id)
    result = await db.execute(stmt)
    kw = result.scalars().first()

    if not kw:
        raise HTTPException(status_code=404, detail="Keyword not found")

    await db.delete(kw)
    await db.commit()
    return {"status": "success"}
