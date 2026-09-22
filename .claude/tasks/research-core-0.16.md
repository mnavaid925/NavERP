# Research — Sub-module 0.16: Backup, Recovery & Data Lifecycle (Module 0, `core`)

Domain surveyed: **enterprise backup & disaster recovery for multi-tenant SaaS**, plus **environment /
sandbox provisioning**. The commercial question every product answers is: *"given that the bytes live
somewhere I do not control, what must I record so that a recovery is provable?"* — and the invariant
across all of them is that the **catalogue row is separate from the bytes**, and a restore is an
**operation with a source, a target and an outcome**, not a button.

Supersedes nothing: `plan-1-0.16-ownership-reconcile.md` is the authority on the boundary, and this file
does not relitigate it.

---

## As-built boundary (read this before proposing anything)

**Owned by 0.8 (`apps/core/models/Retention.py`, `apps/core/views/Privacy.py`) — 0.16 must NOT re-declare
any of it:**

| existing | what it already is | who surfaces it |
|---|---|---|
| `core.RetentionPolicy` | per-tenant, per-data-category: `retention_months`, `action` ∈ {review, delete, anonymize, **archive**}, `basis`, optional `model_label`, `is_active` | `core:retention_policy_list` |
| `core.DisposalRecord` | the *evidence* of a disposal: `method` ∈ {deleted, anonymized, **archived**, destroyed_media, other}, `record_count`, `performed_at`, `performed_by`, `evidence` | `core:disposal_list` |
| `core:retention_board` | COMPUTED board walking each active policy's pinned `model_label`, refusing to print a `0` it cannot justify | 0.8's `LIVE_LINKS` bullet |

`LIVE_LINKS["0.8"]` already claims **"Data Archival & Purging — cold-storage archival, legal holds, and
policy-based purging"** (`NavERP.md:233`). 0.16 supplies **only the two things a schedule structurally
cannot express**:

1. **A legal hold** — an *event with a release* that **suspends** the schedule. `RetentionPolicy` has no
   way to say "this window does not apply right now." (Research **confirms** this; see Bullet 4.)
2. **An archive catalogue** — `action="archive"` says *that* something was archived; nothing records
   *where it went*, so a restore is impossible.

**Also out of scope, owned elsewhere:**
- `tenants.HealthMetric`, `tenants.UsageRecord`/`PLAN_ALLOWANCES`, uptime/error/APM/capacity dashboards,
  status pages → **0.17**.
- `core.RateLimitPolicy`, WAF/IP lists/bot protection → **0.18**.
- `tenants.Subscription`/`SubscriptionInvoice`, entitlements, seats, renewals → **0.19**.
- `core.AuditLog` is **written into** by 0.16 (`write_audit_log`), never re-declared.
- `core.BusinessRuleLog` → **0.17**'s raw material.
- `core.SyncSchedule` (0.13) — a **recorded schedule intention**, `FREQUENCY_CHOICES` ∈ {manual, hourly,
  daily, weekly}. 0.16 **reuses its shape/vocabulary** for backup schedules rather than growing a second
  schedule table. It is *not* a scheduler; its own docstring says "Nothing runs it."

**FKs verified to exist** (recursive grep over model packages, not assumed):
`core.Tenant` `apps/core/models/Tenant.py:17` · `core.AuditLog` `apps/core/models/AuditLog.py:5` ·
`core.Document` `apps/core/models/Document.py:5` · `core.Party` `apps/core/models/Party.py:5` ·
`core.RetentionPolicy` `apps/core/models/Retention.py:22` ·
`tenants.EncryptionKey` `apps/tenants/models/EncryptionKey.py:5` ·
`tenants.HealthMetric` `apps/tenants/models/HealthMetric.py:5` ·
`tenants.UsageRecord` `apps/tenants/models/UsageRecord.py:30` · `accounts.User` (`AUTH_USER_MODEL`).
Both `core` and `tenants` `models/__init__.py` re-export every symbol, so `"tenants.EncryptionKey"` as a
string FK resolves. **`core` is FLAT** (`apps/core/models/Backup.py`) — no sub-module folder.

**Migration:** `core/0013_backup_recovery_data_lifecycle.py` is **already claimed and committed** at claim
time (empty operations) — see `plan-1-0.16-ownership-reconcile.md:109` and the placeholder file.

---

## Products surveyed

