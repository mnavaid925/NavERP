# Research — Sub-module 9.10: Marketing & Campaign Management (Module 9 — eCommerce Management System, `ecommerce`)

- **Sub-module:** 9.10 Marketing & Campaign Management
- **Module:** 9 eCommerce Management System
- **Target app:** `apps/ecommerce` (extending the app created in 9.1 and extended in 9.2 through 9.8)
- **Research date:** 2026-10-31
- **Phase:** Phase 1 Research only
- **Output boundary:** `.claude/tasks/research-ecommerce-9.10.md` only

---

## 1. Executive Summary & Domain Architecture

Sub-module 9.10 delivers the **Omnichannel Marketing Automation, SMS & Push Notification Engine, Affiliate & Referral Program Manager, Social Commerce Syndication Hub, and Technical SEO Optimization Suite** for the NavERP eCommerce platform.

In contemporary high-growth digital commerce (exemplified by Klaviyo, Omnisend, ActiveCampaign, Postscript, Attentive, Refersion, UpPromote, and Yotpo), customer acquisition and retention are driven by coordinated, automated marketing touchpoints rather than disconnected batch blasts:
- **Event-driven email drip campaigns and lifecycle flows** (welcome sequences, abandoned cart recovery, browse abandonment, post-purchase cross-sell, and win-back flows) generate over 40% of email revenue while accounting for less than 5% of total email send volume.
- **High-urgency SMS and push alerts** (flash sales, back-in-stock alerts, order tracking milestones, and location-gated notifications) achieve 98% open rates and 20%+ click-through rates when safeguarded by intelligent frequency throttling (Smart Sending).
- **Affiliate, influencer, and customer referral programs** transform customers and content creators into brand advocates, driving 15% to 30% of new customer acquisition via coupon code attribution, first-party referral links, and automated commission structures.
- **Social commerce catalog syndication** keeps inventory, pricing, and product attributes synchronized in near-real-time across Meta Commerce Manager (Instagram/Facebook Shops) and TikTok Shop to capture impulse mobile commerce while mitigating viral overselling.
- **Automated technical SEO rules** eliminate manual metadata maintenance across thousands of SKUs by generating variable-driven meta tags, Rich Result Schema.org (JSON-LD `Product`, `Offer`, `BreadcrumbList`) markup, XML sitemaps, and search engine rank monitoring.

### Architectural Boundary Rulings (L28, L29, L36, L37):
1. **Core Spine Reuse & Integration (L28/L29)**:
   - Shopper and affiliate identity reuses the unified canonical **`core.Party`** spine (`apps/core/models/Party.py`). Customers and affiliate partners are roles/profiles anchored to `Party`, preventing duplicate party tables.
   - Authenticated staff, marketers, and customer user accounts link directly to **`accounts.User`**.
   - Campaign audience targeting directly leverages **`ecommerce.AudienceSegment`** (`ESEG-`, 9.8) — reusing the RFM and behavioral cohorts established in the personalization sub-module.
   - Product promotional blasts, back-in-stock notifications, and SEO metadata rules target **`ecommerce.CatalogProduct`** (`EPRD-`, 9.1) and **`ecommerce.ProductVariant`** (`PVR-`, 9.1).
   - Category-scoped SEO templates and campaign banners link to **`ecommerce.StoreCategory`** (`ECAT-`, 9.1).
   - Order-triggered transactional alerts and affiliate commission conversions link directly to **`ecommerce.EcommerceOrder`** (`EORD-`, 9.5).
   - Customer-advocate referral links associate with **`ecommerce.CustomerAccountProfile`** (`ECAP-`, 9.6).
   - Financial ledger integrity: Affiliate commission payouts generate financial records in **`apps/accounting/`** (Module 2) via vendor bill or payment vouchers; no secondary financial ledger is created in ecommerce.
2. **Clear Sibling Boundaries (9.2 vs. 9.3 vs. 9.8 vs. 9.9 vs. 9.10 vs. 9.11 vs. 9.13 vs. 9.15)**:
   - **Sub-module 9.2 (Inventory & Stock Management, shipped)**: Owns physical warehouse stock, inventory allocations (`EAL-`), and multi-channel inventory counts (`ChannelInventorySync`). 9.10 handles social commerce catalog feed generation and marketing notifications triggered by restock events.
   - **Sub-module 9.3 (Pricing & Promotion Engine, shipped)**: Owns storefront coupon promotions (`ECPN-`), dynamic pricing rules (`EDPR-`), and flash sale counters (`EFLS-`). 9.10 handles outbound marketing campaign delivery of these promo codes to specific audience segments and tracks affiliate coupon attribution.
   - **Sub-module 9.8 (Personalization & Recommendation Engine, shipped)**: Owns shopper clickstream behavior tracking (`ESBE-`), algorithmic recommendation strategies (`EREC-`), personalized experiences (`EPEX-`), and audience segmentation cohorts (`ESEG-`). 9.10 consumes `AudienceSegment` as campaign recipient targets.
   - **Sub-module 9.9 (Content Management System, sibling)**: Sibling sub-module owning page builder templates, blog/editorial articles, media library assets, and landing page layouts. 9.10 owns marketing campaign messages and SEO metadata rules.
   - **Sub-module 9.10 (This Pass)**: Owns omnichannel marketing campaigns (Email, SMS, Push, Drips, Deliverability tracking), affiliate & referral partner programs, affiliate order conversions/commissions, and automated SEO metadata/schema rules.
   - **Sub-module 9.11 (Marketplace & Multi-Vendor, sibling)**: Owns marketplace vendor onboarding, merchant seller catalogs, and vendor sales split payouts. In contrast, 9.10 owns external affiliate partners, brand ambassadors, and customer referral advocacy.
   - **Sub-module 9.13 (Reviews & UGC, sibling)**: Owns customer star ratings, review moderation, and photo/video user-generated content widgets.
   - **Sub-module 9.15 (Analytics & BI, sibling)**: Owns multi-touch attribution modeling (first-touch, last-touch, linear, W-shaped attribution curves) and blended CAC dashboards. 9.10 tracks campaign-level delivery metrics and direct affiliate order attribution.
