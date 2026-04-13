"""
Unit tests for app.matrix.service — business logic.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from types import SimpleNamespace

from app.matrix import service as matrix_service
from app.matrix.schemas import (
    BatchEvaluateConsistencyResponse,
    MorphologicalParameter,
    PairEvaluateConsistencyResponse,
    EvaluationResult,
    LLMGenerateMorphologicalResponse,
    OrthogonalityCheckResponse,
    ClusterResponse,
    AHPCriteriaResponse,
)

pytestmark = [pytest.mark.unit]


def build_test_parameters():
    return [
        MorphologicalParameter(name="Power", states=["Battery", "Solar", "Fuel", "Grid", "Wind", "Hydrogen", "Hybrid"]),
        MorphologicalParameter(name="Environment", states=["Underwater", "Urban", "Desert", "Arctic", "Forest", "Coastal", "Orbital"]),
        MorphologicalParameter(name="Speed", states=["Stopped", "Slow", "Cruise", "Fast", "Sprint", "Dash", "Burst"]),
    ]


class TestBuildConsistencyTable:
    """Tests for build_consistency_table."""

    def test_empty_parameters(self):
        """Should handle empty parameter list."""
        table, pair_order = matrix_service.build_consistency_table([])
        assert pair_order == []
        assert table == ""

    def test_single_parameter(self):
        """Should handle single parameter (no pairs)."""
        params = [MorphologicalParameter(name="Power", states=["Battery", "Solar"])]
        table, pair_order = matrix_service.build_consistency_table(params)
        assert pair_order == []

    def test_two_parameters(self):
        """Should create one pair for two parameters."""
        params = [
            MorphologicalParameter(name="Power", states=["Battery", "Solar"]),
            MorphologicalParameter(name="Speed", states=["Slow", "Fast"])
        ]
        table, pair_order = matrix_service.build_consistency_table(params)
        assert pair_order == [(0, 1)]
        assert "Pair [0, 1]" in table
        assert "Parameter 0: Power" in table
        assert "Parameter 1: Speed" in table

    def test_indexed_rows_for_pair(self):
        """Should include indexed comparison rows."""
        params = [
            MorphologicalParameter(name="Power", states=["Battery", "Solar"]),
            MorphologicalParameter(name="Speed", states=["Slow", "Fast"])
        ]
        table, pair_order = matrix_service.build_consistency_table(params)
        # 2x2 = 4 combinations
        assert "[0] [0, 0] (Battery) vs (Slow)" in table
        assert "[1] [0, 1] (Battery) vs (Fast)" in table
        assert "[2] [1, 0] (Solar) vs (Slow)" in table
        assert "[3] [1, 1] (Solar) vs (Fast)" in table


class TestBuildDefaultMatrix:
    """Tests for build_default_matrix."""

    def test_empty_parameters(self):
        """Should return empty matrix for no parameters."""
        matrix = matrix_service.build_default_matrix([])
        assert matrix == {}

    def test_single_parameter(self):
        """Should return empty matrix for single parameter (no pairs)."""
        params = [MorphologicalParameter(name="Power", states=["Battery", "Solar"])]
        matrix = matrix_service.build_default_matrix(params)
        assert matrix == {}

    def test_two_parameters(self):
        """Should create all green cells for two parameters."""
        params = [
            MorphologicalParameter(name="Power", states=["Battery", "Solar"]),
            MorphologicalParameter(name="Speed", states=["Slow", "Fast"])
        ]
        matrix = matrix_service.build_default_matrix(params)
        assert "0_1" in matrix
        assert matrix["0_1"]["0_0"] == "green"
        assert matrix["0_1"]["0_1"] == "green"
        assert matrix["0_1"]["1_0"] == "green"
        assert matrix["0_1"]["1_1"] == "green"

    def test_three_parameters(self):
        """Should create matrices for all pairs."""
        params = build_test_parameters()
        matrix = matrix_service.build_default_matrix(params)
        assert "0_1" in matrix
        assert "0_2" in matrix
        assert "1_2" in matrix
        # 3 params x 3 params = 3 pairs, each 7x7 = 49 cells


class TestApplyConsistencyResults:
    """Tests for apply_consistency_results."""

    def test_valid_response_maps_red(self):
        """Should map red status correctly."""
        parameters = build_test_parameters()
        response = BatchEvaluateConsistencyResponse(
            evaluations=[
                PairEvaluateConsistencyResponse(
                    pair=[0, 1],
                    results=EvaluationResult(
                        red=[[0, 0], [1, 1]],
                        yellow=[],
                        reasons={"red": {"[0,0]": "r1", "[1,1]": "r2"}, "yellow": {}},
                        types={"[0,0]": "L", "[1,1]": "E"}
                    ),
                ),
                PairEvaluateConsistencyResponse(
                    pair=[0, 2],
                    results=EvaluationResult(
                        red=[],
                        yellow=[[0, 1]],
                        reasons={"red": {}, "yellow": {"[0,1]": "y1"}},
                        types={}
                    ),
                ),
                PairEvaluateConsistencyResponse(
                    pair=[1, 2],
                    results=EvaluationResult(
                        red=[],
                        yellow=[],
                        reasons={"red": {}, "yellow": {}},
                        types={}
                    ),
                ),
            ]
        )

        matrix, results = matrix_service.apply_consistency_results(parameters, response)

        # Check red cells
        assert matrix["0_1"]["0_0"]["status"] == "red"
        assert matrix["0_1"]["0_0"]["type"] == "L"
        assert matrix["0_1"]["0_0"]["reason"] == "r1"
        assert matrix["0_1"]["1_1"]["status"] == "red"
        assert matrix["0_1"]["1_1"]["type"] == "E"

        # Check yellow cell
        assert matrix["0_2"]["0_1"]["status"] == "yellow"
        assert matrix["0_2"]["0_1"]["reason"] == "y1"

        # Check green cell (not in red or yellow)
        assert matrix["0_1"]["0_1"]["status"] == "green"

    def test_invalid_pair_length_raises(self):
        """Should raise ValueError for invalid pair length."""
        parameters = build_test_parameters()
        response = BatchEvaluateConsistencyResponse(
            evaluations=[
                PairEvaluateConsistencyResponse(
                    pair=[0],  # Invalid - should be [p1, p2]
                    results=EvaluationResult(red=[], yellow=[]),
                ),
            ]
        )

        with pytest.raises(ValueError, match="Invalid pair identifier"):
            matrix_service.apply_consistency_results(parameters, response)

    def test_unexpected_pair_raises(self):
        """Should raise ValueError for unexpected pair."""
        parameters = build_test_parameters()
        response = BatchEvaluateConsistencyResponse(
            evaluations=[
                PairEvaluateConsistencyResponse(
                    pair=[0, 5],  # Parameter 5 doesn't exist
                    results=EvaluationResult(red=[], yellow=[]),
                ),
            ]
        )

        with pytest.raises(ValueError, match="Unexpected pair"):
            matrix_service.apply_consistency_results(parameters, response)

    def test_missing_pairs_raises(self):
        """Should raise ValueError when response is missing pairs."""
        parameters = build_test_parameters()  # 3 params = 3 pairs
        response = BatchEvaluateConsistencyResponse(
            evaluations=[
                PairEvaluateConsistencyResponse(
                    pair=[0, 1],
                    results=EvaluationResult(red=[], yellow=[]),
                ),
                # Missing [0, 2] and [1, 2]
            ]
        )

        with pytest.raises(ValueError, match="missing pair evaluations"):
            matrix_service.apply_consistency_results(parameters, response)

    def test_red_yellow_overlap_yellow_ignored(self):
        """When a cell is red, yellow entry for same cell should be ignored."""
        parameters = build_test_parameters()
        response = BatchEvaluateConsistencyResponse(
            evaluations=[
                PairEvaluateConsistencyResponse(
                    pair=[0, 1],
                    results=EvaluationResult(
                        red=[[0, 0]],
                        yellow=[[0, 0], [1, 1]],  # 0,0 is also in red
                        reasons={"red": {"[0,0]": "r1"}, "yellow": {"[0,0]": "y1", "[1,1]": "y2"}},
                        types={"[0,0]": "L"}
                    ),
                ),
                PairEvaluateConsistencyResponse(
                    pair=[0, 2],
                    results=EvaluationResult(red=[], yellow=[], reasons={"red": {}, "yellow": {}}, types={}),
                ),
                PairEvaluateConsistencyResponse(
                    pair=[1, 2],
                    results=EvaluationResult(red=[], yellow=[], reasons={"red": {}, "yellow": {}}, types={}),
                ),
            ]
        )

        matrix, _ = matrix_service.apply_consistency_results(parameters, response)

        # 0,0 should be red, not yellow
        assert matrix["0_1"]["0_0"]["status"] == "red"
        # 1,1 should be yellow (only in yellow list)
        assert matrix["0_1"]["1_1"]["status"] == "yellow"


class TestEnumerateSolutions:
    """Tests for enumerate_solutions."""

    def test_empty_parameters(self):
        """Should return single empty solution when no parameters."""
        solutions, iterations = matrix_service.enumerate_solutions([], {})
        # Single solution representing no parameters
        assert solutions == [[]]
        assert iterations == 0

    def test_single_parameter(self):
        """Should return all states for single parameter as single-element lists."""
        params = [MorphologicalParameter(name="Power", states=["A", "B", "C"])]
        matrix = {}
        solutions, iterations = matrix_service.enumerate_solutions(params, matrix)
        assert len(solutions) == 3
        assert [0] in solutions
        assert [1] in solutions
        assert [2] in solutions

    def test_all_green_matrix(self):
        """Should return all combinations when all cells are green."""
        params = [
            MorphologicalParameter(name="P1", states=["A", "B"]),
            MorphologicalParameter(name="P2", states=["X", "Y"])
        ]
        matrix = {"0_1": {
            "0_0": {"status": "green"},
            "0_1": {"status": "green"},
            "1_0": {"status": "green"},
            "1_1": {"status": "green"},
        }}
        solutions, iterations = matrix_service.enumerate_solutions(params, matrix)
        assert len(solutions) == 4  # 2 x 2

    def test_red_cell_filters_solutions(self):
        """Should exclude solutions with red cells."""
        params = [
            MorphologicalParameter(name="P1", states=["A", "B"]),
            MorphologicalParameter(name="P2", states=["X", "Y"])
        ]
        # Matrix: pair 0_1 has red at [0,0] (P1=A, P2=X is red/invalid)
        matrix = {"0_1": {
            "0_0": {"status": "red"},    # P1=A, P2=X is red
            "0_1": {"status": "green"},  # P1=A, P2=Y is green
            "1_0": {"status": "green"},  # P1=B, P2=X is green
            "1_1": {"status": "green"},  # P1=B, P2=Y is green
        }}
        solutions, iterations = matrix_service.enumerate_solutions(params, matrix)
        # [0,0] is invalid due to red cell at [0,0]
        # Valid: [0,1], [1,0], [1,1]
        assert [0, 0] not in solutions  # Rejected due to red
        assert [0, 1] in solutions  # Valid - P1=A, P2=Y
        assert [1, 0] in solutions  # Valid - P1=B, P2=X
        assert [1, 1] in solutions  # Valid - P1=B, P2=Y

    def test_max_yellows_limit(self):
        """Should filter solutions exceeding max yellows."""
        params = [
            MorphologicalParameter(name="P1", states=["A", "B"]),
            MorphologicalParameter(name="P2", states=["X", "Y"])
        ]
        matrix = {"0_1": {
            "0_0": {"status": "green"},
            "0_1": {"status": "yellow"},
            "1_0": {"status": "yellow"},
            "1_1": {"status": "green"},
        }}
        # With max_yellows=1, only solutions with <= 1 yellow
        solutions, _ = matrix_service.enumerate_solutions(params, matrix, max_yellows=1)
        # Solutions with 0 yellows
        assert [0, 0] in solutions  # 0 yellows
        assert [1, 1] in solutions  # 0 yellows
        # Solutions with 2 yellows
        # [0, 1] has 1 yellow, [1, 0] has 1 yellow

    def test_safety_limit_on_iterations(self):
        """Should respect iteration safety limit."""
        params = [
            MorphologicalParameter(name=f"P{i}", states=[f"S{j}" for j in range(20)])
            for i in range(10)  # 10 params x 20 states = huge search space
        ]
        matrix = {"0_1": {"0_0": {"status": "green"}}}
        # Just verify it doesn't hang - it will stop at 1M iterations
        solutions, iterations = matrix_service.enumerate_solutions(params, matrix)
        assert iterations > 1000000  # Should hit limit


class TestCheckOrthogonality:
    """Tests for check_orthogonality."""

    @pytest.mark.asyncio
    async def test_all_orthogonal(self, monkeypatch):
        """Should return all_orthogonal when no warnings."""
        params = [
            MorphologicalParameter(name="Power", states=["Battery", "Solar"]),
            MorphologicalParameter(name="Speed", states=["Fast", "Slow"])
        ]

        fake_response = OrthogonalityCheckResponse(warnings=[], all_orthogonal=True)

        class FakeStructuredLLM:
            def __init__(self):
                self.calls = 0
            async def ainvoke(self, messages):
                self.calls += 1
                return fake_response

        class FakeLLM:
            def __init__(self):
                self.structured = FakeStructuredLLM()
            def with_structured_output(self, schema, method=None):
                return self.structured

        fake_llm = FakeLLM()
        monkeypatch.setattr(matrix_service, "get_llm", lambda **kwargs: fake_llm)

        result = await matrix_service.check_orthogonality(params)

        assert result["all_orthogonal"] is True
        assert result["warnings"] == []

    @pytest.mark.asyncio
    async def test_with_warnings(self, monkeypatch):
        """Should return warnings when parameters overlap."""
        params = [
            MorphologicalParameter(name="Power", states=["Battery", "Solar"]),
            MorphologicalParameter(name="Energy", states=["Electric", "Gas"])
        ]

        fake_response = OrthogonalityCheckResponse(
            warnings=[
                {"param1_idx": 0, "param2_idx": 1, "param1_name": "Power", "param2_name": "Energy", "overlap_description": "Similar concepts"}
            ],
            all_orthogonal=False
        )

        class FakeStructuredLLM:
            async def ainvoke(self, messages):
                return fake_response

        class FakeLLM:
            def with_structured_output(self, schema, method=None):
                return FakeStructuredLLM()

        fake_llm = FakeLLM()
        monkeypatch.setattr(matrix_service, "get_llm", lambda **kwargs: fake_llm)

        result = await matrix_service.check_orthogonality(params)

        assert result["all_orthogonal"] is False
        assert len(result["warnings"]) == 1

    @pytest.mark.asyncio
    async def test_error_fallback(self, monkeypatch):
        """Should return default values on ainvoke error."""
        params = [
            MorphologicalParameter(name="Power", states=["Battery", "Solar"]),
        ]

        class FakeStructuredLLM:
            async def ainvoke(self, messages):
                raise Exception("LLM error")

        class FakeLLM:
            def with_structured_output(self, schema, method=None):
                return FakeStructuredLLM()

        fake_llm = FakeLLM()
        monkeypatch.setattr(matrix_service, "get_llm", lambda **kwargs: fake_llm)

        result = await matrix_service.check_orthogonality(params)

        assert result["all_orthogonal"] is True
        assert result["warnings"] == []
        assert "error" in result


class TestClusterSolutions:
    """Tests for cluster_solutions."""

    @pytest.mark.asyncio
    async def test_empty_solutions(self, monkeypatch):
        """Should return empty list for empty solutions."""
        result = await matrix_service.cluster_solutions([], [])
        assert result == []

    @pytest.mark.asyncio
    async def test_clustering_success(self, monkeypatch):
        """Should cluster solutions via LLM."""
        params = [
            MorphologicalParameter(name="Power", states=["Battery", "Solar"]),
            MorphologicalParameter(name="Speed", states=["Fast", "Slow"])
        ]
        solutions = [[0, 0], [0, 1], [1, 0], [1, 1]]

        fake_response = ClusterResponse(clusters=[
            {"name": "Low Power", "description": "Battery-based", "solution_indices": [0, 1]},
            {"name": "Fast Options", "description": "Fast speed", "solution_indices": [1, 3]}
        ])

        class FakeStructuredLLM:
            async def ainvoke(self, messages):
                return fake_response

        class FakeLLM:
            def with_structured_output(self, schema, method=None):
                return FakeStructuredLLM()

        fake_llm = FakeLLM()
        monkeypatch.setattr(matrix_service, "get_llm", lambda **kwargs: fake_llm)

        result = await matrix_service.cluster_solutions(params, solutions)

        assert len(result) == 2
        assert result[0]["name"] == "Low Power"

    @pytest.mark.asyncio
    async def test_clustering_error_fallback(self, monkeypatch):
        """Should use fallback clustering when ainvoke fails."""
        params = [
            MorphologicalParameter(name="Power", states=["A", "B", "C"]),
        ]
        solutions = [[0], [1], [2]]

        class FakeStructuredLLM:
            async def ainvoke(self, messages):
                raise Exception("LLM error")

        class FakeLLM:
            def with_structured_output(self, schema, method=None):
                return FakeStructuredLLM()

        fake_llm = FakeLLM()
        monkeypatch.setattr(matrix_service, "get_llm", lambda **kwargs: fake_llm)

        result = await matrix_service.cluster_solutions(params, solutions, max_clusters=2)

        assert len(result) == 2  # Fallback creates 2 clusters


class TestSuggestAHPWeights:
    """Tests for suggest_ahp_weights."""

    @pytest.mark.asyncio
    async def test_success(self, monkeypatch):
        """Should return weights from LLM."""
        params = [MorphologicalParameter(name="Power", states=["A", "B"])]
        clusters = [{"name": "Cluster 1"}]

        # AHPCriteriaResponse expects List[Dict[str, float]] where key is criteria name
        fake_response = AHPCriteriaResponse(criteria=[
            {"Cost": 0.4},
            {"Risk": 0.3},
            {"Time": 0.2},
            {"Quality": 0.1}
        ])

        class FakeStructuredLLM:
            async def ainvoke(self, messages):
                return fake_response

        class FakeLLM:
            def with_structured_output(self, schema, method=None):
                return FakeStructuredLLM()

        fake_llm = FakeLLM()
        monkeypatch.setattr(matrix_service, "get_llm", lambda **kwargs: fake_llm)

        result = await matrix_service.suggest_ahp_weights(params, clusters)

        assert len(result) == 4
        # Result is response.criteria which is List[Dict[str, float]]
        assert result[0] == {"Cost": 0.4}

    @pytest.mark.asyncio
    async def test_error_fallback(self, monkeypatch):
        """Should return default weights when ainvoke fails."""
        params = [MorphologicalParameter(name="Power", states=["A", "B"])]
        clusters = []

        class FakeStructuredLLM:
            async def ainvoke(self, messages):
                raise Exception("LLM error")

        class FakeLLM:
            def with_structured_output(self, schema, method=None):
                return FakeStructuredLLM()

        fake_llm = FakeLLM()
        monkeypatch.setattr(matrix_service, "get_llm", lambda **kwargs: fake_llm)

        result = await matrix_service.suggest_ahp_weights(params, clusters)

        assert len(result) == 4
        assert result[0]["name"] == "Cost"
        assert result[0]["weight"] == 0.30


class TestScoreSolutions:
    """Tests for score_solutions."""

    @pytest.mark.asyncio
    async def test_empty_solutions(self, monkeypatch):
        """Should return empty for no solutions."""
        params = [MorphologicalParameter(name="Power", states=["A"])]
        weights = [{"name": "Cost", "weight": 1.0}]

        result = await matrix_service.score_solutions(params, [], weights)

        assert result == []

    @pytest.mark.asyncio
    async def test_scoring_success(self, monkeypatch):
        """Should score solutions via LLM."""
        params = [
            MorphologicalParameter(name="Power", states=["Battery", "Solar"]),
            MorphologicalParameter(name="Speed", states=["Fast", "Slow"])
        ]
        solutions = [[0, 0], [1, 1]]
        weights = [{"name": "Cost", "weight": 1.0}]

        import re
        class FakeLLM:
            async def ainvoke(self, messages):
                # Return JSON-like response
                class Response:
                    content = '{"ranked": [{"idx": 0, "ratings": {"Cost": 5}, "score": 0.9, "summary": "Best"}]}'
                return Response()

        fake_llm = FakeLLM()
        monkeypatch.setattr(matrix_service, "get_llm", lambda **kwargs: fake_llm)

        result = await matrix_service.score_solutions(params, solutions, weights)

        assert len(result) >= 1
        assert result[0]["rank"] == 1

    @pytest.mark.asyncio
    async def test_scoring_error_fallback(self, monkeypatch):
        """Should use random scoring on error."""
        params = [
            MorphologicalParameter(name="Power", states=["Battery", "Solar"]),
        ]
        solutions = [[0], [1]]
        weights = [{"name": "Cost", "weight": 1.0}]

        class FakeLLM:
            async def ainvoke(self, messages):
                raise Exception("LLM error")

        fake_llm = FakeLLM()
        monkeypatch.setattr(matrix_service, "get_llm", lambda **kwargs: fake_llm)

        result = await matrix_service.score_solutions(params, solutions, weights)

        assert len(result) == 2  # Fallback returns random scores