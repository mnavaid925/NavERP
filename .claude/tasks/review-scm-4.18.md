# Review findings — scm 4.18 Finance & Accounting Integration

Range: `ac4d600bdb69535b463c2f2adec91bfcdee68495...HEAD` · Generated: 2026-08-15
Wave (parallel): code-reviewer · security-reviewer · performance-reviewer · frontend-reviewer · explorer · qa-smoke-tester

## Summary

| Severity | Count |
|---|---|
| Critical | 0 |
| Important | 4 |
| Minor | 11 |
| **Total (deduped)** | **15** |

| Agent | Raw findings |
|---|---|
| code-reviewer | 4 |
| security-reviewer | 2 |
| performance-reviewer | 4 |
| frontend-reviewer | 2 |
| explorer | 2 |
| qa-smoke-tester | 1 |

## How to work this file (code-fixer)

Fix in ID order: every `C`, then every `I`, then every `M`. One fix → one file → one `git add` + one
`git commit`. Update each **Status** line to `[x] fixed — <commit subject>` or `[~] skipped — <reason>`
as you go. Never delete a finding; a wrong one gets `[~] skipped — not a defect: <why>`. Never `git push`.

## Important

### I1 — `apps/scm/forms/FinanceIntegration/LandedCostVouchers.py:149`

- **Found by:** performance-reviewer
- **Lesson:** L18
- **Problem:** The `freight_invoice` dropdown on the landed-cost charge form uses `select_related("carrier")` only, but `FreightInvoice.__str__` renders `self.carrier.name`, and `Carrier.name` is a PROPERTY that reads `self.party.name` (apps/scm/models/TransportationManagement/Carriers.py:104-107) — so rendering the <select> fires one extra query per option (1 + N queries, e.g. 1 + 180 on a workspace with 180 freight invoices) on both `landedcostcharge_create` and `landedcostcharge_edit`.
- **Fix:** Change `.select_related("carrier")` to `.select_related("carrier__party")` on the `freight_invoice` queryset (line 149). This is the app-wide reference pattern — apps/scm/views/TransportationManagement/FreightInvoices.py:75,99,118 and apps/scm/views/ContractCompliance/TradeDocuments.py:84 all already use `select_related("carrier__party")` for exactly this reason.
- **Status:** [ ] open

### I2 — `apps/scm/forms/FinanceIntegration/LandedCostVouchers.py:152`

- **Found by:** code-reviewer
- **Problem:** `LandedCostChargeForm` narrows `gl_account` and `tax_code` to `is_active=True` (and `party` to `_carrier_parties`) without unioning the currently-stored value back in, so opening the edit form for a charge whose GL account or tax code was deactivated afterwards renders no matching <option>, the browser posts an empty value, and the optional FK is silently NULLed on save — losing the expense account that `draft_bill()` copies onto the vendor bill line, with no validation error to warn anyone.
- **Fix:** After the three narrowing assignments in `LandedCostChargeForm.__init__` (lines 147-157), union the stored pk back in for each optional narrowed FK, e.g. `for name, base in (("gl_account", GLAccount.objects.all()), ("tax_code", TaxCode.objects.all()), ("party", Party.objects.all())): _keep_current(self, name, base)` — reusing the same helper `forms/FinanceIntegration/DutyTariffs.py:67` already defines for exactly this case. (Rated Important rather than Minor because it is silent data loss on a mainline edit path; I am unsure only because it requires the referenced master row to have been deactivated first.)
- **Status:** [ ] open

### I3 — `apps/scm/forms/FinanceIntegration/LandedCostVouchers.py:180`

- **Found by:** explorer
- **Problem:** `DutyTariff.rate_for()` is never called from any view, form or template — grep shows the only caller in the whole repo is `seed_scm.py:5639` — so the sub-module's "Tax Management" master (full CRUD + `LIVE_LINKS["4.18"]["Tax Management"]`) feeds nothing at runtime, while `duty_rate_pct`'s help_text (line 176-178) and `templates/scm/finance/landedcostcharge/form.html:130` both tell the user the rate is "snapshotted from the duty tariff" — a promise the request path never keeps, leaving the user to retype every rate by hand.
- **Fix:** In `LandedCostChargeForm.clean()` (line 180, after the existing `_reject_foreign` call), default the rate when the user left it blank: if `cleaned.get("charge_type") == "duty"` and `not cleaned.get("duty_rate_pct")` and `cleaned.get("hs_code")`, call `DutyTariff.rate_for(self.tenant, cleaned["hs_code"], cleaned.get("country_of_origin", ""), self.voucher.cost_date if self.voucher else None)` and, when it returns a tariff, set `cleaned["duty_rate_pct"] = tariff.duty_rate_pct`. Guard on `charge_type == "duty"` only — `LandedCostCharge.clean()` (models/FinanceIntegration/LandedCostVouchers.py:690) rejects a non-zero rate on any other charge type. Import `DutyTariff` alongside the existing `from apps.scm.models import (...)` block at line 32.
- **Status:** [ ] open

### I4 — `apps/scm/models/InventoryManagement/Items.py:250`

