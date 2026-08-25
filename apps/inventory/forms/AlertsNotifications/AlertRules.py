"""Inventory 5.16 Alerts & Notifications — AlertRule form."""
from django import forms

from apps.inventory.forms._common import *  # noqa: F401,F403
from apps.inventory.forms._common import _reject_foreign
from apps.inventory.models.AlertsNotifications.AlertRules import AlertRule
from apps.scm.models import Item, Location


class AlertRuleForm(TenantUniqueMixin, TenantModelForm):
    """Create/maintain a watch rule [ARL-]; thresholds unused by its type are inert knobs."""

    class Meta:
        model = AlertRule
        fields = [
            "name",
            "alert_type",
            "severity",
            "item",
            "location",
            "expiry_days",
            "overstock_pct",
            "notify_inapp",
            "notify_email",
            "notify_sms",
            "notify_push",
            "email_recipients",
            "cooldown_days",
            "is_active",
            "notes",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "e.g. Critical stock-outs"}),
            "email_recipients": forms.TextInput(
                attrs={"placeholder": "buyer@company.com, ops@company.com"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["item"].queryset = Item.objects.filter(tenant=self.tenant).order_by("sku")
            self.fields["location"].queryset = Location.objects.filter(tenant=self.tenant).order_by("code")

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["item", "location"])
        return cleaned
