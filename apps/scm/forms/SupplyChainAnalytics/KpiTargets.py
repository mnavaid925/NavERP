"""SCM 4.11 Supply Chain Analytics — the ``KpiTarget`` form.

``KpiTarget`` is the ONE row in 4.11 a human authors — every figure on the five analytics pages is
computed live out of 4.1-4.10 — so this is the sub-module's only real create/edit screen. It is a
plain :class:`TenantModelForm` on purpose: the closed metric vocabulary, the band ordering, the
scope/FK agreement, the required metric parameters and the alerting conjunction are all enforced by
``KpiTarget.clean()``, which reads the registry metadata in
``apps/scm/models/SupplyChainAnalytics/_choices.py``. None of that is re-implemented here — this
module's whole job is to hand that validation a correctly TENANT-SCOPED set of choices.

**L39 §2 — the four scope dropdowns are deliberately NOT narrowed by ``scope``.** The create form is
unbound, so no scope has been chosen yet; narrowing ``scope_carrier`` to "only when scope == carrier"
would render four permanently empty selects and the screen could never be completed. That is the 4.5
``ship_to_address`` failure verbatim. Each dropdown offers this tenant's full set, and
``KpiTarget.clean()`` rejects the wrong combination — which also holds against a crafted POST, as a
narrowed dropdown never did.

**Activity is deliberately not a filter either.** A target legitimately watches a *suspended* carrier
or a *discontinued* category: 4.11 reads history, so the subject being dormant today is often exactly
why somebody is measuring it. The one exception is ``owner``, which points at a login rather than a
subject — see below.
"""
from django.contrib.auth import get_user_model

from apps.scm.forms._common import *  # noqa: F401,F403
from apps.scm.forms._common import _supplier_parties
from apps.scm.models import Carrier, ItemCategory, KpiTarget, Location


class KpiTargetForm(TenantModelForm):
    """A goal, its warning/critical bands and its knobs, for one registry metric."""

    class Meta:
        model = KpiTarget
        # EXCLUDE rather than a `fields` list: this model IS a page of settings and every column on
        # it is human intent, so the form is "everything except the plumbing". `tenant` is stamped
        # by crud_create; `number` is auto-assigned in TenantNumbered.save(); `last_evaluated_at` is
        # a system stamp written only by capture_snapshots/detect_alerts (L22); the two timestamps
        # are automatic. All five are already non-editable, so listing them is documentation of the
        # boundary rather than the mechanism enforcing it.
        # A WHITELIST, not `exclude`. The excluded set was correct and every omitted column is
        # already `editable=False`, so nothing was reachable — but a blacklist means the next column
        # added to KpiTarget joins this form silently, and this was the only Meta.exclude on any
        # ModelForm in apps/ (the sibling SupplyChainAlertForm's docstring asserts as much). The
        # field list is verified equal to the model's editable set, so this is the same form.
        #
        # Still excluded, and why: `tenant` is stamped by crud_create; `number` is auto-assigned in
        # TenantNumbered.save(); `last_evaluated_at` is a system stamp written only by
        # capture_snapshots/detect_alerts (L22); the two timestamps are automatic.
        fields = ["metric", "name", "scope", "scope_category", "scope_location", "scope_carrier",
                  "scope_vendor", "period_grain", "date_range", "direction", "target_value",
                  "warning_threshold", "critical_threshold", "parameter_days", "parameter_pct",
                  "is_alerting", "min_impact_value", "severity", "owner", "is_pinned",
                  "display_order", "is_active", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Stamp the tenant onto the unsaved instance so KpiTarget.clean()'s cross-tenant scope guard
        # actually RUNS on create. `crud_create` assigns the tenant only AFTER `is_valid()`
        # (apps/core/crud.py:82-84), so without this the instance is validated with `tenant_id`
        # None — the exact case that guard skips — and the check is dead code on the one path where
        # a crafted POST would exercise it.
        # Not `TenantUniqueMixin`: KpiTarget's only unique_together is (tenant, number), and
        # `number` is auto-assigned and off the form, so its validate_unique half has nothing to
        # check here. Borrowing the mixin for its constructor alone would misname the intent.
        if self.tenant is not None and self.instance.tenant_id is None:
            self.instance.tenant = self.tenant

        # --- the four scope subjects (NOT narrowed by `scope` — see the module docstring) --------
        self._scope_to_tenant("scope_category", ItemCategory.objects.all())
        self._scope_to_tenant("scope_location", Location.objects.all())
        # select_related is load-bearing here and nowhere else in this form: `Carrier.name` is a
        # PROPERTY reading `self.party.name`, so `Carrier.__str__` walks a second FK and the select
        # would fire one query per rendered <option>. ItemCategory / Location / Party / User all
        # render from their own columns, so they need nothing.
        self._scope_to_tenant("scope_carrier", Carrier.objects.select_related("party"))
        # "Supplier" is a PartyRole, so the tenant's whole party book would offer customers, carriers
        # and employees as spend counterparties. Same helper `PurchaseOrderForm.vendor` uses, so the
        # buyer and the analyst are looking at one supplier list.
        if "scope_vendor" in self.fields:
            self.fields["scope_vendor"].queryset = _supplier_parties(self.tenant)

        # --- who is answerable --------------------------------------------------------------------
        # Unlike the scope subjects, `owner` points at a LOGIN, and handing a number to a deactivated
        # account is how a target ends up with nobody watching it — so deactivated users are dropped.
        # The `pk=` leg keeps an already-stored owner selectable after they are deactivated: without
        # it the option would vanish from the select and saving an unrelated edit would silently null
        # the FK. `owner_id` is None on a create form, which Django resolves to `id IS NULL` and
        # matches nothing — the OR is simply inert there.
        self._scope_to_tenant(
            "owner",
            get_user_model().objects.filter(Q(is_active=True) | Q(pk=self.instance.owner_id)),
        )

    def _scope_to_tenant(self, name, queryset):
        """Point one dropdown at this tenant's rows — and at NOTHING when there is no tenant.

        The ``TenantModelForm`` base already scopes every FK whose target carries a ``tenant``
        column, but only ``if tenant is not None``; a tenant-less caller falls through to the
        unscoped default manager. The CRUD helpers never render this form that way, but re-filtering
        from the model rather than chaining off the base's result makes the scoping true by
        construction instead of true by the caller behaving.
        """
        if name in self.fields:
            self.fields[name].queryset = (
                queryset.filter(tenant=self.tenant) if self.tenant is not None else queryset.none()
            )
