"""SCM 4.8 Manufacturing — WorkCenter views (the capacity + rate master)."""
from datetime import timedelta

from django.db.models import Exists, OuterRef

from apps.scm.views._common import *  # noqa: F401,F403
from apps.scm.views._helpers import _location_qs, _need_tenant
from apps.scm.models import ProductionTimeLog, WorkCenter, WorkOrder
from apps.scm.forms import WorkCenterForm

ZERO = Decimal("0")

#: Window the detail page's load + OEE chips are computed over.
_CHIP_DAYS = 30


@login_required
def workcenter_list(request):
    qs = (WorkCenter.objects.filter(tenant=request.tenant)
          .select_related("location", "org_unit", "supervisor")
          # Exists(), NOT Count(): the template only ever asks "any?", and two Counts over two
          # reverse relations LEFT JOIN both children into one cartesian product per centre — a
          # centre with 500 runs and 5,000 logs materialises 2.5M intermediate rows to render 15.
          # It also forces the paginator's COUNT(*) into a subquery over the grouped result.
          .annotate(
              has_work_orders=Exists(
                  WorkOrder.objects.filter(work_center=OuterRef("pk"))),
              has_time_logs=Exists(
                  ProductionTimeLog.objects.filter(work_center=OuterRef("pk"))))
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
    # ONE aggregate over the time logs, reused three ways. actual_hours() and utilization_pct()
    # each used to re-run the identical Sum("duration_minutes") that oee_chip already computes —
    # three scans of the module's fastest-growing table to fill three chips off the same rows.
    oee = obj.oee_chip(since, until)
    actual_hours = oee["booked_hours"]
    return render(request, "scm/manufacturing/workcenter/detail.html", {
        "obj": obj,
        "open_orders": open_orders,
        # workcenter_delete refuses a centre with either kind of history, so the template hides the
        # button rather than offering an action that always bounces with an error.
        "can_delete": not (obj.work_orders.exists() or obj.time_logs.exists()),
        "window_days": _CHIP_DAYS,
        "scheduled_hours": obj.scheduled_hours(since, until),
        "actual_hours": actual_hours,
        "capacity_hours": obj.effective_capacity_hours(_CHIP_DAYS),
        "utilization_pct": obj.utilization_pct(since, until, days=_CHIP_DAYS,
                                               actual=actual_hours),
        "oee": oee,
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
