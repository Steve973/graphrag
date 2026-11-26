import asyncio

import pytest

from graphrag.experiments.qdmr.penman_parser import parse_question_to_penman

pytest.importorskip("penman")

QUESTION = "How many incidents occurred in Spain in or after 2010?"
PENMAN = """(i / incident :quant (q / amr-unknown)
  :location (s / country :name (n / name :op1 "Spain"))
  :time (o / or :op1 (d / date-entity :year 2010)
                :op2 (a / after :op1 d)))"""


class Backend:
    def __init__(self, penman):
        self.penman = penman

    async def complete(self, *, messages, response_model):
        assert messages[1] == {"role": "user", "content": QUESTION}
        return response_model(penman=self.penman)


def test_parser_preserves_the_generated_graph_with_reentrancy():
    assert asyncio.run(parse_question_to_penman(QUESTION, backend=Backend(PENMAN))) == PENMAN


@pytest.mark.parametrize("draft", ["```(i / incident)```", "(i / incident) (d / date)", "(i / incident :time)"])
def test_parser_rejects_invalid_drafts_before_review(draft):
    with pytest.raises(ValueError):
        asyncio.run(parse_question_to_penman(QUESTION, backend=Backend(draft)))
