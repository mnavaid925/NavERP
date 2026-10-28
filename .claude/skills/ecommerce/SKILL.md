---
name: ecommerce
description: Work on the eCommerce module (Module 9 — 9.1 Product Catalog Management: store categories, catalog products, product variants, product relationships, merchandising overview, bulk CSV import/export). Use when the user asks to add/change/debug anything under apps/ecommerce or templates/ecommerce, extend the eCommerce seeder, touch eCommerce sidebar wiring (LIVE_LINKS 9.1), or invokes /ecommerce.
---

# eCommerce Module (Module 9, Sub-module 9.1 Product Catalog Management)

The eCommerce Management System handles online store merchandising, product catalog management, SKU variants, product relationships, and bulk operations. It integrates seamlessly with the NavERP core spine and physical supply chain:
- **Tenant Isolation**: Every model inherits `TenantNumbered` (`tenant`, `number`, `created_at`, `updated_at`). All queries and lookups are strictly tenant-scoped (`tenant=request.tenant`).
- **Physical Inventory Boundary**: Products and variants link to `scm.Item` via string foreign keys (`ForeignKey('scm.Item', ...)`). Module 9 does not duplicate inventory balances or stock movements; physical warehouse stock and valuation remain anchored in `apps/scm` and `apps/inventory`.
- **App Path**: `apps/ecommerce/`
- **Templates**: `templates/ecommerce/`
- **URL Prefix**: `/ecommerce/` (`app_name="ecommerce"`)
- **Mounted in**: `config/urls.py` as `path("ecommerce/", include("apps.ecommerce.urls", namespace="ecommerce"))`
- **Installed App**: `apps.ecommerce` in `config/settings.py`

---

## 1. App Layout & Package Architecture

All four layers (`models`, `forms`, `views`, `urls`) are organized as packages partitioned by sub-module:

```
apps/ecommerce/
├── models/
│   ├── _base.py                     # TenantNumbered abstract base model
│   ├── ProductCatalog/
│   │   ├── StoreCategories.py       # StoreCategory model (ECAT-)
│   │   ├── CatalogProducts.py       # CatalogProduct model (EPRD-)
│   │   ├── ProductVariants.py       # ProductVariant model (PVR-)
│   │   └── ProductRelationships.py  # ProductRelationship model (PRL-)
│   └── __init__.py                  # Surgical re-exports of all models
├── forms/
│   ├── _common.py                   # TenantModelForm, TenantUniqueMixin, reject_foreign
│   ├── ProductCatalog/
│   │   ├── StoreCategories.py       # StoreCategoryForm
│   │   ├── CatalogProducts.py       # CatalogProductForm
│   │   ├── ProductVariants.py       # ProductVariantForm
│   │   ├── ProductRelationships.py  # ProductRelationshipForm
│   │   └── BulkOperations.py        # ProductImportForm
│   └── __init__.py                  # Re-exports of all forms
├── views/
│   ├── _common.py                   # ecommerce_scope, ecommerce_object, csv_safe, write_audit_log
│   ├── ProductCatalog/
│   │   ├── Overview.py              # catalog_overview dashboard
│   │   ├── StoreCategories.py       # storecategory CRUD
│   │   ├── CatalogProducts.py       # catalogproduct CRUD + publish action
│   │   ├── ProductVariants.py       # productvariant CRUD
│   │   ├── ProductRelationships.py  # productrelationship CRUD
│   │   └── BulkOperations.py        # product_import_csv, product_export_csv
│   └── __init__.py                  # Re-exports of all views
├── urls/
│   ├── ProductCatalog/
│   │   ├── Overview.py              # overview & dashboard paths
│   │   ├── StoreCategories.py       # categories/ paths
│   │   ├── CatalogProducts.py       # products/ paths
│   │   ├── ProductVariants.py       # variants/ paths
│   │   ├── ProductRelationships.py  # relationships/ paths
│   │   └── BulkOperations.py        # import/ and export/ paths
│   └── __init__.py                  # Concatenates all urlpatterns with app_name="ecommerce"
├── admin.py                         # Django admin registrations
├── apps.py                          # EcommerceConfig
└── management/commands/
    └── seed_ecommerce.py            # Idempotent demo data seeder
```

