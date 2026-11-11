# Review Findings — Sub-module 11.12: Asset Risk Management

- **Module:** 11 Asset Management System
- **Sub-module:** 11.12 Asset Risk Management (`apps/assets`)
- **Review Range:** `675081c875a082e71e461d2caede11963fca22c6...HEAD`
- **Date:** 2026-11-11
- **Status:** Review Complete — Ready for Phase 5 Code Fixer

---

## Executive Summary

All six reviewers have run in strictly serial order:
1. `code-reviewer` — Analyzed correctness, multi-tenancy, authorization, and core-spine reuse.
2. `explorer` — Verified backend package layouts, re-export blocks, navigation wiring, and admin registration.
3. `frontend-reviewer` — Inspected design system compliance, color-named badges, and template filters.
4. `performance-reviewer` — Evaluated query counts, N+1 patterns, single-query aggregates, and indexing.
5. `qa-smoke-tester` — Executed runtime sweeps across all 27 URLs + landing page (85 passed / 1 failed).
6. `security-reviewer` — Audited tenant isolation, state machine transitions, CSRF, and input validation.

---

## Deduplicated Findings Catalog

### Critical

- [x] **`C1`**: `apps/assets/views/AssetRisk/AssetCyberSecurityProfiles.py:31` — HTTP 500 `FieldError` Crash on Search Filter
  - **Issue:** Query uses `Q(asset__asset_code__icontains=q)`, but `scm.Asset` defines `code`, not `asset_code`. Any search query `?q=<term>` on `/assets/risk/cybersecurity/` crashes with `FieldError: Unsupported lookup 'asset_code'`.
  - **Fix:** Replace `Q(asset__asset_code__icontains=q)` with `Q(asset__code__icontains=q)`.
  - **Status:** [x] fixed — fix(assets): fix asset code field lookup in cybersecurity search filter

---

### Important

- [x] **`I1`**: `templates/assets/assetrisk/` (8 occurrences across 4 templates) — Broken Template Field Reference `asset.asset_code` Rendering Blank
  - **Issue:** `scm.Asset` defines `code`, not `asset_code`. Template lookups `asset.asset_code`, `primary_asset.asset_code`, and `backup_redundant_asset.asset_code` fail silently and render blank strings in the UI.
  - **Locations:**
    - `templates/assets/assetrisk/asset_risk_register/list.html:137`: `rsk.asset.asset_code` -> `rsk.asset.code`
    - `templates/assets/assetrisk/asset_risk_register/detail.html:73`: `risk.asset.asset_code` -> `risk.asset.code`
    - `templates/assets/assetrisk/asset_business_continuity/list.html:124`: `plan.primary_asset.asset_code` -> `plan.primary_asset.code`
    - `templates/assets/assetrisk/asset_business_continuity/list.html:137`: `plan.backup_redundant_asset.asset_code` -> `plan.backup_redundant_asset.code`
    - `templates/assets/assetrisk/asset_business_continuity/detail.html:67`: `plan.primary_asset.asset_code` -> `plan.primary_asset.code`
    - `templates/assets/assetrisk/asset_business_continuity/detail.html:78`: `plan.backup_redundant_asset.asset_code` -> `plan.backup_redundant_asset.code`
    - `templates/assets/assetrisk/asset_cybersecurity/list.html:127`: `prof.asset.asset_code` -> `prof.asset.code`
    - `templates/assets/assetrisk/asset_cybersecurity/detail.html:52`: `profile.asset.asset_code` -> `profile.asset.code`
  - **Status:** [x] fixed — fix(assets): use asset code instead of asset_code across assetrisk templates

- [x] **`I2`**: `apps/assets/models/AssetRisk/AssetCyberSecurityProfiles.py:203` — Unhandled `RelatedObjectDoesNotExist` in `AssetCyberSecurityProfile.__str__`
  - **Issue:** Direct dereference of `self.asset.name` raises an uncaught exception if `asset` is not yet loaded or unset during form initialization or audit logging.
  - **Fix:** Change to `f"{self.number} — {self.asset.name if getattr(self, 'asset_id', None) else 'Unlinked'} ({self.get_device_type_display()})"`.
  - **Status:** [x] fixed — fix(assets): safeguard __str__ in AssetCyberSecurityProfile against unlinked asset

