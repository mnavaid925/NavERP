# Module 11.18 IT Asset Management (ITAM) — Consolidated Review Findings Register

> **Scope**: Module 11.18 IT Asset Management (`apps/assets/{models,forms,views,urls}/ItAssetManagement/`, `templates/assets/itassetmanagement/`, and 11.18 sections of `admin.py`, `seed_assets.py`, `navigation.py`, `0024`). Sibling 11.17 `SpaceFacilityAsset` files excluded per L53.
> **Reviewers Executed (Serial 6/6)**: `code-reviewer` -> `explorer` -> `frontend-reviewer` -> `performance-reviewer` -> `qa-smoke-tester` (report-only) -> `security-reviewer`.
> **Legend**: `- [ ]` Open · `- [x] fixed — <commit/reason>` · `- [~] skipped — <reason>`

---

## Critical (`C1`–`C4`)

- [ ] **C1** (`code-reviewer`, `explorer`, `qa-smoke-tester`): **Invalid & overlength choice keys in `seed_assets.py` + existing DB rows** — `apps/assets/management/commands/seed_assets.py:5272-5559`
  - **Problem**: Seeded `ItHardwareAsset` rows (`server_physical`, `tier_1_mission_critical`, `server_virtual`, `network_switch_router`, `exempt_network_gear`, `workstation`, `tier_3_operational`, `filevault_enabled`, `storage_san_nas`, `disaster_recovery`, `tier_2_business_important`, `nist_purge_cryptographic_erase`) and 3 of 4 `SoftwareLicense` rows (`database_data`, `enterprise_agreement`, `developer_devops`, `named_user`, `cad_engineering`, `concurrent_floating`) use non-existent choice keys (truncating `criticality` and `sanitization_method` in MariaDB, failing `.full_clean()`, breaking dropdown filters, and rendering raw keys in HTML).
  - **Fix**: Replace with exact model `*_CHOICES` keys (`physical_server`, `critical`, `virtual_host`, `router_firewall`, `exempt`, `corporate_enduser`, `medium`, `bitlocker_filevault`, `storage_array`, `dr_standby`, `high`, `crypto_erase`; `database_engine`/`enterprise_ela`, `devops_ide`/`subscription_term`, `design_cad`/`perpetual`), and run a cleanup/re-seed for 11.18 demo rows in DB (without wiping other modules or 11.17).

- [ ] **C2** (`code-reviewer`, `qa-smoke-tester`, `security-reviewer`): **Non-admin AuthZ bypass of `audit_hold` & unrestricted edits while on hold (`SoftwareLicense`)** — `apps/assets/views/ItAssetManagement/SoftwareLicenses.py:225-256,280-297,302-328,365-392` & `templates/assets/itassetmanagement/software_license/detail.html:31-75`
  - **Problem**: Non-admin authenticated users POSTing to `software_license_sync_compliance` (`:287-288`) reset `"audit_hold"` imposed by `@tenant_admin_required` (`software_license_place_audit_hold` at `:395`), unilaterally lifting an audit hold. Additionally, `software_license_edit`, `software_license_reclaim_inactive`, and `software_license_renew_term` only check `is_locked` (`retired`), letting non-admins alter entitlements, allocations, and renewal dates during an active vendor audit hold, and detail UI shows hold-clearing/mutating actions to non-admins.
  - **Fix**: Preserve `audit_hold` in `software_license_sync_compliance` (do not allow non-admins to clear it), reject non-admin mutations (`edit`, `sync_compliance`, `reclaim_inactive`, `renew_term`) when `license_obj.status == "audit_hold"` (allowing tenant admins if they are lifting/managing the hold or keeping hold-management admin-only), and hide/gate those action controls in `software_license/detail.html` for non-admins when `license_obj.status == "audit_hold"`.

- [ ] **C3** (`code-reviewer`, `qa-smoke-tester`, `security-reviewer`): **Non-admin AuthZ bypass of `suspended` & unrestricted edits while suspended (`CloudAssetSubscription`)** — `apps/assets/views/ItAssetManagement/CloudAssetSubscriptions.py:251-282,306-331,336-348,373-400` & `templates/assets/itassetmanagement/cloud_asset_subscription/detail.html:30-72`
  - **Problem**: Non-admin authenticated users POSTing to `cloud_asset_subscription_sanction` (`:316-317`), `cloud_asset_subscription_renew` (`:383-384`), or `cloud_asset_subscription_flag_shadow` (`:344`) overwrite an admin-placed `status="suspended"` back to `"active"` or `"shadow_flagged"`, bypassing `@tenant_admin_required` on `cloud_asset_subscription_suspend`. Also `cloud_asset_subscription_edit` and `sync_finops` allow non-admin edits while suspended, and detail UI lacks admin-gate symmetry.
  - **Fix**: Remove the `if cloud_asset.status == "suspended":` reset branches from `sanction` and `renew`, guard `edit`, `sanction`, `flag_shadow`, `sync_finops`, and `renew` against `cloud_asset.status == "suspended"` unless `is_tenant_admin_user(request.user)`, and hide those controls for non-admins in `cloud_asset_subscription/detail.html` when `cloud_asset.status == "suspended"`.

