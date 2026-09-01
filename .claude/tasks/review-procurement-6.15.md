# Review findings — procurement 6.15 Budget & Cost Management

Range: `2e0431fb...HEAD` · Generated: 2026-09-01
Wave (parallel): code-reviewer · security-reviewer · performance-reviewer · frontend-reviewer · explorer · qa-smoke-tester

## Summary

| Severity | Count |
|---|---|
| Critical | 0 |
| Important | 1 |
| Minor | 5 |
| **Total (deduped)** | **6** |

| Agent | Raw findings |
|---|---|
| code-reviewer | 2 |
| security-reviewer | 0 |
| performance-reviewer | 4 |
| frontend-reviewer | 0 |
| explorer | 0 |
| qa-smoke-tester | 0 |

## How to work this file (code-fixer)

Fix in ID order: every `C`, then every `I`, then every `M`. One fix → one file → one `git add` + one
`git commit`. Update each **Status** line to `[x] fixed — <commit subject>` or `[~] skipped — <reason>`
as you go. Never delete a finding; a wrong one gets `[~] skipped — not a defect: <why>`. Never `git push`.

## Important

### I1 — `apps/procurement/views/BudgetCostManagement/VarianceReport.py:251`

- **Found by:** code-reviewer
- **Problem:** Fiscal-period-only scope silently drops PO-less invoices with no disclosure. When a period (but no budget) is selected, the inv_lines filter through `invoice__purchase_order__requisition__budget__fiscal_period=period` excludes invoices raised without a PO; the standalone map then becomes empty, so those amounts stop being deducted from "remaining" even though REMAINING_NOTE (printed unconditionally) states they are. The same gap IS disclosed for budget scope via SCOPED_INVOICE_NOTE, but the context line renders it only when `selected_budget is not None`.
- **Fix:** Add a period-scope disclosure constant next to SCOPED_INVOICE_NOTE, e.g. `PERIOD_INVOICE_NOTE = "Invoices raised without a purchase order carry no budget or fiscal period, so they cannot be attributed to the selected period and are left out of this scoped view; they appear on the all-periods view."` and change the context line to `"scoped_invoice_note": SCOPED_INVOICE_NOTE if selected_budget is not None else (PERIOD_INVOICE_NOTE if selected_period is not None else "")` — the existing `{% if scoped_invoice_note %}` block in variance_report.html then prints it.
- **Status:** [ ] open

## Minor

### M1 — `apps/procurement/models/BudgetCostManagement/BudgetMappings.py:133`

- **Found by:** performance-reviewer
- **Problem:** `prc_bmap_tnt_active_idx` covers `(tenant, is_active)` only, so neither `resolve()`'s `.order_by("priority", "id")` nor the register's default ordering can be satisfied from the index — the index comment claims it backs that ordering, but MySQL must filesort the tenant's rows.
- **Fix:** Extend the index to `fields=["tenant", "is_active", "priority", "id"]` via a NEW migration 0025 (never edit 0024). Small table, but the fix also makes the comment true.
- **Status:** [ ] open

### M2 — `apps/procurement/views/BudgetCostManagement/BudgetMappings.py:45`

- **Found by:** code-reviewer (also noted by explorer and performance-reviewer)
- **Problem:** `budgetmapping_list` passes a `gl_accounts` context variable that the list template never consumes (the filter bar deliberately omits it; the template mentions it only inside its {% comment %} contract block), so the queryset is fetched and shipped for nothing on every list render.
- **Fix:** Delete the `gl_accounts` entry from both branches of `_filter_dropdowns` so the list view's context exactly matches the template contract; the create/edit forms build their own dropdowns and are unaffected. If the template's {% comment %} contract block mentions gl_accounts, update the comment too.
- **Status:** [ ] open

### M3 — `apps/procurement/views/BudgetCostManagement/BudgetMappings.py:57`

- **Found by:** performance-reviewer
- **Problem:** budgetmapping_list stat cards run three tenant-scoped COUNT queries although inactive = total − active is derivable, so the third query is redundant on every register render.
- **Fix:** Replace the three `.count()` calls with one conditional aggregate: `stats = base.aggregate(total=Count("pk"), active=Count("pk", filter=Q(is_active=True)))` and set `stats["inactive"] = stats["total"] - stats["active"]`.
- **Status:** [ ] open

### M4 — `apps/procurement/views/BudgetCostManagement/CostForecasts.py:80`

- **Found by:** performance-reviewer
- **Problem:** costforecast_list stat cards run three COUNT queries although workspace_wide = total − budget_scoped is derivable, so the third query is redundant on every register render.
- **Fix:** Replace the three `.count()` calls with `base.aggregate(total=Count("pk"), budget_scoped=Count("pk", filter=Q(budget__isnull=False)))` and derive `workspace_wide` as total − budget_scoped.
- **Status:** [ ] open

