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

- [x] **I1**: fixed - guarded `category` and `product` query params with `.isdigit()` check in `CatalogProducts.py` and `ProductVariants.py`.
- [x] **I2**: fixed - parsed and validated Decimal `Price`, `Cost_Price`, and `Compare_At_Price` outside `not dry_run` block with `is_finite()` and non-negative checks in `BulkOperations.py`.
- [x] **I3**: fixed - included `"categories"` in `reject_foreign` call in `CatalogProductForm.clean()`.
- [x] **I4**: fixed - added `clean_csv_file()` validating `.endswith('.csv')` and 5MB size limit in `ProductImportForm`.
- [x] **I5**: fixed - added `visibility` and `brand` `<select>` dropdowns to catalog product list filter card in `catalogproduct/list.html`.
- [x] **I6**: fixed - appended `&visibility={{ visibility_filter }}&brand={{ brand_filter }}` to pagination links in `catalogproduct/list.html`.
- [x] **I7**: fixed - added `is_active` `<select>` dropdown to variant filter bar in `productvariant/list.html`.
- [x] **I8**: fixed - appended `&is_active={{ is_active_filter }}` to pagination links in `productvariant/list.html`.
- [x] **I9**: fixed - queried both `primary_category` and `categories` in `storecategory_detail` and added "Products in Category" card section in `storecategory/detail.html`.
- [x] **I10**: fixed - operated in-memory on prefetched `self.variants.all()` for `price_range_display` and `total_variants_count` in `CatalogProducts.py`.
- [x] **I11**: fixed - added `.select_related("parent")` to `recent_categories` and `.select_related("primary_category").prefetch_related("variants")` to `recent_products` in `Overview.py`.
- [x] **I12**: fixed - added `.select_related("item")` to `variants` queryset in `catalogproduct_detail`.
- [x] **I13**: fixed - preloaded categories into an in-memory dictionary cache prior to the CSV import loop in `BulkOperations.py`.
- [x] **I14**: fixed - appended tenant user login instructions (`admin_acme / password`) and superuser notice to `seed_ecommerce.py`.

---

## Minor

- [x] **M1**: fixed - used `StoreCategory.objects.get_or_create()` with `slug` and defaults in `BulkOperations.py`.
- [x] **M2**: fixed - added cycle detection using `seen = set()` in `StoreCategory.get_breadcrumbs()`.
- [x] **M3**: fixed - added explicit `aria-label` attributes to all icon-only action buttons across all ecommerce templates.
- [x] **M4**: fixed - replaced `space-x-*` with `gap-*` across all form and list templates in `templates/ecommerce/productcatalog/`.
- [x] **M5**: fixed - combined product KPI counts into a single conditional `.aggregate()` query with `Q` in `Overview.py`.
- [x] **M6**: fixed - added `source_product__primary_category` and `target_product__primary_category` to `select_related` in `productrelationship_detail`.
- [x] **M7**: fixed - used `select_related("parent", "parent__parent")` for category list query in `StoreCategories.py`.
- [x] **M8**: fixed - added compound index `ecom_prd_tnt_created_idx` on `(tenant, -created_at)` to `CatalogProduct`, generated migration 0002, and migrated DB.
- [x] **M9**: fixed - added `.only("id", "name")` to product dropdown queries in `ProductVariants.py` and `ProductRelationships.py`.
- [x] **M10**: fixed - set `initial=0` for `sort_order` in `ProductVariantForm.__init__`.
- [x] **M11**: fixed - updated audit logging in `BulkOperations.py` to write audit log when `created_products > 0 or created_variants > 0` even with partial row errors.
- [x] **M12**: fixed - added `errors="replace"` fallback during CSV decode in `BulkOperations.py`.
