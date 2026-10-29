from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.models.Party import Party
from apps.core.utils import write_audit_log
from apps.ecommerce.forms.CustomerProfile.CustomerWishlists import CustomerWishlistForm, CustomerWishlistItemForm
from apps.ecommerce.models.CustomerProfile.CustomerWishlists import CustomerWishlist, CustomerWishlistItem
from apps.ecommerce.models.ProductCatalog.CatalogProducts import CatalogProduct
from apps.ecommerce.views._common import ecommerce_object, ecommerce_scope


@login_required
def customerwishlist_list(request):
    qs = ecommerce_scope(
        CustomerWishlist.objects.select_related("customer").prefetch_related("items"),
        request,
    )

    search_query = request.GET.get("q", "").strip()
    visibility_filter = request.GET.get("visibility", "").strip()

    if search_query:
        qs = qs.filter(
            Q(number__icontains=search_query)
            | Q(name__icontains=search_query)
            | Q(customer__name__icontains=search_query)
            | Q(share_token__icontains=search_query)
        )

    if visibility_filter:
        qs = qs.filter(visibility=visibility_filter)

    paginator = Paginator(qs, 25)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "wishlists": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "q": search_query,
        "search_query": search_query,
        "visibility_choices": CustomerWishlist.VISIBILITY_CHOICES,
        "current_visibility": visibility_filter,
    }
    return render(
        request,
        "ecommerce/customerprofile/customerwishlist/list.html",
        context,
    )


@login_required
def customerwishlist_detail(request, pk):
    wishlist = ecommerce_object(
        request,
        CustomerWishlist,
        pk,
        select_related=("customer",),
        prefetch_related=("items__product", "items__variant"),
    )
    items = wishlist.items.all().select_related("product", "variant")
    products = CatalogProduct.objects.filter(tenant=request.tenant, status="active")

    context = {
        "wishlist": wishlist,
        "items": items,
        "products": products,
        "priority_choices": CustomerWishlistItem.PRIORITY_CHOICES,
    }
    return render(
        request,
        "ecommerce/customerprofile/customerwishlist/detail.html",
        context,
    )


@login_required
@tenant_admin_required
def customerwishlist_create(request):
    if request.method == "POST":
        form = CustomerWishlistForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            wishlist = form.save(commit=False)
            wishlist.tenant = request.tenant
            wishlist.save()
            write_audit_log(
                request.user,
                wishlist,
                "create",
                changes={"number": wishlist.number, "name": wishlist.name},
                tenant=request.tenant,
            )
            messages.success(request, f"Wishlist {wishlist.name} ({wishlist.number}) created successfully.")
            return redirect("ecommerce:customerwishlist_detail", pk=wishlist.pk)
    else:
        form = CustomerWishlistForm(tenant=request.tenant)

    customers = Party.objects.filter(tenant=request.tenant)
    context = {
        "form": form,
        "customers": customers,
        "is_edit": False,
    }
    return render(
        request,
        "ecommerce/customerprofile/customerwishlist/form.html",
        context,
    )


@login_required
@tenant_admin_required
def customerwishlist_edit(request, pk):
    wishlist = ecommerce_object(request, CustomerWishlist, pk)
    if request.method == "POST":
        form = CustomerWishlistForm(request.POST, instance=wishlist, tenant=request.tenant)
        if form.is_valid():
            wishlist = form.save()
            write_audit_log(
                request.user,
                wishlist,
                "update",
                changes={"number": wishlist.number, "name": wishlist.name},
                tenant=request.tenant,
            )
            messages.success(request, f"Wishlist {wishlist.name} ({wishlist.number}) updated successfully.")
            return redirect("ecommerce:customerwishlist_detail", pk=wishlist.pk)
    else:
        form = CustomerWishlistForm(instance=wishlist, tenant=request.tenant)

    customers = Party.objects.filter(tenant=request.tenant)
    context = {
        "form": form,
        "wishlist": wishlist,
        "customers": customers,
        "is_edit": True,
    }
    return render(
        request,
        "ecommerce/customerprofile/customerwishlist/form.html",
        context,
    )


@login_required
@tenant_admin_required
@require_POST
def customerwishlist_delete(request, pk):
    wishlist = ecommerce_object(request, CustomerWishlist, pk)
    number = wishlist.number
    name = wishlist.name
    write_audit_log(
        request.user,
        wishlist,
        "delete",
        changes={"number": number, "name": name},
        tenant=request.tenant,
    )
    wishlist.delete()
    messages.success(request, f"Wishlist {name} ({number}) deleted successfully.")
    return redirect("ecommerce:customerwishlist_list")


@login_required
@require_POST
def customerwishlist_item_add(request, pk):
    wishlist = ecommerce_object(request, CustomerWishlist, pk)
    product_id = request.POST.get("product")
    if not product_id or not str(product_id).isdigit():
        messages.error(request, "Please select a valid product.")
        return redirect("ecommerce:customerwishlist_detail", pk=wishlist.pk)

    variant_id = request.POST.get("variant") or None
    try:
        raw_qty = int(request.POST.get("desired_quantity", 1) or 1)
        desired_qty = max(1, min(raw_qty, 9999))
    except (ValueError, TypeError):
        desired_qty = 1
    priority = request.POST.get("priority", "medium")
    comment = request.POST.get("comment", "").strip()

    product = get_object_or_404(CatalogProduct, pk=product_id, tenant=request.tenant)
    variant = None
    if variant_id:
        from apps.ecommerce.models.ProductCatalog.ProductVariants import ProductVariant

        variant = get_object_or_404(ProductVariant, pk=variant_id, tenant=request.tenant, product=product)

    item, created = CustomerWishlistItem.objects.get_or_create(
        tenant=request.tenant,
        wishlist=wishlist,
        product=product,
        variant=variant,
        defaults={
            "desired_quantity": desired_qty,
            "priority": priority,
            "comment": comment,
        },
    )
    if not created:
        item.desired_quantity += desired_qty
        if comment:
            item.comment = comment
        item.save()

    messages.success(request, f"Added {product.name} to wishlist.")
    return redirect("ecommerce:customerwishlist_detail", pk=wishlist.pk)


@login_required
@require_POST
def customerwishlist_item_delete(request, item_pk):
    item = ecommerce_object(request, CustomerWishlistItem, item_pk)
    wishlist_pk = item.wishlist.pk
    product_name = item.product.name
    item.delete()
    messages.success(request, f"Removed {product_name} from wishlist.")
    return redirect("ecommerce:customerwishlist_detail", pk=wishlist_pk)
