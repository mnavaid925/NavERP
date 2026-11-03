# Review Findings & Action Register: Sub-module 9.20 Multi-Store & Platform Operations

**BASE**: `bc7ed8659edd38e005b53692bdb51ce0501e18da`  
**HEAD**: Sub-module 9.20 Changeset  
**Review Passes Completed**: 6 of 6 (`code-reviewer`, `explorer`, `frontend-reviewer`, `performance-reviewer`, `qa-smoke-tester`, `security-reviewer`)  
**Status**: Complete — All 19 Findings Burned Down (Phase 5 Complete)

---

## Executive Summary
The architecture, modular structure, core spine reuse, URL configuration, and navigation wiring for Sub-module 9.20 are well engineered and strictly adhere to project standards. All read views enforce tenant isolation via `ecommerce_scope` and `ecommerce_object`, all 19 views require login, all mutating actions require POST and CSRF, and there are zero template comment leaks.

Six serial review passes identified 3 Critical, 10 Important, and 6 Minor findings that were burned down by the `code-fixer` agent in Phase 5 in strict ID order.

---

## Critical Findings

- [x] **C1**: `apps/ecommerce/views/MultiStore/*.py` — Forms instantiated without `tenant=request.tenant` in create views (`storefront_instance_create`, `storefront_catalog_assignment_create`, `platform_environment_create`, `deployment_pipeline_create`). Because `self.tenant` evaluates to `None` in `TenantModelForm.__init__`, foreign key querysets are not scoped to the tenant on create, leaking other tenants' records in select dropdowns.  
  *Fix*: Pass `tenant=request.tenant` into form constructors across all create and edit handlers. — fixed: `c5b76902`, `e2d6fb65`, `69574e6e`, `0f193e43` `fix(ecommerce): pass tenant into MultiStore forms to scope querysets`

- [x] **C2**: `apps/ecommerce/views/MultiStore/*.py` (all 15 mutating POST handlers) — Transposed arguments in `write_audit_log(request.user, action, obj, changes)` instead of `write_audit_log(request.user, obj, action, changes)`. Because `obj` receives a string verb, `ContentType.objects.get_for_model(str)` throws `AttributeError: type object 'str' has no attribute '_meta'`, crashing every create, edit, delete, toggle, promote, and rollback POST mutation with HTTP 500.  
  *Fix*: Reorder arguments to `write_audit_log(request.user, obj, action, changes)`. — fixed: `f8035f5f`, `277841fc`, `b8cde7bb`, `3a6fd8b9` `fix(ecommerce): reorder write_audit_log arguments in MultiStore views`

- [x] **C3**: `apps/ecommerce/views/MultiStore/StorefrontInstances.py:68-73` — Sliced queryset subquery `environments = storefront.environments.all()[:10]` passed into `filter(environment__in=environments)` triggers MariaDB 10.4 error 1235 (`LIMIT & IN/ALL/ANY/SOME subquery`). In addition, `recent_deployments` is unused and not rendered in `storefront_instance/detail.html`.  
  *Fix*: Remove the dead subquery and context variable. — fixed: `687390f6` `fix(ecommerce): remove sliced subquery and dead deployments context in storefront detail view`

---

## Important Findings

- [x] **I1**: `apps/ecommerce/views/MultiStore/StorefrontCatalogAssignments.py:32-34` & `DeploymentPipelines.py:32-34` — Integer foreign key filters (`storefront_filter`, `environment_filter`) lack `.isdigit()` guards, causing an unhandled `ValueError` (HTTP 500) on non-numeric input (e.g. `?storefront=abc`).  
  *Fix*: Guard with `if param and param.isdigit(): queryset = queryset.filter(...)`. — fixed: `2872c77a`, `17960c35` `fix(ecommerce): add isdigit guards on integer FK filters`

- [x] **I2**: `apps/ecommerce/views/MultiStore/StorefrontInstances.py:92-94, 123-125` & `DeploymentPipelines.py:161-174` — Multi-record mutations lack atomic transaction protection (default storefront reassignment and deployment promotion with active slot switch).  
  *Fix*: Wrap multi-table state mutations in `with transaction.atomic():`. — fixed: `d8a3969c`, `58f9a5bf` `fix(ecommerce): wrap multi-record state mutations in transaction atomic`

- [x] **I3**: `apps/ecommerce/views/MultiStore/DeploymentPipelines.py:161-182, 187-200` — Missing status / state machine guards on `deployment_promote` and `deployment_rollback` in the view. A direct POST can promote a failed or unbuilt release to 100% live traffic or roll back an inactive release.  
  *Fix*: Add server-side status validation before state transitions. — fixed: `5d28dbdb` `fix(ecommerce): add status state machine guards on deployment promote and rollback`

- [x] **I4**: `apps/ecommerce/forms/MultiStore/DeploymentPipelines.py:8-12` — Mass assignment / gate bypass in `DeploymentPipelineForm`. The form permits selecting `status='promoted_active'` and `traffic_percentage=100` on creation, bypassing the promote workflow and environment slot synchronization.  
  *Fix*: In `clean()`, disallow `status='promoted_active'` and `traffic_percentage > 0` on new records. — fixed: `632f7fa8` `fix(ecommerce): disallow promoted status and positive traffic on new deployment pipelines`

