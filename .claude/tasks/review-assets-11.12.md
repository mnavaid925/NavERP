# Review Findings — Sub-module 11.12: Asset Risk Management

- **Module:** 11 Asset Management System
- **Sub-module:** 11.12 Asset Risk Management (`apps/assets`)
- **Review Range:** `675081c875a082e71e461d2caede11963fca22c6...HEAD`
- **Date:** 2026-11-11
- **Status:** In Progress (Serial Review Passes)

### Pass 2: Codebase Explorer (`explorer`)
- **Structure & Wiring Verification:**
  - Package structure, re-exports in all `__init__.py` files, `LIVE_LINKS["11.12"]` in `navigation.py`, admin classes in `admin.py`, and URL pattern concatenation confirmed 100% complete.
  - Zero duplicate models; proper reuse of `scm.Asset`, `assets.AssetCategory`, `core.Party`, `settings.AUTH_USER_MODEL`.
- **Critical:**
  - `apps/assets/views/AssetRisk/AssetCyberSecurityProfiles.py:31`: Search crash on connected asset lookup (`asset__asset_code` -> `asset__code`).
- **Important:**
  - `apps/assets/models/AssetRisk/AssetCyberSecurityProfiles.py:203`: Unhandled `RelatedObjectDoesNotExist` in `__str__`.
  - `templates/assets/assetrisk/` (8 occurrences across 4 templates): Broken template field reference `asset.asset_code` -> should be `asset.code`.
  - Missing view-level status transition guards on state action endpoints (`complete`, `verify`, `assess`, `close`, `activate`).
- **Minor:**
  - Missing "Back to List" button in `.page-actions` across the 4 detail templates.
  - Action endpoint authorization disparity (`@tenant_admin_required`).
  - Redundant manual calculation calls in `seed_assets.py`.

### Pass 3: Frontend Reviewer (`frontend-reviewer`)
- **Critical:** None (zero comment leak traps, zero pagination 500s, zero missing CSRF).
- **Important:**
  - `templates/assets/assetrisk/` (8 occurrences across 4 templates): Broken field reference `asset.asset_code` on `scm.Asset` (which only defines `code`), rendering asset code blank. Fix: replace with `asset.code` in:
    - `asset_risk_register/list.html:137`
    - `asset_risk_register/detail.html:73`
    - `asset_business_continuity/list.html:124,137`
    - `asset_business_continuity/detail.html:67,78`
    - `asset_cybersecurity/list.html:127`
    - `asset_cybersecurity/detail.html:52`
- **Minor:**
  - `templates/assets/assetrisk/*/detail.html:21`: Missing explicit "Back to List" action button in `.page-actions` header.
  - `templates/assets/assetrisk/*/list.html:94`: Icon-only filter submit button missing `title` / `aria-label="Apply Filters"` for accessibility.

### Pass 4: Performance Reviewer (`performance-reviewer`)
- **Query Efficiency & Optimization Verification:**
  - All 4 list views use single-query `.aggregate(...)` for KPI statistics.
  - All foreign keys looped in templates are eagerly fetched via `select_related(...)`.
  - All pagination queries are applied after filtering and use `Paginator(qs, 25)`.
- **Critical:** None.
- **Important:** None.
- **Minor:**
  - `apps/assets/models/AssetRisk/AssetCyberSecurityProfiles.py:203`: In mutator/action views (`edit`, `delete`, `scan`), `write_audit_log` triggers lazy evaluation of `self.asset.name`.
  - `apps/assets/management/commands/seed_assets.py:3024-3026`: Consolidate 5 queries into a single sliced evaluation (`list(Asset.objects.filter(tenant=tenant).order_by("pk")[:3])`).
  - `apps/assets/management/commands/seed_assets.py:3056,3079,3102,3125`: Remove redundant manual `.save()` / `calculate_scores()` calls.
  - `apps/assets/views/AssetRisk/AssetBusinessContinuityPlans.py:20-25`: Add `"critical_spares_required"` to `.defer(...)` alongside other TextFields.
  - Secondary filter columns can optionally add composite indexes (`idx_ark_ten_strat`, `idx_arma_ten_eff`, `idx_abc_ten_scen`, `idx_acs_ten_dev`).

