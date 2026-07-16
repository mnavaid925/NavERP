"""HRM 3.22 Training Management — Calendar views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    TrainingSession,
)


# ------------------------------------------------------------ Training Calendar (3.22 upcoming sessions)
@login_required
def training_calendar(request):
    """A date-grouped view over TrainingSession (the Training Calendar bullet). Defaults to the
    upcoming lens (from today) and never shows cancelled sessions; optional ?delivery_mode / ?status
    / ?from / ?to GET filters narrow it. Bounded by the date range — no pagination."""
    qs = (TrainingSession.objects.filter(tenant=request.tenant)
          .select_related("course", "instructor_employee__party")
          .exclude(status="cancelled"))
    mode = request.GET.get("delivery_mode", "").strip()
    status = request.GET.get("status", "").strip()
    if mode:
        qs = qs.filter(delivery_mode=mode)
    if status:
        qs = qs.filter(status=status)
    # ?from defaults to today (the "upcoming" lens); ?to is an optional upper bound.
    from_date = parse_date(request.GET.get("from", "").strip() or "") or timezone.localdate()
    to_date = parse_date(request.GET.get("to", "").strip() or "")
    qs = qs.filter(start_datetime__date__gte=from_date)
    if to_date:
        qs = qs.filter(start_datetime__date__lte=to_date)

    sessions_by_date = {}
    for s in qs.order_by("start_datetime", "number")[:200]:
        sessions_by_date.setdefault(timezone.localtime(s.start_datetime).date(), []).append(s)
    return render(request, "hrm/training/calendar.html", {
        "sessions_by_date": list(sessions_by_date.items()),   # [(date, [session, ...]), ...]
        "delivery_mode_choices": TrainingSession.DELIVERY_MODE_CHOICES,
        # The calendar unconditionally excludes cancelled sessions, so offering "Cancelled" as a
        # filter option would be a dead choice that always returns nothing — drop it from the dropdown.
        "status_choices": [(v, lbl) for v, lbl in TrainingSession.STATUS_CHOICES if v != "cancelled"],
        "from_date": from_date,
        "to_date": to_date,
    })
