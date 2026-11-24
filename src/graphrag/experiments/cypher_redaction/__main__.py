"""Rewrite Cypher from standard input and print the resulting query."""

import argparse
import sys

from .rewriter import DEFAULT_ARGUMENT_ORDER, CypherRedactionService, RedactionArgument


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--procedure", required=True, help="Qualified read-only procedure name")
    parser.add_argument(
        "--entitlement-parameter", "--context-parameter", default="redaction_context"
    )
    parser.add_argument(
        "--arguments", nargs="+", choices=list(RedactionArgument), default=DEFAULT_ARGUMENT_ORDER
    )
    parser.add_argument("--decision-field", default="allowed")
    args = parser.parse_args()
    try:
        service = CypherRedactionService(
            args.procedure,
            context_parameter=args.entitlement_parameter,
            argument_order=args.arguments,
            decision_field=args.decision_field,
        )
        result = service.rewrite(sys.stdin.read())
    except ValueError as exc:
        parser.exit(2, f"{parser.prog}: {exc}\n")
    sys.stdout.write(result.cypher)


if __name__ == "__main__":
    main()
