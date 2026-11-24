# Cypher redaction experiment

`CypherRedactionService` takes one read query and returns rewritten Cypher plus the
number of inserted checks. Graphglot parses the Neo4j dialect. The rewriter uses
AST source spans so comments, parameters, and syntax such as legacy variable-length
relationships retain their original spelling.

```bash
python -m graphrag.experiments.cypher_redaction --procedure custom.redactionAllowed <<'CYPHER'
MATCH (a:Author)-[:WROTE]->(p:Publication)
OPTIONAL MATCH (p)-[:CITES*1..3]->(c:Publication)
WHERE c.year >= $since
RETURN a.name, p.title, collect(c.title)
CYPHER
```

```python
from graphrag.experiments.cypher_redaction import CypherRedactionService

service = CypherRedactionService("custom.redactionAllowed")
result = service.rewrite("MATCH (n:Publication) RETURN count(n)")
records = session.run(
    result.cypher,
    {"redaction_context": user_entitlements},
)
```

The caller binds the entitlement list from trusted application state. The
deployed read-only procedure yields a Boolean decision for each candidate.
A missing row, false, or null decision discards the candidate.

To use your deployed procedure, supply its name, its positional arguments, and
the name of its Boolean result field. For example, if it takes entitlements
first and candidate nodes second, configure it this way:

```python
service = CypherRedactionService(
    "apoc.company.checkAccess",
    context_parameter="user_entitlements",
    argument_order=("entitlements", "nodes"),
    decision_field="permitted",
)
rewritten = service.rewrite(cypher)
records = session.run(
    rewritten.cypher,
    {**query_parameters, "user_entitlements": user_entitlements},
)
```

The argument names select the generated expressions. `nodes` is the list of
candidate nodes, `relationships` is the list of candidate relationships, and
`entitlements` is the bound parameter containing the user's entitlement list.
Use the order in the deployed signature and omit unused inputs. The default is
`("nodes", "relationships", "entitlements")` with `YIELD allowed`.
The CLI accepts the same settings via `--procedure`, `--arguments`,
`--entitlement-parameter`, and `--decision-field`.

A match checks each path's nodes and relationships, including anonymous intermediates.
A named single-node match passes that node directly. The call runs in an `EXISTS`
predicate on the matching clause, so aggregation receives filtered rows and
`OPTIONAL MATCH` can still emit its null row. The rewriter also handles recognized
pattern predicates, pattern comprehensions, nested `MATCH` clauses and `UNION`
branches. Explicitly yielded entities from allowlisted APOC path expansion and Neo4j
full-text/vector procedures are checked after the procedure returns. These procedures
rank or limit candidates before the check, which can reduce the number of visible
results. `OPTIONAL CALL` uses a scoped subquery and requires Neo4j 5.24 or later.

Run the application's read-only guard before passing a query to the rewriter, or
pass it as `query_guard=validate_read_only` when constructing the service. The
callback receives the original Cypher before parsing. It returns `None` on
success and raises on rejection. The rewriter propagates that exception.
Reads the rewriter cannot cover raise `UnsupportedCypher`. Examples include unknown
procedures and functions, selective shortest-path patterns, Cypher constructs that
Graphglot 0.14.3 cannot parse faithfully (including `COUNT { ... }` and
`COLLECT { ... }`), and wildcard projections when a temporary match path could
change the projected variables. This experiment filters graph entities and rows.
Property-level masking and production authorization are outside its scope.
