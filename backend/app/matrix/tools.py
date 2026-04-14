"""
Tools for interacting with morphological matrix solutions.

These tools allow LLM agents to search, filter, and explore solutions
from morphological analyses using keyword-based filtering.
"""

import json
import logging
from typing import Annotated, List, Optional

from langchain_core.tools import tool
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.llm.factory import get_llm
from app.matrix.models import MorphologicalAnalysis, Keyword
from app.core.database import get_db_with_schema
from app.core.security import get_current_user
from app.org.dependencies import get_current_org_membership
from app.auth.models import User

logger = logging.getLogger(__name__)


# =============================================================================
# Solution Filter Tools
# =============================================================================

SOLUTION_SEARCH_DESCRIPTION = (
    "Search and filter solutions from a morphological analysis using keywords. "
    "Returns solutions that match ANY of the provided keywords (OR logic). "
    "Use this to find solutions that contain specific technologies, approaches, or characteristics. "
    "Returns up to 20 matching solutions with their parameter assignments."
)


@tool(description=SOLUTION_SEARCH_DESCRIPTION)
async def search_solutions_by_keywords(
    analysis_id: Annotated[int, "The ID of the morphological analysis to search"],
    keywords: Annotated[List[str], "Keywords to filter solutions by. Solutions matching ANY keyword are returned."],
    max_results: Annotated[int, "Maximum number of solutions to return"] = 10,
) -> str:
    """
    Search solutions from a morphological analysis by keywords.

    This tool filters solutions based on keyword matching against solution descriptions.
    Each solution is described as a combination of parameter states.

    Args:
        analysis_id: The ID of the morphological analysis
        keywords: List of keywords to search for
        max_results: Maximum number of results to return

    Returns:
        A string describing matching solutions with their parameter assignments
    """
    logger.info(f"--- search_solutions_by_keywords called: analysis_id={analysis_id}, keywords={keywords}")

    try:
        # Get the analysis
        from app.core.database import async_session_maker

        async with async_session_maker() as db:
            stmt = select(MorphologicalAnalysis).where(
                MorphologicalAnalysis.id == analysis_id
            )
            result = await db.execute(stmt)
            analysis = result.scalars().first()

            if not analysis:
                return f"Analysis with ID {analysis_id} not found."

            if analysis.status != "matrix_ready":
                return f"Analysis '{analysis.focus_question}' is not ready. Current status: {analysis.status}. Please wait for matrix evaluation to complete."

            parameters = json.loads(analysis.parameters_json)
            matrix = json.loads(analysis.matrix_json)

            # Enumerate all valid solutions
            solutions, _ = enumerate_solutions_sync(parameters, matrix)

            if not solutions:
                return "No valid solutions found in this analysis."

            # Filter solutions by keywords
            matched_solutions = []
            keywords_lower = [k.lower() for k in keywords]

            for sol_idx, solution in enumerate(solutions):
                # Build solution description
                sol_desc = build_solution_description(parameters, solution)
                sol_desc_lower = sol_desc.lower()

                # Check if any keyword matches
                if any(kw.lower() in sol_desc_lower for kw in keywords_lower):
                    matched_solutions.append({
                        "index": sol_idx,
                        "solution": solution,
                        "description": sol_desc
                    })

            if not matched_solutions:
                return f"No solutions found matching keywords: {', '.join(keywords)}"

            # Limit results
            matched_solutions = matched_solutions[:max_results]

            # Format output
            output = [f"Found {len(matched_solutions)} solution(s) matching keywords: {', '.join(keywords)}\n"]

            for i, sol in enumerate(matched_solutions):
                output.append(f"\n--- Solution {i+1} (Index: {sol['index']}) ---")
                output.append(sol['description'])

            return "\n".join(output)

    except Exception as e:
        logger.error(f"Error searching solutions: {e}")
        return f"Error searching solutions: {str(e)}"


LIST_ANALYSES_DESCRIPTION = (
    "List all morphological analyses belonging to the current user. "
    "Returns analysis IDs, focus questions, and statuses. "
    "Use this to find the analysis_id needed for other tools."
)


