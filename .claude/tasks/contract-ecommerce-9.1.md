# Contract — Sub-module 9.1: Product Catalog Management (Module 9: eCommerce Management System, `ecommerce`)

- **Sub-module:** 9.1 Product Catalog Management · **Module:** 9 eCommerce Management System · **App:** `apps/ecommerce`
- **Date:** 2026-10-28 · **Status:** FROZEN PRE-BUILD CONTRACT · **Phase:** 3.1 Spec
- **App Status:** Brand-new app (`apps/ecommerce/`). Initial migration: `0001_initial.py`.

---

## 1. Models & CHOICES Contract

All models inherit from `apps.ecommerce.models._base.TenantNumbered` (`tenant`, `number`, `created_at`, `updated_at`).

### 1.1 `StoreCategory` (`apps/ecommerce/models/ProductCatalog/StoreCategories.py`)
- **Table:** `ecommerce_store_category`
- **Number Prefix:** `ECAT` (`ECAT-00001`)
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='ecommerce_store_categories')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `name`: `CharField(max_length=120)`
  - `slug`: `SlugField(max_length=140)`
  - `parent`: `ForeignKey('self', on_delete=SET_NULL, null=True, blank=True, related_name='children')`
  - `description`: `TextField(blank=True)`
  - `image_url`: `URLField(blank=True)`
  - `display_order`: `PositiveIntegerField(default=0)`
  - `is_active`: `BooleanField(default=True)`
  - `include_in_menu`: `BooleanField(default=True)`
  - `meta_title`: `CharField(max_length=160, blank=True)`
  - `meta_description`: `CharField(max_length=255, blank=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='ecommerce_cat_tenant_num_uniq')`
  - `UniqueConstraint(fields=['tenant', 'slug'], name='ecommerce_cat_tenant_slug_uniq')`
  - `Index(fields=['tenant', 'is_active', 'display_order'], name='ecom_cat_tnt_act_ord_idx')`
- **Properties & Methods:**
  - `full_path`: returns `"Parent > Child > Grandchild"` breadcrumb string.
  - `get_breadcrumbs()`: returns list of ancestor dictionaries `[{'name': ..., 'slug': ...}]`.

### 1.2 `CatalogProduct` (`apps/ecommerce/models/ProductCatalog/CatalogProducts.py`)
- **Table:** `ecommerce_catalog_product`
- **Number Prefix:** `EPRD` (`EPRD-00001`)
- **CHOICES:**
  - `STATUS_CHOICES = [('draft', 'Draft'), ('active', 'Active'), ('archived', 'Archived')]`
  - `VISIBILITY_CHOICES = [('storefront', 'Storefront & Search'), ('hidden', 'Hidden'), ('search_only', 'Search Only')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='ecommerce_catalog_products')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `name`: `CharField(max_length=255)`
  - `slug`: `SlugField(max_length=255)`
  - `item`: `ForeignKey('scm.Item', on_delete=SET_NULL, null=True, blank=True, related_name='ecommerce_catalog_products')`
  - `primary_category`: `ForeignKey('ecommerce.StoreCategory', on_delete=SET_NULL, null=True, blank=True, related_name='primary_products')`
  - `categories`: `ManyToManyField('ecommerce.StoreCategory', blank=True, related_name='products')`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default='draft')`
  - `visibility`: `CharField(max_length=20, choices=VISIBILITY_CHOICES, default='storefront')`
  - `brand`: `CharField(max_length=120, blank=True)`
  - `short_description`: `CharField(max_length=500, blank=True)`
  - `description`: `TextField(blank=True)`
  - `hero_image_url`: `URLField(blank=True)`
  - `video_url`: `URLField(blank=True)`
  - `is_featured`: `BooleanField(default=False)`
  - `is_digital`: `BooleanField(default=False)`
  - `pim_completeness`: `PositiveIntegerField(default=0)` (0-100%)
  - `meta_title`: `CharField(max_length=160, blank=True)`
  - `meta_description`: `CharField(max_length=255, blank=True)`
  - `published_at`: `DateTimeField(null=True, blank=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='ecommerce_prd_tenant_num_uniq')`
  - `UniqueConstraint(fields=['tenant', 'slug'], name='ecommerce_prd_tenant_slug_uniq')`
  - `Index(fields=['tenant', 'status', 'visibility'], name='ecom_prd_tnt_stat_vis_idx')`
  - `Index(fields=['tenant', 'brand'], name='ecom_prd_tnt_brand_idx')`
- **Properties & Methods:**
  - `calculate_pim_completeness()`: recalculates score based on name, descriptions, category, brand, images, and active variants.
  - `price_range_display`: returns formatted price or range `"$\10.00"` or `"$\10.00 - $\25.00"`.
  - `active_variants`: helper property for active variants.

