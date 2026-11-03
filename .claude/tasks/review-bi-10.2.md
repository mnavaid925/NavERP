# Review Findings — Sub-module 10.2: ETL/ELT & Data Pipelines (Module 10 — Business Intelligence, `bi`)

- **Sub-module:** 10.2 ETL/ELT & Data Pipelines
- **Module:** 10 Business Intelligence (`apps/bi`)
- **Review Date:** 2026-11-03
- **Changeset:** `2c3e7ffe83fd40e1d73ab07326fb280ee14249fa...632bd1cfa56436ea061cd93d8e3980166ad6a137`
- **Review Passes Completed:** 6/6 Serial Passes (`code-reviewer` → `explorer` → `frontend-reviewer` → `performance-reviewer` → `qa-smoke-tester` → `security-reviewer`)
- **Status:** Deduplicated & Prioritized for Phase 5 (`code-fixer`)

---

## Critical Findings

- [x] **C1**: `write_audit_log` Argument Inversion across all 11 call sites in `apps/bi/views/EtlPipelines/{EtlPipelines,TransformationSteps,EtlPipelineVersions}.py`. Utility signature in `apps/core/utils.py` is `write_audit_log(user, obj, action, changes=None, tenant=None)`. Calling with `(request.tenant, request.user, "bi.etl_pipeline.create", ...)` saves `user=NULL`, logs `auth.User` as the target entity, and truncates action beyond varchar(10). Realign all 11 call sites to `write_audit_log(request.user, instance, "create"|"update"|"delete"|"trigger"|"promote", changes=..., tenant=request.tenant)`, calling delete logs before instance deletion.
- [x] **C2**: Lesson L10 Violation in Template Filter Arguments when `promoted_by` is None. In `templates/bi/etl_pipelines/etl_pipeline/detail.html` (L250), `etl_pipeline_version/list.html` (L123), and `etl_pipeline_version/detail.html` (L94), `default:ver.promoted_by.username` raises `VariableDoesNotExist` and throws 500 when `promoted_by` is None. Replace with `{% if ver.promoted_by %}{{ ver.promoted_by.get_full_name|default:ver.promoted_by.username }}{% else %}System{% endif %}`.
- [x] **C3**: Stored XSS in inline JavaScript confirm handlers via `version_number`. In `templates/bi/etl_pipelines/etl_pipeline_version/{list,detail}.html`, `version.version_number` is interpolated into `onclick="return confirm('... {{ version.version_number }} ...');"`. Validate `version_number` with regex `^[a-zA-Z0-9_\.\-]+$` in `EtlPipelineVersionForm.clean_version_number()` and apply `|escapejs` in templates.
- [x] **C4**: Missing Composite Index on `EtlPipelineRun(tenant, -started_at)`. `EtlPipelineRun` default ordering is `['-started_at']` with `tenant` scoping. Existing indexes have `pipeline` or `status` preceding `started_at`, causing table scans/filesorts on tenant-scoped list queries. Add `models.Index(fields=["tenant", "-started_at"], name="idx_bexr_ten_start_desc")` and generate migration `0005_...`.
- [x] **C5**: Chained Foreign Key Dereference in `__str__` Methods for `EtlPipelineRun` and `EtlPipelineVersion`. Both access `self.pipeline.name`, causing N+1 queries when rendered without `select_related("pipeline")`. Simplify `__str__` to use local fields.

---

## Important Findings

