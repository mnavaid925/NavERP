"""core — 0.16 Backup, Recovery & Data Lifecycle.

**The rule this file is built around, inherited from 0.8 (`apps/core/models/Retention.py`):**

> *"'delete' in this codebase does not erase bytes… A 'destruction' feature that reports success while
> the file survives on disk would be actively dishonest."*

The same reasoning applies here, inverted. NavERP has **no scheduler**, **no object storage client**, and
**no ability to dump or restore its own MySQL database** (`config/settings.py` uses
`django.db.backends.mysql`; there is no `mysqldump`, `xtrabackup`, binlog reader or restore runner
anywhere in the repo). Therefore a page that says "backup complete" would be **the same lie in the other
direction** — and a `RestoreRecord` is not evidence that a restore happened, it is evidence that a
**person reported one**, exactly as `DisposalRecord` is for disposal.

So every model here is a **register of evidence written by hand**, and every page built on them says so.
Two consequences run through the whole file:

1. **`NULL` is not `0`.** `size_bytes`, `record_count`, `integrity_verified_at`, `measured_rpo_minutes`
   are all nullable *on purpose*. A `0` that means "not reported" is the most dangerous number an
   operations board can print (0.8's `retention_board` refuses exactly this). The `*_display` properties
   below render `None` as `"—"` / `"Not verified"` and never coerce it.
2. **No model performs the act.** Nothing here dumps, restores, archives, replicates or provisions. The
   act is out of band; these rows are the trail it leaves.

**Ownership (L36 — what this file deliberately does NOT re-declare):** retention schedules and disposal
evidence are `core.RetentionPolicy` / `core.DisposalRecord` (0.8). `DataArchive` and `LegalHold` **point
at** them. `tenants.EncryptionKey` is FK'd, never copied — it stores only a prefix and a SHA-256 hash, so
re-storing a key on a backup row would both break that rule and be a leak.

**Bullet 4 is mostly built by 0.8.** `LIVE_LINKS["0.8"]` already claims "Data Archival & Purging". This
sub-module supplies only the two things a *schedule* structurally cannot express: a **legal hold** (an
event with a release that **suspends** the schedule — see `Compliance.py`) and an **archive catalogue**
(`RetentionPolicy.action="archive"` says *that* something should be archived; nothing recorded *where it
went*, so a restore was impossible).
"""
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.core.models._base import *  # noqa: F401,F403


#: The schedule vocabulary, reused from 0.13's `SyncSchedule.FREQUENCY_CHOICES` rather than grown a second
#: time. Like that model, a frequency here is a **recorded intention** — `SyncSchedule`'s own docstring
#: says "Nothing runs it", and nothing runs this either.
_SCHEDULE_FREQUENCY_CHOICES = [
    ("manual", "Manual only"),
    ("hourly", "Hourly"),
    ("daily", "Daily"),
    ("weekly", "Weekly"),
]


class TenantConsistentMixin(models.Model):
    """Model edge: a tenant-scoped FK on this row must point into the SAME workspace as the row.

    **Why a model rule and not a form rule.** `TenantModelForm` narrows a FK's *choices* by tenant, but
    that is a UI convenience and it is skipped entirely when `tenant is None` — which is C7, escalated
    and deliberately left alone (the shared helper's behaviour is a Module-0 decision). The Django
    admin uses a plain `ModelForm` with **no narrowing at all**, so without a rule here a workspace's
    sandbox can be recorded as a clone of another tenant's production environment, or a hold pinned to
    another tenant's retention policy. The contract and `LegalHold`'s docstring both rest on
    "`_post_clean` calls `full_clean`, so every `clean()` is enforced everywhere — the seeder *and the
    admin* get it too"; this is the rule that makes that sentence true for tenant consistency.

    Deliberately generic: it walks every `ForeignKey`/`OneToOneField` on the model and checks the ones
    whose target is itself tenant-scoped, so a tenant-scoped FK added later inherits the guard without
    anyone remembering to write it.
    """

    class Meta:
        abstract = True

    def clean(self):
        super().clean()
        if self.tenant_id is None:
            # A tenant-less actor (the superuser, by design) has nothing to be consistent with, and
            # every 0.16 view refuses to build a tenant-less row anyway.
            return
        for field in self._meta.get_fields():
            if not isinstance(field, models.ForeignKey) or field.attname == "tenant_id":
                continue
            linked_id = getattr(self, field.attname)
            if linked_id is None:
                continue
            target = field.related_model
            if target is None or not any(f.name == "tenant" for f in target._meta.fields):
                continue
            linked_tenant_id = (target._default_manager.filter(pk=linked_id)
                                .values_list("tenant_id", flat=True).first())
            # `None` means the linked row is itself tenant-less (e.g. the superuser); only a *different*
            # real tenant is a violation.
            if linked_tenant_id is not None and linked_tenant_id != self.tenant_id:
                raise ValidationError(
                    {field.name: "That record belongs to another workspace."})


