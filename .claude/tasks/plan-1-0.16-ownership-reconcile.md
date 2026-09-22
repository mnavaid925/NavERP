# 0.16 Backup, Recovery & Data Lifecycle — ownership reconcile (Phase 0)

**Run:** `/next-module 0.16` · **BASE:** `6a834d9e3378efde6a62b0924aa69073948e1d4b` · **Date:** 2026-09-22
**Verdict up front:** 0.16 is **mostly unbuilt and mostly unowned** — but **bullet 4 collides with 0.8**,
and the collision is severe enough that 0.16 must *narrow* rather than *re-declare*.

The plan flagged this before I started:

> **0.16** Backup schedules, restore, lifecycle/archival. `core.DisposalRecord` already exists as evidence
> of a real disposal — read it before declaring anything about retention.

I read it. It is worse than "already exists": **0.8 already ships a full retention + disposal register, a
computed compliance board, and a `LIVE_LINKS` bullet claiming it.**

---

## The collision (L36) — proven, not assumed

`apps/core/models/Retention.py` (built by **0.8 Privacy & Data Protection**) owns:

| class | what it does |
|---|---|
| `RetentionPolicy` | per-tenant, per-data-category: `retention_months`, `action` ∈ {review, delete, anonymize, **archive**}, `basis`, optional `model_label` |
| `DisposalRecord` | the *evidence* a disposal happened: `method` ∈ {deleted, anonymized, **archived**, destroyed_media}, `record_count`, `performed_by`, `evidence` |

And `apps/core/views/Privacy.py:385` `retention_board` is a **computed** board that walks each active
policy's pinned `model_label`, counts rows past the window, and explicitly refuses to print a `0` it
cannot justify:

> *"Reporting 0 here would be a false all-clear."*

`LIVE_LINKS["0.8"]` already claims the bullet **"Retention & Disposal Policies" → `core:retention_board`**,
plus extra leaves `core:retention_policy_list` and `core:disposal_list`.

**0.16's bullet 4 is "Data Archival & Purging — cold-storage archival, legal holds, and policy-based
purging."** That is `RetentionPolicy.action="archive"` + `RetentionPolicy.action="delete"` +
`DisposalRecord`, already built and already surfaced.

### The decision

**0.16 does NOT re-declare retention or disposal.** It adds exactly the two things a retention *schedule*
structurally cannot express, and points at 0.8 for the rest:

1. **A legal hold** — because a hold is **not a schedule**. It is an *event with a release* that
   **overrides** every window, and `RetentionPolicy` has no way to say "this window does not apply right
   now." This is the genuine gap.
2. **An archive catalogue** — `RetentionPolicy.action="archive"` says *that* something should be
   archived; nothing records *where the archive went*, so a restore is impossible. This closes the loop
   that 0.8's own docstring left open.

Both are recorded in the contract as **explicit no-re-declaration entries**, the way 7.6 handled
`DeliverableInspection`.

### The honest caveat 0.16 must inherit, not rediscover

`Retention.py`'s module docstring already establishes the house truth that must shape 0.16's design:

> *"The project already established (7.10) that **'delete' in this codebase does not erase bytes** —
> Django never unlinks a `FileField` on row delete. A 'destruction' feature that reports success while
> the file survives on disk would be actively dishonest."*

**This is fatal to the naive reading of 0.16.** A backup register that claims a backup *exists* when the
app never wrote the file is the same lie in the other direction. So 0.16's backups are, like 0.8's
disposals, **registers of evidence written by hand** — and every page says so, in 0.8's voice.

---

## Bullet-by-bullet classification

| # | NavERP.md bullet | status before 0.16 | owner |
|---|---|---|---|
| 1 | **Automated Backups** — scheduled full/incremental w/ encryption + integrity | **absent** | → **0.16** |
| 2 | **Point-in-Time Recovery** — restore to timestamps, per-tenant restore, sandbox refresh | **absent** | → **0.16** |
| 3 | **Disaster Recovery & Failover** — multi-region replication, RPO/RTO, failover drills | **absent** | → **0.16** |
| 4 | **Data Archival & Purging** — cold-storage archival, legal holds, policy-based purging | ⚠️ **MOSTLY BUILT (0.8)** | **narrow** → 0.16 adds holds + archive catalogue only |
| 5 | **Sandbox & Environment Management** — dev/test/staging provisioning, data-subset seeding | **absent** | → **0.16** |

### Bullet 2's "sandbox refresh" vs bullet 5 — an intra-bullet boundary, stated to avoid a double build

Bullet 2 lists **"sandbox refresh"** and bullet 5 lists **"data-subset seeding."** Both are "make a
sandbox." **0.16 will build this exactly once:** an `EnvironmentInstance` (bullet 5) with a
`refresh_from_production` affordance that records the *subset rule* used (bullet 2). One model, two
bullets, and the contract says which bullet maps to which page so no later reviewer calls it a
duplicate.

---

## What already exists that 0.16 must point at, not rebuild (verified by grep)

| existing | app | how 0.16 uses it |
|---|---|---|
| `core.AuditLog` (append-only, `tenant` SET_NULL, `at`) | core | the *audit* log 0.16's ops actions write into via `log_action` |
| `core.BusinessRuleLog` | core | the *rule-evaluation* log — **0.17's** raw material, not 0.16's |
| `core.RetentionPolicy` / `core.DisposalRecord` | core (0.8) | pointed at, never re-declared |
| `tenants.HealthMetric` | tenants (0.1) | the *health* series — **0.17's**, not 0.16's |
| `tenants.UsageRecord` (+ `PLAN_ALLOWANCES`) | tenants (0.1) | metered consumption vs plan — **0.17 capacity**, and **0.19** |
| `tenants.EncryptionKey` | tenants (0.1) | 0.16 **FKs it** to key a backup; never re-declares key material |
| `tenants.Subscription` / `SubscriptionInvoice` | tenants (0.1) | **0.19** re-declares neither |
| `core.SettingDefinition` | core (0.10) | house pattern for a global-vs-tenant registry |

### Deferred to their own sub-modules (stated so 0.16 is not blamed for the gap)
- **Uptime / error / APM / capacity dashboards / status page → 0.17.** 0.16's `RecoveryDrill` records
  **RPO/RTO measured in a drill**; it is *not* an observability dashboard.
- **WAF / rate limiting / IP allow-lists → 0.18.** `core.RateLimitPolicy` (0.13) already exists there.
- **Entitlements / seats / renewals → 0.19.**

---

## Migration number — claimed, not just agreed (L43)

A concurrent session is mid-build on **Module 7.18** and its working tree is dirty right now
(4 modified `templates/projects/reporting/*.html`) — it has not touched `main` yet, and it was
committing to `main` until `6a834d9e`.

Migration leaves at BASE — `core` → `0012_…`, `tenants` → `0004_usagerecord`.
**0.16 targets `core/0013_…`** and writes the empty migration file **immediately, at claim time**, so the
number is not merely agreed but *taken*. If 7.18 lands a `0013_` first, resolve with `makemigrations
--merge`; do not renumber by hand.

---

## Scope for this run (frozen)

**App:** `core` (flat foundation layout — no sub-module folder, per CLAUDE.md Backend Package rule 9).
**Models: 4.** `BackupJob`, `RestoreRecord`, `DataArchive`, `EnvironmentInstance` — plus `LegalHold`
carried as a child of the archive design if the contract can hold it at 4; otherwise 5 and the research
phase says so explicitly.

**Not in this run:** any real dump/restore execution, any scheduler, any object-storage client.
Register-of-evidence only — the 0.8 posture, applied to infrastructure instead of privacy.
