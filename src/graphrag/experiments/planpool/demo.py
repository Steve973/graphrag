"""A deterministic publication example with scripted model decisions and replies."""

import json

from .workflow import Decision, InitialPool, Need

QUESTION = "Who are the foremost experts in feline cardiomyopathy?"
BREAKDOWN = {
    1: "Find publications on feline cardiomyopathy.",
    2: "Find authors of those publications.",
    3: "Identify the foremost experts among those authors.",
}
CONTEXT = [
    "The topic catalog maps feline cardiomyopathy to topic FC-01.",
    "The graph has publication dates, authorship and citation counts.",
]
ANSWERS = {
    1: "Rank by number of publications. Include authors with at least three relevant publications.",
    4: "Count publications from 2015 onward.",
}


def make_decision(action: str, **fields) -> Decision:
    return Decision.model_validate({
        "action": action, "item_id": 0, "question": "", "reason": "",
        "evidence_ids": [], "new_need": None, **fields,
    })


class DemoBackend:
    def __init__(self) -> None:
        date_range = Need(
            target="publication window",
            question="What date range should count toward publication totals?",
            gap="The answer selects publication count but leaves its time window unspecified.",
            source_quote="foremost experts",
            step_ids=[1, 3],
            discovery_ids=[3],
        )
        self.decisions = iter([
            make_decision("finish"),
            make_decision("ask"),
            make_decision(
                "resolve", item_id=1, evidence_ids=[3],
                reason="Rank by relevant publication count.",
            ),
            make_decision(
                "resolve", item_id=2, evidence_ids=[3],
                reason="Require at least three relevant publications.",
            ),
            make_decision(
                "drop", item_id=3, evidence_ids=[3],
                reason="Citation weighting is irrelevant because the user chose publication count.",
            ),
            make_decision("add", new_need=date_range.model_dump()),
            make_decision("ask"),
            make_decision(
                "resolve", item_id=4, evidence_ids=[4],
                reason="Include publications from 2015 onward.",
            ),
            make_decision("finish"),
        ])

    async def complete(self, *, messages, response_model):
        if response_model is InitialPool:
            return InitialPool(needs=[
                Need(
                    target="ranking measure", question="How should experts be ranked?",
                    gap="Publication count and citation count can produce different rankings.",
                    source_quote="foremost experts", step_ids=[3], discovery_ids=[2],
                ),
                Need(
                    target="expert qualification", question="What qualifies an author as an expert?",
                    gap="Authorship alone does not specify the threshold for inclusion.",
                    source_quote="experts", step_ids=[2, 3], discovery_ids=[],
                ),
                Need(
                    target="citation weighting", question="If ranking by citations, should older citations count less?",
                    gap="If citations are used, weighting by age can change the ordering.",
                    source_quote="foremost", step_ids=[3], discovery_ids=[2],
                ),
            ])
        decision = next(self.decisions)
        if decision.action == "ask":
            payload = json.loads(messages[-1]["content"])
            if payload["pool"][0]["status"] == "pending":
                assert "Finish rejected" in payload["last_action_note"]
        return decision
