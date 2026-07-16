"""Shared base + imports for the HRM models package.

apps/hrm/models.py was split into this package (one sub-package per NavERP sub-module 3.1-3.41,
one module per entity, mirroring forms/ views/ urls/). Every entity module does
``from apps.hrm.models._base import *``; the package __init__ re-exports every model so
``from apps.hrm.models import EmployeeProfile`` is unchanged. Models sit deeper than the app root
but Django still derives ``app_label="hrm"`` from the app config -> migrations are unaffected.

The import block below is the ORIGINAL models.py header, verbatim.
"""
import calendar
import math
import secrets
from datetime import date, datetime, timedelta
from decimal import Decimal
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import IntegrityError, models, transaction
from django.db.models import Count, Q, Sum
from django.utils import timezone
from apps.core.utils import next_number


ZERO = Decimal("0")


def _json_safe(value):
    """Coerce a model/field value into a JSON-serializable form for ``field_changes`` storage and for
    comparing a stored snapshot against a live value (dates → ISO strings, Decimals → strings;
    bools/ints/strings/None pass through). Shared by the 3.25 change-request assembly (views) and
    ``EmployeeInfoChangeRequest.apply()``'s lost-update guard."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return str(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _advance_months(d, months):
    """Advance a ``date`` by N calendar months, clamping the day to the target month's length
    (stdlib month-math — ``calendar.monthrange``; no ``dateutil`` dependency). Shared by
    ``LearningProgress.certification_expires_on`` (3.23) and ``TrainingCertificate.save()`` (3.24)."""
    total = d.month - 1 + months
    y, m = d.year + total // 12, total % 12 + 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


# ---------------------------------------------------------------------------
# Shared abstract bases (mirror the proven apps/crm + apps/accounting pattern;
# local copy — peer domain apps don't import each other).
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
    """Adds a human-readable per-tenant ``number`` (e.g. ``EMP-00001``) assigned once in
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
