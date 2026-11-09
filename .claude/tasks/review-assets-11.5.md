# Master Review Findings: Module 11.5 — Maintenance & Repair Management

**Review Range**: `bb6c9161324de1933874a26e1b589f617902f533...HEAD`
**Module**: Asset Management System (`apps/assets`)
**Sub-module**: 11.5 Maintenance & Repair Management
**Entities**:
1. `AssetMaintenanceRequest` [AMRQ-]
2. `AssetMaintenanceSchedule` [AMSC-]
3. `AssetServiceContract` [ASVC-]
4. `AssetMaintenanceLog` [AMLG-]

---

## Consolidated Action Plan (ID-Ordered)

### Critical Findings
- [ ] **[C1] Multi-tenant Queryset Leakage in All Four Create ModelForms**
  - **Files**:
    - `apps/assets/forms/AssetMaintenance/AssetMaintenanceRequests.py`
    - `apps/assets/forms/AssetMaintenance/AssetMaintenanceSchedules.py`
    - `apps/assets/forms/AssetMaintenance/AssetServiceContracts.py`
    - `apps/assets/forms/AssetMaintenance/AssetMaintenanceLogs.py`
    - `apps/assets/views/AssetMaintenance/AssetMaintenanceRequests.py`
    - `apps/assets/views/AssetMaintenance/AssetMaintenanceSchedules.py`
    - `apps/assets/views/AssetMaintenance/AssetServiceContracts.py`
    - `apps/assets/views/AssetMaintenance/AssetMaintenanceLogs.py`
  - **Problem**: Forms inspect `self.tenant` in `__init__`, but neither accept `tenant` as a keyword argument in `__init__` nor pop it before `super().__init__()`. In create views, `form.tenant = request.tenant` was set after instantiation. On creation, `self.instance.tenant` is `None`, exposing all tenants' records in foreign key select fields.
  - **Fix**: Update `__init__(self, *args, **kwargs)` in all 4 forms to `self.tenant = kwargs.pop("tenant", None)` before `super().__init__(*args, **kwargs)`, filter all FK querysets by `self.tenant`, and pass `tenant=request.tenant` into form instantiation in all create views (GET and POST).

- [ ] **[C2] Missing Tenant Cross-Validation for User Foreign Keys in Form clean()**
  - **Files**:
    - `apps/assets/forms/AssetMaintenance/AssetMaintenanceRequests.py`
    - `apps/assets/forms/AssetMaintenance/AssetMaintenanceSchedules.py`
    - `apps/assets/forms/AssetMaintenance/AssetMaintenanceLogs.py`
  - **Problem**: `reject_foreign()` omits User foreign keys (`requester`, `assigned_technician`, `lead_technician`).
  - **Fix**: Validate that User foreign keys belong to `self.tenant` (or check `user_obj.tenant_id == self.tenant.pk`).

- [ ] **[C3] Canonical db_table Omitted on All Four 11.5 Models**
  - **Files**:
    - `apps/assets/models/AssetMaintenance/AssetMaintenanceRequests.py`
    - `apps/assets/models/AssetMaintenance/AssetMaintenanceSchedules.py`
    - `apps/assets/models/AssetMaintenance/AssetServiceContracts.py`
    - `apps/assets/models/AssetMaintenance/AssetMaintenanceLogs.py`
    - `.claude/tasks/contract-assets-11.5.md`
    - `.agents/tasks/gaps-assets-11.5.md`
  - **Problem**: Pre-build contract specified explicit `db_table` names (`assets_maintenance_request`, etc.). Models omitted `db_table`, causing migration `0008` to land with default Django table names (`assets_assetmaintenancerequest`, etc.).
  - **Fix**: Update `.claude/tasks/contract-assets-11.5.md` to align with the as-built database table names, and document in `.agents/tasks/gaps-assets-11.5.md`.

---

