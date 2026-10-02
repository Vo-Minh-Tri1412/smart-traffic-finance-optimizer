"""Unreal entry point for the original PBR v1 scene profile."""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
os.environ.setdefault("AIQ_PBR_PROFILE", "pbr_v1")

main = importlib.import_module("polyhaven_city_level_builder").main


RESULT = main()
