# Research — Sub-module 7.1: Project Initiation & Charter (Module 7 — Project Management, `projects`)

> **Read this first.** 7.1 is the **front door** of Module 7: it turns an unfiltered stream of "we should do X"
> into a *chartered, sponsored, stakeholder-mapped, kicked-off* project. It is **not** planning (7.2 owns WBS,
> sequencing, critical path and the schedule baseline), **not** resourcing (7.3), **not** budgeting (7.4), **not**
> the risk register (7.5), and **not** the requirements register (7.7) — all five of those bullets are one word away
> from 7.1's and all five belong to siblings. The failure mode for this pass is **building a mini-PPM in one run**:
> portfolio scoring models, configurable intake forms, approval workflow engines, dashboards and AI re-scoring are
> all real features in the products surveyed and all of them are explicitly 7.12 / 7.17 / 7.16 / 7.19's.
>
> **The other failure mode is duplicated masters.** Module 7 is greenfield but *two* `PRJ-`-numbered project
> records already exist in the repo (`accounting.Project` from 2.9 and `crm.CrmProject` from 1.8). See the ruling
> below — this pass adds a third `PRJ-` model deliberately, documents the other two as pre-spine stand-ins, and
> touches neither.

---

## Repo state checked first

### LIVE_LINKS built so far in Module 7 (`apps/core/navigation.py`)

**None.** `grep -c '"7\.' apps/core/navigation.py` → **0**. The last sub-module key in the dict is `"6.19"` at
`navigation.py:1690`. Module 7 is fully greenfield.

What *is* built elsewhere (verified keys, for FK context): `0.1–0.14` (core), `1.1–1.12` (CRM), `2.1–2.15`
(accounting, fully built), `3.1–3.41` (HRM, near-complete), `4.1–4.19` (SCM), `5.1–5.20` (inventory, most),
`6.1–6.19` (procurement).

### The app does not exist yet

- `ls apps/projects` → **No such file or directory.**
- `apps.projects` is **not** in `INSTALLED_APPS` (`config/settings.py:46-55` = core, accounts, tenants, dashboard,
  crm, accounting, hrm, scm, inventory, procurement).

So this pass creates the app skeleton (`apps/projects/{models,forms,views,urls}/…` + `apps.py` + `_base.py` +
`templates/projects/…`), adds it to `INSTALLED_APPS`, and wires one `LIVE_LINKS["7.1"]` block.

### The `Item` question — answered with grep (L28: the ERD is intent, the grep is truth)

The research brief flagged that Module 5 is built so a real `Item` master may now exist. **It does — and it is not
where the ERD or the `/next-module` skill says it is.**

```
apps/scm/models/InventoryManagement/Items.py:73:class Item(TenantOwned):
apps/scm/models/InventoryManagement/Items.py:51:class UOM(TenantOwned):
apps/scm/models/InventoryManagement/StockMoves.py:13:class StockMove(TenantOwned):
apps/scm/models/InventoryManagement/LotSerials.py:5:class LotSerial(TenantOwned):
```

- **There is no `core.Item` and no `inventory.Item`.** `grep -rn "^class Item" apps/core/models/
  apps/inventory/models/` returns nothing.
- `apps/inventory/` **does** exist and is populated, but its catalog package only holds *peripheral* models that FK
  across to SCM: `apps/inventory/models/Catalog/ItemPrices.py:19 class ItemPrice(TenantOwned)` with
  `item = models.ForeignKey("scm.Item", …)` at line 29-30. That is the proof: **module 5 itself treats
  `scm.Item` as the item master.**
- So the `/next-module` module table's note *"Item/Location/StockMove/LotSerial/UOM are NOT built yet — Module 5
  will own them"* is **stale**. `scm` (4.3 Inventory Management) built them and `inventory` extends them, exactly
  the L36 pattern (`scm` owns the transactional spine, later modules extend by FK).
- **7.1 does not need `Item` at all** — no material line items in a charter. Recorded here so the next run does not
  re-derive it.

### Spine entities VERIFIED to exist (grep evidence)

