# Ontology meaning and graph schema tools

The service helps an agent understand what a concept means and how the graph
represents it. It can be used alongside graph query tools in a GraphRAG workflow
or a LangChain research agent.

The callable service API uses `resolve(term)` to return resolved, ambiguous or
missing results, `get_entity(identifier)` to look up a known identifier, and
`describe([term, ...])` to combine ontology meaning with database schema mappings.
Use `neighborhood(identifiers, direction=..., predicates=..., limits=...)` for
traversal. Named research-agent tools can call this method with fixed options:
ancestors follow outgoing `rdfs:subClassOf` statements, descendants follow incoming
ones, and immediate relationships use `OntologyContextLimits(max_depth=1)`.

## Agent tools

With a schema configured, `create_ontology_tools(service)` returns six tools:

| Tool | Use |
| --- | --- |
| `ontology_search(query, limit=10, exact=False)` | Find concepts by label, synonym, IRI or CURIE. |
| `ontology_context(terms, direction="both", predicates=None, max_depth=2, max_entities=30, max_relationships=60)` | Get definitions, selected ontology statements and corresponding graph schema bindings together. |
| `ontology_relationships(term, direction="both", predicates=None)` | Inspect immediate statements, such as a property's domain and range, together with schema mappings. |
| `ontology_ancestors(term, max_depth=4)` | Inspect stated superclasses and their schema mappings. |
| `ontology_descendants(term, max_depth=4)` | Inspect stated subclasses and their schema mappings. |
| `ontology_database_element(element_name, property_name=None, relationship_type=None)` | Start from a graph entity, property or relationship and find its ontology meaning. |

The context tool takes a list of names or identifiers. It returns one consistent
payload containing `ontology`, `mappings`, `schema_sources`,
`unmapped_ontology_uris` and `warnings`. Each mapping identifies the ontology
concept and its database elements. Graph bindings include entity labels,
properties, relationship types, endpoints and directions; native LinkML
class/slot definitions carry schema details such as ranges and descriptions.
The three named traversal tools return this same payload. They select traversal
options in the tool handlers without adding convenience methods to the service.

Use the default context for an initial meaning/schema lookup. For a focused
follow-up, select direction or predicate identifiers, or use a named traversal
tool. When the response reports truncation, increase the relevant depth or
resource/statement limit, or narrow the terms and predicates. `max_depth=0`
returns the selected concepts and mappings without following relationships.
Ancestor and descendant tools follow original `rdfs:subClassOf` statements;
they do not compute OWL entailment or prove how database records are classified.
Anonymous restrictions can require a deeper, unfiltered context request.

For example, an agent can search for “Incident”, request context for the selected
IRI, learn that it is represented by an `Event` node, and inspect the mapped
properties and relationships before constructing a graph query. Starting from
`Event.year`, the reverse tool supplies its explicitly mapped ontology meaning.

Ambiguous names return candidates. The agent selects an identifier and calls
again. Unknown names and absent mappings stay explicit. Proposed or asserted
mappings are marked as unverified. A mapping establishes an explicit association;
it does not by itself prove OWL equivalence or validate database contents.

Without a schema, search, context and the named traversal tools remain available,
and context reports that
no database schema mappings are configured. Add `include_sparql=True` when the
agent needs an additional tool for precise SELECT, ASK, CONSTRUCT or DESCRIBE questions
against the ontology. SPARQL is optional in the default tool set.
These tools consult the loaded ontology and schema mappings; they do not query
database records.

## Loading and registration

```python
from pathlib import Path

from graphrag.config.ontology_config import OntologySettings
from graphrag.service.ontology_service import OntologyService, create_ontology_tools

ontology = OntologyService(OntologySettings(
    path=Path("ontology.ttl"),
    schema_path=Path("schema.linkml.yaml"),
))
ontology.initialize()  # During application startup.
ontology_tools = create_ontology_tools(ontology)

# Register these alongside the agent's graph/research tools.
# model.bind_tools(ontology_tools) exposes their schemas to a LangChain model.
# Execute returned calls with the same tool objects, or a LangGraph ToolNode.
tools_by_name = {tool.name: tool for tool in ontology_tools}
payload = tools_by_name["ontology_context"].invoke({"terms": ["Incident"]})
superclasses = tools_by_name["ontology_ancestors"].invoke({"term": "Incident"})
# payload = await tools_by_name["ontology_context"].ainvoke({"terms": ["Incident"]})
```

This factory provides standard LangChain `StructuredTool` objects; it does not
create an agent or automatically register them with an existing workflow.
`ainvoke` runs synchronous handlers in a worker thread. Validation and lookup
errors become tool observations that the agent can respond to.

Initialization loads the ontology snapshot and the optional LinkML schema once.
LinkML resolves schema imports and inherited class/slot definitions. The adapter
extracts explicit ontology alignments and physical bindings, then prepares two
indexes: ontology URI to mapping records, and database address to mapping records.
Requests use these indexes. They never reparse or scan the database schema.
Only ontology context and the selected response are assembled at request time.
Resource changes require a new service instance/application restart.

