from __future__ import annotations

import json
import sys
from pathlib import Path
from types import ModuleType

from ai_quantum_hvtc.experiments import cli


def _payload(capsys) -> dict[str, object]:
    output = capsys.readouterr().out
    assert output.endswith("\n")
    lines = output.splitlines()
    assert lines
    return json.loads(lines[-1])


def test_create_expands_explicit_source_directories(monkeypatch, tmp_path: Path, capsys) -> None:
    source_dir = tmp_path / "source"
    nested = source_dir / "nested"
    nested.mkdir(parents=True)
    (source_dir / "main.py").write_text("main", encoding="utf-8")
    (nested / "helper.py").write_text("helper", encoding="utf-8")
    (nested / "notes.txt").write_text("ignored", encoding="utf-8")
    explicit = tmp_path / "config.json"
    explicit.write_text("{}", encoding="utf-8")
    profile = tmp_path / "profile.toml"
    profile.write_text("profile", encoding="utf-8")
    captured: dict[str, object] = {}

    def fake_create_experiment(**kwargs):
        captured.update(kwargs)
        return tmp_path / "experiments" / "EXP-001"

    monkeypatch.setattr(cli.store, "create_experiment", fake_create_experiment)

    code = cli.main(
        [
            "create",
            "--root",
            str(tmp_path / "experiments"),
            "--experiment-id",
            "EXP-001",
            "--project",
            str(explicit),
            "--snapshot",
            str(explicit),
            "--protocol",
            str(explicit),
            "--source",
            str(source_dir),
            "--source",
            str(explicit),
            "--shared-input",
            f"reward={profile}",
        ]
    )

    assert code == 0
    assert captured["source_paths"] == [
        source_dir / "main.py",
        nested / "helper.py",
        explicit,
    ]
    assert captured["shared_inputs"] == {"reward": profile}
    payload = _payload(capsys)
    assert payload["status"] == "ok"
    assert payload["experiment"] == str(tmp_path / "experiments" / "EXP-001")


def test_prepare_run_resolves_input_paths_from_request_file(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    request_dir = tmp_path / "requests"
    request_dir.mkdir()
    request = request_dir / "run.json"
    request.write_text(
        json.dumps(
            {
                "run_id": "RUN-001",
                "case_id": "case-a",
                "seed": 7,
                "controller_id": "fixed_time",
                "mask": [],
                "inputs": {"routes": "../routes.rou.xml"},
                "expected_outputs": {"summary": "results/summary.json"},
                "settings": {"horizon_seconds": 60},
                "reward_variant": None,
            }
        ),
        encoding="utf-8",
    )
    captured: dict[str, object] = {}

    def fake_create_run(**kwargs):
        captured.update(kwargs)
        return tmp_path / "experiment" / "runs" / "RUN-001"

    monkeypatch.setattr(cli.store, "create_run", fake_create_run)

    code = cli.main(
        [
            "prepare-run",
            "--experiment",
            str(tmp_path / "experiment"),
            "--request",
            str(request),
        ]
    )

    assert code == 0
    assert captured["inputs"] == {"routes": (tmp_path / "routes.rou.xml").resolve()}
    assert captured["expected_outputs"] == {"summary": "results/summary.json"}
    assert captured["reward_variant"] is None
    assert _payload(capsys)["run"].endswith("RUN-001")


def test_malformed_request_returns_compact_json_without_traceback(
    tmp_path: Path,
    capsys,
) -> None:
    request = tmp_path / "bad.json"
    request.write_text("{", encoding="utf-8")

    code = cli.main(
        [
            "prepare-run",
            "--experiment",
            str(tmp_path / "experiment"),
            "--request",
            str(request),
        ]
    )

    assert code == 1
    payload = _payload(capsys)
    assert payload["status"] == "error"
    assert "invalid JSON" in payload["error"]


def test_prepare_and_execute_debug_use_lazy_executor(monkeypatch, tmp_path: Path, capsys) -> None:
    module_name = "ai_quantum_hvtc.experiments.executor"
    executor = ModuleType(module_name)
    calls: dict[str, object] = {}

    def fake_prepare_debug_run(**kwargs):
        calls["prepare"] = kwargs
        return tmp_path / "experiment" / "runs" / "RUN-001"

    def fake_execute_debug_run(directory: Path):
        calls["execute"] = directory
        return {"state": "outputs_verified"}

    executor.prepare_debug_run = fake_prepare_debug_run
    executor.execute_debug_run = fake_execute_debug_run
    monkeypatch.setitem(sys.modules, module_name, executor)
    ledger = tmp_path / "intended_demand_ledger.json"

    assert (
        cli.main(
            [
                "prepare-debug",
                "--experiment",
                str(tmp_path / "experiment"),
                "--run-id",
                "RUN-001",
                "--case",
                "case-a",
                "--seed",
                "7",
                "--routes",
                str(tmp_path / "routes.rou.xml"),
                "--horizon-seconds",
                "60",
                "--step-length",
                "1.0",
                "--intended-demand-ledger",
                str(ledger),
            ]
        )
        == 0
    )
    assert cli.main(["run-debug", "--run", str(tmp_path / "experiment" / "runs" / "RUN-001")]) == 0
    assert calls["prepare"]["step_length_seconds"] == 1.0
    assert calls["prepare"]["intended_demand_ledger"] == ledger
    assert calls["execute"] == tmp_path / "experiment" / "runs" / "RUN-001"
    assert _payload(capsys)["result"]["state"] == "outputs_verified"


def test_module_entrypoint_routes_experiments(monkeypatch) -> None:
    from ai_quantum_hvtc import __main__

    called: list[list[str]] = []

    def fake_main(argv: list[str]) -> int:
        called.append(argv)
        return 17

    monkeypatch.setattr("ai_quantum_hvtc.experiments.cli.main", fake_main)

    assert __main__.main(["experiments", "verify-run", "--run", "RUN-001"]) == 17
    assert called == [["verify-run", "--run", "RUN-001"]]
