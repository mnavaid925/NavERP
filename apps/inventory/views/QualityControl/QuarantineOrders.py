"""Inventory 5.15 Quality Control (QC) & Inspection — QuarantineOrder views.

CRUD plus the four lifecycle verbs (quarantine / release / scrap / cancel). The model's
action methods own the locking and the ledger legs; these views own the HTTP contract —
the 5.5 CrossDockOrder split: POST-only verbs, refusals surfaced as flash messages (a
ValidationError from a guarded action is a user-facing "cannot", never a 500), audit
written by the model inside its transaction.

Gating: starting a hold is operator work (login); RELEASE / SCRAP / CANCEL decide the
fate of stock and reverse or destroy ledger quantities, so they are admin verbs.
Edit/delete guard server-side on draft-only (the template hides the buttons; a crafted
POST must not re-open a document whose number is written into immutable StockMove rows).
"""
from django.core.exceptions import ValidationError
from django.db import transaction

from apps.core.decorators import tenant_admin_required
from apps.inventory.forms import QuarantineOrderForm
from apps.inventory.models import QuarantineOrder
from apps.inventory.views._common import *  # noqa: F401,F403


def _scoped(tenant):
    """Tenant-scoped queryset with the joins every list/detail page renders."""
    return (QuarantineOrder.objects.filter(tenant=tenant)
            .select_related("item", "lot_serial", "source_location", "quarantine_location"))


@login_required
def quarantineorder_list(request):
    qs = _scoped(request.tenant)

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    return crud_list(
        request,
        qs,
        "inventory/qc/quarantineorder/list.html",
        search_fields=["number", "item__sku", "item__name", "reference", "notes"],
        filters=[],
        extra_context={
            "status_choices": QuarantineOrder.STATUS_CHOICES,
            "status": status,
            "is_admin": bool(request.user.is_superuser or getattr(request.user, "is_tenant_admin", False)),
        },
    )


@login_required
def quarantineorder_detail(request, pk):
    obj = get_object_or_404(_scoped(request.tenant), pk=pk)
    return render(request, "inventory/qc/quarantineorder/detail.html", {
        "obj": obj,
        # The order's ledger legs as rows — proof of what actually moved, read from
        # the append-only book rather than restated here.
        "moves": obj.ledger_moves()[:20],
        "is_admin": bool(request.user.is_superuser or getattr(request.user, "is_tenant_admin", False)),
    })


@login_required
def quarantineorder_create(request):
    return crud_create(
        request, form_class=QuarantineOrderForm,
        template="inventory/qc/quarantineorder/form.html",
        success_url="inventory:quarantineorder_list",
    )


@login_required
def quarantineorder_edit(request, pk):
    # Server-side status guard, held UNDER the row lock across the whole request: a
    # concurrent quarantine() committing between our check and crud_edit's save must be
    # impossible, because its action takes the same lock (review I2). The template hides
    # Edit on non-drafts; this is the crafted-POST backstop.
    with transaction.atomic():
        obj = get_object_or_404(QuarantineOrder.objects.select_for_update(),
                                pk=pk, tenant=request.tenant)
        if not obj.is_editable:
            messages.error(
                request,
                f"{obj.number} has posted ledger moves and can no longer be edited.")
            return redirect("inventory:quarantineorder_detail", pk=obj.pk)
        return crud_edit(
            request, model=QuarantineOrder, pk=pk, form_class=QuarantineOrderForm,
            template="inventory/qc/quarantineorder/form.html",
            success_url="inventory:quarantineorder_list",
        )


@tenant_admin_required
@require_POST
def quarantineorder_delete(request, pk):
    """Delete a draft only. A quarantined/released order's number is written into immutable
    StockMove rows — deleting the document would orphan its legs' provenance.

    Hand-rolled rather than delegated to crud_delete (CrossDockOrder/MaintenanceWorkOrder
    precedent): crud_delete re-fetches by pk WITHOUT a lock, so the draft check below runs
    against the row WHILE locked — a concurrent quarantine() either commits first (and the
    delete refuses) or waits (and the delete removes a still-draft document that never
    posted anything).
    """
    with transaction.atomic():
        obj = get_object_or_404(QuarantineOrder.objects.select_for_update(),
                                pk=pk, tenant=request.tenant)
        if not obj.is_editable:
            messages.error(
                request,
                f"{obj.number} has posted ledger moves and cannot be deleted — "
                "cancel it instead.")
            return redirect("inventory:quarantineorder_detail", pk=obj.pk)
        write_audit_log(request.user, obj, "delete")
        number = obj.number
        obj.delete()
    messages.success(request, f"{number} deleted.")
    return redirect("inventory:quarantineorder_list")


@login_required
@require_POST
def quarantineorder_quarantine(request, pk):
    """Hold the goods (operator verb)."""
    return _run_action(request, pk, "quarantine")


@tenant_admin_required
@require_POST
def quarantineorder_release(request, pk):
    """Clear the hold — admin decides quality."""
    return _run_action(request, pk, "release")


@tenant_admin_required
@require_POST
def quarantineorder_scrap(request, pk):
    """Condemn the held units — admin destroys stock."""
    return _run_action(request, pk, "scrap")


@tenant_admin_required
@require_POST
def quarantineorder_cancel(request, pk):
    """Refuse/reverse the hold — admin reverses ledger legs."""
    return _run_action(request, pk, "cancel")


# -- module-private helpers --------------------------------------------------------------------

_ACTION_MESSAGES = {
    "quarantine": "moved into quarantine.",
    "release": "released back to stock.",
    "scrap": "written off from quarantine.",
    "cancel": "cancelled.",
}


def _run_action(request, pk, action):
    """Run one lifecycle verb and turn its refusal into a flash message.

    The success/error split is deliberate: a refusal is EXPECTED traffic (double-click,
    stale tab, someone else got there first), so it lands as a message on the detail
    page rather than an exception page.
    """
    obj = get_object_or_404(QuarantineOrder, pk=pk, tenant=request.tenant)
    try:
        getattr(obj, action)(request.user)
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    else:
        messages.success(request, f"{obj.number} {_ACTION_MESSAGES[action]}")
    return redirect("inventory:quarantineorder_detail", pk=obj.pk)
