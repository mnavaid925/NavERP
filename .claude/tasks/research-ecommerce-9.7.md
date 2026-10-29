# Research — Sub-module 9.7: Search & Product Discovery (Module 9 — eCommerce Management System, `ecommerce`)

- **Sub-module:** 9.7 Search & Product Discovery
- **Module:** 9 eCommerce Management System
- **Target app:** `apps/ecommerce` (extending the app created in 9.1 and extended in 9.2, 9.3, 9.4, 9.5, and 9.6)
- **Research date:** 2026-10-30
- **Phase:** 1 Research only
- **Output boundary:** `.claude/tasks/research-ecommerce-9.7.md` only

---

## 1. Executive Summary & Domain Architecture

Sub-module 9.7 represents the **Search, Autocomplete, Faceted Filtering, Search Merchandising, Synonym & Query Redirect Engine, and Search Discovery Analytics** of the NavERP eCommerce platform.

In modern high-conversion digital commerce (exemplified by Algolia, Coveo, Bloomreach Discovery, Constructor.io, Searchspring / Athos Commerce, Klevu, Yext, Nosto, and visual AI specialists ViSenze and Syte), site search is not a simple SQL `LIKE '%query%'` text filter. It is an intelligent discovery engine that converts shopper purchase intent into revenue. Up to 43% of eCommerce website visitors go directly to the search box, and searchers convert at 2-3x the rate of casual category browsers. When search delivers irrelevant results or a dead-end zero-results page, over 70% of shoppers abandon the site permanently.

### Architectural Boundary Rulings (L28, L29, L36, L37):
1. **Catalog Spine Integration — Search Targets `ecommerce.CatalogProduct` & `ProductVariant`**:
   The primary searchable entity is **`ecommerce.CatalogProduct`** (`EPRD-`, 9.1), with purchasable SKUs, options, and prices indexed from **`ecommerce.ProductVariant`** (`PVR-`, 9.1) and category taxonomy from **`ecommerce.StoreCategory`** (`ECAT-`, 9.1). Sub-module 9.7 does not create a duplicate product index table; instead, it provides search configuration, synonym dictionaries, merchandising overrides, and execution telemetry that operate directly against the catalog spine.
2. **Clear Boundary: 9.7 (Search & Product Discovery) vs. 9.8 (Personalization & Recommendation Engine)**:
   - **Sub-module 9.7 (This Pass)** owns query-driven search, autocomplete suggestions, faceted navigation metadata, search merchandising rules (boost, bury, pin, block, redirect), null-result tracking, and search query telemetry.
   - **Sub-module 9.8 (Sibling)** owns deep clickstream session tracking, machine-learned collaborative filtering recommendations, shopper RFM segmentation, personalized homepages, and abandoned cart triggers.
   - *Interface boundary*: 9.7 provides the search query log and merchandising hooks that 9.8 can later read to inject personalized user affinity vectors into search scoring.
3. **Database Architecture & Zero-External-Dependency Engine**:
   Commercial search leaders often run external SaaS clusters (Algolia, Coveo, Elasticsearch). However, NavERP adheres to standard Django ORM with PostgreSQL/SQLite compatibility. Sub-module 9.7 designs an elegant, high-performance in-database search engine:
   - Case-insensitive multi-field search across product `name`, `brand`, `short_description`, `meta_title`, and variant `sku`.
   - Synonym query expansion (evaluating `SearchSynonym` rules before query execution).
   - Merchandising rule application (intercepting queries for redirects, pins, score boosting, or buries).
   - Dynamic facet aggregation (computing counts per category, brand, and price bracket).
   - Pre-engineered for future full-text / pgvector search extensions without schema disruption.
4. **Multi-Tenancy & Isolation**:
   All search configurations, synonym dictionaries, facet definitions, merchandising rules, and query logs are strictly partitioned by `tenant` (`core.Tenant`). Synonyms and boost rules defined in Workspace A never influence search results in Workspace B.

---

## 2. Repo State Checked First

### 2.1 Navigation & App Tree State
- **`apps/core/navigation.py`:**
  - `"9.1"` is live: Product Information Management, Category Hierarchy, Product Variants, Bulk Import/Export, Product Relationships, Catalog Overview.
  - `"9.2"` is live: Real-Time Stock Tracking, Warehouse & Fulfillment Center Management, Stock Transfers & Adjustments, Backorder & Pre-Order Management, Multi-Channel Inventory Sync, Inventory Operations Console.
  - `"9.3"` is live: Dynamic Price Rules, Discount & Coupon Management, Flash Sales, Loyalty & Rewards Pricing, Competitor Price Monitoring.
  - `"9.4"` is live: Persistent & Guest Cart, One-Page & Multi-Step Checkout, Shipping Rate Calculation, Tax Calculation, Payment Method Orchestration.
  - `"9.5"` is live: Order Capture & Validation, Order Routing & Splitting, Order Status & Tracking, Order Modifications & Cancellations, Returns & Exchanges (RMA).
  - `"9.6"` is live: Customer Account Profile, Address Preferences, Customer Wishlists, Customer Privacy Requests.
  - Sub-module `"9.7"` currently has no `LIVE_LINKS` entries yet.
