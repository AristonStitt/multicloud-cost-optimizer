"""Deterministic synthetic FinOps analytics; no live cloud integrations."""
from __future__ import annotations

from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
KEY = ["customer_id", "provider", "account_id", "resource_id"]
MONTH_HOURS = 720  # 2026-09-01 through 2026-10-01 UTC


def money(value: Any) -> float:
    """Round money in decimal space before converting to JSON-safe float."""
    return float(Decimal(str(value)).quantize(Decimal("0.01")))


def cents(value: Any) -> int:
    return int((Decimal(str(value)) * 100).to_integral_exact())


def usd_from_cents(value: int) -> float:
    return value / 100


@lru_cache(maxsize=1)
def load() -> dict[str, pd.DataFrame]:
    data = {}
    for item in ("customers", "resources", "billing_daily", "utilization_hourly", "candidate_prices", "reconciliation_totals"):
        data[item] = pd.read_csv(DATA_DIR / f"{item}.csv", dtype=str, keep_default_na=False)
    billing = data["billing_daily"]
    billing["cost_cents"] = billing["billed_cost_usd"].map(cents)
    billing["usage_quantity"] = pd.to_numeric(billing["usage_quantity"])
    utilization = data["utilization_hourly"]
    utilization["cpu_utilization_pct"] = pd.to_numeric(utilization["cpu_utilization_pct"], errors="coerce")
    utilization["memory_used_gib"] = pd.to_numeric(utilization["memory_used_gib"], errors="coerce")
    resources = data["resources"]
    for col in ("vcpu", "memory_gib", "max_cpu_p95_pct", "max_memory_peak_pct"):
        resources[col] = pd.to_numeric(resources[col])
    prices = data["candidate_prices"]
    for col in ("vcpu", "memory_gib"):
        prices[col] = pd.to_numeric(prices[col])
    prices["hourly_price_usd"] = prices["hourly_price_usd"].map(lambda v: Decimal(v))
    return data


@lru_cache(maxsize=1)
def resource_records() -> list[dict]:
    data = load()
    # Aggregate separately before joining: avoids multiplying daily charges by hourly samples.
    billing = data["billing_daily"].groupby(KEY, as_index=False).agg(
        cost_cents=("cost_cents", "sum"), hours=("usage_quantity", "sum")
    )
    util = data["utilization_hourly"].groupby(KEY, as_index=False).agg(
        cpu_p95=("cpu_utilization_pct", lambda s: round(s.quantile(0.95), 2)),
        memory_peak_gib=("memory_used_gib", "max"),
        sample_count=("cpu_utilization_pct", "count"),
        missing_memory_samples=("memory_used_gib", lambda s: int(s.isna().sum())),
    )
    merged = data["resources"].merge(billing, on=KEY, how="left", validate="one_to_one")
    merged = merged.merge(util, on=KEY, how="left", validate="one_to_one")
    rows = []
    for rec in merged.to_dict("records"):
        row = {}
        for k, val in rec.items():
            if pd.isna(val):
                row[k] = None
            elif hasattr(val, "item"):
                row[k] = val.item()
            else:
                row[k] = val
        row["cost_usd"] = usd_from_cents(row.pop("cost_cents"))
        rows.append(row)
    return rows


def customers() -> list[dict]:
    return load()["customers"].to_dict("records")


def valid_customer(customer: str | None) -> bool:
    return customer is None or customer in {x["customer_id"] for x in customers()}


def resources(customer: str | None = None) -> list[dict]:
    return [r for r in resource_records() if not customer or r["customer_id"] == customer]


