"""
Unit tests for app.matrix.models — database models.
"""
import pytest
from datetime import datetime

from app.matrix.models import (
    Keyword,
    MatrixCell,
    SolutionCluster,
    AHPWeight,
    MorphologicalAnalysis,
)

pytestmark = [pytest.mark.unit]


class TestKeywordModel:
    """Tests for Keyword model."""

    def test_keyword_creation(self):
        """Should create a keyword with required fields."""
        keyword = Keyword(
            id=1,
            user_id=1,
            word="test",
            source_prompt="context"
        )
        assert keyword.word == "test"
        assert keyword.source_prompt == "context"
        assert keyword.user_id == 1

    def test_keyword_default_created_at(self):
        """Should have server-defined created_at."""
        keyword = Keyword(id=1, user_id=1, word="test")
        assert keyword.created_at is None  # Set by server_default


class TestMatrixCellModel:
    """Tests for MatrixCell model."""

    def test_matrix_cell_required_fields(self):
        """Should create a matrix cell with all required fields."""
        cell = MatrixCell(
            id=1,
            analysis_id=1,
            pair_key="0_1",
            state_pair="0_0",
            status="green"
        )
        assert cell.pair_key == "0_1"
        assert cell.state_pair == "0_0"
        assert cell.status == "green"

    def test_matrix_cell_red_status(self):
        """Should create a red cell with contradiction type."""
        cell = MatrixCell(
            id=1,
            analysis_id=1,
            pair_key="0_1",
            state_pair="0_0",
            status="red",
            contradiction_type="L",
            reason="Logical contradiction"
        )
        assert cell.status == "red"
        assert cell.contradiction_type == "L"
        assert cell.reason == "Logical contradiction"

    def test_matrix_cell_yellow_status(self):
        """Should create a yellow cell with reason."""
        cell = MatrixCell(
            id=1,
            analysis_id=1,
            pair_key="0_1",
            state_pair="1_2",
            status="yellow",
            reason="Possible under conditions"
        )
        assert cell.status == "yellow"
        assert cell.contradiction_type is None


class TestSolutionClusterModel:
    """Tests for SolutionCluster model."""

    def test_solution_cluster_creation(self):
        """Should create a solution cluster."""
        cluster = SolutionCluster(
            id=1,
            analysis_id=1,
            cluster_id="cluster_low_cost",
            name="Low Cost Solutions",
            description="Solutions optimized for cost",
            solution_indices=[0, 2, 5]
        )
        assert cluster.cluster_id == "cluster_low_cost"
        assert cluster.name == "Low Cost Solutions"
        assert cluster.solution_indices == [0, 2, 5]


class TestAHPWeightModel:
    """Tests for AHPWeight model."""

    def test_ahp_weight_creation(self):
        """Should create AHP weight with criteria."""
        weight = AHPWeight(
            id=1,
            analysis_id=1,
            criteria=[
                {"name": "Cost", "weight": 0.30},
                {"name": "Time", "weight": 0.20},
                {"name": "Risk", "weight": 0.25},
                {"name": "Performance", "weight": 0.25}
            ]
        )
        assert len(weight.criteria) == 4
        assert weight.criteria[0]["name"] == "Cost"
        assert weight.criteria[0]["weight"] == 0.30


class TestMorphologicalAnalysisModel:
    """Tests for MorphologicalAnalysis model."""

    def test_morphological_analysis_defaults(self):
        """Should have correct default values (DB-level defaults)."""
        analysis = MorphologicalAnalysis(
            id=1,
            user_id=1,
            focus_question="How should we configure X?"
        )
        # SQLAlchemy defaults are applied at insert time, not on object creation
        assert analysis.focus_question == "How should we configure X?"
        assert analysis.workspace_id is None

    def test_morphological_analysis_with_workspace(self):
        """Should associate with workspace."""
        analysis = MorphologicalAnalysis(
            id=1,
            user_id=1,
            workspace_id=5,
            focus_question="Test?"
        )
        assert analysis.workspace_id == 5

    def test_morphological_analysis_statuses(self):
        """Should accept all valid status values."""
        valid_statuses = [
            "pending",
            "generating_parameters",
            "parameters_ready",
            "generate_failed",
            "evaluating_matrix",
            "matrix_ready",
            "evaluate_failed"
        ]
        for status in valid_statuses:
            analysis = MorphologicalAnalysis(
                id=1,
                user_id=1,
                focus_question="Test?",
                status=status
            )
            assert analysis.status == status