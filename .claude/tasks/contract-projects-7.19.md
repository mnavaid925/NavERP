# Build Contract — Projects 7.19 Master Data & Configuration (`projects`)

> Frozen 2026-09-24 against the live tree at BASE commit `3e10760acea9757261c6e5f45ec85e119fda5d09`.
> This contract is the single source of truth for the entity-by-entity build of Sub-module 7.19.
> Every variable name, field name, URL name, context key, and badge class is pinned here.
> Phase 4 reviews `3e10760a...HEAD`.

---

## 0. Scope & capability coverage

Four NavERP.md §7.19 capability bullets (`NavERP.md:1296–1301`) map to **4 owned models + 1 unnumbered child + 1 hub lens page**. 7.19 is the **foundational master data and configuration layer** of the Project Management module:

| NavERP.md bullet (character-for-character) | What 7.19 owns | Primary URL |
|---|---|---|
| **Project Templates & Methodologies** (Waterfall, Agile, hybrid templates with pre-built WBS and workflows) | `ProjectTemplate` [`PTM-`] with pre-built WBS JSON, default roles, workflow stages, and project instantiation | `projects:ptm_list` |
| **Custom Fields & Forms** (User-defined data capture, validation rules, and conditional visibility) | `ProjectCustomField` [`PCF-`] spanning project entities (`project·task·milestone·risk·team`) with 10 data types & visibility rules | `projects:pcf_list` |
| **Organization Hierarchy & Teams** (Departments, business units, locations, and matrix team structures) | `ProjectTeam` [`PTE-`] linked to `core.OrgUnit` + unnumbered child `ProjectTeamMember` with matrix allocation percentages | `projects:pte_list` |
| **Localization & Multi-Language** (Regional settings, language packs, date/number formats, and time zones) | `ProjectLocaleSetting` [`PLS-`] linking to `core.Language`, `core.TimeZone`, and `accounting.Currency` | `projects:pls_list` |
| The configuration hub surface | `configuration_hub` board with KPIs, methodology distribution, team capacity, and quick links | `projects:configuration_hub` |

### Non-goals & invariants
- **Multi-tenancy**: Every model subclasses `TenantNumbered` or `TenantOwned` (`tenant_id = request.tenant.id`). All views filter `Model.objects.filter(tenant=request.tenant)`.
- **Prefixes pinned**:
  - `PTM-`: `ProjectTemplate`
  - `PCF-`: `ProjectCustomField`
  - `PTE-`: `ProjectTeam`
  - `PLS-`: `ProjectLocaleSetting`
  - `ProjectTeamMember`: unnumbered join row.
- **Audit verbs ≤ 10 chars** (`AuditLog.action` is `varchar(10)`): `create`, `update`, `delete`, `toggle`, `instantiate`, `set_default`.
- **Badges colour-named only** (L33): `badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, `badge-slate`.

---

## 1. Verified ground truth

- `Project` [`PRJ-`] (`apps/projects/models/ProjectInitiation/Projects.py`), url `projects:prj_detail`.
- `core.OrgUnit` (`apps/core/models/OrgUnit.py`), url `core:orgunit_list`.
- `core.Language` (`apps/core/models/Localization.py:58`), url `core:language_list`.
- `core.TimeZone` (`apps/core/models/Localization.py:87`), url `core:timezone_list`.
- `accounting.Currency` (`apps/accounting/models/GeneralLedger/Currencies.py:18`), url `accounting:currency_list`.
- `write_audit_log(user, obj, action, changes=None, tenant=None)` (`apps/core/utils.py:6`).
- Migration: `apps/projects/migrations/` ends at `0027_...`; 7.19 claims **`0028_...`**.

---

## 2. Models Specification

### 2.1 `ProjectTemplate` (`apps/projects/models/MasterDataConfiguration/ProjectTemplates.py`)
- Inherits: `TenantNumbered` (`NUMBER_PREFIX = "PTM"`)
- Fields:
  - `name`: `CharField(max_length=255)`
  - `code`: `CharField(max_length=50, blank=True)`
  - `methodology`: `CharField(max_length=20, choices=[("waterfall", "Waterfall"), ("agile", "Agile"), ("hybrid", "Hybrid")], default="hybrid")`
  - `category`: `CharField(max_length=30, choices=[("software", "Software & IT"), ("infrastructure", "Infrastructure"), ("consulting", "Professional Services / Consulting"), ("r_and_d", "R&D / Innovation"), ("marketing", "Marketing / Creative"), ("operational", "Operational / Internal"), ("internal", "Internal Governance")], default="software")`
  - `complexity`: `CharField(max_length=20, choices=[("small", "Small / Quick-Turn"), ("medium", "Medium Standard"), ("large", "Large Multi-Phase"), ("enterprise", "Enterprise Strategic")], default="medium")`
  - `description`: `TextField(blank=True)`
  - `estimated_duration_days`: `PositiveIntegerField(default=30)`
  - `target_budget`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))`
  - `default_roles`: `JSONField(default=list, blank=True)`
  - `wbs_structure`: `JSONField(default=list, blank=True)`
  - `workflow_config`: `JSONField(default=dict, blank=True)`
  - `is_active`: `BooleanField(default=True)`
  - `is_default`: `BooleanField(default=False)`
  - `created_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")`
