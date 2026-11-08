# Review Findings: Sub-module 11.2 Asset Inventory & Tracking

**Target Sub-module:** 11.2 Asset Inventory & Tracking  
**Changeset Range:** `7116d705d2bc8f2086cc06cc4843028d4fd11cce...HEAD`  
**Review Pass:** Six Reviewers Completed (`code-reviewer`, `explorer`, `frontend-reviewer`, `performance-reviewer`, `qa-smoke-tester`, `security-reviewer`)  
**Status:** Deduplicated, sorted, and prioritized for Phase 5 (`code-fixer`).

---

## Critical

- [ ] **C1** — `apps/assets/views/AssetInventoryTracking/AssetCustodyLogs.py:164-173` & `templates/assets/asset_inventory_tracking/asset_custody_log/detail.html:53-60`, `list.html:180-187`: Missing view-level status and authorization guard on `asset_custody_log_delete`. View allows deleting active/overdue/lost logs via direct POST. Restrict deletion in view to `status in ("returned", "cancelled")` (or require `@tenant_admin_required`), and update template conditions so active loans cannot be deleted.
- [ ] **C2** — `templates/assets/asset_inventory_tracking/asset_incident_report/detail.html:44`: Incorrect RBAC check `request.user.role == 'admin'` locks out tenant administrators from authorizing write-offs (`user.role` is a ForeignKey to `accounts.Role`); replace with `request.user.is_superuser or request.user.is_tenant_admin`.
- [ ] **C3** — `templates/assets/asset_inventory_tracking/asset_incident_report/detail.html:178`: Lesson L10 recurrence: Unguarded `default:incident.write_off_authorized_by.username` inside `{% if incident.write_off_authorized_by or incident.write_off_notes %}` causes a 500 when authorizer is None. Add explicit `{% if incident.write_off_authorized_by %}` guard.

---

## Important

- [ ] **I1** — `apps/assets/models/AssetInventoryTracking/AssetIncidentReports.py:40-48` & `templates/assets/asset_inventory_tracking/asset_incident_report/list.html:158` & `detail.html:17`: Missing `@property status_css` on `AssetIncidentReport` (and add uniform property getter across all 11.2 models) causing unstyled badge classes in templates.
- [ ] **I2** — `apps/assets/management/commands/seed_assets.py:293, 309, 324, 334, 354, 402, 411, 421`: Invalid choice values in `seed_assets` violating model `CHOICES` constants (`"physical_wall_to_wall"` -> `"wall_to_wall"`, `"cycle_count_high_value"` -> `"cycle_count"`, `"investigate"` -> `"incident_initiated"`, `"periodic"` -> `"spot_check"`, `"inter_facility"` -> `"inter_facility_transfer"`, `"tool_crib_checkout"` / `"field_dispatch"` -> `"checkout"`, `"calibrated"` -> `"excellent"`).
- [ ] **I3** — `apps/assets/forms/AssetInventoryTracking/AssetIncidentReports.py:39-40` & `templates/assets/asset_inventory_tracking/asset_incident_report/form.html:117-119, 208-210`: Privilege bypass & workflow mass assignment: `resolution_action` and `write_off_notes` exposed in `AssetIncidentReportForm` create/edit forms. Authorizing write-off and resolution are handled in dedicated workflow views. Exclude both from `Meta.fields` and remove from form template.
- [ ] **I4** — `apps/assets/forms/AssetInventoryTracking/AssetAudits.py:31` & `templates/assets/asset_inventory_tracking/asset_audit/form.html:143-145`: Premature administrative field exposure: `reconciliation_action` exposed in `AssetAuditForm` create/edit. Audit variance reconciliation is a supervisor workflow step handled via `asset_audit_reconcile`. Exclude from `AssetAuditForm` and remove from form template.
- [ ] **I5** — `apps/assets/views/AssetInventoryTracking/AssetMovementLogs.py:144`: Transit tracking integrity: `asset_movement_log_edit` only guards against editing in `("received", "cancelled")`. In-transit transfers remain editable, which allows altering `asset` or destination mid-transit before receipt updates the asset's location. Restrict edit to `("draft", "requested")`.
- [ ] **I6** — `templates/assets/asset_inventory_tracking/asset_audit/detail.html:55-59`: Un-gated administrative button: "Reconcile Discrepancies" modal button is displayed to non-admins but target view `asset_audit_reconcile` requires `@tenant_admin_required`, leading to 403 PermissionDenied. Guard button with `{% if request.user.is_superuser or request.user.is_tenant_admin %}`.
- [ ] **I7** — `templates/assets/asset_inventory_tracking/asset_incident_report/list.html:179-188`: CRUD completeness: Missing POST delete form in table actions column for deletable statuses (`reported`, `closed`).
- [ ] **I8** — Filter dropdown & pagination parameter omissions across list templates:
  - `templates/assets/asset_inventory_tracking/asset_audit/list.html:66-102`: `org_unit` filter dropdown omitted from template filter `<form>`.
  - `templates/assets/asset_inventory_tracking/asset_movement_log/list.html:59-102, 215, 227`: `asset` filter dropdown omitted from filter `<form>` and `&asset={{ request.GET.asset }}` dropped from pagination links.
  - `templates/assets/asset_inventory_tracking/asset_custody_log/list.html:59-102, 216, 228`: `asset` filter dropdown omitted from filter `<form>` and `&asset={{ request.GET.asset }}` dropped from pagination links.
  - `templates/assets/asset_inventory_tracking/asset_incident_report/list.html:66-109, 216, 222`: `location` and `asset` filter dropdowns omitted from filter `<form>` and `&location=` and `&asset=` dropped from pagination links.
