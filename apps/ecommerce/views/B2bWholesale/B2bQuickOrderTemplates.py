import csv
import io
from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.ecommerce.forms.B2bWholesale.B2bQuickOrderTemplates import B2bQuickOrderTemplateForm
from apps.ecommerce.models.B2bWholesale.B2bCompanyAccounts import B2bCompanyAccount
from apps.ecommerce.models.B2bWholesale.B2bQuickOrderTemplates import B2bQuickOrderTemplate
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
def b2bquickordertemplate_list(request):
    qs = ecommerce_scope(
        B2bQuickOrderTemplate.objects.select_related("company", "created_by"),
        request,
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(name__icontains=q)
            | Q(description__icontains=q)
            | Q(company__company_name__icontains=q)
            | Q(number__icontains=q)
        )

    selected_scope = request.GET.get("scope", "").strip()
    if selected_scope:
        qs = qs.filter(scope=selected_scope)

    selected_cadence = request.GET.get("cadence", "").strip()
    if selected_cadence:
        qs = qs.filter(cadence=selected_cadence)

    selected_company = request.GET.get("company", "").strip()
    if selected_company and selected_company.isdigit():
        qs = qs.filter(company_id=selected_company)

    stats = ecommerce_scope(B2bQuickOrderTemplate.objects.all(), request).aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(is_active=True)),
    )
    total_count = stats["total"] or 0
    active_count = stats["active"] or 0

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    companies = ecommerce_scope(B2bCompanyAccount.objects.only("id", "company_name").order_by("company_name"), request)

    context = {
        "quick_order_templates": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "total_count": total_count,
        "active_count": active_count,
        "scope_choices": B2bQuickOrderTemplate.SCOPE_CHOICES,
        "cadence_choices": B2bQuickOrderTemplate.CADENCE_CHOICES,
        "companies": companies,
        "search_query": q,
        "selected_scope": selected_scope,
        "selected_cadence": selected_cadence,
        "selected_company": selected_company,
    }
    return render(request, "ecommerce/b2b_wholesale/b2b_quick_order_template/list.html", context)


@login_required
def b2bquickordertemplate_detail(request, pk):
    template_obj = ecommerce_object(
        request,
        B2bQuickOrderTemplate,
        pk,
        select_related=("company", "created_by"),
    )

    context = {
        "template_obj": template_obj,
        "items_data": template_obj.items_data or [],
    }
    return render(request, "ecommerce/b2b_wholesale/b2b_quick_order_template/detail.html", context)


@login_required
def b2bquickordertemplate_create(request):
    initial = {}
    company_id = request.GET.get("company")
    if company_id:
        initial["company"] = company_id
    initial["created_by"] = request.user.pk

    products = _prepare_product_choices(request, 30)

    if request.method == "POST":
        form = B2bQuickOrderTemplateForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            tmpl = form.save(commit=False)
            tmpl.tenant = request.tenant
            if not tmpl.created_by:
                tmpl.created_by = request.user

            # Parse line items
            product_ids = request.POST.getlist("item_product_id[]")
            qtys = request.POST.getlist("item_qty[]")
            notes = request.POST.getlist("item_notes[]")

            valid_pids = [int(p) for p in product_ids if p and str(p).isdigit()]
            products_map = {
                p.pk: p for p in CatalogProduct.objects.filter(tenant=request.tenant, pk__in=valid_pids).prefetch_related("variants")
            }

            items_data = []
            for idx, pid in enumerate(product_ids):
                if pid and str(pid).isdigit():
                    prod = products_map.get(int(pid))
                    if prod:
                        var = prod.variants.all()[0] if prod.variants.all() else None
                        prod_sku = var.sku if var else prod.number
                        default_price = var.price if (var and var.price) else Decimal("0.00")
                        try:
                            q_val = int(qtys[idx]) if idx < len(qtys) else 1
                            if q_val <= 0 or q_val > 100000:
                                q_val = 1
                        except (ValueError, TypeError, IndexError):
                            q_val = 1
                        n_val = notes[idx] if idx < len(notes) else ""
                        items_data.append({
                            "product_id": prod.pk,
                            "sku": prod_sku,
                            "name": prod.name,
                            "default_quantity": q_val,
                            "unit_price": float(default_price),
                            "uom": "EA",
                            "notes": n_val,
                        })

            tmpl.items_data = items_data
            tmpl.save()

            write_audit_log(
                request.user,
                tmpl,
                "create",
                {"number": tmpl.number, "name": tmpl.name},
                tenant=request.tenant,
            )
            messages.success(request, f"Quick Order Template {tmpl.name} created successfully.")
            return redirect("ecommerce:b2bquickordertemplate_detail", pk=tmpl.pk)
    else:
        form = B2bQuickOrderTemplateForm(initial=initial, tenant=request.tenant)

    context = {
        "form": form,
        "title": "Create Quick Order Template",
        "products": products,
    }
    return render(request, "ecommerce/b2b_wholesale/b2b_quick_order_template/form.html", context)


