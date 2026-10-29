import json
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.models.Party import Party
from apps.core.utils import write_audit_log
from apps.ecommerce.forms.CustomerProfile.CustomerPrivacyRequests import CustomerPrivacyRequestForm
from apps.ecommerce.models.CustomerProfile.CustomerAccountProfiles import CustomerAccountProfile
from apps.ecommerce.models.CustomerProfile.CustomerAddressPreferences import CustomerAddressPreference
from apps.ecommerce.models.CustomerProfile.CustomerPrivacyRequests import CustomerPrivacyRequest
from apps.ecommerce.models.CustomerProfile.CustomerWishlists import CustomerWishlist
from apps.ecommerce.views._common import ecommerce_object, ecommerce_scope


@login_required
def customerprivacyrequest_list(request):
    qs = ecommerce_scope(
        CustomerPrivacyRequest.objects.select_related("customer"),
        request,
    )

    search_query = request.GET.get("q", "").strip()
    type_filter = request.GET.get("request_type", "").strip()
    status_filter = request.GET.get("status", "").strip()

    if search_query:
        qs = qs.filter(
            Q(number__icontains=search_query)
            | Q(customer__name__icontains=search_query)
            | Q(requested_by_email__icontains=search_query)
            | Q(resolution_notes__icontains=search_query)
        )

    if type_filter:
        qs = qs.filter(request_type=type_filter)

    if status_filter:
        qs = qs.filter(status=status_filter)

    paginator = Paginator(qs, 25)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "requests": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "q": search_query,
        "search_query": search_query,
        "type_choices": CustomerPrivacyRequest.REQUEST_TYPE_CHOICES,
        "status_choices": CustomerPrivacyRequest.STATUS_CHOICES,
        "current_type": type_filter,
        "current_status": status_filter,
    }
    return render(
        request,
        "ecommerce/customerprofile/customerprivacyrequest/list.html",
        context,
    )


@login_required
def customerprivacyrequest_detail(request, pk):
    privacy_request = ecommerce_object(
        request,
        CustomerPrivacyRequest,
        pk,
        select_related=("customer",),
    )
    context = {
        "privacy_request": privacy_request,
    }
    return render(
        request,
        "ecommerce/customerprofile/customerprivacyrequest/detail.html",
        context,
    )


@login_required
@tenant_admin_required
def customerprivacyrequest_create(request):
    if request.method == "POST":
        form = CustomerPrivacyRequestForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            req = form.save(commit=False)
            req.tenant = request.tenant
            req.save()
            write_audit_log(
                request.user,
                req,
                "create",
                changes={"number": req.number},
                tenant=request.tenant,
            )
            messages.success(request, f"Privacy request {req.number} registered successfully.")
            return redirect("ecommerce:customerprivacyrequest_detail", pk=req.pk)
    else:
        form = CustomerPrivacyRequestForm(tenant=request.tenant)

    customers = Party.objects.filter(tenant=request.tenant)
    context = {
        "form": form,
        "customers": customers,
        "is_edit": False,
    }
    return render(
        request,
        "ecommerce/customerprofile/customerprivacyrequest/form.html",
        context,
    )


@login_required
@tenant_admin_required
def customerprivacyrequest_edit(request, pk):
    privacy_request = ecommerce_object(request, CustomerPrivacyRequest, pk)
    if request.method == "POST":
        form = CustomerPrivacyRequestForm(request.POST, instance=privacy_request, tenant=request.tenant)
        if form.is_valid():
            privacy_request = form.save()
            write_audit_log(
                request.user,
                privacy_request,
                "update",
                changes={"number": privacy_request.number},
                tenant=request.tenant,
            )
            messages.success(request, f"Privacy request {privacy_request.number} updated successfully.")
            return redirect("ecommerce:customerprivacyrequest_detail", pk=privacy_request.pk)
    else:
        form = CustomerPrivacyRequestForm(instance=privacy_request, tenant=request.tenant)

    customers = Party.objects.filter(tenant=request.tenant)
    context = {
        "form": form,
        "privacy_request": privacy_request,
        "customers": customers,
        "is_edit": True,
    }
    return render(
        request,
        "ecommerce/customerprofile/customerprivacyrequest/form.html",
        context,
    )


@login_required
@tenant_admin_required
@require_POST
def customerprivacyrequest_delete(request, pk):
    privacy_request = ecommerce_object(request, CustomerPrivacyRequest, pk)
    number = privacy_request.number
    write_audit_log(
        request.user,
        privacy_request,
        "delete",
        changes={"number": number},
        tenant=request.tenant,
    )
    privacy_request.delete()
    messages.success(request, f"Privacy request {number} deleted successfully.")
    return redirect("ecommerce:customerprivacyrequest_list")


