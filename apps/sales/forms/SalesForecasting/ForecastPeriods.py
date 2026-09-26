"""8.4 Sales Forecasting — ForecastPeriod form.

``start_date`` / ``end_date`` are absent by construction (they are ``editable=False`` on the
model, so L22 excludes them structurally), and ``tenant`` / ``number`` are absent for the
same reason. ``TenantUniqueMixin`` covers the composite
``sales_fcp_tpt_ypn_uniq`` constraint, which a stock ``validate_unique`` cannot see.
"""
from apps.accounting.models import Currency
from apps.crm.models import SalesQuota
from apps.sales.forms._common import TenantModelForm, TenantUniqueMixin
from apps.sales.models.SalesForecasting.ForecastPeriods import ForecastPeriod


class ForecastPeriodForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = ForecastPeriod
        fields = [
            "name",
            "period_type",
            "period_year",
            "period_number",
            "rollup_dimension",
            "reporting_currency",
            "fx_rate_source_date",
            "is_active",
            "is_locked",
        ]

    def __init__(self, *args, tenant=None, user=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)
        self.user = user
        # accounting.Currency is GLOBAL (no tenant FK), so TenantModelForm's automatic FK
        # tenant-scoping does not apply here -- an explicit active queryset, never filtered
        # by tenant (L29). Slicing keeps the dropdown bounded; the full list is [:500] too.
        if tenant is None:
            self.fields["reporting_currency"].queryset = Currency.objects.none()
        else:
            self.fields["reporting_currency"].queryset = Currency.objects.filter(
                is_active=True,
            ).order_by("code")[:500]
        # A locked period's shape is frozen: only is_active / fx_rate_source_date may move.
        if self.instance.pk and self.instance.is_locked:
            for field_name in (
                "name",
                "period_type",
                "period_year",
                "period_number",
                "rollup_dimension",
            ):
                self.fields[field_name].disabled = True
        # Locking is a tenant-admin right (the Approve/Override role check, 0.8). A
        # non-admin never sees the checkbox as usable and never gets True written.
        if user is not None and not (
            getattr(user, "is_superuser", False) or getattr(user, "is_tenant_admin", False)
        ):
            self.fields["is_locked"].disabled = True
            self.initial["is_locked"] = False

    def clean(self):
        cleaned = super().clean()
        if self.tenant is None:
            self.add_error(None, "A tenant workspace is required.")
        period_type = cleaned.get("period_type")
        period_number = cleaned.get("period_number")
        if period_type and period_number is not None:
            maximum = ForecastPeriod.PERIOD_NUMBER_MAX.get(period_type, 12)
            if not 1 <= period_number <= maximum:
                label = dict(SalesQuota.PERIOD_CHOICES).get(period_type, period_type).lower()
                self.add_error(
                    "period_number",
                    f"A {label} period number must be between 1 and {maximum}.",
                )
        # start_date / end_date are computed from type+year+number, so the window is derived
        # here and range-checked rather than trusted (contract 4.1). The frozen-field branch
        # above means a locked period always reproduces its own stored window.
        period_year = cleaned.get("period_year")
        if period_type and period_year and period_number:
            probe = ForecastPeriod(
                period_type=period_type,
                period_year=period_year,
                period_number=period_number,
            )
            start, end = probe._window()
            if end < start:
                self.add_error("end_date", "The period end cannot precede its start.")
            if not self.instance.pk or not self.instance.is_locked:
                self.instance.start_date = start
                self.instance.end_date = end
        return cleaned
