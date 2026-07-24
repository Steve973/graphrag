from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterable, TYPE_CHECKING

if TYPE_CHECKING:
    from neo4j import Driver


INCIDENT_UNIQUE_CONSTRAINTS = [
    "CREATE CONSTRAINT incident_eventid IF NOT EXISTS FOR (i:Incident) REQUIRE i.eventid IS UNIQUE",
    "CREATE CONSTRAINT country_name IF NOT EXISTS FOR (n:Country) REQUIRE n.name IS UNIQUE",
    "CREATE CONSTRAINT region_name IF NOT EXISTS FOR (n:Region) REQUIRE n.name IS UNIQUE",
    "CREATE CONSTRAINT province_name IF NOT EXISTS FOR (n:Province) REQUIRE n.name IS UNIQUE",
    "CREATE CONSTRAINT city_name IF NOT EXISTS FOR (n:City) REQUIRE n.name IS UNIQUE",
    "CREATE CONSTRAINT attack_type_name IF NOT EXISTS FOR (n:AttackType) REQUIRE n.name IS UNIQUE",
    "CREATE CONSTRAINT target_type_name IF NOT EXISTS FOR (n:TargetType) REQUIRE n.name IS UNIQUE",
    "CREATE CONSTRAINT target_subtype_name IF NOT EXISTS FOR (n:TargetSubType) REQUIRE n.name IS UNIQUE",
    "CREATE CONSTRAINT weapon_type_name IF NOT EXISTS FOR (n:WeaponType) REQUIRE n.name IS UNIQUE",
    "CREATE CONSTRAINT weapon_subtype_name IF NOT EXISTS FOR (n:WeaponSubType) REQUIRE n.name IS UNIQUE",
    "CREATE CONSTRAINT group_name IF NOT EXISTS FOR (n:Group) REQUIRE n.name IS UNIQUE",
]

INCIDENT_INDEXES = [
    "CREATE INDEX incident_year IF NOT EXISTS FOR (i:Incident) ON (i.iyear)",
    "CREATE INDEX incident_date IF NOT EXISTS FOR (i:Incident) ON (i.incident_date)",
]


@dataclass(slots=True)
class GTDBatchResult:
    rows_seen: int
    incidents_written: int


def _normalize_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        cleaned = value.strip()
        if cleaned == "":
            return None
        lower = cleaned.lower()
        if lower in {"na", "n/a", "null", "none", "nan"}:
            return None
        if cleaned.isdigit():
            try:
                return int(cleaned)
            except ValueError:
                return cleaned
        try:
            if "." in cleaned:
                return float(cleaned)
        except ValueError:
            pass
        return cleaned
    return value


def _make_date(parts: dict[str, Any]) -> str | None:
    year = parts.get("iyear")
    month = parts.get("imonth")
    day = parts.get("iday")
    if not year:
        return None
    try:
        month_int = int(month or 1)
        day_int = int(day or 1)
        return date(int(year), month_int, day_int).isoformat()
    except ValueError:
        return None


def _entity(value: Any) -> dict[str, Any] | None:
    normalized = _normalize_value(value)
    if normalized is None:
        return None
    return {"name": normalized}


def _slot_entities(values: Iterable[Any]) -> list[dict[str, Any]]:
    entities: list[dict[str, Any]] = []
    for value in values:
        entity = _entity(value)
        if entity is not None:
            entities.append(entity)
    return entities


def build_incident_payload(row: dict[str, Any], *, source_row_number: int | None = None) -> dict[str, Any]:
    normalized = {key: _normalize_value(value) for key, value in row.items()}
    eventid = normalized.get("eventid")
    if eventid is None:
        raise ValueError("Row is missing eventid")

    incident = {
        key: value
        for key, value in normalized.items()
        if value is not None and key not in {
            "country_txt",
            "region_txt",
            "provstate",
            "city",
            "attacktype1_txt",
            "attacktype2_txt",
            "attacktype3_txt",
            "targtype1_txt",
            "targtype2_txt",
            "targtype3_txt",
            "targsubtype1_txt",
            "targsubtype2_txt",
            "targsubtype3_txt",
            "weaptype1_txt",
            "weaptype2_txt",
            "weaptype3_txt",
            "weapsubtype1_txt",
            "weapsubtype2_txt",
            "weapsubtype3_txt",
            "gname",
            "gname2",
            "gname3",
            "gname4",
        }
    }
    incident["incident_date"] = _make_date(normalized)
    if source_row_number is not None:
        incident["source_row_number"] = source_row_number

    return {
        "incident": incident,
        "country": _entity(normalized.get("country_txt")),
        "region": _entity(normalized.get("region_txt")),
        "province": _entity(normalized.get("provstate")),
        "city": _entity(normalized.get("city")),
        "attack_types": _slot_entities(
            [normalized.get("attacktype1_txt"), normalized.get("attacktype2_txt"), normalized.get("attacktype3_txt")]
        ),
        "target_types": _slot_entities(
            [normalized.get("targtype1_txt"), normalized.get("targtype2_txt"), normalized.get("targtype3_txt")]
        ),
        "target_subtypes": _slot_entities(
            [normalized.get("targsubtype1_txt"), normalized.get("targsubtype2_txt"), normalized.get("targsubtype3_txt")]
        ),
        "weapon_types": _slot_entities(
            [normalized.get("weaptype1_txt"), normalized.get("weaptype2_txt"), normalized.get("weaptype3_txt")]
        ),
        "weapon_subtypes": _slot_entities(
            [normalized.get("weapsubtype1_txt"), normalized.get("weapsubtype2_txt"), normalized.get("weapsubtype3_txt")]
        ),
        "groups": _slot_entities([normalized.get("gname"), normalized.get("gname2"), normalized.get("gname3"), normalized.get("gname4")]),
    }