class BackupJob(TenantConsistentMixin, models.Model):
    """One recorded backup — what was taken, where it went, and whether anyone checked it.

    The `warning` status is the field a naive register omits, and it is the one that matters: a **partial**
    backup is more dangerous than a failed one, because people trust it. Veeam's report vocabulary is
    literally {Success, Warning, Failed} for this reason, and `failure_reason` carries the typed reason
    (`partial_scope_skipped` for the partial case).
    """

    BACKUP_TYPE_CHOICES = [
        ("full", "Full"),
        ("incremental", "Incremental"),
        ("differential", "Differential"),
        ("log", "Transaction log"),
        ("snapshot", "Snapshot"),
    ]
    STATUS_CHOICES = [
        ("queued", "Queued"),
        ("running", "Running"),
        ("success", "Success"),
        ("warning", "Warning — partial"),
        ("failed", "Failed"),
        ("cancelled", "Cancelled"),
    ]
    #: Statuses meaning "this backup has not finished". A row in one of these is **not yet an artefact**:
    #: it has no result, and its absent `integrity_verified_at` means "there is nothing to check yet",
    #: NOT "nobody checked". Kept next to `STATUS_CHOICES` so that whoever edits that vocabulary sees
    #: this subset and has to decide where the new status belongs.
    IN_FLIGHT_STATUSES = ("queued", "running")
    STORAGE_TIER_CHOICES = [
        ("standard", "Standard"),
        ("infrequent", "Infrequent access"),
        ("archive", "Archive"),
        ("deep_archive", "Deep archive"),
        ("tape", "Tape / offline"),
    ]
    ENCRYPTION_SCHEME_CHOICES = [
        ("none", "None"),
        ("aes256", "AES-256"),
        ("rsa", "RSA"),
        ("managed", "Provider-managed"),
        ("other", "Other"),
    ]
    INTEGRITY_METHOD_CHOICES = [
        ("none", "Not checked"),
        ("checksum", "Checksum"),
        ("hash", "Cryptographic hash"),
        ("restore_test", "Restore test"),
        ("vendor_reported", "Vendor reported"),
    ]
    FAILURE_REASON_CHOICES = [
        ("n_a", "Not applicable"),
        ("source_unreachable", "Source unreachable"),
        ("auth_failed", "Authentication failed"),
        ("insufficient_space", "Insufficient space"),
        ("timeout", "Timed out"),
        ("integrity_check_failed", "Integrity check failed"),
        ("cancelled_by_operator", "Cancelled by operator"),
        ("quota", "Licence or quota"),
        ("partial_scope_skipped", "Partial — some scope skipped"),
        ("unknown", "Unknown"),
    ]

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE,
                               related_name="backup_jobs", db_index=True)
    name = models.CharField(max_length=150)
    #: Free text: NavERP has no backup-target object to point at. There is no model of "the database" or
    #: "the file share" in this codebase, so inventing a FK to one would be fiction.
    scope_label = models.CharField(max_length=255, blank=True,
                                   help_text="What is covered, e.g. 'nav_erp schema' or 'ACME tenant'.")
    backup_type = models.CharField(max_length=16, choices=BACKUP_TYPE_CHOICES, default="full")
    frequency = models.CharField(max_length=10, choices=_SCHEDULE_FREQUENCY_CHOICES, default="manual",
                                 help_text="A recorded intention. Nothing in NavERP runs it.")
    #: The backup ARTEFACT's lifetime. Deliberately distinct from `RetentionPolicy.retention_months`,
    #: which is a DATA CATEGORY's lifetime — one is "how long do we keep this file", the other is "how
    #: long do we keep this kind of record". 0.8 owns the second; this owns the first.
    retention_days = models.PositiveIntegerField(null=True, blank=True)
    target_location = models.CharField(max_length=255, blank=True,
                                       help_text="Where it was written. Free text — NavERP has no "
                                                 "storage client.")
    storage_tier = models.CharField(max_length=16, choices=STORAGE_TIER_CHOICES, default="standard")
    #: FK ONLY, never key material. `tenants.EncryptionKey` stores a prefix + SHA-256 hash and never the
    #: plaintext, so copying a "key" column onto this row would both violate that and leak.
    encryption_key = models.ForeignKey("tenants.EncryptionKey", on_delete=models.SET_NULL, null=True,
                                      blank=True, related_name="+")
    encryption_scheme = models.CharField(max_length=16, choices=ENCRYPTION_SCHEME_CHOICES,
                                         default="none")
    #: NULL means "not reported", which is NOT the same as 0 bytes.
    size_bytes = models.BigIntegerField(null=True, blank=True)
    checksum = models.CharField(max_length=128, blank=True)
    integrity_method = models.CharField(max_length=16, choices=INTEGRITY_METHOD_CHOICES, default="none")
    #: NULL means NOT VERIFIED and must render as such — never as a green tick.
    integrity_verified_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="queued")
    failure_reason = models.CharField(max_length=24, choices=FAILURE_REASON_CHOICES, default="n_a")
    #: Hand-entered, because NavERP cannot count retries it did not run.
    attempt_count = models.PositiveSmallIntegerField(default=1)
    #: A CLAIM about the target. WORM can only be enforced by the storage (S3 Object Lock, GCP enforced
    #: retention); a UI that says "locked" when nothing is locked is the fake-delete dishonesty again.
    is_immutable = models.BooleanField(default=False,
                                       help_text="Recorded claim about the target. NavERP cannot "
                                                 "enforce this.")
    retain_until = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    performed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                     blank=True, related_name="+")
    #: A ticket / job id / runbook — the reference that makes this defensible, the same shape
    #: `DisposalRecord.evidence` uses.
    evidence = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-started_at", "-id"]
        indexes = [
            models.Index(fields=["tenant", "-started_at"], name="bkpjob_tenant_at_idx"),
            models.Index(fields=["tenant", "status"], name="bkpjob_tenant_status_idx"),
        ]

    def __str__(self):
        return f"{self.name} · {self.get_backup_type_display()} · {self.get_status_display()}"

    # ---- derived: computed, never stored ----
    @property
    def duration(self):
        """Timedelta, or None when either stamp is missing — not a zero-length duration."""
        if self.started_at and self.finished_at:
            return self.finished_at - self.started_at
        return None

    @property
    def duration_display(self):
        span = self.duration
        if span is None:
            return "—"
        total = int(span.total_seconds())
        hours, remainder = divmod(total, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours:
            return f"{hours}h {minutes}m"
        if minutes:
            return f"{minutes}m {seconds}s"
        return f"{seconds}s"

    @property
    def size_display(self):
        if self.size_bytes is None:
            return "—"
        size = float(self.size_bytes)
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if size < 1024 or unit == "TB":
                return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    @property
    def is_partial(self):
        """A partial backup: some of the declared scope did not make it."""
        return self.status == "warning"

    @property
    def is_verified(self):
        return self.integrity_verified_at is not None

    @property
    def is_in_flight(self):
        """Has this backup finished? `False` for every settled status — including `failed`/`cancelled`.

        Deliberately NOT `not self.is_verified`, which is the conflation C5 was about: a failed backup
        is *settled*, it has a result, and its missing integrity check is a **finding**. A queued backup
        is not settled and its missing check is **not yet a question**. Two different absences.
        """
        return self.status in self.IN_FLIGHT_STATUSES


class DataArchive(TenantConsistentMixin, models.Model):
    """The catalogue entry that makes a restore possible — the loop 0.8 left open.

    `RetentionPolicy.action="archive"` records that something **should** be archived, and
    `DisposalRecord.method="archived"` records that somebody **says** they archived it. Neither records
    **where it went**, so until a row exists here, "archived" in this codebase means "should have been",
    not "is". `location` is the field this whole model exists for.
    """

    STORAGE_TIER_CHOICES = [
        ("hot", "Hot"),
        ("cool", "Cool"),
        ("archive", "Archive"),
        ("glacier", "Glacier"),
        ("deep_archive", "Deep archive"),
        ("offline", "Offline"),
        ("tape", "Tape"),
    ]
    FORMAT_CHOICES = [
        ("sql", "SQL dump"),
        ("csv", "CSV"),
        ("jsonl", "JSON Lines"),
        ("parquet", "Parquet"),
        ("tarball", "Tarball"),
        ("native", "Native / proprietary"),
        ("other", "Other"),
    ]
    STATUS_CHOICES = [
        ("active", "Active"),
        ("restored", "Restored"),
        ("expired", "Expired"),
        ("lost", "Lost"),
        ("destroyed", "Destroyed"),
    ]
    #: Tiers where a retrieval is an asynchronous job rather than a download — S3 Glacier, Cohesity and
    #: Rubrik all model it this way, and a page implying "click -> restored" would be wrong.
    ASYNC_RETRIEVAL_TIERS = frozenset({"glacier", "deep_archive", "offline", "tape"})

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE,
                               related_name="data_archives", db_index=True)
    name = models.CharField(max_length=150)
    #: POINTS AT 0.8. The chain back to *why* this was archived. Never re-declared here (L36).
    policy = models.ForeignKey("core.RetentionPolicy", on_delete=models.SET_NULL, null=True, blank=True,
                               related_name="archives")
    #: POINTS AT 0.8. The evidence record for the disposal, linked rather than duplicated.
    disposal = models.ForeignKey("core.DisposalRecord", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="archives")
    model_label = models.CharField(max_length=120, blank=True,
                                   help_text="`app_label.Model` that was archived — 0.8's vocabulary.")
    content_description = models.TextField(blank=True)
    #: Required, not blank: without a location a restore is impossible, which is the entire point.
    location = models.CharField(max_length=255,
                                help_text="URI or path where the archive IS.")
    storage_tier = models.CharField(max_length=16, choices=STORAGE_TIER_CHOICES, default="archive")
    format = models.CharField(max_length=16, choices=FORMAT_CHOICES, default="sql")
    record_count = models.PositiveIntegerField(null=True, blank=True)  # NULL != 0
    size_bytes = models.BigIntegerField(null=True, blank=True)         # NULL != 0
    encryption_key = models.ForeignKey("tenants.EncryptionKey", on_delete=models.SET_NULL, null=True,
                                       blank=True, related_name="+")
    checksum = models.CharField(max_length=128, blank=True)
    immutable = models.BooleanField(default=False,
                                    help_text="Recorded claim. Immutability is enforced by the storage, "
                                              "not by NavERP.")
    archived_at = models.DateTimeField(null=True, blank=True)
    restored_at = models.DateTimeField(null=True, blank=True)
    #: An archive with no expiry is a leak. Optional because a WORM archive may legitimately be indefinite.
    expires_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="active")
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-archived_at", "-id"]
        indexes = [
            models.Index(fields=["tenant", "status"], name="darch_tenant_status_idx"),
            # The ordering above needs its own index (I5): `darch_tenant_status_idx` is on `status`, so
            # the optimiser could not use it to satisfy `ORDER BY -archived_at` and fell back to
            # `type=ALL` + `Using filesort` over the whole tenant at 5,000 rows.
            models.Index(fields=["tenant", "-archived_at"], name="darch_tenant_at_idx"),
        ]

    def __str__(self):
        return f"{self.name} @ {self.location}"

    @property
    def is_restorable(self):
        """A location plus a status that still exists. `lost` and `destroyed` are not restorable."""
        return bool(self.location) and self.status in {"active", "restored"}

    @property
    def retrieval_is_async(self):
        return self.storage_tier in self.ASYNC_RETRIEVAL_TIERS

    @property
    def tier_display_long(self):
        if self.retrieval_is_async:
            return f"{self.get_storage_tier_display()} — cold / asynchronous retrieval"
        return self.get_storage_tier_display()

    @property
    def age_days(self):
        if self.archived_at is None:
            return None
        return (timezone.now() - self.archived_at).days

    @property
    def record_count_display(self):
        return "—" if self.record_count is None else f"{self.record_count:,}"

    @property
    def size_display(self):
        if self.size_bytes is None:
            return "—"
        size = float(self.size_bytes)
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if size < 1024 or unit == "TB":
                return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"


