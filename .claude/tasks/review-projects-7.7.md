# REVIEW — NavERP 7.7 Scope & Requirements Management (`projects`)

Six serial lanes over the 7.7 changeset: **code-reviewer → explorer → frontend-reviewer →
performance-reviewer → qa-smoke-tester → security-reviewer**. All six are read-only; `qa-smoke-tester`
is the only one that touches the DB and is overridden to *report, not fix*.

**Changeset.** 7.7 was built in earlier sessions and is fully committed, so the review is scoped to the
**7.7 file set**, not `BASE...HEAD` (HEAD has since advanced through the 7.6 build and its fix pass):

* `apps/projects/{models,forms,views,urls}/ScopeRequirements/` — 4 entity modules + `ScopeMatrix.py`
  (views/urls only) + the six `__init__.py`s
* `templates/projects/scope/` — 4 entity folders × `{list,detail,form}.html` + `scope_matrix.html`
* Wire-up: the `# --- 7.7` blocks in the four layer `__init__.py`s, `views/_helpers.py` (`requirements()`),
  `admin.py` (4 registrations), `seed_projects.py` (`_scope` block + `--flush` deletes),
  `apps/core/navigation.py` (`LIVE_LINKS["7.7"]`), `templates/projects/overview.html` +
  `views/ProjectInitiation/Overview.py` (7.7 quick links/counts).

**Spec.** `.claude/tasks/contract-projects-7.7.md` (frozen 2026-09-11, `BASE 08d91a7d`) is the contract;
`.claude/skills/projects/SKILL.md` and `.claude/CLAUDE.md` carry the module conventions.

---

## Lane 1 — `code-reviewer`

Status: **done**. Findings below in the lane's own ID space; deduped IDs assigned at the end of §6.

### Critical

**C1 — `ScopeItem.STATUS_CHOICES` is missing `violated` (contract §2.2)**
`apps/projects/models/ScopeRequirements/ScopeItems.py:33-38` declares only
`open/validated/realized/retired`. The contract pins five values including `("violated", "Violated")`.
Not cosmetic: `is_locked` (line 104-106) is `status in ("realized", "retired")` while the contract pins
`("realized","retired","violated")`. A `violated` row — the state where an assumption failed or a
constraint broke — cannot exist, cannot be filtered (`crud_list`'s enum allow-list drops the unknown
value), and if seeded would be editable/deletable, defeating the evidence model. Fix: add the tuple,
extend `is_locked`, and generate the follow-on migration.

**C2 — admin-gated verbs answer GET with **403**, not 405 — decorator order puts the role check
before the method check**
`Requirements.py:154-156, 174-176, 217-219`; `ScopeChangeRequests.py:140-142, 158-160, 178-180`;
`ScopeVerifications.py:136-138, 162-164`. The stack is `@login_required` / `@tenant_admin_required` /
`@require_POST`, so `require_POST` sits **innermost** and `tenant_admin_required` runs first. Verified
empirically (probe `temp/probe_77_verbs.py`, member vs admin GET):

```
route                memberGET  adminGET
req_approve          403        405
req_reject           403        405
req_verify           403        405
req_submit           405        405      <- member-level verbs are correct
sci_validate         405        405
scr_review           403        405
scr_approve          403        405
scr_reject           403        405
svr_reject           403        405
svr_waive            403        405
```

Eight admin-gated routes leak a role signal (403) for a method that should be refused outright (405).
Fix: reorder to `@login_required` / `@require_POST` / `@tenant_admin_required` on all **nine** admin-gated
verbs (`req_approve`, `req_reject`, `req_verify`, `scr_review`, `scr_approve`, `scr_reject`, `svr_reject`,
`svr_waive`).

> **House-wide note for the fixer.** 7.4 uses the *identical* order (`views/CostManagement/BudgetRevisions.py`,
> `ProjectExpenses.py`) and its `test_cost_security.py:246` only GETs as the **admin** client, so its 405
> assertion passed while the member-403 path was never probed. This is a module-wide pattern, not a 7.7
> regression. Ruling for this run: **fix 7.7 to the correct order**, and record the 7.1–7.5 siblings as a
> follow-up (do not sweep them in this close-out — the changeset is 7.7).