- [ ] **C4** (`security-reviewer`): **Non-admin tampering with NIST SP 800-88 sanitization compliance (`ItHardwareAsset`)** — `apps/assets/forms/ItAssetManagement/ItHardwareAssets.py:81-85`, `apps/assets/views/ItAssetManagement/ItHardwareAssets.py:199-214,259-289`, `templates/assets/itassetmanagement/it_hardware_asset/form.html:201-225`
  - **Problem**: `ItHardwareAssetForm` exposes `sanitization_required`, `sanitization_method`, `sanitization_status`, `sanitization_date`, and `sanitization_certificate_ref` in `@login_required` create/edit views, allowing non-admins to disable `sanitization_required` or self-assert `wiped_verified`/`certificate_on_file` (bypassing `@tenant_admin_required` on `it_hardware_asset_mark_sanitized` and leaving `sanitization_verified_by`/`sanitized_at` unset or stale).
  - **Fix**: Restrict non-admins in `ItHardwareAssetForm` / `create` / `edit` so they cannot set `sanitization_status` to `wiped_verified`/`certificate_on_file` or tamper with sanitization compliance fields once verified (or gate sanitization-attestation fields to tenant admins / `mark_sanitized`), clear `sanitization_verified_by`/`sanitized_at` if status is reset by an admin, and update `it_hardware_asset/form.html` cleanly to match.

---

## Important (`I1`–`I12`)

- [ ] **I1** (`code-reviewer`, `qa-smoke-tester`, `security-reviewer`): **`it_hardware_asset_mark_sanitized` mutates `sanitized_retired` locked records** — `apps/assets/views/ItAssetManagement/ItHardwareAssets.py:375`
  - **Problem**: Line `375` only checks `if hardware.status == "disposed":` instead of `if hardware.is_locked:`, permitting sanitization mutations after lock in `"sanitized_retired"`.
  - **Fix**: Replace `if hardware.status == "disposed":` with `if hardware.is_locked:`.

- [ ] **I2** (`code-reviewer`, `security-reviewer`): **`cmdb_relationship_verify` bypasses duplicate active edge `full_clean()`** — `apps/assets/views/ItAssetManagement/CmdbRelationships.py:299-315`
  - **Problem**: Transitions `"planned"` or `"deprecated"` edges to `"active"` via `save(update_fields=...)` without calling `relationship.full_clean()`, bypassing duplicate active edge validation in `CmdbRelationship.clean()`.
  - **Fix**: Call `relationship.full_clean()` inside `transaction.atomic()` before `relationship.save(...)` and catch `ValidationError` -> `messages.error` + redirect to detail.

- [ ] **I3** (`main-inspection`): **Superuser (`request.tenant is None`) & `create` `Model.clean()` tenant-binding gap** — `apps/assets/views/ItAssetManagement/{ItHardwareAssets,SoftwareLicenses,CloudAssetSubscriptions,CmdbRelationships}.py` (`*_create`)
  - **Problem**: If `request.tenant is None` (Django superuser `admin`), submitting any create form assigns `obj.tenant = None` -> `IntegrityError` 500; also during `form.is_valid()` on create, `self.instance.tenant_id` is still `None` when `Model.clean()` runs `validate_tenant_fks`.
  - **Fix**: Guard `if request.tenant is None: messages.warning(...); return redirect(...)` on POST in all 4 create views, and assign `form.instance.tenant = request.tenant` before `form.is_valid()` (or bind `instance.tenant` when `form` constructs if unset) so `Model.clean()` always sees `tenant_id`.

- [ ] **I4** (`code-reviewer`, `frontend-reviewer`): **Non-existent `stat-icon amber` class on KPI cards** — `templates/assets/itassetmanagement/software_license/detail.html:104`, `cloud_asset_subscription/detail.html:129`
  - **Problem**: Uses `stat-icon amber`, which does not exist in `static/css/theme.css:260-265` (only `green`, `orange`, `purple`, `blue`, `slate`, `red` exist).
  - **Fix**: Change `amber` to `orange` in both templates.

