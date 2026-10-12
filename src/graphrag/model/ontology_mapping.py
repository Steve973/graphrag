"""LLM-facing ontology meaning and database representation contracts."""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Literal

from pydantic import Field, JsonValue

from graphrag.model.base import ContractModel, NonEmptyStr
from graphrag.model.ontology import OntologyContext, OntologyFileSource


class DatabaseElement(ContractModel):
    """A database binding with its backend-native schema representation.

    Examples include LinkML classes/slots, relational tables, or RDF predicates.
    The backend adapter defines the locator/representation, without forcing node
    labels or Cypher concepts into the common semantic mapping contract.
    """

    kind: Literal["database_element"] = "database_element"
    backend: NonEmptyStr
    schema_class: NonEmptyStr
    schema_slot: NonEmptyStr | None = None
    element_type: NonEmptyStr
    identifier: NonEmptyStr
    representation: dict[str, JsonValue] = Field(default_factory=dict)
    description: str | None = None


class OntologySchemaMapping(ContractModel):
    """An explicit correspondence, never inferred from matching names.

    Multiple elements may express a compound representation. Their presence
    alone does not define an executable traversal or imply equivalence.
    """

    ontology_uri: NonEmptyStr
    schema_elements: tuple[DatabaseElement, ...] = Field(min_length=1)
    relation: Literal[
        "identity", "exact", "close", "related", "broad", "narrow", "unspecified"
    ] = "related"
    status: Literal["proposed", "asserted", "verified"] = "proposed"
    confidence: float | None = Field(default=None, ge=0, le=1)
    provenance: NonEmptyStr
    note: str | None = None


class OntologyDatabaseContext(ContractModel):
    """Semantic context paired with database representations and uncertainty."""

    ontology: OntologyContext
    mappings: tuple[OntologySchemaMapping, ...] = ()
    schema_sources: tuple[OntologyFileSource, ...] = ()
    unmapped_ontology_uris: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass
class SchemaMappings:
    """Loaded mapping data, independent of the schema parser or ontology backend.

    Database index keys contain an entity name, optional property name and
    optional relationship type. Adapters supply these physical addresses;
    the ontology service never interprets backend-specific binding annotations.
    Index values reference mapping positions, preserving source order and
    allowing one concept or physical element to have multiple mappings.
    """

    mappings: tuple[OntologySchemaMapping, ...] = ()
    sources: tuple[OntologyFileSource, ...] = ()
    database_index: dict[tuple[str, str | None, str | None], tuple[int, ...]] = field(
        default_factory=dict
    )
    ontology_index: dict[str, tuple[int, ...]] = field(init=False)

    def __post_init__(self) -> None:
        by_uri = defaultdict(list)
        for index, mapping in enumerate(self.mappings):
            by_uri[mapping.ontology_uri].append(index)
        self.ontology_index = {uri: tuple(indices) for uri, indices in by_uri.items()}
        if any(
            index < 0 or index >= len(self.mappings)
            for indices in self.database_index.values()
            for index in indices
        ):
            raise ValueError("Database mapping index refers to an unknown mapping")
