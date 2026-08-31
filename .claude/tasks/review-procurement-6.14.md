# Review findings — procurement 6.14 Spend Analytics & Reporting

Range: `c11639d387acf425553f184a6e747497a5cd1c68...HEAD` · Generated: 2026-09-01
Wave (parallel): code-reviewer · security-reviewer · performance-reviewer · frontend-reviewer · explorer · qa-smoke-tester

## Summary

| Severity | Count |
|---|---|
| Critical | 1 |
| Important | 15 |
| Minor | 17 |
| **Total (deduped)** | **33** |

| Agent | Raw findings |
|---|---|
| code-reviewer | 7 |
| security-reviewer | 6 |
| performance-reviewer | 9 |
| frontend-reviewer | 5 |
| explorer | 4 |
| qa-smoke-tester | 2 |

## How to work this file (code-fixer)

Fix in ID order: every `C`, then every `I`, then every `M`. One fix → one file → one `git add` + one
`git commit`. Update each **Status** line to `[x] fixed — <commit subject>` or `[~] skipped — <reason>`
as you go. Never delete a finding; a wrong one gets `[~] skipped — not a defect: <why>`. Never `git push`.

## Critical

### C1 — `apps/procurement/views/SpendAnalyticsReporting/MaverickFindings.py:308`

- **Found by:** code-reviewer
- **Lesson:** L27
- **Problem:** `maverickfinding_delete` is only `@login_required` while the disposition verb on the same model is `@tenant_admin_required`, and it carries no status guard — so any tenant member can permanently erase a finding, including one already justified/remediated/dismissed with its recorded decision, achieving the outcome the admin gate exists to prevent.
- **Fix:** Add `@tenant_admin_required` between `@login_required` and `@require_POST` (the exact shape of the sibling `invoicedispute_delete` at apps/procurement/views/InvoiceVoucherManagement/InvoiceDisputes.py:311-314), and before delegating to `crud_delete` fetch the row (`get_object_or_404(MaverickSpendFinding, pk=pk, tenant=request.tenant)`) and refuse with `messages.error` + `redirect('procurement:maverickfinding_detail', pk=pk)` when `obj.is_resolved`. Then wrap the bin form in `{% if is_admin %}` in templates/procurement/spendanalytics/maverickfinding/list.html:212 and detail.html:67 so a button that would now 403 is not offered.
- **Status:** [ ] open

## Important

### I1 — `apps/procurement/analytics.py:235`

