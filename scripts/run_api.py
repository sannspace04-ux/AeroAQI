"""
scripts/run_api.py
==================
Development entry point — starts the AeroAQI FastAPI server with uvicorn.

Usage
-----
    python scripts/run_api.py                     # default: port 8000
    python scripts/run_api.py --port 8080         # custom port
    python scripts/run_api.py --reload            # auto-reload on code changes
    python scripts/run_api.py --host 0.0.0.0      # accessible on local network

The API will be available at:
  http://127.0.0.1:8000/docs    — Swagger UI (interactive)
  http://127.0.0.1:8000/redoc   — ReDoc documentation
  http://127.0.0.1:8000/health  — Health / liveness check

Environment variables (set in .env)
------------------------------------
  DATABASE_URL     — SQLAlchemy URL (default: SQLite at data/db/aeroaqi.db)
  ALLOWED_ORIGINS  — Comma-separated CORS origins
  LOG_LEVEL        — DEBUG | INFO | WARNING | ERROR

Notes
-----
- Run the ingestion pipeline first to populate the database:
    python scripts/run_ingestion.py --mode realtime
- The server does NOT start the ingestion pipeline automatically.
  Use POST /pipeline/run or the CLI script for that.
"""

import argparse
import sys
from pathlib import Path

# Ensure project root is on sys.path regardless of where this is run from
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Load .env before importing anything else
from dotenv import load_dotenv
load_dotenv(_PROJECT_ROOT / ".env", override=False)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Start the AeroAQI FastAPI development server"
    )
    p.add_argument("--host", default="127.0.0.1", help="Bind host (default 127.0.0.1)")
    p.add_argument("--port", type=int, default=8000, help="Bind port (default 8000)")
    p.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload on source file changes (development only)",
    )
    p.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of worker processes (default 1; >1 requires gunicorn)",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    try:
        import uvicorn
    except ImportError:
        print(
            "ERROR: uvicorn is not installed.\n"
            "Install it with:  pip install uvicorn[standard]",
            file=sys.stderr,
        )
        sys.exit(1)

    print(
        f"\n  AeroAQI API\n"
        f"  ───────────────────────────────────────\n"
        f"  Swagger UI  →  http://{args.host}:{args.port}/docs\n"
        f"  ReDoc       →  http://{args.host}:{args.port}/redoc\n"
        f"  Health      →  http://{args.host}:{args.port}/health\n"
        f"  ───────────────────────────────────────\n"
    )

    uvicorn.run(
        "src.api.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        workers=args.workers if not args.reload else 1,
        log_level="info",
    )


if __name__ == "__main__":
    main()
