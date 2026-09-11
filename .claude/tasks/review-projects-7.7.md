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

---

## Lane 3 — `frontend-reviewer` (templates, design system)

Status: **done**. Then verified the lane's own findings against live code before filing (see the
per-finding "Verified" notes).

### Critical

**C3 — `scopechange/detail.html:42` renders `{{ obj.HIGH_COST }}`, which resolves to nothing — the
materiality threshold prints blank into visible prose.**
Line 42: `<dd>{{ obj.cost_impact }} <span class="text-muted">(material at {{ obj.HIGH_COST }} or
above)</span></dd>`. `HIGH_COST` is a **class-level constant** on `ScopeChangeRequest`
(`ScopeChangeRequests.py:63`), not an instance field — Django's variable resolution fails on it and
substitutes the empty string, so the CCB's evidence panel reads *"(material at  or above)"*. The very
line that exists to state the threshold states nothing.
*Verified:* `grep -n HIGH_COST templates/.../scopechange/detail.html` → only line 42; no `high_cost`
key is passed by `scr_detail`. *Fix:* pass `{"high_cost": ScopeChangeRequest.HIGH_COST}` from
`scr_detail` and render `{{ high_cost }}`, or hard-code `50,000`. (Passing it from the view is the
cleaner fix — a new context key must also be pinned in the contract.)

### Important

**I6 — `requirement/list.html` never offers an elicitation-method filter, though the view passes
`method_choices` and the column is displayed.**
`req_list` puts `method_choices` in `extra_context` (contract §4.1 pins it) and `list.html:81` shows
the technique column, but `grep -c method_choices` on the template returns **0** and the view's
`filters` list (`Requirements.py:51-55`) has no `elicitation_method` entry. So the register's stated
premise ("what captured it") is unfilterable.
*Verified:* grep 0; the view's filters are `project, requirement_type, priority, status, owner`.
*Fix:* either drop `method_choices` from the view's `extra_context`, or add
`("elicitation_method", "elicitation_method", False)` to `filters` and a matching `<select>` to the
template. (L11: the value is an allow-list choice, so the ORM lookup is safe as a plain field filter.)

**I7 — `scope_matrix.html` never consumes the pinned `creep_max` key.**
`grep -c creep_max` on the template returns **0**; `ScopeMatrix.py:173` passes it and contract §4.5
pins it. Nothing renders wrong — the bars use `row.bar_pct`, which the view already computed against
`creep_max` — so this is a dead pinned key, not a visual defect.
*Verified:* grep 0. *Fix:* render it (e.g. "largest month: {{ creep_max }}") or drop it from the
context and the contract.

### Minor

**M6 — `scope_matrix.html:47` "showing N of M" note does not state the 12-column cap.**
The note appears only under `{% if project %}` and reports rows, not the truncated work-package
columns. The column header falls back to `title="{{ wp.name }}"` (a native tooltip) for the identity
of a capped-out column. *Fix:* widen the note to include the column truncation. (Overlaps Lane 1's M2,
which is about the row cap — deduped to one item at §6.)

**M7 — the same badge colour carries three meanings across the four registers.**
`badge-amber` encodes MoSCoW "Should Have" (`requirement/list.html:84`), priority "High"
(`scopechange/list.html:80`) and the computed "Untraced" state (`requirement/list.html:88`). Not a
contract breach (the computed-state badges are exempt from the `get_*_display` fallback rule) and every
class used is in the theme.css allow-list — purely cosmetic. No fix required.

### Categories checked and EMPTY (recorded so the coverage isn't inferred as "not looked at")

