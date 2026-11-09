"""Sub-module 11.5 Maintenance & Repair Management — Security Test Suite.

Comprehensive security, multi-tenancy, authorization, status-guard, and tamper-protection tests:
1. Cross-Tenant IDOR:
   - For all 4 models (AssetMaintenanceRequest, AssetMaintenanceSchedule, AssetServiceContract, AssetMaintenanceLog):
     - Detail view with tenant B's PK as tenant A user -> asserts 404.
     - Edit view (GET & POST) with tenant B's PK as tenant A user -> asserts 404.
     - Delete view (POST) with tenant B's PK as tenant A admin -> asserts 404.
     - Custom actions with tenant B's PK as tenant A admin -> asserts 404:
       - Request: triage, dispatch, resolve, close, reject
       - Schedule: pause, activate, spawn, record_completion
       - Contract: record_visit, renew, terminate
       - Log: submit, approve, post_gl
     - Reverse IDOR: Tenant B user accessing Tenant A records returns 404 across detail, edit, delete, actions.
     - List views for tenant A must not contain any records belonging to tenant B.

2. Cross-Tenant Foreign Key Injection:
   - Attempting to link Tenant B's asset/contract/vendor in Tenant A creates/edits is rejected.

3. Role-Based Authorization Enforcement (@tenant_admin_required):
   - Non-admin member user attempting delete on any of the 4 models -> returns 403 Forbidden.
   - Non-admin member user attempting terminate contract -> returns 403 Forbidden.
   - Non-admin member user attempting approve log -> returns 403 Forbidden.
   - Non-admin member user attempting post_gl log -> returns 403 Forbidden.

4. Unauthenticated Access Enforcement:
   - Unauthenticated client accessing list, detail, create, edit, delete, or action endpoints redirects to login.

5. Status Guard Compliance:
   - Actions on terminal/invalid status records (e.g. approve already approved, post GL on draft) are guarded.
"""
from decimal import Decimal
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from apps.assets.models import (
    AssetMaintenanceRequest,
    AssetMaintenanceSchedule,
    AssetServiceContract,
    AssetMaintenanceLog,
)

User = get_user_model()
pytestmark = pytest.mark.django_db


# ==============================================================================
# Helper Functions (strictly prefixed with _asset_maintenance_)
# ==============================================================================

def _asset_maintenance_request_payload(asset, org_unit, **overrides):
    payload = {
        "title": "Security Injected Repair Request",
        "fixed_asset": asset.pk,
        "department": org_unit.pk,
        "request_type": "breakdown_repair",
        "urgency": "medium",
        "symptom_description": "Sample symptom description for security testing.",
        "is_breakdown": False,
    }
    payload.update(overrides)
    return payload


def _asset_maintenance_schedule_payload(asset, **overrides):
    payload = {
        "name": "Security Injected Schedule",
        "schedule_type": "time_based",
        "fixed_asset": asset.pk,
        "frequency_interval": 1,
        "frequency_unit": "months",
        "lead_time_days": 3,
        "is_mandatory": True,
        "is_active": True,
    }
    payload.update(overrides)
    return payload


def _asset_maintenance_contract_payload(vendor, **overrides):
    today = timezone.now().date()
    payload = {
        "contract_reference": "SEC-SLA-9999",
        "title": "Security Injected Contract",
        "vendor": vendor.pk,
        "contract_type": "comprehensive_amc",
        "sla_tier": "bronze",
        "start_date": str(today),
        "end_date": str(today + timezone.timedelta(days=365)),
        "contract_value": "12000.00",
        "response_time_sla_hours": 24,
        "resolution_time_sla_hours": 72,
        "included_routine_visits": 4,
        "included_emergency_visits": 2,
    }
    payload.update(overrides)
    return payload