- [x] **I5**: `templates/ecommerce/multi_store/deployment_pipeline/detail.html:44, 54` — Missing `|escapejs` in inline JavaScript confirmation handlers for promotion and rollback buttons. Quotes in release tags or environment names break JS and risk XSS.  
  *Fix*: Wrap interpolated variables in `|escapejs`. — fixed: `217f737f` `fix(ecommerce): escape JavaScript parameters in pipeline promote and rollback confirms`

- [x] **I6**: `apps/ecommerce/views/MultiStore/StorefrontCatalogAssignments.py:18, 66` & `StorefrontInstances.py:65` — N+1 query lookups on `storefront__default_currency` and `CatalogProduct.sku` (`prefetch_related("product__variants")`) in catalog assignment table loops.  
  *Fix*: Add `select_related("storefront__default_currency", ...)` and `prefetch_related("product__variants")`. — fixed: `7023e554`, `82be87d5` `perf(ecommerce): prefetch product variants and select currency to eliminate N+1 queries`

- [x] **I7**: `apps/ecommerce/models/MultiStore/StorefrontCatalogAssignments.py:58` & `DeploymentPipelines.py:69` — Chained FK lookups in model `__str__` methods (`self.storefront.name`, `self.environment.name`), causing N+1 queries during audit logging and form rendering (Rule L18).  
  *Fix*: Use non-FK fields (`number`, `custom_title`, `release_version`, `status`) in `__str__`. — fixed: `c07c75fe`, `ded6ae8a` `perf(ecommerce): eliminate chained FK queries in __str__ methods`

- [x] **I8**: `templates/ecommerce/multi_store/deployment_pipeline/detail.html:159-165` & `storefront_catalog_assignment/detail.html:133` — Inconsistent status badge mappings. Failed/rolled-back deployments fall back to amber badges instead of red, and storefront status in assignment detail is hardcoded to green.  
  *Fix*: Explicitly map all status values to proper theme.css color badges (`badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-slate`). — fixed: `c8475edb`, `719c3774` `style(ecommerce): map status values to proper color badges`

- [x] **I9**: `apps/ecommerce/views/MultiStore/PlatformEnvironments.py:43, 55` & `templates/ecommerce/multi_store/platform_environment/list.html` — Unused `storefronts` context variable in `platform_environment_list` without filter logic in view or select dropdown in template.  
  *Fix*: Implement storefront filter in `platform_environment_list` and add the select dropdown to the list template. — fixed: `03c8e211`, `b5202bd4` `feat(ecommerce): add storefront filter logic and select dropdown in platform environment list`

- [x] **I10**: `apps/ecommerce/views/MultiStore/StorefrontInstances.py:165-171` — Incomplete status guard in `storefront_toggle_status`. If a storefront is in `draft`, `suspended`, or `archived`, the view performs a no-op save but flashes a success message.  
  *Fix*: Validate that `storefront.status in ["active", "maintenance"]` before toggling, returning a warning otherwise. — fixed: `e4643787` `fix(ecommerce): validate storefront status is active or maintenance before toggle`

---

## Minor Findings

- [x] **M1**: `apps/ecommerce/views/MultiStore/*.py` — Form prepopulation `initial["storefront"]` and `initial["environment"]` from GET parameters lack `.isdigit()` validation.  
  *Fix*: Guard with `if param and param.isdigit(): initial[...] = int(param)`. — fixed: `e24280ba`, `ec38b397`, `c86aaec2` `fix(ecommerce): add isdigit validation to initial GET parameters in create views`

- [x] **M2**: `apps/ecommerce/views/MultiStore/*.py` — `page_number = request.GET.get("page")` lacks canonical fallback.  
  *Fix*: Use `page_number = request.GET.get("page", 1)`. — fixed: `488960d6`, `72dd13a4`, `c7ed9908`, `ae108cfa` `fix(ecommerce): add canonical fallback for page number in list views`

- [x] **M3**: `templates/ecommerce/multi_store/storefront_catalog_assignment/list.html:113` — Undefined utility class `text-info`.  
  *Fix*: Replace with `<span class="badge badge-info text-xs mt-0.5">`. — fixed: `921e2e18` `style(ecommerce): replace undefined text-info with badge badge-info in catalog assignments list`

- [x] **M4**: `templates/ecommerce/multi_store/deployment_pipeline/detail.html:27-31, 109` — Missing fallback for `'primary'` target slot and static badge on pipeline detail.  
  *Fix*: Map target slot choices to `badge-green`, `badge-info`, `badge-slate`. — fixed: `0584a17d` `style(ecommerce): map target slot choices to proper color badges in pipeline detail`

- [x] **M5**: `apps/ecommerce/models/MultiStore/StorefrontInstances.py` & `StorefrontCatalogAssignments.py` — Missing composite database indexes on `(tenant, -is_default, name)` and `(tenant, publish_status)`.  
  *Fix*: Add `models.Index` declarations to model `Meta.indexes`. — fixed: `a367c772`, `96febe46`, `4ce23033` `feat(ecommerce): add composite indexes and migration 0040`

- [x] **M6**: `apps/ecommerce/views/MultiStore/MultiStoreHub.py:31-32` — Redundant `select_related` joins on hub querysets for columns not rendered in the template.  
  *Fix*: Remove unnecessary joins on hub preview lists. — fixed: `0bc437a4` `perf(ecommerce): remove redundant joins on hub preview lists`
