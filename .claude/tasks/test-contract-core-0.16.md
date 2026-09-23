# Test contract — Core 0.16 Backup, Recovery & Data Lifecycle (`core`)

> Pinned **before** any test file was written, per the close-out workflow. Every fixture name, every
> hand-computed figure and every assertion target below is decided here first, so the tests cannot
> drift into asserting whatever the code happens to do.
>
> Isolation basis: `pytest.ini` sets `--reuse-db` (schema reuse only). The `db` fixture wraps each test
> in a transaction that is rolled back, so **within one test the database contains only what that
> test's fixtures created** — which is why the figures below can be pinned EXACTLY rather than `>=`.
>
> **0.16 is a register, not an engine.** Nothing here takes a backup, restores one, replicates data or
> provisions an environment; every row records an act performed out of band. A test that asserts
> otherwise is asserting a claim the sub-module explicitly refuses to make.
>
> **Six Criticals were fixed in Phase 5 and one (C7) was escalated.** Several of the figures below
> exist *because* of those fixes, and the fix id is named next to each so a future regression can be
> traced to the finding that produced the rule. Do not "simplify" a fixture away without reading the
> finding.

---

## 1. Fixtures — helpers (`_bkp_*`, module-private to `conftest.py`)

All helpers follow the `_collab_*` / `_docmgt_*` idiom: build the instance, `full_clean()`, `save()`,
return it. Nothing here passes a field the model computes.

| Helper | Signature | Defaults |
|---|---|---|
| `_bkp_job` | `(tenant, **overrides)` | `name="Nightly full backup"`, `status="success"`, `backup_type="full"`, `started_at=now-8h`, `finished_at=started+24m`, `integrity_verified_at=None` |
| `_bkp_archive` | `(tenant, **overrides)` | `name="2024 activity archive"`, `location="glacier://acme/2024.parquet"`, `status="active"` |
| `_bkp_hold` | `(tenant, **overrides)` | `name="Hold — Acme v. Initech"`, `status="active"`, `released_at=None`, `issued_at=now-30d`, `custodian="Finance team"` |
| `_bkp_env` | `(tenant, **overrides)` | `name="Sandbox — UAT"`, `kind="sandbox"`, `copy_scope="none"`, `status="active"` |
| `_bkp_drill` | `(tenant, **overrides)` | `name="Q3 isolated failover"`, `kind="test_failover"`, `outcome="passed"`, `performed_at=now-7d` |
| `_bkp_restore` | `(tenant, **overrides)` | `name="Restore drill"`, `status="succeeded"`, `scope="full_instance"` |
| `_bkp_key` | `(tenant, **overrides)` | `tenants.EncryptionKey` — `name="Primary"`, `prefix="acmekey"`, `key_hash="sha256:…"`, `status="active"`. All four are **required** (`null=False`, `blank=False`, no default), so a helper that omits one raises rather than silently creating a blank row. **Never stores plaintext** — the model holds a prefix and a hash only |

**Why `integrity_verified_at=None` is the default.** The unverified state is the one the board exists
to surface — *"an unverified backup is an untested claim, not a safety net."* A helper that defaulted
to verified would make every test assert the reassuring case.

## 2. Fixtures — public (`bkp_*`)

Tenant A actors are the root-conftest `tenant_a` / `admin_user` / `member_user` / `client_a` /
`member_client`; tenant B uses `tenant_b` / `admin_b` / `client_b`. **0.16 invents no spine entity** —
it FKs `core.Party` and `tenants.EncryptionKey` where the seeder does, and nothing otherwise.

### Tenant A — subjects

