# Research — Sub-module 9.8: Personalization & Recommendation Engine (Module 9 — eCommerce Management System, `ecommerce`)

- **Sub-module:** 9.8 Personalization & Recommendation Engine
- **Module:** 9 eCommerce Management System
- **Target app:** `apps/ecommerce` (extending the app created in 9.1 and extended in 9.2, 9.3, 9.4, 9.5, 9.6, and 9.7)
- **Research date:** 2026-10-30
- **Phase:** 1 Research only
- **Output boundary:** `.claude/tasks/research-ecommerce-9.8.md` only

---

## 1. Executive Summary & Domain Architecture

Sub-module 9.8 delivers the **Real-Time Behavioral Tracking, RFM & Audience Segmentation, Multi-Algorithm Recommendation Engine, Dynamic Hero/Content Personalization, and Omnichannel Lifecycle Trigger System** for the NavERP eCommerce platform.

In modern high-performance digital commerce (exemplified by Dynamic Yield by Mastercard, Nosto, Bloomreach Engagement/Discovery, Klaviyo, Algolia Recommend, Recombee, and Insider), generic "one-size-fits-all" storefronts are obsolete. Commercial benchmarks demonstrate:
- **Personalized product recommendations** drive between 20% to 31% of total digital commerce revenue.
- **Audience segmentation and RFM cohorting** allow merchants to distinguish VIP shoppers from at-risk or churned customers, generating 3x to 5x higher email and browse-trigger conversion rates.
- **Real-time clickstream behavioral capture** allows the commerce platform to deduce shopper affinities within 3 page clicks, dynamically adapting product grids, category recommendations, and promotional messaging.

### Architectural Boundary Rulings (L28, L29, L36, L37):
1. **Catalog & Cart Spine Integration (L36/L37)**:
   - Recommendations and merchandising target canonical **`ecommerce.CatalogProduct`** (`EPRD-`, 9.1) and **`ecommerce.ProductVariant`** (`PVR-`, 9.1).
   - Category-level affinities and dynamic ordering reuse **`ecommerce.StoreCategory`** (`ECAT-`, 9.1).
   - Abandoned cart triggers and upsells link directly to **`ecommerce.CartSession`** (`CART-`, 9.4) and order histories in **`ecommerce.SalesOrderCapture`** (`ORD-`, 9.5).
   - Customer identity and profile link directly to **`ecommerce.CustomerAccountProfile`** (`ECAP-`, 9.6) and unified Core Spine **`core.Party`** and **`accounts.User`**.
2. **Clear Sibling Boundaries (9.7 vs. 9.8 vs. 9.9 vs. 9.10)**:
   - **Sub-module 9.7 (Search & Discovery, shipped)**: Owns explicit search queries, autocomplete, faceted filtering, and search-query merchandising rules (boost, bury, pin, block, redirect).
   - **Sub-module 9.8 (This Pass)**: Owns shopper behavioral clickstream capture, intent scoring, dynamic RFM audience cohorts, algorithmic product recommendation strategies (collaborative, content-based, frequently bought together, trending, replenishment), and personalized campaign experiences (hero banners, browse/cart abandonment triggers).
   - **Sub-module 9.9 (CMS, sibling)**: Sibling sub-module that will own full-page blog articles, landing page layout grids, and static marketing page hierarchies. 9.8 provides dynamic personalized content blocks, not page builders.
   - **Sub-module 9.10 (Marketing Campaigns, sibling)**: Sibling sub-module that will own bulk email delivery queues and outbound affiliate attribution. 9.8 provides the trigger condition logic and segment membership.
3. **Multi-Tenancy & Data Isolation**:
   All behavioral logs, audience cohorts, recommendation strategies, and personalization campaigns are strictly scoped by `tenant` (`core.Tenant`). Cohorts and clickstream data from Tenant A never leak into or bias recommendations in Tenant B.
4. **Base Class & Prefix Discipline**:
   All 4 models inherit from `TenantNumbered` (`apps/ecommerce/models/_base.py`), providing `tenant` FK (`on_delete=CASCADE`), thread-safe auto-number generation, and timestamps.

---

