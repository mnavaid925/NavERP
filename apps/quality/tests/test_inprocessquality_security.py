"""
Security, Multi-Tenant Data Isolation, Role Authorization, and Adversarial Tests
for Sub-module 12.8: In-Process Quality Control (IPQC).

Test coverage requirements:
1. Multi-Tenant Data Isolation & Cross-Tenant IDOR:
   - Cross-tenant GET detail for InProcessInspection, FirstArticleInspection, ProcessParameterLog, LayeredProcessAudit returns 404.
   - Cross-tenant POST edit returns 404.
   - Cross-tenant POST delete returns 404.
   - Cross-tenant POST FAI release returns 404.
   - Symmetric IDOR: Tenant B accessing Tenant A resources returns 404.
   - Cross-tenant list and SPC dashboard isolation: Tenant A never sees Tenant B records.
2. Form Foreign Key Boundary Enforcement (reject_foreign):
   - InProcessInspectionForm rejects foreign tenant's work_order, work_center, controlled_document, non_conformance, operator, inspector.
   - FirstArticleInspectionForm rejects foreign tenant's work_order, work_center, non_conformance, inspector.
   - ProcessParameterLogForm rejects foreign tenant's work_order, work_center, non_conformance, process_deviation.
   - LayeredProcessAuditForm rejects foreign tenant's work_center, org_unit, controlled_document, non_conformance, auditor.
3. Authentication & Authorization Gating:
   - All 26 view endpoints redirect unauthenticated requests to login (302).
   - Non-admin tenant users receive 403 Forbidden on delete endpoints.
   - Non-admin tenant users receive 403 Forbidden on FAI release endpoint.
   - GET requests to @require_POST endpoints (all 4 delete views + FAI release) return 405 Method Not Allowed.
4. Mass-Assignment & Tampering Protections:
   - Form submissions cannot override tenant, number, created_at, updated_at.
   - FirstArticleInspectionForm submission cannot spoof approved_by or approved_at.
   - ProcessParameterLogForm submission cannot spoof logged_by (server-side assigned to request.user).
   - LayeredProcessAuditForm submission cannot override compliance_percentage.
5. CSV Injection Formula Neutralization:
   - Exported CSV files neutralize formula injection characters (=, +, -, @, \\t, \\r) via _csv_safe.
   - Response headers include X-Content-Type-Options: nosniff.
   - Direct unit testing of _csv_safe sanitization logic.
6. XSS Protection:
   - Malicious <script> tags in character/text fields are HTML-escaped by Django templates.
"""

import csv
import io
from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from apps.core.models import OrgUnit, Tenant
from apps.quality.forms import (
    FirstArticleInspectionForm,
    InProcessInspectionForm,
    LayeredProcessAuditForm,
    ProcessParameterLogForm,
)
from apps.quality.forms._common import reject_foreign
from apps.quality.models import (
    ControlledDocument,
    FirstArticleInspection,
    InProcessInspection,
    LayeredProcessAudit,
    NonConformanceReport,
    ProcessDeviation,
    ProcessParameterLog,
)
from apps.quality.views.InProcessQuality.InProcessInspections import _csv_safe
from apps.scm.models import Item, WorkCenter, WorkOrder

User = get_user_model()
pytestmark = pytest.mark.django_db


# =============================================================================
# Helper Utilities (Prefix: _inprocessquality_*)
# =============================================================================

def _inprocessquality_pk(val):
    """Return pk if val is a model instance, or val itself if scalar / None."""
    if hasattr(val, "pk"):
        return val.pk
    return val


def _inprocessquality_date(days_offset=0):
    """Return an ISO formatted date string relative to today."""
    return (timezone.now().date() + timedelta(days=days_offset)).isoformat()


def _inprocessquality_datetime(days_offset=0):
    """Return an ISO formatted datetime string relative to now."""
    return (timezone.now() + timedelta(days=days_offset)).strftime("%Y-%m-%d %H:%M:%S")


def _inprocessquality_inspection_post_data(inspector=None, operator=None, doc=None, ncr=None, wo=None, wc=None, **extra):
    """Build valid baseline POST dictionary for InProcessInspectionForm."""
    data = {
        "title": "CNC Mill Line 2 In-Line Inspection",
        "inspection_type": "dimensional_gauging",
        "stage_gate": "Op 020 - Turning",
        "status": "completed",
        "disposition": "pass",
        "production_order_number": "PO-2026-8801",
        "work_order": _inprocessquality_pk(wo) if wo else "",
        "work_center_code": "WC-CNC-02",
        "work_center": _inprocessquality_pk(wc) if wc else "",
        "operation_step": "Op 020 - Rough Turning",
        "item_code": "ST-SHAFT-22",
        "item_name": "Precision Turbine Stainless Drive Shaft",
        "lot_number": "LOT-2026-IP-001",
        "serial_number": "SN-4140-001",
        "batch_quantity": 500,
        "sample_size_inspected": 5,
        "quantity_passed": 5,
        "quantity_rejected": 0,
        "quantity_reworked": 0,
        "defect_category": "",
        "defect_description": "",
        "controlled_document": _inprocessquality_pk(doc) if doc else "",
        "work_instruction_step": "WI-020 Step 3",
        "operator_sign_off": True,
        "operator": _inprocessquality_pk(operator) if operator else "",
        "inspector": _inprocessquality_pk(inspector) if inspector else "",
        "inspection_date": _inprocessquality_date(0),
        "non_conformance": _inprocessquality_pk(ncr) if ncr else "",
        "notes": "All diameters within blueprint limits.",
    }
    data.update(extra)
    return data


def _inprocessquality_fai_post_data(inspector=None, ncr=None, wo=None, wc=None, **extra):
    """Build valid baseline POST dictionary for FirstArticleInspectionForm."""
    data = {
        "title": "AS9102 Full FAI - Bracket",
        "fai_type": "full_fai",
        "setup_reason": "new_product_intro",
        "status": "in_inspection",
        "production_order_number": "PO-2026-FAI-01",
        "work_order": _inprocessquality_pk(wo) if wo else "",
        "work_center_code": "WC-CNC-01",
        "work_center": _inprocessquality_pk(wc) if wc else "",
        "machine_tooling_id": "CNC-04 Die-B2",
        "item_code": "AERO-BRKT-901",
        "item_name": "Titanium Support Bracket Strut",
        "drawing_number": "DWG-AERO-901",
        "drawing_revision": "Rev C",
        "first_piece_lot_number": "LOT-FAI-001",
        "serial_number": "SN-FAI-001",
        "total_characteristics_inspected": 18,
        "characteristics_conforming": 18,
        "characteristics_out_of_spec": 0,
        "max_deviation_found": "+0.003 mm on Bore Dia",
        "as9102_form1_complete": True,
        "as9102_form2_complete": True,
        "as9102_form3_complete": True,
        "gage_serial_numbers": "CMM-01, Caliper-402, HeightGage-12",
        "release_verdict": "pending",
        "conditional_release_notes": "",
        "non_conformance": _inprocessquality_pk(ncr) if ncr else "",
        "inspector": _inprocessquality_pk(inspector) if inspector else "",
        "notes": "Ballooned drawing characteristics verified on CMM.",
    }
    data.update(extra)
    return data


