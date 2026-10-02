"""Sales 8.8 — the plan-cycle register, its CRUD, and the close/open verb.

**THE ACTUAL NUMBERS ON THIS PAGE ARE DERIVED, NEVER STORED (L37).** The list shows no attainment
column and the detail page stores no ``actual_count``: every figure comes from
``SalesPlanCycle.actual_for`` counting ``ActivityLog`` and ``crm.CrmTask`` rows inside the cycle's
window at read time. A stored number would have to be kept in step with the rows it summarises, and
the first deleted task, backdated activity or clock change would make it disagree with the ledger it
claims to summarise — while still reading as authoritative.

**`sales_plan_cycle_toggle` is POST-only** because it moves the cycle between draft/active/closed.
A GET link that changed a period's status would let a prefetch or a link preview close a plan.
"""
from datetime import timedelta

from django.db import transaction
from django.db.models import Count, Q
from django.urls import reverse
from django.utils import timezone

from apps.crm.models import CalendarEvent, CrmTask, Territory
from apps.core.utils import write_audit_log
from apps.sales.forms.SalesActivityTaskManagement.SalesPlanCycles import (
    ActivityGoalForm,
    SalesPlanCycleForm,
)
from apps.sales.forms._common import tenant_users
from apps.sales.models.SalesActivityTaskManagement.SalesPlanCycles import (
    ActivityGoal,
    SalesPlanCycle,
)
from apps.sales.views._common import *

LIST_TEMPLATE = "sales/salesactivitytaskmanagement/salesplancycle/list.html"
DETAIL_TEMPLATE = "sales/salesactivitytaskmanagement/salesplancycle/detail.html"
FORM_TEMPLATE = "sales/salesactivitytaskmanagement/salesplancycle/form.html"

PAGE_SIZE = 15

#: Open tasks and upcoming events shown on a cycle's detail page. Named and SURFACED, so a truncated
#: panel reads as truncated rather than complete (L40).
MAX_DETAIL_TASKS = 25
MAX_DETAIL_EVENTS = 10

ACTIVE_CHOICES = [("active", "Active"), ("inactive", "Inactive")]


def _cycle_queryset(request):
    return SalesPlanCycle.objects.filter(tenant=request.tenant).select_related("owner", "territory")


def _choice_context(request):
    tenant = request.tenant
    return {
        "cadence_choices": SalesPlanCycle.CADENCE_CHOICES,
        "status_choices": SalesPlanCycle.STATUS_CHOICES,
        "suggestion_mode_choices": SalesPlanCycle.SUGGESTION_MODE_CHOICES,
        "metric_choices": ActivityGoal.METRIC_CHOICES,
        "owners": tenant_users(tenant).order_by("username"),
        # ALL territories, retired included: a CLOSED plan must still explain which territory it was
        # scoped to after that territory is retired.
        "territories": (
            Territory.objects.filter(tenant=tenant).order_by("name")
            if tenant is not None
            else Territory.objects.none()
        ),
    }


@login_required
def sales_plan_cycle_list(request):
    stats = _cycle_queryset(request).aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(status="active")),
        closed=Count("id", filter=Q(status="closed")),
        with_goals=Count("id", filter=Q(goals__isnull=False)),
    )
    return crud_list(
        request,
        _cycle_queryset(request).annotate(_goal_count=Count("goals", distinct=True)),
        LIST_TEMPLATE,
        search_fields=["number", "name", "notes"],
        filters=[
            ("cadence", "cadence", False),
            ("status", "status", False),
            ("suggestion_mode", "suggestion_mode", False),
            ("owner", "owner_id", True),
            ("territory", "territory_id", True),
        ],
        extra_context={
            "page_size": PAGE_SIZE,
            **_choice_context(request),
            "stats": stats,
        },
        per_page=PAGE_SIZE,
    )


@tenant_admin_required
def sales_plan_cycle_create(request):
    return crud_create(
        request,
        form_class=SalesPlanCycleForm,
        template=FORM_TEMPLATE,
        success_url=reverse("sales:sales_plan_cycle_list"),
        extra_context=_choice_context(request),
    )


@login_required
def sales_plan_cycle_detail(request, pk):
    obj = get_object_or_404(_cycle_queryset(request), pk=pk)
    goals = list(obj.goals.all())
    today = timezone.localdate()
    # A CLOSED cycle reports the same numbers forever (its window is in the past either way);
    # an OPEN one is counted as-of today, so a plan that has not finished does not report activity
    # from the future as if it had already happened.
    as_of = None if obj.status == "closed" else today
    progress_rows = [
        {"goal": goal, "actual": actual, "target": target, "percent": percent}
        for goal, (actual, target, percent) in (
            (goal, obj.progress_for(goal, as_of=as_of)) for goal in goals
        )
    ]
    open_tasks = (
        CrmTask.objects.filter(
            tenant=obj.tenant,
            status__in=CrmTask.OPEN_STATUSES,
            due_date__gte=obj.period_start,
            due_date__lte=obj.period_end,
        )
        .select_related("party", "related_opportunity")
        .order_by("due_date", "-pk")[:MAX_DETAIL_TASKS]
        if obj.period_start and obj.period_end
        else CrmTask.objects.none()
    )
    upcoming_events = (
        CalendarEvent.objects.filter(
            tenant=obj.tenant,
            status__in=["scheduled", "confirmed"],
            start__gte=timezone.now(),
            start__lte=obj.period_end,
        )
        .select_related("party", "owner")
        .order_by("start", "pk")[:MAX_DETAIL_EVENTS]
        if obj.period_end
        else CalendarEvent.objects.none()
    )
    caveats = []
    if obj.cadence == "daily" and obj.period_start and obj.period_end and obj.period_end != obj.period_start:
        caveats.append(
            "This is a daily plan whose window spans more than one day, which the model refuses on save."
        )
    if obj.weekly_period_is_not_a_week:
        caveats.append(
            "This is a weekly plan whose window is not seven days, which the model refuses on save."
        )
    return render(request, DETAIL_TEMPLATE, {
        "obj": obj,
        "goals": goals,
        "progress_rows": progress_rows,
        "actuals": {row["goal"].metric: row["actual"] for row in progress_rows},
        "open_tasks": open_tasks,
        "open_task_cap": MAX_DETAIL_TASKS,
        "upcoming_events": upcoming_events,
        "event_cap": MAX_DETAIL_EVENTS,
        "can_close": obj.status != "closed",
        "caveats": caveats,
        "goal_form": ActivityGoalForm(),
        **_choice_context(request),
    })


