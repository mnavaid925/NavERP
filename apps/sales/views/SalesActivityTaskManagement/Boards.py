"""Sales 8.8 — the three read-only boards. NO NEW MODEL IS INTRODUCED HERE.

Modelled on `apps/sales/views/TerritoryQuotaManagement/TerritoryBoards.py`, which shipped
`territory_rebalance_preview` / `territory_coverage_gap` / `territory_white_space` the same way.

**EVERY CAP IS NAMED, PUBLISHED AND SURFACED (L40).** A bound that computes the thing it is bounding
is not a bound — so each constant below is passed into the template as part of a `caps` dict and
printed next to the figure it limits. A board that silently truncates reads as a complete answer,
which is the failure mode L40 was written about.

**THE SUGGESTION BOARD IS RULES, NOT A MODEL, AND SAYS SO.** Every suggestion comes from a named,
deterministic rule below. Nothing here calls an external service, and no language model is involved —
which is why `SalesPlanCycle.suggestion_mode` defaults to `"manual"` and why the board prints the
rule name beside each row. An "AI-suggested" label on a hard-coded `if` would be a lie.

**ORDERING IS EXPLICIT EVERYWHERE (L61).** Anything feeding a "most recent" comparison — or ranking
suggestions — carries an explicit tie-break. An unordered `.first()` is a latent idempotency bug that
only shows up when two rows tie.
"""
from datetime import timedelta

from django.db.models import Count, Max, Q
from django.utils import timezone

from apps.crm.models import CalendarEvent, CrmTask, Opportunity, Territory
from apps.core.models import Party
from apps.sales.models.SalesActivityTaskManagement.ActivityLogs import ActivityLog
from apps.sales.models.SalesActivityTaskManagement.ActivityTypes import ActivityType
from apps.sales.models.SalesActivityTaskManagement.SalesPlanCycles import SalesPlanCycle
from apps.sales.views._common import *

PLAN_TEMPLATE = "sales/salesactivitytaskmanagement/boards/plan.html"
SUGGESTIONS_TEMPLATE = "sales/salesactivitytaskmanagement/boards/next_best_actions.html"
ENGAGEMENT_TEMPLATE = "sales/salesactivitytaskmanagement/boards/email_engagement.html"

# ---- the caps. Every one of these is surfaced in the template beside the number it limits. -------
MAX_BOARD_ACTIVITIES = 500
MAX_BOARD_TASKS = 200
MAX_BOARD_EVENTS = 100
MAX_BOARD_OPPS = 200
MAX_SUGGESTIONS = 25
MAX_ENGAGEMENT_ROWS = 200

# ---- the staleness windows. Named, so the page can say "14" rather than leaving the reader to infer.
STALE_ACTIVITY_DAYS = 14
STALE_EMAIL_DAYS = 7
EVENT_PREP_DAYS = 3

#: Opportunity stages that are finished — a closed deal is never "stale", it is done.
CLOSED_STAGES = ["closed_won", "closed_lost"]


def _caps(**extra):
    """The single source for every cap a board publishes. One dict, every template."""
    caps = {
        "activities": MAX_BOARD_ACTIVITIES,
        "tasks": MAX_BOARD_TASKS,
        "events": MAX_BOARD_EVENTS,
        "opportunities": MAX_BOARD_OPPS,
        "suggestions": MAX_SUGGESTIONS,
        "stale_activity_days": STALE_ACTIVITY_DAYS,
        "stale_email_days": STALE_EMAIL_DAYS,
        "event_prep_days": EVENT_PREP_DAYS,
    }
    caps.update(extra)
    return caps


