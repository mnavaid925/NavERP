"""Projects 7.5 — RiskResponseAction form.

``status``, ``completed_at`` and ``created_by`` are OFF the model form: the lifecycle is
verb-driven (``rra_complete``), so the action keeps its completion stamp. The ``risk`` select is
what pins the action to the register row whose strategy it executes.

``TenantUniqueMixin`` is mixed in FIRST — the house pattern for every ``TenantNumbered`` form — so
``instance.tenant`` is stamped before ``full_clean()`` runs on CREATE. ``_reject_foreign`` then
re-checks the two tenant-scoped FKs a crafted POST could point at another workspace: the narrowed
``<select>`` is UX, not an authorization boundary.
"""
from apps.projects.forms._common import *  # noqa: F401,F403
from apps.projects.forms._common import TenantModelForm, TenantUniqueMixin, _reject_foreign
from apps.projects.models import RiskResponseAction


class RiskResponseActionForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = RiskResponseAction
        fields = ["risk", "title", "description", "strategy", "owner", "due_date", "cost",
                  "trigger", "residual_probability", "residual_impact"]

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["risk", "owner"])
        return cleaned
