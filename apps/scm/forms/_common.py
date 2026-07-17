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
from django import forms
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


def _scope_to_parent(form, field_name, queryset):
    """Point a child-table dropdown at only its parent's rows.

    Used where the FK target has no tenant field of its own, so TenantModelForm cannot scope it.
    Falls back to an EMPTY queryset when there is no parent yet — never to the unscoped default,
    which would leak other tenants' rows into the select.
    """
    if field_name in form.fields:
        form.fields[field_name].queryset = queryset
