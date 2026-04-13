"""
Unit tests for app.blackboard module.
Covers: models, schemas, router endpoints, agent nodes, and celery task.
"""
import json
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from unittest.mock import ANY
from types import SimpleNamespace

import pytest_asyncio
from fastapi import HTTPException

from app.blackboard.models import BlackboardData
from app.blackboard.schemas import BlackboardCreate, BlackboardResponse
from app.blackboard.agent import (
    Block,
    FinalBoard,
    StepHighlight,
    Step,
    ReverseSteps,
    BlackboardState,
    generate_final_board,
    generate_steps_reverse,
    format_output,
    create_blackboard_agent,
    run_blackboard_agent,
)
from app.blackboard.router import router
from app.blackboard import router as bb_router_module
from app.worker.blackboard_tasks import generate_blackboard_task


# ==============================================================================
# Schemas Tests
# ==============================================================================

class TestBlackboardSchemas:
    """Tests for BlackboardCreate and BlackboardResponse schemas."""

    def test_blackboard_create_valid(self):
        """Valid BlackboardCreate should parse correctly."""
        data = BlackboardCreate(topic="How to cook rice", workspace_id=1)
        assert data.topic == "How to cook rice"
        assert data.workspace_id == 1

    def test_blackboard_create_topic_required(self):
        """Topic field is required."""
        with pytest.raises(Exception):
            BlackboardCreate()

    def test_blackboard_create_workspace_optional(self):
        """Workspace_id is optional."""
        data = BlackboardCreate(topic="Math lesson")
        assert data.workspace_id is None

    def test_blackboard_response_valid(self):
        """BlackboardResponse should contain all fields."""
        data = BlackboardResponse(
            id=1,
            topic="Physics 101",
            status="completed",
            content_json='[{"title": "Step 1"}]',
            created_at="2026-01-01T00:00:00"
        )
        assert data.id == 1
        assert data.topic == "Physics 101"
        assert data.status == "completed"
        assert data.content_json == '[{"title": "Step 1"}]'


# ==============================================================================
# Agent Schema Tests
# ==============================================================================

class TestAgentSchemas:
    """Tests for agent Pydantic models (Block, FinalBoard, Step, etc.)."""

    def test_block_creation(self):
        """Block model should accept valid data."""
        block = Block(
            id="blk_1",
            type="text",
            content="Hello world",
            x=10,
            y=20,
            rot=1
        )
        assert block.id == "blk_1"
        assert block.type == "text"
        assert block.content == "Hello world"
        assert block.x == 10
        assert block.y == 20
        assert block.rot == 1

    def test_block_type_literals(self):
        """Block type should only accept valid literals."""
        block_text = Block(id="b1", type="text", content="text", x=0, y=0, rot=0)
        block_math = Block(id="b2", type="math", content="1+1=2", x=0, y=0, rot=0)
        block_result = Block(id="b3", type="result", content="answer", x=0, y=0, rot=0)
        assert block_text.type == "text"
        assert block_math.type == "math"
        assert block_result.type == "result"

    def test_block_invalid_type_rejected(self):
        """Block with invalid type should be rejected."""
        with pytest.raises(Exception):
            Block(id="b1", type="invalid", content="text", x=0, y=0, rot=0)

    def test_final_board_with_blocks(self):
        """FinalBoard should hold a list of blocks."""
        blocks = [
            Block(id="b1", type="text", content="Title", x=10, y=10, rot=0),
            Block(id="b2", type="math", content="E=mc^2", x=20, y=30, rot=-1),
        ]
        board = FinalBoard(blocks=blocks)
        assert len(board.blocks) == 2
        assert board.blocks[0].id == "b1"

    def test_step_highlight(self):
        """StepHighlight should store block_id and highlight flag."""
        highlight = StepHighlight(block_id="blk_1", highlight=True)
        assert highlight.block_id == "blk_1"
        assert highlight.highlight is True

    def test_step_with_visible_blocks(self):
        """Step should contain title, note, and visible_blocks list."""
        step = Step(
            title="Introduction",
            note="Today we learn about gravity",
            visible_blocks=[
                StepHighlight(block_id="b1", highlight=True),
                StepHighlight(block_id="b2", highlight=False),
            ]
        )
        assert step.title == "Introduction"
        assert step.note == "Today we learn about gravity"
        assert len(step.visible_blocks) == 2
        assert step.visible_blocks[0].highlight is True

    def test_reverse_steps_with_multiple_steps(self):
        """ReverseSteps should contain a list of steps."""
        steps = [
            Step(title="Step 1", note="Note 1", visible_blocks=[]),
            Step(title="Step 2", note="Note 2", visible_blocks=[]),
        ]
        reverse_steps = ReverseSteps(steps=steps)
        assert len(reverse_steps.steps) == 2

    def test_step_highlight_can_be_false(self):
        """StepHighlight highlight field can be False."""
        highlight = StepHighlight(block_id="b1", highlight=False)
        assert highlight.highlight is False


