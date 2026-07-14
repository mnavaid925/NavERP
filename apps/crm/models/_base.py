"""Shared base + imports for the CRM models package.

apps/crm/models.py was split into this package (one sub-package per CRM sub-module 1.1-1.12, one
module per entity). Every entity module does ``from apps.crm.models._base import *`` to pull in the
django/base toolkit and the abstract ``TenantNumbered``. The package __init__ re-exports every model,
so ``from apps.crm.models import Lead`` (admin, seeder, analytics, tests) keeps working unchanged.

Model modules live deeper than the app root, but Django still derives ``app_label="crm"`` from the
containing app config, so the migration state is identical to the pre-split monolith.
"""
import calendar
import secrets
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import IntegrityError, models, transaction
from django.utils import timezone

from apps.core.utils import next_number


class TenantNumbered(models.Model):
    """Abstract base: tenant FK + auto per-tenant ``number`` + created/updated timestamps.

    Subclasses set ``NUMBER_PREFIX`` (e.g. ``"LEAD"``). ``save()`` assigns the next number
    once (only when blank) and retries on the rare concurrent ``unique_together(tenant,
    number)`` collision — mirrors ``tenants.SubscriptionInvoice.save()``.
    """

    NUMBER_PREFIX = ""

    # related_name="+" : no reverse accessor needed (views filter Model.objects.filter(tenant=...)),
    # and it sidesteps reverse-name clashes across the abstract base's subclasses.
    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, related_name="+", db_index=True)
    number = models.CharField(max_length=20, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

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
