"""Accounting 2.9 Project/Job Costing — Projects views (split from views.py/views_advanced.py)."""
from apps.accounting.views._common import *  # noqa: F401,F403
from apps.accounting.models import (
    Project,
    ZERO,
)
from apps.accounting.forms import (
    ProjectForm,
)


# ===================================================== 2.9 Project / Job Costing
@login_required
def project_list(request):
    return crud_list(
        request, Project.objects.filter(tenant=request.tenant).select_related("client", "org_unit"),
        "accounting/projects/project/list.html",
        search_fields=["number", "name"],
        filters=[("status", "status", False), ("billing_method", "billing_method", False)],
        extra_context={"status_choices": Project.STATUS_CHOICES, "billing_choices": Project.BILLING_CHOICES},
    )


@login_required
def project_create(request):
    return crud_create(request, form_class=ProjectForm, template="accounting/projects/project/form.html",
                       success_url="accounting:project_list")


@login_required
def project_detail(request, pk):
    obj = get_object_or_404(Project.objects.select_related("client", "org_unit"), pk=pk, tenant=request.tenant)
    # One grouped aggregate for the cost/revenue actuals (was 5 separate .aggregate() calls — perf C2).
    sums = {r["kind"]: r["total"] or ZERO
            for r in obj.cost_entries.filter(status="posted").values("kind").annotate(total=Sum("amount"))}
    actual_cost, actual_revenue = sums.get("cost", ZERO), sums.get("revenue", ZERO)
    return render(request, "accounting/projects/project/detail.html", {
        "obj": obj,
        "cost_entries": obj.cost_entries.all()[:20],
        "actual_cost": actual_cost, "actual_revenue": actual_revenue,
        "variance": (obj.budget_amount or ZERO) - actual_cost,
        "margin": actual_revenue - actual_cost,
    })


@login_required
def project_edit(request, pk):
    return crud_edit(request, model=Project, pk=pk, form_class=ProjectForm,
                     template="accounting/projects/project/form.html", success_url="accounting:project_list")


@login_required
@require_POST
def project_delete(request, pk):
    return crud_delete(request, model=Project, pk=pk, success_url="accounting:project_list")
