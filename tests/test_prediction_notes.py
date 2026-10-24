"""Integration tests using the real model and HTTP adapter."""
from unittest import TestCase

from fastapi.testclient import TestClient
from backend.main import app
from src.predict import _load

client = TestClient(app)


class PredictionNoteTests(TestCase):
    def estimate(self, type_, date="2026-10-26T10:00:00"):
        response = client.post("/api/predict", json={
            "type": type_, "neighborhood": "Dorchester", "open_date": date,
        })
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual([note["code"] for note in result["notes"]], result["flags"])
        return result, {note["code"]: note["message"] for note in result["notes"]}

    def test_pothole_percentage_and_weekend_note(self):
        result, notes = self.estimate("Request for Pothole Repair", "2026-10-24T10:00:00")
        self.assertIn(f'{result["pct_unclosed"]:.0%}', notes["high_unclosed_rate"])
        self.assertIn("weekend_or_holiday", notes)

    def test_missing_target_describes_data_limitation(self):
        models = _load()
        type_ = next(item["type"] for item in models["choices"]["types"]
                     if item["type"] not in models["target_days"])
        result, notes = self.estimate(type_)
        self.assertIsNone(result["target_days"])
        self.assertIsNone(result["p_ontime"])
        self.assertIn("historical data", notes["no_sla"])
        self.assertNotIn("no published target", notes["no_sla"])

    def test_normal_request_has_only_shared_context(self):
        _, notes = self.estimate("Missed Trash/Recycling/Yard Waste/Bulk Item")
        self.assertEqual(set(notes), {"queue_snapshot"})
