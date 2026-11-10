# Review Findings — Sub-module 11.9: Asset Disposal & Retirement (`assets`)

- **Base SHA:** `1c4c993c57123c7630d1d69159a02530b42a579c`
- **Head SHA:** `e85c24490d346ff0fb08df7664c3c3a078438ae6`
- **Date:** 2026-11-10
- **Status:** Consolidated & Deduplicated Findings from 6 Review Passes (Code, Explorer, Frontend, Performance, QA Smoke, Security)

---

## Critical

*None.*

---

## Important

- [x] **I1: Delete Views Lack `@tenant_admin_required` (Authorization / Privilege Escalation)** — fixed (commits 16636049, 853aa905, 05a48850, f5b53e71)
  - **Location:**
    - `apps/assets/views/AssetDisposal/AssetDisposalRequests.py:187-190` (`asset_disposal_request_delete`)
    - `apps/assets/views/AssetDisposal/AssetResaleListings.py:190-193` (`asset_resale_listing_delete`)
    - `apps/assets/views/AssetDisposal/AssetTradeIns.py:172-175` (`asset_trade_in_delete`)
    - `apps/assets/views/AssetDisposal/AssetScrapSalvages.py:204-207` (`asset_scrap_salvage_delete`)
  - **Issue:** All 4 delete actions are decorated with `@login_required` and `@require_POST`, but lack `@tenant_admin_required`. Any authenticated tenant employee could delete disposal requests, resale listings, trade-in agreements, or scrap records.
  - **Fix:** Add `@tenant_admin_required` decorator to all four delete view functions.

- [x] **I2: Missing Idempotency & Status Guards on Financial Settlement Actions (Proceeds Double-Counting)** — fixed (commits ff69eb4b, a64cf7e7, 930041a4)
  - **Location:**
    - `apps/assets/views/AssetDisposal/AssetResaleListings.py:273-292` (`asset_resale_listing_mark_paid`)
    - `apps/assets/views/AssetDisposal/AssetTradeIns.py:202-223` (`asset_trade_in_settle`)
    - `apps/assets/views/AssetDisposal/AssetScrapSalvages.py:277-299` (`asset_scrap_salvage_settle`)
  - **Issue:** The settlement views accumulate gross/net proceeds and expenses directly onto parent `AssetDisposalRequest` (`dr.actual_gross_proceeds += ...`, `dr.actual_removal_cost += ...`). Repeated POST requests (via double-click or automated retry) repeatedly increment these metrics, distorting realized gain/loss and general ledger reconciliations.
  - **Fix:** Add status guards at the beginning of each handler:
    - In `asset_resale_listing_mark_paid`: `if instance.payment_status == "paid": messages.info(request, ...); return redirect(...)`
    - In `asset_trade_in_settle`: `if instance.status == "credit_settled": messages.info(request, ...); return redirect(...)`
    - In `asset_scrap_salvage_settle`: `if instance.status == "settled": messages.info(request, ...); return redirect(...)`

- [x] **I3: Missing Administrative Privilege Guard on Capital Asset Disposal Approval** — fixed (commit b9331e22)
  - **Location:** `apps/assets/views/AssetDisposal/AssetDisposalRequests.py:248-264` (`asset_disposal_request_approve`)
  - **Issue:** Derecognizing capitalized balance sheet assets carries financial governance implications. `asset_disposal_request_approve` is currently decorated only with `@login_required` and `@require_POST`, allowing any non-admin tenant employee to approve asset retirements.
  - **Fix:** Add `@tenant_admin_required` to `asset_disposal_request_approve`.

- [x] **I4: Missing State Transition Guards on Workflow Actions (Out-of-Order Lifecycle Transitions)** — fixed (commits c9585974, ba972ad9, 578415b0, 0d41ab91)
  - **Location:**
    - `apps/assets/views/AssetDisposal/AssetDisposalRequests.py:221-245` (`asset_disposal_request_appraise`)
    - `apps/assets/views/AssetDisposal/AssetDisposalRequests.py:268-280` (`asset_disposal_request_reject`)
    - `apps/assets/views/AssetDisposal/AssetResaleListings.py:207-233` (`asset_resale_listing_record_bid`)
    - `apps/assets/views/AssetDisposal/AssetResaleListings.py:238-268` (`asset_resale_listing_accept_sale`)
    - `apps/assets/views/AssetDisposal/AssetResaleListings.py:297-305` (`asset_resale_listing_mark_delivered`)
    - `apps/assets/views/AssetDisposal/AssetTradeIns.py:189-198` (`asset_trade_in_surrender`)
    - `apps/assets/views/AssetDisposal/AssetScrapSalvages.py:221-247` (`asset_scrap_salvage_certify_abatement`)
    - `apps/assets/views/AssetDisposal/AssetScrapSalvages.py:252-272` (`asset_scrap_salvage_record_cod`)
  - **Issue:** Workflow action endpoints lack status validation guards, permitting out-of-order execution (e.g. appraising or rejecting already completed requests, recording bids on closed listings, or delivering equipment before sale).
  - **Fix:** Add explicit status precondition checks in each transition view.

