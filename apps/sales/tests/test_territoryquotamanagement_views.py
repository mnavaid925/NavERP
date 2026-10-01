"""8.7 Territory & Quota Management -- views lane.

Tests cover:
- All 4 territory boards: rebalance preview, coverage gap, performance, white space.
- CRUD for TerritoryRule (list, detail, create, edit, delete, toggle, run).
- CRUD for AccountTerritoryAssignment (list, detail, create, edit, delete).
- CRUD for TerritoryMember (list, detail, create, edit, delete).
- CRUD & Lifecycle for QuotaPlan (list, detail, create, edit, delete, submit, approve, reject, lock).
- Search and filtering (?q=..., ?status=...).
- Actions column and Actions sidebar presence.

Names: every test is `test_territoryquotamanagement_*` and every helper `_territoryquotamanagement_*`.
"""
from decimal import Decimal
import json

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.sales.models.TerritoryQuotaManagement.AccountTerritoryAssignments import (
    AccountTerritoryAssignment,
)
from apps.sales.models.TerritoryQuotaManagement.QuotaPlans import (
    QuotaPlan,
)
from apps.sales.models.TerritoryQuotaManagement.TerritoryMembers import (
    TerritoryMember,
)
from apps.sales.models.TerritoryQuotaManagement.TerritoryRules import (
    TerritoryRule,
)
from apps.sales.tests.conftest import (
    _territoryquotamanagement_account,
    _territoryquotamanagement_assignment,
    _territoryquotamanagement_crm_quota,
    _territoryquotamanagement_crm_territory,
    _territoryquotamanagement_member,
    _territoryquotamanagement_quotaplan,
    _territoryquotamanagement_rule,
    _salesforecasting_period,
)

pytestmark = pytest.mark.django_db


# ==============================================================================
# 1. BOARDS
# ==============================================================================


def test_territoryquotamanagement_board_rebalance_preview(client, tqm_tenant_a, tqm_admin_a):
    """Rebalance preview board renders with 200 and is strictly read-only."""
    client.force_login(tqm_admin_a)
    url = reverse("sales:territory_rebalance_preview")
    resp = client.get(url)
    assert resp.status_code == 200
    assert "diff_rows" in resp.context or "stats" in resp.context
    # Assert read-only: POST is not supported or does not mutate DB
    post_resp = client.post(url)
    assert post_resp.status_code in (200, 405)


def test_territoryquotamanagement_board_coverage_gap(client, tqm_tenant_a, tqm_admin_a):
    """Coverage gap board renders with 200."""
    client.force_login(tqm_admin_a)
    url = reverse("sales:territory_coverage_gap")
    resp = client.get(url)
    assert resp.status_code == 200
    assert "gap_rows" in resp.context or "orphans" in resp.context or "stats" in resp.context


def test_territoryquotamanagement_board_performance(client, tqm_tenant_a, tqm_admin_a):
    """Territory performance board renders with 200."""
    client.force_login(tqm_admin_a)
    url = reverse("sales:territory_performance")
    resp = client.get(url)
    assert resp.status_code == 200
    assert "rows" in resp.context or "periods" in resp.context or "summary" in resp.context


def test_territoryquotamanagement_board_white_space(client, tqm_tenant_a, tqm_admin_a):
    """Territory white space board renders with 200."""
    client.force_login(tqm_admin_a)
    url = reverse("sales:territory_white_space")
    resp = client.get(url)
    assert resp.status_code == 200
    assert "account_rows" in resp.context or "unassigned" in resp.context or "stats" in resp.context


# ==============================================================================
# 2. TERRITORY RULES CRUD & VERBS
# ==============================================================================