- **Found by:** security-reviewer
- **Lesson:** L11
- **Problem:** `range_bounds` adds `timedelta(days=1)` to a user-supplied custom-range date without a ceiling, so `?range=custom&date_from=2020-01-01&date_to=9999-12-31` (a value that parses cleanly through `_parse_date`) raises an uncaught `OverflowError: date value out of range` and 500s the spend dashboard, category spend, export page and CSV download — and a `SpendReport` saved with that date (the model's own `clean()` explicitly permits `_MAX_DATE = date(9999, 12, 31)`) permanently 500s its detail/export/run/snapshot routes.
- **Fix:** Clamp before adding. In `apps/procurement/analytics.py` add a module constant `_MAX_BOUND = date(9999, 12, 30)` and rewrite the custom branch:

```python
if key == "custom" and date_from is not None:
    date_from = min(date_from, _MAX_BOUND)
    if date_to is not None:
        stop = min(date_to, _MAX_BOUND) + timedelta(days=1)
    else:
        stop = end
    if stop <= date_from:
        stop = date_from + timedelta(days=1)
    return date_from, stop
```

Verified by direct call: `range_bounds("custom", date(2020,1,1), date(9999,12,31))` and `range_bounds("custom", date(9999,12,31), None)` both raise today. The same shape exists nowhere else — `grep -rn "date_to + timedelta(days=1)" apps/` returns only this line.
- **Status:** [ ] open

### I2 — `apps/procurement/analytics.py:328`

- **Found by:** performance-reviewer
- **Problem:** `active_rules()` select_relates only `category`, but `classification_workbench.html:171` renders `{{ rule.subject_label }}` for every rule in the legend panel (up to `MAX_GROUP_ROWS` = 25). `SpendClassificationRule.subject_label` (models/.../SpendClassificationRules.py:329) does `str(self.vendor)` / `str(self.gl_account)` / `str(self.org_unit)`, so every vendor/GL/department rule is one extra query — 1 + N with N up to 25 on the workbench.
- **Fix:** Change line 328 to `.select_related("category", "vendor", "gl_account", "org_unit")`. The rule list is small and fetched once per request, so the three extra LEFT JOINs are free; this also covers `spendrule_detail`'s use of the same helper.
- **Status:** [ ] open

### I3 — `apps/procurement/analytics.py:657`

- **Found by:** qa-smoke-tester
- **Lesson:** L40
- **Problem:** `maverick_rate()` divides a SUM of per-finding `amount` by recognised invoiced spend, but several findings are raised against the same document (and 7 of Acme's 13 are PO-only `no_requisition` findings with no invoice at all), so the numerator over-counts and the ratio is unbounded — the default `spend_dashboard` KPI tile renders "562.3%" for Acme and "203.8%" for Globex, and `maverick_dashboard.html:65/69` prints the same number plus a `style="width:562%"` progress bar under a legend that claims 10%/20% thresholds.
- **Fix:** In `maverick_rate()` compute `pct` from a DISTINCT-document numerator instead of a sum of finding amounts. After `lines = invoiced_lines(tenant, start, end)` and `addressable_value = money(spend["v"] or ZERO)`, add:

    flagged_invoice_ids = (findings.filter(supplier_invoice__isnull=False)
                           .values_list("supplier_invoice_id", flat=True))
    flagged_spend = money(lines.filter(invoice_id__in=flagged_invoice_ids)
                          .aggregate(v=Sum("line_total"))["v"] or ZERO)

then change line 657 to `pct = _share(flagged_spend, addressable_value)` and add `"flagged_spend": flagged_spend` to both the returned dict and the `empty` dict at line 636. Leave `maverick_value` exactly as it is — it is the value-at-risk figure the `maverick_spend` report measure returns at line 751 and must keep its current meaning. Verified: with this change the rendered rate becomes 100.0 / 100.0 / 0 for Acme / Globex / SMOKETEST instead of 562.3 / 203.8 / 0, and is bounded to [0,100] by construction. Note that `_scalar(..., max_value=100)` at line 721 only clamps the unused progress `pct`, never `display`, so it is not a bound on what the user actually sees.
- **Status:** [ ] open

### I4 — `apps/procurement/analytics.py:884`

- **Found by:** performance-reviewer
- **Problem:** The two-axis branch of `compute_report` runs a full `spend_cube` per kept first-axis row: each inner call re-issues its own `SUM(line_total)` total (line 477) plus the group query, and `_narrow_to_row` for the `category` dimension issues a further `SpendClassificationRule` query inside `category_filter_q` (line 344). With the default `top_n=20` that is ~40–60 queries per render, and up to ~300 at the model's `top_n=100` ceiling — paid on every `spendreport_detail` view, every `spendreport_export` download and every `spendreport_snapshot` POST.
- **Fix:** Add an optional `total=None` parameter to `spend_cube` (used at line 477 as `total = total if total is not None else lines.aggregate(...)`) and pass the outer `total` computed at line 840 into the inner calls at line 884, removing one query per row. Additionally hoist the rule lookup out of the loop: fetch `active_rules(tenant)` once and pass a prebuilt per-category `Q` to `_narrow_to_row` instead of letting `category_filter_q` re-query `SpendClassificationRule` for every row.
- **Status:** [ ] open

### I5 — `apps/procurement/models/SpendAnalyticsReporting/MaverickFindings.py:531`

- **Found by:** performance-reviewer
- **Problem:** `_upsert` runs `cls.objects.filter(tenant=tenant, dedupe_key=key).first()` once per candidate, and `scan()` (line 522) calls it in a loop over every candidate the eight detectors produced — with `SCAN_LINE_LIMIT = 20000` the three line-level detectors alone can emit tens of thousands of candidates, so the scan is O(N) SELECTs on top of O(N) saves (each new row also costs a `next_number` query via `TenantNumbered.save`). This is the seeder's hot path (`seed_procurement._seed_spend_analytics` calls `scan()` over a one-year window) as well as the board's scan button.
- **Fix:** In `scan()`, after `candidates` is built and before the `transaction.atomic()` loop, pre-load the map in ONE query: `keys = [c.get("dedupe_key") for c in candidates if c.get("dedupe_key")]; existing_by_key = {o.dedupe_key: o for o in cls.objects.filter(tenant=tenant, dedupe_key__in=keys)}`. Pass it into `_upsert(tenant, row, existing_by_key)` and replace the per-row `.filter(...).first()` at line 531 with `existing_by_key.get(key)`. Optionally collect the refreshed rows and flush them with one `cls.objects.bulk_update(refreshed, [...], batch_size=500)` instead of the per-row `existing.save()` at line 549 (set `leakage_amount` explicitly in the loop, since `save()` is what derives it today).
- **Status:** [ ] open

### I6 — `apps/procurement/views/SpendAnalyticsReporting/ClassificationWorkbench.py:198`

- **Found by:** explorer
- **Problem:** The workbench builds its page with a bare `Paginator(rows, PAGE_SIZE).get_page(...)` instead of `apps.core.crud.paginate()`, so `page_obj.window` is never set — and `templates/partials/pagination.html` (included at classification_workbench.html:145) loops `{% for n in page_obj.window %}`, which silently resolves to empty, so the numbered page links disappear from the only paginated page in 6.14.
- **Fix:** In apps/procurement/views/SpendAnalyticsReporting/ClassificationWorkbench.py change the import on line 29 to `from apps.core.crud import as_db_int, paginate`, delete the now-unused `from django.core.paginator import Paginator` on line 25, and replace lines 198-199 (`paginator = Paginator(rows, PAGE_SIZE)` / `page_obj = paginator.get_page(request.GET.get("page"))`) with `page_obj = paginate(request, rows, PAGE_SIZE)`. In the render context keep `"page_obj": page_obj` and change `"paginator": paginator` to `"paginator": page_obj.paginator` (classification_workbench.html:109 reads `paginator.count`). `apps.core.crud.paginate` takes any sliceable, so the plain list of group rows works unchanged.
- **Status:** [ ] open

### I7 — `apps/procurement/views/SpendAnalyticsReporting/MaverickFindings.py:60`

- **Found by:** performance-reviewer
- **Problem:** `_ROW_RELATIONS` omits `invoice_line`, but `maverickfinding/list.html:166-167` reads `obj.invoice_line` (and `.description`/`.pk`) on every row and again in the `{% if not ... %}` fallback at line 172 — the three line-level detectors (`off_catalog`, `non_preferred_vendor`, `price_above_contract`) all stamp `invoice_line`, so most rows on the register issue one extra query each (1 + N; ~16 queries for a 15-row page instead of 1).
- **Fix:** Add `"invoice_line"` to `_ROW_RELATIONS` on line 60 so it becomes `("vendor", "category", "org_unit", "supplier_invoice", "purchase_order", "invoice_line")`, and drop the now-duplicated bare `"invoice_line"` entry from `_DETAIL_RELATIONS` (line 65), keeping the chained `"invoice_line__invoice"` / `"invoice_line__item"` hops there.
- **Status:** [ ] open

### I8 — `apps/procurement/views/SpendAnalyticsReporting/MaverickFindings.py:310`

- **Found by:** security-reviewer
- **Lesson:** L27
- **Problem:** `maverickfinding_delete` is only `@login_required` while `maverickfinding_disposition` — a strictly weaker action on the same row — is `@tenant_admin_required`, so any ordinary workspace member who is refused permission to dismiss a maverick-spend finding can simply POST to the delete route and destroy the finding together with its resolution note and resolved_by stamp, bypassing the governance gate the module docstring says it is enforcing.
- **Fix:** Add the same gate to the delete route (decorator order matching the disposition verb):

```python
@login_required
@tenant_admin_required
@require_POST
def maverickfinding_delete(request, pk):
    return crud_delete(request, model=MaverickSpendFinding, pk=pk,
                       success_url="procurement:maverickfinding_list")
```

Both templates already receive `is_admin`, so wrap the two delete forms so the now-403 button stops being offered: `templates/procurement/spendanalytics/maverickfinding/list.html:212` and `templates/procurement/spendanalytics/maverickfinding/detail.html:67` become `{% if is_admin %}<form method="post" …>…</form>{% endif %}`, and update the `{% comment %}` above each that currently states the view carries no admin gate.
- **Status:** [ ] open

### I9 — `apps/procurement/views/SpendAnalyticsReporting/MaverickFindings.py:342`

- **Found by:** code-reviewer
- **Lesson:** L7
- **Problem:** The disposition view reads the note from `request.POST.get("note")` but the detail template posts it as `name="resolution_note"` (maverickfinding/detail.html:286), so justify / remediate / dismiss — the three verbs with `needs_note=True` — always bounce with "A note is required…" and no finding can ever be closed from the UI.
- **Fix:** Change line 342 to `note = (request.POST.get("resolution_note") or "").strip()`, matching the 6.13 precedent in apps/procurement/views/InvoiceVoucherManagement/InvoiceDisputes.py:384 and the ProcurementAlerts view; leave the template key as-is.
- **Status:** [ ] open

### I10 — `apps/procurement/views/SpendAnalyticsReporting/SpendDashboards.py:436`

- **Found by:** performance-reviewer
- **Problem:** The line-level export register select_relates only `_classify_select_related(basis)` + `gl_account`, but the row builder below reads `document.currency` on both bases (line 459/458) and `document.vendor` on the committed basis (line 458) — none of which are fetched. That is 1 unfetched FK per row on the invoiced basis and 2 on the committed basis, over a window sliced at `MAX_EXPORT_ROWS = 5000`, i.e. up to 5,000–10,000 extra queries per export page render and per CSV download.
- **Fix:** In `_export_dataset`, extend the select_related at line 436 with the document's own vendor/currency: `extra = ("invoice__currency",) if basis == "invoiced" else ("purchase_order__vendor", "purchase_order__currency")` and call `.select_related(*_classify_select_related(basis), "gl_account", *extra)`. Do NOT widen `_classify_select_related` itself — the classification walk in `analytics._category_groups` does not need currency.
- **Status:** [ ] open

### I11 — `apps/procurement/views/SpendAnalyticsReporting/SpendDashboards.py:497`

- **Found by:** performance-reviewer
- **Lesson:** L40
- **Problem:** `spend_export` (the PAGE) calls `_export_dataset` with no row limit, which materialises up to 5,000 `SupplierInvoiceLine`/`PurchaseOrderLine` rows and builds 5,000 python lists, only for line 535 to render `rows[:25]`. The 25-row preview costs the full download's work on every page view — the same shape as L40 (a bound applied after the thing it bounds has already been built).
- **Fix:** Give `_export_dataset` a `row_limit=MAX_EXPORT_ROWS` keyword and use it for the register slice at line 438 (`[:row_limit]`) only — leave the `dimension != "none"` cube branch alone so its `total_rows` stays the true group count. Then call it from `spend_export` (line 497) with `row_limit=25` and from `spend_export_download` (line 556) with the default. `total_rows` already comes from the independent `lines.count()` at line 434, so the "Showing N of M" note stays correct.
- **Status:** [ ] open

### I12 — `apps/procurement/views/SpendAnalyticsReporting/SpendReports.py:97`

- **Found by:** security-reviewer
- **Problem:** `_report_qs` (and every other `SpendReport` fetch in the module) ignores `is_shared` and `owner`, so a report the UI labels "Private to the owner" (templates/procurement/spendanalytics/spendreport/detail.html:152, list.html:156) is in fact listed, opened, exported, edited and deleted by every logged-in member of the workspace — the app makes an access-control promise it never enforces.
- **Fix:** Enforce it in one place and reuse it. In `apps/procurement/views/SpendAnalyticsReporting/SpendReports.py` add:

```python
from django.db.models import Q

def _visible(request):
    """Shared reports, plus the caller's own private ones."""
    return (SpendReport.objects.filter(tenant=request.tenant)
            .filter(Q(is_shared=True) | Q(owner=request.user)))

def _report_qs(request):
    return _visible(request).select_related(*_ROW_RELATIONS)
```

Then replace every `get_object_or_404(SpendReport, pk=pk, tenant=request.tenant)` in this module (lines 184, 259, 276, 296, 325, 346) with `get_object_or_404(_visible(request), pk=pk)`, scope the snapshot fetches through the parent (`SpendReportSnapshot.objects.filter(tenant=request.tenant, report__in=_visible(request))` at lines 356, 388, 398), and narrow `reports`/`snapshots` in `spend_export` (apps/procurement/views/SpendAnalyticsReporting/SpendDashboards.py:500-503) the same way. If workspace-wide visibility is the intended behaviour instead, drop the field from `SpendReportForm.Meta.fields` and delete the "Private to the owner" badge rather than leaving an unenforced claim.
- **Status:** [ ] open

### I13 — `templates/procurement/spendanalytics/category_spend.html:237`

- **Found by:** explorer
- **Lesson:** L7
- **Problem:** The "Same item, different price" table renders `row.spread` as a percentage (`{{ row.spread|floatformat:1 }}%`, with badge thresholds `> 20` red / `> 5` amber), but the view computes it as an absolute money amount — `"spread": money((hi - lo) …)` in `_item_spread` at apps/procurement/views/SpendAnalyticsReporting/SpendDashboards.py:401 — so a $150 price spread is reported to the category manager as "150.0%" in red and a $2 spread as "2.0%" in green.
- **Fix:** Add a real percentage to the row dict in `_item_spread` (apps/procurement/views/SpendAnalyticsReporting/SpendDashboards.py, in the `item_rows.append({...})` block around line 395-402): `"spread_pct": _share(hi - lo, lo) if (lo is not None and hi is not None and lo) else ZERO` (`_share` is already imported from apps.procurement.analytics). Then in templates/procurement/spendanalytics/category_spend.html line 237 use `row.spread_pct` for the badge thresholds and the `%` display, and add a separate money cell for `{{ row.spread|floatformat:2 }}` (or drop the `%` entirely and format `row.spread` with `floatformat:2` like the neighbouring Lowest/Highest price columns at lines 233-234). Update the `{% else %}` fallback at line 239 to match whichever unit is chosen.
- **Status:** [ ] open

### I14 — `templates/procurement/spendanalytics/classification_workbench.html:145`

- **Found by:** frontend-reviewer
- **Lesson:** L9
- **Problem:** `partials/pagination.html` iterates `{% for n in page_obj.window %}` for the numbered page links, but this page's view builds `page_obj` with a bare `Paginator` (apps/procurement/views/SpendAnalyticsReporting/ClassificationWorkbench.py:198-199) instead of `apps.core.crud.paginate`, which is what sets `page.window` — so the queue's page numbers silently render as nothing and only Prev/Next appear.
- **Fix:** In apps/procurement/views/SpendAnalyticsReporting/ClassificationWorkbench.py replace lines 198-199 with `from apps.core.crud import paginate` + `page_obj = paginate(request, rows, PAGE_SIZE)` and keep `"paginator": page_obj.paginator` for the `{{ paginator.count }}` badge at line 109. The template include needs no change once `page_obj.window` exists.
- **Status:** [ ] open

### I15 — `templates/procurement/spendanalytics/spendreportsnapshot/detail.html:49`

- **Found by:** frontend-reviewer
- **Lesson:** L13
- **Problem:** The "Report settings" grid uses `<div class="detail-label">` / `<div class="detail-value">`, and neither class exists in theme.css (it only ships `.detail-grid`, `.detail-item`, `.detail-item dt`, `.detail-item dd`), so all six rows render as flat unstyled body text instead of the muted uppercase caption every other detail page in the sub-module shows.
- **Fix:** Replace the plain `<div>` wrapper on line 48 and the six rows on lines 49-54 with the canonical markup used by its own siblings (e.g. spendrule/detail.html:66-106): `<dl class="detail-grid">` and, per row, `<div class="detail-item"><dt>Report</dt><dd><a href="{{ back_url }}">{{ report.number }} — {{ report.name }}</a></dd></div>` … closing with `</dl>`. Do not introduce `.detail-label`/`.detail-value`.
- **Status:** [ ] open

## Minor

### M1 — `apps/procurement/analytics.py:477`

- **Found by:** performance-reviewer
- **Problem:** `spend_cube` recomputes `total = lines.aggregate(Sum("line_total"))` on every call even when the caller passes a pre-built `lines` window. `spend_dashboard` calls it three times and then calls `classified_pct` (line 618) and `spend_kpis` (line 687), so the same `SUM(line_total)` over the same joined invoice-line window is executed 4–5 times per dashboard render.
- **Fix:** Add the optional `total=None` parameter described above and thread it through: compute the window total ONCE in `spend_dashboard` (apps/procurement/views/SpendAnalyticsReporting/SpendDashboards.py:186-194) and pass it to the three `spend_cube` calls and to `classified_pct`. Same change benefits `category_spend`, which already has `totals["value"]` in hand at line 254.
- **Status:** [ ] open

### M2 — `apps/procurement/management/commands/seed_procurement.py:1960`

- **Found by:** qa-smoke-tester
- **Lesson:** L44
- **Problem:** `_seed_spend_analytics` seeds rules, findings and reports but no recognised invoiced spend, so on the default window (`invoiced` / `last_90`) Acme has 3 spend lines from 1 supplier and Globex 3 from 1 — the sub-module's two headline pages render a single-row Pareto with HHI 10000 and an A-band of 100%, and every KPI tile on Spend Dashboards is computed off 3 lines.
- **Fix:** Add an idempotent block at the top of `_seed_spend_analytics(self, tenant)` (before the classification-rules block, guarded by its own marker so a re-run is a no-op) that creates ~8-10 small SupplierInvoices in `RECOGNISED_INVOICE_STATUSES` (`approved` / `scheduled` / `paid`) spread across at least 4 distinct supplier Parties, 3 distinct ItemCategories and the last 90 days, each with 2-3 lines. Do NOT mutate the statuses of the invoices 6.13's `_seed_invoice_vouchers` created — that block deliberately spreads them across every lifecycle status and promoting them would desync the Bill/JE postings it made. Only 3 of Acme's 16 seeded invoices reach a recognised status today (1 approved, 1 scheduled, 1 paid), which is why the cube is thin.
- **Status:** [ ] open

### M3 — `apps/procurement/views/_helpers.py:321`

- **Found by:** security-reviewer
- **Problem:** `csv_safe` — now the single shared spreadsheet-injection guard for 6.1's self-service export and all three 6.14 downloads — only neutralises a leading `=`, `+`, `-` or `@`, so a supplier name or line description beginning with a TAB or CR followed by `=` (e.g. `\t=cmd|'/c calc'!A1`) still reaches the reader's spreadsheet as a formula.
- **Fix:** Extend the leading-character set to the full OWASP list:

```python
_CSV_DANGEROUS = ("=", "+", "-", "@", "\t", "\r")

def csv_safe(value):
    text = str(value)
    if text[:1] in _CSV_DANGEROUS:
        return f"'{text}"
    return text
```

Both consumers call through this one definition (`_csv_safe = csv_safe` in apps/procurement/views/DashboardPortal/SelfServiceReports.py:112), so the single edit covers every export.
- **Status:** [ ] open

### M4 — `apps/procurement/views/SpendAnalyticsReporting/ClassificationWorkbench.py:198`

- **Found by:** code-reviewer
- **Lesson:** L9
- **Problem:** The workbench builds its page with a raw `Paginator(...).get_page(...)` instead of `apps.core.crud.paginate`, so `page_obj.window` is never set and the `{% for n in page_obj.window %}` block in partials/pagination.html silently renders no page-number links (Prev/Next still work).
- **Fix:** Replace the raw Paginator with the shared helper: `from apps.core.crud import as_db_int, paginate` at the top, then `page_obj = paginate(request, rows, PAGE_SIZE)` and pass `"paginator": page_obj.paginator` in the context (the template reads `paginator.count` at classification_workbench.html:109).
- **Status:** [ ] open

### M5 — `apps/procurement/views/SpendAnalyticsReporting/SpendDashboards.py:500`

- **Found by:** performance-reviewer
- **Problem:** `reports` is an unbounded tenant queryset rendered in full by `export.html:193` — unlike `snapshots` on line 502, which is correctly sliced `[:10]`. A workspace with hundreds of saved reports renders every one of them on an export page, and `reports.count()` at line 530 issues an extra COUNT because the queryset has not been evaluated yet.
- **Fix:** Slice the render queryset — `reports = (SpendReport.objects.filter(tenant=request.tenant).select_related("owner").order_by("-is_favorite", "name")[:25])` — and keep `stats["reports"]` as its own `SpendReport.objects.filter(tenant=request.tenant).count()`. Drop `vendor`/`category`/`org_unit`/`gl_account` from the select_related: `export.html` renders only number, name, measure, basis, owner and last_run_at.
- **Status:** [ ] open

### M6 — `apps/procurement/views/SpendAnalyticsReporting/SpendReports.py:218`

- **Found by:** performance-reviewer
- **Problem:** `spendreport_detail` calls `analytics.currency_split(...)` a second time for the same report — `compute_report` already computed exactly that split at analytics.py:842. Besides the duplicated aggregate query, the view's call omits the report's saved filters (no `lines=` argument), so `mixed_currency`/`currency_rows` describe the WHOLE window while the table beside them is filtered.
- **Fix:** Return the already-computed split from `compute_report` (add `"currency_rows": split["rows"], "mixed_currency": split["mixed_currency"]` to all three return dicts in analytics.py — `spendreport_snapshot` stores only the five named keys at SpendReports.py:310, so the payload contract is unaffected) and read them off `result` in the view instead of the second `currency_split` call on line 218.
- **Status:** [ ] open

### M7 — `templates/procurement/spendanalytics/maverick_dashboard.html:110`

- **Found by:** frontend-reviewer
- **Problem:** `<label class="form-label">Detectors to run …</label>` carries no `for=` and wraps no control, yet it is the group caption for the `name="reason"` checkboxes below it — a screen reader announces a label bound to nothing and the checkbox group has no accessible name.
- **Fix:** Turn the wrapper into a grouping element: change the `<div class="form-group">` on line 109 to `<fieldset class="form-group">` (closing `</fieldset>` on line 116) and line 110 to `<legend class="form-label">Detectors to run <span class="text-muted">(leave all unticked to run every one)</span></legend>`. The per-checkbox wrapping labels on line 113 are already correct and need no change.
- **Status:** [ ] open

### M8 — `templates/procurement/spendanalytics/maverickfinding/detail.html:58`

- **Found by:** security-reviewer
- **Problem:** The Edit button is offered on every finding, but `maverickfinding_edit` refuses any finding where `obj.is_resolved` and bounces back with an error message, so a user clicking Edit on a justified/remediated/dismissed finding lands on a dead end the page told them was available.
- **Fix:** The detail view already passes `is_resolved`. Wrap all three Edit affordances in the guard the view applies — `templates/procurement/spendanalytics/maverickfinding/detail.html:58` and `:301`, and `templates/procurement/spendanalytics/maverickfinding/list.html:203` (which can test `obj.is_resolved` directly):

```django
{% if not is_resolved %}
  <a href="{% url 'procurement:maverickfinding_edit' obj.pk %}" class="btn btn-primary"><i data-lucide="pencil"></i> Edit</a>
{% endif %}
```
- **Status:** [ ] open

### M9 — `templates/procurement/spendanalytics/maverickfinding/list.html:203`

- **Found by:** code-reviewer
- **Problem:** The Edit pencil is rendered on every row, but `maverickfinding_edit` refuses a resolved finding and bounces to the detail page with an error — the template offers an action the view will not perform.
- **Fix:** Wrap the edit anchor in `{% if not obj.is_resolved %}…{% endif %}` here, and do the same for the two Edit links on templates/procurement/spendanalytics/maverickfinding/detail.html (lines 58 and 301) using `{% if not is_resolved %}`.
- **Status:** [ ] open

### M10 — `templates/procurement/spendanalytics/spendreport/list.html:147`

- **Found by:** frontend-reviewer
- **Problem:** The chart-type badge chain has four explicit branches that collapse to two colours — `bar`/`line`/`pie` all emit `badge-muted` and `table` emits `badge-slate`, which is byte-identical to the `{% else %}` fallback — so three of the five branches are dead weight.
- **Fix:** Replace lines 147-151 with a single line: `<span class="badge {% if obj.chart_type == "table" %}badge-slate{% else %}badge-muted{% endif %}">{{ obj.get_chart_type_display }}</span>` — the display label already covers any future CHOICES value.
- **Status:** [ ] open

### M11 — `templates/procurement/spendanalytics/spendreport/list.html:162`

- **Found by:** code-reviewer
- **Problem:** The favourite toggle posts no `next` field, so `spendreport_favorite` (SpendReports.py:333) falls through to its detail redirect and pinning a row from the register navigates the user off the list they were filtering.
- **Fix:** Add `<input type="hidden" name="next" value="{{ request.get_full_path }}">` inside the favourite form, next to `{% csrf_token %}` — the view already validates it with `url_has_allowed_host_and_scheme`.
- **Status:** [ ] open

### M12 — `templates/procurement/spendanalytics/spendreportsnapshot/detail.html:35`

- **Found by:** code-reviewer
- **Problem:** The snapshot delete form guards with `onclick="return confirm(...)"` on the `<form>` element rather than `onsubmit`, so the confirm does not fire for a keyboard (Enter) submit and differs from every other delete form in this sub-module.
- **Fix:** Change the attribute on the `<form>` tag from `onclick=` to `onsubmit=`, matching spendreport/detail.html:247 and spendrule/detail.html:200.
- **Status:** [ ] open

### M13 — `templates/procurement/spendanalytics/spendreportsnapshot/detail.html:35`

- **Found by:** security-reviewer
- **Problem:** The snapshot delete form uses `onclick="return confirm(...)"` on the `<form>` element instead of `onsubmit`, so the return value is never applied to submission and the destructive POST goes through without the confirmation dialog gating it — unlike every sibling delete form in this sub-module, which uses `onsubmit`.
- **Fix:** Change the attribute to `onsubmit` so the handler's return value actually cancels the submit:

```django
<form method="post" action="{{ delete_url }}" style="display:inline;"
      onsubmit="return confirm('Delete snapshot {{ snapshot.pk }}? The frozen figures cannot be recovered.');">
  {% csrf_token %}
```
- **Status:** [ ] open

### M14 — `templates/procurement/spendanalytics/spendreportsnapshot/detail.html:35`

- **Found by:** frontend-reviewer
- **Problem:** The snapshot delete confirm is bound as `onclick` on the `<form>` element rather than `onsubmit`; a submit that is not a button click (Enter key in the form, or a programmatic submit) never fires the confirm, and it is the only delete in this sub-module not using `onsubmit`.
- **Fix:** Change the attribute on line 35 from `onclick="return confirm(...)"` to `onsubmit="return confirm('Delete snapshot {{ snapshot.pk }}? The frozen figures cannot be recovered.');"`, matching spendreport/detail.html:218 and :247.
- **Status:** [ ] open

### M15 — `templates/procurement/spendanalytics/spendreportsnapshot/detail.html:35`

- **Found by:** explorer
- **Problem:** The snapshot delete form carries `onclick="return confirm(...)"` on the `<form>` element instead of `onsubmit`, unlike every other delete form in this sub-module (spendrule/list.html:169, spendreport/detail.html:218 and :247), so the confirm fires on any click anywhere inside the form region and would not guard a non-click (keyboard) submission.
- **Fix:** In templates/procurement/spendanalytics/spendreportsnapshot/detail.html line 35 change the attribute `onclick="return confirm('Delete snapshot {{ snapshot.pk }}? The frozen figures cannot be recovered.');"` to `onsubmit="return confirm('Delete snapshot {{ snapshot.pk }}? The frozen figures cannot be recovered.');"`, matching spendreport/detail.html:218.
- **Status:** [ ] open

### M16 — `templates/procurement/spendanalytics/spendreportsnapshot/detail.html:49`

- **Found by:** code-reviewer
- **Lesson:** L33
- **Problem:** The settings grid uses `.detail-label` / `.detail-value`, which do not exist in static/css/theme.css (it ships `.detail-item dt` / `.detail-item dd` only), so those six rows render as unstyled text.
- **Fix:** Rewrite lines 48-55 in the design-system shape used by every other 6.14 detail page: `<dl class="detail-grid"><div class="detail-item"><dt>Report</dt><dd>…</dd></div>…</dl>`.
- **Status:** [ ] open

### M17 — `templates/procurement/spendanalytics/spendreportsnapshot/detail.html:49`

- **Found by:** explorer
- **Lesson:** L33
- **Problem:** The "Report settings at the time of the run" grid uses `<div class="detail-label">` / `<div class="detail-value">`, and neither class exists in static/css/theme.css (theme.css:354-357 defines only `.detail-grid`, `.detail-item`, `.detail-item dt`, `.detail-item dd`), so the six labels render as unstyled body text indistinguishable from their values — the sibling 6.14 templates (spendrule/form.html:51-59, spendrule/detail.html) explicitly document the correct markup.
- **Fix:** In templates/procurement/spendanalytics/spendreportsnapshot/detail.html rewrite lines 48-55 as `<dl class="detail-grid">` with one `<div class="detail-item"><dt>Report</dt><dd>…</dd></div>` per pair (Report / Measure / Grouped by / Window / Rows frozen / Taken), matching templates/procurement/spendanalytics/spendrule/form.html:51-59.
- **Status:** [ ] open

## Notes — app-wide / pre-existing (NOT in the fix queue)

- **code-reviewer:** Verified clean, no finding needed: all 34 `{% url %}` names in the new templates resolve (incl. `scm:purchaseorder_detail`, `scm:contract_detail`, `scm:spend_analytics`); every context key consumed by the 12 templates exists in its view's dict; migration 0021 matches the four models field-for-field incl. both `unique_together` pairs and all 8 indexes; all four models carry a tenant FK and both numbered models are `unique_together` with tenant; `models/forms/views/__init__.py` re-export blocks are complete (31 view names, 3 forms, 4 models + 2 window helpers); every GET param goes through `as_db_int` or a whitelist `_selected()`; `min_amount`/`amount`/`benchmark_amount` are `forms.DecimalField`s rather than hand-parsed (L35 satisfied); the seeder is idempotent per block with a `--flush` order consistent with the FK graph and reuses real Party/GLAccount/OrgUnit rows.\n\nPerformance (route to performance-reviewer, not fixed here): `_export_dataset` in views/SpendAnalyticsReporting/SpendDashboards.py:435-473 dereferences `document.vendor` and `document.currency` per row but `_classify_select_related()` covers neither, so a 5000-row CSV is ~10k extra queries; `compute_report` runs one `spend_cube` per kept row for a two-dimension report (analytics.py:882-894); `spend_dashboard` adds a standalone `lines.count()` for `stats.line_count`.\n\nObservation, not actionable: `SpendClassificationRule.preview()` (models/.../SpendClassificationRules.py:516-523) sums the invoiced AND committed bases into one \"value\" for an `applies_to=\"both\"` rule, so an invoice raised against a PO is counted twice in that one figure — it is documented in the docstring and only feeds the preview/`match_count` stamp, never the cube.\n\nPhase-order, out of scope: no SKILL.md/README update and no tests are in this range — those are Phases 6 and 7 and are expected to land after the fix wave.
- **security-reviewer:** No cross-tenant IDOR, no `|safe` / `mark_safe` / `{% autoescape off %}`, no `@csrf_exempt`, no raw SQL, no `.raw()`/`.extra()`, no secrets in forms, messages or `static/js` anywhere in this changeset. Chart data goes through `{{ trend|json_script:… }}` (not `|safe` on `json.dumps`), every inline `style="width:…"` interpolates a server-computed `floatformat` number rather than a tenant-controlled colour (so L26 does not apply), every POST form carries `{% csrf_token %}`, `spendreport_favorite`'s `?next=` is validated with `url_has_allowed_host_and_scheme`, `maverick_scan` and `maverickfinding_disposition` are both `@tenant_admin_required` + `@require_POST`, and every export cell passes through `csv_safe`. There are no file uploads and no payment data in this sub-module.\n\nOut of scope / app-wide observations, not for the fix queue: (1) `spendrule_create/edit/delete` are `@login_required` only, and a classification rule silently re-categorises the whole workspace's spend cube — that matches the existing `ReceiptTolerancePolicy` / `ApprovalRoutingRule` precedent, so it is an app-wide policy question rather than a 6.14 regression. (2) `write_audit_log` in `_report_form` (SpendReports.py:154) builds its own `changes` dict instead of calling `apps.core.crud._changed`, so it bypasses the `_SENSITIVE_AUDIT_FIELDS` redaction — harmless here because no field on `SpendReportForm` is sensitive, but the same hand-rolled shape would leak if the form ever grew one. (3) `_helpers.py`'s `csv_safe` was moved, not authored, in this range — the tab/CR gap it inherits also affected 6.1 before this changeset.
- **performance-reviewer:** App-wide / pre-existing, NOT in this changeset and therefore not in the fix queue:

1. `procurement.SupplierInvoice` (apps/procurement/models/InvoiceVoucherManagement/SupplierInvoices.py:338-343, shipped by 6.13) has `(tenant, status)` and `(tenant, discount_date)` / `(tenant, due_date)` indexes but no `(tenant, status, invoice_date)`. Every single 6.14 query hangs off `invoiced_line_window`, which joins `SupplierInvoiceLine -> invoice` and filters `invoice__tenant`, `invoice__status__in`, `invoice__invoice_date__gte/__lt` together. A composite `models.Index(fields=["tenant", "status", "invoice_date"])` would back the whole sub-module's hot path. It is a one-line Meta change on a 6.13 model plus a migration, so it needs the migration number agreed with any concurrent session (L43) and should be an app-wide pass, not a 6.14 fork.

2. `analytics._category_groups` walks up to `MAX_CLASSIFY_LINES = 5000` lines in Python for the category axis. That is unavoidable given `SpendClassificationRule`'s five match types, it is capped, and the leftover is folded in by exact aggregate difference so the totals stay right — I am flagging it as understood-and-bounded, not as a defect.

3. Recommended `django_assert_max_num_queries` tests for the test-writer agent, each seeded with enough rows that an N+1 shows up (>= 20 findings, >= 3 saved reports, >= 60 invoice lines):
   - `procurement:maverickfinding_list` — assert <= 12 queries on a full 15-row page (catches finding 1; without the fix it grows with the row count).
   - `procurement:spend_export` with `?dimension=none` — assert <= 20 queries (catches findings 2 and 3 together; today it scales with the number of lines in the window).
   - `procurement:classification_workbench` — assert <= 20 queries with >= 10 active rules of mixed match_type (catches finding 4).
   - `procurement:spendreport_detail` on a two-dimension report with `top_n=20` — assert <= 30 queries (catches finding 6).
   - `MaverickSpendFinding.scan(tenant, start, end)` over a window with >= 40 candidates — assert the query count is sub-linear in the candidate count (catches finding 5).
- **frontend-reviewer:** Verified clean and needing no action: all 40+ `{% url %}` targets resolve against apps/procurement/urls/ and apps/scm/urls/ (incl. `scm:purchaseorder_detail`, `scm:contract_detail`, `procurement:supplierinvoiceline_detail`); every pk filter uses `|stringformat:"d"` and never `|slugify`; all three CRUD lists carry `name="q"` + request.GET-reflecting selects, an eye/pencil/trash-2 Actions column with a CSRF POST delete, and an `.empty-state`; all four detail pages carry the Edit / POST-Delete / Back-to-List sidebar (spendreportsnapshot has no Edit by documented design — no form exists); no raw Tailwind colour utilities, no inline colour styles, and no hard-coded left/right (dashboard.html:388 correctly uses `margin-inline-start`); Chart.js is loaded globally in base.html:28 so the two `{% block extra_js %}` charts have their dependency.

Pre-existing / app-wide, NOT actionable for this sub-module:
- `<label class="form-label">` used as a read-only caption with no `for=` and no control appears 22× repo-wide; this sub-module adds three more (maverickfinding/detail.html:107 and :255, spendrule/detail.html:110). A `<dt>` or a plain `<div class="form-label">` would be more correct, but it is an app-wide sweep, not a 6.14 regression.
- Filter search inputs use `aria-label="Search"` rather than `<label for>`; this matches the established 6.x list convention (templates/procurement/invoicevouchermanagement/supplierinvoice/list.html uses the identical markup), so changing it here alone would create inconsistency.
- spendreport/list.html:123-131: the measure badge chain has three `badge-slate` branches identical to its `{% else %}` fallback — the same redundancy class as the chart_type finding, purely cosmetic, folded into notes to avoid duplicating one issue across two lines of the same file.
- spendreportsnapshot/detail.html:45 and export.html:200 print `{{ report.basis_css }}` straight into a class attribute. It is safe today (`BASIS_CSS = {"invoiced": "badge-info", "committed": "badge-slate"}` with a `badge-muted` default, all real classes), but these are the only two places in the sub-module that trust a model CSS helper instead of branching on the CHOICES key — worth knowing if that map is ever edited.
- maverickfinding/list.html:52 uses `stat-icon red`; `.stat-icon.red` does exist in theme.css:260-265, so this is correct despite `red` not being in the older blue/green/orange/purple/slate list.
- **explorer:** VERIFIED CLEAN in my lane (no findings needed): (1) All 31 6.14 url names reverse successfully — I imported the real URLconf under config.settings_test and reversed each one, which also proves `apps/procurement/views/__init__.py`, `models/__init__.py`, `forms/__init__.py` and `admin.py` re-export blocks are complete (a missing name would be an AttributeError at URLconf import). (2) Every `render()`/`crud_*` template path in the six view modules exists on disk (15/15). (3) No banned flat `<entity>_<page>.html` path — the four CRUD entity folders are correct and `dashboard.html`/`category_spend.html`/`export.html`/`maverick_dashboard.html`/`classification_workbench.html` are legitimate sub-module-root standalone pages per template rule 6. (4) All five `LIVE_LINKS[\"6.14\"]` targets reverse, and all five keys match the `parse_catalog()` feature labels for 6.14 byte-for-byte. (5) No `{% url %}` in the new templates names a non-existent route (checked against all 306 procurement route names plus `scm:contract_detail` / `scm:purchaseorder_detail`).

PRE-EXISTING / APP-WIDE (not actionable for 6.14): `spendrule_preview` calls `write_audit_log(..., \"preview\", ...)` and `core.AuditLog.ACTION_CHOICES` is only create/update/delete — but this is an established app-wide pattern (~40 distinct verbs across apps/, several of which, e.g. `tier_approve` and `escalation_run`, also exceed the field's `max_length=10`). `MaverickDashboard.py:249-251` documents the constraint and complies; the rule-preview lane does not. Worth one repo-wide decision, not a 6.14 fix.

HARMLESS DEAD CONTEXT (noted, not filed): `spend_dashboard` passes `drill_url_name` that dashboard.html never reads; `maverick_dashboard` passes `severity_choices`/`status_choices` and `spendrule_list` passes `applies_to_choices`, none of which their templates render. The spendrule list template explicitly explains why `vendors`/`gl_accounts`/`org_units` are present without a matching filter tuple (they feed the empty-state copy), so that one is deliberate.
- **qa-smoke-tester:** FULL SWEEP RESULT (Django test client, admin_acme / password, real seeded MariaDB data; migrate + seed_core + seed_accounts + seed_procurement all idempotent and re-ran clean; `manage.py check` clean; `makemigrations --check --dry-run` = "No changes detected").

url name -> status + content check (GET as admin_acme unless noted):
  spend_dashboard 200 title + 'AeroParcel Express' supplier row | +junk 200 | +filtered(basis=committed,range=last_12_months) 200
  category_spend 200 title + 'Pareto' + league row | +junk 200 | +basis=committed 200
  spend_export 200 title + 'Showing' + SPR numbers | +junk 200 | dimension=supplier/category/department/gl_account/month/none all 200
  spend_export_download 200 text/csv (all 6 dimensions, incl. the empty window)
  classification_workbench 200 title | +junk 200 | basis=invoiced/committed 200
  maverick_dashboard 200 title + all 8 REASON_CHOICES labels present in the reason table | +junk 200
  maverick_scan 405 on GET (POST-only, correct); POST as admin_acme 200 and idempotent (0 new rows); POST as ops_acme 403
  spendrule_list 200 title + all 6 rule names | ?q=a&match_type=vendor&is_active=True 200 | ?category=abc&is_active=abc 200 | ?page=2 200
  spendrule_create 200 (all 12 form fields render) | hostile prefill ?vendor=abc&gl_account=<overflow>&keyword=<300 chars> 200
  spendrule_detail 200 x6 (every seeded row) containing the rule name + match_type display
  spendrule_edit 200 x6 'Edit rule'; spendrule_delete 405 GET / 200 POST round-trip; spendrule_preview 405 GET / 200 POST
  maverickfinding_list 200 title + MSF numbers | ?q=a&status=open&severity=high 200 | junk 200 | ?page=2 200
  maverickfinding_create 200 (15 fields); maverickfinding_detail 200 x14, each containing its own MSF-000NN
  maverickfinding_edit 200 for open rows, 302 -> detail for the 3 disposed rows (the guard is in the view, not just the template)
  maverickfinding_disposition 405 GET / 403 for ops_acme / rejects an unknown verb / refuses `justify` with no note / applies with a note
  spendreport_list 200 title + all 4 SPR numbers and names | filtered 200 | junk 200 | ?page=2 200, and a REAL page 2 (20 temp rows, then deleted) 200
  spendreport_create/edit 200 (18 fields); owner stamped on create and NOT transferred on edit
  spendreport_detail 200 x4 containing number + name; spendreport_export 200 text/csv
  spendreport_run / snapshot / favorite / delete 405 on GET, 200 on the POST round-trip
  spendreportsnapshot_detail 200 containing the snapshot title + parent SPR number; _export 200 csv; _delete 405 GET / 200 POST
  All 5 LIVE_LINKS['6.14'] targets reverse and return 200, and all 5 labels render in the sidebar on both procurement:dashboard and dashboard:home.

Content integrity: NO `{#` / `{% comment` / raw-tag leak on any of the 18 rendered pages. A runtime context-key vs template-root-variable diff over all 15 templates found zero unresolved roots (only the `stringformat` filter name and `obj`, which is correctly absent from the CREATE context and guarded by `{% if obj %}` / `{% if is_edit %}`).

Filters: every declared filter actually narrows the queryset and every dropdown preserves its selection - spendrule match_type (5 values), is_active, category, q; maverickfinding status (5), severity (3), addressable, vendor; spendreport measure, basis, is_favorite. Every row count matched a direct ORM count exactly.

Cross-tenant IDOR: 404 on all 9 GET routes and all 9 POST routes (spendrule detail/edit/preview/delete, maverickfinding detail/edit/disposition/delete, spendreport detail/edit/export/run/favorite/snapshot/delete, snapshot detail/export/delete) with a globex pk while logged in as admin_acme. No leakage.

DB hygiene: every write made during this pass was reverted - the temp page-2 reports, the 144 combination reports, the temp snapshot and the CRUD round-trip rows were deleted, and the one finding I dispositioned was restored, so acme is back at exactly 6 rules / 14 findings / 4 reports / 1 snapshot. All throwaway scripts under temp/ were deleted; no project file was edited and no git command other than `git diff` / `git log` / `git status` was run.

Not actionable / out of scope: `templates/partials/pagination.html` is the shared app-wide partial (pre-existing) that the three 6.14 lists include - it handled page=2/999/abc/-1/0/overflow without a 500. Acme has no OrgUnit-tagged maverick findings, so the department axis on the register renders only its `(unassigned)` bucket, which is the documented 3-hop-nullable-chain caveat rather than a defect.

## Done well

- **code-reviewer:** Tenant discipline is airtight and defence-in-depth: every queryset in the six view modules and in analytics.py is `filter(tenant=request.tenant)` (no `.objects.all()`, no pk-only lookup anywhere), every form FK is narrowed in `__init__` *and* re-checked after POST via `_reject_foreign`, `MaverickSpendFinding.clean()` re-validates all eight FKs including the tenant-less `invoice_line` through its header, and `SpendClassificationRule.resolve()` re-filters a caller-supplied pre-fetched rule list against each line's own workspace so a cached rule list can never classify another tenant's spend.
- **security-reviewer:** Tenant isolation is airtight across all 20 new routes: every one of the 14 `get_object_or_404` calls carries `tenant=request.tenant` (verified line by line), every aggregate in `analytics.py` is tenant-filtered, and all three ModelForms narrow their FK querysets in `__init__` *and* re-check them after the POST via `_reject_foreign` plus a model-level `clean()` backstop — so a crafted POST cannot point a report or a classification rule at another workspace's supplier, GL account or cost centre. `SpendClassificationRule.resolve()` even re-filters the caller's pre-fetched rule list against each line's own tenant rather than trusting it.
- **performance-reviewer:** Aggregates are genuinely derived, never stored, and they are shared rather than repeated per widget: `MaverickFindings._stats` folds four register stat cards into ONE `aggregate()` with `filter=` expressions, `maverick_dashboard` pads a single grouped by-reason query out to the full `REASON_CHOICES` list instead of looping the choices with a query each, and `classified_pct` deliberately returns `(pct, unclassified_value, category_rows)` together so the category classification pass runs once per page rather than twice. The new models are also indexed on exactly the tenant-scoped columns the pages filter and order by — `(tenant, document_date)`, `(tenant, status)`, `(tenant, reason)`, `(tenant, vendor)` on the append-only findings ledger, and `(tenant, dedupe_key)` as a unique_together that backs the scan's upsert lookup.
- **frontend-reviewer:** Every badge in the sub-module branches on the exact frozen CHOICES key (`no_contract`, `po_less_invoice`, `open`/`acknowledged`/`justified`/`remediated`/`dismissed`, `invoiced`/`committed`, …) with a `{{ obj.get_FIELD_display }}` label and a `badge-slate` `{% else %}` fallback, and the templates deliberately do NOT print the models' own `status_css`/`severity_css` helpers into the class attribute — so a backend rename degrades to a styled slate pill instead of an unstyled one. Combined with 100% `{% comment %}` usage for the multi-line design notes (zero `{#` leaks across 3,572 new lines) and only colour-named modifiers on the wire (`badge-green|red|amber|info|muted|slate`, `stat-icon blue|green|orange|purple|slate|red`), both L2 and L33 are clean here by construction rather than by luck.
- **explorer:** Every one of the 15 new templates carries a leading `{% comment %}` block that pins its exact context contract, and I verified all 15 against their views' render() dicts: zero template root-variables are missing from the view context, and the deep shapes agree too (`spend_cube`/`_rows_from_groups` `{label,pk,value,display,pct,count}`, `_scalar` `{value,display,pct}`, `currency_split` `{code,label,display}`, `compute_report` `{summary,columns,rows,chart_*}`). Every nullable FK link on maverickfinding/detail.html is wrapped in `{% if %}` (L10), and every list filter `name=` matches its `crud_list` filter tuple.
- **qa-smoke-tester:** Junk-input hardening on the GET-driven computed pages is genuinely complete, not merely present. Every page degrades a bad parameter to a default rather than raising: `?category=abc`, `?vendor=%C2%B2`, `?org_unit=999999999999999999999`, `?basis=zzz`, `?range=qq`, `?dimension=zzz`, `?date_from=notadate`, `?is_active=abc`, `?addressable=abc` and `?page=abc|-1|0|99999999999999999999` all return 200 with the filter skipped and the page title intact, across all 14 renderable routes. The same holds for the arithmetic: 144 measure x dimension x basis saved-report permutations, a zero-spend window (`date_from=1990-01-01`) and an inverted custom range (`date_from=2030 > date_to=2020`) all render 200 on both the detail page and its CSV with no divide-by-zero and no empty-aggregate crash.