| Fixture | Depends on | Shape | Exists because |
|---|---|---|---|
| `bkp_verified_job_a` | `tenant_a` | `status="success"`, `integrity_verified_at` set | the *only* state that earns a green ✓ |
| `bkp_unverified_job_a` | `tenant_a` | `status="success"`, `integrity_verified_at=None` | the untested claim the board names |
| `bkp_partial_job_a` | `tenant_a` | `status="warning"`, `failure_reason="partial_scope_skipped"` | **a partial backup is more dangerous than a failed one, because people trust it** |
| `bkp_failed_job_a` | `tenant_a` | `status="failed"`, `failure_reason="integrity_check_failed"` | **I6**: verify must refuse it |
| `bkp_queued_job_a` | `tenant_a` | `status="queued"`, `started_at=None`, `finished_at=None` | **C5** — the in-flight row the old ordering hid |
| `bkp_cancelled_job_a` | `tenant_a` | `status="cancelled"`, `started_at=None` | **C5's boundary**: settled, so it is *not* in flight and its missing check IS a finding |
| `bkp_archive_ok_a` | `tenant_a` | `location` set, `status="active"` | the restorable control |
| `bkp_archive_lost_a` | `tenant_a` | `location=""`, `status="lost"` | **I1** — the unrestorable bait the seeder also plants |
| `bkp_hold_active_a` | `tenant_a` | `status="active"`, `released_at=None` | **C2** — a hold must suspend the 0.8 board |
| `bkp_hold_released_a` | `tenant_a` | `status="released"`, `released_at=issued+1h` | **C3** — the legitimately-closed state |
| `bkp_env_a` | `tenant_a` | `kind="sandbox"`, `expires_at=now-1d` | the past-reaping-date row |
| `bkp_env_cycle_a` | `tenant_a`, `bkp_env_a` | two environments pointing at each other | **I8** — the reachable cycle |
| `bkp_posture_both_a` | `tenant_a` | `rpo_target_minutes=60`, `rto_target_minutes=240` | the earned green "Set" |
| `bkp_posture_partial_a` | `tenant_a` | `rpo_target_minutes=60`, `rto_target_minutes=None` | **M6** — half a target is not a green "Set" |
| `bkp_drill_a` | `tenant_a`, `bkp_posture_both_a` | measured RPO/RTO vs the targets | the drill the posture exists to judge |
| `bkp_key_a` | `tenant_a` | an `EncryptionKey` | **C7** — the field whose leak was measured |

### Tenant B — the 404 / isolation subjects

| Fixture | Depends on | Shape |
|---|---|---|
| `bkp_job_b` | `tenant_b` | `status="success"`, verified |
| `bkp_archive_b` | `tenant_b` | restorable |
| `bkp_hold_b` | `tenant_b` | `status="active"` |
| `bkp_env_b` | `tenant_b` | `kind="production"` |
| `bkp_drill_b` | `tenant_b` | `outcome="passed"` |
| `bkp_key_b` | `tenant_b` | an `EncryptionKey` — **the prefix that must never appear in A's dropdown** |

### Payload helpers (not DB fixtures)

| Helper | Returns |
|---|---|
| `bkp_job_payload` | a valid `BackupJobForm` POST dict for `tenant_a` |
| `bkp_restore_payload` | a valid `RestoreRecordForm` POST dict |
| `bkp_hold_payload` | a valid `LegalHoldForm` POST dict |

## 3. Seeded figures — `_seed_backup(tenant)` on a **fresh** tenant

Measured by calling `Command()._seed_backup(fresh_tenant)` inside a rolled-back savepoint. **These are
the figures a smoke asserts**, and they are pinned because a seeder that drifts from its contract
silently weakens every demo and every sweep.

| Entity | Count | Detail |
|---|---|---|
| `BackupJob` | **4** | `success`+verified (`Nightly full backup`), `warning`/partial+unverified (`Hourly transaction log`), `failed`+unverified (`Weekly offsite copy`), **`queued` with `started_at=None`** (`Queued nightly full backup`) |
| — settled | 3 | |
| — in flight | 1 | **M11** — added because its absence is exactly why C5 survived a green sweep |
| — unverified (settled) | 2 | the warning + the failed row |
| — partial | 1 | |
| — failed | 1 | |
| `DataArchive` | **2** | one restorable, one unrestorable (`Legacy CRM export (media lost)`, `location=""`, `status="lost"`) |
| `LegalHold` | **1** | `status="active"` |
| `EnvironmentInstance` | **2** | `production` + a sandbox refreshed from it |
| `RecoveryDrill` | **2** | one with measured actuals, one not yet run |
| `RecoveryPosture` | **1** | the singleton |
| `RestoreRecord` | **1** | |

**Idempotency is pinned**: running `_seed_backup` a second time on the same tenant adds **nothing**
(4 / 2 / 1 unchanged). Every entity has its **own** guard — a tenant-wide guard is the documented
defect that stranded every entity added later.

**`encryption_key` is `NULL` on a fresh seed, and that is correct.** `seed_core` runs before
`seed_tenants`, so no `EncryptionKey` exists yet; the backfill at the end of the method cannot find one
either (**M2**). Pinned so nobody "fixes" it by inventing a key inside `core`.

## 4. Assertion targets — model lane (`test_backup_models.py`)

### `BackupJob` derived state (**C5**)
- **`BackupJob.is_verified` is a PROPERTY** (`integrity_verified_at is not None`), while
  **`RestoreRecord.is_verified` is a stored FIELD** — a *claim* somebody made about a restore, not a
  derivation. Do not assert them the same way; a test that treats the field as derived will pass while
  asserting nothing.
