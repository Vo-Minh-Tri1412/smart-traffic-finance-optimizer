from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SumoRuntimeConfig:
    sumo_binary: str = "sumo"
    netconvert_binary: str = "netconvert"


def resolve_sumo_binary(binary_name: str) -> str | None:
    direct = shutil.which(binary_name)
    if direct:
        return direct

    sumo_home = os.environ.get("SUMO_HOME")
    if not sumo_home:
        return None

    bin_dir = Path(sumo_home) / "bin"
    candidates = [bin_dir / binary_name, bin_dir / f"{binary_name}.exe"]
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return None
