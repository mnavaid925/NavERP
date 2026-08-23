"""Inventory 5.11 Stocktaking & Cycle Counting — Variance Analysis (computed page, NO table).

**Variance Analysis & Adjustments** bullet. The discrepancies already live on the
spine: ``scm.CycleCountTaskLine`` snapshots expected server-side and carries the blind
count; reconciliation posts the reason-coded ``scm.StockAdjustment``. Nothing here
re-states either — this page is the ANALYSIS lens over completed work: per sheet, how
many lines disagreed, by how much, and where the correction landed (the adjustment
link). All tenant-scoped; one page of prefetched sheets pays for its lines once.
"""
from decimal import Decimal

from django.db.models import Prefetch

from apps.core.crud import paginate
from apps.inventory.views._common import *  # noqa: F401,F403
from apps.scm.models import CycleCountTask

ZERO = Decimal("0")

from apps.inventory.forms.StocktakingCycleCounting import VARIANCE_STATUS_CHOICES


@login_required
def variance_report(request):
    qs = (CycleCountTask.objects.filter(tenant=request.tenant)
          .select_related("location", "adjustment"))

    status = request.GET.get("status", "").strip()
    if status == "counted":
        qs = qs.filter(status="counted")
    elif status == "reconciled":
        qs = qs.filter(status="reconciled")
    elif status == "open":
        qs = qs.exclude(status__in=("reconciled", "cancelled"))
    else:
        qs = qs.exclude(status="cancelled")

    q = request.GET.get("q", "").strip()
    if q:
        from django.db.models import Q
        qs = qs.filter(Q(number__icontains=q) | Q(location__code__icontains=q)
                       | Q(notes__icontains=q))

    # Biggest problems first: variance magnitude is a Python-side property of the
    # lines, so order the PAGE by date here and rank within what is rendered —
    # annotating across the reverse relation would fan out on line counts.
    qs = qs.order_by("-scheduled_date", "-id")
    page_obj = paginate(request, qs, per_page=12)
    rows = []
    for task in page_obj.object_list:
        lines = list(task.lines.select_related("item"))
        counted = [ln for ln in lines if ln.counted_quantity is not None]
        variance_qty = sum((ln.variance for ln in counted), ZERO)
        rows.append({
            "task": task,
            "line_count": len(lines),
            "counted_lines": len(counted),
            "variance_lines": sum(1 for ln in counted if ln.has_variance),
            "net_variance": variance_qty,
            "abs_variance": abs(variance_qty),
        })
    rows.sort(key=lambda r: r["abs_variance"], reverse=True)

    return render(request, "inventory/stocktake/variance.html", {
        "object_list": rows,
        "page_obj": page_obj,
        "q": q,
        "status_choices": VARIANCE_STATUS_CHOICES,
        "status": status,
    })