## Schema bindings

Use LinkML `class_uri`, `slot_uri`, `exact_mappings`, `close_mappings`,
`related_mappings`, `broad_mappings`, `narrow_mappings` or `mappings` for explicit
ontology associations. Generated default schema URIs do not assert an alignment.
Reused class-local slot names remain distinct.

Physical graph bindings are annotations:

- Classes: `graph_label`.
- Property slots: `graph_property`.
- Relationship slots: `graph_relationship`, `graph_direction` (`incoming` or
  `outgoing`), `graph_source_label`, and `graph_target_label`.
- Optional schema annotation: `database_backend`.
- Optional mapping metadata: `mapping_status`, `mapping_provenance`,
  `mapping_note`, and `mapping_confidence`.

The adapter also accepts the `neo4j_` spellings used by the supplied GTD schema.
Conflicting bindings or inconsistent relationship endpoints fail loading.
Multiple concepts or schema elements may share mappings; both indexes preserve
all explicit associations.

## Library and service responsibilities

RDFLib handles RDF parsing, namespace expansion, triple retrieval, SPARQL search,
query evaluation and serialization. Search uses native `LCASE`/`CONTAINS` over
all configured labels and synonyms, with exact matches first. Preferred language
and predicate order choose the display label and definition, not search scope.

The service assembles meaning plus graph mappings, reports ambiguity, and limits
context size for the agent. The default context follows both directions for two
hops, with at most 30 resources and 60 triples. Original blank-node OWL
restrictions and literal values remain visible; no invented class-to-class edges
or OWL inference are added. Truncation is reported. Application callers can use
`describe(..., limits=..., direction=..., predicates=...)` for more control;
the agent context tool exposes direction, predicates and traversal budgets while
retaining the default metadata text limits.

`OntologyProvider` supplies initialization, entity lookup, search, resolution,
bounded neighborhood retrieval and SPARQL. The RDFLib provider reads resources
through `OntologyResources` and the shared fsspec `ResourceLoader`. Ontology
imports use explicitly configured locations; unavailable imports warn or fail
according to `unresolved_imports`. A native provider can supply the same primitives
without exporting RDF. `MobiOntologyProvider` currently implements committed
entity reads and identifier resolution; the remaining operations are deferred.

LinkML is a load-time adapter, not a request-time provider. `SchemaMappings` is
plain prepared data. The service can also accept an injected ontology provider
and prepared mappings from another database-schema adapter.

SPARQL queries are confined to the loaded snapshot: updates, `FROM` and `SERVICE`
are excluded. Output limits bound returned context/rows/triples, not parsing or
query execution cost. See [the library audit](ontology_library_audit.md) for the
remaining custom operations and why they belong in this application.

## Initial native Mobi support

`MobiOntologyProvider` reads entity statements using the ontology REST API and
converts expanded JSON-LD directly into our entity model. It does not load an
ontology export or use RDFLib. It supports full IRIs, explicitly configured
CURIEs, annotation predicates, preferred-language selection, and resolution of
known identifiers. Labels/aliases are not yet resolved remotely.

Supply the REST base URL (typically `https://host/mobirest`), ontology record IRI,
production branch IRI, and a specific committed revision IRI. Initialization
freezes this supplied scope; it does not connect to the server or discover the
latest production version. Server access is checked on the first entity read.
All implemented requests are GETs and explicitly set
`applyInProgressCommit=false`. Moving selectors such as `head` are rejected.
Authentication can be provided through a caller-owned, authenticated
`httpx.Client`; login and deployment-specific authentication remain deferred.
The provider's `close()` releases only an HTTP client it created itself.

Imports are excluded by default while production import-version selection is
unimplemented. `include_imports=True` explicitly opts into Mobi's import resolution
and returns a warning that import revisions and failures are unverified. Strict
import validation is unsupported. The failed-imports endpoint is deliberately
not used because the reviewed implementation applies in-progress edits internally.

| Implemented | Deferred until deployment/API verification |
| --- | --- |
| Entity metadata retrieval and identifier resolution | Exact label/alias search and resolution |
| Explicit branch/commit scope and read-only HTTP requests | Authentication/login and automatic production-version selection |
| Expanded JSON-LD conversion and domain errors | Bounded neighborhood traversal, blank-node identity across requests, and SPARQL validation/execution |

Deferred methods raise `OntologyUnsupportedError` without sending requests.
Consequently this provider is not yet a complete backend for the agent tools:
search, combined context, and traversal tools need the deferred methods.
HTTP authentication, authorization, missing-resource, redirect and server errors
are reported as query errors rather than silently interpreted as absent concepts.
Server version metadata is caller-supplied or reported as `unknown`.

Endpoint behavior was reviewed against the
[Mobi ontology API source](https://github.com/inovexcorp/mobi/blob/master/com.mobi.ontology.rest/src/main/java/com/mobi/ontology/rest/OntologyRest.java).
Mock-HTTP tests verify the local implementation; a live deployment has not yet
been tested.
