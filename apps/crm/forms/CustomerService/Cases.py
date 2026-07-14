"""CRM 1.4 Customer Service & Support — Cases forms (split from apps/crm/forms.py)."""
from apps.crm.forms._common import *  # noqa: F401,F403
from apps.crm.models import (
    Case,
    CaseComment,
)


class CaseForm(TenantModelForm):
    class Meta:
        model = Case
        # WARNING: first_response_due/first_responded_at/resolution_due/closed_at/public_token +
        # satisfaction_* are system-managed (SLA save() / portal / public CSAT page). Excluded so a
        # member can't forge SLA timers, back-date a close, or fake a satisfaction score via POST.
        fields = ["subject", "account", "contact", "type", "priority", "status", "origin",
                  "sla_policy", "owner", "due_at", "description"]


class CaseCommentForm(TenantModelForm):
    """Inline on the case detail page; tenant/case/author set in the view."""

    class Meta:
        model = CaseComment
        fields = ["body", "is_public"]
