# Review findings — procurement 6.13 Invoice & Voucher Management

Range: `b1def94a...c11639d387acf425553f184a6e747497a5cd1c68` · Generated: 2026-09-01
Wave (parallel): code-reviewer · security-reviewer · performance-reviewer · frontend-reviewer · explorer · qa-smoke-tester

## Summary

| Severity | Count |
|---|---|
| Critical | 8 |
| Important | 26 |
| Minor | 21 |
| **Total (deduped)** | **55** |

| Agent | Raw findings |
|---|---|
| code-reviewer | 17 |
| security-reviewer | 5 |
| performance-reviewer | 13 |
| frontend-reviewer | 6 |
| explorer | 12 |
| qa-smoke-tester | 2 |

## How to work this file (code-fixer)

Fix in ID order: every `C`, then every `I`, then every `M`. One fix → one file → one `git add` + one
`git commit`. Update each **Status** line to `[x] fixed — <commit subject>` or `[~] skipped — <reason>`
as you go. Never delete a finding; a wrong one gets `[~] skipped — not a defect: <why>`. Never `git push`.

## Critical

### C1 — `apps/procurement/views/InvoiceVoucherManagement/SupplierInvoiceLines.py:226`

- **Found by:** code-reviewer
- **Problem:** `supplierinvoiceline_delete` has no status guard (and no admin gate) while its sibling create/edit views both call `_editable(invoice)` — any logged-in tenant member can POST a delete for a line on an approved/scheduled/paid invoice, and the `invoice.recalc_totals()` on line 241 then rewrites the header subtotal/tax/total so they no longer agree with the `accounting.Bill` and `JournalEntry` already posted by `approve()`.
- **Fix:** Add the same guard the edit view uses, before the delete: after fetching `obj`, `if not _editable(obj.invoice): messages.error(request, f"{obj.invoice.number} is {obj.invoice.get_status_display().lower()} — its lines can no longer be removed."); return redirect('procurement:supplierinvoiceline_detail', pk=pk)`.
- **Status:** [ ] open

### C2 — `apps/procurement/views/InvoiceVoucherManagement/SupplierInvoiceLines.py:226`

- **Found by:** security-reviewer
- **Lesson:** L28
- **Problem:** `supplierinvoiceline_delete` enforces no header-status guard, so any logged-in tenant member can POST-delete a line off an `approved`, `scheduled` or `paid` supplier invoice and the following `invoice.recalc_totals()` silently rewrites the subtotal/tax/total that were already posted to the AP `Bill` and `JournalEntry`, desynchronising the GL from the AP subledger with no way to detect it.
- **Fix:** Mirror the guard both sibling write paths already use (`supplierinvoiceline_create` line 202, `supplierinvoiceline_edit` line 215) before the destructive branch:

```python
@login_required
@require_POST
def supplierinvoiceline_delete(request, pk):
    obj = get_object_or_404(SupplierInvoiceLine.objects.select_related("invoice"),
                            pk=pk, invoice__tenant=request.tenant)
    invoice = obj.invoice
    if not _editable(invoice):
        messages.error(
            request,
            f"{invoice.number} is {invoice.get_status_display().lower()} — its lines can "
            f"no longer be removed.")
        return redirect("procurement:supplierinvoiceline_detail", pk=pk)
    invoice_pk = invoice.pk
    write_audit_log(request.user, obj, "delete")
    obj.delete()
    invoice.recalc_totals()
    ...
```

Pattern-clone sweep for the family (`L28`): `grep -rn -A8 "^def [a-z_]*line_delete" apps/*/views --include=*.py` — `apps/hrm/views/ExpenseManagement/Expenseclaimline.py:62` and `apps/scm/views/ThirdPartyLogistics/ClientBillingRuns.py:589` both DO check the header status; this module is the outlier.
- **Status:** [ ] open

### C3 — `apps/procurement/views/InvoiceVoucherManagement/SupplierInvoices.py:511`

- **Found by:** explorer
- **Lesson:** L44
- **Problem:** `_capture_confirm` requires `line_formset.is_valid()`, but capture.html's stage-2 form (line 128-164) never renders `{{ line_formset.management_form }}` — the POST carries no `lines-TOTAL_FORMS`, so Django appends the `missing_management_form` non-form error and `is_valid()` is always False; the Capture Invoice flow (the sub-module's headline LIVE_LINKS bullet) can therefore never save, and the re-render at line 531 does not pass or show `line_formset`, so the user gets the same page back with no error at all.
- **Fix:** Capture is header-only by design, so drop the formset from this path: delete the `line_formset = SupplierInvoiceLineFormSet(request.POST, instance=None, form_kwargs=…)` construction (lines 509-510), change line 511 to `if form.is_valid():`, and delete the `line_formset.instance = obj` / `line_formset.save()` calls (lines 521-522) — `obj.recalc_totals(save=True)` on a line-less header is still correct. (Alternative, if lines must be keyable at capture: render `{{ line_formset.management_form }}`, the row loop and `line_formset.non_form_errors` in capture.html and add `line_formset` to all three capture render contexts.)
- **Status:** [ ] open

### C4 — `apps/procurement/views/InvoiceVoucherManagement/SupplierInvoices.py:555`

- **Found by:** performance-reviewer
- **Problem:** The Duplicate Invoice Detection board loops over up to DUPLICATE_SCAN_LIMIT (200) invoices and calls `invoice.duplicate_candidates()` per row, which runs its own filtered query (SupplierInvoices.py:531) — 1 + 200 queries on every render of the page, before pagination has even been applied.
- **Fix:** Replace the per-row scan with one grouped query. After building `scanned`, collect `norms = {i.invoice_number_norm for i in scanned if i.invoice_number_norm}` and fetch every peer in ONE query: `peers = SupplierInvoice.objects.filter(tenant=request.tenant, invoice_number_norm__in=norms).select_related('vendor','currency','payment_term')`; bucket them into `by_norm = defaultdict(list)`; then for each scanned invoice build the candidate list from `by_norm[invoice.invoice_number_norm]` (excluding itself) using the same reason/tolerance logic `duplicate_candidates()` applies. Best done by adding an optional `candidates=` argument to `SupplierInvoice.duplicate_candidates(self, limit=10, candidates=None)` that skips the DB hit when the caller supplies the peer list, so the detail page keeps its current call unchanged. Target: 2 queries total for the board.
- **Status:** [ ] open

### C5 — `templates/procurement/invoicevouchermanagement/supplierinvoice/detail.html:351`

- **Found by:** code-reviewer
- **Lesson:** L7
- **Problem:** The loop unpacks two variables (`{% for cand, reasons in duplicate_candidates %}`) but the view passes a list of DICTS (`{"invoice": …, "reasons": …}`); Django's ForNode zips the loopvars over the dict's KEYS, so `cand` becomes the string "invoice", `cand.pk` resolves to '' and `{% url 'procurement:supplierinvoice_detail' cand.pk %}` raises NoReverseMatch — a 500 on the detail page of any invoice that has a duplicate candidate (the seeder creates exactly such a pair: INV-41026 / "INV 41026").
- **Fix:** Change the loop to single-var form and use the dict keys: `{% for cand in duplicate_candidates %}` then `cand.invoice.pk` / `cand.invoice.number` / `cand.invoice.invoice_number` / `cand.invoice.currency` / `cand.invoice.total` / `cand.invoice.invoice_date`, and `{% for reason in cand.reasons %}` at line 359; also update the `obj.duplicate_of.pk == cand.pk` test on line 357 to `cand.invoice.pk`.
- **Status:** [ ] open

### C6 — `templates/procurement/invoicevouchermanagement/supplierinvoice/detail.html:351`

- **Found by:** explorer
- **Lesson:** L7
- **Problem:** `{% for cand, reasons in duplicate_candidates %}` unpacks a DICT — the view passes `[{"invoice": candidate, "reasons": reasons}, …]` (views/InvoiceVoucherManagement/SupplierInvoices.py:217) — so Django's ForNode zips the loop vars against the dict's KEYS, making `cand` the literal string "invoice"; `{% url 'procurement:supplierinvoice_detail' cand.pk %}` then reverses with an empty arg and raises NoReverseMatch, 500ing the invoice detail page for every invoice that has at least one duplicate candidate (the seeder creates such rows).
- **Fix:** Change line 351 to `{% for row in duplicate_candidates %}` and rewrite the body to the dict shape: `{% url 'procurement:supplierinvoice_detail' row.invoice.pk %}`, `{{ row.invoice.number }}`, `{{ row.invoice.invoice_number|default:"no supplier number" }}`, `{% if row.invoice.currency %}{{ row.invoice.currency.code }} {% endif %}{{ row.invoice.total|floatformat:"2" }}`, `{{ row.invoice.invoice_date|date:"M d, Y"|default:"no date" }}`, `{% if obj.duplicate_of and obj.duplicate_of.pk == row.invoice.pk %}`, and `{% for reason in row.reasons %}` — the same shape duplicates.html already uses for `group.candidates`.
- **Status:** [ ] open

### C7 — `templates/procurement/invoicevouchermanagement/supplierinvoice/detail.html:351`

