import asyncio
import json

import pytest
from pydantic import TypeAdapter

from graphrag.experiments.findings.__main__ import DEMO
from graphrag.experiments.findings.evaluator import (
    Case,
    EvaluationError,
    child_pointer,
    evaluate,
    infer_schema,
    load_rows,
    resolve_pointer,
)
from graphrag.experiments.findings.replay import Bindings, Proposals, Verdicts, replay


@pytest.fixture
def cases():
    return TypeAdapter(list[Case]).validate_json(DEMO.read_bytes())


def test_replay_structured_findings_and_partial_coverage(cases):
    for case in cases:
        run = asyncio.run(replay(case, "manual", None))
        assert run["model_calls"] == 0
        assert all(
            all(checks.values())
            for key, checks in run["candidate_scores"].items()
            if run["paths"][key] == "programmatic"
        )
        for finding in run["candidate_findings"]:
            for pointer in finding["pointers"]:
                resolve_pointer(case.result.data, pointer)
    assert run["candidate_scores"]["no-inference-from-empty"] == {"relation": True}


def test_schema_and_pointer_preserve_original_shape():
    payload = {"a/b~c": [{"x": True}, {"x": 1}, {"x": None}, {"y": "other"}]}
    rows = payload["a/b~c"]
    schema = {field.name: field for field in infer_schema(rows)}
    assert schema["x"].types == ["boolean", "integer", "null"]
    assert schema["x"].missing == 1
    assert resolve_pointer(payload, child_pointer(child_pointer("", "a/b~c"), 2)) == {"x": None}
    with pytest.raises(EvaluationError):
        resolve_pointer(payload, "/a~1b~0c/01")
    with pytest.raises(EvaluationError):
        resolve_pointer(payload, "/a~1b~2c/1")


def test_boolean_is_not_a_numeric_operand(cases):
    case = cases[0]
    original = load_rows(case)
    modified = [{**original[0], "year": True}, *original[1:]]
    assertion = case.assertions[0]
    with pytest.raises(EvaluationError, match="Incompatible operands"):
        evaluate(case, assertion, assertion.expression, modified, infer_schema(modified))


def test_binding_fallback_and_review(cases):
    case = cases[0]

    class Backend:
        async def complete(self, *, messages, response_model):
            payload = json.loads(messages[1]["content"])
            if response_model is Bindings:
                assert "data" not in payload
                original = case.assertions[0].expression.model_dump(mode="json")
                return Bindings.model_validate({"items": [
                    {"assertion_id": "publication-count", "expression": original, "reason": "Count unique IDs"},
                    {"assertion_id": "higher-threshold", "expression": {**original, "field": "nonexistent"},
                     "reason": "Exercise invalid field fallback"},
                    {"assertion_id": "field-trial", "expression": None, "reason": "Read the abstract"},
                ]})
            if response_model is Proposals:
                assert {item["id"] for item in payload["assertions"]} == {"higher-threshold", "field-trial"}
                return Proposals.model_validate({"items": [
                    {"assertion_id": "higher-threshold", "relation": "CONTRADICTS",
                     "statement": "Two distinct papers qualify.", "pointers": ["/rows", "/rows/0", "/rows/2"],
                     "value": 2},
                    {"assertion_id": "field-trial", "relation": "SUPPORTS",
                     "statement": "Authors ran a randomized field trial.", "pointers": ["/rows/0"], "value": None},
                    {"assertion_id": "field-trial", "relation": "SUPPORTS",
                     "statement": "Invalid reference.", "pointers": ["/rows/99"], "value": None},
                ]})
            assert response_model is Verdicts
            assert len(payload["findings"]) == 3
            assert payload["findings"][0]["expression"]["reduce"] == "count_distinct"
            assert "cited_data" in payload["findings"][2]
            return Verdicts.model_validate({
                "items": [
                    {"finding_index": index, "accept": index != 1, "reason": "Scripted review"}
                    for index in range(3)
                ]
            })

    run = asyncio.run(replay(case, "hybrid", Backend(), review=True))
    assert run["model_calls"] == 3
    assert run["paths"] == {"publication-count": "programmatic", "higher-threshold": "model", "field-trial": "model"}
    assert all(all(checks.values()) for checks in run["candidate_scores"].values())
    assert len(run["accepted_findings"]) == 2
    assert run["reviewed_scores"]["higher-threshold"]["relation"] is False
    assert any("Unknown fields" in msg for msg in run["diagnostics"])
    assert any("Invalid model citation" in msg for msg in run["diagnostics"])
