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

## Build the normalized GTD research graph

The active model is implemented in `src/gtd/gtd_prepare.py` and
`src/gtd/gtd_ingest.py`. It preserves one incident per source event ID.
Targets, weapon uses, perpetrator attributions, and claims retain their source
slots. Attribution and claim are separate, and incident location and target
nationality have distinct relationships. An exact date exists only where the
source supplies a day, month, and year. The legacy LinkML inventory above
describes the older Gist model.

The local build uses Docker Compose and pins Neo4j Community 2026.10.2.
Use a valid GTD CSV exported as UTF-8 with quoted fields and intact IDs.
For a Windows-1252 CSV, add `--encoding cp1252`. As an alternative, export
the workbook's Data sheet with openpyxl in read-only mode and Python's
`csv.writer`, using `sheet.values` and UTF-8.

From the repository root, with the project environment activated:

```bash
export GTD_PREPARED_DIR="$PWD/build/gtd/prepared"
graphrag-seed-gtd --csv /path/to/gtd.csv --prepare-only --import-dir "$GTD_PREPARED_DIR"
chmod a+rx "$GTD_PREPARED_DIR"
docker compose -f project-resources/gtd/neo4j/compose.yml up -d --wait
graphrag-seed-gtd --load-prepared --uri bolt://127.0.0.1:17687 \
  --import-dir "$GTD_PREPARED_DIR" --import-uri file:///gtd --batch-size 3000
```

The Neo4j ports are loopback-only. Set `GTD_NEO4J_AUTH=neo4j/<password>`,
`NEO4J_PASSWORD`, and `GTD_NEO4J_PASSWORD` consistently if enabling auth.
Range, spatial, full-text and lookup indexes support date, location, casualty
counts, names, and incident summaries. Unique keys back the main graph joins.

The vector helper needs `numpy`, `tokenizers` and `safetensors`. Download
`model.safetensors` and `tokenizer.json` from the `0_StaticEmbedding` directory
in the pinned model revision below into the same local directory.
Both indexing and query encoding use its first 256 Matryoshka dimensions
with cosine similarity.