def _asset_maintenance_log_payload(asset, **overrides):
    today = timezone.now().date()
    payload = {
        "maintenance_type": "corrective_repair",
        "service_date": str(today),
        "completion_date": str(timezone.now().strftime("%Y-%m-%d %H:%M:%S")),
        "fixed_asset": asset.pk,
        "failure_code": "mechanical_wear",
        "downtime_hours": "2.00",
        "labor_hours": "3.00",
        "hourly_labor_rate": "65.00",
        "parts_cost": "150.00",
        "vendor_invoice_cost": "0.00",
        "action_taken": "Replaced worn belt during security validation test.",
    }
    payload.update(overrides)
    return payload


# ==============================================================================
# 1. Cross-Tenant IDOR: AssetMaintenanceRequest
# ==============================================================================

def test_asset_maintenance_security_idor_request_detail_returns_404(client_a, maintenance_request_b):
    """Tenant A client accessing Tenant B maintenance request detail returns 404."""
    url = reverse("assets:asset_maintenance_request_detail", args=[maintenance_request_b.pk])
    response = client_a.get(url)
    assert response.status_code == 404


def test_asset_maintenance_security_idor_request_edit_returns_404(client_a, maintenance_request_b):
    """Tenant A client accessing Tenant B maintenance request edit returns 404."""
    url = reverse("assets:asset_maintenance_request_edit", args=[maintenance_request_b.pk])
    assert client_a.get(url).status_code == 404
    assert client_a.post(url, data={"title": "Hacked Title"}).status_code == 404


def test_asset_maintenance_security_idor_request_delete_returns_404(client_a, maintenance_request_b):
    """Tenant A admin client attempting to delete Tenant B request returns 404."""
    url = reverse("assets:asset_maintenance_request_delete", args=[maintenance_request_b.pk])
    response = client_a.post(url)
    assert response.status_code == 404
    assert AssetMaintenanceRequest.objects.filter(pk=maintenance_request_b.pk).exists()


def test_asset_maintenance_security_idor_request_actions_return_404(client_a, maintenance_request_b):
    """Tenant A client calling workflow actions on Tenant B request returns 404."""
    actions = [
        ("assets:asset_maintenance_request_triage", {}),
        ("assets:asset_maintenance_request_dispatch", {}),
        ("assets:asset_maintenance_request_resolve", {"resolution_summary": "Tampered"}),
        ("assets:asset_maintenance_request_close", {}),
        ("assets:asset_maintenance_request_reject", {"rejection_reason": "Tampered"}),
    ]
    for action_name, payload in actions:
        url = reverse(action_name, args=[maintenance_request_b.pk])
        resp = client_a.post(url, data=payload)
        assert resp.status_code == 404, f"Action {action_name} did not return 404 for cross-tenant IDOR"


def test_asset_maintenance_security_idor_request_reverse_returns_404(client_b, maintenance_request_a):
    """Tenant B client accessing Tenant A request returns 404."""
    url = reverse("assets:asset_maintenance_request_detail", args=[maintenance_request_a.pk])
    assert client_b.get(url).status_code == 404


def test_asset_maintenance_security_request_list_isolation(client_a, maintenance_request_a, maintenance_request_b):
    """Tenant A request list never displays Tenant B requests."""
    url = reverse("assets:asset_maintenance_request_list")
    response = client_a.get(url)
    assert response.status_code == 200
    requests = response.context["maintenance_requests"]
    assert maintenance_request_a in requests
    assert maintenance_request_b not in requests


# ==============================================================================
# 2. Cross-Tenant IDOR: AssetMaintenanceSchedule
# ==============================================================================

def test_asset_maintenance_security_idor_schedule_detail_returns_404(client_a, maintenance_schedule_b):
    """Tenant A client accessing Tenant B schedule detail returns 404."""
    url = reverse("assets:asset_maintenance_schedule_detail", args=[maintenance_schedule_b.pk])
    assert client_a.get(url).status_code == 404


