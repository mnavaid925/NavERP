"""Sales 8.13 — Forms for `AttributionTouchpoint`."""
from django import forms

from apps.accounting.models import Currency
from apps.core.forms import TenantModelForm
from apps.crm.models import Campaign, Lead, Opportunity
from apps.sales.forms._common import TenantUniqueMixin, _reject_foreign
from apps.sales.models.MarketingAlignment.AttributionTouchpoints import (
    AttributionTouchpoint,
)


class AttributionTouchpointForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = AttributionTouchpoint
        fields = [
            "campaign",
            "lead",
            "opportunity",
            "channel",
            "touch_type",
            "touch_date",
            "touch_position",
            "cost",
            "engagement_value",
            "currency",
            "source_reference",
            "notes",
        ]
        widgets = {
            "campaign": forms.Select(attrs={"class": "form-select"}),
            "lead": forms.Select(attrs={"class": "form-select"}),
            "opportunity": forms.Select(attrs={"class": "form-select"}),
            "channel": forms.Select(attrs={"class": "form-select"}),
            "touch_type": forms.Select(attrs={"class": "form-select"}),
            "touch_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "touch_position": forms.Select(attrs={"class": "form-select"}),
            "cost": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": 0}),
            "engagement_value": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": 0}),
            "currency": forms.Select(attrs={"class": "form-select"}),
            "source_reference": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "e.g. utm_source=linkedin&utm_medium=paid_social"}
            ),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["campaign"].queryset = Campaign.objects.filter(
                tenant=self.tenant
            ).order_by("name")
            self.fields["lead"].queryset = Lead.objects.filter(
                tenant=self.tenant
            ).order_by("name")
            self.fields["opportunity"].queryset = Opportunity.objects.filter(
                tenant=self.tenant
            ).order_by("-created_at")
            self.fields["currency"].queryset = Currency.objects.order_by("code")

    def clean(self):
        cleaned_data = super().clean()
        _reject_foreign(
            self,
            cleaned_data,
            ["campaign", "lead", "opportunity", "currency"],
        )
        return cleaned_data
