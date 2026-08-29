# Review findings — procurement 6.11 Order Fulfillment & Tracking

Range: `72b7680af515b7c42428e75845c4a44a667582aa...HEAD` · Generated: 2026-08-29
Wave (parallel): code-reviewer · security-reviewer · performance-reviewer · frontend-reviewer · explorer · qa-smoke-tester

## Summary

| Severity | Count |
|---|---|
| Critical | 0 |
| Important | 9 |
| Minor | 17 |
| **Total (deduped)** | **26** |

| Agent | Raw findings |
|---|---|
| code-reviewer | 6 |
| security-reviewer | 2 |
| performance-reviewer | 4 |
| frontend-reviewer | 8 |
| explorer | 6 |
| qa-smoke-tester | 1 |

## How to work this file (code-fixer)

Fix in ID order: every `C`, then every `I`, then every `M`. One fix → one file → one `git add` + one
`git commit`. Update each **Status** line to `[x] fixed — <commit subject>` or `[~] skipped — <reason>`
as you go. Never delete a finding; a wrong one gets `[~] skipped — not a defect: <why>`. Never `git push`.

## Important

### I1 — `apps/procurement/forms/OrderFulfillment/AdvancedShipmentNotice.py:73`

- **Found by:** performance-reviewer
- **Lesson:** L18
- **Problem:** The ASN create page's `purchase_order` dropdown renders `str(PurchaseOrder)`, which is `f"{self.number} · {self.vendor}"` (apps/scm/models/ProcurementManagement/PurchaseOrders.py:169) — a second FK hop to `core.Party`. The queryset has no `select_related("vendor")` and is unbounded, so `GET /procurement/asns/new/` costs 1 + P queries where P is every receivable PO in the workspace.
- **Fix:** Line 73: `self.fields["purchase_order"].queryset = receivable.select_related("vendor").order_by("-order_date", "-id")`. This is the chained-`__str__` case: `select_related("vendor")` on the FORM queryset, not just on the list view. Add a `django_assert_max_num_queries` test around the ASN create GET with ~20 receivable POs seeded.
- **Status:** [x] fixed — perf(procurement): select_related the vendor on the ASN purchase_order dropdown queryset

### I2 — `apps/procurement/management/commands/seed_procurement.py:1186`

- **Found by:** qa-smoke-tester
- **Lesson:** L39
- **Problem:** The seeder picks the first RECEIVABLE purchase order and its `lines[0]` without checking that the line still has an outstanding balance; on both seeded tenants that is PO-00001 whose first lines are already fully received (ordered 5.0000 / received 5.0000 / outstanding 0.0000), so `AsnLine.outstanding_at_declare` is 0 and the "deliberately short" line (shipped 1.0000 of 5.0000) renders as OVER-shipped with `shortfall == 0` — the ASN detail page's `{% if line.is_short %}` "Record backorder" hand-off link never renders and the whole ASN-shortfall -> backorder prefill path (`_create_initial` in views/OrderFulfillment/Backorder.py) is unreachable from the demo data.
- **Fix:** In `_seed_order_fulfillment`, replace the order/line pick at lines 1186-1207 so the demo lands on a line that still has headroom. (1) Select the order as the first receivable one that has a line with a live balance, e.g. `order = next((o for o in _PO.objects.filter(tenant=tenant, status__in=_PO.RECEIVABLE_STATUSES).order_by("id") if any(l.outstanding_quantity() > 0 for l in o.lines.all())), None)` and keep the existing None warning/return. (2) At line 1198 pick `first = next((l for l in lines if l.outstanding_quantity() > 0), lines[0])` and `second = next((l for l in lines if l is not first and l.outstanding_quantity() > 0), first)`. (3) At lines 1202-1207 size the shortfall against the OUTSTANDING balance, not the ordered quantity: `first_qty = first.outstanding_quantity() or Decimal("1")` (leave the `gap`/`short_qty` arithmetic below unchanged). Verified this is satisfiable for both tenants: acme PO-00001 line 584 has outstanding 1.0000 and PO-00002 line 591 has 40.0000; globex PO-00001 line 587 has outstanding 1.0000. After the change re-run `seed_procurement --flush` and confirm the ASN detail shows an amber variance badge plus the "Record backorder (N)" button.
- **Status:** [x] fixed — fix(procurement): seed order fulfillment against a PO line that still has an outstanding balance so the ASN shortfall path has demo data (verified in a rolled-back transaction on both tenants: verdict now `short`, shortfall 0.5000, `is_short` True — no `--flush` run, the seeder block is guarded and the concurrent 6.10 session is using the DB)

### I3 — `apps/procurement/migrations/0016_advancedshipmentnotice_asnline_deliveryschedule_and_more.py:13`

- **Found by:** explorer
- **Lesson:** L43
- **Problem:** 0016 (committed) declares `('procurement', '0015_purchaseorderchange_purchaseorderchangeline_and_more')` as a dependency, but 0015 is still UNTRACKED in git (it belongs to the concurrent 6.10 session), so at HEAD any fresh checkout / CI run dies with NodeNotFoundError before a single migration applies.
- **Fix:** Do NOT `git add` 0015 from this session (L45 — that tree is not yours). Confirm with the concurrent 6.10 session that `apps/procurement/migrations/0015_purchaseorderchange_purchaseorderchangeline_and_more.py` is committed before this branch is pushed. If 6.10 is abandoned/renumbered, regenerate 0016 with `dependencies = [... ('procurement', '0014_alter_cataloguploadbatch_party_and_more')]` and rerun makemigrations --check.
- **Status:** [~] skipped — cross-session; 0015 belongs to the concurrent 6.10 build (L45). Re-pointing to 0014 would split the migration graph locally. Resolution is that 6.10 commits 0015 before push; flagged to the user.

### I4 — `apps/procurement/migrations/0016_advancedshipmentnotice_asnline_deliveryschedule_and_more.py:14`

- **Found by:** code-reviewer
- **Lesson:** L43
- **Problem:** 0016 declares `('procurement', '0015_purchaseorderchange_purchaseorderchangeline_and_more')` as a dependency, but 0015 is NOT committed at HEAD (it is an untracked file belonging to the concurrent 6.10 session), so a fresh checkout of this range raises `NodeNotFoundError` on any `migrate`/`makemigrations` — i.e. every management command that builds the migration graph fails.
- **Fix:** Do not push/merge this range until the concurrent 6.10 session has committed `apps/procurement/migrations/0015_purchaseorderchange_purchaseorderchangeline_and_more.py`. If 6.10 is abandoned or lands later, re-point this file's dependency to `('procurement', '0014_alter_cataloguploadbatch_party_and_more')` and rename it to `0015_...`.
- **Status:** [~] skipped — cross-session; 0015 belongs to the concurrent 6.10 build (L45). Re-pointing to 0014 would split the migration graph locally. Resolution is that 6.10 commits 0015 before push; flagged to the user.

