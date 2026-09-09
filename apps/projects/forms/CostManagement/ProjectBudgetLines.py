"""Projects 7.4 — ProjectBudgetLine form.

``budget_revision`` and ``project`` are both required; the model's ``clean()`` re-checks that
the line's project, WBS node and control account all belong to the revision's project, so a
crafted POST that mixes workspaces' rows fails on the model layer even if the scoped dropdowns
were bypassed.
"""
from apps.projects.forms._common import *  # noqa: F401,F403
from apps.projects.forms._common import TenantModelForm, TenantUniqueMixin, _reject_foreign
from apps.projects.models import ProjectBudgetLine


class ProjectBudgetLineForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = ProjectBudgetLine
        fields = ["budget_revision", "project", "category", "wbs_node", "control_account",
                  "gl_account", "amount", "note"]

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["budget_revision", "project", "wbs_node",
                                        "control_account", "gl_account"])
        return cleaned
