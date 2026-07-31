import json
from typing import Any, Literal

from pydantic import AliasChoices, Field, JsonValue, TypeAdapter, model_validator

from graph_rag.model.base import NonEmptyStr, ContractModel


class GdsProcedureToolDescriptor(ContractModel):
    """Represent one discovered GDS procedure and its callable input schema.

    Attributes:
        name: Exact discovered procedure name.
        description: Procedure description returned by Neo4j MCP.
        source_signature: Original Neo4j signature retained for forensics.
        input_schema: JSON Schema derived from the signature arguments.
        type: Discovery-result discriminator.
    """

    name: NonEmptyStr
    description: str = ""
    source_signature: NonEmptyStr = Field(
        validation_alias=AliasChoices("source_signature", "signature"),
    )
    input_schema: dict[str, JsonValue] = Field(default_factory=dict)
    type: Literal["procedure"]

    @model_validator(mode="before")
    @classmethod
    def derive_input_schema(cls, value: Any) -> Any:
        """Derive callable JSON Schema while retaining the source signature."""

        if not isinstance(value, dict):
            return value
        data = dict(value)
        signature: str = data.get("source_signature", data.get("signature")) or ""
        if signature and not data.get("input_schema"):
            data["input_schema"] = gds_signature_to_input_schema(signature)
        return data


class GdsProcedureCatalog(ContractModel):
    source_result_ids: list[NonEmptyStr]
    source_format: Literal["official_neo4j_mcp_list_gds_procedures"]
    compact_format: Literal["gds_procedure_catalog_v1"]
    procedures: list[GdsProcedureToolDescriptor]
    catalog_text: NonEmptyStr


GdsProcedures = TypeAdapter(list[GdsProcedureToolDescriptor])


def parse_neo4j_mcp_gds_procedures(
        raw_json_text: str,
) -> list[GdsProcedureToolDescriptor]:
    return GdsProcedures.validate_json(raw_json_text)


def render_gds_procedure_catalog(
        procedures: list[GdsProcedureToolDescriptor],
) -> str:
    lines: list[str] = []

    for procedure in sorted(procedures, key=lambda item: item.name):
        signature = render_gds_signature(procedure.source_signature)
        line = f"PROC {signature}"
        if procedure.description:
            line = f"{line} -- {procedure.description}"
        lines.append(line)

    return "\n".join(lines)


def render_gds_signature(signature: str) -> str:
    name, argument_text, yield_text = split_gds_signature(signature)
    arguments = render_signature_fields(argument_text)
    yields = render_signature_fields(yield_text)
    return f"{name}({arguments}) YIELD {yields}"


def split_gds_signature(signature: str) -> tuple[str, str, str]:
    name, remainder = signature.split("(", 1)
    argument_text, remainder = remainder.split(") :: (", 1)
    yield_text = remainder.removesuffix(")")
    return name, argument_text, yield_text


def render_signature_fields(signature_fields: str) -> str:
    if not signature_fields.strip():
        return ""

    rendered_fields = [
        render_signature_field(field)
        for field in split_top_level_fields(signature_fields)
    ]
    return ", ".join(rendered_fields)


def render_signature_field(field: str) -> str:
    name_and_default, type_name = field.split(" :: ", 1)
    name_and_default = name_and_default.strip()
    type_name = type_name.strip()

    if " = " not in name_and_default:
        return f"{name_and_default}: {type_name}"

    name, default_value = name_and_default.split(" = ", 1)
    return f"{name}: {type_name} = {default_value}"


def gds_signature_to_input_schema(signature: str) -> dict[str, JsonValue]:
    """Convert Neo4j procedure arguments into a callable JSON Schema.

    Args:
        signature: Original Neo4j procedure signature.

    Returns:
        Object JSON Schema whose required fields and defaults reflect the
        procedure arguments.
    """

    _, argument_text, _ = split_gds_signature(signature)
    properties: dict[str, JsonValue] = {}
    required: list[str] = []

    for field in split_top_level_fields(argument_text):
        name_and_default, type_name = field.split(" :: ", 1)
        name_and_default = name_and_default.strip()
        schema = neo4j_type_to_json_schema(type_name.strip())

        if " = " in name_and_default:
            name, default_text = name_and_default.split(" = ", 1)
            default = parse_neo4j_default(default_text.strip())
            schema["default"] = default
        else:
            name = name_and_default
            required.append(name)

        properties[name] = schema

    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


def neo4j_type_to_json_schema(type_name: str) -> dict[str, JsonValue]:
    """Translate one Neo4j signature type into JSON Schema."""

    normalized = type_name.strip().upper()
    scalar_types = {
        "STRING": "string",
        "BOOLEAN": "boolean",
        "INTEGER": "integer",
        "FLOAT": "number",
        "NUMBER": "number",
        "MAP": "object",
    }
    if normalized in scalar_types:
        schema: dict[str, JsonValue] = {"type": scalar_types[normalized]}
        if normalized == "MAP":
            schema["additionalProperties"] = True
        return schema

    if normalized.startswith("LIST<") and normalized.endswith(">"):
        return {
            "type": "array",
            "items": neo4j_type_to_json_schema(normalized[5:-1]),
        }

    return {
        "description": f"Neo4j value of type {type_name.strip()}",
    }


def parse_neo4j_default(value: str) -> JsonValue:
    """Parse a JSON-compatible Neo4j default without inventing a value."""

    normalized = {"TRUE": "true", "FALSE": "false", "NULL": "null"}.get(
        value.upper(),
        value,
    )
    try:
        return json.loads(normalized.replace("'", '"'))
    except json.JSONDecodeError:
        raise ValueError(f"Failed to parse Neo4j default value: {value}")


def split_top_level_fields(fields: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    depth = 0

    for character in fields:
        if character in "([{":
            depth += 1
        elif character in ")]}":
            depth -= 1
        elif character == "," and depth == 0:
            parts.append("".join(current).strip())
            current = []
            continue

        current.append(character)

    if current:
        parts.append("".join(current).strip())

    return parts


def build_gds_procedure_catalog(
        source_result_ids: list[NonEmptyStr],
        raw_json_text: str,
) -> GdsProcedureCatalog:
    procedures = parse_neo4j_mcp_gds_procedures(raw_json_text)
    return GdsProcedureCatalog(
        source_result_ids=source_result_ids,
        source_format="official_neo4j_mcp_list_gds_procedures",
        compact_format="gds_procedure_catalog_v1",
        procedures=procedures,
        catalog_text=render_gds_procedure_catalog(procedures),
    )