### I5 — `apps/procurement/views/OrderFulfillment/AdvancedShipmentNotice.py:118`

- **Found by:** performance-reviewer
- **Problem:** `asn_detail` hands `obj.line_rows()` to the template; every row's `outstanding_at_declare` / `variance` / `shortfall` calls `po_line.outstanding_quantity()` -> `received_quantity()`, which issues one GRN-line `Sum()` aggregate per `PurchaseOrderLine` instance (apps/scm/models/ProcurementManagement/PurchaseOrders.py:200-211). The header's `{{ obj.discrepancy_verdict }}` walks the same rows. Result: 1 + N aggregate queries for an N-line notice (the formset allows up to 50).
- **Fix:** In `asn_detail`, after `lines = obj.line_rows()`, seed the per-instance cache from the spine's one-query helper: `received = obj.purchase_order.received_by_line()` then `for row in lines:` / `if row.po_line_id: row.po_line._received_qty_cache = received.get(row.po_line_id) or Decimal("0")`. Add `from decimal import Decimal` to the module imports (it is not in `views/_common.py`). Pass `lines` (the seeded list) as the `lines` context key. This turns N aggregates into 1, and `PurchaseOrder.received_by_line()`'s own docstring names this as the intended caller pattern.
- **Status:** [x] fixed — perf(procurement): seed the ASN detail line memos from received_by_line so N receipt aggregates become 1

### I6 — `apps/procurement/views/OrderFulfillment/FulfillmentBoards.py:174`

- **Found by:** performance-reviewer
- **Problem:** The delivery-confirmation board's `?due=confirmed` tab renders `row.confirmed_by.get_full_name` for every row (templates/procurement/orderfulfillment/delivery_confirmation.html:100) but `confirmed_by` is not in `_BOARD_SELECT_RELATED`, so a 15-row Confirmed page costs 1 + 15 queries (one User fetch per row).
- **Fix:** In `delivery_confirmation`, change `.select_related(*_BOARD_SELECT_RELATED)` (line 174) to `.select_related(*_BOARD_SELECT_RELATED, "confirmed_by")`. Do NOT add it to `_BOARD_SELECT_RELATED` itself — `inbound_tracking` never renders `confirmed_by` and would gain a pointless LEFT JOIN. Worth a `django_assert_max_num_queries` test on `GET /procurement/order-fulfillment/delivery-confirmation/?due=confirmed` with 15 delivered ASNs seeded, each with a distinct `confirmed_by` user.
- **Status:** [x] fixed — perf(procurement): select_related confirmed_by on the delivery-confirmation board queryset only

### I7 — `templates/procurement/orderfulfillment/asn/list.html:101`

- **Found by:** code-reviewer
- **Lesson:** L32
- **Problem:** The Actions-column delete form is rendered for every logged-in member whenever `obj.status == 'draft'`, but `asn_delete` is `@tenant_admin_required` and raises `PermissionDenied` — a non-admin who clicks the bin gets a hard 403, and the sibling detail page already gates the same button on `can_delete`.
- **Fix:** Wrap the `{% if obj.status == 'draft' %}` delete block in an admin test exactly as `templates/procurement/orderfulfillment/backorder/list.html:119` does — `{% if obj.status == 'draft' and request.user.is_superuser or ... %}` is fragile, so use a nested guard: `{% if obj.status == 'draft' %}{% if request.user.is_superuser or request.user.is_tenant_admin %}<form …>{% endif %}{% endif %}`.
- **Status:** [x] fixed — fix(procurement): gate the ASN register delete button on tenant-admin as well as draft status

### I8 — `templates/procurement/orderfulfillment/asn/list.html:101`

- **Found by:** explorer
- **Problem:** The row Delete form is gated only on `{% if obj.status == 'draft' %}`, but `asn_delete` is `@tenant_admin_required` (apps/procurement/views/OrderFulfillment/AdvancedShipmentNotice.py:212), so any non-admin workspace member sees a Delete button that raises PermissionDenied (403 error page) when clicked.
- **Fix:** Change line 101 to `{% if obj.status == 'draft' and request.user.is_superuser or obj.status == 'draft' and request.user.is_tenant_admin %}` — or more cleanly nest: `{% if obj.status == 'draft' %}{% if request.user.is_superuser or request.user.is_tenant_admin %} …delete form… {% endif %}{% endif %}`, matching the sibling pattern already used at templates/procurement/orderfulfillment/backorder/list.html:119 and the ASN detail page's own `can_delete` (admin AND draft).
- **Status:** [x] fixed — fix(procurement): gate the ASN register delete button on tenant-admin as well as draft status (same one-line gate as I7/M8/M9)

### I9 — `templates/procurement/orderfulfillment/inbound_tracking.html:45`

- **Found by:** frontend-reviewer
- **Problem:** The Status filter is populated from the full `AdvancedShipmentNotice.STATUS_CHOICES` (5 values) but the board queryset is hard-restricted to `IN_FLIGHT_STATUSES = ("submitted", "in_transit")` (view line 100), so selecting Draft, Delivered or Cancelled silently returns an always-empty board with no explanation — three of the five options can never match.
- **Fix:** Restrict the choice list at the source: in `apps/procurement/views/OrderFulfillment/FulfillmentBoards.py:119` change `"status_choices": AdvancedShipmentNotice.STATUS_CHOICES,` to `"status_choices": [c for c in AdvancedShipmentNotice.STATUS_CHOICES if c[0] in AdvancedShipmentNotice.IN_FLIGHT_STATUSES],`. The template loop at line 45 then needs no change and matches its own "All in-flight statuses" blank option.
- **Status:** [x] fixed — fix(procurement): offer only the in-flight statuses in the inbound-tracking status filter

## Minor

### M1 — `apps/procurement/forms/OrderFulfillment/Backorder.py:40`

- **Found by:** code-reviewer
- **Problem:** `revised_promise_date` stays on the form for EDIT as well as CREATE, so any member can move the promised date through `backorder_edit` without `reschedule()` running — `reschedule_count` is not incremented and `original_promise_date` is not backfilled, silently under-reporting the slip count this register is built around (the form template at backorder/form.html:33 asks users not to, but nothing enforces it).
- **Fix:** In `BackorderForm.__init__`, after the queryset narrowing, add `if self.instance.pk: self.fields.pop("revised_promise_date", None)` — the same drop-the-field-on-edit pattern `AdvancedShipmentNoticeForm.__init__` already uses for `purchase_order` — so post-create moves can only go through the counted `backorder_reschedule` verb.
- **Status:** [x] fixed — fix(procurement): drop revised_promise_date from the backorder edit form so a slip can only move through the counted reschedule verb

