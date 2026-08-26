"""Procurement 6.8 Contract Management — ContractAmendment views.

**Contract Amendment Tracking**: a register of proposed changes with the gated
decision verbs. Approve applies the proposal onto the spine agreement under the
CONTRACT row lock (the model's apply() contract); reject is terminal. Decisions are
admin-gated — they rewrite live spend terms (the same authority bar as 6.2/6.5).
"""
from django.db import transaction

from apps.core.crud import crud_list

from apps.procurement.forms import (
    ContractAmendmentDecisionForm,
    ContractAmendmentForm,
    amendable_contracts,
)
from apps.procurement.models import ContractAmendment
from apps.procurement.views._common import *  # noqa: F401,F403
from apps.scm.models import SupplierContract

STATUS_CHOICES = [value for value in ContractAmendment.STATUS_CHOICES]


@login_required
def camendment_list(request):
    qs = (ContractAmendment.objects.filter(tenant=request.tenant)
          .select_related("contract", "requested_by", "decided_by"))
    status = request.GET.get("status", "")
    if status:
        qs = qs.filter(status=status)
    return crud_list(
        request, qs, "procurement/contractsmanagement/amendments/list.html",
        search_fields=["number", "reason", "contract__number", "contract__title"],
        filters=[("status", "status", False)],
        extra_context={"status_choices": STATUS_CHOICES,
                       "is_admin": bool(request.user.is_authenticated
                                        and request.user.is_tenant_admin)},
    )


@login_required
def camendment_detail(request, pk):
    obj = get_object_or_404(
        ContractAmendment.objects.select_related("contract", "requested_by",
                                                 "decided_by"),
        pk=pk, tenant=request.tenant)
    return render(request,
                  "procurement/contractsmanagement/amendments/detail.html",
                  {"obj": obj,
                   # The decision forms (and their note capture) are admin-only.
                   "is_admin": bool(request.user.is_authenticated
                                    and request.user.is_tenant_admin)})


@login_required
def camendment_create(request):
    """File an amendment against one amendable agreement (?contract= preselects)."""
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before filing amendments.")
        return redirect("dashboard:home")
    contracts = amendable_contracts(request.tenant)
    if request.method == "POST":
        form = ContractAmendmentForm(request.POST)
        contract = get_object_or_404(SupplierContract,
                                     pk=request.POST.get("contract") or 0,
                                     tenant=request.tenant)
        if contract.status not in ContractAmendment.AMENDABLE_STATUSES:
            form.add_error(None, "That agreement's state does not accept amendments.")
        elif ContractAmendment.has_open_for(contract):
            form.add_error(
                None,
                f"{contract.number} already has a pending amendment — decide it first "
                f"(change control is sequential).")
        elif form.is_valid():
            # Sequential change control is DECIDED UNDER THE CONTRACT ROW LOCK: the
            # friendly pre-checks above sit outside any lock, so two filings racing
            # them could both pass — the locked re-check below cannot.
            amendment = None
            with transaction.atomic():
                locked = (SupplierContract.objects.select_for_update()
                          .get(pk=contract.pk))
                if locked.status not in ContractAmendment.AMENDABLE_STATUSES:
                    form.add_error(None,
                                   "That agreement's state does not accept amendments.")
                elif ContractAmendment.has_open_for(locked):
                    form.add_error(
                        None,
                        f"{locked.number} already has a pending amendment — decide it "
                        f"first (change control is sequential).")
                else:
                    amendment = form.save(commit=False)
                    amendment.contract = locked
                    amendment.tenant = request.tenant
                    amendment.requested_by = request.user
                    amendment.save()
            if amendment is not None:
                write_audit_log(request.user, amendment, "create")
                messages.success(request,
                                 f"Amendment {amendment.number} filed against "
                                 f"{contract.number}.")
                return redirect("procurement:camendment_detail", pk=amendment.pk)
    else:
        form = ContractAmendmentForm()
    return render(request,
                  "procurement/contractsmanagement/amendments/form.html",
                  {"form": form, "contracts": contracts,
                   "preselect": request.GET.get("contract", "")})


def _decide(request, pk, approve):
    obj = get_object_or_404(ContractAmendment, pk=pk, tenant=request.tenant)
    if obj.status != "pending":
        messages.error(request,
                       f"This amendment is already {obj.get_status_display().lower()}.")
        return redirect("procurement:camendment_detail", pk=pk)
    form = ContractAmendmentDecisionForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Invalid decision note.")
        return redirect("procurement:camendment_detail", pk=pk)
    note = form.cleaned_data.get("decision_note", "")
    with transaction.atomic():
        locked_amendment = (ContractAmendment.objects.select_for_update()
                            .get(pk=obj.pk))
        if locked_amendment.status != "pending":  # lost a decision race
            messages.error(request,
                           "The amendment was just decided by someone else.")
            return redirect("procurement:camendment_detail", pk=pk)
        if not approve:
            locked_amendment.status = "rejected"
            locked_amendment.decided_by = request.user
            locked_amendment.decided_at = timezone.now()
            locked_amendment.decision_note = note
            locked_amendment.save(update_fields=["status", "decided_by",
                                                 "decided_at", "decision_note",
                                                 "updated_at"])
        else:
            contract_locked = (SupplierContract.objects.select_for_update()
                               .get(pk=obj.contract_id))
            # The spine may have been terminated/expired/renewed while this amendment
            # sat pending — apply() writes live spend terms, so re-assert amendability
            # under the same lock that guards the write.
            if contract_locked.status not in ContractAmendment.AMENDABLE_STATUSES:
                messages.error(
                    request,
                    f"{contract_locked.number} is "
                    f"{contract_locked.get_status_display().lower()} — its terms are "
                    f"closed and amendment {locked_amendment.number} can no longer be "
                    f"applied.")
                return redirect("procurement:camendment_detail", pk=pk)
            applied = locked_amendment.apply(request.user, contract_locked, note)
            if not applied:
                messages.error(request,
                               "The amendment can no longer be applied — review it.")
                return redirect("procurement:camendment_detail", pk=pk)
    write_audit_log(request.user, locked_amendment,
                    "amendment_approve" if approve else "amendment_reject",
                    {"note": note})
    verb = "applied to" if approve else "rejected for"
    messages.success(request,
                     f"Amendment {locked_amendment.number} {verb} "
                     f"{locked_amendment.contract.number}.")
    return redirect("procurement:camendment_detail", pk=pk)


@login_required
@tenant_admin_required
@require_POST
def camendment_approve(request, pk):
    return _decide(request, pk, True)


@login_required
@tenant_admin_required
@require_POST
def camendment_reject(request, pk):
    return _decide(request, pk, False)
