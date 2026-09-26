# Contract — NavERP 8.4 Sales Forecasting

- App: `apps/sales` (**existing, live app** — no scaffold, **no `config/settings.py` edit, no `config/urls.py` edit**; `apps.sales` is already installed and the root URLconf already includes `apps/sales/urls/`).
- Sub-module: `8.4 Sales Forecasting` (NavERP.md lines **1327–1332**, five bullets).
- Research: `.claude/tasks/research-sales-8.4.md` · Plan: `.claude/tasks/todo.md` (8.4 block, lines 10375+).
- Test namespace: `salesforecasting`.
- Migration: **`0007`** — leaf confirmed by listing `apps/sales/migrations/`: `0001_initial` … `0005_competitorprofile_opportunitycompetitor_and_more.py`, **`0006_opportunitycompetitor_sales_oc_tenant_profile_idx_and_more.py`**. If Django numbers it differently, take the number it gives and record it here. Agree the number before generating if another session is building in this checkout (L43).
- Read-only reference siblings: `apps/sales/models/{OpportunityPipeline/Pipelines,OpportunityOutcomes/OpportunityOutcomes,OpportunityTeams/OpportunityTeams,CompetitiveIntelligence/CompetitiveIntelligence,ContactAccountManagement/AccountPlans}.py`.

## 0. Ownership boundaries

