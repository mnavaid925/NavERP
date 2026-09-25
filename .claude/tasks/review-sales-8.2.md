# Consolidated Review Findings: Sub-module 8.2 (Opportunity & Pipeline Management)

**Base Sha:** `1f60e789d60be6b262bcea17582e9b9e89261935`
**Contract:** `.claude/tasks/contract-sales-8.2.md`
**Status:** Ready for Phase 5 (`code-fixer`)
**Passes Completed:**
1. Code Reviewer (`code-reviewer`) — Complete
2. Explorer (`explorer`) — Complete
3. Frontend Reviewer (`frontend-reviewer`) — Complete
4. Performance Reviewer (`performance-reviewer`) — Complete
5. QA Smoke Tester (`qa-smoke-tester`) — Complete
6. Security Reviewer (`security-reviewer`) — Complete

---

## Actionable Review Findings Catalog

### Critical Findings

- [ ] **[C1]** `apps/sales/views/OpportunityOutcomes/OpportunityOutcomes.py:234-236`: Unhandled `AttributeError` crashing with HTTP 500 on form validation failure in `_opportunity_transition_form_error(form)`. Iterates over `form.fields.values()` looking for `.errors`, but unbound `Field` objects do not have `.errors`. Fix: iterate over `form.errors.values()`.
- [ ] **[C2]** `apps/sales/opportunity_analytics.py:93-98, 162, 222`: Non-aggregated SQL expression `_sales_weighted_expression()` in grouped `.values().annotate()` queries without `Sum(...)`. Breaks on PostgreSQL (`column must appear in the GROUP BY clause or be used in an aggregate function`) and MySQL `ONLY_FULL_GROUP_BY`, and corrupts forecast totals. Fix: wrap expression in `Sum(...)`.
- [ ] **[C3]** `apps/sales/management/commands/seed_sales.py:46-50, 472-482`: Missing `--backfill` CLI option and non-conforming backfill logic in `seed_sales`. Contract specifies `--backfill` flag to safely attach existing CRM opportunities without overwriting probability overrides or stage timestamps. Fix: add `--backfill` argument and implement non-destructive backfill.
- [ ] **[C4]** `apps/sales/views/Workspace.py:454-484`: Unpaginated tenant-wide opportunity materialization & full-table health scan in `opportunity_workspace_list`. Evaluates entire tenant opportunity queryset in memory before paginating (`list(queryset)`), and passes all IDs to `opportunity_pipeline_health_projection` scanning all tenant tasks, communications, events, and audit logs. Fix: paginate at database level before health projection when health filter is empty.
- [ ] **[C5]** `apps/sales/views/OpportunityPipeline/Pipelines.py:615-657, 452-602`: Massive query duplication & unused heavy aggregations in `opportunity_pipeline_visibility`. Calls `_opportunity_pipeline_board_context` which calculates board stages, unplaced deals, rollups, and unfiltered aging only to discard them and recalculate filtered aging. Fix: separate board calculation from lightweight filter context helper.
- [ ] **[C6]** `apps/sales/views/OpportunityTeams/OpportunityTeams.py:90-95, 160-170`: Pessimistic `select_for_update` row locks and `transaction.atomic()` during HTTP GET requests in `opportunity_team_member_add` and `opportunity_team_member_edit`. Causes opportunity deadlocks and lock contention during form browsing. Fix: remove `transaction.atomic()` and `select_for_update()` from GET branches.

---

### Important Findings

