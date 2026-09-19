# Contract — NavERP 7.16 Reporting & Business Intelligence (app `projects`, existing app)

**Part A: models + forms.** Part B (urls / views / context / templates) is appended by a second agent.
Source of truth: `.claude/tasks/todo.md` §7.16 (from line 8737) and `.claude/tasks/research-projects-7.16.md`.
Style template: `apps/projects/models/FinancialBillingManagement/*.py` (7.15) and
`apps/projects/models/_base.py` (`TenantOwned` / `TenantNumbered` / `NUMBER_PREFIX`).

## A0 — Package layout and imports

**Folder:** `ReportingBusinessIntelligence/` (NavERP.md `### 7.16 Reporting & Business Intelligence`, `&`
dropped) in all four packages, matching the verified siblings `AgileScrumManagement/`,
`ClientExternalCollaboration/`, `PortfolioProgramManagement/`, `FinancialBillingManagement/`.

**Final model-file split (4 entity modules + 1 shared choices module — decided, not deferred):**

| Path | Contents | Models |
|---|---|---|
| `apps/projects/models/ReportingBusinessIntelligence/_choices.py` | the ONE vocabulary module; no models | — |
| `apps/projects/models/ReportingBusinessIntelligence/ProjectReports.py` | `ProjectReport` | 1 |
| `apps/projects/models/ReportingBusinessIntelligence/ReportRuns.py` | `ProjectReportRun` | 1 |
| `apps/projects/models/ReportingBusinessIntelligence/ProjectDashboards.py` | `ProjectDashboard` | 1 |
| `apps/projects/models/ReportingBusinessIntelligence/DashboardWidgets.py` | `DashboardWidget` | 1 |
| `apps/projects/models/ReportingBusinessIntelligence/__init__.py` | **intentionally EMPTY of re-exports** (verbatim `models/FinancialBillingManagement/__init__.py` convention) | — |

**Parent + child file decision (the one CLAUDE.md leaves open for 7.16):** `ProjectDashboard` and
`DashboardWidget` get **two files, not one**. Justification: (a) the plan names both paths explicitly;
(b) the closest analogue in the repo, `apps/crm/models/AnalyticsReporting/`, splits `Dashboards.py` /
`Widgets.py` the same way; (c) `DashboardWidget` is the only model whose `clean()`/form rule depends on
`analytics` (the metric↔chart pair), so keeping it in its own file keeps that dependency edge in one place.
CLAUDE.md rule 2 ("an entity file owns the primary model plus its children") is satisfied in spirit — the
child is not scattered across files, it has exactly one.

**Imports (match 7.15 exactly — this is the app's newest convention, not the older `import *`):**

```python
# apps/projects/models/ReportingBusinessIntelligence/ProjectReports.py
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.projects.models._base import TenantNumbered          # ProjectReport
from apps.projects.models.ReportingBusinessIntelligence._choices import (
    REPORT_TYPE_CHOICES, SUBJECT_CHOICES, MEASURE_CHOICES, DIMENSION_CHOICES,
    RANGE_CHOICES, CHART_CHOICES,
)
```

* All imports ABSOLUTE — never `from .models import …` (CLAUDE.md backend rule 4).
* `TenantNumbered` / `TenantOwned` live in `apps/projects/models/_base.py` (verified: `TenantOwned`
  = `tenant` FK CASCADE `related_name="+"` `db_index=True` + `created_at`/`updated_at`;
  `TenantNumbered` adds `NUMBER_PREFIX` + `number = CharField(max_length=20, editable=False)` and the
  5-attempt `next_number` retry-on-`IntegrityError` `save()`). **Do not re-implement `save()` for
  numbering** — 7.15's `save()` overrides only *quantize money*; 7.16 has no money column, so
  `ProjectReport` / `ProjectDashboard` declare **no `save()` at all** and inherit the base's auto-number.
* `ProjectReportRun` and `DashboardWidget` are plain `models.Model` with their own `tenant` FK (verbatim
  `crm.DashboardWidget` / `procurement.SpendReportSnapshot`), so they import `models`, `settings`,
  `ValidationError` directly — never `TenantOwned`.
* `apps/projects/analytics.py` is imported by **forms and views only**; models NEVER import it
  (one-way edge, 6.14 ruling). This is what decides where the metric↔chart rule lives — see A2.
  Verified this pass: the file **does not exist yet** (`ls apps/projects/analytics.py` → no such file), so
  `WIDGET_METRICS` / `allowed_charts` / `STANDARD_REPORTS` are authored in this build; Part A pins only the
  key spellings they must use. Chart.js 4.4.1 is confirmed global at `templates/base.html:28`.
* Sub-package re-export block to append later (Integrate step, not Part A):
  `from apps.projects.models.ReportingBusinessIntelligence.ProjectReports import ProjectReport` etc. into
  `apps/projects/models/__init__.py` under a `# --- 7.16 Reporting & Business Intelligence` header.

## A1 — Models

### A1.0 `ProjectReport`

`class ProjectReport(TenantNumbered)` · `NUMBER_PREFIX = "REP"` · table `projects_projectreport` ·
**23 declared fields** (+ the 4 inherited `tenant` / `number` / `created_at` / `updated_at` = 27 columns).
`REP` and `PDB` verified unused: `grep -rn 'NUMBER_PREFIX = "REP"\|NUMBER_PREFIX = "PDB"' apps/` → 0 hits,
and neither token appears in the app's 60-prefix inventory (`PRT`=Portfolio, `DSH`=DocumentShare,
`PRJ`=Project, `RTC`, `PPR`, … are the neighbours 7.16 must not collide with).

| # | field | type | args (exact) |
|---|---|---|---|
| 1 | `name` | `CharField` | `max_length=120` |
| 2 | `description` | `TextField` | `blank=True` |
| 3 | `report_type` | `CharField` | `max_length=24, choices=REPORT_TYPE_CHOICES, default="status_report"` |
| 4 | `subject` | `CharField` | `max_length=24, choices=SUBJECT_CHOICES, default="project"` |
| 5 | `measures` | `JSONField` | `default=list, blank=True` — 1–3 keys from `MEASURE_CHOICES` (validated in `clean()`, never a DB constraint) |
| 6 | `dimension_1` | `CharField` | `max_length=20, choices=DIMENSION_CHOICES, default="project"` |
| 7 | `dimension_2` | `CharField` | `max_length=20, choices=DIMENSION_CHOICES, default="none"` |
| 8 | `date_range` | `CharField` | `max_length=10, choices=RANGE_CHOICES, default="last_90"` |
| 9 | `date_from` | `DateField` | `null=True, blank=True` |
| 10 | `date_to` | `DateField` | `null=True, blank=True` |
| 11 | `as_of` | `DateField` | `null=True, blank=True` |
| 12 | `project` | `FK "projects.Project"` | `on_delete=SET_NULL, null=True, blank=True, related_name="project_reports"` |
| 13 | `portfolio` | `FK "projects.Portfolio"` | `on_delete=SET_NULL, null=True, blank=True, related_name="project_reports"` |
| 14 | `client` | `FK "core.Party"` | `on_delete=SET_NULL, null=True, blank=True, related_name="project_reports"` |
| 15 | `org_unit` | `FK "core.OrgUnit"` | `on_delete=SET_NULL, null=True, blank=True, related_name="project_reports"` |
| 16 | `chart_type` | `CharField` | `max_length=10, choices=CHART_CHOICES, default="table"` |
| 17 | `top_n` | `PositiveSmallIntegerField` | `default=20, validators=[MinValueValidator(1), MaxValueValidator(100)]` |
| 18 | `sort_by` | `CharField` | `max_length=24, blank=True` — a `MEASURE_CHOICES` key; validated in `clean()` (a free-text column keeps the axes frozen without a parser) |
| 19 | `notes` | `TextField` | `blank=True` |
| 20 | `is_favorite` | `BooleanField` | `default=False` |
| 21 | `is_shared` | `BooleanField` | `default=False` — **private unless shared** (matches `crm.AnalyticsDashboard`, and it is the ACL claim `visible_reports()` reads) |
| 22 | `owner` | `FK settings.AUTH_USER_MODEL` | `on_delete=SET_NULL, null=True, blank=True, related_name="project_reports"` |
| 23 | `last_run_at` | `DateTimeField` | `null=True, blank=True, editable=False` — system-stamped by `rep_run` / `rep_freeze` ONLY, never on page open |

`related_name="project_reports"` is used on **all five** owners (4 scope FKs + `owner`) deliberately: it is
grep-free app-wide (`grep -rn 'related_name="project_reports"' apps/` → 0 hits), and one name per owning
model is what `procurement.SpendReport` does with `procurement_spend_reports`.

**Class-attribute choice mirrors** (so templates/admin can read `ProjectReport.MEASURE_CHOICES` the way
`procurement.SpendReport` does): `REPORT_TYPE_CHOICES`, `SUBJECT_CHOICES`, `MEASURE_CHOICES`,
`DIMENSION_CHOICES`, `RANGE_CHOICES`, `CHART_CHOICES` — each assigned from `_choices.py`.

```python
class Meta:
    ordering = ["-is_favorite", "name"]
    unique_together = ("tenant", "number")
    indexes = [
        models.Index(fields=["tenant", "report_type"], name="rep_tnt_type_idx"),
        models.Index(fields=["tenant", "is_shared"], name="rep_tnt_share_idx"),
    ]
```

