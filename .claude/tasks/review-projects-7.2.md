# Review — Projects 7.2 Project Planning & Scheduling

Changeset: `69529770..HEAD` (base captured before the build; the tree was clean at BASE).
Contract: `.claude/tasks/contract-projects-7.2.md`.

Six read-only lanes, strictly serial (CLAUDE.md "Module Creation Sequence"):

1. code-reviewer — _in progress_
2. explorer
3. frontend-reviewer
4. performance-reviewer
5. qa-smoke-tester
6. security-reviewer

Findings are appended verbatim per lane below, then deduped, sorted Critical → Important →
Minor, given IDs (C1, I3, M7) and handed to the `code-fixer` agent.

---

## 1. code-reviewer

### Critical

- **apps/projects/forms/ProjectPlanningScheduling/ProjectTasks.py:22-38 — the spec-mandated "parent must belong to the chosen project" check is missing.** `clean()` runs `_reject_foreign` (tenant only) and the cycle walk, but never compares `parent.project_id` to `project_id`; `ProjectTask.clean()` (apps/projects/models/ProjectPlanningScheduling/ProjectTasks.py:102-105) checks only dates, so admin can create the same bad row. Why it matters: with a cross-project parent, `_decorate_wbs` never reaches the child from `roots`, so the task and its whole subtree **silently vanish from the WBS tree** (no wbs_code, no rollup contribution), and `task/form.html:23` explicitly promises "The parent must belong to the same project". Fix: enforce it in `ProjectTask.clean()` (covers form + admin + seeds) with `ValidationError({"parent": ...})`.

### Important

