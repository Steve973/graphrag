# Ontology service

`OntologyService` reads a configured native OWL/RDF file into an RDFLib 7.6.0
`Graph`. It adds exact term resolution, bounded context and question snapshots.
It does not project OWL restrictions into named edges, infer triples, or map
ontology concepts to database labels/properties.

## Configuration and question lifetime

```python
from graphrag.config.ontology_config import OntologySettings
from graphrag.service.ontology_service import OntologyService

reader = OntologyService(OntologySettings(path="/ontologies/fl.owl"))
reader.initialize()  # Optional startup validation; otherwise loading is lazy.

# Once, at the beginning of a NEW question:
reader = reader.for_question()
question_ontology = reader

# Retain question_ontology for all stages and any continuation of that question.
```

The existing data profile accepts `ontology=OntologySettings(...)`, and
`OntologyService.from_profile(profile)` uses it. For environment configuration:

```text
GRAPH_RAG_DATA_PROFILE__ONTOLOGY__PATH=/ontologies/fl.owl
GRAPH_RAG_DATA_PROFILE__ONTOLOGY__FORMAT=xml
```

RDFLib's `guess_format` selects the parser from the suffix (`.owl` means
RDF/XML); `format` can explicitly select an installed RDFLib parser. OWL/XML,
Functional Syntax and Manchester Syntax need an RDF/XML or Turtle export.
Only imports reachable through configured `imports={import_iri: local_path}`
are loaded. Unmapped imports warn, or fail with `unresolved_imports="error"`.
Root/import SHA-256 hashes identify the loaded bytes. At a new question boundary,
resolved path, inode, size and mtime decide whether to create a new snapshot.
An active instance never reloads. Changes preserving all those stat fields
require explicit new construction. Retain/cache the returned instance yourself.

## Useful calls for workflow stages

```python
from graphrag.model.ontology import OntologyContextLimits

# Investigate terms found in a question or retrieved data.
hits = question_ontology.search("organization", limit=10)
resolution = question_ontology.resolve("Institution")

# Prompt-ready context for planning, query construction or interpretation.
context = question_ontology.get_context(
    ["Organization", "Person"],
    limits=OntologyContextLimits(max_depth=2, max_entities=30, max_relationships=60),
)
context_payload = context.model_dump(mode="json")
context_text = context.to_structured_text()

# Focused follow-up access, using identifiers returned by resolution/search.
entity = question_ontology.resolve_entity("Organization")
parents = question_ontology.ancestors(entity.identifier)
children = question_ontology.descendants(entity.identifier)
relationships = question_ontology.relationships(entity.identifier)
```

`search` matches literal substrings in full IRIs, the selected label and aliases,
with exact matches first. `resolve` prefers an exact IRI/bound CURIE, then exact
case-insensitive labels/aliases; ambiguity and missing terms remain explicit.
`resolve_entity` raises a domain exception unless there is one unique match.
Named subjects are searchable. Referenced IRIs can also be fetched directly;
reading one does not silently add it to the search population.

Returned identifiers are full IRIs. RDFLib's namespace manager expands input
CURIEs; `prefixes` can add or override bindings. RDFLib may replace a previous
prefix for the same namespace, so prefer full IRIs for stable identifiers or
explicit `PREFIX` declarations in queries.

Labels, definitions and aliases come from **configured annotation predicates**,
not from guessed ontology semantics. Defaults are `rdfs:label`/`skos:prefLabel`,
`IAO:0000115`/`skos:definition`, and `skos:altLabel`/`oboInOwl:hasExactSynonym`.
Confirm these against the FL file, and override them when needed. Broad, narrow
and related synonyms are not exact-resolution defaults. Predicate priority
precedes preferred-language selection (`language="en"` by default); fallback is
untagged text, then other languages in deterministic order. Entity `types`
contains original named `rdf:type` values, including individual classifications.

Context defaults to two outgoing hops. It returns original triples, including
annotations, literal values and anonymous OWL expressions. For example, an
existential restriction remains `class -> rdfs:subClassOf -> blank node`, with
`owl:onProperty` and `owl:someValuesFrom` on that node. It is not an asserted
class-to-class edge. Blank-node IDs are local to a loaded snapshot.

Limits bound traversal depth, named/anonymous resource count, triple count,
candidates and metadata/literal text lengths. Literals are terminal values;
`entities` contains metadata for named nodes only. Responses report truncation.
Predicate filters apply at every hop; to read details of a restriction, use an
unfiltered context or a targeted SPARQL query. Hierarchy helpers default to
`rdfs:subClassOf` and four hops; these are bounded traversal, not OWL reasoning.

## SPARQL for precise follow-up questions

