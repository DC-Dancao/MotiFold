# backend/tests/unit/test_research_tools.py
"""
Unit tests for app.research.tools — search and summarize functions.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.research.tools import (
    _web_search_impl as web_search,
    search_and_summarize,
    get_readable_text,
    summarize_content,
)


pytestmark = [pytest.mark.unit]


# --------------------------------------------------------------------------
# Mock result objects (similar to what googlesearch.search returns)
# --------------------------------------------------------------------------


class MockSearchResult:
    """Mock for googlesearch search result object with .title and .url."""

    def __init__(self, title: str, url: str):
        self.title = title
        self.url = url


# --------------------------------------------------------------------------
# Testget_readableText
# --------------------------------------------------------------------------


class TestGetReadableText:
    """get_readable_text fetches and strips HTML from a URL."""

    @pytest.mark.asyncio
    async def test_returns_text_content(self):
        """HTML is parsed and text is extracted."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(
            return_value="<html><body><p>Hello world</p></body></html>"
        )

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response), __aexit__=AsyncMock(return_value=None)))

        result = await get_readable_text("https://example.com", mock_session)
        assert "Hello world" in result

    @pytest.mark.asyncio
    async def test_returns_error_on_non_200(self):
        """Non-200 status returns an error message."""
        mock_response = AsyncMock()
        mock_response.status = 404

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response), __aexit__=AsyncMock(return_value=None)))

        result = await get_readable_text("https://example.com", mock_session)
        assert "404" in result


# --------------------------------------------------------------------------
# TestWebSearch
# --------------------------------------------------------------------------


class TestWebSearch:
    """web_search runs Google searches and fetches page content."""

    @pytest.mark.asyncio
    async def test_search_results_include_title_url_content(self):
        """web_search returns results with title, URL, and fetched content."""
        mock_results = [
            MockSearchResult(title="Example Site", url="https://example.com"),
            MockSearchResult(title="Another Site", url="https://example.org"),
        ]

        # search is a sync function — use regular MagicMock, not AsyncMock
        with patch("app.research.tools.search") as mock_search:
            mock_search.return_value = iter(mock_results)

            with patch("app.research.tools.get_readable_text", new_callable=AsyncMock) as mock_fetch:
                mock_fetch.side_effect = ["Example page content", "Another page content"]

                result = await web_search(queries=["test query"], max_results=2)

                assert "Example Site" in result
                assert "https://example.com" in result
                assert "Example page content" in result

    @pytest.mark.asyncio
    async def test_search_handles_empty_results(self):
        """Empty search results don't crash."""
        with patch("app.research.tools.search") as mock_search:
            mock_search.return_value = iter([])

            result = await web_search(queries=["nonexistent query"], max_results=5)
            assert "[]" in result or result == "[]"

    @pytest.mark.asyncio
    async def test_search_error_does_not_crash(self):
        """Search exception is caught and logged, returns empty."""
        with patch("app.research.tools.search") as mock_search:
            mock_search.side_effect = Exception("Network error")

            result = await web_search(queries=["test"], max_results=5)
            assert result == "[]"


# --------------------------------------------------------------------------
# TestSearchAndSummarize
# --------------------------------------------------------------------------


