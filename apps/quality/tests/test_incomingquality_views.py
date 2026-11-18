"""
View unit tests for Sub-module 12.7: Incoming Quality Control (IQC).

Covers all views, routes, query filters, search, pagination, context contracts,
form submissions (valid & invalid), status progressions, custom business actions,
CSV exports, admin deletion gates, and multi-tenant isolation:
1. IncomingInspectionPlan (list, detail, create, edit, delete, export)
2. IncomingInspectionLot (list, detail, create, edit, delete, record_sample, make_decision, export)
3. CertificateOfAnalysis (list, detail, create, edit, delete, verify, export)
4. QualityReturnAuthorization (list, detail, create, edit, delete, advance, export)
5. IQC SPC Dashboard (iqc_spc_dashboard)
6. Cross-tenant isolation & unauthenticated redirection
"""

import csv
import io
import json
from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from apps.core.models import AuditLog, Party
from apps.quality.models import (
    CertificateOfAnalysis,
    IncomingInspectionLot,
    IncomingInspectionPlan,
    QualityReturnAuthorization,
)

User = get_user_model()
pytestmark = pytest.mark.django_db


# =============================================================================
# Helper Utilities (Prefix: _incomingquality_views_*)
# =============================================================================

def _incomingquality_views_pk(val):
    """Return pk if val is a model instance, or val itself if scalar / None."""
    if hasattr(val, "pk"):
        return val.pk
    return val


def _incomingquality_views_date(days_offset=0):
    """Return an ISO formatted date string relative to today."""
    return (timezone.now().date() + timedelta(days=days_offset)).isoformat()


def _incomingquality_views_plan_data(supplier=None, doc=None, team=None, **extra):
    """Build valid baseline POST dictionary for IncomingInspectionPlanForm."""
    data = {
        "title": "Titanium Rods Receiving Plan",
        "item_code": "TI-ROD-01",
        "item_name": "Medical Grade Titanium Rod 10mm",
        "revision": "A",
        "supplier": _incomingquality_views_pk(supplier) if supplier else "",
        "sampling_standard": "ansi_asq_z14",
        "inspection_level": "level_2",
        "inspection_severity": "normal",
        "inspection_frequency": "every_lot",
        "skip_lot_interval": 5,
        "aql_critical": "0.00",
        "aql_major": "1.00",
        "aql_minor": "4.00",
        "requires_coa": True,
        "requires_coc": False,
        "status": "active",
        "sop_document": _incomingquality_views_pk(doc) if doc else "",
        "assigned_team": _incomingquality_views_pk(team) if team else "",
        "characteristics_json": json.dumps([
            {"name": "Diameter", "type": "variable", "target": 10.0, "lsl": 9.95, "usl": 10.05, "unit": "mm"}
        ]),
        "notes": "Incoming inspection requirements per ISO 13485.",
    }
    data.update(extra)
    return data


def _incomingquality_views_lot_data(plan, supplier, inspector=None, decided_by=None, **extra):
    """Build valid baseline POST dictionary for IncomingInspectionLotForm."""
    data = {
        "inspection_plan": _incomingquality_views_pk(plan),
        "item_code": "TI-ROD-01",
        "item_name": "Medical Grade Titanium Rod 10mm",
        "supplier": _incomingquality_views_pk(supplier),
        "purchase_order": "",
        "goods_receipt_note": "",
        "lot_number": "LOT-2026-IQC-0881",
        "heat_or_batch": "HEAT-9941",
        "receipt_date": _incomingquality_views_date(-2),
        "inspection_date": _incomingquality_views_date(0),
        "lot_quantity": "500.000",
        "sample_size": 32,
        "inspected_quantity": 32,
        "accepted_quantity": "500.000",
        "rejected_quantity": "0.000",
        "quarantine_quantity": "0.000",
        "critical_defects": 0,
        "major_defects": 0,
        "minor_defects": 0,
        "stage": "completed",
        "usage_decision": "accepted",
        "usage_decision_notes": "Conforms fully to critical dimensions.",
        "decided_by": _incomingquality_views_pk(decided_by) if decided_by else "",
        "inspector": _incomingquality_views_pk(inspector) if inspector else "",
        "linked_ncr": "",
        "linked_deviation": "",
        "linked_containment": "",
        "linked_scar": "",
        "measurements_json": json.dumps([
            {"sample_no": 1, "characteristic": "Diameter", "value": 10.001, "is_pass": True},
            {"sample_no": 2, "characteristic": "Diameter", "value": 9.998, "is_pass": True},
        ]),
        "notes": "ANSI Z1.4 Level II normal inspection executed.",
    }
    data.update(extra)
    return data


def _incomingquality_views_coa_data(supplier, plan=None, lot=None, doc=None, **extra):
    """Build valid baseline POST dictionary for CertificateOfAnalysisForm."""
    data = {
        "certificate_number": "COA-VND-2026-9921",
        "supplier": _incomingquality_views_pk(supplier),
        "item_code": "TI-ROD-01",
        "item_name": "Medical Grade Titanium Rod 10mm",
        "lot_number": "LOT-2026-IQC-0881",
        "inspection_lot": _incomingquality_views_pk(lot) if lot else "",
        "inspection_plan": _incomingquality_views_pk(plan) if plan else "",
        "manufacturer_name": "Precision Alloys Corp",
        "date_of_manufacture": _incomingquality_views_date(-30),
        "expiry_or_retest_date": _incomingquality_views_date(365),
        "lab_accreditation": "ISO/IEC 17025 Accredited Lab #441",
        "status": "received",
        "supporting_document": _incomingquality_views_pk(doc) if doc else "",
        "parameters_json": json.dumps([
            {"parameter": "Tensile Strength", "lsl": 860.0, "usl": 950.0, "actual_value": 895.0, "unit": "MPa"}
        ]),
        "notes": "Verified against mill test report.",
    }
    data.update(extra)
    return data


def _incomingquality_views_rma_data(lot, supplier, coordinator=None, **extra):
    """Build valid baseline POST dictionary for QualityReturnAuthorizationForm."""
    data = {
        "inspection_lot": _incomingquality_views_pk(lot),
        "supplier": _incomingquality_views_pk(supplier),
        "vendor_rma_number": "VRMA-2026-1188",
        "return_reason": "dimensional_oos",
        "disposition_type": "return_for_credit",
        "return_quantity": "50.000",
        "unit_of_measure": "EA",
        "estimated_credit_value": "1250.00",
        "status": "rma_requested",
        "carrier": "FedEx Freight",
        "tracking_number": "7849 2011 8841",
        "bill_of_lading": "BOL-99410",
        "shipped_date": _incomingquality_views_date(2),
        "vendor_receipt_date": _incomingquality_views_date(6),
        "debit_memo_number": "DM-2026-041",
        "settled_amount": "1250.00",
        "settlement_date": _incomingquality_views_date(10),
        "assigned_coordinator": _incomingquality_views_pk(coordinator) if coordinator else "",
        "linked_ncr": "",
        "linked_scar": "",
        "notes": "Parts rejected during incoming dimensional verification.",
    }
    data.update(extra)
    return data


# =============================================================================
# 1. IncomingInspectionPlan Views
# =============================================================================

def test_incomingquality_views_plan_list_get_and_context(client, admin_user, incoming_plan_a):
    """Verify inspection plan list GET returns 200 with required context keys and record content."""
    client.force_login(admin_user)
    url = reverse("quality:incoming_inspection_plan_list")
    resp = client.get(url)
    assert resp.status_code == 200

    context_keys = [
        "plans",
        "page_obj",
        "paginator",
        "is_paginated",
        "total_count",
        "status_choices",
        "frequency_choices",
        "suppliers",
        "current_status",
        "current_frequency",
        "current_supplier",
        "search_query",
    ]
    for key in context_keys:
        assert key in resp.context, f"Key '{key}' missing from plan list context"

    assert incoming_plan_a in resp.context["plans"]
    assert incoming_plan_a.number in resp.content.decode()


