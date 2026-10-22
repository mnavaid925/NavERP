# Review — Sub-module 8.12 Sales Analytics & Intelligence (Module 8 — Sales Management System, `apps/sales`)

> The six-reviewer pass for the 8.12 build. Each reviewer ran **serially, one at a time**, against the frozen
> changeset. Findings are deduped, sorted Critical → Important → Minor, and assigned IDs `C1`–`C5`, `I1`–`I12`, `M1`–`M15`.

## Scope of this review

**Base sha:** `04884feb` (the commit that opened the 8.12 work) · **Head at review time:** the tip of `main`.

**The 8.12 changeset — 43 new files:**

| Layer | Files |
|---|---|
| Models | `apps/sales/models/SalesAnalytics/{__init__,WinLossDebriefs,StageVelocityAnalyses,FunnelConversionRecords,RepPerformanceScorecards}.py` |
| Forms | `apps/sales/forms/SalesAnalytics/{__init__,WinLossDebriefs,StageVelocityAnalyses,FunnelConversionRecords,RepPerformanceScorecards}.py` |
| Views | `apps/sales/views/SalesAnalytics/{__init__,_helpers,WinLossDebriefs,StageVelocityAnalyses,FunnelConversionRecords,RepPerformanceScorecards,AnalyticsConsoles}.py` |
| URLs | `apps/sales/urls/SalesAnalytics/{__init__,WinLossDebriefs,StageVelocityAnalyses,FunnelConversionRecords,RepPerformanceScorecards,AnalyticsConsoles}.py` |
| Migration | `apps/sales/migrations/0024_funnelconversionrecord_repperformancescorecard_and_more.py` |
| Templates | `templates/sales/salesanalytics/{winlossdebrief,stagevelocityanalysis,funnelconversionrecord,repperformancescorecard}/{list,detail,form}.html` (12) + `templates/sales/salesanalytics/boards/{analytics_console,win_loss_console,velocity_console,funnel_console,rep_scorecard_console,benchmark_console}.html` (6) |

**Modified shared files (8):** `apps/sales/models/__init__.py` · `apps/sales/forms/__init__.py` ·
`apps/sales/views/__init__.py` · `apps/sales/urls/__init__.py` · `apps/sales/admin.py` ·
`apps/sales/management/commands/seed_sales.py` · `apps/core/navigation.py` · `templates/sales/overview.html`

**The frozen spec:** `.claude/tasks/contract-sales-8.12.md` — the contract every reviewer checked against.

---

## Reviewer Log (All Six Completed)

| # | Reviewer | Focus | Status |
|---|---|---|---|
| 1 | `code-reviewer` | Django correctness, data integrity, spine reuse, package structure | complete |
| 2 | `explorer` | Spine/ownership mapping, view↔template contract, dead code | complete |
| 3 | `frontend-reviewer` | Design system, comment leaks, filters, pagination, a11y | complete |
| 4 | `performance-reviewer` | N+1 queries, unbounded reads, index coverage | complete |
| 5 | `qa-smoke-tester` | Runtime re-verification against the contract (610 assertions) | complete |
| 6 | `security-reviewer` | Tenant isolation, IDOR, injection, mass assignment, auth/authz | complete |

---

## Findings Summary

- **Critical:** 5 (`C1`–`C5`)
- **Important:** 12 (`I1`–`I12`)
- **Minor:** 15 (`M1`–`M15`)

---

## Deduped & Prioritized Findings

### Critical

- [x] **C1 — `_pk_filter` raises `ValueError` on superscript / circled Unicode digits → HTTP 500 on all four 8.12 list pages.**
  `apps/sales/views/SalesAnalytics/_helpers.py:23-25`. The guard `if not value or not value.isdigit(): return None` followed by `int(value)` fails because `str.isdigit()` accepts characters like `'²'` (U+00B2) and `'①'` (U+2460) that `int()` refuses.
  *Fix:* Delegate to house helper `from apps.core.crud import as_db_int` (which uses `.isdecimal()` and handles overflow). Fixed — `9ff8a760` `fix(sales): delegate _pk_filter to as_db_int to handle unicode digits and overflow`.

- [x] **C2 — N+1 chained FK hops in `funnel_conversion_record_detail` and edit views.**
  `apps/sales/views/SalesAnalytics/FunnelConversionRecords.py:126-134`. Detail template displays `{{ obj.from_stage.pipeline.name }}` and `{{ obj.to_stage.pipeline.name }}`. `select_related` selects `from_stage` and `to_stage`, but omits `from_stage__pipeline` and `to_stage__pipeline`, triggering 2 extra queries per detail/edit page view.
  *Fix:* Add `"from_stage__pipeline"` and `"to_stage__pipeline"` to `select_related`. Fixed — `53daa779` `fix(sales): add from_stage__pipeline and to_stage__pipeline to select_related in FunnelConversionRecord detail and edit views`.

