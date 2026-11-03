# Contract — Sub-module 9.20: Multi-Store & Platform Operations (Module 9: eCommerce Management System, `ecommerce`)

- **Sub-module:** 9.20 Multi-Store & Platform Operations · **Module:** 9 eCommerce Management System · **App:** `apps/ecommerce`
- **Date:** 2026-11-03 · **Status:** FROZEN PRE-BUILD CONTRACT · **Phase:** 3.1 Spec
- **App Status:** Extending existing `apps/ecommerce/`. Next incremental migration: `0037_...` (or next available)
- **Package Layout:** `MultiStore/` across `models/`, `forms/`, `views/`, `urls/`, and templates `templates/ecommerce/multi_store/`.

---

## 1. Models & CHOICES Contract

All top-level models inherit from `apps.ecommerce.models._base.TenantNumbered` (`tenant`, `number`, `created_at`, `updated_at`).

### 1.1 `StorefrontInstance` (`apps/ecommerce/models/MultiStore/StorefrontInstances.py`)
- **Table:** `ecommerce_storefront_instance`
- **Number Prefix:** `ESTR` (`ESTR-00001`)
- **CHOICES:**
  - `STORE_TYPE_CHOICES = [('retail_b2c', 'Retail B2C'), ('wholesale_b2b', 'Wholesale B2B'), ('hybrid', 'Hybrid B2B/B2C'), ('brand_boutique', 'Brand Boutique'), ('outlet_clearance', 'Outlet / Clearance')]`
  - `STATUS_CHOICES = [('draft', 'Draft / In Design'), ('active', 'Active / Online'), ('maintenance', 'Maintenance Mode'), ('suspended', 'Suspended'), ('archived', 'Archived')]`
  - `CHECKOUT_MODE_CHOICES = [('standard_multistep', 'Standard Multi-Step'), ('one_page_express', 'One-Page Express'), ('headless_api', 'Headless API Hand-off')]`
  - `SSL_STATUS_CHOICES = [('active_provisioned', 'Active / Auto-Renewing'), ('pending_dns', 'Pending DNS Verification'), ('custom_cert', 'Custom Certificate Uploaded'), ('expired', 'Expired / Error')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `name`: `CharField(max_length=255, help_text="Storefront channel display name")`
  - `code`: `CharField(max_length=50, blank=True, help_text="Unique storefront code/slug")`
  - `store_type`: `CharField(max_length=30, choices=STORE_TYPE_CHOICES, default='retail_b2c')`
  - `brand_name`: `CharField(max_length=150, blank=True, help_text="Brand portfolio name")`
  - `primary_domain`: `CharField(max_length=255, help_text="Canonical domain e.g. shop.acme.com")`
  - `custom_domains`: `TextField(blank=True, help_text="Secondary domains or regional subdomains")`
  - `default_currency`: `ForeignKey('accounting.Currency', on_delete=PROTECT, related_name='storefront_defaults')`
  - `supported_currencies`: `CharField(max_length=255, default='USD,EUR,GBP')`
  - `default_locale`: `CharField(max_length=10, default='en-US')`
  - `supported_locales`: `CharField(max_length=255, default='en-US,es-ES,de-DE,fr-FR')`
  - `root_category`: `ForeignKey('ecommerce.StoreCategory', on_delete=SET_NULL, null=True, blank=True, related_name='storefront_roots')`
  - `default_fulfillment_center`: `ForeignKey('ecommerce.FulfillmentCenter', on_delete=SET_NULL, null=True, blank=True, related_name='storefront_assignments')`
  - `theme_identifier`: `CharField(max_length=100, default='default-slate')`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default='active')`
  - `is_default`: `BooleanField(default=False, help_text="Primary default store for this tenant")`
  - `checkout_mode`: `CharField(max_length=25, choices=CHECKOUT_MODE_CHOICES, default='standard_multistep')`
  - `ssl_certificate_status`: `CharField(max_length=25, choices=SSL_STATUS_CHOICES, default='active_provisioned')`
  - `description`: `TextField(blank=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='ecommerce_estr_tenant_num_uniq')`
  - `Index(fields=['tenant', 'status', 'store_type'], name='idx_estr_ten_stat_type')`
  - `Index(fields=['tenant', 'primary_domain'], name='idx_estr_ten_domain')`

---