* All seven 7.16 index names verified free: `grep -rn "<name>" apps/` → 0 hits for `rep_tnt_type_idx`,
  `rep_tnt_share_idx`, `run_tnt_gen_idx`, `run_tnt_rep_idx`, `pdb_tnt_own_idx`, `pdb_tnt_share_idx`,
  `wdg_tnt_dash_idx` (index names are DB-global, hence the `rep_`/`run_`/`pdb_`/`wdg_` prefixes rather than
  crm's `crm_rpt_*`).
* **`ordering` correction:** the plan says `["name"]`; the code convention for a saved-report register is
  `["-is_favorite", "name"]` (`crm.AnalyticsReport`, `procurement.SpendReport` — both verified). Pinned as
  `["-is_favorite", "name"]`; see A3.

`__str__`: `return f"{self.number} · {self.name}"` — the `·` separator is 7.15/crm house style
(`procurement.SpendReport` uses `" - "`; the projects app's newest modules use `·`).

**`save()`**: none. `TenantNumbered.save()` already does the concurrent-collision retry —
`for _ in range(5): self.number = next_number(type(self), self.tenant, self.NUMBER_PREFIX)` inside a
`transaction.atomic()` with `IntegrityError → self.number = ""` — which is exactly the "7.15 mechanics" the
plan asks for; 7.15's own `save()` overrides exist only to `q2()` money, which 7.16 has none of.

**`clean()` rules (model is the ONLY home for these — no analytics import needed to evaluate them):**

1. `measures` must be a non-empty list of ≤ 3 entries, each a key of `MEASURE_CHOICES`
   (`errors["measures"] = "Pick between 1 and 3 measures."` / `"Unknown measure: <key>."`).
2. `date_range == "custom"` ⇒ BOTH `date_from` and `date_to` are required
    ("A custom range needs a start date." / "…an end date."). For every other non-`all` value the pair is
    an **override**: either both set or both blank (a half-entered window is meaningless).
    `date_range == "all"` ⇒ both bounds must be BLANK ("An all-time report cannot carry a window.").
3. `date_from` and `date_to` both set ⇒ `date_from <= date_to`
   (`"The start date cannot be after the end date."`).
4. **Window ≤ 730 days** when both bounds are set: `(self.date_to - self.date_from).days > 730` ⇒ error on
   `date_to` (`"A report window cannot span more than 730 days."`) — Teamwork's two-year cap.
5. `as_of` set and both bounds set ⇒ `date_from <= as_of <= date_to`
   (`"The as-of date must fall inside the window."`). `as_of` blank on a non-`all` range is fine — the
   preset resolves to "now" at compute time.
6. `dimension_1 == dimension_2 and dimension_1 != "none"` ⇒ error on `dimension_2`
   (`"Pick a different second dimension, or set it to none."`).
7. `sort_by` non-blank ⇒ must be a key of `MEASURE_CHOICES`.
8. Scope-FK tenancy: for `project`, `portfolio`, `client`, `org_unit` —
   `if chosen_id and tenant_id and getattr(self, field).tenant_id != tenant_id:` ⇒
   `errors[field] = f"That {label} belongs to another workspace."` (verbatim
   `procurement.SpendReport.clean()` loop). `core.Party`, `core.OrgUnit`, `projects.Project`,
   `projects.Portfolio` all carry their own `tenant` FK (verified) so the check is safe for all four.
9. `report_type == "custom"` ⇒ `subject` must not be blank-empty and `measures` must be explicit (a canned
   kind carries its own axes from `analytics.STANDARD_REPORTS`).

Errors are collected into a dict and raised once as `ValidationError(errors)` — no `raise` inside the loop.

### A1.1 `ProjectReportRun`

`class ProjectReportRun(models.Model)` — **NOT `TenantNumbered`, NOT `TenantOwned`**: a plain `models.Model`
carrying its own `tenant` FK (verbatim `crm.ReportSnapshot` / `procurement.SpendReportSnapshot`, both
verified). Table `projects_projectreportrun`. **Unnumbered** — no `number`, no `NUMBER_PREFIX`; a run is
identified by `title` + `generated_at`, exactly like both precedents.
**17 declared fields.**

| # | field | type | args (exact) |
|---|---|---|---|
| 1 | `tenant` | `FK "core.Tenant"` | `on_delete=CASCADE, related_name="+", db_index=True` (verbatim base shape; lets `get_object_or_404(ProjectReportRun, pk=…, tenant=request.tenant)` work without walking the parent) |
| 2 | `report` | `FK "projects.ProjectReport"` | `on_delete=CASCADE, related_name="runs"` |
| 3 | `title` | `CharField` | `max_length=200` — the freeze copies `report.name`, so a re-titled parent never renames history |
| 4 | `period_from` | `DateField` | `null=True, blank=True` — the RESOLVED window at freeze time (a preset `last_90` is materialised here, which is the whole point of a frozen run) |
| 5 | `period_to` | `DateField` | `null=True, blank=True` |
| 6 | `as_of` | `DateField` | **required, no null** — `rep_freeze` always supplies it (`report.as_of or timezone.localdate()`), so every run records the instant it speaks for |
| 7 | `generated_by` | `FK settings.AUTH_USER_MODEL` | `on_delete=SET_NULL, null=True, blank=True, editable=False, related_name="+"` |
| 8 | `generated_at` | `DateTimeField` | `auto_now_add=True, editable=False` — the freeze instant; the ordering key; never rewritten |
| 9 | `updated_at` | `DateTimeField` | `auto_now=True, editable=False` — see the note below (deviation D5) |
| 10 | `summary` | `JSONField` | `default=dict, blank=True` — KPI cards `{label: value}` (a dict, not crm's list: `run_detail` and `exec_pack` look values up by label) |
| 11 | `data` | `JSONField` | `default=dict, blank=True` — `{columns, rows, chart_type, chart_labels, chart_data, caveats, truncated, rating}` exactly as `analytics.compute_report()` returns it; every value JSON-serialisable |
| 12 | `row_count` | `PositiveIntegerField` | `default=0` |
| 13 | `narrative` | `TextField` | `blank=True` — the only human-authored body text; pre-filled from `analytics.narrative_seed()`, editable while `draft` |
| 14 | `status` | `CharField` | `max_length=10, choices=RUN_STATUS_CHOICES, default="draft"` |
| 15 | `issued_by` | `FK settings.AUTH_USER_MODEL` | `on_delete=SET_NULL, null=True, blank=True, editable=False, related_name="+"` |
| 16 | `issued_at` | `DateTimeField` | `null=True, blank=True, editable=False` |
| 17 | `document` | `FK "core.Document"` | `on_delete=SET_NULL, null=True, blank=True, related_name="project_report_runs"` — set when the issued pack is filed against a `projects.DocumentTemplate` whose `category` is `report` or `status_update` (both verified present in `DocumentTemplate.CATEGORY_CHOICES`) |

* `generated_by` / `issued_by` both `related_name="+"`: two FKs to the same target on one model need distinct
  reverse names, and `+` suppresses both (matches the base's `tenant` choice). Verified free (nothing
  references them).
* `report` `related_name="runs"`: within `apps/projects` nothing uses `runs` yet; repo-wide the literal exists
  only on unrelated parents (`inventory` `StockSyncChannel`, and `widgets`-style children in crm/hrm). Django's
  reverse-name clash check is **per parent model**, so this cannot collide — see A3/D3 for the honest note.
* **Child cascade rule:** `report` CASCADE ⇒ deleting a saved report deletes its frozen history. `tenant`
  CASCADE ⇒ tenant purge deletes them too. No `PROTECT` anywhere on this model.

```python
class Meta:
    ordering = ["-generated_at", "-id"]          # the tie-breaker ruling — deterministic "latest"
    indexes = [
        models.Index(fields=["tenant", "generated_at"], name="run_tnt_gen_idx"),
        models.Index(fields=["tenant", "report"], name="run_tnt_rep_idx"),
    ]
```

⚠️ **`models.Index` takes plain field names, NOT the `"-generated_at"` ordering syntax** (that string is only
valid in `Meta.ordering`; passing it to `Index(fields=[…])` raises `ValueError` at import). A composite
`(tenant, generated_at)` index is scanned backwards by both SQLite and MySQL, so it serves the
`-generated_at` ordering just as well — which is why `procurement` pins `["tenant", "report"]` plain too.

No `unique_together` (a report legitimately freezes many times). No `constraints` — a frozen run's payload is
arbitrary JSON and the row has no natural business key.

`__str__`: `return f"{self.title} ({self.generated_at:%Y-%m-%d %H:%M})"` (verbatim both precedents).

**`save()`**: none — no numbering, no money. Do NOT add `auto_now` to `generated_at`.

**`clean()` rules (all evaluable without `analytics`):**

1. `period_from` and `period_to` both set ⇒ `period_from <= period_to`.
2. Window ≤ 730 days when both set (same cap as the parent question — a frozen run must not outlive the
   builder's own limit).
3. `as_of` must satisfy `period_from <= as_of <= period_to` when the bounds are present.
4. `document_id` set ⇒ `document.tenant_id == self.tenant_id` ("That document belongs to another workspace.").
5. `status` transitions are **not** validated in `clean()` — they are verb-gated in the views (`run_issue` is the
   only writer of `issued`/`issued_by`/`issued_at`; `run_archive` the only writer of `archived`). A model-level
   transition guard would fight the `.update()` calls that deliberately avoid touching `updated_at`.

**Write discipline (the freeze-only contract):** rows are minted exclusively by `rep_freeze` inside one
`transaction.atomic()` together with the parent's `last_run_at` stamp. There is **no create view, no edit
form, no builder form** for this model, exactly as `procurement.SpendReportSnapshot` documents. Later writes
are limited to `narrative` (draft only), `issue`, `archive`, and the admin-gated `delete`.
`run_detail` re-reads `summary` / `data` and recomputes NOTHING.

**RAG persistence lives here and nowhere else:** `analytics.rag_streak()` walks this series
(`-generated_at, -id`, `status="issued"`, reading `data["rating"]`) — that read-only dependency on stored rows
is the entire justification for the table.

### A1.2 `ProjectDashboard`

`class ProjectDashboard(TenantNumbered)` · `NUMBER_PREFIX = "PDB"` · table `projects_projectdashboard` ·
**10 declared fields** (+4 inherited = 14 columns). The container for bullet 3.

| # | field | type | args (exact) |
|---|---|---|---|
| 1 | `name` | `CharField` | `max_length=120` |
| 2 | `description` | `TextField` | `blank=True` |
| 3 | `owner` | `FK settings.AUTH_USER_MODEL` | `on_delete=SET_NULL, null=True, blank=True, related_name="project_dashboards"` — **`null` = a tenant-provided audience template nobody owns** |
| 4 | `audience` | `CharField` | `max_length=20, choices=AUDIENCE_CHOICES, default="pm"` |
| 5 | `default_range` | `CharField` | `max_length=10, choices=RANGE_CHOICES, default="last_90"` — overridable per request by `?range=` |
| 6 | `layout` | `CharField` | `max_length=5, choices=LAYOUT_CHOICES, default="two"` |
| 7 | `is_default` | `BooleanField` | `default=False` — the personalized home tile |
| 8 | `is_shared` | `BooleanField` | `default=False` |
| 9 | `project` | `FK "projects.Project"` | `on_delete=SET_NULL, null=True, blank=True, related_name="project_dashboards"` |
| 10 | `portfolio` | `FK "projects.Portfolio"` | `on_delete=SET_NULL, null=True, blank=True, related_name="project_dashboards"` |

`related_name="project_dashboards"` verified free repo-wide (0 hits), same reasoning as A1.0.

```python
class Meta:
    ordering = ["-is_default", "name"]           # matches crm.AnalyticsDashboard
    unique_together = ("tenant", "number")
    indexes = [
        models.Index(fields=["tenant", "owner"], name="pdb_tnt_own_idx"),
        models.Index(fields=["tenant", "is_shared"], name="pdb_tnt_share_idx"),
    ]
```

`__str__`: `return f"{self.number} · {self.name}"`.
**`save()`**: none — inherited auto-number. No money to quantize.

**Computed, not stored:**

* `widget_count` → `@property` returning `self.widgets.count()` (crm's exact shape). The **list** view uses
  `ProjectDashboard.objects.filter(...).annotate(annotation_count=Count("widgets"))` instead of the property,
  so a 25-row page does not fire 25 COUNT queries — pin both names (`widget_count` on the object,
  `annotation_count` in the annotation) because templates read whichever is in scope.
* No stored "health"/"budget" column of any kind.

**`clean()` rules:**

1. At most one default per owner:
   `ProjectDashboard.objects.filter(tenant_id, owner_id=self.owner_id, is_default=True).exclude(pk=self.pk).exists()`
   ⇒ `errors["is_default"] = "This workspace already has a default dashboard for that owner — unset the other one first."`
   (when `owner` is `None` the same query is run on `owner__isnull=True`).
2. `is_default=True` and `is_shared=False` and `owner is None` ⇒ error — an unowned tenant template must be
   shared, otherwise nothing on earth can ever resolve it in `pdb_home`.
3. Scope-FK tenancy for `project` and `portfolio` (same loop as A1.0 rule 8).
4. `default_range == "custom"` ⇒ error ("A dashboard window must be one of the presets — tiles have no date
   pair to resolve."). `RANGE_CHOICES` is shared with `ProjectReport`, so the `custom` key is legal there and
   illegal here; `DashboardWidget.date_range` carries the identical ban (A1.3 rule 4).

### A1.3 `DashboardWidget`

`class DashboardWidget(models.Model)` — **unnumbered child, plain `models.Model`, own `tenant` FK**
(verbatim `crm.models.AnalyticsReporting.Widgets.DashboardWidget`, which this name deliberately mirrors:
different app ⇒ different table `projects_dashboardwidget`). **13 declared fields.**

| # | field | type | args (exact) |
|---|---|---|---|
| 1 | `tenant` | `FK "core.Tenant"` | `on_delete=CASCADE, related_name="+", db_index=True` |
| 2 | `dashboard` | `FK "projects.ProjectDashboard"` | `on_delete=CASCADE, related_name="widgets"` |
| 3 | `title` | `CharField` | `max_length=120` |
| 4 | `metric` | `CharField` | `max_length=40, choices=WIDGET_METRIC_CHOICES, default="kpi_active_projects"` — keys must match `analytics.WIDGET_METRICS` EXACTLY |
| 5 | `chart_type` | `CharField` | `max_length=10, choices=CHART_CHOICES, default="kpi"` |
| 6 | `date_range` | `CharField` | `max_length=10, choices=RANGE_CHOICES, default="last_30"` |
| 7 | `size` | `CharField` | `max_length=10, choices=SIZE_CHOICES, default="medium"` |
| 8 | `position` | `PositiveIntegerField` | `default=0` — manual ordering; `wdg_move` swaps neighbours, `wdg_create` appends `max(position)+1` |
| 9 | `target_value` | `DecimalField` | `max_digits=14, decimal_places=2, null=True, blank=True` — progress-to-target for `kpi`/`gauge` only |
| 10 | `project` | `FK "projects.Project"` | `on_delete=SET_NULL, null=True, blank=True, related_name="+"` |
| 11 | `portfolio` | `FK "projects.Portfolio"` | `on_delete=SET_NULL, null=True, blank=True, related_name="+"` |
| 12 | `created_at` | `DateTimeField` | `auto_now_add=True` |
| 13 | `updated_at` | `DateTimeField` | `auto_now=True` |

* Scope FKs are `related_name="+"`: a tile narrows a project, it owns no relation anyone reverses. It also
  keeps the reverse-name space clean — `Project` already receives `project_reports` (A1.0) and
  `project_dashboards` (A1.2), both verified free repo-wide (0 hits each) before being pinned.
* `dashboard` `related_name="widgets"` mirrors crm and hrm exactly; reverse names are per-parent so no clash
  (A3/D3).
* **Tenancy is denormalised on purpose**: `widget.tenant` MUST equal `widget.dashboard.tenant`. `clean()`
  enforces it; `wdg_create` sets it from the parent. That is what lets a tile row be `get_object_or_404`'d by
  `pk, tenant=request.tenant` without a join, and it is what `CASCADE` on `dashboard` protects.

```python
class Meta:
    ordering = ["position", "id"]
    indexes = [
        models.Index(fields=["tenant", "dashboard"], name="wdg_tnt_dash_idx"),
    ]
```

No `unique_together` (two tiles may legitimately share a position after a delete; `wdg_move` renumbers).

`__str__`: `return f"{self.title} ({self.get_chart_type_display()})"`.
**`save()`**: none.

**`clean()` rules:**

1. Scope-FK tenancy for `project`, `portfolio` **and** `dashboard`
   (`dashboard.tenant_id != self.tenant_id` ⇒ "This dashboard belongs to another workspace.").
2. `target_value` is meaningful only for `kpi` / `gauge` ⇒ if set while `chart_type` is not in
   `("kpi", "gauge")`, drop it silently in `analytics` but **reject in the form**, not here — see A2 (the model
   has no business nulling user data).
3. **The metric↔chart pair is NOT here.** The valid chart set comes from `analytics.allowed_charts(metric)`,
   and models must not import analytics (one-way edge). The rule therefore lives in
   `DashboardWidgetForm.clean()` — mirroring `apps/crm/forms/AnalyticsReporting/Widgets.py:17–26`, which is the
   verified precedent. The model's `choices=WIDGET_METRIC_CHOICES` still refuses an unknown key at DB/form
   level, so the only gap is a directly-instantiated row in a shell.
4. `date_range == "custom"` ⇒ error — a tile has no date pair, so only the five presets plus `all` resolve
   (identical to A1.2 rule 4). `DashboardWidgetForm.__init__` also narrows
   `self.fields["date_range"].choices` to the presets so the dropdown never offers an option the model rejects;
   the `clean()` check stays as the non-form-writer guard.
5. `position` is never validated — `wdg_create` assigns `max(position) + 1` and `wdg_move` swaps neighbours.

### A1.4 Choices constants (complete literals)

All eleven constants live in `apps/projects/models/ReportingBusinessIntelligence/_choices.py` — the app's
FIRST per-sub-module `_choices.py` (convention verified 10× in the repo; closest precedent
`apps/crm/models/AnalyticsReporting/_choices.py`, which carries exactly this report/widget vocabulary).
They are **plain module-level lists of `(key, label)` 2-tuples**, imported by the entity modules with an
absolute import, AND re-exposed as class attributes on the model (both `procurement.SpendReport` and the
7.15 modules do this) so a view can hand `ProjectReport.MEASURE_CHOICES` straight to the template.

**The axes are FROZEN and code-defined. There is no formula parser, no user-authored expression, no
`MetricDefinition` table** — the `*_CHOICES` lists below plus `analytics.WIDGET_METRICS` ARE the semantic
layer. Adding an axis is a code change reviewed with the compute function that implements it; a builder
dropdown can never invent one. (Formula/calculated columns are parked to 7.19.)

`max_length` on each column is >= the longest key below (checked key-by-key); templates and tests compare the
**raw string key**, never the label.

```python
# apps/projects/models/ReportingBusinessIntelligence/_choices.py
"""Projects 7.16 Reporting & Business Intelligence — the frozen report/dashboard vocabulary.

One shared choices module for the whole sub-module: the builder, the tiles, the canned reports and the
templates all read the SAME list, so a report axis can never exist in one place and not another.
No models here. analytics.py mirrors these keys in its registries; models NEVER import analytics.
"""

# -- the window ---------------------------------------------------------------------------------
# `custom` is required by the builder's explicit date_from/date_to pair: without it the two date
# columns are unreachable (procurement.DATE_RANGE_CHOICES carries it for the same reason).
RANGE_CHOICES = [
    ("last_7", "Last 7 days"),
    ("last_30", "Last 30 days"),
    ("last_90", "Last 90 days"),
    ("quarter", "This quarter"),
    ("year", "This year"),
    ("all", "All time"),
    ("custom", "Custom range"),
]

# -- how a result renders -----------------------------------------------------------------------
# CANVAS kinds (Chart.js 4.4.1, already global in templates/base.html): bar, line, pie, doughnut.
# HTML kinds (NO canvas — a KPI card, gauge, table and heat band are markup): kpi, gauge, table, heat.
# analytics.allowed_charts(metric) is the authority on which pair; CHART_CHOICES only bounds the column.
CHART_CHOICES = [
    ("kpi", "KPI Card"),
    ("gauge", "Gauge"),
    ("bar", "Bar Chart"),
    ("line", "Line Chart"),
    ("pie", "Pie Chart"),
    ("doughnut", "Doughnut Chart"),
    ("table", "Table"),
    ("heat", "Heat Bands"),
]

# -- dashboard chrome ---------------------------------------------------------------------------
LAYOUT_CHOICES = [
    ("one", "Single column"),
    ("two", "Two columns"),
    ("three", "Three columns"),
]

SIZE_CHOICES = [
    ("small", "Small (quarter width)"),
    ("medium", "Medium (half width)"),
    ("large", "Large (three-quarter width)"),
    ("full", "Full width"),
]

# the real NavERP personas a tenant template is authored for (Dynamics role dashboards + the
# monday/Zoho template-gallery finding)
AUDIENCE_CHOICES = [
    ("pm", "Project Manager"),
    ("resource_manager", "Resource Manager"),
    ("finance", "Finance / PMO Costing"),
    ("quality", "Quality Manager"),
    ("agile_team", "Agile Team"),
    ("executive", "Executive / Steering Committee"),
    ("portfolio", "Portfolio Manager"),
]

# -- the canned report kinds (16) ---------------------------------------------------------------
# One entry per analytics.STANDARD_REPORTS key; "custom" is the builder's own kind.
# rbi_home's "50+ standard reports" answer is these 16 kinds x 4 scope axes, NOT 16 pages.
REPORT_TYPE_CHOICES = [
    ("status_report", "Project Status Report"),
    ("milestone_summary", "Milestone Summary"),
    ("schedule_variance", "Schedule Variance"),
    ("risk_register", "Risk Register"),
    ("issue_log", "Issue Log"),
    ("quality_defect_summary", "Quality & Defect Summary"),
    ("scope_change_summary", "Scope Change Summary"),
    ("cost_variance", "Cost Variance"),
    ("earned_value", "Earned Value (EVM)"),
    ("resource_utilization", "Resource Utilization"),
    ("time_entry", "Time Entry Detail"),
    ("billing_summary", "Billing Summary"),
    ("agile_throughput", "Agile Throughput / Velocity"),
    ("portfolio_health", "Portfolio Health"),
    ("steering_pack", "Executive & Steering Pack"),
    ("custom", "Custom (built with the report builder)"),
]

# -- what a report counts rows OF (16 registers) -------------------------------------------------
SUBJECT_CHOICES = [
    ("project", "Projects"),
    ("task", "Tasks & work items"),
    ("milestone", "Milestones"),
    ("requirement", "Requirements"),
    ("change_order", "Scope changes"),
    ("sprint", "Sprints"),
    ("time_entry", "Time entries"),
    ("resource_allocation", "Resource allocations"),
    ("cost", "Cost lines (7.4 cost control)"),
    ("invoice", "Project invoices (7.15)"),
    ("payment", "Payments received (7.15)"),
    ("risk", "Risks"),
    ("issue", "Issues"),
    ("quality_review", "Quality reviews"),
    ("defect", "Quality defects"),
    ("document", "Documents & lessons"),
]

# -- what a report measures (24, frozen) ---------------------------------------------------------
# The 15 ratio/variance/aging keys are the calculated columns Procore & Celoxis sell a formula
# editor for; here they are read-only keys backed by analytics, so the EVM maths stays in ONE place.
# Costs/EVM come from CostControlAccount's @property reads, billing from 7.15 rows — 7.16 stores NONE.
MEASURE_CHOICES = [
    ("planned_value", "Planned value (PV)"),
    ("earned_value", "Earned value (EV)"),
    ("actual_cost", "Actual cost (AC)"),
    ("budget_at_completion", "Budget at completion (BAC)"),
    ("eac", "Estimate at completion (EAC)"),
    ("cv", "Cost variance (CV)"),
    ("cv_pct", "Cost variance %"),
    ("sv", "Schedule variance (SV)"),
    ("sv_pct", "Schedule variance %"),
    ("cpi", "Cost performance index (CPI)"),
    ("spi", "Schedule performance index (SPI)"),
    ("margin_pct", "Margin % (invoiced vs actual cost)"),
    ("hours", "Hours booked"),
    ("billable_pct", "Billable %"),
    ("utilization_pct", "Utilization %"),
    ("task_count", "Tasks"),
    ("open_count", "Open items"),
    ("completed_count", "Completed items"),
    ("on_time_pct", "On-time %"),
    ("slip_days", "Schedule slip (days)"),
    ("exposure_value", "Risk exposure value"),
    ("aging_days", "Aging (days)"),
    ("unbilled_amount", "Unbilled amount"),
    ("invoiced_amount", "Invoiced amount"),
]

# -- how a report groups rows (18, incl. none) ---------------------------------------------------
# The plan's budget was 17 axes + `none`; `defect_severity` is split out of `severity` because the
# quality register's scale (critical/major/minor/trivial) is not the risk/issue scale.
DIMENSION_CHOICES = [
    ("project", "Project"),
    ("portfolio", "Portfolio"),
    ("client", "Client"),
    ("org_unit", "Department / cost centre"),
    ("resource", "Resource"),
    ("role", "Role"),
    ("activity_code", "Activity code"),
    ("wbs_phase", "WBS phase"),
    ("milestone_status", "Milestone status"),
    ("task_type", "Task type"),
    ("priority", "Priority"),
    ("status", "Status"),
    ("risk_category", "Risk category"),
    ("severity", "Severity"),
    ("defect_severity", "Defect severity"),
    ("month", "Month"),
    ("quarter", "Quarter"),
    ("none", "- none -"),
]

# -- run workflow -------------------------------------------------------------------------------
# Module name carries the RUN_ prefix so this shared vocabulary can never be mistaken for a
# project/task status list; the model still exposes it as ProjectReportRun.STATUS_CHOICES.
RUN_STATUS_CHOICES = [
    ("draft", "Draft (frozen, not yet issued)"),
    ("issued", "Issued"),
    ("archived", "Archived"),
]

# -- tile metrics (25) ---------------------------------------------------------------------------
# Every key MUST exist in analytics.WIDGET_METRICS with the same spelling — the tile is a pointer
# into that registry, and a typo'd key is a blank tile that still returns 200 (L8).
WIDGET_METRIC_CHOICES = [
    # scalar → kpi / gauge
    ("kpi_active_projects", "KPI · Active projects (#)"),
    ("kpi_overdue_tasks", "KPI · Overdue tasks (#)"),
    ("kpi_open_risks", "KPI · Open risks (#)"),
    ("kpi_open_issues", "KPI · Open issues (#)"),
    ("kpi_open_defects", "KPI · Open defects (#)"),
    ("kpi_cpi", "KPI · CPI"),
    ("kpi_spi", "KPI · SPI"),
    ("kpi_utilization_pct", "KPI · Utilization %"),
    ("kpi_billable_pct", "KPI · Billable %"),
    ("kpi_unbilled_amount", "KPI · Unbilled amount"),
    ("kpi_schedule_slip_days", "KPI · Schedule slip (days)"),
    # series → bar / line / pie / doughnut / heat
    ("projects_by_status", "Chart · Projects by status"),
    ("tasks_by_status", "Chart · Tasks by status"),
    ("risks_by_category", "Chart · Risks by category"),
    ("issues_by_severity", "Chart · Issues by severity"),
    ("defects_by_severity", "Chart · Defects by severity"),
    ("hours_by_activity_code", "Chart · Hours by activity code"),
    ("cost_variance_by_project", "Chart · Cost variance by project"),
    ("ev_curve_by_month", "Chart · EV curve by month"),
    ("utilization_by_resource", "Chart · Utilization by resource"),
    ("milestones_on_time_by_month", "Chart · Milestones on time by month"),
    ("health_heat_bands", "Chart · Portfolio health heat bands"),
    # table → table only
    ("top_cost_variance_projects", "Table · Worst cost variance"),
    ("top_risk_exposure_projects", "Table · Highest risk exposure"),
    ("overdue_milestones", "Table · Overdue milestones"),
]
```

**Class-attribute exposure (the template/test contract):**

| model | class attributes |
|---|---|
| `ProjectReport` | `REPORT_TYPE_CHOICES`, `SUBJECT_CHOICES`, `MEASURE_CHOICES`, `DIMENSION_CHOICES`, `RANGE_CHOICES`, `CHART_CHOICES` |
| `ProjectReportRun` | `STATUS_CHOICES = RUN_STATUS_CHOICES` |
| `ProjectDashboard` | `AUDIENCE_CHOICES`, `LAYOUT_CHOICES`, `RANGE_CHOICES` |
| `DashboardWidget` | `WIDGET_METRIC_CHOICES`, `CHART_CHOICES`, `RANGE_CHOICES`, `SIZE_CHOICES` |

Counts to assert in `test_reporting_models.py`: **7** / 8 / 3 / 4 / 7 / 16 / 16 / **24** / **18** / 3 / **25**
(`RANGE / CHART / LAYOUT / SIZE / AUDIENCE / REPORT_TYPE / SUBJECT / MEASURE / DIMENSION / RUN_STATUS /
WIDGET_METRIC`) — `DIMENSION_CHOICES` is 18 rows because `none` is a real option, not a blank, and
`RANGE_CHOICES` carries `custom` because the builder's explicit date pair has to be selectable (D19).
`ProjectDashboard.clean()` additionally **refuses `default_range == "custom"`** (rule 4 in A1.2): a dashboard
carries no date pair, so only the six presets are meaningful there.

`analytics.py` must expose the SAME key sets (`MEASURES`, `DIMENSIONS`, `SUBJECTS`, `WIDGET_METRICS`,
`STANDARD_REPORTS`), and a test asserts the two key lists are equal — that equality is the only thing keeping a
dropdown from offering a metric that computes to nothing.

### A1.5 Stored vs computed

**Nothing in these four tables is a number anyone can add up wrong.** Every figure is either a JSON payload
frozen by `rep_freeze` (a *record* of what was computed once) or a `@property`. There are ZERO `DecimalField`
"result" columns, ZERO count columns, ZERO percentage columns — the only `DecimalField` in the whole sub-module
is `DashboardWidget.target_value`, which is a human-entered **goal**, not a measurement.

Two non-choice tuples go at the bottom of `_choices.py` to make the discriminator single-sourced:

```python
#: chart kinds rendered by Chart.js on a <canvas>
CANVAS_CHARTS = ("bar", "line", "pie", "doughnut")
#: chart kinds rendered as plain HTML (never a canvas — a blank canvas still returns 200, L8)
HTML_CHARTS = ("kpi", "gauge", "table", "heat")
```

| model | stored column | Python `@property` (computed, never stored) |
|---|---|---|
| `ProjectReport` | the 23 columns in A1.0 | `metric_labels` → `[dict(MEASURE_CHOICES)[k] for k in measures]`; `dimension_labels`; `window_label` (the resolved `date_range` text, or `"<from> → <to>"` when the custom pair is set); `is_custom` (`report_type == "custom"`); `is_canned` (the inverse); `scope_label` (`project.name` → `portfolio.name` → `client.name` → `org_unit.name` → `"All projects"`) |
| `ProjectReportRun` | the 17 columns in A1.1 | `is_draft` / `is_issued` / `is_archived` (compare `status` to the literal keys); `is_editable` (`status == "draft"` — the ONLY gate on `run_narrative`); `rating` (`(self.data or {}).get("rating") or ""` — the RAG letter); `rag_css` (a `{"green","amber","red"}` map to **colour-named** badge classes `badge-green`/`badge-amber`/`badge-red`, `badge-muted` fallback — L33: `theme.css` has no `badge-success`); `columns` / `rows` / `chart_type` / `chart_labels` / `chart_data` / `caveats` / `truncated` (thin `self.data.get(...)` readers, so no template ever indexes a JSONField); `summary_cards` (the dict → `[{label, value}]` list for the KPI strip) |
| `ProjectDashboard` | the 10 columns in A1.2 | `widget_count` (`self.widgets.count()`; list pages use `annotation_count=Count("widgets")` instead); `is_template` (`owner_id is None`); `column_span` (`{"one": 12, "two": 6, "three": 4}[layout]` with a `.get(layout, 6)` fallback) |
| `DashboardWidget` | the 13 columns in A1.3 | `is_canvas` (`chart_type in CANVAS_CHARTS`); `canvas_id` (`f"wchart{self.pk}"` — the exact DOM id the template renders and the JS looks up); `size_css` (a `SIZE_CHOICES`-keyed map to the grid classes); `metric_label` / `chart_label` (`get_FOO_display()` aliases the tile header reads); `drill_url_name` is **NOT** a property — it comes from `analytics.WIDGET_METRICS[metric]["drill_url_name"]` via `compute_widget`, because models must not import analytics |

**Margin and RAG are computed, never columns:**

* *margin* is the measure key `margin_pct`, computed by `analytics` from 7.15's
  `ProjectInvoice`/`ProjectPaymentRecord` rows against 7.4's actual cost. It appears in `run.summary` /
  `run.data["rows"]` as JSON and in the builder only as a dropdown key.
* *RAG* is 7.4's `CostControlAccount.health` `@property` (verified: `apps/projects/models/CostManagement/CostControlAccounts.py:232`,
  alongside `bac:104`, `ev:118`, `pv:145`, `ac:161`, `committed:166`, `available:171`, `cv:178`, `sv:183`,
  `cpi:188`, `spi:196`, `eac:203`, `etc:212`) read at compute time, written into a run's `data` as a string,
  and re-read from there. `analytics.rag_streak()` then counts consecutive issued runs with the same `rating`.
  No `rag` / `health` / `score` column is added to any 7.16 table.

`ProjectReportRun.data` and `.summary` are the **only** place a computed value is stored, and that is the
definition of a frozen run, not a cache: it is never refreshed, never used to answer a different question, and
never read back into `analytics`.

### A1.6 Tenancy, cascade and the read-only rule

**Tenancy (all four models):**

1. Every model carries `tenant` → `core.Tenant`, `on_delete=CASCADE`, `db_index=True`.
   `ProjectReport` / `ProjectDashboard` get it from `TenantOwned`; `ProjectReportRun` / `DashboardWidget`
   declare it themselves (verbatim `crm.ReportSnapshot` / `crm.DashboardWidget`, both verified) with
   `related_name="+"` — every query is `filter(tenant=request.tenant)`, so no reverse accessor is wanted.
2. **Children cascade from their parent, and the parent's tenant owns the child's tenant:**
   `ProjectReportRun.report` CASCADE (deleting a saved report deletes its history) and
   `DashboardWidget.dashboard` CASCADE (deleting a dashboard deletes its tiles). Both children ALSO have their
   own `tenant` FK CASCADE, so a tenant purge deletes them either way — the two paths agree because `clean()`
   forbids them from disagreeing.
3. Scope FKs are `SET_NULL` (a deleted project must not silently delete the reports that once looked at it) and
   are **revalidated against `tenant` in `clean()` on all four models** — the four in `ProjectReport`, two in
   `ProjectDashboard`, two in `DashboardWidget`, plus `document` on `ProjectReportRun`.
4. `request.tenant is None` (the `admin` superuser) ⇒ every register is empty. That is by design; the seeder
   prints the `admin_<slug>` login.
5. `is_shared` is a real ACL claim, not a cosmetic flag: `visible_reports()` / `visible_runs()` /
   `visible_dashboards()` are the single definition, and a private row for another user is a **404**, not a
   hidden row. `ProjectReportRun` has no `is_shared` of its own — it inherits its parent report's privacy.
   **There is no partial unique index to lean on here**, which is exactly why rule 1 of A1.2's `clean()` is a
   `SELECT … .exclude(pk=self.pk)` existence check rather than a `unique_together` (see A3/D4).

**The read-only rule (L29) — encode it in every module docstring:**

* **No model in 7.16 writes money, never calls `accounting.*`, and never mutates a 7.4 or 7.15 row.** There is
  no `JournalEntry`, no `ProjectInvoice`, no `CostControlAccount` write anywhere in the sub-module — the only
  FK to a *document* is the optional `core.Document` an issued pack is filed against, and that row already
  exists (`run_issue` links an existing document; it does not upload or create one).
* `accounting` owns the ledger and project balances are **derived** there (L29, restated in 7.15's contract);
  7.4 `CostControlAccount` owns EVM as `@property` reads; 7.15 owns billing/invoice/payment/aging. 7.16 reads
  all of them and stores questions, frozen answers, containers and tiles. Nothing else.
* Consequently: **no `q2()` call, no `MAX_Q2` clamp, no money `DecimalField`** in any 7.16 model. If a later
  pass wants a stored figure, it is a new run row, not a new column.
* Deleting a 7.16 row must never cascade INTO another module: the only outgoing FKs are `SET_NULL` (scope) or
  `CASCADE` inbound (children pointing here), so no `Project`, `Party`, `OrgUnit`, `Document` or billing row is
  ever deleted by a 7.16 purge.

## A2 — Forms

**Files** (`apps/projects/forms/ReportingBusinessIntelligence/`, sub-package `__init__.py` intentionally EMPTY
of re-exports like 7.15's; the app-level `forms/__init__.py` gets the `# --- 7.16` block at Integrate):

| path | classes |
|---|---|
| `_choices.py` (models pkg) | — (A1.4) |
| `ProjectReports.py` | `ProjectReportForm` |
| `ReportRuns.py` | `ProjectReportNarrativeForm`, `ProjectReportIssueForm` |
| `ProjectDashboards.py` | `ProjectDashboardForm` |
| `DashboardWidgets.py` | `DashboardWidgetForm` |

**Base class (all four): `class XForm(TenantUniqueMixin, TenantModelForm)` — that exact order.**
Verified convention in this app (`forms/AgileScrumManagement/Sprints.py:10` and 4 siblings). It is not
cosmetic here: `TenantUniqueMixin.__init__` stamps `instance.tenant` before `full_clean()` runs, and every
7.16 model's `clean()` compares a chosen FK's `tenant_id` against `self.tenant_id`. Without the mixin every
CREATE would be falsely rejected as cross-tenant, because the CRUD helpers only assign the real tenant AFTER
`is_valid()`. Import from the absolute path:
`from apps.projects.forms._common import TenantUniqueMixin, TenantModelForm, _reject_foreign`
(`TenantUniqueMixin` and `_reject_foreign` are defined in `apps/projects/forms/_common.py`; `TenantModelForm`
is re-exported there from `apps.core.forms` — verified `apps/core/forms/_common.py:25`).

### A2.1 `ProjectReportForm` (`ProjectReports.py`)

```python
class Meta:
    model = ProjectReport
    fields = ["name", "description", "report_type", "subject", "measures", "dimension_1",
              "dimension_2", "date_range", "date_from", "date_to", "as_of",
              "project", "portfolio", "client", "org_unit",
              "chart_type", "top_n", "sort_by", "notes", "is_shared"]
```

Excluded, and why (L22 — every omission must have a reason):

| omitted | reason |
|---|---|
| `tenant` | set by the CRUD helper / `TenantUniqueMixin`; never a user input |
| `number` | `editable=False`, auto-assigned by `TenantNumbered.save()` with `REP-` |
| `owner` | defaulted to `request.user` in `rep_create` (`form.instance.owner = request.user` when the view has one); editing an owner is an ownership transfer, not a builder field |
| `last_run_at` | `editable=False`, a system stamp written only by `rep_run` / `rep_freeze`; on the form it would be a lie waiting to be typed |
| `is_favorite` | toggled by the `rep_favorite` POST verb, never by the record form — otherwise every edit form reset the star and lost a concurrent toggle |
| `created_at`, `updated_at` | `auto_now_add` / `auto_now` |

Widgets (the guided builder — the whole point is that NO axis is a text box):

* `report_type`, `subject`, `dimension_1`, `dimension_2`, `date_range`, `chart_type`, `sort_by` →
  `forms.Select(attrs={"class": "form-select"})`. They need **no explicit `choices=`**: the model field's
  `choices` already populate the ModelChoiceField, so the dropdown IS the frozen list. `sort_by` is
  `required=False` and gets `MEASURE_CHOICES` plus a `("", "- default -")` option.
* `measures` → **`forms.MultipleChoiceField(choices=MEASURE_CHOICES, widget=forms.CheckboxSelectMultiple)`,
  declared explicitly on the form class** (a JSONField maps to no widget). Its `clean_measures()` coerces the
  selected list back into the JSON list and enforces `1 <= len <= 3`. This is the one field whose form type
  differs from the column type, so `test_reporting_forms.py` must assert `form.instance.measures` is a `list`.
* `date_from`, `date_to`, `as_of` → `forms.DateInput(attrs={"class": "form-input", "type": "date"})`
  (`TenantModelForm` already does this for every `DateField`; overriding is harmless and matches 7.15).
* `top_n` → `forms.NumberInput(attrs={"class": "form-input", "min": "1", "max": "100"})`.
* `name`/`description`/`notes` → `TextInput` / `Textarea(rows=2)` with the `form-input` / `form-textarea`
  classes (set automatically by `TenantModelForm`; spelled out to match 7.15's files).
* `project`, `portfolio`, `client`, `org_unit`, `is_shared` → `Select` / `CheckboxInput`.

Tenancy of the querysets: `TenantModelForm.__init__(tenant=…)` **already filters every `ModelChoiceField` whose
target model has a `tenant` column** (verified `apps/core/forms/_common.py:51–55`) — and `Project`, `Portfolio`,
`Party`, `OrgUnit` all do. So **no manual `ModelChoiceField` queryset is required**; if the builder wants a
nicer label or an ordering (`Project.objects.filter(tenant=…).order_by("name")`), override the queryset in
`__init__` AFTER `super().__init__()` and keep the `tenant=tenant` filter inside it — never widen it.
`tenant=None` (a shell/test that forgets it) leaves the querysets unfiltered, which is exactly why the crafted-
POST re-check below is not optional.

```python
def __init__(self, *args, tenant=None, **kwargs):
    super().__init__(*args, tenant=tenant, **kwargs)
    if tenant is not None:
        self.fields["project"].queryset = Project.objects.filter(tenant=tenant).order_by("name")
        self.fields["portfolio"].queryset = Portfolio.objects.filter(tenant=tenant).order_by("name")
        self.fields["client"].queryset = Party.objects.filter(tenant=tenant).order_by("name")
        self.fields["org_unit"].queryset = OrgUnit.objects.filter(tenant=tenant).order_by("name")
```

(absolute imports for those four models; `Party` is `core.Party`, the client register.)

```python
def clean(self):
    cleaned = super().clean()
    _reject_foreign(self, cleaned, ["project", "portfolio", "client", "org_unit"])
    return cleaned
```

`_reject_foreign` is the crafted-POST guard: *a narrowed `<select>` is UX, not an authorization boundary.*
None of these four targets is a global model, so all four are safe to pass (the `accounting.Currency` trap in
`forms/_common.py`'s docstring does not apply to 7.16 — there is no currency FK here at all).

### A2.2 `ProjectReportRun` — two forms, **no builder/edit form**

`ProjectReportRun` has **no `ModelForm` over its question fields**: no `run_create`, no `run_edit`, no field for
`report`, `title`, `period_*`, `as_of`, `summary`, `data`, `row_count`, `status`, `issued_by`, `issued_at`,
`generated_by`, `generated_at`. Rows exist only because `rep_freeze` minted them inside a
`transaction.atomic()`. Editing a frozen answer in place would destroy the one property that justifies the
table. The two forms that do exist cover the only human-authored late writes:

```python
class ProjectReportNarrativeForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = ProjectReportRun
        fields = ["narrative"]
        widgets = {"narrative": forms.Textarea(attrs={"class": "form-textarea", "rows": 8,
                                                      "placeholder": "Commentary for the steering pack…"})}
    def clean(self):
        cleaned = super().clean()
        if self.instance.pk and not self.instance.is_draft:
            raise ValidationError({"narrative": "An issued or archived run cannot be edited — freeze a new run."})
        return cleaned


class ProjectReportIssueForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = ProjectReportRun
        fields = ["document"]
        widgets = {"document": forms.Select(attrs={"class": "form-select"})}
    # __init__(tenant=…) narrows document to core.Document.objects.filter(tenant=tenant)
    # clean(): _reject_foreign(self, cleaned, ["document"]) + require run.is_draft before issuing
```

* The `document` `ModelChoiceField` **must** be tenant-narrowed — and it is, twice: `TenantModelForm`'s auto
  scope (core.Document carries `tenant`, verified `apps/core/models/Document.py:14`) plus `_reject_foreign` on
  the crafted POST. **No file upload on this form**: the issued pack links an EXISTING document; uploads are
  the document repository's job (7.10).
* Gating on `is_draft` is the form's job (it reads `self.instance`), not `model.clean()`'s — the model would
  then reject the very `run_issue` write that flips the status in the same save.
* `narrative` is the only free text in the sub-module that reaches a page a colleague reads; it renders
  auto-escaped through `{{ }}` like every other string (no `|safe` anywhere).

### A2.3 `ProjectDashboardForm` (`ProjectDashboards.py`)

```python
class Meta:
    model = ProjectDashboard
    fields = ["name", "description", "audience", "default_range", "layout",
              "is_shared", "project", "portfolio"]
```

| omitted | reason |
|---|---|
| `tenant` / `number` | as A2.1 (`PDB-` auto-number) |
| `owner` | `request.user` on create; `null` is reserved for a seeder-authored tenant template, which is not something a UI form may create |
| `is_default` | made True only through the `pdb_home`/set-default verb, so "which one is my home" is an explicit act and two rows can never both be the default because two edit forms were saved |
| `created_at` / `updated_at` | auto |

`audience`, `default_range`, `layout` are `forms.Select`; `project`/`portfolio` are tenant-narrowed in
`__init__` exactly as A2.1; `clean()` runs
`_reject_foreign(self, cleaned, ["project", "portfolio"])`.

### A2.4 `DashboardWidgetForm` (`DashboardWidgets.py`)

```python
class Meta:
    model = DashboardWidget
    fields = ["title", "metric", "chart_type", "date_range", "size", "target_value",
              "project", "portfolio"]
```

| omitted | reason |
|---|---|
| `tenant` | copied from the parent dashboard by `wdg_create` (`form.instance.tenant = dashboard.tenant`) |
| `dashboard` | fixed by the URL (`reporting/dashboards/<int:pk>/widgets/add/`); on the form it would be a cross-dashboard move nobody asked for |
| `position` | auto-appended (`max(position)+1`) on create; re-ordered only by the `wdg_move` POST, so a hand-typed position cannot interleave two tiles |
| `created_at` / `updated_at` | auto |

`clean()` carries **the metric↔chart rule** (its home; see A1.3 `clean()` rule 3), copied from the verified
crm precedent `apps/crm/forms/AnalyticsReporting/Widgets.py:17–26`:

```python
def clean(self):
    from apps.projects.analytics import WIDGET_METRICS, allowed_charts   # local import, crm's shape
    cleaned = super().clean()
    metric, chart_type = cleaned.get("metric"), cleaned.get("chart_type")
    if metric and chart_type and metric in WIDGET_METRICS:
        ok = allowed_charts(metric)
        if chart_type not in ok:
            self.add_error("chart_type", "This metric supports: " + ", ".join(ok) + ".")
    _reject_foreign(self, cleaned, ["project", "portfolio"])
    return cleaned
```

* **Rule-home ledger (one home per rule, as mandated):**
  | rule | home | why |
  |---|---|---|
  | measures 1–3 + known keys | `ProjectReport.clean()` | pure vocabulary check, no analytics needed |
  | window required / ordered / ≤ 730 d / `as_of` inside | model `clean()` on both `ProjectReport` and `ProjectReportRun` | it is a data-integrity invariant, and the seeder/`rep_freeze` bypass the form |
  | `dimension_1 != dimension_2` | model `clean()` | same |
  | `sort_by` ∈ measure keys | model `clean()` | same |
  | metric ↔ chart pair | **form** `clean()` (both widget and report) | needs `analytics.allowed_charts`; models must not import analytics (one-way edge) |
  | scope-FK tenancy (invariant) | model `clean()` | defence in depth for non-form writers |
  | scope-FK tenancy (crafted POST, field-level error) | form `clean()` via `_reject_foreign` | renders on the field the user actually touched |
  | `is_default` uniqueness | model `clean()` | the DB cannot express it (no partial unique on MySQL) |
  | draft-only narrative / issue gating | form `clean()` | it is a workflow gate on a verb, not an invariant of the row |
* `target_value` gets `forms.NumberInput(attrs={"class": "form-input", "step": "0.01"})` and
  `required=False`; the form does NOT reject `target_value` on a bar chart (that would fight a user switching
  chart type after filling the goal) — `analytics` simply ignores it, and the field's `help_text` says so.
* **Choice lists into the form vs the template:** the `CharField(choices=…)` columns already carry their options
  from A1.4, so the builder needs NO extra constructor argument. The parts that are NOT model fields —
  `MEASURE_CHOICES` for the `measures` MultipleChoiceField, and `analytics.allowed_charts(metric)` for the
  "charts allowed for this metric" JS hint — must be passed explicitly: `ProjectReportForm.__init__(…, tenant)`
  sets `self.fields["measures"].choices = MEASURE_CHOICES`, and the **view** passes `chart_rules` (the
  `metric → [allowed charts]` JSON map) into the template context for the builder's progressive disclosure.
  Part B owns that context key; A2's claim is only that the form never reads `request` and never invents a choice.

## A3 — Deviations from plan

Every one of these is **the code winning over the plan**, with the verification that decided it.

| ID | plan said | contract pins | why |
|---|---|---|---|
| D1 | `ProjectReport.Meta.ordering = ["name"]` | `["-is_favorite", "name"]` | both precedents (`crm.AnalyticsReport`, `procurement.SpendReport`, verified) favour the star; the column exists on the model, so ordering by it costs nothing |
| D2 | `STATUS_CHOICES` in `_choices.py` | `RUN_STATUS_CHOICES`, exposed as `ProjectReportRun.STATUS_CHOICES` | a bare `STATUS_CHOICES` in a shared module is ambiguous in an app where `Project`, `Task`, `Risk`, `Issue` all have one; templates/tests still compare the raw `draft`/`issued`/`archived` keys |
| D3 | `related_name="runs"`, `related_name="widgets"` "grepped free app-wide" | kept, **with the correction that a repo-wide grep is NOT empty**: `related_name="runs"` → `apps/inventory/models/ThirdPartyIntegrations/StockSyncRuns.py:81`; `related_name="widgets"` → `apps/crm/.../Widgets.py:14` and `apps/hrm/models/AnalyticsDashboard/Widget.py:50`. All three sit on **different parent models**, and Django's reverse-name clash check is per-parent, so they cannot conflict; `grep` inside `apps/projects/` is 0 for both. `manage.py check` is the gate that proves it | a "grep-free" claim in the plan was wrong; the design is still safe |
| D4 | at-most-one-default expressed alongside `unique_together` | a `clean()` `SELECT … .exclude(pk=self.pk)` existence check ONLY | neither MySQL (the driver is PyMySQL) nor SQLite gives Django a **partial** unique (`WHERE is_default = 1`); `UniqueConstraint(condition=…)` is silently unsupported on MySQL, so it must not be relied on. `unique_together` here stays exactly `("tenant","number")` |
| D5 | `ProjectReportRun` = crm/procurement snapshot shape "written once and never edited" (their precedents have **no** timestamp pair) | `generated_at` (`auto_now_add`) **+** `updated_at` (`auto_now`) | the run is NOT literally write-once: `narrative`, `issue` and `archive` mutate it, and an audit-answering "when did this pack last change" question had no column to answer it. `generated_at` stays the ordering key so `updated_at` can never reshuffle "latest" |
| D6 | `as_of` (Date) | required, no `null` | a run with no as-of instant cannot support the as-of discipline or `rag_streak`; `rep_freeze` always resolves it |
| D7 | `summary` JSONField (precedents use `default=list`) | `default=dict`, shape `{label: value}` | `run_detail` and `exec_pack` look values up by label; a list forces a linear scan in the template (index gymnastics are banned in Part B too) |
| D8 | `models.Index(fields=["tenant", "-generated_at"])` | `fields=["tenant", "generated_at"]` | **`Index(fields=[…])` does not accept the ordering-prefixed string** — it raises at import; a composite index scans backwards fine on both engines |
| D9 | `MEASURE_CHOICES ≈20`, `DIMENSION_CHOICES 17`, `WIDGET_METRIC_CHOICES ≈22` | **24 / 18 / 25** | the 15 named ratio keys need their base aggregates (`planned_value`, `earned_value`, `actual_cost`, `budget_at_completion`, `invoiced_amount`, `task_count`, `completed_count`) or a ratio column has nothing to divide; `none` is a real 18th dimension row; the widget list is the plan's own 25 enumerated keys (its "≈22" undercounted) plus `margin_pct` living in MEASURE only |
| D10 | the metric↔chart pair validated in `DashboardWidget.clean()` | in `DashboardWidgetForm.clean()` | `analytics.allowed_charts(metric)` is the only authority and **models never import analytics** (the one-way edge, restated verbatim in `procurement` `SpendReports.py` docstring). crm already resolves this the same way (`forms/AnalyticsReporting/Widgets.py:17–26`) |
| D11 | `is_shared` default unspecified (procurement defaults `True`) | `default=False` on both `ProjectReport` and `ProjectDashboard` | `is_shared` is the ACL claim `visible_*()` reads; a saved report is private until deliberately shared (crm's `AnalyticsDashboard` default) |
| D12 | forms: `ProjectReportNarrativeForm` only for runs | `ProjectReportNarrativeForm` **and** `ProjectReportIssueForm` (`fields=["document"]`) | `run_issue` needs a tenant-narrowed `ModelChoiceField` over `core.Document`; putting it in the narrative form would let a narrative save silently attach a filing document |
| D13 | `top_n` PositiveInt | `PositiveSmallIntegerField` | `procurement.SpendReport.top_n` verbatim; the 1..100 validators make the smaller type free |
| D14 | "`save()` auto-number behaviour with the concurrent-collision retry used by 7.15" | **no `save()` override at all** on the two numbered models | the retry already lives in `TenantNumbered.save()` (`models/_base.py:66–75`); 7.15's per-model `save()` methods exist only to `q2()` money, which 7.16 has none of. Re-declaring it would fork the numbering logic |
| D15 | `measures` JSONField with no form story | `forms.MultipleChoiceField(choices=MEASURE_CHOICES)` + `clean_measures()` coercion | a JSONField generates no widget; without this the builder's central "add columns" step has no input |
| D16 | `_choices.py` "apps/projects has none yet" | confirmed — 7.16 ships the app's first | `ls apps/projects/models/*/` has no `_choices.py`; `_base.py` is the only underscore module |
| D17 | (unspecified) | FK target strings are **app-label-qualified**: `"projects.ProjectReport"`, `"projects.ProjectDashboard"`, `"core.Document"`, `"projects.Project"`, `"projects.Portfolio"`, `"core.Party"`, `"core.OrgUnit"` | the models sit three levels deep in a sub-package; a bare `"ProjectReport"` string resolves only inside the same app and `"core.Party"` must be explicit anyway (7.15's files all qualify) |
| D18 | (unspecified) | `apps/projects/models/__init__.py`'s new block uses the file's **relative** form (`from .ReportingBusinessIntelligence.ProjectReports import ProjectReport  # noqa: F401`) | CLAUDE.md's "absolute imports" rule governs entity modules; the app-level re-export file is written relatively by every one of the 15 existing sections (verified tail: 7.14/7.15 blocks) — matching the file beats the general rule, and Integrate must not restate it |
| D19 | `RANGE_CHOICES` = the 6 presets (`last_7`…`all`) **plus `custom`** | 7 rows | the model carries `date_from`/`date_to` and `clean()` validates a 730-day custom window, but with the plan's 6 keys no user can ever *reach* that pair — the builder would render two dead date inputs. `procurement.DATE_RANGE_CHOICES` (verified) has exactly this 6+`custom` shape for exactly this reason. Consequence pinned: `custom` is banned on `ProjectDashboard.default_range` / `DashboardWidget.date_range`, which have no date pair |

**Still open for Part B (deliberately not Part A's to pin):** every url name, view name, context key, template
path and the seeder's `_reporting_bi` row counts — they live in the plan's later sections and Part B owns them.
Part A's promise to Part B is: the four models, their 23/17/10/13 columns, the 11 choice constants + the 2 chart
tuples, the property names in A1.5, the four form classes with the `Meta.fields` whitelists in A2, and the fact
that no 7.16 model imports `analytics` or writes money.

---

# PART B — views / urls / context contract / analytics registry / templates / seeder / verification

**Vocabulary source:** Part A above, verbatim. Part B adds no field, no choice key and no form.

## B0 — Verification ledger for Part B (what was read, and what it proved)

| read | proved |
|---|---|
| `apps/core/crud.py` (whole file) | `crud_list` supplies **exactly** `object_list` (= `page_obj.object_list`), `page_obj`, `q` + `extra_context`; `crud_create` supplies `form`, `is_edit=False`; `crud_edit` supplies `form`, `obj`, `is_edit=True`; `crud_detail` supplies `obj`; `crud_delete` supplies **nothing** (redirect only). It also carries the whole L11 filter-guard stack (`as_db_int`, `_is_pk_lookup`, `_enum_values`, the `True`/`False` bool mapping) and L9 pagination (`paginate()` sets `page.window`). **`per_page=15` default.** |
| `apps/projects/views/_common.py` | the star-import toolkit for every 7.16 view module: `messages`, `login_required`, `get_object_or_404`, `redirect`, `render`, `timezone`, `require_POST`, the five `crud_*` helpers, `tenant_admin_required`, `write_audit_log`. Docstring restates the `varchar(10)` audit-action cap. |
| `apps/projects/urls/__init__.py` (head + tail) | `app_name = "projects"` once; each sub-module's entity url module is imported as `_<prefix>_<entity>` and **concatenated in build order**; 7.15's tail is `_fbm_ratecards + _fbm_billingruns + _fbm_revenueschedules + _fbm_paymentrecords + _fbm_financialboards`. Every first segment in the app is a literal — the no-converter-in-first-component invariant. |
| `grep -rn 'path("reporting/' apps/projects/urls/` | **0 hits** → the `reporting/` first segment is free; re-verify at Integrate (a concurrent session could claim it, L43). |
| `apps/projects/urls/FinancialBillingManagement/{__init__.py,FinancialBoards.py}` | sub-package `__init__.py` is a one-line docstring (no re-exports); standalone-board urls sit in their own module with the **trailing-slash literal path + bare view name** (`path("financial/pnl/", views.financial_pnl, name="financial_pnl")`); entity modules import `... import X as views`. |
| `templates/projects/financialbilling/**` (find) | the shape Part B copies: standalone boards at the sub-module root (`pnl.html`, `variance.html`, `aging.html`, `cashflow.html`), entity triples in `<entity>/{list,detail,form}.html`, plus a secondary action page (`billingrun/preview_pdf.html`). |
| `grep -rn -B3 'def .*_delete' apps/projects/views/**` + `RiskManagement/IssueEscalations.py:87–91` | the app's **actual** verb-gate order is `@login_required` → `@require_POST` → `@tenant_admin_required`. See D20. |
| `apps/procurement/views/SpendAnalyticsReporting/SpendReports.py` (docstring + head) | the ACL-in-one-place pattern (`visible_reports(request)`), `_snapshot_qs`, `csv_safe` from `views/_helpers.py`, template constants at module top, `import csv` / `HttpResponse` / `reverse` and `from apps.procurement import analytics`. |
| `.claude/tasks/todo.md` §7.16 (8737–9142) | the page/url-name set Part B must pin exactly, the five `LIVE_LINKS` bullets, the seeder row budget, and the smoke checklist. |

## B1 — URL map (exact `path()` / view / `name=` / verbs)

**`app_name = "projects"`** already exists in `urls/__init__.py` — every name below is used as
`projects:<name>`. **31 routes** over 5 url modules, every one under the single literal first segment
`reporting/`. All paths carry the trailing slash (house style, verified against 7.13/7.15).

### B1.0 File split (`apps/projects/urls/ReportingBusinessIntelligence/`)

One module per entity file, matching the models/forms/views split in A0/A2, plus one module for the four
standalone computed pages — **the exact 7.15 shape** (`FinancialBoards.py` is the precedent for
`ReportingHome.py`). Each sub-package `__init__.py` is a one-line docstring with **no re-exports**.

| url module | routes |
|---|---|
| `ReportingHome.py` | 4 — `rbi_home`, `report_library`, `report_standard`, `exec_pack` |
| `ProjectReports.py` | 10 |
| `ReportRuns.py` | 7 |
| `ProjectDashboards.py` | 6 |
| `DashboardWidgets.py` | 4 |

Each file: `from django.urls import path` + `from apps.projects.views.ReportingBusinessIntelligence import
<ProjectModule> as views` + a module-level `urlpatterns` list. **Views are imported from the entity module
directly, not from the package `__init__`** (procurement's documented rule — a package-level re-export here is
a star-import cycle at URLconf import time).

### B1.1 `ReportingHome.py` (GET only — no verbs here)

| # | `path()` | view function | `name=` | verbs |
|---|---|---|---|---|
| 1 | `reporting/` | `ReportingHome.rbi_home` | `rbi_home` | GET |
| 2 | `reporting/library/` | `ReportingHome.report_library` | `report_library` | GET |
| 3 | `reporting/standard/` | `ReportingHome.report_standard` | `report_standard` | GET |
| 4 | `reporting/exec-pack/` | `ReportingHome.exec_pack` | `exec_pack` | GET |

`rbi_home` is path `reporting/` with **no trailing segment** — it is the only route whose first component is the
bare segment, so it can never shadow a longer literal (`reporting/library/` … are separate components).

### B1.2 `ProjectReports.py` — **literal `add/` first, then `<int:pk>/`, then the pk verbs**

| # | `path()` | view function | `name=` | verbs |
|---|---|---|---|---|
| 5 | `reporting/reports/` | `ProjectReports.rep_list` | `rep_list` | GET |
| 6 | `reporting/reports/add/` | `ProjectReports.rep_create` | `rep_create` | GET, POST |
| 7 | `reporting/reports/<int:pk>/` | `ProjectReports.rep_detail` | `rep_detail` | GET |
| 8 | `reporting/reports/<int:pk>/edit/` | `ProjectReports.rep_edit` | `rep_edit` | GET, POST |
| 9 | `reporting/reports/<int:pk>/delete/` | `ProjectReports.rep_delete` | `rep_delete` | **POST only** |
| 10 | `reporting/reports/<int:pk>/run/` | `ProjectReports.rep_run` | `rep_run` | **POST only** |
| 11 | `reporting/reports/<int:pk>/freeze/` | `ProjectReports.rep_freeze` | `rep_freeze` | **POST only** |
| 12 | `reporting/reports/<int:pk>/favorite/` | `ProjectReports.rep_favorite` | `rep_favorite` | **POST only** |
| 13 | `reporting/reports/<int:pk>/csv/` | `ProjectReports.rep_csv` | `rep_csv` | GET |
| 14 | `reporting/reports/<int:pk>/json/` | `ProjectReports.rep_json` | `rep_json` | GET |

### B1.3 `ReportRuns.py` — **no create, no edit** (the documented CRUD exemption, A2.2)

| # | `path()` | view function | `name=` | verbs |
|---|---|---|---|---|
| 15 | `reporting/runs/` | `ReportRuns.run_list` | `run_list` | GET |
| 16 | `reporting/runs/<int:pk>/` | `ReportRuns.run_detail` | `run_detail` | GET |
| 17 | `reporting/runs/<int:pk>/narrative/` | `ReportRuns.run_narrative` | `run_narrative` | **POST only** |
| 18 | `reporting/runs/<int:pk>/issue/` | `ReportRuns.run_issue` | `run_issue` | **POST only** |
| 19 | `reporting/runs/<int:pk>/archive/` | `ReportRuns.run_archive` | `run_archive` | **POST only** |
| 20 | `reporting/runs/<int:pk>/delete/` | `ReportRuns.run_delete` | `run_delete` | **POST only**, `@tenant_admin_required` |
| 21 | `reporting/runs/<int:pk>/csv/` | `ReportRuns.run_csv` | `run_csv` | GET |

There is deliberately **no `run_json`** — `rep_json` is the machine-readable face of a *live* compute; a frozen
run is already a stored JSON payload and its `run_csv` reads `run.data` verbatim. Two JSON exits for one stored
answer is two code paths that can disagree.

### B1.4 `ProjectDashboards.py`

| # | `path()` | view function | `name=` | verbs |
|---|---|---|---|---|
| 22 | `reporting/home/` | `ProjectDashboards.pdb_home` | `pdb_home` | GET |
| 23 | `reporting/dashboards/` | `ProjectDashboards.pdb_list` | `pdb_list` | GET |
| 24 | `reporting/dashboards/add/` | `ProjectDashboards.pdb_create` | `pdb_create` | GET, POST |
| 25 | `reporting/dashboards/<int:pk>/` | `ProjectDashboards.pdb_detail` | `pdb_detail` | GET |
| 26 | `reporting/dashboards/<int:pk>/edit/` | `ProjectDashboards.pdb_edit` | `pdb_edit` | GET, POST |
| 27 | `reporting/dashboards/<int:pk>/delete/` | `ProjectDashboards.pdb_delete` | `pdb_delete` | **POST only** |

`reporting/home/` (the dashboard home) vs `reporting/` (the BI home) are two distinct literals — do not merge.

### B1.5 `DashboardWidgets.py` — child mounted BOTH ways (parent-scoped create, own pk for the verbs)

| # | `path()` | view function | `name=` | verbs |
|---|---|---|---|---|
| 28 | `reporting/dashboards/<int:pk>/widgets/add/` | `DashboardWidgets.wdg_create` | `wdg_create` | GET, POST |
| 29 | `reporting/widgets/<int:pk>/edit/` | `DashboardWidgets.wdg_edit` | `wdg_edit` | GET, POST |
| 30 | `reporting/widgets/<int:pk>/delete/` | `DashboardWidgets.wdg_delete` | `wdg_delete` | **POST only** |
| 31 | `reporting/widgets/<int:pk>/move/` | `DashboardWidgets.wdg_move` | `wdg_move` | **POST only** |

`wdg_create`'s `<int:pk>` is the **dashboard** pk; the other three are the **widget** pk. The `reporting/
dashboards/<int:pk>/widgets/` prefix therefore has a *different* referent than `pdb_detail`'s pk — which is fine
because they are different route shapes, and it is why `wdg_create` must be listed in this module (next to the
other three) and **not** in `ProjectDashboards.py`.

### B1.6 Concatenation order in `apps/projects/urls/__init__.py` (first-match-wins)

Append the import block after the `_fbm_*` imports and the `+` block after `_fbm_financialboards`, with the
sub-module's own house comment (7.13/7.14/7.15 style):

```python
from .ReportingBusinessIntelligence.ReportingHome import urlpatterns as _rbi_home
from .ReportingBusinessIntelligence.ProjectReports import urlpatterns as _rbi_reports
from .ReportingBusinessIntelligence.ReportRuns import urlpatterns as _rbi_runs
from .ReportingBusinessIntelligence.ProjectDashboards import urlpatterns as _rbi_dashboards
from .ReportingBusinessIntelligence.DashboardWidgets import urlpatterns as _rbi_widgets
```

```python
    # 7.16 Reporting & Business Intelligence — every first segment is prefixed with reporting/
    # (verified 0 pre-existing uses of the literal), so nothing here can shadow an earlier
    # sub-module. Within the family the standalone pages precede the registers and the child
    # tiles are mounted under reporting/widgets/, so no two routes in this block share a prefix
    # shape. Literal routes precede <int:pk> inside each module.
    + _rbi_home
    + _rbi_reports
    + _rbi_runs
    + _rbi_dashboards
    + _rbi_widgets
```

**Why this order and not alphabetical:** `_rbi_home` first puts the four bare literals (`reporting/`,
`reporting/library/`, `reporting/standard/`, `reporting/exec-pack/`) ahead of everything; `_rbi_reports` before
`_rbi_runs` keeps `reporting/reports/` and `reporting/runs/` resolvable before any `<int:pk>` under either;
`_rbi_dashboards` **must** precede `_rbi_widgets` so `reporting/dashboards/<int:pk>/` is claimed by
`pdb_detail` and the longer `reporting/dashboards/<int:pk>/widgets/add/` still wins its own shape (it is longer,
so it cannot be shadowed — the ordering is for legibility, and the smoke sweep in B5 asserts all five literal
shapes anyway). Inside each module: bare list → `add/` → `<int:pk>/` → `<int:pk>/<verb>/` → `<int:pk>/{csv,json}/`.

### B1.7 Verb discipline

**11 POST-only routes:** `rep_delete`, `rep_run`, `rep_freeze`, `rep_favorite`, `run_narrative`, `run_issue`,
`run_archive`, `run_delete`, `pdb_delete`, `wdg_delete`, `wdg_move`.

**Decorator order — pin it exactly, it is 7.7's 403-vs-405 bug (verified against the code, D20):**

```python
@login_required          # outermost — a logged-out POST redirects to login, it does not 405
@require_POST            # verb gate BEFORE the role gate → wrong verb + wrong role = 405, not 403
@tenant_admin_required   # role gate INNERMOST (run_delete only)
def run_delete(request, pk): …
```

`@require_POST` must be outermost **among the verb/permission gates** (i.e. outside `tenant_admin_required`) so
a member hitting `run_delete` with a GET gets **405**, not the misleading 403 — but `@login_required` still sits
above `@require_POST`, which is the app-wide shape at `RiskManagement/IssueEscalations.py:87–90`,
`FinancialBillingManagement/{BillingRuns,PaymentRecords,RateCards,RevenueSchedules}.py` and every other
`*_delete` in the app. **`@require_POST` never wraps a form view** (`rep_create`/`rep_edit`/`pdb_*`/`wdg_create`
/`wdg_edit` are GET+POST through the `crud_*` helpers).

**CSRF:** every POST is a real `<form method="post">` with `{% csrf_token %}` (L-rule from CRUD Completeness);
`wdg_move` and `rep_favorite` are form posts from the detail/dashboard pages, never `fetch()` with a hand-rolled
header.

## B2 — View-by-view context contract

Every key a template reads is listed here with its producer. A key the template reads and the view does not pass
renders **blank at HTTP 200** (L8), which is why this section is the longest in the contract.

### B2.0 — Rules that apply to every entry

**R1 — what `crud_*` already supplies (verified `apps/core/crud.py`), and therefore what a view must NOT
re-pass or rename:**

| helper | keys it puts in the context | consequence for 7.16 |
|---|---|---|
| `crud_list` | `object_list` (= `page_obj.object_list`), `page_obj`, `q` + `extra_context` | **every 7.16 list template iterates `{% for r in object_list %}`.** A template that loops `{% for r in reports %}` renders an empty table on a 200 — the exact L8 bug this rule exists to stop. `run_list`'s loop var is also `object_list` (`{% for run in object_list %}` — the *alias* is fine, the *name* is not). |
| `crud_create` | `form`, `is_edit: False` | extra keys only via `extra_context=` |
| `crud_edit` | `form`, `obj`, `is_edit: True` | `obj` is **the edited object** |
| `crud_detail` | `obj` | **unused by 7.16** — `rep_detail` and `pdb_detail` both compute, so they are hand-written (they still use the key `obj`, so the rule holds) |
| `crud_delete` | *(none — it only redirects)* | only usable when the redirect target needs no pk |

`paginate()` also sets `page_obj.window`, which `partials/pagination.html` reads. **`per_page` stays at the
helper's default of 15** on all three registers (no page overrides it, so no page can disagree about its page
size).

**R2 — filter echo variables.** The verified 7.15 house style
(`templates/projects/financialbilling/ratecard/list.html:37,47`) is a **view-passed echo var per filter**, named
`<param>_filter`, NOT `request.GET.<param>` in the template. Part B pins that shape. Every echo is the
**stripped string** from `request.GET.get("<param>", "").strip()` — never the parsed int, so `?project=abc`
echoes `abc` and simply does not match an option.

**R3 — `selected` comparisons.**
* String/enum filter: `{% if type_filter == t.0 %}selected{% endif %}` (`t.0` is the key of the `(key, label)`
  tuple — Django templates cannot subscript a tuple by string).
* pk filter: `{% if project_filter|stringformat:"d" == p.pk|stringformat:"d" %}selected{% endif %}` —
  **`|stringformat:"d"` on BOTH sides, never `|slugify`** (slugify mangles nothing here but is the wrong tool and
  is banned by the filter rules; the int→str coercion is the point).
* Boolean filter: option values are the exact strings `True` / `False`, because that is the key set of
  `crud_list`'s `{"True": True, "False": False}` mapping. Lowercase `true` happens to survive
  `BooleanField.to_python`, but the mapping does not — so a lowercase option would render `selected` off while
  filtering on. Pin capitalised.

**R4 — pagination.** Every list template ends with `{% include "partials/pagination.html" %}`. That partial is
L9-safe (it guards `has_previous` / `has_next` / `num_pages > 1`) **and it requires `page_obj`** — so it is
included only on `rep_list`, `run_list`, `pdb_list`, and deliberately **not** on `rbi_home`, whose `object_list`
has no `page_obj` beside it (documented in the template, so a reviewer does not "fix" it).

**R5 — who makes JSON safe for `json_script` (pinned to one answer): `analytics`.**
Every compute function returns only `str` / `int` / `float` / `bool` / `None` / `list` / `dict`, with money and
percentages already converted by `_money` / `_num` / `_pct` (display strings) and raw series values coerced with
`float()`, and every date already an `isoformat()` string. `_jsonable(value)` is the single tail-guard analytics
applies to any value before it enters a payload. **Views never convert, templates never convert, `rep_freeze`
stores the payload verbatim, `run_detail` renders the stored payload verbatim.** A `date` object IS allowed in a
template context for `{{ as_of|date:"d M Y" }}` display (`rep_detail`, `exec_pack`, `run_detail`) but must never
be placed inside `chart_config` / `chart_configs` / `summary` / `data`. The smoke test's decoded-JSON assertion
in B5 is what proves it.

**R6 — chart payload shape (copied from the verified crm contract,
`apps/crm/views/AnalyticsReporting/Dashboards.py:52–59` + `templates/crm/analytics/dashboard/detail.html:59,77–104`):**
* one entry per canvas: `{"id": <int widget pk>, "type": <bar|line|pie|doughnut>, "labels": [str], "data": [number]}`;
* the view appends it **only** when `result["kind"] == "series"` **and** `w.chart_type in CANVAS_CHARTS` — the
  `HTML_CHARTS` kinds (`kpi`, `gauge`, `table`, `heat`) render markup and get **no** canvas (A1.5: a blank canvas
  still returns 200);
* the DOM id is `wchart{{ w.pk }}`, which is `{{ w.canvas_id }}` from A1.5 — **the property and the template must
  agree, so the template uses `id="{{ w.canvas_id }}"`**, and the JS looks up `"wchart" + c.id`;
* the `json_script` ids are fixed per page: **`rbi-charts`** on the dashboard grid (both `pdb_detail` and
  `pdb_home`), **`rbi-report-chart`** on the single-chart pages (`standard.html`, `report/detail.html`).

**R7 — ACL (one definition each, all three in `analytics`, all three returning a QuerySet):**
`visible_reports(request)` → `ProjectReport.filter(tenant).filter(Q(is_shared=True) | Q(owner=request.user))`;
`visible_dashboards(request)` → same over `ProjectDashboard`;
`visible_runs(request)` → `ProjectReportRun.filter(tenant).filter(report__in=visible_reports(request))` — a run
inherits its parent report's privacy (it has no `is_shared` of its own, A1.6). **Every fetch in the sub-module
goes through one of these three, including the CSV/JSON routes.** Because the helper is the *queryset* the
`get_object_or_404` runs against, a private object owned by a colleague is a **404, not a 403** — it does not
exist for that caller. `tenant=None` (superuser `admin`) ⇒ empty registers everywhere (multi-tenancy rule).

| view | queryset it fetches from |
|---|---|
| `rep_list`, `rep_detail`, `rep_edit`, `rep_delete`, `rep_run`, `rep_freeze`, `rep_favorite`, `rep_csv`, `rep_json` | `visible_reports(request)` |
| `run_list`, `run_detail`, `run_narrative`, `run_issue`, `run_archive`, `run_delete`, `run_csv` | `visible_runs(request)` |
| `pdb_list`, `pdb_detail`, `pdb_edit`, `pdb_delete`, `pdb_home`, `wdg_create` (the **parent dashboard**) | `visible_dashboards(request)` |
| `wdg_edit`, `wdg_delete`, `wdg_move` | `DashboardWidget.objects.filter(tenant=request.tenant, pk=pk, dashboard__in=visible_dashboards(request))` — a tile under a colleague's private dashboard is a 404 too |
| `rbi_home`, `report_library`, `exec_pack` | all three, for their strips |

**R8 — audit.** `write_audit_log(request.user, obj, action, changes=…)` (verified
`apps/core/utils.py:6`). `action` is **`varchar(10)`** and each of these is ≤ 10 chars: `create`, `update`,
`delete`, `freeze`, `issue`, `export`, `archive`, `toggle`. **The verb goes in `changes`**
(`changes={"verb": "favorite"}`, `changes={"direction": "up"}`, `changes={"rows": n}`). `crud_create` /
`crud_edit` / `crud_delete` already log `create` / `update` / `delete`; hand-written views log their own.

**R9 — helper usage per view (so nobody "simplifies" a pk-redirect into a static one):**

| hand-written because | views |
|---|---|
| needs a compute / non-paginated grid | `rbi_home`, `report_library`, `report_standard`, `exec_pack`, `rep_detail`, `pdb_detail`, `pdb_home` |
| redirect target needs the object's pk | `rep_create`? **no** — it uses `crud_create` with the static `"projects:rep_list"`; `wdg_create`/`wdg_edit`/`wdg_delete`/`wdg_move` redirect to `projects:pdb_detail` with the parent pk, so they are hand-written |
| POST-only field write with a `.update()` | `rep_run`, `rep_freeze`, `rep_favorite`, `rep_delete`, `run_narrative`, `run_issue`, `run_archive`, `run_delete`, `pdb_delete` |
| returns a non-HTML response | `rep_csv`, `rep_json`, `run_csv` |
| uses the `crud_*` helpers verbatim | `rep_list`, `rep_create`, `rep_edit`, `run_list`, `pdb_list`, `pdb_edit` |

`rep_delete` / `pdb_delete` **do** use `crud_delete` (static `success_url` is enough); `wdg_delete` does not.

**R10 — redirect-back (`@require_POST` verbs that must return to the page the user was on).** Pinned helper
`redirect_back_or(request, fallback_name, **kwargs)` added to `apps/projects/views/_helpers.py` (verified: the
file has `org_units`, `clients`, `projects`, `resource_profiles`, `project_requests`, `owners`, `requirements`,
`critical_path_ids` and **no** `csv_safe` / `redirect_back_or` — both are added by 7.16 as surgical appends, per
CLAUDE.md rule 5 since two view modules need them). It reads `request.POST.get("next")` and validates it with
`url_has_allowed_host_and_scheme` (procurement's verified import) before trusting it; otherwise
`redirect(fallback_name, **kwargs)`. Used by `rep_favorite`, `wdg_move`, `wdg_delete`, `run_narrative`,
`run_issue`. `?next=` values are produced by the templates as `{{ request.path }}`.

### B2.1 `views/ReportingBusinessIntelligence/ReportingHome.py`

#### `rbi_home` — `render(request, "projects/reporting/home.html", ctx)` (hand-written; no `page_obj`)

| key | type | source | consumed by |
|---|---|---|---|
| `object_list` | list of `ProjectReport` (NOT a page) | `visible_reports(request).order_by("-last_run_at", "-id")[:5]` — `select_related("owner")` | the "recently run reports" strip; `{% for r in object_list %}` |
| `my_dashboard` | `ProjectDashboard` or `None` | `analytics.home_dashboard(request)` (B3) — the caller's `is_default`, else the shared tenant template for their audience, else `None` | the hero tile `{% if my_dashboard %}` |
| `recent_runs` | queryset ≤ 10 of `ProjectReportRun` | `visible_runs(request).select_related("report", "generated_by")[:10]` | the "latest frozen runs" table |
| `dashboards` | queryset ≤ 6 of `ProjectDashboard` | `visible_dashboards(request).annotate(annotation_count=Count("widgets"))[:6]` | the dashboard card row (reads `annotation_count`) |
| `sibling_boards` | `list[dict]` — `{"label": str, "url": str, "group": str, "module": str}` | built in-view from `analytics.SIBLING_BOARDS` (B3) through `reverse()`; **`url` is a resolved str, never a url name the template must reverse** | "Already-built reporting surfaces" panel — bullet 1's "50+ reports" answer |
| `library` | `list[dict]` — `{"type": str key, "label": str, "subject": str label, "url": str}` | `analytics.STANDARD_REPORTS` mapped to `report_standard?type=<key>` | the canned-report quick grid |
| `counts` | `dict[str,int]` — `{"reports": n, "dashboards": n, "runs": n, "issued": n}` | four `.count()` calls on the visible querysets — **never a table-wide count** | the KPI strip `{{ counts.reports }}` |
| `can_build` | `bool` | `True` when `request.tenant` is not None | gates the "New report" button (superuser with no tenant sees no CTAs) |

#### `report_library` — `render(request, "projects/reporting/library.html", ctx)`

| key | type | source | consumed by |
|---|---|---|---|
| `library` | `list[dict]`, one per `REPORT_TYPE_CHOICES` kind **in choice order**, `{"type","label","subject","subject_label","description","sections","is_canned","url","saved_count"}` | `analytics.STANDARD_REPORTS` + `ProjectReport.objects.filter(tenant=…, report_type=k).count()` batched in **one** `values("report_type").annotate(Count("id"))` read (no per-row loop) | the whole page; `{% for r in library %}` |
| `total_kinds` | `int` | `len(library)` | the "N standard reports" caption — the honest answer to "50+", which is `16 kinds × 4 scope axes` |
| `sibling_boards` | as `rbi_home` | same constant | the "engine you are not reusing" panel |
| `type_filter` | `str` | `request.GET.get("type", "").strip()` echo | narrows the list client-side; `{% if type_filter %}` banner |

`?type=` here is a **display filter only**; an unknown key leaves the full list (never an empty page, L11).

#### `report_standard` — `render(request, "projects/reporting/standard.html", ctx)` (the page that renders all 16 kinds)

GET params read: `type`, `project`, `portfolio`, `client`, `org_unit`, `from`, `to`, `as_of`.

| key | type | source | consumed by |
|---|---|---|---|
| `kind` | `str` — ALWAYS a valid `REPORT_TYPE_CHOICES` key | `request.GET.get("type")` if `in analytics.STANDARD_REPORTS` else **`"status_report"`** (junk never 500s and never blanks the page, L11) | every partial's `{% if kind == "…" %}` |
| `kind_meta` | `dict` — `{"label","subject","description","sections","drill"}` | `analytics.STANDARD_REPORTS[kind]` | the header block |
| `sections` | `list[dict]` — `{"area": str, "title": str}` | `kind_meta["sections"]` | `{% for s in sections %}` caption loop |
| `section_templates` | `list[str]` — **full template path strings**, computed in Python | `[f"projects/reporting/_standard_section_{s['area']}.html" for s in sections]` | `{% for t in section_templates %}{% include t %}{% endfor %}` — **no path building in the template**; an area with no partial is dropped by the view, not silently 500'd by `include` |
| `result` | `dict` — the whole payload | `analytics.standard_report(kind, request.tenant, params)` | the partials read `result.columns` / `result.rows` off the parent context |
| `summary` | `dict[str, str]` `{label: display-value}` | `result["summary"]` | KPI strip `{% if summary %}` |
| `summary_cards` | `list[dict]` — `{"label","value"}` | `analytics.summary_pairs(summary)` — **the view calls it, the template never iterates a dict for a strip** | the KPI cards |
| `columns` | `list[str]` | `result["columns"]` | `<thead>`; `colspan="{{ columns|length }}"` on the empty row |
| `rows` | `list[list]` — every cell `str`/`int`/`float`/`None` | `result["rows"]` (already capped + `_jsonable`d) | `<tbody>` `{% for row in rows %}{% for cell in row %}` |
| `chart_type` | `str` key of `CHART_CHOICES` | `result["chart_type"]` | `{% if chart_type in canvas_charts %}` discriminator |
| `chart_labels` | `list[str]` | `result["chart_labels"]` | the HTML fallback + the canvas payload |
| `chart_data` | `list[float]` | `result["chart_data"]` | ditto |
| `chart_config` | `list[dict]` — **0 or 1 entry**, `{"id": 0, "type","labels","data"}` | the view, only when `chart_type in CANVAS_CHARTS` and `chart_labels` is non-empty | `{{ chart_config|json_script:"rbi-report-chart" }}` + `<canvas id="wchart0">` (`id` 0 is the single-chart convention; `wchart0` is `wchart` + `0`) |
| `chart_rows` | `list[dict]` — `{"label": str, "value": num}` | `zip(chart_labels, chart_data)` in the view | the **HTML bar table** rendered for `HTML_CHARTS` kinds — this is what replaces template index gymnastics |
| `canvas_charts` | `tuple[str]` | the constant `CANVAS_CHARTS` imported into the context (a template cannot import) | `{% if chart_type in canvas_charts %}` |
| `caveats` | `list[str]` | `result["caveats"]` — includes the `(unassigned)` denominator note (B3) | the amber caveat list |
| `truncated` | `bool` | `result["truncated"]` — set by analytics as `pre_cap_count > analytics.MAX_REGISTER_ROWS` (2000), **never** `len(rows) == cap` (B3.5) | the truncation strip, `{% if truncated %}` |
| `as_of` | `date` object | resolved from `?as_of` (via `as_db_int`-style date parsing helper `_parse_date`) else `timezone.localdate()` | `{{ as_of|date:"d M Y" }}` — display only, **never inside a json_script key** |
| `active_filters` | `dict[str,str]` — `{"project","portfolio","client","org_unit","from","to"}` | the six raw echo strings | the filter-bar `selected` comparisons via `active_filters.project\|stringformat:"d"` … — see R3 |
| `projects` / `portfolios` / `clients` / `org_units` | querysets | `views/_helpers.projects(tenant)`, `Portfolio.objects.filter(tenant=…).order_by("name")`, `clients(tenant)`, `org_units(tenant)` | the four scope `<select>`s |
| `report_types` | `list[tuple]` | `ProjectReport.REPORT_TYPE_CHOICES` (class attr, A1.4) | the kind `<select>`, compared as `{% if kind == t.0 %}` |
| `range_choices` | `list[tuple]` | `analytics.PRESET_RANGES` (`RANGE_CHOICES` minus `custom`) | the quick-window links |
| `save_report_url` | `str` | `reverse("projects:rep_create") + "?type=" + kind + "&project=…" + "&from=…"` — **querystring-built in the view** | the "Save this as a report" CTA |
| `export_urls` | `list[dict]` — `{"label","url"}`; **`[]` on this page** | nothing to export until it is a saved report or a frozen run (D22) | `{% if export_urls %}` — the block renders nothing, it never 500s on `{% url %}` |

#### `exec_pack` — `render(request, "projects/reporting/exec_pack.html", ctx)` (print page)

GET params: `portfolio`, `project`, `as_of`.

| key | type | source | consumed by |
|---|---|---|---|
| `bands` | `list[dict]` — `{"project": Project, "portfolio": str, "program": str, "rating": str, "rag_css": str, "streak_weeks": int, "streak_label": str, "cpi": float, "spi": float, "cv": str, "sv": str, "hours": float, "margin_pct": str, "drill_url": str}` | `analytics.exec_pack(request.tenant, portfolio=…, as_of=…)` | the RAG band table; `class="badge {{ b.rag_css }}"`, `{{ b.streak_label }}` = "amber · 6 weeks" |
| `rag_series` | `list[dict]` — `{"label": str, "green": int, "amber": int, "red": int}` | `analytics.rag_streak()` month buckets over `visible_runs`-scoped issued runs reading `data["rating"]` | the persistence sparkline (`chart_config`-shaped canvas is NOT used here; it is an HTML mini-table) |
| `chart_config` / `chart_rows` / `canvas_charts` | as B2.1 `report_standard` | the exec payload's portfolio→program→project rollup | the trend canvas + its HTML fallback |
| `summary` / `summary_cards` | as above | `exec_pack()["summary"]` | the pack header KPI strip |
| `narrative_run` | `ProjectReportRun` or `None` | `visible_runs(request).filter(report__report_type="steering_pack", status="issued").first()` — Meta ordering makes it the latest | the commentary block; **`{% if narrative_run %}` guards it and its empty state says "No issued steering pack yet"** |
| `narrative` | `str` | `narrative_run.narrative` when present else `""` | the body paragraph (auto-escaped, no `|safe`) |
| `as_of` | `date` | `?as_of` else `timezone.localdate()` | header + the print title |
| `portfolio` | `Portfolio` or `None` | `visible`-scoped… it is a plain `Portfolio.objects.filter(tenant=request.tenant, pk=as_db_int(request.GET.get("portfolio"))).first()` | header scope label |
| `active_filters` | `dict[str,str]` — `{"portfolio","project"}` | echoes | the filter bar |
| `portfolios` / `projects` | querysets | helpers above | the filter bar |
| `print_mode` | `bool` | `request.GET.get("print") == "1"` | adds `class="printing"` + hides the chrome (`.no-print`) — the browser-print "PDF" path |
| `drills` | `list[dict]` — `{"label","url"}` | `reverse()` of `projects:pfm_dashboard`, `projects:financial_pnl`, `projects:risk_analysis`, `projects:utilization_dashboard` (all verified url names of sibling sub-modules) | the "deep enough?" link row — 7.16 links, never re-derives |

### B2.2 `views/ReportingBusinessIntelligence/ProjectReports.py`

Template constants at module top (procurement's shape): `TEMPLATE_LIST`, `TEMPLATE_DETAIL`, `TEMPLATE_FORM`.

#### `rep_list` — `crud_list(request, qs, "projects/reporting/report/list.html", …)`

`qs = visible_reports(request).select_related("owner", "project", "portfolio", "client", "org_unit")`

| key | type | source | consumed by |
|---|---|---|---|
| `object_list` | `list[ProjectReport]` (this page's slice) | **`crud_list`** | `{% for r in object_list %}` — the register table |
| `page_obj` | `Page` | **`crud_list`** | `{% include "partials/pagination.html" %}` |
| `q` | `str` | **`crud_list`** (stripped) | the search box `value="{{ q }}"` |
| `report_type_choices` | `list[tuple]` | `ProjectReport.REPORT_TYPE_CHOICES` | `#report_type` `<select>`; `{% if type_filter == t.0 %}selected` |
| `subject_choices` | `list[tuple]` | `ProjectReport.SUBJECT_CHOICES` | `#subject` |
| `chart_choices` | `list[tuple]` | `ProjectReport.CHART_CHOICES` | `#chart_type` |
| `type_filter` | `str` | `request.GET.get("report_type","").strip()` | the `selected` echo — the **param is `report_type`, the echo is `type_filter`** (pinned; do not rename either) |
| `subject_filter` | `str` | `request.GET.get("subject","").strip()` | ditto |
| `chart_filter` | `str` | `request.GET.get("chart_type","").strip()` | ditto |
| `project_filter` | `str` | `request.GET.get("project","").strip()` | `{% if project_filter\|stringformat:"d" == p.pk\|stringformat:"d" %}` (R3) |
| `owner_filter` | `str` | `request.GET.get("owner","").strip()` | same, on the owner dropdown |
| `shared_filter` | `str` | `request.GET.get("shared","").strip()` | `{% if shared_filter == "True" %}selected{% endif %}` on the `True`/`False` options (R3) |
| `favorite_filter` | `str` | `request.GET.get("favorite","").strip()` | ditto |
| `projects` | queryset | `views/_helpers.projects(request.tenant)` | the project `<option>` list |
| `owners` | queryset | `views/_helpers.owners(request.tenant)` | the owner `<option>` list |

`filters=` (the `crud_list` triples): `("report_type","report_type",False)`, `("subject","subject",False)`,
`("chart_type","chart_type",False)`, `("project","project_id",True)`, `("owner","owner_id",True)`,
`("shared","is_shared",False)`, `("favorite","is_favorite",False)`. **No relation-hop lookups** (`report__…`)
anywhere in `filters` — `_enum_values` bails on a `__` and the junk value would then silently empty the register
(L11). `search_fields=["number","name","description","notes"]`.

#### `rep_create` — `crud_create(request, form_class=ProjectReportForm, template="projects/reporting/report/form.html", success_url="projects:rep_list", extra_context=…)`

| key | type | source | consumed by |
|---|---|---|---|
| `form` | `ProjectReportForm` (bound or fresh, built with `tenant=request.tenant`) | **`crud_create`** | `{% include "partials/form_field.html" %}` per bound field |
| `is_edit` | `False` | **`crud_create`** | the header "New saved report" vs "Edit" |
| `report_type_choices` | `list[tuple]` | `ProjectReport.REPORT_TYPE_CHOICES` | the "start from a canned kind" JS + the step-1 caption |
| `measure_choices` | `list[tuple]` | `ProjectReport.MEASURE_CHOICES` | the `measures` checkbox grid labels (the field itself already has them from the form, A2.1 — this copy is for the "2 of 3 chosen" counter) |
| `dimension_choices` | `list[tuple]` | `ProjectReport.DIMENSION_CHOICES` | the axis pickers |
| `canned_axes` | `dict[str, dict]` — `{report_type_key: {"subject","measures","dimension_1","dimension_2","chart_type"}}` | `analytics.STANDARD_REPORTS[k]["axes"]` | the builder's "prefill from a canned report" step. **A2's `chart_rules` promise lands here** (D23) |
| `form_action_url` | `str` | `reverse("projects:rep_create")` | the `<form action>` (explicit, because the page is reached from a `?type=` querystring link) |
| `initial_type` | `str` | `request.GET.get("type","").strip()` if a valid key else `""` | the pre-selected canned kind on a `?type=` entry |

**There is no `obj` on `rep_create`** — `crud_create` does not pass one, and the template must not read `{{ obj… }}`.

#### `rep_detail` — **the live result page** (hand-written; `render(request, "projects/reporting/report/detail.html", ctx)`)

| key | type | source | consumed by |
|---|---|---|---|
| `obj` | `ProjectReport` | `get_object_or_404(visible_reports(request).select_related(…), pk=pk)` — R7 | header (`obj.number`, `obj.name`), `{% if obj.is_favorite %}`, `{{ obj.window_label }}`, `{{ obj.scope_label }}`, `{{ obj.metric_labels }}`, `{{ obj.dimension_labels }}`, `{{ obj.chart_type }}` |
| `result` | `dict` | `analytics.compute_report(obj)` — **the ONLY compute call on this page** | the shared result partials |
| `summary` / `summary_cards` / `columns` / `rows` / `chart_type` / `chart_labels` / `chart_data` / `chart_config` / `chart_rows` / `canvas_charts` / `caveats` / `truncated` | exactly as B2.1 `report_standard` | unpacked from `result` by the view (`ctx.update(analytics.flatten(result))` is **not** allowed to be magic — the view lists the twelve keys explicitly, same names as `standard.html`, so the two pages share `projects/reporting/_result_table.html` and `_result_chart.html` verbatim) | the result region |
| `rating` | `str` `""`/`green`/`amber`/`red` | `result["rating"]` | the RAG badge `{{ rag_css }}` |
| `rag_css` | `str` | `{"green":"badge-green","amber":"badge-amber","red":"badge-red"}.get(rating, "badge-muted")` — **the same map the run property uses** (A1.5, L33) | the badge class |
| `sections` / `section_templates` | as B2.1 | only when `obj.is_canned` (from `STANDARD_REPORTS[obj.report_type]["sections"]`); **`[]` for `report_type == "custom"`** | canned kinds render their sections; a custom report renders the generic result partials only (D24) |
| `runs` | queryset ≤ 10 of `ProjectReportRun` | `obj.runs.filter(tenant=request.tenant).select_related("generated_by")[:10]` | the "frozen history" side panel, `{% for run in runs %}` + an `{% empty %}` "Nothing frozen yet — Freeze to open a run" |
| `is_owner` | `bool` | `obj.owner_id == request.user.id` | the "Private to you" badge |
| `can_run` | `bool` | `request.tenant is not None` | gates the Run / Freeze buttons |
| `freeze_url`, `csv_url`, `json_url`, `run_url` | `str` | `reverse("projects:rep_freeze", args=[obj.pk])` etc. | the "copy these links" panel only — **every in-page button uses `{% url %}`, never these** (they exist because the plan pins the keys; a template that reads them must survive them being absent, and none does) |

**`last_run_at` is NOT touched by this view** — opening the page is not running the report (procurement's rule,
restated in the module docstring).

#### `rep_edit` — `crud_edit(request, model=ProjectReport, pk=pk, form_class=ProjectReportForm, template="projects/reporting/report/form.html", success_url="projects:rep_list", extra_context=…)`

Keys: `form`, `obj`, `is_edit=True` from **`crud_edit`**, **plus** `report_type_choices`, `measure_choices`,
`dimension_choices`, `canned_axes`, `form_action_url` = `reverse("projects:rep_edit", args=[pk])`.
⚠️ **`crud_edit` fetches `ProjectReport.objects.filter(tenant=request.tenant)` internally — it does NOT apply
the ACL.** Pinned: `rep_edit` is therefore **hand-written** for the fetch and calls `crud_edit` only after
confirming visibility:
```python
obj = get_object_or_404(visible_reports(request), pk=pk)   # 404 before crud_edit sees the pk
```
…is NOT how it works (the helper re-fetches). **Resolution pinned:** `rep_edit` does its own
`get_object_or_404(visible_reports(request), pk=pk)` for the *permission* check and then delegates to
`crud_edit` with that same `pk` — a second, harmless fetch on the same tenant — so the ACL still 404s a private
colleague object first. `rep_list`'s row links are only ever generated from the visible queryset, so a hand-typed
pk is the attack path this covers. The same shape applies to `pdb_edit`. **`test_reporting_security.py` asserts
it** (B6).

#### `rep_delete` — `crud_delete(request, model=ProjectReport, pk=pk, success_url="projects:rep_list")`
`@login_required @require_POST`. No context (R1). **`get_object_or_404` inside the helper is tenant-scoped but
NOT ACL-scoped** — same resolution as `rep_edit`: a `get_object_or_404(visible_reports(request), pk=pk)` guard
line before delegating. Deleting a report CASCADEs its runs (A1.6) — the confirm text says
`Delete this report and its N frozen runs?` and the count comes from the JS-populated data attribute, never a
context key.

#### `rep_run` — `@login_required @require_POST`, no template
Body: guard-fetch → `result = analytics.compute_report(obj)` →
`ProjectReport.objects.filter(pk=pk, tenant=request.tenant).update(last_run_at=timezone.now())`
(`.update()` so `auto_now` on `updated_at` cannot claim the definition changed — A1.0) →
`messages.success(request, f"{row_count} rows.")` → `redirect("projects:rep_detail", pk=obj.pk)`.
Audit `action="update"`, `changes={"verb": "run", "rows": result["row_count"]}`.
`result["row_count"]` is `len(rows)` and is a view-side int, never a payload key (B3 keeps the payload at nine
keys).

#### `rep_freeze` — `@login_required @require_POST`, no template
One `transaction.atomic()`: guard-fetch → compute → `ProjectReportRun.objects.create(tenant=…, report=obj,
title=obj.name, period_from=resolved_from, period_to=resolved_to, as_of=obj.as_of or timezone.localdate(),
generated_by=request.user, summary=result["summary"], data=<the other eight payload keys>,
row_count=len(result["rows"]), narrative=analytics.narrative_seed(request.tenant, obj, result))` →
`ProjectReport.objects.filter(pk=…, tenant=…).update(last_run_at=timezone.now())`.
Audit `action="freeze"`, `changes={"verb": "freeze", "rows": n}`. → `redirect("projects:run_detail", pk=run.pk)`.
**The only writer of run rows in the entire app** (A1.1).

#### `rep_favorite` — `@login_required @require_POST`, no template
`new = not obj.is_favorite`; `ProjectReport.objects.filter(pk=…, tenant=…).update(is_favorite=new)`;
`messages.success(request, "Added to / removed from favourites.")`; audit `action="toggle"`,
`changes={"verb": "favorite", "is_favorite": str(new)}`; → `redirect_back_or(request, "projects:rep_list")`.

#### `rep_csv` — returns `HttpResponse` (**no template, no context**)
Guard-fetch by `visible_reports(request)` → `compute_report(obj)` →
`_csv_response(f"{obj.number}.csv", result["columns"], result["rows"])` → audit `action="export"`,
`changes={"verb": "csv", "rows": n}`. Headers `text/csv; charset=utf-8` +
`Content-Disposition: attachment; filename="REP-00001.csv"`; **every cell through `csv_safe`**; rows capped at
`analytics.MAX_EXPORT_ROWS`. Filename is built from the system-assigned `number` only, never from `obj.name`
(a newline or a quote in user text would land in a response header — procurement's verified comment).

#### `rep_json` — returns `JsonResponse` (**no template, no context**)
`{"meta": {"report": obj.number, "name": obj.name, "kind": obj.report_type, "scope": obj.scope_label,
"window": obj.window_label, "generated_at": timezone.now().isoformat(), "row_count": n, "truncated": bool},
"columns": […], "rows": […], "summary": {…}, "chart": {"type","labels","data"}, "caveats": […]}`.
`safe=True` is **not** needed (R5 guarantees plain types); a `Decimal` reaching `JsonResponse` is a build
failure, not a runtime surprise. Audit `action="export"`, `changes={"verb": "json"}`. This is the payload 7.18's
token feed will hang off — say so in the docstring, and say the feed itself is 7.18's (honesty rule from the
plan).

### B2.3 `views/ReportingBusinessIntelligence/ReportRuns.py`

#### `run_list` — `crud_list(request, qs, "projects/reporting/reportrun/list.html", …)`

`qs = visible_runs(request).select_related("report", "generated_by", "issued_by")`

| key | type | source | consumed by |
|---|---|---|---|
| `object_list` | `list[ProjectReportRun]` | **`crud_list`** | `{% for run in object_list %}` — reads `run.title`, `run.report.name`, `run.get_status_display`, `run.row_count`, `run.generated_at`, `run.rating`, `run.rag_css` |
| `page_obj`, `q` | as R1 | **`crud_list`** | pagination partial + search box |
| `status_choices` | `list[tuple]` | `ProjectReportRun.STATUS_CHOICES` (= `RUN_STATUS_CHOICES`) | `#status` select, `{% if status_filter == s.0 %}selected` |
| `reports` | queryset | `visible_reports(request).order_by("name")` | `#report` select |
| `owners` | queryset | `views/_helpers.owners(request.tenant)` | `#generated_by` select |
| `status_filter` | `str` | echo of `status` | R3 |
| `report_filter` | `str` | echo of `report` | `{% if report_filter\|stringformat:"d" == r.pk\|stringformat:"d" %}` |
| `owner_filter` | `str` | echo of `generated_by` | R3 |
| `favorite_filter` — **absent** | — | there is no `is_favorite` on a run | the template must not offer one |

`filters=[("status","status",False), ("report","report_id",True), ("generated_by","generated_by_id",True)]`;
`search_fields=["title","narrative"]`. **Note the page's own empty state** must read "No reports have been frozen
yet" — the seeder ships **zero runs** by design, so this is the first thing a fresh workspace sees.

#### `run_detail` — hand-written, `render(request, "projects/reporting/reportrun/detail.html", ctx)`
**Recomputes nothing.** `test_reporting_views.py` patches `analytics.compute_report` to raise and the page must
still return 200 (B6).

| key | type | source | consumed by |
|---|---|---|---|
| `obj` | `ProjectReportRun` | `get_object_or_404(visible_runs(request).select_related("report","generated_by","issued_by","document"), pk=pk)` | header: `obj.title`, `{{ obj.generated_at\|date }}`, `{{ obj.as_of\|date }}`, `{{ obj.row_count }}`, `{{ obj.get_status_display }}`, `{{ obj.rag_css }}`, `{{ obj.summary_cards }}` |
| `report` | `ProjectReport` | `obj.report` (already `select_related`) | the "ran from" breadcrumb + `report.scope_label` |
| `summary` | `dict[str,str]` | `obj.summary` — the stored JSON | `{% if summary %}` |
| `summary_cards` | `list[dict]` | `obj.summary_cards` (**the A1.5 model property**, not a view rebuild) | the KPI strip |
| `columns` / `rows` | `list[str]` / `list[list]` | `obj.columns` / `obj.rows` (**A1.5 properties** over `obj.data`) | the frozen table |
| `chart_type` | `str` | `obj.chart_type` property | discriminator |
| `chart_labels` / `chart_data` | `list` | `obj.chart_labels` / `obj.chart_data` properties | canvas + fallback |
| `chart_config` | `list[dict]` 0/1 | the view, from those two + `chart_type in CANVAS_CHARTS`, `{"id": obj.pk, "type", "labels", "data"}` | `json_script:"rbi-report-chart"` + `<canvas id="wchart{{ obj.pk }}">` |
| `chart_rows` | `list[dict]` | `zip(...)` in the view | HTML fallback |
| `canvas_charts` | `tuple` | the `CANVAS_CHARTS` constant | R6 discriminator |
| `caveats` | `list[str]` | `obj.caveats` property | amber list |
| `truncated` | `bool` | `obj.truncated` property | the "this run's register was capped at 2000 rows" strip |
| `rating` / `rag_css` | `str` / `str` | `obj.rating` / `obj.rag_css` properties | the badge |
| `narrative` | `str` | `obj.narrative` | the commentary `<div>` (escaped, `linebreaksbr`) |
| `is_draft` / `is_issued` / `is_archived` / `is_editable` | `bool` ×4 | the A1.5 properties | which verb buttons render (`{% if is_editable %}` → the narrative form) |
| `runs` | queryset ≤ 5 | `ProjectReportRun.objects.filter(tenant=request.tenant, report=report).exclude(pk=obj.pk)[:5]` | the "earlier runs of this question" strip + the trend link |
| `csv_url` | `str` | `reverse("projects:run_csv", args=[obj.pk])` | the copy panel only (see `rep_detail`) |
| `document` | `core.Document` or `None` | `obj.document` | the "filed against" row + `{% if document %}` |

#### `run_narrative` — `@login_required @require_POST`, no template
`obj = get_object_or_404(visible_runs(request), pk=pk)`; `form = ProjectReportNarrativeForm(request.POST,
instance=obj, tenant=request.tenant)`; valid → `form.save()` + audit `update` / `changes={"verb":"narrative"}` +
`messages.success`; **invalid → `messages.error(request, " · ".join(form.errors["narrative"]))`** and the same
redirect. There is no re-render path: a POST-only verb cannot return a form page, and the editor is an inline
`<textarea>` on `run_detail`. Not-draft → the form's `clean()` produces the error string above (A2.2), so no
separate 403 branch exists. → `redirect("projects:run_detail", pk=obj.pk)`.

#### `run_issue` — `@login_required @require_POST`, no template
`ProjectReportIssueForm(request.POST, instance=obj, tenant=request.tenant)`; valid →
`run = form.save(commit=False)`; then `run.status = "issued"`, `run.issued_by = request.user`,
`run.issued_at = timezone.now()`; `run.save()`; audit `action="issue"`,
`changes={"verb": "issue", "document": str(run.document_id or "")}`; `messages.success(request,
f"{run.title} issued.")`; → `redirect("projects:run_detail", pk=run.pk)`.
No file upload (A2.2): the `document` field is a `ModelChoiceField` over existing tenant documents.

#### `run_archive` — `@login_required @require_POST`, no template
`obj.status = "archived"`; `obj.save()` (an already-archived run → `messages.info` and no write, so a double-click
cannot produce a second audit row). Audit `action="archive"`, `changes={"verb": "archive"}`.
→ `redirect("projects:run_detail", pk=obj.pk)`.

**⚠️ Pinned write split (the `auto_now` trap).** `.update()` bypasses `auto_now`, so `updated_at` would go stale
on a row the audit trail claims changed. Therefore:
* **`.update()`** — `rep_run` (`ProjectReport.last_run_at`) and `rep_favorite` (`ProjectReport.is_favorite`) ONLY.
  Those two deliberately must NOT move `ProjectReport.updated_at`, which means "the definition was edited" (A1.0).
* **`obj.save()`** — every `ProjectReportRun` write (`run_narrative`, `run_issue`, `run_archive`) and every child
  write (`wdg_move`'s position swaps), because D5 gave the run an `updated_at` precisely so "when did this pack
  last change" has an honest answer.

#### `run_delete` — `@login_required @require_POST @tenant_admin_required`, no template
Guard-fetch via `visible_runs(request)` → `write_audit_log(request.user, obj, "delete", changes={"verb":
"delete", "report": obj.report.number})` **before** `obj.delete()` (the audit row must outlive the object and
still name it) → `messages.success` → `redirect("projects:run_list")`.

#### `run_csv` — returns `HttpResponse` (**no template**)
Straight from `obj.columns` / `obj.rows` — **no recompute, so the file matches the page** (procurement's rule).
`_csv_response(f"{obj.report.number}-{obj.pk}.csv", …)` (the run has no `number` of its own, A1.1, so the name is
parent-number + pk — system-assigned parts only). Audit `action="export"`, `changes={"verb":"csv","run":pk}`.

### B2.4 `views/ReportingBusinessIntelligence/ProjectDashboards.py`

#### `pdb_home` — hand-written, `render(request, "projects/reporting/dashboard_home.html", ctx)`

| key | type | source | consumed by |
|---|---|---|---|
| `dashboard` | `ProjectDashboard` or `None` | `analytics.home_dashboard(request)` (B3) | `{% if dashboard %}` → the grid; `{% else %}` → the empty state |
| `rendered_widgets` | `list[dict]` — `{"widget","result","span"}` | `compute_widget(w)` per `dashboard.widgets.filter(tenant=request.tenant)`; `span` from crm's verified map `{"small":1,"medium":2,"large":3,"full":cols}` clamped with `min(…, cols)` | **`projects/reporting/_widget_grid.html`** (shared with `pdb_detail`, so one markup source) |
| `chart_configs` | `list[dict]` per R6 | the view, only `result["kind"] == "series"` **and** `w.chart_type in CANVAS_CHARTS` | `{{ chart_configs\|json_script:"rbi-charts" }}` |
| `cols` | `int` 1/2/3 | `{"one":1,"two":2,"three":3}.get(dashboard.layout, 2)` — **the view computes it, not `obj.column_span`** (`column_span` is the 12-col CSS span from A1.5; `cols` is the grid column count the template multiplies into `repeat({{ cols }}, …)`) | the grid `style` |
| `active_range` | `str` key | `dashboard.default_range` (`?range=` is **not** accepted on home — pinned; only `pdb_detail` carries the override, so "my home" is always the authored window). Home therefore passes **no `range_choices`** | the tile windows fed into `compute_widget(w, date_range=…)`; the header badge reads `active_range_label` instead |
| `active_range_label` | `str` | `dict(RANGE_CHOICES)[active_range]` | the badge (a template cannot look up a dict by a variable key without `{% with %}` gymnastics) |
| `other_dashboards` | queryset ≤ 4 | `visible_dashboards(request).exclude(pk=dashboard.pk).annotate(…)` (exclude is harmless when `dashboard is None`) | the "switch view" strip |
| `empty` | `bool` | `dashboard is None or not rendered_widgets` | the "create your dashboard" CTA |
| `create_url` / `detail_url` | `str` | `reverse("projects:pdb_create")` / `reverse("projects:pdb_detail", args=[…])` (`""` when no dashboard) | the CTAs |

#### `pdb_list` — `crud_list(request, qs, "projects/reporting/dashboard/list.html", …)`
`qs = visible_dashboards(request).select_related("owner").annotate(annotation_count=Count("widgets"))`

| key | type | source | consumed by |
|---|---|---|---|
| `object_list` | `list[ProjectDashboard]` | **`crud_list`** | `{% for d in object_list %}` — **reads `d.annotation_count`, NOT `d.widget_count`** (the property would fire one COUNT per row; A1.5 pins both names for exactly this reason) |
| `page_obj`, `q` | as R1 | **`crud_list`** | partial + search |
| `audience_choices` | `list[tuple]` | `ProjectDashboard.AUDIENCE_CHOICES` | `#audience` |
| `layout_choices` | `list[tuple]` | `ProjectDashboard.LAYOUT_CHOICES` | `#layout` |
| `owners` / `projects` | querysets | `_helpers.owners(tenant)` / `_helpers.projects(tenant)` | the two FK selects |
| `audience_filter`, `layout_filter`, `owner_filter`, `project_filter`, `shared_filter` | `str` ×5 | GET echoes | R3, `|stringformat:"d"` on the two pk ones |

`filters=[("audience","audience",False), ("layout","layout",False), ("owner","owner_id",True),
("project","project_id",True), ("shared","is_shared",False)]`; `search_fields=["number","name","description"]`.

#### `pdb_detail` — hand-written, `render(request, "projects/reporting/dashboard/detail.html", ctx)`

| key | type | source | consumed by |
|---|---|---|---|
| `obj` | `ProjectDashboard` | `get_object_or_404(visible_dashboards(request).select_related("owner","project","portfolio"), pk=pk)` | header `obj.number`, `obj.name`, `{{ obj.get_audience_display }}`, `obj.is_template`, `obj.is_shared`, `{{ obj.column_span }}` |
| `active_range` | `str` key | `rng = request.GET.get("range","").strip()`; `active_range = rng if rng in dict(RANGE_KEYS) and rng != "custom" else obj.default_range` — **a junk `?range=` silently falls back (L11) and `custom` is refused (A1.2 rule 4)** | every tile's window + the switcher's `selected` state |
| `active_range_label` | `str` | `dict(ProjectDashboard.RANGE_CHOICES)[active_range]` | the header badge |
| `range_choices` | `list[tuple]` | `analytics.PRESET_RANGES` (6, no `custom`) | the window switcher `{% for k,l in range_choices %}<a href="{% url 'projects:pdb_detail' obj.pk %}?range={{ k }}" {% if k == active_range %}class="active"{% endif %}` — **compares the raw key, never a label** |
| `rendered_widgets` | `list[dict]` `{"widget","result","span"}` | `analytics.compute_widget(w)` per tile, each tile narrowed to `active_range` (B3 — the override is applied **inside `compute_widget`'s `start,end`**, via the optional `date_range=` arg, so no tile mutates its own model row) | `_widget_grid.html` |
| `chart_configs` | `list[dict]` | R6 filter over `rendered_widgets` | `json_script:"rbi-charts"` |
| `cols` | `int` | the `layout` map above | the grid |
| `widget_add_url` | `str` | `reverse("projects:wdg_create", args=[obj.pk])` | the "Add tile" button (also `{% url %}`-ed in the template; the key exists because the empty state is a JS-injected card) |
| `is_owner` | `bool` | `obj.owner_id == request.user.id` | the "Private to you" badge |
| `can_edit` | `bool` | `is_owner or obj.is_shared and tenant-admin-or-superuser` (crm's `_can_share_dashboards` shape) | Edit/Delete/tile-management affordances |
| `empty` | `bool` | `not rendered_widgets` | the "no tiles yet" card |
| `home_url` | `str` | `reverse("projects:pdb_home")` | the breadcrumb |

⚠️ `pdb_detail` **must not** pass a `page_obj` (there is no pagination over tiles — the grid is bounded by
`MAX_TILES_PER_DASHBOARD = 24`, B3) and `dashboard/detail.html` therefore does **not** include the pagination
partial.

#### `pdb_create` / `pdb_edit`
`pdb_create` = `crud_create(form_class=ProjectDashboardForm,
template="projects/reporting/dashboard/form.html", success_url="projects:pdb_list", extra_context=…)` ⇒
`form`, `is_edit=False` + `audience_choices`, `layout_choices`, `range_choices` (= `PRESET_RANGES`).
`pdb_edit` = `crud_edit(model=ProjectDashboard, …, template="projects/reporting/dashboard/form.html",
success_url="projects:pdb_detail")` ⇒ `form`, `obj`, `is_edit=True` + the same three. **Both fetch through
`visible_dashboards(request)` first** (R7, same guard pattern as `rep_edit`). `is_default` / `owner` are not on
either form (A2.3), so no context key offers them.

#### `pdb_delete` — `@login_required @require_POST`
Guard-fetch by `visible_dashboards(request)`, then `crud_delete(model=ProjectDashboard, pk=pk,
success_url="projects:pdb_list")`. Deleting a dashboard CASCADEs its tiles (A1.6).

### B2.5 `views/ReportingBusinessIntelligence/DashboardWidgets.py`
All four resolve the **parent dashboard** through `visible_dashboards(request)` (R7) and share
`_widget_context(dashboard)` which returns the four choice keys below — so create and edit cannot drift.

| key | type | source | consumed by | present on |
|---|---|---|---|---|
| `form` | `DashboardWidgetForm` | the view (built with `tenant=request.tenant`) | both widget pages | `wdg_create`, `wdg_edit` |
| `is_edit` | `bool` | the view | the header + the `<form action>` | both |
| `obj` | `DashboardWidget` | the view | the edit page's "tile of {{ obj.dashboard.name }}" line | **`wdg_edit` ONLY** — its absence on `wdg_create` is the L8 trap this table exists to catch |
| `dashboard` | `ProjectDashboard` | the parent, in BOTH cases | the breadcrumb, the cancel link, the `<h2>Tiles on {{ dashboard.name }}</h2>` | both |
| `metric_choices` | `list[tuple]` | `DashboardWidget.WIDGET_METRIC_CHOICES` | the metric `<select>`'s optgroup headers + the JS hint | both |
| `chart_choices` | `list[tuple]` | `DashboardWidget.CHART_CHOICES` | the chart `<select>` | both |
| `size_choices` | `list[tuple]` | `DashboardWidget.SIZE_CHOICES` | the size `<select>` | both |
| `range_choices` | `list[tuple]` | `analytics.PRESET_RANGES` — narrowed so the tile dropdown never offers `custom` (A1.3 rule 4) | the window `<select>` | both |
| `chart_rules` | `dict[str, list[str]]` | `analytics.chart_rules()` | `{{ chart_rules\|json_script:"rbi-chart-rules" }}` + the JS that prunes the chart dropdown (A2.4's promise, **the only place this key lives**) | both |
| `cancel_url` | `str` | `reverse("projects:pdb_detail", args=[dashboard.pk])` | the Cancel button | both |

`wdg_create`: on valid POST → `form.instance.tenant = dashboard.tenant`;
`form.instance.dashboard = dashboard`; `form.instance.position = (dashboard.widgets.aggregate(m=Max("position"))["m"] or 0) + 1`;
`obj.save()`; audit `create`; → `redirect("projects:pdb_detail", pk=dashboard.pk)`.
`wdg_edit`: `crud_edit` is **not** used (its `get_object_or_404` is tenant-only and its redirect cannot name the
parent) — the view is hand-written with the same POST/GET shape, `audit="update"`.
`wdg_delete`: hand-written (`obj.save`-less `obj.delete()`, audit `delete`, redirect to the parent detail).
`wdg_move`: `@login_required @require_POST`; `direction = request.POST.get("direction","").strip()`;
**anything but `up`/`down` → `messages.error` + redirect back (L11)**; swap = fetch the neighbour by
`position` (`<` for up / `>` for down, `order_by("-position","id")` for up, `order_by("position","id")` for down,
`filter(tenant, dashboard=obj.dashboard).exclude(pk=obj.pk)`), then `DashboardWidget.objects.filter(pk__in=[a,b])
 …` writes **two `.update(position=…)` calls inside one `transaction.atomic()`**, with a renumber fallback when
positions tie (`analytics.renumber_tiles(dashboard)` when the neighbour's position equals the moved tile's).
Audit `action="toggle"`, `changes={"verb":"move","direction":direction}`. → `redirect_back_or(request,
"projects:pdb_detail", pk=obj.dashboard_id)`.

#### `wdg_create` / `wdg_edit` **form validation error rendering**
Both templates render `{% if form.non_field_errors %}` and each bound field's errors inline — because the
metric↔chart refusal (A2.4) is the most common user error on the page and a silent re-render would look like a
dead button.

## B3 — `apps/projects/analytics.py` registry contract

**One new flat file at the app root** — `apps/projects/analytics.py` (verified **absent** as of this pass:
`ls apps/projects/analytics.py` → no such file). CLAUDE.md backend rule 8 pins `analytics.py` flat at the app
root, exactly like `apps/crm/analytics.py` (471 lines) and `apps/procurement/analytics.py`. It is **not** a
sub-package module and it is **not** re-exported from `models/`.

### B3.0 Import direction (the hard rule, restated from A0)

```
models  ←── forms  ←── views
   ↑                       ↑
   └──── analytics ────────┘        analytics imports models; views import analytics
```

* `analytics.py` may import **only** models (+ stdlib, `django.db.models`, `django.utils`, and the
  `_choices.py` constants). It never imports `forms`, `views`, `apps.core.crud`, or `request`.
* **`models/ReportingBusinessIntelligence/*.py` never import `analytics`** (A0/A1.3/D10). Every metric↔chart
  validation a view or form needs comes from `analytics.allowed_charts()` / `chart_rules()` or the form — never
  from a model property.
* The `*_CHOICES` lists are imported **from** `models/ReportingBusinessIntelligence/_choices.py`; analytics does
  not re-declare a second vocabulary. **A test asserts the key sets are equal** (A1.4), which is the only guard
  against a dropdown offering a metric that computes to nothing.
* `analytics.py` reads `apps.projects.views` **never**, and holds **url names as strings** only (the `drill_url_name`
  values). It must not call `reverse()` — a bad name would then surface at import time in an unrelated request
  path; the smoke sweep in B5 resolves them instead.

### B3.1 Module constants

| name | type | content |
|---|---|---|
| `MEASURES` | `dict[str, dict]` | one per `MEASURE_CHOICES` key (24): `{"label", "kind": "money"\|"pct"\|"num"\|"hours"\|"days", "unit"}` |
| `DIMENSIONS` | `dict[str, dict]` | one per `DIMENSION_CHOICES` key (18): `{"label", "field": <ORM path or callable key>, "order"}` — `none` maps to `{"field": None}` |
| `SUBJECTS` | `dict[str, dict]` | one per `SUBJECT_CHOICES` key (16): `{"label", "model": <Model class>, "date_field": str, "open_q": Q, "text_field": str}` |
| `PRESET_RANGES` | `list[tuple]` | `RANGE_CHOICES` **minus** `custom` (6 rows) — the only window list a dashboard/tile page may offer (A1.2 rule 4, A1.3 rule 4) |
| `MAX_REGISTER_ROWS` | `int = 2000` | the compute cap (7.5's `_REGISTER_CAP = 2000` at `views/RiskManagement/RiskAnalysis.py:55`, same number by design) |
| `MAX_EXPORT_ROWS` | `int = 5000` | the CSV writer cap (procurement's verified value) |
| `MAX_TILES_PER_DASHBOARD` | `int = 24` | the grid cap; `wdg_create` refuses beyond it with a message |
| `UNASSIGNED` | `str = "(unassigned)"` | the single spelling of the null-group label, so a row and a caveat can never disagree |
| `SIBLING_BOARDS` | `list[dict]` | `{"label", "url_name", "module"}` for `projects:pfm_dashboard`, `projects:utilization_dashboard`, `projects:velocity_report`, `projects:financial_pnl`, `projects:financial_variance`, `projects:ar_aging`, `projects:cash_flow_forecast`, `projects:risk_analysis`, `projects:qrv_report`, `projects:task_board`, `projects:gantt_timeline`, `projects:sprint_execution` — resolved by the **views** into `sibling_boards` |
| `WIDGET_METRICS` | `dict[str, dict]` | 25 entries, one per `WIDGET_METRIC_CHOICES` key — B3.2 |
| `STANDARD_REPORTS` | `dict[str, dict]` | 15 entries (every `REPORT_TYPE_CHOICES` key **except** `custom`) — B3.3 |

### B3.2 `WIDGET_METRICS` — the tile registry

```python
WIDGET_METRICS = {
    "kpi_cpi": {
        "label":   "CPI",                      # mirrors the choices label, never replaces it
        "kind":    "scalar",                   # scalar | series | table
        "charts":  ["kpi", "gauge"],           # MUST be a subset of CANVAS_CHARTS ∪ HTML_CHARTS
        "resolver": _r_cpi,                    # callable(tenant, start, end, **scope) -> partial dict
        "drill_url_name": "projects:prj_list", # a VERIFIED sibling list route, or "" for none
        "drill_params": {"project": "project"},# which of the tile's scope FKs feed the drill's GET params
        "unit":    "ratio",                    # money | pct | num | hours | days | ratio
        "intrinsic_max": None,                 # a % / rating scalar's natural gauge ceiling
    },
    …
}
```

* **25 keys, one per `WIDGET_METRIC_CHOICES` row**, split 11 `scalar` / 11 `series` / 3 `table` (A1.4's exact
  grouping). `kind` drives the `compute_widget` contract; `charts` drives `allowed_charts`.
* `kind == "scalar"` ⇒ `charts` ⊆ `("kpi","gauge")`; `"series"` ⇒ ⊆ `("bar","line","pie","doughnut","heat")`;
  `"table"` ⇒ `["table"]`. **A test asserts each row's `charts` is a subset of `CANVAS_CHARTS + HTML_CHARTS` and
  matches its `kind`** — that is the rule that stops a gauge asking for a multi-series (A1.3).
* `drill_url_name` values are **all verified sibling list routes**, so tile drill-down costs nothing:
  `projects:rsk_list`, `projects:iss_list`, `projects:qdf_list`, `projects:tsk_list`, `projects:mst_list`,
  `projects:rte_list`, `projects:ral_list`, `projects:pex_list`, `projects:pci_list`, `projects:prj_list`.
  `health_heat_bands` drills to `projects:pfm_dashboard` (7.12 owns portfolio health — B3.7). **B5's smoke script
  `reverse()`-asserts every one of these names**, because a typo'd name is a 500 inside a tile link, not a
  visible contract break here.

### B3.3 `STANDARD_REPORTS` — the canned-report registry

```python
STANDARD_REPORTS = {
    "cost_variance": {
        "label": "Cost Variance",
        "subject": "cost",                       # a SUBJECT_CHOICES key
        "description": "…",
        "axes": {"measures": ["cv", "cv_pct", "actual_cost"],
                 "dimension_1": "project", "dimension_2": "month",
                 "chart_type": "bar"},           # what the builder prefills (context key `canned_axes`)
        "sections": [{"area": "cost", "title": "Cost variance by project"},
                     {"area": "trend", "title": "Variance trend"}],   # → _standard_section_<area>.html
        "computer": _s_cost_variance,            # callable(tenant, params) -> payload dict
        "drill_url_name": "projects:financial_variance",
    },
    …
}
```
* **15 kinds** — the 16 `REPORT_TYPE_CHOICES` rows minus `custom`, which is the builder's own kind and has no
  canned entry (`"custom"` must **not** be a key; a test asserts `set(STANDARD_REPORTS) ==
  set(dict(REPORT_TYPE_CHOICES)) - {"custom"}`).
* `sections` areas are drawn from a **closed set of eight** (`schedule`, `cost`, `risk`, `quality`, `resource`,
  `scope`, `agile`, `trend`) and each one has a partial on disk (B4). A view drops any area with no partial
  rather than letting `{% include %}` raise.

### B3.4 Public functions (exact signatures)

```python
def range_bounds(key: str) -> tuple[datetime | None, datetime | None]:
    """Preset → (start, end). `end` is None for every preset (meaning 'up to now');
    `start` is None for 'all'. `custom` is NOT accepted here — raise ValueError."""

def resolve_window(report_or_range, *, as_of=None) -> dict:
    """The ONE window resolver: returns {"start": date|None, "end": date|None,
    "as_of": date, "label": str}. Accepts a ProjectReport, a range key str, or None.
    An explicit date_from/date_to pair wins over the preset; `custom` never reaches range_bounds()."""

def allowed_charts(metric: str) -> list[str]:
    """The authority on which chart keys a metric may use. [] for an unknown metric
    (the form then adds no error — an unknown key is already refused by the model's choices)."""

def chart_rules() -> dict[str, list[str]]:
    """{metric_key: [chart_key, …]} for every WIDGET_METRICS row. One call per widget form page,
    handed to the template as `chart_rules` and to JS as `rbi-chart-rules`."""

def compute_widget(widget, *, date_range: str | None = None) -> dict:
    """Live tile. `date_range` overrides widget.date_range WITHOUT mutating the row — this is how
    pdb_detail's ?range= reaches every tile (B2.4). Returns, by kind:
      scalar -> {"kind","value":float,"display":str,"max":float,"pct":int 0-100,"unit":str}
      series -> {"kind","labels":[str],"data":[float],"unit":str}
      table  -> {"kind","columns":[str],"rows":[[cell]],"total":int,"truncated":bool}
      heat   -> {"kind","bands":[{"label","count","css"}]}
    Unknown metric -> {"kind":"scalar","value":0,"display":"—","error":"Unknown metric"} (never raises)."""

def compute_report(report: ProjectReport) -> dict:
    """Nine keys, all JSON-clean (R5):
       {"summary": {label: display-str},          # a DICT — A1.5/D7
        "columns": [str], "rows": [[cell]],
        "chart_type": str, "chart_labels": [str], "chart_data": [float],
        "caveats": [str], "truncated": bool, "rating": ""|green|amber|red}
    No "summary" LIST, no "row_count" key (the views use len(rows)), no `chart_label` singular."""

def standard_report(kind: str, tenant, params: dict) -> dict:
    """Same nine-key payload. Unknown `kind` returns the `status_report` payload shape with a caveat,
    never raises (L11 — `report_standard` also normalises before calling, so this is the belt)."""

def exec_pack(tenant, *, portfolio=None, project=None, as_of=None) -> dict:
    """The pack header payload (`summary` + the rollup `columns`/`rows`/`chart_*` + caveats)
    PLUS two extra keys the pack alone needs: "bands" (the RAG row dicts, B2.1) and
    "rollup" (portfolio→program→project rows). `bands` is the one place a rating is derived."""

def rag_streak(tenant, project=None, as_of=None) -> dict:
    """{"rating": str, "weeks": int, "label": "amber · 6 weeks"} from the consecutive issued
    ProjectReportRun series (-generated_at,-id, status="issued", reading data["rating"]).
    No issued run -> {"rating": "", "weeks": 0, "label": "no history"} — the template's {%% if %%}
    covers it. This is the ONLY function that reads stored run payloads, and it reads one key."""

def narrative_seed(tenant, report, result) -> str:
    """Plain-text starter for a new run's `narrative`: open IssueEscalation count + the project's
    latest KnowledgeEntry lesson + the top caveat line. No LLM, no markdown, and it is a STARTING
    POINT the author is expected to edit — say so in the docstring."""

def summary_pairs(summary: dict) -> list[dict]:   # {"label","value"} ×N, insertion order kept
    """The one converter from the stored dict to a KPI strip list. The model has its own identical
    `summary_cards` property (A1.5) because models cannot import analytics — the 3-line duplication
    is the price of the one-way edge, and B6's test pins both to the same output."""

def home_dashboard(request) -> ProjectDashboard | None:
    """The caller's is_default, else a shared tenant template (owner IS NULL) whose audience matches
    their role, else the newest visible one, else None. Read-only; writes nothing."""

def visible_reports(request):     # -> QuerySet[ProjectReport]     (R7)
def visible_dashboards(request):  # -> QuerySet[ProjectDashboard]  (R7)
def visible_runs(request):        # -> QuerySet[ProjectReportRun]  (R7)

def renumber_tiles(dashboard) -> None:
    """Rewrite positions to 0..n-1 in current order. Called by wdg_move ONLY on a tie (B2.5)."""

def _jsonable(value):   # Decimal→float, date/datetime→isoformat, tuple→list, anything else unchanged
def _money(v) / _num(v) / _pct(v) / _hours(v)   # display strings, crm's exact shapes
```

**These three are the only analytics callables that take a `request`** (`home_dashboard`,
`visible_reports`, `visible_dashboards`, `visible_runs` — four, and they read only `.tenant` and `.user`);
everything else takes a `tenant` and explicit args, which is what makes the compute layer testable without a
client (B6).

### B3.5 Query discipline — the two rules a reviewer will look for

1. **No per-row property loop.** `CostControlAccount.bac/pv/ev/ac/cv/sv/cpi/spi/eac/health` are `@property`
   reads (verified A1.5: `CostManagement/CostControlAccounts.py:104–232`), so a naive "for each project, read
   its account's CPI" is N+1 with a subquery each. Every EVM-backed metric must therefore:
   `CostControlAccount.objects.filter(tenant=…, project__in=scope)` **once**,
   `.select_related("project")`, then read the properties over **that already-fetched list**, capped at
   `MAX_REGISTER_ROWS`; or better, express the same arithmetic in one `values(…).annotate(…)` (7.15's
   `FinancialBoards.py` is the in-app proof that the aggregate form works — `values("project_id").annotate(...)`
   into a `{project_id: row}` dict, then a single join loop over the capped page of projects).
   **Pinned for 7.16:** the ratio metrics (`cv`, `sv`, `cpi`, `spi`, `eac`, `margin_pct`, `exposure_value`) are
   computed from **annotated aggregates keyed by `project_id`**, and the ONLY permitted property-loop is over
   the page of rows actually being rendered (`[:top_n]`), with the cap stated in the function's docstring.
2. **Cap + honest caveat.** `rows = rows[:MAX_REGISTER_ROWS]` and `truncated = len(pre_cap) > MAX_REGISTER_ROWS`
   — never `len(rows) == cap` (a 2000-row answer would claim truncation). The `truncated` flag is in the payload,
   so a frozen run records that it was capped (B2.3 `run_detail` renders the strip from the stored flag, not a
   re-count). Every `top_n` read uses `.annotate(Count("id", ...))` for a "showing N of M" tail, and when the
   remainder is dropped the caveat says how much and under which key (procurement's `"(Unclassified)"`-into-total
   rule at `apps/procurement/analytics.py:442`).

### B3.6 The `(unassigned)` denominator caveat

* `utilization_pct` = `Sum(ResourceTimeEntry.hours)` ÷ `ResourceAllocation.planned_hours(win_start, win_end)`
  (verified `ResourceManagement/ResourceAllocations.py:107`, and the window pair is exactly what
  `resolve_window()` returns). A resource with **no allocation in the window has no denominator**.
* Pinned behaviour: such a resource is grouped under `UNASSIGNED` (`"(unassigned)"`) in the `utilization_by_resource`
  series and reported as `display="—"` (never `0%`, never `inf`, never a `ZeroDivisionError`) in the
  `kpi_utilization_pct` scalar; and **one caveat string is appended** —
  `"N of M resources have no allocation in this window and are grouped as (unassigned)."` — because
  an averaged KPI that quietly dropped a third of the workforce is a lie, and the caveat is the difference
  between a rounding note and an honest denominator. `kpi_utilization_pct` divides **only** by the allocated
  denominator and says so.
* The same shape applies to `billable_pct` (no rate card) and `margin_pct` (no revenue schedule).

### B3.7 What analytics must NOT do

* No write of any kind. **`analytics.py` contains zero `.save()`, zero `.create()`, zero `.update()`** except
  `renumber_tiles()`, which is the one documented position-repair writer; the test in B6 greps for the rest.
* No `accounting.*` import, no `JournalEntry`, no money written anywhere (L29, restated in the module docstring).
* No re-derivation of 7.12's portfolio health, 7.13's velocity, 7.15's aging, 7.11's utilization dashboards,
  7.5's risk exposure or 7.6's QRV — those metrics **link** to the owning page via `drill_url_name` /
  `SIBLING_BOARDS`. The heat tile counts RAG bands from `CostControlAccount.health` **only** to fill its own
  4-band strip and then links out; it never claims to be the engine.
* No chart.js config assembly — analytics returns labels/data; the **view** builds `chart_config`/`chart_configs`
  (R6). Keeping the DOM ids out of analytics is what lets the same payload serve the CSV and JSON routes.

## B4 — Templates: exact tree + `render()` path strings

**26 files** under `templates/projects/reporting/` (the short slug, verified sibling shape:
`templates/projects/financialbilling/`, `agile/`, `portfolio/`). **Every `render()` first argument is the full
path from the templates root**, e.g. `render(request, "projects/reporting/report/list.html", ctx)`.

### B4.0 Resolving CLAUDE.md rule 6 against the entity-CRUD rule

* **Rule 6 (standalone pages at the sub-module root)** owns the four computed pages that are not any entity's
  list/detail/form: `home.html`, `library.html`, `standard.html`, `exec_pack.html`. Same precedent as 7.15's
  `financialbilling/{pnl,variance,aging,cashflow}.html`.
* **The entity-CRUD rule** owns `report/`, `reportrun/`, `dashboard/`, `widget/`, one folder per entity, the page
  as the bare filename.
* **Rule 5 (longest-entity-stem fold) overrides the plan's `dashboard_home.html` path.** The plan names
  `templates/projects/reporting/dashboard_home.html`; rule 5 says a non-CRUD page folds into
  `<entity>/<action>.html` when it begins with `<entity>_` and that entity already has a CRUD triple here — and
  `dashboard/` does. **Pinned: `projects/reporting/dashboard/home.html`** (D21). The fold also removes a real
  ambiguity: the root already has `home.html` for `rbi_home`, and two files called `*home*` one folder apart is
  exactly the drift rule 5 exists to prevent.
* `exec_pack.html` stays at the root — `exec_pack` begins with no entity stem (`report`/`reportrun`/`dashboard`/
  `widget`), so rule 5's longest-stem test does not fire. Same for `library.html` and `standard.html`.
* **Partials are `_`-prefixed inside the folder that includes them** (the observed convention,
  `templates/projects/taskwork/_task_blocks_panel.html`). All 7.16 partials live at the **sub-module root**
  because each is included by two different entity folders (`_widget_grid.html` by `dashboard/detail.html` and
  `dashboard/home.html`; `_result_table.html` by `standard.html` and `report/detail.html`) — a partial that
  lives inside one entity folder and is included from another is how folders stop meaning anything.

### B4.1 The tree

```
templates/projects/reporting/
├── home.html                                  rbi_home            "projects/reporting/home.html"
├── library.html                               report_library      "projects/reporting/library.html"
├── standard.html                              report_standard     "projects/reporting/standard.html"
├── exec_pack.html                             exec_pack           "projects/reporting/exec_pack.html"
├── _widget_grid.html                          (partial, B2.4/B2.4 pdb_home + pdb_detail)
├── _result_table.html                         (partial, standard + report/detail + reportrun/detail)
├── _result_chart.html                         (partial, the canvas + its HTML fallback + json_script)
├── _charts_script.html                        (partial, the ONE `new Chart()` loop, in {% block extra_js %})
├── _standard_section_schedule.html            ┐
├── _standard_section_cost.html                │
├── _standard_section_risk.html                │  the eight areas of B3.3's closed set; each is
├── _standard_section_quality.html             │  included by `section_templates` ONLY, and each
├── _standard_section_resource.html            │  reads the flat result keys (columns/rows/chart_*)
├── _standard_section_scope.html               │  from the parent context — no `with` hand-off,
├── _standard_section_agile.html               │  no arguments
└── _standard_section_trend.html               ┘
├── report/list.html                           rep_list            "projects/reporting/report/list.html"
├── report/detail.html                         rep_detail          "…/report/detail.html"
├── report/form.html                           rep_create/rep_edit "…/report/form.html"
├── reportrun/list.html                        run_list            "…/reportrun/list.html"
├── reportrun/detail.html                      run_detail          "…/reportrun/detail.html"
├── dashboard/list.html                        pdb_list            "…/dashboard/list.html"
├── dashboard/detail.html                      pdb_detail          "…/dashboard/detail.html"
├── dashboard/home.html                        pdb_home            "…/dashboard/home.html"   ← D21
├── dashboard/form.html                        pdb_create/pdb_edit "…/dashboard/form.html"
└── widget/form.html                           wdg_create/wdg_edit "…/widget/form.html"
```

**Count:** 4 root standalone + 12 partials + 3 `report/` + 2 `reportrun/` + 4 `dashboard/` + 1 `widget/` = **26**.

**Documented exemptions (CRUD Completeness rule, stated in the module docstrings so a reviewer does not file
them):**
* `reportrun/` has **no `form.html`** — a run is minted by `rep_freeze` only (A2.2), so there is no create/edit
  page. Its `detail.html` carries the narrative `<textarea>` (a POST to `run_narrative`) and the Issue form,
  which is the "edit" affordance the model actually allows.
* `widget/` has **no `list.html` and no `detail.html`** — a tile is rendered inside its dashboard grid and has no
  page of its own (A1.3, and the same exemption `crm` documents for its widgets).
* Delete is a POST form in the row/page, never a page — `rep_delete`/`pdb_delete`/`run_delete`/`wdg_delete` have
  no template.

### B4.2 Every file's structural contract

* **`{% extends "base.html" %}`** on all 14 pages (verified: `base.html` exposes `title`, `extra_css` (:33),
  `content` (:47), `extra_js` (:59)). Partials and `_charts_script.html` extend nothing.
* List pages: page-header + breadcrumb, a filter `<form method="get">` card, a table with **an Actions column**
  (View / Edit / Delete — the delete being
  `<form method="post" action="{% url 'projects:rep_delete' r.pk %}" onsubmit="return confirm('…');">{% csrf_token %}…`),
  `{% empty %}` row, and `{% include "partials/pagination.html" %}`.
* Detail pages: an Actions sidebar with Back-to-list, Edit (status/ownership-gated with `{% if %}`), Delete
  (POST + confirm), and the page's own verbs (Run / Freeze / Issue / Archive).
* Form pages: `<form method="post">{% csrf_token %}` + `{% include "partials/form_field.html" %}` per bound
  field, `{{ form.non_field_errors }}` on top, Cancel → `cancel_url` / `{% url %}`, and
  `<input type="hidden" name="next" value="{{ request.path }}">` on the pages `redirect_back_or` serves.
* `widget/form.html` is a **two-entity page**: it names its parent (`{{ dashboard.name }}`) and is reached from
  the dashboard, so its Cancel returns there. The three-level nesting precedent is
  `templates/projects/collaboration/meeting/agendaitem/form.html` (verified path pattern in the plan).

### B4.3 Chart rendering — reuse, add no dependency

Chart.js **4.4.1** is confirmed global at `templates/base.html:28`
(`cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js`) — **re-verified this pass, so no script tag is added
anywhere in 7.16.** The contract is copied from `templates/crm/analytics/dashboard/detail.html:59,77–104`:
`<canvas id="{{ w.canvas_id }}" height="160">` (⇒ `wchart<pk>`) + `{{ chart_configs|json_script:"rbi-charts" }}` +
the IIFE that `JSON.parse`s the script's `textContent`, looks up `"wchart" + c.id`, skips an entry with no
labels, and calls `new Chart(el, {type, data:{labels, datasets}, options})`. That IIFE lives **once**, in
`_charts_script.html`, included inside `{% block extra_js %}` by `dashboard/detail.html`, `dashboard/home.html`,
`standard.html`, `report/detail.html` and `exec_pack.html` — it reads whichever `json_script` ids are present, so
one file cannot drift from another.
* `{% json_script %}` is the **only** way a payload reaches JS here. **No `|safe`, no manual
  `{{ chart_data|safe }}` interpolation into a `<script>`** (an escaping hole and the classic XSS route).
* `HTML_CHARTS` kinds (`kpi`, `gauge`, `table`, `heat`) render markup from `summary_cards` / `chart_rows` /
  `result.bands` and get **no canvas at all** — a blank canvas is a passing test and a broken page (L8).

### B4.4 Badges — colour-named only (L33)

Verified in `static/css/theme.css`: the only badge utilities are
**`badge-green`, `badge-amber`, `badge-red`, `badge-info`, `badge-muted`, `badge-slate`** (+ `badge-group`).
**There is no `badge-success` / `badge-danger` / `badge-warning` — those class names must not appear in any 7.16
template.** Mappings pinned:

| state | class |
|---|---|
| RAG green / `issued` / shared | `badge-green` (RAG), `badge-info` (issued) |
| RAG amber / `draft` | `badge-amber` |
| RAG red / overdue / breaching | `badge-red` |
| `archived` / private / un-owned | `badge-muted` |
| neutral counts, the `(unassigned)` row, kind tags | `badge-slate` |

`obj.rag_css` (A1.5) and the view-side `rag_css` key (B2.2) both emit these strings, so the template writes
`class="badge {{ obj.rag_css }}"` — **the class name never appears as a literal in the template for a RAG badge**,
which is what keeps `{% else %}` fallbacks from inventing a `badge-success`. Every other badge keeps the required
`{% else %}` fallback and compares **raw choice keys** (`{% if run.status == "issued" %}`, never the label).

### B4.5 `exec_pack` print stylesheet — no PDF library (verified)

`requirements.txt` re-read this pass: Django, PyMySQL, python-dotenv, stripe, Pillow, cryptography, pdfplumber
(extraction only), pytest, pytest-django, python-barcode, qrcode. **No `weasyprint`, no `reportlab`, no
`pdfkit`** — the plan's claim holds and adding one is a dependency decision, not this pass's. So "PDF" means
**browser print**, the house pattern already used by `templates/projects/financialbilling/billingrun/preview_pdf.html`
(`@media print { .no-print { display: none; } }` + a `.print-btn` calling `window.print()`).
`exec_pack.html` differs from that precedent in ONE way, pinned: it **extends `base.html`** (it is a filterable
working page, not a letter), so:
* `{% block extra_css %}` carries an inline `<style>` with
  `@media print { .no-print, aside, .topbar, .sidebar, .pagination { display: none !important; }
  .card { border: none !important; break-inside: avoid; } body { margin: 0; } @page { size: A4 landscape; margin: 12mm; } }`
* the filter bar, the buttons and the sidebar links carry `class="no-print"`,
* `?print=1` (`print_mode`, B2.1) additionally renders the pack full-width without the app chrome and the header
  prints `As of {{ as_of|date:"d M Y" }}` — a stable artefact for a screenshot or a print-to-PDF,
* the RAG table is **print-legible without colour**: each band cell carries the colour badge AND the word
  (`Green`/`Amber`/`Red`), because a black-and-white printout of three greys is not a status report.

### B4.6 Responses with **no template**

`rep_csv`, `run_csv` → `HttpResponse(content_type="text/csv")` + `Content-Disposition: attachment`;
`rep_json` → `JsonResponse`. None of the three renders, resolves a template, or appears in B4.1.
`_csv_response(filename, columns, rows)` (added to `apps/projects/views/_helpers.py` next to `csv_safe`, R10) is
the single writer for both CSV routes — every cell through `csv_safe`, rows capped at `analytics.MAX_EXPORT_ROWS`,
filename from system-assigned `number`/pk only.

### B4.7 Template syntax rules this sub-module must obey

* **Multi-line comments use `{% comment %} … {% endcomment %}`. `{# … #}` is single-line only** and a
  `{# … #}` spanning lines silently swallows the markup between them — which looks exactly like an L8 blank
  region. 7.16 has narrative-length comments in `standard.html` (the per-area notes) and in
  `_charts_script.html`; both use `{% comment %}`.
* `{% verbatim %}` is not needed anywhere — nothing here prints template syntax as content.
* No `|safe` (B4.3), no index gymnastics (`{{ row.3 }}` is banned — that is why `chart_rows` and
  `summary_cards` are zipped in the view), no `{% if x == y|default %}` comparisons against a label, and no
  `{% url %}` inside a `{% with %}` that shadows a context key pinned in B2.
* Empty states on every table and grid — `run_list` and `pdb_home` are the two pages a fresh workspace sees
  completely empty (the seeder ships 0 runs and its default dashboard may not match the caller's audience).

## B5 — Seeder `_reporting_bi`, integrate checklist, verification

### B5.0 Seeder — `_reporting_bi(self, tenant, now)` in `seed_projects.py`

**Placement (surgical `Edit`, never a rewrite — L43):** a new method appended after `_financial_billing` (which
starts at line 3798), and **one call line inserted in `_seed_tenant` immediately after
`self._financial_billing(tenant, now)` (line 481)**:
```python
        self._reporting_bi(tenant, now)
```

**Idempotency guard (Seed rule 1) — first statement:**
```python
if ProjectReport.objects.filter(tenant=tenant).exists():
    self.stdout.write(f"  {tenant.name}: 7.16 Reporting & Business Intelligence already seeded — skipping.")
    return
```
Every row is then written with `get_or_create` on its natural key (`(tenant, name)` for the reports and
dashboards, `(tenant, dashboard, title)` for the tiles, `(tenant, number)` never hand-typed), so a workspace
interrupted mid-block repairs instead of duplicating. `number` comes from `TenantNumbered.save()` — the seeder
**never sets `number`**.

**Locals — reuse what the 7.15 block already resolves, never mint a second project or client:**
```python
today        = now.date()
active_proj  = Project.objects.filter(tenant=tenant, status="active").order_by("id").first() \
               or Project.objects.filter(tenant=tenant).order_by("id").first()
second_proj  = Project.objects.filter(tenant=tenant).exclude(id=active_proj.id).first() or active_proj
portfolio    = Portfolio.objects.filter(tenant=tenant).order_by("id").first()   # made by _portfolio_management (line 3048)
client_party = self._client(tenant)                                             # the existing helper
manager      = (active_proj.project_manager or active_proj.created_by
                or get_user_model().objects.filter(tenant=tenant, is_superuser=False).first())
pm_user      = (get_user_model().objects.filter(tenant=tenant, username__startswith="admin_").order_by("id").first()
                or manager)
if not active_proj or not pm_user:
    return
```
⚠️ **`pm_user` (the tenant admin, `admin_<slug>`) is the `is_default` dashboard's owner on purpose.** `pdb_home`
resolves the caller's own default, and the smoke sweep runs as `admin_acme` (B5.3) — if the default were owned
by `manager` the smoke test would open an empty home page and still pass on status. This is the seeder's part in
the L8 trap.

**Rows: 2 dashboards / 11 widgets / 5 reports / 0 runs.**

*Dashboard A* — `ProjectDashboard(name="PM Delivery Board", audience="pm", owner=pm_user, is_default=True,
is_shared=False, layout="two", default_range="last_30", project=active_proj, description=…)` → `PDB-00001`.
*Dashboard B* — `ProjectDashboard(name="Executive Portfolio Pulse", audience="executive", owner=None,
is_default=False, is_shared=True, layout="three", default_range="last_90", portfolio=portfolio, description=…)`
→ `PDB-00002`. `owner=None` + `is_shared=True` is A1.2 rule 2's own requirement (an unowned tenant template
**must** be shared, or nothing can resolve it), and `default_range` is a preset, never `custom` (A1.2 rule 4).

| # | tile · dashboard | `title` | `metric` | `chart_type` | `date_range` | `size` | `position` | `target_value` | scope |
|---|---|---|---|---|---|---|---|---|---|
| 1 | A | Active projects | `kpi_active_projects` | `kpi` | `last_30` | `small` | 0 | — | project=active_proj |
| 2 | A | Overdue tasks | `kpi_overdue_tasks` | `kpi` | `last_30` | `small` | 1 | — | project=active_proj |
| 3 | A | Open risks | `kpi_open_risks` | `kpi` | `last_30` | `small` | 2 | — | project=active_proj |
| 4 | A | Work by status | `tasks_by_status` | `bar` | `last_90` | `medium` | 3 | — | project=active_proj |
| 5 | A | Project mix | `projects_by_status` | `doughnut` | `last_90` | `medium` | 4 | — | — |
| 6 | A | Slipped milestones | `overdue_milestones` | `table` | `last_30` | `full` | 5 | — | project=active_proj |
| 7 | B | Cost performance | `kpi_cpi` | `gauge` | `last_90` | `medium` | 0 | `1.00` | — |
| 8 | B | Schedule performance | `kpi_spi` | `kpi` | `last_90` | `medium` | 1 | — | — |
| 9 | B | Cost variance by project | `cost_variance_by_project` | `bar` | `last_90` | `large` | 2 | — | — |
| 10 | B | Earned-value curve | `ev_curve_by_month` | `line` | `year` | `medium` | 3 | — | — |
| 11 | B | Portfolio health | `health_heat_bands` | `heat` | `last_90` | `full` | 4 | — | portfolio=portfolio |

Every row above is a **legal metric↔chart pair** (`scalar`→`kpi`/`gauge`, `series`→`bar`/`line`/`doughnut`/`heat`,
`table`→`table`, B3.2), `target_value` only on the gauge (A1.3 rule 2), and each tile's `tenant` is set to
`dashboard.tenant` in the same statement that sets `dashboard=` (A1.3's denormalisation rule). A tile whose
metric↔chart pair the seeder broke would raise in `full_clean()` — the seeder calls `obj.full_clean()` then
`obj.save()` for exactly that reason (a seeder that bypasses validation is how a blank tile ships).

| # | `ProjectReport` | `name` | `report_type` | `subject` | `measures` | `dimension_1` / `dimension_2` | `date_range` | `chart_type` | `top_n` | shared / fav / owner |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | REP-00001 | Weekly status digest | `status_report` | `project` | `completed_count`,`open_count` | `status` / `none` | `last_7` | `table` | 20 | shared ✓ · fav ✓ · `pm_user` |
| 2 | REP-00002 | Earned value by project | `earned_value` | `project` | `earned_value`,`cv`,`cpi` | `project` / `month` | `last_90` | `line` | 15 | shared ✓ · `pm_user` |
| 3 | REP-00003 | Risk exposure register | `risk_register` | `risk` | `exposure_value`,`open_count` | `risk_category` / `severity` | `all` | `bar` | 50 | shared ✓ · `pm_user` |
| 4 | REP-00004 | My utilization check | `resource_utilization` | `resource_allocation` | `utilization_pct`,`hours` | `resource` / `role` | `last_30` | `bar` | 25 | **shared ✗ (private)** · `pm_user` |
| 5 | REP-00005 | Unbilled by client (custom) | `custom` | `invoice` | `unbilled_amount`,`invoiced_amount` | `client` / `month` | `custom` (`date_from=today-60`, `date_to=today-14`) | `bar` | 10 | shared ✓ · `pm_user`, `project=active_proj`, `client=client_party`, `sort_by="unbilled_amount"` |

Row 4 exists so the **private-object 404 is testable on a seeded workspace**; row 5 exercises the `custom` range
pair, the `sort_by` measure key and two scope FKs; row 3 exercises `date_range="all"` with both bounds blank;
row 1 is the `REP-00001` string the smoke sweep asserts. All five satisfy `ProjectReport.clean()` (measures ≤ 3
and known keys, `d1 != d2`, window ≤ 730 d, scope FKs on this tenant).

**ZERO `ProjectReportRun` rows — hard rule.** *"A frozen run must be issued by a human"* (the research's
explicit ruling). The seeder must not call `rep_freeze`'s logic, must not `ProjectReportRun.objects.create(...)`,
and must **print the reason** so a reader does not file it as missing demo data:
```python
self.stdout.write(f"  {tenant.name}: 7.16 — 2 dashboards, 11 tiles, 5 saved reports; "
                  f"0 runs (a run is frozen by a person from a report page, never seeded).")
```
Consequences B5.3 must respect: `run_list`, `exec_pack` (`narrative_run` is None) and `rag_streak`
(`"no history"`) all have to render their empty states, and the smoke sweep mints its own run through
`rep_freeze` — never by inserting a row directly.

**Tail:** the existing `_print_logins()` (line 4135) already prints the tenant admins and the
`Superuser 'admin' has no tenant` warning — **do not duplicate it**, just confirm the run output still ends with
it (Seed rule 3).

### B5.1 `LIVE_LINKS["7.16"]` (the one wire-up entry)

Surgical `Edit`: one dict inserted **after the `"7.15"` block** (which ends at `apps/core/navigation.py:1940`),
before line 1942. Keys are NavERP.md's bolded bullet labels **exactly** (`_FEATURE_RE` at :1964 matches the bold
label, not the line); `?query` suffixes are supported by `_safe_reverse` (:2149).

```python
    "7.16": {
        "Standard Project Reports":               "projects:report_library",
        "Custom Report Builder":                  "projects:rep_list",
        "Real-Time Dashboards & Widgets":         "projects:pdb_home",
        "Executive & Steering Committee Packs":   "projects:exec_pack",
        "Data Export & API Connectivity":         "projects:run_list",
        # Extra live leaves:
        "Reporting & BI Home":                    "projects:rbi_home",
        "Saved Reports":                          "projects:rep_list",
        "Standard Report Runner":                 "projects:report_standard?type=status_report",
        "Report Runs (frozen)":                   "projects:run_list",
        "Dashboards":                             "projects:pdb_list",
        "Portfolio Heat Map":                     "projects:pfm_dashboard",   # 7.12's engine, linked not rebuilt
    },
```
`ProjectReportRun` gets **no create page** and `DashboardWidget` **no list page** of its own, so neither appears
as a leaf — one comment line in the house style says why ("this dict maps bullets to pages").

### B5.2 Integrate checklist (single writer, only DB writer — order matters)

Verify **all** expected files actually landed *before* wiring anything (Phase 3 step 4), then:

1. **Re-export blocks — all FOUR packages + urls** (a missing line is an `ImportError`/`AttributeError` at
   runtime, backend rule 3):
   * `apps/projects/models/__init__.py` — a `# --- 7.16 Reporting & Business Intelligence` section, in the file's
     **relative** form (D18): `from .ReportingBusinessIntelligence.ProjectReports import ProjectReport  # noqa: F401`
     + `ProjectReportRun`, `ProjectDashboard`, `DashboardWidget` **and** the eleven `_choices` constants
     (`RANGE_CHOICES`, `CHART_CHOICES`, `LAYOUT_CHOICES`, `SIZE_CHOICES`, `AUDIENCE_CHOICES`,
     `REPORT_TYPE_CHOICES`, `SUBJECT_CHOICES`, `MEASURE_CHOICES`, `DIMENSION_CHOICES`, `RUN_STATUS_CHOICES`,
     `WIDGET_METRIC_CHOICES` + `CANVAS_CHARTS`, `HTML_CHARTS`) so `from apps.projects.models import X` keeps working.
   * `apps/projects/forms/__init__.py` — `ProjectReportForm`, `ProjectReportNarrativeForm`,
     `ProjectReportIssueForm`, `ProjectDashboardForm`, `DashboardWidgetForm`.
   * `apps/projects/views/__init__.py` — **all 31 view functions by name** (the 7.15 precedent at `views/__init__.py:609`
     lists even the board views; a name missing here is an `AttributeError` in `urls/…` at URLconf import).
   * `apps/projects/urls/__init__.py` — the five imports + the five `+ _rbi_*` terms in B1.6's order.
   * The five **sub-package** `__init__.py` files stay intentionally EMPTY of re-exports (A0, verbatim
     `models/FinancialBillingManagement/__init__.py`).
2. **`admin.py`** — register the four: `ProjectReportAdmin` (`list_filter=("report_type","chart_type",
   "is_shared","is_favorite")`, `search_fields=("number","name","description")`, `readonly_fields=
   ("number","last_run_at","created_at","updated_at")`); `ProjectReportRunAdmin` with `has_add_permission` →
   `False` and `has_change_permission` limited to `narrative` (read-only fields otherwise);
   `ProjectDashboardAdmin`; `DashboardWidgetAdmin` with `list_select_related = ("dashboard",)`.
3. **CSV/redirect helpers** — append `csv_safe` and `redirect_back_or` to `apps/projects/views/_helpers.py`
   (verified absent; surgical append, L43 — another session may be editing this file).
4. **Migration — re-check the number AT RUN TIME, never assume it.** `apps/projects/migrations/` tops out at
   `0023_projectpaymentrecord_ppr_tnt_dunning_idx_and_more.py` **as of this pass**, and a concurrent session owns
   7.15 test fixes in this checkout, so immediately before `makemigrations`: `ls apps/projects/migrations/`,
   `git rev-parse HEAD`, then `python manage.py makemigrations projects` (expect **one** new file, likely
   `0024_projectdashboard_projectreport_…py`, alphabetically keyed by the four models), then
   `git status --short apps/projects/migrations/` to prove **only your file** appeared (makemigrations is scoped
   to the app *registry*, not to your files). `migrate`. Then `makemigrations projects --check` must say
   **"No changes detected"** — a second migration means a model in the sub-package failed to keep its
   `app_label` (backend rule 8).
5. **`apps/projects/tests/conftest.py` is OFF LIMITS until Phase 6** — it is dirty in the working tree and belongs
   to the concurrent 7.15 session (L45). No 7.16 step before Phase 6 may touch it; at Phase 6 step 1 re-run
   `git status --short apps/projects/tests/` and only then append a `_reporting_*` helper block.
6. **Commit one file per commit** with explicit paths, PowerShell separators (`;`, never `&&`),
   **never `git push`**.

### B5.3 Verification checklist (Phase 3 step 4) + the smoke gate (step 5)

```
python manage.py makemigrations projects     # ONE file, number confirmed at run time
python manage.py migrate                     # + makemigrations projects --check  -> "No changes detected"
python manage.py seed_projects               # run TWICE; the 2nd must print the 7.16 skip line, change nothing
python manage.py check                       # clean, 0 issues
```

`temp/smoke_716.py` (gitignored `temp/`, L46 — never committed), driving the Django test client as
**`admin_acme` / `password`** (the superuser `admin` has `tenant=None` and would see empty registers):

1. **Every one of the 31 routes resolves and renders.** `django.urls.reverse()` on each name first (this also
   proves B1's `first-match-wins` claim and every `drill_url_name` / `SIBLING_BOARDS` string in B3 — a
   `NoReverseMatch` here is a 500 in a user's face later). Assert the five literal shapes explicitly:
   `reporting/`, `reporting/library/`, `reporting/standard/`, `reporting/reports/add/`,
   `reporting/dashboards/add/`, `reporting/home/` hit the intended views.
2. **Content, not just status (L8).** On `rbi_home`: `REP-00001` and `PM Delivery Board` appear in the HTML;
   on `rep_list`: the five seeded names; on `pdb_list`: both dashboard names + the tile counts; on
   `rep_detail(REP-00001)`: a table header cell and a row; on `pdb_detail(1)`: two tile titles. On every page:
   **no `{#`, no `{%`, no `{{` leak** (an unrendered or swallowed tag), and the page `<title>` string.
3. **A rendered chart, not a 200.** On `pdb_detail` and `pdb_home`: the literal `rbi-charts` script id is present,
   and decoding it yields **≥ 1 entry with a non-empty `labels` list**; at least one KPI tile's display value
   appears as text (e.g. a digit inside `class="stat-value"`). A blank `<canvas>` passes assertion 2 and fails
   this one — which is the whole point of the check. Also assert the canvas id form: `id="wchart<widget pk>"`.
4. **Freeze → issue → read.** `POST rep_freeze(REP-00001)`; follow the redirect to `run_detail`; assert the
   stored title, `row_count` and the RAG badge appear; `POST run_narrative` then `POST run_issue`; assert
   `status` flipped and `issued_by` is `admin_acme`. Then assert `run_detail` renders identically with
   `analytics.compute_report` monkey-patched to raise (the no-recompute rule).
5. **Junk params never 500 and never empty the register (L11).** `report_standard?type=nonsense` → 200 with the
   `status_report` payload; `rep_list?report_type=nope&project=0` → 200 with all 5 rows;
   `rep_list?project=99999999999999999999` (over-range, 20 digits) → 200 with all 5 rows;
   `pdb_detail?range=nonsense` → 200 with the authored window; `run_list?status=garbage` → 200.
6. **Pagination (L9).** `rep_list?page=2` and `run_list?page=2` → 200. Because the seeder mints 5 reports and
   0 runs at `per_page=15`, the sweep **creates 16 throwaway `ProjectReport` rows for `acme`** in the script,
   asserts a genuine page 2 (`page_obj.has_previous` and `has_next` both true on page 2, 15 rows on page 1),
   then deletes them. `partials/pagination.html` is also asserted present in the HTML of all three registers.
   (This is the honest reading of the plan's "the seeder must mint enough rows" — D25.)
7. **Cross-tenant IDOR → 404** for `rep_detail`, `rep_edit`, `rep_delete`, `rep_run`, `rep_freeze`,
   `rep_favorite`, `rep_csv`, `rep_json`, `run_detail`, `run_csv`, `pdb_detail`, `pdb_edit`, `pdb_delete`,
   `wdg_edit`, `wdg_delete`, `wdg_move`: mint one row in a **second tenant**, then request its pk as
   `admin_acme` and require **404**, on both verbs where the route is POST-only.
8. **Private-object ACL → 404** (R7): as a *different* member of `acme`, `rep_detail(REP-00004)`
   (the seeded private report), its `edit`/`csv`/`json`, and `pdb_detail` of a colleague's private dashboard are
   all **404 — not 403, not a blank row**. Then assert the same pks **are** 200 for `admin_acme` (the owner), so
   the test cannot pass by simply breaking every fetch.
9. **Verb discipline (7.7's lesson).** `GET` on each of the 11 POST-only routes → **405, never 403** — including
   `run_delete` hit with a GET as a *plain member*, which must be **405** and not the misleading 403, because
   `@require_POST` sits outside `@tenant_admin_required` (B1.7). The same `run_delete` as a tenant admin with a
   POST → 302/200, so the 405 assertion cannot pass by simply breaking the route. A logged-out `GET` on those
   routes → 302 to login (`@login_required` is outermost).
10. **Exports.** `rep_csv` → 200, `text/csv`, `Content-Disposition: attachment; filename="REP-00001.csv"`, the
    header row equals `compute_report()["columns"]`, and a cell containing `=1+1` renders as `'=1+1`
    (formula-neutralised). `rep_json` → 200 and `json.loads()` succeeds (proof R5 held — no `Decimal`/`date`
    leaked). `run_csv` matches the frozen page's row count exactly. **Each of the three appends an
    `AuditLog` row with `action="export"`** and the row's `changes["verb"]` names the flavour.
11. **Sidebar.** `7.16` renders **Live** with all five bullet labels present as keys of `LIVE_LINKS["7.16"]`
    (the `_FEATURE_RE` match is the bold label, so a paraphrased key silently renders a dead bullet), and the
    module-7 group is open on a 7.16 page.
12. **Regression.** `python manage.py test apps.projects` (full, unfiltered, L47) — the existing 7.15 lane
    (`test_financialbilling_*`) must still be green, since `urls/__init__.py`, `views/__init__.py`, `admin.py`,
    `seed_projects.py`, `views/_helpers.py` and `navigation.py` are all shared files.

## B6 — Test naming

**subslug = `reporting`** (the plan's own ruling, matching the `reporting/` template folder and the
`projects/reporting` slug convention of 7.11–7.15). **Four files** in `apps/projects/tests/`:

* `test_reporting_models.py`
* `test_reporting_forms.py`
* `test_reporting_views.py`
* `test_reporting_security.py`

**Naming, without exception** (the rule exists because the next sub-module appends files alongside these in the
same package):
* every test function `test_reporting_<thing>` — e.g. `test_reporting_report_number_is_rep_prefixed`,
  `test_reporting_widget_metric_chart_pair_is_enforced`, `test_reporting_run_detail_does_not_recompute`,
  `test_reporting_private_report_is_404_for_a_colleague`;
* every module-level helper `_reporting_<thing>` — `_reporting_payload()`, `_reporting_make_report()`,
  `_reporting_client()`; **no unprefixed `make_report` / `client` helper anywhere**;
* fixtures (where `conftest.py` is extended at Phase 6 step 1): `reporting_report`, `reporting_run`,
  `reporting_dashboard`, `reporting_widget`, `reporting_tenant_b` — all `reporting_`-prefixed for the same
  reason.

**What each file must cover (from the contract's own load-bearing claims):**

| file | the assertions that only this file can carry |
|---|---|
| `test_reporting_models.py` | `REP-` / `PDB-` auto-numbering; the A1.0 `clean()` rules incl. the ≤ 730-day window and the `all`/`custom` bound pairings; `dimension_1 == dimension_2` refusal; scope-FK tenancy on all four models; the A1.2 at-most-one-default rule; the `custom` ban on `ProjectDashboard.default_range` / `DashboardWidget.date_range`; the `-generated_at, -id` tie-break; the A1.5 property set (`summary_cards`, `columns`/`rows`, `rag_css`, `is_canvas`, `canvas_id`, `annotation_count` vs `widget_count`); **and the choice-count assertions from A1.4 (7 / 8 / 3 / 4 / 7 / 16 / 16 / 24 / 18 / 3 / 25)** |
| `test_reporting_forms.py` | every `Meta.fields` whitelist verbatim from A2 and the omission list; `form.instance.measures` is a `list` after a valid bound form (D15); `TenantUniqueMixin` stamping so a CREATE is not falsely rejected as cross-tenant; `_reject_foreign` on a crafted POST naming a foreign project; **the metric↔chart refusal living in the FORM (D10) and `allowed_charts()` being its only source**; the draft-only `narrative` / `issue` gates; the document queryset being tenant-narrowed |
| `test_reporting_views.py` | every GET page 200 with content; **the context contract of B2 — one test per url name asserting the pinned keys are in `response.context`** (`object_list`, `page_obj`, `q`, each `*_choices`, each `*_filter`, `rendered_widgets`, `chart_configs`, `cols`, `active_range`, `section_templates`, `export_urls`, `print_mode`); the list-var rule (a template rendering rows from `object_list`); filter + search + pagination behaviour incl. junk params falling back to the unfiltered list rather than an empty one; `pdb_detail?range=` overriding every tile while leaving the stored `default_range` untouched; the freeze→issue→archive verb chain and `rep_run`/`rep_favorite`'s `.update()` **not** moving `updated_at` while the run writes **do** (B2.3's split); csv/json payloads; `rag_streak` reading the stored series; `summary_pairs()` and `ProjectReportRun.summary_cards` agreeing on the same dict |
| `test_reporting_security.py` | login required on all 31; tenant isolation + cross-tenant IDOR → **404**; private-object ACL → **404 not 403** for report/dashboard/run/tile and for the **export and JSON** routes too (R7: an access rule with two definitions has one out of date); the 11 POST-only routes → **405 on GET**, incl. `run_delete` as a plain member being **405 not 403** (B1.7); `run_delete` gated to tenant admins; the `admin.py`/superuser `tenant=None` empty-register case; CSRF enforced; **every export appends an `AuditLog` row with an action ≤ 10 chars and the verb in `changes`**; `csv_safe` neutralising a leading `=`; and the **analytics registry parity** test — `set(WIDGET_METRICS) == set(dict(WIDGET_METRIC_CHOICES))`, `set(STANDARD_REPORTS) == set(dict(REPORT_TYPE_CHOICES)) - {"custom"}`, and `allowed_charts(m) ⊆ CANVAS_CHARTS + HTML_CHARTS` for every `m` (A1.4's and B3.2's whole safety net) |

**Execution rules:** SQLite in-memory (the app's existing test settings — no MySQL needed for 7.16, and no
partial-index reliance, D4). Phase 6 runs the **full unfiltered** `apps.projects` suite at the end — never `-k`,
because a filter excludes exactly the 7.15 / 6.14 / crm tests a shared-file change (`urls/__init__.py`,
`views/__init__.py`, `views/_helpers.py`, `admin.py`, `seed_projects.py`, `navigation.py`) can break (L47).
`conftest.py` is owned by Phase 6 step 1 alone and must be clean of the concurrent 7.15 session's edits first
(B5.2 item 5).

## B7 — Part B deviations (code over plan)

| ID | plan said | Part B pins | why |
|---|---|---|---|
| **D20** | "`@require_POST` outermost" (7.7's 403-vs-405 lesson) | `@login_required` → `@require_POST` → `@tenant_admin_required`, i.e. `require_POST` is outermost **among the verb/role gates** | verified in the app at `RiskManagement/IssueEscalations.py:87–90` and all four 7.15 `*_delete` views. `login_required` must stay outermost, or an anonymous GET on a POST route answers 405 instead of redirecting to login; the 7.7 bug being fixed is 403-before-405, which the `require_POST`-before-`tenant_admin_required` order solves. The plan's shorthand, read literally, would break the anonymous case |
| **D21** | template `templates/projects/reporting/dashboard_home.html` | `templates/projects/reporting/dashboard/home.html` | CLAUDE.md Template rule 5's longest-entity-stem fold: `dashboard_home.html` begins with `dashboard_` and `dashboard/` already owns a CRUD triple. It also removes the root-`home.html` vs `dashboard_home.html` ambiguity |
| **D22** | `report_standard` context includes `export_urls` | `export_urls` **is** a context key and is `[]` on `report_standard` | a canned page has no row to hang a `rep_csv`/`rep_json` pk on, and inventing a `?format=json` param would add an unlisted 32nd route. The key stays in the contract so the shared result partial has one code path; the template's `{% if export_urls %}` renders nothing |
| **D23** | A2: "the view passes `chart_rules` … into the builder's context" | `chart_rules` lives on **`wdg_create`/`wdg_edit`** only; the report builder's prefill key is **`canned_axes`** | `allowed_charts(metric)` is a *widget* rule (metric↔chart); `ProjectReport` has no `metric` field, so a `chart_rules` map on the builder would be a key the template cannot use. A2's promise is honoured where its own rule lives, and the builder gets the JSON hint it actually needs |
| **D24** | "the saved-report result renders through the SAME section partials as `standard.html`" | shared markup = `_result_table.html` + `_result_chart.html` (both pages); `_standard_section_*.html` renders **only** for a canned `report_type`, and `section_templates` is `[]` for `custom` | a `custom` builder report has no canned sections by definition. The single-sourcing guarantee that matters — one compute, one table, one chart renderer — is kept by the two `_result_*` partials and `compute_report()` |
| **D25** | "the seeder must mint enough rows that pagination has a genuine page 2" | seeder stays at **5 reports / 2 dashboards / 11 tiles / 0 runs**; the smoke sweep mints 16 throwaway rows, asserts, then deletes them | 5 rows at `per_page=15` can never page. Minting 16 demo reports to satisfy a test would make the demo data worse than the assertion, and `run_list` can **never** page without seeding runs — which B5.0 forbids |
| **D26** | `crud_edit` / `crud_delete` as-is for `rep_edit` / `rep_delete` / `pdb_edit` / `pdb_delete` | each does a `get_object_or_404(visible_*(request), pk=pk)` **guard line** before delegating | `crud_edit`/`crud_delete` filter on `tenant` only (`apps/core/crud.py:198,226`) — they have no ACL hook. Without the guard a colleague's **private shared-tenant** object would be editable by pk, and R7's "private is a 404" would be true only on the list page. The helper re-fetches; that one duplicate SELECT is the price of keeping the shared helper shared |
| **D27** | `visible_reports` / `visible_dashboards` / `visible_runs` "in ONE place each" | they live in **`apps/projects/analytics.py`**, not in the entity view module (procurement's placement) | three view modules + the home/exec pages all need them; a second copy in `views/_helpers.py` would need `Q` + models there. They are the only four analytics callables taking a `request` (they read `.tenant` / `.user` only), and the placement is what lets B5.3's ACL tests call them without a client |
| **D28** | B3.2: each `WIDGET_METRICS` row carries `"resolver": _r_cpi` | the registry row has **no compute key**; each tile's compute is a module function named `_tile_<metric>`, registered into a separate `WIDGET_COMPUTE` dict by the bare `@_widget` decorator, whose key is derived from `func.__name__.removeprefix("_tile_")`. An **import-time `assert set(WIDGET_COMPUTE) == set(WIDGET_METRICS)`** closes the loop | `WIDGET_METRICS` is defined at line ~400 and the computes at ~1280, so a literal `"resolver": _r_cpi` key needs forward references. Deriving the key from the name makes row↔compute drift impossible by construction and keeps the metric stated exactly once; the assert turns a missing compute into an import error instead of a permanently blank tile. (The first cut had all 25 functions named `_` — every traceback read `in _` and every `WIDGET_COMPUTE` value had `__name__ == "_"`.) |
| **D29** | B3.2 row keys `drill_params`, `intrinsic_max` | **dropped.** A row is `{label, kind, charts, unit, drill_url_name}`; the gauge ceiling comes from `_GAUGE_MAX` keyed by `unit` (`pct`→100, `index`→2) | the ceiling is a property of the **unit**, not the metric — eleven scalar rows would have repeated the same two numbers and one of them could have disagreed with its own unit. `drill_params` had no caller: tile scope is resolved once in `compute_widget` via `_scope_project_ids(tenant_id, {project_id, portfolio_id})` |
| **D30** | B3.1: `DIMENSIONS` = `{"label","field","order"}`, `SUBJECTS` = `{"label","model","date_field","open_q","text_field"}` | both are **flat `{key: label}` maps**; the ORM paths, date fields and open-state `Q` objects live in `_load_facts()` / `_group_value()` / `_aggregate()` | 16 subjects need 16 different joins and annotation sets — a data dict cannot express that without becoming a second lambda registry next to the real one. The labels are what the templates and the column headers read, so that is all the map carries |
| **D31** | B3.4: `range_bounds(key) -> (start, end)` beside `resolve_window()` | **`range_bounds` is not implemented.** `_date_window()` (private) + `resolve_window()` are the one resolver; `range_bounds`'s job — a preset key → bounds — is `_date_window`'s first branch | two public window APIs is one too many and `range_bounds` had exactly one legal caller. It also could not express the `custom`/`date_from`/`date_to` pair that `resolve_window` must accept, so keeping both meant one of them was always the wrong call |
| **D32** | B3.4: `compute_report` returns "**nine keys**" | returns the nine **plus seven**: `chart_dataset_label`, `group_count`, `window`, `subject`, `measures`, `dimensions`, `sort_by`. `row_count` is still **absent** (the views use `len(rows)`) | `group_count` is what B3.5 rule 2's "showing N of M" tail needs; `chart_dataset_label` is what the canvas legend and `narrative_seed` read; `subject`/`measures`/`dimensions`/`sort_by`/`window` are the payload echoing the question so a frozen run is self-describing when the report row behind it is later edited. A stored-JSON payload that cannot say what it asked is a run that must be re-computed to be read |
| **D33** | B3.4: `compute_widget` returns the per-kind keys only; unknown metric → `{"kind":"scalar","value":0,"display":"—","error":"Unknown metric"}` | **every** payload carries `kind`, `metric`, `unit`, `chart_type`, `drill_url_name`, `range_label`, `caveats` and then its kind keys (a `heat` series adds `bands` alongside `labels`/`data`). A tile that cannot answer goes through one local `blank(error)` helper: `kind`/`chart_type` forced to the scalar card, `value`/`max`/`pct` = `None`, `display` = `—`, `error` = `"unknown metric"` or **the exception class name** | the grid partial needs the drill name and the range label per tile — without them every tile link would have to re-resolve its own scope in the template. `value` is `None` and not `0` because 0 is a real answer and `None` is not (the same rule `_pct()` states). Forcing `chart_type` on the failure path is what stops the view building a canvas config for a payload with no data; echoing only the exception **class** keeps a raw DB error out of the HTML |
| **D34** | B3.5 rule 2: `truncated = len(pre_cap) > MAX_REGISTER_ROWS` | that rule is followed verbatim in `_compute` (the register). A **table tile** uses `truncated = len(rows) < total` | a tile table caps itself at 10 rows by design, so it is always "truncated" in the honest sense and never near 2000 — testing the register's cap there would always say `False` while the 11th row sat invisible. `total` is the scope's own count, taken with `.annotate(Count(...))` or `.count()`, never `len(rows)` |
| **D35** | B3.4 / B2.1: `rag_streak` label `"amber · 6 weeks"`, `bands[].streak_label` "amber · 6 weeks" | the number counts **consecutive issued runs**, and the sentence says `f"{rating} · {n} run/runs in a row"` (`_streak_result`). No history → `"no rating on record"`; a lone run → `"… · no prior run at this rating"` | runs are minted on demand, not on a calendar — nothing in the stored series can support a claim about weeks. `_streak_result` is the ONE place a streak becomes a sentence so the pack and a run detail cannot word the same series differently. `_rating_series` deliberately reads one report per project: two different questions both being `red` is not one streak |
| **D36** | B2.1: `exec_pack` → `bands[].drill_url` | the pack emits **`drill_url_name` + `drill_pk`**; the view resolves `drill_url` | B3.0 bans `reverse()` inside analytics — a typo'd url name would then raise at import time in an unrelated request path. `_rbi_home`/`exec_pack` view does the one-line resolve, and B5's smoke sweep `reverse()`-asserts every name instead |
| **D37** | B3.4's function list | **one addition**: `rag_history(tenant, *, months=6, as_of=None)` → `[{label, green, amber, red}]` with zero-filled `TruncMonth` buckets | B2.1's `rag_series` is a month-bucketed persistence sparkline. `rag_streak` is deliberately about ONE project's latest report, so it cannot serve it, and the bucket arithmetic in a template would be a `{% for %}` counting loop pretending to be analytics |
| **D38** | B3.4: `def _jsonable(value)` | **`json_safe(value)`** — public, and `exec_pack`/`compute_report`/`compute_widget` all return through it | the CSV and JSON export routes (B2.3) have to normalise a payload before writing it; importing `_jsonable` across a module boundary is a private-name import, which is the thing the underscore exists to prevent |
| **D39** | B3.1's constant list | **one addition**: `MAX_EVM_PROJECTS = 200` — the ceiling on `_tenant_project_ids()`, i.e. how many projects one EVM read may join across | B3.5 rule 1 caps the *rows* a metric returns but says nothing about the *projects* `_evm_map()` walks. 200 keeps the property loop over already-fetched accounts bounded by the aggregate read, and the tile states the cap in a caveat when the scope is wider |
| **D40** | the plan's risk arithmetic: `exposure = probability / 100 × cost_impact` | both `_load_facts`' risk branch and `_risk_exposure_grouped` read **`ProjectRisk.exposure`** (7.5's own `emv` property) | `probability` is a **1–5 ordinal**, not a percentage (`RiskManagement/ProjectRisks.py:183` → `cost_impact * PROBABILITY_PCT[probability] / 100`). The plan's spelling understated every open risk by ~10×, and B3.7 bans re-deriving 7.5's exposure in the first place — reading the model is what keeps one register telling one story |

**Part B's answer to Part A's open questions (A3's tail):** every url name (B1), every view function name
(B1/B2), every context key (B2), every template path (B4) and the seeder's row counts (B5.0: **2 dashboards,
11 widgets, 5 reports, 0 runs**) are now pinned. **Part B adds no field, no choice key and no form** — the only
new names it introduces are analytics symbols (`MEASURES`, `DIMENSIONS`, `SUBJECTS`, `WIDGET_METRICS`,
`WIDGET_COMPUTE`, `STANDARD_REPORTS`, `PRESET_RANGES`, `SIBLING_BOARDS`, `UNASSIGNED`, `MAX_REGISTER_ROWS`,
`MAX_EXPORT_ROWS`, `MAX_EVM_PROJECTS`, `MAX_TILES_PER_DASHBOARD`, `allowed_charts`, `chart_rules`,
`resolve_window`, `compute_widget`, `compute_report`, `standard_report`, `exec_pack`, `rag_streak`,
`rag_history`, `narrative_seed`, `summary_pairs`, `home_dashboard`, `renumber_tiles`, `json_safe`) and three
view helpers (`csv_safe`, `redirect_back_or`, `_csv_response`).

**Part B's promise back to Part A (three things A must not break):**
1. `ProjectReportRun.summary` is a **dict** and `.data` holds the **whole `compute_report()` payload** — B3.4's
   nine keys plus D32's seven self-describing ones, and nothing is dropped on the way in. If A changes either
   shape, B2.3's property list and `rep_freeze`'s write both move with it.
2. `CANVAS_CHARTS` / `HTML_CHARTS` are the **only** discriminator for canvas-vs-markup rendering (R6, B4.3) —
   adding a chart kind means touching both `_widget_grid.html` and `_result_chart.html`.
3. `DashboardWidget.canvas_id` == `f"wchart{self.pk}"` is the DOM contract the JS looks up; renaming the
   property or its format breaks the smoke assertion in B5.3 item 3 before it breaks anything visible.