### Pass 5: QA Smoke Tester (`qa-smoke-tester`)
- **Runtime URL Matrix (27 URLs + Landing):**
  - 85 runtime checks passed.
  - Cross-tenant IDOR verified: all foreign tenant accesses return 404.
  - `@require_POST` verified: GET requests to mutators/actions return 405.
- **Critical:**
  - `CRIT-1`: `apps/assets/views/AssetRisk/AssetCyberSecurityProfiles.py:31`: Search query `?q=<term>` crashes with HTTP 500 `FieldError: Unsupported lookup 'asset_code' for ForeignKey`. Fix: change to `Q(asset__code__icontains=q)`.
- **Important:**
  - `IMP-1`: `templates/assets/assetrisk/` (8 locations): Silent blank rendering of `asset.asset_code` across list and detail pages. Fix: change to `asset.code`.
  - `IMP-2`: `apps/assets/models/AssetRisk/AssetCyberSecurityProfiles.py:203`: Unhandled `RelatedObjectDoesNotExist` in `__str__`.
- **Minor:**
  - `MIN-1`: Missing "Back to List" action button across all 4 detail templates.
  - `MIN-2`: Action endpoint authorization disparity (`@tenant_admin_required`).

---

## Review Pass Log

### Pass 1: Code Reviewer (`code-reviewer`)
- **Critical:**
  - `apps/assets/views/AssetRisk/AssetCyberSecurityProfiles.py:31`: Search crash: `qs.filter(Q(asset__asset_code__icontains=q))` raises `FieldError` because `scm.Asset` defines `code`, not `asset_code`. Fix: replace with `Q(asset__code__icontains=q)`.
- **Important:**
  - `apps/assets/models/AssetRisk/AssetCyberSecurityProfiles.py:203`: Unhandled `RelatedObjectDoesNotExist` in `__str__`: `self.asset.name` raises exception when `asset` is not yet loaded or unset. Fix: change to `f"{self.number} — {self.asset.name if self.asset_id else 'Unlinked'} ({self.get_device_type_display()})"`.
  - `apps/assets/views/AssetRisk/AssetRiskMitigationActions.py:198,211`: Missing view-level status guards on workflow transitions: `complete` does not verify `action.status in ['planned', 'in_progress']`, and `verify` does not check `action.status == 'completed'`.
  - `apps/assets/views/AssetRisk/AssetRiskRegisters.py:185,198`: Missing view-level status guards: `assess` allows overwriting status on closed/treating risks, and `close` does not guard against closing already closed risks.
  - `apps/assets/views/AssetRisk/AssetBusinessContinuityPlans.py:177`: Missing view-level status guard: `activate` does not check if `plan.status in ['draft', 'under_review']`.
  - `templates/assets/assetrisk/` (8 templates): Broken field reference `asset.asset_code`. In `asset_risk_register/list.html:137`, `asset_risk_register/detail.html:73`, `asset_business_continuity/list.html:124,137`, `asset_business_continuity/detail.html:67,78`, `asset_cybersecurity/list.html:127`, and `asset_cybersecurity/detail.html:52`, change `asset.asset_code` to `asset.code`.
- **Minor:**
  - `templates/assets/assetrisk/*/detail.html`: Missing "Back to List" link in detail header actions.
  - `apps/assets/views/AssetRisk/{AssetBusinessContinuityPlans.py,AssetRiskMitigationActions.py,AssetRiskRegisters.py}`: Action endpoint authorization disparity: `activate`, `verify`, `assess`, `close` require only `@login_required` while CRUD views require `@tenant_admin_required`.
  - `apps/assets/management/commands/seed_assets.py:3056`: Redundant model method calls `ark.calculate_scores()` and `ark.save()` after `create()`.

### Pass 2: Codebase Explorer (`explorer`)
- **Structure & Wiring Verification:**
  - Package structure, re-exports in all `__init__.py` files, `LIVE_LINKS["11.12"]` in `navigation.py`, admin classes in `admin.py`, and URL pattern concatenation confirmed 100% complete.
  - Zero duplicate models; proper reuse of `scm.Asset`, `assets.AssetCategory`, `core.Party`, `settings.AUTH_USER_MODEL`.
- **Critical:**
  - `apps/assets/views/AssetRisk/AssetCyberSecurityProfiles.py:31`: Search crash on connected asset lookup (`asset__asset_code` -> `asset__code`).
