# Contract — Sub-module 8.12 Sales Analytics & Intelligence (Module 8 — Sales Management System, `apps/sales`)

> The frozen code-level contract for the 8.12 build. Derived from `.claude/tasks/research-sales-8.12.md`
> and `.claude/tasks/todo.md` (the 8.12 plan section). **Every name below is pinned** — a name left
> unpinned is a silently blank region (L7) or a `NoReverseMatch` (L54).
>
> **App exists → EXTEND run.** No `config/settings.py` change. No `config/urls.py` change.
> **Migration: `0024`** (re-verify at generation time — L43).
>
> **CONCURRENT WRITER:** another session commits to this same checkout. Shared files are edited
> **surgically** (insert one block, never rewrite/reformat). Re-read each shared file immediately
> before editing it.

---

## 0. Ground rules that bind every file in this sub-module

| Rule | Requirement |
|---|---|
| Imports | **Absolute** inside `models/`, `forms/`, `views/`, `urls/` packages. `from apps.sales.models import X`. |
| Re-exports | Every new model/form/view must be added to the owning package's `__init__.py` import block **and** `__all__`. A model/form/view without a re-export is an `ImportError` at runtime. |
| `views/__init__.py` `__all__` | It is a **prefix filter** (`name.startswith((...))`). A view whose name prefix is not in that tuple is **silently not exported**. Every new view name prefix must be added. |
| `urls/__init__.py` | BOTH the `from .SalesAnalytics import urlpatterns as _sales_analytics` import **and** the `*_sales_analytics` splice into `urlpatterns` are required. The import alone is a no-op that still leaves `manage.py check` clean while every `reverse()` raises `NoReverseMatch` (L54). |
| Tenant | `tenant` is **inherited** from `TenantNumbered` (`apps/sales/models/_base.py`). **Do NOT redeclare it** — a second declaration is a duplicate field, not a unique `related_name`. Every view filters `Model.objects.filter(tenant=request.tenant)`. |
| Views | Function-based. `@login_required` on **all** views. **create/edit use `@login_required` only** — they are ordinary domain writes, and every sibling sub-module (8.9 CoachingScorecards, 8.10 CommissionEarnings, 8.11 CustomerHealthScores, 8.13 AttributionTouchpoints) gates them that way, so a sales rep can log their own debrief / scorecard. **delete** is `@require_POST` + `@tenant_admin_required` (the house pattern for a destructive write; `tenant_admin_required` already applies `@login_required` internally, so do not stack a third decorator). |
| Audit | Every write calls `write_audit_log(request.user, obj, "create"|"update"|"delete", <changes>, tenant=request.tenant)` from `apps/core/utils.py`. Signature: `write_audit_log(user, obj, action, changes=None, tenant=None)`. |
| Pagination | `Paginator(qs, 15)`. Links guard with `{% if page_obj.has_previous %}` / `{% if page_obj.has_next %}` (L9). |
| Integer FK filters | Validate with `_pk_filter()` from `apps/sales/views/SalesAnalytics/_helpers.py` — `.isdigit()` **plus** a 64-bit range bound. A bare `.isdigit()` is NOT enough: a 20-digit value reaches the DB and raises `OverflowError` on SQLite (rejected outright by MySQL) → 500. A junk or out-of-range value is **ignored**, never raises (L11). One shared helper, imported by all four entity view modules — do not re-implement it per entity. |
| FK pk compare in templates | `{% if request.GET.x == obj.pk|stringformat:"d" %}selected{% endif %}` — never `|slugify`. |
| Badges | COLOUR-NAMED classes only: `badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, `badge-slate`. `badge-success` / `badge-danger` / `badge-warning` **do not exist** in `static/css/theme.css` (L33). Every branch tests the model's **exact** CHOICES value and ends with an `{% else %}` fallback of `{{ obj.get_<field>_display }}`. |
| `.stat-icon` | Only `blue`, `green`, `orange`, `purple`, `slate` exist and are approved. No `amber`, no `red`. |
| Template comments | Multi-line notes use `{% comment %}…{% endcomment %}`. A multi-line `{# … #}` **leaks as visible text** (L2). |
| Nullable FK deref | Always `{% if obj.fk %}…{% else %}—{% endif %}`. A failed lookup inside a filter argument raises `VariableDoesNotExist` → 500 (L10). |
| Forms | `class Meta.fields` **excludes** `tenant`, `number`, `created_at`, `updated_at`, and every **derived** field. Base is `TenantModelForm` (auto-scopes tenant-scoped FK querysets, auto-applies widget classes). Add `TenantUniqueMixin` from `apps/sales/forms/_common.py` so `tenant` is stamped on a new instance. |
| Derived fields | A value that is a **ratio/difference of two fields on the same row** is **computed in `save()`**, marked `editable=False`, and excluded from the form. A value that IS the record's own measured data stays editable. |
| Templates | `{% extends "base.html" %}`. Path = `templates/sales/salesanalytics/<entity>/<page>.html` — one folder per sub-module → one folder per entity → bare `list` / `detail` / `form`. |
| Commits | One file per commit, PowerShell-safe `git add 'f'; git commit -m '…'`. Never `&&`. Never `git push`. |

### Verified spine (grep-confirmed — do not re-invent)
`core.Party` · `crm.Opportunity` (OPP-) · `crm.Lead` (LEAD-) · `crm.Territory` · `crm.SalesQuota` ·
`crm.CommunicationLog` · `crm.AnalyticsReport` / `AnalyticsDashboard` / `DashboardWidget` / `ReportSnapshot` ·
`sales.Pipeline` (PIPE-) · `sales.PipelineStage` · `sales.OpportunityPipelinePlacement` ·
`sales.WinLossReason` (WLR-) · `sales.OpportunityOutcome` (OUT-) · `sales.OpportunityCompetitor` ·
`sales.ActivityLog` (SAL-) · `sales.ActivityType` · `sales.QuotaPlan` (QPA-) · `sales.ForecastPeriod` ·
`sales.CoachingScorecard` (CSC-) · `accounting.Currency` · `accounts.User` (`settings.AUTH_USER_MODEL`).

### Existing analytics helpers the consoles render over — **never write a second aggregation engine**
`apps/sales/opportunity_analytics.py`:
`sales_win_loss_rows(tenant, pipeline_id=, owner_id=, territory_id=, currency=, date_from=, date_to=)` ·
`sales_competitor_rows(tenant, …same kwargs…)` · `sales_stage_age_rows(tenant, pipeline_id=, owner_id=,
territory_id=, currency=, date_from=, date_to=, health=, as_of=, placements=)` ·
`sales_pipeline_rollups(tenant, pipeline_id=, owner_id=, territory_id=, currency=, as_of=)` ·
`sales_pipeline_currency_totals(tenant, …)` · `sales_health_counts(tenant, opportunities=None, placements=None, *, as_of=None)`.

`apps/crm/analytics.py`:
**`compute_report(report)` is PUBLIC** — reach the funnel / top-performers figures through it with a
`crm.AnalyticsReport` whose `report_type` is `"funnel"` or `"sales_performance"` (both are valid
`REPORT_TYPE_CHOICES`). **Do NOT import the underscore-private `_compute_funnel` / `_compute_sales_performance`
across the app boundary.**

### Ownership ruling (L36/L37) — zero duplicate masters
8.12 declares **no** win/loss-reason table, **no** opportunity-outcome table, **no** competitor table,
**no** report/dashboard/widget/snapshot engine, **no** quota/period table, **no** activity master,
**no** call-rubric scorecard, **no** ledger, **no** currency table, **no** rep table, **no** benchmark master,
**no** funnel-stage table. It EXTENDS the above by FK.

### Number prefixes — verified free repo-wide
`WLA` (WinLossDebrief) · `VCA` (StageVelocityAnalysis) · `FNL` (FunnelConversionRecord) ·
`RPS` (RepPerformanceScorecard). **Taken, do not use:** `WLR`, `OUT`, `CSC`, `SCR`.

---

## 1. Entity 1 — `WinLossDebrief` [`WLA-`] — bullet 1 (Win/Loss Analysis)

### 1.1 Model — `apps/sales/models/SalesAnalytics/WinLossDebriefs.py`

```python
INTERVIEW_CHANNEL_CHOICES = [
    ("interview", "Interview"),
    ("survey", "Survey"),
    ("email_review", "Email Review"),
    ("internal_debrief", "Internal Debrief"),
    ("analysis", "Desk Analysis"),
]
FEEDBACK_TEAM_CHOICES = [
    ("product", "Product"), ("marketing", "Marketing"), ("sales", "Sales"),
    ("finance", "Finance"), ("operations", "Operations"), ("other", "Other"),
]
DEBRIEF_STATUS_CHOICES = [
    ("draft", "Draft"), ("submitted", "Submitted"), ("shared", "Shared with Team"),
    ("actioned", "Actioned"), ("closed", "Closed"),
]
```

`class WinLossDebrief(TenantNumbered)` — `NUMBER_PREFIX = "WLA"`.

| Field | Definition |
|---|---|
| `opportunity` | FK `"crm.Opportunity"`, `on_delete=models.PROTECT`, `related_name="sales_win_loss_debriefs"` |
| `outcome` | FK `"sales.OpportunityOutcome"`, `PROTECT`, `null=True, blank=True`, `related_name="sales_win_loss_debriefs"` |
| `primary_reason` | FK `"sales.WinLossReason"`, `PROTECT`, `null=True, blank=True`, `related_name="sales_win_loss_debriefs"` |
| `account` | FK `"core.Party"`, `SET_NULL`, `null=True, blank=True`, `related_name="sales_win_loss_debrief_accounts"` |
| `interviewer` | FK `settings.AUTH_USER_MODEL`, `SET_NULL`, `null=True, blank=True`, `related_name="sales_win_loss_debrief_interviewers"` |
| `action_owner` | FK `settings.AUTH_USER_MODEL`, `SET_NULL`, `null=True, blank=True`, `related_name="sales_win_loss_debrief_action_owners"` |
| `communication_log` | FK `"crm.CommunicationLog"`, `SET_NULL`, `null=True, blank=True`, `related_name="sales_win_loss_debriefs"` |
| `debriefed_on` | `DateField(default=timezone.localdate)` |
| `interview_channel` | `CharField(max_length=20, choices=INTERVIEW_CHANNEL_CHOICES, default="interview")` |
| `decision_drivers` | `JSONField(default=list, blank=True)` — `[{"driver": str, "sentiment": "positive"\|"negative", "weight": int 1–5, "quote": str}]` |
| `buyer_quote` | `TextField(blank=True)` |
| `counterfactual` | `TextField(blank=True)` |
| `feedback_team` | `CharField(max_length=20, choices=FEEDBACK_TEAM_CHOICES, default="sales")` |
| `action_items` | `TextField(blank=True)` |
| `actioned_on` | `DateField(null=True, blank=True)` |
| `status` | `CharField(max_length=12, choices=DEBRIEF_STATUS_CHOICES, default="draft")` |
| `notes` | `TextField(blank=True)` |

- `Meta.ordering = ["-debriefed_on", "-created_at"]`
- `Meta.constraints`:
  - `UniqueConstraint(fields=["tenant", "number"], name="sales_wla_tenant_number_uniq")`
  - `UniqueConstraint(fields=["tenant", "opportunity"], name="sales_wla_tenant_opp_uniq")` — one debrief per deal.
- `Meta.indexes`:
  - `Index(fields=["tenant", "status"], name="sales_wla_tenant_status_idx")`
  - `Index(fields=["tenant", "feedback_team"], name="sales_wla_tenant_fb_idx")`
- `__str__` → `f"{self.number or 'WLA'} · {self.opportunity}"` (guard the None opportunity).
- `clean()` — every FK must belong to the same tenant: `opportunity`, `outcome`, `primary_reason`, `account`,
  `interviewer`, `action_owner`, `communication_log`. Raise `ValidationError({field: "…"})` per field.
  Follow the `OpportunityOutcome.clean()` pattern (`_relation_belongs_to_tenant` style helper).
  Additional rule: when `outcome_id` is set, `outcome.opportunity_id` must equal `opportunity_id`.
- Properties (used by templates — keep the names exact):
  - `status_badge_class` → `draft→badge-muted`, `submitted→badge-info`, `shared→badge-slate`, `actioned→badge-amber`, `closed→badge-green`, default `badge-slate`
  - `channel_badge_class` → `interview→badge-info`, `survey→badge-slate`, `email_review→badge-muted`, `internal_debrief→badge-slate`, `analysis→badge-slate`, default `badge-slate`
  - `feedback_badge_class` → `product→badge-purple`… **no — `badge-purple` does not exist.** Use only the approved set: `product→badge-info`, `marketing→badge-info`, `sales→badge-slate`, `finance→badge-muted`, `operations→badge-muted`, `other→badge-muted`, default `badge-slate`.
  - `is_open` → `status in {"draft", "submitted", "shared"}`
  - `driver_count` → `len(self.decision_drivers or [])`

> ⚠ `OpportunityOutcome` is **append-only** (`save()` raises when not adding; `delete()` raises). That is why
> `outcome` is `PROTECT` — a cascade delete would try to delete an immutable row. Never call `.delete()` on it.

### 1.2 Form — `apps/sales/forms/SalesAnalytics/WinLossDebriefs.py`
`class WinLossDebriefForm(TenantUniqueMixin, TenantModelForm)`

- `Meta.model = WinLossDebrief`
- `Meta.fields` = `["opportunity", "outcome", "primary_reason", "account", "interviewer", "action_owner",
  "communication_log", "debriefed_on", "interview_channel", "decision_drivers", "buyer_quote", "counterfactual",
  "feedback_team", "action_items", "actioned_on", "status", "notes"]`
- `Meta.widgets`: selects → `{"class": "form-select"}`; `debriefed_on` / `actioned_on` →
  `forms.DateInput(attrs={"class": "form-input", "type": "date"})`; `buyer_quote` / `counterfactual` /
  `action_items` / `notes` → `forms.Textarea(attrs={"class": "form-textarea", "rows": 3})`;
  `decision_drivers` → `forms.Textarea(attrs={"class": "form-textarea", "rows": 4, "placeholder": '[{"driver": "…", "sentiment": "negative", "weight": 4, "quote": "…"}]'})`.
  `TenantModelForm` already sets `form-select` / `form-textarea` / `form-input` defaults — do not fight it.
- `__init__`: `TenantUniqueMixin` stamps `tenant`. FK querysets are auto-scoped by `TenantModelForm`
  (it filters `tenant=` on any model that has a `tenant` field) — do not re-filter.
- `clean_decision_drivers(self, value)`: `value` is the parsed JSON (Django's `forms.JSONField` already
  rejects malformed JSON). Require: a `list`; each item a `dict` with a non-empty `driver` `str`;
  `sentiment` in `{"positive", "negative"}`; `weight` an `int` 1–5 (absent `weight` → default 1);
  `quote` optional `str`. Raise `ValidationError` with a clear message on any violation.
- `clean()`: call `super().clean()` then `_reject_foreign(self, cleaned_data, ["opportunity", "outcome",
  "primary_reason", "account", "interviewer", "action_owner", "communication_log"])`
  (`_reject_foreign` is imported from `apps.sales.forms._common`).

### 1.3 Views — `apps/sales/views/SalesAnalytics/WinLossDebriefs.py`
5 views, named exactly:

| View function | URL name | Method |
|---|---|---|
| `win_loss_debrief_list` | `win_loss_debrief_list` | GET |
| `win_loss_debrief_detail` | `win_loss_debrief_detail` | GET |
| `win_loss_debrief_create` | `win_loss_debrief_create` | GET/POST |
| `win_loss_debrief_edit` | `win_loss_debrief_edit` | GET/POST |
| `win_loss_debrief_delete` | `win_loss_debrief_delete` | POST only |

**`win_loss_debrief_list`** — queryset
`WinLossDebrief.objects.filter(tenant=request.tenant).select_related("opportunity", "account", "primary_reason", "interviewer", "action_owner")`.
- search `q` → `Q(opportunity__name__icontains=q) | Q(number__icontains=q) | Q(buyer_quote__icontains=q) | Q(action_items__icontains=q) | Q(notes__icontains=q)`
- filters, each applied **before** pagination: `status` (exact), `interview_channel` (exact),
  `feedback_team` (exact), `opportunity` (int, `.isdigit()` guard), `reason` (int, `.isdigit()` guard → `primary_reason_id`).
- `stats = qs.aggregate(total_count=Count("id"), open_count=Count("id", filter=Q(status__in=["draft","submitted","shared"])), actioned_count=Count("id", filter=Q(status="actioned")), closed_count=Count("id", filter=Q(status="closed")))`
- `paginator = Paginator(qs, 15)`; `page_obj = paginator.get_page(request.GET.get("page"))`
- **Context keys (exact):** `debriefs` (= `page_obj.object_list`), `page_obj`, `q`, `status_choices`,
  `interview_channel_choices`, `feedback_team_choices`, `opportunities`, `outcomes`, `reasons`, `accounts`,
  `interviewers`, `action_owners`, `stats`, `active_filters`.
  - `opportunities` = `crm.Opportunity.objects.filter(tenant=request.tenant).order_by("name")`
  - `outcomes` = `sales.OpportunityOutcome.objects.filter(tenant=request.tenant).select_related("opportunity").order_by("-closed_at")`
  - `reasons` = `sales.WinLossReason.objects.filter(tenant=request.tenant, is_active=True).order_by("sequence", "name")`
  - `accounts` = `core.Party.objects.filter(tenant=request.tenant, roles__role="customer", roles__status="active").distinct().order_by("name")`
    — `PartyRole.party` has `related_name="roles"` and `PartyRole.role` holds `"customer"` ✓ (verified).
  - `interviewers` = `action_owners` = `User.objects.filter(tenant=request.tenant, is_active=True).order_by("username")`
  - `active_filters` = `{"q": q, "status": status, "interview_channel": channel, "opportunity": opportunity_id, "reason": reason_id}` (omit the `feedback_team` key only if the template does not use it — the template **does** use it, so include `"feedback_team": feedback_team`).
- render `sales/salesanalytics/winlossdebrief/list.html`

**`win_loss_debrief_detail`** — `get_object_or_404(WinLossDebrief.objects.filter(tenant=request.tenant).select_related(...), pk=pk)`.
Context: `{"obj": obj, "debrief": obj}`. Render `sales/salesanalytics/winlossdebrief/detail.html`.

**`win_loss_debrief_create`** — `form = WinLossDebriefForm(request.POST, tenant=request.tenant)`; on valid →
`obj = form.save()`; `write_audit_log(request.user, obj, "create", f"…", tenant=request.tenant)`;
`messages.success(...)`; `redirect("sales:win_loss_debrief_detail", pk=obj.pk)`.
Context `{"form": form, "obj": None, "is_edit": False}`. Render `…/form.html`.

**`win_loss_debrief_edit`** — same, with `instance=obj`; context `{"form": form, "obj": obj, "is_edit": True}`.

**`win_loss_debrief_delete`** — `@require_POST` + `@tenant_admin_required`; get_object_or_404; audit `"delete"`;
`obj.delete()`; `messages.success`; `redirect("sales:win_loss_debrief_list")`.

### 1.4 URLs — `apps/sales/urls/SalesAnalytics/WinLossDebriefs.py`
```
sales-analytics/win-loss-debriefs/            → win_loss_debrief_list
sales-analytics/win-loss-debriefs/create/     → win_loss_debrief_create
sales-analytics/win-loss-debriefs/<int:pk>/   → win_loss_debrief_detail
sales-analytics/win-loss-debriefs/<int:pk>/edit/   → win_loss_debrief_edit
sales-analytics/win-loss-debriefs/<int:pk>/delete/ → win_loss_debrief_delete
```
Literal routes before `<int:pk>`.

### 1.5 Templates — `templates/sales/salesanalytics/winlossdebrief/`
`list.html`, `detail.html`, `form.html` — the exact page/field/filter set is in §6.

---

## 2. Entity 2 — `StageVelocityAnalysis` [`VCA-`] — bullet 2 (Sales Velocity & Cycle Time)

### 2.1 Model — `apps/sales/models/SalesAnalytics/StageVelocityAnalyses.py`

```python
VELOCITY_STATUS_CHOICES = [("draft", "Draft"), ("reviewed", "Reviewed"), ("approved", "Approved")]
```

`class StageVelocityAnalysis(TenantNumbered)` — `NUMBER_PREFIX = "VCA"`.

| Field | Definition |
|---|---|
| `pipeline` | FK `"sales.Pipeline"`, `PROTECT`, `related_name="sales_velocity_analyses"` |
| `pipeline_stage` | FK `"sales.PipelineStage"`, `PROTECT`, `related_name="sales_velocity_analyses"` |
| `period_start` | `DateField()` |
| `period_end` | `DateField()` |
| `opportunity_count` | `PositiveIntegerField(default=0)` |
| `median_days_in_stage` | `DecimalField(max_digits=8, decimal_places=2, default=0, validators=[MinValueValidator(0)])` |
| `p90_days_in_stage` | `DecimalField(max_digits=8, decimal_places=2, default=0, validators=[MinValueValidator(0)])` |
| `max_days_in_stage` | `PositiveIntegerField(default=0)` |
| `sales_cycle_days` | `DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)` |
| `velocity_value` | `DecimalField(max_digits=16, decimal_places=2, default=0, validators=[MinValueValidator(0)])` |
| `is_bottleneck` | `BooleanField(default=False)` |
| `bottleneck_rank` | `PositiveSmallIntegerField(null=True, blank=True)` |
| `recommendation` | `TextField(blank=True)` |
| `benchmark_days` | `DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)` |
| `benchmark_source` | `CharField(max_length=120, blank=True)` |
| `benchmark_as_of` | `DateField(null=True, blank=True)` |
| `segment` | `CharField(max_length=40, blank=True)` |
| `status` | `CharField(max_length=12, choices=VELOCITY_STATUS_CHOICES, default="draft")` |
| `notes` | `TextField(blank=True)` |

- **There is deliberately NO `avg_days_in_stage` field.** A right-skewed duration distribution is reported as
  **median and p90**; a plain average invites a reader to treat a mean as typical. Do not add one.
- `Meta.ordering = ["-period_end", "-period_start", "pipeline", "pipeline_stage"]`
- `Meta.constraints`:
  - `UniqueConstraint(fields=["tenant", "number"], name="sales_vca_tenant_number_uniq")`
  - `UniqueConstraint(fields=["tenant", "pipeline_stage", "period_start"], name="sales_vca_stage_period_uniq")`
- `Meta.indexes`:
  - `Index(fields=["tenant", "status"], name="sales_vca_tenant_status_idx")`
  - `Index(fields=["tenant", "is_bottleneck"], name="sales_vca_tenant_bneck_idx")` — ⚠ Django caps an index
    name at **30 characters** (`models.E034`); the obvious `sales_vca_tenant_bottleneck_idx` is 32 and is rejected.
  - `Index(fields=["tenant", "pipeline"], name="sales_vca_tenant_pipeline_idx")`
- `clean()`: `pipeline_stage.pipeline_id == pipeline_id` (the stage must belong to the selected pipeline);
  tenant checks for `pipeline`, `pipeline_stage`; `period_end >= period_start`.
- Properties:
  - `status_badge_class` → `draft→badge-muted`, `reviewed→badge-info`, `approved→badge-green`, default `badge-slate`
  - `bottleneck_badge_class` → `badge-red` if `is_bottleneck` else `badge-muted`
  - `days_over_target` → `self.median_days_in_stage - self.pipeline_stage.target_days` when
    `pipeline_stage.target_days` is not `None` and `pipeline_stage_id` is set, else `None`
  - `is_over_target` → `days_over_target is not None and days_over_target > 0`

> **Document in the model docstring:** there is no stage-transition history table in NavERP, so
> historical per-stage durations are **not derivable** — `median_days_in_stage` / `p90_days_in_stage` /
> `max_days_in_stage` are the **persisted, recorded measurement** for the period (the record's own data,
> hence editable). `is_bottleneck` and `bottleneck_rank` are a manager's judgement (the stage's
> `target_days` is nullable and a rank is relative to sibling rows) — the console re-derives a **live**
> rank at render time and shows it beside the stored snapshot; the stored rank is the judgement at entry
> time. This is gap `GAP-sales-8.12-01`.