def test_incomingquality_views_plan_list_search_and_filters(client, admin_user, incoming_plan_a, supplier_party_a):
    """Verify inspection plan list filters correctly by search query, status, frequency, and supplier."""
    client.force_login(admin_user)
    url = reverse("quality:incoming_inspection_plan_list")

    # Match query & filters
    resp_match = client.get(url, {
        "q": incoming_plan_a.title,
        "status": incoming_plan_a.status,
        "frequency": incoming_plan_a.inspection_frequency,
        "supplier": str(supplier_party_a.pk),
    })
    assert resp_match.status_code == 200
    assert incoming_plan_a in resp_match.context["plans"]

    # Filter mismatch
    resp_nomatch = client.get(url, {"status": "inactive"})
    assert resp_nomatch.status_code == 200
    assert incoming_plan_a not in resp_nomatch.context["plans"]


def test_incomingquality_views_plan_list_pagination_and_junk(client, admin_user, incoming_plan_a):
    """Verify plan list handles junk parameters and pagination gracefully without crashing."""
    client.force_login(admin_user)
    url = reverse("quality:incoming_inspection_plan_list")

    resp_junk = client.get(url, {
        "status": "bogus_status",
        "frequency": "invalid_freq",
        "supplier": "not_an_int",
        "page": "invalid_page_number",
    })
    assert resp_junk.status_code == 200
    assert resp_junk.context["page_obj"].number == 1


def test_incomingquality_views_plan_detail_get_and_context(client, admin_user, incoming_plan_a):
    """Verify plan detail GET returns 200 with plan context and template content."""
    client.force_login(admin_user)
    url = reverse("quality:incoming_inspection_plan_detail", kwargs={"pk": incoming_plan_a.pk})
    resp = client.get(url)
    assert resp.status_code == 200

    assert resp.context["plan"] == incoming_plan_a
    assert resp.context["obj"] == incoming_plan_a
    assert "status_css" in resp.context
    assert "freq_css" in resp.context
    assert incoming_plan_a.number in resp.content.decode()
    assert incoming_plan_a.title in resp.content.decode()


def test_incomingquality_views_plan_create_get(client, admin_user):
    """Verify plan create GET renders the form and title context."""
    client.force_login(admin_user)
    url = reverse("quality:incoming_inspection_plan_create")
    resp = client.get(url)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert "title" in resp.context


def test_incomingquality_views_plan_create_post_valid(client, admin_user, tenant_a, supplier_party_a, doc_a, quality_department):
    """Verify valid POST creates IncomingInspectionPlan, writes audit log, and redirects to detail."""
    client.force_login(admin_user)
    url = reverse("quality:incoming_inspection_plan_create")
    post_data = _incomingquality_views_plan_data(
        supplier=supplier_party_a,
        doc=doc_a,
        team=quality_department,
        title="New Precision Sensor Plan",
        item_code="SNS-100",
    )

    resp = client.post(url, post_data)
    assert resp.status_code == 302

    created_plan = IncomingInspectionPlan.objects.get(title="New Precision Sensor Plan", tenant=tenant_a)
    assert resp.url == reverse("quality:incoming_inspection_plan_detail", kwargs={"pk": created_plan.pk})
    assert created_plan.item_code == "SNS-100"
    assert created_plan.supplier == supplier_party_a
    assert len(created_plan.characteristics_matrix) == 1

    # Verify audit log
    assert AuditLog.objects.filter(
        tenant=tenant_a,
        action="create",
        target__contains=created_plan.number,
    ).exists()


def test_incomingquality_views_plan_create_post_invalid(client, admin_user):
    """Verify invalid POST returns 200 with form validation errors."""
    client.force_login(admin_user)
    url = reverse("quality:incoming_inspection_plan_create")
    # Empty title, missing required fields
    resp = client.post(url, {"title": "", "item_code": ""})
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["form"].errors


def test_incomingquality_views_plan_edit_get(client, admin_user, incoming_plan_a):
    """Verify plan edit GET returns 200 with populated form."""
    client.force_login(admin_user)
    url = reverse("quality:incoming_inspection_plan_edit", kwargs={"pk": incoming_plan_a.pk})
    resp = client.get(url)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["plan"] == incoming_plan_a


def test_incomingquality_views_plan_edit_post_valid(client, admin_user, incoming_plan_a, supplier_party_a, doc_a, quality_department):
    """Verify valid POST updates the plan and redirects to detail."""
    client.force_login(admin_user)
    url = reverse("quality:incoming_inspection_plan_edit", kwargs={"pk": incoming_plan_a.pk})
    post_data = _incomingquality_views_plan_data(
        supplier=supplier_party_a,
        doc=doc_a,
        team=quality_department,
        title="Updated Titanium Rods IQC Plan",
        notes="Updated tolerance specs.",
    )

    resp = client.post(url, post_data)
    assert resp.status_code == 302
    assert resp.url == reverse("quality:incoming_inspection_plan_detail", kwargs={"pk": incoming_plan_a.pk})

    incoming_plan_a.refresh_from_db()
    assert incoming_plan_a.title == "Updated Titanium Rods IQC Plan"
    assert incoming_plan_a.notes == "Updated tolerance specs."


def test_incomingquality_views_plan_edit_post_invalid(client, admin_user, incoming_plan_a):
    """Verify invalid POST on edit renders 200 with errors and does not update."""
    client.force_login(admin_user)
    url = reverse("quality:incoming_inspection_plan_edit", kwargs={"pk": incoming_plan_a.pk})
    resp = client.post(url, {"title": ""})
    assert resp.status_code == 200
    assert "form" in resp.context
    assert "title" in resp.context["form"].errors


def test_incomingquality_views_plan_delete_method_not_allowed(client, admin_user, incoming_plan_a):
    """Verify GET on delete endpoint returns 405 Method Not Allowed."""
    client.force_login(admin_user)
    url = reverse("quality:incoming_inspection_plan_delete", kwargs={"pk": incoming_plan_a.pk})
    resp = client.get(url)
    assert resp.status_code == 405


def test_incomingquality_views_plan_delete_non_admin_forbidden(client, member_user, incoming_plan_a):
    """Verify non-admin user is rejected with 403 on delete."""
    client.force_login(member_user)
    url = reverse("quality:incoming_inspection_plan_delete", kwargs={"pk": incoming_plan_a.pk})
    resp = client.post(url)
    assert resp.status_code == 403


def test_incomingquality_views_plan_delete_admin_success(client, admin_user, tenant_a, supplier_party_a):
    """Verify tenant admin can delete plan via POST and is redirected to list."""
    plan_to_delete = IncomingInspectionPlan.objects.create(
        tenant=tenant_a,
        title="Plan to Delete",
        item_code="DEL-001",
        item_name="Item for Deletion",
        supplier=supplier_party_a,
    )
    url = reverse("quality:incoming_inspection_plan_delete", kwargs={"pk": plan_to_delete.pk})

    client.force_login(admin_user)
    resp = client.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("quality:incoming_inspection_plan_list")
    assert not IncomingInspectionPlan.objects.filter(pk=plan_to_delete.pk).exists()


def test_incomingquality_views_plan_export_csv(client, admin_user, incoming_plan_a):
    """Verify plan export returns CSV with correct headers and nosniff protection."""
    client.force_login(admin_user)
    url = reverse("quality:incoming_inspection_plan_export")
    resp = client.get(url)
    assert resp.status_code == 200
    assert "text/csv" in resp["Content-Type"]
    assert "incoming_inspection_plans.csv" in resp["Content-Disposition"]
    assert resp["X-Content-Type-Options"] == "nosniff"

    content = resp.content.decode("utf-8")
    reader = csv.reader(io.StringIO(content))
    headers = next(reader)
    assert "Plan Number" in headers
    assert "Title" in headers
    assert "Item Code" in headers
    rows = list(reader)
    assert any(incoming_plan_a.number in row[0] for row in rows)