1. **The opportunity master is CRM's, not Sales'.** `crm.Opportunity` (`apps/crm/models/SalesForceAutomation/Opportunities.py:5`, prefix `OPP`) is the only opportunity table. 8.4 reads and links to it; it never re-declares an opportunity, stage, product, account or contact.
2. **Quota DESIGN is 8.7's.** 8.4 only *reads and snapshots* `crm.SalesQuota` (`apps/crm/models/SalesForceAutomation/SalesQuotas.py:5`, prefix `QTA`, `PERIOD_CHOICES = month/quarter/year`, `target_amount` `Decimal(14,2)`, `owner`, `territory`, `period_year`, `period_number`). 8.4 creates no quota row and no allocation/ramp table.
3. **No order.** `scm.SalesOrder` is SCM's; 8.6 will FK into it. 8.4 never touches an order, an invoice, or a journal entry.
4. **No second currency ledger** (L29). `accounting.Currency` is the currency spine; `accounting.ExchangeRate` is the only FX source. 8.4 never sums unlike currencies and never silently defaults to USD (8.2's settled rule).
5. **The AI prediction is storage + explanation only.** No model is trained, no inference run, no score displayed below the **40-won AND 40-lost** eligibility gate counted from `sales.OpportunityOutcome` (append-only).
6. **A `ForecastScenario` must never mutate a `ForecastSubmission`.** Assert in the smoke sweep.
7. Every model is tenant-scoped via `apps/sales/models/_base.py`; every query filters `tenant=request.tenant`; every FK selection is same-tenant. Rollup visibility never grants access.
8. **The approver right is a role check** (`@tenant_admin_required` → `is_superuser or user.is_tenant_admin`), never a record ACL. 8.2 already ruled team membership is not a security boundary.

## 1. Naming (settled — do not "fix")

| Thing | Name | Note |
|---|---|---|
| Backend package (all four layers) | `SalesForecasting/` | PascalCase of the NavERP.md `### 8.4` title, matching `ContactAccountManagement/` |
| **Template folder** | **`templates/sales/salesforecasting/`** | **Mechanical lowercase, matching `leadmanagement/` (8.1) and `contactaccountmanagement/` (8.3).** Research suggested `forecasting/`; the plan overrode it. 8.2's `templates/sales/opportunity/` is the one deliberate exception. **The builder must not rename this back to `forecasting/`.** |
| URL prefix | `forecast/` | New top-level literal segment under `sales:` |
| Number prefixes | `FCP` / `FCS` / `FAD` / `FSC` | `FCP-00001` etc. — `next_number(type(self), self.tenant, PREFIX)`, width 5, via `TenantNumbered.save()` in `apps/sales/models/_base.py` |
| Reused period vocabulary | `crm.SalesQuota.PERIOD_CHOICES` | **verbatim, no re-spelling, no new table** |
| Reused category vocabulary | `crm.Opportunity.FORECAST_CATEGORY_CHOICES` | **verbatim, no new category table** |

### Forecast-category vocabulary — confirmed reuse, not a new entity

`omitted | pipeline | best_case | commit | closed` **already exist**, twice:

- `crm.Opportunity.FORECAST_CATEGORY_CHOICES` — `apps/crm/models/SalesForceAutomation/Opportunities.py:20-26`; field `forecast_category = CharField(max_length=12, choices=…, default="pipeline")` at line 32.
- `sales.PipelineStage.FORECAST_CATEGORY_CHOICES` — `apps/sales/models/OpportunityPipeline/Pipelines.py:113-119`; field at lines 135-139.

**Import path to pin:** `from apps.crm.models import Opportunity, SalesQuota`, then `Opportunity.FORECAST_CATEGORY_CHOICES` / `SalesQuota.PERIOD_CHOICES` (the `apps/crm/models/__init__.py` re-export already satisfies this — `views/OpportunityPipeline/Pipelines.py:16` does `from apps.crm.models import Opportunity, Territory`). **8.4 declares no `ForecastCategory` model, no form for one, and no new choices tuple** — a divergence in one place becomes a divergence in four models, and a new table would be a second vocabulary (L28/L29).

## 2. New package layout

```
apps/sales/models/SalesForecasting/__init__.py            (new, empty)
apps/sales/models/SalesForecasting/ForecastPeriods.py      → ForecastPeriod
apps/sales/models/SalesForecasting/ForecastSubmissions.py → ForecastSubmission
apps/sales/models/SalesForecasting/ForecastAdjustments.py → ForecastAdjustment
apps/sales/models/SalesForecasting/ForecastScenarios.py   → ForecastScenario
apps/sales/forms/SalesForecasting/{__init__,ForecastPeriods,ForecastSubmissions,ForecastAdjustments,ForecastScenarios}.py
apps/sales/views/SalesForecasting/{__init__,ForecastPeriods,ForecastSubmissions,ForecastAdjustments,ForecastScenarios,ForecastBoards}.py
apps/sales/urls/SalesForecasting/{__init__,ForecastPeriods,ForecastSubmissions,ForecastAdjustments,ForecastScenarios,ForecastBoards}.py
apps/sales/forecast_services.py                            (flat service module, like opportunity_services.py)
```

Absolute imports only (`from apps.sales.models._base import TenantNumbered`), per the backend-package rule. Shared toolkit: models `_base.py`; forms `from apps.sales.forms._common import TenantModelForm, TenantUniqueMixin, TenantActionForm, _reject_foreign, tenant_users`; views `from apps.sales.views._common import *` (gives `sales_object`, `sales_scope`, `safe_parse_date`, `csv_export_response`, `csv_safe`).

Top-level re-exports, URL concatenation, `admin.py`, `seed_sales.py` and `navigation.py` are touched **only at Integrate**, after every file exists.


## 3. Model contract

All four models live in `apps/sales/models/SalesForecasting/`, `app_label = "sales"` (derived from the app config — the deeper path needs **no** new app label and no config change). Every model inherits its `tenant` FK from `apps/sales/models/_base.py`:

- `TenantNumbered` → `tenant` (`related_name="+"`, `db_index=True`), `number` (`max_length=20`, `editable=False`), `created_at` (`auto_now_add=True`), `updated_at` (`auto_now=True`).
- `TenantOwned` → the same without `number`.

**Derived-vs-stored ruling, applied to EVERY number in 8.4** (the single most important rule in this sub-module — a stored total is a drift bug waiting to happen; the accounting spine derives balances for the same reason, L29):

| Ruling | Fields |
|---|---|
| **PROPERTY — never a column** | `ForecastPeriod.label`, `.period_elapsed_pct`, `.is_current`; `ForecastSubmission.total_forecast_amount`, `.variance_amount`, `.attainment_pct`, `.pace_pct`; `ForecastAdjustment.net_delta`; `ForecastScenario.effective_pipeline_amount`, `.effective_best_case_amount`, `.effective_commit_amount` |
| **STORED SNAPSHOT — written by a service, excluded from every form** | `ForecastSubmission.weighted_amount` (from `OpportunityPipelinePlacement.effective_probability`), `ForecastSubmission.quota_amount` (from `SalesQuota.target_amount`), `ForecastSubmission.actual_amount` (from `OpportunityOutcome result="won"`), `ForecastScenario.projected_commit_amount`, `ForecastScenario.projected_total_amount` |
| **USER-ENTERED COLUMN** | the five `ForecastSubmission` category amounts, the three `ForecastScenario.*_delta_pct`, `ForecastPeriod.fx_rate_source_date` |

**Correction to the plan, pinned here so the builder does not guess:** the plan lists `weighted_amount` among the stored amounts *and* forbids storing derived values. It is a **snapshot, not a form field** — it records what the pipeline weighed at submit time and is refreshed only by the submit/save service, so it is **excluded from `ForecastSubmissionForm.Meta.fields`**, exactly like the `ai_*` block. `total_forecast_amount` (`commit + best_case + pipeline`) remains a pure property; do not add a `total_forecast_amount` column even though the name reads like a field.

### 3.1 `ForecastPeriod` — `FCP-` — `models/SalesForecasting/ForecastPeriods.py`

`class ForecastPeriod(TenantNumbered)`, `NUMBER_PREFIX = "FCP"`. Driver: category rollups need a period to roll *into*; the three Dynamics rollup templates; 8.2's explicit deferral of reporting-currency roll-ups.

```python
ROLLUP_DIMENSION_CHOICES = [
    ("user", "Sales Representative"),
    ("org_unit", "Organizational Unit"),
    ("territory", "Territory"),
]
```

| Field | Definition | Justification |
|---|---|---|
| `name` | `CharField(max_length=160)` | the display label the user names; the derived `label` is separate |
| `period_type` | `CharField(max_length=10, choices=SalesQuota.PERIOD_CHOICES, default="quarter")` | reuses `crm.SalesQuota.PERIOD_CHOICES` **verbatim** (month/quarter/year) |
| `period_year` | `PositiveSmallIntegerField(default=timezone.localdate().year, validators=[MinValueValidator(1970), MaxValueValidator(9999)])` | `crm.SalesQuota.period_year` precedent (line 20) |
| `period_number` | `PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(12)])` | month 1-12 / quarter 1-4 / year 1; range tightened per type in `clean()` |
| `start_date` | `DateField(editable=False)` | **computed** in `clean()`/`save()` from type+year+number; `editable=False` auto-excludes it from every ModelForm (L22) |
| `end_date` | `DateField(editable=False)` | **computed**; inclusive last day of the period |
| `rollup_dimension` | `CharField(max_length=12, choices=ROLLUP_DIMENSION_CHOICES, default="user")` | the three Dynamics templates; product hierarchy is out of scope for 8.4 |
| `reporting_currency` | `FK("accounting.Currency", SET_NULL, null=True, blank=True, related_name="sales_forecast_periods")` | `accounting.Currency` is **global — no tenant FK** (`Currencies.py:7-14`), so `clean()` must NOT tenant-check this one |
| `fx_rate_source_date` | `DateField(null=True, blank=True)` | reference date of the rate actually applied; the rate is **read** from `accounting.ExchangeRate`, never copied into a sales table |
| `is_active` | `BooleanField(default=True)` | a closed period leaves the picker |
| `is_locked` | `BooleanField(default=False)` | locks its submissions; enforced in the edit/submit actions, not just visually |

`Meta`: `ordering = ["-period_year", "period_number", "name"]`; `constraints = [UniqueConstraint(["tenant","number"], name="sales_fcp_tenant_number_uniq"), UniqueConstraint(["tenant","period_type","period_year","period_number"], name="sales_fcp_tpt_ypn_uniq"), CheckConstraint(Q(period_number__gte=1) & Q(period_number__lte=12), name="sales_fcp_period_number_valid")]`; `indexes = [Index(["tenant","is_active"], name="sales_fcp_tenant_active_idx"), Index(["tenant","period_type","period_year"], name="sales_fcp_tnt_type_year_idx")]`. `verbose_name_plural = "forecast periods"`.

`clean()`: (a) `period_number` in range for the type — month 1-12, quarter 1-4, year exactly 1; (b) compute `start_date`/`end_date`; (c) `end_date >= start_date`. `delete()` raises `ValidationError` while any `ForecastSubmission` references it (mirrors `WinLossReason.delete()`, `OpportunityOutcomes.py:57-60`).

`@property label` → `f"{self.get_period_type_display()} {self.period_year}"` + (`f" · P{self.period_number}"` when `period_type != "year"`). `@property is_current` → `timezone.localdate()` between `start_date` and `end_date`. `@property period_elapsed_pct` → `Decimal` 0-100 elapsed fraction (0 before start, 100 after end). `__str__` → `f"{self.number} · {self.label}"` (the `OpportunityOutcome` / `AccountPlan` shape).


### 3.2 `ForecastSubmission` — `FCS-` — `models/SalesForecasting/ForecastSubmissions.py`

`class ForecastSubmission(TenantNumbered)`, `NUMBER_PREFIX = "FCS"`. Driver: the per-rep forecast call; bullets 1 (categories & commitments) and 3 (attainment).

```python
STATUS_CHOICES = [
    ("draft", "Draft"),
    ("submitted", "Submitted"),
    ("approved", "Approved"),
    ("rejected", "Rejected"),
    ("locked", "Locked"),
]
```

FKs — string reference form; every target **re-grepped in this run** across `apps/*/models/` packages (not flat `models.py`):

| Field | Target | on_delete | related_name | nullable |
|---|---|---|---|---|
| `period` | `"sales.ForecastPeriod"` | **PROTECT** | `submissions` | no |
| `owner` | `settings.AUTH_USER_MODEL` | SET_NULL | `sales_forecast_submissions` | yes |
| `org_unit` | `"core.OrgUnit"` | SET_NULL | `sales_forecast_submissions` | yes |
| `territory` | `"crm.Territory"` | SET_NULL | `sales_forecast_submissions` | yes |
| `pipeline` | `"sales.Pipeline"` | SET_NULL | `sales_forecast_submissions` | yes |
| `quota_ref` | `"crm.SalesQuota"` | SET_NULL | `sales_forecast_submissions` | yes |
| `submitted_by` | `settings.AUTH_USER_MODEL` | SET_NULL | `"+"` | yes, `editable=False` |
| `reviewed_by` | `settings.AUTH_USER_MODEL` | SET_NULL | `"+"` | yes, `editable=False` |

`related_name="+"` on the three **actor** FKs is deliberate: the `TenantEventOwned` base convention, and it prevents four `User.forecastsubmission_set`-style accessors colliding with the existing `crm_opportunities` / `crm_sales_quotas` / `crm_territories` / `crm_tasks` reverse names.

| Field | Definition | Kind |
|---|---|---|
| `status` | `CharField(max_length=12, choices=STATUS_CHOICES, default="draft")` | workflow-controlled, excluded from forms |
| `omitted_amount` | `DecimalField(max_digits=14, decimal_places=2, default=0, validators=[MinValueValidator(Decimal("0"))])` | user-entered |
| `pipeline_amount` | same | user-entered |
| `best_case_amount` | same | user-entered |
| `commit_amount` | same | user-entered |
| `closed_amount` | same | user-entered |
| `weighted_amount` | same | **service snapshot** — from `OpportunityPipelinePlacement.effective_probability` |
| `quota_amount` | same | **service snapshot** — from `quota_ref.target_amount` |
| `actual_amount` | same | **service snapshot** — from `sales.OpportunityOutcome` `result="won"`; **never hand-picked, and no second close-date field** |
| `submitted_at` | `DateTimeField(null=True, blank=True, editable=False)` | system (L22) |
| `reviewed_at` | `DateTimeField(null=True, blank=True, editable=False)` | system (L22) |
| `review_note` | `TextField(blank=True)` | user, on reject |
| `ai_predicted_pipeline` / `ai_predicted_best_case` / `ai_predicted_commit` | `DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)` | AI schema, nullable, system-written |
| `ai_confidence_pct` | `PositiveSmallIntegerField(null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(100)])` | AI schema |
| `ai_model_name` | `CharField(max_length=120, blank=True)` | AI provenance |
| `ai_model_version` | `CharField(max_length=60, blank=True)` | AI provenance |
| `ai_generated_at` | `DateTimeField(null=True, blank=True)` | AI provenance |
| `ai_explanation` | `JSONField(default=dict, blank=True)` | named factors + weights; **rendered wherever a prediction is shown** |
| `notes` | `TextField(blank=True)` | user |

`Meta`: `ordering = ["-created_at", "-id"]`; `constraints = [UniqueConstraint(["tenant","number"], name="sales_fcs_tenant_number_uniq"), CheckConstraint(Q(omitted_amount__gte=0) & Q(pipeline_amount__gte=0) & Q(best_case_amount__gte=0) & Q(commit_amount__gte=0) & Q(closed_amount__gte=0) & Q(weighted_amount__gte=0) & Q(quota_amount__gte=0) & Q(actual_amount__gte=0), name="sales_fcs_amounts_nonneg")]`; `indexes = [Index(["tenant","period","status"], name="sales_fcs_tnt_p_status_idx"), Index(["tenant","owner"], name="sales_fcs_tnt_owner_idx"), Index(["tenant","period","org_unit"], name="sales_fcs_tnt_p_org_idx")]`. `verbose_name_plural = "forecast submissions"`.

**Uniqueness — a DB `UniqueConstraint(["tenant","period","owner"])` is UNSAFE and is forbidden here:** `owner` is nullable, and NULLs do not collide in a SQL unique index, so it would silently permit unlimited duplicate drafts. Enforce `(tenant, period, owner)` in `clean()` (the plan is explicit). `quota_ref` also carries `crm.SalesQuota`'s own composite unique, so a quota is snapshotted **by value** into `quota_amount` and editing the quota never rewrites history.

`clean()`: (a) `_relation_belongs_to_tenant` for `period`, `owner`, `org_unit`, `territory`, `pipeline`, `quota_ref`, `submitted_by`, `reviewed_by` (the exact helper from `OpportunityTeams.py:56-65`); (b) one submission per `(tenant, period, owner)`; (c) all eight amounts `>= 0`; (d) when `period.is_locked`, `status` may not leave `locked`; (e) `status in {"approved","rejected"}` requires `reviewed_by` + `reviewed_at`.

Properties: `total_forecast_amount` = `commit_amount + best_case_amount + pipeline_amount` (Decimal-safe: `Decimal(self.commit_amount or 0) + …`, the `Opportunity.split_amount` / `Opportunity.weighted_amount` shape); `variance_amount` = `total_forecast_amount - actual_amount`; `attainment_pct` = `actual_amount / quota_amount * 100`, or **`None` when `quota_amount <= 0` — never divide by zero; the template renders "—", not `Infinity`/`NaN`**; `pace_pct` = `self.period.period_elapsed_pct` or `None`. `__str__` → `f"{self.number} · {self.owner or '—'} · {self.period}"`.


### 3.3 `ForecastAdjustment` — `FAD-` — `models/SalesForecasting/ForecastAdjustments.py`

`class ForecastAdjustment(TenantNumbered)`, `NUMBER_PREFIX = "FAD"`. Driver: bullet 1 "**with manager override**" and bullet 4's sandbagging detection. This is an audit trail, not an editable document.

```python
ADJUSTMENT_KIND_CHOICES = [
    ("direct", "Direct"),
    ("indirect", "Indirect"),
    ("revert", "Revert"),
]
TARGET_FIELD_CHOICES = [
    ("category", "Forecast Category"),
    ("amount", "Amount"),
]
REASON_CODE_CHOICES = [
    ("new_deal", "New Deal Added"),
    ("deal_advanced", "Deal Advanced A Stage"),
    ("deal_slipped", "Deal Slipped"),
    ("deal_lost", "Deal Lost"),
    ("deal_won", "Deal Won"),
    ("amount_revised", "Amount Revised"),
    ("timing_revised", "Timing Revised"),
    ("territory_reassigned", "Territory Reassigned"),
    ("manager_judgement", "Manager Judgement"),
    ("correction", "Data Correction"),
]
```

| Field | Definition | Kind |
|---|---|---|
| `submission` | `FK("sales.ForecastSubmission", PROTECT, related_name="adjustments")` | **PROTECT** — an audit row is never cascaded away |
| `opportunity` | `FK("crm.Opportunity", SET_NULL, null=True, blank=True, related_name="sales_forecast_adjustments")` | deal-level override; `SET_NULL` so a closed-lost deal keeps its history |
| `placement` | `FK("sales.OpportunityPipelinePlacement", SET_NULL, null=True, blank=True, related_name="sales_forecast_adjustments")` | the same deal's pipeline position |
| `created_by` | `FK(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True, editable=False, related_name="+")` | actor; `related_name="+"` per the actor-FK convention |
| `adjustment_kind` | `CharField(max_length=12, choices=ADJUSTMENT_KIND_CHOICES, default="direct")` | Microsoft's taxonomy verbatim; `indirect` rows are system-written when a manager total propagates down |
| `target_field` | `CharField(max_length=12, choices=TARGET_FIELD_CHOICES, default="category")` | |
| `original_value` | `DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)` | **system snapshot**, excluded from the form |
| `adjusted_value` | `DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)` | user-entered (`amount` rows) |
| `original_category` | `CharField(max_length=12, choices=Opportunity.FORECAST_CATEGORY_CHOICES, null=True, blank=True)` | **system snapshot**, excluded from the form |
| `adjusted_category` | `CharField(max_length=12, choices=Opportunity.FORECAST_CATEGORY_CHOICES, null=True, blank=True)` | user-entered (`category` rows) |
| `reason_code` | `CharField(max_length=32, choices=REASON_CODE_CHOICES)` | **REQUIRED, no default** — an override with no reason is exactly the sandbagging signal bullet 5 hunts |
| `note` | `TextField(blank=True)` | free-text justification |
| `is_reverted` | `BooleanField(default=False)` | |
| `reverted_at` | `DateTimeField(null=True, blank=True, editable=False)` | system (L22) |
| `revert_reason` | `CharField(max_length=255, blank=True)` | **REQUIRED on revert** — Dynamics' mandatory-reason *Reset* |

**The calculated/system value is NOT stored here.** The post-override figure is recomputed from `opportunity` / `placement` / the submission, which is exactly what makes "Reset" always possible and needs no extra column. Do **not** add `adjusted_total` or `calculated_value`.

`Meta`: `ordering = ["-created_at", "-id"]`; `constraints = [UniqueConstraint(["tenant","number"], name="sales_fad_tenant_number_uniq"), CheckConstraint(Q(is_reverted=False) | Q(is_reverted=True, reverted_at__isnull=False), name="sales_fad_reverted_stamped")]`; `indexes = [Index(["tenant","submission"], name="sales_fad_tnt_submission_idx"), Index(["tenant","reason_code"], name="sales_fad_tnt_reason_idx"), Index(["tenant","adjustment_kind"], name="sales_fad_tnt_kind_idx"), Index(["tenant","opportunity"], name="sales_fad_tnt_opp_idx")]`. `verbose_name_plural = "forecast adjustments"`.

`clean()`: (a) `reason_code` non-blank and a member of `REASON_CODE_CHOICES`; (b) `is_reverted is True` requires `reverted_at` **and** a non-blank `revert_reason`; (c) `target_field == "category"` → the category pair set and the value pair null; `target_field == "amount"` → the value pair set and the category pair null; (d) same-tenant check for `submission`, `opportunity`, `placement`, `created_by`; (e) when `opportunity` and `placement` are both set, `placement.opportunity_id == opportunity_id`; (f) refuse an adjustment whose `submission.period.is_locked` is `True`.

`@property net_delta` → `Decimal(self.adjusted_value or 0) - Decimal(self.original_value or 0)` for `amount` rows, else `None`. `__str__` → `f"{self.number} · {self.get_adjustment_kind_display()} · {self.reason_code}"`.


### 3.4 `ForecastScenario` — `FSC-` — `models/SalesForecasting/ForecastScenarios.py`

`class ForecastScenario(TenantNumbered)`, `NUMBER_PREFIX = "FSC"`. Driver: bullet 4's "**scenario modeling**". A what-if that never touches the real forecast.

```python
SCENARIO_TYPE_CHOICES = [
    ("upside", "Upside"),
    ("base", "Base"),
    ("downside", "Downside"),
    ("custom", "Custom"),
]
```

| Field | Definition | Kind |
|---|---|---|
| `period` | `FK("sales.ForecastPeriod", PROTECT, related_name="scenarios")` | **PROTECT** |
| `owner` | `FK(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True, related_name="sales_forecast_scenarios")` | a scenario is often the manager's own what-if |
| `name` | `CharField(max_length=160)` | |
| `scenario_type` | `CharField(max_length=12, choices=SCENARIO_TYPE_CHOICES, default="custom")` | |
| `probability_pct` | `PositiveSmallIntegerField(default=50, validators=[MinValueValidator(0), MaxValueValidator(100)])` | weight in the blended number (`PipelineStage.probability` + `sales_pstage_probability_valid` precedent) |
| `is_baseline` | `BooleanField(default=False)` | the "current plan" row |
| `is_selected` | `BooleanField(default=False)` | the scenario the attainment board reads |
| `pipeline_delta_pct` | `DecimalField(max_digits=6, decimal_places=2, default=0, validators=[MinValueValidator(Decimal("-100.00")), MaxValueValidator(Decimal("1000.00"))])` | **deltas, not absolutes**, so the scenario stays honest as the pipeline moves |
| `best_case_delta_pct` | same | |
| `commit_delta_pct` | same | |
| `projected_commit_amount` | `DecimalField(max_digits=14, decimal_places=2, default=0, validators=[MinValueValidator(Decimal("0"))], editable=False)` | **snapshot of what the scenario computed**, labelled as such |
| `projected_total_amount` | same, `editable=False` | snapshot |
| `assumption_notes` | `TextField(blank=True)` | |

`Meta`: `ordering = ["-is_baseline", "name", "-created_at"]`; `constraints = [UniqueConstraint(["tenant","number"], name="sales_fsc_tenant_number_uniq"), UniqueConstraint(["tenant","period","name"], name="sales_fsc_tnt_period_name_uniq"), CheckConstraint(Q(probability_pct__gte=0) & Q(probability_pct__lte=100), name="sales_fsc_probability_valid"), CheckConstraint(Q(is_baseline=False) | Q(is_baseline=True, is_selected=True), name="sales_fsc_baseline_selected")]`; `indexes = [Index(["tenant","period"], name="sales_fsc_tnt_period_idx"), Index(["tenant","is_selected"], name="sales_fsc_tnt_selected_idx")]`. `verbose_name_plural = "forecast scenarios"`.

**Design ruling pinned:** the `sales_fsc_baseline_selected` CheckConstraint means **only the baseline may be `is_selected`** — "selected" *is* "this is the current plan", so there is exactly one selected scenario per tenant and the attainment board never has to break a tie.

`clean()`: (a) same-tenant for `period` and `owner`; (b) a locked period refuses new or changed scenarios; (c) `probability_pct` in 0-100.

Properties: `effective_pipeline_amount` / `effective_best_case_amount` / `effective_commit_amount` → the period's selected or baseline submission amount × `(1 + delta_pct/100)`, or `None` when no submission exists. `__str__` → `f"{self.number} · {self.name} · {self.get_scenario_type_display()}"`.

**Scenario isolation (assert in smoke):** applying a scenario writes only `projected_commit_amount`, `projected_total_amount` and the two booleans on `ForecastScenario` rows. No `ForecastSubmission` field is touched, in code or in SQL.


## 4. Form contract

All form classes inherit `TenantModelForm` (from `apps.sales.forms._common`, itself re-exporting `apps.core.forms._common.TenantModelForm`) and are constructed as `FormClass(request.POST or None, tenant=request.tenant, …)` — `tenant=` is popped by `crud_*` and passed explicitly on hand-rolled views.

**The exclusion rule, stated once (L20 / L22):** the convention in this app is an explicit `Meta.fields` allow-list, so *anything not listed is excluded*. The lists below are therefore the complete field set. Never use `fields = "__all__"`, and never add a `Meta.exclude` here.

| Always excluded, and why | Fields |
|---|---|
| Tenant + auto-number | `tenant`, `number` (both `editable=False`; `TenantNumbered.save()` mints the number) |
| System timestamps (L22) | `created_at`, `updated_at`, `start_date`, `end_date` (`auto_now*` or `editable=False`) |
| Workflow-controlled | `ForecastSubmission.status`, `ForecastScenario.is_selected` (set by the select action) |
| Actor / audit | `submitted_by`, `reviewed_by`, `created_by` (all `editable=False`) |
| Derived (properties) | `total_forecast_amount`, `variance_amount`, `attainment_pct`, `pace_pct`, `label`, `period_elapsed_pct`, `is_current`, `net_delta`, `effective_*` |
| Service snapshots | `weighted_amount`, `quota_amount`, `actual_amount`, `projected_commit_amount`, `projected_total_amount` |
| AI system-written | `ai_predicted_pipeline`, `ai_predicted_best_case`, `ai_predicted_commit`, `ai_confidence_pct`, `ai_model_name`, `ai_model_version`, `ai_generated_at`, `ai_explanation` |
| System snapshot / audit-only | `ForecastAdjustment.original_value`, `original_category`, `reverted_at`, `is_reverted` |

### 4.1 `ForecastPeriodForm(TenantUniqueMixin, TenantModelForm)`

Needed for the composite `sales_fcp_tpt_ypn_uniq` — the same `TenantUniqueMixin` + `validate_unique(exclude={"tenant"})` pair `PipelineForm` and `WinLossReasonForm` use.

```python
class Meta:
    model = ForecastPeriod
    fields = ["name", "period_type", "period_year", "period_number",
              "rollup_dimension", "reporting_currency", "fx_rate_source_date",
              "is_active", "is_locked"]
```

- `__init__(…, tenant=None, user=None)`: `reporting_currency.queryset = Currency.objects.filter(is_active=True).order_by("code")[:500]`. **`Currency` is global (no `tenant` field), so `TenantModelForm`'s automatic FK tenant-scoping does not apply here — do not assume it, and do not try to filter it by tenant.** When `tenant is None` use `Currency.objects.none()`. A non-tenant-admin sees `is_locked` **disabled** and forced `False` (the `AccountPlanForm` non-admin `owner` pattern).
- **disabled** when `self.instance.pk and self.instance.is_locked`: `["name","period_type","period_year","period_number","rollup_dimension"]` — a locked period's shape is frozen; only `is_active`/`fx_rate_source_date` may move.
- `clean()`: `period_number` in range for the chosen `period_type` (month 1-12, quarter 1-4, year 1); `end_date >= start_date`; `self.add_error(None, "A tenant workspace is required.")` when `tenant is None`.

### 4.2 `ForecastSubmissionForm(TenantModelForm)`

```python
class Meta:
    model = ForecastSubmission
    fields = ["period", "owner", "org_unit", "territory", "pipeline", "quota_ref",
              "omitted_amount", "pipeline_amount", "best_case_amount",
              "commit_amount", "closed_amount", "review_note", "notes"]
    widgets = {"review_note": forms.Textarea(attrs={"rows": 3}),
               "notes": forms.Textarea(attrs={"rows": 3})}
```

- `__init__(…, tenant=None, user=None)`: every FK queryset is `Model.objects.none()` when `tenant is None`, else tenant-filtered and **bounded to `[:500]`** (the `AccountPlanForm` bounded-list pattern — an unbounded user/territory/org-unit list is a page-weight bug).
- Non-admin: `owner` narrowed to `User.objects.filter(pk=user.pk, tenant=tenant, is_active=True)`, `disabled=True`, `initial = user.pk`.
- **when `self.instance.pk and (self.instance.period.is_locked or self.instance.status in {"approved","locked"})` every field is disabled** (the `PipelineStageForm.locked_fields` pattern), with `self.locked_fields` recorded so `clean()` re-checks a tampered POST.
- `clean()`: `_reject_foreign(self, cleaned, ["period","owner","org_unit","territory","pipeline","quota_ref"])`; the five category amounts `>= 0`; a locked period or a non-draft submission refuses any change; one submission per `(tenant, period, owner)`.
- The five amount widgets get `forms.NumberInput(attrs={"step": "0.01", "min": "0"})`.


### 4.3 `ForecastAdjustmentForm(TenantModelForm)`

```python
class Meta:
    model = ForecastAdjustment
    fields = ["submission", "opportunity", "placement", "adjustment_kind",
              "target_field", "adjusted_value", "adjusted_category",
              "reason_code", "note"]
    widgets = {"note": forms.Textarea(attrs={"rows": 3})}
```

- `adjustment_kind` is `disabled=True`, pinned to `"direct"` on create — an `indirect` row is system-written and a `revert` row is written by the revert action. A hand-typed kind is exactly the audit-trail forgery the plan guards against.
- `__init__`: `adjusted_value` shown only when `target_field == "amount"`, `adjusted_category` only when `target_field == "category"` — **and both are re-validated in `clean()` so hiding a field is not the only guard.**
- `clean()`: **`reason_code` is required** — `self.add_error("reason_code", "An adjustment requires a reason code.")` when blank; `target_field` / `adjusted_value` / `adjusted_category` coherence; `placement.opportunity_id == opportunity_id`; `_reject_foreign` for `submission`, `opportunity`, `placement`; a locked period refuses.

### 4.4 `ForecastScenarioForm(TenantModelForm)`

```python
class Meta:
    model = ForecastScenario
    fields = ["period", "owner", "name", "scenario_type", "probability_pct",
              "is_baseline", "pipeline_delta_pct", "best_case_delta_pct",
              "commit_delta_pct", "assumption_notes"]
    widgets = {"assumption_notes": forms.Textarea(attrs={"rows": 4})}
```

- `__init__`: `is_baseline` `disabled=True` on edit (only the baseline may be selected — the CheckConstraint).
- `clean()`: `probability_pct` 0-100; every `*_delta_pct >= -100`; `(tenant, period, name)` unique via `TenantUniqueMixin`; a locked period refuses; **`is_baseline=True` implies `is_selected=True`** (surfaces the constraint as a form error rather than an `IntegrityError`).

### 4.5 Action forms (plain `TenantActionForm`, per `OpportunityTransitionForm`)

| Class | Fields | Used by |
|---|---|---|
| `ForecastReviewForm` | `note` (`CharField(required=False, max_length=4000, widget=Textarea)`) | `approve` / `reject` — `note` **required when rejecting** |
| `ForecastRevertForm` | `revert_reason` (`CharField(max_length=255)` — **required**; Dynamics' mandatory-reason Reset) | `revert` |
| `ForecastScenarioApplyForm` | `period` (`ModelChoiceField`), `target` (`ChoiceField` = `weighted` / `commit` / `total`), `variance_threshold_pct` (`DecimalField`, default 20) | `forecast_scenario_apply` |

All three take `tenant=` in `__init__` and start from `Model.objects.none()` when `tenant is None`, exactly as `OpportunityTransitionForm` does.


## 5. URL contract

`app_name = "sales"` is already set in `apps/sales/urls/__init__.py`; every new name is referenced as `sales:<name>`. Django resolves **first-match-wins, so order is behaviour.**

**Greedy-route check performed (read-only grep): `apps/sales/urls/` contains NO `<str:…>` route at all.** Every existing sales route is literal-prefixed (`opportunity/…`, `accounts/…`, `account-plans/…`, `account-stakeholders/…`, `lead-…`). `forecast/` is therefore a brand-new top-level literal segment that **cannot** be shadowed by, and cannot shadow, anything existing. The literal-before-`<int:pk>` rule still applies *inside each new module*.

### 5.1 `urls/SalesForecasting/ForecastPeriods.py`

| Path | `name=` | View | Method / gate |
|---|---|---|---|
| `forecast/periods/` | `forecast_period_list` | `forecast_period_list` | `@login_required` |
| `forecast/periods/add/` | `forecast_period_create` | `forecast_period_create` | `@tenant_admin_required` |
| `forecast/periods/export/` | `forecast_period_export` | `forecast_period_export` | `@login_required` |
| `forecast/periods/<int:pk>/lock/` | `forecast_period_lock` | `forecast_period_lock` | `@require_POST` + `@tenant_admin_required` |
| `forecast/periods/<int:pk>/unlock/` | `forecast_period_unlock` | `forecast_period_unlock` | `@require_POST` + `@tenant_admin_required` |
| `forecast/periods/<int:pk>/edit/` | `forecast_period_edit` | `forecast_period_edit` | `@tenant_admin_required` |
| `forecast/periods/<int:pk>/delete/` | `forecast_period_delete` | `forecast_period_delete` | `@require_POST` + `@tenant_admin_required` |
| `forecast/periods/<int:pk>/` | `forecast_period_detail` | `forecast_period_detail` | `@login_required` |

### 5.2 `urls/SalesForecasting/ForecastSubmissions.py`

| Path | `name=` | View | Method / gate |
|---|---|---|---|
| `forecast/submissions/` | `forecast_submission_list` | `forecast_submission_list` | `@login_required` |
| `forecast/submissions/add/` | `forecast_submission_create` | `forecast_submission_create` | `@login_required` |
| `forecast/submissions/export/` | `forecast_submission_export` | `forecast_submission_export` | `@login_required` |
| `forecast/submissions/<int:pk>/submit/` | `forecast_submission_submit` | `forecast_submission_submit` | `@require_POST` + `@login_required` |
| `forecast/submissions/<int:pk>/approve/` | `forecast_submission_approve` | `forecast_submission_approve` | `@require_POST` + `@tenant_admin_required` |
| `forecast/submissions/<int:pk>/reject/` | `forecast_submission_reject` | `forecast_submission_reject` | `@require_POST` + `@tenant_admin_required` |
| `forecast/submissions/<int:pk>/edit/` | `forecast_submission_edit` | `forecast_submission_edit` | `@login_required` |
| `forecast/submissions/<int:pk>/delete/` | `forecast_submission_delete` | `forecast_submission_delete` | `@require_POST` + `@tenant_admin_required` |
| `forecast/submissions/<int:pk>/` | `forecast_submission_detail` | `forecast_submission_detail` | `@login_required` |

`create`/`edit`/`submit` are `@login_required` (a rep submits their own call) while `approve`/`reject`/`delete` are `@tenant_admin_required` (bullet 1's manager override). `submit` additionally re-checks `obj.owner_id == request.user.pk or request.user.is_tenant_admin`.

### 5.3 `urls/SalesForecasting/ForecastAdjustments.py`

| Path | `name=` | View | Method / gate |
|---|---|---|---|
| `forecast/adjustments/` | `forecast_adjustment_list` | `forecast_adjustment_list` | `@login_required` |
| `forecast/adjustments/add/` | `forecast_adjustment_create` | `forecast_adjustment_create` | `@tenant_admin_required` |
| `forecast/adjustments/export/` | `forecast_adjustment_export` | `forecast_adjustment_export` | `@login_required` |
| `forecast/adjustments/<int:pk>/revert/` | `forecast_adjustment_revert` | `forecast_adjustment_revert` | `@require_POST` + `@tenant_admin_required` |
| `forecast/adjustments/<int:pk>/edit/` | `forecast_adjustment_edit` | `forecast_adjustment_edit` | `@tenant_admin_required` |
| `forecast/adjustments/<int:pk>/delete/` | `forecast_adjustment_delete` | `forecast_adjustment_delete` | `@require_POST` + `@tenant_admin_required` |
| `forecast/adjustments/<int:pk>/` | `forecast_adjustment_detail` | `forecast_adjustment_detail` | `@login_required` |

### 5.4 `urls/SalesForecasting/ForecastScenarios.py`

| Path | `name=` | View | Method / gate |
|---|---|---|---|
| `forecast/scenarios/` | `forecast_scenario_list` | `forecast_scenario_list` | `@login_required` |
| `forecast/scenarios/add/` | `forecast_scenario_create` | `forecast_scenario_create` | `@tenant_admin_required` |
| `forecast/scenarios/apply/` | `forecast_scenario_apply` | `forecast_scenario_apply` | `@require_POST` + `@tenant_admin_required` |
| `forecast/scenarios/<int:pk>/select/` | `forecast_scenario_select` | `forecast_scenario_select` | `@require_POST` + `@tenant_admin_required` |
| `forecast/scenarios/<int:pk>/edit/` | `forecast_scenario_edit` | `forecast_scenario_edit` | `@tenant_admin_required` |
| `forecast/scenarios/<int:pk>/delete/` | `forecast_scenario_delete` | `forecast_scenario_delete` | `@require_POST` + `@tenant_admin_required` |
| `forecast/scenarios/<int:pk>/` | `forecast_scenario_detail` | `forecast_scenario_detail` | `@login_required` |

### 5.5 `urls/SalesForecasting/ForecastBoards.py` (the four derived reports — **no new model**)

| Path | `name=` | View | Gate |
|---|---|---|---|
| `forecast/board/` | `forecast_board` | `forecast_board` | `@login_required` |
| `forecast/attainment/` | `forecast_attainment` | `forecast_attainment` | `@login_required` |
| `forecast/accuracy/` | `forecast_accuracy` | `forecast_accuracy` | `@login_required` |
| `forecast/call/` | `forecast_call` | `forecast_call` | `@login_required` |

`forecast_scenario_apply` takes its period from the POST body (a `ForecastScenarioApplyForm`), so it is a **collection-level literal route** declared above every `<int:pk>` route in that module.


### 5.6 Final concatenated order in `apps/sales/urls/__init__.py`

Add five imports (`… as _forecast_periods`, `_forecast_submissions`, `_forecast_adjustments`, `_forecast_scenarios`, `_forecast_boards`) and insert five entries **after `*_boards` and before `*_pipelines`**, so the read-only report pages sit next to the other board surfaces rather than at the very end of the list:

```python
urlpatterns = [
    *_overview,             # 8.1
    *_score_events,
    *_qualifications,
    *_routing_rules,
    *_nurture,
    *_enrichment,           # 8.3
    *_stakeholders,
    *_classifications,
    *_plans,
    *_boards,
    *_forecast_periods,     # 8.4  ← NEW
    *_forecast_submissions, # 8.4  ← NEW
    *_forecast_adjustments, # 8.4  ← NEW
    *_forecast_scenarios,   # 8.4  ← NEW
    *_forecast_boards,      # 8.4  ← NEW
    *_pipelines,            # 8.2
    *_teams,
    *_competitors,
    *_outcomes,
    *_workspace,
]
```

This is safe because the five new groups all start with the distinct literal segment `forecast/`, and no existing sales group contains a `<str:…>` catch-all. Within each new module keep the listed order: collection literals → `add/` → `export/` → `apply/` → `<int:pk>` action routes → `<int:pk>/edit/` → `<int:pk>/delete/` → `<int:pk>/`.

## 6. VIEW CONTEXT KEYS — the field that decides whether the build works (L7 / L8)

**Every key below is mandatory.** A name left unpinned renders a blank region and still returns **200** (L8) — that is exactly the failure this section exists to prevent. `page_obj` must come from `apps.core.crud.paginate` (it sets `page_obj.window`, which `templates/partials/pagination.html` iterates unguarded at line 16), never from a bare `Paginator(...).get_page(...)`.

Shared list-view rules: `q = request.GET.get("q","").strip()[:200]`; integer FK params go through `apps.core.crud.as_db_int` (L11 — `?period=abc` and an over-range `?period=999…9` are **skipped, not 500**); enum params are checked against `dict(Model.<X>_CHOICES)` and **reset to `""` on a junk value** so a stale bookmark shows the unfiltered register rather than an empty one; `page_obj = paginate(request, queryset, 20)`; `stats = base_queryset.aggregate(...)`; `export_url = reverse(...)` with `request.GET.urlencode()` appended (the `account_plan_list` shape).

### 6.1 `ForecastPeriods` views

**`forecast_period_list`** → `sales/salesforecasting/forecastperiod/list.html`

| Key | Value |
|---|---|
| `object_list` | `page_obj.object_list` |
| `page_obj` | `paginate(request, queryset, 20)` |
| `q` | the stripped search string |
| `period_type` / `rollup_dimension` | the raw GET echo (`""` when junk) |
| `active` | `"active"` / `"inactive"` / `""` |
| `locked` | `"locked"` / `"unlocked"` / `""` |
| `period_type_choices` | `SalesQuota.PERIOD_CHOICES` |
| `rollup_dimension_choices` | `ForecastPeriod.ROLLUP_DIMENSION_CHOICES` |
| `active_choices` | `[("active","Active"),("inactive","Inactive")]` |
| `locked_choices` | `[("locked","Locked"),("unlocked","Unlocked")]` |
| `stats` | `.aggregate()` with keys **`total`, `active`, `inactive`, `locked`, `current`** |
| `export_url` | `reverse("sales:forecast_period_export")` + preserved GET |
| `can_edit_all` | `request.user.is_superuser or is_tenant_admin` |

**`forecast_period_detail`** → `…/forecastperiod/detail.html`: `obj`, `submissions` (list `[:200]`), `submissions_count`, `submission_rows` (per-status counts), `status_choices` (`ForecastSubmission.STATUS_CHOICES`), `scenarios` (list), `category_totals` (dict keyed by the five category values → `Decimal`), `total_forecast_amount` (the sum over that dict), `currency_rollups` (dict `{currency_code: {pipeline, best_case, commit, closed, total}}` — never summed across codes), `fx_note` (the `fx_rate_source_date` / missing-rate message), `can_edit`, `can_lock`, `is_locked`.

**`forecast_period_create`** / **`forecast_period_edit`** → `…/forecastperiod/form.html`: `form`, `is_edit` (`False`/`True`), `obj` (**edit only**), `period_type_choices`, `rollup_dimension_choices`, `currencies` (list of `accounting.Currency`, `[:500]`), `can_lock`, `is_locked`. **`start_date`/`end_date` are NEVER context keys** — the form shows the derived `obj.start_date` / `obj.end_date` after a successful save, or an empty state on create.

**`forecast_period_export`** → CSV, no context (`csv_export_response(..., dataset="forecast_periods", filename="sales-forecast-periods.csv")`). **`_lock` / `_unlock`** → redirect to `sales:forecast_period_detail`. **`_delete`** → redirect to `sales:forecast_period_list`.


### 6.2 `ForecastSubmissions` views

**`forecast_submission_list`** → `…/forecastsubmission/list.html`

| Key | Value |
|---|---|
| `object_list`, `page_obj`, `q` | as above |
| `status` | raw GET echo |
| `period_id` | `as_db_int(...) or ""` |
| `owner_id`, `org_unit_id`, `territory_id`, `pipeline_id` | `as_db_int(...) or ""` |
| `status_choices` | `ForecastSubmission.STATUS_CHOICES` |
| `periods` | tenant-scoped `ForecastPeriod` list `[:200]` for the filter dropdown |
| `period_choices` | `[(p.pk, str(p)) for p in periods]` — **both keys**, the template may need value/label pairs |
| `owners`, `org_units`, `territories`, `pipelines` | FK filter lists, tenant-scoped, `[:500]` |
| `page_total_forecast` | `Decimal` — the sum of `total_forecast_amount` over the **page**, for the stat card. **Do not name it `total_forecast_amount` on a list** — on a list that name is ambiguous with a single object's property and the template will silently read the wrong one. |
| `stats` | `.aggregate()` with keys **`total`, `draft`, `submitted`, `approved`, `rejected`, `locked`** |
| `export_url`, `can_edit_all` | as above |

**`forecast_submission_detail`** → `…/forecastsubmission/detail.html`: `obj`, `period`, `owner`, `org_unit`, `territory`, `pipeline`, `quota`, `category_amounts` (dict `{category_value: Decimal}` for the five values), `total_forecast_amount` (**the property**), `weighted_amount`, `quota_amount`, `actual_amount`, `variance_amount` (**the property**), `attainment_pct` (**the property**, or `None`), `pace_pct` (**the property**, or `None`), `adjustments` (list `[:200]`), `adjustment_rows` (per-`reason_code` counts — the sandbagging signal), `opportunity_rollups` (per-currency weighted/open counts from `sales.OpportunityPipelinePlacement`), `ai_available` (bool — the 40-won/40-lost gate), `ai_gate_message` (shown when the gate fails; **no prediction value may be rendered in that case**), `ai_explanation` (`obj.ai_explanation`, always beside any prediction), `status_choices`, `allowed_actions`, `can_edit`, `can_submit`, `can_review`, `is_period_locked`.

**`forecast_submission_create` / `_edit`** → `…/forecastsubmission/form.html`: `form`, `is_edit`, `obj` (edit only), `periods`, `owners`, `org_units`, `territories`, `pipelines`, `quotas` (tenant-scoped `crm.SalesQuota`, `[:500]`), `category_choices` (`Opportunity.FORECAST_CATEGORY_CHOICES`, the field legend), `is_period_locked`, `can_submit`.

**`_submit` / `_approve` / `_reject`** → redirect to `sales:forecast_submission_detail` with a `messages.success` / `messages.error` on `ValidationError` (the `_transition_plan` shape). **`_delete`** → redirect to `sales:forecast_submission_list`. **`_export`** → no context.

### 6.3 `ForecastAdjustments` views

An adjustment has **no `status`** — do not invent one. Its filter set is `kind`, `reason_code`, `target_field`, `submission_id`, `opportunity_id`, `is_reverted`.

**`forecast_adjustment_list`** → `…/forecastadjustment/list.html`: `object_list`, `page_obj`, `q`, `kind`, `reason_code`, `target_field`, `submission_id`, `opportunity_id`, `is_reverted`, `adjustment_kind_choices`, `reason_code_choices`, `target_field_choices`, `category_choices`, `submissions` (list `[:200]`), `opportunities` (list `[:500]`), `reverted_choices` (`[("yes","Reverted"),("no","Not reverted")]`), `stats` (keys **`total`, `direct`, `indirect`, `revert`, `reverted`, `unreverted`**), `export_url`, `can_edit_all`.

**`forecast_adjustment_detail`** → `…/forecastadjustment/detail.html`: `obj`, `submission`, `opportunity`, `placement`, `created_by`, `net_delta` (**the property**, or `None` for a `category` row), `original_display` / `adjusted_display` (a value **or** a category label, resolved for the row's `target_field` — one key, resolved in the view, so the template never branches on `target_field` itself), `reason_code_choices`, `revert_form` (a `ForecastRevertForm` instance), `can_revert`, `can_edit`, `can_delete`, `is_reverted`, `revert_reason`, `reverted_at`.

**`forecast_adjustment_create` / `_edit`** → `…/forecastadjustment/form.html`: `form`, `is_edit`, `obj` (edit only), `submissions`, `opportunities`, `placements` (only those whose `opportunity_id` matches the chosen opportunity; `[]` on create), `adjustment_kind_choices`, `target_field_choices`, `reason_code_choices`, `category_choices`, `is_period_locked`.

**`_revert`** → redirect to `sales:forecast_adjustment_detail`. **`_export`** → no context. **`_delete`** → redirect to `sales:forecast_adjustment_list`.

### 6.4 `ForecastScenarios` views

**`forecast_scenario_list`** → `…/forecastscenario/list.html`: `object_list`, `page_obj`, `q`, `scenario_type`, `period_id`, `owner_id`, `is_selected` (`"yes"`/`"no"`/`""`), `scenario_type_choices`, `periods`, `owners`, `selected_choices`, `stats` (keys **`total`, `upside`, `base`, `downside`, `custom`, `selected`**), `can_edit_all`. **No `export_url`** — scenarios ship no export action; a template that renders one is a template bug.

**`forecast_scenario_detail`** → `…/forecastscenario/detail.html`: `obj`, `period`, `owner`, `effective_pipeline_amount`, `effective_best_case_amount`, `effective_commit_amount` (**the properties**, or `None`), `baseline_totals` (the selected/baseline submission's five category amounts — the input to the deltas), `periods`, `owners`, `scenario_type_choices`, `can_apply`, `can_select`, `can_edit`, `can_delete`, `isolation_note` (the constant text stating that applying a scenario never mutates a submission).

**`forecast_scenario_create` / `_edit`** → `…/forecastscenario/form.html`: `form`, `is_edit`, `obj` (edit only), `periods`, `owners`, `scenario_type_choices`, `is_period_locked`.

**`_select`** / **`forecast_scenario_apply`** → redirect to `sales:forecast_scenario_detail`. **`_delete`** → redirect to `sales:forecast_scenario_list`.


### 6.5 `ForecastBoards` views (all four, read-only, derived — **no new model**)

**`forecast_board`** → `sales/salesforecasting/forecastboard/board.html`

| Key | Value |
|---|---|
| `period` | the selected `ForecastPeriod` (from `?period=<int>`) or `None` |
| `periods` | the period filter list, `[:200]` |
| `period_choices` | `[(p.pk, str(p)) for p in periods]` |
| `category_choices` | `Opportunity.FORECAST_CATEGORY_CHOICES` |
| `rows` | per-`rollup_dimension` node: `{"key","label","owner","org_unit","territory","per_category":{cat: Decimal},"total_forecast_amount","weighted_amount","quota_amount","attainment_pct","variance_amount","ai_predicted_commit","ai_confidence_pct","ai_explanation","child_count","depth"}` — **`total_forecast_amount` / `attainment_pct` / `variance_amount` on a row are computed in the service, never read off a column** |
| `totals_by_category` | `{cat: Decimal}` across `rows` |
| `grand_total` | `Decimal` |
| `ai_available` | bool — `OpportunityOutcome` counts `>= 40 won` **and** `>= 40 lost` |
| `ai_gate_message` | the explanatory sentence rendered when the gate fails |
| `ai_explanation` | dict of factor → weight for the selected period, or `{}` |
| `rollup_dimension` | the raw GET echo |
| `rollup_dimension_choices` | `ForecastPeriod.ROLLUP_DIMENSION_CHOICES` |
| `caveats` | list of strings (missing FX rate, missing quota, no `OrgUnit` node) |
| `stats` | keys **`periods`, `submissions`, `approved`, `adjustments`, `scenarios`** |

**`forecast_attainment`** → `…/forecastboard/attainment.html`: `period`, `periods`, `period_choices`, `rows` (`{"owner","org_unit","territory","quota_amount","actual_amount","attainment_pct","pace_pct","variance_amount"}`), `pace_pct` (the period's property), `ahead_rows` / `behind_rows` / `on_pace_rows` (three pre-filtered lists — the template does not re-filter), `stats` (keys **`total`, `ahead`, `on_pace`, `behind`, `no_quota`**), `caveats`, `can_edit_all`.

**`forecast_accuracy`** → `…/forecastboard/accuracy.html`: `periods` (all past periods, `[:200]`), `rows` (per period: `{"period","label","submitted_total","actual_amount","variance_amount","bias_pct","weight_bias","adjustment_count"}`), `bias_rows` (per owner: `{"owner","mean_bias_pct","submissions"}`), `sandbagging_rows` (per owner: `{"owner","early_vs_final_pct","adjustment_count"}`), `stats` (keys **`periods`, `mean_bias_pct`, `worst_biased_owner`**), `caveats`, `period_choices`, `selected_period_id`.

**`forecast_call`** → `…/forecastboard/call.html`: `period`, `periods`, `period_choices`, `submission_rows` (per submission: `{"submission","owner","org_unit","territory","category_amounts","total_forecast_amount","status","submitted_at"}`), `adjustment_rows` (per adjustment with its `reason_code`, `created_by`, `note`, `is_reverted` — the "why did my forecast change" answer), `ai_available`, `ai_gate_message`, `ai_explanation`, `caveats`, `can_review`.

**No board view writes anything.** `write_audit_log` is **not** called from a read; only a CSV export writes an audit row, and that is `csv_export_response`'s job.

### 6.6 Hand-rolled save paths — mandatory `write_audit_log`

`crud_*` gives create/edit/delete their audit row for free. The **hand-rolled** actions must call `write_audit_log(request.user, obj, "update", {...}, tenant=request.tenant)` themselves, inside the same `transaction.atomic()` as the write (the `opportunity_win_loss_reason_create` shape):

| Action | `changes` dict (minimum) |
|---|---|
| `forecast_submission_submit` | `{"operation": "submit_forecast", "status": "submitted", "total_forecast_amount": str(...)}` |
| `forecast_submission_approve` | `{"operation": "approve_forecast", "note": …}` |
| `forecast_submission_reject` | `{"operation": "reject_forecast", "note": …}` |
| `forecast_adjustment_create` / `_edit` / `_revert` | `{"operation": "create_adjustment" / "revert_adjustment", "reason_code": …, "revert_reason": …}` |
| `forecast_period_lock` / `_unlock` | `{"operation": "lock_period" / "unlock_period"}` |
| `forecast_scenario_apply` / `_select` | `{"operation": "apply_scenario" / "select_scenario", "period": …, "target": …}` |

Never put a raw amount-bearing note into `changes` without truncating; `_changed()` already caps at 200 chars for form-driven changes, and the hand-rolled dicts must do the same.


## 7. Templates

Folder is **`templates/sales/salesforecasting/`** (mechanical lowercase, matching 8.1 `leadmanagement/` and 8.3 `contactaccountmanagement/` — see §1; the research's `forecasting/` suggestion was overridden and must not be restored). Shape is `templates/<app>/<submodule>/<entity>/<page>.html` with the **bare** page filename; a flat `<entity>_<page>.html` is banned.

| Path | Rendered by |
|---|---|
| `salesforecasting/forecastperiod/list.html` | `forecast_period_list` |
| `salesforecasting/forecastperiod/detail.html` | `forecast_period_detail` |
| `salesforecasting/forecastperiod/form.html` | `forecast_period_create`, `forecast_period_edit` |
| `salesforecasting/forecastsubmission/list.html` | `forecast_submission_list` |
| `salesforecasting/forecastsubmission/detail.html` | `forecast_submission_detail` |
| `salesforecasting/forecastsubmission/form.html` | `forecast_submission_create`, `forecast_submission_edit` |
| `salesforecasting/forecastadjustment/list.html` | `forecast_adjustment_list` |
| `salesforecasting/forecastadjustment/detail.html` | `forecast_adjustment_detail` |
| `salesforecasting/forecastadjustment/form.html` | `forecast_adjustment_create`, `forecast_adjustment_edit` |
| `salesforecasting/forecastscenario/list.html` | `forecast_scenario_list` |
| `salesforecasting/forecastscenario/detail.html` | `forecast_scenario_detail` |
| `salesforecasting/forecastscenario/form.html` | `forecast_scenario_create`, `forecast_scenario_edit` |
| `salesforecasting/forecastboard/board.html` | `forecast_board` |
| `salesforecasting/forecastboard/attainment.html` | `forecast_attainment` |
| `salesforecasting/forecastboard/accuracy.html` | `forecast_accuracy` |
| `salesforecasting/forecastboard/call.html` | `forecast_call` |

**16 files.** The four report pages sit in a `forecastboard/` entity folder as **secondary action pages inside the entity folder** (bare filenames, no flat `forecast_board.html` at the app root) — the 8.2 `…/pipeline/board.html` precedent.

**Design-system rules (verified against the sibling 8.3 templates, L33):**
- `{% extends "base.html" %}` on all 16; `{% include "partials/pagination.html" %}` after every table (it needs `page_obj` **and** `page_obj.window`).
- Badges: **only** `badge-green` / `badge-red` / `badge-amber` / `badge-info` / `badge-muted` / `badge-slate`. The semantic `-success` / `-danger` names **do not exist** in `static/css/theme.css`.
- Stat icons: **only** `blue` / `green` / `orange` / `purple` / `slate` (`<div class="stat-icon blue">`).
- Other verified classes used by the siblings: `page-header`, `page-title`, `breadcrumb`, `page-actions`, `card`, `card-header`, `card-title`, `card-body`, `table-wrap`, `table`, `th-actions`, `table-actions`, `btn`, `btn-primary`, `btn-outline`, `btn-danger`, `btn-icon`, `btn-icon danger`, `form-input`, `form-select`, `form-textarea`, `form-check`, `form-group`, `form-error`, `filter-bar`, `detail-grid`, `detail-item`, `empty-state`, `text-muted`, `sr-only`.
- Pagination uses `has_previous` / `has_next` **guards** — never unguarded `previous`/`next` (L9; the partial already guards, so just include it).
- **FK/pk comparisons in filter dropdowns use `|stringformat:"d"`** — `{% if request.GET.period == p.pk|stringformat:"d" %}selected{% endif %}`. **Never `|slugify`** on a pk.
- Every list has an **Actions column**: eye → detail, pencil → edit, bin → a POST form with `{% csrf_token %}` and `onsubmit="return confirm('…')"`, wrapped in `{% if can_edit %}` / status guards.
- Every detail has an **Actions sidebar**: Edit, POST+confirm Delete (status-conditional), Back to List (`{% url 'sales:forecast_*_list' %}`).
- Every badge branch ends in an `{% else %}` fallback of `{{ obj.get_field_display }}`; nullable values are guarded `{% if obj.x %}…{% else %}—{% endif %}`.
- **The derived totals block on each detail renders from the PROPERTIES** — `{{ obj.total_forecast_amount }}`, `{{ obj.variance_amount }}`, `{{ obj.attainment_pct|default:"—" }}` — never from a stored column. `attainment_pct` returning `None` must render as `—`, not `0`.
- The forecast board shows the **entered** category amounts **beside** the `ai_*` prediction column, and `ai_explanation` is rendered **wherever a prediction appears** — a number is never presented without its reason. When `ai_available` is `False`, render `ai_gate_message` and **no prediction value at all**.
- No `{# … #}` comments and no `{% comment %}` blocks (the smoke sweep greps for leaked comment markers).


## 8. Services and the rollup axis

New flat module `apps/sales/forecast_services.py` (a single-purpose flat module at the app root is allowed, exactly like `apps/sales/services.py`, `opportunity_services.py`, `opportunity_analytics.py`). It holds `forecast_org_unit_chain`, `forecast_submission_snapshot`, `forecast_rollup_rows`, `forecast_attainment_rows`, `forecast_accuracy_rows`, `forecast_ai_gate`, `forecast_submit`, `forecast_review`, `forecast_revert`, `forecast_lock_period`, `forecast_apply_scenario`.

**The rollup axis — the single most likely place for a bad FK.** There is **no `User.manager` field** anywhere in the codebase (verified: `accounts.User`, `apps/accounts/models.py:52`, has `tenant`, `party`, `role`, `email`, `username`, `first_name`, `last_name`, `is_tenant_admin`, `status`, `is_active`, `is_staff`, `date_joined` — no manager). Rep→manager→director walks **`core.OrgUnit.parent`** (`apps/core/models/OrgUnit.py:19`, `related_name="children"`). Resolve a user's node through `sales.OpportunityTeamMember.org_unit` (verified: `OpportunityTeams.py:27-32`), falling back to the submission's own `org_unit` / `territory`.

- The walk must be **iterative, bounded and cycle-safe** (a `seen` set, a hard depth cap, children visited not followed blindly). `core.OrgUnit.parent` is a self-FK with **no cycle validation anywhere in the codebase**, so a legacy cycle is reachable — the same hazard `AccountBoards` handles for the CRM account hierarchy, and the same reason 8.3 had to render a `cycle_detected` flag.
- **"You cannot adjust a level above you"** (Microsoft): `forecast_adjustment_create` compares the acting user's node against the submission's node on the walk and refuses a downward-only violation with `PermissionDenied`. This is a **business rule over a role check, not a record ACL** — a tenant admin passes it.
- FX: read `accounting.ExchangeRate` by `(tenant, currency, rate_date = period.fx_rate_source_date or period.end_date)`; on a miss add the row to `caveats` and **never fall back to 1.0 silently**. `accounting.Currency` has no `tenant` field, so it is never tenant-filtered (L29).
- `actual_amount` derives from `sales.OpportunityOutcome` (`result="won"`, `tenant=request.tenant`, `closed_at` inside the period). `OpportunityOutcome.save()` refuses a re-save and `delete()` refuses a delete — it is append-only, so treat it strictly as a read source.
- `weighted_amount` uses `sales.OpportunityPipelinePlacement.effective_probability` (the property at `Pipelines.py:356-360`, which already prefers `probability_override` over the stage probability), grouped by `opportunity.currency`.

## 9. Migration + Integrate (single-writer pass)

**Verify every expected file landed BEFORE wiring anything** (L12 — the check-after-edit hook blocks a shared-file edit before its target exists).

1. `apps/sales/models/__init__.py` — add the import line **and** the `__all__` entry. The existing shape is one `from .<SubModule>.<Entity> import (…)` per line, then a flat `__all__` list. Add:
   ```python
   from .SalesForecasting.ForecastPeriods import ForecastPeriod
   from .SalesForecasting.ForecastSubmissions import ForecastSubmission
   from .SalesForecasting.ForecastAdjustments import ForecastAdjustment
   from .SalesForecasting.ForecastScenarios import ForecastScenario
   ```
   plus `"ForecastPeriod", "ForecastSubmission", "ForecastAdjustment", "ForecastScenario",` in `__all__`. **Forgetting either half is an `ImportError` at runtime** — and `seed_sales.py` imports from `apps.sales.models`, so a missing re-export breaks the seeder too.
2. `apps/sales/forms/__init__.py` — add the seven form imports + `__all__` entries (`ForecastPeriodForm`, `ForecastSubmissionForm`, `ForecastAdjustmentForm`, `ForecastScenarioForm`, `ForecastReviewForm`, `ForecastRevertForm`, `ForecastScenarioApplyForm`).
3. `apps/sales/views/__init__.py` — **the existing `__all__` is a computed glob**: `__all__ = [name for name in globals() if name.startswith(("lead_", "party_enrichment_", "account_", "opportunity_"))]`. **Every 8.4 view function name must start with `forecast_` so it is included**, otherwise `views.forecast_period_list` raises `AttributeError` at import. Recommendation: the url modules use **explicit named imports** (the `OpportunityPipeline` / `CompetitiveIntelligence` pattern, more robust than `ContactAccountManagement`'s `from apps.sales import views`), and the `forecast_` prefix is still required for the glob.
4. `apps/sales/urls/__init__.py` — five imports + five `*_forecast…` entries in the order given in §5.6.


5. `apps/sales/admin.py` — four `@admin.register` blocks matching the sibling shape (`list_display`, `list_filter`, `search_fields`, `readonly_fields`, `list_select_related`, `raw_id_fields`). `ForecastSubmission` gets `raw_id_fields = ("period","owner","org_unit","territory","pipeline","quota_ref","submitted_by","reviewed_by")` and `readonly_fields` covering `tenant`, `number`, `status`, `weighted_amount`, `quota_amount`, `actual_amount`, `submitted_at`, `reviewed_at` and the whole `ai_*` block — **Django admin is a second writer; every workflow- and service-controlled field must be readonly there or the append-only / snapshot rulings are bypassable from `/admin/`.** `ForecastScenario` also gets `projected_commit_amount`, `projected_total_amount` and `is_selected` readonly.
6. `apps/sales/management/commands/seed_sales.py` — **extend the existing command; do not create a new one.** Add `_seed_sales_forecasting(tenant, owner)` called from `_seed_tenant`, reusing the `Party` / `Opportunity` / `Pipeline` / `OpportunityOutcome` / `Territory` / `Currency` rows it already seeds. Guard each creation with an existence check on `(tenant, number)` so a **second run is a no-op** (run it **twice**). Update `help=` to name 8.4, and **keep** the existing tenant-admin login line and the "Superuser `admin` has tenant=None" warning. Seed at least: 2 `ForecastPeriod` (one current, one past), 2-3 `ForecastSubmission` across two owners, 2-3 `ForecastAdjustment` (one `reverted`), 2 `ForecastScenario` (one baseline **and** selected). Do **not** seed 40 won + 40 lost outcomes — the AI gate must fail in the seeded demo (§10).
7. **No `config/settings.py` edit. No `config/urls.py` edit.** Confirm `apps.sales` is installed and the root include already points at `apps/sales/urls/`; change nothing unless a check fails.
8. `makemigrations sales` → **claims `0007`**. `migrate` → `seed_sales` **twice** → `python manage.py check` → `makemigrations --check` must print **"No changes detected"** (the models sit deeper than the app root, but Django still derives `app_label` from the app config, so a correct split needs no extra migration).

### `LIVE_LINKS["8.4"]` in `apps/core/navigation.py`

One new dict, placed after the existing `"8.3"` block (~line 2188; `"8.1"` ~2167, `"8.2"` ~2179). Keys are the **exact NavERP.md 8.4 bullet strings**, verbatim from lines 1328-1332. Every value is a **staff-reachable** management page — **never a login-gated portal view** (L32).

```python
"8.4": {
    "Forecast Categories & Commitments":      "sales:forecast_submission_list",
    "AI-Powered Predictive Forecasting":      "sales:forecast_board",
    "Quota Management & Attainment":          "sales:forecast_attainment",
    "Forecast Rollups & Adjustments":         "sales:forecast_adjustment_list",
    "Forecast Accuracy & Variance Analysis":  "sales:forecast_accuracy",
    # Reversing extras (not NavERP.md bullets):
    "Forecast Periods":      "sales:forecast_period_list",
    "Scenarios & What-If":   "sales:forecast_scenario_list",
    "Forecast Call":         "sales:forecast_call",
},
```

The five bullet strings must match NavERP.md **character for character** — `parse_catalog()` keys the module tree off them and a typo silently produces a dead bullet. Do not touch `"8.1"`, `"8.2"`, `"8.3"` or any other live key, and do not touch the catalog machinery.

## 10. Verification (smoke sweep as `admin_acme` / `password`)

The superuser `admin` has `tenant=None` and sees no module data **by design** — smoke as a tenant admin. **Content assertions, not just status** (L8: a mismatched context var returns 200 and renders blank).

- Every new `sales:*` URL returns 200/302 as expected.
- Each page actually **contains** its title, a seeded `FCP-`/`FCS-`/`FAD-`/`FSC-` number, the seeded owner name, and the **derived** total.
- **Junk params** — `?status=nonsense&period=abc&q=%20&owner=999999999999999999999` — do not 500 and do not empty the register.
- **Page 2** of each list paginates.
- **Cross-tenant IDOR → 404** for a foreign tenant's period / submission / adjustment / scenario, on every `<int:pk>` route.
- Every mutation **rejects GET** (405) and requires valid CSRF.
- No `{#` or `{% comment` leaks into the rendered HTML.
- **Scenario isolation:** applying a `ForecastScenario` leaves every `ForecastSubmission` row byte-identical.
- **AI gate:** with the seeded data the 40-won/40-lost gate fails, the board renders `ai_gate_message`, and **no prediction value appears** in the HTML.
- **Lock:** a locked `ForecastPeriod` makes its submissions read-only — an edit POST on a locked period is rejected **server-side**, not just hidden in the UI.
- Sidebar shows **8.4 Live** and all five bullets navigate to working staff pages.
- Run the 8.4 test modules alone first, then the **full unfiltered** sales suite — never a `-k` filter (L47). **Carry-forward:** 8.2 skipped Phase 6/7, so `test_opportunitypipeline_security.py` is untracked and the sales suite may already be red at 8.4 close-out; report 8.2 residue as **pre-existing**, do not regress into it.


## 11. Risks (each with its lesson)

| # | Risk | Lesson |
|---|---|---|
| R1 | **Unpinned context key** → a 200 that renders a blank filter bar, stat card or totals block. §6 is the whole defence. | **L7 / L8** |
| R2 | **`request.tenant is None`** for the superuser `admin`. Every list must filter `tenant=request.tenant` (an empty result is correct) and never use `Model.objects.all()`; `crud_create` already refuses with "Select a tenant workspace before creating records." | Multi-tenancy rules 1/2 |
| R3 | **`related_name` collisions.** `crm.Opportunity` already carries `sales_pipeline_placement`, `sales_team_members`, `sales_outcomes`, `sales_competitors`, `sales_account_plans`, `splits`; `crm.Territory` carries `opportunities`, `sales_quotas`, `child_territories`; `core.OrgUnit` carries `org_units`, `children`; `accounts.User` carries `crm_opportunities`, `crm_sales_quotas`, `crm_territories`, `crm_tasks` and more. 8.4 uses `sales_forecast_submissions`, `sales_forecast_scenarios`, `sales_forecast_adjustments`, `submissions`, `scenarios`, `adjustments`, and `"+"` on every actor FK. **Two FKs from one model to the same target need distinct `related_name`s or Django raises `fields.E304` at check time.** | L28 |
| R4 | **URL-order collision.** First-match-wins. Verified: no `<str:…>` route exists anywhere in `apps/sales/urls/`, and `forecast/` is a fresh literal prefix — but any future greedy route under `forecast/` must be declared **last**; within a module, literals before `<int:pk>`. | package rule 6 |
| R5 | **Re-export omission.** A model/form/view added without its `__init__.py` line **and** its `__all__` entry is an `ImportError`/`AttributeError` at runtime, not at build time. `apps/sales/views/__init__.py` computes `__all__` from a **prefix glob** (`lead_`, `party_enrichment_`, `account_`, `opportunity_`) — every 8.4 view must start with `forecast_` to be included. | package rule 3 |
| R6 | **Decimal / FX rounding.** `Decimal(self.commit_amount or 0) + …` — never `float`. `attainment_pct` / `pace_pct` **divide by `quota_amount`** and must return `None` rather than raising `ZeroDivisionError` or rendering `Infinity`/`NaN`. Multi-currency sums are grouped by verified currency code and **never** combined; a missing `ExchangeRate` becomes a `caveats` entry, not a 1.0 default. | L29 / L33 |
| R7 | **`core.OrgUnit.parent` rollup with no `User.manager`.** FK'ing a non-existent `User.manager` is a `FieldError` at import. The walk must be cycle-safe: `OrgUnit.parent` has **no** cycle validation anywhere in the codebase, so a legacy cycle hangs or over-counts a rollup. | L28 |
| R8 | **PROTECT FKs + delete paths.** `ForecastSubmission.period`, `ForecastAdjustment.submission`, `ForecastScenario.period` are `PROTECT`; a `ForecastPeriod.delete()` with submissions raises `ProtectedError`, which is a **500** unless the view catches it (the `opportunity_win_loss_reason_create` `except (ValidationError, IntegrityError)` + `ProtectedError` shape). Guard every delete path. | — |
| R9 | **A locked period must be read-only server-side.** Hiding the Edit button is not enforcement; the edit / submit / adjust / scenario actions each re-check `period.is_locked`. | — |
| R10 | **Django admin as a second writer.** Without the `readonly_fields` in §9.5, `/admin/` bypasses every workflow, snapshot and append-only ruling in this contract. | — |
| R11 | **Migration-number collision** with another session building in this checkout → agree `0007` before generating. | **L43** |
| R12 | **A dirty working tree is not 8.4's.** The checkout was already dirty at plan time (`M templates/projects/reporting/*`, `M .claude/tasks/todo.md`, untracked `.commandcode/`, `.gemini/`, `.workbuddy-ai/`, `.zcode/`). Leave those alone and never commit them. | **L45** |
| R13 | **Colour-named classes only.** `badge-success` / `badge-danger` do not exist in `static/css/theme.css`; a typo renders unstyled, not red. | **L33** |
| R14 | **Seeded login** is `admin_acme` / `password`; the superuser `admin` / `admin` has `tenant=None` — report that as a design fact, not a bug. | Multi-tenancy rule 1 |


## 12. Test contract (namespace `salesforecasting`)

`apps/sales/tests/` already exists with `__init__.py` and `conftest.py` (owned by 8.1 — **do not edit `conftest.py` from a later step without re-running the full suite**). Add, in this order, one file at a time, each committed alone:

- `test_salesforecasting_models.py` — field/choices/`related_name` assertions; the derived-vs-stored ruling (**assert `total_forecast_amount` is not a concrete field on `_meta`**); every `clean()` refusal; `TenantNumbered` minting (`FCP-00001` shape); the exact constraint and index names.
- `test_salesforecasting_forms.py` — each `Meta.fields` list verbatim; the exclusion set (assert `tenant`, `number`, `status`, every `ai_*` and `weighted_amount` are **not** in `form.fields`); `reason_code` required; non-negative amounts; date-range validation; `tenant=None` → `.none()` querysets.
- `test_salesforecasting_views.py` — every url name resolves; every list renders 200 **and contains** its context data; junk params do not 500; page 2 works; every `forecast_*` view name is present in `apps.sales.views.__all__`.
- `test_salesforecasting_security.py` — cross-tenant 404 on every `<int:pk>` route; GET rejected on every mutation; CSRF enforced; `@tenant_admin_required` on the privileged actions; a non-admin cannot lock a period, approve a submission, or adjust a level above themselves; scenario isolation; the AI gate hides predictions.

Every test function is `test_salesforecasting_*` and every module-level helper is `_salesforecasting_*`, so the next sub-module appending nearby cannot shadow them.

## 13. Corrections to the plan, recorded

1. **`weighted_amount` is a snapshot, not a form field.** The plan lists it among the stored amounts *and* separately forbids stored derived values. Ruling pinned: a **service-written snapshot** (from `OpportunityPipelinePlacement.effective_probability`), **excluded from `ForecastSubmissionForm.Meta.fields`** exactly like the `ai_*` block (§3).
2. **A `(tenant, period, owner)` DB `UniqueConstraint` is forbidden, not merely unsafe.** `owner` is nullable and NULLs do not collide in a SQL unique index, so the constraint would silently permit unlimited duplicate drafts. Enforced in `clean()` instead (§3.2).
3. **`ForecastAdjustment` gets no `status` field.** Its filter set is `kind` / `reason_code` / `target_field` / `is_reverted`; the generic "wrap Edit/Delete in `{% if obj.status == 'draft' %}`" rule does not apply and was **not** carried over (§6.3).
4. **`ForecastScenario.is_selected` is a workflow field, not a form field** — the select action owns it — and a `CheckConstraint` makes only the baseline selectable, so there is exactly one selected scenario per tenant (§3.4 / §4.4).
5. **`start_date` / `end_date` are `editable=False`**, not merely "excluded", so the exclusion is structural (L22) and cannot be undone by a future `Meta.fields` edit (§3.1).
6. **`accounting.Currency` is global (no `tenant` field).** `TenantModelForm` tenant-scopes FK querysets only when the target model *has* a `tenant` field, so `reporting_currency` needs an explicit `is_active=True` queryset and must never be tenant-filtered (§3.1 / §4.1).
7. **The list-level total is pinned as `page_total_forecast`, not `total_forecast_amount`.** On a list page the singular name is ambiguous with a single object's property, and the template would silently read the wrong one (§6.2).
8. **URL insertion point is `after *_boards`, not appended at the end** — the four read-only report pages group with the other board surfaces. Ordering is safe either way because `forecast/` is a fresh literal prefix and no sales route is a `<str:…>` catch-all (§5.6).
9. **The views `__all__` glob is a real trap** — it filters on `lead_` / `party_enrichment_` / `account_` / `opportunity_` prefixes. Every 8.4 view name is pinned to start with `forecast_`, and the url modules use explicit named imports (the `OpportunityPipeline` pattern) rather than `from apps.sales import views` (§9.3).
10. **`ForecastScenario` ships no export action**, so there is no `export_url` context key and no export button — the plan did not require one (§6.4).