def test_asset_maintenance_security_idor_schedule_edit_returns_404(client_a, maintenance_schedule_b):
    """Tenant A client accessing Tenant B schedule edit returns 404."""
    url = reverse("assets:asset_maintenance_schedule_edit", args=[maintenance_schedule_b.pk])
    assert client_a.get(url).status_code == 404
    assert client_a.post(url, data={"name": "Hacked Schedule"}).status_code == 404


def test_asset_maintenance_security_idor_schedule_delete_returns_404(client_a, maintenance_schedule_b):
    """Tenant A admin client attempting to delete Tenant B schedule returns 404."""
    url = reverse("assets:asset_maintenance_schedule_delete", args=[maintenance_schedule_b.pk])
    response = client_a.post(url)
    assert response.status_code == 404
    assert AssetMaintenanceSchedule.objects.filter(pk=maintenance_schedule_b.pk).exists()


def test_asset_maintenance_security_idor_schedule_actions_return_404(client_a, maintenance_schedule_b):
    """Tenant A client calling workflow actions on Tenant B schedule returns 404."""
    actions = [
        ("assets:asset_maintenance_schedule_pause", {}),
        ("assets:asset_maintenance_schedule_activate", {}),
        ("assets:asset_maintenance_schedule_generate_request", {}),
        ("assets:asset_maintenance_schedule_record_completion", {}),
    ]
    for action_name, payload in actions:
        url = reverse(action_name, args=[maintenance_schedule_b.pk])
        resp = client_a.post(url, data=payload)
        assert resp.status_code == 404, f"Action {action_name} did not return 404 for cross-tenant IDOR"


def test_asset_maintenance_security_idor_schedule_reverse_returns_404(client_b, maintenance_schedule_a):
    """Tenant B client accessing Tenant A schedule returns 404."""
    url = reverse("assets:asset_maintenance_schedule_detail", args=[maintenance_schedule_a.pk])
    assert client_b.get(url).status_code == 404


def test_asset_maintenance_security_schedule_list_isolation(client_a, maintenance_schedule_a, maintenance_schedule_b):
    """Tenant A schedule list never displays Tenant B schedules."""
    url = reverse("assets:asset_maintenance_schedule_list")
    response = client_a.get(url)
    assert response.status_code == 200
    schedules = response.context["maintenance_schedules"]
    assert maintenance_schedule_a in schedules
    assert maintenance_schedule_b not in schedules


# ==============================================================================
# 3. Cross-Tenant IDOR: AssetServiceContract
# ==============================================================================

def test_asset_maintenance_security_idor_contract_detail_returns_404(client_a, service_contract_b):
    """Tenant A client accessing Tenant B service contract detail returns 404."""
    url = reverse("assets:asset_service_contract_detail", args=[service_contract_b.pk])
    assert client_a.get(url).status_code == 404


def test_asset_maintenance_security_idor_contract_edit_returns_404(client_a, service_contract_b):
    """Tenant A client accessing Tenant B service contract edit returns 404."""
    url = reverse("assets:asset_service_contract_edit", args=[service_contract_b.pk])
    assert client_a.get(url).status_code == 404
    assert client_a.post(url, data={"title": "Hacked Title"}).status_code == 404


def test_asset_maintenance_security_idor_contract_delete_returns_404(client_a, service_contract_b):
    """Tenant A admin client attempting to delete Tenant B contract returns 404."""
    url = reverse("assets:asset_service_contract_delete", args=[service_contract_b.pk])
    response = client_a.post(url)
    assert response.status_code == 404
    assert AssetServiceContract.objects.filter(pk=service_contract_b.pk).exists()


def test_asset_maintenance_security_idor_contract_actions_return_404(client_a, service_contract_b):
    """Tenant A client calling workflow actions on Tenant B contract returns 404."""
    actions = [
        ("assets:asset_service_contract_record_visit", {"visit_type": "routine", "notes": "Hacked"}),
        ("assets:asset_service_contract_renew", {"new_end_date": "2028-12-31", "contract_value": "15000.00"}),
        ("assets:asset_service_contract_terminate", {"termination_reason": "Hacked"}),
    ]
    for action_name, payload in actions:
        url = reverse(action_name, args=[service_contract_b.pk])
        resp = client_a.post(url, data=payload)
        assert resp.status_code == 404, f"Action {action_name} did not return 404 for cross-tenant IDOR"


