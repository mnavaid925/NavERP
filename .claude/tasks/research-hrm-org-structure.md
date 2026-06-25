# Research — Module 3.2: Organizational Structure (hrm-org-structure)

## Leaders surveyed

1. **Workday HCM** — enterprise gold standard; supervisory orgs, position management, effective dating, drag-and-drop org studio — https://www.workday.com/en-us/products/human-capital-management/human-resource-management/org-management.html
2. **SAP SuccessFactors Employee Central** — foundation objects model: Legal Entity → Business Unit → Division → Department → Cost Center; job classification with pay grade propagation — https://community.sap.com/t5/human-capital-management-blog-posts-by-members/the-successfactors-employee-central-organization-structure/ba-p/13122280
3. **Oracle HCM Cloud** — departments + cost centers as distinct entities; position slots with FTE and funding source; tree-based hierarchy — https://docs.oracle.com/en/cloud/saas/human-resources/24d/faucf/cost-centers-and-departments.html
4. **Personio** — cleanest job-architecture model: job family → job track → job level → grade → salary band (min/mid/max); location-specific salary bands — https://support.personio.de/hc/en-us/articles/18286680534813
5. **Keka HR** — Indian mid-market leader; explicit department-head assignment as an implicit role used in multi-step approval chains; pay grades + bands tied to designations — https://help.keka.com/admin/knowledge/how-to-assign-department-head
6. **Darwinbox** — APAC enterprise; designations mapped to departments + bands + grades with unique identifier codes; cross-entity org charts across group companies — https://darwinbox.com/blog/advanced-hrms-features
7. **Zoho People** — SMB/mid-market; legal entity → business unit → division as structural layers, departments independent; cross-entity reporting relationships — https://help.zoho.com/portal/en/kb/people/administrator-guide/settings/manage-accounts/articles/organization-structure-zoho-people
8. **BambooHR** — SMB leader; job levels and salary bands configurable; org chart built-in with department grouping; directory searchable by department/division/location — https://www.bamboohr.com/product-updates/levels-and-bands
9. **ChartHop** — purpose-built org design / headcount planning; drag-and-drop what-if scenario modeling; groups + matrix teams; real-time financial impact of proposed changes — https://www.charthop.com/
10. **ADP Workforce Now** — enterprise payroll/HR; positions with unique IDs, status, and budget attributes; department codes + cost center codes as validation tables; job codes/titles catalog — https://apps.adp.com/en-US/apps/318664/built-position-intelligence-for-adp-workforce-now/features

---

## Codebase reality check (verified before recommending models)

| What exists | Where | What it has / what it lacks |
|---|---|---|
| `core.OrgUnit` | `apps/core/models.py:42` | `tenant`, `kind` (company/branch/department/team/cost_center), `name`, `parent` (self-FK). **No** `head`, `code`, `description`, `budget`, `is_active` |
| `core.Employment` | `apps/core/models.py:166` | `party`, `org_unit`, `manager` (→core.Party), `job_title`, `hired_on`, `status`. Org-chart hierarchy is derived from `manager` + `OrgUnit.parent` — no model needed |
| `hrm.Designation` | `apps/hrm/models.py:76` | `tenant`, `name`, `grade` (CharField), `department` (→core.OrgUnit), `min_salary`, `max_salary`, `is_active`. **Missing**: job_family, job_track/level, description, headcount budget |
| `tenants.BrandingSetting` | `apps/tenants/models.py:104` | `logo`, `primary_color`, `accent_color`, `email_from_name`, `email_footer`. Already covers all Company Setup / branding bullet. HRM must NOT replicate it |

**Constraint confirmed**: HRM cannot touch `apps/core/` or `apps/tenants/`. Any field that `core.OrgUnit` lacks must live in a new HRM-owned companion table that FKs into `core.OrgUnit` by string.

---

## Feature catalog by sub-module

### 3.2.1 Company Setup

