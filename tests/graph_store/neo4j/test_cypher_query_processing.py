"""Tests for clause-level Cypher query splitting."""

from graph_rag.graph_store.neo4j.cypher_query_processing import (
    CypherClauseKeyword,
    find_last_clause_index,
    split_cypher_clauses,
)


def test_splits_top_level_clauses_in_order() -> None:
    """Split ordinary read-query clauses and preserve their text."""

    clauses = split_cypher_clauses(
        "MATCH (document:Document) "
        "WHERE document.id = $document_id "
        "WITH document "
        "RETURN document ORDER BY document.id LIMIT 10"
    )

    assert [clause.keyword for clause in clauses] == [
        CypherClauseKeyword.MATCH,
        CypherClauseKeyword.WHERE,
        CypherClauseKeyword.WITH,
        CypherClauseKeyword.RETURN,
        CypherClauseKeyword.ORDER_BY,
        CypherClauseKeyword.LIMIT,
    ]
    assert clauses[1].text == "WHERE document.id = $document_id"


def test_ignores_keywords_inside_nested_or_quoted_text() -> None:
    """Keep subquery, pattern, comment, and literal keywords inside a clause."""

    clauses = split_cypher_clauses(
        "CALL { MATCH (nested:Document) RETURN nested } "
        "YIELD value "
        "RETURN 'MATCH RETURN' AS text /* LIMIT 1 */"
    )

    assert [clause.keyword for clause in clauses] == [
        CypherClauseKeyword.CALL,
        CypherClauseKeyword.YIELD,
        CypherClauseKeyword.RETURN,
    ]
    assert "MATCH (nested:Document)" in clauses[0].text


def test_recognizes_longest_multiword_keyword() -> None:
    """Prefer OPTIONAL MATCH and UNION ALL over their shorter suffixes."""

    clauses = split_cypher_clauses(
        "OPTIONAL MATCH (document:Document) RETURN document "
        "UNION ALL MATCH (other:Document) RETURN other"
    )

    assert [clause.keyword for clause in clauses] == [
        CypherClauseKeyword.OPTIONAL_MATCH,
        CypherClauseKeyword.RETURN,
        CypherClauseKeyword.UNION_ALL,
        CypherClauseKeyword.MATCH,
        CypherClauseKeyword.RETURN,
    ]


def test_finds_last_clause_selected_by_the_caller() -> None:
    """Return the final index matching caller-selected clause keywords."""

    clauses = split_cypher_clauses(
        "MATCH (first:Document) WITH first "
        "OPTIONAL MATCH (second:Document) RETURN first, second"
    )

    index = find_last_clause_index(
        clauses,
        {CypherClauseKeyword.MATCH, CypherClauseKeyword.OPTIONAL_MATCH},
    )

    assert index == 2
