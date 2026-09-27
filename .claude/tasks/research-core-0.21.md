# Research — sub-module 0.21 Compliance, Governance & Risk (`core`)

**Phase 1 of the module creation sequence.** Written 2026-09-28, before any 0.21 code.
`BASE` at the time of writing: `5ab1c305`. Migration leaf: `core.0016_security_threat_protection`.

Source of truth for scope: `NavERP.md` lines 273–278, verbatim:

1. **Compliance Frameworks** — SOC 2, ISO 27001, GDPR, HIPAA, and PCI-DSS control mapping.
2. **Policy Management** — Security policy authoring, acknowledgment tracking, and enforcement.
3. **Risk Register & Assessment** — Risk identification, scoring, treatment plans, and monitoring.
4. **Audit & Certification Support** — Evidence collection, auditor access, and control attestation.
5. **Data Residency & Sovereignty** — Region-pinned storage and jurisdiction-specific controls.

---

## 0. How this document was produced, and what was verified

This pass was **run inline in the main session, not by the `research` subagent**: the subagent
failed with `429 Daily free limit reached` and could not be retried inside the session. The
structural requirements of the phase are unchanged (catalog → reconciliation → recommended scope →
prefixes → field sketch), but the constraint shaped the depth of the *search*, not the rigour of
the *reconciliation* — the reconciliation below was done by direct `manage.py shell` introspection
and by reading the source, which is stronger evidence than a web search anyway.

**Verified by execution** (`venv\Scripts\python.exe manage.py shell`, temp script, since deleted):

- The full list of 74 live `core` models and their `db_table`s.
- Every `NUMBER_PREFIX` declared repo-wide, with the models that declare each.
- The collision status of all eight candidate prefixes.

**Verified by reading**: `apps/core/models/Privacy.py`, `Security.py`, `Monitoring.py`,
`AuditLog.py`, `Retention.py`, `LegalHold.py`, `settings_engine.py`, `seed_core.py`, `crud.py`,
`utils.py`, `forms/_common.py`, `views/_common.py`, `urls.py`, and `contract-core-0.20.md`.

**Verified by web research**: Drata's Control Framework (DCF) model, ServiceNow IRM's risk
register, Vanta's framework control sets, OneTrust's compliance automation, Archer's Risk Catalog
and Risk Management solution.

> **Deviation to note for the reviewer**: the project's rules say research belongs to the

### 1.2 Policy management (bullet 2)

| # | Feature | Source | Pri |
|---|---|---|---|
| 1.2.1 | A **policy** record: title, code, category, body/summary, version, owner, status | OneTrust Policy Management; Drata Policy Center | **P1** |
| 1.2.2 | **Versioning with effective dates** — a policy has a version and an effective date, and acknowledgement is per-version | Drata Policy Center ("Policy Owners", personnel compliance) | **P1** |
| 1.2.3 | **Acknowledgement tracking** as rows: who acknowledged, when, which version | Drata "Managing Personnel Compliance" | **P1** |
| 1.2.4 | **Review cadence / next review date** | OneTrust | **P1** |
| 1.2.5 | Policy ↔ **control linkage** (a policy is how a control is *communicated*) | Drata DCF connects policies to controls | **P2** |
| 1.2.6 | **Automated reminders / escalation** for non-acknowledgers | OneTrust | **X** — no mail dispatcher exists (0.12 owns delivery; there is still no dispatcher) |
| 1.2.7 | Actual **enforcement** (block the action) | — | **X** — see §2, this is a claim NavERP cannot honestly make |

### 1.3 Risk register (bullet 3)

