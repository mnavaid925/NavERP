"""Inventory 5.14 Barcode & RFID Integration — RfidTag CRUD, lifecycle and bulk-read views."""
from django.db.models import Count

from apps.core.crud import as_db_int
from apps.core.decorators import tenant_admin_required
from apps.inventory.forms.BarcodeRfidIntegration.RfidTags import RfidTagForm
from apps.inventory.models.BarcodeRfidIntegration.RfidTags import RfidTag
from apps.inventory.views._common import *  # noqa: F401,F403
from apps.scm.models import Location


@login_required
def rfidtag_list(request):
    """List RFID tags with search, status/kind filtering and a KPI strip."""
    qs = (
        RfidTag.objects.filter(tenant=request.tenant)
        .select_related("item", "location", "lot_serial", "last_seen_location")
    )

    # Search & filters — junk GET values (status=zzz) fall back to "" instead of echoing back
    # into context and rendering a silently empty register.
    valid_statuses = dict(RfidTag.STATUS_CHOICES)
    valid_kinds = dict(RfidTag.KIND_CHOICES)

    status = request.GET.get("status", "").strip()
    if status and status not in valid_statuses:
        status = ""
    if status:
        qs = qs.filter(status=status)

    kind = request.GET.get("kind", "").strip()
    if kind and kind not in valid_kinds:
        kind = ""
    if kind:
        qs = qs.filter(kind=kind)

    # KPIs across the tenant's full tag register — one grouped query, not four COUNTs
    status_counts = {
        row["status"]: row["n"]
        for row in RfidTag.objects.filter(tenant=request.tenant)
        .values("status")
        .annotate(n=Count("id"))
    }
    stats = {
        "total": sum(status_counts.values()),
        "active": status_counts.get("active", 0),
        "unassigned": status_counts.get("unassigned", 0),
        "retired": status_counts.get("retired", 0),
        "lost": status_counts.get("lost", 0),
    }

    return crud_list(
        request,
        qs,
        "inventory/barcode/rfidtag/list.html",
        search_fields=["epc", "target_ref", "pallet_ref", "item__sku", "location__code"],
        filters=(),
        extra_context={
            "stats": stats,
            "status_choices": RfidTag.STATUS_CHOICES,
            "status": status,
            "kind_choices": RfidTag.KIND_CHOICES,
            "kind": kind,
            "is_admin": bool(request.user.is_superuser or getattr(request.user, "is_tenant_admin", False)),
        },
    )


@login_required
def rfidtag_detail(request, pk):
    """View details of an RFID tag."""
    return crud_detail(
        request,
        model=RfidTag,
        pk=pk,
        template="inventory/barcode/rfidtag/detail.html",
        select_related=("item", "location", "lot_serial", "last_seen_location"),
        extra_context={
            "is_admin": bool(request.user.is_superuser or getattr(request.user, "is_tenant_admin", False)),
        },
    )


@tenant_admin_required
def rfidtag_create(request):
    """Register a new RFID tag."""
    return crud_create(
        request,
        form_class=RfidTagForm,
        template="inventory/barcode/rfidtag/form.html",
        success_url="inventory:rfidtag_list",
    )


@tenant_admin_required
def rfidtag_edit(request, pk):
    """Edit an existing RFID tag."""
    return crud_edit(
        request,
        model=RfidTag,
        pk=pk,
        form_class=RfidTagForm,
        template="inventory/barcode/rfidtag/form.html",
        success_url="inventory:rfidtag_list",
    )


@tenant_admin_required
@require_POST
def rfidtag_delete(request, pk):
    """Delete an RFID tag record."""
    return crud_delete(
        request,
        model=RfidTag,
        pk=pk,
        success_url="inventory:rfidtag_list",
    )


@tenant_admin_required
@require_POST
def rfidtag_activate(request, pk):
    """Activate an unassigned tag that has a target attached."""
    return _lifecycle_action(request, pk, "activate")


@tenant_admin_required
@require_POST
def rfidtag_retire(request, pk):
    """Retire an active or unassigned tag from circulation."""
    return _lifecycle_action(request, pk, "retire")


@tenant_admin_required
@require_POST
def rfidtag_mark_lost(request, pk):
    """Mark an active tag as lost in the field."""
    return _lifecycle_action(request, pk, "mark_lost")


def _lifecycle_action(request, pk, verb):
    """Shared body of the activate/retire/mark-lost POST actions."""
    tag = get_object_or_404(RfidTag, pk=pk, tenant=request.tenant)
    try:
        getattr(tag, verb)()
        tag.save(update_fields=["status", "updated_at"])
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
        return redirect("inventory:rfidtag_detail", pk=tag.pk)
    write_audit_log(request.user, tag, "update", {"action": verb})
    messages.success(request, f"Tag {tag.epc}: {verb.replace('_', ' ')} done.")
    return redirect("inventory:rfidtag_detail", pk=tag.pk)


@tenant_admin_required
def rfidtag_bulkread(request):
    """Reader-sweep console — paste EPCs, stamp last-seen on every matching tag."""
    locations = Location.objects.filter(tenant=request.tenant, is_active=True).order_by("code")

    if request.method == "POST":
        epcs = [e.strip().upper() for e in request.POST.get("epcs", "").splitlines() if e.strip()]
        truncated = False
        if len(epcs) > 500:
            epcs = epcs[:500]
            truncated = True

        loc_id = as_db_int(request.POST.get("location"))
        location = None
        if loc_id:
            # A foreign/bogus id degrades to "no read point" rather than 500ing.
            location = Location.objects.filter(tenant=request.tenant, pk=loc_id).first()

        result = RfidTag.bulk_read(request.tenant, epcs, location=location)

        # One summary audit row for the whole sweep (obj=None is supported by write_audit_log;
        # the explicit tenant kwarg keeps the row inside this workspace).
        write_audit_log(
            request.user,
            None,
            "update",
            {"action": "bulk_read", "matched": result["matched"], "unknown": len(result["unknown"])},
            tenant=request.tenant,
        )
        if truncated:
            messages.warning(request, "Input capped at the first 500 EPCs; extra lines ignored.")
        messages.success(request, f"{result['matched']} tags seen · {len(result['unknown'])} unknown")
        return redirect("inventory:rfidtag_bulkread")

    return render(
        request,
        "inventory/barcode/rfidtag/bulkread.html",
        {"locations": locations},
    )