## 2. Repo State Checked First

### 2.1 Navigation & App Tree State
- **`apps/core/navigation.py`:**
   - `"9.1"` is live: Product Catalog Management (`EPRD`, `PVR`, `ECAT`, `PREL`, `PRDIMG`, `PRDATTR`).
   - `"9.2"` is live: Inventory & Stock Management (`WHS`, `STKTRF`, `STKADJ`, `BORD`, `CHSYNC`).
   - `"9.3"` is live: Pricing & Promotion Engine (`DPR`, `COUP`, `FSAL`, `LOYP`, `CMPR`).
   - `"9.4"` is live: Shopping Cart & Checkout (`CART`, `CLINE`, `CHCK`, `SHPR`, `PAYO`).
   - `"9.5"` is live: Order Management System (`ORD`, `ORIT`, `ORUT`, `CHNG`, `RMA`).
   - `"9.6"` is live: Customer Account & Profile (`ECAP`, `ECAD`, `EWSH`, `EPRV`).
   - `"9.7"` is live: Search & Product Discovery (`ESYM`, `ESFC`, `ESMR`, `ESQL`).
   - Sub-module `"9.8"` currently has no `LIVE_LINKS` entries yet.
- **`apps/ecommerce/` package structure:**
   - Sub-module 9.8 will add package subdirectories: `Personalization/` across `models/`, `forms/`, `views/`, `urls/`, and `templates/ecommerce/personalization/`.

### 2.2 As-Built Core Spine Entities (Grep Verified)
| Entity | Location | Status | 9.8 Usage |
|---|---|---|---|
| `core.Tenant` | `apps/core/models/Tenant.py:17` | **Present** | Strict workspace tenant isolation |
| `core.Party` | `apps/core/models/Party.py:5` | **Present** | Unified shopper party identity |
| `accounts.User` | `apps/accounts/models/User.py:14` | **Present** | Authenticated shopper/admin identity |
| `ecommerce.CatalogProduct` | `apps/ecommerce/models/ProductCatalog/CatalogProducts.py:8` | **Present** | Target entity for recommendations and clickstream events |
| `ecommerce.ProductVariant` | `apps/ecommerce/models/ProductCatalog/ProductVariants.py:10` | **Present** | Variant-level SKU tracking and replenishment |
| `ecommerce.StoreCategory` | `apps/ecommerce/models/ProductCatalog/StoreCategories.py:7` | **Present** | Category affinity modeling and curated collections |
| `ecommerce.CartSession` | `apps/ecommerce/models/CartCheckout/CartSessions.py:10` | **Present** | Abandoned cart trigger target and cross-sell source |
| `ecommerce.SalesOrderCapture` | `apps/ecommerce/models/OrderManagement/SalesOrderCaptures.py:10` | **Present** | Order history analysis, RFM scoring, frequently-bought-together source |
| `ecommerce.CustomerAccountProfile` | `apps/ecommerce/models/CustomerAccount/CustomerAccountProfiles.py:9` | **Present** | Shopper profile anchor and lifecycle stage mapping |

### 2.3 Prefix Collision Verification
All candidate prefixes checked across all models in the repository via `git grep -E '\b(ESEG|EREC|EPEX|ESBE)\b'`:
- `ESEG` — `AudienceSegment` (**Verified 100% FREE**)
- `EREC` — `RecommendationStrategy` (**Verified 100% FREE**)
- `EPEX` — `PersonalizedExperience` (**Verified 100% FREE**)
- `ESBE` — `ShopperBehaviorEvent` (**Verified 100% FREE**)

---

## 3. Commercial Market Leaders Surveyed

### 1. Dynamic Yield by Mastercard (Experience OS)
- **Positioning**: Global enterprise personalization and decision engine powering McDonald's, Sephora, PacSun, and Lacoste.
- **Reference**: https://www.dynamicyield.com/experience-os/
- **Key Capabilities**:
  - **Dynamic Affinity Profiling**: Tracks real-time session interactions (product views, category clicks, price preferences, color selections) and calculates decay-weighted category/brand affinities.
  - **Omnichannel Recommendation Strategies**: Supports multi-model recommendations: "Similar Products" (content-based), "Users Also Bought" (collaborative), "Trending in Category" (popularity), and "Buy It Again" (replenishment intervals).
  - **Contextual Experience Engine**: Replaces homepage hero banners, promotional carousels, and category banners dynamically based on audience segment matches.
  - **Predictive Intent Scoring**: Flags shoppers showing high bounce likelihood vs. high purchase probability to adjust promotional discounts in real time.

