"""
View unit tests for Sub-module 12.8: In-Process Quality Control (IPQC).

Covers all views, routes, query filters, search, pagination, context contracts,
form submissions (valid & invalid), status progressions, production release gating,
CSV exports, admin deletion gates, and multi-tenant isolation:
1. InProcessInspection (list, detail, create, edit, delete, export)
2. FirstArticleInspection (list, detail, create, edit, release, delete, export)
3. ProcessParameterLog (list, detail, create, edit, delete, export)
4. LayeredProcessAudit (list, detail, create, edit, delete, export)
5. SPC Control Dashboard (spc_dashboard)
6. Cross-tenant isolation & unauthenticated redirection
"""

import csv
import io
from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from apps.core.models import AuditLog
from apps.quality.models import (
    FirstArticleInspection,
    InProcessInspection,
    LayeredProcessAudit,
    ProcessParameterLog,
)

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
# 1. InProcessInspection Views
# =============================================================================

def test_inprocessquality_view_inspection_list_get_and_context(client, admin_user, in_process_inspection_a):
    """Verify inspection list GET returns 200 with required context keys, stats, and item content."""
    client.force_login(admin_user)
    url = reverse("quality:in_process_inspection_list")
    resp = client.get(url)
    assert resp.status_code == 200

    context_keys = [
        "page_obj",
        "inspections",
        "status_choices",
        "disposition_choices",
        "type_choices",
        "defect_choices",
        "work_centers",
        "total_inspections_count",
        "passed_count",
        "rework_count",
        "rejected_count",
        "search_query",
        "current_status",
        "current_disposition",
        "current_type",
        "current_defect",
        "current_work_center",
    ]
    for key in context_keys:
        assert key in resp.context, f"Key '{key}' missing from inspection list context"

    assert in_process_inspection_a in resp.context["inspections"]
    assert resp.context["total_inspections_count"] >= 1
    content = resp.content.decode()
    assert in_process_inspection_a.number in content
    assert in_process_inspection_a.title in content


def test_inprocessquality_view_inspection_list_search_and_filters(client, admin_user, in_process_inspection_a):
    """Verify inspection list filters by search query, status, disposition, and inspection_type."""
    client.force_login(admin_user)
    url = reverse("quality:in_process_inspection_list")

    # Match search query
    resp_search = client.get(url, {"q": in_process_inspection_a.title})
    assert resp_search.status_code == 200
    assert in_process_inspection_a in resp_search.context["inspections"]

    # Match type and disposition
    resp_filter = client.get(url, {
        "status": in_process_inspection_a.status,
        "disposition": in_process_inspection_a.disposition,
        "inspection_type": in_process_inspection_a.inspection_type,
    })
    assert resp_filter.status_code == 200
    assert in_process_inspection_a in resp_filter.context["inspections"]

    # Non-matching filter
    resp_nomatch = client.get(url, {"status": "cancelled"})
    assert resp_nomatch.status_code == 200
    assert in_process_inspection_a not in resp_nomatch.context["inspections"]


def test_inprocessquality_view_inspection_list_pagination_and_junk(client, admin_user, tenant_a):
    """Verify inspection list handles pagination and invalid query parameters gracefully."""
    client.force_login(admin_user)
    url = reverse("quality:in_process_inspection_list")

    # Create 16 inspections to exceed page size (15)
    for i in range(16):
        InProcessInspection.objects.create(
            tenant=tenant_a,
            title=f"Batch Inspection #{i}",
            inspection_type="dimensional_gauging",
            stage_gate="Op 010",
            status="completed",
            disposition="pass",
            production_order_number=f"PO-TEST-{i}",
            work_center_code="WC-01",
            item_code=f"ITEM-{i}",
            item_name=f"Part {i}",
            lot_number=f"LOT-{i}",
            batch_quantity=100,
            sample_size_inspected=5,
            quantity_passed=5,
            quantity_rejected=0,
        )

    resp_p1 = client.get(url)
    assert resp_p1.status_code == 200
    assert resp_p1.context["page_obj"].number == 1
    assert len(resp_p1.context["page_obj"]) == 15

    resp_p2 = client.get(url, {"page": 2})
    assert resp_p2.status_code == 200
    assert resp_p2.context["page_obj"].number == 2

    # Junk parameter handling
    resp_junk = client.get(url, {"page": "invalid_page", "work_center": "non_numeric"})
    assert resp_junk.status_code == 200
    assert resp_junk.context["page_obj"].number == 1


def test_inprocessquality_view_inspection_list_empty_state(client, admin_user):
    """Verify inspection list renders empty state when no inspections exist."""
    client.force_login(admin_user)
    InProcessInspection.objects.all().delete()
    url = reverse("quality:in_process_inspection_list")
    resp = client.get(url)
    assert resp.status_code == 200
    assert resp.context["total_inspections_count"] == 0
    assert len(resp.context["inspections"]) == 0


def test_inprocessquality_view_inspection_detail_get_and_context(client, admin_user, in_process_inspection_a):
    """Verify inspection detail GET returns 200 with inspection context and rendered content."""
    client.force_login(admin_user)
    url = reverse("quality:in_process_inspection_detail", kwargs={"pk": in_process_inspection_a.pk})
    resp = client.get(url)
    assert resp.status_code == 200
    assert resp.context["inspection"] == in_process_inspection_a
    content = resp.content.decode()
    assert in_process_inspection_a.number in content
    assert in_process_inspection_a.item_code in content


def test_inprocessquality_view_inspection_detail_404_not_found(client, admin_user):
    """Verify inspection detail returns 404 for non-existent pk."""
    client.force_login(admin_user)
    url = reverse("quality:in_process_inspection_detail", kwargs={"pk": 999999})
    resp = client.get(url)
    assert resp.status_code == 404


def test_inprocessquality_view_inspection_create_get(client, admin_user):
    """Verify inspection create GET renders empty form and title context."""
    client.force_login(admin_user)
    url = reverse("quality:in_process_inspection_create")
    resp = client.get(url)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["is_edit"] is False
    assert resp.context["inspection"] is None
    assert resp.context["title"] == "New In-Process Inspection"


def test_inprocessquality_view_inspection_create_post_valid(client, admin_user, tenant_a, doc_a):
    """Verify valid POST creates inspection, records audit log, and redirects to detail."""
    client.force_login(admin_user)
    url = reverse("quality:in_process_inspection_create")
    post_data = _inprocessquality_inspection_post_data(
        doc=doc_a,
        title="Bore Grinding Stage Inspection",
        item_code="BRG-GRIND-09",
    )

    resp = client.post(url, post_data)
    assert resp.status_code == 302

    created = InProcessInspection.objects.get(title="Bore Grinding Stage Inspection", tenant=tenant_a)
    assert resp.url == reverse("quality:in_process_inspection_detail", kwargs={"pk": created.pk})
    assert created.tenant == tenant_a
    assert created.item_code == "BRG-GRIND-09"

    # Verify audit log
    assert AuditLog.objects.filter(
        tenant=tenant_a,
        action="create",
        object_repr__contains=created.number,
    ).exists()


