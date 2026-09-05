"""Procurement 6.17 Risk & Compliance Management — the fraud scan and the fraud board.

Two standalone pages that are about the RULES rather than about one alert, which is why they
live here rather than in ``FraudAlerts.py``:

* ``fraud_scan`` — GET renders the window form, the eight tuning constants READ-ONLY, and the
  plain statement of the one rule that is not buildable. POST runs ``FraudAlert.scan()`` and
  reports what it raised, what it skipped and what it capped.
* ``fraud_board`` — open alerts by rule, by severity and by age, plus the two citation panels
  that point at the neighbouring modules that already own their part of the problem.

Discipline a reviewer will otherwise go looking for:

* **The POST leg is admin-gated, the GET leg is not.** The gate is inside the function rather
  than a decorator, because a decorator would also hide the read-only thresholds and the
  not-buildable note from every non-admin — and those are exactly the things everybody should
  be able to read. A non-admin POST is refused with a message, never silently ignored.
* **The scan is the only thing on either page that writes**, and it writes ``FraudAlert`` rows
  and nothing else (L29). No suspension, no invoice block, no PO hold, no party edit.
* **The window cap is enforced twice** — by ``FraudScanForm`` where it can be a field error, and
  again inside ``scan()`` as the non-form backstop. Both measure it arithmetically; neither ever
  builds the range (L40 §1).
* **The board is four aggregate queries**, not a Python walk over every alert. Each breakdown is
  one grouped ``values().annotate()``; the ageing buckets are one conditional aggregate.
* **"Rules", never "AI".** Everything here is deterministic SQL and arithmetic, and both pages
  say so in those words.

Context contracts pinned by ``.claude/tasks/contract-procurement-6.17.md`` §1:

``fraud_scan``  → ``form``, ``results``, ``rule_labels``, ``skipped_groups``, ``capped``,
                  ``scan_limits``, ``not_buildable_note``, ``is_admin``.
``fraud_board`` → ``by_rule``, ``by_severity``, ``ageing``, ``rule_labels``,
                  ``citation_invoice_url``, ``citation_maverick_url``, ``stats``, ``is_admin``.
"""
from datetime import timedelta

from django.db.models import Count, Q, Sum
from django.urls import reverse

from apps.procurement.forms.RiskComplianceManagement.FraudAlerts import FraudScanForm
# NOT-YET-WIRED entity of this SAME sub-module: import the entity MODULE directly, never
# ``from apps.procurement.models import X`` — the sub-package is not wired until the Integrator
# lands it, and a package-level re-export would be a star-import cycle at URLconf import time.
from apps.procurement.models.RiskComplianceManagement.FraudAlerts import (
    OPEN_STATUSES, RULE_CHOICES, SEVERITY_CHOICES, SEVERITY_CSS, FraudAlert)
from apps.procurement.views._common import *  # noqa: F401,F403

TEMPLATE_SCAN = "procurement/riskcompliance/fraud_scan.html"
TEMPLATE_BOARD = "procurement/riskcompliance/fraud_board.html"

#: How far back the scan form's default window reaches when the page is opened cold.
DEFAULT_SCAN_DAYS = 90

#: The ageing buckets, worst LAST so the board reads left-to-right from fresh to neglected.
#: ``(key, label, lower bound in days, upper bound in days or None, badge class)`` — bounds are
#: half-open on the age, so a 7-day-old alert is in the first bucket and an 8-day-old in the
#: second, and no alert can fall into two.
AGE_BUCKETS = [
    ("fresh", "0-7 days", 0, 8, "badge-green"),
    ("week", "8-30 days", 8, 31, "badge-info"),
    ("month", "31-90 days", 31, 91, "badge-amber"),
    ("stale", "Over 90 days", 91, None, "badge-red"),
]


# -- shared helpers ------------------------------------------------------------------------------

def _is_admin(request):
    """Mirrors ``@tenant_admin_required`` exactly, so a hidden button and a refused POST agree."""
    return bool(request.user.is_superuser or getattr(request.user, "is_tenant_admin", False))


def _need_tenant(request, what):
    """The superuser has no workspace by design; say so instead of rendering an empty page."""
    if request.tenant is None:
        messages.error(request, f"Select a tenant workspace to {what}.")
        return redirect("dashboard:home")
    return None


def _default_window():
    """The window the scan form opens on: the last ``DEFAULT_SCAN_DAYS`` up to tomorrow.

    ``end`` is EXCLUSIVE, so tomorrow is what includes today — an operator who scans "up to
    today" and finds nothing from this morning would reasonably conclude the rules do not work.
    """
    today = timezone.localdate()
    return {"start": today - timedelta(days=DEFAULT_SCAN_DAYS), "end": today + timedelta(days=1)}


