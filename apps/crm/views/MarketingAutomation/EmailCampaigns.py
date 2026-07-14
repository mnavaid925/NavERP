"""CRM 1.3 Marketing Automation — EmailCampaigns views (split from apps/crm/views.py)."""
from apps.crm.views._common import *  # noqa: F401,F403
from apps.crm.models import (
    Campaign,
    CampaignMember,
    EmailCampaign,
)
from apps.crm.forms import (
    EmailCampaignForm,
)


# ------------------------------------------------------------ Email campaigns / blasts (1.3)
@login_required
def emailcampaign_list(request):
    return crud_list(
        request,
        EmailCampaign.objects.filter(tenant=request.tenant).select_related("campaign", "template", "owner"),
        "crm/marketing/emailcampaign/list.html",
        search_fields=["number", "name", "campaign__name"],
        filters=[("status", "status", False), ("send_type", "send_type", False),
                 ("campaign", "campaign_id", True)],
        extra_context={"status_choices": EmailCampaign.STATUS_CHOICES,
                       "send_type_choices": EmailCampaign.SEND_TYPE_CHOICES,
                       "campaigns": Campaign.objects.filter(tenant=request.tenant).only("pk", "name", "number")},
    )


@login_required
def emailcampaign_create(request):
    return crud_create(request, form_class=EmailCampaignForm,
                       template="crm/marketing/emailcampaign/form.html",
                       success_url="crm:emailcampaign_list")


@login_required
def emailcampaign_detail(request, pk):
    obj = get_object_or_404(
        EmailCampaign.objects.select_related("campaign", "template", "variant_template", "owner"),
        pk=pk, tenant=request.tenant)
    return render(request, "crm/marketing/emailcampaign/detail.html", {"obj": obj})


@login_required
def emailcampaign_edit(request, pk):
    return crud_edit(request, model=EmailCampaign, pk=pk, form_class=EmailCampaignForm,
                     template="crm/marketing/emailcampaign/form.html",
                     success_url="crm:emailcampaign_list")


@login_required
@require_POST
def emailcampaign_delete(request, pk):
    return crud_delete(request, model=EmailCampaign, pk=pk, success_url="crm:emailcampaign_list")


@tenant_admin_required  # firing a blast is privileged + irreversible — mirrors expense_approve/crm_po_receive
@require_POST
def emailcampaign_send(request, pk):
    """Simulate a send: snapshot recipient count from the campaign's members, stamp the
    send, and advance any 'targeted' members to 'sent'. (No real ESP — metrics are modelled,
    not delivered.) recipients_count/sent_count/sent_at are system-set here, never via the form."""
    blast = get_object_or_404(EmailCampaign.objects.select_related("campaign"), pk=pk, tenant=request.tenant)
    recipients = CampaignMember.objects.filter(tenant=request.tenant, campaign=blast.campaign).count()
    with transaction.atomic():
        # Conditional UPDATE claims the row atomically: a second concurrent POST sees the status
        # already advanced and updates 0 rows, so the metrics can never be double-counted.
        claimed = EmailCampaign.objects.filter(pk=blast.pk, tenant=request.tenant).exclude(
            status__in=("sending", "sent", "cancelled")).update(
            recipients_count=recipients, sent_count=recipients, status="sent",
            sent_at=timezone.now())
        if not claimed:
            messages.info(request, "This email campaign has already been sent or cancelled.")
            return redirect("crm:emailcampaign_detail", pk=blast.pk)
        CampaignMember.objects.filter(
            tenant=request.tenant, campaign=blast.campaign, status="targeted").update(status="sent")
    write_audit_log(request.user, blast, "update", {"action": "send", "recipients": recipients})
    messages.success(request, f"{blast.number} sent to {recipients} recipient(s).")
    return redirect("crm:emailcampaign_detail", pk=blast.pk)
