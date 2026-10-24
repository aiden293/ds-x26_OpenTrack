"""Edge-case tests for predict(): each flag fires for the input meant to trigger it,
stays off for a normal request, and the contract invariants hold everywhere.

Usage: .venv/bin/python -m tests.test_predict   (needs models/ from src.export)
"""
from datetime import datetime

from src.clean import DEMO_TYPES, UNKNOWN_NEIGHBORHOOD
from src.policy import ONTIME_TYPES
from src.predict import FLAG_MESSAGES, _load, flag_messages, predict

POTHOLE, STREET_LIGHT, TRASH = DEMO_TYPES[0], DEMO_TYPES[1], DEMO_TYPES[2]
MONDAY = datetime(2026, 10, 26, 10, 0)
SATURDAY = datetime(2026, 10, 24, 10, 0)
PATRIOTS_DAY = datetime(2026, 4, 20, 10, 0)   # Monday holiday in MA
CONTRACT_KEYS = {"p50", "p80", "baseline_p50", "baseline_p80", "target_days", "p_ontime",
                 "n_support", "used_model"}


def flags(*args, **kw) -> set[str]:
    return set(predict(*args, **kw)["flags"])


def check_invariants(r: dict, type_: str) -> None:
    assert CONTRACT_KEYS <= r.keys()
    assert 0 <= r["p50"] <= r["p80"]
    assert r["used_model"] in ("ml", "baseline")
    assert set(r["flags"]) <= FLAG_MESSAGES.keys()
    assert "queue_snapshot" in r["flags"]
    if type_ not in ONTIME_TYPES or r["target_days"] is None:
        assert r["p_ontime"] is None
    else:
        assert 0 <= r["p_ontime"] <= 1
    assert len(flag_messages(r)) == len(r["flags"])


def main() -> None:
    L = _load()
    # normal request: only the always-on flag plus facts about the type
    r = predict(TRASH, "Dorchester", MONDAY)
    assert set(r["flags"]) == {"queue_snapshot"}, r["flags"]

    # each flag, triggered on purpose
    assert "weekend_or_holiday" in flags(TRASH, "Dorchester", SATURDAY)
    assert "weekend_or_holiday" in flags(TRASH, "Dorchester", PATRIOTS_DAY)
    assert "unknown_type" in flags("Alien Landing", "Dorchester", MONDAY)
    r = predict("Alien Landing", "Dorchester", MONDAY)
    assert r["used_model"] == "baseline" and r["n_support"] == 0 and r["pct_unclosed"] is None
    assert {"neighborhood_fallback"} <= flags(TRASH, "Atlantis", MONDAY)
    assert "neighborhood_fallback" in flags(TRASH, UNKNOWN_NEIGHBORHOOD, MONDAY)
    assert "few_local_cases" in flags(POTHOLE, "Chestnut Hill", MONDAY)
    assert "few_local_cases" not in flags(POTHOLE, "Dorchester", MONDAY)
    assert {"high_unclosed_rate"} <= flags(POTHOLE, "Dorchester", MONDAY)
    sl = flags(STREET_LIGHT, "Dorchester", MONDAY)
    assert {"p80_baseline", "wide_range"} <= sl, sl
    assert "non_resident_source" in flags(POTHOLE, "Dorchester", MONDAY, "City Worker App")
    assert "non_resident_source" not in flags(POTHOLE, "Dorchester", MONDAY, "Constituent Call")

    small = [t for t, v in L["baseline"]["type"].items() if v["n"] < 100]
    assert small, "no low-support type to test"
    assert "low_support" in flags(small[0], "Dorchester", MONDAY)

    no_sla = [c["type"] for c in L["choices"]["types"] if c["type"] not in L["target_days"]]
    assert no_sla, "no type without SLA to test"
    r = predict(no_sla[0], "Dorchester", MONDAY)
    assert "no_sla" in r["flags"] and r["target_days"] is None and r["p_ontime"] is None

    # message templating uses the real number
    msg = flag_messages(predict(POTHOLE, "Dorchester", MONDAY))
    assert any("32%" in m for m in msg), msg

    # invariants over every dropdown type x neighborhood x a weekday/weekend date
    n = 0
    for c in L["choices"]["types"]:
        for nb in L["choices"]["neighborhoods"]:
            for d in (MONDAY, SATURDAY):
                check_invariants(predict(c["type"], nb, d), c["type"])
                n += 1
    print(f"OK: flag triggers + invariants on {n} type x neighborhood x day combinations")


if __name__ == "__main__":
    main()