| # | Feature | Source | Pri |
|---|---|---|---|
| 1.3.1 | A **risk** record: statement, description, category, owner, status | Archer Risk Catalog ("risk description, impact, likelihood, owner, status, and links to controls, business units, and loss events") | **P1** |
| 1.3.2 | **Likelihood × impact** on explicit scales, with a **derived score** | Archer; ServiceNow IRM risk scoring | **P1** |
| 1.3.3 | **Inherent vs residual** risk | Archer ("Inherent and residual risk can be assessed … rolling up to intermediate and enterprise risk statements") | **P1** |
| 1.3.4 | **Treatment / response type**: accept, mitigate, transfer, avoid | ServiceNow IRM risk responses; Archer treatment plans | **P1** |
| 1.3.5 | **Risk treatment plan** — the narrative of what will be done, with an owner and a date | Archer; OneTrust | **P1** |
| 1.3.6 | **Risk → control linkage** (which controls mitigate a risk) | Archer ("Controls … linkage to risks") | **P1** |
| 1.3.7 | **Review cadence / next review**, and a **last assessed** stamp | Archer ("Last Assessed Date field is updated to the RCSA approved date") | **P1** |
| 1.3.8 | **Risk snapshots** over time for trending | Archer Risk Snapshot | **P2** — a history table; a defensible later pass |
| 1.3.9 | **Key risk indicators / metrics** and threshold breaches | Archer Metrics + Metrics Results | **P2** — belongs with 0.17's alerting vocabulary, and would duplicate `AlertRule` |
| 1.3.10 | **RCSA campaigns** (self-assessment campaigns over a scope) | Archer RCSA | **P2** — heavy workflow; a later pass |
| 1.3.11 | Three-level risk rollup (granular → intermediate → enterprise statement) | Archer | **X** for this pass — a hierarchy needs a self-FK and a rollup engine; deferred, noted not lost |

### 1.4 Audit & certification support (bullet 4)

| # | Feature | Source | Pri |
|---|---|---|---|
| 1.4.1 | An **audit/engagement** record: framework, type, period, status, auditor, dates | Drata "Navigating an Audit"; ServiceNow Audit Management engagements | **P1** |
| 1.4.2 | **External auditor access** as a first-class, scoped, time-boxed thing | Drata "Navigate to Drata as an auditor"; ServiceNow "add auditors … for an engagement" | **P1** (as a *recorded* access grant — see §2) |
| 1.4.3 | An **evidence** artifact: title, kind, reference/link, collected-on, owner, review period | Drata "Managing Evidence"; OneTrust evidence tasks/collectors | **P1** |
| 1.4.4 | **Evidence → control** linkage | Drata DCF connects evidence to controls | **P1** |
| 1.4.5 | A **finding/issue** raised by an audit: severity, description, owner, status, due date, remediation | ServiceNow "Manage audit issues and remediation"; Drata GRC issues | **P1** |
| 1.4.6 | **Control attestation** — a named person attests a control is operating, with a period and an outcome | Drata "Control Owners"; OneTrust attestation | **P1** |
| 1.4.7 | Evidence **collection automation / connectors** | OneTrust "pre-architected end-to-end collectors" | **X** — no collector runtime exists; NavERP has no evidence-picking daemon (the 0.20 `JobDefinition` is a *register*, and nothing runs it) |

---

## 2. What this application cannot do — the register-honest posture

This is the constraint that shapes the whole build, and it is inherited verbatim from 0.16/0.17/0.18/0.20.
**NavERP is a single-region Django application with one database, no mail dispatcher, no
background worker, and no evidence collector.** So:

- **A control is a record of a control. Nothing enforces it.** `implemented` is a statement a
  person made, not a gate. This is exactly `core.BusinessRule`'s documented stance and 0.20's
  "register of intent, not a runtime".
- **An audit is a record of an engagement. No auditor gains any access.** The auditor row is a
  *recorded access grant* — who was granted review of what, until when. There is no
  read-only external role, no expiring session, and no second login path. Writing a page that says
  "auditor access granted" without that sentence would be the exact lie 0.20's pages refuse.
- **A data-residency row is a declared jurisdiction. Nothing is pinned.** There is one database
  and it is where it is. The page must say so, and it must not claim enforcement.
