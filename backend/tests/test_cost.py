import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings

client = TestClient(app)
client.__enter__()


def test_cost_ingest():
    r = client.post("/api/cost/ingest")
    assert r.status_code == 200
    body = r.json()
    assert body["records_ingested"] == 309
    assert body["vendors_ingested"] > 0
    assert body["budgets_ingested"] > 0


def test_building_summary_shape():
    r = client.get("/api/cost/building")
    assert r.status_code == 200
    body = r.json()
    assert body["summary"]["record_count"] == 309
    assert body["summary"]["total_spend_inr"] > 0
    assert body["anomaly_model_confidence"]["available"] is True
    assert body["anomaly_comparison_confidence"]["available"] is True
    assert body["forecast_confidence"]["available"] is True


def test_category_breakdown_sums_to_total():
    r = client.get("/api/cost/building")
    body = r.json()
    total = body["summary"]["total_spend_inr"]
    breakdown_sum = sum(c["spend_inr"] for c in body["category_breakdown"])
    assert abs(breakdown_sum - total) < 1.0


def test_vendors_listed():
    r = client.get("/api/cost/vendors")
    body = r.json()
    assert len(body["vendors"]) > 0
    assert all("total_spend_inr" in v for v in body["vendors"])


def test_budgets_are_disclosed_as_assumption_based():
    """Budgets are NOT real published figures (see build_cost_dataset.py)
    — every budget the API returns must carry that disclosure."""
    r = client.get("/api/cost/budgets")
    body = r.json()
    assert len(body["budgets"]) > 0
    for b in body["budgets"]:
        assert "assumption" in b["basis"].lower()


def test_flagged_invoices_have_scores():
    r = client.get("/api/cost/building")
    body = r.json()
    for f in body["flagged_invoices"]:
        assert f["anomaly_score"] >= 0


def test_forecast_reports_honest_confidence():
    r = client.get("/api/cost/building")
    body = r.json()
    forecast = body["forecast"]
    assert forecast["available"] is True
    assert forecast["direction"] in ("up", "down", "flat")
    assert forecast["confidence"]["n_weeks_total"] == 71


def test_manual_record_add_and_delete():
    # Read the seeded admin's creds from settings (see app/main.py's
    # lifespan) instead of hardcoding "admin"/"facilityops123" — those
    # can legitimately differ between local dev and CI.
    login = client.post("/api/auth/login", json={"username": settings.ADMIN_USERNAME, "password": settings.ADMIN_PASSWORD})
    assert login.status_code == 200
    token = login.json()["access_token"]
    auth_headers = {"Authorization": f"Bearer {token}"}

    r = client.post("/api/cost/records", json={
        "vendor_name": "Test Vendor Ltd", "category": "Repairs & Maintenance", "amount_inr": 1234.56,
    }, headers=auth_headers)
    assert r.status_code == 200
    record_id = r.json()["id"]

    r2 = client.get("/api/cost/records/recent", params={"limit": 5})
    assert any(rec["id"] == record_id for rec in r2.json()["records"])

    r3 = client.delete(f"/api/cost/records/{record_id}", headers=auth_headers)
    assert r3.status_code == 200


def test_manual_record_add_requires_auth():
    """/records is a protected admin action — no Bearer token should be
    rejected with 401, not silently allowed through."""
    r = client.post("/api/cost/records", json={
        "vendor_name": "Unauthorized Vendor", "category": "Repairs & Maintenance", "amount_inr": 1.0,
    })
    assert r.status_code == 401


def test_investigate_endpoint_runs():
    r = client.get("/api/cost/investigate")
    assert r.status_code == 200
    body = r.json()
    assert "final_summary" in body
    assert body["tool_call_count"] >= 0


def test_facility_health_aggregates_all_five_agents():
    r = client.get("/api/facility/health")
    assert r.status_code == 200
    body = r.json()
    assert set(body["subscores"]) == {"energy", "maintenance", "occupancy", "security", "cost"}
    assert 0 <= body["composite_score"] <= 100
    assert body["status"] in ("Excellent", "Good", "Needs Attention", "Critical")


