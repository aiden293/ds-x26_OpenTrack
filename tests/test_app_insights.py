"""Tests for the result-page endpoints (/api/meta, /api/insights, /api/cases), using the real data."""
from datetime import datetime
from unittest import TestCase
from unittest.mock import patch

from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)
payload = {"type": "Street Light Outages", "neighborhood": "Hyde Park", "open_date": "2026-10-26T10:00:00"}


class AppInsightsTests(TestCase):
    def test_meta_groups_every_type(self):
        meta = client.get("/api/meta").json()
        self.assertEqual(len(meta["groups"]), 11)
        self.assertTrue(all(0 <= t["group"] < len(meta["groups"]) for t in meta["types"]))
        self.assertEqual(sum(t["demo"] for t in meta["types"]), 5)
        self.assertTrue(all(t["hit"] is None or 0 <= t["hit"] <= 1 for t in meta["types"]))
        self.assertEqual(meta["stats"]["cases"], 1099534)

    def test_insights_shapes(self):
        r = client.post("/api/insights", json=payload)
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertAlmostEqual(sum(body["distribution"]["shares"]), 1, places=2)
        meta = client.get("/api/meta").json()
        self.assertEqual(len(body["compare"]), len(meta["neighborhoods"]) - 1)   # no "Unknown / Citywide"
        self.assertTrue(all(row["p80"] >= row["p50"] for row in body["compare"]))
        self.assertEqual(body["local"]["n"], 240)
        self.assertLess(body["hit"]["lower"], body["hit"]["rate"])

    def test_cases_scope_sort_and_cutoff(self):
        r = client.post("/api/cases", json={**payload, "sort": "short"}).json()
        self.assertTrue(r["available"])
        self.assertEqual(r["total"], 431)
        rows = r["cases"]
        self.assertEqual(len(rows), 5)
        self.assertTrue(all(c["neighborhood"] == "Hyde Park" for c in rows))
        self.assertEqual([c["resolution_days"] for c in rows], sorted(c["resolution_days"] for c in rows))
        self.assertTrue(all(c["fastest"] for c in rows))
        early = client.post("/api/cases", json={**payload, "open_date": "2023-01-01T00:00:00", "scope": "all"}).json()
        self.assertTrue(all(datetime.fromisoformat(c["closed_dt"]) < datetime(2023, 1, 1) for c in early["cases"]))

    def test_cases_relevance_puts_post_change_cases_last(self):
        r = client.post("/api/cases", json={**payload, "page": 1}).json()
        self.assertFalse(any(c["after_system_change"] for c in r["cases"]))
        last = client.post("/api/cases", json={**payload, "page": r["pages"]}).json()
        self.assertEqual(last["page"], r["pages"])

    def test_cases_page_is_clamped_and_inputs_validated(self):
        r = client.post("/api/cases", json={**payload, "page": 99999}).json()
        self.assertEqual(r["page"], r["pages"])
        self.assertEqual(client.post("/api/cases", json={**payload, "sort": "random"}).status_code, 422)
        self.assertEqual(client.post("/api/cases", json={**payload, "scope": "world"}).status_code, 422)

    def test_missing_cases_file(self):
        with patch("backend.main.CASES") as path:
            path.is_file.return_value = False
            self.assertFalse(client.post("/api/cases", json=payload).json()["available"])
            self.assertEqual(client.post("/api/insights", json=payload).status_code, 503)