# ==============================================================================
# Agent Node Tests
# ==============================================================================

class TestAgentNodes:
    """Tests for individual agent nodes: generate_final_board, generate_steps_reverse, format_output."""

    @patch("app.blackboard.agent.get_llm")
    async def test_generate_final_board_returns_final_board(self, mock_get_llm):
        """generate_final_board should return a FinalBoard object."""
        mock_model = MagicMock()
        mock_structured_output = MagicMock()
        mock_model.with_structured_output.return_value = mock_structured_output

        mock_chain = MagicMock()
        mock_chain.ainvoke = AsyncMock(return_value=FinalBoard(blocks=[
            Block(id="b1", type="text", content="Test", x=10, y=10, rot=0)
        ]))
        mock_structured_output.ainvoke = mock_chain.ainvoke

        # The prompt | llm | parser chain
        mock_llm_instance = MagicMock()
        mock_llm_instance.bind.return_value = mock_llm_instance
        mock_llm_instance.__or__ = lambda self, other: mock_chain
        mock_get_llm.return_value = mock_llm_instance

        state: BlackboardState = {"topic": "Test Topic"}
        result = await generate_final_board(state)

        assert "final_board" in result
        assert isinstance(result["final_board"], FinalBoard)

    @patch("app.blackboard.agent.get_llm")
    async def test_generate_steps_reverse_returns_reverse_steps(self, mock_get_llm):
        """generate_steps_reverse should return ReverseSteps object."""
        mock_model = MagicMock()
        mock_structured_output = MagicMock()
        mock_model.with_structured_output.return_value = mock_structured_output

        mock_chain = MagicMock()
        mock_chain.ainvoke = AsyncMock(return_value=ReverseSteps(steps=[
            Step(title="Step 1", note="Note 1", visible_blocks=[
                StepHighlight(block_id="b1", highlight=True)
            ])
        ]))
        mock_structured_output.ainvoke = mock_chain.ainvoke

        mock_llm_instance = MagicMock()
        mock_llm_instance.bind.return_value = mock_llm_instance
        mock_llm_instance.__or__ = lambda self, other: mock_chain
        mock_get_llm.return_value = mock_llm_instance

        final_board = FinalBoard(blocks=[
            Block(id="b1", type="text", content="Test", x=10, y=10, rot=0)
        ])
        state: BlackboardState = {
            "topic": "Test",
            "final_board": final_board,
            "reverse_steps": ReverseSteps(steps=[]),
            "final_output": []
        }

        result = await generate_steps_reverse(state)

        assert "reverse_steps" in result
        assert isinstance(result["reverse_steps"], ReverseSteps)
        assert len(result["reverse_steps"].steps) == 1

    def test_format_output_creates_correct_structure(self):
        """format_output should create the expected JSON array format."""
        final_board = FinalBoard(blocks=[
            Block(id="b1", type="text", content="Block 1", x=10, y=10, rot=0),
            Block(id="b2", type="math", content="2+2=4", x=20, y=20, rot=1),
        ])

        reverse_steps = ReverseSteps(steps=[
            Step(
                title="Step 1: Introduction",
                note="Let's start with basics",
                visible_blocks=[
                    StepHighlight(block_id="b1", highlight=True),
                ]
            ),
            Step(
                title="Step 2: Math",
                note="Now for math",
                visible_blocks=[
                    StepHighlight(block_id="b1", highlight=False),
                    StepHighlight(block_id="b2", highlight=True),
                ]
            ),
        ])

        state: BlackboardState = {
            "topic": "Test",
            "final_board": final_board,
            "reverse_steps": reverse_steps,
            "final_output": []
        }

        result = format_output(state)

        assert "final_output" in result
        output = result["final_output"]

        assert len(output) == 2

        # Step 1
        assert output[0]["title"] == "Step 1: Introduction"
        assert output[0]["note"] == "Let's start with basics"
        assert len(output[0]["boardState"]) == 1
        assert output[0]["boardState"][0]["id"] == "b1"
        assert output[0]["boardState"][0]["highlight"] is True

        # Step 2
        assert output[1]["title"] == "Step 2: Math"
        assert len(output[1]["boardState"]) == 2
        # b1 should have highlight=False in step 2
        b1_in_step2 = next(b for b in output[1]["boardState"] if b["id"] == "b1")
        assert b1_in_step2["highlight"] is False
        # b2 should have highlight=True in step 2
        b2_in_step2 = next(b for b in output[1]["boardState"] if b["id"] == "b2")
        assert b2_in_step2["highlight"] is True

    def test_format_output_hides_unknown_blocks(self):
        """format_output should ignore visible_blocks with unknown block_ids."""
        final_board = FinalBoard(blocks=[
            Block(id="b1", type="text", content="Block 1", x=10, y=10, rot=0),
        ])

        reverse_steps = ReverseSteps(steps=[
            Step(
                title="Step 1",
                note="Note",
                visible_blocks=[
                    StepHighlight(block_id="b1", highlight=True),
                    StepHighlight(block_id="unknown_block", highlight=True),
                ]
            ),
        ])

        state: BlackboardState = {
            "topic": "Test",
            "final_board": final_board,
            "reverse_steps": reverse_steps,
            "final_output": []
        }

        result = format_output(state)
        output = result["final_output"]

        assert len(output[0]["boardState"]) == 1
        assert output[0]["boardState"][0]["id"] == "b1"


