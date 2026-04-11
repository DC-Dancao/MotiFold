"""
Unit tests for MemoryService.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4


class TestRRFFusion:
    """Tests for RRF fusion function."""

    def test_rrf_fusion_empty(self):
        """Test RRF fusion with empty input."""
        from app.memory.fusion import rrf_fusion

        result = rrf_fusion([])
        assert result == []

    def test_rrf_fusion_single_list(self):
        """Test RRF fusion with single result list."""
        from app.memory.fusion import rrf_fusion

        results = [[{"id": "A", "score": 0.9}, {"id": "B", "score": 0.8}]]
        fused = rrf_fusion(results)

        assert len(fused) == 2
        ids = [r["id"] for r in fused]
        assert ids == ["A", "B"]

    def test_rrf_fusion_multiple_lists(self):
        """Test RRF fusion combines ranks from multiple strategies."""
        from app.memory.fusion import rrf_fusion

        semantic = [{"id": "A", "score": 0.9}, {"id": "B", "score": 0.8}]
        keyword = [{"id": "B", "score": 0.95}, {"id": "C", "score": 0.85}]
        graph = [{"id": "C", "score": 0.9}]

        fused = rrf_fusion([semantic, keyword, graph])

        ids = [r["id"] for r in fused]
        # B appears in 2 lists (semantic + keyword), should rank high
        # C appears in 2 lists (keyword + graph), should rank high
        # A appears in 1 list only, should rank lower
        assert "B" in ids
        assert "A" in ids
        assert "C" in ids
        # B and C should rank above A (B and C appear in more lists)
        assert ids.index("B") < ids.index("A") or ids.index("C") < ids.index("A")

    def test_rrf_fusion_with_k_parameter(self):
        """Test RRF fusion k parameter affects scoring."""
        from app.memory.fusion import rrf_fusion

        results = [[{"id": "A", "score": 0.9}]]
        fused_k1 = rrf_fusion(results, k=1)
        fused_k100 = rrf_fusion(results, k=100)

        assert fused_k1[0]["rrf_score"] == 1 / (1 + 0 + 1)  # = 0.5 for k=1
        assert fused_k100[0]["rrf_score"] == 1 / (100 + 0 + 1)  # ~= 0.01 for k=100


class TestEntityResolver:
    """Tests for EntityResolver class."""

    def test_entity_resolver_init(self):
        """Test EntityResolver initializes correctly."""
        from app.memory.entity import EntityResolver

        mock_db = MagicMock()
        resolver = EntityResolver(mock_db)

        assert resolver.db == mock_db

    @pytest.mark.asyncio
    async def test_find_similar_no_match(self):
        """Test find_similar returns None when no match found."""
        from app.memory.entity import EntityResolver

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_db.execute.return_value = mock_result

        resolver = EntityResolver(mock_db)
        result = await resolver.find_similar(uuid4(), "Test Entity")

        assert result is None
        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_resolve_exact_match(self):
        """Test resolve returns existing entity on exact match."""
        from app.memory.entity import EntityResolver

        mock_db = AsyncMock()
        entity_id = uuid4()

        # Mock _find_exact to return an ID
        mock_db.execute.return_value = MagicMock()
        mock_db.commit.return_value = None

        resolver = EntityResolver(mock_db)
        resolver._find_exact = AsyncMock(return_value=entity_id)

        result_id, was_created = await resolver.resolve(uuid4(), "Test Entity")

        assert result_id == entity_id
        assert was_created is False


class TestMemorySearch:
    """Tests for MemorySearch class."""

    def test_memory_search_init(self):
        """Test MemorySearch initializes correctly."""
        from app.memory.search import MemorySearch

        mock_db = MagicMock()
        search = MemorySearch(mock_db)

        assert search.db == mock_db

    @pytest.mark.asyncio
    async def test_keyword_search_no_bank(self):
        """Test keyword_search returns empty list when no bank exists."""
        from app.memory.search import MemorySearch

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        search = MemorySearch(mock_db)
        results = await search.keyword_search(workspace_id=999, query="test")

        assert results == []


class TestMemoryServiceHelpers:
    """Tests for MemoryService helper methods."""

    def test_extract_entities_simple(self):
        """Test simple entity extraction with capitalization heuristic."""
        from app.memory.service import MemoryService

        mock_db = MagicMock()
        mock_embedding = MagicMock()
        mock_embedding.encode.return_value = [[0.1] * 1024]

        service = MemoryService(mock_db)
        service.embedding = mock_embedding

        # Test with capitalized phrases (2+ consecutive capitalized words)
        content = "Zhang Wei works at Google in San Francisco"
        entities = service._extract_entities_simple(content)

        entity_names = [e["name"] for e in entities]
        # Google is single word, should not be extracted
        assert "Zhang Wei" in entity_names
        assert "Google" not in entity_names  # Single word, filtered out
        assert "San Francisco" in entity_names

    def test_extract_entities_simple_single_word(self):
        """Test simple entity extraction ignores single words."""
        from app.memory.service import MemoryService

        mock_db = MagicMock()
        mock_embedding = MagicMock()
        mock_embedding.encode.return_value = [[0.1] * 1024]

        service = MemoryService(mock_db)
        service.embedding = mock_embedding

        # Single words should be ignored
        content = "Hello world"
        entities = service._extract_entities_simple(content)

        # No entities since "Hello" and "World" are single words
        assert len(entities) == 0

    def test_extract_entities_simple_no_capitals(self):
        """Test simple entity extraction with no capitalized phrases."""
        from app.memory.service import MemoryService

        mock_db = MagicMock()
        mock_embedding = MagicMock()
        mock_embedding.encode.return_value = [[0.1] * 1024]

        service = MemoryService(mock_db)
        service.embedding = mock_embedding

        content = "this is all lowercase"
        entities = service._extract_entities_simple(content)

        assert len(entities) == 0


class TestMemoryLimitExceededError:
    """Tests for MemoryLimitExceededError exception."""

    def test_exception_message(self):
        """Test MemoryLimitExceededError message format."""
        from app.memory.service import MemoryLimitExceededError

        error = MemoryLimitExceededError("Workspace 1 has reached limit")
        assert "Workspace 1" in str(error)
        assert "limit" in str(error)

    def test_exception_is_exception(self):
        """Test MemoryLimitExceededError is an Exception subclass."""
        from app.memory.service import MemoryLimitExceededError

        assert issubclass(MemoryLimitExceededError, Exception)
