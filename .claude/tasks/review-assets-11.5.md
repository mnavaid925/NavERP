# Review Findings: Module 11.5 — Maintenance & Repair Management

**Review Range**: `bb6c9161324de1933874a26e1b589f617902f533...HEAD`
**Module**: Asset Management System (`apps/assets`)
**Sub-module**: 11.5 Maintenance & Repair Management
**Entities**:
1. `AssetMaintenanceRequest` [AMRQ-]
2. `AssetMaintenanceSchedule` [AMSC-]
3. `AssetServiceContract` [ASVC-]
4. `AssetMaintenanceLog` [AMLG-]

---

## Reviewer 1: `code-reviewer` Findings

### Critical
- **[CR1-C1] Multi-tenant Queryset Leakage in All Four Create ModelForms**
  - **Files**: `apps/assets/forms/AssetMaintenance/AssetMaintenanceRequests.py` (56-64), `AssetMaintenanceSchedules.py` (67-82), `AssetServiceContracts.py` (66-73), `AssetMaintenanceLogs.py` (78-91), and corresponding views `asset_maintenance_*_create`.
  - **Problem**: Forms inspect `self.tenant` in `__init__`, but neither accept `tenant` as a keyword argument in `__init__` nor pop it before `super().__init__()`. In create views, `form.tenant = request.tenant` is assigned *after* `Form()` instantiation. For unsaved model instances, `self.instance.tenant` is `None`, causing all foreign key dropdown querysets to evaluate without tenant scoping during creation GET/POST.
  - **Fix**: Update `__init__(self, *args, **kwargs)` in all four forms to `self.tenant = kwargs.pop("tenant", None)` before `super().__init__(*args, **kwargs)`, and pass `tenant=request.tenant` into form instantiation in all create views.

- **[CR1-C2] Missing Tenant Cross-Validation for User Foreign Keys in Form clean()**
  - **Files**: `apps/assets/forms/AssetMaintenance/AssetMaintenanceRequests.py` (67), `AssetMaintenanceSchedules.py` (85), `AssetMaintenanceLogs.py` (94-106).
  - **Problem**: `reject_foreign()` omits User foreign keys (`requester`, `assigned_technician`, `lead_technician`).
  - **Fix**: Validate that `requester`, `assigned_technician`, and `lead_technician` match `self.tenant` (or check `tenant_id`).

### Important
- **[CR1-I1] Contract Drift: service_contract Missing from AssetMaintenanceRequestDispatchForm & View Dispatch Logic**
  - **Files**: `apps/assets/forms/AssetMaintenance/AssetMaintenanceRequests.py` (85-108), `apps/assets/views/AssetMaintenance/AssetMaintenanceRequests.py` (211-224), `templates/assets/asset_maintenance/asset_maintenance_request/detail.html` (340-365).
  - **Problem**: Contract Section 2.1 specifies `service_contract` on `AssetMaintenanceRequestDispatchForm`, but it was omitted from the form, view dispatch call, and modal.
  - **Fix**: Add `service_contract` choice field scoped to tenant, pass to `obj.dispatch()`, and render in modal.

- **[CR1-I2] General Ledger Posting Stub: post_to_gl Does Not Post a Journal Entry**
  - **Files**: `apps/assets/models/AssetMaintenance/AssetMaintenanceLogs.py` (288-307), `apps/assets/views/AssetMaintenance/AssetMaintenanceLogs.py` (188-193).
  - **Problem**: `post_to_gl()` marks status as `posted` but does not instantiate `JournalEntry` / `JournalLine`s.
  - **Fix**: Create balanced `accounting.JournalEntry` (Dr Expense / Cr AP/Cash) or document in gap register.

- **[CR1-I3] User-Submitted Remarks Discarded in PM Completion & Contract Renewal**
  - **Files**: `apps/assets/views/AssetMaintenance/AssetMaintenanceSchedules.py` (230-254), `AssetServiceContracts.py` (207-224).
  - **Problem**: `notes` entered in completion and renewal forms are discarded.
  - **Fix**: Update `record_completion()` and `renew()` to accept and persist notes.

- **[CR1-I4] Non-Standard Theme Classes Used for Badges (badge-blue and badge-purple)**
  - **Files**: `apps/assets/models/AssetMaintenance/AssetMaintenanceLogs.py` (60, 66), `AssetMaintenanceSchedules.py` (53), `AssetServiceContracts.py` (53, 55).
  - **Problem**: `badge-blue` and `badge-purple` are not defined in `theme.css`.
  - **Fix**: Replace `badge-blue` with `badge-info`, and `badge-purple` with `badge-slate` or `badge-info`.

### Minor
- **[CR1-M1] Fragile Substring Checks in Detail Template Status Conditions**
  - **Files**: `templates/assets/asset_maintenance/asset_maintenance_request/detail.html` (35, 50, 65).
  - **Problem**: Uses `in "submitted,triaged"` instead of explicit boolean checks.
  - **Fix**: Use `status == "submitted" or status == "triaged"`.

