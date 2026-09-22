# Contract — Module 0 0.16 Backup, Recovery & Data Lifecycle (`core`)

**Source of truth:** `.claude/tasks/research-core-0.16.md` · `.claude/tasks/plan-1-0.16-ownership-reconcile.md`
**BASE:** `6a834d9e` · **Migration:** `core/0013_backup_recovery_data_lifecycle.py` (claimed `00122627`)
**App:** `core` — **FLAT** entity files at the package root. `urls.py` is a **flat file**.
**Templates:** `templates/core/<entity>/<page>.html` · **Test subslug:** `backup`

> A name left unpinned in this file is a silently blank page or a `NoReverseMatch` (L7). Everything the
> views pass and everything the templates read is pinned below. **Do not invent a context key at template
> time — if a template needs something not listed in §5, add it to this contract first.**

---

## 1. Ownership — the L36 no-re-declaration list

0.16 must **never** declare any of these; it FKs them or links to them. Enforced here so the reviewers
have a written boundary to test against.

| symbol | where it lives | 0.16's relationship |
|---|---|---|
| `core.RetentionPolicy` | `apps/core/models/Retention.py:22` | **FK target** (`DataArchive.policy`, `LegalHold.retention_policy`). Never re-declared. |
| `core.DisposalRecord` | `apps/core/models/Retention.py:62` | **FK target** (`DataArchive.disposal`). Never re-declared. |
| `core:retention_board` | `apps/core/views/Privacy.py:385` | **linked**, never duplicated. 0.16 boards copy its *zero rule*, not its code. |
| `tenants.EncryptionKey` | `apps/tenants/models/EncryptionKey.py:5` | **FK target** only. It stores `prefix` + `key_hash` and **never plaintext** — so a FK is the only honest reference, and **no 0.16 model may carry a key/secret column**. |
| `core.Party` | `apps/core/models/Party.py:5` | **FK target** (`LegalHold.subject_party`). |
| `core.SyncSchedule` | `apps/core/models/Integration.py:219` | **vocabulary reuse only** — `FREQUENCY_CHOICES` is copied as a tuple reference, not a second schedule table. |
| `core.AuditLog` | `apps/core/models/AuditLog.py:5` | **written into** via `write_audit_log`. Verb goes in `changes`, never `action` (`varchar(10)`; `.create()` never validates choices). |
| `tenants.HealthMetric`, `tenants.UsageRecord` | `apps/tenants/models/` | **0.17 / 0.19**. Not read, not written. |
| `core.RateLimitPolicy` | `apps/core/models/Integration.py:114` | **0.18**. Untouched. |
| `core.PiiClassification` | `apps/core/models/Privacy.py:17` | **0.8**. `EnvironmentInstance.masking_required` points at the *obligation*, it does not run 0.8's discovery. |

All FK strings below are **verified to exist and to be re-exported by their package `__init__.py`**:
`core.Tenant`, `core.Party`, `core.RetentionPolicy`, `core.DisposalRecord`, `tenants.EncryptionKey`,
`settings.AUTH_USER_MODEL`.

---

## 2. Models — 6, in `apps/core/models/Backup.py` and `apps/core/models/Compliance.py`

### 2.1 `BackupJob` → `apps/core/models/Backup.py`
Register of a backup a human reports as taken. Bullet 1.

