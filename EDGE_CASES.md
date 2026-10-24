# Edge cases: what we left out, and how the app and the talk handle it

Every exclusion or fallback in the pipeline was a decision. This file maps each one to the
inputs where it shows up, what `predict()` / `similar_cases()` do, and what to say.
All numbers come from runs in this repo (`reports/`, `models/`, `tests/test_predict.py`).

## How the app should use this
`predict()` returns `flags` (codes) and `pct_unclosed`; `flag_messages(result)` returns
suggested text. Show the messages under the estimate. `queue_snapshot` is always on, so it
can live in a footer instead. Do not re-derive these rules in the app.

```python
from src.predict import predict, flag_messages
r = predict("Request for Pothole Repair", "Dorchester", datetime(2026, 10, 24, 10))
r["flags"]          # ['queue_snapshot', 'high_unclosed_rate', 'weekend_or_holiday']
flag_messages(r)    # ['Queue conditions are as of October 2025, ...', '32% of past requests ...', ...]
```

## Register

| Decision in the pipeline | Where it shows up | App behavior | Flag |
|---|---|---|---|
| Never-closed requests are not in training (about 25% of 2025 requests; 32% of potholes opened 2022-01 to 2025-09) | Types that often stay open | Estimate unchanged; share shown | `high_unclosed_rate` (>= 15%) |
| Duplicate / invalid / automated / referred / bulk closures excluded from the target | A request closed as a duplicate within minutes | Estimate reflects requests that were actually handled | (text in footer) |
| Queue features frozen at 2025-10-01 (Oct 2025 311 system change truncates later closures) | Every request | `state_time` returned | `queue_snapshot` (always) |
| `target_days` estimated from the 2025 median per type and weekday | Types without a city target | `target_days=None`, no comparison, no `p_ontime` | `no_sla` |
| `p_ontime` only for the 5 demo types (classifier failed overall on 2025 because of Parking Enforcement drift) | All other types | `p_ontime=None`; hide the widget | (none; `None` is the signal) |
| Street Light p80 uses the baseline (ML p80 was worse on 2025 test) | Street Light Outages | `p80_used_model="baseline"` | `p80_baseline` |
| Per-type baseline falls back to reason, then global | Rare or unknown types | `used_model="baseline"`, `n_support=0` | `unknown_type`, `low_support` (< 100 cases) |
| Unknown neighborhood mapped to "Unknown / Citywide" | Typos, "Boston", missing | Citywide queue state | `neighborhood_fallback` |
| Neighborhood rolling stats need >= 5 recent cases | Small neighborhoods (e.g. Chestnut Hill: 80 cases in 5 years) | Model leans on citywide features | `few_local_cases` (< 30 cases) |
| p50 and p80 come from separate models on skewed data | Bimodal types (quick fix vs months) | Range shown as is | `wide_range` (p80 >= 7 d and >= 4x p50) |
| Calendar features use the filing time | Weekend and MA holiday filings | Estimate is longer | `weekend_or_holiday` |
| Staff channels (City Worker App, Employee Generated) close much faster (42% of City Worker potholes in < 5 min) | Source dropdown | Default source is Citizens Connect App | `non_resident_source` |

`similar_cases()` edge cases:
- Fewer than k same-neighborhood cases in season: widens to any neighborhood, then any time; `match_level` says which. Pothole in Chestnut Hill returns 10 `any_neighborhood_season` cases.
- Unknown type: empty DataFrame. Show "no similar past requests".
- Identical rows can appear (several poles reported at once, same open and close time). They are real separate cases.
- `closure_reason` can be empty or terse ("Resolved"). Emails and phone numbers are redacted.

## How often flags fire
Across the 134 dropdown types (Dorchester, Monday filing): `queue_snapshot` 134,
`wide_range` 57, `high_unclosed_rate` 44, `few_local_cases` 36, `no_sla` 22,
`low_support` 22, `p80_baseline` 1. Most types carry at least one caveat, so the UI needs room for 1 to 3 short notes.

## Demo scenarios (real outputs, Monday = 2026-10-26 10:00, Saturday = 2026-10-24 10:00)

| | Input | p50 / p80 (days) | Target | p_ontime | Flags |
|---|---|---|---|---|---|
| A | Missed Trash, Dorchester, Monday | 0.06 / 0.30 | 1.0 | 0.98 | `queue_snapshot` |
| B | Pothole, Dorchester, Monday | 0.92 / 2.49 | 1.0 | 0.59 | + `high_unclosed_rate` |
| C | Pothole, Dorchester, Saturday | 3.05 / 5.03 | 2.8 | 0.28 | + `high_unclosed_rate`, `weekend_or_holiday` |
| D | Street Light, Hyde Park, Monday | 19.82 / 95.57 | 14.4 | 0.31 | + `p80_baseline`, `wide_range` |
| E | Pothole, Chestnut Hill, Monday | 1.12 / 3.67 | 1.0 | 0.43 | + `few_local_cases`, `high_unclosed_rate` |
| F | "Alien Landing", Dorchester | 0.46 / 4.03 (global baseline) | None | None | + `unknown_type`, `no_sla` |

Suggested live demo: B (clean case), then C (same request on a Saturday: estimate triples,
on-time chance halves), then D (honest wide range).

## For the presentation: found -> decided -> checked

| Found | Decided | Checked |
|---|---|---|
| 1,909 Abandoned Vehicle cases from 2021 closed on a few days in Oct 2024 | `bulk_closure` rule excludes same-day purges of old cases | 2021 median 1,048 -> 78 days |
| Pothole backlog grows every year (905 -> 17,547) because ~30% never close | Dropped `backlog_type`; kept 90-day backlog | Validation difference 0.12%, no drift risk |
| On-time classifier collapsed on 2025 (AUC 0.684) | Diagnosed Parking Enforcement drift; show `p_ontime` only on demo types | Demo types AUC 0.869, ECE 0.049 |
| Closures vanish after the Oct 2025 system change | Freeze queue state at 2025-10-01 | Street Light p50 38 -> 12 days |
| Many requests never close | Show the share per type in the app | `high_unclosed_rate` on 44 of 134 types |

## Not handled (say so if asked)
- Today's real queue: the data ends in 2025, so every estimate uses October 2025 conditions.
- Requests filed through the new 311 system after Oct 2025 are not in the data at all.
- Within-type differences (e.g. a small vs a large tree job) are invisible to the model.
- Reporting bias: areas that report more appear more; the equity analysis notes this.
