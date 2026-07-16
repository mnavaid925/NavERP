"""HRM 3.5 Job Requisition — Jobdescriptiontemplate views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    Designation,
    JobDescriptionTemplate,
    JobRequisition,
)
from apps.hrm.forms import (
    JobDescriptionTemplateForm,
)


# ============================================================ 3.5 Job Requisition
# Job Description Templates — reusable JD library (copy-on-apply onto a requisition).
@login_required
def jobdescriptiontemplate_list(request):
    return crud_list(
        request,
        JobDescriptionTemplate.objects.filter(tenant=request.tenant).select_related("designation"),
        "hrm/recruitment/jobdescriptiontemplate/list.html",
        search_fields=["number", "name", "jd_summary", "designation__name"],
        filters=[("is_active", "is_active", False), ("designation", "designation_id", True)],
        extra_context={"designations": Designation.objects.filter(tenant=request.tenant, is_active=True)
                       .order_by("name")},
    )


@tenant_admin_required  # the shared JD template library is HR-config — admin-managed
def jobdescriptiontemplate_create(request):
    return crud_create(request, form_class=JobDescriptionTemplateForm,
                       template="hrm/recruitment/jobdescriptiontemplate/form.html",
                       success_url="hrm:jobdescriptiontemplate_list")


@login_required
def jobdescriptiontemplate_detail(request, pk):
    obj = get_object_or_404(
        JobDescriptionTemplate.objects.select_related("designation"), pk=pk, tenant=request.tenant)
    linked_reqs = (JobRequisition.objects.filter(tenant=request.tenant, template=obj)
                   .order_by("-created_at")[:10])
    return render(request, "hrm/recruitment/jobdescriptiontemplate/detail.html",
                  {"obj": obj, "linked_reqs": linked_reqs})


@tenant_admin_required  # the shared JD template library is HR-config — admin-managed
def jobdescriptiontemplate_edit(request, pk):
    return crud_edit(request, model=JobDescriptionTemplate, pk=pk,
                     form_class=JobDescriptionTemplateForm,
                     template="hrm/recruitment/jobdescriptiontemplate/form.html",
                     success_url="hrm:jobdescriptiontemplate_list")


@tenant_admin_required  # the shared JD template library is HR-config — admin-managed
@require_POST
def jobdescriptiontemplate_delete(request, pk):
    obj = get_object_or_404(JobDescriptionTemplate, pk=pk, tenant=request.tenant)
    # Guard: a template referenced by requisitions is kept for the record — deactivate instead.
    if JobRequisition.objects.filter(tenant=request.tenant, template=obj).exists():
        messages.error(request, "Cannot delete a template used by requisitions. Deactivate it instead.")
        return redirect("hrm:jobdescriptiontemplate_detail", pk=obj.pk)
    write_audit_log(request.user, obj, "delete")
    obj.delete()
    messages.success(request, "Job description template deleted.")
    return redirect("hrm:jobdescriptiontemplate_list")
