import json
from typing import List, Dict, Tuple, Any
from pydantic import ValidationError
from langchain_core.messages import SystemMessage, HumanMessage

from app.llm import get_llm
from app.config import settings
from app.routers.matrix_router import (
    LLMGenerateMorphologicalResponse,
    GenerateMorphologicalResponse,
    MorphologicalParameter,
    normalize_morphological_response,
    BatchEvaluateConsistencyResponse,
    EvaluateConsistencyResponse,
    build_consistency_table,
    apply_consistency_results,
    PairEvaluateConsistencyResponse
)

async def generate_morphological_parameters(focus_question: str) -> GenerateMorphologicalResponse:
    llm = get_llm(model_name=settings.OPENAI_MODEL_PRO, streaming=True)
    structured_llm = llm.with_structured_output(LLMGenerateMorphologicalResponse, method="json_schema", strict=True)

    system_prompt = """You are an expert in Morphological Analysis.
Based on the user's focus question, extract key parameters (dimensions) and their possible states.
Follow the '7x7 rule' strictly:
- generate exactly 7 parameters
- generate exactly 7 distinct states for each parameter
- keep only the most decision-relevant parameters and states
- remove duplicates, synonyms, empty items, and overlapping dimensions
Parameters should be orthogonal (independent of each other).
Ensure exactly 7 parameters and exactly 7 states per parameter."""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=(
            f"Focus Question: {focus_question}\n"
            "Return exactly 7 parameters. Each parameter must include exactly 7 states."
        ))
    ]

    last_error = None
    for attempt in range(3):
        try:
            response = await structured_llm.ainvoke(messages)
            if response is None:
                raise ValueError("LLM returned None instead of the expected structured output schema. Please use the appropriate schema format.")
            
            return normalize_morphological_response(response)
        except (ValidationError, ValueError) as e:
            last_error = e
            if attempt < 2:
                messages.append(HumanMessage(
                    content=f"Validation failed on previous attempt: {e}. "
                            "Please fix the errors and try again. Ensure you return exactly 7 orthogonal parameters, each with exactly 7 distinct states."
                ))

    raise ValueError(f"Failed to generate valid morphological parameters: {last_error}")

async def evaluate_morphological_consistency(parameters: List[MorphologicalParameter]) -> Dict[str, Any]:
    llm = get_llm(model_name=settings.OPENAI_MODEL_PRO, streaming=True)
    structured_llm = llm.with_structured_output(BatchEvaluateConsistencyResponse, method="json_schema", strict=True)
    comparison_table, pair_order = build_consistency_table(parameters)

    system_prompt = """You are an expert in Cross-Consistency Assessment for Morphological Analysis.
Evaluate all pairwise state combinations in the provided indexed comparison table.
There are 3 levels of compatibility:
- "green": completely compatible
- "yellow": possibly compatible under certain conditions
- "red": impossible because of logical, empirical, or normative contradiction, OR it is not plausible in normal engineering practice.

You must evaluate every parameter pair in the table and return one item per pair.
Rows not listed in "red" or "yellow" are treated as "green".
If a combination is slightly unreasonable or not plausible in conventional engineering, you MUST strictly classify it as "red". Do not imagine extreme conditions to justify it.
Each pair item must use the parameter indexes shown in the table, and each state entry must use [state_1_index, state_2_index].
Do not include markdown or any explanation outside the structured response."""

    user_prompt = "Parameters:\n"
    for p_idx, parameter in enumerate(parameters):
        user_prompt += f"[{p_idx}] {parameter.name}: "
        user_prompt += ", ".join(f"({s_idx}) {state}" for s_idx, state in enumerate(parameter.states))
        user_prompt += "\n"

    user_prompt += "\nIndexed comparison table:\n"
    user_prompt += comparison_table
    user_prompt += "\n\nReturn one evaluation item for each pair in this order:\n"
    user_prompt += "\n".join(f"[{p1_idx}, {p2_idx}]" for p1_idx, p2_idx in pair_order)

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt)
    ]

    last_error = None
    for attempt in range(3):
        try:
            response = await structured_llm.ainvoke(messages)
            if response is None:
                raise ValueError("LLM returned None instead of the expected structured output schema. Please use the appropriate schema format.")
            
            matrix_data, normalized_results = apply_consistency_results(parameters, response)
            return {
                "matrix": matrix_data,
                "results_list": normalized_results
            }
        except Exception as e:
            last_error = e
            if attempt < 2:
                messages.append(SystemMessage(
                    content=f"Validation failed on previous attempt: {str(e)}. "
                            "Please carefully review the requirement and retry, ensuring you return valid data following the provided schema."
                ))

    raise ValueError(f"Failed to evaluate consistency after {3} attempts. Last error: {last_error}")
