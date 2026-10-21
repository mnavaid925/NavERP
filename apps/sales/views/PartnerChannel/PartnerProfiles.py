"""Sales 8.14 — Views for `PartnerProfile` and Partner Performance Console."""
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.models import User
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.sales.forms.PartnerChannel.PartnerProfiles import PartnerProfileForm
from apps.sales.models.PartnerChannel.PartnerProfiles import (
    ONBOARDING_STATUS_CHOICES,
    PARTNER_TIER_CHOICES,
    PARTNER_TYPE_CHOICES,
    PartnerProfile,
)


@login_required
def partner_profile_list(request):
    qs = (
        PartnerProfile.objects.filter(tenant=request.tenant)
        .select_related("partner", "channel_manager", "authorized_territory", "currency")
        .order_by("-actual_revenue_ytd", "partner__name")
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(partner__name__icontains=q)
            | Q(number__icontains=q)
            | Q(channel_manager__first_name__icontains=q)
            | Q(channel_manager__last_name__icontains=q)
            | Q(notes__icontains=q)
        )

    partner_type = request.GET.get("partner_type", "").strip()
    if partner_type:
        qs = qs.filter(partner_type=partner_type)

    onboarding_status = request.GET.get("onboarding_status", "").strip()
    if onboarding_status:
        qs = qs.filter(onboarding_status=onboarding_status)

    tier = request.GET.get("tier", "").strip()
    if tier:
        qs = qs.filter(tier=tier)

    cam_id = request.GET.get("channel_manager", "").strip()
    if cam_id and cam_id.isdigit():
        qs = qs.filter(channel_manager_id=int(cam_id))

    stats = qs.aggregate(
        total_count=Count("id"),
        active_count=Count("id", filter=Q(onboarding_status="active")),
        total_revenue=Sum("actual_revenue_ytd"),
        avg_target=Avg("annual_revenue_target"),
    )

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    channel_managers = (
        User.objects.filter(tenant=request.tenant, is_active=True)
        .order_by("first_name", "last_name")
    )

    context = {
        "page_obj": page_obj,
        "partner_profiles": page_obj.object_list,
        "partner_type_choices": PARTNER_TYPE_CHOICES,
        "onboarding_status_choices": ONBOARDING_STATUS_CHOICES,
        "tier_choices": PARTNER_TIER_CHOICES,
        "channel_managers": channel_managers,
        "stats": stats,
        "q": q,
        "selected_type": partner_type,
        "selected_status": onboarding_status,
        "selected_tier": tier,
        "selected_cam": cam_id,
    }
    return render(request, "sales/partnerchannel/partnerprofile/list.html", context)


@login_required
def partner_profile_detail(request, pk):
    partner_profile = get_object_or_404(
        PartnerProfile.objects.filter(tenant=request.tenant).select_related(
            "partner", "channel_manager", "authorized_territory", "currency", "agreement_document"
        ),
        pk=pk,
    )

    # Linked registrations, plans, and conflicts
    registrations = (
        partner_profile.partner.sales_partner_deal_registrations.filter(tenant=request.tenant)
        .select_related("customer_account", "currency")
        .order_by("-submission_date")[:10]
    )
    joint_plans = (
        partner_profile.partner.sales_partner_joint_plans.filter(tenant=request.tenant)
        .select_related("client_account", "currency")
        .order_by("-period_end")[:10]
    )
    conflicts = (
        partner_profile.partner.sales_claimed_conflicts.filter(tenant=request.tenant)
        .select_related("client_account", "direct_sales_rep")
        .order_by("-created_at")[:10]
    )

    context = {
        "partner_profile": partner_profile,
        "registrations": registrations,
        "joint_plans": joint_plans,
        "conflicts": conflicts,
    }
    return render(request, "sales/partnerchannel/partnerprofile/detail.html", context)


@login_required
def partner_profile_create(request):
    if request.method == "POST":
        form = PartnerProfileForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.save()
            write_audit_log(
                user=request.user,
                obj=obj,
                action="create",
                changes=f"Created partner profile {obj.number} for {obj.partner.name}",
                tenant=request.tenant,
            )
            messages.success(request, f"Partner profile {obj.number} created successfully.")
            return redirect("sales:partner_profile_detail", pk=obj.pk)
    else:
        form = PartnerProfileForm(tenant=request.tenant)

    return render(request, "sales/partnerchannel/partnerprofile/form.html", {"form": form, "is_edit": False})