### 2.2 Form — `apps/sales/forms/SalesAnalytics/StageVelocityAnalyses.py`
`class StageVelocityAnalysisForm(TenantUniqueMixin, TenantModelForm)`
- `Meta.fields` = `["pipeline", "pipeline_stage", "period_start", "period_end", "opportunity_count",
  "median_days_in_stage", "p90_days_in_stage", "max_days_in_stage", "sales_cycle_days", "velocity_value",
  "is_bottleneck", "bottleneck_rank", "recommendation", "benchmark_days", "benchmark_source",
  "benchmark_as_of", "segment", "status", "notes"]`
- Widgets: selects → `form-select`; dates → `DateInput(type=date)`; numerics → `NumberInput` with
  `{"class": "form-input", "step": "0.01"}` for decimals and `{"class": "form-input", "min": 0}` for integers;
  `recommendation` / `notes` → `Textarea(rows=3)`; `is_bottleneck` → `CheckboxInput`.
- `clean()`: `_reject_foreign(self, cleaned_data, ["pipeline", "pipeline_stage"])`.
- `clean_pipeline_stage(self, value)`: if `value` and the cleaned `pipeline` is set and
  `value.pipeline_id != cleaned_data["pipeline"].pk` → raise
  `ValidationError("Choose a stage from the selected pipeline.")`.