class TestSearchAndSummarize:
    """search_and_summarize runs searches, fetches content, and summarizes."""

    @pytest.mark.asyncio
    async def test_returns_summarized_results(self):
        """Results include query, title, url, summary, and key_excerpts."""
        mock_results = [
            MockSearchResult(title="AI Agents", url="https://example.com/ai"),
        ]

        # search is sync — must be regular MagicMock, not AsyncMock
        with patch("app.research.tools.search") as mock_search:
            mock_search.return_value = iter(mock_results)

            with patch("app.research.tools.get_readable_text", new_callable=AsyncMock) as mock_fetch:
                mock_fetch.return_value = "AI agents are software that can autonomously write code."

                with patch("app.research.tools.summarize_content", new_callable=AsyncMock) as mock_summarize:
                    from app.research.state import Summary
                    mock_summarize.return_value = Summary(
                        summary="AI agents automate code generation.",
                        key_excerpts="AI agents can write code autonomously.",
                    )

                    result = await search_and_summarize(
                        queries=["AI agents"],
                        max_results=5,
                    )

                    assert len(result) == 1
                    assert result[0]["title"] == "AI Agents"
                    assert result[0]["url"] == "https://example.com/ai"
                    assert result[0]["query"] == "AI agents"
                    assert "AI agents automate" in result[0]["summary"]

    @pytest.mark.asyncio
    async def test_multiple_queries_all_processed(self):
        """Multiple queries each get their own results."""
        mock_results_1 = [MockSearchResult(title="Site A", url="https://a.com")]
        mock_results_2 = [MockSearchResult(title="Site B", url="https://b.com")]

        call_count = 0

        # search is sync — must be regular function, not async
        def mock_search_fn(query, num_results, advanced):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return iter(mock_results_1)
            return iter(mock_results_2)

        with patch("app.research.tools.search", side_effect=mock_search_fn):
            with patch("app.research.tools.get_readable_text", new_callable=AsyncMock) as mock_fetch:
                mock_fetch.return_value = "Page content."

                with patch("app.research.tools.summarize_content", new_callable=AsyncMock) as mock_summarize:
                    from app.research.state import Summary
                    mock_summarize.return_value = Summary(summary="Summary.", key_excerpts="")

                    result = await search_and_summarize(
                        queries=["query A", "query B"],
                        max_results=5,
                    )

                    assert len(result) == 2
                    assert result[0]["query"] == "query A"
                    assert result[1]["query"] == "query B"

    @pytest.mark.asyncio
    async def test_search_error_returns_empty_for_that_query(self):
        """A failed search for one query doesn't crash the whole pipeline."""
        # search is sync — must be regular function, not async
        def mock_search_fn(query, num_results, advanced):
            if "fail" in query:
                raise Exception("Search failed")
            return iter([MockSearchResult(title="Success", url="https://success.com")])

        with patch("app.research.tools.search", side_effect=mock_search_fn):
            with patch("app.research.tools.get_readable_text", new_callable=AsyncMock) as mock_fetch:
                mock_fetch.return_value = "Content."

                with patch("app.research.tools.summarize_content", new_callable=AsyncMock) as mock_summarize:
                    from app.research.state import Summary
                    mock_summarize.return_value = Summary(summary="Summary.", key_excerpts="")

                    result = await search_and_summarize(
                        queries=["success query", "fail query"],
                        max_results=5,
                    )

                    assert len(result) == 1
                    assert result[0]["query"] == "success query"

    @pytest.mark.asyncio
    async def test_progress_callback_called(self):
        """Progress callback is invoked after each result."""
        mock_results = [
            MockSearchResult(title="Result 1", url="https://r1.com"),
            MockSearchResult(title="Result 2", url="https://r2.com"),
        ]

        # search is sync — must be regular MagicMock, not AsyncMock
        with patch("app.research.tools.search") as mock_search:
            mock_search.return_value = iter(mock_results)

            with patch("app.research.tools.get_readable_text", new_callable=AsyncMock) as mock_fetch:
                mock_fetch.return_value = "Content."

                with patch("app.research.tools.summarize_content", new_callable=AsyncMock) as mock_summarize:
                    from app.research.state import Summary
                    mock_summarize.return_value = Summary(summary="Summary.", key_excerpts="")

                    callback_calls = []

                    async def progress_callback(query, count):
                        callback_calls.append((query, count))

                    await search_and_summarize(
                        queries=["test query"],
                        max_results=5,
                        progress_callback=progress_callback,
                    )

                    assert len(callback_calls) == 2
                    assert callback_calls[0][1] == 1
                    assert callback_calls[1][1] == 2