- **apps/projects/views/ProjectPlanningScheduling/ScheduleBaselines.py:74-81 + forms/.../ScheduleBaselines.py:14 — `bsl_edit` lets a `what_if` row become `baseline` via the form, bypassing the freeze machinery.** `BaselineForm.fields` includes `baseline_type`; editing a what-if to "Frozen Baseline" calls plain `crud_edit` — no `freeze_snapshot()`, no `is_active`, snapshot columns stay NULL — and the row is now `is_frozen`, so it can never be edited or deleted again (guards at :76, :88), yet `bsl_activate` will happily activate a snapshot-less baseline. Fix: drop `baseline_type` from the form on edit (or pin it in `bsl_edit`'s kwargs / exclude in `__init__` when `instance.pk`), so type transitions only happen through `bsl_promote`.
- **No committed tests for 7.2.** The contract pins the test convention (`planning_*` fixtures, `test_planning_*`) and 7.1 shipped `test_initiation_{models,forms,views,security}.py`; this changeset ships zero test files — verification is only uncommitted `temp/smoke_72*.py`. NOTE (main session): tests are Step 5c of the same pipeline, still queued — not a deferral; this lane's finding is satisfied by the pending 5c work, and 5c must cover the state guards, cycle guards and cross-tenant re-checks this lane had to eyeball.

### Minor

- **forms/.../ProjectTasks.py:3-7 — `owner` is excluded from `_reject_foreign`, deviating from frozen spec line 90** ("`_reject_foreign` on `project`, `parent`, `owner`"). The form's rationale is factually right (User.tenant is nullable, and 7.1 never re-checks `project_manager`/`executive_sponsor`), but the spec says templates/tests compare against it: either conform or amend the contract.
- **templates/projects/planning/task/detail.html:80 — "Add a dependency" links to `dep_create?project=<pk>`, but `dep_create` only reads `?predecessor=` / `?successor=`** — the param is dead and the form renders empty. Fix: `?predecessor={{ obj.pk }}`.
- **views/_helpers.py:84-86,109 — forward-pass and walk-back ties break by predecessor pk order (from `order_by("predecessor_id", ...)`), not by `(sequence, id)` as the docstring (line 53) and spec claim**; only the endpoint choice (line 99) uses sequence/id. Determinism holds; fix the docstring or sort `parents` by `(sequence, id)`.
- **views/_helpers.py:71-72 — `duration()` guards `None`/0 but not a negative `duration_days`** (possible if `planned_end < planned_start` enters via a non-form path): it would flow into `best` and break the strictly-decreasing invariant the walk-back termination relies on. Fix: `max(task.duration_days or 1, 1)`.
- **views/_helpers.py:76-93 — recursion depth equals chain length**, so a ~1000-task chain 500s with RecursionError; "bounded by the node count" is true but is not protection. An iterative longest-path pass is cheap insurance.
- **views/ProjectPlanningScheduling/ProjectTasks.py:24-27 — the `rolled` docstring misstates cycle behavior**: a cycle reachable from a root re-renders its duplicated subtree up to `tree_max_depth` (the early `return` in `walk` doesn't stop the *template* recursing `node.kids`), and cycle components disconnected from a root silently vanish. Harmless (uncraftable via forms), but the comment should tell the truth.
- **views/ProjectPlanningScheduling/ProjectMilestones.py:75-92 — the tenant-admin gate on `mst_achieve` is bypassable via `mst_edit`**: `MilestoneForm` includes `status`, so any member can set `achieved` (stamping `actual_date`) or un-achieve through plain edit. Spec-compliant (spec lists `status` in the form), but the governance asymmetry deserves a decision (e.g. drop `status` from the edit form and keep verbs only).
- **apps/core/navigation.py:1716-1728 — `LIVE_LINKS["7.2"]` key order differs from the frozen spec listing** (Estimation before Sequencing). Dict equality is unaffected, but a strict order test against the contract would fail.
- **templates/projects/overview.html:56-75 — the four quick-link rows are WBS Tree/Dependencies/Milestones/Baselines, but spec line 285 freezes "Task Register, Dependencies, Milestones, Baselines"**; swap or amend the spec.
- **forms/.../ProjectTasks.py:30-37 — the cycle walk does one DB query per ancestor hop** (`node = node.parent`, up to 250 per save). Walk a preloaded dict or accept and note it.

### Verified correct

- Models vs spec (fields/choices/ordering/uniques/index names; `makemigrations --check` clean); multi-tenancy (every query tenant-scoped, `_reject_foreign` + `TenantUniqueMixin` placement); state machines (`actual_date` stamp via `update_fields`, `freeze_snapshot()` before save, one-active-per-project inside `transaction.atomic()`, frozen guards in views AND templates, audit actions ≤ 10 chars); critical-path DFS core (memoisation, cycle guard, deterministic endpoint, terminating walk-back, `node.kids` decoration); urls/packages (literal-first ordering, disjoint first segments, all re-export blocks complete, empty sub-package `__init__`s); templates (guarded L10 idiom, no unguarded nullable FK in `|default:`, colour-named badges only, all `{% url %}` names exist); seeder (own guard, per-row `.save()`, children-first `--flush`, 7.1 block byte-faithful, critical chain + SS/lag/lead links present, achieved gate consistent with the stamp).

---

## 2. explorer

### Findings

- **`apps/projects/forms/ProjectPlanningScheduling/ProjectTasks.py:24` — `owner` excluded from `_reject_foreign`, contract line 90 pins it.** Evidence: code does `_reject_foreign(self, cleaned, ["project", "parent"])` with a docstring arguing Users can be tenant-less; contract says "`_reject_foreign` on `project`, `parent`, `owner`". The code's rationale matches 7.1's precedent (`ProjectForm` never re-checks `project_manager`/`executive_sponsor`), but the contract declares itself "the spec — templates and tests compare against these exact strings". Conform or amend the contract. Severity: **Minor** (deviation is deliberate and safer than the spec text).
- **`apps/core/navigation.py:1716-1728` — `LIVE_LINKS["7.2"]` key order differs from the frozen listing.** Contract lists WBS → Sequencing → Estimation → Milestone → Baseline → Task Register; code places "Duration & Effort Estimation" before "Task Sequencing & Dependency Mapping". All six label→url pairs are byte-exact; only order drifts. A strict order-equality test against the contract would fail. Severity: **Minor**.
- **`templates/projects/overview.html:56-59` — first quick-link row is "WBS Tree", contract line 285 pins "Task Register".** The other three rows match; aggregate keys all match. Severity: **Minor** (literal drift on one pinned label).
- **`seed_projects.py` flush block — delete order `ScheduleBaseline, TaskDependency, ProjectMilestone, ProjectTask`; contract lists `ScheduleBaseline, ProjectMilestone, TaskDependency, ProjectTask`.** No FK exists between TaskDependency and ProjectMilestone, so the swap is functionally inert — literal drift only. Severity: **Minor**.
- **`seed_projects.py` `_planning()` — baselines seeded for 2 of 3 projects; contract says all 3 get "1 active frozen BSL- baseline + 1 what_if".** Active project: baseline (active, backdated to the kickoff acknowledgement) + what_if; chartered: what_if only; draft: none, with an in-code rationale ("you don't freeze a plan for a project whose charter isn't approved"). Deliberate, documented improvement over the seeded-shape sketch. Severity: **Minor** (amend the contract or the seed).
- **`apps/projects/views/_helpers.py:1-9` — module docstring stale after adding `critical_path_ids`.** Still reads "These three are each shared by more than one of 7.1's registers" (now four helpers). Fix the docstring, not the location (contract mandates the placement). Severity: **Minor**.
- **No committed tests for 7.2** — contract pins the `planning` subslug (`planning_*` fixtures, `_planning_*` helpers, `test_planning_*` tests) but `apps/projects/tests/` has only 7.1 files. Same finding as lane 1, restated for the consistency record. Severity: **Minor** (queued step 5c).
- **`ScheduleBaselines.py:74-81` + `forms/.../ScheduleBaselines.py:14` — contract tension: `BaselineForm` includes `baseline_type`, so `bsl_edit` can flip a `what_if` into a frozen `baseline` without the freeze machinery, while the contract frames `bsl_promote` as the only what_if→baseline transition.** The verbs themselves conform exactly; lane 1 carries the full behavioral analysis (Important). Consistency impact: "what_if rows edit freely" and promote-verb exclusivity can't both hold while the field is editable. Severity: **Important** (tracked under lane 1's finding).

### Verified aligned

- **Bullet coverage:** all five `### 7.2` NavERP.md bullets have a live model + page(s) + LIVE_LINKS entry (WBS→`tsk_tree`; Sequencing→`dep_list` + `critical_path_ids`; Estimation→`tsk_list?node_type=work_package`; Milestones→`mst_list` + `mst_achieve`; Baselines→`bsl_list` + verbs), plus the extra "Task Register" leaf.
- **Contract conformance:** 13 pinned values checked — index names, `related_name="planned_project_tasks"`, the literal `tasks/tree/` route first in its module, all 23 url names/paths, verb gates + ≤10-char audit actions, all 13 template paths, tree context keys + `node.kids` decoration, choice machine values, `unique_together` sets, migration `0003`, prefixes TSK/DEP/MST/BSL, list/form context keys, overview count keys — all pass except the drifts above.
- **Convention conformance:** package layout (empty sub-package inits, top-level re-exports, absolute imports), template shape, url stems, admin shape, seeder guard style (per-row `.save()`, children-first `--flush`), `?query=` deep-link nav convention — all match 7.1 and the peer apps.
- **Spine reuse / naming collisions:** clean. Four novel tables, string FKs, no cross-app module-level imports; no pre-existing `ProjectTask`/`WbsNode`/`TaskDependency`/`ScheduleBaseline`; `crm.CrmMilestone` and `procurement.ContractMilestone` neither shadowed nor shadowing; no reverse-accessor clash on `projects.Project`/`ProjectTask`/User; scope guard honored (no money, no risk rows, no timesheets, no FileFields).
- **Cross-module contract:** nothing blocks 7.3 (resource booking over `node_type="work_package"`, free related_name space, derived `duration_days` usable for capacity math) or 7.8 (additive execution columns on `ProjectTask`).

---

## 3. frontend-reviewer

### Critical

None. No template 500 risks, no broken `{% url %}` targets, no missing CSRF tokens, no off-system classes or invalid icon names.

### Important

- **`templates/projects/planning/milestone/detail.html:11-15` and `templates/projects/planning/schedulebaseline/detail.html:11-19` — tenant-admin-gated verb buttons are rendered unconditionally, violating the 7.1 precedent.** `mst_achieve`, `bsl_promote` and `bsl_activate` are all `@tenant_admin_required` in the views, but the templates gate them only on object state, never on the user. 7.1 explicitly establishes the opposite idiom — `templates/projects/initiation/project/detail.html:25-31` wraps Approve Charter in `{% if request.user.is_superuser or request.user.is_tenant_admin %}` ("rendering it to an ordinary member is a button that answers 403"). Fix: wrap the three `<form>` blocks in the same guard.
- **`templates/projects/planning/task/detail.html:80` — "Add a dependency" deep-link passes a parameter nothing consumes, and lands the user on a form whose two task dropdowns are project-unscoped.** The link is `dep_create?project={{ obj.project_id }}`, but `dep_create` reads only `?predecessor=` / `?successor=`, and `TaskDependencyForm.fields` has no `project` — predecessor and successor selects list every task of every project in the tenant, and a cross-project pair is only caught at `clean()` as a validation bounce. Fix: point the link at `?predecessor={{ obj.pk }}`; consider also scoping the two task querysets when `?project=` is present.

### Minor

- **`templates/projects/planning/task/tree.html:20` — the project selector has no `aria-label`.** Every control in the four list filter-bars is labelled, but the tree's `onchange`-submitting select is unlabelled (the hrm tree it mirrors has the same gap). Fix: `aria-label="Project"`.
- **`templates/projects/overview.html:57-75` — quick-link rows drift from the frozen spec and leave the flat Task Register unreachable from the page body.** Contract pins "Task Register, Dependencies, Milestones, Baselines"; the template ships WBS Tree / Dependencies / Milestones / Baselines. Fix: swap the WBS Tree row for Task Register, or amend the contract.
- **`templates/projects/planning/schedulebaseline/form.html:23` — the help text contradicts the form's own editable `baseline_type` field.** The note promises "a what-if scenario stays editable until you promote it", yet the same page renders `baseline_type` as a live select — exactly lane 1's Important backend finding, visible as UI copy the form refutes. Fix the form field per lane 1; once `baseline_type` is pinned on edit, this text becomes true.
- **All four detail pages use bare `<dt>/<dd>` inside `dl.detail-grid`, the variant the stylesheet does not style** (`theme.css` scopes its dt/dd treatments to `.detail-item dt/dd`). This is the dominant house pattern and byte-matches the 7.1 sibling — flagging once so a future cleanup picks one pattern app-wide.
- **`templates/projects/planning/task/tree.html:43-45` — the "no projects" empty state says "Create a project first" without a link.** Add `<a href="{% url 'projects:prj_create' %}">`.

### Verified correct

- Design-system classes: every class used exists in theme.css (layout, cards, filter-bar, table-wrap, empty-state, form-grid, detail-grid, form-actions, btn variants, fw-600/text-muted, tree-node/tree-children); inline styles replicate the 7.1/hrm idioms exactly.
- Badges: only the six colour-named variants; status→colour maps follow 7.1 semantics; `badge-slate` WBS codes a sensible first use in this app.
- Stat grid 7→11: new cards use only the five allowed stat-icon colours and valid icons; auto-fit grid wraps cleanly; counts wired 1:1 with Overview.py.
- Icons: every `data-lucide` value verified present in the actual lucide v1.43.0 UMD bundle. No invented names.
- URLs: all `{% url %}` targets resolve against the 23 planning names + 7.1 modules. No dead targets.
- Accessibility/destructive actions: aria-labels on list filters, csrf + accurate confirm() on every destructive POST, task delete copy matches the real cascade semantics.
- WBS tree include: bounded recursion, walks `node.kids` (never `children.all`), rollup display tolerates unset attributes.
- Form rendering: the 7.1 generic loop verbatim, with useful per-entity copy.
- State-machine reflections match the views exactly (achieve button vs the view's refusals; Edit/Delete hidden exactly when `is_frozen`; Promote/Activate conditions; boolean select works via crud_list's stringified-boolean mapping).
- Contract invariants: no nullable FK inside `|default:`, empty states actionable, colspans match, pagination included on all four lists, block titles on all 14.

---

## 4. performance-reviewer

Verdict: **no Critical findings** — no N+1 anywhere, no unpaginated list, no aggregate-in-a-loop. One house-precedent violation (Important) plus hygiene items.

### Critical

None found. Cleared: every list routes through `crud_list` (filters before Paginator); the tree renders from one prefetched list with decorated instances on `node.kids` (no related-manager reads in any planning-template loop); overview and seeder follow their documented query budgets.

### Important

- **I-1. Unused `select_related` hops on the two hottest list views — the exact pattern 7.1 measured and removed.** `ProjectTasks.py:73` `tsk_list` selects `parent`, but `task/list.html` never renders `obj.parent` (3 joins, 84 columns/row; the parent join drags a full second row incl. `description` for nothing). `ProjectMilestones.py:18` `mst_list` selects `anchor_task`, never rendered by `milestone/list.html`. At 15 rows/page the cost is small, but it is precisely the mistake 7.1 quantified and fixed (`ProjectRequests.py:22-27` comment). Fix: drop `"parent"` from `tsk_list` and `"anchor_task"` from `mst_list` (detail views use theirs legitimately — keep those).

### Minor

- **M-1. tsk_detail: three chained joins nothing renders** — `child_tasks.select_related("owner")` (child table renders no owner), `predecessor_links.select_related("predecessor__project")` / `successor_links.select_related("successor__project")` (link tables render no project column; the predecessor hop re-fetches `obj` itself). Prune for hygiene under the same precedent.
- **M-2. Default orderings all filesort; 7.1's 0002 added `(tenant,-created_at)` indexes to its four models, 0003 adds none for DEP/BSL; MST orders `(target_date,id)` unindexed; TSK `(project_id,sequence,id)` only prefix-covered.** Argued ~zero at plausible scale (sub-ms filesort of tens-to-hundreds rows). App-wide decision, not a 7.2 fork: `-created_at` without a tenant+created_at index is the app-wide norm; only 7.1 opted out. Either add the four indexes in a 0004 or accept the app-wide norm — don't fix one model only.
- **M-3. Tree page fetches the task table twice** — `critical_path_ids` re-queries work packages though `_decorate_wbs` already loaded every node (measured: 3 queries where 2 would do). Pass the nodes in when a second consumer appears. Nit: tree fetch drags `description` the template never renders (`.only` would prune; single-consumer template makes it safe but low value).
- **M-4. `freeze_snapshot()` loads full model rows to compute three scalars** — one `project.tasks.aggregate(Max/Count/Sum)` is a single round trip and matches house rule 5. Cold path (verbs + 3 seeder calls).
- **M-5. `critical_path_ids` recursion depth is bounded by the recursion limit, not just node count** — a ~950-task linear chain would hit `sys.getrecursionlimit()`. Safe at tens-to-hundreds; convert to an explicit stack if 7.16 ever feeds it a whole tenant.
- **M-6. Recursive include render cost — measured:** seeded 11-node tree ≈ 6-7 ms/render; the `tree_max_depth=5` cap bounds rendering at 121 nodes ≈ 60-80 ms regardless of total WBS size; unbounded parts O(V) sub-ms. Page stays flat at scale; no action.

### Verified correct

- List-view FK audit column-by-column: `dep_list`/`bsl_list` join exactly what renders (7.1 pruning precedent applied properly); all detail views match their templates.
- `_decorate_wbs`: one query for the whole tree; `node.kids` decoration correct AND zero extra queries; children_of/walk/rollups O(V); cycle → skipped node, not stack overflow. Template per-row work query-free (`duration_days` pure date math on loaded columns; rollups computed once in the view).
- `critical_path_ids`: shared memo → O(V+E) total, 2 SQL queries, deterministic; seeded project yields the intended 6-task chain.
- Pagination & counts: filters before Paginator, `count()` not `len()`, nothing lists a queryset to count it; child/link collections sliced `[:50]`.
- Overview's 8 queries fine (6 spans 6 tables — cannot share without UNION hacks).
- Seeder 7.2 block: exactly 2 queries/row (index-backed next_number + INSERT), single transaction, no per-row audit logs or FK dereference surprises.
- Filter index coverage: TSK/MST/BSL/DEP indexes serve the view filters, the sibling-deactivation UPDATE, and both `tsk_detail` link sides; unindexed facets are low-cardinality.

---

## 5. qa-smoke-tester

Runtime verification against dev DB (migrated + seeded), in-process test client, harness `temp/smoke_72_qa.py` (gitignored, not committed). Final run: **101/102 checks passed; 1 failed = F1 below; 0 source files touched; all throwaway rows deleted and seeded state restored.**

### Verified

- **Seeded render sweep (L8 content asserts):** all 16 sub-module URLs + overview → 200 as admin_acme with real seeded content (TSK/DEP/MST/BSL rows, "Finish-to-Start", frozen `badge badge-green`); WBS tree shows wbs_code badges (`1`, `1.1`), `>Critical<`, deliverable rollups, project picker with `?project=` selection; no `{#` / `{% comment` leaks.
- **CRUD round-trips** (row counts restored): task create→detail (TSK- number)→edit→search→delete→404; dependency create/edit(lag −3)/delete; milestone create→achieve (stamped exactly once)→re-achieve refused→edit back to planned clears actual_date→delete.
- **Baseline machinery:** what_if born without snapshot/inactive; activate-on-what_if refused; what_if editable; promote flips type + writes snapshot (11 / 2026-11-23 / 668.00 = live aggregates) + activates + deactivates the old active; frozen edit AND delete POSTs refused with message, row survives; born-frozen create snapshots and takes over.
- **Validation guards:** date-order error; cross-project dep endpoints error; self-dependency error; parent=own-descendant error with parent unchanged; cross-tenant crafted POST → field error, no row.
- **Tenancy:** 404 on all 15 Globex pk probes (detail/edit/delete ×4 entities + 3 verbs), rows untouched; superuser sees empty registers, zero leaks; junk enums/pks/pages all 200 with register intact.
- **Pagination:** with 39 tasks, page 2 renders rows + "Showing 16–30 of 39" + windowed links; page 3 too.
- **Sidebar:** 7.2 shows all five bullets + Task Register; all 11 `/projects/…` hrefs resolve 200.

### Findings

- **F1 — Important: a task can be nested under a parent from a *different project*, making it invisible in every WBS tree.** Repro: POST tsk_create with Acme project A + parent in Acme project B → 302, row created; the task renders in NEITHER project's tree (`_decorate_wbs` walks per-project tasks; the node is neither root nor rendered child). Same root cause as lane 1's Critical (missing `parent.project == project` check in `TaskForm.clean`/model clean). Expected: field error on `parent`, no row.
- **F2 — Minor (informational, layered defense): `_reject_foreign` is a dead second layer for FK pks on creates** — TenantModelForm's queryset scoping rejects a foreign pk first ("Select a valid choice."), so the "That record belongs to another workspace." message is unreachable on that vector. Security outcome identical (no row, field error).
- **F3 — Minor (housekeeping): pre-existing seeded-state drift on Acme from the earlier verb smoke run** (`temp/smoke_72_verbs.py` promoted BSL-00002 and achieved MST-00003 on Acme only). Not a seed bug; noted so the Acme/Globex asymmetry isn't misread.

---

---

## 6. security-reviewer

**No Critical findings.** Every list/detail/verb query is tenant-scoped, all state-change verbs are POST-only and admin-gated at the view, and there is no cross-tenant read or write path. The three Important findings are gate-integrity issues (the tenant-admin gate bypassable through ungated paths) plus one unescaped-JS-context interpolation. (Re-appended verbatim: a later rewrite of this file dropped the lane; the consolidated triage below always carried its findings.)

### Critical

None.

### Important

- **I-1. `BaselineForm` exposes `baseline_type` on edit — a member can "freeze" a row without `bsl_promote`, bypassing `@tenant_admin_required` and voiding the snapshot promise.** `forms/ProjectPlanningScheduling/ScheduleBaselines.py:14` + login-only `bsl_edit`. A crafted POST with `baseline_type=baseline` freezes the row directly: no `frozen_on`/snapshot, audit says `update` not `promote`, the row becomes permanently un-editable/un-deletable, and `bsl_activate` (which only checks `baseline_type != "baseline"`) can later activate this evidence-less row as the baseline 7.1's kickoff attestation points to. Fix: type immutable once created (field error on change). [Fixed as I1.]
- **I-2. `MilestoneForm` exposes `status` — a member can achieve a milestone (even a cancelled one) through the ungated `mst_edit`, bypassing `mst_achieve`'s admin gate and its state guards.** Fix: drop `status` from the form (7.1 excludes verb-driven status). [Fixed as I2.]
- **I-3. Stored XSS in the Activate confirm dialog — `obj.project.name` interpolated into an `onsubmit` JS string (`schedulebaseline/detail.html:16`).** HTML attribute-escaping does not protect the JS string context (entities decode before the JS engine compiles the handler); `project.name` is member-writable and even an innocent apostrophe kills the button. Fix: interpolate only `obj.number`. [Fixed as I3.]

### Minor

- **M-1. Gated verbs offered to non-admins — 403 buttons** (deviation from 7.1's explicit `{% if request.user.is_superuser or request.user.is_tenant_admin %}` template gating). [Fixed as I4.]
- **M-2. Unbounded recursion in `critical_path_ids` and the WBS decoration — member-triggerable tenant-wide self-DoS** (~1000 chained nodes → RecursionError on every tree visit until rows are removed). Fix: explicit-stack iteration with hard caps. [Fixed as M1/M2.]
- **M-3. `TaskForm` cycle walk costs up to 250 lazy FK queries per edit POST** — bounded but member-repeatable amplification. Fix: one prefetched pk→parent_id map. [Fixed as M3.]
- **M-4. `ScheduleBaselineAdmin` leaves `is_active` and `baseline_type` directly editable** — flips without the atomic deactivate-siblings routine. Fix: `readonly_fields`. [Fixed as M9.]

### Verified correct

- **Tenant isolation (IDOR):** all four lists filter `tenant=request.tenant`; all details/verbs use `get_object_or_404(..., tenant=request.tenant)` (incl. the pre-fetches in the baseline views and `mst_achieve`); `tsk_tree` resolves `?project=` through `projects(request.tenant)` — a foreign pk falls back to the tenant's own project, no leak, no enumeration signal; `critical_path_ids`/`freeze_snapshot` transitively scoped; `as_db_int` guards the GET pk.
- **FK surfaces:** `TenantModelForm` scopes every tenant-stamped ModelChoiceField; `_reject_foreign` re-checks `project`/`parent`/`predecessor`/`successor`/`anchor_task`; `owner` deliberately relies on queryset scoping (tenant-less superuser is a legitimate pick) — matches 7.1's `project_manager` treatment.
- **Verb/CSRF safety:** no state mutation reachable via GET (creates/edits mutate only in the POST branch; deletes and all three verbs are `@require_POST`, `crud_delete` self-defending); `{% csrf_token %}` on every inline POST form.
- **Auth split:** achieve/activate/promote `@tenant_admin_required`, plain CRUD login-only — coherent per the contract, except the two form-level bypasses above.
- **Mass assignment:** `tenant`/`number`/`created_by` never in a form; `actual_date`, snapshot columns and `is_active` excluded; `number` stamped by `TenantNumbered.save()` with collision retry.
- **Audit:** actions ≤10 chars with verb detail in `changes`; no 7.2 field name intersects `_SENSITIVE_AUDIT_FIELDS`; refusal messages leak no data.
- **XSS surface:** no `|safe`/`mark_safe`/`autoescape off`/user-data inline styles; all other `confirm()` interpolations are system-generated numbers only.
- **Admin surface:** all four ModelAdmins show the `tenant` column, `list_select_related`, no `raw_id_fields`.
- **LIVE_LINKS/seed:** `?node_type=work_package` is an enum-validated filter over the tenant's own rows; `--flush` is management-command-only with documented scope; per-tenant seed guard; children-first delete order.

# Consolidated triage (authoritative fix list)

Deduped across the six lanes; Critical → Important → Minor; IDs are the fix order. Cross-lane
duplicates are folded into one item with the lanes that raised it.

## Critical

- [x] **C1 — A task can be nested under a parent from another project and silently vanishes from every WBS tree.** (code-reviewer Critical; qa F1.) `TaskForm.clean` checks tenant + cycles only; no `parent.project == project` check exists at model level either. Reproduced: cross-project POST → 302, row created, renders in neither tree. Fix in `apps/projects/models/ProjectPlanningScheduling/ProjectTasks.py::clean` (covers form + admin + any non-form path): when both `parent_id` and `project_id` are set and they disagree, `raise ValidationError({"parent": ...})` mirroring the milestone anchor_task guard.

## Important

- [x] **I1 — `BaselineForm` exposes `baseline_type` on edit: a member can "freeze" a what-if without the gated `bsl_promote`, producing an evidence-less frozen row (no snapshot, audit says `update` not `promote`) that even `bsl_activate` will later accept.** (code-reviewer; explorer; frontend M (form copy contradicted); security I-1.) Fix in `forms/ProjectPlanningScheduling/ScheduleBaselines.py`: once `self.instance.pk` exists, a changed `baseline_type` is a field error ("type is fixed — promote a what-if instead of editing it"); 7.1 precedent: verb-driven fields are excluded/locked on edit.
- [x] **I2 — `MilestoneForm` exposes `status`: a member achieves a milestone (even a cancelled one) through the ungated `mst_edit`, bypassing `mst_achieve`'s tenant-admin gate and state guards — gate and guards are decorative.** (code-reviewer M; security I-2.) Fix: drop `"status"` from `MilestoneForm.fields` (7.1 excludes verb-driven status from `ProjectRequestForm`); `mst_achieve` stays the only path. `TaskForm` keeping `status` is correct (planning state, not gated).
- [x] **I3 — Stored XSS in the Activate confirm dialog: `{{ obj.project.name }}` interpolated into an `onsubmit` JS string in `schedulebaseline/detail.html:16`.** (security I-3.) HTML escaping does not protect the JS string context (entities decode before the JS engine compiles the handler); `project.name` is member-writable, and even an apostrophe kills the button. Fix: drop the name from the message — interpolate only `obj.number` (system-generated), matching every other confirm in the changeset.
- [x] **I4 — Tenant-admin-gated verb buttons render for members (403 buttons): Mark Achieved (milestone detail) and Promote/Activate (baseline detail).** (frontend Important; security M-1.) Fix: wrap each form in `{% if request.user.is_superuser or request.user.is_tenant_admin %}` exactly like 7.1's kickoff/project detail templates, with the why-comment.
- [x] **I5 — Task detail's "Add a dependency" links `dep_create?project=<pk>`, a parameter nothing consumes; the dependency form's task dropdowns are then unscoped.** (code-reviewer M; frontend Important.) Fix: link `?predecessor={{ obj.pk }}` (consumed by the view). Scoping the two task dropdowns by project dynamically is REJECTED for this pass (needs JS chaining; the model clean error catches cross-project pairs) — note it as accepted UX debt.
- [x] **I6 — Unused `select_related` hops on the two hottest lists: `tsk_list` selects `parent` (never rendered), `mst_list` selects `anchor_task` (never rendered)** — the exact pattern 7.1 measured and pruned (84 columns/row on the task register). (performance I-1.) Fix: drop `"parent"` from the `tsk_list` queryset and `"anchor_task"` from `mst_list`; keep both on the detail views where they render.
- [~] skipped — out of the fixer's scope; tests are the next pipeline step. **I7 — No committed tests for 7.2.** NOT a code-fixer item: tests are Step 5c of this pipeline, queued after the fixer, and must pin the state guards, cycle guards, critical path, tenancy and this triage's fixes (`test_planning_*` naming, `planning_*` fixtures).

## Minor

- [x] **M1 — `critical_path_ids` hardening + determinism (perf M-5/M-3 nit; security M-2; code-reviewer Ms):** (a) `duration()` must floor at 1 (`max(task.duration_days or 1, 1)`) so a negative duration can't break the walk-back's decreasing invariant; (b) forward-pass and walk-back tie-breaks must be by `(sequence, id)` as the docstring claims — sort candidate predecessors instead of relying on the dep queryset's pk order; (c) convert the memoised DFS to an ITERATIVE pass (explicit stack / Kahn ordering) with a hard hop cap so a ~1000-task chain cannot RecursionError the tree page; (d) make the docstring's cycle/simplification notes match the implementation exactly.
- [x] **M2 — `_decorate_wbs` walk → iterative with a hard depth cap (security M-2):** template recursion is capped at 5 but the Python `walk` is not; a deep parent chain is a member-triggerable 500. Convert to an explicit stack, cap depth (skip beyond cap, mark nothing), and fix the `rolled` docstring to describe real cycle behavior (duplicate subtree re-render up to the cap; disconnected cycle components vanish).
- [x] **M3 — TaskForm cycle walk does up to 250 lazy FK queries per POST** (code-reviewer M; security M-3). Fix while doing M1/M2: collect `parent_id`s in a Python loop over a prefetched `{pk: parent_id}` map (one query) instead of `node = node.parent` per hop.
- [x] **M4 — `freeze_snapshot()` loads full rows for three scalars** (perf M-4). Fix: one `aggregate(Max("planned_end"), Count("pk"), Sum("effort_hours"))`; keep the q2 clamp semantics.
- [x] **M5 — `LIVE_LINKS["7.2"]` order vs NavERP.md/contract:** move "Task Sequencing & Dependency Mapping" before "Duration & Effort Estimation" in `apps/core/navigation.py` (NavERP.md bullet order), then amend the contract's LIVE_LINKS block to match.
- [x] **M6 — Overview quick-links:** swap the "WBS Tree" row for a "Task Register" row (contract-pinned; the flat register is currently unreachable from the page body). WBS Tree stays reachable via the sidebar and the task register's button.
- [x] **M7 — `tree.html`: add `aria-label="Project"` to the project selector; link "Create a project first" to `projects:prj_create` in the empty state.** (frontend Ms.)
- [x] **M8 — `views/_helpers.py` module docstring stale ("These three")** — update for the fourth helper.
- [x] **M9 — `ScheduleBaselineAdmin` allows editing `is_active`/`baseline_type` in Django admin, bypassing the atomic deactivate-siblings invariant** (security M-4). Fix: add both to `readonly_fields`.
- [x] **M10 — Contract amendments to match as-built decisions** (explorer Ms; main session): (a) TaskForm `_reject_foreign` list is `project`/`parent` only — `owner` deliberately follows 7.1's User-FK precedent (contract line ~90 says owner; fix the contract); (b) seeded shape: active project carries the frozen baseline + what-if, chartered a what-if only, draft none (contract said all three); (c) flush delete order `ScheduleBaseline, TaskDependency, ProjectMilestone, ProjectTask`; (d) quick-links rows are Task Register/Dependencies/Milestones/Baselines; (e) LIVE_LINKS order after M5.
- [~] skipped — recorded, no action required (as triaged). **M11 — Recorded, no action:** qa F2 (queryset scoping rejects foreign pks before `_reject_foreign` — layered defense intact); qa F3 (demo-data drift from the earlier verb smoke run — demo data; the fixer pass re-ran `seed_projects --flush`, which restores the pristine seeded shape); frontend's bare `dl.detail-grid` note (app-wide pattern, 7.1-identical); the `description`-TextField drag on the tree fetch (single-consumer template).

## Already fixed during the build (before review)

- `node.kids` decoration instead of `node.children.all` (prefetch-distinct-objects trap, found in smoke).

## Fix order

C1 → I1 → I2 → I3 → I4 → I5 → I6 → M1..M10 (M11 recorded). One file per commit; verify each fix
(`venv\Scripts\python.exe manage.py check` + targeted re-probe) before marking `[x] fixed`.
I7 (tests) is explicitly out of the fixer's scope — it is the next pipeline step.

## Fixer pass

2026-09-10. Every ID applied, verified with `manage.py check` + a throwaway probe under temp/
(run with the Django test client, all probe rows cleaned up), one source file per commit.
`makemigrations --check --dry-run` clean after C1/I1/I2 and again at the end; `seed_projects
--flush` re-run before the final smoke to restore the pristine seeded shape (also resolves qa
F3's drift).

- **C1** — `ProjectTask.clean` now raises `ValidationError({"parent": ...})` when `parent_id` and
  `project_id` disagree (mirrors the milestone anchor_task guard); probe proved model clean +
  form POST reject a cross-project parent and a same-project parent still saves. Commit `d0c85a47`.
- **I1** — `BaselineForm.clean` locks `baseline_type` on edit (field error "A row's type is fixed
  — promote a what-if scenario instead of editing it."); probe proved a member's crafted type-flip
  POST re-renders with the error and mints no snapshot evidence, while a plain what-if edit still
  302s. Commit `d9b38d65`.
- **I2** — dropped `status` from `MilestoneForm.fields` (status moves only through the gated
  `mst_achieve`); probe proved a member's `mst_edit` POST carrying `status=achieved` leaves the
  row untouched and admin edits still succeed. Commit `c929c2e7`.
- **I3** — Activate confirm now interpolates only `obj.number`
  ("Make baseline {{ obj.number }} the active baseline? …"), no project name in the JS string;
  probe asserted the exact rendered confirm text. Commit `8bd69c5f`.
- **I4** — Mark-Achieved (milestone detail) and Promote/Activate (baseline detail) wrapped in
  `{% if request.user.is_superuser or request.user.is_tenant_admin %}` with a why-comment
  mirroring 7.1's kickoff template; Edit stays login-only. Probe proved admin sees all buttons,
  member sees none but keeps Edit. Commits `9b9bbe14` (milestone) + `aee18a16` (baseline).
- **I5** — task detail's Add-a-dependency link now carries `?predecessor={{ obj.pk }}` (consumed
  by dep_create; the two unscoped dropdowns stay accepted UX debt per the triage); probe followed
  the link and asserted the predecessor pre-selected. Commit `6200ac13`.
- **I6** — dropped `"parent"` from `tsk_list` and `"anchor_task"` from `mst_list` select_related
  (detail views keep them); probe asserted no self-join in the list SQL and both lists/details
  still render. Commits `b641eaae` (tsk_list) + `25dec791` (mst_list).
- **M1** — `critical_path_ids` rewritten: iterative longest-path in Kahn topological order with a
  processed-count cap (cycle nodes and their downstream never resolve and are skipped),
  `duration` floored at `max(duration_days or 1, 1)`, predecessors sorted once by
  `(sequence, id)` and consumed in that order by both the forward pass and the walk-back;
  docstring rewritten to match. Probe: seeded chain unchanged, tie-break picks lowest
  (sequence, id), inverted dates floor to 1, cycle island skipped, all-cyclic plan → empty set,
  1100-node chain computes without RecursionError. Commit `ea8b4e86`.
- **M2** — `_decorate_wbs` walk converted to an iterative post-order over an explicit stack with
  `WBS_MAX_DEPTH = 20` (nodes beyond the cap stay undecorated and out of the kids chains); the
  `rolled` docstring now states the real cycle behavior (a cycle reachable from a root would
  re-render its duplicated subtree only up to the template's tree_max_depth cap; disconnected
  cycle components are absent — with a single parent FK a loop is never root-reachable, and the
  probe proved a looped component detaches gracefully). All decoration attribute names kept.
  Commit `9e771ef2`.
- **M3** — TaskForm cycle walk now runs over a `{pk: parent_id}` map built with ONE
  tenant-scoped query for the project instead of `node.parent` per hop (250-hop cap kept);
  probe proved a 60-deep descendant-parent is still rejected with 2 task-table queries total
  (was ~60) and upward re-parents still succeed. Commit `e198d136`.
- **M4** — `freeze_snapshot` is one `aggregate(Max("planned_end"), Count("pk"),
  Sum("effort_hours"))` with the q2 clamp kept; `Max`/`Count` added to the `_base` import list.
  Probe proved one query and values identical to the old row-load semantics (undated tasks count
  but don't move the finish; all-undated → NULL finish, 0.00 effort). Commits `ff91e352` (_base)
  + `0b1c77f8` (model).
- **M5** — `LIVE_LINKS["7.2"]` order now matches NavERP.md: Task Sequencing before Duration &
  Effort Estimation, comment kept attached. Commit `e298693a`.
- **M6** — overview body quick-links now lead with the Task Register row ("Every WBS node as a
  flat, filterable register."); WBS Tree stays on the sidebar. Commit `0710a575`.
- **M7** — `tree.html` project selector gained `aria-label="Project"` and the empty state links
  "Create a project first" to `projects:prj_create`; probe rendered both states (tenant-less
  superuser for the empty one, cleaned up). Commit `8ecca3f5`.
- **M8** — `_helpers.py` module docstring describes the four helpers (three dropdown builders +
  the critical-path helper) and keeps the single-consumer rule. Commit `b2c0e06d`.
- **M9** — `baseline_type` and `is_active` added to `ScheduleBaselineAdmin.readonly_fields` (with
  the why-comment); probe asserted neither renders an editable input on the admin change form.
  Commit `f7b507b3`.
- **M10** — contract amended to as-built: TaskForm `_reject_foreign` = project/parent only
  (owner deliberately excluded, cycle guard described), ProjectTask `clean()` parent-same-project
  added, MilestoneForm fields without `status`, BaselineForm baseline_type locked on edit,
  seeded shape restated stage-by-stage (active = full plan incl. frozen baseline + what-if;
  chartered = what-if only; draft = none) with the flush order `ScheduleBaseline,
  TaskDependency, ProjectMilestone, ProjectTask`, helpers bullet rewritten for the iterative
  passes, LIVE_LINKS block / quick-link rows / `kids` bullet verified already correct. Commit
  `ec74dc54`.
- **M11** — no action, as triaged (F3's drift resolved as a side effect of the pre-smoke
  re-seed).

Final verification: `manage.py check` clean; `makemigrations --check --dry-run` — no changes;
temp/smoke_72.py — ALL 7.2 SMOKE CHECKS PASSED (its overview needle updated from "WBS Tree" to
"Task Register" to match M6's contract-pinned rows); temp/smoke_72_verbs.py — all checks pass
(it re-mutates Acme demo data by design: promote/activate/achieve). I7 (tests) remains the next
pipeline step.
