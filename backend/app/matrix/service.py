import json
from typing import List, Dict, Tuple, Any
from pydantic import ValidationError
from langchain_core.messages import SystemMessage, HumanMessage

from app.llm.factory import get_llm
from app.core.config import settings
from app.matrix.schemas import (
    LLMGenerateMorphologicalResponse,
    GenerateMorphologicalLLMResponse,
    MorphologicalParameter,
    normalize_morphological_response,
    BatchEvaluateConsistencyResponse,
    EvaluateConsistencyResponse,
    PairEvaluateConsistencyResponse,
)


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


async def generate_morphological_parameters(focus_question: str) -> GenerateMorphologicalLLMResponse:
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
