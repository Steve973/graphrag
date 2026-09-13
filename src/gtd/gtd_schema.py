"""Source and graph contracts for the Global Terrorism Database export."""

from __future__ import annotations

from dataclasses import dataclass

GTD_COLUMNS = (
    "eventid",
    "iyear",
    "imonth",
    "iday",
    "approxdate",
    "extended",
    "resolution",
    "country",
    "country_txt",
    "region",
    "region_txt",
    "provstate",
    "city",
    "latitude",
    "longitude",
    "specificity",
    "vicinity",
    "location",
    "summary",
    "crit1",
    "crit2",
    "crit3",
    "doubtterr",
    "alternative",
    "alternative_txt",
    "multiple",
    "success",
    "suicide",
    "attacktype1",
    "attacktype1_txt",
    "attacktype2",
    "attacktype2_txt",
    "attacktype3",
    "attacktype3_txt",
    "targtype1",
    "targtype1_txt",
    "targsubtype1",
    "targsubtype1_txt",
    "corp1",
    "target1",
    "natlty1",
    "natlty1_txt",
    "targtype2",
    "targtype2_txt",
    "targsubtype2",
    "targsubtype2_txt",
    "corp2",
    "target2",
    "natlty2",
    "natlty2_txt",
    "targtype3",
    "targtype3_txt",
    "targsubtype3",
    "targsubtype3_txt",
    "corp3",
    "target3",
    "natlty3",
    "natlty3_txt",
    "gname",
    "gsubname",
    "gname2",
    "gsubname2",
    "gname3",
    "gsubname3",
    "motive",
    "guncertain1",
    "guncertain2",
    "guncertain3",
    "individual",
    "nperps",
    "nperpcap",
    "claimed",
    "claimmode",
    "claimmode_txt",
    "claim2",
    "claimmode2",
    "claimmode2_txt",
    "claim3",
    "claimmode3",
    "claimmode3_txt",
    "compclaim",
    "weaptype1",
    "weaptype1_txt",
    "weapsubtype1",
    "weapsubtype1_txt",
    "weaptype2",
    "weaptype2_txt",
    "weapsubtype2",
    "weapsubtype2_txt",
    "weaptype3",
    "weaptype3_txt",
    "weapsubtype3",
    "weapsubtype3_txt",
    "weaptype4",
    "weaptype4_txt",
    "weapsubtype4",
    "weapsubtype4_txt",
    "weapdetail",
    "nkill",
    "nkillus",
    "nkillter",
    "nwound",
    "nwoundus",
    "nwoundte",
    "property",
    "propextent",
    "propextent_txt",
    "propvalue",
    "propcomment",
    "ishostkid",
    "nhostkid",
    "nhostkidus",
    "nhours",
    "ndays",
    "divert",
    "kidhijcountry",
    "ransom",
    "ransomamt",
    "ransomamtus",
    "ransompaid",
    "ransompaidus",
    "ransomnote",
    "hostkidoutcome",
    "hostkidoutcome_txt",
    "nreleased",
    "addnotes",
    "scite1",
    "scite2",
    "scite3",
    "dbsource",
    "INT_LOG",
    "INT_IDEO",
    "INT_MISC",
    "INT_ANY",
    "related",
)

# CSV input is textual. These sets define the only automatic numeric conversions.
INTEGER_COLUMNS = frozenset(
    {
        "iyear",
        "imonth",
        "iday",
        "extended",
        "country",
        "region",
        "specificity",
        "vicinity",
        "crit1",
        "crit2",
        "crit3",
        "doubtterr",
        "alternative",
        "multiple",
        "success",
        "suicide",
        "attacktype1",
        "attacktype2",
        "attacktype3",
        "targtype1",
        "targsubtype1",
        "natlty1",
        "targtype2",
        "targsubtype2",
        "natlty2",
        "targtype3",
        "targsubtype3",
        "natlty3",
        "guncertain1",
        "guncertain2",
        "guncertain3",
        "individual",
        "nperps",
        "nperpcap",
        "claimed",
        "claimmode",
        "claim2",
        "claimmode2",
        "claim3",
        "claimmode3",
        "compclaim",
        "weaptype1",
        "weapsubtype1",
        "weaptype2",
        "weapsubtype2",
        "weaptype3",
        "weapsubtype3",
        "weaptype4",
        "weapsubtype4",
        "nkill",
        "nkillus",
        "nkillter",
        "nwound",
        "nwoundus",
        "nwoundte",
        "property",
        "propextent",
        "ishostkid",
        "nhostkid",
        "nhostkidus",
        "nhours",
        "ndays",
        "ransom",
        "hostkidoutcome",
        "nreleased",
        "INT_LOG",
        "INT_IDEO",
        "INT_MISC",
        "INT_ANY",
    }
)

FLOAT_COLUMNS = frozenset(
    {
        "latitude",
        "longitude",
        "propvalue",
        "ransomamt",
        "ransomamtus",
        "ransompaid",
        "ransompaidus",
    }
)


@dataclass(frozen=True, slots=True)
class CodedField:
    code: str
    name: str


ATTACK_FIELDS = tuple(
    CodedField(f"attacktype{i}", f"attacktype{i}_txt") for i in range(1, 4)
)
TARGET_TYPE_FIELDS = tuple(
    CodedField(f"targtype{i}", f"targtype{i}_txt") for i in range(1, 4)
)
TARGET_SUBTYPE_FIELDS = tuple(
    CodedField(f"targsubtype{i}", f"targsubtype{i}_txt") for i in range(1, 4)
)
NATIONALITY_FIELDS = tuple(
    CodedField(f"natlty{i}", f"natlty{i}_txt") for i in range(1, 4)
)
WEAPON_TYPE_FIELDS = tuple(
    CodedField(f"weaptype{i}", f"weaptype{i}_txt") for i in range(1, 5)
)
WEAPON_SUBTYPE_FIELDS = tuple(
    CodedField(f"weapsubtype{i}", f"weapsubtype{i}_txt") for i in range(1, 5)
)
CLAIM_MODE_FIELDS = (
    CodedField("claimmode", "claimmode_txt"),
    CodedField("claimmode2", "claimmode2_txt"),
    CodedField("claimmode3", "claimmode3_txt"),
)


def cypher_property_expression(column: str) -> str:
    """Return the LOAD CSV expression for one GTD property."""

    value = f"trim(row.`{column}`)"
    if column in INTEGER_COLUMNS:
        converted = f"toIntegerOrNull({value})"
    elif column in FLOAT_COLUMNS:
        converted = f"toFloatOrNull({value})"
    else:
        converted = value
    return f"CASE {value} WHEN '' THEN null ELSE {converted} END"
