"""Run the offline example or clarify a question with an existing model backend."""

import argparse
import asyncio
import json
from pathlib import Path
import re
import sys
from uuid import uuid4

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from graphrag.experiments.qdmr.codex_backend import CodexBackend, CodexError

from . import demo
from .workflow import build_graph


def read_breakdown(path: Path) -> dict[int, str]:
    record = json.loads(path.read_text(encoding="utf-8"))
    steps = {}
    for line in record["steps"]:
        match = re.fullmatch(r"([1-9][0-9]*)\. (.+)", line)
        if match is None or int(match[1]) in steps:
            raise ValueError("The breakdown must contain unique numbered steps.")
        steps[int(match[1])] = match[2]
    return steps


async def run(args: argparse.Namespace) -> int:
    if args.demo:
        backend = demo.DemoBackend()
        question = demo.QUESTION
        context = demo.CONTEXT
        steps = demo.BREAKDOWN
    else:
        question = args.question
        context = args.context
        steps = read_breakdown(args.breakdown) if args.breakdown else {}
        if args.backend == "codex":
            backend = CodexBackend(model=args.codex_model, timeout=args.codex_timeout)
        else:
            from graphrag.experiments.qdmr.cli_backend import CliClient, LlmSettings
            from graphrag.llm.structured_output import LangChainStructuredOutput

            backend = LangChainStructuredOutput(CliClient(LlmSettings()))
    graph = build_graph(backend, checkpointer=InMemorySaver(), max_turns=args.max_turns)
    config = {
        "configurable": {"thread_id": str(uuid4())},
        "recursion_limit": 2 * args.max_turns + 4,
    }
    result = await graph.ainvoke({
        "question": question,
        "datasource_context": context,
        "breakdown_steps": steps,
        "unknown_hints": args.hint,
    }, config)
    while pending := result.get("__interrupt__"):
        clarification = pending[0].value
        if args.demo:
            answer = demo.ANSWERS[clarification["item_id"]]
        else:
            print(clarification["question"], file=sys.stderr)
            try:
                answer = input()
            except EOFError:
                print("Input ended with clarification still pending.", file=sys.stderr)
                return 1
        result = await graph.ainvoke(Command(resume=answer), config)

    print(json.dumps({
        "mode": "scripted-demo" if args.demo else args.backend,
        **{key: result[key] for key in ("question", "breakdown_steps", "status", "note", "turns", "pool", "observations")},
    }, indent=2, ensure_ascii=False))
    return int(result["status"] != "ready")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--demo", action="store_true", help="Run a scripted offline example")
    source.add_argument("--question", help="Clarify a question with a model and user replies")
    parser.add_argument("--context", action="append", default=[], help="Datasource observation, repeatable")
    parser.add_argument("--breakdown", type=Path, help="One Hasson decoder JSON record")
    parser.add_argument("--hint", action="append", default=[], help="Known ambiguity candidate, repeatable")
    parser.add_argument("--backend", choices=("codex", "llm"), default="codex")
    parser.add_argument("--codex-model")
    parser.add_argument("--codex-timeout", type=float, default=180)
    parser.add_argument("--max-turns", type=int, default=24)
    args = parser.parse_args()
    if args.max_turns < 1:
        parser.error("--max-turns must be positive")
    if args.demo and (args.context or args.breakdown or args.hint):
        parser.error("--context, --breakdown and --hint require --question")
    try:
        raise SystemExit(asyncio.run(run(args)))
    except (CodexError, OSError, KeyError, TypeError, ValueError) as error:
        parser.exit(1, f"{error}\n")
    except KeyboardInterrupt:
        parser.exit(130)


if __name__ == "__main__":
    main()