def test_inprocessquality_view_inspection_create_post_invalid(client, admin_user):
    """Verify invalid POST on inspection create returns 200 with form errors."""
    client.force_login(admin_user)
    url = reverse("quality:in_process_inspection_create")
    resp = client.post(url, {"title": "", "item_code": ""})
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["form"].errors


def test_inprocessquality_view_inspection_edit_get(client, admin_user, in_process_inspection_a):
    """Verify inspection edit GET renders form bound to existing instance."""
    client.force_login(admin_user)
    url = reverse("quality:in_process_inspection_edit", kwargs={"pk": in_process_inspection_a.pk})
    resp = client.get(url)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["is_edit"] is True
    assert resp.context["inspection"] == in_process_inspection_a


def test_inprocessquality_view_inspection_edit_post_valid(client, admin_user, in_process_inspection_a):
    """Verify valid POST updates inspection, writes audit log, and redirects to detail."""
    client.force_login(admin_user)
    url = reverse("quality:in_process_inspection_edit", kwargs={"pk": in_process_inspection_a.pk})
    post_data = _inprocessquality_inspection_post_data(
        title="Updated CNC Mill Inspection",
        notes="Gaging recalibrated prior to measurement.",
    )

    resp = client.post(url, post_data)
    assert resp.status_code == 302
    assert resp.url == reverse("quality:in_process_inspection_detail", kwargs={"pk": in_process_inspection_a.pk})

    in_process_inspection_a.refresh_from_db()
    assert in_process_inspection_a.title == "Updated CNC Mill Inspection"
    assert in_process_inspection_a.notes == "Gaging recalibrated prior to measurement."

    assert AuditLog.objects.filter(
        tenant=in_process_inspection_a.tenant,
        action="update",
        object_repr__contains=in_process_inspection_a.number,
    ).exists()


def test_inprocessquality_view_inspection_edit_post_invalid(client, admin_user, in_process_inspection_a):
    """Verify invalid POST on edit renders 200 with form errors."""
    client.force_login(admin_user)
    url = reverse("quality:in_process_inspection_edit", kwargs={"pk": in_process_inspection_a.pk})
    resp = client.post(url, {"title": "", "item_code": ""})
    assert resp.status_code == 200
    assert resp.context["form"].errors


def test_inprocessquality_view_inspection_delete_success(client, admin_user, tenant_a):
    """Verify admin user can delete inspection via POST and is redirected to list."""
    to_delete = InProcessInspection.objects.create(
        tenant=tenant_a,
        title="Inspection to Delete",
        inspection_type="dimensional_gauging",
        stage_gate="Op 010",
        status="draft",
        disposition="pending",
        production_order_number="PO-DEL-01",
        work_center_code="WC-01",
        item_code="DEL-01",
        item_name="Delete Part",
        lot_number="LOT-DEL",
        batch_quantity=10,
        sample_size_inspected=2,
        quantity_passed=2,
        quantity_rejected=0,
    )
    client.force_login(admin_user)
    url = reverse("quality:in_process_inspection_delete", kwargs={"pk": to_delete.pk})
    resp = client.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("quality:in_process_inspection_list")
    assert not InProcessInspection.objects.filter(pk=to_delete.pk).exists()

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        action="delete",
        object_repr__contains=to_delete.number,
    ).exists()


def test_inprocessquality_view_inspection_delete_get_not_allowed(client, admin_user, in_process_inspection_a):
    """Verify GET on inspection delete returns 405 Method Not Allowed."""
    client.force_login(admin_user)
    url = reverse("quality:in_process_inspection_delete", kwargs={"pk": in_process_inspection_a.pk})
    resp = client.get(url)
    assert resp.status_code == 405


def test_inprocessquality_view_inspection_delete_non_admin_forbidden(client, member_user, in_process_inspection_a):
    """Verify non-admin user is rejected with 403 on inspection delete."""
    client.force_login(member_user)
    url = reverse("quality:in_process_inspection_delete", kwargs={"pk": in_process_inspection_a.pk})
    resp = client.post(url)
    assert resp.status_code == 403


def test_inprocessquality_view_inspection_export_csv(client, admin_user, in_process_inspection_a):
    """Verify inspection export returns CSV with correct headers and nosniff protection."""
    client.force_login(admin_user)
    url = reverse("quality:in_process_inspection_export_csv")
    resp = client.get(url)
    assert resp.status_code == 200
    assert "text/csv" in resp["Content-Type"]
    assert "in_process_inspections.csv" in resp["Content-Disposition"]
    assert resp["X-Content-Type-Options"] == "nosniff"

    content = resp.content.decode("utf-8")
    reader = csv.reader(io.StringIO(content))
    headers = next(reader)
    assert "Inspection Number" in headers
    assert "Item Code" in headers
    assert "Disposition" in headers
    rows = list(reader)
    assert any(in_process_inspection_a.number in row[0] for row in rows)

    assert AuditLog.objects.filter(
        tenant=in_process_inspection_a.tenant,
        action="export",
    ).exists()


# =============================================================================
# 2. FirstArticleInspection Views
# =============================================================================

def test_inprocessquality_view_fai_list_get_and_context(client, admin_user, fai_a):
    """Verify FAI list GET returns 200 with required context keys, stats, and FAI content."""
    client.force_login(admin_user)
    url = reverse("quality:first_article_inspection_list")
    resp = client.get(url)
    assert resp.status_code == 200

    context_keys = [
        "page_obj",
        "fais",
        "status_choices",
        "fai_type_choices",
        "setup_reason_choices",
        "verdict_choices",
        "work_centers",
        "total_fais_count",
        "approved_count",
        "conditional_count",
        "rejected_count",
        "search_query",
        "current_status",
        "current_type",
        "current_reason",
        "current_verdict",
        "current_work_center",
    ]
    for key in context_keys:
        assert key in resp.context, f"Key '{key}' missing from FAI list context"

    assert fai_a in resp.context["fais"]
    assert resp.context["total_fais_count"] >= 1
    content = resp.content.decode()
    assert fai_a.number in content
    assert fai_a.item_code in content


