import pytest
from graphglot import ast
from graphglot.ast.cypher import CypherPatternComprehension
from graphglot.dialect.neo4j import Neo4j

from graphrag.experiments.cypher_redaction import CypherRedactionService, UnsupportedCypher


@pytest.fixture
def service():
    return CypherRedactionService("custom.redactionAllowed")


@pytest.mark.parametrize("relationship", ["-[:WROTE*1..3]->", "-[:WROTE]->{1,3}"])
def test_rewrites_variable_length_traversal_before_aggregation(service, relationship):
    pattern = f"(a:Author){relationship}(:Publication)"
    result = service.rewrite(
        f"MATCH{pattern} // preserve me\n"
        "RETURN a, count(*)"
    )

    assert result.checks_inserted == 1
    assert result.cypher.startswith(f"MATCH _redaction_path_0 = {pattern}")
    assert "nodes(_redaction_path_0), relationships(_redaction_path_0)" in result.cypher
    assert result.cypher.endswith("// preserve me\nRETURN a, count(*)")
    Neo4j().parse(result.cypher)


def test_filters_all_paths_and_keeps_optional_predicate_local(service):
    result = service.rewrite(
        "MATCH (a), p=(a)-->(b) "
        "OPTIONAL MATCH (b)-->(c) WHERE c.x = 1 OR c.y = 2 RETURN c"
    )

    tree, = Neo4j().parse(result.cypher)
    required, optional = list(tree.find_all(ast.GraphPattern, bfs=False))
    assert result.checks_inserted == 3
    assert len(list(required.find_all(ast.NamedProcedureCall))) == 2
    assert len(list(optional.find_all(ast.NamedProcedureCall))) == 1
    assert "nodes(`p`), relationships(`p`)" in result.cypher
    assert " AND ( c.x = 1 OR c.y = 2) RETURN c" in result.cypher


def test_nested_and_implicit_reads_get_their_own_checks(service):
    result = service.rewrite(
        "MATCH (n) WHERE NOT(n)-->() OR EXISTS { (n)-->() WHERE n.x = 1 } "
        "RETURN [(n)-->(m) | m] AS peers"
    )

    tree, = Neo4j().parse(result.cypher)
    assert result.checks_inserted == 4
    assert len(list(tree.find_all(ast.NamedProcedureCall))) == 4
    comprehension = tree.find_first(CypherPatternComprehension)
    assert comprehension is not None
    assert comprehension.find_first(ast.NamedProcedureCall) is not None
    assert "NOT EXISTS { MATCH" in result.cypher


def test_preserves_unaliased_comprehension_column_name(service):
    result = service.rewrite("MATCH (n) RETURN [(n)-->(m) | m]")

    assert result.cypher.endswith("AS `[(n)-->(m) | m]`")
    Neo4j().parse(result.cypher)


def test_checks_each_union_branch_and_call_subquery(service):
    result = service.rewrite(
        "MATCH (n) CALL (n) { MATCH (n)-->(m) RETURN m } RETURN m "
        "UNION MATCH (m) RETURN m"
    )

    assert result.checks_inserted == 3
    tree, = Neo4j().parse(result.cypher)
    assert len(list(tree.find_all(ast.NamedProcedureCall))) == 3


@pytest.mark.parametrize("depth", [2, 3, 4])
@pytest.mark.parametrize("subquery", ["exists", "call"])
def test_checks_the_match_at_every_subquery_level(service, depth, subquery):
    nested = ""
    for level in range(depth, 0, -1):
        pattern = f"MATCH p{level} = (n{level - 1})-[:CITES]->(n{level})"
        if subquery == "exists":
            nested = f"{pattern} WHERE EXISTS {{ {nested} }}" if nested else pattern
        else:
            nested = (
                f"CALL (n{level - 1}) {{ {pattern} {nested} RETURN n{level} AS child{level} }}"
            )
    if subquery == "exists":
        query = f"MATCH (n0) WHERE EXISTS {{ {nested} }} RETURN n0"
    else:
        query = f"MATCH (n0) {nested} RETURN n0, child1"

    result = service.rewrite(query)

    tree, = Neo4j().parse(result.cypher)
    assert result.checks_inserted == depth + 1
    patterns = list(tree.find_all(ast.GraphPattern, bfs=False))
    assert len(patterns) == depth + 1
    expected_arguments = ["[`n0`], []"] + [
        f"nodes(`p{level}`), relationships(`p{level}`)" for level in range(1, depth + 1)
    ]
    for pattern, arguments in zip(patterns, expected_arguments, strict=True):
        where = pattern.graph_pattern_where_clause
        assert where is not None and where.source_span is not None
        start, end = where.source_span
        assert result.cypher[start:end].startswith(
            f"WHERE EXISTS {{ CALL custom.redactionAllowed({arguments}, $redaction_context)"
        )


