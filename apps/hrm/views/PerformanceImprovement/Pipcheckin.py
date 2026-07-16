"""HRM 3.21 Performance Improvement — Pipcheckin views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.PerformanceImprovement._helpers import _can_edit_checkin, _can_view_pip
from apps.hrm.models import (
    PIPCheckIn,
    PerformanceImprovementPlan,
)
from apps.hrm.forms import (
    PIPCheckInForm,
)
from apps.hrm.views.PerformanceImprovement._helpers import _can_edit_checkin, _can_view_pip


# ------------------------------------------------------------ PIPCheckIn (nested under a PIP)
@login_required
def pipcheckin_create(request, pip_pk):
    pip = get_object_or_404(PerformanceImprovementPlan, pk=pip_pk, tenant=request.tenant)
    if not _can_view_pip(request, pip):   # subject/manager/admin may log a check-in
        raise PermissionDenied("You do not have access to this plan.")
    if pip.status == "closed":
        messages.error(request, "This plan is closed — check-ins can no longer be added.")
        return redirect("hrm:pip_detail", pk=pip.pk)
    if request.method == "POST":
        form = PIPCheckInForm(request.POST,
                              instance=PIPCheckIn(tenant=request.tenant, pip=pip), tenant=request.tenant)
        if form.is_valid():
            try:
                with transaction.atomic():
                    ci = form.save(commit=False)
                    ci.completed_at = timezone.now()  # a logged check-in records a held checkpoint
                    ci.save()
                write_audit_log(request.user, ci, "create")
                messages.success(request, "Check-in logged.")
            except IntegrityError:
                messages.error(request, "Could not log that check-in.")
            return redirect("hrm:pip_detail", pk=pip.pk)
    else:
        form = PIPCheckInForm(instance=PIPCheckIn(tenant=request.tenant, pip=pip), tenant=request.tenant)
    return render(request, "hrm/performance/pipcheckin/form.html", {"form": form, "is_edit": False, "pip": pip})


@login_required
def pipcheckin_detail(request, pk):
    item = get_object_or_404(
        PIPCheckIn.objects.select_related("pip__subject__party", "pip__manager__party"), pk=pk, tenant=request.tenant)
    if not _can_view_pip(request, item.pip):
        raise PermissionDenied("You do not have access to this check-in.")
    return render(request, "hrm/performance/pipcheckin/detail.html",
                  {"obj": item, "pip": item.pip, "can_manage_checkin": _can_edit_checkin(request, item)})


@login_required
def pipcheckin_edit(request, pk):
    item = get_object_or_404(PIPCheckIn.objects.select_related("pip"), pk=pk, tenant=request.tenant)
    if not _can_edit_checkin(request, item):
        messages.error(request, "Only the plan's manager or a tenant admin can edit a check-in, and not once the plan is closed.")
        return redirect("hrm:pip_detail", pk=item.pip_id)
    if request.method == "POST":
        form = PIPCheckInForm(request.POST, instance=item, tenant=request.tenant)
        if form.is_valid():
            form.save()
            write_audit_log(request.user, item, "update")
            messages.success(request, "Check-in updated.")
            return redirect("hrm:pip_detail", pk=item.pip_id)
    else:
        form = PIPCheckInForm(instance=item, tenant=request.tenant)
    return render(request, "hrm/performance/pipcheckin/form.html",
                  {"form": form, "is_edit": True, "obj": item, "pip": item.pip})


@login_required
@require_POST
def pipcheckin_delete(request, pk):
    item = get_object_or_404(PIPCheckIn.objects.select_related("pip"), pk=pk, tenant=request.tenant)
    pip = item.pip
    if not _can_edit_checkin(request, item):
        messages.error(request, "Only the plan's manager or a tenant admin can delete a check-in, and not once the plan is closed.")
        return redirect("hrm:pip_detail", pk=pip.pk)
    write_audit_log(request.user, item, "delete")
    item.delete()
    messages.success(request, "Check-in deleted.")
    return redirect("hrm:pip_detail", pk=pip.pk)