- **Found by:** security-reviewer
- **Lesson:** L35
- **Problem:** `apply_landed_cost()` writes `average_cost + total_amount/on_hand` into `Item.average_cost`, a `DecimalField(max_digits=14, decimal_places=4)` capped at 9,999,999,999.9999, with a clamp on the LOW end only — so a landed-cost charge that is large relative to the receipt's on-hand (charge/on_hand > 1e10) makes `.save()` raise `DataError: Out of range value` inside `LandedCostVoucher.allocate()`, an uncaught 500 on the Allocate button (or, with MySQL strict mode off, a silently truncated inventory valuation).
- **Fix:** Clamp both ends before quantizing. `LandedCostCharge.estimated_amount` / `actual_amount` are `DecimalField(14, 2)` with only `MinValueValidator(ZERO)`, so any logged-in member can enter up to 999,999,999,999.99 and nothing between the form and the column bounds the quotient. In `apps/scm/models/InventoryManagement/Items.py`, add a module constant and use it:

```python
#: The widest value Item.average_cost — DecimalField(max_digits=14, decimal_places=4) — can hold.
MAX_AVERAGE_COST = Decimal("9999999999.9999")

    def apply_landed_cost(self, total_amount):
        ...
        moved = (self.average_cost or ZERO) + (total_amount / on_hand)
        self.average_cost = min(MAX_AVERAGE_COST,
                                max(ZERO, moved)).quantize(Decimal("0.0001"))
        self.save(update_fields=["average_cost", "updated_at"])
```

This is the same shape `LandedCostVoucher.MAX_VARIANCE_PCT` / `MAX_BILL_TAX_RATE_PCT` already use for their narrower columns.
- **Status:** [ ] open

## Minor

### M1 — `apps/scm/forms/FinanceIntegration/DutyTariffs.py:67`

- **Found by:** code-reviewer
- **Problem:** `_keep_current` is a third private copy of a helper that already exists at `apps/scm/forms/AssetManagement/Assets.py:77` and is imported by `MaintenancePlans.py:42` and `MaintenanceWorkOrders.py:41` — and with a different signature (`(form, name, base_queryset)` vs `(queryset, tenant, current_id)`), so the two implementations of one rule can now drift.
- **Fix:** Promote one implementation to `apps/scm/forms/_common.py` (the Backend Package Structure rule-5 home for a helper more than one sub-module needs — the Assets.py docstring at line 48 explicitly says "move either the day a second sub-module wants it", and 4.18 is that day), then import it in `DutyTariffs.py` and `AssetManagement/*.py` instead of redefining it. Clone-family grep: `grep -rn "_keep_current" apps/scm/forms/`.
- **Status:** [ ] open

### M2 — `apps/scm/forms/FinanceIntegration/LandedCostVouchers.py:176`

- **Found by:** qa-smoke-tester
- **Problem:** `duty_rate_pct` renders as a REQUIRED field on every charge type (the model field is `DecimalField(max_digits=6, decimal_places=3, default=0)` with no `blank=True`, so `formfield()` gives `required=True`), even though the form's own help text and the fieldset legend say "Customs Duty charges only" — clearing the pre-filled 0 while adding a Freight/Handling charge blocks the save with "This field is required."
- **Fix:** In `LandedCostChargeForm.__init__`, immediately after the `duty_rate_pct` help_text assignment on lines 176-178, add `self.fields["duty_rate_pct"].required = False` AND add a companion method to the class so the blank cannot reach the NOT NULL column as `None`:

```python
    def clean_duty_rate_pct(self):
        # Customs-only: a cleared box on a freight charge means "no duty", not "invalid".
        # `required=False` alone would hand `None` to a NOT NULL column, so the blank is
        # coerced back to the model default here.
        return self.cleaned_data.get("duty_rate_pct") or Decimal("0")
```

`Decimal` is already in scope via `from apps.scm.forms._common import *` (re-exported at apps/scm/forms/_common.py:27). Do NOT set `required=False` without the `clean_duty_rate_pct` method — that alone turns a cleared box into an IntegrityError. The model's existing `clean()` guard (apps/scm/models/FinanceIntegration/LandedCostVouchers.py:690, rejecting a non-zero rate on a non-duty charge) is unaffected.
- **Status:** [ ] open

### M3 — `apps/scm/models/FinanceIntegration/LandedCostVouchers.py:190`

- **Found by:** performance-reviewer
- **Problem:** `LandedCostVoucher.Meta.indexes` covers `(tenant, status)`, `(tenant, cost_date)` and `(tenant, goods_receipt)` but NOT `(tenant, party)`, even though `party` is a declared list filter (`filters=[..., ("party", "party_id", True)]`, views/FinanceIntegration/LandedCostVouchers.py:115) and `_party_qs` reverse-joins the same column (`scm_landed_cost_vouchers__tenant=tenant`) on EVERY list page load. Only the plain single-column FK index exists, so both queries fall back to filtering on `party_id` and re-checking `tenant` per row.
- **Fix:** Add `models.Index(fields=["tenant", "party"], name="scm_lcv_tnt_party_idx")` to the `indexes` list in `LandedCostVoucher.Meta` and generate the accompanying `AddIndex` migration. This is the app-wide reference pattern for a tenant-scoped FK list filter, not a one-module fork — cf. `scm_cbr_tnt_cli_end_idx` on `(tenant, client, period_end)` for 4.17's `?client=` filter and `scm_rma_tnt_cust_idx` on `(tenant, customer)` for 4.10.
- **Status:** [ ] open

