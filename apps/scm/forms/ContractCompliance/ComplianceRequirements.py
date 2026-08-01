"""SCM 4.12 Contract & Compliance Management — the obligation-register forms.

Two forms, one register. :class:`ComplianceRequirementForm` authors the standing obligation;
:class:`ComplianceCheckForm` records one performed proof cycle against it. Neither re-implements a
rule: the scope/pointer agreement, the cross-tenant guards, the "a contract obligation must name its
contract" link-out rule, the first-due-date requirement and the not-applicable reason all live in
``ComplianceRequirement.clean()``, and the future-date and cross-tenant-evidence rules live in
``ComplianceCheck.clean()``. **This module's whole job is to hand that validation a correctly
TENANT-SCOPED set of choices, and to make sure it actually runs.**

**The tenant stamp is load-bearing, not decoration.** ``crud_create`` assigns the tenant only AFTER
``is_valid()`` (``apps/core/crud.py:120-123``), so an unsaved ``ComplianceRequirement`` reaches
``clean()`` with ``tenant_id`` None — precisely the case its cross-tenant FK guard skips. Without the
stamp in :meth:`ComplianceRequirementForm.__init__` that guard is dead code on the one path where a
crafted POST would exercise it. ``ComplianceCheck`` has the same hole one level down: it has no
``tenant`` column at all, so its evidence guard reads ``requirement.tenant_id`` — which is unset
until the view attaches the parent. :class:`ComplianceCheckForm` therefore takes a ``requirement=``
kwarg and stamps it before validation, for exactly the same reason.

**L39 §2 — the five scope pointers are deliberately NOT narrowed by the chosen ``scope``.** A create
form is unbound, so no scope has been chosen yet; narrowing ``party`` to "only when scope == party"
would render four permanently empty selects and the screen could never be completed. That is the 4.5
``ship_to_address`` failure verbatim. Each dropdown offers this tenant's full set and
``ComplianceRequirement.clean()`` rejects the wrong combination — which also holds against a crafted
POST, as a narrowed dropdown never did.

**Activity/status is deliberately not a filter on the subject dropdowns either.** An obligation
legitimately binds a *suspended* supplier or a *discontinued* item — that the subject is dormant
today is often exactly why somebody is still tracking the duty. ``owner`` is the one exception,
because it points at a login rather than at a subject: see the comment there.
"""
from django.contrib.auth import get_user_model

from apps.core.models import Document, OrgUnit

from apps.scm.forms._common import *  # noqa: F401,F403
from apps.scm.forms._common import _carrier_parties, _supplier_parties
from apps.scm.models import (ComplianceCheck, ComplianceRequirement, Item, Location,
                             SupplierContract, TradeLicense)


def _scope_to_tenant(form, name, queryset):
    """Point one dropdown at this tenant's rows — and at NOTHING when there is no tenant.

    ``TenantModelForm`` already scopes every FK whose target carries a ``tenant`` column, but only
    ``if tenant is not None``; a tenant-less caller falls through to the unscoped default manager.
    The CRUD helpers never render these forms that way, but re-filtering from the model rather than
    chaining off the base's result makes the scoping true by construction instead of true by the
    caller behaving. (The ``KpiTargetForm._scope_to_tenant`` idiom, lifted to a module function
    because two forms in this file need it.)
    """
    if name in form.fields:
        form.fields[name].queryset = (
            queryset.filter(tenant=form.tenant) if form.tenant is not None else queryset.none()
        )


def _obligation_subject_parties(tenant):
    """The counterparties a ``scope="party"`` obligation may name.

    ``SCOPE_CHOICES`` labels this pointer **"Supplier"** and ``scope_label`` renders
    ``"Supplier: Acme Ltd"``, so the tenant's whole party book would offer customers and employees
    under a label that says supplier. Same union the two sibling 4.12 forms use for their party
    dropdowns (``TradeLicenseForm.holder_party`` / ``SustainabilityAssessmentForm.party``), so all
    of 4.12 is looking at ONE counterparty list.

    ``_carrier_parties`` is a superset of ``_supplier_parties`` today (supplier|vendor|partner vs
    supplier|vendor); the union is written out anyway so this stays correct if either helper's role
    list changes. Carriers belong here on their own merit — a HazMat carrier certification is an
    obligation scoped to a carrier.
    """
    if tenant is None:
        return Party.objects.none()
    return (_supplier_parties(tenant) | _carrier_parties(tenant)).distinct()


