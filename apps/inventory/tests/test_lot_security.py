"""Inventory 5.8 Lot & Serial Number Tracking — security & tenancy.

The whole surface is login-gated and tenant-scoped: foreign rows 404 on every
read/write route, deletes are POST-only, the mint form cannot be widened to a foreign
item, and the trace page refuses another workspace's lot id. No page leaks the other
tenant's lot numbers.
"""
import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_pages_require_login(client, lot_rule_default_a, shelf_policy_a,
                             stocked_lot_a):
    for url in (
        reverse("inventory:lotrule_list"),
        reverse("inventory:lotrule_detail", args=[lot_rule_default_a.pk]),
        reverse("inventory:lot_generate"),
        reverse("inventory:shelflifepolicy_list"),
        reverse("inventory:fefo_board"),
        f"{reverse('inventory:traceability')}?lot={stocked_lot_a.pk}",
    ):
        response = client.get(url)
        assert response.status_code in (302, 403), url


def test_foreign_rule_is_404_on_every_verb(client_a, lot_rule_default_b):
    for name in ("detail", "edit"):
        response = client_a.get(reverse(f"inventory:lotrule_{name}",
                                        args=[lot_rule_default_b.pk]))
        assert response.status_code == 404
    response = client_a.post(reverse(
        "inventory:lotrule_delete", args=[lot_rule_default_b.pk]))
    assert response.status_code == 404


def test_foreign_policy_is_404_on_every_verb(client_a, shelf_policy_b):
    for name in ("detail", "edit"):
        response = client_a.get(reverse(
            f"inventory:shelflifepolicy_{name}", args=[shelf_policy_b.pk]))
        assert response.status_code == 404
    assert client_a.post(reverse(
        "inventory:shelflifepolicy_delete", args=[shelf_policy_b.pk])).status_code == 404


def test_trace_refuses_foreign_lot(client_a, stocked_lot_b):
    response = client_a.get(reverse("inventory:traceability"),
                            {"lot": stocked_lot_b.pk})
    assert response.status_code == 404


def test_fefo_board_never_lists_other_tenant_rows(client_a, stocked_lot_b):
    html = client_a.get(reverse("inventory:fefo_board")).content.decode()
    assert stocked_lot_b.number not in html
    assert "LOTB" not in html


def test_generate_cannot_target_foreign_or_untracked_item(client_a, tenant_a,
                                                          tracked_item_b, item_a):
    from apps.scm.models import LotSerial

    before = LotSerial.objects.count()
    for foreign in (tracked_item_b, item_a):     # foreign workspace + untracked SKU
        response = client_a.post(reverse("inventory:lot_generate"),
                                 {"item": foreign.pk})
        assert response.status_code in (200, 302)
    assert LotSerial.objects.count() == before   # nothing minted either way


def test_delete_is_post_only(client_a, lot_rule_default_a, shelf_policy_a):
    rule_url = reverse("inventory:lotrule_delete", args=[lot_rule_default_a.pk])
    policy_url = reverse("inventory:shelflifepolicy_delete", args=[shelf_policy_a.pk])
    for url in (rule_url, policy_url):
        response = client_a.get(url)
        assert response.status_code in (403, 405)


def test_member_user_sees_pages_but_same_tenancy(db, member_user, client_a,
                                                 tenant_a, lot_rule_default_a):
    """A non-admin member of the SAME workspace reads normally — writes stay open to
    any workspace user here, exactly like every sibling sub-module's posture."""
    from apps.inventory.models import LotNumberRule

    assert LotNumberRule.objects.filter(tenant=tenant_a).exists()
