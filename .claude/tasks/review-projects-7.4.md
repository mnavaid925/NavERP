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

---

## Lane 2 — explorer (2026-09-10)

### Findings

- **[Minor] apps/projects/{models,forms,views,urls}/CostManagement/ — the four sub-package `__init__.py` files do not exist.** The plan says "sub-package `__init__.py` files stay EMPTY" and 7.3's sibling `ResourceManagement/` ships four 0-byte ones; 7.1/7.2 also omit them, so the tree is now 2-keep / 1-have / 1-missing. Imports work either way (namespace packages; the compiled .pyc files prove it). Suggested resolution: add four empty `__init__.py` files for tree-shape consistency, or record the omission as the accepted convention.

- **[Minor] apps/projects/management/commands/seed_projects.py `_cost` — the plan's "7–10 lines across all categories" is not literally met.** The active project's revision 0 carries 10 lines across 6 of 7 categories (`other` never appears; chartered has 6 lines/5 categories, draft 3). The plan's actual goals — page 2 (19 PBL rows per tenant > 15), category variety, three CPI health bands, pending revision with positive delta — are all met, and the deviation is documented in the seeder docstring, not silent. Suggested resolution: none required; optionally add one `other`-category line if a later verify pass wants every category exercised.

- **[Minor] contract-projects-7.4.md §6 vs as-built — `source_kind` max_length.** Contract pins `max_length=15`; as-built is 16 (fixed in-commit by 5027e436 — `supplier_invoice` is 16 chars, so 16 is correct). Field-level drift is lane 1's, but the contract doc itself needs the one-word correction; flagging so the fixer updates the contract text rather than the code.

- **[Minor] apps/projects/admin.py — `ProjectBudgetLineAdmin.list_select_related` omits `wbs_node`** which the contract's pinned tuple includes. The in-code comment explains it (wbs_node is not a rendered changelist column, so the join is dead weight) — as-built is better and "as-built wins", recorded here only for traceability. Related cosmetic note: admin.py has a `# --- 7.2` section header but no `# --- 7.4` header above the four registrations (they correctly follow 7.3's block).

### Clean-bill notes per checked area

1. **Plan ↔ as-built completeness — clean.** All 4 models in the planned dependency order (BVR→CCA→PBL→PEX), 16 backend files (same filename in all four layers), 12 templates under `templates/projects/cost/<entity>/{list,detail,form}.html` with lowercase-singular folders, migration `0005` (exactly 4 `CreateModel`s — the predicted leaf), and every Integrate item landed: 4 re-export blocks, 4 admin registrations, seeder `_cost` with its own guard + children-first flush order (PEX→PBL→CCA→BVR before ScheduleBaseline, seed_projects.py:199-202), `LIVE_LINKS["7.4"]`, Overview `pending_revisions`/`posted_spend` (one aggregate per table), overview.html stat-cards + 4 rows. All 5 pinned deviations realized in code (decision_notes added + form-excluded; CCA status 3 values; `pex_edit`/`pex_delete` refuse via `is_locked`; `entry_date` non-nullable + `source_kind` default manual; health cut-points 0.95/1.00/available<0). The deferred list (todo.md L6396–6404) is carried verbatim and echoed in docstrings (no EVMPeriod, no rate fields, no source_change_request, no FX conversion) — nothing silently dropped.
2. **Structure conventions — clean apart from the Minor above.** Re-export blocks: models 4 / forms 5 (DecisionForm tuple-imported) / views 26 (9+5+5+7) / urls 4 imports + concat, all appended after the 7.3 blocks; url first-segments `budgetlines/`, `revisions/`, `controlaccounts/`, `expenses/` are disjoint from 7.1/7.2/7.3's, literal routes precede `<int:pk>/`, `app_name` set once.
3. **Boundary rulings 1–6 — all hold.** R1: no rate/hours anywhere in 7.4 (only negating docstrings) and 7.3's `ResourceManagement/` models carry hours but zero money columns. R2: no `CostBaseline`/`BSL` model; baseline = approved+activated revision (`active_revision` property, `bvr_activate` supersedes-all inside `transaction.atomic()`). R3: no `ChangeRequest` class in `apps/projects`. R4: EVM lives on `CostControlAccount` as properties; zero commits under `apps/procurement/` in the window — 6.15's `CostForecast` untouched. R5: `source_number` is `CharField(max_length=30, blank=True)`, no FK. R6: `gl_account` is PROTECT null-blank in all three models that carry it; no `JournalEntry` writes anywhere in 7.4.
4. **Sibling-seam safety — clean.** Each shared file was touched by exactly one 7.4 commit; the four `__init__.py` commits, admin.py and navigation.py are purely additive (`git show` confirms zero deleted lines); seeder edits only extended the command `help` string and the flush comment; overview.html's only modification is the intro copy sentence (extended to mention the cost layer); Overview.py's only modification is the django import line (`Count, Q` → `Count, DecimalField, Q, Sum, Value`). All 7.1/7.2/7.3 blocks byte-identical, no reordering. The 40-commit 7.4 footprint contains no sibling file beyond the sanctioned seam set.
5. **Docs coherence — no contradiction, but stale.** `.claude/skills/projects/SKILL.md` still says "**As-built: 7.1 only**" with migrations `0001–0002`, "32 route names", "1243 tests" — pre-existing staleness (7.2/7.3 also undocumented); its Phase-7 update must correct these along with adding the 7.4 section. Nothing 7.4 built contradicts a stated skill rule: colour-named badges only, `accounting.Currency` global/unscoped, audit action ≤10 with `{"verb","from","to"}`, no nullable FK inside `|default:`, no annotate-over-property name collisions on CCA registers.