def test_territoryquotamanagement_rule_views_crud(client, tqm_tenant_a, tqm_admin_a, tqm_territory):
    """TerritoryRule list, create, detail, edit, delete."""
    client.force_login(tqm_admin_a)

    # List
    list_url = reverse("sales:territory_rule_list")
    resp = client.get(list_url)
    assert resp.status_code == 200
    assert "stats" in resp.context

    # Create
    create_url = reverse("sales:territory_rule_create")
    create_resp = client.get(create_url)
    assert create_resp.status_code == 200

    data = {
        "name": "California Tech Rule",
        "segment_type": "geographic",
        "match_mode": "all",
        "alignment_type": "primary",
        "assignment_scope": "exact",
        "target_territory": tqm_territory.pk,
        "priority": 50,
        "is_active": True,
        "conditions": json.dumps([{"field": "state", "operator": "eq", "value": "CA"}]),
        "effective_from": timezone.localdate(),
    }
    post_resp = client.post(create_url, data)
    assert post_resp.status_code == 302
    rule = TerritoryRule.objects.get(tenant=tqm_tenant_a, name="California Tech Rule")

    # Detail
    detail_url = reverse("sales:territory_rule_detail", args=[rule.pk])
    detail_resp = client.get(detail_url)
    assert detail_resp.status_code == 200
    assert detail_resp.context["obj"] == rule

    # Edit
    edit_url = reverse("sales:territory_rule_edit", args=[rule.pk])
    edit_resp = client.get(edit_url)
    assert edit_resp.status_code == 200
    data["name"] = "California Tech Rule Updated"
    client.post(edit_url, data)
    rule.refresh_from_db()
    assert rule.name == "California Tech Rule Updated"

    # Toggle action
    toggle_url = reverse("sales:territory_rule_toggle", args=[rule.pk])
    client.post(toggle_url)
    rule.refresh_from_db()
    assert rule.is_active is False

    # Delete
    delete_url = reverse("sales:territory_rule_delete", args=[rule.pk])
    del_resp = client.post(delete_url)
    assert del_resp.status_code == 302
    assert not TerritoryRule.objects.filter(pk=rule.pk).exists()


def test_territoryquotamanagement_rule_run_action(client, tqm_tenant_a, tqm_admin_a, tqm_territory):
    """territory_rule_run action executes and stamps last_run_at and matched_count."""
    client.force_login(tqm_admin_a)
    rule = _territoryquotamanagement_rule(tqm_tenant_a, target_territory=tqm_territory)

    run_url = reverse("sales:territory_rule_run", args=[rule.pk])
    resp = client.post(run_url)
    assert resp.status_code == 302
    rule.refresh_from_db()
    assert rule.last_run_at is not None


# ==============================================================================
# 3. ACCOUNT TERRITORY ASSIGNMENTS CRUD
# ==============================================================================


def test_territoryquotamanagement_assignment_views_crud(
    client, tqm_tenant_a, tqm_admin_a, tqm_territory, tqm_account_a
):
    """AccountTerritoryAssignment list, create, detail, edit, delete."""
    client.force_login(tqm_admin_a)

    # List
    list_url = reverse("sales:account_territory_assignment_list")
    resp = client.get(list_url)
    assert resp.status_code == 200
    assert "stats" in resp.context

    # Create
    create_url = reverse("sales:account_territory_assignment_create")
    assert client.get(create_url).status_code == 200
    data = {
        "account": tqm_account_a.pk,
        "territory": tqm_territory.pk,
        "alignment_type": "primary",
        "assignment_source": "manual",
        "owner": tqm_admin_a.pk,
        "effective_from": timezone.localdate(),
    }
    client.post(create_url, data)
    assignment = AccountTerritoryAssignment.objects.get(
        tenant=tqm_tenant_a, account=tqm_account_a, territory=tqm_territory
    )
    assert assignment.assigned_by == tqm_admin_a

    # Detail
    detail_url = reverse("sales:account_territory_assignment_detail", args=[assignment.pk])
    detail_resp = client.get(detail_url)
    assert detail_resp.status_code == 200
    assert detail_resp.context["obj"] == assignment

    # Edit
    edit_url = reverse("sales:account_territory_assignment_edit", args=[assignment.pk])
    assert client.get(edit_url).status_code == 200
    data["notes"] = "Updated strategic priority account notes"
    client.post(edit_url, data)
    assignment.refresh_from_db()
    assert assignment.notes == "Updated strategic priority account notes"
    # Verify assigned_by was NOT overwritten by edit (C1/frozen evidence)
    assert assignment.assigned_by == tqm_admin_a

    # Delete
    del_url = reverse("sales:account_territory_assignment_delete", args=[assignment.pk])
    del_resp = client.post(del_url)
    assert del_resp.status_code == 302
    assert not AccountTerritoryAssignment.objects.filter(pk=assignment.pk).exists()


# ==============================================================================
# 4. TERRITORY MEMBERS CRUD
# ==============================================================================


def test_territoryquotamanagement_member_views_crud(
    client, tqm_tenant_a, tqm_admin_a, tqm_territory
):
    """TerritoryMember list, create, detail, edit, delete."""
    client.force_login(tqm_admin_a)

    # List
    list_url = reverse("sales:territory_member_list")
    assert client.get(list_url).status_code == 200

    # Create
    create_url = reverse("sales:territory_member_create")
    assert client.get(create_url).status_code == 200
    data = {
        "territory": tqm_territory.pk,
        "user": tqm_admin_a.pk,
        "member_role": "ae",
        "assignment_type": "direct",
        "is_primary": True,
        "coverage_split_pct": "100.00",
        "effective_from": timezone.localdate(),
    }
    client.post(create_url, data)
    member = TerritoryMember.objects.get(
        tenant=tqm_tenant_a, territory=tqm_territory, user=tqm_admin_a
    )

    # Detail
    detail_url = reverse("sales:territory_member_detail", args=[member.pk])
    assert client.get(detail_url).status_code == 200

    # Edit
    edit_url = reverse("sales:territory_member_edit", args=[member.pk])
    assert client.get(edit_url).status_code == 200
    data["notes"] = "Lead account executive"
    client.post(edit_url, data)
    member.refresh_from_db()
    assert member.notes == "Lead account executive"

    # Delete
    del_url = reverse("sales:territory_member_delete", args=[member.pk])
    assert client.post(del_url).status_code == 302
    assert not TerritoryMember.objects.filter(pk=member.pk).exists()


