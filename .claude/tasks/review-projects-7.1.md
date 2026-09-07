# 7.1 Project Initiation & Charter — review findings (`apps/projects`)

**Changeset:** `02519901755f71a5fbf017b97d8858d44708481d...HEAD`
**Contract:** `.claude/tasks/contract-projects-7.1.md`
**Phase 4 of the CLAUDE.md Module Creation Sequence.** Six reviewers run one after another; each
appends here. IDs are assigned after all six are in. Phase 5 (`code-fixer`) burns this down.

## Already fixed before this wave (do not re-report)

- **Four pages returned hard 500s** — a nullable FK dereferenced inside a `|default:` filter
  argument. Django resolves filter *arguments* eagerly and `string_if_invalid` only swallows
  `VariableDoesNotExist` for the *main* variable, so a NULL FK in an argument takes the page down.
  15 sites across 6 templates, fixed with the `templates/accounting` branch-guard idiom.
  Commits `08185761`..`b4b3cd81`.
- The 15 POST-only verbs answer **405** on GET (`@require_POST`) — house pattern, intentional.

---

# Consolidated triage — THE authoritative fix list

60 raw findings across six reviewers, deduped to **36**. **`code-fixer` works this list, in this
order** — the per-reviewer sections below are the evidence, not the worklist. Each row names the
reviewer findings it merges. Tick `[x] fixed` / `[~] skipped — reason` as you go; nothing may be
left `[ ] open`.

Three of these need a **migration `0002`** (I18, M14, M23) — generate **one** migration covering all
three, not three migrations.

## Critical

- [ ] **C1 — `approved` is unreachable through the UI, so `prq_convert` is dead.**
  Merges R1-I1 + R5-C1. No template posts to `prq_approve`; `ProjectRequestForm` excludes `status`,
  so nothing can reach `approved` and Convert can never render. The verb itself is correct — this is
  a wiring gap that kills the sub-module's headline chain. The smoke gate missed it because the
  seeder pre-bakes an `approved` row.
  *Fix:* add an Approve POST form to the Decision card in
  `templates/projects/initiation/projectrequest/detail.html`, gated on
  `obj.status in ProjectRequest.DECISION_STATUSES` **and** on tenant-admin (see I19).

- [ ] **C2 — `pko_complete` skips both ceremony gates and drives a project to `active` with an
  unapproved charter.** Merges R1-I3 + R3-M4 + R5-C2 + R6-F2. View gate only rejects an already
  `completed` kickoff; template offers Complete on a `planned` one. Any member can do
  `prj_create` -> `pko_create` -> Complete and the project goes live with `charter_status='draft'`,
  `charter_approved_by=None` — **routing around** the `@tenant_admin_required` on
  `prj_approve_charter`. Survives adding the auth gate; a tenant admin can trip it by accident.
  *Fix, all three parts:* require `obj.status == "held"` in the view; refuse to promote the project
  unless `project.charter_status == "approved"`; tighten the template to
  `{% if obj.status == 'held' %}`.

- [ ] **C3 — `prq_convert`'s idempotency guard is per-instance, not per-row: two concurrent POSTs
  mint two projects.** R5-C3. `convert_to_project()` checks `if self.converted_project_id` on the
  in-memory instance *before* opening `transaction.atomic()`. Two live instances produce PRJ-00004
  and PRJ-00005 for one demand; `PRQ.converted_project_id` points at the second and the first is an
  orphan nothing links to. Sequential replay is safe — this is concurrency only.
  *Fix:* `select_for_update()` re-read **inside** the atomic block, or a compare-and-swap
  `filter(pk=…, converted_project__isnull=True).update(...)`. Consider a unique constraint on
  `Project.request` (would need the 0002 migration).

## Important

- [ ] **I1 — Tenant-less users get unscoped FK dropdowns on all four create GETs (cross-tenant
  disclosure, incl. every user email).** Merges R1-I5 + R6-F1. The `request.tenant is None` guard
  sits inside `if form.is_valid():`, so a **GET** falls through to `Form(tenant=None)` and
  `TenantModelForm` leaves every FK on the default queryset. Reachable by any ordinary member whose
  tenant was deleted (`User.tenant` is `SET_NULL`), not just the superuser.
  *Fix:* hoist the guard to the first line of all four create views. Also harden
  `apps/core/forms/_common.py` to `.none()` when `tenant` is falsy. **Note the clone at
  `apps/procurement/views/DashboardPortal/ProcurementAlerts.py:82` — out of scope for 7.1; flag it,
  do not fix it here (L43).**
- [ ] **I2 — An approved charter and its signed document are rewritable while the stamp stays.**
  R6-F3. *Fix:* refuse `prj_edit` when `charter_status == "approved"` (peer pattern
  `apps/accounting/views/AccountsPayable/Bills.py:38`); gate the Edit button to match.
- [ ] **I3 — `prq_edit` mass-assigns decision evidence and rewrites an approved business case.**
  Merges R1-I4 + R6-F4. *Fix:* add `rejection_reason`, `information_requested`, `decision_notes` to
  `ProjectRequestForm.Meta.exclude`; add a status guard to `prq_edit`; **update the contract's
  exclusion list at `.claude/tasks/contract-projects-7.1.md:96-97` in the same change** or the fix
  reads as drift later.
- [ ] **I4 — `prq_return_for_information` leaves `decision`/`decided_by`/`decided_at` stamped.**
  Merges R1-M1 + R5-I1. A row renders "Needs Information" *and* "No-Go" at once; from `approved` it
  silently voids the Go. *Fix:* refuse decided statuses, or clear the decision stamps on return.
- [ ] **I5 — `prq_return_for_information` is login-only, so a non-admin can reverse a tenant admin's
  decision.** R5-I2. *Fix:* `@tenant_admin_required`.
- [ ] **I6 — `prq_reject` has no lower gate: a never-submitted `draft` gets a full decision stamp**
  (`submitted_at=None` alongside `decided_at=<now>`). R5-I3. *Fix:* gate to `DECISION_STATUSES`.
- [ ] **I7 — `pko_mark_held` skips the schedule gate and the meeting-date requirement.**
  Merges R1-M2 + R5-I5. Makes "Set a meeting date before scheduling" unenforceable.
  *Fix:* require `scheduled`.
- [ ] **I8 — `pko_mark_baseline_set` accepts a never-held kickoff, contradicting its own message.**
  Merges R1-M3 + R5-I6. *Fix:* `if obj.status in ("planned", "scheduled")`.
- [ ] **I9 — `pko_mark_baseline_set` has no UI trigger, so two rendered fields can never populate.**
  Merges R1-I2 + R5-I7. `projectkickoff/detail.html:47-48` and `list.html:66` render a permanently
  "—" baseline. *Fix:* add the POST form, shown when
  `obj.status != 'planned' and not obj.baseline_acknowledged_at`; gate it — it stamps a signature.
- [ ] **I10 — Deleting a Project strands its source request in a dead `converted` state.** R5-I8.
  `converted_project` is `SET_NULL`, so the request reads "Converted" with project "—" and **every**
  verb then refuses it; the demand is unrecoverable. The delete also CASCADEs stakeholders and
  kickoffs with no warning. *Fix:* refuse the delete while `request` is set (or reopen the request
  and clear `converted`), and name the cascade in the confirm dialog.
- [ ] **I11 — A charter can be submitted and approved on a `cancelled`/`completed` project.** R5-I9.
  *Fix:* gate both charter verbs on `status`, not just `charter_status`.
- [ ] **I12 — The audit trail records a fabricated `from` state on every verb.**
  Merges R1-I7 + R5-I10. Hard-coded `{"from": "draft"}` etc. means the immutable trail **asserts the
  gate was respected in exactly the cases where it was skipped (C2, I7)**. *Fix:* capture
  `previous = obj.status` before mutating; applies to `ProjectRequests.py:111,134,162,188` and
  `ProjectKickoffs.py:124,143,163`.
