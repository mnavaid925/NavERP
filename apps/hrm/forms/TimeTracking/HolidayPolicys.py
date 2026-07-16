"""HRM 3.11 Time Tracking — HolidayPolicys forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    HolidayPolicy,
    PublicHoliday,
)


class HolidayPolicyForm(TenantModelForm):
    class Meta:
        model = HolidayPolicy
        fields = ["name", "location", "org_unit", "employee_type", "designation",
                  "is_default", "floating_holiday_quota", "holidays", "is_active", "description"]
        # `holidays` keeps the default SelectMultiple widget so TenantModelForm styles it as a
        # themed `.form-select` (CheckboxSelectMultiple has no matching theme class and renders
        # as an unstyled <ul>).
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # A policy only governs OPTIONAL (floating) holidays — narrow its pool to those (the base
        # form already tenant-scopes every FK/M2M queryset).
        # Only the holidays M2M needs narrowing (to optional holidays) — the base TenantModelForm
        # already tenant-scopes the org_unit/designation FKs, and Designation.Meta already orders by name.
        if self.tenant is not None and "holidays" in self.fields:
            self.fields["holidays"].queryset = (
                PublicHoliday.objects.filter(tenant=self.tenant, is_optional=True).order_by("date"))
