"""Procurement 6.15 Budget & Cost Management — CostForecast views.

**Forecasting & Projection** bullet. Register, create, detail, delete — and NO edit view, by
design.

Discipline a reviewer will otherwise go looking for:

* **A forecast is a FROZEN projection, stamped at create-time.** The three amount columns are
  ``editable=False`` and are written once, from ``compute_forecast_amounts``, in the create view.
  The detail page renders them AS-STORED and recomputes nothing — the point of freezing a
  projection is that a later month can be held against what was expected THEN. Same exemption as
  ``SpendReportSnapshot``: no form, no edit route.
* **Honesty rule: arithmetic only.** The figure is committed open-PO value and/or a historical
  run-rate extrapolated over a horizon. Nothing here is statistical learning and no label on any
  of these pages may claim "AI", "predictive" or "machine-learned" — a plain moving average is
  not one, and labelling it as such would be the forecast's own undoing.
* **``created_by`` is an authorship stamp** taken from ``request.user`` on create — which is why
  the create path is hand-rolled rather than ``crud_create``: the shared helper has no hook for
  stamping computed amounts plus an author in one save.
* **Every queryset is ``filter(tenant=request.tenant)``** — never ``.all()``.
"""
from django.db.models import Count, Q
from django.urls import reverse

from apps.accounting.models import Budget

from apps.procurement.forms.BudgetCostManagement.CostForecasts import CostForecastForm
# NOT-YET-WIRED entity of this SAME sub-module: import the entity MODULE directly, never
# ``from apps.procurement.models import X`` — the sub-package is not wired until the Integrator
# lands it, and a package-level re-export would be a star-import cycle at URLconf import time.
from apps.procurement.models.BudgetCostManagement.CostForecasts import (
    METHOD_CHOICES, CostForecast, compute_forecast_amounts)
from apps.procurement.views._common import *  # noqa: F401,F403

TEMPLATE_LIST = "procurement/budgetcost/costforecast/list.html"
TEMPLATE_DETAIL = "procurement/budgetcost/costforecast/detail.html"
TEMPLATE_FORM = "procurement/budgetcost/costforecast/form.html"

_ROW_RELATIONS = ("budget", "budget__fiscal_period", "currency", "created_by")

#: Printed on the list, form and detail pages — ONE constant so the three surfaces cannot
#: describe the projection differently (and so the honesty rule is visibly kept).
FORECAST_NOTE = (
    "A forecast is an arithmetic projection frozen at the moment it is saved: committed "
    "open-purchase-order value and/or the recent run rate carried forward over the horizon. "
    "It is not a prediction model and nothing here learns or predicts — it is a number to hold "
    "a later month against."
)


def _need_tenant(request, what):
    """Refuse a tenant-less user (the superuser has ``tenant=None``) before any write.

    Mirrors ``crud_create``'s own guard so the hand-rolled create below cannot mint orphan
    snapshots that no workspace can ever see again.
    """
    if request.tenant is None:
        messages.error(request, f"Select a tenant workspace before you {what}.")
        return redirect("dashboard:home")
    return None


def _forecast_qs(request):
    return CostForecast.objects.filter(tenant=request.tenant).select_related(*_ROW_RELATIONS)


def _budget_dropdowns(request):
    """The budget filter's options — an empty queryset for a tenant-less user."""
    if request.tenant is None:
        return Budget.objects.none()
    return Budget.objects.filter(tenant=request.tenant).select_related("fiscal_period").order_by("-id")


@login_required
def costforecast_list(request):
    """The register of frozen projections, newest as-of date first (model ordering)."""
    base = CostForecast.objects.filter(tenant=request.tenant)
    # ONE conditional aggregate, not three COUNTs: workspace_wide = total - budget_scoped.
    stats = base.aggregate(total=Count("pk"),
                           budget_scoped=Count("pk", filter=Q(budget__isnull=False)))
    stats["workspace_wide"] = stats["total"] - stats["budget_scoped"]
    return crud_list(
        request, _forecast_qs(request), TEMPLATE_LIST,
        search_fields=("number", "name", "assumptions"),
        # method is a plain CHOICES string; budget is an FK and needs the as_db_int guard
        # (crud_list's is_int=True) so a hand-edited query string cannot 500 the page (L11).
        filters=(("method", "method", False),
                 ("budget", "budget_id", True)),
        extra_context={
            "method_choices": METHOD_CHOICES,
            "budgets": _budget_dropdowns(request),
            "stats": stats,
            "forecast_note": FORECAST_NOTE,
        },
    )


@login_required
def costforecast_detail(request, pk):
    """Render the projection exactly as it was frozen. NOTHING here is recomputed."""
    return crud_detail(request, model=CostForecast, pk=pk, template=TEMPLATE_DETAIL,
                       select_related=_ROW_RELATIONS,
                       extra_context={"forecast_note": FORECAST_NOTE})


@login_required
def costforecast_create(request):
    """Freeze one projection: validate the inputs, compute the amounts, stamp and save.

    Hand-rolled rather than ``crud_create``: the three amount columns and ``created_by`` are
    stamped between ``is_valid()`` and the single ``save()``, and the shared helper has no hook
    for that. The amounts come from ``compute_forecast_amounts`` — the same pure function the
    seeder uses, so a saved forecast and a recomputation over the same data agree.
    """
    guard = _need_tenant(request, "create cost forecasts")
    if guard is not None:
        return guard

    if request.method == "POST":
        form = CostForecastForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            amounts = compute_forecast_amounts(
                request.tenant, obj.budget, obj.method, obj.horizon_months, obj.as_of)
            obj.committed_amount = amounts["committed"]
            obj.historical_amount = amounts["historical"]
            obj.forecast_amount = amounts["forecast"]
            obj.created_by = request.user if request.user.is_authenticated else None
            obj.save()
            write_audit_log(request.user, obj, "create", changes={
                "name": obj.name,
                "method": obj.method,
                "horizon_months": obj.horizon_months,
                "as_of": str(obj.as_of),
                "forecast_amount": str(obj.forecast_amount),
            })
            messages.success(request, f"Forecast {obj.number} frozen.")
            return redirect("procurement:costforecast_detail", pk=obj.pk)
    else:
        form = CostForecastForm(tenant=request.tenant)

    return render(request, TEMPLATE_FORM, {
        "form": form,
        "title": "New cost forecast",
        "submit_label": "Freeze forecast",
        "cancel_url": reverse("procurement:costforecast_list"),
        "forecast_note": FORECAST_NOTE,
    })


@login_required
@require_POST
def costforecast_delete(request, pk):
    """Discard a frozen projection. There is no edit — a wrong forecast is deleted and
    re-frozen, never amended in place, so the stored figure always means what it meant."""
    return crud_delete(request, model=CostForecast, pk=pk,
                       success_url="procurement:costforecast_list")
