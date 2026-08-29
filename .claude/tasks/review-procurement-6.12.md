# Review findings — procurement 6.12 Goods Receipt & Inspection

Range: `a3c6adcb12cac090312bf1c3ab741034533c1c8a...HEAD` · Generated: 2026-08-30
Wave (parallel): code-reviewer · security-reviewer · performance-reviewer · frontend-reviewer · explorer · qa-smoke-tester

## Summary

| Severity | Count |
|---|---|
| Critical | 0 |
| Important | 12 |
| Minor | 14 |
| **Total (deduped)** | **26** |

| Agent | Raw findings |
|---|---|
| code-reviewer | 5 |
| security-reviewer | 3 |
| performance-reviewer | 7 |
| frontend-reviewer | 4 |
| explorer | 6 |
| qa-smoke-tester | 1 |

## How to work this file (code-fixer)

Fix in ID order: every `C`, then every `I`, then every `M`. One fix → one file → one `git add` + one
`git commit`. Update each **Status** line to `[x] fixed — <commit subject>` or `[~] skipped — <reason>`
as you go. Never delete a finding; a wrong one gets `[~] skipped — not a defect: <why>`. Never `git push`.

## Important

### I1 — `apps/procurement/forms/GoodsReceiptInspection/ReturnsToVendor.py:100`

- **Found by:** code-reviewer
- **Problem:** `ReturnToVendorForm.goods_receipt` excludes cancelled receipts with no exemption for the instance's stored value, so editing a draft RTV whose receipt was cancelled after the fact renders a select with no matching option and — because the field is `null=True, blank=True` — silently saves `goods_receipt = NULL`, losing the origin link with no error.
- **Fix:** Mirror the exemption `ReturnToVendorLineForm.__init__` already documents at lines 169-184: build `offerable = ~Q(status="cancelled")`, then `if self.instance.pk and self.instance.goods_receipt_id: offerable |= Q(pk=self.instance.goods_receipt_id)`, and apply `GoodsReceiptNote.objects.filter(tenant=tenant).filter(offerable).select_related("purchase_order").order_by("-receipt_date", "-id")`. `Q` is already imported at line 21.
- **Status:** [x] fixed — fix(procurement): exempt an RTV stored goods receipt from the cancelled-receipt exclusion so editing a draft cannot silently NULL the origin link

### I2 — `apps/procurement/forms/GoodsReceiptInspection/ReturnsToVendor.py:189`