# =============================================================================
# 2. IncomingInspectionLot Views
# =============================================================================

def test_incomingquality_views_lot_list_get_and_context(client, admin_user, incoming_lot_a):
    """Verify inspection lot list GET returns 200 with required context keys and lot content."""
    client.force_login(admin_user)
    url = reverse("quality:incoming_inspection_lot_list")
    resp = client.get(url)
    assert resp.status_code == 200

    context_keys = [
        "lots",
        "page_obj",
        "paginator",
        "is_paginated",
        "total_count",
        "stage_choices",
        "usage_decision_choices",
        "suppliers",
        "current_stage",
        "current_decision",
        "current_supplier",
        "search_query",
    ]
    for key in context_keys:
        assert key in resp.context, f"Key '{key}' missing from lot list context"

    assert incoming_lot_a in resp.context["lots"]
    assert incoming_lot_a.number in resp.content.decode()


def test_incomingquality_views_lot_list_search_and_filters(client, admin_user, incoming_lot_a, supplier_party_a):
    """Verify inspection lot list filters correctly by search query, stage, decision, and supplier."""
    client.force_login(admin_user)
    url = reverse("quality:incoming_inspection_lot_list")

    resp_match = client.get(url, {
        "q": incoming_lot_a.lot_number,
        "stage": incoming_lot_a.stage,
        "decision": incoming_lot_a.usage_decision,
        "supplier": str(supplier_party_a.pk),
    })
    assert resp_match.status_code == 200
    assert incoming_lot_a in resp_match.context["lots"]

    resp_nomatch = client.get(url, {"stage": "pending_receipt"})
    assert resp_nomatch.status_code == 200
    assert incoming_lot_a not in resp_nomatch.context["lots"]


def test_incomingquality_views_lot_list_pagination_and_junk(client, admin_user, incoming_lot_a):
    """Verify lot list handles junk parameters and invalid page gracefully."""
    client.force_login(admin_user)
    url = reverse("quality:incoming_inspection_lot_list")

    resp_junk = client.get(url, {
        "stage": "bogus_stage",
        "decision": "invalid_decision",
        "supplier": "not_an_int",
        "page": "junk_page",
    })
    assert resp_junk.status_code == 200
    assert resp_junk.context["page_obj"].number == 1


def test_incomingquality_views_lot_detail_get_and_context(client, admin_user, incoming_lot_a):
    """Verify lot detail GET returns 200 with lot context and badge styles."""
    client.force_login(admin_user)
    url = reverse("quality:incoming_inspection_lot_detail", kwargs={"pk": incoming_lot_a.pk})
    resp = client.get(url)
    assert resp.status_code == 200

    assert resp.context["lot"] == incoming_lot_a
    assert resp.context["obj"] == incoming_lot_a
    assert "stage_css" in resp.context
    assert "decision_css" in resp.context
    assert "usage_decision_choices" in resp.context
    assert incoming_lot_a.number in resp.content.decode()
    assert incoming_lot_a.lot_number in resp.content.decode()


def test_incomingquality_views_lot_create_get(client, admin_user):
    """Verify lot create GET renders the form and title context."""
    client.force_login(admin_user)
    url = reverse("quality:incoming_inspection_lot_create")
    resp = client.get(url)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert "title" in resp.context


def test_incomingquality_views_lot_create_post_valid(client, admin_user, tenant_a, incoming_plan_a, supplier_party_a):
    """Verify valid POST creates IncomingInspectionLot, writes audit log, and redirects to detail."""
    client.force_login(admin_user)
    url = reverse("quality:incoming_inspection_lot_create")
    post_data = _incomingquality_views_lot_data(
        plan=incoming_plan_a,
        supplier=supplier_party_a,
        inspector=admin_user,
        decided_by=admin_user,
        lot_number="LOT-POST-2026-X1",
    )

    resp = client.post(url, post_data)
    assert resp.status_code == 302

    created_lot = IncomingInspectionLot.objects.get(lot_number="LOT-POST-2026-X1", tenant=tenant_a)
    assert resp.url == reverse("quality:incoming_inspection_lot_detail", kwargs={"pk": created_lot.pk})
    assert created_lot.supplier == supplier_party_a
    assert created_lot.inspection_plan == incoming_plan_a

    # Verify audit log
    assert AuditLog.objects.filter(
        tenant=tenant_a,
        action="create",
        target__contains=created_lot.number,
    ).exists()


def test_incomingquality_views_lot_create_post_invalid(client, admin_user):
    """Verify invalid POST returns 200 with form errors."""
    client.force_login(admin_user)
    url = reverse("quality:incoming_inspection_lot_create")
    resp = client.post(url, {"lot_number": "", "item_code": ""})
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["form"].errors


def test_incomingquality_views_lot_edit_get(client, admin_user, incoming_lot_a):
    """Verify lot edit GET returns 200 with populated form."""
    client.force_login(admin_user)
    url = reverse("quality:incoming_inspection_lot_edit", kwargs={"pk": incoming_lot_a.pk})
    resp = client.get(url)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["lot"] == incoming_lot_a


def test_incomingquality_views_lot_edit_post_valid(client, admin_user, incoming_lot_a, incoming_plan_a, supplier_party_a):
    """Verify valid POST updates the lot and redirects to detail."""
    client.force_login(admin_user)
    url = reverse("quality:incoming_inspection_lot_edit", kwargs={"pk": incoming_lot_a.pk})
    post_data = _incomingquality_views_lot_data(
        plan=incoming_plan_a,
        supplier=supplier_party_a,
        inspector=admin_user,
        decided_by=admin_user,
        lot_number=incoming_lot_a.lot_number,
        heat_or_batch="HEAT-UPDATED-007",
    )

    resp = client.post(url, post_data)
    assert resp.status_code == 302
    assert resp.url == reverse("quality:incoming_inspection_lot_detail", kwargs={"pk": incoming_lot_a.pk})

    incoming_lot_a.refresh_from_db()
    assert incoming_lot_a.heat_or_batch == "HEAT-UPDATED-007"


def test_incomingquality_views_lot_edit_post_invalid(client, admin_user, incoming_lot_a):
    """Verify invalid POST on lot edit renders 200 with errors."""
    client.force_login(admin_user)
    url = reverse("quality:incoming_inspection_lot_edit", kwargs={"pk": incoming_lot_a.pk})
    resp = client.post(url, {"lot_number": ""})
    assert resp.status_code == 200
    assert "form" in resp.context
    assert "lot_number" in resp.context["form"].errors


def test_incomingquality_views_lot_delete_method_not_allowed(client, admin_user, incoming_lot_a):
    """Verify GET on lot delete returns 405 Method Not Allowed."""
    client.force_login(admin_user)
    url = reverse("quality:incoming_inspection_lot_delete", kwargs={"pk": incoming_lot_a.pk})
    resp = client.get(url)
    assert resp.status_code == 405


def test_incomingquality_views_lot_delete_non_admin_forbidden(client, member_user, incoming_lot_a):
    """Verify non-admin user is rejected with 403 on lot delete."""
    client.force_login(member_user)
    url = reverse("quality:incoming_inspection_lot_delete", kwargs={"pk": incoming_lot_a.pk})
    resp = client.post(url)
    assert resp.status_code == 403