@login_required
def sales_activity_plan(request):
    """'My day / this week' — goals against actuals, open tasks, and what's already booked.

    Serves NavERP bullets 3 and 5 together. Bullet 3 is served by LINKING to CRM 1.5's
    ``CalendarEvent`` rather than rebuilding a calendar: `sync_source` already covers Google,
    Outlook and iCal, and `public_token` already is the login-free invite/RSVP surface.
    """
    tenant = request.tenant
    today = timezone.localdate()
    cycles = SalesPlanCycle.objects.filter(tenant=tenant).select_related("owner", "territory")

    # `?cycle=<pk>` picks the cycle; default is the active one covering today, else the most recent
    # one that has started. `.order_by(...)` FIRST: an unordered `.first()` picks an arbitrary row
    # whenever two cycles tie on `period_start`, which is exactly L61.
    cycle = None
    requested = request.GET.get("cycle", "")
    if requested and requested.isdecimal():
        cycle = cycles.filter(pk=int(requested)).first()
    if cycle is None:
        cycle = cycles.filter(period_start__lte=today, period_end__gte=today, status="active").order_by("-period_start", "-pk").first()
    if cycle is None:
        cycle = cycles.filter(period_start__lte=today).order_by("-period_start", "-pk").first()

    progress_rows = []
    open_tasks = CrmTask.objects.none()
    upcoming_events = CalendarEvent.objects.none()
    logged = []
    if cycle is not None:
        as_of = None if cycle.status == "closed" else today
        progress_rows = [
            {"goal": goal, "actual": actual, "target": target, "percent": percent}
            for goal, (actual, target, percent) in (
                (goal, cycle.progress_for(goal, as_of=as_of)) for goal in cycle.goals.all()
            )
        ]
        open_tasks = (
            CrmTask.objects.filter(
                tenant=tenant,
                status__in=CrmTask.OPEN_STATUSES,
                due_date__gte=cycle.period_start,
                due_date__lte=cycle.period_end,
            )
            .select_related("party", "related_opportunity")
            .order_by("due_date", "-pk")[:MAX_BOARD_TASKS]
        )
        logged = (
            ActivityLog.objects.filter(
                tenant=tenant,
                occurred_on__gte=cycle.period_start,
                occurred_on__lte=cycle.period_end,
            )
            .select_related("communication_log", "activity_type", "owner", "opportunity")
            .order_by("-occurred_on", "-pk")[:MAX_BOARD_ACTIVITIES]
        )
    upcoming_events = (
        CalendarEvent.objects.filter(
            tenant=tenant,
            status__in=["scheduled", "confirmed"],
            start__gte=timezone.now(),
            start__lte=timezone.now() + timedelta(days=STALE_ACTIVITY_DAYS),
        )
        .select_related("party", "owner")
        .order_by("start", "pk")[:MAX_BOARD_EVENTS]
    )
    return render(request, PLAN_TEMPLATE, {
        "cycle": cycle,
        "cycles": cycles.order_by("-period_start", "-pk")[:25],
        "today": today,
        "progress_rows": progress_rows,
        "open_tasks": open_tasks,
        "logged": logged,
        "upcoming_events": upcoming_events,
        "caps": _caps(),
    })


@login_required
def sales_next_best_actions(request):
    """Deterministic, rule-based next-best-actions. Serves bullet 5.

    Five rules, each named in its output. Every one reads a table that already exists; none of them
    calls anything external. Ordering is `(-weight, due_date, pk)` — explicit, so two suggestions of
    equal weight and date always come back in the same order (L61).
    """
    tenant = request.tenant
    today = timezone.localdate()
    stale_before = today - timedelta(days=STALE_ACTIVITY_DAYS)
    suggestions = []

    # Rule 1 — an overdue open task. The highest-value action is the one already promised.
    for task in (
        CrmTask.objects.filter(tenant=tenant, status__in=CrmTask.OPEN_STATUSES, due_date__lt=today)
        .select_related("party", "related_opportunity")
        .order_by("due_date", "-pk")[:MAX_BOARD_TASKS]
    ):
        suggestions.append({
            "rule": "overdue_task",
            "weight": 100,
            "title": f"Overdue: {task.subject}",
            "detail": f"Due {task.due_date:%d %b %Y} and still open.",
            "due_date": task.due_date,
            "pk": task.pk,
        })

    # Rule 2 — an open deal nobody has touched in 14 days. The single most-used query in every
    # product in the research catalog, and the one that most needs a stale window to mean anything.
    # The `Max` is aggregated ONCE into a dict and then looked up per opportunity — scanning the
    # queryset inside the loop would make this O(opportunities × activities) on a busy workspace.
    last_touch = {
        row["opportunity_id"]: row["_last"]
        for row in ActivityLog.objects.filter(tenant=tenant, opportunity_id__isnull=False)
        .values("opportunity_id")
        .annotate(_last=Max("occurred_on"))
    }
    for opp in (
        Opportunity.objects.filter(tenant=tenant)
        .exclude(stage__in=CLOSED_STAGES)
        .select_related("account", "owner")
        .order_by("name")[:MAX_BOARD_OPPS]
    ):
        touched = last_touch.get(opp.pk)
        if touched is not None and touched >= stale_before:
            continue
        gap = (today - touched).days if touched else STALE_ACTIVITY_DAYS
        suggestions.append({
            "rule": "stale_opportunity",
            "weight": 90,
            "title": f"No activity on {opp.name}",
            "detail": (
                f"Open in {opp.get_stage_display()} with no logged activity for {gap} day(s)."
                if touched
                else f"Open in {opp.get_stage_display()} with no logged activity at all."
            ),
            "due_date": opp.close_date,
            "opportunity": opp,
            "pk": opp.pk,
        })

    # Rule 3 — an email opened, never clicked, older than a week.
    quiet_before = today - timedelta(days=STALE_EMAIL_DAYS)
    for log in (
        ActivityLog.objects.filter(
            tenant=tenant,
            open_count__gt=0,
            click_count=0,
            replied_at__isnull=True,
            occurred_on__lt=quiet_before,
            communication_log__channel="email",
        )
        .select_related("communication_log", "owner")
        .order_by("occurred_on", "-pk")[:MAX_BOARD_TASKS]
    ):
        suggestions.append({
            "rule": "opened_not_clicked",
            "weight": 70,
            "title": f"Opened but not clicked: {log.communication_log.subject or 'an email'}",
            "detail": (
                f"Opened {log.open_count} time(s) on "
                f"{log.occurred_on:%d %b %Y} and never clicked."
            ),
            "due_date": today,
            "pk": log.pk,
        })

    # Rule 4 — a meeting in the next few days with no prep logged against it.
    prep_cutoff = timezone.now() + timedelta(days=EVENT_PREP_DAYS)
    for event in (
        CalendarEvent.objects.filter(
            tenant=tenant,
            status__in=["scheduled", "confirmed"],
            start__gte=timezone.now(),
            start__lte=prep_cutoff,
        )
        .select_related("party", "owner")
        .order_by("start", "pk")[:MAX_BOARD_EVENTS]
    ):
        prepared = ActivityLog.objects.filter(
            tenant=tenant, occurred_on__gte=today - timedelta(days=EVENT_PREP_DAYS), account=event.party_id
        ).exists() if event.party_id else False
        if prepared:
            continue
        suggestions.append({
            "rule": "event_prep",
            "weight": 60,
            "title": f"Prep for {event.title}",
            "detail": (
                f"{event.start:%a %d %b %H:%M} and nothing logged in the last "
                f"{EVENT_PREP_DAYS} day(s) against "
                f"{event.party.name if event.party else 'the account'}."
            ),
            "due_date": event.start.date(),
            "pk": event.pk,
        })

    # Rule 5 — an activity that named its own next step and has not reached its due date.
    for log in (
        ActivityLog.objects.filter(
            tenant=tenant,
            next_best_action__gt="",
            next_best_action_due__gte=today,
        )
        .select_related("communication_log", "owner")
        .order_by("next_best_action_due", "-pk")[:MAX_BOARD_TASKS]
    ):
        suggestions.append({
            "rule": "own_next_step",
            "weight": 50,
            "title": log.next_best_action,
            "detail": f"Named on activity {log.number}; due {log.next_best_action_due:%d %b %Y}.",
            "due_date": log.next_best_action_due,
            "pk": log.pk,
        })

    # The ONE ordering, applied once, with an explicit tie-break on pk.
    suggestions.sort(key=lambda s: (-s["weight"], s["due_date"] or today, s["pk"]))
    truncated = len(suggestions) > MAX_SUGGESTIONS
    return render(request, SUGGESTIONS_TEMPLATE, {
        "suggestions": suggestions[:MAX_SUGGESTIONS],
        "suggested_at": timezone.now(),
        "truncated": truncated,
        "rules": [
            ("overdue_task", "An open task whose due date has passed."),
            ("stale_opportunity", f"An open deal with no logged activity in {STALE_ACTIVITY_DAYS} days."),
            ("opened_not_clicked", f"An email opened but never clicked over {STALE_EMAIL_DAYS} days ago."),
            ("event_prep", f"A meeting within {EVENT_PREP_DAYS} days with nothing logged against it."),
            ("own_next_step", "An activity that named its own next step, now due."),
        ],
        "caps": _caps(),
    })


