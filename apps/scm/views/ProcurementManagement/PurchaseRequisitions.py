"""SCM 4.1 Procurement Management — PurchaseRequisitions views."""
from apps.scm.views._common import *  # noqa: F401,F403
from apps.scm.views._helpers import _need_tenant
from apps.scm.models import (
    PurchaseRequisition,
)
from apps.scm.forms import (
    PurchaseRequisitionForm,
    PurchaseRequisitionLineFormSet,
)


@login_required
def requisition_list(request):
    qs = (PurchaseRequisition.objects
          .filter(tenant=request.tenant)
          .select_related("requester", "org_unit", "budget", "currency"))
    return crud_list(
        request, qs, "scm/procurement/requisition/list.html",
        search_fields=["number", "title", "justification"],
        filters=[("status", "status", False), ("org_unit", "org_unit_id", True)],
        extra_context={
            "status_choices": PurchaseRequisition.STATUS_CHOICES,
            "org_units": _org_units(request.tenant),
        },
    )


def _org_units(tenant):
    from apps.core.models import OrgUnit
    if tenant is None:
        return OrgUnit.objects.none()
    return OrgUnit.objects.filter(tenant=tenant)


@login_required
def requisition_create(request):
    return _requisition_form(request, instance=None)


@login_required
def requisition_edit(request, pk):
    obj = get_object_or_404(PurchaseRequisition, pk=pk, tenant=request.tenant)
    if not obj.is_editable:
        messages.error(request, "Only a draft or pending requisition can be edited.")
        return redirect("scm:requisition_detail", pk=pk)
    return _requisition_form(request, instance=obj)


def _requisition_form(request, instance):
    if instance is None and _need_tenant(request):
        return redirect("scm:requisition_list")
    is_edit = instance is not None
    if request.method == "POST":
        form = PurchaseRequisitionForm(request.POST, request.FILES, instance=instance, tenant=request.tenant)
        formset = PurchaseRequisitionLineFormSet(request.POST, instance=instance,
                                                 form_kwargs={"tenant": request.tenant})
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                req = form.save(commit=False)
                req.tenant = request.tenant
                if not is_edit:
                    req.requester = request.user
                req.save()
                formset.instance = req
                formset.save()
                req.recalc_totals()
            write_audit_log(request.user, req, "update" if is_edit else "create")
            messages.success(request, f"Requisition {req.number} saved.")
            return redirect("scm:requisition_detail", pk=req.pk)
    else:
        form = PurchaseRequisitionForm(instance=instance, tenant=request.tenant)
        formset = PurchaseRequisitionLineFormSet(instance=instance, form_kwargs={"tenant": request.tenant})
    return render(request, "scm/procurement/requisition/form.html",
                  {"form": form, "formset": formset, "is_edit": is_edit, "obj": instance})


@login_required
def requisition_detail(request, pk):
    obj = get_object_or_404(
        PurchaseRequisition.objects.select_related("requester", "org_unit", "budget", "currency", "approved_by"),
        pk=pk, tenant=request.tenant,
    )
    tier_code, tier_label = obj.approval_tier()
    return render(request, "scm/procurement/requisition/detail.html", {
        "obj": obj,
        "lines": obj.lines.select_related("gl_account"),
        "budget_check": obj.budget_check(),
        "tier_code": tier_code,
        "tier_label": tier_label,
        "rfqs": obj.rfqs.only("id", "number", "title", "status"),
        "purchase_orders": obj.purchase_orders.select_related("vendor").only(
            "id", "number", "status", "total", "vendor__name"),
    })


@login_required
@require_POST
def requisition_delete(request, pk):
    obj = get_object_or_404(PurchaseRequisition, pk=pk, tenant=request.tenant)
    if obj.status != "draft":
        messages.error(request, "Only a draft requisition can be deleted.")
        return redirect("scm:requisition_detail", pk=pk)
    return crud_delete(request, model=PurchaseRequisition, pk=pk, success_url="scm:requisition_list")


@login_required
@require_POST
def requisition_submit(request, pk):
    """Draft -> pending approval. Any staff member may submit their own request."""
    obj = get_object_or_404(PurchaseRequisition, pk=pk, tenant=request.tenant)
    if obj.status != "draft":
        messages.info(request, "This requisition has already been submitted.")
        return redirect("scm:requisition_detail", pk=pk)
    if not obj.lines.exists():
        messages.error(request, "Add at least one line before submitting.")
        return redirect("scm:requisition_detail", pk=pk)
    obj.recalc_totals()
    obj.status = "pending_approval"
    obj.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "submit"})
    messages.success(request, f"Requisition {obj.number} submitted for approval.")
    return redirect("scm:requisition_detail", pk=pk)


@tenant_admin_required
@require_POST
def requisition_approve(request, pk):
    """Approve a pending requisition.

    Tenant-admin gated: approving is what commits budget, so it must never be self-service. The
    amount tier is surfaced on the detail page; elevated tiers are flagged there for the approver.
    """
    obj = get_object_or_404(PurchaseRequisition, pk=pk, tenant=request.tenant)
    if obj.status != "pending_approval":
        messages.info(request, "This requisition is not awaiting approval.")
        return redirect("scm:requisition_detail", pk=pk)
    obj.recalc_totals()
    obj.status = "approved"
    obj.approved_by = request.user
    obj.approved_at = timezone.now()
    obj.decision_note = (request.POST.get("decision_note") or "").strip()[:2000]
    obj.save(update_fields=["status", "approved_by", "approved_at", "decision_note", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "approve", "tier": obj.approval_tier()[0]})
    messages.success(request, f"Requisition {obj.number} approved.")
    return redirect("scm:requisition_detail", pk=pk)


@tenant_admin_required
@require_POST
def requisition_reject(request, pk):
    obj = get_object_or_404(PurchaseRequisition, pk=pk, tenant=request.tenant)
    if obj.status != "pending_approval":
        messages.info(request, "This requisition is not awaiting approval.")
        return redirect("scm:requisition_detail", pk=pk)
    reason = (request.POST.get("decision_note") or "").strip()
    if not reason:
        messages.error(request, "Give a reason when rejecting a requisition.")
        return redirect("scm:requisition_detail", pk=pk)
    obj.status = "rejected"
    obj.approved_by = request.user
    obj.approved_at = timezone.now()
    obj.decision_note = reason[:2000]
    obj.save(update_fields=["status", "approved_by", "approved_at", "decision_note", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "reject"})
    messages.success(request, f"Requisition {obj.number} rejected.")
    return redirect("scm:requisition_detail", pk=pk)