def _inprocessquality_param_post_data(wo=None, wc=None, ncr=None, dev=None, **extra):
    """Build valid baseline POST dictionary for ProcessParameterLogForm."""
    data = {
        "parameter_name": "Reflow Temperature",
        "parameter_category": "temperature",
        "unit_of_measure": "°C",
        "work_center_code": "WC-SMT-01",
        "work_center": _inprocessquality_pk(wc) if wc else "",
        "production_order_number": "PO-2026-8802",
        "work_order": _inprocessquality_pk(wo) if wo else "",
        "operation_step": "Op 040 SMT Reflow",
        "item_code": "PCB-A440",
        "lot_number": "LOT-2026-IP-002",
        "target_nominal_value": "245.0000",
        "lower_spec_limit": "235.0000",
        "upper_spec_limit": "255.0000",
        "lower_control_limit": "240.0000",
        "upper_control_limit": "250.0000",
        "recorded_value": "246.2000",
        "recorded_at": _inprocessquality_datetime(0),
        "excursion_status": "normal",
        "containment_action": "none",
        "containment_notes": "",
        "non_conformance": _inprocessquality_pk(ncr) if ncr else "",
        "process_deviation": _inprocessquality_pk(dev) if dev else "",
    }
    data.update(extra)
    return data


def _inprocessquality_audit_post_data(auditor=None, org_unit=None, doc=None, ncr=None, wc=None, **extra):
    """Build valid baseline POST dictionary for LayeredProcessAuditForm."""
    data = {
        "title": "Tier 1 Daily Shift LPA - Turning Cell",
        "audit_layer": "tier_1_operator_lead",
        "focus_area": "standard_work_wi",
        "status": "completed",
        "work_center_code": "WC-CNC-01",
        "work_center": _inprocessquality_pk(wc) if wc else "",
        "org_unit": _inprocessquality_pk(org_unit) if org_unit else "",
        "shift": "Shift 1 (Morning)",
        "scheduled_date": _inprocessquality_date(0),
        "conducted_at": _inprocessquality_datetime(0),
        "auditor": _inprocessquality_pk(auditor) if auditor else "",
        "total_questions_audited": 10,
        "questions_conforming": 10,
        "questions_non_conforming": 0,
        "controlled_document": _inprocessquality_pk(doc) if doc else "",
        "findings_summary": "",
        "on_the_spot_mitigation": False,
        "mitigation_details": "",
        "non_conformance": _inprocessquality_pk(ncr) if ncr else "",
        "notes": "5S audit and torque verification completed.",
    }
    data.update(extra)
    return data


# =============================================================================
# 1. Multi-Tenant Data Isolation & Cross-Tenant IDOR
# =============================================================================

def test_inprocessquality_security_idor_in_process_inspection_detail_edit_delete(
    client, admin_user, admin_b, in_process_inspection_a, in_process_inspection_b
):
    """Verify cross-tenant IDOR access on InProcessInspection returns 404 in both directions."""
    # Tenant A -> Tenant B (404)
    client.force_login(admin_user)
    assert client.get(
        reverse("quality:in_process_inspection_detail", kwargs={"pk": in_process_inspection_b.pk})
    ).status_code == 404
    assert client.get(
        reverse("quality:in_process_inspection_edit", kwargs={"pk": in_process_inspection_b.pk})
    ).status_code == 404
    assert client.post(
        reverse("quality:in_process_inspection_edit", kwargs={"pk": in_process_inspection_b.pk}),
        {"title": "Cross Tenant Tamper"},
    ).status_code == 404
    assert client.post(
        reverse("quality:in_process_inspection_delete", kwargs={"pk": in_process_inspection_b.pk})
    ).status_code == 404

    # Symmetric: Tenant B -> Tenant A (404)
    client.force_login(admin_b)
    assert client.get(
        reverse("quality:in_process_inspection_detail", kwargs={"pk": in_process_inspection_a.pk})
    ).status_code == 404
    assert client.get(
        reverse("quality:in_process_inspection_edit", kwargs={"pk": in_process_inspection_a.pk})
    ).status_code == 404
    assert client.post(
        reverse("quality:in_process_inspection_edit", kwargs={"pk": in_process_inspection_a.pk}),
        {"title": "Cross Tenant Tamper"},
    ).status_code == 404
    assert client.post(
        reverse("quality:in_process_inspection_delete", kwargs={"pk": in_process_inspection_a.pk})
    ).status_code == 404


def test_inprocessquality_security_idor_first_article_inspection_detail_edit_release_delete(
    client, admin_user, admin_b, fai_a, fai_b
):
    """Verify cross-tenant IDOR access and production release on FAI returns 404 symmetrically."""
    # Tenant A -> Tenant B (404)
    client.force_login(admin_user)
    assert client.get(
        reverse("quality:first_article_inspection_detail", kwargs={"pk": fai_b.pk})
    ).status_code == 404
    assert client.get(
        reverse("quality:first_article_inspection_edit", kwargs={"pk": fai_b.pk})
    ).status_code == 404
    assert client.post(
        reverse("quality:first_article_inspection_edit", kwargs={"pk": fai_b.pk}),
        {"title": "Cross Tenant Tamper"},
    ).status_code == 404
    assert client.post(
        reverse("quality:first_article_inspection_release", kwargs={"pk": fai_b.pk})
    ).status_code == 404
    assert client.post(
        reverse("quality:first_article_inspection_delete", kwargs={"pk": fai_b.pk})
    ).status_code == 404

    # Symmetric: Tenant B -> Tenant A (404)
    client.force_login(admin_b)
    assert client.get(
        reverse("quality:first_article_inspection_detail", kwargs={"pk": fai_a.pk})
    ).status_code == 404
    assert client.get(
        reverse("quality:first_article_inspection_edit", kwargs={"pk": fai_a.pk})
    ).status_code == 404
    assert client.post(
        reverse("quality:first_article_inspection_edit", kwargs={"pk": fai_a.pk}),
        {"title": "Cross Tenant Tamper"},
    ).status_code == 404
    assert client.post(
        reverse("quality:first_article_inspection_release", kwargs={"pk": fai_a.pk})
    ).status_code == 404
    assert client.post(
        reverse("quality:first_article_inspection_delete", kwargs={"pk": fai_a.pk})
    ).status_code == 404


