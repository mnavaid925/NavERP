"""Sales 8.8 — the sales activity register, its CRUD, and the two POST engagement verbs.

**THE THREE VERBS ARE THE POINT OF THE FROZEN FIELDS.** ``activity_log_mark_opened`` and
``activity_log_mark_clicked`` are the only writers of ``opened_at`` / ``open_count`` / ``clicked_at`` /
``click_count``, and the reply stamp on the detail POST writes ``replied_at``. All three are
``@require_POST`` so a prefetch, a crawler or a link preview cannot move a rep's engagement numbers
by touching a URL. All three go through ``ActivityLog.advance_email_engagement``, which is
**monotonic**: it increments and first-stamps, and never decrements or clears, so "was it ever
opened" cannot be un-answered by a later non-click event.

They are also the reason the engagement figures are trustworthy. A rep cannot reach these numbers
through a form (L20/L22), so the only way a row's counters move is a deliberate, audited action.
"""
from datetime import timedelta

from django.db import transaction
from django.db.models import Count, Q
from django.urls import reverse
from django.utils import timezone

from apps.crm.models import CommunicationLog, Opportunity, Territory
from apps.core.models import Party
from apps.core.utils import write_audit_log
from apps.sales.forms.SalesActivityTaskManagement.ActivityLogs import (
    SELECTABLE_CAPTURE_SOURCES,
    ActivityLogForm,
)
from apps.sales.forms._common import tenant_users
from apps.sales.models.SalesActivityTaskManagement.ActivityLogs import ActivityLog
from apps.sales.models.SalesActivityTaskManagement.ActivityTypes import ActivityType
from apps.sales.models.SalesActivityTaskManagement.SalesPlanCycles import SalesPlanCycle
from apps.sales.views._common import *

LIST_TEMPLATE = "sales/salesactivitytaskmanagement/activitylog/list.html"
DETAIL_TEMPLATE = "sales/salesactivitytaskmanagement/activitylog/detail.html"
FORM_TEMPLATE = "sales/salesactivitytaskmanagement/activitylog/form.html"

PAGE_SIZE = 15


def _log_queryset(request):
    return ActivityLog.objects.filter(tenant=request.tenant).select_related(
        "communication_log", "activity_type", "owner", "opportunity", "account", "territory",
    )


def _choice_context(request):
    """Every dropdown the list, the create form and the edit form all need.

    All of these are passed to create/edit as well as to list: a form whose dropdown is NARROWER
    than the filter bar is a filter bar that silently hides rows (L54's third rule, one level down).
    """
    tenant = request.tenant
    return {
        "capture_source_choices": SELECTABLE_CAPTURE_SOURCES,
        "owners": tenant_users(tenant).order_by("username"),
        # ALL of the tenant's territories, retired included: a retired territory still explains a
        # historical row, and a register that hides those rows hides its own history.
        "territories": (
            Territory.objects.filter(tenant=tenant).order_by("name")
            if tenant is not None
            else Territory.objects.none()
        ),
        "activity_types": ActivityType.objects.filter(tenant=tenant).order_by("display_order", "name"),
        "opportunities": (
            Opportunity.objects.filter(tenant=tenant).select_related("account").order_by("name")
            if tenant is not None
            else Opportunity.objects.none()
        ),
        "accounts": _tenant_accounts(tenant),
    }


def _tenant_accounts(tenant):
    """The tenant's ORGANISATION parties — the accounts an activity can be about.

    ``kind="organization"`` is the same filter 8.7's territory boards use, and the same one
    `TaskTemplate.generate` uses to walk an account book. Filtering on it here means the account
    dropdown and the generation walk can never disagree about what an account is.
    """
    if tenant is None:
        return Party.objects.none()
    return Party.objects.filter(tenant=tenant, kind="organization").order_by("name")


def _attributable_logs(tenant, keep_pk=None):
    """The CRM 1.5 interactions this form may attribute: the unattributed ones, plus ``keep_pk``.

    Written as an explicit OR of two **positively filtered, tenant-scoped** querysets rather than
    `qs.exclude(sales_activity_logs__tenant=t) | qs.filter(pk=…)` for two reasons.

    * An `exclude()` produces `NOT (EXISTS …)`, and `NOT` does not distribute over `|` the way the
      reading suggests — `A OR NOT B` is not `NOT (A OR B)`, so the join-based exclude and the OR
      combine into something other than what it says.
    * The operand carrying the kept pk MUST be tenant-filtered too. Writing it as
      `CommunicationLog.objects.filter(pk=keep_pk)` with no tenant would hand the edit form another
      workspace's interactions on a guessed pk.

    ``keep_pk`` exists because on EDIT the instance's own log is already attributed: excluding it
    would leave the field's only valid choice unselectable and fail every save with
    "Select a valid choice" (L54's fifth rule, inverted).
    """
    if tenant is None:
        return CommunicationLog.objects.none()
    base = CommunicationLog.objects.filter(tenant=tenant)
    attributed = ActivityLog.objects.filter(tenant=tenant).values("communication_log_id")
    unattributed = base.exclude(pk__in=attributed)
    if keep_pk:
        unattributed = unattributed | base.filter(pk=keep_pk)
    return unattributed.order_by("-occurred_at")


