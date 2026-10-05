"""Deterministic ontology grounding from a native RDF graph.

The source files remain canonical. RDFLib supplies storage, namespace handling
and query evaluation; this service adds resolution and bounded context. Output
limits do not bound parsing or query execution cost. Run synchronous calls in an async worker thread.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from threading import RLock
from typing import TYPE_CHECKING, Annotated, Any, TypeVar, cast
from xml.etree.ElementTree import fromstring

from langchain_core.tools import StructuredTool, ToolException
from pydantic import Field

from rdflib import BNode, Graph, Literal, OWL, RDF, URIRef
from rdflib.plugins.sparql import prepareQuery
from rdflib.plugins.sparql.parserutils import CompValue
from rdflib.term import Identifier
from rdflib.util import guess_format

from graphrag.config.ontology_config import OntologySettings
from graphrag.model.base import ContractModel, NonEmptyStr
from graphrag.model.ontology import (
    OntologyAmbiguityError,
    OntologyContext,
    OntologyContextLimits,
    OntologyDirection,
    OntologyEntity,
    OntologyError,
    OntologyFileSource,
    OntologyLoadError,
    OntologyNeighborhood,
    OntologyNotFoundError,
    OntologyQueryError,
    OntologyQueryType,
    OntologyRelationship,
    OntologyResolution,
    OntologySearchResult,
    OntologySource,
    OntologySparqlResult,
    OntologyUnsupportedError,
)

if TYPE_CHECKING:
    from graphrag.config.graph_rag_config import GraphDataProfile

T = TypeVar("T")
_IS_A = "http://www.w3.org/2000/01/rdf-schema#subClassOf"
_MAX_TERMS = 20
_Resource = URIRef | BNode
_Triple = tuple[_Resource, URIRef, Identifier]


class OntologyService:
    """Reuse one read-only ontology snapshot for lookup and bounded context.

    Construction is lazy; call ``initialize()`` during startup to fail early.
    Call ``for_question()`` at the beginning of a new question and retain its
    returned service throughout that workflow. Changed files create a new
    service; an initialized instance is never reloaded. Graph access is serialized
    to protect metadata caches and RDFLib query evaluation.
    """

    def __init__(self, settings: OntologySettings) -> None:
        self._settings = settings.model_copy(deep=True)
        self._lock = RLock()
        self._graph = Graph()
        self._files: dict[Path, tuple[str, int, int, int]] = {}
        self._source: OntologySource | None = None
        self._entities: dict[str, OntologyEntity] = {}

    @classmethod
    def from_profile(cls, profile: GraphDataProfile) -> OntologyService:
        """Create the service from the dataset's configured ontology."""

        if profile.ontology is None:
            raise OntologyLoadError(f"Profile {profile.id!r} has no ontology configured")
        return cls(profile.ontology)

    @staticmethod
    def _signature(path: Path) -> tuple[str, int, int, int]:
        resolved = path.expanduser().resolve(strict=True)
        stat = resolved.stat()
        return str(resolved), stat.st_ino, stat.st_size, stat.st_mtime_ns

    def initialize(self) -> OntologySource:
        """Load a native graph atomically, with explicitly mapped local imports."""

        with self._lock:
            if self._source is not None:
                return self._source
            try:
                graph = Graph()
                files: dict[Path, tuple[str, int, int, int]] = {}
                sources: list[OntologyFileSource] = []
                warnings: set[str] = set()
                pending = [(self._settings.path, self._settings.format)]
                while pending:
                    requested, explicit_format = pending.pop(0)
                    signature = self._signature(requested)
                    if signature[0] in {item.path for item in sources}:
                        continue
                    path = Path(signature[0])
                    contents = path.read_bytes()
                    format_name = explicit_format or guess_format(path.name)
                    if format_name is None:
                        raise OntologyUnsupportedError("Specify an RDF parser format or export to RDF/XML or Turtle")
                    if format_name in {"xml", "application/rdf+xml"} and fromstring(contents).tag == "{http://www.w3.org/2002/07/owl#}Ontology":
                        raise OntologyUnsupportedError("OWL/XML requires an RDF/XML or Turtle export")
                    document = Graph().parse(data=contents, publicID=path.as_uri(), format=format_name)
                    files[requested] = signature
                    sources.append(OntologyFileSource(path=str(path), sha256=sha256(contents).hexdigest()))
                    graph += document
                    for prefix, namespace in document.namespaces():
                        graph.bind(prefix, namespace, override=False)
                    for imported in sorted(set(map(str, document.objects(None, OWL.imports)))):
                        if imported in self._settings.imports:
                            pending.append((self._settings.imports[imported], None))
                        else:
                            warning = f"Ontology import was not loaded: {imported}"
                            if self._settings.unresolved_imports == "error":
                                raise ValueError(warning)
                            warnings.add(warning)
                if any(self._signature(checked_path) != expected_signature
                       for checked_path, expected_signature in files.items()):
                    raise ValueError("Ontology files changed while loading; retry initialization")
                for prefix, namespace in self._settings.prefixes.items():
                    graph.bind(prefix, URIRef(namespace), replace=True)
                root, *imports = sources
                source = OntologySource(
                    path=root.path, sha256=root.sha256, library="rdflib", library_version=version("rdflib"),
                    imported_files=tuple(imports), warnings=tuple(sorted(warnings)),
                )
                # Only named subjects are searchable; referenced resources remain
                # accessible by identifier and through neighborhood traversal.
                entities = {
                    str(subject): self._read_entity(graph, subject)
                    for subject in sorted(set(graph.subjects()), key=str) if isinstance(subject, URIRef)
                }
            except Exception as exc:
                raise OntologyLoadError(f"Cannot load ontology from {self._settings.path}: {exc}") from exc
            self._graph, self._files, self._entities, self._source = graph, files, entities, source
            return source

    def for_question(self) -> OntologyService:
        """Check file stats only at a new question boundary; retain old snapshots.

        Keep the returned instance throughout that question. A changed root or
        import creates a new instance. SHA-256 identifies the loaded bytes;
        changes preserving all stat fields require explicit new construction.
        """

        with self._lock:
            self.initialize()
            try:
                if all(self._signature(path) == signature for path, signature in self._files.items()):
                    return self
            except OSError as exc:
                raise OntologyLoadError(f"Cannot check ontology files: {exc}") from exc
            refreshed = type(self)(self._settings)
            refreshed.initialize()
            return refreshed

    @staticmethod
    def _call(operation: str, function: Callable[[], T]) -> T:
        try:
            return function()
        except OntologyQueryError:
            raise
        except NotImplementedError as exc:
            raise OntologyUnsupportedError(f"Cannot {operation}") from exc
        except Exception as exc:
            raise OntologyQueryError(f"Failed to {operation}: {exc}") from exc

    @staticmethod
    def _iri(graph: Graph, value: str) -> URIRef:
        try:
            return graph.namespace_manager.expand_curie(value)
        except ValueError:
            return URIRef(value)

    def _read_entity(self, graph: Graph, subject: URIRef) -> OntologyEntity:
        def literals(predicates: Sequence[str]) -> list[str]:
            values: list[str] = []
            for predicate in predicates:
                annotations = (value for value in graph.objects(subject, self._iri(graph, predicate))
                               if isinstance(value, Literal))
                values.extend(str(annotation) for annotation in sorted(annotations, key=lambda literal: (
                    0 if literal.language == self._settings.language else 1 if not literal.language else 2,
                    str(literal), literal.language or "", str(literal.datatype or ""),
                )))
            return list(dict.fromkeys(values))

        labels = literals(self._settings.label_predicates)
        definitions = literals(self._settings.definition_predicates)
        return OntologyEntity(
            identifier=str(subject), label=next(iter(labels), None), definition=next(iter(definitions), None),
            aliases=tuple(value for value in literals(self._settings.alias_predicates) if value not in labels),
            types=tuple(sorted(str(value) for value in graph.objects(subject, RDF.type) if isinstance(value, URIRef))),
        )

    def _entity(self, identifier: str) -> OntologyEntity:
        if identifier not in self._entities:
            return self._call("read entity metadata", lambda: self._read_entity(self._graph, URIRef(identifier)))
        return self._entities[identifier]

    @staticmethod
    def _query(value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Ontology query must be a nonempty string")
        return value.strip()

    @staticmethod
    def _limit(value: int) -> None:
        if type(value) is not int or not 1 <= value <= 200:
            raise ValueError("limit must be an integer between 1 and 200")

    def _identifier(self, query: str) -> str | None:
        node = self._iri(self._graph, query)
        if (node, None, None) in self._graph or (None, None, node) in self._graph or (None, node, None) in self._graph:
            return str(node)
        return None

    def get_entity(self, identifier: str) -> OntologyEntity:
        """Lookup an IRI or bound CURIE; unknown IDs raise explicitly."""

        query = self._query(identifier)
        with self._lock:
            self.initialize()
            entity_id = self._identifier(query)
            if entity_id is None:
                raise OntologyNotFoundError(f"No ontology entity with identifier {query!r}")
            return self._entity(entity_id)

    def search(self, query: str, *, limit: int = 20, exact: bool = False) -> OntologySearchResult:
        """Search IDs, labels, and aliases literally; exact matches rank first.

        Matching is case-insensitive, except that canonical ID lookup retains the
        case. No wildcard, regex, fuzzy matching, or model inference is used.
        Deprecated entities are retained so historical data can be interpreted.
        """

        query = self._query(query)
        self._limit(limit)
        folded = query.casefold()
        with self._lock:
            self.initialize()
            requested_id = self._identifier(query)
            matches: list[tuple[int, str]] = []
            for identifier, entity in self._entities.items():
                values = [identifier.casefold(), *(alias.casefold() for alias in entity.aliases)]
                if entity.label is not None:
                    values.append(entity.label.casefold())
                if identifier == requested_id:
                    rank = 0
                elif folded in values:
                    rank = 1
                elif not exact and any(folded in value for value in values):
                    rank = 2
                else:
                    continue
                matches.append((rank, identifier))
            matches.sort()
            return OntologySearchResult(
                query=query, entities=tuple(self._entity(matched_id) for _, matched_id in matches[:limit]),
                total_matches=len(matches), truncated=len(matches) > limit,
            )

    def resolve(self, term: str, *, limit: int = 10) -> OntologyResolution:
        """Prefer IRIs or bound CURIEs, otherwise retain every exact label/alias match."""

        query = self._query(term)
        self._limit(limit)
        with self._lock:
            self.initialize()
            identifier = self._identifier(query)
            if identifier is not None:
                return OntologyResolution(
                    query=query, status="resolved", candidates=(self._entity(identifier),), total_matches=1,
                )
            folded = query.casefold()
            identifiers = [
                matched_id for matched_id, entity in self._entities.items()
                if (entity.label is not None and entity.label.casefold() == folded)
                or any(alias.casefold() == folded for alias in entity.aliases)
            ]
            total = len(identifiers)
            return OntologyResolution(
                query=query, status="not_found" if not total else "resolved" if total == 1 else "ambiguous",
                candidates=tuple(self._entity(candidate_id) for candidate_id in identifiers[:limit]),
                total_matches=total, truncated=total > limit,
            )

    def resolve_entity(self, term: str) -> OntologyEntity:
        """Require a unique resolution for deterministic workflow operations."""

        result = self.resolve(term)
        if result.status == "not_found":
            raise OntologyNotFoundError(f"No exact ontology match for {result.query!r}")
        if result.status == "ambiguous":
            raise OntologyAmbiguityError(result)
        return result.candidates[0]

    def _edges(
        self, nodes: Sequence[_Resource], direction: OntologyDirection,
        predicates: tuple[URIRef, ...] | None,
    ) -> list[_Triple]:
        edges: set[_Triple] = set()
        for node in nodes:
            for predicate in (None,) if predicates is None else predicates:
                selectors = []
                if direction in {"outgoing", "both"}:
                    selectors.append((node, predicate, None))
                if direction in {"incoming", "both"}:
                    selectors.append((None, predicate, node))
                for selector in selectors:
                    for subject, relation, value in self._graph.triples(selector):
                        if isinstance(subject, (URIRef, BNode)) and isinstance(relation, URIRef) and isinstance(value, Identifier):
                            edges.add((subject, relation, value))
        return sorted(edges, key=lambda edge: tuple(term.n3() for term in edge))

    @staticmethod
    def _bounded(entity: OntologyEntity, limits: OntologyContextLimits) -> OntologyEntity:
        truncated: list[str] = []
        label = entity.label
        definition = entity.definition
        if label is not None and len(label) > limits.max_label_chars:
            label = label[:limits.max_label_chars]
            truncated.append("label")
        if definition is not None and len(definition) > limits.max_definition_chars:
            definition = definition[:limits.max_definition_chars]
            truncated.append("definition")
        aliases = entity.aliases[:limits.max_aliases]
        if len(entity.aliases) > len(aliases) or any(
            len(alias) > limits.max_label_chars for alias in aliases
        ):
            truncated.append("aliases")
        return entity.model_copy(update={
            "label": label, "definition": definition,
            "aliases": tuple(alias[:limits.max_label_chars] for alias in aliases),
            "truncated_fields": tuple(truncated),
        })

    @staticmethod
    def _terms(terms: Sequence[str]) -> tuple[str, ...]:
        if isinstance(terms, str):
            raise ValueError("Supply a sequence of ontology terms, not a string")
        if len(terms) > _MAX_TERMS:
            raise ValueError(f"At most {_MAX_TERMS} ontology terms may be requested")
        return tuple(dict.fromkeys(OntologyService._query(term) for term in terms))

    def neighborhood(
        self, identifiers: Sequence[str], *, direction: OntologyDirection = "both",
        predicates: Sequence[str] | None = None, limits: OntologyContextLimits | None = None,
    ) -> OntologyNeighborhood:
        """Traverse original RDF triples, including blank nodes and literals.

        The node budget includes anonymous resources; literals are terminal
        values. No OWL expressions are projected into invented named edges.
        Blank-node IDs are meaningful only within this loaded snapshot.
        """

        terms = self._terms(identifiers)
        if direction not in {"outgoing", "incoming", "both"}:
            raise ValueError(f"Invalid ontology direction: {direction!r}")
        selected_predicates = None if predicates is None else self._terms(predicates)
        limits = limits or OntologyContextLimits()
        with self._lock:
            self.initialize()
            predicate_nodes = None if selected_predicates is None else tuple(
                self._iri(self._graph, predicate_text) for predicate_text in selected_predicates
            )
            seeds = tuple(dict.fromkeys(self.get_entity(term).identifier for term in terms))
            selected: list[_Resource] = [URIRef(seed) for seed in seeds[:limits.max_entities]]
            visited = set(selected)
            frontier = selected[:]
            edges: set[_Triple] = set()
            reasons = {"max_entities"} if len(selected) < len(seeds) else set()
            for _ in range(limits.max_depth):
                following: list[_Resource] = []
                for edge in self._call("read relationships", lambda: self._edges(frontier, direction, predicate_nodes)):
                    if edge in edges:
                        continue
                    if len(edges) == limits.max_relationships:
                        reasons.add("max_relationships")
                        break
                    new_resources: list[_Resource] = []
                    for endpoint in dict.fromkeys((edge[0], edge[2])):
                        if isinstance(endpoint, (URIRef, BNode)) and endpoint not in visited:
                            new_resources.append(endpoint)
                    if len(selected) + len(new_resources) > limits.max_entities:
                        reasons.add("max_entities")
                        continue
                    edges.add(edge)
                    visited.update(new_resources)
                    selected.extend(new_resources)
                    following.extend(new_resources)
                frontier = following
                if not frontier or "max_relationships" in reasons:
                    break
            if frontier and any(candidate_edge not in edges
                                for candidate_edge in self._edges(frontier, direction, predicate_nodes)):
                reasons.add("max_depth")
            entities = tuple(self._bounded(self._entity(str(node)), limits) for node in selected if isinstance(node, URIRef))
            if any(entity.truncated_fields for entity in entities):
                reasons.add("metadata")
            relationship_results = []
            for subject, predicate, value in sorted(edges, key=lambda rdf_triple: tuple(term.n3() for term in rdf_triple)):
                text = str(value)
                if isinstance(value, Literal) and len(text) > limits.max_literal_chars:
                    text = text[:limits.max_literal_chars]
                    reasons.add("literal_values")
                relationship_results.append(OntologyRelationship(
                    subject=subject.n3() if isinstance(subject, BNode) else str(subject), predicate=str(predicate),
                    object=value.n3() if isinstance(value, BNode) else text,
                    subject_kind="blank_node" if isinstance(subject, BNode) else "iri",
                    object_kind="literal" if isinstance(value, Literal) else "blank_node" if isinstance(value, BNode) else "iri",
                    datatype=str(value.datatype) if isinstance(value, Literal) and value.datatype else None,
                    language=value.language if isinstance(value, Literal) else None,
                ))
            return OntologyNeighborhood(
                seed_ids=seeds, direction=direction,
                predicates=None if predicate_nodes is None else tuple(map(str, predicate_nodes)),
                entities=entities, relationships=tuple(relationship_results), truncation_reasons=tuple(sorted(reasons)),
            )

    def relationships(
        self, identifier: str, *, direction: OntologyDirection = "outgoing",
        predicates: Sequence[str] | None = None, limit: int = 60,
    ) -> OntologyNeighborhood:
        """Return one hop of original triples with bounded endpoint metadata."""

        self._limit(limit)
        return self.neighborhood(
            [identifier], direction=direction, predicates=predicates,
            limits=OntologyContextLimits(max_depth=1, max_entities=200, max_relationships=limit),
        )

    def ancestors(
        self, identifier: str, *, predicates: Sequence[str] = (_IS_A,),
        limits: OntologyContextLimits | None = None,
    ) -> OntologyNeighborhood:
        """Follow outgoing subclass edges (or explicitly selected predicates).

        The returned neighborhood includes the seed and path edges. Depth is
        bounded, so this is not guaranteed to be the complete transitive closure.
        """

        return self.neighborhood(
            [identifier], direction="outgoing", predicates=predicates,
            limits=limits or OntologyContextLimits(max_depth=4),
        )

    def descendants(
        self, identifier: str, *, predicates: Sequence[str] = (_IS_A,),
        limits: OntologyContextLimits | None = None,
    ) -> OntologyNeighborhood:
        """Follow incoming subclass edges, retaining their original orientation."""

        return self.neighborhood(
            [identifier], direction="incoming", predicates=predicates,
            limits=limits or OntologyContextLimits(max_depth=4),
        )

    def get_context(
        self, terms: Sequence[str], *, direction: OntologyDirection = "outgoing",
        predicates: Sequence[str] | None = None, limits: OntologyContextLimits | None = None,
    ) -> OntologyContext:
        """Resolve up to 20 data terms and return bounded context for unique matches.

        Serialize with ``to_structured_text()`` or ``model_dump(mode='json')``.
        Unknown/ambiguous terms are reported rather than silently grounded. The
        caller chooses terms from retrieved data; raw graph labels are not
        automatically assumed to be ontology identifiers or OWL classes.
        """

        terms = self._terms(terms)
        limits = limits or OntologyContextLimits()
        with self._lock:
            source = self.initialize()
            resolutions = tuple(self.resolve(term, limit=limits.max_candidates) for term in terms)
            seeds = [result.candidates[0].identifier for result in resolutions if result.status == "resolved"]
            context_neighborhood = self.neighborhood(seeds, direction=direction, predicates=predicates, limits=limits)
            resolutions = tuple(result.model_copy(update={
                "candidates": tuple(self._bounded(candidate, limits) for candidate in result.candidates),
            }) for result in resolutions)
            warnings = set(source.warnings) | {
                f"{result.status}: {result.query}" for result in resolutions if result.status != "resolved"
            }
            if any(result.truncated for result in resolutions):
                warnings.add("resolution candidates truncated")
            context_entities = (
                *context_neighborhood.entities,
                *(resolved_entity for result in resolutions for resolved_entity in result.candidates),
            )
            for entity in context_entities:
                if entity.truncated_fields:
                    warnings.add("entity metadata truncated")
            return OntologyContext(
                source=source, resolutions=resolutions, neighborhood=context_neighborhood,
                limits=limits, warnings=tuple(sorted(warnings)),
            )

    def query_sparql(self, query: str, *, limit: int = 50) -> OntologySparqlResult:
        """Run native SELECT/ASK/CONSTRUCT/DESCRIBE against this local snapshot.

        SELECT/ASK use RDFLib's standard SPARQL JSON result format. Graph
        results use Turtle. Bounds apply to returned rows/triples, not query
        execution or individual value lengths. FROM/SERVICE are excluded because
        they would access sources outside this configured ontology snapshot.
        """

        query = self._query(query)
        self._limit(limit)
        with self._lock:
            source = self.initialize()
            def evaluate() -> OntologySparqlResult:
                prepared = prepareQuery(query, initNs=dict(self._graph.namespaces()))
                pending = [prepared.algebra]
                while pending:
                    node = pending.pop()
                    if isinstance(node, CompValue) and node.name in {"ServiceGraphPattern", "DatasetClause"}:
                        raise OntologyUnsupportedError("FROM and SERVICE are outside the local ontology snapshot")
                    if isinstance(node, dict):
                        pending.extend(node.values())
                    elif isinstance(node, (list, tuple)):
                        pending.extend(node)
                result = self._graph.query(prepared)
                truncated = False
                if result.type == "SELECT":
                    bindings = result.bindings
                    truncated = len(bindings) > limit
                    result.bindings = bindings[:limit]
                if result.type in {"SELECT", "ASK"}:
                    serialized = result.serialize(format="json")
                    assert serialized is not None
                    data = json.loads(serialized)
                else:
                    assert result.graph is not None
                    triples = sorted(result.graph, key=lambda edge: tuple(term.n3() for term in edge))
                    truncated = len(triples) > limit
                    bounded = Graph()
                    for prefix, namespace in self._graph.namespaces():
                        bounded.bind(prefix, namespace)
                    for triple in triples[:limit]:
                        bounded.add(triple)
                    data = bounded.serialize(format="turtle")
                return OntologySparqlResult(source=source, query_type=cast(OntologyQueryType, result.type), data=data, truncated=truncated)
            return self._call("evaluate SPARQL query", evaluate)


def create_ontology_tools(service: OntologyService) -> list[StructuredTool]:
    """Create LangChain tools bound to one question's ontology snapshot.

    Pass the returned tools to a plain or research agent's tool collection.
    Call ``service.for_question()`` before constructing them for a new question;
    tools never reload the ontology. LangChain provides ``invoke`` and ``ainvoke``
    for these synchronous handlers, running async calls in an executor thread.
    """

    def serialize_result(operation: Callable[[], ContractModel]) -> dict[str, Any]:
        try:
            return operation().model_dump(mode="json")
        except (OntologyError, ValueError) as exc:
            raise ToolException(f"{type(exc).__name__}: {exc}") from exc

    def ontology_search(
        query: Annotated[NonEmptyStr, Field(description="A name, alias, IRI or bound CURIE to find.")],
        limit: Annotated[int, Field(ge=1, le=200, description="Maximum matching entities to return.")] = 10,
        exact: Annotated[bool, Field(description="Require an exact match instead of a substring.")] = False,
    ) -> dict[str, Any]:
        return serialize_result(lambda: service.search(query, limit=limit, exact=exact))

    def ontology_context(
        terms: Annotated[list[NonEmptyStr], Field(
            min_length=1, max_length=20,
            description="Terms from the question or data, or identifiers returned by ontology_search.",
        )],
        direction: Annotated[OntologyDirection, Field(
            description="Outgoing follows a concept's assertions; incoming finds references; both does both.",
        )] = "outgoing",
        predicates: Annotated[list[NonEmptyStr] | None, Field(
            description="Optional predicate IRIs/CURIEs applied at every hop. Null includes all; [] includes none.",
        )] = None,
        limits: Annotated[OntologyContextLimits | None, Field(
            description="Optional output budgets; defaults include two hops, 30 resources and 60 triples.",
        )] = None,
    ) -> dict[str, Any]:
        return serialize_result(lambda: service.get_context(
            terms, direction=direction, predicates=predicates, limits=limits,
        ))

    def ontology_sparql(
        query: Annotated[NonEmptyStr, Field(
            description="A SELECT, ASK, CONSTRUCT or DESCRIBE query over the configured ontology.",
        )],
        limit: Annotated[int, Field(ge=1, le=200, description="Maximum returned rows or triples.")] = 50,
    ) -> dict[str, Any]:
        return serialize_result(lambda: service.query_sparql(query, limit=limit))

    definitions = (
        (ontology_search, "ontology_search", (
            "Find ontology entities by literal name, alias or identifier. Exact matches rank first. "
            "Use this to discover full IRIs before requesting ontology_context. Matches are candidates, "
            "not database schema mappings or inferred facts. Results report counts and truncation."
        )),
        (ontology_context, "ontology_context", (
            "Get bounded ontology meaning for planning, querying retrieved data or interpreting findings. "
            "Returns labels, definitions, aliases, types and original RDF neighborhood triples with source hashes. "
            "Missing or ambiguous terms stay explicit; choose an identifier from the candidates or search again. "
            "Outgoing rdfs:subClassOf traversal finds parents; incoming finds children. Predicate filters apply "
            "at every hop, so omit them to inspect anonymous OWL restrictions. Truncated context is incomplete. "
            "Ontology statements do not establish how the database implements them."
        )),
        (ontology_sparql, "ontology_sparql", (
            "Answer precise ontology questions with native SELECT, ASK, CONSTRUCT or DESCRIBE. "
            "Use full IRIs, explicit PREFIX declarations or graph-bound prefixes; ORDER BY gives stable SELECT order. "
            "Returns standard SPARQL JSON or Turtle, source hashes and truncation. "
            "Only the configured snapshot is queried: updates, FROM and SERVICE are unavailable. "
            "No OWL inference is added. Output bounds do not limit execution cost or individual text values."
        )),
    )
    return [
        StructuredTool.from_function(
            func=handler, name=tool_name, description=tool_description,
            handle_tool_error=True,
            handle_validation_error=lambda validation_error: f"Invalid ontology tool arguments: {validation_error}",
        )
        for handler, tool_name, tool_description in definitions
    ]
