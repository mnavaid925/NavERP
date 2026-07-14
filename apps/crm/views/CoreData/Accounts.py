"""CRM 1.1 Core Data Management — Accounts views (split from apps/crm/views.py)."""
from apps.crm.views._common import *  # noqa: F401,F403
from apps.crm.models import (
    AccountProfile,
    Case,
    ContactProfile,
    INDUSTRY_CHOICES,
    Lead,
    Opportunity,
)
from apps.crm.forms import (
    AccountForm,
)


# ===================== Accounts & Contacts — core.Party + CRM profile (1.1) =================
# Accounts/Contacts ARE the shared core.Party (one identity, many roles); CRM owns a one-to-one
# AccountProfile/ContactProfile carrying the rich fields. Full CRUD here manages the Party + its
# profile together. Routes are keyed by Party pk. Delete removes the underlying Party (cascading
# the profile/roles/addresses); opportunities/cases keep their rows with the link SET_NULL.
@login_required
def account_list(request):
    return crud_list(
        request,
        Party.objects.filter(tenant=request.tenant, kind="organization")
        .select_related("crm_account_profile", "crm_account_profile__owner"),
        "crm/directory/account/list.html", search_fields=["name", "tax_id"],
        filters=[("industry", "crm_account_profile__industry", False),
                 ("source", "crm_account_profile__source", False)],
        extra_context={"industry_choices": INDUSTRY_CHOICES, "source_choices": Lead.SOURCE_CHOICES},
    )


@login_required
def account_detail(request, pk):
    obj = get_object_or_404(
        Party.objects.filter(tenant=request.tenant, kind="organization")
        .select_related("crm_account_profile", "crm_account_profile__owner",
                        "crm_account_profile__parent_account")
        .prefetch_related("roles", "addresses", "contact_methods"),
        pk=pk)
    return render(request, "crm/directory/account/detail.html", {
        "obj": obj,
        "profile": getattr(obj, "crm_account_profile", None),
        "opportunities": Opportunity.objects.filter(tenant=request.tenant, account=obj).select_related("owner")[:20],
        "cases": Case.objects.filter(tenant=request.tenant, account=obj).select_related("owner")[:20],
        "child_accounts": AccountProfile.objects.filter(tenant=request.tenant, parent_account=obj).select_related("party")[:20],
        "stakeholders": ContactProfile.objects.filter(tenant=request.tenant, account=obj).select_related("party")[:20],
    })


@login_required
def account_create(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = AccountForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                party = Party.objects.create(
                    tenant=request.tenant, kind="organization",
                    name=form.cleaned_data["name"], tax_id=form.cleaned_data.get("tax_id", ""))
                profile = form.save(commit=False)
                profile.tenant = request.tenant
                profile.party = party
                profile.save()
            write_audit_log(request.user, party, "create")
            messages.success(request, "Account created.")
            return redirect("crm:account_detail", pk=party.pk)
    else:
        form = AccountForm(tenant=request.tenant)
    return render(request, "crm/directory/account/form.html", {"form": form, "is_edit": False})


@login_required
def account_edit(request, pk):
    party = get_object_or_404(Party, pk=pk, tenant=request.tenant, kind="organization")
    # Bind to the existing profile, or a new (unsaved) one carrying the party — so the form's
    # parent-account self-exclusion works and the profile INSERT happens inside the atomic block.
    profile = (AccountProfile.objects.filter(party=party).first()
               or AccountProfile(party=party, tenant=request.tenant))
    form = AccountForm(request.POST or None, instance=profile, tenant=request.tenant,
                       initial={"name": party.name, "tax_id": party.tax_id})
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            party.name = form.cleaned_data["name"]
            party.tax_id = form.cleaned_data.get("tax_id", "")
            party.save(update_fields=["name", "tax_id"])
            p = form.save(commit=False)
            p.tenant = request.tenant
            p.party = party
            p.save()
        write_audit_log(request.user, party, "update")
        messages.success(request, "Account updated.")
        return redirect("crm:account_detail", pk=party.pk)
    return render(request, "crm/directory/account/form.html", {"form": form, "is_edit": True, "obj": party})


@tenant_admin_required  # deleting a shared core.Party identity is privileged (cross-module blast radius)
@require_POST
def account_delete(request, pk):
    party = get_object_or_404(Party, pk=pk, tenant=request.tenant, kind="organization")
    write_audit_log(request.user, party, "delete")
    party.delete()
    messages.success(request, "Account deleted.")
    return redirect("crm:account_list")
