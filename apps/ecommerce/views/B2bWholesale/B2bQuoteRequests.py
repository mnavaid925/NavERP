from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.ecommerce.forms.B2bWholesale.B2bQuoteRequests import B2bQuoteRequestForm
from apps.ecommerce.models.B2bWholesale.B2bCompanyAccounts import B2bCompanyAccount
from apps.ecommerce.models.B2bWholesale.B2bQuoteRequests import B2bQuoteRequest
from apps.ecommerce.models.OrderManagement.EcommerceOrders import EcommerceOrder, EcommerceOrderLine
from apps.ecommerce.models.ProductCatalog.CatalogProducts import CatalogProduct
from apps.ecommerce.views._common import ecommerce_object, ecommerce_scope


@login_required
def b2bquoterequest_list(request):
    qs = ecommerce_scope(
        B2bQuoteRequest.objects.select_related("company", "requested_by", "currency", "converted_order"),
        request,
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(company__company_name__icontains=q)
            | Q(requested_by__username__icontains=q)
            | Q(buyer_notes__icontains=q)
        )

    selected_status = request.GET.get("status", "").strip()
    if selected_status:
        qs = qs.filter(status=selected_status)

    selected_company = request.GET.get("company", "").strip()
    if selected_company:
        qs = qs.filter(company_id=selected_company)

    stats = ecommerce_scope(B2bQuoteRequest.objects.all(), request).aggregate(
        total=Count("id"),
        pending=Count("id", filter=Q(status__in=["submitted", "under_review", "buyer_review"])),
        quoted_val=Sum("quoted_total", filter=Q(status__in=["quoted", "accepted", "converted_to_order"])),
    )
    total_count = stats["total"] or 0
    pending_count = stats["pending"] or 0
    total_quoted_pipeline = stats["quoted_val"] or Decimal("0.00")

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    companies = ecommerce_scope(B2bCompanyAccount.objects.order_by("company_name"), request)

    context = {
        "quote_requests": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "total_count": total_count,
        "pending_count": pending_count,
        "total_quoted_pipeline": total_quoted_pipeline,
        "status_choices": B2bQuoteRequest.STATUS_CHOICES,
        "companies": companies,
        "search_query": q,
        "selected_status": selected_status,
        "selected_company": selected_company,
    }
    return render(request, "ecommerce/b2b_wholesale/b2b_quote_request/list.html", context)


@login_required
def b2bquoterequest_detail(request, pk):
    quote = ecommerce_object(
        request,
        B2bQuoteRequest,
        pk,
        select_related=("company", "requested_by", "assigned_sales_rep", "currency", "converted_order"),
    )

    context = {
        "quote_request": quote,
        "line_items": quote.line_items_data or [],
    }
    return render(request, "ecommerce/b2b_wholesale/b2b_quote_request/detail.html", context)


@login_required
def b2bquoterequest_create(request):
    initial = {}
    company_id = request.GET.get("company")
    if company_id:
        initial["company"] = company_id
    initial["requested_by"] = request.user.pk

    products = ecommerce_scope(CatalogProduct.objects.filter(is_active=True).order_by("name"), request)[:30]

    if request.method == "POST":
        form = B2bQuoteRequestForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            quote = form.save(commit=False)
            quote.tenant = request.tenant
            if not quote.requested_by:
                quote.requested_by = request.user

            # Parse line items submitted from form
            product_ids = request.POST.getlist("item_product_id[]")
            qtys = request.POST.getlist("item_qty[]")
            unit_prices = request.POST.getlist("item_unit_price[]")
            notes = request.POST.getlist("item_notes[]")

            line_items = []
            subtotal = Decimal("0.00")
            for idx, pid in enumerate(product_ids):
                if pid:
                    prod = CatalogProduct.objects.filter(tenant=request.tenant, pk=pid).first()
                    if prod:
                        try:
                            q_val = int(qtys[idx]) if idx < len(qtys) else 1
                        except (ValueError, IndexError):
                            q_val = 1
                        try:
                            p_val = Decimal(str(unit_prices[idx])) if idx < len(unit_prices) and unit_prices[idx] else prod.retail_price
                        except (ValueError, IndexError):
                            p_val = prod.retail_price

                        n_val = notes[idx] if idx < len(notes) else ""
                        line_tot = (Decimal(str(q_val)) * p_val).quantize(Decimal("0.01"))
                        subtotal += line_tot
                        line_items.append({
                            "product_id": prod.pk,
                            "sku": prod.sku,
                            "name": prod.name,
                            "requested_qty": q_val,
                            "requested_unit_price": float(p_val),
                            "quoted_unit_price": float(p_val),
                            "line_total": float(line_tot),
                            "notes": n_val,
                        })

            quote.line_items_data = line_items
            quote.original_subtotal = subtotal
            quote.recalculate_totals()
            quote.save()

            write_audit_log(
                request,
                "create",
                f"Created B2B Quote Request {quote.number} for {quote.company.company_name}",
                object_id=quote.pk,
            )
            messages.success(request, f"B2B Quote Request {quote.number} created successfully.")
            return redirect("ecommerce:b2bquoterequest_detail", pk=quote.pk)
    else:
        form = B2bQuoteRequestForm(initial=initial, tenant=request.tenant)

    context = {
        "form": form,
        "title": "Create B2B Quote Request (RFQ)",
        "products": products,
    }
    return render(request, "ecommerce/b2b_wholesale/b2b_quote_request/form.html", context)