### Important

**I1 — detail templates ignore the pinned unbound form context keys (L7/L8)**
Contract pins `rejection_form` + `verification_form` (`Requirements.py:108-109`), `outcome_form`
(`ScopeItems.py:83`), `decision_form` (`ScopeChangeRequests.py:96`, `ScopeVerifications.py:86`). No
detail template consumes them — `grep` for those names in `templates/projects/scope/*/detail.html`
returns nothing; the templates hand-roll raw `<form>` + `<textarea name=...>` instead. The views are
correct as written; the keys are dead context. Classic L7/L8 latent blank that renders 200 and no smoke
test catches. Fix: wire the pinned form objects into the four detail templates (the contract-faithful
fix), or drop the keys — prefer wiring.

**I2 — `Requirement.elicitation_method` is `max_length=20`, contract pins 16**
`Requirements.py:102-103` vs contract line 79. Harmless at runtime and the code value is the *safer*
one (`document_analysis` is 17 chars — 16 would truncate), so the contract is what's wrong. Fix: correct
the contract to 20.

**I3 — `sci_retire` gate is looser than `sci_realize`**
`ScopeItems.py:159` refuses only `status == "retired"`, so `sci_retire` can fire from `realized` — the
contract §4.2 pins it open/validated → retired. Fix: gate on `obj.is_open` (matching `sci_realize`),
with the already-retired case as the informational no-op.

### Minor

**M1 — `RequirementAdmin.list_select_related` includes `parent`, never rendered in `list_display`**
`apps/projects/admin.py` — harmless over-fetch. No action required beyond noting it.

**M2 — `MAX_MATRIX_ROWS = 40` is undocumented and silently truncates**
`ScopeMatrix.py:43`. The contract caps only `work_packages` (12) and the gap lists (25); the coverage
counters are computed over the full queryset (correct), so only rendered rows are limited. A large
project shows a truncated matrix with no "showing N of M" line (the work-package side has one). Fix:
add the row-count note to `scope_matrix.html`, or pin the cap in the contract.

**M3 — no finding.** `navigation.py:1789-1799` carries all five verbatim sidebar keys plus the extra
`Requirement Approval Queue` leaf, matching contract §6/§7.

### Lane 1 summary

Structurally sound: all 4 models, 9 forms and 37 views import and resolve, every contract context key is
either passed-and-consumed or passed-and-dead, the derived lenses are correctly pre-scoped as queryset
filters (never as `filters=` specs), `as_db_int` guards every int GET, and every verb captures `previous`
before mutating with a `{"verb","from","to"}` payload inside the 10-char allow-list. Two genuine defects
bookend it — C1 (a missing lifecycle state that silently unlocks its rows) and C2 (decorator order
turning a 405 into a role-leaking 403 on eight routes) — plus I1 (five pinned form keys no template
reads), I3 (a re-retire path the contract forbids) and I2 (a benign contract/code width disagreement).
No re-export missing, no dead import, no stale `7.6` residue; admin satisfies §9.

---

## Lane 2 — `explorer` (architectural placement, boundaries, dead weight)

Status: **done**. Verdict: **architecturally clean** — boundary discipline, package layout, template
structure, seeder shape and navigation wiring all conform. No Critical in this lane.

Boundary discipline verified: `models/ScopeRequirements/` declares **exactly four** classes
(`Requirement`, `ScopeItem`, `ScopeChangeRequest`, `ScopeVerification`) and migration `0007` has exactly
four `CreateModel` ops. No neighbour model was edited for 7.7 (the only neighbour file a 7.7 commit
touched — `ProjectInitiation/Overview.py` — got a purely **additive** read-only count-card diff). Every
cross-module link is a one-line string FK into its owner (`projects.ProjectRisk`, `projects.ProjectTask`,
`core.Party`); 7.7 re-declares none of them. `ScopeChangeRequest.cost_impact` is sizing-only — **no 7.4
model is imported, mutated or seeded** by any 7.7 view/form/`_scope` block. No 7.6/7.9/7.10/7.16/7.17
store was built (the `quality`/`document`/`workflow` greps are docstring prose only).