- **Found by:** qa-smoke-tester
- **Lesson:** L7
- **Problem:** The Duplicate-candidates panel unpacks the context as tuples (`{% for cand, reasons in duplicate_candidates %}`) but the view supplies a list of DICTS (`{"invoice": …, "reasons": …}`), so `cand` resolves to the string "invoice", `cand.pk` renders as '' and `{% url 'procurement:supplierinvoice_detail' cand.pk %}` raises NoReverseMatch — every supplier-invoice detail page that has at least one duplicate candidate returns 500 (verified: /procurement/supplier-invoices/136/ SIV-00010 and /137/ SIV-00011 both 500 as admin_acme on seeded data, and the same two rows exist for globex).
- **Fix:** Align the loop with the identical, already-correct panel in templates/procurement/invoicevouchermanagement/duplicates.html:87-101 — iterate the dicts instead of unpacking. Replace line 351 `{% for cand, reasons in duplicate_candidates %}` with `{% for cand in duplicate_candidates %}` and dereference through `cand.invoice` on the lines inside it: line 353 -> `<a href="{% url 'procurement:supplierinvoice_detail' cand.invoice.pk %}" class="fw-600">{{ cand.invoice.number }}</a>`; line 354 -> `{{ cand.invoice.invoice_number|default:"no supplier number" }}`; line 355 -> `{% if cand.invoice.currency %}{{ cand.invoice.currency.code }} {% endif %}{{ cand.invoice.total|floatformat:"2" }}`; line 356 -> `{{ cand.invoice.invoice_date|date:"M d, Y"|default:"no date" }}`; line 357 -> `{% if obj.duplicate_of and obj.duplicate_of.pk == cand.invoice.pk %}`; line 359 -> `{% for reason in cand.reasons %}`. Do NOT change the view — its dict shape is what duplicates.html already consumes.
- **Status:** [ ] open

### C8 — `templates/procurement/invoicevouchermanagement/supplierinvoiceline/list.html:142`

- **Found by:** performance-reviewer
- **Problem:** The line register calls `obj.cumulative_invoiced_qty` and `obj.cumulative_received_qty` inside the `{% for obj in object_list %}` loop; each property fires its own `Sum()` aggregate (SupplierInvoiceLines.py:125-140), so a 15-row page issues 30 extra aggregate queries (1 + 2N) and each one scans SupplierInvoiceLine / GoodsReceiptLine by po_line.
- **Fix:** Precompute both figures in `supplierinvoiceline_list` (apps/procurement/views/InvoiceVoucherManagement/SupplierInvoiceLines.py:102) with two correlated subqueries on the queryset handed to `crud_list`, and read the annotations in the template instead of the properties. Add: `inv_sq = (SupplierInvoiceLine.objects.filter(po_line=OuterRef('po_line')).exclude(invoice__status__in=SupplierInvoice.TERMINAL_STATUSES).exclude(invoice__invoice_type='credit_memo').values('po_line').annotate(s=Sum('quantity')).values('s')[:1])` and `rcv_sq = (GoodsReceiptLine.objects.filter(po_line=OuterRef('po_line')).exclude(goods_receipt__status='cancelled').values('po_line').annotate(s=Sum('quantity_received')).values('s')[:1])`, then `.annotate(cum_invoiced_qty=Subquery(inv_sq), cum_received_qty=Subquery(rcv_sq))`; change template line 142 to `{{ obj.cum_invoiced_qty|default:0|floatformat:"-4" }} / {{ obj.cum_received_qty|default:0|floatformat:"-4" }}`. Add a `django_assert_max_num_queries` test on `procurement:supplierinvoiceline_list` (budget ~8) so the properties cannot creep back into the loop.
- **Status:** [ ] open

## Important

### I1 — `apps/procurement/forms/__init__.py:105`

- **Found by:** explorer
- **Problem:** `SupplierInvoiceLineFormSet` (forms/InvoiceVoucherManagement/SupplierInvoices.py:171) is the only inline formset in the app that is NOT re-exported from the forms package — the block at line 101-105 imports CaptureUploadForm, SupplierInvoiceForm and SupplierInvoiceLineForm but skips it, while every sibling (AsnLineFormSet, ReturnToVendorLineFormSet, ClauseLinkFormSet, …) is imported and listed in `__all__`; `from apps.procurement.forms import SupplierInvoiceLineFormSet` therefore ImportErrors (a trap for the 6.13 test writer).
- **Fix:** Extend the import at line 101-104 to `from .InvoiceVoucherManagement.SupplierInvoices import (CaptureUploadForm, SupplierInvoiceForm, SupplierInvoiceLineFormSet)` and add `"SupplierInvoiceLineFormSet",` to the `__all__` list beside the other *FormSet entries.
- **Status:** [ ] open

### I2 — `apps/procurement/forms/InvoiceVoucherManagement/SupplierInvoices.py:107`

- **Found by:** code-reviewer
- **Problem:** `purchase_order` (line 105-107) and `goods_receipt` (line 109-111) are assigned SLICED querysets (`[:200]`); `ModelChoiceField.to_python` calls `self.queryset.get(pk=…)`, which on a sliced queryset raises `TypeError: Cannot filter a query once a slice has been taken` — caught by Django and re-raised as `invalid_choice`, so every submitted PO or GRN is rejected with "Select a valid choice" and a PO-matched invoice can never be created or edited through the form.
- **Fix:** Remove the `[:200]` slices on lines 107 and 111 (keep the `select_related`/`order_by`); if the dropdown size is a concern, narrow with a filter (e.g. `.exclude(status__in=(...))`) rather than a slice.
- **Status:** [ ] open

### I3 — `apps/procurement/management/commands/seed_procurement.py:210`

- **Found by:** code-reviewer
- **Problem:** The `--flush` block wipes 6.12 and 6.14 rows but never deletes `InvoiceDispute` / `InvoiceMatchVariance` / `SupplierInvoiceLine` / `SupplierInvoice` (all four are imported at lines 83-86 for that purpose), so after `--flush` the 6.13 block still hits its `if SupplierInvoice.objects.filter(tenant=tenant).exists(): skip` guard and 6.13 demo data can never be regenerated.
- **Fix:** Insert children-first deletes after line 210: `InvoiceDispute.objects.all().delete()`, `InvoiceMatchVariance.objects.all().delete()`, `SupplierInvoiceLine.objects.all().delete()`, `SupplierInvoice.objects.all().delete()` (disputes first — variances SET_NULL onto them; invoices last).
- **Status:** [ ] open

### I4 — `apps/procurement/models/InvoiceVoucherManagement/SupplierInvoices.py:338`

- **Found by:** performance-reviewer
- **Problem:** `Meta.ordering = ["-invoice_date", "-id"]` is the ORDER BY of the register, the dashboard's recent/blocked panels and the duplicate scan, but no index covers `(tenant, invoice_date)` — every one of those pages is a tenant-filtered filesort on the module's largest table. The app-wide reference pattern does index the ordering dimension (e.g. scm `(tenant, reported_at)`, `(tenant, started_at)`, `(tenant, read_at)`), so this is a gap in this module, not an app-wide fork.
- **Fix:** Add `models.Index(fields=["tenant", "-invoice_date"], name="prc_siv_tnt_invdate_idx")` to the `indexes` list at line 338 and generate the follow-on migration (next free number after 0021).
- **Status:** [ ] open

### I5 — `apps/procurement/models/InvoiceVoucherManagement/SupplierInvoices.py:855`

- **Found by:** code-reviewer
- **Problem:** `approve()` always debits the expense leg with `subtotal` and credits AP with `total`; for a credit memo (whose subtotal/total are negative by design) this posts JournalLines with a NEGATIVE debit and a NEGATIVE credit, which violates `JournalLine.clean()`'s one-of-debit-or-credit rule and makes `JournalEntry.is_balanced()` return False (it requires `debit > 0`).
- **Fix:** Swap the legs when the total is negative: build `legs` as `[(ap_account, -total, ZERO), (expense_account, ZERO, -subtotal)]` (plus the mirrored tax leg) when `total < ZERO`, keeping the existing orientation otherwise, so every line carries a positive debit or a positive credit.
- **Status:** [ ] open

### I6 — `apps/procurement/models/InvoiceVoucherManagement/SupplierInvoices.py:1031`

- **Found by:** security-reviewer
- **Problem:** `void()` refuses only `is_locked`, so a tenant admin can void an `approved` or `scheduled` invoice whose `JournalEntry` is already posted, leaving a live GL liability behind a document marked void with no reversing entry — the detail template's own confirm text states the intended rule ("reverse it instead if it was already settled") but nothing enforces it.
- **Fix:** Refuse a void on a posted invoice and mirror it in the flag that renders the button:

```python
# models/.../SupplierInvoices.py
def void(self, user, reason=""):
    if self.is_locked or self.journal_entry_id:
        # A posted invoice is undone by reverse(), which mirrors the entry; voiding it
        # would leave the GL liability with nothing to offset it.
        return False
    ...

# views/.../SupplierInvoices.py line 229
"can_void": is_admin and not obj.is_locked and not obj.journal_entry_id,
```

`_refuse(obj, "voided")` already renders a sensible message for the refused POST.
- **Status:** [ ] open

### I7 — `apps/procurement/views/InvoiceVoucherManagement/MatchVariances.py:273`

