"""Shared base + imports for the accounting models package.

apps/accounting/models.py + models_advanced.py were split into this package (one sub-package per
sub-module 2.1-2.15, one module per entity). Every entity module does
``from apps.accounting.models._base import *`` to pull in the django toolkit and the abstract
``TenantOwned`` / ``TenantNumbered`` bases. The package __init__ re-exports every model, so
``from apps.accounting.models import Invoice`` (CRM, HRM, admin, the seeder, every test) is unchanged.

This also dissolves the old late-import cycle: models.py used to do ``from .models_advanced import *``
at the BOTTOM while models_advanced did ``from .models import ZERO, TenantNumbered, TenantOwned`` —
both now simply import the bases from here.
"""
import calendar
import hashlib
import secrets
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, models, transaction
from django.db.models import Q, Sum

from apps.core.utils import next_number


ZERO = Decimal("0")


def add_months(d, n):
    """Return ``d`` shifted forward by ``n`` calendar months, clamping the day to month-end."""
    month_index = d.month - 1 + n
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return d.replace(year=year, month=month, day=day)


# ---------------------------------------------------------------------------
# Shared abstract bases (mirror the proven apps/crm pattern; local copy — peer
# apps don't import each other).
# ---------------------------------------------------------------------------
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
    """Adds a human-readable per-tenant ``number`` (e.g. ``JE-00001``) assigned once in
    ``save()`` with a retry-on-collision guard (mirrors ``tenants.SubscriptionInvoice``)."""

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
