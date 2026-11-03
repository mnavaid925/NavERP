# Research — Sub-module 9.20: Multi-Store & Platform Operations (Module 9 — eCommerce Management System, `ecommerce`)

- **Sub-module:** 9.20 Multi-Store & Platform Operations
- **Module:** 9 eCommerce Management System
- **Target app:** `apps/ecommerce` (extending the existing app created in 9.1 and extended through 9.18)
- **Research date:** 2026-11-03
- **Phase:** 1 Research only
- **Output file:** `.claude/tasks/research-ecommerce-9.20.md`

---

## 1. Repo State Checked First

### 1.1 Navigation & App Tree State
- **`apps/core/navigation.py` status:**
  - `"9.1"` is live: Product Catalog Management (`EPRD`, `PVR`, `ECAT`, `PRL`)
  - `"9.2"` is live: Inventory & Stock Management (`EFC`, `EAL`, `EBK`, `ESYN`)
  - `"9.3"` is live: Pricing & Promotion Engine (`EDPR`, `ECPN`, `EFLS`, `ECPM`)
  - `"9.4"` is live: Shopping Cart & Checkout (`ECRT`, `ECKS`, `ESHP`, `EPMC`)
  - `"9.5"` is live: Order Management System (`EORD`, `EFUL`, `ERMA`, `EORT`)
  - `"9.6"` is live: Customer Account & Profile (`ECAP`, `ECAD`, `EWSL`, `ECPR`)
  - `"9.7"` is live: Search & Product Discovery (`ESYM`, `ESFC`, `ESMR`, `ESQL`)
  - `"9.8"` is live: Personalization & Recommendation Engine (`EREC`, `EUSR`, `EACF`, `ECST`)
  - `"9.9"` is live: Content Management System (`ECMP`, `EBLP`, `EBNR`, `ENAV`)
  - `"9.10"` is live: Marketing & Campaign Management (`EMCP`, `ECPN`, `EABT`, `EADF`)
  - `"9.11"` is live: Marketplace & Multi-Vendor (`EVND`, `EVPL`, `EVST`, `EVCO`)
  - `"9.12"` is live: Subscription & Recurring Commerce (`ESBP`, `ECSB`, `ESBO`, `ESBD`)
  - `"9.13"` is live: Reviews & User-Generated Content (`EPRV`, `EQNA`, `EUGC`, `ERVR`)
  - `"9.14"` is live: Customer Service & Support (`ECST`, `ELCS`, `ESKB`, `ESLA`)
  - `"9.15"` is live: Analytics & Business Intelligence (`EATT`, `ECMT`, `EPMM`, `ECKM`)
  - `"9.16"` is live: Mobile Commerce (`EMAC`, `EMDR`, `EMPC`, `EMLR`)
  - `"9.17"` is live: B2B & Wholesale Commerce (`EBCA`, `EBCU`, `EBQR`, `EBQT`)
  - `"9.18"` is live: Fraud & Risk Management (`EFRR`, `ETRA`, `ECBD`, `EASA`)
  - `"9.19"`: Integration & API Ecosystem (Researched in `research-ecommerce-9.19.md`)
  - `"9.20"`: Target sub-module (Multi-Store & Platform Operations) — final sub-module in Module 9.

### 1.2 Sibling Models Available to FK (Verified in `apps/ecommerce/models/`)
- `CatalogProduct` (`apps/ecommerce/models/ProductCatalog/CatalogProducts.py` — verified)
- `StoreCategory` (`apps/ecommerce/models/ProductCatalog/StoreCategories.py` — verified)
- `FulfillmentCenter` (`apps/ecommerce/models/InventoryStock/FulfillmentCenters.py` — verified)
- `CmsPage` (`apps/ecommerce/models/ContentManagement/CmsPages.py` — verified)
- `CustomerAccountProfile` (`apps/ecommerce/models/CustomerProfile/CustomerAccountProfiles.py` — verified)
- `EcommerceOrder` (`apps/ecommerce/models/OrderManagement/EcommerceOrders.py` — verified)

### 1.3 Spine Entities Verified to Exist (Grep Evidence)
- `apps/core/models/`:
  - `Tenant`: verified (`apps/core/models/Tenant.py`)
  - `Party`: verified (`apps/core/models/Party.py`)
  - `User`: verified via `django.conf.settings.AUTH_USER_MODEL`
  - `AuditLog`: verified (`apps/core/models/AuditLog.py`)
