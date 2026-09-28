# Contract — sub-module 0.21b: Audit & Certification Support (bullet 4)

> **Base:** `8f1e89d2` · **Frozen before the first line of code**, per the module sequence.
> **Parent:** `research-core-0.21.md` §5.2, which deferred this bullet to its own contract.
> **This contract covers ONE of the two deferred bullets.** Bullet 5 (Data Residency &
> Sovereignty) stays deferred and stays *recorded* — see "Not in this contract" below.

## 0. Scope, and the decision behind it

`NavERP.md` line 278 — **Bullet 4: Audit & Certification Support** — *Evidence collection, auditor
access, and control attestation.*

`research-core-0.21.md:294-297` deferred this bullet in full and said why: *"This is the largest single
chunk and it is the one most entangled with `core.Document` and the (absent) auditor access model, so it
deserves its own contract."* **This is that contract.** Bullet 5 is deliberately NOT bundled in,
because the same reasoning that deferred bullet 4 argues against merging it with bullet 5.

The scope question was put to the user and the prompt timed out, so the main session decided and is
recording the decision openly rather than silently: **bullet 4 alone, one contract, one migration.**

## 1. Models — three, all in the existing flat `apps/core/models/Compliance.py`

Backend rule 9: `core` is a foundation app, so these are appended to the file that already holds the
six 0.21 models. No `<SubModule>/` folder, no `*_advanced.py`, no new file.

| Model | Prefix | Purpose |
|---|---|---|
| `ComplianceAudit` | `CAUD-` | One audit/certification engagement against a framework |
| `AuditEvidence` | `EVD-` | One piece of evidence attached to a control, inside an audit |
| `AuditFinding` | `FND-` | One thing the audit found that is not yet fixed |

**All three prefixes were verified free across every `NUMBER_PREFIX` in the repo** before this
contract was written — the same check that caught `RSK` colliding with `projects.ProjectRisk` in the
first 0.21 pass.


### 1.1 `ComplianceAudit`

| Field | Type | Notes |
|---|---|---|
| `tenant` | FK `core.Tenant` | `related_name="compliance_audits"`, `db_index=True` |
| `number` | `CharField(20, editable=False)` | `CAUD-#####`, literal mint |
| `code` | `CharField(40)` | human key within the tenant |
| `title` | `CharField(200)` | |
| `framework` | FK `core.ControlFramework` | `SET_NULL`, `related_name="audits"` — an audit outlives the framework it was run against |
| `audit_type` | `CharField(20, choices=AUDIT_TYPE_CHOICES)` | `certification` / `internal` / `customer` / `regulatory` |
| `status` | `CharField(20, choices=AUDIT_STATUS_CHOICES, default="planned")` | `planned → fieldwork → findings_issued → closed` |
| `auditor_name` | `CharField(120, blank=True)` | the firm, free text — an external auditor is not a `core.User` |
| `auditor_email` | `EmailField(blank=True)` | **a recorded contact, not an account.** No `User` FK, because granting access is declined (§3) |
| `started_on` / `target_date` | `DateField(null=True, blank=True)` | |
| `closed_on` | `DateField(null=True, blank=True)` | |
| `summary` | `TextField(blank=True)` | |
| `notes` | `TextField(blank=True)` | |

`clean()` guards:
- `target_date` before `started_on` → `ValidationError` on `target_date`.
- `status="closed"` requires `closed_on`; a closed audit with no close date is a fiction.
- `closed_on` requires `status="closed"`; a date against an open audit is contradictory.

`AUDIT_TYPE_CHOICES` = `certification`, `internal`, `customer`, `regulatory`.
`AUDIT_STATUS_CHOICES` = `planned`, `fieldwork`, `findings_issued`, `closed`.

`Meta.ordering = ["-started_on", "code"]`; `unique_together = ("tenant", "code")`;
indexes `("tenant", "status")` → `cad_tenant_status_idx`, `("tenant", "-started_on")` → `cad_tenant_start_idx`.
All names ≤ 30 chars (MariaDB).

### 1.2 `AuditEvidence` — the L36 boundary, stated

| Field | Type | Notes |
|---|---|---|
| `tenant` | FK `core.Tenant` | `related_name="audit_evidence"`, `db_index=True` |
| `number` | `CharField(20, editable=False)` | `EVD-#####` |
| `code` | `CharField(40)` | |
| `title` | `CharField(200)` | |
| `audit` | FK `core.ComplianceAudit` | `CASCADE`, `related_name="evidence"` |
| `control` | FK `core.ComplianceControl` | `SET_NULL`, `related_name="+"` — evidence outlives the control it was gathered for |
| `document` | FK `core.Document` | `SET_NULL`, `null=True`, `blank=True`, `related_name="+"` — **the pointer, not a copy** |
| `evidence_type` | `CharField(20, choices=EVIDENCE_TYPE_CHOICES)` | `document` / `screenshot` / `log_export` / `attestation` / `observation` |
| `collected_on` | `DateField(null=True, blank=True)` | |
| `period_covered` | `CharField(40, blank=True)` | e.g. "2026-Q1" — free text, a per-programme vocabulary |
| `description` | `TextField(blank=True)` | |
| `notes` | `TextField(blank=True)` | |

**L36, stated as a rule:** `document` is a **`core.Document` pointer**. 0.1's `Document` owns file
upload and storage (`upload_to="documents/%Y/%m/"`). This table adds **no** `FileField`, re-declares
**no** upload path, and never copies bytes. It is `SET_NULL` because evidence that referenced a
deleted document is still a truthful record that evidence was collected — a hard FK would delete the
evidence row and silently shrink an audit.