### 1.3 `ProductVariant` (`apps/ecommerce/models/ProductCatalog/ProductVariants.py`)
- **Table:** `ecommerce_product_variant`
- **Number Prefix:** `PVR` (`PVR-00001`)
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='ecommerce_product_variants')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `product`: `ForeignKey('ecommerce.CatalogProduct', on_delete=CASCADE, related_name='variants')`
  - `sku`: `CharField(max_length=64)`
  - `name`: `CharField(max_length=255)`
  - `option_values`: `JSONField(default=dict, blank=True)` (e.g. `{"Size": "M", "Color": "Navy"}`)
  - `barcode`: `CharField(max_length=64, blank=True)`
  - `price`: `DecimalField(max_digits=14, decimal_places=4, default=Decimal('0.0000'), validators=[MinValueValidator(0)])`
  - `compare_at_price`: `DecimalField(max_digits=14, decimal_places=4, null=True, blank=True, validators=[MinValueValidator(0)])`
  - `cost_price`: `DecimalField(max_digits=14, decimal_places=4, default=Decimal('0.0000'), validators=[MinValueValidator(0)])`
  - `item`: `ForeignKey('scm.Item', on_delete=SET_NULL, null=True, blank=True, related_name='ecommerce_variants')`
  - `weight_kg`: `DecimalField(max_digits=8, decimal_places=3, default=Decimal('0.000'), validators=[MinValueValidator(0)])`
  - `image_url`: `URLField(blank=True)`
  - `is_active`: `BooleanField(default=True)`
  - `sort_order`: `PositiveIntegerField(default=0)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='ecommerce_pvr_tenant_num_uniq')`
  - `UniqueConstraint(fields=['tenant', 'sku'], name='ecommerce_pvr_tenant_sku_uniq')`
  - `Index(fields=['tenant', 'product', 'is_active'], name='ecom_pvr_tnt_prd_act_idx')`
  - `Index(fields=['tenant', 'barcode'], name='ecom_pvr_tnt_barc_idx')`
- **Properties & Methods:**
  - `is_on_sale`: returns `True` if `compare_at_price and compare_at_price > price`.
  - `options_summary`: returns formatted string e.g. `"Size: M, Color: Navy"`.
  - `margin_pct`: calculated margin percentage based on price and cost_price.

### 1.4 `ProductRelationship` (`apps/ecommerce/models/ProductCatalog/ProductRelationships.py`)
- **Table:** `ecommerce_product_relationship`
- **Number Prefix:** `PRL` (`PRL-00001`)
- **CHOICES:**
  - `RELATIONSHIP_CHOICES = [('cross_sell', 'Cross-Sell'), ('up_sell', 'Up-Sell'), ('accessory', 'Accessory'), ('bundle_kit', 'Bundle / Kit Component'), ('bought_together', 'Frequently Bought Together')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='ecommerce_product_relationships')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `source_product`: `ForeignKey('ecommerce.CatalogProduct', on_delete=CASCADE, related_name='relationships_from')`
  - `target_product`: `ForeignKey('ecommerce.CatalogProduct', on_delete=CASCADE, related_name='relationships_to')`
  - `relationship_type`: `CharField(max_length=20, choices=RELATIONSHIP_CHOICES, default='cross_sell')`
  - `discount_pct`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'), validators=[MinValueValidator(0), MaxValueValidator(100)])`
  - `is_active`: `BooleanField(default=True)`
  - `sort_order`: `PositiveIntegerField(default=0)`
  - `notes`: `CharField(max_length=255, blank=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='ecommerce_prl_tenant_num_uniq')`
  - `UniqueConstraint(fields=['tenant', 'source_product', 'target_product', 'relationship_type'], name='ecommerce_prl_src_tgt_type_uniq')`
  - `Index(fields=['tenant', 'source_product', 'relationship_type'], name='ecom_prl_tnt_src_type_idx')`

---

## 2. Forms Contract & Exclusions

All forms live in `apps/ecommerce/forms/ProductCatalog/` and inherit from `_common.py`.

1. **`StoreCategoryForm`**:
   - `Meta.model = StoreCategory`
   - `Meta.fields = ['name', 'slug', 'parent', 'description', 'image_url', 'display_order', 'is_active', 'include_in_menu', 'meta_title', 'meta_description']`
   - Excluded: `tenant`, `number`, `created_at`, `updated_at`.
   - Clean: validates parent is not self or a direct descendant (cycles prevention).
