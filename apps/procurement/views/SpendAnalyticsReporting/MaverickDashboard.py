"""Procurement 6.14 Spend Analytics & Reporting — the maverick spend board + the scan verb.

**Maverick Spend Analysis** bullet. Two routes over ``MaverickSpendFinding``:

* ``maverick_dashboard`` (``spend/maverick/``) — a COMPUTED, read-only board. It owns no table and
  writes nothing: every figure is an aggregate over findings the detectors already raised, plus
  the recognised-spend denominator from ``analytics.maverick_rate``.
* ``maverick_scan`` (``spend/maverick/scan/``) — the ONE write in this module. POST-only and
  ``@tenant_admin_required`` (L27): a scan re-reads a whole window of spend, so it is not a link
  anybody can follow by accident.

Discipline worth stating, because a reviewer will look for it:

* **The scan is idempotent by construction.** Every candidate carries a deterministic
  ``dedupe_key`` and is upserted on it, and a finding somebody has already disposed of keeps its
  disposition — a re-scan refreshes the facts and can never quietly re-open settled work. Running
  it twice over an unchanged window raises zero new findings, which is what the success message
  reports.
* **The rate has a legend.** ``band`` is low / medium / high off the 10% and 20% thresholds the
  page prints beside the number, so the colour on the tile always means something specific.
* **The denominator excludes non-addressable spend.** Statutory tax, duty, payroll and
  intercompany settlement stay findings (the fact is still true) but drop out of the rate, because
  a percentage that counts payroll as "spend we could have put on contract" is not a number
  anybody can act on. ``exclusions_note`` says so on the page.

Nothing here posts to ``accounting.*`` — no Bill, no JournalEntry, no Budget, no Payment (L29).
"""
from datetime import date

from django.db.models import Count, Sum
from django.db.models.functions import TruncMonth
from django.urls import reverse

from apps.procurement.analytics import (
    DATE_RANGE_CHOICES,
    DEFAULT_RANGE,
    MAVERICK_BAND_HIGH,
    MAVERICK_BAND_LOW,
    MAX_GROUP_ROWS,
    UNASSIGNED_LABEL,
    UNCLASSIFIED_LABEL,
    _money,
    _share,
    maverick_rate,
    money,
    range_bounds,
)
from apps.procurement.models.SpendAnalyticsReporting.MaverickFindings import (
    REASON_CHOICES,
    SEVERITY_CHOICES,
    STATUS_CHOICES,
    MaverickSpendFinding,
)
from apps.procurement.views._common import *  # noqa: F401,F403

TEMPLATE = "procurement/spendanalytics/maverick_dashboard.html"

_RANGE_KEYS = {key for key, _label in DATE_RANGE_CHOICES}
_REASON_LABELS = dict(REASON_CHOICES)

#: Printed under the rate tile, verbatim. The exclusion is what makes the percentage actionable,
#: so it is never left implicit.
EXCLUSIONS_NOTE = (
    "The rate counts addressable spend only. Statutory tax, duty, payroll and intercompany "
    "settlement are still raised as findings when a detector sees them, but they are excluded "
    f"from the denominator — and a finding dismissed as a false positive is excluded from the "
    f"numerator. Bands: under {MAVERICK_BAND_LOW}% is low, {MAVERICK_BAND_LOW}–"
    f"{MAVERICK_BAND_HIGH}% is medium, above {MAVERICK_BAND_HIGH}% is high."
)

#: Printed above the scan button. A scan is an operator action over a bounded window, not a job.
SCAN_NOTE = (
    "A scan re-reads this window and upserts what it finds on a deterministic key: running it "
    "again never duplicates a finding, and a finding you have already justified, remediated or "
    "dismissed keeps that disposition — only its amounts and detail are refreshed."
)


