"""Sales 8.13 — Forms for `CampaignAttribution`."""
from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError

from apps.accounts.models import User
from apps.core.forms import TenantModelForm
from apps.sales.forms._common import TenantUniqueMixin, _reject_foreign
from apps.sales.models.MarketingAlignment.AttributionTouchpoints import (
    AttributionTouchpoint,
)
from apps.sales.models.MarketingAlignment.CampaignAttributions import (
    CampaignAttribution,
)


class CampaignAttributionForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = CampaignAttribution
        fields = [
            "touchpoint",
            "attribution_model",
            "credit_pct",
            "attributed_revenue",
            "attributed_cost",
            "status",
            "computed_on",
            "computed_by",
            "notes",
        ]
        widgets = {
            "touchpoint": forms.Select(attrs={"class": "form-select"}),
            "attribution_model": forms.Select(attrs={"class": "form-select"}),
            "credit_pct": forms.NumberInput(
                attrs={"class": "form-input", "step": "0.01", "min": 0, "max": 100}
            ),
            "attributed_revenue": forms.NumberInput(
                attrs={"class": "form-input", "step": "0.01", "min": 0}
            ),
            "attributed_cost": forms.NumberInput(
                attrs={"class": "form-input", "step": "0.01", "min": 0}
            ),
            "status": forms.Select(attrs={"class": "form-select"}),
            "computed_on": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "computed_by": forms.Select(attrs={"class": "form-select"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["touchpoint"].queryset = (
                AttributionTouchpoint.objects.filter(tenant=self.tenant)
                .select_related("campaign", "lead", "opportunity")
                .order_by("-touch_date")
            )
            self.fields["computed_by"].queryset = User.objects.filter(
                tenant=self.tenant
            ).order_by("username")

    def clean(self):
        cleaned_data = super().clean()
        _reject_foreign(self, cleaned_data, ["touchpoint", "computed_by"])

        model = cleaned_data.get("attribution_model")
        credit = cleaned_data.get("credit_pct")
        if model == "custom" and (credit is None or credit == Decimal("0.00")):
            raise ValidationError(
                {
                    "credit_pct": (
                        "A custom attribution model must carry an explicit "
                        "credit percentage."
                    )
                }
            )
        return cleaned_data
