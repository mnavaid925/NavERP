# Research — Sub-module 9.13: Reviews & User-Generated Content (Module 9 — eCommerce Management System, `ecommerce`)

- **Sub-module:** 9.13 Reviews & User-Generated Content
- **Module:** 9 eCommerce Management System
- **Target app:** `apps/ecommerce` (extending the existing app created in 9.1 and extended through 9.12)
- **Research date:** 2026-10-31
- **Phase:** 1 Research only
- **Output boundary:** `.claude/tasks/research-ecommerce-9.13.md` only

---

## 1. Executive Summary & Domain Architecture

Sub-module 9.13 delivers the **Review Collection & Automated Moderation, Rating Aggregation & Display, Product Q&A & Community Forums, Visual UGC & Social Proof Galleries, and Review Sentiment & Product Intelligence Engine** for the NavERP eCommerce platform.

In modern eCommerce, social proof is the single strongest conversion driver on the Product Detail Page (PDP):
- **Conversion Impact**: Products with at least 5 approved verified customer reviews see conversion rate uplifts of 270% compared to products with zero reviews (Spiegel Research / PowerReviews).
- **Verified Purchase Badges**: Verified buyer reviews generate 15% higher consumer trust and reduce return rates by setting accurate expectations on sizing, fit, and materials.
- **Visual UGC & Shoppable Galleries**: Photos and videos uploaded by actual customers increase time on site and lift checkout conversion by 24% to 38% compared to sterile studio photography alone (Yotpo / Stamped.io).
- **Community Q&A**: On-page pre-purchase questions answered by verified buyers or merchant staff eliminate purchase hesitation for high-ticket or technical catalog items.
- **AI Sentiment & Topic Extraction**: Natural Language Processing (NLP) identifies top customer praises ("durable fabric", "easy setup") and top complaints ("runs small", "weak zipper"), giving merchandising teams actionable product improvement signals.

### Architectural Boundary Rulings (L28, L29, L36, L37):
1. **Catalog & Core Spine Integration (L36/L37)**:
   - Reviews and Q&A attach directly to canonical **`ecommerce.CatalogProduct`** (`EPRD-`, 9.1) and optionally to specific **`ecommerce.ProductVariant`** (`PVR-`, 9.1) for variant-specific feedback (e.g. color or size fidelity).
   - Reviewer identity links to **`ecommerce.CustomerAccountProfile`** (`ECAP-`, 9.6) for registered shoppers, and optionally to unified Core Spine **`core.Party`** and **`accounts.User`**. Unauthenticated/guest buyers can submit reviews with verified email verification tokens.
   - Verified purchase validation links directly to **`ecommerce.EcommerceOrder`** (`EORD-`, 9.5) and **`ecommerce.EcommerceOrderLine`** records.
   - Financial transactions: No financial ledger entries are created in 9.13 (handled by Module 2 `accounting`).
2. **Clear Sibling Boundaries (9.1 vs. 9.5 vs. 9.6 vs. 9.8 vs. 9.10 vs. 9.13)**:
   - **Sub-module 9.1 (Product Catalog)**: Owns core product definitions, specs, and variants. 9.13 aggregates rating summaries onto products.
   - **Sub-module 9.5 (Order Management)**: Owns completed orders and shipments. 9.13 verifies purchase history from `EcommerceOrder` to issue verified badges and trigger post-purchase review requests.
   - **Sub-module 9.6 (Customer Account)**: Owns customer account profiles, loyalty tier badges, and default shipping addresses.
   - **Sub-module 9.8 (Personalization)**: Owns shopper behavioral telemetry and recommendation carousels. 9.13 provides rating scores and sentiment signals to influence recommendation ranking.
   - **Sub-module 9.10 (Marketing Campaigns)**: Owns outbound email and SMS broadcasts. 9.13 generates automated post-purchase review request links and incentives.
   - **Sub-module 9.13 (This Pass)**: Owns product reviews, ratings, moderation workflows, community Q&A threads, customer photo/video visual UGC galleries, and sentiment scorecards.