### 2.3 Views — `apps/sales/views/SalesAnalytics/StageVelocityAnalyses.py`
| View function | URL name |
|---|---|
| `stage_velocity_analysis_list` | `stage_velocity_analysis_list` |
| `stage_velocity_analysis_detail` | `stage_velocity_analysis_detail` |
| `stage_velocity_analysis_create` | `stage_velocity_analysis_create` |
| `stage_velocity_analysis_edit` | `stage_velocity_analysis_edit` |
| `stage_velocity_analysis_delete` | `stage_velocity_analysis_delete` |

**`stage_velocity_analysis_list`**
- queryset `StageVelocityAnalysis.objects.filter(tenant=request.tenant).select_related("pipeline", "pipeline_stage")`
- search `q` → `Q(number__icontains=q) | Q(pipeline__name__icontains=q) | Q(pipeline_stage__name__icontains=q) | Q(recommendation__icontains=q) | Q(notes__icontains=q)`
- filters: `status` (exact), `pipeline` (int, `.isdigit()`), `pipeline_stage` (int, `.isdigit()`), and
  `bottleneck` (`"1"`/`"true"` → `is_bottleneck=True`).
- `stats = qs.aggregate(total_count=Count("id"), bottleneck_count=Count("id", filter=Q(is_bottleneck=True)), draft_count=Count("id", filter=Q(status="draft")), reviewed_count=Count("id", filter=Q(status="reviewed")), approved_count=Count("id", filter=Q(status="approved")))`
- **Context keys (exact):** `analyses` (= `page_obj.object_list`), `page_obj`, `q`, `status_choices`,
  `pipelines`, `pipeline_stages`, `stats`, `active_filters`.
  - `pipelines` = `sales.Pipeline.objects.filter(tenant=request.tenant, is_active=True).order_by("name")`
  - `pipeline_stages` = `sales.PipelineStage.objects.filter(tenant=request.tenant, is_active=True).select_related("pipeline").order_by("pipeline__name", "sequence")`
  - `active_filters` = `{"q": q, "status": status, "pipeline": pipeline_id, "pipeline_stage": stage_id, "bottleneck": bottleneck}`
