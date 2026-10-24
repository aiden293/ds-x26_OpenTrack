"""App-facing policy decisions, read by src/predict.py.

Reported metrics stay as evaluated in Phase 6 (reports/metrics.json); these overrides
were decided after looking at 2025 test results and are documented as such.
"""
from src.clean import DEMO_TYPES

# On-time probability: the original train-only classifier failed overall on 2025 test
# (AUC 0.684, Brier 0.256 vs constant 0.249), driven by Parking Enforcement drift
# (on-time 0.46 -> 0.24). On the 5 demo types it held up (AUC 0.869, Brier 0.135 vs
# constant 0.223, ECE 0.049; reports/recalibration.json). Show p_ontime only there.
ONTIME_TYPES = set(DEMO_TYPES)

# p80 falls back to baseline for these types: ML p80 pinball was worse on 2025 test
# (Street Light Outages: +3.03 days, 95% CI [2.52, 3.55]).
P80_BASELINE_TYPES = {"Street Light Outages"}
