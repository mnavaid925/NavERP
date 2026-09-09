"""Projects 7.4 — CostControlAccount form.

``status`` IS on this form — the CA has no verbs, so planning/active/closed is ordinary CRUD
state. ``wbs_node`` is same-project enforced twice: as a form error here and in the model's
``clean()`` (a crafted POST skips no layer). ``gl_account`` is the ledger lens only (Ruling 6).
"""
from apps.projects.forms._common import *  # noqa: F401,F403
from apps.projects.forms._common import TenantModelForm, TenantUniqueMixin, _reject_foreign
from apps.projects.models import CostControlAccount


class CostControlAccountForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = CostControlAccount
        fields = ["project", "name", "code", "wbs_node", "gl_account", "contingency",
                  "percent_complete", "status", "note"]

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["project", "wbs_node", "gl_account"])
        return cleaned
