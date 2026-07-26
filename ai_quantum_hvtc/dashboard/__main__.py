from __future__ import annotations

import argparse
from collections.abc import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m ai_quantum_hvtc dashboard",
        description="Serve the dashboard backend API (and built frontend, if present).",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8600)
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Auto-reload on code changes (development only).",
    )
    args = parser.parse_args(argv)

    import uvicorn

    uvicorn.run(
        "ai_quantum_hvtc.dashboard.app:get_app",
        factory=True,
        host=args.host,
        port=args.port,
        reload=args.reload,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
