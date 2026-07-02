---
# HRM 3.10 Leave Management — completion pass (Leave Policy engine + Encashment)  (2026-07-03)

**Context.** 3.10 was previously built (LeaveType / LeaveAllocation / LeaveRequest / PublicHoliday, full CRUD +
approve workflow, `LIVE_LINKS["3.10"]`). Of NavERP.md's 5 bullets, **"Leave Policy" (accrual / carry-forward /
encashment) is the only one not built as a distinct feature** — the rules exist as config on `LeaveType`, but there
is no engine that runs accrual/carry-forward and no standalone encashment workflow (`compute_leave_encashment` is
offboarding-only). This pass completes 3.10 with a policy **engine** + an **encashment** workflow. Extending
`apps/hrm` — NOT a new app.

## New model (1) + 1 field

### `LeaveEncashment` (ENC-…) — the encashment request workflow
- `number` ENC-#### (TenantNumbered), `employee` → EmployeeProfile, `leave_type` → LeaveType (must be encashable)
- `year`, `days`, `rate_per_day`, `amount` (editable=False, = days × rate_per_day in save())
- status `draft → pending → approved → paid` (+ `rejected`, `cancelled`); `OPEN_STATUSES=(draft,pending)`
- `approver`(User SET_NULL), `approved_at`, `paid_on`, `payment_reference`, `decision_note`
- `clean()`: days > 0; leave_type must be `encashable`; days ≤ available balance for (employee, leave_type, year)
- workflow views: submit (owner) / approve+reject+mark_paid (`@tenant_admin_required`) / cancel (owner)
- **on approve** (atomic): reduce the matching `LeaveAllocation.allocated_days` by `days` (encashment consumes leave)

### `LeaveAllocation.carried_forward` (Decimal, editable=False, default 0)
- records days rolled in from the prior year (part of allocated_days) → makes carry-forward idempotent + auditable

## Policy engine (no model — standalone page + admin run actions)
- `leave_policy` (GET): lists LeaveTypes + their accrual/carry-forward/encashment config + a year selector and the
  two run actions; shows a current-year allocation summary.
- `leave_accrual_run` (POST, `@tenant_admin_required`): per active employee × accruing LeaveType, set
  `allocated_days = accrued(year) + carried_forward` (annual→accrual_days; monthly→accrual_days×months_elapsed),
  capped at `max_balance`. Idempotent per run.
- `leave_carryforward_run` (POST, `@tenant_admin_required`): source year → year+1, `carry = min(max(balance,0),
  max_carry_forward)`; set `dst.allocated_days = (dst.allocated_days − dst.carried_forward) + carry`,
  `dst.carried_forward = carry`. Idempotent.

## Build checklist
- [ ] models: `LeaveEncashment` + `LeaveAllocation.carried_forward`
- [ ] forms: `LeaveEncashmentForm` (workflow fields excluded)
- [ ] views: encashment CRUD + submit/approve/reject/mark_paid/cancel; `leave_policy` + accrual/carry-forward runs
- [ ] urls: `leave-encashments/…` (+ workflow) ; `leave-policy/` + `…/accrual-run/` + `…/carry-forward-run/`
- [ ] admin: register `LeaveEncashment`
- [ ] navigation: `LIVE_LINKS["3.10"]` += Leave Policy (`leave_policy`) + Leave Encashment (extra)
- [ ] templates: `leave/encashment/{list,detail,form}.html`, `leave/policy.html` (standalone); show carried_forward on allocation detail
- [ ] seeder: seed 1–2 encashment requests; carried_forward defaults 0
- [ ] migrate + seed (x2 idempotent) + `manage.py check`
- [ ] verify: smoke script — new urls 200/302, accrual/carry-forward runs mutate allocations idempotently, encashment approve reduces allocated_days, cross-tenant 404
- [ ] review agents: code-reviewer → explorer → frontend-reviewer → performance-reviewer → qa-smoke-tester → security-reviewer → test-writer
- [ ] update `.claude/skills/hrm/SKILL.md` 3.10 section

## Review — delivered 2026-07-03

**Scope built.** Completed HRM 3.10 by adding the missing "Leave Policy" bullet as a working engine + an encashment
workflow. New `LeaveEncashment` (`ENC-`, draft→pending→approved→paid/rejected/cancelled; approve consumes balance)
+ `LeaveAllocation.carried_forward`/`encashed_days` fields. **Leave Policy engine** (`leave_policy` page, no model):
admin `leave_accrual_run` (annual grant / monthly rate×elapsed-months, capped at max_balance) and
`leave_carryforward_run` (min(balance, max_carry_forward) → next year), both idempotent + atomic + audit-logged.
Wired into `LIVE_LINKS["3.10"]` (all 5 bullets live + Encashment extra), admin, seeder (2 encashments/tenant),
2 migrations (0020 model+carried_forward, 0021 encashed_days).

**Key correctness insight (encashed_days).** Encashment approve records days in a **separate `encashed_days`** field,
not by shrinking `allocated_days` — because the accrual engine recomputes `allocated_days`, and reducing it directly
would let a routine accrual re-run silently restore cashed-out days (double-spend). `balance = allocated − used −
encashed`; carry-forward and offboarding both net out encashed days.

**Review-agent sequence (all applied + committed):**
- code-reviewer → 4: AuditLog.action truncation (10-char field → verb moved to `changes`); carry-forward dest-year
  `max_balance` cap; `LeaveAllocationForm` resets `carried_forward` on manual edit; `_accrual_target` 0 months for a
  future year.
- explorer → **double-spend bug** (accrual re-run restored encashed days) fixed via the `encashed_days` field; carry-
  forward + `compute_leave_encashment` net encashed days; allocation↔encashment cross-link; pending-encashments KPI.
- frontend-reviewer → 1 (always-render the allocation-detail Encashments card with an empty-state); else clean.
- performance-reviewer → clean (no N+1s; engine `get_or_create`-in-loop is O(employees×types), demo-acceptable —
  deferred the bulk_create/bulk_update rewrite as a scaling note).
- qa-smoke-tester → clean (independent migrate+seed+engine/workflow sweep, double-spend regression confirmed).
- security-reviewer → 1 applied (bound `_policy_year` to 2000–2100 vs oversized-year DB 500); 1 **rejected** (adding
  `tenant=` to `LeaveEncashment.clean()` would filter tenant=None pre-validation on create and break it — not
  exploitable, employee_id is already tenant-bound).
- test-writer → **102 tests** in `test_leave_encashment_and_policy.py`; HRM suite **1,775** green, project-wide **4,422**.

**Skill/README** updated (table 45→46, LeaveEncashment + LeaveAllocation fields, routes/engine actions, template
folders, LIVE_LINKS 3.10, seeder, Deferred pruned + scaling/offboarding notes; test counts refreshed).

**Deferred (future 3.10 passes):** engine bulk-write rewrite (prefetch-dict + bulk_create/bulk_update, pre-assigning
LA- numbers) or background task before ~hundreds of employees; auto-cancel/net open (draft/pending) encashments on
separation so final settlement can't double-pay (spawned as a background task); per-employee↔user ownership scoping
on request/encashment creation (app-wide convention).

**Next unbuilt sub-module:** 3.11 Time Tracking.
