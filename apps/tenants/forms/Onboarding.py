"""tenants — Onboarding forms (split from apps/tenants/forms.py)."""
from apps.tenants.forms._common import *  # noqa: F401,F403
from apps.tenants.models import (
    Subscription,
)


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