### 1.2 `StorefrontCatalogAssignment` (`apps/ecommerce/models/MultiStore/StorefrontCatalogAssignments.py`)
- **Table:** `ecommerce_storefront_catalog_assignment`
- **Number Prefix:** `ESCA` (`ESCA-00001`)
- **CHOICES:**
  - `PUBLISH_STATUS_CHOICES = [('published', 'Published / Live'), ('hidden', 'Hidden from Catalog'), ('coming_soon', 'Coming Soon'), ('discontinued', 'Discontinued in this Store')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `storefront`: `ForeignKey('ecommerce.StorefrontInstance', on_delete=CASCADE, related_name='catalog_assignments')`
  - `product`: `ForeignKey('ecommerce.CatalogProduct', on_delete=CASCADE, related_name='storefront_assignments')`
  - `is_visible`: `BooleanField(default=True)`
  - `is_featured`: `BooleanField(default=False)`
  - `custom_title`: `CharField(max_length=255, blank=True, help_text="Storefront-specific product title override")`
  - `custom_price`: `DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, help_text="Storefront-specific retail price override")`
  - `custom_currency`: `ForeignKey('accounting.Currency', on_delete=SET_NULL, null=True, blank=True, related_name='storefront_custom_prices')`
  - `storefront_badge`: `CharField(max_length=50, blank=True, help_text="Custom badge text, e.g. 'Online Exclusive'")`
  - `sort_order`: `IntegerField(default=0)`
  - `publish_status`: `CharField(max_length=20, choices=PUBLISH_STATUS_CHOICES, default='published')`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='ecommerce_esca_tenant_num_uniq')`
  - `UniqueConstraint(fields=['tenant', 'storefront', 'product'], name='ecommerce_esca_store_prod_uniq')`
  - `Index(fields=['tenant', 'storefront', 'publish_status'], name='idx_esca_ten_store_pub')`
  - `Index(fields=['tenant', 'is_featured'], name='idx_esca_ten_feat')`

---

