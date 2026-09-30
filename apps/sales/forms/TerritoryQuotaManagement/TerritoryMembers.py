"""Sales 8.7 — the territory coverage roster form (`TMB-`).

Three columns answer NavERP bullet 4, and the form keeps them separate: ``member_role`` says WHO
the member is (the hunter / farmer split, the overlay specialist), ``paired_user`` IS the SDR → AE
pairing (a nullable FK is the whole pairing), and ``coverage_split_pct`` is the split credit — a
percentage, never a money column, because incentive compensation is 8.10's and 8.7 must not
store a "credit" figure 8.10 would own.

**OWNERSHIP (L29/L36/L37).** ``territory`` is `crm.Territory` — owned by CRM 1.2, read-only to
8.7. There is deliberately **no** ``is_manager`` / ``manager`` field here: `crm.Territory.manager`
is CRM's single accountable manager, and a second management field would be a second source of
truth for the same fact.

Excluded from ``Meta.fields``, with the reason for each:

* ``tenant`` — set by ``TenantUniqueMixin`` from the view's ``request.tenant``, never from input.
* ``number`` — ``editable=False`` on ``TenantNumbered``; allocated by ``next_number`` (L22).
* ``created_at`` / ``updated_at`` — ``auto_now*`` stamps.

``user`` and ``paired_user`` are both narrowed to ACTIVE users, so a deactivated rep can be
neither added to a roster nor paired. The roster's own checks (no self-pairing, a pairing must
land on an AE membership, direct splits summing to 100) live in the model — they involve sibling
rows, so they belong in the same place that resolves them.
"""
from django import forms

from apps.sales.forms._common import (
    TenantModelForm,
    TenantUniqueMixin,
    _reject_foreign,
    tenant_territories,
    tenant_users,
)
from apps.sales.models.TerritoryQuotaManagement.TerritoryMembers import TerritoryMember


class TerritoryMemberForm(TenantUniqueMixin, TenantModelForm):
    """Add or edit one person's role in one territory, and the split credit they carry."""

    class Meta:
        model = TerritoryMember
        # Excluded, with the reason for each — see the module docstring.
        fields = [
            "territory",
            "user",
            "member_role",
            "assignment_type",
            "coverage_split_pct",
            "paired_user",
            "is_primary",
            "effective_from",
            "effective_to",
            "notes",
        ]
        widgets = {
            "coverage_split_pct": forms.NumberInput(attrs={
                "class": "form-input",
                "step": "0.01",
                "min": "0",
                "max": "100",
            }),
            "notes": forms.TextInput(attrs={
                "class": "form-input",
                "placeholder": "Why this person is on this territory...",
            }),
        }
        help_texts = {
            "member_role": "Who this person is here: hunter, farmer, SDR, AE, or an overlay specialist.",
            "assignment_type": (
                "Direct members carry the territory. A territory becomes a split territory only "
                "when someone is marked shared."
            ),
            "coverage_split_pct": (
                "Direct members must sum to exactly 100.00% once any sibling is shared; a shared "
                "member carries 0.00%. With no shared sibling the total is not checked, so a lone "
                "rep can sit at 100.00%."
            ),
            "paired_user": (
                "The Account Executive this member pairs with. Leave blank when there is no "
                "pairing — a null FK IS the pairing."
            ),
            "effective_to": "Blank means current. A roster change closes the row; it never rewrites it.",
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)
        self.fields["territory"].queryset = tenant_territories(self.tenant).order_by("name")
        self.fields["user"].queryset = tenant_users(self.tenant).order_by("username")
        self.fields["paired_user"].queryset = tenant_users(self.tenant).order_by("username")

    def clean(self):
        cleaned = super().clean()
        tenant_id = getattr(self.tenant, "pk", self.tenant)
        if tenant_id is None:
            self.add_error(None, "A tenant workspace is required.")
        elif self.instance.pk and self.instance.tenant_id != tenant_id:
            self.add_error(None, "The membership must belong to this workspace.")
        # The dropdowns above are already narrowed; this catches a POST that bypasses the widget
        # and says WHY in the author's own terms rather than "Select a valid choice".
        _reject_foreign(self, cleaned, ["territory", "user", "paired_user"])
        return cleaned
