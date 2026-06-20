---
name: accounting
description: Work on the Accounting & Finance module (Module 2 — 2.1 dashboard, 2.2 General Ledger, 2.3 Accounts Payable, 2.4 Accounts Receivable, 2.5 Cash Management, plus advanced 2.6 Fixed Assets, 2.7 Cost Allocation, 2.8 Payroll, 2.9 Project/Job Costing, 2.10 Multi-Entity/Intercompany, 2.11 Tax, 2.12 Reporting/Balance-Sheet/P&L, 2.13 Budgeting, 2.14 Audit Controls, 2.15 Integration). Use when the user asks to add/change/debug anything under apps/accounting or templates/accounting, extend the seed_accounting seeder, touch accounting sidebar wiring (LIVE_LINKS 2.1–2.15), or invokes /accounting.
---

# Accounting & Finance (Module 2)

Tenant-scoped double-entry financial ledger. App path **`apps/accounting`**, templates **`templates/accounting/`**, URL prefix **`/accounting/`**, `app_name = "accounting"`.

## Architecture — this module OWNS the GL spine (lesson L28)
The unified-core spine (`apps/core`) has **no** financial ledger. `apps/accounting` therefore **builds and owns** the GL ledger spine; later modules (Inventory/Procurement/Sales/Assets) FK into `accounting.*` by string, exactly as they FK into `core.*`. It REUSES from core: `core.Party`/`core.PartyRole` (vendors/customers are *roles on a Party* — `VendorProfile`/`CustomerProfile` are thin OneToOne extensions, never new tables), `core.OrgUnit` (GL cost-centre on a journal line), `core.Document` (bill attachment), `core.utils.next_number`/`write_audit_log`, `core.decorators.tenant_admin_required`, `core.crud.*`, `core.forms.TenantModelForm`.

## Double-entry invariants (enforced at model + view layer)
1. A `JournalEntry` posts only when `sum(debit) == sum(credit)` and > 0 (`journal_entry_post`).
2. A posted/void JE is **immutable** (`JournalEntry.is_locked`) — correct via a *reversal* (`reversal_of`), never edit/delete. Same lock on paid/void Invoice/Bill, confirmed/void Payment.
3. `GLAccount` stores **no** balance — `GLAccount.balance()` aggregates posted lines on demand.
4. Posting into a non-open `FiscalPeriod` is blocked.
5. `Invoice`/`Bill` `subtotal/tax_total/total` are recomputed from lines (`recalc_totals()`), never on the form. Status is **not** user-editable — it advances via actions (`invoice_post`, `bill_approve`) and `recompute_payment_status()` (derives partial/paid from *confirmed* allocations).

## Models (`apps/accounting/models.py`) — 18 tables
Abstract bases: `TenantOwned` (tenant FK + timestamps), `TenantNumbered(TenantOwned)` (+ auto per-tenant `number` via `next_number`, 5-retry on collision — mirrors `apps/crm`).

**2.2 General Ledger**
- `Currency` — **global** (no tenant FK), ISO-4217 `code`/`name`/`symbol`/`is_active`.
- `ExchangeRate` — tenant; `currency`, `rate_date`, `rate`, `source`; `unique_together(tenant,currency,rate_date)`.
- `GLAccount` — Chart of Accounts; `code`, `name`, `account_type` (asset/liability/equity/income/expense), `normal_balance` (auto-set in `save()`, editable=False), self-FK `parent`, `is_active`; `unique_together(tenant,code)`; `balance()` derived.
- `FiscalPeriod` — `name`, `period_type`, `start_date`/`end_date`, `status` (open/closed/locked), `closed_by`/`closed_at` (system-set). `is_open` prop.
- `JournalEntry` [**JE-**] — `entry_type`, `status` (draft/pending_approval/posted/void), `fiscal_period`, `entry_date`, `reference`, `reversal_of` (self, editable=False), `created_by`/`approved_by`/`posted_at` (system-set). `is_locked`, `totals()`, `is_balanced()`.
- `JournalLine` — child of JE (no own tenant; inherits via `entry`); `gl_account` (PROTECT), `debit`/`credit`, `party`, `org_unit`, `currency`, `amount_foreign`, `exchange_rate`. `clean()` enforces debit XOR credit.

