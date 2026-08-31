"""Procurement 6.14 Spend Analytics & Reporting — SpendReport form.

One shape: ``SpendReportForm``, the guided report builder. Every axis is a ``<select>`` whose
options come from the model's frozen choice lists — the builder is a small, readable set of
choices rather than a free-form canvas, which is exactly what makes a saved report auditable.

**There is deliberately NO snapshot form.** ``SpendReportSnapshot`` rows are minted only by the
``spendreport_snapshot`` POST from a freshly computed result; a user-typed snapshot would be a
frozen figure nobody could trace back to a run.

Everything the system owns is EXCLUDED, and each exclusion is a deliberate one:

* ``tenant`` — stamped by ``TenantUniqueMixin`` / the create view.
* ``number`` — assigned once by ``TenantNumbered.save()`` (SPR-#####).
* ``owner`` — the authorship stamp, set from ``request.user`` on create only. Offered as a field
  it would let a POST attribute someone else's report to them.
* ``last_run_at`` — a system stamp written by the run/snapshot POSTs. On a form it would be
  rendered by a ``DateInput`` and silently truncated to a date (L22).
* ``created_at`` / ``updated_at`` — the base timestamps.

Tenant discipline: every dropdown is narrowed to the workspace in ``__init__`` AND re-checked in
``clean()``. A narrowed ``<select>`` is UX, not an authorization boundary — an unscoped
``ModelChoiceField`` both displays another tenant's rows and accepts their pk from a crafted POST.
"""
from apps.procurement.forms._common import *  # noqa: F401,F403
from apps.procurement.forms._common import TenantUniqueMixin, _reject_foreign
# NOT-YET-WIRED entities of this SAME sub-module: import the entity MODULE directly, never
# ``from apps.procurement.models import X`` — the sub-package is not wired until the Integrator
# lands it, and a package-level re-export would be a star-import cycle at URLconf import time.
from apps.procurement.models.SpendAnalyticsReporting.SpendReports import SpendReport


def _supplier_parties(tenant):
    """Parties this tenant can buy from — the 6.5/6.8 helper rule verbatim (supplier OR vendor).

    Suppliers are ``core.Party`` rows carrying a ``PartyRole``; there is no vendor table in this
    tree and this form must not invent one. ``.distinct()`` because a party may legitimately hold
    both roles and the join would otherwise duplicate it in the dropdown.
    """
    from apps.core.models import Party

    if tenant is None:
        return Party.objects.none()
    return (Party.objects
            .filter(tenant=tenant, roles__role__in=("supplier", "vendor"))
            .distinct()
            .order_by("name"))


class SpendReportForm(TenantUniqueMixin, TenantModelForm):
    """Build or amend one saved spend report.

    ``TenantUniqueMixin`` comes FIRST so ``instance.tenant`` is stamped before ``full_clean()``
    runs: ``SpendReport.clean()`` compares each chosen FK's tenant against ``self.tenant_id``, and
    without the stamp every CREATE would be falsely rejected as cross-tenant.
    """

    #: Declared explicitly so the magnitude/precision limit is enforced by the FORM rather than
    #: hand-parsed in a view — an over-range figure is a field error, never a driver 500 (L35).
    min_amount = forms.DecimalField(
        max_digits=18, decimal_places=2, min_value=0, required=False,
        widget=forms.NumberInput(attrs={"step": "0.01", "placeholder": "0.00"}),
        help_text="Ignore rows below this value. Leave blank for no floor.")

    class Meta:
        model = SpendReport
        fields = ["name", "description", "basis", "measure", "dimension_1", "dimension_2",
                  "date_range", "date_from", "date_to", "vendor", "category", "org_unit",
                  "gl_account", "min_amount", "chart_type", "top_n", "is_favorite", "is_shared"]
        widgets = {
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)

        if tenant is None:
            # A tenant-less user (the superuser) must not be OFFERED another workspace's rows and
            # must not be able to post one either.
            for name in ("vendor", "category", "org_unit", "gl_account"):
                self.fields[name].queryset = self.fields[name].queryset.none()
            return

        from apps.accounting.models import GLAccount
        from apps.core.models import OrgUnit
        from apps.scm.models import ItemCategory

        # ``TenantModelForm`` has already scoped each of these to the tenant (every target model
        # carries a ``tenant`` column). The narrowing below is the EXTRA rule per axis — role,
        # active-only, ordering — not the tenant boundary itself.
        self.fields["vendor"].queryset = _supplier_parties(tenant)
        self.fields["category"].queryset = (
            ItemCategory.objects.filter(tenant=tenant, is_active=True).order_by("name"))
        self.fields["org_unit"].queryset = OrgUnit.objects.filter(tenant=tenant).order_by("name")
        self.fields["gl_account"].queryset = (
            GLAccount.objects.filter(tenant=tenant, is_active=True).order_by("code"))

        for name in ("vendor", "category", "org_unit", "gl_account"):
            self.fields[name].empty_label = "- any -"

    def clean(self):
        cleaned = super().clean()
        # Re-check every tenant-scoped FK against the workspace: the narrowed <select> above is
        # presentation, and a crafted POST never goes near it.
        _reject_foreign(self, cleaned, ["vendor", "category", "org_unit", "gl_account"])
        return cleaned