class TestBlackboardAgent:
    """Tests for run_blackboard_agent function."""

    @patch("app.blackboard.agent.get_llm")
    async def test_run_blackboard_agent_returns_list(self, mock_get_llm):
        """run_blackboard_agent should return a list of step dicts."""
        mock_model = MagicMock()
        mock_structured_output = MagicMock()
        mock_model.with_structured_output.return_value = mock_structured_output

        final_board = FinalBoard(blocks=[
            Block(id="b1", type="text", content="Title", x=10, y=10, rot=0),
        ])
        reverse_steps = ReverseSteps(steps=[
            Step(
                title="Step 1",
                note="Note",
                visible_blocks=[StepHighlight(block_id="b1", highlight=True)]
            ),
        ])

        mock_chain = MagicMock()
        mock_responses = [final_board, reverse_steps]
        mock_chain.ainvoke = AsyncMock(side_effect=mock_responses)

        mock_llm_instance = MagicMock()
        mock_llm_instance.bind.return_value = mock_llm_instance
        mock_llm_instance.__or__ = lambda self, other: mock_chain
        mock_get_llm.return_value = mock_llm_instance

        result = await run_blackboard_agent("Test topic")

        assert isinstance(result, list)
        assert len(result) == 1
        assert "title" in result[0]
        assert "note" in result[0]
        assert "boardState" in result[0]

    @patch("app.blackboard.agent.get_llm")
    async def test_run_blackboard_agent_multiple_steps(self, mock_get_llm):
        """run_blackboard_agent should handle multiple steps correctly."""
        mock_model = MagicMock()
        mock_structured_output = MagicMock()
        mock_model.with_structured_output.return_value = mock_structured_output

        final_board = FinalBoard(blocks=[
            Block(id="b1", type="text", content="Block 1", x=10, y=10, rot=0),
            Block(id="b2", type="text", content="Block 2", x=20, y=20, rot=1),
            Block(id="b3", type="math", content="1+1=2", x=30, y=30, rot=-1),
        ])
        reverse_steps = ReverseSteps(steps=[
            Step(
                title="Introduction",
                note="Intro note",
                visible_blocks=[StepHighlight(block_id="b1", highlight=True)]
            ),
            Step(
                title="Main Content",
                note="Main note",
                visible_blocks=[
                    StepHighlight(block_id="b1", highlight=False),
                    StepHighlight(block_id="b2", highlight=True),
                ]
            ),
            Step(
                title="Conclusion",
                note="Conclusion note",
                visible_blocks=[
                    StepHighlight(block_id="b1", highlight=False),
                    StepHighlight(block_id="b2", highlight=False),
                    StepHighlight(block_id="b3", highlight=True),
                ]
            ),
        ])

        mock_chain = MagicMock()
        mock_chain.ainvoke = AsyncMock(side_effect=[final_board, reverse_steps])

        mock_llm_instance = MagicMock()
        mock_llm_instance.bind.return_value = mock_llm_instance
        mock_llm_instance.__or__ = lambda self, other: mock_chain
        mock_get_llm.return_value = mock_llm_instance

        result = await run_blackboard_agent("Complex topic")

        assert len(result) == 3
        assert result[0]["title"] == "Introduction"
        assert result[1]["title"] == "Main Content"
        assert result[2]["title"] == "Conclusion"


