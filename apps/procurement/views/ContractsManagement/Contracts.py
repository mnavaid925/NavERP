"""Procurement 6.8 Contract Management — contract register + authoring views.

The register READS the SCM-owned ``scm.SupplierContract`` spine; authoring CREATES a
draft row on it plus this layer's clause links. The lifecycle verbs (activate /
renew / terminate) stay scm's — what 6.8 owns is the drafting and signature surface.

**E-Signature Integration:** signers are added from the contract page; each holds an
unguessable bearer token that gates the PUBLIC sign page (`contract_sign_page`) —
the crm 1.9 flow: GET stamps viewed_at, POST signs/declines under a signer row lock,
and completion is derived, never stored back onto the spine.
"""
from django.db import transaction
from django.urls import reverse

from apps.core.crud import crud_list

from apps.procurement.forms import (
    ClauseLinkFormSet,
    ContractAuthoringForm,
    ContractSignerForm,
)
from apps.procurement.models import ContractSigner
from apps.procurement.models.ContractsManagement.Renewals import expiring_contracts
from apps.procurement.views._common import *  # noqa: F401,F403
from apps.scm.models import SupplierContract


def _choices(model, field):
    return list(model._meta.get_field(field).choices)


STATUS_CHOICES = _choices(SupplierContract, "status")
TYPE_CHOICES = _choices(SupplierContract, "contract_type")


@login_required
def contract_list(request):
    qs = (SupplierContract.objects.filter(tenant=request.tenant)
          .select_related("party", "currency", "owner")
          .order_by("-start_date", "-id"))
    q = request.GET.get("q", "").strip()
    if q:
        from django.db.models import Q
        qs = qs.filter(Q(number__icontains=q) | Q(title__icontains=q)
                       | Q(party__name__icontains=q) | Q(terms_summary__icontains=q))
    status = request.GET.get("status", "")
    if status:
        qs = qs.filter(status=status)
    ctype = request.GET.get("type", "")
    if ctype:
        qs = qs.filter(contract_type=ctype)
    lens = request.GET.get("lens", "")
    if lens == "expiring":
        # Only the agreements whose renewal window is open — the register's alert view.
        expiring_pks = [row["contract"].pk for row in expiring_contracts(request.tenant)]
        qs = qs.filter(pk__in=expiring_pks)
    return crud_list(
        request, qs, "procurement/contractsmanagement/contracts/list.html",
        per_page=20,
        extra_context={"status_choices": STATUS_CHOICES, "type_choices": TYPE_CHOICES,
                       "lens": lens},
    )


def _get_contract(request, pk):
    return get_object_or_404(
        SupplierContract.objects.select_related("party", "currency",
                                                "payment_terms", "owner"),
        pk=pk, tenant=request.tenant)


@login_required
def contract_detail(request, pk):
    """The CLM workspace for one agreement: drafted clauses, signature slots,
    milestones, amendment history, and the derived expiry posture."""
    obj = _get_contract(request, pk)
    links = list(obj.procurement_clause_links.select_related("clause"))
    signers = list(obj.procurement_signers.order_by("order", "id"))
    milestones = list(obj.procurement_milestones.order_by("due_date", "id"))
    amendments = list(obj.procurement_amendments.order_by("-created_at", "-id")[:10])
    open_amendment = next((a for a in amendments if a.status == "pending"), None)
    unsigned = [s for s in signers if not s.has_responded]
    declined = [s for s in signers if s.declined_at is not None]
    from apps.procurement.forms.ContractsManagement import _active_clauses
    return render(request,
                  "procurement/contractsmanagement/contracts/detail.html", {
                      "obj": obj,
                      "links": links,
                      "all_clauses": _active_clauses(request.tenant),
                      "signers": signers,
                      "signer_form": ContractSignerForm(tenant=request.tenant),
                      "unsigned": unsigned,
                      "declined": declined,
                      "all_signed": bool(signers) and not unsigned and not declined,
                      "milestones": milestones,
                      "amendments": amendments,
                      "open_amendment": open_amendment,
                      "days_to_expiry": obj.days_to_expiry(),
                      "is_admin": request.user.is_authenticated
                                  and request.user.is_tenant_admin,
                  })


@login_required
def contract_create(request):
    """Authoring (**Contract Authoring & Templating**): header terms + the drafted
    clause set land in ONE transaction — a half-authored agreement must not exist."""
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before drafting contracts.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = ContractAuthoringForm(request.POST, tenant=request.tenant)
        formset = ClauseLinkFormSet(request.POST, form_kwargs={"tenant": request.tenant})
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                contract = form.save(commit=False)
                contract.tenant = request.tenant
                contract.owner = request.user
                contract.status = "draft"
                contract.save()   # TenantNumbered.save assigns SC-#### on the spine
                formset.instance = contract
                formset.save()
            write_audit_log(request.user, contract, "create",
                            {"authored_via": "procurement_68"})
            messages.success(request,
                             f"Contract {contract.number} drafted with "
                             f"{formset.total_form_count()} clause slots.")
            return redirect("procurement:contract_detail", pk=contract.pk)
    else:
        form = ContractAuthoringForm(tenant=request.tenant)
        formset = ClauseLinkFormSet(form_kwargs={"tenant": request.tenant})
    return render(request, "procurement/contractsmanagement/contracts/form.html",
                  {"form": form, "formset": formset})


