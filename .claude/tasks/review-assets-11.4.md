# Review Findings: NavERP Sub-module 11.4 Depreciation & Financial Management (`apps/assets`)

**Changeset**: `3eb85470bcabd9a57336c559a3d958341b4597cf`..`HEAD`
**Consolidated**: Deduplicated & sorted Critical -> Important -> Minor across all 6 reviewer passes:
1. `code-reviewer`
2. `explorer`
3. `frontend-reviewer`
4. `performance-reviewer`
5. `qa-smoke-tester`
6. `security-reviewer`

---

## Findings Matrix

| ID | Sev | Title | File & Line | Status |
|:---|:---:|:------|:------------|:------:|
| **C1** | Critical | Non-existent attribute access on `scm.Asset` in `complete_transfer()` | `apps/assets/models/AssetDepreciation/AssetTransfers.py:230-238` | `[ ] open` |
| **I1** | Important | Silent omission of General Ledger posting when GL accounts unconfigured in schedule | `apps/assets/models/AssetDepreciation/AssetDepreciationSchedules.py:269-311` | `[ ] open` |
| **I2** | Important | Silent omission of General Ledger posting when GL accounts unconfigured in revaluation | `apps/assets/models/AssetDepreciation/AssetRevaluations.py:215-275` | `[ ] open` |
| **I3** | Important | Depreciation override amount entered by user is overwritten by calculation logic | `apps/assets/models/AssetDepreciation/AssetDepreciationSchedules.py:196-254`, `views/.../AssetDepreciationSchedules.py:120, 155` | `[ ] open` |
| **I4** | Important | `transferred_by` omitted from `reject_foreign` in `AssetTransferForm.clean()` | `apps/assets/forms/AssetDepreciation/AssetTransfers.py:86-104` | `[ ] open` |
| **I5** | Important | Unhandled `decimal.InvalidOperation` on `eval_cost` in Capitalization Policy Evaluator | `apps/assets/views/AssetDepreciation/CapitalizationPolicies.py:83-95`, `models/.../CapitalizationPolicies.py:136-137` | `[ ] open` |
| **I6** | Important | Non-theme badge CSS classes (`badge-purple`, `badge-blue`) in model CSS mappings | `AssetDepreciationSchedules.py:49-50`, `AssetRevaluations.py:47`, `AssetTransfers.py:40-41`, `CapitalizationPolicies.py:34-35` | `[ ] open` |
| **I7** | Important | Invalid text color classes `text-green` and `text-amber` across templates | `revaluation/list.html:138`, `revaluation/detail.html:69-70`, `capitalization_policy/detail.html:120-121, 158` | `[ ] open` |
| **I8** | Important | Privileged action buttons in templates lack tenant admin role gating | Templates across `templates/assets/asset_depreciation/` | `[ ] open` |
| **M1** | Minor | Invalid field lookup `transfer.operational_asset.current_location.name` in detail template | `templates/assets/asset_depreciation/transfer/detail.html:172` | `[ ] open` |
| **M2** | Minor | Capitalization policy test widget display misses `manual_review` classification | `templates/assets/asset_depreciation/capitalization_policy/detail.html:122` | `[ ] open` |
| **M3** | Minor | Deep nested FK lookups in `depreciation_schedule_detail` and `transfer_detail` | `AssetDepreciationSchedules.py:92-101`, `AssetTransfers.py:83-97` | `[ ] open` |
| **M4** | Minor | Missing `search_query` context alias in list views | All 4 list views in `apps/assets/views/AssetDepreciation/` | `[ ] open` |
| **M5** | Minor | Template physical directional margin classes (`mr-1`, `ml-*`) instead of logical RTL (`me-1`, `ms-*`) | Templates across `templates/assets/asset_depreciation/` | `[ ] open` |
| **M6** | Minor | List pagination card footers missing standard padding and border classes | All 4 list templates in `templates/assets/asset_depreciation/` | `[ ] open` |
| **M7** | Minor | Icon-only action buttons in list tables omit `aria-label` | All 4 list templates in `templates/assets/asset_depreciation/` | `[ ] open` |

---