- **Company details & locations** — registered name, tax ID, industry, address, phone per legal entity · seen in: SAP SuccessFactors, Oracle HCM, Zoho People · priority: **table-stakes** · spine: `core.OrgUnit` (kind="company") already exists; company-level extra fields belong in a new `hrm.CompanyProfile` companion · buildable now
- **Logo & branding** — company logo, primary/accent colors for letterheads and reports · seen in: Workday, BambooHR, Personio · priority: **table-stakes** · spine: `tenants.BrandingSetting` **already implements this** — HRM views read it; no new table · **REUSE, no new model**
- **Multi-location / work-site registry** — named office locations with address, used to assign employees and departments · seen in: Keka, ADP Workforce Now, Darwinbox, Oracle HCM · priority: **common** · spine: `core.OrgUnit` (kind="branch") handles hierarchy; a `hrm.WorkLocation` companion adds address + timezone + is_remote · buildable now
- **Fiscal / legal entity** — ability to designate which OrgUnit is a legal entity for statutory purposes · seen in: SAP SuccessFactors, Oracle HCM, Zoho People · priority: **common** · spine: `core.OrgUnit.kind` already has "company"; a `hrm.CompanyProfile` flag `is_legal_entity` distinguishes it · buildable now (or just the kind field)

### 3.2.2 Department Management

- **Department CRUD** — create, edit, deactivate departments with code, name, description · seen in: Workday, SAP SuccessFactors, Keka, Darwinbox, BambooHR, ADP · priority: **table-stakes** · spine: `core.OrgUnit` (kind="department") IS the department; a `hrm.DepartmentProfile` companion adds the missing fields (code, description, is_active) · buildable now
- **Department head / owner assignment** — designate one employee as the head; used in approval chains (leave, expense, requisitions) · seen in: Keka (explicit "assign department head" feature), Darwinbox, ADP, SAP SuccessFactors, Oracle HCM · priority: **table-stakes** · spine: new `hrm.DepartmentProfile.head` FK → `hrm.EmployeeProfile` · buildable now
- **Parent department hierarchy** — nested departments (e.g., Engineering → Backend) · seen in: Workday, SAP SuccessFactors, Oracle HCM, Zoho People · priority: **table-stakes** · spine: `core.OrgUnit.parent` (self-FK) **already provides this** — no new field needed · REUSE
- **Department active/inactive toggle** — deactivate a department without deleting it · seen in: Keka, Darwinbox, BambooHR · priority: **common** · spine: `hrm.DepartmentProfile.is_active` (new field) · buildable now

### 3.2.3 Designation / Job Titles

- **Job family grouping** — group similar roles (e.g., "Engineering," "Sales") above the designation level · seen in: Personio (job family → job track → level), Workday (job family → job profile), SAP SuccessFactors (job classification groupings) · priority: **common** · spine: new `hrm.JobFamily` table (name, description) · buildable now
- **Job grade / level** — named grade (e.g., "G1", "L3", "Senior") with a sort order, separate from the salary band · seen in: Personio (grade integer + level label), Keka (pay grade), Darwinbox (bands + grades), ADP (job grade) · priority: **table-stakes** · spine: enhance `hrm.Designation.grade` from free-text CharField to FK → new `hrm.JobGrade` table · buildable now (migration required)
- **Job description / requirements** — free-text or structured description of duties, qualifications, and competencies stored against the designation · seen in: Workday (job profile), Darwinbox (job description per designation), ADP (position description), SAP SuccessFactors (job classification attributes) · priority: **common** · spine: `hrm.Designation` already exists — add `description` + `requirements` TextFields · buildable now (simple field addition)
- **Salary band (min/mid/max)** — band of pay attached to a grade for equity and offer generation · seen in: Personio (min/mid/max + location-specific), BambooHR (levels & bands), Keka, Darwinbox · priority: **common** · spine: `hrm.Designation` already has `min_salary` / `max_salary`; add `mid_salary` for the midpoint · buildable now (field addition)
- **Headcount budget** — approved number of positions for a designation in a department · seen in: Darwinbox ("total number of roles to be recruited" per designation), ADP (position has budget), Oracle HCM (FTE budget) · priority: **differentiator** · spine: `hrm.Designation.budgeted_headcount` IntegerField · buildable now (field addition)
- **Designation hierarchy level** — integer sort order indicating seniority for reporting and sequencing · seen in: Personio (level within track), Workday (management level), Darwinbox · priority: **common** · spine: `hrm.JobGrade.level_order` PositiveIntegerField on the new JobGrade model · buildable now

