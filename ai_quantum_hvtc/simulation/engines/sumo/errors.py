from __future__ import annotations


class SumoRuntimeError(RuntimeError):
    """Raised when the SUMO backend cannot export, run, or parse a simulation."""
