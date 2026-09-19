# Review Findings: Sub-module 7.15 Financial & Billing Management
Base Commit: `4fa0dd5365dffd1c988d4995b8239b4fab303ffc`

---

## Verdict
**REMEDIATION REQUIRED (5 CRITICAL, 14 IMPORTANT, 8 MINOR)**

All 6 specialist review agents (`code-reviewer`, `explorer`, `frontend-reviewer`, `performance-reviewer`, `qa-smoke-tester`, `security-reviewer`) have audited the codebase serially. Multi-tenancy isolation and foundational security are solid, but remediation is required for pagination/search bypass, concurrency in invoice creation, field naming in A/R aging, and N+1 query loops.

---

## Critical

- **[x] fixed — fix(projects): lock billing run with select_for_update in invoice generation**
  - **Location**: `apps/projects/views/FinancialBillingManagement/BillingRuns.py:151-220`
  - **Problem**: Billing run is fetched and checked outside `transaction.atomic()` without `select_for_update()`. Concurrent requests can create duplicate AR invoices and ledger lines for the same billing run.
  - **Fix**: Wrap in `transaction.atomic()`, fetch billing run using `select_for_update()`, and verify `status in ("draft", "approved")` inside the transaction lock.

- **[x] fixed — fix(projects): use object_list and page_obj paginator across financial billing list views and templates**
  - **Location**:
    - `templates/projects/financialbilling/ratecard/list.html:82, 155`
    - `templates/projects/financialbilling/billingrun/list.html:85, 167`
    - `templates/projects/financialbilling/revenueschedule/list.html:85, 179`
    - `templates/projects/financialbilling/paymentrecord/list.html:85, 183`
    - `apps/projects/views/FinancialBillingManagement/RateCards.py:39`
    - `apps/projects/views/FinancialBillingManagement/BillingRuns.py:48`
    - `apps/projects/views/FinancialBillingManagement/RevenueSchedules.py:49`
    - `apps/projects/views/FinancialBillingManagement/PaymentRecords.py:50`
  - **Problem**: Templates iterate over raw unpaginated querysets (`rate_cards`, `billing_runs`, etc.) from `extra_context` instead of `object_list` / `page_obj`, rendering all records and bypassing search filters (`?q=...`). In addition, pagination footers check `paginator.num_pages` instead of `page_obj.paginator.num_pages`, causing pagination controls to never render.
  - **Fix**: In templates, loop over `object_list` (or `page_obj`), change `paginator.num_pages` to `page_obj.paginator.num_pages`. In views, remove raw querysets from `extra_context`.

- **[x] fixed — fix(projects): use record.number and invoice.number in aging board**
  - **Location**: `templates/projects/financialbilling/aging.html:120, 124`
  - **Problem**: Line 120 accesses non-existent `row.record.record_number` instead of `row.record.number` (empty anchor link). Line 124 accesses non-existent `row.invoice.invoice_number` instead of `row.invoice.number` (all real invoices display fallback "INV-DRAFT").
  - **Fix**: Change to `row.record.number` and `row.invoice.number`.

- **[x] fixed — fix(projects): eliminate N+1 queries by bulk pre-calculating invoice balance due in ppr_list**
  - **Location**: `apps/projects/views/FinancialBillingManagement/PaymentRecords.py:24-25, 76-78`, `templates/projects/financialbilling/paymentrecord/list.html:104-105`, `templates/projects/financialbilling/paymentrecord/detail.html:85`
  - **Problem**:
    1. `select_related` omits `"accounting_invoice__currency"`, triggering 1 query per row.
    2. In-template `r.accounting_invoice.balance_due` executes `Invoice.balance_due()` SQL aggregate per row ($2N+1$ queries).
    3. `r.accounting_invoice.total_amount` accesses non-existent field (model has `total`), rendering blank.
  - **Fix**: Add `"accounting_invoice__currency"` to `select_related`. Pre-calculate invoice balance due / allocations in the view and attach to objects. Change `total_amount` to `total` in templates.

- **[x] fixed — perf(projects): replace per-project PnL queries with 3 bulk group-by aggregations**
  - **Location**: `apps/projects/views/FinancialBillingManagement/FinancialBoards.py:44-64`
  - **Problem**: Python loop over `target_projects` executes 4 separate `.aggregate()` SQL queries per project ($4N+1$ queries).
  - **Fix**: Replace per-project loop with 3 bulk queries using `.values("project_id").annotate(...)`.

---

## Important

