"""
Tests for app.research.schemas — API request/response models.
"""

import pytest

from app.research.schemas import ResearchResult, ResearchStart, ResearchStatus
from app.research.state import ResearchLevel


class TestResearchStart:
    def test_defaults(self):
        schema = ResearchStart(query="What is AI?")
        assert schema.query == "What is AI?"
        assert schema.level == ResearchLevel.STANDARD
        assert schema.max_iterations is None
        assert schema.max_results is None

    def test_with_level(self):
        schema = ResearchStart(query="What is AI?", level=ResearchLevel.EXTENDED)
        assert schema.level == ResearchLevel.EXTENDED

    def test_with_custom_iterations(self):
        schema = ResearchStart(query="What is AI?", max_iterations=5, max_results=20)
        assert schema.max_iterations == 5
        assert schema.max_results == 20

    def test_query_required(self):
        with pytest.raises(Exception):  # ValidationError
            ResearchStart()


class TestResearchStatus:
    def test_valid_statuses(self):
        for status in ["clarifying", "planning", "searching", "synthesizing", "reporting", "done", "error"]:
            s = ResearchStatus(
                status=status,
                message="test",
                progress=0.5,
                level=ResearchLevel.STANDARD,
            )
            assert s.status == status

    def test_progress_range(self):
        s = ResearchStatus(
            status="searching",
            message="Searching...",
            progress=0.75,
            level=ResearchLevel.EXTENDED,
        )
        assert s.progress == 0.75

    def test_optional_iteration(self):
        s = ResearchStatus(
            status="searching",
            message="test",
            progress=0.5,
            level=ResearchLevel.STANDARD,
            iteration=2,
        )
        assert s.iteration == 2

    def test_invalid_status_rejected(self):
        with pytest.raises(Exception):
            ResearchStatus(
                status="invalid_status",
                message="test",
                progress=0.5,
                level=ResearchLevel.STANDARD,
            )


class TestResearchResult:
    def test_valid_result(self):
        r = ResearchResult(
            report="# Report\n\nFindings here.",
            iterations=3,
            level=ResearchLevel.STANDARD,
        )
        assert r.report.startswith("# Report")
        assert r.iterations == 3
        assert r.level == ResearchLevel.STANDARD
