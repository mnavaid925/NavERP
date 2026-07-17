"""SCM 4.2 SRM — SupplierProfile views (onboarding lifecycle)."""
from apps.scm.views._common import *  # noqa: F401,F403
from apps.scm.views._common import _changed
from apps.scm.views._helpers import _need_tenant, _supplier_parties
from apps.scm.models import SupplierProfile
from apps.scm.forms import SupplierProfileForm


@login_required
def supplierprofile_list(request):
    qs = SupplierProfile.objects.filter(tenant=request.tenant).select_related("party", "approved_by")
    return crud_list(
        request, qs, "scm/srm/supplierprofile/list.html",
        search_fields=["party__name", "legal_name", "category", "country"],
        filters=[("onboarding_status", "onboarding_status", False), ("tier", "tier", False)],
        extra_context={
            "status_choices": SupplierProfile.ONBOARDING_CHOICES,
            "tier_choices": SupplierProfile.TIER_CHOICES,
        },
    )


@login_required
def supplierprofile_create(request):
    if _need_tenant(request):
        return redirect("scm:supplierprofile_list")
    return crud_create(
        request, form_class=SupplierProfileForm,
        template="scm/srm/supplierprofile/form.html",
        success_url="scm:supplierprofile_list",
    )


@login_required
def supplierprofile_edit(request, pk):
    obj = get_object_or_404(SupplierProfile, pk=pk, tenant=request.tenant)
    if not obj.is_editable:
        messages.error(request, "An approved or rejected supplier can't be edited — reopen it first.")
        return redirect("scm:supplierprofile_detail", pk=pk)
    return crud_edit(
        request, model=SupplierProfile, pk=pk, form_class=SupplierProfileForm,
        template="scm/srm/supplierprofile/form.html",
        # crud_edit does redirect(success_url) with no args, so this must be an argument-free route.
        success_url="scm:supplierprofile_list",
    )


@login_required
def supplierprofile_detail(request, pk):
    obj = get_object_or_404(
        SupplierProfile.objects.select_related("party", "approved_by"), pk=pk, tenant=request.tenant)
    return render(request, "scm/srm/supplierprofile/detail.html", {
        "obj": obj,
        "dd_progress": obj.due_diligence_progress(),
        "scorecards": obj.party.scm_scorecards.filter(tenant=request.tenant)[:5],
        "contracts": obj.party.scm_supplier_contracts.filter(tenant=request.tenant)[:5],
        "risk_assessments": obj.party.scm_risk_assessments.filter(tenant=request.tenant)[:5],
    })


@login_required
@require_POST
def supplierprofile_delete(request, pk):
    obj = get_object_or_404(SupplierProfile, pk=pk, tenant=request.tenant)
    if obj.onboarding_status != "draft":
        messages.error(request, "Only a draft supplier record can be deleted.")
        return redirect("scm:supplierprofile_detail", pk=pk)
    return crud_delete(request, model=SupplierProfile, pk=pk, success_url="scm:supplierprofile_list")


@login_required
@require_POST
def supplierprofile_submit(request, pk):
    """Move a draft into qualification/due-diligence review."""
    obj = get_object_or_404(SupplierProfile, pk=pk, tenant=request.tenant)
    if obj.onboarding_status not in ("draft", "qualification"):
        messages.info(request, "This supplier is already in review or decided.")
        return redirect("scm:supplierprofile_detail", pk=pk)
    obj.onboarding_status = "due_diligence"
    obj.save(update_fields=["onboarding_status", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "submit_for_dd"})
    messages.success(request, "Supplier moved to due-diligence review.")
    return redirect("scm:supplierprofile_detail", pk=pk)


@tenant_admin_required
@require_POST
def supplierprofile_approve(request, pk):
    """Approve a supplier for use. Tenant-admin gated + due-diligence must be complete."""
    obj = get_object_or_404(SupplierProfile, pk=pk, tenant=request.tenant)
    if obj.onboarding_status in ("approved",):
        messages.info(request, "This supplier is already approved.")
        return redirect("scm:supplierprofile_detail", pk=pk)
    if not obj.due_diligence_complete:
        messages.error(request, "Complete the due-diligence checklist before approving this supplier.")
        return redirect("scm:supplierprofile_detail", pk=pk)
    obj.onboarding_status = "approved"
    obj.approved_by = request.user
    obj.approved_at = timezone.now()
    obj.decision_note = (request.POST.get("decision_note") or "").strip()[:2000]
    obj.save(update_fields=["onboarding_status", "approved_by", "approved_at", "decision_note", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "approve"})
    messages.success(request, f"{obj.party.name} approved.")
    return redirect("scm:supplierprofile_detail", pk=pk)


@tenant_admin_required
@require_POST
def supplierprofile_reject(request, pk):
    obj = get_object_or_404(SupplierProfile, pk=pk, tenant=request.tenant)
    reason = (request.POST.get("decision_note") or "").strip()
    if not reason:
        messages.error(request, "Give a reason when rejecting a supplier.")
        return redirect("scm:supplierprofile_detail", pk=pk)
    obj.onboarding_status = "rejected"
    obj.approved_by = request.user
    obj.approved_at = timezone.now()
    obj.decision_note = reason[:2000]
    obj.save(update_fields=["onboarding_status", "approved_by", "approved_at", "decision_note", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "reject"})
    messages.success(request, f"{obj.party.name} rejected.")
    return redirect("scm:supplierprofile_detail", pk=pk)


@tenant_admin_required
@require_POST
def supplierprofile_suspend(request, pk):
    """Suspend an approved supplier (or reinstate a suspended one) — tenant-admin gated."""
    obj = get_object_or_404(SupplierProfile, pk=pk, tenant=request.tenant)
    if obj.onboarding_status == "suspended":
        obj.onboarding_status = "approved"
        action = "reinstate"
    elif obj.onboarding_status == "approved":
        obj.onboarding_status = "suspended"
        action = "suspend"
    else:
        messages.info(request, "Only an approved or suspended supplier can be toggled.")
        return redirect("scm:supplierprofile_detail", pk=pk)
    obj.save(update_fields=["onboarding_status", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": action})
    messages.success(request, f"{obj.party.name} {action}d.")
    return redirect("scm:supplierprofile_detail", pk=pk)
