import os
from pathlib import Path

import pytest
from neo4j import GraphDatabase, READ_ACCESS

from gtd.gtd_embeddings import StaticEncoder
from gtd.gtd_grounding import ground
from test_gtd_grounding import fixture_breakdown, fixture_review

pytestmark = pytest.mark.skipif(
    os.getenv("GTD_LIVE_TEST") != "1",
    reason="Set GTD_LIVE_TEST=1 with an online GTD database and local embedding model",
)


@pytest.fixture(scope="module")
def live_graph():
    uri = os.getenv("GTD_NEO4J_URI", "bolt://127.0.0.1:17687")
    encoder = StaticEncoder(Path("build/gtd/model"))
    with GraphDatabase.driver(uri) as driver, driver.session(
        database="neo4j", default_access_mode=READ_ACCESS,
    ) as session:
        yield session, encoder


@pytest.mark.parametrize(
    "question, quote, kind, field, literal",
    [
        ("How many incidents occurred in Spain?", "occurred in Spain",
         "incident_country", "incident_country", "Spain"),
        ("What nationalities were reported for targets?", "nationalities were reported for targets",
         "target_nationality", "target_nationality", None),
        ("How many fatalities were reported?", "fatalities", "fatalities", "fatalities", None),
        ("How many injuries were reported?", "injuries", "injuries", "injuries", None),
        ("Which year did it occur?", "Which year", "incident_year", "incident_year", None),
        ("Is the exact date recorded?", "exact date", "exact_incident_date", "exact_date", None),
        ("Did any group claim responsibility?", "claim responsibility",
         "claim", "recorded_claim", None),
        ("Was there a reported attribution?", "reported attribution",
         "attribution", "reported_attribution", None),
    ],
)
def test_shows_discriminating_records(live_graph, question, quote, kind, field, literal):
    session, encoder = live_graph
    report = ground(fixture_breakdown(question, quote), fixture_review(quote, kind, literal),
                    session=session, encoder=encoder)
    candidates, = report["schema_candidates"]
    assert candidates["vector"] and candidates["lexical"]
    check, = report["data_checks"]
    assert check["status"] == "contrast_observed"
    assert field in check["witness"]
    if literal:
        assert literal in (check["witness"]["incident_country"],
                           check["witness"]["target_nationality"])


def test_absent_literal_keeps_data_check_inconclusive(live_graph):
    session, encoder = live_graph
    quote = "occurred in Atlantis"
    report = ground(fixture_breakdown(f"How many incidents {quote}? ", quote),
                    fixture_review(quote, "incident_country", "Atlantis"),
                    session=session, encoder=encoder)
    check, = report["data_checks"]
    assert check["status"] == "inconclusive"
    assert check["witness"] is None
