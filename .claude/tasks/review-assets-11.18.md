# Module 11.18 IT Asset Management (ITAM) — Consolidated Review Findings Register

> **Scope**: Module 11.18 IT Asset Management (`apps/assets/{models,forms,views,urls}/ItAssetManagement/`, `templates/assets/itassetmanagement/`, and 11.18 sections of `admin.py`, `seed_assets.py`, `navigation.py`, `0024`). Sibling 11.17 `SpaceFacilityAsset` files excluded per L53.
> **Reviewers Executed (Serial 6/6)**: `code-reviewer` -> `explorer` -> `frontend-reviewer` -> `performance-reviewer` -> `qa-smoke-tester` (report-only) -> `security-reviewer`.
> **Legend**: `- [ ]` Open · `- [x] fixed — <commit/reason>` · `- [~] skipped — <reason>`

---

## Critical (`C1`–`C4`)

- [x] **C1** (`code-reviewer`, `explorer`, `qa-smoke-tester`) — fixed in `f3d648b2`: Replaced invalid/overlength seeded choice keys with valid model `*_CHOICES` keys in `seed_assets.py`, cleared stale 11.18 demo rows, and re-seeded cleanly twice (95 HW, 76 SW, 76 CL, 100 CMDB all pass `.full_clean()`).
  - **Problem**: Seeded `ItHardwareAsset` rows (`server_physical`, `tier_1_mission_critical`, `server_virtual`, `network_switch_router`, `exempt_network_gear`, `workstation`, `tier_3_operational`, `filevault_enabled`, `storage_san_nas`, `disaster_recovery`, `tier_2_business_important`, `nist_purge_cryptographic_erase`) and 3 of 4 `SoftwareLicense` rows (`database_data`, `enterprise_agreement`, `developer_devops`, `named_user`, `cad_engineering`, `concurrent_floating`) use non-existent choice keys (truncating `criticality` and `sanitization_method` in MariaDB, failing `.full_clean()`, breaking dropdown filters, and rendering raw keys in HTML).
  - **Fix**: Replace with exact model `*_CHOICES` keys (`physical_server`, `critical`, `virtual_host`, `router_firewall`, `exempt`, `corporate_enduser`, `medium`, `bitlocker_filevault`, `storage_array`, `dr_standby`, `high`, `crypto_erase`; `database_engine`/`enterprise_ela`, `devops_ide`/`subscription_term`, `design_cad`/`perpetual`), and run a cleanup/re-seed for 11.18 demo rows in DB (without wiping other modules or 11.17).

- [x] **C2** (`code-reviewer`, `qa-smoke-tester`, `security-reviewer`) — fixed in `eede2677`, `da6c9909`: Preserved `audit_hold` on `SoftwareLicense`, enforced `is_tenant_admin_user` (`403 PermissionDenied`) on `edit`, `sync_compliance`, `reclaim_inactive`, and `renew_term` while on hold, and hid mutating controls in `software_license/detail.html` for non-admins.
  - **Problem**: Non-admin authenticated users POSTing to `software_license_sync_compliance` (`:287-288`) reset `"audit_hold"` imposed by `@tenant_admin_required` (`software_license_place_audit_hold` at `:395`), unilaterally lifting an audit hold. Additionally, `software_license_edit`, `software_license_reclaim_inactive`, and `software_license_renew_term` only check `is_locked` (`retired`), letting non-admins alter entitlements, allocations, and renewal dates during an active vendor audit hold, and detail UI shows hold-clearing/mutating actions to non-admins.
  - **Fix**: Preserve `audit_hold` in `software_license_sync_compliance` (do not allow non-admins to clear it), reject non-admin mutations (`edit`, `sync_compliance`, `reclaim_inactive`, `renew_term`) when `license_obj.status == "audit_hold"` (allowing tenant admins if they are lifting/managing the hold or keeping hold-management admin-only), and hide/gate those action controls in `software_license/detail.html` for non-admins when `license_obj.status == "audit_hold"`.

