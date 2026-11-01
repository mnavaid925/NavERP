# Competitive Feature Research: eCommerce Sub-module 9.9 — Content Management System (CMS)

> **Sub-module**: 9.9 Content Management System (CMS) (`apps/ecommerce/`)  
> **Parent Module**: Module 9: eCommerce Management System  
> **Research Date**: 2026-11-01  
> **Status**: Completed — Phase 1 of Module Creation Sequence  
> **Target Models**: 4 tenant-scoped models (`CmsPage`, `BlogArticle`, `MediaAsset`, `ContentBlock`)

---

## 1. Domain Overview & Leading Products Surveyed

eCommerce Content Management Systems (CMS) bridge the gap between transactional commerce and brand storytelling. Unlike generic publishing platforms, modern retail CMS engines must seamlessly integrate catalog entities (`CatalogProduct`, `StoreCategory`), handle visual merchandising blocks, orchestrate promotional landing pages with A/B variants, manage rich media assets with CDN and SEO alt tags, and support multi-language/locale content delivery.

We surveyed 8 commercial market leaders across visual page builders, eCommerce native platforms, and headless/composable CMS engines:

1. **WordPress + WooCommerce** (Gutenberg block system, editorial workflows, media taxonomy, custom fields)
2. **Shopify Online Store 2.0** (Liquid/JSON section architecture, theme blocks, files CDN manager, native blogging)
3. **Builder.io** (Headless visual development, reusable section blocks, asset library with usage tracking)
4. **Shogun Page Builder** (eCommerce landing page visual composer, A/B split testing, conversion goal tracking)
5. **Contentful** (Structured content modeling, rich text AST, localized content field matrices)
6. **Sanity.io** (Portable text schema, real-time preview, media asset pipeline with hotspot/crop)
7. **Strapi** (Dynamic zones, component libraries, media library folders and optimization)
8. **BigCommerce Page Builder** (Widgets, drag-and-drop merchandising blocks, scheduled content release)

---

## 2. Feature Analysis by NavERP.md Bullets

### Bullet 1: Page Builder & Visual Editor
- **Commercial Precedents**: Shopify OS 2.0 sections, Builder.io visual blocks, Shogun drag-and-drop grid.
- **Industry Standard Features**:
  - Modular section architecture (Hero banners, text-over-image, feature grids, product showcases, testimonial carousels).
  - Configurable display order, responsive visibility toggles (desktop/mobile/tablet), and design theme classes.
  - Live preview canvas and responsive viewport emulation.
  - JSON-based content layout payload storing structured block configurations.
- **NavERP Reality**: Built natively using Tailwind CSS theme classes and structured `ContentBlock` records, allowing merchants to assemble dynamic pages without raw HTML.

### Bullet 2: Blog & Editorial Content
- **Commercial Precedents**: WordPress, Shopify Blog Engine, Ghost, Strapi.
- **Industry Standard Features**:
  - Article authoring with rich text/markdown editor, excerpt summaries, and reading time estimation.
  - Author attribution linked to user identity (`accounts.User`).
  - Editorial publishing workflow: `draft` -> `scheduled` -> `published` -> `archived`.
  - Tagging, categories, and SEO-friendly slug generation with unique constraints.
  - Engagement features: comment moderation toggles, social sharing metadata, featured article flags.

### Bullet 3: Landing Page & Campaign Management
- **Commercial Precedents**: Shogun, Unbounce, Instapage, HubSpot CMS.
- **Industry Standard Features**:
  - Dedicated promotional landing pages isolated from standard store navigation.
  - A/B testing variant management (control vs. variant B) with traffic split weighting.
  - Conversion goal association (link click, checkout redirect, lead capture).
  - Campaign date scheduling (auto-publish on promotional kickoff, auto-archive on expiration).
  - Complete SEO meta controls: title, description, canonical URLs, robots indexing directives (`noindex, nofollow`).

### Bullet 4: Media Library & Asset Management
- **Commercial Precedents**: Shopify Files Manager, Cloudinary DAM, WordPress Media Library, Contentful Assets.
- **Industry Standard Features**:
  - Centralized digital asset repository for product imagery, promotional banners, and marketing attachments.
  - MIME type detection, file size tracking, width/height dimensions extraction.
  - Alt-text SEO management, focal point alignment, and folder/collection taxonomy.
  - Cloud / CDN URL storage with HTTPS URL validation.
  - Reference tracking to prevent breaking live pages when assets are deleted.

### Bullet 5: Content Localization & Translation
- **Commercial Precedents**: Contentful localization, Shopify Markets multi-language, Transifex.
- **Industry Standard Features**:
  - Locale and language code tagging (ISO-639-1 / BCP-47, e.g., `en-US`, `es-ES`, `fr-FR`, `de-DE`).
  - Fallback locale inheritance (fallback to default tenant language if translation is missing).
  - Translation status workflow: `not_translated` -> `in_translation` -> `completed`.
  - Regional content variants scoped by tenant and locale.

---

## 3. Core Spine & Sibling Integration (Lessons L28, L29, L36)

