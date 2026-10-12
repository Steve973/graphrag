"""Provider-based ontology queries and database-independent schema grounding."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from functools import cached_property
from typing import TYPE_CHECKING, Annotated, Any

from langchain_core.tools import StructuredTool, ToolException
from pydantic import Field

from graphrag.config.ontology_config import OntologyReaderSettings, OntologySettings
from graphrag.model.base import ContractModel, NonEmptyStr
from graphrag.model.ontology import (
    OntologyContext,
    OntologyContextLimits,
    OntologyDirection,
    OntologyEntity,
    OntologyError,
    OntologyLoadError,
    OntologyNeighborhood,
    OntologyResolution,
    OntologySearchResult,
    OntologySource,
    OntologySparqlResult,
)
from graphrag.model.ontology_mapping import (
    OntologyDatabaseContext,
    OntologySchemaMapping,
    SchemaMappings,
)
from graphrag.ontology.base_providers import OntologyProvider
from graphrag.ontology.rdflib_provider import RDFLibOntologyProvider
from graphrag.ontology.resources import OntologyResources

if TYPE_CHECKING:
    from graphrag.config.graph_rag_config import GraphDataProfile

class OntologyService:
    """Combine ontology queries with mappings indexed during initialization.

    Remote implementations can instead be injected with provider= and paired
    with plain SchemaMappings data. Call initialize() during startup to load
    profile resources once.
    """

    def __init__(
        self,
        settings: OntologySettings | None = None,
        *,
        provider: OntologyProvider | None = None,
        schema_mappings: SchemaMappings | None = None,
    ) -> None:
        if (settings is None) == (provider is None):
            raise ValueError("Supply exactly one of settings or provider")
        if provider is not None and not isinstance(provider, OntologyProvider):
            raise TypeError("provider must extend OntologyProvider")
        if schema_mappings is not None and not isinstance(
            schema_mappings, SchemaMappings
        ):
            raise TypeError("schema_mappings must be SchemaMappings data")
        self._schema_path = None
        if settings is not None:
            reader_settings = OntologyReaderSettings.model_validate(
                {
                    name: getattr(settings, name)
                    for name in OntologyReaderSettings.model_fields
                }
            )
            provider = RDFLibOntologyProvider(
                OntologyResources(
                    str(settings.path),
                    format=settings.format,
                    imports={iri: str(path) for iri, path in settings.imports.items()},
                ),
                reader_settings,
            )
            if settings.schema_path is not None:
                if schema_mappings is not None:
                    raise ValueError("Supply schema_path or schema_mappings, not both")
                self._schema_path = settings.schema_path
        assert provider is not None
        self.provider = provider
        self._supplied_mappings = schema_mappings

    @cached_property
    def _mapping_data(self) -> SchemaMappings | None:
        if self._schema_path is not None:
            from graphrag.ontology.linkml_loader import load_linkml_mappings

            return load_linkml_mappings(self._schema_path)
        return self._supplied_mappings

    @classmethod
    def from_profile(
        cls,
        profile: GraphDataProfile,
    ) -> OntologyService:
        if profile.ontology is None:
            raise OntologyLoadError(
                f"Profile {profile.id!r} has no ontology configured"
            )
        return cls(profile.ontology)

    def initialize(self) -> OntologySource:
        source = self.provider.initialize()
        _ = self._mapping_data
        return source

    def get_entity(
        self,
        identifier: str,
    ) -> OntologyEntity:
        return self.provider.get_entity(identifier)

    def search(
        self,
        query: str,
        *,
        limit: int = 20,
        exact: bool = False,
    ) -> OntologySearchResult:
        return self.provider.search(query, limit=limit, exact=exact)

    def resolve(
        self,
        term: str,
        *,
        limit: int = 10,
    ) -> OntologyResolution:
        return self.provider.resolve(term, limit=limit)

    def neighborhood(
        self,
        identifiers: Sequence[str],
        *,
        direction: OntologyDirection = "both",
        predicates: Sequence[str] | None = None,
        limits: OntologyContextLimits | None = None,
    ) -> OntologyNeighborhood:
        limits = limits or OntologyContextLimits()
        neighborhood = self.provider.neighborhood(
            identifiers, direction=direction, predicates=predicates, limits=limits
        )
        entities = tuple(
            self._bounded(entity, limits) for entity in neighborhood.entities
        )
        reasons = set(neighborhood.truncation_reasons)
        if any(entity.truncated_fields for entity in entities):
            reasons.add("metadata")
        relationships = []
        for relationship in neighborhood.relationships:
            if (
                relationship.object_kind == "literal"
                and len(relationship.object) > limits.max_literal_chars
            ):
                relationship = relationship.model_copy(
                    update={"object": relationship.object[: limits.max_literal_chars]}
                )
                reasons.add("literal_values")
            relationships.append(relationship)
        return neighborhood.model_copy(
            update={
                "entities": entities,
                "relationships": tuple(relationships),
                "truncation_reasons": tuple(sorted(reasons)),
            }
        )

    @staticmethod
    def _bounded(
        entity: OntologyEntity,
        limits: OntologyContextLimits,
    ) -> OntologyEntity:
        truncated: list[str] = list(entity.truncated_fields)
        label = entity.label
        definition = entity.definition
        if label is not None and len(label) > limits.max_label_chars:
            label = label[: limits.max_label_chars]
            truncated.append("label")
        if definition is not None and len(definition) > limits.max_definition_chars:
            definition = definition[: limits.max_definition_chars]
            truncated.append("definition")
        aliases = entity.aliases[: limits.max_aliases]
        if len(entity.aliases) > len(aliases) or any(
            len(alias) > limits.max_label_chars for alias in aliases
        ):
            truncated.append("aliases")
        return entity.model_copy(
            update={
                "label": label,
                "definition": definition,
                "aliases": tuple(alias[: limits.max_label_chars] for alias in aliases),
                "truncated_fields": tuple(truncated),
            }
        )

    @staticmethod
    def _terms(terms: Sequence[str]) -> tuple[str, ...]:
        if isinstance(terms, str):
            raise ValueError("Supply a sequence of ontology terms, not a string")
        if len(terms) > 20:
            raise ValueError("At most 20 ontology terms may be requested")
        if any(not isinstance(term, str) or not term.strip() for term in terms):
            raise ValueError("Ontology query must be a nonempty string")
        return tuple(dict.fromkeys(term.strip() for term in terms))

    def get_context(
        self,
        terms: Sequence[str],
        *,
        direction: OntologyDirection = "outgoing",
        predicates: Sequence[str] | None = None,
        limits: OntologyContextLimits | None = None,
    ) -> OntologyContext:
        """Resolve up to 20 data terms and return bounded context for unique matches.

        Serialize with ``model_dump(mode='json')``.
        Unknown/ambiguous terms are reported rather than silently grounded. The
        caller chooses terms from retrieved data; raw graph labels are not
        automatically assumed to be ontology identifiers or OWL classes.
        """

        terms = self._terms(terms)
        limits = limits or OntologyContextLimits()
        source = self.initialize()
        resolutions = tuple(
            self.resolve(term, limit=limits.max_candidates) for term in terms
        )
        seeds = [
            result.candidates[0].identifier
            for result in resolutions
            if result.status == "resolved"
        ]
        context_neighborhood = self.neighborhood(
            seeds, direction=direction, predicates=predicates, limits=limits
        )
        resolutions = tuple(
            result.model_copy(
                update={
                    "candidates": tuple(
                        self._bounded(candidate, limits)
                        for candidate in result.candidates
                    ),
                }
            )
            for result in resolutions
        )
        warnings = set(source.warnings) | {
            f"{result.status}: {result.query}"
            for result in resolutions
            if result.status != "resolved"
        }
        if any(result.truncated for result in resolutions):
            warnings.add("resolution candidates truncated")
        context_entities = (
            *context_neighborhood.entities,
            *(
                resolved_entity
                for result in resolutions
                for resolved_entity in result.candidates
            ),
        )
        for entity in context_entities:
            if entity.truncated_fields:
                warnings.add("entity metadata truncated")
        return OntologyContext(
            source=source,
            resolutions=resolutions,
            neighborhood=context_neighborhood,
            limits=limits,
            warnings=tuple(sorted(warnings)),
        )

    def query_sparql(
        self,
        query: str,
        *,
        limit: int = 50,
    ) -> OntologySparqlResult:
        return self.provider.query_sparql(query, limit=limit)

    def describe(
        self,
        terms: Sequence[str],
        *,
        direction: OntologyDirection = "both",
        predicates: Sequence[str] | None = None,
        limits: OntologyContextLimits | None = None,
    ) -> OntologyDatabaseContext:
        """Explain terms and their graph representation using loaded associations.

        Ambiguous/missing terms stay explicit and do not seed mapping lookup.
        Only resolved concepts and their ontology neighborhood supply mappings.
        """
        context = self.get_context(
            terms, direction=direction, predicates=predicates, limits=limits
        )
        identifiers = tuple(
            dict.fromkeys(
                (
                    *(
                        resolution.candidates[0].identifier
                        for resolution in context.resolutions
                        if resolution.status == "resolved"
                    ),
                    *(entity.identifier for entity in context.neighborhood.entities),
                )
            )
        )
        return self._with_mappings(context, identifiers)

    def _with_mappings(
        self,
        context: OntologyContext,
        identifiers: Sequence[str],
        *,
        mappings: tuple[OntologySchemaMapping, ...] | None = None,
    ) -> OntologyDatabaseContext:
        data = self._mapping_data
        if mappings is None:
            indices = sorted(
                {
                    index
                    for uri in identifiers
                    for index in (
                        data.ontology_index.get(uri, ()) if data is not None else ()
                    )
                }
            )
            mappings = (
                tuple(data.mappings[index].model_copy(deep=True) for index in indices)
                if data is not None
                else ()
            )
        sources = data.sources if data is not None else ()
        mapped = {entry.ontology_uri for entry in mappings}
        warnings = list(context.warnings)
        if data is None:
            warnings.append("No database schema mappings configured")
        if any(entry.status != "verified" for entry in mappings):
            warnings.append(
                "Some schema mappings are proposed or asserted; they have not been verified"
            )
        return OntologyDatabaseContext(
            ontology=context,
            mappings=mappings,
            schema_sources=sources,
            unmapped_ontology_uris=tuple(
                uri for uri in identifiers if uri not in mapped
            ),
            warnings=tuple(warnings),
        )

    def resolve_database_element(
        self,
        element_name: str,
        *,
        property_name: str | None = None,
        relationship_type: str | None = None,
        limits: OntologyContextLimits | None = None,
    ) -> OntologyDatabaseContext:
        """Find ontology meaning for an explicitly mapped database entity, field or relationship."""
        if not element_name.strip() or (
            property_name is not None and relationship_type is not None
        ):
            raise ValueError(
                "Provide a nonempty entity name and at most one property or relationship filter"
            )
        data = self._mapping_data
        indices = (
            data.database_index.get(
                (element_name, property_name, relationship_type), ()
            )
            if data is not None
            else ()
        )
        mappings = (
            tuple(data.mappings[index].model_copy(deep=True) for index in indices)
            if data is not None
            else ()
        )
        uris = tuple(dict.fromkeys(mapping.ontology_uri for mapping in mappings))
        if len(uris) > 20:
            raise ValueError(
                "More than 20 ontology concepts match; narrow the graph element filter"
            )
        context = self.get_context(uris, direction="both", limits=limits)
        result = self._with_mappings(context, uris, mappings=mappings)
        if not mappings:
            result = result.model_copy(
                update={
                    "warnings": (
                        *result.warnings,
                        "No explicit mapping for the requested graph element",
                    )
                }
            )
        return result


def create_ontology_tools(
    service: OntologyService,
    *,
    include_sparql: bool = False,
) -> list[StructuredTool]:
    """Create LangChain tools bound to the initialized ontology service.

    Pass the returned tools to a plain or research agent's tool collection.
    Resource changes require an application restart. LangChain provides
    ``invoke`` and ``ainvoke`` for these synchronous handlers, running async
    calls in an executor thread.
    """

    def serialize_result(operation: Callable[[], ContractModel]) -> dict[str, Any]:
        try:
            return operation().model_dump(mode="json")
        except (OntologyError, ValueError) as exc:
            raise ToolException(f"{type(exc).__name__}: {exc}") from exc

    def ontology_search(
        query: Annotated[
            NonEmptyStr, Field(description="A name, alias, IRI or bound CURIE to find.")
        ],
        limit: Annotated[
            int, Field(ge=1, le=200, description="Maximum matching entities to return.")
        ] = 10,
        exact: Annotated[
            bool, Field(description="Require an exact match instead of a substring.")
        ] = False,
    ) -> dict[str, Any]:
        return serialize_result(lambda: service.search(query, limit=limit, exact=exact))

    def ontology_context(
        terms: Annotated[
            list[NonEmptyStr],
            Field(
                min_length=1,
                max_length=20,
                description="Concept names or identifiers found with ontology_search.",
            ),
        ],
        direction: Annotated[
            OntologyDirection,
            Field(description="Follow statements from the concepts, toward them, or both."),
        ] = "both",
        predicates: Annotated[
            list[NonEmptyStr] | None,
            Field(max_length=20, description="Optional predicate IRIs or CURIEs to follow; null follows all."),
        ] = None,
        max_depth: Annotated[
            int, Field(ge=0, le=8, description="Relationship hops; zero returns only the selected concepts and mappings."),
        ] = 2,
        max_entities: Annotated[
            int, Field(ge=1, le=200, description="Maximum resources, including anonymous ontology expressions."),
        ] = 30,
        max_relationships: Annotated[
            int, Field(ge=0, le=1000, description="Maximum original ontology statements to return."),
        ] = 60,
    ) -> dict[str, Any]:
        return serialize_result(
            lambda: service.describe(
                terms,
                direction=direction,
                predicates=predicates,
                limits=OntologyContextLimits(
                    max_depth=max_depth,
                    max_entities=max_entities,
                    max_relationships=max_relationships,
                ),
            )
        )

    def ontology_relationships(
        term: Annotated[
            NonEmptyStr, Field(description="Concept name or identifier; prefer an identifier when ambiguous."),
        ],
        direction: Annotated[
            OntologyDirection,
            Field(description="Outgoing statements start at the concept; incoming statements point to it."),
        ] = "both",
        predicates: Annotated[
            list[NonEmptyStr] | None,
            Field(max_length=20, description="Optional predicate IRIs or CURIEs; null includes all predicates."),
        ] = None,
    ) -> dict[str, Any]:
        return serialize_result(
            lambda: service.describe(
                [term], direction=direction, predicates=predicates,
                limits=OntologyContextLimits(max_depth=1),
            )
        )

    def ontology_ancestors(
        term: Annotated[
            NonEmptyStr, Field(description="Class name or identifier whose stated superclasses to inspect."),
        ],
        max_depth: Annotated[
            int, Field(ge=1, le=8, description="Maximum subclass relationship hops."),
        ] = 4,
    ) -> dict[str, Any]:
        return serialize_result(
            lambda: service.describe(
                [term], direction="outgoing",
                predicates=["http://www.w3.org/2000/01/rdf-schema#subClassOf"],
                limits=OntologyContextLimits(max_depth=max_depth),
            )
        )

    def ontology_descendants(
        term: Annotated[
            NonEmptyStr, Field(description="Class name or identifier whose stated subclasses to inspect."),
        ],
        max_depth: Annotated[
            int, Field(ge=1, le=8, description="Maximum subclass relationship hops."),
        ] = 4,
    ) -> dict[str, Any]:
        return serialize_result(
            lambda: service.describe(
                [term], direction="incoming",
                predicates=["http://www.w3.org/2000/01/rdf-schema#subClassOf"],
                limits=OntologyContextLimits(max_depth=max_depth),
            )
        )

    def ontology_sparql(
        query: Annotated[
            NonEmptyStr,
            Field(
                description="A SELECT, ASK, CONSTRUCT or DESCRIBE query over the configured ontology.",
            ),
        ],
        limit: Annotated[
            int, Field(ge=1, le=200, description="Maximum returned rows or triples.")
        ] = 50,
    ) -> dict[str, Any]:
        return serialize_result(lambda: service.query_sparql(query, limit=limit))

    definitions: list[tuple[Callable[..., dict[str, Any]], str, str]] = [
        (
            ontology_search,
            "ontology_search",
            "Find ontology concepts by name, synonym or identifier. Exact matches rank first. "
            "Use returned identifiers with ontology_context to understand their meaning and graph representation.",
        ),
        (
            ontology_context,
            "ontology_context",
            "Explain concepts and how they are modeled in the graph. Returns ontology definitions, "
            "related concepts and original statements together with explicit schema bindings: entity names, "
            "properties, relationships, endpoints and directions. Use this before planning a graph query "
            "or interpreting results. Ambiguous terms return candidates; choose an identifier and call again. "
            "Use direction and predicate filters for focused follow-up; increase traversal budgets when "
            "truncation is reported, or use max_depth=0 for just the selected concepts and mappings. "
            "Missing mappings and unverified alignments are explicit. Context is bounded; no OWL inference is added.",
        ),
        (
            ontology_relationships,
            "ontology_relationships",
            "Inspect a concept's immediate ontology statements and corresponding database schema mappings. "
            "For properties, inspect outgoing domain and range statements to understand intended endpoints. "
            "For classes, inspect restrictions and related concepts. Anonymous expressions may need deeper "
            "ontology_context inspection. Ambiguity and missing mappings remain explicit. This does not query database records.",
        ),
        (
            ontology_ancestors,
            "ontology_ancestors",
            "Inspect a class's stated superclasses via outgoing rdfs:subClassOf relationships, "
            "with definitions and database schema mappings. Use to understand broader categories before "
            "planning queries or interpreting results. Returns original statements, including anonymous "
            "restrictions; no OWL inference or database-record classification is performed.",
        ),
        (
            ontology_descendants,
            "ontology_descendants",
            "Inspect a class's stated subclasses via incoming rdfs:subClassOf relationships, "
            "with definitions and database schema mappings. Use to discover narrower categories relevant "
            "to a question. No OWL inference is performed; absence or truncation does not prove there are "
            "no other subclasses or database records.",
        ),
    ]
    if service._schema_path is not None or service._supplied_mappings is not None:

        def ontology_database_element(
            element_name: Annotated[
                NonEmptyStr,
                Field(description="Graph entity name, such as a node label; case-sensitive."),
            ],
            property_name: NonEmptyStr | None = None,
            relationship_type: NonEmptyStr | None = None,
        ) -> dict[str, Any]:
            return serialize_result(
                lambda: service.resolve_database_element(
                    element_name,
                    property_name=property_name,
                    relationship_type=relationship_type,
                )
            )

        definitions.append(
            (
                ontology_database_element,
                "ontology_database_element",
                "Explain the ontology meaning of a graph entity, property or relationship. "
                "Use this when starting from graph schema or retrieved data. Provide element_name and "
                "at most one property_name or relationship_type. Returns explicit schema mappings and ontology "
                "context; unknown bindings remain explicit.",
            )
        )
    if include_sparql:
        definitions.append(
            (
                ontology_sparql,
                "ontology_sparql",
                "Query the ontology with SELECT, ASK, CONSTRUCT or DESCRIBE for precise follow-up questions. "
                "Returns SPARQL JSON or Turtle. Only the loaded snapshot is available; FROM, SERVICE and "
                "updates are excluded. Output limits do not bound query execution cost.",
            )
        )
    return [
        StructuredTool.from_function(
            func=handler,
            name=tool_name,
            description=tool_description,
            handle_tool_error=True,
            handle_validation_error=lambda validation_error: (
                f"Invalid ontology tool arguments: {validation_error}"
            ),
        )
        for handler, tool_name, tool_description in definitions
    ]