`clean()` guard: `evidence_type="document"` requires a `document`. Claiming a document you did not
attach is the exact shape of a fabricated evidence trail.

`EVIDENCE_TYPE_CHOICES` = `document`, `screenshot`, `log_export`, `attestation`, `observation`.

`Meta.ordering = ["-collected_on", "code"]`; `unique_together = ("tenant", "code")`;
indexes `("tenant", "audit")` → `evd_tenant_audit_idx`, `("tenant", "evidence_type")` → `evd_tenant_type_idx`.



## 2. Forms — `apps/core/forms/Compliance.py`, appended

- `ComplianceAuditForm` — excludes `number`.
- `AuditEvidenceForm` — excludes `number`. `audit` and `document` are tenant-scoped FKs via
  `TenantModelForm`; `control` is `SET_NULL` so it is a plain `ModelChoiceField`.
- `AuditFindingForm` — excludes `number`.

## 3. Explicitly DECLINED, with reasons (so they are not re-litigated)

- **Auditor access granting.** There is no `accounts.User` for an external auditor and no invitation
  flow that would make one; `auditor_email` is a **recorded contact** and nothing sends mail to it.
  The bullet says "auditor access" and this module grants **none** — stated on every page.
- **Evidence file upload.** 0.1's `Document` owns it. This module points at it.
- **A seeded library of real SOC 2 / ISO 27001 control and evidence texts.** Same refusal as the
  first 0.21 pass: a seeder asserting a control library is the "compliance lie" `regulatory_sync`
  already refuses.
- **Any gate.** No code path reads these three tables to block an action. `status="closed"` is a
  sentence somebody typed, exactly like `ComplianceControl.status="effective"`.
- **Cross-module risk rollup** from `AuditFinding` to `RiskRegister`. Still declined for the reason
  recorded in the first pass.

## 4. Migration

`core.0019_*`, applied after re-reading `apps/core/migrations/` immediately before generating
(never hand-write the number). Adds three tables, their `AlterUniqueTogether` and their index
operations. **No changes to any existing table** — nothing here re-declares a `core.Document` or a
`core.ControlFramework` column.

## 5. Tests — `apps/core/tests/test_compliance_*.py`, `cml021b_` prefixed

Every test and helper is `cml021b_`-prefixed so this pass cannot shadow the first pass's `cml021_`
names in the same `conftest.py`. **The L57 lesson applies to any fixture that creates one of these
rows**: if a `clean()` writes a field, the fixture must call `clean()`.

## Not in this contract

**Bullet 5 — Data Residency & Sovereignty** (`DataResidency` / `DRP-` and its environment binding)
remains deferred. It is **recorded, not lost**, in `research-core-0.21.md` §5.2 and in
`.claude/tasks/todo.md`. Note for whoever picks it up: 0.8's `RegulatoryFramework` already carries
`data_residency_region` (free text, max 80, "recorded, NOT enforced") — that is a **legal
requirement per regime**, whereas a `DataResidency` model would be a **workspace placement
register**. Those are different facts, but the overlap is real and must be reconciled explicitly
before the model is written, or the workspace will have two answers to "where does our data live?"
exactly as 0.8's framework and 0.21's `ControlFramework` nearly did.

### 1.3 `AuditFinding`

| Field | Type | Notes |
|---|---|---|
| `tenant` | FK `core.Tenant` | `related_name="audit_findings"`, `db_index=True` |
| `number` | `CharField(20, editable=False)` | `FND-#####` |
| `code` | `CharField(40)` | |
| `title` | `CharField(200)` | |
| `audit` | FK `core.ComplianceAudit` | `CASCADE`, `related_name="findings"` |
| `control` | FK `core.ComplianceControl` | `SET_NULL`, `related_name="+"` |
| `severity` | `CharField(16, choices=SEVERITY_CHOICES)` | `critical` / `major` / `minor` / `observation` |
| `status` | `CharField(20, choices=FINDING_STATUS_CHOICES, default="open")` | `open` / `remediation` / `resolved` / `risk_accepted` / `closed` |
| `description` | `TextField()` | what is wrong |
| `remediation` | `TextField(blank=True)` | what should happen |
| `due_on` | `DateField(null=True, blank=True)` | |
| `resolved_on` | `DateField(null=True, blank=True)` | |
| `owner` | FK `AUTH_USER_MODEL` | `SET_NULL`, `null=True`, `related_name="+"` — the actor-FK convention |
| `notes` | `TextField(blank=True)` | |

`clean()` guards:
- `status="resolved"` requires `resolved_on` (and vice versa) — the same pair-of-truths rule as the audit.
- `severity="critical"` with `status="risk_accepted"` is refused: a critical finding cannot be waved
  through. This is a **recorded rule, not an enforcement** — nothing blocks the POST, `clean()` refuses.

`SEVERITY_CHOICES` = `critical`, `major`, `minor`, `observation`.
`FINDING_STATUS_CHOICES` = `open`, `remediation`, `resolved`, `risk_accepted`, `closed`.

`Meta.ordering = ["severity", "code"]`; `unique_together = ("tenant", "code")`;
indexes `("tenant", "status")` → `fnd_tenant_status_idx`, `("tenant", "severity")` → `fnd_tenant_sev_idx`.