class ComplianceRequirementForm(TenantModelForm):
    """One standing obligation: what it is, what it binds, who owns it and how often it is re-proved."""

    class Meta:
        model = ComplianceRequirement
        # A WHITELIST, never `Meta.exclude` — a blacklist means the next column added to the model
        # joins this form silently. Every column of the model's editable set is here, in declaration
        # order, and nothing else.
        #
        # Deliberately ABSENT, and why: `tenant` is stamped by `crud_create` (and, before that, in
        # __init__ below so clean() can read it); `number` is auto-assigned in
        # `TenantNumbered.save()`; `last_checked_on` is a system stamp written ONLY by
        # `ComplianceRequirement.record_check()` (L22 — a proof date somebody can type is not proof);
        # `created_at` / `updated_at` are automatic. All five are already non-editable or absent from
        # the model's editable set, so listing them here would be documentation rather than the
        # mechanism — the whitelist IS the mechanism.
        fields = ["title", "description", "source", "source_reference", "framework",
                  "obligation_category", "jurisdiction", "scope", "org_unit", "party", "location",
                  "item", "owner", "frequency", "next_due_date", "notice_days", "contract",
                  "license", "document", "status", "criticality", "not_applicable_reason", "notes"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "not_applicable_reason": forms.Textarea(attrs={"rows": 3}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # THE STAMP. See the module docstring: without it, `ComplianceRequirement.clean()`'s
        # cross-tenant FK guard is skipped on create, which is the one path a crafted POST uses.
        #
        # Not `TenantUniqueMixin`: this model's only `unique_together` is `(tenant, number)`, and
        # `number` is auto-assigned and off the form, so the mixin's `validate_unique` half would
        # have nothing to check. Borrowing it for its constructor alone would misname the intent —
        # the `KpiTargetForm` reading of the same situation.
        if self.tenant is not None and self.instance.tenant_id is None:
            self.instance.tenant = self.tenant

        # --- the four typed scope pointers (NOT narrowed by `scope` — see the module docstring) ---
        # Every one of these targets a tenant-scoped model, so the base class already filtered them;
        # re-filtering from the model makes it true by construction. None of the four `__str__`
        # methods walks a second FK (OrgUnit -> name, Party -> name, Location -> "code · name",
        # Item -> "sku · name"), so no `select_related` is owed here — checked, not assumed.
        _scope_to_tenant(self, "org_unit", OrgUnit.objects.all())
        _scope_to_tenant(self, "location", Location.objects.all())
        _scope_to_tenant(self, "item", Item.objects.all())
        if "party" in self.fields:
            self.fields["party"].queryset = _obligation_subject_parties(self.tenant)

        # --- the link-outs: where the duty comes from ---------------------------------------------
        # No status narrowing on either. An obligation routinely OUTLIVES the paper that created it
        # — a data-retention clause of an expired contract still binds, and a revoked licence's
        # closing conditions still need proving — so filtering these to "active" would hide exactly
        # the rows a compliance officer is chasing. `SupplierContract.__str__` and
        # `TradeLicense.__str__` are both "number · title", off their own columns.
        _scope_to_tenant(self, "contract", SupplierContract.objects.all())
        _scope_to_tenant(self, "license", TradeLicense.objects.all())
        # core.Document, never a FileField — Module 13 (DMS) owns file storage and 4.12 must not
        # grow a second one.
        _scope_to_tenant(self, "document", Document.objects.all())

        # --- who is answerable ---------------------------------------------------------------------
        # Unlike the scope subjects, `owner` points at a LOGIN, and making a deactivated account
        # answerable for an obligation is how a requirement ends up with nobody watching it — so
        # deactivated users are dropped. The `pk=` leg keeps an ALREADY-STORED owner selectable
        # after they are deactivated: without it the option vanishes from the select and saving an
        # unrelated edit would silently null the FK. `owner_id` is None on a create form, which
        # Django resolves to `id IS NULL` and matches nothing — the OR is simply inert there.
        _scope_to_tenant(
            self, "owner",
            get_user_model().objects.filter(Q(is_active=True) | Q(pk=self.instance.owner_id)),
        )


class ComplianceCheckForm(TenantModelForm):
    """One performed proof cycle — the row that makes the register defensible rather than aspirational.

    ``requirement`` is NOT a field: it comes from the URL parent, and letting a POST choose its own
    parent is how a check lands on somebody else's obligation. ``performed_by`` is not a field
    either — "who did it" is an audit fact stamped from ``request.user``, not an input (L22, the
    ``ReturnDisposition.received_by`` posture). ``created_at`` is automatic.

    ``due_date`` IS on the form, and the view defaults it: :func:`compliancerequirement_record_check`
    snapshots the parent's ``next_due_date`` when this field is left blank, so the ordinary path
    records the cycle the check actually answers. Leaving it editable is what allows a *back-filled*
    proof — recording last quarter's certificate now — to say which cycle it belongs to instead of
    silently claiming the current one.
    """

    class Meta:
        model = ComplianceCheck
        fields = ["result", "due_date", "performed_on", "finding", "corrective_reference",
                  "evidence", "notes"]
        widgets = {
            "finding": forms.Textarea(attrs={"rows": 3}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, requirement=None, **kwargs):
        super().__init__(*args, **kwargs)

        # THE STAMP, one level down. `ComplianceCheck` has no `tenant` column of its own, so its
        # cross-tenant evidence guard reads `self.requirement.tenant_id` — and on create that
        # relation is unset until the view attaches the parent AFTER `is_valid()`. Stamping it here
        # is what makes that guard run on the create path at all. Only when it is unset: an edit
        # already carries its parent and must never be repointed at another one.
        if requirement is not None and self.instance.requirement_id is None:
            self.instance.requirement = requirement

        # The evidence dropdown. `core.Document` carries a tenant, so the base class scoped it —
        # this re-filters from the model so the scoping does not depend on the caller having passed
        # a tenant. It is UX either way: `ComplianceCheck.clean()` re-checks the chosen document
        # against the PARENT's tenant, because a narrowed dropdown has never held against a crafted
        # POST and this child cannot be scoped automatically.
        _scope_to_tenant(self, "evidence", Document.objects.all())
