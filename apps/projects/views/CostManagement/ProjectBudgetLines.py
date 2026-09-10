"""Projects 7.4 — ProjectBudgetLine views: the budget register with its totals strip.

The totals strip (per-category + grand total) must cover exactly what the table shows, so the
view pre-scopes a queryset with the SAME filter logic ``crud_list`` applies — same params, same
guard helpers (``as_db_int`` for the pk filters, the model's own CHOICES for the category enum)
— aggregates over it in ONE query, and then lets ``crud_list`` re-apply the same filters to the
register queryset. Re-applying is idempotent, and the register stays correct even if the
pre-scope and crud_list were ever to disagree: the totals would drift, never the rows.

Dropdown sources come from the FULL tenant scope — a filter narrows the table, never its own
pickers.
"""
from django.db.models import DecimalField, Q, Sum, Value
from django.db.models.functions import Coalesce

from apps.core.crud import apply_search, as_db_int
from apps.projects.forms import ProjectBudgetLineForm
from apps.projects.models import BudgetRevision, CostControlAccount, ProjectBudgetLine
from apps.projects.models._base import ZERO
from apps.projects.views._common import *  # noqa: F401,F403
from apps.projects.views._common import get_object_or_404, login_required, redirect, render, require_POST
from apps.projects.views._helpers import projects

_MONEY = DecimalField(max_digits=20, decimal_places=2)

_LOCKED_MSG = ("An approved or superseded revision is frozen cost history — its lines cannot be "
               "edited or deleted; submit a new revision to change the baseline.")

_PBL_FILTERS = [
    ("project", "project_id", True),
    ("budget_revision", "budget_revision_id", True),
    ("category", "category", False),
    ("control_account", "control_account_id", True),
]

_CATEGORY_VALUES = dict(ProjectBudgetLine.CATEGORY_CHOICES)


def _pbl_totals(request):
    """Per-category + grand totals over the register's exact filter scope — one query."""
    scope = ProjectBudgetLine.objects.filter(tenant=request.tenant)
    q = request.GET.get("q", "").strip()
    if q:
        scope = apply_search(scope, q, ["number", "note"])
    for param, lookup, is_int in _PBL_FILTERS:
        val = request.GET.get(param, "").strip()
        if not val:
            continue
        if is_int:
            number = as_db_int(val)
            if number is None or number == 0:
                continue
            scope = scope.filter(**{lookup: number})
        elif val in _CATEGORY_VALUES:
            scope = scope.filter(**{lookup: val})
    agg = {cat: Coalesce(Sum("amount", filter=Q(category=cat)), Value(ZERO), output_field=_MONEY)
           for cat, _label in ProjectBudgetLine.CATEGORY_CHOICES}
    agg["grand_total"] = Coalesce(Sum("amount"), Value(ZERO), output_field=_MONEY)
    row = scope.aggregate(**agg)
    return ({cat: row[cat] for cat, _label in ProjectBudgetLine.CATEGORY_CHOICES},
            row["grand_total"])


@login_required
def pbl_list(request):
    qs = (ProjectBudgetLine.objects.filter(tenant=request.tenant)
          .select_related("project", "budget_revision", "control_account", "wbs_node"))
    category_totals, grand_total = _pbl_totals(request)
    return crud_list(
        request, qs, "projects/cost/projectbudgetline/list.html",
        search_fields=["number", "note"],
        filters=_PBL_FILTERS,
        extra_context={
            "projects": projects(request.tenant),
            "revisions": BudgetRevision.objects.filter(tenant=request.tenant)
                .select_related("project"),
            "category_choices": ProjectBudgetLine.CATEGORY_CHOICES,
            "control_accounts": CostControlAccount.objects.filter(tenant=request.tenant),
            "category_totals": category_totals,
            "grand_total": grand_total,
        },
    )


@login_required
def pbl_create(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = ProjectBudgetLineForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, f"Budget line {obj.number} created.")
            return redirect("projects:pbl_detail", pk=obj.pk)
    else:
        form = ProjectBudgetLineForm(tenant=request.tenant,
                                     initial={"project": request.GET.get("project", "")})
    return render(request, "projects/cost/projectbudgetline/form.html",
                  {"form": form, "is_edit": False})


@login_required
def pbl_detail(request, pk):
    obj = get_object_or_404(
        ProjectBudgetLine.objects.select_related(
            "project", "budget_revision", "wbs_node", "control_account", "gl_account"),
        pk=pk, tenant=request.tenant)
    return render(request, "projects/cost/projectbudgetline/detail.html", {"obj": obj})


@login_required
def pbl_edit(request, pk):
    obj = get_object_or_404(
        ProjectBudgetLine.objects.select_related("budget_revision"), pk=pk, tenant=request.tenant)
    if obj.budget_revision.is_locked:
        messages.error(request, _LOCKED_MSG)
        return redirect("projects:pbl_detail", pk=obj.pk)
    return crud_edit(
        request, model=ProjectBudgetLine, pk=pk, form_class=ProjectBudgetLineForm,
        template="projects/cost/projectbudgetline/form.html", success_url="projects:pbl_list")


@login_required
@require_POST
def pbl_delete(request, pk):
    obj = get_object_or_404(
        ProjectBudgetLine.objects.select_related("budget_revision"), pk=pk, tenant=request.tenant)
    if obj.budget_revision.is_locked:
        messages.error(request, _LOCKED_MSG)
        return redirect("projects:pbl_detail", pk=obj.pk)
    return crud_delete(request, model=ProjectBudgetLine, pk=pk,
                       success_url="projects:pbl_list")
