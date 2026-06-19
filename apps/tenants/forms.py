"""Module 0.1 forms. Secret/derived/system fields are excluded (L20/L22): the
SubscriptionInvoice ``number`` (auto), ``paid_at``/``recorded_at``/``last_rotated_at``
(system-set), all ``stripe_*`` ids, and the EncryptionKey secret/hash."""
from django import forms

from apps.core.forms import TenantModelForm

from .models import (
    BrandingSetting,
    EncryptionKey,
    HealthMetric,
    Subscription,
    SubscriptionInvoice,
)


class SubscriptionForm(TenantModelForm):
    class Meta:
        model = Subscription
        fields = ["plan", "status", "billing_cycle", "amount", "seats", "started_on", "renews_on"]


class SubscriptionInvoiceForm(TenantModelForm):
    class Meta:
        model = SubscriptionInvoice
        fields = ["subscription", "status", "amount", "issued_on", "due_on"]


class BrandingSettingForm(TenantModelForm):
    class Meta:
        model = BrandingSetting
        fields = ["logo", "primary_color", "accent_color", "email_from_name", "email_footer"]
        widgets = {
            "primary_color": forms.TextInput(attrs={"type": "color", "class": "form-input"}),
            "accent_color": forms.TextInput(attrs={"type": "color", "class": "form-input"}),
        }


class EncryptionKeyForm(TenantModelForm):
    # Only the name is user-set; the secret is generated server-side and shown once (L20/L25).
    class Meta:
        model = EncryptionKey
        fields = ["name"]


class HealthMetricForm(TenantModelForm):
    class Meta:
        model = HealthMetric
        fields = ["metric", "value", "status"]


class OnboardingForm(forms.Form):
    """First-run wizard: pick a plan + set basic branding. Creates a trial subscription."""

    plan = forms.ChoiceField(choices=Subscription.PLAN_CHOICES,
                             widget=forms.Select(attrs={"class": "form-select"}))
    seats = forms.IntegerField(min_value=1, initial=5,
                               widget=forms.NumberInput(attrs={"class": "form-input"}))
    primary_color = forms.CharField(initial="#2563eb",
                                    widget=forms.TextInput(attrs={"type": "color", "class": "form-input"}))
    accent_color = forms.CharField(initial="#1d4ed8",
                                   widget=forms.TextInput(attrs={"type": "color", "class": "form-input"}))
    logo = forms.ImageField(required=False, widget=forms.ClearableFileInput(attrs={"class": "form-input"}))