- [ ] **[I1]** `templates/sales/opportunity/workspace.html:272-274`, `templates/sales/opportunity/pipeline/board.html:32-46`, `templates/sales/opportunity/pipeline/visibility.html:19-33`: Filter dropdown selection state resets due to Integer/String equality mismatch (`int == str`). Filter IDs are parsed into Python `int` in views, but compared to `|stringformat:'d'` strings in templates (`5 == "5"` is False). Fix: compare `owner_id == owner.pk`, `territory_id == territory.pk`, `pipeline_id == p.pk`.
- [ ] **[I2]** `templates/sales/opportunity/placement.html:17, 27`: `form.instance.pipeline_id` is None on unplaced opportunity, so selecting pipeline and clicking "Load stages" doesn't show selected pipeline and POST action appends `?pipeline=None`. Fix: use `selected_pipeline_id` context/fallback.
- [ ] **[I3]** `apps/sales/views/OpportunityPipeline/Pipelines.py:617-618`: Unhandled `ValueError` crash (HTTP 500) on malformed date parameters in `opportunity_pipeline_visibility`. `parse_date` crashes with `ValueError: month must be in 1..12` when invalid ISO-like date strings are provided (e.g. `?date_from=2026-13-45`). Fix: use `safe_parse_date` from `apps.sales.views._common`.
- [ ] **[I4]** `apps/sales/forms/OpportunityPipeline/Pipelines.py:203-235`, `apps/sales/views/Workspace.py:680-728`: Opportunity placement form allows selecting Won/Lost stages directly, bypassing mandatory Win/Loss Reason requirement and `OpportunityOutcome` logging. Fix: restrict `current_stage` queryset in placement form to `stage_kind="open"` and validate in `clean()`.
- [ ] **[I5]** `templates/sales/opportunity/pipeline/stages.html:16`, `apps/sales/views/OpportunityPipeline/Pipelines.py:195-223, 312-332`: Stage reordering form action submits to `opportunity_pipeline_stages` instead of dedicated `@require_POST @tenant_admin_required` endpoint `opportunity_pipeline_stage_reorder`. Fix: update form action to `sales:opportunity_pipeline_stage_reorder` and remove redundant POST logic from `opportunity_pipeline_stages`.
- [ ] **[I6]** `apps/sales/views/Workspace.py:339`, `templates/sales/opportunity/workspace.html:199, 244`: Audit log detail links exposed to non-admin users leading to HTTP 403 `PermissionDenied` because `core:auditlog_detail` is `@tenant_admin_required`. Fix: check `is_tenant_admin` or `is_superuser` before generating link, or render as plain text for non-admins.
- [ ] **[I7]** `apps/sales/admin.py:223-229`: `OpportunityPipelinePlacementAdmin` bypasses Sales service & stage validation. Fix: add `has_add_permission=False` and `has_change_permission=False` so placements cannot bypass service-layer validation and auditing.
- [ ] **[I8]** `apps/sales/admin.py:207-279`: Missing `list_select_related` and `raw_id_fields` on 8.2 ModelAdmin classes (`PipelineStageAdmin`, `OpportunityPipelinePlacementAdmin`, `OpportunityTeamMemberAdmin`, `CompetitorProfileAdmin`, `OpportunityCompetitorAdmin`, `OpportunityOutcomeAdmin`), causing N+1 queries. Fix: configure `list_select_related` and `raw_id_fields`.
- [ ] **[I9]** `apps/sales/opportunity_services.py`: Missing export `sales_compute_health` matching contract. Fix: import/alias `opportunity_pipeline_health as sales_compute_health` in `opportunity_services.py` and `__all__`.
- [ ] **[I10]** `apps/sales/views/OpportunityPipeline/Pipelines.py:487-516`, `apps/sales/opportunity_analytics.py:591-595`: Redundant query execution in board view (re-querying placements for stage age) and `opportunity_pipeline_health_projection` re-querying passed opportunity instances. Fix: reuse loaded placement data and passed opportunities.
- [ ] **[I11]** `apps/sales/models/OpportunityPipeline/Pipelines.py`, `CompetitiveIntelligence/CompetitiveIntelligence.py`, `OpportunityOutcomes/OpportunityOutcomes.py`: Missing composite indexes on high-frequency tenant-scoped filters. Fix: add `(tenant, pipeline, current_stage)`, `(tenant, stage_entered_at)`, `(tenant, closed_at)`, `(tenant, competitor_profile)` indexes.
- [ ] **[I12]** `apps/sales/opportunity_analytics.py:278-280, 691-693`: Date function wrapping (`__date__gte`, `__date__lte`) defeating B-tree index range scans in `sales_stage_age_rows` and `_sales_outcome_queryset`. Fix: filter using timezone-aware datetime boundaries.
- [ ] **[I13]** `apps/sales/management/commands/seed_sales.py:468-513`: O(N) iterative queries and unbatched inserts in seeder. Fix: pre-fetch existing placement/team/outcome sets and win/loss reasons outside loop.
- [ ] **[I14]** `templates/sales/opportunity/workspace.html`, `pipeline/detail.html`, `competitor/detail.html`, `winlossreason/detail.html`: Missing standard 2-column actions sidebar (`.layout-2col`) on detail templates. Fix: update layout to standard 2-column detail page layout.
- [ ] **[I15]** `templates/sales/opportunity/pipeline/detail.html:52, 75` and `pipeline/stages.html:31, 54`: Table empty-state colspan mismatch on permission-gated action headers (colspan 10 vs 9 for non-admin in detail, colspan 9 vs 8 for non-admin in stages). Fix: condition colspan on `request.user.is_tenant_admin`.
- [ ] **[I16]** `templates/sales/opportunity/pipeline/form.html:19, 26` and `pipeline/stages.html:19, 20, 67, 73`: Missing accessibility `role="alert"` on form error blocks. Fix: add `role="alert"` attribute.

