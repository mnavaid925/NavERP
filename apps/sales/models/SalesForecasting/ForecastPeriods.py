"""8.4 Sales Forecasting — the forecast period register.

A ``ForecastPeriod`` is the bucket every per-rep forecast call rolls *into*: it names the
window being forecast (month / quarter / year, reusing ``crm.SalesQuota.PERIOD_CHOICES``
verbatim rather than re-spelling the vocabulary), which of the three Dynamics rollup
templates the period reports on, and the reporting currency its amounts are stated in.

Two rules are structural here and cannot be undone by a later edit:

* ``start_date`` / ``end_date`` are ``editable=False`` **computed** columns, so they are
  excluded from every ``ModelForm`` automatically (L22) and can never be hand-typed.
* ``accounting.Currency`` is a **global** master with no ``tenant`` FK, so
  ``reporting_currency`` is deliberately never tenant-checked (L29).
"""
import calendar
from datetime import date
from decimal import Decimal

from django.apps import apps as django_apps
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.crm.models import SalesQuota
from apps.sales.models._base import TenantNumbered


def _optional_sales_model(name):
    """Resolve a later-pass 8.4 model through the app registry, or ``None``.

    ``ForecastSubmission.period`` and ``ForecastScenario.period`` are both ``PROTECT`` FKs
    (contract 3.2 / 3.4), so deleting a period that still carries either must be refused.
    Those siblings are built in later passes, so they are looked up through the app registry
    rather than imported: a module-level import of a model that does not exist yet would
    break ``makemigrations`` for the whole project.
    """
    try:
        return django_apps.get_model("sales", name)
    except LookupError:
        return None


class ForecastPeriod(TenantNumbered):
    NUMBER_PREFIX = "FCP"

    ROLLUP_DIMENSION_CHOICES = [
        ("user", "Sales Representative"),
        ("org_unit", "Organizational Unit"),
        ("territory", "Territory"),
    ]

    #: month 1-12 / quarter 1-4 / year exactly 1 -- tightened per type in ``clean()``.
    PERIOD_NUMBER_MAX = {"month": 12, "quarter": 4, "year": 1}

    name = models.CharField(max_length=160)
    period_type = models.CharField(
        max_length=10,
        choices=SalesQuota.PERIOD_CHOICES,
        default="quarter",
    )
    period_year = models.PositiveSmallIntegerField(
        default=timezone.localdate().year,
        validators=[MinValueValidator(1970), MaxValueValidator(9999)],
    )
    period_number = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(12)],
    )
    # Computed from type + year + number. editable=False auto-excludes both from every form.
    start_date = models.DateField(editable=False)
    end_date = models.DateField(editable=False)
    rollup_dimension = models.CharField(
        max_length=12,
        choices=ROLLUP_DIMENSION_CHOICES,
        default="user",
    )
    # accounting.Currency is GLOBAL (no tenant FK) -- never tenant-check this one (L29).
    reporting_currency = models.ForeignKey(
        "accounting.Currency",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_forecast_periods",
    )
    fx_rate_source_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_locked = models.BooleanField(default=False)

    class Meta:
        ordering = ["-period_year", "period_number", "name"]
        verbose_name_plural = "forecast periods"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="sales_fcp_tenant_number_uniq",
            ),
            models.UniqueConstraint(
                fields=["tenant", "period_type", "period_year", "period_number"],
                name="sales_fcp_tpt_ypn_uniq",
            ),
            models.CheckConstraint(
                Q(period_number__gte=1) & Q(period_number__lte=12),
                name="sales_fcp_period_number_valid",
            ),
        ]
        indexes = [
            models.Index(
                fields=["tenant", "is_active"],
                name="sales_fcp_tenant_active_idx",
            ),
            models.Index(
                fields=["tenant", "period_type", "period_year"],
                name="sales_fcp_tnt_type_year_idx",
            ),
        ]

    @property
    def label(self):
        text = f"{self.get_period_type_display()} {self.period_year}"
        if self.period_type != "year":
            text = f"{text} · P{self.period_number}"
        return text

    @property
    def is_current(self):
        today = timezone.localdate()
        return bool(self.start_date and self.end_date) and self.start_date <= today <= self.end_date

    @property
    def period_elapsed_pct(self):
        """How much of the window has elapsed, as a 0-100 ``Decimal``.

        0 before the window opens, 100 once it has closed. Inclusive day counts, so a period
        ending today reads as elapsed rather than still in progress.
        """
        if not self.start_date or not self.end_date:
            return Decimal("0")
        total_days = (self.end_date - self.start_date).days + 1
        if total_days <= 0:
            return Decimal("0")
        today = timezone.localdate()
        if today <= self.start_date:
            return Decimal("0")
        if today >= self.end_date:
            return Decimal("100")
        elapsed = Decimal((today - self.start_date).days + 1) * Decimal("100")
        return (elapsed / Decimal(total_days)).quantize(Decimal("0.01"))

    def _window(self):
        """``(start_date, end_date)`` for this period's type / year / number."""
        year = self.period_year
        number = self.period_number or 1
        if self.period_type == "month":
            first_month = last_month = number
        elif self.period_type == "quarter":
            first_month = ((number - 1) * 3) + 1
            last_month = first_month + 2
        else:
            first_month, last_month = 1, 12
        return (
            date(year, first_month, 1),
            date(year, last_month, calendar.monthrange(year, last_month)[1]),
        )

    def _number_is_in_range(self):
        maximum = self.PERIOD_NUMBER_MAX.get(self.period_type, 12)
        return 1 <= (self.period_number or 0) <= maximum

    def clean(self):
        super().clean()
        if not self._number_is_in_range():
            maximum = self.PERIOD_NUMBER_MAX.get(self.period_type, 12)
            raise ValidationError({
                "period_number": (
                    f"A {self.get_period_type_display().lower()} period number must be "
                    f"between 1 and {maximum}."
                ),
            })
        start, end = self._window()
        self.start_date = start
        self.end_date = end
        if end < start:
            raise ValidationError({"end_date": "The period end cannot precede its start."})

    def save(self, *args, **kwargs):
        # start_date/end_date are computed, never supplied; derive them on a direct .save()
        # (seeder, service, shell) so they can never be left stale against type/year/number.
        if self.start_date is None or self.end_date is None:
            self.start_date, self.end_date = self._window()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        for model_name, message in (
            ("ForecastSubmission", "A forecast period with submissions cannot be deleted."),
            ("ForecastScenario", "A forecast period with scenarios cannot be deleted."),
        ):
            model = _optional_sales_model(model_name)
            if self.pk and model is not None:
                if model.objects.filter(period_id=self.pk, tenant_id=self.tenant_id).exists():
                    raise ValidationError(message)
        return super().delete(*args, **kwargs)

    def __str__(self):
        return f"{self.number} · {self.label}"

