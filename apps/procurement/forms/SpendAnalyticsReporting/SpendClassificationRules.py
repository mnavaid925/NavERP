"""Procurement 6.14 Spend Analytics & Reporting — SpendClassificationRuleForm.

A classification rule decides how the WHOLE workspace's spend is grouped, so the two jobs this
form has are both about trust:

1. **Every tenant-scoped FK dropdown is narrowed to this workspace** — otherwise an unscoped
   ``ModelChoiceField`` both DISPLAYS another tenant's suppliers and ACCEPTS their pk.
2. **Every one of them is re-checked after the POST** via ``_reject_foreign`` — a narrowed
   ``<select>`` is UX, not an authorization boundary; a hand-edited POST never sees it.

``invoice_type`` is a plain ``CharField`` on the model (6.13 owns the vocabulary), so it is
re-declared here as a ``ChoiceField`` over ``SupplierInvoice.INVOICE_TYPE_CHOICES`` — a free-text
box would let a typo create a rule that can never match anything and never say why.

**Excluded, and why.** ``tenant`` is stamped by ``crud_create`` (and by ``TenantUniqueMixin``
before validation); ``match_count`` and ``last_matched_at`` are system stamps written ONLY by the
preview verb and shown on the detail page — putting a derived stamp on a form is how a
``DateTimeField`` gets silently truncated by a widget (L22); ``created_at``/``updated_at`` are
timestamps. There is no ``status`` and no ``number`` on this model: it is a configuration master,
not a workflow document.
"""
from apps.procurement.forms._common import *  # noqa: F401,F403
from apps.procurement.forms._common import TenantUniqueMixin, _reject_foreign
# NOT-YET-WIRED sub-package: import the entity MODULE directly rather than
# ``from apps.procurement.models import X`` — the package re-export block does not exist until the
# Integrate phase lands it (the 6.13 InvoiceDisputes precedent).
from apps.procurement.models.InvoiceVoucherManagement.SupplierInvoices import SupplierInvoice
from apps.procurement.models.SpendAnalyticsReporting.SpendClassificationRules import (
    SpendClassificationRule,
)


def _supplier_parties(tenant):
    """Parties this workspace can buy from — the local mirror of the helper 6.8/6.12 already keep
    (peer sub-modules copy it rather than import each other's private names). ``core.PartyRole``
    distinguishes ``supplier`` from ``vendor``; BOTH are accepted so the dropdown never hides half
    the counterparties."""
    from apps.core.models import Party

    if tenant is None:
        return Party.objects.none()
    return (Party.objects
            .filter(tenant=tenant, roles__role__in=("supplier", "vendor"))
            .distinct()
            .order_by("name"))


class SpendClassificationRuleForm(TenantUniqueMixin, TenantModelForm):
    """One explicit spend-classification rule.

    ``TenantUniqueMixin`` is mixed in FIRST on purpose: the model's ``clean()`` compares every
    chosen FK's tenant against ``self.tenant_id``, and the CRUD helpers only assign the real
    tenant AFTER ``is_valid()``. Without the mixin's early stamp every CREATE would be falsely
    rejected as cross-tenant.
    """

    # 6.13 owns this vocabulary; the model column is a plain CharField so the two apps are not
    # welded together by a choices= at the schema level.
    invoice_type = forms.ChoiceField(
        required=False,
        choices=[("", "---------")] + list(SupplierInvoice.INVOICE_TYPE_CHOICES),
        help_text="Only used by an Invoice Type rule, and only on the invoiced basis.",
    )

    class Meta:
        model = SpendClassificationRule
        fields = ["name", "match_type", "vendor", "gl_account", "org_unit", "keyword",
                  "invoice_type", "category", "priority", "applies_to", "is_active", "notes"]

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)
        from apps.accounting.models import GLAccount
        from apps.core.models import OrgUnit
        from apps.scm.models import ItemCategory

        # TenantModelForm already scopes an FK whose TARGET model carries a tenant column, but the
        # ordering, the active-only narrowing and the supplier-role narrowing (which it cannot
        # know about) are ours.
        if "vendor" in self.fields:
            self.fields["vendor"].queryset = _supplier_parties(tenant)
            self.fields["vendor"].required = False
        if "gl_account" in self.fields:
            self.fields["gl_account"].queryset = (
                GLAccount.objects.filter(tenant=tenant, is_active=True).order_by("code")
                if tenant is not None else GLAccount.objects.none())
            self.fields["gl_account"].required = False
        if "org_unit" in self.fields:
            self.fields["org_unit"].queryset = (
                OrgUnit.objects.filter(tenant=tenant).order_by("name")
                if tenant is not None else OrgUnit.objects.none())
            self.fields["org_unit"].required = False
        if "category" in self.fields:
            # The ONE required FK — it is the taxonomy target the whole rule exists to set.
            self.fields["category"].queryset = (
                ItemCategory.objects.filter(tenant=tenant, is_active=True).order_by("name")
                if tenant is not None else ItemCategory.objects.none())

    def clean(self):
        cleaned = super().clean()
        # The crafted-POST re-check. ``category`` is included even though it is required: required
        # says a value was sent, not that the value belongs to this workspace.
        _reject_foreign(self, cleaned, ["vendor", "gl_account", "org_unit", "category"])
        return cleaned

    # No DateField on this form at all — and even if one were added, TenantModelForm already owns
    # the date widgets and input_formats. Never re-declare them here (L22).
