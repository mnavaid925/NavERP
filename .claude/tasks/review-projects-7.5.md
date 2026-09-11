# Review — Projects 7.5 Risk & Issue Management

Reviews appended below, most severe first. Base `3eacff12cf7f466922b6874bd4085db647d97f59`.

---

## Deduped index — fix order (this is the list `code-fixer` burns down)

All six reviewers reported **0 Critical**. 23 findings: **10 Important, 13 Minor**. Cross-reviewer
duplicates are merged into one ID; the merged-away twin is noted so nobody re-files it.

| ID | Finding | Where | Source(s) |
|---|---|---|---|
| **I1** | `rsk_realize` / `iss_escalate` are two-model writes with no `transaction.atomic()` — a failed child create leaves a mutated parent | `views/RiskManagement/ProjectRisks.py:158-170`, `ProjectIssues.py:154-165` | code-reviewer |
| **I2** | 7.5 overview counts are computed but never rendered (contract §6 requires them) *and* cost 3 queries + 2 full-register Python passes | `views/ProjectInitiation/Overview.py:85-94` vs `templates/projects/overview.html` | code-reviewer **+ performance-reviewer** (same code path, one fix) |
| **I3** | A realized risk's detail page still offers a no-op "Realize" button that promises an issue | `templates/projects/risk/projectrisk/detail.html:132-136` | frontend-reviewer |
| **I4** | The `?top=1` lens is unreachable and the filter form silently drops it; the `?overdue=1` alias never shows as active | `templates/projects/risk/projectrisk/list.html:18-75`, `views/.../ProjectRisks.py:58-63` | frontend-reviewer |
| **I5** | The Resolve panel's two textareas render unstyled — `IssueResolutionForm` never gets `form-textarea` | `forms/RiskManagement/ProjectIssues.py:31-38`, `templates/projects/risk/issue/detail.html:117-124` | frontend-reviewer |
| **I6** | Response-action detail tells the user to cancel from the edit form, which has no such control | `templates/projects/risk/responseaction/detail.html:55` | frontend-reviewer |
| **I7** | `rra_list` orders by `-created_at` with no index — the only 7.5 register missing one (**needs a migration**) | `models/RiskManagement/RiskResponseActions.py:76-83` | performance-reviewer |
| **I8** | The Monte Carlo recomputes each risk's probability fraction on every one of up to 10 000 iterations | `views/RiskManagement/RiskAnalysis.py:191-195` | performance-reviewer |
| **I9** | `esc_create` / `esc_edit` / `esc_delete` are `@login_required` only, while `iss_escalate` is `@tenant_admin_required` — a member can forge, rewrite and delete the escalation trail (**needs template gating too**) | `views/RiskManagement/IssueEscalations.py:39,72,79` | security-reviewer |
| **I10** | The monitoring "Lessons lens" ignores `?project=` and reads resolved/closed issues tenant-wide | `views/RiskManagement/RiskMonitoring.py:69-93` | explorer **+ security-reviewer** (same defect, one fix) |
| **M1** | Seeder leaves unused locals `i1`, `i2` and a redundant alias `escalated = esc_issue` | `management/commands/seed_projects.py:895,899,916` | code-reviewer |
| **M2** | The four 7.5 sub-package `__init__.py` files carry stale "empty until Integrate" docstrings | `models|forms|views|urls/RiskManagement/__init__.py` | code-reviewer |
| **M3** | `by_band` hardcodes the four band labels — a second copy of the band vocabulary | `views/RiskManagement/RiskMonitoring.py:145-148` | code-reviewer |
| **M4** | `?seed=` / `?iterations=` handling: an out-of-range `iterations` discards a valid `seed`, and on POST the params bind to `request.POST` only so a query-string seed is ignored | `views/RiskManagement/RiskAnalysis.py:172-180` | code-reviewer **+ qa-smoke-tester** (same code path, one fix) |
| **M5** | `esc_detail` renders `obj.issue.owner` without `issue__owner` in `select_related` — 1 extra query per detail | `views/RiskManagement/IssueEscalations.py:66-68` | code-reviewer (cost confirmed by performance-reviewer) |
| **M6** | Three 7.5 admins declare `list_select_related` joins for FKs no changelist column renders | `admin.py:206-207,229-230,244` | explorer |
| **M7** | `detail-grid` is given a `<div>` wrapper no sibling uses, so the label/value grid collapses | `templates/projects/risk/risk_monitoring.html:219-222` | frontend-reviewer |
| **M8** | The Monte Carlo page never states its sampling / planning-grade caveat | `templates/projects/risk/risk_analysis.html:115` | frontend-reviewer |
| **M9** | `risk_analysis` queries the register twice on POST; the second set is a subset of the first | `views/RiskManagement/RiskAnalysis.py:143,186-189` | performance-reviewer |
| **M10** | `risk_monitoring` makes ~10 separate O(n) Python passes and evaluates `severity_band` twice per row | `views/RiskManagement/RiskMonitoring.py:112-148` | performance-reviewer |
| **M11** | The register's pinned derived lenses (`review_date`, `owner`) have no supporting index (**needs a migration**) | `models/RiskManagement/ProjectRisks.py:146-152` | performance-reviewer |
| **M12** | Unindexed choice/date filters on the issue and response registers — `iss_tnt_type_idx`, `iss_tnt_due_idx`, `rra_tnt_strategy_idx` (**needs a migration**) | `models/RiskManagement/ProjectIssues.py:104-110`, `RiskResponseActions.py:78-83` | performance-reviewer |
| **M13** | The two computed pages materialise the whole tenant register with no pagination or cap | `views/RiskManagement/RiskAnalysis.py:143`, `RiskMonitoring.py:80,110` | security-reviewer |

### Not filed — resolved or owned elsewhere

- ~~`manage.py check` is red~~ (explorer) — **resolved**: the blocker was the peer 7.7 `Requirement` model's
  `max_length`; 7.7 has since landed and `manage.py check` is green (`System check identified no issues`).
- **No 7.5 test files** (code-reviewer) — not a `code-fixer` item; owned by Phase 6 (test contract +
  `conftest.py` `risk_*` fixtures, then `test_risk_models` → `_forms` → `_views` → `_security`).

### Migration note (for I7 / M11 / M12)

The three index findings touch models, so they land as **one** migration. Read the leaf on disk immediately
before generating — `0007` is taken by 7.7, so expect `0008_*`. Do not reserve the number.

## code-reviewer

Read the full changeset (4 models, 6 forms, 6 view modules, 6 url modules, 14 templates, migration `0006`, seeder `_risk`, navigation, admin, overview, `_helpers`). The contract is matched closely: every url name resolves, every context key a template consumes is passed, `Meta.ordering`/index names/choice values/`Meta.fields` all match, all four models carry a tenant FK and are FK'd by string into 7.1–7.5, no score/band/EMV/percentile is stored, no `accounting.Currency` import, no write to `CostControlAccount.contingency`, no `annotate`/`filter` on a property, all badges are colour-named and present in `theme.css` (`stat-icon red` does exist — L33's stale recollection does not apply here), and every verb captures `previous` before mutating with an audit action ≤ 10 chars. The findings below are what the 200/405/IDOR/state-machine sweep cannot see.