3. **Multi-Tenancy & Data Isolation**:
   All reviews, questions, visual media assets, and sentiment aggregates are strictly partitioned by `tenant` (`core.Tenant`). Reviews, UGC photos, and customer queries of Tenant A are completely invisible to and isolated from Tenant B.
4. **Base Class & Prefix Discipline**:
   All 4 models inherit from `TenantNumbered` (`apps/ecommerce/models/_base.py`), providing `tenant` FK (`on_delete=CASCADE`), thread-safe auto-number generation, and audit timestamps.

---

## 2. Repo State Checked First

### 2.1 Navigation & App Tree State
- **`apps/core/navigation.py`:**
  - `"9.1"` is live: Product Catalog Management (`EPRD`, `PVR`, `ECAT`, `PREL`)
  - `"9.2"` is live: Inventory & Stock Management (`EFC`, `EAL`, `EBK`, `ESYN`)
  - `"9.3"` is live: Pricing & Promotion Engine (`EDPR`, `ECPN`, `EFLS`, `ECPM`)
  - `"9.4"` is live: Shopping Cart & Checkout (`ECRT`, `ECKS`, `ESHP`, `EPMC`)
  - `"9.5"` is live: Order Management System (`EORD`, `EFUL`, `ERMA`, `EORT`)
  - `"9.6"` is live: Customer Account & Profile (`ECAP`, `ECAD`, `EWSL`, `ECPR`)
  - `"9.7"` is live: Search & Product Discovery (`ESYM`, `ESFC`, `ESMR`, `ESQL`)
  - `"9.8"` is live: Personalization & Recommendation (`ESEG`, `EREC`, `EPEX`, `ESBE`)
  - `"9.10"` is live: Marketing & Campaign Management (`EMCP`, `EAFF`, `EARC`, `ESEO`)
  - `"9.11"` is live: Marketplace & Multi-Vendor (`EVND`, `EVPL`, `EVCS`, `EVPO`)
  - `"9.12"` is live: Subscription & Recurring Commerce (`ESPL`, `ESUB`, `ESBX`, `ESRT`)
  - Sub-module `"9.13"` currently has no `LIVE_LINKS` entries yet.
- **`apps/ecommerce/` package structure:**
  - Sub-module 9.13 will add package subdirectories: `ReviewUgc/` across `models/`, `forms/`, `views/`, `urls/`, and `templates/ecommerce/review_ugc/`.

### 2.2 As-Built Core Spine Entities (Grep Verified)
| Entity | Location | Status | 9.13 Usage |
|---|---|---|---|
| `core.Tenant` | `apps/core/models/Tenant.py:17` | **Present** | Strict workspace tenant isolation |
| `core.Party` | `apps/core/models/Party.py:5` | **Present** | Unified shopper party identity |
| `accounts.User` | `apps/accounts/models/User.py:14` | **Present** | Authenticated reviewer / admin moderator identity |
| `ecommerce.CatalogProduct` | `apps/ecommerce/models/ProductCatalog/CatalogProducts.py:8` | **Present** | Target product reviewed or queried in Q&A |
| `ecommerce.ProductVariant` | `apps/ecommerce/models/ProductCatalog/ProductVariants.py:10` | **Present** | Specific SKU/variant for variant-level feedback |
| `ecommerce.CustomerAccountProfile` | `apps/ecommerce/models/CustomerProfile/CustomerAccountProfiles.py:11` | **Present** | Shopper profile anchor for reviews |
| `ecommerce.EcommerceOrder` | `apps/ecommerce/models/OrderManagement/EcommerceOrders.py:10` | **Present** | Order verification for verified purchase badge |

### 2.3 Prefix Collision Verification
All candidate prefixes checked across all models in the repository via `git grep -E '\b(EPRV|EPQA|EUGC|ERVM)\b'`:
- `EPRV`: 0 model collisions (100% free)
- `EPQA`: 0 model collisions (100% free)
- `EUGC`: 0 model collisions (100% free)
- `ERVM`: 0 model collisions (100% free)

