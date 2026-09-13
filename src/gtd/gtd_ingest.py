"""Load graph-shaped GTD CSV files into Neo4j using ordered ``LOAD CSV`` passes."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import quote

from .gtd_prepare import GtdPreparationResult, prepare_gtd_csv
from .gtd_schema import GTD_COLUMNS, cypher_property_expression

if TYPE_CHECKING:
    from neo4j import Driver

CONSTRAINTS = (
    "CREATE CONSTRAINT incident_eventid IF NOT EXISTS FOR (n:Incident) REQUIRE n.eventid IS UNIQUE",
    "CREATE CONSTRAINT gtd_region_code IF NOT EXISTS FOR (n:GTDRegion) REQUIRE n.code IS UNIQUE",
    "CREATE CONSTRAINT gtd_country_code IF NOT EXISTS FOR (n:GTDCountry) REQUIRE n.code IS UNIQUE",
    "CREATE CONSTRAINT gtd_area_id IF NOT EXISTS FOR (n:GeopoliticalArea) REQUIRE n.area_id IS UNIQUE",
    "CREATE CONSTRAINT gtd_locality_id IF NOT EXISTS FOR (n:GTDLocality) REQUIRE n.locality_id IS UNIQUE",
    "CREATE CONSTRAINT gtd_attack_code IF NOT EXISTS FOR (n:AttackType) REQUIRE n.code IS UNIQUE",
    "CREATE CONSTRAINT gtd_target_type_code IF NOT EXISTS FOR (n:TargetType) REQUIRE n.code IS UNIQUE",
    "CREATE CONSTRAINT gtd_target_subtype_code IF NOT EXISTS FOR (n:TargetSubtype) REQUIRE n.code IS UNIQUE",
    "CREATE CONSTRAINT gtd_weapon_type_code IF NOT EXISTS FOR (n:WeaponType) REQUIRE n.code IS UNIQUE",
    "CREATE CONSTRAINT gtd_weapon_subtype_code IF NOT EXISTS FOR (n:WeaponSubtype) REQUIRE n.code IS UNIQUE",
    "CREATE CONSTRAINT gtd_claim_mode_code IF NOT EXISTS FOR (n:ClaimMode) REQUIRE n.code IS UNIQUE",
    "CREATE CONSTRAINT gtd_group_id IF NOT EXISTS FOR (n:PerpetratorGroup) REQUIRE n.group_id IS UNIQUE",
    "CREATE CONSTRAINT gtd_target_id IF NOT EXISTS FOR (n:TargetObservation) REQUIRE n.target_id IS UNIQUE",
    "CREATE CONSTRAINT gtd_weapon_use_id IF NOT EXISTS FOR (n:WeaponUse) REQUIRE n.weapon_use_id IS UNIQUE",
    "CREATE CONSTRAINT gtd_attribution_id IF NOT EXISTS FOR (n:PerpetratorAttribution) REQUIRE n.attribution_id IS UNIQUE",
    "CREATE CONSTRAINT gtd_claim_id IF NOT EXISTS FOR (n:Claim) REQUIRE n.claim_id IS UNIQUE",
)

INDEXES = (
    "CREATE INDEX gtd_incident_year IF NOT EXISTS FOR (n:GTDIncident) ON (n.iyear)",
    "CREATE INDEX gtd_incident_date IF NOT EXISTS FOR (n:GTDIncident) ON (n.incident_date)",
    "CREATE INDEX gtd_country_name IF NOT EXISTS FOR (n:GTDCountry) ON (n.name)",
    "CREATE INDEX gtd_group_name IF NOT EXISTS FOR (n:PerpetratorGroup) ON (n.name)",
)


@dataclass(frozen=True, slots=True)
class GTDBatchResult:
    rows_seen: int
    incidents_written: int
    source_sha256: str
    prepared_files: dict[str, int]
    reconciliation: dict[str, int]


@dataclass(frozen=True, slots=True)
class _LoadStep:
    filename: str
    body: str


def _incident_body() -> str:
    assignments = [
        f"i.`{column}` = {cypher_property_expression(column)}" for column in GTD_COLUMNS
    ]
    assignments.extend(
        (
            "i.incident_date = CASE trim(row.incident_date) WHEN '' THEN null ELSE date(trim(row.incident_date)) END",
            "i.date_precision = trim(row.date_precision)",
            "i.source_row_number = toInteger(row.source_row_number)",
            "i.source_sha256 = $source_sha256",
        )
    )
    return (
        "MERGE (i:GTD:Incident:GTDIncident {eventid: trim(row.eventid)})\n"
        "SET " + ",\n    ".join(assignments)
    )


NODE_STEPS = (
    _LoadStep(
        "incidents.csv",
        _incident_body(),
    ),
    _LoadStep(
        "regions.csv",
        "MERGE (n:GTD:GTDReference:GeographicArea:Region:GTDRegion {code: toInteger(row.code)}) "
        "SET n.name = trim(row.name)",
    ),
    _LoadStep(
        "countries.csv",
        "MERGE (n:GTD:GTDReference:GeographicArea:Country:GTDCountry {code: toInteger(row.code)}) "
        "SET n.name = trim(row.name)",
    ),
    _LoadStep(
        "geopolitical_areas.csv",
        "MERGE (n:GTD:GeographicArea:GeopoliticalArea {area_id: row.area_id}) SET n.name = trim(row.name), "
        "n.country_code = toIntegerOrNull(row.country_code)",
    ),
    _LoadStep(
        "localities.csv",
        "MERGE (n:GTD:GeographicArea:Locality:GTDLocality {locality_id: row.locality_id}) SET n.name = trim(row.name), "
        "n.country_code = toIntegerOrNull(row.country_code), n.area_id = CASE trim(row.area_id) "
        "WHEN '' THEN null ELSE row.area_id END",
    ),
    _LoadStep(
        "attack_types.csv",
        "MERGE (n:GTD:GTDReference:AttackType {code: toInteger(row.code)}) SET n.name = trim(row.name)",
    ),
    _LoadStep(
        "target_types.csv",
        "MERGE (n:GTD:GTDReference:TargetType {code: toInteger(row.code)}) SET n.name = trim(row.name)",
    ),
    _LoadStep(
        "target_subtypes.csv",
        "MERGE (n:GTD:GTDReference:TargetSubtype {code: toInteger(row.code)}) SET n.name = trim(row.name)",
    ),
    _LoadStep(
        "weapon_types.csv",
        "MERGE (n:GTD:GTDReference:WeaponType {code: toInteger(row.code)}) SET n.name = trim(row.name)",
    ),
    _LoadStep(
        "weapon_subtypes.csv",
        "MERGE (n:GTD:GTDReference:WeaponSubtype {code: toInteger(row.code)}) SET n.name = trim(row.name)",
    ),
    _LoadStep(
        "claim_modes.csv",
        "MERGE (n:GTD:GTDReference:ClaimMode {code: toInteger(row.code)}) SET n.name = trim(row.name)",
    ),
    _LoadStep(
        "groups.csv",
        "MERGE (n:GTD:PerpetratorGroup {group_id: row.group_id}) SET n.name = trim(row.name)",
    ),
    _LoadStep(
        "targets.csv",
        "MERGE (n:GTD:GTDObservation:TargetObservation {target_id: row.target_id}) SET n.slot = toInteger(row.slot), "
        "n.target = CASE trim(row.target) WHEN '' THEN null ELSE trim(row.target) END, "
        "n.corporation = CASE trim(row.corporation) WHEN '' THEN null ELSE trim(row.corporation) END",
    ),
    _LoadStep(
        "weapon_uses.csv",
        "MERGE (n:GTD:GTDObservation:WeaponUse {weapon_use_id: row.weapon_use_id}) SET n.slot = toInteger(row.slot)",
    ),
    _LoadStep(
        "attributions.csv",
        "MERGE (n:GTD:GTDObservation:PerpetratorAttribution {attribution_id: row.attribution_id}) "
        "SET n.slot = toInteger(row.slot), "
        "n.reported_group_name = CASE trim(row.group_name) WHEN '' THEN null ELSE trim(row.group_name) END, "
        "n.subgroup_name = CASE trim(row.subgroup_name) WHEN '' THEN null ELSE trim(row.subgroup_name) END, "
        "n.uncertain = toIntegerOrNull(row.uncertain)",
    ),
    _LoadStep(
        "claims.csv",
        "MERGE (n:GTD:GTDObservation:Claim {claim_id: row.claim_id}) SET n.slot = toInteger(row.slot), "
        "n.claimed = toIntegerOrNull(row.claimed)",
    ),
)

RELATIONSHIP_STEPS = (
    _LoadStep(
        "incident_regions.csv",
        "MATCH (a:GTDIncident {eventid: row.eventid}), (b:GTDRegion {code: toInteger(row.region_code)}) "
        "MERGE (a)-[:IN_GTD_REGION]->(b)",
    ),
    _LoadStep(
        "incident_countries.csv",
        "MATCH (a:GTDIncident {eventid: row.eventid}), (b:GTDCountry {code: toInteger(row.country_code)}) "
        "MERGE (a)-[:OCCURRED_IN_COUNTRY]->(b)",
    ),
    _LoadStep(
        "country_regions.csv",
        "MATCH (a:GTDCountry {code: toInteger(row.country_code)}), (b:GTDRegion {code: toInteger(row.region_code)}) "
        "MERGE (a)-[:IN_GTD_REGION]->(b)",
    ),
    _LoadStep(
        "incident_areas.csv",
        "MATCH (a:GTDIncident {eventid: row.eventid}), (b:GeopoliticalArea {area_id: row.area_id}) "
        "MERGE (a)-[:OCCURRED_IN_AREA]->(b)",
    ),
    _LoadStep(
        "incident_localities.csv",
        "MATCH (a:GTDIncident {eventid: row.eventid}), (b:GTDLocality {locality_id: row.locality_id}) "
        "MERGE (a)-[:OCCURRED_IN_LOCALITY]->(b)",
    ),
    _LoadStep(
        "incident_attacks.csv",
        "MATCH (a:GTDIncident {eventid: row.eventid}), (b:AttackType {code: toInteger(row.attack_type_code)}) "
        "MERGE (a)-[:CLASSIFIED_AS_ATTACK {slot: toInteger(row.slot)}]->(b)",
    ),
    _LoadStep(
        "incident_targets.csv",
        "MATCH (a:GTDIncident {eventid: row.eventid}), (b:TargetObservation {target_id: row.target_id}) "
        "MERGE (a)-[:HAS_TARGET]->(b)",
    ),
    _LoadStep(
        "target_types_rel.csv",
        "MATCH (a:TargetObservation {target_id: row.target_id}), (b:TargetType {code: toInteger(row.type_code)}) "
        "MERGE (a)-[:HAS_TARGET_TYPE]->(b)",
    ),
    _LoadStep(
        "target_subtypes_rel.csv",
        "MATCH (a:TargetObservation {target_id: row.target_id}), (b:TargetSubtype {code: toInteger(row.subtype_code)}) "
        "MERGE (a)-[:HAS_TARGET_SUBTYPE]->(b)",
    ),
    _LoadStep(
        "target_nationalities.csv",
        "MATCH (a:TargetObservation {target_id: row.target_id}), (b:GTDCountry {code: toInteger(row.country_code)}) "
        "MERGE (a)-[:HAS_NATIONALITY]->(b)",
    ),
    _LoadStep(
        "incident_weapon_uses.csv",
        "MATCH (a:GTDIncident {eventid: row.eventid}), (b:WeaponUse {weapon_use_id: row.weapon_use_id}) "
        "MERGE (a)-[:USED_WEAPON]->(b)",
    ),
    _LoadStep(
        "weapon_types_rel.csv",
        "MATCH (a:WeaponUse {weapon_use_id: row.weapon_use_id}), (b:WeaponType {code: toInteger(row.type_code)}) "
        "MERGE (a)-[:HAS_WEAPON_TYPE]->(b)",
    ),
    _LoadStep(
        "weapon_subtypes_rel.csv",
        "MATCH (a:WeaponUse {weapon_use_id: row.weapon_use_id}), (b:WeaponSubtype {code: toInteger(row.subtype_code)}) "
        "MERGE (a)-[:HAS_WEAPON_SUBTYPE]->(b)",
    ),
    _LoadStep(
        "incident_attributions.csv",
        "MATCH (a:GTDIncident {eventid: row.eventid}), (b:PerpetratorAttribution {attribution_id: row.attribution_id}) "
        "MERGE (a)-[:HAS_ATTRIBUTION]->(b)",
    ),
    _LoadStep(
        "attribution_groups.csv",
        "MATCH (a:PerpetratorAttribution {attribution_id: row.attribution_id}), "
        "(b:PerpetratorGroup {group_id: row.group_id}) MERGE (a)-[:ATTRIBUTES_TO]->(b)",
    ),
    _LoadStep(
        "incident_claims.csv",
        "MATCH (a:GTDIncident {eventid: row.eventid}), (b:Claim {claim_id: row.claim_id}) MERGE (a)-[:HAS_CLAIM]->(b)",
    ),
    _LoadStep(
        "claim_modes_rel.csv",
        "MATCH (a:Claim {claim_id: row.claim_id}), (b:ClaimMode {code: toInteger(row.mode_code)}) "
        "MERGE (a)-[:HAS_CLAIM_MODE]->(b)",
    ),
    _LoadStep(
        "claim_groups.csv",
        "MATCH (a:Claim {claim_id: row.claim_id}), (b:PerpetratorGroup {group_id: row.group_id}) "
        "MERGE (a)-[:CLAIMED_BY]->(b)",
    ),
    _LoadStep(
        "related_incidents.csv",
        "MATCH (a:GTDIncident {eventid: row.eventid}), (b:GTDIncident {eventid: row.related_eventid}) "
        "MERGE (a)-[:RELATED_TO]->(b)",
    ),
    _LoadStep(
        "geopolitical_areas.csv",
        "MATCH (a:GeopoliticalArea {area_id: row.area_id}), (b:GTDCountry {code: toInteger(row.country_code)}) "
        "MERGE (a)-[:WITHIN_COUNTRY]->(b)",
    ),
    _LoadStep(
        "localities.csv",
        "MATCH (a:GTDLocality {locality_id: row.locality_id}), (b:GTDCountry {code: toInteger(row.country_code)}) "
        "MERGE (a)-[:WITHIN_COUNTRY]->(b)",
    ),
    _LoadStep(
        "localities.csv",
        "WITH row WHERE trim(row.area_id) <> '' MATCH (a:GTDLocality {locality_id: row.locality_id}), "
        "(b:GeopoliticalArea {area_id: row.area_id}) MERGE (a)-[:WITHIN_AREA]->(b)",
    ),
)


def _load_query(body: str, batch_size: int) -> str:
    return (
        "LOAD CSV WITH HEADERS FROM $csv_url AS row\n"
        "CALL (row) {\n"
        f"  {body}\n"
        f"}} IN TRANSACTIONS OF {batch_size} ROWS"
    )


class GTDIngestor:
    def __init__(self, uri: str, user: str, password: str) -> None:
        from neo4j import GraphDatabase

        self._driver: Driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self) -> None:
        self._driver.close()

    def prepare_schema(self) -> None:
        with self._driver.session() as session:
            for statement in (*CONSTRAINTS, *INDEXES):
                session.run(statement).consume()

    def wipe(self) -> None:
        """Delete the existing graph, matching the command's explicit ``--wipe`` contract."""

        with self._driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n").consume()

    def ingest_prepared(
        self,
        prepared: GtdPreparationResult,
        *,
        import_uri: str,
        batch_size: int = 1_000,
    ) -> GTDBatchResult:
        if batch_size <= 0:
            raise ValueError("batch_size must be greater than zero")
        uri_prefix = import_uri.rstrip("/")
        with self._driver.session() as session:
            for step in (*NODE_STEPS, *RELATIONSHIP_STEPS):
                if prepared.files.get(step.filename, 0) == 0:
                    continue
                csv_url = f"{uri_prefix}/{quote(step.filename)}"
                session.run(
                    _load_query(step.body, batch_size),
                    csv_url=csv_url,
                    source_sha256=prepared.source_sha256,
                ).consume()
            reconciliation = session.run(
                """
                CALL {
                MATCH (i:GTDIncident {source_sha256: $source_sha256})
                RETURN count(i) AS incidents
                }
                CALL {
                MATCH (i:GTDIncident {source_sha256: $source_sha256})-[:HAS_TARGET]->(n:TargetObservation)
                RETURN count(n) AS targets
                }
                CALL {
                MATCH (i:GTDIncident {source_sha256: $source_sha256})-[:USED_WEAPON]->(n:WeaponUse)
                RETURN count(n) AS weapon_uses
                }
                CALL {
                MATCH (i:GTDIncident {source_sha256: $source_sha256})-[:HAS_ATTRIBUTION]->(n:PerpetratorAttribution)
                RETURN count(n) AS attributions
                }
                CALL {
                MATCH (i:GTDIncident {source_sha256: $source_sha256})-[:HAS_CLAIM]->(n:Claim)
                RETURN count(n) AS claims
                }
                RETURN incidents, targets, weapon_uses, attributions, claims
                """,
                source_sha256=prepared.source_sha256,
            ).single(strict=True)
        counts = dict(reconciliation)
        expected = {
            "incidents": prepared.source_rows,
            "targets": prepared.files["targets.csv"],
            "weapon_uses": prepared.files["weapon_uses.csv"],
            "attributions": prepared.files["attributions.csv"],
            "claims": prepared.files["claims.csv"],
        }
        differences = {
            name: (expected[name], counts[name])
            for name in expected
            if expected[name] != counts[name]
        }
        if differences:
            details = ", ".join(
                f"{name}: expected {wanted}, found {actual}"
                for name, (wanted, actual) in differences.items()
            )
            raise RuntimeError(f"GTD reconciliation failed: {details}")
        return GTDBatchResult(
            rows_seen=prepared.source_rows,
            incidents_written=counts["incidents"],
            source_sha256=prepared.source_sha256,
            prepared_files=prepared.files,
            reconciliation=counts,
        )


def read_preparation_manifest(output_dir: Path) -> GtdPreparationResult:
    data = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    data["extra_columns"] = tuple(data.get("extra_columns", ()))
    return GtdPreparationResult(**data)


def load_gtd(
    csv_path: Path,
    uri: str,
    user: str,
    password: str,
    *,
    import_dir: Path,
    import_uri: str,
    batch_size: int = 1_000,
    wipe: bool = False,
    replace_prepared: bool = False,
) -> GTDBatchResult:
    """Prepare the source before connecting, then load it from Neo4j's import directory."""

    prepared = prepare_gtd_csv(csv_path, import_dir, replace=replace_prepared)
    ingestor = GTDIngestor(uri, user, password)
    try:
        if wipe:
            ingestor.wipe()
        ingestor.prepare_schema()
        return ingestor.ingest_prepared(
            prepared, import_uri=import_uri, batch_size=batch_size
        )
    finally:
        ingestor.close()
