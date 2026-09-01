"""Procurement 6.15 Budget & Cost Management — BudgetMapping form.

One shape: ``BudgetMappingForm``, the create-or-edit form for the budget-mapping configuration
master. Everything the system owns is excluded:

* ``tenant`` — stamped by ``TenantUniqueMixin`` / the create helper.
* ``created_at`` / ``updated_at`` — the base timestamps.

Tenant discipline: every dropdown is narrowed to the workspace in ``__init__`` AND re-checked in
``clean()``. A narrowed ``<select>`` is UX, not an authorization boundary — an unscoped
``ModelChoiceField`` both displays another tenant's rows and accepts their pk from a crafted POST.
"""
from apps.procurement.forms._common import *  # noqa: F401,F403
from apps.procurement.forms._common import TenantUniqueMixin, _reject_foreign
# NOT-YET-WIRED entity of this SAME sub-module: import the entity MODULE directly, never
# ``from apps.procurement.models import X`` — the sub-package is not wired until the Integrator
# lands it, and a package-level re-export would be a star-import cycle at URLconf import time.
from apps.procurement.models.BudgetCostManagement.BudgetMappings import BudgetMapping


class BudgetMappingForm(TenantUniqueMixin, TenantModelForm):
    """Create or amend one budget mapping.

    ``TenantUniqueMixin`` comes FIRST so ``instance.tenant`` is stamped before ``full_clean()``
    runs: ``BudgetMapping.clean()`` compares each chosen FK's tenant against ``self.tenant_id``,
    and without the stamp every CREATE would be falsely rejected as cross-tenant.
    """

    class Meta:
        model = BudgetMapping
        fields = ["budget", "org_unit", "project", "default_gl_account", "priority",
                  "is_active", "notes"]
        widgets = {
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)

        if tenant is None:
            # A tenant-less user (the superuser) must not be OFFERED another workspace's rows
            # and must not be able to post one either.
            for name in ("budget", "org_unit", "project", "default_gl_account"):
                self.fields[name].queryset = self.fields[name].queryset.none()
            return

        from apps.accounting.models import Budget, GLAccount, Project
        from apps.core.models import OrgUnit

        # ``TenantModelForm`` has already scoped each of these to the tenant (every target model
        # carries a ``tenant`` column). The narrowing below is the EXTRA rule per axis — ordering
        # and active-only — not the tenant boundary itself.
        self.fields["budget"].queryset = (
            Budget.objects.filter(tenant=tenant).select_related("fiscal_period").order_by("-id"))
        self.fields["org_unit"].queryset = OrgUnit.objects.filter(tenant=tenant).order_by("name")
        self.fields["project"].queryset = Project.objects.filter(tenant=tenant).order_by("name")
        self.fields["default_gl_account"].queryset = (
            GLAccount.objects.filter(tenant=tenant, is_active=True).order_by("code"))

        for name in ("org_unit", "project", "default_gl_account"):
            self.fields[name].empty_label = "- any -"

    def clean(self):
        cleaned = super().clean()
        # Re-check every tenant-scoped FK against the workspace: the narrowed <select> above is
        # presentation, and a crafted POST never goes near it.
        _reject_foreign(self, cleaned, ["budget", "org_unit", "project", "default_gl_account"])
        return cleaned
