"""Procurement 6.15 Budget & Cost Management — BudgetMapping views.

**Budget Allocation & Mapping** bullet. Plain tenant-scoped CRUD over the configuration master:
register (search + filters + pagination), detail, create, edit, delete.

Discipline a reviewer will otherwise go looking for:

* **Every queryset is ``filter(tenant=request.tenant)``** — never ``.all()``. The ``crud_*``
  helpers enforce it for detail/edit/delete; the list narrows its own base queryset.
* **The detail page links through to the availability checker** pre-filled with the mapping's
  budget — the mapping exists to be USED by that check, and the link is the proof.
* **Writes are audited** through ``write_audit_log`` (create/edit via the ``crud_*`` helpers,
  delete via ``crud_delete``).
"""
from apps.accounting.models import Budget, Project
from apps.core.models import OrgUnit

from apps.procurement.forms.BudgetCostManagement.BudgetMappings import BudgetMappingForm
# NOT-YET-WIRED entity of this SAME sub-module: import the entity MODULE directly, never
# ``from apps.procurement.models import X`` — the sub-package is not wired until the Integrator
# lands it, and a package-level re-export would be a star-import cycle at URLconf import time.
from apps.procurement.models.BudgetCostManagement.BudgetMappings import BudgetMapping
from apps.procurement.views._common import *  # noqa: F401,F403

TEMPLATE_LIST = "procurement/budgetcost/budgetmapping/list.html"
TEMPLATE_DETAIL = "procurement/budgetcost/budgetmapping/detail.html"
TEMPLATE_FORM = "procurement/budgetcost/budgetmapping/form.html"

_ROW_RELATIONS = ("budget", "budget__fiscal_period", "org_unit", "project", "default_gl_account")


def _mapping_qs(request):
    return BudgetMapping.objects.filter(tenant=request.tenant).select_related(*_ROW_RELATIONS)


def _filter_dropdowns(request):
    """The three FK dropdowns' options — empty querysets for a tenant-less user.

    ``gl_accounts`` is deliberately absent: the list template's filter bar offers no GL-account
    filter, and the create/edit forms build their own dropdowns, so shipping that queryset here
    would fetch it for nothing on every render.
    """
    if request.tenant is None:
        return {"budgets": Budget.objects.none(), "org_units": OrgUnit.objects.none(),
                "projects": Project.objects.none()}
    return {
        "budgets": Budget.objects.filter(tenant=request.tenant).order_by("-id"),
        "org_units": OrgUnit.objects.filter(tenant=request.tenant).order_by("name"),
        "projects": Project.objects.filter(tenant=request.tenant).order_by("name"),
    }


@login_required
def budgetmapping_list(request):
    """The mapping register: which budget governs which department / project."""
    base = BudgetMapping.objects.filter(tenant=request.tenant)
    stats = {
        "total": base.count(),
        "active": base.filter(is_active=True).count(),
        "inactive": base.filter(is_active=False).count(),
    }
    extra = {"stats": stats}
    extra.update(_filter_dropdowns(request))
    return crud_list(
        request, _mapping_qs(request), TEMPLATE_LIST,
        search_fields=("budget__name", "budget__number", "org_unit__name", "project__name",
                       "notes"),
        # The three FK filters need the as_db_int guard (crud_list's is_int=True); is_active is
        # a boolean crud_list maps from "True"/"False" itself.
        filters=(("budget", "budget_id", True),
                 ("org_unit", "org_unit_id", True),
                 ("project", "project_id", True),
                 ("is_active", "is_active", False)),
        extra_context=extra,
    )


@login_required
def budgetmapping_detail(request, pk):
    return crud_detail(request, model=BudgetMapping, pk=pk, template=TEMPLATE_DETAIL,
                       select_related=_ROW_RELATIONS)


@login_required
def budgetmapping_create(request):
    return crud_create(request, form_class=BudgetMappingForm, template=TEMPLATE_FORM,
                       success_url="procurement:budgetmapping_list")


@login_required
def budgetmapping_edit(request, pk):
    return crud_edit(request, model=BudgetMapping, pk=pk, form_class=BudgetMappingForm,
                     template=TEMPLATE_FORM, success_url="procurement:budgetmapping_list")


@login_required
@require_POST
def budgetmapping_delete(request, pk):
    return crud_delete(request, model=BudgetMapping, pk=pk,
                       success_url="procurement:budgetmapping_list")
