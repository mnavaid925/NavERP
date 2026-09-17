# Build contract — Projects 7.12 Portfolio & Program Management (`projects`)

> Frozen 2026-09-17 against the live tree at commit `d7ba8620`.
> This file is the single source of truth for the entity-by-entity build: every name below is
> resolved against the real code, not aspirational. Anything not pinned here is not authorized.

## 0. Scope (frozen by the research pass)

Five NavERP.md bullets → **four entities, four tables, one computed dashboard page**:

| Bullet (verbatim NavERP.md 7.12) | What 7.12 owns | Artifact |
|---|---|---|
| **Portfolio Dashboard & Heat Maps** | Multi-project health indicators, bubble charts, investment balance views | `Portfolio` [PRT-] container + computed `pfm_dashboard` |
| **Program Dependency Mapping** | Cross-project dependencies, shared resources, milestone alignment | `Program` [PGM-] + `ProgramDependency` [PDEP-] cross-project register |
| **Strategic Alignment & Scoring** | OKR linkage, weighted scoring models, prioritization | `PortfolioInvestment` [PIN-] (4 criteria: strategic, financial, risk, capacity) |
| **Capacity & Pipeline Planning** | Resource pool across programs, demand funnel, intake governance | Computed pipeline funnel over 7.1 `ProjectRequest` + 7.3 `ResourceAllocation` |
| **Portfolio Reporting & Governance** | Executive summaries, steering committee packs, investment reviews | Computed executive section on `pfm_dashboard` + decision verbs (`fund`, `reject`, `defer`) |

### Explicit non-goals
- **No health column** on Portfolio/Program/Investment (health is derived from member project statuses).
- **No intra-project task dependency duplication** (7.2 `TaskDependency` owns intra-project task edges; `ProgramDependency` owns cross-project edges).
- **No scoring recompute engine** (`weighted_score` is a derived property; rank is a computed sort lens).
- **No second financial ledger** (`budget_envelope` is planning input; actuals/commitments read from 7.4).

---

## 1. Verified Ground Truth