- **Found by:** performance-reviewer
- **Problem:** The Match Board iterates the ENTIRE filtered variance queryset (no slice) to build `grouped`, sorts the groups in Python and only then paginates — so a workspace with 20k variances materialises 20k joined rows to render 15 cards, and the whole board's memory/CPU cost grows with the table rather than with the page.
- **Fix:** Paginate the GROUPS at the database level first, then fetch only that page's variances. Replace lines 271-282 with: `agg = (rows.values('invoice_id').annotate(oldest=Min('detected_at'), blocking=Count('id', filter=Q(outcome='block')), warn=Count('id', filter=Q(outcome='warn'))).order_by('oldest', '-invoice_id'))`; `page_obj = paginate(request, agg, BOARD_PAGE_SIZE)`; `page_ids = [r['invoice_id'] for r in page_obj.object_list]`; then one query for the page's rows — `page_rows = rows.filter(invoice_id__in=page_ids).select_related(*_ROW_RELATIONS).order_by('-detected_at','-id')` — and rebuild the `groups` dicts from `page_rows` in `page_ids` order (keep the existing `_group()` shape so match_board.html is unchanged). Compute `stats` from a single `rows.aggregate(...)` / `agg` rather than from the full Python list.
- **Status:** [ ] open

### I8 — `apps/procurement/views/InvoiceVoucherManagement/SupplierInvoiceLines.py:55`

- **Found by:** performance-reviewer
- **Lesson:** L18
- **Problem:** `_ROW_RELATIONS` omits four hops the line register renders per row — `po_line__purchase_order` (list.html:113), `receipt_line__goods_receipt` (list.html:121), `invoice__currency` (list.html:136) and `tax_code` (list.html:155) — so a 15-row page adds up to 4N = 60 single-row FK queries on top of the base query.
- **Fix:** Change line 55 to `_ROW_RELATIONS = ("invoice", "invoice__currency", "po_line", "po_line__purchase_order", "receipt_line", "receipt_line__goods_receipt", "item", "gl_account", "tax_code")`. `_DETAIL_RELATIONS` on line 56 then drops its now-duplicated `"tax_code"` and `"invoice__currency"` entries.
- **Status:** [ ] open

### I9 — `apps/procurement/views/InvoiceVoucherManagement/SupplierInvoiceLines.py:77`

- **Found by:** performance-reviewer
- **Problem:** `_line_stats` issues three separate COUNT queries (total, matched, non_po) over the same table on every render of the line register, where the other three lanes in this sub-module do their stat cards in one `.aggregate()` (SupplierInvoices.py:118, MatchVariances.py:79, InvoiceDisputes.py:113).
- **Fix:** Collapse to one aggregate: `agg = SupplierInvoiceLine.objects.filter(invoice__tenant=tenant).aggregate(lines=Count('id'), matched=Count('id', filter=Q(matched_qty=F('quantity'))), non_po=Count('id', filter=Q(po_line__isnull=True)))` and return `{'lines': agg['lines'], 'matched': agg['matched'], 'unmatched': agg['lines'] - agg['matched'], 'non_po': agg['non_po']}` (add `Count, Q` to the `django.db.models` import on line 22).
- **Status:** [ ] open

### I10 — `apps/procurement/views/InvoiceVoucherManagement/SupplierInvoiceLines.py:114`

- **Found by:** qa-smoke-tester
- **Lesson:** L11
- **Problem:** The `("gl_missing", "gl_account__isnull", False)` crud_list filter 500s for every value except the exact strings "True"/"False": `?gl_missing=1`, `?gl_missing=0`, `?gl_missing=on`, `?gl_missing=true` and `?gl_missing=abc` all raise `ValueError: The QuerySet value for an isnull lookup must be True or False.` crud_list's `except (ValueError, ValidationError)` guard cannot catch it because an `__isnull` lookup is only validated at SQL-compile time, so the exception surfaces later inside `paginate()` -> `Paginator.count`, outside the try block. This is the only `__isnull` crud_list filter in the repo.
- **Fix:** Remove `("gl_missing", "gl_account__isnull", False)` from the `filters=[...]` list on line 114 and apply the predicate explicitly before crud_list (same shape as the `overdue` pre-filter in InvoiceDisputes.py:150). In `supplierinvoiceline_list`, build the queryset into a local first, then: `gl_missing = request.GET.get("gl_missing", "").strip()` / `if gl_missing in ("True", "true", "1", "on"): rows = rows.filter(gl_account__isnull=True)` / `elif gl_missing in ("False", "false", "0"): rows = rows.filter(gl_account__isnull=False)` — anything else falls through unfiltered instead of 500ing. Leave templates/procurement/invoicevouchermanagement/supplierinvoiceline/list.html:77-78 as-is (it already emits only "True"/"False").
- **Status:** [ ] open

### I11 — `apps/procurement/views/InvoiceVoucherManagement/SupplierInvoiceLines.py:318`

- **Found by:** performance-reviewer
- **Problem:** `rows = list(qs)` materialises every approved/scheduled invoice with a due date — including rows whose due date falls far outside the requested horizon, which are then dropped by the bucket comprehensions and never rendered — so the page loads an unbounded result set to display at most `overdue + 7×horizon_weeks` days of it.
- **Fix:** Bound the queryset before materialising it: after the vendor/terms/q filters and before line 318 add `horizon_end = today + timedelta(days=7 * horizon_weeks - 1)` and `qs = qs.filter(due_date__lte=horizon_end)`. Every overdue row (due_date < today) and every bucketed row (due_date <= horizon_end) is preserved, so only rows the page never shows are dropped; `stats.invoices` / `discounted_total` then correctly describe the horizon the board is reporting on.
- **Status:** [ ] open

### I12 — `apps/procurement/views/InvoiceVoucherManagement/SupplierInvoices.py:84`

- **Found by:** performance-reviewer
- **Lesson:** L18
- **Problem:** `_ROW_RELATIONS` omits `goods_receipt`, but the register row renders `{{ obj.goods_receipt.number }}` (templates/procurement/invoicevouchermanagement/supplierinvoice/list.html:122-123) — one extra query per row that has a GRN, i.e. 1 + N (16 queries for a 15-row page). The same tuple is reused by the dashboard's `recent`/`blocked` panels and the duplicates board, so the fix pays three times.
- **Fix:** Change line 84 to `_ROW_RELATIONS = ("vendor", "purchase_order", "goods_receipt", "currency", "payment_term")` and drop the now-duplicated `"goods_receipt"` from `_DETAIL_RELATIONS` on line 88. Add a `django_assert_max_num_queries` test on `procurement:supplierinvoice_list` (budget ~10) with a seeded page of invoices that all carry a GRN.
- **Status:** [ ] open

### I13 — `apps/procurement/views/InvoiceVoucherManagement/SupplierInvoices.py:226`

- **Found by:** code-reviewer
- **Problem:** A credit memo can never leave `draft`: no URL/view invokes `capture()`, `park()` or `submit_for_approval()` (grep confirms zero callers), `can_match` excludes credit memos here, and `run_match()` early-returns for them without touching status — so the credit memo minted by `invoicedispute_resolve`/`_spawn_credit_memo` can never be approved and its credit never reaches the ledger.
- **Fix:** Add a POST-only `supplierinvoice_submit` route + view calling `obj.submit_for_approval()` (with `obj.capture()` first when the status is draft/parked), wire it into the urls module next to `match/`, and render its button on the detail Actions card when `obj.status in ('draft','parked','captured','disputed')`.
- **Status:** [ ] open

### I14 — `apps/procurement/views/InvoiceVoucherManagement/SupplierInvoices.py:299`

- **Found by:** code-reviewer
- **Problem:** `supplierinvoice_delete` delegates straight to `crud_delete` with no status guard, so a tenant admin can hard-delete an approved/scheduled/paid invoice that has already posted an `accounting.Bill` and `JournalEntry` — the ledger rows survive with no source document and the invoice's lines, variances and disputes cascade away.
- **Fix:** Before delegating, fetch the row and refuse a posted one: `obj = get_object_or_404(SupplierInvoice, pk=pk, tenant=request.tenant)`; `if obj.journal_entry_id or obj.status not in SupplierInvoice.EDITABLE_STATUSES: messages.error(request, f"{obj.number} has been posted — void or reverse it instead of deleting it."); return redirect('procurement:supplierinvoice_detail', pk=pk)`.
- **Status:** [ ] open

### I15 — `apps/procurement/views/InvoiceVoucherManagement/SupplierInvoices.py:509`

- **Found by:** code-reviewer
- **Problem:** `_capture_confirm` requires `line_formset.is_valid()`, but `templates/.../capture.html` never renders `{{ line_formset.management_form }}` (it has no lines section at all), so the POST carries no `lines-TOTAL_FORMS`; Django appends a `missing_management_form` non-form error and `is_valid()` is always False — the Capture Invoice flow can never save, and the page silently re-renders with no error shown.
- **Fix:** Drop the formset from the capture confirm stage: delete the `SupplierInvoiceLineFormSet(...)` construction on lines 509-510, gate the save on `if form.is_valid():` only, and remove the `line_formset.instance = obj` / `line_formset.save()` calls (lines 521-522) — capture saves a header-only draft and lines are added from the invoice page.
- **Status:** [ ] open

### I16 — `apps/procurement/views/InvoiceVoucherManagement/SupplierInvoices.py:563`