- **[CR1-M2] Schedule Recalculation Leaves Overdue Date When Recurrence Unit is Runtime Hours or Cycles**
  - **Files**: `apps/assets/models/AssetMaintenance/AssetMaintenanceSchedules.py` (216-230).
  - **Problem**: If recurring by meter or cycles, `next_due_date` is not updated or cleared.
  - **Fix**: Set `self.next_due_date = None` when frequency unit is non-calendar.

- **[CR1-M3] Missing Null Safety Guard in AssetServiceContract.status_css**
  - **Files**: `apps/assets/models/AssetMaintenance/AssetServiceContracts.py` (175-181).
  - **Problem**: Compares `self.end_date < today` without checking if `end_date` is truthy.
  - **Fix**: Add `if self.end_date and self.status == "active":`.

---

## Reviewer 2: `explorer` Findings

### Critical
- **[EXP-C1] Explicit db_table Omitted on All Four 11.5 Models**
  - **Files**: `apps/assets/models/AssetMaintenance/AssetMaintenanceRequests.py`, `AssetMaintenanceSchedules.py`, `AssetServiceContracts.py`, `AssetMaintenanceLogs.py`, `migrations/0008_...py`, `.claude/tasks/contract-assets-11.5.md`.
  - **Problem**: Contract mandates `assets_maintenance_request`, `assets_maintenance_schedule`, `assets_service_contract`, `assets_maintenance_log`. Models omitted `db_table`, defaulting to `assets_assetmaintenancerequest`, etc.
  - **Fix**: Update contract and document in gap register or add `db_table` and generate migration.

### Important
- **[EXP-I1] Dead Context Variable: linked_logs Provided by Views But Never Rendered in Templates**
  - **Files**: `apps/assets/views/AssetMaintenance/AssetMaintenanceSchedules.py` (102), `AssetServiceContracts.py` (93), `templates/assets/asset_maintenance/asset_maintenance_schedule/detail.html`, `templates/assets/asset_maintenance/asset_service_contract/detail.html`.
  - **Problem**: `linked_logs` is queried and passed by schedule and service contract detail views, but neither template renders the logs card.
  - **Fix**: Add a "Service & Maintenance Execution Logs" card/table rendering `linked_logs` in both detail templates.

- **[EXP-I2] Missing Form Filter Control for is_breakdown in Asset Maintenance Request List Template**
  - **Files**: `templates/assets/asset_maintenance/asset_maintenance_request/list.html` (57-103), `apps/assets/views/AssetMaintenance/AssetMaintenanceRequests.py` (49-52).
  - **Problem**: View filters by `is_breakdown=1`, but filter `<form>` in template lacks dropdown or control for it.
  - **Fix**: Add `is_breakdown` filter dropdown or wrap Breakdowns KPI card with `?is_breakdown=1`.

- **[EXP-I3] Contract Action Mismatch: post_to_gl Stub Does Not Create Balanced accounting.JournalEntry**
  - **Files**: `apps/assets/models/AssetMaintenance/AssetMaintenanceLogs.py` (288-307), `apps/assets/views/AssetMaintenance/AssetMaintenanceLogs.py` (188-193).
  - **Problem**: `post_to_gl()` marks status `posted` without generating `JournalEntry`/`JournalLine`s.
  - **Fix**: Create balanced `JournalEntry` or register in `.agents/tasks/gaps-assets-11.5.md`.

- **[EXP-I4] Contract Compliance: service_contract Omitted from AssetMaintenanceRequestDispatchForm and Dispatch Modal**
  - **Files**: `apps/assets/forms/AssetMaintenance/AssetMaintenanceRequests.py` (85-108), `apps/assets/views/AssetMaintenance/AssetMaintenanceRequests.py` (211-224), `templates/assets/asset_maintenance/asset_maintenance_request/detail.html` (340-365).
  - **Problem**: `service_contract` omitted from dispatch form and modal.
  - **Fix**: Add `service_contract` choice field, pass to `obj.dispatch()`, and render in modal.

### Minor
- **[EXP-M1] Missing Empty State Action Buttons in Request Detail Linked Logs Table**
  - **Files**: `templates/assets/asset_maintenance/asset_maintenance_request/detail.html` (207-212).
  - **Problem**: Empty state row has no CTA button.
  - **Fix**: Add "Log First Service Work" button linking to create view.

- **[EXP-M2] Inconsistent Search Query Context Alias Across 11.5 List Views**
  - **Files**: `apps/assets/views/AssetMaintenance/` all 4 list views.
  - **Problem**: Views pass `q` but omit `"search_query": q` in context.
  - **Fix**: Pass `"search_query": q` in list contexts.

---

## Reviewer 3: `frontend-reviewer` Findings

