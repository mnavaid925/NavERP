# Review Record — Sub-module 8.13: Marketing Alignment & Attribution

**Module**: Module 8 — Sales Management System (`apps/sales/`)
**Sub-module**: 8.13 Marketing Alignment & Attribution
**Review window**: `386a2b27a38fb2589f69ddb287976cc2302ea332` (BASE) → `HEAD`
**Changeset**: 48 new files + 10 edited shared files, ~9.3k insertions
**Contract under review**: `.claude/tasks/contract-sales-8.13.md`
**Plan**: `.claude/tasks/todo.md` · **Research**: `.claude/tasks/research-sales-8.13.md`
**Gap register**: `.agents/tasks/gaps-sales-8.13.md`

> ### ⚠️ Review scope is BY PATH, not by commit range
>
> A **concurrent session** is working in this same checkout on the same `main` branch (it is
> building 8.12 and writing the 8.10/8.11 test files). Three of its commits
> (`c7871819`, `04884feb`, `ab5a19a8`) landed inside the `386a2b2...HEAD` range, so the raw
> commit range is **not** a valid review scope — it contains another session's work.
>
> **Review ONLY these paths:**
>
> | Path | What is in scope |
> |---|---|
> | `apps/sales/models/MarketingAlignment/` | 5 entity files, 6 model classes |
> | `apps/sales/forms/MarketingAlignment/` | 5 form modules |
> | `apps/sales/views/MarketingAlignment/` | 5 entity view modules + the console view |
> | `apps/sales/urls/MarketingAlignment/` | 6 url modules |
> | `apps/sales/models/__init__.py` | the 8.13 re-export block only |
> | `apps/sales/forms/__init__.py` | the 8.13 re-export block only |
> | `apps/sales/views/__init__.py` | the 8.13 re-export block only |
> | `apps/sales/urls/__init__.py` | the 8.13 mount only |
> | `apps/sales/admin.py` | the 8.13 admin registrations only |
> | `apps/sales/management/commands/seed_sales.py` | `_seed_marketing_alignment` + the 8.13 call/imports/output only |
> | `apps/sales/migrations/0023_attributiontouchpoint_campaignattribution_and_more.py` | the whole file |
> | `apps/core/navigation.py` | the `LIVE_LINKS["8.13"]` entry only |
> | `templates/sales/marketingalignment/` | all 18 templates |
>
> **Out of scope — do not review, do not comment on, do not fix:** anything under
> `apps/sales/tests/` (owned by the concurrent session), and the 8.10 / 8.11 / 8.12 work.
> A finding that is really about another session's file is not a finding against 8.13.

---

## Review sequence (CLAUDE.md Phase 4 — six reviewers, ONE AT A TIME)

Each reviewer is read-only: it never edits code and never commits. Findings are appended below as
each one reports. When all six have reported, the file is deduped, sorted
**Critical → Important → Minor**, and each finding is given an ID (`C1`, `I3`, `M7`).

| # | Reviewer | Scope | Status | Findings |
|---|---|---|---|---|
| 0 | `qa-smoke-tester` (Phase 3 gate) | rendered pages, filters, pagination, IDOR, content | **done** | 4 (I1, I2, M1, M2) — all fixed in the main session |
| 1 | `code-reviewer` | correctness, contract drift, Django idioms | pending | — |
| 2 | `explorer` | code/structure mapping, duplication, dead paths | pending | — |
| 3 | `frontend-reviewer` | templates, design system, filters, accessibility | pending | — |
| 4 | `performance-reviewer` | queries, N+1, indexes, aggregation | pending | — |
| 5 | `qa-smoke-tester` | rendered pages, filters, pagination, IDOR | pending | — |
| 6 | `security-reviewer` | tenant isolation, IDOR, injection, data exposure | pending | — |

---

## Phase 3 smoke gate — `qa-smoke-tester` pass (2026-10-19)

The Phase 3 gate ran an independent read-only verification against the contract (23 URLs, content
assertions, leak markers, junk params, page 2, cross-tenant IDOR, FK-select scoping,
cross-tenant POST rejection, the console model selector, and `check` / migration drift).

