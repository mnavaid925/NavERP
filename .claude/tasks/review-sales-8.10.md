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

### Verdict
Changes Requested (Commit after fixing Critical + Important).

### Critical
- `templates/sales/incentivecompensation/boards/payout_processing.html:174-180` — Hardcoded Plan Option `<option value="1">Active Plan Envelope</option>` in Batch Statement Generator while `sales_commission_payout_processing` (`CommissionBoards.py:204`) omits `plans` from context, causing 404s or invalid tenant submissions. Fix: Query `plans = CommissionPlan.objects.filter(tenant=request.tenant, status="active")` in view and loop dynamically `{% for p in plans %}<option value="{{ p.pk }}">{{ p.name }}</option>{% endfor %}`.
- `templates/sales/incentivecompensation/commissionstatement/detail.html:104, 193`, `commissionadjustment/list.html:136`, `commissionadjustment/detail.html:62` — Double minus formatting bug on negative amounts: `{% if obj.amount >= 0 %}+${{ obj.amount|floatformat:2 }}{% else %}-${{ obj.amount|floatformat:2 }}{% endif %}` renders `-$ -250.00` because `|floatformat:2` already includes the negative sign. Fix: Render `${{ obj.amount|floatformat:2 }}` in the negative branch or format cleanly.

### Important
- `templates/sales/incentivecompensation/commissionadjustment/list.html:41` & `boards/adjustment_workbench.html:32` — Design system violation: illegal `stat-icon red` (L33). Stat icons must be one of `blue/green/orange/purple/slate`. Fix: Change `stat-icon red` to `stat-icon slate` or `stat-icon orange`.
- `templates/sales/incentivecompensation/commissionplan/detail.html:29`, `commissionearning/detail.html:31`, `commissionstatement/detail.html:30`, `commissionadjustment/detail.html:31` — CRUD Incompleteness: Missing POST-Delete form and Back-to-List button on all 4 detail pages. Fix: Add Back to List link and POST delete button with CSRF token and confirm dialog.
- `templates/sales/incentivecompensation/commissionplan/list.html:211, 215` (drops `tier_mode`), `commissionearning/list.html:228, 231` (drops `plan`, `credit_type`), `commissionadjustment/list.html:200, 203` (drops `payee`) — Active filter GET parameters are dropped during pagination navigation. Fix: Append `{% if request.GET.<param> %}&<param>={{ request.GET.<param> }}{% endif %}` to pagination links.

### Minor
- `templates/sales/incentivecompensation/boards/adjustment_workbench.html:142` — Brittle string slicing `-${{ c.amount|floatformat:2|slice:"1:" }}` drops first digit if amount is non-negative. Fix: Avoid string slicing on numbers.
- `templates/sales/incentivecompensation/boards/earnings_dashboard.html` & `commissionstatement/list.html` — Hardcoded `$` currency symbol across multi-currency boards. Fix: Use currency code/symbol context.

### Done well
- Zero multiline `{# ... #}` comment leaks (L2) across all 17 templates.
- Strict badge color naming compliance: approved color-named classes (`badge-green`, `badge-amber`, `badge-red`, `badge-info`, `badge-slate`, `badge-muted`) with zero `-success/-danger/-warning`.
- Comprehensive None-safe foreign key lookups (L10) for nullable relationships (`opportunity`, `sales_order`, `sales_quota`, `owner`, `payroll_run`, `statement`, `approved_by`).
- Safe PK dropdown comparisons using `|stringformat:'d'`.
- Responsive design with `.table-wrap`, empty states with `.empty-state`, and full accessibility attributes (`aria-label`, `title`).

---

## 4. Performance & Query Review (`performance-reviewer`)

### Verdict
Needs Improvement (Commit after fixing Critical + Important).

