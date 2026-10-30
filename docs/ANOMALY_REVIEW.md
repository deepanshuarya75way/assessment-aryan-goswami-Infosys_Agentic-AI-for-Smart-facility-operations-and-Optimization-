# Cost and energy anomaly review

The Energy and Cost dashboards now have an Anomaly Review panel. Log in as an
administrator or technician, select Scan anomalies, inspect the evidence, then
Confirm or Dismiss. Refreshing or scanning again preserves the review.

## Data flow

- `app/models/anomaly_models.py`: a new SQLAlchemy table, created on startup.
- `app/services/anomaly_service.py`: existing energy z-score and cost Isolation
  Forest detectors, occupancy matching, persistence and review audit metadata.
- `app/api/anomaly_routes.py`: authenticated list, scan and review endpoints.
- `src/components/shared/AnomalyPanel.jsx`: loading/error states, status filters,
  pagination, supporting signals and review actions on both dashboards.

Energy comparisons use each sensor's historical same-hour baseline. Occupancy
matches that sensor and timestamp. Cost evidence includes the invoice amount,
category-median ratio and vendor order count; matching invoice-date occupancy is
context, not evidence that occupancy caused a bill. Missing observations remain
unavailable, never zero. Existing demo data provenance limitations still apply.

A unique hash of building, domain and source event prevents repeated scans from
creating duplicates, including concurrent insert attempts. Reviewed findings are
not reopened. A distinct later reading/invoice can still produce an alert; this
is source-event deduplication, not permanent suppression of a sensor or vendor.
Snapshots remain available even if source records are subsequently removed.

## Local run (PowerShell, from repository root)

Use Python 3.12 or 3.13 and Node.js 24 LTS (minimum Node 22.12).

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
Copy-Item backend/.env.example backend/.env
cd backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Only copy `.env.example` if `.env` does not already exist. Set local admin
credentials there before first startup; use those credentials to log in.
AI_PROVIDER=mock is sufficient for anomaly review; no AI-provider key is needed.

In a second terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Open http://localhost:5173. The frontend calls http://localhost:8000/api during
development. Existing environments can keep their database; startup adds the new
table without deleting old data. Do not copy secrets into Git.

## Verification

From backend: `python -m pytest tests/test_anomaly_review.py -q`.
From frontend: `npm test` and `npm run build`.
For a manual check, scan each domain twice (second scan creates zero new alerts
for unchanged source data), review a finding, reload and verify the saved status.

## Other laptop with an existing trial2 checkout

Keep that folder intact so its uncommitted work is not lost. Clone this repository
into a different folder from its parent directory:

```bash
git clone https://github.com/Aryan2k4/Infosys_Agentic-AI-for-Smart-facility-operations-and-Optimization-.git facilityops-75ways
cd facilityops-75ways
```

The update is on this repository's default branch, not on trial2. This feature
does not retrain models or claim improved prediction accuracy.