def test_inprocessquality_security_idor_process_parameter_log_detail_edit_delete(
    client, admin_user, admin_b, parameter_log_a, parameter_log_b
):
    """Verify cross-tenant IDOR access on ProcessParameterLog returns 404 symmetrically."""
    # Tenant A -> Tenant B (404)
    client.force_login(admin_user)
    assert client.get(
        reverse("quality:process_parameter_log_detail", kwargs={"pk": parameter_log_b.pk})
    ).status_code == 404
    assert client.get(
        reverse("quality:process_parameter_log_edit", kwargs={"pk": parameter_log_b.pk})
    ).status_code == 404
    assert client.post(
        reverse("quality:process_parameter_log_edit", kwargs={"pk": parameter_log_b.pk}),
        {"parameter_name": "Tampered Param"},
    ).status_code == 404
    assert client.post(
        reverse("quality:process_parameter_log_delete", kwargs={"pk": parameter_log_b.pk})
    ).status_code == 404

    # Symmetric: Tenant B -> Tenant A (404)
    client.force_login(admin_b)
    assert client.get(
        reverse("quality:process_parameter_log_detail", kwargs={"pk": parameter_log_a.pk})
    ).status_code == 404
    assert client.get(
        reverse("quality:process_parameter_log_edit", kwargs={"pk": parameter_log_a.pk})
    ).status_code == 404
    assert client.post(
        reverse("quality:process_parameter_log_edit", kwargs={"pk": parameter_log_a.pk}),
        {"parameter_name": "Tampered Param"},
    ).status_code == 404
    assert client.post(
        reverse("quality:process_parameter_log_delete", kwargs={"pk": parameter_log_a.pk})
    ).status_code == 404


def test_inprocessquality_security_idor_layered_process_audit_detail_edit_delete(
    client, admin_user, admin_b, layered_audit_a, layered_audit_b
):
    """Verify cross-tenant IDOR access on LayeredProcessAudit returns 404 symmetrically."""
    # Tenant A -> Tenant B (404)
    client.force_login(admin_user)
    assert client.get(
        reverse("quality:layered_process_audit_detail", kwargs={"pk": layered_audit_b.pk})
    ).status_code == 404
    assert client.get(
        reverse("quality:layered_process_audit_edit", kwargs={"pk": layered_audit_b.pk})
    ).status_code == 404
    assert client.post(
        reverse("quality:layered_process_audit_edit", kwargs={"pk": layered_audit_b.pk}),
        {"title": "Tampered Audit"},
    ).status_code == 404
    assert client.post(
        reverse("quality:layered_process_audit_delete", kwargs={"pk": layered_audit_b.pk})
    ).status_code == 404

    # Symmetric: Tenant B -> Tenant A (404)
    client.force_login(admin_b)
    assert client.get(
        reverse("quality:layered_process_audit_detail", kwargs={"pk": layered_audit_a.pk})
    ).status_code == 404
    assert client.get(
        reverse("quality:layered_process_audit_edit", kwargs={"pk": layered_audit_a.pk})
    ).status_code == 404
    assert client.post(
        reverse("quality:layered_process_audit_edit", kwargs={"pk": layered_audit_a.pk}),
        {"title": "Tampered Audit"},
    ).status_code == 404
    assert client.post(
        reverse("quality:layered_process_audit_delete", kwargs={"pk": layered_audit_a.pk})
    ).status_code == 404


def test_inprocessquality_security_cross_tenant_list_views_data_isolation(
    client, admin_user, admin_b, in_process_inspection_a, in_process_inspection_b,
    fai_a, fai_b, parameter_log_a, parameter_log_b, layered_audit_a, layered_audit_b
):
    """Verify list views strictly filter records by tenant without cross-tenant leakage."""
    # Tenant A sees only Tenant A records
    client.force_login(admin_user)

    resp_insp = client.get(reverse("quality:in_process_inspection_list"))
    assert resp_insp.status_code == 200
    assert in_process_inspection_a in resp_insp.context["inspections"]
    assert in_process_inspection_b not in resp_insp.context["inspections"]
    content_insp = resp_insp.content.decode()
    assert in_process_inspection_a.title in content_insp
    assert in_process_inspection_b.title not in content_insp

    resp_fai = client.get(reverse("quality:first_article_inspection_list"))
    assert resp_fai.status_code == 200
    assert fai_a in resp_fai.context["fais"]
    assert fai_b not in resp_fai.context["fais"]
    content_fai = resp_fai.content.decode()
    assert fai_a.title in content_fai
    assert fai_b.title not in content_fai

    resp_log = client.get(reverse("quality:process_parameter_log_list"))
    assert resp_log.status_code == 200
    assert parameter_log_a in resp_log.context["parameter_logs"]
    assert parameter_log_b not in resp_log.context["parameter_logs"]
    content_log = resp_log.content.decode()
    assert parameter_log_a.parameter_name in content_log
    assert parameter_log_b.parameter_name not in content_log

    resp_lpa = client.get(reverse("quality:layered_process_audit_list"))
    assert resp_lpa.status_code == 200
    assert layered_audit_a in resp_lpa.context["lpas"]
    assert layered_audit_b not in resp_lpa.context["lpas"]
    content_lpa = resp_lpa.content.decode()
    assert layered_audit_a.title in content_lpa
    assert layered_audit_b.title not in content_lpa

    # Symmetric: Tenant B sees only Tenant B records
    client.force_login(admin_b)

    resp_insp_b = client.get(reverse("quality:in_process_inspection_list"))
    assert resp_insp_b.status_code == 200
    assert in_process_inspection_b in resp_insp_b.context["inspections"]
    assert in_process_inspection_a not in resp_insp_b.context["inspections"]
    content_insp_b = resp_insp_b.content.decode()
    assert in_process_inspection_b.title in content_insp_b
    assert in_process_inspection_a.title not in content_insp_b

    resp_fai_b = client.get(reverse("quality:first_article_inspection_list"))
    assert resp_fai_b.status_code == 200
    assert fai_b in resp_fai_b.context["fais"]
    assert fai_a not in resp_fai_b.context["fais"]
    content_fai_b = resp_fai_b.content.decode()
    assert fai_b.title in content_fai_b
    assert fai_a.title not in content_fai_b

    resp_log_b = client.get(reverse("quality:process_parameter_log_list"))
    assert resp_log_b.status_code == 200
    assert parameter_log_b in resp_log_b.context["parameter_logs"]
    assert parameter_log_a not in resp_log_b.context["parameter_logs"]
    content_log_b = resp_log_b.content.decode()
    assert parameter_log_b.parameter_name in content_log_b
    assert parameter_log_a.parameter_name not in content_log_b

    resp_lpa_b = client.get(reverse("quality:layered_process_audit_list"))
    assert resp_lpa_b.status_code == 200
    assert layered_audit_b in resp_lpa_b.context["lpas"]
    assert layered_audit_a not in resp_lpa_b.context["lpas"]
    content_lpa_b = resp_lpa_b.content.decode()
    assert layered_audit_b.title in content_lpa_b
    assert layered_audit_a.title not in content_lpa_b


