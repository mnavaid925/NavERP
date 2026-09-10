# Research — Sub-module 7.6: Quality Management (Module 7 — Project Management, `projects`)

> **Read this first.** 7.6 is the module's **conformance engine**: it turns 7.1's chartered scope,
> 7.2's WBS/deliverable tree and 7.5's risk/issue position into a *planned, assured, controlled and
> formally accepted* quality position on one project's deliverables. It is the sub-module that
> answers three questions the earlier passes deliberately did not: **what must this deliverable
> satisfy?** (acceptance criteria + standard/regulatory mapping), **does it?** (QA reviews + QC
> inspections + defects), and **who formally accepted it?** (deliverable sign-off).
>
> **Researched 2026-09-11** against 10 leading products/practice sources (test-management suites
> TestRail / Zephyr Scale / Xray / qTest / Azure DevOps Test Plans / ALM; regulated-industry QMS
> MasterControl / ETQ / TrackWise / Veeva Vault QMS; SAP S/4HANA QM; Smartsheet / monday.com
> templates; ServiceNow SPM / Planview; and the PMBOK/ISO-9001 deliverable-acceptance process).
>
> **Recommended scope: 4 models** — `QualityPlan` [QPL-], `QualityReview` [QRV-],
> `DeliverableInspection` [QCI-], `QualityDefect` [QDF-] — plus **2 computed pages**
> (`quality_improvement`, `quality_acceptance`).
>
> It is **not** the enterprise QMS (**4.9 `scm`** / future **12.x**), **not** goods receiving
> inspection / receipt tolerance / return-to-vendor (**6.12 `procurement`**), **not** the
> warehouse-floor QC gate (**5.15 `inventory`**), **not** the schedule phase gate
> (**7.2 `ProjectMilestone`**), **not** the project issue register (**7.5**), **not** the document
> repository / lessons-learned store (**7.10**), **not** charts/BI (**7.16**), **not** the
> workflow/notification engine (**7.17**), and **not** the standards/methodology master data
> layer (**7.19**).
>
> **The two failure modes for this pass:**
> 1. **Building a second enterprise QMS.** `apps/scm` Module **4.9 Quality Management** already
>    ships `NonConformance` [NCR-], `CapaAction` [CAPA-], `QualityAudit` [QA-] and
>    `QualityInspection` [QC-] (verified below). 7.6's QC bullet must be a *project-deliverable*
>    inspection, never a rival NCR/CAPA/audit register. See **Ruling 1**.
> 2. **Duplicating `ProjectIssue`.** 7.5's issue register already carries severity, resolution,
>    escalation and lessons. A 7.6 defect is a *deliverable punch-list row with an acceptance
>    disposition* and **links to** a `ProjectIssue` by FK — it is not a second issue log. See
>    **Ruling 2**.

---

## Repo state checked first

### LIVE_LINKS built so far in Module 7 (`apps/core/navigation.py`)

`grep -n '"7\.' apps/core/navigation.py` → **`"7.1"` line 1702, `"7.2"` line 1717, `"7.3"` line
1732, `"7.4"` line 1747, `"7.5"` line 1766. Nothing else.** So 7.1–**7.5 are all built** and
**7.6's sidebar block will be the sixth Module 7 entry.** The `LIVE_LINKS` dict is the source of
truth for built-vs-roadmap (L31) — 7.6 is the lowest-numbered unbuilt `7.M`.

### The app exists; 7.1–7.5 are built (verified, not assumed)

```
apps/projects/models/ProjectInitiation/          → ProjectRequest[PRQ], Project[PRJ],
                                                   ProjectStakeholder[PST], ProjectKickoff[PKO]
apps/projects/models/ProjectPlanningScheduling/  → ProjectTask[TSK], TaskDependency[DEP],
                                                   ProjectMilestone[MST], ScheduleBaseline[BSL]
apps/projects/models/ResourceManagement/         → ResourceProfile[RSP], ResourceAllocation[RAL],
                                                   ResourceTimeEntry[RTE]
apps/projects/models/CostManagement/             → ProjectBudgetLine[PBL], BudgetRevision[BVR],
                                                   CostControlAccount[CCA], ProjectExpense[PEX]
apps/projects/models/RiskManagement/             → ProjectRisk[RSK], RiskResponseAction[RRA],
                                                   ProjectIssue[ISS], IssueEscalation[ESC]
```

- **Migrations shipped:** `0001` … `0006_projectrisk_projectissue_riskresponseaction_and_more`.
  **7.6's migration is `0007_…`.** (`ls apps/projects/migrations/` verified.)
- **Package convention (all five sub-modules):** `models/ forms/ views/ urls/<SubModule>/<Entity>.py`,
  same file name in all four layers, sub-package `__init__.py` files stay EMPTY, re-exports only in
  the four top-level `__init__.py` files. **7.6's sub-module folder is `QualityManagement/`** in
  each layer.
- **`models/__init__.py` re-export blocks:** five labelled blocks (`# --- 7.1 …` … `# --- 7.5 …`).
  **7.6 adds a sixth `# --- 7.6 Quality Management` block.** A missing re-export is a runtime
  `ImportError` for the seeder/tests/admin.
- **URL convention (`apps/projects/urls/__init__.py`):** every first path segment is a **disjoint
  literal** — **no route uses a converter in its first component**, the invariant that stops one
  sub-module shadowing another. 7.6's first segments (`quality-plans/`, `quality-reviews/`,
  `inspections/`, `defects/`, `quality-improvement/`, `quality-acceptance/`) are all new literals.
- **Template convention:** `templates/projects/initiation/` (7.1), `planning/` (7.2), `resource/`
  (7.3), `cost/` (7.4), `risk/` (7.5), each with lowercase-singular entity folders. **7.6 uses
  `templates/projects/quality/<entity>/{list,detail,form}.html`** (`qualityplan/`, `qualityreview/`,
  `inspection/`, `defect/`). `templates/projects/` verified: `cost/ initiation/ planning/ resource/
  risk/ overview.html` — **no `quality/` yet.**
- **Tests convention:** `test_<sub>_{models,forms,views,security}.py` + `<sub>_*` fixtures +
  `_<sub>_*` helpers in `conftest.py`. 7.1=`initiation`, 7.2=`planning`, 7.3=`resource`,
  7.4=`cost`, 7.5=`risk`. **7.6 uses `test_quality_*` / `quality_*` / `_quality_*`.**
  `conftest.py` is shared — only append with a full unfiltered re-run.
- **Seeder:** `apps/projects/management/commands/seed_projects.py` already splits per-sub-module
  guarded blocks — `_seed_tenant` (7.1), `_planning` (7.2), `_resourcing` (7.3), `_cost` (7.4),
  `_risk` (7.5), each idempotent on its own guard. **7.6 adds `_quality` with its own guard** and
  its children-first `--flush` order.
- **The `_base.py` toolkit** (`apps/projects/models/_base.py`): `TenantOwned` (tenant FK +
  created/updated), `TenantNumbered` (per-tenant `number` with the 5-attempt `IntegrityError`
  retry), `q2()` (quantize 2dp + clamp to `MAX_Q2 = 9999999999.99`), `ZERO`. **7.6 ships no money
  column** (L29 — a quality cost is a 7.4 `ProjectExpense`), so `q2()` is imported but unused on the
  model layer.
- **`views/_helpers.py`** already exports `owners(tenant)` (added by 7.5, line 79) — 7.6 **reuses
  it**, adds nothing.

### What 7.1–7.5 already recorded FOR 7.6 (do not re-derive)

- **7.2 owns the WBS *deliverable* node.** `ProjectTask.NODE_TYPE_CHOICES` is
  `[("deliverable", "Deliverable"), ("work_package", "Work Package")]`
  (`apps/projects/models/ProjectPlanningScheduling/ProjectTasks.py:25-28`). A `deliverable` node is
  "a summary node whose dates/effort are the ROLLUP of the work packages beneath it". **This is the
  row 7.6 inspects and accepts** — the `wbs_node` FK every 7.6 model carries.
- **7.2 already owns the *schedule* phase gate.** `ProjectMilestone` has `is_phase_gate`,
  `entry_criteria`, `exit_criteria` and the `mst_achieve` go/no-go verb
  (`ProjectMilestones.py:37-43`). **7.6's "formal review gate" is the *deliverable acceptance*
  decision, not the schedule gate** — see **Ruling 5**.
- **7.5 owns the issue register and the risk register.** `ProjectIssue` (`ProjectIssues.py:29`) is
  general (issue_type / severity / owner / resolution / escalation / `lessons_learned`), and
  `ProjectRisk` carries `category` including `"quality"` (`ProjectRisks.py:44`). 7.6 **FKs both by
  string and re-declares neither** — see **Ruling 2** and **Ruling 7**.
- **7.5's `rsk_realize` verb is the bridge idiom.** It flips a risk to `realized` and *creates the
  linked `ProjectIssue`* (`contract-projects-7.5.md` §4.1). 7.6's `qdf_raise_issue` copies exactly
  this shape for the defect→issue bridge.
- **7.5's "a bullet may be a computed page" precedent.** `risk_analysis` (matrix + EMV + Monte
  Carlo) and `risk_monitoring` (top-risk + burn-down + lessons lens) are POST/GET computed views
  over the register with **no stored table** (`contract-projects-7.5.md` §4.5–4.6). 7.6's bullets 4
  and 5 follow it.
- **7.4's frozen-row precedent** (`BudgetRevision.is_locked` / `ProjectExpense.is_locked`) is the
  idiom 7.6 copies for a `superseded` plan / `closed` defect / `accepted` inspection.

### Spine entities VERIFIED to exist (grep/read evidence)

