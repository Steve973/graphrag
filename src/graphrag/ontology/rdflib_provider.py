"""Deterministic ontology grounding from a native RDF graph.

The source files remain canonical. RDFLib supplies storage, namespace handling
and query evaluation; the application service assembles and bounds context. Output
limits do not bound parsing or query execution cost. Run synchronous calls in an async worker thread.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from hashlib import sha256
from importlib.metadata import version
from threading import RLock
from typing import TypeVar, cast
from xml.etree.ElementTree import fromstring

from rdflib import OWL, RDF, BNode, Graph, Literal, URIRef
from rdflib.plugins.sparql import prepareQuery
from rdflib.plugins.sparql.algebra import traverse
from rdflib.plugins.sparql.parserutils import CompValue
from rdflib.term import Identifier, Node
from rdflib.util import guess_format

from graphrag.config.ontology_config import OntologyReaderSettings
from graphrag.model.ontology import (
    OntologyContextLimits,
    OntologyDirection,
    OntologyEntity,
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
from graphrag.ontology.base_providers import OntologyProvider
from graphrag.ontology.resources import OntologyResources

T = TypeVar("T")
_MAX_TERMS = 20
_Resource = URIRef | BNode
_Triple = tuple[_Resource, URIRef, Identifier]


class RDFLibOntologyProvider(OntologyProvider):
    """Load one read-only ontology for this provider's lifetime.

    Call initialize during startup to load resources and fail early. Resource
    changes require an application restart. Graph access is serialized to
    protect metadata caches and RDFLib query evaluation.
    """

    def __init__(
        self,
        loader: OntologyResources,
        settings: OntologyReaderSettings | None = None,
    ) -> None:
        self.loader = loader
        self._settings = (settings or OntologyReaderSettings()).model_copy(deep=True)
        self._lock = RLock()
        self._graph = Graph()
        self._source: OntologySource | None = None

    @property
    def settings(self) -> OntologyReaderSettings:
        return self._settings.model_copy(deep=True)

    def initialize(self) -> OntologySource:
        """Parse provider-supplied bytes atomically, following available OWL imports."""

        with self._lock:
            if self._source is not None:
                return self._source
            try:
                graph = Graph()
                sources: list[OntologyFileSource] = []
                warnings: set[str] = set()
                pending = [self.loader.get_resource()]
                while pending:
                    resource = pending.pop(0)
                    if resource.source in {item.path for item in sources}:
                        continue
                    contents = resource.content
                    format_name = (
                        (
                            (self.loader.format or self._settings.format)
                            if not sources
                            else None
                        )
                        or guess_format(resource.source)
                        or self.loader.format
                    )
                    if format_name is None:
                        raise OntologyUnsupportedError(
                            "Specify an RDF parser format or export to RDF/XML or Turtle"
                        )
                    if (
                        format_name in {"xml", "application/rdf+xml"}
                        and fromstring(contents).tag
                        == "{http://www.w3.org/2002/07/owl#}Ontology"
                    ):
                        raise OntologyUnsupportedError(
                            "OWL/XML requires an RDF/XML or Turtle export"
                        )
                    document = Graph().parse(
                        data=contents,
                        publicID=resource.base_uri or resource.source,
                        format=format_name,
                    )
                    sources.append(
                        OntologyFileSource(
                            path=resource.source,
                            sha256=sha256(contents).hexdigest(),
                        )
                    )
                    graph += document
                    for prefix, namespace in document.namespaces():
                        graph.bind(prefix, namespace, override=False)
                    for imported in sorted(
                        set(map(str, document.objects(None, OWL.imports)))
                    ):
                        import_resource = self.loader.get_import(imported)
                        if import_resource is not None:
                            pending.append(import_resource)
                        else:
                            warning = f"Ontology import was not loaded: {imported}"
                            if self._settings.unresolved_imports == "error":
                                raise ValueError(warning)
                            warnings.add(warning)
                for prefix, namespace in self._settings.prefixes.items():
                    graph.bind(prefix, URIRef(namespace), replace=True)
                root, *imports = sources
                source = OntologySource(
                    path=root.path,
                    sha256=root.sha256,
                    library="rdflib",
                    library_version=version("rdflib"),
                    imported_files=tuple(imports),
                    warnings=tuple(sorted(warnings)),
                )
            except Exception as exc:
                raise OntologyLoadError(
                    f"Cannot load ontology resources: {exc}"
                ) from exc
            self._graph, self._source = graph, source
            return source

    @staticmethod
    def _call(
        operation: str,
        function: Callable[[], T],
    ) -> T:
        try:
            return function()
        except OntologyQueryError:
            raise
        except NotImplementedError as exc:
            raise OntologyUnsupportedError(f"Cannot {operation}") from exc
        except Exception as exc:
            raise OntologyQueryError(f"Failed to {operation}: {exc}") from exc

    @staticmethod
    def _iri(
        graph: Graph,
        value: str,
    ) -> URIRef:
        try:
            return graph.namespace_manager.expand_curie(value)
        except ValueError:
            return URIRef(value)

    def _read_entity(
        self,
        graph: Graph,
        subject: URIRef,
    ) -> OntologyEntity:
        def literals(predicates: Sequence[str]) -> list[str]:
            values: list[str] = []
            for predicate in predicates:
                annotations = (
                    value
                    for value in graph.objects(subject, self._iri(graph, predicate))
                    if isinstance(value, Literal)
                )
                values.extend(
                    str(annotation)
                    for annotation in sorted(
                        annotations,
                        key=lambda literal: (
                            (
                                0
                                if literal.language == self._settings.language
                                else 1 if not literal.language else 2
                            ),
                            str(literal),
                            literal.language or "",
                            str(literal.datatype or ""),
                        ),
                    )
                )
            return list(dict.fromkeys(values))

        labels = literals(self._settings.label_predicates)
        definitions = literals(self._settings.definition_predicates)
        return OntologyEntity(
            identifier=str(subject),
            label=next(iter(labels), None),
            definition=next(iter(definitions), None),
            aliases=tuple(
                value
                for value in literals(self._settings.alias_predicates)
                if value not in labels
            ),
            types=tuple(
                sorted(
                    str(value)
                    for value in graph.objects(subject, RDF.type)
                    if isinstance(value, URIRef)
                )
            ),
        )

    def _entity(
        self,
        identifier: str,
    ) -> OntologyEntity:
        return self._call(
            "read entity metadata",
            lambda: self._read_entity(self._graph, URIRef(identifier)),
        )

    @staticmethod
    def _query(value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Ontology query must be a nonempty string")
        return value.strip()

    @staticmethod
    def _limit(value: int) -> None:
        if type(value) is not int or not 1 <= value <= 200:
            raise ValueError("limit must be an integer between 1 and 200")

    def _identifier(
        self,
        query: str,
    ) -> str | None:
        node = self._iri(self._graph, query)
        if (
            (node, None, None) in self._graph
            or (None, None, node) in self._graph
            or (None, node, None) in self._graph
        ):
            return str(node)
        return None

    def get_entity(
        self,
        identifier: str,
    ) -> OntologyEntity:
        """Perform a lookup of an IRI or bound CURIE; unknown IDs raise explicitly."""

        query = self._query(identifier)
        with self._lock:
            self.initialize()
            entity_id = self._identifier(query)
            if entity_id is None:
                raise OntologyNotFoundError(
                    f"No ontology entity with identifier {query!r}"
                )
            return self._entity(entity_id)

    def _matches(
        self,
        query: str,
        *,
        exact: bool,
        include_identifiers: bool,
    ) -> list[str]:
        """Let RDFLib match annotation text and rank exact matches first."""

        predicates = " ".join(
            self._iri(self._graph, predicate).n3()
            for predicate in dict.fromkeys(
                (*self._settings.label_predicates, *self._settings.alias_predicates)
            )
        )
        # Only configured predicate IRIs enter query syntax. User text is bound
        # as a literal, including quotes and SPARQL-looking text.
        prepared = prepareQuery(
            """
            SELECT DISTINCT ?entity ?rank WHERE {
                {
                    ?entity ?predicate ?text .
                    VALUES ?predicate { """ + predicates + """ }
                    FILTER(isLiteral(?text))
                } UNION {
                    ?entity ?predicate ?object .
                    FILTER(?include_identifiers)
                    BIND(STR(?entity) AS ?text)
                }
                FILTER(isIRI(?entity))
                BIND(LCASE(STR(?text)) AS ?value)
                FILTER(?value = LCASE(?query) ||
                       (!?exact && CONTAINS(?value, LCASE(?query))))
                BIND(IF(?value = LCASE(?query), 0, 1) AS ?rank)
            } ORDER BY ?rank ?entity
            """
        )
        matches = self._call(
            "search ontology",
            lambda: list(
                self._graph.query(
                    prepared,
                    initBindings={
                        "query": Literal(query),
                        "exact": Literal(exact),
                        "include_identifiers": Literal(include_identifiers),
                    },
                )
            ),
        )
        identifiers = dict.fromkeys(str(row.entity) for row in matches)
        requested_id = self._identifier(query) if include_identifiers else None
        if requested_id is not None:
            identifiers.pop(requested_id, None)
            return [requested_id, *identifiers]
        return list(identifiers)

    def search(
        self,
        query: str,
        *,
        limit: int = 20,
        exact: bool = False,
    ) -> OntologySearchResult:
        """Search IDs, configured labels and aliases literally; exact matches rank first."""

        query = self._query(query)
        self._limit(limit)
        with self._lock:
            self.initialize()
            matches = self._matches(query, exact=exact, include_identifiers=True)
            return OntologySearchResult(
                query=query,
                entities=tuple(
                    self._entity(identifier) for identifier in matches[:limit]
                ),
                total_matches=len(matches),
                truncated=len(matches) > limit,
            )

    def resolve(
        self,
        term: str,
        *,
        limit: int = 10,
    ) -> OntologyResolution:
        """Prefer known identifiers; otherwise retain every exact label/alias match."""

        query = self._query(term)
        self._limit(limit)
        with self._lock:
            self.initialize()
            identifier = self._identifier(query)
            matches = (
                [identifier]
                if identifier is not None
                else self._matches(query, exact=True, include_identifiers=False)
            )
            total = len(matches)
            return OntologyResolution(
                query=query,
                status=(
                    "not_found"
                    if not total
                    else "resolved" if total == 1 else "ambiguous"
                ),
                candidates=tuple(
                    self._entity(identifier) for identifier in matches[:limit]
                ),
                total_matches=total,
                truncated=total > limit,
            )

    def _edges(
        self,
        nodes: Sequence[_Resource],
        direction: OntologyDirection,
        predicates: tuple[URIRef, ...] | None,
    ) -> list[_Triple]:
        if predicates == ():
            return []
        edges: set[tuple[Node, Node, Node]] = set()
        predicate_choice: list[Node] | None = (
            None if predicates is None else list(predicates)
        )
        for node in nodes:
            if direction in {"outgoing", "both"}:
                if predicate_choice is None:
                    edges.update(self._graph.triples((node, None, None)))
                else:
                    edges.update(
                        self._graph.triples_choices((node, predicate_choice, None))
                    )
            if direction in {"incoming", "both"}:
                if predicate_choice is None:
                    edges.update(self._graph.triples((None, None, node)))
                else:
                    edges.update(
                        self._graph.triples_choices((None, predicate_choice, node))
                    )
        # RDFLib types every term as Node; the loaded RDF graph has RDF triples.
        return cast(
            list[_Triple],
            sorted(edges, key=lambda edge: tuple(term.n3() for term in edge)),
        )

    @staticmethod
    def _terms(terms: Sequence[str]) -> tuple[str, ...]:
        if isinstance(terms, str):
            # Retain the public ValueError contract used by tool error handling.
            raise ValueError(  # noqa: TRY004
                "Supply a sequence of ontology terms, not a string"
            )
        if len(terms) > _MAX_TERMS:
            raise ValueError(f"At most {_MAX_TERMS} ontology terms may be requested")
        return tuple(
            dict.fromkeys(RDFLibOntologyProvider._query(term) for term in terms)
        )

    def neighborhood(
        self,
        identifiers: Sequence[str],
        *,
        direction: OntologyDirection = "both",
        predicates: Sequence[str] | None = None,
        limits: OntologyContextLimits | None = None,
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
            predicate_nodes = (
                None
                if selected_predicates is None
                else tuple(
                    self._iri(self._graph, predicate_text)
                    for predicate_text in selected_predicates
                )
            )
            seeds = tuple(
                dict.fromkeys(self.get_entity(term).identifier for term in terms)
            )
            selected: list[_Resource] = [
                URIRef(seed) for seed in seeds[: limits.max_entities]
            ]
            visited = set(selected)
            frontier = selected[:]
            edges: set[_Triple] = set()
            reasons = {"max_entities"} if len(selected) < len(seeds) else set()
            for _ in range(limits.max_depth):
                following: list[_Resource] = []
                for edge in self._call(
                    "read relationships",
                    lambda: self._edges(frontier, direction, predicate_nodes),
                ):
                    if edge in edges:
                        continue
                    if len(edges) == limits.max_relationships:
                        reasons.add("max_relationships")
                        break
                    new_resources: list[_Resource] = []
                    for endpoint in dict.fromkeys((edge[0], edge[2])):
                        if (
                            isinstance(endpoint, (URIRef, BNode))
                            and endpoint not in visited
                        ):
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
            if frontier and any(
                candidate_edge not in edges
                for candidate_edge in self._edges(frontier, direction, predicate_nodes)
            ):
                reasons.add("max_depth")
            entities = tuple(
                self._entity(str(node))
                for node in selected
                if isinstance(node, URIRef)
            )
            relationship_results = []
            for subject, predicate, value in sorted(
                edges, key=lambda rdf_triple: tuple(term.n3() for term in rdf_triple)
            ):
                text = str(value)
                relationship_results.append(
                    OntologyRelationship(
                        subject=(
                            subject.n3() if isinstance(subject, BNode) else str(subject)
                        ),
                        predicate=str(predicate),
                        object=value.n3() if isinstance(value, BNode) else text,
                        subject_kind=(
                            "blank_node" if isinstance(subject, BNode) else "iri"
                        ),
                        object_kind=(
                            "literal"
                            if isinstance(value, Literal)
                            else "blank_node" if isinstance(value, BNode) else "iri"
                        ),
                        datatype=(
                            str(value.datatype)
                            if isinstance(value, Literal) and value.datatype
                            else None
                        ),
                        language=value.language if isinstance(value, Literal) else None,
                    )
                )
            return OntologyNeighborhood(
                seed_ids=seeds,
                direction=direction,
                predicates=(
                    None
                    if predicate_nodes is None
                    else tuple(map(str, predicate_nodes))
                ),
                entities=entities,
                relationships=tuple(relationship_results),
                truncation_reasons=tuple(sorted(reasons)),
            )

    def query_sparql(
        self,
        query: str,
        *,
        limit: int = 50,
    ) -> OntologySparqlResult:
        """Run native SELECT/ASK/CONSTRUCT/DESCRIBE against this local snapshot.

        SELECT/ASK use RDFLib's standard SPARQL JSON result format. Graph
        results use Turtle. SELECT evaluation receives an outer limit with one
        lookahead row. Sorting/aggregation can still process the complete graph;
        bounds do not limit execution time or individual value lengths. FROM/SERVICE are excluded because
        they would access sources outside this configured ontology snapshot.
        """

        query = self._query(query)
        self._limit(limit)
        with self._lock:
            source = self.initialize()

            def evaluate() -> OntologySparqlResult:
                prepared = prepareQuery(query, initNs=dict(self._graph.namespaces()))

                def check_scope(node: object) -> None:
                    if isinstance(node, CompValue) and node.name in {
                        "ServiceGraphPattern",
                        "DatasetClause",
                    }:
                        raise OntologyUnsupportedError(
                            "FROM and SERVICE are outside the local ontology snapshot"
                        )

                traverse(prepared.algebra, visitPre=check_scope)
                if prepared.algebra.name == "SelectQuery":
                    # Let RDFLib apply an outer LIMIT, preserving the query's own
                    # ORDER BY, DISTINCT, aggregates, LIMIT/OFFSET and empty bindings.
                    prepared.algebra["p"] = CompValue(
                        "Slice",
                        p=prepared.algebra.p,
                        start=0,
                        length=limit + 1,
                    )
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
                    triples = sorted(
                        result.graph, key=lambda edge: tuple(term.n3() for term in edge)
                    )
                    truncated = len(triples) > limit
                    bounded = Graph()
                    for prefix, namespace in self._graph.namespaces():
                        bounded.bind(prefix, namespace)
                    for triple in triples[:limit]:
                        bounded.add(triple)
                    data = bounded.serialize(format="turtle")
                return OntologySparqlResult(
                    source=source,
                    query_type=cast(OntologyQueryType, result.type),
                    data=data,
                    truncated=truncated,
                )

            return self._call("evaluate SPARQL query", evaluate)
