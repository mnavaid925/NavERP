from django import forms

from apps.ecommerce.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.ecommerce.models.CustomerProfile.CustomerAccountProfiles import CustomerAccountProfile
from apps.ecommerce.models.SubscriptionCommerce.CustomerSubscriptions import CustomerSubscription
from apps.ecommerce.models.SubscriptionCommerce.SubscriptionRetentionActions import SubscriptionRetentionAction


class SubscriptionRetentionActionForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = SubscriptionRetentionAction
        fields = [
            "subscription",
            "customer_profile",
            "trigger_type",
            "cancellation_reason",
            "churn_risk_score",
            "offered_action",
            "offer_discount_pct",
            "outcome",
            "notes",
        ]
        widgets = {
            "subscription": forms.Select(attrs={"class": "form-select"}),
            "customer_profile": forms.Select(attrs={"class": "form-select"}),
            "trigger_type": forms.Select(attrs={"class": "form-select"}),
            "cancellation_reason": forms.Select(attrs={"class": "form-select"}),
            "churn_risk_score": forms.NumberInput(
                attrs={"class": "form-input", "placeholder": "0.00", "step": "0.01", "min": 0, "max": 100}
            ),
            "offered_action": forms.Select(attrs={"class": "form-select"}),
            "offer_discount_pct": forms.NumberInput(
                attrs={"class": "form-input", "placeholder": "0.00", "step": "0.01", "min": 0, "max": 100}
            ),
            "outcome": forms.Select(attrs={"class": "form-select"}),
            "notes": forms.Textarea(
                attrs={
                    "class": "form-textarea",
                    "rows": 3,
                    "placeholder": "Customer sentiment, retention agent notes, feedback...",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["subscription"].queryset = CustomerSubscription.objects.filter(
                tenant=self.tenant
            ).order_by("-started_at")
            self.fields["customer_profile"].queryset = CustomerAccountProfile.objects.filter(
                tenant=self.tenant
            ).order_by("email")

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["subscription", "customer_profile"])
        return cleaned