| field | exact type / choices |
|---|---|
| `tenant` | `ForeignKey("core.Tenant", on_delete=CASCADE, related_name="backup_jobs", db_index=True)` |
| `name` | `CharField(max_length=150)` |
| `scope_label` | `CharField(max_length=255, blank=True)` — free text ("nav_erp schema"); there is no backup-target object to FK |
| `BACKUP_TYPE_CHOICES` | `[("full","Full"),("incremental","Incremental"),("differential","Differential"),("log","Transaction log"),("snapshot","Snapshot")]` |
| `backup_type` | `CharField(max_length=16, choices=BACKUP_TYPE_CHOICES, default="full")` |
| `frequency` | `CharField(max_length=10, choices=_SCHEDULE_FREQUENCY_CHOICES, default="manual")` — **reuses 0.13's vocabulary**: `manual/hourly/daily/weekly` |
| `retention_days` | `PositiveIntegerField(null=True, blank=True)` — the **artefact's** lifetime; distinct from `RetentionPolicy` (a *data category's* lifetime) |
| `target_location` | `CharField(max_length=255, blank=True)` — free text URI/path; no object storage exists to name |
| `STORAGE_TIER_CHOICES` | `[("standard","Standard"),("infrequent","Infrequent access"),("archive","Archive"),("deep_archive","Deep archive"),("tape","Tape / offline")]` |
| `storage_tier` | `CharField(max_length=16, choices=STORAGE_TIER_CHOICES, default="standard")` |
| `encryption_key` | `ForeignKey("tenants.EncryptionKey", on_delete=SET_NULL, null=True, blank=True, related_name="+")` — **FK only** |
| `ENCRYPTION_SCHEME_CHOICES` | `[("none","None"),("aes256","AES-256"),("rsa","RSA"),("managed","Provider-managed"),("other","Other")]` |
| `encryption_scheme` | `CharField(max_length=16, choices=ENCRYPTION_SCHEME_CHOICES, default="none")` |
| `size_bytes` | `BigIntegerField(null=True, blank=True)` — **NULL ≠ 0** |
| `checksum` | `CharField(max_length=128, blank=True)` |
| `INTEGRITY_METHOD_CHOICES` | `[("none","Not checked"),("checksum","Checksum"),("hash","Cryptographic hash"),("restore_test","Restore test"),("vendor_reported","Vendor reported")]` |
| `integrity_method` | `CharField(max_length=16, choices=INTEGRITY_METHOD_CHOICES, default="none")` |
| `integrity_verified_at` | `DateTimeField(null=True, blank=True)` — **NULL renders as "Not verified"**, never as an OK tick |
| `STATUS_CHOICES` | `[("queued","Queued"),("running","Running"),("success","Success"),("warning","Warning — partial"),("failed","Failed"),("cancelled","Cancelled")]` |
| `status` | `CharField(max_length=16, choices=STATUS_CHOICES, default="queued")` |
| `FAILURE_REASON_CHOICES` | `[("n_a","Not applicable"),("source_unreachable","Source unreachable"),("auth_failed","Authentication failed"),("insufficient_space","Insufficient space"),("timeout","Timed out"),("integrity_check_failed","Integrity check failed"),("cancelled_by_operator","Cancelled by operator"),("quota","Licence or quota"),("partial_scope_skipped","Partial — some scope skipped"),("unknown","Unknown")]` |
| `failure_reason` | `CharField(max_length=24, choices=FAILURE_REASON_CHOICES, default="n_a")` |
| `attempt_count` | `PositiveSmallIntegerField(default=1)` |
| `is_immutable` | `BooleanField(default=False)` — a **claim**; NavERP cannot enforce WORM |
| `retain_until` | `DateTimeField(null=True, blank=True)` |
| `started_at` / `finished_at` | `DateTimeField(null=True, blank=True)` each — **duration is DERIVED** |
| `performed_by` | `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name="+")` |
| `evidence` | `CharField(max_length=255, blank=True)` — ticket / job id / runbook (the `DisposalRecord.evidence` pattern) |
| `notes` | `TextField(blank=True)` |
| `created_at` | `DateTimeField(auto_now_add=True)` |

**`Meta`:** `ordering = ["-started_at", "-id"]`;
`indexes = [Index(fields=["tenant","-started_at"], name="bkpjob_tenant_at_idx"), Index(fields=["tenant","status"], name="bkpjob_tenant_status_idx")]`

**Derived properties (never stored):**
`duration` (finished − started, `None` if either missing) · `is_partial` (`status == "warning"`) ·
`is_verified` (`integrity_verified_at is not None`) · `duration_display` / `size_display` helpers
rendering `None` as `"—"` and `0` as a real zero.

### 2.2 `RestoreRecord` → `apps/core/models/Backup.py`
A restore as an **operation with a source, a target and an outcome**. Bullet 2.

| field | exact type / choices |
|---|---|
| `tenant` | `ForeignKey("core.Tenant", CASCADE, related_name="restore_records", db_index=True)` — the **target** tenant; this is what makes a restore "per-tenant" |
| `backup` | `ForeignKey("core.BackupJob", SET_NULL, null=True, blank=True, related_name="restores")` |
| `archive` | `ForeignKey("core.DataArchive", SET_NULL, null=True, blank=True, related_name="restores")` |
| `SCOPE_CHOICES` | `[("full_instance","Full instance"),("per_tenant","Per tenant"),("table","Table"),("record","Record"),("sandbox_refresh","Sandbox refresh"),("archive_retrieval","Archive retrieval")]` |
| `scope` | `CharField(max_length=20, choices=SCOPE_CHOICES, default="full_instance")` |
| `target_time` | `DateTimeField(null=True, blank=True)` — the PITR instant |
| `target_environment` | `ForeignKey("core.EnvironmentInstance", SET_NULL, null=True, blank=True, related_name="restores")` |
| `STATUS_CHOICES` | `[("planned","Planned"),("running","Running"),("succeeded","Succeeded"),("partial","Partial"),("failed","Failed"),("rolled_back","Rolled back")]` |
| `status` | `CharField(max_length=16, choices=STATUS_CHOICES, default="planned")` |
| `requested_by` | `ForeignKey(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True, related_name="+")` |
| `reason` | `CharField(max_length=255, blank=True)` |
| `started_at` / `finished_at` | `DateTimeField(null=True, blank=True)` |
| `outcome` | `TextField(blank=True)` |
| `is_verified` | `BooleanField(default=False)` — a restore that *ran* ≠ a restore that *verified* |
| `evidence` | `CharField(max_length=255, blank=True)` |
| `created_at` | `DateTimeField(auto_now_add=True)` |