- render `sales/salesanalytics/stagevelocityanalysis/list.html`

**detail** — context `{"obj": obj, "analysis": obj}`.
**create** — context `{"form": form, "obj": None, "is_edit": False}`.
**edit** — context `{"form": form, "obj": obj, "is_edit": True}`.
**delete** — POST-only, tenant-admin, audit, redirect to list.

### 2.4 URLs — `apps/sales/urls/SalesAnalytics/StageVelocityAnalyses.py`
```
sales-analytics/stage-velocity/                → stage_velocity_analysis_list
sales-analytics/stage-velocity/create/         → stage_velocity_analysis_create
sales-analytics/stage-velocity/<int:pk>/       → stage_velocity_analysis_detail
sales-analytics/stage-velocity/<int:pk>/edit/  → stage_velocity_analysis_edit
sales-analytics/stage-velocity/<int:pk>/delete/→ stage_velocity_analysis_delete
```

### 2.5 Templates — `templates/sales/salesanalytics/stagevelocityanalysis/{list,detail,form}.html`

---

## 3. Entity 3 — `FunnelConversionRecord` [`FNL-`] — bullet 3 (Conversion Funnel Analytics)

### 3.1 Model — `apps/sales/models/SalesAnalytics/FunnelConversionRecords.py`

```python
FUNNEL_SCOPE_CHOICES = [
    ("lead_to_opportunity", "Lead to Opportunity"),
    ("opportunity_to_close", "Opportunity to Close"),
    ("stage_to_stage", "Stage to Stage"),
    ("overall", "Overall"),
]
```

`class FunnelConversionRecord(TenantNumbered)` — `NUMBER_PREFIX = "FNL"`.

| Field | Definition |
|---|---|
| `label` | `CharField(max_length=160)` |
| `funnel_scope` | `CharField(max_length=24, choices=FUNNEL_SCOPE_CHOICES, default="lead_to_opportunity")` |
| `from_stage` | FK `"sales.PipelineStage"`, `SET_NULL`, `null=True, blank=True`, `related_name="sales_funnel_from_records"` |
| `to_stage` | FK `"sales.PipelineStage"`, `SET_NULL`, `null=True, blank=True`, `related_name="sales_funnel_to_records"` |
| `territory` | FK `"crm.Territory"`, `SET_NULL`, `null=True, blank=True`, `related_name="sales_funnel_records"` |
| `owner` | FK `settings.AUTH_USER_MODEL`, `SET_NULL`, `null=True, blank=True`, `related_name="sales_funnel_records"` |
| `source_channel` | `CharField(max_length=60, blank=True)` |
| `period_start` | `DateField()` |
| `period_end` | `DateField()` |
| `entered_count` | `PositiveIntegerField(default=0)` |
| `converted_count` | `PositiveIntegerField(default=0)` |
| `conversion_rate_pct` | `DecimalField(max_digits=5, decimal_places=2, editable=False, default=0)` |
| `dropoff_count` | `PositiveIntegerField(editable=False, default=0)` |
| `skipped_count` | `PositiveIntegerField(default=0)` |
| `avg_cycle_days` | `DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)` |
| `benchmark_pct` | `DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)` |
| `benchmark_source` | `CharField(max_length=120, blank=True)` |
| `benchmark_as_of` | `DateField(null=True, blank=True)` |
| `segment` | `CharField(max_length=40, blank=True)` |
| `notes` | `TextField(blank=True)` |

- `save()` — **compute the two derived fields**:
  ```python
  entered = int(self.entered_count or 0)
  converted = int(self.converted_count or 0)
  self.conversion_rate_pct = (
      (Decimal(converted) / Decimal(entered) * Decimal(100)).quantize(Decimal("0.01"))
      if entered > 0 else Decimal("0.00")
  )
  self.dropoff_count = max(0, entered - converted)
  ```
  Use `from decimal import Decimal, ROUND_HALF_UP` and `quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)`.
  Both are `editable=False`, so Django's `ModelForm` excludes them automatically — but still list them
  explicitly as excluded in the form's `Meta.exclude` for clarity.
- `clean()`: `converted_count <= entered_count` (else
  `ValidationError({"converted_count": "Converted count cannot exceed the entered count."})`);
  `period_end >= period_start`; tenant checks for `from_stage`, `to_stage`, `territory`, `owner`;
  when `funnel_scope == "stage_to_stage"` and both stages are set →
  `to_stage.sequence > from_stage.sequence` (else
  `ValidationError({"to_stage": "The destination stage must follow the source stage."})`).
- `Meta.ordering = ["-period_end", "-period_start", "label"]`
- `Meta.constraints`:
  - `UniqueConstraint(fields=["tenant", "number"], name="sales_fnl_tenant_number_uniq")`
  - `UniqueConstraint(fields=["tenant", "label", "period_start"], name="sales_fnl_label_period_uniq")`