@login_required
def partner_profile_edit(request, pk):
    obj = get_object_or_404(PartnerProfile.objects.filter(tenant=request.tenant), pk=pk)
    if request.method == "POST":
        form = PartnerProfileForm(request.POST, instance=obj, tenant=request.tenant)
        if form.is_valid():
            form.save()
            write_audit_log(
                user=request.user,
                obj=obj,
                action="update",
                changes=f"Updated partner profile {obj.number}",
                tenant=request.tenant,
            )
            messages.success(request, f"Partner profile {obj.number} updated successfully.")
            return redirect("sales:partner_profile_detail", pk=obj.pk)
    else:
        form = PartnerProfileForm(instance=obj, tenant=request.tenant)

    return render(
        request,
        "sales/partnerchannel/partnerprofile/form.html",
        {"form": form, "partner_profile": obj, "is_edit": True},
    )


@require_POST
@login_required
@tenant_admin_required
def partner_profile_delete(request, pk):
    obj = get_object_or_404(PartnerProfile.objects.filter(tenant=request.tenant), pk=pk)
    number = obj.number
    write_audit_log(
        user=request.user,
        obj=obj,
        action="delete",
        changes=f"Deleted partner profile {number}",
        tenant=request.tenant,
    )
    obj.delete()
    messages.success(request, f"Partner profile {number} deleted successfully.")
    return redirect("sales:partner_profile_list")


@login_required
def partner_performance_console(request):
    from apps.sales.models.PartnerChannel.ChannelConflicts import ChannelConflict
    from apps.sales.models.PartnerChannel.DealRegistrations import DealRegistration

    partners = PartnerProfile.objects.filter(tenant=request.tenant)
    registrations = DealRegistration.objects.filter(tenant=request.tenant)
    conflicts = ChannelConflict.objects.filter(tenant=request.tenant)

    partner_stats = partners.aggregate(
        total_partner_revenue=Sum("actual_revenue_ytd"),
        active_partners_count=Count("id", filter=Q(onboarding_status="active")),
        avg_certifications=Avg("active_certifications_count"),
    )
    registration_stats = registrations.aggregate(
        registered_deals_count=Count("id"),
        pipeline_value=Sum("estimated_value", filter=Q(status__in=["submitted", "under_review", "approved"])),
    )

    stats = {
        "active_partners_count": partner_stats["active_partners_count"] or 0,
        "total_partner_revenue": partner_stats["total_partner_revenue"] or Decimal("0.00"),
        "registered_deals_count": registration_stats["registered_deals_count"] or 0,
        "pipeline_value": registration_stats["pipeline_value"] or Decimal("0.00"),
        "open_conflicts_count": conflicts.filter(status__in=["open", "in_mediation", "escalated"]).count(),
        "avg_certifications": partner_stats["avg_certifications"] or 0,
    }

    tier_aggregates = {
        row["tier"]: row
        for row in partners.values("tier").annotate(
            count=Count("id"),
            revenue=Sum("actual_revenue_ytd"),
        )
    }
    tier_distribution = []
    for tier_code, tier_label in PARTNER_TIER_CHOICES:
        data = tier_aggregates.get(tier_code)
        tier_distribution.append({
            "code": tier_code,
            "label": tier_label,
            "count": data["count"] if data else 0,
            "revenue": (data["revenue"] if data and data["revenue"] is not None else Decimal("0.00")),
        })

    top_partners = (
        partners.select_related("partner", "channel_manager", "currency")
        .order_by("-actual_revenue_ytd")[:5]
    )

    now = timezone.localdate()
    expiring_soon = now + timezone.timedelta(days=30)
    expiring_registrations = (
        registrations.filter(
            status="approved",
            protection_end_date__gte=now,
            protection_end_date__lte=expiring_soon,
        )
        .select_related("partner", "customer_account", "currency")
        .order_by("protection_end_date")[:5]
    )

    recent_conflicts = (
        conflicts.filter(status__in=["open", "in_mediation", "escalated"])
        .select_related("claimant_partner", "client_account", "direct_sales_rep")
        .order_by("-created_at")[:5]
    )

    context = {
        "stats": stats,
        "tier_distribution": tier_distribution,
        "top_partners": top_partners,
        "expiring_registrations": expiring_registrations,
        "recent_conflicts": recent_conflicts,
    }
    return render(request, "sales/partnerchannel/boards/partner_performance_console.html", context)
