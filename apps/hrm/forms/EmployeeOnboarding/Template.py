"""HRM 3.3 Employee Onboarding — Template forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    OnboardingTemplate,
)


# ----------------------------------------------------------------------- 3.3 Employee Onboarding
class OnboardingTemplateForm(TenantModelForm):
    class Meta:
        model = OnboardingTemplate
        fields = ["name", "description", "designation", "is_active"]