- [ ] **I5** (`code-reviewer`, `frontend-reviewer`): **Undefined `.card-footer` class on Cloud & CMDB pagination** — `templates/assets/itassetmanagement/cloud_asset_subscription/list.html:199-211`, `cmdb_relationship/list.html:191-203`
  - **Problem**: Uses `<div class="card-footer ...">` instead of `<div class="pagination">` with `<span class="muted">Showing ...</span>` matching `it_hardware_asset/list.html:233-248`.
  - **Fix**: Switch both footers to `.pagination` + `<span class="muted">`.

- [ ] **I6** (`frontend-reviewer`): **Incomplete Actions column in Cloud & CMDB list tables** — `templates/assets/itassetmanagement/cloud_asset_subscription/list.html:146,187-189`, `cmdb_relationship/list.html:150,179-181`
  - **Problem**: Actions column renders only `View` with empty `<th></th>`, missing `<th class="th-actions">Actions</th>`, `Edit` (`{% if not obj.is_locked %}`), and admin-gated POST `Delete` with `{% csrf_token %}` and `|escapejs` confirm.
  - **Fix**: Add View, Edit (`not is_locked`), and admin/lock-gated POST Delete icon buttons matching `it_hardware_asset/list.html` / `software_license/list.html`.

- [ ] **I7** (`frontend-reviewer`): **Missing `.empty-state` component on Cloud & CMDB empty tables** — `templates/assets/itassetmanagement/cloud_asset_subscription/list.html:192-194`, `cmdb_relationship/list.html:184-186`
  - **Problem**: Empty table row renders bare text instead of `.empty-state` (`static/css/theme.css:324-326`) with icon, heading, description, and create button.
  - **Fix**: Wrap with `<div class="empty-state">` + create CTA matching `it_hardware_asset/list.html:218-225`.

- [ ] **I8** (`performance-reviewer`): **N+1 query on `ItHardwareAssetForm` `scrap_salvage` dropdown (+ detail)** — `apps/assets/forms/ItAssetManagement/_helpers.py:15-20`, `apps/assets/views/ItAssetManagement/ItHardwareAssets.py:36-49`
  - **Problem**: `AssetScrapSalvage.__str__` accesses `self.fixed_asset.name`; `scope_tenant_querysets()` and `_HW_DETAIL_SELECT_RELATED` omit `select_related("fixed_asset")` / `"scrap_salvage__fixed_asset"`.
  - **Fix**: Add `elif model_cls.__name__ == "AssetScrapSalvage": qs = qs.select_related("fixed_asset")` and include `"scrap_salvage__fixed_asset"` in `_HW_DETAIL_SELECT_RELATED`.

- [ ] **I9** (`performance-reviewer`): **Unbounded Python scan, unbounded lists, and 5 unused JOINs in `ItRefreshBoards`** — `apps/assets/views/ItAssetManagement/ItRefreshBoards.py:39-138`
  - **Problem**: Loops all non-locked `ItHardwareAsset` rows in Python for KPIs and `org_unit_summary`, materializes unbounded `software_rows`/`cloud_rows`, and joins 5 unused FKs (`owner`, `currency`, `license_owner`, `business_owner`).
  - **Fix**: Compute `overdue_hw_count`, `due_90d_hw_count`, `pending_wipe_count`, and `org_unit_summary` via SQL `.aggregate()` / `.values("org_unit__name").annotate(...)`, push horizon/priority filters to SQL `Q(...)`, cap rendered lists (`[:200]`), and trim `select_related`.

- [ ] **I10** (`performance-reviewer`): **Full-row hydration in `build_ci_label_map` + redundant 12-JOIN in `CmdbImpactAnalyses`** — `apps/assets/views/ItAssetManagement/_helpers.py:83-124`, `apps/assets/views/ItAssetManagement/CmdbImpactAnalyses.py:21-33,65`
  - **Problem**: `build_ci_label_map()` executes 5 unbounded `SELECT *` queries hydrating full ORM instances; `_build_impact_context()` joins 12 unused tables on `edges_qs` despite `label_map` caching every CI label.
  - **Fix**: Use bounded `.values_list(...)` in `build_ci_label_map()`, drop `select_related(*CMDB_REL_SELECT_RELATED)` in `CmdbImpactAnalyses`, and resolve `spof_edges` labels via `label_map`.

