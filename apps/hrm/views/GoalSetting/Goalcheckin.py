"""HRM 3.18 Goal Setting — Goalcheckin views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.GoalSetting._helpers import _current_employee_profile
from apps.hrm.models import (
    GoalCheckIn,
    KeyResult,
)
from apps.hrm.forms import (
    GoalCheckInForm,
)
from apps.hrm.views.GoalSetting._helpers import _current_employee_profile


# ---------------------------------------------------------- GoalCheckIn (3.18.5 Goal Tracking log)
@login_required
def goalcheckin_list(request):
    return crud_list(
        request,
        GoalCheckIn.objects.filter(tenant=request.tenant)
        .select_related("key_result", "created_by__party"),  # template uses key_result.title only
        "hrm/performance/goalcheckin/list.html",
        search_fields=("number", "key_result__title", "comment"),
        filters=[("confidence", "confidence", False), ("key_result", "key_result_id", True)],
        extra_context={
            "confidence_choices": GoalCheckIn.CONFIDENCE_CHOICES,
            "key_results": (KeyResult.objects.filter(tenant=request.tenant)
                            .select_related("objective").order_by("title")),
        },
    )


@login_required
def goalcheckin_create(request, keyresult_pk):
    kr = get_object_or_404(KeyResult.objects.select_related("objective"), pk=keyresult_pk, tenant=request.tenant)
    if request.method == "POST":
        checkin = GoalCheckIn(tenant=request.tenant, key_result=kr,
                              created_by=_current_employee_profile(request))
        form = GoalCheckInForm(request.POST, instance=checkin, tenant=request.tenant)
        if form.is_valid():
            form.save()  # GoalCheckIn.save() advances key_result.current_value
            write_audit_log(request.user, kr, "update", {"action": "check_in"})
            messages.success(request, "Check-in logged.")
            return redirect("hrm:keyresult_detail", pk=kr.pk)
    else:
        form = GoalCheckInForm(instance=GoalCheckIn(tenant=request.tenant, key_result=kr),
                               tenant=request.tenant)
    return render(request, "hrm/performance/goalcheckin/form.html", {
        "form": form, "is_edit": False, "key_result": kr, "objective": kr.objective})


@login_required
def goalcheckin_detail(request, pk):
    return crud_detail(request, model=GoalCheckIn, pk=pk,
                       template="hrm/performance/goalcheckin/detail.html",
                       select_related=("key_result__objective", "created_by__party"))


@login_required
@require_POST
def goalcheckin_delete(request, pk):
    obj = get_object_or_404(GoalCheckIn.objects.select_related("key_result"), pk=pk, tenant=request.tenant)
    kr_pk = obj.key_result_id
    write_audit_log(request.user, obj, "delete")
    obj.delete()
    messages.success(request, "Check-in deleted.")
    return redirect("hrm:keyresult_detail", pk=kr_pk)
