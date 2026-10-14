# What changed after reviewing the teammate's 28-page reference chat

The teammate's document is an architectural discussion, not a code repository or evidence of completed integration. It proposes the following conceptual product pipeline:

Customer-authorized cloud data access -> usage/billing/resource normalization -> evidence-based, constrained decision engine -> dashboard explaining recommendations and analysis jobs.

## What is implemented in this ZIP

- Synthetic, **non-FOCUS-certified** CSV adapters for differently shaped AWS/Azure/GCP teaching inputs.
- Reconciled billing, utilization metrics, cost breakdown, rules-driven right-sizing, scheduling, price-anomaly flags, and customer policy restrictions.
- `Analysis Activity` page: on-demand execution of real local data-processing steps; per-step outcomes and trace stored in memory, **not** fake cloud sync or real-time status animation.
- Expandable `Why this recommendation?` details including observed CPU p95 and memory, capacity thresholds, rejected smaller candidates where applicable, modeled savings, assumptions, human review, and lack of execution.
- FastAPI endpoints and a standalone dashboard with filtering.

## What is not implemented (future work)

- Customer AWS IAM role trust, Azure service principals, or GCP workload identity; these require live credentials and security review.
- Live cost exports, FOCUS-compliant ingestion, real provider pricing, infrastructure provisioning/migration, and savings verified on customer bills.
- React, Grafana, Prometheus, PostgreSQL, persistent background job queue, production authentication, and customer-access controls.

For Friday's demo, avoid claiming cloud accounts are connected, policies are enforced through authenticated user roles, machine sizes are real provider SKUs, or savings were realized. Show proof of the data analysis instead.

## Suggested short demo

1. Overview: $5,356.80 fictional spending; 18 VMs; 3 customers; $1,041.60 potential—not realized—compute-only savings.
2. Analysis Activity: run the pipeline; show 5 actual stages and nine billing reconciliation checks.
3. Recommendations: expand oversized-1 to show CPU/memory constraints, rejected 2-vCPU candidate, $129.60 estimate; expand schedule for $217.60 projected benefit.
4. Highlight price spike and missing-memory guardrail as examples of refusing unsupported cost actions.
5. Method & Validation: verify equal same-spec provider catalog prices and blocked migrations. Next phase: read-only cloud connectors and durable app storage.