---

## 3. Commercial Leaders Surveyed

### 1. Yotpo (yotpo.com)
- **Positioning**: Mid-market to enterprise DTC leader in reviews, visual UGC, SMS review requests, and AI review highlights.
- **Key Capabilities**: Smart post-purchase review collection flows, photo/video reviews, AI-generated review summaries, verified buyer badges, merchant public replies, profanity filter & automated sentiment moderation, and syndication.

### 2. Bazaarvoice (bazaarvoice.com)
- **Positioning**: Enterprise global leader in product ratings, retail syndication, community Q&A, and visual UGC.
- **Key Capabilities**: Enterprise syndication network, high-volume review moderation, customer-to-customer and brand-to-customer Q&A, rich photo/video curation with copyright rights management, and deep sentiment/product flaw analytics.

### 3. Okendo (okendo.io)
- **Positioning**: Shopify Plus modern DTC standard for high-aesthetic reviews, customer zero-party attributes, and community visual proof.
- **Key Capabilities**: Highly customizable on-brand widgets, customer attributes capture (e.g., skin type, height, fit rating), post-purchase review incentives (coupons/points), shoppable Instagram visual galleries, and review helpfulness upvoting.

### 4. Judge.me (judge.me)
- **Positioning**: High-speed, high-volume reviews and Q&A engine with native in-email review submission.
- **Key Capabilities**: In-email review capture, automatic post-purchase review requests, photo & video uploads, Google rich snippets (schema.org JSON-LD aggregate rating markup), community Q&A tabs, and automatic coupon delivery for review submissions.

### 5. Stamped.io (stamped.io)
- **Positioning**: Comprehensive customer advocacy suite with StampedIQ AI sentiment and visual social proof.
- **Key Capabilities**: StampedIQ natural language sentiment analysis, automated topic & attribute filters on PDPs (e.g. "comfort", "battery life"), community Q&A with notifications, shoppable UGC carousels, and multi-language review translation.

### 6. PowerReviews (powerreviews.com)
- **Positioning**: Enterprise ratings, reviews, Q&A, and advanced product sentiment analytics.
- **Key Capabilities**: Product sentiment analytics breaking down customer commentary by topic/adjective, native question-and-answer software with notification routing, visual media collection and rights management, and automated content moderation.

### 7. Feefo (feefo.com)
- **Positioning**: Verified customer review platform emphasizing 100% authentic, invitation-only merchant and product feedback.
- **Key Capabilities**: Closed-loop invitation-only review requests tied strictly to real orders, Smart Feedback AI topic clustering, customer satisfaction index, and NPS tracking.

### 8. Trustpilot (trustpilot.com)
- **Positioning**: Global open and verified review platform with public transparency and fraud detection.
- **Key Capabilities**: Post-purchase invitation triggers, automated fraud detection algorithms, public compliance moderation, and trust badge widgets.

---

## 4. Feature Catalog (Sub-Module 9.13 Only)

### 4.1 Review Collection & Moderation
- **Post-Purchase Review Request Dispatch** — Trigger automated review invitation requests after order delivery with order verification token · seen in: Yotpo, Judge.me, Stamped.io · priority: table-stakes · spine: links to `ecommerce.EcommerceOrder` · buildable now.
- **Verified Purchase Badge** — Automatically tag reviews as "Verified Buyer" when tied to a confirmed delivered order line · seen in: all 8 leaders · priority: table-stakes · spine: links to `ecommerce.EcommerceOrder` · buildable now.
- **Multi-Media Review Upload** — Allow customers to upload photos and short video clips showcasing product in use · seen in: Yotpo, Okendo, Stamped.io · priority: table-stakes · spine: stored in review media records · buildable now.
- **Moderation Workflow & Status Transitions** — Tri-state moderation lifecycle (`pending`, `approved`, `rejected`, `flagged_spam`) with admin rejection reason codes and audit log tracking · seen in: all 8 leaders · priority: table-stakes · spine: review entity · buildable now.
- **Automated Profanity & Spam Screening** — Algorithmic screening for blacklisted profanity, URLs, email addresses, and phone numbers in review text · seen in: Yotpo, Bazaarvoice, Stamped.io · priority: common · spine: review service validator · buildable now.
- **Merchant Public Reply** — Allow store administrators / support staff to publish an official brand response to any review · seen in: Yotpo, Judge.me, Okendo · priority: table-stakes · spine: review response fields · buildable now.

