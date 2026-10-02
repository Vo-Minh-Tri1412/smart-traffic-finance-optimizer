"""Unreal entry point for the P11 PBR hero_v2 scene profile."""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
os.environ.setdefault("AIQ_PBR_PROFILE", "hero_v2")

main = importlib.import_module("polyhaven_city_level_builder").main


RESULT = main()