- `Meta.indexes`:
  - `Index(fields=["tenant", "funnel_scope"], name="sales_fnl_tenant_scope_idx")`
  - `Index(fields=["tenant", "period_end"], name="sales_fnl_tenant_period_idx")`
- Properties:
  - `scope_badge_class` → `lead_to_opportunity→badge-info`, `opportunity_to_close→badge-slate`,
    `stage_to_stage→badge-amber`, `overall→badge-muted`, default `badge-slate`
  - `is_below_benchmark` → `benchmark_pct is not None and conversion_rate_pct < benchmark_pct`
  - `benchmark_gap_pct` → `conversion_rate_pct - benchmark_pct` when a benchmark is set, else `None`

### 3.2 Form — `apps/sales/forms/SalesAnalytics/FunnelConversionRecords.py`
`class FunnelConversionRecordForm(TenantUniqueMixin, TenantModelForm)`
- `Meta.fields` = `["label", "funnel_scope", "from_stage", "to_stage", "territory", "owner", "source_channel",
  "period_start", "period_end", "entered_count", "converted_count", "skipped_count", "avg_cycle_days",
  "benchmark_pct", "benchmark_source", "benchmark_as_of", "segment", "notes"]`
- `Meta.exclude` = `["conversion_rate_pct", "dropoff_count"]` (belt-and-braces; they are `editable=False`).
- `clean()`: `_reject_foreign(self, cleaned_data, ["from_stage", "to_stage", "territory", "owner"])`.
- `clean()` also re-checks `converted_count <= entered_count` with a friendly message (the model's
  `clean()` is not called by a ModelForm, so the form must enforce it).

### 3.3 Views — `apps/sales/views/SalesAnalytics/FunnelConversionRecords.py`
| View function | URL name |
|---|---|
| `funnel_conversion_record_list` | `funnel_conversion_record_list` |
| `funnel_conversion_record_detail` | `funnel_conversion_record_detail` |
| `funnel_conversion_record_create` | `funnel_conversion_record_create` |
| `funnel_conversion_record_edit` | `funnel_conversion_record_edit` |
| `funnel_conversion_record_delete` | `funnel_conversion_record_delete` |

**`funnel_conversion_record_list`**
- queryset `FunnelConversionRecord.objects.filter(tenant=request.tenant).select_related("from_stage", "to_stage", "territory", "owner")`
- search `q` → `Q(label__icontains=q) | Q(number__icontains=q) | Q(source_channel__icontains=q) | Q(notes__icontains=q)`
- filters: `funnel_scope` (exact), `from_stage` (int, `.isdigit()`), `to_stage` (int, `.isdigit()`),
  `territory` (int, `.isdigit()`), `owner` (int, `.isdigit()`).
- `stats = qs.aggregate(total_count=Count("id"), avg_conversion_rate_pct=Avg("conversion_rate_pct"), total_dropoff=Sum("dropoff_count"), below_benchmark_count=Count("id", filter=Q(benchmark_pct__isnull=False) & ...))`
  — the `below_benchmark` comparison is a row-wise `conversion_rate_pct < benchmark_pct`, which Django's
  aggregate filter cannot express. Compute it with a separate `qs.filter(benchmark_pct__isnull=False)
  .extra(where=["conversion_rate_pct < benchmark_pct"]).count()` — or, simpler and portable, iterate the
  (already paginated) rows. Use the `.extra()` form with a **literal column expression, never user input**.
  Prefer:
  ```python
  below = qs.filter(benchmark_pct__isnull=False).filter(conversion_rate_pct__lt=F("benchmark_pct")).count()
  ```
  `F("benchmark_pct")` is a DB-side comparison — no SQL injection risk, and it works on MariaDB.
  Build `stats` as a plain dict: `total_count`, `avg_conversion_rate_pct`, `total_dropoff`, `below_benchmark_count`.
- **Context keys (exact):** `records` (= `page_obj.object_list`), `page_obj`, `q`, `scope_choices`,
  `from_stages`, `to_stages`, `territories`, `owners`, `stats`, `active_filters`.
  - `from_stages` / `to_stages` = `sales.PipelineStage.objects.filter(tenant=request.tenant, is_active=True).select_related("pipeline").order_by("pipeline__name", "sequence")`
  - `territories` = `crm.Territory.objects.filter(tenant=request.tenant).order_by("name")`
  - `owners` = `User.objects.filter(tenant=request.tenant, is_active=True).order_by("username")`
  - `active_filters` = `{"q": q, "funnel_scope": scope, "from_stage": from_id, "to_stage": to_id, "territory": territory_id, "owner": owner_id}`
- render `sales/salesanalytics/funnelconversionrecord/list.html`

**detail** — context `{"obj": obj, "record": obj}`.
**create** — `{"form": form, "obj": None, "is_edit": False}`.
**edit** — `{"form": form, "obj": obj, "is_edit": True}`.
**delete** — POST-only, tenant-admin, audit, redirect to list.

### 3.4 URLs — `apps/sales/urls/SalesAnalytics/FunnelConversionRecords.py`
```
sales-analytics/funnel-records/                → funnel_conversion_record_list
sales-analytics/funnel-records/create/         → funnel_conversion_record_create
sales-analytics/funnel-records/<int:pk>/       → funnel_conversion_record_detail
sales-analytics/funnel-records/<int:pk>/edit/  → funnel_conversion_record_edit
sales-analytics/funnel-records/<int:pk>/delete/→ funnel_conversion_record_delete
```

### 3.5 Templates — `templates/sales/salesanalytics/funnelconversionrecord/{list,detail,form}.html`

---

## 4. Entity 4 — `RepPerformanceScorecard` [`RPS-`] — bullet 4 (Rep Performance Scorecards) + measurement half of bullet 5

### 4.1 Model — `apps/sales/models/SalesAnalytics/RepPerformanceScorecards.py`

```python
SCORECARD_RATING_CHOICES = [
    ("outstanding", "Outstanding"), ("strong", "Strong"), ("on_track", "On Track"),
    ("needs_improvement", "Needs Improvement"), ("underperforming", "Underperforming"),
]
SCORECARD_STATUS_CHOICES = [
    ("draft", "Draft"), ("shared", "Shared"), ("acknowledged", "Acknowledged"), ("approved", "Approved"),
]
```

`class RepPerformanceScorecard(TenantNumbered)` — `NUMBER_PREFIX = "RPS"`.

