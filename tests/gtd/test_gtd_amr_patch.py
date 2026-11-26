import asyncio

import pytest

from gtd.gtd_amr import amr_items
from gtd.gtd_amr_patch import Decision, Edit, apply_patch, assess, triples_for

pytest.importorskip("penman")

QUESTION = "How many incidents occurred in Spain in or after 2010?"
DRAFT = """(i / incident
  :location (c / country :name (n / name :op1 "Spain"))
  :time (o / or :op1 (b / before :op1 (d / date-entity :year 2010))
                :op2 (a / after :op1 d)))"""


def correction(quote="in or after 2010"):
    triples = triples_for(DRAFT).triples
    return Edit(
        operation="replace", index=triples.index(("b", ":instance", "before")),
        triple={"source": "b", "role": ":instance", "target": "during"}, quote=quote,
    )


def test_patch_changes_only_the_named_triple():
    corrected = apply_patch(QUESTION, amr_items(DRAFT), [correction()])
    before = set(triples_for(DRAFT).triples)
    after = set(triples_for(corrected["penman"]).triples)
    assert before - after == {("b", ":instance", "before")}
    assert after - before == {("b", ":instance", "during")}


def test_patch_rejects_added_quote():
    with pytest.raises(ValueError, match="quote"):
        apply_patch(QUESTION, amr_items(DRAFT), [correction("before 2010")])


def test_patch_rejects_disconnected_insert():
    disconnected = Edit(
        operation="insert", index=None, quote="Spain",
        triple={"source": "extra", "role": ":instance", "target": "country"},
    )
    with pytest.raises(ValueError, match="connected"):
        apply_patch(QUESTION, amr_items(DRAFT), [disconnected])


@pytest.mark.parametrize("route", ["accepted", "patched"])
def test_no_full_rewrite_for_accepted_or_locally_repaired_draft(route):
    calls = []

    class Backend:
        async def complete(self, *, messages, response_model):
            calls.append(response_model)
            if response_model is Decision:
                edits = [correction()] if route == "patched" else []
                return Decision(action="patch" if edits else "accept", edits=edits, reason="test")
            return response_model(issues=[])

    result = asyncio.run(assess(Backend(), "fixture", QUESTION, amr_items(DRAFT)))
    assert result["approved"] and result["route"] == route
    assert len(calls) == (2 if route == "patched" else 1)
