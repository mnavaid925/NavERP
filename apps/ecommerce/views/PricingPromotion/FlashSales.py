from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.ecommerce.forms.PricingPromotion.FlashSales import FlashSaleForm
from apps.ecommerce.models.PricingPromotion.FlashSales import FlashSale
from apps.ecommerce.views._common import ecommerce_object, ecommerce_scope


@login_required
def flashsale_list(request):
    qs = ecommerce_scope(
        FlashSale.objects.select_related("product", "variant", "category"),
        request,
    )

    search_query = request.GET.get("q", "").strip()
    status_filter = request.GET.get("status", "").strip()

    if search_query:
        qs = qs.filter(
            Q(title__icontains=search_query)
            | Q(number__icontains=search_query)
            | Q(badge_label__icontains=search_query)
            | Q(product__name__icontains=search_query)
            | Q(variant__sku__icontains=search_query)
            | Q(category__name__icontains=search_query)
        )

    if status_filter:
        qs = qs.filter(status=status_filter)

    paginator = Paginator(qs, 25)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "sales": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "search_query": search_query,
        "current_q": search_query,
        "status_filter": status_filter,
        "current_status": status_filter,
        "status_choices": FlashSale.STATUS_CHOICES,
    }
    return render(request, "ecommerce/pricingpromotion/flashsale/list.html", context)


@login_required
def flashsale_detail(request, pk):
    sale = ecommerce_object(
        request,
        FlashSale,
        pk,
        select_related=("product", "variant", "category"),
    )
    context = {
        "sale": sale,
    }
    return render(request, "ecommerce/pricingpromotion/flashsale/detail.html", context)


@login_required
def flashsale_create(request):
    if request.method == "POST":
        form = FlashSaleForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            sale = form.save(commit=False)
            sale.tenant = request.tenant
            sale.save()
            write_audit_log(
                request.tenant,
                request.user,
                "CREATE",
                "FlashSale",
                sale.pk,
                f"Created flash sale {sale.number} ({sale.title})",
            )
            messages.success(request, f"Flash sale '{sale.title}' created successfully.")
            return redirect("ecommerce:flashsale_detail", pk=sale.pk)
    else:
        form = FlashSaleForm(tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": False,
    }
    return render(request, "ecommerce/pricingpromotion/flashsale/form.html", context)


@login_required
def flashsale_edit(request, pk):
    sale = ecommerce_object(
        request,
        FlashSale,
        pk,
        select_related=("product", "variant", "category"),
    )
    if request.method == "POST":
        form = FlashSaleForm(request.POST, instance=sale, tenant=request.tenant)
        if form.is_valid():
            sale = form.save()
            write_audit_log(
                request.tenant,
                request.user,
                "UPDATE",
                "FlashSale",
                sale.pk,
                f"Updated flash sale {sale.number} ({sale.title})",
            )
            messages.success(request, f"Flash sale '{sale.title}' updated successfully.")
            return redirect("ecommerce:flashsale_detail", pk=sale.pk)
    else:
        form = FlashSaleForm(instance=sale, tenant=request.tenant)

    context = {
        "form": form,
        "sale": sale,
        "is_edit": True,
    }
    return render(request, "ecommerce/pricingpromotion/flashsale/form.html", context)


@login_required
@tenant_admin_required
@require_POST
def flashsale_delete(request, pk):
    sale = ecommerce_object(request, FlashSale, pk)
    title = sale.title
    number = sale.number
    sale.delete()
    write_audit_log(
        request.tenant,
        request.user,
        "DELETE",
        "FlashSale",
        pk,
        f"Deleted flash sale {number} ({title})",
    )
    messages.success(request, f"Flash sale '{title}' ({number}) was deleted.")
    return redirect("ecommerce:flashsale_list")
