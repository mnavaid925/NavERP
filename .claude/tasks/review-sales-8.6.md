

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

---

## Pre-Phase fixes (found and fixed during the build, before review opened)

---

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

---

## Phase 6 — Tests (all four lanes, one at a time)

| Lane | Tests | Carries |
|---|---|---|
| `test_ordermanagement_models.py` | 35 | **C1, C2, C3 named regressions**, the derived-not-stored register, `evaluate()` purity, SET_NULL evidence, tenant isolation, FK `on_delete` policy |
| `test_ordermanagement_forms.py` | 18 | the 0.20 `ValueError` trap, driven through **real form instances** (never `full_clean()` in isolation); exact `Meta.fields`; frozen-evidence leakage; tenant-scoped FK querysets |
| `test_ordermanagement_views.py` | 23 | all 49 URL names reverse; L8 content assertions; context keys; POST-only on all 23 mutating verbs; the C3 edit lock at the HTTP layer |
| `test_ordermanagement_security.py` | 15 | cross-tenant **404** on every surface, the wrong-parent child case, board/list leak checks, login floor, enforced CSRF |

**91 tests, all green.** Every C1/C2/C3 test is named after the bug it prevents rather than the
feature it covers, so a future regression points straight at the review finding it reopens.

### The full unfiltered Sales suite — the L47 gate

`pytest apps/sales/tests/` → **1,024 tests, 1,023 passed, 1 skipped, 0 failed, 0 errors.**
Unfiltered on purpose: a `-k` filter excludes exactly the tests a shared-file change can break, and
this changeset *did* change two shared files. The progress output carries **zero `F` and zero `E`**
characters across all fourteen progress lines.

### Phase 6 found two defects no reviewer could have

1. **I destroyed the shared conftest and committed it.** While adding 8.6's fixtures I truncated
   `apps/sales/tests/conftest.py` from **2,707 lines to 343**, deleting `LEADMANAGEMENT_MODEL_FIELDS`,
   `SALESFORECASTING_CHOICES`, `leadmanagement_tenant_a` and every 8.1–8.5 factory — and committed
   that. Nothing caught it because **I had only ever run my own lane**, which imported cleanly from
   my rewritten copy: precisely the trap L47 warns about. The diffstat
   (`275 insertions(+), 2639 deletions(-)`) said so in plain text and I read past it. Restored from
   `HEAD~1`, 8.6's section moved strictly below a marker comment, and the 8.4/8.5 lanes re-run green
   to prove it. **L59.**
2. **I did it again, one file over.** Removing a duplicated close-out block from `todo.md` by line
   range took it from **13,727 lines to 1,102** — 12,680 deletions of other modules' plans — and
   committed that too. Restored from `HEAD~1` and re-applied at the top only.

Both were invisible to the reviewers because a reviewer reads a *diff*, and a diff that deletes
someone else's fixtures reads as a deliberate refactor. Only running the neighbours finds them.
Two instances of the same failure in one session is what turned L59 from an anecdote into a rule:
**never edit a large shared file by line range, and read the diffstat before moving on.**

### Gates re-run after the test work

| Gate | Result |
|---|---|
| Full unfiltered `apps/sales/tests/` | **1,023 passed, 1 skipped, 0 failed** |
| `manage.py check` | clean |
| `makemigrations sales --check` | "No changes detected" |
| Content smoke (`temp/smoke_86.py`) | **73 checks, 0 failures** |
| 8.4 / 8.5 lanes (neighbour regression proof) | green |

---
