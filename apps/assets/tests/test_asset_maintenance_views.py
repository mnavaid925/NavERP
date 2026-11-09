"""Functional view and workflow action tests for Module 11.5 Maintenance & Repair."""
from datetime import timedelta
from decimal import Decimal
import pytest
from django.urls import reverse
from django.utils import timezone

from apps.assets.models import (
    AssetMaintenanceRequest,
    AssetMaintenanceSchedule,
    AssetServiceContract,
    AssetMaintenanceLog,
)


@pytest.mark.django_db
def test_asset_maintenance_request_list_view(client, admin_user, maintenance_request_a):
    client.force_login(admin_user)
    resp = client.get(reverse("assets:asset_maintenance_request_list"))
    assert resp.status_code == 200
    assert "maintenance_requests" in resp.context
    assert maintenance_request_a.number in resp.content.decode()


@pytest.mark.django_db
def test_asset_maintenance_request_detail_view(client, admin_user, maintenance_request_a):
    client.force_login(admin_user)
    resp = client.get(reverse("assets:asset_maintenance_request_detail", args=[maintenance_request_a.pk]))
    assert resp.status_code == 200
    assert resp.context["maintenance_request"] == maintenance_request_a
    assert maintenance_request_a.number in resp.content.decode()


@pytest.mark.django_db
def test_asset_maintenance_request_create_view(client, admin_user, tenant_a, fixed_asset_a):
    client.force_login(admin_user)
    resp = client.get(reverse("assets:asset_maintenance_request_create"))
    assert resp.status_code == 200

    data = {
        "title": "CNC Spindle Bearing Noise Inspection",
        "fixed_asset": str(fixed_asset_a.pk),
        "request_type": "breakdown_repair",
        "urgency": "high",
        "symptom_description": "Audible grinding during rapid traverse.",
    }
    post_resp = client.post(reverse("assets:asset_maintenance_request_create"), data=data)
    assert post_resp.status_code == 302
    created = AssetMaintenanceRequest.objects.filter(tenant=tenant_a, title=data["title"]).first()
    assert created is not None
    assert created.tenant == tenant_a
    assert created.requester == admin_user


@pytest.mark.django_db
def test_asset_maintenance_request_edit_view(client, admin_user, maintenance_request_a):
    client.force_login(admin_user)
    resp = client.get(reverse("assets:asset_maintenance_request_edit", args=[maintenance_request_a.pk]))
    assert resp.status_code == 200

    data = {
        "title": "Updated Spindle Vibration Details",
        "fixed_asset": str(maintenance_request_a.fixed_asset.pk),
        "department": str(maintenance_request_a.department.pk) if maintenance_request_a.department else "",
        "request_type": maintenance_request_a.request_type,
        "urgency": "critical",
        "symptom_description": maintenance_request_a.symptom_description,
    }
    post_resp = client.post(reverse("assets:asset_maintenance_request_edit", args=[maintenance_request_a.pk]), data=data)
    assert post_resp.status_code == 302
    maintenance_request_a.refresh_from_db()
    assert maintenance_request_a.title == "Updated Spindle Vibration Details"
    assert maintenance_request_a.urgency == "critical"


@pytest.mark.django_db
def test_asset_maintenance_request_triage_action(client, admin_user, maintenance_request_a):
    client.force_login(admin_user)
    resp = client.post(
        reverse("assets:asset_maintenance_request_triage", args=[maintenance_request_a.pk]),
        data={"urgency": "critical", "triage_notes": "Immediate safety lockout required."},
    )
    assert resp.status_code == 302
    maintenance_request_a.refresh_from_db()
    assert maintenance_request_a.status == "triaged"
    assert maintenance_request_a.urgency == "critical"


@pytest.mark.django_db
def test_asset_maintenance_request_dispatch_action(client, admin_user, maintenance_request_a, vendor_party_a, service_contract_a):
    client.force_login(admin_user)
    resp = client.post(
        reverse("assets:asset_maintenance_request_dispatch", args=[maintenance_request_a.pk]),
        data={
            "assigned_technician": str(admin_user.pk),
            "assigned_vendor": str(vendor_party_a.pk),
            "service_contract": str(service_contract_a.pk),
        },
    )
    assert resp.status_code == 302
    maintenance_request_a.refresh_from_db()
    assert maintenance_request_a.status == "assigned"
    assert maintenance_request_a.service_contract == service_contract_a


