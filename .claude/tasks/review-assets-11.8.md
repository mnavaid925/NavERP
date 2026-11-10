# Review Findings — Module 11.8: Warranty & Insurance Management

## 1. Code Reviewer
**Verdict:** Commit after fixing Important items.

### Important
- `apps/assets/views/AssetWarrantyInsurance/AssetWarrantyClaims.py:261` — Hand-parsed `approved_amount` from POST lacks `is_finite()`, magnitude cap, and non-negative guards (L35), allowing NaN/Infinity or out-of-range values to corrupt state or crash database save. Fix: wrap parsing with `try/except (InvalidOperation, TypeError)`, assert `approved_amt.is_finite()`, and clamp within `0 <= approved_amt <= Decimal('9999999999.99')`.
- `apps/assets/views/AssetWarrantyInsurance/AssetInsuranceClaims.py:264` — Hand-parsed `settlement_payout_amount` and `salvage_recovery_amount` from POST lack `is_finite()`, magnitude cap, and non-negative guards (L35). Fix: validate both parsed values with `.is_finite()`, non-negativity, and clamp within field magnitude (`Decimal('999999999999.99')`).
- `apps/assets/views/AssetWarrantyInsurance/AssetWarrantyClaims.py:258` — View lacks status guard to prevent settling or rejecting an already finalized claim (`settled_closed` or `rejected`). Fix: check `if claim.claim_status in ['settled_closed', 'rejected']:` and redirect with a warning message before modifying state.
- `apps/assets/views/AssetWarrantyInsurance/AssetInsuranceClaims.py:261` — View lacks status guard preventing settlement or denial on already resolved claims (`settled_paid`, `denied_disputed`, `closed`). Fix: check `if claim.claim_status in ['settled_paid', 'denied_disputed', 'closed']:` and redirect with a warning message before mutating state.
- `templates/assets/assetwarrantyinsurance/assetwarranty/detail.html:236` — Template references non-existent attribute `warranty.service_contract.provider_name` on `AssetServiceContract`, which renders blank. Fix: replace with `{{ warranty.service_contract.vendor.name }}` or `{{ warranty.service_contract.title }}`.
- `apps/assets/views/AssetWarrantyInsurance/AssetWarrantyClaims.py:161` — `asset_warranty_claim_edit` allows updating claim valuation and deductibles on claims that are already `settled_closed`, desynchronizing net recovery without recalculation. Fix: check `if claim.claim_status in ['settled_closed', 'rejected']:` and redirect with a message disallowing edits to settled claims.

### Minor
- `apps/assets/models/AssetWarrantyInsurance/AssetInsurancePolicies.py:66` — `POLICY_TYPE_CSS` maps `"business_interruption"` to `"badge-purple"`, which is not a defined palette class in `static/css/theme.css` (L33). Fix: change `"business_interruption": "badge-purple"` to `"badge-info"` or `"badge-slate"`.
- `apps/assets/views/AssetWarrantyInsurance/AssetWarrantyClaims.py:265` — `resolution_type` posted to settlement view is not validated against `AssetWarrantyClaim.RESOLUTION_TYPE_CHOICES` before saving. Fix: validate `res_type in dict(AssetWarrantyClaim.RESOLUTION_TYPE_CHOICES)` before assignment.
- `apps/assets/views/AssetWarrantyInsurance/AssetInsuranceClaims.py:273` — `settlement_method` posted to settlement view is not validated against `AssetInsuranceClaim.SETTLEMENT_METHOD_CHOICES` before saving. Fix: validate `settlement_method in dict(AssetInsuranceClaim.SETTLEMENT_METHOD_CHOICES)` before assignment.
- `apps/assets/views/AssetWarrantyInsurance/AssetWarrantyClaims.py:284` — When resolving a claim, the covering warranty status is automatically reset to `"active"` even if its `end_date` has elapsed past today. Fix: set status to `"expired"` if `claim.warranty.end_date < timezone.now().date()`, otherwise `"active"`.
- `apps/assets/views/AssetWarrantyInsurance/AssetWarranties.py:231` — `asset_warranty_renew` does not guard against renewing a voided warranty (`status == 'voided'`). Fix: verify `if warranty.status == 'voided': messages.warning(...); return redirect(...)` before renewing.

### Done Well
- Strict multi-tenancy across all layers: all four models inherit `TenantNumbered`, queries use `assets_scope` or explicit `tenant=request.tenant`, forms inherit `TenantModelForm`, and `clean()` methodically executes `reject_foreign()` on all tenant FKs.
- Clear separation of concerns and packaging: 4 models, 4 forms, 4 view modules, 4 URL modules, and 12 templates matching NavERP conventions.
- Comprehensive seeder idempotency with realistic domain test data across Acme and Globex tenants.

## 2. Explorer (Codebase & Architecture)
**Verdict:** PASS with Important items to fix.