- [ ] **I13 — Non-admin members can advance the project lifecycle and delete governance rows.**
  R5-I11. The deletes match house style (287/393 delete views are login-only) — the finding is the
  **inconsistency**: 7.1 gates approve/reject/convert/approve-charter at tenant-admin while leaving
  the kickoff verbs that set `Project.status` ungated. *Fix:* gate the three kickoff verbs.
- [ ] **I14 — Return and Reject render on every status, including ones the view refuses.**
  Merges R3-I1 + R5-M2. A required-looking textarea and a red button that can never succeed.
  *Fix:* mirror the view guards in the template.
- [ ] **I15 — The signed charter document is rendered as dead text.** R3-I2.
  `project/detail.html:40` prints `Document.name` with no link — the artefact the page is named
  after is unreachable. *Fix:* the `templates/accounting/payable/bill/detail.html:43` anchor pattern.
- [ ] **I16 — `attendee_count` is a real 1+N on `pko_list` and `prj_detail` (25 queries at 15 rows
  vs 10 flat).** R4-I1. **Two traps:** you cannot annotate over the property name (data descriptor —
  `AttributeError`), so use `attendee_total`; and an aggregate over a multi-valued relation **drops
  `Meta.ordering`**, silently flipping the register out of newest-first — the explicit
  `.order_by("-created_at","-id")` is mandatory. Measured fix: 25 -> 10.
- [ ] **I17 — `prq_list` ships an 88-column, 3-JOIN row for a template that renders none of it.**
  R4-I2. *Fix:* drop the `select_related`; optionally `.only(...)` the eight rendered columns.
- [ ] **I18 — No index serves the `ordering` all four registers use** (`-created_at, -id`); every
  default register page is `Using filesort` over the tenant's whole row set. R4-I3.
  In-pattern add (20+ models already ship `["tenant","created_at"]`). **Needs migration 0002.**
- [ ] **I19 — Three tenant-admin-only buttons are rendered to every member -> hard 403.**
  Merges R1-I6 + R6-F5. *Fix:* `{% if request.user.is_superuser or request.user.is_tenant_admin %}`.

## Minor

- [ ] **M1** — the "Business Case & Feasibility" sidebar bullet deep-links `?status=assessment`, but
  no verb can reach `screening`/`assessment`, so it lands on an empty register (R1-M4). Fix with C1
  or repoint the bullet.
- [ ] **M2** — `charter_status="rejected"` is a choice no verb can set, yet `prj_submit_charter`
  accepts it as a source (R1-M5).
- [ ] **M3** — `seed_projects.py:237-238` executes a `ContentType` query and `del`s it (R1-M6).
- [ ] **M4** — `seed_projects.py:89` `projects[2]` is a hidden positional coupling (R1-M7).
- [ ] **M5** — "Plan Kickoff" renders when a kickoff already exists (R1-M8).
- [ ] **M6** — class-level `queryset=Project.objects.all()` should be `.none()` fail-closed (R1-M9).
- [ ] **M7** — contract pins `feasibility(24)`; code is `max_length=32`. Also `Project.description`
  is missing from the contract's field list (R1-M10 + smoke-gate note). Doc-only.
- [ ] **M8** — `models/__init__.py` and `forms/__init__.py` omit the `from ._base import *` /
  `from ._common import *` line both reference apps carry; a live trap for the Phase 6 tests (R2-M1).
- [ ] **M9** — `_projects(tenant)` is copy-pasted byte-identically in two entity modules; belongs in
  `views/_helpers.py` (R2-M2).
- [ ] **M10** — `data-lucide="seedling"` is not a Lucide icon (it is `sprout`); renders blank (R3-M1).
- [ ] **M11** — the extra `<div>` inside each `.stat-card` collapses the flex gap (R3-M2).
- [ ] **M12** — `badge-slate`/`badge-muted` are identical so the branch is dead weight, **and the
  live `kickoff` status has no badge branch** so a launching project looks like a draft (R3-M3).
- [ ] **M13** — bare `<th></th>` above two action columns; one action cell not wrapped in
  `.table-actions` (R3-M5).
- [ ] **M14** — two of the nine shipped indexes are dead: `pko_tnt_project_idx` duplicates the
  `unique_together` index byte-for-byte, `pst_tnt_project_idx` is its leftmost prefix (R4-M1).
  **Migration 0002.**
- [ ] **M15** — `Overview.py` uses 7 round trips for 7 stat cards; 4 is the floor (R4-M2).
- [ ] **M16** — `projectkickoff/detail.html:45` `{{ obj.attendee_count }}` re-counts rows the view
  already loaded; `{{ attending|length }}` saves a query (R4-M4).
- [ ] **M17** — `prj_list` carries two joins the template never renders (R4-M5).
- [ ] **M18** — admin changelists lack `list_select_related` (R4-M6).
- [ ] **M19** — the seeder saves each request row up to three times. **Do NOT "fix" with
  `bulk_create`** — `TenantNumbered.save()` allocates `number` and `bulk_create` bypasses it,
  shipping empty numbers (R4-M7).
- [ ] **M20** — negative `estimated_cost`/`estimated_benefit` are accepted and reach the ROI
  properties (R6-F6). NaN/Inf/huge are already correctly rejected. *Fix:* `MinValueValidator(0)`.
  **Migration 0002.**

## Recorded, no action — do NOT "fix" these

- [~] **N1 — `pst_list`'s `influence_rank` filesort** (R4-M3). The `Case/When` is the correct
  *correctness* fix (`"-influence"` sorts alphabetically wrong) and is N+1-free; making it
  index-supported needs a schema change to integer choice fields. **Not worth it at 7.1 scale** —
  recorded so the trade is explicit rather than assumed away.
- [~] **N2 — `ProjectKickoffForm` truncates the meeting time to the minute** (R5-M1). Root cause is
  the shared datetime-local widget in `apps/core/forms/_common.py` — **app-wide, not 7.1's**, and a
  shared-file change another session may be in (L43). Flag upstream, do not change it here.
- [~] **N3 — leftover `SMOKETEST Acme` tenant (pk=70, empty slug)** in the dev DB (R5-M3).
  Pre-existing from an earlier run, not this changeset. Dev-DB hygiene, not code.
- [~] **N4 — the 15 POST verbs answer 405 on GET.** House pattern (`@require_POST`, 1248 uses), a
  correct HTTP answer. Intentional.
- [~] **N5 — `.workbuddy-ai/` is untracked and not gitignored** (R6, out of scope). Belongs in
  `.gitignore`, but the files are another session's (L45) — leave them alone.
- [~] **N6 — the same unguarded `|default:` FK-argument idiom exists in ~59 sites across
  procurement/scm/hrm/crm.** Out of scope for 7.1 and a cross-module sweep risks L43 collisions;
  spun off as its own task.
- [ ] **N7 — no test suite** (R2-I3). Not a fixer item — this is **Phase 6**, which runs next.

---

## Reviewer 1 — `code-reviewer` (correctness, tenancy, structure)

> Verdict: no Critical. Tenancy, migration, spine reuse and package structure are solid —
> every queryset is tenant-scoped, `0001_initial` matches the models field-for-field, and nothing
> duplicates a spine entity. But two of the fifteen POST verbs have **no UI trigger at all**,
> leaving the headline intake -> charter chain unreachable outside the seeder.

### Important

- **[R1-I1] `prq_approve` has no trigger anywhere in the app.**
  `templates/projects/initiation/projectrequest/detail.html:12-24` — the page offers
  Submit / Convert / Edit, and the Decision card offers only Return and Reject. Since
  `prq_convert` refuses anything but `status == "approved"`
  (`apps/projects/views/ProjectInitiation/ProjectRequests.py:205`) and only `prq_approve` can
  produce that status, the go/no-go -> project chain works **only for seeder rows**.
  *Fix:* add an Approve POST form in the Decision card, shown when `obj.status` is in
  `submitted` / `screening` / `assessment`.

- **[R1-I2] `pko_mark_baseline_set` has no trigger either.**
  `templates/projects/initiation/projectkickoff/detail.html:10-27`, although lines 47-48 render
  the stamps it would set. *Fix:* add a POST form shown when
  `obj.status != 'planned' and not obj.baseline_acknowledged_at`.

