"""Inventory 5.16 — view contract.

Every page renders 200 for the owning tenant with the documented context keys, the
?type= lenses actually filter the inbox, the triage verbs persist through the model
guards, run-detection is admin-gated and audited, and the append-only delivery log has
no mutation routes to reverse.
"""
import pytest
from django.urls import reverse
from django.utils import timezone

from apps.inventory.models import AlertRule, InventoryAlert, NotificationDelivery

pytestmark = pytest.mark.django_db


# ------------------------------------------------------------------ inbox


class TestAlertInbox:
    def test_list_renders_with_stats_and_lenses(self, client_a, inventory_alert_open_a):
        response = client_a.get(reverse("inventory:alert_list"))
        assert response.status_code == 200
        assert response.context["stats"]["open"] == 1
        assert "type_choices" in response.context

    def test_type_lens_filters(self, client_a, inventory_alert_open_a):
        content = client_a.get(
            reverse("inventory:alert_list") + "?type=low_stock").content
        assert inventory_alert_open_a.number.encode() in content
        empty = client_a.get(reverse("inventory:alert_list") + "?type=overstock")
        assert empty.status_code == 200
        assert inventory_alert_open_a.number.encode() not in empty.content

    def test_junk_get_degrades_to_no_filter(self, client_a, inventory_alert_open_a):
        response = client_a.get(reverse("inventory:alert_list") + "?type=zzz&severity=x")
        assert response.status_code == 200
        assert inventory_alert_open_a.number.encode() in response.content

    def test_search_by_number(self, client_a, inventory_alert_open_a):
        hit = client_a.get(reverse("inventory:alert_list"), {"q": inventory_alert_open_a.number})
        assert inventory_alert_open_a.title.encode() in hit.content
        miss = client_a.get(reverse("inventory:alert_list"), {"q": "ALT-99999"})
        assert inventory_alert_open_a.number.encode() not in miss.content

    def test_detail_shows_snapshot_and_deliveries(self, client_a, inventory_alert_open_a,
                                                  notification_delivery_a):
        response = client_a.get(
            reverse("inventory:alert_detail", args=[inventory_alert_open_a.pk]))
        assert response.status_code == 200
        assert inventory_alert_open_a.message.encode() in response.content
        assert notification_delivery_a.recipient.encode() in response.content


# ------------------------------------------------------------------ triage verbs


class TestTriage:
    def test_acknowledge_then_resolve_roundtrip(self, client_a, inventory_alert_open_a):
        ack = client_a.post(reverse("inventory:alert_acknowledge",
                                    args=[inventory_alert_open_a.pk]))
        assert ack.status_code == 302
        inventory_alert_open_a.refresh_from_db()
        assert inventory_alert_open_a.status == "acknowledged"
        resolve = client_a.post(reverse("inventory:alert_resolve",
                                        args=[inventory_alert_open_a.pk]),
                                {"resolution_note": "restocked from transfer"})
        assert resolve.status_code == 302
        inventory_alert_open_a.refresh_from_db()
        assert inventory_alert_open_a.status == "resolved"
        assert inventory_alert_open_a.resolution_note == "restocked from transfer"

    def test_resolve_of_resolved_redirects_with_error(self, client_a, tenant_a,
                                                      alert_rule_a):
        alert = InventoryAlert.objects.create(
            tenant=tenant_a, rule=alert_rule_a, alert_type="expiry", severity="info",
            dedup_key="expiry:x", title="Done already", status="resolved")
        response = client_a.post(reverse("inventory:alert_resolve", args=[alert.pk]), {})
        assert response.status_code == 302
        alert.refresh_from_db()
        assert alert.status == "resolved"  # still resolved, no crash

    def test_member_can_triage(self, member_client, inventory_alert_open_a):
        """Acknowledge is operational, not configuration — plain staff may do it."""
        response = member_client.post(reverse("inventory:alert_acknowledge",
                                              args=[inventory_alert_open_a.pk]))
        assert response.status_code == 302
        inventory_alert_open_a.refresh_from_db()
        assert inventory_alert_open_a.status == "acknowledged"


# ------------------------------------------------------------------ rule CRUD


