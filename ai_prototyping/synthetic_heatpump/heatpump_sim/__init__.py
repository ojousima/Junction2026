"""Qualitative synthetic heat-pump temperature time-series simulator."""

from .config import DEFAULT_DURATION_SECONDS, FEATURE_COLUMNS
from .simulator import SimulationResult, simulate_snippet

__all__ = [
    "DEFAULT_DURATION_SECONDS",
    "FEATURE_COLUMNS",
    "SimulationResult",
    "simulate_snippet",
]
