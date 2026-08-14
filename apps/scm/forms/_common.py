"""Shared toolkit for the scm forms package.

One sub-package per NavERP sub-module (4.1-4.19), one module per entity, mirroring models/ views/
urls/. Every entity module does ``from apps.scm.forms._common import *`` then imports only the
models it binds. The package __init__ re-exports every form + formset.

Scoping note (IMPORTANT): ``TenantModelForm`` auto-scopes a ModelChoiceField only when the TARGET
model has its own ``tenant`` field. Child tables here (``PurchaseOrderLine``, ``RFQLine``) deliberately
have no tenant FK — they are reached through their parent — so any dropdown pointing at one MUST be
scoped by hand to the parent object, or the select would list every tenant's rows. See
``_scope_to_parent``.

Boundary note: scoping a dropdown is presentation. ``_reject_foreign`` is the re-check that a
crafted POST has to get past, and it lives HERE rather than in any one sub-module's entity file
because more than one sub-module needs it (Backend Package Structure rule 5) — 4.13 Asset Management
and 4.14 Labor Management both call it, and a copy per sub-package is how two implementations of one
security rule start disagreeing.

Note on the leading underscores: this module carries no ``__all__``, so ``import *`` skips every
private name in it. That is deliberate and it is the reason each entity module follows its
``from apps.scm.forms._common import *`` with an EXPLICIT
``from apps.scm.forms._common import _helper, _helper`` line — the star pulls the public toolkit
(``forms``, ``Q``, ``Party``, ``TenantModelForm``, ``inlineformset_factory``, ``Decimal``,
``TenantUniqueMixin``) and the explicit line names the private helpers the module actually uses, so
a reader can see at the top of any entity file which shared rules it is subject to.
"""
from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.forms import inlineformset_factory

from apps.core.forms import TenantModelForm
from apps.core.models import Party

from apps.accounting.models import Currency


def _active_currencies(form):
    """Constrain a ``currency`` field to active currencies (Currency is GLOBAL — no tenant FK — so
    the TenantModelForm base does not scope it)."""
    if "currency" in form.fields:
        form.fields["currency"].queryset = Currency.objects.filter(is_active=True)


def _supplier_parties(tenant):
    """Parties this tenant can buy from.

    ``core.PartyRole`` distinguishes ``supplier`` from ``vendor`` and the ERD nominally assigns SCM
    the supplier role. In practice a party tagged by the accounting module carries ``vendor``, so
    accept BOTH rather than silently hiding half the counterparties from the buyer.
    """
    if tenant is None:
        return Party.objects.none()
    return Party.objects.filter(tenant=tenant, roles__role__in=("supplier", "vendor")).distinct()


def _customer_parties(tenant):
    """Parties this tenant can sell to (4.5 OMS).

    Single role, unlike ``_supplier_parties``: there is no second spelling of "customer" in
    ``PartyRole.ROLE_CHOICES`` to fall back on, so no OR is needed here.
    """
    if tenant is None:
        return Party.objects.none()
    return Party.objects.filter(tenant=tenant, roles__role="customer").distinct()


def _carrier_parties(tenant):
    """Parties this tenant can hire to move freight (4.6 TMS Carrier master).

    A carrier is procured from like a supplier, so the same supplier/vendor roles apply — plus
    ``partner`` (3PLs are frequently onboarded as partners, not AP vendors). Mirrors
    ``_supplier_parties`` accepting more than one spelling rather than hiding half the counterparties.
    """
    if tenant is None:
        return Party.objects.none()
    return Party.objects.filter(
        tenant=tenant, roles__role__in=("supplier", "vendor", "partner")).distinct()


def _employee_parties(tenant):
    """Parties this tenant can staff a work centre with (4.8 supervisors and machine operators).

    Single role, like ``_customer_parties`` — ``employee`` has no second spelling in
    ``PartyRole.ROLE_CHOICES``. Without this the supervisor/operator dropdowns offer the entire
    party book, customers and carriers included.
    """
    if tenant is None:
        return Party.objects.none()
    return Party.objects.filter(tenant=tenant, roles__role="employee").distinct()


