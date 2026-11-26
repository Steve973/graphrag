import asyncio

from gtd.gtd_coverage import build_coverage


def test_invalid_review_blocks_grounding_without_discarding_the_proposal():
    question = "How many incidents occurred after 2010?"
    proposals = iter([
        {"criteria": [{
            "id": "c1", "statement": "Count every qualifying incident once.",
            "source_quotes": ["How many incidents"], "item_ids": ["incident"],
            "assertions": [{"id": "a1", "statement": "The count includes every qualifying incident."}],
        }]},
        {"issues": [{
            "level": "criterion_to_assertions", "item_id": "a1",
            "source_quote": "Count every qualifying incident once.",
            "explanation": "The assertion does not exclude duplicate counts.",
        }]},
    ])

    class Backend:
        async def complete(self, *, messages, response_model):
            return response_model.model_validate(next(proposals))

    result = asyncio.run(build_coverage(
        question, [{"id": "incident", "lookup": "incidents"}], backend=Backend(),
    ))
    assert result["status"] == "review_invalid"
    assert result["criteria"][0]["assertions"][0]["id"] == "a1"
    assert result["issues"][0]["level"] == "criterion_to_assertions"
