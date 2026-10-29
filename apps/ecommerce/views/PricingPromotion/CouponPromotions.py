from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.ecommerce.forms.PricingPromotion.CouponPromotions import CouponPromotionForm
from apps.ecommerce.models.PricingPromotion.CouponPromotions import CouponPromotion
from apps.ecommerce.views._common import ecommerce_object, ecommerce_scope


@login_required
def couponpromotion_list(request):
    qs = ecommerce_scope(
        CouponPromotion.objects.select_related("customer"),
        request,
    )

    search_query = request.GET.get("q", "").strip()
    discount_type_filter = request.GET.get("discount_type", "").strip()
    tier_filter = request.GET.get("loyalty_tier", "").strip()
    active_filter = request.GET.get("is_active", "").strip()

    if search_query:
        qs = qs.filter(
            Q(code__icontains=search_query)
            | Q(name__icontains=search_query)
            | Q(number__icontains=search_query)
            | Q(customer__name__icontains=search_query)
        )

    if discount_type_filter:
        qs = qs.filter(discount_type=discount_type_filter)

    if tier_filter:
        qs = qs.filter(loyalty_tier_required=tier_filter)

    if active_filter in ("1", "true"):
        qs = qs.filter(is_active=True)
    elif active_filter in ("0", "false"):
        qs = qs.filter(is_active=False)

    paginator = Paginator(qs, 25)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "coupons": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "search_query": search_query,
        "current_q": search_query,
        "discount_type_filter": discount_type_filter,
        "current_type": discount_type_filter,
        "tier_filter": tier_filter,
        "current_tier": tier_filter,
        "active_filter": active_filter,
        "current_status": active_filter,
        "discount_type_choices": CouponPromotion.DISCOUNT_TYPE_CHOICES,
        "loyalty_tier_choices": CouponPromotion.LOYALTY_TIER_CHOICES,
    }
    return render(request, "ecommerce/pricingpromotion/couponpromotion/list.html", context)


@login_required
def couponpromotion_detail(request, pk):
    coupon = ecommerce_object(
        request,
        CouponPromotion,
        pk,
        select_related=("customer",),
    )
    context = {
        "coupon": coupon,
    }
    return render(request, "ecommerce/pricingpromotion/couponpromotion/detail.html", context)


@login_required
def couponpromotion_create(request):
    if request.method == "POST":
        form = CouponPromotionForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            coupon = form.save(commit=False)
            coupon.tenant = request.tenant
            coupon.save()
            write_audit_log(
                request.user,
                coupon,
                "create",
                {"code": coupon.code, "name": coupon.name},
            )
            messages.success(request, f"Coupon code '{coupon.code}' created successfully.")
            return redirect("ecommerce:couponpromotion_detail", pk=coupon.pk)
    else:
        form = CouponPromotionForm(tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": False,
    }
    return render(request, "ecommerce/pricingpromotion/couponpromotion/form.html", context)


@login_required
def couponpromotion_edit(request, pk):
    coupon = ecommerce_object(
        request,
        CouponPromotion,
        pk,
        select_related=("customer",),
    )
    if request.method == "POST":
        form = CouponPromotionForm(request.POST, instance=coupon, tenant=request.tenant)
        if form.is_valid():
            coupon = form.save()
            write_audit_log(
                request.user,
                coupon,
                "update",
                {"code": coupon.code, "name": coupon.name},
            )
            messages.success(request, f"Coupon code '{coupon.code}' updated successfully.")
            return redirect("ecommerce:couponpromotion_detail", pk=coupon.pk)
    else:
        form = CouponPromotionForm(instance=coupon, tenant=request.tenant)

    context = {
        "form": form,
        "coupon": coupon,
        "is_edit": True,
    }
    return render(request, "ecommerce/pricingpromotion/couponpromotion/form.html", context)


@login_required
@tenant_admin_required
@require_POST
def couponpromotion_delete(request, pk):
    coupon = ecommerce_object(request, CouponPromotion, pk)
    code = coupon.code
    number = coupon.number
    coupon.delete()
    write_audit_log(
        request.user,
        coupon,
        "delete",
        {"code": code, "number": number},
    )
    messages.success(request, f"Coupon '{code}' was deleted.")
    return redirect("ecommerce:couponpromotion_list")
