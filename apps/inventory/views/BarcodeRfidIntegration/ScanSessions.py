"""Inventory 5.14 Barcode & RFID Integration — scan-session views + the handheld console.

Scanning is everyone's job, so unlike sibling 5.4/5.9/5.10 the CRUD reads AND writes stay
open to every signed-in member — only delete is tenant-admin gated. A session freezes at
close(): edit refuses closed sessions with a flash on the detail page (the 403-style refusal
via message is house-acceptable), and the close verb is POST-only because it mutates state.

``scan_console`` is the PRIMARY UX: a GET+POST surface that resolves pasted/held-scanned
strings through the shared ``resolve_code`` spine walk and appends one immutable ScanEvent
per code inside a single transaction, capped at 300 codes per submit BEFORE the loop so a
paste-bomb cannot hold the request open.
"""
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from apps.core.crud import as_db_int, crud_create, crud_delete, crud_edit, crud_list
from apps.core.decorators import tenant_admin_required
from apps.inventory.forms.BarcodeRfidIntegration.ScanSessions import ScanSessionForm
from apps.inventory.models.BarcodeRfidIntegration.ScanSessions import (
    ScanEvent,
    ScanSession,
    resolve_code,
)
from apps.inventory.views._common import *  # noqa: F401,F403

#: Hard cap on codes accepted in ONE console submit — enforced before any DB work.
MAX_CODES_PER_SUBMIT = 300


def _is_admin(user):
    """The one admin flag every 5.14 template receives — same test as the decorator."""
    return bool(user.is_superuser or getattr(user, "is_tenant_admin", False))


@login_required
def scansession_list(request):
    """List scan sessions with search, status filtering and a KPI strip."""
    qs = ScanSession.objects.filter(tenant=request.tenant)

    # Junk GET values (status=zzz) fall back to "" instead of rendering a silently empty list.
    valid_statuses = dict(ScanSession.STATUS_CHOICES)
    status = request.GET.get("status", "").strip()
    if status and status not in valid_statuses:
        status = ""
    if status:
        qs = qs.filter(status=status)

    # KPIs across the tenant's full register — one grouped query, not three COUNTs.
    status_counts = {
        row["status"]: row["n"]
        for row in ScanSession.objects.filter(tenant=request.tenant)
        .values("status")
        .annotate(n=Count("id"))
    }
    stats = {
        "total": sum(status_counts.values()),
        "open": status_counts.get("open", 0),
        "closed": status_counts.get("closed", 0),
    }

    return crud_list(
        request,
        qs,
        "inventory/barcode/scansession/list.html",
        search_fields=["number", "device_label", "notes"],
        filters=(),
        extra_context={
            "status_choices": ScanSession.STATUS_CHOICES,
            "status": status,
            "is_admin": _is_admin(request.user),
            "stats": stats,
        },
    )


@login_required
def scansession_detail(request, pk):
    """View one session plus its most recent capture events (newest first, capped)."""
    session = get_object_or_404(ScanSession.objects.filter(tenant=request.tenant), pk=pk)
    events = session.events.all()[:100]
    return render(
        request,
        "inventory/barcode/scansession/detail.html",
        {
            "obj": session,
            "events": events,
            "is_admin": _is_admin(request.user),
        },
    )


@login_required
def scansession_create(request):
    """Open a new scanning session on a device."""
    return crud_create(
        request,
        form_class=ScanSessionForm,
        template="inventory/barcode/scansession/form.html",
        success_url="inventory:scansession_list",
    )


@login_required
def scansession_edit(request, pk):
    """Edit a session — only while it is still open; closed sessions are read-only."""
    obj = get_object_or_404(ScanSession.objects.filter(tenant=request.tenant), pk=pk)
    if obj.status != "open":
        messages.error(request, f"{obj.number} is closed — closed sessions are read-only.")
        return redirect("inventory:scansession_detail", pk=pk)
    return crud_edit(
        request,
        model=ScanSession,
        pk=pk,
        form_class=ScanSessionForm,
        template="inventory/barcode/scansession/form.html",
        success_url="inventory:scansession_list",
    )


@login_required
@require_POST
def scansession_close(request, pk):
    """Close a session exactly once — stamps ended_at and freezes it against edits."""
    obj = get_object_or_404(ScanSession.objects.filter(tenant=request.tenant), pk=pk)
    try:
        obj.close()
    except ValidationError:
        messages.error(request, f"{obj.number} is already closed.")
        return redirect("inventory:scansession_detail", pk=pk)
    obj.save()
    write_audit_log(request.user, obj, "update", {"action": "close"})
    messages.success(request, f"Scan Session {obj.number} closed.")
    return redirect("inventory:scansession_detail", pk=pk)


@tenant_admin_required
@require_POST
def scansession_delete(request, pk):
    """Delete a scan session record (admin only)."""
    return crud_delete(
        request,
        model=ScanSession,
        pk=pk,
        success_url="inventory:scansession_list",
    )


@login_required
def scan_console(request):
    """THE handheld surface — paste or beam codes, resolve them live against the spine."""
    if request.method == "POST":
        session_id = as_db_int(request.POST.get("session"))
        codes_raw = request.POST.get("codes", "")
        # Cap BEFORE the loop: a paste-bomb costs one slice here, not an open transaction.
        codes = [c.strip() for c in codes_raw.splitlines() if c.strip()][:MAX_CODES_PER_SUBMIT]
        truncated = len([c for c in codes_raw.splitlines() if c.strip()]) > MAX_CODES_PER_SUBMIT

        session = None
        if session_id is not None:
            session = ScanSession.objects.filter(
                tenant=request.tenant, pk=session_id, status="open"
            ).first()
        if session is None:
            messages.error(request, "Select an open scan session in this workspace.")
            return redirect("inventory:scan_console")

        ok_count = 0
        with transaction.atomic():
            for code in codes:
                _kind, obj = resolve_code(request.tenant, code)
                event = ScanEvent.record(session=session, raw_code=code, kind=_kind, obj=obj)
                if event is not None and event.ok:
                    ok_count += 1

        summary = f"{len(codes)} scanned · {ok_count} resolved · {len(codes) - ok_count} unknown"
        if truncated:
            summary += f" · truncated at {MAX_CODES_PER_SUBMIT} codes"
        messages.success(request, summary)
        return redirect("inventory:scan_console")

    mode = request.GET.get("mode", "single")
    if mode not in ("single", "batch"):
        mode = "single"

    sessions = ScanSession.objects.filter(tenant=request.tenant, status="open")[:10]
    recent_events = ScanEvent.objects.filter(tenant=request.tenant)[:25]

    # Rolling-24h capture health — one aggregate over the tenant's events.
    cutoff = timezone.now() - timedelta(days=1)
    agg = ScanEvent.objects.filter(tenant=request.tenant, scanned_at__gte=cutoff).aggregate(
        total=Count("id"),
        ok=Count("id", filter=Q(ok=True)),
    )
    stats = {
        "today": agg["total"],
        "ok_rate": (agg["ok"] / agg["total"]) if agg["total"] else None,
    }

    return render(
        request,
        "inventory/barcode/console.html",
        {
            "mode": mode,
            "sessions": sessions,
            "recent_events": recent_events,
            "stats": stats,
            "is_admin": _is_admin(request.user),
        },
    )
