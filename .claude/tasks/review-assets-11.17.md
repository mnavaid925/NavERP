# Consolidated Review Findings — Module 11.17: Space & Facility Asset Management

**Base SHA**: `a82a789039d6ffdd6fd134c64d56885f942230b0`
**Scope**: `BASE...HEAD` scoped strictly to Module `11.17` (`SpaceFacilityAsset` models, forms, views, URLs, templates, admin, navigation, overview, seeder, migration `0024`; concurrent Module `11.18` excluded).
**Passes Completed**: `code-reviewer` → `explorer` → `frontend-reviewer` → `performance-reviewer` → `qa-smoke-tester` (report-only) → `security-reviewer`

> **Rule for Phase 5 (`code-fixer`)**: Fix strictly in ID order (`I1` → `I10` → `M1` → `M16`), commit **one file per commit** (PowerShell `;` syntax, explicit `-- '<path>'`), batch all model schema/index changes (`I1` `PROTECT`, `I8`, `M16`, plus `M3` validator) before running `makemigrations assets --dry-run` and generating a single migration, and do **not** touch any `11.18` (`ItAssetManagement`) files. Mark each item `[x] fixed — <sha>` or `[~] skipped — <reason>`.

---

## Critical
- None found across all 6 review passes.

---

## Important

- [x] **I1**: TOCTOU race bypass on `edit` / `delete` lock checks & `SET_NULL` orphan risk on `AssetSpaceChargeback.journal_entry` — **fixed** (`5f152489`, `56757d1a`, `835eb891`, `5ffba78b`, `f1b11a33`, `e78d283f`)
  - **Sources**: Pass 6 (`security-reviewer` #1)
  - **Locations**: `apps/assets/views/SpaceFacilityAsset/AssetSpaceChargebacks.py:278-291,323-341`, `apps/assets/models/SpaceFacilityAsset/AssetSpaceChargebacks.py:158-165`, `apps/assets/views/SpaceFacilityAsset/AssetFacilitySpaces.py:271-285,314-332`, `apps/assets/views/SpaceFacilityAsset/AssetBuildingSystems.py:246-258,287-302`, `apps/assets/views/SpaceFacilityAsset/AssetFurnitureFixtures.py:245-255,284-298`
  - **Problem**: All four `edit` POST and `delete` handlers fetch the target row with unlocked `assets_object(...)` before `transaction.atomic()`, allowing a concurrent request to race past `can_edit` / `is_locked` / `journal_entry_id is not None`. In addition, `AssetSpaceChargeback.journal_entry` uses `on_delete=models.SET_NULL`, so racing `delete` against `post_gl` can orphan a live posted `JournalEntry`.
  - **Fix**: Inside `transaction.atomic()`, re-fetch the row via `get_object_or_404(assets_scope(Model.objects.select_for_update(), request), pk=pk)` and re-assert lock/status invariants before `form.save()` or `delete()`. Change `AssetSpaceChargeback.journal_entry` to `on_delete=models.PROTECT` (include in the single `11.17` follow-up migration).

- [x] **I2**: All four `11.17` `*_delete` views lack `@tenant_admin_required` — **fixed** (`835eb891`, `5ffba78b`, `f1b11a33`, `e78d283f`, `8566e406`, `0145c4b9`, `c44c6723`, `82615306`)
  - **Sources**: Pass 5 (`qa-smoke-tester` I2)
  - **Locations**: `apps/assets/views/SpaceFacilityAsset/AssetFacilitySpaces.py:310-313`, `apps/assets/views/SpaceFacilityAsset/AssetBuildingSystems.py:283-286`, `apps/assets/views/SpaceFacilityAsset/AssetFurnitureFixtures.py:280-283`, `apps/assets/views/SpaceFacilityAsset/AssetSpaceChargebacks.py:319-322` (plus respective detail views & templates)
  - **Problem**: Non-admin tenant users receive `302` and can delete records instead of `403 Forbidden`, unlike sibling Module 11 destructive endpoints.
  - **Fix**: Decorate all four `*_delete` views with `@tenant_admin_required` and gate `can_delete` in all four detail views with `is_tenant_admin_user(request.user)` (and list templates' delete button rendering behind admin check).

- [x] **I3**: Non-admin user can revert an admin-approved `AssetSpaceChargeback` back into editable `disputed` state — **fixed** (`835eb891`, `d7a47620`)
  - **Sources**: Pass 6 (`security-reviewer` #2)
  - **Locations**: `apps/assets/views/SpaceFacilityAsset/AssetSpaceChargebacks.py:537-556`, `apps/assets/models/SpaceFacilityAsset/AssetSpaceChargebacks.py:60-61`, `templates/assets/spacefacilityasset/asset_space_chargeback/detail.html`
  - **Problem**: Any authenticated tenant user can POST `asset_space_chargeback_dispute` on an `"approved"` chargeback, returning it to `"disputed"` (editable/deletable) while leaving `approved_by` and `approved_at` populated.
  - **Fix**: Restrict non-admin `dispute` to `"pending_approval"` (or require `is_tenant_admin_user(request.user)` to dispute `"approved"`), clear `approved_by`/`approved_at` when an admin disputes an approved chargeback, and hide the Dispute button on `"approved"` chargebacks from non-admins in `detail.html`.

- [x] **I4**: Cross-feature `AssetDocument` `access_classification` bypass on `floor_plan_document` and `schematic_document` — **fixed** (`f46df3d9`, `bbaf9b0f`, `5ffba78b`, `f1b11a33`, `198148d2`, `0819351d`)
  - **Sources**: Pass 6 (`security-reviewer` #3)
  - **Locations**: `apps/assets/forms/SpaceFacilityAsset/AssetFacilitySpaces.py:31,88-90`, `apps/assets/forms/SpaceFacilityAsset/AssetBuildingSystems.py:30,112-114`, `apps/assets/views/SpaceFacilityAsset/AssetFacilitySpaces.py:232`, `apps/assets/views/SpaceFacilityAsset/AssetBuildingSystems.py:220`, `templates/assets/spacefacilityasset/asset_facility_space/detail.html:140`, `templates/assets/spacefacilityasset/asset_building_system/detail.html:161`
  - **Problem**: Unlike Module 11.16 (`AssetOperatingProcedures`), `floor_plan_document` and `schematic_document` form dropdowns and detail templates expose restricted/confidential `AssetDocument` titles, numbers, and PKs to users lacking `is_asset_document_readable(doc, request.user)`.
  - **Fix**: Pass `user=request.user` into `AssetFacilitySpaceForm` and `AssetBuildingSystemForm` (keep backward-compatible default `user=None`), filter the document FK queryset with `readable_asset_document_q(self.user)` (and validate readability in `clean()`), and gate detail display behind `can_view_floor_plan_document` / `can_view_schematic_document` (`is_asset_document_readable(...)`), showing `"Restricted Document"` otherwise.

- [x] **I5**: Seeded `AssetFacilitySpace` demo records use legacy choice slugs absent from `SPACE_LEVEL_CHOICES` / `SPACE_CATEGORY_CHOICES` — **fixed** (`4715c188`)
  - **Sources**: Pass 1 (`CR-I1`), Pass 2 (`EX-I1`), Pass 5 (`QA-I1`)
  - **Locations**: `apps/assets/management/commands/seed_assets.py:4684-4826`
  - **Problem**: Seeded records store `"office_open"`, `"conference_room"`, `"mechanical_electrical"`, `"lab_cleanroom"`, `"zone"`, and `"suite"`, breaking list choice filters, `get_*_display()` labels, and edit dropdown preselection.
  - **Fix**: Update `_seed_tenant_11_17` to use `"office_workspace"`, `"conference_meeting"`, `"mechanical_room"`, `"cleanroom_lab"`, `"wing_zone"`, and `"room"`, validate with `.full_clean()` before saving in seeder, and update existing seeded DB rows / re-run `seed_assets` twice idempotently so MariaDB matches valid choices.

- [x] **I6**: Infrastructure Board CSV export drops `criticality_tier`, includes `hvac_climate`, and diverges on `q=` search — **fixed** (`f1b11a33`, `28d061d8`, `a6757560`)
  - **Sources**: Pass 1 (`CR-I2`), Pass 2 (`EX-I2`), Pass 5 (`QA-M1`)
  - **Locations**: `templates/assets/spacefacilityasset/infrastructure_board.html:21`, `apps/assets/views/SpaceFacilityAsset/InfrastructureBoard.py:30-70`, `apps/assets/views/SpaceFacilityAsset/AssetBuildingSystems.py:29-67,118-120`
  - **Problem**: The board Export CSV button points to `asset_building_system_export_csv` without `criticality_tier` or `INFRASTRUCTURE_DOMAINS` scoping, and `q=` search omits `load_or_voltage_rating` (present on the board) vs `manufacturer`/`model_number`/`serial_number`.
  - **Fix**: Add `criticality_tier` and `infra_only` filtering support in `_filtered_systems_queryset` (or a dedicated board CSV endpoint `asset_infrastructure_board_export_csv` / matching shared helper), pass `criticality_tier` + `infra_only=1` from `infrastructure_board.html`, and align `q=` search across both views.

- [x] **I7**: `AssetBuildingSystemForm.latest_energy_reading` causes N+1 queries via `AssetEnergyReading.__str__()` — **fixed** (`bbaf9b0f`)
  - **Sources**: Pass 4 (`PR-I1`)
  - **Locations**: `apps/assets/forms/SpaceFacilityAsset/AssetBuildingSystems.py:27,112-114`
  - **Problem**: `latest_energy_reading` queryset lacks `.select_related("fixed_asset", "operational_asset")`, firing 1–2 extra queries per reading when rendering the select widget.
  - **Fix**: Add `.select_related("fixed_asset", "operational_asset")` to the `latest_energy_reading` queryset in `AssetBuildingSystemForm.__init__`.

- [x] **I8**: Missing composite indexes on `AssetBuildingSystem` filter/board columns — **fixed** (`d532019b`, `56757d1a`)
  - **Sources**: Pass 4 (`PR-I2`)
  - **Locations**: `apps/assets/models/SpaceFacilityAsset/AssetBuildingSystems.py:281-287`, `apps/assets/views/SpaceFacilityAsset/InfrastructureBoard.py:35-36,61-66,72`, `apps/assets/views/SpaceFacilityAsset/AssetBuildingSystems.py:55,61`
  - **Problem**: Queries frequently filter on `(tenant, criticality_tier)`, `(tenant, condition_grade)`, and `(tenant, subsystem_type)` without composite indexes.
  - **Fix**: Add `idx_afbs_ten_crit`, `idx_afbs_ten_cond`, and `idx_afbs_ten_sub` to `AssetBuildingSystem.Meta.indexes` and generate one follow-up migration (run `makemigrations assets --dry-run` first to avoid colliding with concurrent migrations, combined with `I1` & `M16`).

- [x] **I9**: Broken contrast & hover on table row action buttons across all 5 list/board templates — **fixed** (`8566e406`, `0145c4b9`, `a6757560`, `c44c6723`, `82615306`)
  - **Sources**: Pass 3 (`FE-I1`)
  - **Locations**: `templates/assets/spacefacilityasset/asset_facility_space/list.html:165,167,170`, `templates/assets/spacefacilityasset/asset_building_system/list.html:174,176,179`, `templates/assets/spacefacilityasset/asset_furniture_fixture/list.html:163,165,168`, `templates/assets/spacefacilityasset/asset_space_chargeback/list.html:165,167,170`, `templates/assets/spacefacilityasset/infrastructure_board.html:176,178`
  - **Fix**: Use `theme.css` dedicated classes `class="btn-icon"` on View/Edit links and `class="btn-icon danger"` on Delete buttons (matching sibling Module 11 list templates).

- [x] **I10**: Numeric `0.00` measurements hidden by `|default:"—"` on Building System templates — **fixed** (`0145c4b9`, `0819351d`)
  - **Sources**: Pass 3 (`FE-I2`)
  - **Locations**: `templates/assets/spacefacilityasset/asset_building_system/list.html:162`, `templates/assets/spacefacilityasset/asset_building_system/detail.html:95,102,136,137`
  - **Fix**: Replace `|default:"—"` with `|default_if_none:"—"` on all nullable numeric fields (`setpoint_temp_c`, `measured_temp_c`, `target_humidity_pct`, `measured_humidity_pct`, `served_area_sqft`, `design_capacity_btu_kw`, `airflow_cfm`, etc.).

---

## Minor

- [x] **M1**: `AssetSpaceChargeback.compute_net_chargeback()` can overflow `DecimalField(max_digits=16, decimal_places=2)` and raise `DataError` (`apps/assets/models/SpaceFacilityAsset/AssetSpaceChargebacks.py:188-218,254-261`) — **fixed** (`5f152489`)
  - **Fix**: In `clean()`, reject totals `> Decimal("99999999999999.99")` with a field `ValidationError` on `base_cost_amount`.

- [x] **M2**: Decommissioned-record lock bypass on recalculation/comfort actions, unscoped `select_for_update()`, & Activate button visibility (`apps/assets/views/SpaceFacilityAsset/AssetFacilitySpaces.py:353-445`, `AssetBuildingSystems.py:313-430`, `asset_facility_space/detail.html:29-34,45-52`, `asset_building_system/detail.html:24-29`) — **fixed** (`5ffba78b`, `f1b11a33`, `198148d2`, `0819351d`)
  - **Fix**: Guard `recalculate_utilization` and `evaluate_comfort` with `if obj.is_locked:`, wrap all `select_for_update()` lookups in `assets_scope(..., request)`, and hide `Activate` on `decommissioned` records from non-admin users in detail templates.

- [x] **M3**: `floor_plan_image` upload validator missing at model/admin layer & inconsistent `tenant is None` guard on FF&E/Chargeback create (`AssetFacilitySpaces.py:183-187`, `AssetFurnitureFixtures.py:164-173`, `AssetSpaceChargebacks.py:185-194`) — **fixed** (`3eec583b`, `c2106745`, `ae503436`, `56757d1a`, `835eb891`, `e78d283f`)
  - **Fix**: Attach `validators=[validate_safe_floor_plan_upload]` to `AssetFacilitySpace.floor_plan_image` (or invoke in `clean()`) and add early `if tenant is None: messages.error(...); return redirect(...)` on FF&E & Chargeback create views.

- [x] **M4**: `AuditLog.action` verb drift from contract in FF&E IMAC views (`apps/assets/views/SpaceFacilityAsset/AssetFurnitureFixtures.py:354,431`) — **fixed** (`e78d283f`)
  - **Fix**: Align `"reconfig"` -> `"sched_mv"` and `"relocate"` -> `"comp_move"` per `.claude/tasks/contract-assets-11.17.md:21`.

- [x] **M5**: `AssetFacilitySpace.save()` overwrites `original_floor_plan_name` on non-upload edits (`apps/assets/models/SpaceFacilityAsset/AssetFacilitySpaces.py:283-286`) — **fixed** (`c2106745`)
  - **Fix**: Only capture `original_floor_plan_name` when `not getattr(self.floor_plan_image, "_committed", True)` or `not self.original_floor_plan_name`, and clear it when `not self.floor_plan_image`.

- [x] **M6**: Unordered `.first()` calls in `_seed_tenant_11_17` (`apps/assets/management/commands/seed_assets.py:4653-4681`) — **fixed** (`4715c188`)
  - **Fix**: Add `.order_by("pk")` before `.first()` for deterministic seeding.

- [x] **M7**: Detail-grid markup inconsistency on FF&E and Chargeback detail templates (`templates/assets/spacefacilityasset/asset_furniture_fixture/detail.html:112,166`, `asset_space_chargeback/detail.html:128,188`) — **fixed** (`03c16d5a`, `d7a47620`)
  - **Fix**: Use `<dl class="detail-grid"><div class="detail-item"><dt>...</dt><dd>...</dd></div></dl>` consistent with Space/BuildingSystem detail templates.

- [x] **M8**: Cancel button target inconsistency on Space & Building System edit forms (`asset_facility_space/form.html:174`, `asset_building_system/form.html:231`) — **fixed** (`534dc391`, `4d7b1677`)
  - **Fix**: Link Cancel to the detail page when `is_edit` is true (and list page on create).

- [x] **M9**: Missing `dark:text-blue-400` / `dark:text-amber-400` dark-mode contrast classes on inline links (`asset_facility_space/{detail,form}.html`, `asset_building_system/{list,detail}.html`, `asset_furniture_fixture/{list,detail}.html`, `asset_space_chargeback/{list,detail}.html`, `infrastructure_board.html`) — **fixed** (`198148d2`, `534dc391`, `0145c4b9`, `0819351d`, `a6757560`, `c44c6723`, `03c16d5a`, `82615306`, `d7a47620`)
  - **Fix**: Add `dark:text-blue-400` (and `dark:text-amber-400` on `asset_furniture_fixture/list.html:149`).

- [x] **M10**: RTL layout issues (`text-right` on all 5 list/board templates; `arrow-left` missing `rtl:rotate-180` on all 8 detail/form templates) — **fixed** (`8566e406`, `198148d2`, `534dc391`, `0145c4b9`, `0819351d`, `4d7b1677`, `a6757560`, `c44c6723`, `03c16d5a`, `9a9132d6`, `82615306`, `d7a47620`, `ce054bf7`)
  - **Fix**: Replace `text-right` with `text-end` and add `rtl:rotate-180` to `arrow-left` icons.

- [x] **M11**: Missing `aria-label` on icon-only table row buttons across all 5 list/board templates — **fixed** (`8566e406`, `0145c4b9`, `a6757560`, `c44c6723`, `82615306`)
  - **Fix**: Add descriptive `aria-label` including record number on View/Edit/Delete icon buttons.

- [x] **M12**: `.pagination` summary text alignment (`muted` class missing) across all 5 list/board templates (`list.html` x4 + `infrastructure_board.html`) — **fixed** (`8566e406`, `0145c4b9`, `a6757560`, `c44c6723`, `82615306`)
  - **Fix**: Add `muted` class on pagination summary span and align link styling with `theme.css`.

- [x] **M13**: `asset_facility_space_detail` `_can_delete_space` fires 5 separate `.exists()` queries after detail already evaluates child querysets (`AssetFacilitySpaces.py:70-79,236-263`) — **fixed** (`5ffba78b`)
  - **Fix**: Reuse already-evaluated/annotated child counts or consolidate checks where safe.

- [x] **M14**: Non-streaming CSV exports in `AssetFurnitureFixtures.py:121-140` and `AssetSpaceChargebacks.py:130-155` build in-memory `rows = []` lists — **fixed** (`835eb891`, `e78d283f`)
  - **Fix**: Refactor to a streaming generator yielding rows with `.iterator(chunk_size=500)`.

- [x] **M15**: Unused `select_related` joins on list/detail querysets (`AssetFacilitySpaces.py:31-37,239,244`, `AssetBuildingSystems.py:32-37`, `AssetFurnitureFixtures.py:31-39`, `AssetSpaceChargebacks.py:34-44`) — **fixed** (`835eb891`, `5ffba78b`, `f1b11a33`, `28d061d8`, `e78d283f`)
  - **Fix**: Trim unused `select_related` paths not rendered on list/detail templates.

- [x] **M16**: Secondary unindexed filter columns (`condition_grade` on `AssetFurnitureFixture`, `allocation_basis` and `(tenant, org_unit)` on `AssetSpaceChargeback`) — **fixed** (`5f152489`, `d30ef25a`, `56757d1a`)
  - **Fix**: Add composite `models.Index` entries alongside `I8` in the same follow-up migration.

---

## Phase 6 Query Budget Targets (`django_assert_max_num_queries`)
- List views (`AssetFacilitySpace`, `AssetFurnitureFixture`, `AssetSpaceChargeback`) & `InfrastructureBoard`: <= `14` queries; `AssetBuildingSystem` list: <= `12` queries.
- Detail views & `AssetBuildingSystemForm`: <= `10` queries.
- `assets:overview`: <= `34` queries.
