"""
Unit tests for research state including new MATRIX level.
"""
import pytest

pytestmark = [pytest.mark.unit]


class TestResearchLevel:
    """Tests for ResearchLevel enum."""

    def test_research_level_standard(self):
        """Should have STANDARD level."""
        from app.research.state import ResearchLevel

        assert ResearchLevel.STANDARD is not None
        assert ResearchLevel.STANDARD.value == "standard"

    def test_research_level_extended(self):
        """Should have EXTENDED level."""
        from app.research.state import ResearchLevel

        assert ResearchLevel.EXTENDED is not None
        assert ResearchLevel.EXTENDED.value == "extended"

    def test_research_level_manual(self):
        """Should have MANUAL level."""
        from app.research.state import ResearchLevel

        assert ResearchLevel.MANUAL is not None
        assert ResearchLevel.MANUAL.value == "manual"

    def test_research_level_matrix(self):
        """Should have MATRIX level for morphological analysis exploration."""
        from app.research.state import ResearchLevel

        assert ResearchLevel.MATRIX is not None
        assert ResearchLevel.MATRIX.value == "matrix"

    def test_research_level_all_values(self):
        """Should have all expected level values."""
        from app.research.state import ResearchLevel

        expected = {"standard", "extended", "manual", "matrix"}
        actual = {level.value for level in ResearchLevel}
        assert expected == actual


class TestLevelDefaults:
    """Tests for LEVEL_DEFAULTS."""

    def test_standard_defaults(self):
        """Should have correct defaults for STANDARD."""
        from app.research.state import LEVEL_DEFAULTS, ResearchLevel

        defaults = LEVEL_DEFAULTS[ResearchLevel.STANDARD]
        assert defaults == (3, 10)  # (max_iterations, max_results)

    def test_extended_defaults(self):
        """Should have correct defaults for EXTENDED."""
        from app.research.state import LEVEL_DEFAULTS, ResearchLevel

        defaults = LEVEL_DEFAULTS[ResearchLevel.EXTENDED]
        assert defaults == (6, 20)

    def test_manual_defaults(self):
        """Should have correct defaults for MANUAL."""
        from app.research.state import LEVEL_DEFAULTS, ResearchLevel

        defaults = LEVEL_DEFAULTS[ResearchLevel.MANUAL]
        assert defaults == (5, 10)

    def test_matrix_defaults(self):
        """Should have correct defaults for MATRIX."""
        from app.research.state import LEVEL_DEFAULTS, ResearchLevel

        defaults = LEVEL_DEFAULTS[ResearchLevel.MATRIX]
        assert defaults == (3, 10)  # Same as standard

    def test_level_defaults_for_matrix(self):
        """level_defaults_for should work with MATRIX level."""
        from app.research.state import level_defaults_for, ResearchLevel

        defaults = level_defaults_for(ResearchLevel.MATRIX)
        assert defaults == (3, 10)


class TestResearchStateSchema:
    """Tests for ResearchState schema."""

    def test_research_state_has_all_fields(self):
        """ResearchState should have all expected fields."""
        from app.research.state import ResearchState

        # Check all expected fields exist
        expected_fields = [
            "messages",
            "research_topic",
            "search_queries",
            "search_results",
            "notes",
            "final_report",
            "iterations",
            "max_iterations",
            "max_results",
            "research_level",
            "research_history",
            "user_inputs",
            "needs_followup",
            "followup_options",
            "is_complete",
        ]

        for field in expected_fields:
            assert field in ResearchState.__annotations__


class TestResearchStateInheritsMessagesState:
    """Tests that ResearchState properly inherits MessagesState."""

    def test_research_state_inherits_from_messages_state(self):
        """Should inherit from MessagesState."""
        from app.research.state import ResearchState
        from langgraph.graph import MessagesState

        assert issubclass(ResearchState, MessagesState)

    def test_research_state_messages_field(self):
        """Should have messages field from MessagesState."""
        from app.research.state import ResearchState

        # MessagesState provides the messages field
        assert "messages" in ResearchState.__annotations__