### Important
- **[FE-I1] Non-Existent Theme Badge Classes (badge-purple and badge-blue)**
  - **Files**: `apps/assets/models/AssetMaintenance/AssetMaintenanceSchedules.py` (53), `AssetServiceContracts.py` (53, 55), `AssetMaintenanceLogs.py` (60, 66).
  - **Problem**: `static/css/theme.css` has NO `.badge-purple` and NO `.badge-blue`. Renders unstyled plain pill outlines.
  - **Fix**: Replace `badge-purple` with `badge-info`/`badge-slate` and `badge-blue` with `badge-info`.

- **[FE-I2] RTL Spacing Utility Violations (mr-* and ml-* used instead of logical me-* and ms-*)**
  - **Files**: All 12 templates under `templates/assets/asset_maintenance/`.
  - **Problem**: Physical direction margins break spacing in RTL locales.
  - **Fix**: Replace all `mr-1` with `me-1`, and all `ml-1` with `ms-1`.

- **[FE-I3] Accessibility: Missing for Attributes on Modal Form label Elements**
  - **Files**: `templates/assets/asset_maintenance/asset_maintenance_request/detail.html` (323, 327, 347, 351, 355, 375, 395), `asset_maintenance_schedule/detail.html` (275, 279, 283), `asset_service_contract/detail.html` (269, 273, 277).
  - **Problem**: Action modal labels lack `for="..."` linking to inputs.
  - **Fix**: Add `for="{{ form.<field>.id_for_label }}"` to modal labels.

### Minor
- **[FE-M1] Accessibility: Missing aria-label on Icon-Only Action Buttons**
  - **Files**: All 4 list templates (view, edit, delete buttons) and detail back buttons.
  - **Problem**: Icon buttons have `title` but lack `aria-label`.
  - **Fix**: Add `aria-label` attributes to icon-only buttons.

- **[FE-M2] Query Parameter Preservation in Request List Pagination**
  - **Files**: `templates/assets/asset_maintenance/asset_maintenance_request/list.html` (215, 221).
  - **Problem**: Pagination links omit `&is_breakdown={{ request.GET.is_breakdown }}`.
  - **Fix**: Preserve `is_breakdown` parameter in pagination links.

- **[FE-M3] Use Theme .btn-icon.danger Class on Delete Actions**
  - **Files**: All 4 list templates delete buttons.
  - **Problem**: Missing `.danger` modifier class from `theme.css`.
  - **Fix**: Add `.danger` modifier to delete button classes.

---

## Reviewer 4: `performance-reviewer` Findings

### Important
- **[PERF-I1] Missing select_related for service_contract and dispatched_work_order in Request Detail View**
  - **Files**: `apps/assets/views/AssetMaintenance/AssetMaintenanceRequests.py` (72-88).
  - **Problem**: Detail template renders `maintenance_request.service_contract.contract_number` and `maintenance_request.dispatched_work_order.number`, triggering extra lazy queries on ticket detail page.
  - **Fix**: Add `"service_contract"` and `"dispatched_work_order"` to `select_related` in `asset_maintenance_request_detail`.

### Minor
- **[PERF-M1] Inconsistent KPI Aggregation Base in Request List View**
  - **Files**: `apps/assets/views/AssetMaintenance/AssetMaintenanceRequests.py` (54-61).
  - **Problem**: Computes KPIs on filtered `qs` while Schedules, Contracts, and Logs aggregate on `all_tenant_*` (workspace total).
  - **Fix**: Align to `all_tenant_requests.aggregate(...)` to show workspace-wide maintenance metrics consistently with sibling dashboards.

---

## Reviewer 5: `qa-smoke-tester` Findings

### Verification Status: PASS (32/32 tests green)
- **Standard Endpoints (24 passed)**: List, filtered list, junk-param list, create GET, detail GET, and edit GET for all 4 models (`AssetMaintenanceRequest`, `AssetMaintenanceSchedule`, `AssetServiceContract`, `AssetMaintenanceLog`).
- **Cross-Tenant IDOR (8 passed)**: Attempting to access ACME entities with Globex credentials returns 404 across all detail and edit endpoints.
- **CSRF & HTTP Method Safety**: All 14 mutation endpoints require `@require_POST`, with delete and approval actions protected by `@tenant_admin_required`.

### Minor Findings
- **[QA-M1] Form Validation Error Feedback in Modal Actions**
  - **Files**: Action endpoints in `AssetMaintenanceRequests.py`, `AssetMaintenanceSchedules.py`, `AssetServiceContracts.py`.
  - **Problem**: When a modal action form fails validation (e.g., negative completion meter), views redirect back with `messages.error(request, ...)` showing the first form error, but the modal does not auto-reopen.
  - **Fix**: Standard NavERP pattern handles modal flash messages cleanly, but appending query parameter `?action_error=triage` allows frontend script to auto-reopen modal if needed.