**2.3 AP + 2.4 AR shared masters**
- `PaymentTerm` — `name`, `days_due`, `discount_pct`, `discount_days`, `is_active`.
- `VendorProfile` — OneToOne on `core.Party`; `payment_terms`, `default_expense_account`, `currency`, `is_1099`, `is_active`, `notes`.
- `CustomerProfile` — OneToOne on `core.Party`; `payment_terms`, `credit_limit`, `ar_account`, `currency`, `credit_on_hold`, `is_active`.

**2.4 AR**
- `Invoice` [**INV-**] — `kind` (invoice/credit_note), `party` (PROTECT customer), `payment_terms`, `issue_date`/`due_date`, `status` (draft/sent/partial/paid/void), `currency`, `journal_entry` (system-set), `subtotal/tax_total/total` (derived). `OPEN_STATUSES=(sent,partial)`. `is_locked`, `recalc_totals()`, `amount_paid()` (confirmed only), `balance_due()`, `recompute_payment_status()`.
- `InvoiceLine` — `description`, `quantity`, `unit_price`, `tax_rate_pct`, `line_total` (derived in `save()`), `gl_account` (income).

**2.3 AP**
- `Bill` [**BILL-**] — `party` (PROTECT vendor), `payment_terms`, `bill_date`/`due_date`, `status` (draft/pending_approval/approved/partial/paid/void), `currency`, `journal_entry`, `subtotal/tax_total/total`, `approved_by` (system-set), `document` (core.Document). `OPEN_STATUSES=(approved,partial)`.
- `BillLine` — like InvoiceLine, `gl_account` = expense.

**2.3+2.4 Payments**
- `Payment` [**PAY-**] — `direction` (in/out), `party` (PROTECT), `bank_account` (PROTECT), `payment_method`, `payment_date`, `amount`, `currency`, `status` (draft/confirmed/void), `journal_entry`. `is_locked`, `allocated_total()`, `unallocated()`. NOTE: defined after `BankAccount` (FK ordering).
- `PaymentAllocation` — child of Payment (no own tenant); `invoice` XOR `bill`, `allocated_amount`, `discount_taken`. `clean()` enforces exactly one target.

**2.5 Cash**
- `BankAccount` — `name`, `account_number_last4` (last 4 ONLY), `bank_name`, `currency`, `gl_account`, `opening_balance`/`_date`, `is_active`. `current_balance()` derived.
- `BankTransaction` — `bank_account`, `transaction_date`, `description`, `amount`, `direction` (credit/debit), `source` (manual/csv_import/bank_feed — editable=False on form), `status` (editable=False), `external_ref` (dedupe key).
- `ReconciliationMatch` — `bank_transaction`, `payment` or `journal_line`, `matched_by` (system), `matched_at`, `is_confirmed`.

## URLs / routes (`apps/accounting/urls.py`, namespace `accounting:`)
Per CRUD model: `<base>_list / _create / _detail / _edit / _delete`. Bases: `glaccount`, `fiscal_period`, `journal_entry`, `currency`, `exchange_rate`, `payment_term`, `vendor_profile`, `bill`, `customer_profile`, `invoice`, `payment`, `allocation`, `bank_account`, `bank_transaction`, `reconciliation`.
**Custom actions (POST-only, `@tenant_admin_required` unless noted):** `fiscal_period_close`, `journal_entry_post`, `journal_entry_void`, `bill_approve`, `invoice_post`, `payment_confirm`, `payment_void`, `reconciliation_confirm`, `bank_transaction_import_csv` (GET form + POST upload, `@login_required`).
**Reports / dashboard (GET, `@login_required`):** `accounting_dashboard` (+ alias `dashboard`), `trial_balance`, `ar_aging`, `ap_aging`, `gl_account_ledger` (arg `account_pk`).

## Templates (`templates/accounting/`, 51 files)
Extend `base.html`, design-system classes only (`.card/.btn/.badge badge-green|red|amber|info|muted|slate/.stat-card/.detail-grid/.form-grid/.filter-bar/.table-actions/.empty-state`). Lists: GET filter-bar reflecting `request.GET` + Actions column + `{% include "partials/pagination.html" %}`. Context contract (from `core.crud`): list → `object_list`/`page_obj`/`q`; detail/edit → `obj`; forms → `form`/`is_edit` (+ `formset` for JE/Invoice/Bill). `dashboard.html` uses `json_script` + Chart.js (mirror `crm/overview.html`). Admin-gated action buttons are wrapped `{% if request.user.is_superuser or request.user.is_tenant_admin %}`.

