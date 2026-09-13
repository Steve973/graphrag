from __future__ import annotations

import csv
from pathlib import Path

import pytest

from gtd.gtd_prepare import GTDValidationError, prepare_gtd_csv
from gtd.gtd_schema import GTD_COLUMNS


def _write_source(path: Path, rows: list[dict[str, str]], headers: tuple[str, ...] = GTD_COLUMNS) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def _row(eventid: str = "202001010001") -> dict[str, str]:
    row = dict.fromkeys(GTD_COLUMNS, "")
    row.update({
        "eventid": eventid,
        "iyear": "2020",
        "imonth": "1",
        "iday": "1",
        "country": "217",
        "country_txt": "United States",
        "region": "1",
        "region_txt": "North America",
        "provstate": "Georgia",
        "city": "Springfield",
        "attacktype1": "3",
        "attacktype1_txt": "Bombing/Explosion",
        "targtype1": "1",
        "targtype1_txt": "Business",
        "targsubtype1": "2",
        "targsubtype1_txt": "Restaurant/Bar/Cafe",
        "corp1": "Example Cafe",
        "target1": "Front entrance",
        "natlty1": "217",
        "natlty1_txt": "United States",
        "gname": "Example Group",
        "guncertain1": "0",
        "claimed": "1",
        "claimmode": "1",
        "claimmode_txt": "Letter",
        "weaptype1": "6",
        "weaptype1_txt": "Explosives",
        "weapsubtype1": "16",
        "weapsubtype1_txt": "Unknown Explosive Type",
        "weaptype4": "5",
        "weaptype4_txt": "Firearms",
        "weapsubtype4": "3",
        "weapsubtype4_txt": "Handgun",
    })
    return row


def _read(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_prepares_normalized_nodes_and_slot_relationships(tmp_path: Path) -> None:
    source = tmp_path / "gtd.csv"
    output = tmp_path / "prepared"
    _write_source(source, [_row()])

    result = prepare_gtd_csv(source, output)

    assert result.source_rows == 1
    assert result.files["incidents.csv"] == 1
    assert result.files["targets.csv"] == 1
    assert result.files["weapon_uses.csv"] == 2
    assert {item["slot"] for item in _read(output / "weapon_uses.csv")} == {"1", "4"}
    assert _read(output / "targets.csv")[0]["target_id"] == "202001010001:1"
    assert _read(output / "incidents.csv")[0]["date_precision"] == "day"
    assert len(_read(output / "countries.csv")) == 1


def test_scopes_same_named_places_by_country(tmp_path: Path) -> None:
    source = tmp_path / "gtd.csv"
    output = tmp_path / "prepared"
    first = _row("202001010001")
    second = _row("202001010002")
    second.update({"country": "185", "country_txt": "Spain"})
    _write_source(source, [first, second])

    prepare_gtd_csv(source, output)

    assert len(_read(output / "geopolitical_areas.csv")) == 2
    assert len(_read(output / "localities.csv")) == 2


def test_preserves_partial_date_precision(tmp_path: Path) -> None:
    source = tmp_path / "gtd.csv"
    output = tmp_path / "prepared"
    row = _row()
    row.update({"imonth": "0", "iday": "0"})
    _write_source(source, [row])

    prepare_gtd_csv(source, output)

    incident = _read(output / "incidents.csv")[0]
    assert incident["incident_date"] == ""
    assert incident["date_precision"] == "year"


def test_rejects_missing_columns_before_creating_output(tmp_path: Path) -> None:
    source = tmp_path / "gtd.csv"
    output = tmp_path / "prepared"
    headers = tuple(column for column in GTD_COLUMNS if column != "eventid")
    _write_source(source, [{}], headers=headers)

    with pytest.raises(GTDValidationError, match="missing columns: eventid"):
        prepare_gtd_csv(source, output)

    assert not output.exists()


def test_rejects_duplicate_event_ids(tmp_path: Path) -> None:
    source = tmp_path / "gtd.csv"
    output = tmp_path / "prepared"
    _write_source(source, [_row(), _row()])

    with pytest.raises(GTDValidationError, match="duplicate eventid"):
        prepare_gtd_csv(source, output)

    assert not output.exists()
