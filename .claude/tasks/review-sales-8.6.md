## Summary — 3 findings, all fixed, all the same species

| ID | Severity | Finding | Status |
|---|---|---|---|
| C1 | CRITICAL | `recompute()` raised `TypeError` on any schedule mixing dated and undated obligations (a tuple sentinel where a `date` was required) | `[x] fixed` — `0eab5695` |
| C2 | CRITICAL | `OrderHold.clean()` keyed a message on `evaluation_snapshot`, which is off the form → `ValueError` 500 on create *and* edit (the 0.20 trap) | `[x] fixed` — `c43351fb` |
| C3 | CRITICAL | An APPROVED amendment stayed editable, re-freezing the impact snapshot the approver had signed | `[x] fixed` — `fcfd6385`, `b3676891` |
| F1 | Minor | Contract §6 heading said "24 files"; the enumerated list totals 23 and 23 ship | `[x] fixed` — contract corrected |
| — | PRE-EXISTING | `seed_sales` not idempotent across a whole multi-tenant DB (8.3-era `create_enrichment_event`) | `[~] skipped — separate one-file fix, out of 8.6 scope` |
| — | PRE-EXISTING | `apps/sales/models/_base.py` `TenantNumbered` exhaustion path (contract §12) | `[~] skipped — out of scope by contract` |

**The pattern worth keeping.** C1, C2 and C3 are one defect wearing three hats: **a guard the
prose promised and the code did not deliver.** The docstrings state the invariants correctly and
in detail — `recompute()`'s own docstring explains that undated obligations are allocated but
never recognised, which is precisely the state its sentinel could not sort;
`OrderAmendments.py` documents *why* its snapshot must not be validated in `clean()`, and its
sibling did exactly that anyway. A guard written in a comment rather than in a branch is not a
guard. The Phase 6 tests exist to make each of these a failure that cannot come back silently.

---

# Review — Sub-module 8.6: Order Management

> Phase 4 output. `BASE = 020dd439434fc98ceffc71fe84dc5906a9968952` … `HEAD`. 57 files, ~14.1k insertions.
> Six reviewers run **one at a time**, read-only (QA is report-only). Findings are appended here
> after each agent reports, then deduped and sorted Critical → Important → Minor with IDs.
> The build already fixed one `save()` bug before this phase began (see §Pre-Phase fixes).

## Pre-Phase fixes (found and fixed during the build, before review opened)
---

## 2. `explorer` (read-only, second pass) — contract drift

Ran a mechanical drift check (`temp/explorer_86.py`, throwaway) that introspects the live
Django registry rather than reading prose, then compared it field-by-field against the
**amended** contract. **Result: zero drift.** Nothing to fix.

**Verified clean:**

| Check | Result |
|---|---|
| NUMBER_PREFIX collision (§1) | `OVR`, `OHD`, `AMD`, `RVS` each claimed by exactly one class, one repo-wide use, no collision |
| 6 model field lists, `on_delete`, `related_name`, `max_length` (§2) | all match, including both in-flight contract amendments (`close` absent from `CHANGE_TYPE_CHOICES`; `decision_note` present and editable) |
| `editable=False` frozen/system fields | every action stamp, both snapshots, `journal_entry` and both money columns are non-editable |
| CHOICES lists, all 11 | exact values and order |
| Indexes / named constraints / ordering | 8 indexes + 4 named `*_tenant_number_uniq`, correct ordering tuples |
| `AMENDABLE_STATUSES` / `EDITABLE_STATUSES` / `OPEN_STATUSES` / `BLOCKING_SEVERITIES` | all present with the contracted values (incl. the C3 `EDITABLE_STATUSES` fix) |
| 8 form `Meta.fields` (§3) | all match **exactly** |
| Frozen-evidence leakage into any form | **none** — `evaluation_snapshot`, `impact_snapshot`, `decision_note`, `allocated_amount`, `recognized_amount`, `journal_entry`, `tenant`, `number` and the timestamps are absent from every form |
| 49 routes (§5) | all present, exact names and paths, literals before `<int:pk>` in every module, `orders/raise/<int:order_id>/` as amended |

One **harness** defect was found and fixed in the throwaway script, not the product: a
`hasattr(cls, "SEVERITY_CHOICES")` guard sat above a misspelled `cls.SEVITY_CHOICES` access, so
the guard passed and the access then raised. Worth recording as a pattern — **a `hasattr` guard
and the access it guards must be checked together, or the guard proves nothing.** The check was
rewritten to build each attribute name by concatenation so the two cannot drift apart.

**Re-confirmed by this pass:** `check` clean · `makemigrations --check` "No changes detected" ·
no file under `apps/scm/` modified · no `class SalesOrder` in `apps/sales` · no `JournalEntry`
instantiated anywhere.
---

## 3. `frontend-reviewer` · 4. `performance-reviewer` · 5. `security-reviewer` (read-only)

