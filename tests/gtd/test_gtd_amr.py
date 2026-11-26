import pytest

from gtd.gtd_amr import amr_items

pytest.importorskip("penman")


def test_preserves_amr_directions_qualifiers_and_literal_occurrences():
    graph = '(i / incident :location (c / country :name (n / name :op1 "Spain")) :time (a / after :op1 (d / date-entity :year 2010)))'
    result = amr_items(graph, "Incidents in Spain after 2010?")
    assert result["penman"] == graph
    assert result["root"] == "i"
    items = result["items"]
    assert any(
        (item.get("source"), item.get("role"), item.get("target")) == ("i", ":location", "c")
        for item in items
    )
    year = next(item for item in items if item.get("role") == ":year")
    assert year["value"] == 2010
    assert year["literal_spans"] == [{"start": 25, "end": 29, "text": "2010"}]