### 2. Nosto (Commerce Experience Platform)
- **Positioning**: Leading mid-market and enterprise commerce personalization suite, widely used on Shopify Plus, Magento, and Salesforce Commerce Cloud.
- **Reference**: https://www.nosto.com/features/product-recommendations/
- **Key Capabilities**:
  - **Self-Learning Recommendation Algorithms**: 20+ specialized algorithms including "Frequently Bought Together" (association rule mining), "Top Sellers", "Recently Viewed", and "Order Again" replenishment widgets.
  - **Behavioral Onsite Triggers**: Intercepts browse abandonment and exit intent with personalized modal prompts and dynamic discount reminders.
  - **Customer Lifecycle Segmentation**: Automatically buckets shoppers into New Visitors, Returning Shoppers, Cart Abandoners, High-Value VIPs, and Inactive Churned accounts.
  - **Merchandising Fallbacks**: Configurable fallback strategies (e.g. falling back to top sellers if collaborative filtering yields fewer than 4 items).

### 3. Bloomreach Engagement (formerly Exponea) & Loomi AI
- **Positioning**: Enterprise Customer Data Platform (CDP) and intelligent marketing automation engine.
- **Reference**: https://www.bloomreach.com/en/products/engagement
- **Key Capabilities**:
  - **Unified Shopper Single Customer View (SCV)**: Merges anonymous session cookies with authenticated shopper profiles upon login or checkout.
  - **Automated Lifecycle Triggers**: Automated event-driven triggers: Abandoned Cart (sent after 1 hour), Browse Abandonment (viewed 3+ products in a category without carting), Price Drop Alert, and Back-in-Stock alerts.
  - **RFM Segmentation Matrix**: Computes Recency (days since last purchase), Frequency (lifetime order count), and Monetary (lifetime spend) scores (1 to 5) to cluster customers into 10 actionable tiers (Champions, Loyal Customers, Potential Loyalists, At Risk, Need Attention).
  - **Contextual Recommendation Filtering**: Allows merchants to filter recommendation outputs by inventory availability, category constraints, and margin thresholds.

### 4. Klaviyo (Lifecycle Marketing & Predictive Analytics)
- **Positioning**: The dominant eCommerce retention and trigger automation platform.
- **Reference**: https://www.klaviyo.com/features/predictive-analytics
- **Key Capabilities**:
  - **Event-Driven Behavioral Capture**: Standardized telemetry events: `Viewed Product`, `Added to Cart`, `Started Checkout`, `Placed Order`.
  - **Predictive Customer Lifetime Value (pCLV)**: Predicts next expected purchase date, churn probability, and historical vs. future CLV.
  - **Dynamic Product Feed Integration**: Dynamically populates automated messages with "Products you might also like" based on the shopper's most recently viewed category.

### 5. Algolia Recommend
- **Positioning**: API-first AI recommendation engine built atop Algolia's global edge search network.
- **Reference**: https://www.algolia.com/products/recommend/
- **Key Capabilities**:
  - **Related Products & Frequently Bought Together (FBT)**: Uses co-occurrence matrix factorization over order and cart event streams.
  - **Trending Items**: Computes popularity velocity over sliding time windows (last 24 hours, last 7 days).
  - **Merchandising Rules for Recommendations**: Ability to boost, bury, or filter recommended items based on catalog attributes (e.g., must be in stock, must be same gender/brand).

