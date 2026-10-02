import json
import zipfile
from pathlib import Path

import pytest

from scripts.data.prepare_demand_inventory import (
    build_inventory,
    clock_seconds,
    population_grid_inventory,
    validate_spec,
)


def test_committed_spec() -> None:
    spec = json.loads(Path("configs/demand/current_roi_dataset.v1.json").read_text())
    validate_spec(spec)
    assert spec["quantity_policy"]["base_person_trips"] is None
    assert not spec["quantity_policy"]["observed_OD_available"]


def test_split_geometry_not_duplicate_facility_capacity() -> None:
    result = build_inventory({"zones": [
        {"id": "a", "source_element_id": "way/1", "type": "education"},
        {"id": "b", "source_element_id": "way/1", "type": "education"},
        {"id": "c", "type": "neutral"},
    ]})
    assert result["summary"]["candidate_parents"] == 2
    parent = next(p for p in result["parents"] if p["parent_id"] == "way/1")
    assert parent["entity_ids"] == ["a", "b"]
    assert parent["daily_trips"] is None
    assert parent["reviewed_gates"] == []


def test_duplicate_entity_rejected() -> None:
    with pytest.raises(ValueError, match="Duplicate entity"):
        build_inventory({"zones": [{"id": "a", "type": "neutral"}] * 2})


@pytest.mark.parametrize("value", ["25:00", "24:01", "12:60", "-1:00"])
def test_invalid_clock(value: str) -> None:
    with pytest.raises(ValueError):
        clock_seconds(value)


def test_midnight_endpoint() -> None:
    assert clock_seconds("24:00") == 86400


def test_seed_leakage_rejected() -> None:
    spec = json.loads(Path("configs/demand/current_roi_dataset.v1.json").read_text())
    spec["random_seeds"]["test"] = spec["random_seeds"]["train"]
    with pytest.raises(ValueError, match="overlap"):
        validate_spec(spec)


def test_population_prior_is_grid_diagnostic(tmp_path: Path) -> None:
    path = tmp_path / "grid.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("grid.csv", "X,Y,Z\n106.7,10.7,123.5\n100,20,999\n106.7,10.7,-999\n")
    result = population_grid_inventory(path, [106.69, 10.69, 106.79, 10.78])
    assert result["cell_count"] == 1
    assert result["population_sum_diagnostic"] == 123.5
    assert "not current" in result["claim"]