- **Found by:** code-reviewer
- **Problem:** `supplierinvoice_duplicates` passes the FULL `groups` list as `groups` while `page_obj` paginates the same list, and `duplicates.html:41` iterates `groups` — the pagination control renders but every page shows all groups, so "Next" changes nothing.
- **Fix:** Build the page first and pass its slice: `page_obj = paginate(request, groups)` then `"groups": page_obj.object_list, "page_obj": page_obj` — the same shape `invoice_match_board` already uses at MatchVariances.py:282-287.
- **Status:** [ ] open

### I17 — `apps/procurement/views/InvoiceVoucherManagement/SupplierInvoices.py:579`

- **Found by:** security-reviewer
- **Problem:** `supplierinvoice_match` has no status guard and `run_match()` only refuses `is_locked` (paid/void/reversed), so any logged-in non-admin can POST match on an `approved` or `scheduled` invoice whose `Bill` + `JournalEntry` are already posted; `run_match()` resets `status` back to `pending_approval`/`blocked`, after which `approve()` no-ops on its `journal_entry_id` guard and `reverse()` is no longer offered (it requires status `approved`/`paid`), permanently stranding a GL-posted invoice that a plain member just un-approved.
- **Fix:** Refuse the re-match once the invoice has been posted, in the view (the authorization boundary) and mirror it in the `can_match` flag at line 226 so the button disappears:

```python
# views/.../SupplierInvoices.py, inside supplierinvoice_match, after the row is locked
with transaction.atomic():
    obj = get_object_or_404(SupplierInvoice.objects.select_for_update(),
                            pk=pk, tenant=request.tenant)
    if obj.is_locked or obj.journal_entry_id:
        messages.error(request, f"{obj.number} is already posted — reverse it instead of "
                                f"re-matching it.")
        return redirect("procurement:supplierinvoice_detail", pk=pk)
    _status, counts = obj.run_match(request.user)

# line 226
"can_match": (not obj.is_locked and not obj.journal_entry_id
              and obj.invoice_type != "credit_memo"),
```

Add the same `if self.journal_entry_id: return self.status, counts` line beside the existing `is_locked` early-return in `SupplierInvoice.run_match()` (models/.../SupplierInvoices.py:574) so `supplierinvoice_revalidate` and any future caller inherit it.
- **Status:** [ ] open

### I18 — `templates/procurement/invoicevouchermanagement/capture.html:130`

- **Found by:** code-reviewer
- **Problem:** The stage-2 confirm form posts only `stage=confirm` and the header fields; it never emits the `document` pk that `_capture_document()` reads from `request.POST`, so `document` is always None — the uploaded `core.Document` is orphaned and the invoice is saved with `source="manual"`, `extraction_confidence=0` and empty `extraction_raw_text` even when a text layer was read.
- **Fix:** Add `{% if document %}<input type="hidden" name="document" value="{{ document.pk }}">{% endif %}` immediately after the `stage` hidden input on line 130.
- **Status:** [ ] open

### I19 — `templates/procurement/invoicevouchermanagement/capture.html:130`

- **Found by:** explorer
- **Lesson:** L7
- **Problem:** The stage-2 form posts `stage=confirm` but no `document` field, while `_capture_document()` (views/…/SupplierInvoices.py:435) reads `request.POST.get("document")` — so the uploaded `core.Document` is never re-found: the saved invoice gets `document=None`, `source` falls back to "manual" and `extraction_confidence` to 0, silently discarding the attachment the user just uploaded.
- **Fix:** Immediately after the `<input type="hidden" name="stage" value="confirm">` on line 130 add `{% if document %}<input type="hidden" name="document" value="{{ document.pk }}">{% endif %}` (the view already re-validates the pk against `tenant=request.tenant`, so echoing it is safe).
- **Status:** [ ] open

### I20 — `templates/procurement/invoicevouchermanagement/dashboard.html:222`

- **Found by:** code-reviewer
- **Lesson:** L7
- **Problem:** The "Discounts expiring" rows are dicts of shape `{"invoice": invoice, "discount": panel}` (view line 767), but the Discountable column tests `row.discount_amount` / `row.amount` and the Annualised column tests `row.annualised_pct` — none of those keys exist, so both columns silently render "—" for every row on the panel the 6.13 'Early Payment Discount Tracking' bullet deep-links to.
- **Fix:** Use the dict the view actually passes: line 222 → `{% if row.discount.amount %}{{ row.discount.amount|floatformat:"2" }}{% else %}<span class="text-muted">—</span>{% endif %}`, and line 231 → `{% if row.discount.annualised_pct != None %}{{ row.discount.annualised_pct|floatformat:"2" }}%{% else %}…{% endif %}`.
- **Status:** [ ] open

### I21 — `templates/procurement/invoicevouchermanagement/dashboard.html:222`

- **Found by:** explorer
- **Lesson:** L8
- **Problem:** The "Discounts expiring" rows are `{"invoice": …, "discount": _discount_panel(...)}` dicts (views/…/SupplierInvoices.py:767), but the Discountable cell tests `row.discount_amount` / `row.amount` and the Annualised cell (line 231) tests `row.annualised_pct` — none of those keys exist, so both resolve to None inside `{% if %}` and the two money columns of the Early Payment Discount Tracking panel always render an em-dash, i.e. the LIVE_LINKS "#discount" deep-link lands on a panel with no figures.
- **Fix:** In dashboard.html replace lines 221-225 with `{% if row.discount.amount %}{{ row.discount.amount|floatformat:"2" }}{% else %}<span class="text-muted">—</span>{% endif %}` and line 231 with `{% if row.discount.annualised_pct != None %}{{ row.discount.annualised_pct|floatformat:"2" }}%{% else %}<span class="text-muted">—</span>{% endif %}` — `_discount_panel` returns keys base_amount/amount/payable_if_discounted/days_to_discount/annualised_pct/capturable, which is exactly what supplierinvoice/detail.html already reads correctly.
- **Status:** [ ] open

### I22 — `templates/procurement/invoicevouchermanagement/match_board.html:158`

- **Found by:** explorer
- **Lesson:** L7
- **Problem:** The board renders per-variance `{% for action in v.actions %}` (line 149) with a `{% if v.can_accept %}` fallback (line 158), but `invoice_match_board`'s `_group()` (views/…/MatchVariances.py:224-233) puts raw model instances in `variances` and attaches neither attribute — both resolve to nothing, so no card on the Match Board ever offers the Accept verb even though the header comment asserts "Each variance carries a can_accept flag … and an actions collection".
- **Fix:** Once `InvoiceMatchVariance.can_accept` exists (see the matchvariance/list.html finding), the `{% if v.can_accept %}` POST fallback at line 158 starts rendering with no template change; additionally delete the stale `v.actions` loop at lines 144-157 (or have `_group()` build `variance.actions = [{"url": reverse("procurement:matchvariance_accept", args=[variance.pk]), "label": "Accept variance…", "verb": "get", "css": "btn-outline"}] if variance.can_accept else []`) so the template's documented contract and the view agree.
- **Status:** [ ] open

### I23 — `templates/procurement/invoicevouchermanagement/matchvariance/list.html:196`

- **Found by:** explorer
- **Lesson:** L7
- **Problem:** `{% if obj.can_accept %}` gates the Accept button on a per-row flag that nothing supplies — `matchvariance_list` goes through `crud_list` and never annotates rows, and `InvoiceMatchVariance` has no `can_accept` property (models/…/MatchVariances.py:146-160 define only outcome_css/resolution_css/is_blocking/is_open) — so the register's Actions column silently offers view-only and the one human verb in this lane is unreachable from the register.
- **Fix:** Add to `InvoiceMatchVariance` (apps/procurement/models/InvoiceVoucherManagement/MatchVariances.py, beside `is_open` at line 158) a property `can_accept` returning `self.resolution in ("open", "disputed") and not self.invoice.is_locked`; both list and board querysets already `select_related("invoice")`, so it costs no extra query. Have `matchvariance_detail` (views/…/MatchVariances.py:126) use `obj.can_accept` instead of re-deriving the same expression.
- **Status:** [ ] open

### I24 — `templates/procurement/invoicevouchermanagement/supplierinvoice/detail.html:179`

- **Found by:** frontend-reviewer
- **Problem:** In the Lines table the cell under the `PO line` header renders the PO line's text but hrefs to `procurement:supplierinvoiceline_detail` (this invoice's own line), so clicking a PO reference lands on the invoice line — and because the whole anchor sits inside `{% if line.po_line %}`, a non-PO line has no link into its own detail/edit/delete anywhere on the page.
- **Fix:** Split the two concerns. Make the Description cell (line 175) the route into the line: replace `<span class="fw-600">{{ line.description|default:"—" }}</span>` with `<a href="{% url 'procurement:supplierinvoiceline_detail' line.pk %}" class="fw-600">{{ line.description|default:"Invoice line" }}</a>` (unconditional, so non-PO lines are reachable too). Then point line 179's anchor at the purchase order, matching `supplierinvoiceline/list.html:113`: `<a href="{% url 'scm:purchaseorder_detail' line.po_line.purchase_order.pk %}" class="fw-600">{{ line.po_line }}</a>`.
- **Status:** [ ] open

### I25 — `templates/procurement/invoicevouchermanagement/supplierinvoice/detail.html:191`