- **[R1-I3] `pko_complete` lets a `planned` kickoff be completed.**
  `apps/projects/views/ProjectInitiation/ProjectKickoffs.py:152` refuses only `completed`, so a
  never-held ceremony can stamp `completed_at` and flip its project to `active` — contradicting
  the module docstring's own invariant that a project becomes active *because the ceremony was
  held*. The template offers the button for every non-completed status
  (`projectkickoff/detail.html:21`).
  *Fix:* `if obj.status != "held": messages.error(...); return redirect(...)`.

- **[R1-I4] Any tenant member can rewrite an admin's recorded rejection reason.**
  `apps/projects/forms/ProjectInitiation/ProjectRequests.py:19-25` — the exclude list omits
  `rejection_reason`, `information_requested` and `decision_notes`, so they render as editable
  fields. `prq_reject` is `@tenant_admin_required` but `prq_edit` is only `@login_required`,
  which routes around the gate. *Fix:* add the three fields to `exclude`; update the contract's
  exclusion list at `.claude/tasks/contract-projects-7.1.md:96`.

- **[R1-I5] FK dropdowns leak every workspace's rows to a `tenant=None` user.**
  `apps/projects/views/ProjectInitiation/ProjectRequests.py:51-58` (same shape in `Projects.py:38-43`,
  `ProjectStakeholders.py:55-60`, `ProjectKickoffs.py:61-66`) — the tenant guard sits *inside* the
  POST branch after `is_valid()`, whereas `crud_create` (`apps/core/crud.py:173-176`) redirects
  before the form is built. `TenantModelForm` only scopes ModelChoiceFields when `tenant is not
  None` (`apps/core/forms/_common.py:50-53`), and the middleware assigns `tenant=None` to **any**
  user whose `tenant` FK is null, not just `admin` (`apps/core/middleware.py:26`). So a GET
  renders `requested_by` / `requester_party` / `assigned_reviewer` / `assigned_approver` /
  `party` / `user` dropdowns listing every workspace's rows.
  *Fix:* hoist the `if request.tenant is None` guard to the top of each of the four views.

- **[R1-I6] Buttons offered to users who get a 403 (L32).**
  `templates/projects/initiation/projectrequest/detail.html:19` and `:104`,
  `templates/projects/initiation/project/detail.html:17` — Convert, Reject and Approve Charter
  render for every logged-in user, but those views raise `PermissionDenied` for non-admins
  (`ProjectRequests.py:117,140,195`; `Projects.py:107`).
  *Fix:* wrap each in `{% if user.is_tenant_admin or user.is_superuser %}`.

- **[R1-I7] The audit trail records a state the row was never in.**
  `apps/projects/views/ProjectInitiation/ProjectRequests.py:111` hardcodes `"from": "draft"` even
  when the source was `needs_information`; same false literal at `:134` (`"submitted"` when the
  source was `screening`/`assessment`), `:162`, `:188`, and `ProjectKickoffs.py:124,143,163`.
  *Fix:* capture `previous = obj.status` before the mutation and pass that.

### Minor

- **[R1-M1]** `ProjectRequests.py:180` — `prq_return_for_information` refuses only
  `draft`/`converted`, so an `approved`/`rejected` request can be sent back while `decision`,
  `decided_by`, `decided_at` and `rejection_reason` stay stamped; the register then shows
  "Needs Information" with a No-Go decision. *Fix:* refuse decided statuses, or clear the stamps.
- **[R1-M2]** `ProjectKickoffs.py:133` — `pko_mark_held` accepts `planned`, skipping
  `pko_schedule` and its meeting-date requirement.
- **[R1-M3]** `ProjectKickoffs.py:180-182` — the guard refuses only `planned` but the message
  reads "Hold the kickoff before acknowledging the baseline"; a merely `scheduled` kickoff passes.
  *Fix:* `if obj.status not in ("held", "completed")`.
- **[R1-M4]** `apps/core/navigation.py:1707` — the "Business Case & Feasibility" bullet deep-links
  `?status=assessment`, but no verb or form can put a request into `screening`/`assessment`/
  `deferred` (only the seeder does), so the bullet lands on an empty register on a real workspace.
  *Fix:* add the screening/assessment transitions, or point the bullet at a reachable status.
- **[R1-M5]** `models/ProjectInitiation/Projects.py:39` — `charter_status="rejected"` is a choice
  no verb can set, yet `prj_submit_charter` accepts it as a source (`Projects.py:95`).
- **[R1-M6]** `seed_projects.py:237-238` — `ct = ContentType.objects.get_for_model(Project)`
  followed by `del ct` "for symmetry" is a query executed and thrown away. Delete both lines.
- **[R1-M7]** `seed_projects.py:89` — `projects[2]` assumes `_projects()` returned three rows, but
  it returns two when `_convert()` yields `None` (`:181-192`). Unreachable today, but a hidden
  positional coupling. *Fix:* select the active project by status, not by index.
- **[R1-M8]** `templates/projects/initiation/project/detail.html:140` — "Plan Kickoff" shows even
  when a kickoff exists; `unique_together ("tenant","project")` plus `ProjectKickoffForm.__init__`
  means the form then renders with the project unselectable. *Fix:* `{% if not kickoffs %}`.
- **[R1-M9]** `forms/ProjectInitiation/ProjectStakeholders.py:18` and `ProjectKickoffs.py:13` —
  class-level `queryset=Project.objects.all()` is overwritten in every `__init__` branch, so it is
  safe today; `Project.objects.none()` is the fail-closed default.
- **[R1-M10]** `.claude/tasks/contract-projects-7.1.md:75` still pins `feasibility(24)`; the code
  is `max_length=32` with a documented `fields.E009` reason
  (`models/ProjectInitiation/ProjectRequests.py:131-133`). Doc drift, alongside the already-known
  `Project.description` omission.

### Done well

Spine reuse is exactly right and the reasoning is written down where the next person will find it:
`core.Party` / `core.OrgUnit` / `core.Document` / `core.Activity` / `crm.Opportunity` /
`accounting.Currency` all referenced **by string**, no re-declared customer/employee/currency
table, and `_common.py:20-23` documents why `accounting.Currency` is excluded from
`_reject_foreign` (its global row has no `tenant` to compare). `convert_to_project()`
(`ProjectRequests.py:200-229`) is the standout: one `transaction.atomic()`, an idempotency guard
on `converted_project_id`, both directions linked, and a `save(update_fields=...)` that cannot
re-trigger numbering. `ProjectStakeholder.get_engagement_strategy_display()` catches the
"a property has no generated `get_FOO_display`" trap before it shipped — exactly the L7 discipline
the contract exists to enforce.

---

## Reviewer 2 — `explorer` (structure, context contract)

> Verdict: **the view-context contract is CLEAN** — all 13 templates x 5 view modules match, zero
> missing keys, zero dead keys. Every `obj.<attr>` path in all 13 templates also resolves to a real
> field/property/method on the bound model (0 misses) — the second L8 vector, also clean. Template
> paths all resolve, no URL shadowing, package shape and all 39 re-exports (4 models / 5 forms /
> 30 views) conform. Two Minor findings only.
>
> Verified-good near-misses worth recording: `get_engagement_strategy_display` is read in 3
> templates and Django does *not* generate `get_FOO_display` for a property — the model hand-writes
> it (`models/ProjectInitiation/ProjectStakeholders.py:137-144`). `obj.attendee_count` resolves to
> the property at `ProjectKickoffs.py:76-77`. `influence_rank` looks dead but is consumed by
> `.order_by("-influence_rank", "id")`, not render.

### Minor