def _chunked(items: list[dict[str, Any]], size: int) -> Iterable[list[dict[str, Any]]]:
    for index in range(0, len(items), size):
        yield items[index : index + size]


class GTDIngestor:
    def __init__(self, uri: str, user: str, password: str) -> None:
        from neo4j import GraphDatabase

        self._driver: Driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self) -> None:
        self._driver.close()

    def prepare_schema(self) -> None:
        with self._driver.session() as session:
            for statement in INCIDENT_UNIQUE_CONSTRAINTS + INCIDENT_INDEXES:
                session.run(statement).consume()

    def wipe(self) -> None:
        with self._driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n").consume()

    def ingest_csv(self, csv_path: Path, *, batch_size: int = 500) -> GTDBatchResult:
        rows: list[dict[str, Any]] = []
        rows_seen = 0
        incidents_written = 0

        with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row_number, row in enumerate(reader, start=2):
                payload = build_incident_payload(row, source_row_number=row_number)
                rows.append(payload)
                rows_seen += 1
                if len(rows) >= batch_size:
                    incidents_written += self._write_batch(rows)
                    rows.clear()

        if rows:
            incidents_written += self._write_batch(rows)

        return GTDBatchResult(rows_seen=rows_seen, incidents_written=incidents_written)

    def _write_batch(self, batch: list[dict[str, Any]]) -> int:
        query = """
        UNWIND $rows AS row
        MERGE (i:Incident {eventid: row.incident.eventid})
        SET i += row.incident

        FOREACH (item IN CASE WHEN row.country IS NULL THEN [] ELSE [row.country] END |
          MERGE (n:Country {name: item.name})
          MERGE (i)-[:OCCURRED_IN_COUNTRY]->(n)
        )
        FOREACH (item IN CASE WHEN row.region IS NULL THEN [] ELSE [row.region] END |
          MERGE (n:Region {name: item.name})
          MERGE (i)-[:OCCURRED_IN_REGION]->(n)
        )
        FOREACH (item IN CASE WHEN row.province IS NULL THEN [] ELSE [row.province] END |
          MERGE (n:Province {name: item.name})
          MERGE (i)-[:OCCURRED_IN_PROVINCE]->(n)
        )
        FOREACH (item IN CASE WHEN row.city IS NULL THEN [] ELSE [row.city] END |
          MERGE (n:City {name: item.name})
          MERGE (i)-[:OCCURRED_IN_CITY]->(n)
        )
        FOREACH (item IN row.attack_types |
          MERGE (n:AttackType {name: item.name})
          MERGE (i)-[:HAS_ATTACK_TYPE]->(n)
        )
        FOREACH (item IN row.target_types |
          MERGE (n:TargetType {name: item.name})
          MERGE (i)-[:HAS_TARGET_TYPE]->(n)
        )
        FOREACH (item IN row.target_subtypes |
          MERGE (n:TargetSubType {name: item.name})
          MERGE (i)-[:HAS_TARGET_SUBTYPE]->(n)
        )
        FOREACH (item IN row.weapon_types |
          MERGE (n:WeaponType {name: item.name})
          MERGE (i)-[:USED_WEAPON_TYPE]->(n)
        )
        FOREACH (item IN row.weapon_subtypes |
          MERGE (n:WeaponSubType {name: item.name})
          MERGE (i)-[:USED_WEAPON_SUBTYPE]->(n)
        )
        FOREACH (item IN row.groups |
          MERGE (n:Group {name: item.name})
          MERGE (i)-[:ATTRIBUTED_TO]->(n)
        )
        """
        with self._driver.session() as session:
            result = session.execute_write(lambda tx: tx.run(query, rows=batch).consume())
        return len(batch)


def load_gtd(csv_path: Path, uri: str, user: str, password: str, *, batch_size: int = 500, wipe: bool = False) -> GTDBatchResult:
    ingestor = GTDIngestor(uri, user, password)
    try:
        ingestor.prepare_schema()
        if wipe:
            ingestor.wipe()
        return ingestor.ingest_csv(csv_path, batch_size=batch_size)
    finally:
        ingestor.close()