@login_required
def activity_log_list(request):
    """The sales activity register: search, six GET filters, engagement columns."""
    stats = _log_queryset(request).aggregate(
        total=Count("id"),
        auto_captured=Count("id", filter=Q(is_auto_captured=True)),
        opened=Count("id", filter=Q(open_count__gt=0)),
        clicked=Count("id", filter=Q(click_count__gt=0)),
        replied=Count("id", filter=Q(replied_at__isnull=False)),
        with_next_step=Count("id", filter=Q(next_best_action__gt="")),
    )
    return crud_list(
        request,
        _log_queryset(request),
        LIST_TEMPLATE,
        search_fields=["number", "next_best_action"],
        filters=[
            ("capture_source", "capture_source", False),
            ("owner", "owner_id", True),
            ("opportunity", "opportunity_id", True),
            ("territory", "territory_id", True),
            ("activity_type", "activity_type_id", True),
            ("account", "account_id", True),
        ],
        extra_context={
            "page_size": PAGE_SIZE,
            **_choice_context(request),
            "stats": stats,
        },
        per_page=PAGE_SIZE,
    )


@tenant_admin_required
def activity_log_create(request):
    """Create the sales attribution, and stamp the two frozen columns on first save.

    The form saves via ``crud_create``, which calls ``obj.save()`` — and ``ActivityLog.save()`` is
    what fills ``occurred_on`` and ``planned_minutes``. Those columns are therefore written by the
    MODEL, not this view, so a seeder, a management command and this view all get the same values.
    """
    return crud_create(
        request,
        form_class=ActivityLogForm,
        template=FORM_TEMPLATE,
        success_url=reverse("sales:activity_log_list"),
        extra_context={
            **_choice_context(request),
            "communication_logs": _attributable_logs(request.tenant),
        },
    )


@login_required
def activity_log_detail(request, pk):
    obj = get_object_or_404(_log_queryset(request), pk=pk)
    # The plan cycles this activity actually lands inside. `occurred_on` is DENORMALISED onto the
    # row precisely so this is a date-range filter on an indexed column rather than a per-row
    # timezone conversion off the CRM log.
    goals_hit = SalesPlanCycle.objects.filter(
        tenant=request.tenant,
        period_start__lte=obj.occurred_on,
        period_end__gte=obj.occurred_on,
    ).select_related("owner")[:25] if obj.occurred_on else SalesPlanCycle.objects.none()
    caveats = []
    if obj.communication_log_id and not obj.communication_log.tenant_id == request.tenant.pk:
        caveats.append("The underlying interaction is not in this workspace.")
    if obj.activity_type_id and obj.activity_type.requires_opportunity and not obj.opportunity_id:
        caveats.append(
            "This activity's type requires an opportunity and none is named, which the model refuses "
            "on save."
        )
    return render(request, DETAIL_TEMPLATE, {
        "obj": obj,
        "communication_log": obj.communication_log if obj.communication_log_id else None,
        "goals_hit": goals_hit,
        "caveats": caveats,
    })


@tenant_admin_required
def activity_log_edit(request, pk):
    obj = get_object_or_404(_log_queryset(request), pk=pk)
    return crud_edit(
        request,
        model=ActivityLog,
        pk=pk,
        form_class=ActivityLogForm,
        template=FORM_TEMPLATE,
        success_url=reverse("sales:activity_log_detail", args=[pk]),
        extra_context={
            **_choice_context(request),
            "communication_logs": _attributable_logs(request.tenant, keep_pk=obj.communication_log_id),
        },
    )


@require_POST
@login_required
@tenant_admin_required
def activity_log_delete(request, pk):
    obj = get_object_or_404(_log_queryset(request), pk=pk)
    with transaction.atomic():
        locked = ActivityLog.objects.select_for_update().get(pk=obj.pk, tenant=request.tenant)
        write_audit_log(
            request.user,
            locked,
            "delete",
            {
                "action": "activity_log",
                "channel": locked.channel,
                "occurred_on": str(locked.occurred_on) if locked.occurred_on else None,
                "open_count": locked.open_count,
                "click_count": locked.click_count,
                "replied": bool(locked.replied_at),
            },
            tenant=request.tenant,
        )
        locked.delete()
    messages.success(request, "Sales activity deleted.")
    return redirect("sales:activity_log_list")


def _advance(request, pk, **signals):
    """Shared body of the two engagement verbs. POST-only, tenant-scoped, audited, transactional."""
    obj = get_object_or_404(_log_queryset(request), pk=pk)
    with transaction.atomic():
        locked = ActivityLog.objects.select_for_update().get(pk=obj.pk, tenant=request.tenant)
        changed = locked.advance_email_engagement(**signals)
        if not changed:
            # Nothing moved — a count-only call still changes the counter, so this is only reachable
            # when a caller passes no signal at all. Answer it honestly rather than claiming success.
            messages.warning(request, "That activity was not marked.")
            return redirect("sales:activity_log_detail", pk=obj.pk)
        locked.save(update_fields=set(changed) | {"updated_at"})
        write_audit_log(
            request.user,
            locked,
            "update",
            {
                "action": "activity_engagement",
                "signals": sorted(k for k in signals if signals[k]),
                "fields": sorted(changed),
                "engagement_level": locked.engagement_level,
                "open_count": locked.open_count,
                "click_count": locked.click_count,
            },
            tenant=request.tenant,
        )
    messages.success(
        request,
        f"Activity {locked.number} marked {locked.engagement_label.lower()}.",
    )
    return redirect("sales:activity_log_detail", pk=obj.pk)


@require_POST
@login_required
def activity_log_mark_opened(request, pk):
    """Mark the underlying email opened. One of only three writers of the frozen counters."""
    return _advance(request, pk, opened=True)


@require_POST
@login_required
def activity_log_mark_clicked(request, pk):
    """Mark the underlying email clicked. The counters only ever move up from here."""
    return _advance(request, pk, clicked=True)


@require_POST
@login_required
def activity_log_mark_replied(request, pk):
    """Mark the underlying email replied. Also the only writer of ``replied_at``."""
    return _advance(request, pk, replied=True)