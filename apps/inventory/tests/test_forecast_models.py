"""Inventory 5.13 — model + view/security tests (consolidated slice file)."""
import datetime

from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.inventory.models import StockLevelPlan

pytestmark = pytest.mark.django_db


def _plan(tenant, status="draft", **kw):
    from apps.scm.models import Item
    item, _ = Item.objects.get_or_create(
        tenant=tenant, sku="FC-1", defaults={"name": "Forecasted", "standard_cost": 5})
    return StockLevelPlan.objects.create(
        tenant=tenant, item=item,
        base_target_qty=kw.pop("base", Decimal("40")),
        effective_from=timezone.localdate(), status=status, **kw)


def test_plan_number_prefix_and_recommended_flat(tenant_a):
    plan = _plan(tenant_a)
    assert plan.number.startswith("SLP-")
    assert plan.recommended_qty() == plan.base_target_qty


def test_plan_seasonal_recommendation(tenant_a, tenant_b):
    from apps.scm.models import SeasonalityIndex, SeasonalityProfile
    plan = _plan(tenant_a)
    dec = timezone.localdate().replace(month=12)
    profile = SeasonalityProfile.objects.create(
        tenant=tenant_a, name="Dec peak", bucket="month", scope="item", item=plan.item)
    SeasonalityIndex.objects.create(profile=profile, period_number=12,
                                    index_factor=Decimal("1.5"))
    plan.seasonal_profile = profile
    assert plan.recommended_qty(dec) == Decimal("60.00")


def test_activate_supersedes_previous_active(tenant_a, admin_user):
    first = _plan(tenant_a).activate(admin_user)
    second = _plan(tenant_a).activate(admin_user)
    first.refresh_from_db(); second.refresh_from_db()
    assert second.status == "active" and first.status == "archived"


def test_activate_non_draft_refused(tenant_a, admin_user):
    plan = _plan(tenant_a).activate(admin_user)
    with pytest.raises(Exception):
        plan.activate(admin_user)


def test_window_validation(tenant_a):
    today = timezone.localdate()
    plan = _plan(tenant_a, effective_until=today - datetime.timedelta(days=1))
    with pytest.raises(Exception):
        plan.full_clean()


def test_pages_render_and_verdict(client_a, tenant_a):
    plan = _plan(tenant_a, status="active")
    r = client_a.get(reverse("inventory:stocklevelplan_detail", args=[plan.pk]))
    assert r.status_code == 200 and "Recommended Stock" in r.content.decode()
    assert client_a.get(reverse("inventory:stocklevelplan_list")).status_code == 200
    assert client_a.get(reverse("inventory:planning_board")).status_code == 200


def test_edit_archived_redirects_and_delete_guarded(client_a, tenant_a, admin_user):
    plan = _plan(tenant_a, status="active")
    r = client_a.get(reverse("inventory:stocklevelplan_edit", args=[plan.pk]))
    assert r.status_code == 302
    r = client_a.post(reverse("inventory:stocklevelplan_delete", args=[plan.pk]), follow=True)
    assert StockLevelPlan.objects.filter(pk=plan.pk).exists()


def test_board_lists_rule_rows(client_a, tenant_a):
    body = client_a.get(reverse("inventory:planning_board")).content.decode()
    assert "Computed SS / ROP" in body and "{#" not in body


def test_foreign_routes_404(client_a, tenant_b):
    foreign = _plan(tenant_b, status="active")
    assert client_a.get(reverse("inventory:stocklevelplan_edit",
                                args=[foreign.pk])).status_code == 404
    assert client_a.post(reverse("inventory:stocklevelplan_archive",
                                 args=[foreign.pk])).status_code == 404


def test_login_required(client, tenant_a):
    assert client.get(reverse("inventory:stocklevelplan_list")).status_code in (302, 403)
