import asyncio
from unittest.mock import Mock

import pytest

from graphrag.experiments.qdmr.core import Decomposition
from gtd.gtd_grounding import SemanticReview, analyze_question, ground, validate_review


def fixture_breakdown(question, quote):
    return Decomposition.model_validate({
        "backend": "fixture",
        "question": question,
        "decomposition": {
            "concepts": [{
                "id": "c1", "expression": quote, "kind": "compound", "component_ids": [],
            }],
            "meanings": [{
                "id": "m1", "kind": "scope", "statement": quote, "concept_ids": ["c1"],
                "basis": "explicit", "source_quotes": [quote],
            }],
            "unresolved": [],
            "requirements": [{
                "id": "r1", "statement": quote, "meaning_ids": ["m1"], "depends_on": [],
            }],
        },
    })


def fixture_review(quote, kind, literal=None):
    return SemanticReview.model_validate({
        "issues": [],
        "probes": [{
            "meaning_id": "m1", "source_quote": quote, "kind": kind, "literal": literal,
        }],
    })


def test_review_rejects_probe_value_it_added():
    parsed = fixture_breakdown("How many incidents occurred in Spain?", "occurred in Spain")
    review = fixture_review("occurred in Spain", "incident_country", "France")
    with pytest.raises(ValueError, match="outside the cited source span"):
        validate_review(parsed, review)


def test_pipeline_stops_at_meaning_change_before_querying_graph():
    question = "How many incidents occurred in Spain or France?"
    parsed = fixture_breakdown(question, "Spain or France")
    review = SemanticReview.model_validate({
        "issues": [{
            "kind": "scope_change", "source_quote": "Spain or France",
            "explanation": "The disjunction was not represented in the proposed semantics.",
        }],
        "probes": [],
    })
    seen = []

    class Backend:
        async def complete(self, *, messages, response_model):
            seen.append(messages)
            return parsed.decomposition if len(seen) == 1 else review

    session = Mock()
    backend = Backend()
    report = asyncio.run(analyze_question(
        question, parser=backend, parser_name="fixture", reviewer=backend,
        session=session, encoder=Mock(),
    ))
    assert report["semantic_status"] == "review_failed"
    assert report["data_checks"] == []
    assert len(seen) == 2
    assert "source_quotes" in seen[1][1]["content"]
    session.run.assert_not_called()


def test_unresolved_semantics_stop_before_graph_check():
    parsed = fixture_breakdown("Which incidents were biggest?", "biggest")
    draft = parsed.model_dump()
    draft["decomposition"]["unresolved"] = [{
        "id": "u1", "statement": "The size measure is unspecified.",
        "concept_ids": ["c1"], "requirement_ids": ["r1"], "source_quotes": ["biggest"],
    }]
    session = Mock()
    report = ground(
        Decomposition.model_validate(draft), SemanticReview(issues=[], probes=[]),
        session=session, encoder=Mock(),
    )
    assert report["semantic_status"] == "unresolved"
    session.run.assert_not_called()
