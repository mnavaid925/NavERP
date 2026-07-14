"""CRM 1.3 Marketing Automation — FormSubmissions views (split from apps/crm/views.py)."""
from apps.crm.views._common import *  # noqa: F401,F403
from apps.crm.models import (
    FormSubmission,
    LandingPage,
    Lead,
)


# ------------------------------------------------------------ Form submissions (1.3, read-mostly)
@login_required
def formsubmission_list(request):
    return crud_list(
        request,
        FormSubmission.objects.filter(tenant=request.tenant).select_related(
            "landing_page", "routed_to", "converted_lead"),
        "crm/marketing/formsubmission/list.html",
        search_fields=["name", "email", "company", "landing_page__name"],
        filters=[("status", "status", False), ("landing_page", "landing_page_id", True)],
        extra_context={"status_choices": FormSubmission.STATUS_CHOICES,
                       "landing_pages": LandingPage.objects.filter(tenant=request.tenant).only("pk", "name", "number")},
    )


@login_required
def formsubmission_detail(request, pk):
    obj = get_object_or_404(
        FormSubmission.objects.select_related("landing_page", "routed_to", "converted_lead"),
        pk=pk, tenant=request.tenant)
    return render(request, "crm/marketing/formsubmission/detail.html", {"obj": obj})


@login_required
@require_POST
def formsubmission_delete(request, pk):
    return crud_delete(request, model=FormSubmission, pk=pk, success_url="crm:formsubmission_list")


@login_required
@require_POST
def formsubmission_convert(request, pk):
    """Turn a captured submission into a CRM Lead, routed to the landing page's owner.
    Idempotent — a submission already linked to a lead is left untouched."""
    sub = get_object_or_404(
        FormSubmission.objects.select_related("landing_page", "routed_to"), pk=pk, tenant=request.tenant)
    if sub.converted_lead_id:
        messages.info(request, "This submission was already converted to a lead.")
        return redirect("crm:formsubmission_detail", pk=sub.pk)
    lp = sub.landing_page
    owner = sub.routed_to or (lp.routing_owner if lp else None)
    with transaction.atomic():
        lead = Lead.objects.create(
            tenant=request.tenant, name=sub.name, company=sub.company, email=sub.email,
            phone=sub.phone, source=(lp.lead_source if lp else "web"), status="new",
            owner=owner, description=sub.message,
        )
        sub.converted_lead = lead
        sub.status = "converted"
        sub.routed_to = owner
        sub.save(update_fields=["converted_lead", "status", "routed_to"])
    write_audit_log(request.user, lead, "create", {"from": "form_submission", "submission": sub.pk})
    write_audit_log(request.user, sub, "update", {"action": "convert", "lead": lead.pk})
    messages.success(request, f"Converted to lead {lead.number}.")
    return redirect("crm:lead_detail", pk=lead.pk)