def test_inprocessquality_view_fai_list_search_and_filters(client, admin_user, fai_a):
    """Verify FAI list filters correctly by search query, status, fai_type, and setup_reason."""
    client.force_login(admin_user)
    url = reverse("quality:first_article_inspection_list")

    resp_search = client.get(url, {"q": fai_a.item_code})
    assert resp_search.status_code == 200
    assert fai_a in resp_search.context["fais"]

    resp_filter = client.get(url, {
        "status": fai_a.status,
        "fai_type": fai_a.fai_type,
        "setup_reason": fai_a.setup_reason,
        "release_verdict": fai_a.release_verdict,
    })
    assert resp_filter.status_code == 200
    assert fai_a in resp_filter.context["fais"]

    resp_nomatch = client.get(url, {"status": "rejected_setup_hold"})
    assert resp_nomatch.status_code == 200
    assert fai_a not in resp_nomatch.context["fais"]


def test_inprocessquality_view_fai_list_pagination_and_empty(client, admin_user, tenant_a):
    """Verify FAI list pagination and empty state handling."""
    client.force_login(admin_user)
    url = reverse("quality:first_article_inspection_list")

    # Empty state test
    FirstArticleInspection.objects.all().delete()
    resp_empty = client.get(url)
    assert resp_empty.status_code == 200
    assert resp_empty.context["total_fais_count"] == 0

    # Create 16 FAIs to exceed page size (15)
    for i in range(16):
        FirstArticleInspection.objects.create(
            tenant=tenant_a,
            title=f"FAI #{i}",
            fai_type="full_fai",
            setup_reason="new_product_intro",
            status="in_inspection",
            release_verdict="pending",
            production_order_number=f"PO-FAI-{i}",
            work_center_code="WC-01",
            item_code=f"PART-{i}",
            item_name=f"Part {i}",
            drawing_number=f"DWG-{i}",
            drawing_revision="A",
            total_characteristics_inspected=5,
            characteristics_conforming=5,
            characteristics_out_of_spec=0,
        )

    resp_p1 = client.get(url)
    assert resp_p1.status_code == 200
    assert len(resp_p1.context["page_obj"]) == 15

    resp_p2 = client.get(url, {"page": 2})
    assert resp_p2.status_code == 200
    assert resp_p2.context["page_obj"].number == 2


def test_inprocessquality_view_fai_detail_get_and_context(client, admin_user, fai_a):
    """Verify FAI detail GET returns 200 with fai context and content."""
    client.force_login(admin_user)
    url = reverse("quality:first_article_inspection_detail", kwargs={"pk": fai_a.pk})
    resp = client.get(url)
    assert resp.status_code == 200
    assert resp.context["fai"] == fai_a
    content = resp.content.decode()
    assert fai_a.number in content
    assert fai_a.drawing_number in content


def test_inprocessquality_view_fai_create_get(client, admin_user):
    """Verify FAI create GET renders empty form and title context."""
    client.force_login(admin_user)
    url = reverse("quality:first_article_inspection_create")
    resp = client.get(url)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["is_edit"] is False
    assert resp.context["title"] == "New First Article Inspection"


def test_inprocessquality_view_fai_create_post_valid(client, admin_user, tenant_a):
    """Verify valid POST creates FAI, writes audit log, and redirects to detail."""
    client.force_login(admin_user)
    url = reverse("quality:first_article_inspection_create")
    post_data = _inprocessquality_fai_post_data(
        title="Spindle Flange First Article Inspection",
        item_code="FLG-SPN-01",
    )

    resp = client.post(url, post_data)
    assert resp.status_code == 302

    created = FirstArticleInspection.objects.get(title="Spindle Flange First Article Inspection", tenant=tenant_a)
    assert resp.url == reverse("quality:first_article_inspection_detail", kwargs={"pk": created.pk})
    assert created.tenant == tenant_a
    assert created.item_code == "FLG-SPN-01"

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        action="create",
        object_repr__contains=created.number,
    ).exists()


def test_inprocessquality_view_fai_create_post_invalid(client, admin_user):
    """Verify invalid POST on FAI create returns 200 with errors."""
    client.force_login(admin_user)
    url = reverse("quality:first_article_inspection_create")
    resp = client.post(url, {"title": "", "item_code": ""})
    assert resp.status_code == 200
    assert resp.context["form"].errors


def test_inprocessquality_view_fai_edit_get(client, admin_user, fai_a):
    """Verify FAI edit GET renders bound form and context."""
    client.force_login(admin_user)
    url = reverse("quality:first_article_inspection_edit", kwargs={"pk": fai_a.pk})
    resp = client.get(url)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["is_edit"] is True
    assert resp.context["fai"] == fai_a


def test_inprocessquality_view_fai_edit_post_valid(client, admin_user, fai_a):
    """Verify valid POST updates FAI, writes audit log, and redirects to detail."""
    client.force_login(admin_user)
    url = reverse("quality:first_article_inspection_edit", kwargs={"pk": fai_a.pk})
    post_data = _inprocessquality_fai_post_data(
        title="Updated Bracket FAI Protocol",
        notes="All characteristics cross-checked on coordinate measuring machine.",
    )

    resp = client.post(url, post_data)
    assert resp.status_code == 302
    assert resp.url == reverse("quality:first_article_inspection_detail", kwargs={"pk": fai_a.pk})

    fai_a.refresh_from_db()
    assert fai_a.title == "Updated Bracket FAI Protocol"
    assert fai_a.notes == "All characteristics cross-checked on coordinate measuring machine."

    assert AuditLog.objects.filter(
        tenant=fai_a.tenant,
        action="update",
        object_repr__contains=fai_a.number,
    ).exists()


def test_inprocessquality_view_fai_edit_post_invalid(client, admin_user, fai_a):
    """Verify invalid POST on FAI edit renders 200 with errors."""
    client.force_login(admin_user)
    url = reverse("quality:first_article_inspection_edit", kwargs={"pk": fai_a.pk})
    resp = client.post(url, {"title": ""})
    assert resp.status_code == 200
    assert resp.context["form"].errors


def test_inprocessquality_view_fai_release_success(client, admin_user, fai_a):
    """Verify admin release sets status, release_verdict, approved_by, AS9102 flags, and logs audit."""
    fai_a.status = "in_inspection"
    fai_a.release_verdict = "pending"
    fai_a.total_characteristics_inspected = 10
    fai_a.characteristics_conforming = 10
    fai_a.characteristics_out_of_spec = 0
    fai_a.save()

    client.force_login(admin_user)
    url = reverse("quality:first_article_inspection_release", kwargs={"pk": fai_a.pk})
    resp = client.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("quality:first_article_inspection_detail", kwargs={"pk": fai_a.pk})

    fai_a.refresh_from_db()
    assert fai_a.status == "approved_run_released"
    assert fai_a.release_verdict == "released"
    assert fai_a.approved_by == admin_user
    assert fai_a.approved_at is not None
    assert fai_a.as9102_form1_complete is True
    assert fai_a.as9102_form2_complete is True
    assert fai_a.as9102_form3_complete is True

    assert AuditLog.objects.filter(
        tenant=fai_a.tenant,
        action="release",
        object_repr__contains=fai_a.number,
    ).exists()