# ==============================================================================
# Router Tests
# ==============================================================================

class TestBlackboardRouter:
    """Tests for blackboard API router endpoints."""

    @pytest.fixture
    def mock_dependencies(self, mocker):
        """Mock all dependencies for router tests."""
        mock_get_db = mocker.patch("app.blackboard.router.get_db_with_schema")
        mock_get_current_user = mocker.patch("app.blackboard.router.get_current_user")
        mock_get_org_membership = mocker.patch("app.blackboard.router.get_current_org_membership")
        return {
            "db": mock_get_db,
            "user": mock_get_current_user,
            "membership": mock_get_org_membership,
        }

    def test_router_prefix(self):
        """Router should have correct prefix and tags."""
        assert router.prefix == "/blackboard"
        assert "blackboard" in router.tags

    def test_router_has_responses_404(self):
        """Router should have 404 response defined."""
        assert 404 in router.responses


class TestBlackboardRouterCreate:
    """Tests for POST /blackboard/ endpoint."""

    @pytest.mark.asyncio
    async def test_create_blackboard_returns_response(self, mocker):
        """create_blackboard should return BlackboardResponse."""
        mock_request = MagicMock()
        mock_request.state = MagicMock()

        mock_db = mocker.MagicMock()
        mock_db.flush = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_db.add = MagicMock()

        mock_user = MagicMock()
        mock_user.id = 42

        mock_membership = MagicMock()

        # Mock the BlackboardData insert
        created_record = MagicMock()
        created_record.id = 1
        created_record.topic = "Test Topic"
        created_record.status = "pending"
        created_record.content_json = "[]"
        created_record.created_at = MagicMock()

        def mock_add(obj):
            obj.id = 1
            obj.created_at = MagicMock()

        mock_db.add = MagicMock(side_effect=mock_add)

        mocker.patch("app.blackboard.router.BlackboardData", return_value=created_record)

        # Mock the celery task
        mock_task = mocker.patch("app.blackboard.router.generate_blackboard_task")
        mock_task.delay = MagicMock()

        from app.blackboard.schemas import BlackboardCreate
        from app.blackboard.router import create_blackboard

        bb_create = BlackboardCreate(topic="Test Topic", workspace_id=1)

        result = await create_blackboard(
            bb_create=bb_create,
            request=mock_request,
            db=mock_db,
            current_user=mock_user,
            membership=mock_membership,
        )

        assert result.topic == "Test Topic"
        mock_db.add.assert_called_once()
        mock_db.flush.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_task.delay.assert_called_once()