**Lane 2 count: 0 Critical / 0 Important / 4 Minor**

> Erratum: the lane-2 commit (11954871) is mislabeled "docs(projects): 7.2 explorer lane" — its
> content is the 7.4 explorer lane. Left unamended with live peers (L51); `git log --follow` on
> this file tells the truth.

---

## Lane 3 — frontend-reviewer (2026-09-10)

**Method.** Read all 12 templates + the overview 7.4 blocks against the 7.1/7.2 reference anatomy, theme.css, the shared paginator, the 4 views/urls (ground-truth context), the 4 models and forms, and the CLAUDE.md house rules. Render-verified every page with the Django test client (throwaway script under temp/, now deleted) as both admin_acme (tenant admin) and ops_acme (member). Zero unrendered template variables, zero 500s, zero missing url names on any of the 22 URLs exercised.

### Findings

- **[Important]** `templates/projects/cost/{budgetrevision/detail.html:76,85,94 · costcontrolaccount/list.html:43,51-53 · costcontrolaccount/detail.html:36-50,60,67,81,88 · projectbudgetline/list.html:19,22,28,78,88 · projectexpense/list.html:59,69}` — the alignment class `ta-right` used on every amount/numeric column is **not defined in theme.css** (the only stylesheet; `.text-right` at line 408 is the class the rest of the app uses). All BAC/CPI/amount columns in the 7.4 registers render left-aligned, failing the "amounts aligned right" house convention. Suggested fix: replace `ta-right` with the defined `text-right` (or add `.ta-right` to theme.css).
- **[Important]** `templates/projects/cost/budgetrevision/detail.html:67` — `<p class="stat-value">{{ obj.amount_delta }}</p>` sits in a plain `.card-body`, but theme.css only defines `.stat-card .stat-value` (line 266), so the approver's headline number (verified rendering `50000.00` on BVR-00002) renders as ordinary body text with no emphasis. Suggested fix: add a standalone `.stat-value` rule, or wrap the delta in the stat-card markup.
- **[Minor]** `templates/projects/cost/budgetrevision/list.html:53` and `detail.html:54` — the green "Baseline" badge keys off `activated_at` alone, but `bvr_activate` deliberately keeps superseded rows' `activated_at` as history (BudgetRevisions.py view docstring), so a superseded revision still shows the current-baseline badge. Suggested fix: gate on `{% if obj.activated_at and obj.status == 'approved' %}`, else a muted date.
- **[Minor]** `templates/projects/cost/budgetrevision/detail.html:26-32` — the reject form (label + textarea + button) lives inside `.page-actions` (flex, no wrap, theme.css line 248); the textarea renders ~20ch wide beside the Approve button and the header row can overflow on narrow screens. The 7.1 precedent (`projectrequest/detail.html:138-146`) places the textarea inside the card body. Suggested fix: move the reject form into the Revision card like prq.
- **[Minor]** `templates/projects/cost/projectexpense/list.html` — the view passes `source_kind_choices` (views/CostManagement/ProjectExpenses.py:55) but the template has no Source-kind filter select; the passed context is dead. Suggested fix: add the `source_kind` dropdown (one `filters` tuple + one select) or drop the context key.
- **[Minor]** `templates/projects/cost/projectbudgetline/list.html:15-32` — the "Totals in the current filter" card precedes the filter bar in DOM order, so the totals the user is meant to re-scope sit above controls they haven't seen; every other 7.x list leads with its filter bar. Suggested fix: move the totals card after the filter (or below the register table).
- **[Minor]** `templates/projects/cost/budgetrevision/list.html:50`, `detail.html:49` and `costcontrolaccount/list.html:50`, `detail.html:22` — `superseded` (BVR) and `closed` (CCA) fall into the bare `{% else %}` `.badge` with no colour; `badge-muted` exists in theme.css and would read better. House rule (else + `get_<field>_display`) is satisfied, so cosmetic only.
- **[Minor]** `templates/projects/cost/projectbudgetline/list.html:23-25` — the totals table's `{% empty %}` row is dead code: `_pbl_totals` always returns a dict keyed by every `CATEGORY_CHOICES` entry (zeros included — rendered "Other 0.00"), so "No budget lines in the current filter" can never show. Harmless; drop the branch or skip zero rows.

