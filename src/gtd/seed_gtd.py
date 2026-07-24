from __future__ import annotations

import argparse
import os
from pathlib import Path

from .gtd_ingest import GTDBatchResult, load_gtd


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Seed Neo4j with Global Terrorism Database data.")
    parser.add_argument("--csv", required=True, type=Path, help="Path to a GTD CSV file.")
    parser.add_argument("--uri", default=os.getenv("NEO4J_URI", "bolt://neo4j:7687"))
    parser.add_argument("--user", default=os.getenv("NEO4J_USERNAME") or os.getenv("NEO4J_USER", "neo4j"))
    parser.add_argument("--password", default=os.getenv("NEO4J_PASSWORD", "neo4jpassword"))
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--wipe", action="store_true", help="Delete existing nodes before loading.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    result: GTDBatchResult = load_gtd(
        args.csv,
        args.uri,
        args.user,
        args.password,
        batch_size=args.batch_size,
        wipe=args.wipe,
    )
    print(f"Loaded {result.rows_seen} GTD rows and wrote {result.incidents_written} incidents.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
