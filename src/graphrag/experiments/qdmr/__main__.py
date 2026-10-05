"""Run with python -m graphrag.experiments.qdmr [QUESTION ...]."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from .core import decompose


async def run(args: argparse.Namespace) -> int:
    from .codex_backend import CodexBackend, CodexError

    if args.backend == "codex":
        backend = CodexBackend(model=args.codex_model, timeout=args.codex_timeout)
        name = backend.name
    else:
        from .cli_backend import CliClient, LlmSettings
        from graphrag.llm.structured_output import LangChainStructuredOutput

        settings = LlmSettings()
        backend = LangChainStructuredOutput(CliClient(settings))
        name = settings.model_name
    if args.file:
        questions = Path(args.file).read_text(encoding="utf-8").splitlines()
    elif args.questions:
        questions = args.questions
    elif not sys.stdin.isatty():
        questions = sys.stdin
    else:
        print("Paste one question per line; blank line or Ctrl-D finishes.", file=sys.stderr)
        def interactive():
            while True:
                try:
                    question = input("question> ")
                except EOFError:
                    return
                if not question.strip():
                    return
                yield question
        questions = interactive()
    failed = False
    for question in questions:
        if not question.strip():
            continue
        try:
            result = await decompose(question, backend=backend, backend_name=name)
            if args.jsonl:
                print(result.model_dump_json())
            else:
                print(result.model_dump_json(indent=2))
        except Exception as error:
            failed = True
            # Provider exception text can contain request details or credentials.
            print(json.dumps({"question": question.strip(), "error": type(error).__name__,
                              "message": str(error) if isinstance(error, CodexError) else "Semantic analysis failed; check model connectivity, schema validity and exact source quotes."}),
                  file=sys.stderr)
    return int(failed)


def main() -> None:
    parser = argparse.ArgumentParser(description="Question semantics: concepts, meanings and establishment requirements. Defaults to your saved Codex login; --backend llm uses GraphRAG LLM settings.")
    parser.add_argument("questions", nargs="*", help="One or more quoted questions; otherwise interactive or stdin")
    parser.add_argument("--file", help="UTF-8 file with one question per line")
    parser.add_argument("--jsonl", action="store_true", help="One JSON result per line")
    parser.add_argument("--backend", choices=("codex", "llm"), default="codex")
    parser.add_argument("--codex-model", help="Optional Codex model; otherwise the CLI default")
    parser.add_argument("--codex-timeout", type=float, default=180, help="Seconds per question (default: 180)")
    args = parser.parse_args()
    if args.backend != "codex" and args.codex_model:
        parser.error("--codex-model requires --backend codex")
    if args.file and args.questions:
        parser.error("Use positional questions or --file, not both")
    try:
        code = asyncio.run(run(args))
    except KeyboardInterrupt:
        code = 130
    except Exception as error:
        from pydantic import ValidationError
        if isinstance(error, ValidationError):
            fields = sorted({".".join(map(str, item["loc"])) for item in error.errors(include_input=False)})
            print("Missing or invalid settings: " + ", ".join(fields), file=sys.stderr)
        from .codex_backend import CodexError
        message = str(error) if isinstance(error, CodexError) else f"Setup failed ({type(error).__name__}). Check backend options, configuration and input file."
        print(message, file=sys.stderr)
        code = 1
    raise SystemExit(code)


if __name__ == "__main__":
    main()