def test_incomingquality_views_lot_delete_admin_success(client, admin_user, tenant_a, supplier_party_a, incoming_plan_a):
    """Verify tenant admin can delete lot via POST and is redirected to list."""
    lot_to_delete = IncomingInspectionLot.objects.create(
        tenant=tenant_a,
        inspection_plan=incoming_plan_a,
        supplier=supplier_party_a,
        item_code="DEL-LOT",
        item_name="Del Lot Item",
        lot_number="LOT-DEL-001",
        lot_quantity=Decimal("100.000"),
    )
    url = reverse("quality:incoming_inspection_lot_delete", kwargs={"pk": lot_to_delete.pk})

    client.force_login(admin_user)
    resp = client.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("quality:incoming_inspection_lot_list")
    assert not IncomingInspectionLot.objects.filter(pk=lot_to_delete.pk).exists()


def test_incomingquality_views_lot_record_sample_post_valid(client, admin_user, tenant_a, supplier_party_a, incoming_plan_a):
    """Verify record_sample appends measurement, updates inspected quantity, calls recalculate_spc, and redirects."""
    pending_lot = IncomingInspectionLot.objects.create(
        tenant=tenant_a,
        inspection_plan=incoming_plan_a,
        supplier=supplier_party_a,
        item_code="TI-ROD-01",
        item_name="Titanium Rod",
        lot_number="LOT-SAMPLE-TEST-01",
        lot_quantity=Decimal("100.000"),
        sample_size=5,
        stage="pending_receipt",
        usage_decision="pending",
    )
    url = reverse("quality:incoming_inspection_lot_record_sample", kwargs={"pk": pending_lot.pk})

    client.force_login(admin_user)
    resp = client.post(url, {
        "reading_value": "10.002",
        "characteristic": "Diameter",
        "is_pass": "true",
    })
    assert resp.status_code == 302
    assert resp.url == reverse("quality:incoming_inspection_lot_detail", kwargs={"pk": pending_lot.pk})

    pending_lot.refresh_from_db()
    assert pending_lot.inspected_quantity == 1
    assert pending_lot.stage == "in_inspection"
    assert pending_lot.inspector == admin_user
    assert pending_lot.inspection_date is not None
    assert len(pending_lot.measurements_data) == 1
    assert pending_lot.measurements_data[0]["value"] == 10.002
    assert pending_lot.measurements_data[0]["characteristic"] == "Diameter"


def test_incomingquality_views_lot_record_sample_completed_guard(client, admin_user, incoming_lot_a):
    """Verify recording samples on a completed lot is rejected with an error message."""
    assert incoming_lot_a.stage == "completed"
    url = reverse("quality:incoming_inspection_lot_record_sample", kwargs={"pk": incoming_lot_a.pk})

    initial_count = len(incoming_lot_a.measurements_data or [])
    client.force_login(admin_user)
    resp = client.post(url, {
        "reading_value": "10.005",
        "characteristic": "Diameter",
    })
    assert resp.status_code == 302
    assert resp.url == reverse("quality:incoming_inspection_lot_detail", kwargs={"pk": incoming_lot_a.pk})

    incoming_lot_a.refresh_from_db()
    assert len(incoming_lot_a.measurements_data or []) == initial_count


def test_incomingquality_views_lot_record_sample_invalid_value(client, admin_user, tenant_a, supplier_party_a, incoming_plan_a):
    """Verify recording non-numeric sample measurement is caught and sets error message."""
    pending_lot = IncomingInspectionLot.objects.create(
        tenant=tenant_a,
        inspection_plan=incoming_plan_a,
        supplier=supplier_party_a,
        item_code="TI-ROD-01",
        item_name="Titanium Rod",
        lot_number="LOT-SAMPLE-ERR-01",
        lot_quantity=Decimal("100.000"),
        stage="in_inspection",
        usage_decision="pending",
    )
    url = reverse("quality:incoming_inspection_lot_record_sample", kwargs={"pk": pending_lot.pk})

    client.force_login(admin_user)
    resp = client.post(url, {"reading_value": "invalid_number_abc"})
    assert resp.status_code == 302

    pending_lot.refresh_from_db()
    assert pending_lot.inspected_quantity == 0


def test_incomingquality_views_lot_make_decision_post_valid_accepted(client, admin_user, tenant_a, supplier_party_a, incoming_plan_a):
    """Verify applying 'accepted' decision completes lot, sets accepted_quantity, decided_by, and timestamp."""
    lot = IncomingInspectionLot.objects.create(
        tenant=tenant_a,
        inspection_plan=incoming_plan_a,
        supplier=supplier_party_a,
        item_code="TI-ROD-01",
        item_name="Titanium Rod",
        lot_number="LOT-DEC-ACC-01",
        lot_quantity=Decimal("300.000"),
        sample_size=20,
        inspected_quantity=20,
        stage="in_inspection",
        usage_decision="pending",
    )
    url = reverse("quality:incoming_inspection_lot_make_decision", kwargs={"pk": lot.pk})

    client.force_login(admin_user)
    resp = client.post(url, {
        "usage_decision": "accepted",
        "decision_notes": "All dimensions and surface checks fully within specification.",
    })
    assert resp.status_code == 302
    assert resp.url == reverse("quality:incoming_inspection_lot_detail", kwargs={"pk": lot.pk})

    lot.refresh_from_db()
    assert lot.usage_decision == "accepted"
    assert lot.stage == "completed"
    assert lot.accepted_quantity == Decimal("300.000")
    assert lot.decided_by == admin_user
    assert lot.decided_at is not None
    assert "fully within specification" in lot.usage_decision_notes


def test_incomingquality_views_lot_make_decision_post_valid_quarantined(client, admin_user, tenant_a, supplier_party_a, incoming_plan_a):
    """Verify applying 'quarantined' decision moves lot to 'under_mrb' and sets quarantine_quantity."""
    lot = IncomingInspectionLot.objects.create(
        tenant=tenant_a,
        inspection_plan=incoming_plan_a,
        supplier=supplier_party_a,
        item_code="TI-ROD-01",
        item_name="Titanium Rod",
        lot_number="LOT-DEC-QUR-01",
        lot_quantity=Decimal("250.000"),
        stage="in_inspection",
        usage_decision="pending",
    )
    url = reverse("quality:incoming_inspection_lot_make_decision", kwargs={"pk": lot.pk})

    client.force_login(admin_user)
    resp = client.post(url, {
        "usage_decision": "quarantined",
        "decision_notes": "Out of roundness detected; routed to MRB.",
    })
    assert resp.status_code == 302

    lot.refresh_from_db()
    assert lot.usage_decision == "quarantined"
    assert lot.stage == "under_mrb"
    assert lot.quarantine_quantity == Decimal("250.000")


def test_incomingquality_views_lot_make_decision_post_valid_rejected(client, admin_user, tenant_a, supplier_party_a, incoming_plan_a):
    """Verify applying 'rejected' decision sets stage to completed and rejected_quantity."""
    lot = IncomingInspectionLot.objects.create(
        tenant=tenant_a,
        inspection_plan=incoming_plan_a,
        supplier=supplier_party_a,
        item_code="TI-ROD-01",
        item_name="Titanium Rod",
        lot_number="LOT-DEC-REJ-01",
        lot_quantity=Decimal("150.000"),
        stage="in_inspection",
        usage_decision="pending",
    )
    url = reverse("quality:incoming_inspection_lot_make_decision", kwargs={"pk": lot.pk})

    client.force_login(admin_user)
    resp = client.post(url, {
        "usage_decision": "rejected",
        "decision_notes": "Critical crack defects on 4 samples.",
    })
    assert resp.status_code == 302

    lot.refresh_from_db()
    assert lot.usage_decision == "rejected"
    assert lot.stage == "completed"
    assert lot.rejected_quantity == Decimal("150.000")


def test_incomingquality_views_lot_make_decision_finalized_guard(client, admin_user, incoming_lot_a):
    """Verify attempting to make decision on already finalized lot is blocked with an error message."""
    assert incoming_lot_a.usage_decision != "pending"
    url = reverse("quality:incoming_inspection_lot_make_decision", kwargs={"pk": incoming_lot_a.pk})

    client.force_login(admin_user)
    resp = client.post(url, {"usage_decision": "rejected"})
    assert resp.status_code == 302
    assert resp.url == reverse("quality:incoming_inspection_lot_detail", kwargs={"pk": incoming_lot_a.pk})

    incoming_lot_a.refresh_from_db()
    assert incoming_lot_a.usage_decision == "accepted"


