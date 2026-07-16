"""HRM 3.24 Training Administration — Trainingcertificate forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    TrainingCertificate,
    TrainingCourse,
)


class TrainingCertificateForm(TenantModelForm):
    # number/verification_code/expires_on are auto (save()); status/revoked_reason are workflow-owned.
    class Meta:
        model = TrainingCertificate
        fields = ["employee", "course", "source_attendance", "source_progress", "title", "issued_on"]
        widgets = {"issued_on": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "course" in self.fields and self.tenant is not None:
            # Only certification-granting courses — but keep an already-linked course selectable on edit.
            qs = TrainingCourse.objects.filter(tenant=self.tenant).filter(
                Q(is_certification=True) | Q(pk=getattr(self.instance, "course_id", None)))
            self.fields["course"].queryset = qs.order_by("title")