### 3.2.4 Organization Chart

- **Reporting-line org chart** — visual tree of who reports to whom, derived from `core.Employment.manager` + `core.OrgUnit.parent` · seen in: every product surveyed · priority: **table-stakes** · spine: **derived view** — query `EmployeeProfile` → `Employment.manager` chain; rendered with HTMX / Tailwind cards or JSON tree; **no new model** · buildable now (view only)
- **Department-centric view** — chart grouped by department/OrgUnit rather than by person · seen in: Workday, BambooHR, ChartHop, Zoho People · priority: **common** · spine: derived from `core.OrgUnit.parent` tree; same view, different rendering mode · buildable now (view only)
- **Open positions on chart** — unfilled headcount slots shown alongside filled positions · seen in: ChartHop, ADP (position management), Pingboard, Workday · priority: **differentiator** · spine: `hrm.Designation.budgeted_headcount` minus current active employee count → shown as "open" slots on the chart; no separate table if headcount is tracked on Designation · integration/later (needs headcount analytics)
- **Effective-dated reorg / scenario planning** — plan a future org structure and preview it before the change-date · seen in: Workday (org studio), ChartHop (what-if scenarios) · priority: **differentiator** · spine: would require effective-dated OrgUnit changes (very complex); deferred — beyond a single Django pass

### 3.2.5 Cost Centers

- **Cost center CRUD** — create cost centers with code, name, description, and active status · seen in: SAP SuccessFactors, Oracle HCM, Keka, ADP, Fynth HRMS, Darwinbox · priority: **table-stakes** · spine: `core.OrgUnit` (kind="cost_center") IS the cost center entity; a `hrm.CostCenterProfile` companion adds `code`, `description`, `is_active`, `budget_annual`, `budget_currency` · buildable now
- **Cost center owner / manager** — designate the employee responsible for the cost center's budget · seen in: Oracle HCM, SAP SuccessFactors, Keka, Fynth HRMS · priority: **common** · spine: `hrm.CostCenterProfile.owner` FK → `hrm.EmployeeProfile` · buildable now
- **Annual budget allocation** — store the approved annual budget amount against the cost center · seen in: SAP SuccessFactors, Keka, Personio (cost planning), Fynth HRMS, ADP · priority: **common** · spine: `hrm.CostCenterProfile.budget_annual` DecimalField + `budget_year` PositiveSmallIntegerField · buildable now
- **Cost center hierarchy** — cost centers can have a parent cost center (roll-up reporting) · seen in: SAP SuccessFactors ("Cost Centers can have parent Cost Centers"), Oracle HCM · priority: **common** · spine: `core.OrgUnit.parent` already handles this (OrgUnit is self-FK) · REUSE
- **Department-to-cost-center mapping** — link a department OrgUnit to one or more cost centers for payroll allocation · seen in: SAP SuccessFactors, Oracle HCM, ADP, Keka · priority: **common** · spine: `hrm.DepartmentProfile.cost_center` FK → `core.OrgUnit` (kind="cost_center") · buildable now
- **Budget tracking / actual vs. budget reporting** — compare allocated budget against actual payroll spend (requires GL integration) · seen in: Personio cost planning, ChartHop headcount finance, ADP · priority: **differentiator** · spine: actual spend is derived from `accounting.PayrollRun` → GL; report view only, no new model · integration/later (requires Accounting module)