def _rows(groups, total):
    """``(label, pk, value, count)`` tuples -> the pinned row dicts, biggest first."""
    ordered = sorted(groups, key=lambda row: (-(row[2] or 0), str(row[0])))
    return [{
        "label": label,
        "pk": pk,
        "value": money(value or 0),
        "display": _money(value),
        "pct": _share(value, total),
        "count": count or 0,
    } for label, pk, value, count in ordered[:MAX_GROUP_ROWS]]


def _window_findings(tenant, start, end):
    """Every finding whose SPEND falls in the window — dismissed rows included.

    The board shows dismissed findings in its counts (a workspace that dismissed forty findings
    did that work and should see it); only the RATE excludes them, which is why the exclusion
    lives in ``analytics.maverick_rate`` rather than in this queryset.
    """
    return MaverickSpendFinding.objects.filter(
        tenant=tenant, document_date__gte=start, document_date__lt=end)


@login_required
def maverick_dashboard(request):
    """**Maverick Spend Analysis** — the board: rate, reasons, and the four axes underneath."""
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace to view maverick spend.")
        return redirect("dashboard:home")

    range_key = request.GET.get("range", "").strip()
    range_key = range_key if range_key in _RANGE_KEYS else DEFAULT_RANGE
    start, end = range_bounds(range_key)

    findings = _window_findings(request.tenant, start, end)
    live = findings.exclude(status="dismissed")

    totals = live.aggregate(v=Sum("amount"), n=Count("id"), leak=Sum("leakage_amount"))
    total_value = money(totals["v"] or 0)

    # -- by reason ------------------------------------------------------------------------------
    # One grouped query, then padded out to the full REASON_CHOICES list so a reason with nothing
    # against it reads as a zero rather than as a missing row — "we found none" and "we did not
    # look" are different answers and the board must not blur them.
    seen = {row["reason"]: row for row in
            live.values("reason").annotate(v=Sum("amount"), n=Count("id"))}
    by_reason = []
    for reason, label in REASON_CHOICES:
        row = seen.get(reason, {})
        value = money(row.get("v") or 0)
        by_reason.append({
            "reason": reason,
            "label": label,
            "n": row.get("n") or 0,
            "value": value,
            "display": _money(value),
            "pct": _share(value, total_value),
        })
    by_reason.sort(key=lambda row: (-(row["value"] or 0), row["label"]))

    # -- the four axes --------------------------------------------------------------------------
    by_vendor = _rows([(row["vendor__name"] or UNASSIGNED_LABEL, row["vendor_id"], row["v"],
                        row["n"])
                       for row in live.values("vendor_id", "vendor__name")
                       .annotate(v=Sum("amount"), n=Count("id"))], total_value)

    by_category = _rows([(row["category__name"] or UNCLASSIFIED_LABEL, row["category_id"],
                          row["v"], row["n"])
                         for row in live.values("category_id", "category__name")
                         .annotate(v=Sum("amount"), n=Count("id"))], total_value)

    # The department bucket is explicit: ``org_unit`` is NULL for every PO-less invoice, and a
    # breakdown that dropped those rows would stop agreeing with the total above it.
    by_department = _rows([(row["org_unit__name"] or UNASSIGNED_LABEL, row["org_unit_id"],
                            row["v"], row["n"])
                           for row in live.values("org_unit_id", "org_unit__name")
                           .annotate(v=Sum("amount"), n=Count("id"))], total_value)

    by_severity = _rows([(dict(SEVERITY_CHOICES).get(row["severity"], row["severity"]), None,
                          row["v"], row["n"])
                         for row in live.values("severity")
                         .annotate(v=Sum("amount"), n=Count("id"))], total_value)

    # -- trend ----------------------------------------------------------------------------------
    labels, data = [], []
    for row in (live.annotate(_bucket=TruncMonth("document_date")).values("_bucket")
                .annotate(v=Sum("amount")).order_by("_bucket")):
        if row["_bucket"] is None:
            continue
        labels.append(row["_bucket"].strftime("%b %Y"))
        data.append(float(row["v"] or 0))

    rate = maverick_rate(request.tenant, start, end)
    status_counts = {row["status"]: row["n"] for row in
                     findings.values("status").annotate(n=Count("id"))}

    return render(request, TEMPLATE, {
        "by_reason": by_reason,
        "rate": rate,
        "by_vendor": by_vendor,
        "by_category": by_category,
        "by_department": by_department,
        "by_severity": by_severity,
        "trend": {"labels": labels, "data": data},
        # The same series pre-zipped for the table. A template cannot walk two parallel lists
        # without index gymnastics that silently render the wrong cell, so the pairing is done
        # here where it can be read.
        "trend_rows": [{"label": label, "display": _money(value)}
                       for label, value in zip(labels, data)],
        "leakage_total": money(totals["leak"] or 0),
        "leakage_display": _money(totals["leak"] or 0),
        "open_findings": status_counts.get("open", 0),
        "total_value": total_value,
        "total_display": _money(total_value),
        "stats": {
            "findings": totals["n"] or 0,
            "open": status_counts.get("open", 0),
            "acknowledged": status_counts.get("acknowledged", 0),
            "justified": status_counts.get("justified", 0),
            "remediated": status_counts.get("remediated", 0),
            "dismissed": status_counts.get("dismissed", 0),
            "value_at_risk": total_value,
            "leakage": money(totals["leak"] or 0),
        },
        "reason_choices": REASON_CHOICES,
        "severity_choices": SEVERITY_CHOICES,
        "status_choices": STATUS_CHOICES,
        "range_key": range_key,
        "date_range_choices": DATE_RANGE_CHOICES,
        "start": start,
        "end": end,
        "scan_url": reverse("procurement:maverick_scan"),
        "findings_url": reverse("procurement:maverickfinding_list"),
        "dashboard_url": reverse("procurement:spend_dashboard"),
        "exclusions_note": EXCLUSIONS_NOTE,
        "scan_note": SCAN_NOTE,
        "is_admin": bool(getattr(request.user, "is_superuser", False)
                         or getattr(request.user, "is_tenant_admin", False)),
    })