- **An acknowledgement is a row somebody wrote. Nobody is reminded.** 0.12 owns notification
| `CorporatePolicy` | `core.RetentionPolicy` (0.8, `apps/core/models/Retention.py`) — a *retention* policy, keyed on `data_category`/`model_label`/`retention_months`. Also `core.RateLimitPolicy` (0.13), `hrm.HrPolicy` (3.x) | **Distinct concept, safe to declare — but it must NOT be called `RetentionPolicy`.** A security/corporate policy (acceptable use, access control, code of conduct) is a different object from a data-retention schedule. Name it `CorporatePolicy` to keep the distinction visible, and note `hrm.HrPolicy` explicitly so HRM's policy table is not mistaken for this one. |
| `ComplianceAudit` | `core.AuditLog` (0.1) — the append-only who/what/when record. `scm.QualityAudit` (4.9), `procurement.AuditSeal` | **Distinct and safe.** `AuditLog` is a system-written change trail; `ComplianceAudit` is a human-scheduled audit engagement with a period, a framework and an auditor. Names do not collide; the docstring must say the difference so nobody reports one as the other. |
| `AuditEvidence` | `core.Document` (0.1) owns file upload and storage | **Reference `Document`, do not re-declare a file table.** 0.21's evidence row is a *pointer plus audit metadata* (kind, collected-on, review period, control linkage). |
| `AuditFinding` | none in core. `procurement.InvoiceDispute`, `scm.NonConformance` | **Free to declare.** |
| `RiskRegister` | **`projects.ProjectRisk` (`RSK-`)** in 9.x; `procurement.SupplierRiskAssessment` (`SRA-`); `scm.ComplianceRequirement` (`CR-`); `hrm.ComplianceRegister` (`CMP-`) | **Free to declare, but the PREFIX is taken** — see §4. |
| `ComplianceControl` | `scm.ComplianceRequirement` (4.13), `hrm.ComplianceRegister` (3.x), `procurement.ComplianceScreening` (6.x), `accounting.InternalControl` (2.x) | **Free to declare in `core`.** The nearest neighbour, `scm.ComplianceRequirement`, is a *supplier/contract* requirement — its docstring scope is trade compliance, not internal control attestation. The new model's docstring must name that boundary. |

**Ruling on the framework name (the one genuinely hard call).** Two options:

- (a) Declare `ComplianceFramework` and leave `RegulatoryFramework` alone → the workspace has two
  framework tables that both list "GDPR" and "HIPAA". **Rejected**: the L36 rule exists precisely to
  stop one fact having two homes, and a GDPR row in each would be an unanswerable "which one is
  true?" at audit time.
- (b) **`RegulatoryFramework` stays the record of *which regimes apply*; 0.21 adds a distinct
  `ControlFramework` for *certification programmes* (SOC 2, ISO 27001, PCI-DSS)**, and each
  `ComplianceControl` maps to one or more of *either* via a single mapping table. **Chosen (b).**

---

## 4. Number prefixes — verified, including a collision the earlier plan missed

Verified by enumerating `NUMBER_PREFIX` across every installed app
(`manage.py shell` + `django.apps.apps.get_models()`):

| Candidate | Status | Note |
|---|---|---|
| `CFW` | **free** | for `ControlFramework` |
| `CTL` | **free** | for `ComplianceControl` |
| `CPOL` | **free** | for `CorporatePolicy` |
| `RSK` | **COLLIDES** | already `projects.ProjectRisk` in 9.x |
| `CAUD` | **free** | for `ComplianceAudit` |
| `FND` | **free** | for `AuditFinding` |
| `EVD` | **free** | for `AuditEvidence` |
| `DRP` | **free** | for `DataResidency` |

> **This is a correction to the plan this session inherited**, which listed all eight prefixes as
> collision-free. `RSK` is taken by `projects.ProjectRisk`. `next_number()` scopes by
> `(tenant, prefix)` but the *board* and the *reader* do not: a `RSK-00001` risk and a `RSK-00001`
> project risk in the same tenant would be indistinguishable to an operator, which is precisely
> the failure `prefix_usage()` exists to prevent. **`RiskRegister` is re-prefixed `GRC-`**
> ("governance, risk and compliance" — the name the whole industry uses for this module), which is
> verified free.

