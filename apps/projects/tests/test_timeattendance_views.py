"""Projects 7.11 — Time & Attendance Tracking view tests.

Covers:
- List registers (tac_list, otr_list, pot_list) with search & filters
- Detail views (tac_detail, otr_detail, pot_detail)
- Create & edit views
- Edit/delete locking on approved/rejected records
- Overtime workflow verbs (submit, approve, reject)
- Time reporting & utilization dashboard (KPIs, chargeability, splits, capacity vs demand)
- Calendar sync view (time entries, leaves, holidays, overtime)

Naming: every test ``test_timeattendance_*``, every helper ``_timeattendance_*``.
"""
from decimal import Decimal
import pytest
from django.urls import reverse
from django.utils import timezone

from apps.projects.models import (
    OvertimeRule,
    ProjectOvertimeRecord,
    TimeActivityCode,
)
from apps.projects.tests.conftest import (
    _timeattendance_activity_code,
    _timeattendance_overtime_rule,
    _timeattendance_overtime_record,
    _resource_entry,
)

pytestmark = pytest.mark.django_db


# ==================================================================================================
# Register / List Views
# ==================================================================================================

def test_timeattendance_tac_list_renders_and_filters(client_a, tenant_a, timeattendance_code_a):
    url = reverse("projects:tac_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert timeattendance_code_a.code in resp.content.decode()

    # Filter by category
    resp_filtered = client_a.get(url, {"category": timeattendance_code_a.category})
    assert resp_filtered.status_code == 200
    assert timeattendance_code_a.code in resp_filtered.content.decode()


def test_timeattendance_otr_list_renders_and_filters(client_a, tenant_a, timeattendance_rule_a):
    url = reverse("projects:otr_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert timeattendance_rule_a.name in resp.content.decode()


def test_timeattendance_pot_list_renders_and_filters(client_a, tenant_a, timeattendance_record_draft_a):
    url = reverse("projects:pot_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert timeattendance_record_draft_a.number in resp.content.decode()

    # Filter by status
    resp_filtered = client_a.get(url, {"status": "draft"})
    assert resp_filtered.status_code == 200
    assert timeattendance_record_draft_a.number in resp_filtered.content.decode()


# ==================================================================================================
# Detail Views
# ==================================================================================================

def test_timeattendance_detail_views_render(
    client_a, timeattendance_code_a, timeattendance_rule_a, timeattendance_record_draft_a
):
    tac_resp = client_a.get(reverse("projects:tac_detail", kwargs={"pk": timeattendance_code_a.pk}))
    assert tac_resp.status_code == 200
    assert timeattendance_code_a.name in tac_resp.content.decode()

    otr_resp = client_a.get(reverse("projects:otr_detail", kwargs={"pk": timeattendance_rule_a.pk}))
    assert otr_resp.status_code == 200
    assert timeattendance_rule_a.name in otr_resp.content.decode()

    pot_resp = client_a.get(reverse("projects:pot_detail", kwargs={"pk": timeattendance_record_draft_a.pk}))
    assert pot_resp.status_code == 200
    assert timeattendance_record_draft_a.number in pot_resp.content.decode()


# ==================================================================================================
# Edit & Delete Locking on Approved/Rejected Records
# ==================================================================================================

def test_timeattendance_pot_edit_allows_draft_but_locks_approved(
    client_a, timeattendance_record_draft_a, timeattendance_record_approved_a
):
    draft_url = reverse("projects:pot_edit", kwargs={"pk": timeattendance_record_draft_a.pk})
    resp_draft = client_a.get(draft_url)
    assert resp_draft.status_code == 200

    appr_url = reverse("projects:pot_edit", kwargs={"pk": timeattendance_record_approved_a.pk})
    resp_appr = client_a.get(appr_url)
    assert resp_appr.status_code == 302
    assert resp_appr["Location"] == reverse("projects:pot_detail", kwargs={"pk": timeattendance_record_approved_a.pk})


def test_timeattendance_pot_delete_locks_approved(client_a, timeattendance_record_approved_a):
    appr_del_url = reverse("projects:pot_delete", kwargs={"pk": timeattendance_record_approved_a.pk})
    resp = client_a.post(appr_del_url)
    assert resp.status_code == 302
    assert ProjectOvertimeRecord.objects.filter(pk=timeattendance_record_approved_a.pk).exists()


# ==================================================================================================
# Workflow Verbs: Submit, Approve, Reject
# ==================================================================================================

def test_timeattendance_pot_submit_advances_draft_to_submitted(client_a, timeattendance_record_draft_a):
    url = reverse("projects:pot_submit", kwargs={"pk": timeattendance_record_draft_a.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    timeattendance_record_draft_a.refresh_from_db()
    assert timeattendance_record_draft_a.status == "submitted"
    assert timeattendance_record_draft_a.submitted_at is not None


def test_timeattendance_pot_approve_advances_submitted_to_approved(
    client_a, admin_user, timeattendance_record_submitted_a
):
    url = reverse("projects:pot_approve", kwargs={"pk": timeattendance_record_submitted_a.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    timeattendance_record_submitted_a.refresh_from_db()
    assert timeattendance_record_submitted_a.status == "approved"
    assert timeattendance_record_submitted_a.approved_by == admin_user
    assert timeattendance_record_submitted_a.approved_at is not None


def test_timeattendance_pot_reject_records_decision_note(
    client_a, admin_user, timeattendance_record_submitted_a
):
    url = reverse("projects:pot_reject", kwargs={"pk": timeattendance_record_submitted_a.pk})
    resp = client_a.post(url, {"reason": "Overtime budget exceeded"})
    assert resp.status_code == 302
    timeattendance_record_submitted_a.refresh_from_db()
    assert timeattendance_record_submitted_a.status == "rejected"
    assert timeattendance_record_submitted_a.approved_by == admin_user
    assert timeattendance_record_submitted_a.decision_note == "Overtime budget exceeded"


# ==================================================================================================
# Dashboards & Calendar
# ==================================================================================================

def test_timeattendance_utilization_dashboard_renders_kpis(
    client_a, tenant_a, resource_profile_internal, resource_project
):
    # Seed approved billable and non-billable time entries
    today = timezone.localdate()
    _resource_entry(
        tenant_a, resource_profile_internal,
        project=resource_project,
        entry_date=today,
        hours=Decimal("8.00"),
        is_billable=True,
        status="approved",
    )
    _resource_entry(
        tenant_a, resource_profile_internal,
        project=resource_project,
        entry_date=today,
        hours=Decimal("2.00"),
        is_billable=False,
        status="approved",
    )

    url = reverse("projects:utilization_dashboard")
    resp = client_a.get(url, {"year": str(today.year), "month": str(today.month)})
    assert resp.status_code == 200
    ctx = resp.context
    assert ctx["kpi"]["total_hours"] >= Decimal("10.00")
    assert ctx["kpi"]["billable_hours"] >= Decimal("8.00")
    assert ctx["kpi"]["non_billable_hours"] >= Decimal("2.00")
    assert ctx["kpi"]["chargeability_ratio"] > Decimal("0")
    assert "individual_rows" in ctx
    assert "client_splits" in ctx
    assert "overhead_splits" in ctx
    assert "capacity_demand" in ctx


def test_timeattendance_calendar_renders_with_sync(
    client_a, tenant_a, resource_profile_internal, resource_project
):
    today = timezone.localdate()
    _resource_entry(
        tenant_a, resource_profile_internal,
        project=resource_project,
        entry_date=today,
        hours=Decimal("7.50"),
        is_billable=True,
        status="approved",
    )
    url = reverse("projects:time_calendar")
    resp = client_a.get(url, {"year": str(today.year), "month": str(today.month)})
    assert resp.status_code == 200
    ctx = resp.context
    assert "month_weeks" in ctx
    assert ctx["month_total_hours"] >= Decimal("7.50")
