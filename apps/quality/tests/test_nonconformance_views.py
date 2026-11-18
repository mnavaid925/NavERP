"""View tests for Sub-module 12.5 Non-Conformance & Deviation Management."""
from decimal import Decimal
import pytest
from django.urls import reverse
from django.utils import timezone

from apps.core.models import AuditLog
from apps.quality.models import (
    NonConformanceReport,
    QuarantineContainment,
    MrbDisposition,
    ProcessDeviation,
)


@pytest.mark.django_db
def test_nonconformance_ncr_list_view_and_filters(client, admin_user, ncr_a):
    client.force_login(admin_user)
    url = reverse("quality:non_conformance_report_list")
    resp = client.get(url)
    assert resp.status_code == 200
    assert "non_conformance_reports" in resp.context
    assert "category_choices" in resp.context
    assert "status_choices" in resp.context
    assert ncr_a.number in resp.content.decode()

    # Filter by category
    resp_filtered = client.get(url, {"category": "material"})
    assert resp_filtered.status_code == 200
    assert ncr_a.number in resp_filtered.content.decode()

    # Filter with junk parameters (Lesson L11)
    resp_junk = client.get(url, {"category": "invalid_junk", "page": "xyz"})
    assert resp_junk.status_code == 200


@pytest.mark.django_db
def test_nonconformance_ncr_detail_view_and_null_closed_guard(client, admin_user, ncr_a):
    client.force_login(admin_user)
    # Set closure notes with closed_by = None (C3 regression check)
    ncr_a.closure_notes = "Closure notes recorded without closed_by attribution."
    ncr_a.closed_by = None
    ncr_a.save()

    url = reverse("quality:non_conformance_report_detail", args=[ncr_a.pk])
    resp = client.get(url)
    assert resp.status_code == 200
    assert resp.context["non_conformance_report"] == ncr_a
    assert "containment_records" in resp.context
    assert "mrb_dispositions" in resp.context
    assert "process_deviations" in resp.context
    assert ncr_a.number in resp.content.decode()


@pytest.mark.django_db
def test_nonconformance_ncr_create_view_and_closed_attribution(client, admin_user, tenant_a, quality_department):
    client.force_login(admin_user)
    url = reverse("quality:non_conformance_report_create")
    resp_get = client.get(url)
    assert resp_get.status_code == 200

    data = {
        "title": "Directly Closed Defect Batch",
        "description": "Resolved immediately at intake.",
        "source_type": "in_process",
        "category": "process",
        "severity": "minor",
        "status": "closed",  # M1: closed on create should populate closed_at/by
        "department": quality_department.pk,
        "initiator": admin_user.pk,
        "owner": admin_user.pk,
        "quantity_inspected": "100.00",
        "quantity_nonconforming": "2.00",
        "estimated_financial_loss": "150.00",
        "closure_notes": "Immediate rework completed.",
    }
    resp_post = client.post(url, data)
    assert resp_post.status_code == 302
    created_ncr = NonConformanceReport.objects.filter(tenant=tenant_a, title="Directly Closed Defect Batch").first()
    assert created_ncr is not None
    assert created_ncr.status == "closed"
    assert created_ncr.closed_by == admin_user
    assert created_ncr.closed_at is not None


@pytest.mark.django_db
def test_nonconformance_ncr_delete_lifecycle_guards(client, admin_user, ncr_a, quarantine_a):
    client.force_login(admin_user)
    url = reverse("quality:non_conformance_report_delete", args=[ncr_a.pk])

    # C5: Reject delete when active quarantine hold exists
    resp_hold = client.post(url)
    assert resp_hold.status_code == 302
    assert NonConformanceReport.objects.filter(pk=ncr_a.pk).exists()

    # Release quarantine hold, close NCR
    quarantine_a.status = "released"
    quarantine_a.save()
    ncr_a.status = "closed"
    ncr_a.save()

    # C5: Reject delete when NCR is closed
    resp_closed = client.post(url)
    assert resp_closed.status_code == 302
    assert NonConformanceReport.objects.filter(pk=ncr_a.pk).exists()

    # Set back to draft without active holds: now deletion succeeds
    ncr_a.status = "draft"
    ncr_a.save()
    resp_del = client.post(url)
    assert resp_del.status_code == 302
    assert not NonConformanceReport.objects.filter(pk=ncr_a.pk).exists()


