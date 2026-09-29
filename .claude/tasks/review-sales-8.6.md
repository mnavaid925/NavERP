# Review — Sub-module 8.6: Order Management

> Phase 4 output. `BASE = 020dd439434fc98ceffc71fe84dc5906a9968952` … `HEAD`. 57 files, ~14.1k insertions.
> Six reviewers run **one at a time**, read-only (QA is report-only). Findings are appended here
> after each agent reports, then deduped and sorted Critical → Important → Minor with IDs.
> The build already fixed one `save()` bug before this phase began (see §Pre-Phase fixes).

## Pre-Phase fixes (found and fixed during the build, before review opened)

- `OrderAmendments.py` — the `impact_snapshot` `save()` guard was missing its
  `super().save(...)`, so **no `OrderAmendment` would ever persist**. Fixed in `36bc0a29`.
- `OrderBoards.py:_top_items` — walked `sales_order_line__sales_order_id` from `SalesOrderLine`,
  a path that only exists from `SalesOrderAllocation`; it raised `FieldError` and **500'd the
  reorder board on every render**. Caught by the Phase 3.5 content smoke, fixed in `b338d8e0`.
- Contract corrections made in flight: the unreachable `close` change type was removed (4.5 closes
  only an `invoiced` order, which is not amendable); the `decision_note` column the plan specified
  was restored; `order_hold_raise` was moved to `orders/raise/<int:order_id>/`.

---

## 1. `code-reviewer` (read-only, first pass)

**Verified clean by this pass:** `manage.py check` · `makemigrations --check` "No changes detected"
· all 49 url names reverse to distinct patterns · no file under `apps/scm/` modified · no
`class SalesOrder` anywhere in `apps/sales` · no `JournalEntry` written. **The L36/L37 ruling is
honoured without exception** — `apply()` delegates to 4.5's own `recalc_totals()` /
`recompute_allocation_status()`, cancellation delegates to 4.5's logic, and the boards write
nothing on an order row. The `save()` contract, `update_fields` correctness (all 14 sites),
`select_for_update` scoping, the single-writer rule, L11 junk-param handling, URL shadowing, L29,
L33 and L42 were each checked and are clean.

### CRITICAL

- **C1 — `recompute()` raises `TypeError` on any schedule mixing dated and undated obligations.**
  `RevenueSchedules.py:395` sorts by `(r.recognize_on or UNSCHEDULED, …)` where
  `UNSCHEDULED = (1, 1, 1)` is a **tuple** while `recognize_on` is a `date`. One dated + one
  undated obligation ⇒ `tuple < date` ⇒ crash. `recognize_on` is `null=True` and the form invites
  a blank ("Leave blank only if the performance has no date yet"), so this is a **normal path**,
  and it kills the only verb in 8.6 that moves money. The seeder masks it by dating both rows.
  **Fix:** `UNSCHEDULED = date.max` — a real `date`, and strictly better than the `date.min` the
  code's own comment (lines 83–84) identifies, because `date.min` would sort undated obligations
  *first* and let them consume the shared recognition budget ahead of dated ones.

- **C2 — `OrderHold.clean()` keys a message on `evaluation_snapshot`, which is off the form —
  the exact 0.20 `ValueError` trap.** `OrderHolds.py:291-292`; `OrderHoldForm.Meta.fields` is
  `["sales_order","rule","party","hold_type","reason","clear_note"]` and `evaluation_snapshot` is
  `editable=False`. Django routes the key through `add_error(None, …)` → `ValueError` → **500 on
  both create and edit**, and it is *data-dependent* (fires only for a malformed stored blob), so
  the same form saves for one hold and 500s for another. The sibling `OrderAmendment` already
  normalises the equivalent field in `save()` and documents why it must not be validated in
  `clean()`. **Fix:** delete the `clean()` guard; add an `OrderHold.save()` normalising
  `self.evaluation_snapshot = {}` when it is not a dict, mirroring `OrderAmendments.py:532-539`.

- **C3 — an APPROVED amendment's lines and reason stay editable, and every edit re-freezes the
  impact snapshot the approver signed.** `OrderAmendments.py:141` and the edit view. The approval
  is a decision about a *frozen impact read-out*; letting the document change under it means the
  approval and the applied change are not the same thing.