@tenant_admin_required
def sales_plan_cycle_edit(request, pk):
    return crud_edit(
        request,
        model=SalesPlanCycle,
        pk=pk,
        form_class=SalesPlanCycleForm,
        template=FORM_TEMPLATE,
        success_url=reverse("sales:sales_plan_cycle_detail", args=[pk]),
        extra_context=_choice_context(request),
    )


@require_POST
@login_required
@tenant_admin_required
def sales_plan_cycle_delete(request, pk):
    obj = get_object_or_404(_cycle_queryset(request), pk=pk)
    goal_count = obj.goals.count()
    with transaction.atomic():
        locked = SalesPlanCycle.objects.select_for_update().get(pk=obj.pk, tenant=request.tenant)
        write_audit_log(
            request.user,
            locked,
            "delete",
            {
                "action": "sales_plan_cycle",
                "name": locked.name,
                "cadence": locked.cadence,
                "period_start": str(locked.period_start),
                "period_end": str(locked.period_end),
                "goals": goal_count,
            },
            tenant=request.tenant,
        )
        # Goals cascade. The ACTIVITIES and TASKS the cycle counted are untouched — they belong to
        # 8.8's register and CRM 1.5's, and deleting a plan must never delete a rep's work.
        locked.delete()
    messages.success(
        request,
        f"Plan cycle {obj.number} deleted. Its goals went with it; the logged activities did not.",
    )
    return redirect("sales:sales_plan_cycle_list")


@require_POST
@login_required
@tenant_admin_required
def sales_plan_cycle_toggle(request, pk):
    """Close or re-open a cycle. POST-only: a GET link must never move a period's status."""
    obj = get_object_or_404(_cycle_queryset(request), pk=pk)
    with transaction.atomic():
        locked = SalesPlanCycle.objects.select_for_update().get(pk=obj.pk, tenant=request.tenant)
        locked.status = "draft" if locked.status == "closed" else "closed"
        # `closed_at` is stamped/cleared by the model's own save(), on the TRANSITION. Handing it a
        # value here would put a system-set column back under the view's control.
        locked.save()
        write_audit_log(
            request.user,
            locked,
            "update",
            {
                "action": "sales_plan_cycle_toggle",
                "name": locked.name,
                "status": locked.status,
                "closed_at": locked.closed_at.isoformat() if locked.closed_at else None,
            },
            tenant=locked.tenant,
        )
    messages.success(
        request,
        f"{locked.name} is now {locked.get_status_display().lower()}.",
    )
    return redirect("sales:sales_plan_cycle_detail", pk=obj.pk)


@require_POST
@login_required
@tenant_admin_required
def sales_plan_goal_add(request, pk):
    """Add one activity goal to a cycle. POST-only and audited like every other write."""
    cycle = get_object_or_404(_cycle_queryset(request), pk=pk)
    if cycle.status == "closed":
        messages.error(request, "This cycle is closed, so its goals can no longer be changed.")
        return redirect("sales:sales_plan_cycle_detail", pk=cycle.pk)
    form = ActivityGoalForm(request.POST)
    if form.is_valid():
        metric = form.cleaned_data["metric"]
        # G15 — one goal per (cycle, metric). `update_or_create` rather than a bare create() so a
        # duplicate POST revises the target instead of losing to a unique constraint as a 500.
        goal, created = ActivityGoal.objects.update_or_create(
            tenant=cycle.tenant,
            cycle=cycle,
            metric=metric,
            defaults={"target_count": form.cleaned_data["target_count"]},
        )
        write_audit_log(
            request.user,
            goal,
            "create" if created else "update",
            {
                "action": "activity_goal",
                "cycle": cycle.name,
                "metric": metric,
                "target_count": goal.target_count,
            },
            tenant=cycle.tenant,
        )
        messages.success(
            request,
            f"{'Added' if created else 'Updated'} the {goal.get_metric_display().lower()} goal.",
        )
    else:
        for message in form.errors.get("__all__", []) + [
            error for errors in form.errors.values() for error in errors
        ]:
            messages.error(request, str(message))
    return redirect("sales:sales_plan_cycle_detail", pk=cycle.pk)


@require_POST
@login_required
@tenant_admin_required
def sales_plan_goal_delete(request, pk, goal_pk):
    """Remove one goal. The cycle's activities are untouched — a goal is a target, not a record."""
    cycle = get_object_or_404(_cycle_queryset(request), pk=pk)
    goal = get_object_or_404(ActivityGoal, pk=goal_pk, tenant=cycle.tenant, cycle=cycle)
    write_audit_log(
        request.user,
        goal,
        "delete",
        {"action": "activity_goal", "cycle": cycle.name, "metric": goal.metric,
         "target_count": goal.target_count},
        tenant=cycle.tenant,
    )
    goal.delete()
    messages.success(request, f"Removed the {goal.get_metric_display().lower()} goal.")
    return redirect("sales:sales_plan_cycle_detail", pk=cycle.pk)