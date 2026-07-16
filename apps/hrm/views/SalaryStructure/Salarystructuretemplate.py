"""HRM 3.13 Salary Structure — Salarystructuretemplate views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    JobGrade,
    SalaryStructureLine,
    SalaryStructureTemplate,
)
from apps.hrm.forms import (
    SalaryStructureLineForm,
    SalaryStructureTemplateForm,
)


# ============================================================ Salary Structure Templates (3.13)
@login_required
def salarystructuretemplate_list(request):
    return crud_list(
        request,
        SalaryStructureTemplate.objects.filter(tenant=request.tenant).select_related("job_grade"),
        "hrm/salary/salarystructuretemplate/list.html",
        search_fields=["name", "number"],
        filters=[("job_grade", "job_grade_id", True), ("is_active", "is_active", False)],
        extra_context={"job_grades": JobGrade.objects.filter(tenant=request.tenant).order_by("level_order", "name")},
    )


@login_required
def salarystructuretemplate_create(request):
    return crud_create(request, form_class=SalaryStructureTemplateForm,
                       template="hrm/salary/salarystructuretemplate/form.html",
                       success_url="hrm:salarystructuretemplate_list")


@login_required
def salarystructuretemplate_detail(request, pk):
    obj = get_object_or_404(
        SalaryStructureTemplate.objects.select_related("job_grade"), pk=pk, tenant=request.tenant)
    lines = list(obj.lines.select_related("pay_component").order_by("sequence", "id"))
    return render(request, "hrm/salary/salarystructuretemplate/detail.html", {
        "obj": obj,
        "lines": lines,
        # Compute the CTC total once from the already-fetched lines (avoids the computed_ctc_total
        # property re-issuing its own lines query for each of the two places the template shows it).
        "ctc_total": sum((ln.resolved_amount() for ln in lines), Decimal("0")),
        "line_form": SalaryStructureLineForm(tenant=request.tenant),
    })


@login_required
def salarystructuretemplate_edit(request, pk):
    return crud_edit(request, model=SalaryStructureTemplate, pk=pk, form_class=SalaryStructureTemplateForm,
                     template="hrm/salary/salarystructuretemplate/form.html",
                     success_url="hrm:salarystructuretemplate_list")


@login_required
@require_POST
def salarystructuretemplate_delete(request, pk):
    return crud_delete(request, model=SalaryStructureTemplate, pk=pk,
                       success_url="hrm:salarystructuretemplate_list")


# ------------------------------------------------------ Salary Structure Lines (inline on the template)
@login_required
@require_POST
def salarystructureline_add(request, template_pk):
    template = get_object_or_404(SalaryStructureTemplate, pk=template_pk, tenant=request.tenant)
    # Preset tenant+template on the instance so the form's clean() duplicate check sees the template
    # during validation and form.save() persists the right FK (mirrors timesheetentry_add).
    form = SalaryStructureLineForm(
        request.POST,
        instance=SalaryStructureLine(tenant=request.tenant, template=template),
        tenant=request.tenant)
    if form.is_valid():
        form.save()
        write_audit_log(request.user, template, "update", {"action": "line_add"})
        messages.success(request, "Component line added.")
        return redirect("hrm:salarystructuretemplate_detail", pk=template.pk)
    # Re-render the detail hub with the bound, errored add-form (field errors + typed input preserved).
    lines = list(template.lines.select_related("pay_component").order_by("sequence", "id"))
    return render(request, "hrm/salary/salarystructuretemplate/detail.html", {
        "obj": template,
        "lines": lines,
        "ctc_total": sum((ln.resolved_amount() for ln in lines), Decimal("0")),
        "line_form": form,
    })


@login_required
def salarystructureline_edit(request, pk):
    line = get_object_or_404(SalaryStructureLine.objects.select_related("template"), pk=pk, tenant=request.tenant)
    template = line.template
    if request.method == "POST":
        form = SalaryStructureLineForm(request.POST, instance=line, tenant=request.tenant)
        if form.is_valid():
            form.save()
            write_audit_log(request.user, template, "update", {"action": "line_edit"})
            messages.success(request, "Component line updated.")
            return redirect("hrm:salarystructuretemplate_detail", pk=template.pk)
    else:
        form = SalaryStructureLineForm(instance=line, tenant=request.tenant)
    return render(request, "hrm/salary/salarystructuretemplate/line_form.html",
                  {"form": form, "obj": line, "template": template, "is_edit": True})


@login_required
@require_POST
def salarystructureline_delete(request, pk):
    line = get_object_or_404(SalaryStructureLine.objects.select_related("template"), pk=pk, tenant=request.tenant)
    template_pk = line.template_id
    write_audit_log(request.user, line.template, "update", {"action": "line_delete"})
    line.delete()
    messages.success(request, "Component line removed.")
    return redirect("hrm:salarystructuretemplate_detail", pk=template_pk)
