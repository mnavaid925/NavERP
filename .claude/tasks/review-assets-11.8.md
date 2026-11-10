# Review Findings — Module 11.8: Warranty & Insurance Management

**Base Commit:** `1c4c993c57123c7630d1d69159a02530b42a579c`  
**Head Commit:** `d5deb1ca95e7c858be167d353a25cb062cf1b15c`  
**Review Status:** Completed (6/6 serial passes executed: `code-reviewer`, `explorer`, `frontend-reviewer`, `performance-reviewer`, `qa-smoke-tester`, `security-reviewer`).

---

## Critical

- [x] **C1: `write_audit_log()` Signature Mismatch Crashes All 26 Mutations with HTTP 500 (`TypeError: write_audit_log() got an unexpected keyword argument 'model_name'`)**
  - **Status:** [x] fixed — align write_audit_log signature across warranty and insurance views (27ab531e, 2957c74e, 009ff353, 0d482f24)
  - **Location:**
    - `apps/assets/views/AssetWarrantyInsurance/AssetWarranties.py:135, 164, 192, 216, 238, 257`
    - `apps/assets/views/AssetWarrantyInsurance/AssetWarrantyClaims.py:139, 168, 196, 225, 244, 287, 321`
    - `apps/assets/views/AssetWarrantyInsurance/AssetInsurancePolicies.py:136, 165, 193, 217, 239, 258`
    - `apps/assets/views/AssetWarrantyInsurance/AssetInsuranceClaims.py:141, 170, 198, 227, 247, 285, 311`
  - **Description:** All 26 mutating views and workflow action endpoints invoke `write_audit_log(tenant=request.tenant, user=request.user, action="...", model_name="...", object_id=..., details=...)`. The actual function signature in `apps/core/utils.py` is `write_audit_log(user, obj, action, changes=None, tenant=None)`. The unknown `'model_name'` keyword argument causes an unhandled `TypeError` (HTTP 500) on every create, edit, delete, activate, renew, void, submit, review, settle, reject, cancel, assign adjuster, proof-of-loss, and deny request.
  - **Fix:** Refactor all 26 call sites to `write_audit_log(user=request.user, obj=instance, action="<verb>", changes="<details>", tenant=request.tenant)` (where `<verb>` is a short action code).

---

## Important

- [x] **I1: Hand-Parsed Numeric Input Lacks `is_finite()`, Magnitude Cap, and Non-Negative Guards (Lesson L35)**
  - **Status:** [x] fixed — harden decimal parsing and bounds checking on claim settlements (5df5ae62, 30f8ff67)
  - **Location:**
    - `apps/assets/views/AssetWarrantyInsurance/AssetWarrantyClaims.py:260-264` (`approved_amount`)
    - `apps/assets/views/AssetWarrantyInsurance/AssetInsuranceClaims.py:263-272` (`settlement_payout_amount`, `salvage_recovery_amount`)
  - **Description:** `Decimal(request.POST.get(...))` parses user input without checking `.is_finite()`, bounds, or negative values. Inputting `"NaN"` or `"Infinity"` does not raise on instantiation but causes MySQL errors or data corruption downstream. Large numbers exceeding `max_digits` cause unhandled MySQL 1264 `DataError`.
  - **Fix:** Wrap parsing in `try/except (InvalidOperation, TypeError, ValueError)`, verify `val.is_finite()`, enforce non-negativity (`val >= 0`), and clamp within model bounds (`Decimal("9999999999.99")` or `Decimal("999999999999.99")`). Return user-friendly error message and redirect if invalid.

- [x] **I2: Missing View-Level Status Guards on Claim Settlement, Rejection, and Editing**
  - **Status:** [x] fixed — add status transition checks on edit, settle, and reject/deny (cd0232d3, 45664fc6)
  - **Location:**
    - `apps/assets/views/AssetWarrantyInsurance/AssetWarrantyClaims.py:160, 258, 299`
    - `apps/assets/views/AssetWarrantyInsurance/AssetInsuranceClaims.py:163, 261, 298`
  - **Description:** Detail templates hide actions for finalized claims, but views lack status guards. An already settled (`settled_closed`, `settled_paid`) or rejected/denied claim can be settled again, rejected, or edited via direct POST, corrupting financial history.
  - **Fix:** Add view guards:
    - In settlement/rejection views, assert claim status is in allowed open/review states (e.g. `claim.claim_status in ['submitted', 'under_review']` or `claim.claim_status in ['proof_of_loss_filed', 'under_carrier_review', 'approved_pending_payout', 'adjuster_assigned']`).
    - In edit views, redirect with warning if `claim.claim_status in ['settled_closed', 'rejected', 'settled_paid', 'denied_disputed', 'closed']`.

