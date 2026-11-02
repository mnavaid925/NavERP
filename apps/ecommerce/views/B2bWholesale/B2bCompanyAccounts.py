from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.ecommerce.forms.B2bWholesale.B2bCompanyAccounts import B2bCompanyAccountForm
from apps.ecommerce.models.B2bWholesale.B2bCompanyAccounts import B2bCompanyAccount
from apps.ecommerce.views._common import ecommerce_object, ecommerce_scope


@login_required
def b2bcompanyaccount_list(request):
    qs = ecommerce_scope(
        B2bCompanyAccount.objects.select_related("company_party", "primary_contact", "preferred_currency"),
        request,
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(company_name__icontains=q)
            | Q(number__icontains=q)
            | Q(company_tax_id__icontains=q)
            | Q(business_registration_number__icontains=q)
            | Q(industry__icontains=q)
        )

    selected_status = request.GET.get("status", "").strip()
    if selected_status:
        qs = qs.filter(status=selected_status)

    selected_credit_status = request.GET.get("credit_status", "").strip()
    if selected_credit_status:
        qs = qs.filter(credit_status=selected_credit_status)

    selected_payment_terms = request.GET.get("payment_terms", "").strip()
    if selected_payment_terms:
        qs = qs.filter(payment_terms=selected_payment_terms)

    stats = ecommerce_scope(B2bCompanyAccount.objects.all(), request).aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(status="active")),
        total_credit=Sum("credit_limit"),
        avail_credit=Sum("available_credit"),
    )
    total_count = stats["total"] or 0
    active_count = stats["active"] or 0
    total_credit_granted = stats["total_credit"] or Decimal("0.00")
    total_available_credit = stats["avail_credit"] or Decimal("0.00")

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "company_accounts": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "total_count": total_count,
        "active_count": active_count,
        "total_credit_granted": total_credit_granted,
        "total_available_credit": total_available_credit,
        "status_choices": B2bCompanyAccount.STATUS_CHOICES,
        "credit_status_choices": B2bCompanyAccount.CREDIT_STATUS_CHOICES,
        "payment_terms_choices": B2bCompanyAccount.PAYMENT_TERMS_CHOICES,
        "search_query": q,
        "selected_status": selected_status,
        "selected_credit_status": selected_credit_status,
        "selected_payment_terms": selected_payment_terms,
    }
    return render(request, "ecommerce/b2b_wholesale/b2b_company_account/list.html", context)


@login_required
def b2bcompanyaccount_detail(request, pk):
    account = ecommerce_object(
        request,
        B2bCompanyAccount,
        pk,
        select_related=("company_party", "primary_contact", "preferred_currency", "default_approver"),
    )

    company_users = account.company_users.select_related("user", "party").order_by("user__username")
    quote_requests = account.quote_requests.select_related("requested_by", "currency").order_by("-created_at")[:10]
    quick_order_templates = account.quick_order_templates.select_related("created_by").order_by("-created_at")[:10]

    context = {
        "company_account": account,
        "company_users": company_users,
        "quote_requests": quote_requests,
        "quick_order_templates": quick_order_templates,
    }
    return render(request, "ecommerce/b2b_wholesale/b2b_company_account/detail.html", context)


@login_required
@tenant_admin_required
def b2bcompanyaccount_create(request):
    if request.method == "POST":
        form = B2bCompanyAccountForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            account = form.save(commit=False)
            account.tenant = request.tenant
            account.save()
            write_audit_log(
                request.user,
                account,
                "create",
                {"number": account.number, "company_name": account.company_name},
                tenant=request.tenant,
            )
            messages.success(request, f"B2B Company Account {account.company_name} registered successfully.")
            return redirect("ecommerce:b2bcompanyaccount_detail", pk=account.pk)
    else:
        form = B2bCompanyAccountForm(tenant=request.tenant)

    context = {
        "form": form,
        "title": "Register B2B Company Account",
    }
    return render(request, "ecommerce/b2b_wholesale/b2b_company_account/form.html", context)


@login_required
@tenant_admin_required
def b2bcompanyaccount_edit(request, pk):
    account = ecommerce_object(request, B2bCompanyAccount, pk)
    if request.method == "POST":
        form = B2bCompanyAccountForm(request.POST, instance=account, tenant=request.tenant)
        if form.is_valid():
            account = form.save()
            write_audit_log(
                request.user,
                account,
                "update",
                {"number": account.number, "company_name": account.company_name},
                tenant=request.tenant,
            )
            messages.success(request, f"B2B Company Account {account.company_name} updated successfully.")
            return redirect("ecommerce:b2bcompanyaccount_detail", pk=account.pk)
    else:
        form = B2bCompanyAccountForm(instance=account, tenant=request.tenant)

    context = {
        "form": form,
        "company_account": account,
        "title": f"Edit B2B Company: {account.company_name}",
    }
    return render(request, "ecommerce/b2b_wholesale/b2b_company_account/form.html", context)


@login_required
@tenant_admin_required
def b2bcompanyaccount_delete(request, pk):
    account = ecommerce_object(request, B2bCompanyAccount, pk)
    if request.method == "POST":
        name = account.company_name
        num = account.number
        account.delete()
        write_audit_log(
            request.user,
            account,
            "delete",
            {"number": num, "company_name": name},
            tenant=request.tenant,
        )
        messages.success(request, f"B2B Company Account {name} ({num}) has been deleted.")
        return redirect("ecommerce:b2bcompanyaccount_list")

    return render(
        request,
        "ecommerce/b2b_wholesale/b2b_company_account/detail.html",
        {"company_account": account, "show_delete_confirm": True},
    )


@login_required
def b2bcompanyaccount_punchout_test(request, pk):
    account = ecommerce_object(request, B2bCompanyAccount, pk)

    test_payload = {
        "protocol": account.punchout_protocol,
        "buyer_identity": account.punchout_identity or "BUYER-DEMO-IDENTITY",
        "supplier_domain": "NetworkId",
        "supplier_identity": str(account.tenant.pk),
        "shared_secret_configured": bool(account.punchout_shared_secret),
        "return_url": account.punchout_return_url or "https://procurement.buyer.com/cxml/return",
        "currency": account.preferred_currency.code if account.preferred_currency else "USD",
        "company": account.company_name,
        "punchout_enabled": account.punchout_enabled,
    }

    cxml_response = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE cXML SYSTEM "http://xml.cxml.org/schemas/cXML/1.2.014/cXML.dtd">
<cXML payloadID="{account.number}-SIM@naverb.com" timestamp="2026-11-02T12:00:00Z">
  <Response>
    <Status code="200" text="OK"/>
    <PunchOutSetupResponse>
      <StartPage>
        <URL>https://naverb.local/ecommerce/b2b/punchout/session/{account.number}/</URL>
      </StartPage>
    </PunchOutSetupResponse>
  </Response>
</cXML>"""

    context = {
        "company_account": account,
        "test_payload": test_payload,
        "cxml_response": cxml_response,
    }
    return render(request, "ecommerce/b2b_wholesale/b2b_company_account/punchout_test.html", context)
