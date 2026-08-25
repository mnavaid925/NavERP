"""Inventory 5.16 Alerts & Notifications — alert inbox views (list/detail/triage/detect)."""
from django.core.exceptions import ValidationError
from django.db.models import Count

from apps.core.decorators import tenant_admin_required
from apps.inventory.models.AlertsNotifications.InventoryAlerts import InventoryAlert
from apps.inventory.views._common import *  # noqa: F401,F403


@login_required
def alert_list(request):
    """The alert inbox — every raised condition with type/severity/status lenses.

    The sidebar's 5.16 bullets deep-link here with ``?type=…`` (one inbox, four lenses),
    the same board-lens pattern as 5.7's transfer board.
    """
    qs = (InventoryAlert.objects.filter(tenant=request.tenant)
          .select_related("item", "location", "lot_serial", "purchase_order", "shipment"))

    # Junk GET values fall back to "" instead of rendering a silently empty inbox.
    valid_types = dict(InventoryAlert.TYPE_CHOICES)
    valid_severities = dict(InventoryAlert.SEVERITY_CHOICES)
    valid_statuses = dict(InventoryAlert.STATUS_CHOICES)

    alert_type = request.GET.get("type", "").strip()
    if alert_type and alert_type not in valid_types:
        alert_type = ""
    if alert_type:
        qs = qs.filter(alert_type=alert_type)

    severity = request.GET.get("severity", "").strip()
    if severity and severity not in valid_severities:
        severity = ""
    if severity:
        qs = qs.filter(severity=severity)

    status = request.GET.get("status", "").strip()
    if status and status not in valid_statuses:
        status = ""
    if status:
        qs = qs.filter(status=status)

    # KPI strip across the whole register — one grouped query, not four COUNTs.
    counts = {
        row["status"]: row["n"]
        for row in InventoryAlert.objects.filter(tenant=request.tenant)
        .values("status").annotate(n=Count("id"))
    }
    open_critical = (InventoryAlert.objects.filter(tenant=request.tenant, status="open",
                                                   severity="critical").count())
    stats = {
        "open": counts.get("open", 0),
        "acknowledged": counts.get("acknowledged", 0),
        "resolved": counts.get("resolved", 0),
        "open_critical": open_critical,
    }

    return crud_list(
        request,
        qs,
        "inventory/alerts/inventoryalert/list.html",
        search_fields=["number", "title", "message", "item__sku", "location__code",
                       "lot_serial__number", "purchase_order__number", "shipment__number"],
        filters=(),
        extra_context={
            "stats": stats,
            "type_choices": InventoryAlert.TYPE_CHOICES,
            "severity_choices": InventoryAlert.SEVERITY_CHOICES,
            "status_choices": InventoryAlert.STATUS_CHOICES,
            "type": alert_type,
            "severity": severity,
            "status": status,
            "is_admin": bool(request.user.is_superuser or getattr(request.user, "is_tenant_admin", False)),
        },
    )


@login_required
def alert_detail(request, pk):
    """One alert: its snapshot context plus the delivery log it raised."""
    return crud_detail(
        request,
        model=InventoryAlert,
        pk=pk,
        template="inventory/alerts/inventoryalert/detail.html",
        select_related=("rule", "item", "location", "lot_serial", "purchase_order", "shipment",
                        "acknowledged_by", "resolved_by"),
        extra_context={},
    )


@login_required
@require_POST
def alert_acknowledge(request, pk):
    """Claim an open alert — operational triage, no admin gate (procurement precedent)."""
    alert = get_object_or_404(InventoryAlert, pk=pk, tenant=request.tenant)
    try:
        alert.acknowledge(request.user)
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
        return redirect("inventory:alert_detail", pk=alert.pk)
    write_audit_log(request.user, alert, "update", {"action": "acknowledge"})
    messages.success(request, f"{alert.number} acknowledged.")
    return redirect("inventory:alert_detail", pk=alert.pk)


@login_required
@require_POST
def alert_resolve(request, pk):
    """Close an alert with an optional note; re-raising restarts after the rule's cooldown."""
    alert = get_object_or_404(InventoryAlert, pk=pk, tenant=request.tenant)
    try:
        alert.resolve(request.user, note=request.POST.get("resolution_note", "").strip())
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
        return redirect("inventory:alert_detail", pk=alert.pk)
    write_audit_log(request.user, alert, "update",
                    {"action": "resolve", "resolution_note": alert.resolution_note})
    messages.success(request, f"{alert.number} resolved.")
    return redirect("inventory:alert_detail", pk=alert.pk)


@tenant_admin_required
@require_POST
def alert_run_detection(request):
    """Evaluate every active rule now — deterministic, explainable, never AI."""
    summary = InventoryAlert.run_detection(request.tenant)
    write_audit_log(
        request.user, None, "create",
        {"action": "run_detection", "raised": len(summary["raised"]),
         "skipped_open": summary["skipped_open"],
         "skipped_cooldown": summary["skipped_cooldown"],
         "deliveries": summary["deliveries"]},
        tenant=request.tenant,
    )
    parts = [f"{len(summary['raised'])} raised",
             f"{summary['skipped_open']} already open",
             f"{summary['skipped_cooldown']} cooling down",
             f"{summary['deliveries']} deliveries queued"]
    if len(summary["raised"]) == 0 and not summary["rules_evaluated"]:
        messages.warning(request, "No active rules to evaluate — create one first.")
    else:
        messages.success(request, "Detection run: " + ", ".join(parts) + ".")
    return redirect("inventory:alert_list")
