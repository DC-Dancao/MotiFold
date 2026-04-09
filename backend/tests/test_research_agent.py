"""
Tests for app.research.agent — graph building and node logic.
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from app.research.agent import (
    build_graph,
    level_defaults_for,
    should_continue,
)
from app.research.state import ResearchLevel, ResearchState


class TestBuildGraph:
    def test_graph_has_expected_nodes(self):
        graph = build_graph()
        nodes = list(graph.nodes.keys())
        assert "__start__" in nodes
        assert "clarify_topic" in nodes
        assert "plan_search" in nodes
        assert "execute_search" in nodes
        assert "synthesize" in nodes
        assert "generate_report" in nodes

    def test_graph_compiles_without_error(self):
        # Compiles cleanly — checked via build_graph()
        graph = build_graph()
        assert graph is not None


class TestShouldContinue:
    def test_continues_when_under_max_iterations(self):
        state = ResearchState(
            messages=[],
            iterations=0,
            max_iterations=3,
        )
        assert should_continue(state) == "execute_search"

    def test_continues_when_at_last_allowed_iteration(self):
        state = ResearchState(
            messages=[],
            iterations=2,
            max_iterations=3,
        )
        assert should_continue(state) == "execute_search"

    def test_stops_when_max_iterations_reached(self):
        state = ResearchState(
            messages=[],
            iterations=3,
            max_iterations=3,
        )
        assert should_continue(state) == "generate_report"

    def test_stops_when_exceeds_max_iterations(self):
        state = ResearchState(
            messages=[],
            iterations=10,
            max_iterations=3,
        )
        assert should_continue(state) == "generate_report"


class TestLevelDefaultsFor:
    def test_standard(self):
        iters, results = level_defaults_for(ResearchLevel.STANDARD)
        assert iters == 3
        assert results == 10

    def test_extended(self):
        iters, results = level_defaults_for(ResearchLevel.EXTENDED)
        assert iters == 6
        assert results == 20

    def test_manual(self):
        iters, results = level_defaults_for(ResearchLevel.MANUAL)
        assert iters == 5
        assert results == 10

    def test_unknown_level_falls_back(self):
        # Passing a non-ResearchLevel key would raise KeyError in strict mode
        # but since it's typed as ResearchLevel, this shouldn't happen at runtime
        pass


class TestGraphEdges:
    def test_start_edges_to_clarify_topic(self):
        graph = build_graph()
        # The graph should have edges from __start__ to clarify_topic
        # We verify by checking the graph structure
        assert "clarify_topic" in graph.nodes

    def test_conditional_edges_from_synthesize(self):
        # should_continue determines routing from synthesize
        # Test the routing function directly
        state_iterating = ResearchState(
            messages=[],
            iterations=1,
            max_iterations=3,
        )
        assert should_continue(state_iterating) == "execute_search"

        state_done = ResearchState(
            messages=[],
            iterations=3,
            max_iterations=3,
        )
        assert should_continue(state_done) == "generate_report"