- **[x] fixed — fix(projects): pass billing run tax_rate_pct to generated InvoiceLine items**
  - **Location**: `apps/projects/views/FinancialBillingManagement/BillingRuns.py:173-204`
  - **Problem**: `InvoiceLine` creation omits `tax_rate_pct=billing_run.tax_rate_pct`. Calling `invoice.recalc_totals()` sets line tax to 0% and zeroes out `tax_total`.
  - **Fix**: Pass `tax_rate_pct=billing_run.tax_rate_pct` when creating `InvoiceLine`.

- **[x] fixed — fix(core): align LIVE_LINKS 7.15 navigation targets with contract section 4**
  - **Location**: `apps/core/navigation.py:142-148`
  - **Problem**: Contract Section 4 maps 6 links: "Project Accounting & Cost Centers" -> `projects:prs_list`, "Payment Tracking & Reconciliation" -> `projects:ppr_list`, "Project P&L" -> `projects:financial_pnl`, "A/R Aging Dashboard" -> `projects:ar_aging`, "Rate Cards" -> `projects:rtc_list`, "Payment Records" -> `projects:ppr_list`.
  - **Fix**: Align `LIVE_LINKS["7.15"]` keys and route targets with Section 4 of the contract.

- **[x] fixed — fix(projects): re-export secondary financial billing forms in forms package**
  - **Location**: `apps/projects/forms/__init__.py`
  - **Problem**: Secondary forms (`BillingRunDispatchForm`, `RevenueScheduleRecognizeForm`, `PaymentPromiseForm`, `ContactLogForm`) defined in `FinancialBillingManagement/forms.py` are not re-exported.
  - **Fix**: Re-export them in `apps/projects/forms/__init__.py` and include in `__all__`.

- **[x] fixed — fix(projects): guard ppr_escalate against settled or written-off collection records**
  - **Location**: `apps/projects/views/FinancialBillingManagement/PaymentRecords.py:192-216`, `templates/projects/financialbilling/paymentrecord/detail.html:27-32`
  - **Problem**: View does not check if record is already settled/written_off or status resolved/closed; button displayed unconditionally in template.
  - **Fix**: Guard in view (`if record.stage in ("settled", "written_off") ...`) and conditionally hide button in template.

- **[x] fixed — perf(projects): precompute CCA posted expenses in bulk and add wbs_node to select_related**
  - **Location**: `apps/projects/views/FinancialBillingManagement/FinancialBoards.py:118-163`
  - **Problem**: Missing `wbs_node` in `select_related`, queries BAC/PV/AC/committed per CCA in loop.
  - **Fix**: Add `wbs_node` to `select_related`, precompute posted expenses across control accounts in bulk.

- **[x] fixed — perf(projects): pre-aggregate invoice allocations and aggregate outflows via DB Case/When**
  - **Location**: `apps/projects/views/FinancialBillingManagement/FinancialBoards.py:222-227, 313-321, 332-341`
  - **Problem**: Calling `inv.balance_due()` in loop across invoices. Outflows pull all commitments into Python memory.
  - **Fix**: Pre-aggregate invoice allocations in a single query; aggregate outflows directly in DB using conditional `Case/When`.

- **[x] fixed — fix(projects): align stage badge choices with ProjectPaymentRecord.STAGE_CHOICES in aging board**
  - **Location**: `templates/projects/financialbilling/aging.html:148-161`
  - **Problem**: Checks `escalated`, `disputed`, `legal_hold` while omitting `current`, `overdue`, and `in_dispute`.
  - **Fix**: Align branch conditions with `ProjectPaymentRecord.STAGE_CHOICES`.

- **[x] fixed — fix(projects): replace non-existent theme utility classes in financial boards templates**
  - **Location**: `templates/projects/financialbilling/pnl.html`, `variance.html`, `aging.html`, `cashflow.html`
  - **Problem**: Uses non-existent classes `.text-green`, `.text-amber`, `.btn-ghost`, `.form-control`, `.stats-grid`.
  - **Fix**: Replace with `.text-ok`, `.text-warn`, `.btn.btn-sm.btn-outline`, `.form-select`, `.stat-grid`.

- **[x] fixed — fix(projects): clean up inline styles and dark mode variables in financial boards templates**
  - **Location**: `templates/projects/financialbilling/pnl.html`, `variance.html`, `aging.html`, `cashflow.html`
  - **Problem**: Undefined CSS variables `var(--border-color, #e2e8f0)` and `var(--bg-muted, #f8fafc)` create bright borders and white footers in dark mode.
  - **Fix**: Clean up inline styles and use design system classes (`.table-wrap`, `.table`, `.stat-grid`, `.stat-card`).

