"""
Unit tests for RAG features: BM25 search and cross-encoder reranking.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestCrossEncoderReranker:
    """Tests for CrossEncoderReranker class."""

    def test_reranker_init_default_model(self):
        """Test CrossEncoderReranker initializes with default model."""
        from app.memory.reranker import CrossEncoderReranker

        reranker = CrossEncoderReranker()
        assert reranker.model_name == "cross-encoder/ms-marco-MiniLM-L-6-v2"
        assert reranker._model is None  # Lazy loaded

    def test_reranker_init_custom_model(self):
        """Test CrossEncoderReranker accepts custom model."""
        from app.memory.reranker import CrossEncoderReranker

        reranker = CrossEncoderReranker(model_name="cross-encoder/ms-marco-MiniLM-L-12-v2")
        assert reranker.model_name == "cross-encoder/ms-marco-MiniLM-L-12-v2"

    def test_reranker_detect_cpu(self):
        """Test device detection falls back to CPU."""
        from app.memory.reranker import CrossEncoderReranker

        reranker = CrossEncoderReranker()
        with patch.dict('os.environ', {}, clear=True):
            device = reranker._detect_device()
            assert device == "cpu"

    def test_reranker_sigmoid(self):
        """Test sigmoid normalization."""
        from app.memory.reranker import CrossEncoderReranker

        reranker = CrossEncoderReranker()
        # sigmoid(0) = 0.5
        assert abs(reranker._sigmoid(0) - 0.5) < 0.01
        # sigmoid(large positive) ≈ 1
        assert reranker._sigmoid(10) > 0.99
        # sigmoid(large negative) ≈ 0
        assert reranker._sigmoid(-10) < 0.01

    @pytest.mark.asyncio
    async def test_rerank_empty_candidates(self):
        """Test rerank returns empty list for empty input."""
        from app.memory.reranker import CrossEncoderReranker

        reranker = CrossEncoderReranker()
        results = await reranker.rerank("test query", [])
        assert results == []

    @pytest.mark.asyncio
    async def test_rerank_single_candidate(self):
        """Test rerank with single candidate."""
        from app.memory.reranker import CrossEncoderReranker

        reranker = CrossEncoderReranker()
        # Mock the model
        mock_model = MagicMock()
        mock_model.predict.return_value = [0.95]
        reranker._model = mock_model

        candidates = [
            {"id": "1", "content": "This is a test document", "similarity": 0.8}
        ]
        results = await reranker.rerank("test query", candidates, top_k=5)

        assert len(results) == 1
        assert results[0]["id"] == "1"
        assert "cross_encoder_score" in results[0]
        assert "combined_score" in results[0]

    @pytest.mark.asyncio
    async def test_rerank_combines_scores(self):
        """Test rerank combines original similarity with cross-encoder score."""
        from app.memory.reranker import CrossEncoderReranker

        reranker = CrossEncoderReranker()
        mock_model = MagicMock()
        # Two candidates with different scores
        mock_model.predict.return_value = [0.9, 0.3]
        reranker._model = mock_model

        candidates = [
            {"id": "1", "content": "Relevant content", "similarity": 0.8},
            {"id": "2", "content": "Less relevant content", "similarity": 0.7},
        ]
        results = await reranker.rerank("query", candidates, top_k=2)

        assert len(results) == 2
        # First result should have higher combined score
        assert results[0]["combined_score"] > results[1]["combined_score"]
        # Combined score should be weighted: 0.3*original + 0.7*ce
        assert results[0]["combined_score"] == pytest.approx(
            0.3 * 0.8 + 0.7 * reranker._sigmoid(0.9), rel=0.01
        )

    @pytest.mark.asyncio
    async def test_rerank_respects_top_k(self):
        """Test rerank respects top_k limit."""
        from app.memory.reranker import CrossEncoderReranker

        reranker = CrossEncoderReranker()
        mock_model = MagicMock()
        mock_model.predict.return_value = [0.9, 0.8, 0.7, 0.6, 0.5]
        reranker._model = mock_model

        candidates = [
            {"id": str(i), "content": f"Document {i}", "similarity": 0.8 - i * 0.05}
            for i in range(5)
        ]
        results = await reranker.rerank("query", candidates, top_k=2)

        assert len(results) == 2

    def test_get_reranker_singleton(self):
        """Test get_reranker returns singleton."""
        from app.memory.reranker import get_reranker, _reranker_instance

        # Reset singleton for clean test
        import app.memory.reranker as reranker_module
        reranker_module._reranker_instance = None

        r1 = get_reranker()
        r2 = get_reranker()
        assert r1 is r2


class TestBM25Search:
    """Tests for BM25 keyword search in MemorySearch."""

    def test_tokenize_query(self):
        """Test query tokenization for tsquery."""
        from app.memory.search import MemorySearch

        mock_db = MagicMock()
        search = MemorySearch(mock_db)

        # Single word
        assert search._tokenize_query("hello") == "hello"
        # Multiple words
        tokens = search._tokenize_query("hello world")
        assert "hello" in tokens
        assert "world" in tokens
        # Special characters stripped
        tokens = search._tokenize_query("hello! world?")
        assert "hello" in tokens
        assert "world" in tokens

    def test_tokenize_query_empty(self):
        """Test tokenization of empty query."""
        from app.memory.search import MemorySearch

        mock_db = MagicMock()
        search = MemorySearch(mock_db)
        assert search._tokenize_query("") == ""
        assert search._tokenize_query("   ") == ""

    @pytest.mark.asyncio
    async def test_keyword_search_empty_query(self):
        """Test keyword search with empty query returns empty."""
        from app.memory.search import MemorySearch

        mock_db = AsyncMock()
        search = MemorySearch(mock_db)

        results = await search.keyword_search(workspace_id=1, query="")
        assert results == []

    @pytest.mark.asyncio
    async def test_keyword_search_no_bank(self):
        """Test keyword search returns empty when no bank exists."""
        from app.memory.search import MemorySearch

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        search = MemorySearch(mock_db)
        results = await search.keyword_search(workspace_id=999, query="test")

        assert results == []

    @pytest.mark.asyncio
    async def test_keyword_search_normalizes_scores(self):
        """Test keyword search normalizes BM25 scores to 0-1 range."""
        from app.memory.search import MemorySearch
        from unittest.mock import AsyncMock, MagicMock, patch

        mock_db = AsyncMock()
        search = MemorySearch(mock_db)

        # Mock bank exists
        mock_bank_result = MagicMock()
        mock_bank_result.scalar_one_or_none.return_value = MagicMock(id="bank-1")
        mock_db.execute.return_value = mock_bank_result

        # Mock query results with different ranks
        mock_query_result = MagicMock()
        mock_query_result.all.return_value = [
            (MagicMock(id="1", content="test content 1", extra_data={}, memory_type="fact"), 0.8),
            (MagicMock(id="2", content="test content 2", extra_data={}, memory_type="fact"), 0.4),
        ]

        with patch.object(search, 'db', mock_db):
            mock_db.execute.return_value = mock_query_result
            results = await search.keyword_search(workspace_id=1, query="test")

        # Scores should be normalized to 0-1
        assert len(results) == 2
        assert results[0]["similarity"] == 1.0  # 0.8 / 0.8 = 1.0
        assert results[1]["similarity"] == 0.5   # 0.4 / 0.8 = 0.5


class TestRAGRouterSchemas:
    """Tests for RAG API schemas."""

    def test_rag_ingest_request_schema(self):
        """Test RAGIngestRequest schema validation."""
        from app.memory.router import RAGIngestRequest
        from pydantic import ValidationError

        # Valid request
        req = RAGIngestRequest(report_id=123)
        assert req.report_id == 123

        # Missing report_id raises error
        with pytest.raises(ValidationError):
            RAGIngestRequest()

    def test_rag_query_request_schema(self):
        """Test RAGQueryRequest schema with defaults."""
        from app.memory.router import RAGQueryRequest

        # Default values
        req = RAGQueryRequest(query="test query")
        assert req.query == "test query"
        assert req.limit == 5
        assert req.use_reranker is True

        # Custom values
        req = RAGQueryRequest(query="test", limit=10, use_reranker=False)
        assert req.limit == 10
        assert req.use_reranker is False

    def test_rag_query_request_validation(self):
        """Test RAGQueryRequest limit bounds."""
        from app.memory.router import RAGQueryRequest
        from pydantic import ValidationError

        # limit must be >= 1
        with pytest.raises(ValidationError):
            RAGQueryRequest(query="test", limit=0)

        # limit must be <= 20
        with pytest.raises(ValidationError):
            RAGQueryRequest(query="test", limit=21)


class TestRAGIntegration:
    """Integration tests for RAG pipeline (without actual DB)."""

    def test_rag_pipeline_components_exist(self):
        """Test all RAG components can be imported."""
        from app.memory.reranker import CrossEncoderReranker, get_reranker
        from app.memory.search import MemorySearch
        from app.memory.fusion import rrf_fusion

        # All should be importable
        assert CrossEncoderReranker is not None
        assert get_reranker is not None
        assert MemorySearch is not None
        assert rrf_fusion is not None

    @pytest.mark.asyncio
    async def test_recall_with_reranker_param(self):
        """Test recall method signature accepts use_reranker."""
        from app.memory.service import MemoryService

        mock_db = MagicMock()
        service = MemoryService(mock_db)

        # Verify method accepts use_reranker parameter
        import inspect
        sig = inspect.signature(service.recall)
        params = list(sig.parameters.keys())
        assert "use_reranker" in params

    @pytest.mark.asyncio
    async def test_recall_multi_strategy_with_reranker(self):
        """Test multi-strategy recall accepts use_reranker param."""
        from app.memory.service import MemoryService

        mock_db = MagicMock()
        service = MemoryService(mock_db)

        import inspect
        sig = inspect.signature(service._recall_multi_strategy)
        params = list(sig.parameters.keys())
        assert "use_reranker" in params
