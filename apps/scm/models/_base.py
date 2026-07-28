"""Shared base + imports for the scm models package.

One sub-package per NavERP sub-module (4.1-4.19), one module per entity. Every entity module does
``from apps.scm.models._base import *`` to pull in the django toolkit and the abstract
``TenantOwned`` / ``TenantNumbered`` bases. The package __init__ re-exports every model, so
``from apps.scm.models import PurchaseOrder`` works everywhere (admin, seeder, tests).

The bases are a local copy of the proven apps/crm + apps/accounting pattern — peer apps
deliberately don't import each other's internals.

``secrets`` is re-exported through the star import for the same reason ``apps/crm/models/_base.py``
carries it: 4.10's ``ReturnAuthorization.public_token`` is minted once in ``save()`` with
``secrets.token_urlsafe(32)``, exactly as ``crm.Case.public_token`` is. An unguessable bearer token
is the whole security model of a login-free customer status page, so it comes from the CSPRNG and
never from ``random`` or a uuid4 hex.
"""
import secrets
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import IntegrityError, models, transaction
from django.db.models import F, Q, Sum
from django.utils import timezone

from apps.core.utils import next_number


ZERO = Decimal("0")

#: Ceilings of the two money/quantity column shapes this app uses — DecimalField(max_digits=14,
#: decimal_places=2) and (14, 4).
MAX_Q2 = Decimal("9999999999.99")
MAX_Q4 = Decimal("9999999999.9999")


def q2(value):
    """Quantize to 2dp AND clamp to what a DecimalField(14, 2) holds.

    Both halves matter. A long Decimal fails to save; an OVER-RANGE one raises ``DataError`` inside
    ``bulk_update``, which fails the whole batch rather than the one offending row. Every writer of
    a computed quantity goes through here so a single poisoned figure can only degrade its own row.
    """
    return min(max(Decimal(value or ZERO), -MAX_Q2), MAX_Q2).quantize(Decimal("0.01"))


def q4(value):
    """The 4dp sibling of :func:`q2` — see there for why clamping, not just quantizing, is required."""
    return min(max(Decimal(value or ZERO), -MAX_Q4), MAX_Q4).quantize(Decimal("0.0001"))


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
    """Adds a human-readable per-tenant ``number`` (e.g. ``PO-00001``) assigned once in
    ``save()`` with a retry-on-collision guard."""

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
