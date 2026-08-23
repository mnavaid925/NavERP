"""Inventory 5.13 Inventory Forecasting & Planning — StockLevelPlan views.

CRUD plus the two lifecycle verbs (activate / archive). Activation supersedes the
previous active row by archiving it; refusals are the model's ValidationErrors
surfaced as flash messages.
"""
from django.core.exceptions import ValidationError

from apps.inventory.views._common import *  # noqa: F401,F403
from apps.inventory.forms import StockLevelPlanForm
from apps.inventory.models import StockLevelPlan


def _scoped(tenant):
    return (StockLevelPlan.objects.filter(tenant=tenant)
            .select_related("item", "location", "seasonal_profile"))


@login_required
def stocklevelplan_list(request):
    qs = _scoped(request.tenant)
    return crud_list(
        request, qs, "inventory/planning/stocklevelplan/list.html",
        search_fields=["number", "item__sku", "item__name", "notes"],
        filters=[("status", "status", False), ("item", "item_id", True)],
        extra_context={
            "status_choices": StockLevelPlan.STATUS_CHOICES,
            "active_count": StockLevelPlan.objects.filter(
                tenant=request.tenant, status="active").count(),
        },
    )


@login_required
def stocklevelplan_detail(request, pk):
    obj = get_object_or_404(_scoped(request.tenant), pk=pk)
    flag, css = obj.plan_flags
    return render(request, "inventory/planning/stocklevelplan/detail.html", {
        "obj": obj,
        "recommended": obj.recommended_qty(),
        "flag": flag,
        "css": css,
    })


@login_required
def stocklevelplan_create(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = StockLevelPlanForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, "Created successfully.")
            return redirect("inventory:stocklevelplan_list")
    else:
        form = StockLevelPlanForm(tenant=request.tenant)
    return render(request, "inventory/planning/stocklevelplan/form.html",
                  {"form": form, "is_edit": False})


@login_required
def stocklevelplan_edit(request, pk):
    obj = get_object_or_404(StockLevelPlan, pk=pk, tenant=request.tenant)
    if not obj.is_editable:
        messages.error(request, f"{obj.number} is {obj.get_status_display().lower()} "
                                "and cannot be edited.")
        return redirect("inventory:stocklevelplan_detail", pk=obj.pk)
    return crud_edit(
        request, model=StockLevelPlan, pk=pk, form_class=StockLevelPlanForm,
        template="inventory/planning/stocklevelplan/form.html",
        success_url="inventory:stocklevelplan_list",
    )


@login_required
@require_POST
def stocklevelplan_delete(request, pk):
    obj = get_object_or_404(StockLevelPlan, pk=pk, tenant=request.tenant)
    if not obj.is_editable:
        messages.error(request, f"{obj.number} is {obj.get_status_display().lower()} "
                                "— archive it instead of deleting its history.")
        return redirect("inventory:stocklevelplan_detail", pk=obj.pk)
    return crud_delete(request, model=StockLevelPlan, pk=pk,
                       success_url="inventory:stocklevelplan_list")


@login_required
@require_POST
def stocklevelplan_activate(request, pk):
    return _run_action(request, pk, "activate")


@login_required
@require_POST
def stocklevelplan_archive(request, pk):
    return _run_action(request, pk, "archive")


_ACTION_MESSAGES = {
    "activate": "activated — it is now the plan buyers see.",
    "archive": "archived.",
}


def _run_action(request, pk, action):
    obj = get_object_or_404(StockLevelPlan, pk=pk, tenant=request.tenant)
    try:
        getattr(obj, action)(request.user)
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    else:
        messages.success(request, f"{obj.number} {_ACTION_MESSAGES[action]}")
    return redirect("inventory:stocklevelplan_detail", pk=obj.pk)
