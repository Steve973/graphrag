"""Execute composable table operations over rows with source lineage."""

from dataclasses import dataclass
import operator
from statistics import mean

from pydantic import JsonValue

from .evaluator import (
    Aggregate, Assertion, Case, Column, DeriveField, EvaluationError, FieldOperand,
    FilterRows, Finding, GroupRows, LimitRows, Operand, Pipeline, RankRows,
    RowOperation, Scalar, SortRows, child_pointer, compare, read_field, scalar_kind,
)

ARITHMETIC = {
    "add": operator.add,
    "subtract": operator.sub,
    "multiply": operator.mul,
    "divide": operator.truediv,
}


@dataclass(frozen=True)
class Row:
    fields: dict[str, JsonValue]
    sources: frozenset[int]


@dataclass(frozen=True)
class Table:
    rows: list[Row]
    fields: frozenset[str]

    def require(self, fields: set[str]) -> None:
        if missing := fields - self.fields:
            raise EvaluationError(f"Unknown pipeline fields: {sorted(missing)}")

    def require_new(self, field: str) -> None:
        if field in self.fields:
            raise EvaluationError(f"Pipeline output {field!r} overwrites an existing field")


def sources_of(rows: list[Row]) -> frozenset[int]:
    # Rank assigns a shared source set to every row in its population.
    return frozenset().union(*{row.sources for row in rows})


def key_values(values: list[Scalar], field: str) -> set[str]:
    kinds = {scalar_kind(value, field) for value in values}
    if len(kinds) > 1:
        raise EvaluationError(f"Mixed value types in pipeline field {field!r}")
    return kinds


def aggregate(rows: list[Row], spec: Aggregate) -> Scalar | None:
    if spec.function == "count":
        return len(rows)
    assert spec.field is not None  # Validated by group_rows.
    values = [read_field(row.fields, spec.field) for row in rows]
    kinds = key_values(values, spec.field)
    if spec.function == "count_distinct":
        return len(set(values))
    if spec.function in {"sum", "mean"} and kinds - {"numeric"}:
        raise EvaluationError(f"{spec.function} requires numeric values")
    if spec.function in {"min", "max"} and "boolean" in kinds:
        raise EvaluationError(f"{spec.function} requires ordered values")
    if not values:
        return None
    reducer = {"sum": sum, "mean": mean, "min": min, "max": max}[spec.function]
    try:
        result = reducer(values)
    except OverflowError as error:
        raise EvaluationError(f"{spec.function} overflowed on {spec.field!r}") from error
    scalar_kind(result, spec.output)
    return result


def group_rows(table: Table, step: GroupRows) -> Table:
    fields = [*step.by, *(spec.output for spec in step.aggregates)]
    if len(set(fields)) != len(fields):
        raise EvaluationError("Group keys and aggregate output names must be unique")
    table.require(set(step.by))
    for spec in step.aggregates:
        if (spec.function == "count") != (spec.field is None):
            raise EvaluationError("count uses no field; other aggregations require a field")
        if spec.field is not None:
            table.require({spec.field})

    groups = {} if step.by else {(): []}
    for row in table.rows:
        values = tuple(read_field(row.fields, name) for name in step.by)
        # Keep booleans separate from the corresponding numeric values.
        key = tuple((scalar_kind(value, name), value)
                    for name, value in zip(step.by, values, strict=True))
        groups.setdefault(key, []).append(row)

    grouped = []
    for key, members in groups.items():
        data = dict(zip(step.by, (value for _, value in key), strict=True))
        data.update({spec.output: aggregate(members, spec) for spec in step.aggregates})
        grouped.append(Row(data, sources_of(members)))
    return Table(grouped, frozenset(fields))


def require_operand(table: Table, operand: Operand) -> None:
    if isinstance(operand, FieldOperand):
        table.require({operand.name})


def operand_value(row: Row, operand: Operand) -> Scalar:
    if isinstance(operand, FieldOperand):
        return read_field(row.fields, operand.name)
    return operand.value