| Product | What it is, and what it contributed |
|---|---|
| **AWS Backup + RDS automated backups / PITR** | Managed backup for RDS/EBS/S3/DynamoDB. Backup *plans* assign resources to a *vault* with a schedule + lifecycle (warm→cold). **Contributed:** the isolation of **backup rule (schedule) / backup plan / vault (location) / recovery point (the backup itself)**; continuous backups giving a **recovery window** with a chosen target time inside it; `KmsKeyId` on the recovery point as a **reference**; and PITR as "restore to *any* second in the retention window." |
| **Azure Backup + Azure Site Recovery** | VM/SQL/Files backup with recovery-services vaults; ASR replicates VMs cross-region with a **replication policy** carrying `recoveryPointRetentionInHours` and an **app-consistent vs crash-consistent** snapshot type. **Contributed:** RPO expressed as a **policy property**; the four-way failover vocabulary (**test failover / planned / unplanned / reprotect**) and separation of a **Test Failover** from a real one. |
| **Google Cloud Backup and DR (Backup Vaults)** | Regional vault with **enforced retention**, **immutability/indelibility**, **retention inheritance** from the plan, and a permanently **lockable** minimum retention. Hierarchy is **vault → data source → backup** where a *backup* = "a discrete point-in-time recovery point." **Contributed:** the cleanest statement of **backup-object-as-catalogue-entry**, and that **enforced retention is a floor the plan cannot go below**. |
| **Veeam Backup & Replication (incl. Veeam Backup for Microsoft 365)** | The industry reference for a backup *job*. **Contributed:** the **job session** as the unit — status ∈ {Success, **Warning**, Failed} where **Warning = partial** (some VMs skipped/anomalous) and is deliberately distinct from Failed; **retry count** as a first-class metric; separate job types (backup, replication, **backup copy**, backup-to-tape); "forever incremental" + synthetic full; and the recovery *catalog* that a restore reads instead of the media. |
| **Rubrik** | SLA-Domain-driven protection ("protect with policy X"), **immutability + legal hold on SLA domains**, and archival tiering. **Contributed:** SLA Domain = the schedule+retention+immutability bundle; **legal hold as an SLA-domain property that outlives the retention window.** |
| **Cohesity** | Converged data platform with **long-term retention & archival to cold cloud tiers** ("retain local, archive to cloud, or tier cold data based on policy"). **Contributed:** **storage class / tier** as a real field on an archive (hot / archive / glacier-class), and policy-based tiering as distinct from deletion. |
| **Commvault (+ Metallic)** | Recovery **catalog** service that indexes every recovery point (client, agent, backup set, job, timestamp, size, location) so a restore browses the catalog and never the media. **Contributed:** **the catalogue is the product's brain and the media is dumb**; restore = pick a recovery point from the catalogue. |
| **Druva** | SaaS-native (agentless) backup with a **curated "curator" for legal hold / compliance** and cloud archival. **Contributed:** legal hold in a SaaS context as a **curation-set property with a hold reason**, and the point that SaaS backup **cannot be tested by the vendor's success message alone** — you must record *last verified restore*. |
| **Backblaze B2 / S3 Glacier-class cold storage** | Object storage whose pricing model *is* the lifecycle. **Contributed:** the **storage-class transition** as data (`hot → cool → archive → deep-archive`), a minimum-storage-duration penalty, and retrieval-as-an-async-job (an archive restore is **not instant**). |
| **Salesforce (Data Loader, Backup & Restore, Sandboxes)** | Four **sandbox types** — Developer, Developer Pro, **Partial Copy**, **Full** — differing by storage, refresh interval and whether a **sandbox template defines a data subset**. **Contributed:** **sandbox type as an enum with per-type storage + refresh cadence**, partial-copy + template as the **data-subset seeding** mechanism, and the explicit obligation to **not copy production PII** (masking). |
| **ServiceNow (instance backup/restore, Clone)** | Full/partial backups with a ~14-day retention, a documented **restore workflow**, and **Clone** (production → sub-production). **Contributed:** the **restore-by-request workflow**, clone as a refresh, and **clone-preserved records** (exclude tables like users/sys_ properties from the copy). |
| **NetSuite (Sandbox refresh)** | Sandbox refreshed **from production**; **all configurations, data, user passwords and customizations** are copied and **target changes are OVERWRITTEN**; the sandbox stays **online during the copy**, then an admin **activates** it and the previous version is deleted; refresh takes **hours→72h**. **Contributed:** the exact states of a refresh (**requested → preparing → ready → activated**) and the honest point that a refresh **destroys the target**. |
| **Workday (tenant management)** | Tenant types: **Production, Sandbox, Sandbox Preview** (production + next-release features), **Implementation** tenants; metadata (vendor-owned) vs **tenanted data** (customer-owned). **Contributed:** environments as **typed, numbered tenants** and the preview/production distinction as a *purpose*, not a size. |
| **Standards: ISO 22301, NIST SP 800-34, 3-2-1, WORM, eDiscovery hold** | ISO 22301 = BCM system + BIA + RTO/RPO; NIST SP 800-34 = contingency planning (BIA → recovery strategies → plan → **testing, training, exercises**); 3-2-1 = three copies, two media, one off-site; WORM = write-once-read-many; eDiscovery hold = preservation triggered by **reasonable anticipation of litigation**. **Contributed:** the **RPO/RTO-as-target-vs-actual** split, the **drill** as a documented exercise, and the decisive hold-suspends-schedule ruling. |
| **Atlassian Cloud Backup & Restore** | Org-level backup policies for Jira/Confluence with a defined expiry window (restorable "until the backup expires", 30 days to act). **Contributed:** **backup expiry** as an explicit field and "you have N days from X to act." |

---

## Feature catalog, by bullet

### Bullet 1 — Automated Backups: "Scheduled full/incremental backups with encryption and integrity checks."