---

## Recommended build scope (this pass — 3 HRM-owned models + 1 enhanced model + 2 derived views)

### Model 1: `hrm.JobGrade` [JG-]
**Purpose:** Replaces the free-text `hrm.Designation.grade` CharField with a first-class, orderable grade catalog — the backbone of salary equity, approval routing, and org chart level-coloring.

**Fields justified by research (Personio, Keka, Darwinbox, Workday):**
- `tenant` FK → `core.Tenant`
- `name` CharField(50) — e.g., "G1", "L3", "IC5", "Senior"
- `level_order` PositiveSmallIntegerField — integer sort rank for hierarchy display and sequencing (Personio level within track; Workday management level)
- `description` TextField(blank=True) — narrative definition of what this grade means
- `is_active` BooleanField(default=True)
- unique_together: (`tenant`, `name`)

**Reuses:** `core.Tenant` only. Designation will gain a FK to this model (migration).

**Migration note:** `hrm.Designation.grade` CharField stays as a free-text fallback; a new `hrm.Designation.job_grade` nullable FK → `hrm.JobGrade` is added alongside it. Old CharField data is preserved; views prefer `job_grade` when set.

---

### Model 2: `hrm.DepartmentProfile` [DP-]
**Purpose:** Companion to `core.OrgUnit` (kind="department") — adds the HRM-specific fields that cannot live in the shared core without violating the Module 0 boundary.

