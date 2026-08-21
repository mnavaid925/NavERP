"""Shared base + imports for the inventory models package.

One sub-package per NavERP sub-module (5.1-…), one module per entity. Every entity module does
``from apps.inventory.models._base import *`` to pull in the django toolkit and the abstract
``TenantOwned`` base. The package __init__ re-exports every model, so
``from apps.inventory.models import ItemPrice`` works everywhere (admin, seeder, tests).

The base is a local copy of the proven apps/crm + apps/accounting + apps/scm pattern — peer apps
deliberately don't import each other's internals.

**Ownership (L29/L36):** this app does NOT re-declare the item spine. ``scm.Item``,
``scm.ItemCategory``, ``scm.UOM``, ``scm.Location`` and the append-only ``scm.StockMove`` ledger
landed with SCM 4.3, which OWNS them exactly as ``apps/accounting`` owns the ledger. Module 5 is
the catalog/planning layer AROUND that spine: every model here points at ``scm.Item`` by string
and extends it.
"""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import IntegrityError, models, transaction
from django.db.models import F, Q, Sum
from django.utils import timezone

from apps.core.utils import next_number


ZERO = Decimal("0")


class TenantOwned(models.Model):
    """Tenant FK + created/updated timestamps. ``related_name="+"`` — views always filter
    ``Model.objects.filter(tenant=request.tenant)`` so no reverse accessor is needed and the
    abstract base never clashes across its many subclasses."""

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, related_name="+", db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class TenantNumbered(TenantOwned):
    """Adds a human-readable per-tenant ``number`` (e.g. ``VC-00001``) assigned once in
    ``save()`` with a retry-on-collision guard. Local copy of the proven apps/scm base —
    peer apps deliberately don't import each other's internals."""

    NUMBER_PREFIX = ""

    number = models.CharField(max_length=20, editable=False)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self.number and self.tenant_id and self.NUMBER_PREFIX:
            for _ in range(5):
                self.number = next_number(type(self), self.tenant, self.NUMBER_PREFIX)
                try:
                    with transaction.atomic():
                        return super().save(*args, **kwargs)
                except IntegrityError:
                    self.number = ""
        return super().save(*args, **kwargs)