### M5 — `apps/procurement/views/BudgetCostManagement/VarianceReport.py:157`

- **Found by:** performance-reviewer
- **Problem:** When a budget is selected, inv_lines is already filtered to `invoice__purchase_order__requisition__budget=budget`, so the standalone grouped query's added `invoice__purchase_order__isnull=True` is a contradictory filter that always returns an empty result — one grouped-scan round trip to compute an empty dict.
- **Fix:** Skip the query in the scoped case: `standalone = {} if scoped else _grouped_pair_sum(inv_lines.filter(invoice__purchase_order__isnull=True), ...)`.
- **Status:** [ ] open

## Notes — app-wide / pre-existing (NOT in the fix queue)

- **code-reviewer:** (1) remaining never deducts invoices behind CLOSED POs — consistent with the page's stated formula but worth knowing if closed-PO volume grows; (2) register/variance totals cover the capped 500 rows only, disclosed on-page; (3) VarianceReport.py:143 uses `datetime.date.today()` while the 6.14 window helpers it reuses use `timezone.localdate()` (workspace-TZ) — a consistency nit beyond the lessons list.
- **performance-reviewer:** (1) migration 0024's composite `(tenant, budget)` indexes duplicate Django's auto-created single-column FK index on budget — harmless write amplification consistent with the rest of the repo; (2) CostForecast Meta.ordering `["-as_of", "-id"]` is not fully satisfiable by `prc_fcst_tnt_asof_idx` because of the id tiebreaker — negligible at forecast volumes.
- **security-reviewer:** CSRF relies on global CsrfViewMiddleware; admin registrations staff-gated per repo posture; plain-@login_required BudgetMapping write gates match the verified sibling SpendClassificationRule CRUD posture, so not flagged.
- **explorer:** (1) `budget_variance` also exists as a route name in the accounting and scm namespaces — no collision since namespaces differ; (2) variance_report.html:35 export href can emit a trailing `?`/`&` — harmless, the export parses GET defensively via as_db_int.
- **qa-smoke-tester:** seeded Acme row counts (mappings=5, forecasts=2) are both under crud_list per_page=15, so pagination page 2 is unreachable with seed data — stated explicitly per lane rules. Full sweep (12 URLs, filtered/junk/page-2/IDOR/freeze-via-POST/CSV-parity/checker-arithmetic) passed clean.

## Done well

- **code-reviewer:** Exemplary tenant discipline (every queryset filtered, forms narrow + _reject_foreign + model clean() backstop, tenant-less create guarded), complete __init__ re-export blocks, migration matching the models field-for-field, L11-safe parsing on every GET param, L33-palette badges only, single-source commitment vocabulary shared by all three computed pages, frozen-snapshot create path stamping amounts + created_by in one save, idempotent exists()-guarded seeder running through compute_forecast_amounts, and a flush block covering both new tables.
- **security-reviewer:** Defense-in-depth tenant discipline throughout: crud helpers enforce tenant on every pk lookup, forms triple-guard FKs, the hand-rolled costforecast_create stamps amounts only from compute_forecast_amounts(request.tenant,...) so no crafted POST can set tenant/number/amounts/created_by, both deletes are @require_POST with csrf forms, zero |safe usage, CSV export fully csv_safe'd, redirects only target named routes.
- **performance-reviewer:** Commitment register sums PO lines via a single grouped annotate instead of per-row aggregates; variance report uses one grouped query per population with the load-bearing order_by(); select_related tuples match template FK access exactly; crud_list provides real Paginator pagination.
- **frontend-reviewer:** Perfect theme.css fidelity — every badge/stat-icon/btn modifier exists in theme.css with colour-only names enforced at the model layer plus .get() fallbacks; all multi-line comments use {% comment %}; delete confirms interpolate only system-assigned numbers; all GET filters reflect request state; every list/report page has a .empty-state with a CTA.
- **explorer:** Inter-layer contract fully intact — all 14 new route names plus four external targets resolve; every template variable is supplied; all re-export blocks cover the 6.15 modules; LIVE_LINKS labels char-exact vs NavERP.md; the CostForecast no-edit exemption is consistently honoured across urls, views, templates and LIVE_LINKS.
- **qa-smoke-tester:** All 12 new URLs render 200 with titles and no template leaks; L11 junk-param discipline holds everywhere; tenant isolation is airtight; frozen-forecast amounts match an independent recomputation; deletes POST-only and really delete; CSV row count matches the rendered page; checker arithmetic internally consistent and matches ORM recomputation.
