"""Sales 8.13 — Views for `MqlHandoff` (the marketing-to-sales handoff)."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, F, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.models import User
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.crm.models import Campaign
from apps.sales.forms.MarketingAlignment.MqlHandoffs import MqlHandoffForm
from apps.sales.models.MarketingAlignment.MqlHandoffs import (
    HANDOFF_SOURCE_CHOICES,
    HANDOFF_STATUS_CHOICES,
    MqlHandoff,
)


@login_required
def mql_handoff_list(request):
    qs = (
        MqlHandoff.objects.filter(tenant=request.tenant)
        .select_related("lead", "campaign", "account", "owner", "assigned_to", "opportunity", "currency")
        .order_by("-handoff_at", "-created_at")
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(lead__name__icontains=q)
            | Q(lead__number__icontains=q)
            | Q(account__name__icontains=q)
            | Q(number__icontains=q)
        )

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    source_kind = request.GET.get("source_kind", "").strip()
    if source_kind:
        qs = qs.filter(source_kind=source_kind)

    campaign_id = request.GET.get("campaign", "").strip()
    if campaign_id and campaign_id.isdigit():
        qs = qs.filter(campaign_id=int(campaign_id))

    owner_id = request.GET.get("owner", "").strip()
    if owner_id and owner_id.isdigit():
        qs = qs.filter(owner_id=int(owner_id))

    now = timezone.now()
    # A breach is either "answered late" or "still unanswered past the deadline". Both halves
    # are expressible in SQL, so the count never loads the rows.
    stats = qs.aggregate(
        total_count=Count("id"),
        pending_count=Count("id", filter=Q(status="pending")),
        accepted_count=Count("id", filter=Q(status="accepted")),
        rejected_count=Count("id", filter=Q(status="rejected")),
        expired_count=Count("id", filter=Q(status="expired")),
        converted_count=Count("id", filter=Q(status="converted")),
        sla_breach_count=Count(
            "id",
            filter=Q(responded_at__isnull=False, responded_at__gt=F("sla_due_at"))
            | Q(status="pending", sla_due_at__lt=now),
        ),
    )
    decided_count = stats["accepted_count"] + stats["rejected_count"]
    stats["acceptance_rate_pct"] = (
        round(stats["accepted_count"] / decided_count * 100, 1) if decided_count else None
    )

    # Average response time is computed in Python over the responded handoffs only. A portable
    # SQL duration expression differs between MySQL and SQLite, and this runs on both; the
    # responded subset is bounded by real sales activity, not by the row count of the table.
    response_pairs = list(
        qs.filter(responded_at__isnull=False).values_list("responded_at", "handoff_at")
    )
    response_hours = [
        (responded - handed).total_seconds() / 3600
        for responded, handed in response_pairs
        if responded is not None and handed is not None
    ]
    stats["avg_response_hours"] = (
        round(sum(response_hours) / len(response_hours), 2) if response_hours else None
    )

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    campaigns = Campaign.objects.filter(tenant=request.tenant).order_by("name")
    owners = User.objects.filter(tenant=request.tenant).order_by("username")

    context = {
        "page_obj": page_obj,
        "handoffs": page_obj.object_list,
        "status_choices": HANDOFF_STATUS_CHOICES,
        "source_choices": HANDOFF_SOURCE_CHOICES,
        "campaigns": campaigns,
        "owners": owners,
        "active_filters": {
            "q": q,
            "status": status,
            "source_kind": source_kind,
            "campaign": campaign_id,
            "owner": owner_id,
        },
        "stats": stats,
    }
    return render(
        request,
        "sales/marketingalignment/mqlhandoff/list.html",
        context,
    )


@login_required
def mql_handoff_detail(request, pk):
    obj = get_object_or_404(
        MqlHandoff.objects.filter(tenant=request.tenant).select_related(
            "lead", "campaign", "account", "owner", "assigned_to", "opportunity", "currency"
        ),
        pk=pk,
    )
    return render(
        request,
        "sales/marketingalignment/mqlhandoff/detail.html",
        {"obj": obj, "handoff": obj},
    )


@login_required
def mql_handoff_create(request):
    if request.method == "POST":
        form = MqlHandoffForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save()
            write_audit_log(
                request.user,
                obj,
                "create",
                f"Created MQL handoff {obj.number} for lead "
                f"{obj.lead.name if obj.lead_id else 'unknown'}",
                tenant=request.tenant,
            )
            messages.success(request, f"MQL handoff {obj.number} created successfully.")
            return redirect("sales:mql_handoff_detail", pk=obj.pk)
    else:
        form = MqlHandoffForm(tenant=request.tenant)

    return render(
        request,
        "sales/marketingalignment/mqlhandoff/form.html",
        {"form": form, "obj": None, "is_edit": False},
    )


@login_required
def mql_handoff_edit(request, pk):
    obj = get_object_or_404(
        MqlHandoff.objects.filter(tenant=request.tenant),
        pk=pk,
    )
    if request.method == "POST":
        form = MqlHandoffForm(request.POST, instance=obj, tenant=request.tenant)
        if form.is_valid():
            obj = form.save()
            write_audit_log(
                request.user,
                obj,
                "update",
                f"Updated MQL handoff {obj.number} (status: {obj.get_status_display()})",
                tenant=request.tenant,
            )
            messages.success(request, f"MQL handoff {obj.number} updated successfully.")
            return redirect("sales:mql_handoff_detail", pk=obj.pk)
    else:
        form = MqlHandoffForm(instance=obj, tenant=request.tenant)

    return render(
        request,
        "sales/marketingalignment/mqlhandoff/form.html",
        {"form": form, "obj": obj, "is_edit": True},
    )


@require_POST
@tenant_admin_required
def mql_handoff_delete(request, pk):
    obj = get_object_or_404(
        MqlHandoff.objects.filter(tenant=request.tenant),
        pk=pk,
    )
    number = obj.number
    write_audit_log(
        request.user,
        obj,
        "delete",
        f"Deleted MQL handoff {number}",
        tenant=request.tenant,
    )
    obj.delete()
    messages.success(request, f"MQL handoff {number} deleted.")
    return redirect("sales:mql_handoff_list")
