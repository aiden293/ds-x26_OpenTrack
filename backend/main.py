"""HTTP adapter for the model. Run from the repository root."""
from datetime import datetime
from functools import lru_cache
import json
import logging
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "data/processed/cases_for_app.parquet"
app = FastAPI(title="Civic Pulse API")
logger = logging.getLogger(__name__)


@lru_cache
def choices():
    return json.loads((ROOT / "models/choices.json").read_text())


class Request(BaseModel):
    type: str = Field(min_length=1, max_length=200)
    neighborhood: str = Field(min_length=1, max_length=100)
    open_date: datetime


def validate_request(request: Request):
    options = choices()
    if request.type not in {item["type"] for item in options["types"]}:
        raise HTTPException(422, "Choose a supported request type.")
    if request.neighborhood not in options["neighborhoods"]:
        raise HTTPException(422, "Choose a supported neighborhood.")
    # The trained pipeline uses naive Boston wall-clock datetimes.
    date = request.open_date
    if date.tzinfo is not None:
        date = date.astimezone(ZoneInfo("America/New_York")).replace(tzinfo=None)
    return date


@app.get("/api/health")
def health():
    return {"status": "ok", "similar_cases_available": CASES.is_file()}


@app.get("/api/choices")
def get_choices():
    return choices()


@app.post("/api/predict")
def estimate(request: Request):
    date = validate_request(request)
    try:
        from src.predict import predict
        return predict(request.type, request.neighborhood, date)
    except Exception:
        logger.exception("Prediction failed")
        raise HTTPException(503, "The prediction service is unavailable. Please try again shortly.")


@app.post("/api/similar")
def similar(request: Request):
    date = validate_request(request)
    if not CASES.is_file():
        return {"available": False, "cases": [], "message": "Historical case records have not been connected yet."}
    try:
        from src.similar import similar_cases
        frame = similar_cases(request.type, request.neighborhood, date, k=5)
        return {"available": True, "cases": json.loads(frame.to_json(orient="records", date_format="iso"))}
    except Exception:
        logger.exception("Similar-case lookup failed")
        raise HTTPException(503, "Historical cases are temporarily unavailable.")