```python
result = question_ontology.query_sparql("""
PREFIX owl: <http://www.w3.org/2002/07/owl#>
SELECT ?class ?restriction ?property ?filler WHERE {
  ?class <http://www.w3.org/2000/01/rdf-schema#subClassOf> ?restriction .
  ?restriction owl:onProperty ?property ; owl:someValuesFrom ?filler .
}
ORDER BY ?class ?property ?filler
LIMIT 20
""", limit=20)
result_payload = result.model_dump(mode="json")
```

Native SELECT, ASK, CONSTRUCT and DESCRIBE are supported. `data` is RDFLib's
standard SPARQL JSON for SELECT/ASK (including RDF term kinds, language and
datatype), or Turtle for graph results. The wrapper supplies source provenance,
query type and truncation. Graph results truncated by the triple bound may
contain incomplete expressions; request more context before interpreting them.
Use `ORDER BY` when SELECT row order matters. Namespace bindings from the loaded
graph are available, or supply explicit `PREFIX` declarations.

The query operation targets the configured snapshot. FROM and SERVICE are
excluded because RDFLib can load/query additional local or remote sources
through them; these are RDFLib capabilities, not missing features. Updates are
not exposed. Invalid queries raise `OntologyQueryError`; load failures raise
`OntologyLoadError`, and unsupported external-source queries raise
`OntologyUnsupportedError`. Underlying exceptions remain chained.

Output limits do not impose parsing/query execution time or memory budgets.
SPARQL values are not text-truncated. SELECT bindings and graph results may be
materialized before output limiting. Run synchronous service calls in a worker
thread in an async application; use a separately controlled worker process if a
hard execution budget is required. Choose parser formats deliberately: plugins
such as JSON-LD may resolve external resources while parsing.

## LangChain agent tools

`create_ontology_tools` in the service module returns three standard LangChain
`StructuredTool` objects: `ontology_search`, `ontology_context`, and
`ontology_sparql`. Supply that list to a plain agent or research agent's tool
collection, alongside its other tools. The factory uses the existing
`langchain-core` dependency; it has no LiteLLM adapter.

```python
from graphrag.service.ontology_service import create_ontology_tools

# Once, at the beginning of a new question:
reader = reader.for_question()
ontology_tools = create_ontology_tools(reader)

# Add ontology_tools to your LangChain agent's tools argument.
# Its existing model and agent configuration remain under caller control.

# Direct calls also work:
context_tool = next(tool for tool in ontology_tools if tool.name == "ontology_context")
context_payload = context_tool.invoke({"terms": ["Organization", "Person"]})

# In an async application:
# context_payload = await context_tool.ainvoke({"terms": ["Organization"]})
```

Tools capture the supplied instance and never call `for_question` themselves.
Retain them throughout the question, including continuations. Build new tools
with the newly selected snapshot for the next question. LangChain's native
async invocation runs the synchronous handlers in an executor thread.

Input schemas carry term/row bounds, directions, predicate filters and the
existing context limits. Successful calls return the service's JSON-compatible
payload unchanged, preserving ambiguity, provenance and truncation. Start with
search or context; use SPARQL for precise follow-up questions. Missing and
ambiguous terms are successful observations with explicit resolution statuses,
not invented matches. Validation failures and ontology exceptions become
LangChain error observations, allowing the agent to revise its arguments.
Agent-style calls return `ToolMessage` objects with success/error status;
direct `invoke` returns a dictionary on success and an error string on failure.

The factory is verified against installed `langchain-core==1.4.9` and its
`StructuredTool.from_function` API; see the
[official StructuredTool reference](https://reference.langchain.com/python/langchain-core/tools/structured/StructuredTool).

The repository's own workflow executes tools through `GraphProvider` and its
`AvailableTool` catalog. To use these tools there, advertise their names,
descriptions and schemas in that catalog and route requests to the question's
retained tool collection, then retain results for the relevant stage prompts.
The factory does not change that workflow dispatch. A resumed workflow must use
the same snapshot; process-restart persistence of snapshots is not implemented.
Database-to-ontology mappings remain a separate input when constructing queries
against the actual data store.

No extra RDFLib ecosystem dependency is needed for these operations. Core graph,
namespace, parser and serializer APIs replace the custom wrapper. `infixowl` is
an OWL editing convenience; its constructors/accessors can modify graphs.
pyLODE generates documentation, Prez provides a separate linked-data API, and
OWL-RL/pySHACL address inference/validation. None reduces this local access
service enough to justify another dependency at this stage.

API verification used the installed 7.6.0 package source and the
[official graph API](https://rdflib.readthedocs.io/en/7.6.0/apidocs/rdflib.graph/),
[namespace API](https://rdflib.readthedocs.io/en/7.6.0/apidocs/rdflib.namespace/)
and [RDFLib ecosystem repositories](https://github.com/orgs/RDFLib/repositories?type=all).