### Critical
- `apps/sales/views/IncentiveCompensation/CommissionBoards.py:90-107` — $O(N)$ Per-Rep Aggregation Loop in `sales_commission_earnings_dashboard`: loops over all active tenant reps running `.exists()` and 4 separate aggregates per rep ($1 + 2N$ queries). Fix: Replace loop with a single grouped aggregation `earnings.values('payee__id', 'payee__first_name', 'payee__last_name', 'payee__email').annotate(volume=Sum('credited_volume'), gross=Sum('gross_commission'), spif=Sum('spif_amount'), attainment=Avg('attainment_pct_at_close'))`.
- `apps/sales/views/IncentiveCompensation/CommissionStatements.py:228-248` — $O(R)$ Query Explosion in `commission_statement_generate_batch`: executes 4 separate `.aggregate()` calls on unattached earnings per rep ($5 \times R$ read queries). Fix: Consolidate the 4 calls into a single `.aggregate(vol=Sum(...), base=Sum(...), spif=Sum(...), gross=Sum(...))` per rep.
- `apps/sales/views/IncentiveCompensation/CommissionBoards.py:122` & `templates/sales/incentivecompensation/boards/earnings_dashboard.html:175` — Template N+1 query leak on `plan.currency.code`: `plans` lacks `.select_related('currency')`, triggering a separate query per plan rendered in the dropdown. Fix: Add `.select_related('currency')` to `plans`.
- `apps/sales/views/IncentiveCompensation/CommissionPlans.py:87-91` & `templates/sales/incentivecompensation/commissionplan/detail.html:195` — Template N+1 on `earn.deal_currency.code`: `recent_earnings` omits `deal_currency` from `.select_related()`. Fix: Update view to `.select_related('payee', 'opportunity', 'deal_currency')`.

### Important
- `apps/sales/views/IncentiveCompensation/CommissionBoards.py:244` — Missing `select_related('currency')` in `sales_commission_what_if_calc`, causing an extra DB query when accessing `plan.currency.code` on every AJAX simulation. Fix: Add `.select_related('currency')`.
- `apps/sales/views/IncentiveCompensation/CommissionBoards.py` (lines 34, 110, 215) & list views (`CommissionPlans.py:50`, `CommissionEarnings.py:55`, `CommissionStatements.py:50`, `CommissionAdjustments.py:51`) — Fragmented KPI aggregate queries: firing multiple sequential `.aggregate()` and `.count()` calls instead of a single batched query using `Count('id', filter=Q(...))` and `Sum(...)`. Fix: Combine KPI queries into single batched `.aggregate()` statements.
- `apps/sales/models/IncentiveCompensation/*.py` — Missing compound database indexes on high-traffic filter combinations: `CommissionEarning` missing `(tenant, status)`, `(tenant, plan)`, `(tenant, statement)`; `CommissionAdjustment` missing `(tenant, status)`, `(tenant, statement)`; `CommissionStatement` missing `(tenant, plan)`. Fix: Add indexes to model `Meta.indexes`.

### Minor
- `apps/sales/models/IncentiveCompensation/CommissionEarnings.py:185` — Chained FK traversal in `__str__` accesses `self.deal_currency.code`. If stringified without `deal_currency` prefetched, triggers an extra query.
- `apps/sales/views/IncentiveCompensation/CommissionBoards.py:36-41` — `distinct().count()` on payee values in plan hub can be heavy on large tables.

### Done well
- Consistent pagination enforcement with `Paginator(qs, 15)` across all list views.
- Comprehensive foreign key pre-fetching on core list and detail views (`commission_earning_list` selects all 6 FKs).
- Zero template-level manager queries (`.all()` or `.count()` in loops) across all 17 templates.
- Strict multi-tenant isolation with `tenant=request.tenant` on all ORM queries.

---

## 5. QA & Runtime Verification Review (`qa-smoke-tester`)

### Verdict
FAIL (Critical Runtime Defects Found — Commit after fixing Critical + Important).

