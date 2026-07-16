"""HRM 3.31 Payroll Reports — _helpers views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    InvestmentDeclaration,
    JobGrade,
)


# =============================================================================================
# 3.31 Payroll Reports (derived, read-only — NO models). Aggregate over the built payroll engine
# (PayrollCycle/Payslip/PayslipLine/EmployeeSalaryStructure/TaxComputation/InvestmentDeclaration/
# StatutoryReturn/EmployeeStatutoryIdentifier/CostCenterProfile). All @tenant_admin_required, every
# query tenant-scoped, every rate guards div-by-zero, ?filters (cycle/department/financial_year/
# scheme/status/grade/cost_center) resolved tenant-scoped (IDOR-safe). Statutory government IDs
# (UAN/PF/ESI) are rendered ONLY via masked_*() — never the raw value.
#
# Cost-centre attribution (the one non-obvious join): core.Employment.org_unit is ALWAYS a
# DEPARTMENT-kind OrgUnit; a cost centre is reached from a department via
# hrm.DepartmentProfile.cost_center. Matching only a direct org_unit==cost_center would report zero
# spend for every cost centre on the seeded data, so cost_center_report folds each employee's org
# unit into its department's mapped cost centre (with a defensive direct-assignment branch).
# =============================================================================================
def _fy_choices(tenant):
    """Distinct Indian financial years present on the tenant's tax declarations, newest first."""
    if tenant is None:
        return []
    return sorted(
        InvestmentDeclaration.objects.filter(tenant=tenant)
        .order_by().values_list("financial_year", flat=True).distinct(),
        reverse=True)


def _report_financial_year(request, tenant):
    """Resolve ?financial_year to one the tenant actually has (never trust an arbitrary string).
    Returns (fy, choices); fy defaults to the latest present, or "" when the tenant has none yet."""
    choices = _fy_choices(tenant)
    fy = (request.GET.get("financial_year") or "").strip()
    if fy in choices:
        return fy, choices
    return (choices[0] if choices else ""), choices


def _cc_choices(tenant):
    if tenant is None:
        return OrgUnit.objects.none()
    # Only cost centres that HAVE a CostCenterProfile — the report renders profile rows, so offering
    # a profile-less cost centre would filter to a misleading empty result (its spend actually lands
    # in the Unassigned callout of the unfiltered view).
    return OrgUnit.objects.filter(tenant=tenant, kind="cost_center",
                                  cost_center_profile__isnull=False).order_by("name")


def _report_cost_center(request, tenant):
    """Resolve ?cost_center to a tenant-scoped, PROFILED cost-centre OrgUnit, or None (IDOR-safe). A
    profile-less / garbage / cross-tenant pk resolves to None -> the report shows all cost centres
    (so that spend surfaces in the Unassigned callout) rather than a misleading empty state."""
    pk = (request.GET.get("cost_center") or "").strip()
    if tenant is not None and pk.isdecimal() and len(pk) <= 18:
        return OrgUnit.objects.filter(tenant=tenant, kind="cost_center",
                                      cost_center_profile__isnull=False, pk=int(pk)).first()
    return None


def _grade_choices(tenant):
    if tenant is None:
        return JobGrade.objects.none()
    return JobGrade.objects.filter(tenant=tenant, is_active=True).order_by("level_order", "name")


def _report_job_grade(request, tenant):
    """Resolve ?grade to a tenant-scoped JobGrade, or None (IDOR-safe)."""
    pk = (request.GET.get("grade") or "").strip()
    if tenant is not None and pk.isdecimal() and len(pk) <= 18:
        return JobGrade.objects.filter(tenant=tenant, pk=int(pk)).first()
    return None
