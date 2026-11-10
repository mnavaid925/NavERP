# Review Findings — Sub-module 11.9: Asset Disposal & Retirement (`assets`)

- **Base SHA:** `1c4c993c57123c7630d1d69159a02530b42a579c`
- **Head SHA:** `b58a392b73c3af0efae5407d6e04fdb99f5db254`
- **Date:** 2026-11-10
- **Status:** In Progress — 6 Review Passes (Code, Explorer, Frontend, Performance, QA Smoke, Security)

---

## Pass 1: Code Reviewer Findings

### Critical
*None.*

### Important
1. `apps/assets/views/AssetDisposal/AssetDisposalRequests.py:188`, `AssetResaleListings.py:192`, `AssetTradeIns.py:173`, `AssetScrapSalvages.py:205` — Delete views lack `@tenant_admin_required` decorator.
2. `apps/assets/views/AssetDisposal/AssetResaleListings.py:273-290`, `AssetTradeIns.py:202-218`, `AssetScrapSalvages.py:277-293` — Missing idempotency / status guards on settlement actions causes proceeds double-counting on parent `AssetDisposalRequest`.
3. `templates/assets/assetdisposal/asset_disposal_request/list.html:59-96`, `asset_resale_listing/list.html:59-88`, `asset_scrap_salvage/list.html:59-90` — Missing filter dropdowns in list templates despite view context & logic (`retirement_reason`, `payment_status`, `recycler`).

### Minor
1. `apps/assets/forms/AssetDisposal/AssetDisposalRequests.py:84-95` — Set `acquisition_cost`, `accumulated_depreciation`, and `net_book_value` as `required=False` in form `__init__` so clean() auto-derivation works when fields are left blank.
2. `apps/assets/forms/AssetDisposal/AssetResaleListings.py:74-81`, `AssetTradeIns.py:70-85`, `AssetScrapSalvages.py:92-107` — Add validation in form `clean()` that selected `fixed_asset` matches parent `disposal_request.fixed_asset`, and `retired_fixed_asset != replacement_fixed_asset` in trade-in.
3. `apps/assets/views/AssetDisposal/AssetDisposalRequests.py:221-224`, `268-272` — Add status transition guards on appraisal and rejection actions (`if instance.status not in ["draft", "submitted"]`, `if instance.status in ["completed", "cancelled"]`).
4. `apps/assets/views/AssetDisposal/` list views — Consolidate multi-count KPI metrics into single `.aggregate()`.
5. `apps/assets/views/AssetDisposal/AssetDisposalRequests.py:231`, `AssetScrapSalvages.py:232` — Guard text field concatenation against `None` (`(instance.notes or "") + ...`).

---

## Pass 2: Explorer (Architecture & Contract) Findings

### Critical
*None.*

### Important
1. `templates/assets/assetdisposal/asset_disposal_request/list.html:59-96` — View passes `reason_choices` and filters `retirement_reason`, but template lacks `<select name="retirement_reason">` dropdown.
2. `templates/assets/assetdisposal/asset_resale_listing/list.html:59-89` — View passes `payment_status_choices` and filters `payment_status`, but template omits `payment_status` dropdown and pagination query preservation.
3. `templates/assets/assetdisposal/asset_scrap_salvage/list.html:59-91` — View passes `recycler_list` and filters `recycler`, but template filter form omits `<select name="recycler">` dropdown.
4. `apps/assets/views/AssetDisposal/` delete views — Confirm missing `@tenant_admin_required` on all 4 delete views (`AssetDisposalRequests.py:188`, `AssetResaleListings.py:192`, `AssetTradeIns.py:173`, `AssetScrapSalvages.py:205`).
5. `apps/assets/views/AssetDisposal/` settlement views — Confirm double-counting proceeds risk on `mark_paid` (`ResaleListings:273`), `trade_in_settle` (`TradeIns:202`), and `scrap_salvage_settle` (`ScrapSalvages:277`).

### Minor
1. `templates/assets/assetdisposal/asset_disposal_request/form.html:35-80` — `approved_by` is in Form Meta.fields but omitted in template rendering (state transition handles approval).
2. `templates/assets/assetdisposal/asset_resale_listing/form.html:120-161` — `highest_bid_amount` and `buyer_contact_phone` are in `AssetResaleListingForm.Meta.fields` but omitted in template rendering.
3. Form clean auto-population and cross-validation consistency (matches Pass 1 items 1 & 2).

---

## Pass 3: Frontend Reviewer Findings

### Critical
*None.*

### Important
1. `templates/assets/assetdisposal/asset_disposal_request/list.html:59-96, 187, 191` — Missing `retirement_reason` filter dropdown and query parameter preservation across pagination.
2. `templates/assets/assetdisposal/asset_resale_listing/list.html:59-89, 180, 184` — Missing `payment_status` filter dropdown and query parameter preservation across pagination.
3. `templates/assets/assetdisposal/asset_scrap_salvage/list.html:59-91, 188, 192` — Missing `recycler` filter dropdown and query parameter preservation across pagination.
4. `templates/assets/assetdisposal/asset_resale_listing/form.html:120-161` & `AssetResaleListings.py:27` — Omitted required field `highest_bid_amount` causes silent form validation failure when not supplied in POST payload.

### Minor
1. `templates/assets/assetdisposal/asset_resale_listing/form.html:120-161` — `buyer_contact_phone` omitted from Section 4 in form template alongside contact name and email.
2. `templates/assets/assetdisposal/asset_disposal_request/form.html:35-80` — `approved_by` included in form Meta.fields but omitted in template (approval handled via modal transition).
3. `templates/assets/assetdisposal/asset_disposal_request/form.html:110-126` — Financial inputs lack optional indicators/helper notes regarding automatic derivation.

---

## Pass 4: Performance Reviewer Findings

### Critical
*None.*

### Important
1. `apps/assets/views/AssetDisposal/` list views — Multiple unbundled KPI queries across all 4 list views execute 17 independent queries against `base_tenant_qs`. Bundle into a single `.aggregate()` with conditional `Count("id", filter=Q(...))` and `Sum(...)`.
2. `templates/assets/assetdisposal/asset_disposal_request/detail.html:181, 229, 277` — Invoking `.count` on unevaluated child QuerySets triggers 3 distinct `SELECT COUNT(*)` queries immediately before iterating them. Replace with `|length`.
3. `apps/assets/views/AssetDisposal/AssetDisposalRequests.py:114-116` — Missing `fixed_asset` / `retired_fixed_asset` in child `select_related` calls triggers lazy evaluation during `__str__` execution in templates.

### Minor
1. `apps/assets/views/AssetDisposal/AssetTradeIns.py:69`, `AssetScrapSalvages.py:87`, `AssetDisposalRequests.py:86` — Party and Category queries for dropdown filter contexts should use `.only("id", "name")`.
2. `apps/assets/views/AssetDisposal/` create views — Replace `dr.fixed_asset.pk` and `dr.operational_asset.pk` with `dr.fixed_asset_id` and `dr.operational_asset_id` to avoid lazy foreign key lookups.

---
