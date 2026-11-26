"""Build and query the GTD vector indexes using the pinned static encoder."""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

MODEL = "sentence-transformers/static-similarity-mrl-multilingual-v1"
REVISION = "b68f4122911bcffcd6e1f695f2d99cd6788972d8"
DIMENSIONS = 256
INDEXES = {
    "schema": ("gtd_schema_vector", "GTDSchemaTerm"),
    "summary": ("gtd_summary_vector", "GTDIncident"),
}
NODE_TYPES = {
    "GTDIncident": ("Incident", "Recorded GTD incident or event."),
    "GTDRegion": ("Region", "GTD geographic region."),
    "GTDCountry": ("Country", "GTD country or territory."),
    "GeopoliticalArea": (None, "State, province or comparable administrative area."),
    "GTDLocality": (None, "City or locality scoped to its country and area."),
    "PerpetratorGroup": ("PerpetratorGroup", "Named group associated with a reported attribution or claim."),
    "PerpetratorAttribution": (None, "Reported attribution, including uncertain attribution. Distinct from a claim of responsibility."),
    "Claim": ("Claim", "Reported claim of responsibility. Distinct from an attribution."),
    "TargetObservation": (None, "A target observation as reported in the source record."),
    "AttackType": (None, "GTD classification of an incident by attack type."),
    "TargetType": (None, "Broad classification of a reported target."),
    "TargetSubtype": (None, "Specific classification of a reported target."),
    "WeaponType": ("Weapon", "Broad classification of the reported weapon."),
    "WeaponSubtype": (None, "Specific classification of the reported weapon."),
    "WeaponUse": (None, "Weapon use recorded in one source slot."),
    "ClaimMode": (None, "How a claim of responsibility was communicated."),
}
RELATIONSHIP_DESCRIPTIONS = {
    "HAS_ATTRIBUTION": "Incident has a reported perpetrator attribution, including uncertain attribution.",
    "ATTRIBUTES_TO": "Reported attribution names a suspected perpetrator group.",
    "HAS_CLAIM": "Incident has a reported claim of responsibility.",
    "CLAIMED_BY": "Claim of responsibility was made by the named group.",
    "OCCURRED_IN_COUNTRY": "Country where the incident occurred.",
    "HAS_NATIONALITY": "Reported nationality of the target, which can differ from the incident country.",
}
PROPERTY_DESCRIPTIONS = {
    "iyear": "Incident year, including records with unknown month or day.",
    "incident_date": "Exact incident date when year, month, and day are known.",
    "date_precision": "Whether the source date is known to the day, month, or year.",
    "nkill": "Reported total fatalities, or people killed.",
    "nwound": "Reported total injuries, or people wounded.",
    "doubtterr": "Whether there is doubt about classification as terrorism.",
    "summary": "Source narrative summary of the recorded incident.",
}
GTD_IRI = "http://www.semanticweb.org/user/ontologies/2020/3/GTDB#"


class StaticEncoder:
    """Mean pooling of the published token weights, as used by StaticEmbedding."""

    def __init__(self, model_dir: Path) -> None:
        from safetensors.numpy import load_file
        from tokenizers import Tokenizer

        self.tokenizer = Tokenizer.from_file(str(model_dir / "tokenizer.json"))
        weights = load_file(str(model_dir / "model.safetensors"))["embedding.weight"]
        if weights.shape != (105879, 1024):
            raise ValueError(f"Unexpected embedding table shape: {weights.shape}")
        self.weights = weights[:, :DIMENSIONS]

    def encode(self, texts: list[str]) -> list[list[float] | None]:
        return [
            self.weights[result.ids].mean(axis=0).tolist() if result.ids else None
            for result in self.tokenizer.encode_batch(texts, add_special_tokens=False)
        ]


def humanize(name: str) -> str:
    name = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", name)
    return name.replace("_", " ")


