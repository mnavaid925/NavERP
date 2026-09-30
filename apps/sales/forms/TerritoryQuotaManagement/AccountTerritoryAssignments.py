"""Sales 8.7 — the account-to-territory assignment ledger form (`TAS-`).

One row says "this account sat in this territory for this window". It is a **ledger, not a
pointer**, so a rebalance closes the current row (`effective_to`) and opens a new one instead of
overwriting — which is why the form exposes both dates and says so on `effective_to`.

**OWNERSHIP (L29/L36/L37).** ``territory`` is `crm.Territory` and ``account`` is `core.Party`;
both masters are read-only to 8.7. 8.7 EXTENDS them and declares neither ``Territory`` nor
``SalesQuota`` again — see ``apps/sales/models/TerritoryQuotaManagement/__init__.py``.

Excluded from ``Meta.fields``, with the reason for each:

* ``tenant`` — set by ``TenantUniqueMixin`` from the view's ``request.tenant``, never from input.
* ``number`` — ``editable=False`` on ``TenantNumbered``; allocated by ``next_number`` (L22).
* ``assigned_by`` — **FROZEN EVIDENCE**, ``editable=False``; stamped once by the view from
  ``request.user``. Who made an assignment is a fact about a decision, not a field a later edit
  may rewrite (L22).
* ``created_at`` / ``updated_at`` — ``auto_now*`` stamps.

``rule`` and ``assignment_source`` are left to the model's own ``clean()`` rather than toggled
here: the pairing between them is a *rule about a row*, and a form that flipped the two widgets
on the client would still have to be re-checked on the server to be worth anything.
"""
from django import forms

from apps.core.models import Party
from apps.sales.forms._common import (
    TenantModelForm,
    TenantUniqueMixin,
    _reject_foreign,
    tenant_territories,
)
from apps.sales.models.TerritoryQuotaManagement.AccountTerritoryAssignments import (
    AccountTerritoryAssignment,
)
from apps.sales.models.TerritoryQuotaManagement.TerritoryRules import TerritoryRule


class AccountTerritoryAssignmentForm(TenantUniqueMixin, TenantModelForm):
    """Record one account's placement in one territory for a window of time."""

    class Meta:
        model = AccountTerritoryAssignment
        # Excluded, with the reason for each — see the module docstring.
        fields = [
            "account",
            "territory",
            "rule",
            "owner",
            "alignment_type",
            "assignment_source",
            "effective_from",
            "effective_to",
            "notes",
        ]
        widgets = {
            "notes": forms.Textarea(attrs={
                "class": "form-textarea",
                "rows": 3,
                "placeholder": "Why this account sits here, and what would move it elsewhere...",
            }),
        }
        help_texts = {
            "account": (
                "Organizations only — a person is not assignable to a territory. Dropdown narrowed; "
                "the model refuses one either way."
            ),
            "territory": "The CRM 1.2 territory. 8.7 extends CRM's territory; it never replaces it.",
            "rule": "Only a rule-sourced assignment names the rule that made it.",
            "alignment_type": "An account has at most one active primary territory.",
            "assignment_source": (
                "A rule-sourced assignment must name its rule; the other three sources must not. "
                "A rule run writes its own rows."
            ),
            "effective_to": (
                "Blank means CURRENT. A rebalance closes this row and opens a new one, so last "
                "March stays answerable after the territories have been re-cut."
            ),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)
        # A None tenant must render an EMPTY dropdown. TenantModelForm only narrows when a tenant
        # is given, so without these two lines a tenant-less form would offer every party and
        # every rule in the platform (the ForecastSubmissionForm rule).
        if self.tenant is None:
            self.fields["account"].queryset = Party.objects.none()
            self.fields["rule"].queryset = TerritoryRule.objects.none()
        else:
            # `core.Party` holds both kinds, so the dropdown narrows to organizations; the
            # model's clean() is the guarantee behind the convenience.
            self.fields["account"].queryset = (
                Party.objects.filter(tenant=self.tenant, kind="organization").order_by("name")
            )
            # Only ACTIVE rules are selectable: a retired rule's assignments stay in the ledger,
            # but no new row may claim one produced it.
            self.fields["rule"].queryset = (
                TerritoryRule.objects
                .filter(tenant=self.tenant, is_active=True)
                .order_by("priority", "name")
            )
        self.fields["territory"].queryset = tenant_territories(self.tenant).order_by("name")

    def clean(self):
        cleaned = super().clean()
        tenant_id = getattr(self.tenant, "pk", self.tenant)
        if tenant_id is None:
            self.add_error(None, "A tenant workspace is required.")
            return cleaned
        if self.instance.pk and self.instance.tenant_id != tenant_id:
            self.add_error(None, "The assignment must belong to this workspace.")
            return cleaned
        # The dropdowns above are already narrowed; this catches a POST that bypasses the widget
        # and says WHY in the author's own terms rather than "Select a valid choice".
        _reject_foreign(self, cleaned, ["account", "territory", "rule", "owner"])
        return cleaned
