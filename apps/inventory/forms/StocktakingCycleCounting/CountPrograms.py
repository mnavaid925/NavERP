"""Inventory 5.11 Stocktaking & Cycle Counting — forms."""
from django import forms

from apps.inventory.forms._common import TenantModelForm, TenantUniqueMixin, _reject_foreign
from apps.inventory.models import CountProgram, PhysicalInventory


class CountProgramForm(TenantUniqueMixin, TenantModelForm):
    """A recurring count cadence. The mixin validates (tenant, name) and stamps
    instance.tenant for clean()'s foreign-location check on create."""

    class Meta:
        model = CountProgram
        fields = ["name", "location", "abc_class", "frequency", "weekday",
                  "day_of_month", "count_method", "is_active", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            from apps.scm.models import Location
            self.fields["location"].queryset = (
                Location.objects.filter(tenant=self.tenant)
                .exclude(location_type="warehouse").order_by("code"))

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["location"])
        return cleaned


class PhysicalInventoryForm(TenantUniqueMixin, TenantModelForm):
    """The freeze event's planning fields only — status/freeze are verb-driven."""

    class Meta:
        model = PhysicalInventory
        fields = ["warehouse", "scheduled_date", "notes"]
        widgets = {"scheduled_date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            from apps.scm.models import Location
            self.fields["warehouse"].queryset = (
                Location.objects.filter(tenant=self.tenant,
                                        location_type="warehouse").order_by("code"))

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["warehouse"])
        return cleaned


#: Variance report GET choices shared by view + template.
VARIANCE_STATUS_CHOICES = [
    ("counted", "Counted (unreconciled)"),
    ("reconciled", "Reconciled"),
    ("open", "All open sheets"),
]