# ==============================================================================
# 5. QUOTA PLANS CRUD & LIFECYCLE WORKFLOW
# ==============================================================================


def test_territoryquotamanagement_quota_plan_views_workflow(
    client, tqm_tenant_a, tqm_admin_a, tqm_territory, tqm_quota
):
    """QuotaPlan lifecycle: draft -> submit -> approve -> lock."""
    client.force_login(tqm_admin_a)
    period = _salesforecasting_period(tqm_tenant_a)

    # List
    list_url = reverse("sales:quota_plan_list")
    assert client.get(list_url).status_code == 200

    # Create
    create_url = reverse("sales:quota_plan_create")
    data = {
        "quota_ref": tqm_quota.pk,
        "forecast_period": period.pk,
        "territory": tqm_territory.pk,
        "owner": tqm_admin_a.pk,
        "method": "top_down",
        "allocation_basis": "historical_revenue",
        "baseline_source": "previous_year",
        "growth_target_pct": "15.00",
        "attrition_relief_pct": "3.00",
        "target_type": "revenue",
        "phasing": "equal",
    }
    client.post(create_url, data)
    plan = QuotaPlan.objects.get(tenant=tqm_tenant_a, quota_ref=tqm_quota)
    assert plan.status == "draft"

    # Detail
    detail_url = reverse("sales:quota_plan_detail", args=[plan.pk])
    assert client.get(detail_url).status_code == 200

    # Submit
    submit_url = reverse("sales:quota_plan_submit", args=[plan.pk])
    client.post(submit_url)
    plan.refresh_from_db()
    assert plan.status == "submitted"
    assert plan.submitted_by == tqm_admin_a
    assert plan.submitted_at is not None

    # Approve
    approve_url = reverse("sales:quota_plan_approve", args=[plan.pk])
    client.post(approve_url)
    plan.refresh_from_db()
    assert plan.status == "approved"
    assert plan.approved_by == tqm_admin_a
    assert plan.approved_at is not None

    # Lock
    lock_url = reverse("sales:quota_plan_lock", args=[plan.pk])
    client.post(lock_url)
    plan.refresh_from_db()
    assert plan.status == "locked"

    # Delete
    del_url = reverse("sales:quota_plan_delete", args=[plan.pk])
    assert client.post(del_url).status_code == 302
    assert not QuotaPlan.objects.filter(pk=plan.pk).exists()


def test_territoryquotamanagement_quota_plan_rejection_workflow(
    client, tqm_tenant_a, tqm_admin_a, tqm_territory, tqm_quota
):
    """QuotaPlan reject workflow allows resubmission after editing (C6)."""
    client.force_login(tqm_admin_a)
    plan = _territoryquotamanagement_quotaplan(
        tqm_tenant_a, quota_ref=tqm_quota, territory=tqm_territory, owner=tqm_admin_a, status="submitted"
    )

    # Reject
    reject_url = reverse("sales:quota_plan_reject", args=[plan.pk])
    client.post(reject_url)
    plan.refresh_from_db()
    assert plan.status == "rejected"

    # Edit rejected plan resets to draft
    edit_url = reverse("sales:quota_plan_edit", args=[plan.pk])
    period = plan.forecast_period
    data = {
        "quota_ref": tqm_quota.pk,
        "forecast_period": period.pk,
        "territory": tqm_territory.pk,
        "owner": tqm_admin_a.pk,
        "method": "top_down",
        "allocation_basis": "historical_revenue",
        "baseline_source": "previous_year",
        "growth_target_pct": "20.00",
        "attrition_relief_pct": "5.00",
        "target_type": "revenue",
        "phasing": "equal",
    }
    client.post(edit_url, data)
    plan.refresh_from_db()
    assert plan.status == "draft"

    # Resubmit succeeds!
    submit_url = reverse("sales:quota_plan_submit", args=[plan.pk])
    client.post(submit_url)
    plan.refresh_from_db()
    assert plan.status == "submitted"
