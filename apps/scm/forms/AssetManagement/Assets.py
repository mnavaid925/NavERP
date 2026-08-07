"""SCM 4.13 Asset Management — the ``Asset`` register form and its spare-parts line form.

**What a human types here is the asset as the plant knows it**: what it is, where it sits, who looks
after it, what it cost and which meter it runs on. What a human never types is anything the module
*derives* — MTBF, MTTR, availability, downtime minutes, maintenance cost to date and the warranty
chip are all recomputed on read from the work orders and readings that produce them, so there is no
column for a form to disagree with (``Assets.py:302-572``).

**``status`` IS on this form, and that is the design, not an oversight.** ``Asset.status`` has
exactly one writer and it is the user: no work-order verb touches it. "Is this machine down right
now" is answered by :meth:`Asset.is_down_now` from the open downtime windows, so the operational
lifecycle state stays an editable statement of intent rather than something a verb has to remember
to flip back. Contrast ``MaintenanceWorkOrder.status``, which is ``editable=False`` and absent from
its form precisely because verbs own it.

**``TenantUniqueMixin`` is mixed in, and both halves of it are load-bearing.** ``Asset`` carries
``unique_together ("tenant", "code")``: without the mixin a duplicate plant code passes
``is_valid()`` and then raises an uncaught ``IntegrityError`` — a 500 on an everyday user mistake.
The mixin's constructor also stamps ``self.instance.tenant``, which is what makes
``Asset.clean()``'s cross-tenant FK guard, its ``tag_code`` uniqueness rule and its hierarchy-cycle
walk actually RUN on create: ``crud_create`` assigns the tenant only AFTER ``is_valid()``
(``apps/core/crud.py:120-123``), so without the stamp the instance is validated with ``tenant_id``
None — the exact case those guards skip — and they would be dead code on the one path a crafted POST
exercises.

**``parent`` excludes the instance itself.** ``Asset._validate_hierarchy`` already refuses a
self-parent and any cycle, but an option the form should never accept has no business being offered:
the exclusion is UX, the model walk is the guard.

**``AssetSparePart.asset`` is NOT a form field.** It comes from the route. A parent pk in the POST
body is how a caller grafts a line onto somebody else's machine, and the child carries no ``tenant``
column of its own to catch it — the ``ComplianceCheckForm.requirement`` posture, one sub-module on.
That decision has a second consequence this module has to repair by hand: a field absent from the
form is absent from ``_get_validation_exclusions``' inverse, so Django skips the
``unique_together ("asset", "item")`` check entirely and a duplicate parts line becomes an
``IntegrityError`` rather than a field error. See :meth:`AssetSparePartForm.validate_unique`.

**The two shared helpers below live here rather than in a fifth module** because ``Assets.py`` is
this sub-package's root entity — the other three modules already point at ``Asset`` — so importing
from it adds no dependency edge that did not exist, and the alternative was the same six lines
copied four times. ``apps/scm/forms/__init__.py`` imports this module first, so no cycle is possible.

That argument holds only while the helper is used by THIS sub-module. ``_reject_foreign`` was the
third of them and has moved to ``apps/scm/forms/_common.py``, because 4.14 Labor Management is a
second consumer and a helper shared across sub-modules belongs in the shared module (Backend Package
Structure rule 5) — importing it from a sibling sub-package's entity file would have made 4.14's
forms depend on 4.13's asset register for a rule that has nothing to do with assets. ``_scope_to_tenant``
and ``_keep_current`` stay put; move either the day a second sub-module wants it, not before.
"""
from apps.scm.forms._common import *  # noqa: F401,F403
from apps.scm.forms._common import (TenantUniqueMixin, _employee_parties, _reject_foreign,
                                    _supplier_parties)

from apps.accounting.models import FixedAsset
from apps.core.models import OrgUnit
from apps.scm.models import Asset, AssetSparePart, Item, Location, WorkCenter


# -------------------------------------------------------------------------------------------------
# Shared scoping helpers for the 4.13 form modules. See the module docstring for why they live here.
# -------------------------------------------------------------------------------------------------
def _scope_to_tenant(form, name, queryset):
    """Point one dropdown at this tenant's rows — and at NOTHING when there is no tenant.

    ``TenantModelForm`` already scopes every FK whose target carries a ``tenant`` column, but only
    ``if tenant is not None``; a tenant-less caller falls through to the unscoped default manager.
    The CRUD helpers never render these forms that way, but re-filtering from the model rather than
    chaining off the base's result makes the scoping true by construction instead of true by the
    caller behaving. (The ``ComplianceRequirements._scope_to_tenant`` idiom, verbatim.)
    """
    if name in form.fields:
        form.fields[name].queryset = (
            queryset.filter(tenant=form.tenant) if form.tenant is not None else queryset.none()
        )


