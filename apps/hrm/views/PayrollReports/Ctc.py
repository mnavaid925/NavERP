"""HRM 3.31 Payroll Reports — Ctc views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.PayrollReports._helpers import _grade_choices, _report_job_grade
from apps.hrm.models import (
    EmployeeSalaryStructure,
    PayComponent,
    SalaryStructureLine,
)
from apps.hrm.views.HRReports._helpers import _dept_choices, _report_department
from apps.hrm.views.PayrollReports._helpers import _grade_choices, _report_job_grade


@tenant_admin_required
def ctc_report(request):
    tenant = request.tenant
    dept = _report_department(request, tenant)
    grade = _report_job_grade(request, tenant)
    ctx = {"department": dept, "department_choices": _dept_choices(tenant), "grade": grade,
           "grade_choices": _grade_choices(tenant), "rows": [], "total_ctc": 0, "avg_ctc": 0,
           "headcount": 0, "mix_labels": "[]", "mix_values": "[]"}
    if tenant is not None:
        structs = list(
            EmployeeSalaryStructure.objects.filter(tenant=tenant, status="active")
            .select_related("employee__party", "employee__employment__org_unit", "template__job_grade")
            .filter(**({"employee__employment__org_unit": dept} if dept else {}))
            .filter(**({"template__job_grade": grade} if grade else {})))
        comp_labels = dict(PayComponent.COMPONENT_TYPE_CHOICES)
        template_lines = {}   # template_id -> [SalaryStructureLine]; bounded by DISTINCT templates, not employees
        component_totals = {}
        rows = []
        total = Decimal("0")
        for s in structs:
            ctc = s.annual_ctc_amount or Decimal("0")
            total += ctc
            grade_name = s.template.job_grade.name if (s.template_id and s.template.job_grade_id) else "—"
            rows.append({"employee": s.employee.name,
                         "department": s.employee.department.name if s.employee.department else "—",
                         "grade": grade_name, "annual_ctc": ctc,
                         "monthly": (ctc / Decimal("12")).quantize(Decimal("0.01"))})
            tid = s.template_id
            if tid is None:
                continue
            if tid not in template_lines:
                template_lines[tid] = list(SalaryStructureLine.objects.filter(tenant=tenant, template_id=tid)
                                           .select_related("pay_component"))
            for line in template_lines[tid]:
                ct = line.pay_component.component_type
                component_totals[ct] = component_totals.get(ct, Decimal("0")) + line.resolved_amount(ctc)
        ctx["rows"] = rows
        ctx["headcount"] = len(structs)
        ctx["total_ctc"] = total
        ctx["avg_ctc"] = round(total / len(structs), 2) if structs else 0
        mix = sorted(component_totals.items(), key=lambda kv: kv[1], reverse=True)
        ctx["mix_labels"] = json.dumps([comp_labels.get(k, k) for k, _ in mix])
        ctx["mix_values"] = json.dumps([float(v) for _, v in mix])
    return render(request, "hrm/reports/ctc.html", ctx)
