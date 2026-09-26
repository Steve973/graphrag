import asyncio
import copy
import json

import pytest
from litellm.types.utils import ModelResponse
from pydantic import ValidationError

from graphrag.experiments.qdmr import Decomposition, DecompositionDraft, decompose
from graphrag.llm.structured_output import LiteLlmStructuredOutput, StructuredOutputError


class Client:
    def __init__(self, data):
        self.data = data
        self.requests = []

    async def complete(self, **kwargs) -> ModelResponse:
        self.requests.append(kwargs)
        return ModelResponse(**{"choices": [{"message": {"tool_calls": [{"function": {
            "name": "return_structured_output", "arguments": json.dumps(self.data)
        }}]}}]})


def test_source_grounded_semantics_through_structured_adapter(semantic_payload, semantic_question):
    client = Client(semantic_payload)
    result = asyncio.run(decompose(semantic_question,
        backend=LiteLlmStructuredOutput(client), backend_name="test/model"))
    assert result.schema_version == "question-semantics/1"
    assert result.method == "llm_semantic_analysis"
    assert result.question == semantic_question
    assert result.decomposition.concepts[2].component_ids == ["c2", "c1"]
    assert result.decomposition.requirements[1].depends_on == ["r1"]
    assert "steps" not in result.model_dump()["decomposition"]
    assert "final_step_id" not in result.model_dump()
    request = client.requests[0]
    assert request["messages"][1]["content"] == semantic_question
    assert request["tool_choice"]["function"]["name"] == "return_structured_output"
    assert request["tools"][0]["function"]["parameters"]["additionalProperties"] is False


@pytest.mark.parametrize("change", [
    lambda d: d["concepts"][0].update(id="m1"),
    lambda d: d["concepts"][0].update(component_ids=["c1"]),
    lambda d: d["concepts"][0].update(component_ids=["c6"]),
    lambda d: d["concepts"][2].update(component_ids=["c1", "c1"]),
    lambda d: d["meanings"][0].update(concept_ids=["missing"]),
    lambda d: d["meanings"][0].update(source_quotes=[]),
    lambda d: d["requirements"][0].update(depends_on=["r2"]),
    lambda d: d["requirements"][1].update(depends_on=["r2"]),
    lambda d: d["requirements"][0].update(meaning_ids=["missing"]),
    lambda d: d["unresolved"][0].update(requirement_ids=["missing"]),
    lambda d: d.update(concepts=[]),
    lambda d: d.update(requirements=[]),
    lambda d: d.update(status="needs_clarification"),
    lambda d: d.update(steps=[]),
])
def test_invalid_semantic_references_rejected(semantic_payload, change):
    data = copy.deepcopy(semantic_payload)
    change(data)
    with pytest.raises(ValidationError):
        DecompositionDraft.model_validate(data)


@pytest.mark.parametrize("change", [
    lambda d: d["concepts"][0].update(expression="cardiologists"),
    lambda d: d["meanings"][0].update(source_quotes=["rank by citations"]),
    lambda d: d["unresolved"][0].update(source_quotes=["clinical experience"]),
])
def test_invented_source_text_rejected(semantic_payload, semantic_question, change):
    change(semantic_payload)
    with pytest.raises(ValidationError, match="source|Source"):
        Decomposition(question=semantic_question, backend="test", decomposition=semantic_payload)


def test_bad_backend_shape_fails_without_fabricated_output(semantic_payload, semantic_question):
    client = Client({**semantic_payload, "requirements": []})
    with pytest.raises(StructuredOutputError):
        asyncio.run(decompose(semantic_question, backend=LiteLlmStructuredOutput(client), backend_name="fake"))


def test_explicit_definition_remains_distinct_from_interpretation(semantic_payload, semantic_question):
    question = semantic_question + " An expert has at least four publications."
    semantic_payload["meanings"].extend([
        {"id": "m3", "kind": "definition", "statement": "Qualification requires at least four publications.", "concept_ids": ["c1"], "basis": "explicit", "source_quotes": ["An expert has at least four publications."]},
        {"id": "m4", "kind": "qualification", "statement": "Each distinct publication counts once.", "concept_ids": ["c1"], "basis": "interpretation", "source_quotes": ["four publications"]},
    ])
    result = Decomposition(question=question, backend="test", decomposition=semantic_payload)
    assert result.decomposition.meanings[-2].basis == "explicit"
    assert result.decomposition.meanings[-1].basis == "interpretation"


def test_unresolved_is_optional_without_a_routing_status(semantic_payload):
    semantic_payload["unresolved"] = []
    result = DecompositionDraft.model_validate(semantic_payload)
    assert result.unresolved == []
    assert "status" not in result.model_dump()


def test_empty_input_does_not_call_model(semantic_payload):
    client = Client(semantic_payload)
    with pytest.raises(ValueError):
        asyncio.run(decompose("  ", backend=LiteLlmStructuredOutput(client), backend_name="fake"))
    assert client.requests == []


def test_cli_needs_only_llm_configuration():
    from graphrag.experiments.qdmr.cli_backend import LlmSettings
    config = LlmSettings(_env_file=None, _secrets_dir=(),
        llm_url="http://localhost:8000/v1", llm_api_key="local",
        llm_model="provider/model", llm_provider="provider")
    assert config.model_name == "provider/model"


def test_cli_continues_after_failure(monkeypatch, capsys, tmp_path, semantic_payload, semantic_question):
    from argparse import Namespace
    from graphrag.experiments.qdmr import __main__ as cli
    from graphrag.experiments.qdmr import cli_backend
    config = cli_backend.LlmSettings(_env_file=None, _secrets_dir=(),
        llm_url="http://localhost:8000/v1", llm_api_key="local",
        llm_model="model", llm_provider="provider")
    monkeypatch.setattr(cli_backend, "LlmSettings", lambda: config)
    async def fake_decompose(question, **kwargs):
        if question == "bad":
            raise RuntimeError("secret must not be printed")
        return await decompose(question, backend=LiteLlmStructuredOutput(Client(semantic_payload)), backend_name="fake")
    monkeypatch.setattr(cli, "decompose", fake_decompose)
    path = tmp_path / "questions.txt"
    path.write_text("bad\n\n" + semantic_question + "\n", encoding="utf-8")
    assert asyncio.run(cli.run(Namespace(file=str(path), questions=[], jsonl=True, backend="llm"))) == 1
    output = capsys.readouterr()
    assert json.loads(output.out)["question"] == semantic_question
    assert json.loads(output.err)["error"] == "RuntimeError"
    assert "secret" not in output.err
