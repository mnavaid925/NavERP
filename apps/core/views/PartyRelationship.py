"""core — PartyRelationship views (split from apps/core/views.py)."""
from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from apps.core.views._common import *  # noqa: F401,F403
from apps.core.views._common import _parties
from apps.core.models import (
    PartyRelationship,
)
from apps.core.forms import (
    PartyRelationshipForm,
)
from apps.core.utils import write_audit_log


def _relationship_queryset(request):
    return PartyRelationship.objects.filter(
        tenant=request.tenant,
        from_party__tenant=request.tenant,
        to_party__tenant=request.tenant,
    ).select_related("from_party", "to_party")


# ----------------------------------------------------------------- PartyRelationship
@login_required
def partyrelationship_list(request):
    return crud_list(
        request,
        _relationship_queryset(request),
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
    obj = get_object_or_404(_relationship_queryset(request), pk=pk)
    return render(request, "core/partyrelationship/detail.html", {"obj": obj})


@login_required
def partyrelationship_edit(request, pk):
    obj = get_object_or_404(_relationship_queryset(request), pk=pk)
    if request.method == "POST":
        form = PartyRelationshipForm(request.POST, instance=obj, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                obj = form.save()
                write_audit_log(request.user, obj, "update", {"action": "party_relationship"}, tenant=request.tenant)
            messages.success(request, "Updated successfully.")
            return redirect("core:partyrelationship_list")
    else:
        form = PartyRelationshipForm(instance=obj, tenant=request.tenant)
    return render(request, "core/partyrelationship/form.html", {"form": form, "obj": obj, "is_edit": True})


@login_required
@require_POST
def partyrelationship_delete(request, pk):
    obj = get_object_or_404(_relationship_queryset(request), pk=pk)
    with transaction.atomic():
        write_audit_log(request.user, obj, "delete", {"action": "party_relationship"}, tenant=request.tenant)
        obj.delete()
    messages.success(request, "Deleted successfully.")
    return redirect("core:partyrelationship_list")
