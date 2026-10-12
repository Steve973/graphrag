# Ontology library responsibilities

Reviewed against installed RDFLib 7.6.0 and LinkML Runtime 1.12.0. This is a new
service: response behavior is chosen for useful agent tools, without a legacy
compatibility requirement.

| Operation | Implementation |
| --- | --- |
| Parse RDF and select triples | RDFLib `Graph.parse`, `objects`, `triples` and `triples_choices`. |
| Expand RDF identifiers | RDFLib namespace manager. |
| Search configured labels/synonyms and identifiers | Native bound SPARQL with `LCASE`/`CONTAINS`; exact matches rank first. |
| Execute and serialize ontology queries | RDFLib `prepareQuery`, `Graph.query`, JSON/Turtle serializers. |
| Inspect query algebra for external sources | RDFLib `traverse`; the application rejects FROM/SERVICE. |
| Resolve schema imports/inheritance | LinkML `SchemaView.all_schema`, `induced_class`, `class_induced_slots`. |
| Resolve schema namespaces/mapping types | LinkML `SchemaView.namespaces` and `get_mappings`. |
| Associate physical graph addresses with ontology concepts | Application LinkML adapter, prepared at load time. |
| Retrieve prepared schema associations | Application indexes; no schema scan or parsing per request. |
| Combine ontology meaning with graph representation | Application service. |
| Report ambiguous names and mapping uncertainty | Application service. |
| Bound prompt context and explain truncation | Application service and graph neighborhood budgets. |

Search no longer scans a custom entity cache or maintains Unicode casefold
matching. Native lowercase semantics are sufficient. Every configured label is
searchable, even when another language is selected for display. User text is
bound as a literal, so quotes and query-looking labels remain ordinary data.
There is no eagerly materialized copy of all entity metadata.

The mapping adapter still creates a scoped LinkML view for each induced class or
slot when calling `get_mappings()`. LinkML's global name lookup conflates reused
class-local slot names. Passing definition objects directly to the installed
cached method raises an unhashable-object error. The scoped view uses LinkML's
namespace map and default CURIE maps, and preserves those local identities.
Physical addresses, annotation validation, status and provenance belong to the
application rather than LinkML's generic mapping index.

A small bounded neighborhood traversal remains. RDFLib's native transitive
methods return reachable terms; the agent context needs original path edges,
blank nodes, both directions, and node/edge/depth limits. `Graph.cbd()` follows a
different traversal policy. The service applies metadata and literal text limits
consistently across providers and assembles context and schema associations.
Hierarchy lookups use neighborhood direction and predicate options; named agent
tools can supply those options without separate service methods.

SELECT output uses an outer native RDFLib `Slice` with one lookahead row before
serialization. This touches query algebra and needs verification when upgrading
RDFLib. Ordering, aggregation and graph queries can still process the full graph;
output limits are not execution-time or memory guarantees.

No companion library or reasoning engine is required for these agent tools.
Assertions are returned as loaded, without OWL entailment or automatic alignment
based on matching ontology and database names.

Primary references:

- [LinkML SchemaView](https://linkml.io/linkml/developers/schemaview.html)
- [RDFLib Graph](https://rdflib.readthedocs.io/en/stable/apidocs/rdflib.graph/)
- [RDFLib SPARQL algebra traversal](https://rdflib.readthedocs.io/en/stable/apidocs/rdflib.plugins.sparql.algebra/)
- [RDFLib transitive traversal](https://rdflib.readthedocs.io/en/stable/apidocs/examples.transitive/)

Verification covers meaning plus graph bindings in a single tool response,
reverse lookup, ambiguity/missing concepts, native search semantics and literal
query text, local schema-slot collisions and inherited definitions, prepared
index lookup without resource parsing/scanning, native provider context assembly,
and synchronous/asynchronous LangChain tool execution.