3. **Multi-Tenancy & Data Isolation**:
   All marketing campaigns, affiliate agreements, referral conversions, and SEO metadata rules are strictly scoped by `tenant` (`core.Tenant`). Affiliate tracking codes and campaign metrics are completely isolated per tenant workspace.
4. **Base Class & Prefix Discipline**:
   All models inherit from `TenantNumbered` (`apps/ecommerce/models/_base.py`), providing strict `tenant` foreign keys (`on_delete=CASCADE`), thread-safe auto-number generation, and audit timestamps.

---

## 2. Repo State Checked First

### 2.1 Navigation & App Tree State
- **`apps/core/navigation.py`:**
  - `"9.1"` is live: Product Catalog Management (`EPRD`, `PVR`, `ECAT`, `PRL`)
  - `"9.2"` is live: Inventory & Stock Management (`EFC`, `EAL`, `EBK`, `ESYN`)
  - `"9.3"` is live: Pricing & Promotion Engine (`EDPR`, `ECPN`, `EFLS`, `ECPM`)
  - `"9.4"` is live: Shopping Cart & Checkout (`ECRT`, `ECKS`, `ESHP`, `EPMC`)
  - `"9.5"` is live: Order Management System (`EORD`, `EORT`, `EFUL`, `ERMA`)
  - `"9.6"` is live: Customer Account & Profile (`ECAP`, `ECAD`, `EWSL`, `ECPR`)
  - `"9.7"` is live: Search & Product Discovery (`ESYN`, `ESFC`, `ESMR`, `ESQL`)
  - `"9.8"` is live: Personalization & Recommendation Engine (`ESEG`, `EREC`, `EPEX`, `ESBE`)
  - Sub-module `"9.10"` currently has no `LIVE_LINKS` entries yet.
- **`apps/ecommerce/` package structure:**
  - Sub-module 9.10 will add package subdirectories: `MarketingCampaign/` across `models/`, `forms/`, `views/`, `urls/`, and `templates/ecommerce/marketingcampaign/`.

### 2.2 As-Built Core Spine Entities (Grep Verified)
| Entity | Location | Status | 9.10 Usage |
|---|---|---|---|
| `core.Tenant` | `apps/core/models/Tenant.py:17` | **Present** | Strict workspace tenant isolation |
| `core.Party` | `apps/core/models/Party.py:5` | **Present** | Unified affiliate partner / shopper party identity |
| `accounts.User` | `apps/accounts/models.py:14` | **Present** | Marketer / staff creator and administrator identity |
| `ecommerce.CatalogProduct` | `apps/ecommerce/models/ProductCatalog/CatalogProducts.py:8` | **Present** | Product promotional blasts, back-in-stock alerts, SEO rules |
| `ecommerce.ProductVariant` | `apps/ecommerce/models/ProductCatalog/ProductVariants.py:10` | **Present** | Variant-level inventory restock triggers |
| `ecommerce.StoreCategory` | `apps/ecommerce/models/ProductCatalog/StoreCategories.py:7` | **Present** | Category-level marketing campaigns & SEO metadata templates |
| `ecommerce.EcommerceOrder` | `apps/ecommerce/models/OrderManagement/EcommerceOrders.py:12` | **Present** | Order alerts, post-purchase flows, affiliate commission attribution |
| `ecommerce.CustomerAccountProfile` | `apps/ecommerce/models/CustomerAccount/CustomerAccountProfiles.py:9` | **Present** | Customer referral advocacy and recipient profile linking |
| `ecommerce.AudienceSegment` | `apps/ecommerce/models/Personalization/AudienceSegments.py:10` | **Present** | Campaign recipient cohort targeting (`ESEG-`) |
| `ecommerce.CouponPromotion` | `apps/ecommerce/models/PricingPromotion/CouponPromotions.py:9` | **Present** | Campaign discount codes and affiliate referral coupon linkage |

### 2.3 Prefix Collision Verification
All candidate prefixes checked across all models in the repository via `git grep -E 'NUMBER_PREFIX\s*=\s*"(EMCP|EAFF|EARC|ESEO)"' apps/`:
- `EMCP` — `MarketingCampaign` (**Verified 100% FREE — 0 collisions**)
- `EAFF` — `AffiliatePartner` (**Verified 100% FREE — 0 collisions**)
- `EARC` — `AffiliateReferralConversion` (**Verified 100% FREE — 0 collisions**)
- `ESEO` — `SeoMetadataRule` (**Verified 100% FREE — 0 collisions**)

---

## 3. Commercial Market Leaders Surveyed

### 1. Klaviyo (eCommerce Marketing Automation & Deliverability Hub)
- **Positioning**: The premier e-commerce email & SMS marketing automation platform and Customer Data Platform (CDP) powering over 140,000 global digital brands.
- **Reference**: https://www.klaviyo.com/features/flows and https://www.klaviyo.com/features/email-marketing
- **Key Capabilities**:
  - **Behavioral Drip Flows**: Automated multi-channel sequences triggered by live store events (e.g. Abandoned Checkout, Browse Abandonment, Welcome Series, Post-Purchase Cross-Sell, Customer Win-Back).
  - **Visual Flow Builder with Conditional Splits**: Branching logic based on cart value, order frequency, audience segments, or predicted customer lifetime value.
  - **Deliverability Hub & Sender Reputation**: Centralized dashboard monitoring SPF/DKIM/DMARC status, sending volume breakdown across inbox providers (Gmail, Yahoo, Microsoft), bounce rates, and spam complaint thresholds.
  - **Smart Sending & Fatigue Rules**: Automated sending throttle windows (e.g. 16-hour cooldown) that suppress secondary messages if a recipient recently received a promotional blast.
  - **Dynamic Catalog Product Insertion**: Dynamic product blocks that pull live product titles, images, and prices directly into campaign layouts.

