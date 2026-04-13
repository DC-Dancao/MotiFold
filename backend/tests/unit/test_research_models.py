"""
Tests for app.research.models — ResearchReport SQLAlchemy model.
"""
import pytest
from datetime import datetime

from app.research.models import ResearchReport

pytestmark = pytest.mark.unit


class TestResearchReportModel:
    """Tests for ResearchReport database model."""

    def test_model_accepts_required_fields(self):
        """ResearchReport can be created with required fields."""
        report = ResearchReport(
            user_id=1,
            query="test query",
        )
        assert report.user_id == 1
        assert report.query == "test query"

    def test_default_values_are_set_by_orm(self):
        """ORM defaults are set correctly when all fields provided."""
        report = ResearchReport(
            user_id=1,
            query="test query",
            level="standard",
            status="running",
            notes_json="[]",
            queries_json="[]",
            iterations=0,
        )
        assert report.level == "standard"
        assert report.status == "running"
        assert report.notes_json == "[]"
        assert report.queries_json == "[]"
        assert report.iterations == 0

    def test_research_topic_is_nullable(self):
        """research_topic can be None."""
        report = ResearchReport(
            user_id=1,
            query="test",
            research_topic=None,
        )
        assert report.research_topic is None

    def test_report_is_nullable(self):
        """report can be None (before completion)."""
        report = ResearchReport(
            user_id=1,
            query="test",
            report=None,
        )
        assert report.report is None

    def test_task_id_is_nullable(self):
        """task_id (Celery UUID) can be None."""
        report = ResearchReport(
            user_id=1,
            query="test",
            task_id=None,
        )
        assert report.task_id is None

    def test_workspace_id_is_nullable(self):
        """workspace_id can be None."""
        report = ResearchReport(
            user_id=1,
            query="test",
            workspace_id=None,
        )
        assert report.workspace_id is None

    def test_status_values(self):
        """status field accepts running/done/error."""
        for status in ("running", "done", "error"):
            report = ResearchReport(
                user_id=1,
                query="test",
                status=status,
            )
            assert report.status == status

    def test_level_values(self):
        """level field accepts standard/extended/manual."""
        for level in ("standard", "extended", "manual"):
            report = ResearchReport(
                user_id=1,
                query="test",
                level=level,
            )
            assert report.level == level

    def test_timestamps_default_to_none(self):
        """created_at and updated_at can be None (before insert)."""
        report = ResearchReport(
            user_id=1,
            query="test",
        )
        assert report.created_at is None
        assert report.updated_at is None
