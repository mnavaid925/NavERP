"""Procurement 6.1 User Dashboard & Portal — the Recent Activity Feed.

**Recent Activity Feed** bullet: a chronological log of submissions and approvals on procurement
documents. The trail itself is ``core.AuditLog`` (append-only, written by the shared CRUD helpers
on every mutation across every app) filtered to procurement-relevant content types by
:func:`~apps.procurement.views._helpers.procurement_activity_qs` — a second feed table would be
two sources of truth for "what happened", so there is none.

There is deliberately NO create/edit/delete for feed rows: they are records of what happened, not
opinions to restate. ``activity_detail`` exists only to read one entry's field-level changes.
"""
from datetime import date, datetime, time, timedelta

from django.utils import timezone

from apps.core.models import AuditLog
from apps.procurement.views._common import *  # noqa: F401,F403
from apps.procurement.views._helpers import ACTIVITY_FEED_NOTE, procurement_activity_qs

#: Feed pages are scanned for sequence, not paged through one-by-one — 30/page like scm's trails.
FEED_PER_PAGE = 30

#: The default window when the page is opened with neither date (the audit log only grows).
DEFAULT_WINDOW_DAYS = 30


def _window(raw_from, raw_to):
    """Resolve the two GET boxes into dates, falling back to the default window.

    A junk value (``?date_from=yesterday``) or an impossible date (``2026-02-31``) takes the
    DEFAULT rather than raising — this is a query string anybody can type into, and the page must
    say it defaulted (``raw`` echoes what was actually typed) rather than silently disagreeing
    with its own filter bar.
    """
    today = timezone.localdate()
    default_from = today - timedelta(days=DEFAULT_WINDOW_DAYS - 1)

    def _parse(value, fallback):
        value = (value or "").strip()
        if not value:
            return fallback, ""
        try:
            return date.fromisoformat(value), value
        except ValueError:
            return fallback, value

    date_from, raw_from = _parse(raw_from, default_from)
    date_to, raw_to = _parse(raw_to, today)
    if date_to < date_from:
        # Swapped bounds are corrected, not fatal — show the span the user plainly meant.
        date_from, date_to = date_to, date_from
    return {"date_from": date_from, "date_to": date_to,
            "date_from_raw": raw_from, "date_to_raw": raw_to}


def _aware_bounds(date_from, date_to):
    """A date pair as the inclusive AWARE datetime range covering both days end to end.

    An explicit aware range rather than ``at__date`` lookups: ``__date`` compiles to CONVERT_TZ
    and returns NULL when the timezone tables are not loaded — which on XAMPP MariaDB they are
    not (the scm cold-chain finding).
    """
    start = timezone.make_aware(datetime.combine(date_from, time.min))
    end = timezone.make_aware(datetime.combine(date_to, time.max))
    return start, end


@login_required
def activity_list(request):
    """The full-page feed — always windowed, always paginated, never editable."""
    window = _window(request.GET.get("date_from"), request.GET.get("date_to"))
    start, end = _aware_bounds(window["date_from"], window["date_to"])
    qs = procurement_activity_qs(request.tenant).filter(at__gte=start, at__lte=end)

    # Scope: MY actions (the bullet's wording) is the default; ?scope=all widens to the workspace.
    scope = request.GET.get("scope", "mine")
    if scope not in ("mine", "all"):
        scope = "mine"
    if scope == "mine":
        qs = qs.filter(user=request.user)

    # Action filter resolved against the CLOSED vocabulary — a junk token narrows nothing instead
    # of rendering an empty page while the select shows "All".
    action = request.GET.get("action", "").strip()
    valid_actions = {value for value, _label in AuditLog.ACTION_CHOICES}
    if action not in valid_actions:
        action = ""
    else:
        qs = qs.filter(action=action)

    return crud_list(
        request, qs, "procurement/dashboardportal/activity.html",
        search_fields=["target"],
        extra_context={
            "action": action,
            "action_choices": AuditLog.ACTION_CHOICES,
            "scope": scope,
            "window": window,
            "window_days": DEFAULT_WINDOW_DAYS,
            "window_defaulted": not (window["date_from_raw"] or window["date_to_raw"]),
            "feed_note": ACTIVITY_FEED_NOTE,
        },
        per_page=FEED_PER_PAGE,
    )


@login_required
def activity_detail(request, pk):
    """One audit row, restricted to the SAME domain filter as the list.

    The restriction matters: an audit pk guessed from another module's URL must 404 here even
    though the row belongs to this tenant — this page's contract is procurement rows only.
    """
    obj = get_object_or_404(procurement_activity_qs(request.tenant), pk=pk)
    changes = [(key, value) for key, value in (obj.changes or {}).items()]
    return render(request, "procurement/dashboardportal/activity_detail.html", {
        "obj": obj,
        "changes": changes,
        "feed_note": ACTIVITY_FEED_NOTE,
    })