| Feature | Verdict | Source / reasoning |
|---|---|---|
| Backup **register row** = one recorded backup: scope label, type, schedule reference, started/ended, size, target, status | **[core]** | Veeam *job session*; GCP *backup* object; AWS *recovery point*. This is the whole point of bullet 1. |
| **Backup type** enum: `full`, `incremental`, `differential`, `log`/`transaction_log`, `snapshot` | **[core]** | AWS Backup (snapshot vs continuous), Veeam (full/inc/synthetic full), Azure (app- vs crash-consistent is *separate* from type — do not conflate). NavERP stores the *declared* type; it cannot compute a delta. |
| **Schedule expression** (frequency + window), reusing 0.13's `FREQUENCY_CHOICES` vocabulary | **[core]** | AWS backup *rule*; Veeam schedule; 0.13's `SyncSchedule` precedent. A **record**, not a job (§ The honest limit). |
| **Retention** on the backup (days/months) | **[core]** | Every product. Distinct from `RetentionPolicy` (0.8), which is about *data categories*; this is about *a backup artefact's* lifetime. Note the non-collision explicitly. |
| **Target / location** (free text URI or path) + **storage tier/class** | **[core]** | Cohesity tiers, S3 Glacier classes, AWS vault. **Free text**, because NavERP has no object storage to name (L36). |
| **Encryption**: FK to `tenants.EncryptionKey` + an enum of the *scheme* | **[core]** | AWS `KmsKeyId` is a **reference**; GCP uses **CMEK** or Google-managed. `EncryptionKey` stores **only `prefix` + `key_hash`, never plaintext** — so a FK is the only honest option. |
| **Integrity**: verification method + result + verified-at + checksum | **[core]** | Every product verifies; the *result* is what is recorded. Distinguish **"verified OK"** from **"not verified"** — never coerce the second into the first (0.8's `retention_board` posture). |
| **Status lifecycle** (see below) | **[core]** | Veeam's Success/Warning/Failed/Working/Idle/Retrying. |
| **Failure/partial reason** as an enum + free-text detail | **[core]** | Veeam distinguishes Warning (partial) from Failed; the session detail carries error text. A register with only success/failed is the naive build. |
| **Retry count** / attempt number | **[optional]** | Veeam `retry count`. A **hand-entered** integer is honest here (NavERP cannot count retries itself); keep it small. |
| **`is_verified_restorable` / last restore test** | **[optional]** | Druva's *last verified restore* is the only field that makes a backup claim mean anything; Rubrik/Druva both surface it. Strong contender for [core] if the model budget allows — see Recommended scope. |
| Actual backup **execution** (a real `mysqldump`/`xtrabackup` run) | **[out of scope]** | **No scheduler, no object storage, no ability to dump MySQL.** A GET-triggered dump is exactly the destructive-by-bookmark failure `Retention.py:5` refuses. The act is out of band. |
| **Backup plan / policy engine** with resource assignment, lifecycle transitions, vault objects | **[out of scope]** | AWS/GCP model plans + vaults as first-class; NavERP's `tenants` layer is not an app, and a vault has no meaning with no storage. Collapsing plan+vault into fields on the backup row is correct at this size. |
| Deduplication, compression ratios, synthetic fulls, forever-incremental chains | **[out of scope]** | Needs a real engine (Veeam/Rubrik); recording a fabricated ratio would be dishonest. |
| Immutability/WORM enforcement | **[out of scope — but record the claim]** | S3 Object Lock / GCP enforced retention can only be *enforced* by the storage. 0.16 may record an *immutability flag + retain-until* as a **claim about the target**, never as an enforcement. |

**Standard backup lifecycle states** (as real products name them): `queued`/`pending` → `running`
(Veeam `Working`) → terminal `success` | `warning` (partial — some scope skipped/anomalous) | `failed`
| `cancelled`; plus `retrying`. Veeam's report vocabulary is literally **{Success, Warning, Failed}**
with duration, transferred data, objects-with-anomalies and retry count.

**Standard failure reasons** (collapsed from Veeam KB/community, AWS, Azure): `source_unreachable`,
`auth_failed` (credential/permission), `insufficient_space` (target full/quota), `timeout`,
`integrity_check_failed` (checksum mismatch), `cancelled_by_operator`, `licence_or_quota`,
`partial_scope_skipped`, `unknown`. A **`warning` state with a partial reason** is the field a naive
build omits — and it is the field that matters, because a partial backup is worse than a failed one
(people trust it).

---

### Bullet 2 — Point-in-Time Recovery: "Restore to timestamps, per-tenant restore, and sandbox refresh."

| Feature | Verdict | Source / reasoning |
|---|---|---|
| **Recovery window / range** — earliest→latest recoverable point | **[core]** | RDS PITR: "restore to any point in the retention window." A window is a **computed** pair of timestamps from the register, not a stored row. |
| **Target timestamp** chosen inside the window, validated against it | **[core]** | Every PITR implementation. Must be **validated** (inside window, ≤ now) at the model edge — a target outside the window is not restorable and must be refused, not silently stored. |
| **Restore operation record**: source (backup FKs), target time, target environment, status, started/ended, duration, requested-by, reason, outcome | **[core]** | ASR *Recovery job history*; ServiceNow restore request; Commvault recovery catalog. This is `RestoreRecord`. |
| **Restore status lifecycle**: `planned` → `running` → `succeeded` | `partial` | `failed` | `rolled_back` | **[core]** | ASR shows Pending/Successful; ServiceNow runs a restore workflow. `partial` is essential for a per-tenant restore that got some tables. |
| **Restore *scope*** enum: `full_instance`, `per_tenant`, `table`, `record`, `sandbox_refresh`, `archive_retrieval` | **[core]** | The AWS SaaS post names exactly these granularities; §Bullet 5's sandbox refresh is one of them, and saying so prevents a double build. |
| **Per-tenant restore with an explicit `tenant` scope FK** | **[core]** | The AWS post's whole thesis: in a **pool** model (shared tables + `tenant_id`) — which NavERP is — restore is **PITR-to-clone then extract-that-tenant's-rows**, because no managed backup can restore one tenant. The record must say *which tenant*, and the page must say *why it is the hard case*. |
| **Target environment FK** for the restore (where it went) | **[core]** | ASR restores to a recovery region; NetSuite to a sandbox. Overlaps Bullet 5 — see the dedup note. |
| **Verification / point-of-recovery-recorded** (`is_verified`, verified_at) | **[optional]** | Azure *app-consistent* vs *crash-consistent* is the closest analogue: a restore that booted is not a restore that verified. |
| **Actual restore execution** against MySQL, with downtime orchestration | **[out of scope]** | Requires DB credentials, locking, and a maintenance window. Out of band; the record is written by hand after the DBA does it. |
| Restore-performance tuning, instance rightsizing, temporary-clone lifecycle | **[out of scope]** | Needs real infra (Aurora Serverless v2 etc.). |
| "Restore to a *point between* backups" (true continuous/log-based) | **[out of scope — but honest]** | NavERP has no binlog shipping. The window is a **claim about the backup set**, and the page must say a target time is *within the recorded window*, not *guaranteed bit-exact*. |

---

### Bullet 3 — Disaster Recovery & Failover: "Multi-region replication, RPO/RTO targets, and failover drills."

| Feature | Verdict | Source / reasoning |
|---|---|---|
| **RPO/RTO as a TARGET** (policy/intention) | **[core]** | ISO 22301 / NIST SP 800-34 **set** objectives; ASR encodes RPO as a *replication policy property*; AWS's own guidance says test "to validate that your RPO and RTO objectives can be met." Target lives on a **DR plan / posture row**. |
| **RPO/RTO as an ACTUAL** (measured) | **[core]** | AWS DR: a drill's purpose is to *measure*. Actuals are **properties of a drill**, never columns that overwrite the target. The reconcile file says exactly this: `0.16's RecoveryDrill records RPO/RTO measured in a drill`. |
| **Replication configuration**: mode (`sync`/`async`), region pairing, direction, status | **[core] or [optional]** | ASR region pairs + continuous async replication; GCP multi-region vaults (≥2 regions). Recorded as **declared fields** (we cannot observe replication). Lean **[optional]** if the model budget is tight — but region pairing is the substance of "multi-region replication." |
| **Failover drill record** | **[core]** | AWS DRS: `Initiate drill` → a *recovery job* with `Last recovery result` = Successful/Pending; drills run against a **point-in-time snapshot** and are **non-disruptive**. `RecoveryDrill` is genuinely its own model here. |
| Drill **kind** enum: `planned_failover`, `unplanned_failover`, `test_failover` (isolated), `tabletop`, `backup_restore_test` | **[core]** | ASR's four-way vocabulary (test / planned / unplanned / reprotect) is the industry shape; AWS explicitly separates drills from planned events. |
| Drill **outcome** + measured RPO/RTO + **findings/blockers** + follow-up actions | **[core]** | AWS: "conducting a drill … is not adequate to declare success … test at a business-process level"; the drill's *findings* are the deliverable. |
| Drill **participants / evidence reference** | **[optional]** | ISO 22301 walkthroughs are documented exercises; an evidence ref (ticket/runbook) matches `DisposalRecord.evidence`. |
| **Automatic** failover / promotion / DNS cutover | **[out of scope]** | Needs orchestration infra and a live multi-region deployment NavERP does not have. ASR/AWS automate this; we record that a human did it. |
| DR **dashboard** (continuously measured actual RPO lag, replication health) | **[out of scope — 0.17]** | Continuous measurement is observability. 0.16 records drill-time actuals only. |
| Business-impact analysis, MTD, cost-of-downtime modelling | **[out of scope]** | ISO 22301 BIA is a governance exercise with no data model in this codebase; a free-text `objective` / `notes` on the plan covers the record. |

**Target vs actual — the ruling:** **targets are policy** (a plan/posture row, editable, aspirational),
**actuals are measurements** (a property of one drill, immutable, historical). Products keep them apart
because collapsing them lets a missed target silently rewrite itself into a met one. 0.16 must too.

---

### Bullet 4 — Data Archival & Purging: "Cold-storage archival, legal holds, and policy-based purging."

> **Mostly built by 0.8.** Only two gaps. Everything row with a strikethrough is owned by 0.8 and is
> listed *only* so this file is self-contained.

| Feature | Verdict | Source / reasoning |
|---|---|---|
| ~~Retention schedule per data category~~ | **[out of scope — 0.8 `RetentionPolicy`]** | Built. Do not re-declare. |
| ~~Disposal evidence record~~ | **[out of scope — 0.8 `DisposalRecord`]** | Built. Do not re-declare. |
| ~~Computed "what is past its window" board~~ | **[out of scope — 0.8 `core:retention_board`]** | Built. 0.16 may **link** to it. |
| **Legal hold** as an event with issue/release | **[core]** | eDiscovery: a hold is issued on **reasonable anticipation of litigation** (*Zubulake*), names **custodians**, ties to a **matter**, and is **released** with the duty to preserve ending. S3 Object Lock models a legal hold as **having no expiry and being independent of the retention period**. |
| Hold **fields**: custodian/subject, scope/description, matter/case ref, issuing authority, issued date, issued by, status, release date, released by, release reason | **[core]** | Exterro + MS Purview eDiscovery. Tracking who is on **which** holds is called out as the practical backbone — hence an overlapping-holds warning on release. |
| **Hold SUSPENDS the schedule (confirmed)** | **[core — as behaviour, not a field]** | See the ruling below. |
| **Archive catalogue** entry: where the archive went, so a restore is possible | **[core]** | This is 0.8's open loop. Commvault's recovery catalog, GCP's data-source→backup drill-down, Cohesity's archival tier. |
| Archive **fields**: `location`/`uri`, storage `tier`, `format`, content description, `record_count`/byte counts, encryption key FK, `checksum`, `archived_at`, `restored_at`, `expires_at`, chain back to `RetentionPolicy`/`DisposalRecord` | **[core]** | Every field earns its place: without `location` no restore; without `tier` you cannot say "cold storage" (bullet 4's own words) or the retrieval cost; without `checksum`+key you cannot verify; without the FK back you cannot say *what* was archived. |
| Archive **retrieval** as an operation (requested → retrieved → expired) + a **restore** of an archive | **[core]** | Glacier/S3 archival retrieval is an **async job** with a restore window, not a download; Cohesity/Rubrik model retrieval explicitly. |
| **Immutability / WORM** flag + `retain_until` on the archive | **[optional]** | S3 Object Lock / GCP enforced retention. Record as a **claim** (we do not enforce it) — honest, and useful for an audit. |
| Archive **expiry / retention linkage** | **[core]** | GCP enforced-retention floors, Atlassian's backup expiry. An archive with no expiry is a leak; link to `RetentionPolicy` and/or carry `expires_at`. |
| A second **purge engine** / scheduled deletion | **[out of scope — 0.8]** | `RetentionPolicy.action="delete"` + `DisposalRecord` is the mechanism and the evidence. Re-declaring is L36. |
| Auto-tiering / lifecycle transition automation | **[out of scope]** | Needs real storage (Cohesity, S3 lifecycle rules). Record the tier; do not move bytes. |
| "Right to be forgotten" propagation into backups/archives | **[out of scope]** | Genuinely unsolvable without an engine; Druva/Rubrik treat it as a hard problem. Say so rather than pretending. |

**RULING — a hold SUSPENDS the schedule; it is not a field on it (claim CONFIRMED).**
Evidence is unambiguous and comes from three independent directions:
1. **Case law (the origin of the concept):** *Zubulake v. UBS Warburg* — once litigation is reasonably
   anticipated a party "must **suspend** its routine document retention/destruction policy" and put a
   hold in place. The mechanism is literally described as a suspension of the schedule.
2. **Object storage (the mechanism at scale):** AWS S3 Object Lock — a legal hold has **no expiration
   date**, is **independent of** the retention period, and "**if the retention period expires, the object
   doesn't lose its WORM protection … the legal hold continues to protect the object until an authorized
   user explicitly removes the legal hold.**" Protection persists while *either* is active.
3. **SaaS practice:** Rubrik puts legal hold on the SLA domain as a property that **outlives** the
   retention window.

Therefore: a `RetentionPolicy` row **cannot** express a hold, because (a) the hold has **no window** — its
end is an *event*, not a duration, and (b) the hold's effect is **negative** — it defeats a policy that
would otherwise apply, including one created *later*. Modelling it as a field on the policy fails both:
a boolean `is_on_hold` has no release date, no matter, no issuer, and cannot cover a category that spans
multiple policies. **It must be its own table, evaluated as a live override.** A computed board must
still **name every held scope** and refuse to report a "due for deletion" count it cannot justify (0.8's
zero rule), and **refuse a release that would strand the record on another active hold** (Exterro).

---

### Bullet 5 — Sandbox & Environment Management: "Dev/test/staging provisioning and data-subset seeding."

> **Bullets 2 and 5 both mean "make a sandbox."** Built **once**, as `EnvironmentInstance`, with a
> `refresh_from_production` affordance that records the **subset rule** (bullet 2's "sandbox refresh")
> and the **environment kind** (bullet 5's "dev/test/staging provisioning"). One model, two bullets.

| Feature | Verdict | Source / reasoning |
|---|---|---|
| **Environment** record: name, kind, source account, status, storage, expiry | **[core]** | Salesforce 4 sandbox types; Workday Production/Sandbox/Sandbox Preview/Implementation; ServiceNow sub-prod; NetSuite sandbox. This is `EnvironmentInstance`. |
| **Environment kind** enum: `development`, `test`, `staging`, `training`, `sandbox`, `preview`, `production` | **[core]** | Salesforce's Developer/Developer Pro/Partial/Full map to *purpose* + *copy scope*; Workday names the *purpose* (implementation vs preview). A `production` member is needed because a refresh's **source** is production. |
| **Environment type/tier with per-tier capacity + refresh cadence** | **[core]** | Salesforce: storage limit + refresh interval *per type* (Developer ≥1 day, Full = 29 days). Modelled as a **free-text capacity note + `refresh_interval_days`**, not as a hard quota the app cannot enforce. |
| **Copy scope** enum: `none` (empty), `metadata_only` (config only), `summary` (partial), `full` (everything) | **[core]** | Salesforce: Developer (metadata + minimal), Partial Copy (template subset), Full. NetSuite: configs+data+passwords+customizations. This is the *partial vs full copy* axis. |
| **Data-subset / seed rule** (which data, how much, from where) | **[core]** | Salesforce **sandbox templates**; the "Partial Copy" concept. Free text + an optional record-count cap — a *declared* rule, because nothing here can execute it. |
| **Anonymization/masking obligation** flag + notes | **[core]** | Copying production PII into a lower environment is the classic compliance failure; Workday distinguishes vendor metadata from **tenanted data**, and Salesforce requires masking in partial copies. Record the *obligation* and its acknowledgement; do not pretend to mask. |
| **Refresh operation** record: source env, target env, requested/started/completed, status, refresh mode | **[core] — folded** | NetSuite: **requested → preparing → ready → activated**, target **overwritten**, stays online during the copy, previous version deleted on activation. Fold into `EnvironmentInstance`'s own refresh fields *unless* a 5th model is justified (§ Recommended scope). |
| Refresh **overwrites the target** and must warn | **[core — as behaviour]** | NetSuite states plainly that target changes are overwritten. The page must warn before a refresh is recorded, the way NetSuite tells admins to save work outside the sandbox. |
| Environment **status lifecycle**: `requested`, `provisioning`, `active`, `refreshing`, `ready_to_activate`, `suspended`, `expired`, `reaped` | **[core]** | NetSuite's activation step; Salesforce/ServiceNow lifecycle. `expired`/`reaped` matter — an un-reaped sandbox is a cost and a leak. |
| **Expiry / reaping date** | **[core]** | Salesforce sandbox refresh windows; ServiceNow clone validity windows (7 days non-sharded / 2 sharded). An unmetered sandbox is how a licence bill surprises you (**0.19**'s concern, but the date lives here). |
| **No PII** marker / `contains_production_data` flag | **[optional]** | Direct answer to "is this environment safe to test with?" Worth a boolean. |
| Actually **provisioning** a tenant/environment (create schema, seed rows, mask data) | **[out of scope]** | Requires multi-DB/schema provisioning and a real seeder. A record that claims a sandbox exists when nothing was created is the **same lie** `Retention.py` refuses, inverted. |
| Automated **refresh scheduling** | **[out of scope]** | No scheduler. Record the declared cadence; a human runs it. |
| Environment **cost / resource quota enforcement** | **[out of scope — 0.19]** | Metering and seats are 0.19 (`UsageRecord`/`PLAN_ALLOWANCES`). 0.16 records the environment; 0.19 owns its cost. |
| **PII discovery/anonymization engine** | **[out of scope — 0.8]** | `core.PiiClassification` (0.8) already maps PII. 0.16 points at it; it does not build a masking engine. |

---

## Recommended build scope

**Verdict: 5 models — the reconcile file's 4 PLUS `LegalHold` as its own top-level model.** The
reconcile file said "4, plus `LegalHold` carried as a child of the archive design if the contract can
hold it at 4; otherwise 5 and the research phase says so explicitly." **This is that explicit statement:
it cannot hold it at 4.**

**Why `LegalHold` cannot be a child of `DataArchive`** (and therefore must be the 5th model):
1. A hold's scope is a **data category or a model/entity**, which is exactly what `RetentionPolicy`
   governs — **not what an archive is**. Hanging a hold off an archive would make holds inexpressible for
   data that has not been archived, which is the common case.
2. A hold must **suspend** a schedule (proven above). A suspension targets a *policy/schedule*, so the
   hold must be **comparable to** policies — a peer table, not a subordinate of the archive.
3. A hold has **no release until an event**; an archive has an `expires_at`. The lifecycles are
   different shapes and merging them forces a nullable mess.
4. Exterro's overlapping-hold problem needs a **queryable set of active holds per scope**; a child row of
   an archive cannot be that set.

**Why not a 6th model for the DR posture (RPO/RTO targets + replication)?** Because targets are a
**singleton-per-tenant posture**, and this codebase already has the singleton precedent
(`LocaleProfile`, `BusinessCalendar` — one edit page, no CRUD). Folding the target/RPO/RTO/replication
fields onto `RecoveryDrill` would repeat the exact target-vs-actual mistake the research warns against.
The cheapest honest home is a **small `DisasterRecoveryPlan` singleton** — but that is a **6th model**,
and the budget is 4–5. **Recommendation: keep 5 models** and hold the DR target/RPO/RTO fields on a
**`RecoveryDrill`-adjacent posture** only if the contract allows; otherwise state plainly that
**0.16 records drill actuals and defers the RPO/RTO *target* to the DR plan the operator keeps
out of band**, naming the gap. *(Flagged for the orchestrator — this is the one place 5 is tight.)*

### Model 1 — `BackupJob` (`apps/core/models/Backup.py`)

The register of a backup that a human (or an external agent) reports as taken.

| field | type | notes |
|---|---|---|
| `tenant` | FK `core.Tenant` CASCADE, related_name="backup_jobs", db_index | mandatory |
| `name` / `label` | CharField(150) | what is backed up, human label |
| `scope_label` | CharField(255) | e.g. "nav_erp schema", "tenant ACME" — free text; no FK, because NavERP has no backup target object to point at |
| `backup_type` | CharField(16), choices `BACKUP_TYPE_CHOICES` = full / incremental / differential / log / snapshot | **[core]** |
| `frequency` | CharField(12), choices reusing the 0.13 vocabulary: manual / hourly / daily / weekly | the *declared* schedule |
| `retention_days` | PositiveIntegerField(null=True) | backup artefact lifetime — distinct from `RetentionPolicy` |
| `target_location` | CharField(255, blank) | free text URI/path; no object storage exists to FK |
| `storage_tier` | CharField(16), choices = standard / infrequent / archive / deep_archive / tape | bullet 4's "cold storage" |
| `encryption_key` | FK `tenants.EncryptionKey` SET_NULL null blank, related_name="+" | **FK verified** `apps/tenants/models/EncryptionKey.py:5`; stores prefix+hash only, **never plaintext** |
| `encryption_scheme` | CharField(16), choices = none / aes256 / rsa / managed / other | key *reference* vs key *scheme*, separate |
| `size_bytes` | BigIntegerField(null=True) | null = not reported, **not 0** |
| `checksum` | CharField(128, blank) | recorded value |
| `integrity_method` | CharField(16), choices = none / checksum / hash / restore_test / vendor_reported | how it was verified |
| `integrity_verified_at` | DateTimeField(null=True, blank=True) | null = **not verified** — renders as such, never as OK |
| `status` | CharField(16), choices `STATUS_CHOICES` = queued / running / success / **warning** / failed / cancelled | warning = partial; the state a naive build omits |
| `failure_reason` | CharField(24), choices `FAILURE_REASON_CHOICES` = source_unreachable / auth_failed / insufficient_space / timeout / integrity_check_failed / cancelled_by_operator / quota / partial_scope_skipped / unknown / n/a | **[core]** the field that makes the register honest |
| `attempt_count` | PositiveSmallIntegerField(default=1) | hand-entered retry count |
| `is_immutable` | BooleanField(default=False) | a **claim** about the target; NavERP cannot enforce WORM |
| `retain_until` | DateTimeField(null=True, blank=True) | mirrors WORM retain-until |
| `started_at` / `finished_at` | DateTimeField(null=True, blank=True) | duration **derived**, not stored |
| `performed_by` | FK `AUTH_USER_MODEL` SET_NULL null blank, related_name="+" | who recorded it |
| `evidence` | CharField(255, blank) | ticket/job-id/runbook — the `DisposalRecord.evidence` pattern |
| `notes` | TextField(blank) | |
| `created_at` | DateTimeField(auto_now_add=True) | |

**Derived (never stored):** `duration` (= finished − started), `is_verified`, `is_recent`, `is_partial`
(= status == warning), `is_restorable` (= archived FK's checksum present **and** verified).
**Deliberately does NOT store:** the bytes; a computed delta; a plan/vault object; a compression ratio;
key material; a second tenant-scoped retention policy.

### Model 2 — `RestoreRecord` (`apps/core/models/Backup.py`)

A restore as an **operation with a source, a target and an outcome**.

| field | type | notes |
|---|---|---|
| `tenant` | FK `core.Tenant` CASCADE, related_name="restore_records", db_index | the **target** tenant (this is what makes it "per-tenant") |
| `backup` | FK `core.BackupJob` SET_NULL null blank, related_name="restores" | source backup, if one |
| `archive` | FK `core.DataArchive` SET_NULL null blank, related_name="restores" | source archive — a restore may come from either |
| `scope` | CharField(20), choices `SCOPE_CHOICES` = full_instance / per_tenant / table / record / sandbox_refresh / archive_retrieval | the granularity enum; **`sandbox_refresh` is bullet 2's mapping to bullet 5** |
| `target_time` | DateTimeField(null=True, blank=True) | the PITR timestamp chosen **inside** the window |
| `target_environment` | FK `core.EnvironmentInstance` SET_NULL null blank, related_name="restores" | verified: the same app, defined below |
| `status` | CharField(16), choices = planned / running / succeeded / **partial** / failed / rolled_back | partial = "some of the requested scope came back" |
| `requested_by` | FK `AUTH_USER_MODEL` SET_NULL null blank, related_name="+" | who |
| `reason` | CharField(255, blank) | **why** — required by every audit of a restore |
| `started_at` / `finished_at` | DateTimeField(null=True, blank=True) | duration derived |
| `outcome` / `notes` | TextField(blank) | what actually came back |
| `is_verified` | BooleanField(default=False) | restore *ran* ≠ restore *verified* (Azure app- vs crash-consistent) |
| `evidence` | CharField(255, blank) | ticket/runbook |
| `created_at` | DateTimeField(auto_now_add=True) | |

**Clean rule:** `target_time` must fall inside the source backup's recoverable window and be ≤ now —
refused at the model edge (mirrors `StatutoryRule.clean`), because a target outside the window is **not
restorable** and storing it silently is the false all-clear 0.8 warns about.
**Deliberately does NOT store:** an executed restore, a downtime duration the app invented, a
`RecoveryPoint` list (derived), a per-table row count it cannot know.

### Model 3 — `DataArchive` (`apps/core/models/Backup.py`)

The **catalogue entry that makes a restore possible** — the loop 0.8 left open.

| field | type | notes |
|---|---|---|
| `tenant` | FK `core.Tenant` CASCADE, related_name="data_archives", db_index | |
| `name` | CharField(150) | |
| `policy` | FK `core.RetentionPolicy` SET_NULL null blank, related_name="archives" | **FK verified** `Retention.py:22` — the chain back to *why* it was archived. **Points at 0.8; does not re-declare it.** |
| `disposal` | FK `core.DisposalRecord` SET_NULL null blank, related_name="archives" | **FK verified** `Retention.py:62` — the evidence record, linked |
| `model_label` | CharField(120, blank) | `app_label.Model` that was archived (matches 0.8's vocabulary) |
| `content_description` | TextField(blank) | what is in it — a restore decision needs this |
| `location` | CharField(255) | **URI/path where the archive IS.** Without this a restore is impossible — the single field this whole model exists for |
| `storage_tier` | CharField(16), choices = hot / cool / archive / glacier / deep_archive / offline / tape | bullet 4's "cold storage", as data |
| `format` | CharField(16), choices = sql / csv / jsonl / parquet / tarball / native / other | needed to know how to read it back |
| `record_count` | PositiveIntegerField(null=True) | null ≠ 0 |
| `size_bytes` | BigIntegerField(null=True) | null ≠ 0 |
| `encryption_key` | FK `tenants.EncryptionKey` SET_NULL null blank, related_name="+" | **FK verified**; never key material |
| `checksum` | CharField(128, blank) | verify integrity on retrieval |
| `immutable` | BooleanField(default=False) | WORM claim, as above |
| `archived_at` | DateTimeField(null=True, blank=True) | |
| `restored_at` | DateTimeField(null=True, blank=True) | last successful retrieval |
| `expires_at` | DateTimeField(null=True, blank=True) | retention link; an archive with no expiry is a leak |
| `status` | CharField(12), choices = active / restored / expired / lost / destroyed | `lost` is a **real** and necessary state (media lost) |
| `notes` | TextField(blank) | |
| `created_at` | DateTimeField(auto_now_add=True) | |

**Derived:** `is_restorable` (= `location` present **and** `status` ∈ {active, restored}),
`age_days`, `retrieval_is_async` (= tier ∈ {glacier, deep_archive, offline, tape}).
**Deliberately does NOT store:** the archived bytes; an auto-tier transition; a destruction schedule.

### Model 4 — `LegalHold` (`apps/core/models/Compliance.py`) — **the 5th, argued for above**

The event that **overrides** a schedule.

| field | type | notes |
|---|---|---|
| `tenant` | FK `core.Tenant` CASCADE, related_name="legal_holds", db_index | |
| `name` / `title` | CharField(150) | |
| `custodian` | CharField(200, blank) | person/team/entity subject to the hold (Exterro) |
| `subject_party` | FK `core.Party` SET_NULL null blank, related_name="+" | **FK verified** `Party.py:5` — optional link if the custodian is a Party |
| `matter_reference` | CharField(150, blank) | case/matter number (Exterro: every matter has ≥1 hold) |
| `issuing_authority` | CharField(200, blank) | court/regulator/internal counsel |
| `scope` | TextField(blank) | what data/systems the hold covers |
| `retention_policy` | FK `core.RetentionPolicy` SET_NULL null blank, related_name="legal_holds" | **FK verified** — *which* schedule is suspended. Optional: a hold may cover a category with no pinned policy |
| `model_label` | CharField(120, blank) | the entity/category in scope, in 0.8's vocabulary |
| `issued_at` | DateTimeField(default=timezone.now) | |
| `issued_by` | FK `AUTH_USER_MODEL` SET_NULL null blank, related_name="+" | |
| `status` | CharField(12), choices = active / released / expired / superseded | |
| `released_at` | DateTimeField(null=True, blank=True) | **the release event** — the reason a schedule cannot express this |
| `released_by` | FK `AUTH_USER_MODEL` SET_NULL null blank, related_name="+" | |
| `release_reason` | CharField(255, blank) | Exterro: documentation at release is what proves good faith |
| `authority_reference` | CharField(255, blank) | preservation order / notice ref |
| `notes` | TextField(blank) | |
| `created_at` / `updated_at` | DateTimeField | |

**Derived:** `is_active` (= status == active **and** released_at is null), `age_days`.
**Clean rules:** (a) `released_at` cannot precede `issued_at` (mirrors `StatutoryRule.clean`); (b) a
release is **refused with a warning** if another active hold covers the same `model_label`/policy
(Exterro's *no mistaken release* rule — the anti-spoliation control).
**Deliberately does NOT store:** a duration/expiry in place of a release event (that is the mistake
S3 Object Lock's docs call out); an enforcement mechanism.

### Model 5 — `EnvironmentInstance` (`apps/core/models/Backup.py`)

Bullets 2 and 5's shared "make a sandbox," built once.

| field | type | notes |
|---|---|---|
| `tenant` | FK `core.Tenant` CASCADE, related_name="environment_instances", db_index | |
| `name` | CharField(150) | |
| `kind` | CharField(16), choices `KIND_CHOICES` = production / development / test / staging / training / sandbox / preview | 5's provisioning; `preview` = Workday's "next release" purpose |
| `tier` | CharField(20, blank) | free text (Salesforce Developer/Developer Pro/Partial/Full is a *commercial* tier) |
| `source_environment` | FK self SET_NULL null blank, related_name="derived_environments" | NetSuite: refresh source is production **or another sandbox** — hence self-FK |
| `copy_scope` | CharField(16), choices = none / metadata_only / summary / full | **bullet 5's "data-subset seeding"** — none/metadata_only/summary are the subsets |
| `subset_rule` | TextField(blank) | the *declared* subset rule (Salesforce template) — a record, not an execution |
| `copy_includes_pii` | BooleanField(default=False) | the anonymization obligation flag |
| `masking_required` | BooleanField(default=False) | declared obligation + acknowledgement |
| `status` | CharField(20), choices = requested / provisioning / active / refreshing / ready_to_activate / suspended / expired / reaped | NetSuite's activation step and reaping |
| `refreshed_at` | DateTimeField(null=True, blank=True) | **bullet 2's "sandbox refresh"** |
| `refresh_source` | FK self SET_NULL null blank, related_name="refreshed_from" | the env it was refreshed from |
| `refresh_interval_days` | PositiveSmallIntegerField(null=True, blank=True) | Salesforce per-type cadence |
| `expires_at` | DateTimeField(null=True, blank=True) | **reaping date** — an un-reaped sandbox is cost + leak |
| `storage_limit_mb` | PositiveIntegerField(null=True) | declared capacity, not enforced |
| `is_active` | BooleanField(default=True) | |
| `notes` | TextField(blank) | |
| `created_at` / `updated_at` | DateTimeField | |

**Clean rules:** `source_environment != self`; `expires_at` ≥ `created_at`; `copy_scope != "none"`
required when `copy_includes_pii` (copying production PII is the reason the flag exists).
**Deliberately does NOT store:** a provisioned database/schema; a seeded row count; a masking engine;
a metered cost (0.19 owns that).

**FK summary — all verified to exist:** `core.Tenant`, `core.RetentionPolicy`, `core.DisposalRecord`,
`core.Party`, `tenants.EncryptionKey`, `accounts.User` (AUTH_USER_MODEL). All are re-exported by their
package `__init__.py`, so string references resolve. **`core` is FLAT** — these files are
`apps/core/models/Backup.py` and `apps/core/models/Compliance.py`, added to
`apps/core/models/__init__.py`, with **no** `<SubModule>/` nesting.

---

## The honest limit

NavERP at BASE **cannot truthfully claim** any of the following, and every 0.16 page must say so in 0.8's
voice — a `<p class="text-warn">` notice, not a hidden caveat:

1. **There is no scheduler.** `Retention.py:5` says it outright: "The repo has no scheduler." A backup
   whose `frequency="daily"` is a **recorded intention**, exactly like 0.13's `SyncSchedule`
   ("Nothing runs it"). No backup happens because a row says daily.
2. **There is no object storage and no storage client.** `target_location` is free text; NavERP cannot
   write a byte to it, verify a checksum, or enforce WORM. `is_immutable` is a **claim about someone
   else's system**.
3. **This app cannot dump or restore its own database.** `config/settings.py:103` is MySQL via
   `django.db.backends.mysql`; there is no `mysqldump`, `xtrabackup`, binlog reader or restore runner
   anywhere in the repo. So `RestoreRecord` is **not** evidence a restore occurred — it is evidence that
   **a person reported one**, which is exactly what `DisposalRecord` is for disposal
   (`Retention.py:63`: "The EVIDENCE that a disposal happened. Written by hand, because the act is out of
   band.").
4. **Therefore `PITR` cannot be bit-exact.** The recoverable *window* is computed from recorded backups;
   a `target_time` is "within the window we recorded," never "the database as it was at 14:03:07."
5. **`RetentionPolicy.action="archive"` and `DisposalRecord.method="archived"` (0.8) do not create an
   archive.** `DataArchive` is where the operator records that they did. Until a row exists,
   **"archived" in 0.8 means "should have been archived," not "is archived."** The 0.16 board must link
   to 0.8's board and say this.

**The posture every 0.16 page must take (modelled on `core:retention_board` and `Retention.py`):**
- **A success message is a claim about a record, not about reality.** "Backup recorded", never "Backup
  complete". "Restore recorded", never "Restore successful".
- **Never render a `0` or a blank that means "cannot tell" as if it meant "fine."**
  `retention_board`'s line is the standard: *"Reporting 0 here would be a false all-clear."*
  `integrity_verified_at = null` must render as **"Not verified"**, not as a green tick; `size_bytes =
  null` as **"—"**, not `0 B`.
- **Name the zero-that-means-blind on the board itself**, e.g. "3 backups recorded · **0 verified** — a
  backup that has never been test-restored is an untested claim."
- **No page request may perform the act.** `Retention.py:5–8` refuses a destructive GET: "the only way to
  automate it is to make a page request destructive — a GET … that silently erases rows is a far worse
  failure." A page request must never dump, restore, provision or delete either.
- **State what is out of band, by name.** As `Retention.py` says "The act itself is out of band, and the
  page says so" — 0.16 pages say: the dump, the restore, the replication, the archive transfer and the
  environment provisioning are all performed by an operator outside this application, and this register
  is the evidence trail.

---

## Traps for a naive build

1. **A backup register with only `success`/`failed`.** Real products carry **`warning`/partial** and a
   typed **failure reason** (Veeam's Success/Warning/Failed; error text per failed session). A partial
   backup is the dangerous one because people trust it.
2. **Storing key material on the backup row.** `tenants.EncryptionKey` stores **only `prefix` +
   `key_hash`, never plaintext** (`EncryptionKey.py:6`). Copying a "key" or a "secret" column onto a
   backup/archive row both breaks the rule and is itself a leak. **FK only.**
3. **Re-declaring retention/disposal.** `RetentionPolicy` + `DisposalRecord` are 0.8's and are already
   surfaced. Reading bullet 4 as "build a purging engine" is the L36 violation the reconcile file exists
   to prevent. 0.16 adds holds + the archive catalogue **only**.
4. **`LegalHold` as a boolean/date field on `RetentionPolicy`.** Proven wrong: a hold has **no window**
   (its end is an event) and acts **negatively** on a policy that may not exist yet. It must be its own
   table evaluated as a live override. (S3 Object Lock's docs are explicit that retention and legal hold
   are **independent** and either alone protects.)
5. **Conflating RPO/RTO target with actual.** Targets are policy (editable, aspirational); actuals are a
   drill measurement (immutable, historical). Storing the actual in the target column lets a missed
   objective silently become a met one. AWS/ASR/ISO 22301 all keep them apart.
6. **A `0` (or an empty string) standing in for "not reported".** `size_bytes`, `record_count`,
   `integrity_verified_at` are all **nullable on purpose**. Coercing NULL → 0 is precisely the false
   all-clear 0.8's board refuses (`Privacy.py:390`).
7. **Building two sandboxes.** Bullet 2 says "sandbox refresh" and bullet 5 says "data-subset seeding."
   That is **one** `EnvironmentInstance` with a refresh affordance and a `copy_scope`/`subset_rule` —
   the reconcile file's dedup. Two models is the double-build.
8. **`unique_together` containing `tenant`, with a `ModelForm`.** `Model._get_unique_checks()` drops any
   `unique_together` containing a field excluded from the form, so the form validates and MySQL raises an
   `IntegrityError` **500** (SKILL.md gotcha; see `Localization.py:251` for the guard shape). If a
   uniqueness rule is added (e.g. one active hold per matter+scope), guard it in `clean()`.
9. **`AuditLog.action` is `varchar(10)`** and `.create()` never validates choices — a longer verb
   **truncates silently** (or raises `DataError` under `STRICT_TRANS_TABLES`). Put the verb in `changes`
   (`AuditLog.py:16`).
10. **Assuming a restore is instant.** Archive retrieval from a cold/glacier/tape tier is an **async job**
    (S3 Glacier, Cohesity, Rubrik). A page that implies "click → restored" is wrong; model
    `retrieval_is_async` and record a retrieve→ready lifecycle.
11. **Trying to enforce WORM.** Immutability can only be enforced by the storage (`S3 Object Lock`,
    GCP enforced retention). 0.16 may record `is_immutable`/`retain_until` as a **claim**; a UI that says
    "locked" when nothing is locked is the same dishonesty as a fake delete.
12. **Absorbing 0.17's dashboard.** Drill *actuals* belong here; a continuously-measured replication-lag
    or backup-success dashboard belongs to 0.17. Recording a measured RPO at drill time is not
    observability.
13. **A GET (or a bookmark-replayed POST) that performs the act.** `Retention.py:7` names this exact
    failure. `@require_POST` above the role gate (SKILL.md: decorators apply bottom-up; outermost runs
    first) for any recording action, and **no** route that dumps, restores or deletes.
14. **Forgetting the tenant-less superuser.** Every tenant-scoped 0.16 view needs the
    `request.tenant is None` branch (`messages.info` + redirect) — the boards and singletons do; the
    `crud_list` registers deliberately do not (an empty register is the correct rendering).
15. **Porting a product's plan/vault/SLA-Domain hierarchy.** AWS's plan→vault→recovery-point and Rubrik's
    SLA domain are three objects because they manage *real infrastructure*. With no scheduler and no
    storage, those collapse into **fields on one row**. Re-creating the hierarchy is over-engineering.
16. **Claiming a sandbox was provisioned.** `EnvironmentInstance.status="active"` records that a person
    says it is up. Nothing in NavERP created a schema or seeded a row — and a record of a sandbox that
    does not exist is the inverted version of the fake-delete lie `Retention.py:10` refuses.
