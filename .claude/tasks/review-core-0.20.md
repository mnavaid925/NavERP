# Review — sub-module 0.20 Admin Console & System Operations (`core`)

Review range: `463f7a06..ecadce4b` (my 0.20 commits), scoped by FILE LIST because the history is
interleaved with a concurrent 0.21 session. Contract: `.claude/tasks/contract-core-0.20.md`.
Status: **Phase 4 in progress.** Passes 1-3 of 6 recorded below; passes 4-6 to follow
(`performance-reviewer`, `qa-smoke-tester`, `security-reviewer`).

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