- [x] **I1**: Unvalidated `target_environment` in `etl_pipeline_version_promote`. `target_env = request.POST.get("target_environment", "production")` does not validate against `EtlPipelineVersion.ENVIRONMENT_CHOICES`. Validate `target_env in dict(EtlPipelineVersion.ENVIRONMENT_CHOICES)`.
- [x] **I2**: `EtlPipelineVersionForm.save()` Fails to Re-snapshot When Editing Existing Version. When editing an existing version that already has a saved DAG snapshot, clearing `dag_definition_raw` fails to trigger a re-snapshot because `not instance.dag_definition` evaluates to False. Re-snapshot from `instance.pipeline.steps.all()` whenever raw input is empty.
- [x] **I3**: Missing Composite Index on `EtlPipelineVersion(tenant, -created_at)`. Model orders by `['-created_at']` with `tenant` filter, requiring in-memory sort. Add `models.Index(fields=["tenant", "-created_at"], name="idx_bpvr_ten_created_desc")` in migration `0005_...`.
- [x] **I4**: Multiple Separate Count Queries on Run and Pipeline Lists. In `etl_pipeline_run_list` (3 counts) and `etl_pipeline_list` (2 counts), replace separate `count()` calls with single conditional aggregations using `Count("id", filter=Q(...))`.
- [x] **I5**: Missing Deferral of Large Text & JSON Fields in list views. `EtlPipelineRun.execution_log` (TextField) and `step_progress` (JSONField) in `etl_pipeline_run_list` and `etl_pipeline_detail`, and `EtlPipelineVersion.dag_definition` in `etl_pipeline_version_list`. Add `.defer("execution_log", "step_progress")` and `.defer("dag_definition")`.
- [x] **I6**: Missing Cross-Field Validation for `cron_expression` when `trigger_type == 'scheduled_cron'`. Require `cron_expression` in `EtlPipelineForm.clean()` when trigger type is scheduled cron.
- [x] **I7**: Concurrency Guard on `etl_pipeline_trigger`. Guard against duplicate active runs: if `pipeline.runs.filter(status="running").exists()`, warn user and redirect instead of creating duplicate running run.
- [x] **I8**: Inconsistent Delete Redirect Target from Transformation Steps and Versions List Views. Support redirecting back to `bi:transformation_step_list` and `bi:etl_pipeline_version_list` when deleted from list view context.
- [x] **I9**: Pagination Bar Flex Justification in List Templates. List templates render `.pagination` without `justify-between`, clustering summary text and navigation buttons to the right. Add `justify-between` to `.pagination`.
- [x] **I10**: Cross-Model Validation in `EtlPipelineRunForm`. Verify `version.pipeline_id == pipeline.id` when both are submitted.

---

## Minor Findings

- [x] **M1**: CSV Export in `etl_pipeline_list` Leaves "Source Staging" Blank for Bound Ingestion Pipelines. Use `p.source_ingestion_pipeline.target_staging_table if p.source_ingestion_pipeline else p.source_staging_table`.
- [x] **M2**: Redundant SLA Formatting in `etl_pipeline/detail.html`. Simplify `{{ pipeline.sla_timeout_seconds }}s ({{ pipeline.sla_timeout_seconds|floatformat:0 }} sec)` to `{{ pipeline.sla_timeout_seconds }}s`.
- [ ] **M3**: Redundant `total_count` Queries in Step and Version List Views. Remove unused `total_count = queryset.count()` calls.
- [ ] **M4**: ModelForm Dropdown Field Optimization. Add `.only("id", "name", "number")` to form dropdown querysets for `pipeline`.
- [ ] **M5**: Delete Actions Rendered for Non-Tenant Admins in UI Templates. Wrap delete forms with `{% if request.user.is_superuser or request.user.is_tenant_admin %}`.
- [ ] **M6**: Delete Icon Button Styling Consistency. Use `btn-icon btn-outline text-danger` for consistent ghost action buttons.
- [ ] **M7**: Breadcrumb Separator Class. Add `class="sep"` to breadcrumb separators.
- [ ] **M8**: Missing `list_select_related` in Django Admin for `TransformationStepAdmin`, `EtlPipelineVersionAdmin`, and `EtlPipelineRunAdmin`.
- [ ] **M9**: Semantic Version Duplicate Validation. Check in `EtlPipelineVersionForm.clean()` that `version_number` is not already used on the same pipeline in this tenant.
- [ ] **M10**: Active Production Version Deletion Block. In `etl_pipeline_version_delete`, prevent deleting active production version without prior deprecation/reassignment.
- [ ] **M11**: Add Delete Action Button on Transformation Step and Pipeline Version Detail Views.
