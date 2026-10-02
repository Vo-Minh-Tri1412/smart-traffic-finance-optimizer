from __future__ import annotations

import hashlib
import json
import re
from contextlib import suppress
from pathlib import Path
from typing import Any

from ai_quantum_hvtc.simulation.maps.snapshot import verify_project_snapshot
from ai_quantum_hvtc.simulation.maps.source import sha256_file

EXPERIMENT_SCHEMA = "experiment_manifest.v1"
RUN_SCHEMA = "experiment_run.v1"
OUTPUT_SCHEMA = "run_outputs.v1"
SPLITS = {"rl_train", "rl_validation", "coefficient_fit", "surrogate_validation", "final_test"}
CONTRACTS = {"demand", "observation", "reward", "economic", "evaluator", "safety"}
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
_RESERVED = {"CON", "PRN", "AUX", "NUL"} | {
    f"{prefix}{i}" for prefix in ("COM", "LPT") for i in range(1, 10)
}


class ExperimentError(ValueError):
    """An identity, partition, input or artifact lifecycle invariant was violated."""


def validate_id(value: object) -> str:
    if (
        not isinstance(value, str)
        or not _ID.fullmatch(value)
        or value.endswith(".")
        or value.split(".", 1)[0].upper() in _RESERVED
    ):
        raise ExperimentError(f"invalid portable artifact ID: {value!r}")
    return value


