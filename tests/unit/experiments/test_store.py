from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from ai_quantum_hvtc.experiments.store import (
    ExperimentError,
    create_experiment,
    create_run,
    read_json,
    seal_run,
    validate_id,
    validate_protocol,
    verify_experiment,
    verify_run,
)
from ai_quantum_hvtc.simulation.maps.snapshot import write_project_snapshot
from ai_quantum_hvtc.simulation.maps.source import SumoMapSourceError

NET = """<net>
  <edge id="E1"><lane id="E1_0" index="0" shape="0,0 1,0"/></edge>
  <edge id="E2"><lane id="E2_0" index="0" shape="1,0 2,0"/></edge>
  <edge id=":J_0" function="internal"><lane id=":J_0_0" index="0"/></edge>
  <tlLogic id="TLS" type="static" programID="0" offset="0">
    <phase duration="10" state="G"/><phase duration="3" state="y"/>
    <phase duration="2" state="r"/>
  </tlLogic>
  <junction id="J" type="traffic_light" x="1" y="0"/>
  <connection from="E1" to="E2" fromLane="0" toLane="0" via=":J_0_0"
              tl="TLS" linkIndex="0" dir="s" state="O"/>
</net>"""

SPLIT_SEEDS = {
    "rl_train": [11],
    "rl_validation": [22],
    "coefficient_fit": [33],
    "surrogate_validation": [44],
    "final_test": [55],
}
CONTRACTS = {
    "demand": "demand.v1",
    "observation": "observation.v1",
    "reward": "reward.v1",
    "economic": "economic.v1",
    "evaluator": "evaluator.v1",
    "safety": "safety.v1",
}


@dataclass(frozen=True)
class StoreFixture:
    project: Path
    snapshot: Path
    protocol: Path
    source: Path
    input: Path
    demand: Path
    checkpoint: Path
    evaluator: Path
    reward_r0: Path
    reward_r1: Path
    experiment_root: Path
    experiment: Path
    shared_inputs: dict[str, Path]


