"""core — ContactMethod views (split from apps/core/views.py)."""
from apps.core.views._common import *  # noqa: F401,F403
from apps.core.views._common import _parties
from apps.core.models import (
    ContactMethod,
)
from apps.core.forms import (
    ContactMethodForm,
)


# --------------------------------------------------------------------- ContactMethod
@login_required
def contactmethod_list(request):
    return crud_list(
        request, ContactMethod.objects.filter(tenant=request.tenant).select_related("party"),
        "core/contactmethod/list.html",
        search_fields=["value"],
        filters=[("kind", "kind", False), ("party", "party_id", True)],
        extra_context={"kind_choices": ContactMethod.KIND_CHOICES, "parties": _parties(request)},
    )


@login_required
def contactmethod_create(request):
    return crud_create(request, form_class=ContactMethodForm, template="core/contactmethod/form.html",
                       success_url="core:contactmethod_list")


@login_required
def contactmethod_detail(request, pk):
    return crud_detail(request, model=ContactMethod, pk=pk, template="core/contactmethod/detail.html",
                       select_related=["party"])


@login_required
def contactmethod_edit(request, pk):
    return crud_edit(request, model=ContactMethod, pk=pk, form_class=ContactMethodForm,
                     template="core/contactmethod/form.html", success_url="core:contactmethod_list")


@login_required
@require_POST
def contactmethod_delete(request, pk):
    return crud_delete(request, model=ContactMethod, pk=pk, success_url="core:contactmethod_list")