def digest(data: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(
            data,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        obj: dict[str, Any] = {}
        for key, value in pairs:
            if key in obj:
                raise ExperimentError(f"{path}: duplicate JSON key {key!r}")
            obj[key] = value
        return obj

    def reject_constant(value: str) -> None:
        raise ExperimentError(f"{path}: non-finite JSON number {value}")

    data = json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=unique_object,
        parse_constant=reject_constant,
    )
    if not isinstance(data, dict):
        raise ExperimentError(f"{path}: expected JSON object")
    return data


def file_record(path: Path) -> dict[str, Any]:
    path = path.resolve(strict=True)
    return {"path": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size}


def _verify_file(record: dict[str, Any]) -> None:
    if file_record(Path(record["path"])) != record:
        raise ExperimentError(f"input checksum mismatch: {record['path']}")


def _write_manifest(path: Path, data: dict[str, Any]) -> dict[str, Any]:
    result = {**data, "content_sha256": digest(data)}
    with path.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    return result


def _read_manifest(path: Path, schema: str) -> dict[str, Any]:
    result = read_json(path)
    if result.get("schema_version") != schema:
        raise ExperimentError(f"{path}: unsupported schema")
    content = {k: v for k, v in result.items() if k != "content_sha256"}
    if result.get("content_sha256") != digest(content):
        raise ExperimentError(f"{path}: manifest checksum mismatch")
    return result


def validate_protocol(protocol: dict[str, Any]) -> None:
    if protocol.get("schema_version") != "experiment_protocol.v1":
        raise ExperimentError("unsupported experiment protocol schema")
    mode = protocol.get("mode")
    if mode not in {"debug", "research_synthetic"}:
        raise ExperimentError(
            "mode must be debug or research_synthetic; production claims unsupported"
        )
    seeds = protocol.get("seed_splits")
    if not isinstance(seeds, dict) or set(seeds) != SPLITS:
        raise ExperimentError(f"seed_splits must define exactly {sorted(SPLITS)}")
    seen: set[int] = set()
    for split, values in seeds.items():
        if (
            not isinstance(values, list)
            or not values
            or any(type(v) is not int or v < 0 or v > 2**31 - 1 for v in values)
        ):
            raise ExperimentError(f"{split}: expected non-empty integer seed array")
        if len(set(values)) != len(values) or seen.intersection(values):
            raise ExperimentError("seed partitions overlap or contain duplicate seeds")
        seen.update(values)
    cases = protocol.get("cases")
    if not isinstance(cases, dict) or not cases:
        raise ExperimentError("cases must explicitly assign day/profile/incident cases to splits")
    groups: dict[str, str] = {}
    for case_id, case in cases.items():
        validate_id(case_id)
        if not isinstance(case, dict) or case.get("split") not in SPLITS:
            raise ExperimentError(f"{case_id}: invalid case split")
        # A partition group identifies the underlying day/profile/incident configuration.
        # Renaming a case cannot make its group independent.
        group = validate_id(case.get("partition_group"))
        if group in groups and groups[group] != case["split"]:
            raise ExperimentError(f"case partition_group crosses splits: {group}")
        groups[group] = case["split"]
    if mode == "research_synthetic" and {c["split"] for c in cases.values()} != SPLITS:
        raise ExperimentError("research protocol needs cases in every split")
    versions = protocol.get("contracts")
    if not isinstance(versions, dict) or set(versions) != CONTRACTS:
        raise ExperimentError(f"contracts must explicitly define {sorted(CONTRACTS)}")
    for role, version in versions.items():
        if version is None and mode == "debug":
            continue
        if not isinstance(version, str) or not re.fullmatch(r"[a-z0-9_]+\.v[1-9][0-9]*", version):
            raise ExperimentError(f"{role}: explicit version required; null only allowed in debug")
    objective = protocol.get("objective")
    if objective is None and mode == "debug":
        return
    if not isinstance(objective, dict) or set(objective) != {"evaluator_input", "reward_inputs"}:
        raise ExperimentError("objective needs common evaluator_input and separate reward_inputs")
    evaluator = validate_id(objective["evaluator_input"])
    rewards = objective["reward_inputs"]
    if not isinstance(rewards, dict) or not rewards:
        raise ExperimentError("objective.reward_inputs must declare named reward variants")
    for name, role in rewards.items():
        validate_id(name)
        validate_id(role)
        if role == evaluator:
            raise ExperimentError("reward and evaluator must use separate input roles")


def _validate_objective_inputs(protocol: dict[str, Any], shared: dict[str, Any]) -> None:
    objective = protocol.get("objective")
    if objective is not None:
        roles = {objective["evaluator_input"], *objective["reward_inputs"].values()}
        if not roles.issubset(shared):
            raise ExperimentError(
                f"missing frozen objective inputs: {sorted(roles - shared.keys())}"
            )


def _run_objective(
    experiment: dict[str, Any],
    controller_id: str,
    reward_variant: str | None,
) -> dict[str, Any]:
    objective = experiment["protocol"].get("objective")
    if reward_variant is not None:
        validate_id(reward_variant)
        if objective is None or reward_variant not in objective["reward_inputs"]:
            raise ExperimentError("reward variant is not frozen in experiment protocol")
        if controller_id == "fixed_time":
            raise ExperimentError("fixed_time does not consume a learning reward")
    elif controller_id.startswith("rl_"):
        raise ExperimentError("RL evaluation requires an explicit frozen reward variant")
    shared = experiment["shared_inputs"]
    return {
        "reward_variant": reward_variant,
        "reward_profile_sha256": (
            shared[objective["reward_inputs"][reward_variant]]["sha256"]
            if reward_variant is not None
            else None
        ),
        "evaluator_profile_sha256": (
            shared[objective["evaluator_input"]]["sha256"] if objective else None
        ),
    }


def create_experiment(
    *,
    root: Path,
    experiment_id: str,
    project_path: Path,
    snapshot_path: Path,
    protocol_path: Path,
    source_paths: list[Path],
    shared_inputs: dict[str, Path] | None = None,
) -> Path:
    """Freeze protocol, map identity, implementation and shared profile inputs before any run."""
    validate_id(experiment_id)
    protocol_record = file_record(protocol_path)
    protocol = read_json(protocol_path)
    validate_protocol(protocol)
    snapshot_record = file_record(snapshot_path)
    snapshot = verify_project_snapshot(snapshot_path, project_path)
    if not source_paths:
        raise ExperimentError("source_paths must include the implementation being frozen")
    sources = [file_record(path) for path in sorted(set(source_paths))]
    shared = {validate_id(role): file_record(path) for role, path in (shared_inputs or {}).items()}
    _validate_objective_inputs(protocol, shared)
    _verify_file(protocol_record)
    _verify_file(snapshot_record)
    root.mkdir(parents=True, exist_ok=True)
    directory = root / experiment_id
    directory.mkdir(exist_ok=False)
    (directory / "runs").mkdir()
    (directory / "bindings").mkdir()
    _write_manifest(
        directory / "experiment.json",
        {
            "schema_version": EXPERIMENT_SCHEMA,
            "experiment_id": experiment_id,
            "project_path": str(project_path.resolve()),
            "project_id": snapshot["project_id"],
            "project_snapshot": snapshot_record,
            "protocol_file": protocol_record,
            "protocol": protocol,
            "source_files": sources,
            "shared_inputs": shared,
            "evidence_scope": "identity_only_not_scientific_acceptance",
        },
    )
    return directory


def verify_experiment(directory: Path) -> dict[str, Any]:
    experiment = _read_manifest(directory / "experiment.json", EXPERIMENT_SCHEMA)
    validate_id(experiment["experiment_id"])
    if directory.name != experiment["experiment_id"]:
        raise ExperimentError("experiment directory does not match experiment_id")
    validate_protocol(experiment["protocol"])
    _validate_objective_inputs(experiment["protocol"], experiment["shared_inputs"])
    for record in [
        experiment["project_snapshot"],
        experiment["protocol_file"],
        *experiment["source_files"],
        *experiment["shared_inputs"].values(),
    ]:
        _verify_file(record)
    if read_json(Path(experiment["protocol_file"]["path"])) != experiment["protocol"]:
        raise ExperimentError("embedded protocol differs from frozen source")
    verify_project_snapshot(
        Path(experiment["project_snapshot"]["path"]), Path(experiment["project_path"])
    )
    return experiment


def _output_path(directory: Path, relative: object) -> Path:
    if not isinstance(relative, str) or not relative or "\\" in relative:
        raise ExperimentError("output must be a relative path with forward slashes")
    path = Path(relative)
    if path.is_absolute() or any(p in {"", ".", ".."} for p in relative.split("/")):
        raise ExperimentError("output path must stay within run directory")
    for part in path.parts:
        validate_id(part)
    resolved = (directory / path).resolve()
    if not resolved.is_relative_to(directory.resolve()):
        raise ExperimentError("output path escapes run directory")
    if path.parts[0].lower() in {"run.json", "outputs.json", "execution.json"}:
        raise ExperimentError("output path conflicts with lifecycle metadata")
    return resolved


def _run_bindings(run: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Bind paired conditions, dataset partitions and frozen evaluation policies by content."""
    data_inputs = {
        role: {"sha256": record["sha256"], "bytes": record["bytes"]}
        for role, record in run["inputs"].items()
        if role in {"demand", "routes"}
    }
    pair_key = digest({"case_id": run["case_id"], "seed": run["seed"]})
    bindings = {
        f"pair-{pair_key}": {
            "case_id": run["case_id"],
            "seed": run["seed"],
            "data_inputs": data_inputs,
            "settings": run["settings"],
        }
    }
    for role, record in data_inputs.items():
        bindings[f"partition-{role}-{record['sha256']}"] = {"split": run["split"]}
    if "checkpoint" in run["inputs"]:
        policy_key = digest(
            {
                "controller_id": run["controller_id"],
                "reward_variant": run["objective"]["reward_variant"],
            }
        )
        bindings[f"policy-{policy_key}"] = {
            "checkpoint_sha256": run["inputs"]["checkpoint"]["sha256"],
        }
    return bindings


def _check_bindings(experiment_dir: Path, run: dict[str, Any], *, create: bool) -> None:
    directory = experiment_dir / "bindings"
    if not directory.resolve().is_relative_to(experiment_dir.resolve()):
        raise ExperimentError("binding directory escapes experiment")
    for key, content in _run_bindings(run).items():
        path = directory / f"{key}.json"
        expected = {"schema_version": "experiment_binding.v1", **content}
        if create:
            with suppress(FileExistsError):
                _write_manifest(path, expected)
        found = _read_manifest(path, "experiment_binding.v1")
        if found["content_sha256"] != digest(expected):
            raise ExperimentError(
                f"frozen experiment binding conflict: {key.split('-', 1)[0]}; "
                "paired inputs/settings, dataset splits and evaluation checkpoints cannot drift"
            )


def create_run(
    *,
    experiment_dir: Path,
    run_id: str,
    case_id: str,
    seed: int,
    controller_id: str,
    mask: list[str],
    inputs: dict[str, Path],
    expected_outputs: dict[str, str],
    settings: dict[str, Any],
    reward_variant: str | None = None,
) -> Path:
    validate_id(run_id)
    validate_id(controller_id)
    experiment = verify_experiment(experiment_dir)
    protocol = experiment["protocol"]
    case = protocol["cases"].get(case_id)
    if case is None or type(seed) is not int or seed not in protocol["seed_splits"][case["split"]]:
        raise ExperimentError("case/seed does not belong to its frozen split")
    if (
        not isinstance(mask, list)
        or any(not isinstance(tls, str) for tls in mask)
        or len(set(mask)) != len(mask)
    ):
        raise ExperimentError("mask must be an array of unique TLS IDs")
    snapshot = read_json(Path(experiment["project_snapshot"]["path"]))
    known_tls = {row["tls_id"] for row in snapshot["tls_inventory"]["signals"]}
    if any(tls not in known_tls for tls in mask):
        raise ExperimentError("mask contains unknown TLS IDs")
    if controller_id == "fixed_time" and (mask or "checkpoint" in inputs):
        raise ExperimentError("fixed_time must have empty intervention mask and no checkpoint")
    if controller_id.startswith("rl_") and "checkpoint" not in inputs:
        raise ExperimentError("RL evaluation requires checkpoint input")
    objective = _run_objective(experiment, controller_id, reward_variant)
    records = {validate_id(role): file_record(path) for role, path in inputs.items()}
    if set(records).intersection(experiment["shared_inputs"]):
        raise ExperimentError("run inputs cannot override shared experiment profiles")
    if not records:
        raise ExperimentError("run inputs must be explicit")
    if protocol["mode"] == "research_synthetic" and "demand" not in records:
        raise ExperimentError("research run requires intended demand, not only routed vehicles")
    if not expected_outputs or len(set(expected_outputs.values())) != len(expected_outputs):
        raise ExperimentError("expected_outputs must be non-empty with unique paths")
    directory = experiment_dir / "runs" / run_id
    if not directory.resolve().is_relative_to(experiment_dir.resolve()):
        raise ExperimentError("run directory escapes experiment through a filesystem link")
    resolved_outputs = []
    for role, relative in expected_outputs.items():
        validate_id(role)
        resolved_outputs.append(str(_output_path(directory, relative)).casefold())
    if len(set(resolved_outputs)) != len(resolved_outputs):
        raise ExperimentError("expected output paths collide on a case-insensitive filesystem")
    # JSON validity before reserving a directory; NaN/Infinity settings cannot be frozen.
    digest(settings)
    if "settings" in case and settings != case["settings"]:
        raise ExperimentError("run settings differ from the frozen case settings")
    manifest = {
        "schema_version": RUN_SCHEMA,
        "experiment_id": experiment["experiment_id"],
        "experiment_sha256": experiment["content_sha256"],
        "run_id": run_id,
        "case_id": case_id,
        "split": case["split"],
        "seed": seed,
        "controller_id": controller_id,
        "mask": sorted(mask),
        "inputs": records,
        "settings": settings,
        "expected_outputs": expected_outputs,
        "mode": protocol["mode"],
        "contracts": protocol["contracts"],
        "objective": objective,
    }
    # A failed reservation remains inspectable; do not silently relax partially frozen bindings.
    directory.mkdir(exist_ok=False)
    _check_bindings(experiment_dir, manifest, create=True)
    _write_manifest(directory / "run.json", manifest)
    return directory


def verify_run(directory: Path) -> dict[str, Any]:
    experiment = verify_experiment(directory.parent.parent)
    run = _read_manifest(directory / "run.json", RUN_SCHEMA)
    if (
        run["experiment_id"] != experiment["experiment_id"]
        or run["experiment_sha256"] != experiment["content_sha256"]
    ):
        raise ExperimentError("run belongs to another experiment identity")
    if directory.name != run["run_id"] or directory.parent.name != "runs":
        raise ExperimentError("run directory does not match run_id")
    protocol = experiment["protocol"]
    case = protocol["cases"].get(run["case_id"])
    if (
        case is None
        or run["split"] != case["split"]
        or type(run["seed"]) is not int
        or run["seed"] not in protocol["seed_splits"][case["split"]]
        or run["mode"] != protocol["mode"]
        or run["contracts"] != protocol["contracts"]
    ):
        raise ExperimentError("run metadata differs from frozen experiment protocol")
    if run["objective"] != _run_objective(
        experiment,
        run["controller_id"],
        run["objective"]["reward_variant"],
    ):
        raise ExperimentError("run objective differs from frozen profiles")
    for record in run["inputs"].values():
        _verify_file(record)
    _check_bindings(directory.parent.parent, run, create=False)
    outputs_file = directory / "outputs.json"
    if not outputs_file.exists():
        return {"state": "unsealed", "run": run}
    outputs = _read_manifest(outputs_file, OUTPUT_SCHEMA)
    if (
        outputs.get("run_sha256") != run["content_sha256"]
        or outputs.get("experiment_id") != run["experiment_id"]
        or outputs.get("run_id") != run["run_id"]
    ):
        raise ExperimentError("output manifest belongs to another run")
    if set(outputs["files"]) != set(run["expected_outputs"]):
        raise ExperimentError("sealed outputs differ from expected output roles")
    for role, relative in run["expected_outputs"].items():
        actual = file_record(_output_path(directory, relative))
        expected = outputs["files"][role]
        if (
            expected.get("path") != relative
            or actual["sha256"] != expected["sha256"]
            or actual["bytes"] != expected["bytes"]
        ):
            raise ExperimentError(f"output checksum mismatch: {role}")
    if (
        outputs.get("execution_sha256") is not None
        and sha256_file(directory / "execution.json") != outputs["execution_sha256"]
    ):
        raise ExperimentError("execution provenance checksum mismatch")
    return {"state": "outputs_verified", "run": run, "outputs": outputs}


def _read_verified_output_bytes(
    directory: Path,
    role: str,
    verified: dict[str, Any],
) -> bytes:
    run = verified["run"]
    expected_outputs = run.get("expected_outputs")
    outputs = verified.get("outputs")
    if not isinstance(expected_outputs, dict) or role not in expected_outputs:
        raise ExperimentError(f"run has no declared output role: {role}")
    if not isinstance(outputs, dict) or not isinstance(outputs.get("files"), dict):
        raise ExperimentError("sealed output manifest is malformed")
    record = outputs["files"].get(role)
    relative = expected_outputs[role]
    if (
        not isinstance(relative, str)
        or not isinstance(record, dict)
        or record.get("path") != relative
        or not isinstance(record.get("sha256"), str)
        or type(record.get("bytes")) is not int
    ):
        raise ExperimentError("sealed output record is malformed")
    output_path = _output_path(directory, relative)
    try:
        payload = output_path.read_bytes()
    except OSError as exc:
        raise ExperimentError("could not read sealed output") from exc
    if hashlib.sha256(payload).hexdigest() != record["sha256"] or len(payload) != record["bytes"]:
        raise ExperimentError("sealed output changed while being read")
    return payload


def verify_run_output(directory: Path, role: str) -> tuple[dict[str, Any], bytes | None]:
    """Verify a run once and safely read one declared output, if sealed and present."""
    role = validate_id(role)
    verified = verify_run(directory)
    if verified["state"] != "outputs_verified":
        return verified, None
    run = verified["run"]
    expected_outputs = run.get("expected_outputs")
    if not isinstance(expected_outputs, dict) or role not in expected_outputs:
        return verified, None
    return verified, _read_verified_output_bytes(directory, role, verified)


def read_verified_output(directory: Path, role: str) -> bytes:
    """Read one declared sealed output and verify the bytes returned to the caller."""
    verified, payload = verify_run_output(directory, role)
    if verified["state"] != "outputs_verified":
        raise ExperimentError("run outputs are not sealed and verified")
    if payload is None:
        raise ExperimentError(f"run has no declared output role: {role}")
    return payload


def seal_run(directory: Path) -> dict[str, Any]:
    verified = verify_run(directory)
    if verified["state"] != "unsealed":
        raise ExperimentError("run already sealed; refusing overwrite")
    run = verified["run"]
    files = {}
    for role, relative in run["expected_outputs"].items():
        record = file_record(_output_path(directory, relative))
        files[role] = {"path": relative, "sha256": record["sha256"], "bytes": record["bytes"]}
    # Inputs must still match after hashing potentially large output files.
    verify_run(directory)
    return _write_manifest(
        directory / "outputs.json",
        {
            "schema_version": OUTPUT_SCHEMA,
            "experiment_id": run["experiment_id"],
            "run_id": run["run_id"],
            "run_sha256": run["content_sha256"],
            "files": files,
            "evidence_scope": "artifact_identity_only_not_research_acceptance",
            "execution_sha256": (
                sha256_file(directory / "execution.json")
                if (directory / "execution.json").exists()
                else None
            ),
        },
    )