| Entity | Verified at | What 7.6 uses it for |
|---|---|---|
| `projects.Project` [PRJ-] | `apps/projects/models/ProjectInitiation/Projects.py:27` | the container every 7.6 row FKs (`project` FK, `related_name="quality_plans"` / `"quality_reviews"` / `"quality_inspections"` / `"quality_defects"`); reads `.name`, `.code`, `.project_manager`, `.status` |
| `projects.ProjectTask` [TSK-] | `apps/projects/models/ProjectPlanningScheduling/ProjectTasks.py:22` | **the deliverable under quality control.** `wbs_node` FK (nullable; same-project `clean()` guard — the `ProjectMilestone.anchor_task` pattern at `ProjectMilestones.py:77-80`); `node_type="deliverable"` is the natural target |
| `projects.ProjectMilestone` [MST-] | `apps/projects/models/ProjectPlanningScheduling/ProjectMilestones.py:17` | **the schedule gate a deliverable acceptance is reviewed at.** Optional `milestone` FK on `DeliverableInspection` (nullable) — 7.6 does NOT re-declare `is_phase_gate`/`entry_criteria`/`exit_criteria` |
| `projects.ProjectRisk` [RSK-] | `apps/projects/models/RiskManagement/ProjectRisks.py:34` | **the quality-category risk a plan addresses.** Optional `source_risk` FK on `QualityPlan` (nullable, same-project guard); 7.6 does not touch the register |
| `projects.ProjectIssue` [ISS-] | `apps/projects/models/RiskManagement/ProjectIssues.py:29` | **the defect→issue bridge.** Nullable `project_issue` FK on `QualityDefect`, written by the POST-only `qdf_raise_issue` verb (the `rsk_realize` idiom) — 7.6 never duplicates `ProjectIssue` |
| `projects.ProjectStakeholder` [PST-] | `apps/projects/models/ProjectInitiation/ProjectStakeholders.py:24` | **the customer-validation source.** Carries `stakeholder_type` + RACI — a customer acceptor is grounded here, linked as a lens, not re-declared |
| `core.Party` | `apps/core/models/Party.py:5` | **the external acceptor.** `accepted_by_party` FK on `DeliverableInspection` (nullable) — customer validation by an outside party |
| `core.Document` | `apps/core/models/Document.py:5` | the GFK attachment store — the signed acceptance certificate / inspection evidence attaches **via `core.Document`**, no second attachment table (the 7.1 charter / 7.5 evidence ruling) |
| `core.Activity` | `apps/core/models/Activity.py:5` | the GFK note/meeting store — retrospective *minutes* and review *meetings* are 7.9's `core.Activity`; 7.6 links out |
| `core.AuditLog` | `apps/core/models/AuditLog.py:5` | accept / reject / resolve / close evidence. **`action` is varchar(10)** — verbs 7.6 writes: `create/update/delete/accept/reject/resolve/close/reopen` (all ≤ 10 chars; detail in `changes`) |
| `settings.AUTH_USER_MODEL` | — | every owner/inspector/reviewer/acceptor FK (all nullable `SET_NULL`) |

### Spine entities VERIFIED NOT to exist / to be OWNED ELSEWHERE (grep evidence)

1. **No project quality model exists.** `grep -rn "^class \(QualityPlan\|QualityReview\|
   QualityDefect\|DeliverableInspection\|QualityStandard\|Acceptance\|SignOff\)" apps/` → **empty.**
   Bullets 1–5 all need new tables *except* the enterprise tables in item 2.
2. **The enterprise QMS tables ALREADY EXIST — in `apps/scm`, not a future `apps/quality`.**
   `grep -rn "^class \(NonConformance\|CapaAction\|QualityAudit\|QualityInspection\)\b" apps/` →
   - `apps/scm/models/QualityManagement/NonConformances.py:28` `NonConformance` `NUMBER_PREFIX="NCR"`
   - `apps/scm/models/QualityManagement/CapaActions.py:24` `CapaAction` `NUMBER_PREFIX="CAPA"`
   - `apps/scm/models/QualityManagement/QualityAudits.py:25` `QualityAudit` `NUMBER_PREFIX="QA"`
   - `apps/scm/models/QualityManagement/QualityInspections.py:62` `QualityInspection` `NUMBER_PREFIX="QC"`
   These are Module **4.9 Quality Management System** (NavERP.md §4.9, `LIVE_LINKS["4.9"]` at
   `navigation.py:869`). **`apps/quality` does NOT exist** (`ls apps/` → no `quality`) and Module
   **12 QMS** is `⬜ Roadmap` — but the *as-built* spine already owns these concepts. See **Ruling 1**.
3. **`inventory` owns `QcChecklist`** — `apps/inventory/models/QualityControl/QcChecklists.py:24`
   (with `QcChecklistItem`), the warehouse-floor per-product/per-vendor pre-acceptance check set.
   `LIVE_LINKS["5.15"]` (`navigation.py:1348`) maps the "QC Checklists" bullet to
   `inventory:qcchecklist_list`. 7.6 **does not re-declare it** — see **Ruling 1**.
4. **`inventory` also owns `DefectReport[DEF-]`** (`apps/inventory/models/QualityControl/
   DefectReports.py:29`, `NUMBER_PREFIX="DEF"`) — the warehouse-floor defect log with a write-off.
   7.6's `QualityDefect` is deliverable-scoped, not goods-scoped — see **Ruling 2**.
5. **`procurement` 6.12 owns receiving inspection** — `apps/procurement/models/
   GoodsReceiptInspection/` = `ReceiptTolerancePolicy` (TenantOwned), `ReceiptDiscrepancy[RDS-]`,
   `ReturnToVendor[RTV-]`. Not 7.6's.
6. **No quality standards master.** `core` owns `Party/PartyRole/Address/ContactMethod/
   PartyRelationship/Employment/Activity/AuditLog/Document/OrgUnit/Tenant` only. scm 4.9's
   `QualityAudit.standard` is *free text* with the note *"a standards master is deferred"*
   (`QualityAudits.py:57-59`). A standards library is **7.19's** — see **Ruling 3**.
7. **No chart library and no scheduler/mail worker** (recorded by 7.1/6.8/6.19). 7.6 renders CSS
   bars, tables and badges only; the notification engine is **7.17's**.

### Naming-collision & prefix check (performed, not assumed)

- **Prefixes:** the full repo-wide inventory of `NUMBER_PREFIX = "…"` was dumped (≈250 values).
  **`QPL`, `QRV`, `QCI`, `QDF` are all free** (`grep -rl 'NUMBER_PREFIX = "<X>"' apps/` → 0 files
  each). Near-misses checked and clear: **`QA`, `QC`, `NCR`, `CAPA` are taken by scm 4.9**;
  **`DEF` is inventory's**; `QTA`, `QT`, `QUO`, `QRD` are taken — none of 7.6's four touches them.
- **Class names:** `QualityPlan` / `QualityReview` / `QualityDefect` / `DeliverableInspection` do
  **not** exist anywhere. **`QualityInspection` IS TAKEN** (scm 4.9) — this is why 7.6's inspection
  model is named **`DeliverableInspection`**, not `QualityInspection`. `QualityAudit`,
  `NonConformance`, `CapaAction` are also taken and are not reused.
- **URL stems:** `quality-plans/`, `quality-reviews/`, `inspections/`, `defects/`,
  `quality-improvement/`, `quality-acceptance/` are unused under `apps/projects/urls/`.
- **Templates:** `templates/projects/quality/` does not exist yet.
- **Tests:** `test_quality_*` / `quality_*` / `_quality_*` does not collide with
  `test_initiation_*`, `test_planning_*`, `test_resource_*`, `test_cost_*`, `test_risk_*`.
- **Migration:** next incremental is `0007_…` (7.5 shipped `0006`).

---

## THE RULINGS — boundaries 7.6 must set before anyone else does

### Ruling 1 — 7.6 is the PROJECT-scoped quality layer; the enterprise QMS tables are `scm` 4.9's

**The task's premise needs correcting against the code.** It assumed Module 12 (`apps/quality`) is
the only owner of `NonConformance[NCR-]` / `CapaAction[CAPA-]` / `Inspection[QC-]` /
`QualityAudit[QA-]`. In fact **`apps/scm` Module 4.9 already ships all four** (verified above) and
`LIVE_LINKS["4.9"]` is live at `navigation.py:869`. The `apps/core/navigation.py:1339-1347` banner
says it in as many words: *"The quality-ENGINEERING layer is SCM 4.9's (InspectionPlan,
QualityInspection, NonConformance — L36: point at it, never re-declare it)."*

**Decision: 7.6 ships no NCR, no CAPA, no audit programme, no goods inspection.** Its four models
are **project-deliverable-scoped**:

| Enterprise concept (owner) | 7.6's project-scoped counterpart | Why they are different objects |
|---|---|---|
| `scm.NonConformance` [NCR-] — goods/production/supplier finding with MRB disposition + stock effect | **`QualityDefect` [QDF-]** — a deliverable punch-list item with an *acceptance* disposition | scope (a batch vs a deliverable), disposition vocabulary (scrap/return-to-vendor vs rework/resubmit), **no stock effect** |
| `scm.QualityAudit` [QA-] — counterparty/process audit programme | **`QualityReview` [QRV-]** — a project methodology-adherence / compliance / improvement review | 7.6 reviews *the project's own conformance*, not a supplier or a certification body |
| `scm.QualityInspection` [QC-] — lot inspected against a snapshotted metrology plan | **`DeliverableInspection` [QCI-]** — a deliverable inspected/tested against a quality plan's acceptance criteria | 7.6 is acceptance-oriented, not measurement-oriented; **the class name is deliberately different** |
| `scm.CapaAction` [CAPA-] | *(none)* — a corrective action is 7.5's `ProjectIssue`/`RiskResponseAction`, or the enterprise CAPA | 7.6 does not re-declare CAPA |
| `scm.InspectionPlan` (criteria master) | **`QualityPlan` [QPL-]** — the per-deliverable acceptance-criteria plan | 7.6's plan is per-project/per-deliverable, not a reusable metrology template |

**A genuine enterprise nonconformance** found on a deliverable (a real safety/regulatory failure)
should be *raised as* an `scm.NonConformance` — but `scm.NonConformance` has **no project FK** and
its lifecycle is stock/MRB, so that bridge is **deferred** (a soft `ncr_number` reference at most)
until 4.9/12.x grows a project link. This is the pass's **#1 overlap risk** and is flagged for the
future **12.x QMS session** (see *Belongs to sibling sub-modules*).