@login_required
def b2bquoterequest_edit(request, pk):
    quote = ecommerce_object(request, B2bQuoteRequest, pk)
    products = ecommerce_scope(CatalogProduct.objects.filter(is_active=True).order_by("name"), request)[:30]

    if request.method == "POST":
        form = B2bQuoteRequestForm(request.POST, instance=quote, tenant=request.tenant)
        if form.is_valid():
            quote = form.save(commit=False)

            # Update line items if provided
            product_ids = request.POST.getlist("item_product_id[]")
            if product_ids:
                qtys = request.POST.getlist("item_qty[]")
                unit_prices = request.POST.getlist("item_unit_price[]")
                notes = request.POST.getlist("item_notes[]")

                line_items = []
                subtotal = Decimal("0.00")
                for idx, pid in enumerate(product_ids):
                    if pid:
                        prod = CatalogProduct.objects.filter(tenant=request.tenant, pk=pid).first()
                        if prod:
                            try:
                                q_val = int(qtys[idx]) if idx < len(qtys) else 1
                            except (ValueError, IndexError):
                                q_val = 1
                            try:
                                p_val = Decimal(str(unit_prices[idx])) if idx < len(unit_prices) and unit_prices[idx] else prod.retail_price
                            except (ValueError, IndexError):
                                p_val = prod.retail_price

                            n_val = notes[idx] if idx < len(notes) else ""
                            line_tot = (Decimal(str(q_val)) * p_val).quantize(Decimal("0.01"))
                            subtotal += line_tot
                            line_items.append({
                                "product_id": prod.pk,
                                "sku": prod.sku,
                                "name": prod.name,
                                "requested_qty": q_val,
                                "requested_unit_price": float(p_val),
                                "quoted_unit_price": float(p_val),
                                "line_total": float(line_tot),
                                "notes": n_val,
                            })
                quote.line_items_data = line_items

            quote.recalculate_totals()
            quote.save()

            write_audit_log(
                request,
                "update",
                f"Updated B2B Quote Request {quote.number}",
                object_id=quote.pk,
            )
            messages.success(request, f"Quote Request {quote.number} updated successfully.")
            return redirect("ecommerce:b2bquoterequest_detail", pk=quote.pk)
    else:
        form = B2bQuoteRequestForm(instance=quote, tenant=request.tenant)

    context = {
        "form": form,
        "quote_request": quote,
        "title": f"Edit Quote Request: {quote.number}",
        "products": products,
    }
    return render(request, "ecommerce/b2b_wholesale/b2b_quote_request/form.html", context)


@login_required
@tenant_admin_required
def b2bquoterequest_delete(request, pk):
    quote = ecommerce_object(request, B2bQuoteRequest, pk)
    if request.method == "POST":
        num = quote.number
        co_name = quote.company.company_name
        quote.delete()
        write_audit_log(
            request,
            "delete",
            f"Deleted Quote Request {num} for {co_name}",
            object_id=pk,
        )
        messages.success(request, f"Quote Request {num} has been deleted.")
        return redirect("ecommerce:b2bquoterequest_list")

    return render(
        request,
        "ecommerce/b2b_wholesale/b2b_quote_request/detail.html",
        {"quote_request": quote, "show_delete_confirm": True, "line_items": quote.line_items_data or []},
    )


@login_required
@require_POST
def b2bquoterequest_submit(request, pk):
    quote = ecommerce_object(request, B2bQuoteRequest, pk)
    if quote.status in ["draft", "rejected"]:
        quote.status = "submitted"
        quote.submitted_at = timezone.now()
        quote.save(update_fields=["status", "submitted_at", "updated_at"])
        write_audit_log(request, "update", f"Submitted RFQ {quote.number}", object_id=quote.pk)
        messages.success(request, f"Quote Request {quote.number} has been submitted for review.")
    return redirect("ecommerce:b2bquoterequest_detail", pk=quote.pk)


