"""SCM 4.3 Inventory Management — LotSerial views."""
from django.db.models import ProtectedError

from apps.scm.views._common import *  # noqa: F401,F403
from apps.scm.views._helpers import _need_tenant
from apps.scm.models import LotSerial, Item
from apps.scm.forms import LotSerialForm


@login_required
def lotserial_list(request):
    qs = LotSerial.objects.filter(tenant=request.tenant).select_related("item")
    return crud_list(
        request, qs, "scm/inventory/lotserial/list.html",
        search_fields=["number", "item__sku", "item__name"],
        filters=[("kind", "kind", False), ("status", "status", False), ("item", "item_id", True)],
        extra_context={
            "kind_choices": LotSerial.KIND_CHOICES,
            "status_choices": LotSerial.STATUS_CHOICES,
            "items": Item.objects.filter(tenant=request.tenant, tracking__in=("lot", "serial")),
        },
    )


@login_required
def lotserial_create(request):
    if _need_tenant(request):
        return redirect("scm:lotserial_list")
    return crud_create(request, form_class=LotSerialForm, template="scm/inventory/lotserial/form.html",
                       success_url="scm:lotserial_list")


@login_required
def lotserial_edit(request, pk):
    return crud_edit(request, model=LotSerial, pk=pk, form_class=LotSerialForm,
                     template="scm/inventory/lotserial/form.html", success_url="scm:lotserial_list")


@login_required
def lotserial_detail(request, pk):
    obj = get_object_or_404(LotSerial.objects.select_related("item"), pk=pk, tenant=request.tenant)
    return render(request, "scm/inventory/lotserial/detail.html", {
        "obj": obj,
        "on_hand": obj.on_hand(),
        "moves": obj.stock_moves.select_related("location")[:20],
        # 4.9 Quality: what has been checked on this batch and what was found. `status` already
        # carries the quarantine state — 4.9 flips it and posts NO StockMove, so this panel plus
        # the status chip IS the whole quarantine story for the lot.
        "quality_inspections": (obj.quality_inspections
                                .select_related("inspector", "plan", "location")[:10]),
        "nonconformances": obj.nonconformances.select_related("owner", "location")[:10],
    })


@login_required
@require_POST
def lotserial_delete(request, pk):
    obj = get_object_or_404(LotSerial, pk=pk, tenant=request.tenant)
    if obj.stock_moves.exists():
        messages.error(request, "This lot/serial has stock movements and cannot be deleted.")
        return redirect("scm:lotserial_detail", pk=pk)
    # A lot is now PROTECT-referenced from 4.9 as well (QualityInspection.lot_serial and
    # NonConformance.lot_serial), and it will be from every sub-module that lands after. The
    # friendly stock-movement guard above stays because it is the common case and says something
    # useful; beyond it, enumerating guards with .exists() goes stale the next time a PROTECT FK is
    # added, and the miss shows up as a 500. So ask the database and report what it names — the
    # `location_delete` shape, adopted verbatim. atomic() so the audit row crud_delete writes
    # before deleting rolls back with the failed delete.
    try:
        with transaction.atomic():
            return crud_delete(request, model=LotSerial, pk=pk, success_url="scm:lotserial_list")
    except ProtectedError as exc:
        blockers = sorted({protected._meta.verbose_name for protected in exc.protected_objects})
        messages.error(
            request,
            f"This lot/serial is still referenced by {', '.join(blockers)} and cannot be deleted.")
        return redirect("scm:lotserial_detail", pk=pk)
