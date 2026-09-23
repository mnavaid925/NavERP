# Research — Sub-module 7.19: Master Data & Configuration (Module 7 — Project Management, `projects`)

- **Sub-module:** 7.19 Master Data & Configuration · **Module:** 7 Project Management · **App:** `apps/projects`
- **Base commit:** `3e10760acea9757261c6e5f45ec85e119fda5d09`
- **Date:** 2026-09-23 · **Phase:** 1 (research) · **Output:** `.claude/tasks/research-projects-7.19.md`
- **Mission:** 7.19 is the **foundational master data and configuration layer** of the Project Management module. It provides reusable project templates & methodology frameworks (Waterfall, Agile, Hybrid) with pre-built WBS structures; a flexible, validated custom fields engine with conditional visibility; enterprise matrix team structures spanning corporate organizational units (`core.OrgUnit`); and multi-region localization & regional profile settings (languages, timezones, work-week patterns, formatting). It provides the core configuration spine for projects, linking directly to the platform's core tenant models without duplicating platform-wide services.

---

## 1. Repo state checked first (evidence, not docs)

### 1.1 Module 7 sidebar state (`apps/core/navigation.py`)
- `apps/core/navigation.py` inspection reveals `LIVE_LINKS` keys **7.1 through 7.18** are fully registered (:1865–:2153).
- **7.19 is the final, unbuilt sub-module of Module 7 (Project Management)**.
- Sibling models available to FK:
  - `projects.Project` [PRJ-] (from 7.1 `ProjectInitiation/Projects.py`) — the universal container every later `7.M` sub-module attaches to.
  - Sibling sub-modules 7.1 through 7.18 provide the execution targets: `ProjectTask` (7.2), `ProjectMilestone` (7.2), `ProjectRisk` (7.5), `ProjectWorkflowRule` (7.17), `ProjectIntegrationConnector` (7.18).

### 1.2 Migration & Prefix state
- `apps/projects/migrations/` ends at **`0027_projectsyncjob_syj_tnt_active_idx.py`** (7.18 integration).
- The next migration for 7.19 will be **`0028_...`**.
- Prefixes taken inside `projects` (verified via `grep NUMBER_PREFIX =`):
  `PRJ`, `PRQ`, `PST`, `PKO`, `TSK`, `DEP`, `BSL`, `MST`, `RAL`, `RSP`, `RTE`, `CCA`, `PBL`, `PEX`, `BVR`, `RSK`, `ISS`, `RRA`, `ESC`, `QPL`, `QRV`, `QCI`, `QDF`, `REQ`, `SCI`, `SCR`, `SVR`, `TBK`, `TCL`, `CHN`, `CHM`, `MTG`, `AGI`, `MAIT`, `NTF`, `DSH`, `PFD`, `DTM`, `PDM`, `KNE`, `TAC`, `OTR`, `POT`, `PRT`, `PGM`, `PIN`, `PDEP`, `EPC`, `SPT`, `IMP`, `RET`, `CPA`, `CFB`, `SOW`, `SWA`, `VHD`, `PCI`, `RTC`, `PBR`, `PRS`, `PPR`, `PDB`, `REP`, `RUN`, `PWF`, `PAR`, `RTS`, `PWH`, `IXC`, `SYJ`, `SYR`.
- **Free and recommended prefixes for 7.19 (verified repo-wide — 0 hits across all apps):**
  - **`PTM-`** for `ProjectTemplate`
  - **`PCF-`** for `ProjectCustomField`
  - **`PTE-`** for `ProjectTeam`
  - **`PLS-`** for `ProjectLocaleSetting`
  - Unnumbered child join model: `ProjectTeamMember` (mirrors `ProjectWebhookDelivery`, `ConnectorFieldMapping`, `TaskBlock`).

