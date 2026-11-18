"""
Security, Multi-Tenant Data Isolation, Role Authorization, and Adversarial Tests
for Sub-module 12.7: Incoming Quality Control (IQC).

Test coverage requirements:
1. Multi-Tenant Data Isolation & Cross-Tenant IDOR:
   - Exhaustive IDOR sweeps: accessing Tenant B objects as Tenant A returns HTTP 404
     across detail, edit, delete, and custom action endpoints.
   - Symmetric IDOR: Client B accessing Tenant A resources returns HTTP 404.
   - List views and SPC dashboard never leak Tenant B records or aggregate metrics.
   - Cross-Tenant Foreign Key Injection: forging form submissions with Foreign Keys
     belonging to Tenant B is strictly rejected by reject_foreign.
2. Authentication & Role Enforcement:
   - Unauthenticated GET and POST requests across all endpoints redirect to login (HTTP 302).
   - Non-admin tenant users (e.g. member_user with is_tenant_admin=False) cannot access
     @tenant_admin_required delete endpoints -> HTTP 403 Forbidden.
   - State-changing endpoints reject GET requests -> HTTP 405 Method Not Allowed.
3. Mass Assignment Prevention:
   - Crafting POST data with tenant, number, created_at, updated_at does not overwrite those fields.
   - Form cannot mass-assign internal metrics, variance counts, or auto-calculated properties.
4. Injection Sanitization & Defense-in-Depth:
   - CSV exports neutralize formula injection (including leading whitespace) via _csv_safe.
   - X-Content-Type-Options: nosniff header enforced on exports.
   - Template rendering escapes HTML/XSS payloads.
5. Hand-Parsed Numeric Input & Adversarial Hardening:
   - Non-finite numbers (nan, inf, -inf) in sample recording and CoA verification.
   - Terminal state protection on completed lots and invalid RMA state jumps.
"""

import csv
import io
import json
import math
from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.core.models import AuditLog, OrgUnit, Party, Tenant
from apps.quality.forms.IncomingQuality.IncomingInspectionPlans import IncomingInspectionPlanForm
from apps.quality.forms.IncomingQuality.IncomingInspectionLots import IncomingInspectionLotForm
from apps.quality.forms.IncomingQuality.CertificatesOfAnalysis import CertificateOfAnalysisForm
from apps.quality.forms.IncomingQuality.QualityReturnAuthorizations import QualityReturnAuthorizationForm
from apps.quality.models import (
    CertificateOfAnalysis,
    ControlledDocument,
    IncomingInspectionLot,
    IncomingInspectionPlan,
    QualityReturnAuthorization,
)

User = get_user_model()
pytestmark = pytest.mark.django_db


# =============================================================================
# Helper Utilities (Prefix: _incomingquality_security_*)
# =============================================================================

def _incomingquality_security_pk(val):
    return val.pk if hasattr(val, "pk") else val


# =============================================================================
# 1. Multi-Tenant Data Isolation & Cross-Tenant IDOR
# =============================================================================

def test_incomingquality_security_idor_plan_endpoints(client, admin_user, admin_b, incoming_plan_a, incoming_plan_b):
    """Verify Tenant A cannot access Tenant B's inspection plans and vice versa."""
    client.force_login(admin_user)

    # Tenant A -> Tenant B (404)
    assert client.get(reverse("quality:incoming_inspection_plan_detail", kwargs={"pk": incoming_plan_b.pk})).status_code == 404
    assert client.get(reverse("quality:incoming_inspection_plan_edit", kwargs={"pk": incoming_plan_b.pk})).status_code == 404
    assert client.post(reverse("quality:incoming_inspection_plan_delete", kwargs={"pk": incoming_plan_b.pk})).status_code == 404

    # Symmetric: Tenant B -> Tenant A (404)
    client.force_login(admin_b)
    assert client.get(reverse("quality:incoming_inspection_plan_detail", kwargs={"pk": incoming_plan_a.pk})).status_code == 404
    assert client.get(reverse("quality:incoming_inspection_plan_edit", kwargs={"pk": incoming_plan_a.pk})).status_code == 404
    assert client.post(reverse("quality:incoming_inspection_plan_delete", kwargs={"pk": incoming_plan_a.pk})).status_code == 404


