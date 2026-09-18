"""Build candidate parent-facility inventory without inventing gates or OD volumes."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


def clock_seconds(value: str) -> int:
    hour, minute = (int(part) for part in value.split(":"))
    if not (0 <= hour <= 24 and 0 <= minute < 60) or (hour == 24 and minute != 0):
        raise ValueError(f"Invalid clock time: {value}")
    return hour * 3600 + minute * 60


def validate_spec(spec: dict[str, Any]) -> None:
    if spec["schema_version"] != "current_roi_demand_dataset_spec.v1":
        raise ValueError("Unsupported dataset specification")
    if set(spec["boundary_classes"]) != {"II", "IE", "EI", "EE"}:
        raise ValueError("All four boundary classes are required")
    seeds = [seed for values in spec["random_seeds"].values() for seed in values]
    if len(seeds) != len(set(seeds)):
        raise ValueError("Seed splits overlap")
    purposes: set[str] = set()
    for profile in spec["profiles"]:
        if profile["purpose"] in purposes:
            raise ValueError("Duplicate purpose")
        purposes.add(profile["purpose"])
        if len(profile["directions"]) != len(profile["windows"]):
            raise ValueError("Each window needs a direction")
        for start, end in profile["windows"]:
            if clock_seconds(start) >= clock_seconds(end):
                raise ValueError("Time windows must be nonempty within the day")
        if not profile["windows"] and not profile.get("event_policy"):
            raise ValueError("Unscheduled purposes need an event policy")


def build_inventory(overlay: dict[str, Any]) -> dict[str, Any]:
    parents: dict[str, dict[str, Any]] = {}
    seen_ids: set[str] = set()
    for zone in overlay["zones"]:
        entity_id = zone["id"]
        if entity_id in seen_ids:
            raise ValueError(f"Duplicate entity: {entity_id}")
        seen_ids.add(entity_id)
        parent_id = zone.get("source_element_id") or f"unresolved:{entity_id}"
        parent = parents.setdefault(parent_id, {
            "parent_id": parent_id,
            "entity_ids": [], "names": [], "zone_types": [],
            "status": "candidate_parent_not_reviewed_facility",
            "capacity_persons": None, "daily_trips": None, "reviewed_gates": [],
        })
        parent["entity_ids"].append(entity_id)
        if zone.get("name") and zone["name"] not in parent["names"]:
            parent["names"].append(zone["name"])
        if zone["type"] not in parent["zone_types"]:
            parent["zone_types"].append(zone["type"])
    for parent in parents.values():
        parent["entity_ids"].sort()
        parent["demand_eligible"] = any(t != "neutral" for t in parent["zone_types"])
        parent["needs_type_review"] = len(parent["zone_types"]) > 1
    return {
        "schema_version": "current_roi_demand_inventory.v1",
        "claim": "Geometry grouping only; no current population, gates or OD counts inferred.",
        "summary": {
            "entities": len(seen_ids), "candidate_parents": len(parents),
            "multi_piece_parents": sum(len(p["entity_ids"]) > 1 for p in parents.values()),
            "zone_type_counts": dict(Counter(z["type"] for z in overlay["zones"])),
            "observed_od_rows": 0, "production_ready": False,
        },
        "parents": [parents[key] for key in sorted(parents)],
    }


def population_grid_inventory(path: Path, bbox: list[float]) -> dict[str, Any]:
    """Inspect WorldPop XYZ centers in the diagnostic bbox, not an ROI population census."""
    west, south, east, north = bbox
    if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        raise ValueError("Invalid geographic bbox")
    rows = []
    with zipfile.ZipFile(path) as archive:
        members = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if len(members) != 1:
            raise ValueError("Expected one WorldPop XYZ CSV")
        with archive.open(members[0]) as stream:
            for row in csv.DictReader(io.TextIOWrapper(stream, encoding="utf-8-sig")):
                x, y, z = (float(row[key]) for key in ("X", "Y", "Z"))
                if not all(math.isfinite(value) for value in (x, y, z)):
                    raise ValueError("Nonfinite population grid value")
                if west <= x <= east and south <= y <= north and z >= 0:
                    rows.append({"longitude": x, "latitude": y, "population_2020": z})
    return {
        "source_id": "WORLDPOP-VNM-2020-1KM",
        "archive_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "selection": "cell_center_in_diagnostic_bbox_no_partial_cell_correction",
        "year": 2020,
        "cell_count": len(rows),
        "population_sum_diagnostic": math.fsum(row["population_2020"] for row in rows),
        "claim": "Historical modeled grid population; not current ROI residents or trip counts.",
        "cells": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--worldpop-xyz-zip", type=Path)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    validate_spec(config)
    project_path = ROOT / config["map_project"]
    project = json.loads(project_path.read_text(encoding="utf-8"))
    overlay_path = project_path.parent / project["semantic_overlay_path"]
    result = build_inventory(json.loads(overlay_path.read_text(encoding="utf-8")))
    result["provenance"] = {
        "project_id": project["id"],
        "overlay_sha256": hashlib.sha256(overlay_path.read_bytes()).hexdigest(),
        "dataset_spec_sha256": hashlib.sha256(args.config.read_bytes()).hexdigest(),
    }
    if args.worldpop_xyz_zip:
        result["population_prior"] = population_grid_inventory(
            args.worldpop_xyz_zip, config["geographic_bbox_diagnostic_only"]
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result["summary"], indent=2))


if __name__ == "__main__":
    main()
