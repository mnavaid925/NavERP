"""HRM 3.19 Performance Review — Reviewrating forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    ReviewRating,
)


class ReviewRatingForm(TenantModelForm):
    # review is set from the URL in the nested create view; number is auto-assigned.
    class Meta:
        model = ReviewRating
        fields = ["criterion_label", "criterion_category", "rating_value", "weight", "comment"]
        widgets = {
            "comment": forms.Textarea(attrs={"rows": 2, "class": "form-textarea"}),
        }