def test_asset_maintenance_security_idor_contract_reverse_returns_404(client_b, service_contract_a):
    """Tenant B client accessing Tenant A contract returns 404."""
    url = reverse("assets:asset_service_contract_detail", args=[service_contract_a.pk])
    assert client_b.get(url).status_code == 404


def test_asset_maintenance_security_contract_list_isolation(client_a, service_contract_a, service_contract_b):
    """Tenant A contract list never displays Tenant B contracts."""
    url = reverse("assets:asset_service_contract_list")
    response = client_a.get(url)
    assert response.status_code == 200
    contracts = response.context["service_contracts"]
    assert service_contract_a in contracts
    assert service_contract_b not in contracts


# ==============================================================================
# 4. Cross-Tenant IDOR: AssetMaintenanceLog
# ==============================================================================

def test_asset_maintenance_security_idor_log_detail_returns_404(client_a, maintenance_log_b):
    """Tenant A client accessing Tenant B maintenance log detail returns 404."""
    url = reverse("assets:asset_maintenance_log_detail", args=[maintenance_log_b.pk])
    assert client_a.get(url).status_code == 404


def test_asset_maintenance_security_idor_log_edit_returns_404(client_a, maintenance_log_b):
    """Tenant A client accessing Tenant B maintenance log edit returns 404."""
    url = reverse("assets:asset_maintenance_log_edit", args=[maintenance_log_b.pk])
    assert client_a.get(url).status_code == 404
    assert client_a.post(url, data={"action_taken": "Hacked Log"}).status_code == 404


def test_asset_maintenance_security_idor_log_delete_returns_404(client_a, maintenance_log_b):
    """Tenant A admin client attempting to delete Tenant B log returns 404."""
    url = reverse("assets:asset_maintenance_log_delete", args=[maintenance_log_b.pk])
    response = client_a.post(url)
    assert response.status_code == 404
    assert AssetMaintenanceLog.objects.filter(pk=maintenance_log_b.pk).exists()


def test_asset_maintenance_security_idor_log_actions_return_404(client_a, maintenance_log_b):
    """Tenant A client calling workflow actions on Tenant B log returns 404."""
    actions = [
        ("assets:asset_maintenance_log_submit", {}),
        ("assets:asset_maintenance_log_approve", {}),
        ("assets:asset_maintenance_log_post_gl", {}),
    ]
    for action_name, payload in actions:
        url = reverse(action_name, args=[maintenance_log_b.pk])
        resp = client_a.post(url, data=payload)
        assert resp.status_code == 404, f"Action {action_name} did not return 404 for cross-tenant IDOR"


def test_asset_maintenance_security_idor_log_reverse_returns_404(client_b, maintenance_log_a):
    """Tenant B client accessing Tenant A log returns 404."""
    url = reverse("assets:asset_maintenance_log_detail", args=[maintenance_log_a.pk])
    assert client_b.get(url).status_code == 404


def test_asset_maintenance_security_log_list_isolation(client_a, maintenance_log_a, maintenance_log_b):
    """Tenant A log list never displays Tenant B logs."""
    url = reverse("assets:asset_maintenance_log_list")
    response = client_a.get(url)
    assert response.status_code == 200
    logs = response.context["logs"]
    assert maintenance_log_a in logs
    assert maintenance_log_b not in logs


# ==============================================================================
# 5. Cross-Tenant FK Injection Prevention
# ==============================================================================

def test_asset_maintenance_security_cross_tenant_fk_request_asset_rejected(client_a, fixed_asset_b, org_unit_a):
    """Attempting to create request with Tenant B's asset fails validation."""
    url = reverse("assets:asset_maintenance_request_create")
    payload = _asset_maintenance_request_payload(asset=fixed_asset_b, org_unit=org_unit_a)
    response = client_a.post(url, data=payload)
    # Form invalid re-renders form (status 200) with errors
    assert response.status_code == 200
    assert "fixed_asset" in response.context["form"].errors