- [x] **C3** (`code-reviewer`, `qa-smoke-tester`, `security-reviewer`) — fixed in `e36ca9ab`, `491f535a`: Removed unsuspend reset branches from `sanction`/`renew`, enforced `is_tenant_admin_user` (`403 PermissionDenied`) across suspended `CloudAssetSubscription` endpoints, and hid mutating controls in `cloud_asset_subscription/detail.html` for non-admins.
  - **Problem**: Non-admin authenticated users POSTing to `cloud_asset_subscription_sanction` (`:316-317`), `cloud_asset_subscription_renew` (`:383-384`), or `cloud_asset_subscription_flag_shadow` (`:344`) overwrite an admin-placed `status="suspended"` back to `"active"` or `"shadow_flagged"`, bypassing `@tenant_admin_required` on `cloud_asset_subscription_suspend`. Also `cloud_asset_subscription_edit` and `sync_finops` allow non-admin edits while suspended, and detail UI lacks admin-gate symmetry.
  - **Fix**: Remove the `if cloud_asset.status == "suspended":` reset branches from `sanction` and `renew`, guard `edit`, `sanction`, `flag_shadow`, `sync_finops`, and `renew` against `cloud_asset.status == "suspended"` unless `is_tenant_admin_user(request.user)`, and hide those controls for non-admins in `cloud_asset_subscription/detail.html` when `cloud_asset.status == "suspended"`.

- [x] **C4** (`security-reviewer`) — fixed in `a3d95cb9`, `be2f585a`, `6ac542f2`: Restricted NIST sanitization fields on `ItHardwareAssetForm` to tenant admins, synced `sanitization_verified_by`/`sanitized_at` on admin saves, and hid sanitization inputs in `it_hardware_asset/form.html` for non-admins.
  - **Problem**: `ItHardwareAssetForm` exposes `sanitization_required`, `sanitization_method`, `sanitization_status`, `sanitization_date`, and `sanitization_certificate_ref` in `@login_required` create/edit views, allowing non-admins to disable `sanitization_required` or self-assert `wiped_verified`/`certificate_on_file` (bypassing `@tenant_admin_required` on `it_hardware_asset_mark_sanitized` and leaving `sanitization_verified_by`/`sanitized_at` unset or stale).
  - **Fix**: Restrict non-admins in `ItHardwareAssetForm` / `create` / `edit` so they cannot set `sanitization_status` to `wiped_verified`/`certificate_on_file` or tamper with sanitization compliance fields once verified (or gate sanitization-attestation fields to tenant admins / `mark_sanitized`), clear `sanitization_verified_by`/`sanitized_at` if status is reset by an admin, and update `it_hardware_asset/form.html` cleanly to match.

---

## Important (`I1`–`I12`)

- [x] **I1** (`code-reviewer`, `qa-smoke-tester`, `security-reviewer`) — fixed in `39b6791a`: Guarded `it_hardware_asset_mark_sanitized` with `hardware.is_locked` instead of `"disposed"`-only.
  - **Problem**: Line `375` only checks `if hardware.status == "disposed":` instead of `if hardware.is_locked:`, permitting sanitization mutations after lock in `"sanitized_retired"`.
  - **Fix**: Replace `if hardware.status == "disposed":` with `if hardware.is_locked:`.

- [x] **I2** (`code-reviewer`, `security-reviewer`) — fixed in `a46609aa`: Enforced `relationship.full_clean()` inside `transaction.atomic()` in `cmdb_relationship_verify` and surfaced `ValidationError` via `messages.error`.
  - **Problem**: Transitions `"planned"` or `"deprecated"` edges to `"active"` via `save(update_fields=...)` without calling `relationship.full_clean()`, bypassing duplicate active edge validation in `CmdbRelationship.clean()`.
  - **Fix**: Call `relationship.full_clean()` inside `transaction.atomic()` before `relationship.save(...)` and catch `ValidationError` -> `messages.error` + redirect to detail.