@pytest.mark.django_db
def test_nonconformance_ncr_export_csv_view(client, admin_user, ncr_a):
    client.force_login(admin_user)
    url = reverse("quality:non_conformance_report_export_csv")
    resp = client.get(url)
    assert resp.status_code == 200
    assert "text/csv" in resp["Content-Type"]
    assert resp["X-Content-Type-Options"] == "nosniff"
    assert ncr_a.number in resp.content.decode()


@pytest.mark.django_db
def test_nonconformance_quarantine_views_and_delete_guard(client, admin_user, quarantine_a):
    client.force_login(admin_user)
    # List view
    list_url = reverse("quality:quarantine_containment_list")
    resp_list = client.get(list_url)
    assert resp_list.status_code == 200
    assert quarantine_a.number in resp_list.content.decode()

    # Detail view
    det_url = reverse("quality:quarantine_containment_detail", args=[quarantine_a.pk])
    resp_det = client.get(det_url)
    assert resp_det.status_code == 200
    assert quarantine_a.number in resp_det.content.decode()

    # I5: Active quarantine cannot be deleted
    del_url = reverse("quality:quarantine_containment_delete", args=[quarantine_a.pk])
    resp_del_active = client.post(del_url)
    assert resp_del_active.status_code == 302
    assert QuarantineContainment.objects.filter(pk=quarantine_a.pk).exists()

    # Partially released or draft can be deleted; released/disposed also guarded
    quarantine_a.status = "partially_released"
    quarantine_a.save()
    resp_del_ok = client.post(del_url, {"next": list_url})
    assert resp_del_ok.status_code == 302
    assert not QuarantineContainment.objects.filter(pk=quarantine_a.pk).exists()


@pytest.mark.django_db
def test_nonconformance_mrb_views_and_audit_action_length(client, admin_user, tenant_a, ncr_a):
    client.force_login(admin_user)
    # C1: MRB Create must write AuditLog action <= 10 characters
    create_url = reverse("quality:mrb_disposition_create")
    data = {
        "ncr": ncr_a.pk,
        "title": "Audit Log Test Disposition",
        "disposition_decision": "scrap",
        "technical_justification": "Defect beyond recovery.",
        "mrb_chair": admin_user.pk,
        "scrap_cost": "150.00",
        "rework_labor_cost": "0.00",
        "vendor_chargeback_cost": "0.00",
        "status": "draft",
    }
    resp = client.post(create_url, data)
    assert resp.status_code == 302
    created_mrb = MrbDisposition.objects.filter(tenant=tenant_a, title="Audit Log Test Disposition").first()
    assert created_mrb is not None

    audit_entry = AuditLog.objects.filter(tenant=tenant_a, object_id=str(created_mrb.pk)).first()
    assert audit_entry is not None
    assert len(audit_entry.action) <= 10
    assert audit_entry.action == "create"

    # I5: Delete approved MRB rejected
    created_mrb.status = "approved"
    created_mrb.save()
    del_url = reverse("quality:mrb_disposition_delete", args=[created_mrb.pk])
    resp_del = client.post(del_url)
    assert resp_del.status_code == 302
    assert MrbDisposition.objects.filter(pk=created_mrb.pk).exists()


@pytest.mark.django_db
def test_nonconformance_process_deviation_detail_unapproved_guard(client, admin_user, process_deviation_a):
    client.force_login(admin_user)
    # C2: Unapproved deviation (approved_by = None) renders 200 without VariableDoesNotExist crash
    process_deviation_a.approved_by = None
    process_deviation_a.status = "draft"
    process_deviation_a.save()

    det_url = reverse("quality:process_deviation_detail", args=[process_deviation_a.pk])
    resp = client.get(det_url)
    assert resp.status_code == 200
    assert "Pending Approval" in resp.content.decode()
    assert process_deviation_a.number in resp.content.decode()


@pytest.mark.django_db
def test_nonconformance_analytics_dashboard_view(client, admin_user, ncr_a, mrb_a, quarantine_a):
    client.force_login(admin_user)
    url = reverse("quality:ncr_analytics_dashboard")
    resp = client.get(url)
    assert resp.status_code == 200
    assert "total_ncrs" in resp.context
    assert "severity_breakdown" in resp.context
    assert "category_breakdown" in resp.context
    assert "source_breakdown" in resp.context
    assert resp.context["total_ncrs"] >= 1