**`Meta`:** `ordering = ["-created_at", "-id"]`;
`indexes = [Index(fields=["tenant","-created_at"], name="recrec_tenant_at_idx")]`

**`clean()` — the validation that matters:**
- `target_time` may not be in the future. *(Refused, not clamped — storing a future PITR target is not
  restorable.)*
- If `backup` is set **and** has `started_at`, `target_time` must be `>= backup.started_at` — a target
  before the backup began is outside the recoverable window.
- `scope == "archive_retrieval"` requires `archive` to be set; otherwise a retrieval with no source.
- **At least one of `backup` / `archive`** must be set unless `status == "planned"`.

**Property:** `source_label` — `backup.name` / `archive.name` / `"not recorded"`.

### 2.3 `DataArchive` → `apps/core/models/Backup.py`
The **catalogue entry that makes a restore possible** — the loop 0.8 left open. Bullet 4.

| field | exact type / choices |
|---|---|
| `tenant` | `ForeignKey("core.Tenant", CASCADE, related_name="data_archives", db_index=True)` |
| `name` | `CharField(max_length=150)` |
| `policy` | `ForeignKey("core.RetentionPolicy", SET_NULL, null=True, blank=True, related_name="archives")` — **points at 0.8** |
| `disposal` | `ForeignKey("core.DisposalRecord", SET_NULL, null=True, blank=True, related_name="archives")` — **points at 0.8** |
| `model_label` | `CharField(max_length=120, blank=True)` — 0.8's vocabulary (`app_label.Model`) |
| `content_description` | `TextField(blank=True)` |
| `location` | `CharField(max_length=255)` — **required, not blank.** The field this model exists for: without a location a restore is impossible |
| `STORAGE_TIER_CHOICES` | `[("hot","Hot"),("cool","Cool"),("archive","Archive"),("glacier","Glacier"),("deep_archive","Deep archive"),("offline","Offline"),("tape","Tape")]` |
| `storage_tier` | `CharField(max_length=16, choices=STORAGE_TIER_CHOICES, default="archive")` |
| `FORMAT_CHOICES` | `[("sql","SQL dump"),("csv","CSV"),("jsonl","JSON Lines"),("parquet","Parquet"),("tarball","Tarball"),("native","Native / proprietary"),("other","Other")]` |
| `format` | `CharField(max_length=16, choices=FORMAT_CHOICES, default="sql")` |
| `record_count` | `PositiveIntegerField(null=True, blank=True)` — **NULL ≠ 0** |
| `size_bytes` | `BigIntegerField(null=True, blank=True)` — **NULL ≠ 0** |
| `encryption_key` | `ForeignKey("tenants.EncryptionKey", SET_NULL, null=True, blank=True, related_name="+")` |
| `checksum` | `CharField(max_length=128, blank=True)` |
| `immutable` | `BooleanField(default=False)` — **claim only** |
| `archived_at` | `DateTimeField(null=True, blank=True)` |
| `restored_at` | `DateTimeField(null=True, blank=True)` |
| `expires_at` | `DateTimeField(null=True, blank=True)` — an archive with no expiry is a leak |
| `STATUS_CHOICES` | `[("active","Active"),("restored","Restored"),("expired","Expired"),("lost","Lost"),("destroyed","Destroyed")]` |
| `status` | `CharField(max_length=12, choices=STATUS_CHOICES, default="active")` |
| `notes` | `TextField(blank=True)` |
| `created_at` | `DateTimeField(auto_now_add=True)` |

**`Meta`:** `ordering = ["-archived_at", "-id"]`;
`indexes = [Index(fields=["tenant","status"], name="darch_tenant_status_idx")]`
`unique_together` — **none.** (Deliberately: two archives may legitimately share a name.)

**Derived:** `is_restorable` (`bool(location)` **and** `status in {"active","restored"}`) ·
`retrieval_is_async` (`storage_tier in {"glacier","deep_archive","offline","tape"}`) ·
`age_days`.
**Property:** `tier_display_long` — `"Cold / asynchronous retrieval"` when async, else the `get_storage_tier_display()`.

### 2.4 `LegalHold` → `apps/core/models/Compliance.py`
The event that **suspends** a schedule. Bullet 4. **Not a field on `RetentionPolicy`** — proven in the
research (Zubulake; S3 Object Lock: a hold has no expiry and outlives the retention period).

