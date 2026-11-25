"""
Insert a read-only Neo4j redaction procedure at Cypher graph-read sites.

In the work rag service app, the caller will likely have to keep the
original query. The new query that has been modified, and if the mcp
server rejects the query as invalid, the LLM will have to repair the
original query. After that, it has to pass through this rewriter, and
then it can try again.
"""

import re
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from itertools import pairwise
from types import MappingProxyType

from graphglot import ast
from graphglot.ast.cypher import CypherPatternComprehension, CypherPatternPredicate
from graphglot.ast.functions import Anonymous
from graphglot.dialect.neo4j import Neo4j
from graphglot.error import GraphGlotError
from graphglot.lexer import Token, TokenType


class UnsupportedCypher(ValueError):
    """The experiment could not safely rewrite this query."""


@dataclass(frozen=True)
class RedactionRewrite:
    cypher: str
    checks_inserted: int


class EntityKind(StrEnum):
    NODE = "node"
    RELATIONSHIP = "relationship"
    PATH = "path"


class RedactionArgument(StrEnum):
    NODES = "nodes"
    RELATIONSHIPS = "relationships"
    ENTITLEMENTS = "entitlements"


DEFAULT_ARGUMENT_ORDER = (
    RedactionArgument.NODES,
    RedactionArgument.RELATIONSHIPS,
    RedactionArgument.ENTITLEMENTS,
)


@dataclass(frozen=True)
class _ProcedureCall:
    name: str
    entitlement_parameter: str
    arguments: tuple[RedactionArgument, ...]
    decision_field: str


# Each built-in procedure yields its graph entity under the name of its kind.
_DEFAULT_GRAPH_YIELDS: Mapping[str, EntityKind] = MappingProxyType(
    {
        "apoc.path.expandConfig": EntityKind.PATH,
        "apoc.path.expand": EntityKind.PATH,
        "db.index.fulltext.queryNodes": EntityKind.NODE,
        "db.index.fulltext.queryRelationships": EntityKind.RELATIONSHIP,
        "db.index.vector.queryNodes": EntityKind.NODE,
        "db.index.vector.queryRelationships": EntityKind.RELATIONSHIP,
    }
)

_IDENTIFIER = r"[A-Za-z_][A-Za-z_0-9]*"


class CypherRedactionService:
    """Rewrite one read query using a configured procedure and policy parameter.

    The caller enforces the read-only policy before calling this service or
    supplies a query guard that raises on rejected input.
    Configure the positional arguments and Boolean output to match the deployed
    procedure. The caller binds the entitlement list from trusted application state.
    """

    def __init__(
        self,
        procedure: str,
        *,
        context_parameter: str = "redaction_context",
        argument_order: Sequence[str] = DEFAULT_ARGUMENT_ORDER,
        decision_field: str = "allowed",
        graph_procedures: Mapping[str, Mapping[str, str]] | None = None,
        query_guard: Callable[[str], None] | None = None,
    ) -> None:
        if not re.fullmatch(rf"{_IDENTIFIER}(?:\.{_IDENTIFIER})+", procedure):
            raise ValueError("Expected a qualified redaction procedure name")
        if not re.fullmatch(_IDENTIFIER, context_parameter):
            raise ValueError("Expected a simple entitlement parameter name")
        if not re.fullmatch(_IDENTIFIER, decision_field):
            raise ValueError("Expected a simple decision field name")
        arguments = tuple(RedactionArgument(value) for value in argument_order)
        if arguments.count(RedactionArgument.ENTITLEMENTS) != 1:
            raise ValueError("argument_order must contain entitlements exactly once")
        self._redaction_call = _ProcedureCall(
            procedure, context_parameter, arguments, decision_field
        )
        self._query_guard = query_guard
        if graph_procedures is None:
            self._graph_procedures: dict[str, dict[str, EntityKind]] = {
                name: {kind.value: kind} for name, kind in _DEFAULT_GRAPH_YIELDS.items()
            }
        else:
            self._graph_procedures = {
                name: {field: EntityKind(kind) for field, kind in fields.items()}
                for name, fields in graph_procedures.items()
            }

    def rewrite(self, cypher: str) -> RedactionRewrite:
        """Return rewritten Cypher or raise UnsupportedCypher for an unsupported read."""
        if self._query_guard is not None:
            self._query_guard(cypher)

        # Neo4j interprets Unicode escapes in identifiers. Use the same spellings
        # for AST matching, injected identifiers, and the reserved parameter.
        if re.search(r"\\u[0-9A-Fa-f]{4}", cypher):
            raise UnsupportedCypher("Unicode escape sequences are unsupported")
        dialect = Neo4j()
        try:
            tokens = dialect.tokenize(cypher)
            expressions = [
                expression
                for expression in dialect.parser().parse(tokens, cypher)
                if expression is not None
            ]
        except GraphGlotError as exc:
            raise UnsupportedCypher(f"Graphglot could not parse the Cypher: {exc}") from exc
        if len(expressions) != 1:
            raise UnsupportedCypher("Expected exactly one Cypher statement")
        if any(
            left.token_type == TokenType.DOLLAR_SIGN
            and right.text == self._redaction_call.entitlement_parameter
            for left, right in pairwise(tokens)
        ):
            raise UnsupportedCypher("The redaction entitlement parameter is reserved")

        return _Rewrite(
            cypher,
            tokens,
            self._redaction_call,
            self._graph_procedures,
        ).apply(expressions[0])