### Ruling 2 — A defect is its OWN table that LINKS to `ProjectIssue`; it never duplicates it

The market splits two things "a defect" conflates: a **deliverable acceptance punch-list item**
(what is wrong with *this* deliverable, and what do we do about it before we accept) and a
**project issue** (a RAID-log problem that needs an owner, a severity, a resolution and possibly an
escalation). 7.5 already owns the second.

**Decision: 7.6 ships `QualityDefect` [QDF-] and gives it a nullable `project_issue` FK →
`projects.ProjectIssue`.** The defect row carries the quality-native fields the issue register does
not (the violated acceptance criterion / plan, `defect_category`, `disposition` ∈
{rework/repair/resubmit/accept_as_is/reject/deferred}); the POST-only **`qdf_raise_issue`** verb
*creates and links* a `ProjectIssue` when the defect needs RAID treatment (the exact `rsk_realize`
idiom 7.5 shipped). This is the same shape as 7.5's own risk→issue bridge: **one owner per concept,
a link between them, no second schema** (L36/L29).

### Ruling 3 — Acceptance criteria live on the plan; the STANDARD master is 7.19's (free text here)

Bullet 1 names *"acceptance criteria, regulatory requirements, and industry standard mapping."* The
*criteria* are per-deliverable project data and belong on `QualityPlan.acceptance_criteria`. The
*standard* (ISO 9001:2015, 21 CFR Part 11, ANSI/ASQ Z1.4 …) is a reusable **master** — and a
standards master is master data. scm 4.9 already made this call for audits: `QualityAudit.standard`
is a free-text `CharField` with the docstring note *"a standards master is deferred"*.

**Decision: `QualityPlan.standard_reference` and `regulatory_requirement` are free-text fields**;
the reusable standards/regulatory-clause **library is 7.19's** (Deferred). This is the same ruling
7.5 made for the risk taxonomy (a choices vocabulary, not a table — Ruling 6 there).

### Ruling 4 — Sign-off is a VERB + `core.Document`; the acceptance *record* is the inspection

Bullet 5 names *"formal review gates, customer validation, and acceptance documentation."*

**Decision: the acceptance record is a `DeliverableInspection` row** (`inspection_type="acceptance"`,
`usage_decision` ∈ {accept/accept_with_deviation/reject/rework}, plus `accepted_by` /
`accepted_by_party` / `accepted_at` / `acceptance_note`), the **sign-off is the POST-only
`qci_accept` verb** (it stamps the decision, the acceptor and the timestamp — the 7.2 `mst_achieve` /
7.4 frozen-row idiom), and the **acceptance documentation is a `core.Document`** attached to the
inspection via its GFK (7.10 owns the repository — Ruling 5 there). **No `AcceptanceSignOff` table**
and **no second document store.**

### Ruling 5 — The "formal review gate" is DELIVERABLE acceptance, not 7.2's schedule phase gate

7.2's `ProjectMilestone.is_phase_gate` already carries `entry_criteria` / `exit_criteria` and the
`mst_achieve` go/no-go verb. 7.6 must not re-declare it.