def test_inprocessquality_view_fai_release_already_released(client, admin_user, fai_a):
    """Verify attempting to release an already released FAI redirects with info message."""
    fai_a.status = "approved_run_released"
    fai_a.release_verdict = "released"
    fai_a.save()

    client.force_login(admin_user)
    url = reverse("quality:first_article_inspection_release", kwargs={"pk": fai_a.pk})
    resp = client.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("quality:first_article_inspection_detail", kwargs={"pk": fai_a.pk})


def test_inprocessquality_view_fai_release_blocked_zero_characteristics(client, admin_user, fai_a):
    """Verify release is rejected when total characteristics inspected <= 0."""
    fai_a.status = "in_inspection"
    fai_a.total_characteristics_inspected = 0
    fai_a.characteristics_out_of_spec = 0
    fai_a.save()

    client.force_login(admin_user)
    url = reverse("quality:first_article_inspection_release", kwargs={"pk": fai_a.pk})
    resp = client.post(url)
    assert resp.status_code == 302

    fai_a.refresh_from_db()
    assert fai_a.status == "in_inspection"
    assert fai_a.release_verdict != "released"


def test_inprocessquality_view_fai_release_blocked_oos_characteristics(client, admin_user, fai_a):
    """Verify release is rejected when characteristics out of spec > 0."""
    fai_a.status = "in_inspection"
    fai_a.total_characteristics_inspected = 10
    fai_a.characteristics_out_of_spec = 1
    fai_a.save()

    client.force_login(admin_user)
    url = reverse("quality:first_article_inspection_release", kwargs={"pk": fai_a.pk})
    resp = client.post(url)
    assert resp.status_code == 302

    fai_a.refresh_from_db()
    assert fai_a.status == "in_inspection"
    assert fai_a.release_verdict != "released"


def test_inprocessquality_view_fai_release_get_not_allowed(client, admin_user, fai_a):
    """Verify GET on FAI release returns 405 Method Not Allowed."""
    client.force_login(admin_user)
    url = reverse("quality:first_article_inspection_release", kwargs={"pk": fai_a.pk})
    resp = client.get(url)
    assert resp.status_code == 405


def test_inprocessquality_view_fai_release_non_admin_forbidden(client, member_user, fai_a):
    """Verify non-admin user is rejected with 403 on FAI release."""
    client.force_login(member_user)
    url = reverse("quality:first_article_inspection_release", kwargs={"pk": fai_a.pk})
    resp = client.post(url)
    assert resp.status_code == 403


def test_inprocessquality_view_fai_delete_success(client, admin_user, tenant_a):
    """Verify admin user can delete FAI via POST and is redirected to list."""
    to_delete = FirstArticleInspection.objects.create(
        tenant=tenant_a,
        title="FAI to Delete",
        fai_type="full_fai",
        setup_reason="new_product_intro",
        status="draft",
        production_order_number="PO-DEL-FAI",
        work_center_code="WC-01",
        item_code="DEL-PART",
        item_name="Delete Part",
        drawing_number="DWG-DEL",
        drawing_revision="A",
        total_characteristics_inspected=2,
        characteristics_conforming=2,
        characteristics_out_of_spec=0,
    )
    client.force_login(admin_user)
    url = reverse("quality:first_article_inspection_delete", kwargs={"pk": to_delete.pk})
    resp = client.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("quality:first_article_inspection_list")
    assert not FirstArticleInspection.objects.filter(pk=to_delete.pk).exists()

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        action="delete",
        object_repr__contains=to_delete.number,
    ).exists()


def test_inprocessquality_view_fai_delete_get_not_allowed(client, admin_user, fai_a):
    """Verify GET on FAI delete returns 405 Method Not Allowed."""
    client.force_login(admin_user)
    url = reverse("quality:first_article_inspection_delete", kwargs={"pk": fai_a.pk})
    resp = client.get(url)
    assert resp.status_code == 405


def test_inprocessquality_view_fai_delete_non_admin_forbidden(client, member_user, fai_a):
    """Verify non-admin user is rejected with 403 on FAI delete."""
    client.force_login(member_user)
    url = reverse("quality:first_article_inspection_delete", kwargs={"pk": fai_a.pk})
    resp = client.post(url)
    assert resp.status_code == 403


def test_inprocessquality_view_fai_export_csv(client, admin_user, fai_a):
    """Verify FAI export returns CSV with correct headers and nosniff protection."""
    client.force_login(admin_user)
    url = reverse("quality:first_article_inspection_export_csv")
    resp = client.get(url)
    assert resp.status_code == 200
    assert "text/csv" in resp["Content-Type"]
    assert "first_article_inspections.csv" in resp["Content-Disposition"]
    assert resp["X-Content-Type-Options"] == "nosniff"

    content = resp.content.decode("utf-8")
    reader = csv.reader(io.StringIO(content))
    headers = next(reader)
    assert "FAI Number" in headers
    assert "Drawing Number" in headers
    assert "Release Verdict" in headers
    rows = list(reader)
    assert any(fai_a.number in row[0] for row in rows)

    assert AuditLog.objects.filter(
        tenant=fai_a.tenant,
        action="export",
    ).exists()


# =============================================================================
# 3. ProcessParameterLog Views
# =============================================================================

def test_inprocessquality_view_param_log_list_get_and_context(client, admin_user, parameter_log_a):
    """Verify parameter log list GET returns 200 with required context keys, stats, and log content."""
    client.force_login(admin_user)
    url = reverse("quality:process_parameter_log_list")
    resp = client.get(url)
    assert resp.status_code == 200

    context_keys = [
        "page_obj",
        "parameter_logs",
        "category_choices",
        "excursion_choices",
        "containment_choices",
        "work_centers",
        "total_logs_count",
        "normal_count",
        "out_of_control_count",
        "out_of_spec_count",
        "search_query",
        "current_category",
        "current_excursion",
        "current_containment",
        "current_work_center",
    ]
    for key in context_keys:
        assert key in resp.context, f"Key '{key}' missing from parameter log list context"

    assert parameter_log_a in resp.context["parameter_logs"]
    assert resp.context["total_logs_count"] >= 1
    content = resp.content.decode()
    assert parameter_log_a.number in content
    assert parameter_log_a.parameter_name in content


