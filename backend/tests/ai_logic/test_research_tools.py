# backend/tests/ai_logic/test_research_tools.py
"""
AI logic tests for app.research.tools — web search and summarization.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from app.research.state import Summary

pytestmark = [pytest.mark.ai_logic, pytest.mark.asyncio]


class TestSummarizeContent:
    """Tests for summarize_content function."""

    @pytest.mark.asyncio
    @patch("app.research.tools.get_llm")
    async def test_summarize_content_short_text(self, mock_get_llm):
        """Content too short returns placeholder."""
        from app.research.tools import summarize_content

        result = await summarize_content("Too short", "test query")
        assert result.summary == "[Content too short to summarize]"
        mock_get_llm.assert_not_called()

    @pytest.mark.asyncio
    @patch("app.research.tools.get_llm")
    async def test_summarize_content_success(self, mock_get_llm):
        """Valid content is summarized via LLM."""
        from app.research.tools import summarize_content

        mock_model = MagicMock()
        mock_structured = MagicMock()
        mock_structured.ainvoke = AsyncMock(return_value=Summary(
            summary="AI is changing software development.",
            key_excerpts="Source: https://example.com",
        ))
        mock_model.with_structured_output.return_value.with_retry.return_value = mock_structured
        mock_get_llm.return_value = mock_model

        content = "A" * 200  # longer than 50 chars
        result = await summarize_content(content, "AI impact on jobs")

        assert "AI" in result.summary
        mock_model.with_structured_output.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.research.tools.get_llm")
    async def test_summarize_content_llm_error(self, mock_get_llm):
        """LLM errors return fallback summary."""
        from app.research.tools import summarize_content

        mock_model = MagicMock()
        mock_structured = MagicMock()
        mock_structured.ainvoke = AsyncMock(side_effect=Exception("LLM failed"))
        mock_model.with_structured_output.return_value.with_retry.return_value = mock_structured
        mock_get_llm.return_value = mock_model

        result = await summarize_content("A" * 200, "test")

        assert "[Summary unavailable" in result.summary


class TestFetchUrlContent:
    """Tests for fetch_url_content."""

    @pytest.mark.asyncio
    async def test_fetch_url_content_http_error(self):
        """Non-200 status returns error message."""
        from app.research.tools import get_readable_text

        mock_response = AsyncMock()
        mock_response.status = 404
        mock_response.text = AsyncMock(return_value="Not found")

        # async with session.get(...) as response:
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_response)
        mock_cm.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.get.return_value = mock_cm

        result = await get_readable_text("https://example.com/notfound", mock_session)
        assert "404" in result

    @pytest.mark.asyncio
    async def test_fetch_url_content_success(self):
        """Valid content is fetched successfully."""
        from app.research.tools import get_readable_text

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value="<html><body>Hello World</body></html>")

        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_response)
        mock_cm.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.get.return_value = mock_cm

        result = await get_readable_text("https://example.com/page", mock_session)
        assert "Hello World" in result

    @pytest.mark.asyncio
    async def test_fetch_url_content_timeout(self):
        """Timeout returns error message."""
        from app.research.tools import get_readable_text
        import asyncio

        mock_session = MagicMock()
        mock_session.get.side_effect = asyncio.TimeoutError()

        result = await get_readable_text("https://example.com/slow", mock_session)
        assert "timed out" in result.lower()

    @pytest.mark.asyncio
    async def test_fetch_url_content_exception(self):
        """Generic exception returns error message."""
        from app.research.tools import get_readable_text

        mock_session = MagicMock()
        mock_session.get.side_effect = Exception("Network error")

        result = await get_readable_text("https://example.com/broken", mock_session)
        assert "Error" in result


class TestSearchAndSummarize:
    """Tests for search_and_summarize."""

    @pytest.mark.asyncio
    @patch("app.research.tools.DDGS")
    @patch("app.research.tools.get_llm")
    @patch("aiohttp.ClientSession")
    async def test_search_and_summarize_no_results(self, mock_session_cls, mock_get_llm, mock_ddgs):
        """Empty search results return empty list."""
        from app.research.tools import search_and_summarize

        mock_ddgs_instance = MagicMock()
        mock_ddgs_instance.text.return_value = []
        mock_ddgs.return_value.__enter__.return_value = mock_ddgs_instance

        result = await search_and_summarize(["test query"], max_results=5)
        assert result == []

    @pytest.mark.asyncio
    @patch("app.research.tools.DDGS")
    @patch("app.research.tools.get_llm")
    @patch("aiohttp.ClientSession")
    async def test_search_and_summarize_with_results(self, mock_session_cls, mock_get_llm, mock_ddgs):
        """Results are fetched and summarized."""
        from app.research.tools import search_and_summarize

        # Mock search results
        mock_result = MagicMock()
        mock_result.title = "Example"
        mock_result.url = "https://example.com"
        mock_result.desc = "Example description"
        mock_ddgs_instance = MagicMock()
        mock_ddgs_instance.text.return_value = [mock_result]
        mock_ddgs.return_value.__enter__.return_value = mock_ddgs_instance

        # Mock aiohttp session
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value="Example content here about AI")
        mock_session = AsyncMock()
        mock_session.get.return_value.__aenter__.return_value = mock_response
        mock_session_cls.return_value.__aenter__.return_value = mock_session

        # Mock LLM summarization
        mock_model = MagicMock()
        mock_structured = MagicMock()
        mock_structured.ainvoke = AsyncMock(return_value=Summary(
            summary="Example page about AI.",
            key_excerpts="AI is mentioned.",
        ))
        mock_model.with_structured_output.return_value.with_retry.return_value = mock_structured
        mock_get_llm.return_value = mock_model

        result = await search_and_summarize(["AI news"], max_results=5)

        assert len(result) == 1
        assert result[0]["title"] == "Example"
        assert result[0]["url"] == "https://example.com"
        assert "Example page" in result[0]["summary"]


class TestProgressCallback:
    """Tests that progress_callback is called correctly."""

    @pytest.mark.asyncio
    @patch("app.research.tools.DDGS")
    @patch("app.research.tools.get_llm")
    @patch("aiohttp.ClientSession")
    async def test_progress_callback_called(self, mock_session_cls, mock_get_llm, mock_ddgs):
        """Progress callback is invoked for each result."""
        from app.research.tools import search_and_summarize

        mock_result = MagicMock()
        mock_result.title = "Test"
        mock_result.url = "https://test.com"
        mock_result.desc = "Test description"
        mock_ddgs_instance = MagicMock()
        mock_ddgs_instance.text.return_value = [mock_result]
        mock_ddgs.return_value.__enter__.return_value = mock_ddgs_instance

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value="Test content " * 50)
        mock_session = AsyncMock()
        mock_session.get.return_value.__aenter__.return_value = mock_response
        mock_session_cls.return_value.__aenter__.return_value = mock_session

        mock_model = MagicMock()
        mock_structured = MagicMock()
        mock_structured.ainvoke = AsyncMock(return_value=Summary(
            summary="Test summary.",
            key_excerpts="Key fact.",
        ))
        mock_model.with_structured_output.return_value.with_retry.return_value = mock_structured
        mock_get_llm.return_value = mock_model

        callback_calls = []
        async def progress(query, count):
            callback_calls.append((query, count))

        result = await search_and_summarize(["test"], max_results=5, progress_callback=progress)

        assert len(callback_calls) == 1
        assert callback_calls[0][0] == "test"
        assert callback_calls[0][1] == 1