- **Important:**
  - `apps/assets/models/AssetRisk/AssetCyberSecurityProfiles.py:203`: Unhandled `RelatedObjectDoesNotExist` in `__str__`.
  - `templates/assets/assetrisk/` (8 occurrences across 4 templates): Broken template field reference `asset.asset_code` -> should be `asset.code`.
  - Missing view-level status transition guards on state action endpoints (`complete`, `verify`, `assess`, `close`, `activate`).
- **Minor:**
  - Missing "Back to List" button in `.page-actions` across the 4 detail templates.
  - Action endpoint authorization disparity (`@tenant_admin_required`).
  - Redundant manual calculation calls in `seed_assets.py`.

### Pass 3: Frontend Reviewer (`frontend-reviewer`)
- **Critical:** None (zero comment leak traps, zero pagination 500s, zero missing CSRF).
- **Important:**
  - `templates/assets/assetrisk/` (8 occurrences across 4 templates): Broken field reference `asset.asset_code` on `scm.Asset` (which only defines `code`), rendering asset code blank. Fix: replace with `asset.code` in:
    - `asset_risk_register/list.html:137`
    - `asset_risk_register/detail.html:73`
    - `asset_business_continuity/list.html:124,137`
    - `asset_business_continuity/detail.html:67,78`
    - `asset_cybersecurity/list.html:127`
    - `asset_cybersecurity/detail.html:52`
- **Minor:**
  - `templates/assets/assetrisk/*/detail.html:21`: Missing explicit "Back to List" action button in `.page-actions` header.
  - `templates/assets/assetrisk/*/list.html:94`: Icon-only filter submit button missing `title` / `aria-label="Apply Filters"` for accessibility.

### Pass 4: Performance Reviewer (`performance-reviewer`)
- **Query Efficiency & Optimization Verification:**
  - All 4 list views use single-query `.aggregate(...)` for KPI statistics.
  - All foreign keys looped in templates are eagerly fetched via `select_related(...)`.
  - All pagination queries are applied after filtering and use `Paginator(qs, 25)`.
- **Critical:** None.
- **Important:** None.
- **Minor:**
  - `apps/assets/models/AssetRisk/AssetCyberSecurityProfiles.py:203`: In mutator/action views (`edit`, `delete`, `scan`), `write_audit_log` triggers lazy evaluation of `self.asset.name`.
  - `apps/assets/management/commands/seed_assets.py:3024-3026`: Consolidate 5 queries into a single sliced evaluation (`list(Asset.objects.filter(tenant=tenant).order_by("pk")[:3])`).
  - `apps/assets/management/commands/seed_assets.py:3056,3079,3102,3125`: Remove redundant manual `.save()` / `calculate_scores()` calls.
  - `apps/assets/views/AssetRisk/AssetBusinessContinuityPlans.py:20-25`: Add `"critical_spares_required"` to `.defer(...)` alongside other TextFields.
  - Secondary filter columns can optionally add composite indexes (`idx_ark_ten_strat`, `idx_arma_ten_eff`, `idx_abc_ten_scen`, `idx_acs_ten_dev`).

### Pass 5: QA Smoke Tester (`qa-smoke-tester`)
- **Runtime URL Matrix (27 URLs + Landing):**
  - 85 runtime checks passed.
  - Cross-tenant IDOR verified: all foreign tenant accesses return 404.
  - `@require_POST` verified: GET requests to mutators/actions return 405.
- **Critical:**
  - `CRIT-1`: `apps/assets/views/AssetRisk/AssetCyberSecurityProfiles.py:31`: Search query `?q=<term>` crashes with HTTP 500 `FieldError: Unsupported lookup 'asset_code' for ForeignKey`. Fix: change to `Q(asset__code__icontains=q)`.
- **Important:**
  - `IMP-1`: `templates/assets/assetrisk/` (8 locations): Silent blank rendering of `asset.asset_code` across list and detail pages. Fix: change to `asset.code`.
  - `IMP-2`: `apps/assets/models/AssetRisk/AssetCyberSecurityProfiles.py:203`: Unhandled `RelatedObjectDoesNotExist` in `__str__`.
- **Minor:**
  - `MIN-1`: Missing "Back to List" action button across all 4 detail templates.
  - `MIN-2`: Action endpoint authorization disparity (`@tenant_admin_required`).

---

