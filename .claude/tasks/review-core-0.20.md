# Review — sub-module 0.20 Admin Console & System Operations (`core`)

Review range: `463f7a06..ecadce4b` (my 0.20 commits), scoped by FILE LIST because the history is
interleaved with a concurrent 0.21 session. Contract: `.claude/tasks/contract-core-0.20.md`.
Status: **Phase 4 COMPLETE — all six reviewers have run.** Findings are recorded below, deduplicated
and renumbered in the Consolidated section, for Phase 5 (`code-fixer`) to apply.

> **RETRACTION — C6 (pass 2) is a FALSE POSITIVE and must NOT be fixed.** The explorer reported that
> `core:incident_list` does not exist and 500s the Admin Console. The frontend-reviewer checked it
> independently, contradicted it, and **I verified it myself**: `reverse("core:incident_list")` returns
> `/core/monitoring/incidents/`, `views.incident_list` exists (so `crud("monitoring/incidents",
> "incident")` at `urls.py:241` does generate the name), and `core:incident_board` is the one that does
> **not** reverse. Renaming to `incident_board` would break a working page. C6 is struck.

---

## Pass 1 — `code-reviewer` (read-only, scoped to the 0.20 file list)

### Verdict
**Needs rework before commit.** Five Critical: three `Model.clean()` guards raise `ValidationError`
keyed on fields **excluded from their own forms** (an ordinary dropdown choice 500s), the seeded
`approved` row is permanently uneditable as a direct consequence, and one POST-only verb writes a
12-character action into a `varchar(10)` audit column.

### Critical

- **C1 — `apps/core/models/Change.py:159-168` + `apps/core/forms/AdminConsole.py:99-100`.**
  `ChangeRequest.clean()` raises on `approved_by` / `approved_at` / `rollback_reason` /
  `rollback_at`, and **all four are absent from `ChangeRequestForm.Meta.fields`**. Chain:
  `_post_clean()` -> `full_clean()` -> `clean()` -> `_update_errors()` -> `add_error(None, errors)`,
  and `add_error` raises `ValueError` for a key that is not a form field
  (`django/forms/forms.py:291-295`). `status` **is** a form field, so a user merely picking
  "Approved" from the dropdown 500s. Verified by execution: `status="approved"` and
  `status="rolled_back"` both raise. **Fix: key the error on a field that exists on the form
  (`status`) or `__all__`.**
- **C2 — `apps/core/management/commands/seed_core.py:1413-1422`.** The seeded
  `status="approved"` row with no `approved_by` is **not editable at all**: `crud_edit` re-runs
  `full_clean()` on every save, `approved_by_id` is `None`, so each save 500s. The seeder row and
  the form guard are each defensible; together they make a shipped demo record permanently
  uneditable. **Fix: seed `status="submitted"` (reachable and honest), or give the row a real
  approver via the actor lookup the seeder already has.**
- **C3 — `apps/core/models/Maintenance.py:140-141` + `forms/AdminConsole.py:81-84`.** Same defect:
  `clean()` keys on `ended_at`, excluded from `MaintenanceWindowForm`.
  Verified: `status='ended_early'` -> `ValueError`. Note the form docstring at `:72-74` documents
  this exact case as yielding a friendly refusal — the intent is right, the mechanism 500s.
- **C4 — `apps/core/models/Change.py:228-229` + `forms/AdminConsole.py:114-115`.** Same defect:
  `FeatureRollout.clean()` keys on `completed_at`, excluded from `FeatureRolloutForm`.
  Verified: `status='completed'` -> `ValueError`.
- **C5 — `apps/core/views/AdminConsole.py:842`.** `write_audit_log(request.user, None,
  "bulk_preview", ...)` passes a **12-character** action into `AuditLog.action`
  (`max_length=10`, `apps/core/models/AuditLog.py:16`). Every other verb in the file obeys the rule
  its own comment states at line 155. On this project's non-strict MariaDB (per the `mysql.W002`
  note at `apps/scm/models/LaborManagement/LaborActivities.py:420-423`) the value is **silently
  truncated**; under `STRICT_TRANS_TABLES` it is a `DataError` 500. The smoke could not catch it
  because a truncated action still writes a row. **Fix: `action="update"`, verb into `changes`.**


### Important

- **I1 — `apps/core/views/AdminConsole.py:606`.** The "Firing alerts" tile counts
  `AlertEvent.objects.filter(tenant=tenant, resolved_at__isnull=True)`, which may include states
  that are not genuinely firing. Verify the exact choice set against `core.AlertEvent` when fixing.
- **I2 — `apps/core/views/AdminConsole.py:236`.** `current_count` sums over the full
  **unpaginated** `MaintenanceWindow` queryset in Python. *(routed to performance-reviewer.)*
- **I3 — blank "When" column on `templates/core/adminboard.html` and `opstrail.html`** — the rows
  render `row.created_at`, so this is likely a missing or renamed `AuditLog` field. Verify the
  field name when fixing. *(also routed to frontend-reviewer.)*

### Confirmed SAFE (do not re-litigate)
- `related_name="+"` on `MaintenanceWindow.incident` — nothing in the repo reads a reverse
  accessor, and `maintenancewindow/detail.html:51` links the notice forward via
  `obj.incident.number`.
- Spine reuse: `SCHEDULE_KIND_CHOICES = SyncSchedule.FREQUENCY_CHOICES` by reference
  (`JobScheduler.py:37`); `RISK_LEVEL_CHOICES` deliberately kept separate from
  `AlertRule.SEVERITY_CHOICES` with the reasoning recorded. Both correct.
- Multi-tenancy: every one of the 34 new views filters `tenant=request.tenant`; every object
  lookup is `get_object_or_404(..., tenant=request.tenant)`.
- The honesty invariant holds on the sampled surfaces: `run_now` writes `is_dry_run=True`, leaves
  `last_run_at`/`next_run_at` alone with the reasoning at `AdminConsole.py:144-146`, and uses the
  contract's exact success wording. `BULK_DECLINES` is the strongest artefact in the build.

### Reviewer-suggested tests (to route to test-writer in Phase 6)
- `test_adminconsole_forms.py` — for each of the three forms, `is_valid()` **returns** (does not
  raise) for every value in the model's status choices; an illegal pair yields a field error, not
  an exception.
- `test_adminconsole_models.py` — assert the rules via `pytest.raises(ValidationError)` on
  `full_clean()`, never on `save()`.
- `test_adminconsole_views.py` — POST the edit of the seeded `approved` row and assert 200; assert
  `AuditLog.objects.latest("id").action` is `<= 10` chars and equals `"update"` after
  `bulk_preview`.
- `test_adminconsole_security.py` — cross-tenant IDOR on all six POST-only verbs (the smoke covered
  the five CRUD models; the verbs are the surface that actually mutates).

