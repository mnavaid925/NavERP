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
