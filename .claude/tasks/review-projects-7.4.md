# Review — Sub-module 7.4 Cost & Budget Management (Module 7, app `projects`)

> Six reviewer passes run ONE AFTER ANOTHER against the 7.4 changeset (22 code files + 1 migration;
> scope pinned per L53 — never a commit range, peers' 7.2/7.3 files excluded). Ground truth:
> `.claude/tasks/contract-projects-7.4.md`. The five pinned deviations (contract §13) are not
> re-reported. The Phase-3 smoke harness (297 checks) already proves the pages; these passes add
> what a green smoke cannot see.

---

## Lane 1 — code-reviewer (2026-09-10)

[Critical] apps/projects/views/CostManagement/CostControlAccounts.py:78-82 — cca_delete raises an uncaught ProtectedError (500) on any control account referenced by a ProjectExpense: PEX.control_account is on_delete=PROTECT (contract §6, correct) but crud_delete (apps/core/crud.py:224-232) has no guard, and the Delete button is rendered unconditionally on every CA row/detail (templates/projects/cost/costcontrolaccount/list.html:59, detail.html:100) — every seeded CA has expenses, so the button is a guaranteed 500. Fix with the established house idiom (apps/core/views/Party.py:64-75, apps/accounting/views/GeneralLedger/Currencies.py:71): wrap the crud_delete call in try/except ProtectedError inside transaction.atomic(), messages.error listing the blockers, redirect to cca_detail.

[Important] apps/projects/views/CostManagement/BudgetRevisions.py:81-82 — the category-totals aggregation runs lines.values("category").annotate(total=Sum("amount")) WITHOUT clearing ordering, so Meta.ordering ("-created_at","-id") is emitted as ORDER BY created_at DESC, id DESC against a GROUP BY category aggregate — a latent Error-1055 500 on stock MySQL (ONLY_FULL_GROUP_BY is default there; XAMPP MariaDB happens to tolerate it). The repo's own precedent clears ordering for exactly this reason (apps/scm/views/AssetManagement/Reports.py:324 uses jobs.order_by().values(...).annotate(...)). Fix: insert .order_by() before .values("category").

[Important] apps/projects/views/CostManagement/BudgetRevisions.py:215-216 — bvr_activate's audit changes hard-code {"verb": "activate", "from": "approved", "to": "active_baseline"}: "to" is not a STATUS_CHOICES value and "from" is not captured from obj.status, both deviating from the pinned §9 shape {"verb", "from": previous, "to": obj.status} (contract note 10 pins 7.4 verbs to the prq_* idiom) — ironic given the module docstring (line 17-19) says a hard-coded "from" asserts the gate in exactly the cases where it was not. The per-row supersede audits (208-212) DO follow the idiom. Fix: capture previous = obj.status before the atomic block and write "to": previous (status does not change on activation).

[Minor] apps/projects/{models,forms,views,urls}/CostManagement/ — all four CostManagement/ sub-packages are MISSING their empty __init__.py; all 12 sibling 7.1/7.2/7.3 sub-packages have one (0 bytes) and the plan says "sub-package __init__.py files stay EMPTY" (i.e. present). Imports work via namespace-package semantics, but this is the house-layout deviation. Fix: add four empty __init__.py files.

[Minor] apps/projects/models/CostManagement/CostControlAccounts.py:134-135 — dead code: the `if end == start: return Decimal("1")` branch is unreachable (line 130 returns 0 when today <= start, line 132 returns 1 when today >= end, and end == start satisfies one of the two). No ZeroDivision risk exists at line 136 since that path requires end > start. Fix: delete the two lines.

[Minor] apps/projects/admin.py:175-177 — ProjectBudgetLineAdmin's comment claims "wbs_node is selected for the changelist" but list_select_related omits "wbs_node" (contract §11.2 pins ("tenant","budget_revision","project","wbs_node","control_account")). No runtime effect (wbs_node is not a list_display column), but the comment contradicts the code. Fix: add "wbs_node" to the tuple or correct the comment.

[Minor] templates/projects/cost/budgetrevision/list.html:50 — superseded falls through to the generic <span class="badge"> fallback; contract §10 pins superseded→badge-info (the class exists in static/css/theme.css:289 and is used repo-wide). Fix: add an explicit {% elif obj.status == 'superseded' %}badge-info branch before the {% else %}.

[Minor] apps/projects/views/CostManagement/CostControlAccounts.py:16-28 + templates/projects/cost/costcontrolaccount/list.html:52-54 — register N+1: rendering obj.bac / obj.cpi / obj.health per row re-queries active_revision + 2-3 aggregates per row (~4-5 queries × 15 rows ≈ 60-75 queries/page). The contract pins cpi+health per row (bac is an extra column), so this matches spec — but a per-page prefetch (one active revision + two grouped Sum annotations) would collapse it. Leave for the performance pass to weigh.

[Minor] apps/projects/management/commands/seed_projects.py:685-691,697-699 — chartered revision 0 has 6 lines and draft revision 0 has 3, below the plan's "7–10 PBL lines across all categories" per seeded project (only the active project's 10 lines hit the range, covering 6 of 7 categories — "other" is never used). The 19-line total still clears the page-2 requirement (19 > 15). Fix if desired: pad the chartered/draft line sets.

[Minor] apps/projects/views/CostManagement/ProjectExpenses.py:36 — _initial_currency falls back to the GLOBAL lowest-pk Currency (Currency.objects.order_by("pk").first()), while contract §7 words it "the tenant's first Currency". Currency is global with no tenant column (L29), so the as-built is the only implementable reading and the docstring says so — flagged as a contract erratum to record, not a code change.

### Lane 1 clean bills
All 4 model files otherwise field-by-field per §3–§6; EVM properties correctly None-guarded; all 4 form files exact per §7; all 4 url files exact; shared 7.4 blocks (4/5/26/4 re-exports, admin, seeder incl. hand-recomputed CPI bands and +50,000 delta, LIVE_LINKS, Overview keys, overview.html); migration 0005 fully consistent, no peer tables swept in; remaining 11 templates clean (csrf+confirm everywhere, nullable-FK guards, stringformat:d, badge fallbacks, pagination, empty states).

**Lane 1 count: 1 Critical / 2 Important / 7 Minor**