### M2 — `apps/procurement/views/OrderFulfillment/AdvancedShipmentNotice.py:196`

- **Found by:** security-reviewer
- **Problem:** `asn_edit` is a hand-rolled save path that writes an AuditLog row containing only `{"action": "edit", "lines": <count>}`, so the immutable trail records that the header changed but not WHICH of carrier / tracking_number / expected_delivery_date / supplier_reference / freight terms was altered — exactly the fields a disputed inbound delivery is later argued over.
- **Fix:** Reuse the shared redaction-aware diff helper instead of a hand-written dict. Add `from apps.core.crud import _changed` to the imports and merge its output into the payload:

```python
from apps.core.crud import _changed  # top of file, next to the existing imports

...
            changes = _changed(form)
            changes["lines"] = obj.lines.count()
            write_audit_log(request.user, obj, "update", changes)
```

`_changed(form)` already routes anything in `_SENSITIVE_AUDIT_FIELDS` through `***redacted***`, so this keeps the sensitive-field policy in one place rather than duplicating a list. Note `_changed(form)` must be read BEFORE `form.save()` is not required (it reads `form.changed_data` / `form.cleaned_data`, both populated by `is_valid()`), so the placement above is safe. Family sweep (L28): `rg -n "def \w+_(edit|create)\(" apps/procurement/views -A 25 | rg "write_audit_log\(request\.user, obj, .update."` finds the other hand-rolled save paths in this app that log an action label instead of a field diff (`RfxManagement/Responses.py:116` logs no changes at all).
- **Status:** [x] fixed — security(procurement): record the changed ASN header fields in the edit audit log via the shared redaction-aware diff (verified: audit payload is now {'tracking_number': 'MF-CHANGED-0001', 'lines': 2})

### M3 — `apps/procurement/views/OrderFulfillment/AdvancedShipmentNotice.py:277`

- **Found by:** code-reviewer
- **Problem:** When the delivery-confirmation board's inline form posts with `next=confirmation`, `_back()` redirects to `procurement:delivery_confirmation` with no query string, so a buyer working the Overdue or Awaiting tab is silently dropped back onto the default "Due today" tab after every confirmation.
- **Fix:** Read `due = request.POST.get("due", "").strip()` alongside `next`, keep it only if it is in `FulfillmentBoards._BUCKET_KEYS`, and return `redirect(f"{reverse('procurement:delivery_confirmation')}?due={due}")` when set; add `<input type="hidden" name="due" value="{{ bucket }}">` next to the existing `next` hidden input at templates/procurement/orderfulfillment/delivery_confirmation.html:105.
- **Status:** [x] fixed — fix(procurement): keep the delivery-confirmation tab on the post-confirm redirect + fix(procurement): post the current arrivals tab back with the inline confirm form

### M4 — `apps/procurement/views/OrderFulfillment/Backorder.py:61`

- **Found by:** performance-reviewer
- **Problem:** `backorder_list`'s base queryset select_relates `delivery_schedule`, `asn` and `alert`, but templates/procurement/orderfulfillment/backorder/list.html renders none of them — three unnecessary LEFT JOINs on every list page, each dragging an unused TextField (`asn.notes`, `asn.cancellation_reason`, `delivery_schedule.notes`, `alert.message`) into every row.
- **Fix:** Narrow line 60-61 to `.select_related("po_line", "po_line__purchase_order")` — that is exactly what the list template and `Backorder.__str__` touch. Leave `backorder_detail`'s wider `select_related` (line 99-101) alone; that page does render all three.
- **Status:** [x] fixed — perf(procurement): drop three unrendered joins from the backorder register queryset

### M5 — `apps/procurement/views/OrderFulfillment/FulfillmentBoards.py:119`

- **Found by:** code-reviewer, explorer
- **Lesson:** L39
- **Problem:** `inbound_tracking` passes the full `AdvancedShipmentNotice.STATUS_CHOICES` to a board whose queryset is hard-filtered to `IN_FLIGHT_STATUSES`, so picking Draft / Delivered / Cancelled in the ?status= dropdown always renders an empty board with no explanation.
- **Fix:** Pass only the reachable pairs, e.g. `"status_choices": [(v, l) for v, l in AdvancedShipmentNotice.STATUS_CHOICES if v in AdvancedShipmentNotice.IN_FLIGHT_STATUSES],` — the template's "All in-flight statuses" blank option then tells the truth.
- **Also suggested:** Replace line 119 with `"status_choices": [(v, l) for v, l in AdvancedShipmentNotice.STATUS_CHOICES if v in AdvancedShipmentNotice.IN_FLIGHT_STATUSES],` so the widget only offers Submitted and In Transit.
- **Status:** [x] fixed — fix(procurement): offer only the in-flight statuses in the inbound-tracking status filter (same change as I9)

### M6 — `templates/procurement/orderfulfillment/asn/detail.html:9`

- **Found by:** frontend-reviewer
- **Problem:** The discrepancy badge prints the raw property value as its label — it reads "Declared vs outstanding: ok" / "short" / "over" / "mixed" instead of prose — and the `|default:"—"` is dead code because `discrepancy_verdict` never returns a falsy value (it returns the string `"ok"` even for an ASN with zero lines).
- **Fix:** Use the model's badge map for the class and an explicit label chain, the way the risk badge does at backorder/detail.html:18: `<span class="badge {{ obj.discrepancy_css }}">{% if obj.discrepancy_verdict == 'ok' %}Declared matches outstanding{% elif obj.discrepancy_verdict == 'short' %}Short vs outstanding{% elif obj.discrepancy_verdict == 'over' %}Over-shipped{% else %}Mixed over/short{% endif %}</span>`, and wrap the whole span in `{% if obj.line_count %}...{% endif %}` so a line-less draft does not claim it matches.
- **Status:** [x] fixed — fix(procurement): render the ASN discrepancy badge as prose off the model css map and hide it on a line-less draft

### M7 — `templates/procurement/orderfulfillment/asn/detail.html:9`

- **Found by:** explorer
- **Problem:** The header badge prints the raw enum token — `Declared vs outstanding: {{ obj.discrepancy_verdict|default:"—" }}` renders literally "ok" / "short" / "over" / "mixed" to the user, and the `|default:"—"` is dead because the property always returns at least "ok".
- **Fix:** Render a human label, e.g. `{% if obj.discrepancy_verdict == 'ok' %}Matches outstanding{% elif obj.discrepancy_verdict == 'short' %}Short-shipped{% elif obj.discrepancy_verdict == 'over' %}Over-shipped{% else %}Mixed variance{% endif %}` and drop the `|default` filter.
- **Status:** [x] fixed — fix(procurement): render the ASN discrepancy badge as prose off the model css map and hide it on a line-less draft (same change as M6)

