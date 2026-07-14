"""CRM 1.11 Customer Success & Retention — OnboardingPlans forms (split from apps/crm/forms.py)."""
from apps.crm.forms._common import *  # noqa: F401,F403
from apps.crm.models import (
    OnboardingPlan,
    OnboardingStep,
)


class OnboardingPlanForm(TenantModelForm):
    class Meta:
        model = OnboardingPlan
        fields = ["account", "name", "status", "target_date", "owner", "description"]


class OnboardingStepForm(TenantModelForm):
    """Inline on the OnboardingPlan detail page; tenant/plan set in the view."""

    class Meta:
        model = OnboardingStep
        fields = ["title", "description", "assignee", "due_date"]  # order auto-assigned in the view
