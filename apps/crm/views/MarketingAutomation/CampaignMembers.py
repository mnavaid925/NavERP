"""CRM 1.3 Marketing Automation — CampaignMembers views (split from apps/crm/views.py)."""
from apps.crm.views._common import *  # noqa: F401,F403
from apps.crm.models import (
    Campaign,
    CampaignMember,
)
from apps.crm.forms import (
    CampaignMemberForm,
)


# ------------------------------------------------------------ Campaign members (1.3)
@login_required
def campaignmember_list(request):
    return crud_list(
        request,
        CampaignMember.objects.filter(tenant=request.tenant).select_related("campaign", "party", "lead"),
        "crm/marketing/campaignmember/list.html",
        search_fields=["member_name", "member_email", "campaign__name"],
        filters=[("status", "status", False), ("campaign", "campaign_id", True)],
        extra_context={"status_choices": CampaignMember.STATUS_CHOICES,
                       "campaigns": Campaign.objects.filter(tenant=request.tenant).only("pk", "name", "number")},
    )


@login_required
def campaignmember_create(request):
    return crud_create(request, form_class=CampaignMemberForm,
                       template="crm/marketing/campaignmember/form.html",
                       success_url="crm:campaignmember_list")


@login_required
def campaignmember_detail(request, pk):
    obj = get_object_or_404(
        CampaignMember.objects.select_related("campaign", "party", "lead"), pk=pk, tenant=request.tenant)
    return render(request, "crm/marketing/campaignmember/detail.html", {"obj": obj})


@login_required
def campaignmember_edit(request, pk):
    return crud_edit(request, model=CampaignMember, pk=pk, form_class=CampaignMemberForm,
                     template="crm/marketing/campaignmember/form.html",
                     success_url="crm:campaignmember_list")


@login_required
@require_POST
def campaignmember_delete(request, pk):
    return crud_delete(request, model=CampaignMember, pk=pk, success_url="crm:campaignmember_list")


@login_required
@require_POST
def campaignmember_add(request, pk):
    """Inline add on the campaign detail page — quick manual list entry."""
    campaign = get_object_or_404(Campaign, pk=pk, tenant=request.tenant)
    name = request.POST.get("member_name", "").strip()[:255]
    if not name:
        messages.error(request, "A member name is required.")
        return redirect("crm:campaign_detail", pk=campaign.pk)
    status = request.POST.get("status", "targeted")
    if status not in dict(CampaignMember.STATUS_CHOICES):
        status = "targeted"
    email = request.POST.get("member_email", "").strip()[:254]
    if email:
        try:  # the inline shortcut bypasses the EmailField form — validate here too.
            validate_email(email)
        except ValidationError:
            email = ""
    CampaignMember.objects.create(
        tenant=request.tenant, campaign=campaign, member_name=name,
        member_email=email, status=status)
    messages.success(request, "Member added to the campaign.")
    return redirect("crm:campaign_detail", pk=campaign.pk)


@login_required
@require_POST
def campaignmember_remove(request, member_pk):
    member = get_object_or_404(CampaignMember, pk=member_pk, tenant=request.tenant)
    campaign_id = member.campaign_id
    member.delete()
    messages.success(request, "Member removed.")
    return redirect("crm:campaign_detail", pk=campaign_id)
