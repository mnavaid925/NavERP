"""Projects 7.1 — ProjectRequest forms.

``ProjectRequestForm`` covers intake + the business-case field set (bullet 2). Status and decision
are deliberately OFF the form: they are verb-driven so the who/when stamps stay trustworthy — a
row cannot be edited into "approved".

``currency`` is NOT passed to ``_reject_foreign``: ``accounting.Currency`` is a GLOBAL table with
no ``tenant`` column (L29), so comparing its tenant would raise ``AttributeError`` rather than
guard anything.
"""
from apps.projects.forms._common import *  # noqa: F401,F403
from apps.projects.forms._common import _reject_foreign, forms
from apps.projects.models import ProjectRequest


class ProjectRequestForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = ProjectRequest
        exclude = [
            "tenant", "number",            # auto
            "status", "decision",          # verb-driven
            "decided_by", "decided_at", "submitted_at",   # stamps
            "converted_project",           # set by the convert verb
            "created_by",                  # set in the view
        ]

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["org_unit", "source_opportunity"])
        return cleaned


class ProjectRequestDecisionForm(forms.Form):
    """The reason a request was rejected or sent back for information.

    Shared by the reject and return-for-information verbs so both stamp a reason the requester can
    act on. Required: a rejection with no stated reason is the single most common way an intake
    process loses the trust of the people feeding it.
    """

    reason = forms.CharField(
        widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        required=True,
        label="Reason",
    )
