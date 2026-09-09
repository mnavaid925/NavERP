# Research — Sub-module 7.4: Cost & Budget Management (Module 7 — Project Management, `projects`)

> **Read this first.** 7.4 is the module's **money engine**: it turns 7.1's chartered project and 7.2's WBS into a
> *budgeted, baselined, committed, earned-value-measured, formally re-baselined* cost position. It is **not**
> billing/invoicing to the client (7.15), **not** portfolio rollups (7.12), **not** reporting/BI (7.16), **not** the
> risk register that sizes contingency (7.5), **not** timesheets or resource rates (7.3 — see the ruling below),
> **not** task-execution progress (7.8), and **not** the accounting ledger (2.x owns GL — 7.4 *tracks project cost*
> and FKs into the spine; it **never writes a journal entry**, exactly as `accounting.JobCostEntry` posts JEs and
> `projects` never does). The failure mode for this pass is **building a second ERP inside a sub-module**: a PO
> engine (4.x/6.x own procurement), an AP/invoice engine (6.x `SupplierInvoice`), a spend forecaster (6.x
> `BudgetCostManagement.CostForecast`), a time-phased BCWS curve engine (Cobra-grade EVMS), or client-side
> profitability (7.15). All of them are real features in the products surveyed and all of them are parked below.
>
> **The other trap is a name collision with 7.2.** 7.2's contract froze `ScheduleBaseline` [BSL-] and the
> "frozen snapshot columns are legitimate stored-derived" precedent. 7.4's cost baseline is therefore **not** named
> `CostBaseline` and does **not** reuse the BSL prefix — the cost baseline below is the **approved `BudgetRevision`**,
> which is a different object with a different lifecycle (a schedule baseline freezes *dates*; a cost baseline
> approves *lines* that then become immutable through revision control).

---

## Repo state checked first

### LIVE_LINKS built so far in Module 7 (`apps/core/navigation.py`)

`grep -n '"7\.' apps/core/navigation.py` → **`"7.1"` at line 1702, `"7.2"` at line 1717. Nothing else.** So 7.4's
sidebar block will be the third Module 7 entry, after Planning & Scheduling.

### The app exists; 7.1 and 7.2 are built

```
apps/projects/models/ProjectInitiation/          → ProjectRequest[PRQ], Project[PRJ],
                                                   ProjectStakeholder[PST], ProjectKickoff[PKO]
apps/projects/models/ProjectPlanningScheduling/  → ProjectTask[TSK], TaskDependency[DEP],
                                                   ProjectMilestone[MST], ScheduleBaseline[BSL]
```

- `apps/projects/models/__init__.py` re-exports all eight models in two labelled blocks (`# --- 7.1 …`,
  `# --- 7.2 …`). **7.4 adds a third `# --- 7.4 Cost & Budget Management` re-export block** in the same file.
- Migrations shipped: `0001_initial`, `0002_ordering_indexes_and_nonnegative_estimates`,
  `0003_projecttask_projectmilestone_schedulebaseline_and_more`. **7.4's migration is `0004_…`.**
- Backend package convention (7.1/7.2 both): `models/ forms/ views/ urls/<SubModule>/<Entity>.py`, same file
  name in all four layers, sub-package `__init__.py` files stay EMPTY, re-exports only in the four top-level
  `__init__.py` files. **7.4's sub-module folder is `CostManagement/`** in each layer.
- Template convention: `templates/projects/initiation/<entity>/{list,detail,form}.html` (7.1),
  `templates/projects/planning/<entity>/…` (7.2). **7.4 uses `templates/projects/cost/<entity>/…`** with entity
  folders lowercase singular (`projectbudgetline/`, `budgetrevision/`, `costcontrolaccount/`, `projectexpense/`).
- The `_base.py` toolkit is ready for money: `apps/projects/models/_base.py:28-38` already defines
  `MAX_Q2 = Decimal("9999999999.99")` and `q2()` (quantize to 2dp + clamp), explicitly *the money column shape
  this app writes (DecimalField(14, 2))* — written in 7.1 for the request estimates, **used heavily by 7.4**.
- Tests convention: `test_planning_*` fixtures/helpers per subslug → **7.4 uses `cost`**: fixtures `cost_*`,
  helpers `_cost_*`, tests `test_cost_{models,forms,views,security}.py`. `conftest.py` is owned by itself;
  only append to it with a full unfiltered re-run.
- Seeder: `apps/projects/management/commands/seed_projects.py` already splits per-sub-module guards
  (`_seed_tenant` for 7.1, `_planning` for 7.2). **7.4 adds `_cost` with its own guard** so an already-seeded
  workspace still gets cost rows.

### What 7.1's pass already recorded FOR 7.4 (do not re-derive)

- `Project` ships **no money columns** (`apps/projects/models/ProjectInitiation/Projects.py:19-21` docstring:
  *"No money columns — `budget_amount`, commitments and actuals are 7.4's"*). 7.4 does **not** add money to
  `Project` either — the budget is its own row set, and `Project` stays the identity container.
- `accounting.GLAccount` was verified in 7.1 and **deliberately not FK'd** — *"cost accounts are 7.4's"*
  (`research-projects-7.1.md:76`). 7.4 takes the FKs.
- `accounting.Budget` was verified and **not FK'd** — *"the budget baseline is 7.4's"* (line 77).
- The three-`PRJ-` ruling stands (`research-projects-7.1.md:161-176`): `projects.Project` is the Module 7 master;
  `accounting.Project` (2.9) and `crm.CrmProject` (1.8) are pre-spine stand-ins, untouched.

### Spine entities VERIFIED to exist (grep evidence)

