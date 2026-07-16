"""HRM 3.23 Learning Management (LMS) — Learningprogress forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    LearningProgress,
)


class LearningProgressForm(TenantModelForm):
    class Meta:
        model = LearningProgress
        fields = ["employee", "course", "learning_path", "status", "percent_complete",
                  "time_spent_minutes", "score", "passed", "attempt_count", "points_earned",
                  "started_at", "completed_at"]

    def clean(self):
        # Enforce the ("tenant","employee","course") uniqueness at the form level. Django's ModelForm
        # validate_unique() SKIPS any unique_together that involves an excluded field, and `tenant` is
        # not a form field — so the DB constraint would otherwise only surface as an IntegrityError 500
        # on the flat create path. Check it explicitly here instead.
        cleaned = super().clean()
        employee = cleaned.get("employee")
        course = cleaned.get("course")
        if self.tenant is not None and employee and course:
            dupes = LearningProgress.objects.filter(tenant=self.tenant, employee=employee, course=course)
            if self.instance and self.instance.pk:
                dupes = dupes.exclude(pk=self.instance.pk)
            if dupes.exists():
                raise forms.ValidationError("This employee already has a progress record for this course.")
        return cleaned