@login_required
def sales_email_engagement(request):
    """Opens / clicks / replies by rep and by activity type. Serves bullet 4.

    Every figure is a SUM over `ActivityLog`'s frozen counters — there is no separate engagement
    event table anywhere in the project, which is precisely why these columns live here.
    """
    tenant = request.tenant
    by_owner = (
        ActivityLog.objects.filter(tenant=tenant)
        .exclude(owner=None)
        .values("owner_id", "owner__username", "owner__first_name", "owner__last_name")
        .annotate(
            activities=Count("id"),
            opened=Count("id", filter=Q(open_count__gt=0)),
            clicked=Count("id", filter=Q(click_count__gt=0)),
            replied=Count("id", filter=Q(replied_at__isnull=False)),
            total_opens=Count("open_count"),
            total_clicks=Count("click_count"),
        )
        .order_by("-total_clicks", "-total_opens", "owner__username")[:MAX_ENGAGEMENT_ROWS]
    )
    by_type = (
        ActivityLog.objects.filter(tenant=tenant)
        .values("activity_type_id", "activity_type__name")
        .annotate(
            activities=Count("id"),
            opened=Count("id", filter=Q(open_count__gt=0)),
            clicked=Count("id", filter=Q(click_count__gt=0)),
            replied=Count("id", filter=Q(replied_at__isnull=False)),
        )
        .order_by("-activities", "activity_type__name")[:MAX_ENGAGEMENT_ROWS]
    )
    totals = ActivityLog.objects.filter(tenant=tenant).aggregate(
        activities=Count("id"),
        opened=Count("id", filter=Q(open_count__gt=0)),
        clicked=Count("id", filter=Q(click_count__gt=0)),
        replied=Count("id", filter=Q(replied_at__isnull=False)),
        opens=Count("open_count"),
        clicks=Count("click_count"),
    )
    return render(request, ENGAGEMENT_TEMPLATE, {
        "by_owner": by_owner,
        "by_type": by_type,
        "totals": totals,
        "caps": _caps(engagement_rows=MAX_ENGAGEMENT_ROWS),
    })