- **[R2-M1] Both reference apps re-export their shared toolkit; `projects` does not.**
  `apps/projects/models/__init__.py` omits `from ._base import *` and
  `apps/projects/forms/__init__.py` omits `from ._common import *`, which
  `apps/accounting/models/__init__.py:8`, `apps/crm/models/__init__.py:9`,
  `apps/accounting/forms/__init__.py:8` and `apps/crm/forms/__init__.py:10` all carry. So
  `from apps.projects.models import TenantNumbered` / `from apps.projects.forms import
  TenantUniqueMixin` raise `ImportError` today. Latent — nothing imports them yet — but
  `apps/crm/forms/__init__.py:8-9` documents that its own test suite depends on exactly this line,
  which makes it a live trap for the Phase 6 test-writer and for 7.2.
  *Fix:* add `from ._base import *  # noqa: F401,F403` / `from ._common import *  # noqa: F401,F403`
  by surgical `Edit` (these are shared files).

- **[R2-M2] `_projects(tenant)` is copy-pasted byte-identically across two entity modules.**
  `apps/projects/views/ProjectInitiation/ProjectStakeholders.py:17-20` and
  `.../ProjectKickoffs.py:18-21`. Backend-Package rule 5 puts a helper used by more than one module
  in `views/_helpers.py` — which already exists and already holds `org_units`/`clients`
  (`apps/projects/views/_helpers.py:13,20`) for exactly this reason. Two copies is where they drift.

### Noted, owned by Phase 6

- **[R2-I3] The app has no test suite.** `apps/projects/tests/` holds only an empty `__init__.py` —
  no `conftest.py`, no `test_initiation_*.py` (compare `apps/accounting/tests/`: conftest + 8
  modules). This is Phase 6 of the sequence and is already scheduled; recorded here so the gap is
  not mistaken for coverage.

---

## Reviewer 3 — `frontend-reviewer` (design system, templates)

> Verdict: no Critical. **theme.css discipline is clean — no L33 recurrence**: all 49 distinct
> classes across the 13 templates exist in `static/css/theme.css`, including the compound
> `btn-icon danger` and the easy-to-invent `fw-600`/`detail-grid`/`req`. Zero
> `-success/-warning/-danger` variants. Badge machine values all match real CHOICES with an
> `{% else %}` `get_<field>_display` fallback (no never-true branch). No `{#` multi-line comment
> leak. All three FK filter dropdowns use `|stringformat:"d"`, never `|slugify`, and every rendered
> dropdown is wired in the view `filters=` list. Actions columns, csrf+confirm deletes,
> `.empty-state` and `partials/pagination.html` present on all four registers. All 30 `{% url %}`
> names resolve.

### Important

- **[R3-I1] Return-for-Information and Reject render on every status, but the view refuses most.**
  `templates/projects/initiation/projectrequest/detail.html:96` and `:104`. On a `converted`
  request both bounce ("A converted request cannot be rejected — reject the project."); on an
  already-`rejected` request Reject bounces; on a `draft` request Return-for-Information bounces.
  The user sees a required-looking "Rejection reason" textarea and a red Reject button that can
  never succeed. This is a **state** guard, distinct from the role-guard finding R1-I6.
  *Fix:* mirror the view guards —
  `{% if obj.status != 'draft' and obj.status != 'needs_information' and obj.status != 'converted' %}`
  around Return, `{% if obj.status != 'rejected' and obj.status != 'converted' %}` around Reject.

- **[R3-I2] The signed charter document is rendered as dead text.**
  `templates/projects/initiation/project/detail.html:40` —
  `{{ obj.charter_document|default:"—" }}`. `charter_document` is an FK to `core.Document`, so this
  prints `Document.name` with **no way to open the file**, and no other 7.1 template references it:
  the artefact the page is named after is unreachable from the UI.
  *Fix:* use the house pattern from `templates/accounting/payable/bill/detail.html:43` —
  `{% if obj.charter_document %}<a href="{{ obj.charter_document.file.url }}" target="_blank" rel="noopener"><i data-lucide="file-text"></i> {{ obj.charter_document.name }}</a>{% else %}—{% endif %}`.

### Minor

- **[R3-M1]** `templates/projects/overview.html:56` — `data-lucide="seedling"` is not a Lucide icon
  (Lucide has **`sprout`**; `seedling` is Font Awesome). `lucide.createIcons()` silently skips
  unknown names, so this empty-state renders with a blank icon gap. *Fix:* `sprout`.
- **[R3-M2]** `templates/projects/overview.html:16-22` — each `.stat-card` wraps value+label in an
  extra `<div>`. `.stat-card` is `flex-direction:column; gap:.35rem`, so the wrapper collapses them
  into one flex child and the gap is lost. House markup is flat
  (`templates/hrm/hrm_overview.html:22`) — drop the wrapper.
- **[R3-M3]** Redundant same-colour badge branch (4 sites) **and a missing live status**.
  `.badge-slate` and `.badge-muted` are byte-identical in theme.css, so these render identically and
  the explicit branch is dead weight: `projectrequest/list.html:107` vs `:108`;
  `projectrequest/detail.html:38` vs `:39`; `project/list.html:83` vs `:85`;
  `project/detail.html:46` vs `:48`. More importantly, in `project/list.html:80-85` and
  `project/detail.html:43-48` the **`kickoff`** status — which `pko_mark_held` actually sets and
  `projectkickoff/list.html:8` advertises — has no branch, so a launching project renders the same
  grey as a `draft` one. *Fix:* add
  `{% elif obj.status == 'kickoff' %}<span class="badge badge-amber">{{ obj.get_status_display }}</span>`
  and drop the duplicate `completed`->slate branch.
- **[R3-M4]** `templates/projects/initiation/projectkickoff/detail.html:21` —
  `{% if obj.status != 'completed' %}` puts *Complete* on screen for a brand-new `planned` kickoff,
  so all three verbs appear at once and a user can close out a meeting that was never scheduled.
  *Fix:* `{% if obj.status == 'held' %}`. (Pairs with R1-I3, which fixes the view side.)
- **[R3-M5]** Empty table headers / unwrapped action cell. `templates/projects/overview.html:30` and
  `templates/projects/initiation/project/detail.html:116` end with a bare `<th></th>` above an
  action column — a screen reader announces a nameless column; the house shape
  `<th class="table-actions">Actions</th>` is used 559x elsewhere. Relatedly
  `project/detail.html:130` is the only action cell in the sub-module not wrapped in
  `<div class="table-actions">`, so its eye icon left-aligns under a right-aligned header.

---

## Reviewer 4 — `performance-reviewer` (ORM / query efficiency)

> Method: Django test `Client` as `admin_acme` with `CaptureQueriesContext` against the live dev DB,
> plus a 25-project / 27-kickoff / 106-stakeholder probe inserted and **rolled back** to measure a
> full 15-row page, plus `EXPLAIN` and `SHOW INDEX` on all four tables. Framework baseline is ~7
> queries, so a clean list lands at ~10.
>
> Measured at seeded volume: overview **14**, prq_list 10, prj_list 11, pst_list 10, pko_list **12**;
> prq_detail 9, prj_detail 11, pst_detail 8, pko_detail 12.
> Measured at a real 15-row page: **pko_list 25** (10+15), pst_list 10 flat, prj_list 11 flat.
> **Exactly one N+1 exists in the sub-module.** No Critical.

### Important

- **[R4-I1] `attendee_count` is a genuine 1+N on `pko_list` and `prj_detail` — and the obvious fix
  silently breaks ordering.**
  `models/ProjectInitiation/ProjectKickoffs.py:76-81` runs one
  `SELECT COUNT(*) ... WHERE project_id=? AND attending_kickoff=1` per row. Measured
  **25 queries for a 15-row `pko_list` vs 10 flat**; page 2 (12 rows) = 22. Bounded at page size, so
  it does not grow with the table, but it is 15 extra round trips on every default load.
  Rendered at `projectkickoff/list.html:59`, `project/detail.html:128` (1 COUNT per kickoff),
  and `projectkickoff/detail.html:45` (single row — leave, see R4-M4).

  **Two traps the fixer must not miss.** (1) You cannot annotate over the property name — the
  `property` is a data descriptor and shadows it: `annotate(attendee_count=...)` raises
  `AttributeError: can't set attribute`. Annotate as `attendee_total` and update the two templates.
  (2) **`.order_by()` is not optional.** An aggregate over a multi-valued relation makes Django drop
  `Meta.ordering`, and the register silently flips from newest-first to arbitrary:
  `BASE ['PKO-00002','PKO-00001']` then `ANN ['PKO-00001','PKO-00002']` (no ORDER BY emitted at all)
  then `ANN + explicit .order_by("-created_at","-id")` restores it.

  *Fix* in `views/ProjectInitiation/ProjectKickoffs.py:43-44` and `Projects.py:69`:
  `.annotate(attendee_total=Count("project__stakeholders", filter=Q(project__stakeholders__attending_kickoff=True))).order_by("-created_at", "-id")`.
  Measured result: **25 to 10 queries**, values verified identical to the property.