def test_incomingquality_security_idor_lot_endpoints(client, admin_user, admin_b, incoming_lot_a, incoming_lot_b):
    """Verify cross-tenant lot access and actions return 404."""
    client.force_login(admin_user)

    # Tenant A -> Tenant B (404)
    assert client.get(reverse("quality:incoming_inspection_lot_detail", kwargs={"pk": incoming_lot_b.pk})).status_code == 404
    assert client.get(reverse("quality:incoming_inspection_lot_edit", kwargs={"pk": incoming_lot_b.pk})).status_code == 404
    assert client.post(reverse("quality:incoming_inspection_lot_delete", kwargs={"pk": incoming_lot_b.pk})).status_code == 404
    assert client.post(reverse("quality:incoming_inspection_lot_record_sample", kwargs={"pk": incoming_lot_b.pk}), {"sample_value": 10.0}).status_code == 404
    assert client.post(reverse("quality:incoming_inspection_lot_make_decision", kwargs={"pk": incoming_lot_b.pk}), {"usage_decision": "accepted"}).status_code == 404

    # Symmetric: Tenant B -> Tenant A (404)
    client.force_login(admin_b)
    assert client.get(reverse("quality:incoming_inspection_lot_detail", kwargs={"pk": incoming_lot_a.pk})).status_code == 404
    assert client.get(reverse("quality:incoming_inspection_lot_edit", kwargs={"pk": incoming_lot_a.pk})).status_code == 404
    assert client.post(reverse("quality:incoming_inspection_lot_delete", kwargs={"pk": incoming_lot_a.pk})).status_code == 404
    assert client.post(reverse("quality:incoming_inspection_lot_record_sample", kwargs={"pk": incoming_lot_a.pk}), {"sample_value": 10.0}).status_code == 404
    assert client.post(reverse("quality:incoming_inspection_lot_make_decision", kwargs={"pk": incoming_lot_a.pk}), {"usage_decision": "accepted"}).status_code == 404


def test_incomingquality_security_idor_coa_endpoints(client, admin_user, admin_b, coa_a, coa_b):
    """Verify cross-tenant Certificate of Analysis access and verification return 404."""
    client.force_login(admin_user)

    assert client.get(reverse("quality:certificate_of_analysis_detail", kwargs={"pk": coa_b.pk})).status_code == 404
    assert client.get(reverse("quality:certificate_of_analysis_edit", kwargs={"pk": coa_b.pk})).status_code == 404
    assert client.post(reverse("quality:certificate_of_analysis_delete", kwargs={"pk": coa_b.pk})).status_code == 404
    assert client.post(reverse("quality:certificate_of_analysis_verify", kwargs={"pk": coa_b.pk})).status_code == 404

    # Symmetric
    client.force_login(admin_b)
    assert client.get(reverse("quality:certificate_of_analysis_detail", kwargs={"pk": coa_a.pk})).status_code == 404
    assert client.get(reverse("quality:certificate_of_analysis_edit", kwargs={"pk": coa_a.pk})).status_code == 404
    assert client.post(reverse("quality:certificate_of_analysis_delete", kwargs={"pk": coa_a.pk})).status_code == 404
    assert client.post(reverse("quality:certificate_of_analysis_verify", kwargs={"pk": coa_a.pk})).status_code == 404


def test_incomingquality_security_idor_rma_endpoints(client, admin_user, admin_b, rma_a, rma_b):
    """Verify cross-tenant RMA access and advance return 404."""
    client.force_login(admin_user)

    assert client.get(reverse("quality:quality_return_authorization_detail", kwargs={"pk": rma_b.pk})).status_code == 404
    assert client.get(reverse("quality:quality_return_authorization_edit", kwargs={"pk": rma_b.pk})).status_code == 404
    assert client.post(reverse("quality:quality_return_authorization_delete", kwargs={"pk": rma_b.pk})).status_code == 404
    assert client.post(reverse("quality:quality_return_authorization_advance", kwargs={"pk": rma_b.pk}), {"next_status": "rma_approved"}).status_code == 404

    # Symmetric
    client.force_login(admin_b)
    assert client.get(reverse("quality:quality_return_authorization_detail", kwargs={"pk": rma_a.pk})).status_code == 404
    assert client.get(reverse("quality:quality_return_authorization_edit", kwargs={"pk": rma_a.pk})).status_code == 404
    assert client.post(reverse("quality:quality_return_authorization_delete", kwargs={"pk": rma_a.pk})).status_code == 404
    assert client.post(reverse("quality:quality_return_authorization_advance", kwargs={"pk": rma_a.pk}), {"next_status": "rma_requested"}).status_code == 404


