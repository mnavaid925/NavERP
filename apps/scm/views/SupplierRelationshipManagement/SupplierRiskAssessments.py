"""SCM 4.2 SRM — SupplierRiskAssessment views."""
from apps.scm.views._common import *  # noqa: F401,F403
from apps.scm.views._helpers import _need_tenant, _supplier_parties
from apps.scm.models import SupplierRiskAssessment
from apps.scm.forms import SupplierRiskAssessmentForm


@login_required
def riskassessment_list(request):
    qs = SupplierRiskAssessment.objects.filter(tenant=request.tenant).select_related("party", "assessed_by")
    return crud_list(
        request, qs, "scm/srm/riskassessment/list.html",
        search_fields=["number", "party__name"],
        filters=[("status", "status", False), ("risk_level", "risk_level", False),
                 ("party", "party_id", True)],
        extra_context={
            "status_choices": SupplierRiskAssessment.STATUS_CHOICES,
            "level_choices": SupplierRiskAssessment.LEVEL_CHOICES,
            "parties": _supplier_parties(request.tenant),
        },
    )


@login_required
def riskassessment_create(request):
    if _need_tenant(request):
        return redirect("scm:riskassessment_list")
    return _riskassessment_form(request, instance=None)


@login_required
def riskassessment_edit(request, pk):
    obj = get_object_or_404(SupplierRiskAssessment, pk=pk, tenant=request.tenant)
    if obj.status in ("reviewed", "archived"):
        messages.error(request, "A reviewed or archived assessment can't be edited.")
        return redirect("scm:riskassessment_detail", pk=pk)
    return _riskassessment_form(request, instance=obj)


def _riskassessment_form(request, instance):
    is_edit = instance is not None
    if request.method == "POST":
        form = SupplierRiskAssessmentForm(request.POST, instance=instance, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            if not is_edit:
                obj.assessed_by = request.user
            obj.recompute_risk_level(save=False)  # derive level from the four factor scores
            obj.save()
            write_audit_log(request.user, obj, "update" if is_edit else "create",
                            {"risk_level": obj.risk_level})
            messages.success(request, f"Risk assessment {obj.number} saved.")
            return redirect("scm:riskassessment_detail", pk=obj.pk)
    else:
        form = SupplierRiskAssessmentForm(instance=instance, tenant=request.tenant)
    return render(request, "scm/srm/riskassessment/form.html",
                  {"form": form, "is_edit": is_edit, "obj": instance})


@login_required
def riskassessment_detail(request, pk):
    obj = get_object_or_404(
        SupplierRiskAssessment.objects.select_related("party", "assessed_by"), pk=pk, tenant=request.tenant)
    return render(request, "scm/srm/riskassessment/detail.html", {"obj": obj})


@login_required
@require_POST
def riskassessment_delete(request, pk):
    obj = get_object_or_404(SupplierRiskAssessment, pk=pk, tenant=request.tenant)
    if obj.status != "draft":
        messages.error(request, "Only a draft assessment can be deleted.")
        return redirect("scm:riskassessment_detail", pk=pk)
    return crud_delete(request, model=SupplierRiskAssessment, pk=pk, success_url="scm:riskassessment_list")


@login_required
@require_POST
def riskassessment_submit(request, pk):
    obj = get_object_or_404(SupplierRiskAssessment, pk=pk, tenant=request.tenant)
    if obj.status != "draft":
        messages.info(request, "This assessment has already been submitted.")
        return redirect("scm:riskassessment_detail", pk=pk)
    obj.status = "submitted"
    obj.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "submit"})
    messages.success(request, f"Assessment {obj.number} submitted.")
    return redirect("scm:riskassessment_detail", pk=pk)


@tenant_admin_required
@require_POST
def riskassessment_review(request, pk):
    """Sign off a submitted assessment — tenant-admin gated."""
    obj = get_object_or_404(SupplierRiskAssessment, pk=pk, tenant=request.tenant)
    if obj.status != "submitted":
        messages.info(request, "Only a submitted assessment can be reviewed.")
        return redirect("scm:riskassessment_detail", pk=pk)
    obj.status = "reviewed"
    obj.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "review"})
    messages.success(request, f"Assessment {obj.number} reviewed.")
    return redirect("scm:riskassessment_detail", pk=pk)
