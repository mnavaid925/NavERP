# Review Findings — Sub-module 9.8: Personalization & Recommendation Engine (Module 9: eCommerce Management System, `ecommerce`)

- **Sub-module:** 9.8 Personalization & Recommendation Engine
- **Module:** 9 eCommerce Management System
- **App:** `apps/ecommerce`
- **Date:** 2026-10-30
- **Changeset:** `acaa1a3747559cb7114c75a4bbf9af5f2ea048b0` (BASE) ... `HEAD`
- **Review Passes:**
  1. `code-reviewer` — Completed
  2. `explorer` — Completed
  3. `frontend-reviewer` — Completed
  4. `performance-reviewer` — Completed
  5. `qa-smoke-tester` — Completed (All 12 smoke test scenarios passed)
  6. `security-reviewer` — Completed

---

## Consolidated & Prioritized Findings for Phase 5 (`code-fixer`)

### Critical Findings

- [ ] **C1** — Image Attribute Mismatch on `CatalogProduct` in Recommendations Preview
  - **Location:** `templates/ecommerce/personalization/console/partials/recommendations_preview.html:12-16`
  - **Description:** Template checks `{% if product.images.first %}` and accesses `product.images.first.image_url`. `CatalogProduct` does not have an `images` relation; product artwork is stored directly on `product.hero_image_url`. Recommended items in the console preview fall back to placeholder icons even when product artwork exists.
  - **Fix:** Update template to check `{% if product.hero_image_url %}` and render `<img src="{{ product.hero_image_url }}" alt="{{ product.name }}" class="w-full h-full object-cover">`.

- [ ] **C2** — Stored XSS via Dangerous URI Schemes in `PersonalizedExperience` URLs
  - **Location:** `apps/ecommerce/models/Personalization/PersonalizedExperiences.py:115-125`
  - **Description:** `cta_url` and `hero_image_url` on `PersonalizedExperience` accept arbitrary text without URI scheme validation, allowing `javascript:`, `data:`, or `vbscript:` payloads to be persisted and rendered directly as `href` / `src` attributes in storefront templates.
  - **Fix:** In `PersonalizedExperience.clean()`, validate that `cta_url` and `hero_image_url` do not start with `javascript:`, `data:`, or `vbscript:`, and require that they start with `/`, `http://`, `https://`, or `#`.

- [ ] **C3** — Missing Model-Level Multi-Tenant Foreign Key Validation in `clean()`
  - **Location:** `apps/ecommerce/models/Personalization/AudienceSegments.py:89-98`, `RecommendationStrategies.py:126-135`, `PersonalizedExperiences.py:115-125`
  - **Description:** While forms use `reject_foreign`, the model `clean()` methods omit tenant verification on related foreign keys (`target_category`, `target_segment`, `target_product`). Direct ORM operations or programmatic imports could link Workspace A's personalization entities to Workspace B's categories or products.
  - **Fix:** In `clean()`, assert `self.target_category.tenant_id == self.tenant_id`, `self.target_segment.tenant_id == self.tenant_id`, and `self.target_product.tenant_id == self.tenant_id`.

---

### Important Findings

- [ ] **I1** — N+1 Queries on `AudienceSegment` List View
  - **Location:** `apps/ecommerce/views/Personalization/AudienceSegments.py:19-42`
  - **Description:** `audiencesegment_list` renders `seg.target_category.name` for each row without `select_related("target_category")`, issuing an individual SQL query per displayed segment.
  - **Fix:** Add `.select_related("target_category")` to `qs` in `audiencesegment_list`.

- [ ] **I2** — N+1 Queries on `RecommendationStrategy` List View
  - **Location:** `apps/ecommerce/views/Personalization/RecommendationStrategies.py:17-40`
  - **Description:** `recommendationstrategy_list` accesses `st.target_segment.name` and `st.target_category.name` on every row without joining related models, causing up to 2 additional SQL queries per strategy.
  - **Fix:** Add `.select_related("target_segment", "target_category")` to `qs` in `recommendationstrategy_list`.

- [ ] **I3** — N+1 Queries on `PersonalizedExperience` List View
  - **Location:** `apps/ecommerce/views/Personalization/PersonalizedExperiences.py:17-40`
  - **Description:** `personalizedexperience_list` accesses `exp.target_segment.name` on every row without joining `target_segment`, causing an N+1 query regression.
  - **Fix:** Add `.select_related("target_segment", "target_category", "target_product")` to `qs` in `personalizedexperience_list`.

- [ ] **I4** — N+1 Queries on `ShopperBehaviorEvent` List & Console Views
  - **Location:** `apps/ecommerce/views/Personalization/ShopperBehaviorEvents.py:17-40`, `PersonalizationConsole.py:114`
  - **Description:** `shopperbehaviorevent_list` accesses `evt.product.name`, `evt.category.name`, and `evt.customer_profile.number`. `recent_events` in `personalization_console` also accesses `evt.product.name`. Both queries lack `select_related`.
  - **Fix:** Add `.select_related("product", "category", "customer_profile", "user")` in both views.

- [ ] **I5** — Missing Category Pre-fetch in `compute_recommendations`
  - **Location:** `apps/ecommerce/views/Personalization/PersonalizationConsole.py:23-26`
  - **Description:** `base_qs` in `compute_recommendations` does not select related `primary_category`, causing lazy loading queries when displaying products in recommendation cards.
  - **Fix:** Add `.select_related("primary_category")` to `base_qs`.

---

### Minor Findings

- [ ] **M1** — Detail View Related Queryset Optimizations
  - **Location:** `apps/ecommerce/views/Personalization/AudienceSegments.py:59-61`, `PersonalizedExperiences.py:47-51`
  - **Description:** In `audiencesegment_detail`, related `experiences` query lacks `select_related("target_segment")`.
  - **Fix:** Add `.select_related("target_segment")` to `segment.experiences` queryset.

- [ ] **M2** — Empty State Guidance Consistency in `ShopperBehaviorEvent` List
  - **Location:** `templates/ecommerce/personalization/shopperbehaviorevent/list.html:125-132`
  - **Description:** The empty state in telemetry table doesn't offer a direct link to the Personalization Workbench simulator where events can be observed.
  - **Fix:** Add an inline link to `ecommerce:personalization_console` inside the empty-state container.