| field | exact type / choices |
|---|---|
| `tenant` | `ForeignKey("core.Tenant", CASCADE, related_name="legal_holds", db_index=True)` |
| `name` | `CharField(max_length=150)` |
| `custodian` | `CharField(max_length=200, blank=True)` |
| `subject_party` | `ForeignKey("core.Party", SET_NULL, null=True, blank=True, related_name="+")` |
| `matter_reference` | `CharField(max_length=150, blank=True)` |
| `issuing_authority` | `CharField(max_length=200, blank=True)` |
| `scope` | `TextField(blank=True)` |
| `retention_policy` | `ForeignKey("core.RetentionPolicy", SET_NULL, null=True, blank=True, related_name="legal_holds")` — **which** schedule is suspended |
| `model_label` | `CharField(max_length=120, blank=True)` |
| `issued_at` | `DateTimeField(default=timezone.now)` |
| `issued_by` | `ForeignKey(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True, related_name="+")` |
| `STATUS_CHOICES` | `[("active","Active"),("released","Released"),("expired","Expired"),("superseded","Superseded")]` |
| `status` | `CharField(max_length=12, choices=STATUS_CHOICES, default="active")` |
| `released_at` | `DateTimeField(null=True, blank=True)` — **the release event; the reason a schedule cannot express a hold** |
| `released_by` | `ForeignKey(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True, related_name="+")` |
| `release_reason` | `CharField(max_length=255, blank=True)` |
| `authority_reference` | `CharField(max_length=255, blank=True)` |
| `notes` | `TextField(blank=True)` |
| `created_at` / `updated_at` | `auto_now_add` / `auto_now` |

**`Meta`:** `ordering = ["-issued_at", "-id"]`;
`indexes = [Index(fields=["tenant","status"], name="lghold_tenant_status_idx"), Index(fields=["tenant","model_label"], name="lghold_tenant_model_idx")]`

**`clean()` — two rules, both load-bearing:**
1. `released_at`, if set, must be `>= issued_at` (mirrors `StatutoryRule.clean`).
2. **Anti-spoliation:** if the instance's status is being set to `"released"`, refuse when **another
   active hold** covers the same scope — matched on the overlap of `retention_policy` *or* `model_label`.
   Message: *"Another active hold covers this scope — releasing this one would strand the data on the
   other. Release that hold first."* (Exterro's no-mistaken-release control.)
   Guard excludes `self.instance.pk` when editing.

**Derived:** `is_active` (`status == "active"` and `released_at is None`) · `age_days` ·
`scope_label` (`model_label` or the policy name or `"workspace-wide"`).

### 2.5 `EnvironmentInstance` → `apps/core/models/Backup.py`
Bullets 2 **and** 5 — "make a sandbox" built **once**. Research's dedup.

| field | exact type / choices |
|---|---|
| `tenant` | `ForeignKey("core.Tenant", CASCADE, related_name="environment_instances", db_index=True)` |
| `name` | `CharField(max_length=150)` |
| `KIND_CHOICES` | `[("production","Production"),("development","Development"),("test","Test"),("staging","Staging"),("training","Training"),("sandbox","Sandbox"),("preview","Preview")]` |
| `kind` | `CharField(max_length=16, choices=KIND_CHOICES, default="sandbox")` |
| `tier` | `CharField(max_length=20, blank=True)` — free text; Salesforce's tiers are commercial |
| `source_environment` | `ForeignKey("self", SET_NULL, null=True, blank=True, related_name="derived_environments")` |
| `COPY_SCOPE_CHOICES` | `[("none","Empty — no data"),("metadata_only","Metadata / configuration only"),("summary","Summary — data subset"),("full","Full copy")]` |
| `copy_scope` | `CharField(max_length=16, choices=COPY_SCOPE_CHOICES, default="metadata_only")` — bullet 5's "data-subset seeding" |
| `subset_rule` | `TextField(blank=True)` — the **declared** rule (Salesforce sandbox template). A record, not an execution |
| `copy_includes_pii` | `BooleanField(default=False)` |
| `masking_required` | `BooleanField(default=False)` |
| `STATUS_CHOICES` | `[("requested","Requested"),("provisioning","Provisioning"),("active","Active"),("refreshing","Refreshing"),("ready_to_activate","Ready to activate"),("suspended","Suspended"),("expired","Expired"),("reaped","Reaped")]` |
| `status` | `CharField(max_length=20, choices=STATUS_CHOICES, default="requested")` |
| `refreshed_at` | `DateTimeField(null=True, blank=True)` — bullet 2's "sandbox refresh" |
| `refresh_source` | `ForeignKey("self", SET_NULL, null=True, blank=True, related_name="refreshed_from")` |
| `refresh_interval_days` | `PositiveSmallIntegerField(null=True, blank=True)` |
| `expires_at` | `DateTimeField(null=True, blank=True)` — the **reaping** date |
| `storage_limit_mb` | `PositiveIntegerField(null=True, blank=True)` — declared, not enforced |
| `is_active` | `BooleanField(default=True)` |
| `notes` | `TextField(blank=True)` |
| `created_at` / `updated_at` | `auto_now_add` / `auto_now` |

**`Meta`:** `ordering = ["name"]`;
`indexes = [Index(fields=["tenant","kind"], name="envinst_tenant_kind_idx")]`

**`clean()` — three rules:**
1. `source_environment` may not be `self`.
2. `expires_at`, if set, must be `>= created_at` — guard `created_at is None` for unsaved instances.
3. `copy_includes_pii=True` with `copy_scope="none"` is contradictory → refused.

**Derived:** `is_expired` (`expires_at` set and in the past and `status not in {"expired","reaped"}`) ·
`contains_production_data` (`copy_scope == "full"` and `copy_includes_pii`).

