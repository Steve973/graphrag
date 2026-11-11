import asyncio
import json

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
import pytest

from graphrag.experiments.planpool import build_graph
from graphrag.experiments.planpool.demo import (
    ANSWERS,
    BREAKDOWN,
    CONTEXT,
    QUESTION,
    DemoBackend,
    make_decision,
)
from graphrag.experiments.planpool.workflow import InitialPool, Need


CONFIG = {"configurable": {"thread_id": "test"}}


def test_checkpointed_demo_accounts_for_each_need():
    async def run():
        graph = build_graph(DemoBackend(), checkpointer=InMemorySaver())
        result = await graph.ainvoke({
            "question": QUESTION, "breakdown_steps": BREAKDOWN, "datasource_context": CONTEXT,
        }, CONFIG)
        assert result["status"] == "running"
        assert result["turns"] == 2  # The initial finish was rejected.
        assert all(item["status"] == "pending" for item in result["pool"])
        assert result["__interrupt__"][0].value["item_id"] == 1

        result = await graph.ainvoke(Command(resume=ANSWERS[1]), CONFIG)
        assert result["__interrupt__"][0].value["item_id"] == 4
        assert result["pool"][3]["discovery_ids"] == [3]
        assert result["pool"][1]["evidence_ids"] == [3]  # One reply resolved two items.

        result = await graph.ainvoke(Command(resume=ANSWERS[4]), CONFIG)
        assert result["status"] == "ready"
        assert [item["status"] for item in result["pool"]] == [
            "resolved", "resolved", "dropped", "resolved",
        ]

    asyncio.run(run())


def test_probe_then_reject_fabricated_evidence():
    class Backend:
        def __init__(self):
            self.actions = iter([
                make_decision("probe", question="Look up the topic"),
                make_decision("resolve", item_id=1, reason="Use FC-01", evidence_ids=[99]),
                make_decision("finish"),
            ])

        async def complete(self, *, messages, response_model):
            if response_model is InitialPool:
                return InitialPool(needs=[
                    Need(
                        target="topic", question="Which topic should be used?",
                        gap="The graph topic is unknown.", source_quote="feline cardiomyopathy",
                        step_ids=[], discovery_ids=[],
                    )
                ])
            return next(self.actions)

    async def probe(request):
        assert request == "Look up the topic"
        return "The catalog contains topic FC-01."

    async def run():
        graph = build_graph(Backend(), checkpointer=InMemorySaver(), probe=probe, max_turns=3)
        result = await graph.ainvoke({"question": QUESTION}, CONFIG)
        assert result["status"] == "blocked"
        assert result["observations"][0]["source"] == "datasource"
        assert result["pool"][0]["status"] == "pending"
        assert result["pool"][0]["evidence_ids"] == []

    asyncio.run(run())


def test_detector_receives_breakdown_and_rejects_invalid_anchor():
    class Backend:
        async def complete(self, *, messages, response_model):
            payload = json.loads(messages[-1]["content"])
            assert payload["breakdown_steps"]["3"] == BREAKDOWN[3]
            assert payload["unknown_hints"] == ["Ranking is unspecified."]
            return response_model(needs=[
                Need(
                    target="ranking", question="Which ranking?",
                    gap="Rankings differ by measure.", source_quote="foremost",
                    step_ids=[99], discovery_ids=[],
                )
            ])

    async def run():
        graph = build_graph(Backend(), checkpointer=InMemorySaver())
        await graph.ainvoke({
            "question": QUESTION,
            "breakdown_steps": BREAKDOWN,
            "unknown_hints": ["Ranking is unspecified."],
        }, CONFIG)

    with pytest.raises(ValueError, match="Referenced step IDs"):
        asyncio.run(run())
