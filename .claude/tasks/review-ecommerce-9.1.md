# Review Findings — Sub-module 9.1: Product Catalog Management (Module 9 eCommerce, `ecommerce`)

- **Changeset under review:** `862cd01946276c3da699da5c244955a20f65ed12...HEAD`
- **Date:** 2026-10-28
- **Phase:** Phase 4 Review (6 serial reviewers completed: code-reviewer, explorer, frontend-reviewer, performance-reviewer, qa-smoke-tester, security-reviewer)

---

## Executive Summary

- **Critical:** 0
- **Important:** 14
- **Minor:** 12
- **Total Unique Findings:** 26

---

## Critical
*None.*

---

## Important

- [ ] **I1**: `apps/ecommerce/views/ProductCatalog/CatalogProducts.py:45` & `apps/ecommerce/views/ProductCatalog/ProductVariants.py:36` — Unvalidated integer filter query params: `category` and `product` passed directly without `.isdigit()` check causing 500 `ValueError` on non-numeric or injection payloads (Lesson L11). Guard both with `if category_filter and category_filter.isdigit():` and `if product_filter and product_filter.isdigit():`.
- [ ] **I2**: `apps/ecommerce/views/ProductCatalog/BulkOperations.py:150-197` — CSV import Decimal parsing and dry-run validation bypass: Move `Price` and `Cost_Price` parsing and validation outside `if not dry_run:` block so dry-run actually catches validation errors; wrap Decimal conversions with `try/except (InvalidOperation, TypeError, ValueError)` checking `.is_finite()` and `>= 0`.
- [ ] **I3**: `apps/ecommerce/forms/ProductCatalog/CatalogProducts.py:64` — Multi-tenant M2M validation omission: include `"categories"` in `reject_foreign(self, cleaned_data, ["primary_category", "item", "categories"])` to prevent cross-tenant category association.
- [ ] **I4**: `apps/ecommerce/forms/ProductCatalog/BulkOperations.py:5-9` — CSV file upload validation: In `ProductImportForm`, add `clean_csv_file()` validating `.endswith('.csv')` and file size limit (`5 * 1024 * 1024` bytes / 5MB).
- [ ] **I5**: `templates/ecommerce/productcatalog/catalogproduct/list.html:33-75` — Filter UI dropdowns omitted for `visibility` and `brand`: The view passes `visibility_choices`, `brands_list`, `visibility_filter`, and `brand_filter` in context, but the `<form>` omits `<select name="visibility">` and `<select name="brand">` elements. Add dropdowns to the filter form.
- [ ] **I6**: `templates/ecommerce/productcatalog/catalogproduct/list.html:214,219` — Pagination links drop `visibility` and `brand` query parameters (Lesson L9). Append `&visibility={{ visibility_filter }}&brand={{ brand_filter }}`.
- [ ] **I7**: `templates/ecommerce/productcatalog/productvariant/list.html:30-62` — Filter UI dropdown omitted for `is_active`: Add `<select name="is_active">` to variant list filter bar.
- [ ] **I8**: `templates/ecommerce/productcatalog/productvariant/list.html:165,170` — Pagination links drop `is_active` query parameter (Lesson L9). Append `&is_active={{ is_active_filter }}`.
- [ ] **I9**: `apps/ecommerce/views/ProductCatalog/StoreCategories.py:52-53` & `templates/ecommerce/productcatalog/storecategory/detail.html:189` — StoreCategory detail omits `primary_category` products and template omits products table: Update view query to `CatalogProduct.objects.filter(tenant=request.tenant).filter(Q(primary_category=category) | Q(categories=category)).distinct()` and add "Products in Category" card section in `detail.html`.
- [ ] **I10**: `apps/ecommerce/models/ProductCatalog/CatalogProducts.py:106-120` — N+1 query amplification in `price_range_display` and `total_variants_count`: `self.variants.filter(is_active=True)` and `self.variants.count()` bypass prefetch cache, triggering 60 extra queries on a 20-row page. Operate in-memory on prefetched `self.variants.all()`.
- [ ] **I11**: `apps/ecommerce/views/ProductCatalog/Overview.py:36-37` — Missing `select_related` and `prefetch_related` on Overview dashboard cards. Add `.select_related("parent")` to `recent_categories` and `.select_related("primary_category").prefetch_related("variants")` to `recent_products`.
- [ ] **I12**: `apps/ecommerce/views/ProductCatalog/CatalogProducts.py:94` — Missing `select_related("item")` on `product.variants` in `catalogproduct_detail`.
- [ ] **I13**: `apps/ecommerce/views/ProductCatalog/BulkOperations.py:140-142` — Uncached category lookup in CSV Import loop triggers redundant DB query per row. Preload categories into an in-memory dictionary prior to looping.
- [ ] **I14**: `apps/ecommerce/management/commands/seed_ecommerce.py:30` — Seeder completion message omits tenant admin login instructions and superuser warning. Append tenant user instructions (`admin_acme / password`).

