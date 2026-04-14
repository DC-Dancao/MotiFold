"""
Web search and scraping tools for the Deep Research agent.

Uses googlesearch for web search, aiohttp for async fetching,
and BeautifulSoup for parsing. All LLM calls use the centralized get_llm() factory.
"""

import asyncio
import logging
from datetime import datetime
from typing import Annotated, List

import aiohttp
import bs4
from googlesearch import search
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from app.llm.factory import get_llm
from app.research.state import ResearchState, Summary

logger = logging.getLogger(__name__)


def get_today_str() -> str:
    now = datetime.now()
    return f"{now:%a} {now:%b} {now.day}, {now:%Y}"


# =============================================================================
# Web Search Tool
# =============================================================================

WEB_SEARCH_DESCRIPTION = (
    "A search engine for comprehensive, accurate, and trusted results. "
    "Useful for when you need to answer questions about current events, "
    "factual queries, or detailed research topics."
)


async def get_readable_text(url: str, session: aiohttp.ClientSession) -> str:
    """Asynchronously fetch and parse readable text from a URL."""
    try:
        async with session.get(url, timeout=15) as response:
            if response.status != 200:
                return f"[Error: HTTP {response.status}]"
            html = await response.text()
            soup = bs4.BeautifulSoup(html, "html.parser")
            for script in soup(["script", "style"]):
                script.decompose()
            text = soup.get_text()
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            return "\n".join(chunk for chunk in chunks if chunk)
    except asyncio.TimeoutError:
        return "[Error: Request timed out]"
    except Exception as e:
        return f"[Error: {e}]"


async def _web_search_impl(
    queries: list[str],
    max_results: int,
) -> str:
    """
    Core web search logic — used by both the @tool wrapper and tests.
    """
    logger.info(f"--- web_search called with queries: {queries}, max_results: {max_results}")

    all_results = []

    async with aiohttp.ClientSession() as session:
        search_tasks = []
        query_results: dict[str, list] = {}

        for query in queries:
            try:
                results = await asyncio.to_thread(
                    search, query, num_results=max_results, advanced=True
                )
                query_results[query] = list(results)
                for result in query_results[query]:
                    search_tasks.append(get_readable_text(result.url, session))
            except Exception as e:
                logger.error(f"Google search failed for query '{query}': {e}")
                query_results[query] = []

        web_texts = await asyncio.gather(*search_tasks)

        result_idx = 0
        for query, results in query_results.items():
            for result in results:
                if result_idx < len(web_texts):
                    web_text = web_texts[result_idx]
                    all_results.append(
                        {
                            "query": query,
                            "title": result.title,
                            "url": result.url,
                            "content": web_text,
                        }
                    )
                    result_idx += 1

    return str(all_results)


@tool(description=WEB_SEARCH_DESCRIPTION)
async def web_search(
    queries: Annotated[List[str], "List of search queries to execute"],
    max_results: Annotated[int, "Max results per query"] = 10,
) -> str:
    """Tool wrapper for web search."""
    return await _web_search_impl(queries, max_results)


# =============================================================================
# URL Content Fetcher (for targeted page fetching)
# =============================================================================

async def fetch_url_content(url: str) -> str:
    """Fetch and parse readable text from a single URL."""
    async with aiohttp.ClientSession() as session:
        return await get_readable_text(url, session)


# =============================================================================
# Summarization
# =============================================================================

async def summarize_content(content: str, query: str) -> Summary:
    """
    Summarize a piece of content in the context of a research query.

    Args:
        content: The text content to summarize
        query: The research query this content relates to

    Returns:
        Summary object with summary and key_excerpts
    """
    if not content or len(content.strip()) < 50:
        return Summary(summary="[Content too short to summarize]", key_excerpts="")

    llm = get_llm(model_name="pro", temperature=0)
    summarizer = llm.with_structured_output(Summary, method="function_calling").with_retry(
        stop_after_attempt=3,
    )

    system_prompt = (
        "You are a research assistant. Given a piece of content and a research query, "
        "produce a concise summary and extract key excerpts that are relevant to the query.\n"
        "summary: A 2-3 sentence summary of the content.\n"
        "key_excerpts: 2-4 direct quotes or facts from the content most relevant to the query."
    )

    try:
        result = await summarizer.ainvoke(
            [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": f"Research query: {query}\n\nContent:\n{content[:8000]}",
                },
            ]
        )
        return result
    except Exception as e:
        logger.warning(f"Summarization failed: {e}")
        return Summary(
            summary=f"[Summary unavailable: {e}]",
            key_excerpts="",
        )


# =============================================================================
# Research Pipeline (search + summarize)
# =============================================================================

async def search_and_summarize(
    queries: list[str],
    max_results: int,
    progress_callback=None,
) -> list[dict]:
    """
    Execute searches and summarize results.

    Args:
        queries: Search queries
        max_results: Results per query
        progress_callback: Optional async callback(query, result_count)

    Returns:
        List of dicts with {query, title, url, summary, key_excerpts}
    """
    summarized = []

    async with aiohttp.ClientSession() as session:
        query_results: dict[str, list] = {}

        for query in queries:
            try:
                results = await asyncio.to_thread(
                    search, query, num_results=max_results, advanced=True
                )
                query_results[query] = list(results)
            except Exception as e:
                logger.error(f"Google search failed for '{query}': {e}")
                query_results[query] = []

        fetch_tasks = []
        result_map: list[tuple[str, object]] = []
        for query, results in query_results.items():
            for result in results:
                fetch_tasks.append(get_readable_text(result.url, session))
                result_map.append((query, result))

        web_texts = await asyncio.gather(*fetch_tasks)

        for (query, result), web_text in zip(result_map, web_texts):
            summary = await summarize_content(web_text, query)
            item = {
                "query": query,
                "title": result.title,
                "url": result.url,
                "summary": summary.summary,
                "key_excerpts": summary.key_excerpts,
            }
            summarized.append(item)
            if progress_callback:
                await progress_callback(query, len(summarized))

    return summarized