- `Project` [PRJ-] url name `projects:prj_detail` (`apps/projects/models/ProjectInitiation/Projects.py`).
- `ProjectRequest` [PRQ-] url name `projects:prq_detail` (`apps/projects/models/ProjectInitiation/ProjectRequests.py`).
- `ResourceAllocation` [RAL-] (`apps/projects/models/ResourceManagement/ResourceAllocations.py`).
- `TenantNumbered` (`apps/projects/models/_base.py`).
- `TenantModelForm`, `_reject_foreign` (`apps/projects/forms/_common.py`).
- `crud_list`, `crud_detail`, `crud_create`, `crud_edit`, `crud_delete` (`apps/core/crud.py`).
- `write_audit_log` (`apps/core/utils.py`). Audit action ≤ 10 chars (`create`, `update`, `delete`, `fund`, `reject`, `defer`, `clear`, `reopen`).
- Badge classes: `badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, `badge-slate` (colour-named ONLY).

---

## 2. Models Specification

### 2.1 `Portfolio` [PRT-] — `apps/projects/models/PortfolioProgramManagement/Portfolios.py`
- Base: `TenantNumbered`, `NUMBER_PREFIX = "PRT"`
- Choices:
  - `STATUS_CHOICES = [("draft", "Draft"), ("active", "Active"), ("on_hold", "On Hold"), ("closed", "Closed"), ("archived", "Archived")]`
  - `STRATEGIC_THEME_CHOICES = [("growth", "Growth & Market Expansion"), ("efficiency", "Operational Efficiency"), ("transformation", "Digital Transformation"), ("compliance", "Regulatory & Compliance"), ("innovation", "Innovation & R&D"), ("customer_experience", "Customer Experience")]`
- Fields:
  - `name`: CharField(max_length=255)
  - `code`: CharField(max_length=30, blank=True)
  - `description`: TextField(blank=True)
  - `status`: CharField(max_length=12, choices=STATUS_CHOICES, default="draft")
  - `owner`: ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="owned_portfolios")
  - `strategic_theme`: CharField(max_length=30, choices=STRATEGIC_THEME_CHOICES, default="transformation")
  - `budget_envelope`: DecimalField(max_digits=14, decimal_places=2, default=ZERO)
  - `currency`: ForeignKey("accounting.Currency", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
  - `start_date`: DateField(null=True, blank=True)
  - `end_date`: DateField(null=True, blank=True)
  - `is_active`: BooleanField(default=True)
- Meta:
  - `ordering = ["-created_at"]`
  - `unique_together = (("tenant", "number"),)`
  - `indexes = [models.Index(fields=["tenant", "status"], name="prt_tnt_status_idx"), models.Index(fields=["tenant", "strategic_theme"], name="prt_tnt_theme_idx")]`
- Properties:
  - `total_programs`: count of child programs
  - `total_investments`: count of investments
  - `allocated_budget`: sum of `investments.allocated_budget`
  - `budget_variance`: `budget_envelope - allocated_budget`

### 2.2 `Program` [PGM-] — `apps/projects/models/PortfolioProgramManagement/Programs.py`
- Base: `TenantNumbered`, `NUMBER_PREFIX = "PGM"`
- Choices:
  - `STATUS_CHOICES = [("proposed", "Proposed"), ("planning", "Planning"), ("active", "Active"), ("on_hold", "On Hold"), ("completed", "Completed"), ("cancelled", "Cancelled")]`
- Fields:
  - `portfolio`: ForeignKey("projects.Portfolio", on_delete=models.CASCADE, related_name="programs")
  - `name`: CharField(max_length=255)
  - `code`: CharField(max_length=30, blank=True)
  - `description`: TextField(blank=True)
  - `manager`: ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="managed_programs")
  - `status`: CharField(max_length=12, choices=STATUS_CHOICES, default="proposed")
  - `target_start_date`: DateField(null=True, blank=True)
  - `target_end_date`: DateField(null=True, blank=True)
  - `objectives`: TextField(blank=True)
  - `budget_target`: DecimalField(max_digits=14, decimal_places=2, default=ZERO)
- Meta:
  - `ordering = ["portfolio_id", "-created_at"]`
  - `unique_together = (("tenant", "number"), ("tenant", "portfolio", "name"))`
  - `indexes = [models.Index(fields=["tenant", "portfolio"], name="pgm_tnt_portfolio_idx"), models.Index(fields=["tenant", "status"], name="pgm_tnt_status_idx")]`
- Properties:
  - `total_projects`: count of child investments
  - `allocated_budget`: sum of `investments.allocated_budget`

### 2.3 `PortfolioInvestment` [PIN-] — `apps/projects/models/PortfolioProgramManagement/PortfolioInvestments.py`
- Base: `TenantNumbered`, `NUMBER_PREFIX = "PIN"`
- Choices:
  - `STATUS_CHOICES = [("proposed", "Proposed"), ("under_review", "Under Review"), ("funded", "Funded"), ("deferred", "Deferred"), ("rejected", "Rejected")]`
- Fields:
  - `portfolio`: ForeignKey("projects.Portfolio", on_delete=models.CASCADE, related_name="investments")
  - `project`: ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="portfolio_investments")
  - `program`: ForeignKey("projects.Program", on_delete=models.SET_NULL, null=True, blank=True, related_name="investments")
  - `status`: CharField(max_length=15, choices=STATUS_CHOICES, default="proposed")
  - `strategic_fit`: PositiveSmallIntegerField(default=50, validators=[MinValueValidator(0), MaxValueValidator(100)])
  - `financial_return`: PositiveSmallIntegerField(default=50, validators=[MinValueValidator(0), MaxValueValidator(100)])
  - `delivery_risk`: PositiveSmallIntegerField(default=50, validators=[MinValueValidator(0), MaxValueValidator(100)])
  - `capacity_fit`: PositiveSmallIntegerField(default=50, validators=[MinValueValidator(0), MaxValueValidator(100)])
  - `weight_strategic`: PositiveSmallIntegerField(default=25, validators=[MinValueValidator(0), MaxValueValidator(100)])
  - `weight_financial`: PositiveSmallIntegerField(default=25, validators=[MinValueValidator(0), MaxValueValidator(100)])
  - `weight_risk`: PositiveSmallIntegerField(default=25, validators=[MinValueValidator(0), MaxValueValidator(100)])
  - `weight_capacity`: PositiveSmallIntegerField(default=25, validators=[MinValueValidator(0), MaxValueValidator(100)])
  - `allocated_budget`: DecimalField(max_digits=14, decimal_places=2, default=ZERO)
  - `approved_by`: ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, editable=False, related_name="+")
  - `approved_at`: DateTimeField(null=True, blank=True, editable=False)
  - `decision_notes`: TextField(blank=True)
- Meta:
  - `ordering = ["portfolio_id", "-created_at"]`
  - `unique_together = (("tenant", "number"), ("tenant", "portfolio", "project"))`
  - `indexes = [models.Index(fields=["tenant", "portfolio"], name="pin_tnt_portfolio_idx"), models.Index(fields=["tenant", "status"], name="pin_tnt_status_idx")]`
- Property:
  - `weighted_score`: `Decimal` 0-100 calculated as `(strategic_fit*weight_strategic + financial_return*weight_financial + delivery_risk*weight_risk + capacity_fit*weight_capacity) / total_weight`.

### 2.4 `ProgramDependency` [PDEP-] — `apps/projects/models/PortfolioProgramManagement/ProgramDependencies.py`
- Base: `TenantNumbered`, `NUMBER_PREFIX = "PDEP"`
- Choices:
  - `DEPENDENCY_TYPE_CHOICES = [("finish_to_start", "Finish to Start (FS)"), ("start_to_start", "Start to Start (SS)"), ("shared_resource", "Shared Resource"), ("deliverable_handover", "Deliverable Handover"), ("governance_gate", "Governance Gate")]`
  - `CRITICALITY_CHOICES = [("low", "Low"), ("medium", "Medium"), ("high", "High"), ("critical", "Critical")]`
  - `STATUS_CHOICES = [("open", "Open"), ("mitigated", "Mitigated"), ("cleared", "Cleared"), ("waived", "Waived")]`
- Fields:
  - `source_project`: ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="outgoing_program_dependencies")
  - `target_project`: ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="incoming_program_dependencies")
  - `program`: ForeignKey("projects.Program", on_delete=models.SET_NULL, null=True, blank=True, related_name="dependencies")
  - `dependency_type`: CharField(max_length=25, choices=DEPENDENCY_TYPE_CHOICES, default="finish_to_start")
  - `criticality`: CharField(max_length=10, choices=CRITICALITY_CHOICES, default="medium")
  - `status`: CharField(max_length=12, choices=STATUS_CHOICES, default="open")
  - `lead_lag_days`: IntegerField(default=0)
  - `description`: TextField(blank=True)
  - `owner`: ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
  - `cleared_at`: DateTimeField(null=True, blank=True, editable=False)
- Meta:
  - `ordering = ["-created_at"]`
  - `unique_together = (("tenant", "number"),)`
  - `indexes = [models.Index(fields=["tenant", "source_project"], name="pdep_tnt_source_idx"), models.Index(fields=["tenant", "target_project"], name="pdep_tnt_target_idx"), models.Index(fields=["tenant", "status"], name="pdep_tnt_status_idx")]`
- `clean()`: validate `source_project != target_project` and both belong to `self.tenant`.

---

## 3. URLs & Context Keys

### 3.1 Route Names
- `projects:prt_list` -> `portfolios/`
- `projects:prt_create` -> `portfolios/add/`
- `projects:prt_detail` -> `portfolios/<int:pk>/`
- `projects:prt_edit` -> `portfolios/<int:pk>/edit/`
- `projects:prt_delete` -> `portfolios/<int:pk>/delete/`
- `projects:pgm_list` -> `programs/`
- `projects:pgm_create` -> `programs/add/`
- `projects:pgm_detail` -> `programs/<int:pk>/`
- `projects:pgm_edit` -> `programs/<int:pk>/edit/`
- `projects:pgm_delete` -> `programs/<int:pk>/delete/`
- `projects:pin_list` -> `investments/`
- `projects:pin_create` -> `investments/add/`
- `projects:pin_detail` -> `investments/<int:pk>/`
- `projects:pin_edit` -> `investments/<int:pk>/edit/`
- `projects:pin_delete` -> `investments/<int:pk>/delete/`
- `projects:pin_fund` -> `investments/<int:pk>/fund/`
- `projects:pin_reject` -> `investments/<int:pk>/reject/`
- `projects:pin_defer` -> `investments/<int:pk>/defer/`
- `projects:pdep_list` -> `program-dependencies/`
- `projects:pdep_create` -> `program-dependencies/add/`
- `projects:pdep_detail` -> `program-dependencies/<int:pk>/`
- `projects:pdep_edit` -> `program-dependencies/<int:pk>/edit/`
- `projects:pdep_delete` -> `program-dependencies/<int:pk>/delete/`
- `projects:pdep_clear` -> `program-dependencies/<int:pk>/clear/`
- `projects:pdep_reopen` -> `program-dependencies/<int:pk>/reopen/`
- `projects:pfm_dashboard` -> `portfolio-dashboard/`

### 3.2 View Context Keys
- `prt_list`: `object_list`, `page_obj`, `q`, `status_choices`, `theme_choices`, `total_count`
- `prt_detail`: `obj`, `programs`, `investments`, `allocated_total`, `budget_variance`
- `pgm_list`: `object_list`, `page_obj`, `q`, `status_choices`, `portfolios`, `total_count`
- `pgm_detail`: `obj`, `investments`, `dependencies`, `allocated_total`
- `pin_list`: `object_list`, `page_obj`, `q`, `status_choices`, `portfolios`, `programs`, `total_count`
- `pin_detail`: `obj`, `decision_form`
- `pdep_list`: `object_list`, `page_obj`, `q`, `status_choices`, `criticality_choices`, `type_choices`, `total_count`
- `pdep_detail`: `obj`
- Forms (create/edit): `form`, `obj`, `is_edit`
- `pfm_dashboard`: `portfolios`, `selected_portfolio`, `portfolio_stats`, `quadrant_data`, `health_summary`, `demand_pipeline`, `dependencies_summary`