class RestoreRecord(TenantConsistentMixin, models.Model):
    """A restore as an **operation** with a source, a target and an outcome — not a button.

    This is where "per-tenant restore" lives and why it is hard: NavERP is a **pooled** multi-tenant
    system (shared tables, a `tenant_id` column), and no managed backup can restore one tenant. The
    honest procedure is point-in-time-recover to a clone, then extract that tenant's rows — which is why
    `tenant` here is the *target* tenant and `reason` is asked for on every record.
    """

    SCOPE_CHOICES = [
        ("full_instance", "Full instance"),
        ("per_tenant", "Per tenant"),
        ("table", "Table"),
        ("record", "Record"),
        ("sandbox_refresh", "Sandbox refresh"),
        ("archive_retrieval", "Archive retrieval"),
    ]
    STATUS_CHOICES = [
        ("planned", "Planned"),
        ("running", "Running"),
        ("succeeded", "Succeeded"),
        ("partial", "Partial"),
        ("failed", "Failed"),
        ("rolled_back", "Rolled back"),
    ]

    #: The TARGET tenant. This field is what makes a restore "per-tenant".
    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE,
                               related_name="restore_records", db_index=True)
    backup = models.ForeignKey("core.BackupJob", on_delete=models.SET_NULL, null=True, blank=True,
                               related_name="restores")
    archive = models.ForeignKey("core.DataArchive", on_delete=models.SET_NULL, null=True, blank=True,
                                related_name="restores")
    scope = models.CharField(max_length=20, choices=SCOPE_CHOICES, default="full_instance")
    #: The PITR instant, chosen INSIDE the recorded window. Validated in `clean()` — a target outside the
    #: window is not restorable, and storing it silently would be the false all-clear 0.8 warns about.
    target_time = models.DateTimeField(null=True, blank=True)
    target_environment = models.ForeignKey("core.EnvironmentInstance", on_delete=models.SET_NULL,
                                           null=True, blank=True, related_name="restores")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="planned")
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                     blank=True, related_name="+")
    reason = models.CharField(max_length=255, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    outcome = models.TextField(blank=True)
    #: A restore that RAN is not a restore that VERIFIED — Azure's app-consistent vs crash-consistent
    #: distinction is the same idea.
    is_verified = models.BooleanField(default=False)
    evidence = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["tenant", "-created_at"], name="recrec_tenant_at_idx"),
        ]

    def __str__(self):
        return f"{self.get_scope_display()} -> {self.get_status_display()}"

    def clean(self):
        """Refuse a target time that is not actually restorable, rather than storing a wish."""
        super().clean()
        if self.target_time is not None:
            if self.target_time > timezone.now():
                raise ValidationError(
                    {"target_time": "A recovery target cannot be in the future — that point does not "
                                    "exist yet."})
            if self.backup is not None and self.backup.started_at is not None:
                if self.target_time < self.backup.started_at:
                    raise ValidationError(
                        {"target_time": "This target predates the selected backup, so it falls outside "
                                        "the recoverable window this record claims."})
        # A retrieval with no archive has nothing to retrieve from.
        if self.scope == "archive_retrieval" and self.archive is None:
            raise ValidationError(
                {"archive": "An archive retrieval needs the archive it retrieves from."})
        # The source must be one that CAN be read. `DataArchive.is_restorable` is the property this
        # sub-module added for exactly this purpose, and this register is the only evidence a restore
        # happened — so recording a restore from an archive whose own page says it is lost, destroyed
        # or has no location would be a false clearance of the same shape 0.8 refuses when it declines
        # to report a `0` it cannot justify. The rule lives at the MODEL edge, not in the form's
        # queryset, so the admin and the seeder are covered too — and the seeder plants the bait on
        # purpose ("Legacy CRM export (media lost)", `status="lost"`, `location=""`).
        if self.archive is not None and not self.archive.is_restorable:
            raise ValidationError(
                {"archive": "This archive is marked lost or destroyed, or has no location — it cannot "
                            "be the source of a restore."})
        # A restore that is not merely planned must name a source.
        if self.status != "planned" and self.backup is None and self.archive is None:
            raise ValidationError(
                {"backup": "Name the backup or archive this restore came from — a recorded restore with "
                           "no source cannot be audited."})

    @property
    def source_label(self):
        if self.backup is not None:
            return self.backup.name
        if self.archive is not None:
            return self.archive.name
        return "not recorded"

    @property
    def duration_display(self):
        if self.started_at and self.finished_at:
            total = int((self.finished_at - self.started_at).total_seconds())
            hours, remainder = divmod(total, 3600)
            minutes, seconds = divmod(remainder, 60)
            if hours:
                return f"{hours}h {minutes}m"
            if minutes:
                return f"{minutes}m {seconds}s"
            return f"{seconds}s"
        return "—"


