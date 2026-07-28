"""core — Party views (split from apps/core/views.py)."""
from django.contrib import messages
from django.db import transaction
from django.db.models import ProtectedError
from django.shortcuts import redirect

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
    """Delete a party — with the GENERIC ``except ProtectedError`` guard every other spine master
    already carries (``item_delete``, ``location_delete``, ``lotserial_delete``).

    ``core.Party`` is the most PROTECT-referenced model in the application: sales orders, purchase
    orders, accounting invoices and bills, supplier contracts, carriers, and — as of SCM 4.10 —
    return authorisations and warranty claims all point at it and refuse to let it go. Until now
    this view had NO guard at all, so any of those references turned an ordinary Delete click into
    an uncaught ``ProtectedError``: a 500 page, not a message.

    Deliberately generic rather than an ``.exists()`` enumeration. Every module that lands adds
    references, an enumeration goes stale the moment one does, and the miss shows up as the same
    500 this replaces. ``atomic()`` so the audit row ``crud_delete`` writes before deleting rolls
    back with the failed delete.
    """
    get_object_or_404(Party.objects.only("pk"), pk=pk, tenant=request.tenant)
    try:
        with transaction.atomic():
            return crud_delete(request, model=Party, pk=pk, success_url="core:party_list")
    except ProtectedError as exc:
        blockers = sorted({protected._meta.verbose_name for protected in exc.protected_objects})
        messages.error(
            request,
            f"This party is still referenced by {', '.join(blockers)} and cannot be deleted — "
            "the records that name it would lose their counterparty.")
        return redirect("core:party_detail", pk=pk)