def test_inprocessquality_security_cross_tenant_spc_dashboard_data_isolation(
    client, admin_user, admin_b, in_process_inspection_a, in_process_inspection_b,
    fai_a, fai_b, parameter_log_a, parameter_log_b, layered_audit_a, layered_audit_b
):
    """Verify SPC Control Dashboard aggregates and lists strictly scope to active tenant."""
    # Tenant A
    client.force_login(admin_user)
    resp_a = client.get(reverse("quality:spc_dashboard"))
    assert resp_a.status_code == 200
    content_a = resp_a.content.decode()

    assert in_process_inspection_a in resp_a.context["recent_inspections"]
    assert in_process_inspection_b not in resp_a.context["recent_inspections"]
    assert fai_a in resp_a.context["recent_fais"]
    assert fai_b not in resp_a.context["recent_fais"]
    assert parameter_log_b not in resp_a.context["recent_excursions"]
    assert layered_audit_a in resp_a.context["recent_lpas"]
    assert layered_audit_b not in resp_a.context["recent_lpas"]

    assert in_process_inspection_b.title not in content_a
    assert fai_b.title not in content_a
    assert parameter_log_b.parameter_name not in content_a
    assert layered_audit_b.title not in content_a

    # Symmetric: Tenant B
    client.force_login(admin_b)
    resp_b = client.get(reverse("quality:spc_dashboard"))
    assert resp_b.status_code == 200
    content_b = resp_b.content.decode()

    assert in_process_inspection_b in resp_b.context["recent_inspections"]
    assert in_process_inspection_a not in resp_b.context["recent_inspections"]
    assert fai_b in resp_b.context["recent_fais"]
    assert fai_a not in resp_b.context["recent_fais"]
    assert parameter_log_a not in resp_b.context["recent_excursions"]
    assert layered_audit_b in resp_b.context["recent_lpas"]
    assert layered_audit_a not in resp_b.context["recent_lpas"]

    assert in_process_inspection_a.title not in content_b
    assert fai_a.title not in content_b
    assert parameter_log_a.parameter_name not in content_b
    assert layered_audit_a.title not in content_b


# =============================================================================
# 2. Form Foreign Key Boundary Enforcement (reject_foreign)
# =============================================================================

def test_inprocessquality_security_reject_foreign_in_process_inspection_form(
    tenant_a, tenant_b, admin_user, admin_b, doc_b, ncr_b
):
    """Verify InProcessInspectionForm rejects foreign work_order, work_center, doc, ncr, operator, inspector."""
    item_b = Item.objects.create(tenant=tenant_b, sku="SKU-SEC-B01", name="Foreign Item B")
    wo_b = WorkOrder.objects.create(tenant=tenant_b, item=item_b, quantity_planned=Decimal("100"))
    wc_b = WorkCenter.objects.create(tenant=tenant_b, code="WC-SEC-B01", name="Foreign Center B")

    # 1. Direct reject_foreign invocation on cleaned_data
    form_direct = InProcessInspectionForm(data={}, tenant=tenant_a)
    form_direct.is_valid()
    form_direct.cleaned_data = {
        "work_order": wo_b,
        "work_center": wc_b,
        "controlled_document": doc_b,
        "non_conformance": ncr_b,
        "operator": admin_b,
        "inspector": admin_b,
    }
    reject_foreign(form_direct, form_direct.cleaned_data, [
        "work_order", "work_center", "controlled_document",
        "non_conformance", "operator", "inspector"
    ])
    for field in ["work_order", "work_center", "controlled_document", "non_conformance", "operator", "inspector"]:
        assert field in form_direct.errors
        assert "That record belongs to another workspace." in form_direct.errors[field][0]

    # 2. Form submission with foreign inspector pk is rejected by field validation
    bad_data = _inprocessquality_inspection_post_data(inspector=admin_b.pk)
    form_bound = InProcessInspectionForm(data=bad_data, tenant=tenant_a)
    assert not form_bound.is_valid()
    assert "inspector" in form_bound.errors


def test_inprocessquality_security_reject_foreign_first_article_inspection_form(
    tenant_a, tenant_b, admin_user, admin_b, ncr_b
):
    """Verify FirstArticleInspectionForm rejects foreign work_order, work_center, non_conformance, inspector."""
    item_b = Item.objects.create(tenant=tenant_b, sku="SKU-SEC-B02", name="Foreign FAI Item B")
    wo_b = WorkOrder.objects.create(tenant=tenant_b, item=item_b, quantity_planned=Decimal("50"))
    wc_b = WorkCenter.objects.create(tenant=tenant_b, code="WC-SEC-B02", name="Foreign FAI Center B")

    # Direct reject_foreign invocation on cleaned_data
    form_direct = FirstArticleInspectionForm(data={}, tenant=tenant_a)
    form_direct.is_valid()
    form_direct.cleaned_data = {
        "work_order": wo_b,
        "work_center": wc_b,
        "non_conformance": ncr_b,
        "inspector": admin_b,
    }
    reject_foreign(form_direct, form_direct.cleaned_data, [
        "work_order", "work_center", "non_conformance", "inspector"
    ])
    for field in ["work_order", "work_center", "non_conformance", "inspector"]:
        assert field in form_direct.errors
        assert "That record belongs to another workspace." in form_direct.errors[field][0]

    # Form submission with foreign NCR pk is rejected
    bad_data = _inprocessquality_fai_post_data(ncr=ncr_b.pk)
    form_bound = FirstArticleInspectionForm(data=bad_data, tenant=tenant_a)
    assert not form_bound.is_valid()
    assert "non_conformance" in form_bound.errors


def test_inprocessquality_security_reject_foreign_process_parameter_log_form(
    tenant_a, tenant_b, admin_user, ncr_b, process_deviation_b
):
    """Verify ProcessParameterLogForm rejects foreign work_order, work_center, non_conformance, process_deviation."""
    item_b = Item.objects.create(tenant=tenant_b, sku="SKU-SEC-B03", name="Foreign Log Item B")
    wo_b = WorkOrder.objects.create(tenant=tenant_b, item=item_b, quantity_planned=Decimal("200"))
    wc_b = WorkCenter.objects.create(tenant=tenant_b, code="WC-SEC-B03", name="Foreign Log Center B")

    # Direct reject_foreign invocation on cleaned_data
    form_direct = ProcessParameterLogForm(data={}, tenant=tenant_a)
    form_direct.is_valid()
    form_direct.cleaned_data = {
        "work_order": wo_b,
        "work_center": wc_b,
        "non_conformance": ncr_b,
        "process_deviation": process_deviation_b,
    }
    reject_foreign(form_direct, form_direct.cleaned_data, [
        "work_order", "work_center", "non_conformance", "process_deviation"
    ])
    for field in ["work_order", "work_center", "non_conformance", "process_deviation"]:
        assert field in form_direct.errors
        assert "That record belongs to another workspace." in form_direct.errors[field][0]

    # Form submission with foreign deviation pk is rejected
    bad_data = _inprocessquality_param_post_data(dev=process_deviation_b.pk)
    form_bound = ProcessParameterLogForm(data=bad_data, tenant=tenant_a)
    assert not form_bound.is_valid()
    assert "process_deviation" in form_bound.errors