### Critical
- `apps/sales/views/IncentiveCompensation/CommissionPlans.py` (lines 118, 147, 175), `CommissionEarnings.py` (lines 118, 150, 178), `CommissionStatements.py` (lines 122, 154, 183, 201, 283), `CommissionAdjustments.py` (lines 107, 144, 186, 207) — `write_audit_log` Signature Mismatch: Developers passed strings (e.g. `"sales.CommissionPlan"`) as the 2nd argument instead of the model instance `obj`. In `apps/core/utils.py`, `write_audit_log` attempts `ContentType.objects.get_for_model(obj.__class__)`, crashing with `AttributeError: type object 'str' has no attribute '_meta'`. This causes a systematic HTTP 500 on ALL write/action operations (create, edit, delete, approve, lock, dispute resolution) across all 4 models. Fix: Pass the actual model instance `obj` (or `None` with `tenant=request.tenant`) to `write_audit_log`.
- `apps/sales/forms/IncentiveCompensation/CommissionPlans.py` & `CommissionPlans.py:160-164` — `ValueError: 'CommissionPlanForm' has no field named 'tiers_config'`: Model `clean()` raises `ValidationError({'tiers_config': ...})`, but `CommissionPlanForm` declared the field as `tiers_json`. When Django's `_post_clean` routes the error to form fields, it raises a fatal `ValueError` (HTTP 500) instead of displaying the validation error. Fix: Align the field name in the form to `tiers_config` or remap errors in form `clean()`.

### Important
- `apps/sales/views/IncentiveCompensation/CommissionBoards.py:236-238` — `decimal.InvalidOperation` on Malformed What-If Calculator Query Parameters: Parameters `deal_amount`, `split_pct`, and `current_attainment` are parsed with `Decimal(...)` without `try...except (InvalidOperation, TypeError, ValueError)`. Submitting `?deal_amount=abc` triggers an unhandled HTTP 500 instead of HTTP 400. Fix: Wrap in exception handling and return `JsonResponse({'ok': False, 'error': 'Invalid numeric parameters'}, status=400)`.

### Minor
- `apps/sales/views/IncentiveCompensation/CommissionBoards.py:236` — `deal_amount=NaN` outputs `{"projected_gross": NaN}` in JSON, violating RFC 8259. Fix: Check `.is_finite()` on parsed decimals.
- `apps/sales/views/IncentiveCompensation/CommissionStatements.py:223` — `commission_statement_generate_batch` lacks type checking on `plan_id` before querying `pk=plan_id`, causing `ValueError` if non-numeric string is submitted. Fix: Validate `plan_id.isdecimal()`.

### Done well
- Multi-Tenant IDOR Isolation: 100% pass across all 18 cross-tenant test cases (detail, edit, delete, actions, simulator) cleanly returning HTTP 404 (or 405 on blocked GET).
- All 5 board views returned 200 OK with zero unrendered template leaks.
- All 4 model list views handle arbitrary filters, valid choices, junk query strings, and pagination safely with 200 OK.
- Action and deletion endpoints enforce `@require_POST`, returning 405 on GET.

---

## 6. Security & Multi-Tenancy Review (`security-reviewer`)

### Verdict
FAIL / CONDITIONAL PASS REQUIRED (Commit after fixing Critical + Important).

### Critical
- `apps/sales/views/IncentiveCompensation/CommissionStatements.py:176-192` — Privileged AuthZ & Self-Approval in Statement Approval: `commission_statement_approve` lacks `@tenant_admin_required` or manager gating, and permits sales rep payees to self-approve their own statements (`obj.payee == request.user`). Fix: Add `@tenant_admin_required`, block self-approval with `if obj.payee == request.user and not request.user.is_superuser: return HttpResponseForbidden(...)`, and guard status `if obj.status not in ("draft", "under_review"): return redirect(...)`.
- `apps/sales/views/IncentiveCompensation/CommissionAdjustments.py:166-195` — Privileged AuthZ & Self-Approval in Dispute Ticket Resolution: `commission_adjustment_resolve_dispute` lacks authorization gating and allows sales rep payees/claimants to self-approve their own dispute claims. Fix: Add `@tenant_admin_required` and block self-approval `if (obj.payee == request.user or obj.requested_by == request.user) and not request.user.is_superuser: return HttpResponseForbidden(...)`.
- `apps/sales/forms/IncentiveCompensation/CommissionStatements.py`, `CommissionAdjustments.py`, `CommissionEarnings.py` — Mass Assignment of `status`: Exposing `status` in `Meta.fields` allows direct POST manipulation of lifecycle states (`approved`, `locked`, `paid`). Fix: Remove `status` from `Meta.fields` in all 3 forms and manage state transitions via action endpoints.
- `apps/sales/views/IncentiveCompensation/CommissionStatements.py:194, 212` — Missing Privileged AuthZ on Statement Locking & Batch Generation: `commission_statement_lock` and `commission_statement_generate_batch` allow any logged-in user to finalize statements and execute tenant-wide batch calculations. Fix: Add `@tenant_admin_required` to both endpoints.