def _keep_current(queryset, tenant, current_id):
    """Add a row's ALREADY-STORED choice back into a role-narrowed dropdown.

    A ``core.Party`` dropdown narrowed by ``PartyRole`` has a failure mode a tenant-scoped one does
    not: the role can be removed after the fact. The stored party then vanishes from the ``<select>``,
    the edit form renders with nothing chosen, and saving an unrelated change silently NULLs the FK —
    an asset quietly loses its custodian because somebody edited its notes. The union keeps the
    stored option selectable without widening the list for anybody else.

    Still tenant-scoped in both legs, so this cannot re-admit another workspace's party. On a create
    form ``current_id`` is None and the widening is skipped entirely — the
    ``ComplianceRequirementForm.owner`` reading of the same situation.

    **Why this is one ``filter(Q | Q)`` and NOT ``queryset | Party.objects.filter(...)``.** The
    obvious union raises ``TypeError: Cannot combine a unique query with a non-unique query`` the
    moment it is reached: every caller passes a role-narrowed queryset, those all end in
    ``.distinct()`` (``_supplier_parties`` / ``_employee_parties`` / ``_carrier_parties`` in
    ``apps/scm/forms/_common.py`` — the join through ``PartyRole`` makes it necessary), and Django
    refuses to OR a distinct queryset with a plain one. It is a live 500 rather than a latent one,
    and specifically on the EDIT path only: the ``current_id is None`` guard makes every create form
    return early, so the failure hides from any test that does not first store a party.
    Re-deriving from the model with a ``pk__in`` subquery sidesteps the combination rule altogether
    and does not care whether the caller's queryset is distinct — which is the point, since the
    alternative fix (``.distinct()`` on the right-hand side too) only holds for as long as every
    future caller remembers to keep both sides in the same mode.
    """
    if current_id is None or tenant is None:
        return queryset
    return Party.objects.filter(
        Q(pk__in=queryset.values("pk")) | Q(pk=current_id), tenant=tenant
    ).distinct()