@tool(description=LIST_ANALYSES_DESCRIPTION)
async def list_morphological_analyses(
    limit: Annotated[int, "Maximum number of analyses to return"] = 10,
) -> str:
    """
    List all morphological analyses for the current user.

    Returns a summary of available analyses including their IDs,
    focus questions, and statuses.

    Args:
        limit: Maximum number of analyses to return

    Returns:
        A string listing all available morphological analyses
    """
    logger.info("--- list_morphological_analyses called")

    try:
        from app.core.database import async_session_maker

        async with async_session_maker() as db:
            stmt = select(MorphologicalAnalysis).order_by(
                MorphologicalAnalysis.updated_at.desc()
            ).limit(limit)
            result = await db.execute(stmt)
            analyses = result.scalars().all()

            if not analyses:
                return "No morphological analyses found. Create one first using the matrix generation feature."

            output = [f"Found {len(analyses)} morphological analysis/analyses:\n"]

            for a in analyses:
                params = json.loads(a.parameters_json)
                output.append(f"\n--- Analysis {a.id} ---")
                output.append(f"Focus: {a.focus_question}")
                output.append(f"Status: {a.status}")
                output.append(f"Parameters: {len(params)} parameters")

            return "\n".join(output)

    except Exception as e:
        logger.error(f"Error listing analyses: {e}")
        return f"Error listing analyses: {str(e)}"


GET_SOLUTION_DETAILS_DESCRIPTION = (
    "Get detailed information about a specific solution from a morphological analysis. "
    "Returns the full parameter-state assignments for the solution at the given index."
)


@tool(description=GET_SOLUTION_DETAILS_DESCRIPTION)
async def get_solution_details(
    analysis_id: Annotated[int, "The ID of the morphological analysis"],
    solution_index: Annotated[int, "The index of the solution to get details for"],
) -> str:
    """
    Get detailed information about a specific solution.

    Args:
        analysis_id: The ID of the morphological analysis
        solution_index: The index of the solution

    Returns:
        Detailed description of the solution with all parameter assignments
    """
    logger.info(f"--- get_solution_details called: analysis_id={analysis_id}, solution_index={solution_index}")

    try:
        from app.core.database import async_session_maker

        async with async_session_maker() as db:
            stmt = select(MorphologicalAnalysis).where(
                MorphologicalAnalysis.id == analysis_id
            )
            result = await db.execute(stmt)
            analysis = result.scalars().first()

            if not analysis:
                return f"Analysis with ID {analysis_id} not found."

            parameters = json.loads(analysis.parameters_json)
            matrix = json.loads(analysis.matrix_json)

            # Enumerate solutions
            solutions, _ = enumerate_solutions_sync(parameters, matrix)

            if solution_index >= len(solutions):
                return f"Solution index {solution_index} out of range. Total solutions: {len(solutions)}"

            solution = solutions[solution_index]
            sol_desc = build_solution_description(parameters, solution)

            # Get consistency info for this solution
            consistency = check_solution_consistency(parameters, matrix, solution)

            output = [
                f"--- Solution {solution_index} Details ---",
                f"\nFocus Question: {analysis.focus_question}",
                f"\nParameter Assignments:",
                sol_desc,
                f"\nConsistency: {consistency}"
            ]

            return "\n".join(output)

    except Exception as e:
        logger.error(f"Error getting solution details: {e}")
        return f"Error getting solution details: {str(e)}"


GET_SOLUTIONS_BY_CLUSTER_DESCRIPTION = (
    "Get all solutions belonging to a specific cluster in a morphological analysis. "
    "Clusters group similar solutions together. "
    "Use list_clusters first if you need to find cluster IDs."
)


@tool(description=GET_SOLUTIONS_BY_CLUSTER_DESCRIPTION)
async def get_solutions_by_cluster(
    analysis_id: Annotated[int, "The ID of the morphological analysis"],
    cluster_id: Annotated[str, "The cluster ID to filter by"],
    max_results: Annotated[int, "Maximum number of solutions to return"] = 10,
) -> str:
    """
    Get solutions from a specific cluster.

    Args:
        analysis_id: The ID of the morphological analysis
        cluster_id: The cluster ID to filter by
        max_results: Maximum number of solutions to return

    Returns:
        Solutions belonging to the specified cluster
    """
    logger.info(f"--- get_solutions_by_cluster called: analysis_id={analysis_id}, cluster_id={cluster_id}")

    try:
        from app.core.database import async_session_maker

        async with async_session_maker() as db:
            from app.matrix.models import SolutionCluster

            stmt = select(MorphologicalAnalysis).where(
                MorphologicalAnalysis.id == analysis_id
            )
            result = await db.execute(stmt)
            analysis = result.scalars().first()

            if not analysis:
                return f"Analysis with ID {analysis_id} not found."

            # Find the cluster
            cluster_stmt = select(SolutionCluster).where(
                SolutionCluster.analysis_id == analysis_id,
                SolutionCluster.cluster_id == cluster_id
            )
            cluster_result = await db.execute(cluster_stmt)
            cluster = cluster_result.scalars().first()

            if not cluster:
                return f"Cluster '{cluster_id}' not found in analysis {analysis_id}."

            parameters = json.loads(analysis.parameters_json)
            matrix = json.loads(analysis.matrix_json)

            # Enumerate all solutions
            all_solutions, _ = enumerate_solutions_sync(parameters, matrix)

            # Get solutions for this cluster
            solution_indices = cluster.solution_indices[:max_results]
            cluster_solutions = []

            for idx in solution_indices:
                if idx < len(all_solutions):
                    cluster_solutions.append({
                        "index": idx,
                        "description": build_solution_description(parameters, all_solutions[idx])
                    })

            output = [
                f"--- Cluster: {cluster.name} ---",
                f"Description: {cluster.description or 'No description'}",
                f"\nFound {len(cluster_solutions)} solution(s):"
            ]

            for i, sol in enumerate(cluster_solutions):
                output.append(f"\n--- Solution {i+1} (Index: {sol['index']}) ---")
                output.append(sol['description'])

            return "\n".join(output)

    except Exception as e:
        logger.error(f"Error getting cluster solutions: {e}")
        return f"Error getting cluster solutions: {str(e)}"


