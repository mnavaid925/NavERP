"""Sales 8.13 — Views for `CampaignAttribution` (the conversion-credit assignment)."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.crm.models import Campaign
from apps.sales.forms.MarketingAlignment.CampaignAttributions import (
    CampaignAttributionForm,
)
from apps.sales.models.MarketingAlignment.CampaignAttributions import (
    ATTRIBUTION_MODEL_CHOICES,
    ATTRIBUTION_STATUS_CHOICES,
    CampaignAttribution,
)
from apps.sales.views.MarketingAlignment._common import (
    enum_filter,
    pk_from_param,
    single_currency,
)


@login_required
def campaign_attribution_list(request):
    qs = (
        CampaignAttribution.objects.filter(tenant=request.tenant)
        .select_related(
            "touchpoint",
            "touchpoint__campaign",
            "touchpoint__lead",
            "touchpoint__opportunity",
            "computed_by",
        )
        .order_by("-computed_on", "-created_at")
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(touchpoint__campaign__name__icontains=q)
            | Q(touchpoint__lead__name__icontains=q)
            | Q(touchpoint__opportunity__name__icontains=q)
            | Q(number__icontains=q)
        )

    attribution_model, qs = enum_filter(
        qs, request, "attribution_model", "attribution_model", ATTRIBUTION_MODEL_CHOICES
    )

    status, qs = enum_filter(
        qs, request, "status", "status", ATTRIBUTION_STATUS_CHOICES
    )

    campaign_id = request.GET.get("campaign", "").strip()
    campaign_pk = pk_from_param(campaign_id)
    if campaign_pk is not None:
        qs = qs.filter(touchpoint__campaign_id=campaign_pk)

    stats = qs.aggregate(
        total_count=Count("id"),
        approved_count=Count("id", filter=Q(status="approved")),
        total_attributed_revenue=Sum("attributed_revenue"),
        total_attributed_cost=Sum("attributed_cost"),
    )

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    campaigns = Campaign.objects.filter(tenant=request.tenant).only("id", "name").order_by("name")

    context = {
        "page_obj": page_obj,
        "attributions": page_obj.object_list,
        "model_choices": ATTRIBUTION_MODEL_CHOICES,
        "status_choices": ATTRIBUTION_STATUS_CHOICES,
        "campaigns": campaigns,
        "active_filters": {
            "q": q,
            "attribution_model": attribution_model,
            "status": status,
            "campaign": campaign_id,
        },
        "stats": stats,
        # A credit row carries no currency of its own -- it inherits the touchpoint's. The money
        # totals are only labelled with a symbol when every listed credit shares ONE currency.
        "currency": single_currency(qs, "touchpoint__currency"),
    }
    return render(
        request,
        "sales/marketingalignment/campaignattribution/list.html",
        context,
    )


@login_required
def campaign_attribution_detail(request, pk):
    obj = get_object_or_404(
        CampaignAttribution.objects.filter(tenant=request.tenant).select_related(
            "touchpoint",
            "touchpoint__campaign",
            "touchpoint__lead",
            "touchpoint__opportunity",
            "computed_by",
        ),
        pk=pk,
    )
    return render(
        request,
        "sales/marketingalignment/campaignattribution/detail.html",
        {"obj": obj},
    )


@login_required
def campaign_attribution_create(request):
    if request.method == "POST":
        form = CampaignAttributionForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            if not obj.computed_by_id and request.user.is_authenticated:
                obj.computed_by = request.user
            obj.save()
            write_audit_log(
                request.user,
                obj,
                "create",
                f"Created campaign attribution {obj.number} "
                f"({obj.get_attribution_model_display()}, {obj.credit_pct}% credit)",
                tenant=request.tenant,
            )
            messages.success(request, f"Campaign attribution {obj.number} created successfully.")
            return redirect("sales:campaign_attribution_detail", pk=obj.pk)
    else:
        form = CampaignAttributionForm(tenant=request.tenant)

    return render(
        request,
        "sales/marketingalignment/campaignattribution/form.html",
        {"form": form, "obj": None, "is_edit": False},
    )


@login_required
def campaign_attribution_edit(request, pk):
    obj = get_object_or_404(
        CampaignAttribution.objects.filter(tenant=request.tenant),
        pk=pk,
    )
    if request.method == "POST":
        form = CampaignAttributionForm(
            request.POST, instance=obj, tenant=request.tenant
        )
        if form.is_valid():
            obj = form.save(commit=False)
            if not obj.computed_by_id and request.user.is_authenticated:
                obj.computed_by = request.user
            obj.save()
            write_audit_log(
                request.user,
                obj,
                "update",
                f"Updated campaign attribution {obj.number} "
                f"({obj.get_attribution_model_display()})",
                tenant=request.tenant,
            )
            messages.success(request, f"Campaign attribution {obj.number} updated successfully.")
            return redirect("sales:campaign_attribution_detail", pk=obj.pk)
    else:
        form = CampaignAttributionForm(instance=obj, tenant=request.tenant)

    return render(
        request,
        "sales/marketingalignment/campaignattribution/form.html",
        {"form": form, "obj": obj, "is_edit": True},
    )


@require_POST
@tenant_admin_required
def campaign_attribution_delete(request, pk):
    obj = get_object_or_404(
        CampaignAttribution.objects.filter(tenant=request.tenant),
        pk=pk,
    )
    number = obj.number
    write_audit_log(
        request.user,
        obj,
        "delete",
        f"Deleted campaign attribution {number}",
        tenant=request.tenant,
    )
    obj.delete()
    messages.success(request, f"Campaign attribution {number} deleted.")
    return redirect("sales:campaign_attribution_list")