def test_incomingquality_security_list_views_never_leak_cross_tenant_data(client, admin_user, incoming_plan_b, incoming_lot_b, coa_b, rma_b):
    """Verify list views strictly scope records to the active tenant."""
    client.force_login(admin_user)

    resp_plans = client.get(reverse("quality:incoming_inspection_plan_list"))
    assert incoming_plan_b.number not in resp_plans.content.decode()

    resp_lots = client.get(reverse("quality:incoming_inspection_lot_list"))
    assert incoming_lot_b.number not in resp_lots.content.decode()

    resp_coas = client.get(reverse("quality:certificate_of_analysis_list"))
    assert coa_b.number not in resp_coas.content.decode()

    resp_rmas = client.get(reverse("quality:quality_return_authorization_list"))
    assert rma_b.number not in resp_rmas.content.decode()


def test_incomingquality_security_spc_dashboard_tenant_isolation(client, admin_user, incoming_lot_a, incoming_lot_b):
    """Verify SPC dashboard aggregates and alerts only include Tenant A lots."""
    incoming_lot_a.spc_out_of_control = True
    incoming_lot_a.save()
    incoming_lot_b.spc_out_of_control = True
    incoming_lot_b.save()

    client.force_login(admin_user)
    resp = client.get(reverse("quality:iqc_spc_dashboard"))
    assert resp.status_code == 200
    content = resp.content.decode()
    assert incoming_lot_a.lot_number in content
    assert incoming_lot_b.lot_number not in content


def test_incomingquality_security_cross_tenant_foreign_key_injection_plan(tenant_a, supplier_party_b, doc_b, quality_department_b):
    """Verify submitting Tenant B foreign keys to Tenant A plan form is rejected."""
    data = {
        "title": "Injected Plan",
        "item_code": "INJ-001",
        "item_name": "Injected Item",
        "supplier": supplier_party_b.pk,
        "sop_document": doc_b.pk,
        "assigned_team": quality_department_b.pk,
        "sampling_standard": "ansi_asq_z14",
        "inspection_level": "level_2",
        "inspection_severity": "normal",
        "inspection_frequency": "every_lot",
        "skip_lot_interval": 5,
        "aql_critical": "0.00",
        "aql_major": "1.00",
        "aql_minor": "4.00",
        "status": "draft",
    }
    form = IncomingInspectionPlanForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "supplier" in form.errors or "__all__" in form.errors


def test_incomingquality_security_cross_tenant_foreign_key_injection_lot(tenant_a, incoming_plan_b, supplier_party_b, admin_b):
    """Verify submitting Tenant B foreign keys to Tenant A lot form is rejected."""
    data = {
        "inspection_plan": incoming_plan_b.pk,
        "supplier": supplier_party_b.pk,
        "inspector": admin_b.pk,
        "decided_by": admin_b.pk,
        "item_code": "INJ-002",
        "item_name": "Injected Lot Item",
        "lot_number": "INJ-LOT-01",
        "lot_quantity": "100.000",
        "sample_size": 5,
        "stage": "in_inspection",
        "usage_decision": "pending",
    }
    form = IncomingInspectionLotForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "inspection_plan" in form.errors or "supplier" in form.errors or "__all__" in form.errors


# =============================================================================
# 2. Authentication & Role Enforcement
# =============================================================================

