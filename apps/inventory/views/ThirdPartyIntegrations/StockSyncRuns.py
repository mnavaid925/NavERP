"""Inventory 5.19 Third-Party Integrations & API — ``StockSyncRun`` views (append-only register).

Three routes, mirroring the scm ``WebhookDelivery`` posture: a filtered list, a read-only detail
and ONE admin POST verb. There is deliberately NO create/edit/delete view — runs enter through
``StockSyncRun.record()`` (the sync verb + seeder) and the retry verb below moves only the row's
queue state (status / attempt_no / next_retry_at); it never rewrites a recorded outcome.

**stocksyncrun_retry FIRES NO HTTP REQUEST.** 5.19 ships no transport and no scheduler reads
``next_retry_at`` afterwards; the verb stamps the next slot of SYNC_BACKOFF_SECONDS so the row's
state stays honest, which is exactly why its flash message says out loud that nothing was sent.
"""
from datetime import timedelta

from django.db import transaction
from django.db.models import Count
from django.utils import timezone

from apps.core.crud import as_db_int, crud_detail, crud_list
from apps.core.decorators import tenant_admin_required
from apps.inventory.models.ThirdPartyIntegrations.IntegrationChannels import IntegrationChannel
from apps.inventory.models.ThirdPartyIntegrations.StockSyncRuns import StockSyncRun
from apps.inventory.models.ThirdPartyIntegrations._choices import (
    RUN_STATUS_CHOICES,
    SYNC_BACKOFF_SECONDS,
)
from apps.inventory.views._common import *  # noqa: F401,F403


def _is_admin(user):
    """The one admin flag every 5.19 template receives — same test as the decorator."""
    return bool(user.is_superuser or getattr(user, "is_tenant_admin", False))


@login_required
def stocksyncrun_list(request):
    """Append-only run register: search, ?channel= / ?status= lenses, KPI strip.

    Deep-links from the channel detail panel (?channel=<pk>&status=failed) must survive junk
    input too: ?channel=abc / ?channel=999999999999999999999 fall through as_db_int to an
    unfiltered list rather than a 500, and ?status=zzz falls back to no status filter.
    """
    qs = StockSyncRun.objects.filter(tenant=request.tenant).select_related("channel")

    valid_statuses = dict(RUN_STATUS_CHOICES)
    status = request.GET.get("status", "").strip()
    if status and status not in valid_statuses:
        status = ""
    if status:
        qs = qs.filter(status=status)

    channel_id = as_db_int(request.GET.get("channel"))
    if channel_id is not None:
        qs = qs.filter(channel_id=channel_id)

    # KPIs across the tenant's full register — one grouped query, not five COUNTs.
    status_counts = {
        row["status"]: row["n"]
        for row in StockSyncRun.objects.filter(tenant=request.tenant)
        .values("status")
        .annotate(n=Count("id"))
    }
    stats = {
        "total": sum(status_counts.values()),
        "success": status_counts.get("success", 0),
        "partial": status_counts.get("partial", 0),
        "failed": status_counts.get("failed", 0),
        "simulated": status_counts.get("simulated", 0),
    }

    channel_choices = [
        (c.pk, str(c))
        for c in IntegrationChannel.objects.filter(tenant=request.tenant).order_by("name", "id")
    ]

    return crud_list(
        request,
        qs,
        "inventory/integration/syncrun/list.html",
        search_fields=["number", "error_code"],
        filters=(),
        extra_context={
            "stats": stats,
            "status_choices": RUN_STATUS_CHOICES,
            "status": status,
            "channel_choices": channel_choices,
            "channel": request.GET.get("channel", ""),
            "is_admin": _is_admin(request.user),
        },
    )


@login_required
def stocksyncrun_detail(request, pk):
    """Read-only run sheet — outcomes, error panel, payload excerpt and the queue-state chip."""
    return crud_detail(
        request,
        model=StockSyncRun,
        pk=pk,
        template="inventory/integration/syncrun/detail.html",
        select_related=("channel",),
        extra_context={
            # The SAME ceiling next_backoff_seconds guards on, so the page's "attempt N of M"
            # chip and the retry verb's exhaustion check can never disagree.
            "max_attempts": len(SYNC_BACKOFF_SECONDS),
            "is_admin": _is_admin(request.user),
        },
    )


# =========================================================================================== action
@tenant_admin_required
@require_POST
def stocksyncrun_retry(request, pk):
    """Queue this run onto the next backoff slot — or mark it exhausted. **Sends nothing.**

    # WARNING: NO TRANSPORT. This fires no HTTP request — 5.19 ships no outbound transport and no
    # scheduler reads next_retry_at on a clock. The button says "Retry" and stamps intent only.

    The NEXT wait is computed from the CURRENT attempt state via the model property
    (attempt N sits on schedule slot N-1), then persisted: attempt_no advances exactly once and
    ``next_retry_at`` takes now + that wait. When the property answers ``None`` the published
    schedule is spent — the row is marked ``exhausted`` with ``next_retry_at`` cleared instead of
    being given an attempt the schedule does not describe.

    Recorded OUTCOME columns (counts / error_code / error_message / payload_excerpt / timestamps)
    are never touched: ``save(update_fields=...)`` is narrow on purpose so this verb cannot
    rewrite history even by accident. Evaluated inside ``transaction.atomic()`` on a row taken
    FOR UPDATE, so a double-click cannot burn two schedule slots on one press.
    """
    with transaction.atomic():
        obj = get_object_or_404(StockSyncRun.objects.select_for_update(), pk=pk,
                                tenant=request.tenant)

        wait_seconds = obj.next_backoff_seconds
        if wait_seconds is None:
            obj.status = "exhausted"
            # Cleared, not left behind: a stale future timestamp beside an exhausted status reads
            # as a bug in the integration rather than in the page.
            obj.next_retry_at = None
        else:
            obj.status = "pending"
            obj.attempt_no += 1
            obj.next_retry_at = timezone.now() + timedelta(seconds=wait_seconds)

        obj.save(update_fields=["status", "attempt_no", "next_retry_at", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "retry_scheduled"})

    if obj.status == "exhausted":
        messages.info(
            request,
            f"{obj.number} has used every attempt in the retry schedule "
            f"({StockSyncRun.MAX_ATTEMPTS}) and is now marked exhausted. Nothing was sent — "
            f"outbound transport is not part of this release.")
    else:
        messages.info(
            request,
            f"Attempt {obj.attempt_no} of {StockSyncRun.MAX_ATTEMPTS} queued for "
            f"{timezone.localtime(obj.next_retry_at):%d %b %Y %H:%M} ({wait_seconds}s from now). "
            f"Nothing was sent — outbound transport is not part of this release.")
    return redirect("inventory:stocksyncrun_detail", pk=pk)