LIST_CLUSTERS_DESCRIPTION = (
    "List all solution clusters for a morphological analysis. "
    "Clusters are groups of similar solutions created during morphological analysis. "
    "Use this to find available clusters before getting solutions by cluster."
)


@tool(description=LIST_CLUSTERS_DESCRIPTION)
async def list_clusters(
    analysis_id: Annotated[int, "The ID of the morphological analysis"],
) -> str:
    """
    List all clusters for a morphological analysis.

    Args:
        analysis_id: The ID of the morphological analysis

    Returns:
        List of clusters with their IDs, names, and solution counts
    """
    logger.info(f"--- list_clusters called: analysis_id={analysis_id}")

    try:
        from app.core.database import async_session_maker

        async with async_session_maker() as db:
            from app.matrix.models import SolutionCluster

            stmt = select(SolutionCluster).where(
                SolutionCluster.analysis_id == analysis_id
            )
            result = await db.execute(stmt)
            clusters = result.scalars().all()

            if not clusters:
                return f"No clusters found for analysis {analysis_id}. Run clustering first."

            output = [f"Found {len(clusters)} cluster(s):\n"]

            for c in clusters:
                output.append(f"\n--- Cluster: {c.cluster_id} ---")
                output.append(f"Name: {c.name}")
                if c.description:
                    output.append(f"Description: {c.description}")
                output.append(f"Solutions: {len(c.solution_indices)}")

            return "\n".join(output)

    except Exception as e:
        logger.error(f"Error listing clusters: {e}")
        return f"Error listing clusters: {str(e)}"


# =============================================================================
# Helper Functions
# =============================================================================

def enumerate_solutions_sync(
    parameters: list,
    matrix_data: dict,
    max_yellows: int = 2
) -> tuple:
    """Synchronous version of solution enumeration for use in tools."""
    valid_solutions = []
    total_iterations = 0

    def dfs(current_path, current_yellows):
        nonlocal total_iterations
        if total_iterations > 1000000:
            return

        p_idx = len(current_path)
        if p_idx == len(parameters):
            valid_solutions.append(current_path.copy())
            return

        for s_idx in range(len(parameters[p_idx]["states"])):
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


def build_solution_description(parameters: list, solution: list) -> str:
    """Build a human-readable description of a solution."""
    parts = []
    for p_idx, s_idx in enumerate(solution):
        if p_idx < len(parameters) and s_idx < len(parameters[p_idx]["states"]):
            param_name = parameters[p_idx]["name"]
            state = parameters[p_idx]["states"][s_idx]
            parts.append(f"{param_name}={state}")
    return ", ".join(parts)


def check_solution_consistency(parameters: list, matrix: dict, solution: list) -> str:
    """Check the consistency status of a solution."""
    yellow_count = 0
    green_count = 0

    for p1_idx in range(len(solution)):
        for p2_idx in range(p1_idx + 1, len(solution)):
            pair_key = f"{p1_idx}_{p2_idx}"
            s1, s2 = solution[p1_idx], solution[p2_idx]
            cell = matrix.get(pair_key, {}).get(f"{s1}_{s2}", {})
            status = cell.get("status", "green")
            if status == "yellow":
                yellow_count += 1
            elif status == "green":
                green_count += 1

    return f"{green_count} green, {yellow_count} yellow"


# =============================================================================
# Tool List for Agent Binding
# =============================================================================

SOLUTION_TOOLS = [
    search_solutions_by_keywords,
    list_morphological_analyses,
    get_solution_details,
    get_solutions_by_cluster,
    list_clusters,
]