## Seeder
`venv\Scripts\python.exe manage.py seed_accounting` — idempotent (skips a tenant that already has a `GLAccount`). Per tenant: 4 global currencies + FX rates, ~18-account CoA, a closed prior + open current `FiscalPeriod`, Net-30 + 2/10-Net-30 terms, an Operating bank account, a `VendorProfile`/`CustomerProfile` (reusing `core.Party` vendor/customer roles), 2 invoices (partial + draft), 2 bills (approved + draft), a confirmed payment with a balanced Dr-Cash/Cr-AR JE + allocation, 3 posted manual JEs, 3 bank transactions, 1 reconciliation. Login as `admin_acme` / `password123` (the `admin` superuser has no tenant → no data).

## Conventions & gotchas
- **`Currency` is global** (no tenant FK) — its CRUD is `@tenant_admin_required`; all other models tenant-scope every queryset via `core.crud` helpers.
- **Child tables** `JournalLine`/`InvoiceLine`/`BillLine`/`PaymentAllocation` have no own tenant — they inherit it via the parent; views fetch the parent tenant-scoped, and `allocation_*` views filter `payment__tenant`.
- **`ReconciliationMatchForm` scopes `journal_line` manually** (`entry__tenant`) because `JournalLine` has no direct tenant field — `TenantModelForm` can't auto-scope it.
- **Mass-assignment**: `status` is NOT on Invoice/Bill/JE forms; `source` is NOT on the BankTransaction form; numbers/derived totals/`normal_balance`/`*_by`/`*_at`/`journal_entry`/`reversal_of` are `editable=False`.
- **FK ordering** in models.py: define `BankAccount` before `Payment`.
- **CSV import**: `.csv` only, ≤5 MB; dedupes on `external_ref` in one query, `bulk_create` inside `atomic()`.

## Common tasks
- **Add a field to a model** → edit `models.py`; add to the relevant ModelForm `fields` (NOT if system-set/derived); `makemigrations accounting` + `migrate`; surface in the detail/list/form template.
- **Add a new model + CRUD** → model (TenantOwned/TenantNumbered) → `ModelForm` → views (reuse `crud_list/create/edit/delete` + a custom `_detail`) → 5 url names → `admin.py` → 3 templates → `seed_accounting` → migrate.
- **Add a list filter** → pass the choices/queryset in the view's `crud_list(extra_context=...)`; add the `<select>` to the list template (string compare `request.GET.x == val`; FK compare `obj.pk|stringformat:"d"`; bool `value="True"/"False"`).
- **Extend the seeder** → add to `_seed_tenant` guarded by the CoA-exists check; use balanced `_posted_je(...)` legs for any JE.

## Advanced sub-modules 2.6–2.15 (`models_advanced.py` / `views_advanced.py` / `forms_advanced.py`)
A second pass (migrations `0002` + index `0003`) added 14 accounting-owned models that REUSE the GL spine and
`core.OrgUnit` (the cost-centre / department / legal-entity / consolidation dimension — no new Entity table). New
code lives in `*_advanced.py` files imported into `models.py`/`urls.py`/`admin.py`; templates are in the same
`templates/accounting/` dir. Six **balanced-JE posting actions** (all `@tenant_admin_required`, POST-only) build a
balanced `JournalEntry` via the local `views_advanced._post_journal_entry(tenant, user, desc, legs)` helper
(`legs=[(gl_account, debit, credit, party, org_unit)]`, refuses to post unless Σdebit==Σcredit>0).

- **2.6 Fixed Assets** — `FixedAsset` [FA-] (cost/salvage/useful_life/method straight_line|declining_balance|units,
  derived `book_value()`/`period_depreciation()`; `accumulated_depreciation` advanced by the action) + action
  `fixed_asset_depreciate` (Dr depreciation expense / Cr accumulated, capped at depreciable base); `AssetDisposal`
  [DISP-] + action `asset_disposal_post` (Dr cash+accum / Cr cost ± gain/loss; sets asset `disposed`).