- [x] **I3: Detail View Chained FK Traversal on Related Parties and Currency Causes Extra Queries**
  - **Status:** [x] fixed — prefetch chained FKs on detail views (e0df2e2f, f332f737)
  - **Location:**
    - `apps/assets/views/AssetWarrantyInsurance/AssetWarrantyClaims.py:99-111`
    - `apps/assets/views/AssetWarrantyInsurance/AssetInsuranceClaims.py:100-112`
  - **Description:** Warranty claim detail template renders `claim.warranty.warrantor_party.name`, and insurance claim detail renders `claim.policy.underwriter_party.name` and `claim.policy.currency.code`. These chained foreign keys are not pre-fetched in `select_related()`, triggering +1 and +2 lazy database queries per detail page view.
  - **Fix:** Add `"warranty__warrantor_party"` to `AssetWarrantyClaim.objects.select_related(...)`, and add `"policy__underwriter_party"` and `"policy__currency"` to `AssetInsuranceClaim.objects.select_related(...)`.

- [x] **I4: Non-Existent Attribute `warranty.service_contract.provider_name` Renders Blank in Warranty Detail**
  - **Status:** [x] fixed — use vendor.name on service_contract (d13497b0)
  - **Location:** `templates/assets/assetwarrantyinsurance/assetwarranty/detail.html:236`
  - **Description:** Template attempts to render `warranty.service_contract.provider_name`, but `AssetServiceContract` has no `provider_name` attribute (it defines `vendor = models.ForeignKey("core.Party", ...)`).
  - **Fix:** Replace with `{{ warranty.service_contract.vendor.name }}` (with fallback to `{{ warranty.service_contract.title }}`).

- [x] **I5: Seeder Structure Pollution and Broken Idempotency in `seed_assets.py`**
  - **Status:** [x] fixed — isolate _seed_tenant_11_9 with dedicated idempotency check (eef48645)
  - **Location:** `apps/assets/management/commands/seed_assets.py:1752, 2006`
  - **Description:** In commit `6659c982`, 11.9 demo seeding was appended inside `_seed_tenant_11_8` after an early return guard. If 11.8 records already exist, `_seed_tenant_11_8` returns early, inadvertently skipping 11.9 seeding.
  - **Fix:** Isolate 11.9 seeding into its own `_seed_tenant_11_9(self, tenant)` method with its own idempotency check, wire `self._seed_tenant_11_9(tenant)` in `handle()`, and keep `_seed_tenant_11_8` strictly scoped to 11.8.

---

## Minor

- [x] **M1: Invalid Design System Badge CSS Class `badge-purple` in `AssetInsurancePolicies.py`**
  - **Status:** [x] fixed — change badge-purple to badge-info (b6d93ebc)
  - **Location:** `apps/assets/models/AssetWarrantyInsurance/AssetInsurancePolicies.py:66`
  - **Description:** `POLICY_TYPE_CSS` maps `"business_interruption"` to `"badge-purple"`. Per `theme.css` and lesson L33, badges only support color-named classes (`badge-green/red/amber/info/slate/muted`).
  - **Fix:** Change to `"badge-info"` or `"badge-slate"`.

- [x] **M2: Direct POST Settlement Does Not Validate Model Choice Inputs**
  - **Status:** [x] fixed — validate choice inputs with fallback defaults (9291f170, 9b501ae1)
  - **Location:**
    - `apps/assets/views/AssetWarrantyInsurance/AssetWarrantyClaims.py:265` (`resolution_type`)
    - `apps/assets/views/AssetWarrantyInsurance/AssetInsuranceClaims.py:273` (`settlement_method`)
  - **Description:** POST parameters are assigned to model fields without verifying they exist in `RESOLUTION_TYPE_CHOICES` or `SETTLEMENT_METHOD_CHOICES`. An invalid or oversized string causes a 500 error or invalid data state.
  - **Fix:** Validate choices against `dict(Model.CHOICES)` and fall back to safe default if invalid.

