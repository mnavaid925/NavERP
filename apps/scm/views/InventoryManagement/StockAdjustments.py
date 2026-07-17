"""SCM 4.3 Inventory Management — StockAdjustment views (posts StockMove on post)."""
from django.core.exceptions import ValidationError

from apps.scm.views._common import *  # noqa: F401,F403
from apps.scm.views._common import _changed
from apps.scm.views._helpers import _need_tenant, _post_adjustment
from apps.scm.models import StockAdjustment, StockMove
from apps.scm.forms import StockAdjustmentForm, StockAdjustmentLineFormSet


@login_required
def stockadjustment_list(request):
    qs = StockAdjustment.objects.filter(tenant=request.tenant).select_related("location")
    return crud_list(
        request, qs, "scm/inventory/stockadjustment/list.html",
        search_fields=["number", "notes"],
        filters=[("status", "status", False), ("reason", "reason", False)],
        extra_context={
            "status_choices": StockAdjustment.STATUS_CHOICES,
            "reason_choices": StockAdjustment.REASON_CHOICES,
        },
    )


@login_required
def stockadjustment_create(request):
    return _stockadjustment_form(request, instance=None)


@login_required
def stockadjustment_edit(request, pk):
    obj = get_object_or_404(StockAdjustment, pk=pk, tenant=request.tenant)
    if not obj.is_editable:
        messages.error(request, "Only a draft adjustment can be edited.")
        return redirect("scm:stockadjustment_detail", pk=pk)
    return _stockadjustment_form(request, instance=obj)


def _stockadjustment_form(request, instance):
    if instance is None and _need_tenant(request):
        return redirect("scm:stockadjustment_list")
    is_edit = instance is not None
    if request.method == "POST":
        form = StockAdjustmentForm(request.POST, instance=instance, tenant=request.tenant)
        formset = StockAdjustmentLineFormSet(request.POST, instance=instance,
                                             form_kwargs={"tenant": request.tenant})
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                adj = form.save(commit=False)
                adj.tenant = request.tenant
                adj.save()
                formset.instance = adj
                formset.save()
            write_audit_log(request.user, adj, "update" if is_edit else "create", _changed(form))
            messages.success(request, f"Adjustment {adj.number} saved.")
            return redirect("scm:stockadjustment_detail", pk=adj.pk)
    else:
        form = StockAdjustmentForm(instance=instance, tenant=request.tenant)
        formset = StockAdjustmentLineFormSet(instance=instance, form_kwargs={"tenant": request.tenant})
    return render(request, "scm/inventory/stockadjustment/form.html",
                  {"form": form, "formset": formset, "is_edit": is_edit, "obj": instance})


@login_required
def stockadjustment_detail(request, pk):
    obj = get_object_or_404(StockAdjustment.objects.select_related("location"), pk=pk, tenant=request.tenant)
    return render(request, "scm/inventory/stockadjustment/detail.html", {
        "obj": obj,
        "lines": obj.lines.select_related("item", "lot_serial"),
        "value_impact": obj.value_impact(),
        "moves": (StockMove.objects.filter(tenant=request.tenant, reference=obj.number)
                  .select_related("item") if obj.number else []),
    })


@login_required
@require_POST
def stockadjustment_delete(request, pk):
    obj = get_object_or_404(StockAdjustment, pk=pk, tenant=request.tenant)
    if obj.status != "draft":
        messages.error(request, "Only a draft adjustment can be deleted.")
        return redirect("scm:stockadjustment_detail", pk=pk)
    return crud_delete(request, model=StockAdjustment, pk=pk, success_url="scm:stockadjustment_list")


@tenant_admin_required
@require_POST
def stockadjustment_post(request, pk):
    """Post the adjustment: write a StockMove per line and lock it. Tenant-admin gated (moves stock).

    A negative delta that would drive on-hand below zero is refused inside the atomic block, so a bad
    line rolls back the whole post.
    """
    obj = get_object_or_404(StockAdjustment.objects.select_related("location"), pk=pk, tenant=request.tenant)
    if obj.status != "draft":
        messages.info(request, "This adjustment has already been posted or cancelled.")
        return redirect("scm:stockadjustment_detail", pk=pk)
    if not obj.lines.exists():
        messages.error(request, "Add at least one line before posting.")
        return redirect("scm:stockadjustment_detail", pk=pk)
    try:
        with transaction.atomic():
            _post_adjustment(obj, request.user)
            obj.status = "posted"
            obj.posted_at = timezone.now()
            obj.save(update_fields=["status", "posted_at", "updated_at"])
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
        return redirect("scm:stockadjustment_detail", pk=pk)
    write_audit_log(request.user, obj, "update", {"action": "post"})
    messages.success(request, f"Adjustment {obj.number} posted.")
    return redirect("scm:stockadjustment_detail", pk=pk)


@tenant_admin_required
@require_POST
def stockadjustment_cancel(request, pk):
    obj = get_object_or_404(StockAdjustment, pk=pk, tenant=request.tenant)
    if obj.status != "draft":
        messages.info(request, "Only a draft adjustment can be cancelled — a posted one is corrected by a new adjustment.")
        return redirect("scm:stockadjustment_detail", pk=pk)
    obj.status = "cancelled"
    obj.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "cancel"})
    messages.success(request, f"Adjustment {obj.number} cancelled.")
    return redirect("scm:stockadjustment_detail", pk=pk)