- **Found by:** performance-reviewer
- **Problem:** The invoice detail lines table calls `line.cumulative_invoiced_qty` and `line.cumulative_received_qty` inside the `{% for line in lines %}` loop; each is a `Sum()` aggregate, so a 10-line invoice costs 20 extra queries on the module's most-visited detail page.
- **Fix:** In `supplierinvoice_detail` (apps/procurement/views/InvoiceVoucherManagement/SupplierInvoices.py:208) build the two maps once after materialising `lines`: `po_ids = [l.po_line_id for l in lines if l.po_line_id]`; `invoiced = dict(SupplierInvoiceLine.objects.filter(po_line_id__in=po_ids).exclude(invoice__status__in=SupplierInvoice.TERMINAL_STATUSES).exclude(invoice__invoice_type='credit_memo').values_list('po_line_id').annotate(s=Sum('quantity')))`; `received = dict(GoodsReceiptLine.objects.filter(po_line_id__in=po_ids).exclude(goods_receipt__status='cancelled').values_list('po_line_id').annotate(s=Sum('quantity_received')))`; then `for l in lines: l.cum_invoiced = invoiced.get(l.po_line_id, ZERO); l.cum_received = received.get(l.po_line_id, ZERO)`. Change template lines 191-192 to `{{ line.cum_invoiced|floatformat:"-4" }}` / `{{ line.cum_received|floatformat:"-4" }}`. Two queries regardless of line count.
- **Status:** [ ] open

### I26 — `templates/procurement/invoicevouchermanagement/supplierinvoice/detail.html:459`

- **Found by:** frontend-reviewer
- **Problem:** The detail Actions card offers Edit, Match, Approve, Override, Schedule, Mark-paid, Reverse, Void and Back-to-List, but no Delete — while `supplierinvoice/list.html:181` does offer it, so the CLAUDE.md "detail Actions sidebar = Edit / POST-Delete / Back to List" contract is broken for this entity only.
- **Fix:** Insert a POST delete form immediately before the `Back to invoices` link at line 459, gated on the same test the `@tenant_admin_required` decorator applies (the view already ships `is_admin` — see `views/InvoiceVoucherManagement/SupplierInvoices.py:231`):
{% if is_admin %}<form method="post" action="{% url 'procurement:supplierinvoice_delete' obj.pk %}" onsubmit="return confirm('Delete {{ obj.number }}? Its lines, variances and disputes go with it. Void the invoice instead if you only need to stop payment.');">{% csrf_token %}<button class="btn btn-danger" type="submit"><i data-lucide="trash-2"></i> Delete</button></form>{% endif %}
Keep the apostrophe-free confirm text (matching the list) so nothing needs escaping inside the event-handler attribute.
- **Status:** [ ] open

## Minor

### M1 — `apps/procurement/forms/InvoiceVoucherManagement/InvoiceDisputes.py:56`

- **Found by:** code-reviewer
- **Problem:** `_as_decimal` returns the name `ZERO`, which is not defined in this module and is not exported by `forms/_common`'s star import (verified: `ZERO` is absent from the module namespace) — a latent NameError whenever `_finite()` returns None.
- **Fix:** Replace `ZERO` with `Decimal("0")` on line 56 (the module already imports `Decimal`), or add a module-level `ZERO = Decimal("0")` next to `_MONEY_CEILING`.
- **Status:** [ ] open

### M2 — `apps/procurement/management/commands/seed_procurement.py:1899`

- **Found by:** code-reviewer
- **Problem:** `_dispute_row` hardcodes `number="DSP-DEMO-<key>"`, which bypasses `TenantNumbered.save()`; because those strings sort above `DSP-0…`, `next_number()` then hits its `int(...)` ValueError fallback and issues `count()+1` for every user-created dispute — a fragile number that can collide (and, after 5 IntegrityError retries, save a dispute with an empty number) once any dispute is deleted.
- **Fix:** Drop the `number=number` kwarg (line 1899) and let `TenantNumbered.save()` mint `DSP-00001…`; key the idempotency check on a business key instead, e.g. `InvoiceDispute.objects.filter(tenant=tenant, invoice=invoice, reason_code=reason).first()`, mirroring the `(vendor, invoice_number)` key the invoice loop already uses.
- **Status:** [ ] open

### M3 — `apps/procurement/models/InvoiceVoucherManagement/MatchVariances.py:129`

- **Found by:** performance-reviewer
- **Problem:** InvoiceMatchVariance is the append-only exception ledger (rebuilt wholesale by every `run_match()`) and is ordered by `-detected_at, -id` on both the register and the Match Board, but no index covers `(tenant, detected_at)` — the sort dimension of the fastest-growing table in the sub-module.
- **Fix:** Add `models.Index(fields=["tenant", "-detected_at"], name="prc_imv_tnt_detected_idx")` to the `indexes` list at line 129 and include it in the same follow-on migration as the SupplierInvoice index.
- **Status:** [ ] open

### M4 — `apps/procurement/models/InvoiceVoucherManagement/SupplierInvoices.py:475`

- **Found by:** security-reviewer
- **Problem:** `cumulative_invoiced_qty` aggregates `SupplierInvoiceLine.objects.filter(po_line=po_line)` with no tenant predicate, so the over-invoicing control — the check that stops a supplier billing the same units twice — sums across every workspace's lines that point at that PO line, and any future path that lets a line reference a foreign PO line feeds another tenant's quantities straight into this tenant's block/allow decision.
- **Fix:** Scope the aggregate to the PO line's own workspace so the control can never read across a tenant boundary:

```python
@classmethod
def cumulative_invoiced_qty(cls, po_line):
    if po_line is None:
        return ZERO
    return (SupplierInvoiceLine.objects
            .filter(po_line=po_line,
                    invoice__tenant_id=po_line.purchase_order.tenant_id)
            .exclude(invoice__status__in=cls.TERMINAL_STATUSES)
            .exclude(invoice__invoice_type="credit_memo")
            .aggregate(s=Sum("quantity"))["s"] or ZERO)
```

`cumulative_received_qty` (line 481) is already safe — `po_line.receipt_lines` is reached through the tenant-verified parent.
- **Status:** [ ] open

### M5 — `apps/procurement/urls/InvoiceVoucherManagement/SupplierInvoices.py:23`

- **Found by:** explorer
- **Problem:** `supplierinvoice_revalidate` is the only 6.13 route with no entry point anywhere — no template, no LIVE_LINKS entry and no view redirect references it — so the admin-only bulk re-match sweep can only be triggered by hand-crafting a POST.
- **Fix:** Add an admin-gated trigger on the exceptions register: in templates/procurement/invoicevouchermanagement/matchvariance/list.html page-actions (around line 36), inside `{% if request.user.is_superuser or request.user.is_tenant_admin %}`, add `<form method="post" action="{% url 'procurement:supplierinvoice_revalidate' %}" onsubmit="return confirm('Re-match every blocked and captured invoice?');">{% csrf_token %}<button class="btn btn-outline" type="submit"><i data-lucide="refresh-cw"></i> Re-match all</button></form>` (the view already redirects back to matchvariance_list).
- **Status:** [ ] open

### M6 — `apps/procurement/views/InvoiceVoucherManagement/SupplierInvoiceLines.py:56`

- **Found by:** performance-reviewer
- **Lesson:** L18
- **Problem:** `_DETAIL_RELATIONS` stops at `po_line` / `receipt_line`, but the line detail page renders `obj.po_line.purchase_order.pk|.number` (detail.html:97) and `obj.receipt_line.goods_receipt.pk|.number` (detail.html:102) — two avoidable single-row queries per detail render.
- **Fix:** Once `_ROW_RELATIONS` gains the chained hops (see the line-register finding), this is covered; otherwise append `"po_line__purchase_order", "receipt_line__goods_receipt"` to `_DETAIL_RELATIONS` at line 56.
- **Status:** [ ] open

### M7 — `apps/procurement/views/InvoiceVoucherManagement/SupplierInvoiceLines.py:335`

- **Found by:** code-reviewer
- **Problem:** Same defect as the duplicates board: `paymentschedule_list` paginates `flat_rows` into `page_obj` but the template renders the full `buckets` list, so the pagination control at payment_schedule.html:171 renders yet every page shows all rows.
- **Fix:** Either drop the `{% include "partials/pagination.html" %}` from payment_schedule.html:171 (the buckets are inherently bounded by the horizon) or restrict each bucket's `rows` to `page_obj.object_list` the way `invoicedispute_aging` does at InvoiceDisputes.py:494-503.
- **Status:** [ ] open

### M8 — `apps/procurement/views/InvoiceVoucherManagement/SupplierInvoices.py:257`

- **Found by:** code-reviewer
- **Problem:** The hand-rolled `_invoice_form` writes `write_audit_log(request.user, obj, "update")` with no `changes` payload, so an invoice edit records that something changed but not what — the audit diff `crud_edit` would have captured via `_changed(form)` is silently dropped (the same applies to `_dispute_form` and `_line_form`).
- **Fix:** Pass the diff on the update branch: `write_audit_log(request.user, obj, "update", {name: str(form.cleaned_data.get(name))[:200] for name in form.changed_data})` (or import and reuse `apps.core.crud._changed`).
- **Status:** [ ] open

### M9 — `apps/procurement/views/InvoiceVoucherManagement/SupplierInvoices.py:732`

