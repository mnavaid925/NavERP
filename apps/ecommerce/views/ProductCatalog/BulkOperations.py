import csv
from decimal import Decimal
import io

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils.text import slugify

from apps.core.utils import write_audit_log
from apps.ecommerce.forms.ProductCatalog.BulkOperations import ProductImportForm
from apps.ecommerce.models.ProductCatalog.CatalogProducts import CatalogProduct
from apps.ecommerce.models.ProductCatalog.ProductVariants import ProductVariant
from apps.ecommerce.models.ProductCatalog.StoreCategories import StoreCategory
from apps.ecommerce.views._common import csv_export_response, ecommerce_scope


@login_required
def product_export_csv(request):
    products = (
        ecommerce_scope(CatalogProduct.objects.all(), request)
        .select_related("primary_category")
        .prefetch_related("variants")
        .order_by("name")
    )

    headers = [
        "Product_Number",
        "Product_Name",
        "Slug",
        "Brand",
        "Category",
        "Status",
        "Visibility",
        "SKU",
        "Variant_Name",
        "Price",
        "Compare_At_Price",
        "Cost_Price",
        "Barcode",
        "Weight_KG",
    ]

    rows = []
    for prod in products:
        variants = list(prod.variants.all())
        cat_name = prod.primary_category.name if prod.primary_category else ""
        if variants:
            for v in variants:
                rows.append(
                    [
                        prod.number,
                        prod.name,
                        prod.slug,
                        prod.brand,
                        cat_name,
                        prod.status,
                        prod.visibility,
                        v.sku,
                        v.name,
                        f"{v.price:.2f}",
                        f"{v.compare_at_price:.2f}" if v.compare_at_price else "",
                        f"{v.cost_price:.2f}",
                        v.barcode,
                        f"{v.weight_kg:.3f}",
                    ]
                )
        else:
            rows.append(
                [
                    prod.number,
                    prod.name,
                    prod.slug,
                    prod.brand,
                    cat_name,
                    prod.status,
                    prod.visibility,
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                ]
            )

    filename = f"catalog_export_{request.tenant.pk}.csv"
    return csv_export_response(request, filename=filename, headers=headers, rows=rows)


@login_required
def product_import_csv(request):
    import_results = None
    errors = []

    if request.method == "POST":
        form = ProductImportForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = request.FILES["csv_file"]
            dry_run = form.cleaned_data.get("dry_run", False)
            auto_create_categories = form.cleaned_data.get("auto_create_categories", True)

            try:
                decoded_file = csv_file.read().decode("utf-8-sig")
                io_string = io.StringIO(decoded_file)
                reader = csv.DictReader(io_string)

                created_products = 0
                updated_products = 0
                created_variants = 0
                row_num = 1

                with transaction.atomic():
                    for row in reader:
                        row_num += 1
                        prod_name = (row.get("Product_Name") or row.get("name") or "").strip()
                        sku = (row.get("SKU") or row.get("sku") or "").strip()
                        if not prod_name:
                            errors.append(f"Row {row_num}: Missing required 'Product_Name'.")
                            continue

                        slug = (row.get("Slug") or row.get("slug") or "").strip()
                        if not slug:
                            slug = slugify(prod_name)

                        brand = (row.get("Brand") or row.get("brand") or "").strip()
                        cat_name = (row.get("Category") or row.get("category") or "").strip()
                        status = (row.get("Status") or row.get("status") or "draft").strip().lower()
                        if status not in ("draft", "active", "archived"):
                            status = "draft"

                        visibility = (row.get("Visibility") or row.get("visibility") or "storefront").strip().lower()
                        if visibility not in ("storefront", "hidden", "search_only"):
                            visibility = "storefront"

                        category = None
                        if cat_name:
                            category = StoreCategory.objects.filter(
                                tenant=request.tenant, name__iexact=cat_name
                            ).first()
                            if not category and auto_create_categories and not dry_run:
                                category = StoreCategory.objects.create(
                                    tenant=request.tenant,
                                    name=cat_name,
                                    slug=slugify(cat_name),
                                )

                        if not dry_run:
                            product, p_created = CatalogProduct.objects.get_or_create(
                                tenant=request.tenant,
                                slug=slug,
                                defaults={
                                    "name": prod_name,
                                    "brand": brand,
                                    "primary_category": category,
                                    "status": status,
                                    "visibility": visibility,
                                },
                            )
                            if p_created:
                                created_products += 1
                            else:
                                updated_products += 1

                            if sku:
                                var_name = (row.get("Variant_Name") or row.get("variant_name") or prod_name).strip()
                                price_val = Decimal(str(row.get("Price") or 0).replace("$", "").strip() or 0)
                                compare_val = None
                                if row.get("Compare_At_Price"):
                                    try:
                                        compare_val = Decimal(str(row.get("Compare_At_Price")).replace("$", "").strip())
                                    except Exception:
                                        compare_val = None

                                cost_val = Decimal(str(row.get("Cost_Price") or 0).replace("$", "").strip() or 0)
                                barcode = (row.get("Barcode") or "").strip()

                                variant, v_created = ProductVariant.objects.get_or_create(
                                    tenant=request.tenant,
                                    sku=sku,
                                    defaults={
                                        "product": product,
                                        "name": var_name,
                                        "price": price_val,
                                        "compare_at_price": compare_val,
                                        "cost_price": cost_val,
                                        "barcode": barcode,
                                    },
                                )
                                if v_created:
                                    created_variants += 1
                        else:
                            # Dry run count
                            created_products += 1

                    if dry_run:
                        # Transaction rollback for dry run
                        transaction.set_rollback(True)

                import_results = {
                    "dry_run": dry_run,
                    "rows_processed": row_num - 1,
                    "created_products": created_products,
                    "updated_products": updated_products,
                    "created_variants": created_variants,
                    "errors_count": len(errors),
                }

                if not dry_run and not errors:
                    write_audit_log(
                        request.user,
                        None,
                        "create",
                        {"message": f"Imported {created_products} products and {created_variants} variants from CSV"},
                        tenant=request.tenant,
                    )
                    messages.success(
                        request,
                        f"CSV Import complete: {created_products} products created, {created_variants} variants added.",
                    )
            except Exception as exc:
                errors.append(f"File reading error: {str(exc)}")
    else:
        form = ProductImportForm()

    context = {
        "form": form,
        "import_results": import_results,
        "errors": errors,
    }
    return render(request, "ecommerce/productcatalog/bulk_import.html", context)
