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
| 1 | `code-reviewer` | correctness, contract drift, Django idioms | pending | — |
| 2 | `explorer` | code/structure mapping, duplication, dead paths | pending | — |
| 3 | `frontend-reviewer` | templates, design system, filters, accessibility | pending | — |
| 4 | `performance-reviewer` | queries, N+1, indexes, aggregation | pending | — |
| 5 | `qa-smoke-tester` | rendered pages, filters, pagination, IDOR | pending | — |
| 6 | `security-reviewer` | tenant isolation, IDOR, injection, data exposure | pending | — |

---

## Findings

(findings appended here as each reviewer reports)