### Important Findings
- [ ] **[I1] Contract Drift: service_contract Missing from AssetMaintenanceRequestDispatchForm & Detail Modal**
  - **Files**:
    - `apps/assets/forms/AssetMaintenance/AssetMaintenanceRequests.py`
    - `apps/assets/views/AssetMaintenance/AssetMaintenanceRequests.py`
    - `templates/assets/asset_maintenance/asset_maintenance_request/detail.html`
  - **Problem**: `service_contract` choice field is missing from `AssetMaintenanceRequestDispatchForm`, detail modal, and view dispatch call.
  - **Fix**: Add `service_contract` choice field to form (scoped to `tenant`), pass in view `obj.dispatch()`, and render in modal.

- [ ] **[I2] Dead Context Variable: linked_logs Not Rendered in Schedule & Contract Detail Templates**
  - **Files**:
    - `templates/assets/asset_maintenance/asset_maintenance_schedule/detail.html`
    - `templates/assets/asset_maintenance/asset_service_contract/detail.html`
  - **Problem**: `linked_logs` is queried and passed by views, but neither template renders it.
  - **Fix**: Add a "Service & Execution Logs" table/card rendering `linked_logs` in both detail templates.

- [ ] **[I3] User-Submitted Remarks Discarded in PM Completion & Contract Renewal**
  - **Files**:
    - `apps/assets/models/AssetMaintenance/AssetMaintenanceSchedules.py`
    - `apps/assets/views/AssetMaintenance/AssetMaintenanceSchedules.py`
    - `apps/assets/models/AssetMaintenance/AssetServiceContracts.py`
    - `apps/assets/views/AssetMaintenance/AssetServiceContracts.py`
  - **Problem**: `notes` entered in completion and renewal modal forms are discarded.
  - **Fix**: Update `record_completion()` and `renew()` to accept and persist notes, and include remarks in `write_audit_log`.

- [ ] **[I4] Non-Standard Theme Classes Used for Badges (badge-blue and badge-purple)**
  - **Files**:
    - `apps/assets/models/AssetMaintenance/AssetMaintenanceSchedules.py`
    - `apps/assets/models/AssetMaintenance/AssetServiceContracts.py`
    - `apps/assets/models/AssetMaintenance/AssetMaintenanceLogs.py`
  - **Problem**: `badge-blue` and `badge-purple` do not exist in `static/css/theme.css`.
  - **Fix**: Replace `badge-blue` with `badge-info`, and `badge-purple` with `badge-slate` or `badge-info`.

- [ ] **[I5] Table Action Delete Buttons in List Templates Lack is_tenant_admin Guard**
  - **Files**:
    - `templates/assets/asset_maintenance/asset_maintenance_request/list.html`
    - `templates/assets/asset_maintenance/asset_maintenance_schedule/list.html`
    - `templates/assets/asset_maintenance/asset_service_contract/list.html`
    - `templates/assets/asset_maintenance/asset_maintenance_log/list.html`
  - **Problem**: Delete forms are rendered to non-admin users in table action cells, leading to 403 Forbidden upon submission.
  - **Fix**: Wrap delete `<form>` blocks in `{% if is_tenant_admin %}` across all 4 list templates.

- [ ] **[I6] General Ledger Posting Stub: post_to_gl Does Not Post a Journal Entry**
  - **Files**:
    - `apps/assets/models/AssetMaintenance/AssetMaintenanceLogs.py`
    - `apps/assets/views/AssetMaintenance/AssetMaintenanceLogs.py`
    - `.agents/tasks/gaps-assets-11.5.md`
  - **Problem**: `post_to_gl()` marks status `posted` without generating `accounting.JournalEntry`.
  - **Fix**: Register and track this ERP financial ledger cross-module dependency in `.agents/tasks/gaps-assets-11.5.md`.

