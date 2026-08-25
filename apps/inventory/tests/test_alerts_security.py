"""Inventory 5.16 — security.

Cross-tenant IDOR on every route shape, POST-only destructive verbs, anonymous access,
CSRF enforcement, admin gating of configuration surfaces, crafted-POST foreign-FK
rejection, list isolation and escaping of alert text.
"""
import pytest
from django.test import Client
from django.urls import reverse

from apps.inventory.models import AlertRule, InventoryAlert

pytestmark = pytest.mark.django_db


def test_cross_tenant_alert_pages_404(client_a, inventory_alert_open_b):
    assert client_a.get(reverse("inventory:alert_detail",
                                args=[inventory_alert_open_b.pk])).status_code == 404
    # The verbs are POST-only: a GET is refused by method before anything else...
    assert client_a.get(reverse("inventory:alert_acknowledge",
                                args=[inventory_alert_open_b.pk])).status_code == 405
    # ...so the IDOR probe rides the verb's real method.
    assert client_a.post(reverse("inventory:alert_resolve",
                                 args=[inventory_alert_open_b.pk])).status_code == 404


def test_cross_tenant_alert_post_404_and_row_unchanged(client_a, inventory_alert_open_b):
    response = client_a.post(
        reverse("inventory:alert_resolve", args=[inventory_alert_open_b.pk]),
        {"resolution_note": "hijacked"})
    assert response.status_code == 404
    inventory_alert_open_b.refresh_from_db()
    assert inventory_alert_open_b.status != "resolved"
    assert inventory_alert_open_b.resolution_note == ""


def test_cross_tenant_rule_pages_404(client_a, alert_rule_b):
    assert client_a.get(reverse("inventory:alertrule_detail",
                                args=[alert_rule_b.pk])).status_code == 404
    assert client_a.get(reverse("inventory:alertrule_edit",
                                args=[alert_rule_b.pk])).status_code == 404
    assert client_a.post(reverse("inventory:alertrule_delete",
                                 args=[alert_rule_b.pk])).status_code == 404


def test_cross_tenant_rule_edit_post_404(client_a, alert_rule_b):
    response = client_a.post(
        reverse("inventory:alertrule_edit", args=[alert_rule_b.pk]),
        {"name": "hijacked", "alert_type": "low_stock", "cooldown_days": "1"})
    assert response.status_code == 404
    alert_rule_b.refresh_from_db()
    assert alert_rule_b.name != "hijacked"


def test_cross_tenant_delivery_detail_404(client_a, tenant_b, notification_delivery_a):
    from apps.inventory.models import NotificationDelivery
    globex_alert = InventoryAlert.objects.create(
        tenant=tenant_b, alert_type="expiry", severity="info",
        dedup_key="expiry:foreign", title="Foreign")
    foreign = NotificationDelivery.objects.create(
        tenant=tenant_b, alert=globex_alert, channel="sms", recipient="0700000000")
    assert client_a.get(
        reverse("inventory:delivery_detail", args=[foreign.pk])).status_code == 404
    # ...and the owned row still renders (sanity that the 404 was the fence, not the route).
    assert client_a.get(reverse("inventory:delivery_detail",
                                args=[notification_delivery_a.pk])).status_code == 200


def test_foreign_rows_never_leak_into_lists(client_a, alert_rule_b,
                                            inventory_alert_open_b):
    content = client_a.get(reverse("inventory:alert_list")).content
    assert inventory_alert_open_b.number.encode() not in content
    rules = client_a.get(reverse("inventory:alertrule_list")).content
    assert alert_rule_b.name.encode() not in rules


def test_destructive_verbs_are_post_only(client_a, inventory_alert_open_a, alert_rule_a):
    assert client_a.get(reverse("inventory:alert_acknowledge",
                                args=[inventory_alert_open_a.pk])).status_code == 405
    assert client_a.get(reverse("inventory:alert_resolve",
                                args=[inventory_alert_open_a.pk])).status_code == 405
    assert client_a.get(reverse("inventory:alertrule_delete",
                                args=[alert_rule_a.pk])).status_code == 405


def test_anonymous_redirected_on_every_page(client, alert_rule_a, inventory_alert_open_a):
    bare = ["alert_list", "alertrule_list", "alertrule_create", "delivery_list"]
    for name in bare:
        assert client.get(reverse(f"inventory:{name}")).status_code == 302
    for name in ["alert_detail", "alertrule_detail", "delivery_detail"]:
        pk = {"alert_detail": inventory_alert_open_a.pk,
              "alertrule_detail": alert_rule_a.pk,
              "delivery_detail": 1}[name]
        assert client.get(reverse(f"inventory:{name}", args=[pk])).status_code == 302


def test_member_blocked_from_config_surfaces(member_client, alert_rule_a):
    """Rules + detection are tenant-admin surfaces; a plain member gets 403."""
    assert member_client.get(reverse("inventory:alertrule_create")).status_code == 403
    assert member_client.get(
        reverse("inventory:alertrule_edit", args=[alert_rule_a.pk])).status_code == 403
    assert member_client.post(
        reverse("inventory:alertrule_delete", args=[alert_rule_a.pk])).status_code == 403
    assert member_client.post(reverse("inventory:alert_run_detection")).status_code == 403


def test_csrf_enforced_on_triage_post(admin_user, inventory_alert_open_a, db):
    """A cross-site form post without the token is refused outright."""
    from django.test import Client as CsrfClient
    strict = CsrfClient(enforce_csrf_checks=True)
    strict.force_login(admin_user)
    assert strict.post(reverse("inventory:alert_acknowledge",
                               args=[inventory_alert_open_a.pk])).status_code == 403


def test_crafted_rule_post_cannot_target_foreign_rows(client_a, item_b, location_b, tenant_a):
    response = client_a.post(reverse("inventory:alertrule_create"), {
        "name": "Crafted scope", "alert_type": "low_stock", "severity": "warning",
        "item": item_b.pk, "location": location_b.pk,
        "expiry_days": "30", "overstock_pct": "100.00", "cooldown_days": "1",
    })
    assert response.status_code == 200  # re-render with field errors, never 500
    rule = AlertRule.objects.filter(tenant=tenant_a, name="Crafted scope").first()
    assert rule is None or (rule.item_id is None and rule.location_id is None)


def test_alert_text_is_escaped(client_a, tenant_a, alert_rule_a, db):
    alert = InventoryAlert.objects.create(
        tenant=tenant_a, rule=alert_rule_a, alert_type="expiry", severity="info",
        dedup_key="xss:probe",
        title="<script>alert('x')</script>", message="<b>bold claim</b>")
    content = client_a.get(reverse("inventory:alert_list")).content
    assert b"<script>alert('x')</script>" not in content
    detail = client_a.get(reverse("inventory:alert_detail", args=[alert.pk]))
    assert b"<b>bold claim</b>" not in detail.content