- `bkp_queued_job_a.is_in_flight is True`; `bkp_verified_job_a.is_in_flight is False`.
- **`bkp_cancelled_job_a.is_in_flight is False`** — the boundary that matters. A cancelled row has no
  `started_at` but IS settled, so its absent integrity check is a finding, not "not yet a question".
- `is_in_flight` is **not** the negation of `is_verified`: assert both `bkp_queued_job_a` (in flight,
  unverified) and `bkp_failed_job_a` (settled, unverified) differ on `is_in_flight` while agreeing on
  `is_verified`.
- `IN_FLIGHT_STATUSES == ("queued", "running")`.

### `LegalHold` rules (**C3**, **I7**)
- **Rule 1b(a)**: `status="active"` + `released_at` set → `ValidationError` on **`status`**.
- **Rule 1b(b)**: `status="released"` + `released_at=None` → `ValidationError` on **`released_at`**.
- **The four legitimate states all pass** `full_clean()` — a rule that refuses everything would pass
  the two tests above. Include `expired` and `superseded` with no release date.
- **Rule 1 (I7)**: a hold issued at `20:27:03` and released at `20:27:00` (the minute the widget can
  express) is **accepted**; released at `20:26:00` is **refused**. This is the same-minute case the
  old strict comparison rejected.
- **Rule 2 (anti-spoliation)**: releasing while a sibling active hold covers the same scope is refused,
  and the message **names the blocking hold**. A sibling on a *different* scope does not block.
- `is_active` is `status == "active" and released_at is None`.
- `scope_label` falls back `model_label` → `policy.name` → `"workspace-wide"`.

### `RestoreRecord` (**I1**)
- `status="succeeded"` with `archive=bkp_archive_lost_a` → `ValidationError` on **`archive`**.
- The same record with `archive=bkp_archive_ok_a` → clean.
- The guard does **not** fire when `archive is None` (a restore need not name an archive).

### `EnvironmentInstance` (**I8**)
- A direct self-edge is refused (pre-existing).
- **`A.source_environment = B` while `B.source_environment = A` is refused** — the cycle.
- A legitimate 3-long chain `A → B → C` is accepted (a cycle check that refuses depth would pass the
  cycle test and break the feature).

### `TenantConsistentMixin` — the model edge (**I2**)
- Each of the cross-tenant FKs refuses a linked object whose `tenant_id` differs:
  `BackupJob.encryption_key`, `DataArchive.policy`, `LegalHold.retention_policy`,
  `EnvironmentInstance.source_environment`, `EnvironmentInstance.refresh_source`,
  `RestoreRecord.backup` / `.archive` / `.target_environment`.
- The same FK pointing at a **same-tenant** object is accepted.
- This is the rule the admin inherits, which is the whole point of putting it at the model edge.

### `DataArchive`
- `is_restorable` is False when `location == ""` **or** `status in {"lost", "destroyed"}`; True
  otherwise. Assert the both-disjuncts row (a row that is *both* locationless and lost) is a single
  row, i.e. the property is a boolean, not a count.

## 5. Assertion targets — form lane (`test_backup_forms.py`)

### Tenant scoping
- Every tenant-scoped FK's queryset contains only `tenant_a` rows when built with `tenant=tenant_a`.
- **C7 boundary**: `BackupJobForm(tenant=None).fields["encryption_key"].queryset` is **unnarrowed** —
  the *documented, deliberate* base-class behaviour. Asserted explicitly so that if C7 is ever
  revisited the test fails **loudly** instead of silently changing meaning. Do **not** assert the
  empty-queryset behaviour; that change was reverted (`68ebb8eb`).
- `ProjectIntegrationConnectorForm(tenant=None).fields["owner"].queryset.count() == 0` — the **live
  leak fix** (`2cf76bd4`), which is self-sufficient and therefore *is* safe to pin. (Belongs to
  `apps/projects`; if the 0.16 suite would rather not reach across apps, pin it in the findings file
  instead and note it here.)

### Field behaviour
- `LegalHoldForm` rejects `status="active"` + a release date with the model's message on `status`
  (**C3**), and accepts the corrected payload.
- `RestoreRecordForm` rejects a succeeded restore from `bkp_archive_lost_a` (**I1**).
- `BackupJobForm` accepts a `queued` payload with blank `started_at`/`finished_at` (**C5** — the state
  must be *creatable*, or the whole in-flight path is unreachable).
- `RecoveryPostureForm` accepts RPO-only and both-set; the form must not make either required (**M6**).

### The 21-field form (**I11**)
- The rendered `BackupJobForm` contains **each field exactly once** — a grouping pass that duplicates a
  field is the classic regression here. Assert the count of `<input`/`<select`/`<textarea` ids, not
  just that the page is 200.

