"""HRM 3.23 Learning Management (LMS) — Learningpathitem forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    LearningPathItem,
    TrainingCourse,
)


class LearningPathItemForm(TenantModelForm):
    # `path` is set from the URL in the nested create view; scope `course` to the tenant's active courses.
    class Meta:
        model = LearningPathItem
        fields = ["course", "sequence", "is_mandatory"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "course" in self.fields and self.tenant is not None:
            self.fields["course"].queryset = (
                TrainingCourse.objects.filter(tenant=self.tenant, is_active=True).order_by("title"))

    def clean(self):
        # Enforce the ("tenant","path","course") uniqueness at the form level — like LearningProgressForm,
        # both `tenant` and `path` are excluded from the form, so Django's validate_unique() SKIPS the
        # unique_together and a re-added course would only surface as an IntegrityError 500. `path` is set
        # on the instance by the nested create view (or loaded on edit).
        cleaned = super().clean()
        course = cleaned.get("course")
        path_id = getattr(self.instance, "path_id", None)
        if self.tenant is not None and path_id and course:
            dupes = LearningPathItem.objects.filter(tenant=self.tenant, path_id=path_id, course=course)
            if self.instance and self.instance.pk:
                dupes = dupes.exclude(pk=self.instance.pk)
            if dupes.exists():
                raise forms.ValidationError("This course is already in this path.")
        return cleaned
