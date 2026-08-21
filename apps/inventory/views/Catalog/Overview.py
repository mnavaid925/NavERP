"""Inventory 5.1 Product & Catalog Management — the module landing page.

A computed read over the catalog layer this sub-module owns plus the spine it sits on: SKU counts,
category tree size, and how much of the catalog carries attributes, prices and imagery. Every
figure is an aggregate at render time; nothing here stores a number.
"""
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import render

from apps.inventory.models import ItemAttribute, ItemPrice, ProductFile
from apps.scm.models import Item, ItemCategory


@login_required
def overview(request):
    tenant = request.tenant
    items = Item.objects.filter(tenant=tenant)
    stats = {
        "skus": items.count(),
        "active_skus": items.filter(is_active=True).count(),
        "categories": ItemCategory.objects.filter(tenant=tenant).count(),
        "attributes": ItemAttribute.objects.filter(tenant=tenant).count(),
        "prices": ItemPrice.objects.filter(tenant=tenant).count(),
        "files": ProductFile.objects.filter(tenant=tenant).count(),
    }
    recent_files = (ProductFile.objects.filter(tenant=tenant)
                    .select_related("item").order_by("-created_at")[:6])
    # The coverage figures say how complete the catalog DATA is — a SKU with no price row or no
    # image is a gap in the catalog, not an error, so they read as progress bars not alerts.
    priced_items = (ItemPrice.objects.filter(tenant=tenant, is_active=True)
                    .values("item_id").distinct().count())
    imaged_items = (ProductFile.objects.filter(tenant=tenant, kind="photo")
                    .values("item_id").distinct().count())
    top_categories = (ItemCategory.objects.filter(tenant=tenant)
                      .annotate(item_count=Count("items", filter=Q(items__tenant=tenant)))
                      .order_by("-item_count")[:6])
    return render(request, "inventory/overview.html", {
        "stats": stats,
        "recent_files": recent_files,
        "top_categories": top_categories,
        "priced_items": priced_items,
        "imaged_items": imaged_items,
    })
