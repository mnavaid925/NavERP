"""Inventory 5.8 Lot & Serial Number Tracking — ShelfLifePolicy views.

Plain CRUD, exactly the BinCapacity shape. The board that applies these regimes is the
computed FEFO page; this list is linked from its header (the 5.4 putaway-rules pattern:
a computed queue plus the rules CRUD beside it).
"""
from apps.inventory.views._common import *  # noqa: F401,F403
from apps.inventory.forms import ShelfLifePolicyForm
from apps.inventory.models import ShelfLifePolicy, classify_lot


def _scoped(tenant):
    return (ShelfLifePolicy.objects.filter(tenant=tenant)
            .select_related("item", "item__uom"))


@login_required
def shelflifepolicy_list(request):
    qs = _scoped(request.tenant)
    return crud_list(
        request, qs, "inventory/lottrack/shelflifepolicy/list.html",
        search_fields=["item__sku", "item__name", "notes"],
        filters=[("fefo", "fefo_enforced", False)],
        extra_context={"policy_count": qs.count()},
    )


@login_required
def shelflifepolicy_detail(request, pk):
    obj = get_object_or_404(_scoped(request.tenant), pk=pk)
    # The lots this regime currently governs — read live from the spine, classified
    # with the ONE shared classifier so this panel and the FEFO board can never
    # disagree about what a date means.
    lot_rows = [
        {"lot": lot, "flag": flag, "css": css, "label": label}
        for lot in obj.item.lot_serials.order_by("expiry_date", "number")[:12]
        for (flag, css, label) in [classify_lot(lot, obj)]
    ]
    return render(request, "inventory/lottrack/shelflifepolicy/detail.html", {
        "obj": obj,
        "lot_rows": lot_rows,
    })


@login_required
def shelflifepolicy_create(request):
    return crud_create(
        request, form_class=ShelfLifePolicyForm,
        template="inventory/lottrack/shelflifepolicy/form.html",
        success_url="inventory:shelflifepolicy_list",
    )


@login_required
def shelflifepolicy_edit(request, pk):
    return crud_edit(
        request, model=ShelfLifePolicy, pk=pk, form_class=ShelfLifePolicyForm,
        template="inventory/lottrack/shelflifepolicy/form.html",
        success_url="inventory:shelflifepolicy_list",
    )


@login_required
@require_POST
def shelflifepolicy_delete(request, pk):
    return crud_delete(request, model=ShelfLifePolicy, pk=pk,
                       success_url="inventory:shelflifepolicy_list")
