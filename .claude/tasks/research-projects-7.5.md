# Research — Sub-module 7.5: Risk & Issue Management (Module 7 — Project Management, `projects`)

> **Read this first.** 7.5 is the module's **uncertainty engine**: it turns 7.1's chartered project,
> 7.2's WBS/schedule, 7.3's resourced team and 7.4's budget/EVM position into a *registered, scored,
> responded-to, escalated and monitored* risk-and-issue position. It is the sub-module 7.1's
> `ProjectRequest` docstring explicitly promised the probabilistic work to (*"Deliberately NOT Monte
> Carlo — the probabilistic simulation is 7.5 Risk & Issue Management's"*), and the sub-module that
> **sizes** the `CostControlAccount.contingency` 7.4 already ships a column for.
>
> It is **not** quality/defect/CAPA management (**7.6**), **not** scope change requests / the CCB
> (**7.7**), **not** task execution or blocked-task workflow (**7.8**), **not** the document
> repository / knowledge base / lessons-learned *repository* (**7.10**), **not** portfolio/program
> risk rollup (**7.12**), **not** dashboards/BI/charts (**7.16**), **not** the notification/workflow
> engine (**7.17**), and **not** the reusable-template / taxonomy master data layer (**7.19**).
>
> **The two failure modes for this pass:**
> 1. **Building a second escalation/workflow engine.** 6.3 already ships `procurement.EscalationPolicy`
>    + an idempotent Run engine (verified at `apps/procurement/models/ApprovalWorkflowEngine/Escalations.py:31`)
>    that raises alerts for idle approval chains. 7.5's bullet-4 escalation is **project-issue-scoped**
>    and must be a *recorded path* (levels → role/user targets → resolution), not a configurable
>    policy engine. See **Ruling 1**.
> 2. **Building a second knowledge store.** NavERP 7.10's bullet 4 is literally *"Knowledge Base &
>    Lessons Learned — searchable repository of past project insights, playbooks, and
>    retrospectives."* 7.5's bullet-5 "lessons learned integration" must therefore be a **field on a
>    closed risk/issue**, never a new `LessonsLearned` table. See **Ruling 3**.

---

## Repo state checked first

### LIVE_LINKS built so far in Module 7 (`apps/core/navigation.py`)

`grep -n '"7\.' apps/core/navigation.py` → **`"7.1"` at line 1702, `"7.2"` at line 1717, `"7.3"` at
line 1732, `"7.4"` at line 1747. Nothing else.** So 7.1–7.4 are all built and **7.5's sidebar block
will be the fifth Module 7 entry.** The dict that decides "built vs. roadmap" is the source of truth
(L31) — 7.5 is the lowest-numbered unbuilt `7.M`.

### The app exists; 7.1–7.4 are built (verified, not assumed)

```
apps/projects/models/ProjectInitiation/          → ProjectRequest[PRQ], Project[PRJ],
                                                   ProjectStakeholder[PST], ProjectKickoff[PKO]
apps/projects/models/ProjectPlanningScheduling/  → ProjectTask[TSK], TaskDependency[DEP],
                                                   ProjectMilestone[MST], ScheduleBaseline[BSL]
apps/projects/models/ResourceManagement/         → ResourceProfile[RSP], ResourceAllocation[RAL],
                                                   ResourceTimeEntry[RTE]
apps/projects/models/CostManagement/             → ProjectBudgetLine[PBL], BudgetRevision[BVR],
                                                   CostControlAccount[CCA], ProjectExpense[PEX]
```

- **Migrations shipped:** `0001` … `0005_budgetrevision_costcontrolaccount_projectbudgetline_and_more`.
  **7.5's migration is `0006_…`.** (`ls apps/projects/migrations/` verified.)
- **Package convention (all four sub-modules):** `models/ forms/ views/ urls/<SubModule>/<Entity>.py`,
  same file name in all four layers, sub-package `__init__.py` files stay EMPTY, re-exports only in the
  four top-level `__init__.py` files. **7.5's sub-module folder is `RiskManagement/`** in each layer.
- **`models/__init__.py` re-export blocks:** four labelled blocks (`# --- 7.1 …` … `# --- 7.4 …`).
  **7.5 adds a fifth `# --- 7.5 Risk & Issue Management` block.** A missing re-export is a runtime
  `ImportError` for the seeder/tests/admin.
- **URL convention (`apps/projects/urls/__init__.py`):** every first path segment is a **disjoint
  literal** (`budgetlines/`, `revisions/`, `controlaccounts/`, `expenses/`, `resource-profiles/`,
  `allocations/`, …) — **no route uses a converter in its first component**, which is the invariant
  that stops one sub-module shadowing another. 7.5's first segments (`risks/`, `responses/`,
  `issues/`, `escalations/`, `risk-analysis/`, `risk-monitoring/`) are all new literals.
- **Template convention:** `templates/projects/initiation/` (7.1), `planning/` (7.2), `resource/`
  (7.3), `cost/` (7.4), each with lowercase-singular entity folders. **7.5 uses
  `templates/projects/risk/<entity>/{list,detail,form}.html`** (`risk/`, `responseaction/`,
  `issue/`, `escalation/`). `templates/projects/` verified: `cost/ initiation/ planning/ resource/
  overview.html` — **no `risk/` yet.**
- **Tests convention:** `test_<sub>_{models,forms,views,security}.py` + `<sub>_*` fixtures +
  `_<sub>_*` helpers in `conftest.py`. 7.1=`initiation`, 7.2=`planning`, 7.3=`resource`. **7.5 uses
  `test_risk_*` / `risk_*` / `_risk_*`.** `conftest.py` is shared — only append with a full
  unfiltered re-run.
- **Seeder:** `apps/projects/management/commands/seed_projects.py` already splits per-sub-module
  guarded blocks — `_seed_tenant` (7.1), `_planning` (7.2), `_resourcing` (7.3), `_cost` (7.4),
  each idempotent on its own guard. **7.5 adds `_risk` with its own guard** so an already-seeded
  workspace still gets risk/issue rows, and its children-first `--flush` order.
- **The `_base.py` toolkit** (`apps/projects/models/_base.py`): `TenantOwned` (tenant FK +
  created/updated), `TenantNumbered` (per-tenant `number` with the 5-attempt `IntegrityError` retry),
  `q2()` (quantize 2dp + clamp to `MAX_Q2 = 9999999999.99`), `ZERO`. **7.5's money column
  (`cost_impact`) uses `DecimalField(14, 2)` through `q2()` exactly like 7.4.**

### What 7.1–7.4 already recorded FOR 7.5 (do not re-derive)

- **7.1 promised 7.5 the Monte Carlo.** `apps/projects/models/ProjectInitiation/ProjectRequests.py:78-86`:
  *"The documented flat factor behind 'risk-adjusted return': a `high` risk rating discounts the stated
  benefit to 70%. **Deliberately NOT Monte Carlo** — the probabilistic simulation is 7.5 Risk & Issue
  Management's, and shipping a fake one here would be worse than none."* The `RISK_DISCOUNT` map is the
  **documented-constant-map idiom** 7.5's own probability map should copy.
- **`Project.risk_summary`** (`Projects.py:72`) is a charter-level *summary* field — *"the risk register
  is 7.5's"*. 7.5 does **not** move it; it is the narrative beside the register, not the register.
- **`ProjectRequest.RISK_RATING_CHOICES`** (`low/medium/high/critical`) is an *intake screening* rating
  on the demand row, not a register row. 7.5 does not FK it; the register is per-project.
- **7.2 owns the PLAN.** `ProjectTask` docstring: *"no risk rows (7.5's)."* 7.5 anchors risks to
  `ProjectTask` **by string FK** and never edits the WBS.
- **7.3 owns people, no money.** `ResourceProfile` docstring: *"No money columns (rates/cost are 7.4's)"*.
  A *resource/skill-gap* risk is a risk *category* on a 7.5 row, not a 7.3 feature.
- **7.4 shipped the contingency column 7.5 sizes.** `CostControlAccount.contingency` docstring:
  *"The CA-held reserve. **Sized by 7.5**, recorded here."* — see **Ruling 4**.
- **7.4's frozen-row precedent** (`BudgetRevision.is_locked` / `ProjectExpense.is_locked`, edit+delete
  refuse posted/approved rows) is the idiom 7.5 copies for a **realized** risk / **closed** issue.

### Spine entities VERIFIED to exist (grep/read evidence)