def test_incomingquality_views_lot_make_decision_invalid_choice(client, admin_user, tenant_a, supplier_party_a, incoming_plan_a):
    """Verify invalid decision choice is blocked."""
    lot = IncomingInspectionLot.objects.create(
        tenant=tenant_a,
        inspection_plan=incoming_plan_a,
        supplier=supplier_party_a,
        item_code="TI-ROD-01",
        item_name="Titanium Rod",
        lot_number="LOT-DEC-INV-01",
        lot_quantity=Decimal("100.000"),
        stage="in_inspection",
        usage_decision="pending",
    )
    url = reverse("quality:incoming_inspection_lot_make_decision", kwargs={"pk": lot.pk})

    client.force_login(admin_user)
    resp = client.post(url, {"usage_decision": "bogus_decision_choice"})
    assert resp.status_code == 302

    lot.refresh_from_db()
    assert lot.usage_decision == "pending"


def test_incomingquality_views_lot_export_csv(client, admin_user, incoming_lot_a):
    """Verify lot export returns CSV with correct columns and nosniff protection."""
    client.force_login(admin_user)
    url = reverse("quality:incoming_inspection_lot_export")
    resp = client.get(url)
    assert resp.status_code == 200
    assert "text/csv" in resp["Content-Type"]
    assert "incoming_inspection_lots.csv" in resp["Content-Disposition"]
    assert resp["X-Content-Type-Options"] == "nosniff"

    content = resp.content.decode("utf-8")
    reader = csv.reader(io.StringIO(content))
    headers = next(reader)
    assert "Lot Number" in headers
    assert "Vendor Lot #" in headers
    assert "Usage Decision" in headers
    assert "Cpk" in headers
    rows = list(reader)
    assert any(incoming_lot_a.number in row[0] for row in rows)


# =============================================================================
# 3. CertificateOfAnalysis Views
# =============================================================================

def test_incomingquality_views_coa_list_get_and_context(client, admin_user, coa_a):
    """Verify Certificate of Analysis list GET returns 200 with required context keys."""
    client.force_login(admin_user)
    url = reverse("quality:certificate_of_analysis_list")
    resp = client.get(url)
    assert resp.status_code == 200

    context_keys = [
        "coas",
        "page_obj",
        "paginator",
        "is_paginated",
        "total_count",
        "status_choices",
        "suppliers",
        "current_status",
        "current_within_spec",
        "current_supplier",
        "search_query",
    ]
    for key in context_keys:
        assert key in resp.context, f"Key '{key}' missing from CoA list context"

    assert coa_a in resp.context["coas"]
    assert coa_a.number in resp.content.decode()


def test_incomingquality_views_coa_list_search_and_filters(client, admin_user, coa_a, supplier_party_a):
    """Verify CoA list filters correctly by query, status, within_spec, and supplier."""
    client.force_login(admin_user)
    url = reverse("quality:certificate_of_analysis_list")

    resp_match = client.get(url, {
        "q": coa_a.certificate_number,
        "status": coa_a.status,
        "within_spec": "yes",
        "supplier": str(supplier_party_a.pk),
    })
    assert resp_match.status_code == 200
    assert coa_a in resp_match.context["coas"]

    resp_nomatch = client.get(url, {"within_spec": "no"})
    assert resp_nomatch.status_code == 200
    assert coa_a not in resp_nomatch.context["coas"]


def test_incomingquality_views_coa_list_pagination_and_junk(client, admin_user, coa_a):
    """Verify CoA list handles junk parameters gracefully."""
    client.force_login(admin_user)
    url = reverse("quality:certificate_of_analysis_list")

    resp_junk = client.get(url, {
        "status": "bogus_status",
        "within_spec": "maybe",
        "supplier": "invalid_supplier",
        "page": "invalid_page",
    })
    assert resp_junk.status_code == 200
    assert resp_junk.context["page_obj"].number == 1


def test_incomingquality_views_coa_detail_get_and_context(client, admin_user, coa_a):
    """Verify CoA detail GET returns 200 with object and status style."""
    client.force_login(admin_user)
    url = reverse("quality:certificate_of_analysis_detail", kwargs={"pk": coa_a.pk})
    resp = client.get(url)
    assert resp.status_code == 200

    assert resp.context["coa"] == coa_a
    assert resp.context["obj"] == coa_a
    assert "status_css" in resp.context
    assert coa_a.number in resp.content.decode()
    assert coa_a.certificate_number in resp.content.decode()


def test_incomingquality_views_coa_create_get(client, admin_user):
    """Verify CoA create GET renders form and title."""
    client.force_login(admin_user)
    url = reverse("quality:certificate_of_analysis_create")
    resp = client.get(url)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert "title" in resp.context


def test_incomingquality_views_coa_create_post_valid(client, admin_user, tenant_a, supplier_party_a, incoming_plan_a, incoming_lot_a, doc_a):
    """Verify valid POST creates CertificateOfAnalysis, writes audit log, and redirects to detail."""
    client.force_login(admin_user)
    url = reverse("quality:certificate_of_analysis_create")
    post_data = _incomingquality_views_coa_data(
        supplier=supplier_party_a,
        plan=incoming_plan_a,
        lot=incoming_lot_a,
        doc=doc_a,
        certificate_number="COA-NEW-POST-991",
    )

    resp = client.post(url, post_data)
    assert resp.status_code == 302

    created_coa = CertificateOfAnalysis.objects.get(certificate_number="COA-NEW-POST-991", tenant=tenant_a)
    assert resp.url == reverse("quality:certificate_of_analysis_detail", kwargs={"pk": created_coa.pk})
    assert created_coa.supplier == supplier_party_a
    assert len(created_coa.parameters_payload) == 1

    # Verify audit log
    assert AuditLog.objects.filter(
        tenant=tenant_a,
        action="create",
        target__contains=created_coa.number,
    ).exists()


def test_incomingquality_views_coa_create_post_invalid(client, admin_user):
    """Verify invalid POST returns 200 with form validation errors."""
    client.force_login(admin_user)
    url = reverse("quality:certificate_of_analysis_create")
    resp = client.post(url, {"certificate_number": "", "item_code": ""})
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["form"].errors


def test_incomingquality_views_coa_edit_get(client, admin_user, coa_a):
    """Verify CoA edit GET returns 200 with populated form."""
    client.force_login(admin_user)
    url = reverse("quality:certificate_of_analysis_edit", kwargs={"pk": coa_a.pk})
    resp = client.get(url)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["coa"] == coa_a


def test_incomingquality_views_coa_edit_post_valid(client, admin_user, coa_a, supplier_party_a, incoming_plan_a, incoming_lot_a, doc_a):
    """Verify valid POST updates CertificateOfAnalysis and redirects to detail."""
    client.force_login(admin_user)
    url = reverse("quality:certificate_of_analysis_edit", kwargs={"pk": coa_a.pk})
    post_data = _incomingquality_views_coa_data(
        supplier=supplier_party_a,
        plan=incoming_plan_a,
        lot=incoming_lot_a,
        doc=doc_a,
        certificate_number=coa_a.certificate_number,
        lab_accreditation="Updated ISO 17025 Certified Lab",
    )

    resp = client.post(url, post_data)
    assert resp.status_code == 302
    assert resp.url == reverse("quality:certificate_of_analysis_detail", kwargs={"pk": coa_a.pk})

    coa_a.refresh_from_db()
    assert coa_a.lab_accreditation == "Updated ISO 17025 Certified Lab"


