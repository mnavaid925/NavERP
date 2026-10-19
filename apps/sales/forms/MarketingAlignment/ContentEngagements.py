"""Sales 8.13 — Forms for `ContentEngagement`."""
from django import forms

from apps.accounting.models import Currency
from apps.core.forms import TenantModelForm
from apps.core.models import Party
from apps.crm.models import Campaign, Lead
from apps.sales.forms._common import TenantUniqueMixin, _reject_foreign
from apps.sales.models.MarketingAlignment.ContentEngagements import ContentEngagement
from apps.sales.models.SalesEnablement.EnablementContents import EnablementContent


class ContentEngagementForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = ContentEngagement
        fields = [
            "content",
            "account",
            "lead",
            "campaign",
            "engagement_type",
            "engagement_channel",
            "engagement_score",
            "revenue_attributed",
            "currency",
            "engaged_at",
            "notes",
        ]
        widgets = {
            "content": forms.Select(attrs={"class": "form-select"}),
            "account": forms.Select(attrs={"class": "form-select"}),
            "lead": forms.Select(attrs={"class": "form-select"}),
            "campaign": forms.Select(attrs={"class": "form-select"}),
            "engagement_type": forms.Select(attrs={"class": "form-select"}),
            "engagement_channel": forms.Select(attrs={"class": "form-select"}),
            "engagement_score": forms.NumberInput(
                attrs={"class": "form-input", "min": 0, "max": 100}
            ),
            "revenue_attributed": forms.NumberInput(
                attrs={"class": "form-input", "step": "0.01", "min": 0}
            ),
            "currency": forms.Select(attrs={"class": "form-select"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["content"].queryset = (
                EnablementContent.objects.filter(tenant=self.tenant, is_active=True)
                .order_by("title")
            )
            self.fields["account"].queryset = (
                Party.objects.filter(tenant=self.tenant, roles__role="customer")
                .distinct()
                .order_by("name")
            )
            self.fields["lead"].queryset = Lead.objects.filter(
                tenant=self.tenant
            ).order_by("name")
            self.fields["campaign"].queryset = Campaign.objects.filter(
                tenant=self.tenant
            ).order_by("name")
            self.fields["currency"].queryset = Currency.objects.order_by("code")

    def clean(self):
        cleaned_data = super().clean()
        _reject_foreign(
            self,
            cleaned_data,
            ["content", "account", "lead", "campaign", "currency"],
        )
        return cleaned_data