### Routing
- performance-reviewer: `AdminConsole.py:236` (Python `sum()` over the unpaginated qs), `:88-91`
  and `:342-346` (extra count queries per list load), `:873-875` (unbounded `action_choices`
  scan), `:657` (ten count queries for the admin board).
- frontend-reviewer: the blank "When" column class of defect across the 19 templates.
- security-reviewer: nothing new; tenancy is clean. Optional second opinion on whether
  `tenant_admin_required` (not `login_required`) is the intended gate for the read-only boards.

---

---



---

---

## Pass 2 — `explorer` (read-only, as-built verification)

**Outcome: 2 new Critical, 1 new Important.** Every claim from pass 1 was CONFIRMED against the
code. The honesty invariant is "LARGELY RULED OUT" with exactly two exceptions (C1 below, and the
unlabelled `is_dry_run` checkbox).

### Critical

- **C6 — `apps/core/views/AdminConsole.py:630` and `:644` + `templates/core/adminboard.html`.**
  `core:incident_list` **does not exist and 500s the Admin Console.** `apps/core/urls.py:236-243`
  hand-writes the Incident routes under a different stem: `incident_board` (the list), plus
  `incident_detail` and the notify verb. `crud("monitoring/incidents", "incident")` at `:241` would
  generate `incident_list`, but only if `views.incident_list` exists — it does not, so the factory
  name is never produced. `admin_board` uses `core:incident_list` in the tiles list and in the
  needs-attention strip, so **the module's landing page 500s**. This is the same class of defect as
  the `settings_overview` one already fixed, in a second place — and it survived the first fix
  because the nav-target sweep only checks `LIVE_LINKS` targets, not the hard-coded board links.
  **Fix: `core:incident_list` -> `core:incident_board` at both call sites.**
- **C7 — `apps/core/forms/AdminConsole.py:100` + `templates/core/changerequest/form.html:48`.**
  `ChangeRequestForm` exposes **`requested_at`**, an L22 evidence stamp that four places in this
  sub-module say is off the form (`forms/AdminConsole.py:18-19` module docstring, `:88` class
  docstring, `models/Change.py:114-117`, and `changerequest/form.html:56-57` which tells the user
  "Submitting ... is what stamps the requestor and the request time"). The only writer is
  `change_request_submit` (`views/AdminConsole.py:405`). A user can set a request timestamp on a
  draft that was never submitted — the exact act the same page forbids. **Fix: drop
  `"requested_at"` from `Meta.fields` and the include from the template.**
  - Secondary, same file: `JobRunForm` exposes `is_dry_run` (`forms/AdminConsole.py:66`, rendered
    at `jobrun/form.html:31`) but the model field has **no `help_text`** (`models/JobScheduler.py:182`),
    unlike its neighbours `handler_path` and `pool_name` which both say "recorded only". Unchecking
    it makes the register assert a non-dry run with no qualification on the form. **Fix: exclude it
    from the form (it is only a real dispatcher that could clear it), or add a `help_text`.**

### Important

- **C8 — `templates/core/adminboard.html:83` and `templates/core/opstrail.html:47`.** The "When"
  column renders `row.created_at`, but **`AuditLog` has no `created_at` field** — the timestamp is
  `at`. Both cells render blank. Confirms and sharpens pass-1 finding I3. **Fix: `row.created_at`
  -> `row.at` in both templates.**
- **C9 — `apps/core/views/AdminConsole.py:606`.** The "Firing alerts" tile counts
  `resolved_at__isnull=True`, which over-counts states that are not genuinely firing. **Fix:
  filter on the state set `AlertEvent.is_open` uses (`firing`, `acknowledged`), matching 0.17's
  own `firing_board`** so the console and the board it links to cannot disagree.

### Confirmed by the explorer (do not re-litigate)
- **Spine reuse verified**, with file:line for all 14 FK targets and all 6 support-board models.
- **No duplicate schema.** The only two coexisting `PurchaseOrder` classes are the documented pair
  (canonical `scm` + pre-spine `crm` stand-in); nothing 0.20 adds collides. `RISK_LEVEL_CHOICES`
  is deliberately separate from `AlertRule.SEVERITY_CHOICES` with the reason recorded inline.
- **`opstrail` reuses 0.9's `AuditLog`**, not a second audit table.
- **Every dynamic `{% url %}` reverses except `core:incident_list`** — `ADMIN_BOARD_LINKS` (10/10),
  `SUPPORT_LINKS` (8/8, including `crm:slapolicy_list`, `hrm:helpdesksla_list`,
  `hrm:helpdeskcategory_list`), and the bulk tool keys (no URLs).
- **The honesty invariant holds.** No recorded field is presented as enforced anywhere, checked
  field-by-field against the model `help_text` on all 19 templates. The two exceptions are C7's
  `requested_at` and the unlabelled `is_dry_run` checkbox.
- **Theme classes all exist**; no `stat-row`, no out-of-palette stat-icon tone.
- **Template folder structure is correct**; no flat `<entity>_<page>.html`.
- **All `__init__.py` re-exports present**; every 0.20 name reachable.
- **Migration 0017 is complete** — all five tables, all eleven indexes, the `FeatureRollout`
  `unique_together`.

### Fix order the reviewer recommends
1. C6 (restores the module landing page) · 2. C7 · 3. C8 · 4. C9 · 5. cosmetic badge tinting
   (`opstrail.html:49`, `adminboard.html:85`) and the optional `bulk_preview` audit alignment.

> **C6 IS STRUCK — see the RETRACTION at the top of this file.** It was a false positive; the
> explorer misread `crud()`. Do not rename `core:incident_list`.
## Pass 3 — `frontend-reviewer` (read-only, 19 templates)

**Verdict: request changes.** Design-system discipline is strong: zero unclosed `{#`, every palette
class verified present, `|stringformat:"d"` on every pk filter with zero `|slugify` uses, the shared
`partials/pagination.html` properly L9-guarded and preserving filter params, zero hard-coded colour
literals (so dark mode is free), every table in `.table-wrap`, no fixed pixel widths, and all 25
`{% url %}` names reverse including the cross-app `crm:` / `hrm:` ones. But it **independently
reproduced the C1/C3/C4 500s across the full choice space**, and it is the pass that caught the
explorer on C6.

### Critical

- **C1 — `changerequest/form.html:47`, `maintenancewindow/form.html:36`, `featurerollout/form.html:35`.**
  Confirms and sharpens pass-1 C1/C3/C4 by **reproducing across the full choice space**: the only four
  failing values are `ChangeRequest` `approved` / `rolled_back`, `MaintenanceWindow` `ended_early`,
  and `FeatureRollout` `completed`; every other value validates cleanly. Structurally invisible to
  the 37-check smoke, which only exercises **seeded** rows and never a user-chosen dropdown value.
  **Fix (frontend-side, no model change): restrict each `status` select to the values a person may
  actually author, via the form's widget** — `ChangeRequestForm` offers only `draft`;
  `MaintenanceWindowForm` drops `ended_early`; `FeatureRolloutForm` drops `completed`. The model
  `clean()` guards stay as they are: they are correct, and they should keep firing for admin and API
  callers.