Reuse verified: views import `crud_*`/`tenant_admin_required`/`write_audit_log` from `views/_common`;
forms pull `_reject_foreign`/`TenantModelForm`/`TenantUniqueMixin` from `forms/_common` — nothing
re-implemented. `_helpers.py` gained **exactly one** builder, `requirements(tenant)`.
`ScopeMatrix.py` is computed-only (no snapshot table, no chart library, no `<canvas>`/`<script>`).
Package layout lines up one-to-one (`ScopeItems.py` in all four layers; `ScopeMatrix.py` correctly in
views+urls only); imports are absolute; no `*_advanced.py` sidecar. Templates follow
`scope/<entity>/<page>.html` with no flat duplicates and no stray sub-module-root copy.
`LIVE_LINKS["7.7"]` sits immediately after `"7.5"`, leaves `"7.6"` untouched, and **all six targets
reverse-resolve** with the `?status=submitted` leaf well-formed. All 37 routes are concatenated; all 13
templates are rendered.

### Important

**I4 — `seed_projects.py` command help and `--flush` help under-report what gets wiped**
`seed_projects.py:195` — the command `help` lists only "7.1 Initiation, 7.2 Planning, 7.3 Resourcing,
7.4 Cost & Budget" (stops before 7.5 and 7.7). `:200-204` — the `--flush` help enumerates the deleted
tables but ends at "budget revisions … requests", omitting **all of 7.5's** tables *and* 7.7's four.
The code below it does delete them (`ScopeVerification → ScopeChangeRequest → ScopeItem → Requirement`
at lines 210-213, then the 7.5 trio). *Why it matters:* the help text is the operator's only contract
for a destructive flag that drops **every tenant's** rows; under-reporting it is a real trap. *Fix:*
extend both strings to name the 7.5 and 7.7 models in the children-first order the code already uses.

**I5 — `sci_retire` gate (second-angle confirmation of Lane 1's I3)**
`views/ScopeRequirements/ScopeItems.py:159` guards only `if obj.status == "retired"`, so a **realized**
item can be retired — rewriting its `outcome` and `closed_at` — while `sci_realize:136` correctly refuses
a non-`is_open` row. The model's own `is_locked` treats realized as closed evidence, so the verb
contradicts its model. Same defect as Lane 1's I3; **deduped at §6**, kept here as corroboration.

### Minor

**M4 — the four `ScopeRequirements/__init__.py` docstrings describe a transient build state that no
longer holds.** All four (models/forms/views/urls) read *"Intentionally EMPTY: the package's public
surface is the top-level `__init__.py` re-export block, **added in the Integrate step**"* — but Integrate
is long done and the top-level `__init__.py`s are populated. *Why it matters:* a future reader or agent
treats it as live guidance and may "helpfully" move re-exports back down, inverting the convention.
*Fix:* reword to a static statement of the convention, without the stale tense.

**M5 — `timezone`/`Decimal`/`MinValueValidator` reach the entity modules only via the star-import.**
e.g. `ScopeItems.py:69,113` (`timezone.localdate()`), `ScopeChangeRequests.py:63,88`. This is the
project's pinned idiom (contract §1) and every sibling module does it, so **no action** — recorded as
an accepted convention, noted only because star-imports hide the dependency from linters.

### Lane 2 summary

The 7.7 layer sits exactly where it should: four own tables, one-line string FKs outward, no neighbour
store touched, no 7.4 write, no reinvention of the `crud_*` toolkit. Re-export completeness, absolute
imports, template folders, seeder guard + children-first flush order, and the six nav targets were all
verified against live code, not the ERD. The only substantive items are stale `--flush`/command help
that under-reports a destructive flag (I4) and the `sci_retire` gate already filed by Lane 1 (I5).