def test_checks_index_lookup_traversals_and_union_in_one_query(service):
    result = service.rewrite(
        "CALL db.index.fulltext.queryNodes($index, $term) YIELD node AS publication, score\n"
        "MATCH authorship = (author:Author)-[:WROTE]->(publication)\n"
        "OPTIONAL MATCH citations = (publication)-[:CITES*1..3]->(:Publication)-[:ABOUT]->(topic)\n"
        "WHERE EXISTS { MATCH taxonomy = (topic)-[:NARROWER_THAN]->(:Topic) }\n"
        "WITH author, topic, score\n"
        "CALL (author) {\n"
        "    MATCH collaboration = (author)-[:COLLABORATED_WITH]-(colleague)\n"
        "    RETURN collect(colleague.name) AS collaborators\n"
        "}\n"
        "RETURN author.name AS name, topic.name AS topic, score, collaborators\n"
        "UNION ALL\n"
        "MATCH (guest:Author)\n"
        "RETURN guest.name AS name, null AS topic, 0.0 AS score, [] AS collaborators"
    )

    assert result.checks_inserted == 6
    assert (
        "YIELD node AS publication, score WITH * WHERE EXISTS { "
        "CALL custom.redactionAllowed([`publication`], [], $redaction_context)"
    ) in result.cypher
    for path in ("authorship", "citations", "taxonomy", "collaboration"):
        assert (
            f"WHERE EXISTS {{ CALL custom.redactionAllowed("
            f"nodes(`{path}`), relationships(`{path}`), $redaction_context)"
        ) in result.cypher
    assert (
        "UNION ALL\nMATCH (guest:Author) WHERE EXISTS { "
        "CALL custom.redactionAllowed([`guest`], [], $redaction_context)"
    ) in result.cypher
    Neo4j().parse(result.cypher)


def test_checks_four_levels_of_mixed_call_and_exists_subqueries(service):
    result = service.rewrite(
        "MATCH (a) CALL (a) {\n"
        "    MATCH authorship = (a)-[:WROTE]->(b)\n"
        "    WHERE EXISTS {\n"
        "        MATCH citation = (b)-[:CITES]->(c)\n"
        "        CALL (c) {\n"
        "            MATCH topic = (c)-[:ABOUT]->(d)\n"
        "            WHERE EXISTS { MATCH taxonomy = (d)-[:NARROWER_THAN]->(e) }\n"
        "            RETURN d AS nested\n"
        "        }\n"
        "        RETURN nested\n"
        "    }\n"
        "    RETURN b AS hit\n"
        "} RETURN hit"
    )

    assert result.checks_inserted == 5
    tree, = Neo4j().parse(result.cypher)
    for pattern, path in zip(
        list(tree.find_all(ast.GraphPattern, bfs=False))[1:],
        ("authorship", "citation", "topic", "taxonomy"),
        strict=True,
    ):
        where = pattern.graph_pattern_where_clause
        assert where is not None and where.source_span is not None
        start, end = where.source_span
        assert result.cypher[start:end].startswith(
            f"WHERE EXISTS {{ CALL custom.redactionAllowed("
            f"nodes(`{path}`), relationships(`{path}`), $redaction_context)"
        )


@pytest.mark.parametrize(
    ("source_call", "graph_field", "arguments"),
    [
        (
            "apoc.path.expand($start, $rels, $labels, 1, 3)",
            "path",
            "nodes(`hit`), relationships(`hit`)",
        ),
        ("apoc.path.expandConfig($start, $config)", "path", "nodes(`hit`), relationships(`hit`)"),
        ("db.index.fulltext.queryNodes($index, $term)", "node", "[`hit`], []"),
        ("db.index.vector.queryNodes($index, $k, $vector)", "node", "[`hit`], []"),
        (
            "db.index.vector.queryRelationships($index, $k, $vector)",
            "relationship",
            "[startNode(`hit`), endNode(`hit`)], [`hit`]",
        ),
    ],
)
def test_checks_allowlisted_procedure_yield_before_return(
    service, source_call, graph_field, arguments
):
    result = service.rewrite(f"CALL {source_call} YIELD {graph_field} AS hit RETURN hit")

    assert result.checks_inserted == 1
    assert (
        f"YIELD {graph_field} AS hit WITH * WHERE EXISTS {{ "
        f"CALL custom.redactionAllowed({arguments}, $redaction_context)"
    ) in result.cypher
    Neo4j().parse(result.cypher)


def test_check_uses_yield_alias_and_both_relationship_endpoints(service):
    result = service.rewrite(
        "CALL db.index.fulltext.queryRelationships($index, $term) "
        "YIELD relationship AS `my edge`, score"
    )

    assert result.checks_inserted == 1
    assert "[startNode(`my edge`), endNode(`my edge`)], [`my edge`]" in result.cypher
    assert result.cypher.endswith("RETURN `my edge`, `score`")
    Neo4j().parse(result.cypher)