def schema_terms(session, ontology: Path) -> list[dict]:
    from rdflib import Graph, OWL, RDF, RDFS, URIRef

    graph = Graph().parse(ontology)
    terms = {}

    def add(key: str, kind: str, name: str, text: str, **binding) -> None:
        terms[key] = {"key": key, "kind": kind, "name": name, "text": text, **binding}

    for kind, category in (
        ("ontology_class", OWL.Class),
        ("ontology_object_property", OWL.ObjectProperty),
        ("ontology_datatype_property", OWL.DatatypeProperty),
    ):
        for iri in graph.subjects(RDF.type, category):
            if not isinstance(iri, URIRef) or not str(iri).startswith(GTD_IRI):
                continue
            name = str(iri).removeprefix(GTD_IRI)
            description = " ".join(
                dict.fromkeys([humanize(name), *map(str, graph.objects(iri, RDFS.label)),
                               *map(str, graph.objects(iri, RDFS.comment))])
            )
            add(str(iri), kind, name, description, ontology_iri=str(iri))

    for record in session.run("CALL db.schema.nodeTypeProperties()"):
        labels = record["nodeLabels"]
        label = next((label for label in labels if label in NODE_TYPES), None)
        if label is None:
            continue
        iri_name, description = NODE_TYPES.get(label, (None, humanize(label)))
        add(
            f"node:{label}", "node_label", label, description, node_label=label,
            ontology_iri=f"{GTD_IRI}{iri_name}" if iri_name else None,
        )
        prop = record["propertyName"]
        if prop and prop != "text_embedding":
            add(
                f"property:{label}.{prop}", "node_property", prop,
                f"{humanize(label)} {PROPERTY_DESCRIPTIONS.get(prop, humanize(prop))}",
                node_label=label, property_name=prop, property_types=record["propertyTypes"],
            )
    for record in session.run(
        "MATCH (a:GTD)-[r]->(b:GTD) "
        "RETURN DISTINCT labels(a) AS source, type(r) AS relation, "
        "labels(b) AS target, keys(r) AS properties"
    ):
        source, relation, target = record["source"], record["relation"], record["target"]
        start = next(label for label in source if label in NODE_TYPES)
        end = next(label for label in target if label in NODE_TYPES)
        add(
            f"relationship:{start}:{relation}:{end}", "relationship", relation,
            RELATIONSHIP_DESCRIPTIONS.get(
                relation, f"{humanize(start)} {humanize(relation).lower()} {humanize(end)}"
            ),
            source_label=start, relationship_type=relation, target_label=end,
            relationship_properties=record["properties"],
        )
    return [terms[key] for key in sorted(terms)]


