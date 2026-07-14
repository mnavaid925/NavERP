"""Shared imports for the accounting forms package.

apps/accounting/forms.py + forms_advanced.py were split into this package (one sub-package per
sub-module 2.1-2.15, one module per entity, mirroring models/ views/ urls/). Every entity module does
``from apps.accounting.forms._common import *`` then imports only the models it binds. The package
__init__ re-exports every form + formset, so ``from apps.accounting.forms import InvoiceForm`` is
unchanged (and the advanced forms are now importable from here too, not a separate module).
"""
from django import forms
from django.forms import inlineformset_factory

from apps.core.forms import TenantModelForm
from apps.core.models import Party

from apps.accounting.models import Currency


def _active_currencies(form):
    """Constrain any ``currency`` field to active currencies (Currency is global, so the
    TenantModelForm base does not scope it)."""
    if "currency" in form.fields:
        form.fields["currency"].queryset = Currency.objects.filter(is_active=True)
