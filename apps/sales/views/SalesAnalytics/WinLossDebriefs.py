"""Sales 8.12 — Views for `WinLossDebrief`.

Function-based views over the 8.12 Win/Loss Debrief record. Every queryset is
tenant-scoped, every write is audit-logged, and every integer FK filter is
guarded by ``_pk_filter`` (``.isdigit()`` plus a 64-bit range bound) so a
hand-edited URL is ignored rather than a 500 (L11).
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.accounts.models import User
from apps.core.decorators import tenant_admin_required
from apps.core.models import Party
from apps.core.utils import write_audit_log
from apps.crm.models import Opportunity
from apps.sales.forms.SalesAnalytics.WinLossDebriefs import WinLossDebriefForm
from apps.sales.models.OpportunityOutcomes.OpportunityOutcomes import (
    OpportunityOutcome,
    WinLossReason,
)
from apps.sales.models.SalesAnalytics.WinLossDebriefs import (
    DEBRIEF_STATUS_CHOICES,
    FEEDBACK_TEAM_CHOICES,
    INTERVIEW_CHANNEL_CHOICES,
    WinLossDebrief,
)
from apps.sales.views.SalesAnalytics._helpers import _pk_filter


@login_required
def win_loss_debrief_list(request):
    qs = WinLossDebrief.objects.filter(tenant=request.tenant).select_related(
        "opportunity",
        "account",
        "primary_reason",
        "interviewer",
        "action_owner",
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(opportunity__name__icontains=q)
            | Q(number__icontains=q)
            | Q(buyer_quote__icontains=q)
            | Q(action_items__icontains=q)
            | Q(notes__icontains=q)
        )

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    interview_channel = request.GET.get("interview_channel", "").strip()
    if interview_channel:
        qs = qs.filter(interview_channel=interview_channel)

    feedback_team = request.GET.get("feedback_team", "").strip()
    if feedback_team:
        qs = qs.filter(feedback_team=feedback_team)

    opportunity_id = request.GET.get("opportunity", "").strip()
    opportunity_pk = _pk_filter(opportunity_id)
    if opportunity_pk is not None:
        qs = qs.filter(opportunity_id=opportunity_pk)

    reason_id = request.GET.get("reason", "").strip()
    reason_pk = _pk_filter(reason_id)
    if reason_pk is not None:
        qs = qs.filter(primary_reason_id=reason_pk)

    stats = qs.aggregate(
        total_count=Count("id"),
        open_count=Count("id", filter=Q(status__in=["draft", "submitted", "shared"])),
        actioned_count=Count("id", filter=Q(status="actioned")),
        closed_count=Count("id", filter=Q(status="closed")),
    )

    paginator = Paginator(qs, 15)
    page_obj = paginator.get_page(request.GET.get("page"))

    opportunities = (
        Opportunity.objects.filter(tenant=request.tenant).only("id", "name").order_by("name")
    )
    reasons = WinLossReason.objects.filter(tenant=request.tenant, is_active=True).order_by(
        "sequence", "name"
    )

    context = {
        "debriefs": page_obj.object_list,
        "page_obj": page_obj,
        "q": q,
        "status_choices": DEBRIEF_STATUS_CHOICES,
        "interview_channel_choices": INTERVIEW_CHANNEL_CHOICES,
        "feedback_team_choices": FEEDBACK_TEAM_CHOICES,
        "opportunities": opportunities,
        "reasons": reasons,
        "stats": stats,
        "active_filters": {
            "q": q,
            "status": status,
            "interview_channel": interview_channel,
            "feedback_team": feedback_team,
            "opportunity": opportunity_id,
            "reason": reason_id,
        },
    }
    return render(request, "sales/salesanalytics/winlossdebrief/list.html", context)


@login_required
def win_loss_debrief_detail(request, pk):
    obj = get_object_or_404(
        WinLossDebrief.objects.filter(tenant=request.tenant).select_related(
            "opportunity",
            "outcome",
            "primary_reason",
            "account",
            "interviewer",
            "action_owner",
            "communication_log",
        ),
        pk=pk,
    )
    return render(
        request,
        "sales/salesanalytics/winlossdebrief/detail.html",
        {"obj": obj, "debrief": obj},
    )


@tenant_admin_required
def win_loss_debrief_create(request):
    if request.method == "POST":
        form = WinLossDebriefForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save()
            write_audit_log(
                request.user,
                obj,
                "create",
                f"Recorded win/loss debrief {obj.number} for {obj.opportunity}",
                tenant=request.tenant,
            )
            messages.success(request, f"Win/loss debrief {obj.number} created successfully.")
            return redirect("sales:win_loss_debrief_detail", pk=obj.pk)
    else:
        form = WinLossDebriefForm(tenant=request.tenant)

    return render(
        request,
        "sales/salesanalytics/winlossdebrief/form.html",
        {"form": form, "obj": None, "is_edit": False},
    )


@tenant_admin_required
def win_loss_debrief_edit(request, pk):
    obj = get_object_or_404(
        WinLossDebrief.objects.filter(tenant=request.tenant),
        pk=pk,
    )
    if request.method == "POST":
        form = WinLossDebriefForm(request.POST, instance=obj, tenant=request.tenant)
        if form.is_valid():
            obj = form.save()
            write_audit_log(
                request.user,
                obj,
                "update",
                f"Updated win/loss debrief {obj.number} for {obj.opportunity}",
                tenant=request.tenant,
            )
            messages.success(request, f"Win/loss debrief {obj.number} updated successfully.")
            return redirect("sales:win_loss_debrief_detail", pk=obj.pk)
    else:
        form = WinLossDebriefForm(instance=obj, tenant=request.tenant)

    return render(
        request,
        "sales/salesanalytics/winlossdebrief/form.html",
        {"form": form, "obj": obj, "is_edit": True},
    )


@require_POST
@tenant_admin_required
def win_loss_debrief_delete(request, pk):
    obj = get_object_or_404(
        WinLossDebrief.objects.filter(tenant=request.tenant),
        pk=pk,
    )
    number = obj.number
    opportunity_name = str(obj.opportunity) if obj.opportunity_id else "—"
    write_audit_log(
        request.user,
        obj,
        "delete",
        f"Deleted win/loss debrief {number} for {opportunity_name}",
        tenant=request.tenant,
    )
    obj.delete()
    messages.success(request, f"Win/loss debrief {number} deleted.")
    return redirect("sales:win_loss_debrief_list")
