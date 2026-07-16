"""HRM 3.24 Training Administration — Trainingfeedback forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    TrainingFeedback,
)


class TrainingFeedbackForm(TenantModelForm):
    # `attendance` is set from the URL in the nested create view (excluded here). ratings 1-5 via
    # model MinValue/MaxValue validators; the form clean() only carries the (tenant, attendance) guard.
    class Meta:
        model = TrainingFeedback
        fields = ["overall_rating", "content_rating", "trainer_rating", "would_recommend",
                  "comments", "is_anonymous"]
        widgets = {"comments": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"})}

    def clean(self):
        # (tenant, attendance) unique_together — BOTH fields form-excluded, so validate_unique() skips
        # it entirely; the nested create view sets self.instance.attendance before is_valid().
        cleaned = super().clean()
        attendance_id = getattr(self.instance, "attendance_id", None)
        if self.tenant is not None and attendance_id:
            dupes = TrainingFeedback.objects.filter(tenant=self.tenant, attendance_id=attendance_id)
            if self.instance and self.instance.pk:
                dupes = dupes.exclude(pk=self.instance.pk)
            if dupes.exists():
                raise forms.ValidationError("Feedback has already been submitted for this attendance record.")
        return cleaned
