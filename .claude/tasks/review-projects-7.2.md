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