def summary(customer: str | None = None) -> dict:
    rows = resources(customer)
    total = sum(cents(r["cost_usd"]) for r in rows)
    by_provider = [
        {"provider": p, "cost_usd": usd_from_cents(sum(cents(r["cost_usd"]) for r in rows if r["provider"] == p)),
         "resources": sum(r["provider"] == p for r in rows)}
        for p in ("AWS", "Azure", "GCP")
    ]
    recommendations = decisions(customer)
    potential = sum(cents(r["estimated_savings_usd"]) for r in recommendations if r["type"] in ("resize", "schedule"))
    return {"total_cost_usd": usd_from_cents(total), "resource_count": len(rows),
            "customer_count": len(set(r["customer_id"] for r in rows)),
            "potential_savings_usd": usd_from_cents(potential), "by_provider": by_provider,
            "recommendation_count": len(recommendations), "period": "2026-09-01 to 2026-09-30 UTC",
            "data_source": "Synthetic teaching data; not live billing or provider prices"}


def daily(customer: str | None = None) -> list[dict]:
    table = load()["billing_daily"]
    if customer:
        table = table.loc[table.customer_id == customer]
    grouped = table.groupby(["charge_date", "provider"], as_index=False).agg(cost_cents=("cost_cents", "sum"))
    return [{"date": r.charge_date, "provider": r.provider, "cost_usd": usd_from_cents(int(r.cost_cents))}
            for r in grouped.itertuples(index=False)]


def candidates(row: dict) -> list[dict]:
    """Screen options only within the same cloud, region, architecture and purchase model."""
    if row["memory_peak_gib"] is None:
        return []
    prices = load()["candidate_prices"]
    compatible = prices.loc[
        (prices.provider == row["provider"]) & (prices.region == row["region"])
        & (prices.architecture == row["architecture"])
        & (prices.pricing_model == row["pricing_model"])
        & (prices.vcpu < row["vcpu"])
    ]
    found = []
    for p in compatible.itertuples(index=False):
        projected_cpu = row["cpu_p95"] * row["vcpu"] / p.vcpu
        projected_mem_pct = row["memory_peak_gib"] * 100 / p.memory_gib
        safe_by_observed_metrics = projected_cpu <= row["max_cpu_p95_pct"] and projected_mem_pct <= row["max_memory_peak_pct"]
        prospective = p.hourly_price_usd * Decimal(MONTH_HOURS)
        saved = Decimal(str(row["cost_usd"])) - prospective
        found.append({"machine_type": p.machine_type, "vcpu": int(p.vcpu), "memory_gib": int(p.memory_gib),
                      "projected_cpu_p95_pct": round(projected_cpu, 2),
                      "projected_memory_peak_pct": round(projected_mem_pct, 2),
                      "projected_monthly_cost_usd": money(prospective),
                      "estimated_savings_usd": money(saved),
                      "screen_pass": bool(safe_by_observed_metrics and saved > 0)})
    return found


def daily_spike(row: dict) -> dict | None:
    raw = load()["billing_daily"]
    t = raw.loc[(raw.customer_id == row["customer_id"]) &
                (raw.provider == row["provider"]) &
                (raw.account_id == row["account_id"]) &
                (raw.resource_id == row["resource_id"])].sort_values("charge_date")
    previous = None
    for line in t.itertuples(index=False):
        rate = Decimal(line.unit_price_usd)
        hours = int(line.usage_quantity)
        if previous and rate >= previous[0] * Decimal("1.50") and hours == previous[1]:
            return {"date": line.charge_date, "old_rate": money(previous[0]), "new_rate": money(rate), "usage_hours": hours}
        previous = (rate, hours)
    return None


