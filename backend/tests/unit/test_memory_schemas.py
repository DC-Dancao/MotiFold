"""
Unit tests for app.memory.schemas module.

Tests Memory schemas and validation.
"""
import pytest
from datetime import datetime
from pydantic import ValidationError

pytestmark = [pytest.mark.unit]


class TestMemoryCreate:
    """Tests for MemoryCreate schema."""

    def test_valid_memory_creation(self):
        """Should create MemoryCreate with valid data."""
        from app.memory.schemas import MemoryCreate

        memory = MemoryCreate(content="This is a fact")
        assert memory.content == "This is a fact"
        assert memory.memory_type == "fact"
        assert memory.metadata == {}

    def test_custom_memory_type(self):
        """Should accept custom memory types."""
        from app.memory.schemas import MemoryCreate

        memory = MemoryCreate(content="User preference", memory_type="preference")
        assert memory.memory_type == "preference"

    def test_valid_memory_types(self):
        """Should accept all valid memory types."""
        from app.memory.schemas import MemoryCreate

        for mem_type in ["fact", "preference", "conclusion", "context"]:
            memory = MemoryCreate(content="Test", memory_type=mem_type)
            assert memory.memory_type == mem_type

    def test_custom_metadata(self):
        """Should accept custom metadata dict."""
        from app.memory.schemas import MemoryCreate

        metadata = {"source": "chat", "confidence": 0.95}
        memory = MemoryCreate(content="Test", metadata=metadata)
        assert memory.metadata == metadata

    def test_empty_content_rejected(self):
        """Should reject empty content."""
        from app.memory.schemas import MemoryCreate

        with pytest.raises(ValidationError):
            MemoryCreate(content="")


class TestMemoryRecallResult:
    """Tests for MemoryRecallResult schema."""

    def test_valid_recall_result(self):
        """Should create MemoryRecallResult with valid data."""
        from app.memory.schemas import MemoryRecallResult

        result = MemoryRecallResult(
            id="mem-123",
            content="Recalled fact",
            memory_type="fact",
            similarity=0.95
        )
        assert result.id == "mem-123"
        assert result.similarity == 0.95

    def test_default_metadata(self):
        """Should have empty dict as default metadata."""
        from app.memory.schemas import MemoryRecallResult

        result = MemoryRecallResult(
            id="mem-123",
            content="Test",
            memory_type="fact",
            similarity=0.5
        )
        assert result.metadata == {}


class TestBankConfig:
    """Tests for BankConfig schema."""

    def test_default_dispositions(self):
        """Should have default disposition values of 3."""
        from app.memory.schemas import BankConfig

        config = BankConfig()
        assert config.disposition_skepticism == 3
        assert config.disposition_literalism == 3
        assert config.disposition_empathy == 3

    def test_custom_dispositions(self):
        """Should accept custom disposition values."""
        from app.memory.schemas import BankConfig

        config = BankConfig(
            disposition_skepticism=5,
            disposition_literalism=1,
            disposition_empathy=4
        )
        assert config.disposition_skepticism == 5
        assert config.disposition_literalism == 1
        assert config.disposition_empathy == 4

    def test_mission_statements(self):
        """Should accept optional mission statements."""
        from app.memory.schemas import BankConfig

        config = BankConfig(
            retain_mission="Remember everything",
            reflect_mission="Think deeply"
        )
        assert config.retain_mission == "Remember everything"
        assert config.reflect_mission == "Think deeply"


class TestRecallResponse:
    """Tests for RecallResponse schema."""

    def test_valid_recall_response(self):
        """Should create RecallResponse with results."""
        from app.memory.schemas import RecallResponse, MemoryRecallResult

        result1 = MemoryRecallResult(
            id="mem-1",
            content="Fact 1",
            memory_type="fact",
            similarity=0.95
        )
        result2 = MemoryRecallResult(
            id="mem-2",
            content="Fact 2",
            memory_type="fact",
            similarity=0.85
        )

        response = RecallResponse(
            results=[result1, result2],
            total=2,
            query="test query"
        )
        assert len(response.results) == 2
        assert response.total == 2
        assert response.query == "test query"


class TestRetainResponse:
    """Tests for RetainResponse schema."""

    def test_valid_retain_response(self):
        """Should create RetainResponse with all fields."""
        from app.memory.schemas import RetainResponse

        now = datetime.now()
        response = RetainResponse(
            memory_id="mem-123",
            workspace_id=1,
            memory_type="fact",
            created_at=now
        )
        assert response.memory_id == "mem-123"
        assert response.workspace_id == 1


class TestMemoryRecentItem:
    """Tests for MemoryRecentItem schema."""

    def test_optional_mentioned_at(self):
        """mentioned_at should be optional."""
        from app.memory.schemas import MemoryRecentItem

        item = MemoryRecentItem(
            id="mem-123",
            content="Recent fact",
            memory_type="fact",
            created_at=datetime.now()
        )
        assert item.mentioned_at is None

    def test_with_mentioned_at(self):
        """Should accept mentioned_at datetime."""
        from app.memory.schemas import MemoryRecentItem

        now = datetime.now()
        item = MemoryRecentItem(
            id="mem-123",
            content="Fact",
            memory_type="fact",
            created_at=now,
            mentioned_at=now
        )
        assert item.mentioned_at == now


class TestRecentMemoriesResponse:
    """Tests for RecentMemoriesResponse schema."""

    def test_valid_recent_memories_response(self):
        """Should create RecentMemoriesResponse with memories list."""
        from app.memory.schemas import RecentMemoriesResponse, MemoryRecentItem

        item = MemoryRecentItem(
            id="mem-1",
            content="Recent fact",
            memory_type="fact",
            created_at=datetime.now()
        )

        response = RecentMemoriesResponse(memories=[item], total=1)
        assert len(response.memories) == 1
        assert response.total == 1


class TestMemoryBankInfo:
    """Tests for MemoryBankInfo schema."""

    def test_from_attributes_config(self):
        """Should have from_attributes = True for ORM compatibility."""
        from app.memory.schemas import MemoryBankInfo

        assert MemoryBankInfo.model_config["from_attributes"] is True

    def test_default_config(self):
        """Should have empty dict as default config."""
        from app.memory.schemas import MemoryBankInfo

        bank = MemoryBankInfo(
            id="bank-123",
            workspace_id=1,
            name="Test Bank",
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        assert bank.config == {}
