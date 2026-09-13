from __future__ import annotations

import argparse
import os
from pathlib import Path

from .gtd_ingest import GTDBatchResult, load_gtd
from .gtd_prepare import GtdPreparationResult, prepare_gtd_csv


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Seed Neo4j with Global Terrorism Database data."
    )
    configured_csv = os.getenv("GTD_CSV_PATH")
    parser.add_argument(
        "--csv",
        type=Path,
        default=Path(configured_csv) if configured_csv else None,
        help="Path to a GTD CSV file. Overrides GTD_CSV_PATH.",
    )
    parser.add_argument("--uri", default=os.getenv("NEO4J_URI", "bolt://neo4j:7687"))
    parser.add_argument(
        "--user",
        default=os.getenv("NEO4J_USERNAME") or os.getenv("NEO4J_USER", "neo4j"),
    )
    parser.add_argument(
        "--password", default=os.getenv("NEO4J_PASSWORD", "neo4jpassword")
    )
    parser.add_argument("--batch-size", type=int, default=1_000)
    parser.add_argument(
        "--import-dir",
        type=Path,
        default=Path(os.getenv("NEO4J_IMPORT_DIR", "/import/gtd")),
        help="Directory in Neo4j's shared import volume where prepared CSV files are written.",
    )
    parser.add_argument(
        "--import-uri",
        default=os.getenv("NEO4J_IMPORT_URI", "file:///gtd"),
        help="Neo4j-visible URI for --import-dir.",
    )
    parser.add_argument(
        "--prepare-only",
        action="store_true",
        help="Validate and prepare graph-shaped CSV files without loading Neo4j.",
    )
    parser.add_argument(
        "--replace-prepared",
        action="store_true",
        help="Replace a prior preparation directory created by this importer.",
    )
    parser.add_argument(
        "--wipe", action="store_true", help="Delete existing nodes before loading."
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.csv is None:
        parser.error("provide --csv or set GTD_CSV_PATH")

    if args.prepare_only:
        prepared: GtdPreparationResult = prepare_gtd_csv(
            args.csv, args.import_dir, replace=args.replace_prepared
        )
        print(
            f"Validated {prepared.source_rows} GTD rows and wrote "
            f"{len(prepared.files)} prepared CSV files to {prepared.output_dir}."
        )
        return 0

    result: GTDBatchResult = load_gtd(
        args.csv,
        args.uri,
        args.user,
        args.password,
        import_dir=args.import_dir,
        import_uri=args.import_uri,
        batch_size=args.batch_size,
        wipe=args.wipe,
        replace_prepared=args.replace_prepared,
    )
    print(
        f"Loaded {result.incidents_written} incidents from {result.rows_seen} GTD rows; "
        f"targets={result.reconciliation['targets']}, "
        f"weapon_uses={result.reconciliation['weapon_uses']}, "
        f"attributions={result.reconciliation['attributions']}, "
        f"claims={result.reconciliation['claims']}, "
        f"source_sha256={result.source_sha256}."
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