- **[R4-I2] `prq_list` ships an 88-column, 3-JOIN row for a template that renders none of it.**
  `views/ProjectInitiation/ProjectRequests.py:23-24` does
  `.select_related("org_unit", "assigned_approver", "converted_project")`, but
  `projectrequest/list.html:85-120` renders only `title`, `number` and five `get_*_display` calls —
  **no joined column is touched anywhere on the page.** Measured `columns=88 joins=3 len=3706`;
  the `converted_project` join alone drags all eight of `Project`'s TextFields per request row.
  Trimmed: `columns=9 len=528`. Zero extra *queries* — pure payload and row-instantiation waste, on
  the highest-traffic register in the sub-module. *Fix:* delete the `select_related` entirely;
  optionally add `.only("number","title","request_type","priority","feasibility","decision","status","target_start_date")`
  (`description` is only in the WHERE, never the SELECT, so deferring is safe).

- **[R4-I3] No index serves the `ordering` all four registers actually use.**
  All four models declare `ordering = ["-created_at", "-id"]` (`ProjectRequests.py:162`,
  `Projects.py:103`, `ProjectStakeholders.py:102`, `ProjectKickoffs.py:66`) and **none of the nine
  shipped indexes contains `created_at`**. Every register page — including the unfiltered default,
  the most-requested URL — is `Using filesort`, and the sort runs over the tenant's entire row set
  before `LIMIT 15`, so page cost is O(tenant rows), not O(15).
  This is an **in-pattern add, not a fork**: `["tenant","created_at"]` already ships on 20+ models
  (`crm_lead_tenant_created_idx`, `crm_case_tenant_created_idx`, `hrm_cand_tenant_created_idx`, ...).
  *Fix:* add `models.Index(fields=["tenant","-created_at"], name="prq_tnt_created_idx")` (and
  `prj_`/`pst_`/`pko_`) to each `Meta.indexes`. **This needs a migration (0002).** A descending index
  also gives early termination on the enum-filtered variants, which is why separate
  `(tenant,priority)` / `(tenant,influence)` / `(tenant,agenda_template)` indexes are **not**
  recommended — 3-5-value enums at ~25% selectivity the optimizer will mostly ignore, pure write cost.

### Minor

- **[R4-M1] Two of the nine shipped indexes are dead** (write cost, no read benefit), confirmed from
  `SHOW INDEX`. `ProjectKickoffs.py:69` `pko_tnt_project_idx` is `(tenant_id, project_id)` —
  **byte-identical** to the index MySQL auto-created for `unique_together ("tenant","project")`.
  `ProjectStakeholders.py:110` `pst_tnt_project_idx` is the leftmost prefix of the
  `unique_together ("tenant","project","party","raci_scope")` index. Drop both. The other seven all
  back a live filter reachable from a register filter bar — good coverage.
- **[R4-M2] `Overview.py:18-26` — 7 round trips for 7 stat cards; 4 is the floor** (four tables).
  Measured **7 to 4, values identical** `(9,3,1,3,1,6,2)` using two `aggregate()` calls with
  `Count("pk", filter=Q(...))`. Worth doing — it is the module landing page, hit from every sidebar
  entry — but only a 3-query saving on a cheap page.
- **[R4-M3] `pst_list`'s `influence_rank` is correct and N+1-free but is *not* index-supported.**
  `ProjectStakeholders.py:25-34`, measured 10 queries flat at both 6 and 15 rows, and its
  `select_related("project","party","user")` is fully earned (all three render at
  `projectstakeholder/list.html:71-72`). The `Case/When` is a scalar expression so, unlike R4-I1, it
  does **not** drop ordering. But the SQL is `ORDER BY 19 DESC, id ASC` — an ordinal reference to a
  computed column no index can satisfy: 106 rows examined to return 15. The comment at
  `ProjectStakeholders.py:97-101` is right that `"-influence"` sorts alphabetically-wrong; the
  annotation is the correct *correctness* fix. Making it index-supported needs a schema change
  (store influence/interest as `PositiveSmallIntegerField` with `[(3,"High"),(2,"Medium"),(1,"Low")]`).
  **Not worth doing at 7.1 scale — recorded so the trade is explicit rather than assumed away.**
- **[R4-M4] `projectkickoff/detail.html:45` re-counts a list the view already fetched.**
  `{{ obj.attendee_count }}` fires a COUNT for the same rows `pko_detail` already loads into
  `attending` (`ProjectKickoffs.py:88-89`) and iterates at :60/:65. Change to `{{ attending|length }}`
  — **12 to 11 queries**, zero behaviour change, no view edit.
- **[R4-M5] `prj_list` carries two unused joins.** `Projects.py:16-17` selects `org_unit` and
  `executive_sponsor`; `project/list.html` renders only `client.name` (:87) and `project_manager`
  (:88). Measured `columns=73 joins=4`. Trim to `.select_related("client","project_manager")` —
  the other two are correctly kept on `prj_detail:60-62`, which does render them.
- **[R4-M6] Admin changelists have no `list_select_related`.** `apps/projects/admin.py:22-27`
  (3N) and `:30-35` (2N) on a 100-row changelist. Cold path, one-line fix.
- **[R4-M7] Seeder saves each request row up to three times.**
  `seed_projects.py:154-162`: `.save()`, then a `submitted_at` update, then a `decided_by/decided_at`
  update. Measured **261 queries / 48 rows across 2 tenants, 25 UPDATEs against 18 INSERTs**. Set
  those in the constructor kwargs before the first save (~11 fewer round trips per tenant).
  **Do NOT "fix" with `bulk_create`** — `TenantNumbered.save()` (`models/_base.py:66-75`) allocates
  `number` via `next_number()` and `bulk_create` bypasses `save()`, shipping every row with an empty
  `number`. Tidiness only; the seeder is atomic and block-guarded.

### Genuinely efficient — no action

Pagination is correct everywhere (`crud_list` applies search + filters before `Paginator`; no
`list(qs)`, `len(qs)` or `if qs:` anywhere in the app). `prq_list`/`prj_list`/`pst_list` have **no
N+1 at all** — flat 10-11 queries at 15 rows, identical to 3. `prj_detail`'s `obj.kickoffs.all()`
gets `k.project` free via `_known_related_objects`, so the missing `select_related("project")` there
is correct, not an oversight. No template double-evaluates a queryset (`{% if stakeholders %}` hits
the cache the `{% for %}` reuses — exactly one SELECT each). **No chained `__str__` FK hop (L18)**:
`Party`/`OrgUnit`/`Document.__str__` are all `self.name`, and `ProjectKickoff.__str__` to
`Project.__str__` has no second hop, so `select_related("project")` suffices. Derived money
(`roi_pct`, `risk_adjusted_benefit`, `risk_adjusted_roi_pct`, `ProjectRequests.py:175-196`) is
pure-Decimal arithmetic on loaded columns — zero queries, no stored editable balance.
`next_number()` walks the `(tenant, number)` unique index backwards and reads one row. `prj_detail`
caps stakeholders at `[:50]` with the right joins.

### For the Phase 6 test-writer

Assert **flatness**, not a magic constant (absolute counts drift with session/branding queries):
`django_assert_max_num_queries(12)` on `pko_list` at 2 rows *and* at 15 rows (fails today at 25);
same for `prj_detail` with 5 kickoffs (fails today at 15); `projects:overview` after the R4-M2
collapse (14 today). **And a regression guard for the R4-I1 ordering trap**: assert `pko_list`'s
`object_list` is still newest-first after the annotation lands — that is the one that breaks
silently if the fixer forgets `.order_by()`.