### M8 — `templates/procurement/orderfulfillment/asn/list.html:101`

- **Found by:** security-reviewer
- **Lesson:** L27
- **Problem:** The ASN register renders the Delete button for every draft row to any logged-in workspace member, but `asn_delete` is `@tenant_admin_required`, so a non-admin who clicks it gets a raw 403 PermissionDenied page instead of a working action.
- **Fix:** Add the admin gate that the sibling backorder register already has (backorder/list.html:119). Change line 101 from `{% if obj.status == 'draft' %}` to include the admin test:

```django
{% if obj.status == 'draft' and request.user.is_superuser or obj.status == 'draft' and request.user.is_tenant_admin %}
```

or, clearer and matching the sibling exactly, nest the two conditions:

```django
{% if obj.status == 'draft' %}
  {% if request.user.is_superuser or request.user.is_tenant_admin %}
    <form method="post" action="{% url 'procurement:asn_delete' obj.pk %}" onsubmit="return confirm('Delete draft ASN {{ obj.number }} and its declared lines?');">
      {% csrf_token %}<button class="btn-icon danger" type="submit" title="Delete" aria-label="Delete"><i data-lucide="trash-2"></i></button>
    </form>
  {% endif %}
{% endif %}
```

The view stays as-is — this only stops offering a button that is already correctly refused server-side. Family sweep (L28): the admin-gated delete views in this app are `asn_delete backorder_delete clause_delete delegation_delete routingrule_delete vis_delete vpa_delete vsu_delete`; run `rg -l "procurement:(asn|backorder|clause|delegation|routingrule|vis|vpa|vsu)_delete" templates/procurement` and check each hit for `is_tenant_admin|can_delete` — `orderfulfillment/asn/list.html` is the only in-scope miss.
- **Status:** [x] fixed — fix(procurement): gate the ASN register delete button on tenant-admin as well as draft status (same change as I7/I8/M9)

### M9 — `templates/procurement/orderfulfillment/asn/list.html:101`

