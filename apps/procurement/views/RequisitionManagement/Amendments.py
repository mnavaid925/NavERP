"""Procurement 6.2 Requisition Management — RequisitionAmendments views.

**Requisition Cancellation/Amendment** bullet: a workflow to modify or cancel pending or approved
requisitions. Requesting is open to any workspace member (the requisitions are visible to the
whole workspace and the amendment names its filer); deciding is tenant-admin gated (the same
gate 4.1 puts on approve/reject) because ONLY the approve action mutates the
``scm.PurchaseRequisition`` spine. Every decision is recorded and audited; the amendment row
itself is the reviewable diff, and decided amendments are immutable — corrections are new
filings, never edits of the record.
"""
from django.db import transaction
from django.utils import timezone

from apps.core.crud import crud_list
from apps.procurement.forms import (
    AmendmentDecisionForm,
    RequisitionAmendmentForm,
    RequisitionAmendmentLineFormSet,
)
from apps.procurement.models import RequisitionAmendment
from apps.procurement.views._common import *  # noqa: F401,F403
from apps.scm.models import PurchaseRequisition

#: Line-form fields that count as "this row actually proposes something" when checking whether a
#: cancellation accidentally carries line changes.
_LINE_DATA_FIELDS = ("target_line", "item_description", "quantity", "estimated_unit_price")


@login_required
def amendment_list(request):
    qs = (RequisitionAmendment.objects.filter(tenant=request.tenant)
          .select_related("requisition", "requested_by", "decided_by"))
    return crud_list(
        request, qs, "procurement/requisitionmanagement/amendments/list.html",
        search_fields=["number", "reason"],
        filters=[("status", "status", False), ("type", "amendment_type", False)],
        extra_context={
            "status_choices": RequisitionAmendment.STATUS_CHOICES,
            "type_choices": RequisitionAmendment.AMENDMENT_TYPES,
        },
    )


@login_required
def amendment_detail(request, pk):
    obj = get_object_or_404(
        RequisitionAmendment.objects.select_related(
            "requisition", "requested_by", "decided_by"),
        pk=pk, tenant=request.tenant,
    )
    return render(request, "procurement/requisitionmanagement/amendments/detail.html", {
        "obj": obj,
        "lines": obj.lines.select_related("target_line").order_by("id"),
        "decision_form": AmendmentDecisionForm(),
    })


@login_required
def req_amendment_create(request, requisition_pk):
    """File an amendment against one requisition (any workspace member; an admin decides later).

    The status + one-open-amendment guards run INSIDE a row lock on the requisition, so two
    simultaneous filings cannot both slip past the one-pending-amendment rule.
    """
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before filing amendments.")
        return redirect("dashboard:home")

    with transaction.atomic():
        requisition = get_object_or_404(PurchaseRequisition.objects.select_for_update(),
                                        pk=requisition_pk, tenant=request.tenant)
        if requisition.status not in RequisitionAmendment.AMENDABLE_STATUSES:
            messages.error(request,
                           f"A {requisition.get_status_display().lower()} requisition cannot be "
                           f"amended — drafts can be edited directly; converted/cancelled ones "
                           f"are closed.")
            return redirect("procurement:req_detail", pk=requisition.pk)
        if RequisitionAmendment.has_open_for(requisition):
            messages.error(request,
                           f"Requisition {requisition.number} already has a pending amendment — "
                           f"decide it before filing another.")
            return redirect("procurement:req_detail", pk=requisition.pk)

        amendment = RequisitionAmendment(requisition=requisition, requested_by=request.user)
        if request.method == "POST":
            form = RequisitionAmendmentForm(request.POST, instance=amendment,
                                            tenant=request.tenant)
            formset = RequisitionAmendmentLineFormSet(request.POST, instance=amendment,
                                                      form_kwargs={"tenant": request.tenant})
            if form.is_valid() and formset.is_valid():
                filled = _formset_proposes_changes(formset)
                if form.cleaned_data.get("amendment_type") == "cancel" and filled:
                    form.add_error(None,
                                   "Line changes apply only to 'Amend details' — switch the "
                                   "type or remove the proposed line rows.")
                else:
                    amendment.tenant = request.tenant
                    amendment.requested_by = request.user
                    amendment.save()
                    formset.instance = amendment
                    formset.save()
                    write_audit_log(request.user, amendment, "create",
                                    {"requisition": requisition.number})
                    messages.success(request,
                                     f"Amendment {amendment.number} filed — it now waits for a "
                                     f"workspace admin to decide.")
                    return redirect("procurement:amendment_detail", pk=amendment.pk)
        else:
            form = RequisitionAmendmentForm(instance=amendment, tenant=request.tenant)
            formset = RequisitionAmendmentLineFormSet(instance=amendment,
                                                      form_kwargs={"tenant": request.tenant})

    return render(request, "procurement/requisitionmanagement/amendments/form.html", {
        "form": form,
        "formset": formset,
        "obj": None,
        "requisition": requisition,
        "requisition_lines": list(requisition.lines.order_by("id")),
    })