### Important
- `apps/sales/views/IncentiveCompensation/CommissionEarnings.py:143-170, 172-188` — Missing Status Progression Guards on Paid Earnings: Paid earnings or earnings attached to locked/paid statements can be modified or deleted. Fix: Guard edit and delete views against mutating records in `approved`, `paid`, or `clawed_back` status.
- `apps/sales/views/IncentiveCompensation/CommissionBoards.py:234-275` — Unhandled `Decimal` Exceptions & NaN/Infinity in What-If Simulator: Parameters parsed with `Decimal(...)` without exception handling or `.is_finite()` checks trigger 500s on `?deal_amount=abc` or `NaN`. Fix: Wrap in exception handling and return HTTP 400.
- `apps/sales/views/IncentiveCompensation/CommissionStatements.py:212-270` — Missing Audit Logging on Batch Statement Generation: Batch generation mutates statements and earnings across the tenant without writing an audit log. Fix: Add `write_audit_log`.
- `apps/sales/views/IncentiveCompensation/*.py` — Horizontal Information Disclosure & Rep Mutability: Regular reps can view and edit other reps' earnings and statements. Fix: Restrict non-admin queries and edit permissions to `payee=request.user`.

### Minor
- `apps/sales/views/IncentiveCompensation/CommissionStatements.py:249` — Unvalidated date string slicing in batch statement code generation. Fix: Parse dates with `datetime.date.fromisoformat`.
- `apps/sales/views/IncentiveCompensation/CommissionPlans.py:110` & `CommissionEarnings.py:110` — Unrestricted plan and manual earning creation. Fix: Restrict plan creation to admins/managers.

### Done well
- Strict multi-tenant scoping (`tenant=request.tenant`) across all querysets in models and boards.
- Double-layered foreign key cross-tenant rejection in both forms and model `clean()`.
- HTTP verb enforcement (`@require_POST`) and CSRF tokens across all action endpoints.
- Server-side deterministic waterfall calculations in model `clean()`.

---

## Deduplicated & Prioritized Action Items

