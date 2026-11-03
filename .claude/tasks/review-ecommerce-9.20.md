# Review Findings: Sub-module 9.20 Multi-Store & Platform Operations

**BASE**: `bc7ed8659edd38e005b53692bdb51ce0501e18da`  
**HEAD**: Recent HEAD for Sub-module 9.20

---

## 1. code-reviewer Findings

### Verdict
Needs Fixes (2 Critical, 3 Important, 3 Minor)

### Findings
- **[CRITICAL] C1**: `apps/ecommerce/views/MultiStore/*.py` — Forms instantiated without `tenant=request.tenant` in create views (`storefront_instance_create`, `storefront_catalog_assignment_create`, `platform_environment_create`, `deployment_pipeline_create`). Fix: Pass `tenant=request.tenant` to form constructors.
- **[CRITICAL] C2**: `apps/ecommerce/views/MultiStore/StorefrontInstances.py:66-73` — Sliced queryset subquery `environments = storefront.environments.all()[:10]` passed into `filter(environment__in=environments)` triggers MariaDB 10.4 error 1235. Fix: Evaluate slice with `list(...)` or remove unused context var.
- **[IMPORTANT] I1**: `apps/ecommerce/views/MultiStore/StorefrontCatalogAssignments.py:32-34` and `DeploymentPipelines.py:32-34` — Integer foreign key filters (`storefront_filter`, `environment_filter`) lack `.isdigit()` check, raising `ValueError` on non-numeric GET parameters. Fix: Guard with `if param and param.isdigit():`.
- **[IMPORTANT] I2**: `apps/ecommerce/views/MultiStore/DeploymentPipelines.py:161-174` and `StorefrontInstances.py:92-94, 123-125` — Multi-record updates (`deployment_promote` and `is_default` reset) missing `transaction.atomic()`. Fix: Wrap multi-table state mutations in `with transaction.atomic():`.
- **[IMPORTANT] I3**: `apps/ecommerce/views/MultiStore/PlatformEnvironments.py:43, 55` & `templates/ecommerce/multi_store/platform_environment/list.html` — Unused `storefronts` context in `platform_environment_list` without filter logic in view or select in template. Fix: Wire storefront filter in view and template.
- **[MINOR] M1**: `StorefrontCatalogAssignments.py:77-79`, `PlatformEnvironments.py:80-82`, `DeploymentPipelines.py:83-85` — Prepopulation `initial["storefront"] = request.GET.get("storefront")` lacks `.isdigit()` validation. Fix: Guard with `if val and val.isdigit(): initial["storefront"] = int(val)`.
- **[MINOR] M2**: `views/MultiStore/*.py` — `page_number = request.GET.get("page")` lacks default. Fix: Use `request.GET.get("page", 1)`.
- **[MINOR] M3**: `multi_store_hub.html:249`, `deployment_pipeline/list.html:130` — Hardcoded Tailwind color on dot indicator. Fix: Standardize with theme token or emerald utility.

---

## 2. explorer Findings

### Verdict
PASS / CLEAN (0 Critical, 0 Important, 2 Minor)

### Findings
- **[MINOR] M4**: `apps/ecommerce/views/MultiStore/StorefrontInstances.py:70-79` — Unused context variable `recent_deployments` in `storefront_instance_detail`. Fix: Remove or display in template.
- **[MINOR] M5**: `apps/ecommerce/views/MultiStore/PlatformEnvironments.py:43-55` — Unused context variable `storefronts` in `platform_environment_list` (corresponds with I3). Fix: Wire storefront filter in view and list template.