- **Found by:** performance-reviewer
- **Problem:** `ReturnToVendorLineForm.__init__` assigns a fresh, tenant-wide `PurchaseOrderLine` queryset (every PO line in the workspace, never narrowed by the parent's order even when one is known) to each formset row, and `goods_receipt_line` is likewise tenant-wide whenever the header names no receipt; because `ModelChoiceIterator.__iter__` calls `queryset.iterator()`, each rendered `<select>` re-executes its query, so the RTV edit page costs 2 unbounded queries per row (a 10-line draft + `extra=2` = 24 full-table reads) and renders 24 selects of every PO line in the tenant.
- **Fix:** Two changes in this file. (1) Narrow `po_line` to the parent's order, mirroring `BaseAsnLineFormSet` (apps/procurement/forms/OrderFulfillment/AdvancedShipmentNotice.py:199-206): pass the parent's `purchase_order` through `get_form_kwargs` and use `PurchaseOrderLine.objects.filter(purchase_order=order).select_related("purchase_order")` when it is known, falling back to the tenant-wide queryset only when it is not. (2) Build each field's rendered options ONCE in `BaseReturnToVendorLineFormSet.__init__` and share them, e.g.

```python
def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    for name in ("goods_receipt_line", "po_line"):
        first = next((f for f in self.forms if name in f.fields), None)
        if first is None:
            continue
        shared = [("", "---------")] + [(o.pk, str(o))
                                        for o in first.fields[name].queryset]
        for form in self.forms:
            if name in form.fields:
                form.fields[name].choices = shared
```

Assigning `.choices` sets `_choices` and short-circuits the iterator, while `.queryset` stays in place so `to_python`/`clean` keep enforcing the tenancy narrowing.
- **Status:** [x] fixed — perf(procurement): narrow RTV line po_line to the header order and render each formset select once (plus a follow-up commit moving the sharing into `_construct_form` so `BaseFormSet.forms` stays lazy)

### I3 — `apps/procurement/forms/GoodsReceiptInspection/ReturnsToVendor.py:237`

- **Found by:** security-reviewer
- **Problem:** A return line's `po_line` is only checked for tenancy — nothing ties it to the return's own `purchase_order`/`vendor`, so a return addressed to supplier A can be built (from the dropdown, which lists every PO line in the workspace) on supplier B's ordered line, and `expected_credit` is then quoted off the wrong supplier's unit price.
- **Fix:** In `BaseReturnToVendorLineFormSet.clean()` extend the `po_line` branch to check the counterparty legs, and narrow the dropdown to match. Clean:

```python
header_order_id = getattr(self.instance, "purchase_order_id", None)
vendor_id = getattr(self.instance, "vendor_id", None)
...
po_line = form.cleaned_data.get("po_line")
if po_line is not None:
    if po_line.purchase_order.tenant_id != tenant_id:
        form.add_error("po_line", "That record belongs to another workspace.")
    elif header_order_id and po_line.purchase_order_id != header_order_id:
        form.add_error("po_line", "That line belongs to a different purchase order.")
    elif vendor_id and po_line.purchase_order.vendor_id != vendor_id:
        form.add_error("po_line", "That order was placed with a different supplier.")
```

And feed the header order down so the widget stops offering foreign lines — in `get_form_kwargs` add `kwargs["order"] = getattr(self.instance, "purchase_order", None)`, and in `ReturnToVendorLineForm.__init__(..., order=None, ...)` replace the line-189 queryset with:

```python
po_lines = PurchaseOrderLine.objects.filter(purchase_order__tenant=tenant)
if order is not None:
    po_lines = po_lines.filter(purchase_order=order)
self.fields["po_line"].queryset = po_lines.select_related("purchase_order").order_by("-purchase_order_id", "id")
```
- **Status:** [x] fixed — security(procurement): tie an RTV line ordered-line to the header order AND supplier

### I4 — `apps/procurement/views/GoodsReceiptInspection/ReceiptBoards.py:205`

- **Found by:** performance-reviewer
- **Problem:** `_item_map` fetches the ENTIRE tenant item master (`Item.objects.filter(tenant=tenant).select_related("category", "tenant")`) and does the SKU matching in Python, so every receiving-console render costs one full `scm.Item` table read and every tolerance-exceptions render costs TWO (it is called from both `_uncovered_line_count` line 758 and `_exception_rows` line 777) — on a 20k-item catalogue that is 20k rows materialised per call for a page that needs ~30 of them.
- **Fix:** Pre-filter in SQL exactly the way the sibling helper already does at apps/procurement/views/GoodsReceiptInspection/ReceiptTolerances.py:143-145. Add `from django.db.models.functions import Lower` and replace the loop body with:

```python
found = {}
for item in (Item.objects.filter(tenant=tenant)
             .select_related("category", "tenant")
             .annotate(lower_sku=Lower("sku"))
             .filter(lower_sku__in=skus)):
    key = _norm(item.sku)
    if key in skus and key not in found:
        found[key] = item
return found
```

Keep the `_norm`-based re-keying so the whitespace-collapsing semantics are unchanged for the rows that do come back.
- **Status:** [x] fixed — perf(procurement): match receiving-board SKU hints in SQL instead of scanning the whole item master

### I5 — `apps/procurement/views/GoodsReceiptInspection/ReceiptBoards.py:286`

- **Found by:** performance-reviewer
- **Problem:** `_receipt_by_delivery_ref(tenant, base)` is called on the UNFILTERED, UNPAGINATED console queryset, so it issues a DISTINCT over every in-flight ASN's `supplier_reference` and then a `delivery_note_ref__in=(...)` fetch with an unbounded IN list, materialising every matching GoodsReceiptNote into a dict on every page load; the `booked_7d` stat card is then a Python `sum()` over that dict (line 288) instead of a SQL COUNT, which is exactly the derived-KPI-by-Python-loop pattern the app forbids.
- **Fix:** Split the two uses. Compute the tile as one aggregate:

```python
booked_7d = (GoodsReceiptNote.objects
             .filter(tenant=tenant, created_at__gte=booked_cutoff,
                     delivery_note_ref__in=Subquery(
                         base.exclude(supplier_reference="")
                             .values("supplier_reference")))
             .exclude(status="cancelled").count())
```

and build the row marker from the PAGE only — move `receipt_by_ref = _receipt_by_delivery_ref(tenant, base.filter(pk__in=[a.pk for a in page_obj.object_list]))` down to just before the `_console_rows(...)` call at line 326 (earliest-wins keying is preserved because the map is still built in `id` order).
- **Status:** [x] fixed — perf(procurement): count the console booked tile in SQL and build the row marker from the page

### I6 — `apps/procurement/views/GoodsReceiptInspection/ReceiptBoards.py:374`

- **Found by:** performance-reviewer
- **Problem:** `order.received_by_line()` is called inside the per-ASN loop, memoised only per DISTINCT purchase order — with `BOARD_PER_PAGE = 30` a console page of 30 shipments from 30 different orders issues 30 separate GROUP BY aggregates (1 + N), which is the dominant cost of the page.
- **Fix:** Replace the per-order call with one grouped query over every order on the page, built before the loop in `_console_rows`. Import `PurchaseOrderLine` from `apps.scm.models` and add:

```python
def _received_by_line_bulk(order_ids):
    rows = (PurchaseOrderLine.objects
            .filter(purchase_order_id__in=order_ids)
            .annotate(received=Sum(
                "receipt_lines__quantity_received",
                filter=~Q(receipt_lines__goods_receipt__status="cancelled")))
            .values_list("purchase_order_id", "id", "received"))
    out = {}
    for order_id, line_id, received in rows:
        out.setdefault(order_id, {})[line_id] = received or ZERO
    return out
```

Call it once at the top of `_console_rows` (`received_maps = _received_by_line_bulk({a.purchase_order_id for a in shipments})`) and replace lines 372-375 with `received_map = received_maps.get(order.pk, {})`. Worth a `django_assert_max_num_queries` test on `procurement:receiving_console` asserting the count does not grow between a 1-ASN and a 20-ASN page.
- **Status:** [x] fixed — perf(procurement): fold the console received-quantity lookup into one grouped query (keyed on the PO-line pk, which is globally unique, rather than the nested per-order dict the finding sketched)

### I7 — `apps/procurement/views/GoodsReceiptInspection/ReceiptBoards.py:504`

- **Found by:** code-reviewer
- **Problem:** The console's book verb keys idempotency solely on `asn.supplier_reference`, which is `blank=True` on the ASN model — for a shipment with no supplier reference the existing-receipt check at 505-513 is skipped entirely, `delivery_note_ref` is stored as `""`, `_receipt_by_delivery_ref` (which drops blank keys at line 221/232) can never mark the row Booked, so every re-click mints another draft GoodsReceiptNote and burns another GRN number against the same PO.
- **Fix:** At line 504 use `reference = (asn.supplier_reference or "").strip() or asn.number` so the lookup, the `delivery_note_ref` written at line 527 and the Booked marker all share one key; and in `_receipt_by_delivery_ref` (line 221) build `refs` from both `supplier_reference` and `number` (`refs = [r for r in asn_qs.values_list("supplier_reference", flat=True) if r] + list(asn_qs.values_list("number", flat=True))`), with line 448 falling back to `receipt_by_ref.get(_norm(asn.supplier_reference)) or receipt_by_ref.get(_norm(asn.number))`.
- **Status:** [x] fixed — fix(procurement): give a blank-reference ASN a stable delivery-note key so booking stays idempotent

### I8 — `apps/procurement/views/GoodsReceiptInspection/ReceiptBoards.py:504`

- **Found by:** explorer
- **Problem:** `receiving_console_book`'s idempotency check is skipped entirely when `asn.supplier_reference` is blank (`if reference:`), and `_receipt_by_delivery_ref` excludes blank refs so the row's `is_booked` marker is permanently False — an ASN with no supplier reference (the field is `blank=True` and optional on the 6.11 ASN form) still shows "Not booked yet" after booking and each further click mints another draft GoodsReceiptNote, burning a GRN number each time.
- **Fix:** Give a blank-reference ASN a stable key instead of no key: set `reference = (asn.supplier_reference or '').strip() or asn.number` at line 504 so the existing-receipt lookup and the `delivery_note_ref=reference[:64]` write both always run; correspondingly in `_receipt_by_delivery_ref` (line 221) build `refs` from `supplier_reference or number` per ASN and key `receipt_by_ref` the same way, and at line 448 look up `_norm(asn.supplier_reference or asn.number)`. Both the board marker and the verb then agree for every ASN.
- **Status:** [x] fixed — same defect as I7, resolved by the same commit: fix(procurement): give a blank-reference ASN a stable delivery-note key so booking stays idempotent

### I9 — `templates/procurement/goodsreceiptinspection/receiving_console.html:284`

- **Found by:** code-reviewer
- **Lesson:** L32
- **Problem:** The "Mint lots & serials" form and its submit button are rendered for every logged-in user, but `receiving_console_mint_lots` is `@tenant_admin_required` (ReceiptBoards.py:568) which raises `PermissionDenied` — a plain member is offered a button that only ever returns 403.
- **Fix:** Wrap the whole mint block (lines 283-293) in `{% if request.user.is_superuser or request.user.is_tenant_admin %}...{% endif %}`, exactly as the tolerance-policy list (list.html:170) and discrepancy list (list.html:160) gate their admin-only verbs in this same changeset.
- **Status:** [x] fixed — one defect reported by four lanes; fixed via the can_mint context flag (I12 shape): feat(procurement): pass can_mint to the receiving console + a11y(procurement): gate the console mint-lots form on can_mint

### I10 — `templates/procurement/goodsreceiptinspection/receiving_console.html:284`

- **Found by:** security-reviewer
- **Lesson:** L27
- **Problem:** The "Mint lots & serials" POST form is rendered to every workspace member, but `receiving_console_mint_lots` is `@tenant_admin_required`, so a plain member who clicks it gets a raised `PermissionDenied` (403 error page) instead of a page that never offered the button.
- **Fix:** Wrap the whole mint-lots block in the same admin test the decorator applies — the shape the sibling templates in this very changeset already use (`rtv/list.html:130`, `discrepancy/list.html:160`):

```django
{% if request.user.is_superuser or request.user.is_tenant_admin %}
  <div class="card-body" style="border-top:1px solid var(--border);">
    <form method="post" action="{% url 'procurement:receiving_console_mint_lots' row.asn.pk %}" onsubmit="return confirm('Create lot and serial records from what {{ row.asn.number }} declared? Lines whose SKU cannot be matched to an item are skipped and reported.');">
      {% csrf_token %}
      ...
    </form>
  </div>
{% endif %}
```

(Equivalently, add `"can_mint_lots": bool(request.user.is_superuser or getattr(request.user, "is_tenant_admin", False))` to the `receiving_console` context in `apps/procurement/views/GoodsReceiptInspection/ReceiptBoards.py:322` and gate on that — the tolerance-policy detail page already uses that `can_*` style.)
- **Status:** [x] fixed — one defect reported by four lanes; fixed via the can_mint context flag (I12 shape): feat(procurement): pass can_mint to the receiving console + a11y(procurement): gate the console mint-lots form on can_mint

### I11 — `templates/procurement/goodsreceiptinspection/receiving_console.html:284`

- **Found by:** explorer
- **Problem:** The "Mint lots & serials" POST form is rendered for every console row with no permission guard, but `receiving_console_mint_lots` is `@tenant_admin_required` — a plain workspace member sees the button and gets a 403 PermissionDenied page when they click it.
- **Fix:** Wrap the whole `<div class="card-body" style="border-top:...">` block (lines 283-293) in `{% if request.user.is_superuser or request.user.is_tenant_admin %} ... {% endif %}`, matching the guard already used on `tolerancepolicy/list.html:39` and `discrepancy/list.html:160`. No view change is needed — `receiving_console` already renders for members and the decorator re-checks the POST.
- **Status:** [x] fixed — one defect reported by four lanes; fixed via the can_mint context flag (I12 shape): feat(procurement): pass can_mint to the receiving console + a11y(procurement): gate the console mint-lots form on can_mint

### I12 — `templates/procurement/goodsreceiptinspection/receiving_console.html:284`

- **Found by:** qa-smoke-tester
- **Problem:** The "Mint lots & serials" POST form/button is rendered unconditionally for every console row, but `receiving_console_mint_lots` is `@tenant_admin_required` — a non-admin workspace member (verified with `ops_acme`: 2 mint-lots forms rendered, POST returns 403 PermissionDenied) is offered a button that dead-ends on a hard 403 error page.
- **Fix:** Mirror the gate the rest of 6.12 already uses. In `apps/procurement/views/GoodsReceiptInspection/ReceiptBoards.py::receiving_console` add `"can_mint": bool(request.user.is_superuser or getattr(request.user, "is_tenant_admin", False)),` to the render context at the dict starting on line 322 (next to `"stats": {...}`), extend the template's `Context consumed:` contract comment on line 20-23 with `can_mint`, and wrap lines 283-293 of `receiving_console.html` (the whole `<div class="card-body" style="border-top:...">` holding the mint-lots form) in `{% if can_mint %} ... {% endif %}`. Do NOT gate the book form on it — `receiving_console_book` is `@login_required` only and must stay member-visible.
- **Status:** [x] fixed — one defect reported by four lanes; fixed via the can_mint context flag (I12 shape): feat(procurement): pass can_mint to the receiving console + a11y(procurement): gate the console mint-lots form on can_mint

## Minor

### M1 — `apps/procurement/forms/GoodsReceiptInspection/ReturnsToVendor.py:232`

- **Found by:** security-reviewer
- **Problem:** When the RTV header names no `goods_receipt`, the `header_receipt_id and ...` guard short-circuits and a line may point at ANY live receipt line in the workspace — including one from a different supplier — which then prices `unit_price` off that receipt's PO line (the same mis-pricing as the `po_line` leg, reached through the other field).
- **Fix:** Give the no-header-receipt case its own branch in `BaseReturnToVendorLineFormSet.clean()` so the supplier still has to match:

```python
if receipt_line is not None:
    if receipt_line.goods_receipt.tenant_id != tenant_id:
        form.add_error("goods_receipt_line", "That record belongs to another workspace.")
    elif header_receipt_id:
        if receipt_line.goods_receipt_id != header_receipt_id:
            form.add_error("goods_receipt_line", "That line belongs to a different goods receipt.")
    elif vendor_id and getattr(receipt_line.goods_receipt.purchase_order, "vendor_id", None) != vendor_id:
        form.add_error("goods_receipt_line", "That receipt is from a different supplier.")
```

(`vendor_id = getattr(self.instance, "vendor_id", None)` is the same local the `po_line` fix introduces.) Mirror it on the widget: in `ReturnToVendorLineForm.__init__`'s `elif tenant is not None:` branch (line 169), also `.filter(goods_receipt__purchase_order__vendor_id=vendor_id)` when the header names a vendor, keeping the existing `Q(pk=current_id)` escape so a stored value never becomes an unfixable "invalid choice".
- **Status:** [x] fixed — security(procurement): pin an RTV receipt-line to the header supplier when no receipt is named

### M2 — `apps/procurement/models/GoodsReceiptInspection/ReceiptTolerances.py:68`

- **Found by:** explorer
- **Problem:** `ReceiptTolerancePolicy.VERDICT_CHOICES` is declared but never read by any view, form or template — the six verdict labels are instead hard-coded as `{% if %}` chains in five separate templates (tolerancepolicy/detail.html:125, discrepancy/detail.html:66, receiving_console.html:134 and :230, tolerance_exceptions.html:133), so adding a seventh verdict means editing five files and the constant drifts unnoticed.
- **Fix:** Either pass `verdict_choices=ReceiptTolerancePolicy.VERDICT_CHOICES` into the five contexts and render the label from a lookup, or delete `VERDICT_CHOICES` (lines 66-75) and leave `VERDICT_CSS` as the single verdict vocabulary, updating the tolerancepolicy/detail.html:23 comment that references it.
- **Status:** [x] fixed — took the first option (render the label from a lookup), not the delete: the view now attaches `verdict_label`/`tolerance_label` off VERDICT_CHOICES and all FIVE hand-copied chains are gone. 3 view commits + 4 template commits. This also subsumes M13.

### M3 — `apps/procurement/models/GoodsReceiptInspection/ReceiptTolerances.py:100`

- **Found by:** code-reviewer
- **Problem:** `vendor` uses `on_delete=models.SET_NULL`, and `resolve_receipt_tolerance` treats a NULL `vendor_id` as vendor-agnostic (line 315), so deleting a supplier Party silently converts that supplier's tight band into a workspace-wide catch-all rather than retiring it.
- **Fix:** Use `on_delete=models.CASCADE` for `vendor` (matching `item`/`category` on this same model) so a deleted supplier takes its pinned rule with it, and add the matching `AlterField` to migration 0017. Note this is a clone of the same shape in inventory 5.15 — `grep -rn "vendor = models.ForeignKey" -A 2 apps/*/models/ | grep -B1 SET_NULL` finds the sibling in `apps/inventory/models/QualityControl/QcRoutingRules.py:41`.
- **Status:** [x] fixed — fix(procurement): cascade a receipt tolerance policy with its pinned supplier + migrate(procurement): 0018 (claimed 0018; 0017 is applied and was NOT edited, per M4 guidance)

### M4 — `apps/procurement/models/GoodsReceiptInspection/ReturnsToVendor.py:194`

- **Found by:** performance-reviewer
- **Problem:** The register's duplicate-RMA badge is an `Exists` correlated subquery filtering on `(tenant_id, supplier_rma_number)` (apps/procurement/views/GoodsReceiptInspection/ReturnsToVendor.py:95-100), a combination this changeset introduced but did not index, so the database re-scans the RTV table once per row of every list page.
- **Fix:** Add `models.Index(fields=["tenant", "supplier_rma_number"], name="prc_rtv_tnt_rma_idx")` to `ReturnToVendor.Meta.indexes` alongside the existing three, and generate the accompanying `AddIndex` migration (the 6.12 migration is 0017; add 0018 rather than editing the shipped one).
- **Status:** [x] fixed — perf(procurement): index (tenant, supplier_rma_number) on ReturnToVendor + migrate(procurement): 0019 add prc_rtv_tnt_rma_idx

### M5 — `apps/procurement/views/GoodsReceiptInspection/ReceiptBoards.py:227`

- **Found by:** explorer
- **Problem:** `_receipt_by_delivery_ref` matches with a case-SENSITIVE `delivery_note_ref__in=refs` while `receiving_console_book` matches with `delivery_note_ref__iexact` (line 507), so a receipt whose delivery-note reference differs only in case renders as "Not booked yet" on the console even though the book verb will refuse and redirect to it.
- **Fix:** Make the map use the same case-insensitive rule as the verb: build `cond = Q(); for ref in refs: cond |= Q(delivery_note_ref__iexact=ref)` and filter `GoodsReceiptNote.objects.filter(tenant=tenant).filter(cond)` instead of `delivery_note_ref__in=refs` (`Q` is already imported in this module).
- **Status:** [x] fixed — fix(procurement): give the Booked marker and the book verb one definition of same delivery note (`_ref_key` + `Lower(Trim())` in SQL, rather than the 60-term iexact OR-chain the finding sketched — same case-insensitivity, one sargable IN test)

### M6 — `apps/procurement/views/GoodsReceiptInspection/ReceiptBoards.py:306`

- **Found by:** explorer
- **Problem:** `receiving_console`'s `?status=` is applied straight to the queryset without being validated against `CONSOLE_STATUSES`, so `?status=zzz` (or `?status=draft`, which the board can never show) silently returns an empty board while the `<select>` still reads "All open statuses" — every other closed-vocabulary param in this lane (`?arrival=`, `?bucket=`, `?action=`) is sanitized and echoed back.
- **Fix:** Replace lines 306-308 with `status = request.GET.get("status", "").strip()` / `if status in CONSOLE_STATUSES: qs = qs.filter(status=status)` / `else: status = ""`, and pass `"status": status` in the render context; change the template's echo at receiving_console.html:66 from `request.GET.status == val` to `status == val` so the widget reflects the sanitized value.
- **Status:** [x] fixed — fix(procurement): sanitize the console ?status= against CONSOLE_STATUSES + echo the sanitized value in the select

### M7 — `apps/procurement/views/GoodsReceiptInspection/ReceiptBoards.py:751`

- **Found by:** performance-reviewer
- **Problem:** `_tolerance_rules(tenant)` is fetched twice per `tolerance_exceptions` request — once here inside `_uncovered_line_count` and again at line 776 inside `_exception_rows` — issuing the same `ReceiptTolerancePolicy` query with three joins twice for no benefit.
- **Fix:** Hoist the fetch into `tolerance_exceptions` (before the `stats` block) as `rules = _tolerance_rules(tenant)`, add a `rules` parameter to `_uncovered_line_count(tenant, base, rules)` and `_exception_rows(tenant, lines, rules)`, and pass it in at lines 715 and 735.
- **Status:** [x] fixed — perf(procurement): fetch the tolerance rules once per exceptions render

### M8 — `apps/procurement/views/GoodsReceiptInspection/ReceiptDiscrepancies.py:57`

- **Found by:** performance-reviewer
- **Lesson:** L18
- **Problem:** `_ROW_RELATIONS` joins `quarantine_order` but not `quarantine_order__item`, and `inventory.QuarantineOrder.__str__` reads `self.item.sku` (apps/inventory/models/QualityControl/QuarantineOrders.py:296-298); the discrepancy detail template renders `{{ obj.quarantine_order }}` at line 100, so every escalated finding pays an extra query through the related object's `__str__`.
- **Fix:** Add `"quarantine_order__item"` to the `_ROW_RELATIONS` tuple (after `"quarantine_order"`). The list view shares the tuple and does not render that column, so this only widens the join by one already-cheap FK.
- **Status:** [x] fixed — perf(procurement): join quarantine_order__item on the discrepancy row relations

### M9 — `templates/procurement/goodsreceiptinspection/discrepancy/list.html:125`

- **Found by:** frontend-reviewer
- **Lesson:** L33
- **Problem:** The kind/severity/remedy/status badge colours are hand-written `{% if %}` chains that duplicate `ReceiptDiscrepancy.KIND_CSS`/`SEVERITY_CSS`/`REMEDY_CSS`/`STATUS_CSS`, while the tolerance-policy templates in this same sub-module deliberately read `obj.action_css`/`obj.scope_css` from the model — two contradictory conventions in one sub-module, and the duplicated chain is exactly the drift the 6.11 backorder pages already suffered.
- **Fix:** Replace the inline chains with the model properties, which already fall back to `badge-slate` on an unknown value: line 125 → `<span class="badge {{ obj.kind_css }}">{{ obj.get_kind_display }}</span>`, line 126 → `{{ obj.severity_css }}`, line 130 → `{{ obj.remedy_css }}`, line 145 → `{{ obj.status_css }}`. Do the same for the four chains on `discrepancy/detail.html:19-21,46,48,56` and the three on `rtv/list.html:98,102,117` / `rtv/detail.html:7,8,42,45` using `status_css`/`reason_css`/`remedy_css`.
- **Status:** [x] fixed — style(procurement): read the badges from the model *_css properties across all four templates (4 commits). Note: the RTV remedy chain had ALREADY drifted from REMEDY_CSS (replacement slate vs info, repair amber vs slate); the model map wins.

### M10 — `templates/procurement/goodsreceiptinspection/receipt_audit.html:35`

- **Found by:** code-reviewer
- **Problem:** The first stat tile is labelled "Entries in view" but `stats.total` is computed over the UNFILTERED trail (ReceiptBoards.py:854, whose comment says so explicitly), so the number does not change when `?grn=`/`?action=`/`?q=` narrow the table below it.
- **Fix:** Rename the label to "Receiving entries" (or "All entries") so it matches the workspace-wide aggregate the view deliberately computes.
- **Status:** [x] fixed — fix(procurement): label the audit total tile Receiving entries, not Entries in view

### M11 — `templates/procurement/goodsreceiptinspection/receipt_audit.html:87`

- **Found by:** explorer
- **Problem:** The column headers do not describe the cells beneath them: "Record" (line 86) renders the content-type label and "What changed" (line 87) renders `entry.target` — the document number — while the `AuditLog.changes` payload is never surfaced on this board at all.
- **Fix:** Rename the headers to match the data: line 86 `<th>Type</th>` and line 87 `<th>Record</th>`, or keep the labels and move `{{ entry.target }}` into the "Record" cell (line 110 -> line 99-109's cell) and render a short summary of `entry.changes` under "What changed".
- **Status:** [x] fixed — fix(procurement): name the audit columns Type and Record for what they actually render (option (a)). qa-smoke-tester read this as the 6.1 house convention, but that precedent is a 4-column table with no separate type column; the 5-column 6.12 table genuinely mislabels its cells.

### M12 — `templates/procurement/goodsreceiptinspection/receiving_console.html:52`

- **Found by:** frontend-reviewer
- **Problem:** The arrival quick-tab links only carry `q` forward, so clicking "Overdue"/"Today"/"Awaiting" silently discards an active status, vendor or purchase-order filter and widens the board without the user asking.
- **Fix:** Append the other three params to both tab hrefs, the way the sibling exceptions board already does (`tolerance_exceptions.html:51` carries `vendor`). On line 52 use `href="?arrival={{ val }}{% if q %}&q={{ q|urlencode }}{% endif %}{% if request.GET.status %}&status={{ request.GET.status|urlencode }}{% endif %}{% if request.GET.vendor %}&vendor={{ request.GET.vendor|urlencode }}{% endif %}{% if request.GET.po %}&po={{ request.GET.po|urlencode }}{% endif %}"`, and add the same three `{% if request.GET.* %}` clauses to the "All arrivals" href on line 49 (switching its leading `?` handling so the first param still emits `?`).
- **Status:** [x] fixed — fix(procurement): carry status, vendor and purchase-order through the console arrival tabs

### M13 — `templates/procurement/goodsreceiptinspection/receiving_console.html:139`

- **Found by:** frontend-reviewer
- **Problem:** The verdict label chain ends on a bare `{% else %}No policy{% endif %}`, so any verdict token that is not one of the five spelled-out keys is mislabelled "No policy" instead of showing what it actually was — the same chain on the policy detail page already handles this correctly.
- **Fix:** Close the chain the way `tolerancepolicy/detail.html:130-131` does: `{% elif row.tolerance_verdict == 'no_rule' %}No policy{% else %}{{ row.tolerance_verdict }}{% endif %}`. Apply the identical change to the per-line chain at `receiving_console.html:235` (`line.verdict`) and to `tolerance_exceptions.html:138` (`row.verdict`).
- **Status:** [x] fixed — subsumed by the M2 fix: the chains no longer exist, so an unrecognised verdict renders its own token (via `_verdict_label`) instead of being mislabelled "No policy" — in all three places, not just the one M13 cites.

### M14 — `templates/procurement/goodsreceiptinspection/rtv/detail.html:162`

- **Found by:** frontend-reviewer
- **Problem:** The Delete button in the Actions sidebar is rendered as `btn btn-outline`, so the one destructive action on the page looks identical to the neutral Edit/Back buttons beside it — the two sibling detail pages in this same sub-module use the danger variant.
- **Fix:** Change line 162 to `<button class="btn btn-danger" type="submit"><i data-lucide="trash-2"></i> Delete</button>`, matching `discrepancy/detail.html:186` and `tolerancepolicy/detail.html:165`.
- **Status:** [x] fixed — style(procurement): give the RTV detail Delete button the danger variant

## Notes — app-wide / pre-existing (NOT in the fix queue)

### Added by code-fixer while burning this file down

- **Clone family — the 403 button (I9-I12).** Fixed **this sub-module's instance only** (`can_mint`
  on the receiving console). The security-reviewer's lane already lists nine sibling templates with
  the identical shape (`catalogmanagement/catalogitem/detail.html:49,52,62`,
  `catalogmanagement/tier/detail.html:13,20`, `catalogmanagement/uploadbatch/detail.html:16,21,26`,
  `contractsmanagement/clauses/{detail.html:11,list.html:54}`,
  `contractsmanagement/contracts/renewals.html:10`, `sourcingtendering/events/detail.html:17,18,20`,
  `vendormanagement/invoice-submission/detail.html:57`,
  `vendormanagement/suspension/detail.html:83,84,88`). **Recommend one app-wide sweep commit** rather
  than forking 6.12 further ahead of the rest (L18).
- **Clone family — `vendor = SET_NULL` (M3).** Fixed procurement's instance. The sibling
  `apps/inventory/models/QualityControl/QcRoutingRules.py:41` has the same shape and the same
  "NULL vendor means any vendor" resolver semantics, so deleting a supplier there silently promotes
  a pinned QC rule to a workspace-wide one. **Recommend the same `AlterField` for inventory 5.15**;
  not done here because it is another module's migration lane.
- **M2 was fixed the elegant way, and it subsumed M13.** Rather than deleting `VERDICT_CHOICES` or
  passing it into five contexts, the three views now resolve the LABEL (`verdict_label` /
  `tolerance_label`) and hand it down, so all five hand-copied `{% if %}` chains are gone and an
  unrecognised verdict renders its own token instead of being mislabelled "No policy".
- **One regression was introduced and fixed inside this run.** The I2 choice-sharing was first
  written in `BaseReturnToVendorLineFormSet.__init__`, which forces `BaseFormSet.forms` (a
  `cached_property`) to build eagerly and would have frozen every row's dropdown against the
  PRE-edit header — breaking the ordering `rtv_edit` documents. Moved into `_construct_form` and
  committed separately; verified by asserting that a submit which CHANGES `goods_receipt` still
  accepts the new receipt's lines.
- **Verification baseline for this run:** `manage.py check` clean, `makemigrations --check`
  "No changes detected", and `apps/procurement/tests` green at **1081 passed** before and after.
  Two migrations were claimed and committed: **0018** (M3 `AlterField`) and **0019** (M4 `AddIndex`).
  Migration 0017 was NOT edited.

- **code-reviewer:** Verified clean, no finding needed: every new model carries a tenant FK (ReturnToVendorLine is correctly tenant-less and reached only through its RTV header); every queryset and object lookup in the 27 new views is `tenant=request.tenant`-scoped; every tenant-scoped FK dropdown is narrowed in `__init__` AND re-checked on POST (`_reject_foreign` / `BaseReturnToVendorLineFormSet.clean`); migration 0017 matches the models field-for-field including both `unique_together` and all seven indexes; all four package `__init__.py` re-export blocks are complete (27 views, 12 forms, 7 model symbols); every `{% url %}` name in the six new templates resolves (I checked all 37 against `apps/*/urls/`); every template context key exists in its view's context dict; all list filters are applied before pagination and every filter widget's choices/querysets are passed; the three registers have the full CRUD set with POST-only, status-guarded, csrf'd delete in both the actions column and the detail sidebar; template paths follow `<app>/<submodule>/<entity>/<page>.html` with the three computed boards correctly at the sub-module root.

Performance (route to performance-reviewer, not correctness): `_item_map` (ReceiptBoards.py:191-209) loads the ENTIRE tenant item master into Python on every call and is invoked twice per `tolerance_exceptions` render (`_uncovered_line_count` at 758 and `_exception_rows` at 777); `_tolerance_rules` is likewise fetched twice per render. The sibling `_governed_lines` in ReceiptTolerances.py:143-145 already does this correctly with a DB-side `Lower(\"sku\")` `__in` filter — that is the shape `_item_map` should adopt. Also `tolerance_exceptions` issues four separate correlated-subquery COUNTs for the tiles (line 714).

No tests for 6.12 in this changeset (Phase 6 test wave presumably still to run). The ones worth having, for test-writer: `apps/procurement/tests/test_goodsreceipt_views.py` asserting (a) `receiving_console_book` posted twice for one ASN yields exactly one `GoodsReceiptNote` — this is the finding above and would fail today for an ASN with a blank `supplier_reference`; (b) `receiving_console_mint_lots` returns 403 for a non-admin member; (c) `rtv_edit` on a draft whose `goods_receipt` was cancelled preserves `goods_receipt_id`; (d) `rtv_authorize`/`rtv_ship`/`rtv_close` create zero `StockMove` and zero `JournalEntry` rows, which the module docstring promises.

Pre-existing, out of scope: `ReceiptDiscrepancy.goods_receipt_line` and `ReturnToVendorLine.goods_receipt_line`/`po_line` are `PROTECT` onto scm rows, so `seed_scm --flush` will now raise `ProtectedError` while procurement 6.12 rows exist — the same hazard 6.11's `AsnLine.po_line` already introduced.

Comment drift (not worth a fix commit on its own): `ReceiptDiscrepancyForm.__init__` line 77-78 claims it keeps \"the instance's own receipt in range on EDIT\", but the code never does that — it pops the `goods_receipt` field entirely at line 112 instead, which is safe, so only the comment is wrong.
- **security-reviewer:** Checks that came back clean, so a re-reviewer does not redo them: every one of the 27 new views carries `@login_required`; all five destructive/config-write verbs (`tolerancepolicy_create/edit/delete`, `discrepancy_delete`, `rtv_delete`, `rtv_authorize`, `receiving_console_mint_lots`) carry `@tenant_admin_required`; every mutating route is `@require_POST`; all 18 POST `<form>` tags in the new templates carry `{% csrf_token %}`; no `@csrf_exempt`, no `|safe`, no `mark_safe`, no `{% autoescape off %}`, no `.raw()`/`.extra()`/`cursor.execute`, no `?next=` redirect, no secrets in forms or `messages.success`, no inline `style="…{{ }}"` (L26 clear). Mass assignment is correct on all three ModelForms — `tenant`, `number`, `status`, every verb stamp and both `*_at` timestamps are excluded, and `status`/`shipped_on`/`resolved_at`/`vendor_notified_on` are additionally `editable=False` on the models. The evidence upload validates extension against the core `ALLOWED_DOC_EXTENSIONS` (no `.svg`, so the inline `<img>` render at `discrepancy/detail.html:80` is safe) and size against the core 20MB `MAX_UPLOAD_BYTES`, imported locally so the catalog uploader's 2MB constant cannot shadow it. The `?quantity_affected=` hand-parsed Decimal at `ReceiptDiscrepancies.py:265-278` is a textbook L35 guard (try/except + `is_finite()` + a ceiling derived from `max_digits`). `evidence_url` is a `URLField`, so Django's default scheme allowlist already rejects `javascript:`.

App-wide / pre-existing, NOT actionable here: (1) `MEDIA` files are served without an auth check, so `procurement/receipt_evidence/YYYY/MM/<name>` is readable by anyone with the URL regardless of tenant — the same posture as every other FileField in the repo (avatars, contract documents), and it wants one project-level fix rather than a per-sub-module one. (2) The 403-button shape in finding #1 is a family pattern, not a one-off. The check that finds the rest: list the admin-gated verb names with `grep -rn "tenant_admin_required" -A3 apps/procurement/views/` , then for each name `grep -rn "procurement:<verb>" templates/procurement/` and confirm the hit sits inside `{% if request.user.is_superuser or request.user.is_tenant_admin %}`. Running that across the app surfaces the same shape (out of scope for this changeset) in `catalogmanagement/catalogitem/detail.html:49,52,62`, `catalogmanagement/tier/detail.html:13,20`, `catalogmanagement/uploadbatch/detail.html:16,21,26`, `contractsmanagement/clauses/{detail.html:11,list.html:54}`, `contractsmanagement/contracts/renewals.html:10`, `sourcingtendering/events/detail.html:17,18,20`, `vendormanagement/invoice-submission/detail.html:57` and `vendormanagement/suspension/detail.html:83,84,88` — worth one sweep commit (L28 pattern-clones) rather than nine separate discoveries.
- **performance-reviewer:** Out-of-lane / pre-existing observations, not for the fix queue:

1. `tolerance_exceptions` (ReceiptBoards.py:714) issues four separate `COUNT`s, each of which runs the `_cumulative_received()` correlated subquery over every live receipt line in the workspace, and `_uncovered_line_count` adds a fifth full GROUP BY. The comment at 711-714 correctly explains why a single conditional aggregate is not portable here. On a workspace with 100k+ receipt lines this board will be the slowest page in procurement, but fixing it properly means materialising received-per-PO-line (a denormalised, refreshed-on-write summary), which is an app-wide architectural decision well outside a sub-module review — flagging it as a scale watch item rather than a finding.

2. Neither `ReceiptDiscrepancy` nor `ReturnToVendor` indexes its default `Meta.ordering` of `["-created_at", "-id"]`. This matches the app-wide reference pattern exactly — no procurement model indexes `(tenant, created_at)` (checked all 20 `models.Index` declarations under apps/procurement/models) — so it is an app-wide pass, not a 6.12 fork. Do not fix it here.

3. `_ROW_RELATIONS` on the discrepancy register joins `nonconformance` and `quarantine_order` for the LIST as well as the detail, though the list template renders neither. Two surplus LEFT JOINs on a 15-row page is not worth splitting the tuple; noted only so a future reader does not mistake it for a needed join.

4. Suggested `django_assert_max_num_queries` coverage for the test-writer, once the fixes above land: `procurement:receiving_console` and `procurement:tolerance_exceptions` each asserted against a fixture with 1 row versus 20 rows (the count must not grow), and `procurement:rtv_list` asserted against a page whose returns each carry 3+ lines (must stay flat thanks to the `Prefetch`).
- **frontend-reviewer:** Verified clean and worth recording so the fixer does not re-litigate: no L2 comment leak anywhere (zero `{#` in the 12 new templates); no L33 class invention (all `badge-*` and `stat-icon *` modifiers exist in static/css/theme.css, and the four new model `*_CSS` maps only emit colour-named classes); L9 pagination is delegated to `templates/partials/pagination.html`, which guards `has_previous`/`has_next` and re-emits every GET param except `page`; L10 None-safe display is handled everywhere a nullable FK feeds a filter argument (`{% if entry.user %}`, `{% if obj.created_by %}`, `{% if obj.resolved_by %}`, `{% if row.receipt %}`, `{% if obj.item %}`); every `{% url %}` name resolves (procurement `discrepancy_*`/`rtv_*`/`tolerancepolicy_*`/`tolerance_exceptions`/`receiving_console*`/`receipt_audit`/`asn_*`/`activity_detail`, scm `goodsreceipt_*`/`purchaseorder_detail`/`item_detail`/`lotserial_list`, `core:party_detail` via the crud() factory); pk filters all use `|stringformat:"d"`; every table is inside `.table-wrap`; template paths follow the mandated `<submodule>/<entity>/<page>.html` shape with the three computed boards correctly at the sub-module root.

App-wide / pre-existing, NOT actionable for this sub-module: (1) `<th class="table-actions">` is used on the Actions header in the four new list/board tables, which applies `display:flex` to a table header cell where `.th-actions` (`text-align:right; white-space:nowrap`) is the intended class — but the repo already has 502 templates doing this versus 39 using `th-actions`, so it is the de-facto house convention and fixing it here alone would just add inconsistency. (2) The list-page search/filter controls use `aria-label` rather than a visible `<label for>`; that matches 388 of the 409 existing templates carrying `name="q"`, and the three new board pages (receiving console, tolerance exceptions, receipt audit) actually go further with proper `<label for>` + `id` pairs. (3) The inline formset table in `rtv/form.html` renders its widgets with no per-cell label (screen readers get only the `<th>` text) — this is copied verbatim from `templates/procurement/orderfulfillment/asn/form.html:44-66`, so it is a module-wide formset pattern rather than new drift; worth one deliberate pass across all procurement formset tables (an `sr-only` label per control, as `receiving_console.html:214` already does for the qty inputs) rather than a one-off fix here.
- **explorer:** PRE-EXISTING / APP-WIDE, not for the fix queue:

1. `seed_scm --flush` ProtectedError hazard. seed_scm's `_flush()` deletes `GoodsReceiptLine`/`GoodsReceiptNote`/`PurchaseOrderLine`/`PurchaseOrder` (apps/scm/management/commands/seed_scm.py:1471-1474). 6.12 adds four new cross-app PROTECT FKs onto those tables (`ReceiptDiscrepancy.goods_receipt`, `ReceiptDiscrepancy.goods_receipt_line`, `ReturnToVendorLine.goods_receipt_line`, `ReturnToVendorLine.po_line`), so a `seed_scm --flush` run after `seed_procurement` will raise. The failure mode is NOT new — 6.11's `AsnLine.po_line` and `AdvancedShipmentNotice.purchase_order` are already PROTECT onto the same PO tables — so this is a standing cross-command ordering issue rather than a 6.12 regression. Worth a run-book note ("flush procurement before scm"), not a code change here.

2. The four new url modules' docstrings each assert "The app registers no greedy `<str:…>` converter". That is factually wrong — `apps/procurement/urls/ContractsManagement/Contracts.py:16` declares `contract-sign/<str:token>/`. It is harmless (the converter sits under a literal first segment so it can shadow nothing), and the same sentence was copied from the 6.11 modules, so this is inherited boilerplate rather than a 6.12 defect. I verified independently: no duplicate `name=` and no duplicate `path()` pattern anywhere in the concatenated procurement URLconf.

3. Performance lane (flagging only, not mine to fix): `_item_map` (ReceiptBoards.py:191) iterates the entire tenant item master in Python rather than filtering in the DB, and `tolerance_exceptions` calls it twice per render (once inside `_uncovered_line_count`, once inside `_exception_rows`). Its docstring claims "ONE query", which is true, but the row scan is unbounded.

4. `rtv_detail` passes both `lines` and `line_rows` (ReturnsToVendor.py:174-175); the template reads `lines` only for `{{ lines|length }}` (rtv/detail.html:67), which `line_rows` could serve equally. Harmless redundancy, mentioned only so a fixer does not mistake `lines` for dead context and delete it.
- **qa-smoke-tester:** RUNTIME SWEEP RESULT — 6.12 Goods Receipt & Inspection. DB: migrate (no pending), seed_core + seed_accounts + seed_scm + seed_procurement, all idempotent. Logged in as admin_acme (Acme Inc). 143 total checks across 7 passes, 1 problem (the finding above). `manage.py check` clean.

| url name | GET status | content check |
|---|---|---|
| procurement:dashboard (landing) | 200 | OK |
| tolerancepolicy_list | 200 | title "Receipt Tolerances" |
| tolerancepolicy_list ?q=a&action=warn&active=active&scope=catchall | 200 | OK |
| tolerancepolicy_list ?category=abc&item=abc&vendor=zzz&scope=zzz&page=abc | 200 | OK (junk ignored, L11) |
| tolerancepolicy_list ?page=2 (42 rows / 15) | 200 | "Showing 16-30 of 42" |
| tolerancepolicy_create | 200 | "New Receipt Tolerance" |
| tolerancepolicy_detail | 200 | policy name + scope_label + worked example + governed-lines panel + advisory note all present |
| tolerancepolicy_edit | 200 | OK |
| tolerancepolicy_delete | 405 GET / 302 POST | OK |
| discrepancy_list | 200 | title "Receipt Discrepancies" |
| discrepancy_list ?q=a&status=open&severity=critical&kind=damaged | 200 | OK |
| discrepancy_list ?category=abc&grn=abc&vendor=999999999999999999999&status=zzz | 200 | OK |
| discrepancy_list ?page=2 (42 rows / 15) | 200 | "Showing 16-30 of 42" |
| discrepancy_create | 200 | "New Receipt Discrepancy" |
| discrepancy_create ?goods_receipt=&goods_receipt_line=&kind=&quantity_affected= (real prefill) | 200 | OK |
| discrepancy_create ?quantity_affected=nan / =Infinity / pks=abc | 200 | OK (decimal L11 guard holds) |
| discrepancy_detail | 200 | RDS number, GRN number, kind/severity displays, description, tolerance-verdict panel |
| discrepancy_edit (open RDS-00001) | 200 | "Edit RDS-00001" + upload hint |
| discrepancy_edit (resolved RDS-00002) | 302 | correct refusal |
| discrepancy_delete / notify_vendor / resolve / cancel | 405 GET / 302 POST | OK incl. empty-body POST -> 302 not 500; cancel drove status to `cancelled` |
| rtv_list | 200 | title "Returns to Vendor" |
| rtv_list ?q=a&status=draft&reason=damaged&remedy=credit | 200 | OK |
| rtv_list ?category=abc&vendor=abc&po=999999999999999999999 | 200 | OK |
| rtv_list ?page=2 (42 rows / 15) | 200 | "Showing 16-30 of 42" |
| rtv_create | 200 | "New Return to Vendor" |
| rtv_create ?discrepancy=<real> / =abc | 200 | OK |
| rtv_detail | 200 | RTV number, vendor, status display, 2 line rows w/ descriptions, non-posting note |
| rtv_edit (draft) | 200 | OK |
| rtv_edit (non-draft) | 302 | correct refusal |
| rtv_delete / authorize / ship / close / cancel | 405 GET / 302 POST | OK incl. empty-body POST |
| receiving_console | 200 | title, stat tiles, ASN rows, qty_<pk> inputs present |
| receiving_console ?q=a&arrival=overdue&status=in_transit | 200 | OK |
| receiving_console ?category=abc&vendor=abc&po=zzz&arrival=zzz&status=zzz | 200 | OK |
| receiving_console ?page=2 (42 ASNs / 30) | 200 | "Showing 31-42 of 42" |
| receiving_console_book | 405 GET / 302 POST | real book, empty-refusal and qty=nan all 302 |
| receiving_console_mint_lots | 405 GET / 302 POST | 302 as admin, 403 as member -> see finding |
| tolerance_exceptions | 200 | title; buckets over/short/early/late all 200, prefill "Raise" deep links render where rows exist |
| tolerance_exceptions ?category=abc&bucket=zzz&vendor=abc | 200 | OK (unknown bucket falls back) |
| tolerance_exceptions ?page=2 (46 lines / 30) | 200 | "Showing 31-46 of 46" |
| receipt_audit | 200 | title, 30 entries, activity_detail links |
| receipt_audit ?grn=<real> / ?action=create&q=a / ?grn=abc&action=zzz | 200 | OK |
| receipt_audit ?page=2 (40 entries / 30) | 200 | "Showing 31-40 of 40" |

Comment/leak check: zero `{#` and zero `{% comment` in any rendered body across all pages.

Cross-tenant IDOR (as admin_acme, globex pks): tolerancepolicy_detail 404, tolerancepolicy_edit 404, discrepancy_detail 404, discrepancy_edit 404, rtv_detail 404, rtv_edit 404. `receipt_audit?grn=<globex pk>` returns 200 and silently ignores the foreign pk (no "Scoped to" banner, no foreign rows) — my first automated check flagged it, but that was a FALSE POSITIVE: GRN numbering is per-tenant so both tenants own a row literally named "GRN-00002". Verified by diffing bodies — the only difference is the querystring echoed into the pagination links. Not a leak, not a finding.

Also swept as admin_globex (second tenant): all 6 board/list pages 200 with titles, all 3 create pages 200, all 3 detail pages 200 with the identifier present. Swept as `ops_acme` (non-admin member): all reads 200; `tolerancepolicy_create` 403 (correct, `@tenant_admin_required`), and the tolerance-policy list/detail correctly hide Add/Edit/Delete for a member.

Pre-existing / out of scope: (1) `@tenant_admin_required` in `apps/core/decorators.py:19` raises `PermissionDenied` (hard 403 page) rather than redirecting with a message — app-wide behaviour, not a 6.12 change; the finding above is about not OFFERING the button, not about changing the decorator. (2) `templates/procurement/goodsreceiptinspection/receipt_audit.html:87` labels a column "What changed" while the cell renders `entry.target` (the document label, not the diff) — but that is exactly the 6.1 precedent in `templates/procurement/dashboardportal/activity.html:48`, so it is a house convention rather than 6.12 drift. (3) `temp/` holds ~400 stale artefacts from earlier sessions; I removed only my own eight scripts.

## Done well

- **code-reviewer:** The tenancy work on `scm.GoodsReceiptLine` — a model with no tenant column of its own — is genuinely careful and consistent across all three surfaces: the form queryset is scoped through `goods_receipt__tenant` (ReceiptDiscrepancies.py:89), the crafted-POST re-check deliberately bypasses `_reject_foreign` and walks the header instead because the shared helper would compare `None` to the tenant pk and reject every valid line (ReceiptDiscrepancies.py:142-150), the formset re-checks it per row (ReturnsToVendor.py:227-234), and the model's own `clean()` closes it a third time (ReceiptDiscrepancies.py:225-230). That is the one hole `TenantModelForm` cannot see, and it was found and shut in all four places.
- **security-reviewer:** Tenant scoping is airtight across all 27 new views: every single pk lookup uses `get_object_or_404(..., pk=pk, tenant=request.tenant)` or a pre-scoped queryset, every state-changing verb runs inside `transaction.atomic()` with `select_for_update()`, and — the part that is usually missed — both query-string prefills (`?goods_receipt=&goods_receipt_line=` on `discrepancy_create`, `?discrepancy=` on `rtv_create`) re-validate every referenced pk against `request.tenant` and silently drop it when it is not ours, including scoping the tenant-less `scm.GoodsReceiptLine` through its header. The two `scm` models with no tenant column of their own (`GoodsReceiptLine`, `PurchaseOrderLine`) are correctly narrowed through `goods_receipt__tenant` / `purchase_order__tenant` in the forms and re-checked in `clean()`, and the `qty_<asn_line.pk>` dynamic-field design in `ReceivingConsoleBookForm` makes a crafted quantity for a foreign ASN line a field that simply does not exist.
- **performance-reviewer:** The RTV register is the model of how a derived-value list page should be assembled: `_scoped()` (apps/procurement/views/GoodsReceiptInspection/ReturnsToVendor.py:80-105) resolves the duplicate-RMA badge as a single `Exists` annotation instead of a per-row `.exists()`, prefetches `lines` with the exact `select_related` chain that `expected_credit`'s `po_line.unit_price` / `goods_receipt_line.po_line.unit_price` hops need, and `ReturnToVendor.line_rows()` honours that prefetch (`if "lines" in self._prefetched_objects_cache`) so the credit total, the line count and the rendered table all walk the same instances — a 15-row page stays at a fixed query count. The four stat cards on both registers are single `.aggregate(Count(filter=...))` calls rather than four round trips, and every filter on every new page is applied to the queryset before `Paginator`.
- **frontend-reviewer:** Every badge branch keys off the exact model CHOICES token and every modifier class was cross-checked against theme.css — the four new `_CSS` maps in the models are colour-named only (`badge-green/red/amber/info/muted/slate`), the label always comes from `get_FIELD_display` outside the class chain so a colour miss can never blank a label, and the `stat-icon red` tiles use a variant that genuinely exists (`.stat-icon.red`, theme.css:265). L2 is clean too: all 12 templates use `{% comment %}...{% endcomment %}` for multi-line notes and there is not a single `{#` in the changeset.
- **explorer:** The layer contract is airtight and verifiably so: every one of the 12 new templates' root variables maps to a key the view actually passes (I extracted them mechanically and diffed against each `render()`/`crud_list` context), all 27 url names reverse, all 12 `render()` template paths resolve through the loader, all three package `__init__.py` re-export blocks are complete (27 views / 12 forms / 7 models), and `LIVE_LINKS[\"6.12\"]` matches all ten NavERP.md bullets byte-for-byte with zero dead targets and zero orphan \"extra\" rows — including the six deliberate cross-app maps (`inventory:qcchecklist_list`, `inventory:quarantineorder_list`, `scm:lotserial_list`, `inventory:barcodelabel_list`, `scm:goodsreceipt_list?status=received`, which `_safe_reverse` handles correctly). Every 6.12 page and its junk-param/page-2 variants returned 200 against the seeded workspace, `manage.py check` is clean and `makemigrations --check` reports no changes.
- **qa-smoke-tester:** Every list/board applies its filters as ORM predicates BEFORE pagination and hand-rolls nothing about paging — all six paginated pages (`tolerancepolicy_list`, `discrepancy_list`, `rtv_list`, `receipt_audit`, `tolerance_exceptions`, `receiving_console`) go through `apps.core.crud.paginate` + the L9-safe `partials/pagination.html`, and I proved page 2 is a real second page on all six by bulk-loading 40+ rows (e.g. tolerance_exceptions bucket=over: p1 "Showing 1-30 of 46", p2 "Showing 31-46 of 46", 200 with the title intact). Query counts stayed flat at 21 for a 30-row receiving console and 16 for tolerance_exceptions, so the per-row derived verdicts genuinely batch instead of N+1-ing.