def test_inprocessquality_security_reject_foreign_layered_process_audit_form(
    tenant_a, tenant_b, admin_user, admin_b, doc_b, ncr_b, quality_department_b
):
    """Verify LayeredProcessAuditForm rejects foreign work_center, org_unit, controlled_document, non_conformance, auditor."""
    wc_b = WorkCenter.objects.create(tenant=tenant_b, code="WC-SEC-B04", name="Foreign Audit Center B")

    # Direct reject_foreign invocation on cleaned_data
    form_direct = LayeredProcessAuditForm(data={}, tenant=tenant_a)
    form_direct.is_valid()
    form_direct.cleaned_data = {
        "work_center": wc_b,
        "org_unit": quality_department_b,
        "controlled_document": doc_b,
        "non_conformance": ncr_b,
        "auditor": admin_b,
    }
    reject_foreign(form_direct, form_direct.cleaned_data, [
        "work_center", "org_unit", "controlled_document", "non_conformance", "auditor"
    ])
    for field in ["work_center", "org_unit", "controlled_document", "non_conformance", "auditor"]:
        assert field in form_direct.errors
        assert "That record belongs to another workspace." in form_direct.errors[field][0]

    # Form submission with foreign org_unit pk is rejected
    bad_data = _inprocessquality_audit_post_data(org_unit=quality_department_b.pk)
    form_bound = LayeredProcessAuditForm(data=bad_data, tenant=tenant_a)
    assert not form_bound.is_valid()
    assert "org_unit" in form_bound.errors


# =============================================================================
# 3. Authentication & Authorization Gating
# =============================================================================

def test_inprocessquality_security_unauthenticated_requests_redirect_all_26_endpoints(
    client, in_process_inspection_a, fai_a, parameter_log_a, layered_audit_a
):
    """Verify all 26 view endpoints redirect unauthenticated requests to login (HTTP 302)."""
    endpoints = [
        # InProcessInspection (6)
        reverse("quality:in_process_inspection_list"),
        reverse("quality:in_process_inspection_create"),
        reverse("quality:in_process_inspection_detail", kwargs={"pk": in_process_inspection_a.pk}),
        reverse("quality:in_process_inspection_edit", kwargs={"pk": in_process_inspection_a.pk}),
        reverse("quality:in_process_inspection_delete", kwargs={"pk": in_process_inspection_a.pk}),
        reverse("quality:in_process_inspection_export_csv"),
        # FirstArticleInspection (7)
        reverse("quality:first_article_inspection_list"),
        reverse("quality:first_article_inspection_create"),
        reverse("quality:first_article_inspection_detail", kwargs={"pk": fai_a.pk}),
        reverse("quality:first_article_inspection_edit", kwargs={"pk": fai_a.pk}),
        reverse("quality:first_article_inspection_release", kwargs={"pk": fai_a.pk}),
        reverse("quality:first_article_inspection_delete", kwargs={"pk": fai_a.pk}),
        reverse("quality:first_article_inspection_export_csv"),
        # ProcessParameterLog (6)
        reverse("quality:process_parameter_log_list"),
        reverse("quality:process_parameter_log_create"),
        reverse("quality:process_parameter_log_detail", kwargs={"pk": parameter_log_a.pk}),
        reverse("quality:process_parameter_log_edit", kwargs={"pk": parameter_log_a.pk}),
        reverse("quality:process_parameter_log_delete", kwargs={"pk": parameter_log_a.pk}),
        reverse("quality:process_parameter_log_export_csv"),
        # LayeredProcessAudit (6)
        reverse("quality:layered_process_audit_list"),
        reverse("quality:layered_process_audit_create"),
        reverse("quality:layered_process_audit_detail", kwargs={"pk": layered_audit_a.pk}),
        reverse("quality:layered_process_audit_edit", kwargs={"pk": layered_audit_a.pk}),
        reverse("quality:layered_process_audit_delete", kwargs={"pk": layered_audit_a.pk}),
        reverse("quality:layered_process_audit_export_csv"),
        # SPC Dashboard (1)
        reverse("quality:spc_dashboard"),
    ]

    assert len(endpoints) == 26, f"Expected 26 endpoints, got {len(endpoints)}"

    for url in endpoints:
        resp = client.get(url)
        assert resp.status_code == 302, f"Endpoint {url} did not redirect unauthenticated client"
        assert "/accounts/login/" in resp.url or "login" in resp.url


def test_inprocessquality_security_unauthenticated_mutations_redirect(
    client, in_process_inspection_a, fai_a, parameter_log_a, layered_audit_a
):
    """Verify unauthenticated mutating POST requests redirect to login."""
    post_targets = [
        reverse("quality:in_process_inspection_create"),
        reverse("quality:in_process_inspection_edit", kwargs={"pk": in_process_inspection_a.pk}),
        reverse("quality:in_process_inspection_delete", kwargs={"pk": in_process_inspection_a.pk}),
        reverse("quality:first_article_inspection_create"),
        reverse("quality:first_article_inspection_edit", kwargs={"pk": fai_a.pk}),
        reverse("quality:first_article_inspection_release", kwargs={"pk": fai_a.pk}),
        reverse("quality:first_article_inspection_delete", kwargs={"pk": fai_a.pk}),
        reverse("quality:process_parameter_log_create"),
        reverse("quality:process_parameter_log_edit", kwargs={"pk": parameter_log_a.pk}),
        reverse("quality:process_parameter_log_delete", kwargs={"pk": parameter_log_a.pk}),
        reverse("quality:layered_process_audit_create"),
        reverse("quality:layered_process_audit_edit", kwargs={"pk": layered_audit_a.pk}),
        reverse("quality:layered_process_audit_delete", kwargs={"pk": layered_audit_a.pk}),
    ]
    for url in post_targets:
        resp = client.post(url, {})
        assert resp.status_code == 302, f"POST to {url} did not redirect unauthenticated client"
        assert "/accounts/login/" in resp.url or "login" in resp.url