### 1.3 `PlatformEnvironment` (`apps/ecommerce/models/MultiStore/PlatformEnvironments.py`)
- **Table:** `ecommerce_platform_environment`
- **Number Prefix:** `EENV` (`EENV-00001`)
- **CHOICES:**
  - `ENV_TYPE_CHOICES = [('production', 'Production Live'), ('staging', 'Staging / Pre-Production'), ('sandbox', 'Developer / QA Sandbox'), ('preview', 'Feature Branch Preview'), ('disaster_recovery', 'Disaster Recovery')]`
  - `REGION_CHOICES = [('us-east-1', 'US East (N. Virginia)'), ('us-west-2', 'US West (Oregon)'), ('eu-central-1', 'Europe (Frankfurt)'), ('eu-west-1', 'Europe (Ireland)'), ('ap-southeast-1', 'Asia Pacific (Singapore)'), ('local_cluster', 'Local / On-Premise Cluster')]`
  - `SLOT_CHOICES = [('blue', 'Blue Slot (Active Live)'), ('green', 'Green Slot (Active Live)'), ('single_slot', 'Standard Single Slot')]`
  - `STATUS_CHOICES = [('healthy', 'Healthy / Online'), ('deploying', 'Deployment In Progress'), ('maintenance', 'Maintenance Window'), ('degraded', 'Degraded Performance'), ('decommissioned', 'Decommissioned')]`
  - `RESOURCE_TIER_CHOICES = [('starter', 'Starter (Shared Container)'), ('standard', 'Standard Production'), ('high_performance', 'High Performance (Multi-Node)'), ('enterprise_dedicated', 'Enterprise Dedicated HA')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `name`: `CharField(max_length=255, help_text="Environment name e.g. Production Cluster")`
  - `env_type`: `CharField(max_length=30, choices=ENV_TYPE_CHOICES, default='sandbox')`
  - `storefront`: `ForeignKey('ecommerce.StorefrontInstance', on_delete=SET_NULL, null=True, blank=True, related_name='environments')`
  - `cluster_region`: `CharField(max_length=50, choices=REGION_CHOICES, default='us-east-1')`
  - `base_url`: `URLField(max_length=500, help_text="Canonical URL or preview URL")`
  - `current_active_slot`: `CharField(max_length=20, choices=SLOT_CHOICES, default='single_slot')`
  - `is_sandbox_locked`: `BooleanField(default=False, help_text="Prevents live payment capture and emails")`
  - `status`: `CharField(max_length=25, choices=STATUS_CHOICES, default='healthy')`
  - `resource_tier`: `CharField(max_length=30, choices=RESOURCE_TIER_CHOICES, default='standard')`
  - `last_health_check_at`: `DateTimeField(null=True, blank=True)`
  - `description`: `TextField(blank=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='ecommerce_eenv_tenant_num_uniq')`
  - `Index(fields=['tenant', 'env_type', 'status'], name='idx_eenv_ten_type_stat')`
  - `Index(fields=['tenant', 'current_active_slot'], name='idx_eenv_ten_slot')`

---

### 1.4 `DeploymentPipeline` (`apps/ecommerce/models/MultiStore/DeploymentPipelines.py`)
- **Table:** `ecommerce_deployment_pipeline`
- **Number Prefix:** `EDPL` (`EDPL-00001`)
- **CHOICES:**
  - `STRATEGY_CHOICES = [('blue_green', 'Blue-Green Zero Downtime'), ('canary_shift', 'Canary Traffic Shift'), ('rolling_update', 'Rolling Update'), ('direct_recreate', 'Direct Recreate / In-Place'), ('dry_run', 'Dry Run / Schema Validation Only')]`
  - `TARGET_SLOT_CHOICES = [('blue', 'Blue Slot'), ('green', 'Green Slot'), ('primary', 'Primary Single Slot')]`
  - `STATUS_CHOICES = [('pending', 'Pending Build'), ('building', 'Building & Compiling'), ('staging_preview', 'Staging Preview Ready'), ('awaiting_approval', 'Awaiting Production Approval'), ('promoted_active', 'Promoted / Active Live'), ('rolled_back', 'Rolled Back'), ('failed', 'Deployment Failed')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `environment`: `ForeignKey('ecommerce.PlatformEnvironment', on_delete=CASCADE, related_name='deployment_pipelines')`
  - `release_version`: `CharField(max_length=50, help_text="Release tag or semantic version e.g. v2.4.0")`
  - `git_branch`: `CharField(max_length=100, default='main')`
  - `git_commit_sha`: `CharField(max_length=40, help_text="40-character Git commit hash")`
  - `deployment_strategy`: `CharField(max_length=30, choices=STRATEGY_CHOICES, default='blue_green')`
  - `target_slot`: `CharField(max_length=20, choices=TARGET_SLOT_CHOICES, default='green')`
  - `status`: `CharField(max_length=30, choices=STATUS_CHOICES, default='pending')`
  - `preview_endpoint_url`: `URLField(max_length=500, blank=True, help_text="Pre-promotion test endpoint URL")`
  - `traffic_percentage`: `PositiveSmallIntegerField(default=0, help_text="Traffic percentage cutover 0-100%")`
  - `migration_executed`: `BooleanField(default=False)`
  - `build_duration_seconds`: `PositiveIntegerField(null=True, blank=True)`
  - `deployment_notes`: `TextField(blank=True)`
  - `promoted_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name='promoted_deployments')`
  - `promoted_at`: `DateTimeField(null=True, blank=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='ecommerce_edpl_tenant_num_uniq')`
  - `Index(fields=['tenant', 'status', 'deployment_strategy'], name='idx_edpl_ten_stat_strat')`
  - `Index(fields=['tenant', 'environment', 'created_at'], name='idx_edpl_ten_env_date')`

---

## 2. Forms Contract (`apps/ecommerce/forms/MultiStore/`)

All ModelForms inherit from standard Django `forms.ModelForm` and exclude `tenant`, `number`, `created_at`, `updated_at`, plus workflow-controlled fields.

### 2.1 `StorefrontInstanceForm` (`StorefrontInstances.py`)
- **Model:** `StorefrontInstance`
- **Fields:** `['name', 'code', 'store_type', 'brand_name', 'primary_domain', 'custom_domains', 'default_currency', 'supported_currencies', 'default_locale', 'supported_locales', 'root_category', 'default_fulfillment_center', 'theme_identifier', 'status', 'is_default', 'checkout_mode', 'ssl_certificate_status', 'description']`
- **Excludes:** `tenant`, `number`, `created_at`, `updated_at`

### 2.2 `StorefrontCatalogAssignmentForm` (`StorefrontCatalogAssignments.py`)
- **Model:** `StorefrontCatalogAssignment`
- **Fields:** `['storefront', 'product', 'is_visible', 'is_featured', 'custom_title', 'custom_price', 'custom_currency', 'storefront_badge', 'sort_order', 'publish_status']`
- **Excludes:** `tenant`, `number`, `created_at`, `updated_at`

### 2.3 `PlatformEnvironmentForm` (`PlatformEnvironments.py`)
- **Model:** `PlatformEnvironment`
- **Fields:** `['name', 'env_type', 'storefront', 'cluster_region', 'base_url', 'current_active_slot', 'is_sandbox_locked', 'status', 'resource_tier', 'description']`
- **Excludes:** `tenant`, `number`, `created_at`, `updated_at`, `last_health_check_at`

### 2.4 `DeploymentPipelineForm` (`DeploymentPipelines.py`)
- **Model:** `DeploymentPipeline`
- **Fields:** `['environment', 'release_version', 'git_branch', 'git_commit_sha', 'deployment_strategy', 'target_slot', 'status', 'preview_endpoint_url', 'traffic_percentage', 'migration_executed', 'build_duration_seconds', 'deployment_notes']`
- **Excludes:** `tenant`, `number`, `created_at`, `updated_at`, `promoted_by`, `promoted_at`

---

## 3. URLs Contract (`apps/ecommerce/urls/MultiStore/`)

All URL routes are nested under `apps.ecommerce` namespace (`app_name = 'ecommerce'`).

### 3.1 Overview Hub
- `path('multi-store/', views.multi_store_hub, name='multi_store_hub')`

### 3.2 `StorefrontInstance` (`StorefrontInstances.py`)
- `path('multi-store/storefronts/', views.storefront_instance_list, name='storefront_instance_list')`
- `path('multi-store/storefronts/create/', views.storefront_instance_create, name='storefront_instance_create')`
- `path('multi-store/storefronts/<int:pk>/', views.storefront_instance_detail, name='storefront_instance_detail')`
- `path('multi-store/storefronts/<int:pk>/edit/', views.storefront_instance_edit, name='storefront_instance_edit')`
- `path('multi-store/storefronts/<int:pk>/delete/', views.storefront_instance_delete, name='storefront_instance_delete')`
- `path('multi-store/storefronts/<int:pk>/toggle-status/', views.storefront_toggle_status, name='storefront_toggle_status')`

### 3.3 `StorefrontCatalogAssignment` (`StorefrontCatalogAssignments.py`)
- `path('multi-store/catalog-assignments/', views.storefront_catalog_assignment_list, name='storefront_catalog_assignment_list')`
- `path('multi-store/catalog-assignments/create/', views.storefront_catalog_assignment_create, name='storefront_catalog_assignment_create')`
- `path('multi-store/catalog-assignments/<int:pk>/', views.storefront_catalog_assignment_detail, name='storefront_catalog_assignment_detail')`
- `path('multi-store/catalog-assignments/<int:pk>/edit/', views.storefront_catalog_assignment_edit, name='storefront_catalog_assignment_edit')`
- `path('multi-store/catalog-assignments/<int:pk>/delete/', views.storefront_catalog_assignment_delete, name='storefront_catalog_assignment_delete')`

### 3.4 `PlatformEnvironment` (`PlatformEnvironments.py`)
- `path('multi-store/environments/', views.platform_environment_list, name='platform_environment_list')`
- `path('multi-store/environments/create/', views.platform_environment_create, name='platform_environment_create')`
- `path('multi-store/environments/<int:pk>/', views.platform_environment_detail, name='platform_environment_detail')`
- `path('multi-store/environments/<int:pk>/edit/', views.platform_environment_edit, name='platform_environment_edit')`
- `path('multi-store/environments/<int:pk>/delete/', views.platform_environment_delete, name='platform_environment_delete')`

### 3.5 `DeploymentPipeline` (`DeploymentPipelines.py`)
- `path('multi-store/deployments/', views.deployment_pipeline_list, name='deployment_pipeline_list')`
- `path('multi-store/deployments/create/', views.deployment_pipeline_create, name='deployment_pipeline_create')`
- `path('multi-store/deployments/<int:pk>/', views.deployment_pipeline_detail, name='deployment_pipeline_detail')`
- `path('multi-store/deployments/<int:pk>/edit/', views.deployment_pipeline_edit, name='deployment_pipeline_edit')`
- `path('multi-store/deployments/<int:pk>/delete/', views.deployment_pipeline_delete, name='deployment_pipeline_delete')`
- `path('multi-store/deployments/<int:pk>/promote/', views.deployment_promote, name='deployment_promote')`
- `path('multi-store/deployments/<int:pk>/rollback/', views.deployment_rollback, name='deployment_rollback')`

---

## 4. View Context Keys Contract (Pinned)

Every view passes explicit context keys matching this exact table.

| View Function | Template | Context Keys |
|---|---|---|
| `multi_store_hub` | `ecommerce/multi_store/multi_store_hub.html` | `total_storefronts`, `active_storefronts`, `total_environments`, `production_environments`, `storefronts`, `environments`, `recent_pipelines` |
| `storefront_instance_list` | `ecommerce/multi_store/storefront_instance/list.html` | `storefront_instances`, `page_obj`, `paginator`, `is_paginated`, `search_query`, `store_type_filter`, `status_filter`, `store_type_choices`, `status_choices` |
| `storefront_instance_detail` | `ecommerce/multi_store/storefront_instance/detail.html` | `storefront`, `catalog_assignments`, `environments`, `recent_deployments` |
| `storefront_instance_create` | `ecommerce/multi_store/storefront_instance/form.html` | `form`, `storefront` (`None`), `is_edit` (`False`) |
| `storefront_instance_edit` | `ecommerce/multi_store/storefront_instance/form.html` | `form`, `storefront` (`obj`), `is_edit` (`True`) |
| `storefront_catalog_assignment_list` | `ecommerce/multi_store/storefront_catalog_assignment/list.html` | `catalog_assignments`, `page_obj`, `paginator`, `is_paginated`, `search_query`, `storefront_filter`, `publish_status_filter`, `publish_status_choices`, `storefronts` |
| `storefront_catalog_assignment_detail` | `ecommerce/multi_store/storefront_catalog_assignment/detail.html` | `assignment` |
| `storefront_catalog_assignment_create` | `ecommerce/multi_store/storefront_catalog_assignment/form.html` | `form`, `assignment` (`None`), `is_edit` (`False`) |
| `storefront_catalog_assignment_edit` | `ecommerce/multi_store/storefront_catalog_assignment/form.html` | `form`, `assignment` (`obj`), `is_edit` (`True`) |
| `platform_environment_list` | `ecommerce/multi_store/platform_environment/list.html` | `platform_environments`, `page_obj`, `paginator`, `is_paginated`, `search_query`, `env_type_filter`, `status_filter`, `env_type_choices`, `status_choices`, `storefronts` |
| `platform_environment_detail` | `ecommerce/multi_store/platform_environment/detail.html` | `environment`, `pipelines` |
| `platform_environment_create` | `ecommerce/multi_store/platform_environment/form.html` | `form`, `environment` (`None`), `is_edit` (`False`) |
| `platform_environment_edit` | `ecommerce/multi_store/platform_environment/form.html` | `form`, `environment` (`obj`), `is_edit` (`True`) |
| `deployment_pipeline_list` | `ecommerce/multi_store/deployment_pipeline/list.html` | `deployment_pipelines`, `page_obj`, `paginator`, `is_paginated`, `search_query`, `environment_filter`, `status_filter`, `strategy_filter`, `status_choices`, `strategy_choices`, `environments` |
| `deployment_pipeline_detail` | `ecommerce/multi_store/deployment_pipeline/detail.html` | `pipeline` |
| `deployment_pipeline_create` | `ecommerce/multi_store/deployment_pipeline/form.html` | `form`, `pipeline` (`None`), `is_edit` (`False`) |
| `deployment_pipeline_edit` | `ecommerce/multi_store/deployment_pipeline/form.html` | `form`, `pipeline` (`obj`), `is_edit` (`True`) |

---

## 5. Navigation Contract (`LIVE_LINKS["9.20"]`)

In `apps/core/navigation.py`:

```python
    "9.20": {
        "Multi-Store & Multi-Brand Management": "ecommerce:storefront_instance_list",
        "Deployment & DevOps (CI/CD)": "ecommerce:deployment_pipeline_list",
        # Extra live leaves
        "Multi-Store Operations Hub": "ecommerce:multi_store_hub",
        "Storefronts": "ecommerce:storefront_instance_list",
        "Catalog Assignments": "ecommerce:storefront_catalog_assignment_list",
        "Platform Environments": "ecommerce:platform_environment_list",
        "CI/CD Pipelines": "ecommerce:deployment_pipeline_list",
    },
```