- **Tenant Isolation**: Every CMS model references `core.Tenant` with `on_delete=models.CASCADE` and enforces compound unique constraints on `(tenant, slug)` and `(tenant, number)`.
- **User Identity**: Authors, editors, and uploaders anchor to `accounts.User` (`on_delete=models.SET_NULL`).
- **Product Catalog Linking**: CMS page blocks and promotional sections link to `ecommerce.CatalogProduct` (`EPRD-`, 9.1) and `ecommerce.StoreCategory` (`ECAT-`, 9.1) without duplicating catalog tables.
- **Marketing Campaign Integration**: Landing pages integrate with `ecommerce.MarketingCampaign` (`EMCP-`, 9.10) for conversion attribution.
- **No Duplicate Tables**: No custom user, party, product, or file storage backends; standard Django storage, URL references, and spine foreign keys are reused.

---

## 4. Prefix Collision Sweep & Auto-Numbering

Verified 100% collision-free across the entire NavERP repository:
- `EPAG-` (`CmsPage`) — 0 occurrences in repo
- `EBLG-` (`BlogArticle`) — 0 occurrences in repo
- `EMED-` (`MediaAsset`) — 0 occurrences in repo
- `EBLK-` (`ContentBlock`) — 0 occurrences in repo

All 4 models inherit from `TenantNumbered` (`apps/ecommerce/models/_base.py`), ensuring atomic numbering and audit timestamps.

---

## 5. Recommended Build Scope (4 Models)

### Model 1: `CmsPage` [Prefix: `EPAG-`]
- **File**: `apps/ecommerce/models/ContentManagement/CmsPages.py`
- **Purpose**: Dynamic content and landing page engine with layout templates, status workflow, SEO meta, and A/B test tracking.
- **Key Fields**:
  - `title`, `slug`, `page_type` (`standard`, `landing`, `policy`, `about`, `contact`, `homepage`)
  - `status` (`draft`, `scheduled`, `published`, `archived`)
  - `template_layout` (`full_width`, `boxed`, `sidebar_left`, `sidebar_right`, `minimal_landing`)
  - `meta_title`, `meta_description`, `canonical_url`, `is_indexable` (robots tag)
  - `content_json` (structured blocks representation for visual rendering)
  - `raw_html_body` (editorial content fallback)
  - `published_at`, `view_count`
  - `is_ab_test_active`, `ab_variant_label`, `ab_traffic_percentage`

### Model 2: `BlogArticle` [Prefix: `EBLG-`]
- **File**: `apps/ecommerce/models/ContentManagement/BlogArticles.py`
- **Purpose**: Editorial blog posts, storytelling, brand articles, and content marketing.
- **Key Fields**:
  - `title`, `slug`, `author` (FK `accounts.User`)
  - `category` (`news`, `product_spotlight`, `guides_tutorials`, `lifestyle`, `company_updates`)
  - `excerpt`, `body_markdown`
  - `featured_media` (FK `MediaAsset`)
  - `status` (`draft`, `scheduled`, `published`, `archived`)
  - `published_at`, `reading_time_minutes`, `tags`
  - `allow_comments`, `is_featured`, `view_count`

### Model 3: `MediaAsset` [Prefix: `EMED-`]
- **File**: `apps/ecommerce/models/ContentManagement/MediaAssets.py`
- **Purpose**: Centralized digital asset management for eCommerce banners, article illustrations, and documentation files.
- **Key Fields**:
  - `title`, `file_url` (with HTTP/HTTPS validation)
  - `alt_text`, `caption`
  - `media_type` (`image`, `video`, `document`, `banner`, `icon`)
  - `folder_category` (`banners`, `blog`, `pages`, `marketing`, `icons`, `uncategorized`)
  - `file_size_bytes`, `mime_type`, `width_px`, `height_px`
  - `uploaded_by` (FK `accounts.User`)

### Model 4: `ContentBlock` [Prefix: `EBLK-`]
- **File**: `apps/ecommerce/models/ContentManagement/ContentBlocks.py`
- **Purpose**: Reusable modular visual components that compose `CmsPage` layouts.
- **Key Fields**:
  - `name`, `block_type` (`hero_banner`, `feature_grid`, `product_carousel`, `testimonial`, `cta_banner`, `rich_text`, `faq_accordion`, `newsletter_signup`)
  - `headline`, `subheadline`, `body_text`
  - `media_asset` (FK `MediaAsset`)
  - `cta_label`, `cta_url`
  - `target_category` (FK `ecommerce.StoreCategory`, optional)
  - `target_product` (FK `ecommerce.CatalogProduct`, optional)
  - `bg_color_class`, `text_color_class`, `sort_order`, `is_active`

---

## 6. Out of Scope / Deferred Items
- Full headless GraphQL / Content Delivery API (Deferred to 9.19 Integration & API Ecosystem).
- Automated AI Copywriting generator (Deferred to Module 23 AI & Intelligent Automation).
- Real-time collaborative multi-user editing (Google Docs style WebSocket canvas).
- Direct CDN invalidation webhooks (Fastly/Cloudflare automated cache purges).
