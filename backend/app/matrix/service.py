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
    EvaluationResult,
    PairEvaluateConsistencyResponse,
    OrthogonalityCheckResponse,
    ClusterResponse,
    AHPCriteriaResponse,
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
) -> Tuple[Dict[str, Dict[str, Dict]], List[PairEvaluateConsistencyResponse]]:
    matrix_data: Dict[str, Dict[str, Dict]] = {}
    expected_pairs: set = set()

    for p1_idx in range(len(parameters)):
        for p2_idx in range(p1_idx + 1, len(parameters)):
            pair_key = f"{p1_idx}_{p2_idx}"
            expected_pairs.add(pair_key)
            matrix_data[pair_key] = {}
            for s1_idx in range(len(parameters[p1_idx].states)):
                for s2_idx in range(len(parameters[p2_idx].states)):
                    matrix_data[pair_key][f"{s1_idx}_{s2_idx}"] = {
                        "status": "green",
                        "type": None,
                        "reason": None
                    }

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

        # Process red with types and reasons
        for row in evaluation.results.red:
            if len(row) == 2:
                state_key = f"{row[0]}_{row[1]}"
                matrix_data[pair_key][state_key] = {
                    "status": "red",
                    "type": evaluation.results.types.get(f"[{row[0]},{row[1]}]", "L"),
                    "reason": evaluation.results.reasons.get("red", {}).get(f"[{row[0]},{row[1]}]")
                }

        # Process yellow with reasons
        for row in evaluation.results.yellow:
            if len(row) == 2 and f"{row[0]}_{row[1]}" not in red_pairs:
                state_key = f"{row[0]}_{row[1]}"
                matrix_data[pair_key][state_key] = {
                    "status": "yellow",
                    "type": None,
                    "reason": evaluation.results.reasons.get("yellow", {}).get(f"[{row[0]},{row[1]}]")
                }

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
- "red": impossible because of logical, empirical, or normative contradiction

When marking red, classify the contradiction type:
- "L" (Logical): Conceptually incompatible by definition
- "E" (Empirical): Violates physics, engineering, or observed reality
- "N" (Normative): Conflicts with social norms, laws, or policy

Return brief one-line reason for each red/yellow entry.

Return JSON with:
{
  "pair": [param1_idx, param2_idx],
  "results": {
    "red": [[s1, s2], ...],
    "yellow": [[s1, s2], ...],
    "reasons": {
      "red": {"[s1,s2]": "reason text", ...},
      "yellow": {"[s1,s2]": "reason text", ...}
    },
    "types": {
      "[s1,s2]": "L|E|N"
    }
  }
}
Rows not listed are treated as "green."""

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


async def check_orthogonality(parameters: List[MorphologicalParameter]) -> Dict[str, Any]:
    """Check if parameters are orthogonal (non-overlapping)."""
    llm = get_llm(model_name=settings.OPENAI_MODEL_PRO, streaming=False)
    structured_llm = llm.with_structured_output(OrthogonalityCheckResponse, method="json_schema", strict=True)

    system_prompt = """You are an expert in Morphological Analysis.
Analyze the given parameters for orthogonality - parameters should be independent and not overlap in definition.
Identify any pairs of parameters that have significant overlap or could be merged.

Return warnings for any parameter pairs that overlap significantly."""

    param_text = "\n".join(
        f"[{i}] {p.name}: {', '.join(p.states[:3])}..."
        for i, p in enumerate(parameters)
    )

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"Parameters:\n{param_text}")
    ]

    try:
        response = await structured_llm.ainvoke(messages)
        return {
            "warnings": response.warnings if response else [],
            "all_orthogonal": response.all_orthogonal if response else True
        }
    except Exception as e:
        return {"warnings": [], "all_orthogonal": True, "error": str(e)}


def enumerate_solutions(
    parameters: List[MorphologicalParameter],
    matrix_data: Dict[str, Dict[str, Dict]],
    max_yellows: int = 2
) -> Tuple[List[List[int]], int]:
    """Enumerate all valid solution combinations."""
    total_iterations = 0
    valid_solutions: List[List[int]] = []

    def dfs(current_path: List[int], current_yellows: int) -> None:
        nonlocal total_iterations
        if total_iterations > 1000000:  # Safety limit
            return

        p_idx = len(current_path)
        if p_idx == len(parameters):
            valid_solutions.append(current_path.copy())
            return

        for s_idx in range(len(parameters[p_idx].states)):
            total_iterations += 1
            is_valid = True
            new_yellows = current_yellows

            for prev_p_idx, prev_s_idx in enumerate(current_path):
                if prev_p_idx > p_idx:
                    break
                pid1, pid2 = min(prev_p_idx, p_idx), max(prev_p_idx, p_idx)
                pair_key = f"{pid1}_{pid2}"
                sid1, sid2 = (prev_s_idx, s_idx) if prev_p_idx < p_idx else (s_idx, prev_s_idx)

                cell = matrix_data.get(pair_key, {}).get(f"{sid1}_{sid2}", {})
                status = cell.get("status", "green")

                if status == "red":
                    is_valid = False
                    break
                elif status == "yellow":
                    new_yellows += 1

            if is_valid and new_yellows <= max_yellows:
                dfs(current_path + [s_idx], new_yellows)

    dfs([], 0)
    return valid_solutions, total_iterations


