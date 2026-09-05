"""Procurement 6.18 Inventory & Warehouse Integration — ReplenishmentPolicy form.

One shape: ``ReplenishmentPolicyForm``, the create-or-edit form for the replenishment
configuration master. Everything the system owns is excluded — and that is the whole exclusion
list, because a policy is configuration a person types, not a document the system stamps:

* ``tenant`` — stamped by ``TenantUniqueMixin`` / the create helper.
* ``created_at`` / ``updated_at`` — the base timestamps.

**Tenant discipline.** Every dropdown is narrowed to the workspace in ``__init__`` AND re-checked
in ``clean()``. A narrowed ``<select>`` is UX, **not** an authorization boundary: an unscoped
``ModelChoiceField`` both displays another tenant's rows and accepts their pk from a crafted POST
that never went near the rendered page. ``_reject_foreign`` is the boundary, and
``ReplenishmentPolicy.clean()`` is the model-level backstop behind it — three independent layers,
because a policy carries the vendor and the GL account a generated requisition will be stamped
with, and a cross-tenant one of either would leak into another workspace's spend.

**Why the vendor dropdown is narrowed twice over.** ``TenantModelForm`` already scopes
``preferred_vendor`` to the workspace (``core.Party`` carries its own ``tenant``); the extra
``roles__role__in`` filter is the SUPPLIER rule, not the tenant rule — offering every customer and
employee party as a "preferred vendor" is how a policy ends up pointing at somebody nobody can buy
from. ``core.PartyRole`` distinguishes ``supplier`` from ``vendor`` and workspaces use both
interchangeably, so both are accepted here exactly as the model's own check accepts both.
"""
from apps.procurement.forms._common import *  # noqa: F401,F403
from apps.procurement.forms._common import TenantUniqueMixin, _reject_foreign
# NOT-YET-WIRED entity of this SAME sub-module: import the entity MODULE directly, never
# ``from apps.procurement.models import X`` — the sub-package is not wired until the Integrator
# lands it, and a package-level re-export would be a star-import cycle at URLconf import time.
from apps.procurement.models.InventoryWarehouseIntegration.Policies import ReplenishmentPolicy

#: The tenant-scoped FKs, in one place so ``__init__``'s ``.none()`` sweep and ``clean()``'s
#: re-check can never drift apart — a field added to one list and forgotten in the other is
#: exactly the hole this pairing exists to close.
_TENANT_FKS = ("item", "location", "preferred_vendor", "default_org_unit", "default_budget",
               "default_gl_account")


class ReplenishmentPolicyForm(TenantUniqueMixin, TenantModelForm):
    """Create or amend one replenishment policy.

    ``TenantUniqueMixin`` comes FIRST so ``instance.tenant`` is stamped before ``full_clean()``
    runs: ``ReplenishmentPolicy.clean()`` compares each chosen FK's tenant against
    ``self.tenant_id`` and probes for a duplicate any-location row scoped to that tenant, so
    without the stamp every CREATE would be falsely rejected as cross-tenant.

    The mixin's ``validate_unique`` override matters here too: ``unique_together`` is
    ``(tenant, item, location)`` and ``tenant`` is not a form field, so Django's default
    exclusion list would drop the whole constraint and let a duplicate through to an
    ``IntegrityError`` 500 instead of a field error.
    """

    class Meta:
        model = ReplenishmentPolicy
        # Every editable field, in model order. Listed explicitly rather than via ``exclude`` so
        # a column added to the model later cannot silently become a form input.
        fields = ["item", "location", "source_method", "trigger_mode", "preferred_vendor",
                  "target_level", "order_multiple", "min_order_qty", "max_order_qty",
                  "include_on_order", "include_open_requisitions", "lead_time_days_override",
                  "default_org_unit", "default_budget", "default_gl_account",
                  "is_active", "notes"]
        widgets = {
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)

        if tenant is None:
            # A tenant-less user (the superuser) must not be OFFERED another workspace's rows,
            # and must not be able to post one either. ``item`` is emptied along with the rest:
            # a required field with no choices fails validation, which is the correct outcome —
            # a policy with no workspace has nothing to replenish.
            for name in _TENANT_FKS:
                self.fields[name].queryset = self.fields[name].queryset.none()
            return

        from apps.accounting.models import Budget, GLAccount
        from apps.core.models import OrgUnit, Party
        from apps.scm.models import Item, Location

        # ``TenantModelForm`` has already scoped each of these to the tenant (every target model
        # carries a ``tenant`` column). The narrowing below is the EXTRA rule per axis — active
        # only, supplier only, ordering — never the tenant boundary itself.
        self.fields["item"].queryset = (
            Item.objects.filter(tenant=tenant, is_active=True)
            .select_related("uom").order_by("sku"))
        self.fields["location"].queryset = (
            Location.objects.filter(tenant=tenant, is_active=True).order_by("code"))
        self.fields["preferred_vendor"].queryset = (
            Party.objects.filter(tenant=tenant, roles__role__in=("supplier", "vendor"))
            .distinct().order_by("name"))
        self.fields["default_org_unit"].queryset = OrgUnit.objects.filter(tenant=tenant).order_by("name")
        self.fields["default_budget"].queryset = (
            Budget.objects.filter(tenant=tenant).select_related("fiscal_period").order_by("-id"))
        self.fields["default_gl_account"].queryset = (
            GLAccount.objects.filter(tenant=tenant, is_active=True).order_by("code"))

        # Blank means something specific on each of these, so none of them gets the bare
        # "---------": on ``location`` it is the catch-all scope the resolver falls back to, and
        # on the other four it is "the system does not decide this for you".
        self.fields["location"].empty_label = "- any location -"
        self.fields["preferred_vendor"].empty_label = "- decide at release -"
        for name in ("default_org_unit", "default_budget", "default_gl_account"):
            self.fields[name].empty_label = "- none -"

    def clean(self):
        cleaned = super().clean()
        # Re-check every tenant-scoped FK against the workspace: the narrowed <select> above is
        # presentation, and a crafted POST never goes near it. ``item`` is re-checked too — it is
        # the one required FK here, and a policy pointed at another workspace's item would make
        # ``resolve_map`` answer for a row this tenant cannot see.
        _reject_foreign(self, cleaned, list(_TENANT_FKS))
        return cleaned