### 2.6 `RecoveryPosture` → `apps/core/models/Backup.py` — **tenant singleton**
Bullet 3's **target** half. `OneToOneField` (precedent `LocaleProfile` 0.15, `BusinessCalendar` 0.10)
→ **edit page, not CRUD**.

| field | exact type / choices |
|---|---|
| `tenant` | `OneToOneField("core.Tenant", CASCADE, related_name="recovery_posture", db_index=True)` |
| `rpo_target_minutes` | `PositiveIntegerField(null=True, blank=True)` |
| `rto_target_minutes` | `PositiveIntegerField(null=True, blank=True)` |
| `REPLICATION_MODE_CHOICES` | `[("none","None"),("sync","Synchronous"),("async","Asynchronous")]` |
| `replication_mode` | `CharField(max_length=10, choices=REPLICATION_MODE_CHOICES, default="none")` |
| `primary_region` | `CharField(max_length=80, blank=True)` |
| `dr_region` | `CharField(max_length=80, blank=True)` |
| `backup_retention_days` | `PositiveIntegerField(null=True, blank=True)` |
| `dr_plan_reference` | `CharField(max_length=255, blank=True)` |
| `last_reviewed_at` | `DateField(null=True, blank=True)` |
| `updated_at` | `DateTimeField(auto_now=True)` |

**`Meta`:** `verbose_name = "recovery posture"`.
**Derived:** `has_targets` (`rpo` or `rto` set) · `rpo_display` / `rto_display` rendering `None` as
`"not set"` (never `0`).

### 2.7 `RecoveryDrill` → `apps/core/models/Backup.py`
Bullet 3's **actual** half. Never writes to `RecoveryPosture`.

| field | exact type / choices |
|---|---|
| `tenant` | `ForeignKey("core.Tenant", CASCADE, related_name="recovery_drills", db_index=True)` |
| `name` | `CharField(max_length=150)` |
| `KIND_CHOICES` | `[("planned_failover","Planned failover"),("unplanned_failover","Unplanned failover"),("test_failover","Test failover (isolated)"),("tabletop","Tabletop exercise"),("backup_restore_test","Backup restore test")]` |
| `kind` | `CharField(max_length=24, choices=KIND_CHOICES, default="test_failover")` |
| `scheduled_for` | `DateField(null=True, blank=True)` |
| `performed_at` | `DateTimeField(null=True, blank=True)` |
| `OUTCOME_CHOICES` | `[("not_run","Not yet run"),("passed","Passed"),("partial","Partial"),("failed","Failed")]` |
| `outcome` | `CharField(max_length=10, choices=OUTCOME_CHOICES, default="not_run")` |
| `measured_rpo_minutes` | `PositiveIntegerField(null=True, blank=True)` — **actual**, nullable |
| `measured_rto_minutes` | `PositiveIntegerField(null=True, blank=True)` — **actual**, nullable |
| `participants` | `CharField(max_length=255, blank=True)` |
| `findings` | `TextField(blank=True)` — the deliverable of a drill |
| `follow_up_actions` | `TextField(blank=True)` |
| `evidence` | `CharField(max_length=255, blank=True)` |
| `performed_by` | `ForeignKey(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True, related_name="+")` |
| `notes` | `TextField(blank=True)` |
| `created_at` | `DateTimeField(auto_now_add=True)` |

**`Meta`:** `ordering = ["-performed_at", "-id"]`;
`indexes = [Index(fields=["tenant","outcome"], name="drill_tenant_outcome_idx")]`

**`clean()`:** `outcome != "not_run"` requires `performed_at` (a drill that ran has a date).
**Derived:** `meets_target` / `target_note` — compares `measured_*` against
`tenant.recovery_posture` targets via a safe lookup; `None` when no posture/target exists, so a template
never prints `0` for "cannot tell".

---

## 3. Forms — `apps/core/forms/Backup.py` + `apps/core/forms/Compliance.py`

All subclass `TenantModelForm` (so `tenant` scoping of FK querysets is automatic). **`tenant` is never in
`Meta.fields`** — that is also exactly why a `unique_together` including `tenant` would never validate
(SKILL.md trap). **No 0.16 model declares a `unique_together`**, so the `clean_<field>` guard class is
**not needed here** — recorded explicitly so a reviewer does not file its absence as a finding.

