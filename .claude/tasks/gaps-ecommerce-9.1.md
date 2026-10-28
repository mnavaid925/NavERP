# Gaps Register — Sub-module 9.1: Product Catalog Management (`ecommerce`)

- **Sub-module:** 9.1 Product Catalog Management · **Module:** 9 eCommerce Management System · **App:** `apps/ecommerce`
- **Date Created:** 2026-10-29
- **Status:** Complete / Clean Baseline (0 unresolved defects, 3 documented deferred features)
- **Review Reference:** `.claude/tasks/review-ecommerce-9.1.md`

---

## 1. Review Findings Status

All 26 review findings from the 6 serial review passes (code-reviewer, explorer, frontend-reviewer, performance-reviewer, qa-smoke-tester, security-reviewer) were completely resolved and verified in Phase 5:
- **Critical (0)**: None identified.
- **Important (14)**: 14 fixed (`[x]`), 0 deferred, 0 skipped.
- **Minor (12)**: 12 fixed (`[x]`), 0 deferred, 0 skipped.

---

## 2. Documented Feature Gaps & Architectural Deferrals

### GAP-ecommerce-9.1-01: Deep Multi-Locale Translation Tables (`ProductTranslation`)
- **Owner:** Module 9 eCommerce / Core Internationalization
- **Waiting For / Blocked On:** Workspace-wide multi-language localization framework.
- **Status:** `- [~]` Deferred
- **Description:** Commercial PIM platforms (Akeneo, Pimcore) support per-locale field overrides for name, description, and marketing bullet points across N languages. For 9.1, standard UTF-8 string/text fields are provided on `CatalogProduct` and `StoreCategory`. Dedicated translation join tables will land when a cross-module localization standard is established.
- **Done When:** Per-tenant enabled locales allow creating localized product attribute rows without modifying core schema.

---

### GAP-ecommerce-9.1-02: Video Transcoding & HLS Streaming Engine
- **Owner:** Module 9 eCommerce
- **Waiting For / Blocked On:** Third-party video infrastructure (Cloudflare Stream / AWS MediaConvert).
- **Status:** `- [~]` Deferred
- **Description:** Direct video file upload and server-side FFmpeg transcoding to HLS/DASH adaptive bitrates was declined to protect application server CPU and storage. `CatalogProduct.video_url` stores embeddable URLs (YouTube, Vimeo, Cloudflare Stream).
- **Done When:** Dedicated cloud webhook integration processes background video encodes.

---

### GAP-ecommerce-9.1-03: Cloud Image Optimization & AI Background Removal Pipeline
- **Owner:** Module 9 eCommerce
- **Waiting For / Blocked On:** Cloud image transformation service (Cloudinary / Imgix / AWS Lambda).
- **Status:** `- [~]` Deferred
- **Description:** High-volume eCommerce platforms dynamically generate WebP/AVIF thumbnails at responsive breakpoints and offer automated background removal for product photography. In 9.1, URLs and asset paths are validated, with transformation handled at the edge CDN or external storage layer.
- **Done When:** Asynchronous image processing worker generates WebP/AVIF asset derivatives on upload.
