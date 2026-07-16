"""HRM 3.19 Performance Review — Reviewtemplate forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    ReviewTemplate,
)


class ReviewTemplateForm(TenantModelForm):
    class Meta:
        model = ReviewTemplate
        fields = ["name", "review_type", "rating_scale_max", "include_goals", "is_anonymous",
                  "description", "is_active"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
        }
