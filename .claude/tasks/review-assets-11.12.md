# Review Findings — Sub-module 11.12: Asset Risk Management

- **Module:** 11 Asset Management System
- **Sub-module:** 11.12 Asset Risk Management (`apps/assets`)
- **Review Range:** `675081c875a082e71e461d2caede11963fca22c6...HEAD`
- **Date:** 2026-11-11
- **Status:** In Progress (Serial Review Passes)

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

---