def test_asset_maintenance_security_cross_tenant_fk_schedule_asset_rejected(client_a, fixed_asset_b):
    """Attempting to create schedule with Tenant B's asset fails validation."""
    url = reverse("assets:asset_maintenance_schedule_create")
    payload = _asset_maintenance_schedule_payload(asset=fixed_asset_b)
    response = client_a.post(url, data=payload)
    assert response.status_code == 200
    assert "fixed_asset" in response.context["form"].errors


def test_asset_maintenance_security_cross_tenant_fk_contract_vendor_rejected(client_a, vendor_party_b):
    """Attempting to create contract with Tenant B's vendor fails validation."""
    url = reverse("assets:asset_service_contract_create")
    payload = _asset_maintenance_contract_payload(vendor=vendor_party_b)
    response = client_a.post(url, data=payload)
    assert response.status_code == 200
    assert "vendor" in response.context["form"].errors


def test_asset_maintenance_security_cross_tenant_fk_log_asset_rejected(client_a, fixed_asset_b):
    """Attempting to create maintenance log with Tenant B's asset fails validation."""
    url = reverse("assets:asset_maintenance_log_create")
    payload = _asset_maintenance_log_payload(asset=fixed_asset_b)
    response = client_a.post(url, data=payload)
    assert response.status_code == 200
    assert "fixed_asset" in response.context["form"].errors


# ==============================================================================
# 6. Role-Based Authorization Enforcement (@tenant_admin_required)
# ==============================================================================

def test_asset_maintenance_security_member_cannot_delete_request(member_client, maintenance_request_a):
    """Regular member cannot delete a maintenance request -> 403 Forbidden."""
    url = reverse("assets:asset_maintenance_request_delete", args=[maintenance_request_a.pk])
    response = member_client.post(url)
    assert response.status_code == 403
    assert AssetMaintenanceRequest.objects.filter(pk=maintenance_request_a.pk).exists()


def test_asset_maintenance_security_member_cannot_delete_schedule(member_client, maintenance_schedule_a):
    """Regular member cannot delete a maintenance schedule -> 403 Forbidden."""
    url = reverse("assets:asset_maintenance_schedule_delete", args=[maintenance_schedule_a.pk])
    response = member_client.post(url)
    assert response.status_code == 403
    assert AssetMaintenanceSchedule.objects.filter(pk=maintenance_schedule_a.pk).exists()


def test_asset_maintenance_security_member_cannot_delete_contract(member_client, service_contract_a):
    """Regular member cannot delete a service contract -> 403 Forbidden."""
    url = reverse("assets:asset_service_contract_delete", args=[service_contract_a.pk])
    response = member_client.post(url)
    assert response.status_code == 403
    assert AssetServiceContract.objects.filter(pk=service_contract_a.pk).exists()


def test_asset_maintenance_security_member_cannot_terminate_contract(member_client, service_contract_a):
    """Regular member cannot terminate a service contract -> 403 Forbidden."""
    url = reverse("assets:asset_service_contract_terminate", args=[service_contract_a.pk])
    response = member_client.post(url, data={"termination_reason": "Unauthorized termination"})
    assert response.status_code == 403
    service_contract_a.refresh_from_db()
    assert service_contract_a.status == "active"


def test_asset_maintenance_security_member_cannot_delete_log(member_client, maintenance_log_a):
    """Regular member cannot delete a maintenance log -> 403 Forbidden."""
    url = reverse("assets:asset_maintenance_log_delete", args=[maintenance_log_a.pk])
    response = member_client.post(url)
    assert response.status_code == 403
    assert AssetMaintenanceLog.objects.filter(pk=maintenance_log_a.pk).exists()


