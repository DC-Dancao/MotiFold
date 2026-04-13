"""
Unit tests for app.matrix.schemas module.

Tests Matrix schemas, normalization, and validation.
"""
import pytest
from pydantic import ValidationError

pytestmark = [pytest.mark.unit]


class TestNormalizeMorphologicalText:
    """Tests for normalize_morphological_text helper."""

    def test_removes_extra_whitespace(self):
        """Should collapse multiple spaces into single space."""
        from app.matrix.schemas import normalize_morphological_text

        result = normalize_morphological_text("hello    world")
        assert result == "hello world"

    def test_trims_leading_and_trailing_whitespace(self):
        """Should trim leading and trailing whitespace."""
        from app.matrix.schemas import normalize_morphological_text

        result = normalize_morphological_text("  hello  ")
        assert result == "hello"

    def test_converts_non_string_to_string(self):
        """Should convert non-string input to string."""
        from app.matrix.schemas import normalize_morphological_text

        assert normalize_morphological_text(123) == "123"
        assert normalize_morphological_text(None) == ""
        assert normalize_morphological_text(["a", "b"]) == "a b"


class TestMorphologicalParameter:
    """Tests for MorphologicalParameter schema."""

    def test_valid_parameter(self):
        """Should create valid MorphologicalParameter."""
        from app.matrix.schemas import MorphologicalParameter

        param = MorphologicalParameter(name="Test Param", states=["State1", "State2"])
        assert param.name == "Test Param"
        assert param.states == ["State1", "State2"]

    def test_name_normalization(self):
        """Should normalize parameter name (trim whitespace)."""
        from app.matrix.schemas import MorphologicalParameter

        param = MorphologicalParameter(name="  Test Param  ", states=["State1"])
        assert param.name == "Test Param"

    def test_empty_name_rejected(self):
        """Should reject empty parameter name."""
        from app.matrix.schemas import MorphologicalParameter

        with pytest.raises(ValidationError) as exc_info:
            MorphologicalParameter(name="", states=["State1"])

        assert "cannot be empty" in str(exc_info.value)

    def test_whitespace_only_name_rejected(self):
        """Should reject whitespace-only parameter name."""
        from app.matrix.schemas import MorphologicalParameter

        with pytest.raises(ValidationError) as exc_info:
            MorphologicalParameter(name="   ", states=["State1"])

        assert "cannot be empty" in str(exc_info.value)


class TestNormalizeMorphologicalResponse:
    """Tests for normalize_morphological_response function."""

    def test_valid_response_normalization(self):
        """Should normalize valid LLM response."""
        from app.matrix.schemas import normalize_morphological_response

        raw_response = type('obj', (object,), {
            'parameters': [
                {'name': 'Param 1', 'states': ['State 1', 'State 2']},
                {'name': 'Param 2', 'states': ['State A', 'State B']}
            ]
        })()

        result = normalize_morphological_response(raw_response)
        assert len(result.parameters) == 2
        assert result.parameters[0].name == "Param 1"
        assert result.parameters[1].name == "Param 2"

    def test_removes_duplicate_parameter_names_case_insensitive(self):
        """Should deduplicate parameters by name (case-insensitive)."""
        from app.matrix.schemas import normalize_morphological_response

        raw_response = type('obj', (object,), {
            'parameters': [
                {'name': 'Param 1', 'states': ['State 1']},
                {'name': 'param 1', 'states': ['State 2']},  # Duplicate (case-insensitive)
            ]
        })()

        result = normalize_morphological_response(raw_response)
        assert len(result.parameters) == 1

    def test_removes_duplicate_states_case_insensitive(self):
        """Should deduplicate states within a parameter (case-insensitive)."""
        from app.matrix.schemas import normalize_morphological_response

        raw_response = type('obj', (object,), {
            'parameters': [
                {'name': 'Param 1', 'states': ['State 1', 'STATE 1', 'State 2']},
            ]
        })()

        result = normalize_morphological_response(raw_response)
        assert len(result.parameters[0].states) == 2

    def test_removes_empty_parameters(self):
        """Should skip parameters with empty/whitespace names."""
        from app.matrix.schemas import normalize_morphological_response

        raw_response = type('obj', (object,), {
            'parameters': [
                {'name': '', 'states': ['State 1']},
                {'name': 'Valid Param', 'states': ['State 2']},
            ]
        })()

        result = normalize_morphological_response(raw_response)
        assert len(result.parameters) == 1
        assert result.parameters[0].name == "Valid Param"

    def test_raises_when_too_few_parameters(self):
        """Should raise error when fewer than 2 usable parameters."""
        from app.matrix.schemas import normalize_morphological_response

        raw_response = type('obj', (object,), {
            'parameters': [
                {'name': 'Only One', 'states': ['State 1']},
            ]
        })()

        with pytest.raises(ValueError) as exc_info:
            normalize_morphological_response(raw_response)

        assert "Too few usable parameters" in str(exc_info.value)

    def test_handles_model_objects_input(self):
        """Should handle input that is already a Pydantic model."""
        from app.matrix.schemas import normalize_morphological_response, LLMMorphologicalParameter

        raw_response = type('obj', (object,), {
            'parameters': [
                LLMMorphologicalParameter(name='Param 1', states=['State 1']),
                LLMMorphologicalParameter(name='Param 2', states=['State 2']),
            ]
        })()

        result = normalize_morphological_response(raw_response)
        assert len(result.parameters) == 2