### 2. Omnisend (Omnichannel Email, SMS & Push Automation)
- **Positioning**: All-in-one omnichannel marketing automation platform built exclusively for high-growth e-commerce merchants.
- **Reference**: https://www.omnisend.com/features/automation/ and https://www.omnisend.com/features/
- **Key Capabilities**:
  - **Unified Cross-Channel Journeys**: Blends Email, SMS, and Web Push notifications in a single customer journey workflow editor (e.g. send email $\rightarrow$ if unopened after 24h, send push notification $\rightarrow$ if still unengaged, send SMS with discount code).
  - **Web & Mobile Push Notifications**: Browser-level push alerts for instant retargeting, flash sales, and price drop notifications without requiring native mobile apps.
  - **E-Commerce Product Picker**: Direct sync with store catalog allowing instant insertion of SKUs, prices, and imagery into campaigns.
  - **Revenue-Driven Attribution**: Direct revenue attribution reporting tying exact dollar amounts, order counts, and conversion rates to individual campaign broadcasts and automated flows.

### 3. ActiveCampaign (Lifecycle Automation & Deliverability Tracking)
- **Positioning**: Industry benchmark for visual email automation, multi-branching drip sequences, and enterprise email deliverability.
- **Reference**: https://www.activecampaign.com/product/ecommerce
- **Key Capabilities**:
  - **Event-Driven Lifecycle Triggers**: Triggers automations based on cart abandonment, purchase completions, refund events, and custom website telemetry.
  - **Deliverability Monitoring & Hygiene**: Automated list hygiene flows that tag unengaged subscribers, suppress dormant contacts, and manage bounce classifications (hard vs. soft bounces).
  - **Predictive Send Time Optimization**: Automatically dispatches campaigns at the optimal hour when individual recipients historically open emails.

### 4. Postscript (eCommerce SMS Marketing & Back-in-Stock Alerts)
- **Positioning**: Premier e-commerce SMS and MMS platform specializing in high-converting behavioral text messaging for direct-to-consumer brands.
- **Reference**: https://www.postscript.io/features
- **Key Capabilities**:
  - **Automated Back-in-Stock Alerts**: Captures shopper phone numbers on out-of-stock product pages and automatically fires an SMS notification the moment inventory is replenished.
  - **Transactional Order Alerts**: Immediate SMS updates for order confirmations, fulfillment dispatches, and out-for-delivery notifications.
  - **TCPA / CTIA Compliance Engine**: Strict opt-in timestamp tracking, automated quiet hours (preventing texts between 9 PM and 8 AM recipient local time), and instant STOP/UNSUBSCRIBE suppression handling.
  - **MMS Rich Media Support**: Embeds animated GIFs, product imagery, and discount cards directly in text messages.

### 5. Attentive (Conversational Mobile Messaging & Geofenced Push)
- **Positioning**: Enterprise conversational mobile messaging platform powering high-volume SMS, MMS, and geofenced mobile engagement.
- **Reference**: https://www.attentive.com/features
- **Key Capabilities**:
  - **Geofenced & Location-Based Alerts**: Triggers localized promotional messages and store-opening announcements when subscribers enter designated geographic zones.
  - **Low-Inventory & Price-Drop Triggers**: Automated notifications triggered when viewed catalog items drop below designated safety stock levels or undergo price markdowns.
  - **Variant-Level Waitlisting**: Granular waitlisting down to variant SKUs (size, color, material) with automated subscriber notification upon restock.

### 6. Refersion (Enterprise Affiliate & First-Party Referral Tracking)
- **Positioning**: Enterprise-grade affiliate, influencer, and referral marketing platform with multi-platform first-party link and coupon attribution.
- **Reference**: https://www.refersion.com/features/
- **Key Capabilities**:
  - **First-Party Tracking & Cookie-Free Attribution**: Direct tracking links and coupon-code-based attribution that bypass third-party cookie restrictions and ad blockers.
  - **Flexible Commission Structures**: Supports flat-rate commission per order, percentage of net sales, SKU-specific commissions, and tiered reward structures based on monthly referred sales volume.
  - **Affiliate Portal & Registration**: Dedicated partner onboarding with custom referral link slugs, dashboard analytics, and performance visibility.
  - **Refund / RMA Clawback Protection**: Automatically voids or recalculates pending affiliate commissions if the referred order is refunded or returned.
  - **Automated Payout Batches**: Consolidates approved commissions into scheduled payout runs with tax compliance verification (W-9 / W-8BEN status).

### 7. UpPromote (Affiliate, Ambassador & Customer Referral Programs)
- **Positioning**: Top-ranked e-commerce affiliate and referral marketing software featuring customer-to-advocate conversion and multi-tier tracking.
- **Reference**: https://uppromote.com/features/
- **Key Capabilities**:
  - **Customer Referral Program**: Automatically turns existing verified purchasers into referral advocates, issuing personal referral codes and links post-purchase.
  - **Two-Sided Referral Incentives**: Rewards both the existing advocate (commission/store credit) and the friend (discount on first purchase).
  - **Coupon Code Attribution**: Assigns unique coupon codes directly to affiliates so sales are credited even if the shopper never clicked a tracking link.
  - **Fraud Detection & IP Matching**: Monitors suspicious self-referrals, identical IP purchases, and fraudulent click traffic.

### 8. Yotpo Referrals & Loyalty (Advocate Referrals & Social Commerce)
- **Positioning**: Unified retention platform bridging customer referral programs, social commerce feeds, and visual UGC proof.
- **Reference**: https://www.yotpo.com/platform/referrals/
- **Key Capabilities**:
  - **Social Sharing & Shoppable Referral Links**: One-click social sharing buttons (Facebook, X, WhatsApp, Instagram) generating custom shortened tracking URLs.
  - **Advocate Lifecycle Management**: Tracks advocate performance tiers (Bronze, Silver, Gold VIP) with increasing commission incentives.
  - **Social Proof Integration**: Connects referral widgets with customer review star ratings to increase conversion on advocate landing pages.