def test_facility_alerts_unified_feed():
    r = client.get("/api/facility/alerts")
    assert r.status_code == 200
    body = r.json()
    assert "total_open" in body
    for a in body["alerts"]:
        assert a["domain"] in ("maintenance", "security", "cost")


def test_facility_kpis_shape():
    r = client.get("/api/facility/kpis")
    assert r.status_code == 200
    body = r.json()
    for key in ["energy_total_kwh", "maintenance_avg_health_score", "occupancy_avg_utilization_pct", "cost_total_spend_inr"]:
        assert key in body


def test_combined_dataset_has_both_real_and_derived_sources():
    """The Cost dataset should combine real BBMP capital-works records
    with logically-derived cross-agent operational cost records (see
    data/build_cost_dataset.py) — not just one or the other."""
    r = client.get("/api/cost/records", params={"limit": 1000})
    records = r.json()["records"]
    assert len(records) > 0
    # description text distinguishes the two sources honestly
    bbmp_like = [rec for rec in records if "derived" not in rec.get("description", "").lower()]
    derived_like = [rec for rec in records if "estimated" in rec.get("description", "").lower()]
    assert len(bbmp_like) > 0
    assert len(derived_like) > 0


def test_derived_cross_agent_categories_present():
    r = client.get("/api/cost/building")
    body = r.json()
    categories = {c["category"] for c in body["category_breakdown"]}
    for expected in ["Energy Operations (derived)", "Maintenance Operations (derived)",
                      "Occupancy Operations (derived)", "Security Operations (derived)"]:
        assert expected in categories


def test_derived_costs_not_exposed_on_other_domain_dashboards():
    """The cross-agent-derived cost numbers must stay out of the Energy/
    Maintenance/Occupancy/Security dashboards — only Cost and the
    Executive Overview should ever surface them."""
    for path in ["/api/energy/dashboard", "/api/maintenance/fleet", "/api/occupancy/building", "/api/security/building"]:
        r = client.get(path)
        assert r.status_code == 200
        body_text = str(r.json()).lower()
        assert "amount_inr" not in body_text
        assert "cost_records" not in body_text


def test_bbmp_vendor_concentration_discloses_issuing_authority_caveat():
    """Vendor concentration on the BBMP slice represents issuing
    authorities/circles, not private contractors — this must stay
    disclosed, not silently presented as supplier risk."""
    r = client.get("/api/cost/vendors")
    body = r.json()
    assert any(v["vendor_id"].startswith("AUTH-") for v in body["vendors"])
    assert any(v["vendor_id"].startswith("INTERNAL-") for v in body["vendors"])


def test_cost_data_drift_quiet_on_original_dataset():
    client.post("/api/cost/ingest")
    r = client.get("/api/cost/building")
    assert r.json()["data_drift"]["drift_detected"] is False


def test_cost_data_drift_flags_mismatched_upload():
    """Regression test for a real bug found and fixed: raw amount_inr has
    such a huge training-set std (invoices range from tiny purchases to
    multi-crore tenders) that a z-score on the raw values almost never
    trips, even for wildly different data. Must use log1p(amount_inr)."""
    import pandas as pd
    df = pd.DataFrame({
        "vendor_name": ["Test Vendor"] * 20,
        "category": ["Repairs & Maintenance"] * 20,
        "amount_inr": [500] * 20,
        "date": pd.date_range("2026-01-01", periods=20).strftime("%Y-%m-%d"),
    })
    csv_bytes = df.to_csv(index=False).encode()
    client.post("/api/cost/ingest/upload", files={"file": ("tiny_amounts.csv", csv_bytes, "text/csv")})

    r = client.get("/api/cost/building")
    drift = r.json()["data_drift"]
    assert drift["drift_detected"] is True
    assert drift["level"] in ("medium", "high")

    client.post("/api/cost/ingest")