## Detailed Consolidated Findings

### [C1] Non-existent attribute access on `scm.Asset` in `complete_transfer()`
- **Severity**: Critical
- **File & Line**: `apps/assets/models/AssetDepreciation/AssetTransfers.py:230-238`
- **Description**: In `AssetTransfer.complete_transfer()`, code sets `oa.current_location = self.destination_location` and `oa.assigned_to = self.destination_custodian` and calls `oa.save(update_fields=...)`. `scm.Asset` has no fields with these names (`scm.Asset` fields are `location`, `custodian`, `org_unit`). This causes an unhandled `FieldError`/`AttributeError` on transfer completion.
- **Remediation**:
  ```python
  if oa:
      update_oa_fields = []
      if self.destination_location:
          oa.location = self.destination_location
          update_oa_fields.append("location")
      if self.destination_custodian:
          oa.custodian = self.destination_custodian
          update_oa_fields.append("custodian")
      if self.destination_department:
          oa.org_unit = self.destination_department
          update_oa_fields.append("org_unit")
      if update_oa_fields:
          oa.save(update_fields=update_oa_fields)
  ```

### [I1] Silent omission of General Ledger posting when GL accounts unconfigured in schedule
- **Severity**: Important
- **File & Line**: `apps/assets/models/AssetDepreciation/AssetDepreciationSchedules.py:269-311`
- **Description**: `post_to_gl()` advances status to "posted" and updates asset accumulated depreciation even if GL accounts are missing and no `JournalEntry` is created.
- **Remediation**: Validate `exp_acc` and `accum_acc` exist before proceeding; raise `ValidationError("Both Depreciation Expense and Accumulated Depreciation GL accounts are required to post to the General Ledger.")` if either is missing.

### [I2] Silent omission of General Ledger posting when GL accounts unconfigured in revaluation
- **Severity**: Important
- **File & Line**: `apps/assets/models/AssetDepreciation/AssetRevaluations.py:215-275`
- **Description**: `execute_revaluation()` approves the revaluation and updates asset balances even if required GL accounts are missing for non-zero adjustments.
- **Remediation**: Validate that required accounts exist when `revaluation_adjustment != Decimal("0.00")` and raise `ValidationError` if either debit or credit account is unconfigured.

### [I3] Depreciation override amount entered by user is overwritten by calculation logic
- **Severity**: Important
- **File & Line**: `apps/assets/models/AssetDepreciation/AssetDepreciationSchedules.py:196-254`, `apps/assets/views/AssetDepreciation/AssetDepreciationSchedules.py:120, 155`
- **Description**: When user enters a manual override amount in form, `calculate_depreciation()` unconditionally computes and replaces `self.depreciation_amount`.
- **Remediation**: In `calculate_depreciation()`, check if `self.depreciation_amount and self.depreciation_amount > Decimal("0.00")` and preserve the override amount (capped by remaining depreciable balance).

### [I4] `transferred_by` omitted from `reject_foreign` in `AssetTransferForm.clean()`
- **Severity**: Important
- **File & Line**: `apps/assets/forms/AssetDepreciation/AssetTransfers.py:86-104`
- **Description**: Form `clean()` does not include `"transferred_by"` in `reject_foreign`, creating a cross-tenant user ID injection risk.
- **Remediation**: Add `"transferred_by"` to the `reject_foreign` check list in `clean()`.

### [I5] Unhandled `decimal.InvalidOperation` on `eval_cost` in Capitalization Policy Evaluator (Lesson L35)
- **Severity**: Important
- **File & Line**: `apps/assets/views/AssetDepreciation/CapitalizationPolicies.py:83-95`, `apps/assets/models/AssetDepreciation/CapitalizationPolicies.py:136-137`
- **Description**: `request.GET.get('eval_cost')` is parsed inside `except (ValueError, TypeError):` which misses `decimal.InvalidOperation` and does not check `is_finite()` or bounds.
- **Remediation**: Import `InvalidOperation`, catch `(InvalidOperation, TypeError, ValueError)`, and validate that `cost_val.is_finite()` and `cost_val >= 0`.