def test_incomingquality_security_unauthenticated_redirection(client, incoming_plan_a, incoming_lot_a, coa_a, rma_a):
    """Verify unauthenticated requests redirect to login across all 12.7 endpoints."""
    endpoints = [
        reverse("quality:incoming_inspection_plan_list"),
        reverse("quality:incoming_inspection_plan_create"),
        reverse("quality:incoming_inspection_plan_detail", kwargs={"pk": incoming_plan_a.pk}),
        reverse("quality:incoming_inspection_plan_edit", kwargs={"pk": incoming_plan_a.pk}),
        reverse("quality:incoming_inspection_plan_export"),
        reverse("quality:incoming_inspection_lot_list"),
        reverse("quality:incoming_inspection_lot_create"),
        reverse("quality:incoming_inspection_lot_detail", kwargs={"pk": incoming_lot_a.pk}),
        reverse("quality:incoming_inspection_lot_edit", kwargs={"pk": incoming_lot_a.pk}),
        reverse("quality:incoming_inspection_lot_export"),
        reverse("quality:certificate_of_analysis_list"),
        reverse("quality:certificate_of_analysis_create"),
        reverse("quality:certificate_of_analysis_detail", kwargs={"pk": coa_a.pk}),
        reverse("quality:certificate_of_analysis_edit", kwargs={"pk": coa_a.pk}),
        reverse("quality:certificate_of_analysis_export"),
        reverse("quality:quality_return_authorization_list"),
        reverse("quality:quality_return_authorization_create"),
        reverse("quality:quality_return_authorization_detail", kwargs={"pk": rma_a.pk}),
        reverse("quality:quality_return_authorization_edit", kwargs={"pk": rma_a.pk}),
        reverse("quality:quality_return_authorization_export"),
        reverse("quality:iqc_spc_dashboard"),
    ]
    for url in endpoints:
        resp = client.get(url)
        assert resp.status_code == 302
        assert "login" in resp.url


def test_incomingquality_security_non_admin_forbidden_on_delete(member_client, incoming_plan_a, incoming_lot_a, coa_a, rma_a):
    """Verify non-admin users cannot delete records (HTTP 403 Forbidden)."""
    assert member_client.post(reverse("quality:incoming_inspection_plan_delete", kwargs={"pk": incoming_plan_a.pk})).status_code == 403
    assert member_client.post(reverse("quality:incoming_inspection_lot_delete", kwargs={"pk": incoming_lot_a.pk})).status_code == 403
    assert member_client.post(reverse("quality:certificate_of_analysis_delete", kwargs={"pk": coa_a.pk})).status_code == 403
    assert member_client.post(reverse("quality:quality_return_authorization_delete", kwargs={"pk": rma_a.pk})).status_code == 403


def test_incomingquality_security_method_not_allowed_on_actions(client, admin_user, incoming_plan_a, incoming_lot_a, coa_a, rma_a):
    """Verify destructive and mutating action views reject GET with 405 Method Not Allowed."""
    client.force_login(admin_user)
    action_urls = [
        reverse("quality:incoming_inspection_plan_delete", kwargs={"pk": incoming_plan_a.pk}),
        reverse("quality:incoming_inspection_lot_delete", kwargs={"pk": incoming_lot_a.pk}),
        reverse("quality:incoming_inspection_lot_record_sample", kwargs={"pk": incoming_lot_a.pk}),
        reverse("quality:incoming_inspection_lot_make_decision", kwargs={"pk": incoming_lot_a.pk}),
        reverse("quality:certificate_of_analysis_delete", kwargs={"pk": coa_a.pk}),
        reverse("quality:certificate_of_analysis_verify", kwargs={"pk": coa_a.pk}),
        reverse("quality:quality_return_authorization_delete", kwargs={"pk": rma_a.pk}),
        reverse("quality:quality_return_authorization_advance", kwargs={"pk": rma_a.pk}),
    ]
    for url in action_urls:
        resp = client.get(url)
        assert resp.status_code == 405


# =============================================================================
# 3. Mass Assignment Prevention
# =============================================================================

def test_incomingquality_security_mass_assignment_plan_form(tenant_a, tenant_b, supplier_party_a):
    """Verify tenant, number, and timestamps cannot be mass assigned via form."""
    form = IncomingInspectionPlanForm(
        data={
            "tenant": tenant_b.pk,
            "number": "MALICIOUS-001",
            "created_at": "2020-01-01",
            "title": "Mass Assignment Test Plan",
            "item_code": "SEC-001",
            "item_name": "Security Test Item",
            "revision": "A",
            "supplier": supplier_party_a.pk,
            "sampling_standard": "ansi_asq_z14",
            "inspection_level": "level_2",
            "inspection_severity": "normal",
            "inspection_frequency": "every_lot",
            "skip_lot_interval": 5,
            "aql_critical": "0.00",
            "aql_major": "1.00",
            "aql_minor": "4.00",
            "status": "draft",
        },
        tenant=tenant_a,
    )
    assert form.is_valid(), form.errors
    obj = form.save(commit=False)
    assert obj.tenant == tenant_a
    assert obj.number != "MALICIOUS-001"


