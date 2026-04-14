"""
Unit tests for app.matrix.tools module.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import json

from app.matrix.tools import (
    search_solutions_by_keywords,
    list_morphological_analyses,
    get_solution_details,
    get_solutions_by_cluster,
    list_clusters,
    enumerate_solutions_sync,
    build_solution_description,
    check_solution_consistency,
    SOLUTION_TOOLS,
)

pytestmark = [pytest.mark.unit]


class TestSolutionToolsExist:
    """Tests that all expected tools are defined."""

    def test_solution_tools_list_exists(self):
        """Should have SOLUTION_TOOLS list."""
        assert SOLUTION_TOOLS is not None
        assert isinstance(SOLUTION_TOOLS, list)

    def test_all_expected_tools_present(self):
        """Should have all expected tools."""
        tool_names = [t.name for t in SOLUTION_TOOLS]
        assert "search_solutions_by_keywords" in tool_names
        assert "list_morphological_analyses" in tool_names
        assert "get_solution_details" in tool_names
        assert "get_solutions_by_cluster" in tool_names
        assert "list_clusters" in tool_names


class TestEnumerateSolutionsSync:
    """Tests for enumerate_solutions_sync helper function."""

    def test_empty_parameters(self):
        """Should return single empty solution for no parameters."""
        solutions, iterations = enumerate_solutions_sync([], {})
        assert solutions == [[]]
        assert iterations == 0

    def test_two_parameters_all_green(self):
        """Should return all combinations when all green."""
        parameters = [
            {"name": "Power", "states": ["Battery", "Solar"]},
            {"name": "Speed", "states": ["Fast", "Slow"]}
        ]
        matrix = {
            "0_1": {
                "0_0": {"status": "green"},
                "0_1": {"status": "green"},
                "1_0": {"status": "green"},
                "1_1": {"status": "green"},
            }
        }
        solutions, iterations = enumerate_solutions_sync(parameters, matrix)
        assert len(solutions) == 4

    def test_red_cells_filter_solutions(self):
        """Should exclude solutions with red cells."""
        parameters = [
            {"name": "Power", "states": ["Battery", "Solar"]},
            {"name": "Speed", "states": ["Fast", "Slow"]}
        ]
        matrix = {
            "0_1": {
                "0_0": {"status": "red"},
                "0_1": {"status": "green"},
                "1_0": {"status": "green"},
                "1_1": {"status": "green"},
            }
        }
        solutions, iterations = enumerate_solutions_sync(parameters, matrix)
        assert [0, 0] not in solutions  # Rejected due to red
        assert [0, 1] in solutions
        assert [1, 0] in solutions
        assert [1, 1] in solutions


class TestBuildSolutionDescription:
    """Tests for build_solution_description helper."""

    def test_empty_solution(self):
        """Should handle empty solution."""
        result = build_solution_description([], [])
        assert result == ""

    def test_single_parameter(self):
        """Should format single parameter correctly."""
        parameters = [
            {"name": "Power", "states": ["Battery", "Solar"]}
        ]
        result = build_solution_description(parameters, [0])
        assert "Power=Battery" in result

    def test_multiple_parameters(self):
        """Should format multiple parameters correctly."""
        parameters = [
            {"name": "Power", "states": ["Battery", "Solar"]},
            {"name": "Speed", "states": ["Fast", "Slow"]}
        ]
        result = build_solution_description(parameters, [0, 1])
        assert "Power=Battery" in result
        assert "Speed=Slow" in result


class TestCheckSolutionConsistency:
    """Tests for check_solution_consistency helper."""

    def test_all_green(self):
        """Should report all green."""
        parameters = [
            {"name": "Power", "states": ["Battery", "Solar"]},
            {"name": "Speed", "states": ["Fast", "Slow"]}
        ]
        matrix = {
            "0_1": {
                "0_0": {"status": "green"},
                "0_1": {"status": "green"},
                "1_0": {"status": "green"},
                "1_1": {"status": "green"},
            }
        }
        result = check_solution_consistency(parameters, matrix, [0, 0])
        assert "1 green" in result
        assert "0 yellow" in result

    def test_with_yellow(self):
        """Should count yellow cells."""
        parameters = [
            {"name": "Power", "states": ["Battery", "Solar"]},
            {"name": "Speed", "states": ["Fast", "Slow"]}
        ]
        matrix = {
            "0_1": {
                "0_0": {"status": "yellow"},
                "0_1": {"status": "green"},
                "1_0": {"status": "green"},
                "1_1": {"status": "green"},
            }
        }
        result = check_solution_consistency(parameters, matrix, [0, 0])
        assert "0 green" in result
        assert "1 yellow" in result


class TestSearchSolutionsByKeywordsTool:
    """Tests for search_solutions_by_keywords tool."""

    @pytest.mark.asyncio
    async def test_analysis_not_found(self):
        """Should handle analysis not found."""
        with patch("app.matrix.tools.async_session_maker") as mock_session_maker:
            mock_db = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalars.return_value.first.return_value = None
            mock_db.execute.return_value = mock_result

            async_cm = AsyncMock()
            async_cm.__aenter__.return_value = mock_db
            async_cm.__aexit__.return_value = None
            mock_session_maker.return_value = async_cm

            result = await search_solutions_by_keywords.ainvoke({
                "analysis_id": 999,
                "keywords": ["test"]
            })

            assert "not found" in result.lower()

    @pytest.mark.asyncio
    async def test_analysis_not_ready(self):
        """Should handle analysis not ready."""
        with patch("app.matrix.tools.async_session_maker") as mock_session_maker:
            mock_db = AsyncMock()
            mock_analysis = MagicMock()
            mock_analysis.status = "generating_parameters"
            mock_analysis.focus_question = "Test"

            mock_result = MagicMock()
            mock_result.scalars.return_value.first.return_value = mock_analysis
            mock_db.execute.return_value = mock_result

            async_cm = AsyncMock()
            async_cm.__aenter__.return_value = mock_db
            async_cm.__aexit__.return_value = None
            mock_session_maker.return_value = async_cm

            result = await search_solutions_by_keywords.ainvoke({
                "analysis_id": 1,
                "keywords": ["test"]
            })

            assert "not ready" in result.lower()


class TestListMorphologicalAnalysesTool:
    """Tests for list_morphological_analyses tool."""

    @pytest.mark.asyncio
    async def test_no_analyses(self):
        """Should handle no analyses found."""
        with patch("app.matrix.tools.async_session_maker") as mock_session_maker:
            mock_db = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = []
            mock_db.execute.return_value = mock_result

            async_cm = AsyncMock()
            async_cm.__aenter__.return_value = mock_db
            async_cm.__aexit__.return_value = None
            mock_session_maker.return_value = async_cm

            result = await list_morphological_analyses.ainvoke({})

            assert "no morphological analyses" in result.lower() or "found 0" in result.lower()

    @pytest.mark.asyncio
    async def test_returns_analyses(self):
        """Should return analyses when found."""
        with patch("app.matrix.tools.async_session_maker") as mock_session_maker:
            mock_db = AsyncMock()
            mock_analysis = MagicMock()
            mock_analysis.id = 1
            mock_analysis.focus_question = "How to build a robot?"
            mock_analysis.status = "matrix_ready"
            mock_analysis.parameters_json = json.dumps([
                {"name": "Power", "states": ["Battery"]}
            ])
            mock_analysis.updated_at = None

            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = [mock_analysis]
            mock_db.execute.return_value = mock_result

            async_cm = AsyncMock()
            async_cm.__aenter__.return_value = mock_db
            async_cm.__aexit__.return_value = None
            mock_session_maker.return_value = async_cm

            result = await list_morphological_analyses.ainvoke({})

            assert "1" in result
            assert "robot" in result.lower()


class TestGetSolutionDetailsTool:
    """Tests for get_solution_details tool."""

    @pytest.mark.asyncio
    async def test_analysis_not_found(self):
        """Should handle analysis not found."""
        with patch("app.matrix.tools.async_session_maker") as mock_session_maker:
            mock_db = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalars.return_value.first.return_value = None
            mock_db.execute.return_value = mock_result

            async_cm = AsyncMock()
            async_cm.__aenter__.return_value = mock_db
            async_cm.__aexit__.return_value = None
            mock_session_maker.return_value = async_cm

            result = await get_solution_details.ainvoke({
                "analysis_id": 999,
                "solution_index": 0
            })

            assert "not found" in result.lower()


class TestListClustersTool:
    """Tests for list_clusters tool."""

    @pytest.mark.asyncio
    async def test_no_clusters(self):
        """Should handle no clusters found."""
        with patch("app.matrix.tools.async_session_maker") as mock_session_maker:
            mock_db = AsyncMock()
            mock_analysis = MagicMock()
            mock_analysis.id = 1

            # Mock the select and execute for analysis query
            mock_result = MagicMock()
            mock_result.scalars.return_value.first.return_value = mock_analysis
            mock_db.execute.return_value = mock_result

            async_cm = AsyncMock()
            async_cm.__aenter__.return_value = mock_db
            async_cm.__aexit__.return_value = None
            mock_session_maker.return_value = async_cm

            result = await list_clusters.ainvoke({"analysis_id": 1})

            assert "no clusters" in result.lower() or "not found" in result.lower()
