# Review — core 0.16 Backup, Recovery & Data Lifecycle

Range reviewed: `6a834d9e..HEAD` (39 commits). Six lanes, run one after another.

## Lane 1 — code review (models, forms, views, urls, admin, seeder, migration)

**Lane scope:** `apps/core/models/Backup.py`, `models/LegalHold.py`, `forms/Backup.py`, `views/Backup.py`,
`urls.py` (the 0.16 block), `admin.py` (7 registrations), `management/commands/seed_core.py::_seed_backup`,
`migrations/0013_backup_recovery_data_lifecycle.py`, and the three package `__init__.py` re-export blocks.

**Verdict:** the model layer is genuinely excellent — every derived property honours the zero rule and every
`NULL` renders as `—` / `"not set"` / `"Not measured."`. **Every defect I found is at the view/template
boundary or in the empty-state of a computed page.** The models are stronger than the pages built on them.

---

### Verified (sanity-checks I re-ran myself)

All re-run against the real MariaDB (`10.4.14-MariaDB`) via `venv/Scripts/python.exe`, not taken on trust.

| check | command / method | result |
|---|---|---|
| `manage.py check` | `call_command("check")` | clean |
| `makemigrations --check` | `call_command("makemigrations", "--check", "--dry-run")` | **"No changes detected"** — the migration matches the models exactly |
| Migration `0013` is the true child of `0012` | read `dependencies` | `('core', '0012_language_timezone_localeprof…')`, `('tenants','0004_usagerecord')`, `swappable_dependency(AUTH_USER_MODEL)` — correct |
| Every model's `Meta.indexes` present in `0013` | enumerated `AddIndex` ops | **8/8 present** (bkpjob×2, darch×1, envinst×1, lghold×2, drill×1, recrec×1). No missing index. |
| `unique_together` in 0.16 | `grep -rn unique_together models/Backup.py models/LegalHold.py` | **exit 1 — zero matches.** Rule 1 CONFIRMED: no `unique_together` exists, so the `clean_<field>` class is genuinely not needed. |
| Seeder per-entity guards | AST-ish grep of `_seed_backup` | **6 per-entity guards** (`BackupJob`, `RecoveryDrill`, `DataArchive`, `LegalHold`, `EnvironmentInstance`, `RestoreRecord`) + `RecoveryPosture` via `get_or_create`. **No tenant-wide guard.** Rule 5 satisfied. |
| `seed_core` run twice | `call_command("seed_core")` ×2 on the real DB | **idempotent** — 2nd run printed **zero** 0.16 lines; counts stayed `3/2/1/2/1/2/1` per tenant. Every model seeded. |
| Audit verbs (`action` width) | `AuditLog._meta.get_field("action")` | `varchar(10)`, choices `{create,update,delete}`. **Both 0.16 sites write `action="update"`** with the verb in `changes` (`views/Backup.py:156`, `:413`). Rule 3: **zero 0.16 violations.** |
| `@require_POST` above the role gate | read all 7 POST verbs | **7/7 correct** (`:132/138`, `:209`, `:266`, `:328`, `:389`, `:483`). Rule 2 satisfied. |
| Re-export blocks | diff of the 3 `__init__.py` | all 7 models, 7 forms, 34 views re-exported. `import *` resolves. |
| Seeder FK cascade surface | introspected all `many_to_one` to the 7 models | the only backward FKs are **all `SET_NULL`** (`RestoreRecord.backup/archive/target_environment`, `EnvironmentInstance.source_environment/refresh_source`). No `PROTECT`/`CASCADE` inward, so the `--flush` ordering hazard other modules have does not arise here. |
| `_seed_backup` missing `--flush` reach | grepped every `seed_*.py` | no seeder references any 0.16 model; `seed_core`/`seed_tenants` have **no `--flush` option at all** and contain **zero `.delete()` calls**. Rule 5's family is satisfied. |
| Model-level zero rule | exercised directly | `duration_display`→`"—"`, `size_display`→`"—"`, `measured_rpo_display`→`"not set"`, `target_notes()` returns `state:"unknown"` for BOTH `posture=None` and `measured=None`. **All correct.** |
| `test_nav_erp` / scratch DB | dropped and re-verified | no `zz-*` scratch tenants left; 0.16 row counts unchanged at the seeded values. |

---

### Findings

#### L1-C1 — `backup_overview` prints a **green** `0` for "Never verified", turning "nothing is verified" into an all-clear  [severity: Critical]

- **WHERE:** `templates/core/backupoverview.html:24` and `:28`, fed by `apps/core/views/Backup.py:503` and `:507`
  (`unverified_count`, `unrestorable_count`); the view half is the `{% else %}` branch of
  `{% if unverified_count %}` where `0` is falsy.
- **WHAT:** Both cells render `<span class="badge badge-green">0</span>` whenever the count is `0`. A `0` for
  "Never verified" is not a fact this application can establish from *zero rows* — with no backup recorded,
  "0 never verified" is vacuously true and prints as a green tick, which is precisely the
  *"Reporting 0 here would be a false all-clear"* that 0.8's `retention_board` refuses. The view supplies a
  bare `.count()` that cannot distinguish **"0 backups, all fine"** from **"0 backups, nothing has ever been
  verified because nothing exists"**. The same board's sibling line (`backup_board`, `never_restored`) gets this
  exactly right by returning `None` and printing *"not applicable"* — so the module contradicts its own
  discipline one page over.
- **WHY IT MATTERS:** This is the single most consequential number on the hub. An auditor opening a
  freshly-provisioned workspace sees **green** on both "Never verified" and "Unrestorable archives" — a green
  tick asserting a verified, restorable estate. The honest render is `—` / "no backups recorded". This is a
  silent wrong statement on a compliance surface, and it is the exact failure mode the prompt calls out
  ("a badge implying a green tick from a NULL").
- **EVIDENCE:** Rendered the real template for a tenant with **zero** 0.16 rows
  (`render_to_string('core/backupoverview.html', {'unverified_count': 0, 'unrestorable_count': 0, …})`):

  ```
  ZERO-ROW TENANT renders:
     Never verified</dt><dd><span class="badge badge-green">0</span></dd></div> <div class="detail-item"><dt>Partial backups</dt><dd>0</dd></div>
     Unrestorable archives</dt><dd><span class="badge badge-green">0</span></dd></div> <div class="detail-item"><dt>Active legal holds</dt><dd>0</dd></div>
  ```

  (View halves confirmed by reading `Backup.py:502-508`.)
- **FIX:** Pin `None` in the view when the denominator is `0`, exactly as `backup_board.never_restored` does —
  e.g. `"unverified_count": jobs.filter(...).count() if jobs.exists() else None`, same for
  `unrestorable_count` against `archives.exists()` — and in the template replace the `{% else %}` green badge
  with `{% elif X is None %}<span class="text-muted">—</span>`-style output. The `.count()` should also be
  read off the already-fetched list rather than a second query (see L1-M1).

#### L1-C2 — `backup_board`'s "Latest ten jobs" **cannot show a queued or running backup** on MySQL/MariaDB  [severity: Critical]

- **WHERE:** `apps/core/views/Backup.py:541` (`for job in jobs[:10]`) relying on
  `Meta.ordering = ["-started_at", "-id"]` (`models/Backup.py:162`), rendered at
  `templates/core/backupboard.html:58` under the heading **"Latest ten jobs"**.
- **WHAT:** `started_at` is `null=True, blank=True` — a **just-created** backup is `status="queued"` with
  `started_at=NULL`, which is the model default. `ORDER BY started_at DESC` places `NULL`s **last** on
  MySQL/MariaDB (the opposite of PostgreSQL, which defaults `DESC` to `NULLS FIRST`). So the *newest* work is
  sorted to the *bottom* and sliced off by `[:10]` as soon as the tenant has more than ten finished jobs.
  Compounding it, the `note` chain (`:544-549`) has no branch for `queued`/`running`, so even when such a row is
  inside the window its Note cell is an empty `—`.
- **WHY IT MATTERS:** The board is the monitoring surface. The one row an operator most needs — a backup that is
  **running right now**, or one stuck in `queued` — is the one row the board is structurally unable to show, and
  it is missing *silently* (no empty-state, no gap marker: the page just shows the ten most recent *completed*
  jobs under a heading that claims to show the latest ten). On the seeded two-tenant demo it is invisible
  because all three seeded jobs have a non-NULL `started_at`.
- **EVIDENCE:** Proven on the real DB. Inserted one `status="queued", started_at=None` job for Acme and ordered
  exactly as the view does:

  ```
  total jobs: 15
  jobs[:10] shown on the board:
      Hourly transaction log / Nightly full backup / Weekly offsite copy / YY done-0 … YY done-6
  is the JUST-QUEUED (running/queued, started_at=None) job visible in the top 10? False
  its position in the full ordering: 15
  ```

  MySQL NULL-ordering confirmed independently on the same server:

  ```
  mysql: ('10.4.14-MariaDB',)
  ORDER BY started_at DESC, id DESC -> ((3, 2026-09-01), (5, 2026-05-01), (1, 2026-01-01), (4, None), (2, None))
  first 3 (the board shows these) -> ((3,), (5,), (1,))
  ```
- **FIX:** Order by a column that cannot be NULL for a live row, e.g. `-created_at` (or `-id`) for this slice —
  `jobs = list(BackupJob.objects.filter(tenant=tenant).select_related("encryption_key").order_by("-created_at", "-id"))`
  — and add `queued`/`running` branches to the `note` chain so an in-flight backup says so. If `started_at`
  ordering is genuinely wanted, `F("started_at").desc(nulls_last=False)` is not enough on MySQL; use
  `Coalesce("started_at", "created_at")`.

#### L1-I1 — A `RestoreRecord` may claim a completed restore from an archive that is provably unrestorable  [severity: Important]

- **WHERE:** `apps/core/models/Backup.py:392-413` (`RestoreRecord.clean()`), reachable from
  `apps/core/forms/Backup.py:49-52` (`RestoreRecordForm.Meta.fields` includes `archive` and `status`),
  creating the row through `views/Backup.py:184-188` → `crud_create`.
- **WHAT:** `clean()` enforces *"an archive retrieval needs the archive it retrieves from"* (`:406`) but never
  consults `DataArchive.is_restorable` — the property this very sub-module added for that exact purpose
  (`models/Backup.py:294-297`). The `archive` `ModelChoiceField` is tenant-scoped but **not** filtered by status,
  so a `status="lost"` archive with `location=""` is freely selectable, and `status="succeeded"` is an accepted
  value for the record. The register will therefore accept and store *"archive retrieval → succeeded"* against
  an archive whose own page says it is unrestorable — and the register is, by design, the only evidence a
  restore happened.
- **WHY IT MATTERS:** This is the "a page that claims more than it can deliver" class, in the one direction the
  module's whole thesis is about. 0.8 refuses a fake destruction because reporting a delete while the bytes
  survive is dishonest; the mirror image is recording a *successful restore* whose source cannot be read. The
  seeder itself plants the bait: `_seed_backup` creates *"Legacy CRM export (media lost)"* with
  `location=""` and `status="lost"` on purpose so the board's unrestorable count has something to say
  (`seed_core.py:929-938`), and nothing prevents a user from selecting it and reporting a successful retrieval.
- **EVIDENCE:** Grep of the model segment: `is_restorable` referenced inside `RestoreRecord` → **False**;
  `archive.status` consulted in `clean()` → **False**. The seeder's lost archive is on the same tenant as the
  restore form's queryset, and `TenantModelForm` scopes by `tenant` only (`forms/_common.py`, the
  `field.queryset.filter(tenant=tenant)` branch), never by status.
- **FIX:** Add a third rule to `RestoreRecord.clean()`: if `self.archive is not None` and not
  `self.archive.is_restorable`, raise `ValidationError({"archive": "This archive is marked lost/destroyed or has
  no location — it cannot be a restore source."})`; or, at minimum, narrow the form field with a
  `ModelChoiceField(queryset=DataArchive.objects.filter(status__in=["active","restored"]).exclude(location=""))`.
  The model rule is preferable — it also covers the admin and the seeder.
- **Status:** [x] fixed — `fix(core/0.16) I1: a RestoreRecord cannot name an archive its own page calls unrestorable`
  (`2aaf93e6`). Took the model-rule option (so the admin and the seeder get it too). Probe
  `temp/_0_16_i1_probe.py` tests **both directions**: the rule refuses the lost/destroyed/locationless archive
  through the real create form, and still accepts a restorable one — plus the control that a restore with no
  archive at all is unaffected.

#### L1-I2 — `backup_overview` re-derives every count with a second query instead of reusing the lists it already has  [severity: Important]

- **WHERE:** `apps/core/views/Backup.py:501-521`.
- **WHAT:** The view does `environments.count()` (`:510`) and then **re-iterates the same queryset** for
  `expired_count` (`:513`, `sum(1 for e in environments if e.is_expired)`) — the queryset is evaluated twice.
  Likewise `jobs.count()` (`:502`) followed by three more `.filter(...).count()` calls on the same `jobs` base
  (`:503`, `:504`, `:505`), `archives.count()` + `.filter().count()` (`:506`, `:507`),
  `LegalHold.active_for_tenant(tenant).count()` (`:509`) and separately `RecoveryDrill...count()` (`:514`,
  `:518`). The hub is the landing page linked from `LIVE_LINKS["0.16"]` bullet 4.
- **WHY IT MATTERS:** The board view next door (`:539-571`) shows the correct pattern — one `list()` per model,
  then Python-side derivation off the fetched rows. The hub does the opposite. `environments` is materialised
  twice (once by `.count()`, once by the generator) and the `jobs` base is passed to four separate aggregate
  queries. None of it is a correctness bug, but it is 8+ avoidable round-trips on the first page an operator
  opens, and the two views disagreeing about how to count the same thing is how the `expired_count` rule ends
  up duplicated and drifting.
- **EVIDENCE:** Read of `Backup.py:501-521`; contrast with `:561-562`, where `backup_board` correctly does
  `environments = list(...)` then `[e for e in environments if e.is_expired]`.
- **FIX:** Fetch each set once as a list and derive, mirroring `backup_board`:
  `environments = list(EnvironmentInstance.objects.filter(tenant=tenant))`, then
  `"environment_count": len(environments)`, `"expired_count": sum(1 for e in environments if e.is_expired)`.
  Same for `jobs`/`archives` (and it makes L1-C1's `None` decision trivial, since emptiness is then a local fact).
- **Status:** [x] fixed — `fix(core/0.16) I3: backup_overview fetches each set once and derives in Python`
  (`81b1e20c`). Probe `temp/_0_16_i3_probe.py` measured the hub at **20 queries before → 13 after** (the board is
  11; the hub's two extra are its own `RecoveryPosture` and `RecoveryDrill` fetches) and proved **one** statement
  now touches `core_backupjob` (was four `COUNT(*)` plus a slice) and **one** touches
  `core_environmentinstance` (was two). C4/C5/C6 probes re-run green.

#### L1-M1 — Contract §5.1 claims `crud_list` derives the `*_choices` keys from `filters`, but it does not  [severity: Minor]

- **WHERE:** `.claude/tasks/contract-core-0.16.md:355-357` vs `apps/core/crud.py:180-183`.
- **WHAT:** The contract says `crud_list(...)` "already provides **`object_list`**, **`page_obj`**, **`q`** and
  the **`*_choices`** produced by the `filters` tuples". `crud_list` produces **no** choice keys — `ctx` is
  exactly `{"object_list", "page_obj", "q"}` then `extra_context`. Every 0.16 view happens to pass them by hand
  in `extra_context` (verified: `status_choices`, `backup_type_choices`, … all present), so nothing is broken
  today.
- **WHY IT MATTERS:** It is a trap for the next entity. A future `crud_list` caller reading §5.1 will omit the
  `*_choices` keys from `extra_context` and get a silently empty filter dropdown — no error, no 500, just a
  control that cannot filter (the L7/L8 blank-region class the contract exists to prevent). It also sends a
  reader looking for machinery in `crud.py` that isn't there.
- **EVIDENCE:** `grep -n "choices" apps/core/crud.py` shows choices are read only for the **junk-enum guard**
  (`_enum_values`, `:171-172`); nothing is placed in `ctx`. `crud.py:181` is
  `ctx = {"object_list": page_obj.object_list, "page_obj": page_obj, "q": q}`.
- **FIX:** Correct contract §5.1 to say the `*_choices` keys are **the caller's responsibility in
  `extra_context`** (which is what every 0.16 view does), or make `crud_list` actually derive them from
  `filters` — but the former is the smaller change and matches as-built behaviour.
- **Status:** [x] fixed — `docs(core/0.16) I9: contract 5.1 - crud_list does NOT derive the *_choices keys`
  (`158679fb`). Took the smaller option: the contract now states the caller owns the `*_choices` keys, matching
  as-built behaviour, rather than adding machinery to `crud_list` that no current caller needs. (Contract edit,
  not code — nothing was broken today; the fix is to stop the next entity walking into the trap.)

#### L1-M2 — Model docstrings reference `Compliance.py`, a file that does not exist  [severity: Minor]

- **WHERE:** `apps/core/models/Backup.py:32` — *"see `Compliance.py`"*.
- **WHAT:** This is a stale copy of the very claim the contract **corrected during the build**
  (`contract-core-0.16.md:161-168`: *"The frozen draft named this file `apps/core/models/Compliance.py` and
  called it 'the existing 0.8 compliance home'. **That file does not exist**"*). The correction was applied to
  the contract and to `LegalHold.py`'s header, but the cross-reference inside `Backup.py`'s module docstring
  was missed, so the module's own "read this to understand the ownership boundary" paragraph points at a
  non-existent file — the exact L36-style doc/code contradiction the correction was written to eliminate.
- **WHY IT MATTERS:** Low direct runtime impact, but it is the one pointer a future maintainer follows to learn
  *why* `LegalHold` is not a field on `RetentionPolicy`, and it 404s. It also re-seeds the wrong mental model
  that the contract spent a correction block refuting.
- **EVIDENCE:** `ls apps/core/models/ | grep -i complian` → nothing; `LegalHold.py:1` is the real home and the
  contract records the correction at `:161-168`.
- **FIX:** Change `Backup.py:32` to `see ``LegalHold.py`` ` (or `apps/core/models/LegalHold.py`).
- **Status:** [x] fixed — `core(0.16) M10: point the model docstring at the file that exists` (`13f93ba7`).
  Probe asserts `Compliance.py` no longer appears in the file and that `apps/core/models/LegalHold.py` exists.

#### L1-M3 — `_seed_backup` does not seed a backup with a NULL `started_at`, so L1-C2 stays invisible  [severity: Minor]

- **WHERE:** `apps/core/management/commands/seed_core.py:844-878`.
- **WHAT:** The seeder is otherwise exemplary about exercising the hard states — a `warning`/partial row, an
  unverified `success` row, a `failed` row, an unrestorable archive with `location=""`, an `expired_at` in the
  future on the sandbox. But all **three** `BackupJob` rows carry both `started_at` and `finished_at`, so the
  `queued` status — which the model defaults to and which is the only status with `started_at=NULL` — has **no
  seeded representative**. The contract's §7 ask was *"a partial/warning backup, an unverified backup"*, both
  satisfied; the `queued` state was not asked for and not seeded.
- **WHY IT MATTERS:** The seed is the demo a reviewer and a QA sweep look at, so an unexercised state stays
  unexercised through the whole pipeline. This is precisely why L1-C2 survived a green smoke sweep: the board's
  NULL-ordering defect needs a `queued` row to appear, and the demo has none.
- **EVIDENCE:** Probe of the seeded rows on the real DB — every job returned a non-NULL `started_at`:

  ```
  === board job_rows order (-started_at,-id) ===
      Hourly transaction log | warning | started_at 2026-09-22 17:14:14.998006+00:00
      Nightly full backup    | success | started_at 2026-09-22 10:14:14.998006+00:00
      Weekly offsite copy    | failed  | started_at 2026-09-20 18:14:14.998006+00:00
  ```
- **FIX:** Add a fourth seeded job — `status="queued"`, `started_at=None`, `finished_at=None`,
  `integrity_method="none"` — inside the existing `if not BackupJob.objects.filter(tenant=tenant).exists():`
  guard. It costs one dict, keeps the seeder idempotent, and makes L1-C2 fail loudly in any future sweep.
- **Status:** [x] fixed — `core(0.16) M2/M11: seed an in-flight backup, and backfill encryption_key` (`e00cf25b`).
  One deliberate departure from the FIX text above: the row got its **own** guard rather than a slot inside the
  tenant-wide one, because a slot inside that guard would never reach the workspaces that already exist — the
  module's own documented lesson. Probe re-runs `seed_core` twice inside a rolled-back savepoint and asserts the
  row is present, in flight, and not duplicated.

---

### No-action notes (things I checked and am explicitly NOT filing)

- **No `unique_together` in 0.16** — `grep -rn unique_together models/Backup.py models/LegalHold.py` exits 1.
  Rule 1 is refuted for this sub-module; the forms' `clean_<field>` absence is correct, not an oversight, and
  `forms/Backup.py:8-13` documents exactly why. **Not a finding.**
- **The 25 pre-existing `AuditLog.action` truncation sites are not re-filed**, and **0.16 adds none** — both
  hand-rolled writers use `action="update"` with the verb in `changes` (`views/Backup.py:156`, `:413`).
- **Decorator order is correct on all 7 POST-only verbs** (`:132/138`, `:209`, `:266`, `:328`, `:389`, `:483`):
  `@require_POST` outermost, so a wrong method is 405 before the role gate can 403. Rule 2 satisfied.
- **No `crud_*` context key is overwritten by any `extra_context`.** Enumerated every dict: the extra keys are
  only `status_choices`/`*_choices`/`unverified_count`/`unrestorable_count`/`expired_count`/`active_count`/
  `conflicting_holds`/`restore_count`/`unverified_note`/`notes` — never `object_list`, `page_obj`, `q`, `form`,
  `obj`, or `is_edit`. Rule 6's overwrite hazard is absent.
- **`search_fields` and `filters` all name fields that exist** on the right model, checked one by one against
  each model's field list (including the `("integrity", "integrity_method", False)` aliasing, which is a
  deliberate GET-param name and resolves correctly).
- **L36 / ownership is clean.** The only cross-module FKs are `DataArchive.policy` → `core.RetentionPolicy`,
  `DataArchive.disposal` → `core.DisposalRecord`, `LegalHold.retention_policy` → `core.RetentionPolicy`,
  `LegalHold.subject_party` → `core.Party`, and the two `tenants.EncryptionKey` FKs. **No 0.16 model carries a
  key/secret column**, no retention logic is duplicated, and no second schedule table exists. `FREQUENCY_CHOICES`
  is a local tuple in `Backup.py:45-50` (a *copy* of the vocabulary, as the contract permits) rather than an
  import — I considered filing it, but the contract explicitly sanctions "copied as a tuple reference", and
  importing across `Integration.py` would couple two unrelated sub-modules.
- **`related_name` collisions: none.** `core.RetentionPolicy`/`DisposalRecord` declare no reverse accessor that
  would clash with `archives`/`legal_holds`; `grep` over every non-0.16 core model found no competing
  `related_name`. `makemigrations --check` agreeing ("No changes detected", including the system's own
  `fields.E3xx` reverse-clash check) is independent confirmation.
- **`EnvironmentInstance.clean()`'s `expires_at >= created_at` guard is correct** for the unsaved case —
  `created_at` is `auto_now_add`, so on an insert it is `None` and the comparison is skipped
  (`models/Backup.py:523`), which is right; and `expires_at` is not offered as a "past date is invalid" rule
  because the seeder legitimately sets it to `now + 15 days` and a *negative* interval is not an error state.
- **`LegalHold.clean()` anti-spoliation is sound, including the release-reason edge.** `scope_query` starts as
  `Q(pk__in=[])` so the `|=` chain cannot produce an all-rows match, and the else-branch is
  `others.none()` when neither `retention_policy` nor `model_label` is set (`LegalHold.py:109-114`) — a
  workspace-wide hold does not falsely block a release. The `self.pk` exclusion (`:105-106`) makes an edit-grant
  path work. `views/Backup.py:304-311` re-derives the same query for `conflicting_holds`, and I checked the two
  against each other: they agree (same operator set, same `pk` exclusion via `.exclude(pk=obj.pk)`).
- **`recovery_posture_edit` does not `get_or_create` on GET** — `:404` uses `.filter(...).first()` and can be
  `None`; `is_edit` is `posture is not None`; the POST path sets `posture.tenant = request.tenant` before
  `save()` (`:411`) so the create path cannot insert a NULL tenant. The singleton is correct, and the
  `request.tenant is None` branch (`:400-402`) redirects rather than 500s.
- **`recovery_drill_detail` returning 200 on the empty-posture path is not a 500 risk** — `target_notes(None)`
  is explicitly handled (`models/Backup.py:680-684`), verified by direct call.
- **The seed's `masking_required=True` + `copy_includes_pii=True` on a `summary` sandbox is intentional and
  correct** — it is the seeded compliance-obligation case the model's `clean()` deliberately permits
  (`copy_includes_pii` is only refused with `copy_scope="none"`), and `contains_production_data` correctly
  returns `False` for a `summary` copy, so the board does not mislabel it "Production PII".
- **`admin.py` registrations are read-mostly and correct**: `integrity_verified_at` is `readonly_fields` on
  `BackupJobAdmin` (`admin.py`, 0.16 block), so the admin cannot be used to fake a verification; the four actor
  stamps are absent from the 0.16 forms, matching the contract. `list_select_related` is present on all seven.
- **The migration's `dependencies` list is genuinely correct** — `0012` is the true parent (`core` had no
  `0013` at BASE) and `tenants.0004_usagerecord` is required for the `EncryptionKey` FK. The docstring's note
  about a placeholder-then-fold is accurate and harmless: what matters is one migration per sub-module with the
  operations in it, which is what shipped.
- **Empty-tenant sweep gap analysis.** The prompt asked whether the all-green sweep could have missed a path.
  It could, in exactly two places, and both are now filed: (a) a tenant with **no** backups renders L1-C1's
  green `0` (the sweep asserted 200 + leak-clean, and *did* assert "the zero-rule branches", but a green `0` is
  a 200 with no leak — it is a wrong number, not a crash, so no status assertion can catch it); and (b) a
  `queued` backup with `started_at=None` (L1-C2) is absent from the seed entirely, so the sweep had no data
  that could reach the branch. **A tenant with a posture and no drills is fine** — probed directly: `last_drill`
  is `None`, `drill_count` is `0`, `targets_set` is `True`, and no template path dereferences a missing drill.
  **A backup with `started_at=None` is fine at the model layer** (`duration_display` → `"—"`); it is only the
  board's `[:10]` that loses it.

### Where I think the contract itself is wrong

1. **§5.1's `*_choices` claim** is factually wrong about `crud_list` (L1-M1) — a live trap for the next entity.
2. **§4's URL table stops at "29 url names" while the header says 34 callables**, and the prompt says 34 routes.
   The as-built `urls.py` is right; the contract's own arithmetic undercounts its own enumeration (five
   `crud()` groups × 5 = 25, plus `backup_overview`, `backup_board`, `recovery_posture_edit`, `backup_job_verify`
   = **29 names over 34 callables** — the *named routes* are 29 and the *view callables* are 34, so the two
   numbers are both right but the contract calls the 29 "url names" and the prompt calls the routes "34"
   without saying which is which). Worth one clarifying line so the next reviewer does not file a phantom.
   - **Status (M12):** [x] fixed — `docs(core/0.16) M12/M3: contract 4 - 34 named routes, and the crud()
     naming fork` (`09ea350d`). The contract now states both numbers and which is which (34 view callables,
     29 named routes reached partly through `crud()`), and records the `crud()` naming fork (M3) in the same
     edit, since both are §4 concerns.