## 6. Assertion targets — view lane (`test_backup_views.py`)

### Route resolution
- Every 0.16 route name reverses. **34 callables / 29 names** (**M12**), some reached via `crud()`.

### GET renders — all 15 pages, 200
`backup_overview`, `backup_board`, the six list pages, their `_create`/`_detail`/`_edit` pages, and
`recovery_posture_edit`.

### The hub's figures (**C4**, **C6**, **C8**, **I3**)
- On a workspace with **zero** backups: `unverified_count is None` and `unrestorable_count is None`,
  the page renders **"not applicable"**, and **no `badge-green">0<` appears anywhere**.
- **The control**: on a workspace with rows, `unverified_count == 0` **and the green `0` IS rendered** —
  a fix that suppressed the badge everywhere would be a new bug.
- **C6**: `unverifiable_count is None` on an empty workspace; `0` with rows; the two sibling rows on
  the same page must **agree**.
- **C8**: the five-row `recent_jobs` preview contains an in-flight job, **first**. Reproduce the defect
  first with the pre-fix query (`BackupJob.objects.filter(tenant=t)[:5]`, i.e. `Meta.ordering`) and
  assert the queued job is **absent** from it — a fix without a reproduced defect proves nothing.
- **I3**: query count is in the board's order of magnitude (measured 13 vs 11; assert `< 20`), **and**
  every figure still equals the database computed independently in Python.

### The board (**C2**, **C5**, **C6**)
- `job_rows` includes a queued job, **first**, with the in-flight note — **not** "No integrity check
  recorded" (that is the false accusation C5 fixed).
- `unverified_jobs` **excludes** in-flight rows and **includes** `bkp_cancelled_job_a`.
- `never_restored is None` when there is no successful backup.
- With 10 finished + 1 queued job, the queued one is still present (the measured 9-vs-10 boundary).
- **C2**: with `bkp_hold_active_a` pinning a policy that covers a real row, `retention_board` names the
  hold and reports **0** rows past their window — the spoliation the sub-module exists to prevent.

### Empty states
- Every list page renders its `empty-state` block on a workspace with no rows of that entity.
- Junk filter params (`?status=zzz&page=99`) return **200**, never 500.

### POST verbs
- `backup_job_verify` on `bkp_verified_job_a` → 302 and sets `integrity_verified_at` (**and is
  first-write-wins**, **M1**).
- **I6**: `backup_job_verify` on `bkp_failed_job_a` and `bkp_cancelled_job_a` → **refused**, no write,
  and the page never shows a green ✓ over a failed job.
- **I7**: the hold edit POST accepts a same-minute release and refuses a genuinely back-dated one.
- **C1**: every `_edit` view POSTs a valid payload to **302 + the row persisted** — the blind spot that
  let C1 survive a GET-only sweep.

## 7. Assertion targets — security lane (`test_backup_security.py`)

### Anonymous
- All 34 routes redirect an anonymous client to the login page (302, `settings.LOGIN_URL`).

### Role gate
- `member_client` (not a tenant admin) is refused on every `@tenant_admin_required` route.
- **405 for a wrong method regardless of role** — a GET on a `@require_POST` verb is **405**, not 403,
  for both the admin and the member. Decorator order: `require_POST` sits **above** the role gate.

### Cross-tenant (IDOR)
- Every `_detail` / `_edit` / `_delete` route with tenant B's pk returns **404** for `client_a`, and
  the row is unchanged afterwards.
- No 0.16 list page contains tenant B's row names.

### Mass assignment
- POSTing `tenant=<tenant_b.pk>` on create is ignored — the row lands on `request.tenant`.
- POSTing a foreign FK pk is refused with a field error.

### The tenant-less actor
- A superuser with `tenant=None` is redirected off every 0.16 page with the "apply to a tenant
  workspace" message, and **no page 500s**.
- **C7**: `ProjectIntegrationConnectorForm(tenant=None)` exposes **no other tenant's user** — the live
  leak, asserted from the security lane because that is what it was.

### XSS
- A job name containing `<script>` renders **escaped** in the list and on the board.
- A hold `name` with a single quote does not break the delete `onsubmit` (`|escapejs`).

---

## 8. Not to be asserted

- **That C7's base-class behaviour is "fixed".** It is escalated and deliberately unchanged; the
  contract pins the *current* behaviour so a future change is visible, not so it looks like a defect.
- **That any figure is `>=`.** Every figure above is exact under the rollback-per-test model.
- **That the seeder creates an `EncryptionKey`.** It cannot; that is `tenants`' job (**M2**).
- **That `AuditLog.action` carries a verb.** It is `varchar(10)`; the verb goes in `changes`.
