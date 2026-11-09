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