def explain(row: dict, finding: dict) -> dict:
    """Explain screening results without implying a production change was executed."""
    common = {
        "observation_period": "September 1–30, 2026 UTC (720 hourly samples expected)",
        "current_monthly_compute_usd": money(row["cost_usd"]),
        "current_capacity": f'{row["vcpu"]} vCPU / {row["memory_gib"]} GiB RAM',
        "cpu_p95_pct": round(row["cpu_p95"], 2) if row["cpu_p95"] is not None else None,
        "observed_memory_peak_gib": round(row["memory_peak_gib"], 2) if row["memory_peak_gib"] is not None else None,
        "metric_samples": int(row["sample_count"]),
        "memory_missing_samples": int(row["missing_memory_samples"]),
        "environment": row["environment"],
        "required_schedule": row["required_schedule_utc"],
        "assumptions": ["Fictional September 2026 compute-only pricing", "Hourly samples do not guarantee peak coverage"],
        "approval_status": "Not requested / not executed",
        "checks": [],
        "rejected_alternatives": [],
        "next_action": "Review the recommendation with the workload owner before any change.",
    }
    kind = finding["type"]
    if kind == "resize":
        candidate = finding["candidate"]
        common["proposed_capacity"] = f'{candidate["vcpu"]} vCPU / {candidate["memory_gib"]} GiB RAM'
        common["proposed_monthly_compute_usd"] = candidate["projected_monthly_cost_usd"]
        common["checks"] = [
            {"name": "Projected CPU p95", "observed": f'{candidate["projected_cpu_p95_pct"]:.2f}%', "rule": f'≤ {row["max_cpu_p95_pct"]:.0f}%', "passed": True},
            {"name": "Projected memory peak", "observed": f'{candidate["projected_memory_peak_pct"]:.2f}%', "rule": f'≤ {row["max_memory_peak_pct"]:.0f}%', "passed": True},
            {"name": "Modeled monthly savings", "observed": f'${candidate["estimated_savings_usd"]:.2f}', "rule": "> $0", "passed": True},
        ]
        for alt in candidates(row):
            if alt["screen_pass"] or alt["machine_type"] == candidate["machine_type"]:
                continue
            reasons = []
            if alt["projected_cpu_p95_pct"] > row["max_cpu_p95_pct"]:
                reasons.append(f'CPU {alt["projected_cpu_p95_pct"]:.2f}% exceeds {row["max_cpu_p95_pct"]:.0f}% limit')
            if alt["projected_memory_peak_pct"] > row["max_memory_peak_pct"]:
                reasons.append(f'Memory {alt["projected_memory_peak_pct"]:.2f}% exceeds {row["max_memory_peak_pct"]:.0f}% limit')
            if alt["estimated_savings_usd"] <= 0:
                reasons.append('No positive estimated savings')
            common["rejected_alternatives"].append({"candidate": alt["machine_type"], "reason": '; '.join(reasons)})
        common["assumptions"].append('CPU capacity scales proportionally between synthetic VM shapes')
        common["next_action"] = "Verify software compatibility, peak performance, and business approval before resizing."
    elif kind == "schedule":
        common["proposed_monthly_compute_usd"] = money(Decimal(str(row["cost_usd"])) * Decimal(176) / Decimal(MONTH_HOURS))
        common["checks"] = [
            {"name": "Environment", "observed": row["environment"], "rule": "development", "passed": True},
            {"name": "Required runtime", "observed": "176 of 720 hours", "rule": "Mon–Fri 09:00–17:00 UTC", "passed": True},
            {"name": "Estimated monthly savings", "observed": f'${finding["estimated_savings_usd"]:.2f}', "rule": "> $0", "passed": True},
        ]
        common["assumptions"].append('VM is stopped outside approved hours; no restart, storage, or service charges included')
        common["next_action"] = "Confirm the schedule with the owner and test clean shutdown/startup behavior."
    elif kind == "price_spike":
        issue = finding["evidence"]
        common["checks"] = [
            {"name": "Unit price changed", "observed": f'${issue["old_rate"]:.2f} → ${issue["new_rate"]:.2f}/hour', "rule": "Increase ≥ 50%", "passed": True},
            {"name": "Usage hours", "observed": f'{issue["usage_hours"]} hours/day', "rule": "Unchanged day to day", "passed": True},
        ]
        common["next_action"] = "Investigate the source rate change; do not claim avoidable savings without evidence."
    elif kind == "missing_data":
        common["checks"] = [{"name": "Memory data available", "observed": f'{row["missing_memory_samples"]} readings missing', "rule": "Memory needed before resize", "passed": False}]
        common["next_action"] = "Collect representative memory telemetry and re-run capacity checks."
    elif kind == "keep_capacity":
        common["checks"] = [{"name": "Observed CPU p95", "observed": f'{row["cpu_p95"]:.2f}%', "rule": f'≤ {row["max_cpu_p95_pct"]:.0f}%', "passed": False}]
        common["next_action"] = "Preserve current capacity; investigate CPU contention and burst requirements."
    elif kind == "idle_review":
        common["checks"] = [{"name": "Observed CPU p95", "observed": f'{row["cpu_p95"]:.2f}%', "rule": "< 5% investigation threshold", "passed": True}]
        common["next_action"] = "Confirm standby requirements, service ownership, and dependencies; do not auto-delete."
    else:
        common["next_action"] = "Retain current configuration unless further monitoring or pricing shows a viable alternative."
    return common


