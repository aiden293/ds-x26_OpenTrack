# CivicPulse: handoff for the Streamlit app

## Files you need
| File | In git? | What |
|---|---|---|
| `src/` (whole folder) | yes | `predict.py`, `similar.py` and the modules they import |
| `models/*.joblib`, `models/*.json`, `models/state_snapshot.parquet` | yes | final models (fit on 2022-2025), lookups, `choices.json`, `meta.json` |
| `data/processed/cases_for_app.parquet` | **yes (96 MiB)** | 1,099,534 closed cases for similar-case lookup; included in the repository |
| `reports/metrics.json`, `reports/*.png` | yes | evaluated metrics and charts to quote |

Environment: Python 3.14, `pip install -r requirements.txt`. Run from the repo root.

## API
```python
from datetime import datetime
from src.predict import predict
from src.similar import similar_cases

predict("Request for Pothole Repair", "Dorchester", datetime(2026, 10, 26, 10, 0))
# {'p50': 0.92, 'p80': 2.49, 'baseline_p50': 1.02, 'baseline_p80': 4.87,
#  'target_days': 1.0, 'p_ontime': 0.586, 'n_support': 29601, 'used_model': 'ml',
#  'p80_used_model': 'ml', 'baseline_level': 'type', 'state_time': '2025-10-01 00:00:00'}

similar_cases("Request for Pothole Repair", "Dorchester", datetime(2026, 10, 26), k=10)
# DataFrame: case_enquiry_id, type, neighborhood, open_dt, closed_dt,
#            resolution_days, closure_reason, match_level
```
- All durations are **days** (float). `p50` = typical, `p80` = "8 in 10 were done by".
- `p_ontime` is `None` except for the 5 demo types, and when the type has no city target.
- `target_days` is an estimate of the city's SLA (2025 median for that type and weekday).
- `used_model` / `p80_used_model`: `"baseline"` means the historical per-type percentile.
  Street Light Outages always uses baseline for p80.
- Extra keys (`p80_used_model`, `baseline_level`, `state_time`) are safe to ignore.
- First call loads models (~1 s); later calls ~15 ms. `similar_cases` first call ~0.3 s.
- Dropdowns: use `models/choices.json` (`types` with `demo` flag, `neighborhoods`,
  `sources`, `default_source`). Demo types: Pothole, Street Light, Missed Trash,
  Abandoned Vehicles, Rodent Activity.

## Assumptions to show in the UI
- Estimates are historical, not official deadlines or guarantees. Not an official City of Boston service.
- Queue conditions are as of **2025-10-01** (just before Boston's Oct 2025 311 system change;
  later data is incomplete). Date/time and weekday of the request do affect the estimate
  (weekend filings wait for Monday).
- Based on closed cases only: about 25% of 2025 requests (and ~30% of potholes every year)
  were never closed in the data, so real waits may be longer.
- Neighborhood level only; similar cases have no coordinates and redacted emails/phones.
- Data: City of Boston 311 Service Requests 2021-2025, data.boston.gov, PDDL.

## Numbers you can quote (2025 test, models trained on 2022-2023)
From `reports/metrics.json`: overall p50 MAE 8.69 -> 7.84 days vs baseline (95% CI of
difference -0.89 to -0.81); p80 coverage 0.83. On-time classifier on the 5 demo types:
AUC 0.869 (`reports/recalibration.json`). Do not quote the final-model numbers; there are none.

## Rebuild everything
```bash
.venv/bin/python -m src.load && .venv/bin/python -m src.clean && .venv/bin/python -m src.features \
 && .venv/bin/python -m src.train && .venv/bin/python -m src.evaluate && .venv/bin/python -m src.export
```
(needs the raw CSVs in `data/raw/`).
