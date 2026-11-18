"""Replay acquired results through programmatic and model-based finding generation."""

import argparse
import asyncio
import json
from pathlib import Path

from pydantic import TypeAdapter

from graphrag.experiments.qdmr.codex_backend import CodexBackend, CodexError

from .evaluator import Case
from .replay import replay

DEMO = Path(__file__).with_name("publications.json")


async def run(args: argparse.Namespace) -> None:
    cases = TypeAdapter(list[Case]).validate_json((args.input or DEMO).read_bytes())
    if args.case:
        cases = [case for case in cases if case.id == args.case]
    if not cases:
        raise ValueError("No matching replay cases")
    backend = None
    if args.backend == "codex":
        backend = CodexBackend(model=args.model, timeout=args.timeout)
    elif args.backend == "llm":
        from graphrag.experiments.qdmr.cli_backend import CliClient, LlmSettings
        from graphrag.llm.structured_output import LangChainStructuredOutput

        settings = LlmSettings(**({"llm_model": args.model} if args.model else {}))
        backend = LangChainStructuredOutput(CliClient(settings))

    modes = ("model", "hybrid") if args.mode == "compare" else (args.mode,)
    for case in cases:
        for mode in modes:
            result = await replay(case, mode, backend, review=args.review)
            # One record per run. Preserve completed runs if a later provider call fails.
            print(json.dumps({"backend": args.backend, **result}, ensure_ascii=False), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, help="Replay cases in the bundled JSON format")
    parser.add_argument("--case", help="Run only this case ID")
    parser.add_argument("--mode", choices=("manual", "hybrid", "model", "compare"), default="manual")
    parser.add_argument("--backend", choices=("codex", "llm"))
    parser.add_argument("--model")
    parser.add_argument("--timeout", type=float, default=180, help="Codex timeout per call in seconds")
    parser.add_argument("--review", action="store_true")
    args = parser.parse_args()
    if (args.mode != "manual" or args.review) and not args.backend:
        parser.error("--backend is required for model binding, model findings, or review")
    if args.model and not args.backend:
        parser.error("--model requires --backend")
    try:
        asyncio.run(run(args))
    except (OSError, ValueError, CodexError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