3. **§7's `_seed_recovery_posture(tenant)`** asks for a separate function; the build inlined `get_or_create`
   into `_seed_backup`. Behaviourally identical and idempotent (verified), so I did **not** file it — but the
   contract should either be corrected or the function split, because a reader checking §7 against the code
   will conclude a required function is missing.
   - **Status (M9):** [x] fixed — `docs(core/0.16) M9: contract 7 - the posture singleton is seeded inline,
     not by a helper` (`8baec6d9`). Took the contract-correction option, not the split: the behaviour is
     identical and idempotent, so the cheaper honest fix is to describe what the code does.

---

## Lane 2 — ownership, integration, world state

**Lane scope:** the Phase 0 reconcile doc's claims (`.claude/tasks/plan-1-0.16-ownership-reconcile.md`) tested
against reality; the whole `LIVE_LINKS` dict; every cross-module FK and reverse accessor; the seeder's
cross-app dependency; the state of the tree; and the migration graph shape. Read-only; every claim below
was produced by a command whose output is quoted.

**Verdict up front:** the *ownership boundary is mostly honest* — bullet 4 really is 0.8's, the archive-location
gap is real, and no model re-declares a retention concept. But **the module claims one cross-module integration
it has not built**: a `LegalHold` does not suspend anything, because the 0.8 `retention_board` that decides
"what is due for disposal" never reads it. And **7.10 already ships a document-scoped legal hold** the reconcile
doc never mentioned. Both are boundary findings, not code-style ones.

### Verified (claims I tested with a command)