def test_inprocessquality_security_non_admin_forbidden_on_delete_endpoints(
    member_client, in_process_inspection_a, fai_a, parameter_log_a, layered_audit_a
):
    """Verify non-admin tenant members are rejected with 403 Forbidden on all 4 delete endpoints."""
    # InProcessInspection delete
    resp_insp = member_client.post(
        reverse("quality:in_process_inspection_delete", kwargs={"pk": in_process_inspection_a.pk})
    )
    assert resp_insp.status_code == 403
    assert InProcessInspection.objects.filter(pk=in_process_inspection_a.pk).exists()

    # FirstArticleInspection delete
    resp_fai = member_client.post(
        reverse("quality:first_article_inspection_delete", kwargs={"pk": fai_a.pk})
    )
    assert resp_fai.status_code == 403
    assert FirstArticleInspection.objects.filter(pk=fai_a.pk).exists()

    # ProcessParameterLog delete
    resp_log = member_client.post(
        reverse("quality:process_parameter_log_delete", kwargs={"pk": parameter_log_a.pk})
    )
    assert resp_log.status_code == 403
    assert ProcessParameterLog.objects.filter(pk=parameter_log_a.pk).exists()

    # LayeredProcessAudit delete
    resp_lpa = member_client.post(
        reverse("quality:layered_process_audit_delete", kwargs={"pk": layered_audit_a.pk})
    )
    assert resp_lpa.status_code == 403
    assert LayeredProcessAudit.objects.filter(pk=layered_audit_a.pk).exists()


def test_inprocessquality_security_non_admin_forbidden_on_fai_release_endpoint(member_client, fai_a):
    """Verify non-admin tenant member cannot release First Article Inspection (HTTP 403 Forbidden)."""
    resp = member_client.post(
        reverse("quality:first_article_inspection_release", kwargs={"pk": fai_a.pk})
    )
    assert resp.status_code == 403

    fai_a.refresh_from_db()
    assert fai_a.status != "approved_run_released"
    assert fai_a.release_verdict != "released"
    assert fai_a.approved_by is None


def test_inprocessquality_security_require_post_methods_reject_get(
    client, admin_user, in_process_inspection_a, fai_a, parameter_log_a, layered_audit_a
):
    """Verify @require_POST endpoints (all 4 delete views + FAI release) reject GET with 405 Method Not Allowed."""
    client.force_login(admin_user)
    post_only_urls = [
        reverse("quality:in_process_inspection_delete", kwargs={"pk": in_process_inspection_a.pk}),
        reverse("quality:first_article_inspection_delete", kwargs={"pk": fai_a.pk}),
        reverse("quality:first_article_inspection_release", kwargs={"pk": fai_a.pk}),
        reverse("quality:process_parameter_log_delete", kwargs={"pk": parameter_log_a.pk}),
        reverse("quality:layered_process_audit_delete", kwargs={"pk": layered_audit_a.pk}),
    ]
    for url in post_only_urls:
        resp = client.get(url)
        assert resp.status_code == 405, f"GET on {url} should return 405 Method Not Allowed"


# =============================================================================
# 4. Mass-Assignment & Tampering Protections
# =============================================================================

def test_inprocessquality_security_mass_assignment_in_process_inspection(tenant_a, tenant_b, admin_user):
    """Verify tenant, number, created_at, updated_at cannot be spoofed via InProcessInspectionForm."""
    form = InProcessInspectionForm(tenant=tenant_a)
    forbidden_fields = ["tenant", "number", "created_at", "updated_at"]
    for field in forbidden_fields:
        assert field not in form.fields, f"Field '{field}' should not be in InProcessInspectionForm.fields"

    data = _inprocessquality_inspection_post_data(
        inspector=admin_user,
        tenant=tenant_b.pk,
        number="MALICIOUS-INSP-999",
        created_at="2020-01-01 00:00:00",
        updated_at="2020-01-01 00:00:00",
    )
    bound_form = InProcessInspectionForm(data=data, tenant=tenant_a)
    assert bound_form.is_valid(), bound_form.errors
    instance = bound_form.save(commit=False)
    assert instance.tenant == tenant_a
    assert instance.number != "MALICIOUS-INSP-999"


def test_inprocessquality_security_mass_assignment_first_article_inspection(tenant_a, tenant_b, admin_user, admin_b):
    """Verify tenant, number, approved_by, approved_at cannot be spoofed via FirstArticleInspectionForm."""
    form = FirstArticleInspectionForm(tenant=tenant_a)
    forbidden_fields = ["tenant", "number", "approved_by", "approved_at", "created_at", "updated_at"]
    for field in forbidden_fields:
        assert field not in form.fields, f"Field '{field}' should not be in FirstArticleInspectionForm.fields"

    data = _inprocessquality_fai_post_data(
        inspector=admin_user,
        tenant=tenant_b.pk,
        number="MALICIOUS-FAI-999",
        approved_by=admin_b.pk,
        approved_at="2020-01-01 00:00:00",
    )
    bound_form = FirstArticleInspectionForm(data=data, tenant=tenant_a)
    assert bound_form.is_valid(), bound_form.errors
    instance = bound_form.save(commit=False)
    assert instance.tenant == tenant_a
    assert instance.number != "MALICIOUS-FAI-999"
    assert instance.approved_by is None
    assert instance.approved_at is None


def test_inprocessquality_security_mass_assignment_process_parameter_log(
    client, admin_user, admin_b, tenant_a, tenant_b
):
    """Verify logged_by and tenant cannot be spoofed and are securely assigned server-side."""
    form = ProcessParameterLogForm(tenant=tenant_a)
    forbidden_fields = ["tenant", "number", "logged_by", "created_at", "updated_at"]
    for field in forbidden_fields:
        assert field not in form.fields, f"Field '{field}' should not be in ProcessParameterLogForm.fields"

    # Test via create view POST
    client.force_login(admin_user)
    post_data = _inprocessquality_param_post_data(
        parameter_name="Temperature Sensor Verification",
        tenant=tenant_b.pk,
        number="MALICIOUS-LOG-999",
        logged_by=admin_b.pk,
    )
    resp = client.post(reverse("quality:process_parameter_log_create"), post_data)
    assert resp.status_code == 302

    created_log = ProcessParameterLog.objects.get(
        tenant=tenant_a, parameter_name="Temperature Sensor Verification"
    )
    assert created_log.tenant == tenant_a
    assert created_log.number.startswith("QPAR-")
    assert created_log.number != "MALICIOUS-LOG-999"
    assert created_log.logged_by == admin_user
    assert created_log.logged_by != admin_b