def _source_span(node: ast.Expression) -> tuple[int, int]:
    span = node.source_span
    if span is None:
        raise UnsupportedCypher(f"Graphglot omitted the source span of {type(node).__name__}")
    return span


def _start(node: ast.Expression) -> int:
    start, _ = _source_span(node)
    return start


def _end(node: ast.Expression) -> int:
    _, end = _source_span(node)
    return end


def _quote(name: str) -> str:
    return "`" + name.replace("`", "``") + "`"


class _Rewrite:
    def __init__(
        self,
        source: str,
        tokens: Sequence[Token],
        redaction_call: _ProcedureCall,
        graph_procedures: Mapping[str, Mapping[str, EntityKind]],
    ) -> None:
        self.source = source
        self.tokens = tokens
        self.token_indexes = {token.start: i for i, token in enumerate(tokens)}
        self.names = {token.text for token in tokens}
        self.parents: dict[int, ast.Expression] = {}
        self.redaction_call = redaction_call
        self.graph_procedures = graph_procedures
        self.insertions: dict[int, str] = defaultdict(str)
        self.checks = 0
        self.added_match_binding = False
        self.decision = self._fresh("allowed")

    def apply(self, tree: ast.Expression) -> RedactionRewrite:
        nodes = list(tree.dfs())
        self.parents = {id(child): node for node in nodes for child in node.children()}

        # Process descendants first so nested filters close before outer filters.
        for node in reversed(nodes):
            self._visit(node)
        if self.added_match_binding and any(
            isinstance(child, ast.Asterisk)
            for node in nodes
            if isinstance(node, ast.ReturnStatementBody)
            for child in node.return_statement_body.children()
        ):
            raise UnsupportedCypher(
                "Use an explicit WITH/RETURN projection when a MATCH needs a temporary path"
            )

        parts = []
        cursor = 0
        for position, insertion in sorted(self.insertions.items()):
            parts.extend((self.source[cursor:position], insertion))
            cursor = position
        parts.append(self.source[cursor:])
        return RedactionRewrite("".join(parts), self.checks)

    def _visit(self, node: ast.Expression) -> None:
        if isinstance(node, Anonymous):
            raise UnsupportedCypher("Unrecognized or user-defined functions are unsupported")
        if isinstance(node, ast.StatementBlock) and node.list_next_statement:
            # Graphglot can misread a Cypher expression subquery as a GQL NEXT
            # statement and report spans that end inside the original expression.
            raise UnsupportedCypher("Graphglot parsed this query as a GQL statement chain")
        if isinstance(node, ast.GraphPattern):
            self._match(node)
        elif isinstance(node, CypherPatternComprehension):
            self._comprehension(node)
        elif isinstance(node, CypherPatternPredicate):
            self._pattern_predicate(node)
        elif isinstance(node, ast.NamedProcedureCall):
            self._procedure_call(node)
        elif isinstance(node, ast.ReturnItem) and node.return_item_alias is None:
            self._preserve_column_name(node)

    def _fresh(self, stem: str) -> str:
        number = 0
        while (name := f"_redaction_{stem}_{number}") in self.names:
            number += 1
        self.names.add(name)
        return name

    def _before(self, position: int, text: str) -> None:
        self.insertions[position] = text + self.insertions[position]

    def _prefix_pattern(self, position: int, prefix: str) -> None:
        # A legal original such as MATCH(n) or NOT(n)-->() may lack whitespace.
        pending = self.insertions[position].lstrip()
        leading = "" if position == 0 or self.source[position - 1] in "([{ \t\r\n" else " "
        self.insertions[position] = f"{leading}{prefix} {pending}"

    def _after(self, position: int, text: str) -> None:
        self.insertions[position] += text

    def _path_guard(self, path: ast.PathPattern, *, match: bool = False) -> str:
        if isinstance(path.path_pattern_prefix, ast.PathSearchPrefix):
            raise UnsupportedCypher("Selective path searches require pre-selection redaction")

        if (declaration := path.path_variable_declaration) is not None:
            name = _quote(declaration.path_variable.name)
        else:
            pattern = path.path_pattern_expression
            if isinstance(pattern, ast.PathTerm) and len(pattern.factors) == 1:
                node = pattern.factors[0]
                if isinstance(node, ast.NodePattern) and node.element_pattern_filler:
                    variable = node.element_pattern_filler.element_variable_declaration
                    if variable is not None:
                        name = _quote(variable.element_variable.name)
                        return self._guard(f"[{name}]", "[]")
            name = self._fresh("path")
            self._prefix_pattern(_start(pattern), f"{name} =")
            self.added_match_binding |= match
        return self._guard(f"nodes({name})", f"relationships({name})")

    def _guard(self, nodes: str, relationships: str) -> str:
        call = self.redaction_call
        expressions = {
            RedactionArgument.NODES: nodes,
            RedactionArgument.RELATIONSHIPS: relationships,
            RedactionArgument.ENTITLEMENTS: f"${call.entitlement_parameter}",
        }
        arguments = ", ".join(expressions[argument] for argument in call.arguments)
        self.checks += 1
        return (
            f"EXISTS {{ CALL {call.name}({arguments}) "
            f"YIELD {call.decision_field} AS {self.decision} "
            f"WITH {self.decision} WHERE {self.decision} = true RETURN {self.decision} }}"
        )

    def _filter(
        self, end: int, where: ast.GraphPatternWhereClause | ast.WhereClause | None, guard: str
    ) -> None:
        if where is None:
            self._after(end, f" WHERE {guard}")
            return
        start, end = _source_span(where)
        where_token = self.tokens[self.token_indexes[start]]
        self._before(where_token.end + 1, f" {guard} AND (")
        self._after(end, ")")

    def _match(self, graph: ast.GraphPattern) -> None:
        parent = self.parents.get(id(graph))
        grandparent = self.parents.get(id(parent))
        explicit_match = isinstance(parent, ast.GraphPatternBindingTable) and isinstance(
            grandparent, ast.SimpleMatchStatement
        )
        implicit_exists = isinstance(grandparent, ast.ExistsPredicate)
        if not (explicit_match or implicit_exists) or graph.keep_clause is not None:
            raise UnsupportedCypher("Unsupported MATCH form")
        paths = graph.path_pattern_list
        guard = " AND ".join(
            self._path_guard(path, match=explicit_match) for path in paths.list_path_pattern
        )
        if implicit_exists:
            self._prefix_pattern(_start(paths), "MATCH")
        self._filter(_end(paths), graph.graph_pattern_where_clause, guard)

    def _comprehension(self, node: CypherPatternComprehension) -> None:
        guard = self._path_guard(node.pattern)
        self._filter(_end(node.pattern.path_pattern_expression), node.where_clause, guard)

    def _pattern_predicate(self, node: CypherPatternPredicate) -> None:
        start, end = _source_span(node.pattern)
        guard = self._path_guard(node.pattern)
        i = self.token_indexes[start]
        implicit_exists = (
            i >= 2
            and self.tokens[i - 2].token_type == TokenType.EXISTS
            and self.tokens[i - 1].token_type == TokenType.LEFT_BRACE
        )
        self._prefix_pattern(start, "MATCH" if implicit_exists else "EXISTS { MATCH")
        self._after(end, f" WHERE {guard}" + ("" if implicit_exists else " }"))

    def _procedure_call(self, call: ast.NamedProcedureCall) -> None:
        reference = call.procedure_reference
        if not isinstance(reference, ast.CatalogProcedureParentAndName):
            raise UnsupportedCypher("Unsupported procedure name")
        namespace = reference.catalog_object_parent_reference
        qualifiers = namespace.catalog_object_parent_reference if namespace is not None else []
        if not isinstance(qualifiers, list):
            raise UnsupportedCypher("Unsupported procedure namespace")
        # Validate each segment so quoted names containing dots cannot match other procedures.
        segments = [identifier.name for identifier in (*qualifiers, reference.procedure_name)]
        if any(not re.fullmatch(_IDENTIFIER, segment) for segment in segments):
            raise UnsupportedCypher("Unsupported procedure name")
        name = ".".join(segments)
        fields = self.graph_procedures.get(name)
        if fields is None or name == self.redaction_call.name:
            raise UnsupportedCypher(f"Procedure is outside the graph-read allowlist: {name}")
        if call.yield_clause is None:
            raise UnsupportedCypher(f"{name} requires an explicit YIELD of its graph fields")
        items = call.yield_clause.yield_item_list.list_yield_item
        yielded: dict[str, str] = {}
        for item in items:
            field = item.yield_item_name.name
            alias = item.yield_item_alias
            yielded[field] = _quote(alias.binding_variable.name if alias is not None else field)
        if len(yielded) != len(items) or len(set(yielded.values())) != len(items):
            raise UnsupportedCypher(f"{name} has duplicate YIELD fields or aliases")
        if not fields or fields.keys() - yielded.keys():
            raise UnsupportedCypher(f"{name} must YIELD {', '.join(fields)}")

        nodes: list[str] = []
        relationships: list[str] = []
        for field, kind in fields.items():
            var = yielded[field]
            if kind is EntityKind.NODE:
                nodes.append(f"[{var}]")
            elif kind is EntityKind.RELATIONSHIP:
                nodes.append(f"[startNode({var}), endNode({var})]")
                relationships.append(f"[{var}]")
            elif kind is EntityKind.PATH:
                nodes.append(f"nodes({var})")
                relationships.append(f"relationships({var})")

        statement = self.parents.get(id(call))
        if not isinstance(statement, ast.CallProcedureStatement):
            raise UnsupportedCypher("Unsupported named procedure call form")
        guard = self._guard(" + ".join(nodes) or "[]", " + ".join(relationships) or "[]")
        projection = ", ".join(yielded.values())
        suffix = f" WITH * WHERE {guard}"
        if statement.optional:
            # Keep the null-producing boundary outside the filter.
            optional_index = self.token_indexes[_start(statement)]
            self._before(self.tokens[optional_index + 1].start, "CALL (*) { ")
            suffix += f" RETURN {projection} }}"
        if isinstance(self.parents.get(id(statement)), ast.LinearCatalogModifyingStatement):
            suffix += f" RETURN {projection}"
        self._after(_end(call), suffix)

    def _preserve_column_name(self, item: ast.ReturnItem) -> None:
        if not self.insertions:
            return
        start, end = _source_span(item)
        if any(start <= position <= end for position in self.insertions):
            self._after(end, f" AS {_quote(self.source[start:end])}")