@pytest.mark.django_db
def test_asset_maintenance_request_start_action(client, admin_user, maintenance_request_a):
    client.force_login(admin_user)
    maintenance_request_a.status = "assigned"
    maintenance_request_a.save()
    resp = client.post(reverse("assets:asset_maintenance_request_start", args=[maintenance_request_a.pk]))
    assert resp.status_code == 302
    maintenance_request_a.refresh_from_db()
    assert maintenance_request_a.status == "in_progress"


@pytest.mark.django_db
def test_asset_maintenance_request_resolve_and_close_actions(client, admin_user, maintenance_request_a):
    client.force_login(admin_user)
    maintenance_request_a.status = "in_progress"
    maintenance_request_a.save()
    resp = client.post(
        reverse("assets:asset_maintenance_request_resolve", args=[maintenance_request_a.pk]),
        data={"resolution_summary": "Replaced thermal fuse and verified spindle rotational speed."},
    )
    assert resp.status_code == 302
    maintenance_request_a.refresh_from_db()
    assert maintenance_request_a.status == "resolved"

    close_resp = client.post(reverse("assets:asset_maintenance_request_close", args=[maintenance_request_a.pk]))
    assert close_resp.status_code == 302
    maintenance_request_a.refresh_from_db()
    assert maintenance_request_a.status == "closed"


@pytest.mark.django_db
def test_asset_maintenance_request_reject_action(client, admin_user, maintenance_request_a):
    client.force_login(admin_user)
    resp = client.post(
        reverse("assets:asset_maintenance_request_reject", args=[maintenance_request_a.pk]),
        data={"rejection_reason": "Not an equipment failure."},
    )
    assert resp.status_code == 302
    maintenance_request_a.refresh_from_db()
    assert maintenance_request_a.status == "rejected"


@pytest.mark.django_db
def test_asset_maintenance_request_delete_action(client, admin_user, maintenance_request_a):
    client.force_login(admin_user)
    req_pk = maintenance_request_a.pk
    resp = client.post(reverse("assets:asset_maintenance_request_delete", args=[req_pk]))
    assert resp.status_code == 302
    assert not AssetMaintenanceRequest.objects.filter(pk=req_pk).exists()


@pytest.mark.django_db
def test_asset_maintenance_schedule_list_view(client, admin_user, maintenance_schedule_a):
    client.force_login(admin_user)
    resp = client.get(reverse("assets:asset_maintenance_schedule_list"))
    assert resp.status_code == 200
    assert "maintenance_schedules" in resp.context
    assert maintenance_schedule_a.number in resp.content.decode()


@pytest.mark.django_db
def test_asset_maintenance_schedule_detail_view(client, admin_user, maintenance_schedule_a):
    client.force_login(admin_user)
    resp = client.get(reverse("assets:asset_maintenance_schedule_detail", args=[maintenance_schedule_a.pk]))
    assert resp.status_code == 200
    assert resp.context["maintenance_schedule"] == maintenance_schedule_a
    assert "service_checklist_items" in resp.context


@pytest.mark.django_db
def test_asset_maintenance_schedule_create_view(client, admin_user, tenant_a, fixed_asset_a):
    client.force_login(admin_user)
    resp = client.get(reverse("assets:asset_maintenance_schedule_create"))
    assert resp.status_code == 200

    data = {
        "name": "Monthly Compressor Desiccant Replacement",
        "schedule_type": "time_based",
        "fixed_asset": str(fixed_asset_a.pk),
        "frequency_interval": 1,
        "frequency_unit": "months",
        "lead_time_days": 3,
        "is_mandatory": False,
        "is_active": True,
        "service_checklist": "1. Verify desiccant color\n2. Swap canister",
    }
    post_resp = client.post(reverse("assets:asset_maintenance_schedule_create"), data=data)
    assert post_resp.status_code == 302
    created = AssetMaintenanceSchedule.objects.filter(tenant=tenant_a, name=data["name"]).first()
    assert created is not None
    assert created.next_due_date is not None