| Entity | Verified at | What 7.4 uses it for |
|---|---|---|
| `projects.Project` [PRJ-] | `apps/projects/models/ProjectInitiation/Projects.py:27` | the container every 7.4 row FKs (`project` FK, `related_name="budget_revisions"` / `"control_accounts"` / `"expenses"`; budget lines FK via their revision) |
| `projects.ProjectTask` [TSK-] | `apps/projects/models/ProjectPlanningScheduling/ProjectTasks.py:22` | the WBS anchor for budget lines and control accounts (`node_type` = `deliverable` summary node / `work_package` leaf); **bottom-up rollup walks this tree**. Carries `effort_hours` and planned dates but **no money and no percent-complete** — see the 7.8 note |
| `projects.ScheduleBaseline` [BSL-] | `apps/projects/models/ProjectPlanningScheduling/ScheduleBaselines.py:20` | NOT FK'd — but its **freeze-evidence precedent** (`planned_finish`/`task_count`/`total_effort_hours` stored at freeze because *a frozen baseline that recomputed itself would not be frozen*) and its **one-active-per-project atomic verb pattern** are the two idioms 7.4's revision machinery copies |
| `accounting.GLAccount` | `apps/accounting/models/GeneralLedger/GLAccounts.py:5` | the optional ledger lens on budget lines and control accounts (`unique_together ("tenant","code")`, hierarchical `parent`, **never stores a balance** — `balance()` aggregates posted lines). 7.4 only *labels* cost rows with an account; it never posts |
| `accounting.Currency` | `apps/accounting/models/GeneralLedger/Currencies.py:6` | **GLOBAL table, no tenant column (L29)** — the one FK that must stay unscoped. One currency per budget revision / expense row; sums are at face value, nothing is converted (the `procurement.CostForecast.currency` precedent, `CostForecasts.py:123-126`) |
| `accounting.Budget` + `BudgetLine` [BUD-] | `apps/accounting/models/Budgeting/Budgets.py:6`; `BudgetLines.py:5` | verified, **deliberately not reused** — see the ruling. Their shape (`version` original/revised/forecast, `lines` with `gl_account` + optional `org_unit`) is the reference 7.4's own budget borrows from |
| `accounting.Project` + `JobCostEntry` [PRJ-/JCE-] | `apps/accounting/models/ProjectCosting/Projects.py:6`; `JobCostEntries.py:5` | the 2.9 costing lens. `JobCostEntry` posts a balanced JE per row and derives `actual_cost()` from **its own** table FK'd to `accounting.Project`. 7.4 does not write JCE rows (no `projects.Project` link exists on them); the eventual `accounting.Project ↔ projects.Project` bridge is a spine consolidation, parked |
| `core.Party` | `apps/core/models/Party.py:5` | the vendor on a committed/actual cost row (`vendor` → Party, nullable — same pattern as `scm.PurchaseOrder.vendor`) |
| `core.OrgUnit` | `apps/core/models/OrgUnit.py:5` | has **`cost_center`** in `KIND_CHOICES` — the optional owning-cost-centre FK on a budget line, mirroring `BudgetLine.org_unit` (nullable; only if a slot is free) |
| `core.utils.next_number` | `apps/core/utils.py:34` | prefixes via `TenantNumbered.save()` with the 5-attempt IntegrityError retry (`apps/projects/models/_base.py:66-75`) |
| `core.AuditLog` | `apps/core/models/AuditLog.py` | approval/re-baseline/posting evidence. **`action` is varchar(10)**; verbs 7.4 writes: `create/update/delete/submit/approve/reject/activate/supersede/post/void` — all ≤ 10 chars, detail in `changes` |
| `scm.PurchaseOrder` [PO-] | `apps/scm/models/ProcurementManagement/PurchaseOrders.py:15` | the spine PO (vendor → Party, `currency`, editable only pre-approval, amendment trail). **No project FK on it** — and 7.4 adds none (4.x/6.x own the document). 7.4 records a **soft reference** (`source_number = "PO-00042"`) |
| `procurement.SupplierInvoice` [SIV-] | `apps/procurement/models/InvoiceVoucherManagement/SupplierInvoices.py:135` | the AP engine (match engine, 11-state lifecycle, terminal `paid`). Invoices = **actuals** in 7.4's world; again a soft reference only |
| `procurement.CostForecast` [FCST-] + `BudgetMapping` | `apps/procurement/models/BudgetCostManagement/CostForecasts.py:97` | ⚠️ **exists (6.x).** Workspace-level procurement spend projection (`open_pos` / `run_rate` / `blended` committed-vs-historical arithmetic) against `accounting.Budget`. **Not project-scoped, not earned-value.** 7.4 must not build a second generic spend forecaster — see ruling |
| `hrm.Timesheet` / `hrm.TimesheetEntry` | `apps/hrm/models/TimeTracking/Timesheet.py:8`; `Timesheetentry.py:5` | ⚠️ labor actuals live here **today FK'd to `accounting.Project`** with `task_description` free text *"until Project Management (Module 7) ships a Task/WBS model"* (Timesheetentry.py:9). Re-pointing that FK is 7.3/7.11's; 7.4 only *consumes* labor cost, see ruling |

### Spine entities VERIFIED NOT to exist (grep evidence)

1. **No project-cost model anywhere in `projects` or elsewhere.** `grep -rn "class ControlAccount\|class
   CostBaseline\|class ProjectBudget\|class BudgetChange\|class ProjectExpense\|class Commitment\|class
   BudgetRevision\|class ExpenseItem\|class ChangeRequest\|class CostAccount" apps/` → **empty**. Bullet-5's
   `ChangeRequest[CR-]` is named in the `/next-module` module table but **no sub-module owns it yet** and no class
   exists; `request_type="change_request"` on `ProjectRequest` is a *value*, not a table.
2. **No 7.3 artifacts or code.** `ls .claude/tasks/ | grep project` → 7.1 + 7.2 research/contract/review/test
   files only; **there is no `research-projects-7.3.md` and no `contract-projects-7.3.md`**, and
   `ls apps/projects/models/` shows only `ProjectInitiation/` + `ProjectPlanningScheduling/` — no
   `ResourceManagement/` package exists yet. Whatever the concurrent 7.3 run is doing, **nothing has landed in
   the repo or in `.claude/tasks/` as of 2026-09-10.** The boundary call below is therefore made unilaterally
   and must be re-checked against 7.3's contract the moment it appears.
3. **No percent-complete anywhere in Module 7.** 7.2's `ProjectTask` carries `status`
   (planned/in_progress/done/cancelled) and `effort_hours` — no `%` field, and the 7.2 contract explicitly
   reserved execution fields for 7.8 (*"7.8 extends THIS row in place"*). EV therefore needs a 7.4-local progress
   field until 7.8 ships — designed below, flagged for the hand-off.
4. **No time-phasing / period-cost table anywhere.** No `store period performance`, no period-cost snapshot
   (P6's mechanism) exists in the repo. Time-phased BCWS curves are out of scope for this pass.
5. **No scheduler / mail worker** (recorded by 7.1 from the 6.8/6.19 passes). Over-budget alerts are badges and
   audit rows, not notifications — the notification engine is 7.17's.

---

## THE RULINGS — boundaries 7.4 must set before anyone else does

### Ruling 1 — Resource cost rates are 7.3's; resource cost *aggregation* is 7.4's

**Decision: 7.4 stores amounts, never rates.** Wrike's model (budget fields auto-computed from logged effort ×
bill/cost rates at user/job-role/project level) is the market pattern, but it requires a rate card that only 7.3
can own — and no 7.3 artifact exists yet to contract with. Concretely:

- A 7.4 labor budget line is **an amount against a category and (optionally) a WBS node**. If a later 7.3 rate
  card wants to *generate* that amount from hours × rate, the generator lives in 7.3 and writes `amount` — the
  7.4 row stays an amount and never stores `hours` or `rate`.
- Labor **actuals** come from timesheets (7.3's booking, 7.11's approval, `hrm.TimesheetEntry` today). 7.4
  consumes them as cost rows; it never computes labor cost from rosters or calendars.
- **Re-check this when 7.3's contract lands.** If 7.3 freezes a `ResourceRate`/`RateCard` model, nothing in 7.4
  changes (7.4 has no rate field to collide with); if 7.3 claims budget-line authorship, this ruling is the
  precedent to cite — the first sub-module that needs an object owns it, and 7.4 needs the *amount*, not the rate.

### Ruling 2 — The cost baseline is the approved `BudgetRevision` (not a `CostBaseline`, not `BSL`)

7.2's contract froze `ScheduleBaseline` [BSL-] with `baseline_type = baseline | what_if`, `is_active` kept unique
per project by atomic verbs ("MySQL/MariaDB cannot enforce a partial unique index"), and frozen snapshot columns.
7.4 copies the **patterns** and avoids the **names**: the cost baseline is `BudgetRevision` [BVR-] with
`revision_no` (0 = original), an `activate` verb that supersedes the previous approved revision atomically, and
immutable approved rows. Two deliberate differences from `ScheduleBaseline`:

- A schedule baseline **snapshots** figures because live tasks mutate underneath it. An approved budget revision
  **is** the immutable record (edit/delete refuse it, same state guard as `bsl_edit` on frozen rows), so the
  BAC / category totals / CA budgets can be **derived** from its lines without any snapshot columns. Stored
  derived columns would be a second thing to keep in sync with the lines they summarise.
- `what_if` budgeting is parked (see Deferred) — Procore's PCO workflow and 7.2's what-if scenarios cover the
  near-term need; a budget what-if copy is a `draft` revision in this pass's model.

### Ruling 3 — `ChangeRequest` is 7.7's; 7.4's bullet-5 row is a *budget* revision

