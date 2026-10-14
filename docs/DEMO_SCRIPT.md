# Three-minute demonstration — CloudScope

**Opening (15 sec):** "CloudScope is our working multi-cloud compute-cost optimizer prototype. It normalizes fictional AWS, Azure, and GCP billing, merges resource utilization, and generates explainable optimization candidates. This demonstration uses synthetic sample data, not live customer accounts."

**1. Overview (35 sec):** Show the $5,356.80 total, the AWS/Azure/GCP provider breakdown, 18 VMs, the daily cost chart and $1,041.60 potential savings. Explain these are **computed estimates**, not realized savings. Change customer to Demo Cedar Retail; the total becomes $1,785.60.

**2. Run analysis (35 sec):** Open Analysis Activity, click `Run analysis now`. Point to 5 completed stages: load data, normalize/reconcile, aggregate utilization, evaluate policy constraints, compute dashboard. This runs actual local operations and records results rather than animating a fake progress bar.

**3. Explain recommendation (55 sec):** Open Recommendations; expand `Why this recommendation?` for `oversized-1`. Show measured CPU p95 and memory, candidate VM specifications, capacity checks and $129.60 of illustrative monthly savings. Show `dev_schedule-1` for the scheduling estimate ($217.60). Point out missing-memory finding prevents unsafe resize and price-spike case is flagged for investigation rather than treated as automatic savings.

**4. Resources and validation (25 sec):** Open Resources to show utilization and resource metadata; open Method & Validation to demonstrate alternate provider formats and 9 reconciled customer-provider billing scopes. Explain that cross-cloud migrations are blocked by this dataset's policies, and the price catalog offers no defensible cross-cloud savings claim.

**5. Close (15 sec):** "Our MVP proves the core pipeline—ingest, normalize, analyze, explain, display. Future work is authenticated customer cloud connectors, robust persistent storage, operational governance and live data collection. We do not make production changes automatically."

## Questions you should be ready for
- **Where does the data come from?** Educational CSV inputs representing three fictional customers and 18 VMs. Not real provider exports.
- **What is normalized?** Provider-shaped billing columns become a consistent customer/provider/resource/cost representation. Reconcile once; don't count provider CSVs and canonical CSV twice.
- **How are decisions made?** Explainable Python policy rules using CPU 95th percentile, observed memory peak, workload schedule, and candidate prices.
- **Is a recommendation guaranteed safe?** No. It requires real-world compatibility/performance evaluation and customer approval.
- **What is the actual architecture?** Python analytics → FastAPI → HTML/CSS/JavaScript dashboard, with tests. React, PostgreSQL, Grafana and live provider APIs are planned, not part of this prototype.
