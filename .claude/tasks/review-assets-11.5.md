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
- [x] **[C1] Multi-tenant Queryset Leakage in All Four Create ModelForms**
  - **Files**:
    - `apps/assets/forms/AssetMaintenance/AssetMaintenanceRequests.py`
    - `apps/assets/forms/AssetMaintenance/AssetMaintenanceSchedules.py`
    - `apps/assets/forms/AssetMaintenance/AssetServiceContracts.py`
    - `apps/assets/forms/AssetMaintenance/AssetMaintenanceLogs.py`
    - `apps/assets/views/AssetMaintenance/AssetMaintenanceRequests.py`
    - `apps/assets/views/AssetMaintenance/AssetMaintenanceSchedules.py`
    - `apps/assets/views/AssetMaintenance/AssetServiceContracts.py`
    - `apps/assets/views/AssetMaintenance/AssetMaintenanceLogs.py`
  - **Resolution**: Updated `__init__` across all 4 ModelForms to pop `self.tenant = kwargs.pop("tenant", None)` before `super().__init__()`, filter all foreign key querysets by `self.tenant`, and passed `tenant=request.tenant` from all create and edit views (GET and POST). Verified 0 tenant queryset leakage.

- [x] **[C2] Missing Tenant Cross-Validation for User Foreign Keys in Form clean()**
  - **Files**:
    - `apps/assets/forms/AssetMaintenance/AssetMaintenanceRequests.py`
    - `apps/assets/forms/AssetMaintenance/AssetMaintenanceSchedules.py`
    - `apps/assets/forms/AssetMaintenance/AssetMaintenanceLogs.py`
  - **Resolution**: Added explicit tenant validations for `requester`, `assigned_technician`, and `lead_technician` in form `clean()` methods to reject foreign-tenant user IDs.

- [~] **[C3] Canonical db_table Omitted on All Four 11.5 Models**
  - **Files**:
    - `apps/assets/models/AssetMaintenance/AssetMaintenanceRequests.py`
    - `apps/assets/models/AssetMaintenance/AssetMaintenanceSchedules.py`
    - `apps/assets/models/AssetMaintenance/AssetServiceContracts.py`
    - `apps/assets/models/AssetMaintenance/AssetMaintenanceLogs.py`
    - `.claude/tasks/contract-assets-11.5.md`
    - `.agents/tasks/gaps-assets-11.5.md`
  - **Resolution**: Deferred table renaming to asset module schema harmonization pass to avoid production table-migration churn. Documented in `GAP-assets-11.5-01` and aligned `.claude/tasks/contract-assets-11.5.md` with as-built migration `0008` table names.

---

### Important Findings
- [x] **[I1] Contract Drift: service_contract Missing from AssetMaintenanceRequestDispatchForm & Detail Modal**
  - **Files**:
    - `apps/assets/forms/AssetMaintenance/AssetMaintenanceRequests.py`
    - `apps/assets/views/AssetMaintenance/AssetMaintenanceRequests.py`
    - `templates/assets/asset_maintenance/asset_maintenance_request/detail.html`
  - **Resolution**: Added `service_contract` choice field (scoped to `tenant`), wired into view dispatch logic, and rendered in dispatch modal.

- [x] **[I2] Dead Context Variable: linked_logs Not Rendered in Schedule & Contract Detail Templates**
  - **Files**:
    - `templates/assets/asset_maintenance/asset_maintenance_schedule/detail.html`
    - `templates/assets/asset_maintenance/asset_service_contract/detail.html`
  - **Resolution**: Added "Completed Maintenance Logs" tables rendering `linked_logs` with CTA buttons in both templates.

- [x] **[I3] User-Submitted Remarks Discarded in PM Completion & Contract Renewal**
  - **Files**:
    - `apps/assets/models/AssetMaintenance/AssetMaintenanceSchedules.py`
    - `apps/assets/views/AssetMaintenance/AssetMaintenanceSchedules.py`
    - `apps/assets/models/AssetMaintenance/AssetServiceContracts.py`
    - `apps/assets/views/AssetMaintenance/AssetServiceContracts.py`
  - **Resolution**: Updated `record_completion()` and `renew()` to accept `notes` and append timestamped notes to `self.notes`, and recorded remarks in audit logs.

- [x] **[I4] Non-Standard Theme Classes Used for Badges (badge-blue and badge-purple)**
  - **Files**:
    - `apps/assets/models/AssetMaintenance/AssetMaintenanceSchedules.py`
    - `apps/assets/models/AssetMaintenance/AssetServiceContracts.py`
    - `apps/assets/models/AssetMaintenance/AssetMaintenanceLogs.py`
  - **Resolution**: Replaced `badge-purple` with `badge-info`/`badge-slate` and `badge-blue` with `badge-info`. All badge CSS keys match `theme.css`.