| Field | Definition |
|---|---|
| `rep` | FK `settings.AUTH_USER_MODEL`, `PROTECT`, `related_name="sales_rep_scorecards"` |
| `territory` | FK `"crm.Territory"`, `SET_NULL`, `null=True, blank=True`, `related_name="sales_rep_scorecards"` |
| `manager` | FK `settings.AUTH_USER_MODEL`, `SET_NULL`, `null=True, blank=True`, `related_name="sales_managed_rep_scorecards"` |
| `forecast_period` | FK `"sales.ForecastPeriod"`, `SET_NULL`, `null=True, blank=True`, `related_name="sales_rep_scorecards"` |
| `quota_plan` | FK `"sales.QuotaPlan"`, `SET_NULL`, `null=True, blank=True`, `related_name="sales_rep_scorecards"` |
| `coaching_scorecard` | FK `"sales.CoachingScorecard"`, `SET_NULL`, `null=True, blank=True`, `related_name="sales_rep_scorecards"` |
| `period_start` | `DateField()` |
| `period_end` | `DateField()` |
| `activities_logged` | `PositiveIntegerField(default=0)` |
| `calls_logged` | `PositiveIntegerField(default=0)` |
| `emails_logged` | `PositiveIntegerField(default=0)` |
| `meetings_logged` | `PositiveIntegerField(default=0)` |
| `meetings_booked` | `PositiveIntegerField(default=0)` |
| `follow_ups_completed` | `PositiveIntegerField(default=0)` |
| `activity_minutes` | `PositiveIntegerField(default=0)` |
| `response_time_hours` | `DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)` |
| `opportunities_created` | `PositiveIntegerField(default=0)` |
| `opportunities_won` | `PositiveIntegerField(default=0)` |
| `opportunities_lost` | `PositiveIntegerField(default=0)` |
| `pipeline_value` | `DecimalField(max_digits=16, decimal_places=2, default=0, validators=[MinValueValidator(0)])` |
| `weighted_pipeline_value` | `DecimalField(max_digits=16, decimal_places=2, default=0, validators=[MinValueValidator(0)])` |
| `win_rate_pct` | `DecimalField(max_digits=5, decimal_places=2, editable=False, default=0)` |
| `revenue_closed` | `DecimalField(max_digits=16, decimal_places=2, default=0, validators=[MinValueValidator(0)])` |
| `currency` | FK `"accounting.Currency"`, `SET_NULL`, `null=True, blank=True`, `related_name="sales_rep_scorecards"` |
| `average_deal_size` | `DecimalField(max_digits=14, decimal_places=2, editable=False, default=0)` |
| `sales_cycle_days` | `DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)` |
| `quota_target` | `DecimalField(max_digits=16, decimal_places=2, default=0, validators=[MinValueValidator(0)])` |
| `quota_attainment_pct` | `DecimalField(max_digits=6, decimal_places=2, editable=False, default=0)` |
| `goal_gap_value` | `DecimalField(max_digits=16, decimal_places=2, editable=False, default=0)` |
| `overall_score` | `DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)` |
| `rating` | `CharField(max_length=20, choices=SCORECARD_RATING_CHOICES, default="on_track")` |
| `strengths` | `TextField(blank=True)` |
| `areas_for_improvement` | `TextField(blank=True)` |
| `coaching_actions` | `TextField(blank=True)` |
| `benchmark_win_rate_pct` | `DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)` |
| `benchmark_cycle_days` | `DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)` |
| `benchmark_quota_attainment_pct` | `DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)` |
| `benchmark_source` | `CharField(max_length=120, blank=True)` |
| `benchmark_as_of` | `DateField(null=True, blank=True)` |
| `segment` | `CharField(max_length=40, blank=True)` |
| `status` | `CharField(max_length=12, choices=SCORECARD_STATUS_CHOICES, default="draft")` |
| `notes` | `TextField(blank=True)` |

- `save()` — **compute the four derived fields** (all `editable=False`):
  ```python
  won = int(self.opportunities_won or 0)
  lost = int(self.opportunities_lost or 0)
  revenue = Decimal(self.revenue_closed or 0)
  quota = Decimal(self.quota_target or 0)
  self.win_rate_pct = (Decimal(won) / Decimal(won + lost) * Decimal(100)).quantize(Decimal("0.01"), ROUND_HALF_UP) if (won + lost) else Decimal("0.00")
  self.average_deal_size = (revenue / Decimal(won)).quantize(Decimal("0.01"), ROUND_HALF_UP) if won else Decimal("0.00")
  self.quota_attainment_pct = (revenue / quota * Decimal(100)).quantize(Decimal("0.01"), ROUND_HALF_UP) if quota > 0 else Decimal("0.00")
  self.goal_gap_value = (quota - revenue).quantize(Decimal("0.01"), ROUND_HALF_UP)
  ```
  `goal_gap_value` is **negative when the target is exceeded** — that is the intended sign (gap = target − actual).
- `clean()`: tenant checks for `rep`, `territory`, `manager`, `forecast_period`, `quota_plan`, `coaching_scorecard`;
  `period_end >= period_start`; `opportunities_won + opportunities_lost` need not be bounded.
- `Meta.ordering = ["-period_end", "-period_start", "rep"]`
- `Meta.constraints`:
  - `UniqueConstraint(fields=["tenant", "number"], name="sales_rps_tenant_number_uniq")`
  - `UniqueConstraint(fields=["tenant", "rep", "period_start"], name="sales_rps_rep_period_uniq")`
- `Meta.indexes`:
  - `Index(fields=["tenant", "status"], name="sales_rps_tenant_status_idx")`
  - `Index(fields=["tenant", "rating"], name="sales_rps_tenant_rating_idx")`
  - `Index(fields=["tenant", "rep"], name="sales_rps_tenant_rep_idx")`
- Properties:
  - `rating_badge_class` → `outstanding→badge-green`, `strong→badge-green`, `on_track→badge-info`,
    `needs_improvement→badge-amber`, `underperforming→badge-red`, default `badge-slate`
  - `status_badge_class` → `draft→badge-muted`, `shared→badge-slate`, `acknowledged→badge-info`,
    `approved→badge-green`, default `badge-slate`
  - `goal_gap_badge_class` → `badge-green` when `goal_gap_value <= 0` (target met/exceeded),
    `badge-amber` when positive but within 10%, `badge-red` otherwise, default `badge-slate`
  - `is_on_track` → `rating in {"outstanding", "strong", "on_track"}`
  - `total_activities` → sum of the six activity counters

> **Document in the model docstring:** the activity counters are the period's **recorded evidence**
> (editable). The console shows the **live** `sales.ActivityLog`-derived counts **beside** the stored
> snapshot so any divergence is visible — it never overwrites the stored snapshot. Leading indicators =
> the activity block; lagging indicators = the outcome block. The scorecard is **single-currency**;
> `crm.Opportunity.currency` is per-opportunity, so a cross-currency leaderboard needs FX rates NavERP
> does not hold (`GAP-sales-8.12-11`).

### 4.2 Form — `apps/sales/forms/SalesAnalytics/RepPerformanceScorecards.py`
`class RepPerformanceScorecardForm(TenantUniqueMixin, TenantModelForm)`
- `Meta.fields` = `["rep", "territory", "manager", "forecast_period", "quota_plan", "coaching_scorecard",
  "period_start", "period_end", "activities_logged", "calls_logged", "emails_logged", "meetings_logged",
  "meetings_booked", "follow_ups_completed", "activity_minutes", "response_time_hours",
  "opportunities_created", "opportunities_won", "opportunities_lost", "pipeline_value",
  "weighted_pipeline_value", "revenue_closed", "currency", "sales_cycle_days", "quota_target",
  "overall_score", "rating", "strengths", "areas_for_improvement", "coaching_actions",
  "benchmark_win_rate_pct", "benchmark_cycle_days", "benchmark_quota_attainment_pct", "benchmark_source",
  "benchmark_as_of", "segment", "status", "notes"]`
- `Meta.exclude` = `["win_rate_pct", "average_deal_size", "quota_attainment_pct", "goal_gap_value"]`.
- `clean()`: `_reject_foreign(self, cleaned_data, ["rep", "territory", "manager", "forecast_period",
  "quota_plan", "coaching_scorecard"])`.
- Widgets: selects → `form-select`; dates → `DateInput(type=date)`; decimals → `NumberInput(step="0.01")`;
  integers → `NumberInput(min=0)`; text blocks → `Textarea(rows=3)`.

### 4.3 Views — `apps/sales/views/SalesAnalytics/RepPerformanceScorecards.py`
| View function | URL name |
|---|---|
| `rep_performance_scorecard_list` | `rep_performance_scorecard_list` |
| `rep_performance_scorecard_detail` | `rep_performance_scorecard_detail` |
| `rep_performance_scorecard_create` | `rep_performance_scorecard_create` |
| `rep_performance_scorecard_edit` | `rep_performance_scorecard_edit` |
| `rep_performance_scorecard_delete` | `rep_performance_scorecard_delete` |

**`rep_performance_scorecard_list`**
- queryset `RepPerformanceScorecard.objects.filter(tenant=request.tenant).select_related("rep", "territory", "manager", "currency", "quota_plan", "forecast_period")`
- search `q` → `Q(number__icontains=q) | Q(rep__username__icontains=q) | Q(rep__first_name__icontains=q) | Q(rep__last_name__icontains=q) | Q(strengths__icontains=q) | Q(notes__icontains=q)`
  — ✓ VERIFIED: `accounts.User` has real DB columns `first_name` (max 150) and `last_name` (max 150)
  (`apps/accounts/models.py:74-75`), so both are legitimate ORM lookups on a related field.
- filters: `status` (exact), `rating` (exact), `rep` (int, `.isdigit()`), `territory` (int, `.isdigit()`),
  `forecast_period` (int, `.isdigit()`).