def _formset_proposes_changes(formset):
    """True when any non-deleted row of the formset actually proposes something."""
    for form in formset.forms:
        if not hasattr(form, "cleaned_data") or form.cleaned_data.get("DELETE"):
            continue
        data = form.cleaned_data
        if any(data.get(field) for field in _LINE_DATA_FIELDS):
            return True
        if data.get("action") == "remove":
            return True
    return False


@login_required
@tenant_admin_required
@require_POST
def amendment_approve(request, pk):
    """Decide YES and apply atomically. Tenant-admin gated: this is the one path that mutates an
    already-approved requisition. The amendment row is locked and its pending-ness re-checked
    INSIDE the transaction, so a double-submit cannot apply twice."""
    with transaction.atomic():
        obj = get_object_or_404(RequisitionAmendment.objects.select_for_update()
                                .select_related("requisition"),
                                pk=pk, tenant=request.tenant)
        if not obj.is_pending:
            messages.info(request, "This amendment has already been decided.")
            return redirect("procurement:amendment_detail", pk=pk)
        requisition = obj.requisition
        if requisition.status not in RequisitionAmendment.AMENDABLE_STATUSES:
            messages.error(request,
                           f"The requisition is now '{requisition.get_status_display()}' — "
                           f"there is nothing left to amend. Reject this amendment instead.")
            return redirect("procurement:amendment_detail", pk=pk)

        summary = obj.apply(request.user, note=request.POST.get("decision_note") or "")
        # The spine changed too — record it on the REQUISITION's trail so its timeline shows the
        # amendment landing, not just on the amendment's own row.
        write_audit_log(request.user, requisition, "update",
                        {"action": f"amendment_{obj.amendment_type}", "amendment": obj.number})
    write_audit_log(request.user, obj, "update", {"action": "approve", "applied": summary})
    messages.success(request, f"Amendment {obj.number} approved and applied ({summary}).")
    return redirect("procurement:req_detail", pk=requisition.pk)


@login_required
@tenant_admin_required
@require_POST
def amendment_reject(request, pk):
    with transaction.atomic():
        obj = get_object_or_404(RequisitionAmendment.objects.select_for_update()
                                .select_related("requisition"),
                                pk=pk, tenant=request.tenant)
        if not obj.is_pending:
            messages.info(request, "This amendment has already been decided.")
            return redirect("procurement:amendment_detail", pk=pk)
        note = (request.POST.get("decision_note") or "").strip()
        if not note:
            messages.error(request, "Give a reason when rejecting an amendment.")
            return redirect("procurement:amendment_detail", pk=pk)
        obj.status = "rejected"
        obj.decided_by = request.user
        obj.decided_at = timezone.now()
        obj.decision_note = note[:2000]
        obj.save(update_fields=["status", "decided_by", "decided_at", "decision_note",
                                "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "reject"})
    messages.success(request, f"Amendment {obj.number} rejected.")
    return redirect("procurement:amendment_detail", pk=pk)
