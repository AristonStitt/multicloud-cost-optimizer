"""Offline functional regression tests for the demo's critical claims."""
from fastapi.testclient import TestClient
from backend.main import app
from backend.analytics import summary, decisions, reconciliation, daily, resources, price_comparison

client = TestClient(app)


def test_homepage_and_health():
    assert client.get('/').status_code == 200
    assert 'CloudScope' in client.get('/').text
    assert client.get('/api/health').json() == {'ok': True, 'data_mode': 'synthetic'}


def test_billing_totals():
    overall = summary()
    assert overall['total_cost_usd'] == 5356.80
    assert overall['resource_count'] == 18
    assert overall['customer_count'] == 3
    assert overall['potential_savings_usd'] == 1041.60
    assert {r['provider']: r['cost_usd'] for r in overall['by_provider']} == {
        'AWS': 1728.0, 'Azure': 1728.0, 'GCP': 1900.8
    }
    assert summary('customer-001')['total_cost_usd'] == 1785.60
    assert len(resources()) == 18
    assert len(daily()) == 90


def test_reconciliation_no_double_counting():
    checked = reconciliation()
    assert checked['passed'] is True
    assert len(checked['checks']) == 9
    assert all(x['matches'] and x['raw_provider_adapter_matches'] for x in checked['checks'])


def test_decision_engine_findings_are_derived_not_labels():
    findings = decisions()
    assert len(findings) == 18
    count = {type_: sum(x['type'] == type_ for x in findings) for type_ in
             ('resize', 'schedule', 'price_spike', 'missing_data', 'idle_review', 'keep_capacity')}
    assert set(count.values()) == {3}
    c1 = decisions('customer-001')
    by_name = {item['resource_name']: item for item in c1}
    assert by_name['oversized-1']['estimated_savings_usd'] == 129.60
    assert by_name['oversized-1']['candidate']['projected_cpu_p95_pct'] <= 60
    assert by_name['dev_schedule-1']['estimated_savings_usd'] == 217.60
    assert by_name['spend_spike-1']['evidence'] == {
        'date': '2026-09-25', 'old_rate': 0.40, 'new_rate': 0.80, 'usage_hours': 24
    }
    assert by_name['missing_memory-1']['type'] == 'missing_data'
    assert by_name['busy-1']['type'] == 'keep_capacity'
    assert by_name['idle_review-1']['type'] == 'idle_review'


def test_cloud_comparison_does_not_claim_unrealistic_savings():
    comparison = price_comparison()
    assert comparison['cross_cloud_migration_allowed'] is False
    assert len(comparison['options']) == 3
    assert len(set(x['hourly_price_usd'] for x in comparison['options'])) == 1


def test_validation_and_openapi():
    assert client.get('/api/summary?customer=not-real').status_code == 404
    assert client.get('/api/price-comparison?machine_type=not-real').status_code == 404
    for path in ['/api/summary','/api/daily','/api/resources','/api/recommendations','/api/price-comparison','/api/reconciliation']:
        assert client.get(path).status_code == 200
    assert client.get('/openapi.json').status_code == 200


def test_explanations_have_measured_inputs_and_policy_gates():
    items = {x['resource_name']: x for x in decisions('customer-001')}
    resize = items['oversized-1']['explanation']
    assert resize['cpu_p95_pct'] is not None
    assert resize['observed_memory_peak_gib'] is not None
    assert resize['proposed_monthly_compute_usd'] == 158.40
    assert resize['approval_status'] == 'Not requested / not executed'
    assert len(resize['checks']) == 3
    assert all(c['passed'] for c in resize['checks'])
    missing = items['missing_memory-1']['explanation']
    assert missing['observed_memory_peak_gib'] is None
    assert missing['memory_missing_samples'] == 720
    assert not missing['checks'][0]['passed']


def test_execute_auditable_analysis_job():
    response = client.post('/api/analysis-jobs?customer=customer-001')
    assert response.status_code == 201
    job = response.json()
    assert job['status'] == 'completed'
    assert len(job['steps']) == 5
    assert all(step['status'] == 'completed' for step in job['steps'])
    assert job['result']['resources_evaluated'] == 6
    assert job['result']['reconciliation_checks_passed'] == 9
    assert job['result']['potential_savings_usd'] == 347.20
    assert client.get('/api/analysis-jobs/' + job['job_id']).json() == job
    assert client.post('/api/analysis-jobs?customer=unknown').status_code == 404
    assert client.get('/api/analysis-jobs/unknown').status_code == 404
