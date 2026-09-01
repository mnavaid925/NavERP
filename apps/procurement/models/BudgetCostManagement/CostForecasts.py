"""Procurement 6.15 Budget & Cost Management — CostForecast.

**What it is.** The NavERP.md "Forecasting & Projection" bullet, built honestly: a saved,
FROZEN arithmetic projection of future procurement spend, computed once from open purchase
orders and recognised-invoice history and stamped onto the row at create time. There is no model,
no training set and no probability anywhere in this module, and no label in it may claim one —
the same honesty discipline 6.14's classification rules carry.

**Snapshot discipline.** The three amount columns are ``editable=False`` and are stamped ONLY by
``costforecast_create`` (through :func:`compute_forecast_amounts`) or by the seeder going through
the same function. There is deliberately NO edit page — a hand-amended forecast would be a figure
with no computation behind it, the exact exemption ``SpendReportSnapshot`` documents. The detail
page renders the row as stored and recomputes nothing.

**Derived inputs, never stored inputs.** :func:`compute_forecast_amounts` aggregates from the scm
document spine and 6.13's recognised invoices on every call; nothing is cached anywhere else.

**Import discipline.** The sibling helpers it reads (``open_po_commitment_lines`` from this
sub-package, ``invoiced_line_window`` / ``money`` from 6.14) are imported INSIDE the function:
this sub-package is not wired into ``models/__init__.py`` until the Integrate phase, and a
module-level sibling import that runs while ``apps.procurement.models`` is still initialising is
exactly how an import cycle gets shipped.
"""
from datetime import timedelta

from apps.procurement.models._base import *  # noqa: F401,F403


#: How the projection is arrived at. Arithmetic only — see the module docstring.
METHOD_CHOICES = [
    ("open_pos", "Open POs"),
    ("run_rate", "Run rate (historical)"),
    ("blended", "Blended"),
]

#: Documented approximation: a month is 30 days. The horizon is a projection window, not an
#: accounting period — one or two days of edge never change a forecast's meaning, and pulling a
#: calendar library in for it would be more machinery than the figure warrants.
_DAYS_PER_MONTH = 30


def compute_forecast_amounts(tenant, budget, method, horizon_months, as_of):
    """``{"committed": Decimal, "historical": Decimal, "forecast": Decimal}`` — PURE arithmetic.

    * ``committed`` — the live open-PO commitment total (6.15's
      :data:`~apps.procurement.models.BudgetCostManagement.BudgetMappings.OPEN_COMMITMENT_PO_STATUSES`).
    * ``historical`` — recognised supplier-invoice lines over ``[as_of - horizon, as_of)``.
    * ``forecast`` — open_pos: the commitment total stands as the projection; run_rate: the
      historical window stands; blended: the mean of the two.

    When a budget is given both populations are scoped to the GL accounts its budget lines fund —
    and a budget with NO lines forecasts zeros rather than the whole workspace, because money the
    budget does not fund is not this forecast's business. A ``None`` budget forecasts the whole
    workspace.

    Unit-testable by design: every input is an argument, every output is in the return dict, and
    the create view stamps exactly these three values.
    """
    from apps.procurement.models.BudgetCostManagement.BudgetMappings import (
        open_po_commitment_lines)
    from apps.procurement.models.SpendAnalyticsReporting.SpendClassificationRules import (
        invoiced_line_window, money)

    zeros = {"committed": ZERO, "historical": ZERO, "forecast": ZERO}
    if tenant is None or method not in dict(METHOD_CHOICES) or as_of is None:
        return zeros
    horizon_months = int(horizon_months or 0)
    if horizon_months <= 0:
        return zeros

    gl_ids = None
    if budget is not None:
        gl_ids = {gl_id for gl_id in
                  budget.lines.values_list("gl_account_id", flat=True) if gl_id}
        if not gl_ids:
            return zeros

    po_lines = open_po_commitment_lines(tenant)
    start = as_of - timedelta(days=_DAYS_PER_MONTH * horizon_months)
    inv_lines = invoiced_line_window(tenant, start, as_of)
    if gl_ids:
        po_lines = po_lines.filter(gl_account_id__in=gl_ids)
        inv_lines = inv_lines.filter(gl_account_id__in=gl_ids)

    committed = money(po_lines.aggregate(s=Sum("line_total"))["s"] or ZERO)
    historical = money(inv_lines.aggregate(s=Sum("line_total"))["s"] or ZERO)

    if method == "open_pos":
        forecast = committed
    elif method == "run_rate":
        forecast = historical
    else:  # blended
        forecast = money((committed + historical) / 2)
    return {"committed": committed, "historical": historical, "forecast": forecast}


class CostForecast(TenantNumbered):
    """One frozen projection of future procurement spend [FCST-]."""

    NUMBER_PREFIX = "FCST"

    METHOD_CHOICES = METHOD_CHOICES

    #: theme.css colour-named badges only (L33).
    METHOD_CSS = {"open_pos": "badge-info", "run_rate": "badge-slate", "blended": "badge-muted"}

    name = models.CharField(
        max_length=120,
        help_text="What this forecast is for, e.g. 'Q3 ops spend projection'")
    budget = models.ForeignKey(
        "accounting.Budget", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="procurement_cost_forecasts",
        help_text="Budget whose GL accounts scope this forecast (blank = whole workspace)")
    method = models.CharField(
        max_length=10, choices=METHOD_CHOICES, default="blended",
        help_text="How the projection is arrived at — arithmetic only, never a model")
    horizon_months = models.PositiveSmallIntegerField(
        default=3, validators=[MinValueValidator(1), MaxValueValidator(24)],
        help_text="Months ahead to project (and the history window for run rate), 1-24")
    as_of = models.DateField(
        default=timezone.localdate,
        help_text="The date the figures are computed as at")
    currency = models.ForeignKey(
        "accounting.Currency", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="procurement_cost_forecasts",
        help_text="Display currency label — sums are at face value, nothing is converted")

    # Stamped at create time by compute_forecast_amounts and never hand-editable afterwards.
    committed_amount = models.DecimalField(
        max_digits=18, decimal_places=2, default=0, editable=False,
        help_text="Open purchase-order commitment at the as-of date")
    historical_amount = models.DecimalField(
        max_digits=18, decimal_places=2, default=0, editable=False,
        help_text="Recognised invoices over the horizon window before the as-of date")
    forecast_amount = models.DecimalField(
        max_digits=18, decimal_places=2, default=0, editable=False,
        help_text="The projection itself, per the chosen method")

    assumptions = models.TextField(
        blank=True,
        help_text="What the reader should know: scope, exclusions, why this method")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="procurement_cost_forecasts", editable=False)

    class Meta:
        ordering = ["-as_of", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "as_of"], name="prc_fcst_tnt_asof_idx"),
            models.Index(fields=["tenant", "budget"], name="prc_fcst_tnt_budget_idx"),
        ]
        verbose_name = "Cost Forecast"
        verbose_name_plural = "Cost Forecasts"

    def __str__(self):
        return f"{self.number or 'FCST'} · {self.name}"

    @property
    def method_css(self):
        return self.METHOD_CSS.get(self.method, "badge-slate")

    def clean(self):
        super().clean()
        errors = {}
        tenant_id = getattr(self, "tenant_id", None)

        # Cross-tenant backstop on the budget FK (currency is a global table — no tenant column).
        if tenant_id and self.budget_id:
            if getattr(self.budget, "tenant_id", None) != tenant_id:
                errors["budget"] = "That record belongs to another workspace."

        if errors:
            raise ValidationError(errors)