---

## 2. Models & Entities (Sub-module 9.1)

| Model | Prefix | Key Fields | Core / External FKs | Key Methods / Properties |
|---|---|---|---|---|
| `StoreCategory` | `ECAT-` | `name`, `slug`, `parent`, `display_order`, `is_active`, `include_in_menu` | `self` (hierarchical) | `full_path`, `get_breadcrumbs()` (cycle-safe) |
| `CatalogProduct` | `EPRD-` | `name`, `slug`, `status` (draft/active/archived), `visibility` (storefront/hidden/search_only), `brand`, `pim_completeness` | `primary_category`, `categories` (M2M), `scm.Item` | `calculate_pim_completeness()`, `price_range_display`, `active_variants` |
| `ProductVariant` | `PVR-` | `sku`, `name`, `option_values` (JSON), `price`, `compare_at_price`, `cost_price`, `is_active`, `weight_kg` | `product`, `scm.Item` | `is_on_sale`, `options_summary`, `margin_pct` |
| `ProductRelationship`| `PRL-` | `relationship_type` (cross_sell, up_sell, accessory, bundle_kit, bought_together), `discount_pct`, `is_active` | `source_product`, `target_product` | Unique per `(tenant, source, target, type)` |

---

## 3. URLs & Routes

All routes live under `/ecommerce/` with namespace `ecommerce`:

| URL Pattern | View Function | URL Name | Description |
|---|---|---|---|
| `overview/` | `catalog_overview` | `catalog_overview` | Merchandising & catalog KPI dashboard |
| `""` | `catalog_overview` | `dashboard` | Alias to overview |
| `categories/` | `storecategory_list` | `storecategory_list` | Category tree list & search |
| `categories/create/` | `storecategory_create` | `storecategory_create` | Create category |
| `categories/<int:pk>/` | `storecategory_detail` | `storecategory_detail` | Category detail with subcategories & products |
| `categories/<int:pk>/edit/`| `storecategory_edit` | `storecategory_edit` | Edit category |
| `categories/<int:pk>/delete/`| `storecategory_delete` | `storecategory_delete` | Delete category (POST only, tenant admin required) |
| `products/` | `catalogproduct_list` | `catalogproduct_list` | Product catalog grid/list with filters |
| `products/create/` | `catalogproduct_create` | `catalogproduct_create` | Create catalog product |
| `products/import/` | `product_import_csv` | `product_import_csv` | Bulk CSV product/variant import |
| `products/export/` | `product_export_csv` | `product_export_csv` | Bulk CSV export |
| `products/<int:pk>/` | `catalogproduct_detail` | `catalogproduct_detail` | Product detail with variants & relationships |
| `products/<int:pk>/edit/` | `catalogproduct_edit` | `catalogproduct_edit` | Edit catalog product |
| `products/<int:pk>/delete/`| `catalogproduct_delete` | `catalogproduct_delete` | Delete product (POST only, tenant admin required) |
| `products/<int:pk>/publish/`| `catalogproduct_publish` | `catalogproduct_publish` | Quick toggle draft/active status (POST only) |
| `variants/` | `productvariant_list` | `productvariant_list` | SKU variants list & filter |
| `variants/create/` | `productvariant_create` | `productvariant_create` | Create variant (supports `?product=<id>`) |
| `variants/<int:pk>/` | `productvariant_detail` | `productvariant_detail` | Variant detail view |
| `variants/<int:pk>/edit/` | `productvariant_edit` | `productvariant_edit` | Edit variant |
| `variants/<int:pk>/delete/`| `productvariant_delete` | `productvariant_delete` | Delete variant (POST only, tenant admin required) |
| `relationships/` | `productrelationship_list` | `productrelationship_list` | Merchandising relationships list |
| `relationships/create/` | `productrelationship_create` | `productrelationship_create` | Create relationship (supports `?source=<id>`) |
| `relationships/<int:pk>/`| `productrelationship_detail`| `productrelationship_detail`| Relationship detail view |
| `relationships/<int:pk>/edit/`| `productrelationship_edit`| `productrelationship_edit`| Edit relationship |
| `relationships/<int:pk>/delete/`| `productrelationship_delete`| `productrelationship_delete`| Delete relationship (POST only, tenant admin required) |

