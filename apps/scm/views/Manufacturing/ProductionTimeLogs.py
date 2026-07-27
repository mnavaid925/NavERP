"""SCM 4.8 Manufacturing — ProductionTimeLog views (shop-floor control).

Entries are writable only while their run is OPEN. Once the work order is completed, closed or
cancelled the log is frozen — a softened version of the append-only rule StockMove enforces, kept
loose enough while the run is live to satisfy the CRUD completeness rule.
"""
from apps.scm.views._common import *  # noqa: F401,F403
from apps.scm.views._helpers import _need_tenant
from apps.scm.models import ProductionTimeLog, WorkCenter, WorkOrder
from apps.scm.forms import ProductionTimeLogForm

ZERO = Decimal("0")


def _frozen(request, obj):
    """True (and messages) when the log's run has moved past the editable window."""
    if obj.work_order.status not in WorkOrder.OPEN_STATUSES:
        messages.error(request, f"Work order {obj.work_order.number} is "
                                f"{obj.work_order.get_status_display().lower()} — its production "
                                "log is frozen.")
        return True
    return False


@login_required
def productiontimelog_list(request):
    qs = (ProductionTimeLog.objects.filter(tenant=request.tenant)
          .select_related("work_order", "work_order__item", "work_center", "operator"))
    return crud_list(
        request, qs, "scm/manufacturing/productiontimelog/list.html",
        search_fields=["number", "operation", "notes", "work_order__number",
                       "work_center__code", "operator__name"],
        filters=[("entry_type", "entry_type", False),
                 ("downtime_reason", "downtime_reason", False),
                 ("work_order", "work_order_id", True),
                 ("work_center", "work_center_id", True)],
        extra_context={
            "type_choices": ProductionTimeLog.ENTRY_TYPE_CHOICES,
            "reason_choices": ProductionTimeLog.DOWNTIME_REASON_CHOICES,
            "work_centers": WorkCenter.objects.filter(tenant=request.tenant, is_active=True),
            # Every run, not just open ones. This populates the FILTER dropdown, and a closed run's
            # logs are exactly the rows this page is careful to still show (badged "Frozen") — an
            # open-only list left them filterable by URL but unreachable from the select, and made
            # the deep-link from a finished work order silently reset to "All work orders".
            # The FORM's work-order choices stay open-only; that restriction belongs there.
            "work_orders": WorkOrder.objects.filter(
                tenant=request.tenant).select_related("item"),
        },
    )


@login_required
def productiontimelog_create(request):
    if _need_tenant(request):
        return redirect("scm:productiontimelog_list")
    return crud_create(
        request, form_class=ProductionTimeLogForm,
        template="scm/manufacturing/productiontimelog/form.html",
        success_url="scm:productiontimelog_list")


@login_required
def productiontimelog_edit(request, pk):
    obj = get_object_or_404(ProductionTimeLog.objects.select_related("work_order"),
                            pk=pk, tenant=request.tenant)
    if _frozen(request, obj):
        return redirect("scm:productiontimelog_detail", pk=pk)
    return crud_edit(
        request, model=ProductionTimeLog, pk=pk, form_class=ProductionTimeLogForm,
        template="scm/manufacturing/productiontimelog/form.html",
        success_url="scm:productiontimelog_list")


@login_required
def productiontimelog_detail(request, pk):
    obj = get_object_or_404(
        ProductionTimeLog.objects.select_related("work_order", "work_order__item", "work_center",
                                                 "operator"),
        pk=pk, tenant=request.tenant)
    return render(request, "scm/manufacturing/productiontimelog/detail.html", {
        "obj": obj,
        "is_frozen": obj.work_order.status not in WorkOrder.OPEN_STATUSES,
    })


@login_required
@require_POST
def productiontimelog_delete(request, pk):
    obj = get_object_or_404(ProductionTimeLog.objects.select_related("work_order"),
                            pk=pk, tenant=request.tenant)
    if _frozen(request, obj):
        return redirect("scm:productiontimelog_detail", pk=pk)
    return crud_delete(request, model=ProductionTimeLog, pk=pk,
                       success_url="scm:productiontimelog_list")
