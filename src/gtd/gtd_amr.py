"""Pretrained AMR inference and a lossless view of its extracted items."""

from __future__ import annotations

import re
from pathlib import Path

CHECKPOINT = "parse_xfm_bart_base-v0_1_0"


def parse(question: str, model_dir: Path, *, device: str = "cpu") -> str:
    import amrlib

    model = amrlib.load_stog_model(str(model_dir), device=device, batch_size=1)
    graph = model.parse_sents([question], add_metadata=False)[0]
    if graph is None:
        raise ValueError("The pretrained AMR model did not produce a decodable graph")
    return graph


def amr_items(penman_text: str, question: str = "") -> dict:
    import penman
    from penman.constant import evaluate
    from penman.models.amr import model

    graph = penman.decode(penman_text, model=model)
    concepts = {instance.source: instance.target for instance in graph.instances()}
    names = {
        variable: " ".join(
            str(evaluate(attribute.target))
            for attribute in sorted(
                graph.attributes(source=variable),
                key=lambda attribute: int(attribute.role[3:]) if attribute.role[3:].isdigit() else 0,
            )
            if re.fullmatch(r":op\d+", attribute.role)
        )
        for variable, concept in concepts.items()
        if concept == "name"
    }
    entity_names = {
        edge.source: names[edge.target]
        for edge in graph.edges(role=":name")
        if edge.target in names
    }

    def label(variable: str) -> str:
        return entity_names.get(variable) or names.get(variable) or re.sub(
            r"-\d\d$", "", concepts[variable]
        ).replace("-", " ")

    items = [
        {"id": variable, "kind": "concept", "symbol": symbol, "lookup": label(variable)}
        for variable, symbol in concepts.items()
    ]
    for i, edge in enumerate(graph.edges(), start=1):
        items.append({
            "id": f"edge:{i}", "kind": "relation", "source": edge.source,
            "role": edge.role, "target": edge.target,
            "lookup": f"{label(edge.source)} {edge.role.removeprefix(':')} {label(edge.target)}",
        })
    for i, attribute in enumerate(graph.attributes(), start=1):
        value = evaluate(attribute.target)
        items.append({
            "id": f"attribute:{i}", "kind": "attribute", "source": attribute.source,
            "role": attribute.role, "value": value,
            "lookup": f"{label(attribute.source)} {attribute.role.removeprefix(':')} {value}",
        })
    for item in items:
        if item["kind"] == "relation":
            continue
        literal = str(item.get("value", item["lookup"]))
        occurrences = re.finditer(
            rf"(?<!\w){re.escape(literal)}(?!\w)", question, flags=re.IGNORECASE,
        )
        item["literal_spans"] = [
            {"start": occurrence.start(), "end": occurrence.end(), "text": occurrence.group()}
            for occurrence in occurrences
        ]
    return {"root": graph.top, "penman": penman_text, "items": items}