def test_incomingquality_views_coa_edit_post_invalid(client, admin_user, coa_a):
    """Verify invalid POST on edit renders 200 with errors."""
    client.force_login(admin_user)
    url = reverse("quality:certificate_of_analysis_edit", kwargs={"pk": coa_a.pk})
    resp = client.post(url, {"certificate_number": ""})
    assert resp.status_code == 200
    assert "form" in resp.context
    assert "certificate_number" in resp.context["form"].errors


def test_incomingquality_views_coa_delete_method_not_allowed(client, admin_user, coa_a):
    """Verify GET on CoA delete returns 405 Method Not Allowed."""
    client.force_login(admin_user)
    url = reverse("quality:certificate_of_analysis_delete", kwargs={"pk": coa_a.pk})
    resp = client.get(url)
    assert resp.status_code == 405


def test_incomingquality_views_coa_delete_non_admin_forbidden(client, member_user, coa_a):
    """Verify non-admin is rejected with 403 on CoA delete."""
    client.force_login(member_user)
    url = reverse("quality:certificate_of_analysis_delete", kwargs={"pk": coa_a.pk})
    resp = client.post(url)
    assert resp.status_code == 403


def test_incomingquality_views_coa_delete_admin_success(client, admin_user, tenant_a, supplier_party_a):
    """Verify tenant admin can delete CoA via POST and is redirected to list."""
    coa_to_delete = CertificateOfAnalysis.objects.create(
        tenant=tenant_a,
        supplier=supplier_party_a,
        certificate_number="COA-DEL-001",
        item_code="TI-ROD-01",
        item_name="Titanium Rod",
        lot_number="LOT-DEL",
    )
    url = reverse("quality:certificate_of_analysis_delete", kwargs={"pk": coa_to_delete.pk})

    client.force_login(admin_user)
    resp = client.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("quality:certificate_of_analysis_list")
    assert not CertificateOfAnalysis.objects.filter(pk=coa_to_delete.pk).exists()


def test_incomingquality_views_coa_verify_compliant(client, admin_user, tenant_a, supplier_party_a):
    """Verify verifying compliant CoA marks status verified_compliant and sets verified_by."""
    coa = CertificateOfAnalysis.objects.create(
        tenant=tenant_a,
        supplier=supplier_party_a,
        certificate_number="COA-VER-COMPLIANT",
        item_code="TI-ROD-01",
        item_name="Titanium Rod",
        lot_number="LOT-COMPL-01",
        status="received",
        parameters_payload=[
            {"parameter": "Tensile Strength", "lsl": 860, "usl": 950, "actual_value": 890, "unit": "MPa"},
            {"parameter": "Hardness", "lsl": 30, "usl": 38, "actual_value": 34, "unit": "HRC"},
        ],
    )
    url = reverse("quality:certificate_of_analysis_verify", kwargs={"pk": coa.pk})

    client.force_login(admin_user)
    resp = client.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("quality:certificate_of_analysis_detail", kwargs={"pk": coa.pk})

    coa.refresh_from_db()
    assert coa.is_within_spec is True
    assert coa.variance_count == 0
    assert coa.status == "verified_compliant"
    assert coa.verified_by == admin_user
    assert coa.verified_at is not None


def test_incomingquality_views_coa_verify_exception(client, admin_user, tenant_a, supplier_party_a):
    """Verify verifying out-of-spec CoA marks status exception_detected and counts variances."""
    coa = CertificateOfAnalysis.objects.create(
        tenant=tenant_a,
        supplier=supplier_party_a,
        certificate_number="COA-VER-EXCEPTION",
        item_code="TI-ROD-01",
        item_name="Titanium Rod",
        lot_number="LOT-EXC-01",
        status="received",
        parameters_payload=[
            {"parameter": "Tensile Strength", "lsl": 860, "usl": 950, "actual_value": 800, "unit": "MPa"},
            {"parameter": "Hardness", "lsl": 30, "usl": 38, "actual_value": 45, "unit": "HRC"},
        ],
    )
    url = reverse("quality:certificate_of_analysis_verify", kwargs={"pk": coa.pk})

    client.force_login(admin_user)
    resp = client.post(url)
    assert resp.status_code == 302

    coa.refresh_from_db()
    assert coa.is_within_spec is False
    assert coa.variance_count == 2
    assert coa.status == "exception_detected"
    assert coa.verified_by == admin_user


def test_incomingquality_views_coa_export_csv(client, admin_user, coa_a):
    """Verify CoA export returns CSV with correct columns and nosniff protection."""
    client.force_login(admin_user)
    url = reverse("quality:certificate_of_analysis_export")
    resp = client.get(url)
    assert resp.status_code == 200
    assert "text/csv" in resp["Content-Type"]
    assert "certificates_of_analysis.csv" in resp["Content-Disposition"]
    assert resp["X-Content-Type-Options"] == "nosniff"

    content = resp.content.decode("utf-8")
    reader = csv.reader(io.StringIO(content))
    headers = next(reader)
    assert "Record Number" in headers
    assert "Supplier CoA #" in headers
    assert "Within Spec" in headers
    rows = list(reader)
    assert any(coa_a.number in row[0] for row in rows)


# =============================================================================
# 4. QualityReturnAuthorization Views
# =============================================================================

def test_incomingquality_views_rma_list_get_and_context(client, admin_user, rma_a):
    """Verify RMA list GET returns 200 with required context keys and record content."""
    client.force_login(admin_user)
    url = reverse("quality:quality_return_authorization_list")
    resp = client.get(url)
    assert resp.status_code == 200

    context_keys = [
        "rmas",
        "page_obj",
        "paginator",
        "is_paginated",
        "total_count",
        "status_choices",
        "disposition_choices",
        "suppliers",
        "current_status",
        "current_disposition",
        "current_supplier",
        "search_query",
    ]
    for key in context_keys:
        assert key in resp.context, f"Key '{key}' missing from RMA list context"

    assert rma_a in resp.context["rmas"]
    assert rma_a.number in resp.content.decode()


def test_incomingquality_views_rma_list_search_and_filters(client, admin_user, rma_a, supplier_party_a):
    """Verify RMA list filters correctly by query, status, disposition, and supplier."""
    client.force_login(admin_user)
    url = reverse("quality:quality_return_authorization_list")

    resp_match = client.get(url, {
        "q": rma_a.vendor_rma_number,
        "status": rma_a.status,
        "disposition": rma_a.disposition_type,
        "supplier": str(supplier_party_a.pk),
    })
    assert resp_match.status_code == 200
    assert rma_a in resp_match.context["rmas"]

    resp_nomatch = client.get(url, {"status": "settled_closed"})
    assert resp_nomatch.status_code == 200
    assert rma_a not in resp_nomatch.context["rmas"]


def test_incomingquality_views_rma_list_pagination_and_junk(client, admin_user, rma_a):
    """Verify RMA list handles junk parameters gracefully."""
    client.force_login(admin_user)
    url = reverse("quality:quality_return_authorization_list")

    resp_junk = client.get(url, {
        "status": "bogus_status",
        "disposition": "invalid_disp",
        "supplier": "not_an_int",
        "page": "invalid_page",
    })
    assert resp_junk.status_code == 200
    assert resp_junk.context["page_obj"].number == 1


def test_incomingquality_views_rma_detail_get_and_context(client, admin_user, rma_a):
    """Verify RMA detail GET returns 200 with object and style contexts."""
    client.force_login(admin_user)
    url = reverse("quality:quality_return_authorization_detail", kwargs={"pk": rma_a.pk})
    resp = client.get(url)
    assert resp.status_code == 200

    assert resp.context["rma"] == rma_a
    assert resp.context["obj"] == rma_a
    assert "status_css" in resp.context
    assert "disp_css" in resp.context
    assert rma_a.number in resp.content.decode()
    assert rma_a.vendor_rma_number in resp.content.decode()


