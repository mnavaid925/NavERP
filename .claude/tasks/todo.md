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

## Review — delivered 2026-07-03

**Scope built.** Completed HRM 3.9 by adding the two missing NavERP.md bullets. 2 new models over the
existing attendance spine: `GeoFence` (GPS zones, real haversine `distance_to`/`contains`, delete-guarded)
and `AttendanceRegularization` (`REG-`, draft→pending→approved/rejected/cancelled; admin approve rewrites the
linked punch to `regularized` and, when none is linked, finds the (employee,date) row or materialises a fresh
`ATT-` punch). `AttendanceRecord` gained `latitude`/`longitude`/`geofence` + derived `geo_status()`. Full CRUD +
workflow, admin-gated approve/reject, wired into `LIVE_LINKS["3.9"]` (all 5 bullets now live), seeded, 2 migrations
(0018 models, 0019 geofence index).

**Verification.** `manage.py check` clean; migrates cleanly; `seed_hrm` idempotent (2 geofences + 2 regularizations
/tenant). Smoke script (temp/, gitignored): every new URL 200/302, filters work, no `{#` leaks, both approve
branches correct (linked punch → regularized; unlinked → new ATT- punch materialised + linked back), cross-tenant
IDOR → 404 (incl. the privileged POST, row unmutated), `geofence_detail` flat 9 queries for 15 punches.

**Review-agent sequence (all applied + committed one file per commit):**
- code-reviewer → 2 fixes: approve always produces a corrected punch (was a silent no-op with no linked record);
  approve/reject panel admin-gated (`is_superuser`/`is_tenant_admin`), mirroring 3.8.
- explorer → 4: `AttendanceRecord.clean()` lat/long pairing; dead `privileged-note` CSS removed; punch↔regularization
  back-link section on the record detail; "Pending Regularizations" KPI on the HRM overview.
- frontend-reviewer → clean (only pre-existing-pattern nits; no changes).
- performance-reviewer → 2: `geofence_detail` N+1 fixed via FK-cache priming (24→9 queries); `(tenant, geofence)`
  composite index (migration 0019).
- qa-smoke-tester → clean (independent migrate+seed+sweep all green).
- security-reviewer → no Critical/High/Medium; one pre-existing app-wide Low (any tenant user can file for any
  employee, same as LeaveRequest) left as-is.
- test-writer → **125 tests** in `apps/hrm/tests/test_attendance_management.py`; HRM suite **1,673** green,
  project-wide **4,320** green.

**Skill.** `.claude/skills/hrm/SKILL.md` updated (frontmatter, table count 43→45, 2 new model rows + AttendanceRecord
geo fields, routes + workflow extras, template folders, LIVE_LINKS 3.9, seeder, Deferred pruned).

**Deferred (future 3.9 passes):** live GPS capture from a mobile/biometric device (coords are manual on the form
now); reverse-geocoding of coordinates to addresses; auto-suggesting the nearest active geofence at punch time;
regularization SLA/escalation + bulk approve; per-employee↔user ownership scoping on request creation (app-wide
convention, tracked separately).

**Next unbuilt sub-module:** 3.11 Time Tracking.
