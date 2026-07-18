"""Shared toolkit for the scm forms package.

One sub-package per NavERP sub-module (4.1-4.19), one module per entity, mirroring models/ views/
urls/. Every entity module does ``from apps.scm.forms._common import *`` then imports only the
models it binds. The package __init__ re-exports every form + formset.

Scoping note (IMPORTANT): ``TenantModelForm`` auto-scopes a ModelChoiceField only when the TARGET
model has its own ``tenant`` field. Child tables here (``PurchaseOrderLine``, ``RFQLine``) deliberately
have no tenant FK — they are reached through their parent — so any dropdown pointing at one MUST be
scoped by hand to the parent object, or the select would list every tenant's rows. See
``_scope_to_parent``.
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