- [x] **M3: Resurrecting Voided Warranties and Cancelled Policies via Renewal Endpoint**
  - **Status:** [x] fixed — disallow renewal on voided/cancelled/draft records (111c124e, b54b9956)
  - **Location:**
    - `apps/assets/views/AssetWarrantyInsurance/AssetWarranties.py:230-247`
    - `apps/assets/views/AssetWarrantyInsurance/AssetInsurancePolicies.py:231-247`
  - **Description:** `asset_warranty_renew` and `asset_insurance_policy_renew` allow renewing contracts that have been voided or cancelled by an administrator.
  - **Fix:** Verify status is in `["active", "expiring_soon", "expired"]` before renewing; reject renewal on voided/cancelled contracts.

- [x] **M4: Warranty Status Reactivation on Claim Resolution Ignores Calendar Expiration**
  - **Status:** [x] fixed — check end_date < today before restoring to active (4a64b33a)
  - **Location:** `apps/assets/views/AssetWarrantyInsurance/AssetWarrantyClaims.py:284, 318`
  - **Description:** Resolving or rejecting a claim sets `claim.warranty.status = "active"`, even if the warranty's `end_date` has already passed.
  - **Fix:** Set status to `"expired"` if `claim.warranty.end_date < timezone.now().date()`, else `"active"`.

- [ ] **M5: Mismatch Between UI Delete Button Visibility and Backend View Authorization Gate**
  - **Location:**
    - `templates/assets/assetwarrantyinsurance/assetwarranty/detail.html:50` & `list.html:181`
    - `templates/assets/assetwarrantyinsurance/assetwarrantyclaim/detail.html:50` & `list.html:162`
    - `templates/assets/assetwarrantyinsurance/assetinsurancepolicy/detail.html:50` & `list.html:176`
    - `templates/assets/assetwarrantyinsurance/assetinsuranceclaim/detail.html:46` & `list.html:163`
  - **Description:** Templates check `{% if request.user.is_staff or request.user.is_superuser %}`, while views enforce `@tenant_admin_required`.
  - **Fix:** Update template condition to `{% if request.user.is_superuser or request.user.is_tenant_admin %}`.

- [ ] **M6: Lazy FK Lookups During Claim Form Initial Pre-Population**
  - **Location:**
    - `apps/assets/views/AssetWarrantyInsurance/AssetWarrantyClaims.py:123`
    - `apps/assets/views/AssetWarrantyInsurance/AssetInsuranceClaims.py:124`
  - **Description:** Loading `create/` view with `?warranty=<id>` or `?policy=<id>` performs lazy queries to populate asset and currency fields.
  - **Fix:** Add `.select_related("fixed_asset", "operational_asset", "currency")` to the parent fetch.

- [ ] **M7: Action Icon Buttons in List Templates Lack `aria-label`**
  - **Location:** `templates/assets/assetwarrantyinsurance/{assetwarranty,assetwarrantyclaim,assetinsurancepolicy,assetinsuranceclaim}/list.html`
  - **Description:** Icon-only action links and buttons specify `title` but lack `aria-label` for assistive technology.
  - **Fix:** Add `aria-label` matching `title` on icon-only interactive elements.

- [ ] **M8: Settlement and Rejection Modal Bodies Lack Dark Mode Styling**
  - **Location:** `templates/assets/assetwarrantyinsurance/{assetwarrantyclaim,assetinsuranceclaim}/detail.html`
  - **Description:** Modals use `bg-white rounded-lg` without dark mode classes.
  - **Fix:** Add `dark:bg-slate-800 dark:text-slate-100`.

---

## Review Pass Summary
- **Pass 1: Code Reviewer** — Identified hand-parsed numeric vulnerabilities (L35), status transitions, and unpinned template attributes.
- **Pass 2: Codebase Explorer** — Verified package layout, URLs, context contracts, and identified seeder idempotency pollution.
- **Pass 3: Frontend Reviewer** — Verified 0 comment leaks (L2), verified color-named badges (L33), checked pagination guards (L9) and RTL compliance; identified icon button accessibility and modal dark mode.
- **Pass 4: Performance Reviewer** — Verified zero N+1 in list loops, single-query aggregates, and composite indexes; identified chained FK queries on detail pages.
- **Pass 5: QA Smoke Tester** — Executed 107 runtime checks; verified 25/25 IDOR vectors blocked (404); caught Critical HTTP 500 crashes on all 26 POST mutation call sites due to `write_audit_log` parameter mismatch.
- **Pass 6: Security Reviewer** — Verified multi-tenant scoping and CSRF protection; flagged missing view-level status guards and unvalidated Decimal/choice parsing.
