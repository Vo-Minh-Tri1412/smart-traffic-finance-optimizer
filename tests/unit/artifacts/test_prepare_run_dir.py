from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest

from scripts.artifacts.prepare_run_dir import main, prepare_run_dir


def test_existing_run_metadata_and_results_are_never_overwritten(tmp_path: Path) -> None:
    run = prepare_run_dir("RUN-001", "rl", tmp_path)
    assert (
        json.loads((run / "run_config.json").read_text())["artifact_kind"] == "management_scaffold"
    )
    (run / "run_config.json").write_bytes(b"reviewed experiment metadata")
    (run / "artifacts" / "checkpoint.bin").write_bytes(b"important checkpoint")
    before = {p.relative_to(run): p.read_bytes() for p in run.rglob("*") if p.is_file()}
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        prepare_run_dir("RUN-001", "rl", tmp_path)
    assert {p.relative_to(run): p.read_bytes() for p in run.rglob("*") if p.is_file()} == before


@pytest.mark.parametrize(
    "run_id",
    [
        "",
        ".",
        "..",
        "../escape",
        "a/b",
        "a\\b",
        "C:\\escape",
        "trailing.",
        "trailing ",
        "CON",
        "nul.json",
        "LPT1",
        "COM9.txt",
        "bad:id",
        "a" * 129,
    ],
)
def test_nonportable_or_escaping_run_ids_fail_without_writes(tmp_path: Path, run_id: str) -> None:
    root = tmp_path / "runs"
    with pytest.raises(ValueError, match="run_id"):
        prepare_run_dir(run_id, "rl", root)
    assert not root.exists()


def test_api_validates_stream_before_writing(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    with pytest.raises(ValueError, match="stream"):
        prepare_run_dir("RUN-001", "../outside", root)
    assert not root.exists()


def test_concurrent_creators_have_exactly_one_owner(tmp_path: Path) -> None:
    barrier = Barrier(4)

    def create() -> str:
        barrier.wait()
        try:
            prepare_run_dir("CONCURRENT-001", "rl", tmp_path)
        except FileExistsError:
            return "collision"
        return "created"

    with ThreadPoolExecutor(max_workers=4) as executor:
        outcomes = list(executor.map(lambda _: create(), range(4)))
    assert outcomes.count("created") == 1
    assert outcomes.count("collision") == 3
    metadata = json.loads((tmp_path / "rl/CONCURRENT-001/run_config.json").read_text())
    assert metadata["run_id"] == "CONCURRENT-001"


def test_partial_initialization_keeps_reservation(tmp_path: Path, monkeypatch) -> None:
    def fail_write(*args, **kwargs):
        raise OSError("simulated storage failure")

    monkeypatch.setattr("scripts.artifacts.prepare_run_dir.write_json", fail_write)
    with pytest.raises(OSError, match="storage failure"):
        prepare_run_dir("PARTIAL-001", "rl", tmp_path)
    assert (tmp_path / "rl/PARTIAL-001").is_dir()
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        prepare_run_dir("PARTIAL-001", "rl", tmp_path)


def test_cli_reports_duplicate_as_failure(tmp_path: Path, capsys) -> None:
    args = ["--run-id", "CLI-001", "--stream", "rl", "--root", str(tmp_path)]
    assert main(args) == 0
    capsys.readouterr()
    assert main(args) == 1
    output = capsys.readouterr()
    assert "[OK]" not in output.out
    assert "refusing to overwrite" in output.err
