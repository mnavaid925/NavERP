"""SCM 4.12 Contract & Compliance — the ``TradeLicense`` form.

**What a human types here is the authorisation as the authority granted it**: its number, its dates,
its scope and its two ceilings. What a human never types is the *balance* — ``used_value`` and
``used_quantity`` are re-derived from the documents charged to the licence
(``TradeLicense.recompute_usage()``), and a field that let somebody type one would make the register
lie about how much authority is left. Both are ``editable=False`` on the model, so this is a
whitelist restating a boundary the model already enforces rather than the mechanism enforcing it.

**What is deliberately NOT on this form.** ``tenant`` (stamped by the view), ``number`` (assigned in
``TenantNumbered.save()``), ``status`` (moved only by the submit / approve / revoke verbs and by the
date-driven ``refresh_status()`` — a free-text status dropdown would let somebody type ``active`` on
a licence no authority ever granted and start charging movement to it), ``used_value`` /
``used_quantity`` (the derived counters above), ``approved_at`` / ``approved_by`` / ``revoked_at`` /
``revocation_reason`` (system stamps, L22 — written by the verb that made the decision, so they say
who decided and when rather than what somebody typed), and the two automatic timestamps. That is a
WHITELIST ``Meta.fields``, never an ``exclude``: a blacklist means the next column added to
``TradeLicense`` joins this form silently.

**``TenantUniqueMixin`` is mixed in for ``("tenant", "license_number")``.** The authority's own
number is unique per workspace precisely so one licence cannot be registered twice and have its
balance drawn down in two places. Without the mixin a duplicate passes ``is_valid()`` and then
raises an uncaught ``IntegrityError`` — a 500 on an ordinary user mistake. The mixin also stamps
``self.instance.tenant`` in its constructor, which is what makes ``TradeLicense.clean()``'s
cross-tenant FK guard actually RUN on create: ``crud_create`` assigns the tenant only AFTER
``is_valid()`` (``apps/core/crud.py:120-123``), so without the stamp the instance is validated with
``tenant_id`` None — the exact case that guard skips — and the check would be dead code on the one
path a crafted POST exercises.

**Why the two party dropdowns ARE narrowed by ``PartyRole`` when ``TradeDocumentForm``'s three are
not.** A licence holder is us, a subsidiary or an agent, and a named end user is a counterparty we
buy from, sell through or move freight with — in every case somebody the workspace has a commercial
relationship with, which is the supplier/vendor/partner set. The sibling form's shipper / consignee /
notify are a different question (an export consignee is a *customer*), so narrowing them would hide
the majority of legitimate parties. Both are UX either way: ``TradeLicense.clean()`` re-checks the
tenant of every FK, and that is what holds against a crafted POST (L39 §2).
"""
from apps.scm.forms._common import *  # noqa: F401,F403
from apps.scm.forms._common import (TenantUniqueMixin, _active_currencies, _carrier_parties,
                                    _supplier_parties)

from apps.core.models import Document
from apps.scm.models import TradeLicense


class TradeLicenseForm(TenantUniqueMixin, TenantModelForm):
    """One authorisation — its identity, its dates, its ceilings and what it covers."""

    class Meta:
        model = TradeLicense
        # 20 fields — the model's full editable set. Every column it omits is already
        # `editable=False` (or comes from the base), so this list documents the boundary while
        # `editable=False` is what enforces it. See the module docstring for the omissions.
        fields = [
            # identity — `license_number` is the AUTHORITY's number, distinct from the internal LIC-
            "license_number", "title", "license_type", "issuing_authority", "issuing_country",
            # who it covers
            "holder_party", "end_user_party",
            # the dates, and how far ahead the renewal queue should flag it
            "application_date", "issue_date", "expiry_date", "renewal_notice_days",
            # the CEILINGS. Blank means unlimited in that dimension — not zero (the model's
            # remaining_*/utilization_pct return None there, and the page prints an em dash).
            "authorized_value", "authorized_quantity", "currency",
            # what it covers — free text on purpose: this repo has no HS/ECCN master and no
            # country-control content, and a picklist over data we do not have would be a fake feed.
            "commodity_scope", "eccn_or_hs", "destination_countries", "conditions",
            # evidence
            "document", "notes",
        ]
        widgets = {
            "commodity_scope": forms.Textarea(attrs={"rows": 3}),
            "conditions": forms.Textarea(attrs={"rows": 3}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        # TenantUniqueMixin.__init__ runs first in the MRO: it calls up to TenantModelForm (which
        # sets self.tenant and applies the base scoping) and then stamps self.instance.tenant. Both
        # halves are load-bearing — see the module docstring.
        super().__init__(*args, **kwargs)

        # --- who the licence names ------------------------------------------------------------------
        # Built ONCE and handed to both fields: `ModelChoiceField.queryset`'s setter calls
        # `queryset.all()`, which clones, so the two dropdowns cannot share evaluation state.
        # The union rather than `_carrier_parties` alone: that helper's role tuple happens to be a
        # superset of `_supplier_parties`' today, and writing the union means this stays correct if
        # either helper's roles change. Both return `.none()` for a tenant-less caller, and
        # `EmptyQuerySet | EmptyQuerySet` is empty — so no tenant still means no options.
        counterparties = _supplier_parties(self.tenant) | _carrier_parties(self.tenant)
        for name in ("holder_party", "end_user_party"):
            if name in self.fields:
                self.fields[name].queryset = counterparties

        # --- the money and the evidence ---------------------------------------------------------------
        # `Currency` is GLOBAL (no tenant column) so the base class cannot scope it; the shared
        # helper constrains it to the active set instead.
        _active_currencies(self)
        self._scope_to_tenant("document", Document.objects.all())

    def _scope_to_tenant(self, name, queryset):
        """Point one dropdown at this tenant's rows — and at NOTHING when there is no tenant.

        ``TenantModelForm`` already scopes every FK whose target carries a ``tenant`` column, but
        only ``if tenant is not None``; a tenant-less caller falls through to the unscoped default
        manager. Re-filtering from the model rather than chaining off the base's result makes the
        scoping true by construction instead of true by the caller behaving.
        """
        if name in self.fields:
            self.fields[name].queryset = (
                queryset.filter(tenant=self.tenant) if self.tenant is not None else queryset.none()
            )
