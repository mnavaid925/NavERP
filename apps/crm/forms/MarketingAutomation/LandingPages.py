"""CRM 1.3 Marketing Automation — LandingPages forms (split from apps/crm/forms.py)."""
from apps.crm.forms._common import *  # noqa: F401,F403
from apps.crm.models import (
    LandingPage,
)


class LandingPageForm(TenantModelForm):
    class Meta:
        model = LandingPage
        # WARNING: public_token (unguessable URL key) + submission_count are system-managed —
        # excluded so they can't be forged/reset via POST. `status` is excluded too: making a
        # page public (status=published) exposes a live web-to-lead URL, so that transition is
        # gated to admins via the dedicated landingpage_publish action, not this content form.
        fields = ["name", "campaign", "slug", "headline", "subheadline", "body",
                  "capture_phone", "capture_company", "capture_message", "cta_label",
                  "routing_owner", "lead_source", "owner"]
        widgets = {"body": forms.Textarea(attrs={"rows": 8})}


class PublicLeadForm(forms.Form):
    """The capture form on a public LandingPage — a plain Form (no tenant binding, no model
    mass-assignment). The view decides which optional fields are required from the page's
    capture toggles and builds the FormSubmission/Lead itself."""

    name = forms.CharField(max_length=255, widget=forms.TextInput(attrs={"class": "form-input"}))
    email = forms.EmailField(max_length=254, widget=forms.EmailInput(attrs={"class": "form-input"}))
    phone = forms.CharField(max_length=40, required=False, widget=forms.TextInput(attrs={"class": "form-input"}))
    company = forms.CharField(max_length=255, required=False, widget=forms.TextInput(attrs={"class": "form-input"}))
    message = forms.CharField(max_length=2000, required=False,
                              widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 4}))