- [ ] **I9** — `apps/assets/views/AssetInventoryTracking/AssetCustodyLogs.py:54-58`: Performance: Unconditional database UPDATE query on HTTP GET list view marking overdue loans without checking `.exists()`. Guard with `overdue_qs.exists()` before calling `.update()`.

---

## Minor

- [ ] **M1** — `apps/assets/forms/AssetInventoryTracking/AssetMovementLogs.py:29` & `templates/assets/asset_inventory_tracking/asset_movement_log/form.html:156-158`: `condition_on_receipt` exposed in `AssetMovementLogForm` create/edit before physical receipt occurs; exclude from form and capture in `asset_movement_log_receive`.
- [ ] **M2** — Multi-tenant defense-in-depth: Include user ForeignKeys in `reject_foreign(self, cleaned_data, [...])` in `AssetAudits.py` (`lead_auditor`, `supervisor`), `AssetCustodyLogs.py` (`crib_attendant`), and `AssetIncidentReports.py` (`investigator`).
- [ ] **M3** — `apps/assets/views/AssetInventoryTracking/AssetCustodyLogs.py:126-127`, `AssetIncidentReports.py:125-126`, `AssetMovementLogs.py:130-131`: Validate `asset_id` against `request.tenant` before populating `initial["asset"]` in GET create views.
- [ ] **M4** — `apps/assets/views/overview.py:7-62` & `templates/assets/overview.html:15-110`: Overview dashboard lacks 11.2 metric aggregates & quick links for active audits, movements, custody loans, and incidents.
- [ ] **M5** — `templates/assets/asset_inventory_tracking/asset_incident_report/list.html:115, 134, 193-201, 210-227`: Design system CSS alignment: replace `.table-responsive` with `.table-wrap`, `.text-primary` with `.text-brand`, and align empty state and pagination markup with `.empty-state` and `.pagination`.
- [ ] **M6** — Modal close buttons accessibility: add `aria-label="Close"` in `asset_audit/detail.html:253`, `asset_movement_log/detail.html:248`, `asset_custody_log/detail.html:220, 262`, `asset_incident_report/detail.html:295, 323`.
- [ ] **M7** — `apps/assets/views/AssetInventoryTracking/AssetCustodyLogs.py:177, 214`, `AssetMovementLogs.py:185, 197, 204, 228`, `AssetIncidentReports.py:199, 213`: Add `select_related("asset")` (and `"to_location"`) on single-object action retrieval before accessing related attributes in `messages.success()`.
- [ ] **M8** — `templates/assets/asset_inventory_tracking/asset_audit/list.html:189, 194`: Fragile substring containment tests `status not in 'completed reconciled cancelled'`; replace with explicit condition comparisons.
