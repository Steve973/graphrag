"""Serializable ontology access results for workflows and tool adapters."""

from typing import Literal

from pydantic import Field, JsonValue

from graphrag.model.base import ContractModel, NonEmptyStr

OntologyQueryType = Literal["SELECT", "ASK", "CONSTRUCT", "DESCRIBE"]
OntologyDirection = Literal["outgoing", "incoming", "both"]


class OntologyFileSource(ContractModel):
    """Identify one file included in the loaded ontology snapshot."""

    path: NonEmptyStr
    sha256: NonEmptyStr


class OntologySource(OntologyFileSource):
    """Identify the root file, parser library and explicitly loaded imports."""

    library: NonEmptyStr
    library_version: NonEmptyStr
    imported_files: tuple[OntologyFileSource, ...] = ()
    warnings: tuple[str, ...] = ()


class OntologyEntity(ContractModel):
    """Source metadata for a named entity, including properties and individuals.

    Related entities may be references without declarations or annotations.
    Types are original rdf:type values, including individual classifications.
    Aliases flatten configured annotation scopes; they do not imply OWL equivalence.
    """

    identifier: NonEmptyStr
    label: str | None = None
    definition: str | None = None
    aliases: tuple[str, ...] = ()
    types: tuple[str, ...] = ()
    truncated_fields: tuple[str, ...] = ()


class OntologySearchResult(ContractModel):
    """Deterministic literal matches, with total count before limiting."""

    query: NonEmptyStr
    entities: tuple[OntologyEntity, ...] = ()
    total_matches: int = Field(ge=0)
    truncated: bool = False


class OntologyResolution(ContractModel):
    """Resolve an identifier, IRI, exact label, or exact alias without guessing."""

    query: NonEmptyStr
    status: Literal["resolved", "ambiguous", "not_found"]
    candidates: tuple[OntologyEntity, ...] = ()
    total_matches: int = Field(ge=0)
    truncated: bool = False


class OntologyRelationship(ContractModel):
    """An original RDF triple, preserving anonymous nodes and literal types.

    Identifiers are full IRIs or snapshot-local ``_:`` blank-node IDs. Literal
    objects keep their lexical text (including whitespace and empty strings).
    """

    subject: NonEmptyStr
    predicate: NonEmptyStr
    object: str
    subject_kind: Literal["iri", "blank_node"] = "iri"
    object_kind: Literal["iri", "blank_node", "literal"] = "iri"
    datatype: str | None = None
    language: str | None = None


class OntologyContextLimits(ContractModel):
    """Bound output size; these limits are not a tokenizer or a query timeout."""

    max_depth: int = Field(default=2, ge=0, le=8)
    max_entities: int = Field(default=30, ge=1, le=200)
    max_relationships: int = Field(default=60, ge=0, le=1000)
    max_candidates: int = Field(default=5, ge=1, le=20)
    max_definition_chars: int = Field(default=1200, ge=0, le=10000)
    max_label_chars: int = Field(default=200, ge=1, le=2000)
    max_literal_chars: int = Field(default=1200, ge=0, le=10000)
    max_aliases: int = Field(default=10, ge=0, le=100)


class OntologyNeighborhood(ContractModel):
    """A bounded traversal preserving original edge direction and seed order."""

    seed_ids: tuple[str, ...]
    direction: OntologyDirection
    predicates: tuple[str, ...] | None = None
    entities: tuple[OntologyEntity, ...]
    relationships: tuple[OntologyRelationship, ...]
    truncation_reasons: tuple[str, ...] = ()


class OntologyContext(ContractModel):
    """Prompt-ready context for terms observed in retrieved data.

    Unresolved and ambiguous terms remain explicit. Only uniquely resolved
    terms seed traversal. No inferred triples or data-model mappings are added.
    """

    source: OntologySource
    resolutions: tuple[OntologyResolution, ...]
    neighborhood: OntologyNeighborhood
    limits: OntologyContextLimits
    warnings: tuple[str, ...] = ()


class OntologySparqlResult(ContractModel):
    """Native SPARQL JSON for SELECT/ASK, or Turtle for graph query results.

    Graph results may be incomplete when truncated. Bounds limit returned
    rows/triples, not query cost or the length of individual literal values.
    """

    source: OntologySource
    query_type: OntologyQueryType
    data: dict[str, JsonValue] | str
    truncated: bool = False


class OntologyError(RuntimeError):
    """Base domain error for ontology access at a workflow/tool boundary."""


class OntologyLoadError(OntologyError):
    """The configured file could not be loaded into a usable snapshot."""


class OntologyQueryError(OntologyError):
    """An ontology operation failed; the underlying exception is retained."""


class OntologyUnsupportedError(OntologyQueryError):
    """The requested syntax or operation is not supported by this service."""


class OntologyNotFoundError(OntologyError):
    """No named entity matches the requested identifier or exact term."""


class OntologyAmbiguityError(OntologyError):
    """An exact label or alias denotes multiple entities.

    ``resolution`` carries serializable candidate information for a workflow or
    an eventual tool adapter to return to the caller.
    """

    def __init__(self, resolution: OntologyResolution) -> None:
        self.resolution = resolution
        super().__init__(
            f"{resolution.query!r} matches {resolution.total_matches} ontology entities"
        )
