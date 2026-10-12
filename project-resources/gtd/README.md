# GTD ontology and independent Neo4j graph resources

Retrieved on 2026-10-12 for ontology-to-database mapping experiments.

## Downloaded files

- `ontology/gtdonto.ttl`: the public GTDOnto dataset exported from Reem Alfayez's TriplyDB account as Turtle. The download was gzip-compressed in transit and decompressed locally, then reformatted as compact Turtle with readable prefixes and grouped statements. RDF graph equivalence was verified: all 1,441 triples are unchanged.
- `ontology/triply-metadata.json`: metadata returned by the TriplyDB API at download time.
- `neo4j/1-load_gtdb_script.cql`: Rik Van Bruggen's original GTD Neo4j import script, preserved verbatim.
- `neo4j/2-query_gtdb.cql`: the original accompanying example queries, preserved verbatim.
- `neo4j/schema-inventory.json`: a local inventory of node labels, properties, import expression types, and directed relationships derived from the import script. This is not an author-published schema or a LinkML schema.
- `neo4j/schema.linkml.yaml`: a LinkML representation of that inventory, with 11 node classes, 49 properties, and 11 directed relationship patterns. Custom annotations preserve Neo4j names and directions. Unspecified property types remain unconstrained through `linkml:Any`; relationship slots permit zero or more targets without asserting verified cardinalities. No identifiers or uniqueness constraints are invented. Loaded with LinkML runtime 1.12.0 and checked for complete correspondence with the inventory.
- `neo4j/ontology-mappings.proposed.json`: the earlier alignment reference artifact. The same eight proposed alignments now live directly in `schema.linkml.yaml` using LinkML mapping fields and review annotations; the JSON file is not a runtime input. All remain local proposals, not author-published or verified mappings.
- `sources.json`: download URLs, the Gist revision, byte sizes, and SHA-256 checksums of the three source files. For the reformatted ontology, the original download size/hash and current local size/hash are both recorded.

## Ontology source and verification

- Public dataset: https://triplydb.com/ReemAlfayez/GTDOnto/
- Direct export: https://api.triplydb.com/datasets/ReemAlfayez/GTDOnto/download (request header: `Accept: text/turtle`; decompress gzip response)
- Metadata: https://api.triplydb.com/datasets/ReemAlfayez/GTDOnto
- Paper: https://doi.org/10.3390/bdcc7010024
- Zenodo record: https://zenodo.org/records/7034887

Zenodo restricts access to its files, but the public TriplyDB dataset provides a downloadable OWL ontology in Turtle. There is no need to request Zenodo access to use this public copy. Equivalence to the restricted Zenodo artifact has not been verified. If that exact artifact is needed, use the Zenodo access-request form; its stated condition refers to agreeing to START's GTD terms.

RDFLib successfully parsed the downloaded Turtle: 1,441 triples, 251 explicitly declared OWL classes, 19 explicitly declared object properties, and 57 explicitly declared datatype properties. The ontology IRI is `http://www.semanticweb.org/user/ontologies/2020/3/GTDB`. The public dataset description says it includes two example instances. The paper reports slightly different property counts (20 object properties and 58 data properties), so treat this as a specific public snapshot rather than assuming it is identical to every version described in the paper.

## Neo4j source and schema

Original Gist: https://gist.github.com/rvanbruggen/0a9f607b1b2647e6ea3b

Gist revision: `1ef6dc22a0e37fcc211571168c9ce23a0caa6754`.

The graph schema is expressed in the import script rather than supplied as a separate formal schema. Its labels are `Event`, `Group`, `AttackType`, `Target`, `TargetType`, `Weapon`, `Corporation`, `City`, `ProvState`, `Country`, and `Region`.

| Source label | Relationship | Target label |
| --- | --- | --- |
| Country | PART_OF | Region |
| ProvState | PART_OF | Country |
| City | PART_OF | ProvState |
| Target | IS_A | TargetType |
| Corporation | RELATED_TO | Target |
| Target | IS_FROM | Country |
| Event | EVENT_LOCATED_IN | City |
| Event | IS_OF_ATTACKTYPE | AttackType |
| Event | TARGETS | Target |
| Group | CARRIES_OUT | Event |
| Event | USED_WEAPON | Weapon |

The original scripts use legacy Neo4j syntax, including `using periodic commit`, `create index on`, and `toInt`, plus Neo4j-shell commands. They have not been executed or modernized. Their external CSV dependency was not downloaded. Property types in the inventory reflect the import expressions: several numeric-looking GTD fields remain strings because the script does not convert them. In this graph, `Weapon` represents weapon-type categories, not individual physical weapons.

## Mapping and usage boundaries

GTDOnto and this Neo4j model are independent representations of GTD. No verified alignment between them is supplied here. The derived LinkML schema describes the inventory's structure; it has not been validated against a live database. The proposed mappings embedded in the LinkML schema support service integration testing and require semantic review. Neo4j annotations are local conventions interpreted by `load_linkml_mappings()`, not built-in LinkML database operations. See `docs/ontology_service.md` for configuration and usage.

Source ownership and terms remain with the original authors/providers. The fetched TriplyDB metadata and Gist API response did not identify an explicit license; public download availability alone does not establish unrestricted redistribution rights. Consult the source pages and START's GTD terms for intended use: https://www.start.umd.edu/gtd/.