### Important
- `apps/assets/management/commands/seed_assets.py:1752, 2006` — In commit `6659c982`, 11.9 demo data was appended inside `_seed_tenant_11_8(self, tenant)` instead of an isolated `_seed_tenant_11_9` method. Because `_seed_tenant_11_8` has an early return if `AssetWarranty.objects.filter(tenant=tenant).exists()`, existing 11.8 data causes 11.9 seeding to be bypassed. Fix: extract lines 2004–2178 into a dedicated `_seed_tenant_11_9(self, tenant)` method with its own idempotency check, wire `self._seed_tenant_11_9(tenant)` in `handle()`, and keep `_seed_tenant_11_8` strictly scoped to 11.8.
- `templates/assets/assetwarrantyinsurance/assetwarranty/detail.html:236` — Incompatible model attribute `warranty.service_contract.provider_name` renders blank. Fix: replace with `{{ warranty.service_contract.vendor.name }}` or `{{ warranty.service_contract.title }}`.

### Minor
- `apps/assets/models/AssetWarrantyInsurance/AssetInsurancePolicies.py:66` — `POLICY_TYPE_CSS` maps `"business_interruption"` to `"badge-purple"`, which is not a defined palette class in `static/css/theme.css` (L33). Fix: change `"business_interruption": "badge-purple"` to `"badge-info"` or `"badge-slate"`.
- `apps/assets/views/AssetWarrantyInsurance/AssetWarrantyClaims.py:284` — Warranty status reactivation ignores calendar expiration. Fix: set status to `"expired"` if `claim.warranty.end_date < timezone.now().date()`, otherwise `"active"`.

### Contract & Structure Verification Summary
- **Package Structure:** PASS (4 parallel packages with 4 entity files each, matching backend package convention).
- **Re-exports & `__all__`:** PASS (all 4 models, 4 forms, 34 views re-exported).
- **URL Concatenation:** PASS (literal paths precede `<int:pk>/`, no collisions).
- **Reverse URL Lookup:** PASS (96 URL tags tested, all reverse kwargs valid).
- **Context Contract:** PASS (matches frozen contract in `contract-assets-11.8.md` byte-for-byte).
- **Filter Conformance:** PASS (GET filtering before pagination, `|stringformat:"d"` PK comparisons).
- **Core Spine Reuse:** PASS (`core.Party` for providers, `accounting.Currency` global, links to `accounting.FixedAsset`).
- **Admin & Navigation:** PASS (registered in admin, `LIVE_LINKS["11.8"]` wired).
- **Migrations:** PASS (migration `0012` applied cleanly, `manage.py check` passes 100%).

## 3. Frontend Reviewer
**Verdict:** PASS — All 12 templates exhibit high adherence to NavERP frontend guidelines, `theme.css` standards, accessibility conventions, and the established design system.

### Critical
None.

### Important
None.

### Minor
- `templates/assets/assetwarrantyinsurance/{assetwarranty,assetwarrantyclaim,assetinsurancepolicy,assetinsuranceclaim}/list.html` — Action icon buttons specify `title` but lack `aria-label`. Fix: add `aria-label` matching `title` on icon-only links/buttons.
- `templates/assets/assetwarrantyinsurance/{assetwarrantyclaim,assetinsuranceclaim}/detail.html` — Modal panels use `bg-white rounded-lg` without dark mode classes (`dark:bg-slate-800 dark:text-slate-100`). Fix: add dark utility classes to modal card bodies.
- `templates/assets/assetwarrantyinsurance/{assetwarrantyclaim,assetinsurancepolicy,assetinsuranceclaim}/list.html` — KPI summary stat values hardcode literal `$` instead of dynamic currency. Fix: format with currency or tenant default.

### Done Well
- Zero comment leaks (L2 guard verified across all 12 templates).
- Strict adherence to `theme.css` badges and icons (L33 guard): all badge properties use valid color-named classes (`badge-green/red/amber/info/muted/slate`), stat icons use valid modifiers.
- Robust pagination guards (L9 guard): all prev/next pagination links guarded by `has_previous` / `has_next`.
- PK filter comparisons strictly use `|stringformat:"d"`.
- None-safe display fallbacks with safe defaults (L10 guard).
- RTL-compliant logical spacing utilities (`me-1`, `text-end`).

## 4. Performance Reviewer
**Verdict:** PASS (Clean Performance Architecture — 0 Critical, 2 Important Chained Lookups, 3 Minor Optimizations).

### Critical
None.

### Important
- `apps/assets/views/AssetWarrantyInsurance/AssetWarrantyClaims.py:99-111` — Detail view chained FK traversal on warrantor party in `AssetWarrantyClaim`. Template renders `claim.warranty.warrantor_party.name`, but `warrantor_party` is not in `select_related()`, causing +1 query per claim detail load. Fix: add `"warranty__warrantor_party"` to `select_related()` in `asset_warranty_claim_detail`.
- `apps/assets/views/AssetWarrantyInsurance/AssetInsuranceClaims.py:100-112` — Detail view chained FK traversal on underwriter party and currency in `AssetInsuranceClaim`. Template renders `claim.policy.underwriter_party.name` and `claim.policy.currency.code`, causing +2 unselected queries per claim detail load. Fix: add `"policy__underwriter_party"` and `"policy__currency"` to `select_related()` in `asset_insurance_claim_detail`.

