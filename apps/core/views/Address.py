"""core — Address views (split from apps/core/views.py)."""
from apps.core.views._common import *  # noqa: F401,F403
from apps.core.views._common import _parties
from apps.core.models import (
    Address,
)
from apps.core.forms import (
    AddressForm,
)


# --------------------------------------------------------------------------- Address
@login_required
def address_list(request):
    return crud_list(
        request, Address.objects.filter(tenant=request.tenant).select_related("party"),
        "core/address/list.html",
        search_fields=["line1", "city", "country"],
        filters=[("kind", "kind", False), ("party", "party_id", True)],
        extra_context={"kind_choices": Address.KIND_CHOICES, "parties": _parties(request)},
    )


@login_required
def address_create(request):
    return crud_create(request, form_class=AddressForm, template="core/address/form.html",
                       success_url="core:address_list")


@login_required
def address_detail(request, pk):
    return crud_detail(request, model=Address, pk=pk, template="core/address/detail.html",
                       select_related=["party"])


@login_required
def address_edit(request, pk):
    return crud_edit(request, model=Address, pk=pk, form_class=AddressForm,
                     template="core/address/form.html", success_url="core:address_list")


@login_required
@require_POST
def address_delete(request, pk):
    return crud_delete(request, model=Address, pk=pk, success_url="core:address_list")
