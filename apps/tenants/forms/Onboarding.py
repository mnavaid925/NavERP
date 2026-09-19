"""tenants — Onboarding forms (split from apps/tenants/forms.py)."""
from apps.core.models import DOMAIN

from apps.tenants.forms._common import *  # noqa: F401,F403
from apps.tenants.models import (
    Subscription,
)


class OnboardingForm(forms.Form):
    """First-run wizard: pick a plan + set basic branding. Creates a trial subscription.

    Also collects the 0.1 "domain provisioning" value (``core.Tenant.domain``). CharField strips
    whitespace in ``to_python`` — i.e. BEFORE the model's DOMAIN validator runs — so a pasted
    " acme.example.com " is accepted rather than rejected for its spaces.
    """

    plan = forms.ChoiceField(choices=Subscription.PLAN_CHOICES,
                             widget=forms.Select(attrs={"class": "form-select"}))
    seats = forms.IntegerField(min_value=1, initial=5,
                               widget=forms.NumberInput(attrs={"class": "form-input"}))
    domain = forms.CharField(
        required=False,
        max_length=253,
        validators=[DOMAIN],
        label="Custom domain",
        help_text="Optional. e.g. acme.example.com — leave blank to use your NavERP subdomain.",
        widget=forms.TextInput(attrs={"class": "form-input", "placeholder": "acme.example.com"}),
    )
    primary_color = forms.CharField(initial="#2563eb",
                                    widget=forms.TextInput(attrs={"type": "color", "class": "form-input"}))
    accent_color = forms.CharField(initial="#1d4ed8",
                                   widget=forms.TextInput(attrs={"type": "color", "class": "form-input"}))
    logo = forms.ImageField(required=False, widget=forms.ClearableFileInput(attrs={"class": "form-input"}))
