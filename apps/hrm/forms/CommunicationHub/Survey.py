"""HRM 3.27 Communication Hub — Survey forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    EmployeeProfile,
    Objective,
    Survey,
    SurveyActionPlan,
)
# star-imports skip underscore names -> import the privates explicitly
from apps.hrm.models import Survey as _Survey


class SurveyForm(TenantModelForm):
    """Admin-authored survey. `questions` is a JSON list validated by clean_questions (structure, not
    just 'valid JSON'). `status`/`author` are workflow-owned and excluded."""

    class Meta:
        model = Survey
        fields = ["title", "description", "questions", "is_anonymous", "opens_at", "closes_at"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 2}),
            "questions": forms.Textarea(attrs={"rows": 8, "class": "form-textarea",
                                               "placeholder": '[{"text": "How likely are you to recommend us?", "type": "rating"},\n {"text": "What should we improve?", "type": "text"},\n {"text": "Preferred work mode?", "type": "single_choice", "options": ["Remote", "Hybrid", "Onsite"]}]'}),
        }

    def clean_questions(self):
        questions = self.cleaned_data.get("questions")
        if not isinstance(questions, list) or not questions:
            raise forms.ValidationError("Add at least one question as a JSON list of objects.")
        valid_types = {"rating", "text", "single_choice"}
        for idx, item in enumerate(questions, start=1):
            if not isinstance(item, dict) or not str(item.get("text", "")).strip():
                raise forms.ValidationError(f"Question {idx}: each entry needs a non-empty \"text\".")
            qtype = item.get("type")
            if qtype not in valid_types:
                raise forms.ValidationError(
                    f"Question {idx}: \"type\" must be one of rating, text, single_choice.")
            if qtype == "single_choice" and not (isinstance(item.get("options"), list) and item["options"]):
                raise forms.ValidationError(
                    f"Question {idx}: a single_choice question needs a non-empty \"options\" list.")
        return questions


class SurveyActionPlanForm(TenantModelForm):
    # tenant/number/completed_at are set/managed server-side.
    class Meta:
        model = SurveyActionPlan
        fields = ["survey", "title", "focus_area", "owner", "department", "description",
                  "related_objective", "target_date", "status"]
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            # NOTE: survey is NOT filtered to status="closed" — an already-linked plan whose survey later
            # reopens must still render its selected option. The help_text conveys the intent instead.
            if "survey" in self.fields:
                self.fields["survey"].queryset = (
                    _Survey.objects.filter(tenant=self.tenant).order_by("-created_at"))
            if "owner" in self.fields:
                self.fields["owner"].queryset = (
                    EmployeeProfile.objects.filter(tenant=self.tenant).select_related("party")
                    .order_by("party__name"))
            if "department" in self.fields:
                self.fields["department"].queryset = (
                    OrgUnit.objects.filter(tenant=self.tenant, kind="department").order_by("name"))
            if "related_objective" in self.fields:
                self.fields["related_objective"].queryset = (
                    Objective.objects.filter(tenant=self.tenant).order_by("title"))
