from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.models.Party import Party
from apps.core.utils import write_audit_log
from apps.ecommerce.forms.CustomerProfile.CustomerAccountProfiles import CustomerAccountProfileForm
from apps.ecommerce.models.CustomerProfile.CustomerAccountProfiles import CustomerAccountProfile
from apps.ecommerce.views._common import ecommerce_object, ecommerce_scope


@login_required
def customeraccountprofile_list(request):
    qs = ecommerce_scope(
        CustomerAccountProfile.objects.select_related("customer", "user", "preferred_currency"),
        request,
    )

    search_query = request.GET.get("q", "").strip()
    status_filter = request.GET.get("status", "").strip()
    tier_filter = request.GET.get("tier", "").strip()
    auth_filter = request.GET.get("auth_mode", "").strip()

    if search_query:
        qs = qs.filter(
            Q(number__icontains=search_query)
            | Q(customer__name__icontains=search_query)
            | Q(phone_number__icontains=search_query)
            | Q(user__username__icontains=search_query)
            | Q(user__email__icontains=search_query)
        )

    if status_filter:
        qs = qs.filter(status=status_filter)

    if tier_filter:
        qs = qs.filter(tier=tier_filter)

    if auth_filter:
        qs = qs.filter(auth_mode=auth_filter)

    paginator = Paginator(qs, 25)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "profiles": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "q": search_query,
        "search_query": search_query,
        "status_choices": CustomerAccountProfile.STATUS_CHOICES,
        "tier_choices": CustomerAccountProfile.TIER_CHOICES,
        "auth_mode_choices": CustomerAccountProfile.AUTH_MODE_CHOICES,
        "current_status": status_filter,
        "current_tier": tier_filter,
        "current_auth": auth_filter,
    }
    return render(
        request,
        "ecommerce/customerprofile/customeraccountprofile/list.html",
        context,
    )


@login_required
def customeraccountprofile_detail(request, pk):
    profile = ecommerce_object(
        request,
        CustomerAccountProfile,
        pk,
        select_related=("customer", "user", "preferred_currency"),
    )

    # Related items via core.Party
    recent_orders = []
    if hasattr(profile.customer, "ecommerce_orders"):
        recent_orders = profile.customer.ecommerce_orders.filter(tenant=request.tenant).order_by("-created_at")[:10]

    address_preferences = []
    if hasattr(profile.customer, "ecommerce_address_preferences"):
        address_preferences = profile.customer.ecommerce_address_preferences.filter(
            tenant=request.tenant
        ).select_related("address")

    wishlists = []
    if hasattr(profile.customer, "ecommerce_wishlists"):
        wishlists = profile.customer.ecommerce_wishlists.filter(tenant=request.tenant).prefetch_related("items")

    privacy_requests = []
    if hasattr(profile.customer, "ecommerce_privacy_requests"):
        privacy_requests = profile.customer.ecommerce_privacy_requests.filter(tenant=request.tenant).order_by(
            "-created_at"
        )

    context = {
        "profile": profile,
        "recent_orders": recent_orders,
        "address_preferences": address_preferences,
        "wishlists": wishlists,
        "privacy_requests": privacy_requests,
    }
    return render(
        request,
        "ecommerce/customerprofile/customeraccountprofile/detail.html",
        context,
    )


@login_required
@tenant_admin_required
def customeraccountprofile_create(request):
    if request.method == "POST":
        form = CustomerAccountProfileForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            profile = form.save(commit=False)
            profile.tenant = request.tenant
            profile.save()
            write_audit_log(
                request.user,
                profile,
                "create",
                changes={"number": profile.number},
                tenant=request.tenant,
            )
            messages.success(request, f"Customer profile {profile.number} created successfully.")
            return redirect("ecommerce:customeraccountprofile_detail", pk=profile.pk)
    else:
        form = CustomerAccountProfileForm(tenant=request.tenant)

    customers = Party.objects.filter(tenant=request.tenant)
    context = {
        "form": form,
        "customers": customers,
        "is_edit": False,
    }
    return render(
        request,
        "ecommerce/customerprofile/customeraccountprofile/form.html",
        context,
    )


@login_required
@tenant_admin_required
def customeraccountprofile_edit(request, pk):
    profile = ecommerce_object(request, CustomerAccountProfile, pk)
    if request.method == "POST":
        form = CustomerAccountProfileForm(request.POST, instance=profile, tenant=request.tenant)
        if form.is_valid():
            profile = form.save()
            write_audit_log(
                request.user,
                profile,
                "update",
                changes={"number": profile.number},
                tenant=request.tenant,
            )
            messages.success(request, f"Customer profile {profile.number} updated successfully.")
            return redirect("ecommerce:customeraccountprofile_detail", pk=profile.pk)
    else:
        form = CustomerAccountProfileForm(instance=profile, tenant=request.tenant)

    customers = Party.objects.filter(tenant=request.tenant)
    context = {
        "form": form,
        "profile": profile,
        "customers": customers,
        "is_edit": True,
    }
    return render(
        request,
        "ecommerce/customerprofile/customeraccountprofile/form.html",
        context,
    )


@login_required
@tenant_admin_required
@require_POST
def customeraccountprofile_delete(request, pk):
    profile = ecommerce_object(request, CustomerAccountProfile, pk)
    number = profile.number
    write_audit_log(
        request.user,
        profile,
        "delete",
        changes={"number": number},
        tenant=request.tenant,
    )
    profile.delete()
    messages.success(request, f"Customer profile {number} deleted successfully.")
    return redirect("ecommerce:customeraccountprofile_list")