# -- clause selection verbs -----------------------------------------------------------------------


@login_required
@require_POST
@tenant_admin_required
def contract_add_link(request, pk):
    """Draft one more library clause into the agreement (admin: legal wording)."""
    contract = _get_contract(request, pk)
    clause_pk = request.POST.get("clause")
    section = request.POST.get("section_order") or (
        contract.procurement_clause_links.count() + 1)
    try:
        section = max(1, int(section))
    except ValueError:
        section = contract.procurement_clause_links.count() + 1
    from apps.procurement.models import ContractClause, ContractClauseLink
    clause = get_object_or_404(ContractClause, pk=clause_pk or 0,
                               tenant=request.tenant)
    if ContractClauseLink.objects.filter(contract=contract, clause=clause).exists():
        messages.error(request,
                       f"'{clause.title}' is already drafted into this agreement.")
        return redirect("procurement:contract_detail", pk=pk)
    link = ContractClauseLink.objects.create(
        contract=contract, clause=clause, section_order=section)
    write_audit_log(request.user, contract, "update",
                    {"clause_added": clause.title})
    messages.success(request, f"Clause '{link.clause.title}' added at §{section}.")
    return redirect("procurement:contract_detail", pk=pk)


@login_required
@require_POST
@tenant_admin_required
def contract_remove_link(request, pk, link_id):
    contract = _get_contract(request, pk)
    link = get_object_or_404(ContractClauseLink, pk=link_id, contract=contract)
    title = link.clause.title
    link.delete()
    write_audit_log(request.user, contract, "update", {"clause_removed": title})
    messages.success(request, f"Clause '{title}' removed from the draft.")
    return redirect("procurement:contract_detail", pk=pk)


# -- e-signature verbs ----------------------------------------------------------------------------


@login_required
@require_POST
def contract_add_signer(request, pk):
    """Add one signature slot; the minted token is shown once, to be sent out-of-band."""
    contract = _get_contract(request, pk)
    form = ContractSignerForm(request.POST, tenant=request.tenant)
    if not form.is_valid():
        messages.error(request, "; ".join(
            str(errs[0]) for errs in form.errors.values()))
        return redirect("procurement:contract_detail", pk=pk)
    signer = form.save(commit=False)
    signer.contract = contract
    signer.tenant = request.tenant
    signer.order = contract.procurement_signers.count() + 1
    signer.save()
    write_audit_log(request.user, contract, "update",
                    {"signer_added": signer.signer_name})
    messages.success(request,
                     f"Signature slot {signer.order} added for {signer.signer_name} — "
                     f"send them their signing link:")
    messages.info(request, request.build_absolute_uri(
        reverse("procurement:contract_sign_page", args=[signer.token])))
    return redirect("procurement:contract_detail", pk=pk)


@login_required
@require_POST
def contract_remove_signer(request, pk, signer_id):
    """Remove a slot only while it is UNSIGNED — a response is evidence, keep it."""
    contract = _get_contract(request, pk)
    signer = get_object_or_404(ContractSigner, pk=signer_id, contract=contract)
    if signer.has_responded:
        messages.error(request,
                       "This signer has already responded — their record is part of "
                       "the agreement's history and cannot be removed.")
        return redirect("procurement:contract_detail", pk=pk)
    name = signer.signer_name
    signer.delete()
    write_audit_log(request.user, contract, "update", {"signer_removed": name})
    messages.success(request, f"Signature slot for {name} removed.")
    return redirect("procurement:contract_detail", pk=pk)


def contract_sign_page(request, token):
    """PUBLIC e-signature page — no login; the unguessable token IS the credential
    (crm 1.9's exact flow). GET stamps viewed_at; POST signs/declines under a row
    lock so two racing last-signer POSTs cannot double-write."""
    signer = get_object_or_404(
        ContractSigner.objects.select_related("contract"), token=token)
    contract = signer.contract
    already = signer.has_responded
    if request.method == "POST" and not already:
        with transaction.atomic():
            locked = (ContractSigner.objects.select_for_update()
                      .select_related("contract").get(pk=signer.pk))
            if locked.has_responded:
                pass  # lost a race — fall through to the already-responded render
            else:
                locked.ip_address = request.META.get("REMOTE_ADDR")
                if request.POST.get("action") == "decline":
                    locked.declined_at = timezone.now()
                    locked.save(update_fields=["declined_at", "ip_address"])
                else:
                    locked.signed_at = timezone.now()
                    locked.save(update_fields=["signed_at", "ip_address"])
        return redirect("procurement:contract_sign_page", token=token)
    if signer.viewed_at is None and not already:
        signer.viewed_at = timezone.now()
        signer.save(update_fields=["viewed_at"])
    remaining = contract.procurement_signers.filter(
        signed_at__isnull=True, declined_at__isnull=True).count()
    return render(request, "procurement/contractsmanagement/contracts/sign.html", {
        "signer": signer,
        "contract": contract,
        "already": already,
        "remaining_after": max(0, remaining - (0 if already else 1)),
        "links": list(contract.procurement_clause_links
                      .select_related("clause").order_by("section_order")),
    })