**Result: all 9 functional checks PASSED** — every page renders 200 with the right content, no
`{#` / `{% comment` leak markers, no 500 on hostile query strings, page 2 renders and preserves
active filters, 12/12 cross-tenant URLs return **404**, 19 FK selects across the 6 create forms
offer **0** foreign-tenant pks, a cross-tenant FK POST creates **0** rows, and the console rollup
genuinely changes with the model (`first_touch` $19,800 / `last_touch` $13,200 / `linear` $13,000
on the leading campaign).

**The gate FAILED on contract conformance** with 4 findings. All 4 are fixed below.

### Findings

| ID | Severity | Finding | Status |
|---|---|---|---|
| `I1` | Important | **Touchpoint list had no `lead` filter control.** The view delivered the contract-pinned `leads` context key and honoured `?lead=<pk>` server-side, but the template never rendered a `<select name="lead">` — so the journey-identity dimension was unreachable from the UI. The template's own clear-filters guard and pagination links already referenced `active_filters.lead`, proving it was a dropped control, not a scope decision. | **[x] fixed** |
| `I2` | Important | **Content-engagement list had no `campaign` filter control.** Same shape as I1: the view delivered the contract-pinned `campaigns` context key and honoured `?campaign=<pk>`, but no `<select name="campaign">` was rendered — "which campaign drove this engagement" had no UI path, and the clear-filters guard and pagination links already referenced `active_filters.campaign`. | **[x] fixed** |
| `M1` | Minor | **Touchpoint detail view omitted the contract-pinned `attributions` context key.** Contract §4.2 pins `{"obj", "touchpoint", "attributions"}`; the view passed only `{"obj", "touchpoint"}`. The template did not consume the key either — it showed only the aggregate model property `obj.attributed_revenue`, so the per-model credit breakdown was invisible. No blank region, contract drift only. | **[x] fixed** |
| `M2` | Minor | **Contract named the migration `0022_marketingalignment`; the applied file is `0023_attributiontouchpoint_campaignattribution_and_more.py`** (0022 was taken by `0022_customersuccess_indexes`). Documentation drift only — `makemigrations --check` was clean and `showmigrations` reported every sales migration `[X]`. | **[x] fixed** |

### Fixes applied (main session — Phase 3 drift, not Phase 4 review findings)

- **I1** — `templates/sales/marketingalignment/attributiontouchpoint/list.html`: added the
  `lead` select (options from the `leads` context key, `|stringformat:"d"` pk comparison, and
  `active_filters.lead` reflected as `selected`); filter grid re-laid out to `lg:grid-cols-4`
  for the now-seven controls.
- **I2** — `templates/sales/marketingalignment/contentengagement/list.html`: added the
  `campaign` select on the same pattern; filter grid re-laid out to `lg:grid-cols-4`.
- **M1** — `apps/sales/views/MarketingAlignment/AttributionTouchpoints.py`: the detail view now
  passes `attributions` (the touch's credit rows under every model, `select_related("computed_by")`).
  `templates/sales/marketingalignment/attributiontouchpoint/detail.html` gained a **"Credit by
  Attribution Model"** table that consumes it, so the key is live rather than decorative.
- **M2** — `.claude/tasks/contract-sales-8.13.md`: the migration reference corrected to
  `0023_attributiontouchpoint_campaignattribution_and_more.py`, with the reason recorded.

### Environment note (not a 8.13 defect)

A **concurrent session** is building sub-module **8.12** in this same checkout on the same
`main` branch. It owns `apps/sales/tests/conftest.py` and
`apps/sales/tests/test_customersuccess_models.py`, and it landed three commits inside the
`386a2b2...HEAD` range. 8.13 never touched `apps/sales/tests/` — which is also why Phase 6's
test-writing phase was skipped rather than contended (see `GAP-sales-8.13-09`).

---

## Findings

(findings appended here as each reviewer reports)