2. **`CatalogProductForm`**:
   - `Meta.model = CatalogProduct`
   - `Meta.fields = ['name', 'slug', 'item', 'primary_category', 'categories', 'status', 'visibility', 'brand', 'short_description', 'description', 'hero_image_url', 'video_url', 'is_featured', 'is_digital', 'meta_title', 'meta_description']`
   - Excluded: `tenant`, `number`, `pim_completeness`, `published_at`, `created_at`, `updated_at`.
3. **`ProductVariantForm`**:
   - `Meta.model = ProductVariant`
   - `Meta.fields = ['product', 'sku', 'name', 'option_values', 'barcode', 'price', 'compare_at_price', 'cost_price', 'item', 'weight_kg', 'image_url', 'is_active', 'sort_order']`
   - Excluded: `tenant`, `number`, `created_at`, `updated_at`.
   - Clean: validates option_values JSON dictionary structure; price/compare_at sanity.
4. **`ProductRelationshipForm`**:
   - `Meta.model = ProductRelationship`
   - `Meta.fields = ['source_product', 'target_product', 'relationship_type', 'discount_pct', 'is_active', 'sort_order', 'notes']`
   - Excluded: `tenant`, `number`, `created_at`, `updated_at`.
   - Clean: ensures `source_product != target_product`.
5. **`ProductImportForm`** (`forms.Form`):
   - Fields: `csv_file = FileField()`, `dry_run = BooleanField(required=False, initial=False)`, `auto_create_categories = BooleanField(required=False, initial=True)`

---

## 3. URLs Contract

Namespace: `ecommerce`.

| URL Route Pattern | View Function | URL Name |
|---|---|---|
| `categories/` | `storecategory_list` | `storecategory_list` |
| `categories/create/` | `storecategory_create` | `storecategory_create` |
| `categories/<int:pk>/` | `storecategory_detail` | `storecategory_detail` |
| `categories/<int:pk>/edit/` | `storecategory_edit` | `storecategory_edit` |
| `categories/<int:pk>/delete/` | `storecategory_delete` | `storecategory_delete` |
| `products/` | `catalogproduct_list` | `catalogproduct_list` |
| `products/create/` | `catalogproduct_create` | `catalogproduct_create` |
| `products/import/` | `product_import_csv` | `product_import_csv` |
| `products/export/` | `product_export_csv` | `product_export_csv` |
| `products/<int:pk>/` | `catalogproduct_detail` | `catalogproduct_detail` |
| `products/<int:pk>/edit/` | `catalogproduct_edit` | `catalogproduct_edit` |
| `products/<int:pk>/delete/` | `catalogproduct_delete` | `catalogproduct_delete` |
| `products/<int:pk>/publish/` | `catalogproduct_publish` | `catalogproduct_publish` |
| `variants/` | `productvariant_list` | `productvariant_list` |
| `variants/create/` | `productvariant_create` | `productvariant_create` |
| `variants/<int:pk>/` | `productvariant_detail` | `productvariant_detail` |
| `variants/<int:pk>/edit/` | `productvariant_edit` | `productvariant_edit` |
| `variants/<int:pk>/delete/` | `productvariant_delete` | `productvariant_delete` |
| `relationships/` | `productrelationship_list` | `productrelationship_list` |
| `relationships/create/` | `productrelationship_create` | `productrelationship_create` |
| `relationships/<int:pk>/` | `productrelationship_detail` | `productrelationship_detail` |
| `relationships/<int:pk>/edit/` | `productrelationship_edit` | `productrelationship_edit` |
| `relationships/<int:pk>/delete/` | `productrelationship_delete` | `productrelationship_delete` |
| `overview/` | `catalog_overview` | `catalog_overview` |
| `''` | `catalog_overview` | `dashboard` |

---

## 4. Context Keys Contract (PINNED — Lesson L7)

Every view passes exact, deterministic context keys:

### 4.1 StoreCategory Views
- **List (`storecategory_list`):**
  - `categories`: queryset/page_obj of root and child categories
  - `page_obj`: paginator page object
  - `is_paginated`: boolean
  - `search_query`: `request.GET.get('q', '')`
  - `status_filter`: `request.GET.get('status', '')`
- **Detail (`storecategory_detail`):**
  - `category`: `StoreCategory` object
  - `products`: products in this category
  - `children`: direct sub-categories
- **Form (`storecategory_create`, `storecategory_edit`):**
  - `form`: `StoreCategoryForm` instance
  - `category`: `StoreCategory` object or None
  - `is_edit`: boolean
  - `parent_categories`: queryset of eligible parent categories

