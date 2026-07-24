from typing import Literal

from pydantic import TypeAdapter

from graph_rag.model.base import ContractModel, NonEmptyStr


class Neo4jMcpSchemaRelationship(ContractModel):
    direction: Literal["out", "in"]
    labels: list[NonEmptyStr]
    properties: dict[str, NonEmptyStr] = {}


class Neo4jMcpSchemaValue(ContractModel):
    type: Literal["node", "relationship"]
    properties: dict[str, NonEmptyStr] = {}
    relationships: dict[str, Neo4jMcpSchemaRelationship] = {}


class Neo4jMcpSchemaItem(ContractModel):
    key: NonEmptyStr
    value: Neo4jMcpSchemaValue


class GraphSchemaContext(ContractModel):
    source_result_ids: list[NonEmptyStr]
    source_format: Literal["official_neo4j_mcp_get_schema"]
    compact_format: Literal["neo4j_schema_ddl_v1"]
    schema_items: list[Neo4jMcpSchemaItem]
    schema_ddl: NonEmptyStr


SchemaItems = TypeAdapter(list[Neo4jMcpSchemaItem])


def parse_neo4j_mcp_schema(raw_json_text: str) -> list[Neo4jMcpSchemaItem]:
    return SchemaItems.validate_json(raw_json_text)


def render_schema_ddl(schema_items: list[Neo4jMcpSchemaItem]) -> str:
    lines: list[str] = []

    for item in sorted(schema_items, key=lambda item: item.key):
        if item.value.type != "node":
            continue

        props = render_properties(item.value.properties)
        lines.append(
            f"NODE {item.key} {props}" if props else f"NODE {item.key}"
        )

    for item in sorted(schema_items, key=lambda item: item.key):
        if item.value.type != "node":
            continue

        for rel_type, rel in sorted(item.value.relationships.items()):
            rel_props = render_properties(rel.properties)

            for label in sorted(rel.labels):
                if rel.direction == "out":
                    line = render_relationship_ddl(
                        rel_type=rel_type,
                        from_label=item.key,
                        to_label=label,
                        properties=rel_props,
                    )
                else:
                    line = render_relationship_ddl(
                        rel_type=rel_type,
                        from_label=label,
                        to_label=item.key,
                        properties=rel_props,
                    )

                lines.append(line)

    return "\n".join(lines)


def render_relationship_ddl(
    rel_type: str,
    from_label: str,
    to_label: str,
    properties: str,
) -> str:
    base = f"REL {rel_type} FROM {from_label} TO {to_label}"
    return (
        f"{base} {properties}"
        if properties
        else base
    )


def render_properties(properties: dict[str, str]) -> str:
    if not properties:
        return ""

    rendered = ", ".join(
        f"{name}: {property_type}"
        for name, property_type in sorted(properties.items())
    )
    return f"({rendered})"


def build_graph_schema_context(
    source_result_ids: list[NonEmptyStr],
    raw_json_text: str,
) -> GraphSchemaContext:
    schema_items = parse_neo4j_mcp_schema(raw_json_text)
    return GraphSchemaContext(
        source_result_ids=source_result_ids,
        source_format="official_neo4j_mcp_get_schema",
        compact_format="neo4j_schema_ddl_v1",
        schema_items=schema_items,
        schema_ddl=render_schema_ddl(schema_items),
    )