- [x] **[I5] Table Action Delete Buttons in List Templates Lack is_tenant_admin Guard**
  - **Files**:
    - `templates/assets/asset_maintenance/asset_maintenance_request/list.html`
    - `templates/assets/asset_maintenance/asset_maintenance_schedule/list.html`
    - `templates/assets/asset_maintenance/asset_service_contract/list.html`
    - `templates/assets/asset_maintenance/asset_maintenance_log/list.html`
  - **Resolution**: Wrapped table action delete `<form>` blocks in `{% if is_tenant_admin %}` across all 4 list templates and detail pages.

- [~] **[I6] General Ledger Posting Stub: post_to_gl Does Not Post a Journal Entry**
  - **Files**:
    - `apps/assets/models/AssetMaintenance/AssetMaintenanceLogs.py`
    - `apps/assets/views/AssetMaintenance/AssetMaintenanceLogs.py`
    - `.agents/tasks/gaps-assets-11.5.md`
  - **Resolution**: Formally tracked in `.agents/tasks/gaps-assets-11.5.md` as `GAP-assets-11.5-02`, blocked on Accounting AP bill / cash disbursement ledger integration.

- [x] **[I7] Missing Form Filter Control for is_breakdown in Asset Maintenance Request List Template**
  - **Files**:
    - `templates/assets/asset_maintenance/asset_maintenance_request/list.html`
  - **Resolution**: Added `is_breakdown` select dropdown in request list filter bar.

- [x] **[I8] RTL Spacing Utility Violations (mr-* and ml-* used instead of logical me-* and ms-*)**
  - **Files**:
    - All 12 templates under `templates/assets/asset_maintenance/`.
  - **Resolution**: Replaced all `mr-*` with `me-*`, and `ml-*` with `ms-*` across all list, detail, and form templates.

- [x] **[I9] Accessibility: Missing for Attributes on Modal Form label Elements**
  - **Files**:
    - `templates/assets/asset_maintenance/asset_maintenance_request/detail.html`
    - `templates/assets/asset_maintenance/asset_maintenance_schedule/detail.html`
    - `templates/assets/asset_maintenance/asset_service_contract/detail.html`
  - **Resolution**: Added `for="{{ form.<field>.id_for_label }}"` to all action modal labels.

- [x] **[I10] Missing select_related for service_contract and dispatched_work_order in Request Detail View**
  - **Files**:
    - `apps/assets/views/AssetMaintenance/AssetMaintenanceRequests.py`
  - **Resolution**: Verified `"service_contract"` and `"dispatched_work_order"` are present in `select_related`.

---

### Minor Findings
- [x] **[M1] Fragile Substring Checks in Detail Template Status Conditions**
  - **Files**: `templates/assets/asset_maintenance/asset_maintenance_request/detail.html`
  - **Resolution**: Replaced `in "submitted,triaged"` with explicit boolean `or`.

- [x] **[M2] Schedule Recalculation Leaves Overdue Date When Recurrence Unit is Non-Calendar**
  - **Files**: `apps/assets/models/AssetMaintenance/AssetMaintenanceSchedules.py`
  - **Resolution**: Set `self.next_due_date = None` when frequency unit is non-calendar (hours or cycles).

- [x] **[M3] Missing Null Safety Guard in AssetServiceContract.status_css**
  - **Files**: `apps/assets/models/AssetMaintenance/AssetServiceContracts.py`
  - **Resolution**: Added `if self.status == "active" and self.end_date:`.

- [x] **[M4] Missing Empty State Action Buttons in Request Detail Linked Logs Table**
  - **Files**: `templates/assets/asset_maintenance/asset_maintenance_request/detail.html`
  - **Resolution**: Added "Log First Service Work" CTA button in empty state table row.

- [x] **[M5] Inconsistent Search Query Context Alias Across 11.5 List Views**
  - **Files**: `apps/assets/views/AssetMaintenance/` all 4 list views.
  - **Resolution**: Added `"search_query": q` in context across all 4 list views.

- [x] **[M6] Accessibility: Missing aria-label on Icon-Only Action Buttons**
  - **Files**: All 4 list templates.
  - **Resolution**: Added matching `aria-label` attributes to all icon-only buttons.

- [x] **[M7] Query Parameter Preservation in Request List Pagination**
  - **Files**: `templates/assets/asset_maintenance/asset_maintenance_request/list.html`
  - **Resolution**: Preserved `&is_breakdown={{ request.GET.is_breakdown }}` in pagination links.

- [x] **[M8] Use Theme .btn-icon.danger Class on Delete Actions**
  - **Files**: All 4 list templates.
  - **Resolution**: Added `.danger` modifier class to all delete action buttons.

- [x] **[M9] Inconsistent KPI Aggregation Base in Request List View**
  - **Files**: `apps/assets/views/AssetMaintenance/AssetMaintenanceRequests.py`
  - **Resolution**: Verified workspace-wide aggregation on `all_tenant_requests`.