Also verified: `core` has **no `TenantNumbered` base**, so these mint exactly like 0.20's models —
a hardcoded literal in `save()` via `apps.core.utils.next_number`, registered in
`core.settings_engine.LITERAL_PREFIX_MODELS` so `prefix_usage()` can see them.

---

## 5. Recommended build scope for this pass — 4 models, 6 classes

The inherited plan proposed 8 models. **Four is the right number for one pass** given: (a) 0.20 is
still landing in this same checkout and the shared files are single-writer; (b) the seed library
for frameworks is substantial; (c) the 5 bullet-to-model mapping is cleaner if the two deepest

---

## 6. Field sketch (recommended scope only)

`core` conventions that apply to every model below: `class X(models.Model)`;
`tenant = FK("core.Tenant", on_delete=CASCADE, related_name="…", db_index=True)`;
literal-minted `number` (`editable=False`, `max_length=20`); `Meta.ordering`; every index name
**under 30 characters** (MariaDB limit); actor FKs are `SET_NULL`, `related_name="+"`.

### 6.1 `ControlFramework` — `CFW-`

`number` · `code` (Char 30, unique per tenant) · `name` (150) · `version` (30, blank) ·
`authority` (150, blank — the issuing body, e.g. "AICPA", "ISO") · `description` (Text) ·
`is_active` (bool default True) · `adopted_on` (Date null) · `review_due_on` (Date null) ·
`notes` · `created_at`.

