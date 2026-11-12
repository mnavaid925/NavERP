# Phase 4 Master Review Findings — Sub-module 11.14 (`Asset Analytics & Business Intelligence`)

- **Base SHA:** `d1aa6e479b760216764b50899ded7488cdc07c15`
- **Scope:** 47 `11.14` implementation, template, migration, admin, seeder, and navigation files + 3 planning/contract docs (strictly excluding concurrent `11.15` files).
- **Review Passes Run Serially (Read-Only):**
  1. `code-reviewer` (`21e5afb6`)
  2. `explorer` (`21f6731e`)
  3. `frontend-reviewer` (`08f01669`)
  4. `performance-reviewer` (`e9515f35`)
  5. `qa-smoke-tester` (`a3df016c`)
  6. `security-reviewer` (`1aa1b645`)
- **Deduplicated Action Counts:** `6 Critical` (`C1`–`C6`) · `15 Important` (`I1`–`I15`) · `13 Minor` (`M1`–`M13`) — **Total: 34**
- **Status Legend:** `[ ] open` | `[x] fixed` | `[~] skipped — reason`

---

## Critical

- [x] fixed — **C1** *(Passes 5, 6)* | `apps/assets/forms/AssetAnalytics/_helpers.py:8-17`, `apps/assets/models/AssetAnalytics/_validators.py:41-43`, `apps/assets/views/AssetAnalytics/{AssetLifecycleCostAnalyses.py:150-156, AssetReplacementPlans.py:172-178, AssetPortfolioScenarios.py:142-148, AssetExecutiveScorecards.py:138-144}` — Fixed in `89205a0b`, `0a75d78f`, `a59d8181`, `ff2af6c7`, `afe591b8`, `4927373f`: `scope_tenant_fields()` returns empty querysets when `tenant is None`, `validate_tenant_fks()` requires non-null `tenant_id`, and all 4 `*_create` views guard `request.tenant is None`. *(Sibling `TenantModelForm` out-of-scope pattern-clone `L28`.)*
- [x] fixed — **C2** *(Passes 1, 2, 5)* | `apps/assets/views/AssetAnalytics/PortfolioDashboards.py:58-64` — Fixed in `9bc11c18`: `if org_unit_id or loc_id:` resolves `FixedAsset` PKs via `scm_qs.exclude(fixed_asset_id__isnull=True).values("fixed_asset_id")`.
- [x] fixed — **C3** *(Passes 1, 2, 5)* | `apps/assets/models/AssetAnalytics/AssetExecutiveScorecards.py:293-318` — Fixed in `782fc1a0`: `AssetCapitalization` and the four recovery querysets are scoped by `org_unit_id`, `asset_category_id`, and period date range.
- [x] fixed — **C4** *(Pass 3)* | `templates/assets/assetanalytics/asset_lifecycle_cost_analysis/detail.html:184-187,218-221,232-235` & `templates/assets/assetanalytics/portfolio_dashboard/scenario_compare.html:39-44,150-154` — Fixed in `db4e034b`, `9d30b9ca`: paired light financial summary rows and scenario cards with `dark:` variants.
- [x] fixed — **C5** *(Pass 3)* | `templates/assets/assetanalytics/asset_executive_scorecard/detail.html:34-59` — Fixed in `361c68ba`: added `onsubmit="return confirm('...');"` guards on Publish, Board Approve, and Archive POST forms.
- [x] fixed — **C6** *(Passes 1, 3)* | `apps/assets/forms/AssetAnalytics/AssetPortfolioScenarios.py:56` & `templates/assets/assetanalytics/asset_portfolio_scenario/form.html:84-87` — Fixed in `ec22b03d`, `f5bdcb1f`: switched widget class to `form-check`, inline flex row, and rendered `form.is_baseline.errors`.

---

## Important