- [x] **I3** (`main-inspection`) — fixed in `b4ddbe21`, `4cc06c57`, `b6b88a92`, `22820b3c`: Guarded `request.tenant is None` on POST and bound `form.instance.tenant = request.tenant` before `form.is_valid()` across all four ITAM create views.
  - **Problem**: If `request.tenant is None` (Django superuser `admin`), submitting any create form assigns `obj.tenant = None` -> `IntegrityError` 500; also during `form.is_valid()` on create, `self.instance.tenant_id` is still `None` when `Model.clean()` runs `validate_tenant_fks`.
  - **Fix**: Guard `if request.tenant is None: messages.warning(...); return redirect(...)` on POST in all 4 create views, and assign `form.instance.tenant = request.tenant` before `form.is_valid()` (or bind `instance.tenant` when `form` constructs if unset) so `Model.clean()` always sees `tenant_id`.

- [x] **I4** (`code-reviewer`, `frontend-reviewer`) — fixed in `3fba7ddf`, `7c46d14f`: Replaced invalid `stat-icon amber` with `stat-icon orange` in `software_license/detail.html` and `cloud_asset_subscription/detail.html`.
  - **Problem**: Uses `stat-icon amber`, which does not exist in `static/css/theme.css:260-265` (only `green`, `orange`, `purple`, `blue`, `slate`, `red` exist).
  - **Fix**: Change `amber` to `orange` in both templates.

- [x] **I5** (`code-reviewer`, `frontend-reviewer`) — fixed in `60fc1ff2`, `5dbafa79`: Replaced `.card-footer` with `.pagination` + `<span class="muted">` in `cloud_asset_subscription/list.html` and `cmdb_relationship/list.html`.
  - **Problem**: Uses `<div class="card-footer ...">` instead of `<div class="pagination">` with `<span class="muted">Showing ...</span>` matching `it_hardware_asset/list.html:233-248`.
  - **Fix**: Switch both footers to `.pagination` + `<span class="muted">`.

- [x] **I6** (`frontend-reviewer`) — fixed in `9b051c20`, `a3da526b`: Added `<th class="th-actions">Actions</th>`, View, Edit (`not is_locked`), and admin/lock-gated POST Delete buttons to `cloud_asset_subscription/list.html` and `cmdb_relationship/list.html`.
  - **Problem**: Actions column renders only `View` with empty `<th></th>`, missing `<th class="th-actions">Actions</th>`, `Edit` (`{% if not obj.is_locked %}`), and admin-gated POST `Delete` with `{% csrf_token %}` and `|escapejs` confirm.
  - **Fix**: Add View, Edit (`not is_locked`), and admin/lock-gated POST Delete icon buttons matching `it_hardware_asset/list.html` / `software_license/list.html`.

- [x] **I7** (`frontend-reviewer`) — fixed in `cea0f3e2`, `455427db`: Added `<div class="empty-state">` with icon, heading, description, and create CTA to `cloud_asset_subscription/list.html` and `cmdb_relationship/list.html`.
  - **Problem**: Empty table row renders bare text instead of `.empty-state` (`static/css/theme.css:324-326`) with icon, heading, description, and create button.
  - **Fix**: Wrap with `<div class="empty-state">` + create CTA matching `it_hardware_asset/list.html:218-225`.

- [x] **I8** (`performance-reviewer`) — fixed in `dbcd8969`, `8c9338ff`: Added `select_related("fixed_asset")` for `AssetScrapSalvage` in `scope_tenant_querysets()` and `"scrap_salvage__fixed_asset"` in `_HW_DETAIL_SELECT_RELATED`.
  - **Problem**: `AssetScrapSalvage.__str__` accesses `self.fixed_asset.name`; `scope_tenant_querysets()` and `_HW_DETAIL_SELECT_RELATED` omit `select_related("fixed_asset")` / `"scrap_salvage__fixed_asset"`.
  - **Fix**: Add `elif model_cls.__name__ == "AssetScrapSalvage": qs = qs.select_related("fixed_asset")` and include `"scrap_salvage__fixed_asset"` in `_HW_DETAIL_SELECT_RELATED`.

