"""Sales 8.13 — Views for `AttributionTouchpoint` (the marketing touch ledger)."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.crm.models import Campaign, Lead
from apps.sales.forms.MarketingAlignment.AttributionTouchpoints import (
    AttributionTouchpointForm,
)
from apps.sales.models.MarketingAlignment.AttributionTouchpoints import (
    TOUCH_CHANNEL_CHOICES,
    TOUCH_POSITION_CHOICES,
    TOUCH_TYPE_CHOICES,
    AttributionTouchpoint,
)


@login_required
def attribution_touchpoint_list(request):
    qs = (
        AttributionTouchpoint.objects.filter(tenant=request.tenant)
        .select_related("campaign", "lead", "opportunity", "currency")
        .order_by("-touch_date", "-created_at")
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(campaign__name__icontains=q)
            | Q(lead__name__icontains=q)
            | Q(opportunity__name__icontains=q)
            | Q(source_reference__icontains=q)
            | Q(number__icontains=q)
        )

    channel = request.GET.get("channel", "").strip()
    if channel:
        qs = qs.filter(channel=channel)

    touch_type = request.GET.get("touch_type", "").strip()
    if touch_type:
        qs = qs.filter(touch_type=touch_type)

    position = request.GET.get("position", "").strip()
    if position:
        qs = qs.filter(touch_position=position)

    campaign_id = request.GET.get("campaign", "").strip()
    if campaign_id and campaign_id.isdigit():
        qs = qs.filter(campaign_id=int(campaign_id))

    lead_id = request.GET.get("lead", "").strip()
    if lead_id and lead_id.isdigit():
        qs = qs.filter(lead_id=int(lead_id))

    stats = qs.aggregate(
        total_count=Count("id"),
        total_cost=Sum("cost"),
        total_engagement_value=Sum("engagement_value"),
        first_touch_count=Count("id", filter=Q(touch_position="first")),
        last_touch_count=Count("id", filter=Q(touch_position="last")),
    )

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    campaigns = Campaign.objects.filter(tenant=request.tenant).order_by("name")
    leads = Lead.objects.filter(tenant=request.tenant).order_by("name")

    context = {
        "page_obj": page_obj,
        "touchpoints": page_obj.object_list,
        "channel_choices": TOUCH_CHANNEL_CHOICES,
        "touch_type_choices": TOUCH_TYPE_CHOICES,
        "position_choices": TOUCH_POSITION_CHOICES,
        "campaigns": campaigns,
        "leads": leads,
        "active_filters": {
            "q": q,
            "channel": channel,
            "touch_type": touch_type,
            "position": position,
            "campaign": campaign_id,
            "lead": lead_id,
        },
        "stats": stats,
    }
    return render(
        request,
        "sales/marketingalignment/attributiontouchpoint/list.html",
        context,
    )


@login_required
def attribution_touchpoint_detail(request, pk):
    obj = get_object_or_404(
        AttributionTouchpoint.objects.filter(tenant=request.tenant).select_related(
            "campaign", "lead", "opportunity", "currency"
        ),
        pk=pk,
    )
    return render(
        request,
        "sales/marketingalignment/attributiontouchpoint/detail.html",
        {"obj": obj, "touchpoint": obj},
    )


@login_required
def attribution_touchpoint_create(request):
    if request.method == "POST":
        form = AttributionTouchpointForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save()
            write_audit_log(
                request.user,
                obj,
                "create",
                f"Recorded attribution touchpoint {obj.number} "
                f"({obj.get_channel_display()} / {obj.get_touch_type_display()})",
                tenant=request.tenant,
            )
            messages.success(request, f"Attribution touchpoint {obj.number} created successfully.")
            return redirect("sales:attribution_touchpoint_detail", pk=obj.pk)
    else:
        form = AttributionTouchpointForm(tenant=request.tenant)

    return render(
        request,
        "sales/marketingalignment/attributiontouchpoint/form.html",
        {"form": form, "obj": None, "is_edit": False},
    )


@login_required
def attribution_touchpoint_edit(request, pk):
    obj = get_object_or_404(
        AttributionTouchpoint.objects.filter(tenant=request.tenant),
        pk=pk,
    )
    if request.method == "POST":
        form = AttributionTouchpointForm(
            request.POST, instance=obj, tenant=request.tenant
        )
        if form.is_valid():
            obj = form.save()
            write_audit_log(
                request.user,
                obj,
                "update",
                f"Updated attribution touchpoint {obj.number}",
                tenant=request.tenant,
            )
            messages.success(request, f"Attribution touchpoint {obj.number} updated successfully.")
            return redirect("sales:attribution_touchpoint_detail", pk=obj.pk)
    else:
        form = AttributionTouchpointForm(instance=obj, tenant=request.tenant)

    return render(
        request,
        "sales/marketingalignment/attributiontouchpoint/form.html",
        {"form": form, "obj": obj, "is_edit": True},
    )


@require_POST
@tenant_admin_required
def attribution_touchpoint_delete(request, pk):
    obj = get_object_or_404(
        AttributionTouchpoint.objects.filter(tenant=request.tenant),
        pk=pk,
    )
    number = obj.number
    write_audit_log(
        request.user,
        obj,
        "delete",
        f"Deleted attribution touchpoint {number}",
        tenant=request.tenant,
    )
    obj.delete()
    messages.success(request, f"Attribution touchpoint {number} deleted.")
    return redirect("sales:attribution_touchpoint_list")
