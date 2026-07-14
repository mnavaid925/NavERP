"""CRM 1.1 Core Data Management — Contacts views (split from apps/crm/views.py)."""
from apps.crm.views._common import *  # noqa: F401,F403
from apps.crm.models import (
    Case,
    ContactProfile,
    Lead,
    Opportunity,
)
from apps.crm.forms import (
    ContactForm,
)


@login_required
def contact_list(request):
    return crud_list(
        request,
        Party.objects.filter(tenant=request.tenant, kind="person")
        .select_related("crm_contact_profile", "crm_contact_profile__account"),
        "crm/directory/contact/list.html", search_fields=["name"],
        filters=[("source", "crm_contact_profile__source", False)],
        extra_context={"source_choices": Lead.SOURCE_CHOICES},
    )


@login_required
def contact_detail(request, pk):
    obj = get_object_or_404(
        Party.objects.filter(tenant=request.tenant, kind="person")
        .select_related("crm_contact_profile", "crm_contact_profile__account",
                        "crm_contact_profile__owner")
        .prefetch_related("roles", "contact_methods"),
        pk=pk)
    return render(request, "crm/directory/contact/detail.html", {
        "obj": obj,
        "profile": getattr(obj, "crm_contact_profile", None),
        "opportunities": Opportunity.objects.filter(tenant=request.tenant, primary_contact=obj).select_related("account")[:20],
        "cases": Case.objects.filter(tenant=request.tenant, contact=obj).select_related("owner")[:20],
    })


@login_required
def contact_create(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = ContactForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                party = Party.objects.create(
                    tenant=request.tenant, kind="person", name=form.cleaned_data["name"])
                profile = form.save(commit=False)
                profile.tenant = request.tenant
                profile.party = party
                profile.save()
            write_audit_log(request.user, party, "create")
            messages.success(request, "Contact created.")
            return redirect("crm:contact_detail", pk=party.pk)
    else:
        form = ContactForm(tenant=request.tenant)
    return render(request, "crm/directory/contact/form.html", {"form": form, "is_edit": False})


@login_required
def contact_edit(request, pk):
    party = get_object_or_404(Party, pk=pk, tenant=request.tenant, kind="person")
    profile = (ContactProfile.objects.filter(party=party).first()
               or ContactProfile(party=party, tenant=request.tenant))
    form = ContactForm(request.POST or None, instance=profile, tenant=request.tenant,
                       initial={"name": party.name})
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            party.name = form.cleaned_data["name"]
            party.save(update_fields=["name"])
            p = form.save(commit=False)
            p.tenant = request.tenant
            p.party = party
            p.save()
        write_audit_log(request.user, party, "update")
        messages.success(request, "Contact updated.")
        return redirect("crm:contact_detail", pk=party.pk)
    return render(request, "crm/directory/contact/form.html", {"form": form, "is_edit": True, "obj": party})


@tenant_admin_required  # deleting a shared core.Party identity is privileged (cross-module blast radius)
@require_POST
def contact_delete(request, pk):
    party = get_object_or_404(Party, pk=pk, tenant=request.tenant, kind="person")
    write_audit_log(request.user, party, "delete")
    party.delete()
    messages.success(request, "Contact deleted.")
    return redirect("crm:contact_list")