def decisions(customer: str | None = None) -> list[dict]:
    findings = []
    for r in resources(customer):
        base = {"customer_id": r["customer_id"], "provider": r["provider"], "resource_id": r["resource_id"],
                "resource_name": r["resource_name"], "estimated_savings_usd": 0.0}
        issue = daily_spike(r)
        if issue:
            findings.append({**base, "type": "price_spike", "severity": "warning", "title": "Investigate price increase",
                             "detail": f"On {issue['date']}, unit price rose from ${issue['old_rate']:.2f} to ${issue['new_rate']:.2f}/hour while usage stayed at {issue['usage_hours']} hours/day. No cost reduction assumed.",
                             "evidence": issue})
            continue
        if r["memory_peak_gib"] is None:
            findings.append({**base, "type": "missing_data", "severity": "warning", "title": "Collect memory measurements",
                             "detail": f"All {r['missing_memory_samples']} hourly memory readings are missing; resizing is not approved without this information."})
            continue
        if r["cpu_p95"] < 5.0:
            findings.append({**base, "type": "idle_review", "severity": "info", "title": "Review low-utilization VM",
                             "detail": f"CPU p95 is {r['cpu_p95']:.2f}%. Verify business purpose, standby requirement, owners and dependencies before considering any action. Never auto-delete."})
            continue
        if r["required_schedule_utc"] == "Mon-Fri 09:00-17:00" and r["environment"] == "development":
            hours = 22 * 8  # 22 weekdays in September 2026, UTC schedule
            proposed = Decimal(str(r["cost_usd"])) * Decimal(hours) / Decimal(MONTH_HOURS)
            saved = Decimal(str(r["cost_usd"])) - proposed
            findings.append({**base, "type": "schedule", "severity": "success", "title": "Schedule development compute",
                             "estimated_savings_usd": money(saved),
                             "detail": f"Run only weekdays 09:00–17:00 UTC ({hours} of 720 hours); projected compute spend ${money(proposed):.2f}, subject to owner approval and startup constraints."})
            continue
        if r["cpu_p95"] > r["max_cpu_p95_pct"]:
            findings.append({**base, "type": "keep_capacity", "severity": "info", "title": "Keep capacity; investigate performance",
                             "detail": f"CPU p95 is {r['cpu_p95']:.2f}% versus target {r['max_cpu_p95_pct']}%. Downsizing would be unsafe under this screening rule."})
            continue
        viable = [c for c in candidates(r) if c["screen_pass"]]
        if viable:
            best = max(viable, key=lambda c: c["estimated_savings_usd"])
            findings.append({**base, "type": "resize", "severity": "success", "title": f"Review right-sizing to {best['vcpu']} vCPU / {best['memory_gib']} GiB",
                             "estimated_savings_usd": best["estimated_savings_usd"],
                             "detail": f"Current CPU p95 {r['cpu_p95']:.2f}%, observed memory peak {r['memory_peak_gib']:.2f} GiB. Projected CPU p95 {best['projected_cpu_p95_pct']:.2f}%; memory peak {best['projected_memory_peak_pct']:.2f}% of candidate capacity. Requires compatibility and production approval.",
                             "candidate": best})
        else:
            findings.append({**base, "type": "no_change", "severity": "info", "title": "No safe size reduction identified",
                             "detail": "No cheaper same-cloud candidate passed the CPU and memory thresholds on the observed measurements."})
    # Each finding carries transparent, auditable evidence for the frontend.
    by_resource = {(r["customer_id"], r["provider"], r["resource_id"]): r for r in resources(customer)}
    for finding in findings:
        r = by_resource[(finding["customer_id"], finding["provider"], finding["resource_id"])]
        finding["explanation"] = explain(r, finding)
    ordering = {"resize": 0, "schedule": 1, "price_spike": 2, "missing_data": 3, "idle_review": 4, "keep_capacity": 5, "no_change": 6}
    return sorted(findings, key=lambda item: (ordering[item["type"]], item["customer_id"]))