### 9. Rank Math SEO & Yoast eCommerce (Technical SEO Automation)
- **Positioning**: Leading technical SEO automation suites for e-commerce, delivering automated schema markup, dynamic meta tags, and XML sitemaps.
- **Reference**: https://rankmath.com/schema-generator/
- **Key Capabilities**:
  - **Tokenized Meta Tag Automation**: Dynamic templates using attribute variables (e.g. `{product_name} - Best Price Online | {brand} | {category}`) with length limit enforcement to avoid SERP truncation.
  - **JSON-LD Schema.org Automation**: Server-side generation of `Product`, `Offer`, `AggregateRating`, and `BreadcrumbList` structured data to trigger Google Rich Results.
  - **Dynamic XML Sitemap Engine**: Automatically includes canonical product and category URLs while excluding parameterized filter pages; defines `priority` and `changefreq` per entity.
  - **Robots Indexing Directives**: Granular `index`/`noindex` and `follow`/`nofollow` directives at category and product levels.
  - **Focus Keyword Rank Tracking**: Associates target search keywords with catalog pages and tracks SERP rank positioning.

### 10. DataFeedWatch & CedCommerce (Social Commerce Catalog Syndication)
- **Positioning**: Industry standard for multi-channel product catalog feeds synchronizing e-commerce stores with Meta Catalog (Instagram/Facebook Shops) and TikTok Shop.
- **Reference**: https://www.datafeedwatch.com/solutions/social-media-channels
- **Key Capabilities**:
  - **Multi-Channel Catalog Feeds**: Generates scheduled XML, RSS, and JSON feeds formatted specifically for Meta Commerce Manager and TikTok Seller Center.
  - **Channel-Specific Attribute Mapping**: Maps internal catalog categories to Google Product Categories (GPC) and social taxonomy standards.
  - **Inventory Buffer Sync**: Deducts safety buffers to prevent overselling on fast-moving social flash sales.

---

## 4. Feature Catalog (Sub-module 9.10 Only)

### 4.1 Email Marketing Automation
- **Visual Newsletter Broadcasts & Promotional Blasts** — Marketer design and scheduling of outbound email campaigns with custom subject lines, preheaders, rich HTML bodies, and target segment selection.
  - *Seen in:* Klaviyo, Omnisend, ActiveCampaign
  - *Priority:* `table-stakes`
  - *Spine:* Fields in `MarketingCampaign` (`EMCP-`), targeting `ecommerce.AudienceSegment` (`ESEG-`, 9.8)
  - *Status:* Buildable now
- **Event-Driven Drip Campaigns & Flow Sequences** — Automated multi-step email journeys triggered by customer lifecycle milestones (Welcome Series, Abandoned Cart, Post-Purchase Follow-up, Win-Back).
  - *Seen in:* Klaviyo (Flows), Omnisend, ActiveCampaign
  - *Priority:* `table-stakes`
  - *Spine:* Field `campaign_type` in `MarketingCampaign`
  - *Status:* Buildable now (flow configuration & trigger rule); worker scheduler deferred
- **Transactional Order Alerts & Notification Templates** — System notifications for order confirmation, shipment fulfillment dispatch, and return receipt.
  - *Seen in:* Klaviyo, Omnisend, Postscript
  - *Priority:* `table-stakes`
  - *Spine:* Reuses `ecommerce.EcommerceOrder` (`EORD-`, 9.5) linked to `MarketingCampaign`
  - *Status:* Buildable now
- **Deliverability Monitoring & Sender Health Metrics** — Centralized tracking of sent counts, delivered counts, open rates, click-through rates, hard/soft bounces, unsubscribes, and spam complaints.
  - *Seen in:* Klaviyo (Deliverability Hub), ActiveCampaign
  - *Priority:* `table-stakes`
  - *Spine:* Telemetry fields on `MarketingCampaign`
  - *Status:* Buildable now
- **Smart Sending & Fatigue Throttling** — Automated cooldown window (e.g. 16 or 24 hours) preventing recipients from receiving excessive marketing messages within a short timeframe.
  - *Seen in:* Klaviyo (Smart Sending), Omnisend
  - *Priority:* `common`
  - *Spine:* Field `send_throttle_window_hours` in `MarketingCampaign`
  - *Status:* Buildable now

### 4.2 SMS & Push Notification
- **High-Urgency SMS Promotional Blasts** — Direct SMS campaigns with character count budgeting (GSM-7 vs. UCS-2 encoding), sender ID designation, and discount code insertion.
  - *Seen in:* Postscript, Attentive, Omnisend
  - *Priority:* `table-stakes`
  - *Spine:* Channel `sms` in `MarketingCampaign`
  - *Status:* Buildable now
- **Automated Back-in-Stock Restock Alerts** — Event-driven SMS/Push alerts triggered when an out-of-stock product or variant inventory is replenished.
  - *Seen in:* Postscript, Attentive (Back in Stock Journeys)
  - *Priority:* `common`
  - *Spine:* Campaign type `back_in_stock` with FK `target_product` to `ecommerce.CatalogProduct`
  - *Status:* Buildable now
- **Web & Mobile Push Notifications** — Browser-based and mobile push notifications for instant customer re-engagement, price drops, and cart recovery.
  - *Seen in:* Omnisend, Attentive
  - *Priority:* `common`
  - *Spine:* Channel `push` in `MarketingCampaign`
  - *Status:* Buildable now
- **Geofenced & Location-Gated Promotional Messaging** — Location-targeted messaging triggered based on geographic coordinates (latitude, longitude, radius in kilometers) for omnichannel retail promotions.
  - *Seen in:* Attentive (Location Journeys)
  - *Priority:* `differentiator`
  - *Spine:* Fields `geofence_latitude`, `geofence_longitude`, `geofence_radius_km` in `MarketingCampaign`
  - *Status:* Buildable now

### 4.3 Affiliate & Referral Programs
- **Affiliate & Ambassador Partner Directory** — Central partner management tracking affiliates, influencers, brand ambassadors, and customer advocates.
  - *Seen in:* Refersion, UpPromote, Yotpo Referrals
  - *Priority:* `table-stakes`
  - *Spine:* New table `AffiliatePartner` (`EAFF-`), FK to `core.Party` (spine reuse)
  - *Status:* Buildable now
- **Unique Referral Links & Tracking Slugs** — Generation of distinct partner referral links (e.g. `/ref/{slug}`) for direct first-party attribution.
  - *Seen in:* Refersion (First-Party Tracking), UpPromote
  - *Priority:* `table-stakes`
  - *Spine:* Field `referral_link_slug` in `AffiliatePartner`
  - *Status:* Buildable now