- **`apps/ecommerce/` package structure:**
  - Sub-module 9.7 will add package subdirectories: `SearchDiscovery/` across `models/`, `forms/`, `views/`, `urls/`, and `templates/ecommerce/searchdiscovery/`.

### 2.2 As-Built Core Spine Entities (Grep Verified)
| Entity | Location | Status | 9.7 Usage |
|---|---|---|---|
| `core.Tenant` | `apps/core/models/Tenant.py:17` | **Present** | Workspace multi-tenant isolation |
| `core.Party` | `apps/core/models/Party.py:5` | **Present** | Optional shopper identity in search query telemetry |
| `accounts.User` | `apps/accounts/models/User.py:14` | **Present** | Authenticated user auditing & telemetry |
| `ecommerce.CatalogProduct` | `apps/ecommerce/models/ProductCatalog/CatalogProducts.py:8` | **Present** | Target searchable catalog entity, boost/pin/bury target |
| `ecommerce.ProductVariant` | `apps/ecommerce/models/ProductCatalog/ProductVariants.py:10` | **Present** | SKU matching, option values (Size, Color), price facets |
| `ecommerce.StoreCategory` | `apps/ecommerce/models/ProductCatalog/StoreCategories.py:7` | **Present** | Category-scoped facets, category browse merchandising, redirects |
| `scm.Item` | `apps/scm/models/ItemMaster/Items.py` | **Present** | Canonical item anchor behind catalog products |

### 2.3 Prefix Collision Verification
All candidate prefixes checked across all models in the repository via `git grep -E '\b(ESYM|ESFC|ESMR|ESQL)\b'`:
- `ESYM` — `SearchSynonym` (**Verified 100% FREE**)
- `ESFC` — `SearchFacetConfig` (**Verified 100% FREE**)
- `ESMR` — `SearchMerchandisingRule` (**Verified 100% FREE**)
- `ESQL` — `SearchQueryLog` (**Verified 100% FREE**)

---

## 3. Commercial Market Leaders Surveyed

### 1. Algolia (Algolia Search, Autocomplete & Merchandising Studio)
- **Positioning**: Global gold-standard API-first search and product discovery engine powering leading retailers (Gymshark, Decathlon, Under Armour, Lacoste).
- **Reference**: https://www.algolia.com/products/search-and-discovery/hosted-search-api/, https://www.algolia.com/doc/guides/managing-results/rules/merchandising-and-promoting/
- **Key Capabilities**:
  - **Autocomplete (Search-as-you-Type)**: Sub-50ms instant query suggestions combining predicted search phrases, direct product matches with thumbnails/prices, and matching category links.
  - **Typo Tolerance & NLP**: Automatic phonetic, Damerau-Levenshtein typo correction, and token decomposition.
  - **Synonym Types**: Two-way equivalent synonyms (`sneakers = trainers`), one-way directional synonyms (`tablet -> ipad`), and replacement terms (`adidass -> adidas`).
  - **Merchandising Rules (Visual Merchandising Studio)**: Condition-consequence engine allowing merchandisers to pin products to fixed positions, boost high-margin items, bury out-of-stock items, or inject promotional banners based on search queries or category browse contexts.
  - **Dynamic Faceting**: Disjunctive (OR) facet logic for attributes like brand or size, coupled with contextual facet ordering so relevant filters bubble up automatically.

### 2. Coveo (Coveo for Commerce)
- **Positioning**: Tier-1 enterprise AI relevance and product discovery platform powering global retailers and distributors (Uncapped, Trek Bikes, Skullcandy).
- **Reference**: https://www.coveo.com/en/solutions/ecommerce, https://docs.coveo.com/en/commerce/
- **Key Capabilities**:
  - **Dynamic Navigation Experience (DNE)**: Machine-learned facet extraction and dynamic ordering per query intent (e.g. prioritizing "RAM" and "Screen Size" for laptops, but "Shoe Size" and "Color" for footwear).
  - **Coveo Merchandising Hub**: Visual drag-and-drop merchandising console to pin, boost, bury, or lock products into search and listing grids.
  - **Query Suggestions with Revenue Weighting**: Real-time autocomplete suggestions ranked by past conversion rates and revenue-per-search.
  - **Search Telemetry & Null-Result Intelligence**: Comprehensive tracking of zero-result searches, low-click queries, and query performance reporting.

### 3. Bloomreach Discovery
- **Positioning**: Market-leading commerce experience cloud providing AI search, merchandising, and 1:1 personalization (Albertsons, Bosch, Puma, Staples).
- **Reference**: https://www.bloomreach.com/en/products/discovery, https://documentation.bloomreach.com/discovery/docs/merchandising
- **Key Capabilities**:
  - **Semantic Vector & Keyword Search (Loomi AI)**: Hybrid retrieval combining keyword recall with semantic intent understanding.
  - **Merchandising Actions**: Lock (pin to absolute rank), Boost (elevate relative score), Bury (suppress rank), and Block (completely remove SKU from query results).
  - **Automated & Manual Synonyms**: Merchandiser-curated synonym dictionaries coupled with behavioral synonym discovery mined from search clickstreams.
  - **Campaign Query Redirects**: Merchandiser ability to redirect search queries (e.g. "order tracking", "return policy", "black friday") directly to dedicated CMS pages or category landing pages.