def test_inprocessquality_view_param_log_list_search_and_filters(client, admin_user, parameter_log_a):
    """Verify parameter log list filters by search query, category, and excursion_status."""
    client.force_login(admin_user)
    url = reverse("quality:process_parameter_log_list")

    resp_search = client.get(url, {"q": parameter_log_a.parameter_name})
    assert resp_search.status_code == 200
    assert parameter_log_a in resp_search.context["parameter_logs"]

    resp_filter = client.get(url, {
        "parameter_category": parameter_log_a.parameter_category,
        "excursion_status": parameter_log_a.excursion_status,
    })
    assert resp_filter.status_code == 200
    assert parameter_log_a in resp_filter.context["parameter_logs"]

    resp_nomatch = client.get(url, {"excursion_status": "out_of_spec"})
    assert resp_nomatch.status_code == 200
    assert parameter_log_a not in resp_nomatch.context["parameter_logs"]


def test_inprocessquality_view_param_log_list_pagination_and_empty(client, admin_user, tenant_a):
    """Verify parameter log list pagination and empty state handling."""
    client.force_login(admin_user)
    url = reverse("quality:process_parameter_log_list")

    # Empty state test
    ProcessParameterLog.objects.all().delete()
    resp_empty = client.get(url)
    assert resp_empty.status_code == 200
    assert resp_empty.context["total_logs_count"] == 0

    # Create 16 logs to exceed page size (15)
    for i in range(16):
        ProcessParameterLog.objects.create(
            tenant=tenant_a,
            parameter_name=f"Param #{i}",
            parameter_category="temperature",
            unit_of_measure="°C",
            work_center_code="WC-01",
            item_code=f"ITEM-{i}",
            target_nominal_value=Decimal("100.0000"),
            lower_spec_limit=Decimal("90.0000"),
            upper_spec_limit=Decimal("110.0000"),
            recorded_value=Decimal("100.5000"),
            excursion_status="normal",
        )

    resp_p1 = client.get(url)
    assert resp_p1.status_code == 200
    assert len(resp_p1.context["page_obj"]) == 15

    resp_p2 = client.get(url, {"page": 2})
    assert resp_p2.status_code == 200
    assert resp_p2.context["page_obj"].number == 2


def test_inprocessquality_view_param_log_detail_get_and_context(client, admin_user, parameter_log_a):
    """Verify parameter log detail GET returns 200 with log context and content."""
    client.force_login(admin_user)
    url = reverse("quality:process_parameter_log_detail", kwargs={"pk": parameter_log_a.pk})
    resp = client.get(url)
    assert resp.status_code == 200
    assert resp.context["log"] == parameter_log_a
    content = resp.content.decode()
    assert parameter_log_a.number in content
    assert parameter_log_a.parameter_name in content


def test_inprocessquality_view_param_log_create_get(client, admin_user):
    """Verify parameter log create GET renders form and title context."""
    client.force_login(admin_user)
    url = reverse("quality:process_parameter_log_create")
    resp = client.get(url)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["is_edit"] is False
    assert resp.context["title"] == "Log Critical Process Parameter"


def test_inprocessquality_view_param_log_create_post_valid(client, admin_user, tenant_a):
    """Verify valid POST creates log, automatically sets logged_by to request.user, and logs audit."""
    client.force_login(admin_user)
    url = reverse("quality:process_parameter_log_create")
    post_data = _inprocessquality_param_post_data(
        parameter_name="Wave Solder Preheat Temperature",
        item_code="PCB-WAVE-01",
    )

    resp = client.post(url, post_data)
    assert resp.status_code == 302

    created = ProcessParameterLog.objects.get(parameter_name="Wave Solder Preheat Temperature", tenant=tenant_a)
    assert resp.url == reverse("quality:process_parameter_log_detail", kwargs={"pk": created.pk})
    assert created.tenant == tenant_a
    assert created.logged_by == admin_user
    assert created.item_code == "PCB-WAVE-01"

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        action="create",
        object_repr__contains=created.number,
    ).exists()


def test_inprocessquality_view_param_log_create_post_invalid(client, admin_user):
    """Verify invalid POST on parameter log create returns 200 with errors."""
    client.force_login(admin_user)
    url = reverse("quality:process_parameter_log_create")
    resp = client.post(url, {"parameter_name": ""})
    assert resp.status_code == 200
    assert resp.context["form"].errors


def test_inprocessquality_view_param_log_edit_get(client, admin_user, parameter_log_a):
    """Verify parameter log edit GET renders form bound to instance."""
    client.force_login(admin_user)
    url = reverse("quality:process_parameter_log_edit", kwargs={"pk": parameter_log_a.pk})
    resp = client.get(url)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["is_edit"] is True
    assert resp.context["log"] == parameter_log_a


def test_inprocessquality_view_param_log_edit_post_valid(client, admin_user, parameter_log_a):
    """Verify valid POST updates parameter log, writes audit log, and redirects to detail."""
    client.force_login(admin_user)
    url = reverse("quality:process_parameter_log_edit", kwargs={"pk": parameter_log_a.pk})
    post_data = _inprocessquality_param_post_data(
        parameter_name="Updated Reflow Temperature Profile",
        containment_notes="Thermal zone verified.",
    )

    resp = client.post(url, post_data)
    assert resp.status_code == 302
    assert resp.url == reverse("quality:process_parameter_log_detail", kwargs={"pk": parameter_log_a.pk})

    parameter_log_a.refresh_from_db()
    assert parameter_log_a.parameter_name == "Updated Reflow Temperature Profile"
    assert parameter_log_a.containment_notes == "Thermal zone verified."

    assert AuditLog.objects.filter(
        tenant=parameter_log_a.tenant,
        action="update",
        object_repr__contains=parameter_log_a.number,
    ).exists()


def test_inprocessquality_view_param_log_edit_post_invalid(client, admin_user, parameter_log_a):
    """Verify invalid POST on edit renders 200 with form errors."""
    client.force_login(admin_user)
    url = reverse("quality:process_parameter_log_edit", kwargs={"pk": parameter_log_a.pk})
    resp = client.post(url, {"parameter_name": ""})
    assert resp.status_code == 200
    assert resp.context["form"].errors


def test_inprocessquality_view_param_log_delete_success(client, admin_user, tenant_a):
    """Verify admin user can delete parameter log via POST and is redirected to list."""
    to_delete = ProcessParameterLog.objects.create(
        tenant=tenant_a,
        parameter_name="Log to Delete",
        parameter_category="temperature",
        unit_of_measure="°C",
        work_center_code="WC-01",
        item_code="DEL-01",
        target_nominal_value=Decimal("100.0000"),
        lower_spec_limit=Decimal("90.0000"),
        upper_spec_limit=Decimal("110.0000"),
        recorded_value=Decimal("100.0000"),
        excursion_status="normal",
    )
    client.force_login(admin_user)
    url = reverse("quality:process_parameter_log_delete", kwargs={"pk": to_delete.pk})
    resp = client.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("quality:process_parameter_log_list")
    assert not ProcessParameterLog.objects.filter(pk=to_delete.pk).exists()

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        action="delete",
        object_repr__contains=to_delete.number,
    ).exists()


