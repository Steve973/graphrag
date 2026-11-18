"""Evaluate typed operations over query rows and retain their source pointers."""

from __future__ import annotations

from collections import Counter
from typing import Annotated, Literal
import math
import operator
import re

from pydantic import Field, JsonValue, StrictBool, StrictFloat, StrictInt, StrictStr
from pydantic import model_validator

from graphrag.model.base import ContractModel, NonEmptyStr
from graphrag.model.tool_operations import ToolCallResult, ToolResultStatus

Scalar = StrictBool | StrictInt | StrictFloat | StrictStr
Comparison = Literal["eq", "ne", "lt", "le", "gt", "ge"]
Relation = Literal["SUPPORTS", "CONTRADICTS", "PARTIAL", "QUALIFIES",
                   "CONTEXTUALIZES", "CHALLENGES"]
COMPARISONS = {
    "eq": operator.eq, "ne": operator.ne, "lt": operator.lt,
    "le": operator.le, "gt": operator.gt, "ge": operator.ge,
}
ScalarType = Literal["boolean", "integer", "number", "string", "object", "array", "null"]
JSON_TYPES: dict[type, ScalarType] = {
    bool: "boolean", int: "integer", float: "number", str: "string",
    dict: "object", list: "array", type(None): "null",
}


class EvaluationError(ValueError):
    """An expression cannot be evaluated safely on the given row data."""


class Predicate(ContractModel):
    field: NonEmptyStr
    op: Comparison
    value: Scalar


class Expression(ContractModel):
    filters: list[Predicate]
    reduce: Literal["count", "count_distinct", "min", "max", "value"]
    field: NonEmptyStr | None
    compare: Comparison
    target: Scalar

    def validate_operations(self) -> None:
        if (self.reduce == "count") != (self.field is None):
            raise EvaluationError("count uses no field; every other reduction requires a field")
        if self.reduce in {"count", "count_distinct"} and (
            type(self.target) is not int or self.target < 0
        ):
            raise EvaluationError("count targets must be nonnegative integers")


class Assertion(ContractModel):
    id: NonEmptyStr
    statement: NonEmptyStr
    expression: Expression | None = None
    expected: ExpectedFinding | None = None


class ExpectedFinding(ContractModel):
    relation: Relation | None
    pointers: list[str] | None = None
    value: Scalar | None = None


class Case(ContractModel):
    id: NonEmptyStr
    criterion: NonEmptyStr
    query: NonEmptyStr
    result: ToolCallResult
    rows_pointer: str = ""
    coverage: Literal["complete", "partial", "unknown"] = "unknown"
    assertions: Annotated[list[Assertion], Field(min_length=1)]

    @model_validator(mode="after")
    def validate_input(self) -> Case:
        if self.result.status != ToolResultStatus.SUCCESS:
            raise ValueError("replay requires an acquired, successful query result")
        if len({item.id for item in self.assertions}) != len(self.assertions):
            raise ValueError("assertion IDs must be unique within a case")
        return self


class Column(ContractModel):
    name: str
    types: list[ScalarType]
    missing: int


class Finding(ContractModel):
    assertion_id: NonEmptyStr
    result_id: NonEmptyStr
    relation: Relation
    statement: NonEmptyStr
    pointers: Annotated[list[str], Field(min_length=1)]
    value: Scalar | None = None


def child_pointer(parent: str, key: str | int) -> str:
    token = str(key).replace("~", "~0").replace("/", "~1")
    return f"{parent}/{token}"


def resolve_pointer(document: JsonValue, pointer: str) -> JsonValue:
    if pointer == "":
        return document
    if not pointer.startswith("/"):
        raise EvaluationError(f"Invalid JSON pointer {pointer!r}")
    for token in pointer[1:].split("/"):
        if re.search(r"~(?![01])", token):
            raise EvaluationError(f"Invalid escape in JSON pointer {pointer!r}")
        key = token.replace("~1", "/").replace("~0", "~")
        if isinstance(document, dict) and key in document:
            document = document[key]
        elif isinstance(document, list) and re.fullmatch(r"0|[1-9][0-9]*", key):
            if len(key) <= len(str(len(document))) and int(key) < len(document):
                document = document[int(key)]
            else:
                raise EvaluationError(f"JSON pointer {pointer!r} is out of range")
        else:
            raise EvaluationError(f"JSON pointer {pointer!r} does not resolve")
    return document


def load_rows(case: Case) -> list[dict[str, JsonValue]]:
    value = resolve_pointer(case.result.data, case.rows_pointer)
    if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
        raise EvaluationError("rows_pointer must identify a JSON array of objects")
    return value