class AssetForm(TenantUniqueMixin, TenantModelForm):
    """One maintainable thing — its identity, its place in the plant, its money and its meter."""

    class Meta:
        model = Asset
        # A WHITELIST, never `Meta.exclude` — a blacklist means the next column added to `Asset`
        # joins this form silently. This is the model's FULL editable set, in declaration order.
        #
        # Deliberately ABSENT, and why: `tenant` is stamped by `crud_create` (and, before that, by
        # TenantUniqueMixin so clean() can read it); `number` is auto-assigned in
        # `TenantNumbered.save()`; `created_at` / `updated_at` are automatic. Everything reliability-
        # or cost-shaped is DERIVED and has no column at all — there is nothing here to keep off.
        fields = [
            # identity
            "code", "name", "asset_type", "status", "criticality", "category",
            "manufacturer", "model_number", "serial_number", "tag_code", "specifications",
            # where it is and who looks after it
            "parent", "location", "org_unit", "work_center",
            "custodian", "supplier", "service_vendor",
            # commercial — `fixed_asset` is a POINTER at accounting's capitalised record and nothing
            # more: 4.13 stores no cost basis, no useful life and no accumulated depreciation.
            "purchase_date", "commissioned_on", "warranty_expires_on", "purchase_cost",
            "fixed_asset",
            # the meter DEFINITION. The readings live in MeterReading, append-only.
            "meter_name", "meter_unit",
            "is_active", "notes",
        ]
        widgets = {
            "specifications": forms.Textarea(attrs={"rows": 3}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        # TenantUniqueMixin.__init__ runs first in the MRO: it calls up to TenantModelForm (which
        # sets self.tenant and applies the base scoping) and then stamps self.instance.tenant. Both
        # halves are load-bearing — see the module docstring.
        super().__init__(*args, **kwargs)

        # --- the hierarchy pointer ----------------------------------------------------------------
        # Self-parenting is not even offered. `Asset._validate_hierarchy` is what REFUSES it (and
        # any longer cycle, under a hard depth cap); this just keeps the impossible option out of
        # the list. `exclude(pk=None)` would exclude nothing, so the guard is explicit.
        # `Asset.__str__` is "code · name" off its own columns — no select_related is owed here.
        parent_qs = Asset.objects.all()
        if self.instance.pk is not None:
            parent_qs = parent_qs.exclude(pk=self.instance.pk)
        _scope_to_tenant(self, "parent", parent_qs)

        # --- where it sits ------------------------------------------------------------------------
        # All three carry their own tenant column, so TenantModelForm already scoped them; re-
        # filtering from the model makes it true by construction rather than true by the caller
        # having passed a tenant. None of the three __str__ methods walks a second FK
        # (Location "code · name", WorkCenter "code · name", OrgUnit name) — checked, not assumed.
        _scope_to_tenant(self, "location", Location.objects.all())
        _scope_to_tenant(self, "work_center", WorkCenter.objects.all())
        _scope_to_tenant(self, "org_unit", OrgUnit.objects.all())

        # --- the three party dropdowns ------------------------------------------------------------
        # Narrowed by ROLE, not merely by tenant: `custodian` is help-texted "person or team
        # accountable", so offering the customer book under that label is noise, and the same goes
        # for a supplier dropdown listing employees. The WorkCenterForm.supervisor precedent.
        #
        # `supplier` (who we bought it from) and `service_vendor` (the default contractor) are the
        # same commercial set, so both take `_supplier_parties`. ModelChoiceField's queryset setter
        # calls `.all()`, which clones, so handing one queryset to two fields cannot share
        # evaluation state.
        if "custodian" in self.fields:
            self.fields["custodian"].queryset = _keep_current(
                _employee_parties(self.tenant), self.tenant, self.instance.custodian_id)
        counterparties = _supplier_parties(self.tenant)
        for name in ("supplier", "service_vendor"):
            if name in self.fields:
                self.fields[name].queryset = _keep_current(
                    counterparties, self.tenant, getattr(self.instance, f"{name}_id", None))

        # --- the accounting link --------------------------------------------------------------------
        # Deliberately NOT narrowed by `FixedAsset.status`. An operational asset legitimately points
        # at a book record that is still `cip` (commissioning) or already `disposed` (sold but still
        # on site pending collection) — filtering to `active` would hide exactly the rows somebody is
        # reconciling. `FixedAsset.__str__` is "number · name" off its own columns.
        _scope_to_tenant(self, "fixed_asset", FixedAsset.objects.all())

    def clean(self):
        """Re-check every chosen FK against this workspace — see :func:`_reject_foreign`."""
        cleaned = super().clean()
        _reject_foreign(self, cleaned, Asset.TENANT_SCOPED_FKS)
        return cleaned


class AssetSparePartForm(TenantModelForm):
    """One item this asset consumes when it is serviced. ``asset`` comes from the ROUTE, never POST.

    Four fields and no parent pointer. See the module docstring for why the parent is not a field
    and what that costs — :meth:`validate_unique` is the repair.
    """

    class Meta:
        model = AssetSparePart
        # A WHITELIST. `asset` is absent BY DESIGN (the route supplies it — module docstring); the
        # model has no other columns.
        fields = ["item", "quantity_per_service", "is_critical", "notes"]

    def __init__(self, *args, asset=None, **kwargs):
        super().__init__(*args, **kwargs)

        # THE STAMP, one level down from the tenant. `AssetSparePart` has no `tenant` column at all,
        # so its cross-tenant guard reads `self.asset.tenant_id` — and on create that relation is
        # unset until the view attaches the parent AFTER `is_valid()`. Stamping it here is what makes
        # both that guard and `validate_unique` below run on the create path at all. Only when it is
        # unset: an edit already carries its parent and must never be repointed at another one.
        # (The `ComplianceCheckForm.requirement` posture.)
        if asset is not None and self.instance.asset_id is None:
            self.instance.asset = asset
        # RelatedObjectDoesNotExist subclasses AttributeError, so the default fires cleanly when the
        # instance has no parent yet rather than raising out of the constructor.
        self.asset = asset if asset is not None else getattr(self.instance, "asset", None)

        # 4.3's ONE item master — there is no SparePart table. Not narrowed to `is_spare_part=True`:
        # that flag marks what the storeroom CONSIDERS a spare, and a machine legitimately consumes
        # an ordinary consumable (grease, filters) that nobody has flagged. Narrowing it would make
        # the obvious line un-addable with no way to see why.
        _scope_to_tenant(self, "item", Item.objects.all())

    def clean(self):
        """The item must belong to the ASSET's workspace — checked through the parent.

        ``AssetSparePart.clean()`` carries the same rule and is the guard at the database boundary;
        this repeats it at the form boundary so the check is live even when the parent stamp above
        did not happen (an unparented form is itself a refusal, not a pass).
        """
        cleaned = super().clean()
        item = cleaned.get("item")
        if item is not None:
            asset_tenant_id = getattr(self.asset, "tenant_id", None)
            if asset_tenant_id is None or item.tenant_id != asset_tenant_id:
                self.add_error("item", "That item belongs to another workspace.")
        return cleaned

    def validate_unique(self):
        """Make ``unique_together ("asset", "item")`` actually validate on this form.

        Django skips a ``unique_together`` entirely if ANY of its fields is excluded from
        validation, and a field that is not on the form is always excluded. ``asset`` is not on this
        form by design, so out of the box the check silently does nothing and listing the same part
        twice on one machine passes ``is_valid()`` and then raises an uncaught ``IntegrityError`` —
        a 500 on an ordinary user mistake, and precisely the failure ``TenantUniqueMixin`` exists to
        stop one level up. This is that mixin's ``validate_unique`` half, re-aimed at the parent FK
        instead of at ``tenant``; the constructor's stamp is the other half, without which the check
        would run against ``asset=None`` and match nothing.
        """
        exclude = set(self._get_validation_exclusions())
        exclude.discard("asset")
        try:
            self.instance.validate_unique(exclude=exclude)
        except ValidationError as e:
            self._update_errors(e)
