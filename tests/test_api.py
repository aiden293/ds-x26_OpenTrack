"""HTTP contract tests without requiring the model runtime or large dataset."""
from datetime import datetime
from unittest import TestCase
from unittest.mock import patch
import sys
import types

from fastapi.testclient import TestClient
from backend.main import app, Request, validate_request

client = TestClient(app)
payload = {"type": "Request for Pothole Repair", "neighborhood": "Dorchester", "open_date": "2026-10-26T10:00:00"}


class ApiTests(TestCase):
    def test_choices_are_real(self):
        response = client.get("/api/choices")
        self.assertEqual(response.status_code, 200)
        self.assertIn(payload["type"], [t["type"] for t in response.json()["types"]])

    def test_invalid_inputs(self):
        for field, value in [("type", "made up"), ("neighborhood", "made up"), ("open_date", "invalid")]:
            self.assertEqual(client.post("/api/predict", json={**payload, field: value}).status_code, 422)

    def test_prediction_adapter(self):
        module = types.ModuleType("src.predict")
        with patch.dict(sys.modules, {"src.predict": module}):
            with patch.object(module, "predict", create=True, return_value={"p50": 1.5, "p80": 3, "p_ontime": None}) as predict:
                response = client.post("/api/predict", json=payload)
                self.assertEqual(response.status_code, 200)
                self.assertIsNone(response.json()["p_ontime"])
                predict.assert_called_once_with(payload["type"], "Dorchester", datetime(2026, 10, 26, 10))

    def test_timezone_normalization(self):
        request = Request(**{**payload, "open_date": "2026-10-26T14:00:00+00:00"})
        self.assertEqual(validate_request(request), datetime(2026, 10, 26, 10))

    def test_model_failure_is_unavailable_not_fake_prediction(self):
        module = types.ModuleType("src.predict")
        with patch.dict(sys.modules, {"src.predict": module}):
            with patch.object(module, "predict", create=True, side_effect=RuntimeError("private path")):
                with self.assertLogs("backend.main", level="ERROR"):
                    response = client.post("/api/predict", json=payload)
                self.assertEqual(response.status_code, 503)
                self.assertNotIn("private path", response.text)

    def test_missing_cases(self):
        with patch("backend.main.CASES") as path:
            path.is_file.return_value = False
            response = client.post("/api/similar", json=payload)
            self.assertEqual(response.status_code, 200)
            self.assertFalse(response.json()["available"])
            self.assertEqual(response.json()["cases"], [])