def test_inprocessquality_security_mass_assignment_layered_process_audit(tenant_a, tenant_b, admin_user):
    """Verify compliance_percentage cannot be spoofed and is computed automatically on model save."""
    form = LayeredProcessAuditForm(tenant=tenant_a)
    forbidden_fields = ["tenant", "number", "compliance_percentage", "created_at", "updated_at"]
    for field in forbidden_fields:
        assert field not in form.fields, f"Field '{field}' should not be in LayeredProcessAuditForm.fields"

    data = _inprocessquality_audit_post_data(
        auditor=admin_user,
        total_questions_audited=10,
        questions_conforming=10,
        questions_non_conforming=0,
        compliance_percentage="0.00",  # Attacker attempts to forge 0% compliance
    )
    bound_form = LayeredProcessAuditForm(data=data, tenant=tenant_a)
    assert bound_form.is_valid(), bound_form.errors
    instance = bound_form.save(commit=False)
    instance.tenant = tenant_a
    instance.save()

    assert instance.compliance_percentage == Decimal("100.00")


# =============================================================================
# 5. CSV Injection Formula Neutralization
# =============================================================================

def test_inprocessquality_security_csv_export_neutralizes_formula_inspection(client, admin_user, tenant_a):
    """Verify InProcessInspection CSV export neutralizes formula prefixes and sets nosniff."""
    client.force_login(admin_user)
    InProcessInspection.objects.create(
        tenant=tenant_a,
        title="=cmd|' /C calc'!A0",
        inspection_type="dimensional_gauging",
        stage_gate="+Op 020 Turning",
        status="completed",
        disposition="pass",
        production_order_number="-PO-CSV-01",
        work_center_code="@WC-01",
        item_code="\t=TAB-ITEM",
        item_name="\r=RETURN-ITEM",
        lot_number="LOT-CSV-01",
        batch_quantity=100,
        sample_size_inspected=5,
        quantity_passed=5,
        quantity_rejected=0,
    )

    resp = client.get(reverse("quality:in_process_inspection_export_csv"))
    assert resp.status_code == 200
    assert resp["X-Content-Type-Options"] == "nosniff"

    content = resp.content.decode("utf-8")
    reader = csv.reader(io.StringIO(content))
    rows = list(reader)

    found_formula = False
    for row in rows:
        for cell in row:
            if cell.startswith("'=") or cell.startswith("'+") or cell.startswith("'-") or cell.startswith("'@") or cell.startswith("'\t") or cell.startswith("'\r"):
                found_formula = True
    assert found_formula, f"Formula prefix neutralization failed in InProcessInspection CSV:\n{content}"


def test_inprocessquality_security_csv_export_neutralizes_formula_fai(client, admin_user, tenant_a):
    """Verify FirstArticleInspection CSV export neutralizes formula prefixes and sets nosniff."""
    client.force_login(admin_user)
    FirstArticleInspection.objects.create(
        tenant=tenant_a,
        title="=SUM(1+1)",
        fai_type="full_fai",
        setup_reason="new_product_intro",
        status="in_inspection",
        production_order_number="+PO-FAI-CSV",
        work_center_code="@WC-02",
        item_code="-AERO-CSV",
        item_name="\t=TAB-NAME",
        drawing_number="\r=REV-CSV",
        total_characteristics_inspected=10,
        characteristics_conforming=10,
        characteristics_out_of_spec=0,
    )

    resp = client.get(reverse("quality:first_article_inspection_export_csv"))
    assert resp.status_code == 200
    assert resp["X-Content-Type-Options"] == "nosniff"

    content = resp.content.decode("utf-8")
    reader = csv.reader(io.StringIO(content))
    rows = list(reader)

    found_formula = False
    for row in rows:
        for cell in row:
            if cell.startswith("'=") or cell.startswith("'+") or cell.startswith("'-") or cell.startswith("'@") or cell.startswith("'\t") or cell.startswith("'\r"):
                found_formula = True
    assert found_formula, f"Formula prefix neutralization failed in FAI CSV:\n{content}"


def test_inprocessquality_security_csv_export_neutralizes_formula_parameter_log(client, admin_user, tenant_a):
    """Verify ProcessParameterLog CSV export neutralizes formula prefixes and sets nosniff."""
    client.force_login(admin_user)
    ProcessParameterLog.objects.create(
        tenant=tenant_a,
        parameter_name="=cmd|' /C notepad'!A0",
        parameter_category="temperature",
        unit_of_measure="+°C",
        work_center_code="@WC-SMT",
        production_order_number="-PO-CSV-02",
        item_code="\t=PCB-CSV",
        lot_number="\r=LOT-CSV",
        target_nominal_value=Decimal("200.0000"),
        upper_spec_limit=Decimal("210.0000"),
        lower_spec_limit=Decimal("190.0000"),
        recorded_value=Decimal("201.0000"),
        excursion_status="normal",
    )

    resp = client.get(reverse("quality:process_parameter_log_export_csv"))
    assert resp.status_code == 200
    assert resp["X-Content-Type-Options"] == "nosniff"

    content = resp.content.decode("utf-8")
    reader = csv.reader(io.StringIO(content))
    rows = list(reader)

    found_formula = False
    for row in rows:
        for cell in row:
            if cell.startswith("'=") or cell.startswith("'+") or cell.startswith("'-") or cell.startswith("'@") or cell.startswith("'\t") or cell.startswith("'\r"):
                found_formula = True
    assert found_formula, f"Formula prefix neutralization failed in Parameter Log CSV:\n{content}"


def test_inprocessquality_security_csv_export_neutralizes_formula_layered_audit(client, admin_user, tenant_a):
    """Verify LayeredProcessAudit CSV export neutralizes formula prefixes and sets nosniff."""
    client.force_login(admin_user)
    LayeredProcessAudit.objects.create(
        tenant=tenant_a,
        title="=2+5",
        audit_layer="tier_1_operator_lead",
        focus_area="standard_work_wi",
        status="completed",
        work_center_code="+WC-LPA-01",
        shift="@Shift 1",
        scheduled_date=timezone.now().date(),
        total_questions_audited=5,
        questions_conforming=5,
        questions_non_conforming=0,
        compliance_percentage=Decimal("100.00"),
    )

    resp = client.get(reverse("quality:layered_process_audit_export_csv"))
    assert resp.status_code == 200
    assert resp["X-Content-Type-Options"] == "nosniff"

    content = resp.content.decode("utf-8")
    reader = csv.reader(io.StringIO(content))
    rows = list(reader)

    found_formula = False
    for row in rows:
        for cell in row:
            if cell.startswith("'=") or cell.startswith("'+") or cell.startswith("'-") or cell.startswith("'@"):
                found_formula = True
    assert found_formula, f"Formula prefix neutralization failed in LPA CSV:\n{content}"


