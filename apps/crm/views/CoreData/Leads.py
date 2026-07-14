"""CRM 1.1 Core Data Management — Leads views (split from apps/crm/views.py)."""
from apps.crm.views._common import *  # noqa: F401,F403
from apps.crm.models import (
    Lead,
    Opportunity,
)
from apps.crm.forms import (
    LeadForm,
)


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
                       success_url="crm:lead_list")


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
                     template="crm/directory/lead/form.html", success_url="crm:lead_list")


@login_required
@require_POST
def lead_delete(request, pk):
    return crud_delete(request, model=Lead, pk=pk, success_url="crm:lead_list")


@login_required
@require_POST
def lead_convert(request, pk):
    """One-click conversion (1.1): Lead -> Account (org Party) + Contact (person Party) +
    Opportunity. Idempotent guard: a converted lead is not re-converted."""
    lead = get_object_or_404(Lead, pk=pk, tenant=request.tenant)
    if lead.status == "converted":
        messages.info(request, "This lead has already been converted.")
        return redirect("crm:lead_detail", pk=lead.pk)
    with transaction.atomic():
        account = None
        if lead.company:
            account = Party.objects.create(tenant=request.tenant, kind="organization", name=lead.company)
            PartyRole.objects.create(tenant=request.tenant, party=account, role="customer",
                                     status="active", start_date=timezone.localdate())
        contact = Party.objects.create(tenant=request.tenant, kind="person", name=lead.name)
        PartyRole.objects.create(tenant=request.tenant, party=contact, role="contact",
                                 status="active", start_date=timezone.localdate())
        if lead.email:
            ContactMethod.objects.create(tenant=request.tenant, party=contact, kind="email", value=lead.email)
        opp = Opportunity.objects.create(
            tenant=request.tenant, name=f"{lead.company or lead.name} Opportunity",
            account=account, primary_contact=contact, stage="prospecting",
            amount=lead.est_value, probability=10, owner=lead.owner, source_lead=lead,
        )
        lead.status = "converted"
        lead.converted_party = account or contact
        lead.save(update_fields=["status", "converted_party", "updated_at"])
    write_audit_log(request.user, lead, "update", {"action": "convert"})
    write_audit_log(request.user, opp, "create")
    messages.success(request, f"Lead converted — opportunity {opp.number} created.")
    return redirect("crm:opportunity_detail", pk=opp.pk)
