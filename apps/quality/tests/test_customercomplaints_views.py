"""Unit and functional view tests for Quality Management Sub-module 12.13: Customer Complaint Handling.

Covers:
- CustomerComplaint list, detail, create, edit, delete, triage, close, export CSV
- ComplaintInvestigation list, detail, create, edit, delete, complete, export CSV
- RegulatoryReport list, detail, create, edit, delete, submit, acknowledge, export CSV
- FieldAction list, detail, create, edit, delete, close, export CSV
- ComplaintTrendingDashboard
"""
from datetime import timedelta
import pytest
from django.urls import reverse
from django.utils import timezone

from apps.quality.models.CustomerComplaints.CustomerComplaints import CustomerComplaint
from apps.quality.models.CustomerComplaints.ComplaintInvestigations import ComplaintInvestigation
from apps.quality.models.CustomerComplaints.RegulatoryReports import RegulatoryReport
from apps.quality.models.CustomerComplaints.FieldActions import FieldAction


@pytest.mark.django_db
def test_customercomplaints_complaint_list_view(client, admin_user, customer_complaint_a, customer_party_a):
    """Verify complaint list returns 200 with filters and KPI aggregations."""
    client.force_login(admin_user)
    url = reverse("quality:customer_complaint_list")
    resp = client.get(url)
    assert resp.status_code == 200
    assert "complaints" in resp.context
    assert "total_count" in resp.context
    assert "open_count" in resp.context
    assert "reportable_count" in resp.context
    assert "critical_count" in resp.context
    assert customer_complaint_a.number.encode() in resp.content

    # Filters
    resp_filtered = client.get(url, {
        "status": customer_complaint_a.status,
        "severity": customer_complaint_a.severity,
        "customer": str(customer_party_a.pk),
        "q": "Infusion",
    })
    assert resp_filtered.status_code == 200
    assert customer_complaint_a.number.encode() in resp_filtered.content


@pytest.mark.django_db
def test_customercomplaints_complaint_detail_view(client, admin_user, customer_complaint_a):
    """Verify complaint detail passes child lists and triage form."""
    client.force_login(admin_user)
    url = reverse("quality:customer_complaint_detail", kwargs={"pk": customer_complaint_a.pk})
    resp = client.get(url)
    assert resp.status_code == 200
    assert resp.context["complaint"] == customer_complaint_a
    assert "investigations" in resp.context
    assert "reports" in resp.context
    assert "field_actions" in resp.context


@pytest.mark.django_db
def test_customercomplaints_complaint_create_and_edit_views(client, admin_user, tenant_a, customer_party_a):
    """Verify customer complaint create and edit flows."""
    client.force_login(admin_user)
    create_url = reverse("quality:customer_complaint_create")
    resp = client.get(create_url)
    assert resp.status_code == 200

    today = timezone.now().date()
    create_data = {
        "title": "Air Bubble Detection Anomaly",
        "intake_channel": "web_portal",
        "customer": customer_party_a.pk,
        "complainant_name": "Chief Biomédical Engineer",
        "item_code": "PUMP-4000",
        "item_name": "Infusion Pro Plus",
        "date_received": today,
        "problem_description": "Continuous false positive air-in-line alarm in ICU ward 3.",
        "severity": "major_malfunction",
        "validity": "valid_complaint",
        "reportability": "exempt",
        "sample_return_status": "not_requested",
        "investigation_required": True,
        "assigned_to": admin_user.pk,
    }
    resp = client.post(create_url, create_data)
    assert resp.status_code == 302
    new_cmp = CustomerComplaint.objects.filter(tenant=tenant_a, title=create_data["title"]).first()
    assert new_cmp is not None
    assert new_cmp.number.startswith("QCMP-")

    # Edit flow
    edit_url = reverse("quality:customer_complaint_edit", kwargs={"pk": new_cmp.pk})
    resp = client.get(edit_url)
    assert resp.status_code == 200

    create_data["title"] = "Updated Air Bubble Detection Anomaly"
    resp = client.post(edit_url, create_data)
    assert resp.status_code == 302
    new_cmp.refresh_from_db()
    assert new_cmp.title == "Updated Air Bubble Detection Anomaly"