- **Found by:** performance-reviewer
- **Problem:** `_discount_qs` returns every open invoice that has a discount date and the dashboard walks all of them in Python (line 761) just to discard the ones whose window has closed — an unbounded scan that grows with the workspace's whole invoice history on a page that is meant to be cheap.
- **Fix:** Filter the closed windows out in SQL: `return (SupplierInvoice.objects.filter(tenant=tenant, status__in=OPEN_STATUSES, discount_expiry_date__gte=timezone.localdate()).select_related(*_ROW_RELATIONS))`. `save()` always writes `discount_expiry_date` whenever `discount_date` is set, so this is exactly the rows the Python `capturable` test keeps; the `.exclude(discount_date=None)` becomes redundant.
- **Status:** [ ] open

### M10 — `apps/procurement/views/InvoiceVoucherManagement/SupplierInvoices.py:796`

- **Found by:** performance-reviewer
- **Problem:** The "Invoice disputes" dashboard tile counts a SLICED list — `len(open_disputes)` where `open_disputes = open_rows[:DISPUTE_LIMIT]` (line 774) — so the tile can never report more than 10 open disputes even when `stats.open_disputes` (built from `len(open_rows)` on line 808) says 40.
- **Fix:** Change line 796 to `"count": len(open_rows)` so the tile and the stat card agree on the same figure; `open_disputes` stays the panel's bounded slice.
- **Status:** [ ] open

### M11 — `templates/procurement/invoicevouchermanagement/capture.html:107`

- **Found by:** frontend-reviewer
- **Problem:** On the `Tax total` extraction row the `"none"` confidence branch renders `badge-slate` while the eight sibling rows (lines 93, 95, 97, 99, 101, 103, 105, 109) all render `badge-muted` for the same value, so one row of the confidence table is visibly a different grey from the rest.
- **Fix:** On line 107 change `{% elif tax.confidence == "none" %}<span class="badge badge-slate">Not found</span>` to `{% elif tax.confidence == "none" %}<span class="badge badge-muted">Not found</span>`, leaving the trailing `{% else %}badge-slate` Unknown fallback as is.
- **Status:** [ ] open

### M12 — `templates/procurement/invoicevouchermanagement/dashboard.html:317`

- **Found by:** explorer
- **Problem:** The Dispute aging card prints the raw bucket keys (`overdue`, `0-7`, `60+`, `none`) because the view passes only the `aging` dict and keeps its `AGING_BUCKETS` label list private (views/…/SupplierInvoices.py:69-77, 816), so the panel reads as machine vocabulary next to the properly labelled dispute_aging.html board.
- **Fix:** Have `invoicevoucher_dashboard` emit label/count pairs — e.g. `"aging": [{"key": key, "label": label, "count": aging.get(key, 0)} for key, label in AGING_BUCKETS]` — and change line 317-319 to `{% for b in aging %}<div class="detail-item"><dt>{{ b.label }}</dt><dd class="fw-600">{{ b.count }}</dd></div>{% endfor %}` (the `{% if aging %}` guard at 312 still works on a list).
- **Status:** [ ] open

### M13 — `templates/procurement/invoicevouchermanagement/duplicates.html:41`

- **Found by:** explorer
- **Problem:** The board iterates `{% for group in groups %}` — the FULL group list from the view — yet includes partials/pagination.html at line 118 over `page_obj = paginate(request, groups)`, so with more than 15 suspect groups the widget reads "Showing 1–15 of N" while all N cards render and `?page=2` returns byte-identical content.
- **Fix:** Either iterate the page slice — change line 41 to `{% for group in page_obj.object_list %}` — or drop the `{% include "partials/pagination.html" %}` at line 118 and stop passing `page_obj` from `supplierinvoice_duplicates` (views/…/SupplierInvoices.py:564).
- **Status:** [ ] open

### M14 — `templates/procurement/invoicevouchermanagement/invoicedispute/detail.html:139`

- **Found by:** explorer
- **Problem:** The "Exceptions board" link falls back to `{% url 'procurement:matchvariance_list' %}?dispute={{ obj.pk }}`, but `matchvariance_list` declares no `dispute` filter (its filters are variance_type/outcome/resolution/basis/invoice — views/…/MatchVariances.py:103-105), so the parameter is silently ignored; the branch is also unreachable because `InvoiceDispute.invoice` is a non-null FK.
- **Fix:** Collapse the conditional at line 139 to the single working form `href="{% url 'procurement:matchvariance_list' %}?invoice={{ obj.invoice_id }}"`, dropping the `?dispute=` else-branch.
- **Status:** [ ] open

### M15 — `templates/procurement/invoicevouchermanagement/match_board.html:149`

- **Found by:** code-reviewer
- **Problem:** `{% for action in v.actions %}` and the `{% if v.can_accept %}` fallback both reference attributes the `invoice_match_board` view never sets on a variance row, so neither branch ever renders — the board can only link to the variance detail page and its accept action is dead markup.
- **Fix:** Either drop lines 144-164 and keep just the detail link, or have `_group()` in MatchVariances.py:224 annotate each variance with `variance.can_accept = variance.resolution in ('open','disputed') and not invoice.is_locked` so the documented fallback actually fires.
- **Status:** [ ] open

### M16 — `templates/procurement/invoicevouchermanagement/payment_schedule.html:171`

- **Found by:** explorer
- **Problem:** `paymentschedule_list` paginates the flattened row list into `page_obj` (views/…/SupplierInvoiceLines.py:335) but the template renders every row of every bucket (line 117) and then includes the pagination partial, so the pager is decorative: page 2 shows the same rows as page 1.
- **Fix:** Bucket only the paginated slice — build `page_obj` first and pass `rows` per bucket filtered to `page_obj.object_list` — or, simpler and consistent with the page's bucketed intent, remove the `{% include "partials/pagination.html" %}` at line 171 and stop passing `page_obj` from the view.
- **Status:** [ ] open

### M17 — `templates/procurement/invoicevouchermanagement/supplierinvoice/detail.html:410`

- **Found by:** frontend-reviewer
- **Problem:** `<label class="form-label">Notes</label>` labels nothing — there is no `for=` and no wrapped form control, only a read-only `<div>`, which is an invalid label association and makes a screen reader announce a form field that does not exist.
- **Fix:** Replace the orphan `<label class="form-label">` with `<div class="form-label">` (same styling, no label semantics) on this line. The same orphan-label pattern repeats at `invoicedispute/detail.html:94` (Description) and `:127` (Resolution note), `matchvariance/detail.html:122` (Explanation) and `:129` (Message), and `matchvariance/form.html:78` (Message) — sweep all six. Leave the genuine labels that do carry `for=` (e.g. `matchvariance/form.html:96` `for="id_note"`) untouched.
- **Status:** [ ] open

### M18 — `templates/procurement/invoicevouchermanagement/supplierinvoice/list.html:34`

- **Found by:** frontend-reviewer
- **Lesson:** L33
- **Problem:** The `Blocked` stat card uses `stat-icon orange` because the header comment at line 13 states "stat-icon is limited to blue/green/orange/purple/slate — there is no approved red", but `.stat-icon.red` has existed in theme.css since commit cfb1bcea7 (theme.css:265), so the worst-severity tile renders in the warning colour and is indistinguishable from `Overdue`.
- **Fix:** Change line 34 to `<div class="stat-icon red">` (and, for the same reason, line 37 `Overdue`). Then correct the now-stale claims in the `{% comment %}` headers that assert red is unavailable: this file lines 13-14, `invoicedispute/list.html:15-16`, `matchvariance/list.html:27` and `dashboard.html:13`. Do NOT add `amber` — that variant genuinely does not exist.
- **Status:** [ ] open

### M19 — `templates/procurement/invoicevouchermanagement/supplierinvoiceline/form.html:31`

- **Found by:** frontend-reviewer
- **Problem:** When `invoice` is falsy the template renders the "No invoice to add a line to" empty state at lines 20-29 and then still renders the whole `<form>` below it, so the user is shown a dead-end message immediately followed by a fillable form whose POST the view will reject.
- **Fix:** Turn the guard into an either/or: change line 20 from `{% if not invoice %}` to `{% if not invoice %}` … `{% else %}`, move the `{% endif %}` from line 29 down to just after the closing `</form>` on line 105, so the form only renders when `invoice` is present. On the edit path `invoice` is always set, so nothing is lost.
- **Status:** [ ] open

### M20 — `templates/procurement/invoicevouchermanagement/supplierinvoiceline/list.html:160`

- **Found by:** code-reviewer
- **Problem:** The Actions column offers Edit and Delete on every line regardless of the parent invoice's status; the edit view redirects with an error and (once the Critical guard above lands) the delete will too, so the buttons offer moves the user cannot make — the CLAUDE.md rule is to wrap status-dependent Edit/Delete in a condition.
- **Fix:** Wrap lines 160-170 in `{% if obj.invoice.status == 'draft' or obj.invoice.status == 'parked' or obj.invoice.status == 'captured' %}…{% endif %}`, leaving the View icon unconditional.
- **Status:** [ ] open

### M21 — `templates/procurement/invoicevouchermanagement/supplierinvoiceline/list.html:168`

- **Found by:** security-reviewer
- **Problem:** The line register renders the Delete POST form unconditionally (the list view supplies no per-row editability flag), so the bin icon is offered on lines of approved, scheduled and paid invoices — the button that drives the Critical finding above, and after that view gains its guard it becomes a button that only buys the user a refusal.
- **Fix:** Gate the form on the header's editable window, which is already `select_related` through `_ROW_RELATIONS` so there is no extra query. Add a property on the child model:

```python
# apps/procurement/models/InvoiceVoucherManagement/SupplierInvoiceLines.py
@property
def is_editable(self):
    from apps.procurement.models.InvoiceVoucherManagement.SupplierInvoices import SupplierInvoice
    return self.invoice.status in SupplierInvoice.EDITABLE_STATUSES
```

and wrap both row actions:

```html
{% if obj.is_editable %}
  <a href="{% url 'procurement:supplierinvoiceline_edit' obj.pk %}" class="btn-icon" ...></a>
  <form method="post" action="{% url 'procurement:supplierinvoiceline_delete' obj.pk %}" onsubmit="...">
    {% csrf_token %}<button class="btn-icon danger" type="submit" ...></button>
  </form>
{% endif %}
```

(The entity's own detail page already gates both on `can_edit` at lines 194 and 204 — this is the same rule, applied on the register.)
- **Status:** [ ] open

## Notes — app-wide / pre-existing (NOT in the fix queue)

- **code-reviewer:** Scope: reviewed `git diff b1def94a...c11639d3` (50 files). HEAD is 3fa1d7ae, but `git log c11639d3..HEAD -- apps/procurement/{views,models,forms}/InvoiceVoucherManagement templates/procurement/invoicevouchermanagement` is empty, so the on-disk files I read are byte-identical to the reviewed changeset.

Clone-family sweep: the "paginate a list but render the unpaginated list" shape appears twice in this changeset (duplicates board, payment schedule). `grep -rn "page_obj.*paginate(request, \(groups\|buckets\|rows\|flat_rows\))" apps/*/views/` will find the same shape in other computed-board modules. The "dict passed to the template, template reads flat attributes" shape (dashboard discount panel, invoice detail duplicate candidates) is worth a `grep -rn "{% for .*,.* in " templates/` sweep app-wide — Django unpacks a 2-key dict into its KEYS without raising.

Not actionable / observations only:
- `matchvariance_accept` is `@login_required` only, while the commit message and `InvoiceVarianceAcceptForm`'s docstring both describe it as the "admin accept verb". The view and the `can_accept` template flag agree with each other (no hidden-button/403 mismatch) and accepting a variance does not move money or unblock an invoice on its own, so I did not raise it as an authorization finding — but the docstrings should be corrected or the gate added, whichever matches intent.
- `SupplierInvoice` model verbs `park()`, `unpark()`, `send_back()`, `unschedule()`, `block()` and `raise_dispute()` have no callers anywhere; `status='disputed'` is therefore unreachable through the UI even though the register filters and badges for it. Dead model surface rather than a defect.
- `templates/.../capture.html:12` states "pdfplumber is not in requirements.txt", which the final commit of this changeset made untrue.
- `apps/core/navigation.py` `_route_name()` already strips `#fragment`, so the new `invoicevoucher_dashboard#discount` LIVE_LINKS entry reverses correctly — verified, not a finding.
- **security-reviewer:** Out-of-lane observations, recorded for the other reviewers rather than the fix queue:

1. `templates/procurement/invoicevouchermanagement/capture.html` (the stage-2 `<form>` at line 128) posts neither a hidden `document` input nor `line_formset.management_form`. `_capture_document()` therefore always returns `None` (so the uploaded attachment and the `pdf_text_layer` provenance are dropped and `source` falls back to `"manual"`), and `SupplierInvoiceLineFormSet(request.POST, instance=None, ...)` fails with a `missing_management_form` non-form error the template never renders — Django 5.1 appends it rather than raising, so "Save as a draft invoice" silently re-renders the same page and the confirm stage can never save. Contract/QA lane; not a security defect (it fails closed).

2. `matchvariance/list.html:197` gates the Accept button on `obj.can_accept`, but `matchvariance_list` never annotates rows with `can_accept` — only `matchvariance_detail` computes it. The button is therefore never rendered on the register. Fails closed, so frontend/contract lane.

3. `matchvariance_accept` is `@login_required` only and `can_accept` includes rows with `outcome == "block"`, so a plain member can dispose of a *blocking* three-way-match exception one at a time — the same decision `supplierinvoice_override` reserves for `@tenant_admin_required`. Impact is bounded because `accept()` moves only `resolution` and never the header status (the invoice stays `blocked`), and the next `run_match()` deletes and rebuilds the rows, so acceptance cannot by itself carry an invoice to approval. Called out as a design asymmetry rather than a finding.

4. Pre-existing and app-wide: `next_number()` in `apps/core/utils.py` is a non-atomic max+1, so two concurrent creates of the same prefix in one tenant can collide on `unique_together (tenant, number)`. Already documented in that docstring as a cross-module follow-up; 6.13's four new numbered entities inherit it.

5. `_capture_upload` creates a `core.Document` row (and stores the file) on every upload POST, before any invoice exists, with no cleanup for abandoned sessions. Storage growth only — no authorization consequence, and the extension/size allowlist from `apps/core/forms/_common.py` is correctly applied.
- **performance-reviewer:** Out-of-lane observations, recorded only: (1) templates/procurement/invoicevouchermanagement/dashboard.html:222 and :231 read `row.discount_amount` / `row.annualised_pct`, but `expiring` rows are dicts shaped `{"invoice": ..., "discount": panel}` (SupplierInvoices.py:767) — the lookup silently fails and the discount column renders the em-dash fallback; it should be `row.discount.amount` / `row.discount.annualised_pct`. That is a context-key mismatch (L7/L8), not a query issue, so I have left it for the frontend/code-review lanes. (2) `SupplierInvoice.run_match()` issues 2-3 aggregate queries per invoice line (cumulative_received/cumulative_invoiced at model lines 671-687); that is a POST-only write path bounded by the line count of one document, and the seeder only matches three invoices, so I did not file it — but if a bulk "revalidate" sweep (`supplierinvoice_revalidate`, which re-matches every blocked/captured invoice under one lock) ever runs over hundreds of invoices it will be the hot spot, and the same two subqueries used in the line-register fix would flatten it. (3) The seeder's per-row `.create()` loop is correct as written — `SupplierInvoiceLine.save()` derives `line_total` and cascades `recalc_totals()`, so `bulk_create` does not fit; volume is ~16 invoices / ~20 lines per tenant. (4) Missing indexes on ordering columns look like a wider pattern worth an app-wide pass: several sibling modules index `(tenant, <status>)` and `(tenant, <fk>)` but not the `Meta.ordering` date, so the two index findings above may repeat across procurement/scm registers.
- **frontend-reviewer:** Verified clean, no action needed: all 22 distinct `{% url 'procurement:…' %}` names in the changeset resolve against `apps/procurement/urls/InvoiceVoucherManagement/*`, and the two cross-app links (`scm:purchaseorder_detail`, `scm:goodsreceipt_detail`) exist. All FK pk filters use `|stringformat:"d"` (never `|slugify`) and every select re-selects from `request.GET`. Every nullable FK that feeds a filter argument (`assigned_to.get_full_name|default:…username`, `raised_by`, `approved_by`, `dispute`, `credit_memo_invoice`) sits inside an `{% if %}` guard — L10 is respected throughout. Every table is wrapped in `.table-wrap`; there are no raw Tailwind colour utilities and no hard-coded left/right, so dark mode and RTL are unaffected. All confirm() strings are apostrophe-free and interpolate only system-assigned numbers or integer pks, and the delete forms use `onsubmit="return confirm(...)"` on the form rather than `onclick` on the button, which also covers Enter-key submission — better than the CLAUDE.md pattern.\n\nApp-wide observations, not actionable here: (1) `.filter-bar` (theme.css:350, `flex-wrap`) is reused as the button row in every Actions card (`supplierinvoice/detail.html:420`, `invoicedispute/detail.html:247`, `matchvariance/detail.html:169`, `supplierinvoiceline/detail.html:193`). It is a semantic stretch, but `.form-actions` has no `flex-wrap` and would overflow with 8 buttons, so the choice is pragmatic — the design system arguably wants a `.action-bar` class rather than a change to these templates. (2) `.table-actions` carries `justify-content: flex-end`, so its use outside a table cell in `match_board.html:142` right-aligns those buttons inside the `<details>` body; cosmetic only. (3) Search inputs and filter selects across the whole app use `aria-label` rather than a visible `<label for>`; these templates follow that existing convention consistently, so I did not flag it per-file. (4) `dispute_aging.html` and `duplicates.html` have no `name=\"q\"` search box, but both are standalone report/board pages (template-structure rule 6) whose view contracts pin no `q` key, so this is a scope question for the backend, not a template defect.
- **explorer:** App-wide / out-of-scope observations, not for the fix queue:
- Template folder shape is compliant: entity CRUD lives at `templates/procurement/invoicevouchermanagement/<entity>/{list,detail,form}.html` and the six standalone boards (capture, dashboard, duplicates, match_board, payment_schedule, dispute_aging) sit at the sub-module root, which the CLAUDE.md rule permits. No banned flat `<entity>_<page>.html` file shipped.
- The three sub-package `__init__.py` files (models/forms/views/InvoiceVoucherManagement) deliberately carry no re-export block to avoid a star-import cycle; the app-level packages import the entity modules directly, which is consistent and works. Only the missing `SupplierInvoiceLineFormSet` line is a real gap.
- `InvoiceDispute.withdraw()` (models/…/InvoiceDisputes.py:341) has no route and no caller — dead code by design per dispute_aging.html's comment, left as-is.
- `invoice_match_board`'s sort key `(group[\"oldest_at\"] is None, group[\"oldest_at\"], -pk)` would raise TypeError comparing two `None` values, but `detected_at` is `auto_now_add` and non-null so `oldest_at` can never be None in practice — not worth a change.
- Pagination-over-a-fully-rendered-list is a repeating shape in this app's board pages (duplicates, payment_schedule); worth a sweep across the other computed boards (6.11/6.12) in a separate pass rather than as part of this sub-module's fixes.
- **qa-smoke-tester:** RUNTIME SETUP: `manage.py migrate` (no pending migrations), `seed_core`, `seed_accounts`, `seed_procurement` all clean; seed_procurement is idempotent (second run reported "already present, skipping" for every 6.13 lane). Acme has 25 invoices / 35 lines / 16 variances / 6 disputes — enough for page 2 on three registers.

SWEEP RESULT (as admin_acme, in-process test client, raise_request_exception=False):
- Pass 1, 83 checks -> 0 failing. 22 GET-able routes + module landing, one filtered list per register, `?category=abc` junk on every list, junk-int (`?vendor=abc`, `?invoice=abc`, `?supplier=abc`), `?page=2` on all four paginated registers, `?page=999`, 16 POST-only verbs -> 405, 8 IDOR probes -> 404. All statuses in (200, 302, 405, 404) as designed; all content assertions passed (page titles, sampled `str(obj)` tokens on every detail).
- Pass 2, content depth -> 0 failing. All five LIVE_LINKS["6.13"] targets resolve and are reachable, including the `#fragment` form `procurement:invoicevoucher_dashboard#discount` (navigation._safe_reverse splits the suffix correctly and the dashboard really does carry `id="discount"` at dashboard.html:190). All five bullets render in the sidebar under the "6.13 Invoice ..." heading. Filtered lists render the sampled row; detail pages render their lines, variances, tolerances and discount panels.
- Pass 3, 130-URL junk/empty battery -> 1 failure (the gl_missing finding). Covered `?page=abc/-1/0/99999`, superscript-digit FK values (`?vendor=²`), over-range pks (999999999999999999999), NUL/quote/`<script>` in `?q`, `?weeks=0/-3/99999` on the payment schedule, `?bucket=²` on the aging board, and a `?q=zzzzzzzzzzzz` zero-row empty state (plus empty-state + page 2) for all 8 lists/boards.
- Pass 4, exhaustive per-row render -> 2 failures (both the duplicate-candidates Critical). Rendered the detail page of EVERY seeded acme row: 25 invoices (all statuses/types incl. credit_memo), 35 lines, 16 variances (+ 16 accept confirmations), 6 disputes; then every edit form and every `?invoice=<pk>`-pointed create form (0 failures).
- Pass 5, near-empty tenant (SMOKETEST Acme, 9 invoices / 0 variances / 0 disputes) -> all 12 pages 200. No division-by-zero or empty-bucket crash on the dashboard, match board, aging board or payment schedule.
- Invalid-POST re-render probes (empty POST to both create + both edit forms, tampered formset ManagementForm `lines-TOTAL_FORMS=abc`, over-long variance note, bogus `resolution=zzz`, and all five capture-stage permutations incl. `stage=zzz` / `document=abc`) all returned 200/302 with errors, never 500.

NOT ACTIONABLE FOR THIS SUB-MODULE (pre-existing / out of range):
- The root cause of the gl_missing 500 is a gap in the shared `apps/core/crud.py:99-104` guard: it wraps only the `.filter()` call, but `__isnull` (and any other lazily-validated lookup) raises at SQL-compile time inside `paginate()`. Hardening crud_list to coerce/skip non-boolean values for `*__isnull` lookups would fix this class repo-wide, but apps/core/crud.py is outside the b1def94a...c11639d3 range, so the finding above is scoped to the 6.13 view instead.
- `seed_procurement` emits naive-datetime RuntimeWarnings for `PurchaseRequisition.created_at` (6.2, pre-existing) — noise only, no effect on 6.13.
- `apps/procurement/urls/__init__.py` shows a concurrent 6.14 sub-module already splatted after 6.13; its first segments (`spend/`, `spend-rules/`, …) do not collide with any 6.13 segment, and the 6.13 landing page resolved cleanly, so the appended-last ordering holds.

## Done well

- **code-reviewer:** The tenant boundary is genuinely airtight across all four lanes: every queryset is `filter(tenant=request.tenant)` (or `invoice__tenant=` for the tenant-less child), every privileged verb re-fetches under `select_for_update()` inside `transaction.atomic()`, the model verbs re-check their own guard so a direct POST cannot skip a state, and `approve()`'s `if self.journal_entry_id: return False` double-submit guard means a double-clicked approval cannot mint a second Bill/JournalEntry. Every int GET filter goes through `as_db_int` (L11) and the package split + `__init__.py` re-exports are complete and correct.
- **security-reviewer:** The form layer is the strongest part of this sub-module: every tenant-scoped FK is narrowed in `__init__` AND independently re-checked in `clean()` via `_reject_foreign`, the two tenant-less scm children (`PurchaseOrderLine`/`GoodsReceiptLine`) are checked through their own headers because `_reject_foreign` cannot see a `tenant_id` on them, `tenant=None` empties every dropdown rather than offering another workspace's rows, and every system-owned column (`status`, `number`, `bill`, `journal_entry`, `invoice_number_norm`, all four derived money columns, `source`/`extraction_confidence`, `approved_by`/`approved_at`, the dispute's `supplier`/`resolution`/`raised_by`) is kept out of `Meta.fields` — mass assignment has no surface here. Tenant scoping is likewise clean: every one of the 40+ ORM calls in the changeset carries `tenant=request.tenant` or `invoice__tenant=request.tenant`, every `get_object_or_404` is tenant-scoped, `crud_delete` is only used on models that actually have a `tenant` column, and the child `SupplierInvoiceLine` correctly gets a hand-rolled delete rather than the parent helper. Every POST form in all 18 new templates carries `{% csrf_token %}`; there is no `|safe`, no `mark_safe`, no `{% autoescape off %}`, no `<script>` block, no `@csrf_exempt`, no `?next=` redirect, no raw SQL, and no user value in an inline `style=`.
- **performance-reviewer:** Derived money is genuinely derived, never stored-and-drifted: `SupplierInvoice.recalc_totals()` re-sums from the lines, and `cumulative_invoiced_qty` / `cumulative_received_qty` are `Sum()` aggregates over live rows rather than counter columns — plus three of the four lanes build their whole stat-card row in a single `.aggregate(Count(..., filter=Q(...)))` (SupplierInvoices.py:118, MatchVariances.py:79, InvoiceDisputes.py:113), which is exactly the one-query-per-card rule. `InvoiceMatchVariance.__str__` deliberately prints `self.invoice_id` instead of `self.invoice` with a comment saying why — the L18 chained-`__str__` fan-out was consciously avoided.
- **frontend-reviewer:** Badge fidelity is the strongest part of this sub-module: across all 18 templates every `{% if %}`/`{% elif %}` chain compares the *exact* CHOICES key frozen in the models (`total_amount`, `quantity_no_receipt`, `duplicate_suspect`, `pending_approval`, `awaiting_internal`… all verified against `models/InvoiceVoucherManagement/*.py`), every chain ends in an `{% else %}` `badge-slate` branch carrying `{{ obj.get_FIELD_display }}`, and every modifier used is a real colour-named theme.css class — zero `badge-success`/`-danger`/`-warning` regressions despite the author explicitly writing about them in the comments. Equally good: not one `{# … #}` leak (every multi-line note is a proper `{% comment %}`…`{% endcomment %}`, L2 clean), and pagination is delegated to the L9-safe `partials/pagination.html` on all six paged pages rather than hand-rolled — so `previous_page_number`/`next_page_number` are guarded and the filter query string survives paging for free.
- **explorer:** The url→view wiring is airtight: all 37 `views.<name>` references in the four 6.13 URL modules exist in `apps/procurement/views/__init__.py`, every one of the ~40 `{% url 'procurement:…' %}` names used across the twelve new templates resolves to a declared route, the two cross-app links (`scm:purchaseorder_detail`, `scm:goodsreceipt_detail`) are real, and all five `LIVE_LINKS[\"6.13\"]` targets reverse cleanly — including the `#discount` fragment, whose anchor genuinely exists at dashboard.html:190.
- **qa-smoke-tester:** Cross-tenant isolation is airtight across all four entities: every one of the 8 IDOR probes (supplierinvoice_detail/edit, supplierinvoiceline_detail/edit, matchvariance_detail/accept, invoicedispute_detail/edit) returned 404 with a globex pk while logged in as admin_acme, and the child entity SupplierInvoiceLine — which has no tenant column — is correctly scoped through `invoice__tenant=request.tenant` on every read AND on `?invoice=<globex pk>` in the create route (302 refusal, not a graft). Every one of the 16 POST-only verbs returned 405 on GET rather than executing or 500ing, and all 8 list/board pages render their title, stat cards and real seeded rows with zero `{#` / `{% comment` / `{{` / `{%` leaks in both populated and zero-row states.