def test_inprocessquality_view_param_log_delete_get_not_allowed(client, admin_user, parameter_log_a):
    """Verify GET on parameter log delete returns 405 Method Not Allowed."""
    client.force_login(admin_user)
    url = reverse("quality:process_parameter_log_delete", kwargs={"pk": parameter_log_a.pk})
    resp = client.get(url)
    assert resp.status_code == 405


def test_inprocessquality_view_param_log_delete_non_admin_forbidden(client, member_user, parameter_log_a):
    """Verify non-admin user is rejected with 403 on parameter log delete."""
    client.force_login(member_user)
    url = reverse("quality:process_parameter_log_delete", kwargs={"pk": parameter_log_a.pk})
    resp = client.post(url)
    assert resp.status_code == 403


def test_inprocessquality_view_param_log_export_csv(client, admin_user, parameter_log_a):
    """Verify parameter log export returns CSV with correct headers and nosniff protection."""
    client.force_login(admin_user)
    url = reverse("quality:process_parameter_log_export_csv")
    resp = client.get(url)
    assert resp.status_code == 200
    assert "text/csv" in resp["Content-Type"]
    assert "process_parameter_logs.csv" in resp["Content-Disposition"]
    assert resp["X-Content-Type-Options"] == "nosniff"

    content = resp.content.decode("utf-8")
    reader = csv.reader(io.StringIO(content))
    headers = next(reader)
    assert "Log Number" in headers
    assert "Parameter Name" in headers
    assert "Recorded Value" in headers
    rows = list(reader)
    assert any(parameter_log_a.number in row[0] for row in rows)

    assert AuditLog.objects.filter(
        tenant=parameter_log_a.tenant,
        action="export",
    ).exists()


# =============================================================================
# 4. LayeredProcessAudit Views
# =============================================================================

def test_inprocessquality_view_layered_audit_list_get_and_context(client, admin_user, layered_audit_a):
    """Verify LPA list GET returns 200 with required context keys, stats, and audit content."""
    client.force_login(admin_user)
    url = reverse("quality:layered_process_audit_list")
    resp = client.get(url)
    assert resp.status_code == 200

    context_keys = [
        "page_obj",
        "lpas",
        "layer_choices",
        "focus_choices",
        "status_choices",
        "work_centers",
        "total_audits_count",
        "completed_count",
        "scheduled_count",
        "avg_compliance_rate",
        "search_query",
        "current_layer",
        "current_focus",
        "current_status",
        "current_work_center",
    ]
    for key in context_keys:
        assert key in resp.context, f"Key '{key}' missing from LPA list context"

    assert layered_audit_a in resp.context["lpas"]
    assert resp.context["total_audits_count"] >= 1
    content = resp.content.decode()
    assert layered_audit_a.number in content
    assert layered_audit_a.title in content


def test_inprocessquality_view_layered_audit_list_search_and_filters(client, admin_user, layered_audit_a):
    """Verify LPA list filters by search query, audit_layer, focus_area, and status."""
    client.force_login(admin_user)
    url = reverse("quality:layered_process_audit_list")

    resp_search = client.get(url, {"q": layered_audit_a.title})
    assert resp_search.status_code == 200
    assert layered_audit_a in resp_search.context["lpas"]

    resp_filter = client.get(url, {
        "audit_layer": layered_audit_a.audit_layer,
        "focus_area": layered_audit_a.focus_area,
        "status": layered_audit_a.status,
    })
    assert resp_filter.status_code == 200
    assert layered_audit_a in resp_filter.context["lpas"]

    resp_nomatch = client.get(url, {"status": "scheduled"})
    assert resp_nomatch.status_code == 200
    assert layered_audit_a not in resp_nomatch.context["lpas"]


def test_inprocessquality_view_layered_audit_list_pagination_and_empty(client, admin_user, tenant_a):
    """Verify LPA list pagination and empty state handling."""
    client.force_login(admin_user)
    url = reverse("quality:layered_process_audit_list")

    # Empty state test
    LayeredProcessAudit.objects.all().delete()
    resp_empty = client.get(url)
    assert resp_empty.status_code == 200
    assert resp_empty.context["total_audits_count"] == 0

    # Create 16 LPAs to exceed page size (15)
    for i in range(16):
        LayeredProcessAudit.objects.create(
            tenant=tenant_a,
            title=f"LPA #{i}",
            audit_layer="tier_1_operator_lead",
            focus_area="standard_work_wi",
            status="completed",
            work_center_code="WC-01",
            shift="Shift 1",
            scheduled_date=timezone.now().date(),
            total_questions_audited=10,
            questions_conforming=10,
            questions_non_conforming=0,
            compliance_percentage=Decimal("100.00"),
        )

    resp_p1 = client.get(url)
    assert resp_p1.status_code == 200
    assert len(resp_p1.context["page_obj"]) == 15

    resp_p2 = client.get(url, {"page": 2})
    assert resp_p2.status_code == 200
    assert resp_p2.context["page_obj"].number == 2


def test_inprocessquality_view_layered_audit_detail_get_and_context(client, admin_user, layered_audit_a):
    """Verify LPA detail GET returns 200 with lpa context and content."""
    client.force_login(admin_user)
    url = reverse("quality:layered_process_audit_detail", kwargs={"pk": layered_audit_a.pk})
    resp = client.get(url)
    assert resp.status_code == 200
    assert resp.context["lpa"] == layered_audit_a
    content = resp.content.decode()
    assert layered_audit_a.number in content
    assert layered_audit_a.title in content


def test_inprocessquality_view_layered_audit_create_get(client, admin_user):
    """Verify LPA create GET renders form and title context."""
    client.force_login(admin_user)
    url = reverse("quality:layered_process_audit_create")
    resp = client.get(url)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["is_edit"] is False
    assert resp.context["title"] == "Schedule Layered Process Audit (LPA)"


def test_inprocessquality_view_layered_audit_create_post_valid(client, admin_user, tenant_a):
    """Verify valid POST creates LPA, sets auditor to request.user if blank, and logs audit."""
    client.force_login(admin_user)
    url = reverse("quality:layered_process_audit_create")
    post_data = _inprocessquality_audit_post_data(
        title="Weekly Plant Manager LPA Walk",
        audit_layer="tier_3_quality_manager",
        focus_area="safety_poka_yoke",
    )

    resp = client.post(url, post_data)
    assert resp.status_code == 302

    created = LayeredProcessAudit.objects.get(title="Weekly Plant Manager LPA Walk", tenant=tenant_a)
    assert resp.url == reverse("quality:layered_process_audit_detail", kwargs={"pk": created.pk})
    assert created.tenant == tenant_a
    assert created.auditor == admin_user
    assert created.focus_area == "safety_poka_yoke"

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        action="create",
        object_repr__contains=created.number,
    ).exists()


