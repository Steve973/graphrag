import pytest


@pytest.fixture
def semantic_question():
    return "Show me the top five foremost experts in feline cardiomyopathy."


@pytest.fixture
def semantic_payload():
    return {
        "concepts": [
            {"id": "c1", "expression": "experts", "kind": "entity", "component_ids": []},
            {"id": "c2", "expression": "foremost", "kind": "qualifier", "component_ids": []},
            {"id": "c3", "expression": "foremost experts", "kind": "compound", "component_ids": ["c2", "c1"]},
            {"id": "c4", "expression": "feline", "kind": "qualifier", "component_ids": []},
            {"id": "c5", "expression": "cardiomyopathy", "kind": "domain", "component_ids": []},
            {"id": "c6", "expression": "feline cardiomyopathy", "kind": "compound", "component_ids": ["c4", "c5"]},
            {"id": "c7", "expression": "top five", "kind": "quantity", "component_ids": []},
        ],
        "meanings": [
            {"id": "m1", "kind": "requested_result", "statement": "The requested result is five foremost experts in feline cardiomyopathy.", "concept_ids": ["c3", "c6", "c7"], "basis": "explicit", "source_quotes": ["top five foremost experts in feline cardiomyopathy"]},
            {"id": "m2", "kind": "relationship", "statement": "Expertise is restricted to feline cardiomyopathy.", "concept_ids": ["c1", "c6"], "basis": "explicit", "source_quotes": ["experts in feline cardiomyopathy"]},
        ],
        "requirements": [
            {"id": "r1", "statement": "The meanings of the domain, expertise and foremost must be established in context.", "meaning_ids": ["m1", "m2"], "depends_on": []},
            {"id": "r2", "statement": "Which entities satisfy the requested qualification and ranking must be established.", "meaning_ids": ["m1", "m2"], "depends_on": ["r1"]},
        ],
        "unresolved": [
            {"id": "u1", "statement": "The qualification and ranking criteria are unspecified.", "concept_ids": ["c1", "c2"], "requirement_ids": ["r1", "r2"], "source_quotes": ["foremost experts"]},
        ],
    }