def test_incomingquality_views_rma_create_get(client, admin_user):
    """Verify RMA create GET renders form and title."""
    client.force_login(admin_user)
    url = reverse("quality:quality_return_authorization_create")
    resp = client.get(url)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert "title" in resp.context


def test_incomingquality_views_rma_create_post_valid(client, admin_user, tenant_a, incoming_lot_a, supplier_party_a):
    """Verify valid POST creates QualityReturnAuthorization, writes audit log, and redirects to detail."""
    client.force_login(admin_user)
    url = reverse("quality:quality_return_authorization_create")
    post_data = _incomingquality_views_rma_data(
        lot=incoming_lot_a,
        supplier=supplier_party_a,
        coordinator=admin_user,
        vendor_rma_number="VRMA-POST-NEW-01",
    )

    resp = client.post(url, post_data)
    assert resp.status_code == 302

    created_rma = QualityReturnAuthorization.objects.get(vendor_rma_number="VRMA-POST-NEW-01", tenant=tenant_a)
    assert resp.url == reverse("quality:quality_return_authorization_detail", kwargs={"pk": created_rma.pk})
    assert created_rma.supplier == supplier_party_a
    assert created_rma.inspection_lot == incoming_lot_a
    assert created_rma.return_quantity == Decimal("50.000")

    # Verify audit log
    assert AuditLog.objects.filter(
        tenant=tenant_a,
        action="create",
        target__contains=created_rma.number,
    ).exists()


def test_incomingquality_views_rma_create_post_invalid(client, admin_user):
    """Verify invalid POST returns 200 with form validation errors."""
    client.force_login(admin_user)
    url = reverse("quality:quality_return_authorization_create")
    resp = client.post(url, {"vendor_rma_number": "", "return_reason": ""})
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["form"].errors


def test_incomingquality_views_rma_edit_get(client, admin_user, rma_a):
    """Verify RMA edit GET returns 200 with populated form."""
    client.force_login(admin_user)
    url = reverse("quality:quality_return_authorization_edit", kwargs={"pk": rma_a.pk})
    resp = client.get(url)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["rma"] == rma_a


def test_incomingquality_views_rma_edit_post_valid(client, admin_user, rma_a, incoming_lot_a, supplier_party_a):
    """Verify valid POST updates RMA and redirects to detail."""
    client.force_login(admin_user)
    url = reverse("quality:quality_return_authorization_edit", kwargs={"pk": rma_a.pk})
    post_data = _incomingquality_views_rma_data(
        lot=incoming_lot_a,
        supplier=supplier_party_a,
        coordinator=admin_user,
        vendor_rma_number=rma_a.vendor_rma_number,
        carrier="DHL Express Worldwide",
        tracking_number="DHL-9948-221",
    )

    resp = client.post(url, post_data)
    assert resp.status_code == 302
    assert resp.url == reverse("quality:quality_return_authorization_detail", kwargs={"pk": rma_a.pk})

    rma_a.refresh_from_db()
    assert rma_a.carrier == "DHL Express Worldwide"
    assert rma_a.tracking_number == "DHL-9948-221"


def test_incomingquality_views_rma_edit_post_invalid(client, admin_user, rma_a):
    """Verify invalid POST on edit renders 200 with errors."""
    client.force_login(admin_user)
    url = reverse("quality:quality_return_authorization_edit", kwargs={"pk": rma_a.pk})
    resp = client.post(url, {"return_reason": ""})
    assert resp.status_code == 200
    assert "form" in resp.context
    assert "return_reason" in resp.context["form"].errors


def test_incomingquality_views_rma_delete_method_not_allowed(client, admin_user, rma_a):
    """Verify GET on RMA delete returns 405 Method Not Allowed."""
    client.force_login(admin_user)
    url = reverse("quality:quality_return_authorization_delete", kwargs={"pk": rma_a.pk})
    resp = client.get(url)
    assert resp.status_code == 405


def test_incomingquality_views_rma_delete_non_admin_forbidden(client, member_user, rma_a):
    """Verify non-admin is rejected with 403 on RMA delete."""
    client.force_login(member_user)
    url = reverse("quality:quality_return_authorization_delete", kwargs={"pk": rma_a.pk})
    resp = client.post(url)
    assert resp.status_code == 403


def test_incomingquality_views_rma_delete_admin_success(client, admin_user, tenant_a, incoming_lot_a, supplier_party_a):
    """Verify tenant admin can delete RMA via POST and is redirected to list."""
    rma_to_delete = QualityReturnAuthorization.objects.create(
        tenant=tenant_a,
        inspection_lot=incoming_lot_a,
        supplier=supplier_party_a,
        vendor_rma_number="VRMA-DEL-001",
        return_reason="dimensional_oos",
        disposition_type="return_for_credit",
        return_quantity=Decimal("10.000"),
    )
    url = reverse("quality:quality_return_authorization_delete", kwargs={"pk": rma_to_delete.pk})

    client.force_login(admin_user)
    resp = client.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("quality:quality_return_authorization_list")
    assert not QualityReturnAuthorization.objects.filter(pk=rma_to_delete.pk).exists()


def test_incomingquality_views_rma_advance_valid_transition(client, admin_user, rma_a):
    """Verify valid state progression from rma_requested to rma_approved."""
    assert rma_a.status == "rma_requested"
    url = reverse("quality:quality_return_authorization_advance", kwargs={"pk": rma_a.pk})

    client.force_login(admin_user)
    resp = client.post(url, {"next_status": "rma_approved"})
    assert resp.status_code == 302
    assert resp.url == reverse("quality:quality_return_authorization_detail", kwargs={"pk": rma_a.pk})

    rma_a.refresh_from_db()
    assert rma_a.status == "rma_approved"


def test_incomingquality_views_rma_advance_shipped_sets_date(client, admin_user, tenant_a, incoming_lot_a, supplier_party_a):
    """Verify advancing to shipped_to_vendor automatically sets shipped_date."""
    rma = QualityReturnAuthorization.objects.create(
        tenant=tenant_a,
        inspection_lot=incoming_lot_a,
        supplier=supplier_party_a,
        vendor_rma_number="VRMA-SHIP-01",
        return_reason="dimensional_oos",
        disposition_type="return_for_credit",
        return_quantity=Decimal("20.000"),
        status="rma_approved",
    )
    url = reverse("quality:quality_return_authorization_advance", kwargs={"pk": rma.pk})

    client.force_login(admin_user)
    resp = client.post(url, {"next_status": "shipped_to_vendor"})
    assert resp.status_code == 302

    rma.refresh_from_db()
    assert rma.status == "shipped_to_vendor"
    assert rma.shipped_date == timezone.now().date()


def test_incomingquality_views_rma_advance_settled_sets_amount(client, admin_user, tenant_a, incoming_lot_a, supplier_party_a):
    """Verify advancing to settled_closed automatically sets settlement_date and copies estimated_credit_value."""
    rma = QualityReturnAuthorization.objects.create(
        tenant=tenant_a,
        inspection_lot=incoming_lot_a,
        supplier=supplier_party_a,
        vendor_rma_number="VRMA-SETTLE-01",
        return_reason="dimensional_oos",
        disposition_type="return_for_credit",
        return_quantity=Decimal("20.000"),
        estimated_credit_value=Decimal("850.00"),
        settled_amount=Decimal("0.00"),
        status="received_by_vendor",
    )
    url = reverse("quality:quality_return_authorization_advance", kwargs={"pk": rma.pk})

    client.force_login(admin_user)
    resp = client.post(url, {"next_status": "settled_closed"})
    assert resp.status_code == 302

    rma.refresh_from_db()
    assert rma.status == "settled_closed"
    assert rma.settlement_date == timezone.now().date()
    assert rma.settled_amount == Decimal("850.00")