### 1.3 Spine entities verified to exist (grep evidence)
- **`core.Tenant`** (`apps/core/models/Tenant.py:17`): Mandatory multi-tenant isolation anchor for all 7.19 models via `TenantOwned` and `TenantNumbered`.
- **`core.OrgUnit`** (`apps/core/models/OrgUnit.py:5`): Exists with `kind` ∈ `['company', 'branch', 'department', 'team', 'cost_center']`. Reused by `ProjectTeam.org_unit` for matrix organizational alignment.
- **`core.Language`** (`apps/core/models/Localization.py:58`): Global ISO 639-1 language master (`code`, `name`, `native_name`, `is_rtl`). Reused by `ProjectLocaleSetting.language`.
- **`core.TimeZone`** (`apps/core/models/Localization.py:87`): Global IANA timezone master (`name`, `label`, `utc_offset_minutes`, `observes_dst`). Reused by `ProjectLocaleSetting.time_zone`.
- **`accounting.Currency`** (`apps/accounting/models/GeneralLedger/Currencies.py:18`): Global ISO 4217 currency master. Reused by `ProjectLocaleSetting.currency` and `ProjectTemplate.target_budget`.
- **`settings.AUTH_USER_MODEL`**: Standard user model for `team_lead`, `created_by`, and `ProjectTeamMember.user`.
- **`projects.Project`** (`apps/projects/models/ProjectInitiation/Projects.py:27`): Exists with `methodology` choices (`waterfall`, `agile`, `hybrid`). Line 63 explicitly states: `#: The reusable template LIBRARY behind this is 7.19 Master Data & Configuration's.`

### 1.4 URL namespace check
- Verified in `apps/projects/urls/`: No colliding routes exist for `ptm_*`, `pcf_*`, `pte_*`, `pls_*`, `templates/`, `custom-fields/`, `teams/`, or `locale-settings/`.

---

## 2. Leaders surveyed (with source links)