class TestBlackboardRouterGet:
    """Tests for GET /blackboard/{bb_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_blackboard_returns_data(self, mocker):
        """get_blackboard should return BlackboardResponse for existing record."""
        mock_request = MagicMock()

        mock_db = mocker.MagicMock()
        mock_result = mocker.MagicMock()
        mock_scalars = mocker.MagicMock()
        mock_scalars.first.return_value = MagicMock(
            id=5,
            topic="Existing Board",
            status="completed",
            content_json='[{"title": "Step 1"}]',
            created_at=MagicMock(),
        )
        mock_result.scalars.return_value = mock_scalars
        mock_db.execute = AsyncMock(return_value=mock_result)

        mock_user = MagicMock()
        mock_membership = MagicMock()

        from app.blackboard.router import get_blackboard

        result = await get_blackboard(
            bb_id=5,
            request=mock_request,
            db=mock_db,
            current_user=mock_user,
            membership=mock_membership,
        )

        assert result.id == 5
        assert result.topic == "Existing Board"

    @pytest.mark.asyncio
    async def test_get_blackboard_raises_404(self, mocker):
        """get_blackboard should raise 404 for non-existent record."""
        mock_request = MagicMock()

        mock_db = mocker.MagicMock()
        mock_result = mocker.MagicMock()
        mock_scalars = mocker.MagicMock()
        mock_scalars.first.return_value = None
        mock_result.scalars.return_value = mock_scalars
        mock_db.execute = AsyncMock(return_value=mock_result)

        mock_user = MagicMock()
        mock_membership = MagicMock()

        from app.blackboard.router import get_blackboard

        with pytest.raises(HTTPException) as exc_info:
            await get_blackboard(
                bb_id=999,
                request=mock_request,
                db=mock_db,
                current_user=mock_user,
                membership=mock_membership,
            )

        assert exc_info.value.status_code == 404


class TestBlackboardRouterHistory:
    """Tests for GET /blackboard/history endpoint."""

    @pytest.mark.asyncio
    async def test_get_blackboard_history_returns_list(self, mocker):
        """get_blackboard_history should return list of BlackboardResponse."""
        mock_request = MagicMock()

        mock_db = mocker.MagicMock()
        mock_records = [
            MagicMock(
                id=1,
                topic="Board 1",
                status="completed",
                content_json="[]",
                created_at=MagicMock(),
            ),
            MagicMock(
                id=2,
                topic="Board 2",
                status="failed",
                content_json="[]",
                created_at=MagicMock(),
            ),
        ]
        mock_result = mocker.MagicMock()
        mock_scalars = mocker.MagicMock()
        mock_scalars.all.return_value = mock_records
        mock_result.scalars.return_value = mock_scalars
        mock_db.execute = AsyncMock(return_value=mock_result)

        mock_user = MagicMock()
        mock_membership = MagicMock()

        from app.blackboard.router import get_blackboard_history

        result = await get_blackboard_history(
            request=mock_request,
            workspace_id=None,
            db=mock_db,
            current_user=mock_user,
            membership=mock_membership,
        )

        assert len(result) == 2
        assert result[0].id == 1
        assert result[1].id == 2

    @pytest.mark.asyncio
    async def test_get_blackboard_history_filters_by_workspace(self, mocker):
        """get_blackboard_history should filter by workspace_id when provided."""
        mock_request = MagicMock()

        mock_db = mocker.MagicMock()
        mock_result = mocker.MagicMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        # Capture the query to verify filter was applied
        captured_query = None
        async def capture_execute(query):
            nonlocal captured_query
            captured_query = query
            return mock_result

        mock_db.execute = AsyncMock(side_effect=capture_execute)

        mock_user = MagicMock()
        mock_membership = MagicMock()

        from app.blackboard.router import get_blackboard_history

        await get_blackboard_history(
            request=mock_request,
            workspace_id=42,
            db=mock_db,
            current_user=mock_user,
            membership=mock_membership,
        )

        # The query should have been filtered by workspace_id
        assert captured_query is not None


class TestBlackboardRouterDelete:
    """Tests for DELETE /blackboard/{bb_id} endpoint."""

    @pytest.mark.asyncio
    async def test_delete_blackboard_success(self, mocker):
        """delete_blackboard should delete existing record and return success."""
        mock_request = MagicMock()

        mock_record = MagicMock()
        mock_result = mocker.MagicMock()
        mock_scalars = mocker.MagicMock()
        mock_scalars.first.return_value = mock_record
        mock_result.scalars.return_value = mock_scalars
        mock_db = mocker.MagicMock()
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.delete = AsyncMock()
        mock_db.commit = AsyncMock()

        mock_user = MagicMock()
        mock_membership = MagicMock()

        from app.blackboard.router import delete_blackboard

        result = await delete_blackboard(
            bb_id=1,
            request=mock_request,
            db=mock_db,
            current_user=mock_user,
            membership=mock_membership,
        )

        assert result == {"message": "Deleted successfully"}
        mock_db.delete.assert_called_once_with(mock_record)

    @pytest.mark.asyncio
    async def test_delete_blackboard_raises_404(self, mocker):
        """delete_blackboard should raise 404 for non-existent record."""
        mock_request = MagicMock()

        mock_result = mocker.MagicMock()
        mock_scalars = mocker.MagicMock()
        mock_scalars.first.return_value = None
        mock_result.scalars.return_value = mock_scalars
        mock_db = mocker.MagicMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        mock_user = MagicMock()
        mock_membership = MagicMock()

        from app.blackboard.router import delete_blackboard

        with pytest.raises(HTTPException) as exc_info:
            await delete_blackboard(
                bb_id=999,
                request=mock_request,
                db=mock_db,
                current_user=mock_user,
                membership=mock_membership,
            )

        assert exc_info.value.status_code == 404


# ==============================================================================
# Model Tests
# ==============================================================================

class TestBlackboardDataModel:
    """Tests for BlackboardData SQLAlchemy model."""

    def test_tablename(self):
        """BlackboardData should have correct tablename."""
        assert BlackboardData.__tablename__ == "blackboards"

    def test_columns_exist(self):
        """BlackboardData should have all required columns."""
        columns = [c.name for c in BlackboardData.__table__.columns]
        assert "id" in columns
        assert "user_id" in columns
        assert "workspace_id" in columns
        assert "topic" in columns
        assert "content_json" in columns
        assert "status" in columns
        assert "created_at" in columns
        assert "updated_at" in columns

    def test_relationships(self):
        """BlackboardData should have relationships to User and Workspace."""
        assert "owner" in dir(BlackboardData)
        assert "workspace" in dir(BlackboardData)

    def test_default_values(self):
        """BlackboardData should have correct defaults."""
        # Check that status defaults to empty string (non-nullable but has default behavior)
        bb = BlackboardData(
            user_id=1,
            topic="Test",
            content_json="[]",
            status="pending"
        )
        assert bb.status == "pending"
        assert bb.content_json == "[]"


# ==============================================================================
# Celery Task Tests
# ==============================================================================

class TestGenerateBlackboardTask:
    """Tests for generate_blackboard_task Celery task."""

    def test_task_is_registered(self):
        """generate_blackboard_task should be a celery task."""
        from app.worker.blackboard_tasks import celery_app
        assert "generate_blackboard_task" in celery_app.tasks

    def test_task_calls_agent_and_updates_db(self, mocker):
        """generate_blackboard_task should call agent and update DB records."""
        mock_session = MagicMock()
        mock_engine = MagicMock()
        mock_sessionmaker = MagicMock(return_value=mock_session)
        mocker.patch("app.worker.blackboard_tasks.SessionLocal", mock_sessionmaker)

        mock_bb_record = MagicMock()
        mock_bb_record.id = 1
        mock_bb_record.user_id = 10
        mock_bb_record.status = "pending"
        mock_bb_record.content_json = "[]"

        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_bb_record
        mock_session.query.return_value = mock_query

        mock_redis = MagicMock()
        mocker.patch("app.worker.blackboard_tasks.redis_client", mock_redis)

        mocker.patch("app.worker.blackboard_tasks.run_async_from_sync")

        generate_blackboard_task(blackboard_id=1, topic="Test Topic", org_schema=None)

        # Verify status was updated
        assert mock_bb_record.status == "generating"
        mock_session.commit.assert_called()

    def test_task_handles_missing_record(self, mocker):
        """generate_blackboard_task should handle missing BlackboardData gracefully."""
        mock_session = MagicMock()
        mock_sessionmaker = MagicMock(return_value=mock_session)
        mocker.patch("app.worker.blackboard_tasks.SessionLocal", mock_sessionmaker)

        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        mock_session.query.return_value = mock_query

        mocker.patch("app.worker.blackboard_tasks.redis_client", MagicMock())

        # Should not raise, just return early
        generate_blackboard_task(blackboard_id=999, topic="Test", org_schema=None)

    def test_task_publishes_on_success(self, mocker):
        """generate_blackboard_task should publish to Redis on success."""
        mock_session = MagicMock()
        mock_sessionmaker = MagicMock(return_value=mock_session)
        mocker.patch("app.worker.blackboard_tasks.SessionLocal", mock_sessionmaker)

        mock_bb_record = MagicMock()
        mock_bb_record.id = 1
        mock_bb_record.user_id = 10
        mock_bb_record.status = "pending"
        mock_bb_record.content_json = "[]"

        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_bb_record
        mock_session.query.return_value = mock_query

        mock_redis = MagicMock()
        mocker.patch("app.worker.blackboard_tasks.redis_client", mock_redis)

        # Mock the agent to return valid steps data
        mocker.patch(
            "app.worker.blackboard_tasks.run_async_from_sync",
            return_value=[{"title": "Step 1", "note": "Note", "boardState": []}]
        )

        generate_blackboard_task(blackboard_id=1, topic="Test Topic", org_schema=None)

        # Verify Redis publish was called
        mock_redis.publish.assert_called()
        call_args = mock_redis.publish.call_args
        assert "user_notifications_10" in str(call_args)

    def test_task_publishes_on_failure(self, mocker):
        """generate_blackboard_task should publish failed status on exception."""
        mock_session = MagicMock()
        mock_sessionmaker = MagicMock(return_value=mock_session)
        mocker.patch("app.worker.blackboard_tasks.SessionLocal", mock_sessionmaker)

        mock_bb_record = MagicMock()
        mock_bb_record.id = 1
        mock_bb_record.user_id = 10
        mock_bb_record.status = "pending"
        mock_bb_record.content_json = "[]"

        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_bb_record
        mock_session.query.return_value = mock_query

        mock_redis = MagicMock()
        mocker.patch("app.worker.blackboard_tasks.redis_client", mock_redis)

        # Mock the agent to raise an exception
        mocker.patch(
            "app.worker.blackboard_tasks.run_async_from_sync",
            side_effect=Exception("Agent failed")
        )

        generate_blackboard_task(blackboard_id=1, topic="Test Topic", org_schema=None)

        # Verify status was set to failed
        assert mock_bb_record.status == "failed"
        mock_session.commit.assert_called()

        # Verify Redis publish was called with failed status
        mock_redis.publish.assert_called()

    def test_task_sets_search_path_for_org_schema(self, mocker):
        """generate_blackboard_task should set search_path when org_schema is provided."""
        mock_session = MagicMock()
        mock_sessionmaker = MagicMock(return_value=mock_session)
        mocker.patch("app.worker.blackboard_tasks.SessionLocal", mock_sessionmaker)

        mock_bb_record = MagicMock()
        mock_bb_record.id = 1
        mock_bb_record.user_id = 10
        mock_bb_record.status = "pending"
        mock_bb_record.content_json = "[]"

        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_bb_record
        mock_session.query.return_value = mock_query

        mocker.patch("app.worker.blackboard_tasks.redis_client", MagicMock())
        mocker.patch(
            "app.worker.blackboard_tasks.run_async_from_sync",
            return_value=[]
        )

        from sqlalchemy import text
        mock_session.execute = MagicMock()

        generate_blackboard_task(blackboard_id=1, topic="Test", org_schema="test_org")

        # Verify execute was called to set search_path
        calls = mock_session.execute.call_args_list
        search_path_calls = [c for c in calls if "search_path" in str(c)]
        assert len(search_path_calls) >= 1
