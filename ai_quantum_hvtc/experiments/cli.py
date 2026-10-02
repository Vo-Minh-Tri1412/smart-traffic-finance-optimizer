from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, NoReturn

from . import store


class _ArgumentError(ValueError):
    """An argparse error that can be returned as the CLI's JSON error payload."""


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise _ArgumentError(message)


def _emit(payload: Mapping[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str))


def _ok(command: str, **fields: Any) -> None:
    _emit({"status": "ok", "command": command, **fields})


def _failed(command: str, error: BaseException) -> None:
    _emit(
        {
            "status": "error",
            "command": command,
            "error_type": type(error).__name__,
            "error": str(error) or type(error).__name__,
        }
    )


def _role_path(value: str, *, option: str) -> tuple[str, str]:
    role, separator, path = value.partition("=")
    if not separator or not role or not path:
        raise _ArgumentError(f"{option} must be ROLE=PATH")
    return role, path


def _role_paths(values: Sequence[str], *, option: str) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for value in values:
        role, path = _role_path(value, option=option)
        if role in result:
            raise _ArgumentError(f"duplicate role for {option}: {role!r}")
        result[role] = Path(path)
    return result


def _source_paths(values: Sequence[str]) -> list[Path]:
    """Expand explicit source directories to Python files, without globbing arguments."""
    result: list[Path] = []
    for value in values:
        path = Path(value)
        if path.is_dir():
            files = sorted(
                candidate
                for candidate in path.rglob("*")
                if candidate.is_file()
                and candidate.suffix.lower() == ".py"
                and "__pycache__" not in candidate.parts
            )
            if not files:
                raise ValueError(f"source directory contains no Python files: {path}")
            result.extend(files)
        else:
            result.append(path)
    return result


def _request_object(path: Path) -> dict[str, Any]:
    try:
        return store.read_json(path)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: invalid JSON: {exc.msg}") from exc


def _request_mapping(
    value: object,
    *,
    field: str,
    base_dir: Path,
    resolve_paths: bool,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"request field {field!r} must be an object")
    result: dict[str, Any] = {}
    for role, item in value.items():
        if not isinstance(role, str) or not role:
            raise ValueError(f"request field {field!r} has an invalid role")
        if not isinstance(item, str) or not item:
            raise ValueError(f"request field {field!r}.{role!r} must be a non-empty path")
        result[role] = (base_dir / item).resolve() if resolve_paths else item
    return result


def _prepare_run_request(request_path: Path) -> dict[str, Any]:
    request = _request_object(request_path)
    allowed = {
        "run_id",
        "case_id",
        "seed",
        "controller_id",
        "mask",
        "inputs",
        "expected_outputs",
        "settings",
        "reward_variant",
    }
    unknown = sorted(set(request) - allowed)
    if unknown:
        raise ValueError(f"request contains unsupported fields: {', '.join(unknown)}")
    required = {
        "run_id",
        "case_id",
        "seed",
        "controller_id",
        "mask",
        "inputs",
        "expected_outputs",
        "settings",
    }
    missing = sorted(required - set(request))
    if missing:
        raise ValueError(f"request is missing required fields: {', '.join(missing)}")
    base_dir = request_path.resolve().parent
    return {
        "run_id": request["run_id"],
        "case_id": request["case_id"],
        "seed": request["seed"],
        "controller_id": request["controller_id"],
        "mask": request["mask"],
        "inputs": _request_mapping(
            request["inputs"],
            field="inputs",
            base_dir=base_dir,
            resolve_paths=True,
        ),
        "expected_outputs": _request_mapping(
            request["expected_outputs"],
            field="expected_outputs",
            base_dir=base_dir,
            resolve_paths=False,
        ),
        "settings": request["settings"],
        "reward_variant": request.get("reward_variant"),
    }


def _cmd_create(args: argparse.Namespace) -> None:
    shared_inputs = _role_paths(args.shared_input, option="--shared-input")
    experiment_dir = store.create_experiment(
        root=Path(args.root),
        experiment_id=args.experiment_id,
        project_path=Path(args.project),
        snapshot_path=Path(args.snapshot),
        protocol_path=Path(args.protocol),
        source_paths=_source_paths(args.source),
        shared_inputs=shared_inputs,
    )
    _ok("create", experiment=str(experiment_dir))


def _cmd_prepare_run(args: argparse.Namespace) -> None:
    request_path = Path(args.request)
    request = _prepare_run_request(request_path)
    run_dir = store.create_run(
        experiment_dir=Path(args.experiment),
        run_id=request["run_id"],
        case_id=request["case_id"],
        seed=request["seed"],
        controller_id=request["controller_id"],
        mask=request["mask"],
        inputs=request["inputs"],
        expected_outputs=request["expected_outputs"],
        settings=request["settings"],
        reward_variant=request["reward_variant"],
    )
    _ok("prepare-run", run=str(run_dir))


