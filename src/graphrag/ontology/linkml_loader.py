"""Load-time LinkML adapter: resolved definitions, mappings and physical addresses."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

from linkml_runtime.dumpers import json_dumper
from linkml_runtime.linkml_model.annotations import Annotation
from linkml_runtime.linkml_model.meta import (
    ClassDefinition,
    Element,
    ElementName,
    SchemaDefinition,
    SlotDefinition,
)
from linkml_runtime.utils.schemaview import SchemaView
from pydantic import JsonValue

from graphrag.model.ontology import OntologyFileSource, OntologyLoadError
from graphrag.model.ontology_mapping import (
    DatabaseElement,
    OntologySchemaMapping,
    SchemaMappings,
)
from graphrag.resource_loader import ResourceLoader


def annotation(
    definition: Element,
    name: str,
) -> Any:
    # LinkML normalizes annotations to a tag-to-Annotation dictionary on load.
    annotations = cast(Mapping[str, Annotation], definition.annotations)
    keys = dict.fromkeys((name, name.replace("graph_", "neo4j_", 1)))
    values = [annotations[k].value for k in keys if k in annotations]
    if values and any(v != values[0] for v in values):
        raise ValueError(f"Conflicting graph binding annotations: {name}")
    return values[0] if values else None


def _elements(
    view: SchemaView,
) -> tuple[
    dict[tuple[str, str | None], ClassDefinition | SlotDefinition],
    dict[tuple[str, str | None], DatabaseElement],
]:
    definitions: dict[tuple[str, str | None], ClassDefinition | SlotDefinition] = {}
    elements: dict[tuple[str, str | None], DatabaseElement] = {}
    classes = cast(Mapping[str, ClassDefinition], view.all_classes())
    schema = view.schema
    assert schema is not None
    backend = annotation(schema, "database_backend") or (
        "neo4j"
        if any(annotation(c, "neo4j_label") is not None for c in classes.values())
        else "property_graph"
    )
    for name, cls in classes.items():
        label = annotation(cls, "graph_label")
        if label is None:
            continue
        definitions[(name, None)] = view.induced_class(name)
        for slot in view.class_induced_slots(name):
            prop, rel = annotation(slot, "graph_property"), annotation(
                slot, "graph_relationship"
            )
            if prop is not None and rel is not None:
                raise ValueError(f"Conflicting graph annotations: {name}.{slot.name}")
            if rel is not None:
                direction = annotation(slot, "graph_direction")
                source, target = annotation(slot, "graph_source_label"), annotation(
                    slot, "graph_target_label"
                )
                owner, endpoint = (
                    (source, target) if direction == "outgoing" else (target, source)
                )
                if (
                    direction not in {"incoming", "outgoing"}
                    or owner != label
                    or slot.range is None
                    or slot.range not in classes
                    or annotation(classes[slot.range], "graph_label") != endpoint
                ):
                    raise ValueError(
                        f"Conflicting graph endpoints/range: {name}.{slot.name}"
                    )
            if prop is not None or rel is not None:
                definitions[(name, slot.name)] = slot
    for (name, slot), definition in definitions.items():
        binding = {
            k: annotation(definition, "graph_" + k)
            for k in (
                "label",
                "property",
                "relationship",
                "direction",
                "source_label",
                "target_label",
            )
        }
        binding = {k: v for k, v in binding.items() if v is not None}
        if slot is not None:
            binding["owner_label"] = annotation(classes[name], "graph_label")
        elements[(name, slot)] = DatabaseElement(
            backend=backend,
            schema_class=name,
            schema_slot=slot,
            element_type=(
                "node"
                if slot is None
                else "relationship" if "relationship" in binding else "property"
            ),
            identifier=binding.get("label")
            or binding.get("relationship")
            or binding["property"],
            representation={
                "binding": binding,
                "schema": cast(dict[str, JsonValue], json_dumper.to_dict(definition)),
            },
            description=definition.description,
        )
    return definitions, elements


def load_linkml_mappings(
    schema_path: Path | str,
) -> SchemaMappings:
    """Parse LinkML once and return plain mapping data with prepared indexes."""

    schema_path = Path(schema_path)
    try:
        root = ResourceLoader().read(schema_path)
        view = SchemaView(
            root.content.decode(),
            base_dir=str(schema_path.expanduser().absolute().parent),
        )
        schema = view.schema
        assert schema is not None
        schema.source_file = root.source
        schemas = view.all_schema()  # LinkML resolves the import closure.
        # LinkML alone retrieves imports; record their source locations.
        sources = (
            OntologyFileSource(
                path=root.source,
                sha256=sha256(root.content).hexdigest(),
            ),
        ) + tuple(
            OntologyFileSource(
                path=s.source_file or str(s.id),
            )
            for s in schemas
            if s is not schema and s.id != "https://w3id.org/linkml/types"
        )
        definitions, elements = _elements(view)
        prefixes = dict(view.namespaces())
        mappings = []
        for key, definition in definitions.items():
            # A global mapping index conflates reused class-local attribute names.
            scoped_schema = SchemaDefinition(
                id=schema.id,
                name="mapping_lookup",
                prefixes=prefixes,
                default_prefix=schema.default_prefix,
                default_curi_maps=schema.default_curi_maps,
                classes=(
                    [deepcopy(definition)]
                    if isinstance(definition, ClassDefinition)
                    else None
                ),
                slots=(
                    [deepcopy(definition)]
                    if isinstance(definition, SlotDefinition)
                    else None
                ),
            )
            scoped = SchemaView(scoped_schema)
            for relation, uris in scoped.get_mappings(
                ElementName(definition.name), expand=True
            ).items():
                if relation == "native" or (
                    relation == "self"
                    and not (
                        getattr(definition, "class_uri", None)
                        or getattr(definition, "slot_uri", None)
                    )
                ):
                    continue  # Generated schema URIs do not assert an alignment.
                for uri in uris:
                    relation_choice = {
                        "self": "identity",
                        "undefined": "unspecified",
                    }.get(relation, relation)
                    mappings.append(
                        OntologySchemaMapping.model_validate(
                            {
                                "ontology_uri": uri,
                                "schema_elements": (elements[key],),
                                "relation": relation_choice,
                                "status": annotation(definition, "mapping_status")
                                or "asserted",
                                "provenance": annotation(
                                    definition, "mapping_provenance"
                                )
                                or f"{schema_path}:{key}:{relation}",
                                "note": annotation(definition, "mapping_note"),
                                "confidence": annotation(
                                    definition, "mapping_confidence"
                                ),
                            }
                        )
                    )
        reverse: defaultdict[tuple[str, str | None, str | None], list[int]] = (
            defaultdict(list)
        )
        for index, mapping in enumerate(mappings):
            for element in mapping.schema_elements:
                binding = cast(dict[str, str], element.representation["binding"])
                if element.element_type == "node":
                    database_key = (element.identifier, None, None)
                elif element.element_type == "property":
                    database_key = (binding["owner_label"], element.identifier, None)
                else:
                    owner = (
                        binding["source_label"]
                        if binding["direction"] == "outgoing"
                        else binding["target_label"]
                    )
                    database_key = (owner, None, element.identifier)
                if index not in reverse[database_key]:
                    reverse[database_key].append(index)
        return SchemaMappings(
            mappings=tuple(mappings),
            sources=sources,
            database_index={key: tuple(indices) for key, indices in reverse.items()},
        )
    except Exception as exc:
        raise OntologyLoadError(
            f"Cannot load LinkML mappings from {schema_path}: {exc}"
        ) from exc