class TenantUniqueMixin:
    """Makes a model's ``unique_together`` that INCLUDES ``tenant`` actually validate on a form.

    Two separate things both have to be true or the check silently does nothing:

    1. The instance needs its tenant — `tenant` is never a form field and `crud_create`/`crud_edit`
       only assign it AFTER `is_valid()`, so without this the check would run against `tenant=None`.
    2. `tenant` must be removed from the validation exclusions — Django skips a `unique_together`
       entirely if ANY of its fields is excluded, and a non-form field is always excluded. Stamping
       the tenant alone is NOT enough; this is the half that actually enables the check.

    Without both, a duplicate SKU/code/lot-number passes `is_valid()` and then raises an uncaught
    IntegrityError (a 500) on `.save()` — an everyday user mistake crashing a mainline CRUD path.
    Mix this in BEFORE TenantModelForm on any scm form whose model has such a constraint.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None and self.instance.tenant_id is None:
            self.instance.tenant = self.tenant

    def validate_unique(self):
        exclude = set(self._get_validation_exclusions())
        exclude.discard("tenant")
        try:
            self.instance.validate_unique(exclude=exclude)
        except ValidationError as e:
            self._update_errors(e)


def _scope_to_parent(form, field_name, queryset):
    """Point a child-table dropdown at only its parent's rows.

    Used where the FK target has no tenant field of its own, so TenantModelForm cannot scope it.
    Falls back to an EMPTY queryset when there is no parent yet — never to the unscoped default,
    which would leak other tenants' rows into the select.
    """
    if field_name in form.fields:
        form.fields[field_name].queryset = queryset


def _keep_current(form, name, base_queryset):
    """Union a field's CURRENTLY-STORED choice back into its narrowed dropdown.

    Every narrowing a form applies on top of tenant scoping — ``is_active=True``, a ``PartyRole``,
    "dedicated to this client" — can legitimately exclude the value a row ALREADY holds, because the
    master can be deactivated or the role removed after the row was saved. The stored option then
    vanishes from the ``<select>``, the browser posts an empty value, and saving an unrelated change
    silently NULLs the FK for somebody who only came to fix a typo. On a required field it refuses
    the save instead, with an error naming a field the user never touched. A no-op whenever the
    stored value still qualifies (the common case); it exists for the one that no longer does.

    ``base_queryset`` is the UN-narrowed one, so any ``select_related`` the dropdown's ``__str__``
    needs survives the rebuild — rebuilding off the bare default manager drops it and reintroduces
    one query per option. Pass a TENANT-SCOPED base: the union re-admits ``Q(pk=current)``
    unconditionally, so an unscoped base would re-admit a foreign row if one ever reached the column.

    Written as one ``filter(Q | Q)`` over a ``pk__in`` subquery rather than ``queryset | other``:
    role-narrowed party querysets all end in ``.distinct()`` and Django raises
    ``TypeError: Cannot combine a unique query with a non-unique query`` the moment such a queryset
    is OR-ed with a plain one — a live 500 on the EDIT path only.

    Lives HERE, not in one sub-module's entity file, because more than one sub-module needs it
    (Backend Package Structure rule 5) — 4.17 Third-Party Logistics and 4.18 Finance Integration were
    the two that made it shared, the same argument that moved ``_reject_foreign`` here for 4.13/4.14.
    Three older private copies of this rule still exist under different signatures
    (``AssetManagement/Assets.py``, ``ThirdPartyLogistics/LogisticsClients.py`` and
    ``ThirdPartyLogistics/ClientRateCards.py``); consolidating them onto this one is an app-wide pass,
    not one sub-module's to fork.
    """
    if name not in form.fields:
        return
    current = getattr(form.instance, f"{name}_id", None)
    if current is None:
        return
    narrowed = form.fields[name].queryset
    form.fields[name].queryset = base_queryset.filter(
        Q(pk__in=narrowed.values("pk")) | Q(pk=current)).distinct()


def _reject_foreign(form, cleaned, names):
    """Field-error any chosen FK whose row belongs to another workspace.

    A form's narrowed FK queryset is UX, not an authorization boundary: **a narrowed ``<select>``
    has never held against a crafted POST** (L39 §2), and every form in this package is reachable by
    any logged-in member of any workspace. So EVERY tenant-scoped FK is re-checked here, at the form
    boundary. The models' own ``clean()`` methods carry the same guard and it is the one that holds
    at the database boundary; this repeats it at the FORM boundary for two reasons a reviewer should
    not have to rediscover:

    * it does not depend on the instance's tenant having been stamped before validation, so it is
      live on the create path whether or not a given form mixes in the stamp; and
    * it keys the error on a field the FORM has, which is what makes it renderable. A model error
      keyed on a column that is not on the form raises ``ValueError`` out of ``add_error`` — a 500
      instead of a field error. (``MeterReading.clean()``'s ``recorded_by`` leg is exactly that
      shape, which is why the view must stamp that field AFTER ``is_valid()``.)

    ``names`` is normally the model's own ``TENANT_SCOPED_FKS`` — one table, read by both boundaries
    — plus any soft reference (a ``core.Party`` pointer) that table deliberately omits.
    """
    tenant_id = form.tenant.pk if form.tenant is not None else None
    for name in names:
        chosen = cleaned.get(name)
        if chosen is None:
            continue
        if getattr(chosen, "tenant_id", None) != tenant_id:
            form.add_error(name, "That record belongs to another workspace.")