- [x] **I9** (`performance-reviewer`) — fixed in `3aaee9ef`: Pushed `ItRefreshBoards` KPIs, horizon/priority filters, and OrgUnit CapEx rollup to SQL `.aggregate()`/`.annotate()`, capped rendered boards to 200 rows, trimmed unused FKs, and streamed CSV.
  - **Problem**: Loops all non-locked `ItHardwareAsset` rows in Python for KPIs and `org_unit_summary`, materializes unbounded `software_rows`/`cloud_rows`, and joins 5 unused FKs (`owner`, `currency`, `license_owner`, `business_owner`).
  - **Fix**: Compute `overdue_hw_count`, `due_90d_hw_count`, `pending_wipe_count`, and `org_unit_summary` via SQL `.aggregate()` / `.values("org_unit__name").annotate(...)`, push horizon/priority filters to SQL `Q(...)`, cap rendered lists (`[:200]`), and trim `select_related`.

- [x] **I10** (`performance-reviewer`) — fixed in `a66b4f27`, `3475aaed`: Converted `build_ci_label_map()` to bounded `.values_list(...)[:500]`, dropped redundant 12-JOIN `select_related` in `CmdbImpactAnalyses`, and resolved `spof_edges` labels from `label_map`.
  - **Problem**: `build_ci_label_map()` executes 5 unbounded `SELECT *` queries hydrating full ORM instances; `_build_impact_context()` joins 12 unused tables on `edges_qs` despite `label_map` caching every CI label.
  - **Fix**: Use bounded `.values_list(...)` in `build_ci_label_map()`, drop `select_related(*CMDB_REL_SELECT_RELATED)` in `CmdbImpactAnalyses`, and resolve `spof_edges` labels via `label_map`.

- [x] **I11** (`performance-reviewer`) — fixed in `d2ec695e`, `817c32bf`, `e27daba2`, `4ee2ba4d`, `3aaee9ef`: Parameterized `select_related` on `_filter_*_queryset` for exports and streamed `qs[:10000].iterator(chunk_size=1000)` across all five ITAM CSV export endpoints.
  - **Problem**: Export views iterate unbounded `qs` before `islice(..., 10000)` and reuse heavyweight list `select_related` JOINs not exported to CSV.
  - **Fix**: Parameterize `select_related` on `_filter_*_queryset(..., select_related=...)` and stream `qs[:10000].iterator(chunk_size=1000)`.

- [x] **I12** (`performance-reviewer`) — fixed in `cac3d5e7`, `a9ce2ca4`, `32cb8658`, `db051200`, `56757d1a`: Added composite `Meta.indexes` (<= 30 chars) to all four ITAM models and generated/applied `0025_alter_assetfacilityspace_floor_plan_image_and_more.py` (which also incorporates pre-existing committed 11.17 model edits present on `HEAD`).
  - **Problem**: Default `Meta.ordering` pairs (`(tenant, hostname)`, `(tenant, software_name)`, `(tenant, name)`, `(tenant, -updated_at)`) and high-frequency list filter columns lack composite indexes.
  - **Fix**: Add composite `Meta.indexes` (all `<= 30` chars) and generate a clean incremental migration (verify `--dry-run` against clean 11.17 state first per L51/L53).

---

## Minor (`M1`–`M12`)