- `stats` (plain dict): `total_count` (Count), `avg_win_rate_pct` (Avg over `win_rate_pct`),
  `total_revenue_closed` (Sum over `revenue_closed`), `avg_quota_attainment_pct` (Avg over
  `quota_attainment_pct`), `on_track_count` (Count with `filter=Q(rating__in=["outstanding","strong","on_track"])`).
- **Context keys (exact):** `scorecards` (= `page_obj.object_list`), `page_obj`, `q`, `status_choices`,
  `rating_choices`, `reps`, `territories`, `managers`, `currencies`, `quota_plans`, `forecast_periods`,
  `stats`, `active_filters`.
  - `reps` = `User.objects.filter(tenant=request.tenant, is_active=True).order_by("username")`
  - `managers` = same queryset
  - `territories` = `crm.Territory.objects.filter(tenant=request.tenant).order_by("name")`
  - `currencies` = `accounting.Currency.objects.all().order_by("code")` — **Currency is GLOBAL (no tenant
    FK); do not filter it by tenant.**
  - `quota_plans` = `sales.QuotaPlan.objects.filter(tenant=request.tenant).order_by("-created_at")`
    — ⚠ **`QuotaPlan` has NO `name` field** (it has `quota_ref`, `forecast_period`, `owner`, `territory`,
    `method`, `target_type`, `phasing`, `parameters`, `status`, `is_active`). Ordering by `"name"` raises
    `FieldError` → 500. Order by `-created_at`.
  - `forecast_periods` = `sales.ForecastPeriod.objects.filter(tenant=request.tenant).order_by("-start_date")`
  - `active_filters` = `{"q": q, "status": status, "rating": rating, "rep": rep_id, "territory": territory_id, "forecast_period": period_id}`
- render `sales/salesanalytics/repperformancescorecard/list.html`

**detail** — context `{"obj": obj, "scorecard": obj}`.
**create** — `{"form": form, "obj": None, "is_edit": False}`.
**edit** — `{"form": form, "obj": obj, "is_edit": True}`.
**delete** — POST-only, tenant-admin, audit, redirect to list.

### 4.4 URLs — `apps/sales/urls/SalesAnalytics/RepPerformanceScorecards.py`
```
sales-analytics/scorecards/                → rep_performance_scorecard_list
sales-analytics/scorecards/create/         → rep_performance_scorecard_create
sales-analytics/scorecards/<int:pk>/       → rep_performance_scorecard_detail
sales-analytics/scorecards/<int:pk>/edit/  → rep_performance_scorecard_edit
sales-analytics/scorecards/<int:pk>/delete/→ rep_performance_scorecard_delete
```

### 4.5 Templates — `templates/sales/salesanalytics/repperformancescorecard/{list,detail,form}.html`

---

## 5. Consoles — 6 derived read-only pages, **no new models**

File: `apps/sales/views/SalesAnalytics/AnalyticsConsoles.py`
Templates: `templates/sales/salesanalytics/boards/<name>.html`

| View function | URL name | Path | Helper(s) rendered over |
|---|---|---|---|
| `analytics_console` | `analytics_console` | `sales-analytics/` | `sales_health_counts` + `sales_pipeline_rollups` |
| `win_loss_console` | `win_loss_console` | `sales-analytics/win-loss/` | `sales_win_loss_rows` + `sales_competitor_rows` |
| `velocity_console` | `velocity_console` | `sales-analytics/velocity/` | `sales_stage_age_rows` + `sales_pipeline_rollups` |
| `funnel_console` | `funnel_console` | `sales-analytics/funnel/` | **`crm.analytics.compute_report(report)`** on a saved `crm.AnalyticsReport` with `report_type="funnel"` + the FNL- records |
| `rep_scorecard_console` | `rep_scorecard_console` | `sales-analytics/rep-scorecards/` | RPS- rows + a `sales.ActivityLog` aggregate + `compute_report` on `report_type="sales_performance"` |
| `benchmark_console` | `benchmark_console` | `sales-analytics/benchmarks/` | RPS-/FNL-/VCA- benchmark fields + `sales.QuotaPlan` |

Rules:
- Each console view's **module-level docstring must name the existing helper it renders over**.
- Every figure is computed **at render time**. Nothing is stored. A console must never write.
- All consoles are `@login_required` and tenant-scoped.
- **If a helper raises or returns nothing, the console must degrade gracefully** — catch `Exception` around
  the optional helper call and render an empty table with an explanatory message, never a 500. The funnel
  console in particular depends on a `crm.AnalyticsReport` row existing; if none exists for the tenant,
  create none and render an explanatory empty state.
- For `compute_report`, build the report **in memory** if the tenant has no saved report:
  ```python
  from apps.crm.models import AnalyticsReport
  from apps.crm.analytics import compute_report
  report = AnalyticsReport(tenant=request.tenant, name="8.12 Funnel", report_type="funnel", date_range="last_90")
  payload = compute_report(report)
  ```
  `compute_report` reads `report.tenant`, `report.report_type`, `report.date_range`, `report.group_by` —
  inspect `apps/crm/analytics.py::compute_report` and `range_bounds` to confirm the exact attributes it
  needs, and make sure every one of them has a value on the in-memory instance (an unsaved instance has
  `group_by` defaulting to `"month"`, which is fine).
- **Pinned context keys** (a console that renders blank is a failure):

| Console | Context keys |
|---|---|
| `analytics_console` | `stats` (dict: `total_debriefs`, `total_velocity_analyses`, `total_funnel_records`, `total_scorecards`, `open_feedback_actions`, `pipeline_health`), `bullet_links` (list of `{"label": str, "url": str}` for the five bullets), `recent_debriefs`, `recent_analyses` |
| `win_loss_console` | `stats`, `win_loss_rows`, `competitor_rows`, `driver_rows`, `open_actions`, `result_choices` |
| `velocity_console` | `stats`, `stage_age_rows`, `rollup_rows`, `bottleneck_rows`, `aging_rows` |
| `funnel_console` | `stats`, `funnel_rows`, `funnel_report`, `benchmark_rows` |
| `rep_scorecard_console` | `stats`, `scorecard_rows`, `leaderboard`, `team_rollup`, `activity_totals`, `percentile_bands` |
| `benchmark_console` | `stats`, `peer_rows`, `percentile_bands`, `benchmark_rows`, `goal_gap_rows` |

- `bullet_links` entries are `{"label": "Win/Loss Analysis", "url": reverse("sales:win_loss_console")}` etc.
  — build them with `reverse()`, never a hard-coded path.
- `result_choices` = `sales.OpportunityOutcome.RESULT_CHOICES` (a list of `(value, label)` tuples).
- `driver_rows` = the recurring decision drivers aggregated from `WinLossDebrief.decision_drivers`
  (count the `driver` strings across the tenant's debriefs, sort by count desc, cap at 20).
- `bottleneck_rows` = the VCA- rows, with a **live** rank re-derived at render time and shown **beside** the
  stored `bottleneck_rank`.
- `percentile_bands` = the median / 75th / 90th percentile of the RPS- rows' `win_rate_pct` (computed in
  Python over the row values — the row count is small).

---

## 6. Template specifications

### 6.1 Every list page
Structure (matching the 8.11 / 8.13 sibling pages):
1. `{% extends "base.html" %}` and `{% block content %}`.
2. `.page-header` with `.page-title` and a `.breadcrumb`.
3. `.stat-grid` of `.stat-card` blocks — one per `stats` key, using `.stat-icon` with only
   `blue` / `green` / `orange` / `purple` / `slate`.
4. A `.card > .card-body` containing a `<form method="get" class="filter-bar">` with **one control per
   declared filter**, each reflecting `request.GET`, plus Apply and Reset.
   - text filters: `<input type="search" name="q" value="{{ q }}" class="form-input">`
   - choice filters: `<select name="status" class="form-select">` with
     `{% if request.GET.status == "draft" %}selected{% endif %}` for a string choice, and
     `{% if request.GET.opportunity == r.pk|stringformat:"d" %}selected{% endif %}` for an FK.
   - **Every `<select>` must have a `<label for="...">` and a matching `id` on the control** — a filter
     with no label is a review finding.
