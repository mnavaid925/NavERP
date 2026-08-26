"""Procurement 6.9 Catalog Management — CatalogPriceTier views.

**Pricing & Tier Management**: the tier register across the tenant's catalogue, the
propose → approve/activate → retire lifecycle (guarded POST verbs), and a detail page that
prices the break against its item's current base price alongside the sibling tiers.
"""
from django.db.models import Count, Q

from apps.core.crud import crud_delete, crud_list
from apps.procurement.forms import CatalogPriceTierForm
from apps.procurement.models import CatalogItem, CatalogPriceTier
from apps.procurement.views._common import *  # noqa: F401,F403


@login_required
def catalog_tier_list(request):
    qs = (CatalogPriceTier.objects.filter(tenant=request.tenant)
          .select_related("catalog_item", "contract")
          .order_by("catalog_item_id", "min_quantity"))
    # ONE aggregate for the whole stat strip — never three queries.
    stats = CatalogPriceTier.objects.filter(tenant=request.tenant).aggregate(
        proposed=Count("pk", filter=Q(status="draft")),
        active=Count("pk", filter=Q(status="active")),
        superseded=Count("pk", filter=Q(status="superseded")),
    )
    return crud_list(
        request, qs, "procurement/catalogmanagement/tier/list.html",
        search_fields=["catalog_item__name", "catalog_item__number"],
        filters=[("status", "status", False), ("catalog_item", "catalog_item_id", True)],
        extra_context={
            "status_choices": CatalogPriceTier.STATUS_CHOICES,
            "item_choices": CatalogItem.objects.filter(tenant=request.tenant).order_by("name"),
            "stats": stats,
        },
    )


@login_required
def catalog_tier_detail(request, pk):
    obj = get_object_or_404(
        CatalogPriceTier.objects.select_related("catalog_item", "contract",
                                                "submitted_by", "approved_by"),
        pk=pk, tenant=request.tenant,
    )
    # Templates cannot pass method arguments: price THIS tier against the parent item's base
    # once here; sibling rows render their pricing rule as stored.
    base_price = obj.catalog_item.base_price
    return render(request, "procurement/catalogmanagement/tier/detail.html", {
        "obj": obj,
        "item_tiers": (obj.catalog_item.price_tiers.exclude(pk=obj.pk)
                       .select_related("contract").order_by("min_quantity")),
        "base_price": base_price,
        "effective_price": obj.effective_price(base_price),
    })


def _tier_form(request, instance):
    """Shared create/edit body (RfxEvents._event_form precedent): stamps submitted_by on
    create; edits are gated to Proposed tiers by the caller."""
    if instance is None and request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating price tiers.")
        return redirect("dashboard:home")
    is_edit = instance is not None
    if request.method == "POST":
        form = CatalogPriceTierForm(request.POST, instance=instance, tenant=request.tenant)
        if form.is_valid():
            tier = form.save(commit=False)
            tier.tenant = request.tenant
            if not is_edit:
                tier.submitted_by = request.user
            tier.save()
            write_audit_log(request.user, tier, "update" if is_edit else "create")
            messages.success(request,
                             f"Price tier saved for {tier.catalog_item.name}.")
            return redirect("procurement:catalog_tier_detail", pk=tier.pk)
    else:
        form = CatalogPriceTierForm(instance=instance, tenant=request.tenant)
    return render(request, "procurement/catalogmanagement/tier/form.html",
                  {"form": form, "is_edit": is_edit, "obj": instance})


@login_required
def catalog_tier_create(request):
    return _tier_form(request, instance=None)


@login_required
def catalog_tier_edit(request, pk):
    obj = get_object_or_404(CatalogPriceTier.objects.select_related("catalog_item"),
                            pk=pk, tenant=request.tenant)
    if obj.status != "draft":
        messages.error(request, f"This tier is {obj.get_status_display()} — only proposed "
                                f"tiers can be edited.")
        return redirect("procurement:catalog_tier_detail", pk=obj.pk)
    return _tier_form(request, instance=obj)


@login_required
@require_POST
def catalog_tier_delete(request, pk):
    return crud_delete(request, model=CatalogPriceTier, pk=pk,
                       success_url="procurement:catalog_tier_list")


# -- lifecycle -------------------------------------------------------------------------------------


@tenant_admin_required
@require_POST
def catalog_tier_approve(request, pk):
    obj = get_object_or_404(CatalogPriceTier.objects.select_related("catalog_item"),
                            pk=pk, tenant=request.tenant)
    if obj.approve(request.user):
        write_audit_log(request.user, obj, "approve")
        messages.success(request, f"Tier approved — {obj.catalog_item.name} now prices this "
                                  f"break at ≥ {obj.min_quantity} units.")
    else:
        messages.error(request, f"Only proposed tiers can be approved — this one is "
                                f"{obj.get_status_display()}.")
    return redirect("procurement:catalog_tier_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def catalog_tier_retire(request, pk):
    obj = get_object_or_404(CatalogPriceTier.objects.select_related("catalog_item"),
                            pk=pk, tenant=request.tenant)
    if obj.retire():
        write_audit_log(request.user, obj, "retire")
        messages.success(request, f"Tier retired — the ≥ {obj.min_quantity} break on "
                                  f"{obj.catalog_item.name} is now superseded.")
    else:
        messages.error(request, f"Only active tiers can be retired — this one is "
                                f"{obj.get_status_display()}.")
    return redirect("procurement:catalog_tier_detail", pk=obj.pk)