- **C2 — same three forms, plus the copy that already warns about it.** `changerequest/form.html:56-57`
  says "Leave `status` at Draft. Submitting is a separate action on the change's own page" — correct
  and well-judged — but the `<select>` directly above it offers nine values including Approved and
  Rolled back, and choosing either 500s. The honesty copy describes a constraint the control does not
  enforce. Resolved by the C1 fix.

### Important

- **I1 — `adminboard.html:83` and `opstrail.html:47`.** `row.created_at` -> `row.at`. Confirms pass-2
  C8 independently. Two cells, both load-bearing: they are the "When" column on two audit surfaces.
- **I2 — a "keep as is" instruction, not a change.** The reviewer's sharpest observation: the
  "this system still has no scheduler" thread is correct on every page, and the two seeded rows that
  a careless future pass would "improve" are the ones that would break the invariant. Do NOT replace a
  seeded `skipped` run with a green success, or a `queued` one with any claim of real execution.
- **I3 — `changerequest/detail.html` badge chain** does not cover the model's full
  `STATUS_CHOICES`; some legal values fall through to a generic slate badge. Align it.
- **I4 — `maintenancewindow/list.html` badge chain** likewise has gaps against
  `WINDOW_STATUS_CHOICES`. Align it.
- **I5 — the rollback-reason input on `changerequest/detail.html`** needs an explicit `<label>` and a
  logical-property margin instead of the inline `style` it uses now.
- **I6 — six `<th>` elements use `class="table-actions"`** where the header-cell class should be
  `th-actions` (the body-cell class genuinely is `table-actions`). Align the header cells.
- **I7 — a name that will mislead the next editor**, same class as I2: correct today, wrong-sounding
  tomorrow.

### Minor

- **M1 — a `{{ n|pluralize:"...ies,y" }}` argument order** to correct.
- **M2-M5 — cleanups** reported in the agent's full output; none blocking.

### The reviewer's fix order
C1/C2 -> I1 -> I3, I4 -> I5 -> I6 -> M1 -> I2, I7, M3-M5. It flags **I2 and I7** as the two most
likely to be skipped and most likely to cause a future incident, "since both are cases where the
code is right today and the *name* or the *silence* will mislead the next editor."

### Confirmed CLEAN by the reviewer (do not re-litigate)
Comment-leak class · theme palette · pagination L9 guards and param preservation · pk filters
(`|stringformat:"d"`, zero `|slugify`) · every view `filters=[...]` name has a matching `name=` in
the template and every `request.GET.X` re-selects · None-safe display (every nullable FK/datetime is
inside a guard or uses the `|date:...|default:"—"` idiom; **no None FK in a filter argument**) ·
cross-app URLs · dark mode · responsiveness.

---

---

---

## Pass 4 — `performance-reviewer` (read-only, all render paths)

**Verdict: three real N+1s on hot paths.** Query counts were derived from the actual render paths,
not estimated. Nothing in the model layer runs a query per row except `ChangeRequest.rollout_count`.

### Measured per page load (fixed + N+1)

| View | Fixed | N+1 | Total |
|---|---|---|---|
| `support_board` | 12 | **+20** | <=32 |
| `admin_board` | 12 | **+10** | <=22 |
| `jobrun_list` | 4 | **+15** | <=19 |
| `jobdefinition_detail` | 3 | **+10** | <=13 |
| `maintenancewindow_list` | 5 (2 are O(all rows)) | 0 | 5 |
| `ops_audit_trail` | 3 (1 is O(all audit rows)) | 0 | 3 |
| `jobdefinition_list`, `changerequest_list`, `bulk_board`, `featurerollout_list` | 4-7 | 0 | clean |

### Critical

- **C10 — `views/AdminConsole.py:166` + `templates/core/jobrun/list.html:73`.** `jobrun_list`
  `select_related`s `job`, but the row loop prints `{{ obj.triggered_by }}`, an FK to `accounts.User`
  that is **not** selected. **1 + N, up to 15 extra queries on a 15-row page.** `User.__str__`
  returns `self.email`, so there is no chained hop and one field fixes it.
  **Fix: `select_related("job", "triggered_by")`.**
- **C11 — `views/AdminConsole.py:704-705` + `templates/core/supportboard.html:98,107`.**
  `crm_articles` and `hrm_articles` carry no `select_related`, but the templates dereference
  `{{ a.kb_category.name }}` and `{{ a.category.name }}`. **Up to 10 + 10 = 20 extra queries** — the
  largest single-page N+1 here. The other two loops (`crm_cases`, `hrm_tickets`) dereference only
  local columns: **confirmed no N+1 there.** **Fix: add `select_related` for each category.**
- **C12 — `views/AdminConsole.py:657` + `templates/core/adminboard.html:84`.** `recent_activity` has
  no `select_related("user")` and the template prints `{{ row.user }}`. **Up to 10 extra queries on
  the page an operator opens first.** The telling part: `ops_audit_trail` at `:860` **does** have
  `.select_related("user")` for the same model, same column, same dereference, 200 lines away. This
  is a **copy divergence, not a design choice.** **Fix: add `select_related("user")`.**

### Important