def build_indexes(
    session, encoder: StaticEncoder, ontology: Path, schema_output: Path | None = None
) -> None:
    terms = schema_terms(session, ontology)
    session.run(
        "CREATE CONSTRAINT gtd_schema_term_key IF NOT EXISTS "
        "FOR (n:GTDSchemaTerm) REQUIRE n.key IS UNIQUE"
    ).consume()
    session.run(
        "CREATE FULLTEXT INDEX gtd_schema_text IF NOT EXISTS "
        "FOR (n:GTDSchemaTerm) ON EACH [n.name, n.text]"
    ).consume()
    for start in range(0, len(terms), 512):
        batch = terms[start : start + 512]
        vectors = encoder.encode([term["text"] for term in batch])
        session.run(
            "UNWIND $rows AS row MERGE (n:GTDSchemaTerm {key: row.key}) SET n = row",
            rows=[dict(term, text_embedding=vector) for term, vector in zip(batch, vectors, strict=True)],
        ).consume()

    # Use indexed Incident identifiers for stable keyset pagination and restartability.
    cursor = ""
    summaries = 0
    while rows := session.run(
        "MATCH (n:Incident:GTDIncident) WHERE n.eventid > $cursor AND n.summary IS NOT NULL "
        "RETURN n.eventid AS eventid, n.summary AS summary ORDER BY n.eventid LIMIT 512",
        cursor=cursor,
    ).data():
        cursor = rows[-1]["eventid"]
        vectors = encoder.encode([row["summary"] for row in rows])
        session.run(
            "UNWIND $rows AS row MATCH (n:Incident:GTDIncident {eventid: row.eventid}) "
            "SET n.text_embedding = row.embedding",
            rows=[
                {"eventid": row["eventid"], "embedding": vector}
                for row, vector in zip(rows, vectors, strict=True)
            ],
        ).consume()
        summaries += len(rows)
        if summaries // 10000 != (summaries - len(rows)) // 10000:
            print(f"Encoded {summaries} incident summaries", flush=True)

    for index, label in INDEXES.values():
        session.run(
            f"CREATE VECTOR INDEX {index} IF NOT EXISTS FOR (n:{label}) ON n.text_embedding "
            f"OPTIONS {{indexConfig: {{`vector.dimensions`: {DIMENSIONS}, "
            "`vector.similarity_function`: 'cosine'}}"
        ).consume()
    session.run(
        "MERGE (n:GTDVectorConfiguration {model: $model}) "
        "SET n.revision = $revision, n.dimensions = $dimensions",
        model=MODEL, revision=REVISION, dimensions=DIMENSIONS,
    ).consume()
    session.run("CALL db.awaitIndexes(1800)").consume()
    if schema_output is not None:
        schema = {
            "terms": terms,
            "indexes": session.run(
                "SHOW INDEXES YIELD name, type, state, entityType, labelsOrTypes, properties "
                "RETURN * ORDER BY name"
            ).data(),
            "constraints": session.run(
                "SHOW CONSTRAINTS YIELD name, type, labelsOrTypes, properties "
                "RETURN * ORDER BY name"
            ).data(),
            "embedding": {"model": MODEL, "revision": REVISION, "dimensions": DIMENSIONS},
        }
        schema_output.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")
    print(f"Indexed {len(terms)} ontology and schema terms and processed {summaries} summaries.")


def search(
    session, encoder: StaticEncoder, text: str, scope: str, limit: int,
    *, vector: list[float] | None = None,
) -> list[dict]:
    if limit < 1:
        raise ValueError("The result limit must be positive")
    if vector is None:
        vector = encoder.encode([text])[0]
    if vector is None:
        raise ValueError("The lookup term produced no tokens")
    index, label = INDEXES[scope]
    return session.run(
        f"CYPHER 25 MATCH (node:{label}) "
        f"SEARCH node IN (VECTOR INDEX {index} FOR $vector LIMIT $limit) SCORE AS score "
        "RETURN coalesce(node.name, node.eventid) AS match, node.kind AS kind, "
        "node.key AS key, node.text AS description, "
        "node.node_label AS node_label, node.property_name AS property_name, "
        "node.source_label AS source_label, node.target_label AS target_label, "
        "node.relationship_type AS relationship_type, node.ontology_iri AS ontology_iri, score "
        "ORDER BY score DESC",
        limit=limit, vector=vector,
    ).data()


def main() -> None:
    from neo4j import GraphDatabase

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--uri", default="bolt://127.0.0.1:17687")
    parser.add_argument("--user", default="neo4j")
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build")
    build.add_argument("--ontology", type=Path, required=True)
    build.add_argument("--schema-output", type=Path)
    lookup = commands.add_parser("search")
    lookup.add_argument("text")
    lookup.add_argument("--scope", choices=INDEXES, default="schema")
    lookup.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()
    encoder = StaticEncoder(args.model_dir)
    password = os.getenv("GTD_NEO4J_PASSWORD")
    auth = (args.user, password) if password else None
    with GraphDatabase.driver(args.uri, auth=auth) as driver, driver.session(database="neo4j") as session:
        if args.command == "build":
            build_indexes(session, encoder, args.ontology, args.schema_output)
        else:
            print(json.dumps(search(session, encoder, args.text, args.scope, args.limit), indent=2))


if __name__ == "__main__":
    main()
