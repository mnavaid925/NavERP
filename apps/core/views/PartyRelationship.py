"""core — PartyRelationship views (split from apps/core/views.py)."""
from apps.core.views._common import *  # noqa: F401,F403
from apps.core.views._common import _parties
from apps.core.models import (
    PartyRelationship,
)
from apps.core.forms import (
    PartyRelationshipForm,
)


# ----------------------------------------------------------------- PartyRelationship
@login_required
def partyrelationship_list(request):
    return crud_list(
        request,
        PartyRelationship.objects.filter(tenant=request.tenant).select_related("from_party", "to_party"),
        "core/partyrelationship/list.html",
        search_fields=["from_party__name", "to_party__name"],
        filters=[("kind", "kind", False)],
        extra_context={"kind_choices": PartyRelationship.KIND_CHOICES, "parties": _parties(request)},
    )


@login_required
def partyrelationship_create(request):
    return crud_create(request, form_class=PartyRelationshipForm,
                       template="core/partyrelationship/form.html",
                       success_url="core:partyrelationship_list")


@login_required
def partyrelationship_detail(request, pk):
    return crud_detail(request, model=PartyRelationship, pk=pk,
                       template="core/partyrelationship/detail.html",
                       select_related=["from_party", "to_party"])


@login_required
def partyrelationship_edit(request, pk):
    return crud_edit(request, model=PartyRelationship, pk=pk, form_class=PartyRelationshipForm,
                     template="core/partyrelationship/form.html",
                     success_url="core:partyrelationship_list")


@login_required
@require_POST
def partyrelationship_delete(request, pk):
    return crud_delete(request, model=PartyRelationship, pk=pk,
                       success_url="core:partyrelationship_list")
