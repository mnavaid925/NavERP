"""Shared base + imports for the projects models package.

One sub-package per NavERP sub-module (7.1-…), one module per entity. Every entity module does
``from apps.projects.models._base import *`` to pull in the django toolkit and the abstract
``TenantOwned`` base. The package __init__ re-exports every model, so
``from apps.projects.models import Project`` works everywhere (admin, seeder, tests).

The base is a local copy of the proven apps/crm + apps/accounting + apps/scm + apps/inventory +
apps/procurement pattern — peer apps deliberately don't import each other's internals.

**Ownership:** 7.1 ships the intake → charter → stakeholder → kickoff chain. It ships NO money
columns on ``Project`` (those are 7.4's cost & budget management, and ``accounting.Project``
already carries the costing lens), and NO second attachment store (the signed charter is a
``core.Document``).
"""
from decimal import Decimal

from django.conf import settings  # noqa: F401  (entity modules reference AUTH_USER_MODEL)
from django.core.exceptions import ValidationError  # noqa: F401
from django.core.validators import MaxValueValidator, MinValueValidator  # noqa: F401
from django.db import IntegrityError, models, transaction
from django.db.models import F, Q, Sum  # noqa: F401
from django.utils import timezone  # noqa: F401

from apps.core.utils import next_number


ZERO = Decimal("0")

#: Ceiling of the money column shape this app writes (DecimalField(14, 2)) — mirrors
#: procurement.MAX_Q2 / scm.MAX_Q2 so computed figures are clamped to what the column holds
#: instead of dying as a driver DataError.
MAX_Q2 = Decimal("9999999999.99")


def q2(value):
    """Quantize to 2dp AND clamp to what a DecimalField(14, 2) holds (same contract as scm.q2)."""
    return min(max(Decimal(value or ZERO), -MAX_Q2), MAX_Q2).quantize(Decimal("0.01"))


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
    """Adds a human-readable per-tenant ``number`` (e.g. ``PRQ-00001``) assigned once in
    ``save()`` with a retry-on-collision guard — the same proven base the peer apps use, built
    on ``apps.core.utils.next_number``."""

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