def test_optional_procedure_filters_inside_scoped_call(service):
    result = service.rewrite(
        "OPTIONAL CALL db.index.vector.queryNodes($index, $k, $vector) "
        "YIELD node AS n, score RETURN n, score"
    )

    assert result.checks_inserted == 1
    assert result.cypher.startswith("OPTIONAL CALL (*) { CALL db.index.vector.queryNodes(")
    assert "YIELD node AS n, score WITH * WHERE EXISTS" in result.cypher
    assert result.cypher.endswith("RETURN `n`, `score` } RETURN n, score")


def test_configured_procedure_checks_custom_yield_name():
    service = CypherRedactionService(
        "custom.redactionAllowed",
        graph_procedures={"custom.readGraph": {"route": "path"}},
    )

    result = service.rewrite("CALL custom.readGraph() YIELD route AS p RETURN p")

    assert result.checks_inserted == 1
    assert "nodes(`p`), relationships(`p`)" in result.cypher
    Neo4j().parse(result.cypher)


def test_invalid_graph_entity_kind_is_rejected_when_configured():
    with pytest.raises(ValueError, match="invalid.*EntityKind"):
        CypherRedactionService(
            "custom.redactionAllowed",
            graph_procedures={"custom.readGraph": {"route": "invalid"}},
        )


@pytest.mark.parametrize(
    ("argument_order", "expected_arguments"),
    [
        (("entitlements", "nodes"), "$user_entitlements, [`n`]"),
        (("entitlements",), "$user_entitlements"),
        (("relationships", "entitlements", "nodes"), "[], $user_entitlements, [`n`]"),
    ],
)
def test_redaction_procedure_uses_the_configured_signature(argument_order, expected_arguments):
    service = CypherRedactionService(
        "apoc.company.checkAccess",
        context_parameter="user_entitlements",
        argument_order=argument_order,
        decision_field="permitted",
    )

    result = service.rewrite("MATCH (n:Publication) RETURN n")

    assert f"CALL apoc.company.checkAccess({expected_arguments}) YIELD permitted AS" in result.cypher
    Neo4j().parse(result.cypher)
    with pytest.raises(UnsupportedCypher, match="entitlement parameter is reserved"):
        service.rewrite("RETURN $user_entitlements")


@pytest.mark.parametrize("argument_order", [("nodes",), ("entitlements", "entitlements")])
def test_signature_requires_one_entitlement_argument(argument_order):
    with pytest.raises(ValueError, match="entitlements exactly once"):
        CypherRedactionService("apoc.company.checkAccess", argument_order=argument_order)


def test_single_node_keeps_wildcard_and_avoids_alias_collision(service):
    result = service.rewrite("MATCH (`_redaction_allowed_0`) RETURN *")

    assert result.checks_inserted == 1
    assert "YIELD allowed AS _redaction_allowed_1" in result.cypher
    assert result.cypher.endswith("RETURN *")


def test_query_without_graph_reads_is_returned_verbatim(service):
    source = "RETURN 'MATCH ()' AS sample // keep me\n"

    result = service.rewrite(source)

    assert result.checks_inserted == 0
    assert result.cypher == source


def test_optional_query_guard_receives_the_original_cypher():
    seen: list[str] = []
    service = CypherRedactionService("custom.redactionAllowed", query_guard=seen.append)
    source = "MATCH (n:Publication) RETURN n"

    assert service.rewrite(source).checks_inserted == 1
    assert seen == [source]


def test_query_guard_rejection_is_propagated_before_parsing():
    rejection = PermissionError("Query rejected by application policy")

    def reject(_cypher: str) -> None:
        raise rejection

    service = CypherRedactionService("custom.redactionAllowed", query_guard=reject)

    with pytest.raises(PermissionError) as exc:
        service.rewrite("MATCH (")
    assert exc.value is rejection


@pytest.mark.parametrize(
    ("query", "reason"),
    [
        ("MATCH ()-->(n) RETURN *", "explicit WITH/RETURN"),
        ("MATCH p=SHORTEST 1 (a)-->(b) RETURN p", "pre-selection"),
        ("RETURN 1; RETURN 2", "one Cypher statement"),
        ("MATCH (n) RETURN COUNT { MATCH (n)-->() }", "GQL statement chain"),
        ("CALL apoc.cypher.run($query, {}) YIELD value RETURN value", "allowlist"),
        ("CALL db.index.vector.queryNodes($i, $k, $v) YIELD score RETURN score", "must YIELD"),
        ("RETURN apoc.anything(1)", "user-defined functions"),
        ("RETURN $`redaction_context`", "reserved"),
    ],
)
def test_rejects_inputs_that_cannot_be_rewritten(service, query, reason):
    with pytest.raises(UnsupportedCypher, match=reason):
        service.rewrite(query)
