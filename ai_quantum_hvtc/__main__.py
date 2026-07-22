from __future__ import annotations

import sys

from .doctor import main as doctor_main


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] == "simulate":
        from .simulation.cli import main as simulation_main

        return simulation_main(args[1:])
    if args and args[0] == "dashboard":
        from .dashboard.__main__ import main as dashboard_main

        return dashboard_main(args[1:])
    return doctor_main(args)


if __name__ == "__main__":
    raise SystemExit(main())
