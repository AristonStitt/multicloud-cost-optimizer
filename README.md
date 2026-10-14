# CloudScope — Working Multi-Cloud Cost Optimizer Demo

**Team members: start with [`START_HERE_TEAM.md`](START_HERE_TEAM.md).** For a 3-minute presentation, use [`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md).

**Friday-ready local proof of concept.** This application shows a complete data-to-recommendation workflow using the provided synthetic September 2026 datasets. It is not connected to AWS, Azure, or GCP accounts, does not use current provider prices, and does not execute migrations.

## Quick start (macOS, Linux, Windows)

Use Python 3.11 or newer. Open a terminal in the extracted folder:

```bash
python3 -m venv .venv
source .venv/bin/activate       # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:8000** in the browser. Interactive FastAPI API docs: **http://127.0.0.1:8000/docs**. Stop the server with Ctrl+C.

If port 8000 is busy, use `--port 8010` and open http://127.0.0.1:8010.

### Run automated tests

```bash
python -m pip install pytest httpx
python -m pytest -q
```

## Expected visible results

- Total September spend: **$5,356.80** across 18 VMs and 3 fictional customers.
- AWS: $1,728.00; Azure: $1,728.00; GCP: $1,900.80.
- The estimate of **$1,041.60** savings sums only 3 same-cloud right-sizing reviews ($129.60 each) and 3 permitted-hours scheduling reviews ($217.60 each); this is *potential, unapproved compute-only savings*, not realized savings.
- Price anomalies: synthetic GCP unit price increases from $0.40 to $0.80/hr on September 25, while daily hours remain 24.
- Other findings: 3 missing-memory flags, 3 low-activity ownership reviews, and 3 busy machines that must not be downsized.
- Cross-cloud comparison: the *provided* hypothetical catalog rates are the same across all three vendors for equal machine types, and customer policies disallow cross-cloud migrations. Do not advertise migration savings.

## Demonstration flow (about 3 minutes)

1. **Overview:** Select “All demo customers”; show spending, potential savings, daily chart and cloud cost distribution.
2. **Customer filter:** Select “Demo Cedar Retail” and show costs change to $1,785.60 and potential savings to $347.20.
3. **Analysis Activity:** Press **Run analysis now**. The API re-reads local sources, validates all 9 billing scopes, calculates utilization, evaluates rules, and records actual completed phases. This is synchronous and fast; there is no fake progress animation.
4. **Recommendations:** Open **Why this recommendation?** for an oversized VM to display measured CPU/memory, proposed shape, capacity threshold checks, rejected alternatives, assumptions, and the approval requirement. Show the development scheduling recommendation and the September 25 pricing anomaly.
5. **Resources:** Show per-machine resource inventory, CPU p95, memory peak, environment and monthly spend. Search for `missing_memory` and explain why missing is not zero.
6. **Method & Validation:** Show the cross-cloud *illustrative* price comparison, customer migration restrictions, and the 9 successful reconciliation checks. Optional: open `/docs` to demonstrate a real backend API.

## System architecture

```text
raw_toy provider billing CSVs ──┐
canonical billing_daily.csv ────┼─> normalization and exact-cent reconciliation
resource inventory + metrics ──┘                 |
                                               v
                           pandas analytics / rule-based screening
                                               |
                                               v
                                FastAPI REST endpoints on :8000
                                               |
                                               v
                     Offline-ready HTML/CSS/JS browser dashboard
```

The frontend is deliberately **framework-free** so it can run immediately with no Node tooling. The FastAPI endpoints can also be called by a React frontend. Prometheus/Grafana are not running in this MVP; adding them is a later extension. This choice maximizes likelihood of a functioning demonstration.

### Project files

| File | Purpose |
|---|---|
| `backend/analytics.py` | Read datasets, normalize, aggregate, right-size/schedule screening, pricing checks and integrity verification |
| `backend/main.py` | Documented REST API and static UI hosting |
| `frontend/index.html` | Dashboard pages |
| `frontend/app.js` | API interactions, customer filtering, cost visualization, recommendation cards |
| `frontend/styles.css` | Responsive styling |
| `data/*.csv` | Uploaded fictional inputs, local-only |
| `tests/test_demo.py` | Deterministic tests for totals, recommendations, data integrity, API |

### API endpoints

`POST /api/analysis-jobs` (execute local CSV analysis and record real step outcomes), `GET /api/analysis-jobs/{job_id}` (retrieve an in-memory execution trace), `GET /api/health`, `/api/customers`, `/api/summary`, `/api/daily`, `/api/resources`, `/api/recommendations`, `/api/price-comparison`, `/api/reconciliation`. Most endpoints accept a `?customer=customer-001` optional query parameter. Documentation and request schemas are browsable at `/docs`.

## Team reference alignment (October 14)

The provided teammate discussion proposes a future customer product with cloud-provider permission-based connectors, FOCUS-aligned cost normalization, a decision engine, per-recommendation evidence, and a React dashboard. This demo follows the **same logical layers** using provider-shaped toy CSV adapters, rule-based Python analysis, and FastAPI endpoints, but intentionally substitutes a framework-free browser UI and in-memory analysis-job records for React, PostgreSQL, a task queue, real customer authorizations, and live cloud APIs. The source CSV schema is educational and **is not certified FOCUS-compliant**. Do not portray future extensions as implemented features.

**What the new Analysis Activity screen actually does:** `POST /api/analysis-jobs` synchronously reopens cached input loading, validates the three provider-shaped adapters against 9 reconciliation totals, aggregates resource measurements, reruns the decision rules, and records its measured completed steps. It does **not** simulate a running cloud sync, push live metrics, or persist results after the process restarts.

**Explainability:** Finding cards include a collapsible evidence section with the observed dataset values, threshold checks, (where applicable) rejected candidates and next actions. All savings are *potential* and no cloud change is made.

## Calculation notes and limitations

- Charge aggregation uses integer cents from canonical `billing_daily.csv`; hourly utilization is **separately** aggregated on `(customer_id, provider, account_id, resource_id)` before joining. This avoids charging hourly utilization rows multiple times.
- External-shaped AWS/Azure/GCP CSVs are *alternative representations of the same charges*, not additional expenses. Provider-specific adapters map columns and reconcile totals against the canonical dataset.
- CPU p95 is the observed 95th percentile of the 720 hourly sampled CPU percentages. Sampled memory peak is an **observed** maximum, not a guarantee of true transient peak.
- Same-cloud right-sizing projects CPU p95 as `current_vcpu × current_cpu_p95 / candidate_vcpu` and memory load as `observed_peak_gib / candidate_memory_gib`. A candidate passes only if both are within the resource thresholds and cost decreases. This assumes equivalent per-vCPU compute capacity **for this toy exercise only**.
- Scheduling assumes 22 weekdays × 8 hours (176 hours) in September 2026 and a constant illustrative hourly compute rate. Actual runtime savings may differ due to reboot time, dependent services, storage and traffic.
- A daily price spike is detected on increased unit price with constant billed hours; this is flagged for human investigation instead of being treated as automatically avoidable.
- Business-critical low-activity resources are *never automatically deleted*. Missing memory measurements block recommendations. All fictional customer policies prohibit cross-cloud migrations and require approvals.
- The dataset excludes network egress, storage, reservations, tax, credits, compatibility validation, actual latency, compliance verification and sustained performance measurements. The application makes **screening suggestions**, not safe production change decisions.
- Only **September 2026 synthetic compute data** is modeled; no actual provider or customer data or credentials are required.

## What to build next (after the demo)

1. Replace CSV adapters with authenticated cloud read-only billing/metrics API integration.
2. Add persistent datasets and users with isolation/security controls.
3. Migrate frontend to React and optionally embed Grafana/Prometheus monitoring.
4. Add prices from authenticated published sources, equivalent workload/region constraints, latency and egress fees.
5. Add policy approval workflows; migrate workloads only after production design/testing.