### 4. Constructor.io
- **Positioning**: Silicon Valley AI product discovery platform purpose-built for enterprise B2C eCommerce (Target Australia, Sephora, Birkenstock, Petco).
- **Reference**: https://constructor.io/, https://docs.constructor.io/
- **Key Capabilities**:
  - **Revenue-Optimized Behavioral Ranking**: Search ranking algorithms optimized for Gross Merchandise Value (GMV), conversion rate, and revenue-per-visitor rather than purely textual matching.
  - **Dynamic Facet Prioritization**: Automatically surfaces and reorders filter attributes based on live aggregate shopper interaction data.
  - **Automated Synonym & Misspelling Correction**: Self-learning natural language processing that catches vocabulary mismatches without endless manual synonym maintenance.
  - **Personalized Browse Grids**: Category landing pages dynamically sorted by individual shopper intent and category popularity trends.

### 5. Searchspring (Athos Commerce)
- **Positioning**: Premier site search, navigation, and visual merchandising solution widely adopted across mid-market and enterprise eCommerce (Chubbies, Moen, Volcom, Wildfang).
- **Reference**: https://searchspring.com/, https://support.searchspring.net/hc/en-us
- **Key Capabilities**:
  - **Visual Merchandising Console**: Drag-and-drop grid interface allowing merchants to manually position products on search and category pages.
  - **Boost & Bury Campaign Scheduling**: Date-bounded rules that automatically promote holiday products or bury end-of-season items during active dates.
  - **Granular Facet Configuration**: Full control over facet widget types (checkboxes, color swatches, price sliders, rating stars), multi-select OR/AND logic, and collapse thresholds.
  - **Actionable Insights & Zero-Result Reports**: Granular dashboards highlighting top searches, zero-result searches, and keyword redirects.

