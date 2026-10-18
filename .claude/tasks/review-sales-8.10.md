# Review Findings: Sales 8.10 Incentive Compensation Management

**Base Commit:** `bf3ecbf7017f0bec1590b4f5dc9f06585aa67cb7`
**Head Commit:** `45bfcdc125ffabd864848582ae8b26cf030cedd6`
**Target Sub-Module:** Sub-module 8.10 Incentive Compensation Management (`apps/sales/`)

---

## 1. Code Review (`code-reviewer`)

### Verdict
Commit after fixing Critical+Important.

### Critical
- `apps/sales/views/IncentiveCompensation/CommissionStatements.py:177` — `commission_statement_approve` lacks privilege authorization gating, does not prevent payees from approving their own commission statements, and has no status guard preventing re-approval of locked/paid statements. Fix: Add `@tenant_admin_required` or manager role check, block self-approval (`if obj.payee == request.user and not request.user.is_superuser: return HttpResponseForbidden(...)`), and guard `if obj.status not in ("draft", "under_review"): return redirect(...)`.
- `apps/sales/views/IncentiveCompensation/CommissionStatements.py:196` — `commission_statement_lock` lacks privilege authorization gating and does not enforce a view-level status guard checking `if obj.status == "approved"`. Fix: Add `@tenant_admin_required` and enforce `if obj.status != "approved": return redirect(...)`.
- `apps/sales/views/IncentiveCompensation/CommissionAdjustments.py:167` — `commission_adjustment_resolve_dispute` lacks authorization gating and allows sales reps to self-approve their own dispute claims. Fix: Add manager/tenant admin authorization check and block self-approval when `obj.payee == request.user and not request.user.is_superuser`.
- `apps/sales/views/IncentiveCompensation/CommissionEarnings.py:145` — `commission_earning_edit` and `commission_earning_delete` (line 175) lack view-level status guards against mutating or deleting earnings that are already `paid` or attached to a finalized/locked statement. Fix: Guard both views with `if obj.status in ("approved", "paid", "clawed_back") or (obj.statement and obj.statement.status in ("locked", "exported", "paid")): return redirect(...)`.

### Important
- `apps/sales/forms/IncentiveCompensation/CommissionStatements.py:20` — `CommissionStatementForm` exposes `status` in `Meta.fields`, allowing any user to set statements directly to `approved`, `locked`, or `paid` via standard POST. Fix: Remove `"status"` from `CommissionStatementForm.Meta.fields` and manage statement state transitions exclusively through dedicated action endpoints.
- `apps/sales/forms/IncentiveCompensation/CommissionAdjustments.py:21` — `CommissionAdjustmentForm` exposes `status` in `Meta.fields`, allowing direct POST assignment of `approved` or `applied` states. Fix: Remove `"status"` from `CommissionAdjustmentForm.Meta.fields` and default new adjustments to `"draft"` in the create view.
- `templates/sales/incentivecompensation/boards/payout_processing.html:178` — Batch statement generation form hardcodes `<option value="1">Active Plan Envelope</option>` while `sales_commission_payout_processing` (`apps/sales/views/IncentiveCompensation/CommissionBoards.py:204`) omits `plans` from context, causing 404s when plan 1 does not belong to the tenant. Fix: In `sales_commission_payout_processing`, query `plans = CommissionPlan.objects.filter(tenant=request.tenant, status="active")`, pass to context, and render dynamically in the template dropdown.
- `apps/sales/views/IncentiveCompensation/CommissionBoards.py:236` — `sales_commission_what_if_calc` parses raw numeric GET parameters (`deal_amount`, `split_pct`, `current_attainment`) via `Decimal(...)` without `InvalidOperation` handling, `is_finite()` checks, or magnitude limits, triggering unhandled 500s on non-numeric or NaN input (L35). Fix: Wrap decimal conversions in `try...except (InvalidOperation, TypeError)` and verify `.is_finite()`, returning HTTP 400 on malformed input.
- `apps/sales/views/IncentiveCompensation/CommissionStatements.py:264` — `commission_statement_generate_batch` sets `net_payout=gross` instead of subtracting `draw_recovered`, storing inaccurate net settlement amounts because `Model.objects.create()` bypasses model `clean()`. Fix: Explicitly compute `net_payout = max(Decimal("0.00"), gross - draw_recovered)` before creation.
- `templates/sales/incentivecompensation/commissionplan/detail.html:30` — Detail views (`commissionplan`, `commissionearning:32`, `commissionstatement:31`, `commissionadjustment:32`) lack the actions sidebar contract, omitting a Back-to-List link and a status-conditional POST-only delete button with confirmation. Fix: Add a Back-to-List navigation link and a status-conditional POST-only delete form with `{% csrf_token %}` and confirm modal to each detail template.
- `templates/sales/incentivecompensation/commissionplan/list.html:211` — Pagination links drop active GET filter parameters (`tier_mode` in `commissionplan`, `plan` and `credit_type` in `commissionearning:227`, `payee` in `commissionadjustment:200`), causing page 2+ navigation to reset filters. Fix: Append `{% if request.GET.<field> %}&<field>={{ request.GET.<field> }}{% endif %}` for all filter fields to pagination links.