[Pinned model files](https://huggingface.co/sentence-transformers/static-similarity-mrl-multilingual-v1/tree/b68f4122911bcffcd6e1f695f2d99cd6788972d8/0_StaticEmbedding)

```bash
python -m gtd.gtd_embeddings --model-dir /path/to/model build \
  --ontology project-resources/gtd/ontology/gtdonto.ttl \
  --schema-output build/gtd/schema.json
python -m gtd.gtd_embeddings --model-dir /path/to/model search "reported fatalities"
```

`gtd_schema_vector` searches declared ontology terms and observed database labels,
properties and relationship patterns. `gtd_summary_vector` searches incident
summaries with `--scope summary`. The schema export includes the observed property
types, directed relationship endpoints, indexes, and constraints. The ontology
and physical model are distinct. The catalog includes explicit links for selected
label mappings and leaves other ontology terms unbound. Its results are candidates
for checking against records. The vector score does not establish a binding.

Stop the service before dumping. Load the dump into a fresh volume by selecting
a different Compose project name. The restore example uses separate loopback
ports so it can run alongside the source container.

```bash
gtd_compose=project-resources/gtd/neo4j/compose.yml
gtd_build_dir="$PWD/build/gtd"
docker compose -f "$gtd_compose" stop neo4j
docker compose -f "$gtd_compose" run --rm --no-deps -T \
  --entrypoint /var/lib/neo4j/bin/neo4j-admin neo4j \
  database dump neo4j --to-stdout > "$gtd_build_dir/neo4j.dump"
GTD_HTTP_PORT=27474 GTD_BOLT_PORT=27687 docker compose -p graphrag-gtd-restore \
  -f "$gtd_compose" run --rm --no-deps -T \
  --entrypoint /var/lib/neo4j/bin/neo4j-admin neo4j \
  database load neo4j --from-stdin < "$gtd_build_dir/neo4j.dump"
GTD_HTTP_PORT=27474 GTD_BOLT_PORT=27687 docker compose -p graphrag-gtd-restore \
  -f "$gtd_compose" up -d --wait
```

## Check a question before planning

With the GTD container running and the pinned model files under
`build/gtd/model`, submit a question from the repository root. The parser and
reviewer use the repo's authenticated Codex CLI backend. The local embedding
helper needs the same optional packages as the index builder, available with
`uv sync --group gtd`.

```bash
.venv/bin/python -m gtd.gtd_grounding 'How many incidents occurred in Spain after 2010?'
```

The JSON includes the original question and source-quoted breakdown, a separate
semantic review, lexical and vector schema candidates for each concept, and
read-only data checks. The corpus context resolves generic references to GTD
incidents without providing physical schema to the parser. A review issue or
unresolved meaning stops before querying the database. To use a different
Codex model for review, pass `--review-model MODEL`.

Data checks cover eight mapping types across four distinctions. They compare
incident country with target nationality, fatalities with injuries, incident
year with complete date, and reported attribution with claim of responsibility.
A `contrast_observed` result includes a record on which the two mappings differ.
An `inconclusive` result means the bounded probe returned no distinguishing
record. Unsupported mappings remain candidates and review approval is not a
guarantee that the interpretation is complete.

To run the real-database checks with fixture parses and no model provider calls:

```bash
GTD_LIVE_TEST=1 .venv/bin/python -m pytest tests/gtd/test_gtd_grounding_live.py -q
```

## Compare pretrained AMR with the existing semantic parser

The comparison uses the published amrlib BART-base checkpoint
[`parse_xfm_bart_base-v0_1_0`](https://github.com/bjascob/amrlib-models/releases/tag/parse_xfm_bart_base-v0_1_0).
Install the optional AMR runtime in its own directory. This setup uses CPU
PyTorch and leaves the application environment's parser dependencies unchanged.

```bash
mkdir -p build/gtd/amr
uv pip install --target build/gtd/amr/runtime --index https://download.pytorch.org/whl/cpu 'torch==2.8.0+cpu'
uv pip install --target build/gtd/amr/runtime amrlib==0.8.0 transformers==4.53.3 penman==1.3.1 unidecode==1.4.0
curl -fL https://github.com/bjascob/amrlib-models/releases/download/parse_xfm_bart_base-v0_1_0/model_parse_xfm_bart_base-v0_1_0.tar.gz -o build/gtd/amr/checkpoint.tar.gz
tar -xzf build/gtd/amr/checkpoint.tar.gz -C build/gtd/amr
HF_HOME="$PWD/build/gtd/amr/hf" OMP_NUM_THREADS=4 PYTHONPATH="$PWD/build/gtd/amr/runtime:$PWD/src" \
  .venv/bin/python -m gtd.gtd_compare 'How many incidents occurred in Spain after 2010?' \
  --amr-model build/gtd/amr/model_parse_xfm_bart_base-v0_1_0 \
  --baseline build/gtd/grounding-live-example.json --coverage > build/gtd/amr-comparison.json
```

Omit `--baseline` to run a new Codex parse for the same question. Omit
`--coverage` to inspect parsing and retrieval alone. `--review` adds a
separate semantic review without building criteria.

AMR output preserves the original PENMAN, root, concept nodes, directed roles,
attributes, and any exact literal occurrences found in the question. Codex
output preserves the extracted concept and meaning fields. Both carry lookup
text and independent ranked matches for ontology concepts, physical schema
items, and indexed incident summaries, plus graph-name lookup. The ontology
and schema scores are computed separately from their stored vectors so hits in
one source cannot crowd out the other.

With `--coverage`, a clean semantic review allows criteria and atomic
assertions to be proposed. A separate pass checks question-to-criteria and
criterion-to-assertions coverage, including protection against added
requirements. A rejected draft gets one revision with the review findings
and is reviewed again. An accepted coverage draft gets the same per-item retrieval
for criteria and atomic assertions. Candidate matches give later stages
possible bindings. They do not establish logical coverage or evidence support.

### Test AMR followed by LLM repair

Add `--hybrid` to the comparison command. The hybrid starts from the raw AMR
graph and reviews it against the original wording. It retains an explicit
correction log with source quotes and AMR item references, and emits a
normalized breakdown in the same format as the Codex-only path. A fresh
review receives the repaired representation without the correction log.
Only a reviewed hybrid without outstanding issues or ambiguities proceeds
to Neo4j grounding. The vectors are deliberately absent from the repair
prompt so candidate mappings cannot steer the interpretation.

```bash
HF_HOME="$PWD/build/gtd/amr/hf" OMP_NUM_THREADS=4 PYTHONPATH="$PWD/build/gtd/amr/runtime:$PWD/src" \
  .venv/bin/python -m gtd.gtd_compare 'How many incidents occurred in Spain in or after 2010?' \
  --amr-model build/gtd/amr/model_parse_xfm_bart_base-v0_1_0 --hybrid
```

Add `--no-grounding` to evaluate semantics without a Neo4j connection.

### Review and patch an AMR draft

The patch experiment asks the model to accept the draft, provide a small edit
to specific AMR triples, or request a full breakdown. It validates the patch
and re-reviews the resulting graph against the question. Unsafe or inadequate
patches fall back to the full structured breakdown and its review. The output
includes each stage's elapsed time, the route, and whether the result passed.

```bash
HF_HUB_OFFLINE=1 HF_HOME="$PWD/build/gtd/amr/hf" OMP_NUM_THREADS=4 \
  PYTHONPATH="$PWD/build/gtd/amr/runtime:$PWD/src" \
  .venv/bin/python -m gtd.gtd_amr_patch 'How many incidents occurred in Spain in or after 2010?' \
  --amr-model build/gtd/amr/model_parse_xfm_bart_base-v0_1_0
```
