"""Inventory 5.17 Reporting & Analytics — InventoryReportSnapshot form.

Only the generation knobs are fields: ``tenant``, the IRS- number, the
generated-by user and the computed ``summary`` are assigned by the view after
the engine runs. The location FK is tenant-scoped by ``TenantModelForm`` and
re-checked by ``_reject_foreign`` — a narrowed <select> is UX, not a boundary.
"""
from django import forms
from django.core.exceptions import ValidationError

from apps.inventory.forms._common import TenantModelForm, _reject_foreign
from apps.inventory.models import InventoryReportSnapshot


class ReportSnapshotForm(TenantModelForm):
    class Meta:
        model = InventoryReportSnapshot
        fields = ["report_type", "title", "window_days", "location", "notes"]
        widgets = {"window_days": forms.NumberInput(attrs={"min": 1, "max": 3650})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Window only drives turnover/ABC; valuation/aging are whole-history.
        self.fields["window_days"].help_text = (
            "Trailing window in days — used by Stock Turnover and ABC Analysis.")

    def clean_window_days(self):
        days = self.cleaned_data.get("window_days")
        if days is not None and not 1 <= days <= 3650:
            raise ValidationError("Window must be between 1 and 3650 days.")
        return days

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["location"])
        return cleaned
