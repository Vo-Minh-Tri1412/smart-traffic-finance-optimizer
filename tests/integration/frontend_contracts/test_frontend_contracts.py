from __future__ import annotations

import json
from pathlib import Path

CONTRACT_DIR = Path("frontend/contracts")
MOCK_DIR = Path("frontend/mock-data")


def test_frontend_contract_files_are_valid_json() -> None:
    for path in CONTRACT_DIR.glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["$schema"].startswith("https://json-schema.org/")
        assert data["type"] == "object"


def test_mock_trace_frames_include_required_contract_fields() -> None:
    schema = json.loads((CONTRACT_DIR / "simulation_trace.schema.json").read_text(encoding="utf-8"))
    required = set(schema["required"])
    rows = [
        json.loads(line)
        for line in (MOCK_DIR / "sample_simulation_trace.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]

    assert rows
    assert required.issubset(rows[0])


def test_mock_summary_files_include_required_contract_fields() -> None:
    for name in ["metrics_summary", "public_finance_summary", "district_spec"]:
        schema = json.loads((CONTRACT_DIR / f"{name}.schema.json").read_text(encoding="utf-8"))
        sample = json.loads((MOCK_DIR / f"sample_{name}.json").read_text(encoding="utf-8"))
        assert set(schema["required"]).issubset(sample)
