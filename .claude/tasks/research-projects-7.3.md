# Research — Sub-module 7.3: Resource Management (Module 7 — Project Management, `projects`)

> **Read this first.** 7.3 is the *people* sub-module of Module 7: it turns the chartered project (7.1) and its
> WBS (7.2) into **booked, staffed, time-logged work**. It is **not** the task-execution layer (7.8 extends
> `ProjectTask` in place with assignments/actuals), **not** money (7.4 owns cost/budget, 7.15 owns billing —
> `projects.Project` deliberately carries no money columns and 7.3 must add none), **not** attendance
> (HRM 3.9/3.11 own check-in/shift/overtime and the payroll-grade weekly timesheet), and **not** portfolio-level
> capacity governance (7.12). The failure mode for this pass is **building a mini-PSA**: rate cards, margin-aware
> candidate comparison, AI staffing optimizers, scenario planners and configurable workflow engines are all real
> in the products surveyed and all belong to siblings or later passes.
>
> **The second failure mode is a fourth timesheet.** The repo already has `hrm.Timesheet`/`TimesheetEntry`
> (3.11, weekly header + entries + approval) and `crm.Timesheet` (1.8 pre-spine stand-in). 7.3's fifth bullet
> still needs project-facing actuals, but they must be the *thinnest* table that makes "actuals-to-plan" joinable
> to `projects.Project` — not another full timesheet product.

---

## Repo state checked first

### LIVE_LINKS built so far in Module 7 (`apps/core/navigation.py`)

`"7.1"` at `navigation.py:1702`, `"7.2"` at `navigation.py:1717`. **No `"7.3"` key** — this sub-module is
greenfield. Everything earlier (0.x, 1.x, 2.x, 3.x, 4.x, 6.x) is live per the same dict.

### Sibling models verified to exist (grep/read evidence — all under `apps/projects/models/`)

