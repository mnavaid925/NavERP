"""Inventory 5.16 — model invariants.

The alert engine's whole contract lives at the model boundary: per-tenant ARL-/ALT-
numbering, recipient normalisation, the scope matcher, the acknowledge/resolve verbs,
and a run_detection() that raises from real spine state, suppresses duplicates while one
is open and honours the rule's cooldown.
"""
import datetime
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.inventory.models import AlertRule, InventoryAlert, NotificationDelivery

pytestmark = pytest.mark.django_db


# ------------------------------------------------------------------ numbering / basics


class TestNumberingAndBasics:
    def test_arl_number_sequence_per_tenant(self, tenant_a, tenant_b):
        first = AlertRule.objects.create(
            tenant=tenant_a, name="Rule one", alert_type="low_stock", cooldown_days=1)
        second = AlertRule.objects.create(
            tenant=tenant_a, name="Rule two", alert_type="expiry", cooldown_days=1)
        other = AlertRule.objects.create(
            tenant=tenant_b, name="Theirs", alert_type="overstock", cooldown_days=1)
        assert first.number == "ARL-00001"
        assert second.number == "ARL-00002"
        assert other.number == "ARL-00001"  # sequences never share across tenants

    def test_alt_number_sequence(self, tenant_a, alert_rule_a, inventory_alert_open_a):
        assert inventory_alert_open_a.number == "ALT-00001"
        second = InventoryAlert.objects.create(
            tenant=tenant_a, rule=alert_rule_a, alert_type="overstock", severity="info",
            dedup_key="overstock:0", title="Another")
        assert second.number == "ALT-00002"

    def test_recipients_normalised_on_save(self, tenant_a):
        rule = AlertRule.objects.create(
            tenant=tenant_a, name="Email rule", alert_type="low_stock",
            notify_email=True, notify_inapp=False,
            email_recipients=" Ops@Example.com , ops@example.com; buyer@example.com ",
            cooldown_days=1)
        rule.refresh_from_db()
        assert rule.email_recipients == "ops@example.com,buyer@example.com"

    def test_channels_property_order_and_content(self, tenant_a):
        rule = AlertRule(tenant=tenant_a, name="x", notify_sms=True, notify_inapp=True)
        assert rule.channels == ["in_app", "sms"]
        rule.notify_push = True
        # Declared order is stable: in_app -> email -> sms -> push.
        assert rule.channels == ["in_app", "sms", "push"]
        rule.notify_email = True
        assert rule.channels == ["in_app", "email", "sms", "push"]

    def test_in_scope_matching(self, item_a, location_a):
        unscoped = AlertRule(name="all")
        assert unscoped.in_scope(item_a.pk, location_a.pk)
        item_scoped = AlertRule(name="item", item_id=item_a.pk)
        assert item_scoped.in_scope(item_a.pk, None)
        assert not item_scoped.in_scope(item_a.pk + 1, None)

    def test_clean_rejects_foreign_scope_rows(self, tenant_a, item_b):
        rule = AlertRule(
            tenant=tenant_a, name="Foreign scope", alert_type="low_stock",
            item=item_b, cooldown_days=1)
        with pytest.raises(ValidationError) as exc:
            rule.clean()
        assert "item" in exc.value.message_dict

    def test_clean_requires_email_recipient_when_email_on(self, tenant_a):
        rule = AlertRule(
            tenant=tenant_a, name="Silent email", alert_type="low_stock",
            notify_email=True, email_recipients="  ", cooldown_days=1)
        with pytest.raises(ValidationError) as exc:
            rule.clean()
        assert "email_recipients" in exc.value.message_dict


# ------------------------------------------------------------------ triage verbs


class TestTriageVerbs:
    def test_acknowledge_stamps_user_and_time(self, admin_user, inventory_alert_open_a):
        inventory_alert_open_a.acknowledge(admin_user)
        inventory_alert_open_a.refresh_from_db()
        assert inventory_alert_open_a.status == "acknowledged"
        assert inventory_alert_open_a.acknowledged_by == admin_user
        assert inventory_alert_open_a.acknowledged_at is not None

    def test_acknowledge_refuses_non_open(self, admin_user, inventory_alert_open_a):
        inventory_alert_open_a.acknowledge(admin_user)
        with pytest.raises(ValidationError):
            inventory_alert_open_a.acknowledge(admin_user)

    def test_resolve_persists_note(self, admin_user, inventory_alert_open_a):
        inventory_alert_open_a.resolve(admin_user, note="restocked")
        inventory_alert_open_a.refresh_from_db()
        assert inventory_alert_open_a.status == "resolved"
        assert inventory_alert_open_a.resolution_note == "restocked"
        assert inventory_alert_open_a.resolved_at is not None

    def test_resolve_twice_refused(self, admin_user, inventory_alert_open_a):
        inventory_alert_open_a.resolve(admin_user)
        with pytest.raises(ValidationError):
            inventory_alert_open_a.resolve(admin_user)