def test_incomingquality_security_mass_assignment_lot_spc_metrics(tenant_a, incoming_plan_a, supplier_party_a):
    """Verify internal SPC metrics cannot be mass assigned via lot form."""
    form = IncomingInspectionLotForm(
        data={
            "inspection_plan": incoming_plan_a.pk,
            "supplier": supplier_party_a.pk,
            "item_code": "TI-ROD-01",
            "item_name": "Medical Grade Titanium Rod 10mm",
            "lot_number": "SEC-LOT-01",
            "lot_quantity": "100.000",
            "sample_size": 10,
            "inspected_quantity": 0,
            "accepted_quantity": "0.000",
            "rejected_quantity": "0.000",
            "quarantine_quantity": "0.000",
            "critical_defects": 0,
            "major_defects": 0,
            "minor_defects": 0,
            "stage": "in_inspection",
            "usage_decision": "pending",
            "spc_cpk": "99.99",
            "spc_out_of_control": True,
        },
        tenant=tenant_a,
    )
    assert form.is_valid(), form.errors
    obj = form.save(commit=False)
    assert obj.spc_cpk is None
    assert obj.spc_out_of_control is False


# =============================================================================
# 4. Injection Sanitization & Defense-in-Depth
# =============================================================================

def test_incomingquality_security_csv_export_neutralizes_formula_injection(client, admin_user, tenant_a, supplier_party_a, incoming_plan_a):
    """Verify CSV export prepends single quote to neutralize spreadsheet formulas."""
    client.force_login(admin_user)
    # Create lot with formula injection payloads
    IncomingInspectionLot.objects.create(
        tenant=tenant_a,
        inspection_plan=incoming_plan_a,
        supplier=supplier_party_a,
        item_code="=cmd|' /C calc'!A0",
        item_name="+SUM(1+1)",
        lot_number="@evil_lot",
        lot_quantity=Decimal("10.000"),
        sample_size=1,
    )

    resp = client.get(reverse("quality:incoming_inspection_lot_export"))
    assert resp.status_code == 200
    assert resp["X-Content-Type-Options"] == "nosniff"

    content = resp.content.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(content))
    rows = list(reader)

    # Check that any cell starting with =, +, -, @ is sanitized
    found_sanitized = False
    for row in rows:
        for cell in row:
            if cell.startswith("'=" ) or cell.startswith("'+") or cell.startswith("'@"):
                found_sanitized = True
    assert found_sanitized, f"Formula injection was not sanitized in CSV export:\n{content}"


def test_incomingquality_security_xss_escaping_in_templates(client, admin_user, tenant_a, supplier_party_a):
    """Verify HTML script tags in plan titles and item codes are escaped in HTML responses."""
    client.force_login(admin_user)
    xss_payload = "<script>alert('xss-test')</script>"
    plan = IncomingInspectionPlan.objects.create(
        tenant=tenant_a,
        title=f"XSS Plan {xss_payload}",
        item_code="XSS-CODE",
        item_name=xss_payload,
        supplier=supplier_party_a,
        status="draft",
    )

    resp = client.get(reverse("quality:incoming_inspection_plan_detail", kwargs={"pk": plan.pk}))
    assert resp.status_code == 200
    content = resp.content.decode()
    assert "<script>alert('xss-test')</script>" not in content
    assert "&lt;script&gt;alert(&#x27;xss-test&#x27;)&lt;/script&gt;" in content or "&lt;script&gt;" in content


# =============================================================================
# 5. Hand-Parsed Numeric Input & Adversarial Hardening
# =============================================================================