def test_inprocessquality_security_csv_safe_utility_exhaustive():
    """Verify _csv_safe directly neutralizes all formula trigger prefixes and whitespace variants."""
    # Prefix characters that require quoting
    assert _csv_safe("=SUM(A1:A10)") == "'=SUM(A1:A10)"
    assert _csv_safe("+12345") == "'+12345"
    assert _csv_safe("-999") == "'-999"
    assert _csv_safe("@admin") == "'@admin"

    # Leading whitespace before formula triggers
    assert _csv_safe("   =CMD") == "'   =CMD"
    assert _csv_safe("  +EVAL") == "'  +EVAL"
    assert _csv_safe("  -EXEC") == "'  -EXEC"
    assert _csv_safe("  @IMPORT") == "'  @IMPORT"
    assert _csv_safe("\t=FORMULA") == "'\t=FORMULA"
    assert _csv_safe("\r=FORMULA") == "'\r=FORMULA"

    # Safe inputs
    assert _csv_safe(None) == ""
    assert _csv_safe("Safe Plain Text") == "Safe Plain Text"
    assert _csv_safe("Part #12345") == "Part #12345"
    assert _csv_safe(100) == "100"
    assert _csv_safe(Decimal("25.5000")) == "25.5000"


# =============================================================================
# 6. XSS Protection
# =============================================================================

def test_inprocessquality_security_xss_escaping_in_process_inspection(client, admin_user, tenant_a):
    """Verify malicious script tags in InProcessInspection fields are HTML-escaped."""
    client.force_login(admin_user)
    xss_payload = "<script>alert('xss-insp')</script>"
    inspection = InProcessInspection.objects.create(
        tenant=tenant_a,
        title=f"Inspection {xss_payload}",
        inspection_type="dimensional_gauging",
        stage_gate=f"Gate {xss_payload}",
        status="completed",
        disposition="reject_scrap",
        production_order_number="PO-XSS-01",
        work_center_code="WC-XSS",
        item_code="XSS-ITEM",
        item_name=f"Part {xss_payload}",
        lot_number="LOT-XSS",
        batch_quantity=100,
        sample_size_inspected=5,
        quantity_passed=4,
        quantity_rejected=1,
        defect_description=f"Defect {xss_payload}",
    )

    # Detail page
    resp_detail = client.get(
        reverse("quality:in_process_inspection_detail", kwargs={"pk": inspection.pk})
    )
    assert resp_detail.status_code == 200
    content_detail = resp_detail.content.decode()
    assert xss_payload not in content_detail
    assert "&lt;script&gt;alert(&#x27;xss-insp&#x27;)&lt;/script&gt;" in content_detail or "&lt;script&gt;" in content_detail

    # List page
    resp_list = client.get(reverse("quality:in_process_inspection_list"))
    assert resp_list.status_code == 200
    content_list = resp_list.content.decode()
    assert xss_payload not in content_list
    assert "&lt;script&gt;" in content_list


def test_inprocessquality_security_xss_escaping_first_article_inspection(client, admin_user, tenant_a):
    """Verify malicious script tags in FirstArticleInspection fields are HTML-escaped."""
    client.force_login(admin_user)
    xss_payload = "<script>alert('xss-fai')</script>"
    fai = FirstArticleInspection.objects.create(
        tenant=tenant_a,
        title=f"FAI {xss_payload}",
        fai_type="full_fai",
        setup_reason="new_product_intro",
        status="in_inspection",
        production_order_number="PO-XSS-FAI",
        work_center_code="WC-XSS-02",
        item_code="XSS-FAI-ITEM",
        item_name=f"Strut {xss_payload}",
        drawing_number=f"DWG-{xss_payload}",
        total_characteristics_inspected=10,
        characteristics_conforming=10,
        characteristics_out_of_spec=0,
        notes=f"Audit notes {xss_payload}",
    )

    # Detail page
    resp_detail = client.get(
        reverse("quality:first_article_inspection_detail", kwargs={"pk": fai.pk})
    )
    assert resp_detail.status_code == 200
    content_detail = resp_detail.content.decode()
    assert xss_payload not in content_detail
    assert "&lt;script&gt;" in content_detail

    # List page
    resp_list = client.get(reverse("quality:first_article_inspection_list"))
    assert resp_list.status_code == 200
    content_list = resp_list.content.decode()
    assert xss_payload not in content_list
    assert "&lt;script&gt;" in content_list


def test_inprocessquality_security_xss_escaping_process_parameter_log(client, admin_user, tenant_a):
    """Verify malicious script tags in ProcessParameterLog fields are HTML-escaped."""
    client.force_login(admin_user)
    xss_payload = "<script>alert('xss-param')</script>"
    log = ProcessParameterLog.objects.create(
        tenant=tenant_a,
        parameter_name=f"Temperature {xss_payload}",
        parameter_category="temperature",
        unit_of_measure="°C",
        work_center_code="WC-SMT-XSS",
        production_order_number="PO-XSS-03",
        item_code="XSS-PARAM-ITEM",
        lot_number="LOT-XSS-03",
        target_nominal_value=Decimal("200.0000"),
        upper_spec_limit=Decimal("210.0000"),
        lower_spec_limit=Decimal("190.0000"),
        recorded_value=Decimal("205.0000"),
        excursion_status="normal",
        containment_notes=f"Containment {xss_payload}",
    )

    # Detail page
    resp_detail = client.get(
        reverse("quality:process_parameter_log_detail", kwargs={"pk": log.pk})
    )
    assert resp_detail.status_code == 200
    content_detail = resp_detail.content.decode()
    assert xss_payload not in content_detail
    assert "&lt;script&gt;" in content_detail

    # List page
    resp_list = client.get(reverse("quality:process_parameter_log_list"))
    assert resp_list.status_code == 200
    content_list = resp_list.content.decode()
    assert xss_payload not in content_list
    assert "&lt;script&gt;" in content_list


def test_inprocessquality_security_xss_escaping_layered_process_audit(client, admin_user, tenant_a):
    """Verify malicious script tags in LayeredProcessAudit fields are HTML-escaped."""
    client.force_login(admin_user)
    xss_payload = "<script>alert('xss-lpa')</script>"
    lpa = LayeredProcessAudit.objects.create(
        tenant=tenant_a,
        title=f"LPA Audit {xss_payload}",
        audit_layer="tier_1_operator_lead",
        focus_area="standard_work_wi",
        status="completed",
        work_center_code="WC-LPA-XSS",
        shift="Shift 1",
        scheduled_date=timezone.now().date(),
        total_questions_audited=10,
        questions_conforming=9,
        questions_non_conforming=1,
        findings_summary=f"Audit findings {xss_payload}",
        notes=f"Auditor remarks {xss_payload}",
        compliance_percentage=Decimal("90.00"),
    )

    # Detail page
    resp_detail = client.get(
        reverse("quality:layered_process_audit_detail", kwargs={"pk": lpa.pk})
    )
    assert resp_detail.status_code == 200
    content_detail = resp_detail.content.decode()
    assert xss_payload not in content_detail
    assert "&lt;script&gt;" in content_detail

    # List page
    resp_list = client.get(reverse("quality:layered_process_audit_list"))
    assert resp_list.status_code == 200
    content_list = resp_list.content.decode()
    assert xss_payload not in content_list
    assert "&lt;script&gt;" in content_list