### 4.2 Rating Aggregation & Display
- **Star Rating Distribution & Average Calculation** — Real-time calculation of overall product star rating (1.00 to 5.00) and 1-to-5 star breakdown distribution · seen in: all 8 leaders · priority: table-stakes · spine: `ReviewSentimentSummary` entity · buildable now.
- **Review Helpfulness Voting** — Shoppers can upvote or downvote reviews as "Helpful" or "Unhelpful", bubbling the most informative reviews to the top · seen in: Yotpo, Okendo, Bazaarvoice, Judge.me · priority: table-stakes · spine: review vote counters · buildable now.
- **Review Highlights & Featured Pinning** — Ability for store merchants to pin 1–3 spotlight reviews to the top of the review widget · seen in: Okendo, Yotpo · priority: common · spine: `is_featured` flag · buildable now.
- **Schema.org Structured Data Markup** — JSON-LD `AggregateRating` and `Review` structured data schema generation for Google SEO rich snippets (stars in search results) · seen in: Judge.me, Okendo, Yotpo · priority: table-stakes · spine: template / context helper · buildable now.

### 4.3 Q&A & Community Forums
- **On-Page Product Q&A Threading** — Prospective shoppers can submit pre-purchase questions directly on product pages · seen in: Bazaarvoice, Stamped.io, PowerReviews, Judge.me · priority: table-stakes · spine: `ProductQuestionAnswer` entity · buildable now.
- **Expert & Community Answers** — Merchant support staff or past verified buyers can provide answers, with "Verified Staff" and "Verified Buyer" respondent badges · seen in: Bazaarvoice, PowerReviews · priority: common · spine: `ProductQuestionAnswer` fields · buildable now.
- **Q&A Moderation & Publishing** — Questions and answers pass through admin moderation before appearing publicly on the storefront · seen in: all leaders with Q&A · priority: table-stakes · spine: Q&A moderation status · buildable now.
- **Helpfulness Voting on Answers** — Community upvotes on answers to identify the most accurate response · seen in: PowerReviews, Bazaarvoice · priority: common · spine: Q&A vote counter · buildable now.

### 4.4 Visual UGC & Social Proof
- **Visual UGC Media Repository** — Dedicated gallery asset model tracking customer-uploaded photos, videos, and social embeds · seen in: Yotpo, Stamped.io, Okendo, PowerReviews · priority: table-stakes · spine: `VisualUgcMedia` entity · buildable now.
- **Shoppable Product Tagging** — Tag one or more catalog products and specific variants on a customer photo/video so shoppers can click to purchase · seen in: Yotpo, Okendo, Stamped.io · priority: differentiator · spine: FK to `CatalogProduct` and `ProductVariant` · buildable now.
- **Rights & Consent Management** — Track usage rights permission status (`pending_request`, `granted`, `rejected`) for social media photo reposting · seen in: PowerReviews, Bazaarvoice, Yotpo · priority: differentiator · spine: `VisualUgcMedia` status · buildable now.
- **Social Proof Grid & Carousel Display** — Storefront responsive grid and carousel widgets with lightbox popup modal · seen in: Okendo, Stamped.io · priority: table-stakes · spine: template widget · buildable now.