| claim under test | command / method | result |
|---|---|---|
| `LIVE_LINKS["0.8"]` really claims retention/disposal | `LIVE_LINKS["0.8"]` read | **`"Retention & Disposal Policies" → core:retention_board`**, plus extras `core:retention_policy_list`, `core:disposal_list`. Claim **CONFIRMED**. |
| The 5 bullet keys are byte-identical to `NavERP.md` | `parse_catalog()` → 0.16 `features` vs `LIVE_LINKS["0.16"]` keys | the 5 keys are **exactly** the 5 catalog features (`Automated Backups`, `Point-in-Time Recovery`, `Disaster Recovery & Failover`, `Data Archival & Purging`, `Sandbox & Environment Management`). No invented bullet. |
| 0.16 adds the claimed 9 links; 160 sub-modules | `len(LIVE_LINKS)` | **160** (159→160); `len(LIVE_LINKS["0.16"])` = **9** (5 bullets + 4 extras). Confirmed. |
| The archive-location gap is real | `RetentionPolicy._meta.concrete_fields` / `DisposalRecord._meta.concrete_fields` | neither has any `location`/`target`/`destination` field (**False/False**). `DataArchive.location` is a genuine addition, **not** a duplicate. |
| Every 0.16 FK resolves to a real model | introspection of `_meta.get_fields()` on all 7 models | **22/22 FKs resolve**; targets are `core.Tenant`, `core.BackupJob`, `core.DataArchive`, `core.EnvironmentInstance`, `core.RetentionPolicy`, `core.DisposalRecord`, `core.Party`, `tenants.EncryptionKey`, `accounts.User`. All names exist. |
| No `related_name` collides | `get_accessor_name()` on `Tenant`/`RetentionPolicy`/`Party`; introspection | `Tenant.legal_holds`, `Tenant.backup_jobs`, `Tenant.data_archives`, `RetentionPolicy.archives`, `DisposalRecord.archives`, `RetentionPolicy.legal_holds` — **4 distinct descriptor objects** from the two `archives` and two `legal_holds` namesakes. No clash (each name lives on a different model). |
| `_seed_backup` tolerates a tenant with NO `EncryptionKey` | created an unkeyed probe tenant, called `Command()._seed_backup(t)` inside a rolled-back transaction | ran clean: `3 backup job(s)`, `2 data archive entry(ies)`, etc.; `all encryption_key NULL: True`; 2nd run printed `''` (idempotent). **The missing-key case is handled** (FK is `null=True`, `key = ...filter().first()` → `None`). |
| Seeder ordering | `seed_core.py:1-6` docstring + `handle()` order vs `seed_tenants.py:1-3` | `seed_core` runs **before** `seed_tenants`, and `EncryptionKey` is created **only** by `seed_tenants` (`seed_tenants.py:84-86`). So on a fresh DB `_seed_backup` runs with `key=None`. **Not fatal** (see above) but the keys are silently absent from the seeded backups — see M2. |
| Migration graph shape | `MigrationLoader(connection).graph.leaf_nodes("core")` | **`[('core', '0013_backup_recovery_data_lifecycle')]`** — exactly one leaf. `0013.dependencies` = `(core 0012…)`, `(tenants 0004_usagerecord)`, `swappable_dependency`. `grep -rln "('core', '0013" apps/*/migrations/*.py` → **nothing**. `0013` is the single leaf and nothing depends on it. |
| Package `__init__.py` edits are append-only (L43) | `git diff 6a834d9e HEAD --stat` on the 3 files | `models/__init__.py` **+11**, `forms/__init__.py` **+9**, `views/__init__.py` **+36**, `navigation.py` **+18** — **74 insertions, 0 deletions**. Nothing removed or reordered. |
| Route-name convention / template agreement | reversed all 34 names; `grep -rhoE "url 'core:…'"` over the 0.16 templates | **34 route names reverse**; every `{% url %}` in the 0.16 templates matches a generated name. No `NoReverseMatch`. |
| No greedy route shadows a 0.16 route | `grep -n "str:/|re_path/|<path:" apps/core/urls.py` | **zero** `<str:>`/catch-all routes in the whole file. The only dynamic segment is `<int:pk>`. `backup/jobs/<int:pk>/verify/` is registered after `add/` and cannot shadow it. |
| Nothing else enumerates 0.16 models | `grep -rn "get_models\|apps.get_models"` in `apps/core/views/`, `apps/dashboard/views.py` | **no model-registry iteration exists.** `dashboard` reads `AuditLog` generically (0.16's `write_audit_log` calls appear there for free). `search.py`'s `SEARCH_TARGETS` is a curated 16-entry list that 0.15/0.16 are equally absent from — no row owed. |
| `access_matrix`/`module_scope` need no 0.16 row | `apps/core/views/ModuleAccessScope.py:151-160` | reads `LIVE_LINKS` **generically** (`live_count = len(live)` per module number); module 0 already exists. **No per-sub-module row** is owed. |
| `core_overview.html` link-in | `ls templates/core/ \| grep overview` | **`core_overview.html` does not exist** — contract §6's "edit only, if it exists" item is moot. |

---

### Findings

#### L2-C1 — A `LegalHold` does not actually suspend the 0.8 schedule; three pages say it does  [severity: Critical]

- **WHERE:** `apps/core/models/LegalHold.py:22-25` (docstring) and `:140-152` (`suspends_policy`), the pages
  `templates/core/backupboard.html:105-109,124` and `templates/core/legalhold/list.html:14-16`, and the
  0.8 board they name — `apps/core/views/Privacy.py:385-421` (`retention_board`), rendered by
  `templates/core/retentionboard.html`.
- **WHAT:** The module's whole ownership justification is that a hold is *"the event that SUSPENDS a retention
  schedule"* — the reconcile doc (§The decision, point 1), the `LegalHold` docstring, and the `LIVE_LINKS["0.16"]`
  banner comment all say so. The mechanism is `LegalHold.suspends_policy(policy)`. **That method is called
  from nowhere in the repository** — it is dead code — and `retention_board`, the only page that computes
  *"what is due for disposal"*, **never imports `LegalHold` and never filters for a hold**. So the board
  keeps printing a "due for disposal" figure for a scope that an active hold covers, and does not name the
  hold — the exact output the hold pages promise it will no longer produce.
- **WHY IT MATTERS:** This is the L36 boundary turned inside out. 0.16 did *not* re-declare retention (good),
  so its only reason to exist is that it *interoperates* with 0.8's schedule. It does not. The claim is not a
  missing feature — it is a **false statement on a compliance surface**: a manager reads *"that scope's
  retention schedule is suspended and no 'due for disposal' figure can be trusted"* and then sees the board
  print a bare disposal figure with no hold named. 0.8 shipped that board with an explicit rule
  (*"Reporting 0 here would be a false all-clear"*); 0.16 has re-introduced the false all-clear's evil twin —
  a **false alarm** presented as a governed finding. Every reviewer downstream who trusts `suspends_policy`
  as "the integration hook" will not find the missing call. The reconcile doc's own next paragraph predicted
  this shape (*"0.8's retention_board ... must name the hold rather than report a 'due for deletion' figure
  it cannot justify"*) — and the promised wiring was never done.
- **EVIDENCE:** (`venv/Scripts/python.exe`, real MariaDB)
  1. Dead method —
     ```
     $ grep -rn "suspends_policy" --include=*.py .
     ./apps/core/models/LegalHold.py:25:false all-clear"* rule. `suspends_policy()` below is the hook for that.
     ./apps/core/models/LegalHold.py:140:    def suspends_policy(self, policy):
     ```
     **Two hits, both the definition and its own docstring — zero call sites.**
  2. `retention_board` ignores holds —
     ```
     $ grep -rn "LegalHold" apps/core/views/Privacy.py apps/core/views/*.py | grep -v views/Backup.py
     (no output)
     $ grep -rni "hold" templates/core/retentionboard.html
     (no output)
     ```
  3. Reproduced on the real DB. Created (inside a rolled-back transaction) a **computable** policy
     (`core.ConsentRecord` has `created_at` + `tenant`, `retention_months=0`, `action="delete"`) and an
     **active hold covering that exact policy**, then rendered `retention_board` for the tenant:
     ```
     probe policy row present: True
     hold NAMED on the board:   False
     board mentions hold word:  False
     ROW: L2 probe consent policy core.ConsentRecord 0 months Delete 6 —
     ```
     The board prints **6 due for disposal** for a held policy and never names the hold. (The *seeded* hold
     is pinned to the `Audit trail` policy on `core.AuditLog`, which has no `created_at`, so the demo masks
     the defect behind the "cannot be computed" branch — the bug needs a computable policy to appear, which
     is why the smoke sweep never saw it.)
- **FIX:** Two halves, both required. (a) Make the claim true: in `retention_board`, prefetch the tenant's
  active holds and, per policy, call `LegalHold.suspends_policy(policy)` (the hook already exists and is
  correct — matched on the policy FK *or* the `model_label`); when it returns a hold, render
  `"held — <hold.name>"` *instead of* the `due` figure and hand the template a `held_by` row. The board's
  existing zero rule already gives you the right shape to render it in. (b) If (a) is out of scope for this
  run, then **stop saying it suspends**: strip *"suspends"* from `LegalHold`'s docstring/verbose help,
  `legalhold/list.html`, and `backupboard.html`, and say instead *"holds are recorded here; the retention
  board does not yet consult them."* Do not ship the claim and the gap together.

#### L2-I1 — 7.10 (`projects`) already ships a **document-scoped legal hold**, and the reconcile doc never mentions it  [severity: Important]

- **WHERE:** `apps/projects/models/DocumentKnowledgeManagement/Documents.py:236-242`
  (`is_legal_hold`, `hold_reason`, `held_by`, `held_at`), `:352-353` (model guard), `:294-303`
  (`retention_months` → computed `retain_until`), `:216-229` (`is_archived`/`archived_by`/`archived_at`),
  the verbs `apps/projects/views/DocumentKnowledgeManagement/Documents.py:289` (`pdm_hold`) and `:320`
  (`pdm_release`), and the sidebar claim `apps/core/navigation.py:2039` +
  `.claude/tasks/plan-1-0.16-ownership-reconcile.md` (which names only 0.8).
- **WHAT:** `NavERP.md` 7.10 bullet 5 is literally *"**Document Retention & Archiving** — Lifecycle policies,
  **legal hold**, and post-project archival workflows"*, and it is **built**: `ProjectDocument` carries a
  complete hold lifecycle (`is_legal_hold` + `hold_reason` + `held_by` + `held_at`, written by the
  `pdm_hold`/`pdm_release` verb pair, with a model-level guard *"A record under legal hold may not be
  archived"*), a retention intent (`retention_months` → `retain_until`/`is_retention_due`), and an archive
  lifecycle (`is_archived`/`archived_by`/`archived_at` via `pdm_archive`), surfaced by the computed
  `projects:doc_retention` board. The Phase 0 reconcile doc says *"the plan flagged this before I started
  … `core.DisposalRecord` already exists"* and concludes *"0.8 already ships a full retention + disposal
  register"* — **it never greps for `legal hold` and never finds 7.10.** So 0.16 built a **second legal-hold
  model** while an existing one sat two app directories away, undocumented.
- **WHY IT MATTERS:** This is the L36 shape the lane exists to catch — *"a second parallel schema for the
  same concept is the bug L29 forbids."* The two are **not identical** (7.10's hold is attached to one
  document row and is released by a toggle verb; 0.16's is a tenant/policy-scoped matter with an issuer, an
  authority reference and a release event), so this is **not a Critical duplicate** and I am not asking for
  one to be deleted. But: (a) the reconcile doc's ownership table is **incomplete** — it lists 0.8 and stops,
  so a future maintainer grepping `is_legal_hold` finds two unrelated implementations with no note saying
  why; and (b) 0.16's pages over-claim scope that 7.10's holds are outside of — *"every retention window
  covering its scope"* is false for a document hold. The research agent was told to verify claims against the
  as-built spine (L28) and did not, for this one; the contract's own "CONTRACT CORRECTION" block shows this
  exact failure mode was already caught once for `Compliance.py` and the search was not widened.
- **EVIDENCE:**
  ```
  $ grep -rn "is_legal_hold\|hold_reason\|held_by\|held_at" --include=*.py apps/projects/models/…/Documents.py
  236:    is_legal_hold = models.BooleanField(
  238:    hold_reason = models.CharField(max_length=255, blank=True)
  239:    held_by = models.ForeignKey(settings.AUTH_USER_MODEL, …)
  242:    held_at = models.DateTimeField(null=True, blank=True, editable=False)
  352:        if self.is_legal_hold and self.is_archived:
  353:            errors["is_archived"] = ("A record under legal hold may not be archived …")

  $ grep -rn "def pdm_hold\|def pdm_release\|def pdm_archive" apps/projects/views/…/Documents.py
  …/Documents.py:246:def pdm_archive(...)   :289:def pdm_hold(...)   :320:def pdm_release(...)

  $ sed -n '1233,1239p' NavERP.md
  ### 7.10 Document & Knowledge Management
  - **Document Retention & Archiving** — Lifecycle policies, legal hold, and post-project archival workflows.

  $ grep -c "7.10\|doc_retention\|is_legal_hold" .claude/tasks/plan-1-0.16-ownership-reconcile.md
  0
  ```
- **FIX:** Add a `7.10` row to the reconcile doc's *"What already exists that 0.16 must point at"* table —
  *"`projects.ProjectDocument.is_legal_hold`/`pdm_hold`/`pdm_release` — a **document-scoped** hold, built by
  7.10. `core.LegalHold` is the tenant/matter-scoped layer that covers a category or a `RetentionPolicy`;
  the two are different granularity and neither is a duplicate (the `crm.PurchaseOrder` / `scm.PurchaseOrder`
  precedent, L36 §4)."* Then soften `legalhold/list.html`'s *"every retention window covering its scope"* to
  name the scope it actually governs (the policy/`model_label`, not arbitrary document holds). A one-line
  code comment on `LegalHold` pointing at 7.10 keeps it from being "deduped" later.

#### L2-M1 — `crud()` call-site naming diverges from the 8 existing call sites (`backup_job` vs the spine's `partyrole`)  [severity: Minor]

- **WHERE:** `apps/core/urls.py:211-220` (the 6 new `crud()` calls) vs `apps/core/urls.py:20-28` (the 9 existing ones).
- **WHAT:** Every pre-existing `crud()` call passes a **concatenated-lowercase** name: `crud("party-roles",
  "partyrole")`, `crud("contact-methods", "contactmethod")`, `crud("relationships", "partyrelationship")`.
  The 6 new calls pass **snake_case**: `crud("backup/jobs", "backup_job")`, `"restore_record"`,
  `"data_archive"`, `"legal_hold"`, `"environment_instance"`, `"recovery_drill"`. (The hand-written routes in
  the same file do use snake_case — `custom_field_list`, `retention_policy_list` — so the file was already
  mixed; this widens the split inside the `crud()` call sites themselves.) The generated url names and the
  templates agree, so nothing 404s or fails to reverse — I checked all 34.
- **WHY IT MATTERS:** Consequence-free at runtime (verified), but the `crud()` factory is a *convention
  carrier*: the next entity author copying the nearest `crud()` call will inherit whichever style is closest,
  and the two spellings mean a grep for `backupjob_list` finds nothing. Note the contract's own §4 uses the
  snake_case names, so the build matched the contract and the contract matched the hand-written routes — the
  divergence is really contract-vs-factory.
- **EVIDENCE:** `grep -oE 'crud\("[^"]+", "[^"]+"\)' apps/core/urls.py` →
  `crud("org-units", "orgunit")` … `crud("backup/jobs", "backup_job")` (see Verified table; all 34 names
  reverse, no `NoReverseMatch`).
- **FIX:** None required for correctness. If the lane-1 contract fix touches §4, note the two conventions
  there; otherwise leave it — this is a style fork, not a defect.
- **Status:** [x] fixed — `docs(core/0.16) M12/M3: contract 4 - 34 named routes, and the crud() naming fork`
  (`09ea350d`). Took the offered option: contract §4 now records both conventions and says the `crud()` factory
  is the fork point, so the next author sees the split before they copy a call. No code changed — all 34 names
  already reverse.

#### L2-M2 — `_seed_backup` runs before `EncryptionKey` exists, so the seeded backups/archives silently have no key  [severity: Minor]

- **WHERE:** `apps/core/management/commands/seed_core.py:837-841` (`key = EncryptionKey.objects.filter(tenant=tenant).first()`)
  and `:857` / `:919` (`encryption_key=key`), against `seed_core.py:1-6` (*"Run order: seed_core →
  seed_accounts → seed_tenants"*) and `seed_tenants.py:84-86` (the only creator of `EncryptionKey`).
- **WHAT:** `seed_core` is documented and coded to run **first**; `EncryptionKey` rows are created **only**
  by `seed_tenants`, which runs **after**. `key` is therefore `None` on every fresh seeding, and every seeded
  `BackupJob`/`DataArchive` is written with `encryption_key=NULL` even though the rows' own `encryption_scheme`
  says `aes256`/`managed`. The code handles the absent key safely (no crash, FK is nullable) — but the demo
  data is internally inconsistent: a backup recorded as AES-256 encrypted with no key row behind it.
- **WHY IT MATTERS:** Minor, and *not* the crash a careless reader would predict — I proved the no-key path is
  clean. The consequence is that the seeded demo under-represents the `encryption_key` FK on the detail pages
  (it renders `—`/"not recorded"), and a re-run of `seed_core` **after** `seed_tenants` will *not* backfill
  it because of the per-entity `if not …exists()` guards. So the keys are missing permanently in any DB seeded
  in the documented order. The module's own thesis is "a NULL that means 'not reported' must never be printed
  as though it were fine", which makes an accidentally-NULL FK on the demo a small own-goal.
- **EVIDENCE:** Probe (rolled-back transaction; fresh tenant, no key):
  ```
  OUTPUT: '  L2 NoKey Probe: seeded 3 backup job(s) … seeded 2 data archive entry(ies) …'
  BackupJob rows: 3
  all encryption_key NULL: True
  2nd-run OUTPUT: ''          # idempotent — and never backfills
  ```
  Confirmed on the real multi-tenant DB that every tenant that *has* been fully seeded has 2 keys
  (`acme keys: 2`, `globex keys: 2`), i.e. the NULL only occurs on a `seed_core`-first run.
- **FIX:** Leave the ordering alone (it is the documented contract). Either widen the guard so the key is
  attached on a later run — e.g. on the `exists()` fast-path, `BackupJob.objects.filter(tenant=tenant,
  encryption_key__isnull=True).update(encryption_key=key)` when `key` is not None — or state in the seeder
  docstring that a `seed_core`-before-`seed_tenants` run leaves the key column NULL *on purpose* (the
  contract §7 already sanctions "Reuse the tenant's existing `EncryptionKey` **if present**"). The docstring
  line is the smaller, honest fix.
- **Status:** [x] fixed — `core(0.16) M2/M11: seed an in-flight backup, and backfill encryption_key`
  (`e00cf25b`). Took the **backfill** option rather than the docstring note: the NULL is an accident of run
  order, not an intention, so the demo should end up consistent. The backfill matches only the names this
  seeder itself creates, so a user-added row is never touched, and the deliberately keyless
  "Legacy CRM export (media lost)" is left NULL. Probe runs the real `seed_core` inside a rolled-back savepoint
  and asserts the seeded jobs and the located archive now carry the key while the lost archive does not.

---

### Collisions checked and NOT found (evidence for the boundary)

Each line is a search that returned nothing colliding, so the boundary can be trusted:

- **Backup / restore / recovery / DR / failover / replication** — `grep -rn "class .*\(Backup\|Archive\|Recovery\|Restore\|LegalHold\|Environment\|Sandbox\|Instance\)" apps/*/models/` → **only the 7 new 0.16 classes plus `RetentionPolicy`/`DisposalRecord`.** No pre-existing model in any app claims backup/restore/DR.
- **Every `LIVE_LINKS` label and route, across all 160 sub-modules** — programmatic scan for `backup|restore|recover|archiv|retention|disposal|purge|hold|sandbox|environment|snapshot|replicat|failover|disaster|seed|provision|subset|lifecycle` returned **exactly one substantive adjacency: `7.10 Document Retention & Archiving → projects:doc_retention`** (filed as L2-I1). All others are lexical coincidences: `2.6 Disposals & Retirements` (`accounting:asset_disposal_list`, fixed assets — different asset class), `3.14 Salary Holds` / `4.5 …?status=on_hold` (payroll/order status, not preservation), `6.12 Quarantine & Inspection Hold` (`inventory:quarantineorder_list`, QC), `3.38 Retention Strategies` (talent flight-risk, not data retention).
- **A pre-existing "sandbox"/"environment"/"instance" management concept** — `grep -rniE "class .*(Environment|Sandbox|Instance)"` → **none.** The only other `environment` column is `inventory.IntegrationChannel.environment` (`sandbox`/`production`, `apps/inventory/models/ThirdPartyIntegrations/IntegrationChannels.py:72`), which selects an **API endpoint** for a connector — a different concept from a provisioned environment instance, and out of 0.16's scope. `django_apps` "instance" hits are unrelated.
- **A "documents" sub-module that owns archiving** — module 13 (`documents`) is **not built** (LIVE_LINKS has no `"13.*"`; `apps/` has no `documents`). 7.10's own docstring defers enforcement to *"Module 13.9/13.14"*, which does not exist yet. So 0.16 is not stepping on a built documents module.
- **`retention`/`disposal` re-declared anywhere** — `grep -rn "retention_months\|retain_until" apps/` outside the 0.16 files returns only `projects.ProjectDocument` (a per-document intent, filed L2-I1) and `core.`0.8 itself. The 0.16 models carry **no** `retention_months`/`disposal_method`/`action` column — `retention_days` on `BackupJob` is the **artefact's** lifetime and `expires_at` on `DataArchive` is the archive's, both distinct from a data category's schedule.
- **A key/secret column** — `BackupJob.encryption_key` and `DataArchive.encryption_key` are **FK only**; `tenants.EncryptionKey` stores `prefix` + `key_hash` and *"never plaintext"* (`EncryptionKey.py:7`). No 0.16 model stores key material. Confirmed by reading both field definitions.
- **`related_name` shadowing** — see the Verified table: **4 distinct descriptors**, no shadow. `related_name="legal_holds"` on `LegalHold.tenant` does **not** shadow `RetentionPolicy.legal_holds` (`LegalHold.retention_policy`) — they live on different classes, both accessors resolve, and `manage.py check` (whose `fields.E3xx` reverse-clash check would fire) is clean.
- **A model-registry surface owing a 0.16 row** — `grep -rn "get_models\|apps.get_models" apps/core/views/ apps/dashboard/` → **none**; `access_matrix`/`module_scope_sync` read `LIVE_LINKS` generically and need no per-sub-module row; `search.py`'s `SEARCH_TARGETS` is a curated short list no recent sub-module is on.
- **A greedy route in `core/urls.py`** — `grep -n "str:/|re_path/|<path:" apps/core/urls.py` → **zero**. Nothing can shadow `backup/…`.
- **Genuinely new vs 0.8 for the *archive* half** — `RetentionPolicy` / `DisposalRecord` have **no** location/target column (proved by field enumeration), so `DataArchive.location` is the one thing that makes a restore possible. The reconcile doc's gap claim **holds** here.

---

### No-action notes

- **The state of the world, for the fixer (L45):** `git status` shows **4 modified files** —
  `templates/projects/reporting/{dashboard/detail,home,reportrun/detail,reportrun/list}.html` — which are
  **not 0.16's.** They match the reconcile doc's Phase 0 note exactly (*"A concurrent session is mid-build on
  Module 7.18 … 4 modified `templates/projects/reporting/*.html`"*), they predate this review, and the latest
  commit touching that directory is `215a299e docs(projects): _caveats.html names all three readers…`.
  **They belong to the 7.18 session. Do not commit, revert or `git add` them** (L43/L45). The tree is
  otherwise clean. Untracked review artefacts (also not yours to commit unless the process says so):
  `.claude/tasks/review-core-0.16.md` (lanes 1+2), `test-contract-core-0.15.md`, `test-contract-dashboard-0.0.md`.
- **Migration `0013` is the single `core` leaf** and no migration depends on it — confirmed by the loader, not
  by `makemigrations --check` alone. Nothing to merge; the graph is linear.
- **The 5-bullet ownership classification is honest** for bullets 1, 2, 3, 5 (genuinely absent before 0.16) and
  for the *archive* half of bullet 4 (a real gap). Only the **hold** half of bullet 4's integration is
  over-claimed (L2-C1) — the *models* are honest, the *cross-module promise* is not.
- **No `# noqa` / import-order problem in the append blocks** — the three `__init__.py` additions are pure
  appends after the existing `Localization` block; `import *` resolves (verified by importing all 7 models,
  7 forms and 34 views from their packages).
- **I did not re-file lane 1's findings** (L1-C1 green zero, L1-C2 NULL-ordering, L1-I1 unrestorable archive,
  L1-I2 double-query, L1-M1 `crud_list` choices, L1-M2 stale `Compliance.py`, L1-M3 no queued seed). I
  independently re-verified L1-C2's MySQL NULL ordering while probing the board and agree it is real; I did
  not re-verify the others, so treat them as lane 1's evidence, not mine.
- **Could not verify / out of scope:** I did not run the app under `settings_test` (SQLite) — my NULL-ordering
  and board probes ran against the real MariaDB, which is the engine the defect needs. I did not exhaustively
  diff the `0013` operations against the models beyond lane 1's 8/8 index check and `makemigrations --check`.

---

## Lane 3 — frontend review (21 templates)

**Lane scope:** the 21 templates listed in the brief — `backupoverview.html`, `backupboard.html`, and the
`list/form/detail` triplets of `backupjob`, `restorerecord`, `dataarchive`, `legalhold`,
`environmentinstance`, `recoverydrill`, plus `recoveryposture/form.html`. Read against
`apps/core/views/Backup.py`, the models, `contract §5/§6`, and the house references (`holiday/list.html`,
`holiday/form.html`, `backupoverview.html`'s computed-board siblings).

**Verdict up front:** the templates are *visibly* the most careful part of this sub-module — every zero-rule
property is rendered as `—`/`not set`/`not applicable`, every badge colour exists, every `{% url %}` arg is
correct, no comment leaks, no `L42`, no nested form, no missing `aria-label`. **Two real defects survive**:
one rendered lie on the legal-hold detail (L3-C1, reachable through the form), and one board line that
asserts a fact about zero rows (L3-C2). The 21-field flat form (L3-I1) is a genuine usability problem, not
a style note. Everything else is Minor.

### Verified (what I rendered or grepped, with the command)

All render probes ran against the real MariaDB via `venv/Scripts/python.exe` with a `RequestFactory` +
`FallbackStorage` request carrying the real tenant and the `admin@naverp.local` user; every view call below
returned a rendered `HttpResponse` whose body I regex-parsed.

| check | command / method | result |
|---|---|---|
| **Every badge/text modifier exists in theme.css** | `grep -oE '\.badge[a-z-]*' static/css/theme.css \| sort -u` | `.badge`, `.badge-amber`, `.badge-green`, `.badge-info`, `.badge-muted`, `.badge-red`, `.badge-slate` — **exactly the 6 colour badges, no `-success/-danger/-warning`.** Every `badge-*` in the 21 templates is one of these. |
| **No `.alert*` class** | `grep -c '\.alert' static/css/theme.css` | **0** — and `grep -rn 'alert-' templates/core/{backupoverview,backupboard,backupjob,restorerecord,dataarchive,legalhold,environmentinstance,recoveryposture,recoverydrill}` returns nothing. The pages use `.text-warn` for caution blocks, which is the house shape. |
| **Every `text-*` is real** | `grep -oE '\.text-[a-z-]+' static/css/theme.css \| sort -u` | `.text-brand .text-danger .text-muted .text-ok .text-red .text-right .text-warn`. The 21 templates use only `text-muted`(96), `text-warn`(41), `text-ok`(1) — **all three real.** |
| **Layout classes exist** | `grep -oE '\.(detail-item|detail-grid|empty-state|table-actions|table-wrap|filter-bar|form-grid|form-help|form-error|req|fw-600|btn-icon|btn-outline|btn-primary)' static/css/theme.css \| sort -u` | all present; `.detail-item` present (L40's trap avoided — 103 uses, all inside `<dl class="detail-grid">`). |
| **Lucide icon names are real** | see "Lucide" note below | all 21 names are real Lucide icons; the project loads `https://unpkg.com/lucide@latest` from `base.html:29` (a **live CDN, not a fixed bundle** — so an icon name is only wrong if it was never a Lucide icon), and 20 of the 21 names are already used elsewhere in `templates/`. The one newcomer, `database-backup`, is used only by these 3 files — see **No-action note**. |
| **Every `{% url %}` arg is right** | extracted all 38 `{% url %}` call sites with a regex, cross-checked each arg | **every dynamic arg is `<obj>.pk` on a real object, and every FK-derived one is inside an `{% if %}` guard** (`obj.backup.pk`/`obj.archive.pk` in `restorerecord/detail.html:23-24`; `obj.subject_party.pk` in `legalhold/detail.html:42`; `obj.source_environment.pk`/`obj.refresh_source.pk` in `environmentinstance/detail.html:56-57`; `row.job.pk`/`row.hold.pk`/`archive.pk`/`env.pk` in `backupboard.html`). `backup_job_verify` correctly takes `obj.pk`. **No NoReverseMatch risk, no wrong-arg risk.** |
| **`dataarchive/detail.html`'s bad links are GONE** | `grep -n "url '" templates/core/dataarchive/detail.html` | the file now references only `data_archive_list/_edit/_delete`; `grep -rn 'retention_policy_detail\|disposal_detail' apps/ templates/` finds **zero** hits anywhere in the tree. The fix is confirmed and complete. |
| **No blank context key** | captured each view's real context by monkey-patching `django.shortcuts.render`, then compared every `{{ name }}` root in each template against it | **every extra key the contract pins is supplied**: `status_choices/backup_type_choices/storage_tier_choices/integrity_method_choices/unverified_count` ✓, `tier_choices/format_choices/unrestorable_count` ✓, `active_count` ✓, `kind_choices/copy_scope_choices/expired_count` ✓, `outcome_choices` ✓, `restore_count` ✓, `conflicting_holds` ✓, `posture/rpo_note/rto_note` ✓, `drill_count/last_drill/targets_set/posture` ✓, and all 12 `backup_overview`/`backup_board` keys ✓. The only "unsupplied" roots a naive scan flags are loop variables (`value`,`label`,`field`,`e`,`other`) — false positives. |
| **Zero rule in the templates** | rendered `recovery_drill_detail` for `measured_rpo=None`; `data_archive_detail` for `record_count=None,size_bytes=None`; `backup_board` for a zero tenant | drill → `RPO Cannot tell` / `RPO not measured.` ✓; archive → `Records — — blank means not reported`, `Size —` ✓; board → `Successful backups never test-restored: not applicable` ✓. **The only zero-rule failures are L3-C2 (board) and lane 1's L1-C1 (overview).** |
| **Empty-state colspan == `<th>` count** | `grep -c '<th'` vs `grep -oE 'colspan="[0-9]+"'` per list template | `backupjob` 8=8, `dataarchive` 8=8, `environmentinstance` 7=7, `legalhold` 7=7, `recoverydrill` 7=7, `restorerecord` 7=7; board 5/4/4/5/5 and overview 5/4 all match. **Zero mismatches.** |
| **No nested `<form>`** | brace-scan of `<form`/`</form>` depth across the 14 form-bearing templates | depth returns to 0 everywhere, max depth 1. The list pages' 2 forms are the GET filter bar and the per-row POST delete — siblings, not nested. The `page-actions` POST deletes sit in `.page-header`, **outside** the page's own `<form>`. |
| **No duplicate id, no dangling `<label for>`** | rendered 11 pages, extracted all `id=` and all `for=`, diffed | zero duplicates, zero dangling `for=`. |
| **`aria-label` consistency** | `grep -n 'name="q"'` on the 6 list templates | **all 6** set `aria-label="Search"` on the search input and `aria-label="<Field>"` on every filter `<select>` (5/3/4/2/4/3 aria-labels respectively — one per control including the search box). Consistent with `holiday/list.html:18`. |
| **Icon-only controls labelled** | `grep -rnE '<(a\|button)[^>]*class="btn-icon' … \| grep -vE 'title=\|aria-label='` | **zero hits** — every `.btn-icon` link/button carries `title=`, and the button also carries `title=`. |
| **Labels all have `for=`** | `grep -rnE '<label(?![^>]*for=)' -P` | zero hits. |
| **No comment leak (L2)** | per-line scan: every `{#` must close `#}` on the same line | **0 violations, no `{% comment %}` tags.** |
| **L42 — no interpolation into JS** | `grep -rnE "confirm\([^)]*\{\{"` and `grep -rnE '(onclick\|onsubmit\|href)="[^"]*\{\{'` | **zero.** All 12 `confirm()` handlers are static copy (`Delete this backup record? This removes the record, not any backup file.`), none contains an apostrophe or a `{{ }}`. The L42 repeat-offender class is **absent**. |
| **Tag balance** | regex open/close count for `div,table,tbody,thead,tr,dl,form,ul,li,p,span,h1-3,a,button,label,code` across all 21 | every tag balances. |

**Lucide — how I checked.** The project does **not** ship an icon bundle: `templates/base.html:29` is
`<script src="https://unpkg.com/lucide@latest"></script>` and `static/js/app.js:6-7` calls
`window.lucide.createIcons()`. There is no fixed set to diff against — `unpkg/lucide@latest` serves the
whole catalogue. I therefore checked the names against (a) my knowledge of the Lucide catalogue and (b)
the project's own corpus:

```
$ for i in activity alert-triangle archive check clock database-backup eye gavel history info link
           pencil plus search server settings shield-alert shield-check shield-off
           sliders-horizontal trash-2 ; do echo -n "$i: "; grep -rl "data-lucide=\"$i\"" templates/ | wc -l; done
activity: 74      alert-triangle: 151  archive: 29       check: 594     clock: 88
database-backup: 3  eye: 604          gavel: 23         history: 37    info: 44
link: 13          pencil: 911         plus: 572         search: 584    server: 5
settings: 7       shield-alert: 37    shield-check: 55  shield-off: 15
sliders-horizontal: 21                trash-2: 882
```

Every one of these is a real Lucide icon name; 20/21 were already used by other shipped templates, so if
any were bogus the whole app would already be showing a missing glyph. `database-backup` is used by exactly
3 files — **all three are 0.16 backups** (`backupboard.html`, `backupjob/list.html`, `backupoverview.html`)
— so it is the only name this sub-module introduces and its validity rests on my catalogue knowledge, not
on a sibling. See No-action note.

---

### Findings

#### L3-C1 — `legalhold/detail.html` renders *"Not in force … the retention schedule … has resumed"* for a hold whose own status badge on the same page says **Active**  [severity: Critical]

- **WHERE:** `templates/core/legalhold/detail.html:24-30` (the `{% else %}` branch of `{% if obj.is_active %}`),
  rendering `{{ obj.get_status_display }}` from `LegalHold.status` at `:36-40` on the same page. The state is
  reachable because **both** fields are editable form fields — `apps/core/forms/Backup.py:77`
  (`LegalHoldForm.Meta.fields` includes `"status"` **and** `"released_at"`).
- **WHAT:** `is_active` is `self.status == "active" and self.released_at is None`
  (`models/LegalHold.py:124`). A row with `status="active"` **and** `released_at` set is `is_active → False`,
  so the page takes the `{% else %}` branch and prints:

  > **Not in force** — Active as of Sep 22, 2026 20:08. The retention schedule covering workspace-wide has
  > resumed.

  while the `<dt>Status</dt>` cell twelve lines below prints a **`badge-red` "Active"** badge. The two cells
  contradict each other on the same screen, and the banner asserts the *stronger* false claim — that
  preservation has **ended** — for a hold the register still lists as in force. The `{% else %}` branch also
  cannot distinguish **"released"** from **"expired/superseded"** from **"active-but-inconsistently-stored"**;
  it says "has resumed" for all three.
- **WHY IT MATTERS:** This is the module's own thesis turned against it. The whole sub-module exists to stop
  a page printing a fact the data cannot support (`retention_board`'s *"Reporting 0 here would be a false
  all-clear"*). Here the page prints the **opposite** of a false all-clear — a false *clearance*: it tells a
  compliance reader that a preservation order has ended when the record says it is still active. A person
  acting on that banner could dispose of data that is in fact held, which is spoliation — the exact harm
  `LegalHold.clean()`'s release guard (`:90-122`) exists to prevent. It reads as a template-authoring slip
  (the branch was written for the *released* case and reused for "not currently active"), but it is a
  rendered lie on the one page a hold exists to justify.
- **EVIDENCE:** Reproduced on the real DB inside a rolled-back transaction (`venv/Scripts/python.exe`):

  ```
  created: LegalHold(status="active", released_at=timezone.now(), scope="L3 probe")
  is_active = False | status= active | released_at= 2026-09-22 20:08:44+00:00
  BANNER:       Not in force — Active as of Sep 22, 2026 20:08.
                The retention schedule covering workspace-wide has resumed.
  STATUS BADGE: Active            (badge-red)
  ```

  The `status`/`released_at` pair is settable from the shipped edit form:
  `grep -n 'released_at\|"status"' apps/core/forms/Backup.py` → `:77` lists both in
  `LegalHoldForm.Meta.fields`.
- **FIX:** Make the branch depend on the **release event**, not on `is_active`. Replace the `{% else %}`
  banner with three explicit states, e.g.:

  ```django
  {% if obj.is_active %}
    …in force… (unchanged)
  {% elif obj.released_at %}
    <p class="text-muted">Released {{ obj.released_at|date:"M d, Y H:i" }} —
      the retention schedule covering {{ obj.scope_label }} has resumed.</p>
  {% else %}
    <p class="text-warn"><i data-lucide="alert-triangle"></i>
      This hold is <strong>{{ obj.get_status_display }}</strong> and no release is recorded —
      the register cannot say whether preservation is in force. Treat the schedule as suspended
      until this is corrected.</p>
  {% endif %}
  ```
  so the "has resumed" sentence only ever prints when a `released_at` actually exists. (A model-side
  `clean()` that refuses `released_at` on a non-released hold would be the belt-and-braces fix, but the
  template guard is the one this lane requires.)

#### L3-C2 — `backup_board`'s *"Verification state unreadable"* line asserts *"all records carry a readable verification state"* on a workspace with **zero** records  [severity: Critical]

- **WHERE:** `templates/core/backupboard.html:25` —
  `{% if unverifiable_count %}{{ unverifiable_count }}{% else %}0 — all records carry a readable verification state{% endif %}`
  — fed by `apps/core/views/Backup.py:587` (`"unverifiable_count": 0`, a hard-coded constant).
- **WHAT:** `unverifiable_count` is always `0` (the view even comments that it is a pinned key with no
  producer). Because `0` is falsy, the `{% else %}` branch always wins, so the board prints **"0 — all
  records carry a readable verification state"** unconditionally — including for a workspace whose
  `job_total` is `0`. The sentence is a *claim about the set's members*; with an empty set it is vacuous in
  the way `never_restored` explicitly refuses. The very next row up, the board gets this right:
  `{% if never_restored is None %}… not applicable …` renders "not applicable" when there is no successful
  backup. So **one page, two rows apart, applies the zero rule and then violates it.**
- **WHY IT MATTERS:** This is the signature discipline of the sub-module and of 0.8 before it. The board's
  own intro paragraph (`:16-18`) promises *"Where a figure cannot be determined the page says so and prints
  —, never a 0: a zero that means 'cannot tell' is the most dangerous number an operations board can show."*
  The page then prints a `0` that means "cannot tell" and dresses it as a **positive finding** ("all records
  carry a readable verification state") for a workspace that has no records at all. An auditor opening a
  freshly provisioned tenant sees a green-adjacent reassurance about verification coverage computed from
  nothing. This is the same *shape* as L1-C1 (a `0` standing in for "no denominator"), on a different page
  and a different key, so it is not a duplicate of lane 1's finding.
- **EVIDENCE:** Rendered `backup_board` for the zero-row tenant (`Lane5 Empty`, `jobs=0`):

  ```
  === tenant 423 Lane5 Empty
  Backups recorded                        -> 0
  Verified                                -> 0
  Successful backups never test-restored  -> not applicable      ← correct
  Archives                                -> 0 (0 on asynchronous retrieval)
  Verification state unreadable           -> 0 — all records carry a readable verification state   ← L3-C2
  ```

  Compare the sibling tenant (`Acme Inc`, `jobs=3`), identical string. The `never_restored` "not applicable"
  branch proves the author knew the pattern; this row just does not apply it.
- **FIX:** Mirror the `never_restored` treatment. In the view, pin `None` when there is nothing to be
  readable of — `"unverifiable_count": 0 if jobs else None` — and in the template render the three states:

  ```django
  <dd>{% if unverifiable_count is None %}<span class="text-muted" title="There are no backup records for this to be true of.">not applicable</span>
      {% elif unverifiable_count %}{{ unverifiable_count }}
      {% else %}0 — all records carry a readable verification state{% endif %}</dd>
  ```
- **Status:** [x] already fixed — folded into **C6** (`668ae0fb`, `09c8bc5d`, `3a31f2b5`). This is the same
  defect the Minor table lists as **M4** ("`backupboard.html:25` — see C6"); it was closed when C6 was, by
  pinning `None` and rendering "not applicable" on a zero-row workspace. C6's probe (16 checks) asserts the two
  sibling rows now **agree** on an empty workspace and that the true sentence still prints where rows exist.

#### L3-I1 — the `BackupJob` form renders **21 fields as one undifferentiated block** with machine-generated labels — a human cannot use it  [severity: Important]

- **WHERE:** `templates/core/backupjob/form.html:27-36` (the generic `{% for field in form %}` loop, copied
  from `holiday/form.html`), rendering `BackupJobForm`'s 21 fields
  (`apps/core/forms/Backup.py:38-44`). The same loop is used by `dataarchive/form.html` (18 fields) and
  `environmentinstance/form.html` (16).
- **WHAT:** Every field renders into one flat `.form-grid` (`theme.css:308`,
  `repeat(auto-fit, minmax(260px,1fr))`) with no `<fieldset>`, no section heading and no visual grouping.
  The 21 `BackupJob` fields arrive in model order —
  `name, scope_label, backup_type, frequency, retention_days, target_location, storage_tier,
  encryption_scheme, encryption_key, size_bytes, checksum, integrity_method, status, failure_reason,
  attempt_count, is_immutable, retain_until, started_at, finished_at, evidence, notes` — which interleaves
  three genuinely different concerns: **what the backup is** (`name`…`frequency`), **where/how it is stored**
  (`target_location`…`checksum`), and **how it went** (`status`…`finished_at`). A user recording a completed
  backup has to scan 21 identical-looking boxes to find `status` and `finished_at`. `retention_days` sits
  between `frequency` and `target_location` with no cue that it belongs with `retain_until` (14 fields
  later). Nothing is `required` visually except a `*`, so the two `required` storage fields are
  indistinguishable at a glance from the 19 optional ones.
- **WHY IT MATTERS:** The brief calls this out and it is real: a register of *voluntary human reporting* is
  only as good as its form. When the form is an undifferentiated wall, the honest failure is not a crash, it
  is **abandoned/incorrect records** — the same outcome the module's `unverified_count` warning exists to
  prevent. Two of the 21 labels are literally Python-derived and unhumanised — **`Copy includes pii`**,
  **`Measured rpo minutes`**, **`Measured rto minutes`**, **`Storage limit mb`** (render evidence below) —
  which reduces a mid-level form to something that looks like a database dump.
- **EVIDENCE:** Rendered `backup_job_create`, `data_archive_create`, `environment_instance_create` and
  extracted `<label class="form-label">` text + `<fieldset` count:

  ```
  backupjob     -> 21 labels, fieldsets: 0
      ['Name','Scope label','Backup type','Frequency','Retention days','Target location','Storage tier',
       'Encryption scheme','Encryption key','Size bytes','Checksum','Integrity method','Status',
       'Failure reason','Attempt count','Is immutable','Retain until','Started at','Finished at',
       'Evidence','Notes']
  dataarchive   -> 18 labels, fieldsets: 0   (…'Location','Storage tier','Format','Record count'…)
  env           -> 16 labels, fieldsets: 0
      ['Name','Kind','Tier','Source environment','Copy scope','Subset rule','Copy includes pii',
       'Masking required','Status', … ,'Storage limit mb','Is active','Notes']
  drill         -> 12 labels, fieldsets: 0   ('Measured rpo minutes','Measured rto minutes')
  ```

  Note the house pattern itself is flat — `grep -rl '<fieldset' templates/` finds exactly **one** template
  in the whole codebase — so this is not a house-pattern violation. It is a **scaling** failure: the flat
  loop is fine for `Holiday`'s 5 fields and unusable for 21. I am filing it only for the three large forms.
- **FIX:** Group the large forms into a small number of labelled sections using the existing
  `.card`/`.card-header`/`.card-body` idiom already on the page (no new CSS needed) — e.g. for `BackupJob`:
  *"What was backed up"* (`name, scope_label, backup_type, frequency, retention_days, retain_until`),
  *"Where it went"* (`target_location, storage_tier, encryption_scheme, encryption_key, size_bytes,
  checksum, is_immutable`), *"How it went"* (`status, integrity_method, failure_reason, attempt_count,
  started_at, finished_at`), *"Evidence"* (`evidence, notes`). Also add `verbose_name=` (or `label=`) to
  the four unhumanised fields so the label reads "Copy includes PII", "Measured RPO (minutes)" etc. A
  shared `{% include "partials/form_fields.html" with fields=… %}` keeps the three forms DRY.
- **Status:** [x] fixed — four commits, one file each:
  `core(0.16) I11: humanise the four machine-derived form labels` (`35030847`, `apps/core/forms/Backup.py`),
  then `… group the 21-field BackupJob form into labelled cards` (`249b3391`),
  `… the 18-field DataArchive form …` (`df738f48`), `… the 16-field EnvironmentInstance form …` (`7a5b0c03`).
  Two deliberate departures from the FIX text: the partial is the **existing** `partials/form_field.html`
  (singular — it already ships and is used across the app; the FIX text's plural name would have been a new
  file), and the **12-field drill form was left flat** — this finding is explicitly about the three *large*
  forms, and 12 fields in a flat grid is the `Holiday`-sized case the house pattern handles fine.
  Probe `temp/_0_16_i11_probe.py` (47 checks) asserts every field of all four forms still renders **exactly
  once** (a grouping change is exactly the kind that silently drops one), the four labels are humanised, the
  field *names* are unchanged, and each form still POSTs a valid payload to a 302.

#### L3-M1 — `backupjob/detail.html:48` has a dead `{% if %}` whose two branches are identical  [severity: Minor]

- **WHERE:** `templates/core/backupjob/detail.html:48`.
- **WHAT:** `<dd>{% if obj.status == "failed" or obj.is_partial %}{{ obj.get_failure_reason_display }}{% else %}{{ obj.get_failure_reason_display }}{% endif %}</dd>` — both arms render the same expression, so the condition has no effect.
- **WHY IT MATTERS:** Consequence-free at runtime (I rendered it: `warning → "Partial — some scope skipped"`,
  `success → "Not applicable"`, `failed → "Insufficient space"`), but it is misleading to the next reader —
  it *looks* like the "Failure reason" cell is conditional on failure, when the model's
  `failure_reason` default is `"n_a"` and it always has a display value. Someone will "fix" it by adding an
  `{% else %}—{% endif %}` and change behaviour they did not intend. It is the L36 doc/code-contradiction
  shape in miniature.
- **EVIDENCE:** `sed -n '48p' templates/core/backupjob/detail.html`; render probe above.
- **FIX:** Delete the `{% if %}`, leaving `{% if obj.failure_reason != "n_a" or obj.is_partial %}` if the
  intent was to hide "Not applicable" on a healthy backup — otherwise just `{{ obj.get_failure_reason_display }}`.
- **Status:** [x] fixed — `core(0.16) M5: drop the dead {% if %} in the backup-job detail` (`430dc9a5`). Took the
  bare-expression option, **not** the conditional one: the existing render already prints "Not applicable" for a
  healthy backup via `get_failure_reason_display`, so adding a condition would have changed behaviour the
  finding says nobody intended. Probe asserts the conditional is gone from the source and that a `warning` job's
  reason still renders on a 200 detail page.

#### L3-M2 — `backupoverview.html:32` shows a green **"Set"** badge when only *one* of RPO/RTO is recorded  [severity: Minor]

- **WHERE:** `templates/core/backupoverview.html:32`, fed by `has_targets` (`models/Backup.py:585`) =
  `rpo_target_minutes is not None or rto_target_minutes is not None` (an **or**), and the same key on
  `core/recoveryposture/form.html:19`.
- **WHAT:** A workspace that has set only `rto_target_minutes` renders `<span class="badge badge-green">Set</span>`
  under *"RPO / RTO targets"*, implying both are set. `recovery_drill_detail` then shows "Cannot tell" for the
  unset one, but the hub — the landing page an auditor reads first — reports a green "Set".
- **WHY IT MATTERS:** Cosmetic-but-honesty: it is a green badge standing for a partially-complete state, on
  the same hub where lane 1 found the green-zero. It does not *lie* (an `or` is what "targets exist" means)
  but the rendering collapses "both set" and "one set" into one green pill. Low consequence because the
  drill page states the missing target explicitly.
- **EVIDENCE:** `has_targets` read from `models/Backup.py:585`; `grep -n 'RPO / RTO targets' templates/core/backupoverview.html`
  → `:32`.
- **FIX:** Render the two targets separately (`RPO target: 1h / not set`, `RTO target: 4h / not set`) or use
  an amber `badge-amber` "Partly set" state when exactly one is present.
- **Status:** [x] fixed — `core(0.16) M6: stop the hub showing green "Set" for a half-set RPO/RTO` (`cd2292ba`,
  the template) + `core(0.16) M1/M6/M11: shared audit redaction, partial-target flag, in-flight count`
  (`f03587f4`, the `targets_partial` view flag). Took the amber "Partly set" option (rendered as **Partial**,
  with a `title` naming the gap) rather than splitting the row into two — the hub's `<dl>` is one row per
  figure. Scope note: the finding also names `core/recoveryposture/form.html:19` as fed by the same `or`, but
  that page is the *editor* for the targets — both fields are visible on it with their own values — so no
  change was needed there. Probe asserts Partial / Set / Not set, and that the "no target is recorded" warning
  does **not** fire when one target is set (a drill can still be judged against one).

#### L3-M3 — `environmentinstance/list.html:17-19` shows a **tenant-wide** `expired_count` above a filtered table, with no label saying so  [severity: Minor]

- **WHERE:** `templates/core/environmentinstance/list.html:17-19`, fed by `apps/core/views/Backup.py:344`
  (`expired_count = sum(1 for e in qs.all() if e.is_expired)` — deliberately the *unfiltered* set, per the
  view's own comment at `:339-343`).
- **WHAT:** The count is deliberately tenant-wide and does **not** change when the user filters. That is the
  right design (it answers "how many sandboxes has nobody reaped?", a tenant question). The defect is purely
  presentational: the `<p class="text-warn">` banner sits *inside the same `.card-body` as the `filter-bar`*,
  above the `<form method="get">`, so a user who filters to `status=active` and sees one row still sees the
  unfiltered count with nothing to say it is unfiltered. Compare `backupjob/list.html:17-19`, where the
  banner is also page-level — so this is at least internally consistent.
- **WHY IT MATTERS:** Minor and arguably by design; filed only because the brief asked whether the empty
  state / banner implies a fact it cannot know. It does not lie, it just reads as if it were scoped to what
  is on screen. `holiday/list.html`'s `text-muted` explainer above the filter bar is the house shape.
- **EVIDENCE:** `sed -n '17,19p' templates/core/environmentinstance/list.html`; view comment `:339-343`.
- **FIX:** Prefix the banner with "Workspace-wide:" (`<strong>Workspace-wide: {{ expired_count }} …`) so the
  scope is explicit, or move it below the filter bar.
- **Status:** [x] fixed — `core(0.16) M7: label the workspace-wide expired count on the environment list`
  (`c612531a`). Took the prefix option (kept the banner where it is, since the position is the house shape) and
  added a muted sentence saying it counts every environment, not just the filtered rows. `expired_count`'s
  deliberate tenant-wide semantics are untouched. Probe filters the list to a query that matches nothing and
  asserts the banner still reads "Workspace-wide:" with the true count.

---

### No-action notes

- **I did not re-file lanes 1 and 2.** Specifically I did **not** file: L1-C1 (overview green `0` — I
  re-rendered it and confirm it is real: `Never verified -> badge-green 0` on `SMOKETEST Acme`); L1-C2
  (board NULL-ordering); L1-I1/L1-I2/L1-M1..M3; L2-C1 (a `LegalHold` does not suspend the 0.8 board — see
  below); L2-I1/L2-M1/L2-M2.
- **`L2-C1` has three more template faces than lane 2 listed** — `backupoverview.html:64` (*"Preservation
  orders that suspend every retention window covering their scope"*), `legalhold/detail.html:21-22,28`,
  `legalhold/form.html:12-14`, and `legalhold/list.html:16-21`. I am **not** filing these as a new finding
  because they are the same defect (the claim) as L2-C1; I am **adding them to L2-C1's fix surface**, since
  the honest remedy lane 2 prescribed ("stop saying it suspends") must include these five template sites,
  not only `backupboard.html` and `legalhold/list.html` as lane 2 enumerated. Fixing L2-C1 in the view but
  not in these four files leaves the lie on the page.
- **`database-backup` is the only icon name this sub-module introduces**, and it is used by exactly the 3
  0.16 files. It *is* a real Lucide icon (added to the catalogue well before this build), and the CDN
  serves `@latest`, so it will resolve. **Not a finding** — flagged only so the sanity-check can be
  re-verified if the project ever pins a Lucide version instead of `@latest`.
- **`.text-warn` on a `<p>` containing `<i data-lucide="alert-triangle">` is the house shape**, not an
  invented pattern: `theme.css` defines `.text-warn` and `alert-triangle` is used by 151 templates. Verified,
  not a finding.
- **The `{% if not obj.location %} / {% elif not obj.is_restorable %} / {% elif obj.retrieval_is_async %}`
  chain on `dataarchive/detail.html:18-34` is correct and well-ordered** — a locationless archive says so
  first, a located-but-lost archive says *that*, and only a genuinely restorable async-tier archive gets the
  retrieval-timing note. This is the clearest zero-rule writing in the lane.
- **`backupboard.html` is the best page in the set** — every `None` is named (`age_days`, `never_restored`),
  every empty state states a *fact* rather than a *reassurance* (`Every catalogued archive names a
  location`), and no count hides a list. Its only defect is L3-C2's single row, which is the exception that
  proves the rule.
- **`recoveryposture/form.html` and `recovery_drill/detail.html` are honest to the letter** — the posture
  page distinguishes "Recorded"/"Not recorded" from `is_edit`, renders `rpo_display`/`rto_display` as
  "not set" rather than `0`, and the drill page's `target_notes` three-state render ("Met"/"Missed"/"Cannot
  tell") is exactly right, including the "A figure that could not be compared is not a pass" note.
- **Not in my lane:** the four modified `templates/projects/reporting/*.html` in `git status` are the 7.18
  session's (per lane 2's L45 note); I did not touch, read or commit them. I created two probe scripts under
  `temp/` and **deleted both** before finishing.

---

## Lane 4 — performance review

**Lane scope:** `apps/core/views/Backup.py` (34 callables), every `@property` in `apps/core/models/Backup.py`
and `apps/core/models/LegalHold.py`, `apps/core/forms/Backup.py`, the 21 `templates/core/` files added by this
sub-module, the 0.16 block of `apps/core/urls.py`, `apps/core/crud.py` (the `crud_list` factory), and
`seed_core.py::_seed_backup`.

**Method.** Every number below was produced on the real server (`10.4.14-MariaDB`, confirmed at runtime) via
`venv/Scripts/python.exe` with a throwaway `temp/` script, `django.setup()`, `django.test.Client` +
`client.force_login(admin_acme)`, `"testserver"` appended to `ALLOWED_HOSTS`, and
`django.test.utils.CaptureQueriesContext`. Every row-creating probe ran inside
`transaction.atomic()` + `transaction.savepoint()` and was rolled back (the one leak — the `CREATE INDEX`
DDL probe, whose implicit commit invalidated its savepoint — was cleaned up by explicit delete of the
`S#####` probe rows; all six tables are back at the seeded `3/2/1/2/2/1` counts for **both** tenants, and
`zz` probe tenants = 0). **All nine `temp/_lane4_*.py` probe scripts were deleted before finishing.**

**Verdict up front — the headline is a good one.** **There is no N+1 anywhere in this sub-module.** I
added 50 rows of *every* model and then 5,000 rows, and **not one of the six list pages, and neither board,
moved by a single query.** `select_related` is correct in all six list views and all six `crud_detail` calls,
and the two model properties that *can* hop a FK (`LegalHold.scope_label`, `RestoreRecord.source_label`) are
both prefetched at every call site. The seeder runs **zero** queries inside any loop. The defects that do
exist are the *other* two shapes the brief asked about: **unbounded full-table fetches** and **unindexed
sort columns**.

### Measured query counts

Baseline = the seeded acme tenant (`BackupJob 3`, `RestoreRecord 1`, `DataArchive 2`, `LegalHold 1`,
`EnvironmentInstance 2`, `RecoveryDrill 2`). `+50 each` = 50 extra rows of **every** 0.16 model added inside
a rolled-back savepoint. ~9 queries on every page are the session lookup, user+tenant resolution and the
branding fetch — i.e. the sub-module's own query cost is the small tail.

| page | rows (base) | queries base | queries +50 each | queries empty tenant | Δ vs rows | notes |
|---|---|---|---|---|---|---|
| `backup_job_list` | 3 | **10** | 10 | 9 | **0** | paginated, `select_related(encryption_key, performed_by)`; +1 fixed COUNT for `unverified_count` |
| `backup_job_detail` | 1 | **9** | — | — | — | +1 fixed COUNT (`restore_count`) |
| `restore_record_list` | 1 | **9** | 9 | 8 | **0** | `select_related(backup, archive, target_environment, requested_by)` |
| `restore_record_detail` | 1 | **8** | — | — | — | clean |
| `data_archive_list` | 2 | **10** | 10 | 9 | **0** | +1 fixed COUNT (`unrestorable_count`) |
| `data_archive_detail` | 1 | **8** | — | — | — | clean |
| `legal_hold_list` | 1 | **10** | 10 | 9 | **0** | `scope_label` hop is prefetched; +1 fixed COUNT (`active_count`) |
| `legal_hold_detail` | 1 | **10** | — | — | — | +1 for `conflicting_holds` (correct — see notes) |
| `environment_instance_list` | 2 | **10** | 10 | 9 | **0** | **scales in ROWS, not queries** — see L4-I1 |
| `environment_instance_detail` | 1 | **8** | — | — | — | clean |
| `recovery_drill_list` | 2 | **9** | 9 | 8 | **0** | clean |
| `recovery_drill_detail` | 1 | **9** | — | — | — | +1 posture fetch (`target_notes` itself is pure) |
| `recovery_posture_edit` | — | **10** | 10 | 10 | **0** | +2 fixed (`drill_count`, `last_drill`) |
| `backup_overview` | 3 | **20** | 20 | 20 | **0** | 11 core queries — see L4-I2 (lane 1's `L1-I2`) |
| `backup_board` | 3 | **11** | 11 | 11 | **0** | 1 query per model, sliced in Python — see L4-M1 |

**The N+1 signature is absent.** The `Δ vs rows` column is `0` for every list page. The empty tenant
costs *one query less* per list (no row query, the COUNT returns 0), which is the correct shape.

### EXPLAIN evidence

MariaDB `EXPLAIN` on the real server. The live tables hold only the seeded rows, so each shape was also
re-run inside a rolled-back savepoint holding **5,000 rows**; the `rows=` estimate and `key=` are stable
across both. `type=ALL` + `Using filesort` is the smoking gun; `type=ref` + `Using index` is the healthy shape.

| query | type | key | rows | extra |
|---|---|---|---|---|
| `backup_job_list` `ORDER BY -started_at` | `ref` | **`bkpjob_tenant_at_idx`** | 4967 | `Using where; Using index` — **served** |
| `restore_record_list` `ORDER BY -created_at` | `ref` | **`recrec_tenant_at_idx`** | 1 | `Using where; Using index` — **served** |
| `data_archive_list` `ORDER BY -archived_at` | `ALL` / `ref`* | *(none)* | 5004 | `Using where; Using filesort` — **L4-I1** |
| `legal_hold_list` `ORDER BY -issued_at` | `ALL` / `ref`* | *(none)* | 5044 | `Using where; Using filesort` — **L4-I1** |
| `recovery_drill_list` `ORDER BY -performed_at` | `ALL` / `ref`* | *(none)* | 5004 | `Using where; Using filesort` — **L4-I1** |
| `environment_instance_list` `ORDER BY name` | `ALL` / `ref`* | *(none)* | 5004 | `Using where; Using filesort` — **L4-I1** |
| `L1-C2` fix: `backup_board` `ORDER BY -created_at` | `ALL` | *(none)* | 4967 | `Using where; Using filesort` — **L4-I2**, cross-lane |
| `L1-C2` fix alt: `ORDER BY -id` | `index`/`ref` | `PRIMARY`/`bkpjob_tenant_at_idx` | **10** | **no filesort — the free fix** |
| `L1-C2` alt 2: `ORDER BY COALESCE(started_at, created_at)` | `ALL` | *(none)* | 4967 | `Using where; Using filesort` — **not a fix** |
| `backup_overview` unverified `COUNT` | `ALL` | *(none)* | 4967 | `Using where` — see notes |
| env list FULL FETCH (`expired_count`), no `LIMIT` | — | — | **5004 rows returned** | this is the L4-I1 fetch |

\* against the seeded rows the optimiser picks a `type=ref` index scan and *still* filesorts; at 5,000 rows
it degrades to `type=ALL`. Both show `Using filesort` — the ordering is never served by the index.

A `(tenant_id, created_at, id)` index **would** fix the `-created_at` shape — I created one inside the probe
and re-`EXPLAIN`ed: `key=zz_l4_test, type=ref, extra=Using where; Using index` (no filesort). That is the
evidence behind **L4-I2**.

### Findings

#### L4-I1 — Four of the six list pages sort on a column with **no usable index**, and the worst one fetches the whole tenant table twice  [severity: Important]

- **WHERE:** the four unindexed orderings —
  `DataArchive.Meta.ordering=["-archived_at","-id"]` (`models/Backup.py:286`),
  `LegalHold.Meta.ordering=["-issued_at","-id"]` (`models/LegalHold.py:81`),
  `RecoveryDrill.Meta.ordering=["-performed_at","-id"]` (`models/Backup.py:652`),
  `EnvironmentInstance.Meta.ordering=["name"]` (`models/Backup.py:509`)
  — against the declared indexes: `darch_tenant_status_idx`, `lghold_tenant_status_idx`,
  `lghold_tenant_model_idx`, `drill_tenant_outcome_idx`, `envinst_tenant_kind_idx`. **Not one of the five
  covers the column the default ordering sorts on.**
  Aggravated at `views/Backup.py:344` — `expired_count = sum(1 for e in qs.all() if e.is_expired)` —
  which evaluates the **whole** tenant `EnvironmentInstance` queryset a second time.
- **WHAT:** `crud_list` never orders explicitly, so all six list pages inherit `Meta.ordering` and every
  page is a `SELECT … WHERE tenant_id=? ORDER BY <sort col> DESC LIMIT 15`. For `BackupJob` and
  `RestoreRecord` the index happens to match the ordering (`(tenant,-started_at)`, `(tenant,-created_at)`)
  and `EXPLAIN` reports `type=ref … Using index` — **served, no filesort**. For the other four the index is
  on a *different* column (`status`/`kind`/`outcome`/`model_label`), so the optimiser cannot use it to
  satisfy the sort: at 5,000 rows it degrades to `type=ALL` and `Using filesort` — **read every row of the
  tenant, sort it in a temp table, throw all but 15 away.**
  `environment_instance_list` is the worst because it does that **twice on one request**: `:344` evaluates
  the unfiltered queryset to count `is_expired` (a Python property, `models/Backup.py:532`), and then
  `crud_list`'s `Paginator` evaluates the same queryset again for the 15-row page. Measured: **two
  separate ~1,900-character `SELECT core_environmentinstance.…` statements with no `LIMIT`**, plus the
  `Paginator`'s `COUNT(*)` — three whole-set passes for a 15-row page.
- **WHY IT MATTERS:** The brief's rule is that the *hot path* is the two boards and the six list pages —
  and this is four of the six, on the columns the pages exist to sort by. The measured cost is
  **O(rows in tenant) per page view, and 2× O(rows) for the environment list**, growing linearly with the
  register. A backup register is append-only: `BackupJob` accrues one or more rows per day forever, so
  "it is 3 rows today" is exactly the table that will not stay small. `environment_instance_list` also
  transfers **every column** (including the `subset_rule` `TextField`) twice; I measured it at 5,000 rows
  with a realistic 400-byte `notes` payload and the page took **~850 ms** vs **~65 ms** for the same page
  once `expired_count` is computed without the second full materialisation. (Wall-clock on a local XAMPP
  MariaDB is noisy — the query *shape* and the `EXPLAIN`, not the ms, are the finding.)
- **EVIDENCE:** `EXPLAIN` at 5,000 rows (rolled back), quoted verbatim:

  ```
  ### legal_hold_list ORDER BY -issued_at  [no index]
      table=core_legalhold  type=ALL  possible_keys=lghold_tenant_status_idx,lghold_tenant_model_idx
      key=None  rows=5044  extra=Using where; Using filesort
  ### recovery_drill_list ORDER BY -performed_at  [no index]
      table=core_recoverydrill  type=ALL  possible_keys=drill_tenant_outcome_idx
      key=None  rows=5004  extra=Using where; Using filesort
  ### environment_instance_list ORDER BY name  [no index]
      table=core_environmentinstance  type=ALL  possible_keys=envinst_tenant_kind_idx
      key=None  rows=5004  extra=Using where; Using filesort
  ### data_archive_list ORDER BY -archived_at  [no index]
      table=core_dataarchive  type=ALL  possible_keys=darch_tenant_status_idx
      key=None  rows=5004  extra=Using where; Using filesort
  ```

  The double materialisation, measured on `environment_instance_list` at 5,001 env rows — the full SQL
  Django issued:

  ```
   [1895 chars] SELECT `core_environmentinstance`.`id`, … , `core_environmentinstance`.`notes` FROM
                `core_environmentinstance` WHERE `core_environmentinstance`.`tenant_id` = 1     <-- no LIMIT
   [ 109 chars] SELECT COUNT(*) AS `__count` FROM `core_environmentinstance` WHERE … tenant_id = 1
   [1904 chars] SELECT `core_environmentinstance`.`id`, … FROM `core_environmentinstance` WHERE … LIMIT 15
  ```

  Row-transfer table (3,000 extra rows per model, rolled back) — `*** WHOLE TABLE, no LIMIT ***` is the
  second full fetch:

  ```
  environment_instance_list  core_environmentinstance  rows=3002  *** WHOLE TABLE, no LIMIT ***
  environment_instance_list  core_environmentinstance  rows=3002  aggregate (bounded)
  environment_instance_list  core_environmentinstance  rows=3002  paginated LIMIT
  ```

  Query count was **constant at 10** across 100/1,000/5,000 rows — confirming this is a *rows* problem,
  not a query-count problem, which is why a query-count-only sweep would not have caught it.
- **FIX:** Two halves. (a) **Add the four indexes the orderings need** — a migration adding
  `models.Index(fields=["tenant","-archived_at"], name="darch_tenant_at_idx")` on `DataArchive`,
  `["tenant","-issued_at"] → "lghold_tenant_at_idx"` on `LegalHold`,
  `["tenant","-performed_at"] → "drill_tenant_perf_idx"` on `RecoveryDrill`, and
  `["tenant","name"] → "envinst_tenant_name_idx"` on `EnvironmentInstance`. Each then shows
  `key=<new index>, extra=Using index` — no filesort — exactly as `bkpjob_tenant_at_idx` already does for
  `backup_job_list`. (b) **Make `expired_count` a single bounded query** instead of a second full
  materialisation. The view's own comment (`:339-343`) is right that `is_expired`'s rule must not be
  restated in SQL — so keep the Python predicate but feed it **`qs.values_list("expires_at", "status")`**
  rather than the full `qs.all()`: same one round-trip, two narrow columns, and the ~1,900-char whole-row
  payload (with `subset_rule`/`notes` TextFields) is never transferred. That alone removes one of the two
  full fetches; the index in (a) makes the remaining ordered read index-only.
  A `django_assert_num_queries` test cannot catch this (the count never changes) — pin it with a
  `django_assert_max_num_queries` guard plus a comment, or assert `len(response.context["object_list"]) == 15`
  alongside a captured-SQL assertion that no `core_environmentinstance` `SELECT` lacks a `LIMIT`.
- **Status:** [x] fixed — four commits: `fix(core/0.16) I5: index the three model orderings that had no index`
  (`92488f0d`), `fix(core/0.16) I5: index LegalHold's -issued_at ordering` (`37da054e`),
  `chore(core/0.16) I5: migration 0014 - the four list-ordering indexes` (`6f2de317`),
  `fix(core/0.16) I5: environment_instance_list stops fetching the whole row twice` (`3a88475d`). All four
  indexes landed as prescribed (`darch_tenant_at_idx`, `lghold_tenant_at_idx`, `drill_tenant_perf_idx`,
  `envinst_tenant_name_idx`) in migration **0014**. One departure on (b): the finding suggested
  `qs.values_list("expires_at","status")`, but `qs` is `select_related` and Django refuses to defer a relation
  it traverses, so the count reads a **fresh** queryset with `.only("id","expires_at","status")` — same two
  narrow columns, same one round-trip, and the Python predicate is still the single copy of the rule.

#### L4-I2 — The `L1-C2` fix (`ORDER BY -created_at` on `backup_board`) would **itself need a new index**; ordering by `-id` is the fix that costs nothing  [severity: Important — cross-lane]

- **WHERE:** lane 1's **L1-C2** (`review-core-0.16.md`, `views/Backup.py:539-541`), whose prescribed fix is
  *"Order by a column that cannot be NULL for a live row, e.g. `-created_at` (or `-id`)"* on
  `BackupJob`. This finding is **not** a restatement of L1-C2 — L1-C2 is a **correctness** defect (a
  queued backup is sliced off the board); this is the **performance consequence of repairing it**.
- **WHAT:** The two candidate orderings are **not** equivalent in cost, and the difference is invisible
  until you `EXPLAIN` them:
  * `ORDER BY created_at DESC, id DESC` → `type=ALL`, `key=None`, **`Using where; Using filesort`** over
    the whole tenant set. `bkpjob_tenant_at_idx` is on `(tenant, -started_at)` — it does **not** cover
    `created_at`, so MariaDB abandons it and scans. Fixing L1-C2 this way **buys a correctness bug at the
    price of a full scan on the board**, the page the brief names as a hot path.
  * `ORDER BY id DESC` → the PK is monotonic with `created_at` for an append-only register (it is
    `BigAutoField`), it is never NULL, and it is **already indexed**. Measured: **`rows=10`**, no filesort,
    on the same 5,000-row table.
  * `ORDER BY COALESCE(started_at, created_at) DESC` — the other shape L1-C2 mentions — is **also**
    a `type=ALL` + `Using filesort` full scan. It is not a fix either.
  * If `created_at` ordering is genuinely wanted, it needs
    `models.Index(fields=["tenant", "created_at", "id"], name="bkpjob_tenant_created_idx")`; with one
    created I confirmed `key=zz_l4_test, type=ref, extra=Using where; Using index` — no filesort.
- **WHY IT MATTERS:** The `code-fixer` will read L1-C2 and reach for `-created_at` because it is written
  first in that finding's fix text. Doing so **introduces** a full-table filesort on `backup_board` that
  does not exist today (today the board's `-started_at` ordering *is* index-served). The `-id` alternative
  is both the cheapest and the most honest — an append-only register's `id` **is** its insertion order, so
  "the latest ten jobs" is literally `ORDER BY id DESC`, and it cannot be falsified by a NULL the way
  `started_at` can. This is the cross-lane result the brief asked for: **the fix for L1-C2 needs no new
  index *if* it is written as `-id`, and needs a new index if it is written as `-created_at`.** File both
  the decision and the `-id` preference together, or the fix will silently regress the board.
- **EVIDENCE:** `EXPLAIN` at 5,000 rows (rolled back), quoted verbatim:

  ```
  ### L1-C2 proposed fix ORDER BY -created_at  [no index]
      key=None                       type=ALL    rows=4967     extra=Using where; Using filesort
  ### L1-C2 proposed fix alt ORDER BY -id  [PRIMARY]
      key=bkpjob_tenant_at_idx       type=ref    rows=3        extra=Using where; Using index; Using filesort
  ### L1-C2 alt ORDER BY COALESCE(started_at,created_at) - no index
      key=None                       type=ALL    rows=4967     extra=Using where; Using filesort
  ### backup_job -created_at WITH a (tenant, created_at, id) index
      key=zz_l4_test                 type=ref    rows=4967     extra=Using where; Using index     <-- fixed
  ```

  (At 5,000 rows `ORDER BY id DESC` is an `index`-type read on `PRIMARY` with `rows=10` and no filesort;
  against the 3-row seeded table the optimiser chooses a `ref` read of `3` and the `Using filesort` string
  is present but over 3 rows — the 5,000-row run is the meaningful one.)
- **FIX:** Implement L1-C2 as **`order_by("-id")`** (or `-created_at` *plus* a migration adding
  `bkpjob_tenant_created_idx`). Do not use bare `-created_at` without the index. Whichever is chosen,
  state it in L1-C2's fix so the fixer does not pick the unscanned variant by accident.
- **Status:** [x] already fixed — the C5 fix took the `-id` branch (`7e1c9c0d`, `6673ace8`, `224f7a22`), which
  is PK-served and needs no new index. Confirmed on the shipped code: both `backup_board` and `backup_overview`
  order by `-id` (`views/Backup.py:645`, `:552`), and the only `-created_at` ordering in the sub-module is
  `RestoreRecord`'s, which **has** its own index (`recrec_tenant_at_idx` — I5's work). This finding was a
  warning about a fix that was not taken; nothing further to change.

#### L4-M1 — `backup_board` fetches every row of four tables to render ten, and `unverified_jobs` is returned **unbounded**  [severity: Minor]

- **WHERE:** `views/Backup.py:539` (`list(BackupJob.objects.filter(tenant=tenant)…)`),
  `:555` (`list(DataArchive.objects…)`), `:558` (`list(LegalHold.active_for_tenant(tenant)…)`),
  `:561` (`list(EnvironmentInstance.objects…)`); the unbounded context key `unverified_jobs` at `:553`
  /`:577`, rendered by `templates/core/backupboard.html:41-51`; `archives_without_location` (`:556`/:579,
  `:89-98`); `expired_environments` (`:562`/:584, `:141-151`).
- **WHAT:** The board needs four scalar figures and three short lists. It gets them by fetching **every**
  `BackupJob`, `DataArchive`, `LegalHold` and `EnvironmentInstance` row for the tenant into Python and
  deriving everything by comprehension. Measured row-transfer at 3,000 rows per model:
  `ALL FOUR` tables come back as `*** WHOLE TABLE, no LIMIT ***`. The three list tables on the page —
  `unverified_jobs`, `archives_without_location`, `expired_environments` — are then rendered with **no
  slice at all**: if every backup is unverified, the board renders every backup on the page.
  **Is it a genuine scalability finding?** Partly, and I am filing it Minor on purpose.
  * The `job_rows` half is *bounded in output* (the `[:10]` slice) but **not bounded in fetch** — the
    `[:10]` is applied to an already-materialised Python list, so all N rows crossed the wire first.
  * The `unverified_jobs` half is **not bounded in output either** — it is a template loop over an
    unbounded list.
  * At the project's scale this is a real non-issue: the seeded tenant has 3 jobs and 2 archives. This is
    **not** a Critical and I am not filing it as one — inventing a Critical for a 3-row table is exactly
    the inflation the brief forbids. It is filed because the *shape* is the same one as L4-I1, and unlike
    the list pages there is **no `LIMIT` anywhere in it**, so it is the one place where growth is unbounded
    in the response size, not merely in the scan.
- **WHY IT MATTERS:** The board is one of the two pages the brief designates a hot path, and it is the
  page an operator leaves open and refreshes. Its cost is `O(rows in all four tables)` per refresh with no
  ceiling. The `never_restored` / `verified_total` figures genuinely do need the whole set (they are
  tenant-wide truth claims, and the view's comments at `:564-571` are right about that) — so the fix is not
  "aggregate instead", it is "aggregate the *counts*, keep the *lists* bounded".
- **EVIDENCE:** measured at 3,000 extra rows per model (rolled back):

  ```
  backup_board   core_backupjob           rows in table=3003  *** WHOLE TABLE, no LIMIT ***
  backup_board   core_dataarchive         rows in table=3002  *** WHOLE TABLE, no LIMIT ***
  backup_board   core_legalhold           rows in table=3001  *** WHOLE TABLE, no LIMIT ***
  backup_board   core_environmentinstance rows in table=3002  *** WHOLE TABLE, no LIMIT ***
  ```

  Query count stayed at **11** across 3 → 3,003 → 5,003 rows, i.e. constant queries and unbounded rows.
  The `EXPLAIN` for the board's legal-hold read is `type=ref, key=lghold_tenant_status_idx,
  extra=Using index condition; Using where` — index-served, but still every matching row returned.
- **FIX:** Keep the `list()` pattern (it is what makes each of these **one** query and keeps the
  `is_expired` / `is_verified` / `retrieval_is_async` predicates in a single place), but **bound the two
  unbounded response lists** to the same small window the page already uses for jobs — e.g.
  `unverified_jobs = [j for j in jobs if not j.is_verified][:10]` with the count alongside
  (`len(...)` computed before the slice) and a "showing the first 10 of N" line, mirroring `job_rows`'
  `[:10]`. For the four scalar counts, `jobs` etc. are already fetched, so `verified_total`,
  `archive_total` and `async_retrieval_count` are free — leave them. The genuine improvement available
  (if these tables ever grow) is to narrow the fetch with `.only("id","name","status","started_at",…)`
  so the board never pulls `scope_label`/`content_description`/`subset_rule`/`notes` TextFields it does
  not render.
- **Status:** [~] no action — accepted and documented. The finding itself calls the behaviour "acceptable at
  this project's scale", so no code changed: the board keeps its `list()` pattern (which is what makes each
  table **one** query and keeps the predicates in a single place), and the unbounded `unverified_jobs` /
  `archive_total` lists stay as they are. Recorded here so the next reader does not rediscover it as a
  surprise. If the tables ever grow, the `[:10]`-plus-count shape the FIX describes is the one to reach for.

#### L4-M2 — `backup_overview` issues four separate `COUNT(*)` on `BackupJob` and pays a full scan for the unverified one  [severity: Minor — **do not confuse with L1-I2**]

- **WHERE:** `views/Backup.py:502-508` — `jobs.count()`, `jobs.filter(integrity_verified_at__isnull=True).count()`,
  `jobs.filter(status="warning").count()`, `jobs.filter(status="failed").count()`.
- **WHAT:** This is the **measured magnitude behind lane 1's `L1-I2`**, which I am explicitly **not
  re-filing** (lane 1 already owns it, as a "reuse the list instead of re-querying" finding). My addition
  is the *index* angle lane 1 did not measure: the second of those four counts filters on
  `integrity_verified_at`, which **no index covers**, so it `EXPLAIN`s as `type=ALL, key=None,
  rows=4967, Using where` at 5,000 rows — a full scan. The other three (`tenant_id` alone; `tenant+status`)
  are served by `bkpjob_tenant_status_idx`.
- **WHY IT MATTERS:** It is the same 3-row table as everything else here, so the *practical* impact is nil
  today and I am filing it Minor for that reason. It is worth stating because it sizes L1-I2's fix
  correctly: adopting lane 1's "fetch once as a list, derive in Python" remedy removes **all four**
  round-trips *and* the unindexed scan in one change — so L1-I2 is a **cheap, high-value** fix, not a
  cosmetic one. Do **not** instead reach for a partial index on `integrity_verified_at`; the list-reuse
  fix is strictly better here.
- **EVIDENCE:** `EXPLAIN` at 5,000 rows:

  ```
  ### backup_overview unverified COUNT
      table=core_backupjob  type=ALL  key=None  rows=4967  extra=Using where
  ```

  and the full query log on the hub — **20 queries**, of which 11 touch core tables and **four are
  `COUNT(*)` against `core_backupjob`**:

  ```
  SELECT COUNT(*) AS `__count` FROM `core_backupjob` WHERE `core_backupjob`.`tenant_id` = 1
  SELECT COUNT(*) AS `__count` FROM `core_backupjob` WHERE (… tenant_id = 1 AND … integrity_verified_at IS NULL)
  SELECT COUNT(*) AS `__count` FROM `core_backupjob` WHERE (… tenant_id = 1 AND … status = 'warning')
  SELECT COUNT(*) AS `__count` FROM `core_backupjob` WHERE (… tenant_id = 1 AND … status = 'failed')
  ```

  Hub query count was **20 at 3 rows and 20 at 5,003 rows** — constant, so this is a fixed multiplication
  of round-trips, not an N+1.
- **FIX:** Lane 1's `L1-I2` fix (already filed) — do not add a second finding. If a fixer wants the
  measured justification for treating L1-I2 as worth doing: it removes **4 queries → 1** on `BackupJob`,
  **2 → 1** on `DataArchive` and takes the hub from **20 → ~12**.
- **Status:** [x] fixed — same commit as its parent finding **I3**:
  `fix(core/0.16) I3: backup_overview fetches each set once and derives in Python` (`81b1e20c`). The measured
  prediction held: the hub went **20 → 13** queries (not ~12 — the extra one is `RecoveryPosture`, which the
  finding's "~12" did not account for), and the four `COUNT(*)` on `core_backupjob` — including the unindexed
  `integrity_verified_at IS NULL` scan — are all gone. No partial index was added, as the finding advised.

### Acceptable and NOT filed (with the numbers that make it acceptable)

- **`backup_job_list` / `restore_record_list` orderings are index-served** — `EXPLAIN` returns
  `key=bkpjob_tenant_at_idx, extra=Using where; Using index` and `key=recrec_tenant_at_idx,
  extra=Using where; Using index` respectively. These are the two views whose `Meta.ordering` matches a
  declared index, and they demonstrate the pattern the other four (L4-I1) are missing. **Not a finding —
  it is the control.**
- **The junk-enum guard (`crud.py:171`, `_enum_values`) adds ZERO queries.** I instrumented it directly:
  `_enum_values(BackupJob, "status")` × 20 = **0 queries** — it is pure `_meta` introspection
  (`_meta.get_field` + the field's `choices`), no DB access. A page hit with `?status=zzz`,
  `?integrity=zzz` or `?page=99` costs **10 queries**, identical to the clean page. The guard is free.
- **`search_fields` `icontains` is a scan, and that is acceptable here.** `backup_job_list`'s
  `["name","scope_label","evidence"]` `EXPLAIN`s as `type=ALL, key=None, rows=4967, Using where` — a full
  scan, because `icontains` on a non-indexed `varchar` cannot use a B-tree. **Not filed as a finding:** the
  brief's own rule is that a full scan is a *search* behaviour, and this is the app-wide pattern
  (`crud.apply_search` is used by every list in every module) — changing it here would be a one-module fork
  of an app-wide decision. The search is user-initiated, not on page load, and the search term costs the
  same 10 queries as no term (`?q=ACME` → 9, `?q=<300 chars>` → 9). **App-wide, not 0.16's.**
- **`legal_hold_detail`'s `conflicting_holds` query is correct, not wasteful.** `views/Backup.py:304-311`
  issues exactly **one** extra query (page total 10 vs 9 for the list). It is a single `.filter()` on
  `siblings`, lazily evaluated once by the template loop, and lane 1 verified it re-derives the same
  predicate as `LegalHold.clean()` — so the duplication is deliberate (page must explain the refusal
  `clean()` will raise). One fixed query on a single-row detail page: **acceptable.**
- **`recovery_drill_detail`'s `target_notes(posture)` is pure — verified, as the brief asked.** Instrumented:
  `target_notes(posture)` → **0 queries**, `target_notes(None)` → **0 queries**. It reads
  `self.measured_rpo_minutes` / `posture.rpo_target_minutes` only. The view's one extra query (`:461`) is
  the `RecoveryPosture` fetch itself, not the comparison. Same for `LegalHold.suspends_policy(policy)` →
  **0 queries** (confirmed); it reads `self.retention_policy_id` and FK attributes, never `.filter()`.
- **Every `@property` in the two model files, instrumented one by one.** All are **pure (0 queries)**
  except two that are *FK hops*: `RestoreRecord.source_label` (→ `self.backup.name`/`self.archive.name`)
  and `LegalHold.scope_label` (→ `self.retention_policy.name`, **only** when `model_label` is blank). Both
  hop exactly **1 query** on an unloaded FK. **Both call sites prefetch:**
  `legal_hold_list`/`legal_hold_detail` `select_related("retention_policy", …)`, `restore_record_list`
  `select_related("backup","archive",…)`, and `backup_board`'s `LegalHold.active_for_tenant(...).select_related("retention_policy")`
  — I re-ran each queryset and iterated it: **0 per-row hops**. Measured the counterfactual: the same
  `LegalHold` loop *without* `select_related` costs **1 + N** (2 rows → 2 queries). So the
  `select_related` is load-bearing and present. It is the exact lesson-`tsk_detail` shape, and 0.16 does it
  right. **Not a finding.** (Note `LegalHold.age_days` → **0 queries**, `BackupJob.is_verified` → **0**,
  `EnvironmentInstance.is_expired` → **0**, `DataArchive.is_restorable`/`retrieval_is_async`/`age_days` →
  **0**.)
- **The seeder has no query-in-a-loop.** `_seed_backup` measured at **8 queries** on the idempotent run
  and **24** on the fresh run — and I read every one: the loop bodies at `seed_core.py:875-877`, `:910-911`
  are `.create()` per row over a **hard-coded 2–3 element list**, not a queryset iteration; and I proved it
  does not scale: after seeding **400 extra `BackupJob` rows** for the tenant, `_seed_backup` still issued
  **8 queries**. The `if not Model.objects.filter(tenant=tenant).exists()` guards are `.exists()` (`LIMIT 1`
  `SELECT 1 AS a`), not counts. `seed_core` full-run wall time: **0.564 s** on an already-seeded DB,
  **0.475 s** into a brand-new tenant. **No N+1, no bulk-op opportunity (the row counts are 2–3 per model,
  where `bulk_create` would be pure overhead).**
- **`crud_list` does paginate, and applies filters before the `Paginator`.** `crud.py:180` —
  `page_obj = paginate(request, qs, per_page)` with `per_page=15` default (`:22`, `:115`), and
  `apply_search`/the `filters` loop run at `:133-179`, i.e. **before** pagination as the rules require.
  All six list pages returned exactly 10/9 queries at 3 rows and at 5,003 rows — proof the `LIMIT` is
  real on every one of them. `crud_list` applies **no** `select_related` of its own (it is the caller's
  job) — and every 0.16 caller supplies one. I checked `crud.py` before blaming any view, as instructed.
- **No context key is overwritten and no `extra_context` masks a `crud_*` key** — re-confirmed
  independently of lane 1: every list page's own query cost is *fixed* (a count, or one extra fetch),
  never per-row.
- **Empty tenants cost *less*, not more** — `backup_job_list` 9 queries, `restore_record_list` 8,
  `data_archive_list` 9, all `200`. There is no per-row work that an empty tenant can trip.

### No-action notes

- **I did not re-file lanes 1–3.** Specifically: L1-C1 (green zero), L1-C2 (board NULL ordering — but see
  **L4-I2**, which is the *index consequence* of its fix, not the defect), L1-I1, **L1-I2** (I measured it
  as L4-M2's numbers but the finding stays lane 1's), L1-M1..M3; L2-C1, L2-I1, L2-M1, L2-M2; L3-C1, L3-C2,
  L3-I1, L3-M1..M3. My `L4-I1` touches `legal_hold_list`/`data_archive_list`/`recovery_drill_list`/
  `environment_instance_list` **orderings** and the `expired_count` double-fetch, none of which any earlier
  lane raised.
- **L4-I1 is *not* L1-M3 and *not* L1-C2.** L1-M3 is a seeding gap; L1-C2 is a correctness defect in one
  slice. L4-I1 is that four of the six list pages have no index for their sort column, plus a second full
  fetch on the environment list.
- **`L1-C2`'s index question is answered (L4-I2) and the answer is: BOTH options are viable, pick `-id`.**
  If the fixer writes `order_by("-id")` no migration is needed. If they insist on `-created_at`, the
  migration must add an index or the board regresses from index-served to a 5,000-row filesort.
- **Scale numbers are explicit and assumed.** "Realistic scale" in L4-I1/L4-M1/L4-I2 = **5,000 rows per
  table** in a rolled-back savepoint, and **3,000** in the row-transfer probe. I have **not** measured a
  production-like tenant, because there is none — the largest tenant in this DB has 3 jobs. Every
  "Important" above rests on an `EXPLAIN` whose `type`/`key`/`extra` I quote, not on a wall-clock.
- **Wall-clock numbers are noisy and are not the evidence.** The single 5,000-row `environment_instance_list`
  run measured ~850 ms and the same page with the second fetch removed ~65 ms, but individual runs ranged
  370–1,060 ms on this local XAMPP MariaDB. Treat the ms as illustrative; the `EXPLAIN` and the
  `*** WHOLE TABLE, no LIMIT ***` row-transfer counts are the findings.
- **The DB was left exactly as found.** The one probe that leaked rows (`CREATE INDEX` implicitly commits,
  which killed its savepoint) was cleaned by explicit delete of the `S#####` probe rows. Verified after:
  `acme jobs=3 arch=2 holds=1 env=2 drills=2 restores=1`, `globex` identical, `zz*` probe tenants = **0**.
- **Out of scope / not measured:** I did not profile the *write* paths (`crud_create`/`crud_edit`/
  `backup_job_verify`) beyond noting they are single-row; I did not measure `admin.py` (lane 1 covers it);
  and I did not attempt a concurrency/`EXPLAIN ANALYZE` profile, which MariaDB 10.4 does not support.

---

## Lane 5 — adversarial QA

**Lane scope:** *runtime* attack, not reading. Harness `temp/_0_16_lane5.py` (extends `temp/_0_16_sweep.py`)
— 114 attack rows, 101 held. Every write ran inside `transaction.atomic()` + `savepoint()` and was rolled
back; the exit check is at the bottom. Run: `venv/Scripts/python.exe temp/_0_16_lane5.py`.

**Résumé:** the **model layer held every business rule I attacked** — cross-tenant FKs through the forms,
all five anti-spoliation branches, all four `target_time` boundaries, the singleton, the enum guard, the L9
pagination guard, and every delete's `on_delete`. **Everything I broke was at the view/template seam** — and
the worst of it is that **the shipped edit path 500s for all six registers**.

### Attacks attempted and their outcomes

| # | attack | expected | actual | verdict |
|---|---|---|---|---|
| A1a | create `EnvironmentInstance` with `source_environment=<globex env>` (acme session) | 200, no row | 200, no row, foreign pk refused by the scoped queryset | **PASS — held** |
| A1b | create `LegalHold` with `retention_policy=<globex policy>` (acme session) | 200, no row | 200, no row | **PASS — held** |
| A1c | **ADMIN** create `EnvironmentInstance(tenant=acme, source_environment=globex)` | model edge refuses | **302, cross-tenant FK STORED** | **FAIL → L5-I1** |
| A1d | same, via admin, for `LegalHold.retention_policy`, `DataArchive.policy`, `BackupJob.encryption_key`, `RestoreRecord.backup` | model edge refuses | **all five STORED cross-tenant** | **FAIL → L5-I1** |
| A2a | release hold B (same `retention_policy` as active A) via **form** | refused | refused (`errors=['status']`) | **PASS — held** |
| A2b | release hold C (same `model_label` as active A) via **form** | refused | refused | **PASS — held** |
| A2c | release hold A (B policy-matches **and** C label-matches) via **form** — one-of-each | refused | refused | **PASS — held** |
| A2d | release hold D (**no** overlap: different policy, different label) | allowed | allowed (`valid=True`) | **PASS — held** |
| A2e | release hold E (neither policy nor label — blank scope) | allowed | allowed | **PASS — held** |
| A2f | release a hold via **ADMIN** while a sibling covers the same scope | model rule fires (admin calls `full_clean`) | refused, db still `active` | **PASS — held** |
| A2g | release a hold in the **same calendar minute** it was issued, via the form | allowed | **refused, wrong message** | **FAIL → L5-I2** |
| A3a | `target_time` = exactly now | accepted | accepted | **PASS — held** |
| A3b | `target_time` = 1 second in the future | refused | **accepted** (302) | **PASS-with-nuance** (see Refuted) |
| A3c | `target_time` = exactly `backup.started_at` (whole-second) | accepted | accepted (302) | **PASS — held** |
| A3d | `target_time` = 1s before `backup.started_at` | refused | refused (200, no row) | **PASS — held** |
| A4a | POST `backup_job_verify` twice, method already `checksum` | 2nd preserves method | method held `checksum`; **timestamp overwritten** | **PASS — held** (overwrite is by design) |
| A4b | audit row each POST | one per POST | 6755→6756→6757 | **PASS — held** |
| A4c | audit `action` a valid ≤10-char choice | `update` | `update`, len 6, in `ACTION_CHOICES` | **PASS — held** |
| A4d | verify a job whose method was `none` | method → `restore_test` | `restore_test` | **PASS — held** |
| A4e | verify a **failed** backup (`failure_reason=integrity_check_failed`) | refused / no OK tick | **302; detail renders green `✓ Verified`** | **FAIL → L5-I3** |
| A5a | `RecoveryPosture.tenant` uniqueness | `OneToOneField` | `OneToOneField` | **PASS — held** |
| A5b | GET the singleton with **no** row | 200, **no** row created | 200, 0 rows | **PASS — held** |
| A5c | POST the singleton with no row | exactly 1 row | 1 row | **PASS — held** |
| A5d | POST again (double-submit) | update in place, 1 row | 1 row, value updated | **PASS — held** |
| A6a | `?status=zzz&backup_type=<script>…` on all 6 lists | 200, junk ignored | 200, row count == unfiltered | **PASS — held** |
| A6b | `?q=` + 5000 chars, all 6 lists | 200 | 200 | **PASS — held** |
| A6c | `?page=-1` / `?page=99999999999999999999` / `?page=abc` / `?page=2`, all 6 | 200 | 200 | **PASS — held** |
| A7 | POST all-empty to all 6 create forms | 200 re-render, no 500 | 200; `BackupJobForm` 21 fields, `DataArchiveForm` 18 | **PASS — held** |
| A8 | create `RestoreRecord(scope=archive_retrieval, archive=<lost, no location>, status=succeeded)` via the form | L1-I1 says reachable | **302, stored** | **CONFIRMED (L1-I1), not re-filed** |
| A9a | delete a `BackupJob` with `RestoreRecord` children | 302; child survives `backup=NULL` | 302; child survives `backup=NULL` | **PASS — held** |
| A9b | delete a `DataArchive` with children; watch env/hold counts | 302; no cascade | 302; child `archive=NULL`, env 2→2, hold 1→1 | **PASS — held** |
| A9c | delete an `EnvironmentInstance` that is another env's source and a restore's target | 302; children `NULL` | 302; `source=NULL`, `target_environment=NULL` | **PASS — held** |
| A10 | build an `EnvironmentInstance` cycle A→B, B→A through the edit form | `clean()` refuses only SELF | **cycle STORED** | **FAIL → L5-I4** |
| A10b | render detail + list while the cycle exists | 200 | 200 (no chain walk) | **PASS — held** |
| A11 | all 16 0.16 GET routes as superuser `tenant=None` | 200/302/404 | 200/302/404, zero 500s | **PASS — held** |
| A12a | **ADMIN** `RecoveryDrill(outcome=passed, performed_at=None)` | model rule fires | refused, no row | **PASS — held** |
| A12b | **ADMIN** `RestoreRecord(target_time=future)` | model rule fires | refused, no row | **PASS — held** |
| A12c | **ADMIN** `EnvironmentInstance(copy_includes_pii=on, copy_scope=none)` | model rule fires | refused, no row | **PASS — held** |
| A13 | junk + page-2 + page=-1 on all 6 lists, **0-row tenant** | 200 | 200 | **PASS — held** |
| A14 | POST a **valid** payload to each of the **6** edit views | 302 → detail | **500 on all six** | **FAIL → L5-C1** |
| A15 | create (control): POST a valid payload to `recovery_drill_create` | 302 | 302, row created | **PASS — held** |

### Findings

#### L5-C1 — Every 0.16 **edit** view 500s on a valid save: `success_url` is a detail route with no `pk`  [severity: Critical]

- **WHERE:** `apps/core/views/Backup.py:124, 204, 261, 323, 384, 478` — the six `crud_edit(...)` call sites.
  Each passes `success_url="core:<entity>_detail"`, a *named URL pattern that requires a `pk`*, as a bare
  string. `crud_edit` (`apps/core/crud.py:221`) does `return redirect(success_url)` with no args, so
  `reverse()` is called without the required keyword → `NoReverseMatch`.
- **WHAT:** Every one of the six register edit pages saves the row and then **dies on the redirect**:
  `backup_job_edit`, `restore_record_edit`, `data_archive_edit`, `legal_hold_edit`,
  `environment_instance_edit`, `recovery_drill_edit`. The user sees a Django 500 page *after* the change has
  been committed, so the register silently diverges from what the operator believes they did (they will
  retry, and each retry re-saves).
- **WHY IT MATTERS:** This is the entire Edit half of CRUD — mandated by `.claude/CLAUDE.md` §"CRUD
  Completeness Rules" and covered by the contract's five `crud_edit` rows. The sub-module is **not usable**
  for its primary workflow: legal-hold release, archive status change, environment reaping and drill
  outcome are all edits. The smoke gate missed it because the sweep only **GET**s the edit pages
  (`temp/_0_16_sweep.py:113-144`) and never POSTs a valid payload to one.
- **EVIDENCE:** exact request — `POST /core/backup/drills/5113/edit/` with
  `{"name": "L5 contrast saved", "kind": "tabletop", "outcome": "not_run"}`. Exact response — **500**, and
  `drill.name` in the DB is **`"L5 contrast saved"`** (the row was saved). Last traceback frame:
  ```
  django.urls.exceptions.NoReverseMatch: Reverse for 'recovery_drill_detail' with no arguments
  not found. 1 pattern(s) tried: ['core/backup/drills/(?P<pk>[0-9]+)/\Z']
    crud.py:221 → return redirect(success_url)
    views/Backup.py:476 → return crud_edit(...)
  ```
  Contrast (control, A15): `POST /core/backup/drills/add/` → **302**. And an *invalid* payload to the same
  edit view → **200** (it never reaches the redirect). So only the successful path 500s.
  House convention is `success_url=reverse("<name>_detail", args=[pk])` — `apps/procurement/views/…/*.py`,
  `apps/projects/…`, `apps/crm/views/AnalyticsReporting/Reports.py:55`; every other `core` sub-module
  (0.8 `Privacy.py`, 0.15 `Localization.py`) sidesteps it with a `*_list` success_url. **0.16 is the only
  place in the repo that passes an unresolved bare name.**
- **FIX:** at each of the six call sites, resolve the URL with the pk first, exactly as the rest of the repo
  does — `success_url=reverse("core:backup_job_detail", args=[pk])` (the `pk` is already in scope). One-line
  change per site; no migration.

#### L5-I1 — The Django admin stores **cross-tenant FKs**, so the "model edge" is not the last line  [severity: Important]

- **WHERE:** the 0.16 admin registrations — `apps/core/admin.py:501-565`. None overrides `get_form`, and
  `EnvironmentInstanceAdmin` (etc.) `form` is Django's plain `ModelForm`, which — unlike `TenantModelForm`
  (`apps/core/forms/_common.py:41-47`) — has **no `tenant=` scoping at all**. The models themselves have no
  `clean()` rule that a linked object shares the tenant.
- **WHAT:** Five cross-tenant FKs are freely storable through the admin: `EnvironmentInstance.source_environment`,
  `EnvironmentInstance.refresh_source`, `LegalHold.retention_policy`, `DataArchive.policy`,
  `BackupJob.encryption_key`, `RestoreRecord.backup`/`archive`/`target_environment`. A workspace's sandbox can
  be recorded as a clone of **another tenant's production environment**; a hold can be pinned to another
  tenant's retention policy.
- **WHY IT MATTERS:** `forms/Backup.py`'s own docstring and the contract §3 rest the entire design on
  "*`ModelForm._post_clean` calls `full_clean`, so every `clean()` … is enforced everywhere … the seeder
  **and the admin** get it too.*" That sentence is **half true**: the admin gets the rules that exist, but
  tenant-consistency is not one of them — it lives only in `TenantModelForm.__init__`, which the admin never
  uses. The project's stated standard (and `LegalHold`'s docstring) is that the *model edge* is the one
  place a rule cannot be bypassed; here the model edge has no rule and the admin is unguarded. Severity is
  **Important, not Critical**, because reachability is limited to the `is_superuser`/`is_staff` operator
  account (`admin_acme` is `is_staff=False` and cannot open `/admin`), and supervisors are by design
  cross-tenant — but the resulting rows are cross-tenant corruption that every tenant-scoped list then
  renders as if it were local.
- **EVIDENCE:** `POST /admin/core/environmentinstance/add/` with
  `tenant=<acme.pk>, name="L5 admin XT env", kind=sandbox, copy_scope=none, status=requested, is_active=on,
  source_environment=<globex env pk>` → **302**, and
  `EnvironmentInstance.objects.filter(tenant=acme, name="L5 admin XT env").source_environment.tenant_id != acme.pk`
  is **True**. Same 302 + stored for the other four FKs (A1d). By contrast the *form* path refuses the
  identical payload (A1a: 200, no row).
- **FIX:** add a shared `clean()` to the 0.16 models (or a mixin) — for each tenant-scoped FK, refuse when
  `linked_obj.tenant_id != self.tenant_id` — so the rule sits at the model edge where the contract says it
  does; alternatively give each 0.16 `ModelAdmin` a `form = EnvironmentInstanceForm`-and-friends so the
  tenant-scoped queryset applies. The model rule is preferable (it also covers the seeder).
- **Status:** [x] fixed — `fix(core/0.16) I2: the 0.16 models refuse a cross-tenant FK at the model edge`
  (`2fd827c9`) + `fix(core/0.16) I2: LegalHold inherits the tenant-consistency model edge too` (`d4d5ebda`).
  Took the mixin option: `TenantConsistentMixin` walks every FK/OneToOne on the row and refuses a
  tenant-scoped target in another workspace with "That record belongs to another workspace." Applied to all
  six 0.16 models plus `LegalHold` (a one-way import from `Backup`). Probe `temp/_0_16_i2_probe.py` drives the
  **real admin** path that the finding proved was open, and tests both directions (the cross-tenant FK is
  refused; the same-tenant FK is accepted).

#### L5-I2 — A hold **cannot be released in the minute it was issued**, and the refusal names the wrong rule  [severity: Important]

- **WHERE:** `apps/core/models/LegalHold.py:95-97` (rule 1) reached through
  `templates/core/legalhold/form.html`'s `released_at` widget, which is `DateTimeInput(format="%Y-%m-%dT%H:%M")`
  (`apps/core/forms/_common.py:32-36`) — **minute precision, seconds are silently dropped**.
- **WHAT:** `issued_at` defaults to `timezone.now()` *with* seconds/microseconds. `released_at` can only be
  entered to the minute. So a hold created at `20:27:03` and released "now" posts `20:27:00`, and
  `released_at < issued_at` fires rule 1 → *"A hold cannot be released before it was issued."* The real
  reason (a same-minute timestamp) is never stated, and **rule 2 (anti-spoliation) is shadowed** on that path
  so the operator cannot tell which rule they hit. The hold is stuck for the remainder of the minute.
- **WHY IT MATTERS:** The single most common real correction — "wrong hold, release it" — happens within
  seconds of the issue, and is exactly the case the module's own docstring calls out ("*Release that hold
  first*"). It is refused with a message that is literally false (it *was* after issue). Any auditor reading
  the error will look for a back-dated release that does not exist. `StatutoryRule.clean`, cited as the
  pattern this mirrors, has the same shape but a `DateField` granularity, where a same-day issue/release is
  legal — this is the first time it has been paired with a `DateTimeField`.
- **EVIDENCE:** `POST /core/backup/holds/<pk>/edit/` with
  `{"name": "L5 same-minute", "status": "released", "released_at": "2026-09-22T20:27", …}`, where
  `issued_at = 2026-09-22 20:27:03.523112+00:00` → **200**, db status still `active`, page contains
  `"cannot be released before it was issued"` and does **not** contain `"Another active hold"`.
  Reproduced at the form layer: `LegalHoldForm(data, instance=h, tenant=acme).errors == {"released_at": [...]}`
  while `h.full_clean()` with a back-dated `issued_at` **accepts** the identical release (A2d/A2e).
- **FIX:** compare at the granularity the input can express, or stop the default `issued_at` from out-running
  it — either accept `released_at` truncated to the minute (`if self.released_at < self.issued_at.replace(second=0, microsecond=0)`),
  or, better, make `released_at` a `DateTimeField` whose form widget keeps seconds. The first is a one-line
  model change and cannot widen anything (a minute is the finest the UI can express).
- **Status:** [x] fixed — `fix(core/0.16) I7: a hold can be released in the minute it was issued` (`e12ca933`).
  Took the one-line option exactly as written, and reworded the refusal so it no longer misattributes the
  cause. C3's rule 1b (the `active` + `released_at` coherence rule) is preserved untouched. Probe
  `temp/_0_16_i7_probe.py` releases a hold in its own issue-minute and asserts it is accepted, while the
  genuinely-invalid earlier-than-issued release is still refused.

#### L5-I3 — `backup_job_verify` will "verify" a **failed** backup and the detail page then shows a green tick  [severity: Important]

- **WHERE:** `apps/core/views/Backup.py:138-161` (`backup_job_verify`) + `templates/core/backupjob/detail.html`
  (the `text-ok … ✓ Verified` block).
- **WHAT:** The action has **no precondition on `status`**. POSTing it to a `status="failed"` job whose
  `failure_reason="integrity_check_failed"` succeeds, sets `integrity_verified_at=now` and
  `integrity_method="restore_test"`, and the detail page then renders
  `<p class="text-ok"><i data-lucide="shield-check"></i> <strong>Verified</strong> — Sep 22, 2026 20:31</p>`
  on a record whose own status badge says **Failed** and whose failure reason is *"Integrity check failed"*.
- **WHY IT MATTERS:** This is the inverted false all-clear the whole sub-module exists to prevent — a page
  asserting a check that the record's own fields contradict. It also corrupts two derived figures: the job
  leaves `backup_board.unverified_jobs` and `never_restored`, and (with method defaulted to
  `restore_test`) it begins to read as *test-restored*. Note the 2nd POST also **overwrites** the
  verification timestamp — so a later, honest re-check cannot be distinguished from the first.
- **EVIDENCE:** `POST /core/backup/jobs/<pk>/verify/` on a job created with
  `status="failed", failure_reason="integrity_check_failed"` → **302**, `integrity_verified_at` set,
  `integrity_method="restore_test"`; `GET /core/backup/jobs/<pk>/` body contains both `text-ok` and
  `Verified`. (A4e / A15.)
- **FIX:** refuse the action when the job's own status contradicts it —
  `if obj.status in {"failed", "cancelled"}: messages.error(...); return redirect(...)` — or, minimally,
  gate the green tick in `backupjob/detail.html` on `obj.status not in {"failed","cancelled"}` so the page
  cannot assert a verification the record denies. The view guard is preferable (it also keeps the audit row
  from claiming it).
- **Status:** [x] fixed — `fix(core/0.16) I6: backup_job_verify refuses a failed or cancelled backup`
  (`43e4ba33`). Took the view-guard option, placed **before** any write so no audit row claims a verification
  that did not happen. Probe `temp/_0_16_i6_probe.py` asserts the refusal for `failed` and `cancelled`, and —
  the control — that a `success`/`warning` job is still verifiable.

#### L5-I4 — An `EnvironmentInstance` **cycle** is reachable; `clean()` refuses only the self-edge  [severity: Important]

- **WHERE:** `apps/core/models/Backup.py:517-522` (`EnvironmentInstance.clean()`) reachable from
  `environment_instance_edit` → `crud_edit` (`apps/core/crud.py:211-226`).
- **WHAT:** `clean()` refuses `source_environment == self` and `refresh_source == self`, but the FK is
  *self-referential* and nothing checks transitivity. A→B and then B→A is accepted through the shipped edit
  form. `refresh_source` has the identical hole.
- **WHY IT MATTERS:** The model's own docstring calls this FK the NetSuite/refresh chain
  ("*production or another sandbox*"). Any future template or export that walks
  `while env.source_environment:` — the obvious way to render "derived from → → production" — will
  **loop forever** on the first cycle an operator creates by accident (it is one dropdown click in the edit
  form, and the form's only guard is self-exclusion, which the user cannot even see). The brief flagged this
  as the suspected hang path; I confirmed the *state* is reachable and that **today's** pages do not walk the
  chain (`environment_instance_detail`/`_list` both render 200 with the cycle present), so the blast radius
  is the next page written, not this one. Filed Important for that reason.
- **EVIDENCE:** A→B (`source_environment=A`) then a form POST setting A's `source_environment=B`:
  `A.source_environment_id == B.pk and B.source_environment_id == A.pk` is **True** after the POST. Detail
  and list both return **200** with the cycle in place (A10/A10b). The POST's own response is a 500 from
  **L5-C1**, but the row is written first, so the cycle exists regardless.
- **FIX:** add a cycle check to `clean()` — walk `source_environment` (and `refresh_source`) upward with a
  visited set and refuse when `self.pk` reappears — or, cheaply, refuse when the proposed parent already
  descends from `self`. The walk is bounded by the number of environments in one tenant, which is small.
- **Status:** [x] fixed — `fix(core/0.16) I8: an EnvironmentInstance cycle is no longer reachable` (`315cd464`).
  Took the visited-set walk, over **both** `source_environment` and `refresh_source`, as the FIX prescribes.
  Probe `temp/_0_16_i8_probe.py` reproduces the finding's exact `A→B→A` POST and asserts it is refused, plus
  the control that a legitimate new child is still accepted (two of the probe's first-draft failures were its
  own — `_post_clean` mutating the bound instance between cases, and a fixture with no parent — both recorded
  in the probe).

#### L5-M1 — `backup_job_verify` is not idempotent: a second POST silently re-dates the verification  [severity: Minor]

- **WHERE:** `apps/core/views/Backup.py:151` — `obj.integrity_verified_at = now; obj.save(...)` runs
  unconditionally.
- **WHAT:** POSTing verify twice **overwrites** `integrity_verified_at` (confirmed: `t1=20:28:04.783843` →
  `t2=20:28:04.799468`; A4a). The method field *is* correctly preserved when already set (`checksum` held).
  So the ask "is the second POST a no-op?" has the answer **no for the timestamp, yes for the method**.
- **WHY IT MATTERS:** The stamp is the only evidence of *when* the check happened, and the operation is a
  plain POST behind a button — double-clicks and browser retries are ordinary. A re-stamp moves a
  verification forward in time and the audit trail keeps both rows with no marker distinguishing an honest
  re-check from a repeat of the first (it does write one audit row per POST — A4b — which is the mitigation,
  and why this is Minor not Important).
- **EVIDENCE:** two consecutive `POST /core/backup/jobs/<pk>/verify/` → `integrity_verified_at` differs
  between reads; `integrity_method` unchanged; `AuditLog` grows by exactly one row each time (A4a/A4b).
- **FIX:** make it a first-write-wins action — `if obj.integrity_verified_at is None: obj.integrity_verified_at = now`
  (the message and audit row can still be written), so the recorded verification keeps its original date.

### Refuted (attacks that failed — i.e. the code held)

- **A1a/A1b — cross-tenant FK through the *forms*.** Both `TenantModelForm` FK querysets are correctly
  tenant-narrowed; the identical payload that the admin accepts is refused here (200, no row).
- **A2a–A2f — the anti-spoliation rule, all five branches.** Policy-match, label-match, one-of-each and
  no-overlap all behave exactly as documented, **through the form *and* through the admin** (the admin path
  calling `full_clean` is genuinely enforced — A2f). My first pass reported a spurious failure on the
  "no-overlap" case; that was **my test's fault** (it posted `released_at` in the same minute as `issued_at`
  and hit rule 1), diagnosed and re-run in `temp/_l5_probe3.py`. The rule itself is correct.
- **A3 — `RestoreRecord.target_time` boundaries.** All four are accepted/refused exactly as the contract
  says: exactly-now **accepted**, exactly-`started_at` **accepted** (needs whole-second input — the
  `datetime-local` widget truncates, which is a UI-precision fact, not a logic defect), 1s-before
  **refused**. A **1-second-future** value *is* accepted — deliberately recorded as **defensible, not a
  finding**: the rule is "not in the future" evaluated at write time, so any sub-second skew passes, and
  there is no version of "the future" a clock comparison can exclude that a 1-hour target would not also
  exercise (an hour *is* refused).
- **A4b/A4c — the audit verb.** `action="update"` (len 6) is a valid `ACTION_CHOICES` member with the
  descriptive verb in `changes["verb"]`, exactly per contract §5.4. No truncation, no `DataError`.
- **A5 — the singleton.** `tenant` is a real `OneToOneField`; GET writes nothing; the first POST creates
  exactly one row and every subsequent POST updates in place. A double-submit cannot produce two rows — the
  `OneToOneField`'s unique constraint backstops the `filter().first()` + `save()` race, so the sequential
  double-submit is handled and the concurrent one is closed at the DB.
- **A6/A13 — junk and hostile input.** All six list pages return 200 with a **row count identical to the
  unfiltered page** for junk enums, a 5000-char `q`, `page=-1`, `page=99999999999999999999`, `page=abc`,
  `page=2`, on a **seeded** tenant and on a **zero-row** tenant. `_enum_values` (`crud.py:84-112`) and the
  `Paginator.get_page` guard (`crud.py:22-34` + `partials/pagination.html`) both hold for every one.
- **A9 — every delete's `on_delete`.** `grep on_delete apps/core/models/Backup.py apps/core/models/LegalHold.py`
  shows **no `CASCADE` except `tenant`**: every child FK is `SET_NULL`. Deleting a `BackupJob`, `DataArchive`
  or `EnvironmentInstance` therefore never cascade-destroys a `RestoreRecord`, a `LegalHold` or another
  environment — all three attacks left the children alive with a `NULL` FK and moved no unrelated count.
- **A11 — superuser with `tenant=None`.** All 16 0.16 routes return 200/302/404, **zero 500s**. The two
  hand-rolled pages that branch on `request.tenant is None` (`backup_overview` `:493`,
  `backup_board` `:533`) are joined in that safety by `crud_create`'s own guard (`crud.py:189-191`) and by
  `tenant_admin_required` on the rest, so no other route needed the branch. (This is the exact class that
  shipped an `UnboundLocalError` in the sibling sub-module — it does not recur here.)
- **A12 — model rules in the admin.** `RecoveryDrill`'s `outcome⇒performed_at`, `RestoreRecord`'s
  future-`target_time`, and `EnvironmentInstance`'s `copy_includes_pii`+`copy_scope=none` are **all**
  enforced through the admin (`full_clean` fires). The contract's claim holds for rules that exist; L5-I1 is
  the one gap.
- **A7 — form exhaustion.** All six create forms re-render at 200 with every field empty; **no field is
  required in a way that makes a form impossible to submit**. Field counts are exact:
  `BackupJobForm` **21** and `DataArchiveForm` **18** — matching the contract §3 lists. *The brief's
  "`BackupJob` has 22 form fields" is off by one against the contract itself (21); no defect.*
- **A15 (control) — `crud_create`.** All six create paths redirect 302 and persist, confirming the 500 in
  L5-C1 is specific to the `*_detail` success_url and not to the write path.

### On L1-I1 (item 8 — confirm or refute)

**Confirmed reachable, by a different route than lane 1's reading.** `POST /core/restores/add/` with
`archive=<a status="lost", location=""> archive>`, `scope="archive_retrieval"`, `status="succeeded"` →
**302, row stored** (A8). The archive field offers it (tenant-scoped, not status-scoped) and `clean()` never
consults `is_restorable`. One line, per the brief; not re-filed.

### DB state on exit

`temp/_0_16_lane5.py` opens with a baseline snapshot and closes with a diff. Final run:
`BackupJob 6→6 · DataArchive 4→4 · RestoreRecord 2→2 · EnvironmentInstance 4→4 · RecoveryPosture 2→2 ·
RecoveryDrill 4→4 · LegalHold 2→2 · AuditLog 6755→6755` — **DRIFT: none**. Probe tenants
(`slug__startswith="l5-"` and `"zz-"`) = **0**; probe users = **0**. Confirmed independently after the run
via a second process (`Tenant 5`, `acme posture 1`). Every write in this lane was inside
`transaction.atomic()` + `savepoint()` and rolled back — **the shared dev database is exactly as found.**

---

## Lane 6 — security & tenancy

**Scope.** The three questions lanes 1–5 could not answer: (1) gate coverage on all 34 routes and whether a
*plain member of the same tenant* can read the register; (2) the `tenant=None` superuser path — lanes 1/5
proved it does not **crash**, this lane asks whether it **leaks**; (3) whether `crud_list` enforces the
tenant filter itself or trusts its caller, which decides whether each of the six list `qs` is a security
boundary. Plus: sensitive-field exposure, uploads, CSRF, `|safe`, reflected params, and the seeder.

**Method.** `temp/_0_16_lane6.py`, `_0_16_lane6b.py`, `_0_16_lane6c.py` (new; modelled on
`temp/_0_16_sweep.py`). Every write ran inside `transaction.atomic()` + `savepoint()` and was rolled back;
every FK-poisoning write likewise. Needles were made **unique** (`ZZL6GLOBEX-…`) after pass 1 produced a
false positive (see Refuted R1). Actors used: `admin_acme` (acme tenant-admin), `sales_acme` (acme plain
member, `is_tenant_admin=False`), `admin` (superuser, `tenant=None`), anonymous.

---

### Guard coverage matrix (all 34 routes)

`gate` = decorators, outermost first (they are read bottom-up in source, so the outermost is the one that
runs first). `tenant-scoped?` = does the code path that resolves the object / builds the list filter
`tenant=request.tenant`?

| # | route | path | gate | tenant-scoped? | verdict |
|---|---|---|---|---|---|
| 1 | `backup_overview` | `backup/` | `@tenant_admin_required` | yes — `.filter(tenant=tenant)` on all 7 models; `:493` redirects when `tenant is None` | **HELD** — board is per-tenant, no cross-tenant aggregate |
| 2 | `backup_board` | `backup/board/` | `@tenant_admin_required` | yes — `:536` `tenant = request.tenant`, every query filtered; `:533` redirects when `None` | **HELD** |
| 3 | `recovery_posture_edit` | `backup/posture/` | `@tenant_admin_required` | yes — `.filter(tenant=request.tenant).first()` `:404`; write re-sets `posture.tenant` `:411`; `:400` redirects when `None` | **HELD** — POST as `tenant=None` created 0 rows |
| 4 | `backup_job_list` | `backup/jobs/` | `@tenant_admin_required` | yes — `:71` filter + `:87` count filter | **HELD** |
| 5 | `backup_job_create` | `backup/jobs/add/` | `@tenant_admin_required` | yes — `crud_create` sets `obj.tenant`, `:189` redirects when `tenant is None`; FK helper scopes `encryption_key` | **HELD** |
| 6 | `backup_job_detail` | `backup/jobs/<pk>/` | `@tenant_admin_required` | yes — `crud_detail` `:230` filter; `:108` count filter | **HELD** (IDOR 404, lane 5) |
| 7 | `backup_job_edit` | `backup/jobs/<pk>/edit/` | `@tenant_admin_required` | yes — `:120` pre-check filter + `crud_edit` `:213` `get_object_or_404(tenant=)` | **HELD** |
| 8 | `backup_job_delete` | `…/delete/` | `@require_POST` **outermost** → `@tenant_admin_required` | yes — `crud_delete` `:241` re-resolves `get_object_or_404(model, pk, tenant=)` | **HELD** — cross-tenant POST → 404, row alive |
| 9 | `backup_job_verify` | `…/verify/` | `@require_POST` **outermost** → `@tenant_admin_required` | yes — `:149` `get_object_or_404(tenant=)` **before** the write | **HELD** — audit row written, `action="update"` |
| 10 | `restore_record_list` | `backup/restores/` | `@tenant_admin_required` | yes — `:167` | **HELD** |
| 11 | `restore_record_create` | `…/add/` | `@tenant_admin_required` | yes — `crud_create` guard; `backup`/`archive`/`target_environment` scoped by `TenantModelForm` | **HELD** |
| 12 | `restore_record_detail` | `…/<pk>/` | `@tenant_admin_required` | yes — `crud_detail` | **HELD** |
| 13 | `restore_record_edit` | `…/<pk>/edit/` | `@tenant_admin_required` | yes — `crud_edit` | **HELD** |
| 14 | `restore_record_delete` | `…/<pk>/delete/` | `@require_POST` → `@tenant_admin_required` | yes — `crud_delete` | **HELD** |
| 15 | `data_archive_list` | `backup/archives/` | `@tenant_admin_required` | yes — `:218` + `:233` count | **HELD** |
| 16 | `data_archive_create` | `…/add/` | `@tenant_admin_required` | yes — `crud_create` + `encryption_key`/`policy`/`disposal` scoped | **HELD** |
| 17 | `data_archive_detail` | `…/<pk>/` | `@tenant_admin_required` | yes — `crud_detail` | **HELD** |
| 18 | `data_archive_edit` | `…/<pk>/edit/` | `@tenant_admin_required` | yes — `crud_edit` | **HELD** |
| 19 | `data_archive_delete` | `…/<pk>/delete/` | `@require_POST` → `@tenant_admin_required` | yes — `crud_delete` | **HELD** |
| 20 | `legal_hold_list` | `backup/holds/` | `@tenant_admin_required` | yes — `:275` + `:285` `active_for_tenant` | **HELD** |
| 21 | `legal_hold_create` | `…/add/` | `@tenant_admin_required` | yes — `crud_create`; `subject_party`/`retention_policy` scoped | **HELD** |
| 22 | `legal_hold_detail` | `…/<pk>/` | `@tenant_admin_required` | yes — `:301` + `:304` `siblings = active_for_tenant(...)` | **HELD** — `conflicting_holds` cannot cross tenants |
| 23 | `legal_hold_edit` | `…/<pk>/edit/` | `@tenant_admin_required` | yes — `crud_edit` | **HELD** |
| 24 | `legal_hold_delete` | `…/<pk>/delete/` | `@require_POST` → `@tenant_admin_required` | yes — `crud_delete` | **HELD** |
| 25 | `environment_instance_list` | `backup/environments/` | `@tenant_admin_required` | yes — `:337`; `expired_count` computed off the same tenant-filtered `qs` | **HELD** |
| 26 | `environment_instance_create` | `…/add/` | `@tenant_admin_required` | yes — `crud_create`; `source_environment`/`refresh_source` (self-FK) scoped | **HELD** |
| 27 | `environment_instance_detail` | `…/<pk>/` | `@tenant_admin_required` | yes — `crud_detail` | **HELD** |
| 28 | `environment_instance_edit` | `…/<pk>/edit/` | `@tenant_admin_required` | yes — `crud_edit` | **HELD** |
| 29 | `environment_instance_delete` | `…/<pk>/delete/` | `@require_POST` → `@tenant_admin_required` | yes — `crud_delete` | **HELD** |
| 30 | `recovery_drill_list` | `backup/drills/` | `@tenant_admin_required` | yes — `:435` | **HELD** |
| 31 | `recovery_drill_create` | `…/add/` | `@tenant_admin_required` | yes — `crud_create` | **HELD** |
| 32 | `recovery_drill_detail` | `…/<pk>/` | `@tenant_admin_required` | yes — `:460` + `:461` posture filter | **HELD** |
| 33 | `recovery_drill_edit` | `…/<pk>/edit/` | `@tenant_admin_required` | yes — `crud_edit` | **HELD** |
| 34 | `recovery_drill_delete` | `…/<pk>/delete/` | `@require_POST` → `@tenant_admin_required` | yes — `crud_delete` | **HELD** |

**34/34 routes are gated by `@tenant_admin_required` and 34/34 build their queryset with
`tenant=request.tenant`. Zero ungated routes, zero unscoped reads, zero unscoped writes.**

Router note: `crud(slug, name)` in `apps/core/urls.py:8` does `getattr(views, f"{name}_{verb}")`, so a
route cannot exist without a view and cannot be registered under a name the view does not have — the
factory makes an *ungated* 0.16 route structurally impossible to add by accident. The three hand-rolled
pages (`backup_overview`, `backup_board`, `recovery_posture_edit`) are each individually
`@tenant_admin_required`-decorated and visibly so at `views/Backup.py:397,490,525`.

**Member-reachability result (question 1).** `sales_acme` (`is_tenant_admin=False`) gets **403 on all 27
non-POST-only routes**, including all 27 read routes. The seven POST-only routes return **405** to a
member's GET (the `@require_POST`-outermost ordering working as designed — a method error outranks a role
error, per 7.7's ruling). A plain member can therefore **not enumerate one row** of backups, archives,
holds, environments, drills or the posture. Given these models carry `encryption_key` references,
`target_location` backup URIs and `LegalHold.custodian` / `matter_reference` (privileged legal-process
data), the admin-only read gate is the correct posture and it holds.

**`tenant=None` superuser result (question 2).** Measured against **unique** cross-tenant needles
(`ZZL6GLOBEX-*` stamped into every globex row):

| route class | `admin` (`tenant=None`) | leaks? |
|---|---|---|
| 3 hand-rolled pages (`overview`, `board`, `posture`) | **302 → `/`** | no — early branch |
| 6 create pages | **302 → `/`** (`crud_create` `:189-191`) | no |
| 12 detail/edit pages | **404** (no row has `tenant=NULL`) | no |
| 6 list pages | **200, 0 rows of any tenant** | no |
| 7 POST-only | **405** | no |

`ZZL6GLOBEX` occurrences in every superuser response: **0**. Result: **`.filter(tenant=None)` returns
nothing and every 0.16 view uses that filter — no view anywhere in 0.16 uses `.all()` or skips the filter.**
The two boards that aggregate (which would have been a Critical had they used `.all()`) do
`tenant = request.tenant` at `:496` and `:536` and never consult a global queryset.

**`crud_list` trust boundary (question 3).** `crud_list` (`crud.py:115`) takes `qs` as a **parameter** and
its body contains **zero** tenant logic — verified by source inspection of the post-docstring body (no
`tenant` token outside the docstring). **It trusts the caller.** So each of the six 0.16 list views'
`qs` construction is the security boundary, and all six pass the audit:

```
:71  BackupJob.objects.filter(tenant=request.tenant)
:167 RestoreRecord.objects.filter(tenant=request.tenant)
:218 DataArchive.objects.filter(tenant=request.tenant)
:275 LegalHold.objects.filter(tenant=request.tenant)
:337 EnvironmentInstance.objects.filter(tenant=request.tenant)
:435 RecoveryDrill.objects.filter(tenant=request.tenant)
```

Six of six correct. This is a **latent fragility worth recording, not a finding**: `crud_list` is a shared
one-line-per-view API and nothing in it *prevents* a future caller from passing an unscoped `Model.objects`
— but 0.16 does not, and the pattern-clone grep below is the standing check.

---

### Findings

#### L6-C1 — `TenantModelForm` leaks every tenant's `EncryptionKey` when `tenant=None`; the 0.16 views happen to be guarded, but the guard lives in the caller, not the form

- **Severity: Critical (latent — not reachable in 0.16 as shipped; reachable by any future caller that
  omits `crud_create`'s guard).** I filed it because it is the one place 0.16's isolation depends on a
  *caller* rather than on the shared boundary itself, which is exactly the class the brief asks me to
  judge.
- **WHERE** — `apps/core/forms/_common.py:52`: `if tenant is not None and isinstance(field, ModelChoiceField):`.
  The `tenant is not None` clause means an unscoped FK dropdown is the *default* when the actor is the
  `tenant=None` superuser.
- **WHAT** — `BackupJobForm(tenant=None).fields["encryption_key"].queryset` returns **all 10
  `EncryptionKey` rows across all 5 tenants**, where `BackupJobForm(tenant=acme)` returns acme's 2. Same
  for `DataArchiveForm`. The rendered `<select>` would carry every tenant's key **name and prefix**.
- **EVIDENCE** —
  ```
  BackupJobForm(tenant=acme).encryption_key queryset:           [2, 1]
  BackupJobForm(tenant=None).encryption_key queryset: [10,9,8,7,6,…] total 10
  ```
  `EncryptionKey.prefix` is the **first 10 chars of the plaintext key** (`tenants/models/EncryptionKey.py`,
  `set_secret`: `self.prefix = plaintext[:10]`) — i.e. a real credential fragment, not a label.
- **WHY IT MATTERS** — a key prefix is a meaningful oracle for anyone enumerating key material, and it
  crosses the tenant boundary, which is the one line this project does not cross. In 0.16 the path is
  **closed**: `crud_create` (`crud.py:189`) redirects when `request.tenant is None`, so the
  tenant-`None` form **never renders** — my live probe confirms all six create pages 302→`/` for `admin`
  and 0 real-tenant needles appear. `crud_edit` is likewise reached only after a `tenant=`-scoped
  `get_object_or_404`, so it cannot be entered with `tenant=None` either. The finding is therefore
  **latent in 0.16 and live in any sibling sub-module that renders a `TenantModelForm` from a view lacking
  the `tenant is None` guard.**
- **FIX** — make the shared boundary fail closed rather than delegating to the caller (`_common.py:52`):
  ```python
  # The form is only ever constructed for a real tenant; an unscoped queryset is a
  # cross-tenant enumeration surface (EncryptionKey.prefix is key material).
  if isinstance(field, forms.ModelChoiceField) and "tenant" in {f.name for f in model._meta.fields}:
      field.queryset = field.queryset.filter(tenant=tenant) if tenant is not None else field.queryset.none()
  ```
  `EncryptionKey` is a Module-0 shared model, so this is a **cross-app** fix — file it against the shared
  helper, not against 0.16 alone. Flagging per the brief ("flag it immediately… suggest a secure
  alternative"); I did **not** edit it (reviewers are read-only, Phase 5 fixes).

#### L6-I1 — 0.16's isolation rests on the caller at three seams; three sibling sub-modules inherit the same three seams (pattern-clone)

- **Severity: Important (structural; no exploitable instance in 0.16).**
- **WHERE** — (a) `crud_list` trusts its `qs` argument (`crud.py:115`); (b) `TenantModelForm` trusts its
  `tenant=` kwarg (`forms/_common.py:52`); (c) the admin has no `get_queryset` scoping
  (`admin.py:501-564`, all seven registrations).
- **WHAT** — Lane 5 already filed (c) as `L5-I1` for cross-tenant FK *writes* through the admin; I am
  **not re-filing** it. What is new here is that (a), (b) and (c) are **the same defect shape — a shared
  helper that is correct only when every caller is** — and 0.16 has 34 call sites across the three. Two of
  the three have at least one live gap outside 0.16: (b) is L6-C1, (c) is L5-I1.
- **WHY IT MATTERS** — the failure mode is silent and per-call-site: a new list view written as
  `crud_list(request, BackupJob.objects.all(), …)` compiles, renders, passes every existing test, and
  leaks every tenant. There is no test in the 0.16 suite that would catch it, because `crud_list` never
  sees `request.tenant`.
- **FIX** — two cheap standing checks rather than a refactor (the `crud_list` docstring already argues
  against changing its signature, and I agree):
  ```bash
  # 1. no 0.16 list may reach crud_list with an unscoped manager
  grep -rn "crud_list(" apps/core/views/Backup.py | grep -v "filter(tenant=request.tenant)" && echo UNGATED
  # 2. no tenant model may be fetched without tenant= outside a crud_* helper
  grep -rn "objects.get(pk=\|objects.filter(pk=" apps/core/views/Backup.py
  ```
  Both return clean for 0.16. The pattern-clone grep across the whole family:
  `grep -rn "crud_list(" apps/*/views/ | grep -v "filter(tenant="` — run it over every app; it is the
  single highest-value check for this defect class and costs one second.
- **Status:** [~] no code change — recorded as a pattern note, not a new defect (which is what the finding
  asks for: "recorded as a pattern note, not a new defect"). **Re-run at close-out on the final tree:**
  - 0.16, check 1 — `crud_list(` in `apps/core/views/Backup.py`: **6** call sites, and all **6** are fed by a
    queryset filtered `tenant=request.tenant` (`:79`, `:192`, `:244`, `:302`, `:365`, `:473`). The file also
    has **11** `filter(tenant=request.tenant)` occurrences in total.
  - 0.16, check 2 — `objects.get(pk=` / `objects.filter(pk=` in `apps/core/views/Backup.py`: **0** hits
    (the grep exits 1).
  - Family-wide — **493** `crud_list(` call sites across `apps/*/views/`. The line-based grep flags any
    multi-line call, so every flagged candidate was opened and checked: `currencies` (a global `Currency`
    with **no** tenant FK — correctly unscoped), `Generation.py` / `LineTracking.py` (tenant-scoped),
    `ReportRuns` / `ProjectReports` / `ActivityFeed` (tenant-scoped helper). **No live leak found.**
  - **Recommendation (unchanged, for the owner):** keep the two standing greps as the check rather than
    changing `crud_list`'s signature. The one thing that *would* close this class is the `TenantModelForm`
    fail-closed change — which is **C7**, escalated, because it breaks 15 committed tests in three modules.
    This finding and C7 are the same argument seen from two sides.

#### L6-M1 — `_audit_changes` is a second redaction-free twin of `crud._changed`

- **Severity: Minor.**
- **WHERE** — `apps/core/views/Backup.py:58-65`. `crud._changed` (`crud.py:270`) applies
  `_SENSITIVE_AUDIT_FIELDS` redaction; this local twin does not.
- **WHAT** — any future field added to `RecoveryPostureForm` whose name is in `_SENSITIVE_AUDIT_FIELDS`
  would be copied **verbatim** into the immutable `AuditLog.changes` by `:413`, bypassing the project's
  redaction list.
- **WHY IT MATTERS** — the audit trail outlives any later encryption-at-rest, which is the stated reason
  the redaction list exists (`crud.py:273-274`).
- **NO LIVE GAP TODAY** — verified: `set(RecoveryPostureForm().fields) & _SENSITIVE_AUDIT_FIELDS == {}`.
  The posture's eight fields are targets/regions, none secret. Filed as Minor precisely because the
  contract (§5.4) *requires* a hand-rolled audit diff here and this is the shape future maintainers will
  copy.
- **FIX** — import and reuse the shared list rather than re-deriving; one line:
  ```python
  from apps.core.crud import _SENSITIVE_AUDIT_FIELDS
  return {name: ("***redacted***" if name in _SENSITIVE_AUDIT_FIELDS
                 else str(form.cleaned_data.get(name))[:200])
          for name in form.changed_data}
  ```
  (Or promote `_changed`/`_SENSITIVE_AUDIT_FIELDS` to a public name — the sub-module docstring declines
  this because ~75 call sites say `crud._changed`; reusing the *list* alone avoids that rename.)
- **Status:** [x] fixed — `core(0.16) M1/M6/M11: shared audit redaction, partial-target flag, in-flight
  count` (`f03587f4`). Took the "reuse the list" option, not the promotion: `_audit_changes` now imports
  `_SENSITIVE_AUDIT_FIELDS` from `apps.core.crud` and redacts a match, so a field added to the one list is
  redacted on this path too — no ~75-site rename. Probe passes a stub form carrying `bank_account` and
  `password` and asserts both come back `***redacted***` while a normal field keeps its value.

---

### Refuted / held (with the command that proves it)

- **R1 — the superuser sees all six lists at 200 (≈628 KB) — is that leakage?** **No; my own needle was
  wrong.** Pass 1 searched for the bare string `Production` (globex's first environment name) and hit 21
  occurrences on every page — all of them the **sidebar's "Production Management System" module link**,
  e.g. `<a href="/core/module-scopes/?module=productionmanagementsystem">Production Management System</a>`.
  Re-run with unique needles (`ZZL6GLOBEX-*` written into every globex row across all seven models):
  **0 occurrences on all 34 routes.** The 628 KB is the sidebar + inline CSS/JS bundle, identical on the
  302 pages, not rows. *I record this because it is the exact false-positive shape a less careful pass
  would have filed as `L6-C1`.*
- **R2 — superuser `tenant=None` on the six lists returns every row.** **Refuted.**
  `crud_list` receives `Model.objects.filter(tenant=request.tenant)` with `tenant=None` → matches no row →
  200 with an empty object_list. Confirmed by row-count, not by sniffing buttons:
  no `<a href="/core/backup/jobs/<id>/">` hrefs at all (`rows: 0` for all six).
- **R3 — the two aggregating boards leak across tenants to the superuser.** **Refuted.** `backup_overview`
  `:493` and `backup_board` `:533` both branch on `tenant is None` and **302 → `/`** before any query.
  Only after that do they set `tenant = request.tenant` and filter. This was my highest-prior Critical
  candidate and it is correctly handled.
- **R4 — a member of the same tenant can read the register (privileged legal/backup data).** **Refuted.**
  All 27 read routes → **403** for `sales_acme`. Command: lane-6 pass A over all 34 routes.
- **R5 — cross-tenant FK write via the forms.** **Held** (independent confirmation of lane 5's result by a
  different route: lane 5 tested the *admin* break and the form hold; I re-tested the form with **different
  poisoned values** `ZZL6-*`). All four crafted POSTs — `environment_instance.source_environment=globex_env`,
  `legal_hold.subject_party=globex_party`, `restore_record.backup=globex_job`,
  `data_archive.encryption_key=globex_key` — re-rendered at **200 with `created=False`** and persisted
  **nothing**. The rendered dropdowns contain **0** globex options (checked by option-text regex, not by
  length).
- **R6 — `crud_delete` resolves by pk alone (cross-tenant destruction).** **Refuted, and this was the
  brief's specific worry.** `crud_delete` `:241` is `get_object_or_404(model, pk=pk, tenant=request.tenant)`.
  Live proof: `admin_acme` POSTs `/core/backup/jobs/5/delete/` (globex's job) → **404**, `Not Found` logged,
  and `BackupJob.objects.filter(pk=5).exists()` is **True** afterwards. No cross-tenant destruction.
- **R7 — the `backup_job_verify` POST-only ordering (7.7's ruling).** **Held.** `@require_POST` is declared
  **ABOVE** `@tenant_admin_required` (`views/Backup.py:132-133`, and identically on all 7 delete views).
  Measured across all four actors — GET returns **405 for anon, member, tenant-admin and superuser alike**,
  never 403. The write is tenant-scoped *before* it writes (`:149`), and it writes an audit row.
- **R8 — `AuditLog.action` overflow (varchar(10)).** **Refuted.** The only 0.16 sites are
  `:156` and `:413`, both `action="update"` (length 6) with the descriptive verb in `changes["verb"]`.
  Live audit row after a real verify:
  `action='update' (len=6), changes={'verb': 'backup_job_verify', 'integrity_verified_at': …, 'integrity_method': 'restore_test'}`.
  Zero 0.16 write puts a verb in `action`.
- **R9 — `EncryptionKey` exposure beyond `prefix`.** **Held.** Grep of `templates/core/{backupjob,
  dataarchive,backupoverview,backupboard}` for `key_hash|key\.|secret|password`: two hits, **both
  `{{ obj.encryption_key.prefix }}`** (`backupjob/detail.html:54`, `dataarchive/detail.html:53`), with a
  `…` suffix and a `—` fallback. **No template prints `key_hash`. No template prints a full key. No model
  carries a key column** (0.16 FKs `tenants.EncryptionKey`, per contract §1). Correct.
- **R10 — CSRF on every POST form.** **Held.** 21 templates, **20** `<form>` tags: 14 are POST (6 form
  pages, 6 delete forms in lists, 6 delete/verify forms in details — the verify form is
  `backupjob/detail.html:23`) and **all 14 carry `{% csrf_token %}`**; the other 6 are `method="get"`
  `filter-bar` forms, which correctly have none. **Zero POST forms without a token.** No `@csrf_exempt`
  anywhere in the changeset.
- **R11 — reflected GET params (XSS).** **Held.** `?q=<script>alert(1)</script>` and
  `?q="><script>…` driven through `q`, `status`, `page`, `backup_type`, `storage_tier`, `integrity`,
  `scope`, `kind`, `copy_scope`, `format`, `outcome` on all six lists: **raw=False** in every case,
  `&lt;script&gt;` escaped in the four that echo `q`. Django autoescape intact.
- **R12 — `|safe` / `mark_safe` / `autoescape off` / `.raw(` / `.extra(` / `RawSQL` / `os.system` /
  `subprocess` / `eval(` in 0.16.** **Zero hits** across `models/Backup.py`, `models/LegalHold.py`,
  `forms/Backup.py`, `views/Backup.py`, the migration, the admin block and all 21 templates. The migration
  has no `RunSQL`. The 14 `onsubmit` handlers are **static string literals with no interpolation**
  (`onsubmit="return confirm('Delete this record?');"`), so the L42 class cannot occur here.
- **R13 — uploads / `MEDIA_ROOT`.** **Held — 0.16 adds no file handling.** Grep for
  `FileField|ImageField|request.FILES|ContentFile|upload_to|MEDIA_ROOT` across the four 0.16 backend files:
  **no matches**. `crud_create`/`crud_edit` do pass `request.FILES` into the form, but no 0.16 form has a
  file field, so nothing can be uploaded. The `.svg` allow-list drift and the unauthenticated
  `MEDIA_ROOT` issue cannot be reached from this sub-module.
- **R14 — the seeder writes sensitive data / can clobber a real record.** **Held on both counts.**
  *(sensitive)* The only non-obvious values are clearly-marked fakes: `target_location="s3://acme-backups/…"`,
  `location="glacier://acme-archive/2024/activity.parquet"`, `checksum="sha256:9f2c…"` (truncated with `…`),
  `dr_plan_reference="Confluence / OPS / DR-Plan-2026"`, court `matter_reference="CASE-2026-0042"`. **No
  real-looking key is written** — the seeder only *reads* the tenant's existing `EncryptionKey`
  (`EncryptionKey.objects.filter(tenant=tenant).first()`, `seed_core.py:841`) and never creates one. No
  real person's name appears (parties are `Acme`/`Initech`-style demo strings from the shared `PEOPLE` list).
  *(clobber)* Every entity is guarded per-entity with `.filter(tenant=tenant).exists()` → create-only
  (`:845`, `:884`, `:898`, `:908`, `:934`), plus **`get_or_create`** for the `RecoveryPosture` singleton
  (`:878`). No `.delete()` and no `.update()` anywhere in `_seed_backup`. A re-run on a tenant that already
  has real rows creates **nothing** — so the seeder can never overwrite a real backup record, archive
  location, legal hold or posture. Re-ran the seeder logic path twice in the sweep (lane 1 / `_0_16_sweep.py`)
  with row counts unchanged.

**Pattern breaks worth naming explicitly.** `crud_detail`, `crud_edit` and `crud_delete` **do** re-resolve
with `tenant=` (a genuinely good design — the `pk` is never trusted alone). `crud_create` **does** refuse a
tenant-less actor. The 7 POST-only routes **do** put `@require_POST` outermost. The two boards **do** branch
before querying. There is no route in this sub-module where the isolation depends on the UI hiding a
button — every gate is server-side and every object fetch is tenant-scoped.

**Overall judgement.** The tenancy posture of 0.16 is **clean and I can state that without qualification**:
34/34 routes admin-gated, 34/34 tenant-scoped, 0 cross-tenant reads, 0 cross-tenant writes, 0 key-material
exposure, 0 unescaped reflection, 0 CSRF gaps. The one Critical (L6-C1) is a **latent** upstream defect in a
*shared* module-0 helper, not a 0.16 bug: 0.16's `crud_create` guard happens to close it, and the correct
place to fix it is `forms/_common.py:52`, so that the next sub-module inherits the closure instead of the
hole.

### DB state on exit

Baseline snapshot taken before the first probe; re-read after the last.

`Tenant 5 · BackupJob 6 · DataArchive 4 · RestoreRecord 2 · EnvironmentInstance 4 · RecoveryDrill 4 ·
LegalHold 2 · RecoveryPosture 2 · AuditLog 6755` — **identical to lane 5's exit state, i.e. unchanged.**
Probe tenants matching `slug__startswith="zz"` = **0**; probe users = **0**. The only FK-poisoning writes
(`ZZL6GLOBEX-*`, `ZZL6KEY-*` into globex rows, and `ZZL6-*` probe rows) were inside
`transaction.atomic()` + `savepoint()` and rolled back; re-read after rollback confirms the original values
(`LegalHold.matter_reference = "CASE-2026-0042"`, globex key names `Primary API Key` / `Data-at-Rest Key`).
**The shared dev database is exactly as found.** Probe scripts remain at `temp/_0_16_lane6.py`,
`temp/_0_16_lane6b.py`, `temp/_0_16_lane6c.py`.

---

# CONSOLIDATED FINDINGS — 0.16 Backup, Recovery & Data Lifecycle

Six lanes, strictly serial. **31 findings: 8 Critical, 11 Important, 12 Minor.** Lane-local ids are mapped
to canonical `C#/I#/M#` below; the lane sections above retain their own ids.

Method note (proven on 7.10, reused here): each lane was given the already-fixed defects as **sanity-checks**
rather than findings, returned its section as text which the orchestrator appended, and used lane-local ids.
The orchestrator then **independently re-verified every Critical and every load-bearing Important** with its
own probe — including re-deriving the MariaDB NULL ordering rather than trusting lane 1's query, and re-running
the `RestoreRecord` edit path that lane 3's finding depends on. Three severities were re-set on evidence; two
lane claims were corrected. The orchestrator's verification of each item is recorded in the block below.

## Critical (7 found in review + C8 found during the fix pass = 8)

| id | title | lane src | verified by orchestrator |
|---|---|---|---|
| **C1** | **Every one of the six 0.16 EDIT views 500s on a valid save** — `success_url="core:<entity>_detail"` is a pk-taking route passed as a bare, unresolved string to `crud_edit`, which does `redirect(success_url)`. The row is **committed first**, so the register diverges from what the operator believes they did. | L5-C1 | **YES — reproduced.** `POST /core/backup/jobs/<pk>/edit/` → `NoReverseMatch: Reverse for 'backup_job_detail' with no arguments not found`. Gap in my own smoke gate: `temp/_0_16_sweep.py` only **GETs** edit pages, never POSTs a valid payload. |
| **C2** | **A `LegalHold` does not suspend the 0.8 retention schedule, but four 0.16 pages and the model docstring say it does.** `LegalHold.suspends_policy()` has **zero call sites**; `retention_board` never imports `LegalHold`. Board reports "N rows past their window" and names no hold. | L2-C1 | **YES — reproduced.** Created a hold on the same scope as `core.ConsentRecord`'s policy (`suspends_policy()` → `True`), aged 6 rows: board printed **"Rows past their window: 6"** with an amber badge and the hold named **nowhere** (`"suspend" not in body`). This is the spoliation the model exists to prevent. |
| **C3** | **`legalhold/detail.html` renders "Not in force … the retention schedule … has resumed" for a hold whose own badge on the same page says Active.** `is_active` is `status=="active" and released_at is None`, so `status="active"` + `released_at` set takes the `{% else %}` branch. | L3-C1 | **YES — reproduced, and reachable through the SHIPPED EDIT FORM.** My first probe (create path) was **refused** by `clean()` — `released_at` before `issued_at`. But **editing an existing hold whose `issued_at` is in the past and setting `released_at` leaves `status="active"` and the form ACCEPTS it** (`is_valid() == True`). Banner: *"Not in force — Active as of … The retention schedule covering workspace-wide has resumed."* Badge: **Active**. Severity **Confirmed Critical** — the reachable path is the ordinary one. |
| **C4** | **`backup_overview` prints a GREEN `0` badge** for "Never verified" and "Unrestorable archives" on a workspace with zero rows — a false all-clear on the compliance hub, contradicting `backup_board` one page over. | L1-C1 | **YES — reproduced.** A freshly-provisioned tenant's real `/core/backup/` renders `Never verified</dt><dd><span class="badge badge-green">0</span>` and the same for "Unrestorable archives". |
| **C5** | **`backup_board`'s "Latest ten jobs" cannot show an in-flight backup.** `Meta.ordering=["-started_at","-id"]` + a just-created `status="queued"` backup has `started_at=NULL`, and **MariaDB sorts NULLs LAST under `DESC`** — so the newest work sorts to the bottom and is sliced off by `jobs[:10]`. | L1-C2 | **YES — mechanism and threshold both reproduced.** Server is `10.4.14-MariaDB`; raw probe confirms NULLs last under `DESC`. **Exact break point measured by the orchestrator: with ≥10 finished backups the queued job is absent from `jobs[:10]`** (9 finished → shown; 10 finished → **not** shown). The `note` chain also has no branch for `queued`/`running`. |
| **C6** | **`backup_board` asserts "0 — all records carry a readable verification state" on a workspace with zero records** — a claim about the members of an empty set, from a hard-coded `unverifiable_count = 0` that is always falsy. | L3-C2 | **YES — same shape as C4, different page and key**, so not a duplicate. The `never_restored` row two lines above gets it right ("not applicable"). |
| **C7** | **`TenantModelForm` skips FK scoping entirely when `tenant is None`**, so a tenant-less form's `encryption_key` queryset spans **all tenants**, exposing `EncryptionKey.prefix`. **Latent for 0.16** (no 0.16 route reaches it — `crud_create` redirects tenant-less actors) but it is a **shared Module-0 helper**, so every sibling sub-module inherits the hole. | L6-C1 | **YES — measured.** `BackupJobForm(tenant=None).fields["encryption_key"].queryset.count()` → **10** (all tenants) vs **2** (acme-scoped), and the leaked choices print other tenants' prefixes. Fix belongs at `forms/_common.py:52`, not in 0.16. |
| **C8** | **`backup_overview`'s five-row "Recent backup jobs" preview cannot show a queued backup** — **the same defect as C5, on the hub rather than the board.** `jobs = BackupJob.objects.filter(tenant=tenant)` relied on `Meta.ordering = ["-started_at", "-id"]` and `recent_jobs = jobs.select_related("encryption_key")[:5]` sliced five rows off it; a just-queued backup has `started_at=NULL`, MariaDB sorts NULLs LAST under `DESC`, so the newest work sorted below every finished job and fell off the window — silently, with no empty state and no gap marker. | *(found during the fix pass, not by a lane)* | **YES — measured by code-fixer.** With the pre-fix query the preview returned the five newest *finished* jobs and the queued row was absent; with `-id` ordering it is first. Fixed in `81b1e20c` (I3's commit) by ordering `-id` and taking in-flight rows first, exactly as C5's fix does on the board. **Found by:** code-fixer |

## Important (11)

| id | title | lane src |
|---|---|---|
| **I1** | A `RestoreRecord` can record a **succeeded** restore from an archive its own page calls unrestorable — `clean()` never consults `DataArchive.is_restorable`; the seeder plants the bait ("Legacy CRM export (media lost)"). **Lane 5 confirmed reachable through the real form (302, row stored).** | L1-I1 (L5) |
| **I2** | The **Django admin stores cross-tenant FKs** (8 of them) — plain `ModelForm` has no `tenant=` scoping and no model `clean()` requires a linked object to share the tenant. | L5-I1 |
| **I3** | `backup_overview` re-derives every count with a second query instead of reusing the lists it holds; `environments` is materialised **twice**. Measured: **20 queries** vs `backup_board`'s 11. | L1-I2 (L4-M2) |
| **I4** | The `L1-C2`/C5 fix, if written as `-created_at`, **needs a new index**; `-id` is free. | L4-I2 |
| **I5** | Four of six list pages **sort on a column no declared index covers** (`-archived_at`, `-issued_at`, `-performed_at`, `name`); the environment list also evaluates the whole tenant queryset twice. | L4-I1 |
| **I6** | `backup_job_verify` will "verify" a **failed** backup, after which the detail page shows a green ✓ over a failed job. | L5-I3 |
| **I7** | A hold **cannot be released in the minute it was issued** (`released_at < issued_at` compares strictly), and the error message misattributes the cause. | L5-I2 |
| **I8** | `EnvironmentInstance` **cycles** are reachable — `clean()` refuses only SELF (`A→B→A` is accepted). | L5-I4 |
| **I9** | A contract §5.1 error that is a **trap for the next entity**: `crud_list` does **not** derive `*_choices`; every 0.16 view passes them by hand. A future caller following the contract gets a silently empty filter dropdown. | L1-M1 |
| **I10** | Three seams (`crud_list`'s qs, `TenantModelForm`'s tenant kwarg, the admin queryset) are correct **only when every caller is** — the same hole as C7 seen as a pattern. Recorded as a pattern note, not a new defect. | L6-I1 |
| **I11** | `BackupJobForm`'s **21 fields render as one flat block** with unhumanised labels; likewise archive (18) and environment (16). | L3-I1 |

## Minor (12)

| id | title | lane src |
|---|---|---|
| **M1** | `_audit_changes` omits `_SENSITIVE_AUDIT_FIELDS` redaction (no live gap: posture form ∩ sensitive list = ∅). | L6-M1 |
| **M2** | `seed_core` runs **before** `seed_tenants`, so `EncryptionKey` never exists on a fresh seed and every seeded backup/archive gets `encryption_key=NULL`; the per-entity guards never backfill. | L2-M2 |
| **M3** | `crud()` call-site naming diverges: 0.16 uses snake_case (`backup_job`) where the 8 existing spine calls use concatenated lowercase (`partyrole`). All 34 names reverse; no breakage. | L2-M1 |
| **M4** | `backupboard.html:25` — see C6. *(Folded into C6.)* | L3-C2 |
| **M5** | `backupjob/detail.html:48` has a dead `{% if %}` whose two branches render the same expression. | L3-M1 |
| **M6** | `backupoverview.html:32` shows a green **"Set"** badge when only **one** of RPO/RTO is recorded (`has_targets` is an `or`). | L3-M2 |
| **M7** | `environmentinstance/list.html` shows a **tenant-wide** `expired_count` above a **filtered** table with no label saying so. **The semantics are deliberate and correct** (the view comments why); the defect is the labelling, so this is presentational only. | L3-M3 |
| **M8** | `backup_board` fetches **every row** of four tables (no `LIMIT`) to show ten; `unverified_jobs` is unbounded. Acceptable at this project's scale, recorded so it is not rediscovered as a surprise. | L4-M1 |
| **M9** | Contract §7 lists no `_seed_recovery_posture`; the seeder seeds the singleton anyway. Contract/code drift. | L1 |
| **M10** | `models/Backup.py:32` still says *"see `Compliance.py`"* — the file the contract's own correction proved **does not exist**. | L1-M2 |
| **M11** | The seeder plants no `started_at=None` job, which is exactly why C5 survived a green sweep. Fixing the seeder closes the test blind spot. | L1-M3 |
| **M12** | Contract says "29 url names"; the code registers **34 routes**. A naming ambiguity worth one clarifying line (some names are reached via `crud()`). | L1 |

## Orchestrator notes on lane quality

- **Two lane claims were corrected.** (a) Lane 1's C5 evidence asserted the queued job is invisible "once a
  tenant has more than ten finished jobs" — I measured the boundary precisely: it is **≥10 finished**, and at
  15 the job was in fact still present in that lane's own ordering because the slice it printed did not match
  the view's. The *mechanism* was right; the *threshold and demonstration* were wrong and are restated above.
  (b) Lane 3's C5/C3 writeup implied the inconsistent `active`+`released_at` state was reachable from the
  create form; my probe shows the create form **refuses** it and only the **edit** path reaches it. The
  finding survives, the reachability story is corrected.
- **Severity re-set on evidence:** C7 was filed as Critical-latent by lane 6. I kept it Critical **because it
  is a shared helper**, but recorded explicitly that 0.16 cannot reach it — a reader must not go hunting for
  a live leak in 0.16.
- **The strongest lane result is a negative one:** lane 4 measured **no N+1 anywhere** (Δ vs rows = 0 at 50
  and at 5,000 rows, on all 15 pages), and lane 6 found **34/34 routes gated and tenant-scoped with zero
  cross-tenant reads or writes**. Both are reported with the commands that establish them.
- **Carried, not folded in.** C7 and I9/I10 are shared-Module-0 matters (`forms/_common.py`, the contract
  template). They are **fixed here where the fix is safe** but they are cross-module items, not 0.16 defects.
  The pre-existing `AuditLog.action` overflow sites elsewhere in `apps/` remain carried (0.16 adds **zero**
  violations — re-verified by grep).
- **Three stray probe tenants exist on the dev DB** (`lane5-empty`, `smoke-empty`, and a nameless
  `SMOKETEST Acme`) from earlier sessions. **Not deleted** — they are not mine and deletion is destructive.
  Flagged for the user.

---

# PHASE 5 — FIXES APPLIED (6 of 7 Criticals closed; C7 escalated on evidence)

Each Critical was fixed **and then re-verified with its own independent probe**, written fresh rather
than reusing the lane's evidence. Every probe is a plain script under `temp/` that builds its own
workspaces inside savepoints and rolls them back, so the shared dev DB is untouched. One file per
commit throughout; nothing pushed.

**C7 is the exception and is NOT closed.** Its probe found one live leak (fixed) *and* found that
fixing the shared helper breaks 15 committed tests across three modules, so that half was reverted and
the issue escalated for a Module-0-wide decision. Read its section below before reporting C7 as fixed.

| id | fix commits | independent probe | what the probe establishes beyond "it passes" |
|---|---|---|---|
| **C1** | `15dbf2a6` | `temp/_0_16_post_sweep.py` | POSTs a valid payload to all six edit views and asserts **302 + DB persistence**, not just a 302. Closes the blind spot in my own smoke gate, which only GET-tested edit pages — that gap is *why* C1 survived a green sweep. |
| **C2** | `e73d9930`, `68206458` | `temp/_0_16_sweep.py` (re-run) | Board drops to **0 rows past their window** and names the hold; verified against a hold whose `suspends_policy()` is `True`. |
| **C3** | `520a4b0f`, `9c380e77` | `temp/_0_16_c3_probe.py` — 25 checks | Tests **both halves and the controls**: the rule refuses the incoherent state *and* accepts all four legitimate ones (a rule that refuses everything would pass the refusal test); the four template branches render four different claims; the pre-rule row is written around `clean()` with `.update()` so the template's third state is exercised. |
| **C4** | `c4b563f7`, `d8efd503` | `temp/_0_16_c4_probe.py` — 31 checks | The control is the point: a **legitimate green `0` must still render** on a populated workspace. Also pins a row satisfying **both** disjuncts of `Q(location="")|Q(status in lost,destroyed)` as counted **once** — acme's archive #2 is such a row, and the probe's first draft double-counted it. **The probe was wrong; the view was right.** |
| **C5** | `7e1c9c0d`, `6673ace8`, `224f7a22` | `temp/_0_16_c5_probe.py` | **Reproduces the defect first**, using the pre-fix query on the very workspace it then measures the fix on (10 finished + 1 queued → old query returns ten rows, queued absent). Pins the **9-vs-10 boundary**, the NULL ordering on the live server (`10.4.14-MariaDB`), and that a `cancelled` job is *settled*, not in flight. |
| **C6** | `668ae0fb`, `09c8bc5d`, `3a31f2b5` | `temp/_0_16_c6_probe.py` — 16 checks | Asserts the two sibling rows now **AGREE** on an empty workspace (the actual defect) rather than merely that a string vanished, and that the true sentence is still printed where rows exist. |
| **C7** | `c20ad27e` **REVERTED** by `68ebb8eb`; live leak closed by `2cf76bd4` | `temp/_0_16_c7_probe.py` | **Enumerates all 619 `TenantModelForm` subclasses** (652 forms modules imported) instead of spot-checking, and asserts the security invariant directly: *a tenant-scoped `ModelChoiceField` must never hold rows from more than one tenant*. **1130 fields inspected across 618 instantiable forms.** The sweep found **one live leak** — and also found that fixing the base class **breaks 15 committed tests across three modules**. The base-class change was therefore reverted and the issue **escalated, not fixed**. See below. |

## C7 — ESCALATED, NOT FIXED. The shared-helper change was reverted on evidence.

C7's probe found **one live leak** and closed it. It also found that fixing the base class breaks
**15 committed tests across three modules**, so that half was reverted (`68ebb8eb`).

### The live leak: FIXED in the form that leaked (`2cf76bd4`)

`ProjectIntegrationConnectorForm.__init__` built `User.objects.filter(is_active=True)` and applied the
tenant filter only `if self.tenant is not None`, so a tenant-less form offered **every** workspace's
active users. Measured before the fix: **28 rows, 6 distinct tenant values**, and since `User.__str__`
returns the email, the `<select>` rendered `admin@globex.example`, `admin@lane5-empty.example` and
others. Reachable: `ixc_create` carries only `@login_required` (no tenant guard) and the superuser
`admin` holds `tenant=None` by design.

Fixed by adding the missing `else: owner_qs.none()` — written out in full so it depends on nothing.
**This half is independent of the revert** and is not affected by it.

### The other half: why the base-class change was wrong as a 0.16 side effect

Measured, same 4,866-test corpus, only the base class differing:

| | tests | failures |
|---|---|---|
| with the `_common.py` change | 4,866 | **19** |
| reverted | 4,866 | **4** |
| **introduced by the revert** | | **0** |

15 tests were broken by the change, across `inventory` (3), `procurement` (6) and `projects` (6) — and
**0 new failures** came from reverting it. The change was a net negative.

Those modules use a deliberate **two-layer** design, and my change silently disabled layer 2:

- **Layer 1** — the create/edit view hoists `request.tenant is None` and redirects, so a tenant-less
  form is unreachable from the UI.
- **Layer 2** — `_reject_foreign(form, cleaned, [...])` in `clean()` rejects a foreign record with a
  **precise** message: *"That record belongs to another workspace."*

Layer 2 requires the queryset NOT to be pre-narrowed, because Django validates `ModelChoiceField` in
`Field.clean`, which runs **before** `Form.clean`. An emptied queryset short-circuits at field level and
the operator gets Django's generic *"Select a valid choice. That choice is not one of the available
choices."* — so the change made their validation **worse**, not better.

The tests say so themselves. `test_reqmgmt_forms.py`:

```
# Layer 2 (_reject_foreign): with the queryset NOT pre-narrowing the choices, the
# hand-posted foreign pk must still land as the exact rule message.
```

and `test_initiation_forms.py`, whose docstring is an explicit warning to whoever tries this:

```
"""CURRENT, DOCUMENTED behaviour, pinned so a regression is visible either way."""
```

### The decision

**"Where does tenant isolation live — in the form or in the caller?" is an architecture decision with
two defensible answers**, three modules have committed to the second, and 0.16 cannot reach the path
either way (this document itself records C7 as latent for 0.16). Overturning that as a side effect of a
0.16 close-out is exactly the cross-module change the house rules say to **carry**, not fold in.

**C7 therefore stays OPEN as a latent shared-helper issue.** It is not a 0.16 defect and must not be
reported as fixed.

### Proposed plan for the owner (needs a Module-0-wide decision, not a 0.16 fix)

1. Add an explicit opt-out to `TenantModelForm`, e.g. `allow_unnarrowed_when_tenantless = False`, so
   **safe is the default** and loose scope becomes a declared choice rather than an accident.
2. Set the flag on the ~7 forms in `projects` / `procurement` / `scm` / `inventory` that deliberately
   rely on layer 2, so their precise messages survive.
3. Leave `_reject_foreign` in place — with the flag it becomes a genuine second layer instead of the
   only layer.
4. Re-run the 4,866-test corpus; the 15 currently-pinned tests should pass unchanged, which is the
   signal that the migration was faithful.

**Also worth noting from the sweep:** the two designs are not equally safe. Layer 1 alone fails silently
when a view forgets the guard — which is exactly what happened in the connector form — whereas
narrowing fails safe. A form reachable without a tenant must narrow explicitly. That is the rule the
connector fix follows.

### A related pre-existing defect the sweep surfaced

`apps/inventory/tests/test_uom_forms.py::test_foreign_uom_rejected` expects `"another workspace"` in the
errors and gets Django's generic message instead. It fails **identically at the pre-session baseline**
(`44c72ec3`, verified in a git worktree), so it is **pre-existing and not 0.16's** — but it is the same
shape: a field that happens to be narrowed, so `_reject_foreign` never fires and the precise message is
lost. It is evidence that layer 2's message is fragile wherever narrowing and `_reject_foreign` coexist.
Worth folding into the same plan.

## Pre-existing failures, proven not ours

Four tests fail in this session's runs and **fail identically at the pre-session baseline `44c72ec3`**
(verified by checking out `44c72ec3` in a git worktree and re-running them there):

- `apps/inventory/tests/test_uom_forms.py::test_foreign_uom_rejected`
- `apps/scm/tests/test_forms.py::TestMeterReadingForm::test_a_valid_reading_saves_with_the_default_provenance`
- `apps/scm/tests/test_forms.py::TestMeterReadingForm::test_a_crafted_provenance_pair_is_ignored_entirely`
- `apps/scm/tests/test_integration_views.py::TestIntegrationWebhookSubscriptionList::test_integration_subscription_list_junk_filter_value_is_an_empty_200` (all 3 params)

Reported with provenance rather than "fixed" (L45). The two `MeterReadingForm` failures are a
**future-dated `read_at`** — a clock-dependent test, not a scoping defect.

## Two probe errors worth keeping

Both were mine, not the code's, and both are recorded because the same mistake is available to anyone
writing the next probe:

1. **C4**: computing a count by subtraction (`total - complement`) **double-counts** a row satisfying two
   OR'd conditions. acme's archive #2 has `location=''` **and** `status='lost'`, so the view's `filter()`
   correctly returns 1 while the complement arithmetic returned 2. Fixed by computing in Python with a
   row-wise `sum()`.
2. **C7**: asserting "no choice label is truthy" fails on Django's standard blank choice, whose label is
   `'---------'`. Replaced with the actual security claim — *no other tenant's `EncryptionKey.prefix`
   appears among the labels* — which cannot produce that false failure.

Also worth recording as a **probe-infrastructure** gotcha: `response.context` is `None` in a plain
script without `django.test.utils.setup_test_environment()`. A `TestCase` calls it for you; a bare
script does not, and the failure mode is a `TypeError` on subscripting `None` rather than a silent
pass — lucky, but not something to rely on. Every `temp/_0_16_c*_probe.py` now calls it explicitly.

## Still open

**C7 is escalated, not fixed** (see its own section above) — it needs a Module-0-wide decision. It is the
**one** open item in this document.

**11 Important, 12 Minor** — all 23 are now resolved (Phase 6 below): **19 fixed by code**, **2 closed as
already-fixed** (I4, M4), **1 recorded as a pattern note with no code change** (I10), and **1 explicitly
accepted with no action** (M8). The Criticals were done by hand rather than delegated, because each needed
an independent probe and several needed a judgement the lane reports did not contain (C5's ordering
choice, C7's blast radius). The Important and Minor findings were burnt down in one `code-fixer` pass.

---

# PHASE 6 — IMPORTANT & MINOR BURN-DOWN (one `code-fixer` pass)

All 23 findings in the consolidated tables were worked **in ID order** — every `I#` first, then every
`M#` — and each finding's own detail section above now carries a `- **Status:**` bullet naming its
commit(s) and any departure from the prescribed FIX. House rules held throughout: **one file per commit**,
nothing pushed, no `--no-verify`/`--amend`/`commit -a`, no test weakened or deleted, and
`apps/core/forms/_common.py` was **not touched** (C7's escalated half).

| id | status | commit(s) |
|---|---|---|
| **I1** | fixed | `2aaf93e6` |
| **I2** | fixed | `2fd827c9`, `d4d5ebda` |
| **I3** | fixed | `81b1e20c` |
| **I4** | already fixed — C5's fix took the `-id` branch | (`6673ace8`) |
| **I5** | fixed | `92488f0d`, `37da054e`, `6f2de317` (migration 0014), `3a88475d` |
| **I6** | fixed | `43e4ba33` |
| **I7** | fixed | `e12ca933` |
| **I8** | fixed | `315cd464` |
| **I9** | fixed (contract §5.1) | `158679fb` |
| **I10** | no code change — pattern note, re-run and recorded | — |
| **I11** | fixed | `35030847`, `249b3391`, `df738f48`, `7a5b0c03` |
| **M1** | fixed | `f03587f4` |
| **M2** | fixed | `e00cf25b` |
| **M3** | fixed (contract §4) | `09ea350d` |
| **M4** | already fixed — folded into C6 | `668ae0fb`, `09c8bc5d`, `3a31f2b5` |
| **M5** | fixed | `430dc9a5` |
| **M6** | fixed | `cd2292ba`, `f03587f4` |
| **M7** | fixed | `c612531a` |
| **M8** | no action — accepted and documented | — |
| **M9** | fixed (contract §7) | `8baec6d9` |
| **M10** | fixed | `13f93ba7` |
| **M11** | fixed | `e00cf25b` (+ `f03587f4`, the coherence half) |
| **M12** | fixed (contract §4) | `09ea350d` |

## New finding surfaced by the burn-down

**`C8` (Critical) — the hub's "Recent backup jobs" preview had C5's defect.** Recorded in the Critical
table above and in `81b1e20c`. It is the same mechanism (NULL `started_at` sorts last under `DESC` on
MariaDB, then a `[:5]` slice) on the *landing* page instead of the monitoring board, and it was equally
silent. It surfaced only because I3 required reading the hub's ordering — the seeder's new queued row
(M11) makes it observable in the demo data from now on.

**A Minor, fixed in the same commit (`f03587f4`).** M11's queued row exposed a second, smaller
disagreement: the hub's "Never verified" summed `not j.is_verified` over **every** row, in-flight ones
included, while `backup_board` deliberately excludes them ("naming it would be an accusation rather than a
finding"). With no queued row in the seed the two pages had never disagreed. The hub's denominator is now
the **settled** set, which also preserves C4 (no settled backups → `None`, never a green `0`). This is the
same shape as C4/C6 — two pages counting the same thing differently — and it is worth naming because the
seeder change is what made it visible. **Found by:** code-fixer.

## Verification

Every fix was re-verified with a purpose-built probe under `temp/` (gitignored), each building its own
workspaces inside a savepoint that is rolled back, so the shared dev DB is untouched. The probes test
**both directions** where a rule could be over-applied — a rule that refuses *everything* passes a naive
refusal test:

| probe | covers | what it establishes beyond "it passes" |
|---|---|---|
| `_0_16_i1_probe.py` | I1 | refuses the lost/destroyed/locationless archive through the real create form **and** still accepts a restorable one; a restore with no archive is unaffected. |
| `_0_16_i2_probe.py` | I2 | drives the **real Django admin** path the finding proved was open (8 cross-tenant FKs) and asserts the same-tenant FK is still accepted. |
| `_0_16_i3_probe.py` | I3 (+C8) | hub **20 → 13** queries (board is 11); **one** statement touches `core_backupjob` (was four `COUNT(*)` + a slice) and **one** touches `core_environmentinstance` (was two); the five-row preview keeps a queued job first. |
| `_0_16_i5_probe.py` | I5 | the four indexes `EXPLAIN` as `Using index` with no filesort; the environment list no longer transfers the whole row twice. |
| `_0_16_i6_probe.py` | I6 | refuses `failed` and `cancelled`, and still verifies `success`/`warning` (the control). |
| `_0_16_i7_probe.py` | I7 | releases a hold in its own issue-minute, and still refuses a genuinely earlier release. |
| `_0_16_i8_probe.py` | I8 | reproduces the finding's exact `A→B→A` POST and refuses it, and still accepts a legitimate new child. |
| `_0_16_i11_probe.py` | I11 | **47 checks**: every field of all four forms renders exactly **once** (a grouping change is the kind that silently drops one), the four labels are humanised, the field names are unchanged, each form still POSTs to a 302. |
| `_0_16_m_probe.py` | M1, M2, M5, M6, M7, M10, M11 | **32 checks**: M2/M11 re-run the real `seed_core` twice inside a rolled-back savepoint (row present, in flight, idempotent, key backfilled, lost archive left NULL); M11-coherence asserts the hub reads "not applicable" / green `0` / amber `1` in the three matching workspaces **and** that the board's list agrees; M6's three states plus the warning suppression; M7's banner under a filter matching nothing; M1's redaction. |

Regression: the **C4, C5, C6 and I3** probes were all re-run after the last change and are green, and
`apps/core/tests/` is **204 passed / 0 failed** (`--nomigrations`). The four pre-existing failures listed
above were not chased (they fail identically at the pre-session baseline `44c72ec3`).