- [x] **`I3`**: `apps/assets/views/AssetRisk/` — Missing Server-Side State Machine Guards on Workflow Action Endpoints
  - **Issue:** Mutating POST actions execute unconditional status overwrites without validating the current status, allowing invalid transitions or regressions via direct POST.
  - **Fixes:**
    - In `AssetRiskRegisters.py:185`: `asset_risk_register_assess` must guard `if risk.status != "identified": return redirect(...)`.
    - In `AssetRiskRegisters.py:198`: `asset_risk_register_close` must guard `if risk.status == "closed": return redirect(...)`.
    - In `AssetBusinessContinuityPlans.py:177`: `asset_business_continuity_plan_activate` must guard `if plan.status not in ["draft", "under_review"]: return redirect(...)`.
    - In `AssetRiskMitigationActions.py:198`: `asset_risk_mitigation_action_complete` must guard `if action.status not in ["planned", "in_progress"]: return redirect(...)`.
    - In `AssetRiskMitigationActions.py:211`: `asset_risk_mitigation_action_verify` must guard `if action.status != "completed": return redirect(...)`.
  - **Status:** [x] fixed — fix(assets): add state machine guards on workflow action endpoints across assetrisk views

- [x] **`I4`**: `apps/assets/views/AssetRisk/` — Authorization Privilege Disparity on Critical Workflow Endpoints
  - **Issue:** Administrative/governance endpoints (`close`, `activate`, `verify`) require only `@login_required` while standard CRUD views require `@tenant_admin_required`. Non-admin tenant users could close high-exposure risks, activate continuity plans, or sign off on mitigations.
  - **Fixes:**
    - `AssetRiskRegisters.py:196`: add `@tenant_admin_required` to `asset_risk_register_close`.
    - `AssetBusinessContinuityPlans.py:175`: add `@tenant_admin_required` to `asset_business_continuity_plan_activate`.
    - `AssetRiskMitigationActions.py:209`: add `@tenant_admin_required` to `asset_risk_mitigation_action_verify`.
  - **Status:** [x] fixed — security(assets): require tenant_admin_required on critical workflow endpoints

---

### Minor

- [x] **`M1`**: `templates/assets/assetrisk/*/detail.html` (all 4 detail templates) — Missing "Back to List" Action Button in Header
  - **Issue:** Detail headers contain mutator actions but lack a direct `<a href="..." class="btn btn-outline"><i data-lucide="arrow-left" class="w-4 h-4 me-1"></i> Back to List</a>`.
  - **Fix:** Add Back to List button to `page-actions` across the 4 detail templates.
  - **Status:** [x] fixed — feat(assets): add back to list button across assetrisk detail templates

- [x] **`M2`**: `apps/assets/models/AssetRisk/AssetCyberSecurityProfiles.py:163` & `apps/assets/forms/AssetRisk/AssetCyberSecurityProfiles.py:51` — Server-Side Boundary Validation on CVSS Score
  - **Issue:** `cve_risk_score` lacks server-side range validation `[0.0, 10.0]`.
  - **Fix:** Add `MinValueValidator(Decimal("0.0")), MaxValueValidator(Decimal("10.0"))` to the model field and clean in form.
  - **Status:** [x] fixed — fix(assets): add CVSS range validators to AssetCyberSecurityProfile model and form

- [x] **`M3`**: `apps/assets/forms/AssetRisk/AssetBusinessContinuityPlans.py:30,32` — Disable Direct Editing of Drill History in General Edit Form
  - **Issue:** `last_drill_date` and `drill_result` are directly editable in `AssetBusinessContinuityPlanForm`.
  - **Fix:** Mark `last_drill_date` and `drill_result` as `disabled = True` in `__init__`.
  - **Status:** [x] fixed — fix(assets): disable drill history fields on AssetBusinessContinuityPlanForm

- [ ] **`M4`**: `templates/assets/assetrisk/*/list.html:94` — Accessibility: Icon-Only Filter Submit Button
  - **Issue:** Filter submit buttons lack `title` / `aria-label`.
  - **Fix:** Add `title="Apply Filters" aria-label="Apply Filters"` to the filter submit `<button>`.

- [ ] **`M5`**: `apps/assets/management/commands/seed_assets.py:3056,3079,3102,3125` — Redundant Calculation & Save Calls
  - **Issue:** `ark.calculate_scores()` and `ark.save()` are called after `create()`, triggering redundant SQL UPDATEs.
  - **Fix:** Remove redundant manual calculation calls.

- [ ] **`M6`**: `apps/assets/management/commands/seed_assets.py:3024-3026` — Sliced Queryset Consolidation for Asset Lookup
  - **Issue:** Multiple database roundtrips during tenant asset initialization.
  - **Fix:** Fetch assets via single sliced query `list(Asset.objects.filter(tenant=tenant).order_by("pk")[:3])`.

- [ ] **`M7`**: `apps/assets/views/AssetRisk/AssetBusinessContinuityPlans.py:20-25` — Defer Large TextField in Continuity Plan List View
  - **Issue:** `critical_spares_required` is an unbounded `TextField` pulled unnecessarily in list queries.
  - **Fix:** Add `"critical_spares_required"` to `.defer(...)` alongside `failover_procedure` and `failback_procedure`.