@login_required
def b2bquickordertemplate_edit(request, pk):
    tmpl = ecommerce_object(request, B2bQuickOrderTemplate, pk)
    products = _prepare_product_choices(request, 30)

    if request.method == "POST":
        form = B2bQuickOrderTemplateForm(request.POST, instance=tmpl, tenant=request.tenant)
        if form.is_valid():
            tmpl = form.save(commit=False)

            # Update line items if provided
            product_ids = request.POST.getlist("item_product_id[]")
            if product_ids:
                qtys = request.POST.getlist("item_qty[]")
                notes = request.POST.getlist("item_notes[]")

                valid_pids = [int(p) for p in product_ids if p and str(p).isdigit()]
                products_map = {
                    p.pk: p for p in CatalogProduct.objects.filter(tenant=request.tenant, pk__in=valid_pids).prefetch_related("variants")
                }

                items_data = []
                for idx, pid in enumerate(product_ids):
                    if pid and str(pid).isdigit():
                        prod = products_map.get(int(pid))
                        if prod:
                            var = prod.variants.all()[0] if prod.variants.all() else None
                            prod_sku = var.sku if var else prod.number
                            default_price = var.price if (var and var.price) else Decimal("0.00")
                            try:
                                q_val = int(qtys[idx]) if idx < len(qtys) else 1
                                if q_val <= 0 or q_val > 100000:
                                    q_val = 1
                            except (ValueError, TypeError, IndexError):
                                q_val = 1
                            n_val = notes[idx] if idx < len(notes) else ""
                            items_data.append({
                                "product_id": prod.pk,
                                "sku": prod_sku,
                                "name": prod.name,
                                "default_quantity": q_val,
                                "unit_price": float(default_price),
                                "uom": "EA",
                                "notes": n_val,
                            })
                tmpl.items_data = items_data

            tmpl.save()

            write_audit_log(
                request.user,
                tmpl,
                "update",
                {"number": tmpl.number, "name": tmpl.name},
                tenant=request.tenant,
            )
            messages.success(request, f"Quick Order Template {tmpl.name} updated successfully.")
            return redirect("ecommerce:b2bquickordertemplate_detail", pk=tmpl.pk)
    else:
        form = B2bQuickOrderTemplateForm(instance=tmpl, tenant=request.tenant)

    context = {
        "form": form,
        "template_obj": tmpl,
        "title": f"Edit Quick Order Template: {tmpl.name}",
        "products": products,
    }
    return render(request, "ecommerce/b2b_wholesale/b2b_quick_order_template/form.html", context)


@login_required
@tenant_admin_required
@require_POST
def b2bquickordertemplate_delete(request, pk):
    tmpl = ecommerce_object(request, B2bQuickOrderTemplate, pk)
    name = tmpl.name
    num = tmpl.number
    tmpl.delete()
    write_audit_log(
        request.user,
        tmpl,
        "delete",
        {"number": num, "name": name},
        tenant=request.tenant,
    )
    messages.success(request, f"Template {name} has been deleted.")
    return redirect("ecommerce:b2bquickordertemplate_list")