### 6. Recombee (AI Recommendation Engine as a Service)
- **Positioning**: Flexible machine-learning recommendation engine powering international eCommerce and media platforms.
- **Reference**: https://www.recombee.com/
- **Key Capabilities**:
  - **Hybrid Recommendation Pipelines**: Blends collaborative filtering (user-item interactions) with content-based filtering (product metadata similarities) to solve the cold-start problem for new products and new visitors.
  - **Real-Time Clickstream Ingestion**: Instantaneous profile updating upon each HTTP interaction.
  - **Scenario-Based Endpoints**: Different strategy configurations for Homepage Feed, PDP Cross-Sell, Cart Upsell, and Checkout Drawer.

---

## 4. Feature Catalog (Sub-module 9.8 Personalization & Recommendation Engine)

### 4.1 Behavioral Tracking & Profiles
- **Clickstream Event Capture** — Records real-time shopper actions: `page_view`, `product_view`, `category_view`, `search_query`, `cart_add`, `wishlist_add`, `checkout_start`, and `order_purchase` · seen in: Dynamic Yield, Bloomreach, Klaviyo · priority: `table-stakes` · spine: new model `ShopperBehaviorEvent` (`ESBE-`) linked to `core.Tenant`, optional `core.Party`/`User`, `ecommerce.CatalogProduct`, `ecommerce.StoreCategory` · buildable now.
- **Anonymous-to-Known Profile Unification** — Tracks anonymous shoppers via UUID `session_key`, automatically binding historical clickstream events to `core.Party` and `accounts.User` upon login or checkout · seen in: Bloomreach SCV, Klaviyo · priority: `table-stakes` · spine: `ShopperBehaviorEvent.session_key` + `customer_profile` · buildable now.
- **Category & Brand Affinity Scoring** — Aggregates interaction frequency and intent weight (e.g., viewing = 1 point, carting = 5 points, buying = 10 points) over a 30-day sliding window to calculate top affinity categories and brands · seen in: Dynamic Yield, Nosto · priority: `common` · spine: computed on demand or cached on `AudienceSegment`/workbench · buildable now.
- **Intent Velocity & Exit Intent** — Detects rapid sequential product views and cart abandonment precursors · seen in: Nosto, Dynamic Yield · priority: `differentiator` · spine: telemetry aggregation in `ShopperBehaviorEvent` · buildable now.