**Frontend — verified clean, with one false positive struck.** All 23 templates exist at the
contracted paths. Badge classes are within the six legal ones; every `badge-success` grep hit is
a **comment warning against using it** (`"badge-success/warning/danger do NOT … render
unstyled"`), not a usage. List templates carry the Actions column with 6 POST forms, 6 CSRF
tokens and 9 `confirm(...)` calls. FK dropdowns use `|stringformat:"d"`. Detail pages have
Actions sidebars. No leaked `{#` / `{% comment` markers (L2/L3) — asserted across all 10
paginated pages by the content smoke.

**F1 — contract §6's heading said "24 files"; the build ships 23 and the enumerated list totals
23.** The count in the heading was wrong, the list was always right, and every file on it exists.
**Contract corrected** — do not read the gap as a missing template.

**Performance — verified clean, no N+1.** Query capture forced on, measured per page:

| Page | Queries | ms |
|---|---|---|
| `revenue_recognition_board` | 24 | 292 |
| `revenue_schedule_list` | 21 | 289 |
| `order_fulfillment_board` | 18 | 345 |
| `order_capture_board` | 14 | 295 |
| `order_hold_list` | 13 | 287 |
| `order_validation_rule_list` | 12 | 299 |
| `order_history_board` | 12 | 264 |
| `order_amendment_list` / `…open_queue` | 11 | 254 / 296 |
---

## 6. `qa-smoke-tester` (read-only; the ONLY pass that touches the DB, report-only override)

Content smoke (`temp/smoke_86.py`, throwaway) — **73 checks, 0 failures.** It asserts rendered
CONTENT, not just status, which is the L8 point: a context key a template reads but the view does
not pass returns 200 and renders blank.

| Gate | Result |
|---|---|
| 10 list/board pages render 200 **with asserted content** | PASS |
| 7 detail pages show the object's own number | PASS |
| 4 create forms render a real CSRF-protected `<form>` | PASS |
| ASC 606 read-out present on the schedule detail | PASS |
| junk GET params on 5 lists → 200, never 500 (L11) | PASS |
| page 2 of 3 paginated lists | PASS |
| no leaked `{#` / `{% comment` (L2/L3) across 10 pages | PASS |
| **cross-tenant IDOR → 404 on 4 detail surfaces** | PASS |
| 49 url names reverse, 0 duplicate patterns | PASS |
| `manage.py check` | clean |
| `makemigrations sales --check` | "No changes detected" |
| `seed_sales` × 3 → identical counts (OVR 3, OHD 1, AMD 1, line 1, RVS 1, POB 2) | PASS |
| 23 mutating verbs refuse GET with 405 | PASS |

Two harness defects were found and fixed **in the throwaway scripts, not the product**, and are
recorded because both are the kind that silently produces a false PASS: (1) the `hasattr` guard
that tested a different string than the access it guarded (§2 above); (2) `ALLOWED_HOSTS` does
not include `testserver`, so every request 400'd until the harness overrode it — read naively
that is 28 "failing" pages, and the temptation is to blame the app.

### A pre-existing defect found in passing — filed NOT as an 8.6 regression

`seed_sales` aborts partway through a multi-tenant database with
`ValidationError: ["That idempotency key was already used for different enrichment evidence."]`
raised from `apps/sales/services.py:774` (`create_enrichment_event`), reached from
`_seed_contact_account_management`. It fires on a **later tenant whose enrichment row was
written with different evidence text**, so `seed_sales` is idempotent per tenant but not across
a whole database. This is 8.3-era code, pre-dates this changeset, and reproduces with no 8.6
file involved. **8.6's own seeder block is byte-stable and is not the cause.** Filed for a
separate one-file fix; widening this changeset to repair it would be the wrong call.

---

## Pre-Phase fixes (found and fixed during the build, before review opened)
| `reorder_customers_board` | 11 | 230 |
| `renewals_due_board` | 9 | 277 |

Every page is 9–24 queries and flat regardless of row count, because each board aggregates in one
grouped query and the per-line loops operate on an already-fetched list. The two heaviest
(`revenue_recognition_board`, `revenue_schedule_list`) derive a `stats` dict in Python by
design — the SQLite integer-division trap forbids pushing that into `aggregate()` — and are
still well inside budget. `select_related` is used on all five view modules (3–16 call sites).
No unbounded loop issues per-row queries; the one loop flagged by pattern
(`OrderBoards.py:506`, over already-fetched `rows`) is a false positive.

**Security — verified clean.** All **23 mutating verbs refuse GET with 405 Method Not Allowed**;
none mutated on GET and none 500'd. Greps for `eval(`, `.raw(`, `raw_sql`, `password`,
`api_key`, `secret` across the three 8.6 packages: **all clean**. Frozen evidence is
server-generated and off every form; the hold checkout is exclusive; cross-tenant IDOR returns
404 on all four detail surfaces (asserted in the content smoke).

> **Probe artefact, struck, not a finding:** six verbs reported "cannot reverse" —
> `order_hold_bulk_raise` / `…bulk_clear` (no `pk`), and the four child line/obligation verbs
> (need `line_pk` / `obligation_pk`). Those are my probe passing the wrong kwargs, not app
> defects: the routes exist and, per the 405 log, correctly reject GET. Recorded because a
> reverse failure and a real routing bug look identical in a report.

---

## Pre-Phase fixes (found and fixed during the build, before review opened)

---

## 1. `code-reviewer` (read-only, first pass)

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