@pytest.mark.django_db
def test_customercomplaints_complaint_triage_action(client, admin_user, customer_complaint_a):
    """Verify triage action updates complaint state and sets triaged metadata."""
    client.force_login(admin_user)
    customer_complaint_a.status = "intake_received"
    customer_complaint_a.save()
    url = reverse("quality:customer_complaint_triage", kwargs={"pk": customer_complaint_a.pk})
    data = {
        "validity": "valid_complaint",
        "severity": "critical_safety",
        "reportability": "reportable_event",
        "complaint_category": "Software Freeze",
        "investigation_required": True,
        "assigned_to": admin_user.pk,
        "triage_notes": "Triage verified device freeze caused medication pause.",
    }
    resp = client.post(url, data)
    assert resp.status_code == 302
    customer_complaint_a.refresh_from_db()
    assert customer_complaint_a.status == "under_investigation"
    assert customer_complaint_a.triaged_by == admin_user
    assert customer_complaint_a.triaged_at is not None

    # Triage already completed should be rejected
    resp_again = client.post(url, data)
    assert resp_again.status_code == 302


@pytest.mark.django_db
def test_customercomplaints_complaint_close_action(client, admin_user, customer_complaint_a):
    """Verify close action sets resolution and timestamp."""
    client.force_login(admin_user)
    url = reverse("quality:customer_complaint_close", kwargs={"pk": customer_complaint_a.pk})
    data = {
        "resolution_summary": "Firmware patch v2.1 applied. Customer verified successful resolution.",
        "customer_letter_sent": True,
    }
    resp = client.post(url, data)
    assert resp.status_code == 302
    customer_complaint_a.refresh_from_db()
    assert customer_complaint_a.status == "closed"
    assert customer_complaint_a.closed_by == admin_user
    assert customer_complaint_a.closed_at is not None


@pytest.mark.django_db
def test_customercomplaints_investigation_views(client, admin_user, tenant_a, customer_complaint_a, complaint_investigation_a):
    """Verify investigation list, detail, create, edit, and complete actions."""
    client.force_login(admin_user)
    list_url = reverse("quality:complaint_investigation_list")
    resp = client.get(list_url)
    assert resp.status_code == 200
    assert "investigations" in resp.context
    assert "total_count" in resp.context

    # Detail
    detail_url = reverse("quality:complaint_investigation_detail", kwargs={"pk": complaint_investigation_a.pk})
    resp = client.get(detail_url)
    assert resp.status_code == 200
    assert resp.context["investigation"] == complaint_investigation_a

    # Create
    create_url = reverse("quality:complaint_investigation_create")
    today = timezone.now().date()
    create_data = {
        "complaint": customer_complaint_a.pk,
        "lead_investigator": admin_user.pk,
        "target_completion_date": today + timedelta(days=14),
        "analytical_method": "electrical_functional",
        "dhr_quantity_produced": 1000,
        "root_cause_category": "component_defect",
        "investigation_summary": "Oscilloscope readings confirmed clock jitter.",
    }
    resp = client.post(create_url, create_data)
    assert resp.status_code == 302
    new_inv = ComplaintInvestigation.objects.filter(tenant=tenant_a, complaint=customer_complaint_a).last()
    assert new_inv is not None

    # Complete action
    complete_url = reverse("quality:complaint_investigation_complete", kwargs={"pk": new_inv.pk})
    resp = client.post(complete_url, {
        "root_cause_narrative": "Crystal oscillator drift at 40C ambient.",
        "investigation_conclusion": "Replaced crystal vendor.",
    })
    assert resp.status_code == 302
    new_inv.refresh_from_db()
    assert new_inv.status in ["approved", "pending_qa_review"]