- **Referral Coupon Code Generation & Attribution** — Creation and linking of specific coupon codes (e.g. `ALICE15`, `VIPSUMMER`) attributed directly to the affiliate partner.
  - *Seen in:* UpPromote, Refersion
  - *Priority:* `table-stakes`
  - *Spine:* Field `referral_code` in `AffiliatePartner`, FK to `ecommerce.CouponPromotion` (`ECPN-`, 9.3)
  - *Status:* Buildable now
- **Configurable Commission Structures** — Support for percentage of net sales, flat dollar amount per order, or tiered commission structures.
  - *Seen in:* Refersion, UpPromote
  - *Priority:* `table-stakes`
  - *Spine:* Fields `commission_type` and `commission_rate` in `AffiliatePartner`
  - *Status:* Buildable now
- **Order Referral Conversion Tracking & Attribution** — Ledger recording each referred order, gross/net order value, attribution source (link click vs coupon code), and calculated commission.
  - *Seen in:* Refersion, UpPromote
  - *Priority:* `table-stakes`
  - *Spine:* New table `AffiliateReferralConversion` (`EARC-`), FK to `ecommerce.EcommerceOrder` (`EORD-`, 9.5)
  - *Status:* Buildable now
- **Refund & RMA Commission Clawback Protection** — Automatic recalculation and voiding of affiliate commissions if the referred order is returned or cancelled.
  - *Seen in:* Refersion, UpPromote
  - *Priority:* `common`
  - *Spine:* Field `status='voided_refund'` in `AffiliateReferralConversion` linked to `ERMA-` (9.5)
  - *Status:* Buildable now
- **Customer Referral Advocacy (Two-Sided Incentive)** — Mechanism allowing regular customers to invite friends with mutual rewards (advocate gets store credit/commission, friend gets discount).
  - *Seen in:* UpPromote, Yotpo Referrals
  - *Priority:* `common`
  - *Spine:* Optional FK `customer_profile` to `ecommerce.CustomerAccountProfile` in `AffiliatePartner`
  - *Status:* Buildable now

### 4.4 Social Commerce Integration
- **Social Catalog Feed Syndication (Meta / TikTok)** — Automated export and syndication of product catalogs in standardized XML/RSS/JSON feeds for Meta Commerce Manager and TikTok Seller Center.
  - *Seen in:* DataFeedWatch, CedCommerce, Shopify Sales Channels
  - *Priority:* `table-stakes`
  - *Spine:* Built via catalog export endpoints consuming `ecommerce.CatalogProduct` (`EPRD-`, 9.1) and `ChannelInventorySync` (9.2)
  - *Status:* Buildable now (feed export); external SaaS webhook sync deferred
- **Shoppable Social Post Tags & Feed Sync** — Mapping catalog product SKUs to social post assets for Instagram/TikTok shoppable posts.
  - *Seen in:* Yotpo, CedCommerce, Meta Commerce Manager
  - *Priority:* `common`
  - *Spine:* Architecture endpoint / catalog metadata
  - *Status:* Buildable now; native in-app checkout sync deferred to marketplace pass (9.11)
- **Social Proof Widgets & Referral Sharing** — Embeddable referral and social proof share buttons (WhatsApp, Facebook, X) for customer advocacy.
  - *Seen in:* Yotpo, UpPromote
  - *Priority:* `common`
  - *Spine:* Storefront sharing component linked to `AffiliatePartner`
  - *Status:* Buildable now

### 4.5 SEO & Organic Traffic Tools
- **Tokenized Meta Tag Automation** — Dynamic title and meta description templates with attribute replacement tokens (`{product_name}`, `{brand}`, `{category}`, `{price}`, `{site_name}`) to automate SEO across thousands of SKUs.
  - *Seen in:* Rank Math, Yoast SEO, Smart SEO
  - *Priority:* `table-stakes`
  - *Spine:* New table `SeoMetadataRule` (`ESEO-`)
  - *Status:* Buildable now
- **JSON-LD Schema.org Structured Data Automation** — Automated generation of Rich Result JSON-LD payloads (`Product`, `Offer`, `BreadcrumbList`, `Organization`) on storefront pages to maximize Google Rich Result visibility.
  - *Seen in:* Rank Math, ClickRank AI, Yoast
  - *Priority:* `table-stakes`
  - *Spine:* Field `json_ld_schema_type` in `SeoMetadataRule`
  - *Status:* Buildable now
- **XML Sitemap Hierarchy & Indexing Rules** — Configurable inclusion, `priority` (0.1–1.0), and `changefreq` (daily, weekly, monthly) settings for search engine crawl budgets.
  - *Seen in:* Rank Math, Google Search Console tools
  - *Priority:* `table-stakes`
  - *Spine:* Fields `sitemap_included`, `sitemap_priority`, `sitemap_changefreq` in `SeoMetadataRule`
  - *Status:* Buildable now
- **Robots Indexing Directives** — Storefront indexing rules (`index, follow`, `noindex, follow`, `noindex, nofollow`) to protect staging or discontinued products from SEO penalties.
  - *Seen in:* Rank Math, Yoast
  - *Priority:* `table-stakes`
  - *Spine:* Field `robots_directive` in `SeoMetadataRule`
  - *Status:* Buildable now
- **Target Keyword SERP Rank Tracking** — Association of primary focus keywords with catalog entities and recording of monitored search engine rank positions.
  - *Seen in:* Rank Math, Ahrefs, SEMrush
  - *Priority:* `common`
  - *Spine:* Fields `target_keyword`, `tracked_rank_position`, `rank_tracked_at` in `SeoMetadataRule`
  - *Status:* Buildable now

---

## 5. Recommended Build Scope (This Pass — 4 Models)

To deliver a production-grade, highly cohesive marketing engine matching the NavERP `/next-module` 1–4 model standard, we recommend **4 tenant-scoped models** organized under `apps/ecommerce/models/MarketingCampaign/`:

```
apps/ecommerce/models/MarketingCampaign/
├── __init__.py
├── MarketingCampaigns.py               # EMCP — Omnichannel Campaigns, Drips & Deliverability
├── AffiliatePartners.py                # EAFF — Affiliate & Referral Partners, Codes & Terms
├── AffiliateReferralConversions.py     # EARC — Order Attribution, Commission & Clawback
└── SeoMetadataRules.py                 # ESEO — Meta Tag Templates, Schema.org & Sitemap Rules
```

### Model 1: `MarketingCampaign` [Prefix: `EMCP`]
- **Purpose**: Core omnichannel marketing campaign and automated flow entity. Orchestrates email newsletters, drip journeys, transactional alerts, SMS promotional blasts, push notifications, and back-in-stock alerts with audience segment targeting, smart sending fatigue controls, and deliverability performance tracking.
- **Inherits**: `TenantNumbered` (`apps/ecommerce/models/_base.py`)
- **Key Fields & Choices**:
  - `tenant` (FK `core.Tenant`, on_delete=CASCADE)
  - `number` (CharField, `EMCP-XXXXX`, auto-generated)
  - `name` (CharField, max_length=150, help_text="Administrative campaign name, e.g. 'Black Friday VIP Early Access'")
  - `code` (CharField, max_length=60, help_text="Machine slug identifier")
  - `campaign_type` (CharField, max_length=30, choices: `newsletter_broadcast`, `drip_sequence`, `order_alert`, `back_in_stock`, `abandoned_cart`, `geofenced_blast`, `promotional_flash`, default `newsletter_broadcast`)
  - `channel` (CharField, max_length=20, choices: `email`, `sms`, `push`, `omnichannel`, default `email`)
  - `status` (CharField, max_length=20, choices: `draft`, `scheduled`, `sending`, `sent`, `cancelled`, `paused`, default `draft`)
  - `target_segment` (FK `ecommerce.AudienceSegment`, on_delete=models.SET_NULL, null=True, blank=True, related_name="campaigns", help_text="Target audience cohort from 9.8 Personalization")
  - `target_product` (FK `ecommerce.CatalogProduct`, on_delete=models.SET_NULL, null=True, blank=True, related_name="marketing_campaigns", help_text="Target product for back-in-stock alerts or single-product promo blasts")
  - `subject` (CharField, max_length=200, blank=True, help_text="Email subject line / SMS headline / Push notification title")
  - `preview_text` (CharField, max_length=255, blank=True, help_text="Email preheader preview text / Push short summary")
  - `content_body` (TextField, help_text="Newsletter HTML markup / SMS text message / Push message copy")
  - `sender_name` (CharField, max_length=100, blank=True, help_text="Brand or sender display name")
  - `sender_address` (CharField, max_length=120, blank=True, help_text="From email address or SMS sender ID")
  - `scheduled_at` (DateTimeField, null=True, blank=True, help_text="Scheduled broadcast dispatch time")
  - `sent_at` (DateTimeField, null=True, blank=True, help_text="Timestamp when campaign dispatch completed")
  - `send_throttle_window_hours` (PositiveIntegerField, default=16, help_text="Smart Sending cooldown window to prevent recipient fatigue")
  - `geofence_latitude` (DecimalField, max_digits=9, decimal_places=6, null=True, blank=True, help_text="Target geographic latitude for geofenced push alerts")
  - `geofence_longitude` (DecimalField, max_digits=9, decimal_places=6, null=True, blank=True, help_text="Target geographic longitude for geofenced push alerts")
  - `geofence_radius_km` (DecimalField, max_digits=6, decimal_places=2, null=True, blank=True, help_text="Target radius in km around geofence coordinate")
  - **Deliverability Telemetry**:
    - `recipient_count` (PositiveIntegerField, default=0, help_text="Total targeted recipient profiles")
    - `delivered_count` (PositiveIntegerField, default=0, help_text="Confirmed delivered messages")
    - `opened_count` (PositiveIntegerField, default=0, help_text="Unique opens recorded")
    - `clicked_count` (PositiveIntegerField, default=0, help_text="Unique link clicks recorded")
    - `bounced_count` (PositiveIntegerField, default=0, help_text="Failed or bounced dispatches")
    - `unsubscribed_count` (PositiveIntegerField, default=0, help_text="Unsubscribe opt-outs recorded")
    - `complaint_count` (PositiveIntegerField, default=0, help_text="Spam complaints reported")
    - `revenue_attributed` (DecimalField, max_digits=12, decimal_places=2, default=Decimal("0.00"), help_text="Total store revenue directly attributed to this campaign")
- **Constraints & Indexes**:
  - Unique constraint on `["tenant", "number"]`
  - Unique constraint on `["tenant", "code"]`
  - Index on `["tenant", "status", "campaign_type"]`
  - Index on `["tenant", "scheduled_at"]`
- **Verified FKs**: `core.Tenant`, `ecommerce.AudienceSegment`, `ecommerce.CatalogProduct`.