- `apps/accounting/models/`:
  - `Currency`: verified (`apps/accounting/models/GeneralLedger/Currencies.py`)

### 1.4 Architectural Boundary Invariants (L28, L29, L36, L37)
1. **Multi-Tenancy & Data Isolation (L28, L36)**:
   - All Multi-Store & Platform Operations models inherit from `TenantNumbered` (`apps/ecommerce/models/_base.py`) with strict `tenant` (`core.Tenant`) isolation.
   - Storefront instances, catalog assignments, platform environments, and deployment pipelines are strictly scoped to `tenant=request.tenant`.
2. **Centralized Master Catalog with Store Scoping (L28)**:
   - Single source of truth: master products live in `ecommerce.CatalogProduct`. 9.20 introduces `StorefrontCatalogAssignment` to govern visibility, custom storefront titles, and storefront-specific prices without duplicating inventory or core SKU master data.
3. **Core Spine & Currency Ownership (L29)**:
   - Multi-currency storefront configuration directly links to Module 2 `accounting.Currency`.
4. **DevOps & Blue-Green Integrity**:
   - Environment definitions provide sandbox isolation flags to prevent sandbox test orders from triggering production inventory allocations or real financial transactions.
   - Deployment pipelines track build versions, commit SHAs, deployment strategies (blue-green cutovers vs rolling), and validation audit trails.

---

## 2. Leaders Surveyed (with Source Links)