- Meta: `ordering = ["-created_at", "-id"]`, indexes: `["tenant", "methodology"]`, `["tenant", "is_active"]`.
- Methods: `__str__`, `get_methodology_badge()`, `get_complexity_badge()`.

### 2.2 `ProjectCustomField` (`apps/projects/models/MasterDataConfiguration/ProjectCustomFields.py`)
- Inherits: `TenantNumbered` (`NUMBER_PREFIX = "PCF"`)
- Fields:
  - `name`: `CharField(max_length=255)`
  - `field_key`: `SlugField(max_length=60)`
  - `label`: `CharField(max_length=200)`
  - `target_entity`: `CharField(max_length=20, choices=[("project", "Project"), ("task", "Task"), ("milestone", "Milestone"), ("risk", "Risk"), ("team", "Team")], default="project")`
  - `field_type`: `CharField(max_length=20, choices=[("text", "Text"), ("textarea", "Text Area (Long)"), ("integer", "Integer"), ("decimal", "Decimal / Number"), ("date", "Date"), ("boolean", "Yes / No (Boolean)"), ("select", "Single Select Dropdown"), ("multiselect", "Multi-Select"), ("url", "URL Link"), ("user_ref", "User Reference")], default="text")`
  - `form_section`: `CharField(max_length=30, choices=[("general", "General"), ("governance", "Governance"), ("technical", "Technical"), ("financial", "Financial"), ("risk", "Risk & Compliance"), ("custom", "Custom")], default="general")`
  - `description`: `TextField(blank=True)`
  - `placeholder`: `CharField(max_length=255, blank=True)`
  - `default_value`: `CharField(max_length=255, blank=True)`
  - `is_required`: `BooleanField(default=False)`
  - `min_value`: `DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)`
  - `max_value`: `DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)`
  - `regex_pattern`: `CharField(max_length=255, blank=True)`
  - `choices_list`: `JSONField(default=list, blank=True)`
  - `visibility_rule`: `JSONField(default=dict, blank=True)`
  - `display_order`: `PositiveIntegerField(default=0)`
  - `is_active`: `BooleanField(default=True)`
- Meta: `ordering = ["target_entity", "form_section", "display_order", "id"]`, `unique_together = ("tenant", "target_entity", "field_key")`.
- Methods: `__str__`, `get_target_entity_badge()`, `get_field_type_badge()`.

### 2.3 `ProjectTeam` & `ProjectTeamMember` (`apps/projects/models/MasterDataConfiguration/ProjectTeams.py`)
- `ProjectTeam` inherits: `TenantNumbered` (`NUMBER_PREFIX = "PTE"`)
  - Fields:
    - `name`: `CharField(max_length=255)`
    - `code`: `CharField(max_length=50, blank=True)`
    - `team_type`: `CharField(max_length=20, choices=[("dedicated", "Dedicated Project Team"), ("matrix", "Matrix Shared Team"), ("cross_functional", "Cross-Functional Delivery"), ("agile_pod", "Agile Pod / Scrum Team"), ("vendor_external", "Vendor / Contractor Team")], default="cross_functional")`
    - `org_unit`: `ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True, related_name="project_teams")`
    - `project`: `ForeignKey("projects.Project", on_delete=models.SET_NULL, null=True, blank=True, related_name="teams")`
    - `team_lead`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="led_project_teams")`
    - `description`: `TextField(blank=True)`
    - `location`: `CharField(max_length=100, blank=True)`
    - `is_active`: `BooleanField(default=True)`
  - Meta: `ordering = ["-created_at", "-id"]`, indexes: `["tenant", "team_type"]`, `["tenant", "org_unit"]`.
  - Methods: `__str__`, `get_team_type_badge()`, `member_count()` (derived).
- `ProjectTeamMember` inherits: `TenantOwned`
  - Fields:
    - `team`: `ForeignKey("projects.ProjectTeam", on_delete=models.CASCADE, related_name="members")`
    - `user`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="project_team_memberships")`
    - `role`: `CharField(max_length=30, choices=[("project_manager", "Project Manager"), ("scrum_master", "Scrum Master"), ("tech_lead", "Technical Lead"), ("developer", "Software Engineer / Developer"), ("designer", "UI/UX Designer"), ("qa_engineer", "QA / Test Engineer"), ("business_analyst", "Business Analyst"), ("consultant", "Functional Consultant"), ("stakeholder", "Team Stakeholder")], default="developer")`
    - `allocation_percentage`: `PositiveSmallIntegerField(default=100, validators=[MinValueValidator(1), MaxValueValidator(100)])`
    - `is_primary_contact`: `BooleanField(default=False)`
    - `joined_date`: `DateField(null=True, blank=True)`
    - `left_date`: `DateField(null=True, blank=True)`
  - Meta: `unique_together = ("team", "user")`, `ordering = ["-is_primary_contact", "user__username"]`.