def derive_field(table: Table, step: DeriveField) -> Table:
    table.require_new(step.output)
    require_operand(table, step.left)
    require_operand(table, step.right)
    derived = []
    for row in table.rows:
        left = operand_value(row, step.left)
        right = operand_value(row, step.right)
        if {scalar_kind(left, step.output), scalar_kind(right, step.output)} != {"numeric"}:
            raise EvaluationError("Arithmetic requires numeric operands")
        try:
            value = ARITHMETIC[step.arithmetic](left, right)
        except ArithmeticError as error:
            raise EvaluationError(f"Cannot {step.arithmetic} into {step.output!r}: {error}") from error
        scalar_kind(value, step.output)
        derived.append(Row({**row.fields, step.output: value}, row.sources))
    return Table(derived, table.fields | {step.output})


def order_rows(table: Table, field: str, descending: bool) -> list[tuple[Scalar, Row]]:
    table.require({field})
    values = [read_field(row.fields, field) for row in table.rows]
    if "boolean" in key_values(values, field):
        raise EvaluationError(f"Cannot order boolean field {field!r}")
    return sorted(zip(values, table.rows, strict=True), key=lambda pair: pair[0],
                  reverse=descending)


def rank_rows(table: Table, step: RankRows) -> Table:
    table.require_new(step.output)
    population = sources_of(table.rows)
    ranked = []
    previous = None
    rank = 0
    for position, (value, row) in enumerate(order_rows(table, step.field, step.descending), 1):
        if value != previous:
            rank = rank + 1 if step.ties == "dense" else position
            previous = value
        ranked.append(Row({**row.fields, step.output: rank}, population))
    return Table(ranked, table.fields | {step.output})


def apply_operation(table: Table, step: RowOperation) -> Table:
    match step:
        case FilterRows():
            table.require({item.field for item in step.predicates})
            selected = [
                row for row in table.rows
                if all(compare(read_field(row.fields, item.field), item.op, item.value, item.field)
                       for item in step.predicates)
            ]
            return Table(selected, table.fields)
        case GroupRows():
            return group_rows(table, step)
        case DeriveField():
            return derive_field(table, step)
        case RankRows():
            return rank_rows(table, step)
        case SortRows():
            population = sources_of(table.rows)
            ordered = order_rows(table, step.field, step.descending)
            return Table([Row(row.fields, population) for _, row in ordered], table.fields)
        case LimitRows():
            return Table(table.rows[:step.count], table.fields)


def evaluate_pipeline(
    case: Case, assertion: Assertion, expression: Pipeline,
    rows: list[dict[str, JsonValue]], schema: list[Column],
) -> Finding | None:
    table = Table([Row(row, frozenset({index})) for index, row in enumerate(rows)],
                  frozenset(column.name for column in schema))
    for step in expression.steps:
        table = apply_operation(table, step)

    table.require({expression.field})
    require_operand(table, expression.target)
    if not table.rows:
        return None
    if len(table.rows) != 1:
        raise EvaluationError("Pipeline comparison requires exactly one output row")
    row = table.rows[0]
    if row.fields[expression.field] is None:
        # An empty population has no mean, minimum, or maximum.
        return None
    value = read_field(row.fields, expression.field)
    target = operand_value(row, expression.target)
    matches = compare(value, expression.compare, target, expression.field)
    if case.coverage == "complete":
        relation = "SUPPORTS" if matches else "CONTRADICTS"
        scope = "the complete query result"
    else:
        if not row.sources:
            return None
        relation = "CONTEXTUALIZES"
        scope = "the returned subset"
    return Finding(
        assertion_id=assertion.id, result_id=case.result.id, relation=relation,
        value=value, pointers=[
            case.rows_pointer,
            *(child_pointer(case.rows_pointer, index) for index in sorted(row.sources)),
        ],
        statement=f"{expression.field} is {value!r} in {scope} "
                  f"({expression.compare} {target!r}: {matches}).",
    )