### M4 — `apps/scm/models/FinanceIntegration/LandedCostVouchers.py:416`

- **Found by:** code-reviewer
- **Problem:** Two guards interact into a workflow dead end: `allocate()` refuses a voucher on which no charge capitalises, and `draft_bill()` (line 518) refuses any status other than allocated/accrued — so a voucher carrying only recoverable import VAT or only non-capitalising (expensed) charges can never leave `draft` and can never be handed to Accounts Payable, even though the vendor genuinely has to be paid for those charges.
- **Fix:** Relax the `draft_bill()` status guard at line 518 to also permit `draft` when nothing on the voucher capitalises — e.g. `if self.status not in ("allocated", "accrued") and any(c.capitalises and c.allocatable_amount > ZERO for c in self.charges.all()): raise ValidationError(...)` — so a purely-recoverable/expensed voucher can still draft its bill while a voucher with real capitalising charges still has to be allocated first.
- **Status:** [ ] open

### M5 — `apps/scm/models/FinanceIntegration/LandedCostVouchers.py:460`

- **Found by:** security-reviewer
- **Lesson:** L35
- **Problem:** `allocate()` builds each `LandedCostAllocation` with `unit_cost_uplift=q4(allocated / quantity)` into a `DecimalField(14, 4)` (max 9,999,999,999.9999) and `basis_value=q4(basis_value)` into a `DecimalField(16, 4)`, neither clamped — and because the rows go out through `bulk_create()` no `full_clean()` ever sees them, so an out-of-range derived figure reaches the driver directly and raises `DataError` mid-transaction.
- **Fix:** Clamp both derived columns to their own widths in the row construction (same file, in the `for index, (move, basis_value) in enumerate(pairs)` loop):

```python
#: Column ceilings for LandedCostAllocation — bulk_create() skips full_clean(), so these are
#: the only guard between a derived figure and the driver.
MAX_UPLIFT = Decimal("9999999999.9999")      # unit_cost_uplift  DecimalField(14, 4)
MAX_BASIS_VALUE = Decimal("999999999999.9999")  # basis_value    DecimalField(16, 4)

                    rows.append(LandedCostAllocation(
                        ...
                        basis_value=min(MAX_BASIS_VALUE, q4(basis_value)),
                        ...
                        unit_cost_uplift=(min(MAX_UPLIFT, q4(allocated / quantity))
                                          if quantity else ZERO),
                    ))
```
- **Status:** [ ] open

### M6 — `apps/scm/models/FinanceIntegration/LandedCostVouchers.py:477`

- **Found by:** code-reviewer
- **Problem:** `allocate()` unconditionally sets `status = "allocated"` but never clears `accrued_at`, so re-allocating an *accrued* voucher demotes the status while leaving the accrual stamp behind — the detail page then renders the "Allocated" status chip and the `{% if obj.accrued_at %}` "Accrued" badge (templates/scm/finance/landedcostvoucher/detail.html:132) at the same time, and the "Accrued" detail row still shows a timestamp for a voucher that is no longer accrued.
- **Fix:** In `allocate()`, before the save at line 477-478, add `if self.accrued_at is not None: self.accrued_at = None` and change the save to `self.save(update_fields=["status", "accrued_at", "updated_at"])` — the ladder rung is being stepped back, so its stamp should go with it.
- **Status:** [ ] open

### M7 — `apps/scm/views/FinanceIntegration/DutyTariffs.py:216`

