"""NavERP 8.6 Order Management — the Sales-side layer over SCM 4.5's sales order.

**OWNERSHIP (L36/L37) — the one thing to read before changing anything in this package.**
`scm.SalesOrder` / `scm.SalesOrderLine` / `scm.SalesOrderAllocation` are OWNED by SCM 4.5 and
live in `apps/scm/models/OrderManagement/`. That module states the ruling in its own header and
records that *"there is deliberately NO amendment flow here — amend/cancel with impact analysis
is Module 8.6's job."*

**This package is that job, built as an EXTENSION.** Every model here reaches the order through
an FK and none of them declares a second order master. A `class SalesOrder` in `apps/sales` would
be a bug, not a variant — the parallel-schema failure L29/L37 exist to prevent. `NavERP-ERD.md`
row 8 (Module 8, "Sales") still reads as though Sales owns the order; that row was stale and this
sub-module is what reconciles it, alongside the `LIVE_LINKS["8.6"]` comment in
`apps/core/navigation.py` and the note appended to L37 in `.claude/tasks/lessons.md`.

What 8.6 adds is the *commercial* layer SCM deliberately declined:

* `OrderValidationRule` — the typed rule set that replaces 4.5's two hard-coded hold checks.
* `OrderHold` — the auditable, checkout-able hold with a frozen `evaluation_snapshot`. 8.6 writes
  back ONLY `SalesOrder.credit_hold` / `hold_reason`; 4.5's `salesorder_release_hold` stays the
  release verb and `salesorder_submit` stays the only submitter.
* `OrderAmendment` + `OrderAmendmentLine` — change orders, line modifications and cancellations
  with impact analysis frozen at propose time. `apply()` is the ONLY writer of
  `SalesOrderLine.quantity_ordered` / `unit_price`, and it calls 4.5's own `recalc_totals()` and
  `recompute_allocation_status()` rather than re-deriving them.
* `RevenueSchedule` + `PerformanceObligation` — the repo's only ASC 606 / IFRS 15 representation.
  **Every money balance is a derived `@property`; the only stored money columns are the two
  `editable=False` fields on the obligation, written solely by `recompute()`.** 8.6 posts NO
  `JournalEntry` (L29) — `journal_entry` is a reference-only FK.

Two rules run through all of it: **frozen evidence is never authorable** (`evaluation_snapshot`,
`impact_snapshot` and `decision_note` are all off every form, L22), and **all money arithmetic is
done in Python over a fetched set**, never with an `F()` expression — the SQLite integer-division
trap silently drops fractional cents rather than raising.
"""
from .OrderAmendments import OrderAmendment, OrderAmendmentLine
from .OrderHolds import OrderHold
from .OrderValidationRules import OrderValidationRule
from .RevenueSchedules import PerformanceObligation, RevenueSchedule

__all__ = [
    "OrderValidationRule",
    "OrderHold",
    "OrderAmendment",
    "OrderAmendmentLine",
    "RevenueSchedule",
    "PerformanceObligation",
]
