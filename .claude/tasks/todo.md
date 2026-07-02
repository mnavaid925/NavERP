---
# HRM 3.9 Attendance Management — completion pass (Regularization + Geofencing)  (2026-07-02)

**Context.** 3.9 was previously built (Shift / ShiftAssignment / AttendanceRecord, full CRUD,
`LIVE_LINKS["3.9"]`). Two NavERP.md bullets (line 502–507) were never built as distinct features:
**Attendance Regularization** and **Geofencing**. This pass completes the sub-module by adding those
two, then re-runs the review-agent sequence. Extending `apps/hrm` — NOT a new app.

## New models (2)

### 1. `AttendanceRegularization` (REG-…) — Attendance Regularization bullet
Employee-raised request to correct an attendance punch; multi-state approval workflow that, on approve,
writes the corrected times back onto the linked `AttendanceRecord` (status → `regularized`).
- `number` REG-#### (TenantNumbered), `employee` → EmployeeProfile
- `attendance_record` → AttendanceRecord (SET_NULL, optional — corrected on approve if linked)
- `date`, `reason_type` (missed_punch/forgot_checkin/forgot_checkout/wrong_time/on_duty/work_from_home/system_error/other)
- `requested_check_in`, `requested_check_out`, `reason`
- status machine `draft → pending → approved/rejected` (+ `cancelled`); `OPEN_STATUSES=(draft,pending)`
- `approver` (User, SET_NULL), `approved_at`, `decision_note`
- workflow views: submit (owner) / approve+reject (`@tenant_admin_required`) / cancel — mirrors LeaveRequest
- on approve: apply requested times to the linked record + set it `regularized` (recompute hours in save)

### 2. `GeoFence` — Geofencing bullet
A GPS zone for field/site attendance; real haversine `distance_to`/`contains` (not a stub).
- `name` (unique per tenant), `latitude`/`longitude` (Decimal 9,6 + range validators), `radius_m`, `address`, `is_active`
- delete guard: block if attendance rows reference it (deactivate instead) — mirrors `shift_delete`

### `AttendanceRecord` extension (Geofencing capture on punches)
- add `latitude`, `longitude`, `geofence` (FK GeoFence SET_NULL) + `geo_status()` helper (verified/outside/—)
- extend `AttendanceRecordForm` + record list/detail templates to show geo verification

## Build checklist
- [ ] models: `import math`; extend AttendanceRecord; add GeoFence + AttendanceRegularization
- [ ] forms: `GeoFenceForm`, `AttendanceRegularizationForm`; extend `AttendanceRecordForm` (lat/long/geofence)
- [ ] views: full CRUD for both + regularization submit/approve/reject/cancel; geofence delete guard
- [ ] urls: `geofences/…`, `regularizations/…` (+ workflow actions)
- [ ] admin: register `GeoFence`, `AttendanceRegularization`
- [ ] navigation: `LIVE_LINKS["3.9"]` += Attendance Regularization + Geofencing
- [ ] templates: `attendance/geofence/{list,detail,form}.html`, `attendance/regularization/{list,detail,form}.html`
- [ ] seeder: `_seed_geofences` + regularizations; attach geofence to a few present punches; add to flush order
- [ ] migrate + seed (x2 idempotent) + `manage.py check`
- [ ] verify: throwaway smoke script — every new url 200/302 as admin_acme + cross-tenant 404
- [ ] review agents: code-reviewer → explorer → frontend-reviewer → performance-reviewer → qa-smoke-tester → security-reviewer → test-writer
- [ ] update `.claude/skills/hrm/SKILL.md` 3.9 section

## Review
_(filled in after build)_
