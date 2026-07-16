"""HRM 3.3 Employee Onboarding — Program forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    OnboardingProgram,
)


class OnboardingProgramForm(TenantModelForm):
    # SECURITY: `status` and `completed_at` are NOT form fields — a program starts at the model
    # default "draft" and both are advanced only by the privileged workflow actions
    # (activate/complete/cancel). Exposing them would let a crafted POST skip the workflow.
    class Meta:
        model = OnboardingProgram
        fields = ["employee", "template", "start_date", "buddy", "welcome_message",
                  "welcome_video_url", "first_day_notes", "notes"]

    def clean(self):
        cleaned = super().clean()
        employee = cleaned.get("employee")
        buddy = cleaned.get("buddy")
        if employee and buddy and employee == buddy:
            self.add_error("buddy", "An employee cannot be their own onboarding buddy.")
        # One onboarding program per employee per tenant — the form holds the tenant (the view
        # sets it on the instance only after save, so this guard lives here, not on the model).
        if employee and self.tenant is not None:
            dupes = OnboardingProgram.objects.filter(tenant=self.tenant, employee=employee)
            if self.instance.pk:
                dupes = dupes.exclude(pk=self.instance.pk)
            if dupes.exists():
                self.add_error("employee", "This employee already has an onboarding program.")
        return cleaned