def _protocol(
    *,
    mode: str = "debug",
    objective: dict[str, Any] | None = None,
    include_objective: bool = True,
    case_settings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cases = {
        f"case_{split}": {
            "split": split,
            "partition_group": f"group_{split}",
        }
        for split in SPLIT_SEEDS
    }
    if case_settings is not None:
        cases["case_rl_train"]["settings"] = case_settings
    protocol: dict[str, Any] = {
        "schema_version": "experiment_protocol.v1",
        "mode": mode,
        "seed_splits": {split: list(seeds) for split, seeds in SPLIT_SEEDS.items()},
        "cases": cases,
        "contracts": CONTRACTS
        if mode == "research_synthetic"
        else {role: None for role in CONTRACTS},
    }
    if include_objective:
        protocol["objective"] = objective
    return protocol


def _write_project(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "map.net.xml").write_text(NET, encoding="utf-8")
    (root / "overlay.json").write_text(
        json.dumps(
            {
                "schema_version": "semantic_overlay.v1",
                "id": "overlay",
                "name": "Infrastructure test overlay",
                "zones": [
                    {
                        "id": "Z",
                        "name": "Zone",
                        "type": "residential",
                        "anchor_edges": ["E1"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (root / "demand.json").write_text('{"status": "fixture"}', encoding="utf-8")
    descriptor = root / "project.json"
    descriptor.write_text(
        json.dumps(
            {
                "id": "project",
                "name": "Infrastructure test project",
                "version": "v1",
                "source": {"net_path": "map.net.xml"},
                "semantic_overlay_path": "overlay.json",
                "demand_config_path": "demand.json",
            }
        ),
        encoding="utf-8",
    )
    return descriptor


def _make_fixture(
    tmp_path: Path,
    *,
    mode: str = "debug",
    objective: dict[str, Any] | None = None,
    include_objective: bool = True,
    case_settings: dict[str, Any] | None = None,
    freeze_profiles: bool = False,
) -> StoreFixture:
    project = _write_project(tmp_path / "project")
    snapshot = tmp_path / "snapshot.json"
    write_project_snapshot(project, snapshot)

    protocol = tmp_path / "protocol.json"
    protocol.write_text(
        json.dumps(
            _protocol(
                mode=mode,
                objective=objective,
                include_objective=include_objective,
                case_settings=case_settings,
            )
        ),
        encoding="utf-8",
    )
    source = tmp_path / "controller.py"
    source.write_text("def controller():\n    return 'fixture'\n", encoding="utf-8")
    input_path = tmp_path / "input.json"
    input_path.write_text('{"input": "fixture"}', encoding="utf-8")
    demand = tmp_path / "intended_demand.json"
    demand.write_text('{"demand": "fixture"}', encoding="utf-8")
    checkpoint = tmp_path / "checkpoint.zip"
    checkpoint.write_bytes(b"checkpoint-fixture")

    evaluator = tmp_path / "evaluation_profile.json"
    evaluator.write_text('{"profile": "evaluation"}', encoding="utf-8")
    reward_r0 = tmp_path / "reward_r0.json"
    reward_r0.write_text('{"profile": "r0"}', encoding="utf-8")
    reward_r1 = tmp_path / "reward_r1.json"
    reward_r1.write_text('{"profile": "r1"}', encoding="utf-8")
    shared_inputs = (
        {
            "evaluation_profile": evaluator,
            "reward_r0": reward_r0,
            "reward_r1": reward_r1,
        }
        if freeze_profiles
        else {}
    )
    experiment_root = tmp_path / "experiments"
    experiment = create_experiment(
        root=experiment_root,
        experiment_id="exp_fixture",
        project_path=project,
        snapshot_path=snapshot,
        protocol_path=protocol,
        source_paths=[source],
        shared_inputs=shared_inputs,
    )
    return StoreFixture(
        project=project,
        snapshot=snapshot,
        protocol=protocol,
        source=source,
        input=input_path,
        demand=demand,
        checkpoint=checkpoint,
        evaluator=evaluator,
        reward_r0=reward_r0,
        reward_r1=reward_r1,
        experiment_root=experiment_root,
        experiment=experiment,
        shared_inputs=shared_inputs,
    )


def _run_kwargs(fixture: StoreFixture, **overrides: Any) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "experiment_dir": fixture.experiment,
        "run_id": "run_fixture",
        "case_id": "case_rl_train",
        "seed": 11,
        "controller_id": "fixed_time",
        "mask": [],
        "inputs": {"config": fixture.input},
        "expected_outputs": {"metrics": "metrics/result.json"},
        "settings": {},
    }
    kwargs.update(overrides)
    return kwargs


def _create_run(fixture: StoreFixture, **overrides: Any) -> Path:
    return create_run(**_run_kwargs(fixture, **overrides))


def _research_fixture(tmp_path: Path) -> StoreFixture:
    objective = {
        "evaluator_input": "evaluation_profile",
        "reward_inputs": {"R0": "reward_r0", "R1": "reward_r1"},
    }
    return _make_fixture(
        tmp_path,
        mode="research_synthetic",
        objective=objective,
        freeze_profiles=True,
    )


def test_debug_protocol_allows_none_or_omitted_objective() -> None:
    validate_protocol(_protocol(objective=None))
    validate_protocol(_protocol(include_objective=False))


def test_protocol_rejects_overlapping_seeds_and_cross_split_groups() -> None:
    overlapping = _protocol()
    overlapping["seed_splits"]["rl_validation"] = [11]
    with pytest.raises(ExperimentError, match="overlap"):
        validate_protocol(overlapping)

    crossing = _protocol()
    crossing["cases"]["case_rl_validation"]["partition_group"] = "group_rl_train"
    with pytest.raises(ExperimentError, match="partition_group"):
        validate_protocol(crossing)


@pytest.mark.parametrize(
    "value",
    [None, 1, "", ".", "..", "bad/name", "bad\\name", "name.", "CON", "con.txt", "LPT9.log"],
)
def test_validate_id_rejects_nonportable_artifact_ids(value: object) -> None:
    with pytest.raises(ExperimentError):
        validate_id(value)


def test_protocol_schema_and_research_objective_are_strict(tmp_path: Path) -> None:
    malformed = _protocol()
    malformed["schema_version"] = "experiment_protocol.v0"
    with pytest.raises(ExperimentError, match="schema"):
        validate_protocol(malformed)

    research_without_objective = _protocol(mode="research_synthetic", objective=None)
    with pytest.raises(ExperimentError, match="objective"):
        validate_protocol(research_without_objective)

    missing_role = _research_protocol_without_role()
    protocol_path = tmp_path / "protocol.json"
    protocol_path.write_text(json.dumps(missing_role), encoding="utf-8")
    with pytest.raises(ExperimentError, match="missing frozen objective inputs"):
        _make_fixture(
            tmp_path,
            mode="research_synthetic",
            objective=missing_role["objective"],
            freeze_profiles=True,
        )


def _research_protocol_without_role() -> dict[str, Any]:
    protocol = _protocol(
        mode="research_synthetic",
        objective={
            "evaluator_input": "evaluation_profile",
            "reward_inputs": {"R0": "reward_missing", "R1": "reward_r1"},
        },
    )
    return protocol


def test_create_experiment_and_run_freeze_identity(tmp_path: Path) -> None:
    fixture = _make_fixture(tmp_path)
    experiment = verify_experiment(fixture.experiment)
    assert experiment["experiment_id"] == "exp_fixture"
    assert experiment["evidence_scope"] == "identity_only_not_scientific_acceptance"

    run = _create_run(fixture)
    verified = verify_run(run)
    assert verified["state"] == "unsealed"
    assert verified["run"]["split"] == "rl_train"
    assert verified["run"]["objective"] == {
        "reward_variant": None,
        "reward_profile_sha256": None,
        "evaluator_profile_sha256": None,
    }


def test_duplicate_experiment_and_run_ids_never_overwrite(tmp_path: Path) -> None:
    fixture = _make_fixture(tmp_path)
    experiment_before = (fixture.experiment / "experiment.json").read_bytes()
    with pytest.raises(FileExistsError):
        create_experiment(
            root=fixture.experiment_root,
            experiment_id="exp_fixture",
            project_path=fixture.project,
            snapshot_path=fixture.snapshot,
            protocol_path=fixture.protocol,
            source_paths=[fixture.source],
        )
    assert (fixture.experiment / "experiment.json").read_bytes() == experiment_before

    run = _create_run(fixture)
    run_before = (run / "run.json").read_bytes()
    with pytest.raises(FileExistsError):
        _create_run(fixture)
    assert (run / "run.json").read_bytes() == run_before


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"case_id": "case_unknown"}, "case/seed"),
        ({"seed": 22}, "case/seed"),
        ({"mask": ["UNKNOWN_TLS"]}, "unknown TLS"),
        ({"mask": ["TLS", "TLS"]}, "unique"),
    ],
)
def test_run_rejects_wrong_case_seed_and_mask(
    tmp_path: Path, overrides: dict[str, Any], message: str
) -> None:
    fixture = _make_fixture(tmp_path)
    with pytest.raises(ExperimentError, match=message):
        _create_run(fixture, **overrides)


def test_run_controller_and_reward_variant_gates_are_fail_closed(tmp_path: Path) -> None:
    fixture = _make_fixture(tmp_path)
    with pytest.raises(ExperimentError, match="fixed_time"):
        _create_run(fixture, mask=["TLS"])
    with pytest.raises(ExperimentError, match="fixed_time"):
        _create_run(fixture, inputs={"checkpoint": fixture.checkpoint})

    research = _research_fixture(tmp_path / "research")
    rl_inputs = {"demand": research.demand, "checkpoint": research.checkpoint}
    with pytest.raises(ExperimentError, match="explicit frozen reward"):
        _create_run(research, controller_id="rl_ppo", inputs=rl_inputs)
    with pytest.raises(ExperimentError, match="not frozen"):
        _create_run(
            research,
            controller_id="rl_ppo",
            inputs=rl_inputs,
            reward_variant="R9",
        )
    with pytest.raises(ExperimentError, match="fixed_time"):
        _create_run(
            research,
            inputs={"demand": research.demand},
            reward_variant="R0",
        )

    run = _create_run(
        research,
        controller_id="rl_ppo",
        inputs=rl_inputs,
        reward_variant="R1",
    )
    manifest = read_json(run / "run.json")
    assert manifest["objective"]["reward_variant"] == "R1"
    assert (
        manifest["objective"]["reward_profile_sha256"]
        == hashlib.sha256(research.reward_r1.read_bytes()).hexdigest()
    )
    assert (
        manifest["objective"]["evaluator_profile_sha256"]
        == hashlib.sha256(research.evaluator.read_bytes()).hexdigest()
    )


def test_case_settings_are_frozen_into_run_identity(tmp_path: Path) -> None:
    fixture = _make_fixture(tmp_path, case_settings={"scenario": "normal", "horizon": 10})
    with pytest.raises(ExperimentError, match="settings"):
        _create_run(fixture, settings={"scenario": "normal", "horizon": 11})
    run = _create_run(fixture, settings={"scenario": "normal", "horizon": 10})
    assert read_json(run / "run.json")["settings"] == {"scenario": "normal", "horizon": 10}


def test_bindings_freeze_same_case_seed_data_and_runtime_settings(tmp_path: Path) -> None:
    fixture = _make_fixture(tmp_path)
    _create_run(
        fixture,
        run_id="binding_a",
        inputs={"demand": fixture.demand, "routes": fixture.input},
        settings={"scenario": "normal"},
    )
    alternate_demand = tmp_path / "alternate_demand.json"
    alternate_demand.write_text('{"demand": "alternate"}', encoding="utf-8")

    with pytest.raises(ExperimentError, match="paired inputs/settings"):
        _create_run(
            fixture,
            run_id="binding_b",
            inputs={"demand": alternate_demand, "routes": fixture.input},
            settings={"scenario": "normal"},
        )
    assert (fixture.experiment / "runs" / "binding_b").is_dir()
    assert not (fixture.experiment / "runs" / "binding_b" / "run.json").exists()

    with pytest.raises(ExperimentError, match="paired inputs/settings"):
        _create_run(
            fixture,
            run_id="binding_c",
            controller_id="actuated",
            inputs={"demand": fixture.demand, "routes": fixture.input},
            settings={"scenario": "peak"},
        )

    run = _create_run(
        fixture,
        run_id="binding_same_data_other_controller",
        controller_id="actuated",
        inputs={"demand": fixture.demand, "routes": fixture.input},
        settings={"scenario": "normal"},
    )
    assert read_json(run / "run.json")["controller_id"] == "actuated"


def test_bindings_keep_a_data_hash_in_one_split(tmp_path: Path) -> None:
    fixture = _make_fixture(tmp_path)
    _create_run(
        fixture,
        run_id="train_binding",
        inputs={"demand": fixture.demand, "routes": fixture.input},
    )
    with pytest.raises(ExperimentError, match="dataset splits"):
        _create_run(
            fixture,
            run_id="validation_binding",
            case_id="case_rl_validation",
            seed=22,
            inputs={"demand": fixture.demand, "routes": fixture.input},
        )
    assert not (fixture.experiment / "runs" / "validation_binding" / "run.json").exists()


def test_policy_checkpoint_binding_is_fixed_across_masks(tmp_path: Path) -> None:
    fixture = _research_fixture(tmp_path)
    inputs = {"demand": fixture.demand, "checkpoint": fixture.checkpoint}
    _create_run(
        fixture,
        run_id="policy_a",
        controller_id="rl_ppo",
        inputs=inputs,
        reward_variant="R1",
    )
    _create_run(
        fixture,
        run_id="policy_same_checkpoint",
        controller_id="rl_ppo",
        mask=["TLS"],
        inputs=inputs,
        reward_variant="R1",
    )

    alternate_checkpoint = tmp_path / "checkpoint_alternate.zip"
    alternate_checkpoint.write_bytes(b"different-checkpoint")
    with pytest.raises(ExperimentError, match="evaluation checkpoints"):
        _create_run(
            fixture,
            run_id="policy_different_checkpoint",
            controller_id="rl_ppo",
            mask=["TLS"],
            inputs={"demand": fixture.demand, "checkpoint": alternate_checkpoint},
            reward_variant="R1",
        )


@pytest.mark.parametrize("filename", ["protocol.json", "controller.py"])
def test_protocol_and_source_byte_changes_invalidate_experiment(
    tmp_path: Path, filename: str
) -> None:
    fixture = _make_fixture(tmp_path)
    path = fixture.protocol if filename == "protocol.json" else fixture.source
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(ExperimentError, match="checksum"):
        verify_experiment(fixture.experiment)


@pytest.mark.parametrize("filename", ["project.json", "map.net.xml", "overlay.json", "demand.json"])
def test_project_input_byte_changes_invalidate_experiment(tmp_path: Path, filename: str) -> None:
    fixture = _make_fixture(tmp_path)
    path = fixture.project.parent / filename
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises((ExperimentError, SumoMapSourceError), match="mismatch"):
        verify_experiment(fixture.experiment)


def test_run_input_byte_changes_invalidate_run(tmp_path: Path) -> None:
    fixture = _make_fixture(tmp_path)
    run = _create_run(fixture)
    fixture.input.write_bytes(fixture.input.read_bytes() + b"\n")
    with pytest.raises(ExperimentError, match="checksum"):
        verify_run(run)


@pytest.mark.parametrize("role", ["evaluation_profile", "reward_r0", "reward_r1"])
def test_shared_objective_profile_mutation_invalidates_identity(tmp_path: Path, role: str) -> None:
    fixture = _research_fixture(tmp_path)
    run = _create_run(
        fixture,
        controller_id="rl_ppo",
        inputs={"demand": fixture.demand, "checkpoint": fixture.checkpoint},
        reward_variant="R1",
    )
    fixture.shared_inputs[role].write_bytes(fixture.shared_inputs[role].read_bytes() + b"\n")
    with pytest.raises(ExperimentError, match="checksum"):
        verify_experiment(fixture.experiment)
    with pytest.raises(ExperimentError, match="checksum"):
        verify_run(run)


def test_missing_expected_output_keeps_run_unsealed_and_cannot_be_sealed(
    tmp_path: Path,
) -> None:
    fixture = _make_fixture(tmp_path)
    run = _create_run(fixture)
    assert verify_run(run)["state"] == "unsealed"
    with pytest.raises(FileNotFoundError):
        seal_run(run)
    assert not (run / "outputs.json").exists()


def test_sealed_output_is_verified_and_mutation_is_rejected(tmp_path: Path) -> None:
    fixture = _make_fixture(tmp_path)
    run = _create_run(fixture)
    output = run / "metrics" / "result.json"
    output.parent.mkdir()
    output.write_text('{"score": 1}', encoding="utf-8")
    sealed = seal_run(run)
    assert sealed["evidence_scope"] == "artifact_identity_only_not_research_acceptance"
    assert verify_run(run)["state"] == "outputs_verified"
    with pytest.raises(ExperimentError, match="already sealed"):
        seal_run(run)

    outputs_before = (run / "outputs.json").read_bytes()
    output.write_text('{"score": 2}', encoding="utf-8")
    with pytest.raises(ExperimentError, match="output checksum"):
        verify_run(run)
    assert (run / "outputs.json").read_bytes() == outputs_before


def test_corrupt_sealed_output_manifest_is_rejected(tmp_path: Path) -> None:
    fixture = _make_fixture(tmp_path)
    run = _create_run(fixture)
    output = run / "metrics" / "result.json"
    output.parent.mkdir()
    output.write_text('{"score": 1}', encoding="utf-8")
    seal_run(run)
    outputs = json.loads((run / "outputs.json").read_text(encoding="utf-8"))
    outputs["files"]["metrics"]["path"] = "other.json"
    (run / "outputs.json").write_text(json.dumps(outputs), encoding="utf-8")
    with pytest.raises(ExperimentError, match="manifest checksum"):
        verify_run(run)


@pytest.mark.parametrize("relative", ["", "../outside.json", "metrics\\result.json", "run.json"])
def test_output_paths_cannot_escape_or_replace_lifecycle_metadata(
    tmp_path: Path, relative: str
) -> None:
    fixture = _make_fixture(tmp_path)
    with pytest.raises(ExperimentError):
        _create_run(fixture, expected_outputs={"metrics": relative})


def test_output_paths_reject_case_insensitive_collisions(tmp_path: Path) -> None:
    fixture = _make_fixture(tmp_path)
    with pytest.raises(ExperimentError, match="case-insensitive"):
        _create_run(
            fixture,
            expected_outputs={
                "metrics_lower": "metrics/result.json",
                "metrics_upper": "METRICS/RESULT.JSON",
            },
        )


def test_duplicate_json_keys_and_nonfinite_numbers_are_rejected(tmp_path: Path) -> None:
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text('{"key": 1, "key": 2}', encoding="utf-8")
    with pytest.raises(ExperimentError, match="duplicate JSON key"):
        read_json(duplicate)

    nonfinite = tmp_path / "nonfinite.json"
    nonfinite.write_text('{"value": NaN}', encoding="utf-8")
    with pytest.raises(ExperimentError, match="non-finite"):
        read_json(nonfinite)


def test_experiment_and_run_directory_names_are_bound_to_manifest_ids(tmp_path: Path) -> None:
    fixture = _make_fixture(tmp_path)
    renamed_experiment = fixture.experiment_root / "renamed"
    fixture.experiment.rename(renamed_experiment)
    with pytest.raises(ExperimentError, match="experiment directory"):
        verify_experiment(renamed_experiment)

    fixture = _make_fixture(tmp_path / "second")
    run = _create_run(fixture)
    renamed_run = fixture.experiment / "runs" / "renamed"
    run.rename(renamed_run)
    with pytest.raises(ExperimentError, match="run directory"):
        verify_run(renamed_run)