| Entity | Verified at | What 7.5 uses it for |
|---|---|---|
| `projects.Project` [PRJ-] | `apps/projects/models/ProjectInitiation/Projects.py:27` | the container every 7.5 row FKs (`project` FK, `related_name="risks"` / `"issues"`); reads `start_date`/`end_date` for the exposure window, `project_manager` for default ownership |
| `projects.ProjectTask` [TSK-] | `apps/projects/models/ProjectPlanningScheduling/ProjectTasks.py:22` | the WBS anchor a risk/issue attaches to (`wbs_node` FK, nullable; same-project `clean()` guard — the `ProjectMilestone.anchor_task` pattern at `ProjectMilestones.py:77-80`) |
| `projects.ProjectMilestone` [MST-] | `apps/projects/models/ProjectPlanningScheduling/ProjectMilestones.py:17` | *not FK'd* this pass — but its `is_late` property + `anchor_task` same-project guard are the two idioms 7.5's `review_date` overdue flag copies |
| `projects.ProjectStakeholder` [PST-] | `apps/projects/models/ProjectInitiation/ProjectStakeholders.py:24` | **the escalation target source.** Carries `raci_role`, `raci_scope`, `influence`/`interest`, and `get_engagement_strategy_display()` — an escalation target *role* ("Program Manager", "Executive Sponsor") is grounded in the stakeholder grid rather than invented; 7.5 renders a lens, does not re-declare it |
| `projects.ResourceProfile` [RSP-] | `apps/projects/models/ResourceManagement/ResourceProfiles.py:19` | *not FK'd* — resource/skill risk is a `category="resource"` value, and the named owner stays `AUTH_USER_MODEL` (the register's owner is a login, not a pool row) |
| `projects.CostControlAccount` [CCA-] | `apps/projects/models/CostManagement/CostControlAccounts.py:29` | **the contingency target.** `contingency` is sized by 7.5's EMV/Monte-Carlo analysis and recorded on the CCA by 7.4 (Ruling 4). Optional `contingency_account` FK on a risk links a risk to the CA whose reserve it justifies |
| `projects.ProjectExpense` [PEX-] | `apps/projects/models/CostManagement/ProjectExpenses.py:23` | *not FK'd* — a mitigation's **cost** is recorded on the response action; if it becomes a real spend it is a 7.4 `ProjectExpense(source_kind="manual")` (soft cross-reference, never a write) |
| `projects.BudgetRevision` [BVR-] | `apps/projects/models/CostManagement/BudgetRevisions.py:27` | the **cost baseline** the Monte Carlo overrun probability is measured against (the project's approved-and-activated revision); read-only lens |
| `projects.ProjectRequest` [PRQ-] | `apps/projects/models/ProjectInitiation/ProjectRequests.py:25` | **the promise of Monte Carlo** (docstring) + the `RISK_DISCOUNT` constant-map idiom. *Not FK'd* — the register is per-project, not per-request |
| `projects.ScheduleBaseline` [BSL-] | `apps/projects/models/ProjectPlanningScheduling/ScheduleBaselines.py:24` | *not FK'd* — its **frozen-row verb idiom** and **one-active-per-project atomic verb** are the patterns 7.5's realization/closure guards copy |
| `core.Party` | `apps/core/models/Party.py:5` | *available, not needed this pass* — a risk owner is an internal login; an **external** owner (a supplier carrying a transferred risk) would be a `Party` on the response action (nullable, deferred) |
| `core.OrgUnit` | `apps/core/models/OrgUnit.py:5` | *not FK'd* — the project already carries `org_unit`; a risk inherits it through `project` |
| `core.Document` | `apps/core/models/Document.py:5` | the GFK attachment store — a risk assessment report / evidence PDF attaches to a risk **via `core.Document`**, no second attachment table (the 7.1 charter ruling) |
| `core.Activity` | `apps/core/models/Activity.py:5` | the GFK task/meeting/note store — a mitigation follow-up **action item** could be a `core.Activity`; 7.5 keeps its own `RiskResponseAction` for the *risk-native* action, and links out (no M2M, the `ProjectKickoff` no-M2M ruling) |
| `core.AuditLog` | `apps/core/models/AuditLog.py:5` | escalate / realize / resolve / close evidence. **`action` is varchar(10)** — verbs 7.5 writes: `create/update/delete/escalate/realize/resolve/close/reopen` (all ≤ 10 chars; detail in `changes`) |
| `accounting.Currency` | `apps/accounting/models/GeneralLedger/Currencies.py:6` | **GLOBAL table, no tenant column (L29)** — the one FK that must stay unscoped. One currency per risk's `cost_impact` (or per project); sums at face value, nothing converted |

### Spine entities VERIFIED NOT to exist (grep evidence)

1. **No risk/issue model anywhere.** `grep -rn "^class \(Risk\|Issue\|RiskRegister\|ProjectRisk\|RAID\|
   LessonsLearned\|RiskResponse\|RiskAssessment\|IssueEscalation\|EscalationPath\|RiskCategory\)" apps/`
   → **empty.** Bullet 1's register, bullet 3's response, bullet 4's issue and escalation all need new tables.
2. **No Monte Carlo / simulation / EMV table.** Nothing named `Simulation`/`MonteCarlo`/`RiskRun`/
   `EMV` exists. (This is why **Ruling 2** recommends a computed page, not a table.)
3. **No lessons-learned table.** `grep -rin "lessons.learned\|class.*Lesson" apps/` → no model. 7.10's
   bullet 4 is the owning feature; `core.Document` + `core.Activity` already exist as the store.
4. **No risk taxonomy master in `core`.** `core` owns `Party/PartyRole/OrgUnit/Activity/AuditLog/
   Document/Employment/Tenant` only (grep-verified). A taxonomy is a **choices vocabulary** this pass
   (Ruling 6); the reusable **checklist/template library** for "common project types" is 7.19's
   (`Project.methodology` docstring already says *"the reusable template LIBRARY behind this is 7.19"*).
5. **A generic escalation engine EXISTS in 6.3.** `procurement.EscalationPolicy`
   (`apps/procurement/models/ApprovalWorkflowEngine/Escalations.py:31`) + its Run engine raise
   `ProcurementAlert`s for approval chains idle past a window. It is **procurement-document-scoped**;
   7.5 must not re-declare a policy engine (Ruling 1).
6. **`crm.WorkflowRule`** (`apps/crm/models/AutomationWorkflow/WorkflowRules.py:6`) exists — CRM
   automation, not a project escalation engine. Evidence the repo puts automation rules in the owning
   module; 7.5 does not need one.
7. **No scheduler / mail worker** (recorded by 7.1/6.8/6.19). Review-due and escalation-overdue
   signals are badges and audit rows, not notifications — the notification engine is **7.17**'s.

### Naming-collision & prefix check (performed, not assumed)

- **Prefixes:** the full repo-wide inventory of `NUMBER_PREFIX = "…"` was dumped. **`RSK`, `RRA`,
  `ISS`, `ESC` are all free** (`grep -rl 'NUMBER_PREFIX = "<X>"' apps/` → 0 files each). Near-misses
  checked and clear: `RSP` is **taken** (7.3 `ResourceProfile`), `RPL`, `RSV`, `RPT`, `RA`, `RAL`,
  `RAM` are taken — none of 7.5's four touches them. `CR` (scm.ComplianceRequirement) and `PRJ` ×3 are
  the standing squats; avoided.
- **Class names:** no `ProjectRisk`/`RiskResponseAction`/`ProjectIssue`/`IssueEscalation` (or near-miss
  `Risk`/`Issue`/`RiskRegister`/`RAIDLog`/`Escalation`) exists anywhere in `apps/`.
- **URL stems:** `risks/`, `responses/`, `issues/`, `escalations/`, `risk-analysis/`,
  `risk-monitoring/` are unused under `apps/projects/urls/`.
- **Templates:** `templates/projects/risk/` does not exist yet.
- **Tests:** `test_risk_*` / `risk_*` / `_risk_*` does not collide with `test_initiation_*`,
  `test_planning_*`, `test_resource_*` (or the 7.4 `cost_*` namespace).
- **Migration:** next incremental is `0006_…` (7.4 shipped `0005`).

---

## THE RULINGS — boundaries 7.5 must set before anyone else does

### Ruling 1 — 7.5 owns the risk & issue registers; the escalation *engine* is 6.3's / 7.17's

The market splits two things the word "escalation" conflates:

- a **configurable escalation policy** (auto-raise to role X after N days, SLA timers, routing rules) —
  which is a *workflow engine* feature; and
- a **recorded escalation path** (this issue went level 1 → level 2 → level 3, to these people, for
  these reasons, resolved here) — which is *register data*.

**Decision: 7.5 ships the second, never the first.** The escalation path is realized by
`IssueEscalation` rows (level number + target role + named target + reason + outcome) that record the
path as it happens, plus the *current* level/target denormalized onto `ProjectIssue` for the register
lens. A tenant-configurable **escalation matrix** (level → role → response time, auto-escalate on
breach) is **7.17 Workflow & Automation's**; the generic approval-chain policy engine already exists at
`procurement.EscalationPolicy` (6.3) and 7.5 does not duplicate it. This is the same shape as 7.4's
Ruling 5 (`procurement.CostForecast` is workspace spend, 7.4's EAC is project-scoped — same word,
different object).

### Ruling 2 — Monte Carlo is a COMPUTED page over the register, never a stored simulation table

**Decision: 7.5 owns the Monte Carlo as a POST-only computed view (deterministic, seeded, no table).**
Justification:

- 7.1's docstring promised 7.5 the simulation; the *honest* realization is a computation over the
  register, not a snapshot. A stored `RiskSimulation` table would go **stale the instant a risk's
  probability or impact changes** — the same argument 7.4 used for "EVM metrics are derived, never
  stored columns" (`CostControlAccounts.py:6-8`).
- The register **is** the model. Every tool surveyed recomputes: Primavera Risk Analysis is
  file-based and re-runs the simulation on demand (it only *snapshots reports*); Deltek Acumen re-runs
  the Monte Carlo each analysis. The register rows are the source of truth.
- The computation is cheap (hundreds of risks × ~1,000 iterations is sub-second in pure Python), so
  caching buys nothing.
- **Determinism matters and is cheap:** the run uses `random.Random(seed)` with a **seed the user can
  fix** (Pertmaster's "lock the random seed for reproducible comparison runs"). The page shows the seed
  and accepts `?seed=`, so a re-run is byte-identical.
- **No numpy.** Stdlib `random` + `statistics` only — the repo has no scientific-Python dependency and
  adding one for one page is over-scope.
- **Latin Hypercube Sampling, correlation, decision trees, convergence auto-stop are deferred**
  (Pertmaster/Safran-grade). Simple random sampling is the documented simplification, the same class as
  7.2's longest-chain critical path and 7.4's linear-PV.
- **Charts are 7.16's.** 7.5 renders the result as a **confidence table** (P10/P50/P80/P90/mean exposure)
  and the matrix as an **HTML grid**, not a chart library — the 7.4 "badges and tables, not charts" rule.

If a tenant later needs period-over-period simulation history, an `RiskSimulationSnapshot` table is the
**first thing to add** (Deferred) — but it is a report cache, not the model.

### Ruling 3 — "Lessons learned" is a FIELD on a closed risk/issue, NOT a second knowledge store

NavERP 7.10's bullet 4 (*"Knowledge Base & Lessons Learned — searchable repository of past project
insights, playbooks, and retrospectives"*) **owns the lessons-learned repository.** `core.Document`
(GFK attachment store) and `core.Activity` (GFK note/task store) already exist.

**Decision: 7.5 adds a `lessons_learned` TextField to `ProjectRisk` and `ProjectIssue`** — the
PMBOK-grade *risk-register-native* lesson ("what we learned closing THIS risk/issue") — and **builds no
lessons table, no risk library, no checklist table.** Bullet 5's "lessons learned integration" is
realized as: (a) the field on the closed row, (b) a lens listing closed rows with non-empty lessons,
and (c) a link to 7.10's repository for the cross-project artifact. The **reusable risk library**
(Oracle Primavera's *"workspace-level library of reusable risks"*) and the **checklists for common
project types** (bullet 1) are **7.19 Master Data & Configuration's** template library — parked, not
scoped here. This is the same "first sub-module that needs it defines it, the owner keeps the store"
rule 7.4 applied to EVM definitions.

### Ruling 4 — Contingency is *sized* by 7.5, *stored* by 7.4

`CostControlAccount.contingency` (`CostControlAccounts.py:54-57`) says in as many words: *"The CA-held
reserve. **Sized by 7.5**, recorded here."* **Decision: 7.5 computes and displays the risk-based
contingency (EMV total and the P80-minus-deterministic delta) on the analysis page, and the user
records the agreed figure on 7.4's `CostControlAccount`.** An optional `contingency_account` FK on
`ProjectRisk` links a risk to the CA whose reserve it justifies (read-only lens; the write to
`contingency` stays 7.4's — one writer per column). **No automated write verb this pass** — that is a
cross-sub-module write and is deferred until 7.4's contract invites it (the 7.4→7.3 re-check pattern).

### Ruling 5 — Schedule risk is *recorded* by 7.5, *simulated* by nobody this pass

7.2's critical path is a **documented simplification** (longest chain), not a probabilistic scheduler.
A real schedule-risk simulation (three-point duration estimates per activity, discrete risk events
mapped to activities, a P80 finish date) needs a CPM engine and per-activity uncertainty that **7.2 does
not ship.** **Decision: 7.5 records `schedule_impact_days` on a risk** (the estimated delay if it fires)
and rolls it up as an exposure figure; it does **not** simulate against the WBS network. Quantified
schedule-risk integration with 7.2 is deferred until 7.2 grows activity uncertainty (Deferred).

### Ruling 6 — The risk taxonomy is a choices vocabulary this pass; the checklist/template library is 7.19's

Bullet 1 names *"risk taxonomy, brainstorming tools, and checklists for common project types."* A
`RiskCategory` **table** would be master data (tenant-editable taxonomy) — that is 7.19's territory (the
same reason `Project.methodology`'s template library is 7.19's). **Decision: `category` is a
`CharField(choices=…)`** with the market-standard set (technical / schedule / cost / resource /
external / organizational / quality / compliance / other), **not a table.** A tenant-editable taxonomy
and the per-project-type checklists are 7.19 (Deferred). "Brainstorming tools" (a facilitated capture
session) is a **form + a bulk-add view**, not a model.

---

## Leaders surveyed (with source links)

The domain is **project risk & issue management** — from Monte-Carlo schedule/cost engines (Primavera,
Acumen) through enterprise GRC risk registers (Riskonnect ARM, LogicManager) to the RAID-log
configuration inside generic PM tools (Jira, Smartsheet, monday.com, Wrike), plus the **practice
standard** (ISO 31000 / PMBOK) that supplies the vocabulary all of them use.

1. **Oracle Primavera Cloud Risk Management** — the enterprise reference for the **risk register +
   quantitative analysis in one product**: risks carry *"descriptions, status, probabilities, impacts,
   and other information"*, scored against **project/program risk criteria**, with **risk response
   actions** and *post-response contexts*, a **workspace-level library of reusable risks**, and a
   **Monte Carlo** producing probability curves + a cost/schedule **scatter plot** + Joint Confidence
   Level. <br>
   [Risk Overview (Oracle docs)](https://docs.oracle.com/cd/E80480_01/English/user_guides/risk_management_user_guide/88293.htm) ·
   [Risk Analysis Prerequisites (Oracle docs)](https://docs.oracle.com/cd/E80480_01/English/user_guides/risk_management_user_guide/93538.htm)
2. **Oracle Primavera Risk Analysis (formerly Pertmaster)** — the **Monte Carlo engine** reference:
   qualitative register + quantitative simulation, three-point duration estimates, discrete risk events
   (Bernoulli/Binomial/Poisson), **Latin Hypercube**, **5,000–10,000 iterations**, **locked random
   seed**, S-curves (P50/P80/P90), **tornado charts**, **criticality index**, pre- vs post-mitigation
   comparison, and **contingency = P80 − deterministic**. <br>
   [Primavera Risk Analysis: Practitioner's Guide to QSRA (IQRM)](https://iqrm.net/blog/primavera-risk-analysis) ·
   [Primavera Risk Analysis (Ten Six)](https://tensix.com/primavera-risk-analysis/)
3. **Riskonnect Active Risk Manager (ARM)** — the enterprise GRC register: **risk registers across
   projects/programs/portfolios**, **heat maps**, **bowtie cause-and-effect analysis**, **schedule and
   cost impact analysis** (Monte Carlo), **risk assessments**, customizable **KRIs/KPIs**, and
   ISO 31000 / COSO / PMBOK framework alignment. <br>
   [Active Risk Manager (Riskonnect)](https://riskonnect.com/solutions/active-risk-manager/)
4. **Deltek Acumen Risk** — the **cost-schedule risk** reference: an **integrated risk register of
   discrete risk events**, each with a **probability indicator** and **cost risk impact** /
   **schedule risk impact**; scored as *"probability + whichever of cost/schedule impact is higher"*,
   color-coded; **3-point impacts** (min/most-likely/max); risks mapped to activities feed a Monte Carlo
   engine; up to 10 user-defined fields. <br>
   [Risk Register (Risk Events) — Deltek Acumen 8.6](https://help.deltek.com/Product/Acumen/8.6/GA/Risk%20Register%20Risk%20Events.html) ·
   [The Risk Analysis Process — Deltek Acumen](https://help.deltek.com/Products/Acumen/8.6/GA/The%20Risk%20Analysis%20Process.html)
5. **Jira (native risk issue type + Risk Register apps)** — the mass-market **RAID-in-your-tracker**
   reference: a `Risk` issue type with **Likelihood** (Rare/Unlikely/Possible/Likely/Almost Certain),
   **Impact** (Insignificant→Severe), **Risk Owner**, a status workflow, **issue links to mitigation
   tasks**, and — in the dedicated apps — **automatic scoring (probability × severity)**, **pre- and
   post-mitigation (residual) tracking**, a **traceability table**, and a colour-coded **risk matrix**. <br>
   [How to Track Risks in Jira (Atlassian Community)](https://community.atlassian.com/forums/App-Central-articles/How-to-Track-Risks-in-Jira-A-Practical-Guide-for-Regulated-Teams/ba-p/3221040) ·
   [Risk Register app (Atlassian Marketplace)](https://marketplace.atlassian.com/apps/1213146/risk-register)
6. **Smartsheet / monday.com risk registers** — the **spreadsheet-register** reference and the source
   of the field list most teams actually use: **Risk ID, description (If…then), category, probability
   (1–5), impact (1–5), risk score = P×I, risk owner, mitigation action, contingency plan, trigger,
   status (Open/In Progress/Mitigated/Closed), review date**, a **risk matrix**, and explicit
   **escalation criteria** (impact thresholds, time triggers, resource needs). <br>
   [Risk register template guide (monday.com)](https://monday.com/blog/project-management/risk-register-template/) ·
   [Program Risk Register template (monday.com)](https://monday.com/templates/program-risk-register) ·
   [Risk register templates (Smartsheet)](https://www.smartsheet.com/risk-register-templates)
7. **nTask** — the **dedicated risk module on a budget** reference: a native risk register with
   **categories and statuses**, a **likelihood/impact matrix with priority levels**, **risk owners with
   due dates and alerts**, and **mitigation steps as tasks with assignees**. <br>
   [Top software for project risk management (EatSip365)](https://eatsip365.com/top-software-for-project-risk-management)
8. **Wrike** — the **configurable RAID-log** reference: risk intake folders, **custom workflows for
   RAID logs**, **custom fields for impact scores**, dashboards for high-risk/overdue items, and
   **automation rules** for reminders and escalations. <br>
   [Best Project Risk Management Software (GD TopCon)](http://www.gdtopcon.com/best-project-risk-management-software.html) ·
   [Best PM tools for risk management (ONES)](https://ones.com/blog/tool-guide/best-project-management-tools-for-project-risk-management-4)
9. **Planview** — the **portfolio-risk** reference: risk scored **across dimensions** (technical,
   commercial, cost, strategic fit), **risk vs. reward** and **pipeline** views, **risk tolerance**
   framing, and the warning against collapsing risk into one number. (Its lesson: keep risk a *separate*
   dimension, not a discount baked into a score — which is why 7.1's flat `RISK_DISCOUNT` is explicitly
   not the register.) <br>
   [Manage Risks, But Don't Eliminate Them (Planview)](https://blog.planview.com/manage-portfolio-risks/)
10. **ISO 31000 / PMBOK practice standard** (not a product — the vocabulary source) — the process
    (establish context → identify → analyse → evaluate → treat → monitor & review, with communication &
    consultation throughout); the **five treatment strategies** (avoid / reduce-mitigate / transfer-share
    / accept / **exploit** for opportunities, + PMBOK's **escalate**); **residual risk**; **risk
    appetite vs. tolerance**; **EMV = probability × impact**; the **risk register**, **risk owner**, and
    **lessons-learned register**. <br>
    [ISO 31000 process guide (NovelVista)](https://www.novelvista.com/blogs/quality-management/iso-31000-risk-management-process) ·
    [Risk mitigation: the five response strategies + EMV + scoring bands (RiskPublishing)](https://riskpublishing.com/risk-mitigation-in-project-management/) ·
    [Lessons-learned register (PM Study Circle)](https://pmstudycircle.com/lessons-learned-register/)
11. **Escalation-matrix practice (ProjectManager.com)** — the **levels/roles/targets/triggers** source:
    escalation **levels 1–4** (Team Lead → PM → Program Manager → Executive Sponsor), **priority levels**
    (Critical/High/Medium/Low), **escalation triggers** (time-based SLA, budget variance >10%, schedule
    slip >3 days on the critical path, safety, client complaint), a **contact matrix** (role + backup),
    and a **workflow** (identify → log → assign severity → attempt L1 → escalate on SLA breach → track →
    close & document). <br>
    [Escalation matrix guide (ProjectManager.com)](https://www.projectmanager.com/blog/escalation-matrix)

**Practice references also read:** PMI's **risk burndown** (cumulative **probability × impact** risk
score plotted over time — *"risk trends and the change in risk scores over time are comparable [across
teams]"*) — [Risk Burndown Charts (PMI)](https://www.pmi.org/disciplined-agile/agile/riskburndown).

**Considered and not cited:** *LogicManager* / *LogicGate Risk Cloud* / *InEight* surfaced GRC/ERM or
capital-project pages that added no field the eleven above do not already evidence (they are enterprise
GRC/ERM, a different buyer than one project's register); *Asana* / *ClickUp* / *Airtable* are generic
work tools with no risk-native model (the ONES comparison confirms they are the "flexible task
customization" tier, not risk governance). Dropped rather than cited second-hand.

---

## Feature catalog (this sub-module only)

Priority key: **table-stakes** (nearly every leader has it) · **common** (most have it) ·
**differentiator** (a few standouts). Spine names are grep-verified per the tables above.

### Bullet 1 — Risk Identification & Register
*"Risk taxonomy, brainstorming tools, and checklists for common project types."*

- **A single per-project risk register** — one row per identified risk, the register every tool is built
  on (Primavera's project risk register, ARM's project registers, Jira's Risk issue type, nTask's risk
  module). · seen in: all eleven · priority: **table-stakes** · spine: **new table `ProjectRisk`** ·
  buildable now.
- **A risk taxonomy as a category vocabulary** — the classification every register carries (monday:
  Technical/Resource/External/Financial; riskpublishing: Schedule/Cost/Resource/Compliance/Technical).
  · seen in: Primavera (criteria), ARM (taxonomy), monday, Smartsheet, nTask · priority:
  **table-stakes** · spine: `category` `CharField(choices=…)` on `ProjectRisk` (technical / schedule /
  cost / resource / external / organizational / quality / compliance / other) — **not a table** (Ruling
  6) · buildable now.
- **Cause → event → effect structure** — the PMBOK "If … then" statement; Smartsheet's registers use
  it verbatim and ARM's bowtie analysis formalizes it. · seen in: Smartsheet, monday, ARM (bowtie) ·
  priority: **common** · spine: `cause` + `effect` TextFields beside `title`/`description` ·
  buildable now.
- **Threat vs. opportunity (two-sided risk)** — ISO 31000 and Primavera both model **threats AND
  opportunities**, not just bad things. · seen in: Primavera, ISO 31000 · priority: **common** ·
  spine: `risk_type` choices (`threat` / `opportunity`) · buildable now.
- **Named human owner (never a team)** — every register guide is emphatic: *"Each risk has a named
  human owner — never a team or department."* · seen in: Primavera, Jira, nTask, all guides · priority:
  **table-stakes** · spine: `owner` FK → `AUTH_USER_MODEL` (nullable, SET_NULL) · buildable now.
- **Provenance & dates** — who raised it and when, plus a **review date** (the register's cadence
  column). · seen in: Smartsheet, monday, Jira, Primavera · priority: **table-stakes** · spine:
  `identified_by` FK, `identified_date`, `review_date` on `ProjectRisk` · buildable now.
- **WBS anchoring** — Primavera requires **activities assigned to a risk** for the impact to propagate;
  the NavERP equivalent is anchoring a risk to a `ProjectTask` node. · seen in: Primavera, Acumen
  (mapping risk events to activities) · priority: **common** · spine: `wbs_node` FK →
  `projects.ProjectTask` (nullable, SET_NULL, same-project `clean()` guard) · buildable now.
- **Checklists for common project types** — bullet 1 names them; Oracle ships a **workspace-level
  library of reusable risks**. · seen in: Primavera (risk library), ARM (risk library) · priority:
  **common** · **deferred → 7.19** (the reusable-template library; `Project.methodology` already points
  there) + 7.10 for the repository · not buildable without a master-data pass.
- **Brainstorming / facilitated capture** — a bulk-entry session. · seen in: practice (workshops) ·
  priority: **common** · spine: a **bulk-add form view** over `ProjectRisk` (no model) · buildable now
  (view).
- **Bowtie cause-and-effect analysis** — ARM's differentiator. · seen in: ARM · priority:
  **differentiator** · **deferred** — needs a cause/control graph model; the `cause`/`effect` text is
  the honest stand-in this pass.

### Bullet 2 — Qualitative & Quantitative Analysis
*"Probability/impact matrices, Monte Carlo simulation, and expected monetary value."*

- **Probability × impact scoring with a defined scale** — the universal qualitative engine: a 1–5
  likelihood × 1–5 impact → a score. monday/Smartsheet use exactly this; Jira's app **automates** the
  score (probability × severity) that native Jira cannot. · seen in: monday, Smartsheet, Jira apps,
  nTask, Primavera · priority: **table-stakes** · spine: `probability` + `impact`
  `PositiveSmallIntegerField` (validators 1–5) with a **derived `score` property** (never stored) ·
  buildable now.
- **Score bands → a severity rating** — the standard bands (riskpublishing: 1–3 Low, 4–7 Medium, 8–14
  High, 15–25 Critical; ITIL-style priority levels). · seen in: riskpublishing, monday, ITIL ·
  priority: **table-stakes** · spine: a **derived `severity_band` property** (low/medium/high/critical)
  + `get_severity_band_display()`-style label helper (the `ProjectStakeholder.get_engagement_strategy_display`
  precedent at `ProjectStakeholders.py:144`) · buildable now.
- **A probability/impact matrix (heat map)** — the visual the bullet names; ARM ships heat maps, Jira
  apps a colour-coded matrix, monday a 3×3. · seen in: ARM, Jira apps, monday, nTask · priority:
  **table-stakes** · spine: a **computed HTML grid** over the register (rows = probability 1–5, cols =
  impact 1–5, each cell = count + colour), rendered on the analysis page — **no chart library, no
  stored matrix** (7.16 owns charts) · buildable now (view).
- **Expected Monetary Value (EMV) = probability × cost impact** — the bullet's third term; the
  deterministic contingency input (*"Informs contingency reserve sizing"*). · seen in: ISO 31000/PMBOK
  practice, all quantitative tools · priority: **table-stakes** · spine: `cost_impact`
  `DecimalField(14, 2)` on `ProjectRisk` + a **documented `PROBABILITY_PCT` map** (the 7.1
  `RISK_DISCOUNT` idiom) → a **derived `emv` property**; the register total is the EMV exposure ·
  buildable now.
- **Schedule-impact recording** — Deltek scores on the *higher* of cost/schedule impact; the register
  needs the schedule figure even if 7.5 cannot simulate it. · seen in: Deltek Acumen, Primavera ·
  priority: **common** · spine: `schedule_impact_days` `PositiveIntegerField` on `ProjectRisk`
  (recorded, not simulated — Ruling 5) · buildable now.
- **Monte Carlo simulation over the register** — the bullet's headline and 7.1's explicit promise. A
  real engine (Primavera, Pertmaster, Acumen, ARM). · seen in: Primavera, Primavera Risk Analysis,
  Deltek Acumen, ARM · priority: **table-stakes (for this bullet)** · spine: a **POST-only computed
  page** — seeded `random.Random`, Bernoulli occurrence per risk × `cost_impact`, N iterations →
  **P10/P50/P80/P90 + mean** rendered as a table, **never a stored table** (Ruling 2) · buildable now
  (view).
- **Pre- vs post-mitigation (residual) scoring** — Jira apps track *both states in the same record and
  calculate residual automatically*; Primavera runs the analysis on both contexts. · seen in: Jira
  apps, Primavera, ARM · priority: **table-stakes** · spine: `residual_probability` +
  `residual_impact` on `ProjectRisk` (and on `RiskResponseAction`) → a **derived `residual_score`**
  · buildable now.
- **Overrun probability against the budget** — Primavera's *"chance of finishing On Time AND Under
  Budget"* / Joint Confidence Level. · seen in: Primavera, ARM · priority: **common** · spine: the
  computed page compares the simulated exposure distribution against the project's **active
  `BudgetRevision`** total (7.4 read-only lens) and reports the **% chance of exceeding it** · buildable
  now (view).
- **Latin Hypercube sampling, risk correlation, decision trees, convergence auto-stop** — Pertmaster/
  Safran-grade. · seen in: Primavera Risk Analysis, Safran · priority: **differentiator** ·
  **deferred** — simple random sampling is the documented simplification; correlation needs a
  correlation matrix model · not buildable this pass.
- **Quantified schedule-risk simulation (3-point durations → P80 finish)** — Primavera/Acumen's core.
  · priority: **differentiator** · **deferred → needs 7.2 activity uncertainty** (Ruling 5) — 7.5
  records `schedule_impact_days` only.

### Bullet 3 — Risk Response Planning
*"Avoid, transfer, mitigate, accept strategies with action owners and triggers."*

- **A response strategy per risk** — the bullet names the four (ISO 31000's T.A.R.A: avoid / mitigate /
  transfer / accept); the standard adds **exploit** (opportunities) and PMBOK adds **escalate**.
  · seen in: ISO 31000, PMBOK, every register template · priority: **table-stakes** · spine:
  `response_strategy` choices (`avoid` / `mitigate` / `transfer` / `accept` / `exploit` / `escalate`)
  on `ProjectRisk` · buildable now.
- **Response ACTIONS with their own owners** — Primavera's *"risk response actions"*, Jira's linked
  mitigation tasks, nTask's *"mitigation steps as tasks with assignees"*. The action owner is
  frequently **not** the risk owner. · seen in: Primavera, Jira apps, nTask, Smartsheet · priority:
  **table-stakes** · spine: **new table `RiskResponseAction`** (child of `ProjectRisk`) with its own
  `owner`, `due_date`, `status` · buildable now.
- **Triggers** — the observable event that activates the response, named in the bullet and in every
  register template (*"Trigger events documented: define observable events in advance so the response
  plan activates automatically"*). · seen in: Smartsheet, monday, riskpublishing · priority:
  **table-stakes** · spine: `trigger` TextField on `ProjectRisk` **and** on `RiskResponseAction`
  (the action's own activation trigger) · buildable now.
- **Contingency plan (what to do if it fires)** — distinct from the mitigation action (preventive vs.
  reactive); every template has both columns. · seen in: Smartsheet, monday · priority:
  **table-stakes** · spine: `contingency_plan` TextField on `ProjectRisk` · buildable now.
- **Mitigation cost** — *"What is the estimated cost of the mitigation?"* is one of the five questions
  a good action answers. · seen in: practice guides, Primavera (post-mitigation cost) · priority:
  **common** · spine: `cost` `DecimalField(14, 2)` on `RiskResponseAction` (recorded; a real spend is
  a 7.4 `ProjectExpense` — soft, Ruling 4/5) · buildable now.
- **Post-action residual estimate** — the *"number the sponsor accepts"*. · seen in: Jira apps,
  Primavera, ARM · priority: **common** · spine: `residual_probability` + `residual_impact` on
  `RiskResponseAction` → derived `residual_score` · buildable now.
- **Action completion tracking** — *"When will it be completed (milestone or date)?"*. · seen in: all ·
  priority: **table-stakes** · spine: `status` (planned / in_progress / completed / cancelled) +
  `completed_at` (stamped by a POST-only `rra_complete` verb) · buildable now.
- **Response-ROI (compare pre/post exposure curves)** — Pertmaster computes the ROI of each action.
  · seen in: Primavera Risk Analysis · priority: **differentiator** · **deferred** — needs two
  simulated contexts per action; the residual columns give the static version this pass.

### Bullet 4 — Issue Logging & Escalation
*"Issue capture, severity classification, resolution tracking, and escalation paths."*

- **A per-project issue register** — the RAID-log "I" (Jira's risk/issue apps, Smartsheet trackers,
  monday boards). · seen in: Jira, Smartsheet, monday, Wrike · priority: **table-stakes** · spine:
  **new table `ProjectIssue`** · buildable now.
- **Severity classification** — the bullet names it; the escalation-matrix practice uses priority
  levels Critical/High/Medium/Low. · seen in: escalation practice, Jira, Smartsheet · priority:
  **table-stakes** · spine: `severity` choices (`critical` / `high` / `medium` / `low`) on
  `ProjectIssue` · buildable now.
- **Issue provenance from a realized risk** — a risk that fires becomes an issue; the RAID log's whole
  point. · seen in: practice (risk → issue), Jira (links) · priority: **common** · spine: nullable
  `risk` FK → `ProjectRisk` (SET_NULL) + a POST-only **`rsk_realize`** verb that marks the risk
  `realized` and creates the linked issue · buildable now.
- **Resolution tracking (who/when/how)** — *"follow the issue from identification through mitigation to
  verified resolution"*; not just a status. · seen in: Jira (lifecycle + evidence), ARM, ProjectManager
  workflow (*"Close and document"*). · priority: **table-stakes** · spine: `resolution_note` TextField,
  `root_cause` TextField, `resolved_by` FK + `resolved_at` stamp (written by a POST-only `iss_resolve`
  verb, never a form field — the 7.4 `decision_notes` rule) · buildable now.
- **A real escalation path (levels / roles / targets)** — the bullet names it and the task requires it.
  Escalation-matrix practice defines **levels 1–4** (Team Lead → PM → Program Manager → Executive
  Sponsor), a **target role + named person + backup**, and **triggers** (SLA breach, cost/schedule
  variance). · seen in: escalation practice, Jira (escalation rules), Wrike (automations) · priority:
  **table-stakes** · spine: **new table `IssueEscalation`** (one row per escalation event: `level`,
  `target_role`, `target_user`, `reason`, `escalated_by`, `escalated_at`, `resolved_at`, `outcome`) +
  the **current** `escalation_level` / `escalated_to` / `escalated_at` denormalized onto
  `ProjectIssue` for the register lens; a POST-only **`iss_escalate`** verb (tenant_admin) appends the
  row and advances the current level · buildable now.
- **Escalation targets grounded in the stakeholder grid** — an escalation target *role* is a
  `ProjectStakeholder` RACI/type fact, not an invented field. · priority: **common** · spine:
  `target_role` is free text this pass, with the `pst_list` register linked as the role reference
  (`raci_scope`/`stakeholder_type`); a FK to `ProjectStakeholder` is deferred (a target may be outside
  the project's own stakeholders) · buildable now.
- **Auto-escalation on SLA breach / configurable escalation matrix** — *"automated escalation with
  role-based access"*, *"escalate if SLA exceeded"*. · seen in: escalation practice, Wrike, Jira ·
  priority: **common** · **deferred → 7.17** (the workflow engine) / 6.3's existing
  `procurement.EscalationPolicy` (Ruling 1) — 7.5 records the path, it does not run timers.
- **Overdue / ageing issue flags** — *"Format Rules — automated visual alerts when a risk has no owner
  or is past its due date"*. · seen in: Jira apps, monday · priority: **common** · spine: derived
  `is_overdue` + `age_days` properties → badges and a `?overdue=1` register lens · buildable now
  (no notification — that is 7.17).
- **External ticketing integration (Jira / ServiceNow sync)** — · priority: **differentiator** ·
  **deferred → 7.18** (integrations); the `source_number`-style soft reference would be the pattern.

### Bullet 5 — Risk Monitoring & Reporting
*"Top-risk dashboards, burn-down of risk exposure, and lessons learned integration."*

- **A top-risk view (the register sorted/banded by exposure)** — *"Filters and dashboards highlight top
  threats"*; the exposure ranking is the register's `score`/`emv` annotation. · seen in: ARM, Primavera,
  Jira, monday · priority: **table-stakes** · spine: a **lens on `rsk_list`** (`?band=critical`,
  ordered by score/EMV) — **no new table** · buildable now (view).
- **Risk exposure burn-down over time** — PMI's **risk burndown**: the **cumulative Σ(probability ×
  impact)** plotted over time, *"how our risk profile is trending"*. · seen in: PMI Disciplined Agile,
  practice · priority: **common** · spine: a **computed monitoring page** aggregating the register's
  exposure by `identified_date`/`review_date` into a period table (CSS bars, **not a chart** — 7.16) ·
  buildable now (view).
- **Review cadence / due-for-review queue** — *"Review at every status meeting … matched to project
  pace"*; the register's `review_date` drives it. · seen in: Smartsheet, monday, ARM · priority:
  **table-stakes** · spine: a `?review_due=1` lens + derived `is_review_overdue` · buildable now.
- **Risk appetite / tolerance threshold** — ISO 31000 §6.4.4: risks are prioritised *against* appetite
  and tolerance; Planview frames tolerance explicitly. · seen in: ISO 31000, ARM, Planview · priority:
  **common** · spine: a **documented constant band map** (the 7.1 `RISK_DISCOUNT` idiom) driving the
  severity badge + an "above tolerance" flag — **not a per-tenant config table this pass** (that is
  7.19; Deferred) · buildable now.
- **Lessons-learned integration** — the bullet's third term. PMBOK's lessons-learned register is
  *updated throughout* and *searched at the start of new projects*. · seen in: PMBOK practice, ARM
  (risk library), Primavera (reusable risk library) · priority: **common** · spine: **`lessons_learned`
  TextField on closed `ProjectRisk`/`ProjectIssue`** + a lens listing closed rows with non-empty
  lessons + a link to 7.10's repository — **NO new table** (Ruling 3) · buildable now.
- **Risk heat map / dashboard for leadership** — ARM heat maps, Primavera dashboards. · priority:
  **common** · spine: the **matrix grid on the analysis page** + colour-coded badges on the register;
  **chart dashboards are 7.16's** · buildable now (grid only).
- **KRI / KPI indicators** — ARM's customizable KRIs/KPIs (leading indicators, not the risk itself).
  · seen in: ARM, ISO 31000 (§ monitoring tracks KPIs/KRIs) · priority: **differentiator** ·
  **deferred** — KRI definitions are master data (7.19) and the KRI *values* need a metrics engine;
  7.5's exposure figures are the honest stand-in.
- **Cross-project / portfolio risk aggregation** — ARM aggregates from project to program to
  enterprise. · priority: **common** · **deferred → 7.12** (portfolio) — the project is the highest
  aggregation this pass builds.

### Beyond the bullets (found in the market, worth recording)

- **A workspace-level reusable risk library** — Oracle's *"library of reusable risks"*, ARM's risk
  library. · priority: **common** · **deferred → 7.10 (repository) / 7.19 (master data)**; Ruling 3.
- **Risk → issue → change-request chain** — a realized risk can drive a scope change. · priority:
  **differentiator** · **deferred → 7.7** — a nullable `source_risk` FK on 7.7's future `ChangeRequest`,
  or a `source_issue` on `BudgetRevision` (7.4 Ruling 3 already parked the CR bridge).
- **Decision-tree / EMV per decision** — Pertmaster. · priority: **differentiator** · **deferred** —
  a decision model is a different object; EMV per risk is the pass's scope.

---

## Recommended build scope (this pass — 4 models)

All four are tenant-scoped `TenantNumbered` subclasses in `apps/projects/models/RiskManagement/` (one
file per entity, same name in `forms/ views/ urls/`), full CRUD (list with working filters + create +
detail + edit + POST-only delete), templates under `templates/projects/risk/<entity>/{list,detail,form}.html`,
re-export block `# --- 7.5 Risk & Issue Management` in `apps/projects/models/__init__.py` (a missing
re-export is a runtime `ImportError`), migration `0006_…`, seeder block `_risk` with its own guard,
tests `test_risk_*`. All money is `DecimalField(14, 2)` through the existing `q2()` clamp; all scores,
bands, EMV and simulation figures are **derived properties / computed views, never stored columns**
(the 7.1 ROI / 7.4 EVM ruling); audit actions ≤ 10 chars.

### 1. `ProjectRisk` [**RSK-**] — *one identified threat or opportunity on one project: its taxonomy,
its qualitative score, its quantitative cost/schedule impact, its response strategy, its owner, its
review cadence, and (when closed) its lesson.*

Covers bullets **1 (Identification & Register)**, **2 (Qualitative & Quantitative Analysis — the
inputs and the EMV)**, **3 (Response Planning — the strategy, trigger and contingency plan)** and
**5 (Monitoring — review date + lessons field)**. The register row is where four of the five bullets
meet, exactly as the market's risk register is one row per risk.

Fields:
- `project` → `projects.Project` CASCADE `related_name="risks"` (the container; read-only parent).
- `wbs_node` → `projects.ProjectTask` SET_NULL null+blank `related_name="risks"` — **same-project
  `clean()` guard** (the `ProjectMilestone.anchor_task` pattern).
- `title` CharField(255); `description` TextField; `cause` TextField blank; `effect` TextField blank
  (the "If…then" structure).
- `category` CharField(max_length=16, choices=…) — `technical / schedule / cost / resource / external /
  organizational / quality / compliance / other` (the market taxonomy; **choices, not a table** —
  Ruling 6).
- `risk_type` CharField(max_length=12, choices=…) — `threat / opportunity` (ISO 31000 two-sided risk).
- `probability` PositiveSmallIntegerField (validators `MinValueValidator(1)`, `MaxValueValidator(5)`);
  `impact` PositiveSmallIntegerField (1–5). **Derived `score = probability * impact`; derived
  `severity_band`** (1–3 `low` / 4–7 `medium` / 8–14 `high` / 15–25 `critical`) + a
  `get_severity_band_display()` helper (the `ProjectStakeholder` label-helper precedent).
- **`PROBABILITY_PCT` documented constant map** `{1: 10, 2: 30, 3: 50, 4: 70, 5: 90}` (the 7.1
  `RISK_DISCOUNT` idiom) → **derived `emv = q2(cost_impact × PROBABILITY_PCT[probability] / 100)`**.
- `cost_impact` DecimalField(14, 2) default `Decimal("0")`, `MinValueValidator(0)` (the monetary
  impact; the EMV and Monte Carlo input).
- `schedule_impact_days` PositiveIntegerField null+blank (recorded, **not simulated** — Ruling 5).
- `response_strategy` CharField(max_length=12, choices=…) — `avoid / mitigate / transfer / accept /
  exploit / escalate` (the bullet's four + ISO 31000's exploit + PMBOK's escalate).
- `response_note` TextField blank; `trigger` TextField blank; `contingency_plan` TextField blank.
- `status` CharField(max_length=16, choices=…) — **`identified / assessing / response_planned /
  monitoring / realized / closed`** (the register lifecycle; `realized` = it happened, `closed` =
  resolved/retired).
- `owner` → `AUTH_USER_MODEL` SET_NULL null+blank `related_name="owned_risks"` (the named human owner);
  `identified_by` → `AUTH_USER_MODEL` SET_NULL null+blank `related_name="raised_risks"`.
- `identified_date` DateField (default `timezone.localdate`); `review_date` DateField null+blank
  (**derived `is_review_overdue`** = review_date passed and not closed).
- `residual_probability` / `residual_impact` PositiveSmallIntegerField null+blank (the post-response
  estimate; **derived `residual_score` / `residual_band`**).
- `contingency_account` → `projects.CostControlAccount` SET_NULL null+blank
  `related_name="risks"` (the CA whose 7.4 reserve this risk justifies — read-only lens; **the write to
  `contingency` stays 7.4's** — Ruling 4).
- `lessons_learned` TextField blank (bullet 5's integration — the closed-row takeaway; **NOT a store** —
  Ruling 3).
- `closed_at` DateTimeField null+blank `editable=False` (stamped by the close verb);
  `created_by` → `AUTH_USER_MODEL` SET_NULL null+blank `editable=False`.

`Meta`: `ordering = ["-created_at", "-id"]`; `unique_together = ("tenant", "number")`; indexes
`("tenant","project")` → `rsk_tnt_project_idx`, `("tenant","status")` → `rsk_tnt_status_idx`,
`("tenant","category")` → `rsk_tnt_category_idx`, `("tenant","risk_type")` → `rsk_tnt_rtype_idx`,
`("tenant","-created_at")` → `rsk_tnt_created_idx` (serves `Meta.ordering` itself — the in-pattern
add on 20+ models).

**Derived properties (all documented, all guarded):** `score`, `severity_band` + display, `emv`,
`residual_score`, `residual_band`, `is_review_overdue`, `exposure` (= `emv`, for the burn-down sum).

**Verbs (POST-only, audited):** `rsk_realize` (login; `monitoring`/`response_planned` → `realized`,
audit `realize`) — **may create the linked `ProjectIssue`** (the risk→issue bridge); `rsk_close`
(login; → `closed`, stamps `closed_at`, audit `close`); `rsk_reopen` (tenant_admin, audit `reopen`).
Closed rows refuse edit/delete (the `ScheduleBaseline`/`BudgetRevision` frozen-row guard).

**FKs (all verified):** `projects.Project`, `projects.ProjectTask`, `projects.CostControlAccount`,
`AUTH_USER_MODEL`.

### 2. `RiskResponseAction` [**RRA-**] — *one planned action against one risk: the strategy it
implements, its own owner, its due date, its cost, its trigger, and the residual it is expected to
leave.*

Covers bullet **3 (Risk Response Planning)** — the bullet's *"action owners and triggers"*; one risk
can carry several actions (Primavera's "risk response actions", Jira's linked mitigation tasks).

Fields:
- `risk` → `projects.ProjectRisk` CASCADE `related_name="response_actions"` (the action is only real
  inside a risk).
- `title` CharField(255); `description` TextField blank.
- `strategy` CharField(max_length=12, choices=…) — same vocabulary as `ProjectRisk.response_strategy`
  (an action implements one strategy).
- `owner` → `AUTH_USER_MODEL` SET_NULL null+blank `related_name="risk_actions"` (the **action** owner,
  distinct from the risk owner).
- `due_date` DateField null+blank (**derived `is_overdue`**).
- `cost` DecimalField(14, 2) default 0, `MinValueValidator(0)` (estimated mitigation cost; a real
  spend is a 7.4 `ProjectExpense` — soft).
- `trigger` TextField blank (the observable event that activates THIS action).
- `status` CharField(max_length=12, choices=…) — `planned / in_progress / completed / cancelled`.
- `residual_probability` / `residual_impact` PositiveSmallIntegerField null+blank (**derived
  `residual_score`**).
- `completed_at` DateTimeField null+blank `editable=False`; `created_by` → `AUTH_USER_MODEL`.

`Meta`: `ordering = ["-created_at", "-id"]`; `unique_together = ("tenant", "number")`; indexes
`("tenant","risk")` → `rra_tnt_risk_idx`, `("tenant","status")` → `rra_tnt_status_idx`,
`("tenant","owner")` → `rra_tnt_owner_idx`, `("tenant","due_date")` → `rra_tnt_due_idx`.

**Verbs:** `rra_complete` (login; → `completed`, stamps `completed_at`, audit `update`/`complete`).

**FKs (verified):** `projects.ProjectRisk`, `AUTH_USER_MODEL`.

### 3. `ProjectIssue` [**ISS-**] — *one captured issue on one project: its severity, its owner, its
target resolution date, its provenance from a risk, its resolution evidence, and its current
escalation level.*

Covers bullet **4 (Issue Logging & Escalation)** — the capture, severity, resolution and current
escalation state.

Fields:
- `project` → `projects.Project` CASCADE `related_name="issues"`.
- `wbs_node` → `projects.ProjectTask` SET_NULL null+blank `related_name="issues"` (same-project guard).
- `risk` → `projects.ProjectRisk` SET_NULL null+blank `related_name="issues"` (provenance: the risk
  that materialized — set by `rsk_realize`).
- `title` CharField(255); `description` TextField.
- `issue_type` CharField(max_length=12, choices=…) — `issue / action_item / decision / other` (the RAID
  log's other letters are 7.2/7.7's; 7.5 keeps the issue-native set).
- `severity` CharField(max_length=8, choices=…) — **`critical / high / medium / low`** (the bullet's
  "severity classification"; the escalation practice's priority levels).
- `status` CharField(max_length=12, choices=…) — **`open / in_progress / blocked / resolved / closed /
  cancelled`**.
- `owner` → `AUTH_USER_MODEL` SET_NULL null+blank `related_name="owned_issues"`;
  `raised_by` → `AUTH_USER_MODEL` SET_NULL null+blank `related_name="raised_issues"`.
- `identified_date` DateField (default today); `due_date` DateField null+blank (**derived `is_overdue`**,
  `age_days`).
- **Escalation (current state — denormalized for the register lens):** `escalation_level`
  PositiveSmallIntegerField default 0 (0 = not escalated, 1–4 = tier); `escalated_to` →
  `AUTH_USER_MODEL` SET_NULL null+blank `related_name="escalated_issues"`; `escalated_at` DateTimeField
  null+blank `editable=False`.
- **Resolution (verb-written evidence, never form fields — the 7.4 `decision_notes` rule):**
  `root_cause` TextField blank; `resolution_note` TextField blank; `resolved_by` → `AUTH_USER_MODEL`
  SET_NULL null+blank `editable=False`; `resolved_at` DateTimeField null+blank `editable=False`.
- `lessons_learned` TextField blank (Ruling 3); `created_by` → `AUTH_USER_MODEL`.

`Meta`: `ordering = ["-created_at", "-id"]`; `unique_together = ("tenant", "number")`; indexes
`("tenant","project")` → `iss_tnt_project_idx`, `("tenant","status")` → `iss_tnt_status_idx`,
`("tenant","severity")` → `iss_tnt_severity_idx`, `("tenant","escalation_level")` →
`iss_tnt_esc_idx`, `("tenant","-created_at")` → `iss_tnt_created_idx`.

**Derived:** `is_overdue`, `age_days`, `is_open`, `severity_badge` (colour-named class dict —
**`badge-red`/`badge-amber`/`badge-green` only**, L33).

**Verbs (POST-only, audited):** `iss_escalate` (**tenant_admin** — appends an `IssueEscalation` row,
increments `escalation_level`, sets `escalated_to`/`escalated_at`, audit `escalate`);
`iss_resolve` (login — stamps `resolved_by`/`resolved_at`, status → `resolved`, audit `resolve`);
`iss_close` (login — `resolved` → `closed`, audit `close`). Resolved/closed rows refuse edit/delete of
the resolution fields (frozen-row guard).

**FKs (verified):** `projects.Project`, `projects.ProjectTask`, `projects.ProjectRisk`,
`AUTH_USER_MODEL`.

### 4. `IssueEscalation` [**ESC-**] — *one step of an issue's escalation path: which level, to which
role and named target, why, when, and how it was resolved at that level.*

Covers bullet **4's escalation-path requirement** explicitly (the task: *"must have a real escalation
path concept (levels/roles/targets) and resolution tracking — not just a status field"*). Realized as
recorded events, **not a configurable policy engine** (Ruling 1).

Fields:
- `issue` → `projects.ProjectIssue` CASCADE `related_name="escalations"`.
- `level` PositiveSmallIntegerField (1–4; validators `MinValueValidator(1)`, `MaxValueValidator(4)`).
- `target_role` CharField(80) blank (the role label, e.g. "Program Manager", "Executive Sponsor" —
  grounded in the `pst_list` RACI/type register, linked as a lens).
- `target_user` → `AUTH_USER_MODEL` SET_NULL null+blank `related_name="issue_escalations"` (the named
  target; the practice's "primary + backup" is two rows, not two columns).
- `reason` TextField (why it was escalated — required; the practice's "complete and accurate issue
  details").
- `escalated_by` → `AUTH_USER_MODEL` SET_NULL null+blank; `escalated_at` DateTimeField (auto-set).
- `resolved_at` DateTimeField null+blank (when this level closed it);
  `outcome` TextField blank (what was decided at this level).
- `created_by` → `AUTH_USER_MODEL`.

`Meta`: `ordering = ["issue_id", "level", "id"]` (the path reads in level order); `unique_together =
("tenant", "number")`; indexes `("tenant","issue")` → `esc_tnt_issue_idx`, `("tenant","level")` →
`esc_tnt_level_idx`.

**FKs (verified):** `projects.ProjectIssue`, `AUTH_USER_MODEL`.

**Auto-number prefixes to reserve:** `RSK`, `RRA`, `ISS`, `ESC` — **all four verified free** across
`apps/` (see the collision check above). `RSP` is 7.3's; none of the four touches it.

**Computed pages (no model — the 7.3 `capacity_demand` precedent):**
- **`risk_analysis`** — the **probability/impact matrix grid** (5×5 cells, each a count + colour),
  the **EMV table** (per risk + project total), the **seeded Monte Carlo** (POST to run; `?seed=` for
  reproducibility; renders **P10/P50/P80/P90/mean** exposure as a table), and the **overrun probability**
  against the active `BudgetRevision` total. **No chart library** (7.16 owns charts); **no stored table**
  (Ruling 2).
- **`risk_monitoring`** — the **top-risk list** (register ordered by exposure), the **exposure
  burn-down table** (period totals of Σ score / Σ EMV), the **review-due queue**, the
  **above-tolerance flag** (documented constant band), and the **lessons lens** (closed rows with a
  non-empty `lessons_learned`).

**Trade-offs I am consciously accepting (state them in the code):**
- **The risk register and its analysis share one model** (`ProjectRisk`) rather than a separate
  `RiskAssessment` table. A risk's probability/impact *is* the register column the market ships; a
  separate assessment table would duplicate the row it assesses. The residual pair is the one
  two-state split, and it stays on the same row (Jira's app does exactly this).
- **Escalation is recorded events, not a policy engine.** `IssueEscalation` rows + the current level
  on the issue give a real path with resolution tracking; a tenant-configurable matrix with SLA timers
  is 7.17's (and 6.3 already owns a generic policy engine — Ruling 1).
- **Monte Carlo is computed and seeded, never stored.** Documented in the view's docstring; the first
  table to add if a tenant needs simulation history is `RiskSimulationSnapshot` (Deferred).
- **`lessons_learned` is a field, not a store.** 7.10 owns the repository (Ruling 3); the field is the
  register-native lesson.
- **Schedule risk is recorded, not simulated.** `schedule_impact_days` is a figure; the network
  simulation waits on 7.2 activity uncertainty (Ruling 5).
- **If the pass runs long, the cut order is: `RiskResponseAction` → `IssueEscalation` → (never)
  `ProjectRisk`/`ProjectIssue`.** Folding `RiskResponseAction` into `ProjectRisk` costs bullet 3 its
  multi-action model (one response per risk) but degrades gracefully; folding `IssueEscalation` into
  `ProjectIssue` fields costs bullet 4 its path history (the current level survives). `ProjectRisk`
  and `ProjectIssue` are **never cut** — bullets 1–5 have no other home.

**Sidebar entry to add — `LIVE_LINKS["7.5"]`:**

```python
"7.5": {
    "Risk Identification & Register":     "projects:rsk_list",
    # The matrix + EMV + Monte Carlo are a COMPUTED page over the register (no stored table) —
    # the 7.3 `capacity_demand` precedent (a computed board, not a model).
    "Qualitative & Quantitative Analysis": "projects:risk_analysis",
    # The response ACTIONS are their own register; the strategy column also renders on rsk_list.
    "Risk Response Planning":             "projects:rra_list",
    "Issue Logging & Escalation":         "projects:iss_list",
    # Top-risk board + exposure burn-down + review queue + lessons lens — a computed monitoring
    # page over the same register (no stored table).
    "Risk Monitoring & Reporting":        "projects:risk_monitoring",
    # Extra live leaf: the escalation queue is the issue register's `?escalated=1` lens.
    "Issue Escalation Queue":             "projects:iss_list?escalated=1",
},
```

Bullet 2 and bullet 5 map to computed pages rather than registers on purpose — the matrix, EMV,
simulation and burn-down are *computations over the register*, and 7.3's `capacity_demand` already
established the "computed board" precedent. If the pass wants fewer pages, bullet 5 can degrade to
`projects:rsk_list?band=critical` with the burn-down as a `#burndown` fragment on `risk_analysis`
(`_safe_reverse` supports `url#frag` — the 6.13 `#search` / 7.3 `#demand` precedent).

**Seeder sketch (`_risk`, own guard):** per tenant — for each seeded active project: 8–12
`ProjectRisk` rows spanning all categories and both `risk_type`s, anchored to the existing WBS work
packages, with `probability`/`impact`/`cost_impact` values that make the matrix populate all four
severity bands and the EMV total land in a meaningful range; one `realized` risk linked to one
`ProjectIssue`; 2–3 `RiskResponseAction` rows per top risk (one `completed`, one `overdue` to show the
flag); 5–7 `ProjectIssue` rows across all severities with 2 `resolved` (stamped) and one carrying an
`IssueEscalation` at level 2 with a populated `target_role`/`reason`; one closed risk with a non-empty
`lessons_learned`. `--flush` deletes children-first:
`IssueEscalation, ProjectIssue, RiskResponseAction, ProjectRisk`.

---

## Belongs to sibling sub-modules (parked, not scoped here)

- **Quality defects, inspections, NC/CAPA, acceptance sign-off** → **7.6**. Note `inventory` already
  ships a QC `DefectReport` (a QC-scoped defect register) — 7.5's issue register is *project-scoped*
  and does not duplicate it.
- **Scope change requests, requirements, the CCB, scope-creep alerts** → **7.7**. A realized risk that
  drives a scope change is a future `ChangeRequest.source_risk` FK (Deferred).
- **Task execution, blocked-task workflow, Kanban/Gantt progress** → **7.8** (extends `ProjectTask` in
  place). 7.5's `wbs_node` anchor is planning grain only.
- **Document repository, knowledge base, lessons-learned repository, document retention** → **7.10**.
  7.5's `lessons_learned` field feeds it; the repository is 7.10's (Ruling 3).
- **Portfolio/program risk rollup, cross-project risk heat maps, enterprise risk aggregation** →
  **7.12**. The project is the highest aggregation this pass builds.
- **Dashboards, charts, report builder, exports** → **7.16**. 7.5 renders matrix grids, tables and
  colour badges; the Monte Carlo S-curve *chart* and the burn-down *chart* are 7.16's.
- **Notification, reminder and workflow automation (auto-escalation, SLA timers, review reminders)** →
  **7.17**. 7.5's verbs write `core.AuditLog` and surface in-page queues only.
- **The generic approval-chain escalation engine** → **6.3** (`procurement.EscalationPolicy` +
  Run). 7.5 records a project-issue path; it does not re-declare a policy engine (Ruling 1).
- **Risk taxonomy master data, reusable risk library, per-project-type checklists, custom fields,
  risk-appetite config** → **7.19 Master Data & Configuration** (and 7.10 for the repository). The
  taxonomy is a choices field this pass (Ruling 6).
- **External ticketing / GRC integrations (Jira, ServiceNow, Riskonnect sync)** → **7.18**.
- **The GL and the ledger** → **2.x**. 7.5's `cost_impact` is a project figure; if a mitigation becomes
  real spend it is a 7.4 `ProjectExpense`, and the ledger is accounting's (L29).

---

## Deferred (later passes / integrations)

| Area | Why deferred |
|---|---|
| **`RiskSimulationSnapshot` (stored Monte Carlo runs per period)** | A report cache, not the model — a stored simulation goes stale the instant a register row changes (Ruling 2). Add only when a tenant needs period-over-period simulation history. |
| **Quantified schedule-risk simulation (3-point durations → P80 finish, criticality index)** | Needs per-activity duration uncertainty and a CPM engine 7.2 does not ship (Ruling 5). 7.5 records `schedule_impact_days` only. |
| **Latin Hypercube sampling, risk correlation / risk-driver modeling, convergence auto-stop** | Pertmaster/Safran-grade; simple random sampling is the documented simplification. Correlation needs a correlation-matrix model. |
| **Decision-tree analysis** | A different object (decisions, not risks); EMV per risk is this pass's scope. |
| **Bowtie cause-and-effect analysis (ARM)** | Needs a cause/control graph model; `cause`/`effect` text is the honest stand-in. |
| **Automated contingency write into `CostControlAccount.contingency`** | One writer per column — the write stays 7.4's (Ruling 4); a cross-sub-module write verb waits on 7.4's contract. |
| **Reusable risk library + per-project-type risk checklists** | Master data / template library → 7.19; the repository → 7.10 (Ruling 3/6). |
| **Tenant-configurable escalation matrix + auto-escalation on SLA breach** | A workflow-engine feature → 7.17; the generic engine already exists at 6.3 (Ruling 1). |
| **Risk appetite / tolerance as a per-tenant config table** | A documented constant band map this pass (the 7.1 `RISK_DISCOUNT` idiom); per-tenant config is 7.19. |
| **KRI / KPI indicators (leading indicators)** | KRI definitions are master data (7.19) and KRI values need a metrics engine; 7.5's exposure figures stand in. |
| **Cross-project / portfolio risk aggregation and enterprise heat maps** | 7.12 (portfolio). |
| **Risk dashboards and S-curve / tornado / burn-down charts** | 7.16 (BI). 7.5 renders grids, tables and badges. |
| **Escalation notifications, review reminders, missing-owner alerts** | No scheduler/mail worker (7.1/6.8/6.19 all recorded it); 7.17's. Badges and audit rows only. |
| **Risk → scope change request FK (7.7) and risk → budget revision linkage (7.4)** | Those models' contracts do not invite the bridge yet; 7.4 Ruling 3 parked the CR bridge, and 7.7 has no row. One-line FKs when they land. |
| **External ticketing / GRC sync (Jira, ServiceNow)** | Integration → 7.18; a `source_number`-style soft reference would be the pattern. |

---

## House-rule constraints discovered (numbered lessons that apply)

Quoted from `.claude/tasks/lessons.md`, the rules this pass must obey:

- **L31 — one sub-module per run.** *"the unit of 'next' is the sub-module; CLAUDE.md's Module
  Creation Sequence (research→todo→code→reviews→skill) runs per sub-module, scoped to that one `N.M`."*
  7.5 builds its **own new tables only**.
- **L28 (verify the spine) — *"before writing any code that FKs into or queries a spine entity, confirm
  it exists … the agents' `NavERP-ERD.md`/`NavERP.md` describe the intended spine, not the built one."*
  Every FK above was grep-verified at its real file/line.
- **L29 — *"the AR/AP ledger, journal posting, multi-currency, and bank masters are REAL now — … FK
  into `accounting.*` by string … do NOT build a second ledger or a stand-in."*** And `Currency` is
  **GLOBAL (no tenant FK)** — the one FK that stays unscoped.
- **L36 — *"the module that ships FIRST owns the shared entity … the later module EXTENDS by FK, never
  re-declares — a second parallel schema for the same concept is the bug L29 forbids."*** 7.5 FKs
  `Project`/`ProjectTask`/`CostControlAccount` **by string**, re-declares none of 7.1–7.4.
- **L7 — *"the contract handed to parallel agents must pin EVERY context key a template consumes
  (detail object, edit-mode object, every `*_choices`, every FK queryset), not just the list var."***
  The 7.5 contract must pin the risk/issue/action/escalation context vars and the `*_choices`.
- **L8 — *"after the status-code sweep, also assert each detail page's rendered HTML contains the
  object's identifier … this catches the silent-blank class."*** Tests assert `str(obj)` tokens.
- **L11 — *"Integer FK list filters must validate input before `.filter(fk_id=…)`"*** (`?project=abc` →
  `ValueError` → 500). Guard the risk/issue register's project/wbs/owner filters with `if value.isdigit()`.
- **L9 / L10 —** guard pagination (`page_obj.has_previous`) and user-FK display (`{% if fk %}`) — the
  register renders `owner`/`escalated_to`/`target_user`, all nullable user FKs.
- **L2 — *"Multi-line `{# … #}` comments **leak as visible text**. Use `{% comment %} … {% endcomment %}`
  for any note longer than one line."*** The 7.5 templates have many multi-line notes → use
  `{% comment %}`.
- **L3 — *"Pair the status-code smoke test … with a rendered-HTML content check (assert no `{#`/
  `{% comment` markers …)."*** The `test_risk_views` pass must assert no comment leak.
- **L33 — *"the design system uses a FIXED, colour-named palette per component and there is NO
  semantic/danger variant … Known-good sets: badges `badge-green/red/amber/info/muted/slate`."*** The
  severity/band badges must use colour-named classes (`badge-red`/`badge-amber`/`badge-green`) and copy
  a sibling's ternary verbatim — run `grep -n '\.badge-' static/css/theme.css` **before** writing them.
- **L27 — *"privileged/workspace-config writes use `@tenant_admin_required`."*** `iss_escalate` and
  `rsk_reopen` are tenant-admin; list/detail stay `@login_required`.
- **L35 — *"A hand-parsed POSTed `Decimal` amount needs a FULL guard chain."*** The Monte Carlo view
  parses `?seed=` and the EMV/`cost_impact` inputs — use a `forms.DecimalField`/`IntegerField` with
  `is_finite()` + magnitude cap rather than raw `request.GET` parsing.
- **L16 — *"Date-equality tests flake on the UTC-offset window (use Django's `timezone`, not
  `datetime.date.today()`)."*** `identified_date`/`review_date`/`is_overdue` all use `timezone.localdate()`.

**Verified spine summary for the todo agent:** `projects.Project` (`Projects.py:27`),
`projects.ProjectTask` (`ProjectTasks.py:22`), `projects.ProjectMilestone` (`ProjectMilestones.py:17`),
`projects.ProjectStakeholder` (`ProjectStakeholders.py:24`), `projects.CostControlAccount`
(`CostControlAccounts.py:29`), `projects.BudgetRevision` (`BudgetRevisions.py:27`),
`projects.ProjectRequest` (`ProjectRequests.py:25`), `core.Party`, `core.OrgUnit`, `core.Document`,
`core.Activity`, `core.AuditLog`, `accounting.Currency` (GLOBAL). **No `Risk`/`Issue`/`LessonsLearned`
class exists anywhere**; `procurement.EscalationPolicy` (6.3) exists and is **not** duplicated.
