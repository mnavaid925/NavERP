# Research — Sub-module 9.1: Product Catalog Management (Module 9 — eCommerce Management System, `ecommerce`)

- **Sub-module:** 9.1 Product Catalog Management
- **Module:** 9 eCommerce Management System
- **Target app:** `apps/ecommerce` (brand-new app; to be scaffolded in Phase 3)
- **Research date:** 2026-10-28
- **Phase:** 1 Research only
- **Output boundary:** `.claude/tasks/research-ecommerce-9.1.md` only; no application code, migrations, settings, navigation, or git commits

---

## 1. Executive Summary & Domain Architecture

Sub-module 9.1 is the **merchandising and product presentation foundation** of the eCommerce Management System. While warehouse inventory management (`apps/scm` and `apps/inventory`) tracks physical stock balances, batch lots, and valuation ledgers, eCommerce 9.1 manages how products are packaged, organized, variant-configured, cross-promoted, and discovered by digital buyers across web storefronts.

### The Decisive Ownership & Boundary Rule:
> **`scm.Item` remains the canonical physical inventory stock-keeping master.** It owns SKU, base UOM, item type, valuation costing, standard/average cost, and warehouse reorder points. 
> 
> **`ecommerce` 9.1 does NOT duplicate the inventory master.** Instead, `CatalogProduct` acts as the customer-facing merchandising header (with rich web descriptions, SEO slugs, publishing readiness, and marketing categorization), while `ProductVariant` represents purchasable SKU options (size/color/material) that link directly to physical `scm.Item` records for real-time stock and fulfillment.

### Recommended Build Scope — Exactly Four eCommerce Models:
1. **`CatalogProduct`** [`EPRD-`] — Merchandised product presentation header with SEO slug, publishing lifecycle (`draft`, `active`, `archived`), visibility, brand, rich copy, PIM completeness score, and optional physical item anchor (`scm.Item`).
2. **`StoreCategory`** [`ECAT-`] — Customer-facing merchandising navigation hierarchy (parent-child tree, SEO URLs, display order, menu placement, banner imagery) distinct from internal warehouse storage categories.
3. **`ProductVariant`** [`PVR-`] — Purchasable SKU matrix with option value mappings (e.g. Size=L, Color=Navy), independent storefront selling prices, compare-at MSRP, barcode, shipping weight, and FK to `scm.Item` for inventory tracking.
4. **`ProductRelationship`** [`PRL-`] — Merchandising links between products powering cross-sells, up-sells, accessories, bundles/kits, and frequently-bought-together suggestions with display ordering and promotional bundle discounts.

**Bulk Import & Export** (Bullet 4) is implemented as robust operational view actions and forms (CSV catalog export and bulk CSV import with validation, column mapping, and error reporting) operating across `CatalogProduct` and `ProductVariant`, avoiding table bloat while fulfilling all enterprise bulk workflow requirements.

---

## 2. Repo State Checked First

### 2.1 Navigation & App Tree State
- **`apps/core/navigation.py`:** Checked `LIVE_LINKS`. No `"9.*"` entries exist anywhere in the dictionary. Module 9 has zero built sub-modules. Sub-module 9.1 is the entry gate to Module 9.
- **`apps/ecommerce/`:** Verified non-existent. Module 9 will be scaffolded during Phase 3 of 9.1.

### 2.2 As-Built Core Spine Entities (Grep Verified)
Every spine entity mapped in this research was verified against the repository:

| Entity | Location | Verified Status | 9.1 Relationship |
|---|---|---|---|
| `scm.Item` | `apps/scm/models/InventoryManagement/Items.py:73` | **Present** | Canonical physical stock-keeping SKU; FK target for `CatalogProduct.item` and `ProductVariant.item` |
| `scm.ItemCategory` | `apps/scm/models/InventoryManagement/Items.py:34` | **Present** | Warehouse internal categorization; not storefront navigation |
| `scm.UOM` | `apps/scm/models/InventoryManagement/Items.py:51` | **Present** | Measurement units; reused for packaging specifications |
| `inventory.ItemAttribute` | `apps/inventory/models/Catalog/ItemAttributes.py:19` | **Present** | Name/value spec-sheet attributes hanging off `scm.Item` |
| `inventory.ItemPrice` | `apps/inventory/models/Catalog/ItemPrices.py:19` | **Present** | Sell-side tier prices (retail, wholesale, volume breaks) on `scm.Item` |
| `inventory.ProductFile` | `apps/inventory/models/Catalog/ProductFiles.py:28` | **Present** | Photos, PDFs, datasheets, and manuals attached to `scm.Item` |
| `sales.SalesPriceBookEntry` | `apps/sales/models/MasterDataConfiguration/SalesPriceBookEntries.py:10` | **Present** | B2B CPQ pricebook entries (`NUMBER_PREFIX = "PBE"`) |
| `sales.ProductBundleOption` | `apps/sales/models/QuoteProposalCPQ/ProductBundles.py:8` | **Present** | CPQ quote bundling rules (`NUMBER_PREFIX = "BND"`) |
| `crm.Product` | `apps/crm/models/SalesForceAutomation/Products.py:5` | **Present** | SFA quoting products (`NUMBER_PREFIX = "PRD"`) |
| `scm.SupplierCatalog` | `apps/scm/models/ProcurementManagement/SupplierCatalogs.py:9` | **Present** | Vendor procurement catalog (`NUMBER_PREFIX = "CAT"`) |
| `core.Party` | `apps/core/models/Party.py:5` | **Present** | Customer / Vendor / Brand owner identity lens |
| `accounting.Currency` | `apps/accounting/models/GeneralLedger/Currencies.py:6` | **Present** | Multi-currency ISO currency code master |
| `core.Tenant` | `apps/core/models/Tenant.py:17` | **Present** | Multi-tenant isolation boundary |

### 2.3 Prefix Collision Verification
We executed an exhaustive scan of `NUMBER_PREFIX` across all apps and queried `apps.core.settings_engine.prefix_usage()`:
- ❌ **`CAT`** is **ALREADY IN USE** by `scm.SupplierCatalog` (`ProcurementManagement/SupplierCatalogs.py`).
- ❌ **`PRD`** is **ALREADY IN USE** by `crm.Product` and `scm.ProductionTimeLog`.
- ❌ **`BND`** is **ALREADY IN USE** by `sales.ProductBundleOption`.
- ❌ **`PBE`** is **ALREADY IN USE** by `sales.SalesPriceBookEntry`.
- ✅ **`ECAT`** (`StoreCategory`) — **100% Free** (zero codebase occurrences).
- ✅ **`EPRD`** (`CatalogProduct`) — **100% Free** (zero codebase occurrences).
- ✅ **`PVR`** (`ProductVariant`) — **100% Free** (zero codebase occurrences).
- ✅ **`PRL`** (`ProductRelationship`) — **100% Free** (zero codebase occurrences).
- Additional verified free candidate prefixes: `PIM`, `CTG`, `SKU`, `VAR`, `EPIM`, `EREL`, `EBUN`.

---

## 3. Commercial Market Leaders Surveyed

We analyzed 10 leading commercial platforms across PIM, enterprise eCommerce suites, and modern headless architectures:

