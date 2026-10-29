from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.models.Address import Address
from apps.core.models.Party import Party
from apps.core.utils import write_audit_log
from apps.ecommerce.forms.CustomerProfile.CustomerAddressPreferences import CustomerAddressPreferenceForm
from apps.ecommerce.models.CustomerProfile.CustomerAddressPreferences import CustomerAddressPreference
from apps.ecommerce.views._common import ecommerce_object, ecommerce_scope


@login_required
def customeraddresspreference_list(request):
    qs = ecommerce_scope(
        CustomerAddressPreference.objects.select_related("customer", "address"),
        request,
    )

    search_query = request.GET.get("q", "").strip()
    window_filter = request.GET.get("window", "").strip()

    if search_query:
        qs = qs.filter(
            Q(number__icontains=search_query)
            | Q(label__icontains=search_query)
            | Q(customer__name__icontains=search_query)
            | Q(recipient_name__icontains=search_query)
            | Q(delivery_instructions__icontains=search_query)
            | Q(address__city__icontains=search_query)
        )

    if window_filter:
        qs = qs.filter(preferred_delivery_window=window_filter)

    paginator = Paginator(qs, 25)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "preferences": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "q": search_query,
        "search_query": search_query,
        "window_choices": CustomerAddressPreference.WINDOW_CHOICES,
        "current_window": window_filter,
    }
    return render(
        request,
        "ecommerce/customerprofile/customeraddresspreference/list.html",
        context,
    )


@login_required
def customeraddresspreference_detail(request, pk):
    preference = ecommerce_object(
        request,
        CustomerAddressPreference,
        pk,
        select_related=("customer", "address"),
    )
    context = {
        "preference": preference,
    }
    return render(
        request,
        "ecommerce/customerprofile/customeraddresspreference/detail.html",
        context,
    )


@login_required
@tenant_admin_required
def customeraddresspreference_create(request):
    if request.method == "POST":
        form = CustomerAddressPreferenceForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            pref = form.save(commit=False)
            pref.tenant = request.tenant
            pref.save()
            write_audit_log(
                request.user,
                pref,
                "create",
                changes={"number": pref.number},
                tenant=request.tenant,
            )
            messages.success(request, f"Address preference {pref.number} created successfully.")
            return redirect("ecommerce:customeraddresspreference_detail", pk=pref.pk)
    else:
        form = CustomerAddressPreferenceForm(tenant=request.tenant)

    customers = Party.objects.filter(tenant=request.tenant)
    addresses = Address.objects.filter(tenant=request.tenant)
    context = {
        "form": form,
        "customers": customers,
        "addresses": addresses,
        "is_edit": False,
    }
    return render(
        request,
        "ecommerce/customerprofile/customeraddresspreference/form.html",
        context,
    )


@login_required
@tenant_admin_required
def customeraddresspreference_edit(request, pk):
    preference = ecommerce_object(request, CustomerAddressPreference, pk)
    if request.method == "POST":
        form = CustomerAddressPreferenceForm(request.POST, instance=preference, tenant=request.tenant)
        if form.is_valid():
            preference = form.save()
            write_audit_log(
                request.user,
                preference,
                "update",
                changes={"number": preference.number},
                tenant=request.tenant,
            )
            messages.success(request, f"Address preference {preference.number} updated successfully.")
            return redirect("ecommerce:customeraddresspreference_detail", pk=preference.pk)
    else:
        form = CustomerAddressPreferenceForm(instance=preference, tenant=request.tenant)

    customers = Party.objects.filter(tenant=request.tenant)
    addresses = Address.objects.filter(tenant=request.tenant)
    context = {
        "form": form,
        "preference": preference,
        "customers": customers,
        "addresses": addresses,
        "is_edit": True,
    }
    return render(
        request,
        "ecommerce/customerprofile/customeraddresspreference/form.html",
        context,
    )


@login_required
@tenant_admin_required
@require_POST
def customeraddresspreference_delete(request, pk):
    preference = ecommerce_object(request, CustomerAddressPreference, pk)
    number = preference.number
    write_audit_log(
        request.user,
        preference,
        "delete",
        changes={"number": number},
        tenant=request.tenant,
    )
    preference.delete()
    messages.success(request, f"Address preference {number} deleted successfully.")
    return redirect("ecommerce:customeraddresspreference_list")
