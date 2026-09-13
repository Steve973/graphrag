"""Validate a GTD export and prepare graph-shaped CSV files for Neo4j."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
import sys
import tempfile
from contextlib import ExitStack
from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable

from .gtd_schema import (
    ATTACK_FIELDS,
    CLAIM_MODE_FIELDS,
    FLOAT_COLUMNS,
    GTD_COLUMNS,
    INTEGER_COLUMNS,
)

EVENT_ID_PATTERN = re.compile(r"^[0-9]{12}$")


class GTDValidationError(ValueError):
    """Raised when the source file cannot safely be imported."""


@dataclass(frozen=True, slots=True)
class GtdPreparationResult:
    source_path: str
    output_dir: str
    source_sha256: str
    source_rows: int
    files: dict[str, int]
    extra_columns: tuple[str, ...] = ()


FILE_HEADERS: dict[str, tuple[str, ...]] = {
    "incidents.csv": (
        *GTD_COLUMNS,
        "incident_date",
        "date_precision",
        "source_row_number",
    ),
    "regions.csv": ("code", "name"),
    "countries.csv": ("code", "name"),
    "geopolitical_areas.csv": ("area_id", "country_code", "name"),
    "localities.csv": ("locality_id", "country_code", "area_id", "name"),
    "attack_types.csv": ("code", "name"),
    "target_types.csv": ("code", "name"),
    "target_subtypes.csv": ("code", "name"),
    "weapon_types.csv": ("code", "name"),
    "weapon_subtypes.csv": ("code", "name"),
    "claim_modes.csv": ("code", "name"),
    "groups.csv": ("group_id", "name"),
    "targets.csv": (
        "target_id",
        "eventid",
        "slot",
        "target",
        "corporation",
        "type_code",
        "subtype_code",
        "nationality_code",
    ),
    "weapon_uses.csv": (
        "weapon_use_id",
        "eventid",
        "slot",
        "type_code",
        "subtype_code",
    ),
    "attributions.csv": (
        "attribution_id",
        "eventid",
        "slot",
        "group_id",
        "group_name",
        "subgroup_name",
        "uncertain",
    ),
    "claims.csv": ("claim_id", "eventid", "slot", "claimed", "mode_code", "group_id"),
    "incident_regions.csv": ("eventid", "region_code"),
    "incident_countries.csv": ("eventid", "country_code"),
    "country_regions.csv": ("country_code", "region_code"),
    "incident_areas.csv": ("eventid", "area_id"),
    "incident_localities.csv": ("eventid", "locality_id"),
    "incident_attacks.csv": ("eventid", "attack_type_code", "slot"),
    "incident_targets.csv": ("eventid", "target_id"),
    "target_types_rel.csv": ("target_id", "type_code"),
    "target_subtypes_rel.csv": ("target_id", "subtype_code"),
    "target_nationalities.csv": ("target_id", "country_code"),
    "incident_weapon_uses.csv": ("eventid", "weapon_use_id"),
    "weapon_types_rel.csv": ("weapon_use_id", "type_code"),
    "weapon_subtypes_rel.csv": ("weapon_use_id", "subtype_code"),
    "incident_attributions.csv": ("eventid", "attribution_id"),
    "attribution_groups.csv": ("attribution_id", "group_id"),
    "incident_claims.csv": ("eventid", "claim_id"),
    "claim_modes_rel.csv": ("claim_id", "mode_code"),
    "claim_groups.csv": ("claim_id", "group_id"),
    "related_incidents.csv": ("eventid", "related_eventid"),
}


class _CsvOutputs:
    def __init__(self, directory: Path, stack: ExitStack) -> None:
        self.counts = {name: 0 for name in FILE_HEADERS}
        self._writers: dict[str, csv.DictWriter] = {}
        self._unique_keys: dict[str, set[str]] = {}
        for name, headers in FILE_HEADERS.items():
            handle = stack.enter_context(
                (directory / name).open("w", encoding="utf-8", newline="")
            )
            writer = csv.DictWriter(
                handle, fieldnames=headers, extrasaction="ignore", lineterminator="\n"
            )
            writer.writeheader()
            self._writers[name] = writer

    def write(self, name: str, row: dict[str, Any]) -> None:
        self._writers[name].writerow(row)
        self.counts[name] += 1

    def write_unique(self, name: str, key: str, row: dict[str, Any]) -> None:
        keys = self._unique_keys.setdefault(name, set())
        if key in keys:
            return
        keys.add(key)
        self.write(name, row)


class _Dimensions:
    def __init__(self, outputs: _CsvOutputs) -> None:
        self.outputs = outputs
        self.values: dict[str, dict[str, str]] = {}

    def add(self, filename: str, code: str, name: str, *, row_number: int) -> None:
        if not code and not name:
            return
        if not code or not name:
            raise GTDValidationError(
                f"row {row_number}: {filename} requires both a code and a name"
            )
        known = self.values.setdefault(filename, {})
        previous = known.get(code)
        if previous is not None and previous != name:
            raise GTDValidationError(
                f"row {row_number}: code {code!r} in {filename} maps to both "
                f"{previous!r} and {name!r}"
            )
        if previous is None:
            known[code] = name
            self.outputs.write(filename, {"code": code, "name": name})


def _source_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stable_key(*parts: str) -> str:
    material = "\x1f".join(part.strip().casefold() for part in parts)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _is_known_name(value: str) -> bool:
    return bool(value) and value.casefold() not in {"unknown", "not applicable", "n/a"}


def _detect_dialect(path: Path) -> type[csv.Dialect]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        sample = handle.read(128 * 1024)
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error as error:
        raise GTDValidationError(
            f"could not determine the CSV delimiter: {error}"
        ) from error


def _integer_text(value: str, column: str, row_number: int) -> str:
    try:
        number = Decimal(value)
    except InvalidOperation as error:
        raise GTDValidationError(
            f"row {row_number}: {column} must be an integer, got {value!r}"
        ) from error
    if number != number.to_integral_value():
        raise GTDValidationError(
            f"row {row_number}: {column} must be an integer, got {value!r}"
        )
    return str(int(number))


def _event_id(value: str, row_number: int) -> str:
    candidate = _integer_text(value, "eventid", row_number)
    if not EVENT_ID_PATTERN.fullmatch(candidate):
        raise GTDValidationError(
            f"row {row_number}: eventid must contain exactly 12 digits, got {value!r}"
        )
    return candidate


def _clean_row(
    raw: dict[str | None, str | list[str] | None], row_number: int
) -> dict[str, str]:
    if None in raw:
        raise GTDValidationError(
            f"row {row_number}: row has more values than the header"
        )
    row = {column: (raw.get(column) or "").strip() for column in GTD_COLUMNS}
    row["eventid"] = _event_id(row["eventid"], row_number)
    for column in INTEGER_COLUMNS:
        if row[column]:
            row[column] = _integer_text(row[column], column, row_number)
    for column in FLOAT_COLUMNS:
        if not row[column]:
            continue
        try:
            Decimal(row[column])
        except InvalidOperation as error:
            raise GTDValidationError(
                f"row {row_number}: {column} must be numeric, got {row[column]!r}"
            ) from error
    return row


def _date_values(row: dict[str, str], row_number: int) -> tuple[str, str]:
    year = int(row["iyear"])
    month = int(row["imonth"])
    day = int(row["iday"])
    if month == 0:
        if day != 0:
            raise GTDValidationError(
                f"row {row_number}: iday cannot be known when imonth is 0"
            )
        return "", "year"
    if not 1 <= month <= 12:
        raise GTDValidationError(f"row {row_number}: imonth must be from 0 through 12")
    if day == 0:
        return "", "month"
    try:
        return date(year, month, day).isoformat(), "day"
    except ValueError as error:
        raise GTDValidationError(
            f"row {row_number}: invalid incident date: {error}"
        ) from error


def _coded(
    dimensions: _Dimensions,
    filename: str,
    row: dict[str, str],
    code_column: str,
    name_column: str,
    row_number: int,
) -> tuple[str, str]:
    code, name = row[code_column], row[name_column]
    dimensions.add(filename, code, name, row_number=row_number)
    return code, name


def _write_row(
    outputs: _CsvOutputs, dimensions: _Dimensions, row: dict[str, str], row_number: int
) -> None:
    eventid = row["eventid"]
    incident_date, precision = _date_values(row, row_number)
    outputs.write(
        "incidents.csv",
        {
            **row,
            "incident_date": incident_date,
            "date_precision": precision,
            "source_row_number": row_number,
        },
    )

    region_code, _ = _coded(
        dimensions, "regions.csv", row, "region", "region_txt", row_number
    )
    country_code, _ = _coded(
        dimensions, "countries.csv", row, "country", "country_txt", row_number
    )
    if region_code:
        outputs.write(
            "incident_regions.csv", {"eventid": eventid, "region_code": region_code}
        )
    if country_code:
        outputs.write(
            "incident_countries.csv", {"eventid": eventid, "country_code": country_code}
        )
    if country_code and region_code:
        outputs.write_unique(
            "country_regions.csv",
            f"{country_code}:{region_code}",
            {"country_code": country_code, "region_code": region_code},
        )

    area_id = ""
    if _is_known_name(row["provstate"]):
        area_id = _stable_key(country_code, row["provstate"])
        outputs.write_unique(
            "geopolitical_areas.csv",
            area_id,
            {
                "area_id": area_id,
                "country_code": country_code,
                "name": row["provstate"],
            },
        )
        outputs.write("incident_areas.csv", {"eventid": eventid, "area_id": area_id})
    if _is_known_name(row["city"]):
        locality_id = _stable_key(country_code, area_id, row["city"])
        outputs.write_unique(
            "localities.csv",
            locality_id,
            {
                "locality_id": locality_id,
                "country_code": country_code,
                "area_id": area_id,
                "name": row["city"],
            },
        )
        outputs.write(
            "incident_localities.csv", {"eventid": eventid, "locality_id": locality_id}
        )

    for slot, fields in enumerate(ATTACK_FIELDS, start=1):
        code, _ = _coded(
            dimensions, "attack_types.csv", row, fields.code, fields.name, row_number
        )
        if code:
            outputs.write(
                "incident_attacks.csv",
                {"eventid": eventid, "attack_type_code": code, "slot": slot},
            )

    for slot in range(1, 4):
        target_values = [
            row[f"target{slot}"],
            row[f"corp{slot}"],
            row[f"targtype{slot}"],
            row[f"targsubtype{slot}"],
            row[f"natlty{slot}"],
        ]
        if not any(target_values):
            continue
        target_id = f"{eventid}:{slot}"
        type_code, _ = _coded(
            dimensions,
            "target_types.csv",
            row,
            f"targtype{slot}",
            f"targtype{slot}_txt",
            row_number,
        )
        subtype_code, _ = _coded(
            dimensions,
            "target_subtypes.csv",
            row,
            f"targsubtype{slot}",
            f"targsubtype{slot}_txt",
            row_number,
        )
        nationality_code, _ = _coded(
            dimensions,
            "countries.csv",
            row,
            f"natlty{slot}",
            f"natlty{slot}_txt",
            row_number,
        )
        outputs.write(
            "targets.csv",
            {
                "target_id": target_id,
                "eventid": eventid,
                "slot": slot,
                "target": row[f"target{slot}"],
                "corporation": row[f"corp{slot}"],
                "type_code": type_code,
                "subtype_code": subtype_code,
                "nationality_code": nationality_code,
            },
        )
        outputs.write(
            "incident_targets.csv", {"eventid": eventid, "target_id": target_id}
        )
        if type_code:
            outputs.write(
                "target_types_rel.csv", {"target_id": target_id, "type_code": type_code}
            )
        if subtype_code:
            outputs.write(
                "target_subtypes_rel.csv",
                {"target_id": target_id, "subtype_code": subtype_code},
            )
        if nationality_code:
            outputs.write(
                "target_nationalities.csv",
                {"target_id": target_id, "country_code": nationality_code},
            )

    group_ids: dict[int, str] = {}
    for slot in range(1, 4):
        suffix = "" if slot == 1 else str(slot)
        group_name = row[f"gname{suffix}"]
        subgroup_name = row[f"gsubname{suffix}"]
        uncertain = row[f"guncertain{slot}"]
        if not any((group_name, subgroup_name, uncertain)):
            continue
        attribution_id = f"{eventid}:{slot}"
        group_id = ""
        if group_name and group_name.casefold() not in {"unknown", "other"}:
            group_id = _stable_key(group_name)
            group_ids[slot] = group_id
            outputs.write_unique(
                "groups.csv", group_id, {"group_id": group_id, "name": group_name}
            )
        outputs.write(
            "attributions.csv",
            {
                "attribution_id": attribution_id,
                "eventid": eventid,
                "slot": slot,
                "group_id": group_id,
                "group_name": group_name,
                "subgroup_name": subgroup_name,
                "uncertain": uncertain,
            },
        )
        outputs.write(
            "incident_attributions.csv",
            {"eventid": eventid, "attribution_id": attribution_id},
        )
        if group_id:
            outputs.write(
                "attribution_groups.csv",
                {"attribution_id": attribution_id, "group_id": group_id},
            )

    for slot in range(1, 5):
        type_code, _ = _coded(
            dimensions,
            "weapon_types.csv",
            row,
            f"weaptype{slot}",
            f"weaptype{slot}_txt",
            row_number,
        )
        subtype_code, _ = _coded(
            dimensions,
            "weapon_subtypes.csv",
            row,
            f"weapsubtype{slot}",
            f"weapsubtype{slot}_txt",
            row_number,
        )
        if not type_code and not subtype_code:
            continue
        weapon_use_id = f"{eventid}:{slot}"
        outputs.write(
            "weapon_uses.csv",
            {
                "weapon_use_id": weapon_use_id,
                "eventid": eventid,
                "slot": slot,
                "type_code": type_code,
                "subtype_code": subtype_code,
            },
        )
        outputs.write(
            "incident_weapon_uses.csv",
            {"eventid": eventid, "weapon_use_id": weapon_use_id},
        )
        if type_code:
            outputs.write(
                "weapon_types_rel.csv",
                {"weapon_use_id": weapon_use_id, "type_code": type_code},
            )
        if subtype_code:
            outputs.write(
                "weapon_subtypes_rel.csv",
                {"weapon_use_id": weapon_use_id, "subtype_code": subtype_code},
            )

    for slot, fields in enumerate(CLAIM_MODE_FIELDS, start=1):
        claim_column = "claimed" if slot == 1 else f"claim{slot}"
        claimed, mode_code = row[claim_column], row[fields.code]
        if claimed != "1" and mode_code in {"", "0"}:
            continue
        claim_id = f"{eventid}:{slot}"
        _coded(dimensions, "claim_modes.csv", row, fields.code, fields.name, row_number)
        outputs.write(
            "claims.csv",
            {
                "claim_id": claim_id,
                "eventid": eventid,
                "slot": slot,
                "claimed": claimed,
                "mode_code": mode_code,
                "group_id": group_ids.get(slot, ""),
            },
        )
        outputs.write("incident_claims.csv", {"eventid": eventid, "claim_id": claim_id})
        if mode_code:
            outputs.write(
                "claim_modes_rel.csv", {"claim_id": claim_id, "mode_code": mode_code}
            )
        if slot in group_ids:
            outputs.write(
                "claim_groups.csv", {"claim_id": claim_id, "group_id": group_ids[slot]}
            )

    for related_id in _related_ids(row["related"], row_number):
        if related_id != eventid:
            first, second = sorted((eventid, related_id))
            outputs.write_unique(
                "related_incidents.csv",
                f"{first}:{second}",
                {"eventid": first, "related_eventid": second},
            )


def _related_ids(value: str, row_number: int) -> Iterable[str]:
    if not value:
        return ()
    ids: list[str] = []
    for item in value.split(","):
        candidate = item.strip()
        if candidate:
            ids.append(_event_id(candidate, row_number))
    return tuple(dict.fromkeys(ids))


def prepare_gtd_csv(
    source_path: Path,
    output_dir: Path,
    *,
    replace: bool = False,
) -> GtdPreparationResult:
    """Validate one denormalized GTD CSV and create normalized Neo4j import files."""

    source_path = source_path.resolve()
    output_dir = output_dir.resolve()
    if not source_path.is_file():
        raise GTDValidationError(f"GTD source file does not exist: {source_path}")
    if source_path.is_relative_to(output_dir):
        raise GTDValidationError(
            "the source CSV cannot be inside the preparation directory"
        )
    if output_dir.exists():
        if not replace:
            raise GTDValidationError(f"output directory already exists: {output_dir}")
        if not output_dir.is_dir() or not (output_dir / "manifest.json").is_file():
            raise GTDValidationError(
                f"refusing to replace a directory not created by this preparer: {output_dir}"
            )
        allowed = {*FILE_HEADERS, "manifest.json"}
        unexpected = sorted(
            path.name for path in output_dir.iterdir() if path.name not in allowed
        )
        if unexpected:
            raise GTDValidationError(
                f"refusing to replace output containing unexpected files: {', '.join(unexpected)}"
            )
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    csv.field_size_limit(min(sys.maxsize, 2**31 - 1))
    dialect = _detect_dialect(source_path)
    source_hash = _source_sha256(source_path)
    temporary = Path(
        tempfile.mkdtemp(prefix=f".{output_dir.name}-", dir=output_dir.parent)
    )
    row_count = 0
    seen_event_ids: set[str] = set()
    extra_columns: tuple[str, ...] = ()
    try:
        with ExitStack() as stack:
            outputs = _CsvOutputs(temporary, stack)
            dimensions = _Dimensions(outputs)
            source = stack.enter_context(
                source_path.open("r", encoding="utf-8-sig", newline="")
            )
            reader = csv.DictReader(source, dialect=dialect)
            headers = tuple(reader.fieldnames or ())
            duplicates = sorted(
                {header for header in headers if headers.count(header) > 1}
            )
            missing = sorted(set(GTD_COLUMNS) - set(headers))
            extra_columns = tuple(sorted(set(headers) - set(GTD_COLUMNS)))
            if duplicates or missing:
                problems = []
                if missing:
                    problems.append(f"missing columns: {', '.join(missing)}")
                if duplicates:
                    problems.append(f"duplicate columns: {', '.join(duplicates)}")
                raise GTDValidationError("; ".join(problems))
            for row_number, raw in enumerate(reader, start=2):
                row = _clean_row(raw, row_number)
                if row["eventid"] in seen_event_ids:
                    raise GTDValidationError(
                        f"row {row_number}: duplicate eventid {row['eventid']}"
                    )
                seen_event_ids.add(row["eventid"])
                _write_row(outputs, dimensions, row, row_number)
                row_count += 1

        result = GtdPreparationResult(
            source_path=str(source_path),
            output_dir=str(output_dir),
            source_sha256=source_hash,
            source_rows=row_count,
            files=dict(outputs.counts),
            extra_columns=extra_columns,
        )
        (temporary / "manifest.json").write_text(
            json.dumps(asdict(result), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        if output_dir.exists():
            shutil.rmtree(output_dir)
        temporary.rename(output_dir)
        return result
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