class EnvironmentInstance(TenantConsistentMixin, models.Model):
    """A provisioned environment — bullets 2 and 5, built **once**.

    Bullet 2 says "sandbox refresh"; bullet 5 says "dev/test/staging provisioning and data-subset
    seeding". Those are the same capability, so this is one model: `kind` is bullet 5's provisioning,
    `copy_scope`/`subset_rule` are its data-subset seeding, and `refresh_*` is bullet 2's refresh.

    Nothing here provisions anything. A row with `status="active"` records that a **person says** the
    environment is up — and a record of a sandbox that does not exist is the inverted version of the
    fake-delete this codebase already refuses.
    """

    KIND_CHOICES = [
        ("production", "Production"),
        ("development", "Development"),
        ("test", "Test"),
        ("staging", "Staging"),
        ("training", "Training"),
        ("sandbox", "Sandbox"),
        ("preview", "Preview"),
    ]
    COPY_SCOPE_CHOICES = [
        ("none", "Empty — no data"),
        ("metadata_only", "Metadata / configuration only"),
        ("summary", "Summary — data subset"),
        ("full", "Full copy"),
    ]
    STATUS_CHOICES = [
        ("requested", "Requested"),
        ("provisioning", "Provisioning"),
        ("active", "Active"),
        ("refreshing", "Refreshing"),
        ("ready_to_activate", "Ready to activate"),
        ("suspended", "Suspended"),
        ("expired", "Expired"),
        ("reaped", "Reaped"),
    ]

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE,
                               related_name="environment_instances", db_index=True)
    name = models.CharField(max_length=150)
    kind = models.CharField(max_length=16, choices=KIND_CHOICES, default="sandbox")
    #: Free text: a Salesforce "Developer Pro" is a commercial tier, not a property of the environment.
    tier = models.CharField(max_length=20, blank=True)
    #: Self-FK, because NetSuite's refresh source is production *or another sandbox*.
    source_environment = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True,
                                           related_name="derived_environments")
    copy_scope = models.CharField(max_length=16, choices=COPY_SCOPE_CHOICES, default="metadata_only")
    #: The DECLARED subset rule (Salesforce sandbox template). A record, not an execution — nothing here
    #: can select rows.
    subset_rule = models.TextField(blank=True,
                                   help_text="Which data, how much, and from where. Declared, not run.")
    copy_includes_pii = models.BooleanField(default=False)
    masking_required = models.BooleanField(default=False,
                                           help_text="Copying production PII downward is the classic "
                                                     "compliance failure. Records the obligation; "
                                                     "NavERP does not mask.")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="requested")
    refreshed_at = models.DateTimeField(null=True, blank=True)
    refresh_source = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True,
                                       related_name="refreshed_from")
    refresh_interval_days = models.PositiveSmallIntegerField(null=True, blank=True)
    #: The reaping date. An un-reaped sandbox is both a cost and a leak.
    expires_at = models.DateTimeField(null=True, blank=True)
    storage_limit_mb = models.PositiveIntegerField(null=True, blank=True,
                                                   help_text="Declared capacity. Not enforced here.")
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["tenant", "kind"], name="envinst_tenant_kind_idx"),
            # The ordering above needs its own index (I5) — `envinst_tenant_kind_idx` is on `kind`, so
            # `ORDER BY name` was an unindexed filesort over every environment in the tenant.
            models.Index(fields=["tenant", "name"], name="envinst_tenant_name_idx"),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_kind_display()})"

    def _refuse_cycle(self, field_name):
        """Walk `field_name` upward from the proposed parent and refuse if it leads back to `self`.

        The self-FK is the NetSuite refresh chain ("production *or another sandbox*"), so the obvious
        way to render "derived from → → production" is `while env.source_environment:` — which loops
        forever on a cycle. A→B is legitimate; B→A is not, and the only guard was self-exclusion, which
        the operator cannot even see (I8). The walk is bounded by the number of environments in the
        workspace and stops early on a pre-existing cycle it did not cause.
        """
        proposed_parent_id = getattr(self, f"{field_name}_id")
        if proposed_parent_id is None or self.pk is None:
            return
        model = type(self)
        seen = set()
        current_id = proposed_parent_id
        while current_id is not None:
            if current_id == self.pk:
                raise ValidationError(
                    {field_name: "That would create a loop — the environment you selected already "
                                 "derives from this one."})
            if current_id in seen:
                break
            seen.add(current_id)
            current_id = (model.objects.filter(pk=current_id)
                          .values_list(f"{field_name}_id", flat=True).first())

    def clean(self):
        super().clean()
        if self.source_environment_id is not None and self.source_environment_id == self.pk:
            raise ValidationError({"source_environment": "An environment cannot be derived from itself."})
        if self.refresh_source_id is not None and self.refresh_source_id == self.pk:
            raise ValidationError({"refresh_source": "An environment cannot be refreshed from itself."})
        # A self-edge is the shortest cycle; these catch every longer one (A→B→A) that the shipped edit
        # form accepted, because a one-dropdown mistake must not be able to create a state that hangs
        # the next page written against the chain.
        self._refuse_cycle("source_environment")
        self._refuse_cycle("refresh_source")
        if self.expires_at is not None and self.created_at is not None:
            if self.expires_at < self.created_at:
                raise ValidationError({"expires_at": "An environment cannot expire before it was created."})
        if self.copy_includes_pii and self.copy_scope == "none":
            raise ValidationError(
                {"copy_includes_pii": "This copy scope carries no data, so it cannot include production "
                                      "PII. Either widen the copy scope or clear this flag."})

    @property
    def is_expired(self):
        """Past its reaping date and not yet reaped — the state that costs money."""
        if self.expires_at is None or self.status in {"expired", "reaped"}:
            return False
        return self.expires_at < timezone.now()

    @property
    def contains_production_data(self):
        return self.copy_scope == "full" and self.copy_includes_pii