@login_required
def b2b_quick_order_matrix(request):
    """Bulk quick order entry and CSV upload parser."""
    companies = ecommerce_scope(B2bCompanyAccount.objects.filter(status="active").order_by("company_name"), request)
    products = _prepare_product_choices(request, 50)

    parsed_items = []
    csv_errors = []
    success_message = ""

    if request.method == "POST":
        csv_file = request.FILES.get("csv_file")
        if csv_file:
            try:
                decoded = csv_file.read().decode("utf-8-sig")
                reader = csv.reader(io.StringIO(decoded))
                header = next(reader, None)
                rows = list(reader)

                raw_skus = set()
                parsed_rows = []
                for row_idx, row in enumerate(rows, start=2):
                    if not row or not any(row):
                        continue
                    sku = row[0].strip() if len(row) > 0 else ""
                    try:
                        qty = int(row[1].strip()) if len(row) > 1 and row[1].strip() else 1
                        if qty <= 0 or qty > 100000:
                            qty = 1
                    except (ValueError, TypeError):
                        qty = 1
                    if sku:
                        raw_skus.add(sku)
                        parsed_rows.append((row_idx, sku, qty))

                # Batch fetch variants and products by sku/number
                variants_map = {
                    v.sku.lower(): v
                    for v in ProductVariant.objects.filter(tenant=request.tenant, sku__in=list(raw_skus)).select_related("product")
                }
                missing_skus = [s for s in raw_skus if s.lower() not in variants_map]
                products_map = {
                    p.number.lower(): p
                    for p in CatalogProduct.objects.filter(tenant=request.tenant, number__in=missing_skus).prefetch_related("variants")
                }

                for row_idx, sku, qty in parsed_rows:
                    sku_lower = sku.lower()
                    if sku_lower in variants_map:
                        var = variants_map[sku_lower]
                        p_price = var.price or Decimal("0.00")
                        parsed_items.append({
                            "product_id": var.product_id,
                            "sku": var.sku,
                            "name": var.name or (var.product.name if var.product else var.sku),
                            "qty": qty,
                            "price": float(p_price),
                            "line_total": float(Decimal(str(qty)) * p_price),
                            "found": True,
                        })
                    elif sku_lower in products_map:
                        prod = products_map[sku_lower]
                        variants_list = prod.variants.all()
                        first_v = variants_list[0] if variants_list else None
                        p_price = first_v.price if (first_v and first_v.price) else Decimal("0.00")
                        p_sku = first_v.sku if first_v else prod.number
                        parsed_items.append({
                            "product_id": prod.pk,
                            "sku": p_sku,
                            "name": prod.name,
                            "qty": qty,
                            "price": float(p_price),
                            "line_total": float(Decimal(str(qty)) * p_price),
                            "found": True,
                        })
                    else:
                        csv_errors.append(f"Row {row_idx}: SKU '{sku}' not found in active catalog.")
                        parsed_items.append({
                            "product_id": None,
                            "sku": sku,
                            "name": "Item not found in catalog",
                            "qty": qty,
                            "price": 0.0,
                            "line_total": 0.0,
                            "found": False,
                        })
                if parsed_items:
                    success_message = f"Parsed {len(parsed_items)} items from uploaded CSV file."
            except Exception as e:
                csv_errors.append(f"Error parsing CSV file: {str(e)}")

        elif "manual_submit" in request.POST:
            # Parse manual SKU matrix
            skus = request.POST.getlist("matrix_sku[]")
            qtys = request.POST.getlist("matrix_qty[]")
            raw_entries = []
            sku_set = set()
            for idx, s in enumerate(skus):
                sku_val = s.strip()
                if sku_val:
                    try:
                        q_val = int(qtys[idx]) if idx < len(qtys) and qtys[idx] else 1
                        if q_val <= 0 or q_val > 100000:
                            q_val = 1
                    except (ValueError, TypeError):
                        q_val = 1
                    sku_set.add(sku_val)
                    raw_entries.append((sku_val, q_val))

            variants_map = {
                v.sku.lower(): v
                for v in ProductVariant.objects.filter(tenant=request.tenant, sku__in=list(sku_set)).select_related("product")
            }
            missing_skus = [s for s in sku_set if s.lower() not in variants_map]
            products_map = {
                p.number.lower(): p
                for p in CatalogProduct.objects.filter(tenant=request.tenant, number__in=missing_skus).prefetch_related("variants")
            }

            for sku_val, q_val in raw_entries:
                sku_lower = sku_val.lower()
                if sku_lower in variants_map:
                    var = variants_map[sku_lower]
                    p_price = var.price or Decimal("0.00")
                    parsed_items.append({
                        "product_id": var.product_id,
                        "sku": var.sku,
                        "name": var.name or (var.product.name if var.product else var.sku),
                        "qty": q_val,
                        "price": float(p_price),
                        "line_total": float(Decimal(str(q_val)) * p_price),
                        "found": True,
                    })
                elif sku_lower in products_map:
                    prod = products_map[sku_lower]
                    variants_list = prod.variants.all()
                    first_v = variants_list[0] if variants_list else None
                    p_price = first_v.price if (first_v and first_v.price) else Decimal("0.00")
                    p_sku = first_v.sku if first_v else prod.number
                    parsed_items.append({
                        "product_id": prod.pk,
                        "sku": p_sku,
                        "name": prod.name,
                        "qty": q_val,
                        "price": float(p_price),
                        "line_total": float(Decimal(str(q_val)) * p_price),
                        "found": True,
                    })
                else:
                    csv_errors.append(f"SKU '{sku_val}' not found in active catalog.")
                    parsed_items.append({
                        "product_id": None,
                        "sku": sku_val,
                        "name": "Item not found in catalog",
                        "qty": q_val,
                        "price": 0.0,
                        "line_total": 0.0,
                        "found": False,
                    })

            if parsed_items:
                success_message = f"Validated {len(parsed_items)} items from Quick Order matrix."

    context = {
        "companies": companies,
        "products": products,
        "parsed_items": parsed_items,
        "csv_errors": csv_errors,
        "success_message": success_message,
    }
    return render(request, "ecommerce/b2b_wholesale/b2b_quick_order_template/quick_order_matrix.html", context)
