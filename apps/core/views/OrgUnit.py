"""core — OrgUnit views (split from apps/core/views.py)."""
from apps.core.views._common import *  # noqa: F401,F403
from apps.core.models import (
    OrgUnit,
)
from apps.core.forms import (
    OrgUnitForm,
)


# --------------------------------------------------------------------------- OrgUnit
@login_required
def orgunit_list(request):
    return crud_list(
        request, OrgUnit.objects.filter(tenant=request.tenant).select_related("parent"),
        "core/orgunit/list.html",
        search_fields=["name"],
        filters=[("kind", "kind", False), ("parent", "parent_id", True)],
        extra_context={"kind_choices": OrgUnit.KIND_CHOICES,
                       "parents": OrgUnit.objects.filter(tenant=request.tenant)},
    )


@login_required
def orgunit_create(request):
    return crud_create(request, form_class=OrgUnitForm, template="core/orgunit/form.html",
                       success_url="core:orgunit_list")


@login_required
def orgunit_detail(request, pk):
    return crud_detail(request, model=OrgUnit, pk=pk, template="core/orgunit/detail.html",
                       select_related=["parent"])


@login_required
def orgunit_edit(request, pk):
    return crud_edit(request, model=OrgUnit, pk=pk, form_class=OrgUnitForm,
                     template="core/orgunit/form.html", success_url="core:orgunit_list")


@login_required
@require_POST
def orgunit_delete(request, pk):
    return crud_delete(request, model=OrgUnit, pk=pk, success_url="core:orgunit_list")