- [x] **C3 — N+1 query in `StageVelocityAnalysisForm` choice rendering (`PipelineStage.__str__` chained FK hop).**
  `apps/sales/forms/SalesAnalytics/StageVelocityAnalyses.py:10-54`. When `StageVelocityAnalysisForm` renders `pipeline_stage` choices, `PipelineStage.__str__` evaluates `self.pipeline`. Without `select_related("pipeline")`, every choice issues a query.
  *Fix:* In `StageVelocityAnalysisForm.__init__`, set `self.fields["pipeline_stage"].queryset = self.fields["pipeline_stage"].queryset.select_related("pipeline")`. Fixed — `6b75c678` `fix(sales): select_related pipeline on pipeline_stage queryset in StageVelocityAnalysisForm`.

- [x] **C4 — 2x N+1 queries in `FunnelConversionRecordForm` choice rendering (`PipelineStage.__str__` chained FK hop).**
  `apps/sales/forms/SalesAnalytics/FunnelConversionRecords.py:9-56`. Both `from_stage` and `to_stage` choices render `PipelineStage.__str__` evaluating `self.pipeline`, firing $2 \times N$ queries per form load.
  *Fix:* In `FunnelConversionRecordForm.__init__`, apply `.select_related("pipeline")` to `from_stage` and `to_stage` querysets. Fixed — `8948a6d8` `fix(sales): select_related pipeline on from_stage and to_stage in FunnelConversionRecordForm`.

- [x] **C5 — N+1 queries in `RepPerformanceScorecardForm` choice rendering (`QuotaPlan.__str__` and `CoachingScorecard.__str__` chained FK hops).**
  `apps/sales/forms/SalesAnalytics/RepPerformanceScorecards.py:9-100`. `QuotaPlan.__str__` dereferences `self.quota_ref`, and `CoachingScorecard.__str__` dereferences `self.coachee`.
  *Fix:* In `RepPerformanceScorecardForm.__init__`, apply `.select_related("quota_ref")` on `quota_plan` and `.select_related("coachee")` on `coaching_scorecard`. Fixed — `08d60194` `fix(sales): select_related quota_ref and coachee in RepPerformanceScorecardForm`.

---

### Important

- [x] **I1 — `quota_attainment_pct` overflows its `DECIMAL(6,2)` column; `editable=False` removes it from validation.**
  `apps/sales/models/SalesAnalytics/RepPerformanceScorecards.py:194-199, 321-325`. Computed as `revenue_closed / quota_target * 100` with no upper bound; `quota_target` can be `0.01`, producing values > 9999.99. `average_deal_size` has the same issue.
  *Fix:* In `RepPerformanceScorecard.save()`, clamp with `min(computed, _MAX_QUOTA_ATTAINMENT_PCT)` and `min(computed, _MAX_AVERAGE_DEAL_SIZE)`. Fixed — `e713b70d` `fix(sales): clamp average_deal_size and quota_attainment_pct in RepPerformanceScorecard save`.

- [x] **I2 — The seeder is idempotent only within a calendar day — three of the four key sets accumulate a new row per day.**
  `apps/sales/management/commands/seed_sales.py:3232-3234`. `period_start = today - timedelta(days=90)` and `period_end = today`; three guards key on `(entity, period_start)`, which drifts daily.
  *Fix:* Anchor `period_start` and `period_end` to fixed calendar boundaries (e.g. current quarter start/end or stable fixed dates). Fixed — `c2a12eba` `fix(sales): anchor seeder period_start and period_end to stable calendar quarter boundaries`.

- [x] **I3 — The seeded `stage_to_stage` funnel record can violate the model's own `clean()` sequence rule.**
  `apps/sales/management/commands/seed_sales.py:3346, 3357-3358`. `objects.create()` does not call `clean()`. If `open_stages[0]` and `open_stages[1]` span different pipelines or share sequence, `to_stage.sequence > from_stage.sequence` is violated.
  *Fix:* Pick stages explicitly from the same pipeline with strictly increasing sequence. Fixed — `60a0c470` `fix(sales): pick stage_to_stage funnel stages from same pipeline with strictly increasing sequence`.

- [x] **I4 — The seeded "bottleneck" is the fastest stage — the demo board contradicts itself.**
  `apps/sales/management/commands/seed_sales.py:3313-3333`. `idx == 0` (median 4 days) is flagged as bottleneck while `idx == 2` (median 16 days) is not.
  *Fix:* Flag the slowest stage (`idx == 2` or `idx == len - 1`) as bottleneck. Fixed — `8c0954de0` by setting `median_days = Decimal(16 - idx * 6)` so the first stage (`idx == 0`) is the slowest (16 days) and matches `is_bottleneck=True`.

