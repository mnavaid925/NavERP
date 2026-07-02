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

## Review
_(filled in after build)_
