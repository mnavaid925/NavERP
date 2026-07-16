"""HRM 3.4 Employee Offboarding — Exitinterview forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    ExitInterview,
)


class ExitInterviewForm(TenantModelForm):
    # SECURITY: `status` and `conducted_at` are excluded — both are advanced only by the complete /
    # skip workflow actions (which stamp/audit). A crafted POST must not be able to mark an interview
    # "completed" without going through the action.
    class Meta:
        model = ExitInterview
        fields = ["case", "interviewer", "scheduled_at", "mode",
                  "rating_job_satisfaction", "rating_management", "rating_compensation",
                  "rating_work_environment", "rating_growth_opportunities",
                  "rating_work_life_balance", "rating_culture", "rating_overall",
                  "primary_reason", "would_recommend", "would_rejoin",
                  "what_went_well", "what_to_improve", "additional_comments"]

    def clean(self):
        cleaned = super().clean()
        case = cleaned.get("case")
        # One exit interview per case (form-level — a skipped/no-show one can be superseded by
        # deleting it first). The tenant lives on the form, so this guard belongs here, not on the model.
        if case and self.tenant is not None:
            dupes = ExitInterview.objects.filter(tenant=self.tenant, case=case)
            if self.instance.pk:
                dupes = dupes.exclude(pk=self.instance.pk)
            if dupes.exists():
                self.add_error("case", "An exit interview already exists for this separation case.")
        return cleaned