| Entity | Verified at | What 7.3 uses it for |
|---|---|---|
| `projects.Project` [PRJ-] | `ProjectInitiation/Projects.py:27` | **the container every allocation and time entry FKs.** Fields read: `name`, `status` (draft→chartered→kickoff→active→on_hold→completed→cancelled), `project_manager`/`executive_sponsor` → `AUTH_USER_MODEL`, `org_unit` → `core.OrgUnit`, `client` → `core.Party`, `start_date`/`end_date`. **No money columns (7.4's).** |
| `projects.ProjectRequest` [PRQ-] | `ProjectInitiation/ProjectRequests.py:25` | **the demand pipeline.** Status machine runs draft→submitted→screening→assessment→needs_information→approved→rejected→deferred→**converted**. Approved-not-yet-converted requests are exactly the "pipeline" side of bullet 4's "pipeline vs. capacity". |
| `projects.ProjectTask` [TSK-] | `ProjectPlanningScheduling/ProjectTasks.py:22` | the WBS work package. `planned_start/planned_end/effort_hours/owner/status`. Allocations may optionally target a work package; the `effort_hours` column is what makes bookings-vs-effort comparable. **No actuals (7.8's).** |
| `projects.ProjectMilestone` / `TaskDependency` / `ScheduleBaseline` | `ProjectPlanningScheduling/ProjectMilestones.py:17`, `TaskDependencies.py:17`, `ScheduleBaselines.py:24` | present but not needed by 7.3. |

### Spine entities verified (grep evidence)

| Entity | Verified at | What 7.3 uses it for |
|---|---|---|
| `core.Party` | `apps/core/models/Party.py:5` | the **external contractor / freelancer identity** (a `PartyRole` — never a second person master). |
| `core.PartyRole` | `apps/core/models/PartyRole.py:5` | flags *why* a party is in the pool (contractor role). |
| `core.Employment` | `apps/core/models/Employment.py:5` | reached via `hrm.EmployeeProfile.employment` (dept/manager come from here). Not FK'd directly. |
| `core.OrgUnit` | `apps/core/models/OrgUnit.py:5` | the resource's home team/department (pool filters). |
| `core.Activity` | `apps/core/models/Activity.py:5` | available (GFK notes/meetings) but **not needed** — 7.3 has no meeting surface. |
| `core.Document` | `apps/core/models/Document.py:5` | available; certification evidence PDFs stay on the HRM side this pass. |
| `core.AuditLog` + `core.utils.write_audit_log` | `apps/core/models/AuditLog.py:5`, `apps/core/utils.py:6` | audit rows for the staffing verbs (assign / substitute / approve time). |
| `hrm.EmployeeProfile` [EMP-] | `apps/hrm/models/EmployeeManagement/EmployeeProfiles.py:8` | **the internal-person anchor**: `OneToOne` over `core.Party` + `core.Employment`, `employee_type` already carries `contract`/`consultant`. Docstring: *"All other HRM models FK to this, never to core.Party directly."* 7.3 string-FKs it (`"hrm.EmployeeProfile"`), the sanctioned cross-app pattern. |
| `hrm.EmployeeSkill` | `apps/hrm/models/WorkforcePlanning/Employeeskill.py:5` | **the skills inventory already exists (HRM 3.40)**: `skill_name`, `skill_category` (incl. `certification`), `proficiency_level` (beginner→expert), `years_experience`, `is_certified`, `certification_name`, `is_critical_skill`; unique `(tenant, employee, skill_name)`. 7.3 must NOT re-declare it — it is a documented lens. |
| `hrm.Timesheet` / `hrm.TimesheetEntry` | `apps/hrm/models/TimeTracking/Timesheet.py:8`, `Timesheetentry.py:5` | the payroll-grade weekly timesheet (draft→pending→approved/rejected, entry locks on approval). ⚠️ Its entry's `project` FK points at **`accounting.Project` (the 2.9 stand-in)** and its task is free text — **it cannot join to `projects.Project`**. That gap is why bullet 5 needs a thin projects-side table. |

### Already built elsewhere — do NOT duplicate

- **`crm.ResourceAllocation`** (`apps/crm/models/ProjectDelivery/ResourceAllocation.py:6`, prefix `RA`) — the
  1.8 pre-spine stand-in: bookings against `crm.CrmProject` keyed on `User` with `hours_per_week` + an
  `overlap_hours(win_start, win_end)` proration helper that is **proven code worth copying**. It serves CRM
  projects only; 7.3 builds its own booking against `projects.Project` and leaves the stand-in untouched
  (the documented 7.1 `PRJ-` stand-in ruling, same pattern).
- **`crm.Timesheet`** (`apps/crm/models/ProjectDelivery/Timesheets.py:5`) — 1.8's flat per-entry time log
  against `crm.CrmProject`. Same stand-in treatment.
- **`hrm.EmployeeSkill`** (above) and the **live HRM pages** `hrm:employeeskill_list` /
  `hrm:workforce_gap_analysis` (LIVE_LINKS `"3.40"`) — the competency matrix and certifications lens already
  ships. 7.3 links to it, exactly the way 3.29 reused 3.11's utilization report.
- **`next_number` / `TenantNumbered`** — `_base.py` is local to `apps/projects` and re-exports the proven
  retry-on-collision `save()`; new entities just set `NUMBER_PREFIX`.

### Prefixes reserved this pass (grep over `NUMBER_PREFIX = ` repo-wide)

`RSP`, `RAL`, `RTE` are **unused** anywhere in the repo. (Prefixes are only unique per model, but avoiding a
fourth `PRJ`-style collision story is cheap.)

---

## Leaders surveyed (with source links)

The domain is **professional-services resource management / capacity planning / PSA staffing** — not generic
"project management software".

1. **Float** — the reference for *visual scheduling discipline*: hours-or-percent allocation, live capacity and
   over-capacity warnings, and placeholders for not-yet-hired people. <br>
   [Resource scheduling](https://www.float.com/resource-scheduling) ·
   [Plan ahead with Placeholders](https://www.float.com/whats-new/plan-ahead-with-placeholders)
2. **Resource Guru** — the reference for *clash-first scheduling* and for **timesheets auto-filled from
   bookings with built-in approvals**. <br>
   [Resource Guru](https://resourceguruapp.com/) ·
   [Resource placeholders](https://resourceguruapp.com/blog/product-updates/resource-placeholders)
3. **Runn** — the reference for *forecast-grade capacity*: hours-free visibility, rate cards, and timesheet
   alerts when logged time differs from schedule. <br>
   [Features](https://www.runn.io/features) ·
   [The Beginner's Guide to Resource Leveling](https://www.runn.io/blog/resource-leveling) ·
   [Using Placeholders in Resource Scheduling](https://www.runn.io/blog/using-placeholders-in-resource-scheduling-a-runndown)
4. **Kantata (Mavenlink lineage)** — the reference for *demand-side resourcing*: a resourcing dashboard that
   puts supply and demand (including **unsold work**) side by side, resource requests, and internal-vs-external
   candidate comparison. <br>
   [Staffing and Resource Forecasting](https://www.kantata.com/solutions/resource-forecasting-and-staffing)
5. **Certinia PSA (formerly FinancialForce)** — the reference for the *resource request → hold → assign*
   staffing workflow with skills on the request. <br>
   [Resource Requests Overview](https://help.certinia.com/main/2026.2/Content/PSA/Features/ResourceRequests/AboutResourceRequests.htm) ·
   [Skill Suggestions for Resource Requests](https://help.certinia.com/main/2026.2/Content/PSA/Features/SkillsCertifications/SkillSuggestions/SkillSuggestionsOverview.htm)
6. **Planview AdaptiveWork** — the reference for *skill-based matching and placeholder resources used for
   forecasting before named assignments*. <br>
   [AdaptiveWork product page](https://www.planview.com/products-solutions/products/adaptivework/) ·
   [Capacity Planning & Staffing Request Automation (Planview Community)](https://community.planview.com/learn-and-share-64/capacity-planning-staffing-request-automation-221)
7. **Scoro** — the reference for *bookings at two granularities* (fixed hours or % of availability) and for
   capacity that reacts to leave; its planning page is the clearest statement of *hiring/outsourcing triggers*. <br>
   [Resource & Capacity Planning](https://www.scoro.com/apps/resource-planning/) ·
   [Resource bookings – an overview (Help Center)](https://support.scoro.com/hc/en-us/articles/25995337245197-Resource-bookings-an-overview)
8. **Deltek Vantagepoint** — the reference for *assignment dependency chains* and forecasting future resource
   requirements early enough to train or hire. <br>
   [Take Resource Planning to the Next Level](https://www.deltek.com/resources/articles/vp-resource-planning-next-level/) ·
   [Resource Planning Software (BCS ProSoft)](https://www.bcsprosoft.com/deltek/vantagepoint-2/resource-planning-software/)
9. **Wrike (Wrike Resource)** — the reference for the *two-axes workload split*: per-user workload charts vs a
   project-axes "Resources view" for spotting gaps. <br>
   [Wrike Resource (Help Center)](https://help.wrike.com/hc/en-us/articles/360024767374-Wrike-Resource) ·
   [Resources View (Help Center)](https://help.wrike.com/hc/en-us/articles/1500000614522-Resources-View)

**Considered and dropped, with reasons:** *monday.com*'s capacity pages were unreachable this run (captcha), so
no monday-specific claims are made. *10,000ft* is now Smartsheet's "Resource Management by Smartsheet"; its
placeholder behavior is documented second-hand via the
[Smartsheet community thread on placeholder assignments](https://community.smartsheet.com/en/discussion/122723/assign-multiple-placeholders-or-a-combination-of-named-people-and-placeholders-to-a-row)
— cited only for the cross-product placeholder evidence, not for unique features. *Productive*
([Placeholders help article](https://help.productive.io/en/articles/4168381-placeholders)) and *Projectworks*
([Plan capacity with placeholders](https://www.projectworks.com/blog/project-resource-management-with-placeholders))
are cited only to establish that placeholders are a domain-wide mechanic, not a niche one.

---

## Feature catalog (this sub-module only)

Priority key: **table-stakes** (nearly every leader has it) · **common** (most have it) · **differentiator**
(a few standouts). Spine names are grep-verified per the tables above.

### Bullet 1 — Resource Pool & Skills Inventory
*"Employee profiles, competency matrices, certifications, and availability calendars."*

- **A single pool register of bookable people** — one place the resource manager can see who exists, what they
  do, and whether they can take work. Every surveyed tool is built on one (Float's schedule rows, Resource
  Guru's people, Runn's capacity list, Certinia's resources). · seen in: Float, Resource Guru, Runn, Certinia,
  Scoro · priority: **table-stakes** · spine: **new table `ResourceProfile`** · buildable now.
- **People keyed on the HR record, never a second person master** — the pool is a *project-facing lens* over
  the employee; contractors get a `core.Party` identity. · seen in: Certinia (resources carry HR-ish detail,
  skills, certifications) · priority: **table-stakes** · spine: `employee` FK → **`hrm.EmployeeProfile`**
  (nullable) + `party` FK → **`core.Party`** (nullable, external) — one of the two required · buildable now.
- **Per-person capacity (weekly hours)** — the denominator of every utilization/over-allocation computation.
  Runn: *"see … how many hours free they have"*; Scoro computes capacity from calendars and leave. · seen in:
  Runn, Scoro, Float ("track capacity live") · priority: **table-stakes** · spine:
  `weekly_capacity_hours` column on `ResourceProfile` · buildable now.
- **A utilization target per person** — forecast utilization is only meaningful against a target. Kantata's
  resourcing dashboard shows forecast utilization; Scoro and Runn report against goals. · seen in: Kantata,
  Scoro, Runn · priority: **common** · spine: `utilization_target_pct` column · buildable now.
- **Skills search & proficiency for staffing** — match requests to people by skill. Kantata profiles skills on
  unsold work; Certinia attaches skills to requests and auto-suggests them from role/region/practice; Planview
  does skill-based matching. · seen in: Kantata, Certinia, Planview AdaptiveWork · priority: **common** ·
  spine: **documented lens on `hrm.EmployeeSkill`** (already live at `hrm:employeeskill_list`, 3.40) + a
  free-text `skill_requirements` on the booking side — **no projects-side skill table this pass** · buildable
  now (lens).
- **Certifications tracking** — Certinia explicitly tracks *"resource details, certifications, and skills"*.
  · seen in: Certinia · priority: **common** · spine: **lens on `hrm.EmployeeSkill`** (`is_certified` +
  `certification_name` + `skill_category="certification"` already exist) · buildable now (lens).
- **Contractor / non-employee resources in the same pool** — Kantata compares internal vs external candidates;
  Productive and Projectworks plan outsourced capacity; `hrm.EmployeeProfile.employee_type` already carries
  `contract`/`consultant`, and true externals are Parties. · seen in: Kantata, Productive, Projectworks ·
  priority: **common** · spine: `resource_type` choices on `ResourceProfile` (internal / contractor /
  freelancer / consultant) + the `core.Party` FK · buildable now.
- **Availability calendar (booked-vs-free over time)** — Float shows *"live utilization indicators … right on
  the Schedule"*; Resource Guru visualises *"availability, workloads, and utilization"*; Scoro's per-person
  heatmap shows how much of each person's time is booked. · seen in: Float, Resource Guru, Scoro, Runn ·
  priority: **table-stakes** · spine: **a computed capacity board over `ResourceAllocation` rows against
  `weekly_capacity_hours`** — no stored calendar table. ⚠️ Leave/absence deduction is HRM 3.10's data; until an
  integration exists the board treats capacity as uniform weekly hours and says so on the page · buildable now
  (view).
- **Equipment and meeting-room booking** — Resource Guru ships these as first-class bookable entities. ·
  seen in: Resource Guru · priority: **differentiator** · **out of scope** — 7.3 resources *people*; equipment
  is a future pool type, not this pass.

### Bullet 2 — Resource Allocation & Leveling
*"Capacity planning, over-allocation alerts, and automatic smoothing algorithms."*

- **A booking = person + role + magnitude + date window, attached to a project** — the atomic allocation every
  tool shares. Scoro allows *"fixed hours (e.g. 6h/day) or percentage-based (e.g. 75% of daily availability)"*;
  Float allocates *"by hours or percentages"*; Planview uses percentage-based capacity. · seen in: Float,
  Scoro, Planview, all others · priority: **table-stakes** · spine: **new table `ResourceAllocation`** with
  `allocation_unit` choices (hours_per_week / pct_capacity / total_hours) + `start_date`/`end_date`
  (null end = ongoing, the proven `crm.ResourceAllocation` convention) · buildable now.
- **Booking at project grain (optionally task grain)** — high-level booking before task-level detail is the
  market norm (Scoro: *"booking time for a project before deciding on specific tasks"*; Resource Guru books
  phases). · seen in: Scoro, Resource Guru, Wrike (Resources view vs task effort) · priority: **table-stakes** ·
  spine: `project` FK required-ish + `project_task` FK → `projects.ProjectTask` nullable · buildable now.
- **Over-allocation alerts** — Float: *"over-capacity warnings"*; Resource Guru: *"quickly identify clashes and
  conflicts"*; Wrike detects resource conflicts; Runn has an entire over-allocation playbook. · seen in: Float,
  Resource Guru, Runn, Wrike · priority: **table-stakes** · spine: a **computed view** aggregating bookings per
  resource-week vs `weekly_capacity_hours`, with alert flags and a register filter — **no stored alert table**
  · buildable now.
- **Leveling / smoothing — the honest market picture** — the leaders overwhelmingly *flag and manually
  rebalance* (drag-and-drop); Kelloo is the one tool that models knock-on effects automatically, and
  MS-Project-style auto-leveling is the legacy exception. Runn's own guide describes leveling as a manual
  planning technique. · seen in: Runn (guide), Kelloo, Float (manual) · priority: **common** · spine: the
  capacity board doubles as the **smoothing lens** — over-booked resource-weeks listed with the bookings that
  cause them; the fix is editing the bookings (move/shrink/split). **No optimizer this pass** · buildable now
  (view + guidance copy).
- **Soft vs committed (hard) bookings** — Certinia's hold/assign workflow (*"You can hold and assign resources
  for the resource request"*), Kantata soft-booking against unsold work, Runn placeholders for proposal-stage
  projects. · seen in: Certinia, Kantata, Runn · priority: **common** · spine: `booking_status` choices on
  `ResourceAllocation` (requested / soft / firm / completed / cancelled / released) · buildable now.
- **Live utilization indicators on the schedule** — Float's headline; the capacity board covers it · seen in:
  Float · priority: **common** · same computed view · buildable now.

### Bullet 3 — Team Assembly & Role Assignment
*"Named resource booking, generic placeholder roles, and substitution workflows."*

- **Named resource booking** — pick the person; the register records who. Universal. · seen in: all ·
  priority: **table-stakes** · spine: `resource` FK → `ResourceProfile` on `ResourceAllocation` · buildable
  now.
- **Generic placeholder roles (unnamed bookings)** — the strongest cross-product signal in this research:
  Resource Guru ["resource placeholders"](https://resourceguruapp.com/blog/product-updates/resource-placeholders),
  Float ["plan ahead with Placeholders"](https://www.float.com/whats-new/plan-ahead-with-placeholders)
  (explicitly for new hires with tentative start dates), Runn placeholders *"especially useful for tentative
  projects still at proposal stage"*, Productive's "placeholder users", Planview's *"placeholder resources …
  for forecasting before named assignments"*. · seen in: Resource Guru, Float, Runn, Productive, Planview,
  10,000ft/Smartsheet · priority: **table-stakes** · spine: **`resource` NULL + `role_name` populated** — a
  placeholder is a *state of the booking*, never a fake person row · buildable now.
- **Resource requests / staffing requests as a workflow** — Certinia's Resource Request (role, skills, dates,
  optional suggested resource) and Planview's staffing-request automation both model "ask first, staff later".
  · seen in: Certinia, Planview, Kantata (resource requests on the resourcing dashboard) · priority: **common**
  · spine: `booking_status="requested"` + `skill_requirements` + `requested_by` — the request **is** a
  placeholder allocation in the requested state (one table, two market objects; see trade-off note) ·
  buildable now.
- **Placeholder → named fulfillment** — the moment of assembly: Certinia *"assign resources"* from a request;
  Resource Guru/Runn/Float promote a placeholder by naming it. · seen in: Certinia, Resource Guru, Runn,
  Float · priority: **table-stakes** · spine: a POST-only **"Assign resource"** verb that fills `resource` and
  moves the status forward, writing `core.AuditLog` · buildable now.
- **Substitution workflow** — the bullet names it. Certinia lets you hold *another* resource for a request;
  the mechanic in every tool is: release the current person, book the replacement, keep the history. · seen
  in: Certinia, Planview · priority: **common** · spine: a POST-only **"Substitute"** verb — sets the current
  booking to `released` and creates the successor with `substitute_of` self-FK pointing back, + `core.AuditLog`
  · buildable now.
- **Candidate comparison (internal vs external on skills, availability, margin)** — Kantata's Candidate
  Assignments. · seen in: Kantata · priority: **differentiator** · **deferred** — margin is money (7.4/7.15);
  a skills/availability-only comparison is a future enhancement over data this pass already stores.
- **Role rate cards** — Certinia/Runn tie bill and cost rates to roles. · seen in: Certinia, Runn · priority:
  **common in market** · **parked — money** → 7.4/7.15 (L29).

### Bullet 4 — Resource Forecasting & Demand Planning
*"Pipeline vs. capacity views, hiring triggers, and contractor engagement."*

- **Demand records that can exist before the project does** — Kantata's *"Skills Profiling on Unsold Work"*
  soft-books people against pipeline deals; Runn placeholders serve *"tentative projects still at proposal
  stage"*. · seen in: Kantata, Runn, Certinia (requests tied to opportunities) · priority: **common** · spine:
  `project_request` FK → **`projects.ProjectRequest`** (nullable) on `ResourceAllocation` — demand hangs off
  the 7.1 pipeline when there is no project yet · buildable now.
- **Pipeline vs capacity view** — Kantata's resourcing dashboard puts supply and demand side by side; Scoro:
  *"Know when to bring in more work and spot resource shortages before they happen"*; Wrike Resource forecasts
  demand. · seen in: Kantata, Scoro, Wrike, Planview · priority: **table-stakes** · spine: a **computed
  demand view** over `ResourceAllocation` (placeholders + soft bookings, split project-linked vs
  request-linked) against pool capacity — **no new model** · buildable now (view).
- **Hiring triggers** — Scoro's planning page is explicit: *"Make proactive decisions on outsourcing or
  hiring"*; Deltek: *"identify future resource requirements, enabling timely training and capacity planning"*.
  · seen in: Scoro, Deltek Vantagepoint, Certinia (forecasting accuracy framing) · priority: **common** ·
  spine: a computed **coverage-gap flag** on the demand view — demand hours with no named fulfillment inside
  the horizon; surfaced as a filter/lens, not a stored workflow · buildable now (view).
- **Contractor engagement windows** — Productive/Projectworks plan outsourced capacity; contractors need an
  engagement window, not an employment record. · seen in: Productive, Projectworks, Kantata · priority:
  **common** · spine: `resource_type="contractor"` + `available_from`/`available_to` on `ResourceProfile`
  · buildable now.
- **Scenario / what-if planning** — Runn scenarios, Kelloo modeling, Planview what-if. · seen in: Runn,
  Kelloo, Planview · priority: **differentiator** · **deferred** — needs a scenario-copy mechanic over the
  whole booking set; first candidate for a later 7.3 pass.
- **AI staffing optimization** — Kantata's Staffing Optimizer builds AI-optimal staffing scenarios; Certinia's
  Intelligent Staffing matches resources to requests; Wrike has AI workload forecasting. · seen in: Kantata,
  Certinia, Wrike · priority: **differentiator** · **out of scope** — no ML infrastructure (same ruling as
  7.1's AI re-scoring).

### Bullet 5 — Time Tracking & Timesheets
*"Daily/weekly entry, approval routing, and actuals-to-plan comparison."*

- **Per-day time logged against project (and optionally task)** — the entry grain of every tool. Resource
  Guru's *"Timesheets auto-fill based on work that's already booked"*; Runn's *"simple and easy to use
  timesheets"*; Wrike Resource ships timesheets with billable time. · seen in: Resource Guru, Runn, Wrike,
  Float · priority: **table-stakes** · spine: **new table `ResourceTimeEntry`** (flat daily rows; `project`
  nullable so non-project time is loggable; `project_task` nullable) · buildable now.
- **Approval routing (submit → approve/reject)** — Resource Guru: timesheets *"include built-in approvals"*;
  the house already has the proven machine twice (`hrm.Timesheet` draft→pending→approved/rejected,
  `crm.Timesheet` draft→submitted→approved/rejected). · seen in: Resource Guru, Wrike · priority:
  **table-stakes** · spine: `status` (draft / submitted / approved / rejected) + `approved_by` +
  `submitted_at`/`approved_at` + a **weekly bulk-approve verb** per person-week (the weekly lens) ·
  buildable now.
- **Actuals-to-plan comparison (scheduled vs actual)** — Resource Guru: *"compare scheduled vs. actual hours
  worked"*; Runn alerts *"when time is missing or someone worked different hours than scheduled"*. · seen in:
  Resource Guru, Runn, Scoro · priority: **table-stakes** · spine: a **computed comparison view** aggregating
  approved `ResourceTimeEntry.hours` vs `ResourceAllocation` planned hours per project/resource — the only
  honest way to realize the bullet, and the reason the entry must FK `projects.Project` (HRM's entry cannot —
  it points at the 2.9 stand-in) · buildable now (view).
- **Weekly entry grid** — the bullet says "daily/weekly entry". The market models a weekly *document*
  (HRM's header/entry split), but for project actuals a weekly *lens* over flat entries is enough this pass.
  · seen in: all · priority: **common** · spine: list view grouped by resource + ISO week; **no header model**
  (trade-off note below) · buildable now.
- **Auto-filled timesheets from bookings** — Resource Guru's differentiator: the form pre-fills from the
  schedule. · seen in: Resource Guru · priority: **differentiator** · **deferred** — a form-prefill
  enhancement; the data model (allocations + entries) already supports it.
- **Missing-timesheet nudges** — Runn alerts on missing time. · seen in: Runn · priority: **common** ·
  **deferred** — needs the 7.17 notification engine; a "this week's non-submitters" filter is the cheap lens.
- **Billable vs non-billable hours, overtime, leave integration, utilization dashboards** — NavERP.md's own
  **7.11 Time & Attendance Tracking** bullets, plus HRM 3.9/3.10/3.11's turf. · priority: — · **parked to
  7.11/HRM**; 7.3 ships hours only, deliberately **no billable/rate/money columns** (7.15/7.4; L29).

### Beyond the bullets (found in the market, worth recording)

- **Leave factored into capacity automatically** — Scoro: *"When someone books leave, their available hours
  update across the planner"*; Resource Guru ships Leave Management; Float shows *"pre-booked time off"*. ·
  priority: **common** · **deferred** — an HRM 3.10 integration; this pass documents capacity as
  uniform-weekly-hours on the board.
- **Schedule dependencies between assignments** — Deltek Vantagepoint links assignments with schedule
  dependencies. · priority: **differentiator** · **deferred** — 7.2's `TaskDependency` already models the
  schedule-side concept; allocation chaining is a later nicety.
- **Assignment sub-rows / multi-level plans** — Deltek's detailed plans with sub-rows. · priority:
  **differentiator** · **deferred** — task-grain bookings (`project_task` FK) already give one level.

---

## Recommended build scope (this pass — 3 models)

All tenant-scoped via `apps/projects/models/_base.py` (`TenantOwned`/`TenantNumbered`), full CRUD (list with
filters + create + detail + edit + POST-only delete), under
`apps/projects/{models,forms,views,urls}/ResourceManagement/`, templates under
`templates/projects/resourcing/<entity-slug>/{list,detail,form}.html` (slug choice is the todo agent's to
finalize; `initiation`/`planning` are the precedents).

1. **`ResourceProfile`** [**RSP-**] — *one bookable person in the tenant's pool: who they are (HR employee or
   external party), their type, home team, default role, capacity and utilization target.*
   Covers bullet **1 (Resource Pool & Skills Inventory)** — the live pool register — and supplies the capacity
   denominator every other bullet computes against.
   Fields: `employee` FK **`"hrm.EmployeeProfile"`** (`SET_NULL`, null, blank, string FK — the sanctioned
   cross-app pattern; the HR truth for internal staff, incl. `contract`/`consultant` types) · `party` FK
   `"core.Party"` (`SET_NULL`, null, blank — external contractor/freelancer identity) · `resource_type`
   (internal / contractor / freelancer / consultant, default `internal`) · `default_role` CharField(80) ·
   `org_unit` FK `"core.OrgUnit"` (null, blank) · `skill_summary` CharField(255, blank) (quick filter; the
   matrix is the `hrm.EmployeeSkill` lens) · `weekly_capacity_hours` DecimalField(6,2, default 40,
   MinValueValidator 0) · `utilization_target_pct` PositiveSmallIntegerField (default 80, validators 1–100) ·
   `available_from` / `available_to` DateField (null, blank — contractor engagement window) · `status`
   (active / inactive) · `notes` TextField.
   `clean()`: exactly one of `employee`/`party` required; an employee may appear in the pool only once per
   tenant. Derived `name` property (employee → party → fallback). Skills/certs detail page links to the
   existing `hrm:employeeskill_list` lens (3.40) filtered by employee — **no new skill table**.
   **FKs (verified):** `hrm.EmployeeProfile`, `core.Party`, `core.OrgUnit`.
   Indexes: (tenant, resource_type), (tenant, status), (tenant, employee), (tenant, party).

2. **`ResourceAllocation`** [**RAL-**] — *one booking: a role (+ optionally a named resource) asked for or
   committed to a project / pipeline request / work package for a magnitude over a date window.*
   Covers bullets **2 (Allocation & Leveling)**, **3 (Team Assembly & Role Assignment)** and the demand half of
   **4 (Forecasting & Demand Planning)** — placeholders and soft bookings ARE the pipeline demand.
   Fields: `project` FK `"projects.Project"` (`CASCADE`, null, blank, related_name `allocations`) ·
   `project_request` FK `"projects.ProjectRequest"` (`SET_NULL`, null, blank — pipeline demand with no project
   yet) · `project_task` FK `"projects.ProjectTask"` (`SET_NULL`, null, blank — task-grain booking) ·
   `resource` FK `"projects.ResourceProfile"` (`SET_NULL`, null, blank — **NULL = placeholder**) · `role_name`
   CharField(80) (the generic role; the placeholder's whole identity) · `skill_requirements` CharField(255,
   blank) (Certinia's skills-on-request, free text until a taxonomy is justified) · `allocation_unit`
   (hours_per_week / pct_capacity / total_hours, default `hours_per_week`) · `hours_per_week` DecimalField(6,2,
   null, blank) · `pct_capacity` PositiveSmallIntegerField (null, blank, 1–100) · `total_hours`
   DecimalField(8,2, null, blank) · `start_date` DateField · `end_date` DateField (null = ongoing — the proven
   `crm.ResourceAllocation` convention) · `booking_status` (**requested / soft / firm / completed / cancelled /
   released** — Certinia hold↔assign, Kantata soft-book; a booking whose window contains today and status in
   (soft, firm) is *live*, derived) · `substitute_of` FK `"self"` (`SET_NULL`, null, blank,
   related_name `substituted_by` — the substitution chain) · `requested_by` FK `AUTH_USER_MODEL` (null,
   blank) · `notes` TextField.
   `clean()`: `project` or `project_request` required; `end_date >= start_date`; exactly one magnitude field
   per unit. Derived `planned_hours(win_start, win_end)` property — copy the proven
   `crm.ResourceAllocation.overlap_hours()` proration and extend it to the three units.
   **Verbs (POST-only, audited):** **assign-resource** (placeholder → named, fulfills bullet 3),
   **substitute** (release current + successor row via `substitute_of`), status transitions
   requested→soft→firm, cancel, complete.
   **Capacity board (computed view, no model):** per resource-week, sum of live `planned_hours` vs
   `weekly_capacity_hours` → over-allocation alerts (bullet 2) + a demand section splitting project-linked vs
   request-linked placeholders/soft bookings vs capacity, with a coverage-gap filter (bullet 4) and the
   smoothing guidance (the market-honest "flag + manually rebalance" position).
   **FKs (verified):** `projects.Project`, `projects.ProjectRequest`, `projects.ProjectTask`,
   `projects.ResourceProfile`, `AUTH_USER_MODEL`.
   Indexes: (tenant, resource), (tenant, project), (tenant, project_request), (tenant, booking_status),
   (tenant, start_date).

3. **`ResourceTimeEntry`** [**RTE-**] — *one day's logged hours against a project (and optionally a work
   package), with the submit→approve routing and the approved hours that make actuals-to-plan joinable.*
   Covers bullet **5 (Time Tracking & Timesheets)**. Deliberately the *thinnest* projects-side time table —
   not a fourth timesheet product (see trade-offs).
   Fields: `resource` FK `"projects.ResourceProfile"` (`CASCADE` — mirrors `hrm.Timesheet.employee`) ·
   `project` FK `"projects.Project"` (`SET_NULL`, null, blank — non-project time is loggable, HRM-entry
   precedent) · `project_task` FK `"projects.ProjectTask"` (`SET_NULL`, null, blank; 7.8 extends the task in
   place) · `entry_date` DateField · `hours` DecimalField(5,2, MinValueValidator > 0) ·
   `task_description` CharField(255, blank) · `status` (**draft / submitted / approved / rejected** — the
   machine proven twice in-house) · `submitted_at` DateTime (null) · `approved_by` FK `AUTH_USER_MODEL`
   (null, blank) · `approved_at` DateTime (null) · `decision_note` TextField(blank, rejection reason) ·
   `notes` TextField(blank).
   **NO billable flag, NO rates, NO money columns** (7.11/7.15/7.4; L29).
   **Weekly lens:** the register groups by resource + ISO week of `entry_date`; a **weekly bulk
   approve/reject verb** per person-week (function view — no header model). **Actuals-to-plan comparison
   (computed view, no model):** approved hours vs `ResourceAllocation.planned_hours` per project and per
   resource, with variance columns (Resource Guru's "scheduled vs actual", Runn's deviation alert).
   **FKs (verified):** `projects.ResourceProfile`, `projects.Project`, `projects.ProjectTask`,
   `AUTH_USER_MODEL`.
   Indexes: (tenant, resource, entry_date), (tenant, project, entry_date), (tenant, status).

**Auto-number prefixes to reserve:** `RSP`, `RAL`, `RTE` (verified unused repo-wide).

**Sidebar entry to add — one `LIVE_LINKS["7.3"]` block mapping all five bullets** (fragments and `?query=`
lenses follow the 2.1 / 7.1 / 6.19 precedents; final names are the todo agent's):

| Bullet | Route | Why |
|---|---|---|
| Resource Pool & Skills Inventory | `projects:rsp_list` | the live pool register; detail links to the existing `hrm:employeeskill_list` lens for the competency matrix/certifications. |
| Resource Allocation & Leveling | `projects:capacity_demand` | the computed capacity board: bookings vs capacity, over-allocation alerts, smoothing lens. |
| Team Assembly & Role Assignment | `projects:ral_list` | the booking register — placeholders, named bookings, assign/substitute verbs. |
| Resource Forecasting & Demand Planning | `projects:capacity_demand#demand` | the demand section of the same board (pipeline vs capacity + coverage-gap/hiring-trigger filter). |
| Time Tracking & Timesheets | `projects:rte_list` | the time register; the approval queue is its `?status=submitted` lens. |
| *extra live leaf:* Time Approvals | `projects:rte_list?status=submitted` | the 7.1 extra-leaf precedent (labels that aren't NavERP.md bullets are appended by the parser). |

**Trade-offs I am consciously accepting (state each in the code):**

1. **No `ResourceRequest` table.** Certinia and Planview model requests as their own object; 7.3 folds the
   request into the allocation (`booking_status="requested"` + `skill_requirements` + `requested_by`). One
   table, two market objects. If a real request-approval workflow is needed later, split it — the field set is
   already grouped for it.
2. **No timesheet header.** `hrm.Timesheet` has a header because payroll needs a locked document; project
   actuals-to-plan only needs approved rows. Flat entries + weekly verbs. If 7.11 wants a lockable weekly
   document, that is 7.11's model to add (FK-ing or extending this one), not 7.3's.
3. **Skills stay an HRM lens.** `hrm.EmployeeSkill` already ships proficiency + certifications and a live
   page (3.40). Re-declaring it project-side would be the second-person-master mistake in miniature. The
   price: matching on skills is filter-by-free-text until a projects-side skill requirement taxonomy is
   justified by usage.
4. **The availability calendar is a computed board, not a stored calendar.** Leave/absence deduction
   (Scoro/Resource Guru/Float behavior) needs HRM 3.10 data and is deferred; the board's capacity is
   uniform weekly hours and says so on the page.
5. **No smoothing engine.** The market position is honest: leaders flag over-allocation and rebalance by
   hand (Kelloo and MS-Project lineage excepted; Kantata's optimizer is the AI outlier). 7.3 ships alerts +
   a smoothing lens; an optimizer verb is a later pass.
6. **If the pass runs long, the cut order is: `ResourceProfile` → capacity board → `ResourceTimeEntry`.**
   `ResourceProfile` can collapse (allocations could string-FK `hrm.EmployeeProfile` + `core.Party` directly
   with a flat 40h capacity default) at the cost of bullet 1 losing its own live page; the capacity board can
   degrade to a filtered `ral_list`. **`ResourceTimeEntry` is never cut** — bullet 5 has no joinable actuals
   anywhere else in the repo (`hrm.TimesheetEntry.project` points at the 2.9 stand-in).

---

## Belongs to sibling sub-modules (parked, not scoped here)

- **Task execution & assignment UX — Kanban/Gantt, progress, task-level assignment workflow, sub-tasks** →
  **7.8** (extends `ProjectTask` in place). 7.3's `project_task` booking FK is planning grain only.
- **Budget planning, cost baseline, EVM, expense tracking, EAC/CPI/SPI, change control** → **7.4**. 7.3 ships
  **no money columns anywhere** (no rates, no cost, no billable value).
- **Deep timesheet UX — weekly grid document, billable vs non-billable, overtime & leave integration,
  utilization dashboards, chargeability** → **7.11 Time & Attendance Tracking** (and HRM 3.9/3.10/3.11 own
  attendance, leave and the payroll-grade timesheet). 7.3's `ResourceTimeEntry` is the project-facing slice
  7.11 may extend in place.
- **Portfolio & program capacity — multi-project resource pool, demand funnel governance, shared-resource
  dependency mapping** → **7.12**. 7.3's board is within-tenant-pool, not portfolio governance.
- **Approvals escalation, notification & reminder rules (missing timesheets, over-allocation notifications)** →
  **7.17 Workflow & Automation**. 7.3's verbs write `core.AuditLog` and surface in-page queues only.
- **HR & talent system connectors (Workday/BambooHR/ADP sync of resource pools and time data)** → **7.18**.
- **Org hierarchy & teams configuration, custom fields** → **7.19** (and `core.OrgUnit`).
- **Client-facing staffing visibility, SOW staffing commitments** → **7.14**.
- **Project financial actuals, revenue, invoicing from timesheets** → **7.15** (accounting owns the ledger,
  L29; `hrm.TimesheetEntry` billable value already exists on the HRM side).

## Deferred (later passes / integrations)

| Area | Why deferred |
|---|---|
| **Leave-aware capacity deduction** | Scoro/Resource Guru/Float all factor time off into capacity. Needs HRM 3.10 LeaveRequest integration (cross-app reads or a sync); the board documents uniform weekly hours until then. |
| **Scenario / what-if planning (copy a booking set, compare)** | Runn/Kelloo/Planview differentiator. Needs a scenario-copy mechanic over the whole booking set — a clean second 7.3 pass. |
| **AI staffing optimizer / intelligent skill matching** | Kantata Staffing Optimizer, Certinia Intelligent Staffing, Wrike AI forecasts. No ML infrastructure (same ruling as 7.1's AI re-scoring). Skill *suggestions* from role context (Certinia) are cheap enough to add when a skill taxonomy exists. |
| **Auto-filled timesheets from bookings** | Resource Guru's best mechanic; a form-prefill enhancement over data this pass already stores. |
| **Candidate comparison on skills/availability/margin (internal vs external)** | Kantata Candidate Assignments. Margin is money (7.4/7.15); a skills+availability-only compare can ride on data this pass stores. |
| **Role rate cards / cost rates** | Certinia/Runn. Money → 7.4/7.15 (L29). |
| **Missing-timesheet nudges & scheduled alerts** | Runn behavior. Needs 7.17's notification engine; a non-submitters filter is the cheap lens. |
| **Waitlists, equipment & meeting-room booking** | Resource Guru extras. Not people-resourcing; equipment would be a new pool type with none of this pass's models. |
| **Assignment schedule dependencies (Deltek-style chaining)** | 7.2's `TaskDependency` owns schedule logic; allocation chaining is a later nicety over `project_task`. |
| **HRM↔projects time reconciliation (merging `hrm.TimesheetEntry`'s `accounting.Project` lens with `projects.Project`)** | A spine-consolidation problem (the 2.9 stand-in), not a sub-module pass — same class as the 7.1 `PRJ-` ruling. 7.3 builds the joinable project-side actuals; the reconciliation is a future spine task. |