| Entity | Verified at | What 7.1 uses it for |
|---|---|---|
| `core.Tenant` | `apps/core/models/Tenant.py:5` | tenant scoping via `TenantOwned`/`TenantNumbered` |
| `core.Party` | `apps/core/models/Party.py:5` | the **stakeholder / requesting organisation / client** identity. Customers, vendors, suppliers, employees, leads, contacts are all `PartyRole` rows — never re-declare one. |
| `core.PartyRole` | `apps/core/models/PartyRole.py:5` | lets a stakeholder register show *why* a party is on the project (customer / vendor / partner / employee). |
| `core.OrgUnit` | `apps/core/models/OrgUnit.py:5` | the owning/delivery department. Has `KIND_CHOICES` company/branch/department/team/**cost_center** and a self-FK `parent`. |
| `core.Activity` | `apps/core/models/Activity.py:5` | **the kickoff meeting and its onboarding action items.** `KIND_CHOICES` already carries `task`/`call`/`email`/`meeting`/`note`, has `status` open→in_progress→done→cancelled, `due_at`, `owner`, `party`, and a **GenericForeignKey** to attach to any record. This is why bullet 5 does not need its own child table. |
| `core.Document` | `apps/core/models/Document.py:5` | the signed charter PDF / supporting attachment (GFK + `file` + `classification`). 6.19's ruling applies: **do not extend or replace it**; a charter PDF is a one-off attachment, not a controlled repository document. |
| `core.Employment` | `apps/core/models/Employment.py:5` | the employment record behind an internal stakeholder (via `EmployeeProfile`). |
| `core.AuditLog` + `core.utils.write_audit_log` | `apps/core/models/AuditLog.py:5`; `apps/core/utils.py:6` | audit rows for the go/no-go decision, charter approval and kickoff-completion verbs. |
| `core.utils.next_number` | `apps/core/utils.py:34` | the `PRQ-` / `PRJ-` / `PST-` / `PKO-` prefixes via `TenantNumbered` (retry-on-collision guard lives in `TenantNumbered.save()`, `apps/scm/models/_base.py:66-86` is the reference implementation to copy). |
| `accounting.Currency` | `apps/accounting/models/GeneralLedger/Currencies.py:6` | the currency on a request's cost/benefit estimate. **Read-only — no ledger effect (L29).** |
| `accounting.GLAccount` | `apps/accounting/models/GeneralLedger/GLAccounts.py:5` | verified but **deliberately not FK'd this pass** — cost accounts are 7.4's. |
| `accounting.Budget` | `apps/accounting/models/Budgeting/Budgets.py:6` | verified but **not FK'd** — the budget baseline is 7.4's. |
| `accounting.Project` **[PRJ-]** | `apps/accounting/models/ProjectCosting/Projects.py:6` | ⚠️ **exists.** The 2.9 job-costing lens: `client`→Party, `org_unit`, `billing_method`, `budget_amount`, status planning/active/on_hold/closed, derived `actual_cost()` / `actual_revenue()` / `margin()` from `JobCostEntry`. See ruling. |
| `accounting.JobCostEntry` | `apps/accounting/models/ProjectCosting/JobCostEntries.py:5` | the posted cost/revenue rows 2.9 derives actuals from. **7.1 must not build a second cost ledger.** |
| `crm.CrmProject` **[PRJ-]** | `apps/crm/models/ProjectDelivery/Projects.py:6` | ⚠️ **exists.** The 1.8 post-sale delivery lens: `account`→Party, `source_opportunity`, status planning/active/on_hold/completed/cancelled, `budget`, `owner`→User, derived `progress_pct` (completed÷total milestones) and `is_overdue`. See ruling. |
| `crm.CrmMilestone` | `apps/crm/models/ProjectDelivery/Milestones.py:5` | ⚠️ **exists** (1.8). 7.2 will need a `Milestone` for schedule milestones — it must decide whether to extend this or declare `projects.Milestone`. Not 7.1's call; flagged for the 7.2 run. |
| `crm.Opportunity` | `apps/crm/models/SalesForceAutomation/Opportunities.py:5` | the optional "this project came from a won deal" provenance FK (1.8 already models it as `CrmProject.source_opportunity`). |
| `hrm.EmployeeProfile` | `apps/hrm/models/EmployeeManagement/EmployeeProfiles.py:8` | the internal-person anchor (`OneToOne` over `core.Party` + `core.Employment`). Its docstring says *"All other HRM models FK to this, never to core.Party directly"* — projects is not HRM, so 7.1 FKs `core.Party` and reaches `party.employee_profile` when it needs HR detail. |
| `hrm.DepartmentProfile` | `apps/hrm/models/OrganizationalStructure/Department.py:5` | **Note the name — there is no `hrm.Department`.** Not needed by 7.1 (`core.OrgUnit` is the right org FK, as `accounting.Project.org_unit` already does). |
| `scm.Item` / `scm.UOM` | `apps/scm/models/InventoryManagement/Items.py:73` / `:51` | verified, **not used by 7.1**. |

### Spine entities VERIFIED NOT to exist

1. **No `core.Project`.** `NavERP-ERD.md:341` and `research-crm-1.7-1.12.md:499` both speak of a
   `core_project` / `core.Project` with `number "PRJ-#####"`. **`grep -rn "^class Project" apps/*/models/`
   returns only `accounting.Project` and `crm.CrmProject`.** The ERD's `core.Project` is unbuilt intent — do not
   FK it.
2. **No `projects` app, no `7.*` LIVE_LINKS, no `projects` tables at all.**
3. **No form-builder / custom-field engine anywhere.** NavERP ships fixed model fields; there is no dynamic
   question store. Configurable intake forms are therefore 7.19's (*Custom Fields & Forms*), not 7.1's.
4. **No mail worker / no scheduler.** The procurement 6.8 and 6.19 passes both record this: renewal and reminder
   scans are user-pressed verbs, not cron jobs. 7.1's approval notifications are **in-app only**.
5. **No weighted-scoring / prioritisation-model table.** `grep` finds no `Scorecard`, `ScoringModel` or
   `PriorityModel` anywhere. Per-request scores in 7.1 are plain numeric columns; the *reusable scoring model* is
   7.12's (*Strategic Alignment & Scoring*).

### Sibling research files checked

`ls .claude/tasks/ | grep -i project` → **empty** (confirmed: no prior Module 7 research). The two files that
mention a project record are older and out of scope for 7.1's decision: `research-accounting-advanced.md:662`
(a 2.9 `Project` row in a model table) and `research-crm-1.7-1.12.md:497` (the 1.8 `CrmProject`). Neither
catalogued intake, business case, charter, stakeholders or kickoff, so **this is a fresh backlog**.

Format reference read: `.claude/tasks/research-procurement-6.19.md` (same house style: repo-state table with
grep line numbers, ruled either/or decisions up front, per-bullet feature catalog, 1–4 model build scope,
parked-to-sibling list, deferred table).

---

## THE RULING — does `Project` [PRJ-] land in 7.1 or 7.2?

**Decision: 7.1.** 7.1 ships `Project` [PRJ-]. 7.2 inherits it and adds the planning structure around it.

### The case for 7.2

- NavERP.md's 7.2 bullet list opens with *"Work Breakdown Structure (WBS) — hierarchical task decomposition"*, and
  in every product surveyed the WBS root **is** the project record. If the WBS root is 7.2's, the root arguably is
  too.
- 7.2 owns *"Schedule Baseline & Version Control — frozen baselines"*, and a frozen baseline is what makes a
  project's dates authoritative. One could argue the project only becomes "real" once it has a baseline.
- The `/next-module` module table groups `Project[PRJ-], ProjectTask, Milestone, Timesheet[TS-], RiskItem,
  ChangeRequest[CR-]` — a cluster that reads like a 7.2 planning group, and it assigns `Project` no sub-module.
- Deferring keeps 7.1 a pure "intake" pass and avoids shipping a container with nothing in it yet.

### The case for 7.1 — and why it wins

- **Every surveyed product creates the project at *initiation*, not at WBS time.** ServiceNow: *"once a demand is
  approved, it can be smoothly converted into a Project, Enhancement, or Change Request."* Clarity: *"You can now
  convert an approved idea into a project using a template."* BrightWork 365's terminal intake stage is literally
  named **"Create Project"** (`Draft → Accept → Review → Approve → Create Project`). Wrike: submitting a request
  form *"Creates a task, a project, a custom item type or a blueprint"* and populates it from the form. Intake that
  cannot produce a project is a form, not a pipeline.
- **PM² (via OpenProject) settles it explicitly.** The Initiating Phase produces **three** artefacts — Project
  Initiation Request, Business Case, Project Charter — and then: *"5.5 Phase Gate RfP (Ready for Planning) … A
  review and approval are recommended before the project can formally move to the next phase."* 7.2 *is* what
  happens after that gate. A project record must therefore exist **before** planning begins.
- **A charter with nothing to charter is an orphan.** Scope, objectives, success criteria and executive sponsor are
  attributes *of a project*. Without `Project` in 7.1, bullets 1–5 would all need nullable FKs to a table that does
  not exist until 7.2 — the exact fragile pattern the spine rules warn against (and the reason `core.Project` in
  the ERD has quietly stayed unbuilt for six modules).
- **The tie-break in the module table favours 7.1.** `Project[PRJ-]` is listed with no sub-module assignment; the
  rule is "first sub-module that needs it", and four of 7.1's five bullets need it versus arguably one of 7.2's.

### What 7.1 ships vs what 7.2 inherits

- **7.1 owns the project's *identity and authorisation*:** number, name, charter content (scope, objectives,
  success criteria, assumptions, constraints), executive sponsor, manager, owning `OrgUnit`, target dates as
  *charter-level intent*, and the lifecycle states from draft through chartered to kickoff.
- **7.2 inherits `Project` unchanged as an identity** and adds the *planning structure* that FKs it: a WBS/work-item
  tree, predecessor/successor dependencies with lag/lead, duration & effort estimating with confidence ranges,
  milestone & phase-gate definitions, and the frozen `ScheduleBaseline` **+ baseline versions** (7.1's
  `start_date`/`end_date` stay mutable charter targets; the frozen copies live on 7.2's baseline rows).
- 7.2 also inherits the still-open question of whether to reuse `crm.CrmMilestone` (1.8) or declare
  `projects.Milestone`.

### The second ruling this forced — the `PRJ-` collision

`accounting.Project` (2.9, job costing) and `crm.CrmProject` (1.8, post-sale delivery) **both** already use
`NUMBER_PREFIX = "PRJ"`. Shipping `projects.Project` with `PRJ-` makes three.

**Decision: ship it, and document the other two as pre-spine stand-ins.** This is the documented
`crm.PurchaseOrder` precedent in reverse: when the spine master's owning module finally builds it, the earlier
lens-specific copies are re-labelled as stand-ins rather than migrated under time pressure. Concretely:

- `projects.Project` is **the** Module 7 project master going forward. Its docstring must state that
  `accounting.Project` (2.9 financial lens) and `crm.CrmProject` (1.8 delivery lens) are pre-spine stand-ins and
  that both are candidates to later carry a nullable `projects.Project` link.
- **Do not touch modules 1 and 2 this pass.** They are built, tested and live in the sidebar; a merge is its own
  migration.
- Prefixes stay as they are (numbers are per-tenant per-model, so `PRJ-00001` meaning three different rows across
  three apps is ugly but not a key collision — `unique_together = ("tenant", "number")` is per model).

---

## Leaders surveyed (with source links)

The domain here is **project intake / demand management / business case / project chartering** — i.e. PPM and
intake tools — not generic "project management software".

1. **Planview** — enterprise PPM / strategic portfolio management; a Gartner SPM Magic Quadrant Leader five years
   running. The reference for *structured intake + objective scoring*. <br>
   [Demand Management](https://www.planview.com/lp/demand-prioritization/) ·
   [Planview ProjectAdvantage reviews (G2)](https://www.g2.com/products/planview-projectadvantage/reviews)
2. **ServiceNow Strategic Portfolio Management — Demand Management** — the reference for *demand-to-project
   automation* and for the idea→demand→project conversion path. <br>
   [Demand Management](https://www.servicenow.com/products/demand-management.html) ·
   [ServiceNow Demand Management guide (Surety Systems)](https://www.suretysystems.com/insights/servicenow-demand-management-guide-surety-systems/)
3. **Broadcom Clarity** — the reference for *ideas as a governed object with a conversion-to-project action*. <br>
   [Capture, Develop, and Approve New Ideas (techdocs)](https://techdocs.broadcom.com/us/en/ca-enterprise-software/business-management/clarity-project-and-portfolio-management-ppm-on-premise/16-3-1/using/new-user-experience-capture-develop-and-approve-new-ideas.html)
4. **Microsoft 365 / Power Platform project-intake (BrightWork 365)** — the most *concretely documented* intake
   pipeline: intake form fields, a request "command centre", 0–3-stage Power Automate approval flows, and
   carry-over of request data into the created project. <br>
   [A Quick Guide to Project Request Management](https://www.brightwork.com/blog/a-quick-guide-to-project-request-management)
5. **Jira Product Discovery (Atlassian)** — the reference for *configurable scoring fields and formulas* (impact,
   effort, RICE) and for stakeholder voting/commenting on ideas. <br>
   [Jira Product Discovery features](https://www.atlassian.com/software/jira/product-discovery/features)
6. **Asana** — two sources: how Asana's own PMO runs intake, and its initiation methodology page, which is the
   clearest statement of *charter vs business case* and of the influence/interest grid. <br>
   [How Asana uses work management to streamline project intake](https://asana.com/resources/asana-on-asana-project-intake) ·
   [Project initiation: 4 steps](https://asana.com/resources/project-initiation)
7. **Wrike** — the reference for *request forms as a first-class object* (question types, "Creates", "Saves to",
   "Visible to", external public links, submission counters, auto-start of an approval). <br>
   [Request Forms in Wrike (Help Center)](https://help.wrike.com/hc/en-us/articles/1500005122521-Request-Forms-in-Wrike) ·
   [Custom Request Forms](https://www.wrike.com/features/custom-request-forms/)
8. **Planisware Orchestra** — the reference for *phase-gate governance*: gates composed of deliverables plus
   financial *and* qualitative criteria organised in a scorecard, decided by named gate-keepers. <br>
   [How to successfully manage a phase and gate process](https://planisware.com/resources/work-management-collaboration/how-successfully-manage-phase-and-gate-process-planisware)
9. **OpenProject / PM² methodology** — the reference for the *artefact set* of the initiating phase (Project
   Initiation Request → Business Case → Project Charter → "Ready for Planning" gate) and for per-artefact
   **RASCI** tables. <br>
   [5 Initiating Phase](https://www.openproject.org/docs/project-management-guide/5-initiating-phase/)

**Considered and not cited:** *Smartsheet* appears as a leader in every 2026 PPM comparison surveyed, but every
Smartsheet page tried this run (product, template-gallery and help-centre URLs, plus its charter PDF) returned
404 through the fetcher, so **no Smartsheet-specific feature claims are made below**. *Monday.com*'s public work-
management page is now entirely AI-agent positioning with no intake detail; *Oracle Primavera P6 EPPM* and
*Airtable* have no meaningful initiation/chartering surface to read. All three were checked and dropped rather
than cited second-hand.

---

## Feature catalog (this sub-module only)

Priority key: **table-stakes** (nearly every leader has it) · **common** (most have it) · **differentiator** (a few
standouts).

### Bullet 1 — Project Request & Intake
*"Standardized request forms, stakeholder submission portals, and demand pipeline tracking."*

- **One standardised intake form capturing the same fields every time** — the whole point of intake; it converts
  unstructured asks into comparable data. Asana's own PMO lead: *"A form lets you take unstructured data and turn
  it into structured data."* Fields named in the market: project owner, name, description and objectives, proposed
  timelines with a final deadline, budget, known risks and constraints, required resources, **project sponsor**,
  metrics/KPIs, supporting documentation (BrightWork); description + customer needs + assigned PM
  (BrightWork 365). · seen in: Asana, BrightWork/Microsoft, Wrike, ServiceNow, Clarity · priority:
  **table-stakes** · spine: **new table `ProjectRequest`** · buildable now.
- **A typed request** — new project / enhancement / change request / defect repair / idea, because the routing and
  the depth of assessment differ per type. ServiceNow's intake covers *"new products, services, enhancements, and
  defect repairs"* plus Idea Management. · seen in: ServiceNow, Wrike (item type chosen per form), Clarity ·
  priority: **common** · spine: `request_type` choices on `ProjectRequest` · buildable now.
- **A visible demand pipeline / request backlog with status stages** — one queue everyone can filter. BrightWork's
  SharePoint template uses **Draft → Review → Pending Decision → Approved/Rejected**, and can be sent *back* a
  stage for more information at any point; BrightWork 365 tracks *Drafting, Accepting, Reviewing, Approval*.
  · seen in: BrightWork/Microsoft, ServiceNow (Demand Workbench with customisable filters), Planview, Clarity
  (Ideas grid), Asana · priority: **table-stakes** · spine: `status` choices on `ProjectRequest` **including an
  explicit "returned for information" state** · buildable now.
- **Anyone can submit; a named requester is recorded** — BrightWork: *"Requested By"*, *"Reviewer"*, *"Approver"*
  are separate named people, all automatically alerted; PM² says *"Anyone can introduce a Project Initiation
  Request"*. · seen in: BrightWork/Microsoft, PM²/OpenProject, Clarity (*"from throughout your organization and
  from partners and customers"*) · priority: **table-stakes** · spine: `requested_by` → `AUTH_USER_MODEL` +
  `requester_party` → `core.Party` (nullable, for the external/partner submitter) · buildable now.
- **Named reviewer and approver on the request** — decisions have owners · seen in: BrightWork/Microsoft,
  ServiceNow (demand manager role), PM² (Project Owner, Appropriate Governance Body) · priority: **table-stakes** ·
  spine: `assigned_reviewer` / `assigned_approver` → `AUTH_USER_MODEL` · buildable now.
- **Request provenance and org context** — where the demand came from and which part of the business owns it ·
  seen in: Clarity (ideas from partners *and* customers), BrightWork (per-department intake), ServiceNow ·
  priority: **common** · spine: `source` choices (portal / internal / idea / opportunity / email) + `org_unit` →
  `core.OrgUnit` + optional `source_opportunity` → `crm.Opportunity` (the 1.8 precedent:
  `CrmProject.source_opportunity`) · buildable now.
- **Multi-stage approval before the project exists** — BrightWork 365 ships four business-process flows with
  **0, 1, 2 or 3 approval stages** before project creation; PM² distinguishes informal approval (Project Owner
  accepts) from formal (a governance body reviews and approves). · seen in: BrightWork/Microsoft, PM², ServiceNow
  (*"customizable process flows … tailored stages, approval gates"*) · priority: **common** · spine: a **static**
  status machine + explicit POST-only approve/reject/return verbs on `ProjectRequest`. **A configurable workflow
  designer is 7.17's** · buildable now (fixed shape).
- **Convert an approved request into a project, carrying its data over** — the single most important mechanic in
  this bullet. BrightWork: *"carry over the key information filled in at the Drafting stage to the new project
  site … ensure the new project has the strategic alignment information used in the governance/approval process"*;
  ServiceNow converts to a Project/Enhancement/Change Request; Clarity converts an approved idea via
  *Create from Template*; Wrike's form creates and populates the project directly. · seen in: BrightWork/Microsoft,
  ServiceNow, Clarity, Wrike, Planview · priority: **table-stakes** · spine: a POST-only **"Convert to project"**
  verb on `ProjectRequest` that creates the `Project` and stamps `Project.request` (nullable self-documenting FK) ·
  buildable now.
- **External / public submission link** — Wrike request forms support *"Shared publicly"* with a public link for
  non-account submitters, and Clarity captures demand *"from partners and customers"*. · seen in: Wrike, Clarity ·
  priority: **common** · **deferred** — an unauthenticated write endpoint is a real security surface (spam, PII,
  tenant-isolation). 7.1 ships authenticated submission with a `core.Party` requester; the portal is 7.14's.
- **Dynamic / conditional intake forms** — Wrike's forms change questions based on earlier answers · seen in:
  Wrike · priority: **differentiator** · **deferred → 7.19** (*Custom Fields & Forms*). NavERP has no form-builder.
- **Requester-facing status tracking and comments** · seen in: BrightWork/Microsoft, Wrike · priority: **common** ·
  spine: the request's detail page + `core.AuditLog`; threaded discussion is 7.9's · buildable now (read-only
  history).

### Bullet 2 — Business Case & Feasibility
*"Cost-benefit analysis, ROI modeling, risk-adjusted return calculations, and go/no-go gates."*

- **Cost and benefit estimates on the demand record** — so a request can be ranked on economics rather than volume ·
  seen in: ServiceNow (*"key metrics for prioritization, including Cost, Return on Investment (ROI), Size,
  Strategic Alignment, and Risk"*), Planview (*"scores every request against strategic value, cost, and resource
  impact"*), BrightWork (budget on the intake form) · priority: **table-stakes** · spine: `estimated_cost`,
  `estimated_benefit`, `currency` → `accounting.Currency` on `ProjectRequest` · buildable now.
- **A computed ROI** — the bullet says "ROI modeling"; the honest version at this scale is a derived percentage,
  not a multi-year cash-flow model · seen in: ServiceNow (ROI as a named scoring metric), Planview, Asana
  (*"estimate of the return on investment (ROI) the project will bring"*) · priority: **table-stakes** · spine: a
  **`roi_pct` property** computed from the two estimate columns — **a derived property, never a stored column** ·
  buildable now.
- **Risk-adjustment of the return** — the bullet explicitly says *risk-adjusted*. The honest, buildable version is a
  risk rating that feeds a discount factor on the benefit side, plus a required-risk-review flag. · seen in:
  ServiceNow (risk as a scoring dimension), Planview (*"dynamic business case scoring, risk and benefit"* per G2),
  Asana (*"analysis of project risks and a risk management plan"*) · priority: **common** · spine: `risk_rating`
  choices (low/medium/high/critical) + `risk_adjusted_benefit` property applying a documented per-rating factor.
  **Probabilistic methods (Monte Carlo, EMV) are 7.5's** — record the factor in the docstring so it is never
  mistaken for actuarial output · buildable now.
- **Strategic alignment as a scored dimension** — not just money · seen in: ServiceNow (Strategic Alignment metric),
  Planview (*"strategic value"*), Asana (*"Does the request contribute to a growth or retention target?"*,
  *"Is it important for overall data governance?"*) · priority: **table-stakes** · spine: `strategic_alignment`
  small-int score on `ProjectRequest`. **The reusable weighted scoring model is 7.12's** — 7.1 stores the numbers ·
  buildable now.
- **A feasibility assessment with a verdict** — Asana makes it one of four initiation steps, answering *"Does my
  team have the required resources?"* and *"Will there be enough ROI to make this worth pursuing?"*, skippable for
  small or repeat projects; PM² puts a SWOT across several candidate solutions inside the Business Case. · seen in:
  Asana, PM²/OpenProject · priority: **common** · spine: `feasibility` choices (not_assessed / feasible /
  feasible_with_constraints / not_feasible) + `feasibility_notes` + `alternatives_considered` TextField ·
  buildable now.
- **An explicit go / no-go decision, recorded** — a decision, a decider, a date and a reason · seen in: Planisware
  (gate decision by gate-keepers), PM² (*"If the Business Case or Project Charter is not approved, the project
  proceeds directly to the Closing Phase for Lessons Learned and archiving"*), ServiceNow, Clarity
  (*"approve and fund … reject the low-priority ideas"*) · priority: **table-stakes** · spine: `decision` choices
  (go / no_go / hold / deferred) + `decided_by` + `decided_at` + `decision_notes` + `rejection_reason`; the verb
  writes a `core.AuditLog` row · buildable now.
- **Rejected requests stay visible with a reason** — BrightWork: *"If rejected, explain why to improve future
  requests"*; Clarity: rejected so teams *"do not allocate budget or time on them"*. · seen in: BrightWork/Microsoft,
  Clarity · priority: **common** · spine: keep the row in `status="rejected"` with a filter on the register ·
  buildable now.
- **A business case as a distinct, re-examinable document** — PM²: *"a living document … should be re-examined at
  critical project milestones to check that the expected benefits are still achievable"*; Asana distinguishes a
  short charter for small initiatives from a full business case for large ones. · seen in: PM²/OpenProject, Asana ·
  priority: **common** · spine: **folded onto `ProjectRequest` this pass** (market-majority pattern: ServiceNow,
  Planview, Clarity and JPD all put the economics on the demand record). The exact split to a separate
  `BusinessCase` table is recorded under *Deferred* · buildable now as a field set.
- **Visual comparison of competing demands (bubble charts, matrices)** — ServiceNow's *"Configurable Bubble Charts
  and Timeline Visualizations"*; JPD's *"list and matrix views"*. · seen in: ServiceNow, JPD, Planview · priority:
  **common** · **deferred → 7.16** (reporting/BI) for charts; 7.1's register sorts on the score columns.
- **AI re-scoring of demands as budgets and capacity change** · seen in: Planview · priority: **differentiator** ·
  **out of scope** — no ML infrastructure, and continuous reprioritisation is 7.12's.
- **Configurable scoring formulas (RICE, custom)** · seen in: JPD (*"custom formulas"*), Planview, Clarity
  (blueprints with business rules) · priority: **differentiator** · **deferred → 7.12 / 7.19**.

### Bullet 3 — Project Charter Authoring
*"Scope definition, objectives, success criteria, and executive sponsor assignment."*

- **The charter as the project's authorising record** — PM²: *"provides a basis for the more detailed project
  planning … defines the project's objectives (i.e. scope, time, cost, quality), high-level requirements, risks and
  constraints, as well as the project milestones and deliverable(s)"* and is *"a key element of the project
  approval process (along with the Business Case)"*. · seen in: PM²/OpenProject, Asana, BrightWork/Microsoft ·
  priority: **table-stakes** · spine: **new table `Project`** · buildable now.
- **Scope stated positively *and* negatively** — in-scope and out-of-scope are separate statements; PM² warns
  *"Avoid presenting detailed requirements. Instead present high-level needs and features."* · seen in: Asana,
  PM²/OpenProject · priority: **table-stakes** · spine: `in_scope` + `out_of_scope` TextFields on `Project`
  (**not** a requirements register — that is 7.7's) · buildable now.
- **Objectives, and separately, measurable success criteria** — PM²'s PIR *"summarises the success criteria against
  which it will be evaluated"* and the Business Case guideline says *"Identify measurable criteria that will be
  used to determine the success of the project"*; Asana lists *"Metrics and KPIs"* on the intake form. · seen in:
  PM²/OpenProject, Asana, BrightWork/Microsoft · priority: **table-stakes** · spine: `objectives` +
  `success_criteria` TextFields · buildable now.
- **Executive sponsor as a named, assignable role** — the bullet names it explicitly; BrightWork's intake form
  carries **Project Sponsor** as a required field and Asana's charter *"Who"* = *"Key stakeholders, project
  sponsors, and project team members"*. · seen in: BrightWork/Microsoft, Asana, PM² (Project Owner = *"the main
  beneficiary of the project's outputs"*) · priority: **table-stakes** · spine: `executive_sponsor` →
  `AUTH_USER_MODEL` (nullable) · buildable now.
- **A project manager assigned after approval** — PM²: *"The Project Manager (PM) is typically assigned after the
  Business Case is approved (or at the latest before the completion of the Project Charter)"*; BrightWork's intake
  carries *"assigned project manager"*. · seen in: PM²/OpenProject, BrightWork/Microsoft · priority:
  **table-stakes** · spine: `project_manager` → `AUTH_USER_MODEL` (nullable) · buildable now.
- **Assumptions, constraints and high-level risks recorded at charter time** — PM²'s PIR *"highlights the key
  assumptions, constraints and risks as assessed at this stage"*; BrightWork's intake asks for *"known risks and
  constraints"*. · seen in: PM²/OpenProject, BrightWork/Microsoft · priority: **table-stakes** · spine:
  `assumptions` + `constraints` TextFields + a `risk_summary`. **The risk *register* with probability/impact and
  response planning is 7.5's** — 7.1 records the charter-level summary only · buildable now.
- **Charter approval is a separate, formal sign-off** — Asana: *"Without a signed project charter or approved
  business case, you risk losing support when challenges arise"*; PM²: the Steering Committee accepts and the
  governance body *"evaluates and accepts or rejects"*. · seen in: Asana, PM²/OpenProject, Planisware · priority:
  **table-stakes** · spine: `charter_status` + `charter_approved_by` + `charter_approved_at` + a POST-only approve
  verb writing `core.AuditLog` · buildable now.
- **A signed charter document attached** — the artefact itself, not just fields · seen in: Asana (signed charter),
  BrightWork (*"Supporting documentation"*) · priority: **common** · spine: `charter_document` → `core.Document`
  (nullable). **Reuse `core.Document`** — do not build a second attachment store (6.19's ruling) · buildable now.
- **Charter deliberately kept short** — PM²: *"The Project Charter should be brief so that it can be sent to project
  stakeholders as soon as possible."* · priority: **common (design guidance, not a feature)** · spine: keep
  `Project` to charter content only; resist adding planning/budget/cost fields that belong to 7.2/7.4 ·
  buildable now.
- **Charter created from a template / methodology** · seen in: Clarity (*"Create from Template"*), BrightWork
  (*"pick the right template"*, *"re-use an existing site"*) · priority: **common** · **deferred → 7.19**
  (*Project Templates & Methodologies*). 7.1 ships a `methodology` choices field only.

### Bullet 4 — Stakeholder Identification & Analysis
*"RACI matrices, influence/interest mapping, and communication preference capture."*

- **A stakeholder register, so nobody is overlooked** — Asana: *"use a stakeholder register to ensure you're not
  overlooking any important players"*, built by answering *"Who needs to approve my project? Who will provide
  resources? Who can influence my project?"*. · seen in: Asana, PM²/OpenProject, Planisware · priority:
  **table-stakes** · spine: **new table `ProjectStakeholder`** FK'd to `Project` · buildable now.
- **RACI assignment per stakeholder** — the bullet names it. Asana puts a RACI chart in the business case to define
  *"how decisions will be made"*; PM² publishes a per-artefact **RASCI** table (Responsible / Accountable /
  Support / Consult / Inform) across roles (AGB, PSC, PO, BM, BIG, SP, PM, PCT). · seen in: Asana, PM²/OpenProject ·
  priority: **table-stakes** · spine: `raci_role` choices (R/A/C/I) + `raci_scope` CharField on
  `ProjectStakeholder` — one row per stakeholder per scope, which is exactly what a RACI matrix *is* ·
  buildable now.
- **Influence / interest grid with a derived engagement strategy** — Asana maps high/high → *"key stakeholder who
  should approve your project during the initiation phase"*, high/low, low/high, low/low, and notes the last group
  only needs a heads-up. · seen in: Asana · priority: **table-stakes** · spine: `influence` + `interest` choices
  (high/medium/low) + a derived `engagement_strategy` property
  (manage_closely / keep_satisfied / keep_informed / monitor) · buildable now.
- **Communication preference and cadence captured per stakeholder** — the bullet's *"communication preference
  capture"*; Asana's business case includes *"a communication plan"*. · seen in: Asana, PM²/OpenProject ·
  priority: **table-stakes** · spine: `comms_preference` choices (email / meeting / written_report / portal /
  none) + `comms_frequency` choices (daily / weekly / monthly / at_milestone / ad_hoc) · buildable now.
- **Internal and external stakeholders in one register** — Clarity captures demand *"from partners and customers"*;
  Asana's stakeholders include *"cross-functional teams you are requesting budget or resources from"*. · seen in:
  Clarity, Asana, BrightWork · priority: **table-stakes** · spine: `party` → `core.Party` (nullable; covers both a
  person and an organisation) + optional `user` → `AUTH_USER_MODEL` for the internal login. **Never a second
  person master** — employees are a `PartyRole` · buildable now.
- **Stakeholder type / why they are on the list** — sponsor, approver, resource provider, subject-matter expert,
  affected party · seen in: Asana (who approves / who provides resources / who can influence), PM² (named roles) ·
  priority: **common** · spine: `stakeholder_type` choices · buildable now.
- **A stakeholder engagement plan as a deliverable** — Asana's named artefact · seen in: Asana · priority: **common**
  · **no new table** — the register *is* the plan once RACI + influence/interest + comms are on it. Render it as a
  matrix view on the project detail page · buildable now.
- **Stakeholder voting / reactions on ideas** — JPD lets teammates *"react to, comment, and vote on ideas"* ·
  seen in: JPD · priority: **differentiator** · **deferred → 7.9** (collaboration). Not a data-model concern here.
- **OrgUnit-level stakeholders (a whole department as a stakeholder)** · seen in: PM² (Solution Provider is an
  organisational unit) · priority: **common** · spine: optional `org_unit` → `core.OrgUnit` on
  `ProjectStakeholder`. Include only if the pass has room — it is a fifth nullable FK.

### Bullet 5 — Project Kickoff & Launch
*"Meeting templates, team onboarding checklists, and baseline setting ceremonies."*

- **A kickoff meeting as a schedulable, tracked event** — Asana's step 4 is *"Assemble your team and tools"* and
  PM² assigns the Project Core Team *"before the Planning Kick-off Meeting"*. · seen in: Asana, PM²/OpenProject ·
  priority: **table-stakes** · spine: **reuse `core.Activity`** (`kind="meeting"`, GFK to the project, with
  `subject`, `due_at`, `owner`, `status`, `party`) for the meeting, **plus** a `ProjectKickoff` record for the
  launch as a whole · buildable now.
- **A team onboarding checklist** — the bullet names it. · seen in: Asana (*"Team charter template … to help
  everyone understand shared goals, roles, and responsibilities from day one"*), PM² (Project Core Team assigned
  before kickoff) · priority: **table-stakes** · spine: **reuse `core.Activity` with `kind="task"`** for the
  individual onboarding items (access provisioned, tooling set up, intro to sponsor, ways-of-working agreed).
  **This is a deliberate spine reuse to stay inside the 4-model cap** — see the trade-off note under the build
  scope · buildable now.
- **A baseline-setting ceremony recorded as an attestation** — the bullet's *"baseline setting ceremonies"*. The
  ceremony belongs to 7.1; the baseline *record* belongs to 7.2. · seen in: PM² (the "Ready for Planning" gate is
  the ceremony that hands the project to planning) · priority: **common** · spine: `baseline_acknowledged_at` +
  `baseline_acknowledged_by` on `ProjectKickoff`, a POST-only "mark baseline set" verb + `core.AuditLog`. **The
  actual frozen schedule baseline rows are 7.2's** — 7.1 records that the ceremony happened · buildable now.
- **A kickoff status on the project itself** — the project moves from *chartered* to *kicked off* to *active* ·
  seen in: PM² (phase gate), BrightWork (Create Project is the terminal intake stage) · priority: **table-stakes** ·
  spine: `status` choices on `Project` including `kickoff` and `active` · buildable now.
- **Meeting agenda templates** — the bullet's *"meeting templates"* · seen in: Asana (team charter template),
  BrightWork (pre-built project request templates) · priority: **common** · **deferred → 7.19** (*Project Templates
  & Methodologies*). 7.1 ships an `agenda` TextField plus an `agenda_template` choices field; a reusable template
  library needs 7.19's template object.
- **Named attendees and apologies** · seen in: Asana, PM² (PSC, PO, SP, PM, PCT all attend) · priority: **common** ·
  spine: `attending_kickoff` boolean on `ProjectStakeholder` — **no M2M table** (that would be model #5) ·
  buildable now.
- **Meeting minutes and action-item tracking** · seen in: Asana, PM² · priority: **common** · **deferred → 7.9**
  (*Meeting Management* — agenda builders, minutes capture, action item tracking). 7.1's `core.Activity` rows cover
  the action items; minutes are 7.9's.

### Beyond the bullets (found in the market, worth recording)

- **Ideas as a lighter-weight object *below* demand** — ServiceNow has Idea Management where users *"submit,
  communicate, and develop new ideas that can be promoted to a formal demand request"*; Clarity has a full Ideas
  grid with its own blueprint. · priority: **common** · spine: **no new table** — 7.1 models this as a
  `request_type="idea"` value plus a `promoted_to` self-FK on `ProjectRequest`. Cheap, and it keeps the pipeline to
  one register · buildable now if a slot opens up.
- **Submission analytics on the intake channel** — Wrike tracks *"Submitted total"*, *"Submitted this month"*,
  *"Last submitted by/date"* per form. · priority: **differentiator** · spine: a `submitted_total`-style counter on
  whatever later owns the form definition (7.19) — **not** on `ProjectRequest`, where it would be a per-row
  anomaly · deferred.
- **Automatic propagation of request data into the created project** · seen in: BrightWork, Wrike, ServiceNow ·
  priority: **table-stakes** · **this is the "Convert to project" verb** above. It is the single highest-value
  behaviour in the whole sub-module — if the pass only ships one verb, ship this one.
- **Sending a request back to the requester for more information** · seen in: BrightWork (*"send it back to Draft
  to get more information"*, at *any* stage) · priority: **common** · spine: a `needs_information` status +
  `information_requested` TextField · buildable now, cheap.

---

## Recommended build scope (this pass — 4 models)

All four are tenant-scoped (`TenantOwned` / `TenantNumbered` copied from `apps/scm/models/_base.py:53-86` into a new
`apps/projects/models/_base.py`), all get full CRUD (list with working filters + create + detail + edit + POST-only
delete), and all live under `apps/projects/{models,forms,views,urls}/ProjectInitiation/` with templates under
`templates/projects/initiation/<entity>/{list,detail,form}.html`.

1. **`ProjectRequest`** [**PRQ-**] — *one demand in the pipeline: the standardised ask, its economics, its
   feasibility, and the go/no-go decision taken on it.*
   Covers bullets **1 (Project Request & Intake)** and **2 (Business Case & Feasibility)**.
   Fields justified by the catalog: `title`, `description`, `request_type` (new_project / enhancement /
   change_request / defect / idea — ServiceNow), `requested_by` → `AUTH_USER_MODEL`, `requester_party` →
   `core.Party` (nullable, external submitter), `org_unit` → `core.OrgUnit`, `source` (portal / internal / idea /
   opportunity / email), `source_opportunity` → `crm.Opportunity` (nullable, 1.8 precedent), `assigned_reviewer` /
   `assigned_approver` → `AUTH_USER_MODEL`, `priority` (low/medium/high/critical), `strategic_alignment` (small int
   score — ServiceNow/Planview), `estimated_cost` + `estimated_benefit` + `currency` → `accounting.Currency`,
   `roi_pct` (**derived property, not a column**), `risk_rating` (low/medium/high/critical) +
   `risk_adjusted_benefit` (**derived**, documented flat factor per rating — the "risk-adjusted return" half of the
   bullet, explicitly *not* Monte Carlo), `feasibility` (not_assessed / feasible / feasible_with_constraints /
   not_feasible) + `feasibility_notes` + `alternatives_considered` (PM² SWOT-across-solutions lite),
   `required_resources` (free text — 7.3 owns real resourcing), `target_start_date` / `target_end_date`,
   `status` (**draft → submitted → screening → assessment → needs_information → approved → rejected → deferred →
   converted** — BrightWork's Draft/Review/Pending Decision/Approved/Rejected plus the send-back state),
   `decision` (go / no_go / hold / deferred) + `decided_by` + `decided_at` + `decision_notes` +
   `rejection_reason`, `submitted_at`, `converted_project` → `Project` (nullable, set by the verb).
   **Verbs:** submit, approve, reject, return-for-information, **convert-to-project** (creates the `Project`,
   copies title/description/dates/sponsor across — the carry-over BrightWork/ServiceNow/Clarity all do — and
   writes a `core.AuditLog` row).
   **FKs (all verified):** `core.Party`, `core.OrgUnit`, `accounting.Currency` (read-only, L29),
   `crm.Opportunity`, `projects.Project`, `AUTH_USER_MODEL`.

2. **`Project`** [**PRJ-**] — *the chartered project: identity, authorisation, scope, success criteria, sponsor.*
   Covers bullet **3 (Project Charter Authoring)**, and is the container every later `7.M` FKs.
   Fields justified by the catalog: `name`, `code` (optional short code), `request` → `ProjectRequest` (nullable
   provenance), `methodology` (waterfall / agile / hybrid — the *template library* behind it is 7.19's),
   `in_scope` + `out_of_scope` (PM²'s high-level-only guidance; the requirements register stays 7.7's),
   `objectives`, `success_criteria` (must be measurable — PM²), `assumptions`, `constraints`, `risk_summary`
   (charter-level only; the register is 7.5's), `executive_sponsor` → `AUTH_USER_MODEL`, `project_manager` →
   `AUTH_USER_MODEL` (PM²: assigned after the business case, before the charter completes), `org_unit` →
   `core.OrgUnit`, `client` → `core.Party` (nullable — the client *identity*; the portal, SOW and billing are
   7.14/7.15's), `start_date` / `end_date` (**charter-level targets; the frozen baseline is 7.2's**),
   `charter_status` (draft / submitted / approved / rejected) + `charter_approved_by` + `charter_approved_at`,
   `charter_document` → `core.Document` (nullable — the signed PDF; **reuse**, never a second attachment store),
   `status` (draft → chartered → kickoff → active → on_hold → completed → cancelled).
   **No money columns** — `budget_amount`, commitments and actuals are 7.4's and `accounting.Project` already
   carries them for the costing lens.
   **Verbs:** submit-charter, approve-charter (POST-only, writes `core.AuditLog`).
   **FKs (all verified):** `ProjectRequest`, `core.OrgUnit`, `core.Party`, `core.Document`, `AUTH_USER_MODEL`.
   **Docstring must carry the stand-in note** naming `accounting.Project` (2.9) and `crm.CrmProject` (1.8).

3. **`ProjectStakeholder`** [**PST-**] — *one row per stakeholder on one project: who they are, their RACI cell,
   their influence/interest quadrant, and how they want to be communicated with. The register *is* the RACI matrix
   and the engagement plan.*
   Covers bullet **4 (Stakeholder Identification & Analysis)**.
   Fields: `project` → `Project` (CASCADE), `party` → `core.Party` (nullable — a person *or* an organisation,
   internal employee *or* external client; employees are a `PartyRole`, never a second person master),
   `user` → `AUTH_USER_MODEL` (nullable — the internal login, when there is one), `stakeholder_type`
   (sponsor / approver / resource_provider / subject_matter_expert / affected / team_member / other),
   `raci_role` (R / A / C / I) + `raci_scope` (CharField — what the assignment covers, e.g. "charter approval"),
   `influence` + `interest` (high / medium / low) + a derived **`engagement_strategy`** property
   (manage_closely / keep_satisfied / keep_informed / monitor — Asana's four quadrants),
   `comms_preference` (email / meeting / written_report / portal / none), `comms_frequency`
   (daily / weekly / monthly / at_milestone / ad_hoc), `attending_kickoff` boolean (the kickoff attendee list
   without an M2M), `notes`.
   `unique_together = ("tenant", "project", "party", "raci_scope")`, `ordering = ["-influence", "party__name"]`.
   **FKs (all verified):** `projects.Project`, `core.Party`, `AUTH_USER_MODEL`.
   *(Optional 5th FK `org_unit` → `core.OrgUnit` for "this whole department is a stakeholder" — only if room.)*

4. **`ProjectKickoff`** [**PKO-**] — *the launch record for one project: the meeting, the agenda, the onboarding
   checklist, and the attestation that the baseline ceremony happened.*
   Covers bullet **5 (Project Kickoff & Launch)**.
   Fields: `project` → `Project` (OneToOne-ish — use a plain FK + `unique_together ("tenant","project")` so the
   app never fights a OneToOne on a partially-created row), `meeting_date`, `location_or_link`,
   `agenda_template` (choices: standard / agile / client_facing / custom — the *reusable template library* is
   7.19's), `agenda` (TextField), `attendee_summary` (TextField, or a count annotated from
   `ProjectStakeholder.attending_kickoff`), `onboarding_notes` (TextField — the individual onboarding items live as
   `core.Activity(kind="task")` rows attached to the project), `status`
   (planned / scheduled / held / completed), `baseline_acknowledged_at` + `baseline_acknowledged_by` (the
   "baseline setting ceremony" attestation — **the baseline itself is 7.2's**), `completed_at`, `notes`.
   **Verbs:** schedule, mark-held, **complete** (writes `core.AuditLog`), **mark-baseline-set**.
   **FKs (all verified):** `projects.Project`, `AUTH_USER_MODEL`.

**Auto-number prefixes to reserve:** `PRQ`, `PRJ`, `PST`, `PKO`.
⚠️ `PRJ` is already in use by `accounting.Project` (2.9) and `crm.CrmProject` (1.8) — see the ruling. Numbers are
unique per `(tenant, number)` **within a model**, so there is no key collision, but the docstring and the sidebar
copy must be explicit about which "project" a user is looking at.

**Trade-off I am consciously accepting (state it in the code):** bullet 2 gets a *field set* on `ProjectRequest`
rather than its own `BusinessCase` table, and bullet 5 gets a `ProjectKickoff` table whose onboarding checklist
items are `core.Activity(kind="task")` rows rather than a `ProjectKickoffItem` child. Both choices exist to stay
inside the 4-model cap and both are reversible:
- If a charter-level business case *document* with its own approver and version history is wanted later, split
  `BusinessCase` [PBC-] out of `ProjectRequest` — the field names above are already grouped for it.
- If per-item onboarding status (assignee, due, done) matters more than a single attestation, promote the
  `core.Activity` rows to a real `ProjectKickoffItem` table and drop `ProjectKickoff.onboarding_notes`.
- **If the pass runs long, `ProjectKickoff` is the one to drop first** — it is the only one of the four whose
  content can be fully re-expressed on existing spine (`core.Activity` for the meeting and the checklist, plus a
  `kickoff_date` column and a status value on `Project`).

**Sidebar entry to add:** one `LIVE_LINKS["7.1"]` block mapping all five bullets — Project Request & Intake →
`projects:prq_list`; Business Case & Feasibility → `projects:prq_list?status=assessment` (deep-link precedent from
6.14); Project Charter Authoring → `projects:prj_list`; Stakeholder Identification & Analysis →
`projects:pst_list`; Project Kickoff & Launch → `projects:pko_list`.

---

## Belongs to sibling sub-modules (parked, not scoped here)

- **WBS, task sequencing & dependencies (FS/SS/lag/lead), critical path, duration & effort estimating with
  confidence ranges, milestone & phase-gate definition, schedule baseline + baseline versions, what-if scenarios,
  fast-tracking/crashing** → **7.2**. 7.2 also inherits the open `crm.CrmMilestone` (1.8) vs `projects.Milestone`
  question.
- **Resource pool & skills inventory, allocation & leveling, team assembly & role assignment, resource
  forecasting & demand planning, timesheets** → **7.3**. (7.1's `required_resources` is free text only.)
- **Budget planning & estimation, cost baseline & control accounts, EVM, expense tracking & commitments,
  EAC/CPI/SPI, change control & budget revisions** → **7.4**. 7.1 ships **no** money columns on `Project`.
- **Risk register with probability/impact matrices, Monte Carlo, EMV, risk response planning
  (avoid/transfer/mitigate/accept), issue logging & escalation, risk monitoring dashboards, lessons-learned
  integration** → **7.5**. 7.1 keeps only a charter-level `risk_summary` and a request-level `risk_rating`.
- **Quality planning, acceptance criteria as a controlled artefact, QA/QC, deliverable acceptance & sign-off** →
  **7.6**. (7.1's `success_criteria` is the charter's own statement, not the QA artefact.)
- **Requirements elicitation, requirements documentation & traceability matrix, scope change requests, CCB,
  scope verification & control** → **7.7**. 7.1's `in_scope`/`out_of_scope` are deliberately high-level (PM²).
- **Task creation & assignment, Kanban/Scrum boards, Gantt charts, task dependencies** → **7.8**.
- **Team messaging & channels, document co-editing, meeting management (minutes, action items), notifications &
  alerts, activity streams** → **7.9**. Kickoff *minutes* are 7.9's; 7.1 records that the meeting happened.
- **Document repository & folders, document templates, version control & check-in/out, lessons-learned knowledge
  base, retention & archiving** → **7.10**. 7.1 attaches the charter PDF to `core.Document` and stops there.
- **Timesheets & time approval** → **7.11**.
- **Portfolio dashboards & heat maps, program dependency mapping, reusable weighted **scoring models**,
  demand-vs-capacity pipeline planning, portfolio/steering reporting** → **7.12**. 7.1 stores *per-request* score
  numbers; the *model* that weights them, and the cross-project view, are 7.12's. This is the single biggest
  thing 7.1 must resist building.
- **Sprint planning, standups, burndown, releases, epics, retrospectives** → **7.13**.
- **Client portal & visibility, client feedback & approvals, SOW/contract management, external vendor
  coordination, client invoicing** → **7.14**. 7.1 ships the `client` Party FK and nothing else.
- **Project accounting, revenue recognition, invoice generation, A/R, multi-currency & tax** → **7.15** (and
  `apps/accounting` owns the ledger — L29).
- **Standard & custom reports, dashboards & widgets, executive packs, data export & OData/REST** → **7.16**. The
  bubble/matrix charts ServiceNow and JPD show are 7.16's, not 7.1's.
- **Visual workflow designer, approval automation (auto-approval within thresholds, escalation on timeout,
  delegation), notification & reminder rules, recurring task automation, iPaaS** → **7.17**. 7.1's multi-stage
  approval is a **fixed** status machine with explicit verbs.
- **ERP/CRM/HR/DevOps/file-storage connectors** → **7.18**.
- **Project templates & methodologies with pre-built WBS, custom fields & forms, org hierarchy & teams,
  localization** → **7.19**. This is where **configurable intake forms**, **dynamic/conditional questions**,
  **meeting agenda templates** and **charter templates** live. 7.1 ships fixed field sets and choices fields only.

---

## Deferred (later passes / integrations)

| Area | Why deferred |
|---|---|
| **Public / unauthenticated stakeholder submission portal** | Wrike's "Shared publicly" and Clarity's partner/customer intake are real, but an anonymous write endpoint is a spam/PII/tenant-isolation surface that needs tokenised URLs, rate limiting and moderation. 7.1 ships authenticated submission with a `core.Party` requester; the portal is 7.14's. |
| **Configurable / dynamic intake forms (conditional questions, per-type forms, form builder)** | No form-builder or custom-field engine exists anywhere in the repo. NavERP 7.19 *Custom Fields & Forms*. 7.1 ships one fixed form per model. |
| **Reusable weighted scoring models, bubble/matrix prioritisation charts, AI re-scoring** | The *model* and the *visuals* are 7.12 (strategic alignment & scoring) and 7.16 (reporting). 7.1 stores raw numeric scores. AI re-scoring (Planview) additionally needs ML infrastructure NavERP does not have. |
| **Monte Carlo, EMV, probabilistic risk-adjusted return** | NavERP 7.5 *Qualitative & Quantitative Analysis*. 7.1's `risk_adjusted_benefit` is a documented flat factor per risk rating and the docstring must say so. |
| **E-mail notification of request status changes / approvals / rejections** | No mail worker and no scheduler (the procurement 6.8 and 6.19 passes record the same limitation). Decisions land on the request's detail page and in `core.AuditLog`; the reminder/notification engine is 7.17's. |
| **Separate `BusinessCase` [PBC-] table with its own approver and version history** | PM² and Asana both treat it as a distinct artefact. Folded onto `ProjectRequest` this pass to stay inside 4 models and because ServiceNow/Planview/Clarity/JPD all put the economics on the demand record. First thing to split out if a real BC document is needed. |
| **`ProjectKickoffItem` child rows for the onboarding checklist** | Would be model #5. `core.Activity(kind="task")` covers assignee/due/status today at the cost of not being joinable in a tenant-filtered list. |
| **Merging `accounting.Project` (2.9) and `crm.CrmProject` (1.8) into `projects.Project`** | Deliberate: modules 1 and 2 are built, tested and live. The stand-in note in `Project`'s docstring plus a future nullable link is the honest intermediate state — the `crm.PurchaseOrder` precedent. |
| **Idea Management as its own object with voting, comments and reactions** | Modeled as `request_type="idea"` this pass. A full idea portal with voting (JPD, ServiceNow Idea Management) is 7.9/7.19. |
| **Charter e-signature / approval workflow with e-sign** | Needs a signature provider; 7.10/13 own document approval. 7.1 records `charter_approved_by` + timestamp + an attached PDF. |
| **Stakeholder M2M to OrgUnit, external portal visibility per stakeholder** | 7.14. Would also be a 5th FK. |
| **Kickoff minutes, action-item tracking, threaded discussion** | 7.9 *Meeting Management*. |
| **Capacity-aware intake ("do we have the people?")** | 7.3 (resource forecasting) + 7.12 (capacity & pipeline planning). 7.1's `required_resources` is free text. |
| **Integration to Jira/Azure DevOps/GitHub for delivery, and to ERP/CRM for context** | 7.18. |
