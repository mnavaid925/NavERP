"""SCM 4.3 Inventory Management — StockTransfer views (posts a paired StockMove on complete)."""
from django.core.exceptions import ValidationError

from apps.scm.views._common import *  # noqa: F401,F403
from apps.scm.views._common import _changed
from apps.scm.views._helpers import _need_tenant, _post_transfer
from apps.scm.models import StockTransfer
from apps.scm.forms import StockTransferForm, StockTransferLineFormSet


@login_required
def stocktransfer_list(request):
    qs = (StockTransfer.objects.filter(tenant=request.tenant)
          .select_related("from_location", "to_location"))
    return crud_list(
        request, qs, "scm/inventory/stocktransfer/list.html",
        search_fields=["number", "notes"],
        filters=[("status", "status", False)],
        extra_context={"status_choices": StockTransfer.STATUS_CHOICES},
    )


@login_required
def stocktransfer_create(request):
    return _stocktransfer_form(request, instance=None)


@login_required
def stocktransfer_edit(request, pk):
    obj = get_object_or_404(StockTransfer, pk=pk, tenant=request.tenant)
    if not obj.is_editable:
        messages.error(request, "Only a draft transfer can be edited.")
        return redirect("scm:stocktransfer_detail", pk=pk)
    return _stocktransfer_form(request, instance=obj)


def _stocktransfer_form(request, instance):
    if instance is None and _need_tenant(request):
        return redirect("scm:stocktransfer_list")
    is_edit = instance is not None
    if request.method == "POST":
        form = StockTransferForm(request.POST, instance=instance, tenant=request.tenant)
        formset = StockTransferLineFormSet(request.POST, instance=instance,
                                           form_kwargs={"tenant": request.tenant})
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                transfer = form.save(commit=False)
                transfer.tenant = request.tenant
                transfer.save()
                formset.instance = transfer
                formset.save()
            write_audit_log(request.user, transfer, "update" if is_edit else "create", _changed(form))
            messages.success(request, f"Transfer {transfer.number} saved.")
            return redirect("scm:stocktransfer_detail", pk=transfer.pk)
    else:
        form = StockTransferForm(instance=instance, tenant=request.tenant)
        formset = StockTransferLineFormSet(instance=instance, form_kwargs={"tenant": request.tenant})
    return render(request, "scm/inventory/stocktransfer/form.html",
                  {"form": form, "formset": formset, "is_edit": is_edit, "obj": instance})


@login_required
def stocktransfer_detail(request, pk):
    obj = get_object_or_404(
        StockTransfer.objects.select_related("from_location", "to_location"), pk=pk, tenant=request.tenant)
    lines = obj.lines.select_related("item", "lot_serial")
    # Show the buyer whether the source can currently cover each line, before they complete.
    line_rows = [{"line": ln, "available": ln.item.on_hand(location=obj.from_location)} for ln in lines]
    return render(request, "scm/inventory/stocktransfer/detail.html", {
        "obj": obj,
        "line_rows": line_rows,
        "moves": obj_moves(obj),
    })


def obj_moves(transfer):
    from apps.scm.models import StockMove
    return (StockMove.objects.filter(tenant=transfer.tenant, reference=transfer.number)
            .select_related("item", "location") if transfer.number else [])


@login_required
@require_POST
def stocktransfer_delete(request, pk):
    obj = get_object_or_404(StockTransfer, pk=pk, tenant=request.tenant)
    if obj.status != "draft":
        messages.error(request, "Only a draft transfer can be deleted — cancel a completed one is not allowed.")
        return redirect("scm:stocktransfer_detail", pk=pk)
    return crud_delete(request, model=StockTransfer, pk=pk, success_url="scm:stocktransfer_list")


@tenant_admin_required
@require_POST
def stocktransfer_complete(request, pk):
    """Post the paired StockMoves and mark the transfer completed.

    Tenant-admin gated: this actually moves stock. The source on-hand guard runs inside the same
    atomic block as the posting, so a mid-transfer shortfall rolls the whole thing back — nothing
    partial is ever committed.
    """
    obj = get_object_or_404(StockTransfer.objects.select_related("from_location", "to_location"),
                            pk=pk, tenant=request.tenant)
    if obj.status not in ("draft", "in_transit"):
        messages.info(request, "This transfer is already completed or cancelled.")
        return redirect("scm:stocktransfer_detail", pk=pk)
    if not obj.lines.exists():
        messages.error(request, "Add at least one line before completing the transfer.")
        return redirect("scm:stocktransfer_detail", pk=pk)
    try:
        with transaction.atomic():
            _post_transfer(obj, request.user)
            obj.status = "completed"
            obj.completed_at = timezone.now()
            obj.save(update_fields=["status", "completed_at", "updated_at"])
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
        return redirect("scm:stocktransfer_detail", pk=pk)
    write_audit_log(request.user, obj, "update", {"action": "complete"})
    messages.success(request, f"Transfer {obj.number} completed and stock moved.")
    return redirect("scm:stocktransfer_detail", pk=pk)


@tenant_admin_required
@require_POST
def stocktransfer_cancel(request, pk):
    obj = get_object_or_404(StockTransfer, pk=pk, tenant=request.tenant)
    if obj.status in ("completed", "cancelled"):
        messages.info(request, "A completed transfer cannot be cancelled — post a reverse transfer instead.")
        return redirect("scm:stocktransfer_detail", pk=pk)
    obj.status = "cancelled"
    obj.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "cancel"})
    messages.success(request, f"Transfer {obj.number} cancelled.")
    return redirect("scm:stocktransfer_detail", pk=pk)
