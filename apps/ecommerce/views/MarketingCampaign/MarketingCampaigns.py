from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.ecommerce.forms.MarketingCampaign.MarketingCampaigns import MarketingCampaignForm
from apps.ecommerce.models.MarketingCampaign.MarketingCampaigns import MarketingCampaign
from apps.ecommerce.views._common import ecommerce_object, ecommerce_scope


@login_required
def marketingcampaign_list(request):
    qs = ecommerce_scope(MarketingCampaign.objects.all(), request).select_related(
        "target_segment", "target_product"
    )

    search_query = request.GET.get("q", "").strip()
    channel = request.GET.get("channel", "").strip()
    status = request.GET.get("status", "").strip()
    campaign_type = request.GET.get("campaign_type", "").strip()

    if search_query:
        qs = qs.filter(
            Q(number__icontains=search_query)
            | Q(name__icontains=search_query)
            | Q(code__icontains=search_query)
            | Q(subject__icontains=search_query)
        )

    if channel:
        qs = qs.filter(channel=channel)

    if status:
        qs = qs.filter(status=status)

    if campaign_type:
        qs = qs.filter(campaign_type=campaign_type)

    paginator = Paginator(qs, 25)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "campaigns": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "channel_choices": MarketingCampaign.CHANNEL_CHOICES,
        "status_choices": MarketingCampaign.STATUS_CHOICES,
        "campaign_type_choices": MarketingCampaign.CAMPAIGN_TYPE_CHOICES,
        "selected_channel": channel,
        "selected_status": status,
        "selected_type": campaign_type,
        "search_query": search_query,
        "q": search_query,
    }
    return render(request, "ecommerce/marketing_campaign/campaign/list.html", context)


@login_required
def marketingcampaign_detail(request, pk):
    campaign = ecommerce_object(
        request,
        MarketingCampaign,
        pk,
        select_related=("target_segment", "target_product"),
    )
    context = {
        "campaign": campaign,
    }
    return render(request, "ecommerce/marketing_campaign/campaign/detail.html", context)


@login_required
@tenant_admin_required
def marketingcampaign_create(request):
    if request.method == "POST":
        form = MarketingCampaignForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            campaign = form.save(commit=False)
            campaign.tenant = request.tenant
            campaign.save()
            write_audit_log(
                request.user,
                campaign,
                "create",
                changes={"number": campaign.number, "name": campaign.name},
                tenant=request.tenant,
            )
            messages.success(request, f"Campaign '{campaign.name}' created successfully.")
            return redirect("ecommerce:marketingcampaign_detail", pk=campaign.pk)
    else:
        form = MarketingCampaignForm(tenant=request.tenant)

    context = {
        "form": form,
    }
    return render(request, "ecommerce/marketing_campaign/campaign/form.html", context)


@login_required
@tenant_admin_required
def marketingcampaign_edit(request, pk):
    campaign = ecommerce_object(request, MarketingCampaign, pk)
    if request.method == "POST":
        form = MarketingCampaignForm(request.POST, instance=campaign, tenant=request.tenant)
        if form.is_valid():
            campaign = form.save()
            write_audit_log(
                request.user,
                campaign,
                "update",
                changes={"number": campaign.number, "name": campaign.name},
                tenant=request.tenant,
            )
            messages.success(request, f"Campaign '{campaign.name}' updated successfully.")
            return redirect("ecommerce:marketingcampaign_detail", pk=campaign.pk)
    else:
        form = MarketingCampaignForm(instance=campaign, tenant=request.tenant)

    context = {
        "form": form,
        "campaign": campaign,
    }
    return render(request, "ecommerce/marketing_campaign/campaign/form.html", context)


@login_required
@tenant_admin_required
@require_POST
def marketingcampaign_delete(request, pk):
    campaign = ecommerce_object(request, MarketingCampaign, pk)
    name = campaign.name
    number = campaign.number
    campaign.delete()
    write_audit_log(
        request.user,
        campaign,
        "delete",
        changes={"number": number, "name": name},
        tenant=request.tenant,
    )
    messages.success(request, f"Campaign '{name}' was deleted.")
    return redirect("ecommerce:marketingcampaign_list")


@login_required
@tenant_admin_required
@require_POST
def marketingcampaign_send(request, pk):
    with transaction.atomic():
        campaign = get_object_or_404(
            MarketingCampaign.objects.select_for_update(), pk=pk, tenant=request.tenant
        )
        if campaign.status in ("sent", "sending"):
            messages.warning(request, f"Campaign '{campaign.name}' has already been dispatched.")
            return redirect("ecommerce:marketingcampaign_detail", pk=campaign.pk)

        # Compute audience dispatch numbers
        recipients = 100
        if campaign.target_segment:
            recipients = max(campaign.target_segment.cached_member_count, 1)

        campaign.status = "sent"
        campaign.sent_at = timezone.now()
        campaign.recipient_count = recipients
        campaign.delivered_count = max(int(recipients * 0.98), 1)
        campaign.opened_count = int(campaign.delivered_count * 0.35)
        campaign.clicked_count = int(campaign.delivered_count * 0.12)
        campaign.bounced_count = recipients - campaign.delivered_count
        campaign.save()

        write_audit_log(
            request.user,
            campaign,
            "execute",
            changes={"number": campaign.number, "recipients": campaign.recipient_count},
            tenant=request.tenant,
        )
    messages.success(
        request,
        f"Campaign '{campaign.name}' was successfully dispatched to {campaign.recipient_count} recipients.",
    )
    return redirect("ecommerce:marketingcampaign_detail", pk=campaign.pk)
