"""HRM 3.27 Communication Hub — Suggestion forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    Suggestion,
)


class SuggestionForm(TenantModelForm):
    """Employee's suggestion. `employee` is resolved server-side by _ss_child_create; all workflow
    fields (status/approver/approved_at/decision_note/implementation_note/implemented_at) are excluded.
    Mirrors AssetRequestForm's shape."""

    class Meta:
        model = Suggestion
        fields = ["title", "body", "category", "is_anonymous"]
        widgets = {"body": forms.Textarea(attrs={"rows": 5})}