@pytest.mark.django_db
def test_asset_maintenance_schedule_toggle_and_spawn_actions(client, admin_user, maintenance_schedule_a):
    client.force_login(admin_user)
    resp = client.post(reverse("assets:asset_maintenance_schedule_pause", args=[maintenance_schedule_a.pk]))
    assert resp.status_code == 302
    maintenance_schedule_a.refresh_from_db()
    assert maintenance_schedule_a.status == "paused"

    resp_act = client.post(reverse("assets:asset_maintenance_schedule_activate", args=[maintenance_schedule_a.pk]))
    assert resp_act.status_code == 302
    maintenance_schedule_a.refresh_from_db()
    assert maintenance_schedule_a.status == "active"

    spawn_resp = client.post(reverse("assets:asset_maintenance_schedule_generate_request", args=[maintenance_schedule_a.pk]))
    assert spawn_resp.status_code == 302
    spawned = AssetMaintenanceRequest.objects.filter(tenant=maintenance_schedule_a.tenant, title__icontains=maintenance_schedule_a.name).first()
    assert spawned is not None


@pytest.mark.django_db
def test_asset_maintenance_schedule_record_completion_action(client, admin_user, maintenance_schedule_a):
    client.force_login(admin_user)
    today = timezone.now().date()
    data = {
        "completion_date": today.strftime("%Y-%m-%d"),
        "completion_meter": "1450.00",
        "notes": "PM completed per routine checklist.",
    }
    resp = client.post(reverse("assets:asset_maintenance_schedule_record_completion", args=[maintenance_schedule_a.pk]), data=data)
    assert resp.status_code == 302
    maintenance_schedule_a.refresh_from_db()
    assert maintenance_schedule_a.last_service_date == today
    assert "PM completed per routine" in maintenance_schedule_a.notes


@pytest.mark.django_db
def test_asset_service_contract_list_and_detail_views(client, admin_user, service_contract_a):
    client.force_login(admin_user)
    resp_list = client.get(reverse("assets:asset_service_contract_list"))
    assert resp_list.status_code == 200
    assert "service_contracts" in resp_list.context

    resp_detail = client.get(reverse("assets:asset_service_contract_detail", args=[service_contract_a.pk]))
    assert resp_detail.status_code == 200
    assert resp_detail.context["service_contract"] == service_contract_a


@pytest.mark.django_db
def test_asset_service_contract_record_visit_and_renew_actions(client, admin_user, service_contract_a):
    client.force_login(admin_user)
    resp = client.post(reverse("assets:asset_service_contract_record_visit", args=[service_contract_a.pk]))
    assert resp.status_code == 302
    service_contract_a.refresh_from_db()
    assert service_contract_a.pm_visits_completed == 1

    future_date = (timezone.now().date() + timedelta(days=730)).strftime("%Y-%m-%d")
    renew_resp = client.post(
        reverse("assets:asset_service_contract_renew", args=[service_contract_a.pk]),
        data={"new_end_date": future_date, "new_contract_value": "16500.00", "notes": "Two-year renewal with negotiated terms."},
    )
    assert renew_resp.status_code == 302
    service_contract_a.refresh_from_db()
    assert service_contract_a.pm_visits_completed == 0
    assert "Two-year renewal" in service_contract_a.notes


@pytest.mark.django_db
def test_asset_maintenance_log_lifecycle_views(client, admin_user, maintenance_log_a):
    client.force_login(admin_user)
    resp_list = client.get(reverse("assets:asset_maintenance_log_list"))
    assert resp_list.status_code == 200

    resp_detail = client.get(reverse("assets:asset_maintenance_log_detail", args=[maintenance_log_a.pk]))
    assert resp_detail.status_code == 200

    submit_resp = client.post(reverse("assets:asset_maintenance_log_submit_review", args=[maintenance_log_a.pk]))
    assert submit_resp.status_code == 302
    maintenance_log_a.refresh_from_db()
    assert maintenance_log_a.status == "in_review"

    approve_resp = client.post(reverse("assets:asset_maintenance_log_approve", args=[maintenance_log_a.pk]))
    assert approve_resp.status_code == 302
    maintenance_log_a.refresh_from_db()
    assert maintenance_log_a.status == "approved"

    post_resp = client.post(reverse("assets:asset_maintenance_log_post_gl", args=[maintenance_log_a.pk]))
    assert post_resp.status_code == 302
    maintenance_log_a.refresh_from_db()
    assert maintenance_log_a.status == "posted"
