# Review Findings — Sub-module 10.2: ETL/ELT & Data Pipelines (Module 10 — Business Intelligence, `bi`)

- **Sub-module:** 10.2 ETL/ELT & Data Pipelines
- **Module:** 10 Business Intelligence (`apps/bi`)
- **Review Date:** 2026-11-03
- **Changeset:** `2c3e7ffe83fd40e1d73ab07326fb280ee14249fa...632bd1cfa56436ea061cd93d8e3980166ad6a137`
- **Review Phase:** 4 Serial Review Pass (1: `code-reviewer` → 2: `explorer` → 3: `frontend-reviewer` → 4: `performance-reviewer` → 5: `qa-smoke-tester` → 6: `security-reviewer`)

---

## Pass 1: `code-reviewer` Findings

### C1. Corrupted `write_audit_log` Arguments Across All 11 Call Sites
- **Files**:
  - `apps/bi/views/EtlPipelines/EtlPipelines.py`
  - `apps/bi/views/EtlPipelines/TransformationSteps.py`
  - `apps/bi/views/EtlPipelines/EtlPipelineVersions.py`
- **Defect**: The shared utility signature in `apps/core/utils.py` is `write_audit_log(user, obj, action, changes=None, tenant=None)`. All 11 view call sites inverted the arguments by passing `(request.tenant, request.user, "bi.etl_pipeline.create", ...)`. This causes `user` to receive `Tenant`, `obj` to receive `User`, and `action` to exceed `varchar(10)`, corrupting audit logs.
- **Fix**: Realign all 11 call sites to `write_audit_log(request.user, instance, "create"/"update"/"delete"/"trigger"/"promote", changes=..., tenant=request.tenant)`, calling delete logs before instance deletion.

### C2. Verify Migration `0004_*.py` Tracking
- **File**: `apps/bi/migrations/0004_etlpipeline_etlpipelineversion_etlpipelinerun_and_more.py`
- **Defect**: Ensure `0004_*.py` is cleanly applied, migrations check passes, and all 4 tables exist with proper constraints.
- **Fix**: Verified committed in `632bd1cf`. Keep in checklist to verify test suite runner loads it.

### I1. Unvalidated `target_environment` in `etl_pipeline_version_promote`
- **File**: `apps/bi/views/EtlPipelines/EtlPipelineVersions.py`
- **Defect**: `target_env = request.POST.get("target_environment", "production")` does not validate against `EtlPipelineVersion.ENVIRONMENT_CHOICES`. Arbitrary string could be saved to `environment`.
- **Fix**: Validate `target_env in dict(EtlPipelineVersion.ENVIRONMENT_CHOICES)`.

### I2. `EtlPipelineVersionForm.save()` Fails to Re-snapshot When Editing Existing Version
- **File**: `apps/bi/forms/EtlPipelines/EtlPipelineVersions.py`
- **Defect**: When editing an existing version that already has a saved DAG snapshot, clearing `dag_definition_raw` fails to trigger a re-snapshot because `not instance.dag_definition` evaluates to False.
- **Fix**: Re-snapshot from `instance.pipeline.steps.all()` whenever raw input is empty.

### I3. Potential `AttributeError` in `EtlPipelineRun.__str__` if `started_at` is None
- **File**: `apps/bi/models/EtlPipelines/EtlPipelineRuns.py`
- **Defect**: Calling `self.started_at.strftime(...)` without null-check crashes if `started_at` is None on an unsaved/pending run.
- **Fix**: Guard formatting: `self.started_at.strftime(...) if self.started_at else 'Pending'`.

### I4. Missing Composite Index on `EtlPipelineRun(tenant, -started_at)`
- **File**: `apps/bi/models/EtlPipelines/EtlPipelineRuns.py`
- **Defect**: Model orders by `-started_at` and is filtered by `tenant`, but lacks index `(tenant, -started_at)`.
- **Fix**: Add `models.Index(fields=["tenant", "-started_at"], name="idx_bexr_ten_start_desc")`.

### I5. Inconsistent Delete Redirect Target from Transformation Steps and Versions List Views
- **Files**: `apps/bi/views/EtlPipelines/TransformationSteps.py`, `apps/bi/views/EtlPipelines/EtlPipelineVersions.py`
- **Defect**: Deleting from list view redirects to `bi:etl_pipeline_detail` instead of staying on the list view.
- **Fix**: Support redirecting back to `bi:transformation_step_list` / `bi:etl_pipeline_version_list`.

### I6. Missing Cross-Field Validation for `cron_expression` when `trigger_type == 'scheduled_cron'`
- **File**: `apps/bi/forms/EtlPipelines/EtlPipelines.py`
- **Defect**: If `trigger_type == 'scheduled_cron'`, blank `cron_expression` is permitted.
- **Fix**: Require `cron_expression` in `clean()` when trigger type is scheduled cron.

### M1. CSV Export in `etl_pipeline_list` Leaves "Source Staging" Blank for Bound Ingestion Pipelines
- **File**: `apps/bi/views/EtlPipelines/EtlPipelines.py`
- **Defect**: CSV export writes `p.source_staging_table` directly; when bound via `source_ingestion_pipeline` it is empty.
- **Fix**: Use `p.source_ingestion_pipeline.target_staging_table if p.source_ingestion_pipeline else p.source_staging_table`.

### M2. Redundant SLA Formatting in `etl_pipeline/detail.html`
- **File**: `templates/bi/etl_pipelines/etl_pipeline/detail.html`
- **Defect**: `{{ pipeline.sla_timeout_seconds }}s ({{ pipeline.sla_timeout_seconds|floatformat:0 }} sec)` renders redundant text.
- **Fix**: Simplify to `{{ pipeline.sla_timeout_seconds }}s`.

### M3. Context Variable `available_sources` in Canvas Template
- **File**: `templates/bi/etl_pipelines/etl_pipeline/canvas.html`
- **Defect**: `available_sources` passed in context can be surfaced in a node source selector.

### M4. `EtlPipelineRunForm` Hooking
- **File**: `apps/bi/forms/EtlPipelines/EtlPipelineRuns.py`
- **Defect**: Form defined but runs are triggered via action. Keep documented as manual backfill trigger form.

### M5. Semantic Version Duplicate Validation
- **File**: `apps/bi/forms/EtlPipelines/EtlPipelineVersions.py`
- **Defect**: Form should validate that `version_number` is not already used on the same pipeline in this tenant.