def test_inprocessquality_view_layered_audit_create_post_invalid(client, admin_user):
    """Verify invalid POST on LPA create returns 200 with form errors."""
    client.force_login(admin_user)
    url = reverse("quality:layered_process_audit_create")
    resp = client.post(url, {"title": ""})
    assert resp.status_code == 200
    assert resp.context["form"].errors


def test_inprocessquality_view_layered_audit_edit_get(client, admin_user, layered_audit_a):
    """Verify LPA edit GET renders form bound to instance."""
    client.force_login(admin_user)
    url = reverse("quality:layered_process_audit_edit", kwargs={"pk": layered_audit_a.pk})
    resp = client.get(url)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["is_edit"] is True
    assert resp.context["lpa"] == layered_audit_a


def test_inprocessquality_view_layered_audit_edit_post_valid(client, admin_user, layered_audit_a):
    """Verify valid POST updates LPA, writes audit log, and redirects to detail."""
    client.force_login(admin_user)
    url = reverse("quality:layered_process_audit_edit", kwargs={"pk": layered_audit_a.pk})
    post_data = _inprocessquality_audit_post_data(
        title="Updated Supervisor LPA Walk",
        notes="Torque calibration seals verified on all stations.",
    )

    resp = client.post(url, post_data)
    assert resp.status_code == 302
    assert resp.url == reverse("quality:layered_process_audit_detail", kwargs={"pk": layered_audit_a.pk})

    layered_audit_a.refresh_from_db()
    assert layered_audit_a.title == "Updated Supervisor LPA Walk"
    assert layered_audit_a.notes == "Torque calibration seals verified on all stations."

    assert AuditLog.objects.filter(
        tenant=layered_audit_a.tenant,
        action="update",
        object_repr__contains=layered_audit_a.number,
    ).exists()


def test_inprocessquality_view_layered_audit_edit_post_invalid(client, admin_user, layered_audit_a):
    """Verify invalid POST on LPA edit renders 200 with form errors."""
    client.force_login(admin_user)
    url = reverse("quality:layered_process_audit_edit", kwargs={"pk": layered_audit_a.pk})
    resp = client.post(url, {"title": ""})
    assert resp.status_code == 200
    assert resp.context["form"].errors


def test_inprocessquality_view_layered_audit_delete_success(client, admin_user, tenant_a):
    """Verify admin user can delete LPA via POST and is redirected to list."""
    to_delete = LayeredProcessAudit.objects.create(
        tenant=tenant_a,
        title="LPA to Delete",
        audit_layer="tier_1_operator_lead",
        focus_area="standard_work_wi",
        status="scheduled",
        work_center_code="WC-01",
        shift="Shift 1",
        scheduled_date=timezone.now().date(),
        total_questions_audited=5,
        questions_conforming=5,
        questions_non_conforming=0,
    )
    client.force_login(admin_user)
    url = reverse("quality:layered_process_audit_delete", kwargs={"pk": to_delete.pk})
    resp = client.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("quality:layered_process_audit_list")
    assert not LayeredProcessAudit.objects.filter(pk=to_delete.pk).exists()

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        action="delete",
        object_repr__contains=to_delete.number,
    ).exists()


def test_inprocessquality_view_layered_audit_delete_get_not_allowed(client, admin_user, layered_audit_a):
    """Verify GET on LPA delete returns 405 Method Not Allowed."""
    client.force_login(admin_user)
    url = reverse("quality:layered_process_audit_delete", kwargs={"pk": layered_audit_a.pk})
    resp = client.get(url)
    assert resp.status_code == 405


def test_inprocessquality_view_layered_audit_delete_non_admin_forbidden(client, member_user, layered_audit_a):
    """Verify non-admin user is rejected with 403 on LPA delete."""
    client.force_login(member_user)
    url = reverse("quality:layered_process_audit_delete", kwargs={"pk": layered_audit_a.pk})
    resp = client.post(url)
    assert resp.status_code == 403


def test_inprocessquality_view_layered_audit_export_csv(client, admin_user, layered_audit_a):
    """Verify LPA export returns CSV with correct headers and nosniff protection."""
    client.force_login(admin_user)
    url = reverse("quality:layered_process_audit_export_csv")
    resp = client.get(url)
    assert resp.status_code == 200
    assert "text/csv" in resp["Content-Type"]
    assert "layered_process_audits.csv" in resp["Content-Disposition"]
    assert resp["X-Content-Type-Options"] == "nosniff"

    content = resp.content.decode("utf-8")
    reader = csv.reader(io.StringIO(content))
    headers = next(reader)
    assert "Audit Number" in headers
    assert "Audit Layer" in headers
    assert "Compliance %" in headers
    rows = list(reader)
    assert any(layered_audit_a.number in row[0] for row in rows)

    assert AuditLog.objects.filter(
        tenant=layered_audit_a.tenant,
        action="export",
    ).exists()


# =============================================================================
# 5. SPC Dashboard View
# =============================================================================

def test_inprocessquality_view_spc_dashboard_get_and_context(
    client,
    admin_user,
    in_process_inspection_a,
    fai_a,
    parameter_log_a,
    layered_audit_a,
):
    """Verify SPC Dashboard GET returns 200 with all KPIs, recent excursions, and recent records."""
    # Ensure parameter log has an excursion to show in recent_excursions
    parameter_log_a.excursion_status = "out_of_control"
    parameter_log_a.save()

    client.force_login(admin_user)
    url = reverse("quality:spc_dashboard")
    resp = client.get(url)
    assert resp.status_code == 200

    context_keys = [
        "total_inspections",
        "fai_pending_release_count",
        "active_ooc_oos_count",
        "avg_lpa_compliance",
        "recent_inspections",
        "recent_fais",
        "recent_excursions",
        "recent_lpas",
    ]
    for key in context_keys:
        assert key in resp.context, f"Key '{key}' missing from SPC Dashboard context"

    assert resp.context["total_inspections"] >= 1
    assert resp.context["active_ooc_oos_count"] >= 1
    assert in_process_inspection_a in resp.context["recent_inspections"]
    assert fai_a in resp.context["recent_fais"]
    assert parameter_log_a in resp.context["recent_excursions"]
    assert layered_audit_a in resp.context["recent_lpas"]

    content = resp.content.decode()
    assert "Shop Floor Quality & SPC Control Dashboard" in content
    assert in_process_inspection_a.number in content


