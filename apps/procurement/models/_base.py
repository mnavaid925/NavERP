"""Shared base + imports for the procurement models package.

One sub-package per NavERP sub-module (6.1-…), one module per entity. Every entity module does
``from apps.procurement.models._base import *`` to pull in the django toolkit and the abstract
``TenantOwned`` base. The package __init__ re-exports every model, so
``from apps.procurement.models import ProcurementAlert`` works everywhere (admin, seeder, tests).

The base is a local copy of the proven apps/crm + apps/accounting + apps/scm + apps/inventory
pattern — peer apps deliberately don't import each other's internals.

**Ownership (L29/L36):** this app does NOT re-declare the procurement document spine.
``scm.PurchaseRequisition``, ``scm.RFQ``, ``scm.PurchaseOrder`` and ``scm.GoodsReceiptNote``
landed with SCM 4.1, which OWNS them exactly as ``apps/accounting`` owns the ledger. Module 6 is
the people/workflow layer AROUND that spine: the 6.1 portal reads those documents and its Quick
Requisition Entry WRITES into ``scm.PurchaseRequisition`` — it never declares a parallel one.
"""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import IntegrityError, models, transaction
from django.db.models import F, Q, Sum
from django.utils import timezone


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