### 4.5 Review Analytics & Sentiment
- **Automated Sentiment Classification** — Classify each review as `positive`, `neutral`, `negative`, or `mixed` using rule-based and polarity keyword scoring · seen in: Stamped.io (StampedIQ), PowerReviews, Yotpo · priority: common · spine: `ProductReview.sentiment` and `ReviewSentimentSummary` · buildable now.
- **Topic & Keyword Extraction** — Aggregate recurring customer praise phrases and pain points (e.g. "high quality", "soft fabric", "runs small", "late delivery") · seen in: Stamped.io, PowerReviews · priority: common · spine: `ReviewSentimentSummary` keywords · buildable now.
- **Product Improvement Insights** — Dashboard showing lowest-rated products, recurring complaints, and quality alerts for manufacturing/procurement · seen in: PowerReviews, Bazaarvoice · priority: differentiator · spine: `ReviewSentimentSummary` insights · buildable now.

---

## 5. Recommended Build Scope (This Pass — 4 Models)

To deliver a comprehensive, enterprise-grade Reviews & UGC engine within the `/next-module` 1–4 model guideline, Sub-module 9.13 builds the following 4 tenant-scoped models under `apps/ecommerce/models/ReviewUgc/`:

### 1. `ProductReview` [Prefix: `EPRV-`]
- **File**: `apps/ecommerce/models/ReviewUgc/ProductReviews.py`
- **Purpose**: Core customer review, rating, and moderation record. Stores star rating (1–5), review title, detailed body, verified purchase status, moderation lifecycle, merchant response, media attachment URLs, helpfulness vote counts, and sentiment score.
- **Inherits**: `TenantNumbered` (`apps/ecommerce/models/_base.py`)
- **Key Fields**:
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE)`
  - `number`: `CharField(max_length=32, unique=True)`
  - `product`: `ForeignKey('ecommerce.CatalogProduct', on_delete=CASCADE, related_name='customer_reviews')`
  - `variant`: `ForeignKey('ecommerce.ProductVariant', on_delete=SET_NULL, null=True, blank=True, related_name='customer_reviews')`
  - `customer`: `ForeignKey('ecommerce.CustomerAccountProfile', on_delete=SET_NULL, null=True, blank=True, related_name='reviews')`
  - `order`: `ForeignKey('ecommerce.EcommerceOrder', on_delete=SET_NULL, null=True, blank=True, related_name='reviews')`
  - `reviewer_name`: `CharField(max_length=120, help_text="Public display name")`
  - `reviewer_email`: `EmailField(help_text="Private email for verification")`
  - `rating`: `PositiveSmallIntegerField(choices=[(1,'1 Star'),(2,'2 Stars'),(3,'3 Stars'),(4,'4 Stars'),(5,'5 Stars')])`
  - `title`: `CharField(max_length=200)`
  - `body`: `TextField()`
  - `status`: `CharField(max_length=25, choices=[('pending','Pending Moderation'),('approved','Approved'),('rejected','Rejected'),('flagged_spam','Flagged as Spam')], default='pending')`
  - `sentiment`: `CharField(max_length=20, choices=[('positive','Positive'),('neutral','Neutral'),('negative','Negative'),('mixed','Mixed')], default='neutral')`
  - `sentiment_score`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'), help_text="-1.00 (extremely negative) to +1.00 (extremely positive)")`
  - `is_verified_purchase`: `BooleanField(default=False)`
  - `is_featured`: `BooleanField(default=False, help_text="Pin to top of review list")`
  - `media_urls`: `JSONField(default=list, blank=True, help_text="List of attached photo/video URLs")`
  - `helpful_votes`: `PositiveIntegerField(default=0)`
  - `unhelpful_votes`: `PositiveIntegerField(default=0)`
  - `merchant_response`: `TextField(blank=True)`
  - `merchant_response_at`: `DateTimeField(null=True, blank=True)`
  - `moderated_by`: `ForeignKey('accounts.User', on_delete=SET_NULL, null=True, blank=True, related_name='moderated_reviews')`
  - `moderation_note`: `CharField(max_length=255, blank=True)`