The module table lists `ChangeRequest[CR-]` unassigned, 7.7's bullet names scope change proposals and CCB
decisions, and no `ChangeRequest` class exists yet. 7.4 therefore does **not** mint a `ChangeRequest` model. The
cost-side change vehicle is `BudgetRevision` — a formally requested, impact-analysed, approved (or rejected)
re-statement of the project budget. A 7.7 scope CR that has cost impact would drive a `BudgetRevision` (or the
reverse, once 7.7 ships an FK target) — the linkage is parked until 7.7 defines its row. Cosmetic note:
`NUMBER_PREFIX = "CR"` is already squatted by `scm.ComplianceRequirement`; prefix `BVR` avoids the issue entirely.

### Ruling 4 — EVM metric *definitions* belong to 7.4; 7.15's "Budget vs. Actual Analysis" bullet reads them

NavERP 7.15 bullet 4 (*"Real-time cost variance, earned value metrics, and forecast updates"*) literally overlaps
7.4's bullet 4. Decision: **7.4 is the first sub-module that needs the metrics, so 7.4 defines them** as derived
properties on the control account; 7.15's bullet is the *financial* lens (revenue recognition, A/R, client
profitability) and consumes the numbers. This is the same "first sub-module that needs it" rule that put
`Project` in 7.1.

### Ruling 5 — Procurement's `BudgetCostManagement` is workspace spend, not project cost — no duplicate forecaster

6.x shipped `procurement.CostForecast` [FCST-] (committed open-PO + historical invoice run-rate, projected per
`accounting.Budget`) and `BudgetMapping`. Those are **workspace-level procurement spend** tools. 7.4's EAC is
**project-scoped and earned-value-based** (`BAC/CPI`), computed from project budget lines and project cost rows.
Same word ("forecast"), different object. 7.4 builds no `CostForecast`-shaped model and no per-PO commitment
engine — its commitment rows are *records of* procurement documents, keyed by number.

### Ruling 6 — 7.4 tracks project cost; the ledger is 2.x's; contingency analysis is 7.5's

- 7.4 FKs `accounting.GLAccount` as a reporting lens and **never** writes `JournalEntry`/`JobCostEntry`. The 2.9
  bridge (`accounting.Project` ↔ `projects.Project`) is a parked spine consolidation.
- Contingency is **budgeted** in 7.4 (a first-class line category and a CA field). The *analysis that sizes it*
  (Monte Carlo, EMV, risk-adjusted reserves) is 7.5's — the same split 7.1 drew with its flat risk discount.

---

## Leaders surveyed (with source links)

The domain here is **project cost control / earned value management** — from ANSI/EIA-748 EVMS engines down to
lightweight PM budget trackers. The spread matters: the EVM-grade tools define the *control-account* vocabulary,
the lightweight tools define the *budget-vs-actual* UX, and construction cost control defines the
*commitments* triangle this bullet set is clearly written from.