5. A `.table-wrap > table.table` with an **Actions column** (view = eye icon, edit = pencil icon,
   delete = bin icon). The delete control is a **POST form** with `{% csrf_token %}` and
   `onclick="return confirm('…')"`. Wrap Edit/Delete in a `{% if %}` on status where the status makes the
   action invalid.
6. `{% empty %}` → a `.empty-state` block.
7. `{% include "partials/pagination.html" %}` — check how that partial expects the page object before
   relying on it; if it is not driven by `page_obj`, render the pagination links inline with
   `{% if page_obj.has_previous %}` / `{% if page_obj.has_next %}` guards (L9).

### 6.2 Every detail page
- An **Actions sidebar**: Edit link (conditional on status where applicable), a **POST** delete form with
  `confirm()` + `{% csrf_token %}` (conditional), and a Back-to-List link.
- The full field set, with every nullable FK guarded by `{% if %}` (L10).
- The **derived** read-outs (`conversion_rate_pct`, `dropoff_count`, `win_rate_pct`, `average_deal_size`,
  `quota_attainment_pct`, `goal_gap_value`) shown as read-only values, never as form inputs.

### 6.3 Every form page
- `{% csrf_token %}`, the form fields, Save / Cancel.
- Render form errors with `{{ form.errors }}` / per-field `{{ field.errors }}`.
- Derived fields are **not** inputs.

---

## 7. Shared-file edits — surgical, additive, single-writer, re-read before editing

| File | Change |
|---|---|
| `apps/sales/models/__init__.py` | Add `from .SalesAnalytics.WinLossDebriefs import …` etc. (4 import lines) **after** the 8.13 block, plus the 4 model names **and** the 8 CHOICES constants to `__all__`. |
| `apps/sales/forms/__init__.py` | Add the 8.12 form import block after the 8.13 block + the 4 form names to `__all__`. |
| `apps/sales/views/__init__.py` | Add `from .SalesAnalytics import (…)` with the 4 entity view modules' names + the 6 console names, **and** extend the `__all__` prefix tuple with: `"win_loss_debrief_"`, `"stage_velocity_analysis_"`, `"funnel_conversion_record_"`, `"rep_performance_scorecard_"`, `"analytics_console"`, `"win_loss_console"`, `"velocity_console"`, `"funnel_console"`, `"rep_scorecard_console"`, `"benchmark_console"`. |
| `apps/sales/urls/__init__.py` | Add `from .SalesAnalytics import urlpatterns as _sales_analytics` **and** splice `*_sales_analytics` into `urlpatterns`. |
| `apps/sales/admin.py` | Register the 4 models. |
| `apps/sales/management/commands/seed_sales.py` | Append a `_seed_sales_analytics(self, tenant, owner)` method + **one** call in `_seed_tenant` after `_seed_marketing_alignment(...)`. Do not restructure the existing command. |
| `apps/core/navigation.py` | Add ONE `LIVE_LINKS["8.12"]` entry (see §8). |
| `templates/sales/overview.html` | Add one link to `sales:analytics_console` in the page-actions bar. (⚠ the real file is `templates/sales/overview.html` — there is **no** `templates/sales/sales_overview.html`; it is the module landing page for 8.1 Lead Operations.) |

### Seeder rules
- Reuse the **existing** `crm.Opportunity` / `crm.Lead` / `core.Party` (customer) / `sales.Pipeline` /
  `sales.PipelineStage` / `sales.QuotaPlan` / `sales.ForecastPeriod` / `accounts.User` rows — create **none**
  of them. If a required master is missing for a tenant, print a warning and skip that tenant's rows.
- Idempotency keys: WLA `(tenant, opportunity)` · VCA `(tenant, pipeline_stage, period_start)` ·
  FNL `(tenant, label, period_start)` · RPS `(tenant, rep, period_start)`. Use `get_or_create` or an
  existence check so the second run yields **identical counts**.
- At least **one** row per model per tenant, with realistic values (a debrief with decision drivers, a
  velocity analysis for a stage, a funnel record, a scorecard for a rep).

---

## 8. `LIVE_LINKS["8.12"]` — the single navigation entry

Insert into `apps/core/navigation.py` in the `LIVE_LINKS` dict, positioned to keep the 8.x keys in
NavERP.md order (after the `"8.11"` block, before `"8.13"`).

```python
    # 8.12 Sales Analytics & Intelligence
    # OWNERSHIP RULING (L36/L37): EXTENDS (never redeclares) Sales 8.2 WinLossReason (WLR-) +
    # OpportunityOutcome (OUT-); links Sales 8.9 CoachingScorecard (CSC-) by FK. Reuses
    # crm.Opportunity (OPP-), crm.Lead (LEAD-), crm.Territory, crm.CommunicationLog (COM-),
    # crm.AnalyticsReport / AnalyticsDashboard / DashboardWidget / ReportSnapshot (CRM 1.6
    # report engine), sales.Pipeline (PIPE-) / PipelineStage (target_days) /
    # OpportunityPipelinePlacement (stage_entered_at), sales.ActivityLog (SAL-) / ActivityType,
    # sales.QuotaPlan (QPA-), sales.ForecastPeriod, core.Party, accounting.Currency and
    # accounts.User. The six consoles render over apps/sales/opportunity_analytics.py and
    # apps/crm/analytics.py. Zero duplicate reason, outcome, report, widget, quota, currency,
    # activity, competitor or coaching-scorecard models declared.
    "8.12": {
        "Win/Loss Analysis": "sales:win_loss_console",
        "Sales Velocity & Cycle Time": "sales:velocity_console",
        "Conversion Funnel Analytics": "sales:funnel_console",
        "Rep Performance Scorecards": "sales:rep_scorecard_console",
        "Benchmarking & Peer Comparison": "sales:benchmark_console",
        # Extra live leaves
        "Sales Analytics Console": "sales:analytics_console",
        "Win/Loss Debriefs": "sales:win_loss_debrief_list",
        "Stage Velocity Analyses": "sales:stage_velocity_analysis_list",
        "Funnel Conversion Records": "sales:funnel_conversion_record_list",
        "Rep Scorecard Records": "sales:rep_performance_scorecard_list",
    },
```

> ⚠ **No duplicate dict key.** The bullet `"Rep Performance Scorecards"` and the extra leaf must have
> **different labels** — the extra leaf is `"Rep Scorecard Records"`. A repeated key silently drops one
> entry from the sidebar.
>
> The five bullet keys are the **verbatim** NavERP.md texts; the sidebar looks the key up by bullet text.

---

## 9. Verification gates

- [ ] `venv\Scripts\python.exe manage.py makemigrations sales` → `0024_salesanalytics.py`
      (**re-verify the number first**, L43)
- [ ] `venv\Scripts\python.exe manage.py migrate`
- [ ] `venv\Scripts\python.exe manage.py seed_sales` ×2 → identical counts
- [ ] `venv\Scripts\python.exe manage.py check` → 0 issues
- [ ] `venv\Scripts\python.exe manage.py makemigrations --check --dry-run` → `No changes detected`
- [ ] All **26** new url names reverse (no `NoReverseMatch`)
- [ ] Smoke sweep as `admin_acme` / `password` (`temp/` script, gitignored):
      4 list + 4 detail + 4 create + 4 edit + 6 console pages → 200;
      each list page contains its seeded record (`WLA-…`, `VCA-…`, `FNL-…`, `RPS-…`);
      each console contains its KPI labels **and a non-empty table**;
      every pinned context key is populated (filter dropdowns non-empty, `stats` renders numbers);
      ≥7 hostile query strings (incl. `?page=999`, `?status=nope`, `?opportunity=abc`,
      `?opportunity=999999999999999999999`) on every list page and console → **no 500**;
      page 2 → 200 on all 4 list pages;
      **cross-tenant IDOR** → an `admin_globex` pk → **404** on the detail and edit routes of all 4 models;
      zero `{#` / `{% comment` markers in any rendered page (L2);
      zero `badge-success|badge-danger|badge-warning|badge-purple|stat-icon amber|stat-icon red` (L33)
- [ ] Sidebar: 8.12 shows **5 bullets + 5 extra leaves**, all Live, and the five bullets resolve to
      **five distinct** hrefs (L30)
- [ ] `.agents/tasks/gaps-sales-8.12.md` created and linked from the close-out block
