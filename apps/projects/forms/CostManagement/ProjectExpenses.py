"""Projects 7.4 — ProjectExpense form.

``status`` is OFF the form (verb-driven — post/void) and so is ``created_by`` (stamped in the
create view). ``currency`` is NOT passed to ``_reject_foreign``: ``accounting.Currency`` is a
GLOBAL table with no ``tenant`` column (L29) — ``TenantModelForm`` skips its scoping for the
same reason, and the create view supplies the initial from the project's active revision.
"""
from apps.projects.forms._common import *  # noqa: F401,F403
from apps.projects.forms._common import TenantModelForm, TenantUniqueMixin, _reject_foreign
from apps.projects.models import ProjectExpense


class ProjectExpenseForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = ProjectExpense
        fields = ["project", "control_account", "wbs_node", "entry_type", "source_kind",
                  "source_number", "vendor", "gl_account", "amount", "currency", "entry_date",
                  "description"]

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["project", "control_account", "wbs_node", "vendor",
                                        "gl_account"])
        return cleaned