### Model 2: `AffiliatePartner` [Prefix: `EAFF`]
- **Purpose**: Master record for external affiliate partners, brand ambassadors, influencers, and customer referral advocates. Configures referral tracking slugs, unique coupon codes, commission rates, attribution cookie windows, and aggregates lifetime referred revenue.
- **Inherits**: `TenantNumbered` (`apps/ecommerce/models/_base.py`)
- **Key Fields & Choices**:
  - `tenant` (FK `core.Tenant`, on_delete=CASCADE)
  - `number` (CharField, `EAFF-XXXXX`, auto-generated)
  - `name` (CharField, max_length=120, help_text="Partner display name or company name")
  - `party` (FK `core.Party`, on_delete=CASCADE, related_name="affiliate_profiles", help_text="Unified Core Spine Party entity")
  - `customer_profile` (FK `ecommerce.CustomerAccountProfile`, on_delete=SET_NULL, null=True, blank=True, related_name="affiliate_memberships", help_text="Optional shopper account profile for customer advocates")
  - `partner_type` (CharField, max_length=25, choices: `affiliate`, `influencer`, `brand_ambassador`, `customer_advocate`, default `affiliate`)
  - `referral_code` (CharField, max_length=50, help_text="Unique discount / promo tracking code, e.g. 'SUMMER25', 'ALICE10'")
  - `referral_link_slug` (CharField, max_length=60, help_text="Unique tracking URL slug, e.g. 'alice-smith'")
  - `commission_type` (CharField, max_length=25, choices: `percentage_net_sales`, `flat_per_order`, `tiered`, default `percentage_net_sales`)
  - `commission_rate` (DecimalField, max_digits=6, decimal_places=2, default=Decimal("10.00"), help_text="Commission rate percentage (e.g. 10.00%) or flat dollar amount ($10.00)")
  - `cookie_duration_days` (PositiveIntegerField, default=30, help_text="Referral attribution window in days")
  - `status` (CharField, max_length=20, choices: `active`, `pending_approval`, `suspended`, `inactive`, default `pending_approval`)
  - `payout_threshold` (DecimalField, max_digits=10, decimal_places=2, default=Decimal("50.00"), help_text="Minimum earnings required before payout batch generation")
  - `payment_email` (EmailField, blank=True, help_text="Payout PayPal / remittance email address")
  - **Aggregated Performance Metrics**:
    - `total_orders_referred` (PositiveIntegerField, default=0)
    - `total_revenue_generated` (DecimalField, max_digits=12, decimal_places=2, default=Decimal("0.00"))
    - `total_commission_earned` (DecimalField, max_digits=12, decimal_places=2, default=Decimal("0.00"))
    - `total_commission_paid` (DecimalField, max_digits=12, decimal_places=2, default=Decimal("0.00"))
- **Constraints & Indexes**:
  - Unique constraint on `["tenant", "number"]`
  - Unique constraint on `["tenant", "referral_code"]`
  - Unique constraint on `["tenant", "referral_link_slug"]`
  - Index on `["tenant", "status", "partner_type"]`
- **Verified FKs**: `core.Tenant`, `core.Party`, `ecommerce.CustomerAccountProfile`.

### Model 3: `AffiliateReferralConversion` [Prefix: `EARC`]
- **Purpose**: Granular transaction ledger recording referred store orders, attribution mechanics (link click vs coupon code), computed commissions, approval status, and automatic clawback handling upon order cancellation or return.
- **Inherits**: `TenantNumbered` (`apps/ecommerce/models/_base.py`)
- **Key Fields & Choices**:
  - `tenant` (FK `core.Tenant`, on_delete=CASCADE)
  - `number` (CharField, `EARC-XXXXX`, auto-generated)
  - `affiliate` (FK `ecommerce.AffiliatePartner`, on_delete=CASCADE, related_name="referral_conversions", help_text="Credited affiliate partner")
  - `order` (FK `ecommerce.EcommerceOrder`, on_delete=CASCADE, related_name="affiliate_conversions", help_text="Referred store order from 9.5 OMS")
  - `referred_customer` (FK `ecommerce.CustomerAccountProfile`, on_delete=SET_NULL, null=True, blank=True, related_name="referral_orders", help_text="Referred shopper profile")
  - `attribution_type` (CharField, max_length=25, choices: `referral_link`, `coupon_code`, `manual_credit`, default `referral_link`)
  - `order_amount` (DecimalField, max_digits=12, decimal_places=2, help_text="Eligible net merchandise order amount")
  - `commission_rate_applied` (DecimalField, max_digits=6, decimal_places=2, help_text="Historical commission rate locked at conversion time")
  - `commission_amount` (DecimalField, max_digits=10, decimal_places=2, help_text="Calculated partner commission")
  - `status` (CharField, max_length=20, choices: `pending_review`, `approved`, `paid`, `voided_refund`, default `pending_review`)
  - `payout_reference` (CharField, max_length=100, blank=True, help_text="Remittance reference or accounting payment batch voucher ID")
  - `paid_at` (DateTimeField, null=True, blank=True, help_text="Timestamp of commission disbursement")
  - `notes` (TextField, blank=True, help_text="Audit notes, reason for void/rejection, or clawback details")
- **Constraints & Indexes**:
  - Unique constraint on `["tenant", "number"]`
  - Unique constraint on `["tenant", "affiliate", "order"]` (prevents double-crediting an order)
  - Index on `["tenant", "status", "created_at"]`
- **Verified FKs**: `core.Tenant`, `ecommerce.AffiliatePartner`, `ecommerce.EcommerceOrder`, `ecommerce.CustomerAccountProfile`.

### Model 4: `SeoMetadataRule` [Prefix: `ESEO`]
- **Purpose**: Technical SEO automation rule engine configuring dynamic meta titles, meta descriptions, Schema.org JSON-LD structured data, XML sitemap indexing controls, robots directives, and SERP focus keyword tracking across categories, products, or custom storefront pages.
- **Inherits**: `TenantNumbered` (`apps/ecommerce/models/_base.py`)
- **Key Fields & Choices**:
  - `tenant` (FK `core.Tenant`, on_delete=CASCADE)
  - `number` (CharField, `ESEO-XXXXX`, auto-generated)
  - `name` (CharField, max_length=120, help_text="Administrative label, e.g. 'Footwear Category Dynamic Meta Rule'")
  - `rule_type` (CharField, max_length=25, choices: `global_default`, `category_template`, `product_template`, `custom_url`, default `product_template`)
  - `target_category` (FK `ecommerce.StoreCategory`, on_delete=SET_NULL, null=True, blank=True, related_name="seo_rules", help_text="Target category scope for category rules")
  - `target_product` (FK `ecommerce.CatalogProduct`, on_delete=SET_NULL, null=True, blank=True, related_name="seo_rules", help_text="Specific product override for custom product rules")
  - `url_path_pattern` (CharField, max_length=255, blank=True, help_text="URL pattern for custom pages, e.g. '/promotions/summer-sale/'")
  - `meta_title_template` (CharField, max_length=200, help_text="SEO Title template supporting tokens: {product_name}, {brand}, {category}, {price}, {site_name}")
  - `meta_description_template` (TextField, help_text="Meta Description template supporting dynamic variable tokens")
  - `json_ld_schema_type` (CharField, max_length=30, choices: `Product`, `BreadcrumbList`, `Organization`, `WebSite`, `FAQPage`, `None`, default `Product`)
  - `canonical_url_override` (URLField, blank=True, help_text="Custom canonical URL if different from request URL")
  - `og_title` (CharField, max_length=200, blank=True, help_text="OpenGraph title for social media sharing")
  - `og_description` (TextField, blank=True, help_text="OpenGraph description for social snippets")
  - `og_image_url` (URLField, blank=True, help_text="Social preview image link")
  - `robots_directive` (CharField, max_length=30, choices: `index_follow`, `noindex_follow`, `noindex_nofollow`, `index_nofollow`, default `index_follow`)
  - `sitemap_included` (BooleanField, default=True, help_text="Include matching pages in dynamic XML sitemap generation")
  - `sitemap_priority` (DecimalField, max_digits=3, decimal_places=2, default=Decimal("0.80"), help_text="Sitemap crawl priority from 0.00 to 1.00")
  - `sitemap_changefreq` (CharField, max_length=15, choices: `always`, `hourly`, `daily`, `weekly`, `monthly`, `yearly`, `never`, default `weekly`)
  - `target_keyword` (CharField, max_length=100, blank=True, help_text="Primary focus keyword for organic rank monitoring")
  - `tracked_rank_position` (PositiveIntegerField, null=True, blank=True, help_text="Monitored search engine SERP rank position")
  - `rank_tracked_at` (DateTimeField, null=True, blank=True, help_text="Timestamp of latest SERP rank check")
  - `is_active` (BooleanField, default=True)