def test_inprocessquality_view_spc_dashboard_tenant_isolation(
    client,
    admin_user,
    in_process_inspection_b,
    fai_b,
    parameter_log_b,
    layered_audit_b,
):
    """Verify Tenant A's SPC Dashboard does not include Tenant B's data in KPIs or recent lists."""
    client.force_login(admin_user)
    url = reverse("quality:spc_dashboard")
    resp = client.get(url)
    assert resp.status_code == 200

    assert in_process_inspection_b not in resp.context["recent_inspections"]
    assert fai_b not in resp.context["recent_fais"]
    assert parameter_log_b not in resp.context["recent_excursions"]
    assert layered_audit_b not in resp.context["recent_lpas"]


# =============================================================================
# 6. Cross-Tenant Isolation & Unauthenticated Protection
# =============================================================================

def test_inprocessquality_view_cross_tenant_isolation_reads(
    client,
    admin_user,
    in_process_inspection_b,
    fai_b,
    parameter_log_b,
    layered_audit_b,
):
    """Verify Tenant A user cannot read Tenant B's records via detail views (404 returned)."""
    client.force_login(admin_user)

    # InProcessInspection
    resp_insp = client.get(reverse("quality:in_process_inspection_detail", kwargs={"pk": in_process_inspection_b.pk}))
    assert resp_insp.status_code == 404

    # FirstArticleInspection
    resp_fai = client.get(reverse("quality:first_article_inspection_detail", kwargs={"pk": fai_b.pk}))
    assert resp_fai.status_code == 404

    # ProcessParameterLog
    resp_log = client.get(reverse("quality:process_parameter_log_detail", kwargs={"pk": parameter_log_b.pk}))
    assert resp_log.status_code == 404

    # LayeredProcessAudit
    resp_lpa = client.get(reverse("quality:layered_process_audit_detail", kwargs={"pk": layered_audit_b.pk}))
    assert resp_lpa.status_code == 404


def test_inprocessquality_view_cross_tenant_isolation_mutations(
    client,
    admin_user,
    in_process_inspection_b,
    fai_b,
    parameter_log_b,
    layered_audit_b,
):
    """Verify Tenant A user cannot edit, delete, or release Tenant B's records (404 returned)."""
    client.force_login(admin_user)

    # InProcessInspection edit and delete
    resp_insp_edit = client.post(
        reverse("quality:in_process_inspection_edit", kwargs={"pk": in_process_inspection_b.pk}),
        {"title": "Hacked Title"},
    )
    assert resp_insp_edit.status_code == 404

    resp_insp_del = client.post(
        reverse("quality:in_process_inspection_delete", kwargs={"pk": in_process_inspection_b.pk})
    )
    assert resp_insp_del.status_code == 404

    # FAI edit, release, delete
    resp_fai_edit = client.post(
        reverse("quality:first_article_inspection_edit", kwargs={"pk": fai_b.pk}),
        {"title": "Hacked Title"},
    )
    assert resp_fai_edit.status_code == 404

    resp_fai_rel = client.post(
        reverse("quality:first_article_inspection_release", kwargs={"pk": fai_b.pk})
    )
    assert resp_fai_rel.status_code == 404

    resp_fai_del = client.post(
        reverse("quality:first_article_inspection_delete", kwargs={"pk": fai_b.pk})
    )
    assert resp_fai_del.status_code == 404

    # ProcessParameterLog edit and delete
    resp_log_edit = client.post(
        reverse("quality:process_parameter_log_edit", kwargs={"pk": parameter_log_b.pk}),
        {"parameter_name": "Hacked Name"},
    )
    assert resp_log_edit.status_code == 404

    resp_log_del = client.post(
        reverse("quality:process_parameter_log_delete", kwargs={"pk": parameter_log_b.pk})
    )
    assert resp_log_del.status_code == 404

    # LPA edit and delete
    resp_lpa_edit = client.post(
        reverse("quality:layered_process_audit_edit", kwargs={"pk": layered_audit_b.pk}),
        {"title": "Hacked Title"},
    )
    assert resp_lpa_edit.status_code == 404

    resp_lpa_del = client.post(
        reverse("quality:layered_process_audit_delete", kwargs={"pk": layered_audit_b.pk})
    )
    assert resp_lpa_del.status_code == 404


def test_inprocessquality_view_unauthenticated_redirects(
    client,
    in_process_inspection_a,
    fai_a,
    parameter_log_a,
    layered_audit_a,
):
    """Verify unauthenticated requests redirect to login across all views."""
    urls = [
        reverse("quality:in_process_inspection_list"),
        reverse("quality:in_process_inspection_create"),
        reverse("quality:in_process_inspection_detail", kwargs={"pk": in_process_inspection_a.pk}),
        reverse("quality:in_process_inspection_edit", kwargs={"pk": in_process_inspection_a.pk}),
        reverse("quality:in_process_inspection_delete", kwargs={"pk": in_process_inspection_a.pk}),
        reverse("quality:in_process_inspection_export_csv"),
        reverse("quality:first_article_inspection_list"),
        reverse("quality:first_article_inspection_create"),
        reverse("quality:first_article_inspection_detail", kwargs={"pk": fai_a.pk}),
        reverse("quality:first_article_inspection_edit", kwargs={"pk": fai_a.pk}),
        reverse("quality:first_article_inspection_release", kwargs={"pk": fai_a.pk}),
        reverse("quality:first_article_inspection_delete", kwargs={"pk": fai_a.pk}),
        reverse("quality:first_article_inspection_export_csv"),
        reverse("quality:process_parameter_log_list"),
        reverse("quality:process_parameter_log_create"),
        reverse("quality:process_parameter_log_detail", kwargs={"pk": parameter_log_a.pk}),
        reverse("quality:process_parameter_log_edit", kwargs={"pk": parameter_log_a.pk}),
        reverse("quality:process_parameter_log_delete", kwargs={"pk": parameter_log_a.pk}),
        reverse("quality:process_parameter_log_export_csv"),
        reverse("quality:layered_process_audit_list"),
        reverse("quality:layered_process_audit_create"),
        reverse("quality:layered_process_audit_detail", kwargs={"pk": layered_audit_a.pk}),
        reverse("quality:layered_process_audit_edit", kwargs={"pk": layered_audit_a.pk}),
        reverse("quality:layered_process_audit_delete", kwargs={"pk": layered_audit_a.pk}),
        reverse("quality:layered_process_audit_export_csv"),
        reverse("quality:spc_dashboard"),
    ]

    for url in urls:
        resp = client.get(url)
        assert resp.status_code == 302, f"URL '{url}' did not redirect unauthenticated client."
        assert "/accounts/login/" in resp.url or "login" in resp.url
