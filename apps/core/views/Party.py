"""core — Party views (split from apps/core/views.py)."""
from apps.core.views._common import *  # noqa: F401,F403
from apps.core.models import (
    Party,
)
from apps.core.forms import (
    PartyForm,
)


# ----------------------------------------------------------------------------- Party
@login_required
def party_list(request):
    return crud_list(
        request, Party.objects.filter(tenant=request.tenant),
        "core/party/list.html",
        search_fields=["name", "tax_id"],
        filters=[("kind", "kind", False)],
        extra_context={"kind_choices": Party.KIND_CHOICES},
    )


@login_required
def party_create(request):
    return crud_create(request, form_class=PartyForm, template="core/party/form.html",
                       success_url="core:party_list")


@login_required
def party_detail(request, pk):
    return crud_detail(request, model=Party, pk=pk, template="core/party/detail.html",
                       extra_context=None)


@login_required
def party_edit(request, pk):
    return crud_edit(request, model=Party, pk=pk, form_class=PartyForm,
                     template="core/party/form.html", success_url="core:party_list")


@login_required
@require_POST
def party_delete(request, pk):
    return crud_delete(request, model=Party, pk=pk, success_url="core:party_list")