### [I6] Non-theme badge CSS classes (`badge-purple`, `badge-blue`) in model CSS mappings
- **Severity**: Important
- **File & Line**: `AssetDepreciationSchedules.py:49-50`, `AssetRevaluations.py:47`, `AssetTransfers.py:40-41`, `CapitalizationPolicies.py:34-35`
- **Description**: `theme.css` only supports `badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, `badge-slate`.
- **Remediation**: Map `badge-blue` to `badge-info` and `badge-purple` to `badge-slate` (or `badge-info`).

### [I7] Invalid text color classes `text-green` and `text-amber` across templates
- **Severity**: Important
- **File & Line**: `revaluation/list.html:138`, `revaluation/detail.html:69-70`, `capitalization_policy/detail.html:120-121, 158`
- **Description**: `text-green` and `text-amber` are invalid in `theme.css`.
- **Remediation**: Replace with `text-ok` and `text-warn`.

### [I8] Privileged action buttons in templates lack tenant admin role gating
- **Severity**: Important
- **File & Line**: Templates across `templates/assets/asset_depreciation/`
- **Description**: Action buttons for delete, post to GL, approve revaluation, and complete transfer lack `{% if request.user.is_superuser or request.user.is_tenant_admin %}`.
- **Remediation**: Wrap privileged action buttons in `{% if request.user.is_superuser or request.user.is_tenant_admin %}`.

### [M1] Invalid field lookup `transfer.operational_asset.current_location.name` in detail template
- **Severity**: Minor
- **File & Line**: `templates/assets/asset_depreciation/transfer/detail.html:172`
- **Description**: Template accesses `current_location` which doesn't exist on `scm.Asset`.
- **Remediation**: Change to `transfer.operational_asset.location.name`.

### [M2] Capitalization policy test widget display misses `manual_review` classification
- **Severity**: Minor
- **File & Line**: `templates/assets/asset_depreciation/capitalization_policy/detail.html:122`
- **Description**: Displays `EXPENSE IMMEDIATELY (OpEx)` for `manual_review` policies.
- **Remediation**: Add `elif eval_result.classification == 'manual_review'` branch rendering `FLAG FOR CONTROLLER MANUAL REVIEW`.

### [M3] Deep nested FK lookups in `depreciation_schedule_detail` and `transfer_detail`
- **Severity**: Minor
- **File & Line**: `AssetDepreciationSchedules.py:92-101`, `AssetTransfers.py:83-97`
- **Description**: Detail views can trigger 1-3 extra SQL queries when rendering fallback accounts and asset context.
- **Remediation**: Include `"fixed_asset__expense_account"`, `"fixed_asset__accumulated_account"` in schedule detail, and `"fixed_asset__location"`, `"fixed_asset__custodian"`, `"operational_asset__location"` in transfer detail.

### [M4] Missing `search_query` context alias in list views
- **Severity**: Minor
- **File & Line**: All 4 list views in `apps/assets/views/AssetDepreciation/`
- **Description**: List views pass `"q": q` but omit `"search_query": q`.
- **Remediation**: Pass `"search_query": q` in context dictionaries.

### [M5] Template physical directional margin classes (`mr-1`, `ml-*`) instead of logical RTL (`me-1`, `ms-*`)
- **Severity**: Minor
- **File & Line**: Templates across `templates/assets/asset_depreciation/`
- **Description**: Physical margin classes break bidirectional RTL layouts.
- **Remediation**: Replace `mr-1` with `me-1` and `ml-*` with `ms-*`.

### [M6] List pagination card footers missing standard padding and border classes
- **Severity**: Minor
- **File & Line**: All 4 list templates in `templates/assets/asset_depreciation/`
- **Description**: Missing `p-4 border-t border-slate-100` on `.card-footer`.
- **Remediation**: Add `p-4 border-t border-slate-100` to list card footers.

### [M7] Icon-only action buttons in list tables omit `aria-label`
- **Severity**: Minor
- **File & Line**: All 4 list templates in `templates/assets/asset_depreciation/`
- **Description**: Action buttons have `title` but lack `aria-label`.
- **Remediation**: Add `aria-label` matching `title`.