class RecoveryPosture(TenantConsistentMixin, models.Model):
    """The tenant's DR **targets** — one row, an edit page, no CRUD.

    A `OneToOne` because a workspace has exactly one recovery posture, so the house
    list/detail/create/edit/delete shape does not apply (the same reasoning as 0.15's `LocaleProfile` and
    0.10's `BusinessCalendar`).

    **Targets live here and never on a drill.** A drill carries *measured actuals*; a posture carries the
    *editable intention*. Collapsing the two would let a missed objective silently rewrite itself into a
    met one — which is precisely why AWS, Azure Site Recovery and ISO 22301 all keep them apart.
    """

    REPLICATION_MODE_CHOICES = [
        ("none", "None"),
        ("sync", "Synchronous"),
        ("async", "Asynchronous"),
    ]

    tenant = models.OneToOneField("core.Tenant", on_delete=models.CASCADE,
                                  related_name="recovery_posture", db_index=True)
    rpo_target_minutes = models.PositiveIntegerField(
        null=True, blank=True, help_text="Recovery point objective: how much data loss is acceptable.")
    rto_target_minutes = models.PositiveIntegerField(
        null=True, blank=True, help_text="Recovery time objective: how long an outage may last.")
    replication_mode = models.CharField(max_length=10, choices=REPLICATION_MODE_CHOICES, default="none")
    primary_region = models.CharField(max_length=80, blank=True)
    dr_region = models.CharField(max_length=80, blank=True)
    backup_retention_days = models.PositiveIntegerField(null=True, blank=True)
    dr_plan_reference = models.CharField(max_length=255, blank=True,
                                         help_text="Where the plan itself lives. NavERP stores the "
                                                   "reference, not the document.")
    last_reviewed_at = models.DateField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "recovery posture"
        verbose_name_plural = "recovery posture"

    def __str__(self):
        return f"Recovery posture ({self.tenant})"

    @property
    def has_targets(self):
        return self.rpo_target_minutes is not None or self.rto_target_minutes is not None

    @staticmethod
    def _minutes_display(value):
        if value is None:
            return "not set"
        if value < 60:
            return f"{value} min"
        hours, minutes = divmod(value, 60)
        return f"{hours}h" if minutes == 0 else f"{hours}h {minutes}m"

    @property
    def rpo_display(self):
        return self._minutes_display(self.rpo_target_minutes)

    @property
    def rto_display(self):
        return self._minutes_display(self.rto_target_minutes)

    @property
    def replication_is_configured(self):
        return self.replication_mode != "none" and bool(self.dr_region)


