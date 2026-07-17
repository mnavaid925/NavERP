"""SCM 4.2 SRM — SupplierScorecard views (incl. derive-from-signals)."""
from apps.scm.views._common import *  # noqa: F401,F403
from apps.scm.views._helpers import _need_tenant, _supplier_parties
from apps.scm.models import SupplierScorecard
from apps.scm.forms import SupplierScorecardForm


@login_required
def scorecard_list(request):
    qs = SupplierScorecard.objects.filter(tenant=request.tenant).select_related("party")
    return crud_list(
        request, qs, "scm/srm/scorecard/list.html",
        search_fields=["number", "party__name"],
        filters=[("status", "status", False), ("party", "party_id", True)],
        extra_context={
            "status_choices": SupplierScorecard.STATUS_CHOICES,
            "parties": _supplier_parties(request.tenant),
        },
    )


@login_required
def scorecard_create(request):
    if _need_tenant(request):
        return redirect("scm:scorecard_list")
    return crud_create(
        request, form_class=SupplierScorecardForm,
        template="scm/srm/scorecard/form.html", success_url="scm:scorecard_list",
    )


@login_required
def scorecard_edit(request, pk):
    obj = get_object_or_404(SupplierScorecard, pk=pk, tenant=request.tenant)
    if obj.status == "archived":
        messages.error(request, "An archived scorecard can't be edited.")
        return redirect("scm:scorecard_detail", pk=pk)
    return crud_edit(
        request, model=SupplierScorecard, pk=pk, form_class=SupplierScorecardForm,
        template="scm/srm/scorecard/form.html", success_url="scm:scorecard_list",
    )


@login_required
def scorecard_detail(request, pk):
    obj = get_object_or_404(SupplierScorecard.objects.select_related("party"), pk=pk, tenant=request.tenant)
    obj.recompute_overall(save=True)  # keep the derived blend fresh vs any hand-edited dimensions
    return render(request, "scm/srm/scorecard/detail.html", {"obj": obj})


@login_required
@require_POST
def scorecard_delete(request, pk):
    obj = get_object_or_404(SupplierScorecard, pk=pk, tenant=request.tenant)
    if obj.status != "draft":
        messages.error(request, "Only a draft scorecard can be deleted.")
        return redirect("scm:scorecard_detail", pk=pk)
    return crud_delete(request, model=SupplierScorecard, pk=pk, success_url="scm:scorecard_list")


@login_required
@require_POST
def scorecard_recompute(request, pk):
    """Derive the four dimension scores from real 4.1 procurement signals for this period."""
    obj = get_object_or_404(SupplierScorecard, pk=pk, tenant=request.tenant)
    if obj.manual_override:
        messages.info(request, "This scorecard is set to manual override — signals are not applied.")
        return redirect("scm:scorecard_detail", pk=pk)
    obj.recompute_from_signals(save=True)
    write_audit_log(request.user, obj, "update", {"action": "recompute_from_signals"})
    messages.success(request, "Scores recomputed from procurement history.")
    return redirect("scm:scorecard_detail", pk=pk)


@login_required
@require_POST
def scorecard_publish(request, pk):
    obj = get_object_or_404(SupplierScorecard, pk=pk, tenant=request.tenant)
    if obj.status != "draft":
        messages.info(request, "Only a draft scorecard can be published.")
        return redirect("scm:scorecard_detail", pk=pk)
    obj.recompute_overall(save=False)
    obj.status = "published"
    obj.save(update_fields=["status", "overall_score", "grade", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "publish"})
    messages.success(request, f"Scorecard {obj.number} published.")
    return redirect("scm:scorecard_detail", pk=pk)