### 4.2 AI-Driven Product Recommendations
- **Multi-Strategy Recommendation Algorithms** — Configurable strategy rules supporting 7 distinct algorithms:
  1. `frequently_bought_together` (association rule mining on order items)
  2. `related_products` (content-based category/brand/attribute similarity)
  3. `collaborative_filtering` (shoppers who viewed/bought X also viewed/bought Y)
  4. `trending_popular` (top views/purchases in last N days)
  5. `recently_viewed` (shopper's own chronological view history)
  6. `replenishment` (consumable items due for repurchase based on elapsed cycle days)
  7. `hybrid` (weighted combination of content similarity and sales velocity)
  · seen in: Dynamic Yield, Nosto, Algolia Recommend, Recombee · priority: `table-stakes` · spine: new model `RecommendationStrategy` (`EREC-`) · buildable now.
- **Placement & Layout Contexts** — Dedicated placement locations: `pdp_related`, `cart_cross_sell`, `homepage_feed`, `category_trending`, `checkout_upsell`, `email_block` · seen in: Recombee, Algolia Recommend · priority: `table-stakes` · spine: `RecommendationStrategy.placement` · buildable now.
- **Merchandising Guardrails & Filters** — Configurable rules: `min_rating`, `only_in_stock`, `same_brand_only`, `exclude_viewed`, `price_bracket_modifier` (e.g., show items within +/- 30% of current item price) · seen in: Algolia, Nosto · priority: `common` · spine: `RecommendationStrategy` JSON/filter fields · buildable now.
- **Cold-Start Fallback Strategy** — Automatically falls back to site-wide trending or category best-sellers when personalized or collaborative history is sparse · seen in: Nosto, Bloomreach · priority: `table-stakes` · spine: `RecommendationStrategy.fallback_strategy` · buildable now.

### 4.3 Personalized Homepages & Content
- **Dynamic Personalized Experiences** — Rule-based campaigns delivering personalized hero banners, targeted promotional headlines, and curated collections per audience segment · seen in: Dynamic Yield Experience OS, Bloomreach · priority: `table-stakes` · spine: new model `PersonalizedExperience` (`EPEX-`) · buildable now.
- **Segment Targeting & Priority Arbitration** — Multiple experiences targeting overlapping segments evaluated by strict priority score (highest priority wins) · seen in: Dynamic Yield, Nosto · priority: `common` · spine: `PersonalizedExperience.priority` + `target_segment` · buildable now.
- **Curated Category & Collection Pinning** — Displays category shortcuts or featured collections matching the shopper's highest affinity category on the homepage · seen in: Nosto, Bloomreach · priority: `common` · spine: `PersonalizedExperience.target_category` / `target_product` · buildable now.
- **Active Campaign Scheduling** — Start and end timestamps allowing scheduled promotional personalization campaigns (e.g., Black Friday VIP early access) · seen in: Dynamic Yield · priority: `table-stakes` · spine: `PersonalizedExperience.start_date` / `end_date` · buildable now.

### 4.4 Email & Push Personalization (Lifecycle Triggers)
- **Automated Lifecycle Trigger Types** — Campaign triggers targeting key friction points in the customer journey:
  1. `cart_abandonment` (shopper has active items in cart with no checkout after N hours)
  2. `browse_abandonment` (shopper viewed 2+ items in a category without carting)
  3. `replenishment_reminder` (estimated repurchase window reached for recurring consumable products)
  4. `win_back` (lapsed high-value customer inactive for 60+ days)
  5. `welcome_series` (new shopper account onboarding with introductory voucher)
  · seen in: Klaviyo, Bloomreach Engagement, Nosto · priority: `table-stakes` · spine: `PersonalizedExperience.experience_type` (`trigger_*`) with `trigger_delay_hours` · buildable now.
- **Trigger Execution Telemetry & Conversion Tracking** — Tracks dispatch count, impressions, clicks, and recovered revenue attributed to personalized triggers · seen in: Klaviyo, Dynamic Yield · priority: `common` · spine: `PersonalizedExperience.impression_count`, `click_count`, `conversion_count` · buildable now.

### 4.5 Segmentation & Audience Builder
- **Dynamic Audience Cohorts** — Rules-based audience segmentation supporting automatic cohort assignment based on shopper attributes and order history · seen in: Bloomreach, Klaviyo · priority: `table-stakes` · spine: new model `AudienceSegment` (`ESEG-`) · buildable now.
- **RFM Analysis Engine** — Built-in Recency, Frequency, Monetary scoring:
  - `recency_days_max`: Days since last purchase (e.g. <= 30 for active, >= 90 for at-risk)
  - `min_order_count`: Lifetime order threshold (e.g. >= 5 for repeat, 1 for first-time)
  - `min_lifetime_spend`: Minimum total revenue contribution (e.g. >= $1,000 for VIP)
  · seen in: Bloomreach, Klaviyo, Dynamic Yield · priority: `table-stakes` · spine: `AudienceSegment` RFM fields · buildable now.
- **Lifecycle Stage Bucketing** — Standardized customer lifecycle stages: `new_visitor`, `first_time_buyer`, `active_repeat`, `high_value_vip`, `at_risk`, `churned_lapsed` · seen in: Bloomreach, Nosto · priority: `common` · spine: `AudienceSegment.lifecycle_stage` · buildable now.
- **Affinity Category Constraints** — Ability to restrict segments to customers showing strong affinity for specific catalog categories (e.g., "Electronics Aficionados", "Footwear Lovers") · seen in: Dynamic Yield, Bloomreach · priority: `common` · spine: `AudienceSegment.target_category` · buildable now.
- **Member Count & Auto-Recalculation** — Background or on-demand evaluation of matching shopper profiles with stored `cached_member_count` and last evaluated timestamp · seen in: Klaviyo, Bloomreach · priority: `table-stakes` · spine: `AudienceSegment.cached_member_count`, `last_evaluated_at` · buildable now.

---

## 5. Recommended Build Scope (This Pass: 4 Models + Workbench)

Sub-module 9.8 will implement exactly **4 tenant-scoped models** inheriting from `TenantNumbered`, plus a specialized **Personalization & Recommendation Workbench**:

### 1. `AudienceSegment` [Prefix: `ESEG-`] (`apps/ecommerce/models/Personalization/AudienceSegments.py`)
- **Purpose**: Defines dynamic shopper cohorts based on RFM scores, lifecycle stages, category affinities, and minimum spend rules.
- **Key Fields**:
  - `name`: `CharField(max_length=120)`
  - `code`: `CharField(max_length=60, db_index=True)`
  - `lifecycle_stage`: `CharField(max_length=30, choices=LIFECYCLE_STAGE_CHOICES, default="all")`
  - `recency_days_max`: `PositiveIntegerField(null=True, blank=True)`
  - `min_order_count`: `PositiveIntegerField(default=0)`
  - `min_lifetime_spend`: `DecimalField(max_digits=12, decimal_places=2, default=0.00)`
  - `target_category`: `ForeignKey("ecommerce.StoreCategory", on_delete=models.SET_NULL, null=True, blank=True)`
  - `cached_member_count`: `PositiveIntegerField(default=0)`
  - `last_evaluated_at`: `DateTimeField(null=True, blank=True)`
  - `is_active`: `BooleanField(default=True)`
  - `description`: `TextField(blank=True)`
- **Constraints & Indexes**: Unique constraint on `[tenant, number]` and `[tenant, code]`. Index on `[tenant, is_active, lifecycle_stage]`.

### 2. `RecommendationStrategy` [Prefix: `EREC-`] (`apps/ecommerce/models/Personalization/RecommendationStrategies.py`)
- **Purpose**: Manages multi-algorithm recommendation rules, placements, ranking weights, and fallback mechanisms.
- **Key Fields**:
  - `name`: `CharField(max_length=120)`
  - `code`: `CharField(max_length=60, db_index=True)`
  - `algorithm`: `CharField(max_length=30, choices=ALGORITHM_CHOICES, default="related_products")`
  - `placement`: `CharField(max_length=30, choices=PLACEMENT_CHOICES, default="pdp_related")`
  - `fallback_strategy`: `CharField(max_length=30, choices=FALLBACK_CHOICES, default="trending_popular")`
  - `max_items`: `PositiveIntegerField(default=6)`
  - `min_rating`: `DecimalField(max_digits=3, decimal_places=2, default=0.00)`
  - `same_brand_only`: `BooleanField(default=False)`
  - `only_in_stock`: `BooleanField(default=True)`
  - `target_category`: `ForeignKey("ecommerce.StoreCategory", on_delete=models.SET_NULL, null=True, blank=True)`
  - `target_segment`: `ForeignKey("ecommerce.AudienceSegment", on_delete=models.SET_NULL, null=True, blank=True)`
  - `is_active`: `BooleanField(default=True)`
  - `description`: `TextField(blank=True)`
- **Constraints & Indexes**: Unique constraint on `[tenant, number]` and `[tenant, code]`. Index on `[tenant, is_active, placement]`.

### 3. `PersonalizedExperience` [Prefix: `EPEX-`] (`apps/ecommerce/models/Personalization/PersonalizedExperiences.py`)
- **Purpose**: Manages dynamic hero banners, curated collections, and automated lifecycle triggers (cart/browse abandonment).
- **Key Fields**:
  - `name`: `CharField(max_length=120)`
  - `experience_type`: `CharField(max_length=30, choices=EXPERIENCE_TYPE_CHOICES, default="home_hero")`
  - `target_segment`: `ForeignKey("ecommerce.AudienceSegment", on_delete=models.CASCADE, related_name="experiences")`
  - `target_category`: `ForeignKey("ecommerce.StoreCategory", on_delete=models.SET_NULL, null=True, blank=True)`
  - `target_product`: `ForeignKey("ecommerce.CatalogProduct", on_delete=models.SET_NULL, null=True, blank=True)`
  - `headline`: `CharField(max_length=150, blank=True)`
  - `subheadline`: `TextField(blank=True)`
  - `cta_label`: `CharField(max_length=50, blank=True)`
  - `cta_url`: `CharField(max_length=255, blank=True)`
  - `hero_image_url`: `CharField(max_length=255, blank=True)`
  - `trigger_delay_hours`: `PositiveIntegerField(default=1, help_text="Delay before trigger dispatch")`
  - `priority`: `PositiveIntegerField(default=10, help_text="Higher priority takes precedence")`
  - `start_date`: `DateTimeField(null=True, blank=True)`
  - `end_date`: `DateTimeField(null=True, blank=True)`
  - `is_active`: `BooleanField(default=True)`
  - `impression_count`: `PositiveIntegerField(default=0)`
  - `click_count`: `PositiveIntegerField(default=0)`
  - `conversion_count`: `PositiveIntegerField(default=0)`
- **Constraints & Indexes**: Unique constraint on `[tenant, number]`. Index on `[tenant, is_active, experience_type, priority]`.

### 4. `ShopperBehaviorEvent` [Prefix: `ESBE-`] (`apps/ecommerce/models/Personalization/ShopperBehaviorEvents.py`)
- **Purpose**: High-throughput telemetry capture recording clicks, views, cart additions, and intent velocity.
- **Key Fields**:
  - `session_key`: `CharField(max_length=64, db_index=True)`
  - `customer_profile`: `ForeignKey("ecommerce.CustomerAccountProfile", on_delete=models.SET_NULL, null=True, blank=True, related_name="behavior_events")`
  - `party`: `ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="shopper_behavior_events")`
  - `user`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="shopper_behavior_events")`
  - `event_type`: `CharField(max_length=30, choices=EVENT_TYPE_CHOICES, default="page_view")`
  - `product`: `ForeignKey("ecommerce.CatalogProduct", on_delete=models.SET_NULL, null=True, blank=True, related_name="behavior_events")`
  - `category`: `ForeignKey("ecommerce.StoreCategory", on_delete=models.SET_NULL, null=True, blank=True, related_name="behavior_events")`
  - `intent_score_delta`: `IntegerField(default=1, help_text="Weight or score contribution of this interaction")`
  - `referrer_url`: `CharField(max_length=255, blank=True)`
  - `ip_address`: `GenericIPAddressField(null=True, blank=True)`
  - `user_agent`: `CharField(max_length=255, blank=True)`
  - `payload_json`: `JSONField(default=dict, blank=True)`
- **Constraints & Indexes**: Unique constraint on `[tenant, number]`. Index on `[tenant, session_key, event_type]`, Index on `[tenant, event_type, created_at]`.

### 5. Workbench & Operational Tools:
- **`PersonalizationWorkbench` & Recommendation Simulator**:
  - Administrative console allowing merchandisers to preview recommendation outputs for any product or shopper segment.
  - Interactive simulator displaying what a shopper in segment "VIP" or "At-Risk" would see on the homepage and PDP.
  - Real-time recalculation of audience segment sizes and trigger simulations (evaluating cart abandonment candidates).

---

## 6. Belongs to Sibling Sub-modules (Parked, Not Scoped Here)
- **Sub-module 9.9 (CMS & Landing Pages)**: Multi-column page builder, WYSIWYG article blocks, and static navigation trees. (9.8 provides dynamic personalized content cards, not full page CMS).
- **Sub-module 9.10 (Marketing & Campaigns)**: Mass outbound email dispatch, affiliate tracking, tracking UTM parameters across external ad campaigns.
- **Sub-module 9.13 (Reviews & UGC)**: Customer star ratings and verified review moderation (9.8 consumes `min_rating` read-only).
- **Sub-module 9.15 (Analytics & BI)**: Site-wide P&L, inventory GMV reports, and multi-channel attribution modeling.

---

## 7. Deferred (Later Passes / Integrations)
- **External Vector DB / Neural Embedding Clusters (Pinecone / Milvus / Qdrant)**: Real-time neural product embeddings deferred to future enterprise plugin. 9.8 provides database-native collaborative and content similarity that runs cleanly in standard PostgreSQL/SQLite.
- **Direct Mail / WhatsApp Gateway Webhooks**: Omnichannel messaging adapters deferred to 9.10 and 9.19. 9.8 tracks trigger eligibility and payload readiness.
