"""CRM 1.1 Core Data Management — Leads views (split from apps/crm/views.py)."""
from apps.crm.views._common import *  # noqa: F401,F403
from apps.crm.models import (
    Lead,
    Opportunity,
)
from apps.crm.forms import (
    LeadForm,
)
from apps.crm.services import convert_lead
from apps.sales.services import exit_nurture_for_lead


# ===================================================================== Leads (1.1)
@login_required
def lead_list(request):
    return crud_list(
        request, Lead.objects.filter(tenant=request.tenant).select_related("owner"),
        "crm/directory/lead/list.html",
        search_fields=["name", "company", "email", "number"],
        filters=[("status", "status", False), ("rating", "rating", False), ("source", "source", False)],
        extra_context={"status_choices": Lead.STATUS_CHOICES,
                       "rating_choices": Lead.RATING_CHOICES,
                       "source_choices": Lead.SOURCE_CHOICES},
    )


@login_required
def lead_create(request):
    return crud_create(request, form_class=LeadForm, template="crm/directory/lead/form.html",
                       success_url="crm:lead_list", form_kwargs={"user": request.user})


@login_required
def lead_detail(request, pk):
    obj = get_object_or_404(Lead.objects.select_related("owner", "converted_party"),
                            pk=pk, tenant=request.tenant)
    return render(request, "crm/directory/lead/detail.html", {
        "obj": obj,
        # Explicit tenant scope (defense-in-depth) — never trust a reverse-FK manager alone.
        "opportunities": Opportunity.objects.filter(
            tenant=request.tenant, source_lead=obj).select_related("account")[:20],
    })


@login_required
def lead_edit(request, pk):
    return crud_edit(request, model=Lead, pk=pk, form_class=LeadForm,
                     template="crm/directory/lead/form.html", success_url="crm:lead_list", form_kwargs={"user": request.user})


@login_required
@require_POST
def lead_delete(request, pk):
    from apps.sales.models import LeadNurtureEnrollment, LeadQualification, LeadScoreEvent

    lead = get_object_or_404(Lead, pk=pk, tenant=request.tenant)
    if (LeadScoreEvent.objects.filter(tenant=request.tenant, lead=lead).exists()
            or LeadQualification.objects.filter(tenant=request.tenant, lead=lead).exists()
            or LeadNurtureEnrollment.objects.filter(tenant=request.tenant, lead=lead).exists()):
        messages.error(request, "This lead has Sales history and must be retained.")
        return redirect("crm:lead_detail", pk=lead.pk)
    return crud_delete(request, model=Lead, pk=pk, success_url="crm:lead_list")


@require_POST
@tenant_admin_required
def lead_convert(request, pk):
    lead = get_object_or_404(Lead, pk=pk, tenant=request.tenant)
    with transaction.atomic():
        locked_lead = Lead.objects.select_for_update().get(pk=lead.pk, tenant=request.tenant)
        already_converted = locked_lead.status == "converted"
        if not already_converted:
            from apps.sales.models import LeadQualification
            qualification = LeadQualification.objects.filter(tenant=request.tenant, lead=locked_lead).first()
            if qualification is not None and qualification.status != "qualified":
                messages.error(request, "A qualified assessment is required before conversion.")
                return redirect("crm:lead_detail", pk=locked_lead.pk)
        try:
            opp = convert_lead(locked_lead, request.tenant)
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
            return redirect("crm:lead_detail", pk=locked_lead.pk)
        locked_lead.refresh_from_db()
        if locked_lead.status != "converted" or not Opportunity.objects.filter(pk=opp.pk, tenant=request.tenant, source_lead=locked_lead).exists():
            transaction.set_rollback(True)
            messages.error(request, "CRM conversion could not be verified.")
            return redirect("crm:lead_detail", pk=locked_lead.pk)
        exit_nurture_for_lead(locked_lead, request.tenant, request.user, "converted")
        if not already_converted:
            write_audit_log(request.user, locked_lead, "update", {"action": "convert"})
            write_audit_log(request.user, opp, "create")
    if already_converted:
        messages.info(request, "This lead has already been converted.")
    else:
        messages.success(request, f"Lead converted — opportunity {opp.number} created.")
    return redirect("crm:opportunity_detail", pk=opp.pk)
