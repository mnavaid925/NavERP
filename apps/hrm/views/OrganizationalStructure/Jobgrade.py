"""HRM 3.2 Organizational Structure — Jobgrade views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    Designation,
    JobGrade,
)
from apps.hrm.forms import (
    JobGradeForm,
)


# ============================================================ Job Grades (3.2)
@login_required
def jobgrade_list(request):
    return crud_list(
        request,
        JobGrade.objects.filter(tenant=request.tenant)
        .annotate(designation_count=Count("designations")).order_by("level_order", "name"),
        "hrm/organization/jobgrade/list.html",
        search_fields=["name", "description"],
        filters=[("is_active", "is_active", False)],
    )


@login_required
def jobgrade_create(request):
    return crud_create(request, form_class=JobGradeForm,
                       template="hrm/organization/jobgrade/form.html",
                       success_url="hrm:jobgrade_list")


@login_required
def jobgrade_detail(request, pk):
    obj = get_object_or_404(
        JobGrade.objects.annotate(designation_count=Count("designations")),
        pk=pk, tenant=request.tenant)
    return render(request, "hrm/organization/jobgrade/detail.html", {
        "obj": obj,
        "designations": Designation.objects.filter(tenant=request.tenant, job_grade=obj)
        .select_related("department")[:50],
        "designation_count": obj.designation_count,
    })


@login_required
def jobgrade_edit(request, pk):
    return crud_edit(request, model=JobGrade, pk=pk, form_class=JobGradeForm,
                     template="hrm/organization/jobgrade/form.html",
                     success_url="hrm:jobgrade_list")


@login_required
@require_POST
def jobgrade_delete(request, pk):
    obj = get_object_or_404(JobGrade, pk=pk, tenant=request.tenant)
    if Designation.objects.filter(tenant=request.tenant, job_grade=obj).exists():
        messages.error(request, "Cannot delete a grade assigned to designations. "
                                "Deactivate it instead.")
        return redirect("hrm:jobgrade_detail", pk=obj.pk)
    write_audit_log(request.user, obj, "delete")
    obj.delete()
    messages.success(request, "Job grade deleted.")
    return redirect("hrm:jobgrade_list")