@login_required
@tenant_admin_required
@require_POST
def b2bquoterequest_quote(request, pk):
    quote = ecommerce_object(request, B2bQuoteRequest, pk)
    discount = request.POST.get("quoted_discount_percent")
    if discount:
        try:
            quote.quoted_discount_percent = Decimal(str(discount))
        except (ValueError, TypeError):
            pass

    quote.recalculate_totals()
    quote.status = "quoted"
    quote.quoted_at = timezone.now()
    if not quote.assigned_sales_rep:
        quote.assigned_sales_rep = request.user

    quote.save(update_fields=["status", "quoted_at", "quoted_discount_percent", "original_subtotal", "quoted_total", "assigned_sales_rep", "updated_at"])
    write_audit_log(request, "update", f"Quoted offer dispatched for {quote.number} (${quote.quoted_total})", object_id=quote.pk)
    messages.success(request, f"Quote offer dispatched for {quote.number} at ${quote.quoted_total:.2f}.")
    return redirect("ecommerce:b2bquoterequest_detail", pk=quote.pk)


@login_required
@require_POST
def b2bquoterequest_accept(request, pk):
    quote = ecommerce_object(request, B2bQuoteRequest, pk)
    quote.status = "accepted"
    quote.accepted_at = timezone.now()
    quote.save(update_fields=["status", "accepted_at", "updated_at"])
    write_audit_log(request, "update", f"Accepted Quote {quote.number}", object_id=quote.pk)
    messages.success(request, f"Quote {quote.number} accepted by buyer. Ready for order conversion.")
    return redirect("ecommerce:b2bquoterequest_detail", pk=quote.pk)


@login_required
@require_POST
def b2bquoterequest_reject(request, pk):
    quote = ecommerce_object(request, B2bQuoteRequest, pk)
    reason = request.POST.get("rejection_reason", "").strip()
    quote.status = "rejected"
    if reason:
        quote.rejection_reason = reason
    quote.save(update_fields=["status", "rejection_reason", "updated_at"])
    write_audit_log(request, "update", f"Declined Quote {quote.number}: {reason}", object_id=quote.pk)
    messages.warning(request, f"Quote {quote.number} marked as rejected.")
    return redirect("ecommerce:b2bquoterequest_detail", pk=quote.pk)


@login_required
@tenant_admin_required
@require_POST
def b2bquoterequest_convert_order(request, pk):
    quote = ecommerce_object(request, B2bQuoteRequest, pk, select_related=("company", "currency"))

    if quote.converted_order:
        messages.info(request, f"This quote was already converted to Order {quote.converted_order.number}.")
        return redirect("ecommerce:order_detail", pk=quote.converted_order.pk)

    with transaction.atomic():
        # Create authoritative EcommerceOrder
        order = EcommerceOrder.objects.create(
            tenant=request.tenant,
            customer=quote.company.company_party,
            currency=quote.currency,
            status="processing",
            payment_status="authorized" if quote.company.has_available_credit(quote.quoted_total) else "pending",
            subtotal=quote.original_subtotal,
            discount_amount=(quote.original_subtotal - (quote.quoted_total - quote.tax_amount - quote.shipping_estimate)),
            tax_amount=quote.tax_amount,
            shipping_amount=quote.shipping_estimate,
            total_amount=quote.quoted_total,
            guest_email=quote.requested_by.email if quote.requested_by else "",
        )

        # Create order items
        for item in quote.line_items_data:
            pid = item.get("product_id")
            prod = CatalogProduct.objects.filter(tenant=request.tenant, pk=pid).first() if pid else None
            if not prod:
                prod = CatalogProduct.objects.filter(tenant=request.tenant).first()
            if prod:
                EcommerceOrderLine.objects.create(
                    tenant=request.tenant,
                    order=order,
                    product=prod,
                    sku=item.get("sku") or prod.sku,
                    product_name=item.get("name") or prod.name,
                    quantity=item.get("requested_qty", 1),
                    unit_price=Decimal(str(item.get("quoted_unit_price") or item.get("requested_unit_price") or 0)),
                    line_total=Decimal(str(item.get("line_total", 0))),
                )

        # Deduct credit if applicable
        if quote.company.available_credit >= quote.quoted_total:
            quote.company.available_credit -= quote.quoted_total
            quote.company.save(update_fields=["available_credit", "updated_at"])

        quote.converted_order = order
        quote.status = "converted_to_order"
        quote.save(update_fields=["converted_order", "status", "updated_at"])

    write_audit_log(
        request,
        "convert",
        f"Converted Quote {quote.number} into EcommerceOrder {order.number}",
        object_id=quote.pk,
    )
    messages.success(request, f"Quote {quote.number} converted into Order {order.number} successfully!")
    return redirect("ecommerce:order_detail", pk=order.pk)
