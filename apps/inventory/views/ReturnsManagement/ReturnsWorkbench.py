"""Inventory 5.10 Returns Management — Warehouse Returns Workbench (Computed Board).

Real-time operational dashboard for warehouse intake, inspection staging, and guided
disposition routing across all open customer return requests and bench inventory.
"""
from django.db.models import Count, Q

from apps.core.crud import paginate
from apps.inventory.models import (
    DispositionRoutingRule,
    ReturnInspection,
    resolve_disposition_routing,
)
from apps.inventory.views._common import *  # noqa: F401,F403
from apps.scm.models import ReturnAuthorization, ReturnDisposition, ReturnLine


@login_required
def returns_workbench(request):
    """Warehouse operations board for receiving, inspecting and routing returns."""
    tenant = request.tenant

    # Preload all active disposition routing rules once to avoid N+1 queries during resolution
    rules = list(
        DispositionRoutingRule.objects.filter(tenant=tenant, is_active=True)
        .select_related("item", "category", "destination_location")
        .order_by("priority", "id")
    )

    # 1. Open Return Authorizations requiring warehouse action
    rma_qs = (
        ReturnAuthorization.objects.filter(
            tenant=tenant,
            status__in=["approved", "awaiting_receipt", "partially_received", "received"],
        )
        .select_related("customer")
        .prefetch_related("lines__item", "inventory_inspections")
        .order_by("-id")
    )

    # Search filter
    q = request.GET.get("q", "").strip()
    if q:
        rma_qs = rma_qs.filter(
            Q(number__icontains=q)
            | Q(customer__name__icontains=q)
            | Q(lines__item__sku__icontains=q)
            | Q(lines__item__name__icontains=q)
        ).distinct()

    # Build actionable return items list
    bench_items = []
    # Query pending dispositions on bench
    pending_disps = list(
        ReturnDisposition.objects.filter(tenant=tenant, disposition="received_pending")
        .select_related(
            "return_line",
            "return_line__return_authorization",
            "return_line__return_authorization__customer",
            "return_line__item",
            "return_line__item__category",
            "location",
            "lot_serial",
        )
        .order_by("-received_on", "-id")
    )

    # One query for the whole bench, not one .exists() per pending disposition
    inspected_disp_ids = set(
        ReturnInspection.objects.filter(
            tenant=tenant,
            return_disposition_id__in=[disp.id for disp in pending_disps],
        ).values_list("return_disposition_id", flat=True)
    )

    # Display strings for the dict-rows are computed HERE, in the view — the template's
    # {% else %} branches print these instead of raw codes like "received_pending".
    disposition_labels = dict(ReturnDisposition.DISPOSITION_CHOICES)
    grade_labels = dict(ReturnDisposition.GRADE_CHOICES)

    # Attach live inspection and routing suggestions to bench items
    for disp in pending_disps:
        item = disp.return_line.item if disp.return_line else None
        rule, suggested_disp, dest_loc, reason = resolve_disposition_routing(
            item, condition_grade=disp.condition_grade, rules=rules, tenant=tenant
        )
        suggested_value = suggested_disp or disp.disposition

        bench_items.append({
            "disposition": disp,
            "rma": disp.return_line.return_authorization if disp.return_line else None,
            "line": disp.return_line,
            "item": item,
            "quantity": disp.quantity,
            "condition_grade": disp.condition_grade,
            "condition_grade_display": grade_labels.get(disp.condition_grade, disp.condition_grade),
            "suggested_disposition": suggested_value,
            "suggested_disposition_display": disposition_labels.get(suggested_value, suggested_value),
            "destination_location": dest_loc,
            "routing_reason": reason,
            "has_inspection": disp.id in inspected_disp_ids,
        })

    # Stats strip — grouped counts, not repeated COUNT(*) scans (house pattern)
    open_statuses = ["approved", "awaiting_receipt", "partially_received", "received"]
    rma_status_counts = {
        row["status"]: row["n"]
        for row in ReturnAuthorization.objects.filter(tenant=tenant)
        .filter(status__in=open_statuses)
        .values("status")
        .annotate(n=Count("id"))
    }
    inspection_status_counts = {
        row["status"]: row["n"]
        for row in ReturnInspection.objects.filter(tenant=tenant)
        .values("status")
        .annotate(n=Count("id"))
    }

    stats = {
        "active_rmas": sum(rma_status_counts.values()),
        "awaiting_bench": len(pending_disps),
        "inspections_passed": inspection_status_counts.get("passed", 0),
        "quarantined": inspection_status_counts.get("quarantined", 0),
    }

    # Paginate open RMAs
    page_obj = paginate(request, rma_qs, per_page=15)

    return render(
        request,
        "inventory/returns/workbench.html",
        {
            "page_obj": page_obj,
            "rmas": page_obj.object_list,
            "bench_items": bench_items[:20],
            "stats": stats,
            "q": q,
            "is_admin": bool(request.user.is_superuser or getattr(request.user, "is_tenant_admin", False)),
        },
    )