- [ ] **[I7] Missing Form Filter Control for is_breakdown in Asset Maintenance Request List Template**
  - **Files**:
    - `templates/assets/asset_maintenance/asset_maintenance_request/list.html`
  - **Problem**: View implements `is_breakdown=1` filtering, but the template `<form>` lacks a dropdown or control.
  - **Fix**: Add `is_breakdown` select dropdown in the filter bar.

- [ ] **[I8] RTL Spacing Utility Violations (mr-* and ml-* used instead of logical me-* and ms-*)**
  - **Files**:
    - All 12 templates under `templates/assets/asset_maintenance/`.
  - **Problem**: Physical margins break spacing in RTL locales.
  - **Fix**: Replace `mr-*` with `me-*` and `ml-*` with `ms-*`.

- [ ] **[I9] Accessibility: Missing for Attributes on Modal Form label Elements**
  - **Files**:
    - `templates/assets/asset_maintenance/asset_maintenance_request/detail.html`
    - `templates/assets/asset_maintenance/asset_maintenance_schedule/detail.html`
    - `templates/assets/asset_maintenance/asset_service_contract/detail.html`
  - **Problem**: Action modal form labels lack `for` attributes linking to input IDs.
  - **Fix**: Add `for="{{ form.<field>.id_for_label }}"` to modal labels.

- [ ] **[I10] Missing select_related for service_contract and dispatched_work_order in Request Detail View**
  - **Files**:
    - `apps/assets/views/AssetMaintenance/AssetMaintenanceRequests.py`
  - **Problem**: Lazy query loading triggered when accessing `maintenance_request.service_contract` and `maintenance_request.dispatched_work_order`.
  - **Fix**: Add `"service_contract"` and `"dispatched_work_order"` to `select_related` in `asset_maintenance_request_detail`.

---

### Minor Findings
- [ ] **[M1] Fragile Substring Checks in Detail Template Status Conditions**
  - **Files**: `templates/assets/asset_maintenance/asset_maintenance_request/detail.html`
  - **Fix**: Replace `in "submitted,triaged"` with explicit `or` conditions.

- [ ] **[M2] Schedule Recalculation Leaves Overdue Date When Recurrence Unit is Non-Calendar**
  - **Files**: `apps/assets/models/AssetMaintenance/AssetMaintenanceSchedules.py`
  - **Fix**: Set `self.next_due_date = None` when frequency unit is runtime hours or cycles.

- [ ] **[M3] Missing Null Safety Guard in AssetServiceContract.status_css**
  - **Files**: `apps/assets/models/AssetMaintenance/AssetServiceContracts.py`
  - **Fix**: Add `if self.end_date and self.status == "active":`.

- [ ] **[M4] Missing Empty State Action Buttons in Request Detail Linked Logs Table**
  - **Files**: `templates/assets/asset_maintenance/asset_maintenance_request/detail.html`
  - **Fix**: Add "Log First Service Work" CTA button.

- [ ] **[M5] Inconsistent Search Query Context Alias Across 11.5 List Views**
  - **Files**: `apps/assets/views/AssetMaintenance/` all 4 list views.
  - **Fix**: Pass `"search_query": q` in list contexts.

- [ ] **[M6] Accessibility: Missing aria-label on Icon-Only Action Buttons**
  - **Files**: All 4 list templates.
  - **Fix**: Add `aria-label` matching `title`.

- [ ] **[M7] Query Parameter Preservation in Request List Pagination**
  - **Files**: `templates/assets/asset_maintenance/asset_maintenance_request/list.html`
  - **Fix**: Preserve `is_breakdown` in pagination links.

- [ ] **[M8] Use Theme .btn-icon.danger Class on Delete Actions**
  - **Files**: All 4 list templates.
  - **Fix**: Add `.danger` modifier to delete button classes.

- [ ] **[M9] Inconsistent KPI Aggregation Base in Request List View**
  - **Files**: `apps/assets/views/AssetMaintenance/AssetMaintenanceRequests.py`
  - **Fix**: Align to `all_tenant_requests.aggregate(...)`.
