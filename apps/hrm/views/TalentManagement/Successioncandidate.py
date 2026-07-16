"""HRM 3.38 Talent Management & Succession — Successioncandidate views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    SuccessionCandidate,
    SuccessionPlan,
)
from apps.hrm.forms import (
    SuccessionCandidateForm,
)


@tenant_admin_required
@require_POST
def successioncandidate_add(request, plan_pk):
    """Add a ranked successor to a plan's bench (inline on the plan detail — mirrors travelbooking_add)."""
    plan = get_object_or_404(SuccessionPlan, pk=plan_pk, tenant=request.tenant)
    form = SuccessionCandidateForm(request.POST,
                                   instance=SuccessionCandidate(tenant=request.tenant, plan=plan),
                                   tenant=request.tenant)
    if form.is_valid():
        try:
            # Savepoint: a duplicate-successor IntegrityError must roll back only this insert instead of
            # poisoning the surrounding request transaction (which would then raise
            # TransactionManagementError on the next query). Mirrors investmentdeclarationline_add.
            with transaction.atomic():
                form.save()
        except IntegrityError:
            messages.error(request, "That employee is already a successor on this plan.")
            return redirect("hrm:successionplan_detail", pk=plan.pk)
        write_audit_log(request.user, plan, "update", {"action": "candidate_add"})
        messages.success(request, "Successor added to the bench.")
    else:
        messages.error(request, "; ".join(f"{fld}: {errs[0]}" for fld, errs in form.errors.items()))
    return redirect("hrm:successionplan_detail", pk=plan.pk)


@tenant_admin_required
def successioncandidate_edit(request, pk):
    obj = get_object_or_404(SuccessionCandidate.objects.select_related("plan"), pk=pk, tenant=request.tenant)
    if request.method == "POST":
        form = SuccessionCandidateForm(request.POST, instance=obj, tenant=request.tenant)
        if form.is_valid():
            form.save()
            write_audit_log(request.user, obj.plan, "update", {"action": "candidate_edit"})
            messages.success(request, "Successor updated.")
            return redirect("hrm:successionplan_detail", pk=obj.plan_id)
    else:
        form = SuccessionCandidateForm(instance=obj, tenant=request.tenant)
    return render(request, "hrm/talent/successioncandidate/form.html",
                  {"form": form, "obj": obj, "plan": obj.plan, "is_edit": True})


@tenant_admin_required
@require_POST
def successioncandidate_delete(request, pk):
    obj = get_object_or_404(SuccessionCandidate.objects.select_related("plan"), pk=pk, tenant=request.tenant)
    plan_pk = obj.plan_id
    obj.delete()
    write_audit_log(request.user, obj.plan, "update", {"action": "candidate_delete"})
    messages.success(request, "Successor removed from the bench.")
    return redirect("hrm:successionplan_detail", pk=plan_pk)