### 6. Klevu (Athos Commerce)
- **Positioning**: Leading Finnish AI search and discovery platform specializing in natural language processing (NLP), vector search, and headless storefronts (Flying Tiger Copenhagen, O'Neills).
- **Reference**: https://www.klevu.com/, https://help.klevu.com/
- **Key Capabilities**:
  - **Smart Search Overlay & Instant Autocomplete**: Rich popup overlay appearing on keystroke showing trending searches, recent searches, popular categories, and top matching products.
  - **Self-Learning Query NLP**: Automatic entity extraction detecting brands, colors, genders, and price limits directly from conversational search strings ("black running shoes under $100").
  - **Visual & Keyword Merchandising**: Rule-based product boosting combined with automated conversion-based ranking.

### 7. Yext (Search Experience)
- **Positioning**: Knowledge-graph and natural language search platform powering enterprise search experiences (Samsung, Subway, Campbell's).
- **Reference**: https://www.yext.com/products/search
- **Key Capabilities**:
  - **Knowledge Graph Entity Search**: Deconstructs search queries into structured entity attributes rather than raw string matching.
  - **Multi-Hop Semantic Faceting**: Discovers relationships across categories, brands, and specifications to dynamically populate facet filters.
  - **Search Query Analytics**: Deep telemetry on search frequency, click-through rates, session exit rates, and query conversion funnels.
  - **Synonym & Query Redirect Management**: Centralized management of synonyms, abbreviations, and explicit landing page redirects.

### 8. Nosto (Search & Product Discovery)
- **Positioning**: Unified commerce intelligence platform integrating site search, visual merchandising, and product recommendations (Paul Smith, Helly Hansen, Dermalogica).
- **Reference**: https://www.nosto.com/products/search/, https://support.nosto.com/
- **Key Capabilities**:
  - **Unified Experience Engine**: Seamlessly coordinates search results, category browse pages, and personalized recommendations under one catalog model.
  - **Inventory-Aware Merchandising**: Automatically deprioritizes or buries products with low stock or broken size runs, while boosting high-margin, well-stocked items.
  - **Personalized Category Navigation**: Tailors facet visibility and default product sorting according to customer browsing history and affinity.

### 9. ViSenze & Syte (Visual Search & Multimodal Product Discovery)
- **Positioning**: Specialized visual AI and computer vision platforms for retail and fashion (Rakuten, ASOS, Prada, Farfetch, Wayfair).
- **Reference**: https://www.visenze.com/, https://www.syte.ai/
- **Key Capabilities**:
  - **Image-Based Search**: Shoppers upload a photo or screenshot to find exact or visually similar products based on color, pattern, shape, and silhouette.
  - **"Shop the Look" & Complementary Recommendations**: Computer vision analyzes a photo of a model wearing an outfit, isolates individual items (jacket, pants, shoes), and recommends matching catalog SKUs.
  - **Zero-Result Visual Fallback**: When text searches return no exact keywords, the visual discovery engine surfaces visually similar items from the closest category.

---

## 4. Feature Catalog (Sub-module 9.7 only)

### 4.1 Site Search & Autocomplete
- **Typo-Tolerant Catalog Search** — Search execution engine matching shopper queries against product name, brand, short description, meta title, and variant SKUs with error tolerance and word stemming.
  - *Seen in:* Algolia, Coveo, Bloomreach, Klevu
  - *Priority:* `table-stakes`
  - *Spine:* Queries `ecommerce.CatalogProduct` and `ecommerce.ProductVariant`
  - *Status:* Buildable now
- **Predictive Autocomplete Dropdown ("Search-as-you-Type")** — Instant suggestion endpoint returning top matching product suggestions, top brand matches, and suggested category links as the user types.
  - *Seen in:* Algolia (Autocomplete.js), Klevu, Searchspring, Coveo
  - *Priority:* `table-stakes`
  - *Spine:* Dedicated JSON autocomplete endpoint querying active products & categories
  - *Status:* Buildable now
- **Trending & Historical Query Suggestions** — Autocomplete dropdown displays popular past queries and trending keywords mined from `SearchQueryLog`.
  - *Seen in:* Algolia (Query Suggestions), Coveo, Constructor.io
  - *Priority:* `common`
  - *Spine:* Reads aggregated top queries from `SearchQueryLog`
  - *Status:* Buildable now
- **Zero-Result Graceful Fallback** — When a search term produces 0 exact matches, the system suggests alternative queries, expands terms via partial matches, or highlights featured catalog items instead of showing a blank screen.
  - *Seen in:* Bloomreach, Constructor.io, Searchspring
  - *Priority:* `table-stakes`
  - *Spine:* Fallback query evaluation logic in search view
  - *Status:* Buildable now

### 4.2 Faceted Search & Filtering
- **Dynamic Multi-Attribute Facet Filtering** — Configurable facet sidebar enabling shoppers to filter catalog results by Category, Brand, Price, Product Options (Size, Color), Rating, and Stock Availability.
  - *Seen in:* Algolia, Bloomreach, Searchspring, Coveo
  - *Priority:* `table-stakes`
  - *Spine:* Governed by `SearchFacetConfig` (`ESFC-`)
  - *Status:* Buildable now
- **Disjunctive (OR) vs. Conjunctive (AND) Facet Logic** — Allows multiple selections within the same facet (e.g. Brand = "Nike" OR "Adidas") while applying AND logic across different facets (Brand = Nike AND Size = Medium).
  - *Seen in:* Algolia, Searchspring, Coveo
  - *Priority:* `table-stakes`
  - *Spine:* Execution logic in search query builder
  - *Status:* Buildable now
- **Price Range Filter & Sliders** — Dynamic calculation of minimum and maximum catalog prices for the current result set with min/max input fields and range sliders.
  - *Seen in:* Shopify, Searchspring, Algolia, Adobe Commerce
  - *Priority:* `table-stakes`
  - *Spine:* Aggregate min/max computation over `ProductVariant.price`
  - *Status:* Buildable now
- **Visual Facet Widgets (Color Swatches & Star Ratings)** — Specialized facet rendering for visual attributes (color swatch buttons, rating star selectors, checkboxes, and boolean toggles).
  - *Seen in:* Searchspring, Algolia InstantSearch, Nosto
  - *Priority:* `common`
  - *Spine:* Field `widget_type` in `SearchFacetConfig`
  - *Status:* Buildable now
- **Category-Scoped Facets** — Ability to restrict specific facets to relevant categories only (e.g. "Screen Size" only displays under Electronics; "Shoe Size" only under Footwear).
  - *Seen in:* Coveo (Dynamic Navigation), Bloomreach, Searchspring
  - *Priority:* `common`
  - *Spine:* Optional FK `category_scope` to `ecommerce.StoreCategory` in `SearchFacetConfig`
  - *Status:* Buildable now
- **Facet Ordering & Default Collapsed State** — Digital merchandiser control over the sequence of facet blocks on the page, with flags to keep secondary facets collapsed by default.
  - *Seen in:* Searchspring, Bloomreach, Algolia
  - *Priority:* `common`
  - *Spine:* Fields `display_order` and `is_collapsed_by_default` in `SearchFacetConfig`
  - *Status:* Buildable now

### 4.3 Visual Search & AI Recommendations
- **Visually Similar Product Matching (Style Matching)** — Discovers and presents catalog products sharing similar visual attributes (same category, primary color, brand, or style tag) on product detail pages and search results.
  - *Seen in:* ViSenze, Syte, Bloomreach
  - *Priority:* `common`
  - *Spine:* Multi-attribute heuristic matching over `CatalogProduct` and `ProductVariant.option_values`
  - *Status:* Buildable now (heuristic/attribute-based); deep CNN tensor matching flagged for deferred ML pass
- **Complementary Product Pairing ("Shop the Look")** — Curated or attribute-based recommendations suggesting accessories or complementary items that match the viewed product (e.g., matching belt for shoes).
  - *Seen in:* Syte, ViSenze, Nosto
  - *Priority:* `common`
  - *Spine:* Reuses `ecommerce.ProductRelationship` (type `accessory` / `cross_sell`, 9.1)
  - *Status:* Buildable now
- **Visual Search Fallback on Zero-Result Searches** — When a textual search query yields zero matches, the system surfaces top trending or visually similar products from the closest detected category.
  - *Seen in:* ViSenze, Syte, Klevu
  - *Priority:* `table-stakes`
  - *Spine:* Action handler in search view
  - *Status:* Buildable now
- **Image Upload / Multimodal Search Pipeline (Architecture Stand-in)** — Structured API endpoint and schema readiness for receiving an uploaded image or image URL to extract catalog matches.
  - *Seen in:* ViSenze, Syte, Google Cloud Retail Search
  - *Priority:* `differentiator`
  - *Spine:* Search view endpoint with image parameter support
  - *Status:* Buildable now (architecture stand-in); binary neural net inference deferred to external service

### 4.4 Search Analytics & Merchandising
- **Synonym Management (Two-Way, One-Way, Replacement)** — Comprehensive dictionary mapping synonyms so diverse shopper vocabularies land on the correct products without catalog data pollution.
  - *Seen in:* Algolia, Bloomreach, Coveo, Searchspring
  - *Priority:* `table-stakes`
  - *Spine:* New table `SearchSynonym` (`ESYM-`)
  - *Status:* Buildable now
- **Curated Search Result Boosting & Demoting (Boost / Bury Rules)** — Merchandiser rules that adjust product relevance scores (+/- weight) for specific search queries or globally across the catalog.
  - *Seen in:* Algolia, Coveo, Bloomreach, Searchspring, Nosto
  - *Priority:* `table-stakes`
  - *Spine:* New table `SearchMerchandisingRule` (`ESMR-`)
  - *Status:* Buildable now
- **Slot Pinning / Locking (Fixed Rank Merchandising)** — Merchandisers can force a specific hero product to appear at an exact position (e.g. Slot 1 or Slot 2) for high-intent search queries.
  - *Seen in:* Algolia (Pinning), Coveo, Bloomreach (Locking), Searchspring
  - *Priority:* `table-stakes`
  - *Spine:* Field `pin_position` in `SearchMerchandisingRule` (`ESMR-`)
  - *Status:* Buildable now
- **Product Blocking / Exclusion** — Merchandiser ability to completely hide or exclude specific SKUs from query results (e.g. hide refurbished items when searching for "new flagship").
  - *Seen in:* Bloomreach (Block), Searchspring, Algolia
  - *Priority:* `common`
  - *Spine:* Action `block` in `SearchMerchandisingRule` (`ESMR-`)
  - *Status:* Buildable now
- **High-Intent Query URL Redirects** — Automatic redirection of high-intent keywords (e.g. "gift card", "shipping policy", "customer service", "black friday") directly to dedicated pages.
  - *Seen in:* Bloomreach, Searchspring, Algolia, Coveo, Yext
  - *Priority:* `table-stakes`
  - *Spine:* Action `redirect` and `redirect_url` in `SearchMerchandisingRule` (`ESMR-`)
  - *Status:* Buildable now
- **Promotional In-Grid Banners** — Ability to inject custom marketing banners (image, heading, promo copy, click URL) directly into search results or category browse grids.
  - *Seen in:* Algolia, Coveo, Searchspring
  - *Priority:* `common`
  - *Spine:* Action `banner` and banner fields in `SearchMerchandisingRule` (`ESMR-`)
  - *Status:* Buildable now
- **Search Query Telemetry & Null-Result Tracking** — Real-time logging of search queries capturing query terms, result counts, execution time (ms), applied filters, clicked products, and zero-result markers.
  - *Seen in:* Algolia, Coveo, Searchspring, Yext
  - *Priority:* `table-stakes`
  - *Spine:* New table `SearchQueryLog` (`ESQL-`)
  - *Status:* Buildable now
- **Search Analytics Dashboard** — Reporting console aggregating total searches, zero-result search rate, top searched terms, and low-converting queries to guide catalog purchasing and merchandising decisions.
  - *Seen in:* Algolia, Searchspring, Coveo
  - *Priority:* `table-stakes`
  - *Spine:* Analytics aggregation view querying `SearchQueryLog`
  - *Status:* Buildable now

### 4.5 Personalized Browse Experience
- **Behavioral Sorting & Sort Overrides** — Storefront sorting options: Best Match / Relevance, Price (Low to High), Price (High to Low), Newest Arrivals, Product Name (A-Z), and Top Rated.
  - *Seen in:* Shopify, Adobe Commerce, BigCommerce, Bloomreach
  - *Priority:* `table-stakes`
  - *Spine:* Query parameter sorting on search and category views
  - *Status:* Buildable now
- **Category Browse Merchandising** — Applying merchandising rules to category listing pages (PLPs), enabling category-specific pinning, boosting, and banner injections.
  - *Seen in:* Searchspring, Bloomreach, Algolia Merchandising Studio
  - *Priority:* `common`
  - *Spine:* Supported via `target_category` in `SearchMerchandisingRule` (`ESMR-`)
  - *Status:* Buildable now
- **Recently Viewed Products Tracker** — Client-side / session-based memory of recently inspected products, displayed at the bottom of search and category listing pages.
  - *Seen in:* Amazon, Shopify, Adobe Commerce, Klevu
  - *Priority:* `common`
  - *Spine:* Session / cookie-backed product list referencing `ecommerce.CatalogProduct`
  - *Status:* Buildable now
- **Context-Aware Category Landing Page Headers** — Rich category headers with custom merchandising banners, active filter breadcrumbs, and sub-category pills.
  - *Seen in:* Bloomreach, Constructor.io, Searchspring
  - *Priority:* `common`
  - *Spine:* Storefront template integration using `StoreCategory` and `SearchMerchandisingRule`
  - *Status:* Buildable now

### 4.6 Beyond the Bullets (High-Value Market Additions)
- **Time-Bounded Merchandising Campaigns** — Merchandising rules with start and end timestamps, automatically activating for promotional windows (e.g. Cyber Monday, Valentine's Day) and deactivating without manual intervention.
  - *Seen in:* Searchspring, Bloomreach, Coveo
  - *Priority:* `common`
  - *Spine:* `start_date` and `end_date` on `SearchMerchandisingRule`
  - *Status:* Buildable now
- **Synonym Hit Telemetry** — Tracking rule usage frequency directly on `SearchSynonym` to identify which synonyms are actively utilized by shoppers.
  - *Seen in:* Algolia, Coveo
  - *Priority:* `common`
  - *Spine:* Counter field on `SearchSynonym`
  - *Status:* Buildable now

---

## 5. Recommended Build Scope (This Pass — Exactly 4 Models)

To deliver a comprehensive, enterprise-grade search and product discovery suite for Sub-module 9.7 that fulfills all NavERP.md feature bullets without database bloat, we recommend **exactly 4 tenant-scoped models** organized under `apps/ecommerce/models/SearchDiscovery/`:

```
apps/ecommerce/models/SearchDiscovery/
├── __init__.py
├── SearchSynonyms.py           # Model 1: SearchSynonym [ESYM]
├── SearchFacetConfigs.py        # Model 2: SearchFacetConfig [ESFC]
├── SearchMerchandisingRules.py  # Model 3: SearchMerchandisingRule [ESMR]
└── SearchQueryLogs.py           # Model 4: SearchQueryLog [ESQL]
```

### Model 1: `SearchSynonym` [Prefix: `ESYM`]
- **Purpose**: Dictionary of query expansions, directional mappings, and typo replacements that bridge the vocabulary gap between how shoppers search and how products are described in the catalog.
- **Inherits**: `TenantNumbered` (`apps/ecommerce/models/_base.py`)
- **Fields & Choices**:
  - `tenant` (FK `core.Tenant`, on_delete=CASCADE)
  - `number` (CharField, `ESYM-XXXXX`, auto-generated)
  - `name` (CharField, max_length=120, help_text="Administrative label for this synonym rule")
  - `synonym_type` (CharField, max_length=20, choices: `two_way`, `one_way`, `replacement`, default `two_way`)
    - `two_way`: Equivalent terms (e.g. "sofa", "couch", "davenport" all return results for any term).
    - `one_way`: Directional mapping (e.g. searching for "footwear" returns "sneakers", "boots", "loafers", but searching for "boots" does not return sneakers).
    - `replacement`: Explicit substitution (e.g. correcting "sammsung" -> "samsung" or "tshirt" -> "t-shirt").
  - `root_term` (CharField, max_length=120, help_text="Root trigger keyword for one-way and replacement rules; primary anchor for two-way")
  - `synonyms` (TextField, help_text="Comma-separated list of synonym terms, e.g. 'couch, sofa, settee'")
  - `is_active` (BooleanField, default=True)
  - `hit_count` (PositiveIntegerField, default=0, help_text="Times this synonym rule has expanded a search query")
  - `notes` (TextField, blank=True)
- **Constraints & Indexes**:
  - Unique constraint on `["tenant", "number"]`
  - Index on `["tenant", "is_active", "synonym_type"]`
  - Index on `["tenant", "root_term"]`
- **Verified FKs**: `core.Tenant`.

### Model 2: `SearchFacetConfig` [Prefix: `ESFC`]
- **Purpose**: Governs dynamic faceted navigation and sidebar filters across search result pages and category listings. Configures which attributes appear as filters, widget visualization styles, selection logic, and category scoping.
- **Inherits**: `TenantNumbered` (`apps/ecommerce/models/_base.py`)
- **Fields & Choices**:
  - `tenant` (FK `core.Tenant`, on_delete=CASCADE)
  - `number` (CharField, `ESFC-XXXXX`, auto-generated)
  - `name` (CharField, max_length=100, help_text="Storefront display heading, e.g. 'Brand', 'Color', 'Price'")
  - `code` (CharField, max_length=50, help_text="Machine identifier, e.g. 'brand', 'price', 'category', 'color', 'size', 'in_stock'")
  - `source_type` (CharField, max_length=30, choices: `category`, `brand`, `price`, `variant_option`, `availability`, `rating`, `tag`, default `brand`)
  - `option_key` (CharField, max_length=50, blank=True, help_text="Key in ProductVariant.option_values (e.g. 'Size', 'Color') when source_type='variant_option'")
  - `widget_type` (CharField, max_length=20, choices: `checkbox`, `color_swatch`, `price_slider`, `rating_stars`, `toggle`, `dropdown`, default `checkbox`)
  - `filter_logic` (CharField, max_length=15, choices: `disjunctive`, `conjunctive`, default `disjunctive`, help_text="Disjunctive (OR) allows multi-select within facet; Conjunctive (AND) requires all selected values")
  - `display_order` (PositiveIntegerField, default=0, help_text="Sidebar vertical presentation order")
  - `is_collapsed_by_default` (BooleanField, default=False)
  - `max_values_shown` (PositiveIntegerField, default=10, help_text="Max filter items displayed before 'Show More' toggle")
  - `is_searchable` (BooleanField, default=False, help_text="Show in-facet search box for facets with 10+ values like Brands")
  - `category_scope` (FK `ecommerce.StoreCategory`, on_delete=SET_NULL, null=True, blank=True, related_name="scoped_facets", help_text="Optional: Restrict this filter to a specific category hierarchy")
  - `is_active` (BooleanField, default=True)
- **Constraints & Indexes**:
  - Unique constraint on `["tenant", "number"]`
  - Unique constraint on `["tenant", "code", "category_scope"]`
  - Index on `["tenant", "is_active", "display_order"]`
- **Verified FKs**: `core.Tenant`, `ecommerce.StoreCategory`.

### Model 3: `SearchMerchandisingRule` [Prefix: `ESMR`]
- **Purpose**: Merchandising studio rules controlling catalog presentation on search results and category browse listings. Enables merchandisers to curate product placement, boost scores, pin products into top slots, bury low-inventory items, block products, inject promotional banners, or redirect queries to dedicated campaign URLs.
- **Inherits**: `TenantNumbered` (`apps/ecommerce/models/_base.py`)
- **Fields & Choices**:
  - `tenant` (FK `core.Tenant`, on_delete=CASCADE)
  - `number` (CharField, `ESMR-XXXXX`, auto-generated)
  - `name` (CharField, max_length=150, help_text="Rule description, e.g. 'Pin Air Max on Sneakers Query'")
  - `rule_type` (CharField, max_length=20, choices: `query`, `category`, `global`, default `query`)
  - `trigger_query` (CharField, max_length=200, blank=True, help_text="Target search query string when rule_type='query'")
  - `match_type` (CharField, max_length=20, choices: `exact`, `contains`, `starts_with`, default `exact`)
  - `target_category` (FK `ecommerce.StoreCategory`, on_delete=SET_NULL, null=True, blank=True, related_name="merchandising_rules", help_text="Target category listing when rule_type='category'")
  - `action_type` (CharField, max_length=20, choices: `boost`, `bury`, `pin`, `block`, `redirect`, `banner`, default `boost`)
  - `boosted_product` (FK `ecommerce.CatalogProduct`, on_delete=CASCADE, null=True, blank=True, related_name="merchandising_rules", help_text="Target product for boost, bury, pin, or block actions")
  - `boost_weight` (IntegerField, default=10, help_text="Relevance score modifier (-100 to +100). Positive boosts; negative buries")
  - `pin_position` (PositiveIntegerField, null=True, blank=True, help_text="Fixed 1-indexed rank position (1=Slot 1, 2=Slot 2) when action_type='pin'")
  - `redirect_url` (CharField, max_length=255, blank=True, help_text="Target URL when action_type='redirect'")
  - `banner_title` (CharField, max_length=150, blank=True, help_text="Promotional banner heading when action_type='banner'")
  - `banner_body` (TextField, blank=True, help_text="Promotional banner body text / discount copy")
  - `banner_image_url` (URLField, blank=True, help_text="Promotional banner background or artwork image")
  - `banner_link_url` (CharField, max_length=255, blank=True, help_text="Click destination for banner")
  - `priority` (PositiveIntegerField, default=10, help_text="Evaluation priority (higher number evaluated first)")
  - `start_date` (DateTimeField, null=True, blank=True, help_text="Optional campaign start time")
  - `end_date` (DateTimeField, null=True, blank=True, help_text="Optional campaign end time")
  - `is_active` (BooleanField, default=True)
- **Constraints & Indexes**:
  - Unique constraint on `["tenant", "number"]`
  - Index on `["tenant", "is_active", "rule_type"]`
  - Index on `["tenant", "trigger_query"]`
- **Verified FKs**: `core.Tenant`, `ecommerce.StoreCategory`, `ecommerce.CatalogProduct`.

### Model 4: `SearchQueryLog` [Prefix: `ESQL`]
- **Purpose**: Search analytics and discovery telemetry tracking executed shopper searches, hit counts, latency, zero-result flags, applied filters, and product click events. Provides the data foundation for null-result reporting and merchandising insights.
- **Inherits**: `TenantNumbered` (`apps/ecommerce/models/_base.py`)
- **Fields & Choices**:
  - `tenant` (FK `core.Tenant`, on_delete=CASCADE)
  - `number` (CharField, `ESQL-XXXXX`, auto-generated)
  - `query_text` (CharField, max_length=255, db_index=True, help_text="Raw search query string entered by shopper")
  - `normalized_query` (CharField, max_length=255, db_index=True, help_text="Cleaned, lowercase, stripped search term for grouping")
  - `results_count` (PositiveIntegerField, default=0, help_text="Count of matching products returned")
  - `is_zero_result` (BooleanField, default=False, db_index=True, help_text="True if search returned 0 items (null-result)")
  - `execution_time_ms` (PositiveIntegerField, default=0, help_text="Search latency in milliseconds")
  - `applied_filters` (JSONField, default=dict, blank=True, help_text="Dictionary of facet filters applied during query")
  - `sort_order` (CharField, max_length=30, default="relevance", help_text="Active sort order selected (e.g. relevance, price_asc, newest)")
  - `redirected_to` (CharField, max_length=255, blank=True, help_text="Destination URL if intercepted by redirect rule")
  - `clicked_product` (FK `ecommerce.CatalogProduct`, on_delete=SET_NULL, null=True, blank=True, related_name="search_clicks", help_text="First product clicked by shopper from search results")
  - `click_position` (PositiveIntegerField, null=True, blank=True, help_text="1-indexed rank position of clicked product")
  - `session_key` (CharField, max_length=64, blank=True, db_index=True, help_text="Shopper session key for anonymous attribution")
  - `customer` (FK `core.Party`, on_delete=SET_NULL, null=True, blank=True, related_name="ecommerce_search_logs", help_text="Shopper party record if authenticated")
  - `ip_address` (GenericIPAddressField, null=True, blank=True)
- **Constraints & Indexes**:
  - Unique constraint on `["tenant", "number"]`
  - Index on `["tenant", "is_zero_result", "-created_at"]`
  - Index on `["tenant", "normalized_query"]`
  - Index on `["tenant", "-created_at"]`
- **Verified FKs**: `core.Tenant`, `ecommerce.CatalogProduct`, `core.Party`.

---

## 6. Belongs to Sibling Sub-modules (Parked, Not Scoped Here)

- **9.1 Product Information Management (PIM)**: Catalog products, variants, category hierarchies, product relationships. *(Built)*
- **9.2 Inventory & Stock Management**: Real-time stock counts, fulfillment center routing, backorders. *(Built)*
- **9.3 Pricing & Promotion Engine**: Price calculation, discount coupons, flash sales, price matching. *(Built)*
- **9.4 Shopping Cart & Checkout**: Cart calculation, checkout orchestration, payment methods. *(Built)*
- **9.5 Order Management System (OMS)**: Order capture, fulfillment splitting, RMAs. *(Built)*
- **9.6 Customer Account & Profile**: Shopper profiles, address preferences, wishlists, GDPR DSAR requests. *(Built)*
- **9.8 Personalization & Recommendation Engine**: Real-time intent scoring, collaborative filtering, dynamic homepage hero banners, customer RFM segmentation cohorts. *(Sibling 9.8)*
- **9.9 Content Management System (CMS)**: Visual page builder, blog/editorial articles, media library asset management, promotional landing pages. *(Sibling 9.9)*
- **9.10 Marketing & Campaign Management**: Automated marketing email journeys, SMS broadcasts. *(Sibling 9.10)*
- **9.13 Reviews & User-Generated Content**: Verified buyer reviews, star rating submissions, user photo uploads. *(Sibling 9.13)*

---

## 7. Deferred (Later Passes / External Integrations)

- **External Search Cluster Connectors (OpenSearch, Elasticsearch, Algolia SaaS)**: The 4-model architecture provides a complete, self-contained Django ORM search engine. Direct webhook sync to external SaaS clusters is deferred to an enterprise integration pass.
- **Deep Computer Vision CNN / CLIP Neural Networks**: Real-time image tensor embedding extraction for image-to-image reverse visual search is architected through the visual matching heuristic and search endpoints, but binary inference hardware (Torch/ONNX runtime) is deferred.
- **Vector Database Storage (`pgvector` / Pinecone)**: Multi-modal embedding similarity vector indexes for hybrid lexical-semantic retrieval can overlay the `SearchQueryLog` and `CatalogProduct` tables in a future AI infrastructure pass.
- **Automated Clickstream Synonym NLP Discovery**: Automatic unsupervised clustering of zero-result queries to clicked products is deferred to Sub-module 9.8's machine learning pipelines.