* **Badge-class validity (L33)** — **clean.** Every class emitted by the 13 templates is in the
  theme.css allow-list: only `badge-green/amber/red/info/muted/slate` plus
  `badge-{{ obj.badge_class }}` (whose source is each model's `STATUS_BANDS`, all valid values). No
  `-success`/`-warning`/`-danger`. Stat-icon colours used are all six that exist.
* **L10 nullable-FK-in-`|default:`** — **clean.** Zero occurrences; every nullable FK
  (`owner`, `requested_by`, `inspected_by`, `source_party`, `accepted_by`, `parent`, `requirement`,
  `risk`, `wbs_node`) renders via `{% if fk %}…{% else %}—{% endif %}`.
* **L2 multi-line comments** — **clean.** `grep '{#'` across all 13 templates returns zero matches;
  every note uses `{% comment %}…{% endcomment %}`.
* **List-page CRUD completeness + filter-param drift** — **clean.** All four lists have the full
  `.page-header`/breadcrumb, GET filter form with `q` bound, `.table-wrap`/`.table` + Actions column
  (eye/pencil/delete POST + csrf + `confirm()`), pagination include and `.empty-state`. Every filter
  `name=` matches the view's `filters` tuples and the derived lenses; no drift found.
* **`scope_matrix` GET-only + no chart library + no snapshot** — **clean** apart from I7.
* **Empty/zero states** — **clean.** `{% empty %}` on every loop; `bar_pct`/`coverage_pct` are
  view-computed and 0-safe, so no template-side division.
* **`overview.html` 7.7 additions** — **clean.** The five quick links resolve to live `projects:` names
  and all five count cards (`requirement_count`, `untraced_count`, `scope_change_count`,
  `pending_change_count`, `pending_verification_count`) are keys `Overview.py:104-111` actually passes.

### Lane 3 rulings on items the lane itself raised, and the orchestrator's correction

* **The lane's "C2" (ScopeItem detail offers Realize/Retire from `open`) is NOT a defect — downgraded
  to no-action.** Verified against `scopeitem/detail.html:52-73` and `ScopeItems.py:110-172`: the
  template gates Validate on `status == 'open'` and offers Realize/Retire whenever the row is not
  locked, which is exactly the model's `is_open` contract (`open` **or** `validated`), and the page
  carries copy that says so in as many words ("Realizing records that it came to pass; retiring
  records that it no longer applies. Both close the row"). `sci_realize` accepts `open` by design.
  The lane's own text contradicted its heading; the template is correct. The **one** real
  ScopeItem defect remains Lane 1's I3 (`sci_retire` accepts `realized`, which `is_open` excludes).
* **Corroboration on the filed L7/L8 finding (Lane 1 I1) — the severity is confirmed *dead key*, not
  silent no-op.** The lane checked every hand-rolled verb form's POST field name against its form
  class and all five match (`reason`, `note`, `outcome`, `decision_note`, `note`), so the verbs bind
  and store correctly. The pinned unbound `*_form` objects are a wasted object and a missing CSS
  hook, not a broken transition. No new ID; Lane 1's I1 stands as written.
* **The lane's "I1" (widget classes not asserted by templates) is not a finding** — `{{ field }}` with
  `_common.py` widget attrs is the house pattern across 7.1–7.5. No action.

### Lane 3 summary

Mechanically the 13 templates are in good shape: badge classes are all in the allow-list, no nullable
FK sits in a `|default:`, no multi-line comment leaks, the four lists carry the full CRUD action set
with working filters, and `overview.html`'s new cards consume keys the view really passes. The one
genuine visual bug is **C3** — `{{ obj.HIGH_COST }}` printing blank into the CCB's materiality line.
The remaining items are dead pinned context keys (`method_choices`, `creep_max`) and two cosmetic
notes. The lane's headline "Critical" about the ScopeItem lifecycle buttons was checked against the
code and **withdrawn** — the template matches the model's contract and documents it in copy.

---

## Lane 4 — `performance-reviewer` (measured query counts)

Status: **done**. Measured, not guessed: `CaptureQueriesContext` under `--nomigrations` (L49), 16 seeded
rows per register (per_page+1 so a second page exists), then re-run at 40/100/300 rows to test for growth.

### Measured table

| Route | Queries | Grows with rows? |
|---|---:|---|
| `req_list` | 11 | **flat** (11 at 16/40/100/300 rows) |
| `sci_list` | 11 | flat |
| `scr_list` | 11 | flat |
| `svr_list` | 11 | flat |
| `req_list?untraced=1` | 11 | flat |
| `req_list?pending=1` | 11 | flat |
| `req_list?verified=1` | 10 | flat |
| `sci_list?boundaries=1` | 10 | flat |
| `sci_list?open=1` | 11 | flat |
| `scr_list?pending=1` | 11 | flat |
| `scr_list?high_impact=1` | 10 | flat |
| `svr_list?pending=1` | 11 | flat |
| `req_detail` (children+CRs+SVRs+SCIs) | 12 | flat |
| `sci_detail` | 8 | flat |
| `scr_detail` | 8 | flat |
| `svr_detail` | 8 | flat |
| `scope_matrix?project=` | 34 | flat (34 at 30 wp / +200 SCR / +100 req) |
| `scope_matrix` (no `?project=`, tenant-wide) | 31 | flat |
| `scope_matrix` (30 work packages) | 34 | flat |

Every register holds at exactly **11 queries from 16 → 300 rows** — at or better than the 7.4 bar
(75→22 / 119→14). The pinned `select_related` lists are complete.

### Critical

None in this lane. No route — register, detail, derived lens, matrix, or tenant-wide matrix —
re-queries per row, and no cap is missing before the template.

### Important

**I8 — `scope_matrix` issues 16 unconditional `COUNT(*)` round-trips for the summary strip.**
`views/ScopeRequirements/ScopeMatrix.py:148-161`. The 34-query budget decomposes as ~5 setup
(session/user/tenant/branding/projects), 1 project, 2 work-package, 1 coverage aggregate, 2 grouped
verification counts, 3 matrix/gap SELECTs, 1 creep SELECT, **6 `scope_summary` counts (`:153-161`)**
and **10 `_rows()` counts (`:149`)** where `_rows` iterates 6 type + 4 priority choices doing one
`.count()` each. It is *flat* — safe against volume — but ten scalar tallies are ~47% of the page's
budget. *Fix:* collapse each family into one `values(field).annotate(Count("id"))` (2 queries replace
16), or drop the zero-count choices from `_rows()`.

**I9 — the `scope_matrix` creep loop materializes every approved/implemented change row unbounded.**
`ScopeMatrix.py:124-139`: `changes_qs.filter(status__in=("approved","implemented"))` has **no slice**,
unlike the two gap lists (`GAP_LIMIT=25`, `:116-119`) and the matrix rows (`MAX_MATRIX_ROWS=40`, `:107`).
Measured: 500 approved changes ⇒ 500 rows loaded in Python. The query count stays flat (one SELECT), so
this is **not** an N+1 — it is an unbounded result set (memory/CPU). Mitigating: `is_high_impact` and the
two impact columns are already-loaded scalars, so no per-row FK query. *Fix:* aggregate in the DB
(`annotate(TruncMonth(...))`) or slice a bound the way the sibling panels are capped.

### Minor

**M8 — `req_detail`'s `change_requests` slice is a superset of the contract and partly dead.**
`Requirements.py:102` pins `select_related("requested_by", "risk")` while `requirement/detail.html:135-152`
renders neither `c.risk` nor `c.requested_by`. Measured 12 queries — no cost today; the `risk` join is
dead weight (the admin's own "joined but renders in no column" rule). *Fix:* drop `risk`, or render the
risk column the join was added for.

**M9 — the creep SELECT fetches full row objects where `.values()` would do** (`ScopeMatrix.py:124`).
Folds into I9; noted only to close the category. No separate action.

### Categories checked and EMPTY

* **Unbounded queryset reaching a template** — none. All caps are applied **in the view, before render**:
  `MAX_MATRIX_COLUMNS=12` (`:77`), `MAX_MATRIX_ROWS=40` (`:107`), `GAP_LIMIT=25` (`:116-119`).
* **Per-row FK query inside a loop** — none. The `matrix_rows` loop (`:105-114`) reads
  `requirement.wbs_node_id` (free) and two pre-grouped dicts; the creep loop reads local columns only.
* **A `prefetch_related` that should have removed a query** — none. Each `req_detail` child loop
  (`child_requirements`/`change_requests`/`verifications`/`linked_scope_items`) is `select_related`ed in
  the view (`:101-107`) and costs exactly one query each.
* **Missing `select_related` on a rendered FK** — none. Every `<td>` deref in the four list templates was
  cross-checked against §4's pinned lists and matches (including `svr_list`'s `obj.requirement.number`
  and `req_list`'s `obj.wbs_node.name`).
* **A derived property dereferencing an unjoined FK** — none. `is_high_impact`, `is_traced`, `is_open`,
  `is_locked`, `is_review_overdue`, `badge_class` all read scalar columns only.

### Lane 4 summary

7.7 is performance-clean and flat: all four registers and every derived lens sit at 10–11 queries
whether the page holds 16 or 300 rows, the four detail pages at 8–12, and `scope_matrix` at 34 (31
tenant-wide) with no growth as work packages, changes or requirements increase. The view-level caps the
contract promised are genuinely applied before rendering, and no template loop dereferences an unjoined
FK. Two non-blocking budget items remain, both in `ScopeMatrix.py` — I8 (16 separate counts that two
grouped aggregates would replace) and I9 (the unbounded creep loop) — neither of which grows with row
count, so neither threatens the 7.4 bar. The temp measurement script was deleted.
