"""
scripts/run_ingestion.py
=========================
Command-line entry point for the AeroAQI ingestion pipeline.

Usage
-----
    # Real-time run (fetch the latest 48 hours of data):
    python scripts/run_ingestion.py --mode realtime

    # Historical backfill for a specific date range:
    python scripts/run_ingestion.py --mode historical --start 2023-10-01 --end 2023-10-31

    # Skip specific sources (useful for debugging):
    python scripts/run_ingestion.py --mode realtime --skip era5 gadm

    # Run only Open-Meteo (skip everything else):
    python scripts/run_ingestion.py --mode realtime --skip openaq firms gadm era5

    # Show the full schema summary:
    python scripts/run_ingestion.py --schema

Before running
--------------
  1. Install dependencies:
       pip install -r requirements.txt

  2. Copy .env.example to .env and fill in your API keys:
       copy .env.example .env
       (then edit .env with your real OPENAQ_API_KEY and FIRMS_MAP_KEY)

  3. Run the pipeline:
       python scripts/run_ingestion.py --mode realtime

Expected output files
---------------------
  data/raw/openaq/         — raw JSON responses from OpenAQ
  data/raw/openmeteo/      — raw JSON responses from Open-Meteo
  data/raw/firms/          — raw CSV files from NASA FIRMS
  data/raw/gadm/           — GADM shapefile ZIP (downloaded once)
  data/processed/openaq/   — validated Parquet files
  data/processed/openmeteo/— validated Parquet files
  data/processed/firms/    — validated Parquet files
  data/processed/gadm/     — GeoJSON boundary files
  data/db/aeroaqi.db       — SQLite database
  logs/aeroaqi.log         — rotating log file
"""

import argparse
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Make sure the project root is on sys.path so all src imports work
# regardless of which directory the user runs this script from.
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="run_ingestion",
        description="AeroAQI data ingestion pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--mode",
        choices=["realtime", "historical"],
        default="realtime",
        help=(
            "realtime: fetch the latest data (default). "
            "historical: fetch a date range (requires --start and --end)."
        ),
    )
    parser.add_argument(
        "--start",
        metavar="YYYY-MM-DD",
        help="Start date for historical mode (e.g. 2023-10-01).",
    )
    parser.add_argument(
        "--end",
        metavar="YYYY-MM-DD",
        help="End date for historical mode (e.g. 2023-10-31).",
    )
    parser.add_argument(
        "--skip",
        nargs="*",
        metavar="SOURCE",
        default=[],
        help=(
            "One or more source names to skip. "
            "Valid names: openaq openmeteo era5 firms gadm. "
            "Example: --skip era5 gadm"
        ),
    )
    parser.add_argument(
        "--schema",
        action="store_true",
        help="Print the master data schema and exit (no data fetching).",
    )
    parser.add_argument(
        "--db-url",
        metavar="URL",
        default=None,
        help=(
            "Override the database URL. "
            "Default: reads DATABASE_URL from .env, "
            "falls back to SQLite at data/db/aeroaqi.db."
        ),
    )
    return parser.parse_args()


def main() -> int:
    """
    Main entry point.
    Returns 0 on success, 1 if any source failed.
    """
    args = parse_args()

    # --- Schema-only mode ---------------------------------------------------
    if args.schema:
        from src.schema.master_schema import print_schema_summary
        print_schema_summary()
        return 0

    # --- Validate historical mode arguments ---------------------------------
    if args.mode == "historical" and (not args.start or not args.end):
        print(
            "ERROR: --mode historical requires both --start and --end.\n"
            "Example: python scripts/run_ingestion.py "
            "--mode historical --start 2023-10-01 --end 2023-10-31",
            file=sys.stderr,
        )
        return 1

    # --- Import after sys.path is set ---------------------------------------
    from src.pipeline.ingest_pipeline import IngestionPipeline
    from src.utils.logger import get_logger

    log = get_logger("run_ingestion")

    log.info(
        f"Starting ingestion | mode={args.mode} | "
        f"start={args.start} | end={args.end} | "
        f"skip={args.skip}"
    )

    # --- Run pipeline -------------------------------------------------------
    pipeline = IngestionPipeline(
        db_url=args.db_url,
        skip_sources=args.skip or [],
    )

    results = pipeline.run(
        mode=args.mode,
        start_date=args.start,
        end_date=args.end,
    )

    # --- Exit code based on results -----------------------------------------
    failed = [r for r in results if r.status == "failed"]
    if failed:
        log.warning(
            f"{len(failed)} source(s) failed: "
            f"{[r.source_name for r in failed]}"
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
