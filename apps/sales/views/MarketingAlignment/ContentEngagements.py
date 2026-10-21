"""Sales 8.13 — Views for `ContentEngagement` (content performance)."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.models import Party
from apps.core.utils import write_audit_log
from apps.crm.models import Campaign, Lead
from apps.sales.forms.MarketingAlignment.ContentEngagements import (
    ContentEngagementForm,
)
from apps.sales.models.MarketingAlignment.ContentEngagements import (
    ENGAGEMENT_CHANNEL_CHOICES,
    ENGAGEMENT_TYPE_CHOICES,
    ContentEngagement,
)
from apps.sales.models.SalesEnablement.EnablementContents import EnablementContent
from apps.sales.views.MarketingAlignment._common import (
    enum_filter,
    pk_from_param,
    single_currency,
)


@login_required
def content_engagement_list(request):
    qs = (
        ContentEngagement.objects.filter(tenant=request.tenant)
        .select_related("content", "account", "lead", "campaign", "currency")
        .order_by("-engaged_at", "-created_at")
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(content__title__icontains=q)
            | Q(account__name__icontains=q)
            | Q(lead__name__icontains=q)
            | Q(number__icontains=q)
        )

    engagement_type, qs = enum_filter(
        qs, request, "engagement_type", "engagement_type", ENGAGEMENT_TYPE_CHOICES
    )

    engagement_channel, qs = enum_filter(
        qs, request, "engagement_channel", "engagement_channel", ENGAGEMENT_CHANNEL_CHOICES
    )

    content_id = request.GET.get("content", "").strip()
    content_pk = pk_from_param(content_id)
    if content_pk is not None:
        qs = qs.filter(content_id=content_pk)

    account_id = request.GET.get("account", "").strip()
    account_pk = pk_from_param(account_id)
    if account_pk is not None:
        qs = qs.filter(account_id=account_pk)

    campaign_id = request.GET.get("campaign", "").strip()
    campaign_pk = pk_from_param(campaign_id)
    if campaign_pk is not None:
        qs = qs.filter(campaign_id=campaign_pk)

    stats = qs.aggregate(
        total_count=Count("id"),
        download_count=Count("id", filter=Q(engagement_type="download")),
        total_revenue_attributed=Sum("revenue_attributed"),
        avg_engagement_score=Avg("engagement_score"),
        engaged_account_count=Count("account_id", distinct=True),
    )

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    contents = (
        EnablementContent.objects.filter(tenant=request.tenant, is_active=True)
        .only("id", "title")
        .order_by("title")
    )
    accounts = (
        Party.objects.filter(tenant=request.tenant, roles__role="customer")
        .only("id", "name")
        .distinct()
        .order_by("name")
    )
    campaigns = Campaign.objects.filter(tenant=request.tenant).only("id", "name").order_by("name")

    context = {
        "page_obj": page_obj,
        "engagements": page_obj.object_list,
        "engagement_type_choices": ENGAGEMENT_TYPE_CHOICES,
        "channel_choices": ENGAGEMENT_CHANNEL_CHOICES,
        "contents": contents,
        "accounts": accounts,
        "campaigns": campaigns,
        "active_filters": {
            "q": q,
            "engagement_type": engagement_type,
            "engagement_channel": engagement_channel,
            "content": content_id,
            "account": account_id,
            "campaign": campaign_id,
        },
        "stats": stats,
        # The money total is only labelled with a symbol when every listed engagement shares
        # ONE currency -- see `single_currency`.
        "currency": single_currency(qs),
    }
    return render(
        request,
        "sales/marketingalignment/contentengagement/list.html",
        context,
    )


@login_required
def content_engagement_detail(request, pk):
    obj = get_object_or_404(
        ContentEngagement.objects.filter(tenant=request.tenant).select_related(
            "content", "account", "lead", "campaign", "currency"
        ),
        pk=pk,
    )
    return render(
        request,
        "sales/marketingalignment/contentengagement/detail.html",
        {"obj": obj},
    )


@login_required
def content_engagement_create(request):
    if request.method == "POST":
        form = ContentEngagementForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save()
            write_audit_log(
                request.user,
                obj,
                "create",
                f"Recorded content engagement {obj.number} on "
                f"{obj.content.title if obj.content_id else 'content'}",
                tenant=request.tenant,
            )
            messages.success(request, f"Content engagement {obj.number} created successfully.")
            return redirect("sales:content_engagement_detail", pk=obj.pk)
    else:
        form = ContentEngagementForm(tenant=request.tenant)

    return render(
        request,
        "sales/marketingalignment/contentengagement/form.html",
        {"form": form, "obj": None, "is_edit": False},
    )


@login_required
def content_engagement_edit(request, pk):
    obj = get_object_or_404(
        ContentEngagement.objects.filter(tenant=request.tenant),
        pk=pk,
    )
    if request.method == "POST":
        form = ContentEngagementForm(request.POST, instance=obj, tenant=request.tenant)
        if form.is_valid():
            obj = form.save()
            write_audit_log(
                request.user,
                obj,
                "update",
                f"Updated content engagement {obj.number}",
                tenant=request.tenant,
            )
            messages.success(request, f"Content engagement {obj.number} updated successfully.")
            return redirect("sales:content_engagement_detail", pk=obj.pk)
    else:
        form = ContentEngagementForm(instance=obj, tenant=request.tenant)

    return render(
        request,
        "sales/marketingalignment/contentengagement/form.html",
        {"form": form, "obj": obj, "is_edit": True},
    )


@require_POST
@tenant_admin_required
def content_engagement_delete(request, pk):
    obj = get_object_or_404(
        ContentEngagement.objects.filter(tenant=request.tenant),
        pk=pk,
    )
    number = obj.number
    write_audit_log(
        request.user,
        obj,
        "delete",
        f"Deleted content engagement {number}",
        tenant=request.tenant,
    )
    obj.delete()
    messages.success(request, f"Content engagement {number} deleted.")
    return redirect("sales:content_engagement_list")