class TestMatrixCellSchema:
    """Tests for MatrixCellSchema."""

    def test_valid_green_cell(self):
        """Should create green status cell."""
        from app.matrix.schemas import MatrixCellSchema

        cell = MatrixCellSchema(status="green")
        assert cell.status == "green"
        assert cell.contradiction_type is None

    def test_valid_red_cell_with_contradiction(self):
        """Should create red cell with contradiction type."""
        from app.matrix.schemas import MatrixCellSchema

        cell = MatrixCellSchema(
            status="red",
            contradiction_type="L",
            reason="Logical contradiction"
        )
        assert cell.status == "red"
        assert cell.contradiction_type == "L"
        assert cell.reason == "Logical contradiction"

    def test_valid_yellow_cell(self):
        """Should create yellow status cell."""
        from app.matrix.schemas import MatrixCellSchema

        cell = MatrixCellSchema(status="yellow")
        assert cell.status == "yellow"

    def test_invalid_status_rejected(self):
        """Should reject invalid status values."""
        from app.matrix.schemas import MatrixCellSchema

        with pytest.raises(ValidationError):
            MatrixCellSchema(status="invalid")


class TestClusterRequest:
    """Tests for ClusterRequest schema."""

    def test_default_max_clusters(self):
        """Should have default max_clusters of 5."""
        from app.matrix.schemas import ClusterRequest

        req = ClusterRequest(analysis_id=1)
        assert req.max_clusters == 5

    def test_valid_max_clusters_range(self):
        """Should accept max_clusters between 2 and 10."""
        from app.matrix.schemas import ClusterRequest

        for n in [2, 5, 10]:
            req = ClusterRequest(analysis_id=1, max_clusters=n)
            assert req.max_clusters == n

    def test_rejects_max_clusters_below_2(self):
        """Should reject max_clusters less than 2."""
        from app.matrix.schemas import ClusterRequest

        with pytest.raises(ValidationError):
            ClusterRequest(analysis_id=1, max_clusters=1)

    def test_rejects_max_clusters_above_10(self):
        """Should reject max_clusters greater than 10."""
        from app.matrix.schemas import ClusterRequest

        with pytest.raises(ValidationError):
            ClusterRequest(analysis_id=1, max_clusters=11)


class TestAHPSuggestRequest:
    """Tests for AHPSuggestRequest schema."""

    def test_default_num_criteria(self):
        """Should have default num_criteria of 4."""
        from app.matrix.schemas import AHPSuggestRequest

        req = AHPSuggestRequest(analysis_id=1)
        assert req.num_criteria == 4

    def test_valid_criteria_range(self):
        """Should accept num_criteria between 3 and 6."""
        from app.matrix.schemas import AHPSuggestRequest

        for n in [3, 4, 5, 6]:
            req = AHPSuggestRequest(analysis_id=1, num_criteria=n)
            assert req.num_criteria == n

    def test_rejects_num_criteria_below_3(self):
        """Should reject num_criteria less than 3."""
        from app.matrix.schemas import AHPSuggestRequest

        with pytest.raises(ValidationError):
            AHPSuggestRequest(analysis_id=1, num_criteria=2)

    def test_rejects_num_criteria_above_6(self):
        """Should reject num_criteria greater than 6."""
        from app.matrix.schemas import AHPSuggestRequest

        with pytest.raises(ValidationError):
            AHPSuggestRequest(analysis_id=1, num_criteria=7)


class TestEvaluationResult:
    """Tests for EvaluationResult schema."""

    def test_default_empty_lists(self):
        """Should have empty lists and dicts as defaults."""
        from app.matrix.schemas import EvaluationResult

        result = EvaluationResult()
        assert result.red == []
        assert result.yellow == []
        assert result.reasons == {}
        assert result.types == {}

    def test_with_conflicts(self):
        """Should accept conflict data."""
        from app.matrix.schemas import EvaluationResult

        result = EvaluationResult(
            red=[[0, 1], [2, 3]],
            yellow=[[1, 2]],
            reasons={"red": {"0,1": "Mutually exclusive"}},
            types={"red": {"0,1": "L"}}
        )
        assert len(result.red) == 2
        assert len(result.yellow) == 1


class TestScoredSolution:
    """Tests for ScoredSolution schema."""

    def test_valid_scored_solution(self):
        """Should create valid ScoredSolution."""
        from app.matrix.schemas import ScoredSolution

        solution = ScoredSolution(
            rank=1,
            solution_index=5,
            solution=["State1", "State2"],
            score=0.95,
            ratings={"criteria1": 4, "criteria2": 5},
            summary="Best solution"
        )
        assert solution.rank == 1
        assert solution.score == 0.95