1. **ServiceNow Strategic Portfolio Management (SPM)** — Enterprise PPM suite featuring lifecycle project templates (`pm_project_template`), dictionary custom fields with UI policies & client scripts, cross-functional teamspaces, and platform localization framework.
   *Source:* [ServiceNow SPM Project Templates](https://docs.servicenow.com/bundle/washingtondc-it-business-management/page/product/project-management/concept/c_ProjectTemplates.html)
2. **Microsoft Dynamics 365 Project Operations** — Enterprise PSA/PPM solution leveraging Dataverse custom entities, WBS project templates, organizational units (contracting vs resourcing units), and multi-currency/regional format profiles.
   *Source:* [Microsoft Project Operations Templates](https://learn.microsoft.com/en-us/dynamics365/project-operations/project-management/project-templates)
3. **Jira Enterprise (Atlassian)** — Enterprise agile/hybrid project configuration platform with project templates/schemes, centralized custom field libraries, Atlassian Teams (cross-functional matrix teams), and multi-language pack support.
   *Source:* [Jira Enterprise Custom Fields & Config](https://support.atlassian.com/jira-cloud-administration/docs/configure-custom-fields/)
4. **Planview AdaptiveWork (formerly Clarizen)** — Leading enterprise PPM solution offering methodology templates (Waterfall, Agile, Hybrid), dynamic custom fields with conditional visibility rules, and matrix resource team management.
   *Source:* [Planview AdaptiveWork Configuration](https://success.planview.com/Planview_AdaptiveWork/Settings/Customization/Custom_Fields)
5. **Smartsheet / Resource Management by Smartsheet** — Modern enterprise work management with Blueprint project templates, dynamic custom columns/forms, cross-departmental matrix teams, and regional account locale settings.
   *Source:* [Smartsheet Project Templates & Blueprints](https://help.smartsheet.com/articles/2482329-create-and-use-templates)
6. **Oracle Primavera Cloud / NetSuite OpenAir** — Heavyweight engineering PPM and PSA systems featuring hierarchical WBS templates, User-Defined Fields (UDFs) with strict validation, Organizational Breakdown Structure (OBS) matrix teams, and regional formatting.
   *Source:* [Oracle Primavera Cloud WBS & Templates](https://www.oracle.com/industries/construction-engineering/primavera-cloud-project-management/)
7. **Monday.com Enterprise** — Work OS providing reusable workspace/board templates, 30+ column-type custom fields with conditional logic, cross-functional teams, and multilingual support.
   *Source:* [Monday.com Enterprise Templates & Columns](https://support.monday.com/hc/en-us/articles/115005310965-Board-templates)
8. **Asana Enterprise** — Collaborative work management with reusable Project Templates, Organization Custom Field Library, form branching logic, cross-functional Teams, and global locale configurations.
   *Source:* [Asana Enterprise Custom Fields & Templates](https://asana.com/enterprise)

---

## 3. Feature catalog (this sub-module only)

### 3.1 Project Templates & Methodologies (NavERP 7.19 Bullet 1)
- **Methodology-Driven Templates** — Pre-configured project blueprints supporting Waterfall (linear stage-gate), Agile (scrum sprints/backlogs), and Hybrid (stage-gate milestone governance with agile sprint execution) frameworks.
  · *Seen in:* ServiceNow SPM, Planview, Microsoft Project Operations, Jira Enterprise.
  · *Priority:* `table-stakes`.
  · *Spine:* Stored in new `ProjectTemplate` table; maps to `projects.Project.methodology`.
  · *Buildable now:* Yes.
- **Pre-Built Work Breakdown Structure (WBS)** — Standardized phase, milestone, and deliverable hierarchies serialized in a structured JSON schema, including task descriptions, estimated duration days, and baseline sequencing.
  · *Seen in:* Microsoft Project Operations, Oracle Primavera, ServiceNow SPM, Smartsheet.
  · *Priority:* `table-stakes`.
  · *Spine:* `ProjectTemplate.wbs_structure` (JSONField).
  · *Buildable now:* Yes.
- **Pre-Configured Workflow Stage Gates** — Reusable lifecycle stage gates, default statuses, and exit/entry approval requirements defined at the template level.
  · *Seen in:* ServiceNow SPM, Planview AdaptiveWork, Asana Enterprise.
  · *Priority:* `common`.
  · *Spine:* `ProjectTemplate.workflow_config` (JSONField); links conceptually to 7.17 `ProjectWorkflowRule`.
  · *Buildable now:* Yes.
- **Recommended Resource Roles & Composition** — Pre-defined standard roles and disciplines (e.g., Project Manager, Technical Lead, Solution Architect, QA Lead) attached to the template for initial team staffing.
  · *Seen in:* Microsoft Project Operations, Planview, NetSuite OpenAir.
  · *Priority:* `common`.
  · *Spine:* `ProjectTemplate.default_roles` (JSONField).
  · *Buildable now:* Yes.
- **Template Complexity & Governance Sizing** — Categorization of templates by delivery domain (Software, Infrastructure, Consulting, R&D, Marketing) and project scale/complexity (Small, Medium, Large, Enterprise) with active and default flags.
  · *Seen in:* ServiceNow SPM, Jira Enterprise, Monday.com Enterprise.
  · *Priority:* `common`.
  · *Spine:* `ProjectTemplate` fields (`category`, `complexity`, `is_active`, `is_default`).
  · *Buildable now:* Yes.

### 3.2 Custom Fields & Forms (NavERP 7.19 Bullet 2)
- **Multi-Entity Target Scope** — Dynamic custom fields configured specifically across project management entities: `project`, `task`, `milestone`, `risk`, and `team`.
  · *Seen in:* Jira Enterprise, Planview AdaptiveWork, Monday.com Enterprise, Asana Enterprise.
  · *Priority:* `table-stakes`.
  · *Spine:* `ProjectCustomField.target_entity`.
  · *Buildable now:* Yes.
- **Rich Data Type Catalog** — Support for user-defined field types: Text, Long Text (Textarea), Integer, Decimal/Currency, Date, Boolean (Yes/No), Single Select Dropdown, Multi-Select, URL, and User Reference.
  · *Seen in:* Jira Enterprise, Monday.com, Planview, ServiceNow SPM.
  · *Priority:* `table-stakes`.
  · *Spine:* `ProjectCustomField.field_type`.
  · *Buildable now:* Yes.
- **Strict Validation Rules** — Configurable validation parameters including required flags, minimum/maximum numeric ranges, regex string patterns, and predefined JSON option lists for choice types.
  · *Seen in:* ServiceNow SPM, Planview, Jira Enterprise, Oracle Primavera UDFs.
  · *Priority:* `table-stakes`.
  · *Spine:* `ProjectCustomField` validation fields (`is_required`, `min_value`, `max_value`, `regex_pattern`, `choices_list`).
  · *Buildable now:* Yes.
- **Form Categorization & Section Layout** — Grouping of custom fields into intuitive form sections (General, Governance, Technical, Financial, Risk, Custom) with custom display ordering and placeholder guidance.
  · *Seen in:* ServiceNow SPM, Microsoft Project Operations (Dataverse forms), Monday.com.
  · *Priority:* `common`.
  · *Spine:* `ProjectCustomField.form_section`, `display_order`, `placeholder`, `help_text`.
  · *Buildable now:* Yes.
- **Conditional Visibility Engine** — Rules governing field display based on other field states (e.g., reveal "Sprint Cadence" only when `methodology == "agile"`, or "Regulatory ID" when `category == "infrastructure"`).
  · *Seen in:* Planview AdaptiveWork, ServiceNow UI Policies, Smartsheet Dynamic Forms.
  · *Priority:* `differentiator`.
  · *Spine:* `ProjectCustomField.visibility_rule` (JSONField).
  · *Buildable now:* Yes.

### 3.3 Organization Hierarchy & Teams (NavERP 7.19 Bullet 3)
- **Matrix Team Structures** — Project delivery teams supporting matrixed resource assignment across functional corporate boundaries (`core.OrgUnit`), contrasting dedicated project teams against cross-functional shared resource pools.
  · *Seen in:* ServiceNow SPM Teamspaces, Microsoft Project Operations, Planview, Oracle Primavera OBS.
  · *Priority:* `table-stakes`.
  · *Spine:* `ProjectTeam` [PTE-] linking to `core.OrgUnit` and optional `projects.Project`.
  · *Buildable now:* Yes.
- **Team Taxonomy & Operational Modes** — Classification by team structure: Dedicated Project Team, Matrix Shared Team, Cross-Functional Delivery Team, Agile Scrum/Kanban Pod, or External Vendor/Contractor Team.
  · *Seen in:* Jira Enterprise (Atlassian Teams), Monday.com, Planview.
  · *Priority:* `common`.
  · *Spine:* `ProjectTeam.team_type`.
  · *Buildable now:* Yes.
- **Team Leadership & Geographic Hub** — Assignment of dedicated Team Leads (`settings.AUTH_USER_MODEL`) and location/hub designations (e.g. "London HQ", "Frankfurt", "Remote EMEA").
  · *Seen in:* Jira Enterprise, Asana Enterprise, Monday.com Resource Directory.
  · *Priority:* `common`.
  · *Spine:* `ProjectTeam.team_lead`, `ProjectTeam.location`.
  · *Buildable now:* Yes.
- **Matrix Team Membership & Allocation Percentages** — Child membership records linking individual users to teams with fractional allocation percentages (e.g., 50% commitment to Project A, 50% to Functional Line), functional project roles, and primary contact indicators.
  · *Seen in:* Planview, Microsoft Project Operations, NetSuite OpenAir.
  · *Priority:* `table-stakes`.
  · *Spine:* `ProjectTeamMember` child table linking `ProjectTeam` and `settings.AUTH_USER_MODEL`.
  · *Buildable now:* Yes.
- **Corporate OrgUnit Alignment** — Direct integration with corporate organizational units (`core.OrgUnit`), allowing executive rollups and department-level governance over project delivery teams.
  · *Seen in:* Microsoft Project Operations, ServiceNow SPM, Oracle Primavera OBS.
  · *Priority:* `common`.
  · *Spine:* `ProjectTeam.org_unit` → `core.OrgUnit`.
  · *Buildable now:* Yes.

### 3.4 Localization & Multi-Language (NavERP 7.19 Bullet 4)
- **Project Regional Settings Profiles** — Configurable regional and locale profiles applicable tenant-wide as defaults or assigned as specific project overrides.
  · *Seen in:* Microsoft Project Operations, Oracle Primavera, NetSuite OpenAir, ServiceNow.
  · *Priority:* `table-stakes`.
  · *Spine:* `ProjectLocaleSetting` [PLS-] linking optionally to `projects.Project`.
  · *Buildable now:* Yes.
- **Platform Language & RTL Integration** — Foreign key linkage to platform languages (`core.Language`), ensuring projects adopt tenant-approved language packs and RTL presentation rules.
  · *Seen in:* Jira Enterprise, ServiceNow Localization Framework, Planview.
  · *Priority:* `table-stakes`.
  · *Spine:* `ProjectLocaleSetting.language` → `core.Language`.
  · *Buildable now:* Yes.
- **Timezone & Calendar Awareness** — Direct reference to IANA timezone definitions (`core.TimeZone`) to establish the authoritative time boundary for project schedules, task deadlines, and timesheet cuts.
  · *Seen in:* Oracle Primavera Cloud, Microsoft Project Operations, Jira Enterprise.
  · *Priority:* `table-stakes`.
  · *Spine:* `ProjectLocaleSetting.time_zone` → `core.TimeZone`.
  · *Buildable now:* Yes.
- **Working Hours & Work-Week Calendar Patterns** — Explicit configuration of standard working hours per day (e.g., 8.00 hours) and active working days patterns (e.g., Monday through Friday, or Sunday through Thursday for Middle East locales).
  · *Seen in:* Microsoft Project Operations, Oracle Primavera, Smartsheet.
  · *Priority:* `common`.
  · *Spine:* `ProjectLocaleSetting.working_hours_per_day`, `working_days_pattern` (JSONField).
  · *Buildable now:* Yes.
- **Date, Time & Number Formatting Preferences** — Explicit formatting choices for dates (ISO `YYYY-MM-DD`, UK/EU `DD/MM/YYYY`, US `MM/DD/YYYY`, East Asia `YYYY/MM/DD`), time display (12-hour vs. 24-hour), first day of the week (Monday, Saturday, Sunday), and number/currency decimal notation.
  · *Seen in:* Smartsheet, NetSuite OpenAir, Microsoft Project Operations, Jira.
  · *Priority:* `common`.
  · *Spine:* `ProjectLocaleSetting` format fields (`date_format`, `time_format`, `first_day_of_week`, `number_format`, `currency`).
  · *Buildable now:* Yes.

### 3.5 Beyond the bullets (Enterprise Differentiators)
- **Project Instantiation Engine Ready** — Clean JSON schema contracts on `ProjectTemplate` allowing future or custom action workflows to clone the WBS hierarchy into live `ProjectTask` and `ProjectMilestone` records with a single click.
  · *Seen in:* ServiceNow SPM, Monday.com Enterprise, Asana Enterprise.
  · *Priority:* `differentiator`.
  · *Buildable now:* Yes (schema structured and pre-seeded).

---

## 4. Recommended build scope (this pass — 1–4 models)

To fully cover the 4 NavERP.md feature bullets with maximum elegance, zero redundancy, and strict adherence to the unified spine, we recommend exactly **4 primary models** plus **1 unnumbered child membership table**:

```
apps/projects/models/MasterDataConfiguration/
├── ProjectTemplates.py         # ProjectTemplate [PTM-] (Bullet 1)
├── ProjectCustomFields.py      # ProjectCustomField [PCF-] (Bullet 2)
├── ProjectTeams.py             # ProjectTeam [PTE-] + ProjectTeamMember (Bullet 3)
└── ProjectLocaleSettings.py    # ProjectLocaleSetting [PLS-] (Bullet 4)
```

### 4.1 `ProjectTemplate` [PTM-]
- **Purpose:** Reusable project blueprint and methodology framework (Bullet 1).
- **Base:** `TenantNumbered` (`NUMBER_PREFIX = "PTM"`).
- **Fields:**
  - `name`: `CharField(max_length=255)` — Template title (e.g., "Enterprise Cloud Migration (Hybrid)", "Standard Mobile App (Agile)", "Capital Construction Stage-Gate").
  - `code`: `CharField(max_length=50, blank=True)` — Short identifier (e.g., "TMPL-HYB-01").
  - `methodology`: `CharField(max_length=20, choices=METHODOLOGY_CHOICES, default="hybrid")` — `waterfall`, `agile`, `hybrid`. Matches `Project.METHODOLOGY_CHOICES`.
  - `category`: `CharField(max_length=30, choices=CATEGORY_CHOICES, default="software")` — `software`, `infrastructure`, `consulting`, `r_and_d`, `marketing`, `operational`, `internal`.
  - `complexity`: `CharField(max_length=20, choices=COMPLEXITY_CHOICES, default="medium")` — `small`, `medium`, `large`, `enterprise`.
  - `description`: `TextField(blank=True)` — Scope description and guidance for project managers.
  - `estimated_duration_days`: `PositiveIntegerField(default=30)` — Baseline duration estimate in business days.
  - `target_budget`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))` — Indicative budget estimate.
  - `default_roles`: `JSONField(default=list, blank=True)` — List of recommended roles (e.g. `["Project Manager", "Lead Architect", "Senior Developer", "QA Analyst"]`).
  - `wbs_structure`: `JSONField(default=list, blank=True)` — Hierarchical WBS tree with pre-built phases, milestones, tasks, estimates, and order.
  - `workflow_config`: `JSONField(default=dict, blank=True)` — Default stage gate names and approval requirements.
  - `is_active`: `BooleanField(default=True)` — Active availability in template selector.
  - `is_default`: `BooleanField(default=False)` — System default template for the methodology.
  - `created_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")`
- **Indexes:** `["tenant", "methodology"]`, `["tenant", "is_active"]`.
- **Validation:** Enforce unique default template per methodology per tenant when `is_default=True`.

### 4.2 `ProjectCustomField` [PCF-]
- **Purpose:** User-defined data capture, validation rules, and conditional visibility (Bullet 2).
- **Base:** `TenantNumbered` (`NUMBER_PREFIX = "PCF"`).
- **Fields:**
  - `name`: `CharField(max_length=255)` — Administrative field name (e.g., "Client Compliance Tier").
  - `field_key`: `SlugField(max_length=60)` — Programmatic key used in JSON data stores (e.g., "compliance_tier").
  - `label`: `CharField(max_length=200)` — Label rendered on generated forms (e.g., "Compliance Tier (ISO/SOC2)").
  - `target_entity`: `CharField(max_length=20, choices=TARGET_ENTITY_CHOICES, default="project")` — `project`, `task`, `milestone`, `risk`, `team`.
  - `field_type`: `CharField(max_length=20, choices=FIELD_TYPE_CHOICES, default="text")` — `text`, `textarea`, `integer`, `decimal`, `date`, `boolean`, `select`, `multiselect`, `url`, `user_ref`.
  - `form_section`: `CharField(max_length=30, choices=SECTION_CHOICES, default="general")` — `general`, `governance`, `technical`, `financial`, `risk`, `custom`.
  - `description`: `TextField(blank=True)` — Admin notes.
  - `placeholder`: `CharField(max_length=255, blank=True)` — UI input placeholder.
  - `default_value`: `CharField(max_length=255, blank=True)` — Initial pre-fill value.
  - `is_required`: `BooleanField(default=False)` — Required validation flag.
  - `min_value`: `DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)` — Lower bound for integer/decimal.
  - `max_value`: `DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)` — Upper bound for integer/decimal.
  - `regex_pattern`: `CharField(max_length=255, blank=True)` — Validation regex for text/url.
  - `choices_list`: `JSONField(default=list, blank=True)` — Predefined option values for `select` and `multiselect`.
  - `visibility_rule`: `JSONField(default=dict, blank=True)` — Conditional display logic.
  - `display_order`: `PositiveIntegerField(default=0)` — Ordering within the form section.
  - `is_active`: `BooleanField(default=True)` — Active toggle.
- **Constraints:** `unique_together = ("tenant", "target_entity", "field_key")`.
- **Indexes:** `["tenant", "target_entity", "is_active"]`.

### 4.3 `ProjectTeam` [PTE-] & `ProjectTeamMember`
- **Purpose:** Matrix team organization, corporate hierarchy alignment, and membership allocations (Bullet 3).
- **`ProjectTeam` Model:**
  - **Base:** `TenantNumbered` (`NUMBER_PREFIX = "PTE"`).
  - **Fields:**
    - `name`: `CharField(max_length=255)` — Team name (e.g., "Core Banking Transformation Pod", "EMEA Cloud Delivery Team").
    - `code`: `CharField(max_length=50, blank=True)` — Short identifier (e.g., "TEAM-FIN-01").
    - `team_type`: `CharField(max_length=20, choices=TEAM_TYPE_CHOICES, default="cross_functional")` — `dedicated`, `matrix`, `cross_functional`, `agile_pod`, `vendor_external`.
    - `org_unit`: `ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True, related_name="project_teams")` — Link to corporate department / branch / cost center.
    - `project`: `ForeignKey("projects.Project", on_delete=models.SET_NULL, null=True, blank=True, related_name="teams")` — Assigned project (null for shared resource pools).
    - `team_lead`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="led_project_teams")` — Lead/Manager.
    - `description`: `TextField(blank=True)` — Team remit and charter.
    - `location`: `CharField(max_length=100, blank=True)` — Hub/Location.
    - `is_active`: `BooleanField(default=True)` — Active status.
  - **Indexes:** `["tenant", "team_type"]`, `["tenant", "org_unit"]`, `["tenant", "project"]`.
- **`ProjectTeamMember` Model:**
  - **Base:** `TenantOwned` (Unnumbered join row).
  - **Fields:**
    - `team`: `ForeignKey("projects.ProjectTeam", on_delete=models.CASCADE, related_name="members")`
    - `user`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="project_team_memberships")`
    - `role`: `CharField(max_length=30, choices=ROLE_CHOICES, default="developer")`
    - `allocation_percentage`: `PositiveSmallIntegerField(default=100, validators=[MinValueValidator(1), MaxValueValidator(100)])`
    - `is_primary_contact`: `BooleanField(default=False)`
    - `joined_date`: `DateField(null=True, blank=True)`
    - `left_date`: `DateField(null=True, blank=True)`
  - **Constraints:** `unique_together = ("team", "user")`.

### 4.4 `ProjectLocaleSetting` [PLS-]
- **Purpose:** Regional settings, multi-language packs, date/number formats, and working timezone rules (Bullet 4).
- **Base:** `TenantNumbered` (`NUMBER_PREFIX = "PLS"`).
- **Fields:**
  - `name`: `CharField(max_length=255)` — Profile title.
  - `code`: `CharField(max_length=50, blank=True)` — Short identifier.
  - `project`: `ForeignKey("projects.Project", on_delete=models.SET_NULL, null=True, blank=True, related_name="locale_settings")`
  - `language`: `ForeignKey("core.Language", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")`
  - `time_zone`: `ForeignKey("core.TimeZone", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")`
  - `currency`: `ForeignKey("accounting.Currency", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")`
  - `date_format`: `CharField(max_length=40, default="YYYY-MM-DD", choices=DATE_FORMAT_CHOICES)`
  - `time_format`: `CharField(max_length=10, default="24h", choices=[("12h", "12-hour (am/pm)"), ("24h", "24-hour")])`
  - `first_day_of_week`: `PositiveSmallIntegerField(default=1, choices=[(1, "Monday"), (6, "Saturday"), (7, "Sunday")])`
  - `number_format`: `CharField(max_length=40, default="#,##0.00", choices=NUMBER_FORMAT_CHOICES)`
  - `working_hours_per_day`: `DecimalField(max_digits=4, decimal_places=2, default=Decimal("8.00"), validators=[MinValueValidator(Decimal("1.00")), MaxValueValidator(Decimal("24.00"))])`
  - `working_days_pattern`: `JSONField(default=list, blank=True)`
  - `is_default`: `BooleanField(default=False)`
  - `is_active`: `BooleanField(default=True)`
- **Indexes:** `["tenant", "project"]`, `["tenant", "is_default"]`.
- **Validation:** Only one tenant-level default setting (`project=None`, `is_default=True`) per tenant.

---

## 5. Belongs to sibling sub-modules (parked, not scoped here)

- **Project Charter Authoring & Stakeholder Register** → 7.1 Project Initiation & Charter (`Project`, `ProjectRequest`, `ProjectStakeholder`).
- **Detailed WBS Task Scheduling, Dependencies & Baseline Snapshots** → 7.2 Project Planning & Scheduling (`ProjectTask`, `ProjectMilestone`, `ScheduleBaseline`, `TaskDependency`).
- **Individual Bookable Resource Profiles, Capacity Hours & Bookings** → 7.3 Resource Management (`ResourceProfile`, `ResourceAllocation`).
- **Project Budgets, Cost Accounts, Revisions & Expense Logs** → 7.4 Cost & Budget Management (`ProjectBudgetLine`, `CostControlAccount`, `ProjectExpense`).
- **Risk Assessment Registers & Issue Escalations** → 7.5 Risk & Issue Management (`ProjectRisk`, `ProjectIssue`, `IssueEscalation`).
- **Quality Plans & Deliverable Defect Tracking** → 7.6 Quality Management (`QualityPlan`, `DeliverableInspection`, `QualityDefect`).
- **Requirements & Scope Change Requests** → 7.7 Scope & Requirements Management (`Requirement`, `ScopeItem`, `ScopeChangeRequest`).
- **Kanban Task Boards & Checklists** → 7.8 Task & Work Management (`TaskChecklistItem`, `TaskBlock`).
- **Document Repositories, Folder Hierarchies & Revisions** → 7.10 Document & Knowledge Management (`ProjectDocument`, `ProjectFolder`).
- **Timesheets & Activity Codes** → 7.11 Time & Attendance Tracking (`ResourceTimeEntry`, `TimeActivityCode`).
- **Strategic Portfolios & Programs** → 7.12 Portfolio & Program Management (`Portfolio`, `Program`).
- **Agile Sprints, Backlogs & Retrospectives** → 7.13 Agile & Scrum Management (`Sprint`, `ProjectEpic`, `SprintRetrospective`).
- **External Client Portals, Vendor Handoffs & SOWs** → 7.14 Client & External Collaboration (`ClientPortalAccess`, `StatementOfWork`, `VendorHandoff`).
- **Rate Cards, Invoicing & Billing Runs** → 7.15 Financial & Billing Management (`ProjectRateCard`, `ProjectBillingRun`).
- **BI Reports, Widgets & Executive Dashboards** → 7.16 Reporting & Business Intelligence (`ProjectReport`, `ProjectDashboard`, `DashboardWidget`).
- **Workflow Automation Rules & Webhook Deliveries** → 7.17 Workflow & Automation (`ProjectWorkflowRule`, `ProjectWebhookEndpoint`).
- **Third-Party Integrations & Sync Jobs** → 7.18 Integration & API Hub (`ProjectIntegrationConnector`, `ProjectSyncJob`).
- **Platform-wide Tenant Localization Defaults** → 0.15 `core.LocaleProfile` (7.19 provides project-specific configuration profiles).

---

## 6. Deferred (later passes / integrations)

- **Interactive Drag-and-Drop Visual Form Canvas** — Dragging custom fields onto a live GUI layout canvas is deferred to a future frontend enhancement pass; the underlying metadata schema, section layout, and validation rules are fully operational via standard CRUD in this pass.
- **Dynamic In-Browser Expression Evaluator for Formulas** — Runtime mathematical formula calculations across custom fields are deferred; data persistence, numeric bounds, and validation regex are delivered now.
- **Automated Deep-Cloning WBS Project Instantiator** — Full automated creation of 50+ live task/milestone rows from template JSON is deferred to a future service-layer utility; the complete WBS hierarchy and roles catalog are captured in `ProjectTemplate` now.
- **Dynamic Timezone Date Converter Middleware** — Real-time DST arithmetic against user sessions is deferred to Python `zoneinfo` rendering helpers; timezone foreign keys and offset display labels are fully modeled now.

---

## 7. Summary

- **Sub-module:** 7.19 Master Data & Configuration (`apps/projects`)
- **Products Surveyed:** ServiceNow SPM, Microsoft Dynamics 365 Project Operations, Jira Enterprise, Planview AdaptiveWork, Smartsheet Resource Management, Oracle Primavera Cloud / NetSuite OpenAir, Monday.com Enterprise, Asana Enterprise.
- **Recommended 1–4 Model Build Scope:**
  1. `ProjectTemplate` [`PTM-`] — Methodology blueprints (Waterfall/Agile/Hybrid) with pre-built WBS hierarchy JSON, default roles, workflow stages, and budget/duration baselines.
  2. `ProjectCustomField` [`PCF-`] — Multi-entity custom field definitions across projects, tasks, milestones, risks, and teams with 10 data types, validation rules, section layouts, and conditional visibility JSON.
  3. `ProjectTeam` [`PTE-`] + `ProjectTeamMember` — Matrix team structures spanning corporate `core.OrgUnit` departments, team taxonomy, dedicated team leads, locations, and member allocation percentages.
  4. `ProjectLocaleSetting` [`PLS-`] — Project and regional configuration profiles linking to `core.Language`, `core.TimeZone`, and `accounting.Currency`, with work-week patterns, working hours, and date/number formatting rules.
- **File Output:** `.claude/tasks/research-projects-7.19.md`
