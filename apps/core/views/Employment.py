"""core — Employment views (split from apps/core/views.py)."""
from apps.core.views._common import *  # noqa: F401,F403
from apps.core.views._common import _parties
from apps.core.models import (
    Employment,
    OrgUnit,
)
from apps.core.forms import (
    EmploymentForm,
)


# ------------------------------------------------------------------------ Employment
@login_required
def employment_list(request):
    return crud_list(
        request,
        Employment.objects.filter(tenant=request.tenant).select_related("party", "org_unit", "manager"),
        "core/employment/list.html",
        search_fields=["party__name", "job_title"],
        filters=[("status", "status", False), ("org_unit", "org_unit_id", True)],
        extra_context={"status_choices": Employment.STATUS_CHOICES,
                       "org_units": OrgUnit.objects.filter(tenant=request.tenant),
                       "parties": _parties(request)},
    )


@login_required
def employment_create(request):
    return crud_create(request, form_class=EmploymentForm, template="core/employment/form.html",
                       success_url="core:employment_list")


@login_required
def employment_detail(request, pk):
    return crud_detail(request, model=Employment, pk=pk, template="core/employment/detail.html",
                       select_related=["party", "org_unit", "manager"])


@login_required
def employment_edit(request, pk):
    return crud_edit(request, model=Employment, pk=pk, form_class=EmploymentForm,
                     template="core/employment/form.html", success_url="core:employment_list")


@login_required
@require_POST
def employment_delete(request, pk):
    return crud_delete(request, model=Employment, pk=pk, success_url="core:employment_list")
