"""HRM 3.16 Tax & Investment — Taxcomputation views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.TaxInvestment._helpers import _computation_breakdown
from apps.hrm.models import (
    EmployeeProfile,
    TaxComputation,
)
from apps.hrm.forms import (
    TaxComputationForm,
)
from apps.hrm.views.TaxInvestment._helpers import _computation_breakdown


# ---------------------------------------------- TaxComputation (engine + Form 16 tie-in)
@login_required
def taxcomputation_list(request):
    return crud_list(
        request,
        # No declaration join — the list template renders only scalar fields + employee.party.name;
        # declaration is loaded on the detail/form16_partb views where it's actually shown.
        TaxComputation.objects.filter(tenant=request.tenant).select_related("employee__party"),
        "hrm/tax/taxcomputation/list.html",
        search_fields=["number", "employee__party__name"],
        filters=[("financial_year", "financial_year", False),
                 ("computation_type", "computation_type", False), ("employee", "employee_id", True)],
        extra_context={
            "computation_type_choices": TaxComputation.COMPUTATION_TYPE_CHOICES,
            "employees": EmployeeProfile.objects.filter(tenant=request.tenant).select_related("party"),
        },
    )


@login_required
def taxcomputation_create(request):
    return crud_create(request, form_class=TaxComputationForm,
                       template="hrm/tax/taxcomputation/form.html", success_url="hrm:taxcomputation_list")


@login_required
def taxcomputation_detail(request, pk):
    obj = get_object_or_404(
        TaxComputation.objects.select_related("employee__party", "declaration", "statutory_return"),
        pk=pk, tenant=request.tenant)
    return render(request, "hrm/tax/taxcomputation/detail.html", {
        "obj": obj,
        "breakdown": _computation_breakdown(obj),
        "lines": obj.declaration.lines.all(),
    })


@login_required
def taxcomputation_edit(request, pk):
    return crud_edit(request, model=TaxComputation, pk=pk, form_class=TaxComputationForm,
                     template="hrm/tax/taxcomputation/form.html", success_url="hrm:taxcomputation_list")


@login_required
@require_POST
def taxcomputation_delete(request, pk):
    return crud_delete(request, model=TaxComputation, pk=pk, success_url="hrm:taxcomputation_list")


@tenant_admin_required
@require_POST
def taxcomputation_generate(request, pk):
    """(Re)run the tax engine — mirrors statutoryreturn_generate's idempotent re-aggregate pattern."""
    obj = get_object_or_404(TaxComputation, pk=pk, tenant=request.tenant)
    try:
        obj.recompute()
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
        return redirect("hrm:taxcomputation_detail", pk=obj.pk)
    write_audit_log(request.user, obj, "update",
                    {"action": "generate", "tax_payable": str(obj.tax_payable)})
    messages.success(request,
        f"Computed {obj.number}: tax payable {obj.tax_payable}, paid YTD {obj.tax_paid_ytd}, "
        f"monthly TDS {obj.monthly_tds_amount}.")
    return redirect("hrm:taxcomputation_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def taxcomputation_link_form16(request, pk):
    obj = get_object_or_404(TaxComputation, pk=pk, tenant=request.tenant)
    ret = obj.link_form16(request.user)
    write_audit_log(request.user, obj, "update", {"action": "link_form16", "return": ret.number})
    messages.success(request,
        f"Linked Form 16 register row {ret.number} (Part A). Open Form 16 Part B for the full certificate.")
    return redirect("hrm:taxcomputation_detail", pk=obj.pk)
