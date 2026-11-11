"""Run the upstream decoding code in a temporary Python import tree."""

import ast
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from zipfile import ZipFile


def write_source(path: Path, source: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


def stage_support_modules(upstream: Path, target: Path) -> None:
    # Load only definitions used by decoding. The surrounding modules eagerly
    # initialize spaCy, WordNet and evaluation components.
    files = [
        (
            "scripts/qdmr_to_logical_form/operator_identifier.py",
            "from enum import Enum",
            ("QDMROperator", "ArgumentType"),
            "def _get_variations",
        ),
        (
            "scripts/data_processing/break_app_store_generation.py",
            "from typing import List",
            ("get_additional_resources",),
            None,
        ),
    ]
    for relative_path, imports, names, end_marker in files:
        source = (upstream / relative_path).read_text(encoding="utf-8")
        if end_marker:
            source = source[:source.index(end_marker)]
        definitions = {
            node.name: ast.get_source_segment(source, node)
            for node in ast.parse(source).body
            if isinstance(node, ast.ClassDef | ast.FunctionDef)
        }
        selected = "\n\n".join(definitions[name] for name in names)
        write_source(target / relative_path, f"{imports}\n\n{selected}\n")

    relative_path = "evaluation/normal_form/normalized_graph_matcher.py"
    source = (upstream / relative_path).read_text(encoding="utf-8")
    matcher = next(
        node for node in ast.parse(source).body
        if isinstance(node, ast.ClassDef) and node.name == "NormalizedGraphMatchScorer"
    )
    reorder = next(
        node for node in matcher.body
        if isinstance(node, ast.FunctionDef) and node.name == "reorder"
    )
    method = "\n".join(source.splitlines()[reorder.decorator_list[0].lineno - 1 : reorder.end_lineno])
    write_source(
        target / relative_path,
        "import re\nfrom typing import Dict\nimport networkx as nx\n"
        "from utils.graph import reorder_by_level\n\n"
        f"class NormalizedGraphMatchScorer:\n{method}\n",
    )


def stage_decoder(upstream: Path, target: Path) -> None:
    decoder_root = "dependencies_graph/extractors"
    token_decoder = f"{decoder_root}/tokens_dependencies_extractors"
    spans_decoder = f"{decoder_root}/tokens_dependencies_to_qdmr_extractors"
    paths = [
        *sorted((upstream / "dependencies_graph/data_types").glob("*.py")),
        *sorted((upstream / token_decoder).rglob("*.py")),
        *sorted((upstream / spans_decoder).rglob("*.py")),
        upstream / decoder_root / "spans_dependencies_extractors/base_spans_dependencies_extractor.py",
        upstream / "evaluation/decomposition.py",
        upstream / "utils/graph.py",
        upstream / "utils/data_structures.py",
    ]
    for source_file in paths:
        relative_path = source_file.relative_to(upstream)
        source = source_file.read_text(encoding="utf-8")
        source = source.replace("from overrides import overrides", "from typing import override as overrides")
        source = source.replace("from queue import Queue, deque", "from collections import deque\nfrom queue import Queue")
        source = source.replace("from spacy import displacy\n", "")
        source = source.replace("    svg = displacy.render", "    from spacy import displacy\n\n    svg = displacy.render")
        source = source.replace("import matplotlib.pyplot as plt\n", "")
        source = source.replace(
            "def draw_decomposition_graph(graph, title=None, pos=None):",
            "def draw_decomposition_graph(graph, title=None, pos=None):\n    import matplotlib.pyplot as plt",
        )
        source = source.replace("import more_itertools as mit", "from itertools import groupby")
        source = source.replace(
            "    for group in mit.consecutive_groups(sorted(iterable)):\n        group = list(group)",
            "    for _, run in groupby(enumerate(sorted(iterable)), key=lambda item: item[1] - item[0]):\n"
            "        group = [value for _, value in run]",
        )
        if relative_path == Path("evaluation/decomposition.py"):
            source = source.replace(r", '#\g<1>'", r", r'#\g<1>'")
            source = source.replace(r'"@@\g<1>@@"', r'r"@@\g<1>@@"')
        write_source(target / relative_path, source)

    stage_support_modules(upstream, target)
    (target / decoder_root / "spans_dependencies_extractors/__init__.py").write_text(
        "from .base_spans_dependencies_extractor import BaseSpansDependenciesExtractor\n",
        encoding="utf-8",
    )


def load_rows(upstream: Path, split: str, graph_file: Path | None):
    if graph_file:
        with graph_file.open(encoding="utf-8") as stream:
            yield from (json.loads(line) for line in stream if line.strip())
    else:
        member = f"datasets/Break/QDMR/{split}_dependencies_graph.json"
        with ZipFile(upstream / "datasets.zip") as archive, archive.open(member) as stream:
            yield from (json.loads(line) for line in stream if line.strip())


def decode(row: dict, extractor) -> dict:
    from dependencies_graph.data_types import TokensDependencies

    metadata = row["metadata"]
    if "deps" in row:
        question_tokens = [token["text"] for token in row["tokens"]]
        entries = row["tokens"] + row.get("extra_tokens", [])
        tokens = [entry["text"] for entry in entries]
        tags = [entry["tag"] for entry in entries]
        arcs = row["deps"]
    else:
        tokens, tags = metadata["tokens"], metadata["pos"]
        boundary = tokens.index("[RSC]") if "[RSC]" in tokens else len(tokens)
        question_tokens = tokens[:boundary]
        arcs = [
            (source, target, relation)
            for (source, target), tag in zip(row["arcs"], row["arc_tags"], strict=True)
            if tag != "NONE"
            for relation in tag.split("&")
        ]

    if not all(
        type(index) is int and 0 <= index < len(tokens)
        for source, target, _ in arcs for index in (source, target)
    ):
        raise ValueError("An arc points outside the token list")

    debug = {}
    graph = TokensDependencies.from_tokens(tokens, tags, arcs)
    qdmr = extractor.extract(graph, debug=debug)
    if not qdmr.decomposition_list:
        raise ValueError("The upstream decoder recovered no QDMR steps")
    spans = debug["spans_dependencies"]
    return {
        "question_id": metadata.get("question_id"),
        "question": metadata.get("question") or " ".join(question_tokens),
        "steps": qdmr.to_break_standard_string(multiline=True).splitlines(),
        "qdmr_dependencies": sorted(qdmr.to_graph().edges()),
        "span_steps": [
            {"id": step_id, "text": " ".join(tokens[index] for index in data.iter_indexes())}
            for step_id, data in spans.steps()
        ],
        "span_dependencies": [
            {"from": source, "to": target, "role": data.to_string()}
            for source, target, data in spans.dependencies()
        ],
    }


def run(args) -> int:
    with TemporaryDirectory(prefix="hasson-decoder-") as directory:
        target = Path(directory)
        stage_decoder(args.upstream, target)
        sys.path.insert(0, directory)
        from dependencies_graph.extractors.tokens_dependencies_extractors import (
            AddOperatorsPropertiesCollapser,
            DupSingleToMultipleStepsCollapser,
            MissingResourcesCollapser,
            NotAlignedDumCollapser,
            ToDependencyTypeCollapser,
            ToSequentialIdsCollapser,
            TokensDependenciesExtractor,
        )
        from dependencies_graph.extractors.tokens_dependencies_to_qdmr_extractors import (
            RuleBasedSpansDepToQdmrConverter,
            SpansBasedTokensDependenciesToQDMRExtractor,
        )

        # The decoding half of upstream's config_default, in the upstream order.
        token_decoder = TokensDependenciesExtractor(
            spans_dependencies_extractor=None,
            collapsers=[
                ToSequentialIdsCollapser(),
                ToDependencyTypeCollapser(),
                MissingResourcesCollapser(),
                DupSingleToMultipleStepsCollapser(count=5),
                NotAlignedDumCollapser(count=5),
                AddOperatorsPropertiesCollapser(),
            ],
        )
        extractor = SpansBasedTokensDependenciesToQDMRExtractor(
            RuleBasedSpansDepToQdmrConverter(), token_decoder
        )
        matched = 0
        failures = 0
        rows = load_rows(args.upstream, args.split, args.graph_file)
        for row in rows:
            question_id = row["metadata"].get("question_id")
            if args.question_id and question_id != args.question_id:
                continue
            matched += 1
            try:
                result = decode(row, extractor)
            except (KeyError, IndexError, TypeError, ValueError, AssertionError) as error:
                failures += 1
                print(f"{question_id}: {type(error).__name__}: {error}", file=sys.stderr)
            else:
                result["input"] = "graph-file" if args.graph_file else f"published-break-{args.split}"
                print(json.dumps(result, ensure_ascii=False))
            if matched == args.limit:
                break
        rows.close()
        if not matched:
            print("No matching graph records.", file=sys.stderr)
        return int(not matched or failures > 0)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream", type=Path, required=True)
    parser.add_argument("--split", choices=("dev", "train"), default="dev")
    parser.add_argument("--graph-file", type=Path, help="Upstream gold or prediction JSONL")
    parser.add_argument("--question-id", help="Select a single record by its BREAK or prediction ID")
    parser.add_argument("--limit", type=int, default=1, help="Maximum records to decode")
    args = parser.parse_args()
    if args.limit < 1:
        parser.error("--limit must be positive")
    try:
        raise SystemExit(run(args))
    except (OSError, ValueError, ImportError) as error:
        parser.exit(1, f"{type(error).__name__}: {error}\n")
