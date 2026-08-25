"""Inventory 5.18 Journal Entry Automation — the computed board + its two posting verbs.

One page answers "what stock value has not reached the ledger yet, and what did":

* the account map (GLPostRule per event type) with its active state;
* PENDING — posted ``scm.StockAdjustment``s that have no JournalSyncLog row yet,
  each with its signed value impact;
* RECENT — the register of what was posted (JSY rows), linked to their JEs.

The COGS runner defaults its window to "the day after the last batch → today", so the
ordinary rhythm is open-page, press Post. Both verbs are admin-gated and refuse
politely through the services' ValidationErrors.
"""
from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.dateparse import parse_date

from apps.core.decorators import tenant_admin_required
from apps.inventory.models import (
    GLPostRule,
    JournalSyncLog,
    post_adjustment_to_gl,
    post_cogs_batch,
)
from apps.inventory.views._common import *  # noqa: F401,F403
from apps.scm.models import StockAdjustment

ZERO = Decimal("0")


def _scoped_pending(tenant):
    """Posted adjustments with no JSY row yet — ONE anti-join, newest first."""
    already = (JournalSyncLog.objects.filter(tenant=tenant, stock_adjustment__isnull=False)
               .values("stock_adjustment_id"))
    return (StockAdjustment.objects.filter(tenant=tenant, status="posted")
            .exclude(pk__in=already)
            .select_related("location")
            .order_by("-posted_at", "-id"))


@login_required
def je_automation(request):
    tenant = request.tenant
    rules = {r.event_type: r for r in GLPostRule.objects.filter(tenant=tenant)
             .select_related("inventory_account", "offset_account")}
    pending = list(_scoped_pending(tenant)[:50])
    logs = (JournalSyncLog.objects.filter(tenant=tenant)
            .select_related("stock_adjustment", "journal_entry")[:15])
    last_batch = (JournalSyncLog.objects.filter(tenant=tenant, source_kind="cogs_batch")
                  .order_by("-date_to").first())
    today = timezone.localdate()
    default_from = ((last_batch.date_to + timedelta(days=1)) if last_batch else today)
    return render(request, "inventory/finint/je_automation.html", {
        "adjustment_rule": rules.get("adjustment"),
        "cogs_rule": rules.get("cogs"),
        "pending": pending,
        "pending_value": sum((a.value_impact() for a in pending), ZERO),
        "logs": logs,
        "last_batch": last_batch,
        "default_from": min(default_from, today),
        "default_to": today,
    })


@tenant_admin_required
@require_POST
def je_post_adjustment(request, pk):
    adjustment = get_object_or_404(StockAdjustment, pk=pk, tenant=request.tenant)
    try:
        log, je = post_adjustment_to_gl(request.tenant, request.user, adjustment)
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
        return redirect("inventory:je_automation")
    messages.success(request, f"{adjustment.number} posted to the GL as {je.number}.")
    return redirect("inventory:je_automation")


@tenant_admin_required
@require_POST
def je_post_cogs(request):
    date_from = parse_date(request.POST.get("date_from") or "")
    date_to = parse_date(request.POST.get("date_to") or "")
    if date_from is None or date_to is None:
        messages.error(request, "Pick both dates for the COGS window.")
        return redirect("inventory:je_automation")
    try:
        log, je = post_cogs_batch(request.tenant, request.user, date_from, date_to)
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
        return redirect("inventory:je_automation")
    messages.success(
        request, f"COGS batch posted to the GL as {je.number} ({log.moves_count} moves).")
    return redirect("inventory:je_automation")