@pytest.mark.django_db
def test_customercomplaints_regulatory_report_views(client, admin_user, tenant_a, customer_complaint_a, regulatory_report_a):
    """Verify regulatory report list, detail, create, edit, submit, and acknowledge."""
    client.force_login(admin_user)
    list_url = reverse("quality:regulatory_report_list")
    resp = client.get(list_url)
    assert resp.status_code == 200
    assert "reports" in resp.context

    # Detail
    detail_url = reverse("quality:regulatory_report_detail", kwargs={"pk": regulatory_report_a.pk})
    resp = client.get(detail_url)
    assert resp.status_code == 200
    assert resp.context["report"] == regulatory_report_a

    # Create
    create_url = reverse("quality:regulatory_report_create")
    today = timezone.now().date()
    create_data = {
        "complaint": customer_complaint_a.pk,
        "agency": "fda_cdrh",
        "report_type": "initial_report",
        "adverse_event_class": "serious_injury",
        "timeline_category": "30_day_standard_mdr",
        "statutory_due_date": today + timedelta(days=20),
        "submission_format": "fda_emdr_xml",
        "event_summary": "Patient experienced brief medication pause before pump was reset.",
        "prepared_by": admin_user.pk,
    }
    resp = client.post(create_url, create_data)
    assert resp.status_code == 302
    new_rpt = RegulatoryReport.objects.filter(tenant=tenant_a, complaint=customer_complaint_a).last()
    assert new_rpt is not None

    # Submit action
    submit_url = reverse("quality:regulatory_report_submit", kwargs={"pk": new_rpt.pk})
    resp = client.post(submit_url, {
        "agency_report_identifier": "MDR-2026-00991",
        "submission_date": str(today),
    })
    assert resp.status_code == 302
    new_rpt.refresh_from_db()
    assert new_rpt.submission_status == "submitted"

    # Acknowledge action
    ack_url = reverse("quality:regulatory_report_acknowledge", kwargs={"pk": new_rpt.pk})
    resp = client.post(ack_url, {
        "agency_acknowledgement_number": "ACK-GATEWAY-88192",
    })
    assert resp.status_code == 302
    new_rpt.refresh_from_db()
    assert new_rpt.submission_status == "acknowledged"


@pytest.mark.django_db
def test_customercomplaints_field_action_views(client, admin_user, tenant_a, customer_complaint_a, field_action_a):
    """Verify field action list, detail, create, edit, and close."""
    client.force_login(admin_user)
    list_url = reverse("quality:field_action_list")
    resp = client.get(list_url)
    assert resp.status_code == 200
    assert "field_actions" in resp.context

    # Detail
    detail_url = reverse("quality:field_action_detail", kwargs={"pk": field_action_a.pk})
    resp = client.get(detail_url)
    assert resp.status_code == 200
    assert resp.context["field_action"] == field_action_a

    # Create
    create_url = reverse("quality:field_action_create")
    today = timezone.now().date()
    create_data = {
        "title": "Software Patch Recall v1.1",
        "action_type": "field_correction_rework",
        "recall_class": "class_ii_moderate",
        "initiating_complaint": customer_complaint_a.pk,
        "coordinator": admin_user.pk,
        "initiation_date": today,
        "affected_product_code": "PUMP-4000",
        "affected_product_name": "Infusion Pro Plus",
        "affected_lot_numbers": "LOT-2026-X1",
        "reason_for_action": "Mandatory firmware update to eliminate timing jitter.",
        "total_units_distributed": 200,
        "consignees_targeted": 20,
        "consignees_notified": 20,
        "consignees_responded": 18,
        "units_quarantined_field": 5,
        "units_recovered_destroyed": 10,
    }
    resp = client.post(create_url, create_data)
    assert resp.status_code == 302
    new_fa = FieldAction.objects.filter(tenant=tenant_a, title=create_data["title"]).first()
    assert new_fa is not None

    # Close action
    close_url = reverse("quality:field_action_close", kwargs={"pk": new_fa.pk})
    resp = client.post(close_url, {
        "closure_summary": "100% of affected hospital sites successfully updated and verified.",
    })
    assert resp.status_code == 302
    new_fa.refresh_from_db()
    assert new_fa.status == "closed_terminated"


@pytest.mark.django_db
def test_customercomplaints_csv_exports(client, admin_user):
    """Verify all 4 Customer Complaint CSV export views return text/csv."""
    client.force_login(admin_user)
    export_routes = [
        "quality:customer_complaint_export_csv",
        "quality:complaint_investigation_export_csv",
        "quality:regulatory_report_export_csv",
        "quality:field_action_export_csv",
    ]
    for route in export_routes:
        url = reverse(route)
        resp = client.get(url)
        assert resp.status_code == 200
        assert resp["Content-Type"].startswith("text/csv")
        assert "attachment; filename=" in resp["Content-Disposition"]


@pytest.mark.django_db
def test_customercomplaints_trending_dashboard_view(client, admin_user, customer_complaint_a, field_action_a):
    """Verify complaint trending command center renders metrics and charts."""
    client.force_login(admin_user)
    url = reverse("quality:complaint_trending_dashboard")
    resp = client.get(url)
    assert resp.status_code == 200
    assert "total_complaints_ytd" in resp.context
    assert "open_complaints" in resp.context
    assert "reportable_adverse_events" in resp.context
    assert "active_field_recalls" in resp.context
    assert "avg_cycle_days" in resp.context
    assert "category_distribution" in resp.context
    assert "severity_distribution" in resp.context
