from typing import Literal

from pydantic import TypeAdapter

from graph_rag.model.base import NonEmptyStr, ContractModel


class Neo4jMcpGdsProcedure(ContractModel):
    name: NonEmptyStr
    description: str = ""
    signature: NonEmptyStr
    type: Literal["procedure"]


class GdsProcedureCatalogContext(ContractModel):
    source_result_ids: list[NonEmptyStr]
    source_format: Literal["official_neo4j_mcp_list_gds_procedures"]
    compact_format: Literal["gds_procedure_catalog_v1"]
    procedures: list[Neo4jMcpGdsProcedure]
    catalog_text: NonEmptyStr


GdsProcedures = TypeAdapter(list[Neo4jMcpGdsProcedure])


def parse_neo4j_mcp_gds_procedures(
        raw_json_text: str,
) -> list[Neo4jMcpGdsProcedure]:
    return GdsProcedures.validate_json(raw_json_text)


def render_gds_procedure_catalog(
        procedures: list[Neo4jMcpGdsProcedure],
) -> str:
    lines: list[str] = []

    for procedure in sorted(procedures, key=lambda item: item.name):
        signature = render_gds_signature(procedure.signature)
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


def build_gds_procedure_catalog_context(
        source_result_ids: list[NonEmptyStr],
        raw_json_text: str,
) -> GdsProcedureCatalogContext:
    procedures = parse_neo4j_mcp_gds_procedures(raw_json_text)
    return GdsProcedureCatalogContext(
        source_result_ids=source_result_ids,
        source_format="official_neo4j_mcp_list_gds_procedures",
        compact_format="gds_procedure_catalog_v1",
        procedures=procedures,
        catalog_text=render_gds_procedure_catalog(procedures),
    )