| form | `Meta.model` | `Meta.fields` (exact, in order) |
|---|---|---|
| `BackupJobForm` | `BackupJob` | `name, scope_label, backup_type, frequency, retention_days, target_location, storage_tier, encryption_scheme, encryption_key, size_bytes, checksum, integrity_method, status, failure_reason, attempt_count, is_immutable, retain_until, started_at, finished_at, evidence, notes` |
| `RestoreRecordForm` | `RestoreRecord` | `backup, archive, scope, target_time, target_environment, status, reason, started_at, finished_at, outcome, is_verified, evidence` |
| `DataArchiveForm` | `DataArchive` | `name, policy, disposal, model_label, content_description, location, storage_tier, format, record_count, size_bytes, encryption_key, checksum, immutable, archived_at, restored_at, expires_at, status, notes` |
| `LegalHoldForm` | `LegalHold` | `name, custodian, subject_party, matter_reference, issuing_authority, scope, retention_policy, model_label, status, released_at, release_reason, authority_reference, notes` |
| `EnvironmentInstanceForm` | `EnvironmentInstance` | `name, kind, tier, source_environment, copy_scope, subset_rule, copy_includes_pii, masking_required, status, refreshed_at, refresh_source, refresh_interval_days, expires_at, storage_limit_mb, is_active, notes` |
| `RecoveryPostureForm` | `RecoveryPosture` | `rpo_target_minutes, rto_target_minutes, replication_mode, primary_region, dr_region, backup_retention_days, dr_plan_reference, last_reviewed_at` |
| `RecoveryDrillForm` | `RecoveryDrill` | `name, kind, scheduled_for, performed_at, outcome, measured_rpo_minutes, measured_rto_minutes, participants, findings, follow_up_actions, evidence, notes` |

**Excluded from every form, deliberately:** `tenant` (set in the view), `created_at` / `updated_at`
(auto), `performed_by` / `issued_by` / `released_by` / `requested_by` (the actor is the request user —
**never a form field**, or a user could attribute a legal release to somebody else).
**`BackupJob.integrity_verified_at` is excluded** — it is written only by `backup_job_verify`
(`@require_POST`), so the register cannot be edited into claiming a verification that never happened.

---

## 4. URLs — appended to the flat `apps/core/urls.py`

`crud(slug, name)` generates the 5 standard routes per register. **Literal segments before `<int:pk>`.**