- **C13 — `views/AdminConsole.py:236`.** Confirms and extends the already-established `current_count`
  finding: a Python generator over the full unpaginated `qs`, which also carries
  `prefetch_related("affected_services")`, so every row's M2M is hydrated and thrown away. This is
  **two** defects, not one:
  1. **Cost**: O(all windows) plus a wasted prefetch, on every list load.
  2. **Correctness**: it is built from the **PRE-FILTER** queryset, while `crud_list` applies
     status/recurrence/environment/search internally — so **the badge can disagree with the table
     below it** whenever a filter is active.
  **Fix: `qs.filter(starts_at__lte=now, ends_at__gt=now).count()` with one captured `now`,** which
  also removes the per-row `timezone.now()` read and needs no `isnull` filters (SQL three-valued
  logic already excludes NULL, matching the property's `bool()` guard).
- **C14 — `views/AdminConsole.py:873-875`.** `action_choices` scans **every distinct action over the
  tenant's entire append-only audit log on every page load**, unbounded, to re-derive a small closed
  vocabulary. Needs a bounded alternative and an `assertNumQueries` lock so it cannot regress to a
  full scan.
- **C15 — `Change.py:170-173` (`ChangeRequest.rollout_count` = `len(self.rollouts.all())`).** A
  **query per call**; currently safe because the detail template reads it once, but it is a latent
  N+1 the moment a list template renders it per row. Annotate when used in a list.
- **C16 — `views/AdminConsole.py:110` (`jobdefinition_detail`).** Up to 10 extra queries; the `runs`
  loop is not `select_related` through the job.
- **C17 — `maintenancewindow_detail`.** Needs a 3-line `prefetch_related` param on the shared
  `crud_detail` plus moving the template's `.exists` test into the view.

### Confirmed ACCEPTABLE — do NOT "fix" these (the reviewer was explicit)

- The four list-view `.count()`s (`unrun_count` / `muted_count` / `awaiting_count` /
  `high_risk_open`) — real but cheap.
- The **eleven** `admin_board` counts — "leave them". The real defect on that page is the `row.user`
  N+1 (C12), not the count count.
- **Both `MaintenanceWindow` indexes are correctly matched to their queries.** `window_live` is
  index-served by `(tenant, starts_at)` as a range scan; `window_scheduled` is index-assisted by
  `(tenant, status)` collapsing `status__in` to two keys. **Add neither** — a table holding tens of
  declared windows per tenant does not justify it.
- M1's unused joins, M2's unused context keys.

### Handoff to test-writer
`assertNumQueries` on `core:jobrun_list` (4), `core:support_board` (12), `core:admin_board` (12),
`core:jobdefinition_detail` (3), `core:ops_audit_trail` (3), plus a row-count assertion on
`action_choices` to lock C14 against regressing to a full scan.

### Non-perf, flagged in passing — CORROBORATES pass-1 C5
`"bulk_preview"` is 12 chars into `AuditLog.action = CharField(max_length=10)`
(`AdminConsole.py:842` vs `AuditLog.py:16`), and **`write_audit_log` never validates `action`
against `ACTION_CHOICES`** — a MySQL strict-mode `DataError` 1406 on every Preview click, invisible
to the SQLite test suite. A third independent confirmation that C5 is real.

---
---

## Pass 5 — `qa-smoke-tester` (the only reviewer permitted to touch the DB; REPORT-ONLY override applied)


**Verdict: FAIL. The predicted four 500s are all confirmed and no others — but the defect is worse
than predicted, because on EDIT it is data-dependent.**

### Critical

- **C18 — CONFIRMS pass-1 C1/C3/C4 and pass-3 C1, and escalates it.** All four reproduce on **create
  AND edit**:
  | Form | Status | Exception |
  |---|---|---|
  | `ChangeRequestForm` | `approved` | `ValueError: 'ChangeRequestForm' has no field named 'approved_by'` |
  | `ChangeRequestForm` | `rolled_back` | `ValueError: ... has no field named 'rollback_reason'` |
  | `MaintenanceWindowForm` | `ended_early` | `ValueError: ... has no field named 'ended_at'` |
  | `FeatureRolloutForm` | `completed` | `ValueError: ... has no field named 'completed_at'` |
  **Three findings the static passes could not produce:**
  1. **The values ARE in the rendered dropdowns.** QA dumped the shipped form markup and confirmed
     `changerequest add` renders `[draft, submitted, approved, ...]`, `maintenancewindow add` renders
     `[draft, scheduled, active, ended_early, ...]`, and `featurerollout add` renders
     `[planned, running, paused, completed, rolled_back]`. **A tenant admin picks "Approved" and gets
     a 500.** This is the most reachable 500 in the sub-module — not a hand-made-POST edge case.
  2. **On EDIT the outcome depends on invisible prior state.** `construct_instance` only writes
     `Meta.fields`, so editing a row whose stamp is NULL 500s, while editing a row a verb already
     stamped **saves fine (302)**. The same dropdown therefore 500s or silently saves depending on
     state the user cannot see. That is worse than a plain 500.
  3. **The form docstrings promise the opposite.** `forms/AdminConsole.py:70-77` states a user who
     picks `ended_early` "gets a refusal explaining that a window may only be ended by the verb" — it
     gets a 500 instead. **Fix: key every `clean()` rule that guards an excluded evidence stamp to
     `NON_FIELD_ERRORS` (or to a field that IS in `Meta.fields`), and correct the three docstrings
     that claim the refusal already works.** Add a test that walks every `STATUS_CHOICES` value
     through create **and** edit — that walk alone catches all four.

### Important

- **C19 — CONFIRMS pass-1 C5, with the environment evidence that makes it a real 500.** POST a valid
  tool to `bulk_preview`, then the newest `AuditLog` row's `action` comes back **silently truncated**:
  the column is `max_length=10` and the code passes a 12-character `"bulk_preview"`. QA also captured
  why it is currently silent — `@@sql_mode = 'NO_ZERO_IN_DATE,NO_ZERO_DATE,NO_ENGINE_SUBSTITUTION'`,
  i.e. `STRICT_TRANS_TABLES` is **not** set, and `mysql.W002` is emitted on every migrate. Under a
  strict-mode host the same click is a `DataError` 1406. **Fix: widen the column (the audit trail is a
  permanent record), and add a length assertion or `full_clean()` in `write_audit_log` so a too-long
  verb fails loudly at the source rather than depending on `sql_mode`.**

### Confirmed WORKING by QA (do not re-litigate, do not "fix")

- **All six POST-only verbs behave correctly**, including every documented refusal: cross-tenant pk
  -> 404, GET -> 405, submit an already-submitted change -> refused, approve a non-submitted one ->
  refused, roll back a non-completed one -> refused, roll back with an EMPTY reason -> refused, end a
  draft window -> refused, end an already-ended window -> refused, delete an already-started window ->
  refused. **`@require_POST` above `@tenant_admin_required` is confirmed correct** (405 regardless of
  role). **Refusals write 0 audit rows**, which is the behaviour every guard comment claims.
- **Full CRUD round-trips pass on all five entities** with minted numbers `JOB-00006`, `RUN-00007`,
  `MNTW-00022`, `CHG-00066`; `FeatureRollout` correctly has no number.
- **`JobRun.clean()`'s own rules surface as clean field errors** through the form, and the
  hand-written `FeatureRolloutForm.clean_feature_flag` duplicate guard refuses a duplicate pair with a
  **field error, not a 500** — "exactly the pattern C18 needs".
- **The `FeatureRollout` stage x percentage ladder behaves exactly as documented**: `internal` 0 only,
  `general` 100 only, `partial` 1-99, `pilot` unconstrained, all rejections clean field errors.
- **Page 2 and every filter**: page 2 renders wherever rows exceed the page size
  (maintenancewindow 21, changerequest 65, featurerollout 26); `page=abc` / `-1` / `0` all fall back;
  **all 5 lists, 17 filter dropdowns, every choice value applied with no 500**; search narrows on all
  five.
- **`admin_board`**: 8 tiles, every one an int with a resolving URL; `needs_attention` 7/7;
  `ADMIN_BOARD_LINKS` 10/10. **The zero rule holds** — "Open incidents 0" and "Configured settings 0"
  are genuine counts, not unmeasured values.
- **`ops_audit_trail`**: 217 rows, pagination 25/25/25/17, `page=999` and `page=abc` clamp, `?action=`
  correct for all 9 real actions, junk action safe, and **POST/DELETE/PUT re-render without writing** —
  the read-only claim holds.

### Minor

- **M6 — the shared `crud.py` boolean map** accepts only `True`/`False`; QA suggests widening to
  `true/1/on` / `false/0/off`. Explicitly **not** a 0.20 blocker.

---

## Pass 6 — `security-reviewer` (read-only, final pass)

**Verdict: the isolation and authorization posture is SOUND. No Critical cross-tenant read or write.**
Eight of ten focus areas are clean, verified by reading rather than assuming. Two Important, three
Minor, and one claim in my own briefing **challenged**.

### Important

- **C20 — `forms/AdminConsole.py:100` (`ChangeRequestForm` exposes `requested_at`).** Confirms C7 and
  **escalates it**: the field is not merely settable at creation, it is settable on **every subsequent
  edit**, because the form is bound to `changerequest_edit` with no state guard. An admin can create a
  draft, POST the **edit** with `status=submitted&requested_at=2019-01-01`, and `ChangeRequest.clean()`
  has no rule for `submitted`, so it validates and saves — **a forged request date on the register**.
  The submit verb overwrites it on the legitimate path, but the forgery is live on the row from the
  edit until then, and permanent if the change stays in `draft`. `Meta.ordering` uses `-created_at`,
  so only the displayed stamp lies.
  **The root cause of it surviving five passes: the module docstring at `forms/AdminConsole.py:90-94`
  asserts the field is off the form — a docstring that says the opposite of the code.** The reviewer
  asks for a grep across the family for that same false-claim shape.
- **C21 — `views/AdminConsole.py:842` + `models/AuditLog.py:19`.** Independently confirms C5/C19, and
  notes `config/settings.py:110` sets only `{"charset": "utf8mb4"}`, so the **DB default governs**:
  non-strict truncates to `bulk_previe`; under `STRICT_TRANS_TABLES` it is a **`DataError` -> HTTP 500
  on every preview click**, and because the write happens *before* the redirect the operator sees a
  500 instead of the count. Every other 0.20 verb respects the rule its own comment states
  (`run_now` 7, `end_now` 7, `submit` 6, `approve` 7, `rollback` 8) — `bulk_preview` at 12 is the lone
  exception. **Audit-integrity, not cosmetic: the one verb whose record may be silently mangled is
  the one claiming "nothing was executed".**

### Minor

- **C22 — `JobRunForm` exposes `is_dry_run`** with no `help_text` (confirms C7's secondary). Drop it
  from the form; only a real dispatcher could legitimately clear it.
- **C23 — `row.created_at` -> `row.at`** in `adminboard.html` and `opstrail.html` (confirms C8/I1).
- **C24 — `ops_audit_trail` renders `changes` in bulk** where 0.9's `auditlog_detail` renders one row
  at a time, so a leak 0.9 made you hunt for becomes visible at a glance. **Not a new exposure** (same
  `@tenant_admin_required` audience, same tenant filter) but worth recording as an amplifier.
  **DEFERRED — do not fix in this pass.**

### A claim this pass CHALLENGED in my briefing (verified by me)

I briefed the reviewer that "no `|safe` / `{% autoescape off %}` was found by the frontend pass" and
asked it to challenge if wrong. It checked the Python-side builders too (`_tile()` dicts,
`ADMIN_BOARD_LINKS`, `SUPPORT_LINKS`, `BULK_TOOL_CHOICES`) and found **no XSS**: nothing is marked
safe and no value is interpolated into HTML rather than rendered by Django. It also confirmed the
`tenant_admin_required` gate by reading it — `superuser OR is_tenant_admin`, so a plain tenant member
is refused and the name is accurate.

### Verified ABSENT — eight classes, with the evidence checked (do not re-litigate)

1. **Mass assignment** apart from C20/C22: every evidence stamp and actor field is excluded from its
   form, and `TenantModelForm.__init__` (`forms/_common.py:51-55`) tenant-scopes every FK/M2M
   queryset, so a crafted POST cannot attach another tenant's `sync_schedule`, `environment`,
   `incident`, `change_request`, `job` or `feature_flag`. The two deliberate `status`-exposable cases
   are each backed by a `clean()` rule refusing the dangerous value.
2. **No SQL injection**: no raw SQL, no `.extra()`, no `RawSQL`, no string-built filter key; the
   `crud_list` `filters=[(param, lookup, is_int)]` tuples are literals and no GET value reaches a
   filter *key*.
3. **XSS**: none — see the challenge above.
4. **CSRF**: every delete form carries `{% csrf_token %}`; no 0.20 view is decorated with anything
   exempting it from `CsrfViewMiddleware`.
5. **`handler_path` is never resolved.** Grepped specifically for `import_module` / `getattr` on it:
   the field is free text, never imported, so there is no RCE primitive. Confirmed.
6. **Open redirect**: all six verbs and all five `crud_*` flows redirect to a **fixed named route**
   with a pk taken from the already-scoped object, never from user input. Repo-wide, the only `next=`
   handling is procurement's, which uses `url_has_allowed_host_and_scheme`.
7. **Timing / enumeration**: all six verbs call `get_object_or_404(..., tenant=request.tenant)` as
   their **first** statement, before any state inspection — a cross-tenant pk and a nonexistent pk take
   the identical code path to an identical 404, with no 403/404 distinction to leak.
8. **No information disclosure via `AuditLog.changes`.** Traced properly: `_changed(form)` redacts all
   25 names in `crud._SENSITIVE_AUDIT_FIELDS`, and hand-rolled `changes=` dicts bypass redaction by
   design — so the reviewer enumerated **every** hand-rolled dict in the repo. The 0.20 verbs write only
   `obj.number`, booleans, counts, a username and `reason[:200]`: **no sensitive value, and no 0.20
   write path can place a value into a field the redaction list would have needed to name.**

### Reviewer's fix order for the fixer
1. C21 (`bulk_preview` audit verb) · 2. C20 (`requested_at`) · 3. C22 (`is_dry_run`) ·
4. C23 (`row.at`) · 5. C24 (defer). And **grep the family for the false-claim docstring shape** before
fixing C20.

---

# CONSOLIDATED FINDINGS — for Phase 5 (`code-fixer`)

All six reviewers have run. Their findings are **deduplicated and renumbered** below: several passes
reported the same defect independently, and the pass-level IDs (`C1`..`C24` in the narratives above)
are **superseded** by this list. Apply in **ID order: Critical, then Important, then Minor.** Mark
each `[x] fixed` or `[~] skipped — reason` as you go. **C6 is struck** (false positive) and is
deliberately absent.

## Critical

| ID | Status | Finding | Location | Fix |
|---|---|---|---|---|
| **X1** | [x] fixed | **Four status values 500 on create AND edit.** `clean()` raises `ValidationError` keyed on fields **excluded from their own form**; `_update_errors` -> `add_error(None, …)` -> `ValueError` for a key that is not a form field. Affects `ChangeRequest` `approved` / `rolled_back`, `MaintenanceWindow` `ended_early`, `FeatureRollout` `completed`. The values **are in the rendered dropdowns**, and on edit the outcome is **data-dependent** (a NULL stamp 500s; a verb-stamped row saves). | `models/Change.py:159-168,228-229`, `models/Maintenance.py:140-141`, `forms/AdminConsole.py:81-84,99-100,114-115` | **Three parts, all required.** **(a) Model:** key every guard on an excluded stamp to `NON_FIELD_ERRORS` (`__all__`) so the refusal RENDERS instead of raising — the guards themselves are correct and must keep firing for admin/API callers. **(b) Form:** restrict each `status` widget to the values a person may author, so guarded values are never offered: `ChangeRequestForm` -> `draft` only; `MaintenanceWindowForm` -> drop `ended_early`; `FeatureRolloutForm` -> drop `completed`. **(c) Correct the three form docstrings that claim the refusal already works** (`forms/AdminConsole.py:70-77` and siblings). |
| **X2** | [x] fixed | **`bulk_preview` writes a 12-char verb into a `varchar(10)` column.** Every other 0.20 verb fits (`run_now` 7, `end_now` 7, `submit` 6, `approve` 7, `rollback` 8). Silently truncates to `bulk_previe` on this non-strict MariaDB (`@@sql_mode` lacks `STRICT_TRANS_TABLES`); **`DataError` -> 500 on every preview click** under a strict host. The write happens *before* the redirect, so the operator sees a 500 instead of the count. | `views/AdminConsole.py:842`, `models/AuditLog.py:19`, `config/settings.py:110` | Pass `action="update"` and move the verb into `changes={"verb": "bulk_preview", …}`, matching the rule the file's own comment at `:155` states and the `projects/…/RetentionBoard.py:124-129` precedent. **Also add a length guard in `write_audit_log`** so a too-long verb fails loudly at the source rather than depending on `sql_mode`. **Do NOT shorten the verb to fit** — the audit trail is a permanent record. |
| **X3** | [x] fixed | **`ChangeRequestForm` exposes `requested_at` — a forgeable evidence stamp.** Settable on EVERY edit, not just creation: create a draft, POST the edit with `status=submitted&requested_at=2019-01-01`; `clean()` has no rule for `submitted`, so it saves. A **forged request date on the register**. The submit verb overwrites it later, but the lie is live until then and permanent if the row stays a draft. | `forms/AdminConsole.py:100`, `templates/core/changerequest/form.html:48` | Drop `"requested_at"` from `Meta.fields` and the include from the template. **Then grep the other four form classes for the same false-claim docstring shape** — the docstring at `:90-94` asserting this field is off the form is why it survived six passes. |
| **X4** | [x] fixed | **The seeded `status="approved"` ChangeRequest is permanently uneditable.** `crud_edit` re-runs `full_clean()` on every save and `approved_by_id` is `None`, so every save 500s. A shipped demo record that can never be edited again. | `management/commands/seed_core.py:1413-1422` | Seed `status="submitted"` (reachable and honest) **or** give the row a real approver via the actor lookup the seeder already has. The seeder row and the `clean()` guard are each defensible; together they are not. |
| **X5** | [x] fixed | **Three N+1s on hot paths**, together ~45 wasted queries across four pages. | `views/AdminConsole.py:166` (`jobrun_list` -> `triggered_by`), `:704-705` (`support_board` -> `kb_category` / `category`), `:657` (`admin_board` -> `user`) | Add the missing `select_related`. Note `:657` is a **copy divergence**: `ops_audit_trail` at `:860` already has `.select_related("user")` for the same model, column and dereference. |
| **X6** | [x] fixed | **`current_count` is O(all rows) in Python AND disagrees with the table it sits above.** A generator over the full unpaginated `qs` (which also carries a wasted `prefetch_related`), built from the **PRE-FILTER** queryset while `crud_list` applies status/recurrence/environment/search internally — so the badge can contradict the rows beneath it whenever a filter is active. | `views/AdminConsole.py:236` | `qs.filter(starts_at__lte=now, ends_at__gt=now).count()` with a single captured `now`. No `isnull` filters needed — SQL three-valued logic already excludes NULL, matching the property's `bool()` guard. |


## Important

| ID | Finding | Location | Fix |
|---|---|---|---|
| **X7** | [x] fixed | **`row.created_at` on a field that does not exist** — `AuditLog`'s timestamp is `at`. Both "When" cells render **blank** on two audit surfaces. | `templates/core/adminboard.html:83`, `templates/core/opstrail.html:47` | `row.created_at` -> `row.at`. |
| **X8** | [x] fixed | **`action_choices` scans the tenant's ENTIRE append-only audit log on every page load**, unbounded, to re-derive a small closed vocabulary. | `views/AdminConsole.py:873-875` | Bound it (a fixed set, or `.values("action").distinct()` with a cap). |
| **X9** | [x] fixed | **`JobRunForm` exposes `is_dry_run` with no `help_text`**, unlike its neighbours `handler_path` and `pool_name` which both say "recorded only". Unchecking it makes the register assert a run that was not a dry run. | `forms/AdminConsole.py:66`, `templates/core/jobrun/form.html:31`, `models/JobScheduler.py:182` | Drop it from the form — only a real dispatcher could legitimately clear it. |
| **X10** | [x] fixed | **The "Firing alerts" tile over-counts**, using `resolved_at__isnull=True` rather than the state set 0.17's own `firing_board` uses, so the console and the board it links to can disagree. | `views/AdminConsole.py:606` | Filter on the same states `AlertEvent.is_open` uses (`firing`, `acknowledged`). |
| **X11** | [x] fixed | **`jobdefinition_detail` N+1** — up to 10 extra queries; the `runs` loop is not `select_related` through the job. | `views/AdminConsole.py:110` | `select_related`. |
| **X12** | [x] fixed | **`ChangeRequest.rollout_count` runs a query per call** — safe today (one detail read) but a latent N+1 the moment a list renders it per row. | `models/Change.py:170-173` | Annotate when used in a list. |
| **X13** | [x] fixed | **`maintenancewindow_detail`** — the three M2M loops and the template's `.exists` test. | `views/AdminConsole.py`, `templates/core/maintenancewindow/detail.html` | 3-line `prefetch_related` param on the shared `crud_detail`; move the `.exists` test into the view. |
| **X14** | [x] fixed | **Badge chains do not cover the full CHOICES sets** on two pages. | `templates/core/changerequest/detail.html`, `templates/core/maintenancewindow/list.html` | Align with the model's `STATUS_CHOICES`. |
| **X15** | [x] fixed | **The rollback-reason input has no `<label>`** and uses an inline `style` rather than a logical-property margin. | `templates/core/changerequest/detail.html` | Add the label; use logical properties. |
| **X16** | [x] fixed | **Six `<th>` use `class="table-actions"`** where the header-cell class is `th-actions`. | six header cells across the entity lists | Align the header cells. |

## Minor

| ID | Finding | Location | Fix |
|---|---|---|---|
| **X17** | [x] fixed | A `{{ n|pluralize:"...ies,y" }}` argument order to correct. | `templates/core/jobdefinition/list.html` | Correct it. |
| **X18** | [~] skipped — **pre-marked DEFERRED by the review.** Widening `crud.py`'s shared boolean map is not a 0.20 defect, and `crud.py` is a shared file a concurrent 0.21 session is using; changing shared plumbing outside the findings file's own instruction is exactly what this pass was told not to do. **Recommend an app-wide pass.** | `apps/core/crud.py` (shared) | Deferred — not a 0.20 blocker, and it is a shared file another session may be using. |
| **X19** | [~] skipped — **pre-marked DEFERRED by the review.** `ops_audit_trail` renders `changes` in bulk where 0.9's `auditlog_detail` renders one row at a time, amplifying any leak's visibility. **Not a new exposure**: same `@tenant_admin_required` audience, same tenant filter, and the security pass traced every hand-rolled `changes=` dict in the repo and found no sensitive value on any 0.20 write path. Deferring it changes no verdict. | `views/AdminConsole.py:841` | **DEFERRED** — same audience and same tenant filter, so not a new exposure. |

## KEEP AS IS — do NOT "fix" these

Recorded because three separate passes flagged them as wrong or as traps:

- **The four list-view `.count()`s and the eleven `admin_board` counts** — cheap at this scale; the
  `performance-reviewer` explicitly said "leave them". The real defect on `admin_board` is X5.
- **Both `MaintenanceWindow` indexes** — already correctly matched to their queries. `window_live` is
  range-served by `(tenant, starts_at)`; `window_scheduled` is index-assisted by `(tenant, status)`.
  **Add neither.**
- **The two seeded `JobRun` rows (`queued` and `skipped`)** — nothing detects or executes in 0.20, so
  a green success would be a false claim. **Never replace them with a success.** Phase 5 left both
  exactly as seeded, as instructed.
- **`related_name="+"` on `MaintenanceWindow.incident`** — 0.17 owns `Incident`; nothing reads a
  reverse accessor.
- **`core:incident_list`** — valid; `core:incident_board` is the name that does NOT exist. C6 was a
  false positive.

## Test handoff for Phase 6

- `test_adminconsole_forms.py` — **walk every `STATUS_CHOICES` value through create AND edit** and
  assert `is_valid()` RETURNS (never raises). That walk alone catches all of X1. Plus the
  `FeatureRollout` stage x percentage matrix (0/50/100).
- `test_adminconsole_models.py` — assert every guard via `pytest.raises(ValidationError)` on
  `full_clean()`, never on `save()`.
- `test_adminconsole_views.py` — the six verbs: valid effect, GET->405, cross-tenant->404, and every
  refusal; `bulk_preview` leaves row counts identical AND writes `action` `<= 10` chars; editing the
  seeded row works.
- `test_adminconsole_security.py` — cross-tenant IDOR on all six verbs; `requested_at` not
  POST-settable; every FK dropdown tenant-scoped.
- `assertNumQueries` on `jobrun_list` (4), `support_board` (12), `admin_board` (12),
  `jobdefinition_detail` (3), `ops_audit_trail` (3) — locks X5 and X8.
  **Do not write these as fixed budgets.** Phase 5 proved the budget form cannot catch this class
  of defect: `jobdefinition_detail` had a budget of 6, a `select_related` was added, and the page
  still cost 15 because the join was on the wrong FK. Assert the count is **identical at N rows
  and at 2N rows** instead (L58), and keep the rows present (L57).

---

# PHASE 5 — APPLIED (`code-fixer`)

**Outcome: 17 of 19 fixed, 2 deliberately skipped (X18, X19 — both pre-marked DEFERRED).** No row
is left open. Every "fixed" below was proved by a command actually run in this pass; the command
is named so a later pass can re-run it rather than take this on trust.

## How each was proved

| ID | Status | How it was verified | Evidence |
|---|---|---|---|
| **X1** | [x] fixed | **(a)** the four guards re-keyed on `NON_FIELD_ERRORS`; **(b)** each `status` widget narrowed to authorable values; **(c)** the three docstrings corrected. `is_valid()` **returns** for all four values on create AND edit carrying a non-field error, and all 20 values across the three `STATUS_CHOICES` walk cleanly. Then the real HTTP flow: **9 POSTs, every one HTTP 200 with the refusal rendered and the row unchanged.** | `temp/_020_verify.py`, `temp/_020_probe_500s.py` |
| **X2** | [x] fixed | `bulk_preview` writes `action='update'` (6 chars) and the verb survives in `changes`. A length guard now raises at the source in `write_audit_log` instead of depending on `sql_mode`. The verb was **not** shortened. | `temp/_020_verify.py` |
| **X3** | [x] fixed | `requested_at` gone from `Meta.fields` and from the form template. The false-claim docstring that hid this is corrected, and the module docstring now records **why** the field is excluded. | commit `109665da` + the docstring rewrite |
| **X4** | [x] fixed | **Chose `status="submitted"`, not a real approver.** `submitted` needs no actor and `clean()` places no rule on it, so the row is editable from the first save on a fresh DB *and* on a re-seed — `_seed_actor()` returns `None` on a first pass because `seed_core` runs **before** `seed_accounts`, so an approved row seeded that way would be uneditable again. The seeder must not invent an approver identity, which is `_seed_actor`'s own stated rule. `submitted` is also the state Approve is offered from, so the register still shows a decision somebody owes. | commit `0815c0f3`; the seeded row verified in `temp/_020_probe_500s.py` |
| **X5** | [x] fixed | The three `select_related` added. Proved by **row-count invariance**, not a budget: `jobrun_list` 11 queries at 1 and at 5 rows; `support_board` 19 and 19; `admin_board` 19 and 19. | `temp/_020_verify.py` |
| **X6** | [x] fixed | `current_count` is a DB-side `.count()`. It is now asserted to **agree with the `is_current` property** (both say 2) rather than merely being fast. | `temp/_020_verify.py` |
| **X7** | [x] fixed | `row.created_at` -> `row.at` on both surfaces. Asserted by checking the newest row's **real timestamp appears in the rendered HTML** — a content assertion, so this cannot return as a quiet blank. | `temp/_020_verify.py` |
| **X8** | [x] fixed | The `action_choices` scan is capped at 200; `ops_audit_trail` now costs 10 queries against a log that only grows. | `temp/_020_verify.py` |
| **X9** | [x] fixed | `is_dry_run` dropped from `JobRunForm` and from the form template, with the reason recorded — nothing in this repo can legitimately clear it. | commits `e14b9282`, `965d7372` |
| **X10** | [x] fixed | The tile counts `firing` + `acknowledged`, the same set `AlertEvent.is_open` and 0.17's `firing_board` use, so the tile can no longer contradict the board it links to. | `temp/_020_verify.py` |

| **X11** | [x] fixed | **The first attempt was wrong and the check caught it.** The prior `select_related("job")` joined a FK the template never dereferences — the loop renders `{{ run.triggered_by }}` — so the page cost 15 queries before *and after*. Now joined on `triggered_by`: **10 queries, flat at 1 and 5 rows.** See L58. | `temp/_020_verify.py` |
| **X12** | [x] fixed | `rollout_count` reads the prefetch cache when present, and the detail view passes `prefetch_related=("rollouts")`. Asserted **both** ways: 11 queries at 1 and at 5 rollout stages, and the count equals the table prefetched *and* unprefetched. Deliberately **not** an `annotate()` alias — a `property` is a data descriptor, so `ModelIterable` cannot `setattr` it and the page would die (L57). | `temp/_020_verify.py` |
| **X13** | [x] fixed | `crud_detail` gained an optional `prefetch_related` (additive, defaults `()`, every existing caller unchanged) and the window detail uses it. The template's empty state reads the prefetched `.all` — **`.exists` re-queries and throws the prefetch away.** 11 queries at 1 and at 5 attached services. | `temp/_020_verify.py` |
| **X14** | [x] fixed | Both badge chains aligned with their `STATUS_CHOICES` (9 and 6 values). `cancelled` is now red on the window list rather than sharing neutral slate with `completed`, and the comment records why the remaining `else` stays slate and **not** green: nothing here silences anything, so a green "successful" window would be a claim the page cannot back. | `temp/_020_verify.py` |
| **X15** | [x] fixed | The rollback reason now has a real `<label>` in the house shape (`.form-label` + the `.req` marker), and the inline margin is the **logical** `margin-inline-end`. The check force-renders the form on a `completed` change first, so it cannot pass vacuously. | `temp/_020_verify.py` |
| **X16** | [x] fixed | All six 0.20 header cells use `th-actions`; the `<td>` row cells keep `table-actions`, which is correct there. `featureflag/list.html` also has one but belongs to an earlier sub-module, so it was left alone. | `temp/_020_verify.py` |
| **X17** | [x] fixed | `pluralize:"ies,y"` (singular, plural — **reversed**) rendered "1 job carrIES". Now `pluralize:"y,ies"`. | `temp/_020_verify.py` |
| **X18** | [~] skipped | **Pre-marked DEFERRED.** Not a 0.20 defect, and `crud.py` is shared with the concurrent 0.21 session. **Recommend an app-wide pass.** | — |
| **X19** | [~] skipped | **Pre-marked DEFERRED.** Same audience and same tenant filter as 0.9's `auditlog_detail`, so not a new exposure. | — |

## Two things this pass changed about its own instructions

- **X11's first fix was aimed at the wrong column.** The review said `views/AdminConsole.py:110`
  needed a `select_related`; a join was added on `run.job`, which the template never dereferences,
  and the query count did not move. Only the row-count-invariance check exposed it. **A fixed
  budget would have passed it.** Recorded as **L58** in `lessons.md`.
- **The `has_scope` idea for X13 was reverted.** An earlier draft computed the empty state in the
  view, which meant `maintenancewindow_detail` had stopped calling `crud_detail` and the new
  `prefetch_related` parameter was left dead. It now goes through `crud_detail` like every other
  detail page, and the template tests the prefetched sets — no duplicated tenant-scoping logic.

## Commands run (all from `c:\xampp\htdocs\NavERP`)

| Command | Result |
|---|---|
| `venv\Scripts\python.exe manage.py check` | `System check identified no issues (0 silenced).` |
| `venv\Scripts\python.exe manage.py makemigrations --check --dry-run` | `No changes detected` — no migration was needed, and none was generated. |
| `venv\Scripts\python.exe temp\_020_smoke.py` | `0.20 smoke OK - 37 checks` |
| `venv\Scripts\python.exe temp\_020_verify.py` | `0.20 verify OK - 57 checks` |
| `venv\Scripts\python.exe temp\_020_probe_500s.py` | `0.20 500-probe OK - 9 POSTs: no status value 500s on create or edit` |

## Manual confirmation of the four formerly-500ing values

Required explicitly, and done through the real HTTP flow rather than at the form layer —
`temp/_020_probe_500s.py`, all nine POSTs returning **HTTP 200 with the refusal rendered on the
page and the row unchanged**:

| Model | Status | CREATE | EDIT |
|---|---|---|---|
| `ChangeRequest` | `approved` | 200, refused, row still `draft` | 200, refused, row still `draft` |
| `ChangeRequest` | `rolled_back` | 200, refused, row still `draft` | 200, refused, row still `draft` |
| `MaintenanceWindow` | `ended_early` | 200, refused, row still `scheduled` | 200, refused, row still `scheduled` |
| `FeatureRollout` | `completed` | 200, refused, row still `planned` | 200, refused, row still `planned` |

Plus the seeded row from X4: edit form **200**, POST **302**.

## Deliberately NOT touched

Per the binding **KEEP AS IS** section, and verified as untouched: `core:incident_list` (valid —
`core:incident_board` is the name that does not exist, so C6 stays struck); no indexes added; the
two seeded non-success `JobRun` rows left exactly as seeded; `related_name="+"` on
`MaintenanceWindow.incident` unchanged. The eleven `admin_board` counts and the four list-view
`.count()`s were also left alone — the real defect on that page was X5, which is fixed.

## For Phase 6 (tests)

`temp/_020_verify.py` (57 checks) and `temp/_020_probe_500s.py` (9 POSTs) are the executable
specification for the four test modules below. Concretely, the assertions that earned their keep
here and should become tests rather than throwaway scripts:

- **The `STATUS_CHOICES` walk** (all 20 values, create and edit, asserting `is_valid()` RETURNS).
  This is the single check that catches all of X1 — a guard that fires on four values and crashes
  on a fifth is not a fix.
- **Row-count invariance** instead of `assertNumQueries` budgets (L58).
- **`_020_probe_500s.py`'s 9 POSTs** — the form-layer check proves the guard renders; only the HTTP
  check proves the request does not 500.
- The badge-coverage and `th-actions` checks read TEMPLATE SOURCE, not rendered HTML: a rendered
  page shows one object's status, so a rendered-HTML search for all nine values can never pass.






---
 (read-only, all render paths)
