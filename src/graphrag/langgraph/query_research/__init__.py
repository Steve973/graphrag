"""Criterion research with parallel query workers and bounded supervisor review."""

from graphrag.langgraph.query_research.contracts import (
    ResearchCriterion,
    ResearchResult,
)
from graphrag.langgraph.query_research.graph import build_query_research_graph

__all__ = ["ResearchCriterion", "ResearchResult", "build_query_research_graph"]