### 2.4 `ProjectLocaleSetting` (`apps/projects/models/MasterDataConfiguration/ProjectLocaleSettings.py`)
- Inherits: `TenantNumbered` (`NUMBER_PREFIX = "PLS"`)
- Fields:
  - `name`: `CharField(max_length=255)`
  - `code`: `CharField(max_length=50, blank=True)`
  - `project`: `ForeignKey("projects.Project", on_delete=models.SET_NULL, null=True, blank=True, related_name="locale_settings")`
  - `language`: `ForeignKey("core.Language", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")`
  - `time_zone`: `ForeignKey("core.TimeZone", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")`
  - `currency`: `ForeignKey("accounting.Currency", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")`
  - `date_format`: `CharField(max_length=40, default="YYYY-MM-DD", choices=[("YYYY-MM-DD", "YYYY-MM-DD (ISO)"), ("DD/MM/YYYY", "DD/MM/YYYY (UK/EU)"), ("MM/DD/YYYY", "MM/DD/YYYY (US)"), ("YYYY/MM/DD", "YYYY/MM/DD (East Asia)")])`
  - `time_format`: `CharField(max_length=10, default="24h", choices=[("12h", "12-hour (am/pm)"), ("24h", "24-hour")])`
  - `first_day_of_week`: `PositiveSmallIntegerField(default=1, choices=[(1, "Monday"), (6, "Saturday"), (7, "Sunday")])`
  - `number_format`: `CharField(max_length=40, default="#,##0.00", choices=[("#,##0.00", "1,234.56"), ("#.##0,00", "1.234,56"), ("# ##0,00", "1 234,56")])`
  - `working_hours_per_day`: `DecimalField(max_digits=4, decimal_places=2, default=Decimal("8.00"), validators=[MinValueValidator(Decimal("1.00")), MaxValueValidator(Decimal("24.00"))])`
  - `working_days_pattern`: `JSONField(default=list, blank=True)`
  - `is_default`: `BooleanField(default=False)`
  - `is_active`: `BooleanField(default=True)`
- Meta: `ordering = ["-is_default", "name"]`, indexes: `["tenant", "project"]`, `["tenant", "is_default"]`.
- Methods: `__str__`, `clean()` (ensures only one default per tenant when `project=None`).

---

## 3. Views & URL Contracts

### 3.1 `ProjectTemplates`
- Routes:
  - `projects:ptm_list` -> `master-data/templates/` (GET)
  - `projects:ptm_create` -> `master-data/templates/add/` (GET, POST)
  - `projects:ptm_detail` -> `master-data/templates/<int:pk>/` (GET)
  - `projects:ptm_edit` -> `master-data/templates/<int:pk>/edit/` (GET, POST)
  - `projects:ptm_delete` -> `master-data/templates/<int:pk>/delete/` (POST)
  - `projects:ptm_instantiate` -> `master-data/templates/<int:pk>/instantiate/` (GET, POST)
- Context Keys:
  - `ptm_list`: `templates`, `page_obj`, `methodology_choices`, `category_choices`, `complexity_choices`, `q`, `methodology`, `category`, `is_active`, `stats`
  - `ptm_detail`: `template`, `wbs_phases`, `tasks_count`, `milestones_count`
  - `ptm_create`/`ptm_edit`: `form`, `template` (on edit), `is_edit`
  - `ptm_instantiate`: `form`, `template`

### 3.2 `ProjectCustomFields`
- Routes:
  - `projects:pcf_list` -> `master-data/custom-fields/` (GET)
  - `projects:pcf_create` -> `master-data/custom-fields/add/` (GET, POST)
  - `projects:pcf_detail` -> `master-data/custom-fields/<int:pk>/` (GET)
  - `projects:pcf_edit` -> `master-data/custom-fields/<int:pk>/edit/` (GET, POST)
  - `projects:pcf_delete` -> `master-data/custom-fields/<int:pk>/delete/` (POST)
  - `projects:pcf_toggle_active` -> `master-data/custom-fields/<int:pk>/toggle/` (POST)