### Important — `rsk_realize` is a two-model write with no `transaction.atomic()` — a failed issue create leaves a realized risk with no issue
- **Where:** `apps/projects/views/RiskManagement/ProjectRisks.py:158-170` (and the same shape at `apps/projects/views/RiskManagement/ProjectIssues.py:154-165`)
- **What:** `rsk_realize` saves the risk (`status="realized"`) and *then* creates the linked `ProjectIssue`. Neither the risk save, the issue create, nor the two `write_audit_log` calls are wrapped in `transaction.atomic()`. `iss_escalate` has the identical shape (saves the `IssueEscalation` row, then updates the issue's `escalation_level`/`escalated_to`/`escalated_at`). The 7.x house pattern for a verb that writes more than one model is atomic — `apps/projects/views/ProjectInitiation/Projects.py:139` (`prj_convert`), `CostManagement/BudgetRevisions.py:211` (`bvr_activate`), `ProjectPlanningScheduling/ScheduleBaselines.py:112,136`, `ResourceManagement/ResourceAllocations.py:171`.
- **Why it matters:** the contract's whole point for `rsk_realize` is that the register and the issue log "cannot drift about which risk materialized". If `ProjectIssue.objects.create` raises (auto-number `next_number` exhausted its 5 retries under a collision, a driver error, a future validation), the risk is already `realized` and the issue does not exist — the exact drift the contract forbids, with no rollback. A partial `iss_escalate` leaves the escalation row written but the issue's current level unchanged.
- **Fix:** wrap each verb's writes in `with transaction.atomic():` (import `transaction` from the `_base` toolkit the model modules already re-export), so a failed child create rolls the parent update back. Clone-family sweep: `grep -rn "def .*_realize\|def .*_escalate\|objects.create" apps/projects/views/` for any other verb that saves a parent then creates a child.

### Important — 7.5 overview counts are computed but never rendered (contract §6 requires them), costing 4 queries on the landing page
- **Where:** `apps/projects/views/ProjectInitiation/Overview.py:85-92` against `templates/projects/overview.html:15-32`
- **What:** the view adds `risk_count`, `above_tolerance`, `review_due_count` and `issue_count` to the context, but `templates/projects/overview.html` never references any of them — the `stat-grid` still ends at `posted_spend` (line 31), and the only 7.5 additions to the template are the six quick-link `<tr>` rows. Contract §6 pins `templates/projects/overview.html — 7.5 quick links + counts`; the counts half is missing.
- **Why it matters:** (a) contract drift — the required counts render nowhere; (b) the three risk figures are computed with **four** queries on the module landing page, two of which (`above_tolerance`, `review_due_count`) load the **entire** register and iterate it in Python — pure waste on a page every project user hits. A GET-200 smoke sweep sees nothing: the page renders fine, just without the numbers.
- **Fix:** either render the four values as stat cards / a summary row in `overview.html` (the committed intent), or drop the four context keys. Do not leave them computed-but-unused. If kept, compute all three risk figures from one materialised register (`reg = list(ProjectRisk.objects.filter(tenant=tenant))`) instead of three separate querysets.

### Important — no 7.5 test files in the changeset despite contract §0 pinning four
- **Where:** `apps/projects/tests/` (needs `test_risk_models.py`, `test_risk_forms.py`, `test_risk_views.py`, `test_risk_security.py`)
- **What:** the changeset adds zero test files; `find . -name "test_risk*"` finds only the unrelated procurement `test_riskcompliance_*`. Contract §0 names `test_risk_models/_forms/_views/_security` with `test_risk_*` names and `_risk_*` helpers. The "100-assertion smoke sweep" that passes is not in the tree.
- **Why it matters:** the smoke sweep cannot assert the things this review found, nor the classes the contract explicitly asks tests for (L8's content assertion, L3's comment-leak assertion). No regression guard exists for the derived-vs-stored invariant, the `?band=`/`?overdue=` lenses, or the Monte Carlo determinism.
- **Fix:** hand to **test-writer**: `test_risk_views.py` should assert each detail page's rendered HTML contains `str(obj)` (L8), that `?band=critical` returns exactly the rows whose `probability*impact` is 15–25, that `?overdue=1`/`?escalated=1` narrow before pagination, that a POST Monte Carlo with the same `?seed=` twice is byte-identical, and that no `{#`/`{% comment` marker leaks (L3); `test_risk_security.py` should assert cross-tenant 404s on all seven verbs and that `iss_escalate`/`rsk_reopen` 403 for a non-admin member.

### Minor — seeder leaves unused locals `i1`, `i2` and a redundant alias `escalated = esc_issue`
- **Where:** `apps/projects/management/commands/seed_projects.py:895,899,916`
- **What:** `i1 = issue(...)` and `i2 = issue(...)` are assigned and never read; `escalated = esc_issue` is an alias used only to pass `escalated` to the two `escalation(...)` calls.
- **Why it matters:** dead code the task explicitly flags; `i1`/`i2` look like they were meant to be linked to the escalation path and are not.
- **Fix:** drop the `i1 =` / `i2 =` assignments (call `issue(...)` bare) and pass `esc_issue` directly to `escalation(...)`.

### Minor — 7.5 sub-package `__init__.py` files are not empty and their docstrings are now stale
- **Where:** `apps/projects/models/RiskManagement/__init__.py`, `.../forms/RiskManagement/__init__.py`, `.../views/RiskManagement/__init__.py`, `.../urls/RiskManagement/__init__.py`
- **What:** contract §6 pins these four files as **empty** (the sibling `ProjectInitiation`/`CostManagement` sub-package `__init__.py` files are 0 bytes). These carry docstrings that still say "Empty until Integrate" / "Intentionally EMPTY ... added in the Integrate step" — but Integrate has already shipped (the top-level re-export blocks exist).
- **Why it matters:** convention drift against the contract and the siblings, plus a comment that now misdescribes the tree.
- **Fix:** blank the four files (or trim the docstrings to a single current line); they are functionally empty, so either is harmless — just stop asserting they are "empty until Integrate".

### Minor — `by_band` hardcodes the four band labels — a second copy of the band vocabulary
- **Where:** `apps/projects/views/RiskManagement/RiskMonitoring.py:145-148`
- **What:** `by_band` is built from a literal `(("low","Low"),("medium","Medium"),("high","High"),("critical","Critical"))` tuple, while the same labels already live in `ProjectRisk._BAND_LABELS`, the view's `BAND_CHOICES` (`ProjectRisks.py:22`) and `RiskAnalysis._BAND_BADGES`. `severity_band` itself reads `SEVERITY_BANDS`, so a fifth band would silently drop out of this strip.
- **Why it matters:** the task's "any second source of truth" rule — the summary strip can drift from `SEVERITY_BANDS` without any error.
- **Fix:** derive the labels from `ProjectRisk._BAND_LABELS` (or iterate `SEVERITY_BANDS`) instead of the inline tuple.

### Minor — an out-of-range `?iterations=` silently discards a valid `?seed=` (both fields share one form)
- **Where:** `apps/projects/views/RiskManagement/RiskAnalysis.py:172-180`
- **What:** `SimulationParamsForm` validates `seed` and `iterations` together; `if params.is_valid(): ... else: seed, iterations = None, None`. So `?seed=7&iterations=99999` fails validation on `iterations` and the valid seed is thrown away, resetting to `DEFAULT_SEED` (42). The contract only requires a *junk seed* to fall back; it does not say a valid seed should be lost because an unrelated field is out of range.
- **Why it matters:** a user who locks a seed for a reproducible comparison loses it on one mistyped iteration count — the determinism guarantee the page advertises is silently broken. No 500, so the smoke sweep passes.
- **Fix:** read each field independently (`seed = params.cleaned_data.get("seed") if "seed" not in params.errors else None`, or two small `IntegerField` forms / `as_db_int`-style guards), so a valid seed survives an out-of-range iteration count.

### Minor — `esc_detail` renders `obj.issue.owner` without `issue__owner` in `select_related`
- **Where:** `apps/projects/views/RiskManagement/IssueEscalations.py:66-68` against `templates/projects/risk/escalation/detail.html:28`
- **What:** the detail queryset selects `"issue", "issue__project", "target_user", "escalated_by", "created_by"` but the template dereferences `obj.issue.owner`, which is not in the select chain.
- **Why it matters:** one extra query per escalation detail view — small, but the registers/detail pages elsewhere are all fully selected (the task's "every rendered FK needs `select_related`" rule).
- **Fix:** add `"issue__owner"` to the `select_related(...)` call. (Routing: performance-reviewer owns N+1 cost; this is a one-line fix.)

code-reviewer: 0 Critical, 3 Important, 5 Minor.

## explorer

Read the `code-reviewer` section above and did not repeat it. This pass is structural / integration
integrity only: it traces every path, resolves every route name against the live urlconf, diffs the
migration against the models, runs the read-only Django checks, and walks the seeder's guards and
delete order. Verified clean: all 4 models / 6 forms / 30 view functions are re-exported and every
one is reachable from a `urlpatterns` entry; all 6 new url modules are imported and concatenated in
`urls/__init__.py`; the resolver builds with **0 duplicate names** and all 30 `projects:*` names
reverse (`/projects/risks/`, `/projects/risk-analysis/`, …); every `{% url %}` in `templates/projects/risk/`
and `overview.html` names an existing route; every `{% extends %}`/`{% include %}` target exists; no
first path component anywhere in `apps/projects/urls/` uses a converter (so no greedy shadowing) and
within each new module `add/` precedes `<int:pk>/`; `makemigrations --check --skip-checks` reports
**zero 7.5 drift** (the migration matches the four models field-by-field, including `related_name`,
`on_delete`, null/blank, validators and all 16 indexes / 4 `unique_together`s); the 5 `LIVE_LINKS["7.5"]`
keys match the five NavERP.md §7.5 bullets character-for-character and all six mapped targets resolve;
the `_risk` guard is its own (`ProjectRisk…exists()`) so it runs on a 7.1–7.4-only tenant; and the
`--flush` order (escalation → issue → response action → risk) is children-first against every new
FK (`SET_NULL`/`CASCADE`, no `PROTECT`), so it cannot raise. Findings below are what that sweep did not clear.

### Minor — `manage.py check` is red, but on a peer session's uncommitted 7.7 model — it cannot validate 7.5 (peer-session blocker, NOT a 7.5 defect)
- **Where:** `apps/projects/models/ScopeRequirements/Requirements.py:29` (untracked) via `apps/projects/models/__init__.py:60`
- **What:** `venv\Scripts\python.exe manage.py check` aborts with `fields.E009: 'max_length' is too small to fit the longest value in 'choices'` on `projects.Requirement.elicitation_method` and `.verification_method`. `Requirement` is the concurrent 7.7 Scope & Requirements session's uncommitted work (untracked `ScopeRequirements/` dir + uncommitted `models/__init__.py:55-63`; the same session is also mid-edit in `overview.html`, `Overview.py`, `seed_projects.py`). No 7.5 model, admin or url contributes a check error: `check` reports only these two, so the admin.E/urls.E checks all pass. On the 7.5 changeset at HEAD (without 7.7) check is clean, and `makemigrations --check --skip-checks` lists **only the four 7.7 models**, i.e. zero 7.5 drift.
- **Why it matters:** the required startup/validation gate is unavailable for the whole `projects` app while the peer's model is in the tree, so "7.5 is clean" and "check could not run" are indistinguishable to the next reader.
- **Fix:** none inside this changeset — do **not** touch the peer's files (L45). The 7.7 session must widen those two `max_length`s (or shorten the choice values); re-run `manage.py check` after it lands.

### Minor — the monitoring "Lessons lens" mixes a project-scoped risk list with tenant-wide issues
- **Where:** `apps/projects/views/RiskManagement/RiskMonitoring.py:69-93` (invoked at `:139` as `_lessons(tenant, register)`)
- **What:** `_lessons` iterates the **project-scoped** `register` for closed risks, but fetches the issue half with `ProjectIssue.objects.filter(tenant=tenant, status__in=("resolved","closed"))` — no `project` filter. Every other lens on the page (`top_risks`, `burndown_rows`, `review_queue`, `tolerance`, `by_category`, `by_band`) narrows to the selected project; the lessons table does not for issues.
- **Why it matters:** with `?project=X` selected, a reviewer sees another project's lessons mixed into X's report — the same class of "one page of N differs from its siblings" drift the contract's other lenses avoid.
- **Fix:** thread the selected `project` into `_lessons` and add `project=project` to the issue queryset when `project is not None`, matching the risk half.

### Minor — three 7.5 admins declare `list_select_related` joins for FKs no changelist column renders
- **Where:** `apps/projects/admin.py:206-207` (`ProjectRiskAdmin`), `:229-230` (`ProjectIssueAdmin`), `:244` (`IssueEscalationAdmin`)
- **What:** `ProjectRiskAdmin` joins `wbs_node`, `identified_by`, `contingency_account`; `ProjectIssueAdmin` joins `wbs_node`, `risk`, `raised_by`, `resolved_by`; `IssueEscalationAdmin` joins `escalated_by` — none of these appears in the corresponding `list_display`, and all three models' `__str__` is `f"{number} — {title}"` (no FK walked). `ProjectBudgetLineAdmin` (`:182-184`) documents the opposite rule for this app: "`wbs_node` is deliberately NOT joined … it renders in no changelist column, so the join would be dead weight — as-built wins."
- **Why it matters:** 8 unnecessary joins per changelist render, and 7.5 contradicts the 7.4 precedent stated in the same file — a future maintainer cannot tell which is the house rule.
- **Fix:** drop the unrendered names from each `list_select_related`, keeping `tenant` plus exactly the FK columns in `list_display` (and any FK a `__str__` actually walks).

explorer: 0 Critical, 0 Important, 3 Minor.

## frontend-reviewer

Read the charter (`.claude/agents/frontend-reviewer.md`), contract §5 + §4.5/§4.6, `lessons.md` (L2/L9/L10/L33), `static/css/theme.css`, and the `code-reviewer`/`explorer` sections above — **their findings are not repeated**. Reviewed the 14 templates under `templates/projects/risk/` and the 7.5 additions to `overview.html` (the concurrent 7.7 rows/stat cards in `overview.html` are out of scope and ignored). Verified clean against the siblings (`cost/projectexpense/*`, `cost/costcontrolaccount/*`, `resource/capacity_demand.html`): **L2** — zero `{#` in the changeset, every long note uses `{% comment %}…{% endcomment %}` (counts match per file); **L10** — every `|default:` whose argument dereferences a nullable FK (`owner`, `identified_by`, `escalated_to`, `resolved_by`, `target_user`, `created_by`) sits inside a `{% if fk %}` guard, and the only unguarded `|default:` (`target_role`) takes a literal `"—"`; **L33** — every `badge-*` / `stat-icon <c>` / `text-*` / `btn-icon danger` class exists in `theme.css` (colour-sweep over all 15 files found no invented class); **L9** — all four lists include `partials/pagination.html`, which guards `previous_page_number`/`next_page_number`; every list has a `{% empty %}` `.empty-state`, a `filter-bar` whose FK/pk comparisons use `|stringformat:"d"` (never `|slugify`) and whose selects re-select from `request.GET`; the matrix degrades a 0-count cell to a muted `·` and `matrix_max` feeds no width calc; the burn-down is `.progress`/`.progress-bar` CSS bars, not a chart; `{{ simulation.samples }}` is never rendered. **Praise:** the two computed pages are the strongest templates in the changeset — the matrix is a real HTML grid with a band legend, the percentile table + stat cards read cleanly, and the "sized here / written by 7.4" caveat (`risk_analysis.html:172`) is exactly the one-writer discipline the contract asks for.

### Important — a realized risk's detail page still offers a no-op "Realize" button that promises an issue
- **Where:** `templates/projects/risk/projectrisk/detail.html:132-136` (the `{% else %}` at `:132`); contrast `templates/projects/risk/projectrisk/list.html:108,119`
- **What:** the Lifecycle panel branches on `{% if obj.status == 'closed' %}…{% else %}`. A `realized` row is not `closed`, so it takes the `else` and renders the "Realize (raise an issue)" danger button (confirm text: *"It will raise a linked issue."*). But `is_locked` is True for `realized`, so the list correctly hides Realize/Edit/Delete (`list.html:108`), and the view treats an already-realized row as `messages.info("That risk is already realized.")` and writes nothing (`apps/projects/views/RiskManagement/ProjectRisks.py:155-157`).
- **Why it matters:** the detail page contradicts the list's own gating for the same row: it shows a prominent button that claims it will mint an issue and instead silently no-ops (only the Close form is legitimately still allowed from `realized`).
- **Fix:** gate the Realize form with `{% if not obj.is_locked %}` and keep the Close form available for `realized` rows — i.e. split the `else` so Realize renders only while the row is live.

### Important — the `?top=1` lens is unreachable, and the filter form silently drops it (plus the `?overdue=1` alias)
- **Where:** `templates/projects/risk/projectrisk/list.html:18-75` (no field or link for `top`); the only lens link in the whole 7.5 UI is `templates/projects/risk/issue/list.html:11` (`?escalated=1`)
- **What:** `rsk_list` implements a documented `?top=1` ordering lens (`apps/projects/views/RiskManagement/ProjectRisks.py:60-63`) and also accepts `?overdue=1` as an alias of `?review_due=1` (`ProjectRisks.py:58`), but neither is a field of the filter form and nothing links to them. A GET form re-submits only its own fields, so even a hand-typed `?top=1` is dropped on the next Filter click, and `?overdue=1` renders the register's `review_due` checkbox *unchecked* (active lens, not shown as active). `rra_list`/`iss_list` both name their control `overdue`, so a cross-register link is lost only on the risk register.
- **Why it matters:** a contract-pinned derived lens (§4.1) has no entry point and cannot be held across a filter submit; the two sibling registers expose the same concept under a different parameter name.
- **Fix:** give `top` a UI entry (a "Top risks" link in `.page-actions`, or a `{% if request.GET.top == '1' %}<input type="hidden" name="top" value="1">{% endif %}` so it survives a submit) and make the `overdue` alias reflect the checkbox (rename the control to `overdue`, or OR both params in the `checked` test).

### Important — the Resolve panel's two textareas render unstyled (no `form-textarea` class)
- **Where:** `templates/projects/risk/issue/detail.html:117-124`, rendering `IssueResolutionForm` (`apps/projects/forms/RiskManagement/ProjectIssues.py:31-38`)
- **What:** `IssueResolutionForm` is a plain `forms.Form`, so it never runs `TenantModelForm`'s widget-class loop; its `root_cause`/`resolution_note` `Textarea` widgets set only `rows` (no `class`). The template renders them via `{{ field }}`, emitting `<textarea rows="3">` with no `form-textarea`; `theme.css` styles only `.form-textarea` (there is no bare `textarea` rule — line 312/317). The sibling plain forms set the class (`BudgetRevisionDecisionForm`, `ProjectRequestDecisionForm`: `attrs={"class": "form-textarea", "rows": 3}`).
- **Why it matters:** the only form controls on the page render as raw browser textareas with no theme border/background/focus ring — the exact "renders unstyled" class of defect L33 records, invisible to any 200/405 sweep.
- **Fix:** add `"class": "form-textarea"` to both `Textarea` attrs in `IssueResolutionForm` (and to `RiskClosureForm`'s widget, which is latent only because `projectrisk/detail.html:141` hand-writes its textarea instead of rendering the form).

### Important — response-action detail tells the user to cancel from the edit form, which has no such control
- **Where:** `templates/projects/risk/responseaction/detail.html:55`
- **What:** the copy reads "Cancelling is done from the edit form." `RiskResponseActionForm` excludes `status` (§3) and the only verb is `rra_complete` (`apps/projects/views/RiskManagement/RiskResponseActions.py`), so `cancelled` is unreachable and the edit form offers no way to set it.
- **Why it matters:** the page points the user at a capability that does not exist; the `cancelled` badge branch in the list (`responseaction/list.html:75`) is dead, and a completed action's only stated exit is false.
- **Fix:** either state the truth (a completed action is terminal; cancelling is not offered in 7.5) or add the missing cancel verb/field — do not leave an instruction for a control that is not there.

### Minor — `detail-grid` is given a `<div>` wrapper no sibling uses
- **Where:** `templates/projects/risk/risk_monitoring.html:219-222`
- **What:** each `<dt>/<dd>` pair is wrapped in a `<div>` inside `<dl class="detail-grid">`; every sibling detail page emits bare `<dt>/<dd>` as direct grid children (e.g. `templates/projects/cost/costcontrolaccount/detail.html:19-26`). `.detail-grid` is `grid-template-columns: repeat(auto-fit, minmax(240px, 1fr))` (theme.css:354), so the wrapper makes each pair a single stacked cell instead of the house label/value grid.
- **Why it matters:** the "Register summary" strip renders differently from every other `detail-grid` in the module — the label/value pairing the grid exists to produce is lost.
- **Fix:** drop the two `<div>` wrappers and emit the `<dt>/<dd>` pairs directly.

### Minor — the Monte Carlo page never states its sampling / planning-grade caveat
- **Where:** `templates/projects/risk/risk_analysis.html:115` (and the run block `:130-159`)
- **What:** the contract calls simple random sampling "the documented simplification" (`apps/projects/views/RiskManagement/RiskAnalysis.py:23`), and the house labels a planning-grade figure as such (`templates/projects/cost/costcontrolaccount/detail.html:39` — "Planning-grade linear PV"). The page describes the draw ("one Bernoulli per open risk … nearest-rank percentiles") but never says it is simple random sampling or a planning-grade estimate; only the contingency sized-vs-written caveat renders (`:172`).
- **Why it matters:** the percentiles read as an authoritative exposure figure with no note that the draw is the deferred-simplification method the contract documents.
- **Fix:** add one `.text-muted` line under the simulation, e.g. "Planning-grade: simple random sampling — Latin Hypercube and risk correlation are deferred."

frontend-reviewer: 0 Critical, 4 Important, 2 Minor.

## performance-reviewer

Read the charter (`.claude/agents/performance-reviewer.md`), contract §2/§4, `lessons.md` (L18 chained-N+1, L41 annotate/HAVING), the 7.5 views + four models + the `_risk` seeder block + `Overview.py` + the 14 templates, and the `code-reviewer`/`explorer`/`frontend-reviewer` sections above — **their findings are not repeated**. Two are cross-referenced, not re-filed: code-reviewer's `esc_detail` `obj.issue.owner` gap (`apps/projects/views/RiskManagement/IssueEscalations.py:66`) is confirmed as exactly **1 extra query per escalation detail** (add `"issue__owner"` to the `select_related`), and their Overview "counts computed but unrendered" finding is the same code path as my Overview query-cost finding below.

**Verified clean (the sweep the task asked for).** Every register queryset joins **every FK its template renders** — `rsk_list` (`project, wbs_node, owner, identified_by, contingency_account`), `rra_list` (`risk, risk__project, owner`), `iss_list` (`project, wbs_node, risk, owner, raised_by, escalated_to`), `esc_list` (`issue, issue__project, target_user, escalated_by`) — so there is **no N+1 on any register or detail page**: `rsk_list` = 4 queries (Paginator COUNT + page slice + `projects` + `owners` dropdowns) independent of row count, `rsk_detail` = 3 (obj + `response_actions` + `linked_issues`). **No Python property is used in a `filter()` / `order_by()` / `annotate()`** anywhere — `?band=`, `?review_due=`, `?overdue=`, `?escalated=` are all rebuilt from real columns (`_band_q`, `review_date__lt`, `due_date__lt`) and `?top=1` orders by columns — so the property-as-column hunt yields **no Critical** (no raise, no silent no-op). No `objects.filter()` inside a loop, no `get_user_model()` per row, no `len(qs)` on an unevaluated queryset, no queryset iterated twice. The `_risk` seeder is straight-line: **17 risks + 7 actions + 7 issues + 2 escalations = 33 `save()`s per tenant** (each a `next_number` SELECT + INSERT — no `bulk_create`, which would bypass `TenantNumbered.save()`), nothing quadratic; `--flush` is four bulk `objects.all().delete()` in children-first order (cheap). Remaining findings are cost, not correctness.

### Important — `rra_list` orders by `-created_at` with no index (the only 7.5 register missing one)
- **Where:** `apps/projects/models/RiskManagement/RiskResponseActions.py:76` (`ordering`) vs `:78-83` (indexes)
- **What:** `Meta.ordering = ["-created_at", "-id"]`, but the four indexes are `(tenant,risk)`, `(tenant,status)`, `(tenant,owner)`, `(tenant,due_date)`. Siblings `ProjectRisk` (`rsk_tnt_created_idx`) and `ProjectIssue` (`iss_tnt_created_idx`) both carry a `(tenant, -created_at)` index; RRA is the one that does not (confirmed against `migrations/0006_projectrisk_projectissue_riskresponseaction_and_more.py`).
- **Why it matters:** every `rra_list` render sorts the tenant's **entire** action set to return the first 15 rows — a filesort on every page load that grows with the register, where the index would let the planner walk in order and stop at 15.
- **Fix:** add `models.Index(fields=["tenant", "-created_at"], name="rra_tnt_created_idx")`.

### Important — the Monte Carlo recomputes each risk's probability fraction on every one of up to 10 000 iterations
- **Where:** `apps/projects/views/RiskManagement/RiskAnalysis.py:191-195`
- **What:** the per-iteration generator evaluates `PROBABILITY_PCT.get(risk.probability, 0) / 100` and touches `risk.cost_impact` for **every** risk on **every** iteration. The fraction is a pure function of the row and never changes across iterations.
- **Why it matters:** work is `iterations × n`. Seeder `n = 17` → 170 000 evaluations (trivial). A real program register `n ≈ 1 000` at the contract's max `iterations = 10 000` → **10 000 000 dict lookups + 10 000 000 integer divisions + up to 10 M `Decimal` additions** inside one synchronous POST — several seconds of CPU any logged-in member can trigger, on the page that already does the most work (the `Decimal` sum is the dominant term).
- **Fix:** precompute once, e.g. `population = [(r.cost_impact, PROBABILITY_PCT.get(r.probability, 0) / 100) for r in population]`, then `sum(cost for cost, p in population if rng.random() < p)` — removes the per-element dict lookup, division and attribute hop (a ~2× constant-factor cut; the draw stays O(iterations × n) and the 100–10 000 clamp is unchanged).

### Minor — `risk_analysis` queries the register twice on POST; the second set is a subset of the first
- **Where:** `apps/projects/views/RiskManagement/RiskAnalysis.py:143` (`register = list(register_qs)`) and `:186-189` (`population = list(register_qs.filter(...).exclude(...).order_by("id"))`)
- **What:** the POST path re-issues the same table scan that `register` already materialised; `population` is strictly `{r ∈ register : cost_impact > 0, status ∉ (closed, realized)}`.
- **Why it matters:** one avoidable round trip on the heaviest page. Not N+1 — the cost is fixed, not per-row.
- **Fix:** derive it in Python from the materialised list, preserving the pinned draw order: `population = sorted((r for r in register if r.cost_impact > 0 and r.status not in _UNCERTAIN_EXCLUDED), key=lambda r: r.id)`. Order matters — the RNG draws in `population` order, so the seed is only reproducible if this stays `id`-ascending.

### Minor — `risk_monitoring` makes ~10 separate O(n) Python passes over the register and evaluates `severity_band` twice per row
- **Where:** `apps/projects/views/RiskManagement/RiskMonitoring.py:112-148`
- **What:** `open_count`/`closed_count`/`realized_count` are three passes; `top_risks` **sorts the whole register** only to slice `[:25]`; `review_queue` is another pass + sort; `_burndown`, `_lessons`, `category_counter` and `band_counter` are four more; `severity_band` is computed in `above_tolerance_count` and again in `band_counter` (each call loops the four `SEVERITY_BANDS`).
- **Why it matters:** `n = 17` in the seeder is free, but the real-world ceiling (a large program register, ~10³ rows) makes this ~10 full passes plus 2× the band lookup per row, recomputed on every GET. Avoidable, not incorrect.
- **Fix:** accumulate the three status counts and the two `Counter`s in a single `for risk in register` loop (compute `severity_band` once per row into a local), and use `heapq.nlargest(25, register, key=lambda r: (r.probability, r.impact, r.cost_impact, r.id))` instead of `sorted(...)[:25]`.

### Minor — the register's pinned derived lenses have no supporting index
- **Where:** `apps/projects/views/RiskManagement/ProjectRisks.py:54-63` against `apps/projects/models/RiskManagement/ProjectRisks.py:146-152`
- **What:** `?review_due=1`/`?overdue=1` filter `review_date__lt` + `status__in` (no index on `review_date`); `?band=` is a 25-term OR over `(probability, impact)` (no index); `?top=1` orders by `(probability, impact, cost_impact, id)` (no index); `?owner=` has only the implicit single-column FK index, not a `(tenant, owner)` composite.
- **Why it matters:** each lens degrades to a scan/filesort of the tenant's register. `?band=`/`?top=1` are inherently non-btree (documented) and can stay; `review_date` and `owner` are cheap to index.
- **Fix:** add `models.Index(fields=["tenant","review_date"], name="rsk_tnt_review_idx")` and `models.Index(fields=["tenant","owner"], name="rsk_tnt_owner_idx")`; leave the band/top lenses as the documented scan.

### Minor — unindexed choice/date filters on the issue and response registers
- **Where:** `apps/projects/views/RiskManagement/ProjectIssues.py:47-51` vs `apps/projects/models/RiskManagement/ProjectIssues.py:104-110`; `apps/projects/views/RiskManagement/RiskResponseActions.py:39-42` vs `apps/projects/models/RiskManagement/RiskResponseActions.py:78-83`
- **What:** `?issue_type=` (`ProjectIssue.issue_type`) and `?strategy=` (`RiskResponseAction.strategy`) are non-FK choice columns with no index; `ProjectIssue.due_date` (the pinned `?overdue=1` lens, `ProjectIssues.py:42`) has no index — while RRA's `due_date` **is** indexed (`rra_tnt_due_idx`), so the issue log is the inconsistent one.
- **Why it matters:** each such filter scans the tenant's table; the issue log's overdue lens in particular is a first-class monitoring view.
- **Fix:** add `iss_tnt_type_idx` `(tenant, issue_type)`, `iss_tnt_due_idx` `(tenant, due_date)`, `rra_tnt_strategy_idx` `(tenant, strategy)`.

### Minor — `overview` computes the two 7.5 decision counts with 3 queries and 2 full-register Python passes
- **Where:** `apps/projects/views/ProjectInitiation/Overview.py:88-94`
- **What:** `risk_count` is a SQL COUNT, but `above_tolerance` and `review_due_count` each re-issue `ProjectRisk.objects.filter(tenant=tenant)` and iterate the whole register in Python (the first calls the `severity_band` property per row). Three queries, two full materialisations of the same table.
- **Why it matters:** this is the module landing page every project user hits; it pays 2 full register loads to compute two integers. (code-reviewer owns the "counts never rendered" half of this; this is the query-cost half.) `above_tolerance` is also expressible as a column filter — the same `(probability, impact)` reconstruction `_band_q` uses.
- **Fix:** materialise once (`reg = list(ProjectRisk.objects.filter(tenant=tenant))`) and derive both sums from it, or reuse `_band_q("high") | _band_q("critical")` so the database does the tolerance count.

performance-reviewer: 0 Critical, 2 Important, 4 Minor.

## qa-smoke-tester

Swept all 30 named routes of projects 7.5 (29 `projects:` URLs + the `projects:overview` landing page) through the in-process Django test client as `admin_acme` after `migrate` + `seed_core` + `seed_accounts` + `seed_projects`, against real seeded rows (17 risks / 7 response actions / 7 issues / 2 escalations per tenant, ×2 tenants). ~500 requests in total — 325 in the main pass plus 145 POST-based cross-tenant IDOR probes, 4 empty-body create POSTs, page-2 fetches and a 19-template comment-marker sweep. **Zero 500s, zero comment-marker leaks, zero cross-tenant reads, all eight state-machine gates hold.**

### Minor — Monte Carlo `?seed=` / `?iterations=` are silently ignored on POST — **see M4**
- **Where:** `apps/projects/views/RiskManagement/RiskAnalysis.py:172`
- **What:** `params = SimulationParamsForm(request.POST if request.method == "POST" else request.GET)` binds the parameters to `request.POST` *exclusively* on POST, so a seed supplied in the query string is discarded. Measured: POSTing `/projects/risk-analysis/?seed=123&iterations=500`, `?seed=42`, `?seed=7` and `?seed=999` (empty POST body) all return the *identical* result set — `Mean 616847.00 / P10 418000.00 / P50 621000.00 / P80 760000.00 / P90 806000.00` — because every one of them fell back to `DEFAULT_SEED = 42` / `DEFAULT_ITERATIONS = 1000`. With the seed in the POST body instead (the on-page form's normal path) the seed *is* honoured and is reproducible per seed (`123 → 623600.00`, `42 → 620272.00`, `7 → 626772.00`, `999 → 632492.00`).
- **Why it matters:** the page is self-consistent (line 128 honestly reports "Seed 42 · 1000 iterations"), so nothing is *wrong* on screen — but a bookmarked or shared simulation URL with `?seed=123&iterations=500` renders the form showing 123/500 on GET and then runs (and reports) 42/1000 on POST. The module's own docstring pins `rng = random.Random(seed)` from the query params, so this is a contract/implementation drift, not a deliberate choice. Same line is why `?iterations=99999` falls back to 1000 rather than clamping to `MAX_ITERATIONS = 10000` — a validation error on either field discards *both* values (`RiskAnalysis.py:173-179`).
- **Fix:** fall back per-field instead of wholesale — e.g. build the form from `request.POST`, and when it is invalid or a field is missing, re-read that field from `request.GET` before applying `DEFAULT_SEED`/`DEFAULT_ITERATIONS`; clamp `iterations` to `[MIN_ITERATIONS, MAX_ITERATIONS]` rather than defaulting it.

#### url-name → status + content check

| url name | status | content check |
|---|---|---|
| `projects:overview` | 200 | "Project Management" present; no `{#` / `{% comment` |
| `projects:rsk_list` | 200 | `Risk Register` title; 15 rows; no comment markers |
| `projects:rsk_create` | 200 | `Log Risk` heading; POST with empty body → 200 re-render |
| `projects:rsk_detail` | 200 | `RSK-00017` in HTML, response-action + linked-issue blocks |
| `projects:rsk_edit` | 200 | `Edit Risk` heading |
| `projects:rsk_delete` (GET) | 405 | correct — `@require_POST` |
| `projects:rsk_realize` (GET) | 405 | correct |
| `projects:rsk_close` (GET) | 405 | correct |
| `projects:rsk_reopen` (GET) | 405 | correct |
| `projects:rra_list` | 200 | `Risk Response Actions` title; no comment markers |
| `projects:rra_create` | 200 | `Log Response Action`; empty POST → 200 |
| `projects:rra_detail` | 200 | `RRA-00007` in HTML |
| `projects:rra_edit` | 200 | `Edit Response Action` |
| `projects:rra_delete` (GET) | 405 | correct |
| `projects:rra_complete` (GET) | 405 | correct |
| `projects:iss_list` | 200 | `Issue Log` title; no comment markers |
| `projects:iss_create` | 200 | `Log Issue`; empty POST → 200 |
| `projects:iss_detail` | 200 | `ISS-00007` in HTML, escalation form + resolution form |
| `projects:iss_edit` | 302 / 200 | 302 on the locked `ISS-00007` (the `is_locked` guard — correct); **200 + `Edit Issue`** on a live `ISS-00004` |
| `projects:iss_delete` (GET) | 405 | correct |
| `projects:iss_escalate` (GET) | 405 | correct |
| `projects:iss_resolve` (GET) | 405 | correct |
| `projects:iss_close` (GET) | 405 | correct |
| `projects:esc_list` | 200 | `Issue Escalations` title; no comment markers |
| `projects:esc_create` | 200 | `Log Escalation`; empty POST → 200 |
| `projects:esc_detail` | 200 | `ESC-00001` in HTML |
| `projects:esc_edit` | 200 | `Edit Escalation` |
| `projects:esc_delete` (GET) | 405 | correct |
| `projects:risk_analysis` | 200 | `Qualitative & Quantitative Analysis`; "Probability × Impact matrix" + "Largest cell: N" render; EMV total renders (`675400.00`) |
| `projects:risk_monitoring` | 200 | `Risk Monitoring & Reporting`; "Burn-down by identification month" (5 `style="width: N%"` bars), "Review queue", "Risk tolerance" all render |

**Junk params** — 20 variants (`?status=nope`, `?project=0`, `?probability=²`, `?seed=abc`, `?iterations=99999`, `?page=9999`, `?band=nope`, `?top=nope`, `?q=`, `?owner=0`, `?risk=0`, `?issue=0`, `?level=abc`, `?category=nope`, `?severity=nope`, `?overdue=1`, `?review_due=1`, `?escalated=1`, `?top=1`) × 4 registers + 11 × 2 computed boards = 102 requests: **all 200**, every one keeping its page title, and no junk enum/pk filter silently emptied a register (the empty state never appeared where the unfiltered page had rows).

**Page 2** — `rsk_list` (17 rows > `per_page=15`) renders 2 real rows on page 2; `rra_list`, `iss_list`, `esc_list` all 200 (Paginator clamps the out-of-range page).

**Cross-tenant IDOR** — 66 GET probes + **145 POST probes** across all 19 `<int:pk>` routes with globex pks: `rsk`/`rra`/`iss`/`esc` detail + edit → **404**; the 11 POST-only verbs + deletes → **404 on POST** (not just the 405 you get on GET, so the tenant filter is genuinely in the write path). No leak.

**State machine** (all executed inside a rolled-back transaction; seed state re-verified unchanged afterwards):

| gate | result |
|---|---|
| escalate on a resolved/closed issue refused | PASS — 302, `escalation_level 0 → 0` |
| resolve twice refused | PASS — second call does not overwrite `resolution_note` |
| close twice refused | PASS — `resolved → closed → closed` |
| close an open (non-resolved) issue refused | PASS — stays `blocked` |
| realize on a closed risk refused | PASS — `closed → closed` |
| risk close twice refused | PASS |
| complete twice refused | PASS — `completed_at` stamp stable |
| reopen a live risk refused | PASS — `identified → identified` |
| non-admin member on `iss_escalate` | **403** — `ops_acme` (role=Member) exists in the seed and is refused |
| non-admin member on `rsk_reopen` | **403** |

**Monte Carlo determinism** — two POSTs with the same `?seed=123&iterations=500` are **not** byte-identical, but the only difference is the two rotating `csrfmiddlewaretoken` values (16 diff lines, both CSRF inputs). With CSRF stripped the bodies are identical, and seeds 123/42/7 each reproduce their own numbers exactly. Determinism holds — see M4 for the separate seed-binding issue.

**Tenant-less superuser `admin`** (`tenant=None`) — `overview`, all four registers and both computed boards render **200** with their empty states (no 500), and the 0-safe branches hold (`Largest cell: 0`, zeroed burn-down, "No lessons captured").

qa-smoke-tester: 0 Critical, 0 Important, 1 Minor.

## security-reviewer

Swept all 29 7.5 view functions, the 6 forms, the 4 models, the 14 templates and the five shared-file blocks, and runtime-probed the classes a status-code sweep cannot see (POST-body FK scoping, the Monte Carlo clamp, GET-mutation, the `?project=` lens on the computed pages). Verified clean: every one of the 29 views carries `@login_required`; all 11 mutating verbs/deletes are `@require_POST` (GET → 405, re-confirmed at runtime); CSRF is present on all 13 POST forms in `templates/projects/risk/**` and no `@csrf_exempt` exists in the app; every audit action string is ≤ 8 chars (`create`, `update`, `delete`, `realize`, `close`, `reopen`, `escalate`, `resolve`, `complete`) against `AuditLog.action varchar(10)`; mass assignment is clean (no `Meta.fields = "__all__"`; `status`, `tenant`, `number`, `closed_at`, `completed_at`, `resolved_at`, `escalation_level`, `escalated_to`, `escalated_at`, `created_by` are all off the four ModelForms); no `|safe` / `mark_safe` / `autoescape off` / `.raw()` / `.extra()` / `cursor.execute` / `?next=` anywhere in the sub-module; no secrets or PII in the `_risk` seeder. Also **disproved** two suspicions at runtime: a crafted POST carrying a foreign tenant's `project` / `risk` / `issue` / `owner` / `wbs_node` / `contingency_account` / `target_user` pk is rejected with a field error on all four ModelForms (the `TenantModelForm` queryset scoping plus `_reject_foreign` both hold, and no row leaks), and the Monte Carlo clamp genuinely holds — `iterations=999999999`, `-5`, `abc`, `0`, `10^20` and a 100 000-digit `seed` all fall back to the 1000-iteration default in 0.2 s with a 200, because `SimulationParamsForm` invalidates the whole form rather than clamping field-by-field.

### Important — a non-admin member can write and delete the escalation trail that `iss_escalate` is admin-gated to protect — **I9**
- **Where:** `apps/projects/views/RiskManagement/IssueEscalations.py:39` (`esc_create`), `:72` (`esc_edit`), `:79` (`esc_delete`) — versus `apps/projects/views/RiskManagement/ProjectIssues.py:128-131` (`iss_escalate`, `@tenant_admin_required`)
- **What:** `iss_escalate` is deliberately admin-gated — its own docstring says "escalation is a privileged act". But the register it writes (`IssueEscalation`) has its own plain-CRUD trio gated by `@login_required` only. Confirmed at runtime as `ops_acme` (role=Member, `is_tenant_admin=False`): `POST /projects/issues/11/escalate/` → **403**, while `POST /projects/escalations/add/` with `issue=11&level=4&reason=…` → **302**, creating `ESC-00003 — L4 ISS-00004` owned by the member. The row renders on the issue's own "Escalation path" table (confirmed: the reason text is present in `/projects/issues/11/`). The same member then rewrote it (`esc_edit` → level 4 → 2, reason and outcome edited → 302) and deleted it (`esc_delete` → row gone). `esc_create` also accepts any `level` 1–4 and any live, resolved **or closed** issue.
- **Why it matters:** the admin gate on `iss_escalate` is bypassable for the register half of its effect. Any member can make it appear that an issue was pushed to "Level 4 — Executive Sponsor", name a target, edit someone else's escalation reason/outcome after the fact, and delete the record of who was told — the exact privilege and evidence-tampering the gate exists to prevent. It is intra-tenant, not cross-tenant, hence Important rather than Critical.
- **Fix:** gate the trio with the same decorator and stop rendering the buttons to non-admins.
  ```python
  @login_required
  @tenant_admin_required
  def esc_create(request): ...

  @login_required
  @tenant_admin_required
  def esc_edit(request, pk): ...

  @login_required
  @tenant_admin_required
  @require_POST
  def esc_delete(request, pk): ...
  ```
  In `templates/projects/risk/escalation/list.html` and `.../escalation/detail.html`, wrap the Add/Edit/Delete controls in `{% if request.user.is_superuser or request.user.is_tenant_admin %}` (the pattern already used at `templates/projects/risk/projectrisk/detail.html:127` and `templates/projects/risk/issue/detail.html:78`). If the intent is instead that any member may record an escalation, the fix is the reverse — drop `@tenant_admin_required` from `iss_escalate` — but do not leave the two paths disagreeing.

### Important — the lessons lens ignores the `?project=` filter and reads resolved/closed issues tenant-wide — **I10**
- **Where:** `apps/projects/views/RiskManagement/RiskMonitoring.py:80-83` (`_lessons`), consumed at `:139`
- **What:** every other lens on the page is anchored to the selected project (`register_qs` is filtered at `:108-109`), but `_lessons` re-queries `ProjectIssue.objects.filter(tenant=tenant, …)` with no `project=` term, then slices to 25. Confirmed at runtime: with `?project=255` (Fleet replacement programme, which has **zero** resolved/closed issues), the page renders both lessons belonging to `ISS-00005` and `ISS-00006` on project 256 (Customer portal release 3); same for `?project=254`.
- **Why it matters:** `lessons_learned` is the most sensitive free text in the module — root causes and post-incident reviews ("Root cause established during the post-incident review"). A user who has narrowed the board to one project is shown another project's incident write-ups, and `lessons_count` (`:140`) mis-reports the count for the selected scope. Intra-tenant today, but it is a derived path that reaches rows without re-anchoring to the lens every sibling lens honours, and it will become a cross-project boundary the moment per-project visibility lands. **This is the same defect explorer filed as a Minor; security-reviewer raises it to Important because of the free-text exposure.**
- **Fix:** pass the project through and filter on it, mirroring `register_qs`:
  ```python
  def _lessons(tenant, register, project=None):
      ...
      issues = (ProjectIssue.objects
                .filter(tenant=tenant, status__in=("resolved", "closed"))
                .exclude(lessons_learned=""))
      if project is not None:
          issues = issues.filter(project=project)
      issues = issues.select_related("project")
  ```
  and call it as `_lessons(tenant, register, project)`.

### Minor — the two computed pages materialise the whole tenant register with no pagination or cap — **M13**
- **Where:** `apps/projects/views/RiskManagement/RiskAnalysis.py:143` (`register = list(register_qs)`), `apps/projects/views/RiskManagement/RiskMonitoring.py:110` (same), plus `RiskMonitoring.py:80` which loads every resolved/closed tenant issue before `entries[:25]`
- **What:** with no `?project=` selected, both pages pull every `ProjectRisk` row in the tenant into Python — `_build_matrix` (O(n) buckets) plus a per-row dict in `emv_rows` for the analysis page, and `_open_risks` / `_burndown` passes on the monitoring page. `emv_rows` is sliced to 50 only *after* the full list is built and sorted (`:167`, `:217`), and `_lessons` slices to 25 only after loading every qualifying issue.
- **Why it matters:** a large tenant (tens of thousands of register rows) makes an unparameterised `GET /projects/risk-monitoring/` a whole-table materialisation in the request thread, reachable by any logged-in member. Not remotely triggerable and not unbounded-by-input, so Minor — but it is the one unbounded read in the sub-module.
- **Fix:** cap the working set the same way `emv_rows[:50]` caps the display, e.g. `register = list(register_qs[:2000])` with a "showing the first N rows" note, or push the burn-down to `values().annotate()`; for `_lessons`, add `.order_by("-resolved_at")[:25]` to the issue query instead of slicing in Python.

security-reviewer: 0 Critical, 2 Important, 1 Minor.
