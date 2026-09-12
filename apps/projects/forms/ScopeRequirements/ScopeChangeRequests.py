"""Projects 7.7 — ScopeChangeRequest form + the companion form the reject verb binds.

``status``, ``decision_note``, ``decided_by``/``decided_at`` and ``implemented_at`` are OFF the
model form: the CCB decision is minted by the audited ``scr_approve`` / ``scr_reject`` verbs (both
admin-gated), so the register keeps its approval trail.

``TenantUniqueMixin`` is mixed in FIRST because ``ScopeChangeRequest.clean()`` compares both the
chosen requirement's and the chosen risk's project against ``self.project``.
"""
from apps.projects.forms._common import *  # noqa: F401,F403
from apps.projects.forms._common import TenantModelForm, TenantUniqueMixin, _reject_foreign
from apps.projects.models import ScopeChangeRequest


class ScopeChangeForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = ScopeChangeRequest
        fields = ["project", "requirement", "risk", "title", "description", "justification",
                  "source", "priority", "schedule_impact_days", "cost_impact", "quality_impact",
                  "quality_note", "requested_by"]

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["project", "requirement", "risk", "requested_by"])
        return cleaned


class ChangeRejectionForm(forms.Form):
    """The ``scr_reject`` verb's body: the board's reason for turning the change down."""

    decision_note = forms.CharField(
        required=True, widget=forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
        help_text="The board's reason for rejecting the change. Stored on the register row.")
