"""CRM 1.11 Customer Success & Retention — Surveys forms (split from apps/crm/forms.py)."""
from apps.crm.forms._common import *  # noqa: F401,F403
from apps.crm.models import (
    Survey,
)


class SurveyForm(TenantModelForm):
    class Meta:
        model = Survey
        # sent_at is stamped by the survey_send action (admin), not typed by hand.
        fields = ["account", "contact", "survey_type", "trigger", "related_case",
                  "score", "feedback_text"]

    def clean(self):
        # The model field caps at 10 (the NPS ceiling); enforce each type's real range here so a
        # CSAT can't be saved as 8 and then mis-classified as "satisfied".
        cleaned = super().clean()
        score, stype = cleaned.get("score"), cleaned.get("survey_type")
        limits = {"nps": (0, 10), "csat": (1, 5), "ces": (1, 7)}
        if score is not None and stype in limits:
            lo, hi = limits[stype]
            if not (lo <= score <= hi):
                self.add_error("score", f"Score must be {lo}–{hi} for {stype.upper()}.")
        return cleaned
