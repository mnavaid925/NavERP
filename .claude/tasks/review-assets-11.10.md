# Review Findings — Sub-module 11.10: Lease & Rental Management (`apps/assets`)

**Review Range**: `d469573958d456219878a4f3866014e78801de1e` (BASE) ... `ee669a93d2c307e35d5e736d59f25a083270d8fe` (HEAD)
**Date**: 2026-11-10
**Status**: IN PROGRESS (Pass 3 of 6 complete)

---

## Pass 1: Code Reviewer (`code-reviewer`)

### Critical
- [ ] **CR1**: Contract edit resets current amortized liability and ROU carrying balances to initial (`apps/assets/models/AssetLeaseRental/AssetLeaseContracts.py:351-352`, `apps/assets/views/AssetLeaseRental/AssetLeaseContracts.py:156,204-206`). In `calculate_present_value()`, `current_lease_liability` and `current_rou_asset_carrying_value` are set unconditionally to `initial_liability` and `initial_rou`. Only reset if status is draft or no schedules are paid.
- [ ] **CR2**: Cross-tenant User leakage in `AssetLeaseModificationForm` (`apps/assets/forms/AssetLeaseRental/AssetLeaseModifications.py:59,63`) and `AssetLeaseBuyAnalysisForm` (`apps/assets/forms/AssetLeaseRental/AssetLeaseBuyAnalyses.py:71-73,77`). `requested_by` and `evaluated_by` querysets are not filtered by `tenant=self.tenant`, and not checked in `reject_foreign`.

### Important
- [ ] **IR1**: Day-of-month collapse bug in amortization schedule date incrementation (`apps/assets/models/AssetLeaseRental/AssetLeaseContracts.py:459-463`). Clamping `_d` to February length permanently degrades subsequent months' day to 28 instead of returning to 30/31. Store `base_day = first_payment_date.day`.
- [ ] **IR2**: Missing audit logging on `asset_lease_contract_calculate` (`apps/assets/views/AssetLeaseRental/AssetLeaseContracts.py:201-213`). Mutating action lacks `write_audit_log`.
- [ ] **IR3**: Termination and buyout actions do not derecognize or cancel remaining scheduled installments (`apps/assets/views/AssetLeaseRental/AssetLeaseContracts.py:251-271`, `apps/assets/views/AssetLeaseRental/AssetLeaseModifications.py:238-242`). Cancel remaining future schedules (`status="scheduled" -> "cancelled"`).
- [ ] **IR4**: Flawed salvage tax treatment and mismatched horizons in Lease vs. Buy Analysis (`apps/assets/models/AssetLeaseRental/AssetLeaseBuyAnalyses.py:311-312,333,339-342`). Taxing salvage when book value equals salvage incorrectly penalizes buy scenario; buyout option evaluation at `min(years, lease_years)`.
- [ ] **IR5**: Paid schedules and executed modifications can be deleted without restriction (`apps/assets/views/AssetLeaseRental/AssetLeaseSchedules.py:165-180`, `apps/assets/views/AssetLeaseRental/AssetLeaseModifications.py:191-206`). Disallow deleting paid schedules and executed modifications.

### Minor
- [ ] **MR1**: Form clean methods lack non-negative and range validation (`AssetLeaseContracts.py`, `AssetLeaseModifications.py`, `AssetLeaseBuyAnalyses.py`). Add explicit bounds validation in `clean()`.
- [ ] **MR2**: `AssetLeaseModification` model lacks automatic computation of adjustment deltas on `save()` (`AssetLeaseModifications.py`). Implement model `save()` calculation.
- [ ] **MR3**: Missing unique constraint on `(tenant, lease_contract, period_number)` in `AssetLeaseSchedule` (`AssetLeaseSchedules.py:111-121`). Enforce uniqueness.
- [ ] **MR4**: Cross-tenant IDOR check in `asset_lease_schedule_create` GET parameter (`AssetLeaseSchedules.py:98-100`). Validate tenant ownership using `assets_object`.
- [ ] **MR5**: Deleting a schedule line from schedule list redirects to contract detail (`AssetLeaseSchedules.py:180`). Redirect back to schedule list if invoked from schedule list.

---

## Pass 2: Explorer (`explorer`)

### Critical
*None.*

### Important
*None.*

### Minor
- [ ] **MR6**: `AssetLeaseScheduleAdmin` list_filter lacks temporal filter (`apps/assets/admin.py:383`). Add `due_date` filter for periodic reconciliation in admin.
- [ ] **MR7**: Contextual Cancel Link on Modification Form (`templates/assets/assetleaserental/asset_lease_modification/form.html:149`). Cancel button unconditionally navigates to list even when originating from a lease contract detail page via `?lease=<id>`.
- [ ] **MR8**: Contract Document Discrepancy on Schedule URL Path Prefix (`.claude/tasks/contract-assets-11.10.md:231-237`). Update contract doc to reflect `lease-schedules/` route prefix implemented to prevent collision with 11.5 maintenance schedules.

---

## Pass 3: Frontend Reviewer (`frontend-reviewer`)

### Critical
*None.*

### Important
- [ ] **IR6**: Undefined design system badge class `badge-purple` in templates and models (`list.html:135`, `detail.html:19`, `AssetLeaseContracts.py:56,61`, `AssetLeaseModifications.py:51`, `AssetLeaseBuyAnalyses.py:41`). `badge-purple` does not exist in `theme.css`. Replace with valid colour-named badge (e.g. `badge-info` or `badge-slate`).
- [ ] **IR7**: Non-standard utility classes `text-success` and `text-purple` used in financial displays (`contract/detail.html:41,271,323`, `schedule/list.html:125`, `modification/list.html:129`, etc.). Replace with valid `theme.css` `.text-ok` or `.text-brand`.
- [ ] **IR8**: Orphan dollar signs and `$N/A` displayed on nullable numeric values (`contract/detail.html:172,196`, `buy_analysis/detail.html:150,154,162`). Guard nullable numeric figures with `{% if ... %}`.

### Minor
- [ ] **MR9**: Missing `aria-label` on filter and search inputs across all 4 list templates (`contract/list.html:61`, `schedule/list.html:61`, `modification/list.html:54`, `buy_analysis/list.html:54`).
- [ ] **MR10**: Missing `aria-label` on icon-only table action buttons across all list templates (view, edit, delete).
- [ ] **MR11**: Missing `scope="col"` on table header `<th>` cells across all list and detail child tables.
- [ ] **MR12**: Hardcoded light-slate utility classes lacking dark mode contrast variants in cards and detail sections.