def test_incomingquality_views_rma_advance_invalid_transition(client, admin_user, tenant_a, incoming_lot_a, supplier_party_a):
    """Verify illegal transition (e.g. draft directly to settled_closed) is rejected with error."""
    rma = QualityReturnAuthorization.objects.create(
        tenant=tenant_a,
        inspection_lot=incoming_lot_a,
        supplier=supplier_party_a,
        vendor_rma_number="VRMA-ILLEGAL-01",
        return_reason="dimensional_oos",
        disposition_type="return_for_credit",
        return_quantity=Decimal("20.000"),
        status="draft",
    )
    url = reverse("quality:quality_return_authorization_advance", kwargs={"pk": rma.pk})

    client.force_login(admin_user)
    resp = client.post(url, {"next_status": "settled_closed"})
    assert resp.status_code == 302

    rma.refresh_from_db()
    assert rma.status == "draft"


def test_incomingquality_views_rma_export_csv(client, admin_user, rma_a):
    """Verify RMA export returns CSV with correct columns and nosniff protection."""
    client.force_login(admin_user)
    url = reverse("quality:quality_return_authorization_export")
    resp = client.get(url)
    assert resp.status_code == 200
    assert "text/csv" in resp["Content-Type"]
    assert "quality_return_authorizations.csv" in resp["Content-Disposition"]
    assert resp["X-Content-Type-Options"] == "nosniff"

    content = resp.content.decode("utf-8")
    reader = csv.reader(io.StringIO(content))
    headers = next(reader)
    assert "RMA Number" in headers
    assert "Vendor RMA #" in headers
    assert "Disposition Type" in headers
    rows = list(reader)
    assert any(rma_a.number in row[0] for row in rows)


# =============================================================================
# 5. IQC SPC Dashboard Views
# =============================================================================

def test_incomingquality_views_spc_dashboard_get_and_context(client, admin_user, incoming_lot_a):
    """Verify IQC SPC Dashboard GET returns 200 with all metrics and KPI aggregations."""
    client.force_login(admin_user)
    url = reverse("quality:iqc_spc_dashboard")
    resp = client.get(url)
    assert resp.status_code == 200

    context_keys = [
        "lots_inspected_count",
        "acceptance_rate",
        "avg_cpk",
        "out_of_control_count",
        "recent_alerts",
        "supplier_leaderboard",
        "defect_pareto",
    ]
    for key in context_keys:
        assert key in resp.context, f"Key '{key}' missing from dashboard context"

    assert resp.context["lots_inspected_count"] >= 1
    assert "critical" in resp.context["defect_pareto"]
    assert "major" in resp.context["defect_pareto"]
    assert "minor" in resp.context["defect_pareto"]


def test_incomingquality_views_spc_dashboard_metrics_and_alerts(client, admin_user, tenant_a, supplier_party_a, incoming_plan_a):
    """Verify SPC dashboard reflects defect counts, out of control alerts, and supplier ranking."""
    # Create an alert lot with defects and low Cpk
    alert_lot = IncomingInspectionLot.objects.create(
        tenant=tenant_a,
        inspection_plan=incoming_plan_a,
        supplier=supplier_party_a,
        item_code="TI-ROD-01",
        item_name="Titanium Rod",
        lot_number="LOT-ALERT-999",
        lot_quantity=Decimal("200.000"),
        sample_size=15,
        inspected_quantity=15,
        critical_defects=3,
        major_defects=5,
        minor_defects=7,
        stage="completed",
        usage_decision="rejected",
        spc_cpk=Decimal("0.850"),
        spc_out_of_control=True,
    )

    client.force_login(admin_user)
    url = reverse("quality:iqc_spc_dashboard")
    resp = client.get(url)
    assert resp.status_code == 200

    assert resp.context["out_of_control_count"] >= 1
    assert resp.context["defect_pareto"]["critical"] >= 3
    assert resp.context["defect_pareto"]["major"] >= 5
    assert resp.context["defect_pareto"]["minor"] >= 7
    assert any(alert_lot.number == a.number for a in resp.context["recent_alerts"])
    assert any(s["name"] == supplier_party_a.name for s in resp.context["supplier_leaderboard"])


# =============================================================================
# 6. Cross-Tenant Isolation & Authentication Guards
# =============================================================================

def test_incomingquality_views_unauthenticated_redirect(client, incoming_plan_a, incoming_lot_a, coa_a, rma_a):
    """Verify unauthenticated access to all IQC endpoints redirects to login."""
    urls = [
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

    for url in urls:
        resp = client.get(url)
        assert resp.status_code == 302
        assert "/accounts/login/" in resp.url or "login" in resp.url


def test_incomingquality_views_cross_tenant_isolation_detail(client, admin_user, incoming_plan_b, incoming_lot_b, coa_b, rma_b):
    """Verify tenant_a user cannot access tenant_b objects via detail, edit, delete, or action views (returns 404)."""
    client.force_login(admin_user)

    # Detail 404
    assert client.get(reverse("quality:incoming_inspection_plan_detail", kwargs={"pk": incoming_plan_b.pk})).status_code == 404
    assert client.get(reverse("quality:incoming_inspection_lot_detail", kwargs={"pk": incoming_lot_b.pk})).status_code == 404
    assert client.get(reverse("quality:certificate_of_analysis_detail", kwargs={"pk": coa_b.pk})).status_code == 404
    assert client.get(reverse("quality:quality_return_authorization_detail", kwargs={"pk": rma_b.pk})).status_code == 404

    # Edit 404
    assert client.get(reverse("quality:incoming_inspection_plan_edit", kwargs={"pk": incoming_plan_b.pk})).status_code == 404
    assert client.get(reverse("quality:incoming_inspection_lot_edit", kwargs={"pk": incoming_lot_b.pk})).status_code == 404
    assert client.get(reverse("quality:certificate_of_analysis_edit", kwargs={"pk": coa_b.pk})).status_code == 404
    assert client.get(reverse("quality:quality_return_authorization_edit", kwargs={"pk": rma_b.pk})).status_code == 404

    # Delete 404
    assert client.post(reverse("quality:incoming_inspection_plan_delete", kwargs={"pk": incoming_plan_b.pk})).status_code == 404
    assert client.post(reverse("quality:incoming_inspection_lot_delete", kwargs={"pk": incoming_lot_b.pk})).status_code == 404
    assert client.post(reverse("quality:certificate_of_analysis_delete", kwargs={"pk": coa_b.pk})).status_code == 404
    assert client.post(reverse("quality:quality_return_authorization_delete", kwargs={"pk": rma_b.pk})).status_code == 404

    # Custom actions 404
    assert client.post(reverse("quality:incoming_inspection_lot_record_sample", kwargs={"pk": incoming_lot_b.pk})).status_code == 404
    assert client.post(reverse("quality:incoming_inspection_lot_make_decision", kwargs={"pk": incoming_lot_b.pk})).status_code == 404
    assert client.post(reverse("quality:certificate_of_analysis_verify", kwargs={"pk": coa_b.pk})).status_code == 404
    assert client.post(reverse("quality:quality_return_authorization_advance", kwargs={"pk": rma_b.pk})).status_code == 404


def test_incomingquality_views_cross_tenant_isolation_list(client, admin_user, incoming_plan_b, incoming_lot_b, coa_b, rma_b):
    """Verify tenant_a list views and dashboard do not expose tenant_b records."""
    client.force_login(admin_user)

    plan_resp = client.get(reverse("quality:incoming_inspection_plan_list"))
    assert incoming_plan_b.number not in plan_resp.content.decode()

    lot_resp = client.get(reverse("quality:incoming_inspection_lot_list"))
    assert incoming_lot_b.number not in lot_resp.content.decode()

    coa_resp = client.get(reverse("quality:certificate_of_analysis_list"))
    assert coa_b.number not in coa_resp.content.decode()

    rma_resp = client.get(reverse("quality:quality_return_authorization_list"))
    assert rma_b.number not in rma_resp.content.decode()