- [ ] **I11** (`performance-reviewer`): **CSV exports materialize full querysets and join unused list FKs** — `ItHardwareAssets.py:154-195`, `SoftwareLicenses.py:116-157`, `CloudAssetSubscriptions.py:138-183`, `CmdbRelationships.py:136-175`, `ItRefreshBoards.py:153-210`
  - **Problem**: Export views iterate unbounded `qs` before `islice(..., 10000)` and reuse heavyweight list `select_related` JOINs not exported to CSV.
  - **Fix**: Parameterize `select_related` on `_filter_*_queryset(..., select_related=...)` and stream `qs[:10000].iterator(chunk_size=1000)`.

- [ ] **I12** (`performance-reviewer`): **Missing composite indexes on `Meta.ordering` & hot filter columns** — `ItHardwareAssets.py:326,334-339`, `SoftwareLicenses.py:195,203-208`, `CloudAssetSubscriptions.py:245,254-259`, `CmdbRelationships.py:238,247-252`
  - **Problem**: Default `Meta.ordering` pairs (`(tenant, hostname)`, `(tenant, software_name)`, `(tenant, name)`, `(tenant, -updated_at)`) and high-frequency list filter columns lack composite indexes.
  - **Fix**: Add composite `Meta.indexes` (all `<= 30` chars) and generate a clean incremental migration (verify `--dry-run` against clean 11.17 state first per L51/L53).

---

## Minor (`M1`–`M12`)

- [ ] **M1** (`code-reviewer`, `explorer`, `security-reviewer`): **Uniform `validate_tenant_fks` error accumulation** — `apps/assets/models/ItAssetManagement/_validators.py:25-37`, `ItHardwareAssets.py:407`, `SoftwareLicenses.py:277`, `CloudAssetSubscriptions.py:266`, `CmdbRelationships.py:281`
  - **Problem**: `validate_tenant_fks` raises immediately instead of returning the accumulated `errors` dict, short-circuiting subsequent field checks in `clean()`, and models invoke it inconsistently.
  - **Fix**: Always return `errors` dict (never raise inside `validate_tenant_fks`) and accumulate `errors = validate_tenant_fks(...)` uniformly in all 4 models before raising `ValidationError(errors)` once.

- [ ] **M2** (`code-reviewer`, `security-reviewer`): **Tighten `validate_masked_key_ref` heuristic & invoke in `SoftwareLicense.clean()`** — `apps/assets/forms/ItAssetManagement/_helpers.py:32-41`, `apps/assets/models/ItAssetManagement/SoftwareLicenses.py:275-298`
  - **Problem**: `validate_masked_key_ref` skips validation if `"x"` appears anywhere or no hyphens exist, permitting unmasked Microsoft keys or unbroken 16+ char hex/token keys; furthermore, `SoftwareLicense.clean()` omits `validate_masked_key_ref`, leaving `SoftwareLicenseAdmin` unprotected.
  - **Fix**: Require explicit masking (`"*" in raw or "xxxx" in raw.lower()`) and reject unmasked multi-segment or 16+ char alphanumeric/hex/token keys (`_`/`+`/`/`/`=`, `AKIA`/`sk_`/`ghp_`), and invoke `validate_masked_key_ref` inside `SoftwareLicense.clean()`.

- [ ] **M3** (`security-reviewer`): **Audit log entries omit `changes` payload on sensitive transitions** — `ItHardwareAssets.py:330,398,431`, `SoftwareLicenses.py:292,326,355,387,406,423`, `CloudAssetSubscriptions.py:329,346,363,395,414,439`, `CmdbRelationships.py:313,329,346`
  - **Problem**: `write_audit_log` calls pass `changes=None` by default, omitting before/after status, entitlement/seat deltas (`true_up`, `reclaim`), and sanitization verification details.
  - **Fix**: Pass structured `changes={...}` dicts (`{"from_status": ..., "to_status": ...}`, seat/entitlement deltas) to `write_audit_log` on lifecycle, compliance, and sanitization actions.

- [ ] **M4** (`security-reviewer`): **Missing model-level `MinValueValidator` on `CloudAssetSubscription` cost fields** — `apps/assets/models/ItAssetManagement/CloudAssetSubscriptions.py:162-171`
  - **Problem**: Unlike `ItHardwareAsset.estimated_refresh_cost` and `SoftwareLicense.unit_license_cost`/`total_annual_spend`, `monthly_recurring_cost` and `annual_contract_value` omit `validators=[MinValueValidator(Decimal("0.00"))]`.
  - **Fix**: Add `validators=[MinValueValidator(Decimal("0.00"))]` to `monthly_recurring_cost` and `annual_contract_value` (fold into the incremental migration from `I12`).