---

## Minor

- [ ] **M1**: `apps/ecommerce/views/ProductCatalog/BulkOperations.py:144` — In CSV import, `StoreCategory.objects.create(tenant=request.tenant, name=cat_name, slug=slugify(cat_name))` can raise `IntegrityError` if category exists. Use `StoreCategory.objects.get_or_create(tenant=request.tenant, slug=slugify(cat_name), defaults={"name": cat_name})`.
- [ ] **M2**: `apps/ecommerce/models/ProductCatalog/StoreCategories.py:61` — `get_breadcrumbs()` traverses `curr.parent` without cycle detection. Maintain `seen = set()` inside `get_breadcrumbs()` and break if `curr.pk in seen`.
- [ ] **M3**: `templates/ecommerce/productcatalog/**/` — Add explicit `aria-label` attributes to all icon-only action buttons alongside `title`.
- [ ] **M4**: `templates/ecommerce/productcatalog/bulk_import.html:82` & form templates — Replace `space-x-*` with `gap-*` for RTL safety.
- [ ] **M5**: `apps/ecommerce/views/ProductCatalog/Overview.py:20-34` — Multiple individual KPI queries against `CatalogProduct`. Combine into a single conditional `.aggregate()` query.
- [ ] **M6**: `apps/ecommerce/views/ProductCatalog/ProductRelationships.py:54-59` — Chained N+1 queries in `productrelationship_detail`. Add `source_product__primary_category` and `target_product__primary_category` to `select_related`.
- [ ] **M7**: `apps/ecommerce/views/ProductCatalog/StoreCategories.py:17` — Category hierarchy breadcrumb query depth in `storecategory_list`. Use `select_related("parent", "parent__parent")`.
- [ ] **M8**: `apps/ecommerce/models/ProductCatalog/CatalogProducts.py:69-72` — Missing compound index on `(tenant, -created_at)` for `CatalogProduct`. Add `models.Index(fields=["tenant", "-created_at"], name="ecom_prd_tnt_created_idx")`.
- [ ] **M9**: `apps/ecommerce/views/ProductCatalog/ProductVariants.py:49` & `apps/ecommerce/views/ProductCatalog/ProductRelationships.py:96,130` — Unconstrained model instantiation for dropdown filters. Add `.only("id", "name")` to product dropdown queries.
- [ ] **M10**: `apps/ecommerce/forms/ProductCatalog/ProductVariants.py:55` & `apps/ecommerce/models/ProductCatalog/ProductVariants.py:68` — `sort_order` required in `ProductVariantForm` without initial default. Set `initial=0`.
- [ ] **M11**: `apps/ecommerce/views/ProductCatalog/BulkOperations.py:211` — Bulk CSV import skips audit logging when partial row-level validation errors occur. Write audit log if `created_products > 0 or created_variants > 0`.
- [ ] **M12**: `apps/ecommerce/views/ProductCatalog/BulkOperations.py:106` — Missing `errors="replace"` fallback during CSV decode: use `csv_file.read().decode("utf-8-sig", errors="replace")`.
