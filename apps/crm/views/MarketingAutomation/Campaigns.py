"""CRM 1.3 Marketing Automation — Campaigns views (split from apps/crm/views.py)."""
from apps.crm.views._common import *  # noqa: F401,F403
from apps.crm.models import (
    Campaign,
    CampaignMember,
    EmailCampaign,
    LandingPage,
    Opportunity,
)
from apps.crm.forms import (
    CampaignForm,
)


# ------------------------------------------------------------ Campaigns (1.3)
@login_required
def campaign_list(request):
    return crud_list(
        request, Campaign.objects.filter(tenant=request.tenant).select_related("owner"),
        "crm/marketing/campaign/list.html",
        search_fields=["name", "number"],
        filters=[("status", "status", False), ("type", "type", False),
                 ("objective", "objective", False)],
        extra_context={"status_choices": Campaign.STATUS_CHOICES,
                       "type_choices": Campaign.TYPE_CHOICES,
                       "objective_choices": Campaign.OBJECTIVE_CHOICES},
    )


@login_required
def campaign_create(request):
    return crud_create(request, form_class=CampaignForm, template="crm/marketing/campaign/form.html",
                       success_url="crm:campaign_list")


@login_required
def campaign_detail(request, pk):
    obj = get_object_or_404(
        Campaign.objects.select_related("owner", "parent_campaign"), pk=pk, tenant=request.tenant)
    members_qs = CampaignMember.objects.filter(tenant=request.tenant, campaign=obj)
    # Single aggregate for the funnel stats — no per-row loop, no N+1.
    agg = members_qs.aggregate(
        total=Count("id"),
        responded=Count("id", filter=Q(status__in=CampaignMember.RESPONDED_STATUSES)),
    )
    total, responded = agg["total"] or 0, agg["responded"] or 0
    return render(request, "crm/marketing/campaign/detail.html", {
        "obj": obj,
        "members": members_qs.select_related("party", "lead")[:50],
        "member_total": total,
        "responded_count": responded,
        "response_rate": (responded / total * 100) if total else None,
        "email_campaigns": EmailCampaign.objects.filter(
            tenant=request.tenant, campaign=obj).select_related("template")[:20],
        "landing_pages": LandingPage.objects.filter(
            tenant=request.tenant, campaign=obj)[:20],
        "opportunities": Opportunity.objects.filter(
            tenant=request.tenant, campaign=obj).select_related("account")[:20],
        "member_status_choices": CampaignMember.STATUS_CHOICES,
    })


@login_required
def campaign_edit(request, pk):
    return crud_edit(request, model=Campaign, pk=pk, form_class=CampaignForm,
                     template="crm/marketing/campaign/form.html", success_url="crm:campaign_list")


@login_required
@require_POST
def campaign_delete(request, pk):
    return crud_delete(request, model=Campaign, pk=pk, success_url="crm:campaign_list")