### 4.2 CatalogProduct Views
- **List (`catalogproduct_list`):**
  - `products`: paginated products queryset
  - `page_obj`: paginator page object
  - `is_paginated`: boolean
  - `search_query`: string
  - `status_filter`: string
  - `visibility_filter`: string
  - `category_filter`: string
  - `brand_filter`: string
  - `status_choices`: `CatalogProduct.STATUS_CHOICES`
  - `visibility_choices`: `CatalogProduct.VISIBILITY_CHOICES`
  - `categories_list`: queryset of active `StoreCategory`
  - `brands_list`: list of distinct brand strings
- **Detail (`catalogproduct_detail`):**
  - `product`: `CatalogProduct` object
  - `variants`: active/ordered variants
  - `relationships`: all relationships from this product
  - `cross_sells`: target products where type='cross_sell'
  - `up_sells`: target products where type='up_sell'
  - `accessories`: target products where type='accessory'
  - `bundles`: target products where type='bundle_kit'
  - `bought_together`: target products where type='bought_together'
- **Form (`catalogproduct_create`, `catalogproduct_edit`):**
  - `form`: `CatalogProductForm`
  - `product`: `CatalogProduct` object or None
  - `is_edit`: boolean
  - `primary_categories`: queryset of `StoreCategory`
  - `items_list`: queryset of `scm.Item`
  - `status_choices`: `CatalogProduct.STATUS_CHOICES`
  - `visibility_choices`: `CatalogProduct.VISIBILITY_CHOICES`

### 4.3 ProductVariant Views
- **List (`productvariant_list`):**
  - `variants`: paginated variants queryset
  - `page_obj`: paginator page object
  - `is_paginated`: boolean
  - `search_query`: string
  - `product_filter`: string
  - `is_active_filter`: string
  - `products_list`: queryset of `CatalogProduct`
- **Detail (`productvariant_detail`):**
  - `variant`: `ProductVariant` object
  - `product`: parent `CatalogProduct`
  - `item`: linked `scm.Item` or None
- **Form (`productvariant_create`, `productvariant_edit`):**
  - `form`: `ProductVariantForm`
  - `variant`: `ProductVariant` object or None
  - `is_edit`: boolean
  - `products_list`: queryset of `CatalogProduct`
  - `items_list`: queryset of `scm.Item`

### 4.4 ProductRelationship Views
- **List (`productrelationship_list`):**
  - `relationships`: paginated relationships queryset
  - `page_obj`: paginator page object
  - `is_paginated`: boolean
  - `search_query`: string
  - `type_filter`: string
  - `relationship_type_choices`: `ProductRelationship.RELATIONSHIP_CHOICES`
- **Detail (`productrelationship_detail`):**
  - `relationship`: `ProductRelationship` object
- **Form (`productrelationship_create`, `productrelationship_edit`):**
  - `form`: `ProductRelationshipForm`
  - `relationship`: `ProductRelationship` object or None
  - `is_edit`: boolean
  - `products_list`: queryset of `CatalogProduct`
  - `relationship_type_choices`: `ProductRelationship.RELATIONSHIP_CHOICES`

### 4.5 Bulk & Overview Views
- **Bulk Import (`product_import_csv`):**
  - `form`: `ProductImportForm`
  - `import_results`: dictionary of import summary stats (created, updated, skipped, errors)
  - `errors`: list of validation errors
- **Catalog Overview (`catalog_overview`):**
  - `total_products`: integer
  - `active_products`: integer
  - `draft_products`: integer
  - `total_categories`: integer
  - `total_variants`: integer
  - `zero_variant_products`: integer count of products without variants
  - `avg_pim_completeness`: float/integer percentage
  - `recent_products`: queryset of 5 recent products
  - `recent_categories`: queryset of 5 recent categories

---

## 5. Theme CSS Badge & Styling Contract

Per house standard (Lesson L33), semantic `-success`/`-danger` classes DO NOT EXIST. Only color-named badges are valid:
- `active` / `in_stock` -> `badge-green`
- `draft` / `bought_together` / `bundle_kit` -> `badge-amber`
- `archived` / `hidden` -> `badge-slate` or `badge-muted`
- `storefront` / `cross_sell` / `up_sell` / `accessory` -> `badge-info`
- `low_stock` / `at_risk` -> `badge-red`

---

## 6. Sidebar Navigation Contract (`apps/core/navigation.py`)

Exact verbatim mapping for `LIVE_LINKS["9.1"]`:
```python
"9.1": {
    "Product Information Management (PIM)": "ecommerce:catalogproduct_list",
    "Category & Navigation Hierarchy": "ecommerce:storecategory_list",
    "Product Variants & Configurations": "ecommerce:productvariant_list",
    "Bulk Import & Export": "ecommerce:product_import_csv",
    "Product Relationships & Bundling": "ecommerce:productrelationship_list",
    # Extra live leaves
    "Catalog Overview": "ecommerce:catalog_overview",
},
```
