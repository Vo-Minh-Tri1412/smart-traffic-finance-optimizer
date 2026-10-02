from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest

import ai_quantum_hvtc.dashboard.store as dashboard_store
from ai_quantum_hvtc.dashboard.services import run_simulation
from ai_quantum_hvtc.dashboard.store import RunStore
from ai_quantum_hvtc.simulation.domain import DistrictSpec
from ai_quantum_hvtc.simulation.metrics import SimulationResult
from ai_quantum_hvtc.simulation.specs import load_district_spec

SPEC_PATH = Path("tests/fixtures/specs/toy_public_district_v1.json")


def _run_inputs() -> tuple[DistrictSpec, SimulationResult]:
    spec = load_district_spec(SPEC_PATH)
    result = run_simulation(
        spec=spec,
        scenario_id="normal_weekday",
        controller_id="fixed_time",
        engine_id="reference",
        seed=42,
    )
    return spec, result


def test_duplicate_partial_run_preserves_sentinel_and_fails_before_serialization(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec, result = _run_inputs()
    runs_dir = tmp_path / "runs"
    target = runs_dir / "DUPLICATE-RUN"
    target.mkdir(parents=True)
    sentinel = target / "reviewed-output.bin"
    sentinel.write_bytes(b"do not overwrite")
    store = RunStore(runs_dir)

    def fail_if_serialized(*_args: object, **_kwargs: object) -> None:
        pytest.fail("duplicate run must be rejected before invoking serializers")

    monkeypatch.setattr(dashboard_store, "result_to_json", fail_if_serialized)
    monkeypatch.setattr(dashboard_store, "result_to_trace_jsonl", fail_if_serialized)

    with pytest.raises(FileExistsError, match="refusing to overwrite or resume"):
        store.save_run(
            result=result,
            spec=spec,
            district_id=spec.metadata.district_id,
            run_id="DUPLICATE-RUN",
        )

    assert sentinel.read_bytes() == b"do not overwrite"
    assert sorted(path.name for path in target.iterdir()) == [sentinel.name]


def test_concurrent_saves_reserve_a_run_id_for_exactly_one_writer(tmp_path: Path) -> None:
    spec, result = _run_inputs()
    store = RunStore(tmp_path / "runs")
    barrier = Barrier(4)

    def save() -> str:
        barrier.wait()
        try:
            store.save_run(
                result=result,
                spec=spec,
                district_id=spec.metadata.district_id,
                run_id="CONCURRENT-RUN",
            )
        except FileExistsError:
            return "collision"
        return "created"

    with ThreadPoolExecutor(max_workers=4) as executor:
        outcomes = list(executor.map(lambda _index: save(), range(4)))

    assert outcomes.count("created") == 1
    assert outcomes.count("collision") == 3
    target = store.run_dir("CONCURRENT-RUN")
    assert {path.name for path in target.iterdir()} == {
        dashboard_store.META_FILE,
        dashboard_store.RESULT_FILE,
        dashboard_store.TRACE_FILE,
    }
