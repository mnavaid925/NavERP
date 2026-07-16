"""HRM 3.27 Communication Hub — build_survey_response_forms forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.forms.PersonalInformation._helpers import _ThemedForm


def build_survey_response_form(questions):
    """Assemble a plain themed Form with one field per survey question (rating -> a 0-10 select,
    single_choice -> a select of the question's options, text -> an optional textarea). Used by
    views.survey_respond — NOT a ModelForm, because SurveyResponse.answers is a JSON map keyed by
    question index. Fields are named `q_<index>` so the view can rebuild the {index: answer} map."""
    fields = {}
    for i, q in enumerate(questions or []):
        label = str(q.get("text") or f"Question {i + 1}")
        qtype = q.get("type")
        if qtype == "rating":
            fields[f"q_{i}"] = forms.ChoiceField(label=label, choices=[(str(n), str(n)) for n in range(11)])
        elif qtype == "single_choice":
            fields[f"q_{i}"] = forms.ChoiceField(label=label, choices=[(o, o) for o in (q.get("options") or [])])
        else:  # text
            fields[f"q_{i}"] = forms.CharField(label=label, required=False,
                                               widget=forms.Textarea(attrs={"rows": 2}))
    return type("SurveyResponseForm", (_ThemedForm,), fields)