- **Found by:** performance-reviewer
- **Problem:** `dutytariff_detail` fetches the SAME row twice on every load — once via the `.only("is_active", "effective_from", "effective_to")` pre-read to compute the `is_current` context key, then again inside `crud_detail`. Two SELECTs where one suffices, purely to hand the template a flag the already-fetched `obj` can answer for free (`DutyTariff.is_current` is a pure property that queries nothing — the view's own docstring says so at line 202).
- **Fix:** Delete the `flags = get_object_or_404(...only(...))` pre-read (lines 216-219) and pass only `{"today": timezone.localdate()}` as `extra_context`; then in templates/scm/finance/dutytariff/detail.html replace the five bare `is_current` references (lines 68, 91, 92, 95, 208, 259) with `obj.is_current`. Same rendered output, one query instead of two.
- **Status:** [ ] open

### M8 — `apps/scm/views/FinanceIntegration/LandedCostVouchers.py:100`

- **Found by:** performance-reviewer
- **Problem:** `landedcostvoucher_list` runs TWO `aggregate()` calls over the same tenant-filtered `LandedCostVoucher` table (lines 92 and 100), costing an extra round trip on every list page load. The comment copies 4.17's `ClientBillingRun` rule, but that split is required there only because `ClientBillingRun` HAS a money column literally named `total` that the `total=Count("id")` alias shadows. `LandedCostVoucher` has no field named `total`/`draft`/`allocated`/`accrued`/`reconciled`/`cancelled`, and the money aggregate already uses shadow-free aliases (`sum_actual`, `sum_variance`) over `actual_total` / `variance_amount` — so no alias can collide and the split buys nothing.
- **Fix:** Merge the two calls into one: move `sum_actual=Coalesce(Sum("actual_total"), Value(ZERO), output_field=_MONEY)` and `sum_variance=Coalesce(Sum("variance_amount"), Value(ZERO), output_field=_MONEY)` into the `counts = ...aggregate(...)` call at line 92, delete the second `LandedCostVoucher.objects.filter(...).aggregate(...)` block, and keep the existing remap `stats = {**counts, "actual_total": counts["sum_actual"], "variance_total": counts["sum_variance"]}` so the frozen `stats.actual_total` / `stats.variance_total` template keys are unchanged. Update the comment to record why the 4.17 alias-shadow trap does not apply to this model.
- **Status:** [ ] open

### M9 — `apps/scm/views/FinanceIntegration/LandedCostVouchers.py:243`

- **Found by:** explorer
- **Lesson:** L7
- **Problem:** `_allocation_groups` sets `unit_cost_uplift` to `ZERO` (never `None`) when a group has no quantity, but `templates/scm/finance/landedcostvoucher/detail.html:444` and `:477` both test `{% if group.unit_cost_uplift is not None %}` — so the `{% else %}—{% endif %}` branch at line 477 is dead code and a zero-quantity group would render the misleading badge "+0.0000 per unit" instead of the intended "not allocated" dash.
- **Fix:** Change line 243-244 to emit `None` rather than `ZERO` when there is no quantity: `group["unit_cost_uplift"] = q4(group["allocated_amount"] / quantity) if quantity else None`. That matches the `is not None` contract the template was written against and matches the identical `uplift_per_unit` treatment in `views/FinanceIntegration/Reports.py:811`. No other consumer reads this key (grep: only detail.html).
- **Status:** [ ] open

### M10 — `templates/scm/finance/landedcostvoucher/detail.html:463`

- **Found by:** frontend-reviewer
- **Problem:** The allocation row's "Basis used" cell hand-writes a five-branch chain whose {% else %} prints the RAW value `{{ row.basis_used }}`, even though LandedCostAllocation.basis_used is a real choices field (apps/scm/models/FinanceIntegration/LandedCostVouchers.py:757 sets choices=LandedCostVoucher.ALLOCATION_BASIS_CHOICES) — so a sixth basis added later renders as `weight_volume` instead of its label, and the five branches duplicate labels Django already resolves.
- **Fix:** Replace the whole chain at lines 457-464 with the single line `<td class="nowrap">{{ row.get_basis_used_display }}</td>`. Unlike `charge.effective_basis` on line 287 (a property with no display method, where the hand chain is correct and must stay), `basis_used` is a model field with choices, so `get_basis_used_display` exists and is the canonical fallback rule 5 asks for.
- **Status:** [ ] open

### M11 — `templates/scm/finance/payables.html:233`

- **Found by:** frontend-reviewer
- **Problem:** For landed-cost rows the view sends `match_status = voucher.status` (apps/scm/views/FinanceIntegration/Reports.py:317-318), so a voucher renders "Draft" / "Allocated" / "Reconciled" as a slate badge under the column headed **Match** — asserting a three-way-match state that never happened, and directly contradicting this template's own docblock at lines 50-51 which states that landed rows "carry no match of their own and print a dash".
- **Fix:** Guard the Match cell on the source. In the `<td>` at line 217, wrap the existing chain: `{% if row.source == "landed" %}<span class="text-muted">&mdash;</span>{% else %}` … existing `{% if row.match_status == "matched" %}` … `{% endif %}{% endif %}`. While there, correct the docblock at lines 50-51: freight rows DO carry a real match status (FreightInvoice.MATCH_STATUS_CHOICES adds `duplicate` / `disputed`, both of which correctly land in the slate `{% elif row.match_status %}` fallback) — only landed rows should print the dash.
- **Status:** [ ] open

## Notes — app-wide / pre-existing (NOT in the fix queue)

- **code-reviewer:** Verified and clean, for the record: all four new models carry a tenant FK except `LandedCostCharge`, which is a documented tenant-less child reached only via `voucher__tenant=request.tenant` (`_charge_or_404`); every queryset in the 12 voucher views, 5 tariff views and 4 report views is tenant-scoped or scoped through a tenant-verified parent; the four verbs are `@require_POST` + `@tenant_admin_required` with the model methods re-checking every transition; `crud_list` int-guards `?party=` and the reports run every GET param through `_as_choice`/`_as_date`/`as_db_int`; pagination goes through `partials/pagination.html`; migration 0031 matches the models exactly and `makemigrations --check` says "No changes detected"; all 21 new url names reverse and every `{% url %}` in the new templates resolves; all four package `__init__.py` re-export blocks are complete (4 models, 3 forms, 21 views, 3 urlpattern lists); every `badge-success`/`badge-danger` occurrence is inside a `{% comment %}` block, not markup; template paths follow `scm/finance/<entity>/<page>.html` with the four report pages correctly at the sub-module root.

Non-actionable observations: (a) `apps/scm/views/InventoryManagement/Reports.py:75` filters `stock_move__isnull=False` on a non-nullable FK — a harmless no-op predicate, not worth a commit on its own; (b) `_grouped_sum`'s docstring (Reports.py:160) warns that `Meta.ordering` leaks into GROUP BY — that has not been true since Django 3.1, so the explicit `.order_by()` is belt-and-braces rather than the load-bearing fix the comment claims (the code is correct either way); (c) `finance_budget_variance` treats an unresolvable `?budget=` pk as "no filter" and shows the whole workspace, which contradicts the inline comment's "selects nothing" but is consistent with the house L11 posture everywhere else; (d) the review range also carries the tail of 4.17 — `apps/scm/tests/{conftest,test_3pl_*}.py` (6800 lines) and the `ClientBillingRun.draft_invoice` guard-reordering fix — which belong to the previous sub-module's test wave and are outside this lane's target.
- **security-reviewer:** Zero cross-tenant, authorization, CSRF, XSS, secret-exposure, open-redirect or upload findings in this range. Specifics I verified rather than assumed:

- **CSRF**: all nine POST `<form>` blocks in `templates/scm/finance/` carry `{% csrf_token %}`; no HTMX POSTs, no `@csrf_exempt`.
- **XSS / CSS injection**: no `|safe`, `mark_safe`, `{% autoescape off %}` or `<script>` anywhere in the new templates; the only inline `style="…{{ }}…"` candidate is `landedcostvoucher/detail.html:198`, which is a static `white-space:pre-line` with `{{ obj.notes }}` in the element BODY, not the attribute. Every `confirm(...)` string interpolates only the system-generated `obj.number` (`LC-`/`DTY-`), and apostrophes are written `\'` per L42. `payables.html:211` / `receivables.html:208` use `href="{{ row.url }}"` where `row.url` is `reverse()`d server-side in `Reports.py`.
- **Junk-param posture (L11)**: report GET params go through `_as_choice` (validated against the model's own CHOICES), `as_db_int` and `_as_date`; the two selected pks are resolved *through* the tenant-scoped queryset (`Reports.py:680-682`), so a foreign pk selects nothing rather than narrowing by a stranger's budget.
- **No raw SQL, `eval`, `new Function`, or secrets** in the changeset; no file-upload surface; no `?next=` handling.
- **Runtime confirmation**: I executed `_payable_grn_rows`, `_payable_freight_rows`, `_payable_landed_rows`, `_receivable_salesorder_rows`, `_receivable_billingrun_rows`, `_receivable_return_rows`, `_budget_variance_rows` (both unscoped and with a real budget+period selected), `_landed_variance_rows` for all three `?group=` values and `_invoice_balances` against the seeded DB as tenant "Acme Inc" — all returned rows with no `FieldError`, so the deep `goods_receipt__purchase_order__requisition__budget__fiscal_period` chains genuinely resolve. `manage.py check` is clean.

**Not flagged, deliberately (app-wide posture, not this sub-module's to change):** `DutyTariff` CRUD is `@login_required` only, with no tenant-admin gate on create/edit/delete of a customs *rate* master. That matches the app's established posture for rate masters — 4.17's `ClientRateCard`, the closest analogue (rates that drive client billing), is `@login_required` throughout including `activate`/`supersede` (`apps/scm/views/ThirdPartyLogistics/ClientRateCards.py:128-514`). If the house rule tightens for financial rate masters it should be swept family-wide, not applied to 4.18 alone.

**Pattern-clone sweep for the two findings (L28).** Both are the same class — *a derived Decimal written into a narrower column with no upper clamp*. The grep that finds the family is:

    grep -rn "\.quantize(Decimal(" apps/scm/models/
    grep -rn "max(ZERO," apps/scm/models/          # finds the one-sided clamps

That sweep turns up one **pre-existing** sibling outside this range: `Item.apply_receipt()` (`apps/scm/models/InventoryManagement/Items.py:221`) writes `((prior_val + quantity*unit_cost) / new_qty).quantize(...)` into the same `average_cost` column with no clamp at either end. It is much harder to trip (the result is bounded by the receipt's own `unit_cost`, which is a 14,4 column) and it is not part of this changeset, so it is out of scope here — but if finding #1 is fixed with a `MAX_AVERAGE_COST` constant, that constant should be applied at line 221 in the same commit.

**Seeder note (pre-existing pattern, not a finding):** `_flush`'s new 4.18 block deletes `LandedCostAllocation/Charge/Voucher/DutyTariff` with `.objects.all().delete()` across *every* tenant. That is the seeder-wide convention already (`StockMove.objects.all().delete()` and the 4.17/4.16 blocks do the same) and `--flush` is an explicit dev-only destructive flag, so it is consistent rather than new exposure.
- **performance-reviewer:** APP-WIDE / OUT OF SCOPE, recorded not queued:

1. The four 4.18 report pages (`finance_payables`, `finance_receivables`, `finance_budget_variance`, `landed_cost_variance`) are deliberately UNPAGINATED, capped at ROW_CAP=500 rows / SCAN_CAP=5000 scanned detail rows with a `truncated` flag surfaced to the template. That is the same posture as the pre-existing `valuation_report`, `on_hand_by_location`, `reorder_alerts` and `client_space_report` — computed reports in this app are capped rather than paginated. I did not flag it. The one memory-shaped consequence worth knowing: on a workspace at the cap, `_payable_grn_rows` materialises 500 GoodsReceiptNotes plus every one of their `GoodsReceiptLine` rows in a single prefetch. If that ever bites, the fix is to replace `received_value(lines=lines)` with a grouped `.values(\"grn_id\").annotate(Sum(F(\"quantity_received\") * F(\"po_line__unit_price\")))` map, not to paginate.

2. `Item.apply_landed_cost()` (models/InventoryManagement/Items.py:225) issues one `on_hand()` aggregate plus one `save()` per item, and `LandedCostVoucher.allocate()` calls it once per item after calling `_unallocate()` which does the same — so a 20-item receipt costs ~80 queries on the Allocate button press. This exactly mirrors the pre-existing `apply_receipt()` contract and lives on a POST verb, not a list/dashboard path, so I did not flag it. If the allocate path ever needs tightening, the shape is: one grouped `StockMove.objects.filter(item__in=...).values(\"item_id\").annotate(Sum(\"quantity\"))` for all on-hands, then `Item.objects.bulk_update(items, [\"average_cost\", \"updated_at\"])`.

3. Two harmless wasted LEFT JOINs in `LandedCostVoucherForm.__init__`: `.select_related(\"purchase_order\")` on the `goods_receipt` dropdown (line 77) and `.select_related(\"carrier\")` on the `shipment` dropdown (line 86). Neither `GoodsReceiptNote.__str__` (uses `purchase_order_id`) nor `Shipment.__str__` (number + direction) dereferences those FKs, so there is no N+1 to prevent — just an unneeded join. Not worth a commit on its own; fold it in if that file is touched for finding 1 anyway.

4. TEST SUGGESTION for the test-writer agent — a `django_assert_max_num_queries` lock is genuinely useful on three of these, since all three are one careless `select_related` drop away from an N+1:
   - `landedcostcharge_create` GET with ~10 seeded FreightInvoices → assert <= 15 queries (this is the regression lock for finding 1; without the `carrier__party` fix it will be ~25).
   - `finance_receivables` with ~10 invoiced documents across all three sources → assert <= 20 (locks `_invoice_balances` staying a single grouped query rather than drifting back to per-row `balance_due()`).
   - `finance_budget_variance` with 3 org units, several PR/PO lines and 2 vouchers → assert <= 15 (locks the five grouped queries + the one `OrgUnit` name fetch, i.e. that nothing reintroduces `OrgUnit.objects.get(pk=...)` inside the row loop).
   Also worth one plain-correctness test alongside them: `landedcostvoucher_list` stats must stay computed over the WHOLE workspace, not the filtered page, if finding 2's aggregate merge is applied.
- **frontend-reviewer:** Verified clean across all twelve changed templates (budget_variance, dutytariff/{list,detail,form}, landed_cost_variance, landedcostcharge/form, landedcostvoucher/{list,detail,form}, payables, receivables, overview):

- L2 comment leak: zero `{#` sequences anywhere in the twelve files; every multi-line note uses {% comment %}...{% endcomment %}, and `{% templatetag openblock %}` is used correctly where a tag name appears inside prose.
- L9 pagination: both list pages delegate to templates/partials/pagination.html, which guards previous_page_number/next_page_number inside has_previous/has_next and re-emits every GET param except `page`. Report pages use a row_cap/truncated banner instead of pagination, which is the right call for a union report.
- L10 none-safety: no `|default` is applied to any FK anywhere (all `|default` hits are inside comments); every nullable FK — tax_code, effective_to, shipment, trade_document, currency, bill, charge.party/freight_invoice/gl_account, group.item, move.item/location, row.org_unit — sits inside an explicit {% if %}. Decimal|None values use `is not None`, never truthiness.
- L11/filters: pk dropdowns (party, budget, fiscal_period) all use `|stringformat:"d"`; no `|slugify` anywhere. Every select re-selects from request.GET, except landed_cost_variance's `group` which correctly binds to the view-normalised `group` rather than the raw query string.
- URLs: every {% url %} target resolves — dutytariff_*, landedcostvoucher_*, landedcostcharge_{create,edit,delete}, landed_cost_variance, finance_{payables,receivables,budget_variance}, goodsreceipt_detail, shipment_detail, tradedocument_detail, freightinvoice_detail, item_detail, location_detail, salesorder_list, clientbillingrun_list, returnauthorization_list, purchaseorder_list, and accounting:{bill_detail,bill_list,invoice_list,tax_code_detail,budget_list} all exist. `obj.pk` on both form templates is guarded behind {% if is_edit %}, including in the Cancel href.
- Context contract: every key read by a template is actually rendered by its view (checked crud_list extra_context for both lists, the hand-rolled detail render, both charge-form renders and all four report renders).
- Admin gate at landedcostvoucher/detail.html:591 matches apps/core/decorators.py:18 exactly (`is_superuser or is_tenant_admin`) and covers precisely the four @tenant_admin_required verbs; Edit/Delete/Add-charge sit outside it and are @login_required only, which is correct. It is also the established house idiom (20+ accounting templates use the identical expression).
- colspan arithmetic is correct on all nine tables, empty-states and tfoot rows included.

App-wide / pre-existing, NOT actionable here:
- `<th class="table-actions">` makes the header cell `display:flex` when theme.css ships `.th-actions` for exactly that job — but the codebase uses the former 415 times against 12 for the latter, so these templates are following the house pattern.
- Icon-only `.btn-icon` controls carry `title=` but no `aria-label=`, identical to every shipped sibling (templates/scm/3pl/logisticsclient/list.html:238).
- The two list pages' search inputs use `aria-label=\"Search\"` rather than a visible `<label for>`, matching the shipped 3PL pattern; the four report pages do pair `<label for>` with `id=` properly.
- The `void` branches in payables.html:255 and receivables.html:231 are byte-identical to their own {% else %} fallback (badge-slate + same label) — redundant but harmless, and arguably deliberate documentation of the vocabulary.
- **explorer:** Verified clean, no finding raised: all 21 new `scm:` url names reverse (script run against `config.settings_test`); zero duplicate url names and zero duplicate route strings across the whole 634-pattern concatenated `apps/scm/urls/__init__.py`; no top-level `<str:…>` converter exists anywhere in the app so the seven new first segments (`landed-cost-vouchers`, `landed-cost-charges`, `landed-cost-variance`, `duty-tariffs`, `finance-payables`, `finance-receivables`, `finance-budget-variance`) cannot be shadowed; all 11 new templates load via `get_template()` and none uses a banned flat `<entity>_<page>.html` path (the four report pages at `templates/scm/finance/` root are standalone pages, allowed by template rule 6); the four models, three forms and 21 views are all present on `apps.scm.{models,forms,views}` so no `__init__.py` re-export block is missing; every `{% url %}` target in the new templates resolves, including the cross-app `accounting:bill_detail`, `accounting:bill_list`, `accounting:invoice_list`, `accounting:budget_list`, `accounting:tax_code_detail`; `LIVE_LINKS[\"4.18\"]`'s five keys match the NavERP.md 4.18 bullet titles verbatim (NavERP.md:853-857) and all five targets are live staff pages; every ORM field path in the four report views compiles (checked by forcing SQL compilation on each queryset); `manage.py check` is clean and `makemigrations --check` reports \"No changes detected\"; the detail page's verb-button gate `{% if request.user.is_superuser or request.user.is_tenant_admin %}` matches `tenant_admin_required` exactly; `ItemForm.Meta.fields` gaining `weight_kg`/`volume_cbm` is safe because `templates/scm/inventory/item/form.html:13` loops `{% for field in form %}` rather than naming fields (no silent blanking on edit); every CSS class used exists in `static/css/theme.css` (`text-warn`, `badge-amber`, `badge-red`, `btn-icon.danger`, `stat-icon.slate`, `.req`). Not actionable for this sub-module: `apps/scm/tests/` has no `test_finance_*` module yet (Phase 6 test wave); and the index comment at models/FinanceIntegration/LandedCostVouchers.py:196 justifies `scm_lcv_tnt_grn_idx` by \"the GRN detail page's 'what did this receipt cost to land' panel\", which does not exist — no GRN template was touched in this changeset.
- **qa-smoke-tester:** SCOPE / METHOD: migrate + seed_core + seed_accounts + seed_scm were all idempotent no-ops (data already present). Every mutating probe (verb-ladder POSTs, create/edit/delete POSTs, 24 probe tariffs + 20 probe vouchers for real pagination overflow, the delete-everything empty-state pass) ran inside a rolled-back `transaction.atomic()` or was explicitly cleaned up; final row counts are identical to the seeded state (2 vouchers / 5 charges / 9 allocations / 2 tariffs per tenant) and `manage.py check` is clean. All five throwaway scripts under `temp/` were deleted.

NOT ACTIONABLE, observed while sweeping:

1. The four report pages carry NO pagination by design (`ROW_CAP = 500` / `SCAN_CAP = 5000` with a `truncated` flag, documented at apps/scm/views/FinanceIntegration/Reports.py:77-87). `?page=2` is therefore accepted and silently ignored — correct behaviour, but it means a workspace that hits the cap has no way to reach rows 501+. That is a deliberate product ruling, not a defect.

2. `finance_receivables` rendered 58 rows on the seeded Acme workspace with no pagination and no row-count ceiling below 500. It stays fast at this size, but it is the 4.18 page most likely to feel heavy on a real workspace. Performance lane, not runtime correctness.

3. The `duty_rate_pct` widget's label renders as the raw field name "Duty rate pct" rather than "Duty rate %". Cosmetic; frontend lane.

4. PRE-EXISTING, outside this changeset: `temp/` already contains ~180 leftover scripts from earlier sub-module sessions. It is gitignored, so this is housekeeping only — I removed only my own five files.

5. The two "failures" my first write-path pass reported (`landedcostcharge_create` / `_edit` returning 200 instead of 302) were artifacts of a hand-built POST that omitted `duty_rate_pct`; the rendered form pre-fills it with `0`, and a realistic full-form submission returns 302 and re-totals the parent voucher correctly. Only the narrower usability issue in the findings array survived that re-check.

## Done well

- **code-reviewer:** The seeder produces every derived 4.18 figure through the real production code path — `_seed_finance_tenant` calls `LandedCostVoucher.allocate()` and `draft_bill()` rather than hand-writing `LandedCostAllocation` rows (apps/scm/management/commands/seed_scm.py:5556-5560), and it snapshots the duty rate through the actual `DutyTariff.rate_for()` lookup. That means every `seed_scm` re-exercises the rounding-remainder rule, the basis fallback chain and the `BillLine` precision clamps, so the demo data cannot drift from the implementation. The early-return idempotency guard and the `get_or_create` on the tariff *natural* key (not the auto-assigned `number`) are both correct.
- **security-reviewer:** Tenant scoping is complete and defence-in-depth, not just present: every one of the twelve `get_object_or_404` calls in `apps/scm/views/FinanceIntegration/` passes `tenant=request.tenant`, the tenant-less child `LandedCostCharge` is fetched through `voucher__tenant=request.tenant` (`LandedCostVouchers.py:436`), the charge's parent comes from the ROUTE rather than the POST body, every FK dropdown on all three forms falls back to `.none()` for a tenant-less user *and* is re-checked with `_reject_foreign` in `clean()`, and all four money-moving verbs are `@tenant_admin_required` + `@require_POST` with the detail template's buttons wrapped in the matching `{% if request.user.is_superuser or request.user.is_tenant_admin %}` gate (L27 both halves). Mass assignment is clean too — the rendered fields in both form templates match the `Meta.fields` whitelists exactly, with `status`, `bill`, `number`, `tenant`, `accrued_at` and all five derived money columns absent.
- **performance-reviewer:** The four computed report views are query-disciplined in exactly the way this lane cares about: `_grouped_sum` clears `Meta.ordering` before `.values().annotate()` so a model's default ordering cannot silently explode the GROUP BY, budget variance resolves five whole dimensions in five grouped queries instead of one per department, `_invoice_balances` replaces 500 per-row `Invoice.balance_due()` aggregates with one `Coalesce(Sum(..., filter=...))` pass, `_payable_grn_rows` prefetches `lines` with `select_related(\"po_line\")` INSIDE the Prefetch so `received_value()` costs zero extra queries per row, and `valuation_report` was correctly extended with a single grouped `LandedCostAllocation` uplift map rather than a per-item lookup. Every row link is pre-reversed in Python, so no template does work in a loop.
- **frontend-reviewer:** Every status badge in the changeset is colour-named and value-exact: the voucher chains enumerate the five literal STATUS_CHOICES keys (draft/allocated/accrued/reconciled/cancelled) verified against apps/scm/models/FinanceIntegration/LandedCostVouchers.py:103-109, the payables chain matches Bill.STATUS_CHOICES and the receivables chain Invoice.STATUS_CHOICES exactly, and every chain ends in an {% else %} that prints the resolved get_*_display label. A grep of all class attributes across templates/scm/finance/ returns only badge-green/red/amber/info/muted/slate and stat-icon blue/green/orange/purple/slate — the L33 family does not recur once in ~3,300 new lines, and the templates carry the reasoning inline so the next author cannot reintroduce it by accident.
- **explorer:** Every row link on the three union report pages is reversed in Python and handed to the template as a plain `row[\"url\"]` string (Reports.py:232, :270, :307, :398, :419, :441), so the classic \"union page reverses a variable view name → NoReverseMatch 500 the moment one source contributes a row\" failure cannot happen — and all six of those route names (`scm:goodsreceipt_detail`, `scm:freightinvoice_detail`, `scm:landedcostvoucher_detail`, `scm:salesorder_detail`, `scm:clientbillingrun_detail`, `scm:returnauthorization_detail`) exist and reverse cleanly.
- **qa-smoke-tester:** The four report views are the only 4.18 pages that union several sources, and every one of them survived hostile input without a single 500: choice params are checked against their own `*_CHOICES` set before reaching `.filter()`, the two pk params go through `as_db_int`, and `_as_date` swallows `2024-02-30` / `notadate` / a 40-digit year (apps/scm/views/FinanceIntegration/Reports.py:133-157). Crucially, every row's link is reversed in PYTHON at build time rather than via `{% url %}` on a variable view name (line 232 even carries the `goodsreceipt_detail` vs `goodsreceiptnote_detail` correction inline) — the exact construction that turns a multi-source report into a `NoReverseMatch` 500 the moment one source contributes a row. Paired with `_variance_pct` returning `None` (not 0) and both templates guarding it with `{% if row.variance_pct is not None %}`, the reports render correctly on the empty tenant, the tenant-less superuser and the fully-populated workspace alike.