- [x] **I5 — Missing `@tenant_admin_required` on mutating views (`create` and `edit`).**
  `WinLossDebriefs.py:154, 179`, `StageVelocityAnalyses.py:115, 140`, `FunnelConversionRecords.py:143, 168`, `RepPerformanceScorecards.py:157, 182`. All 4 `create` and `edit` views use `@login_required` instead of `@tenant_admin_required`.
  *Fix:* Apply `@tenant_admin_required` decorator to all 8 create and edit views. Fixed — `113219b7`, `6d785c18`, `aff71c66`, `15635035` `fix(sales): require tenant_admin_required on create and edit views across SalesAnalytics`.

- [x] **I6 — Empty badge pill rendered via non-existent `get_is_bottleneck_display` on `BooleanField` in templates.**
  `templates/sales/salesanalytics/stagevelocityanalysis/list.html:184`, `detail.html:23, 146, 252`. `is_bottleneck` is `models.BooleanField(default=False)` without choices. `{{ analysis.get_is_bottleneck_display }}` evaluates to `""`, rendering an empty badge `<span class="badge badge-muted"></span>`.
  *Fix:* Add `@property def bottleneck_display(self): return "Bottleneck" if self.is_bottleneck else "Normal"` to `StageVelocityAnalysis` and update templates. Fixed — `2d6949e9`, `d6c8ff32`, `188d5732` `feat/fix(sales): add bottleneck_display property and update stage velocity analysis templates`.

- [x] **I7 — Python loop aggregation over entire model table in `benchmark_console`.**
  `apps/sales/views/SalesAnalytics/AnalyticsConsoles.py:1221-1226`. Loads all `QuotaPlan` rows into memory and sums `quota_ref.target_amount` in Python.
  *Fix:* Use `QuotaPlan.objects.filter(tenant=tenant).aggregate(count=Count("id"), target_total=Sum("quota_ref__target_amount"))`. Fixed — `1e06099e` `fix(sales): use SQL aggregate for QuotaPlan target_total in benchmark_console`.

- [x] **I8 — Python loop `sum()` and redundant count query in `_activity_totals`.**
  `apps/sales/views/SalesAnalytics/AnalyticsConsoles.py:1154-1157`. Pulls `planned_minutes` flat into Python to sum, and fires a separate count query.
  *Fix:* Combine into single aggregate: `in_period.aggregate(auto_captured=Count("id", filter=Q(is_auto_captured=True)), planned_minutes=Sum("planned_minutes"))`. Fixed — `d4c56f8e` `fix(sales): combine activity totals count and sum into single aggregate`.

- [ ] **I9 — Full table scan with Python filtering in `_benchmark_rows`.**
  `apps/sales/views/SalesAnalytics/AnalyticsConsoles.py:1353, 1370`. Fetches un-benchmarked rows over the wire only to discard them in Python.
  *Fix:* Filter in SQL: `benchmark_pct__isnull=False` and `benchmark_days__isnull=False`.

- [ ] **I10 — Unbounded querysets rendered on console boards.**
  `apps/sales/views/SalesAnalytics/AnalyticsConsoles.py:641-654, 916-923, 1001-1020`. `open_actions`, `funnel_rows`, and `scorecard_rows` render unbounded rows.
  *Fix:* Cap display lists with `[:ROW_LIMIT]` (25).

- [ ] **I11 — Dead queries executed in `win_loss_debrief_list` and `rep_performance_scorecard_list`.**
  `WinLossDebriefs.py:87-104` queries `outcomes`, `accounts`, `users`; `RepPerformanceScorecards.py:105-107` queries `currencies`, `quota_plans`, `managers`. These are never rendered in template filters.
  *Fix:* Remove unused querysets.

- [ ] **I12 — Missing composite indexes on hot sort/filter columns.**
  `WinLossDebrief`: `(tenant, -debriefed_on)`, `(tenant, interview_channel)`. `StageVelocityAnalysis`: `(tenant, -period_end)`. `RepPerformanceScorecard`: `(tenant, -period_end)`.
  *Fix:* Add `models.Index` in `Meta.indexes` and generate incremental migration `0027`.

---

### Minor

- [ ] **M1 — Dead local `amount` in `win_loss_console`.**
  `apps/sales/views/SalesAnalytics/AnalyticsConsoles.py:608`. Assigned, never read.
  *Fix:* Delete the unused line.

