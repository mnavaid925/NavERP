"""Sales 8.14 — Views for `ChannelConflict`."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.models import Party
from apps.core.utils import write_audit_log
from apps.sales.forms.PartnerChannel.ChannelConflicts import ChannelConflictForm
from apps.sales.models.PartnerChannel.ChannelConflicts import (
    CONFLICT_STATUS_CHOICES,
    CONFLICT_TYPE_CHOICES,
    ESCALATION_LEVEL_CHOICES,
    ChannelConflict,
)


@login_required
def channel_conflict_list(request):
    qs = (
        ChannelConflict.objects.filter(tenant=request.tenant)
        .select_related(
            "claimant_partner",
            "competing_partner",
            "client_account",
            "direct_sales_rep",
            "territory",
            "escalated_to",
            "resolved_by",
        )
        .order_by("-created_at")
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(claimant_partner__name__icontains=q)
            | Q(client_account__name__icontains=q)
            | Q(description__icontains=q)
            | Q(resolution_rationale__icontains=q)
        )

    conflict_type = request.GET.get("conflict_type", "").strip()
    if conflict_type:
        qs = qs.filter(conflict_type=conflict_type)

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    escalation_level = request.GET.get("escalation_level", "").strip()
    if escalation_level:
        qs = qs.filter(escalation_level=escalation_level)

    stats = qs.aggregate(
        total_count=Count("id"),
        open_count=Count("id", filter=Q(status__in=["open", "in_mediation"])),
        resolved_count=Count("id", filter=Q(status="resolved")),
        escalated_count=Count("id", filter=Q(status="escalated")),
    )

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "conflicts": page_obj.object_list,
        "conflict_type_choices": CONFLICT_TYPE_CHOICES,
        "status_choices": CONFLICT_STATUS_CHOICES,
        "escalation_level_choices": ESCALATION_LEVEL_CHOICES,
        "stats": stats,
        "q": q,
        "selected_type": conflict_type,
        "selected_status": status,
        "selected_level": escalation_level,
    }
    return render(request, "sales/partnerchannel/channelconflict/list.html", context)


@login_required
def channel_conflict_detail(request, pk):
    conflict = get_object_or_404(
        ChannelConflict.objects.filter(tenant=request.tenant).select_related(
            "claimant_partner",
            "competing_partner",
            "client_account",
            "direct_sales_rep",
            "territory",
            "deal_registration",
            "opportunity",
            "escalated_to",
            "resolved_by",
        ),
        pk=pk,
    )

    context = {
        "conflict": conflict,
    }
    return render(request, "sales/partnerchannel/channelconflict/detail.html", context)


@login_required
def channel_conflict_create(request):
    if request.method == "POST":
        form = ChannelConflictForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                obj = form.save(commit=False)
                obj.tenant = request.tenant
                obj.save()
                # If linked to deal registration, flag registration as conflicted
                if obj.deal_registration:
                    obj.deal_registration.is_conflicted = True
                    obj.deal_registration.conflict_summary = f"Conflict {obj.number} filed: {obj.get_conflict_type_display()}"
                    obj.deal_registration.save(update_fields=["is_conflicted", "conflict_summary", "updated_at"])

                write_audit_log(
                    tenant=request.tenant,
                    user=request.user,
                    action="create",
                    model_name="ChannelConflict",
                    object_id=str(obj.pk),
                    details=f"Filed channel conflict {obj.number} — {obj.get_conflict_type_display()}",
                )
            messages.success(request, f"Channel conflict dispute {obj.number} filed successfully.")
            return redirect("sales:channel_conflict_detail", pk=obj.pk)
    else:
        form = ChannelConflictForm(tenant=request.tenant)

    return render(request, "sales/partnerchannel/channelconflict/form.html", {"form": form, "is_edit": False})


@login_required
def channel_conflict_edit(request, pk):
    obj = get_object_or_404(ChannelConflict.objects.filter(tenant=request.tenant), pk=pk)
    if request.method == "POST":
        form = ChannelConflictForm(request.POST, instance=obj, tenant=request.tenant)
        if form.is_valid():
            ccf = form.save(commit=False)
            if ccf.status == "resolved" and not ccf.resolved_at:
                ccf.resolved_at = timezone.now()
                ccf.resolved_by = request.user
            ccf.save()

            write_audit_log(
                tenant=request.tenant,
                user=request.user,
                action="update",
                model_name="ChannelConflict",
                object_id=str(obj.pk),
                details=f"Updated channel conflict {obj.number} (Status: {obj.get_status_display()})",
            )
            messages.success(request, f"Channel conflict {obj.number} updated successfully.")
            return redirect("sales:channel_conflict_detail", pk=obj.pk)
    else:
        form = ChannelConflictForm(instance=obj, tenant=request.tenant)

    return render(
        request,
        "sales/partnerchannel/channelconflict/form.html",
        {"form": form, "conflict": obj, "is_edit": True},
    )


@require_POST
@login_required
@tenant_admin_required
def channel_conflict_delete(request, pk):
    obj = get_object_or_404(ChannelConflict.objects.filter(tenant=request.tenant), pk=pk)
    number = obj.number
    obj.delete()
    write_audit_log(
        tenant=request.tenant,
        user=request.user,
        action="delete",
        model_name="ChannelConflict",
        object_id=str(pk),
        details=f"Deleted channel conflict {number}",
    )
    messages.success(request, f"Channel conflict dispute {number} deleted successfully.")
    return redirect("sales:channel_conflict_list")