class RecoveryDrill(TenantConsistentMixin, models.Model):
    """One rehearsal — bullet 3's **actual** half, and the only place a measured RPO/RTO is recorded.

    ISO 22301 and NIST SP 800-34 both make the *exercise* the evidence that a plan works, and AWS's own
    guidance is blunt that initiating a drill "is not adequate to declare success". So `findings` is the
    deliverable of this record, not the outcome alone.
    """

    KIND_CHOICES = [
        ("planned_failover", "Planned failover"),
        ("unplanned_failover", "Unplanned failover"),
        ("test_failover", "Test failover (isolated)"),
        ("tabletop", "Tabletop exercise"),
        ("backup_restore_test", "Backup restore test"),
    ]
    OUTCOME_CHOICES = [
        ("not_run", "Not yet run"),
        ("passed", "Passed"),
        ("partial", "Partial"),
        ("failed", "Failed"),
    ]

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE,
                               related_name="recovery_drills", db_index=True)
    name = models.CharField(max_length=150)
    kind = models.CharField(max_length=24, choices=KIND_CHOICES, default="test_failover")
    scheduled_for = models.DateField(null=True, blank=True)
    performed_at = models.DateTimeField(null=True, blank=True)
    outcome = models.CharField(max_length=10, choices=OUTCOME_CHOICES, default="not_run")
    #: MEASURED, not targeted. Never written back to `RecoveryPosture`.
    measured_rpo_minutes = models.PositiveIntegerField(null=True, blank=True)
    measured_rto_minutes = models.PositiveIntegerField(null=True, blank=True)
    participants = models.CharField(max_length=255, blank=True)
    findings = models.TextField(blank=True, help_text="What the drill actually showed. The deliverable.")
    follow_up_actions = models.TextField(blank=True)
    evidence = models.CharField(max_length=255, blank=True)
    performed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                     blank=True, related_name="+")
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-performed_at", "-id"]
        indexes = [
            models.Index(fields=["tenant", "outcome"], name="drill_tenant_outcome_idx"),
            # The ordering above needs its own index (I5) — `drill_tenant_outcome_idx` is on `outcome`,
            # so `ORDER BY -performed_at` was an unindexed filesort over every drill in the tenant.
            models.Index(fields=["tenant", "-performed_at"], name="drill_tenant_perf_idx"),
        ]

    def __str__(self):
        return f"{self.name} · {self.get_outcome_display()}"

    def clean(self):
        super().clean()
        if self.outcome != "not_run" and self.performed_at is None:
            raise ValidationError(
                {"performed_at": "A drill that produced an outcome has a date. Record when it ran."})

    #: Measurement vs target comparison. A `None` result means "cannot tell" and the page must say so —
    #: it must never be rendered as a pass or a zero.
    def _target_note(self, measured, target_minutes, label):
        if measured is None:
            return {"state": "unknown", "text": f"{label} not measured."}
        if target_minutes is None:
            return {"state": "unknown", "text": f"{label} measured; no target set to compare against."}
        if measured <= target_minutes:
            return {"state": "met", "text": f"{label} {measured} min — within the {target_minutes} min target."}
        return {"state": "missed",
                "text": f"{label} {measured} min — over the {target_minutes} min target."}

    def target_notes(self, posture):
        """`posture` may be None: with no posture there are no targets, and that is stated, not guessed."""
        if posture is None:
            return {"rpo": {"state": "unknown", "text": "No recovery posture is recorded for this "
                                                        "workspace, so there is no target to compare."},
                    "rto": {"state": "unknown", "text": "No recovery posture is recorded for this "
                                                        "workspace, so there is no target to compare."}}
        return {
            "rpo": self._target_note(self.measured_rpo_minutes, posture.rpo_target_minutes, "RPO"),
            "rto": self._target_note(self.measured_rto_minutes, posture.rto_target_minutes, "RTO"),
        }

    @property
    def measured_rpo_display(self):
        return RecoveryPosture._minutes_display(self.measured_rpo_minutes)

    @property
    def measured_rto_display(self):
        return RecoveryPosture._minutes_display(self.measured_rto_minutes)