### Per-page clean bills
budgetrevision/list.html PASS; budgetrevision/detail.html PASS with findings 2-4 (state machine verified live); budgetrevision/form.html PASS (status/decision_notes verifiably absent); costcontrolaccount/list.html PASS with findings 1,7; costcontrolaccount/detail.html PASS with finding 1 (all 15 EVM rows match the model math); costcontrolaccount/form.html PASS; projectbudgetline/list.html PASS with findings 1,6,8 (totals track the filter); projectbudgetline/detail.html PASS; projectbudgetline/form.html PASS; projectexpense/list.html PASS with findings 1,5 (actions match status rules exactly; member sees 0 void buttons); projectexpense/detail.html PASS; projectexpense/form.html PASS; overview.html 7.4 blocks PASS.

**Lane 3 count: 0 Critical / 2 Important / 6 Minor**

---

## Lane 4 — performance-reviewer (2026-09-10)

**Method.** Live seeded MariaDB, django.test.Client + CaptureQueriesContext, warmed render, two stable passes; throwaway scripts deleted; EXPLAIN on migration 0005's shipped predicates.

### Findings

**[Critical] apps/projects/models/CostManagement/CostControlAccounts.py:86-167 (surfaces at templates/projects/cost/costcontrolaccount/list.html:52-54) — Lane-1 N+1 CONFIRMED: the CCA register re-derives EVM inputs per property access and the ORM does not cache across separate `.filter().aggregate()` calls; the register renders `bac`, `cpi`, `health.badge`, `health.state` per row, and `health` is resolved TWICE per row (two template lookups). Measured: 13-22 queries/row (worst case: bac 2 + cpi 4 + health.badge 8 + health.state 8), 75 queries/page at only 3 seeded rows vs sibling bar 10-13 — a full 15-row page projects to ~300. Suggested fix (either): (A) minimal — make `active_revision`, `bac`, `ac`, `committed` `cached_property` (per-instance, per-request safe); collapses to 4 queries/row, all 16 public properties stay plain properties reading the cached primitives, contract untouched; or (B) at-bar — annotate the `cca_list` queryset with three grouped sums (`ProjectBudgetLine` Sum grouped by control_account over approved+activated revisions; `ProjectExpense` conditional Sum grouped by control_account for actual/accrual and for commitment), properties prefer the annotation and fall back to computing (the 6.11 DeliverySchedule "prefer annotation, fall back to property" precedent; the scm Reports grouped-aggregate idiom). B lands the register at ~15 queries/page, matching siblings. The per-row SUMs are indexed and bounded per CA — this is a round-trip-count problem, not a scan problem; no new index fixes it.**

