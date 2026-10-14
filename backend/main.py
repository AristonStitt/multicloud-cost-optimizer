"""Friday demo service: REST API + static dashboard."""
from pathlib import Path
from datetime import datetime, timezone
from time import perf_counter
from uuid import uuid4
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from backend import analytics as a

app = FastAPI(title="Multi-Cloud Cost Optimizer", version="0.1.0",
              description="Synthetic offline teaching prototype. No production cloud credentials or migrations.")
FRONTEND = Path(__file__).resolve().parent.parent / "frontend"
app.mount("/assets", StaticFiles(directory=FRONTEND), name="assets")


def validate(customer: str | None) -> None:
    if not a.valid_customer(customer):
        raise HTTPException(404, "Customer not found")


@app.get("/")
def home():
    return FileResponse(FRONTEND / "index.html")


@app.get("/api/health")
def health():
    return {"ok": True, "data_mode": "synthetic"}


@app.get("/api/customers")
def get_customers():
    return a.customers()


@app.get("/api/summary")
def get_summary(customer: str | None = None):
    validate(customer)
    return a.summary(customer)


@app.get("/api/daily")
def get_daily(customer: str | None = None):
    validate(customer)
    return a.daily(customer)


@app.get("/api/resources")
def get_resources(customer: str | None = None):
    validate(customer)
    return a.resources(customer)


@app.get("/api/recommendations")
def get_recommendations(customer: str | None = None):
    validate(customer)
    return a.decisions(customer)


@app.get("/api/price-comparison")
def get_price_comparison(machine_type: str = Query("demo-4vcpu-16gib"), customer: str | None = None):
    validate(customer)
    out = a.price_comparison(machine_type, customer)
    if not out["options"]:
        raise HTTPException(404, "Unknown synthetic machine type")
    return out


@app.get("/api/reconciliation")
def get_reconciliation():
    return a.reconciliation()


# Deliberately in-memory, single-process run history for the classroom prototype.
# It is not a durable task queue or a live cloud-sync mechanism.
ANALYSIS_JOBS: dict[str, dict] = {}


@app.post("/api/analysis-jobs", status_code=201)
def start_analysis(customer: str | None = None):
    """Execute real, synchronous pipeline checks and retain their measured trace."""
    validate(customer)
    job_id = uuid4().hex[:12]
    job = {"job_id": job_id, "customer": customer or "all", "status": "running",
           "started_at_utc": datetime.now(timezone.utc).isoformat(), "steps": []}
    ANALYSIS_JOBS[job_id] = job
    try:
        def step(name, fn):
            start = perf_counter()
            value, message = fn()
            job["steps"].append({"step": name, "status": "completed", "details": message,
                                 "elapsed_ms": round((perf_counter() - start) * 1000, 2)})
            return value

        # Clear memoization so this request actually re-reads the provided local inputs.
        a.resource_records.cache_clear()
        a.load.cache_clear()
        step("Load source data", lambda: (a.load(),
            "Read canonical billing, inventory, utilization, prices, and customer policies from local CSVs."))
        checked = step("Normalize and reconcile billing", lambda: (
            a.reconciliation(), "Compare provider-shaped toy billing inputs to the 9 expected customer/provider totals."))
        if not checked["passed"]:
            raise ValueError("Billing reconciliation failed; recommendations were not approved for display")
        inventory = step("Aggregate resource utilization", lambda: (
            a.resources(customer), "Independently aggregate 30-day billing, CPU p95, and sampled memory peaks by resource."))
        findings = step("Evaluate policy-aware candidates", lambda: (
            a.decisions(customer), "Apply capacity, missing-data, schedule, anomaly, and customer-policy screening."))
        overall = step("Compute results for dashboard", lambda: (
            a.summary(customer), "Aggregate computed spend and non-overlapping modeled scheduling/right-sizing savings."))
        job["result"] = {"resources_evaluated": len(inventory), "findings": len(findings),
                         "total_cost_usd": overall["total_cost_usd"],
                         "potential_savings_usd": overall["potential_savings_usd"],
                         "reconciliation_checks_passed": len(checked["checks"])}
        job["status"] = "completed"
    except Exception as exc:
        job["status"] = "failed"
        job["error"] = str(exc)
    job["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    # Only retain the latest 30 runs for this demo process.
    while len(ANALYSIS_JOBS) > 30:
        del ANALYSIS_JOBS[next(iter(ANALYSIS_JOBS))]
    return job


@app.get("/api/analysis-jobs/{job_id}")
def get_analysis_job(job_id: str):
    if job_id not in ANALYSIS_JOBS:
        raise HTTPException(404, "Analysis job not found (in-memory history resets when server restarts)")
    return ANALYSIS_JOBS[job_id]