`FRAMEWORK_TYPE_CHOICES` = `attestation` (SOC 2, ISO 27001, PCI-DSS — certified against),
`regulatory` (a mirror of 0.8's `RegulatoryFramework`, for cross-linking), `industry`,
`internal`. The `regulatory` value exists so a workspace can point a control at the GDPR regime
**by reference** without 0.21 re-declaring GDPR's obligations.

Indexes: `(tenant, is_active)` → `cfw_tenant_active_idx`; `(tenant, code)` unique via
`unique_together`.

### 6.2 `ComplianceControl` — `CTL-`

`number` · `code` (Char 30, unique per tenant) · `title` (200) · `description` (Text blank) ·
`category` (Char 40, blank) · `status` (`CONTROL_STATUS_CHOICES`: `not_started`, `in_progress`,
`implemented`, `effective`, `not_applicable`; default `not_started`) · `owner` (FK
`settings.AUTH_USER_MODEL` SET_NULL null blank `related_name="+"`) · `frequency` (Char 20, blank —
recorded, nothing schedules it) · `evidence_reference` (Char 255, blank) · `last_reviewed_on`
(Date null) · `next_review_on` (Date null) · `notes` · `created_at`.

`clean()`: `next_review_on` before `last_reviewed_on` is refused; `status="effective"` requires a

### 6.4 `CorporatePolicy` — `CPOL-`

`number` · `code` (Char 30, unique per tenant) · `title` (200) · `summary` (Text) ·
`policy_type` (`POLICY_TYPE_CHOICES`: `security`, `acceptable_use`, `access_control`,
`data_handling`, `incident_response`, `business_continuity`, `code_of_conduct`; default `security`) ·
`version` (Char 20, default `"1.0"`) · `status` (`POLICY_STATUS_CHOICES`: `draft`, `published`,
`retired`; default `draft`) · `owner` FK user SET_NULL `related_name="+"` · `effective_on` (Date
null) · `review_due_on` (Date null) · `requires_acknowledgement` (bool default True) ·
`body` (Text blank) · `notes` · `created_at` · `updated_at`.

`clean()`: `status="published"` requires `effective_on`; `review_due_on` before `effective_on` is
refused. **Deliberately NOT named `RetentionPolicy`** — see §3.

Indexes: `(tenant, status)` → `cpol_tenant_status_idx`; `(tenant, policy_type)` → `cpol_tenant_type_idx`.

### 6.5 `PolicyAcknowledgement` — child, no prefix

`tenant` · `policy` FK `CorporatePolicy` CASCADE `related_name="acknowledgements"` · `user` FK
`settings.AUTH_USER_MODEL` CASCADE `related_name="+"` · `policy_version` (Char 20 — **snapshotted**
from the policy at acknowledgement time, because acknowledging v1 of a policy that has since been
re-versioned to v2 is a materially different act) · `acknowledged_at` (DateTime auto_now_add) ·
`notes` (blank).

`unique_together = (("policy", "user", "policy_version"),)` — re-acknowledging a *new* version is
allowed; re-acknowledging the same one is not. Index `(policy, acknowledged_at)` →
`ack_pol_time_idx`.

### 6.6 `RiskRegister` — `GRC-` (not `RSK-`, see §4)

`number` · `title` (200) · `risk_statement` (Text) · `description` (Text blank) · `category`
(Char 40, blank) · `likelihood` (`LIKELIHOOD_CHOICES`: `rare`, `unlikely`, `possible`, `likely`,
`almost_certain`; default `possible`) · `impact` (`RISK_IMPACT_CHOICES`: `negligible`, `minor`,
`moderate`, `major`, `severe`; default `minor`) · `inherent_score` (PositiveSmallInteger, derived
in `clean()` from likelihood×impact — **stored**, because it is what an auditor reads and sorting
on a computed property would be a filesort) · `residual_score` (PositiveSmallInteger null) ·
`treatment` (`TREATMENT_CHOICES`: `accept`, `mitigate`, `transfer`, `avoid`; default `mitigate`) ·
`treatment_plan` (Text blank) · `status` (`RISK_STATUS_CHOICES`: `identified`, `assessing`,
`treating`, `monitoring`, `closed`; default `identified`) · `owner` FK user SET_NULL `related_name="+"`
· `reviewed_on` (Date null) · `next_review_on` (Date null) · `notes` · `created_at`.

`clean()`: `inherent_score` is **recomputed** from the two ordinals and never trusted from a POST
(off the form, and `clean()` is the real gate); `residual_score` must be ≤ `inherent_score`;
`status="closed"` requires a `reviewed_on`; `next_review_on` before `reviewed_on` is refused.

`@property score_label` returns the band word (`low`/`medium`/`high`/`critical`) derived from the
score — derived, never stored, so it cannot drift from the number.

Indexes: `(tenant, status)` → `grc_tenant_status_idx`; `(tenant, -inherent_score)` →
`grc_tenant_score_idx`; `(tenant, category)` → `grc_tenant_cat_idx`.

### 6.7 Vocabulary note (the L29 "share by reference" rule)

`RISK_IMPACT_CHOICES` here is **not** `ChangeRequest.RISK_LEVEL_CHOICES` and **not**
`VulnerabilityFinding.SEVERITY_BAND_CHOICES`. A change's risk, a CVSS band and an enterprise risk's
impact are three different facts that happen to share some words. 0.20's `Change.py` docstring
already records this exact ruling for the same reason; the new constant follows it. The one
vocabulary that **is** reused is the likelihood/impact *shape* from Archer, which no core model has.

---

## 7. Open questions for the contract

1. **`ComplianceFramework` vs `ControlFramework`** — resolved as the §3 ruling (b), but the contract
   must state it loudly, because a future reader looking for a class called `ComplianceFramework`
   will not find one and must be told where it went.
2. **`RSK-` → `GRC-`** — a rename against an inherited plan. The contract must record it as a
   RULING with the collision evidence.
3. **Should `ControlFrameworkMapping` also reach `RegulatoryFramework`?** The `regulatory` type
   says yes eventually, but adding a second FK to the same join table is a schema change. **This
   pass defers it** and says so in the model docstring.

`last_reviewed_on`.

Indexes: `(tenant, status)` → `ctl_tenant_status_idx`; `(tenant, category)` → `ctl_tenant_cat_idx`.

### 6.3 `ControlFrameworkMapping` — child, no prefix

`tenant` · `framework` FK `ControlFramework` CASCADE `related_name="mappings"` · `control` FK
`ComplianceControl` CASCADE `related_name="mappings"` · `clause_reference` (Char 40, blank — e.g.
`CC1.1`, `A.8.15`) · `coverage` (`COVERAGE_CHOICES`: `not_started`, `partial`, `covered`,
`not_applicable`; default `not_started`) · `notes`.

`unique_together = (("framework", "control"),)`. A join table, deliberately unnumbered — it is only
ever addressed through its two parents. Index `(framework, coverage)` → `cfmap_fw_cov_idx`.

**This is the row that makes bullet 1 real**: without it, "one control maps to several
frameworks" (Drata's explicit best practice) is impossible, and the 0.21 pages would be a flat list
of controls with no framework relationship at all.

chains (framework→control→mapping) each get their parent and child in one commit than if eight land
at once.

### 5.1 In scope (this pass)

| # | Model | Prefix | Serves | File |
|---|---|---|---|---|
| 1 | `ControlFramework` | `CFW-` | bullet 1 | `apps/core/models/Compliance.py` |
| 2 | `ComplianceControl` | `CTL-` | bullet 1 | same |
| 3 | `ControlFrameworkMapping` | *no prefix* (child) | bullet 1 | same |
| 4 | `CorporatePolicy` | `CPOL-` | bullet 2 | same |
| 5 | `PolicyAcknowledgement` | *no prefix* (child) | bullet 2 | same |
| 6 | `RiskRegister` | `GRC-` | bullet 3 | same |

### 5.2 Deferred to a second 0.21 pass (recorded here so it is not lost)

- **Bullet 4 in full**: `ComplianceAudit` (`CAUD-`), `AuditEvidence` (`EVD-`), `AuditFinding`
  (`FND-`), plus the control-attestation record. This is the largest single chunk and it is the one
  most entangled with `core.Document` and the (absent) auditor access model, so it deserves its
  own contract.
- **Bullet 5**: `DataResidency` (`DRP-`) and its `EnvironmentInstance` binding.
- Everything marked P2 in §1, and everything marked X.

### 5.3 Declined outright, with reasons

- **Control *enforcement*** — a register, not a gate (§2).
- **A `NotificationDispatcher`** — 0.12 owns templates; there is still no dispatcher. Policy
  reminders are therefore declined rather than half-built.
- **A seeded content library of 200+ real control texts** — 0.21 seeds a small, honest demo set
  (a handful of framework + control rows) and says so. Shipping a fake-exhaustive SOC 2 catalog
  would be the "compliance lie" `regulatory_sync` already refuses ("a workspace claiming HIPAA
  because a seeder said so would be a compliance lie").
- **Cross-module risk rollup** (`projects.ProjectRisk` → `RiskRegister`) — a reconciliation
  between two apps' risk models is a cross-module project, not a 0.21 side effect.


The distinction is real and holds in the products: GDPR/CCPA/HIPAA are *laws* that impose duties
and a DSAR clock (0.8's job), while SOC 2 / ISO 27001 / PCI-DSS are *voluntary attestation
programmes* you get certified against, composed of controls you evidence (0.21's job). Drata models
both as separate "frameworks" and OneTrust sells them as separate products ("SOC 2", "ISO 27001",
"GDPR", "HIPAA" as four distinct tiles). So the split is the vendors' own, not a NavERP invention.

  *templates and rules*; there is still no dispatcher.
- **Evidence is a pointer to something that exists elsewhere.** `core.Document` (0.1) already
  owns file upload; 0.21 does not re-declare a document table, it references one.

Success messages say **"recorded"**, never "enforced", "granted", "reminded" or "verified".

---

## 3. Reconciliation — what NavERP already owns (L29/L36)

**This is the most important section in the document.** `core` is a foundation app whose earlier
sub-modules already built several things whose *names* collide with the obvious 0.21 names. Each
row below is verified by reading the named file, not inferred.

| 0.21 candidate | Already in the repo | Verdict |
|---|---|---|
| `ComplianceFramework` | **`core.RegulatoryFramework`** — `apps/core/models/Privacy.py:72`. Codes `gdpr, ccpa, hipaa, lgpd, pipeda, other`; `dsar_window_days`; **`data_residency_region`** (CharField 80); unique per `(tenant, code)` | **DO NOT re-declare the name.** 0.8 already owns "which regime is this workspace under, and the obligations that implies". Naming a second class `ComplianceFramework` would give one workspace two answers to the same question. See the ruling below. |
| `DataResidencyPolicy` | `RegulatoryFramework.data_residency_region` (a single free-text region on the framework row) **and** `core.EnvironmentInstance` (0.16) which provisions dev/test/staging/sandbox | **Extend, don't duplicate.** 0.8's field is one free-text region on a framework row and is explicitly documented as "Recorded, NOT enforced". 0.21 promotes it into a real jurisdiction record with operations and transfer rules. The 0.8 field is left untouched (it is live data and a live form field) and 0.21 adds the structure beside it. |

| 1.4.8 | Work papers, findings rollup, expense tracking | ServiceNow Audit Management | **P2** |

### 1.5 Data residency & sovereignty (bullet 5)

| # | Feature | Source | Pri |
|---|---|---|---|
| 1.5.1 | A **region/jurisdiction** record: code, name, country, group | general (Azure data-residency concepts; Kiteworks sovereign regions) | **P1** |
| 1.5.2 | **Allowed operations** per region: store / process / transfer, and whether transfers are permitted | general | **P1** |
| 1.5.3 | **Transfer restrictions** to other regions | general | **P1** |
| 1.5.4 | **Key-management** residency note (where the keys live vs where the data lives) | general | **P1** |
| 1.5.5 | Region ↔ **environment** binding (which provisioned environment holds data in which region) | NavERP's own `EnvironmentInstance` (0.16) | **P1** |
| 1.5.6 | Actual **geofenced routing** of requests | — | **X** — NavERP is single-region Django; it cannot pin storage. Recorded intent only (§2) |
| 1.5.7 | A **data-residency compliance status** rollup per region | general | **P2** |

> `research` agent. It ran out of quota. The Phase 4 reviewers should treat the *search breadth*
> here as thinner than 0.20's, and lean harder on the reconciliation, which is exhaustive.

---

## 1. Feature catalog, deduplicated and prioritized

Each feature is tagged with the bullet it serves and the product(s) it was observed in.
**P1** = ships in this pass. **P2** = deferred to a later 0.21 pass. **X** = declined, with a reason.

### 1.1 Compliance frameworks (bullet 1)

| # | Feature | Source | Pri |
|---|---|---|---|
| 1.1.1 | A **framework** as its own record: code, name, version, issuing body, description, whether the workspace has adopted it | Drata "Frameworks", OneTrust "50+ ready-to-use frameworks" | **P1** |
| 1.1.2 | A **control** as its own record, framework-agnostic, with a stable code, title, description and category | Drata DCF ("the primary 'nodes' … to which requirements, risks, policies, monitoring tests … are connected") | **P1** |
| 1.1.3 | **Many-to-many** control↔framework mapping. Drata is explicit that one requirement maps to *several* controls and several controls map to one requirement, and that "mapping multiple controls to a single requirement is a common and accepted practice" | Drata DCF | **P1** |
| 1.1.4 | Per-mapping **coverage status** (not in scope / in progress / implemented / effective / not applicable) and an optional clause/requirement reference (`CC1.1`, `6.1.2`) | Drata DCF examples; Vanta control sets | **P1** |
| 1.1.5 | **Control set / scope selection** — a SOC 2 engagement may include only some of the five Trust Services Criteria, and changing scope mid-audit is dangerous enough that Vanta forbids it | Vanta (CC / A / C / PI / P; "not allowed during an active audit") | **P2** |
| 1.1.6 | **Gap analysis** (which required controls have no implemented control) | OneTrust; Drata GRC gap analysis | **P2** |
| 1.1.7 | Framework content shipped as a **seeded library** rather than typed per tenant | OneTrust, Drata, Vanta all ship catalogs | **P1** (seeder only — see §5) |