# ------------------------------------------------------------------ detection engine


def _reorder_rule(tenant, item, location, point="5"):
    from apps.scm.models import ReorderRule
    return ReorderRule.objects.create(
        tenant=tenant, item=item, location=location,
        reorder_point=Decimal(point), safety_stock=Decimal("0"))


class TestRunDetection:
    def test_low_stock_raised_from_ledger(self, tenant_a, alert_rule_a, item_a, location_a):
        from apps.scm.models import StockMove
        _reorder_rule(tenant_a, item_a, location_a, point="50")
        StockMove.objects.create(
            tenant=tenant_a, item=item_a, location=location_a,
            quantity=Decimal("4"), unit_cost=Decimal("1"), move_type="receipt",
            moved_at=timezone.now())
        summary = InventoryAlert.run_detection(tenant_a)
        assert len(summary["raised"]) == 1
        alert = summary["raised"][0]
        assert alert.alert_type == "low_stock"
        assert alert.dedup_key == f"low_stock:{item_a.pk}:{location_a.pk}"
        assert alert.metric_value == Decimal("4")
        # ...and one in-app delivery was queued for it.
        assert NotificationDelivery.objects.filter(alert=alert, channel="in_app").exists()

    def test_out_of_stock_beats_low_stock(self, tenant_a, alert_rule_a, item_a, location_a):
        from apps.inventory.models import AlertRule
        from apps.scm.models import StockMove
        AlertRule.objects.create(
            tenant=tenant_a, name="Stock-out siren", alert_type="out_of_stock",
            severity="critical", cooldown_days=1)
        _reorder_rule(tenant_a, item_a, location_a)
        StockMove.objects.create(
            tenant=tenant_a, item=item_a, location=location_a,
            quantity=Decimal("-2"), unit_cost=Decimal("1"), move_type="issue",
            moved_at=timezone.now())
        summary = InventoryAlert.run_detection(tenant_a)
        # Negative on-hand takes ONLY the out-of-stock branch - no low-stock echo.
        assert [a.alert_type for a in summary["raised"]] == ["out_of_stock"]

    def test_dedup_skips_while_one_open(self, tenant_a, alert_rule_a, item_a, location_a,
                                        inventory_alert_open_a):
        _reorder_rule(tenant_a, item_a, location_a)
        from apps.scm.models import StockMove
        StockMove.objects.create(
            tenant=tenant_a, item=item_a, location=location_a,
            quantity=Decimal("2"), unit_cost=Decimal("1"), move_type="receipt",
            moved_at=timezone.now())
        summary = InventoryAlert.run_detection(tenant_a)
        assert summary["raised"] == []
        assert summary["skipped_open"] >= 1

    def test_cooldown_blocks_reraise_until_window_passes(self, admin_user, tenant_a,
                                                         alert_rule_a, item_a, location_a,
                                                         inventory_alert_open_a):
        from apps.scm.models import StockMove
        _reorder_rule(tenant_a, item_a, location_a)
        StockMove.objects.create(
            tenant=tenant_a, item=item_a, location=location_a,
            quantity=Decimal("2"), unit_cost=Decimal("1"), move_type="receipt",
            moved_at=timezone.now())
        inventory_alert_open_a.resolve(admin_user)  # frees the dedup key...
        alert_rule_a.cooldown_days = 30
        alert_rule_a.save()
        summary = InventoryAlert.run_detection(tenant_a)
        raised_now = [a for a in summary["raised"]
                      if a.dedup_key == inventory_alert_open_a.dedup_key]
        assert raised_now == []  # ...but the condition is still cooling down
        assert summary["skipped_cooldown"] >= 1
        alert_rule_a.cooldown_days = 0
        alert_rule_a.save()
        summary = InventoryAlert.run_detection(tenant_a)
        assert any(a.dedup_key == inventory_alert_open_a.dedup_key for a in summary["raised"])

    def test_expiry_window_and_expired_wording(self, tenant_a, tracked_item_a, location_a,
                                               stocked_lot_a):
        from apps.inventory.models import AlertRule
        from apps.scm.models import LotSerial
        AlertRule.objects.create(
            tenant=tenant_a, name="Expiry radar", alert_type="expiry",
            severity="warning", expiry_days=45, cooldown_days=1)
        expired_lot = LotSerial.objects.create(
            tenant=tenant_a, item=tracked_item_a, number="LOTA-EXPIRED",
            expiry_date=timezone.localdate() - datetime.timedelta(days=3))
        summary = InventoryAlert.run_detection(tenant_a)
        by_key = {a.dedup_key: a for a in summary["raised"]}
        assert f"expiry:{stocked_lot_a.pk}" in by_key          # inside the 45-day window
        assert f"expiry:{expired_lot.pk}" in by_key            # negative days still flagged
        assert by_key[f"expiry:{expired_lot.pk}"].title.startswith("Expired:")
        assert by_key[f"expiry:{stocked_lot_a.pk}"].title.startswith("Expiring:")

    def test_overstock_reads_declared_envelopes_only(self, tenant_a, item_a, location_a):
        from apps.inventory.models import AlertRule, BinCapacity
        from apps.scm.models import StockMove
        AlertRule.objects.create(
            tenant=tenant_a, name="Overstock guard", alert_type="overstock",
            severity="info", overstock_pct=Decimal("95"), cooldown_days=1)
        BinCapacity.objects.create(tenant=tenant_a, location=location_a,
                                   max_quantity=Decimal("10"))
        StockMove.objects.create(
            tenant=tenant_a, item=item_a, location=location_a, quantity=Decimal("12"),
            unit_cost=Decimal("1"), move_type="receipt", moved_at=timezone.now())
        summary = InventoryAlert.run_detection(tenant_a)
        assert len(summary["raised"]) == 1
        assert summary["raised"][0].alert_type == "overstock"

    def test_workflow_triggers_po_and_shipment(self, tenant_a, po_pending_a):
        from apps.core.models import Party
        from apps.scm.models import Shipment
        from apps.inventory.models import AlertRule
        AlertRule.objects.create(
            tenant=tenant_a, name="Stuck POs", alert_type="po_approval_pending",
            cooldown_days=1)
        AlertRule.objects.create(
            tenant=tenant_a, name="Late shipments", alert_type="shipment_delayed",
            cooldown_days=1)
        Party.objects.get_or_create(
            tenant=tenant_a, name="Acme Freight", defaults={"kind": "organization"})
        Shipment.objects.create(
            tenant=tenant_a, number="SHP-LATE01", direction="outbound",
            planned_delivery_date=timezone.localdate() - datetime.timedelta(days=4),
            origin_text="A", destination_text="B")
        types = {a.alert_type for a in InventoryAlert.run_detection(tenant_a)["raised"]}
        assert "po_approval_pending" in types
        assert "shipment_delayed" in types

    def test_inactive_rules_never_fire(self, tenant_a, alert_rule_a, item_a, location_a):
        _reorder_rule(tenant_a, item_a, location_a)
        from apps.scm.models import StockMove
        StockMove.objects.create(
            tenant=tenant_a, item=item_a, location=location_a,
            quantity=Decimal("1"), unit_cost=Decimal("1"), move_type="receipt",
            moved_at=timezone.now())
        alert_rule_a.is_active = False
        alert_rule_a.save()
        summary = InventoryAlert.run_detection(tenant_a)
        assert summary["rules_evaluated"] == 0
        assert summary["raised"] == []

    def test_deliveries_written_per_channel_per_recipient(self, tenant_a, po_pending_a):
        from apps.inventory.models import AlertRule
        rule = AlertRule.objects.create(
            tenant=tenant_a, name="Fan-out rule", alert_type="po_approval_pending",
            notify_inapp=True, notify_email=True, notify_sms=True,
            email_recipients="a@example.com,b@example.com", cooldown_days=1)
        InventoryAlert.run_detection(tenant_a)
        channels = list(NotificationDelivery.objects.filter(alert__rule=rule)
                        .values_list("channel", flat=True))
        assert channels.count("email") == 2   # one per recipient
        assert channels.count("in_app") == 1
        assert channels.count("sms") == 1