def price_comparison(machine_type: str = "demo-4vcpu-16gib", customer: str | None = None) -> dict:
    prices = load()["candidate_prices"]
    sub = prices.loc[prices.machine_type == machine_type]
    items = [{"provider": p.provider, "region": p.region, "machine_type": p.machine_type,
              "hourly_price_usd": money(p.hourly_price_usd), "projected_720h_cost_usd": money(p.hourly_price_usd * Decimal(MONTH_HOURS))}
             for p in sub.itertuples(index=False)]
    users = [c for c in customers() if not customer or c["customer_id"] == customer]
    blocked = any(c["cross_cloud_migration_allowed"] == "False" for c in users)
    return {"machine_type": machine_type, "options": items,
            "cross_cloud_migration_allowed": not blocked,
            "note": "Fictional same-spec cloud prices; comparison is indicative, not a migration approval. All customers explicitly prohibit cross-cloud migration."}


def reconciliation() -> dict:
    data = load()
    grouped = data["billing_daily"].groupby(["customer_id", "provider"], as_index=False).agg(total=("cost_cents", "sum"))
    wanted = data["reconciliation_totals"]
    outcomes = []
    for row in wanted.itertuples(index=False):
        matches = grouped.loc[(grouped.customer_id == row.customer_id) & (grouped.provider == row.provider)]
        actual = int(matches.iloc[0].total) if len(matches) == 1 else -1
        expected = cents(row.billed_cost_usd)
        outcomes.append({"customer_id": row.customer_id, "provider": row.provider, "actual_usd": usd_from_cents(actual),
                         "expected_usd": usd_from_cents(expected), "matches": actual == expected})
    # normalize 3 heterogeneous toy provider CSVs; use only as check, not additional charges
    adapters = {
        "AWS": ("aws_billing", "customer", "account", "resource", "amount"),
        "Azure": ("azure_billing", "customerId", "subscription", "resourceId", "cost"),
        "GCP": ("gcp_billing", "tenant", "project", "resource_name", "cost_amount"),
    }
    normalized = []
    for provider, (file_name, cust, acct, res, amount) in adapters.items():
        d = pd.read_csv(DATA_DIR / f"{file_name}.csv", dtype=str)
        d = d.rename(columns={cust: "customer_id", acct: "account_id", res: "resource_id", amount: "cost"})
        d["provider"] = provider
        d["cents"] = d["cost"].map(cents)
        normalized.append(d[KEY + ["cents"]])
    merged = pd.concat(normalized, ignore_index=True).groupby(["customer_id", "provider"], as_index=False)["cents"].sum()
    for x in outcomes:
        v = merged.loc[(merged.customer_id == x["customer_id"]) & (merged.provider == x["provider"])]
        x["raw_provider_adapter_matches"] = len(v) == 1 and int(v.iloc[0].cents) == cents(x["actual_usd"])
    return {"passed": all(o["matches"] and o["raw_provider_adapter_matches"] for o in outcomes), "checks": outcomes,
            "note": "Provider CSVs are alternative representations of canonical charges, never additive."}
