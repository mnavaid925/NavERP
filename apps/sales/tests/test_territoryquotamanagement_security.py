"""8.7 Territory & Quota Management -- security lane.

Multi-tenancy and authorization are asserted from the outside:
- Cross-tenant IDOR: Tenant B accessing Tenant A's record gets HTTP 404 (never 403, 302, or 200).
- Anonymous visitor: all routes redirect to login (302).
- HTTP Method enforcement: state mutations require POST (GET returns 405).
- Tenant admin guards: administrative endpoints protected against standard members.
- Quota plan ownership enforcement (I12): standard member cannot edit/submit another rep's plan.
- Historical ended member guard (I11): membership with passed effective_to cannot be edited.

Names: every test is `test_territoryquotamanagement_*` and every helper `_territoryquotamanagement_*`.
"""
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

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

_SEEDED_MODELS = (
    "territory_rule",
    "account_territory_assignment",
    "territory_member",
    "quota_plan",
)


def _seed_tenant_a(tenant, admin):
    """Seed a connected graph of 8.7 records for Tenant A."""
    territory = _territoryquotamanagement_crm_territory(tenant, name="Primary Territory")
    account = _territoryquotamanagement_account(tenant, name="Primary Corp")
    period = _salesforecasting_period(tenant)
    quota = _territoryquotamanagement_crm_quota(tenant, territory=territory, owner=admin)

    rule = _territoryquotamanagement_rule(tenant, target_territory=territory)
    assignment = _territoryquotamanagement_assignment(tenant, account=account, territory=territory)
    member = _territoryquotamanagement_member(tenant, territory=territory, user=admin)
    plan = _territoryquotamanagement_quotaplan(
        tenant, quota_ref=quota, forecast_period=period, territory=territory, owner=admin
    )
    return {
        "rule": rule,
        "assignment": assignment,
        "member": member,
        "plan": plan,
    }


def test_territoryquotamanagement_security_cross_tenant_idor_returns_404(
    client, tqm_tenant_a, tqm_tenant_b, tqm_admin_a, admin_b
):
    """Admin B accessing Tenant A's objects must receive 404 across all detail and mutation views."""
    seed = _seed_tenant_a(tqm_tenant_a, tqm_admin_a)
    client.force_login(admin_b)

    # 1. TerritoryRule surfaces
    rule_pk = seed["rule"].pk
    assert client.get(reverse("sales:territory_rule_detail", args=[rule_pk])).status_code == 404
    assert client.get(reverse("sales:territory_rule_edit", args=[rule_pk])).status_code == 404
    assert client.post(reverse("sales:territory_rule_toggle", args=[rule_pk])).status_code == 404
    assert client.post(reverse("sales:territory_rule_run", args=[rule_pk])).status_code == 404
    assert client.post(reverse("sales:territory_rule_delete", args=[rule_pk])).status_code == 404

    # 2. AccountTerritoryAssignment surfaces
    assign_pk = seed["assignment"].pk
    assert client.get(reverse("sales:account_territory_assignment_detail", args=[assign_pk])).status_code == 404
    assert client.get(reverse("sales:account_territory_assignment_edit", args=[assign_pk])).status_code == 404
    assert client.post(reverse("sales:account_territory_assignment_delete", args=[assign_pk])).status_code == 404

    # 3. TerritoryMember surfaces
    member_pk = seed["member"].pk
    assert client.get(reverse("sales:territory_member_detail", args=[member_pk])).status_code == 404
    assert client.get(reverse("sales:territory_member_edit", args=[member_pk])).status_code == 404
    assert client.post(reverse("sales:territory_member_delete", args=[member_pk])).status_code == 404

    # 4. QuotaPlan surfaces
    plan_pk = seed["plan"].pk
    assert client.get(reverse("sales:quota_plan_detail", args=[plan_pk])).status_code == 404
    assert client.get(reverse("sales:quota_plan_edit", args=[plan_pk])).status_code == 404
    assert client.post(reverse("sales:quota_plan_submit", args=[plan_pk])).status_code == 404
    assert client.post(reverse("sales:quota_plan_approve", args=[plan_pk])).status_code == 404
    assert client.post(reverse("sales:quota_plan_reject", args=[plan_pk])).status_code == 404
    assert client.post(reverse("sales:quota_plan_lock", args=[plan_pk])).status_code == 404
    assert client.post(reverse("sales:quota_plan_delete", args=[plan_pk])).status_code == 404