1. **Shopify** (SaaS eCommerce Market Leader)
   - *Key Architecture:* Standard Product Taxonomy with Category Metafields, up to 2,048 Variants per product, Option axes (Size/Color/Material), Smart (rule-based) & Manual Collections, Native Product Bundles mapping bundle variants directly to component SKUs.
   - *Source:* [Shopify Product & Variant GraphQL API](https://shopify.dev/docs/apps/build/graphql/products-variants) · [Shopify Taxonomy](https://help.shopify.com/en/manual/products/details/product-taxonomy) · [Shopify Bundles](https://help.shopify.com/en/manual/products/bundles)

2. **Akeneo PIM** (Open Source & Enterprise PIM Benchmark)
   - *Key Architecture:* Product Models (family template) vs. Variant Products (concrete sellable SKUs), Multi-tree Category Hierarchies (channel-specific categorization), Channel Completeness Rules (readiness gates before activation), Asset Manager with contextualized media by locale/channel.
   - *Source:* [Akeneo Product Information Management](https://www.akeneo.com/product-information-management/) · [Akeneo Variants](https://help.akeneo.com/articles/manage-your-variants.html) · [Akeneo Categories](https://help.akeneo.com/articles/manage-your-categories.html)

3. **Pimcore** (PIM, MDM & Digital Asset Management Data Hub)
   - *Key Architecture:* Dual PIM + DAM platform, Classification Stores for dynamic technical specifications, hierarchical taxonomy trees with data inheritance, rich object relationships (cross-sell, up-sell, accessory, kit) with bidirectional propagation, Data Importer/Data Hub for CSV/XML/JSON syndication.
   - *Source:* [Pimcore PIM Core Platform](https://pimcore.com/en/products/pim-product-information-management) · [Pimcore Data Modeling](https://pimcore.com/docs/platform/Pimcore/Data_Modeling/)

4. **BigCommerce** (Enterprise SaaS Commerce)
   - *Key Architecture:* Decoupled Variant Options (stock-keeping items with unique SKUs and prices) vs. Modifier Options (non-inventory customizations like engravings or gift wraps), Multi-level Category Trees with independent Multi-Storefront assignment, Custom Fields, manual and automatic Related Products.
   - *Source:* [BigCommerce Product Options V3](https://support.bigcommerce.com/s/article/Product-Options-v3) · [BigCommerce REST Catalog API](https://developer.bigcommerce.com/docs/rest-catalog)

5. **Adobe Commerce / Magento 2** (Enterprise EAV Catalog Architecture)
   - *Key Architecture:* 6 Native Product Types (Simple, Configurable, Grouped, Bundle, Virtual, Downloadable), Category Hierarchy with URL rewrites and breadcrumbs, tri-part Product Relationships (Related items on PDP, Up-sell items for premium upgrades, Cross-sell items on the shopping cart page).
   - *Source:* [Adobe Commerce Product Types](https://experienceleague.adobe.com/en/docs/commerce-admin/catalog/products/types/product-types) · [Product Relationships](https://experienceleague.adobe.com/en/docs/commerce-admin/catalog/products/relations/product-relationships)

6. **Salsify** (Product Experience Management & Digital Shelf Leader)
   - *Key Architecture:* Enterprise PXM hub, parent-child variant modeling, kits/bundles/assemblies, cross-sell and up-sell networks, digital shelf readiness scoring, channel-specific attribute formatting and syndication feeds.
   - *Source:* [Salsify PIM](https://www.salsify.com/products/product-information-management) · [Salsify Digital Shelf Syndication](https://www.salsify.com/products/digital-shelf-syndication)

7. **inriver PIM** (Elastic Data Model & Multi-Channel Syndication)
   - *Key Architecture:* Graph-based elastic data model connecting Products to Items (variants), Resources (media assets), and Channels, automated completeness evaluation, relationship links for accessories and spare parts.
   - *Source:* [inriver PIM Capabilities](https://www.inriver.com/product/product-information-management/) · [inriver Syndication](https://www.inriver.com/capabilities/syndication/)

8. **Medusa.js** (Modern Decoupled Headless Commerce Engine)
   - *Key Architecture:* Product Module with `ProductCategory` (hierarchical adjacency tree), `Product` (merchandising root), `ProductOption` & `ProductOptionValue`, `ProductVariant` (SKU, barcode, independent prices, weight, dimensional bounds), remote links connecting variants to Inventory and Pricing modules.
   - *Source:* [Medusa Product Module](https://docs.medusajs.com/resources/commerce-modules/product) · [Medusa Category Hierarchy](https://docs.medusajs.com/resources/commerce-modules/product/categories)

9. **Saleor** (GraphQL-Native Headless Commerce)
   - *Key Architecture:* `ProductType` (defining attribute schemas and physical/digital kind), `Product`, `ProductVariant` (the sole purchasable unit), Channel-specific pricing and publication state, Product and Variant Media attachments.
   - *Source:* [Saleor Product Overview](https://docs.saleor.io/docs/3.x/developer/products/overview) · [Saleor Attributes](https://docs.saleor.io/docs/3.x/developer/products/attributes)

10. **Sylius** (Decoupled Symfony eCommerce Framework)
    - *Key Architecture:* Decoupled components: `Product`, `Taxon` (taxonomy tree), `ProductVariant` (SKUs, options, channel pricing), `ProductAttribute` (translatable dynamic specs via `ProductAttributeValue`), Main Taxon for canonical SEO routing.
    - *Source:* [Sylius Products Book](https://docs.sylius.com/en/latest/book/products/index.html) · [Sylius Taxons & Taxonomy](https://docs.sylius.com/en/latest/book/products/taxons.html)

---

## 4. Feature Catalog (Grouped by NavERP.md 9.1 Bullets)

### 4.1 Product Information Management (PIM)
Centralized product data hub with descriptions, specifications, images, videos, and multilingual content.

- **Merchandised Product Header** — Central storefront representation decoupling web cataloging from raw inventory rows; maintains title, slug, merchandising status, visibility, and brand attribution.
  - *Seen in:* Shopify, BigCommerce, Adobe Commerce, Medusa.js, Akeneo
  - *Priority:* `table-stakes`
  - *Spine Mapping:* New model `CatalogProduct` [`EPRD-`]; optionally links to `scm.Item`
  - *Status:* Buildable now

- **PIM Completeness & Readiness Scoring** — Automated or calculated score (0–100%) checking required merchandising data (description, image, category, SEO tags, variants) before permitting product publishing.
  - *Seen in:* Akeneo PIM, Salsify, inriver, Pimcore
  - *Priority:* `differentiator`
  - *Spine Mapping:* Column `CatalogProduct.pim_completeness` + computed calculation method
  - *Status:* Buildable now

- **Rich Web Copy & Multimedia Pointers** — HTML/Markdown long description, short excerpt for product cards, primary cover image, and external video URL (YouTube/Vimeo embed pointer).
  - *Seen in:* Shopify, BigCommerce, Sylius, Saleor
  - *Priority:* `table-stakes`
  - *Spine Mapping:* Fields on `CatalogProduct`; binary file storage reuses `inventory.ProductFile` or media URLs
  - *Status:* Buildable now

- **SEO & Canonical URL Optimization** — Custom meta title, meta description, URL slug, and canonical path generation for search engine ranking.
  - *Seen in:* Shopify, BigCommerce, Adobe Commerce, Sylius
  - *Priority:* `table-stakes`
  - *Spine Mapping:* Fields on `CatalogProduct` and `StoreCategory`
  - *Status:* Buildable now

- **Multilingual Content Storage** — Per-locale translated titles, descriptions, and metadata.
  - *Seen in:* Akeneo, Pimcore, Sylius, Saleor
  - *Priority:* `common`
  - *Spine Mapping:* Deferred to future translation pass / JSON localization field to maintain lean 4-model scope
  - *Status:* Deferred (see Section 7)

---

### 4.2 Category & Navigation Hierarchy
Dynamic category trees, faceted navigation, breadcrumb management, and SEO-friendly URLs.

- **Hierarchical Category Tree (Adjacency List)** — Multi-level nested merchandising taxonomy with parent-child relationships allowing arbitrary depth (e.g. *Apparel > Mens > Jackets*).
  - *Seen in:* Shopify (Collections), BigCommerce, Medusa.js, Sylius, Akeneo
  - *Priority:* `table-stakes`
  - *Spine Mapping:* New model `StoreCategory` [`ECAT-`] with self-referencing `parent` FK
  - *Status:* Buildable now

- **Automatic Breadcrumb & Path Traversal** — Traversal logic that builds complete breadcrumb trails (`Home > Electronics > Audio > Headphones`) and canonical hierarchical URL paths.
  - *Seen in:* Adobe Commerce, BigCommerce, Sylius (Main Taxon), Medusa.js
  - *Priority:* `table-stakes`
  - *Spine Mapping:* Model property/method on `StoreCategory` (`get_breadcrumbs()`, `full_path`)
  - *Status:* Buildable now

- **Storefront Navigation & Display Controls** — Display ordering, active status toggle, "Include in Storefront Navigation Menu" flag, and category banner image.
  - *Seen in:* Shopify, BigCommerce, Adobe Commerce, Sylius
  - *Priority:* `table-stakes`
  - *Spine Mapping:* Fields on `StoreCategory` (`sort_order`, `is_active`, `include_in_menu`, `banner_url`)
  - *Status:* Buildable now

- **Multi-Category Assignment** — Many-to-many relationship allowing a product to appear in multiple categories (e.g. both "Winter Jackets" and "Featured Holiday Deals").
  - *Seen in:* Shopify, BigCommerce, Adobe Commerce, Sylius
  - *Priority:* `table-stakes`
  - *Spine Mapping:* `CatalogProduct.primary_category` FK + `categories` M2M to `StoreCategory`
  - *Status:* Buildable now

- **Faceted Navigation Attribute Filters** — Facet definitions for customer sidebar filtering (by price, brand, color, size).
  - *Seen in:* BigCommerce, Adobe Commerce, Algolia
  - *Priority:* `common`
  - *Spine Mapping:* Handled via GET query parameters and faceted filter logic in 9.1 views; heavy search indexing belongs to **9.7 Search & Product Discovery**
  - *Status:* Buildable now (lightweight query facets) / full search index deferred to 9.7

---

### 4.3 Product Variants & Configurations
Size, color, material, and custom option matrices with independent SKUs and pricing.

- **Purchasable SKU Matrix** — Child variant rows representing distinct purchasable configurations (e.g. Size=L, Color=Navy) each with a dedicated SKU.
  - *Seen in:* Shopify, BigCommerce, Adobe Commerce, Medusa.js, Saleor, Sylius
  - *Priority:* `table-stakes`
  - *Spine Mapping:* New model `ProductVariant` [`PVR-`] with FK to `CatalogProduct`
  - *Status:* Buildable now

- **Structured Option Value Matrix** — Normalized or JSON-structured storage for multi-dimensional options (e.g. `{"Size": "Large", "Color": "Navy", "Material": "Cotton"}`).
  - *Seen in:* Medusa.js, Shopify, BigCommerce, Saleor
  - *Priority:* `table-stakes`
  - *Spine Mapping:* `ProductVariant.option_values` (JSONField / structured dictionary)
  - *Status:* Buildable now

- **Independent Storefront Pricing & Compare-at MSRP** — Storefront selling price (`price`) alongside a strike-through compare-at price (`compare_at_price`) for on-sale visual presentation.
  - *Seen in:* Shopify, BigCommerce, Medusa.js, WooCommerce
  - *Priority:* `table-stakes`
  - *Spine Mapping:* `ProductVariant.price`, `ProductVariant.compare_at_price`
  - *Status:* Buildable now

- **Physical Inventory Fulfillment Link** — Foreign key linking each eCommerce variant to a physical `scm.Item` SKU to enable real-time stock decrements and ERP warehouse fulfillment.
  - *Seen in:* SAP Commerce, BigCommerce ERP connectors, Medusa Remote Links
  - *Priority:* `table-stakes`
  - *Spine Mapping:* `ProductVariant.item` FK to `scm.Item`
  - *Status:* Buildable now

- **Shipping Dimension & Barcode Tracking** — Variant-level shipping weight (essential for 9.4 carrier rate calculation) and retail barcode identifiers (UPC / EAN / GTIN).
  - *Seen in:* Shopify, BigCommerce, Saleor, Medusa.js
  - *Priority:* `table-stakes`
  - *Spine Mapping:* `ProductVariant.barcode`, `ProductVariant.weight_kg`
  - *Status:* Buildable now

- **Modifier Options / Custom Monogramming** — Free-form buyer text inputs or non-inventory customizations (e.g. engraving).
  - *Seen in:* BigCommerce Modifier Options, Shopify Line Item Properties
  - *Priority:* `common`
  - *Spine Mapping:* Belongs to **9.4 Shopping Cart & Checkout** line item properties
  - *Status:* Parked to 9.4

---

### 4.4 Bulk Import & Export
CSV, Excel, and API-based mass product updates, image syncing, and catalog versioning.

- **Bulk CSV Product Export** — Filtered export of products and variants to CSV with complete columns (SKU, title, category, price, inventory link, status) for offline editing.
  - *Seen in:* Shopify, BigCommerce, WooCommerce, Akeneo
  - *Priority:* `table-stakes`
  - *Spine Mapping:* Streaming HTTP CSV view action (`/ecommerce/products/export/`)
  - *Status:* Buildable now

- **Bulk CSV Product Ingestion with Validation** — Mass upload of product catalogs via CSV with row-by-row validation, duplicate SKU detection, category mapping, and error reporting table.
  - *Seen in:* Shopify, BigCommerce, Pimcore Data Importer, Akeneo
  - *Priority:* `table-stakes`
  - *Spine Mapping:* Form & View action with preview and transaction rollback (`/ecommerce/products/import/`)
  - *Status:* Buildable now

- **Mass Price & Status Adjustments** — Batch updating catalog prices (percentage increase/decrease) or activating/deactivating assortments.
  - *Seen in:* BigCommerce, Akeneo, Pimcore
  - *Priority:* `common`
  - *Spine Mapping:* Batch action view (`/ecommerce/products/bulk-update/`)
  - *Status:* Buildable now

- **Catalog Snapshot & Versioning** — Audit history tracking who modified catalog attributes, prices, or publishing state.
  - *Seen in:* Pimcore, Akeneo, Salsify
  - *Priority:* `common`
  - *Spine Mapping:* Reuses `core.AuditLog`
  - *Status:* Buildable now

- **Cloud Media Asset Syncing** — Automated S3 / CDN bulk image ingestion from ZIP or external URLs.
  - *Seen in:* Pimcore, Akeneo Enterprise Asset Manager
  - *Priority:* `differentiator`
  - *Spine Mapping:* Heavy worker queue / cloud integration; deferred to **9.19 / external integration**
  - *Status:* Deferred

---

### 4.5 Product Relationships & Bundling
Cross-sells, up-sells, accessories, kits, and frequently-bought-together logic.

- **Multi-Type Merchandising Relationships** — Explicit directed relationships between products with distinct semantic types:
  1. `cross_sell` — Complementary items shown in cart or checkout (e.g. HDMI cable with TV)
  2. `up_sell` — Premium alternative shown on PDP (e.g. 256GB model when viewing 64GB)
  3. `accessory` — Compatible attachments or add-ons (e.g. phone case, charger)
  4. `bundle_kit` — Multi-item bundle sold as a cohesive unit (e.g. camera + lens + bag)
  5. `bought_together` — Algorithmic or curated pairings to increase Average Order Value (AOV)
  - *Seen in:* Adobe Commerce (Magento 2), BigCommerce, Shopify Bundles, Salsify
  - *Priority:* `table-stakes`
  - *Spine Mapping:* New model `ProductRelationship` [`PRL-`]
  - *Status:* Buildable now

- **Promotional Bundle Discounts** — Percentage discount applied when the related target item is purchased together with the source product (e.g. "Save 15% when purchased together").
  - *Seen in:* Shopify Bundles, Adobe Commerce, BigCommerce
  - *Priority:* `common`
  - *Spine Mapping:* `ProductRelationship.discount_pct`
  - *Status:* Buildable now

- **Relationship Sorting & Status Controls** — Display ordering on the PDP and active toggle to retire stale recommendations.
  - *Seen in:* Adobe Commerce, BigCommerce, Pimcore
  - *Priority:* `table-stakes`
  - *Spine Mapping:* `ProductRelationship.sort_order`, `ProductRelationship.is_active`
  - *Status:* Buildable now

- **Dynamic Collaborative-Filtering Recommendation Engine** — Machine learning clickstream models generating automated "frequently bought together" links.
  - *Seen in:* Amazon, Shopify Predictive Recommendations
  - *Priority:* `differentiator`
  - *Spine Mapping:* Belongs to **9.8 Personalization & Recommendation Engine**
  - *Status:* Parked to 9.8

---

## 5. Recommended Build Scope (This Pass — Exactly 4 Models)

To maintain architectural elegance, high cohesion, and strict compliance with the `/next-module` 1–4 model boundary, we recommend the following four tenant-scoped models under `apps/ecommerce/models/ProductCatalog/`:

```
apps/ecommerce/models/ProductCatalog/
├── StoreCategories.py       -> StoreCategory (ECAT-)
├── CatalogProducts.py        -> CatalogProduct (EPRD-)
├── ProductVariants.py        -> ProductVariant (PVR-)
└── ProductRelationships.py   -> ProductRelationship (PRL-)
```

### 1. `StoreCategory` [`ECAT-`]
Merchandising category tree for storefront navigation and SEO.
- **Number prefix:** `ECAT` (`ECAT-00001`) — Verified free
- **Fields:**
  - `tenant` (TenantOwned/TenantNumbered)
  - `category_number` (CharField, unique per tenant)
  - `name` (CharField, max_length=120)
  - `slug` (SlugField, max_length=140)
  - `parent` (ForeignKey `"self"`, null=True, blank=True, related_name="children")
  - `description` (TextField, blank=True)
  - `image_url` (URLField, blank=True)
  - `display_order` (PositiveIntegerField, default=0)
  - `is_active` (BooleanField, default=True)
  - `include_in_menu` (BooleanField, default=True)
  - `meta_title` (CharField, max_length=160, blank=True)
  - `meta_description` (CharField, max_length=255, blank=True)
- **Justified by:** Researched capabilities in Akeneo, BigCommerce, Medusa.js, Sylius (Bullet 2).
- **Spine FKs:** Self-referencing tree (`parent`).

### 2. `CatalogProduct` [`EPRD-`]
Merchandised product presentation header for digital storefronts.
- **Number prefix:** `EPRD` (`EPRD-00001`) — Verified free
- **Fields:**
  - `tenant` (TenantOwned/TenantNumbered)
  - `product_number` (CharField, unique per tenant)
  - `name` (CharField, max_length=255)
  - `slug` (SlugField, max_length=255)
  - `item` (ForeignKey `"scm.Item"`, null=True, blank=True, related_name="ecommerce_products", help_text="Canonical inventory master for single-SKU products or primary item anchor")
  - `primary_category` (ForeignKey `"ecommerce.StoreCategory"`, on_delete=models.SET_NULL, null=True, blank=True, related_name="primary_products")
  - `categories` (ManyToManyField `"ecommerce.StoreCategory"`, blank=True, related_name="products")
  - `status` (CharField, choices=[`draft`, `active`, `archived`], default=`draft`)
  - `visibility` (CharField, choices=[`storefront`, `hidden`, `search_only`], default=`storefront`)
  - `brand` (CharField, max_length=120, blank=True)
  - `short_description` (CharField, max_length=500, blank=True)
  - `description` (TextField, blank=True)
  - `hero_image_url` (URLField, blank=True)
  - `video_url` (URLField, blank=True)
  - `is_featured` (BooleanField, default=False)
  - `is_digital` (BooleanField, default=False)
  - `pim_completeness` (PositiveIntegerField, default=0, help_text="Calculated readiness score 0-100%")
  - `meta_title` (CharField, max_length=160, blank=True)
  - `meta_description` (CharField, max_length=255, blank=True)
  - `published_at` (DateTimeField, null=True, blank=True)
- **Justified by:** Researched capabilities in Shopify, Akeneo, BigCommerce, Pimcore (Bullet 1).
- **Spine FKs:** `scm.Item` (canonical inventory), `StoreCategory` (merchandising taxonomy).

### 3. `ProductVariant` [`PVR-`]
Purchasable SKU configuration matrix with independent pricing and inventory mapping.
- **Number prefix:** `PVR` (`PVR-00001`) — Verified free
- **Fields:**
  - `tenant` (TenantOwned/TenantNumbered)
  - `variant_number` (CharField, unique per tenant)
  - `product` (ForeignKey `"ecommerce.CatalogProduct"`, on_delete=models.CASCADE, related_name="variants")
  - `sku` (CharField, max_length=64)
  - `name` (CharField, max_length=255, help_text="e.g. Red / Large")
  - `option_values` (JSONField, default=dict, help_text='Key-value option matrix: {"Size": "L", "Color": "Navy"}')
  - `barcode` (CharField, max_length=64, blank=True, help_text="UPC, EAN, or ISBN")
  - `price` (DecimalField, max_digits=14, decimal_places=4, validators=[MinValueValidator(0)], help_text="Storefront selling price")
  - `compare_at_price` (DecimalField, max_digits=14, decimal_places=4, null=True, blank=True, help_text="MSRP / Strike-through price")
  - `cost_price` (DecimalField, max_digits=14, decimal_places=4, default=0, help_text="Base cost for margin analysis")
  - `item` (ForeignKey `"scm.Item"`, on_delete=models.SET_NULL, null=True, blank=True, related_name="ecommerce_variants", help_text="Physical inventory SKU for real-time stock and warehouse fulfillment")
  - `weight_kg` (DecimalField, max_digits=8, decimal_places=3, default=0, help_text="Weight for shipping calculations")
  - `image_url` (URLField, blank=True)
  - `is_active` (BooleanField, default=True)
  - `sort_order` (PositiveIntegerField, default=0)
- **Justified by:** Researched capabilities in Shopify, BigCommerce, Medusa.js, Saleor, Sylius (Bullet 3).
- **Spine FKs:** `CatalogProduct` (parent container), `scm.Item` (canonical stock-keeping SKU).

### 4. `ProductRelationship` [`PRL-`]
Merchandising connection engine for cross-sells, up-sells, accessories, bundles, and kits.
- **Number prefix:** `PRL` (`PRL-00001`) — Verified free
- **Fields:**
  - `tenant` (TenantOwned/TenantNumbered)
  - `relationship_number` (CharField, unique per tenant)
  - `source_product` (ForeignKey `"ecommerce.CatalogProduct"`, on_delete=models.CASCADE, related_name="relationships_from")
  - `target_product` (ForeignKey `"ecommerce.CatalogProduct"`, on_delete=models.CASCADE, related_name="relationships_to")
  - `relationship_type` (CharField, max_length=20, choices=[
      (`cross_sell`, `Cross-Sell`),
      (`up_sell`, `Up-Sell`),
      (`accessory`, `Accessory`),
      (`bundle_kit`, `Bundle / Kit`),
      (`bought_together`, `Frequently Bought Together`),
    ], default=`cross_sell`)
  - `discount_pct` (DecimalField, max_digits=5, decimal_places=2, default=0, help_text="Discount when purchased together")
  - `is_active` (BooleanField, default=True)
  - `sort_order` (PositiveIntegerField, default=0)
  - `notes` (CharField, max_length=255, blank=True)
- **Justified by:** Researched capabilities in Adobe Commerce (Magento 2), BigCommerce, Pimcore, Salsify (Bullet 5).
- **Spine FKs:** `CatalogProduct` (source and target products).

---

## 6. Belongs to Sibling Sub-Modules (Parked, Not Scoped Here)

To prevent scope creep and preserve clean sub-module boundaries, the following capabilities are explicitly parked for their dedicated sub-modules:

| Feature Area | Owning Sibling Sub-Module | Rationale |
|---|---|---|
| Multi-location stock levels & reservations | **9.2 Inventory & Stock Management** | Warehouse stock pools, safety stock thresholds, and low-stock alerts belong to 9.2. |
| Backorder & pre-order inventory gating | **9.2 Inventory & Stock Management** | Customer-facing availability messaging and waitlist capture belong to 9.2. |
| Dynamic promo discounts & coupon codes | **9.3 Pricing & Promotion Engine** | Stacking discount rules, coupon codes, and customer-segment pricing belong to 9.3. |
| Flash sales & limited-time countdown timers | **9.3 Pricing & Promotion Engine** | Time-based flash sale engines belong to 9.3. |
| Shopping cart persistence & checkout session | **9.4 Shopping Cart & Checkout** | Cart persistence, guest sessions, and line-item modifier options belong to 9.4. |
| Shipping rate calculation & Tax compliance | **9.4 Shopping Cart & Checkout** | Carrier API calculation and tax nexus calculation belong to 9.4. |
| Order validation, split routing & fulfillment | **9.5 Order Management System (OMS)** | OMS lifecycle from payment authorization to warehouse routing belongs to 9.5. |
| Typo-tolerant search & autocomplete | **9.7 Search & Product Discovery** | Elasticsearch / Algolia search clusters and instant predictive search belong to 9.7. |
| AI collaborative filtering recommendations | **9.8 Personalization & Recommendation** | Machine learning behavioral models and clickstream recommendations belong to 9.8. |
| Visual drag-and-drop page builder | **9.9 Content Management System (CMS)** | Landing page builders and editorial layout grids belong to 9.9. |
| Multi-vendor seller onboarding & catalog split | **9.11 Marketplace & Multi-Vendor** | Vendor commissions and split seller catalogs belong to 9.11. |
| Multi-brand & multi-storefront routing | **9.20 Multi-Store & Platform Operations** | Distinct domain routing and multi-currency storefronts belong to 9.20. |

---

## 7. Deferred (Later Passes / External Integrations)

The following items are recognized as enterprise PIM / eCommerce capabilities but are deferred from 9.1's core build:

1. **Automated Multilingual Translation Pipeline:**
   - *Reason for Deferral:* Deep multi-locale translation tables (`ProductTranslation`) add massive schema complexity. In 9.1, standard Unicode text fields handle international character sets cleanly; a centralized translation framework belongs to Module 23 / core i18n tooling.
2. **Binary Video Transcoding & HLS Streaming:**
   - *Reason for Deferral:* NavERP stores URL pointers to hosted video providers (YouTube, Vimeo, Cloudflare Stream) rather than managing video transcoding workers and raw storage.
3. **Automated Image Background Removal & WEBP Microservice:**
   - *Reason for Deferral:* Best handled by external CDN transformers (Cloudinary, imgix) or client-side upload preprocessing rather than blocking the core Django application server.
4. **Third-Party Marketplace Feed Syndication (Google Merchant Center, Amazon Feed API):**
   - *Reason for Deferral:* External XML/RSS feed generators belong to **9.19 Integration & API Ecosystem** once the core catalog models are stabilized.
5. **Real-time EDI Catalog Feeds (832 Price/Sales Catalog):**
   - *Reason for Deferral:* B2B EDI transaction sets belong to **9.17 B2B & Wholesale Commerce** and **9.19 Integration & API Ecosystem**.

---

## 8. Summary & Next Steps

This research establishes a rock-solid, production-grade foundation for **Sub-module 9.1 Product Catalog Management**:
- **Clean Spine Extension:** Reuses `scm.Item` as the physical inventory anchor without duplication.
- **Zero Prefix Collisions:** Proved `ECAT`, `EPRD`, `PVR`, and `PRL` are 100% free across the entire codebase.
- **Strict 4-Model Scope:** `StoreCategory`, `CatalogProduct`, `ProductVariant`, and `ProductRelationship` fully deliver the 5 NavERP.md feature bullets.
- **Hand-off to Phase 2 (`todo` agent):** Ready to generate the concrete implementation plan in `.claude/tasks/todo.md`.