---

### Minor Findings

- [ ] **[M1]** `templates/sales/opportunity/competitor/detail.html:53`: Links opportunity to `crm:opportunity_detail` instead of `sales:opportunity_workspace_detail`. Fix: update link to `sales:opportunity_workspace_detail`.
- [ ] **[M2]** `apps/sales/views/Workspace.py:743-764`: Opportunity unplace action lacks ownership or admin authorization check. Fix: verify user is admin, opportunity owner, or active team co-owner/approver before deleting placement.
- [ ] **[M3]** `templates/sales/opportunity/pipeline/stages.html:45-48`, `pipeline/detail.html:70`, `competitor/detail.html:73`: Icon-only action buttons (`.btn-icon`) lack `aria-label` attribute. Fix: add descriptive `aria-label`.
- [ ] **[M4]** `templates/sales/opportunity/pipeline/stages.html:45, 85-110`: Pipeline stage reorder JS does not update button `disabled` states on DOM reordering. Fix: update disabled attributes in reorder handler.
- [ ] **[M5]** `templates/sales/opportunity/competitor/form.html:9`, `competitor/link_form.html:13`, `winlossreason/form.html:9`: Missing Lucide icons on back/cancel links. Fix: add arrow-left Lucide icon to back links.
- [ ] **[M6]** `templates/sales/opportunity/pipeline/board.html:138`: Missing currency code on board unplaced opportunities table (`{{ opp.amount }}`). Fix: display `{{ opp.currency.code|default:opp.currency|default:"" }} {{ opp.amount }}`.
- [ ] **[M7]** `templates/sales/opportunity/placement.html:53`: Missing unit label in placement stage table (`{{ stage.target_days }}` without `days`). Fix: render `{{ stage.target_days }} days`.
- [ ] **[M8]** `templates/sales/opportunity/winlossreason/detail.html:55`: Chained N+1 through `__str__` cascades when rendering `{{ outcome.competitor_link }}`. Fix: render `{{ outcome.competitor_link.competitor_profile.party.name }}` directly.
- [ ] **[M9]** `apps/sales/opportunity_analytics.py:101-127`: In-memory placement stale calculation fetching non-target stages. Fix: filter `current_stage__target_days__isnull=False` inside `_sales_rollup_stale_counts`.
- [ ] **[M10]** `apps/sales/views/OpportunityPipeline/Pipelines.py:467-468`: Missing `.distinct()` on Owner ID Extraction in Board View (`values_list("owner_id", flat=True)`). Fix: add `.distinct()`.
- [ ] **[M11]** `apps/sales/views/Workspace.py:559-563, 572-579`: Unused querysets materialized in `opportunity_workspace_detail` (`competitor_profiles`, `win_loss_reasons`). Fix: remove unused queries from view context.
- [ ] **[M12]** `apps/sales/views/OpportunityPipeline/Pipelines.py:131-132`: Split count queries in pipeline detail view. Fix: combine into single aggregate query.
- [ ] **[M13]** `templates/sales/opportunity/pipeline/visibility.html:80-97`: Unbounded result rendering in visibility view tables. Fix: limit to top 100 stalest placements or paginate.
- [ ] **[M14]** `apps/sales/tests/`: Automated test suite for Sub-module 8.2 (To be implemented in Phase 6).