def test_territoryquotamanagement_security_anonymous_redirects_to_login(client):
    """Anonymous visitors must be redirected to login on all boards and registers."""
    urls = [
        reverse("sales:territory_rebalance_preview"),
        reverse("sales:territory_coverage_gap"),
        reverse("sales:territory_performance"),
        reverse("sales:territory_white_space"),
        reverse("sales:territory_rule_list"),
        reverse("sales:account_territory_assignment_list"),
        reverse("sales:territory_member_list"),
        reverse("sales:quota_plan_list"),
    ]
    for url in urls:
        resp = client.get(url)
        assert resp.status_code == 302
        assert "/login" in resp.url or "login" in resp.headers.get("Location", "")


def test_territoryquotamanagement_security_action_methods_require_post(
    client, tqm_tenant_a, tqm_admin_a, tqm_territory, tqm_quota
):
    """Destructive and state-changing actions must return 405 on GET."""
    client.force_login(tqm_admin_a)
    rule = _territoryquotamanagement_rule(tqm_tenant_a, target_territory=tqm_territory)
    account = _territoryquotamanagement_account(tqm_tenant_a)
    assign = _territoryquotamanagement_assignment(tqm_tenant_a, account=account, territory=tqm_territory)
    member = _territoryquotamanagement_member(tqm_tenant_a, territory=tqm_territory, user=tqm_admin_a)
    period = _salesforecasting_period(tqm_tenant_a)
    plan = _territoryquotamanagement_quotaplan(
        tqm_tenant_a, quota_ref=tqm_quota, forecast_period=period, territory=tqm_territory, owner=tqm_admin_a
    )

    action_urls = [
        reverse("sales:territory_rule_run", args=[rule.pk]),
        reverse("sales:territory_rule_toggle", args=[rule.pk]),
        reverse("sales:territory_rule_delete", args=[rule.pk]),
        reverse("sales:account_territory_assignment_delete", args=[assign.pk]),
        reverse("sales:territory_member_delete", args=[member.pk]),
        reverse("sales:quota_plan_submit", args=[plan.pk]),
        reverse("sales:quota_plan_approve", args=[plan.pk]),
        reverse("sales:quota_plan_reject", args=[plan.pk]),
        reverse("sales:quota_plan_lock", args=[plan.pk]),
        reverse("sales:quota_plan_delete", args=[plan.pk]),
    ]
    for url in action_urls:
        resp = client.get(url)
        assert resp.status_code == 405, f"URL {url} must return 405 on GET"


def test_territoryquotamanagement_security_admin_only_endpoints(
    client, tqm_tenant_a, tqm_member_a, tqm_territory
):
    """Standard non-admin members cannot access tenant admin endpoints (I13)."""
    client.force_login(tqm_member_a)

    # Rule administration requires tenant admin
    rule_create = reverse("sales:territory_rule_create")
    assert client.get(rule_create).status_code in (302, 403)

    # Member creation and editing require tenant admin (I13)
    member_create = reverse("sales:territory_member_create")
    assert client.get(member_create).status_code in (302, 403)


def test_territoryquotamanagement_security_quota_plan_ownership(
    client, tqm_tenant_a, tqm_admin_a, tqm_member_a, tqm_territory, tqm_quota
):
    """Standard member cannot edit or submit another rep's quota plan (I12)."""
    period = _salesforecasting_period(tqm_tenant_a)
    # Plan owned by admin_a
    plan = _territoryquotamanagement_quotaplan(
        tqm_tenant_a, quota_ref=tqm_quota, forecast_period=period, territory=tqm_territory, owner=tqm_admin_a
    )

    # Member_a tries to submit or edit admin_a's plan
    client.force_login(tqm_member_a)
    edit_url = reverse("sales:quota_plan_edit", args=[plan.pk])
    submit_url = reverse("sales:quota_plan_submit", args=[plan.pk])

    # Should redirect with error
    assert client.get(edit_url).status_code == 302
    assert client.post(submit_url).status_code == 302


def test_territoryquotamanagement_security_ended_member_cannot_be_edited(
    client, tqm_tenant_a, tqm_admin_a, tqm_territory
):
    """A historical ended membership cannot be edited via direct POST (I11)."""
    client.force_login(tqm_admin_a)
    yesterday = timezone.localdate() - timezone.timedelta(days=1)
    past_start = timezone.localdate() - timezone.timedelta(days=30)
    member = _territoryquotamanagement_member(
        tqm_tenant_a,
        territory=tqm_territory,
        user=tqm_admin_a,
        effective_from=past_start,
        effective_to=yesterday,
    )

    edit_url = reverse("sales:territory_member_edit", args=[member.pk])
    resp = client.post(edit_url, {"notes": "Tampering with historical ended membership"})
    assert resp.status_code == 302
    member.refresh_from_db()
    assert member.notes != "Tampering with historical ended membership"
