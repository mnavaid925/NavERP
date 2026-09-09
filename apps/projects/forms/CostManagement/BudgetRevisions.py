"""Projects 7.4 — BudgetRevision forms.

``status`` and every stamp (``requested_at``, ``decided_by/_at``, ``activated_at``) are OFF the
form — they are verb-driven so the who/when trail stays trustworthy (the ``ProjectRequest``
precedent). ``decision_notes`` is excluded for a stronger reason: it is a gated verb's written
evidence, and leaving it POST-settable through the ungated edit form would let any member rewrite
the admin's stated rejection rationale.

``currency`` is NOT passed to ``_reject_foreign``: ``accounting.Currency`` is a GLOBAL table with
no ``tenant`` column (L29), so comparing its tenant would raise ``AttributeError`` rather than
guard anything.
"""
from apps.projects.forms._common import *  # noqa: F401,F403
from apps.projects.forms._common import _reject_foreign, forms
from apps.projects.models import BudgetRevision


class BudgetRevisionForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = BudgetRevision
        fields = ["project", "revision_no", "title", "currency", "reason", "impact_note",
                  "schedule_impact_note", "requested_by"]

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["project", "requested_by"])
        return cleaned


class BudgetRevisionDecisionForm(forms.Form):
    """The reason a revision was rejected — required: a rejection with no stated reason is how a
    change-control process loses the trust of the people feeding it (the ``ProjectRequest`` mirror,
    with the field named after the model column it fills)."""

    decision_notes = forms.CharField(
        widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        required=True,
        label="Reason",
    )