- [x] **M1** (`code-reviewer`, `explorer`, `security-reviewer`) — fixed in `10fc9f7b`, `e18ede5a`, `a32f0263`: Updated `validate_tenant_fks` to always return accumulated error dicts without early raise, and aligned `ItHardwareAsset.clean()` and `SoftwareLicense.clean()` with uniform error accumulation.
  - **Problem**: `validate_tenant_fks` raises immediately instead of returning the accumulated `errors` dict, short-circuiting subsequent field checks in `clean()`, and models invoke it inconsistently.
  - **Fix**: Always return `errors` dict (never raise inside `validate_tenant_fks`) and accumulate `errors = validate_tenant_fks(...)` uniformly in all 4 models before raising `ValidationError(errors)` once.

- [x] **M2** (`code-reviewer`, `security-reviewer`) — fixed in `fd7e9f92`, `9c3db956`, `e14e0885`: Moved and hardened `validate_masked_key_ref` in `_validators.py`, re-exported in `forms/ItAssetManagement/_helpers.py`, and enforced it inside `SoftwareLicense.clean()`.
  - **Problem**: `validate_masked_key_ref` skips validation if `"x"` appears anywhere or no hyphens exist, permitting unmasked Microsoft keys or unbroken 16+ char hex/token keys; furthermore, `SoftwareLicense.clean()` omits `validate_masked_key_ref`, leaving `SoftwareLicenseAdmin` unprotected.
  - **Fix**: Require explicit masking (`"*" in raw or "xxxx" in raw.lower()`) and reject unmasked multi-segment or 16+ char alphanumeric/hex/token keys (`_`/`+`/`/`/`=`, `AKIA`/`sk_`/`ghp_`), and invoke `validate_masked_key_ref` inside `SoftwareLicense.clean()`.

- [x] **M3** (`security-reviewer`) — fixed in `1b20a188`, `ba531518`, `58aaea35`, `f1c14fb2`: Passed structured JSON-serializable before/after `changes` dicts to `write_audit_log` on IT Hardware, Software License, Cloud Subscription, and CMDB lifecycle/compliance/sanitization actions.
  - **Problem**: `write_audit_log` calls pass `changes=None` by default, omitting before/after status, entitlement/seat deltas (`true_up`, `reclaim`), and sanitization verification details.
  - **Fix**: Pass structured `changes={...}` dicts (`{"from_status": ..., "to_status": ...}`, seat/entitlement deltas) to `write_audit_log` on lifecycle, compliance, and sanitization actions.

- [x] **M4** (`security-reviewer`) — fixed in `32cb8658`, `56757d1a`: Added `MinValueValidator(Decimal("0.00"))` to `CloudAssetSubscription.monthly_recurring_cost` and `annual_contract_value`, folded into migration `0025`.
  - **Problem**: Unlike `ItHardwareAsset.estimated_refresh_cost` and `SoftwareLicense.unit_license_cost`/`total_annual_spend`, `monthly_recurring_cost` and `annual_contract_value` omit `validators=[MinValueValidator(Decimal("0.00"))]`.
  - **Fix**: Add `validators=[MinValueValidator(Decimal("0.00"))]` to `monthly_recurring_cost` and `annual_contract_value` (fold into the incremental migration from `I12`).

- [x] **M5** (`explorer`) — fixed in `f3d648b2`: Cleared `mdm_platform=""` when `mdm_enrolled=False` in `seed_assets.py` and re-seeded 11.18 demo rows.
  - **Problem**: Sets literal `"none"` when `mdm_enrolled=False`, displaying `"none"` instead of `"—"` in detail view.
  - **Fix**: Set `mdm_platform=""` when unenrolled.

- [x] **M6** (`frontend-reviewer`) — fixed in `c2b6ab0c`, `65b531d5`, `d3e51960`, `e5620118`, `af98c982`, `742e4b71`, `7fd68805`, `dd8c9eb9`, `61f75f7e`: Added `dark:text-indigo-400`, `dark:text-red-400`, `dark:text-amber-400`, and `dark:text-slate-400` variants across all 9 ITAM templates.
  - **Problem**: `text-indigo-600`, `text-red-600`, `text-amber-600`, and `text-slate-500` lack `dark:` variants.
  - **Fix**: Add `dark:text-indigo-400`, `dark:text-red-400`, `dark:text-amber-400`, `dark:text-slate-400`.

