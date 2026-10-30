# Agentic AI for Smart Facility Operations & Optimization

## Cost and Energy Anomaly Intelligence

Energy and Cost now include persistent anomaly review: scan existing data,
inspect occupancy context and supporting signals, then confirm or dismiss a
finding. Repeat scans preserve reviews and avoid duplicate source events.
See [local setup, file guide and verification](docs/ANOMALY_REVIEW.md).
Use Node.js 24 LTS and Python 3.12/3.13 for this checkout.

### 🔗 [Live Demo](https://facilityops.onrender.com/)

> **Note on Free-Tier Hosting:** The backend is hosted on Render's free tier, so it spins down after inactivity. If the demo above doesn't load within ~30 seconds on first visit, [wake the backend here first](https://facilityops.onrender.com/health), then refresh the live demo link.

![Tests](https://img.shields.io/badge/tests-59%2F59%20passing-brightgreen)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Python](https://img.shields.io/badge/backend-FastAPI-009688)
![Frontend](https://img.shields.io/badge/frontend-React%20%2B%20Vite-61DAFB)
![Status](https://img.shields.io/badge/milestones-1--4%20complete-blue)

An agentic AI platform that monitors and optimizes a facility across five domains (Energy, Maintenance, Occupancy, Security, and Cost) and rolls them all up into a single Facility Intelligence Engine.

I designed and built this end to end as a solo project for the Infosys Springboard AI internship: architecture, data pipelines, ML models, the agentic layer, backend, frontend, tests and documentation.

---

## What this actually is

Most "AI facility dashboard" projects are one LLM call narrating some pre-computed numbers. This isn't that. Every domain agent follows the same four-stage pattern (`analyze → recommend → investigate → run`), backed by ML models I trained and evaluated myself, plus a real agentic layer where the model is handed a set of tools and decides for itself what to call and in what order, not a scripted sequence.

A few things I tried to get right instead of faking:

- **Multiple models per domain, compared honestly.** I didn't just pick the best number and ship it. Every domain compares at least two models against a naive baseline, and when a model underperforms (like the 24h energy forecast), I say so instead of hiding it.
- **Agents actually hand work to each other.** Energy can open a maintenance ticket. Occupancy can trigger a security alert. These are real backend function calls, not just links between dashboards.
- **I disclose the data.** Some of it is real public data, some is derived from that real data with a documented formula, and some is synthetic because no usable real dataset exists (e.g. access-control logs). I say which is which, everywhere it matters.

This submission covers Milestones 1–4: all five agents, the ML pipeline behind each, the agentic tool-calling layer, and all six dashboards (five domain dashboards + one executive overview). 59/59 tests passing.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         React Frontend (Vite)                       │
│   Executive │ Energy │ Maintenance │ Occupancy │ Security │ Cost     │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ REST (FastAPI)
┌───────────────────────────────▼─────────────────────────────────────┐
│                     Facility Intelligence Engine                     │
│         /api/facility/health · /alerts · /kpis  (aggregation)        │
└───┬───────────┬──────────────┬──────────────┬──────────────┬────────┘
    │           │              │              │              │
┌───▼───┐  ┌────▼─────┐  ┌─────▼─────┐  ┌─────▼─────┐  ┌─────▼─────┐
│Energy │  │Maintenance│  │ Occupancy │  │ Security  │  │   Cost    │
│ Agent │  │  Agent    │  │  Agent    │  │  Agent    │  │  Agent    │
└───┬───┘  └────┬─────┘  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘
    │           │              │              │              │
    │   Cross-agent handoffs (real function calls, not UI-only)
    │   Energy ──flags──▶ Maintenance   Occupancy ──flags──▶ Security
    │
┌───▼─────────────────────────────────────────────────────────────────┐
│         ML Models (per domain) + LLM Providers (Mock/Groq/Gemini)    │
│   Forecasting · RUL prediction · Classification · Anomaly detection  │
└─────────────────────────────────────────────────────────────────────┘
```

Every agent follows the same skeleton:

```
init()  →  analyze()  →  recommend()  →  run()
```

...plus an `investigate()` path where an LLM gets tools instead of answers and works through a multi-step investigation on its own. See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full reasoning and how the system extends without rewrites.

### Three layers of "intelligence," not just one

| Layer | What it is | Example |
|---|---|---|
| 1. Rule-based | Deterministic checks: fast, explainable, always available | `EnergyAgent.recommend()`: 7 rule checks |
| 2. ML forecasting/detection | Trained models, cross-validated, benchmarked against naive baselines | Multi-horizon energy forecasting, RUL prediction, anomaly detection |
| 3. Agentic investigation | The model gets tools and decides the call sequence itself | `/investigate` endpoints: real multi-step tool use |

---

## Milestones

<details>
<summary><b>Milestone 1: Energy Intelligence & Monitoring</b> (Weeks 1–2) ✅</summary>

- **Energy Agent** ingests utility/IoT data and runs consumption analytics: totals/peaks, HVAC/Lighting/Plug/Other breakdown, trend detection, per-hour anomaly detection (z-score), phantom-load ratio, temperature and occupancy correlation.
- 7 rule-based recommendations with estimated savings %.
- **ML forecasting**: three separately trained models (1h / 6h / 24h horizons), each comparing Linear Regression / Random Forest / Gradient Boosting against two naive baselines, validated with a time-ordered holdout and 5-fold `TimeSeriesSplit`. The 1h/6h models beat baseline by ~65–67%; the 24h model only marginally (~5%) and is flagged `confidence: low` rather than dressed up.
- **LLM briefing**: turns the Energy Agent's structured output into a plain-English summary for a facility manager. Provider-agnostic (`MockProvider` / `GroqProvider` / `GeminiProvider`), falls back to Mock if no key is set.
- **Agentic investigation** (`/api/energy/investigate`): the model has 7 real tools (consumption summary, submeter breakdown, anomaly detection, temperature correlation, occupancy correlation, horizon-aware forecast, maintenance-flagging handoff) and decides which to call. It genuinely branches: the 24h forecast is only pulled if the 1h forecast shows a ≥8% shift; temperature correlation only if HVAC is a large load share.
- **Data**: three real public datasets on one shared 15-min timeline: PJM Interconnection grid load (rescaled), Environment Canada hourly weather, UCI Occupancy Detection dataset.

</details>

<details>
<summary><b>Milestone 2: Predictive Maintenance</b> (Weeks 3–4) ✅</summary>

- **Maintenance Agent**, same four-step template, proof the architecture generalizes past one domain.
- **Data**: NASA C-MAPSS Turbofan Engine Degradation dataset (FD001): real sensor measurements run to actual mechanical failure, relabeled onto fictional facility assets (disclosed).
- **ML model**: RUL (Remaining Useful Life) prediction. Compared Linear Regression, Random Forest, Gradient Boosting, Histogram Gradient Boosting, and a blended ensemble. The ensemble won, MAE 14.47 cycles (R² 0.753) vs. a naive baseline of 34.83 cycles (58.5% improvement). Ships with an 80% prediction interval (empirical coverage: 80.0%), evaluated on NASA's own held-out 100-engine test set.
- **Agentic investigation** (`/maintenance/investigate`) with real tools: fleet-wide health check, single-asset check, at-risk asset listing, work-order creation.
- **Cross-agent handoff**: the Energy Agent's maintenance-flagging tool calls the same `open_work_order()` function the Maintenance Agent uses internally. A real row lands in the database tagged `source="energy_agent"`, visually distinguished in the UI. First real proof of agent cooperation in the codebase.

</details>

<details>
<summary><b>Milestone 3: Occupancy & Security Intelligence</b> (Weeks 5–6) ✅</summary>

**Occupancy Agent**
- Classifier trained directly on the UCI Occupancy Detection dataset (real minute-level ambient sensor data + ground-truth photo labels), evaluated on UCI's own two held-out test splits.
- Logistic Regression beat Gradient Boosting: 98.25% accuracy (F1 0.964) vs. a 75.7% naive baseline.
- Live 8-zone fleet (offices, meeting rooms, cafeteria, lobby, server room, executive wing): real time-of-day profile projected per zone with independent noise (disclosed synthetic step).

**Security Agent**
- Fully synthetic, disclosed dataset (no license-clear real access-control dataset exists publicly) with deliberately injected, labeled anomalies for honest evaluation.
- Isolation Forest (unsupervised, live scorer): precision 0.714, recall 0.738, F1 0.726. A Local Outlier Factor model is kept as a second opinion. A supervised RandomForest reference (F1 0.706) shows how much accuracy the unsupervised constraint costs; the unsupervised model actually edges it out.
- Detection is validated against known injected patterns, explicitly not validated against real incidents, and stated wherever results are shown.

**Cross-agent handoff (Occupancy → Security)**: any occupancy in a restricted zone (e.g. Server Room) triggers a real row in `security_alerts` tagged `source="occupancy_agent"`.

</details>

<details>
<summary><b>Milestone 4: Cost Optimization & Facility Intelligence</b> (Weeks 7–8) ✅</summary>

**Cost Optimization Agent**: two-part dataset, both disclosed:
- Part A: ~97 real BBMP (Bengaluru municipal corporation) capital-works tender records from a public civic-data portal: real titles, amounts, categories. Two caveats stated in-code: the source data names the issuing office, not the winning contractor, and tender dates are remapped onto the demo window with spacing preserved.
- Part B: ~212 records of cross-agent operational cost, derived from the other four agents' real processed data using disclosed, published-rate formulas (BESCOM-style time-of-day tariffs for energy, wear-severity-based repair cost for maintenance, FM services rate for occupancy, incident-response labor cost for security). A test enforces that this derived cost never leaks into other domain dashboards.
- 4 ML models compared honestly: IsolationForest + LocalOutlierFactor for anomaly detection (8.1% flagged, 92.2% cross-model agreement, reported as unsupervised diagnostics since there's no labeled ground truth); GradientBoosting + RandomForest for a smoothed 3-week spend trend forecast (RandomForest won, +20.7% over naive baseline), after an earlier attempt at forecasting raw weekly totals scored worse than naive, which is why the target is smoothed.

**Facility Intelligence Engine**: a thin aggregation layer that never re-derives anything from the five agents, so it can't drift from what each dashboard already shows:
- `GET /api/facility/health`: composite 0–100 score, equal-weighted across all five domains, full breakdown included.
- `GET /api/facility/alerts`: unified alert feed across all agents.
- `GET /api/facility/kpis`: headline KPIs for the Executive dashboard.

**Frontend**: `/executive` Overview dashboard (now the default landing page) with a per-domain KPI row, Facility Health Score gauge, and unified alert feed. All ₹ amounts render in lakh/crore notation.

</details>

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI, SQLAlchemy, scikit-learn, TensorFlow/Keras (LSTM for RUL), pandas |
| Frontend | React, Vite, Tailwind CSS |
| LLM Providers | Groq (recommended, free tier), Gemini, Mock (no key required) |
| ML | Linear/Logistic Regression, Random Forest, Gradient Boosting, Histogram Gradient Boosting, LSTM, Isolation Forest, Local Outlier Factor |
| Infra | Docker & Docker Compose |
| Testing | pytest (59/59 passing) |

---

## Getting Started

### Backend

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
# → http://localhost:8000/docs  (Swagger UI)
# Data auto-ingests on first startup.
```

> **Windows note:** if `uvicorn app.main:app --reload` fails with an "Application Control policy has blocked this file" error, run `python -m uvicorn app.main:app --reload` instead.

### Frontend

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
# → http://localhost:5173/executive  (default landing page)
```

### Or, with Docker

```bash
docker-compose up --build
```

### Enabling a real LLM (optional, Mock works out of the box)

```env
# backend/.env
AI_PROVIDER=groq
GROQ_API_KEY=your_key_here   # free at https://console.groq.com/keys
```

---

## API Reference

Endpoints are grouped by domain: Energy (`/api/energy/*`), Maintenance (`/maintenance/*`), Occupancy (`/occupancy/*`), Security (`/security/*`), Cost (`/cost/*`), and Facility Intelligence (`/api/facility/*`). Full interactive docs are at `/docs` once the backend is running.

---

## Testing

```bash
cd backend
python -m pytest tests/ -v
```

59/59 passing. Covers ingestion, consumption/spend summaries, analytics shape, recommendation validity, dashboard payloads, readings pagination, ML forecast/anomaly endpoints, LLM briefings, agentic investigations (checking for real multi-tool calls, not canned responses), cross-agent handoffs, the combined real+derived Cost dataset, and the domain-isolation guarantee for derived cost data.

---

## Data Sources & Honesty Notes

I tried to be upfront about exactly which parts of each dataset are real, which are derived from real data via a documented formula, and which are synthetic.

| Domain | Real source | Nature |
|---|---|---|
| Energy | PJM grid load, Environment Canada weather, UCI Occupancy | 3 real datasets, composited onto one timeline |
| Maintenance | NASA C-MAPSS (FD001) | Real sensor data, relabeled onto fictional assets |
| Occupancy | UCI Occupancy Detection | Real classifier training + real profile projected across a synthetic 8-zone fleet |
| Security | None | Fully synthetic, disclosed, with labeled injected anomalies |
| Cost | BBMP tender data (data.opencity.in) | Real capital-works records + formula-derived cross-agent operating cost |

See each milestone section above, or the relevant `build_*_dataset.py` script, for full detail.

---

## Additional Documentation

- [`ARCHITECTURE.md`](./ARCHITECTURE.md): design rationale and how the system extends without rewrites
- [`docs/BACKEND_GUIDE.md`](./docs/BACKEND_GUIDE.md): backend structure and conventions
- [`docs/FRONTEND_GUIDE.md`](./docs/FRONTEND_GUIDE.md): frontend structure and conventions
- [`docs/MODEL_CARDS.md`](./docs/MODEL_CARDS.md): per-model cards with metrics and limitations
- [`docs/PROBLEM_STATEMENT_AND_OUTCOMES.md`](./docs/PROBLEM_STATEMENT_AND_OUTCOMES.md): problem statement and delivered outcomes

---

## Author

**Aryan Goswami**: sole author. Architecture, data pipelines, ML models, agentic AI layer, backend, frontend, testing and documentation.

[GitHub](https://github.com/Aryan2k4) · [LinkedIn](https://linkedin.com/in/aryan-goswami-6b0014324)

---

## License

This project is licensed under the [MIT License](./LICENSE). Copyright (c) 2026 Aryan Goswami.
