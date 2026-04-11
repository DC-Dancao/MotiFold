from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update
from typing import List
import json

from app.llm.factory import get_llm
from app.core.database import get_db
from app.auth.models import User
from app.matrix.models import Keyword, MorphologicalAnalysis
from app.core.security import get_current_user
from app.core.config import settings

from langchain_core.messages import SystemMessage, HumanMessage

from app.matrix.schemas import (
    GenerateKeywordsRequest,
    GenerateKeywordsResponse,
    ModifyKeywordRequest,
    ModifyKeywordResponse,
    KeywordSchema,
    SaveKeywordRequest,
    MorphologicalParameter,
    ExtractQuestionRequest,
    ExtractQuestionResponse,
    GenerateMorphologicalRequest,
    GenerateMorphologicalResponse,
    EvaluateConsistencyRequest,
    EvaluateConsistencyResponse,
    SaveMorphologicalRequest,
    MorphologicalAnalysisSchema,
)
from app.matrix.stream import (
    get_redis,
    get_matrix_state,
    get_processing_status,
    subscribe_stream,
)

router = APIRouter(prefix="/matrix", tags=["matrix"])


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
        from app.worker.matrix_tasks import generate_morphological_task
        
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


@router.post("/morphological/evaluate", response_model=EvaluateConsistencyResponse)
async def evaluate_consistency(
    req: EvaluateConsistencyRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        from app.worker.matrix_tasks import evaluate_consistency_task
        
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


@router.get("/morphological/{analysis_id}/stream")
async def stream_morphological_analysis(
    analysis_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    SSE stream of morphological analysis progress events.
    """
    # Verify ownership before streaming
    stmt = select(MorphologicalAnalysis).where(
        MorphologicalAnalysis.id == analysis_id,
        MorphologicalAnalysis.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    analysis = result.scalars().first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    async def event_generator():
        redis = await get_redis()
        pubsub = redis.pubsub()
        await pubsub.subscribe(f"matrix_stream_{analysis_id}")

        is_processing = await get_processing_status(analysis_id)

        # Emit persisted state first so reconnected clients see full progress
        if is_processing:
            redis_state = await get_matrix_state(analysis_id)
            if redis_state:
                yield f"data: {json.dumps({'type': 'rejoin', **redis_state})}\n\n"

        if not is_processing:
            if analysis:
                # Emit current persisted state
                yield f"data: {json.dumps({'type': 'rejoin', 'status': analysis.status, 'parameters': json.loads(analysis.parameters_json), 'matrix': json.loads(analysis.matrix_json)})}\n\n"
                # If already complete, send done
                if analysis.status in ("parameters_ready", "matrix_ready", "evaluate_failed"):
                    yield f"data: {json.dumps({'type': 'done', 'status': analysis.status})}\n\n"
                    yield "data: [DONE]\n\n"
            else:
                yield f"data: {json.dumps({'type': 'status', 'event': 'not_found', 'message': 'Analysis not found'})}\n\n"
                yield "data: [DONE]\n\n"

            await pubsub.unsubscribe(f"matrix_stream_{analysis_id}")
            await pubsub.close()
            return

        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    data = message["data"]
                    # Check for [DONE] event format: {"type": "[DONE]", "parameters": [...], "matrix": {...}, "status": "..."}
                    try:
                        parsed = json.loads(data)
                        if parsed.get("type") == "[DONE]":
                            done_event = {"type": "done"}
                            if parsed.get("parameters"):
                                done_event["parameters"] = parsed["parameters"]
                            if parsed.get("matrix"):
                                done_event["matrix"] = parsed["matrix"]
                            if parsed.get("status"):
                                done_event["status"] = parsed["status"]
                            yield f"data: {json.dumps(done_event)}\n\n"
                            break
                        # Emit original data for other events
                        yield f"data: {data}\n\n"
                    except json.JSONDecodeError:
                        # Plain string "[DONE]" fallback
                        if data == "[DONE]":
                            yield f"data: {json.dumps({'type': 'done'})}\n\n"
                            yield "data: [DONE]\n\n"
                            break
                        yield f"data: {data}\n\n"
        finally:
            await pubsub.unsubscribe(f"matrix_stream_{analysis_id}")
            await pubsub.close()

    return StreamingResponse(event_generator(), media_type="text/event-stream")


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