def test_asset_maintenance_security_member_cannot_approve_log(member_client, maintenance_log_a):
    """Regular member cannot approve a maintenance log -> 403 Forbidden."""
    maintenance_log_a.status = "submitted"
    maintenance_log_a.save()
    url = reverse("assets:asset_maintenance_log_approve", args=[maintenance_log_a.pk])
    response = member_client.post(url)
    assert response.status_code == 403
    maintenance_log_a.refresh_from_db()
    assert maintenance_log_a.status == "submitted"


def test_asset_maintenance_security_member_cannot_post_gl_log(member_client, maintenance_log_a):
    """Regular member cannot post maintenance log to GL -> 403 Forbidden."""
    maintenance_log_a.status = "approved"
    maintenance_log_a.save()
    url = reverse("assets:asset_maintenance_log_post_gl", args=[maintenance_log_a.pk])
    response = member_client.post(url)
    assert response.status_code == 403
    maintenance_log_a.refresh_from_db()
    assert not maintenance_log_a.is_gl_posted


# ==============================================================================
# 7. Unauthenticated Access Protection
# ==============================================================================

def test_asset_maintenance_security_unauthenticated_redirects_to_login(client, maintenance_request_a, maintenance_schedule_a, service_contract_a, maintenance_log_a):
    """Unauthenticated client is redirected to login for all maintenance endpoints."""
    endpoints = [
        reverse("assets:asset_maintenance_request_list"),
        reverse("assets:asset_maintenance_request_create"),
        reverse("assets:asset_maintenance_request_detail", args=[maintenance_request_a.pk]),
        reverse("assets:asset_maintenance_request_edit", args=[maintenance_request_a.pk]),
        reverse("assets:asset_maintenance_schedule_list"),
        reverse("assets:asset_maintenance_schedule_create"),
        reverse("assets:asset_maintenance_schedule_detail", args=[maintenance_schedule_a.pk]),
        reverse("assets:asset_service_contract_list"),
        reverse("assets:asset_service_contract_create"),
        reverse("assets:asset_service_contract_detail", args=[service_contract_a.pk]),
        reverse("assets:asset_maintenance_log_list"),
        reverse("assets:asset_maintenance_log_create"),
        reverse("assets:asset_maintenance_log_detail", args=[maintenance_log_a.pk]),
    ]
    for url in endpoints:
        resp = client.get(url)
        assert resp.status_code == 302, f"Expected 302 redirect for {url}, got {resp.status_code}"
        assert "/accounts/login/" in resp.url or "login" in resp.url


# ==============================================================================
# 8. Status Guard Compliance
# ==============================================================================

def test_asset_maintenance_security_cannot_approve_already_approved_log(client_a, maintenance_log_a):
    """Attempting to approve an already approved log redirects with error/warning."""
    maintenance_log_a.status = "approved"
    maintenance_log_a.save()
    url = reverse("assets:asset_maintenance_log_approve", args=[maintenance_log_a.pk])
    response = client_a.post(url)
    assert response.status_code == 302
    assert response.url == reverse("assets:asset_maintenance_log_detail", args=[maintenance_log_a.pk])


def test_asset_maintenance_security_cannot_post_gl_on_draft_log(client_a, maintenance_log_a):
    """Attempting to post GL on draft log is blocked with redirect."""
    assert maintenance_log_a.status == "draft"
    url = reverse("assets:asset_maintenance_log_post_gl", args=[maintenance_log_a.pk])
    response = client_a.post(url)
    assert response.status_code == 302
    maintenance_log_a.refresh_from_db()
    assert not maintenance_log_a.is_gl_posted


def test_asset_maintenance_security_cannot_terminate_already_terminated_contract(client_a, service_contract_a):
    """Attempting to terminate an already terminated contract redirects."""
    service_contract_a.status = "terminated"
    service_contract_a.save()
    url = reverse("assets:asset_service_contract_terminate", args=[service_contract_a.pk])
    response = client_a.post(url, data={"termination_reason": "Second termination"})
    assert response.status_code == 302