- [x] **I5: Mass-Assignment Risk on Authorization Authority (`approved_by` / `authorized_by` in Form Meta.fields)** — fixed (commits cc14694b, 29d97b32, dd661808)
  - **Location:**
    - `apps/assets/forms/AssetDisposal/AssetDisposalRequests.py:27` (`approved_by`)
    - `apps/assets/forms/AssetDisposal/AssetTradeIns.py:25` (`authorized_by`)
  - **Issue:** `approved_by` and `authorized_by` are included in form `Meta.fields`. A raw POST can supply an arbitrary user id and establish approval outside the official approval workflow.
  - **Fix:** Remove `approved_by` from `AssetDisposalRequestForm.Meta.fields` and `authorized_by` from `AssetTradeInForm.Meta.fields`.

- [x] **I6: Silent Form Validation Failure on Browser Create of `AssetResaleListing`** — fixed (commit f3ee7d8b)
  - **Location:**
    - `apps/assets/forms/AssetDisposal/AssetResaleListings.py:20-41`
    - `templates/assets/assetdisposal/asset_resale_listing/form.html:120-161`
  - **Issue:** `highest_bid_amount`, `gross_sale_proceeds`, `commission_rate_percent`, and `tax_amount` default to `required=True` because the model fields lack `blank=True`. In browser form submissions, these fields are either unrendered or inappropriate for a new listing, causing silent validation failure.
  - **Fix:** Set `required=False` with `initial=Decimal('0.00')` for these fields in `AssetResaleListingForm.__init__`.

- [ ] **I7: Validation Failure on Auto-Derived Financial Fields in `AssetDisposalRequestForm`**
  - **Location:** `apps/assets/forms/AssetDisposal/AssetDisposalRequests.py:31-36, 84-95`
  - **Issue:** When creating a disposal request in the browser, leaving `acquisition_cost`, `accumulated_depreciation`, or `net_book_value` blank triggers a validation error before `clean()` can auto-derive them from the selected fixed asset.
  - **Fix:** Set `required=False` for `acquisition_cost`, `accumulated_depreciation`, `net_book_value`, `estimated_residual_value`, and `estimated_removal_cost` in `AssetDisposalRequestForm.__init__`.

- [ ] **I8: Missing Filter Dropdowns in List Templates and Pagination Parameter Preservation**
  - **Location:**
    - `templates/assets/assetdisposal/asset_disposal_request/list.html:59-96, 187, 191` (`retirement_reason`)
    - `templates/assets/assetdisposal/asset_resale_listing/list.html:59-89, 180, 184` (`payment_status`)
    - `templates/assets/assetdisposal/asset_scrap_salvage/list.html:59-91, 188, 192` (`recycler`)
  - **Issue:** Views supply `reason_choices`, `payment_status_choices`, and `recycler_list` in context and filter on `request.GET`, but list templates omit the corresponding `<select>` elements and pagination query parameter preservation.
  - **Fix:** Add the missing dropdown `<select>` controls and preserve their query parameters in pagination links.

- [ ] **I9: Multiple Unbundled KPI Queries in All 4 List Views**
  - **Location:**
    - `apps/assets/views/AssetDisposal/AssetDisposalRequests.py:66-72`
    - `apps/assets/views/AssetDisposal/AssetResaleListings.py:60-65`
    - `apps/assets/views/AssetDisposal/AssetTradeIns.py:52-57`
    - `apps/assets/views/AssetDisposal/AssetScrapSalvages.py:61-74`
  - **Issue:** Each list view runs 4–5 individual queries against `base_tenant_qs` (`.count()` and `.aggregate()`), executing 17 queries across lists instead of 4.
  - **Fix:** Consolidate KPI metrics into a single `.aggregate()` call using conditional `Count("id", filter=Q(...))` and `Sum(...)`.