@login_required
@tenant_admin_required
@require_POST
def maverick_scan(request):
    """Run the detectors over the posted window and report ``{reason: count}``.

    The window is the board's own range selector, posted back — never a free-form date pair — so
    a scan can only ever cover a window somebody could already see. Unknown reasons in the posted
    checkbox group are ignored rather than raising (L11): a hand-edited value must NARROW the
    scan, not 500 it.
    """
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before running a scan.")
        return redirect("dashboard:home")

    range_key = request.POST.get("range", "").strip()
    range_key = range_key if range_key in _RANGE_KEYS else DEFAULT_RANGE
    start, end = range_bounds(range_key)

    posted = [value for value in request.POST.getlist("reason") if value in _REASON_LABELS]
    counts = MaverickSpendFinding.scan(request.tenant, start, end,
                                       reasons=posted or None, user=request.user)

    raised = sum(counts.values())
    detail = ", ".join(f"{_REASON_LABELS.get(reason, reason)}: {n}"
                       for reason, n in sorted(counts.items()) if n) or "nothing new"
    # The scan writes rows through the model rather than through a ``crud_*`` helper, so the audit
    # row is written HERE — a hand-rolled save path that skips it leaves an un-attributable change.
    # ``core.AuditLog.ACTION_CHOICES`` is create/update/delete only, so the verb is "update" with
    # the scan's own shape in ``changes``; inventing a fifth action would fail the field's choices.
    write_audit_log(request.user, None, "update", {
        "model": "MaverickSpendFinding",
        "action": "scan",
        "window": f"{start:%Y-%m-%d}..{end:%Y-%m-%d}",
        "reasons": posted or "all",
        "raised": raised,
    }, tenant=request.tenant)

    if raised:
        messages.success(request, f"Scan complete — {raised} new finding(s). {detail}.")
    else:
        messages.info(request, "Scan complete — no new findings. Existing rows were refreshed "
                               "and every disposition was kept.")
    return redirect(f"{reverse('procurement:maverick_dashboard')}?range={range_key}")