- [ ] **M2 — Missing overflow clamping in `FunnelConversionRecord.save()` for derived column.**
  `apps/sales/models/SalesAnalytics/FunnelConversionRecords.py:152-162`. If `FunnelConversionRecord.save()` is called programmatically with `converted_count > entered_count`, the rate exceeds `999.99` and overflows `DECIMAL(5,2)`.
  *Fix:* Clamp `self.conversion_rate_pct = min(rate, Decimal("999.99"))`.

- [ ] **M3 — Uncapped array size in `clean_decision_drivers`.**
  `apps/sales/forms/SalesAnalytics/WinLossDebriefs.py:58-111`. Submitting an excessively large array increases row size and console processing time.
  *Fix:* Enforce `if len(value) > 50: raise ValidationError(...)`.

- [ ] **M4 — Unescaped model number in JavaScript `confirm()` dialogs.**
  `winlossdebrief/detail.html:236`, `stagevelocityanalysis/detail.html:225`, `funnelconversionrecord/detail.html:217`, `repperformancescorecard/detail.html:358`.
  *Fix:* Use `{{ obj.number|escapejs }}`.

- [ ] **M5 — Missing nested `select_related` in `stage_velocity_analysis_delete`.**
  `apps/sales/views/SalesAnalytics/StageVelocityAnalyses.py:175`. Calls `str(obj.pipeline_stage)` which evaluates `stage.pipeline`.
  *Fix:* Change to `.select_related("pipeline", "pipeline_stage__pipeline")`.

- [ ] **M6 — Filter querysets lack `.only()` in list views.**
  `apps/sales/views/SalesAnalytics/WinLossDebriefs.py:86`. Opportunities dropdown fetches full models.
  *Fix:* Use `.only("id", "name")`.

- [ ] **M7 — Inconsistent / deprecated Lucide icon identifiers in console boards and list templates.**
  `boards/analytics_console.html:112`, `boards/velocity_console.html:64`, `boards/funnel_console.html:98`, `boards/benchmark_console.html:98` use `alert-triangle`; `repperformancescorecard/list.html:234` uses `user-square-2`.
  *Fix:* Update to canonical names `triangle-alert`, `square-user`, `trending-down`.

- [ ] **M8 — Dark mode contrast on raw slate callout containers in detail templates.**
  `winlossdebrief/detail.html:177, 186, 195, 204`, `stagevelocityanalysis/detail.html:184, 193`, `repperformancescorecard/detail.html:261, 270, 279, 288`.
  *Fix:* Add `dark:bg-slate-800/50 dark:border-slate-700 dark:text-slate-200`.

- [ ] **M9 — Screen-reader `aria-label` missing on icon-only table action buttons.**
  `winlossdebrief/list.html:196, 205, 211`, `stagevelocityanalysis/list.html:188, 197, 203`, `funnelconversionrecord/list.html:217, 220, 226`, `repperformancescorecard/list.html:207, 216, 222`.
  *Fix:* Add `aria-label` matching `title`.

- [ ] **M10 — `_relation_belongs_to_tenant` duplicated across model modules.**
  `WinLossDebriefs.py:152`, `StageVelocityAnalyses.py:131`, `FunnelConversionRecords.py:127`, `RepPerformanceScorecards.py:273`.
  *Fix:* Maintainability only; consistent with house convention. Note in code.

- [ ] **M11 — The contract's stated premise about `Model.clean()` for Django 5.1.**
  `.claude/tasks/contract-sales-8.12.md:410-411`. `ModelForm._post_clean` calls `full_clean()`, which calls `Model.clean()`.
  *Fix:* Correct the contract text.

- [ ] **M12 — `from_stage` / `to_stage` populated on non-stage funnel rows in seeder.**
  `apps/sales/management/commands/seed_sales.py:3357-3358`.
  *Fix:* Set `from_stage=None, to_stage=None` on `lead_to_opportunity` and `opportunity_to_close`.

- [ ] **M13 — `WinLossDebrief.primary_reason` assigned positionally in seeder.**
  `apps/sales/management/commands/seed_sales.py:3270`.
  *Fix:* Ensure reason result matches outcome result (`won`/`lost`).

- [ ] **M14 — No seeded funnel record falls below its benchmark.**
  `apps/sales/management/commands/seed_sales.py:3368`.
  *Fix:* Set benchmark on one record higher than its conversion rate to exercise the below-benchmark filter.

- [ ] **M15 — `TenantScopedFKAdmin` docstring scope.**
  `apps/sales/admin.py:853`. Documented as 8.13 base class but 8.12 uses it.
  *Fix:* Broaden docstring to indicate reuse across sales sub-modules.
