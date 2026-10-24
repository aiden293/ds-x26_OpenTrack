# Civic Pulse

A Boston 311 project that aims to estimate how long citizen service requests take to resolve using historical request data.

## Current stage

Data analysis and modeling are done. The app uses a Next.js interface and a FastAPI adapter for the existing Python models.

- Data: City of Boston 311 Service Requests 2021-2025 (data.boston.gov, PDDL), 1,433,236 requests, 1,099,534 valid closures after cleaning.
- Models: per-type baseline and gradient-boosted quantile models (p50, p80) for resolution days, plus an on-time classifier. Trained on 2022-2023, tuned on 2024, tested on 2025.
- On the 2025 test set, p50 mean absolute error is 7.84 days vs 8.69 for the baseline (`reports/metrics.json`).
- Also included: real similar past cases and a neighborhood gap analysis (`reports/equity.png`).

Estimates are historical, not official City of Boston deadlines. About 25% of 2025 requests were never closed in the data, and Boston's October 2025 311 system change truncates later closures.

## App milestone

Select a request type, neighborhood, and Boston-local date/time to retrieve a real model estimate. The app shows typical and longer waits, estimated city targets, on-time probabilities when supported, and historical cases when the separate dataset is installed.

## Repository

- `README.md` - project overview and local setup.
- `frontend/` - Next.js app (request form, predictions, and similar cases).
- `backend/` - FastAPI HTTP adapter; model code remains in `src/`.
- `BLUEPRINT.md` - minimal scope and next steps.
- `APP_HANDOFF.md` - how the app calls `predict()` and `similar_cases()`, and which caveats to show.
- `src/` - data pipeline (`load`, `clean`, `features`, `train`, `evaluate`, `export`) and app-facing `predict.py`, `similar.py`.
- `tests/` - sanity tests for features, similar cases, and predict() edge-case flags.
- `EDGE_CASES.md` - every exclusion and fallback, the flag it raises, and how to present it.
- `models/` - final models and lookup files used by `predict()`; `models/eval/` holds the train-only models behind the reported metrics.
- `reports/` - metrics, charts, and phase reports.
- `requirements.txt` - Python dependencies.
- `data/processed/cases_for_app.parquet` - 1,099,534 closed cases used by the similar-case lookup, included in Git.
- `.gitignore` - excludes other local data, secrets, and generated files. Raw CSVs and other processed datasets are not committed.

## Getting started

Use Node.js 22+ and Python 3.12 or the model teammate's Python 3.14 environment (as specified in `APP_HANDOFF.md`). This app was verified locally on Python 3.12 with the pinned model dependencies. Keep those dependency versions: loading scikit-learn model files with different versions is unsupported.

From the repository root, in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python -X utf8 -m pip install -r backend/requirements.txt
.\.venv\Scripts\python -X utf8 -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

In a second terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Open http://localhost:3000. Next.js proxies `/api/*` to `http://127.0.0.1:8000`; set `BACKEND_URL` in `frontend/.env.local` to change that address. API documentation is at http://127.0.0.1:8000/docs.

The API reads dropdown options from `models/choices.json` and invokes the real `src.predict.predict` function. Datetimes entered in the app are Boston local time. No mock predictions are shown; model errors produce an unavailable message.

The repository includes `data/processed/cases_for_app.parquet`, so similar cases work after cloning and installing dependencies. If that file is absent, predictions still work and the history panel explains that records are not connected. Restart the API after replacing an already loaded dataset or model.

Checks:

```powershell
.\.venv\Scripts\python -m unittest tests.test_api
cd frontend
npm run build
```

The API tests verify validation, timezone handling, the prediction adapter, and missing-data behavior. They use a stub only for the model call. A real prediction was also verified through the Next.js proxy: `Request for Pothole Repair`, `Dorchester`, `2026-10-26T10:00:00` returned p50 `0.921` days and p80 `2.486` days, matching the handoff example after rounding.