- **Found by:** frontend-reviewer
- **Problem:** The row Delete button is gated only on `obj.status == 'draft'`, while the detail page hides it from non-admins via `can_delete = is_admin and obj.status == 'draft'` (views/OrderFulfillment/AdvancedShipmentNotice.py:130) and the sibling backorder register gates on the user at backorder/list.html:119 — so a non-admin sees a Delete action on the list that the detail page denies.
- **Fix:** Nest the existing user gate inside the status gate (Django's `and` binds tighter than `or`, so use two tags rather than one mixed expression): change line 101 to `{% if obj.status == 'draft' %}{% if request.user.is_superuser or request.user.is_tenant_admin %}` and add the matching second `{% endif %}` after line 104's `</form>`.
- **Status:** [x] fixed — fix(procurement): gate the ASN register delete button on tenant-admin as well as draft status (same change as I7/I8/M8)

### M10 — `templates/procurement/orderfulfillment/backorder/list.html:100`

- **Found by:** frontend-reviewer
- **Lesson:** L33
- **Problem:** The hand-rolled reason badge chain has already diverged from the model's own `Backorder.reason_css` map: `material_shortage` renders `badge-amber` here but `badge-red` in `apps/procurement/models/OrderFulfillment/Backorder.py:335`, so the same reason is two different colours depending on which surface reads it.
- **Fix:** Replace the whole `{% if obj.reason == ... %}` chain with the model helper: `<span class="badge {{ obj.reason_css }}">{{ obj.get_reason_display }}</span>`. Apply the identical replacement to the duplicated chain at `templates/procurement/orderfulfillment/backorder/detail.html:37`.
- **Status:** [x] fixed — fix(procurement): render the backorder register reason badge from Backorder.reason_css + the same on the detail page

### M11 — `templates/procurement/orderfulfillment/backorder/list.html:100`

- **Found by:** explorer
- **Problem:** The reason badge re-implements the colour map inline and already disagrees with the model's own `Backorder.reason_css` (apps/procurement/models/OrderFulfillment/Backorder.py:333) — the template renders `material_shortage` as `badge-amber` while the model says `badge-red`, so the same row is a different colour depending on which layer renders it.
- **Fix:** Replace the inline `{% if obj.reason == … %}` chain on line 100 with `<span class="badge {{ obj.reason_css }}">{{ obj.get_reason_display }}</span>`, and do the same at templates/procurement/orderfulfillment/backorder/detail.html:37, so the model's presentation helper is the single source of truth.
- **Status:** [x] fixed — fix(procurement): render the backorder detail reason badge from Backorder.reason_css (same change as M10)

### M12 — `templates/procurement/orderfulfillment/delivery_confirmation.html:84`

- **Found by:** frontend-reviewer
- **Problem:** `{{ row.expected_delivery_date }}` renders with Django's default DATE_FORMAT ("Aug. 29, 2026") while every other date in the sub-module uses `|date:"M d, Y"`, so the arrivals queue formats dates differently from the ASN register and detail pages it links to.
- **Fix:** Add the filter: `{{ row.expected_delivery_date|date:"M d, Y" }}` on line 84, and the matching `{{ row.delivered_at|date:"M d, Y H:i" }}` on line 94 (the POD timestamp, which asn/detail.html:58 already renders with that exact format).
- **Status:** [x] fixed — style(procurement): format the arrivals-board expected date and POD timestamp like the rest of the sub-module

### M13 — `templates/procurement/orderfulfillment/deliveryschedule/detail.html:42`

- **Found by:** code-reviewer
- **Problem:** The "{{ obj.slip_days }} day(s) earlier" branch is unreachable dead code: it is nested inside `{% if obj.has_slip %}`, and `DeliverySchedule.has_slip` is defined as `slip_days > 0`, so a supplier who promises EARLIER than the need-by date renders as "—" even though the model docstring says the negative case is meaningful.
- **Fix:** Gate on the value instead of the flag: replace `{% if obj.has_slip %}` with `{% if obj.promised_date %}` on this row so the `{% if obj.slip_days > 0 %}…{% else %}…earlier…{% endif %}` split can actually fire; the same dead `{% else %}` sits at templates/procurement/orderfulfillment/deliveryschedule/list.html:104.
- **Status:** [~] skipped — superseded by M14: gating on `obj.promised_date` would render a promise made EXACTLY on the need-by date as "0 day(s) earlier". The reachable-and-correct guard is non-zero `slip_days`, which M14 asks for and which is what landed.

### M14 — `templates/procurement/orderfulfillment/deliveryschedule/detail.html:42`

- **Found by:** explorer
- **Lesson:** L39
- **Problem:** The slip cell is wrapped in `{% if obj.has_slip %}` and then branches on `{% if obj.slip_days > 0 %}` … `{% else %}<span class="badge badge-info">{{ obj.slip_days }} day(s) earlier</span>`; since `has_slip` is defined as `slip_days > 0` (apps/procurement/models/OrderFulfillment/DeliverySchedule.py:195) the "earlier" branch is unreachable, so a supplier promising EARLIER than the need-by date renders a bare "—".
- **Fix:** Change the outer guard on line 42 from `{% if obj.has_slip %}` to `{% if obj.slip_days %}` (non-zero) so the negative branch can render; apply the identical change to the sibling block at templates/procurement/orderfulfillment/deliveryschedule/list.html:101.
- **Status:** [x] fixed — fix(procurement): make the early-promise slip branch reachable on the delivery-schedule detail page + the same on the register (detail also drops the minus sign via widthratio so it no longer reads "-2 day(s) earlier")

### M15 — `templates/procurement/orderfulfillment/deliveryschedule/list.html:54`

- **Found by:** frontend-reviewer
- **Lesson:** L33
- **Problem:** `.form-check` is defined in static/css/theme.css:318 as a checkbox-INPUT style (`width: 1rem; height: 1rem; accent-color: var(--brand-600); vertical-align: middle`) but is applied to the wrapping `<label>`; width/height are ignored on an inline `<label>`, so the checkbox on line 55 never receives the design-system sizing the class exists to give it.
- **Fix:** Move the class onto the control and label the wrapper: line 54 becomes `<label class="form-label" for="filter-late" style="margin:0;">` and line 55 becomes `<input type="checkbox" class="form-check" id="filter-late" name="late" value="1" {% if request.GET.late == '1' %}checked{% endif %}>` (this is the shape asn/list.html:61-63 already uses for the same filter).
- **Status:** [x] fixed — style(procurement): move .form-check onto the late-only checkbox where theme.css can size it

### M16 — `templates/procurement/orderfulfillment/deliveryschedule/split.html:71`

- **Found by:** frontend-reviewer
- **Lesson:** L13
- **Problem:** `class="text-muted small"` — `small` exists in neither static/css/theme.css nor Tailwind, so it is a dead no-op class (the sibling `text-center` on line 86 is fine, it is a real Tailwind utility).
- **Fix:** Drop the invented token: `<div class="text-muted">{{ line.sku_hint }}</div>`, or use Tailwind's `text-xs` if a smaller size is actually wanted.
- **Status:** [x] fixed — style(procurement): drop the invented small class from the split console sku hint

### M17 — `templates/procurement/orderfulfillment/inbound_tracking.html:61`

- **Found by:** frontend-reviewer
- **Problem:** A second `<label for="tracking_late">Past expected date only</label>` points at the same input already labelled on line 60, so the checkbox's accessible name concatenates to "Overdue Past expected date only" for screen-reader users.
- **Fix:** Keep one label. Change line 60 to a non-labelling caption — `<span class="form-label">Overdue</span>` — and leave the inline `<label for="tracking_late">Past expected date only</label>` on line 61 as the control's single label.
- **Status:** [x] fixed — a11y(procurement): one label per overdue checkbox on the tracking board (caption span + form-check on the control)

## Notes — app-wide / pre-existing (NOT in the fix queue)

- **code-reviewer:** Multi-tenancy is clean across the whole slice: all three new models carry a `tenant` FK via `TenantNumbered`, `AsnLine` is correctly tenant-less and reached only through its tenant-verified parent, every list/detail/verb queryset filters `tenant=request.tenant`, and every FK dropdown that `TenantModelForm` cannot auto-scope (`po_line`, whose target `scm.PurchaseOrderLine` has no tenant column) is narrowed through `purchase_order__tenant` AND re-checked in `clean()`. Package structure, `__init__.py` re-exports (models/forms/views/urls, all four layers), URL literal-before-`<int:pk>` ordering, template paths, `{% url %}` names, `stringformat:\"d\"` FK filter comparisons, badge palette (all colour-named, all with `{% else %}` fallbacks), pagination guards and the `partials/pagination.html` include all check out. The migration matches the models field-for-field.\n\nOut-of-scope observations:\n- The working tree is dirty with a concurrent 6.10 session's files (`apps/procurement/{models,forms,views,urls}/PurchaseOrderManagement/`, migration 0015, `templates/procurement/purchaseordermanagement/`). Left untouched per L45; only the committed 72b7680...HEAD range was reviewed.\n- `seed_procurement._seed_order_fulfillment` comments that \"`_seed_po_management` has already guaranteed [a receivable PO] exists\" — that method does not exist at HEAD (it is the 6.10 seeder block); at HEAD the receivable PO comes from `seed_scm`, and the code correctly warns-and-skips when there is none. Comment-only inaccuracy.\n- Operational consequence of this diff, shared with the existing 6.10 shape: `AdvancedShipmentNotice.purchase_order`, `AsnLine.po_line`, `DeliverySchedule.po_line` and `Backorder.po_line` are all `on_delete=PROTECT` into `scm.*`, so `seed_scm --flush` will now fail while 6.11 rows exist. Consistent with `PurchaseOrderChange`, so not a new pattern — but worth knowing before the next SCM re-seed.\n- Performance (routed, not counted as findings here): `AsnLine.outstanding_at_declare` fires one `received_quantity()` aggregate per line on the ASN detail page, and `AsnLine.clean()` dereferences `self.asn` once per formset row on edit.
- **security-reviewer:** SCOPE NOTE — the untracked `apps/procurement/{models,forms,views,urls}/PurchaseOrderManagement/`, `templates/procurement/purchaseordermanagement/`, migration `0015_...` and `.claude/tasks/research-procurement-6.10.md` in `git status` are a CONCURRENT session's 6.10 build (L45), not part of the 72b7680...HEAD range. I did not review or touch them.

WHAT I VERIFIED CLEAN IN THIS CHANGESET (no finding raised):
- IDOR: every one of the 14 pk lookups across `AdvancedShipmentNotice.py`, `Backorder.py`, `DeliverySchedule.py` passes `tenant=request.tenant` to `get_object_or_404`; every list/aggregate/stat queryset is `.filter(tenant=request.tenant)`; `crud_edit`/`crud_delete` re-fetch tenant-scoped internally. `obj.line_rows()` and `siblings` scope through an already-verified parent, which is safe.
- Forms as a tenant surface: `TenantModelForm` only auto-scopes ModelChoiceFields when `tenant is not None` (apps/core/forms/_common.py:51), so a tenant-less caller would otherwise get an UNSCOPED dropdown. All three 6.11 ModelForms defend against that explicitly — `BackorderForm` and `DeliveryScheduleForm` with `else: ...objects.none()` branches, `AdvancedShipmentNoticeForm` because `filter(tenant=None)` on a non-nullable FK is empty. `scm.PurchaseOrderLine` (no tenant column) is narrowed via `purchase_order__tenant` in all four places it renders.
- Mass assignment: `tenant`, `number`, `created_by`, `created_at`/`updated_at` are excluded from all three ModelForms; `AdvancedShipmentNotice.status` + the whole POD block (`delivered_at`, `arrival_condition`, `pod_reference`, `received_signature_name`, `confirmed_by`) and `Backorder.status`/`reschedule_count`/`closed_at`/`closure_note`/`alert` are `editable=False` on the model AND absent from `Meta.fields`. `DeliverySchedule.status` IS on the form, but that ladder stamps no timestamp and no actor off its status, so there is nothing a crafted POST can forge.
- AuthZ: all 26 new views carry `@login_required`; the 9 mutating verbs are `@require_POST`; `asn_delete` and `backorder_delete` add `@tenant_admin_required`. Every status guard is enforced in the view AND re-checked inside the model verb under `select_for_update()`, so a double-submitted delivery confirmation cannot re-stamp the POD block.
- CSRF: all 19 POST `<form>` elements in `templates/procurement/orderfulfillment/` contain `{% csrf_token %}`, including the hand-built inline confirm form on the delivery-confirmation board and the hand-built cancel-note form on the backorder detail page. No HTMX POSTs and no `@csrf_exempt` in the range.
- XSS / CSS injection: zero `|safe`, `mark_safe`, `{% autoescape off %}` in the range. The only interpolations into inline `style=` are `{{ coverage_pct }}` / `{{ obj.coverage_pct }}`, which are ints clamped to 0-100 by `_coverage()` and `DeliverySchedule.coverage_pct` — not user strings (L26 does not bite). The only interpolations into `onclick`/`onsubmit` confirm strings are system-assigned `ASN-`/`BKO-`/`DSC-` numbers, never user-typed text (L42 respected, and both templates say so).
- Open redirect: `asn_confirm_delivery` reads `request.POST["next"]` but compares it against the single literal `"confirmation"` and maps to a hardcoded url name — a user-supplied URL is never passed to `redirect()`.
- No SQL: no `.raw()`, `.extra()` or `cursor.execute` anywhere in the range. No file uploads, no secrets, no payment data, no public/token endpoints introduced by 6.11, so those checklist sections have no surface here.
- `apps/core/navigation.py` 6.11 entries all point at staff, `@login_required`, tenant-scoped pages — no L32 portal-page-in-staff-sidebar violation.

PRE-EXISTING, OUT OF SCOPE (do NOT queue for this fixer): `templates/procurement/contractsmanagement/clauses/list.html` and `.../clauses/detail.html` both offer `procurement:clause_delete` with zero `is_tenant_admin`/`can_delete` guard, while `clause_delete` is `@tenant_admin_required` — the same shape as finding 1 but shipped in an earlier sub-module. Worth a separate follow-up commit rather than folding into the 6.11 fix pass.
- **performance-reviewer:** Verified clean in this lane, no action needed: every list applies its non-crud_list filter (`?late=1`, `?risk=`, the confirmation bucket `Q()`) to the QUERYSET before `crud_list`'s `Paginator`, so page counts never lie; all four stat-card blocks (`_asn_stats`, `inbound_tracking` totals, `delivery_confirmation` totals, `backorder_list` stats, `deliveryschedule_list` stats) are single `.aggregate(Count(..., filter=Q(...)))` calls rather than one `.count()` per card; `?due=zzz` and `?risk=zzz` sanitize to a default instead of 500ing; the seeder writes ~8 rows per tenant through `TenantNumbered.save()` (numbering forbids `bulk_create`, so per-row saves are correct there); no template calls `.count`/`.all`/`.exists` inside a `{% for %}`; `deliveryschedule_detail`'s `{{ siblings|length }}` reuses the queryset the loop iterates immediately after, which is the cheaper form. `asn_edit`'s `obj.lines.count()` for the audit payload is a real SQL COUNT, not `len()`.

APP-WIDE (not a 6.11 fork, do not fix here): no model under apps/procurement/models/ carries a `(tenant, created_at)` index, yet 16 of them — including the two new `TenantNumbered` models in this range — declare `ordering = [\"-created_at\", \"-id\"]`, which is the default sort of every unfiltered register page. CRM already ships this index (`crm_lead_tenant_created_idx`, `crm_case_tenant_created_idx`, …). This wants one app-wide procurement index migration, not a per-sub-module addition. The three ASN, two DeliverySchedule and three Backorder indexes that 6.11 DID add all back filters the pages actually issue and all landed in migration 0016.

PRE-EXISTING / OUT OF LANE: (a) `asn_list` combines `annotate(line_total=Count(\"lines\"))` with five `select_related` joins, forcing a GROUP BY over every selected column of six tables before the LIMIT; a `Subquery`-based count like the DS lane's `_scheduled_total_subquery` would avoid the group-by entirely, but this matches the existing procurement register style and the correctness/ordering handling around it is right. (b) The `po_line` ModelChoiceFields on `BackorderForm`, `DeliveryScheduleForm` and `DeliveryScheduleSplitForm` are unbounded over every PO line in the workspace — a render-size concern, not a query-count one (`PurchaseOrderLine.__str__` resolves no FK), and the same unbounded shape exists across the app. (c) `AdvancedShipmentNoticeAdmin.list_display` includes `purchase_order`, which Django auto-covers with a depth-1 `select_related()`; the `__str__` hop to `vendor` at depth 2 is uncovered, but the admin changelist is a cold staff-only path.

The working tree also contains an in-progress 6.10 build (apps/procurement/*/PurchaseOrderManagement/, migration 0015, templates/procurement/purchaseordermanagement/) from a concurrent session — outside the reviewed range and untouched.
- **frontend-reviewer:** Scope and structure checks that came back clean, for the record:

- Template folder shape is correct throughout. `asn/`, `backorder/`, `deliveryschedule/` each carry `{list,detail,form}.html`; `deliveryschedule/split.html` is a secondary entity action correctly placed inside the entity folder (rule 5); `delivery_confirmation.html` and `inbound_tracking.html` are standalone board pages at the sub-module root (rule 6). No banned flat `<entity>_<page>.html` file anywhere in the changeset.
- L2: grepped every changed template for `{#`. The only occurrence is `deliveryschedule/split.html:35`, inside a `{% comment %}` block and on a single line — it is the note explaining the L2 rule, not a leak.
- L33: `grep -oE '\.(badge-[a-z]+|stat-icon(\.[a-z]+)?|text-[a-z]+)' static/css/theme.css` confirms the available set; every modifier used in the changeset is in it. Note `.stat-icon.red` and `.text-danger/.text-red/.text-ok/.text-warn` have since been added to theme.css, so `stat-icon red` (asn/list.html:18, backorder/list.html:24, delivery_confirmation.html:29) and `text-warn` (deliveryschedule/list.html:113) are all valid.
- All 28 distinct `{% url %}` names in these templates resolve (27 under `apps/procurement/urls/`, plus `scm:purchaseorder_detail` at apps/scm/urls/ProcurementManagement/PurchaseOrders.py:11).
- All context keys referenced by the templates are supplied: every `stats.*` key, `*_choices`, `carriers`, `purchase_orders`, `po_lines`, `siblings`, `coverage_pct`/`remaining_quantity`/`scheduled_total`/`is_under_covered`, all `can_*` booleans, and all four forms. `q` comes from `crud_list` (apps/core/crud.py:105).
- CRUD completeness: all three registers have a GET filter form with `name="q"` + status/FK selects reflecting `request.GET`, an Actions column (eye / pencil / trash-2), CSRF-bearing POST delete with a confirm, and an `.empty-state` `{% empty %}` branch with a correct `colspan` (verified against the `<th>` count on all seven tables). All three detail pages have Edit / POST-Delete / Back-to-List.
- Filters use `|stringformat:"d"` for every pk comparison (asn/list.html:48,56; backorder/list.html:63; deliveryschedule/list.html:49; inbound_tracking.html:55) — no `|slugify` anywhere.
- Nullable-FK display is guarded correctly in the filter-argument position (L10): `{% if obj.confirmed_by %}{{ obj.confirmed_by.get_full_name|default:obj.confirmed_by.username }}{% else %}—{% endif %}` at asn/detail.html:63, backorder/detail.html:169 and delivery_confirmation.html:100. The unguarded `obj.po_line.uom_hint` lookups (backorder/list.html:98, backorder/detail.html:36) are bare lookups on a non-nullable FK, so they cannot 500.
- Responsive/dark/RTL: every table is inside `.table-wrap`; there are no raw Tailwind colour utilities needing `dark:` variants; the inline styles are only `flex`, `min-width`, `gap`, `width` and symmetric margins — nothing hard-codes left/right.
- No HTMX, no inline secrets, and no changed static include in this changeset, so items 12's CSRF-header / `lucide.createIcons()` / `?v=` cache-buster checks do not apply.

Out of scope but observed: the working tree is dirty with a concurrent 6.10 PurchaseOrderManagement build (`templates/procurement/purchaseordermanagement/` and friends). I did not review or touch any of it. Separately, `apps/procurement/views/OrderFulfillment/AdvancedShipmentNotice.py:216` documents `asn_delete` as "Admin-gated" but the function body only checks the draft status before delegating to `crud_delete` — that is a Python-side question for the security/code reviewers, not a template finding, and it is the reason finding #4 above is framed as a UI inconsistency rather than an exposure.
- **explorer:** Scope/ownership: the working tree still carries the concurrent 6.10 session's uncommitted files (`apps/procurement/{models,forms,views,urls}/PurchaseOrderManagement/`, migration 0015, `templates/procurement/purchaseordermanagement/`, plus the M-marked shared files). The 6.11 commits touched the shared `__init__.py`/`admin.py`/`navigation.py`/seeder surgically (additive hunks only) and did not clobber 6.10's lines — verified via `git diff BASE...HEAD` on each shared file.

Pre-existing / app-wide, NOT actionable here: (1) `.text-center` and `.small` are used in `deliveryschedule/split.html:71,86` but are defined nowhere in `static/css/theme.css`; `text-center` already appears in 4 templates repo-wide, so this is an existing L13-family gap rather than a 6.11 regression. (2) The `stat-icon red` modifier used on three 6.11 boards DOES exist (theme.css:265), so it is not an L33 violation despite `red` being absent from the palette list in the build brief. (3) The 6.11 url docstrings assert \"the app has no greedy `<str:…>` route\" — `contract-sign/<str:token>/` does exist (ContractsManagement/Contracts.py:16), but it sits under a literal first segment so the no-shadowing conclusion still holds.

Tests: `apps/procurement/tests/` has suites for portal/awe/eauction/contracts/catalogmgmt but no `test_orderfulfillment_*` / `test_fulfillment_*` module yet — expected, Phase 6 has not run.
- **qa-smoke-tester:** Pre-existing / out-of-scope observations, not for the fix queue:

1. The working tree is NOT clean: `apps/procurement/{admin,forms/__init__,models/__init__,urls/__init__,views/__init__}.py`, `apps/core/navigation.py`, `seed_procurement.py` are modified and `migrations/0015_*`, `models|forms|urls|views/PurchaseOrderManagement/`, `templates/procurement/purchaseordermanagement/` are untracked — that is the concurrent 6.10 session (L45). 6.11's migration 0016 depends on 0015, so 6.11 cannot be migrated in a checkout that lacks the 6.10 session's uncommitted migration. Nothing to do here, but the fixer must not stage those files.

2. `manage.py seed_procurement` prints `SMOKETEST Acme: PO-00001 has no lines - skipping order fulfillment.` — the guard behaves correctly and warns; that leftover tenant is from an earlier session, not this build.

3. Two 6.11 UI states have no demo row, same root cause as the finding (fixing it fixes both): the ASN discrepancy verdict never renders `short` or `mixed` (both seeded ASNs fold to `over`), and the delivery-schedule detail page's amber "Under-covered" warning never appears (the seeded ladder is exactly 100% of the ordered quantity, so only "Fully laid out" is reachable).

4. No ASN in the seed links a `scm.Shipment`, so the inbound-tracking board's TMS branch is dark on seeded data. I exercised it manually (linked SHP-00002 + a Carrier in a rolled-back transaction) and `tracking_status_text` / `eta_display` / `location_display` / `shipment.number` all rendered correctly on both the board and the ASN detail page — the code is fine, only the demo is thin. Optional seeder polish, not a defect.

5. `temp/` holds several hundred leftover scripts and logs from previous sessions (L46). I added and removed only my own; the rest were left untouched.

6. `manage.py migrate` emits `mysql.W002` (MariaDB strict mode off) and the seeders emit `RuntimeWarning: naive datetime` for `PurchaseRequisition.created_at` — both app-wide and pre-existing, unrelated to 6.11.

### Notes added by the code-fixer pass (2026-08-29)

- **Cross-session (I3/I4, open):** migration `0016` still depends on `0015_purchaseorderchange_purchaseorderchangeline_and_more`, which is UNTRACKED and belongs to the concurrent 6.10 build. Nothing was re-pointed: `0015` exists on disk here, so pointing `0016` at `0014` would create two leaf nodes and break `migrate` for both sessions immediately. **This range must not be pushed until the 6.10 session commits `0015`.**
- **Shared file, partial commit (I2):** `apps/procurement/management/commands/seed_procurement.py` carries the 6.10 session's uncommitted `_seed_po_management` block plus one earlier uncommitted 6.11 tweak (`expected_delivery_date=today` on the in-flight ASN) that is not this pass's work. Only the two `_seed_order_fulfillment` hunks were staged (`git apply --cached` of an extracted patch) and committed; the rest of the file is left dirty and untouched. The committed blob was compile-checked on its own.
- **App-wide, do NOT fork here (M2 family, L18):** other hand-rolled save paths in this app still write an action label instead of a field diff — `apps/procurement/views/RfxManagement/Responses.py:116` logs no `changes` at all. Recommend one app-wide pass moving them onto `apps.core.crud._changed(form)`; only the 6.11 instance (`asn_edit`) was changed.
- **Pre-existing, out of scope (M8 family):** `templates/procurement/contractsmanagement/clauses/list.html` and `.../clauses/detail.html` offer `procurement:clause_delete` with no `is_tenant_admin` guard while the view is `@tenant_admin_required` — exactly the shape fixed here for the ASN register. Worth its own follow-up commit against 6.7.
- **Seeder demo data:** the I2 fix was verified inside a rolled-back transaction rather than with `seed_procurement --flush`, because the concurrent 6.10 session is using the same database. To see the new short-shipped ASN in the demo data, someone must re-seed (the block is guarded on `AdvancedShipmentNotice.objects.filter(tenant=...).exists()`, so an idempotent re-run will NOT rewrite the existing rows — a `--flush` is required, and it will also clear 6.10's rows).

## Done well

- **code-reviewer:** Every ASN and Backorder state transition is a model verb that re-checks its own guard *inside* the method and returns a bool, and every calling view wraps it in `transaction.atomic()` + `select_for_update()` (e.g. `asn_confirm_delivery` at apps/procurement/views/OrderFulfillment/AdvancedShipmentNotice.py:279-292) — a double-submitted confirmation genuinely cannot re-stamp `delivered_at`, the POD block or `confirmed_by`, and the view reports it with `messages.info` instead of pretending it worked. The Backorder risk buckets are equally disciplined: `_risk_conditions()` expresses them as ORM `Q()` date arithmetic applied to the queryset *before* `crud_list` paginates, with `Backorder.risk_bucket` mirroring the same clauses in Python, so the stat cards, the `?risk=` filter, the page counts and the per-row badge cannot disagree.
- **security-reviewer:** Every tenant-scoped FK dropdown in this sub-module is narrowed in `__init__` AND re-checked on POST in two independent layers — the form's `_reject_foreign(...)` / explicit `po_line.purchase_order.tenant_id` comparison, and again in the model's own `clean()` — so a crafted POST carrying another workspace's `po_line`, `asn`, `delivery_schedule`, `ship_to`, `carrier` or `shipment` pk lands as a field error instead of a saved cross-tenant row. `scm.PurchaseOrderLine` (which has no `tenant` column and is therefore invisible to `TenantModelForm`'s automatic scoping) is handled explicitly everywhere it appears, including the `?po_line=&asn=&quantity=` deep-link prefill in `_create_initial`, which re-validates every pk against `request.tenant` before using it and guards the hand-parsed `Decimal` with `is_finite()` (L35).
- **performance-reviewer:** The Split Delivery lane got derived coverage right end to end: `_scheduled_total_subquery()` (apps/procurement/views/OrderFulfillment/DeliverySchedule.py:40) annotates `sched_total_annot` as one correlated Subquery, and `DeliverySchedule.line_scheduled_total` (models/OrderFulfillment/DeliverySchedule.py:216) prefers that annotation over its own aggregate — so a 15-row list renders `coverage_pct` / `is_under_covered` / `remaining_quantity` with zero extra queries, and the same helper is reused with `OuterRef(\"pk\")` for the split console's PO-line board. Nothing is stored; there is no editable balance column anywhere in 6.11.
- **frontend-reviewer:** Badge/CHOICES fidelity is genuinely clean: all 14 hand-rolled badge chains across the six entity templates use the exact model CHOICES values (`in_transit`, `no_commitment`, `material_shortage`, …), every modifier is a real colour-named theme.css class (`badge-green/red/amber/info/muted/slate`, `stat-icon blue/orange/red/green/purple/slate` — all verified present in `static/css/theme.css`), each chain ends in a `{% else %}badge-muted{% endif %}` fallback with a `{{ obj.get_FIELD_display }}` label, and the two board templates go one better by reading the model's own `{{ row.status_css|default:'badge-slate' }}` map. Zero L33 regressions, zero L2 comment leaks (the single `{#` in the changeset sits inside a `{% comment %}` block at `deliveryschedule/split.html:35` and is deliberately documenting the L2 rule), and all five paginated pages use the L9-safe `templates/partials/pagination.html` which guards `has_previous`/`has_next` and preserves every non-`page` GET param.
- **explorer:** The context-variable contract is airtight end-to-end: every root template variable across all 12 new pages (the `can_*` action gates on both detail pages, `bucket`/`bucket_choices`/`condition_choices` on the confirmation board, and the `siblings`/`scheduled_total`/`remaining_quantity`/`coverage_pct`/`is_under_covered` set on the schedule detail) is actually passed by its view; all 28 `{% url %}` names resolve to registered routes; every `render()`/`crud_list()` template path exists on disk (including the split console the split view renders); and all four package `__init__.py` re-export blocks (models 5 names, forms 10, views 26, urls sub-package) carry the complete 6.11 surface, with the `LIVE_LINKS[\"6.11\"]` keys matching the five NavERP.md 6.11 bullet strings character-for-character.
- **qa-smoke-tester:** Every non-column filter is applied to the QUERYSET before `crud_list` paginates (`?late=1` on asn_list/deliveryschedule_list/inbound_tracking, the `?risk=` ORM date-arithmetic buckets on backorder_list, the `?due=` bucket predicates on delivery_confirmation) and every int FK filter goes through `as_db_int`, with the `?due=` tab sanitized against a whitelist. Result: `?category=abc`, `?carrier=abc`, `?po=999999999999999999999`, `?risk=zzz`, `?due=zzz`, `?page=-1`, `?page=abc` and `?quantity=nan|Infinity` all render 200, and with 20 extra rows injected per entity every list served a genuine page 2/3/999 at 200 with filters preserved — no L9/L11-class failure anywhere in the sub-module.