def infer_schema(rows: list[dict[str, JsonValue]]) -> list[Column]:
    types: dict[str, set[ScalarType]] = {}
    present: Counter[str] = Counter()
    for row in rows:
        for name, value in row.items():
            types.setdefault(name, set()).add(JSON_TYPES[type(value)])
            present[name] += 1
    return [Column(name=name, types=sorted(kinds), missing=len(rows) - present[name])
            for name, kinds in sorted(types.items())]


def scalar_kind(value: JsonValue, field: str) -> str:
    if type(value) in {int, float}:
        if isinstance(value, float) and not math.isfinite(value):
            raise EvaluationError(f"{field!r} contains a nonfinite number")
        return "numeric"
    if type(value) in {str, bool}:
        return JSON_TYPES[type(value)]
    raise EvaluationError(f"{field!r} requires a non-null scalar")


def compare(left: Scalar, op: Comparison, right: Scalar, field: str) -> bool:
    kind = scalar_kind(left, field)
    if kind != scalar_kind(right, field) or (kind == "boolean" and op not in {"eq", "ne"}):
        raise EvaluationError(f"Incompatible operands for {op} on {field!r}")
    return COMPARISONS[op](left, right)


def read_field(row: dict[str, JsonValue], field: str) -> Scalar:
    if field not in row:
        raise EvaluationError(f"Field {field!r} is missing from a row used by the expression")
    value = row[field]
    scalar_kind(value, field)
    return value


def relation_for_value(
    value: Scalar, expression: Expression, complete: bool
) -> Relation:
    op, target = expression.compare, expression.target
    matches = compare(value, op, target, expression.field or "count")
    if complete:
        return "SUPPORTS" if matches else "CONTRADICTS"

    # Adding rows can only increase counts/maxima and decrease minima.
    if expression.reduce in {"count", "count_distinct", "max"}:
        if (matches and op in {"ge", "gt"}) or (not matches and op in {"le", "lt"}):
            return "SUPPORTS" if matches else "CONTRADICTS"
        if value > target and op in {"eq", "ne"}:
            return "CONTRADICTS" if op == "eq" else "SUPPORTS"
    elif expression.reduce == "min":
        if (matches and op in {"le", "lt"}) or (not matches and op in {"ge", "gt"}):
            return "SUPPORTS" if matches else "CONTRADICTS"
        if value < target and op in {"eq", "ne"}:
            return "CONTRADICTS" if op == "eq" else "SUPPORTS"
    return "PARTIAL"


def evaluate(
    case: Case, assertion: Assertion, expression: Expression,
    rows: list[dict[str, JsonValue]], schema: list[Column],
) -> Finding | None:
    expression.validate_operations()
    names = {column.name for column in schema}
    used_fields = {item.field for item in expression.filters}
    if expression.field is not None:
        used_fields.add(expression.field)
    if rows and used_fields - names:
        raise EvaluationError(f"Unknown fields: {sorted(used_fields - names)}")

    selected = []
    for index, row in enumerate(rows):
        for predicate in expression.filters:
            value = read_field(row, predicate.field)
            if not compare(value, predicate.op, predicate.value, predicate.field):
                break
        else:
            selected.append(index)

    metric = expression.reduce
    field = expression.field
    if metric == "count":
        value = len(selected)
    else:
        assert field is not None  # Validated by validate_operations.
        if not selected and metric != "count_distinct":
            return None
        values = [read_field(rows[index], field) for index in selected]
        kinds = {scalar_kind(item, field) for item in values}
        if len(kinds) > 1 or (metric in {"min", "max"} and kinds == {"boolean"}):
            raise EvaluationError(f"Cannot apply {metric} to the values in {field!r}")
        if metric == "count_distinct":
            representatives = {}
            for item, index in zip(values, selected, strict=True):
                representatives.setdefault(item, index)
            value = len(representatives)
            selected = list(representatives.values())
        elif metric in {"min", "max"}:
            reduce_values = min if metric == "min" else max
            value = reduce_values(values)
            if case.coverage == "complete":
                # The entire row collection is needed to establish an exact extremum.
                selected = []
            else:
                selected = [selected[values.index(value)]]
        else:
            if len(values) != 1:
                raise EvaluationError("value requires exactly one selected row")
            value = values[0]

    relation = relation_for_value(value, expression, case.coverage == "complete")
    if not selected and value == 0 and relation == "PARTIAL":
        return None
    pointers = [child_pointer(case.rows_pointer, index) for index in selected]
    if not pointers or (case.coverage == "complete" and relation in {"SUPPORTS", "CONTRADICTS"}):
        # Preserve the examined collection for conclusions relying on full coverage.
        pointers = [case.rows_pointer, *pointers]
    scope = "complete result" if case.coverage == "complete" else "returned rows"
    metric_name = f"{metric}({field})" if field is not None else metric
    return Finding(
        assertion_id=assertion.id, result_id=case.result.id, relation=relation,
        value=value, pointers=pointers,
        statement=f"{metric_name} over matching rows in the {scope} is {value!r}.",
    )
