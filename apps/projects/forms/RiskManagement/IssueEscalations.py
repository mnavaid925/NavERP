"""Projects 7.5 — IssueEscalation form.

``tenant``, ``number``, ``escalated_by``, ``escalated_at``, ``resolved_at`` and ``created_by`` are
OFF the model form: ``escalated_at`` is stamped on insert, ``escalated_by`` / ``created_by`` are
written by the view, and the row is appended by ``iss_escalate`` or this register's own create — so
the escalation trail keeps its timestamps.

``level`` is declared explicitly as a ``TypedChoiceField`` over ``IssueEscalation.LEVEL_CHOICES``
(the register's single level vocabulary) rather than left as the model's bare 1–4 integer input.

``TenantUniqueMixin`` is mixed in FIRST (contract §3): ``issue`` and ``target_user`` are both
tenant-scoped FKs, and the mixin stamps ``instance.tenant`` before ``full_clean()`` runs on CREATE
— without it every create is falsely rejected as cross-tenant. ``_reject_foreign`` re-checks both
FKs, because a narrowed ``<select>`` is UX, not an authorization boundary.

``issue`` stays REQUIRED on purpose: the inline escalate form on the issue detail page is
issue-scoped by its URL, so ``iss_escalate`` injects the pk into the bound POST data rather than
loosening the field (a null-issue escalation row would be a real integrity hole).
"""
from apps.projects.forms._common import *  # noqa: F401,F403
from apps.projects.forms._common import TenantModelForm, TenantUniqueMixin, _reject_foreign
from apps.projects.models import IssueEscalation


class IssueEscalationForm(TenantUniqueMixin, TenantModelForm):
    level = forms.TypedChoiceField(
        choices=IssueEscalation.LEVEL_CHOICES, coerce=int,
        help_text="The tier the issue is being pushed to.")

    class Meta:
        model = IssueEscalation
        fields = ["issue", "level", "target_role", "target_user", "reason", "outcome"]

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["issue", "target_user"])
        return cleaned