- **2.7 Cost Allocation** — `CostAllocation` [CALLOC-] + `cost_allocation_post` (Dr target / Cr source).
- **2.8 Payroll** — `PayrollRun` [PRUN-] (aggregate totals; `net_pay` DERIVED = gross−employee_tax−deductions so the
  JE balances) + `payroll_run_post` (Dr wages+tax+benefits expense / Cr cash + taxes-payable + deductions-payable).
- **2.9 Project/Job Costing** — `Project` [PRJ-] (budget vs derived actuals) + `JobCostEntry` [JCE-] +
  `job_cost_entry_post` (cost: Dr expense/Cr cash; revenue: Dr cash/Cr income).
- **2.10 Multi-Entity** — `IntercompanyTransaction` [ICT-] + `intercompany_post` (Dr due-from on lender org / Cr
  due-to on borrower org) + `intercompany_toggle_eliminated` (admin; the `eliminated` flag is NOT on the form).
- **2.11 Tax** — `TaxCode` (rate master) + `TaxReturn` [TAXR-] (filing record, no JE; edit/delete admin-gated).
- **2.12 Reporting** — report views (no CRUD model): `balance_sheet`, `profit_and_loss` (both read one grouped
  `_account_balances(tenant)` aggregate over posted lines) + `ScheduledReport` config model.
- **2.13 Budgeting** — `Budget` [BUD-] + `BudgetLine` (standalone CRUD under a budget; `budget_line_*` views redirect
  to the parent detail) + `budget_variance` report (budget vs posted actuals).
- **2.14 Audit & Controls** — `InternalControl` [CTRL-] (SOX control + last test result); audit trail reuses `core.AuditLog`.
- **2.15 Integration** — `IntegrationConfig` (provider/category/status); the API secret is NEVER stored — only
  prefix + SHA-256 hash (L20/L25); `integration_rotate_key` (admin) reveals the plaintext once via a pop-once
  session key; `integration_edit`/`delete` are admin-gated; the form has no key field.

Advanced conventions: status fields owned by posting actions are OFF the forms (AssetDisposal/CostAllocation/
PayrollRun/JobCostEntry); `FixedAssetForm` drops the `disposed` choice; posted records are immutable (`is_locked`);
the advanced demo data is seeded DRAFT (via `_seed_advanced`, self-guarded on `FixedAsset`) so you can exercise the
post actions. Account-resolution heuristic: posting actions use model FKs where set, else `_first_account(tenant,
type, code_prefix)` (e.g. depreciation→1600/1690/6400, payroll→6100/1000/2200/2100) — per-tenant configurable
control accounts are the documented future migration.

## Sidebar wiring (`apps/core/navigation.py` LIVE_LINKS)
Keys **`"2.1"`–`"2.15"`** map NavERP.md bullets → routes. 2.1 dashboard/trial-balance; 2.2 GL; 2.3 AP; 2.4 AR; 2.5
cash (see above). Advanced: 2.6 fixed_asset/asset_disposal; 2.7 cost_allocation; 2.8 payroll_run; 2.9 project/
job_cost_entry; 2.10 `core:orgunit_list` + intercompany; 2.11 tax_code/tax_return; 2.12 balance_sheet/profit_and_loss/
scheduled_report + dashboard; 2.13 budget/budget_variance; 2.14 internal_control + `core:auditlog_list`/`core:document_list`/
`accounts:role_list`; 2.15 integration. Don't edit `MODULE_CATALOG`.

## Deferred (later passes)
Bank feeds (Plaid), OCR bill capture, AI cash-flow forecast, customer/vendor portal, allocation-rules engine, 1099
generation, recurring JE scheduler, dunning auto-send, FX revaluation, invoice/bill **void** actions, per-tenant
configurable AR/AP/depreciation control accounts (posting picks the first matching code-prefix today),
gl_account_ledger pagination. Advanced deferred: live integration sync (Plaid/Avalara/Stripe API calls), DRF REST
API, Celery scheduled-report delivery, parallel tax-depreciation books, full WBS/earned-value, currency-translation
(CTA) run, XBRL/EDGAR, and the FK migration onto Inventory (Module 5)/HRM (Module 3)/Projects (Module 7) masters
when those modules land.