- [x] fixed — **I1** *(Passes 5, 6)* | `apps/assets/views/AssetAnalytics/AssetExecutiveScorecards.py:189-198` & `templates/assets/assetanalytics/asset_executive_scorecard/{list.html:171-176, detail.html:60-65}` — Fixed in `edba8d70`, `4b00697b`, `4966c481`: blocked deletion when `scorecard.is_locked` and hid Delete buttons on locked scorecards.
- [x] fixed — **I2** *(Pass 6)* | `apps/assets/views/AssetAnalytics/AssetExecutiveScorecards.py:241-255` & `templates/assets/assetanalytics/asset_executive_scorecard/detail.html:44-51` — Fixed in `c18417b9`, `ab47423e`: enforced SoD check (`prepared_by_id != request.user.pk`) and hid Board Approve button for the preparer.
- [x] fixed — **I3** *(Passes 1, 5, 6)* | `apps/assets/forms/AssetAnalytics/{AssetLifecycleCostAnalyses.py, AssetReplacementPlans.py, AssetPortfolioScenarios.py, AssetExecutiveScorecards.py}`, 4 `form.html` templates, and `.claude/tasks/contract-assets-11.14.md` — Fixed in `0ef0a0ba`, `b1b324d3`, `87937662`, `2cddf2a4`, `f30657ea`, `ab4237a9`, `f7b480a3`, `f0102163`, `09d6f607`.
- [x] fixed — **I4** *(Passes 1, 3, 5, 6)* | `apps/assets/{models,views}/AssetAnalytics/{AssetLifecycleCostAnalyses,AssetReplacementPlans,AssetPortfolioScenarios}.py`, 6 templates, and `.claude/tasks/contract-assets-11.14.md` — Fixed in `9dd021e7`, `7db5755b`, `9b409e3b`, `889c845b`, `d5f0b8d9`, `9e8a7276`, `7524ba8c`, `d3fe1f13`, `dc7b89ad`, `b4a01183`, `02a03d14`, `e87e59f1`, `9dedd018`.
- [x] fixed — **I5** *(Passes 1, 5, 6)* | `apps/assets/{models,forms}/AssetAnalytics/{AssetPortfolioScenarios.py, AssetLifecycleCostAnalyses.py, AssetReplacementPlans.py}` — Fixed in `3faee16e`, `dc29db82`, `69583e63`, `0309096d`, `32c16266`, `4586be0f`.
- [x] fixed — **I6** *(Pass 6)* | `apps/assets/models/AssetAnalytics/{AssetLifecycleCostAnalyses.py, AssetReplacementPlans.py, AssetPortfolioScenarios.py, AssetExecutiveScorecards.py}` — Fixed in `9619cdc4`, `ae4e882d`, `283fe733`, `8a361f10`.
- [x] fixed — **I7** *(Passes 3, 6)* | 8 CRUD list/detail templates under `templates/assets/assetanalytics/` — Fixed in `71565134`, `01a24899`, `05b44ae1`, `52e6bca0`, `d88b7018`, `04a901d2`, `3a089135`, `f96b215a`.
- [x] fixed — **I8** *(Pass 4)* | `apps/assets/views/AssetAnalytics/*.py` — Fixed in `e46afb1f`, `a50dbf66`, `570dd660`, `4b2d5303`.
- [x] fixed — **I9** *(Pass 4)* | `apps/assets/views/AssetAnalytics/PortfolioDashboards.py` — Fixed in `38c145dd`.
- [x] fixed — **I10** *(Pass 4)* | `apps/assets/models/AssetAnalytics/*.py` & migration `0021` — Fixed in `22e6ce60`, `8fdddcf2`, `8a34517b`, `b0be790b`, `0e900114`.
- [x] fixed — **I11** *(Pass 4)* | `apps/assets/views/AssetAnalytics/*.py`, `AssetExecutiveScorecards.py` model, and `.claude/tasks/contract-assets-11.14.md` — Fixed in `5dd85425`, `01674e24`, `1675dfff`, `dd4c7501`, `2abb15fa`, `a592b871`, `df4b9a86`.
- [x] fixed — **I12** *(Pass 3)* | 4 `list.html` templates under `templates/assets/assetanalytics/` — Fixed in `51b555cc`, `c8d69e87`, `f471876e`, `66c68399`.
- [x] fixed — **I13** *(Pass 3)* | 4 `list.html` templates & `portfolio_dashboard/dashboard.html` — Fixed in `036b7d5a`, `b34eb57c`, `2a981223`, `a4cb52f9`, `24caf6ce`.
- [x] fixed — **I14** *(Pass 3)* | 14 templates under `templates/assets/assetanalytics/` — Fixed in `e7c6d9c6`, `ffb5fed0`, `decaecc5`, `0dbe6cdb`, `d327cc91`, `f20d4ce0`, `545077a4`, `c637369b`, `99dc2964`, `743049f0`, `fd396eff`, `64d6cfe6`, `6c44b5da`, `4ce79840`.
- [x] fixed — **I15** *(Pass 3)* | `apps/assets/templatetags/asset_analytics_tags.py`, templates, and `.claude/tasks/contract-assets-11.14.md` — Fixed in `169945c9`, `39faf7ba`, `4479dcc6`, `4ba96d45`, `4a5524dd`, `da20a659`, `4ebb4d22`, `03f60ce1`, `6a626bc3`, `e2c19e82`, `db81fe7e`, `1731a776`, `830b090a`.