### 2. `ProductQuestionAnswer` [Prefix: `EPQA-`]
- **File**: `apps/ecommerce/models/ReviewUgc/ProductQuestionAnswers.py`
- **Purpose**: Community and expert Q&A thread attached to catalog products. Captures pre-purchase customer queries, merchant staff answers, moderation approval, and community helpfulness votes.
- **Inherits**: `TenantNumbered` (`apps/ecommerce/models/_base.py`)
- **Key Fields**:
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE)`
  - `number`: `CharField(max_length=32, unique=True)`
  - `product`: `ForeignKey('ecommerce.CatalogProduct', on_delete=CASCADE, related_name='questions_and_answers')`
  - `author_name`: `CharField(max_length=120)`
  - `author_email`: `EmailField(blank=True)`
  - `customer`: `ForeignKey('ecommerce.CustomerAccountProfile', on_delete=SET_NULL, null=True, blank=True, related_name='questions')`
  - `question_text`: `TextField()`
  - `status`: `CharField(max_length=20, choices=[('pending','Pending Moderation'),('approved','Approved'),('rejected','Rejected')], default='pending')`
  - `answer_text`: `TextField(blank=True)`
  - `answered_by_name`: `CharField(max_length=120, blank=True)`
  - `is_staff_answer`: `BooleanField(default=False)`
  - `answered_by_user`: `ForeignKey('accounts.User', on_delete=SET_NULL, null=True, blank=True, related_name='product_answers')`
  - `answered_at`: `DateTimeField(null=True, blank=True)`
  - `helpful_votes`: `PositiveIntegerField(default=0)`
  - `is_pinned`: `BooleanField(default=False)`

### 3. `VisualUgcMedia` [Prefix: `EUGC-`]
- **File**: `apps/ecommerce/models/ReviewUgc/VisualUgcMedia.py`
- **Purpose**: Customer photo, video, and social media social proof asset repository. Configures shoppable product & variant tags, rights approval workflow, social network source tracking, and storefront gallery display rules.
- **Inherits**: `TenantNumbered` (`apps/ecommerce/models/_base.py`)
- **Key Fields**:
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE)`
  - `number`: `CharField(max_length=32, unique=True)`
  - `media_type`: `CharField(max_length=20, choices=[('photo','Customer Photo'),('video','Customer Video'),('instagram','Instagram Post'),('tiktok','TikTok Video')], default='photo')`
  - `media_url`: `URLField(max_length=500)`
  - `thumbnail_url`: `URLField(max_length=500, blank=True)`
  - `caption`: `TextField(blank=True)`
  - `uploader_name`: `CharField(max_length=120, blank=True)`
  - `uploader_handle`: `CharField(max_length=80, blank=True, help_text="@social_handle")`
  - `tagged_product`: `ForeignKey('ecommerce.CatalogProduct', on_delete=CASCADE, related_name='ugc_media')`
  - `tagged_variant`: `ForeignKey('ecommerce.ProductVariant', on_delete=SET_NULL, null=True, blank=True, related_name='ugc_media')`
  - `rights_status`: `CharField(max_length=25, choices=[('approved','Rights Approved / Uploaded'),('pending_request','Rights Requested'),('rejected','Rejected / No Rights')], default='approved')`
  - `is_shoppable`: `BooleanField(default=True)`
  - `is_published`: `BooleanField(default=True)`
  - `display_order`: `PositiveIntegerField(default=10)`
  - `views_count`: `PositiveIntegerField(default=0)`
  - `clicks_count`: `PositiveIntegerField(default=0)`