**Decision: 7.6's gate is the *deliverable acceptance decision*** (`DeliverableInspection` with
`inspection_type="acceptance"`), optionally anchored to the `ProjectMilestone` it is reviewed at via
a nullable `milestone` FK. The two are **related, not duplicated**: 7.2 gates *the schedule* ("may
this phase proceed?"), 7.6 gates *the deliverable* ("is this output accepted?"). A `QualityReview`
with `review_type="gate_review"` records the review meeting/checklist; the *decision* is the
inspection's usage decision.

### Ruling 6 — Continuous improvement: 7.6 owns the IMPROVEMENT RECORD; minutes/ceremony/repo are siblings'

Bullet 4 names *"kaizen events, retrospectives, and process maturity assessments."* Each term has a
sibling claim:

- retrospective **minutes** → **7.9** (*"Meeting Management — minutes capture"*, and 7.10 bullet 4
  names *"retrospectives"* in the knowledge repository);
- the sprint-retro **ceremony** → **7.13** (*"Retrospectives & Team Health"*);
- the **lessons repository** → **7.10**;
- the **methodology / template library** → **7.19**.

**Decision: 7.6 owns a `QualityReview` row with `review_type ∈ {kaizen_event, retrospective,
maturity_assessment}`** — the *improvement record* (what we will change, who owns it, by when, and
the before/after measure) is quality-management data. The minutes are a `core.Activity` (7.9's) and
the repository is 7.10's; 7.6 **links out, builds no store.** The **process maturity assessment** is
a **computed page** (`quality_improvement`) scoring the project's reviews/defects — **no stored
maturity table** (the 7.5 Monte Carlo ruling: a stored score goes stale the instant an input
changes).

### Ruling 7 — No money, no GL, no second ledger (L29)

7.6 ships **no money column and no journal**. If quality has a cost (rework, a failed-test
re-run, a third-party inspection fee), it is recorded as a **7.4 `ProjectExpense`** (soft
cross-reference — a note on the defect, never a write). scm 4.9 already made the identical call
(*"No JournalEntry (L29). `cost_of_quality` is a recorded management figure with no GL effect"*,
`NonConformances.py:22`). `q2()` is imported but 7.6 declares no `DecimalField`.

---

## Leaders surveyed (with source links)

The domain is **project quality management / QA-QC / deliverable acceptance** — from
test-management suites (TestRail, Zephyr Scale, Xray, qTest, Azure DevOps Test Plans, ALM) through
regulated-industry QMS platforms (MasterControl, ETQ, TrackWise, Veeva Vault QMS, SAP S/4HANA QM)
to the spreadsheet/board templates (Smartsheet, monday.com) and the **practice standard**
(PMBOK/ISO 9001 + the deliverable-acceptance process) that supplies the vocabulary all of them use.

1. **TestRail (IDERA)** — the standalone test-management reference: **test plans** (rated
   *excellent* for organisation), **test suites**, **test cases** (versioned, parameterised, shared
   steps, unlimited custom fields), **test runs** with per-case status/comment/**defect links**,
   **milestones** (progress by milestone), a **traceability matrix** ("connects test cases to
   requirements with a single click"), **coverage reports** and trend analysis.
   <br>[Test Management Tools Comparison 2026 (QA Skills)](https://qaskills.sh/blog/test-management-tools-comparison-2026) ·
   [Popular test management tools (TestRail)](https://www.testrail.com/blog/popular-test-management-tools/)
2. **Zephyr Scale (SmartBear) & Xray (Jira-native)** — the "quality inside the tracker" reference:
   **test cases**, **test cycles/executions**, **Test Plan / Test Set / Pre-Condition** issue types
   (Xray), **per-environment result tracking**, **requirement coverage** (Xray rated *excellent*)
   and **defect linking via native Jira issue links**.
   <br>[Test Management Platform Comparison (Modern QA)](https://modernqacourse.com/docs/en/18-test-management-tools/02-test-platforms/01-platform-comparison) ·
   [Test case management comparison (Autonoma)](https://getautonoma.com/blog/test-case-management-tools)
3. **qTest (Tricentis)** — the **enterprise-governance** reference: excellent test-plan and test-case
   management, `qTest Insights` portfolio analytics, CI/CD orchestration, and — the part that maps
   to 7.6 — **enterprise approval workflows, e-signatures, audit trails and compliance reporting**.
   <br>[qTest deep-dive (QA Skills)](https://qaskills.sh/blog/test-management-tools-comparison-2026)
4. **Azure DevOps Test Plans (Microsoft)** — the **UAT / acceptance** reference: test plans with
   **static / requirement-based / query-based suites**, test cases as **steps + expected outcomes**,
   **shared steps & shared parameters**, **configurations** (OS/browser), **end-to-end
   traceability** (tests and defects auto-linked to requirements and builds), a **requirements
   quality widget**, **progress reports**, and an explicit **User Acceptance Testing** flow
   (invite testers, monitor results). No native sign-off/gate — acceptance is a decision, not a
   built-in workflow.
   <br>[What is Azure Test Plans? (Microsoft Learn)](https://learn.microsoft.com/en-us/azure/devops/test/overview?view=azure-devops)
5. **HP / Micro Focus ALM & Quality Center** — the **enterprise lifecycle** reference that put
   *requirements ↔ test plan ↔ test lab ↔ defects* in one repository (the four-module ALM shape),
   with traceability and coverage as first-class governance.
   <br>[22 best test management tools (TestRail)](https://www.testrail.com/blog/popular-test-management-tools/)
6. **MasterControl / ETQ Reliance / TrackWise / Veeva Vault QMS** — the **regulated-industry QMS**
   reference: **document control, CAPA, nonconformance/deviation, audit management, change control,
   training**, e-signature (21 CFR Part 11) and **fixed approval ladders**. Veeva is strong where
   the QMS is one integrated Vault; TrackWise is the CAPA/workflow heavyweight.
   <br>[TrackWise vs Veeva QMS vs MasterControl compared (AIBudWP)](https://aibudwp.com/trackwise-vs-veeva-qms-vs-mastercontrol-quality-management-software-compared/) ·
   [Best non-conformance tracking software 2026 (Zipdo)](https://zipdo.co/best/non-conformance-tracking-software/)
7. **SAP S/4HANA Cloud — Quality Management (QM)** — the **one product that explicitly names
   "quality planning"**: *quality planning, quality inspection, quality notifications, quality
   control, quality certificates, supplier quality, audit management*, with continuous improvement
   named as a benefit. (Its "quality certificate" is the closest thing to a sign-off artifact.)
   <br>[Best quality management software (The CTO Club)](https://thectoclub.com/tools/best-quality-management-software/)
8. **Arena / ComplianceQuest / Ideagen / Intellect / QT9 / AlisQI / Intelex / QMS Xpress** — the
   **mid-market QMS** reference: the recurring five are **CAPA, nonconformance, audits &
   inspections, document control, supplier quality** (+ training). **Audits is the only capability
   named by all ten products**; "acceptance criteria", "sign-off" and "kaizen" are *not* named by
   any — they are project-management vocabulary, not QMS vocabulary.
   <br>[Best quality management software (The CTO Club)](https://thectoclub.com/tools/best-quality-management-software/)
9. **Smartsheet / monday.com quality templates** — the **spreadsheet/board** reference and the
   source of the field list most teams actually use: a **Project Quality Assurance Plan**, **QC
   checklists**, a **defect log**, and **acceptance sign-off** columns (criterion, evidence,
   accepted-by, date, conditions).
   <br>[Free Quality Assurance Templates (Smartsheet)](https://www.smartsheet.com/content/quality-assurance-templates) ·
   [Free Quality Control Templates (Smartsheet)](https://www.smartsheet.com/content/quality-control-templates)
10. **ServiceNow SPM / Planview** — the **stage-gate / portfolio** reference: **stage-gate review
    workflows**, review gates with entry/exit criteria, and portfolio quality roll-ups. (Its lesson
    for 7.6: a gate is a *review with a decision*, and the decision belongs to the gate object, not
    to a generic status field.)
    <br>[Planview vs ServiceNow (Gartner Peer Insights)](https://www.gartner.com/reviews/market/project-and-portfolio-management/compare/planview-vs-servicenow) ·
    [Best portfolio software 2026 (WorldMetrics)](https://worldmetrics.org/best/portfolio-software/)
11. **PMBOK / ISO 9001 + the deliverable-acceptance process** (not a product — the vocabulary
    source) — **acceptance criteria** defined early (charter/scope/contract), the **six-step
    acceptance process** (define criteria → review deliverables → test/UAT → stakeholder
    evaluation → **formal written sign-off** → record), the **acceptance types** (final / partial /
    **conditional** / provisional), the **punch list** for conditional acceptance, and the rule
    that **acceptance precedes handover** and must be **written** (a demo is not acceptance).
    <br>[Deliverable Acceptance & Handover (EduRev)](https://edurev.in/t/505275/Deliverable-Acceptance-and-Handover) ·
    [Acceptance in project management (CertifyEra)](https://certifyera.com/terms/acceptance-in-project-management) ·
    [Project closure & formal acceptance (BVOP)](https://bvop.org/kb/projectclosureactivities.html)

**Considered and not cited:** *Jira* on its own (no quality-native model — it is the *host* for
Zephyr/Xray, already cited); *Airtable/Asana/ClickUp* (generic work tools, no acceptance model);
*Deltek* (its quality surface is schedule/cost risk, already covered by 7.5); *Siemens Teamcenter
Quality* (PLM-scoped, adds no field the eleven do not evidence). Dropped rather than cited
second-hand.

---

## Feature catalog (this sub-module only)

Priority key: **table-stakes** (nearly every leader has it) · **common** (most have it) ·
**differentiator** (a few standouts). Spine names are grep-verified per the tables above.

### Bullet 1 — Quality Planning & Standards
*"Acceptance criteria, regulatory requirements, and industry standard mapping."*

- **A per-deliverable quality plan** — the plan that states what a deliverable must satisfy; SAP QM
  is the one product that names *"quality planning"* explicitly, and every PMBOK/ISO guide starts
  with *"acceptance criteria are defined early in the charter, scope statement, or contract."*
  · seen in: SAP S/4HANA QM, PMBOK/ISO 9001 practice, Smartsheet QA-plan template · priority:
  **table-stakes** · spine: **new table `QualityPlan`** · buildable now.
- **Measurable acceptance criteria** — *"clear, specific, measurable, relevant, testable"* — the
  criteria column every template carries. · seen in: PMBOK/ISO 9001, CertifyEra, Smartsheet ·
  priority: **table-stakes** · spine: `acceptance_criteria` TextField on `QualityPlan` ·
  buildable now.
- **A verification method per criterion** — *"testable … can be verified through inspections,
  tests, or demonstrations."* The market's standard method set is **inspection / testing /
  demonstration / review / analysis**. · seen in: PMBOK practice, SAP QM (inspection), Azure Test
  Plans (test/UAT) · priority: **table-stakes** · spine: `verification_method`
  `CharField(choices=…)` on `QualityPlan` · buildable now.
- **Industry-standard / regulatory mapping** — ISO 9001, 21 CFR Part 11, ANSI/ASQ Z1.4, customer
  specs. **The mapping is per-project free text; the reusable standards LIBRARY is master data.**
  · seen in: SAP QM, MasterControl/ETQ/Veeva (document control), scm 4.9 (`QualityAudit.standard`
  free text) · priority: **common** · spine: `standard_reference` + `regulatory_requirement`
  Char/TextFields on `QualityPlan` — **not a table** (Ruling 3) · buildable now.
- **A named plan owner + approval** — *"who is accountable for this deliverable's quality"*; the
  acceptance criteria are *frozen* once approved (the scm 4.9 snapshot idiom). · seen in: SAP QM,
  qTest (approval workflows), MasterControl · priority: **common** · spine: `owner`,
  `approved_by`/`approved_at` (verb-stamped) on `QualityPlan` · buildable now.
- **Quality-plan versioning / supersede** — a re-issued plan must not rewrite a past acceptance.
  · seen in: MasterControl/Veeva (document control), scm 4.9 (`InspectionResult` snapshot) ·
  priority: **common** · spine: `status ∈ {draft, active, superseded, closed}` + `is_locked`;
  full version history is **deferred → 7.10** (the document repository) · buildable now (status).
- **A reusable standards / criteria library** — SAP's *"templates for your quality management
  processes"*. · priority: **common** · **deferred → 7.19** (master data; Ruling 3) + 7.10 for the
  repository · not buildable without a master-data pass.

### Bullet 2 — Quality Assurance (QA)
*"Process audits, compliance checklists, and methodology adherence reviews."*

- **A project-scoped quality review record** — the review event that asks *"is this project
  following its own process/methodology?"*. **The audit PROGRAMME (supplier/customer/certification
  audits) is scm 4.9's `QualityAudit`** — 7.6 reviews the project, not a counterparty (Ruling 1).
  · seen in: SAP QM (audit management), MasterControl/ETQ/QT9 (audit), ServiceNow SPM (review
  gates) · priority: **table-stakes** · spine: **new table `QualityReview`** with
  `review_type ∈ {methodology_review, compliance_check, …}` · buildable now.
- **Methodology-adherence review** — *"did we hold the required reviews / follow the WBS
  process / produce the required artifacts?"*. · seen in: PMBOK practice, ServiceNow SPM stage-gate,
  scm 4.9 (internal audit) · priority: **table-stakes** · spine: `review_type="methodology_review"`
  + `scope` TextField on `QualityReview` · buildable now.
- **A compliance checklist on the review** — pass/fail checkpoints ticked during the review. (The
  reusable checklist LIBRARY is master data; the per-review checklist is data.) · seen in:
  MasterControl/ETQ/Intelex, Smartsheet QA checklist, scm 4.9 (`InspectionPlan` as the audit
  checklist) · priority: **table-stakes** · spine: `checklist` TextField on `QualityReview` +
  `findings` — **no checklist table this pass** (the 7.5 Ruling-6 idiom; a library is 7.19's) ·
  buildable now.
- **A reviewer, a review date and a status lifecycle** — the review register's cadence columns.
  · seen in: all QMS suites · priority: **table-stakes** · spine: `reviewer` FK,
  `review_date`, `status ∈ {planned, in_progress, reported, closed, cancelled}` on
  `QualityReview` · buildable now.
- **Findings from a review** — the review's output. (A *material* finding becomes a
  `QualityDefect` or a 7.5 `ProjectIssue`; an *enterprise* nonconformance is scm 4.9's NCR.)
  · seen in: scm 4.9 (findings ARE NCR rows), MasterControl · priority: **common** · spine:
  `findings` TextField + an optional link out (no second findings table — Ruling 1) · buildable now.
- **Recurring audit schedules / auto-generated audits** — a calendar-driven audit programme.
  · priority: **differentiator** · **deferred → 7.17** (the workflow/scheduler engine); 7.6 records
  the review, it does not schedule it.
- **Configurable approval ladders / e-signature on a review** — MasterControl/ETQ/Veeva/21 CFR
  Part 11. · priority: **differentiator** · **deferred → 7.17**; scm 4.9 already parked the
  identical feature (*"rules-based routing, configurable approval matrices and electronic-signature
  ladders … NavERP has no workflow engine"*, `CapaActions.py:14-17`).

### Bullet 3 — Quality Control (QC) & Inspections
*"Testing protocols, defect tracking, and inspection result recording."*

- **A deliverable inspection / test event** — the execution record: a deliverable checked against
  a plan's acceptance criteria, with a result. **The class is `DeliverableInspection`, not
  `QualityInspection`** (scm 4.9 owns that name — Ruling 1). · seen in: TestRail (test run), Azure
  Test Plans (test run), qTest, SAP QM (inspection), scm 4.9 (QualityInspection) · priority:
  **table-stakes** · spine: **new table `DeliverableInspection`** · buildable now.
- **A testing protocol / procedure** — the steps + expected outcomes (Azure Test Plans) / the test
  method. · seen in: Azure Test Plans, TestRail, Xray · priority: **table-stakes** · spine:
  `description` TextField on `DeliverableInspection` (the protocol) — **no test-step child table
  this pass** (a step editor is a differentiator; see below) · buildable now.
- **Inspection result recording** — pass / fail / conditional / N/A, with the inspected date and
  the inspector. · seen in: all · priority: **table-stakes** · spine: `result` choices +
  `inspected_date` + `inspector` FK on `DeliverableInspection` · buildable now.
- **A usage / acceptance decision distinct from the result** — SAP/scm 4.9 split *pass/fail* from
  *accept / accept-with-deviation / reject / rework*. · seen in: SAP QM, scm 4.9
  (`USAGE_DECISION_CHOICES`) · priority: **table-stakes** · spine: `usage_decision` choices on
  `DeliverableInspection` (the acceptance decision — Ruling 4) · buildable now.
- **Defect tracking (the punch list)** — the defects an inspection (or a review) finds, each with a
  disposition and an owner. **A deliverable punch-list row, distinct from scm's goods NCR and from
  7.5's `ProjectIssue`** (Ruling 2). · seen in: Smartsheet defect log, TestRail/Azure (bug links),
  scm 4.9 (NCR), inventory `DefectReport` · priority: **table-stakes** · spine: **new table
  `QualityDefect`** with an optional `project_issue` FK · buildable now.
- **Defect severity + category + disposition** — critical/major/minor/observation; functional /
  performance / documentation / compliance / …; rework / repair / resubmit / accept-as-is / reject.
  · seen in: scm 4.9 (severity + disposition), MasterControl, PMBOK · priority: **table-stakes** ·
  spine: `severity` / `defect_category` / `disposition` choices on `QualityDefect` · buildable now.
- **The defect→project-issue bridge** — a defect that needs RAID treatment becomes a 7.5 issue.
  · priority: **common** · spine: nullable `project_issue` FK + the POST-only **`qdf_raise_issue`**
  verb (the `rsk_realize` idiom) · buildable now.
- **Requirement / criterion traceability matrix** — TestRail "connects test cases to requirements",
  Xray "every Jira issue links to test cases", Azure "end-to-end traceability". · seen in: TestRail,
  Xray, qTest, Azure Test Plans · priority: **common** · spine: `quality_plan` FK on both
  `DeliverableInspection` and `QualityDefect` gives a *criterion → inspection → defect* chain; the
  rendered **traceability grid is a lens/section** (the 7.5 matrix precedent), **no matrix table**
  · buildable now (FK + view).
- **A test-step editor (steps + expected outcomes, shared steps/parameters)** — Azure Test Plans'
  child model. · priority: **common** · **deferred** — a step child-table forks CRUD for a
  differentiator; the protocol `description` is the honest stand-in this pass.
- **Configurations / parameterised test data** (OS/browser/data sets) · seen in: Azure Test Plans,
  TestRail, Xray · priority: **differentiator** · **deferred** — needs a configuration matrix model.
- **Automated test execution / CI integration** (qTest Launch, Azure pipelines) · priority:
  **differentiator** · **deferred → 7.18** (integrations).
- **AQL sampling plans / statistical process control (SPC)** — scm 4.9 / Module 12 territory.
  · priority: **differentiator** · **owned elsewhere → scm 4.9 / 12.x** (goods/production quality).

### Bullet 4 — Continuous Improvement
*"Kaizen events, retrospectives, and process maturity assessments."*

- **An improvement record (kaizen / retrospective)** — what we will change, who owns it, by when,
  and the before/after measure. **7.6 owns the record; the minutes are 7.9's and the ceremony is
  7.13's** (Ruling 6). · seen in: SAP QM (continuous improvement), the QMS suites (narrative
  "continuous improvement"), PMBOK (lessons-learned register) · priority: **table-stakes** ·
  spine: `review_type ∈ {kaizen_event, retrospective}` + `improvement_action` /
  `improvement_owner` / `improvement_due_date` / `improvement_status` on `QualityReview` ·
  buildable now.
- **A process maturity assessment** — CMMI-style maturity scoring (the practice source: PDCA/Kaizen
  + maturity models). · seen in: CMMI Institute, continuous-improvement practice · priority:
  **common** · spine: a **computed page** (`quality_improvement`) scoring the project's reviews and
  defect closure, plus an optional per-review `maturity_score` — **no stored maturity table**
  (Ruling 6) · buildable now (view).
- **An improvement action with an owner and a due date** — the action half of every retro/kaizen.
  · seen in: PMBOK lessons-learned register, ServiceNow/Planview · priority: **table-stakes** ·
  spine: the `improvement_*` fields on `QualityReview` · buildable now.
- **Lessons-learned integration** — PMBOK's lessons-learned register, updated throughout and
  searched at the start of new projects. · seen in: PMBOK practice, scm 4.9 (CAPA), 7.5 (the
  `lessons_learned` field precedent) · priority: **common** · spine: **`lessons_learned` TextField
  on `QualityDefect`** + a link to 7.10's repository — **NO new table** (Ruling 6; the 7.5 Ruling-3
  idiom) · buildable now.
- **A defect-trend / improvement trend over time** — PDCA's "check" step. · priority: **common** ·
  spine: a **computed monitoring table** (defects by period, closure rate — CSS bars, **not a
  chart**, 7.16) · buildable now (view).
- **Retrospective boards / team-sentiment surveys** — 7.13's *"Retrospectives & Team Health"*.
  · priority: **differentiator** · **owned elsewhere → 7.13**.
- **A searchable lessons-learned repository** — 7.10 bullet 4. · priority: **common** ·
  **owned elsewhere → 7.10**; 7.6's `lessons_learned` field feeds it.
- **Configurable methodology/template library** — 7.19. · priority: **common** ·
  **owned elsewhere → 7.19**.

### Bullet 5 — Deliverable Acceptance & Sign-off
*"Formal review gates, customer validation, and acceptance documentation."*

- **A formal acceptance record per deliverable** — the decision that a deliverable is accepted
  (final / partial / conditional / provisional — CertifyEra), with the acceptor and the date.
  · seen in: PMBOK/ISO 9001 (the six-step acceptance process), SAP QM (quality certificate),
  Azure Test Plans (UAT), ServiceNow/Planview (stage-gate) · priority: **table-stakes** · spine:
  a `DeliverableInspection` with `inspection_type="acceptance"` + `usage_decision` +
  `accepted_by`/`accepted_by_party`/`accepted_at` (Ruling 4) · buildable now.
- **A formal review gate** — a review with a go/no-go decision at a gate. **7.6's gate is the
  deliverable acceptance decision; 7.2's is the schedule phase gate** (Ruling 5). · seen in:
  ServiceNow SPM, Planview, scm 4.9 (audit), 7.2 (`mst_achieve`) · priority: **table-stakes** ·
  spine: `DeliverableInspection.milestone` FK (optional) + `QualityReview` with
  `review_type="gate_review"`; the POST-only **`qci_accept`** verb is the decision · buildable now.
- **Customer validation by an external party** — the acceptor is often the customer, not a login.
  · seen in: PMBOK ("customer or sponsor acceptance"), Subtrak (client acceptance) · priority:
  **table-stakes** · spine: `accepted_by_party` FK → `core.Party` (nullable) +
  `accepted_by` FK → `AUTH_USER_MODEL`; grounded in `pst_list` as a lens · buildable now.
- **Conditional acceptance + a punch list** — *"conditional acceptance occurs when the customer
  agrees the deliverable is mostly complete but identifies minor items … collected in a punch
  list"*; the PM must track the open items before final acceptance. · seen in: PMBOK/BVOP practice,
  Subtrak · priority: **table-stakes** · spine: `result="conditional"` +
  `acceptance_note` on the inspection, and the **open `QualityDefect` rows are the punch list**
  (disposition ≠ accept_as_is) · buildable now.
- **Acceptance documentation** — *"a signed acceptance form or certificate … filed in the project
  records."* · seen in: PMBOK practice, Subtrak (closeout package), SAP (quality certificate) ·
  priority: **table-stakes** · spine: a **`core.Document`** attached to the inspection via its
  GFK (7.10 owns the repository — Ruling 4) · buildable now.
- **A signed acceptance certificate (generated PDF)** — the artifact itself. · priority:
  **common** · **deferred → 7.16** (report generation) — 7.6 renders a printable acceptance page,
  not a PDF engine.
- **Acceptance triggering handover / milestone billing** — *"acceptance triggers financial
  transactions, such as final payments"*. · priority: **common** · **owned elsewhere** — a milestone
  billing link is 7.15's, a handover is 7.14's; 7.6 records the acceptance only (no GL — L29/Ruling 7).
- **Electronic signature (21 CFR Part 11)** — Veeva/MasterControl. · priority: **differentiator** ·
  **deferred → 7.17** (the workflow/e-signature engine); 7.6 records a named acceptor + timestamp.

### Beyond the bullets (found in the market, worth recording)

- **A traceability matrix (criterion ↔ inspection ↔ defect)** — TestRail/Xray/qTest/Azure. ·
  priority: **common** · spine: FK chain + a rendered grid — **no matrix table** · buildable now.
- **A quality dashboard / RAG status per deliverable** — ServiceNow/Planview, every QMS. ·
  priority: **common** · spine: the **`quality_acceptance` computed board** + colour badges;
  charts are 7.16's · buildable now.
- **Defect escape rate / rework rate KPIs** — qTest Insights, ARM-style KRIs. · priority:
  **differentiator** · **deferred** — KPI definitions are master data (7.19) and the values need a
  metrics engine; 7.6's defect counts stand in.
- **Supplier-quality linkage (a defect traced to a supplier)** — scm 4.2/4.9 territory. · priority:
  **common** · **owned elsewhere → scm 4.9** (supplier quality / SCAR).

---

## Recommended build scope (this pass — 4 models)

All four are tenant-scoped `TenantNumbered` subclasses in `apps/projects/models/QualityManagement/`
(one file per entity, same name in `forms/ views/ urls/`), full CRUD (list with working filters +
create + detail + edit + POST-only delete), templates under
`templates/projects/quality/<entity>/{list,detail,form}.html`, re-export block
`# --- 7.6 Quality Management` in `apps/projects/models/__init__.py` (a missing re-export is a
runtime `ImportError`), migration `0007_…`, seeder block `_quality` with its own guard, tests
`test_quality_*`. **No money column, no score column, no simulation table** — every pass rate,
punch-list count and maturity figure is a derived property or a computed view (the 7.1 ROI / 7.4
EVM / 7.5 Monte-Carlo ruling). Audit actions ≤ 10 chars.

### 1. `QualityPlan` [**QPL-**] — *what one deliverable must satisfy: its acceptance criteria, its
verification method, its standard/regulatory references, its owner, and its approval.*

Covers bullet **1 (Quality Planning & Standards)** and is the criteria anchor bullets 3 and 5
inspect against. One plan per deliverable (or per project, when no WBS node is named).

Fields:
- `project` → `projects.Project` CASCADE `related_name="quality_plans"` (the container; read-only
  parent).
- `wbs_node` → `projects.ProjectTask` SET_NULL null+blank `related_name="quality_plans"` — **the
  deliverable**; same-project `clean()` guard (the `ProjectMilestone.anchor_task` pattern).
- `source_risk` → `projects.ProjectRisk` SET_NULL null+blank `related_name="quality_plans"` — the
  7.5 quality-category risk this plan mitigates (optional; same-project guard).
- `title` CharField(255); `description` TextField blank.
- `acceptance_criteria` TextField() — **required**; the measurable criteria (bullet 1's core).
- `verification_method` CharField(max_length=16, choices=…) — `inspection / testing /
  demonstration / review / analysis / audit`.
- `standard_reference` CharField(120) blank — free text, e.g. `"ISO 9001:2015"`, `"21 CFR Part 11"`
  (**a standards master is 7.19's** — Ruling 3; the scm 4.9 `QualityAudit.standard` idiom).
- `regulatory_requirement` TextField blank — the clause/requirement text.
- `owner` → `AUTH_USER_MODEL` SET_NULL null+blank `related_name="owned_quality_plans"`.
- `status` CharField(max_length=16, choices=…) — **`draft / active / superseded / closed`** —
  **off the form**.
- `planned_review_date` DateField null+blank (**derived `is_review_overdue`**).
- `approved_by` → `AUTH_USER_MODEL` SET_NULL null+blank `editable=False` `related_name="approved_quality_plans"`;
  `approved_at` DateTimeField null+blank `editable=False` (stamped by the `qpl_approve` verb).
- `created_by` → `AUTH_USER_MODEL` SET_NULL null+blank `editable=False` `related_name="qpl_created"`.

`Meta`: `ordering = ["-created_at", "-id"]`; `unique_together = ("tenant", "number")`; indexes
`("tenant","project")` → `qpl_tnt_project_idx`, `("tenant","status")` → `qpl_tnt_status_idx`,
`("tenant","wbs_node")` → `qpl_tnt_wbs_idx`, `("tenant","-created_at")` → `qpl_tnt_created_idx`.

**Derived:** `is_review_overdue`, `is_locked` (`status in ("superseded","closed")`).

**Verbs (POST-only, audited):** `qpl_approve` (login; `draft → active`, stamps `approved_by`/
`approved_at`, audit `update` with `{"verb":"approve"}`); `qpl_supersede` (tenant_admin; `active →
superseded`, audit `update`). Approved/superseded rows refuse edit/delete of the criteria
(frozen-row guard — the 7.4 `BudgetRevision` idiom).

**FKs (all verified):** `projects.Project`, `projects.ProjectTask`, `projects.ProjectRisk`,
`AUTH_USER_MODEL`.

### 2. `QualityReview` [**QRV-**] — *one project quality event: a methodology/compliance review, a
gate review, or a kaizen/retrospective improvement, with its checklist, findings and improvement
action.*

Covers bullet **2 (Quality Assurance)** and bullet **4 (Continuous Improvement)**, discriminated by
`review_type`. **This is a deliberate consolidation of two bullets into one "structured quality
event" register** — both are *an event with a checklist, findings, an owner and actions*, and the
market's QMS suites model them as one generic record with a type; splitting them would fork CRUD to
express one choice field's worth of difference (the inventory 5.15 `QcChecklist` "one object with a
kind" ruling). The alternative (a 5th `QualityImprovement` model) is the named cut-order fallback
below.

Fields:
- `project` → `projects.Project` CASCADE `related_name="quality_reviews"`.
- `wbs_node` → `projects.ProjectTask` SET_NULL null+blank `related_name="quality_reviews"`
  (optional anchor; same-project guard).
- `quality_plan` → `projects.QualityPlan` SET_NULL null+blank `related_name="reviews"` (optional —
  the plan this review checks against).
- `title` CharField(255); `scope` TextField blank (what was reviewed).
- `review_type` CharField(max_length=24, choices=…) — **`methodology_review / compliance_check /
  gate_review / kaizen_event / retrospective / maturity_assessment`**.
- `checklist` TextField blank (the compliance checklist items ticked during the review — **a
  reusable checklist library is 7.19's**; no checklist table — the 7.5 Ruling-6 idiom).
- `findings` TextField blank.
- `reviewer` → `AUTH_USER_MODEL` SET_NULL null+blank `related_name="conducted_quality_reviews"`.
- `review_date` DateField (default `timezone.localdate`).
- `status` CharField(max_length=12, choices=…) — **`planned / in_progress / reported / closed /
  cancelled`** — **off the form**.
- `maturity_score` PositiveSmallIntegerField null+blank (`MinValueValidator(1)`,
  `MaxValueValidator(5)`) — the optional process-maturity rating (used by `maturity_assessment` /
  `methodology_review`).
- **Improvement (bullet 4):** `improvement_action` TextField blank; `improvement_owner` →
  `AUTH_USER_MODEL` SET_NULL null+blank `related_name="owned_quality_reviews"`;
  `improvement_due_date` DateField null+blank (**derived `is_improvement_overdue`**);
  `improvement_status` CharField(max_length=12, choices=…) — `n_a / planned / in_progress / done`.
- `closed_at` DateTimeField null+blank `editable=False`; `created_by` → `AUTH_USER_MODEL`
  SET_NULL null+blank `editable=False` `related_name="qrv_created"`.

`Meta`: `ordering = ["-review_date", "-id"]`; `unique_together = ("tenant", "number")`; indexes
`("tenant","project")` → `qrv_tnt_project_idx`, `("tenant","review_type")` → `qrv_tnt_type_idx`,
`("tenant","status")` → `qrv_tnt_status_idx`, `("tenant","improvement_status")` →
`qrv_tnt_imp_idx`, `("tenant","-review_date")` → `qrv_tnt_date_idx`.

**Derived:** `is_improvement_overdue`, `is_locked` (`status in ("closed","cancelled")`),
`is_improvement` (`review_type in ("kaizen_event","retrospective")`).

**Verbs:** `qrv_report` (login; `in_progress → reported`, audit `update`); `qrv_close` (login;
`reported → closed`, stamps `closed_at`, audit `close`). Closed rows refuse edit/delete.

**FKs (all verified):** `projects.Project`, `projects.ProjectTask`, `projects.QualityPlan`,
`AUTH_USER_MODEL`.

### 3. `DeliverableInspection` [**QCI-**] — *one inspection/test/review of one deliverable against a
plan: the protocol, the result, the usage/acceptance decision, the acceptor and the evidence.*

Covers bullet **3 (QC & Inspections — the execution + result recording)** and bullet **5
(Deliverable Acceptance & Sign-off — the acceptance decision, customer validation, the document
link)**. Named `DeliverableInspection` because `QualityInspection` is taken by scm 4.9 (Ruling 1).

Fields:
- `project` → `projects.Project` CASCADE `related_name="quality_inspections"`.
- `wbs_node` → `projects.ProjectTask` SET_NULL null+blank `related_name="quality_inspections"`
  (the deliverable; same-project guard).
- `quality_plan` → `projects.QualityPlan` SET_NULL null+blank `related_name="inspections"` (the
  criteria inspected against; same-project guard).
- `milestone` → `projects.ProjectMilestone` SET_NULL null+blank `related_name="quality_inspections"`
  (the gate this acceptance is reviewed at — **7.2's gate, not re-declared** — Ruling 5).
- `title` CharField(255); `description` TextField blank (the testing protocol / procedure).
- `inspection_type` CharField(max_length=16, choices=…) — **`review / testing / demonstration /
  walkthrough / acceptance`**.
- `planned_date` DateField null+blank; `inspected_date` DateField null+blank (**derived `is_overdue`**).
- `inspector` → `AUTH_USER_MODEL` SET_NULL null+blank `related_name="conducted_inspections"`.
- `result` CharField(max_length=12, choices=…) — **`pending / pass / fail / conditional /
  not_applicable`**.
- `usage_decision` CharField(max_length=24, choices=…) — **`pending / accept / accept_with_deviation
  / reject / rework`** (the scm 4.9 `USAGE_DECISION_CHOICES` vocabulary; Ruling 4).
- `findings` TextField blank.
- **Acceptance (bullet 5 — verb-written, never form fields — the 7.4 `decision_notes` rule):**
  `accepted_by` → `AUTH_USER_MODEL` SET_NULL null+blank `editable=False`
  `related_name="accepted_inspections"`; `accepted_by_party` → `core.Party` SET_NULL null+blank
  `related_name="accepted_inspections"` (the external/customer acceptor); `accepted_at` DateTimeField
  null+blank `editable=False`; `acceptance_note` TextField blank (conditions / reservations).
- `status` CharField(max_length=12, choices=…) — **`planned / in_progress / passed / failed /
  on_hold / cancelled`** (the scm 4.9 `STATUS_CHOICES` vocabulary) — **off the form**.
- `created_by` → `AUTH_USER_MODEL` SET_NULL null+blank `editable=False` `related_name="qci_created"`.

`Meta`: `ordering = ["-created_at", "-id"]`; `unique_together = ("tenant", "number")`; indexes
`("tenant","project")` → `qci_tnt_project_idx`, `("tenant","status")` → `qci_tnt_status_idx`,
`("tenant","result")` → `qci_tnt_result_idx`, `("tenant","usage_decision")` → `qci_tnt_decision_idx`,
`("tenant","wbs_node")` → `qci_tnt_wbs_idx`.

**Derived:** `is_overdue`, `is_locked` (`status in ("passed","failed","cancelled")` or
`usage_decision != "pending"`), `defect_count` (`self.defects.count()`), `is_acceptance`
(`inspection_type == "acceptance"`).

**Verbs (POST-only, audited; `previous` captured first):** `qci_record` (login; sets `result` +
`inspected_date` + `status`, audit `update`); **`qci_accept`** (login; sets `usage_decision` ∈
{accept, accept_with_deviation}, `accepted_by`/`accepted_by_party`/`accepted_at`, `status="passed"`,
audit `accept`); `qci_reject` (login; `usage_decision="reject"`, `status="failed"`, audit `reject`).
Accepted/failed rows refuse edit/delete (frozen-row guard).

**FKs (all verified):** `projects.Project`, `projects.ProjectTask`, `projects.QualityPlan`,
`projects.ProjectMilestone`, `core.Party`, `AUTH_USER_MODEL`.

### 4. `QualityDefect` [**QDF-**] — *one punch-list item on a deliverable: what is wrong, against
which criterion, how severe, its disposition, its owner, and (optionally) the 7.5 issue it became.*

Covers bullet **3's defect tracking** and bullet **5's punch list**. **It is NOT a second NCR
(scm 4.9's) and NOT a second issue log (7.5's)** — it links to `ProjectIssue` by FK (Ruling 2).

Fields:
- `project` → `projects.Project` CASCADE `related_name="quality_defects"`.
- `wbs_node` → `projects.ProjectTask` SET_NULL null+blank `related_name="quality_defects"`.
- `quality_plan` → `projects.QualityPlan` SET_NULL null+blank `related_name="defects"` (the
  criterion violated; same-project guard).
- `inspection` → `projects.DeliverableInspection` SET_NULL null+blank `related_name="defects"`
  (the inspection that found it).
- `project_issue` → `projects.ProjectIssue` SET_NULL null+blank `related_name="quality_defects"`
  (**the bridge — written by `qdf_raise_issue`, the `rsk_realize` idiom**).
- `title` CharField(255); `description` TextField().
- `defect_category` CharField(max_length=16, choices=…) — **`functional / performance /
  documentation / compliance / dimensional / workmanship / usability / other`** (deliverable-quality
  categories — **deliberately distinct from scm 4.9's goods categories**).
- `severity` CharField(max_length=8, choices=…) — **`critical / major / minor / observation`**
  (the scm 4.9 `NonConformance.SEVERITY_CHOICES` vocabulary, reused verbatim).
- `disposition` CharField(max_length=16, choices=…) — **`open / rework / repair / resubmit /
  accept_as_is / reject / deferred`** (the punch-list disposition).
- `status` CharField(max_length=12, choices=…) — **`open / in_progress / resolved / closed /
  cancelled`** — **off the form**.
- `owner` → `AUTH_USER_MODEL` SET_NULL null+blank `related_name="owned_quality_defects"`.
- `identified_date` DateField (default `timezone.localdate`); `due_date` DateField null+blank
  (**derived `is_overdue`, `age_days`**).
- `root_cause` TextField blank; `resolution_note` TextField blank;
  `resolved_by` → `AUTH_USER_MODEL` SET_NULL null+blank `editable=False`
  `related_name="resolved_quality_defects"`; `resolved_at` DateTimeField null+blank `editable=False`.
- `lessons_learned` TextField blank (the 7.5 Ruling-3 idiom — **the repository is 7.10's**).
- `created_by` → `AUTH_USER_MODEL` SET_NULL null+blank `editable=False` `related_name="qdf_created"`.

`Meta`: `ordering = ["-created_at", "-id"]`; `unique_together = ("tenant", "number")`; indexes
`("tenant","project")` → `qdf_tnt_project_idx`, `("tenant","status")` → `qdf_tnt_status_idx`,
`("tenant","severity")` → `qdf_tnt_severity_idx`, `("tenant","disposition")` →
`qdf_tnt_disp_idx`, `("tenant","-created_at")` → `qdf_tnt_created_idx`.

**Derived:** `is_overdue` = `due_date` set, `< today`, `status in ("open","in_progress")`;
`age_days`; `is_open`; `is_locked` (`status in ("resolved","closed")`).

**Verbs (POST-only, audited):** `qdf_resolve` (login; binds a resolution form, sets `root_cause`/
`resolution_note`/`resolved_by`/`resolved_at`, `status="resolved"`, audit `resolve`); `qdf_close`
(login; `resolved → closed`, audit `close`); **`qdf_raise_issue`** (login; creates a
`projects.ProjectIssue` — `project`, `wbs_node`, `title`, `description`, `severity` mapped from
`severity`, `owner`, `raised_by=request.user`, `created_by=request.user` — sets `project_issue`,
audits `create` on the issue and `update` on the defect; message names both numbers).
Resolved/closed rows refuse edit/delete.

**FKs (all verified):** `projects.Project`, `projects.ProjectTask`, `projects.QualityPlan`,
`projects.DeliverableInspection`, `projects.ProjectIssue`, `AUTH_USER_MODEL`.

**Auto-number prefixes to reserve:** `QPL`, `QRV`, `QCI`, `QDF` — **all four verified free** across
`apps/` (see the collision check above). `QA`/`QC`/`NCR`/`CAPA` are scm 4.9's; `DEF` is inventory's;
none of the four touches them.

**Computed pages (no model — the 7.3 `capacity_demand` / 7.5 `risk_analysis` precedent):**
- **`quality_improvement`** — the **continuous-improvement & maturity board** (GET-only): the
  kaizen/retrospective register (`review_type ∈ {kaizen_event, retrospective}`) with their
  `improvement_status`; the **process-maturity assessment** (a computed score over the project's
  reviews' `maturity_score` and defect closure — a table + band, **no stored maturity table**,
  Ruling 6); the **defect-trend table** (defects opened/closed by period — CSS bars, **not a
  chart**, 7.16); the **lessons lens** (closed defects with a non-empty `lessons_learned` + a link
  to 7.10's repository).
- **`quality_acceptance`** — the **deliverable acceptance board** (GET-only): one row per WBS
  deliverable with its `QualityPlan` status, its latest `DeliverableInspection` result, its open
  `QualityDefect` punch-list count, and its acceptance state (pending / conditional / accepted /
  rejected), plus the `qci_accept` action and the acceptance-queue count.

**Trade-offs I am consciously accepting (state them in the code):**
- **`QualityReview` carries both QA (bullet 2) and improvement (bullet 4)** via `review_type`. Both
  are "a structured quality event with a checklist, findings, an owner and actions"; a separate
  `QualityImprovement` table would fork CRUD to express one choice field (the inventory 5.15
  `QcChecklist` "one object with a kind" ruling). The split is the named cut-order fallback below.
- **`DeliverableInspection` carries both QC (bullet 3) and acceptance (bullet 5).** Acceptance *is*
  the terminal inspection decision — SAP QM and scm 4.9 both split `result` from `usage_decision` on
  one row; a separate `AcceptanceSignOff` table would duplicate the row it accepts (Ruling 4).
- **A defect links to `ProjectIssue`, it is not one.** The defect carries quality-native fields
  (criterion, category, disposition); the issue carries RAID treatment. `qdf_raise_issue` bridges
  them (Ruling 2).
- **The enterprise NCR/CAPA/audit tables are scm 4.9's.** 7.6 builds none of them (Ruling 1) — the
  #1 overlap risk, flagged for 12.x.
- **No money, no stored score, no chart.** Cost is a 7.4 `ProjectExpense`; maturity and pass rates
  are computed; charts are 7.16's (Ruling 6/7).
- **If the pass runs long, the cut order is: `QualityDefect` → `QualityReview` → (never)
  `QualityPlan`/`DeliverableInspection`.** Folding `QualityDefect` into `DeliverableInspection`
  costs bullet 3 its punch-list register (the inspection's `findings` text survives) but degrades
  gracefully; folding `QualityReview` costs bullets 2/4 their register (a `QualityPlan` note
  survives). `QualityPlan` and `DeliverableInspection` are **never cut** — bullets 1/3/5 have no
  other home.

**Sidebar entry to add — `LIVE_LINKS["7.6"]`:**

```python
"7.6": {
    "Quality Planning & Standards":      "projects:qpl_list",
    # QA reviews are the review register's assurance lens (methodology + compliance). The audit
    # PROGRAMME (supplier/customer/certification) stays scm 4.9's QualityAudit (L36) — 7.6 reviews
    # the PROJECT's conformance, not a counterparty.
    "Quality Assurance (QA)":            "projects:qrv_list?kind=assurance",
    # The deliverable-inspection register (testing protocols + result recording). Named
    # DeliverableInspection because scm 4.9 owns the class name QualityInspection.
    "Quality Control (QC) & Inspections": "projects:qci_list",
    # Kaizen / retrospective / maturity + defect trend — a COMPUTED page over the review and defect
    # registers (no stored maturity table) — the 7.3 capacity_demand / 7.5 risk_analysis precedent.
    "Continuous Improvement":            "projects:quality_improvement",
    # The acceptance board — a COMPUTED page over plans + inspections + open defects (the punch
    # list). Acceptance is a verb + a core.Document, not a new store (Ruling 4).
    "Deliverable Acceptance & Sign-off":  "projects:quality_acceptance",
    # Extra live leaves: the whole review register and the defect/punch-list register.
    "Quality Review Register":           "projects:qrv_list",
    "Defect & Punch List":               "projects:qdf_list",
},
```

Bullets 4 and 5 map to computed pages on purpose — the maturity score and the acceptance board are
*aggregations over the registers*, and 7.3's `capacity_demand` / 7.5's `risk_analysis` already
established the "computed board" precedent. If the pass wants fewer pages, bullet 4 can degrade to
`projects:qrv_list?kind=improvement` and bullet 5 to `projects:qci_list?inspection_type=acceptance`
(both supported by the pre-scoped lenses).

**Seeder sketch (`_quality`, own guard):** per tenant — for each seeded active project: 3–5
`QualityPlan` rows anchored to existing WBS **deliverable** nodes, spanning all `verification_method`
values and both `standard_reference` populated/blank, one `approved` (stamped) and one `superseded`;
4–6 `QualityReview` rows spanning all `review_type` values (one `methodology_review` reported, one
`kaizen_event` with an `improvement_action`/owner/due date, one `maturity_assessment` with a
`maturity_score`); 5–8 `DeliverableInspection` rows spanning all `result` and `usage_decision`
values, including one **acceptance** inspection with `accepted_by`/`accepted_by_party`/`accepted_at`
stamped and a `core.Document` certificate, and one `conditional` acceptance with open punch-list
defects; 6–10 `QualityDefect` rows across all severities/categories/dispositions, one resolved
(stamped) and linked to a `ProjectIssue` via `qdf_raise_issue`, one overdue to show the flag, one
with a non-empty `lessons_learned`. `--flush` deletes children-first:
`QualityDefect, DeliverableInspection, QualityReview, QualityPlan`.

---

## Belongs to sibling sub-modules (parked, not scoped here)

- **The enterprise QMS — NCR, CAPA, audit programme, goods/production inspection, calibration,
  supplier quality, SPC** → **scm 4.9 (as-built)** and the future **12.x QMS** (`apps/quality`,
  roadmap). 7.6 builds none of them (Ruling 1). **The #1 overlap risk:** a project deliverable
  failure that is a genuine enterprise nonconformance should eventually raise an
  `scm.NonConformance`, but that table has no project FK today — the bridge is deferred. **Flag
  for the 12.x session** and, when 4.9 grows a project link, add a one-line FK.
- **Goods receipt inspection, receipt tolerance policy, discrepancy claims, return-to-vendor** →
  **6.12 `procurement`** (`ReceiptTolerancePolicy`, `ReceiptDiscrepancy[RDS-]`,
  `ReturnToVendor[RTV-]`).
- **The warehouse-floor QC gate (per-product/per-vendor checklists, QC routing, quarantine,
  floor defect log)** → **5.15 `inventory`** (`QcChecklist`, `QcRoutingRule`, `QuarantineOrder[QRD-]`,
  `DefectReport[DEF-]`).
- **The schedule phase gate (entry/exit criteria, go/no-go)** → **7.2 `ProjectMilestone`**
  (`is_phase_gate`, `mst_achieve`). 7.6's gate is deliverable acceptance (Ruling 5).
- **The project issue register, escalation, risk register** → **7.5**. 7.6's defect links to
  `ProjectIssue` (Ruling 2); it never re-declares it.
- **Scope change / the CCB / requirements traceability** → **7.7**. Acceptance criteria are
  quality criteria, not requirements (the requirements document is 7.7's).
- **Meeting minutes, retrospectives-as-ceremony, team health** → **7.9** (minutes) and **7.13**
  (sprint retros). 7.6 owns the improvement *record* only (Ruling 6).
- **The document repository, knowledge base, lessons-learned store, document retention** → **7.10**.
  The acceptance certificate is a `core.Document`; the lessons repository is 7.10's (Ruling 4/6).
- **Portfolio/program quality roll-ups, cross-project quality heat maps** → **7.12**.
- **Dashboards, charts, report builder, PDF generation, exports** → **7.16**. 7.6 renders grids,
  tables and colour badges; the acceptance-certificate PDF and the defect-trend *chart* are 7.16's.
- **Workflow, approval ladders, e-signature, auto-scheduling, notifications/reminders** → **7.17**.
  7.6's verbs write `core.AuditLog` and surface in-page queues only.
- **Standards/regulatory-clause master, checklist library, methodology templates, custom fields,
  KPI definitions** → **7.19 Master Data & Configuration** (and 7.10 for the repository). The
  standard reference is free text this pass (Ruling 3).
- **External integrations (Jira/Xray/Zephyr/TestRail sync, GRC)** → **7.18**.
- **The GL and the ledger** → **2.x**. 7.6's quality cost is a 7.4 `ProjectExpense`; the ledger is
  accounting's (L29/Ruling 7).

---

## Deferred (later passes / integrations)

| Area | Why deferred |
|---|---|
| **The enterprise NCR / CAPA / audit programme / calibration** | scm 4.9 owns them today; 7.6 is project-scoped (Ruling 1). A defect→`scm.NonConformance` bridge waits on a project FK on that table — **flag for 12.x**. |
| **Test-step child table (steps + expected outcomes, shared steps/parameters)** | Azure Test Plans' differentiator; the protocol `description` is the honest stand-in this pass. |
| **Test configurations / parameterised test data (OS/browser/data sets)** | Needs a configuration-matrix model; not table-stakes for a small ERP. |
| **A reusable standards / regulatory-clause library** | Master data → 7.19; the standard reference is free text (Ruling 3). |
| **A reusable checklist library + methodology templates** | Master data → 7.19; the per-review checklist is a text field. |
| **Automated test execution / CI integration (qTest Launch, pipelines)** | Integration → 7.18. |
| **Recurring audit schedules, auto-escalation, review reminders** | No scheduler/mail worker (7.1/6.8/6.19 recorded it); 7.17's. Badges and audit rows only. |
| **Configurable approval ladders + electronic signature (21 CFR Part 11)** | A workflow-engine feature → 7.17; scm 4.9 parked the identical item. |
| **A stored process-maturity score / assessment table** | A computed page this pass (Ruling 6) — a stored score goes stale the instant an input changes. |
| **Acceptance-certificate PDF generation / report builder / exports** | 7.16 (BI/reporting). 7.6 renders a printable acceptance page. |
| **Defect escape rate / rework rate KPIs** | KPI definitions are master data (7.19) and values need a metrics engine; defect counts stand in. |
| **Acceptance → milestone billing / handover workflow** | 7.15 (billing) / 7.14 (handover); 7.6 records the acceptance only (no GL — Ruling 7). |
| **External test-management / GRC sync (Jira/Xray/Zephyr/TestRail, ServiceNow)** | Integration → 7.18; a `source_number`-style soft reference would be the pattern. |
| **Cross-project / portfolio quality roll-up** | 7.12 (portfolio). |

---

## House-rule constraints discovered (numbered lessons that apply)

Quoted from `.claude/tasks/lessons.md`, the rules this pass must obey:

- **L31 — one sub-module per run.** *"the unit of 'next' is the sub-module; CLAUDE.md's Module
  Creation Sequence … runs per sub-module, scoped to that one `N.M`."* 7.6 builds its **own new
  tables only**.
- **L28 (verify the spine) — *"before writing any code that FKs into or queries a spine entity,
  confirm it exists … the agents' `NavERP-ERD.md`/`NavERP.md` describe the intended spine, not the
  built one."*** Every FK above was grep-verified at its real file/line; **the task's premise that
  the enterprise QMS tables are unbuilt was corrected against the code** (`scm` 4.9 ships them).
- **L29 — *"the AR/AP ledger … do NOT build a second ledger or a stand-in."*** 7.6 ships no money
  column and no journal (Ruling 7).
- **L36 — *"the module that ships FIRST owns the shared entity … the later module EXTENDS by FK,
  never re-declares — a second parallel schema for the same concept is the bug L29 forbids."*** 7.6
  FKs `Project`/`ProjectTask`/`ProjectMilestone`/`ProjectRisk`/`ProjectIssue` **by string**, and
  **re-declares none of scm 4.9's NCR/CAPA/QA/QC** (Ruling 1). The class name `QualityInspection`
  is deliberately avoided (`DeliverableInspection`).
- **L7 — *"the contract handed to parallel agents must pin EVERY context key a template
  consumes."*** The 7.6 contract must pin the four registers' context vars, both computed pages'
  context, and every `*_choices`.
- **L8 — *"assert each detail page's rendered HTML contains the object's identifier."*** Tests
  assert `str(obj)` tokens.
- **L11 — *"Integer FK list filters must validate input before `.filter(fk_id=…)`."*** Guard the
  registers' `project`/`wbs_node`/`owner`/`inspection`/`plan` filters with `if value.isdigit()`.
- **L9 / L10 —** guard pagination and user-FK display — every register renders nullable user FKs
  (`owner`, `inspector`, `reviewer`, `accepted_by`, `resolved_by`).
- **L2 — *"Multi-line `{# … #}` comments leak as visible text. Use `{% comment %}`."***
- **L3 —** the `test_quality_views` pass must assert no comment-marker leak.
- **L33 — *"the design system uses a FIXED, colour-named palette per component … badges
  `badge-green/red/amber/info/muted/slate`."*** Severity/result/acceptance badges use colour-named
  classes and copy a sibling's ternary verbatim — run `grep -n '\.badge-' static/css/theme.css`
  **before** writing them.
- **L27 — *"privileged/workspace-config writes use `@tenant_admin_required`."*** `qpl_supersede`
  is tenant-admin; the rest are `@login_required`.
- **L35 — *"A hand-parsed POSTed `Decimal` amount needs a FULL guard chain."*** 7.6 ships no
  Decimal input; any `?project=` / `?inspection=` GET is parsed through a `forms.Form`
  (`IntegerField`) or `as_db_int`, never raw `request.GET`.
- **L16 — *"Date-equality tests flake on the UTC-offset window (use Django's `timezone`)."***
  `review_date`/`planned_date`/`identified_date`/`is_overdue` all use `timezone.localdate()`.

**Verified spine summary for the todo agent:** `projects.Project` (`Projects.py:27`),
`projects.ProjectTask` (`ProjectTasks.py:22`, `node_type="deliverable"`), `projects.ProjectMilestone`
(`ProjectMilestones.py:17`), `projects.ProjectRisk` (`ProjectRisks.py:34`), `projects.ProjectIssue`
(`ProjectIssues.py:29`), `projects.ProjectStakeholder` (`ProjectStakeholders.py:24`), `core.Party`,
`core.Document`, `core.Activity`, `core.AuditLog`, `AUTH_USER_MODEL`. **No `QualityPlan`/`QualityReview`/
`QualityDefect`/`DeliverableInspection` class exists**; **`scm` 4.9 owns `NonConformance`/`CapaAction`/
`QualityAudit`/`QualityInspection` and is not re-declared**; `inventory` 5.15 owns `QcChecklist`/
`DefectReport`; `procurement` 6.12 owns the receipt-inspection tables.