1. **BigCommerce (Multi-Storefront / MSF & Channels API)**
   - *Benchmark SaaS architecture for managing multiple storefronts and brands from a single backend control panel.*
   - Sources: [BigCommerce Multi-Storefront Guide](https://developer.bigcommerce.com/docs/storefront/multi-storefront), [BigCommerce Channels & Catalogs Documentation](https://support.bigcommerce.com/s/article/Multi-Storefront).
   - Key capabilities: Channel-specific storefront mapping, independent category trees per channel, per-channel price lists, shared vs channel-assigned product catalogs, centralized order fulfillment and analytics.

2. **Adobe Commerce / Magento Commerce (Website -> Store -> Store View Hierarchy)**
   - *Industry-standard enterprise multi-store hierarchical architecture.*
   - Sources: [Adobe Commerce Store Hierarchy Documentation](https://experienceleague.adobe.com/en/docs/commerce-admin/start/setup/stores-all-stores), [Adobe Cloud Deployment Strategies](https://experienceleague.adobe.com/en/docs/commerce-operations/deployment-guide/introduction).
   - Key capabilities: 4-tier hierarchy (`Global -> Website -> Store -> Store View`), website-level base currencies and payment methods, store-level root category assignment, store-view level translation and localized presentation.

3. **SAP Commerce Cloud (CCV2 Cloud Portal & Blue-Green Deployments)**
   - *Enterprise standard for cloud commerce operations, environment management, and zero-downtime releases.*
   - Sources: [SAP Commerce Cloud Blue-Green Deployments](https://help.sap.com/docs/SAP_COMMERCE_CLOUD_PUBLIC_CLOUD/b2f40052823d4eac8955eab0b73c9b74/846ca153591f4229bca0f00f074a3f5f.html), [SAP CCV2 Cloud Portal Guide](https://help.sap.com/docs/SAP_COMMERCE_CLOUD_PUBLIC_CLOUD/b2f40052823d4eac8955eab0b73c9b74/8c79c8369363401fa9157db4001d236f.html).
   - Key capabilities: Cloud Portal environment management (Development, Staging, Production), automated build creation from Git branches, dual-slot Blue-Green deployment with preview endpoints, traffic shifting, and formal accept/reject deployment decisions.

4. **Salesforce B2C Commerce Cloud (Multi-Site, Code Versions & Staging Replication)**
   - *High-scale multi-brand commerce with strict staging-to-production replication workflows.*
   - Sources: [Salesforce B2C Commerce Multi-Site Architecture](https://developer.salesforce.com/docs/commerce/b2c-commerce/guide/b2c-architecture.html), [Salesforce Code Replication & Sandboxes](https://help.salesforce.com/s/articleView?id=sf.b2c_replication.htm).
   - Key capabilities: Multi-site cartridge management, discrete code versions (`v_2026_release_1`), On-Demand Sandboxes (ODS) for isolated development, multi-stage code replication (transfer, activate, rollback/revert).

5. **Shopware 6 (Sales Channels, Virtual Domains & Staging)**
   - *Modern European open-source eCommerce platform built around Sales Channel touchpoints.*
   - Sources: [Shopware 6 Sales Channels Documentation](https://docs.shopware.com/en/shopware-6-en/configuration/sales-channels), [Shopware 6 Staging Setup](https://docs.shopware.com/en/shopware-6-en/system/staging).
   - Key capabilities: Headless and HTML sales channels, virtual domain mapping (subdomains and subpaths), distinct default languages and currencies, staging mode flags to disable production external services.

6. **Shopify Plus (Organization Admin, Expansion Stores & Sandboxes)**
   - *Global enterprise multi-brand SaaS architecture.*
   - Sources: [Shopify Plus Organization Admin](https://help.shopify.com/en/manual/organization-management), [Shopify Development Stores](https://help.shopify.com/en/manual/shopify-plus/expansion-stores).
   - Key capabilities: Organization-level oversight across up to 50 expansion stores, centralized user roles and store provisioning, sandbox development stores with transfer capabilities, theme version control.

7. **Commerce Layer / Fabric (Composable Multi-Brand Channel Orchestration)**
   - *MACH-compliant headless commerce engine for multi-market and multi-brand deployment.*
   - Sources: [Commerce Layer Multi-Market Architecture](https://docs.commercelayer.io/core/markets), [Fabric Platform Deployment](https://fabric.inc/platform).
   - Key capabilities: Multi-market scoping (linking markets to specific price lists, inventory sources, and languages), preview deployment links, zero-downtime microservice configuration updates.

---

## 3. Feature Catalog (Sub-module 9.20 only)

### 3.1 Multi-Store & Multi-Brand Management
- **Multi-Brand Storefront Channel Registry** — Master registry of distinct storefront channels, brand portals, and regional stores under a single tenant account. · seen in: *BigCommerce MSF, Shopify Plus, Shopware 6* · priority: `table-stakes` · spine: new table `StorefrontInstance` · `buildable now`
- **Domain & Virtual URL Mapping** — Binding primary production domains, regional subdomains (`us.brand.com`, `eu.brand.com`), and preview subpaths to specific storefronts with SSL provisioning status tracking. · seen in: *BigCommerce, Shopware 6, Adobe Commerce* · priority: `table-stakes` · spine: `StorefrontInstance` · `buildable now`
- **Scoped Currencies & Localization** — Assigning default and supported transactional currencies (FK `accounting.Currency`), default language locales, and country restrictions per storefront instance. · seen in: *Adobe Commerce, BigCommerce, Shopware 6* · priority: `table-stakes` · spine: `StorefrontInstance` + reuses `accounting.Currency` · `buildable now`
- **Root Category & Navigation Binding** — Binding storefront instances to dedicated root category trees (`ecommerce.StoreCategory`), enabling unique menu hierarchies and product departments per brand. · seen in: *Adobe Commerce, BigCommerce MSF* · priority: `table-stakes` · spine: `StorefrontInstance` + reuses `ecommerce.StoreCategory` · `buildable now`
- **Selective Catalog Assignment & Publishing** — Granular mapping table (`StorefrontCatalogAssignment`) governing which master products appear on which storefronts, with custom storefront titles, storefront pricing overrides, and featured product flags. · seen in: *BigCommerce MSF, Adobe Commerce* · priority: `table-stakes` · spine: new table `StorefrontCatalogAssignment` + reuses `ecommerce.CatalogProduct` · `buildable now`
- **Default Warehouse & Fulfillment Node Scoping** — Associating storefront instances with primary fulfillment centers (`ecommerce.FulfillmentCenter`) for regional delivery routing. · seen in: *BigCommerce, Shopware 6* · priority: `common` · spine: `StorefrontInstance` + reuses `ecommerce.FulfillmentCenter` · `buildable now`

### 3.2 Deployment & DevOps (CI/CD)
- **Multi-Tier Environment Registry** — Managing isolated runtime tiers (`production`, `staging`, `sandbox`, `preview`, `disaster_recovery`) with region clustering, base URLs, and resource tiers. · seen in: *SAP Commerce Cloud CCV2, Salesforce B2C Commerce, Shopify Plus* · priority: `table-stakes` · spine: new table `PlatformEnvironment` · `buildable now`
- **Sandbox Environment Isolation Safeguards** — Built-in security locks (`is_sandbox_locked`) that automatically prevent sandbox environments from sending live outbound emails, charging real credit cards, or mutating production inventory. · seen in: *Shopware 6, Salesforce B2C Commerce* · priority: `table-stakes` · spine: `PlatformEnvironment` · `buildable now`
- **CI/CD Deployment Pipelines & Releases** — Structured deployment pipeline tracking Git branches, commit SHAs, release version tags (`v2.4.0`), target environments, and deployment status lifecycle (`pending`, `building`, `staging_preview`, `awaiting_approval`, `promoted_active`, `rollback`, `failed`). · seen in: *SAP CCV2, Vercel, Salesforce Commerce* · priority: `table-stakes` · spine: new table `DeploymentPipeline` · `buildable now`
- **Blue-Green Deployment Cutover & Traffic Shifting** — Zero-downtime deployment orchestration managing dual slots (`blue` vs `green`), preview endpoint generation for pre-release acceptance testing, and configurable traffic percentage cutover (0% to 100%). · seen in: *SAP CCV2 Blue-Green, AWS ECS/Route53* · priority: `differentiator` · spine: `DeploymentPipeline` + `PlatformEnvironment` · `buildable now`
- **One-Click Rollback & Revert Workflow** — Instant reverting to previous known-good deployment versions if regression is observed on the active traffic slot. · seen in: *SAP CCV2, Salesforce Commerce, Vercel* · priority: `table-stakes` · spine: `DeploymentPipeline` · `buildable now`
- **Database Migration & Validation Audit** — Recording whether database schema migrations were executed during the deployment pipeline run, logging build duration, and tracking approving user identity via `core.AuditLog`. · seen in: *SAP CCV2 Cloud Portal* · priority: `table-stakes` · spine: `DeploymentPipeline` + reuses `core.AuditLog` · `buildable now`

---

## 4. Recommended Build Scope (This Pass — 4 Models)

All 4 models inherit from `TenantNumbered` (`apps/ecommerce/models/_base.py`) with strict `tenant` (`core.Tenant`) isolation.

1. **`StorefrontInstance`** [Prefix: `ESTR-`] (`apps/ecommerce/models/MultiStore/StorefrontInstances.py`)
   - **Purpose**: Authoritative Multi-Store & Multi-Brand Storefront Channel model representing independent storefronts, brand boutiques, B2B wholesale portals, and regional digital presences with custom domains, scoped currencies, and root categories.
   - **Fields**:
     - `tenant` (`core.Tenant`, CASCADE)
     - `name`: CharField(max_length=255)
     - `code`: CharField(max_length=50, blank=True)
     - `store_type`: CharField(max_length=30, choices=[("retail_b2c", "Retail B2C"), ("wholesale_b2b", "Wholesale B2B"), ("hybrid", "Hybrid B2B/B2C"), ("brand_boutique", "Brand Boutique"), ("outlet_clearance", "Outlet / Clearance")], default="retail_b2c")
     - `brand_name`: CharField(max_length=150, blank=True)
     - `primary_domain`: CharField(max_length=255)
     - `custom_domains`: TextField(blank=True, help_text="Comma-separated or newline-separated secondary domains and subdomains")
     - `default_currency`: ForeignKey(`accounting.Currency`, PROTECT, related_name="storefront_defaults")
     - `supported_currencies`: CharField(max_length=255, default="USD,EUR,GBP")
     - `default_locale`: CharField(max_length=10, default="en-US")
     - `supported_locales`: CharField(max_length=255, default="en-US,es-ES,de-DE,fr-FR")
     - `root_category`: ForeignKey(`ecommerce.StoreCategory`, SET_NULL, null=True, blank=True, related_name="storefront_roots")
     - `default_fulfillment_center`: ForeignKey(`ecommerce.FulfillmentCenter`, SET_NULL, null=True, blank=True, related_name="storefront_assignments")
     - `theme_identifier`: CharField(max_length=100, default="default-slate")
     - `status`: CharField(max_length=20, choices=[("draft", "Draft / In Design"), ("active", "Active / Online"), ("maintenance", "Maintenance Mode"), ("suspended", "Suspended"), ("archived", "Archived")], default="active")
     - `is_default`: BooleanField(default=False)
     - `checkout_mode`: CharField(max_length=25, choices=[("standard_multistep", "Standard Multi-Step"), ("one_page_express", "One-Page Express"), ("headless_api", "Headless API Hand-off")], default="standard_multistep")
     - `ssl_certificate_status`: CharField(max_length=25, choices=[("active_provisioned", "Active / Auto-Renewing"), ("pending_dns", "Pending DNS Verification"), ("custom_cert", "Custom Certificate Uploaded"), ("expired", "Expired / Error")], default="active_provisioned")
     - `description`: TextField(blank=True)
   - **Form Excludes**: `tenant`, `number`, `created_at`, `updated_at`

2. **`StorefrontCatalogAssignment`** [Prefix: `ESCA-`] (`apps/ecommerce/models/MultiStore/StorefrontCatalogAssignments.py`)
   - **Purpose**: Scoped catalog mapping controlling product assortment, storefront-specific pricing, custom merchandising titles, and storefront feature tags across channels.
   - **Fields**:
     - `tenant` (`core.Tenant`, CASCADE)
     - `storefront`: ForeignKey(`ecommerce.StorefrontInstance`, CASCADE, related_name="catalog_assignments")
     - `product`: ForeignKey(`ecommerce.CatalogProduct`, CASCADE, related_name="storefront_assignments")
     - `is_visible`: BooleanField(default=True)
     - `is_featured`: BooleanField(default=False)
     - `custom_title`: CharField(max_length=255, blank=True, help_text="Storefront-specific product title override")
     - `custom_price`: DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, help_text="Storefront-specific retail price override")
     - `custom_currency`: ForeignKey(`accounting.Currency`, SET_NULL, null=True, blank=True, related_name="storefront_custom_prices")
     - `storefront_badge`: CharField(max_length=50, blank=True, help_text="Custom badge text, e.g. 'Online Exclusive', 'Store Special'")
     - `sort_order`: IntegerField(default=0)
     - `publish_status`: CharField(max_length=20, choices=[("published", "Published / Live"), ("hidden", "Hidden from Catalog"), ("coming_soon", "Coming Soon"), ("discontinued", "Discontinued in this Store")], default="published")
   - **Form Excludes**: `tenant`, `number`, `created_at`, `updated_at`

3. **`PlatformEnvironment`** [Prefix: `EENV-`] (`apps/ecommerce/models/MultiStore/PlatformEnvironments.py`)
   - **Purpose**: Infrastructure instance & runtime tier manager modeling isolated operational tiers (Production, Staging, QA Sandbox, Disaster Recovery) with blue-green active slots and test isolation safeguards.
   - **Fields**:
     - `tenant` (`core.Tenant`, CASCADE)
     - `name`: CharField(max_length=255)
     - `env_type`: CharField(max_length=30, choices=[("production", "Production Live"), ("staging", "Staging / Pre-Production"), ("sandbox", "Developer / QA Sandbox"), ("preview", "Feature Branch Preview"), ("disaster_recovery", "Disaster Recovery")], default="sandbox")
     - `storefront`: ForeignKey(`ecommerce.StorefrontInstance`, SET_NULL, null=True, blank=True, related_name="environments")
     - `cluster_region`: CharField(max_length=50, choices=[("us-east-1", "US East (N. Virginia)"), ("us-west-2", "US West (Oregon)"), ("eu-central-1", "Europe (Frankfurt)"), ("eu-west-1", "Europe (Ireland)"), ("ap-southeast-1", "Asia Pacific (Singapore)"), ("local_cluster", "Local / On-Premise Cluster")], default="us-east-1")
     - `base_url`: URLField(help_text="Canonical web address or preview URL of the environment")
     - `current_active_slot`: CharField(max_length=20, choices=[("blue", "Blue Slot (Active Live)"), ("green", "Green Slot (Active Live)"), ("single_slot", "Standard Single Slot")], default="single_slot")
     - `is_sandbox_locked`: BooleanField(default=False, help_text="Locks environment to prevent live credit card charges, real outbound emails, or inventory decrements")
     - `status`: CharField(max_length=25, choices=[("healthy", "Healthy / Online"), ("deploying", "Deployment In Progress"), ("maintenance", "Maintenance Window"), ("degraded", "Degraded Performance"), ("decommissioned", "Decommissioned")], default="healthy")
     - `resource_tier`: CharField(max_length=30, choices=[("starter", "Starter (Shared Container)"), ("standard", "Standard Production"), ("high_performance", "High Performance (Multi-Node)"), ("enterprise_dedicated", "Enterprise Dedicated HA")], default="standard")
     - `last_health_check_at`: DateTimeField(null=True, blank=True)
     - `description`: TextField(blank=True)
   - **Form Excludes**: `tenant`, `number`, `created_at`, `updated_at`, `last_health_check_at`

4. **`DeploymentPipeline`** [Prefix: `EDPL-`] (`apps/ecommerce/models/MultiStore/DeploymentPipelines.py`)
   - **Purpose**: CI/CD release pipeline, build artifact, blue-green deployment gate, and rollback operation record tracking release versions, commit SHAs, validation test outcomes, and traffic routing.
   - **Fields**:
     - `tenant` (`core.Tenant`, CASCADE)
     - `environment`: ForeignKey(`ecommerce.PlatformEnvironment`, CASCADE, related_name="deployment_pipelines")
     - `release_version`: CharField(max_length=50, help_text="Release tag or semantic version, e.g. v2.4.0")
     - `git_branch`: CharField(max_length=100, default="main")
     - `git_commit_sha`: CharField(max_length=40, help_text="40-character Git commit hash")
     - `deployment_strategy`: CharField(max_length=30, choices=[("blue_green", "Blue-Green Zero Downtime"), ("canary_shift", "Canary Traffic Shift"), ("rolling_update", "Rolling Update"), ("direct_recreate", "Direct Recreate / In-Place"), ("dry_run", "Dry Run / Schema Validation Only")], default="blue_green")
     - `target_slot`: CharField(max_length=20, choices=[("blue", "Blue Slot"), ("green", "Green Slot"), ("primary", "Primary Single Slot")], default="green")
     - `status`: CharField(max_length=30, choices=[("pending", "Pending Build"), ("building", "Building & Compiling"), ("staging_preview", "Staging Preview Ready"), ("awaiting_approval", "Awaiting Production Approval"), ("promoted_active", "Promoted / Active Live"), ("rolled_back", "Rolled Back"), ("failed", "Deployment Failed")], default="pending")
     - `preview_endpoint_url`: URLField(blank=True, help_text="URL to test and validate release before promoting traffic")
     - `traffic_percentage`: IntegerField(default=0, help_text="Percentage of live visitor traffic routed to this release (0 to 100%)")
     - `migration_executed`: BooleanField(default=False, help_text="Indicates whether database schema migrations were applied")
     - `build_duration_seconds`: IntegerField(null=True, blank=True)
     - `deployment_notes`: TextField(blank=True)
     - `promoted_by`: ForeignKey(`settings.AUTH_USER_MODEL`, SET_NULL, null=True, blank=True, related_name="promoted_deployments")
     - `promoted_at`: DateTimeField(null=True, blank=True)
   - **Form Excludes**: `tenant`, `number`, `created_at`, `updated_at`, `promoted_at`, `promoted_by`

---

## 5. Belongs to Sibling Sub-modules (Parked, Not Scoped Here)

- **9.1 Product Catalog Management**: Core `CatalogProduct` and `StoreCategory` models remain in 9.1; 9.20 only manages storefront channel visibility and price overrides.
- **9.4 Shopping Cart & Checkout**: Cart session persistence and checkout form rendering stay in 9.4; 9.20 sets the store's `checkout_mode`.
- **9.9 Content Management System (CMS)**: CMS pages and blog posts belong to 9.9; 9.20 links storefront instances to root menus and themes.
- **9.19 Integration & API Ecosystem**: Third-party ERP sync jobs, PSP webhook ingestion, and headless OAuth API tokens belong to 9.19.

---

## 6. Deferred (Later Passes / Enterprise Infrastructure)

- **Live DNS Provider API Automation** (e.g., Cloudflare / AWS Route53 automated CNAME provisioning) — Domains tracked in Django models; automated DNS record manipulation deferred to cloud automation scripts.
- **Physical Kubernetes Cluster Pod Autoscaling** — Container orchestration metrics and cluster autoscaling deferred to infrastructure DevOps layer.
- **Automated Webdriver E2E Synthetic Monitoring** — End-to-end browser bot testing deferred to external CI/CD runner pipelines.