- Context Keys:
  - `pcf_list`: `custom_fields`, `page_obj`, `target_choices`, `field_type_choices`, `section_choices`, `q`, `target_entity`, `field_type`, `is_active`, `stats`
  - `pcf_detail`: `custom_field`
  - `pcf_create`/`pcf_edit`: `form`, `custom_field` (on edit), `is_edit`

### 3.3 `ProjectTeams`
- Routes:
  - `projects:pte_list` -> `master-data/teams/` (GET)
  - `projects:pte_create` -> `master-data/teams/add/` (GET, POST)
  - `projects:pte_detail` -> `master-data/teams/<int:pk>/` (GET)
  - `projects:pte_edit` -> `master-data/teams/<int:pk>/edit/` (GET, POST)
  - `projects:pte_delete` -> `master-data/teams/<int:pk>/delete/` (POST)
  - `projects:pte_add_member` -> `master-data/teams/<int:pk>/members/add/` (POST)
  - `projects:pte_remove_member` -> `master-data/teams/<int:team_pk>/members/<int:pk>/delete/` (POST)
- Context Keys:
  - `pte_list`: `teams`, `page_obj`, `team_type_choices`, `org_units`, `q`, `team_type`, `org_unit_id`, `is_active`, `stats`
  - `pte_detail`: `team`, `members`, `member_form`, `total_allocation`
  - `pte_create`/`pte_edit`: `form`, `team` (on edit), `is_edit`

### 3.4 `ProjectLocaleSettings`
- Routes:
  - `projects:pls_list` -> `master-data/locale-settings/` (GET)
  - `projects:pls_create` -> `master-data/locale-settings/add/` (GET, POST)
  - `projects:pls_detail` -> `master-data/locale-settings/<int:pk>/` (GET)
  - `projects:pls_edit` -> `master-data/locale-settings/<int:pk>/edit/` (GET, POST)
  - `projects:pls_delete` -> `master-data/locale-settings/<int:pk>/delete/` (POST)
  - `projects:pls_set_default` -> `master-data/locale-settings/<int:pk>/set-default/` (POST)
- Context Keys:
  - `pls_list`: `locale_settings`, `page_obj`, `languages`, `time_zones`, `currencies`, `q`, `is_active`, `stats`
  - `pls_detail`: `locale_setting`, `working_days_display`
  - `pls_create`/`pls_edit`: `form`, `locale_setting` (on edit), `is_edit`

### 3.5 `ConfigurationHub`
- Route:
  - `projects:configuration_hub` -> `master-data/hub/` (GET)
- Context Keys:
  - `stats`: `templates_count`, `active_templates`, `custom_fields_count`, `teams_count`, `team_members_count`, `locale_profiles_count`
  - `methodologies`: breakdown list with percentages
  - `target_entities`: breakdown of custom fields
  - `recent_templates`: top 5 active templates
  - `recent_teams`: top 5 active teams with member counts

---

## 4. Templates Specification

Templates reside in `templates/projects/masterdataconfiguration/`:
- `template/list.html`, `detail.html`, `form.html`, `instantiate.html`
- `customfield/list.html`, `detail.html`, `form.html`
- `team/list.html`, `detail.html`, `form.html`
- `localesetting/list.html`, `detail.html`, `form.html`
- `boards/hub.html`

All templates extend `base.html` and use color-named badges (`badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, `badge-slate`) and Lucide icons.

---

## 5. Navigation & Seeder Contracts

### 5.1 `apps/core/navigation.py`
```python
    "7.19": {
        "Project Templates & Methodologies": "projects:ptm_list",
        "Custom Fields & Forms":             "projects:pcf_list",
        "Organization Hierarchy & Teams":    "projects:pte_list",
        "Localization & Multi-Language":     "projects:pls_list",
        # Extra live leaves:
        "Configuration Hub":                 "projects:configuration_hub",
    },
```

### 5.2 Seeder `seed_projects.py`
- Method: `_master_data_configuration(self, tenant, now)`
- Guard: `if ProjectTemplate.objects.filter(tenant=tenant).exists(): return`
- Seeds 3 templates with realistic WBS JSON, 5 custom fields, 3 matrix teams with members, and 2 locale profiles.
- `--flush` cleans up child `ProjectTeamMember` -> `ProjectTeam` -> `ProjectCustomField` -> `ProjectTemplate` -> `ProjectLocaleSetting`.