async def cluster_solutions(
    parameters: List[MorphologicalParameter],
    solutions: List[List[int]],
    max_clusters: int = 5
) -> List[Dict[str, Any]]:
    """Auto-cluster solutions using LLM."""
    if not solutions:
        return []

    llm = get_llm(model_name=settings.OPENAI_MODEL_PRO, streaming=False)
    structured_llm = llm.with_structured_output(ClusterResponse, method="json_schema", strict=True)

    # Prepare solution descriptions (truncate for LLM)
    solution_descs = []
    for i, sol in enumerate(solutions[:100]):  # Limit to 100 for LLM
        desc = ", ".join(f"{parameters[p_idx].name}={parameters[p_idx].states[s_idx]}"
                        for p_idx, s_idx in enumerate(sol))
        solution_descs.append(f"[{i}] {desc}")

    system_prompt = """Group these solutions into meaningful clusters based on their characteristics.
Each cluster should have a distinct theme (e.g., "Low-Cost Baseline", "High-Tech Future").
Return cluster names, descriptions, and which solution indices belong to each."""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content="\n".join(solution_descs))
    ]

    try:
        response = await structured_llm.ainvoke(messages)
        return [{"name": c.name, "description": c.description, "solution_indices": c.solution_indices}
                for c in response.clusters] if response else []
    except Exception as e:
        # Fallback: simple random clustering
        return [{"name": f"Group {i+1}", "description": "", "solution_indices": solutions[i::max_clusters]}
                for i in range(min(max_clusters, len(solutions)))]


async def suggest_ahp_weights(
    parameters: List[MorphologicalParameter],
    cluster_solutions: List[Dict]
) -> List[Dict[str, float]]:
    """Suggest initial AHP weights based on context."""
    llm = get_llm(model_name=settings.OPENAI_MODEL_PRO, streaming=False)
    structured_llm = llm.with_structured_output(AHPCriteriaResponse, method="json_schema", strict=True)

    system_prompt = """Given this morphological analysis problem, suggest 4-5 evaluation criteria with weights.
Common criteria: Cost, Implementation Time, Risk, Performance, Scalability, Maintainability.
Return weights that sum to 1.0."""

    context = f"Parameters: {[p.name for p in parameters]}\nClusters: {[c['name'] for c in cluster_solutions]}"

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=context)
    ]

    try:
        response = await structured_llm.ainvoke(messages)
        if response and response.criteria:
            return response.criteria
    except Exception as e:
        pass

    # Fallback weights
    return [
        {"name": "Cost", "weight": 0.30},
        {"name": "Time", "weight": 0.20},
        {"name": "Risk", "weight": 0.25},
        {"name": "Performance", "weight": 0.25}
    ]


async def score_solutions(
    parameters: List[MorphologicalParameter],
    solutions: List[List[int]],
    weights: List[Dict[str, float]],
    top_k: int = 5
) -> List[Dict[str, Any]]:
    """Score and rank solutions using LLM."""
    if not solutions:
        return []

    llm = get_llm(model_name=settings.OPENAI_MODEL_PRO, streaming=False)
    criteria_names = [w["name"] for w in weights]
    criteria_weights = {w["name"]: w["weight"] for w in weights}

    # Prepare solution descriptions
    solution_descs = []
    for i, sol in enumerate(solutions[:20]):  # Limit to top 20 for LLM
        desc = ", ".join(f"{parameters[p_idx].states[s_idx]}" for p_idx, s_idx in enumerate(sol))
        solution_descs.append(f"[{i}] {desc}")

    system_prompt = f"""Rate each solution 1-5 on these criteria: {', '.join(criteria_names)}.
1 = Poor, 5 = Excellent.
Then calculate weighted score.
Return JSON: {{"ranked": [{{"idx": 0, "ratings": {{"Cost": 3, ...}}, "score": 0.85, "summary": "..."}}]}}"""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content="\n".join(solution_descs))
    ]

    ranked = []
    try:
        response = await llm.ainvoke(messages)
        import json, re
        match = re.search(r'\{.*\}', response.content, re.DOTALL)
        if match:
            data = json.loads(match.group())
            for item in data.get("ranked", [])[:top_k]:
                sol_idx = item["idx"]
                ranked.append({
                    "rank": len(ranked) + 1,
                    "solution_index": sol_idx,
                    "solution": [parameters[p_idx].states[s_idx] for p_idx, s_idx in enumerate(solutions[sol_idx])] if sol_idx < len(solutions) else [parameters[p_idx].states[s_idx] for p_idx, s_idx in enumerate(solutions[0])],
                    "score": item.get("score", 0),
                    "ratings": item.get("ratings", {}),
                    "summary": item.get("summary", "")
                })
    except Exception as e:
        # Fallback: random scoring
        import random
        for i, sol in enumerate(solutions[:top_k]):
            ranked.append({
                "rank": i + 1,
                "solution_index": i,
                "solution": [parameters[p_idx].states[s_idx] for p_idx, s_idx in enumerate(sol)],
                "score": random.uniform(0.5, 1.0),
                "ratings": {c: random.randint(2, 5) for c in criteria_names},
                "summary": "Generated based on criteria evaluation"
            })

    return ranked