1. **Oracle Primavera (P6 / Primavera Cloud)** — the enterprise scheduling-cost reference: PV/EV/AC as the
   basis of all earned value fields, a **designated EV baseline**, rollups assignment → activity → WBS → project,
   and *Store Period Performance* for period metrics. <br>
   [Earned Value Overview (Oracle docs)](https://docs.oracle.com/cd/E80480_01/English/user_guides/schedule_management_user_guide/233373.htm) ·
   [P6 Professional EVM features (Ten Six)](https://tensix.com/primavera-p6-professional-evm-features/)
2. **Deltek Cobra** — the reference EVMS **cost engine** for compliance-driven projects: control accounts and
   work packages as first-class structure, management reserve, flexible EV calculation methods (by budget /
   dollars / time / hours), budgets vs actuals vs forecasts, EIA-748/DCMA compliance. <br>
   [Deltek Cobra](https://www.deltek.com/products/delivery-assurance/ppm/cobra/) ·
   [Earned value methods (Deltek help)](https://help.deltek.com/product/Cobra/8.0/GA/Methods%20for%20Calculating%20Earned%20Value.html) ·
   [EVM Series QRG (PDF — management reserve, CAs, WPs)](https://education.deltek.com/web/rsl/ppm/evm/cobra_earnedvaluemanagementseriesqrg.pdf)
3. **Microsoft Project / Project Online (PWA)** — the mass-market EVM baseline: *a baseline budget is required
   before earned value analysis means anything*; built-in PV/EV/AC/CV/SV/CPI/SPI reporting. <br>
   [Earned value analysis, for the rest of us (Microsoft Support)](https://support.microsoft.com/en-us/project/earned-value-analysis-for-the-rest-of-us) ·
   [Manage costs (Microsoft Support)](https://support.microsoft.com/en-us/project/user-goal-manage-costs)
4. **Procore** — the construction cost-control reference and the reason bullet 3 reads the way it does:
   budget line items with cost codes; **commitments** (POs, subcontracts, their change orders) recorded
   *at execution, not at payment*; change events → potential change orders → change orders; budget revisions. <br>
   [Committed costs (Procore library)](https://www.procore.com/library/committed-costs) ·
   [Commitment management](https://www.procore.com/financial-management/commitments) ·
   [Change Orders user guide](https://en-ca.support.procore.com/products/online/user-guide/project-level/change-orders)
5. **Unanet (GovCon / A&E ERP)** — the mid-market EVM reference: EAC = actuals + ETC as a *rolling* forecast,
   CPI/SPI shown in context with ETC/EAC, timekeeping feeding EVM directly. <br>
   [Unanet ERP for A&E — Project Management](https://unanet.com/erp-for-a-e/project-management/) ·
   [Unanet ERP for GovCon — Project Management](https://unanet.com/erp-for-govcon/project-management) ·
   [Phased estimating / EAC methodology (Unanet blog)](https://unanet.com/blog/project-planning-estimate-budget-and-forecast)
6. **Celoxis** — PPM mid-market: budget structured **by phase, task, resource and cost type**, real-time
   budget-vs-actual, forecasting to catch overruns. <br>
   [Project cost management guide (Celoxis)](https://www.celoxis.com/article/project-cost-management-software) ·
   [PM software features 2026 (Celoxis)](https://www.celoxis.com/article/project-management-software-features)
7. **Wrike** — the lightweight end: financial fields (budget, planned/actual fees, planned/actual cost) computed
   from logged effort × bill/cost hourly rates at user/job-role/project level. <br>
   [Financial Fields for Budgeting (Wrike help)](https://help.wrike.com/hc/en-us/articles/1500005128341-Financial-Fields-for-Budgeting) ·
   [Budgeting in Wrike](https://help.wrike.com/hc/en-us/articles/360058001433-Budgeting-in-Wrike) ·
   [Hourly rates in Wrike's budgeting](https://help.wrike.com/hc/en-us/articles/1500005128301-Hourly-Rates-in-Wrike-s-Budgeting)
8. **Scoro** — professional-services cost management with the cleanest **committed-cost** semantics outside
   construction: a *"Consider purchase orders as committed cost"* toggle in the budget burn, bills + POs as
   project cost, quoted-vs-actual tables. <br>
   [Burn and breakdown charts — budget (Scoro support)](https://support.scoro.com/hc/en-us/articles/18326155777037-Burn-and-breakdown-charts-budget) ·
   [Cost management (Scoro)](https://www.scoro.com/features/cost-management/)

**Considered and not cited:** *Planview Portfolios* and *Smartsheet* surfaced no cost-control pages that fetched
cleanly this run (Smartsheet 404'd through the fetcher in 7.1's pass too), and *Monday.com* / *Float* are
rate-and-utilisation trackers without a control-account concept — none of the four would have added a feature the
eight above do not already evidence. Dropped rather than cited second-hand.

---

## Feature catalog (this sub-module only)

Priority key: **table-stakes** (nearly every leader has it) · **common** (most have it) · **differentiator** (a
few standouts).

### Bullet 1 — Budget Planning & Estimation
*"Labor, material, overhead, and contingency budgeting with bottom-up rollup."*

- **A structured project budget with cost categories** — the four the bullet names (labor / material / overhead /
  contingency) plus the market's standard extras. Celoxis budgets *"by phase, task, resource, cost type, and
  time"*; Procore's budget is line items with cost codes; Cobra's budget structure is the CA/WP tree with
  category breakdowns. · seen in: Celoxis, Procore, Cobra, Scoro (quoted vs actual) · priority: **table-stakes** ·
  spine: **new table `ProjectBudgetLine`** with a `category` choices field (labor / material / equipment /
  subcontract / overhead / contingency / other — the bullet's four plus the three the market always adds) ·
  buildable now.
- **Bottom-up rollup from the WBS** — the bullet's *bottom-up*: a work-package line is entered at the leaf, and
  deliverable/project/category totals are the ROLLUP, never re-keyed. P6 rolls assignment → activity → WBS →
  project; the 7.2 tree view already computes `rollup_effort_hours` on deliverables the same way. · seen in:
  Primavera P6, Celoxis (by task/phase), Cobra (WP → CA → project) · priority: **table-stakes** · spine:
  `wbs_node` → `projects.ProjectTask` on the line (nullable — some cost is project-level); category and project
  totals are **derived properties/annotations, never stored** · buildable now.
- **The budget as a versioned document, not a live-editable pile** — `accounting.Budget` already models
  `version` (original / revised / forecast) and Procore/Cobra keep budget revisions as first-class history; the
  Scoro/Procore burn only means something against a *stated* baseline. · seen in: Procore (budget revisions),
  Cobra (budget change log), Celoxis · priority: **table-stakes** · spine: **new table `BudgetRevision`** —
  `revision_no` 0 = original; the approved revision **is** the cost baseline (Ruling 2) · buildable now.
- **Contingency as a first-class bucket, not a rounding fudge** — Cobra's management reserve is *"a portion of
  the contract budget base held … to cover unanticipated program requirements"*; PMBOK separates contingency from
  the cost baseline proper. · seen in: Cobra (management reserve), PMBOK-grade tools · priority: **common** ·
  spine: `category="contingency"` lines + a `contingency` column on `CostControlAccount` for the CA-held
  reserve; **the risk analysis that sizes it is 7.5's** (Ruling 6) · buildable now.
- **Budget lines mapped to GL accounts** — so project cost and the ledger speak the same vocabulary without the
  project writing to it. `accounting.BudgetLine.gl_account` and `scm.PurchaseOrderLine.gl_account` are the
  in-repo precedents. · seen in: ERP-grade tools generally (Cobra/Unanet) · priority: **common** · spine:
  `gl_account` → `accounting.GLAccount` (nullable, PROTECT like `JobCostEntry.gl_account`) on the line ·
  buildable now.
- **A single display currency per budget** — `accounting.Currency` is the global unscoped master; sums at face
  value, nothing converted (the `procurement.CostForecast.currency` help text is the wording to copy). · seen
  in: every multi-currency ERP tool · priority: **table-stakes** · spine: `currency` → `accounting.Currency` on
  `BudgetRevision` (and per-row override on `ProjectExpense`, defaulting to the revision's) · buildable now.
- **Top-down budget vs bottom-up estimate reconciliation** — 7.2 owns the *estimating methods*
  (`ESTIMATION_CHOICES` bottom_up/top_down/analogous/parametric live on `ProjectTask`); 7.4 records the money.
  A variance column between top-down and rolled-up lines is cheap but needs a top-down store this pass does not
  have. · seen in: P6, Celoxis · priority: **common** · **deferred** (needs a top-down target row; fold into
  `BudgetRevision` later if wanted) · not buildable without model #5.
- **Rate-based labor budgeting (hours × rate cards)** — Wrike computes planned cost from effort × bill/cost
  rates at user/role/project level; Unanet feeds timekeeping into budgets. · seen in: Wrike, Unanet · priority:
  **common** · **deferred → 7.3** — Ruling 1: 7.4 stores amounts; 7.3 owns rates and would *generate* them.

### Bullet 2 — Cost Baseline & Control Accounts
*"Earned value management (EVM) structures and work package cost tracking."*

- **Control accounts as the EVM planning structure** — the unit where scope, budget, actuals and progress meet.
  Cobra manages *"Control Accounts, Work Packages and Resources"* as its core structure; P6 rolls EV up through
  WBS elements. Lightweight tools (Wrike, Scoro, Float) have no CA concept at all — that absence is exactly the
  enterprise/lightweight divide, and NavERP's bullet 2 asks for it. · seen in: Cobra, P6, Unanet · priority:
  **table-stakes (for this bullet)** · spine: **new table `CostControlAccount`** · buildable now.
- **One designated active baseline the project is managed against** — P6: *"to track earned value, you must
  designate an existing baseline as your earned value baseline"*; Microsoft Project requires a baseline before
  any variance is meaningful. · seen in: P6 (EV baseline designation), Microsoft Project, Cobra · priority:
  **table-stakes** · spine: the **approved** `BudgetRevision` is the baseline (exactly one per project, kept
  true by the `bvr_activate` verb inside `transaction.atomic()` — the `ScheduleBaseline.is_active` idiom) ·
  buildable now.
- **CAs anchored to the WBS** — a control account covers a deliverable node's subtree; work packages below it
  carry the budget lines. · seen in: Cobra (CA ⊃ WPs), P6 (WBS-level EV) · priority: **table-stakes** · spine:
  `wbs_node` → `projects.ProjectTask` on `CostControlAccount` (nullable — a CA may cover the project root) +
  `clean()` guard that the node belongs to the same project (the `ProjectMilestone.anchor_task` pattern) ·
  buildable now.
- **Work-package cost tracking (budget vs actual per WBS node)** — the bullet's second half. · seen in: P6,
  Celoxis (by task), Procore (cost codes ≈ WBS) · priority: **table-stakes** · spine: derived — budget per node
  = SUM of active-revision lines with that `wbs_node` (or its subtree); actuals per node = SUM of
  `ProjectExpense` rows with that node. Both read-only aggregates in views · buildable now.
- **A percent-complete at the cost-control level** — EV needs progress and 7.2 shipped none (its contract
  reserved execution for 7.8). The honest interim: an explicit `percent_complete` on the CA, manually attested
  (0–100, DecimalField(5,2)), with a docstring note that **7.8's task execution fields supersede the manual
  entry** — the same way 7.1's kickoff attestation defers to 7.2's baseline rows. · seen in: every EVM tool
  (P6 performance-percent-complete options; Cobra EV methods) · priority: **table-stakes** · spine:
  `percent_complete` on `CostControlAccount` · buildable now, hand-off documented.
- **Freeze-time BAC evidence without snapshot columns** — `ScheduleBaseline` stores snapshots because live tasks
  mutate; approved revision rows are immutable, so BAC is honestly derivable. · priority: **common (design
  ruling, not a feature)** · spine: `bac` as a **derived property** on `CostControlAccount` = SUM of the active
  revision's lines mapped to that CA · buildable now.
- **Management reserve separate from contingency** — Cobra's distinction (MR held *above* the performance
  baseline). · seen in: Cobra, DCMA-grade EVMS · priority: **differentiator** · **deferred** — folded into
  `CostControlAccount.contingency` this pass; splitting MR out is one more column when a tenant actually asks.
- **Time-phased performance measurement baseline (period BCWS curves, Store Period Performance)** — P6's
  incremental period metrics. · seen in: P6, Cobra · priority: **differentiator** · **deferred** — needs a
  period-cost table (model #5+) and a scheduler; NavERP's planning-grade PV below is the documented
  simplification, mirroring how 7.2 documented its longest-chain critical path.

### Bullet 3 — Expense Tracking & Commitments
*"POs, invoices, accruals, and real-time spend against budget."*

- **Commitments distinct from actuals** — Procore defines committed costs as *"expenses that are guaranteed
  through formal agreements"* recorded *"at the moment a contract or purchase order is executed — not when an
  invoice arrives"*; Scoro's toggle does the same arithmetic in the forecast; without them *"costs are variable
  and can be forgotten until they hit the books as actual costs"*. · seen in: Procore, Scoro, construction
  cost-control generally · priority: **table-stakes** · spine: `ProjectExpense.entry_type = commitment` ·
  buildable now.
- **Actuals (vendor invoices, bills)** — the SIV-side of the world; 6.x's `SupplierInvoice` owns the AP
  lifecycle and 7.4 never re-runs it. · seen in: every tool surveyed · priority: **table-stakes** · spine:
  `entry_type = actual` + `source_number` (e.g. `SIV-00045`) **soft reference** — no FK, 4.x/6.x own the
  documents (Ruling 5) · buildable now.
- **Accruals** — the third leg of the bullet; the committed/actual/accrual triangle is standard
  construction/EVM vocabulary. · seen in: Procore/Scoro ecosystem, EVM practice · priority: **common** · spine:
  `entry_type = accrual`, reversed by a paired negative row (`status = void`) rather than a delete · buildable
  now.
- **A reference to the source procurement document** — Procore: a PO is issued, receipt confirmed, funds
  visible; Scoro considers *"POs … as committed cost"*. In NavERP the PO engine is `scm.PurchaseOrder` (no
  project FK) and invoices are `procurement.SupplierInvoice`. · priority: **table-stakes** · spine:
  `source_kind` choices (purchase_order / supplier_invoice / contract / timesheet / manual / accrual) +
  `source_number` CharField — **deliberately not FKs** (Ruling 5: 7.4 records, never operates) · buildable now.
- **Real-time spend against budget (remaining budget, burn)** — Celoxis *"track actual vs planned costs in real
  time"*; Scoro's burn/breakdown; Wrike's budget dashboard. · seen in: Celoxis, Scoro, Wrike, Unanet · priority:
  **table-stakes** · spine: derived properties/annotations on `CostControlAccount` and the project overview —
  `budget_total`, `committed`, `actual`, `available = budget − committed − actual` · buildable now.
- **The vendor on the cost row** — commitments and invoices have a counterparty; `scm.PurchaseOrder.vendor` →
  `core.Party` is the pattern. · seen in: Procore (vendor per commitment), Unanet · priority: **common** ·
  spine: `vendor` → `core.Party` (nullable) on `ProjectExpense` · buildable now.
- **A posting lifecycle on cost rows** — drafts don't burn budget; voided rows shouldn't disappear from history.
  `JobCostEntry` (draft/posted) and `SupplierInvoice`'s verb-guarded lifecycle are the in-repo precedents. ·
  priority: **common** · spine: `status` (draft / posted / void) + POST-only `pex_post` verb (audit action
  `post`) · buildable now.
- **Commitment change orders as a sub-workflow (PCO → CO against a specific PO)** — Procore's depth; the
  amendment itself belongs to procurement. · seen in: Procore · priority: **differentiator** · **deferred** —
  a commitment change is recorded as a new/adjusted `ProjectExpense` commitment row (delta rows, audit-logged);
  the PO amendment workflow is 4.x/6.x's.
- **Timesheet labor actuals flowing into project cost automatically** — Unanet: *"time entry data feeds directly
  into EVM calculations"*; Wrike computes from logged effort. · seen in: Unanet, Wrike · priority: **common** ·
  **deferred → 7.3/7.11** — when `hrm.TimesheetEntry` repoints to `projects.ProjectTask`, a labor-cost
  synchronisation can write `ProjectExpense(kind=actual, source_kind=timesheet)` rows; until then labor actuals
  are manual rows. The `source_kind="timesheet"` choice reserves the vocabulary now.

### Bullet 4 — Forecasting & Estimate at Completion (EAC)
*"Trend analysis, CPI/SPI projections, and to-complete performance index."*

- **CPI and SPI as first-class derived metrics** — P6 names *"performance indexes"* among its core EV outputs;
  Microsoft Project ships CV/SV/CPI/SPI reporting out of the box; Unanet shows CPI/SPI *"in context with metrics
  like ETC and EAC"*. · seen in: P6, Microsoft Project, Unanet, Cobra · priority: **table-stakes** · spine:
  **derived properties** on `CostControlAccount`: `cv`, `sv`, `cpi`, `spi` (division-by-zero guarded — AC or PV
  of 0 returns None, never a crash) · buildable now.
- **PV without a time-phasing engine** — P6's PV is *"the budgeted cost of work scheduled to be performed by a
  specified date"*; a real BCWS curve needs period phasing this pass does not build. The honest planning-grade
  stand-in: linear planned progress across the CA's planned window (fraction elapsed at the data date, 0 before
  start, 1 after finish), from the 7.2 dates. · seen in: simplified-EMA tools; documented deviation from P6 ·
  priority: **common** · spine: `pv` property with the simplification **stated in its docstring** (the 7.2
  `critical_path_ids` precedent) · buildable now.
- **EAC / ETC** — the bullet's headline. Unanet: *"EAC = Actuals + ETC"*, *not static*, rolling; the
  CPI-driven classic is `EAC = BAC / CPI`. · seen in: Unanet, P6 (*"estimates at completion"*), Cobra ·
  priority: **table-stakes** · spine: `eac` = `BAC / CPI` when AC > 0 else `BAC` (documented technique choice,
  one formula, no per-row method selector), `etc` = `EAC − AC` · buildable now.
- **TCPI (to-complete performance index)** — named verbatim in the bullet; the *pace you must now sustain*:
  `(BAC − EV) / (BAC − AC)`. · seen in: PMBOK-grade tools (Cobra, P6's full field set) · priority: **common** ·
  spine: `tcpi` derived property (guarded: `BAC − AC` of 0 → None) · buildable now.
- **VAC (variance at completion)** — `BAC − EAC`, the number an executive actually reads. · seen in: P6/Cobra
  field sets, PMBOK · priority: **common** · spine: `vac` derived property · buildable now.
- **Trend analysis** — the bullet's first word. Two honest shapes this pass: burn over `entry_date` from the
  expense rows themselves (no new table), and EAC movement visible through `core.AuditLog` + revision history. A
  dedicated EAC-snapshot-per-period table is P6's *Store Period Performance*. · seen in: Unanet (interactive
  charts), Scoro (burn charts), P6 (period metrics) · priority: **common** · spine: **no new table** — read-only
  burn aggregations in views; **charts are 7.16's**; an `EACSnapshot` table is the first thing to add if a
  tenant needs period-over-period EVM reporting (Deferred) · buildable now (aggregate lens).
- **Forecast revisions approved like budgets** — Unanet's rolling forecast; `accounting.Budget` already carries
  `version="forecast"` as a distinct version kind. · priority: **common** · **deferred** — a forecast-flavoured
  `BudgetRevision` (`revision_kind = baseline | forecast`) is a two-value extension reserved in the field list
  but not built this pass; the EAC property is the live forecast.
- **Over-budget alerts/thresholds** — the reason people look at CPI at all. Without a notification engine (no
  scheduler, 7.1's finding), the honest version is a derived health state rendered as a colour-named badge. ·
  seen in: Procore, Wrike, Scoro · priority: **common** · spine: `health` property (under / watch / over, from
  CPI and available-budget thresholds) → `badge-green/-amber/-red` on registers; **notification/reminder rules
  are 7.17's** · buildable now.

### Bullet 5 — Change Control & Budget Revisions
*"Formal change requests, impact analysis, and re-baseline approvals."*

- **A formal, numbered budget change request with a lifecycle** — Procore's change events are *"the starting
  point of Procore's change management workflow"*; Cobra keeps a budget change log. · seen in: Procore, Cobra,
  P6 (re-baselining) · priority: **table-stakes** · spine: `BudgetRevision` status machine
  `draft → pending_approval → approved | rejected → (superseded)` + `requested_by`, `reason`, `requested_at` ·
  buildable now.
- **Impact analysis before approval** — the bullet names it. Procore links change-event line items to budget
  codes and contracts so the financial impact is explicit before a CO issues. · seen in: Procore, P6 · priority:
  **table-stakes** · spine: `impact_note` + `schedule_impact_note` TextFields (schedule impact *ownership* is
  7.2's dates and 7.7's scope CRs — 7.4 records the note) + a **derived `amount_delta`** (sum of this revision's
  lines minus the current approved revision's, per category — the diff an approver needs) · buildable now.
- **An approval gate with named authority and evidence** — 7.1's verb model: POST-only, `@tenant_admin_required`
  where money authority matters, `core.AuditLog` row with previous/new status captured *before* mutation. ·
  seen in: Procore (CO approvals), Cobra (budget changes) · priority: **table-stakes** · spine: `bvr_submit` /
  `bvr_approve` / `bvr_reject` verbs; `decided_by` + `decided_at` stamps · buildable now.
- **Re-baselining: activate the approved revision, supersede the old baseline** — P6's *"recalculate costs to set
  the initial BAC"* after designating a new EV baseline; Cobra's budget change log. · seen in: P6, Cobra,
  Procore (budget revisions apply) · priority: **table-stakes** · spine: `bvr_activate` (POST, tenant_admin) —
  inside `transaction.atomic()` flips the prior approved revision to `superseded` and this one to `approved` +
  active; audit action `activate` / `supersede` · buildable now.
- **Version history that survives the re-baseline** — approved revisions are immutable (edit/delete refuse, the
  `bsl_edit`-on-frozen guard); every historical revision stays queryable. · seen in: Cobra, Procore · priority:
  **table-stakes** · spine: the rows themselves + `superseded_at` stamp · buildable now.
- **Rejection with a reason** — BrightWork's *"if rejected, explain why"* from 7.1 applies verbatim. · priority:
  **common** · spine: `bvr_reject` + `decision_notes` · buildable now.
- **Cross-module change linkage (scope CR → budget revision)** — 7.7 owns the CCB and scope CRs; no class exists
  yet. · priority: **common** · **deferred** — when 7.7 ships its `ChangeRequest` row, a nullable
  `source_change_request` FK on `BudgetRevision` is the one-line bridge; Ruling 3 records the vocabulary.

---

## Recommended build scope (this pass — 4 models)

All four are tenant-scoped `TenantNumbered` subclasses in `apps/projects/models/CostManagement/` (one file per
entity, same name in `forms/ views/ urls/`), full CRUD (list with working filters + create + detail + edit +
POST-only delete), templates under `templates/projects/cost/<entity>/{list,detail,form}.html`, re-export block
`# --- 7.4 Cost & Budget Management` in `apps/projects/models/__init__.py` (a missing re-export is a runtime
`ImportError`), migration `0004_…`, seeder block `_cost` with its own guard, tests `test_cost_*`.
All money is `DecimalField(14, 2)` through the existing `q2()` clamp; all metrics are **derived properties,
never stored columns** (the 7.1 ROI ruling); audit actions ≤ 10 chars.

1. **`ProjectBudgetLine`** [**PBL-**] — *one budgeted amount for one cost category against one project,
   optionally against one WBS node and one control account. The row the whole sub-module rolls up from.*
   Covers bullet **1 (Budget Planning & Estimation)** and carries bullet 5's substance (lines belong to a
   revision).
   Fields: `budget_revision` → `BudgetRevision` CASCADE (`related_name="lines"`) — **the line is only real
   inside a revision**; `project` → `projects.Project` CASCADE `related_name="budget_lines"` (denormalised for
   filters, `clean()`-checked against the revision's project); `category` (labor / material / equipment /
   subcontract / overhead / contingency / other — the bullet's four first, `max_length=14`); `wbs_node` →
   `projects.ProjectTask` SET_NULL null+blank `related_name="budget_lines"` (leaf or deliverable; bottom-up
   rollup source); `control_account` → `CostControlAccount` SET_NULL null+blank
   `related_name="budget_lines"`; `gl_account` → `accounting.GLAccount` PROTECT null+blank
   `related_name="project_budget_lines"`; `amount` DecimalField(14,2) `MinValueValidator(0)` (the 0002
   non-negative precedent); `note` TextField blank.
   `unique_together = ("tenant", "number")`; indexes `("tenant","project")` → `pbl_tnt_project_idx`,
   `("tenant","budget_revision")` → `pbl_tnt_rev_idx`, `("tenant","control_account")` → `pbl_tnt_ca_idx`.
   Derived (view-level): category totals, project total, per-CA BAC. **No `hours`, no `rate`** (Ruling 1).
   FKs (all verified): `BudgetRevision`, `projects.Project`, `projects.ProjectTask`, `CostControlAccount`,
   `accounting.GLAccount`.

2. **`BudgetRevision`** [**BVR-**] — *one version of a project's budget: revision 0 is the original plan, every
   later one is a formally requested, impact-analysed, approved (or rejected) re-baseline. The approved revision
   IS the cost baseline.*
   Covers bullets **1 (the planning document)** and **5 (Change Control & Budget Revisions)** — one table, both
   halves, exactly as the business case was folded onto `ProjectRequest` in 7.1.
   Fields: `project` → `projects.Project` CASCADE `related_name="budget_revisions"`; `revision_no`
   PositiveSmallIntegerField default 0; `title` CharField(255); `currency` → `accounting.Currency` SET_NULL
   null+blank (face-value sums, never converted); `status` (draft / pending_approval / approved / rejected /
   superseded — default `draft`); `reason` TextField (why this change); `impact_note` + `schedule_impact_note`
   TextFields blank (cost impact detail; schedule impact *ownership* stays 7.2/7.7); `requested_by` →
   AUTH_USER_MODEL SET_NULL null+blank; `requested_at` DateTimeField auto-set on the submit verb;
   `decided_by` / `decided_at` (editable=False, stamped by the approve/reject verbs);
   `activated_at` DateTimeField null+blank editable=False (the re-baseline stamp);
   `created_by` → AUTH_USER_MODEL SET_NULL null+blank editable=False.
   `unique_together = ("tenant","number")` + `("tenant","project","revision_no")` (two originals is a bug, not
   a limit); index `("tenant","project","status")` → `bvr_tnt_prj_status_idx`.
   **Derived property:** `amount_delta` — SUM(this revision's lines) − SUM(current active revision's lines),
   clamped via `q2()`; rendered on the detail page as the approver's headline number.
   **Verbs (POST-only):** `bvr_submit` (login, draft only), `bvr_approve` (**tenant_admin**, pending_approval
   only, stamps decided_by/_at — does NOT activate), `bvr_reject` (tenant_admin, stamps + `decision_notes`),
   `bvr_activate` (**tenant_admin**, approved only) — atomically supersedes the previously active revision
   (status → `superseded`, `activated_at` stamped) and marks this one active; writes audit `activate` /
   `supersede`. Approved/superseded rows refuse edit+delete (the `ScheduleBaseline` frozen-row guard).
   Reserved not built: `revision_kind` (baseline / forecast) for Unanet-style rolling forecast versions.
   FKs (all verified): `projects.Project`, `accounting.Currency`, AUTH_USER_MODEL.

3. **`CostControlAccount`** [**CCA-**] — *one EVM control structure for a slice of the project: the WBS anchor,
   the GL lens, the contingency hold, the attested progress — and every earned-value metric as a derived
   property.*
   Covers bullets **2 (Cost Baseline & Control Accounts)** and **4 (Forecasting & EAC)** — the metrics have no
   other honest home (Ruling 4).
   Fields: `project` → `projects.Project` CASCADE `related_name="control_accounts"`; `name` CharField(255);
   `code` CharField(30) (the CA identifier tenants already have — "CA-1.2"); `wbs_node` → `projects.ProjectTask`
   SET_NULL null+blank `related_name="control_accounts"` (a `deliverable` node or the project root —
   `clean()` same-project guard, the `anchor_task` pattern); `gl_account` → `accounting.GLAccount` PROTECT
   null+blank `related_name="project_control_accounts"`; `contingency` DecimalField(14,2) default 0
   MinValueValidator(0) (the CA-held reserve; sized by 7.5's analysis, recorded here — Ruling 6);
   `percent_complete` DecimalField(5,2) default 0, validators 0–100 (manually attested until 7.8's execution
   fields land — **the docstring must name the hand-off**); `status` (planning / baseline / active / closed —
   `baseline` set when the revision containing it activates; keep it simple: derive display from the active
   revision and leave `status` to planning/closed); `note` TextField blank.
   `unique_together = ("tenant","number")` + `("tenant","project","code")`; indexes
   `("tenant","project")` → `cca_tnt_project_idx`, `("tenant","status")` → `cca_tnt_status_idx`.
   **Derived properties (all documented, all guarded):**
   - `bac` — SUM of the **active** revision's `ProjectBudgetLine.amount` mapped to this CA (+ `contingency`
     only in the `bac_with_contingency` variant; PMBOK keeps them separable).
   - `ev` — `bac × percent_complete / 100`.
   - `pv` — `bac ×` linear fraction of the anchored node's (or project's) planned window elapsed at
     `timezone.localdate()`; **docstring states this is planning-grade, not a time-phased BCWS curve**.
   - `ac` — SUM of `ProjectExpense.amount` where `control_account = self` and `status = "posted"` and
     `entry_type in ("actual", "accrual")` (commitments excluded — they are `committed`, below).
   - `committed` — same aggregate, `entry_type = "commitment"`.
   - `available` — `bac − committed − ac`, `q2()`-clamped.
   - `cv = ev − ac`, `sv = ev − pv`, `cpi = ev/ac` (None when ac == 0), `spi = ev/pv` (None when pv == 0),
     `eac = bac/cpi` when cpi else `bac` (documented single-technique choice), `etc = eac − ac`,
     `tcpi = (bac − ev)/(bac − ac)` (None when denominator 0), `vac = bac − eac`.
   - `health` — under / watch / over from `cpi` and `available` thresholds → colour-named badge class dict
     (`badge-green/-amber/-red` only — the `-success/-danger` variants do not exist).
   FKs (all verified): `projects.Project`, `projects.ProjectTask`, `accounting.GLAccount`.

4. **`ProjectExpense`** [**PEX-**] — *one committed, actual, or accrued cost row against a project and control
   account — the spend side of every metric, with a soft reference to whichever procurement document caused it.*
   Covers bullet **3 (Expense Tracking & Commitments)**; feeds `ac`/`committed` into bullets 2 and 4.
   Fields: `project` → `projects.Project` CASCADE `related_name="expenses"`; `control_account` →
   `CostControlAccount` PROTECT `related_name="expenses"` (**required** — the cost code is what makes EVM math
   honest; a CA-less cost row would silently drop out of every index); `wbs_node` → `projects.ProjectTask`
   SET_NULL null+blank `related_name="expenses"` (finer than the CA when the tenant tracks it);
   `entry_type` (commitment / actual / accrual — default `actual`); `source_kind` (purchase_order /
   supplier_invoice / contract / timesheet / manual / accrual); `source_number` CharField(30) blank (e.g.
   `PO-00042`, `SIV-00187` — **a soft reference, never an FK**: 4.x/6.x own those engines and neither carries a
   project link; Ruling 5); `vendor` → `core.Party` SET_NULL null+blank `related_name="project_expenses"`;
   `gl_account` → `accounting.GLAccount` PROTECT null+blank `related_name="project_expenses"`; `amount`
   DecimalField(14,2) `MinValueValidator(0)` (reversals are negative adjustments through paired rows if ever
   needed — keep the column non-negative like the 0002 precedent and record the void via status);
   `currency` → `accounting.Currency` SET_NULL null+blank (defaults to the revision's currency in the form);
   `entry_date` DateField (the burn-trend dimension); `status` (draft / posted / void — default `draft`);
   `description` CharField(255) blank; `created_by` → AUTH_USER_MODEL SET_NULL null+blank editable=False.
   `unique_together = ("tenant","number")`; indexes `("tenant","project")` → `pex_tnt_project_idx`,
   `("tenant","control_account")` → `pex_tnt_ca_idx`, `("tenant","entry_type")` → `pex_tnt_etype_idx`,
   `("tenant","entry_date")` → `pex_tnt_date_idx`.
   **Verbs (POST-only):** `pex_post` (login, draft → posted, audit `post`), `pex_void` (**tenant_admin**,
   posted → void, audit `void`; void rows stay visible and stop counting — the audit trail keeps the original).
   FKs (all verified): `projects.Project`, `CostControlAccount`, `projects.ProjectTask`, `core.Party`,
   `accounting.GLAccount`, `accounting.Currency`, AUTH_USER_MODEL.

**Auto-number prefixes to reserve:** `PBL`, `BVR`, `CCA`, `PEX` — **all four verified free** across `apps/`
(see the collision check below). No shared `PRJ`-style precedent mess this time.

**Trade-offs I am consciously accepting (state them in the code):**
- **Bullet 1 and bullet 5 share `BudgetRevision`** rather than getting separate `ProjectBudget`-header and
  `BudgetChangeRequest` tables. The lifecycle is genuinely one object (a change request that is approved *is*
  the next budget version); two tables would need a third to reconcile them. If a tenant ever wants what-if
  budget *scenarios* (not just sequential revisions), that is the moment to add `budget_type = baseline |
  what_if` — a two-value migration, exactly like 7.2's `baseline_type`.
- **EV progress is a CA-level manual attestation**, not task-level. It is the single most likely future edit
  (7.8 will put execution progress on `ProjectTask`); the `percent_complete` docstring must say "superseded by
  7.8" so nobody mistakes it for a permanent design.
- **PV is linear, not time-phased.** Documented simplification, the same honesty as 7.2's critical path. If a
  tenant needs period curves, that is an `EVMPeriod` table + a real EVMS conversation (Deferred).
- **If the pass runs long, `ProjectBudgetLine`'s `wbs_node` and `gl_account` FKs are the first trims** — the
  model degrades to project+category level budgeting, still functional; nothing else depends on those two being
  populated (both nullable for exactly this reason).

**Sidebar entry to add — `LIVE_LINKS["7.4"]`:**

```python
"7.4": {
    "Budget Planning & Estimation":      "projects:pbl_list",
    "Cost Baseline & Control Accounts":  "projects:cca_list",
    "Expense Tracking & Commitments":    "projects:pex_list",
    "Forecasting & EAC":                 "projects:cca_list",   # EAC/CPI/SPI/TCPI/VAC render on the CA register + detail
    "Change Control & Budget Revisions": "projects:bvr_list",
    "Budget Register":                   "projects:pbl_list",    # extra live leaf, 7.2's "Task Register" precedent
}
```
Bullet 4 maps to the same register as bullet 2 on purpose — the EVM columns are CA columns, and 7.1/7.2 both
established that a bullet may be a *lens* on a register rather than a new page (`?status=submitted`,
`?node_type=work_package`). If the pass wants a distinct destination, a project-cost rollup section on the
overview page is the cheap honest option — **not** a dashboard (7.16).

**Seeder sketch (`_cost`, own guard):** per tenant — revision 0 (`approved`+active) on each seeded project with
7–10 lines across all categories anchored to the existing WBS work packages; one CA per deliverable of the
active project with percent_complete values that make the seeded CPI land in all three health bands; ~12
`ProjectExpense` rows (commitment rows referencing the seeder's world honestly — `source_number="PO-…"` strings
only, since `scm.PurchaseOrder` rows are not guaranteed to exist in a bare workspace; actual + one accrual pair);
one `pending_approval` revision with a visible positive `amount_delta`. `--flush` deletes children-first:
`ProjectExpense, ProjectBudgetLine, CostControlAccount, BudgetRevision`.

---

## Naming-collision check (performed, not assumed)

For each proposed class — `ProjectBudgetLine`, `BudgetRevision`, `CostControlAccount`, `ProjectExpense` — and for
the near-miss vocabulary (`ControlAccount`, `CostBaseline`, `ProjectBudget`, `BudgetChange`, `Commitment`,
`CostAccount`, `ChangeRequest`, `ExpenseItem`):

- `grep -rn "class <Name>" apps/` → **no hits for any of them.** No model anywhere in the repo carries these
  names, so no collision within `app_label = "projects"` (or across apps).
- `grep` over `.claude/tasks/contract-projects-7.2.md` → 7.2 froze only `ProjectTask`, `TaskDependency`,
  `ProjectMilestone`, `ScheduleBaseline` + their forms/views/url names (`tsk_ dep_ mst_ bsl_`). **None of 7.4's
  four names, stems (`pbl_ bvr_ cca_ pex_`), or path prefixes (`budgetlines/ revisions/ controlaccounts/
  expenses/`) collide.** `ScheduleBaseline` and 7.4's cost baseline are deliberately differently-named objects
  (Ruling 2).
- `ls .claude/tasks/ | grep project` → **no `research-projects-7.3.md`, no `contract-projects-7.3.md`** (and no
  `ResourceManagement/` code in the app). The 7.3 boundary is recorded as a unilateral ruling (Ruling 1) and
  must be re-verified when 7.3's contract lands; none of 7.4's names claim resource vocabulary
  (`rate`, `resource`, `allocation` appear nowhere in the proposed field lists), so the collision surface with a
  not-yet-written 7.3 is empty by construction.
- Prefixes `PBL` / `BVR` / `CCA` / `PEX`: `grep -rl 'NUMBER_PREFIX = "<X>"' apps/` → **zero files for each**
  (the inventory of existing prefixes was checked in full; `PRJ` ×3 and `CR` ×1 are the only relevant squats and
  none of the four touches them). URL stems and template folders verified unused under `apps/projects/` and
  `templates/projects/`.
- Templates: `templates/projects/cost/` does not exist yet (7.1 used `initiation/`, 7.2 used `planning/`).
- Test namespace: `test_cost_*` / `cost_*` / `_cost_*` does not collide with `test_initiation_*` /
  `test_planning_*` (7.1/7.2's naming-convention guard).
- Migration: next incremental is `0004_…` (7.2 shipped `0003`).

---

## Belongs to sibling sub-modules (parked, not scoped here)

- **Timesheets, time approval, resource pool, rate cards, allocation & leveling** → **7.3 / 7.11** (Ruling 1).
  Labor actuals *flow into* `ProjectExpense(source_kind="timesheet")` once the timesheet spine repoints to
  `projects.ProjectTask` — the `hrm.TimesheetEntry.project → accounting.Project` FK is the standing stand-in.
- **Scope change requests, CCB, requirements** → **7.7** (Ruling 3). `BudgetRevision` is the cost expression;
  the FK bridge waits for 7.7's row.
- **Risk register, Monte Carlo, EMV, contingency sizing** → **7.5** (Ruling 6). 7.4 records the contingency
  amount; 7.5 justifies it.
- **Client billing, revenue recognition, A/R, margin** → **7.15**. It consumes 7.4's EVM properties (Ruling 4);
  7.4 builds no revenue-side row at all.
- **Portfolio rollups, cross-project cost heat maps, capacity/cost pipeline** → **7.12**. The single biggest
  resist: no portfolio-level budget aggregation table this pass.
- **Charts, dashboards, report builder, exports** → **7.16**. Burn charts, CPI trend lines and the executive
  cost pack are 7.16's; 7.4 renders badges and tables.
- **Approval workflow designer, auto-approval thresholds, notifications** → **7.17**. 7.4's approval is a fixed
  status machine with explicit verbs (7.1's pattern); over-budget alerts are badges, not notifications.
- **Task execution, assignments, actual progress on tasks** → **7.8**. It supersedes the CA-level
  `percent_complete` attestation.
- **The procurement document engines (PO amendments, supplier-invoice lifecycle)** → **4.x / 6.x**. 7.4 records
  `source_number` references and never operates those lifecycles (Ruling 5).
- **The GL and the 2.9 job-costing bridge** → **2.x**. 7.4 FKs `GLAccount` as a lens; the
  `accounting.Project ↔ projects.Project` consolidation is a spine migration, not a sub-module pass.

---

## Deferred (later passes / integrations)

| Area | Why deferred |
|---|---|
| **Time-phased EVM (period BCWS/BCWP curves, P6 "Store Period Performance", an `EVMPeriod` snapshot table)** | Needs a period-cost table and a scheduling engine; P6/Cobra territory. 7.4 ships linear-PV planning-grade metrics, the same documented simplification class as 7.2's critical path. First table to add for period-over-period EVM reporting. |
| **`EACSnapshot` per CA per period for trend charts** | Trend is answerable read-only from `ProjectExpense.entry_date` burn + audit history this pass; charts belong to 7.16 anyway. Add only when a tenant needs period EVM history. |
| **What-if budget scenarios (`budget_type = baseline \| what_if`)** | A two-value migration when wanted (7.2's `baseline_type` precedent). Sequential revisions cover the formal re-baseline bullet. |
| **`revision_kind = forecast` rolling forecast versions** | Unanet-style forecast versioning is one choice-value on `BudgetRevision`; reserved in the field list, not built — the live EAC property is the forecast until then. |
| **Rate-based labor budgeting / hours × rate generation** | 7.3 owns rate cards (Ruling 1). 7.4 rows stay amounts; a 7.3 generator may write them later. |
| **Timesheet → labor-actual synchronisation** | Needs `hrm.TimesheetEntry` repointed to `projects.ProjectTask` (7.3/7.11's migration) plus a sync verb. `source_kind="timesheet"` reserves the vocabulary. |
| **Commitment change-order sub-workflow (PCO/CCO per Procore)** | The PO amendment engine is 4.x/6.x's; a commitment delta is an audited `ProjectExpense` adjustment row here. |
| **Top-down budget target rows and reconciliation variance** | Would be a fifth model (a per-project top-down target set). 7.2 already owns the *estimating method* vocabulary; the money-side reconciliation needs its own row set first. |
| **Management reserve as a separate above-baseline bucket** | Cobra's MR distinction; folded into `CostControlAccount.contingency` this pass. One column when a DCMA-grade tenant appears. |
| **FK `BudgetRevision.source_change_request` → 7.7's ChangeRequest** | 7.7's model does not exist yet (verified). One-line bridge when it lands (Ruling 3). |
| **Multi-currency conversion (FX) on project cost** | `accounting.Currency` is a label master; sums are at face value everywhere in this repo (the `procurement.CostForecast.currency` wording). FX is 2.x/7.15's. |
| **Accounting bridge: `accounting.Project ↔ projects.Project` link, cost postings to GL** | 2.x owns the ledger (L29); `JobCostEntry` posts JEs. A nullable link is the parked spine consolidation, not a 7.4 feature. |
| **Over-budget notifications, escalation, reminder rules** | No mail worker / scheduler (6.8/6.19/7.1 all recorded it). 7.17's. Badges and audit rows only this pass. |
| **Portfolio-level cost rollups and heat maps** | 7.12. The project is the highest aggregation this pass builds. |