### Critical (Must Fix Before Merge)
- [x] fixed — fix(sales): pass model instance to write_audit_log across 8.10 views **C1**: Fix `write_audit_log` signature across all 8.10 views (`CommissionPlans.py`, `CommissionEarnings.py`, `CommissionStatements.py`, `CommissionAdjustments.py`) by passing the model instance `obj` instead of string `"sales.<Model>"` to prevent systematic HTTP 500 crashes.
- [x] fixed — fix(sales): add authz, self-approval block, and status guard to commission_statement_approve **C2**: Add `@tenant_admin_required`, self-approval block (`obj.payee == request.user`), and status progression guard (`obj.status in ('draft', 'under_review')`) to `commission_statement_approve` in `CommissionStatements.py`.
- [x] fixed — fix(sales): add authz, status guard, and self-locking block to commission_statement_lock **C3**: Add `@tenant_admin_required`, status guard (`obj.status == 'approved'`), and payee self-locking block to `commission_statement_lock` in `CommissionStatements.py`.
- [x] fixed — fix(sales): add authz, self-approval block, and status guard to dispute resolution **C4**: Add `@tenant_admin_required`, self-approval block (`obj.payee == request.user or obj.requested_by == request.user`), and status guard (`obj.status == 'disputed'`) to `commission_adjustment_resolve_dispute` in `CommissionAdjustments.py`.
- [x] fixed — fix(sales): remove status from CommissionStatementForm, CommissionAdjustmentForm, CommissionEarningForm and templates **C5**: Remove `"status"` from `Meta.fields` in `CommissionStatementForm`, `CommissionAdjustmentForm`, and `CommissionEarningForm` to prevent mass assignment lifecycle bypass. Update templates to remove status input widgets.
- [x] fixed — fix(sales): remap tiers_config and spif_config validation errors to form fields **C6**: Fix `CommissionPlanForm` field name mapping: align field to `tiers_config` (or remap in form `clean()`) to prevent `ValueError: 'CommissionPlanForm' has no field named 'tiers_config'` on validation failure.
- [x] fixed — fix(sales): pass active plans to payout processing context and render dynamically **C7**: Fix hardcoded `<option value="1">` in `payout_processing.html:178` and pass `plans = CommissionPlan.objects.filter(tenant=request.tenant, status='active')` from `sales_commission_payout_processing` in `CommissionBoards.py`.
- [ ] **C8**: Fix double minus formatting bug (`-$ -250.00`) on negative amounts in `commissionstatement/detail.html:104, 193`, `commissionadjustment/list.html:136`, and `commissionadjustment/detail.html:62`.
- [ ] **C9**: Add `@tenant_admin_required`, `plan_id.isdecimal()` check, `net_payout = max(Decimal('0.00'), gross - draw_recovered)` calculation, and `write_audit_log` call to `commission_statement_generate_batch` in `CommissionStatements.py`.
- [ ] **C10**: Add status mutation guards to `commission_earning_edit`, `commission_earning_delete`, and `commission_adjustment_edit` preventing modification/deletion of records in `approved`, `paid`, or `clawed_back` status, or on locked statements.
- [ ] **C11**: Replace $O(N)$ rep aggregation loop in `sales_commission_earnings_dashboard` (`CommissionBoards.py:90-107`) with a single grouped `.values('payee').annotate(...)` query.
- [ ] **C12**: Add cross-payee validation in model `clean()`: ensure `CommissionAdjustment.earning.payee == self.payee` and `statement.payee == self.payee`, and `CommissionEarning.statement.payee == self.payee`.

### Important (High Priority Improvements)
- [ ] **I1**: In `sales_commission_what_if_calc` (`CommissionBoards.py:236-244`), wrap `Decimal(...)` parsing in `try...except (InvalidOperation, TypeError, ValueError)`, validate `.is_finite()`, enforce bounds, return HTTP 400 on error, and add `.select_related('currency')` to `plan`.
- [ ] **I2**: Replace illegal `stat-icon red` (L33) with `stat-icon slate` or `stat-icon orange` in `commissionadjustment/list.html:41` and `boards/adjustment_workbench.html:32`.
- [ ] **I3**: Add Back-to-List button and status-conditional POST-only delete button with CSRF and confirm dialog on all 4 detail templates (`commissionplan`, `commissionearning`, `commissionstatement`, `commissionadjustment`).
- [ ] **I4**: Preserve active filter GET parameters in pagination links across `commissionplan/list.html`, `commissionearning/list.html`, and `commissionadjustment/list.html`.
- [ ] **I5**: Fix template N+1 queries by adding `.select_related('currency')` in `sales_commission_earnings_dashboard`, and `.select_related('deal_currency')` in `commission_plan_detail`.
- [ ] **I6**: Consolidate fragmented KPI aggregate queries in boards and list views into batched `.aggregate()` calls.
- [ ] **I7**: Add composite database indexes `(tenant, status)`, `(tenant, plan)`, and `(tenant, statement)` to `CommissionEarning`, `CommissionAdjustment`, and `CommissionStatement`. Run `makemigrations` and `migrate`.
- [ ] **I8**: Enforce horizontal data scoping: non-admin users only view/edit their own payee records in list and detail views.
- [ ] **I9**: Clean up unused `CommissionDisputeTicketForm` in `CommissionAdjustments.py`.

### Minor (Clean-up & Polish)
- [ ] **M1**: Update badge fallback rendering to use `{{ obj.get_status_display }}` instead of hardcoded text.
- [ ] **M2**: Fix brittle string slicing `slice:"1:"` in `adjustment_workbench.html:142`.
- [ ] **M3**: Update `seed_sales.py:93` help string to include 8.7 through 8.10.
- [ ] **M4**: Use tenant currency or plan currency code instead of hardcoded `$` symbol in multi-currency templates.