def _cmd_prepare_debug(args: argparse.Namespace) -> None:
    from .executor import prepare_debug_run

    run_dir = prepare_debug_run(
        experiment_dir=Path(args.experiment),
        run_id=args.run_id,
        case_id=args.case,
        seed=args.seed,
        routes=Path(args.routes),
        horizon_seconds=args.horizon_seconds,
        step_length_seconds=args.step_length,
        intended_demand_ledger=(
            Path(args.intended_demand_ledger) if args.intended_demand_ledger is not None else None
        ),
    )
    _ok("prepare-debug", run=str(run_dir))


def _cmd_verify_experiment(args: argparse.Namespace) -> None:
    result = store.verify_experiment(Path(args.experiment))
    _ok(
        "verify-experiment",
        experiment_id=result["experiment_id"],
        content_sha256=result["content_sha256"],
        mode=result["protocol"]["mode"],
    )


def _cmd_verify_run(args: argparse.Namespace) -> None:
    result = store.verify_run(Path(args.run))
    run = result["run"]
    _ok(
        "verify-run",
        experiment_id=run["experiment_id"],
        run_id=run["run_id"],
        state=result["state"],
        mode=run["mode"],
        content_sha256=run["content_sha256"],
    )


def _cmd_run_debug(args: argparse.Namespace) -> None:
    from .executor import execute_debug_run

    result = execute_debug_run(Path(args.run))
    fields: dict[str, Any] = {"result": result}
    if isinstance(result, dict):
        fields.update({key: value for key, value in result.items() if key != "status"})
        if "status" in result:
            fields["execution_status"] = result["status"]
    _ok("run-debug", **fields)


def build_parser() -> argparse.ArgumentParser:
    parser = _ArgumentParser(
        prog="python -m ai_quantum_hvtc experiments",
        description="Create and verify frozen experiment and run identities.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create", help="freeze an experiment identity")
    create.add_argument(
        "--root",
        required=True,
        help="directory under which the experiment is created",
    )
    create.add_argument("--experiment-id", required=True)
    create.add_argument("--project", required=True, help="retained project descriptor")
    create.add_argument("--snapshot", required=True, help="project snapshot JSON")
    create.add_argument("--protocol", required=True, help="experiment protocol JSON")
    create.add_argument(
        "--source",
        action="append",
        required=True,
        help="explicit source file or directory; directories recursively include *.py",
    )
    create.add_argument(
        "--shared-input",
        action="append",
        default=[],
        metavar="ROLE=PATH",
        help="frozen shared input, repeatable",
    )
    create.set_defaults(handler=_cmd_create)

    prepare_run = subparsers.add_parser("prepare-run", help="reserve and freeze a run")
    prepare_run.add_argument("--experiment", required=True)
    prepare_run.add_argument("--request", required=True, help="run request JSON")
    prepare_run.set_defaults(handler=_cmd_prepare_run)

    prepare_debug = subparsers.add_parser(
        "prepare-debug",
        help="prepare a debug existing-net run",
    )
    prepare_debug.add_argument("--experiment", required=True)
    prepare_debug.add_argument("--run-id", required=True)
    prepare_debug.add_argument("--case", required=True)
    prepare_debug.add_argument("--seed", required=True, type=int)
    prepare_debug.add_argument("--routes", required=True)
    prepare_debug.add_argument(
        "--intended-demand-ledger",
        help="optional frozen TASK-100 per-requested-vehicle-trip ledger",
    )
    prepare_debug.add_argument("--horizon-seconds", required=True, type=int)
    prepare_debug.add_argument("--step-length", required=True, type=float)
    prepare_debug.set_defaults(handler=_cmd_prepare_debug)

    verify_experiment = subparsers.add_parser(
        "verify-experiment",
        help="verify an experiment identity and its frozen inputs",
    )
    verify_experiment.add_argument("--experiment", required=True)
    verify_experiment.set_defaults(handler=_cmd_verify_experiment)

    verify_run = subparsers.add_parser("verify-run", help="verify a run and any sealed outputs")
    verify_run.add_argument("--run", required=True)
    verify_run.set_defaults(handler=_cmd_verify_run)

    run_debug = subparsers.add_parser("run-debug", help="execute and seal a prepared debug run")
    run_debug.add_argument("--run", required=True)
    run_debug.set_defaults(handler=_cmd_run_debug)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
        args.handler(args)
    except SystemExit:
        raise
    except Exception as exc:
        command = getattr(locals().get("args"), "command", "experiments")
        _failed(command, exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