class TestRuleCrud:
    def test_list_and_detail_render(self, client_a, alert_rule_a):
        assert client_a.get(reverse("inventory:alertrule_list")).status_code == 200
        detail = client_a.get(reverse("inventory:alertrule_detail", args=[alert_rule_a.pk]))
        assert detail.status_code == 200
        assert alert_rule_a.name.encode() in detail.content

    def test_create_edit_delete_roundtrip(self, client_a, tenant_a):
        create = client_a.post(reverse("inventory:alertrule_create"), {
            "name": "View-made rule", "alert_type": "expiry", "severity": "info",
            "item": "", "location": "", "expiry_days": "14", "overstock_pct": "100.00",
            "cooldown_days": "3", "notify_inapp": "on",
        })
        assert create.status_code == 302
        rule = AlertRule.objects.get(tenant=tenant_a, name="View-made rule")
        assert rule.number.startswith("ARL-")

        edit = client_a.post(reverse("inventory:alertrule_edit", args=[rule.pk]),
                             {"name": "Renamed by view", "alert_type": "expiry",
                              "severity": "info", "item": "", "location": "",
                              "expiry_days": "21", "overstock_pct": "100.00",
                              "cooldown_days": "3", "notify_inapp": "on"})
        assert edit.status_code == 302
        rule.refresh_from_db()
        assert rule.name == "Renamed by view"

        delete = client_a.post(reverse("inventory:alertrule_delete", args=[rule.pk]))
        assert delete.status_code == 302
        assert not AlertRule.objects.filter(pk=rule.pk).exists()

    def test_invalid_rule_create_rerenders_with_errors(self, client_a, tenant_a):
        response = client_a.post(reverse("inventory:alertrule_create"), {
            "name": "Bad", "alert_type": "expiry", "severity": "info",
            "notify_email": "on", "email_recipients": "",
        })
        assert response.status_code == 200
        assert not AlertRule.objects.filter(tenant=tenant_a, name="Bad").exists()


# ------------------------------------------------------------------ detection endpoint


class TestRunDetection:
    def test_admin_post_runs_and_reports(self, client_a, alert_rule_a, item_a, location_a):
        from apps.scm.models import ReorderRule, StockMove
        from decimal import Decimal
        ReorderRule.objects.create(tenant=item_a.tenant, item=item_a, location=location_a,
                                   reorder_point=Decimal("9"))
        StockMove.objects.create(tenant=item_a.tenant, item=item_a, location=location_a,
                                 quantity=Decimal("2"), unit_cost=Decimal("1"),
                                 move_type="receipt", moved_at=timezone.now())
        before = InventoryAlert.objects.count()
        response = client_a.post(reverse("inventory:alert_run_detection"))
        assert response.status_code == 302
        assert InventoryAlert.objects.count() == before + 1

    def test_member_post_is_403(self, member_client):
        response = member_client.post(reverse("inventory:alert_run_detection"))
        assert response.status_code == 403

    def test_get_is_405(self, client_a):
        assert client_a.get(reverse("inventory:alert_run_detection")).status_code == 405

    def test_second_run_does_not_duplicate(self, client_a, alert_rule_a):
        client_a.post(reverse("inventory:alert_run_detection"))
        count = InventoryAlert.objects.count()
        client_a.post(reverse("inventory:alert_run_detection"))
        assert InventoryAlert.objects.count() == count  # dedup holds across requests


# ------------------------------------------------------------------ deliveries (append-only)


class TestDeliveryPages:
    def test_list_and_detail_read_only(self, client_a, notification_delivery_a):
        listing = client_a.get(reverse("inventory:delivery_list"))
        assert listing.status_code == 200
        assert notification_delivery_a.recipient.encode() in listing.content
        detail = client_a.get(
            reverse("inventory:delivery_detail", args=[notification_delivery_a.pk]))
        assert detail.status_code == 200

    def test_channel_filter(self, client_a, notification_delivery_a):
        hit = client_a.get(reverse("inventory:delivery_list"), {"channel": "email"})
        assert notification_delivery_a.pk and hit.status_code == 200
        miss = client_a.get(reverse("inventory:delivery_list"), {"channel": "sms"})
        assert notification_delivery_a.recipient.encode() not in miss.content

    def test_no_mutation_routes_exist(self):
        """The dispatch log is a record, not an opinion — no write routes to reverse."""
        from django.urls import NoReverseMatch
        for name in ("delivery_create", "delivery_edit", "delivery_delete"):
            with pytest.raises(NoReverseMatch):
                reverse(f"inventory:{name}")