---

## Reviewer 5 — `qa-smoke-tester` (state machine + write paths, report-only)

> Method: in-process `django.test.Client(raise_request_exception=False)`, `force_login` as
> `admin_acme` / `ops_acme` / cross-tenant probes against Globex pks, everything wrapped in one
> `transaction.atomic()` and rolled back. Post-run row dump verified byte-identical to pre-run in
> every status, stamp and FK. `manage.py check` clean.
>
> **Three Critical.** This pass went past the smoke gate into the state machine, which is where the
> real defects were.

### Critical

- **[R5-C1] `approved` is unreachable through the UI, so `prq_convert` — the sub-module's headline
  verb — is dead once the two seeded rows are used.**
  `grep -rn "prq_approve" templates/` is **empty**; no template posts to
  `/projects/project-requests/<pk>/approve/`. `projectrequest/detail.html:18` renders Convert only
  under `{% if obj.status == 'approved' and not obj.converted_project_id %}`, and
  `ProjectRequestForm` excludes `status`, so `prq_edit` cannot set it either.
  *Repro:* create a request via the UI, Submit -> `status='submitted'`. The detail page now offers
  only Return, Reject, Edit, Delete. **There is no path to `approved`, therefore no path to Convert.**
  The view itself is correct — POSTed directly, `draft -> submitted -> approved -> converted` all
  302 with correct stamps. The smoke gate missed this because `seed_projects` pre-bakes `PRQ-00007`
  as `approved`. (Same defect as R1-I1; this pass proves the downstream consequence.)

- **[R5-C2] `pko_complete` skips both ceremony gates and drives a project to `active` with an
  unapproved charter — one click in the default UI.**
  View gate is only `if obj.status == "completed"`; template gate is `{% if obj.status != 'completed' %}`
  (`projectkickoff/detail.html:20`), so **Complete renders on a `planned` kickoff**.
  *Repro:* `Project(status='draft', charter_status='draft', charter_approved_at=None)` +
  `ProjectKickoff(status='planned', meeting_date=None)` — exactly what `pko_create` produces.
  `POST /projects/kickoffs/<pk>/complete/` (empty body) -> 302 "Kickoff completed — … is now active."
  Resulting rows: `PKO status 'planned'->'completed', completed_at=<now>, meeting_date=None`;
  `PRJ status 'draft'->'active', charter_status='draft', charter_approved_at=None`.
  A project reaches **Active** with no submitted charter, no scheduled meeting, no held ceremony.
  Note the asymmetry: `pko_schedule` refuses without a `meeting_date`, and that guard is bypassed
  simply by clicking Complete instead of Schedule.

- **[R5-C3] The `prq_convert` idempotency guard is per-*instance*, not per-row: two concurrent POSTs
  mint two projects.**
  Sequential replay **is** safe (verified: 2nd POST refused, project count 4->4). But
  `ProjectRequest.convert_to_project()` checks `if self.converted_project_id: return None` on the
  **in-memory instance** and only *then* opens `transaction.atomic()`; the view's guard has the same
  shape, and each concurrent request gets its own `get_object_or_404` instance.
  *Deterministic repro* (two live instances = two simultaneous requests):
  `a = ProjectRequest.objects.get(pk=X); b = ProjectRequest.objects.get(pk=X)` ->
  `a.convert_to_project(user)` gives `PRJ-00004`, `b.convert_to_project(user)` gives `PRJ-00005`
  because b's guard reads b's stale `None`.
  Result: acme project count `3 -> 5` for one demand. `PRQ.converted_project_id` points at the
  **second** project; `PRJ-00004.source_requests == []` while
  `PRJ-00005.source_requests == ['PRQ-00011']` — the two FKs diverge and PRJ-00004 is an orphan
  nothing links to from the register.
  *Fix:* `select_for_update()` re-read **inside** the atomic block, or a compare-and-swap
  `filter(pk=…, converted_project__isnull=True).update(...)`, and/or a unique constraint on
  `Project.request`.

### Important

- **[R5-I1] `prq_return_for_information` accepts a decided row and leaves the decision stamped.**
  Gate blocks only `needs_information`/`draft`/`converted`.
  *From `rejected`:* start `status='rejected', decision='no_go', decided_by=2, decided_at=…,
  rejection_reason='not viable'`; `POST /…/<pk>/return/` `reason=send me the numbers` -> 302.
  Row becomes `status='needs_information'` (renders "Needs Information", `badge-amber`) **and**
  `decision='no_go'` ("No-Go") **and** `decided_by`/`decided_at` still stamped. `?decision=no_go` on
  the register returns a row whose Status column reads "Needs Information", and the detail page
  shows the No-Go block and the Information-requested block simultaneously.
  *From `approved`:* same POST leaves `decision='go'` intact while the row displays as awaiting
  information — and it is no longer convertible (Convert needs `status=='approved'`), so **the Go
  decision is silently voided.** The template renders this form unconditionally
  (`projectrequest/detail.html:96`, no `{% if %}`).

- **[R5-I2] `prq_return_for_information` is `@login_required` only, so a non-admin can reverse a
  tenant admin's decision.** `prq_approve` / `prq_reject` / `prq_convert` / `prj_approve_charter`
  correctly 403 for `ops_acme`; this one does not: as `ops_acme`,
  `POST /projects/project-requests/<pk>/return/` on a `submitted` row -> **302**,
  `status 'submitted'->'needs_information'`. Combined with R5-I1, a plain member can do this to an
  `approved` row and void the admin's Go.

- **[R5-I3] `prq_reject` has no lower gate: a never-submitted `draft` can be rejected with a full
  decision stamp.** Gate blocks only `rejected`/`converted`; `prq_approve` by contrast requires
  `DECISION_STATUSES`. *Repro:* fresh `status='draft', submitted_at=None`; `POST /…/<pk>/reject/`
  `reason=no budget` -> 302. Row: `status='rejected', decision='no_go', decided_by=2,
  decided_at=<now>, rejection_reason='no budget'`, **`submitted_at=None`** — a formal decision on a
  request never submitted for one.

- **[R5-I4] Stale decision fields survive re-submission and re-decision.**
  Chain via POSTs: `rejected` -> return -> submit -> approve. After `prq_submit`:
  `status='submitted'` but `decision='no_go'`, `decided_by=2`, `rejection_reason='not viable'`.
  After `prq_approve`: `status='approved'`, `decision='go'`, but **`rejection_reason='not viable'`
  remains** — the detail page renders "Rejection reason: not viable" under an Approved/Go header.
  Same class: `prq_reject` on an `approved` row flips `decision 'go'->'no_go'` leaving no trace a Go
  was ever recorded.

- **[R5-I5] `pko_mark_held` skips the schedule gate and the meeting-date requirement.**
  Gate is `if obj.status in ("held","completed")`, so `planned` passes. *Repro:*
  `PKO(status='planned', meeting_date=None)`, `PRJ(status='draft')` -> `POST /…/mark-held/` -> 302,
  `PKO.status='held'` with `meeting_date=None`, `PRJ.status 'draft'->'kickoff'`. The template offers
  the button on `planned`, so this is the designed path — which makes "Set a meeting date before
  scheduling" unenforceable.

- **[R5-I6] `pko_mark_baseline_set` accepts a never-held kickoff, contradicting its own message.**
  Gate is `if obj.status == "planned"` — `scheduled` is not blocked. *Repro:*
  `PKO(status='scheduled', meeting_date=<future>)`, never held -> `POST /…/baseline/` -> 302
  "Baseline acknowledged.", `baseline_acknowledged_at=<now>, baseline_acknowledged_by=2`.
  Should be `if obj.status in ("planned", "scheduled")`.

