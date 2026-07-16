"""HRM 3.7 Interview Process — FeedbackCriterions forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    FeedbackCriterion,
)


class FeedbackCriterionForm(TenantModelForm):
    # Inline-add on the feedback detail hub; `feedback` is set in the view.
    class Meta:
        model = FeedbackCriterion
        fields = ["criterion_name", "rating", "notes"]
        widgets = {"rating": forms.NumberInput(attrs={"min": 1, "max": 5})}

    def clean_rating(self):
        rating = self.cleaned_data.get("rating")
        if rating is not None and not (1 <= rating <= 5):
            raise forms.ValidationError("Rating must be between 1 and 5.")
        return rating
