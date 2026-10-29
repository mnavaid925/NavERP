---
name: ecommerce
description: Work on the eCommerce module (Module 9 — 9.1 Product Catalog Management & 9.2 Inventory & Stock Management: store categories, catalog products, product variants, merchandising relationships, fulfillment centers, stock allocations, available-to-promise ATP, backorder & pre-order policies, multi-channel inventory sync). Use when the user asks to add/change/debug anything under apps/ecommerce or templates/ecommerce, extend the eCommerce seeder, touch eCommerce sidebar wiring (LIVE_LINKS 9.1 or 9.2), or invokes /ecommerce.
---

# eCommerce Module (Module 9: 9.1 Catalog & 9.2 Inventory & Stock Management)

The eCommerce Management System handles online store merchandising, product catalog management, SKU variants, product relationships, multi-node fulfillment center routing, real-time stock allocations, available-to-promise (ATP) calculation, backorder/pre-order waitlists, and multi-channel inventory synchronization feeds. It integrates seamlessly with the NavERP core spine and physical supply chain:
- **Tenant Isolation**: Every model inherits `TenantNumbered` (`tenant`, `number`, `created_at`, `updated_at`). All queries and lookups are strictly tenant-scoped (`tenant=request.tenant`).
- **Physical Inventory Boundary**: Products, variants, and fulfillment centers link to `scm.Item` and `scm.Location` via string foreign keys. Module 9 does not duplicate inventory ledger balances or physical bin movements; physical warehouse stock and valuation remain anchored in `apps/scm` and `apps/inventory`, while eCommerce manages digital storefront availability, reservations, buffers, and channel broadcasting.
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
│   ├── InventoryStock/
│   │   ├── FulfillmentCenters.py    # FulfillmentCenter model (EFC-)
│   │   ├── InventoryAllocations.py  # InventoryAllocation model (EAL-)
│   │   ├── BackorderPolicies.py     # BackorderPolicy model (EBK-)
│   │   └── ChannelInventorySyncs.py # ChannelInventorySync model (ESYN-)
│   └── __init__.py                  # Surgical re-exports of all models
├── forms/
│   ├── _common.py                   # TenantModelForm, TenantUniqueMixin, reject_foreign
│   ├── ProductCatalog/
│   │   ├── StoreCategories.py       # StoreCategoryForm
│   │   ├── CatalogProducts.py       # CatalogProductForm
│   │   ├── ProductVariants.py       # ProductVariantForm
│   │   ├── ProductRelationships.py  # ProductRelationshipForm
│   │   └── BulkOperations.py        # ProductImportForm
│   ├── InventoryStock/
│   │   ├── FulfillmentCenters.py    # FulfillmentCenterForm
│   │   ├── InventoryAllocations.py  # InventoryAllocationForm, StockAdjustmentActionForm
│   │   ├── BackorderPolicies.py     # BackorderPolicyForm
│   │   └── ChannelInventorySyncs.py # ChannelInventorySyncForm
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
│   ├── InventoryStock/
│   │   ├── Operations.py            # inventory_operations console dashboard
│   │   ├── FulfillmentCenters.py    # fulfillmentcenter CRUD
│   │   ├── InventoryAllocations.py  # inventoryallocation CRUD + stock adjust
│   │   ├── BackorderPolicies.py     # backorderpolicy CRUD
│   │   └── ChannelInventorySyncs.py # channelinventorysync CRUD + broadcast trigger
│   └── __init__.py                  # Re-exports of all views
├── urls/
│   ├── ProductCatalog/
│   │   ├── Overview.py              # overview & dashboard paths
│   │   ├── StoreCategories.py       # categories/ paths
│   │   ├── CatalogProducts.py       # products/ paths
│   │   ├── ProductVariants.py       # variants/ paths
│   │   ├── ProductRelationships.py  # relationships/ paths
│   │   └── BulkOperations.py        # import/ and export/ paths
│   ├── InventoryStock/
│   │   ├── Operations.py            # inventory/ console path
│   │   ├── FulfillmentCenters.py    # inventory/centers/ paths
│   │   ├── InventoryAllocations.py  # inventory/allocations/ paths
│   │   ├── BackorderPolicies.py     # inventory/backorders/ paths
│   │   └── ChannelInventorySyncs.py # inventory/sync/ paths
│   └── __init__.py                  # Concatenates all urlpatterns with app_name="ecommerce"
├── admin.py                         # Django admin registrations
├── apps.py                          # EcommerceConfig
└── management/commands/
    └── seed_ecommerce.py            # Idempotent demo data seeder
