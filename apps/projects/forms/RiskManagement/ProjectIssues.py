"""Projects 7.5 — ProjectIssue form + the resolve verb's companion form.

``status``, ``root_cause``, ``resolution_note``, ``resolved_by``, ``resolved_at``,
``escalation_level``, ``escalated_to``, ``escalated_at`` and ``created_by`` are OFF the model form:
the lifecycle is verb-driven (escalate / resolve / close), so the issue log keeps its evidence
stamps. ``IssueResolutionForm`` is the ``iss_resolve`` verb's body — a plain ``forms.Form`` (not a
ModelForm) so the root cause and the resolution note are written by the verb that also stamps
``resolved_by``/``resolved_at``, never by a generic edit.

``TenantUniqueMixin`` is mixed in FIRST: ``ProjectIssue.clean()`` compares two chosen FKs' project
against ``self.project``, and the mixin is what stamps ``instance.tenant`` before ``full_clean()``
runs on CREATE (without it every create is falsely rejected as cross-tenant).
"""
from apps.projects.forms._common import *  # noqa: F401,F403
from apps.projects.forms._common import TenantModelForm, TenantUniqueMixin, _reject_foreign
from apps.projects.models import ProjectIssue


class ProjectIssueForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = ProjectIssue
        fields = ["project", "wbs_node", "risk", "title", "description", "issue_type", "severity",
                  "owner", "raised_by", "identified_date", "due_date", "lessons_learned"]

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["project", "wbs_node", "risk", "owner", "raised_by"])
        return cleaned


class IssueResolutionForm(forms.Form):
    """The ``iss_resolve`` verb's body: the root cause (optional) and the resolution (required)."""

    root_cause = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Why this issue happened — the input the monitoring page's lessons lens reads.")
    resolution_note = forms.CharField(
        required=True, widget=forms.Textarea(attrs={"rows": 3}),
        help_text="What was done to resolve it. Required — a resolved issue must say how.")
