"""SCM 4.10 Returns Management — ReturnReason views (the reason-code master).

No sidebar key — the ``InspectionPlan`` / ``WorkCenter`` / ``ReorderRule`` precedent. A reason is
configuration, reached from the return-portal console and from the RMA line form, not a queue
somebody works.

``returnreason_delete`` uses the GENERIC ``except ProtectedError`` inside ``atomic()`` rather than
an ``.exists()`` enumeration (§7.4). ``ReturnLine.reason`` is PROTECT today; the enumeration this
avoids is exactly the one ``item_delete``'s comment describes going stale — 5.10 and 9.5 are
declared FK extenders of this table, so the list of things pointing at a reason will grow.
"""
from django.db.models import ProtectedError

from apps.scm.views._common import *  # noqa: F401,F403
from apps.scm.views._helpers import _need_tenant
from apps.scm.models import ReturnLine, ReturnReason
from apps.scm.forms import ReturnReasonForm


@login_required
def returnreason_list(request):
    # `in_use_agg`, not `in_use`: §7.3 — no annotation in 4.10 may share a name with a model
    # property, so every one of them carries the `_agg` suffix whether a property exists today or
    # not. Exists, not Count: the list only asks "is this reason in use?" — a COUNT would GROUP BY
    # the whole ReturnLine table per row and unset QuerySet.ordered into the bargain.
    qs = (ReturnReason.objects.filter(tenant=request.tenant)
          .annotate(in_use_agg=Exists(ReturnLine.objects.filter(reason_id=OuterRef("pk")))))
    stats = ReturnReason.objects.filter(tenant=request.tenant).aggregate(
        active=Count("id", filter=Q(is_active=True)),
        blocks_restock=Count("id", filter=Q(blocks_restock=True)),
        our_fault=Count("id", filter=Q(fault_party__in=("merchant", "supplier", "carrier"))),
        needs_photo=Count("id", filter=Q(requires_photo=True)),
    )
    return crud_list(
        request, qs, "scm/returns/returnreason/list.html",
        search_fields=["code", "name", "follow_up_question"],
        filters=[("fault_party", "fault_party", False), ("is_active", "is_active", False),
                 ("blocks_restock", "blocks_restock", False),
                 ("requires_photo", "requires_photo", False),
                 ("suggested_disposition", "suggested_disposition", False)],
        extra_context={
            "fault_choices": ReturnReason.FAULT_PARTY_CHOICES,
            "disposition_choices": ReturnReason._meta.get_field("suggested_disposition").choices,
            "stats": stats,
        },
    )


@login_required
def returnreason_create(request):
    if _need_tenant(request):
        return redirect("scm:returnreason_list")
    return crud_create(request, form_class=ReturnReasonForm,
                       template="scm/returns/returnreason/form.html",
                       success_url="scm:returnreason_list")


@login_required
def returnreason_edit(request, pk):
    return crud_edit(request, model=ReturnReason, pk=pk, form_class=ReturnReasonForm,
                     template="scm/returns/returnreason/form.html",
                     success_url="scm:returnreason_list")


@login_required
def returnreason_detail(request, pk):
    obj = get_object_or_404(ReturnReason, pk=pk, tenant=request.tenant)
    return render(request, "scm/returns/returnreason/detail.html", {
        "obj": obj,
        # The lines actually raised on this reason — evidence for whether the configuration is
        # doing anything, capped because this is a sample panel and not the register.
        "return_lines": (obj.return_lines
                         .select_related("return_authorization__customer", "item")
                         .order_by("-id")[:25]),
        "allowed_resolutions": obj.allowed_resolutions,
    })


@login_required
@require_POST
def returnreason_delete(request, pk):
    """Generic ProtectedError guard (§7.4) — never an ``.exists()`` chain.

    ``ReturnLine.reason`` is the only PROTECT reference today, but 5.10 and 9.5 are declared FK
    extenders of this table, so an enumeration would go stale and the miss would show up as a 500.
    Wrapped in ``atomic()`` so the audit row ``crud_delete`` writes before deleting rolls back with
    the failed delete.
    """
    get_object_or_404(ReturnReason.objects.only("pk"), pk=pk, tenant=request.tenant)
    try:
        with transaction.atomic():
            return crud_delete(request, model=ReturnReason, pk=pk,
                               success_url="scm:returnreason_list")
    except ProtectedError as exc:
        blockers = sorted({protected._meta.verbose_name for protected in exc.protected_objects})
        messages.error(
            request,
            f"This reason is still referenced by {', '.join(blockers)} and cannot be deleted — "
            "deactivate it instead so past returns keep their reason.")
        return redirect("scm:returnreason_detail", pk=pk)