**Fields justified by research (Keka dept-head, SAP SuccessFactors, Darwinbox, BambooHR, Oracle HCM):**
- `tenant` FK → `core.Tenant`
- `org_unit` OneToOneField → `core.OrgUnit` — the canonical department node; no standalone name or parent (those live on OrgUnit)
- `code` CharField(20, blank=True) — short mnemonic (e.g., "ENG", "FIN"); used by payroll splits and reports (ADP, SAP SuccessFactors)
- `description` TextField(blank=True)
- `head` FK → `hrm.EmployeeProfile` (null=True, blank=True) — the department head; used as an implicit role in future approval chains (Keka's core differentiator)
- `cost_center` FK → `core.OrgUnit` (null=True, blank=True, limit_choices_to={'kind':'cost_center'}) — maps payroll to the cost center (SAP SuccessFactors, Oracle HCM, ADP)
- `is_active` BooleanField(default=True) — soft-delete without removing the OrgUnit (Keka, Darwinbox)
- unique_together: (`tenant`, `org_unit`)

**Reuses:** `core.OrgUnit` (the department node and the cost_center node), `hrm.EmployeeProfile` (the head).

---

### Model 3: `hrm.CostCenterProfile` [CC-]
**Purpose:** Companion to `core.OrgUnit` (kind="cost_center") — adds budget, owner, and code fields that core cannot hold.

**Fields justified by research (SAP SuccessFactors, Oracle HCM, Keka, Fynth HRMS, ADP):**
- `tenant` FK → `core.Tenant`
- `org_unit` OneToOneField → `core.OrgUnit` — the canonical cost_center node
- `code` CharField(20, blank=True) — short alphanumeric code for payroll allocation and reporting (ADP dept codes, SAP SuccessFactors cost center codes)
- `description` TextField(blank=True)
- `owner` FK → `hrm.EmployeeProfile` (null=True, blank=True) — budget owner / cost center manager (Oracle HCM, SAP SuccessFactors, Keka)
- `budget_annual` DecimalField(14, 2, null=True, blank=True) — approved annual personnel budget for this cost center (Keka, Personio cost planning, SAP SuccessFactors)
- `budget_year` PositiveSmallIntegerField(null=True, blank=True) — the fiscal year the budget applies to
- `is_active` BooleanField(default=True)
- unique_together: (`tenant`, `org_unit`)

**Reuses:** `core.OrgUnit` (the cost_center node and its parent self-FK for hierarchy), `hrm.EmployeeProfile` (the owner).

---

### Model 4: `hrm.Designation` — ENHANCE (no new model, migration only)
**Purpose:** Lift grade from free-text to FK; add job description and headcount budget fields; add mid-salary for band midpoint.

**Fields to add (justified by research):**
- `job_grade` FK → `hrm.JobGrade` (null=True, blank=True, on_delete=SET_NULL) — replaces raw `grade` CharField (Personio, Keka, Darwinbox)
- `description` TextField(blank=True) — job duties / purpose (Workday job profile, Darwinbox, ADP position description)
- `requirements` TextField(blank=True) — qualifications / competencies (Darwinbox, Personio career frameworks)
- `mid_salary` DecimalField(14, 2, null=True, blank=True) — band midpoint alongside existing min/max (Personio min/mid/max salary band)
- `budgeted_headcount` PositiveSmallIntegerField(null=True, blank=True) — approved position slots for this role (Darwinbox, ADP position management, Oracle HCM FTE)

**Existing fields preserved unchanged:** `name`, `grade` (CharField kept as fallback), `department` (FK→core.OrgUnit), `min_salary`, `max_salary`, `is_active`.

---

### Derived View 1: Org Chart (no model)
**Source:** `hrm.EmployeeProfile` → `core.Employment.manager` (reporting chain) + `core.OrgUnit.parent` (department tree)  
**Render:** JSON tree endpoint consumed by an HTMX-driven collapsible card tree in the template; optionally a flat table "department view" grouping employees by OrgUnit  
**Why no model:** every product surveyed agrees the chart is a derived visualization — it reads the manager / org_unit fields already stored, not a separate data store  

---

### Derived View 2: Company Setup page (no model)
**Source:** `core.OrgUnit` (kind="company") for company name / parent hierarchy; `tenants.BrandingSetting` for logo / colors  
**Render:** A read/edit page in HRM that surfaces the company-level OrgUnit's name + the BrandingSetting fields already managed in tenant settings  
**Why no model:** `BrandingSetting` (Module 0) already handles logo and branding; `core.OrgUnit` already handles the company node — HRM just reads them  

---

## Deferred (later passes / integrations)

- **Job families / tracks** — Personio-style `hrm.JobFamily` + `hrm.JobTrack` tables for career laddering. Valuable but out of scope for this foundational pass; the `hrm.JobGrade` + `hrm.Designation.description` fields lay the groundwork. Revisit when building 3.38 Talent Management.
- **Position management (position slots)** — Workday/ADP "open position" concept (a named slot distinct from the person who fills it). Requires a `hrm.Position` table and headcount-control logic. Deferred; `budgeted_headcount` on Designation is the lightweight proxy for now.
- **Effective-dated org changes** — Workday org studio / ChartHop scenario planning. Requires storing historical OrgUnit membership with from/to dates. Far beyond a single Django pass; deferred to a dedicated workforce-planning sub-module.
- **Location work-site registry** — `hrm.WorkLocation` companion to `core.OrgUnit` (kind="branch") with address + timezone + is_remote. Useful but not required for the 5 NavERP.md bullets; deferred to employee management (3.1) or a future location sub-module.
- **Budget tracking vs. actuals** — comparing `CostCenterProfile.budget_annual` against actual payroll spend requires the Accounting module (PayrollRun → GL). Deferred until Accounting (Module 2) is built.
- **Org-chart export (PDF/PNG)** — standard feature in ChartHop, BambooHR, OrgVue. Deferred; browser print / screenshot covers the need until a dedicated export view is warranted.
- **Matrix / cross-functional reporting** — Workday matrix organizations, Zoho cross-entity reporting. Deferred; `core.Employment.manager` is single-parent; a matrix structure needs a many-many join table.
- **Work location integration on org chart** — pinning employees to physical offices on a map (ChartHop). Integration/later; requires geocoding data.