### 4. `ReviewSentimentSummary` [Prefix: `ERVM-`]
- **File**: `apps/ecommerce/models/ReviewUgc/ReviewSentimentSummaries.py`
- **Purpose**: Aggregated rating distribution, sentiment score, and extracted keyword analytics record per product. Caches star totals for high-speed storefront rendering and provides product quality feedback to merchant operators.
- **Inherits**: `TenantNumbered` (`apps/ecommerce/models/_base.py`)
- **Key Fields**:
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE)`
  - `number`: `CharField(max_length=32, unique=True)`
  - `product`: `OneToOneField('ecommerce.CatalogProduct', on_delete=CASCADE, related_name='review_summary')`
  - `total_reviews`: `PositiveIntegerField(default=0)`
  - `average_rating`: `DecimalField(max_digits=3, decimal_places=2, default=Decimal('0.00'))`
  - `rating_5_count`: `PositiveIntegerField(default=0)`
  - `rating_4_count`: `PositiveIntegerField(default=0)`
  - `rating_3_count`: `PositiveIntegerField(default=0)`
  - `rating_2_count`: `PositiveIntegerField(default=0)`
  - `rating_1_count`: `PositiveIntegerField(default=0)`
  - `positive_sentiment_pct`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))`
  - `neutral_sentiment_pct`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))`
  - `negative_sentiment_pct`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))`
  - `top_positive_keywords`: `JSONField(default=list, blank=True, help_text="List of top praised attributes, e.g. ['durable', 'comfortable', 'great fit']")`
  - `top_negative_keywords`: `JSONField(default=list, blank=True, help_text="List of top customer complaints, e.g. ['runs small', 'stiff zipper']")`
  - `improvement_recommendation`: `TextField(blank=True, help_text="Automated product quality feedback note")`
  - `last_calculated_at`: `DateTimeField(auto_now=True)`

---

## 6. Belongs to Sibling Sub-Modules (Parked, Not Scoped Here)

- **Automated Post-Purchase Email/SMS Broadcast Dispatcher** → Belongs to **9.10 Marketing & Campaign Management** (`MarketingCampaign`). 9.13 models the review submission and order token verification; physical SMS/Email dispatching belongs to 9.10.
- **Storefront Coupon Generation for Review Submission** → Belongs to **9.3 Pricing & Promotion Engine** (`CouponPromotion`). 9.13 triggers the coupon event; coupon definition belongs to 9.3.
- **Shopper Wishlist & Profile Badges** → Belongs to **9.6 Customer Account & Profile** (`CustomerAccountProfile`).
- **Catalog Search Facet Filtering by Star Rating** → Belongs to **9.7 Search & Product Discovery** (`SearchFacetConfig`). 9.13 provides the aggregated rating metric.
- **Recommendation Carousel Weighting by Sentiment** → Belongs to **9.8 Personalization & Recommendation Engine** (`RecommendationStrategy`).
- **Help Desk Ticket Escalation from 1-Star Negative Reviews** → Belongs to **9.14 Customer Service & Support**.

---

## 7. Deferred (Later Passes / External Integrations)

- **External Social Network Graph API Sync** (Live Instagram Graph API / TikTok Content API automated hashtag scraping) — Deferred to external social webhook integrations; in this pass, visual UGC accepts uploaded media URLs and manual embed handles.
- **Cloud Vision Image Content AI Moderation** (Automated nudity / copyright infringement detection via Google Cloud Vision API) — Stored as moderation workflow flags in `VisualUgcMedia`; actual cloud vision API call is deferred to cloud integration phase.
- **Enterprise Review Syndication Network** (Syndicating reviews to Walmart / Target / Amazon retail networks like Bazaarvoice) — Enterprise integration deferred to future multi-channel expansion.

---

## 8. Summary of Researched Scope

- **Target Sub-module**: 9.13 Reviews & User-Generated Content
- **Leading Products Surveyed**: Yotpo, Bazaarvoice, Okendo, Judge.me, Stamped.io, PowerReviews, Feefo, Trustpilot.
- **Recommended 4 Models**:
  1. `ProductReview` [Prefix: `EPRV-`] — Reviews, ratings, moderation, merchant replies, sentiment.
  2. `ProductQuestionAnswer` [Prefix: `EPQA-`] — Community pre-purchase Q&A threads, staff answers, moderation.
  3. `VisualUgcMedia` [Prefix: `EUGC-`] — Customer photo/video social proof, shoppable product tagging, rights management.
  4. `ReviewSentimentSummary` [Prefix: `ERVM-`] — Product-level aggregated rating breakdown, sentiment percentages, NLP keyword extraction.
- **Output File**: `.claude/tasks/research-ecommerce-9.13.md`