@login_required
@tenant_admin_required
@require_POST
def customerprivacyrequest_generate_export(request, pk):
    privacy_request = ecommerce_object(request, CustomerPrivacyRequest, pk)
    customer = privacy_request.customer

    # Assemble JSON export payload
    profile_data = {}
    profile = CustomerAccountProfile.objects.filter(
        tenant=request.tenant, customer=customer
    ).select_related("preferred_currency").first()
    if profile:
        profile_data = {
            "profile_number": profile.number,
            "tier": profile.tier,
            "phone_number": profile.phone_number,
            "preferred_currency": profile.preferred_currency.code if profile.preferred_currency else "USD",
            "email_opt_in": profile.email_marketing_opt_in,
            "sms_opt_in": profile.sms_marketing_opt_in,
            "total_spent": str(profile.total_spent),
            "order_count": profile.order_count,
        }

    address_data = []
    for pref in CustomerAddressPreference.objects.filter(
        tenant=request.tenant, customer=customer
    ).select_related("address"):
        address_data.append({
            "label": pref.label,
            "line1": pref.address.line1 if pref.address else "",
            "city": pref.address.city if pref.address else "",
            "country": pref.address.country if pref.address else "",
            "postal_code": getattr(pref.address, "postal_code", "") if pref.address else "",
            "instructions": pref.delivery_instructions,
        })

    wishlist_data = []
    for w in CustomerWishlist.objects.filter(
        tenant=request.tenant, customer=customer
    ).annotate(items_count=Count("items")):
        wishlist_data.append({
            "name": w.name,
            "items_count": w.items_count,
        })

    export_payload = {
        "export_date": timezone.now().isoformat(),
        "customer_id": customer.pk,
        "customer_name": customer.name,
        "profile": profile_data,
        "addresses": address_data,
        "wishlists": wishlist_data,
    }

    privacy_request.data_export_payload = export_payload
    privacy_request.status = "completed"
    privacy_request.completed_at = timezone.now()
    privacy_request.resolution_notes = f"Machine-readable JSON data portability export compiled on {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}."
    privacy_request.save()

    write_audit_log(
        request.user,
        privacy_request,
        "export",
        changes={"customer": customer.name, "action": "dsar_export"},
        tenant=request.tenant,
    )
    messages.success(request, f"Data portability export payload generated for {privacy_request.number}.")
    return redirect("ecommerce:customerprivacyrequest_detail", pk=privacy_request.pk)


@login_required
@tenant_admin_required
@require_POST
def customerprivacyrequest_anonymize(request, pk):
    privacy_request = ecommerce_object(request, CustomerPrivacyRequest, pk)
    if privacy_request.request_type != "erasure_anonymize":
        messages.error(request, "Only erasure / anonymization requests can be processed for data anonymization.")
        return redirect("ecommerce:customerprivacyrequest_detail", pk=privacy_request.pk)

    customer = privacy_request.customer

    with transaction.atomic():
        # Anonymize Customer Profile
        profile = CustomerAccountProfile.objects.filter(tenant=request.tenant, customer=customer).first()
        if profile:
            if profile.user:
                auth_user = profile.user
                auth_user.is_active = False
                auth_user.email = f"erased_{auth_user.pk}@anonymized.local"
                auth_user.save(update_fields=["is_active", "email"])
            profile.phone_number = ""
            profile.phone_verified = False
            profile.user = None
            profile.email_marketing_opt_in = False
            profile.sms_marketing_opt_in = False
            profile.status = "anonymized"
            profile.internal_notes = f"GDPR Anonymized per {privacy_request.number} on {timezone.now().strftime('%Y-%m-%d')}."
            profile.save()

        # Clear address preference instructions and contact numbers
        CustomerAddressPreference.objects.filter(tenant=request.tenant, customer=customer).update(
            recipient_name="GDPR Anonymized",
            contact_phone="",
            delivery_instructions="",
        )

        # Anonymize customer wishlists
        CustomerWishlist.objects.filter(tenant=request.tenant, customer=customer).update(
            name="Anonymized Wishlist",
            visibility="private",
            share_token="",
            notes="",
        )

        privacy_request.status = "completed"
        privacy_request.completed_at = timezone.now()
        privacy_request.resolution_notes = f"Customer PII anonymized and marketing opt-ins revoked on {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}."
        privacy_request.save()

        write_audit_log(
            request.user,
            privacy_request,
            "anonymize",
            changes={"customer": customer.name, "action": "gdpr_erasure"},
            tenant=request.tenant,
        )

    messages.success(request, f"Customer PII anonymized successfully under {privacy_request.number}.")
    return redirect("ecommerce:customerprivacyrequest_detail", pk=privacy_request.pk)