- **[R5-I7] `pko_mark_baseline_set` has no UI trigger, so two rendered fields can never be
  populated.** `grep -rn "pko_mark_baseline_set" templates/` is empty, yet
  `projectkickoff/detail.html:47-48` render "Baseline acknowledged" / "Acknowledged by" and
  `projectkickoff/list.html:66` renders a Baseline column — permanently "—" except on the seeder's
  pre-stamped `PKO-00001`. Also login-only, so once wired **any member can sign the acknowledgement**
  (an evidence field). (Overlaps R1-I2.)

- **[R5-I8] Deleting a Project strands its source request in a dead `converted` state and cascades
  silently.** `prj_delete` has no guard for `request`/`stakeholders`/`kickoffs`;
  `ProjectRequest.converted_project` is `SET_NULL`. *Repro:* convert PRQ -> PRJ, then
  `POST /projects/projects/<prj>/delete/` -> 302 "Deleted successfully." Request row is now
  `status='converted', converted_project_id=None` — detail shows Status "Converted" with Converted
  project "—". **Every verb then refuses it:** submit ("already converted"), approve ("this one is
  converted"), reject ("reject the project" — the project is gone), return ("cannot be sent back"),
  convert ("Only an approved request can be converted"). The row can only be edited or deleted; the
  demand is **permanently unrecoverable**. The delete also CASCADEs `ProjectStakeholder` +
  `ProjectKickoff` with no warning in the confirm dialog.

- **[R5-I9] A charter can be submitted and approved on a `cancelled`/`completed` project.**
  `prj_submit_charter` gates on `charter_status`, never on `status`. *Repro:*
  `PRJ(status='cancelled', charter_status='rejected')` -> submit-charter 302 -> approve-charter 302
  "Charter approved — … is chartered." Row: `status='cancelled'` **and** `charter_status='approved'`,
  `charter_approved_by=2`, `charter_approved_at=<now>` — a green Approved charter on a cancelled
  project, and the success message claims it "is chartered" while `status` was left alone.

- **[R5-I10] The audit trail records a fabricated `from` state on every verb.** Every
  `write_audit_log(..., changes={"from": <literal>})` hard-codes the source state. Observed:
  `needs_information -> submitted` logged as `{'from':'draft'}`; `screening -> approved` logged as
  `{'from':'submitted'}`; `planned -> completed` logged as `{'from':'held'}`.
  **The immutable trail therefore asserts the gate was respected in exactly the cases where it was
  skipped (R5-C2 / R5-I5).** *Fix:* capture `previous = obj.status` before mutating. (Same root as
  R1-I7; this pass shows why it matters.)

- **[R5-I11] Non-admin members can advance the project lifecycle and delete governance rows.**
  As `ops_acme` (`is_tenant_admin=False`): `pko_mark_held` 302 (project -> kickoff), `pko_complete`
  302 (project -> active), `pko_mark_baseline_set` 302 (`baseline_acknowledged_by=ops_acme`),
  `prq_delete` 302 **row deleted** (a `submitted` request), `prj_delete` 302 **row deleted** (a
  project with a submitted charter).
  *Calibration:* 287 of 393 delete views app-wide are login-only, so the deletes match house style —
  but 7.1 gates approve/reject/convert/approve-charter at tenant-admin while leaving the kickoff
  verbs that set `Project.status` ungated. That inconsistency is the finding.

### Minor

- **[R5-M1]** `ProjectKickoffForm` round-trip truncates the meeting time: GET edit, re-POST
  unchanged -> `meeting_date 2026-09-14 16:48:25.279341+00:00 -> 2026-09-14 16:48:00+00:00`. Root
  cause is the shared datetime-local widget format `%Y-%m-%dT%H:%M` in
  `apps/core/forms/_common.py` — **app-wide, not 7.1-specific**. The other three forms round-trip
  byte-clean.
- **[R5-M2]** Reject and Return-for-Information render unconditionally on the request detail page,
  so the UI offers them on `draft` and `converted` rows. (Overlaps R3-I1.)
- **[R5-M3]** Leftover tenant `SMOKETEST Acme` (pk=70, `slug=''`) with users `admin_`/`ops_`/`sales_`
  is in the dev DB from an earlier run; `seed_projects` prints a skip line for it every time.
  **Pre-existing, not from this pass.**

### Verified correct (no action needed)

**Happy path** end to end — `prq_create -> submit -> approve -> convert -> submit-charter ->
approve-charter -> pko_create -> schedule -> mark-held -> complete -> baseline` — all 302 with
correct stamps and correct project-status side effects. **Replay:** all 10 verbs POSTed twice; every
second POST refused with a message and **zero** field deltas — including `prq_convert` (no second
project) and the evidence-stamping `prj_approve_charter` / `pko_mark_baseline_set`, which correctly
refuse to overwrite the first approver. **`convert_to_project` mapping** verified field-by-field
(`title->name`, `description`, `org_unit`, `requester_party->client`,
`assigned_approver->executive_sponsor`, `target_start_date->start_date`, `target_end_date->end_date`,
`request` back-pointer, `created_by`) — nothing else copied. **Backwards transitions refused** with a
message and no write. **Form round-trip** byte-clean on `ProjectRequestForm`, `ProjectForm`,
`ProjectStakeholderForm`. **Excluded/system fields cannot be POSTed** on any create or edit form —
injected `tenant=<globex>`, `number='HACKED-…'`, `status`, `decision`, `decided_by/at`,
`submitted_at`, `converted_project`, `created_by`, `charter_status`, `charter_approved_by/at`,
`request`, `completed_at`, `baseline_acknowledged_by/at`, `id`/`pk`: every one ignored, zero delta.
**Cross-tenant writes:** 19 POST probes against Globex pks as `admin_acme` -> **all 404**, Globex
counts unchanged, zero rows mutated. **Cross-tenant FK smuggling rejected on all four forms**, create
and edit, with same-tenant controls proving the test is not vacuous; rejection comes from
`TenantModelForm`'s queryset scoping, with `_reject_foreign` as a never-firing second layer. Global
`accounting.Currency` still accepted (L29 respected).

### Suggested fix order

R5-C1 (wire Approve) -> R5-C2 (`pko_complete` requires `held`) -> R5-C3 (`select_for_update` in
`convert_to_project`) -> R5-I1/I2 -> R5-I3 -> R5-I5/I6 -> R5-I8 -> R5-I9 -> R5-I10 -> R5-I4/I7/I11
-> R5-M1/M2.

---

## Reviewer 6 — `security-reviewer`

> Six findings beyond the already-established list. **No Critical.** Four Important (three of them
> real vulnerabilities in the "defeats a gate / leaks another tenant's data" sense), two Minor.

### Important

- **[R6-F1] A tenant-less authenticated user gets unscoped FK dropdowns on all four create forms —
  cross-tenant disclosure including every user email platform-wide.**
  `views/ProjectInitiation/ProjectRequests.py:54` (guard) + `:64-67` (GET path);
  same shape in `Projects.py:41`+`:51-54`, `ProjectStakeholders.py:58`+`:68-73`,
  `ProjectKickoffs.py:64`+`:74-78`.
  The `request.tenant is None` guard sits **inside `if form.is_valid():`** — a POST-only path — so a
  **GET** falls straight through to `Form(tenant=None)`, and `TenantModelForm` only scopes
  ModelChoiceFields `if tenant is not None` (`apps/core/forms/_common.py:52`), leaving every FK on
  the ModelForm default queryset: **all rows, all tenants**.
  `GET /projects/project-requests/add/` renders `<option>`s containing every tenant's
  `core.Party.name` and `core.OrgUnit.name`, every `crm.Opportunity`, and — via `requested_by` /
  `assigned_reviewer` / `assigned_approver` — **every user account's email address platform-wide**
  (`User.__str__` returns `self.email`, `apps/accounts/models.py:82-83`).
  `GET /projects/projects/add/` adds every tenant's `core.Document.name` via `charter_document`.
  **This is not superuser-only.** `User.tenant` is `on_delete=SET_NULL, null=True`
  (`apps/accounts/models.py:56`), so deleting a Tenant leaves its ordinary, still-`is_active`
  members with `tenant=None` and a working login — that is the reachable attacker. (That
  precondition is what keeps it off Critical.)
  The author half-knew: `ProjectStakeholderForm.__init__` and `ProjectKickoffForm.__init__`
  explicitly `.none()` the `project` field when `tenant is None`, but leave `party`/`user` on the
  default queryset.
  *Fix:* hoist the guard to the **first line** of all four create views, before any form is
  constructed (the house pattern — `apps/core/crud.py:174`). Belt-and-braces in
  `apps/core/forms/_common.py`: `field.queryset = field.queryset.filter(tenant=tenant) if tenant
  else field.queryset.none()`.
  **Pattern-clone grep (L28):** `grep -rn -A 3 "if form.is_valid():" --include=*.py apps/ | grep
  "request.tenant is None"` returns the four 7.1 create views **and**
  `apps/procurement/views/DashboardPortal/ProcurementAlerts.py:82`. Every other create view in the
  tree puts the guard on the first line — that grep is the whole family.

- **[R6-F2] `pko_complete` has no "must have been held" guard, so a project reaches `active` with the
  tenant-admin charter approval never happening — a clean bypass, not a weak gate.**
  `views/ProjectInitiation/ProjectKickoffs.py:148-165`; button offered for any non-completed kickoff
  at `templates/projects/initiation/projectkickoff/detail.html:21-25`.
  An ordinary member, using only login-gated endpoints, can do `prj_create` (draft/draft) ->
  `pko_create` (planned) -> `POST /projects/kickoffs/<pk>/complete/`, and lines 159-161 see
  `project.status == "draft"` and set it to `active`. The project is live in every register with
  `charter_status='draft'` and `charter_approved_by=None`, so the `@tenant_admin_required` on
  `prj_approve_charter` is **routed around**. `pko_mark_held` has the same hole from `planned`.
  **This survives adding the auth gate** — a tenant admin can trip it with one click too.
  *Fix:* require `obj.status == "held"`, **and** refuse to promote the project unless
  `project.charter_status == "approved"`. (Deepens R5-C2 with the authorization consequence.)

- **[R6-F3] No post-approval edit lock: an approved charter and its signed document are rewritable
  while the approval stamp stays.**
  `views/ProjectInitiation/Projects.py:74-80`; Edit button unconditional at
  `templates/projects/initiation/project/detail.html:21`.
  A plain member opens `/projects/projects/<pk>/edit/` on a `charter_status='approved'` project and
  rewrites `objectives`, `in_scope`, `out_of_scope`, `start_date`, `end_date`, `project_manager`,
  `client` — and swaps `charter_document` to a different `core.Document` — while
  `charter_approved_by`/`charter_approved_at` are untouched, so the detail page still attests that
  the tenant admin approved *this* text. **You cannot forge the signature; you can change what it
  signs, which is the same outcome.**
  *Fix:* the peer pattern at `apps/accounting/views/AccountsPayable/Bills.py:38` — refuse the edit
  when `charter_status == "approved"` (or reset the charter to draft and clear both stamps on a
  material edit; silently keeping the stamp is what is not acceptable). Match the template.

- **[R6-F4] `prq_edit` lets a member rewrite an approved business case, and decision-evidence fields
  are left on the form (mass assignment).**
  `views/ProjectInitiation/ProjectRequests.py:81-87`; exclude list at
  `forms/ProjectInitiation/ProjectRequests.py:19-25`.
  (a) `estimated_cost`, `estimated_benefit`, `risk_rating` and `title` stay editable after a tenant
  admin stamped `decision='go'`/`decided_by`/`decided_at`, so **the ROI the admin approved is not the
  ROI the page shows afterwards.** (b) The exclude list omits `rejection_reason`,
  `information_requested` and `decision_notes` — but `rejection_reason` is written **only** by the
  `@tenant_admin_required` `prq_reject` (:156) and `information_requested` only by
  `prq_return_for_information` (:185), so any member can rewrite or blank the admin's stated
  rationale through the ordinary edit form. **A field written by a gated verb must not also be
  POST-settable by an ungated one.**
  *Fix:* add the three names to `exclude`, plus a status guard in `prq_edit` mirroring R6-F3. The
  contract at `.claude/tasks/contract-projects-7.1.md:96-97` needs the same three names, or the fix
  gets reverted as "contract drift". (Same root as R1-I4, with the business-case half added.)

### Minor

- **[R6-F5] Three `@tenant_admin_required` buttons are rendered to every member -> hard 403.**
  `projectrequest/detail.html:19` (Convert) and `:104` (Reject);
  `project/detail.html:17` (Approve Charter). `grep -rn "is_tenant_admin" templates/projects/`
  returns **nothing**, while every peer module gates them
  (`templates/accounting/cash/reconciliation/detail.html:10`). (Confirms R1-I6.)
- **[R6-F6] `estimated_cost` / `estimated_benefit` accept negative values (L35, the one live case).**
  `models/ProjectInitiation/ProjectRequests.py:123-124`, consumed at `:185` (`roi_pct`) and `:196`
  (`risk_adjusted_roi_pct`). Three of the four L35 sub-cases are genuinely clean here:
  **NaN/Infinity not exploitable** (no hand-parsed `Decimal(request.POST[...])` anywhere; Django
  5.1.15 rejects non-finite in `forms/fields.py:431-440`); **huge magnitude not exploitable**
  (`DecimalValidator(14,2)`); **negative accepted** — neither field carries `MinValueValidator` and
  the `exclude`-based form gives the generated field no `min_value`. `cost=-100, benefit=1000000`
  yields `roi_pct` clamped by `q2()` to `-9999999999.99%` — no 500, but the business-case screen
  prints a fabricated number and the ready-to-convert queue ranks on it.
  *Fix:* `MinValueValidator(Decimal("0"))` on both (already imported at `models/_base.py:20`);
  **needs a migration.** Hardening note, not a finding: `q2()` (`models/_base.py:38`) would raise
  `InvalidOperation` on a NaN via `max(NaN, -MAX_Q2)` — unreachable today, but an L35 500 the moment
  an importer or API bypasses the form.

### Genuinely clean

**File upload:** no `FileField`/`ImageField`/`request.FILES` anywhere in `apps/projects`;
`charter_document` FKs an already-persisted `core.Document`, so nothing bypasses
`ALLOWED_DOC_EXTENSIONS`/`MAX_UPLOAD_BYTES`. **SQL injection:** no `.raw()`, `.extra()`,
`cursor.execute` or `RawSQL`; the `Case/When` rank in `pst_list` is parameterized ORM.
**CSRF:** every `method="post"` form in all 13 templates has a matching `{% csrf_token %}` (1:1
counts); no `@csrf_exempt`. **XSS:** no `|safe`, `mark_safe` or `{% autoescape off %}`; user text
goes through `|linebreaksbr` on escaped output; the only inline `style=` is hard-coded.
**Open redirect:** no `?next=` handling; every `redirect()` takes a url name plus a pk.
**List-filter injection:** enum filters route through `crud_list`'s CHOICES allow-list, int filters
through `as_db_int` — junk/over-range/`0` params skip rather than 500 or silently empty.
**Tenant scoping of all 27 views:** every queryset and `get_object_or_404` carries
`tenant=request.tenant`; the reverse-relation walks hang off an already-verified parent.
**Secrets:** none in the app or seeder; `.env` is gitignored.

> Out of scope but noticed: `.workbuddy-ai/` is untracked **and not gitignored**, so a bare
> `git add .` would commit another tool's memory files. It predates this changeset (L45) — leave the
> files alone, but the path belongs in `.gitignore`.

### Severity judgement on the attestation gaps (as asked)

A login-only gate on a **signature field** is a genuine vulnerability, and the earlier reviewers were
right to flag `pko_mark_baseline_set` / `pko_complete` / `prq_return_for_information`. The addition
here is that **fixing the decorator alone will not close them**: R6-F2 shows the same control is
bypassable through a missing *state transition* guard even with the gate in place, and R6-F3/F4 show
that gating who may *stamp* an approval is worthless while any member may still edit *what was
approved*. Fix the gate, the transition, and the post-approval edit lock **together**, or the audit
trail keeps asserting a control that did not hold.
