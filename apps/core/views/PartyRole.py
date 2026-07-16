"""core — PartyRole views (split from apps/core/views.py)."""
from apps.core.views._common import *  # noqa: F401,F403
from apps.core.views._common import _parties
from apps.core.models import (
    PartyRole,
)
from apps.core.forms import (
    PartyRoleForm,
)


# ------------------------------------------------------------------------- PartyRole
@login_required
def partyrole_list(request):
    return crud_list(
        request, PartyRole.objects.filter(tenant=request.tenant).select_related("party"),
        "core/partyrole/list.html",
        search_fields=["party__name"],
        filters=[("role", "role", False), ("status", "status", False), ("party", "party_id", True)],
        extra_context={"role_choices": PartyRole.ROLE_CHOICES,
                       "status_choices": PartyRole.STATUS_CHOICES, "parties": _parties(request)},
    )


@login_required
def partyrole_create(request):
    return crud_create(request, form_class=PartyRoleForm, template="core/partyrole/form.html",
                       success_url="core:partyrole_list")


@login_required
def partyrole_detail(request, pk):
    return crud_detail(request, model=PartyRole, pk=pk, template="core/partyrole/detail.html",
                       select_related=["party"])


@login_required
def partyrole_edit(request, pk):
    return crud_edit(request, model=PartyRole, pk=pk, form_class=PartyRoleForm,
                     template="core/partyrole/form.html", success_url="core:partyrole_list")


@login_required
@require_POST
def partyrole_delete(request, pk):
    return crud_delete(request, model=PartyRole, pk=pk, success_url="core:partyrole_list")
