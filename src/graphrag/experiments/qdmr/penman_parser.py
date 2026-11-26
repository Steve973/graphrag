"""Parse a question into an AMR graph serialized as PENMAN."""

from __future__ import annotations

from .core import Contract, StructuredBackend, Text


class AMRParse(Contract):
    penman: Text


PARSER_PROMPT = """Parse the supplied English question into a single Abstract Meaning
Representation (AMR) graph in PENMAN. Return only the structured response with
the PENMAN graph as its string value. Use conventional AMR frame senses and
roles when possible, regular variable declarations and reentrancies, and
amr-unknown where appropriate for interrogatives. Preserve the requested
output, numeric comparisons, exact temporal boundaries, scope of disjunction
and negation, entity/time attachments, quantities, filters, rankings and
ordering if present. Use separate, semantically scoped concepts or roles for
explicit distinctions if conventional AMR would lose them. Preserve ambiguous
words without choosing a meaning or supplying an unstated metric. Do not
answer the question, add assumptions, invent data schema, or produce a query
plan. Return one connected graph without Markdown or comment lines."""


async def parse_question_to_penman(question: str, *, backend: StructuredBackend) -> str:
    """Generate a PENMAN draft for downstream semantic review."""
    import penman
    from penman.models.amr import model

    question = question.strip()
    if not question:
        raise ValueError("Question must be non-empty")

    response = await backend.complete(
        messages=[
            {"role": "system", "content": PARSER_PROMPT},
            {"role": "user", "content": question},
        ],
        response_model=AMRParse,
    )
    draft = response.penman
    if not draft.startswith("(") or not draft.endswith(")"):
        raise ValueError("Expected a bare PENMAN graph")
    graphs = penman.loads(draft, model=model)
    if len(graphs) != 1:
        raise ValueError("Expected one PENMAN graph")
    graph = graphs[0]
    instances = graph.instances()
    variables = {instance.source for instance in instances}
    if graph.top not in variables or len(variables) != len(instances):
        raise ValueError("Expected unique variable declarations and a declared root")
    if any(target is None for _, _, target in graph.triples):
        raise ValueError("PENMAN graph has a missing concept or role value")
    return draft
