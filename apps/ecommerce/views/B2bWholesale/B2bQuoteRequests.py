from decimal import Decimal, InvalidOperation
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
from apps.ecommerce.models.ProductCatalog.ProductVariants import ProductVariant
from apps.ecommerce.views._common import ecommerce_object, ecommerce_scope


def _prepare_product_choices(request, limit=30):
    products = list(
        ecommerce_scope(
            CatalogProduct.objects.filter(status="active").prefetch_related("variants").order_by("name"),
            request,
        )[:limit]
    )
    for p in products:
        var = p.variants.first()
        p.display_sku = var.sku if var else p.number
        p.display_price = var.price if (var and var.price) else Decimal("0.00")
    return products


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
    if selected_company and selected_company.isdigit():
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

    products = _prepare_product_choices(request, 30)

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

            valid_pids = [int(p) for p in product_ids if p and str(p).isdigit()]
            products_map = {
                p.pk: p for p in CatalogProduct.objects.filter(tenant=request.tenant, pk__in=valid_pids).prefetch_related("variants")
            }

            line_items = []
            subtotal = Decimal("0.00")
            for idx, pid in enumerate(product_ids):
                if pid and str(pid).isdigit():
                    prod = products_map.get(int(pid))
                    if prod:
                        variants_list = prod.variants.all()
                        var = variants_list[0] if variants_list else None
                        prod_sku = var.sku if var else prod.number
                        default_price = var.price if (var and var.price) else Decimal("0.00")
                        try:
                            q_val = int(qtys[idx]) if idx < len(qtys) else 1
                            if q_val < 1:
                                q_val = 1
                        except (ValueError, IndexError):
                            q_val = 1
                        try:
                            if idx < len(unit_prices) and unit_prices[idx]:
                                p_val = Decimal(str(unit_prices[idx]))
                                if not p_val.is_finite() or p_val < Decimal("0.00"):
                                    p_val = default_price
                            else:
                                p_val = default_price
                        except (ValueError, IndexError, InvalidOperation, TypeError):
                            p_val = default_price

                        n_val = notes[idx] if idx < len(notes) else ""
                        line_tot = (Decimal(str(q_val)) * p_val).quantize(Decimal("0.01"))
                        subtotal += line_tot
                        line_items.append({
                            "product_id": prod.pk,
                            "sku": prod_sku,
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
                request.user,
                quote,
                "create",
                {"number": quote.number, "company": quote.company.company_name},
                tenant=request.tenant,
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
    products = _prepare_product_choices(request, 30)

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

                valid_pids = [int(p) for p in product_ids if p and str(p).isdigit()]
                products_map = {
                    p.pk: p for p in CatalogProduct.objects.filter(tenant=request.tenant, pk__in=valid_pids).prefetch_related("variants")
                }

                line_items = []
                subtotal = Decimal("0.00")
                for idx, pid in enumerate(product_ids):
                    if pid and str(pid).isdigit():
                        prod = products_map.get(int(pid))
                        if prod:
                            variants_list = prod.variants.all()
                            var = variants_list[0] if variants_list else None
                            prod_sku = var.sku if var else prod.number
                            default_price = var.price if (var and var.price) else Decimal("0.00")
                            try:
                                q_val = int(qtys[idx]) if idx < len(qtys) else 1
                                if q_val < 1:
                                    q_val = 1
                            except (ValueError, IndexError):
                                q_val = 1
                            try:
                                if idx < len(unit_prices) and unit_prices[idx]:
                                    p_val = Decimal(str(unit_prices[idx]))
                                    if not p_val.is_finite() or p_val < Decimal("0.00"):
                                        p_val = default_price
                                else:
                                    p_val = default_price
                            except (ValueError, IndexError, InvalidOperation, TypeError):
                                p_val = default_price

                            n_val = notes[idx] if idx < len(notes) else ""
                            line_tot = (Decimal(str(q_val)) * p_val).quantize(Decimal("0.01"))
                            subtotal += line_tot
                            line_items.append({
                                "product_id": prod.pk,
                                "sku": prod_sku,
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
                request.user,
                quote,
                "update",
                {"number": quote.number, "company": quote.company.company_name},
                tenant=request.tenant,
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
            request.user,
            quote,
            "delete",
            {"number": num, "company": co_name},
            tenant=request.tenant,
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
        write_audit_log(request.user, quote, "submit", {"number": quote.number, "status": quote.status}, tenant=request.tenant)
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
            d_dec = Decimal(str(discount))
            if d_dec.is_finite() and Decimal("0.00") <= d_dec <= Decimal("100.00"):
                quote.quoted_discount_percent = d_dec
            elif d_dec.is_finite() and d_dec > Decimal("100.00"):
                quote.quoted_discount_percent = Decimal("100.00")
            elif d_dec.is_finite() and d_dec < Decimal("0.00"):
                quote.quoted_discount_percent = Decimal("0.00")
        except (ValueError, TypeError, InvalidOperation):
            pass

    quote.recalculate_totals()
    quote.status = "quoted"
    quote.quoted_at = timezone.now()
    if not quote.assigned_sales_rep:
        quote.assigned_sales_rep = request.user

    quote.save(update_fields=["status", "quoted_at", "quoted_discount_percent", "original_subtotal", "quoted_total", "assigned_sales_rep", "updated_at"])
    write_audit_log(request.user, quote, "quote", {"number": quote.number, "quoted_total": str(quote.quoted_total)}, tenant=request.tenant)
    messages.success(request, f"Quote offer dispatched for {quote.number} at ${quote.quoted_total:.2f}.")
    return redirect("ecommerce:b2bquoterequest_detail", pk=quote.pk)


@login_required
@require_POST
def b2bquoterequest_accept(request, pk):
    quote = ecommerce_object(request, B2bQuoteRequest, pk)
    quote.status = "accepted"
    quote.accepted_at = timezone.now()
    quote.save(update_fields=["status", "accepted_at", "updated_at"])
    write_audit_log(request.user, quote, "accept", {"number": quote.number, "status": quote.status}, tenant=request.tenant)
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
    write_audit_log(request.user, quote, "reject", {"number": quote.number, "reason": reason}, tenant=request.tenant)
    messages.warning(request, f"Quote {quote.number} marked as rejected.")
    return redirect("ecommerce:b2bquoterequest_detail", pk=quote.pk)


@login_required
@tenant_admin_required
@require_POST
def b2bquoterequest_convert_order(request, pk):
    quote = ecommerce_object(request, B2bQuoteRequest, pk, select_related=("company", "currency"))

    if quote.converted_order:
        messages.info(request, f"This quote was already converted to Order {quote.converted_order.number}.")
        return redirect("ecommerce:ecommerceorder_detail", pk=quote.converted_order.pk)

    party = quote.company.company_party
    party_addr = party.addresses.filter(kind="shipping").first() or party.addresses.first() if party else None
    shipping_name = (
        (quote.requested_by.get_full_name() if quote.requested_by else "")
        or quote.company.company_name
    )[:150]
    shipping_line1 = (party_addr.line1 if party_addr and party_addr.line1 else "100 Commercial Way")[:255]
    shipping_city = (party_addr.city if party_addr and party_addr.city else "Enterprise City")[:100]
    shipping_postal_code = "10001"
    shipping_country = (party_addr.country if party_addr and party_addr.country else "USA")[:100]

    with transaction.atomic():
        # Create authoritative EcommerceOrder
        order = EcommerceOrder.objects.create(
            tenant=request.tenant,
            customer=quote.company.company_party,
            currency=quote.currency,
            status="processing",
            payment_status="authorized" if quote.company.has_available_credit(quote.quoted_total) else "pending",
            subtotal_amount=quote.original_subtotal,
            discount_amount=(quote.original_subtotal - (quote.quoted_total - quote.tax_amount - quote.shipping_estimate)),
            tax_amount=quote.tax_amount,
            shipping_amount=quote.shipping_estimate,
            total_amount=quote.quoted_total,
            guest_email=quote.requested_by.email if quote.requested_by else "",
            shipping_name=shipping_name,
            shipping_address_line1=shipping_line1,
            shipping_city=shipping_city,
            shipping_postal_code=shipping_postal_code,
            shipping_country=shipping_country,
            shipping_address=party_addr,
        )

        # Batch fetch products for line items
        pids = [int(item.get("product_id")) for item in quote.line_items_data if item.get("product_id") and str(item.get("product_id")).isdigit()]
        products_map = {
            p.pk: p for p in CatalogProduct.objects.filter(tenant=request.tenant, pk__in=pids).prefetch_related("variants")
        }
        fallback_prod = None

        # Create order items
        for item in quote.line_items_data:
            pid = item.get("product_id")
            prod = products_map.get(int(pid)) if pid and str(pid).isdigit() else None
            if not prod:
                if fallback_prod is None:
                    fallback_prod = CatalogProduct.objects.filter(tenant=request.tenant).prefetch_related("variants").first()
                prod = fallback_prod
            if prod:
                variants_list = prod.variants.all()
                var = variants_list[0] if variants_list else None
                item_sku = item.get("sku") or (var.sku if var else prod.number)
                EcommerceOrderLine.objects.create(
                    tenant=request.tenant,
                    order=order,
                    product=prod,
                    sku=item_sku,
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
        request.user,
        quote,
        "convert",
        {"number": quote.number, "order_number": order.number},
        tenant=request.tenant,
    )
    messages.success(request, f"Quote {quote.number} converted into Order {order.number} successfully!")
    return redirect("ecommerce:ecommerceorder_detail", pk=order.pk)