**[Important] apps/projects/models/CostManagement/CostControlAccounts.py:86-236 (surfaces at templates/projects/cost/costcontrolaccount/detail.html:11,32,36-50) — same root cause on the detail page: the EV panel renders all 16 metrics plus `health` twice, with no memoization, so `bac` is re-queried ~15 times, `ac` ~10, `active_revision` ~20. Measured: 119 queries for ONE object vs `bvr_detail` 13 and `pex_detail` 8 (clears the >100 bar today at seed scale of 1 CA). Fix is the same property-side change as above — Option A alone collapses this page to ~20 queries; no template or view change needed.**

**[Minor] apps/projects/migrations/0005:146-148 / models/CostManagement/ProjectBudgetLines.py:58-65 — the `category` filter and the `_pbl_totals` per-category aggregate (`category=cat` conditional Sum over tenant scope) have no `(tenant, category)` composite; EXPLAIN falls back to the tenant-leading prefix of the (tenant, number) unique (ref, 31 rows on acme). Correct-but-uncovered combination; the other three PBL filters all have their shipped composite. Add `pbl_tnt_category_idx` only if category filters prove common.**

**[Minor] apps/projects/migrations/0005:154-168 — PEX `tenant+status` (the register's status filter, and Overview.py:73-77 `posted_spend` conditional Sum) and BVR `tenant+status` without project (Overview.py:71-72 `pending_revisions` count) likewise ride the tenant prefix (`pex_tnt_date_idx` / `bvr_tnt_prj_status_idx` leading tenant). Tenant partition is the real selectivity here; fine at tenant scale — note only.**

**[Minor] apps/projects/migrations/0005:44-68,86-116 — every register orders `["-created_at","-id"]` (PEX `["-entry_date","-id"]`) with no `(tenant, created_at)` composite → EXPLAIN shows `Using filesort` on the tenant partition for base-list queries. Identical shape to the 7.1/7.2 siblings' orderings — house convention, not a 7.4 defect; index only if a register ever goes wide.**

### Measured numbers (acme: 3 Projects / 4 BVR / 3 CCA / 31 PBL / 12 PEX)

| page | queries | sql time | sibling bar (7.1/7.2) |
|---|---|---|---|
| cca_list | **75** | 46-141 ms | 10-13 |
| cca_list?project= | **75** | 141 ms | — |
| cca_detail (CCA-00001) | **119** | 142 ms | 8-13 (bvr/pex detail) |
| bvr_list | 10 | 15 ms | 10-13 |
| pbl_list | 13 (incl. totals strip + 3 dropdowns) | 32 ms | 10-13 |
| pex_list | 11 | <1 ms | 10-13 |
| bvr_detail (BVR-00001) | 13 (incl. amount_delta = 3) | <1 ms | 8-13 |
| pex_detail | 8 | 32 ms | 8-13 |
| projects overview | 20 (7.4 hunk adds exactly 2) | <1 ms | — |
| prj_list / bsl_list / tsk_tree (baselines) | 11 / 10 / 12 | — | — |

Per-row probe: `bac` 2 q · `cpi` 1-4 q · `health` 5-8 q × two template resolutions → 19.0 q/row average, 22 worst → 12 + 15×19 ≈ **297 queries at a full page**.

### Index audit
All composites present as declared; `active_revision`'s project+status lookup uses the project_id FK index; `bvr_activate`'s select_for_update hits `bvr_tnt_prj_status_idx` exactly; per-CA expense aggregates use the control_account FK index. No shipped filter is index-less; the three Minors are the only uncovered combos.

### Clean bills
bvr_list / pbl_list / pex_list / pex_detail / bvr_detail / overview within sibling bar; pbl totals strip aggregates in ONE conditional-Sum query; pagination LIMIT-bounded with indexed counts; seeder _cost strictly linear; forms carry no chained-FK `__str__` hop; admin list_select_related everywhere.

**Lane 4 count: 1 Critical / 1 Important / 3 Minor** (one root cause shared with lane 1's handoff; fix = cached_property floor, grouped-annotate at-bar)

---

## Lane 5 — qa-smoke-tester (2026-09-10, REPORT-ONLY override)

**Harness re-run first: 297/297 green, no regression.** Then 138 gap-probe checks (POST create paths end-to-end, form validation paths, filter+pagination composition, activate audit trail, rejection evidence, redirect targets, cross-tenant form POSTs, message-frame sanity) — all green.

### Findings

**[Critical] cca_delete — 500 on a CA referenced by any expense (CONFIRMS lane 1's pending finding; fresh evidence, not a new discovery).** `apps/core/crud.py:230` (`obj.delete()` inside `crud_delete`, reached from `apps/projects/views/CostManagement/CostControlAccounts.py:81`). `ProjectExpense.control_account` is PROTECT and non-nullable, so POST `cca_delete` on any CA with expenses raises `ProtectedError` → 500: `POST /projects/controlaccounts/<pk>/delete/ → 500, django.db.models.deletion.ProtectedError … 'ProjectExpense.control_account'` (expected 302). Two aggravations: the CA survives with no message, and `crud_delete` writes the `"delete"` AuditLog row BEFORE `obj.delete()`, so every attempt also leaves an orphan delete-audit row for a CA that still exists. Suggested fix: in `cca_delete` (or centrally in `crud_delete`), wrap the delete in try/except `ProtectedError` → `messages.error` + redirect to detail, and write the audit row only after a successful `obj.delete()`.

**[Minor] Cross-tenant FK refusal on the four create forms never uses the pinned `_reject_foreign` message.** Every FK target of the 7.4 forms (Project, BudgetRevision, CostControlAccount, ProjectTask, GLAccount, User, Party) carries a tenant column, so `TenantModelForm` scopes every ModelChoiceField queryset and Django refuses a forged foreign pk earlier with the generic `Select a valid choice. That choice is not one of the available choices.` (200 + field error, no row created, foreign row untouched — the security outcome is correct). Evidence: POST pbl_create with `budget_revision`=<Globex pk> → 200, error renders, no row; same for bvr/cca/pex project/control_account probes. `_reject_foreign` is therefore unreachable defense-in-depth on these forms (its `"That record belongs to another workspace."` message can never render). Suggested fix: none required for security; optionally record in the contract that the pinned message is second-layer only, or accept the Django default message as the user-visible one.

**[Minor] `bvr_reject` validates the decision form BEFORE the status precondition.** `apps/projects/views/CostManagement/BudgetRevisions.py` (`bvr_reject`): POST reject on a non-pending revision with EMPTY decision_notes returns `A rejection needs a stated reason.` instead of the correct status refusal; with notes present the correct `Only a revision pending approval can be rejected` fires. Verified empirically on seeded draft BVR-00004 (non-destructive): empty-notes → form-order message; row untouched, still draft, `decision_notes` still `''`. Writes nothing in either case; the reject button only renders for pending rows, so this needs a crafted/stale POST. Suggested fix: move the `obj.status != "pending_approval"` check above `form.is_valid()`.

### Probe-area summary
PASS 1 POST create paths (PBL-00032/BVR-00005/CCA-00004/PEX-00013 minted, numbers in messages, create/delete audits, cascade delete of a draft revision with lines clean) · PASS 2 form validation (amount=-5, cross-project clean(), duplicate revision_no/CA code via TenantUniqueMixin, missing control_account, revision_no 65535 cap, percent_complete 150) · PASS 3 filter+pagination composition (scoped rows, page links preserve filters, filtered totals smaller and exact: 1,366,000.00 / 1,120,000.00 < 1,631,000.00) · PASS 4 activate audit trail (one activate + one supersede per row, already-superseded not re-superseded, activated_at kept as history) · PASS 5 rejection evidence (notes persisted + rendered, stamps + audit) · PASS 6 redirect targets (valid verbs → detail, refusals → detail, deletes → list) · PASS 7 cross-tenant POST re-check (all four forms refuse at 200, no rows) · PASS 8 message-frame sanity (no leak into the next request).

### Row-count identity (start == end)
BVR 8/8 · CCA 6/6 · PBL 62/62 · PEX 24/24 (Acme 4/3/31/12 intact) · Projects 6/6 · AuditLog 4694/4694 · all four tables byte-identical.

**Lane 5 count: 1 Critical (confirms lane 1; not a new discovery) / 0 Important / 2 Minor — plus 138/138 gap-probe checks green**

---

## Lane 6 — security-reviewer (2026-09-10, FINAL lane)

60/60 runtime checks passed inside one force-rolled-back transaction; temp scripts deleted.

### Findings

**[Important] apps/projects/views/CostManagement/ProjectBudgetLines.py:112-123 — the ACTIVE cost baseline can be rewritten through its lines, bypassing change control.** `pbl_edit`/`pbl_delete` are login-only with no locked-revision guard, so any member can POST `/budgetlines/<pk>/edit/` and change (or delete) a `ProjectBudgetLine` belonging to the approved+activated revision — silently moving BAC, EV, PV, available, and the health badge for every control account that revision feeds, with no governance verb and only a field-level "update" audit row. The BVR row itself is frozen (`bvr_edit`/`bvr_delete` refuse `is_locked`), but the baseline's content is not; the same argument that froze posted expenses (deviation #3: "the evidence the EVM math reads") applies verbatim to baseline lines, and contradicts the module's own docstring ("a baseline that could be quietly rewritten would not be a baseline"). This matches the letter of the frozen contract (§5 "No verbs. Ordinary frozen-free CRUD.") so it needs a contract ruling, not a silent fix. Suggested fix: refuse PBL edit/delete when `obj.budget_revision.is_locked` (mirror `_LOCKED_MSG`), or route the decision through the contract first.

**[Minor] apps/projects/admin.py:156-157 — `decision_notes` is editable in `BudgetRevisionAdmin`.** A Django-admin edit can rewrite the rejection rationale — verb-written evidence (`bvr_reject` is its only legitimate writer) — outside the gate. As-built matches the contract's pinned readonly list (§11.2), but the 7.2 precedent makes the equivalent field readonly (`ResourceTimeEntryAdmin.readonly_fields` includes `decision_note`, admin.py:143-144). Suggested fix: add `"decision_notes"` to `BudgetRevisionAdmin.readonly_fields`.

**[Minor] apps/projects/views/CostManagement/BudgetRevisions.py:215-216 — `bvr_activate` hard-codes the audit `{"from": "approved"}` and writes its own audit row outside the atomic block.** The per-row `supersede` audits are inside `transaction.atomic()` while the main `activate` audit is after it — a failure between commit and audit leaves an activation with no audit row. Suggested fix: capture `previous` and move the `write_audit_log` call inside the atomic block. (Merged with lane 1's shape finding into I3.)

**[Minor — hardening note, not a defect] models' `active_revision` filters by `self.project` with no tenant predicate; tenant isolation of the property layer rests on the form layer.** Every view fetch site is tenant-scoped (all 26 verified); DB invariants hold (11/11 mismatch SELECTs returned 0); consistent with the app-wide `anchor_task` same-project pattern; a model-`clean()` tenant pin would make it structural. Note only — N1.

### Authorization matrix
All 26 views verified from the URL side (table above in the lane transcript): the four contract-reserved admin verbs carry the full `@login_required + @tenant_admin_required + @require_POST` stack; `bvr_submit`/`pex_post` login-only by design; member escalation attempts 403 having written nothing; audit rows carry `changes.from/to`, tenant, action ≤ 10 chars.

### Clean bills
XSS (no `|safe`, no attribute interpolation of user strings, autoescape verified in value positions) · `_initial_currency` deep link tenant-scoped · seeder `_cost` tenant-clean per tenant · migration 0005 matches models · integrate hunks complete and additive · admin verb-driven state readonly (only gap: M10) · numbering/enumeration app-wide convention.

**Lane 6 count: 0 Critical / 1 Important / 3 Minor**

---

# CLOSE-OUT — deduped, sorted, assigned (2026-09-10)

Six lanes: 2C/6I/19M raw → deduped below. Status legend: `[ ] open` → `[x] fixed` / `[~] skipped — reason` / `[n] no-action — reason` (Phase 5 fills these in).

## Critical
- [x] **C1** fixed (51d56966) — `cca_delete` wraps `crud_delete` in try/except `ProtectedError` inside `transaction.atomic()` (the `party_delete` idiom): `messages.error` names the blocking expenses, redirects to `cca_detail`, and the atomic block rolls the pre-written audit row back on failure so it lands only on success. Verified: POST on CCA-00001 → 302 + message + CA intact + AuditLog count unchanged; throwaway expense-free CA → 302 to list, gone, exactly one delete-audit row.
- [x] **C2** fixed (5ecd1a38) — `active_revision`, `bac`, `ac`, `committed` are `cached_property`; all 16 public metrics stay plain properties reading the cached primitives; zero call-site changes. Measured (CaptureQueriesContext, warmed): cca_list 75 → **22** queries at 3 rows, cca_detail 119 → **14**.

## Important
- [x] **I1** fixed (cf8cacd2 + contract e777a1e6) — `pbl_edit`/`pbl_delete` fetch with `select_related("budget_revision")` and refuse `obj.budget_revision.is_locked` BEFORE delegating to the crud helpers, with the `_LOCKED_MSG` wording ("...frozen cost history — its lines cannot be edited or deleted; submit a new revision to change the baseline."). Verified: GET/POST edit + POST delete on PBL-00001 → 302 + refusal + row unchanged; PBL-00029 (draft-project line) still editable, delete path proven on a throwaway unlocked line.
- [x] **I2** fixed (03ec7c6b) — `.order_by()` before `.values("category")`; the totals SQL now ends `GROUP BY ... ORDER BY NULL` (no Meta columns — Error-1055 safe).
- [x] **I3** fixed (7547f9c9) — `previous = obj.status` captured before the atomic block (loop variable renamed so it cannot shadow), `write_audit_log(..., "activate", changes={"verb": "activate", "from": previous, "to": previous})` INSIDE the block, post-block call removed. Verified on throwaway rows: activate audit carries from=approved, to=approved.
- [x] **I4** fixed (623d29ad, ea7fb921, 63c15f60, 9aaea142, 0c5f1fc8 — one per template) — `ta-right` → `text-right` in the five templates; `grep -rn "ta-right" templates/projects/cost/` is empty.
- [x] **I5** fixed (d0070e6e) — the delta headline rides the overview's stat-card markup (`stat-icon purple` + `<p class="stat-value">{{ obj.amount_delta }}</p>` + `stat-label`); the `<p>` keeps the harness's `stat-value">NUMBER</p>` regex valid.

## Minor
- [x] **M1** fixed — the four empty `CostManagement/__init__.py` files (a2145045, 6ed01412, a28a3852, 315bdeeb — one commit each per house rule).
- [x] **M2** fixed (37d76ef3, f526d2fe, 32bf9632, 1635f5ca) — `{% elif obj.status == 'superseded' %}` → `badge-info` on BVR list+detail; `{% elif obj.status == 'closed' %}` → `badge-muted` on CCA list+detail. Harness note: the walk's superseded-badge expectation updated from the old fallback `badge">Superseded<` to `badge-info">Superseded<` (it encoded the missing branch).
- [x] **M3** fixed (1579ca6f, 9fb038d6) — the Baseline badge gates on `activated_at AND status == 'approved'`; superseded rows show their stamp as a muted plain date (list + detail).
- [x] **M4** fixed (50fd8199) — reject form moved into the Revision card body after the detail grid (the prq precedent), role- AND status-gated; `name="decision_notes"`, label and the confirm kept.
- [x] **M5** fixed (8c9609ff, e4722a01) — `("source_kind", "source_kind", False)` in the `pex_list` filters + the Source-kind select mirroring the entry-type one; junk `?source_kind=` values are still silently ignored by the L11 guards.
- [x] **M6** fixed (9cf6d324 + comment-tag fix 0e645b4c) — the totals card now sits below the register card, so the filter bar leads like every other 7.x list.
- [x] **M7** fixed (32d4e38a) — the dead `{% empty %}` branch in the totals strip is gone.
- [x] **M8** fixed (6a527cdc) — the unreachable `end == start` branch deleted; the comment now states end > start is guaranteed at the division.
- [x] **M9** fixed (26112b7a) — ProjectBudgetLineAdmin comment corrected (wbs_node deliberately NOT joined — as-built wins) + `# --- 7.4 Cost & Budget Management ---` header above the four registrations.
- [x] **M10** fixed (2323d747) — `"decision_notes"` added to `BudgetRevisionAdmin.readonly_fields` (the 7.2 `decision_note` precedent).
- [x] **M11** fixed (4e086cc4) — the `status != "pending_approval"` check now runs before `BudgetRevisionDecisionForm` validation; both messages unchanged. Verified: empty-notes reject on a draft → the status refusal; on a pending row → the reason refusal; nothing written either way.
- [x] **M12** fixed (ff60ce1d) — one `other`-category line (5000.00, sundry-costs note) appended to the ACTIVE project's revision 0 in `_cost`; the shared DB was NOT flushed or re-seeded (31 Acme PBL rows verified intact) — the line lands on fresh workspaces. Harness note: the page-1 expectation now reads the DB's newest Acme PBL number instead of the hard-coded `PBL-00031`.
- [x] **M13** fixed (9071c805) — contract §6 `source_kind` max_length 15 → 16 (choices line + field table, fields.E009/`supplier_invoice` parenthetical); §7 currency fallback wording = "the first Currency on file (global table, L29)"; §7 carries the one-line note that `_reject_foreign`'s pinned message is unreachable second-layer defense because every FK target is tenant-scoped (security outcome unchanged); §5's I1 lock ruling landed with the I1 commit.
- [n] **M14** no-action — index notes (`(tenant, category)` on PBL, `tenant+status` on PEX/BVR, `(tenant, created_at)` ordering composites) stay recorded for a future pass; no migration this pass (no model changes were made anywhere, so none is needed).

## No-action notes
- **N1** `active_revision` tenant predicate — form-layer enforcement + verified DB invariants; model-`clean()` pin deferred as hardening (lane 6).
- **N2** Seeder chartered/draft line counts below "7-10" — page-2, band and delta goals all met; documented in the seeder docstring (lane 2).

**Deduped totals: 2 Critical / 5 Important / 14 Minor + 2 no-action notes.**

**Close-out status (fixer, 2026-09-10):** C1-C2, I1-I5, M1-M13 all fixed; M14 no-action (N1/N2
below unchanged). Final gate: `manage.py check` clean; `temp/smoke_74.py` **301/301 green**
(297 original + 4 added by the I1 refusal checks), run twice for stability. Harness upkeep:
I1's editable-form check moved to an unlocked line (+ refusal checks for PBL-00001), I4 string
swap, M2's superseded-badge expectation updated to `badge-info` (encoded the old missing
branch), M12's page-1 number read from the DB, C2's span-a-mutation `ac` assertions re-fetch a
fresh instance (cached_property is per-instance, request-scoped), and the audit scrub is scoped
to rows the run itself wrote (a pre-existing orphan audit row on the shared DB had collided with
a fresh throwaway pk and got scrubbed once — historical detritus, referenced row long gone).
One lesson recorded the hard way: multi-line `{# … #}` comments leak into rendered HTML (the
harness's template-leak sweep caught it) — `{% comment %}` is the only safe multi-line form.
