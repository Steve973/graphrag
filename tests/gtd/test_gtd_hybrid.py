import asyncio
import json

import pytest

from gtd.gtd_compare import repair_amr

QUESTION = "Incidents in or after 2010?"
AMR = {"root": "x", "penman": "(x / before)", "items": [{"id": "x", "lookup": "before"}]}


@pytest.mark.parametrize("item_id", ["x", "phantom"])
def test_amr_repair_preserves_auditable_source_and_checks_references(item_id):
    class RepairBackend:
        async def complete(self, *, messages, response_model):
            payload = json.loads(messages[1]["content"])
            assert payload == {"question": QUESTION, "amr": AMR}
            return response_model.model_validate({
                "corrections": [{
                    "item_ids": [item_id], "source_quote": "in or after 2010",
                    "explanation": "The lower bound includes 2010.",
                }],
                "decomposition": {
                    "concepts": [{
                        "id": "c1", "expression": "in or after 2010",
                        "kind": "qualifier", "component_ids": [],
                    }],
                    "meanings": [{
                        "id": "m1", "kind": "scope", "statement": "2010 inclusively.",
                        "concept_ids": ["c1"], "basis": "explicit",
                        "source_quotes": ["in or after 2010"],
                    }],
                    "requirements": [{
                        "id": "r1", "statement": "Establish occurrence year.",
                        "meaning_ids": ["m1"], "depends_on": [],
                    }],
                    "unresolved": [],
                },
            })

    async def run():
        return await repair_amr(RepairBackend(), "fixture", QUESTION, AMR)

    if item_id == "phantom":
        with pytest.raises(ValueError, match="item reference"):
            asyncio.run(run())
    else:
        repaired = asyncio.run(run())
        assert repaired["corrections"][0]["item_ids"] == ["x"]
        assert repaired["items"][1]["statement"] == "2010 inclusively."
        assert AMR["items"][0]["lookup"] == "before"