```

---

## 2. Models & Entities

### Sub-module 9.1: Product Catalog Management
| Model | Prefix | Key Fields | Core / External FKs | Key Methods / Properties |
|---|---|---|---|---|
| `StoreCategory` | `ECAT-` | `name`, `slug`, `parent`, `display_order`, `is_active`, `include_in_menu` | `self` (hierarchical) | `full_path`, `get_breadcrumbs()` (cycle-safe) |
| `CatalogProduct` | `EPRD-` | `name`, `slug`, `status` (draft/active/archived), `visibility` (storefront/hidden/search_only), `brand`, `pim_completeness` | `primary_category`, `categories` (M2M), `scm.Item` | `calculate_pim_completeness()`, `price_range_display`, `active_variants` |
| `ProductVariant` | `PVR-` | `sku`, `name`, `option_values` (JSON), `price`, `compare_at_price`, `cost_price`, `is_active`, `weight_kg` | `product`, `scm.Item` | `is_on_sale`, `options_summary`, `margin_pct` |
| `ProductRelationship`| `PRL-` | `relationship_type` (cross_sell, up_sell, accessory, bundle_kit, bought_together), `discount_pct`, `is_active` | `source_product`, `target_product` | Unique per `(tenant, source, target, type)` |

### Sub-module 9.2: Inventory & Stock Management
| Model | Prefix | Key Fields | Core / External FKs | Key Methods / Properties |
|---|---|---|---|---|
| `FulfillmentCenter` | `EFC-` | `name`, `code`, `center_type`, `priority`, `is_active`, `supports_pick_pack_ship`, `supports_customer_pickup`, `daily_cutoff_time`, address fields | `scm.Location` | Unique per `(tenant, code)`. Priority routing order. |
| `InventoryAllocation` | `EAL-` | `quantity_on_hand`, `quantity_allocated`, `safety_stock_buffer`, `low_stock_threshold`, `zone_bin`, `last_counted_at` | `product`, `variant`, `fulfillment_center` | `available_to_promise` (`max(0, on_hand - allocated - safety_buffer)`), `is_low_stock_alert` |
| `BackorderPolicy` | `EBK-` | `policy_type` (deny_when_empty, allow_backorder_with_notice, pre_order_only), `storefront_message`, `expected_availability_date`, `max_backorder_quantity`, `current_backorder_count`, `auto_notify_waitlist` | `variant` (OneToOne) | Unique per `(tenant, variant)` |
| `ChannelInventorySync`| `ESYN-`| `channel_type`, `channel_name`, `sync_mode`, `allocation_buffer_pct`, `last_synced_quantity`, `sync_status`, `last_synced_at` | `variant`, `fulfillment_center` (optional) | `calculate_sync_quantity()` (applies buffer percentage to ATP) |

---

## 3. URLs & Routes

All routes live under `/ecommerce/` with namespace `ecommerce`:

### 9.1 Catalog Routes
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

### 9.2 Inventory & Stock Routes
| URL Pattern | View Function | URL Name | Description |
|---|---|---|---|
| `inventory/` | `inventory_operations` | `inventory_operations` | Operations console & stock KPI overview |
| `inventory/centers/` | `fulfillmentcenter_list` | `fulfillmentcenter_list` | Centers list with type & status filters |
| `inventory/centers/create/` | `fulfillmentcenter_create` | `fulfillmentcenter_create` | Add new fulfillment center / 3PL node |
| `inventory/centers/<int:pk>/` | `fulfillmentcenter_detail` | `fulfillmentcenter_detail` | Center detail with stocked SKUs and sync feeds |
| `inventory/centers/<int:pk>/edit/` | `fulfillmentcenter_edit` | `fulfillmentcenter_edit` | Edit fulfillment center |
| `inventory/centers/<int:pk>/delete/`| `fulfillmentcenter_delete` | `fulfillmentcenter_delete` | Delete fulfillment center (POST, tenant admin) |
| `inventory/allocations/` | `inventoryallocation_list` | `inventoryallocation_list` | Stock allocation table with ATP & low stock filters |
| `inventory/allocations/create/` | `inventoryallocation_create` | `inventoryallocation_create` | Create allocation (supports `?center=` & `?variant=`) |
| `inventory/allocations/<int:pk>/` | `inventoryallocation_detail` | `inventoryallocation_detail` | Allocation detail with ATP equation & audit log |
| `inventory/allocations/<int:pk>/edit/` | `inventoryallocation_edit` | `inventoryallocation_edit` | Edit allocation parameters & safety buffers |
| `inventory/allocations/<int:pk>/adjust/` | `inventoryallocation_adjust` | `inventoryallocation_adjust` | Stock adjustment workflow (cycle count, damage, etc.) |
| `inventory/allocations/<int:pk>/delete/`| `inventoryallocation_delete` | `inventoryallocation_delete` | Delete allocation (POST, tenant admin) |
| `inventory/backorders/` | `backorderpolicy_list` | `backorderpolicy_list` | Backorder & pre-order policy list |
| `inventory/backorders/create/` | `backorderpolicy_create` | `backorderpolicy_create` | Configure backorder/pre-order policy |
| `inventory/backorders/<int:pk>/` | `backorderpolicy_detail` | `backorderpolicy_detail` | Policy detail with waitlist commitments |
| `inventory/backorders/<int:pk>/edit/` | `backorderpolicy_edit` | `backorderpolicy_edit` | Edit policy message, caps, and dates |
| `inventory/backorders/<int:pk>/delete/`| `backorderpolicy_delete` | `backorderpolicy_delete` | Delete policy (POST, tenant admin) |
| `inventory/sync/` | `channelinventorysync_list` | `channelinventorysync_list` | Multi-channel sync feeds list |
| `inventory/sync/create/` | `channelinventorysync_create` | `channelinventorysync_create` | Connect new channel inventory feed |
| `inventory/sync/<int:pk>/` | `channelinventorysync_detail` | `channelinventorysync_detail` | Feed detail with broadcast calculations & diagnostics |
| `inventory/sync/<int:pk>/edit/` | `channelinventorysync_edit` | `channelinventorysync_edit` | Edit sync mode, buffers, or status |
| `inventory/sync/<int:pk>/delete/` | `channelinventorysync_delete` | `channelinventorysync_delete` | Delete channel feed (POST, tenant admin) |
| `inventory/sync/<int:pk>/trigger/` | `channelinventorysync_trigger` | `channelinventorysync_trigger` | On-demand instant stock broadcast push (POST) |

---

## 4. Templates & Design System

Templates are stored under `templates/ecommerce/`:
- `productcatalog/` — Catalog overview, bulk import, storecategory, catalogproduct, productvariant, productrelationship templates.
- `inventorystock/`
  - `overview.html` — Operations console: ATP KPIs, low stock alerts, active fulfillment centers, connected channel syncs, and backorder queue.
  - `fulfillmentcenter/` — `list.html`, `detail.html`, `form.html`.
  - `inventoryallocation/` — `list.html` (with ATP highlights), `detail.html` (with ATP equation breakdown), `form.html`, `adjust.html` (cycle count / damage write-off workflow).
  - `backorderpolicy/` — `list.html`, `detail.html`, `form.html`.
  - `channelinventorysync/` — `list.html`, `detail.html`, `form.html`.

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
- 3 Fulfillment Centers: Main Distribution Hub (`DC-MAIN-01`), West Coast 3PL Partner (`3PL-WEST-02`), Downtown Flagship Store (`RET-FLAG-01`).
- 10 Inventory Allocations with on-hand, allocated, safety stock, and bin locations.
- 3 Backorder & Pre-Order Policies with waitlist tracking and customer storefront messages.
- 4 Multi-Channel Sync Feeds covering Shopify, Amazon Prime, Walmart Marketplace, and In-Store POS with buffer percentages.
- All demo data is scoped to tenant `acme`.

---

## 6. Conventions & Gotchas

1. **Multi-Tenancy & IDOR**:
   - Every view must filter queries using `tenant=request.tenant`.
   - Single object lookups must use `ecommerce_object(Model, pk, request.tenant)` or `get_object_or_404(Model, pk=pk, tenant=request.tenant)`.
   - ModelForms must use `TenantUniqueMixin` and filter all FK querysets in `__init__` to `self.tenant`.
   - Form `clean()` methods must invoke `reject_foreign(self, cleaned_data, [...])`.
2. **Context Variable Contract**:
   - List views pass `page_obj`, `is_paginated`, filter values, and choice constants.
   - Detail views pass the singular entity name along with preloaded related collections.
3. **Available-to-Promise (ATP)**:
   - Digital storefronts must show `ATP = max(0, quantity_on_hand - quantity_allocated - safety_stock_buffer)` rather than raw on-hand stock.
4. **Audit Logging Signature**:
   - `write_audit_log(request.user, obj, action, changes_dict)` — always pass `user` first, `obj` second, short action verb third, and changes dictionary fourth.
5. **Integer Query Param Guarding (Lesson L11)**:
   - Always validate foreign key filter parameters before passing to ORM: `if param and param.isdigit():`.
6. **Open Redirect Validation**:
   - Always validate `next` parameters with `url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()})`.

---

## 7. Sidebar Navigation

Mounted in `apps/core/navigation.py`:
```python
LIVE_LINKS["9.1"] = ("ecommerce:catalog_overview", "9.1 Product Catalog", "ecommerce")
LIVE_LINKS["9.2"] = ("ecommerce:inventory_operations", "9.2 Inventory & Stock", "ecommerce")
```
Appears under the eCommerce section of the primary navigation bar.