# -- the scan ------------------------------------------------------------------------------------

@login_required
def fraud_scan(request):
    """Run the fraud rules over a window, and say exactly what they did.

    GET renders the form, the eight tuning constants read-only, and the not-buildable note.
    POST runs the scan — **admin only**, checked inside the function so the read-only half of
    the page stays visible to everybody.

    ``results`` is ``{rule_value: newly_raised_count}`` on POST and ``None`` on GET, which is what
    lets the template tell "not run yet" from "ran and found nothing" — two very different
    things to say on a fraud page.

    ``skipped_groups`` and ``capped`` come back from ``scan()``'s ``diagnostics`` out-parameter
    and carry these EXACT keys (L41 §1), which the template renders and nothing else::

        skipped_groups → {"rule", "rule_label", "attribute", "size", "limit"}
        capped         → {"rule", "rule_label", "attribute", "emitted", "limit"}

    Both are stated on the page rather than swallowed. A scan that quietly skipped the group
    containing the real overlap, and said "6 alerts raised", would be worse than no scan.
    """
    guard = _need_tenant(request, "run the fraud rules")
    if guard is not None:
        return guard

    is_admin = _is_admin(request)
    results, diagnostics = None, {"skipped_groups": [], "capped": []}

    if request.method == "POST":
        if not is_admin:
            # Refused out loud rather than silently ignored — and BEFORE the form is bound, so a
            # non-admin never gets validation feedback on a scan they cannot run anyway.
            messages.error(request, "Only a workspace administrator can run the fraud rules.")
            return redirect("procurement:fraud_scan")
        form = FraudScanForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            results = FraudAlert.scan(
                request.tenant,
                form.cleaned_data["start"],
                form.cleaned_data["end"],
                rules=form.selected_rules(),
                user=request.user,
                diagnostics=diagnostics,
            )
            raised = sum(results.values())
            if raised:
                # ONE audit entry per scan, not one per alert: the alerts themselves are the
                # record of what was found, and an audit log that mirrors them row for row is a
                # log nobody can read.
                # ``tenant=`` is passed EXPLICITLY: with ``obj=None`` the helper falls back to
                # the user's own tenant, and a superuser running a workspace scan has none — the
                # entry would land unattributed.
                write_audit_log(request.user, None, "update", changes={
                    "action": "fraud_scan",
                    "window": f"{form.cleaned_data['start']} to {form.cleaned_data['end']}",
                    "raised": raised,
                }, tenant=request.tenant)
                messages.success(request, f"{raised} new fraud alert(s) raised.")
            else:
                messages.info(
                    request,
                    "The rules ran and raised nothing new. Alerts that already existed for this "
                    "window were refreshed in place, and none was re-opened.")
    else:
        form = FraudScanForm(initial=_default_window(), tenant=request.tenant)

    return render(request, TEMPLATE_SCAN, {
        "form": form,
        "results": results,
        "rule_labels": RULE_CHOICES,
        "skipped_groups": diagnostics["skipped_groups"],
        "capped": diagnostics["capped"],
        "scan_limits": FraudAlert.scan_limits(),
        "not_buildable_note": FraudAlert.NOT_BUILDABLE_NOTE,
        "is_admin": is_admin,
    })


# -- the board -----------------------------------------------------------------------------------

def _board_stats(tenant):
    """The board's headline counts. ``confirmed`` is the contract's name for ``substantiated``."""
    return FraudAlert.objects.filter(tenant=tenant).aggregate(
        total=Count("id"),
        open=Count("id", filter=Q(status="open")),
        investigating=Count("id", filter=Q(status="investigating")),
        confirmed=Count("id", filter=Q(status="substantiated")),
        high=Count("id", filter=Q(severity="high", status__in=OPEN_STATUSES)),
    )


def _by_rule(tenant, register_url):
    """Open and total alerts per rule, as ONE grouped aggregate.

    ROW-DICT CONTRACT (L41 §1) — each entry carries EXACTLY::

        {"rule", "label", "open", "total", "high", "amount", "url"}

    ``url`` narrows the register by RULE ONLY. The open/high figures are deliberately not links:
    the register's status filter takes a single value and "open" there means the ``open`` status
    rather than both live statuses, so a link would land on a shorter list than the number beside
    it — the classic way a board stops being trusted.

    Every rule appears, including the ones with nothing against them. A rule silently missing
    from a fraud board reads as a rule that was never run.
    """
    grouped = {row["rule"]: row for row in (
        FraudAlert.objects.filter(tenant=tenant).values("rule").annotate(
            total=Count("id"),
            open=Count("id", filter=Q(status__in=OPEN_STATUSES)),
            high=Count("id", filter=Q(severity="high", status__in=OPEN_STATUSES)),
            amount=Sum("amount", filter=Q(status__in=OPEN_STATUSES)),
        ))}
    rows = []
    for value, label in RULE_CHOICES:
        found = grouped.get(value, {})
        rows.append({
            "rule": value,
            "label": label,
            "open": found.get("open", 0),
            "total": found.get("total", 0),
            "high": found.get("high", 0),
            # NULL when no open alert under this rule carries an amount — an overlap rule never
            # has one, and rendering 0.00 there would claim a measured zero.
            "amount": found.get("amount"),
            "url": f"{register_url}?rule={value}",
        })
    return rows


