from graph_rag.graph_store.neo4j.neo4j_gds import (
    GdsProcedureToolDescriptor,
    gds_signature_to_input_schema,
)


def test_discovery_signature_becomes_callable_json_schema() -> None:
    procedure = GdsProcedureToolDescriptor.model_validate(
        {
            "name": "gds.pageRank.stream",
            "description": "Run PageRank.",
            "signature": (
                "gds.pageRank.stream(graphName :: STRING, "
                "configuration = {} :: MAP) :: "
                "(nodeId :: INTEGER, score :: FLOAT)"
            ),
            "type": "procedure",
        }
    )

    assert procedure.source_signature.startswith("gds.pageRank.stream(")
    assert procedure.input_schema == {
        "type": "object",
        "properties": {
            "graphName": {"type": "string"},
            "configuration": {
                "type": "object",
                "additionalProperties": True,
                "default": {},
            },
        },
        "required": ["graphName"],
        "additionalProperties": False,
    }


def test_converts_lists_scalars_defaults_and_unknown_types() -> None:
    schema = gds_signature_to_input_schema(
        "gds.example(values :: LIST<INTEGER>, enabled = true :: BOOLEAN, "
        "ratio = 0.5 :: FLOAT, context :: CUSTOM) :: (value :: ANY)"
    )

    assert schema["properties"] == {
        "values": {"type": "array", "items": {"type": "integer"}},
        "enabled": {"type": "boolean", "default": True},
        "ratio": {"type": "number", "default": 0.5},
        "context": {"description": "Neo4j value of type CUSTOM"},
    }
    assert schema["required"] == ["values", "context"]


def test_unparseable_default_remains_optional_without_invented_default() -> None:
    schema = gds_signature_to_input_schema(
        "gds.example(config = {foo: 'bar'} :: MAP) :: (value :: ANY)"
    )

    assert schema["properties"]["config"] == {
        "type": "object",
        "additionalProperties": True,
    }
    assert schema["required"] == []