- [x] **M7** (`frontend-reviewer`) — fixed in `23d5311f`, `083f35e7`, `8cb5af52`: Aligned `<th class="th-actions">`, `text-end`, `.btn-icon.danger`, and `<span class="muted">` pagination classes with `static/css/theme.css` across `it_hardware_asset/list.html`, `software_license/list.html`, and `it_refresh_board.html`.
  - **Problem**: Uses `text-right` instead of `th-actions`/`text-end`, omits `<span class="muted">` in `.pagination`, and omits `.danger` on delete `.btn-icon`.
  - **Fix**: Update classes to match `static/css/theme.css`.

- [x] **M8** (`frontend-reviewer`, `security-reviewer`) — fixed in `f3eaf3fc`, `478b1f28`: Applied `|escapejs` to `id_for_label` JS strings in `cmdb_relationship/form.html` and rendered `cloud_asset.resource_tags.items` as `.badge.badge-slate` pills in `cloud_asset_subscription/detail.html`.
  - **Problem**: Form JS interpolates `id_for_label` without `|escapejs`; `cloud_asset_subscription/detail.html` renders `resource_tags` as raw Python dict string.
  - **Fix**: Apply `|escapejs` on `id_for_label` JS strings and render `resource_tags.items` as `.badge.badge-slate` pills.

- [x] **M9** (`performance-reviewer`) — fixed in `5b6329a5`, `8e9cdf6d`, `455c4f49`, `e31830af`, `abf99dbe`: Split `CMDB_REL_EDGE_SELECT_RELATED` (10 CI FKs) from `CMDB_REL_DETAIL_SELECT_RELATED` and trimmed unrendered FKs from list `select_related` tuples across all four ITAM list/detail views.
  - **Problem**: List tuples include unrendered FKs and edge subtables join unused `"owner"`/`"verified_by"`.
  - **Fix**: Trim list `select_related` to rendered FKs and split `CMDB_REL_EDGE_SELECT_RELATED` (10 CI FKs) from `CMDB_REL_DETAIL_SELECT_RELATED`.

- [x] **M10** (`performance-reviewer`) — fixed in `3ef5b33a`, `9148950f`: Passed `select_related=("sanitization_verified_by",)` in `it_hardware_asset_edit` and `select_related=("verified_by",)` in `cmdb_relationship_edit`.
  - **Problem**: Edit views fetch instance without `select_related("sanitization_verified_by")` / `select_related("verified_by")` before `validate_tenant_fks`.
  - **Fix**: Pass `select_related` to `assets_object` in those two edit views.

- [x] **M11** (`performance-reviewer`) — fixed in `42415846`, `cf7f3011`, `477ed008`, `56711154`, `fec95be5`: Capped detail CMDB edge panels to `[:50]` across all four ITAM detail views and evaluated each CI queryset once to share widget choices across `source_*`/`target_*` pairs in `CmdbRelationshipForm` (reducing form render SQL queries from 11 to 6).
  - **Problem**: Detail CMDB panels have no slice cap on hub nodes; `CmdbRelationshipForm` executes duplicate querysets for `source_*` vs `target_*`.
  - **Fix**: Slice detail CMDB subtables (e.g. `[:50]`) and evaluate/reuse shared per-CI querysets cleanly where helpful.

- [x] **M12** (`performance-reviewer`) — fixed in `5b0d9357`: Consolidated `OrgUnit` first/last lookup into one ordered query in `seed_assets.py` (`ItHardwareAsset.refresh_priority` executes zero DB queries and intentionally avoids instance-level caching so in-memory date/status mutations cannot go stale).
  - **Problem**: `refresh_priority` recomputes `timezone.now().date()` across badge/label calls per row; seeder runs 2 queries for first/last `OrgUnit`.
  - **Fix**: Optional micro-cleanup (safe to defer or clean in-place if trivial).