---

## Minor

- [x] fixed — **M1** *(Passes 1, 2, 6)* | `apps/assets/admin.py:82-191` — Fixed in `46efe174`.
- [x] fixed — **M2** *(Passes 2, 3, 5)* | `apps/assets/views/AssetAnalytics/PortfolioDashboards.py` & `dashboard.html` — Fixed in `0f9f5d01`, `147fbe4e`.
- [x] fixed — **M3** *(Pass 2)* | `apps/assets/urls/AssetAnalytics/__init__.py` — Fixed in `318e6184`.
- [x] fixed — **M4** *(Pass 2)* | `apps/assets/views/__init__.py` — Fixed in `62977e1c`.
- [x] fixed — **M5** *(Pass 4)* | `PortfolioDashboards.py` & `apps/assets/forms/AssetAnalytics/*.py` — Fixed in `a375bdaa`, `507aec26`, `dbf2c218`, `0a35ea65`, `d94863f4`.
- [x] fixed — **M6** *(Passes 1, 4)* | `apps/assets/management/commands/seed_assets.py` — Fixed in `5b84f000`.
- [x] fixed — **M7** *(Pass 6)* | `apps/assets/views/AssetAnalytics/_helpers.py` & `PortfolioDashboards.py` — Fixed in `0c234224`, `48e161c9`.
- [x] fixed — **M8** *(Pass 6)* | `apps/assets/views/AssetAnalytics/*.py` — Fixed in `0dc02564`, `835b1396`, `26819f1d`, `059b9c49`.
- [x] fixed — **M9** *(Pass 6)* | Delete/lock `confirm()` handlers in `list.html` / `detail.html` templates — Fixed across `361c68ba`, `4b00697b`, `4966c481`, `7524ba8c`, `d3fe1f13`, `dc7b89ad`, `b4a01183`, `02a03d14`, `e87e59f1` (all `confirm()` interpolations verified using `|escapejs`).
- [x] fixed — **M10** *(Pass 3)* | Detail & list templates (`ALCC`, `ARPL`, `AWIF`, `AKPI`) — Fixed in `1779899c`, `e8ef85e9`, `8c2c24ec`, `ead781b4`, `a90dc11a`.
- [x] fixed — **M11** *(Pass 3)* | `templates/assets/assetanalytics/asset_portfolio_scenario/detail.html` — Fixed in `dd2ef6ae`.
- [x] fixed — **M12** *(Pass 3)* | RTL-safe alignment & `scenario_compare.html` polish — Fixed in `e51e1b79`, `e761d2b7`, `3855a914`, `88ab7fe1`, `491835bb`, `5bc70ef3`, `9683cbca`, `1c3a7033`.
- [x] fixed — **M13** *(Pass 3)* | All 4 `form.html` templates — Fixed in `03dfe3f4`, `7480269e`, `ded626d4`, `3fc4306c`.

---

## Follow-up Sibling Gap Resolved
- [x] fixed — **GAP-assets-11.16-04** | `apps/assets/views/AssetAnalytics/_helpers.py:22-29` — Fixed in `dfbd261a`: `apply_choice_filter` now ignores unrecognized GET choice parameters (`return qs`) per L11/L44.
