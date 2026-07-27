"""SCM 4.8 Manufacturing — WorkCenter views (the capacity + rate master)."""
from datetime import timedelta

from apps.scm.views._common import *  # noqa: F401,F403
from apps.scm.views._helpers import _location_qs, _need_tenant
from apps.scm.models import WorkCenter, WorkOrder
from apps.scm.forms import WorkCenterForm

ZERO = Decimal("0")

#: Window the detail page's load + OEE chips are computed over.
_CHIP_DAYS = 30


@login_required
def workcenter_list(request):
    qs = (WorkCenter.objects.filter(tenant=request.tenant)
          .select_related("location", "org_unit", "supervisor")
          # Two EXISTS subqueries per page, not two queries per row — the list gates its Delete
          # button on the same rule workcenter_delete enforces.
          .annotate(wo_count=Count("work_orders", distinct=True),
                    log_count=Count("time_logs", distinct=True))
          .order_by("code"))
    return crud_list(
        request, qs, "scm/manufacturing/workcenter/list.html",
        search_fields=["number", "code", "name", "notes", "location__code", "supervisor__name"],
        filters=[("center_type", "center_type", False), ("is_active", "is_active", False),
                 ("location", "location_id", True)],
        extra_context={
            "type_choices": WorkCenter.CENTER_TYPE_CHOICES,
            "locations": _location_qs(request.tenant),
        },
    )


@login_required
def workcenter_create(request):
    if _need_tenant(request):
        return redirect("scm:workcenter_list")
    return crud_create(
        request, form_class=WorkCenterForm, template="scm/manufacturing/workcenter/form.html",
        success_url="scm:workcenter_list")


@login_required
def workcenter_edit(request, pk):
    return crud_edit(
        request, model=WorkCenter, pk=pk, form_class=WorkCenterForm,
        template="scm/manufacturing/workcenter/form.html", success_url="scm:workcenter_list")


@login_required
def workcenter_detail(request, pk):
    obj = get_object_or_404(
        WorkCenter.objects.select_related("location", "org_unit", "supervisor"),
        pk=pk, tenant=request.tenant)
    until = timezone.now()
    since = until - timedelta(days=_CHIP_DAYS)
    open_orders = (WorkOrder.objects
                   .filter(tenant=request.tenant, work_center=obj,
                           status__in=("planned", "released", "in_progress"))
                   .select_related("item")
                   # By date only. `-priority` would sort the CharField alphabetically
                   # (urgent, normal, low, high), which reads like a ranking but isn't one.
                   .order_by("planned_start", "-id")[:20])
    return render(request, "scm/manufacturing/workcenter/detail.html", {
        "obj": obj,
        "open_orders": open_orders,
        # workcenter_delete refuses a centre with either kind of history, so the template hides the
        # button rather than offering an action that always bounces with an error.
        "can_delete": not (obj.work_orders.exists() or obj.time_logs.exists()),
        "window_days": _CHIP_DAYS,
        "scheduled_hours": obj.scheduled_hours(since, until),
        "actual_hours": obj.actual_hours(since, until),
        "capacity_hours": obj.effective_capacity_hours(_CHIP_DAYS),
        "utilization_pct": obj.utilization_pct(since, until, days=_CHIP_DAYS),
        "oee": obj.oee_chip(since, until),
    })


@login_required
@require_POST
def workcenter_delete(request, pk):
    obj = get_object_or_404(WorkCenter, pk=pk, tenant=request.tenant)
    # WorkOrder.work_center and ProductionTimeLog.work_center are both PROTECT, so a centre with
    # history would raise ProtectedError inside crud_delete — a 500, not a message. Refuse it here
    # with somewhere to look, the same way item_delete does for stock movements.
    if obj.work_orders.exists():
        messages.error(request, "This work centre has work orders and cannot be deleted — "
                                "deactivate it instead.")
        return redirect("scm:workcenter_detail", pk=pk)
    if obj.time_logs.exists():
        messages.error(request, "This work centre has production time logs and cannot be deleted — "
                                "deactivate it instead.")
        return redirect("scm:workcenter_detail", pk=pk)
    return crud_delete(request, model=WorkCenter, pk=pk, success_url="scm:workcenter_list")