- [ ] **M5** (`explorer`): **Seeder `mdm_platform="none"` when unenrolled** — `apps/assets/management/commands/seed_assets.py:5289,5327`
  - **Problem**: Sets literal `"none"` when `mdm_enrolled=False`, displaying `"none"` instead of `"—"` in detail view.
  - **Fix**: Set `mdm_platform=""` when unenrolled.

- [ ] **M6** (`frontend-reviewer`): **Dark-mode contrast variants on utility classes** — `cloud_asset_subscription/list.html:153,168`, `cmdb_relationship/list.html:157`, `software_license/list.html:179`, `software_license/detail.html:109,198,221`, `it_hardware_asset/detail.html:201,224`, `cloud_asset_subscription/detail.html:195,218`, `cmdb_relationship/detail.html:130,151`, `it_refresh_board.html:120,173,198,219`, `cmdb_impact_analysis.html:106,110,130,134,154`
  - **Problem**: `text-indigo-600`, `text-red-600`, `text-amber-600`, and `text-slate-500` lack `dark:` variants.
  - **Fix**: Add `dark:text-indigo-400`, `dark:text-red-400`, `dark:text-amber-400`, `dark:text-slate-400`.

- [ ] **M7** (`frontend-reviewer`): **RTL & Theme alignment polish (`th-actions`, `text-end`, `muted`, `danger`)** — `it_hardware_asset/list.html:151,207,235`, `software_license/list.html:141,196,224`, `it_refresh_board.html:178`
  - **Problem**: Uses `text-right` instead of `th-actions`/`text-end`, omits `<span class="muted">` in `.pagination`, and omits `.danger` on delete `.btn-icon`.
  - **Fix**: Update classes to match `static/css/theme.css`.

- [ ] **M8** (`frontend-reviewer`, `security-reviewer`): **JS `|escapejs` & Resource Tags Pills polish** — `templates/assets/itassetmanagement/cmdb_relationship/form.html:179-180`, `cloud_asset_subscription/detail.html:156`
  - **Problem**: Form JS interpolates `id_for_label` without `|escapejs`; `cloud_asset_subscription/detail.html` renders `resource_tags` as raw Python dict string.
  - **Fix**: Apply `|escapejs` on `id_for_label` JS strings and render `resource_tags.items` as `.badge.badge-slate` pills.

- [ ] **M9** (`performance-reviewer`): **Trim unused `select_related` JOINs in list & detail edge panels** — `ItHardwareAssets.py:29-35`, `SoftwareLicenses.py:28-33`, `CloudAssetSubscriptions.py:35-41`, `_helpers.py:11-24`
  - **Problem**: List tuples include unrendered FKs and edge subtables join unused `"owner"`/`"verified_by"`.
  - **Fix**: Trim list `select_related` to rendered FKs and split `CMDB_REL_EDGE_SELECT_RELATED` (10 CI FKs) from `CMDB_REL_DETAIL_SELECT_RELATED`.

- [ ] **M10** (`performance-reviewer`): **Avoid lazy `User` query on edit POST** — `ItHardwareAssets.py:261`, `CmdbRelationships.py:247`
  - **Problem**: Edit views fetch instance without `select_related("sanitization_verified_by")` / `select_related("verified_by")` before `validate_tenant_fks`.
  - **Fix**: Pass `select_related` to `assets_object` in those two edit views.

- [ ] **M11** (`performance-reviewer`): **Unsliced detail CMDB edge panels & duplicated form queries** — `ItHardwareAssets.py:237-246`, `SoftwareLicenses.py:201-210`, `CloudAssetSubscriptions.py:227-236`, `CmdbRelationships.py:219-232`, `forms/ItAssetManagement/CmdbRelationships.py:69-71`
  - **Problem**: Detail CMDB panels have no slice cap on hub nodes; `CmdbRelationshipForm` executes duplicate querysets for `source_*` vs `target_*`.
  - **Fix**: Slice detail CMDB subtables (e.g. `[:50]`) and evaluate/reuse shared per-CI querysets cleanly where helpful.

- [ ] **M12** (`performance-reviewer`): **Minor `refresh_priority` & seeder OrgUnit lookup polish** — `ItHardwareAssets.py:373-403`, `seed_assets.py:5248-5249`
  - **Problem**: `refresh_priority` recomputes `timezone.now().date()` across badge/label calls per row; seeder runs 2 queries for first/last `OrgUnit`.
  - **Fix**: Optional micro-cleanup (safe to defer or clean in-place if trivial).
