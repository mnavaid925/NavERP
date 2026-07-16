"""HRM 3.22 Training Management — Trainingcourse forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    TrainingCourse,
)


# ----------------------------------------------------------------------- 3.22 Training Management
class TrainingCourseForm(TenantModelForm):
    # Excludes tenant + auto number. prerequisite_course is tenant-scoped (by TenantModelForm) and,
    # on edit, must not offer the course itself as its own prerequisite.
    class Meta:
        model = TrainingCourse
        fields = ["title", "description", "category", "delivery_mode", "provider_type", "duration_hours",
                  "is_certification", "certification_name", "certification_validity_months",
                  "prerequisite_course", "default_capacity", "is_active"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "prerequisite_course" in self.fields and self.tenant is not None:
            qs = TrainingCourse.objects.filter(tenant=self.tenant).order_by("title")
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)   # a course can't be its own prerequisite
            self.fields["prerequisite_course"].queryset = qs