---

## 4. Templates & Design System

Templates are stored under `templates/ecommerce/`:
- `productcatalog/overview.html` — KPI stats cards, quick action links, recent categories & products tables.
- `productcatalog/bulk_import.html` — File upload form, CSV column format guide, and dry-run preview tables.
- `productcatalog/storecategory/` — `list.html`, `detail.html` (with subcategories and products cards), `form.html`.
- `productcatalog/catalogproduct/` — `list.html` (filter bar with search, status, visibility, category, brand), `detail.html` (PIM completeness progress bar, variants table, relationship sections), `form.html`.
- `productcatalog/productvariant/` — `list.html`, `detail.html`, `form.html`.
- `productcatalog/productrelationship/` — `list.html`, `detail.html`, `form.html`.

**UI & Badge Rules:**
- Only use color-named badge classes from `static/css/theme.css`: `badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, `badge-slate`.
- Stat icon classes: `stat-icon blue`, `stat-icon green`, `stat-icon orange`, `stat-icon purple`, `stat-icon slate`.
- Never use semantic `-success`, `-danger`, or `-warning` classes (which render unstyled).

---

## 5. Seeder & Demo Data

Run the idempotent demo seeder:
```powershell
venv\Scripts\python.exe manage.py seed_ecommerce
```

The command provisions:
- 5 Hierarchical Categories: Electronics, Computing, Laptops, Accessories, Audio.
- 5 Catalog Products: Pro Ultra Laptop, Mechanical Keyboard, Wireless Mouse, Noise-Cancelling Headphones, Thunderbolt Dock.
- 11 Product Variants across multiple SKUs, sizes, colors, and option configurations with pricing and compare-at discounts.
- 6 Merchandising Relationships: Cross-sells, Up-sells, Accessories, and Frequently Bought Together bundles.
- All demo data is scoped to tenant `acme`.

---

## 6. Conventions & Gotchas

1. **Multi-Tenancy & IDOR**:
   - Every view must filter queries using `tenant=request.tenant`.
   - Single object lookups must use `ecommerce_object(Model, pk, request.tenant)` or `get_object_or_404(Model, pk=pk, tenant=request.tenant)`.
   - ModelForms must use `TenantUniqueMixin` and filter all FK querysets in `__init__` to `self.tenant`.
   - Form `clean()` methods must invoke `reject_foreign(self, cleaned_data, [...])`.
2. **Context Variable Contract**:
   - List views pass `page_obj`, `is_paginated`, filter values (`status_filter`, `visibility_filter`, etc.), and choice constants (`status_choices`, `visibility_choices`).
   - Detail views pass the singular entity name (`category`, `product`, `variant`, `relationship`) along with related collections.
3. **Integer Query Param Guarding (Lesson L11)**:
   - Always validate foreign key filter parameters before passing to ORM: `if param and param.isdigit():`.
4. **CSV Export & Import Security**:
   - CSV export sanitizes formulas (`=`, `+`, `-`, `@`) with a leading `'`.
   - CSV import strictly enforces `.csv` extension and a 5MB size limit.
5. **N+1 Avoidance**:
   - `price_range_display` and `total_variants_count` evaluate in-memory over prefetched `self.variants.all()`.
   - Detail and overview queries use `select_related` and `prefetch_related`.

---

## 7. Sidebar Navigation

Mounted in `apps/core/navigation.py`:
```python
LIVE_LINKS["9.1"] = ("ecommerce:catalog_overview", "9.1 Product Catalog", "ecommerce")
```
Appears under the eCommerce section of the primary navigation bar.