| url name | path | view |
|---|---|---|
| `backup_overview` | `backup/` | `backup_overview` |
| `backup_board` | `backup/board/` | `backup_board` |
| `recovery_posture_edit` | `backup/posture/` | `recovery_posture_edit` |
| *(via `crud("backup/jobs","backup_job")`)* → `backup_job_list` | `backup/jobs/` | `backup_job_list` |
| `backup_job_create` | `backup/jobs/add/` | |
| `backup_job_detail` | `backup/jobs/<int:pk>/` | |
| `backup_job_edit` | `backup/jobs/<int:pk>/edit/` | |
| `backup_job_delete` | `backup/jobs/<int:pk>/delete/` | |
| **`backup_job_verify`** | `backup/jobs/<int:pk>/verify/` | `backup_job_verify` — **`@require_POST`, declared ABOVE the role gate** so a GET is **405** regardless of role (7.7's ruling) |
| *(via `crud("backup/restores","restore_record")`)* → `restore_record_list/_create/_detail/_edit/_delete` | `backup/restores/…` | |
| *(via `crud("backup/archives","data_archive")`)* → `data_archive_list/_create/_detail/_edit/_delete` | `backup/archives/…` | |
| *(via `crud("backup/holds","legal_hold")`)* → `legal_hold_list/_create/_detail/_edit/_delete` | `backup/holds/…` | |
| *(via `crud("backup/environments","environment_instance")`)* → `environment_instance_list/_create/_detail/_edit/_delete` | `backup/environments/…` | |
| *(via `crud("backup/drills","recovery_drill")`)* → `recovery_drill_list/_create/_detail/_edit/_delete` | `backup/drills/…` | |

**Total: 29 url names.** `backup_job_verify` must be registered **after** the literal `add/` route and
**before** nothing that would shadow it — it is a POST-only action, so placement is safe, but it is
listed last in the `crud("backup/jobs", …)` group by explicit hand-append to keep the pattern visible.

---

## 5. THE CONTEXT CONTRACT — every key every view passes (L7/L8)

### 5.1 The five `crud_list` registers
`crud_list(request, qs, template, search_fields=…, filters=…, extra_context=…)` already provides
**`object_list`**, **`page_obj`**, **`q`** and the **`*_choices`** produced by the `filters` tuples.
Everything in the "extra" column below is what this sub-module adds and **must be pinned**.

| view | template | `search_fields` | `filters` | extra context keys (all mandatory) |
|---|---|---|---|---|
| `backup_job_list` | `core/backupjob/list.html` | `("name","scope_label","evidence")` | `(("status","status",False),("backup_type","backup_type",False),("storage_tier","storage_tier",False),("integrity","integrity_method",False))` | `status_choices`, `backup_type_choices`, `storage_tier_choices`, `integrity_method_choices`, `unverified_count` |
| `restore_record_list` | `core/restorerecord/list.html` | `("reason","outcome","evidence")` | `(("status","status",False),("scope","scope",False))` | `status_choices`, `scope_choices` |
| `data_archive_list` | `core/dataarchive/list.html` | `("name","location","content_description")` | `(("status","status",False),("storage_tier","storage_tier",False),("format","format",False))` | `status_choices`, `tier_choices`, `format_choices`, `unrestorable_count` |
| `legal_hold_list` | `core/legalhold/list.html` | `("name","custodian","matter_reference","issuing_authority")` | `(("status","status",False))` | `status_choices`, `active_count` |
| `environment_instance_list` | `core/environmentinstance/list.html` | `("name","tier","subset_rule")` | `(("kind","kind",False),("status","status",False),("copy_scope","copy_scope",False))` | `kind_choices`, `status_choices`, `copy_scope_choices`, `expired_count` |
| `recovery_drill_list` | `core/recoverydrill/list.html` | `("name","findings","participants")` | `(("kind","kind",False),("outcome","outcome",False))` | `kind_choices`, `outcome_choices` |

> **The `filters` tuples are `(get_param, orm_lookup, is_int)`.** `crud_list` already ignores a junk enum
> value (L11), so no per-view guard is needed — and a reviewer must not file that as a missing guard.

### 5.2 The five `crud_create` / `crud_edit` pages
`crud_create` → `{"form": form, "is_edit": False}` · `crud_edit` → `{"form": form, "obj": obj, "is_edit": True}`.
**No extra keys.** The templates use `is_edit` for the title/button and nothing else.
*Exception:* `backup_job` form gets **`unverified_note`** (bool) — see 5.5.

### 5.3 The six `crud_detail` pages
`crud_detail` → `{"obj": obj}` + `select_related`.
| view | `select_related` | extra |
|---|---|---|
| `backup_job_detail` | `("encryption_key","performed_by")` | `restore_count` |
| `restore_record_detail` | `("backup","archive","target_environment","requested_by")` | — |
| `data_archive_detail` | `("policy","disposal","encryption_key")` | — |
| `legal_hold_detail` | `("retention_policy","subject_party","issued_by","released_by")` | `conflicting_holds` (qs of other active holds on the same scope) |
| `environment_instance_detail` | `("source_environment","refresh_source")` | — |
| `recovery_drill_detail` | `("performed_by",)` | `posture`, `rpo_note`, `rto_note` |

### 5.4 The hand-rolled pages — **all keys pinned**

**`recovery_posture_edit`** → `core/recoveryposture/form.html`
`crud_*` does **not** apply (singleton). Context:
```
{
  "form": form, "posture": posture_or_None, "is_edit": bool(posture),
  "drill_count": int, "last_drill": RecoveryDrill_or_None,
  "targets_set": bool,                       # rpo or rto present
}
```
Behaviour: GET reads `.filter(tenant=request.tenant).first()` (**may be `None`**) — it must **not**
`get_or_create`, because that inserts a row merely because somebody opened the page. POST writes.
`request.tenant is None` → `messages.info` + redirect to `dashboard:home`.

**`backup_overview`** → `core/backupoverview.html` — COMPUTED hub, no table.
```
{
  "job_count": int, "unverified_count": int, "partial_count": int, "failed_count": int,
  "archive_count": int, "unrestorable_count": int, "active_hold_count": int,
  "environment_count": int, "expired_count": int, "drill_count": int,
  "posture": RecoveryPosture_or_None, "targets_set": bool,
  "recent_jobs": [BackupJob ≤5], "recent_drills": [RecoveryDrill ≤5],
}
```

**`backup_board`** → `core/backupboard.html` — COMPUTED monitoring. **Follows 0.8's zero rule: never a
`0` that means "cannot tell", and every `None` is named as such.**
```
{
  "job_rows":  [{"job": BackupJob, "age_days": int|None, "note": str}],      # newest ≤10
  "verified_total": int, "job_total": int,
  "unverified_jobs": [BackupJob],            # explicitly named, not a count alone
  "never_restored": int|None,                # None (not 0) when there are no successful backups
  "archives_without_location": [DataArchive],# these are UNRESTORABLE — named
  "archive_total": int,
  "async_retrieval_count": int,
  "active_holds": [LegalHold],
  "holds_suspending": [{"hold": LegalHold, "policy": RetentionPolicy|None}],
  "expired_environments": [EnvironmentInstance],
  "unverifiable_count": int,                 # jobs whose verification CANNOT be determined
  "notes": [str],                            # the honest-limit lines the page prints verbatim
}
```

**`backup_job_verify`** — POST-only, no template. Redirects to `backup_job_detail` on success. Records
`integrity_verified_at = timezone.now()` **and** `integrity_method` if it was `"none"` → `"restore_test"`;
writes an audit row. A **GET returns 405**.

**The audit-verb rule (applies to every hand-rolled write in this sub-module).** `AuditLog.action` is
**`varchar(10)`** and `.create()` never validates `choices`, so a longer verb truncates silently on
non-strict MySQL or raises `DataError` (a 500) under `STRICT_TRANS_TABLES`. The house pattern — verified
at `apps/core/views/Localization.py:142` — is that `action` stays a short valid choice and the
descriptive verb goes in `changes["verb"]`:

```python
write_audit_log(request.user, obj, "update",
                changes={"verb": "backup_job_verify", "integrity_verified_at": str(now)})
```

So `backup_job_verify` writes `action="update"`, **not** `action="verify"`.

### 5.5 `unverified_note`
`backup_job` **create/edit** passes `unverified_note=True` when the instance exists and
`integrity_verified_at is None`, so the form page warns that opening this form does not verify anything
and that verification is a separate POST-only action. Pinned because the template branches on it.

---

## 6. Templates — `templates/core/<entity>/<page>.html`

Foundation apps keep templates at `<entity>/<page>.html` (CLAUDE.md Template rule 4 — flat, no
sub-module level, mirroring `templates/core/statutoryrule/list.html`).

| file | rule |
|---|---|
| `backupjob/{list,detail,form}.html` | list: search + 4 filters + pagination + Actions (eye/pencil/trash-2) + POST delete w/ `{% csrf_token %}` + `confirm()`; `unverified_count` surfaced as a warning row |
| `restorerecord/{list,detail,form}.html` | list: search + 2 filters |
| `dataarchive/{list,detail,form}.html` | list: search + 3 filters; **`unrestorable_count`** surfaced |
| `legalhold/{list,detail,form}.html` | list: search + status filter; detail shows `conflicting_holds` |
| `environmentinstance/{list,detail,form}.html` | list: search + 3 filters; `expired_count` surfaced |
| `recoverydrill/{list,detail,form}.html` | list: search + 2 filters; detail shows posture + notes |
| `recoveryposture/form.html` | singleton edit; **no delete**, because there is nothing to delete |
| `backupoverview.html`, `backupboard.html` | computed; no Actions column |
| `templates/core/core_overview.html` | link the new pages (edit only, if it exists) |

**Design-system constraints (all verified against `static/css/theme.css`):**
- Badges: **colour-named only** — `badge-green`, `badge-amber`, `badge-red`, `badge-info`, `badge-muted`,
  `badge-slate`. **`badge-success`/`badge-warning`/`badge-danger` do NOT exist and render unstyled (L33).**
- Notices: **`<p class="text-muted">`** with variants `text-warn`, `text-ok`, `text-danger`, `text-brand`.
  **`.alert` / `.alert-info` / `.alert-warning` / `.alert-danger` do NOT exist in `theme.css`.**
- Icons: `<i data-lucide="eye|pencil|trash-2"></i>`.
- Every badge gets an `{% else %}{{ obj.get_<field>_display }}{% endfor %}`-style fallback.
- **Every page carries the honest-limit notice.** Exact required line on the register lists:
  > *"This is a register of evidence, not a backup engine. NavERP has no scheduler and no storage
  > client — records here describe work performed outside the application."*
- **`NULL` renders as `"—"` or `"Not verified"`. Never as `0`, never as a tick.**
- Never interpolate user text into a single-quoted JS literal in `onsubmit` — use `|escapejs` (L42).

---

## 7. Seeder — extend `apps/core/management/commands/seed_core.py`

`_seed_backup(tenant)` with a **per-entity guard** (never a tenant-wide one — a tenant-wide guard
silently strands every entity added later). Reuse the tenant's existing `EncryptionKey` if present.
`_seed_recovery_posture(tenant)` for the singleton (`get_or_create`).

Rows: 3 `BackupJob` (one `success` + verified, one **`warning`/partial** with
`partial_scope_skipped` — so the UI's partial state is exercised, one `failed`) · 1 `RestoreRecord` ·
1 `DataArchive` · 1 `LegalHold` (active) · 2 `EnvironmentInstance` (one `production`, one `sandbox`
refreshed from it) · 1 `RecoveryPosture` · 2 `RecoveryDrill` (one `passed` with measured RPO/RTO, one
`not_run`). **Every model seeded** — `temp/audit_integrity.py` check 6 fails on an unseeded, unexplained
model.

---

## 8. `LIVE_LINKS["0.16"]`

Five bullet keys, **byte-identical to `NavERP.md`** (verify with the real `parse_catalog()`, not by eye):

| bullet key (exact NavERP.md text) | target |
|---|---|
| `Automated Backups` | `core:backup_job_list` |
| `Point-in-Time Recovery` | `core:restore_record_list` |
| `Disaster Recovery & Failover` | `core:recovery_drill_list` |
| `Data Archival & Purging` | `core:data_archive_list` |
| `Sandbox & Environment Management` | `core:environment_instance_list` |

Extra leaves: `Backup Overview` → `core:backup_overview`, `Backup & Recovery Board` →
`core:backup_board`, `Recovery Posture` → `core:recovery_posture_edit`, `Legal Holds` →
`core:legal_hold_list`.

---

## 9. Verification gate (per CLAUDE.md)

`makemigrations --check` → "No changes detected" · `migrate` · `seed_core` **×2** (2nd idempotent) ·
`manage.py check` · `temp/audit_integrity.py` **6/6** · smoke as `admin_acme` asserting **content** ·
`backup_job_verify` GET → **405** · cross-tenant IDOR → **404** · final `apps/core/tests` run **without**
`--nomigrations`.