- **Constraints & Indexes**:
  - Unique constraint on `["tenant", "number"]`
  - Index on `["tenant", "is_active", "rule_type"]`
  - Index on `["tenant", "target_keyword"]`
- **Verified FKs**: `core.Tenant`, `ecommerce.StoreCategory`, `ecommerce.CatalogProduct`.

---

## 6. Belongs to Sibling Sub-modules (Parked, Not Scoped Here)

- **9.1 Product Catalog Management**: Category hierarchies, variants, product relationship graphs (`EPRD`, `PVR`, `ECAT`, `PRL`). *(Built)*
- **9.2 Inventory & Stock Management**: Warehouse fulfillment centers, ATP inventory allocations, backorder policies, multi-channel stock sync (`EFC`, `EAL`, `EBK`, `ESYN`). *(Built)*
- **9.3 Pricing & Promotion Engine**: Dynamic customer pricing, coupon discounts, flash sales, competitor monitoring (`EDPR`, `ECPN`, `EFLS`, `ECPM`). *(Built)*
- **9.4 Shopping Cart & Checkout**: Cart sessions, multi-step checkout orchestration, carrier shipping, payment configs (`ECRT`, `ECKS`, `ESHP`, `EPMC`). *(Built)*
- **9.5 Order Management System**: Order routing, fulfillment dispatches, return merchandise authorizations (`EORD`, `EFUL`, `ERMA`). *(Built)*
- **9.6 Customer Account & Profile**: Customer account profiles, address books, wishlists, GDPR DSAR requests (`ECAP`, `ECAD`, `EWSL`, `ECPR`). *(Built)*
- **9.7 Search & Product Discovery**: Autocomplete dictionary, faceted filtering, search boost/pin/block merchandising rules, query telemetry (`ESYN`, `ESFC`, `ESMR`, `ESQL`). *(Built)*
- **9.8 Personalization & Recommendation Engine**: Clickstream behavioral telemetry, collaborative/content recommendation strategies, dynamic hero banners, RFM audience segments (`ESEG`, `EREC`, `EPEX`, `ESBE`). *(Built)*
- **9.9 Content Management System (CMS)**: Visual page builder, blog/editorial articles, media library assets, promotional landing pages. *(Sibling 9.9)*
- **9.11 Marketplace & Multi-Vendor**: Vendor application onboarding, seller KYC, vendor catalog moderation, seller-specific commission splits and marketplace payouts. *(Sibling 9.11 — note: 9.11 governs multi-seller marketplace commissions; 9.10 governs marketing affiliate & referral advocacy)*
- **9.12 Subscription & Recurring Commerce**: Recurring billing plans, subscription box rotation, dunning management, churn prediction. *(Sibling 9.12)*
- **9.13 Reviews & User-Generated Content**: Post-purchase review requests, star rating displays, customer photo/video UGC galleries, customer Q&A forums. *(Sibling 9.13)*
- **9.15 Analytics & Business Intelligence**: Advanced multi-touch attribution modeling (first-touch, last-touch, linear, W-shaped attribution curves), blended customer acquisition cost (CAC), LTV cohort analysis. *(Sibling 9.15)*

---

## 7. Deferred (Later Passes / External Integrations)

- **Outbound Email Transport Dispatcher**: Direct SMTP, SendGrid, Amazon SES, or Postmark delivery worker daemons. The `MarketingCampaign` model defines all recipient targeting, templates, and deliverability metrics; physical network dispatch is handled by background worker tasks.
- **SMS Gateway Connectors**: Direct integration with Twilio, Sinch, or Telnyx APIs for physical cellular transmission.
- **Mobile Push Network Daemons**: Direct WebSocket or APNs (Apple Push Notification service) and FCM (Firebase Cloud Messaging) transmission gateways.
- **Live Social Commerce API Webhooks (Meta Graph API & TikTok Seller Central)**: Automated bidirectional sync daemons pushing real-time inventory adjustments and pulling native TikTok/Instagram in-app checkouts. Social catalog syndication feeds are handled via standard XML/RSS views in 9.10.
- **Automated SERP Scraping & Search Console Crawlers**: Automated headless browser scraping or direct Google Search Console API synchronization for real-time rank position tracking. Manual and webhook-updated rank positions are fully supported in `SeoMetadataRule`.
- **Automated PayPal / Wise Mass Payout Webhooks**: Direct banking API execution for affiliate disbursements. Commissions are calculated, approved, and marked as paid in `AffiliateReferralConversion`, with financial voucher posting in Module 2 (`apps/accounting`).