### Minor
- `templates/sales/incentivecompensation/commissionplan/list.html:164` — Status badge fallbacks in `{% else %}` blocks hardcode static badges (`Archived`, `Draft`) instead of rendering `{{ obj.get_status_display }}` across list, detail, and board templates. Fix: Render `<span class="badge badge-slate">{{ obj.get_status_display }}</span>` in the `{% else %}` branch.
- `templates/sales/incentivecompensation/boards/adjustment_workbench.html:142` — Negative clawback formatting uses string slicing (`slice:"1:"`) instead of arithmetic absolute value or currency formatting. Fix: Format negative amounts with standard currency filters.
- `apps/sales/management/commands/seed_sales.py:93` — Command help text states "Seed Sales 8.1, 8.2, 8.3, 8.4, 8.5, and 8.6 data idempotently", omitting 8.7 through 8.10. Fix: Update help string to reference 8.1 through 8.10.

### Done well
- Multi-tenancy and data isolation are cleanly implemented across all 4 models (`CommissionPlan`, `CommissionEarning`, `CommissionStatement`, `CommissionAdjustment`), forms, views, and migration `0019`. Model `clean()` methods rigorously validate tenant isolation on every domain foreign key and User foreign key.
- Ownership rulings L29/L36/L37 are strictly followed, reusing `crm.Opportunity`, `crm.SalesQuota`, `sales.QuotaPlan`, `scm.SalesOrder`, `accounting.Currency`, `accounting.ExchangeRate`, and `accounting.PayrollRun` without creating redundant spine tables.

---

## 2. Architecture & Exploration Review (`explorer`)

### Verdict
Commit after fixing Critical + Important.

### Critical
- `apps/sales/views/IncentiveCompensation/CommissionStatements.py:177` & `196` — `commission_statement_approve` and `commission_statement_lock` lack `@tenant_admin_required` / manager authorization, permit self-approval by payees (`obj.payee == request.user`), and fail to check status state machine preconditions (e.g. approving an already locked/paid statement, or locking a non-approved statement).
- `apps/sales/views/IncentiveCompensation/CommissionAdjustments.py:167` — `commission_adjustment_resolve_dispute` lacks authorization checks and allows payees to self-resolve their own disputes.
- `apps/sales/views/IncentiveCompensation/CommissionEarnings.py:145` & `175` — `commission_earning_edit` and `commission_earning_delete` do not prevent editing or deletion of earnings that are `paid` or attached to a `locked`/`paid` statement.
- `apps/sales/models/IncentiveCompensation/CommissionAdjustments.py:155` & `CommissionEarnings.py:210` — Cross-payee relational leakage: `CommissionAdjustment.clean()` does not verify that `self.earning.payee == self.payee` or `self.statement.payee == self.payee` when linked; similarly, `CommissionEarning.clean()` does not verify `self.statement.payee == self.payee`.

### Important
- `templates/sales/incentivecompensation/boards/payout_processing.html:178` & `apps/sales/views/IncentiveCompensation/CommissionBoards.py:204` — `sales_commission_payout_processing` omits `plans` from context, while the template has a hardcoded `<option value="1">Active Plan Envelope</option>` fallback which breaks multi-tenancy. Context must provide `plans = CommissionPlan.objects.filter(tenant=request.tenant, status="active")`.
- `apps/sales/views/IncentiveCompensation/CommissionStatements.py:264` — `commission_statement_generate_batch` creates statements bypassing draw deductions (`net_payout = gross` instead of `max(Decimal('0.00'), gross - draw_recovered)`).
- `apps/sales/views/IncentiveCompensation/CommissionBoards.py:236` — `sales_commission_what_if_calc` parses raw numeric GET parameters (`deal_amount`, `split_pct`, `current_attainment`) via `Decimal(...)` without `InvalidOperation` handling, `is_finite()` checks, or magnitude limits, risking 500s on bad inputs (L35).
- `apps/sales/forms/IncentiveCompensation/CommissionStatements.py:20` & `CommissionAdjustments.py:21` — Exposing `status` in `Meta.fields` allows direct POST manipulation of lifecycle states.
- `templates/sales/incentivecompensation/commissionplan/detail.html:30` (and `commissionearning`, `commissionstatement`, `commissionadjustment`) — Detail views omit Back-to-List link and status-guarded POST-only delete button with modal confirmation.
- `templates/sales/incentivecompensation/commissionplan/list.html:211` — Active filter GET parameters are dropped in pagination links across list templates.
- `apps/sales/forms/IncentiveCompensation/CommissionAdjustments.py:44` — `CommissionDisputeTicketForm` is defined but unused across views.

### Minor
- Status badge fallbacks use hardcoded text instead of `{{ obj.get_status_display }}`.
- Negative clawback formatting uses string slicing in `adjustment_workbench.html:142`.
- Command help text in `seed_sales.py:93` omits 8.7-8.10.

### Done well
- Backend package structure strictly adheres to the 4-layer architecture (`models`, `forms`, `views`, `urls`).
- Zero duplicate spine models declared; full reuse of `crm.Opportunity`, `crm.SalesQuota`, `scm.SalesOrder`, `accounting.Currency`, `accounting.ExchangeRate`, `accounting.PayrollRun` (L29/L36/L37).
- `LIVE_LINKS["8.10"]` in `apps/core/navigation.py` accurately represents all 5 NavERP.md 8.10 bullets with 0 dead links.
- All 17 templates present on disk and correctly aligned with views.

---

## 3. Frontend & Template Review (`frontend-reviewer`)
*Pending review run...*

---

## 4. Performance & Query Review (`performance-reviewer`)
*Pending review run...*

---

## 5. QA & Runtime Verification Review (`qa-smoke-tester`)
*Pending review run...*

---

## 6. Security & Multi-Tenancy Review (`security-reviewer`)
*Pending review run...*

---

## Deduplicated & Prioritized Action Items
*To be compiled after all 6 passes...*
