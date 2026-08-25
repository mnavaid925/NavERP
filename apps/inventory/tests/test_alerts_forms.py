"""Inventory 5.16 — form contract.

The rule catalog is the one editable entity: field set frozen, tenant-unique name enforced
at the form boundary (not left to IntegrityError), foreign scope rows rejected with a
field error, and the email channel required to carry at least one address.
"""
import pytest
from django.core.exceptions import ValidationError

from apps.inventory.forms import AlertRuleForm
from apps.inventory.models import AlertRule

pytestmark = pytest.mark.django_db


EXPECTED_FIELDS = [
    "name", "alert_type", "severity", "item", "location",
    "expiry_days", "overstock_pct",
    "notify_inapp", "notify_email", "notify_sms", "notify_push",
    "email_recipients", "cooldown_days", "is_active", "notes",
]


def _base_data(**overrides):
    data = {
        "name": "Smoke watch",
        "alert_type": "low_stock",
        "severity": "warning",
        "item": "",
        "location": "",
        "expiry_days": "30",
        "overstock_pct": "100.00",
        "cooldown_days": "7",
        "email_recipients": "",
    }
    data.update(overrides)
    return data


class TestAlertRuleForm:
    def test_field_set_frozen(self):
        assert list(AlertRuleForm.Meta.fields) == EXPECTED_FIELDS

    def test_tenant_and_number_not_form_fields(self, tenant_a):
        form = AlertRuleForm(tenant=tenant_a)
        assert "tenant" not in form.fields
        assert "number" not in form.fields

    def test_valid_create_saves_with_arl_number(self, tenant_a):
        form = AlertRuleForm(_base_data(), tenant=tenant_a)
        assert form.is_valid(), form.errors
        rule = form.save()
        assert rule.tenant == tenant_a
        assert rule.number.startswith("ARL-")

    def test_duplicate_name_same_tenant_rejected_at_boundary(self, tenant_a, alert_rule_a):
        form = AlertRuleForm(_base_data(name=alert_rule_a.name), tenant=tenant_a)
        assert not form.is_valid()
        assert "__all__" in form.errors or "name" in form.errors

    def test_same_name_other_tenant_allowed(self, tenant_b, alert_rule_a):
        form = AlertRuleForm(_base_data(name=alert_rule_a.name), tenant=tenant_b)
        assert form.is_valid(), form.errors

    def test_email_channel_requires_recipient(self, tenant_a):
        form = AlertRuleForm(_base_data(notify_email="on"), tenant=tenant_a)
        assert not form.is_valid()
        assert "email_recipients" in form.errors

    def test_email_recipient_present_passes(self, tenant_a):
        form = AlertRuleForm(
            _base_data(notify_email="on", email_recipients="ops@example.com"),
            tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_foreign_item_rejected_with_field_error(self, tenant_a, item_b):
        """A crafted POST naming another workspace's item must render as a field error,
        never leak or 500."""
        form = AlertRuleForm(_base_data(item=item_b.pk), tenant=tenant_a)
        assert not form.is_valid()
        assert "item" in form.errors

    def test_foreign_location_rejected_with_field_error(self, tenant_a, location_b):
        form = AlertRuleForm(_base_data(location=location_b.pk), tenant=tenant_a)
        assert not form.is_valid()
        assert "location" in form.errors

    def test_edit_roundtrip_keeps_number(self, tenant_a, alert_rule_a):
        form = AlertRuleForm(_base_data(name="Renamed watch"), instance=alert_rule_a,
                             tenant=tenant_a)
        assert form.is_valid(), form.errors
        saved = form.save()
        saved.refresh_from_db()
        assert saved.name == "Renamed watch"
        assert saved.number == alert_rule_a.number  # numbering is assign-once