- [ ] **I10: Redundant QuerySet `.count` in Detail Template**
  - **Location:** `templates/assets/assetdisposal/asset_disposal_request/detail.html:181, 229, 277`
  - **Issue:** Invoking `.count` on `resale_listings`, `trade_ins`, and `scrap_salvages` executes 3 distinct `SELECT COUNT(*)` queries immediately prior to iterating them in `{% for %}` loops.
  - **Fix:** Replace `.count` with `|length` in `detail.html`.

- [ ] **I11: Missing `select_related` on Child Queries for Relations Accessed by `__str__`**
  - **Location:** `apps/assets/views/AssetDisposal/AssetDisposalRequests.py:114-116`
  - **Issue:** Child queries `resale_listings`, `trade_ins`, and `scrap_salvages` omit `fixed_asset` / `retired_fixed_asset`, triggering lazy N+1 queries when `__str__` evaluates `self.fixed_asset.name`.
  - **Fix:** Add `"fixed_asset"` to `select_related` for `resale_listings` and `scrap_salvages`, and `"retired_fixed_asset"` for `trade_ins`.

---

## Minor

- [ ] **M1: Form Cross-Entity Reference Validation (Parent vs Child Fixed Asset)**
  - **Location:**
    - `apps/assets/forms/AssetDisposal/AssetResaleListings.py:75-81`
    - `apps/assets/forms/AssetDisposal/AssetTradeIns.py:70-85`
    - `apps/assets/forms/AssetDisposal/AssetScrapSalvages.py:92-107`
  - **Issue:** Forms do not validate that selected `fixed_asset` matches parent `disposal_request.fixed_asset`, or that `retired_fixed_asset != replacement_fixed_asset` in trade-in.
  - **Fix:** In form `clean()`, validate that `fixed_asset == disposal_request.fixed_asset` and ensure `retired_fixed_asset != replacement_fixed_asset`.

- [ ] **M2: Defensive String Concatenation on Notes Fields**
  - **Location:**
    - `apps/assets/views/AssetDisposal/AssetDisposalRequests.py:231`
    - `apps/assets/views/AssetDisposal/AssetScrapSalvages.py:232`
  - **Issue:** Direct `+=` concatenation on `instance.justification_notes` and `instance.notes` raises `TypeError` if field value is `None`.
  - **Fix:** Guard with `(instance.notes or "") + f"\n..."`.

- [ ] **M3: `buyer_contact_phone` Omitted in Resale Listing Form Template**
  - **Location:** `templates/assets/assetdisposal/asset_resale_listing/form.html:120-161`
  - **Issue:** Included in `AssetResaleListingForm.Meta.fields:34`, but omitted from the contact details section in `form.html`.
  - **Fix:** Add `buyer_contact_phone` input block to Section 4 in `form.html`.

- [ ] **M4: Party and Category Query Optimization in List Views**
  - **Location:**
    - `apps/assets/views/AssetDisposal/AssetTradeIns.py:69`
    - `apps/assets/views/AssetDisposal/AssetScrapSalvages.py:87`
    - `apps/assets/views/AssetDisposal/AssetDisposalRequests.py:86`
  - **Issue:** Filter dropdown querysets fetch all columns for Parties and Categories.
  - **Fix:** Append `.only("id", "name")` to reduce memory and query payload.

- [ ] **M5: Redundant Foreign Key Lookup in Create Views**
  - **Location:**
    - `apps/assets/views/AssetDisposal/AssetResaleListings.py:149-151`
    - `apps/assets/views/AssetDisposal/AssetTradeIns.py:132`
    - `apps/assets/views/AssetDisposal/AssetScrapSalvages.py:163-165`
  - **Issue:** Accessing `dr.fixed_asset.pk` triggers lazy model instantiation when `dr.fixed_asset_id` is already loaded.
  - **Fix:** Use `dr.fixed_asset_id` and `dr.operational_asset_id`.

- [ ] **M6: `AssetDisposalAppraisalForm` Initializer Signature**
  - **Location:** `apps/assets/forms/AssetDisposal/AssetDisposalRequests.py:133`
  - **Issue:** Positional `tenant` argument without default breaks standard Django form conventions.
  - **Fix:** Change signature to `def __init__(self, tenant=None, *args, **kwargs):`.

- [ ] **M7: Restrict Edit Mode on Post-Approval Disposal Requests**
  - **Location:** `apps/assets/views/AssetDisposal/AssetDisposalRequests.py:164`
  - **Issue:** An approved request (`approved` or `in_progress`) can currently still be modified via standard edit form.
  - **Fix:** Restrict edit access to preliminary states (`draft`, `submitted`), redirecting with a warning once approved.

---