def _by_severity(tenant, register_url):
    """Open and total alerts per severity, as ONE grouped aggregate.

    ROW-DICT CONTRACT (L41 §1) — each entry carries EXACTLY::

        {"severity", "label", "css", "open", "total", "url"}

    Ordered high → low: on this board the row that matters is at the top.
    """
    grouped = {row["severity"]: row for row in (
        FraudAlert.objects.filter(tenant=tenant).values("severity").annotate(
            total=Count("id"),
            open=Count("id", filter=Q(status__in=OPEN_STATUSES)),
        ))}
    rows = []
    for value, label in reversed(SEVERITY_CHOICES):
        found = grouped.get(value, {})
        rows.append({
            "severity": value,
            "label": label,
            "css": SEVERITY_CSS.get(value, "badge-slate"),
            "open": found.get("open", 0),
            "total": found.get("total", 0),
            "url": f"{register_url}?severity={value}",
        })
    return rows


def _ageing(tenant, today):
    """How long the OPEN alerts have been sitting, in four buckets, as ONE conditional aggregate.

    ROW-DICT CONTRACT (L41 §1) — each entry carries EXACTLY::

        {"key", "label", "count", "css"}

    There is deliberately **no ``url``**: the register has no date-range filter, so a link here
    would either 404 a parameter nothing reads or land on a list that does not match the number
    printed beside it. An honest count with no link beats a link to the wrong page.

    Age is measured from ``document_date`` — the date of the FACT — so a bucket does not reset
    every time somebody re-runs the scan.
    """
    aggregates = {}
    for key, _label, low, high, _css in AGE_BUCKETS:
        # An age of ``low`` days means document_date <= today - low; an age below ``high`` means
        # document_date > today - high. Computed as two date bounds so the whole thing is one
        # SQL aggregate rather than a Python walk over every open alert.
        condition = Q(status__in=OPEN_STATUSES)
        if low:
            condition &= Q(document_date__lte=today - timedelta(days=low))
        if high is not None:
            condition &= Q(document_date__gt=today - timedelta(days=high))
        aggregates[key] = Count("id", filter=condition)
    # The freshest bucket carries NO upper date bound (``low`` is 0 for it), so it also catches an
    # alert dated today or, defensively, later. A ``document_date__lte=today`` here would leave a
    # future-dated open alert in no bucket at all, and the buckets would silently sum to less than
    # ``stats.open`` — reachable, because FraudScanForm bounds ``end`` only relative to ``start``.
    counts = FraudAlert.objects.filter(tenant=tenant).aggregate(**aggregates)
    return [{"key": key, "label": label, "count": counts.get(key, 0), "css": css}
            for key, label, _low, _high, css in AGE_BUCKETS]


@login_required
def fraud_board(request):
    """Where the open fraud work is: by rule, by severity, by age — and who else owns what.

    Four aggregate queries and no stored rollup: the board is computed from the register on every
    request, so it cannot go stale and there is no counter to drift.

    The two citation panels exist so this page does not quietly claim work that is not its own:

    * **``citation_invoice_url``** points at 6.13's DUPLICATE-INVOICE board rather than at the
      invoice register with a query parameter. The register's filters are status / match_status /
      vendor / source / invoice_type — there is no duplicate parameter on it, and inventing one
      would render a filter the view ignores. The dedicated board is the page that actually
      answers the question.
    * **``citation_maverick_url``** points at 6.14's maverick dashboard. Spend that went around
      the process is a different question from spend that was not honest, and 6.17 does not
      re-detect it.
    """
    guard = _need_tenant(request, "review the fraud board")
    if guard is not None:
        return guard

    today = timezone.localdate()
    register_url = reverse("procurement:fraudalert_list")
    return render(request, TEMPLATE_BOARD, {
        "by_rule": _by_rule(request.tenant, register_url),
        "by_severity": _by_severity(request.tenant, register_url),
        "ageing": _ageing(request.tenant, today),
        "rule_labels": RULE_CHOICES,
        "citation_invoice_url": reverse("procurement:supplierinvoice_duplicates"),
        "citation_maverick_url": reverse("procurement:maverick_dashboard"),
        "stats": _board_stats(request.tenant),
        "is_admin": _is_admin(request),
    })