### Minor
- `apps/assets/views/AssetWarrantyInsurance/AssetWarrantyClaims.py:123` & `AssetInsuranceClaims.py:124` — Lazy FK lookups during claim form initial pre-population from query params (`?warranty=<id>` and `?policy=<id>`). Fix: add `select_related("fixed_asset", "operational_asset", "currency")` on parent lookup.
- `apps/assets/views/AssetWarrantyInsurance/AssetWarrantyClaims.py:212, 258, 301` — State transition actions lazy load parent warranty. Fix: use `select_related("warranty")`.
- `apps/assets/views/AssetWarrantyInsurance/AssetWarranties.py:92` & `AssetInsurancePolicies.py:92` — Category dropdown in list views fetches all columns. Fix: append `.only("id", "name")`.

### Done Well
- Zero N+1 on all 4 list views: all ForeignKeys accessed in loops are pre-fetched via `select_related()`.
- Large TextFields (`terms_and_conditions`, `coverage_terms`, `defect_description`, etc.) explicitly deferred in list queries.
- Header KPI metrics computed in a single `.aggregate()` call with conditional `filter=Q(...)`.
- Clean `__str__` implementations without FK traversal (L18 guard).
- Composite multi-tenant indexes on `(tenant, status)`, `(tenant, date)`, and `UniqueConstraint(tenant, number)`.

## 5. QA Smoke Tester
**Verdict:** FAIL (1 Critical finding blocking all mutation/action endpoints with HTTP 500, 0 Important, 0 Minor).

### Critical
- `apps/assets/views/AssetWarrantyInsurance/AssetWarranties.py` (lines 135, 164, 192, 216, 238, 257)
- `apps/assets/views/AssetWarrantyInsurance/AssetWarrantyClaims.py` (lines 139, 168, 196, 225, 244, 287, 321)
- `apps/assets/views/AssetWarrantyInsurance/AssetInsurancePolicies.py` (lines 136, 165, 193, 217, 239, 258)
- `apps/assets/views/AssetWarrantyInsurance/AssetInsuranceClaims.py` (lines 141, 170, 198, 227, 247, 285, 311)
  — **`write_audit_log()` Signature Mismatch Crashes All Mutations with 500 (`TypeError: write_audit_log() got an unexpected keyword argument 'model_name'`)**:
  All 26 call sites across 11.8 view modules invoke `write_audit_log(tenant=request.tenant, user=request.user, action="...", model_name="...", object_id=..., details=...)`. However, `apps.core.utils.write_audit_log` defines signature `write_audit_log(user, obj, action, changes=None, tenant=None)`. The unexpected keyword argument `'model_name'` causes an unhandled `TypeError` (HTTP 500) whenever ANY record is created, edited, deleted, activated, renewed, voided, submitted, reviewed, settled, rejected, cancelled, adjuster-assigned, proof-filed, or denied.
  **Fix:** Update all 26 call sites across all 4 view files to match the authoritative signature:
  `write_audit_log(user=request.user, obj=instance, action="<verb>", changes="<details>", tenant=request.tenant)` (with `<verb>` <= 10 characters or short code).

### Important
None.

### Minor
None.

### Done Well
- **URL & Page Coverage (107/107 checks executed):**
  - All 4 list views (`asset_warranty_list`, `asset_warranty_claim_list`, `asset_insurance_policy_list`, `asset_insurance_claim_list`) and module landing page (`assets:overview`) render status 200 with zero template comment leaks (`{#` / `{% comment`), valid page `<title>` tags, and functional search / choice filters.
  - Robust junk-parameter handling across all lists: non-existent strings and out-of-range pages return HTTP 200 cleanly without 500 errors.
  - Page 2 pagination verified cleanly on all list views.
  - All 6 create views (including query-param pre-populated forms `?warranty=` and `?policy=`) render clean forms.
  - All 8 detail and edit views render status 200; sampled object identifiers (`AWAR-00001`, `AWCL-00002`, `AINS-00001`, `AICL-00002`) verified present in rendered HTML.
- **HTTP Method Enforcement:**
  - All 18 action/delete endpoints decorated with `@require_POST` correctly reject GET requests with HTTP 405 Method Not Allowed.
- **Cross-Tenant IDOR Security (25/25 vectors blocked):**
  - Tenant admin `admin_acme` attempting to view detail, view edit, or POST action/delete against Globex records (`AWAR-00001`, `AWCL-00002`, `AINS-00001`, `AICL-00002` with Globex PKs) consistently and safely returns HTTP 404 across 100% of routes.

