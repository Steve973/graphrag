import asyncio
import json
from pathlib import Path

import pytest

from graphrag.experiments.qdmr.codex_backend import CodexBackend, CodexError
from graphrag.experiments.qdmr.core import DecompositionDraft


@pytest.mark.parametrize("mode", ["success", "exit", "missing", "invalid", "timeout"])
def test_codex_subprocess_contract(monkeypatch, mode, semantic_payload):
    captured = {}
    monkeypatch.setattr("shutil.which", lambda value: "/usr/bin/codex")
    monkeypatch.setenv("OPENAI_API_KEY", "do-not-pass")
    monkeypatch.setenv("CODEX_API_KEY", "do-not-pass")

    class Process:
        returncode = None
        killed = False
        async def communicate(self, data):
            captured["prompt"] = data.decode()
            if mode == "timeout":
                await asyncio.sleep(10)
            self.returncode = 1 if mode == "exit" else 0
            if mode not in ("missing", "exit"):
                output = Path(captured["args"][captured["args"].index("--output-last-message") + 1])
                output.write_text(json.dumps(
                    {**semantic_payload, "requirements": []} if mode == "invalid" else semantic_payload
                ))
        def kill(self):
            self.killed = True
            self.returncode = -9
        async def wait(self):
            return self.returncode

    process = Process()
    async def spawn(*args, **kwargs):
        captured.update(args=args, kwargs=kwargs)
        schema = Path(args[args.index("--output-schema") + 1])
        assert "concepts" in json.loads(schema.read_text())["properties"]
        return process
    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    backend = CodexBackend(timeout=0.02 if mode == "timeout" else 1)
    call = backend.complete(messages=[{"role": "user", "content": "films; $(no shell)"}], response_model=DecompositionDraft)
    if mode == "success":
        assert asyncio.run(call).concepts[0].expression == "experts"
    else:
        with pytest.raises(CodexError):
            asyncio.run(call)
    assert captured["args"][-1] == "-"
    assert "read-only" in captured["args"]
    assert "--ignore-user-config" in captured["args"]
    assert "--ephemeral" in captured["args"]
    assert "films; $(no shell)" in captured["prompt"]
    assert "OPENAI_API_KEY" not in captured["kwargs"]["env"]
    assert "CODEX_API_KEY" not in captured["kwargs"]["env"]
    assert not Path(captured["kwargs"]["cwd"]).exists()
    if mode == "timeout":
        assert process.killed


def test_missing_cli(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda value: None)
    with pytest.raises(CodexError, match="not found"):
        CodexBackend()


@pytest.mark.parametrize("timeout", [0, -1, float("nan"), float("inf")])
def test_invalid_timeout(timeout):
    with pytest.raises(ValueError):
        CodexBackend(timeout=timeout)
