"""CRM 1.11 Customer Success & Retention — OnboardingTemplates forms (split from apps/crm/forms.py)."""
from apps.crm.forms._common import *  # noqa: F401,F403
from apps.crm.models import (
    OnboardingTemplate,
    OnboardingTemplateStep,
)


class OnboardingTemplateForm(TenantModelForm):
    class Meta:
        model = OnboardingTemplate
        fields = ["name", "description", "is_active"]


class OnboardingTemplateStepForm(TenantModelForm):
    """Inline on the OnboardingTemplate detail page; tenant/template set in the view."""

    class Meta:
        model = OnboardingTemplateStep
        fields = ["title", "description", "offset_days"]  # order auto-assigned in the view
