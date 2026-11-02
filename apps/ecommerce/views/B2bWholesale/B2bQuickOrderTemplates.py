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
from apps.ecommerce.views._common import ecommerce_object, ecommerce_scope


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
    if selected_company:
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

    companies = ecommerce_scope(B2bCompanyAccount.objects.order_by("company_name"), request)

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

    products = ecommerce_scope(CatalogProduct.objects.filter(is_active=True).order_by("name"), request)[:30]

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

            items_data = []
            for idx, pid in enumerate(product_ids):
                if pid:
                    prod = CatalogProduct.objects.filter(tenant=request.tenant, pk=pid).first()
                    if prod:
                        try:
                            q_val = int(qtys[idx]) if idx < len(qtys) else 1
                        except (ValueError, IndexError):
                            q_val = 1
                        n_val = notes[idx] if idx < len(notes) else ""
                        items_data.append({
                            "product_id": prod.pk,
                            "sku": prod.sku,
                            "name": prod.name,
                            "default_quantity": q_val,
                            "unit_price": float(prod.retail_price),
                            "uom": "EA",
                            "notes": n_val,
                        })

            tmpl.items_data = items_data
            tmpl.save()

            write_audit_log(
                request,
                "create",
                f"Created Quick Order Template {tmpl.name} ({tmpl.number})",
                object_id=tmpl.pk,
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
    products = ecommerce_scope(CatalogProduct.objects.filter(is_active=True).order_by("name"), request)[:30]

    if request.method == "POST":
        form = B2bQuickOrderTemplateForm(request.POST, instance=tmpl, tenant=request.tenant)
        if form.is_valid():
            tmpl = form.save(commit=False)

            # Update line items if provided
            product_ids = request.POST.getlist("item_product_id[]")
            if product_ids:
                qtys = request.POST.getlist("item_qty[]")
                notes = request.POST.getlist("item_notes[]")

                items_data = []
                for idx, pid in enumerate(product_ids):
                    if pid:
                        prod = CatalogProduct.objects.filter(tenant=request.tenant, pk=pid).first()
                        if prod:
                            try:
                                q_val = int(qtys[idx]) if idx < len(qtys) else 1
                            except (ValueError, IndexError):
                                q_val = 1
                            n_val = notes[idx] if idx < len(notes) else ""
                            items_data.append({
                                "product_id": prod.pk,
                                "sku": prod.sku,
                                "name": prod.name,
                                "default_quantity": q_val,
                                "unit_price": float(prod.retail_price),
                                "uom": "EA",
                                "notes": n_val,
                            })
                tmpl.items_data = items_data

            tmpl.save()

            write_audit_log(
                request,
                "update",
                f"Updated Quick Order Template {tmpl.name} ({tmpl.number})",
                object_id=tmpl.pk,
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
def b2bquickordertemplate_delete(request, pk):
    tmpl = ecommerce_object(request, B2bQuickOrderTemplate, pk)
    if request.method == "POST":
        name = tmpl.name
        num = tmpl.number
        tmpl.delete()
        write_audit_log(
            request,
            "delete",
            f"Deleted Quick Order Template {name} ({num})",
            object_id=pk,
        )
        messages.success(request, f"Template {name} has been deleted.")
        return redirect("ecommerce:b2bquickordertemplate_list")

    return render(
        request,
        "ecommerce/b2b_wholesale/b2b_quick_order_template/detail.html",
        {"template_obj": tmpl, "show_delete_confirm": True, "items_data": tmpl.items_data or []},
    )


@login_required
def b2b_quick_order_matrix(request):
    """Bulk quick order entry and CSV upload parser."""
    companies = ecommerce_scope(B2bCompanyAccount.objects.filter(status="active").order_by("company_name"), request)
    products = ecommerce_scope(CatalogProduct.objects.filter(is_active=True).order_by("name"), request)[:50]

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

                for row_idx, row in enumerate(reader, start=2):
                    if not row or not any(row):
                        continue
                    sku = row[0].strip() if len(row) > 0 else ""
                    try:
                        qty = int(row[1].strip()) if len(row) > 1 and row[1].strip() else 1
                    except ValueError:
                        qty = 1

                    if sku:
                        prod = CatalogProduct.objects.filter(tenant=request.tenant, sku__iexact=sku).first()
                        if prod:
                            parsed_items.append({
                                "product_id": prod.pk,
                                "sku": prod.sku,
                                "name": prod.name,
                                "qty": qty,
                                "price": float(prod.retail_price),
                                "line_total": float(Decimal(str(qty)) * prod.retail_price),
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
            for idx, s in enumerate(skus):
                sku_val = s.strip()
                if sku_val:
                    try:
                        q_val = int(qtys[idx]) if idx < len(qtys) and qtys[idx] else 1
                    except ValueError:
                        q_val = 1
                    prod = CatalogProduct.objects.filter(tenant=request.tenant, sku__iexact=sku_val).first()
                    if prod:
                        parsed_items.append({
                            "product_id": prod.pk,
                            "sku": prod.sku,
                            "name": prod.name,
                            "qty": q_val,
                            "price": float(prod.retail_price),
                            "line_total": float(Decimal(str(q_val)) * prod.retail_price),
                            "found": True,
                        })
                    else:
                        csv_errors.append(f"SKU '{sku_val}' not found in active catalog.")

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
