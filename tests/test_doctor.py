from __future__ import annotations

from pathlib import Path

from ai_quantum_hvtc.doctor import run_checks


def test_doctor_passes_for_repository_scaffold() -> None:
    root = Path(__file__).resolve().parents[1]

    results = run_checks(root)

    assert all(result.ok for result in results), [
        f"{result.name}: {result.detail}" for result in results if not result.ok
    ]