- **[x] fixed — fix(projects): add fallback badge branch on status badges in billing templates**
  - **Location**:
    - `templates/projects/financialbilling/billingrun/detail.html:65-74`
    - `templates/projects/financialbilling/revenueschedule/detail.html:67-78`
    - `templates/projects/financialbilling/paymentrecord/list.html:144-151`
  - **Problem**: Missing `{% else %}<span class="badge badge-muted">{{ obj.get_status_display }}</span>{% endif %}`.
  - **Fix**: Add standard fallback branch.

- **[x] fixed — fix(projects): add min_value to PaymentPromiseForm and assigned_collector to _reject_foreign**
  - **Location**: `apps/projects/forms/FinancialBillingManagement/PaymentRecords.py:40-60`
  - **Problem**: `promised_amount` missing `min_value=Decimal("0.00")`; `assigned_collector` missing in `_reject_foreign`.
  - **Fix**: Add `min_value=Decimal("0.00")` and add `"assigned_collector"` to `_reject_foreign`.

- **[x] fixed — fix(projects): guard pbr_dispatch to require invoiced billing run status**
  - **Location**: `apps/projects/views/FinancialBillingManagement/BillingRuns.py:224-250`, `templates/projects/financialbilling/billingrun/detail.html:258-272`
  - **Problem**: Dispatch allowed on draft/cancelled runs.
  - **Fix**: Enforce `billing_run.status == "invoiced"` in view and template.

- **[x] fixed — fix(projects): record accurate initial status in state transition audit logs**
  - **Location**: `apps/projects/views/FinancialBillingManagement/BillingRuns.py:215`, `RevenueSchedules.py:178`
  - **Problem**: Hardcodes initial status as "approved" in audit log even if transitioned directly from "draft".
  - **Fix**: Use `initial_status = obj.status`.

- **[ ] I14: Unposted Expenses Filter Missing in Financial Boards**
  - **Location**: `apps/projects/views/FinancialBillingManagement/FinancialBoards.py:61, 324`
  - **Problem**: `ProjectExpense` queries omit `status="posted"`.
  - **Fix**: Add `status="posted"` to expense queries.

---

## Minor

- **[ ] M1: Missing Composite Database Indexes on Filtered Fields**
  - **Location**: `apps/projects/models/FinancialBillingManagement/RateCards.py`, `RevenueSchedules.py`, `PaymentRecords.py`
  - **Problem**: Missing indexes: `(tenant, is_active)` on RTC, `(tenant, method)` on PRS, `(tenant, dunning_level)` on PPR.
  - **Fix**: Add to `Meta.indexes` and generate migration.

- **[ ] M2: Duplicate `COUNT(*)` Queries in List Views**
  - **Location**: `RateCards.py:43`, `BillingRuns.py:53`, `RevenueSchedules.py:56`, `PaymentRecords.py:57`
  - **Problem**: `"total_count": qs.count()` evaluates duplicate count query.
  - **Fix**: Remove `"total_count"` from `extra_context`, use `page_obj.paginator.count` in templates.

- **[ ] M3: Query Parameter Preservation in Pagination Links**
  - **Location**: List templates pagination links.
  - **Fix**: Preserve `q` and filter params in pagination links.

- **[ ] M4: Form Modal `<label>` Tags Missing `for=""` Attribute**
  - **Location**: `billingrun/detail.html`, `revenueschedule/detail.html`, `paymentrecord/detail.html` modals.
  - **Fix**: Add `for="{{ form.field.id_for_label }}"`.

- **[ ] M5: Cash Flow Forecast Inflows Query Missing `.distinct()`**
  - **Location**: `FinancialBoards.py:307`
  - **Fix**: Append `.distinct()` to `inflows_qs`.

- **[ ] M6: Project Filter Label Fallback in Dashboard Templates**
  - **Location**: `pnl.html:44`, `variance.html:44`, `aging.html:44`, `cashflow.html:44`
  - **Fix**: Use `{{ p.code|default:p.number }} — {{ p.name }}`.

- **[ ] M7: Cross-Record Project and Milestone Validation in Forms**
  - **Location**: `BillingRuns.py`, `PaymentRecords.py`, `RevenueSchedules.py` forms.
  - **Fix**: Validate that milestone and sow belong to the selected project.

- **[ ] M8: Update Checkboxes in `.claude/tasks/todo.md`**
  - **Location**: `.claude/tasks/todo.md`
  - **Fix**: Mark 7.15 checkboxes completed during closeout.