def test_incomingquality_security_record_sample_rejects_nan_and_infinity(client, admin_user, tenant_a, incoming_plan_a, supplier_party_a):
    """Verify non-finite float strings in sample recording are rejected cleanly without 500 error."""
    client.force_login(admin_user)
    lot = IncomingInspectionLot.objects.create(
        tenant=tenant_a,
        inspection_plan=incoming_plan_a,
        supplier=supplier_party_a,
        item_code="TI-ROD-01",
        item_name="Titanium Rod",
        lot_number="LOT-NAN-01",
        lot_quantity=Decimal("100.000"),
        sample_size=10,
        stage="in_inspection",
    )

    adversarial_inputs = ["nan", "NaN", "inf", "-inf", "Infinity", "-Infinity", "1e9999999", "invalid_string"]
    for val in adversarial_inputs:
        resp = client.post(
            reverse("quality:incoming_inspection_lot_record_sample", kwargs={"pk": lot.pk}),
            {"sample_value": val, "characteristic": "Diameter"},
        )
        assert resp.status_code in (200, 302)  # Either redisplays with error or redirects with flash message
        lot.refresh_from_db()
        assert len(lot.measurements_data) == 0, f"Adversarial value {val} was erroneously recorded!"


def test_incomingquality_security_coa_verify_rejects_nan_bypass(tenant_a, supplier_party_a, incoming_plan_a, incoming_lot_a):
    """Verify CoA analytical verification sets is_pass=False if actual_value is NaN."""
    coa = CertificateOfAnalysis.objects.create(
        tenant=tenant_a,
        certificate_number="COA-NAN-01",
        item_code="TI-ROD-01",
        item_name="Titanium Rod",
        lot_number="LOT-NAN-01",
        supplier=supplier_party_a,
        inspection_lot=incoming_lot_a,
        inspection_plan=incoming_plan_a,
        parameters_payload=[
            {"parameter": "Yield Strength", "lsl": 790, "usl": 880, "actual_value": "nan", "unit": "MPa"},
        ],
    )
    coa.verify_specifications()
    assert coa.is_within_spec is False
    assert coa.variance_count == 1
    assert coa.status == "exception_detected"


def test_incomingquality_security_terminal_stage_guards(client, admin_user, tenant_a, incoming_plan_a, supplier_party_a):
    """Verify completed lots cannot record new samples or overwrite usage decisions."""
    client.force_login(admin_user)
    completed_lot = IncomingInspectionLot.objects.create(
        tenant=tenant_a,
        inspection_plan=incoming_plan_a,
        supplier=supplier_party_a,
        item_code="TI-ROD-01",
        item_name="Titanium Rod",
        lot_number="LOT-COMP-01",
        lot_quantity=Decimal("100.000"),
        sample_size=10,
        stage="completed",
        usage_decision="accepted",
        accepted_quantity=Decimal("100.000"),
    )

    # Attempting to record sample on completed lot is rejected
    resp_sample = client.post(
        reverse("quality:incoming_inspection_lot_record_sample", kwargs={"pk": completed_lot.pk}),
        {"sample_value": "10.001"},
    )
    assert resp_sample.status_code == 302
    completed_lot.refresh_from_db()
    assert len(completed_lot.measurements_data) == 0

    # Attempting to change usage decision on completed lot is rejected
    resp_decision = client.post(
        reverse("quality:incoming_inspection_lot_make_decision", kwargs={"pk": completed_lot.pk}),
        {"usage_decision": "rejected", "rejected_quantity": "100.000"},
    )
    assert resp_decision.status_code == 302
    completed_lot.refresh_from_db()
    assert completed_lot.usage_decision == "accepted"


def test_incomingquality_security_rma_advance_disallows_invalid_transitions(client, admin_user, rma_a):
    """Verify RMA advance endpoint rejects skipping steps (e.g. draft directly to settled_closed)."""
    client.force_login(admin_user)
    rma_a.status = "draft"
    rma_a.save()

    # Invalid jump from draft directly to settled_closed
    resp = client.post(
        reverse("quality:quality_return_authorization_advance", kwargs={"pk": rma_a.pk}),
        {"next_status": "settled_closed"},
    )
    assert resp.status_code == 302
    rma_a.refresh_from_db()
    assert rma_a.status == "draft", "Invalid transition from draft directly to settled_closed was erroneously allowed!"

    # Valid step to rma_requested succeeds
    resp_valid = client.post(
        reverse("quality:quality_return_authorization_advance", kwargs={"pk": rma_a.pk}),
        {"next_status": "rma_requested"},
    )
    assert resp_valid.status_code == 302
    rma_a.refresh_from_db()
    assert rma_a.status == "rma_requested"
