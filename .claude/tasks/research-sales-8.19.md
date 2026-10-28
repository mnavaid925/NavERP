# Research — Sub-module 8.19: Master Data & Configuration (Module 8 — Sales, `apps/sales`)

- **Sub-module:** 8.19 Master Data & Configuration · **Module:** 8 Sales Management System · **App:** `apps/sales`
- **Base commit:** `d289c460e5e74689d5fee8f2c23c1e9734fefc70` (HEAD at research time)
- **Date:** 2026-10-28 · **Phase:** 1 (research) · **Output:** `.claude/tasks/research-sales-8.19.md` (read-only research agent)
- **Mission:** 8.19 is the **master data, pricing governance, extensible entity modeling, methodology configuration, and regional commercial settings layer** of the Sales Management module. It delivers the final four foundational pillars defined in `NavERP.md` §8.19:
  1. **Product Catalog & Pricing** — SKU management, price books, multi-currency support, regional pricing, per-product list/floor price overrides, and volume tier discount schedules.
  2. **Custom Fields & Objects** — Extensible sales data model, custom sales object definitions, formula fields, relationship lookups, and validation rules.
  3. **Sales Methodology Configuration** — Formal qualification methodologies (MEDDIC, MEDDPICC, BANT, SPIN, Challenger, Command of the Message, Custom) mapped to pipeline stages with mandatory stage-gate qualification checklists and passing score thresholds.
  4. **Localization & Multi-Language** — Regional commercial rules, primary and secondary currency support, date/number formatting, sales tax/VAT display modes (inclusive vs. exclusive), and statutory legal disclaimer templates.

Sub-module 8.19 is the **final sub-module of Module 8 (Sales Management System)**. It completes the sales configuration lifecycle and bridges Sales with Core Master Data (`core.Party`), CRM Catalogs (`crm.Product`, `crm.PriceBook`), Pipeline Engines (`sales.Pipeline`, `sales.PipelineStage`), and Accounting Ledgers (`accounting.Currency`).

---

## 1. Repo state checked first (evidence, not docs)

### 1.1 Module 8 sidebar state (`apps/core/navigation.py`)
Direct check on `apps/core/navigation.py`:
- `LIVE_LINKS` contains `"8.1"` through `"8.18"` (lines 2327–2631).
- Sub-module 8.18 (`Integration & API Hub`) is live with routes:
  - `sales:sales_integration_connector_list`
  - `sales:sales_sync_job_list`
  - `sales:sales_sync_run_list`
  - `sales:sales_integration_overview`
- **Sub-module `"8.19"` is the next (and final) unbuilt sub-module in Module 8.**

### 1.2 Migration & Number Prefix State
- `apps/sales/migrations/` ends at **`0034_alter_salessyncjob_batch_size.py`**.
- Sub-module 8.19 claims migration **`0035_...`**.
- **Prefix Collision Audit across entire repo (`apps/**/models`):**
  - Checked against all active prefixes in `core`, `accounts`, `crm`, `accounting`, `hrm`, `scm`, `inventory`, `production`, `projects`, and `sales`.
  - Prefix audit verification:
    - **`PBE`** (`SalesPriceBookEntry`) — **FREE** (0 collisions across repo)
    - **`SCO`** (`SalesCustomEntityDefinition`) — **FREE** (0 collisions across repo)
    - **`SMD`** (`SalesMethodology`) — **FREE** (0 collisions across repo)
    - **`SRG`** (`SalesRegionalSetting`) — **FREE** (0 collisions across repo)

### 1.3 As-built spine entities 8.19 reuses & FKs against (Verified via grep & import)
| Entity | Model Path | Key Fields & Semantics | URL Names in Repo |
|---|---|---|---|
| `Tenant` | `apps.core.models.Tenant` | Multi-tenant root isolation entity | System root |
| `Party` | `apps.core.models.Party` | Central customer accounts, partner entities, and organizations | `core:party_list`, `core:party_detail` |
| `PriceBook` | `apps.crm.models.SalesForceAutomation.PriceBooks.PriceBook` [`PB-`] | Regional/tier price list catalog. Docstring explicitly notes: *"`PriceBookEntry` is a documented future enhancement, not built here."* 8.19 builds this entry table! | `crm:pricebook_list`, `crm:pricebook_detail` |
| `Product` | `apps.crm.models.SalesForceAutomation.Products.Product` [`PRD-`] | Sales catalog sellable product/service master with SKU, unit price, and cost | `crm:product_list`, `crm:product_detail` |
| `Pipeline` | `apps.sales.models.OpportunityPipeline.Pipelines.Pipeline` [`PIPE-`] | Sales opportunity workflow pipelines with stage definitions | `sales:pipeline_list`, `sales:pipeline_detail` |
| `PipelineStage` | `apps.sales.models.OpportunityPipeline.Pipelines.PipelineStage` | Specific stage steps within a pipeline (code, probability, forecast category) | Nested under Pipeline |
| `Currency` | `apps.accounting.models.GeneralLedger.Currencies.Currency` | Financial currency master (`code`, `name`, `symbol`, `is_active`) | `accounting:currency_list` |
| `Item` | `apps.scm.models.InventoryManagement.Items.Item` | Supply chain item inventory master (optional cross-reference for physical stock) | `scm:item_list` |
| `CPQQuote` | `apps.sales.models.QuoteProposalCPQ.CPQQuote` [`CPQ-`] | Sales quoting engine consuming price book pricing and regional terms | `sales:cpq_quote_list` |
| `CustomerContract` | `apps.sales.models.ContractSubscriptionManagement.CustomerContract` [`CCT-`] | Customer legal contracts governed by regional statutory terms | `sales:customer_contract_list` |

---

## 2. Leaders surveyed (with source links)

1. **Salesforce CRM Platform & Sales Cloud** — Enterprise CRM benchmark for product catalog junction modeling, extensible custom objects, and pipeline qualification.
   - *Source:* `https://www.salesforce.com/products/sales-cloud/`
   - *Key takeaway:* Separation of `Product2` (catalog), `Pricebook2` (tier collection), and `PricebookEntry` (junction holding currency, list price, floor price, and active state); `CustomObject` and `CustomField` metadata engine with formula evaluation and lookup relationships; Sales Path with stage-gate guidance and required qualification fields (MEDDIC/Challenger); Multi-currency and Translation Workbench.
2. **Microsoft Dynamics 365 Sales** — Commercial sales management with Dataverse extensible schema and Business Process Flows.
   - *Source:* `https://learn.microsoft.com/en-us/dynamics365/sales/`
   - *Key takeaway:* Product Catalog hierarchy with Price Lists and Price List Items (supporting currency amount, markup, margin over cost, volume quantity tiers); Dataverse custom tables, custom columns, and Power Fx formulas; Business Process Flow stage gates enforcing mandatory qualification fields before advancing deals.
3. **HubSpot CRM (Sales Hub Enterprise)** — Modern RevOps platform with extensible custom objects and playbook guidance.
   - *Source:* `https://www.hubspot.com/products/sales`
   - *Key takeaway:* Product Library with regional Price Books; Custom Objects & Properties with calculated/formula properties; Deal Stage Requirements mandating completion of properties or Playbook qualification checklists before deal stage progression.
4. **SAP Sales Cloud (CX Sales V2)** — Enterprise CX sales suite integrated with ERP backbones.
   - *Source:* `https://www.sap.com/products/crm/sales-cloud.html`
   - *Key takeaway:* Structured Product Master with Price Lists and discount condition tables; Key User Adaptation Mode defining custom fields and business objects; Activity Advisor and Opportunity Milestones for sales methodologies; Localization profiles governing regional sales tax display and legal disclaimer notices.
5. **Oracle CX Sales (Fusion Cloud Sales)** — Comprehensive enterprise sales platform with advanced metadata modeling and methodology frameworks.
   - *Source:* `https://www.oracle.com/cx/sales/`
   - *Key takeaway:* Application Composer for custom objects, dynamic choice lists, and formula attributes; Native MEDDPICC sales methodology stage-gating and deal assessments; Multi-currency price lists with volume tiering; Statutory localization rules for regional sales operations.
6. **Zoho CRM** — Mid-market to enterprise sales platform with flexible module customization and process governance.
   - *Source:* `https://www.zoho.com/crm/`
   - *Key takeaway:* Products and Price Books with flat, differential, and volume tier pricing; Custom Modules and Custom Fields with formula calculations; Blueprint stage transition rules enforcing entry criteria and mandatory during-transition checklist fields; Multi-currency management.
7. **Pipedrive** — Visual sales CRM with structured product catalogs and pipeline governance.
   - *Source:* `https://www.pipedrive.com/en/products`
   - *Key takeaway:* Product catalog with multi-currency unit prices; Custom fields on deals, products, and organizations; Pipeline stages with deal rotting alerts, stage probability weighting, and required field gating.
8. **SugarCRM / Creatio (Studio & Dynamic Case Management)** — No-code composable CRM with dynamic phase-gate governance.
   - *Source:* `https://www.creatio.com/` and `https://www.sugarcrm.com/`
   - *Key takeaway:* Studio extensibility for custom objects and relationships; Dynamic Case Management stage gates enforcing manager approvals and methodology verification; Regional sales configuration and legal clause management.

---

## 3. Feature catalog (this sub-module only)

### 3.1 Product Catalog & Pricing (SKU management, price books, currency support, regional pricing)
- **Per-Product Price Book Entry Junction (`SalesPriceBookEntry`)** — Concrete junction record linking a Price Book (`crm.PriceBook`) to a Product (`crm.Product` or SKU) defining specific currency, list price, floor price, and active date range. · *seen in:* Salesforce (`PricebookEntry`), Dynamics 365 (`Price List Item`), SAP CX · *priority:* `table-stakes` · *spine:* `crm.PriceBook`, `crm.Product`, `accounting.Currency` via `SalesPriceBookEntry` [`PBE-`] · *buildable now*
- **Floor Price & Minimum Margin Protection** — Explicit floor price field below which sales reps cannot discount without triggering executive approval workflows (protecting profitability). · *seen in:* Salesforce CPQ, Dynamics 365, Oracle CX · *priority:* `table-stakes` · *spine:* `SalesPriceBookEntry.floor_price` · *buildable now*
- **Volume Tier Discount Schedules (`volume_tier_breaks`)** — JSON tier matrix defining quantity break brackets (e.g. 1–9 units = $100, 10–49 units = $90, 50+ units = $80) with support for flat price or percentage discount. · *seen in:* Zoho CRM, Dynamics 365, Salesforce · *priority:* `common` · *spine:* `SalesPriceBookEntry.volume_tier_breaks` · *buildable now*
- **Minimum Order Quantity (MOQ)** — Enforced minimum purchase quantity required for the specified price book entry. · *seen in:* Dynamics 365, SAP Sales Cloud · *priority:* `common` · *spine:* `SalesPriceBookEntry.min_quantity` · *buildable now*
- **Pricing Model Strategy** — Method used to determine line item price (`flat`, `tier_volume`, `tier_graduated`, `markup_cost`). · *seen in:* Dynamics 365, Oracle CX · *priority:* `common` · *spine:* `SalesPriceBookEntry.pricing_model` · *buildable now*
- **Effective Date Range Windowing** — Temporal validity (`valid_from`, `valid_to`) allowing marketing and sales ops to pre-schedule seasonal price book updates without overwriting current rates. · *seen in:* SAP Sales Cloud, Oracle CX, Salesforce · *priority:* `table-stakes` · *spine:* `SalesPriceBookEntry.valid_from`, `valid_to` · *buildable now*
- **Real-Time Currency Exchange Conversion Engine** — Dynamic rate translation between corporate currency and transaction currency. · *seen in:* Salesforce Multi-Currency, Dynamics 365 · *priority:* `common` · *spine:* Reuses `accounting.Currency` and `core.localization_board` · *buildable now*

### 3.2 Custom Fields & Objects (Extensible data model, custom relationships, formula fields)
- **Sales Custom Entity & Object Register (`SalesCustomEntityDefinition`)** — Tenant-scoped registry defining custom sales objects or extending standard sales entities (`Opportunity`, `CPQQuote`, `SalesOrder`, `CustomerContract`, `Party`). · *seen in:* Salesforce (`CustomObject`), HubSpot Custom Objects, Dynamics Dataverse Tables · *priority:* `table-stakes` · *spine:* `SalesCustomEntityDefinition` [`SCO-`] · *buildable now*
- **Extensible Field Types** — Configurable types: `text`, `number`, `currency`, `percent`, `date`, `boolean`, `picklist`, `formula`, and `lookup_relationship`. · *seen in:* Salesforce, HubSpot, Zoho CRM · *priority:* `table-stakes` · *spine:* `SalesCustomEntityDefinition.field_type` · *buildable now*
- **Formula Field Expression Metadata (`formula_expression`)** — Declarative expression string enabling computed sales metrics (e.g., `"{expected_arr} * {commission_rate_pct} / 100"`, `"{unit_price} * {quantity} * (1 - {discount_pct}/100)"`). · *seen in:* Salesforce Formula Fields, Dynamics Power Fx, Zoho Formulas · *priority:* `common` · *spine:* `SalesCustomEntityDefinition.formula_expression` · *buildable now*
- **Relationship Lookup Modeling (`target_model`, `relationship_type`)** — Defining 1:N or master-detail relationships linking custom objects to parent opportunities, accounts, or contracts. · *seen in:* Salesforce, Dataverse, Oracle Application Composer · *priority:* `common` · *spine:* `SalesCustomEntityDefinition.relationship_type` · *buildable now*
- **Declarative Validation Rules (`validation_rule_expression`)** — Configurable expression checks ensuring data integrity before record save (e.g. requiring justification if discount exceeds 20%). · *seen in:* Salesforce Validation Rules, Creatio Studio · *priority:* `common` · *spine:* `SalesCustomEntityDefinition.validation_rule_expression` · *buildable now*
- **Picklist Value Matrix (`picklist_options`)** — Ordered list of permitted string choices for picklist custom fields. · *seen in:* HubSpot Properties, Salesforce Global Value Sets · *priority:* `table-stakes` · *spine:* `SalesCustomEntityDefinition.picklist_options` (JSONField) · *buildable now*

### 3.3 Sales Methodology Configuration (MEDDIC, SPIN, Challenger, stage mapping)
- **Methodology Template Configuration (`SalesMethodology`)** — Pre-configured or custom qualification templates supporting industry standards: `MEDDIC`, `MEDDPICC`, `BANT`, `SPIN`, `Challenger`, `Command of the Message`, `Sandler`, and `Custom`. · *seen in:* Salesforce Sales Path, Oracle CX Sales, HubSpot Playbooks · *priority:* `table-stakes` · *spine:* `SalesMethodology` [`SMD-`] · *buildable now*
- **Pipeline Stage Gate Mapping (`target_stage`)** — Direct linkage between a methodology qualification checklist and a specific `sales.PipelineStage` (e.g. requiring MEDDPICC Economic Buyer verification before advancing from Proposal to Negotiation). · *seen in:* Dynamics 365 BPF Stage Gates, Zoho Blueprint Transitions, Creatio · *priority:* `table-stakes` · *spine:* FK to `sales.PipelineStage` · *buildable now*
- **Structured Qualification Criteria Checklist (`qualification_criteria`)** — JSON schema list of qualification points, each with code, question/criterion label, help guidance, score weight, and mandatory flag. (e.g. for MEDDPICC: Metrics, Economic Buyer, Decision Criteria, Decision Process, Paper Process, Implicate Pain, Champion, Competition). · *seen in:* Oracle CX Sales, Salesforce Sales Path · *priority:* `table-stakes` · *spine:* `SalesMethodology.qualification_criteria` (JSONField) · *buildable now*
- **Mandatory Stage Gate Enforcement (`mandatory_gate_enforcement`)** — Toggle enforcing that all mandatory criteria must be satisfied and verified before the opportunity stage can advance. · *seen in:* Dynamics 365, Creatio DCM, Zoho Blueprint · *priority:* `common` · *spine:* `SalesMethodology.mandatory_gate_enforcement` (BooleanField) · *buildable now*
- **Passing Score Threshold (`min_passing_score`)** — Weighted score hurdle (e.g. minimum 70/100 points) required for deal qualification certification. · *seen in:* Oracle CX Sales Assessments, HubSpot · *priority:* `common` · *spine:* `SalesMethodology.min_passing_score` · *buildable now*
- **Coaching & Enablement Guidelines (`coaching_guidelines`)** — Manager-provided tactical prompts and deal advice displayed to reps while working deals in that stage. · *seen in:* Salesforce Guidance for Success, HubSpot Playbooks · *priority:* `common` · *spine:* `SalesMethodology.coaching_guidelines` · *buildable now*

### 3.4 Localization & Multi-Language (Language packs, regional formats, compliance rule localization)
- **Sales Regional Commercial Settings (`SalesRegionalSetting`)** — Region/territory commercial rules (e.g. North America, EMEA, DACH, UK, APAC, LATAM) encapsulating legal, currency, and presentation preferences. · *seen in:* Salesforce Regional Settings, SAP Sales Cloud, Oracle CX · *priority:* `table-stakes` · *spine:* `SalesRegionalSetting` [`SRG-`] · *buildable now*
- **Currency Configuration (`primary_currency_code`, `supported_currencies`)** — Default transactional currency and allowed secondary pricing currencies for the sales region. · *seen in:* Salesforce Multi-Currency, Dynamics 365 · *priority:* `table-stakes` · *spine:* Reuses `accounting.Currency` codes via `SalesRegionalSetting` · *buildable now*
- **Tax / VAT Presentation Mode (`tax_display_mode`)** — Commercial convention: `tax_exclusive` (typical in US/Canada B2B) vs. `tax_inclusive` (mandated in EU/UK/Australia consumer and SME trade). · *seen in:* SAP Sales Cloud, NetSuite, Zoho CRM · *priority:* `table-stakes` · *spine:* `SalesRegionalSetting.tax_display_mode` · *buildable now*
- **Regional Formatting (`date_format`, `number_format`)** — Locale presentation standards for sales documents (e.g., `YYYY-MM-DD` vs `MM/DD/YYYY` vs `DD/MM/YYYY`; decimal comma vs point). · *seen in:* Dynamics 365, Salesforce · *priority:* `table-stakes` · *spine:* `SalesRegionalSetting.date_format`, `number_format` · *buildable now*
- **Standard Quote Terms & Legal Disclaimers (`default_quote_terms`, `legal_disclaimer`)** — Default localized contractual clauses, payment stipulations, and mandatory statutory notices (e.g., GDPR data notice, German Impressum/commercial register lines, cooling-off rights). · *seen in:* SAP CX, Oracle CX, SugarCRM · *priority:* `common` · *spine:* `SalesRegionalSetting.default_quote_terms`, `legal_disclaimer` · *buildable now*
- **Statutory Cooling-Off Period (`cooling_off_days`)** — Regional mandatory statutory period (e.g. 14 days in EU consumer/commercial protection laws) recorded for contract compliance. · *seen in:* SAP Sales Cloud, Salesforce Regional Compliance · *priority:* `common` · *spine:* `SalesRegionalSetting.cooling_off_days` · *buildable now*

### 3.5 Beyond the bullets
- **Price Book Entry Cloner / Bulk Adjuster** — Ability to duplicate a price book entry into another currency or price book with a percentage margin adjustment. · *seen in:* Salesforce Price Book Utilities, Dynamics 365 · *priority:* `common` · *spine:* Model method / view action · *buildable now*
- **Methodology Audit & Deal Health Score** — Read-only computed qualification score badge (0–100%) visible on Opportunity views based on completed methodology checklist points. · *seen in:* Oracle CX Assessment, Salesforce Sales Path · *priority:* `differentiator` · *spine:* Computed helper on `SalesMethodology` · *buildable now*

---

## 4. Recommended build scope (this pass — 1–4 models)

Following the strict 1–4 model unit rule and prefix collision audit, the recommended build scope for Sub-module 8.19 comprises **four focused, tenant-scoped models**:

### Model 1: `SalesPriceBookEntry` [`PBE-`]
- **Purpose:** Concrete per-product price book entries extending `crm.PriceBook` and `crm.Product` with currency, list price, floor price, volume tiers, MOQ, and active date windows.
- **Prefix:** `PBE-` (TenantNumbered, verified FREE across repo)
- **Key Fields:**
  - `tenant` (FK `core.Tenant`)
  - `number` (CharField `PBE-000001`, unique per tenant)
  - `price_book` (FK `crm.PriceBook`, on_delete=CASCADE, related_name="entries")
  - `product` (FK `crm.Product`, on_delete=SET_NULL, null=True, blank=True, related_name="price_book_entries")
  - `sku_code` (CharField, max_length=64, db_index=True)
  - `currency_code` (CharField, max_length=3, default="USD")
  - `list_price` (DecimalField, max_digits=12, decimal_places=2, default=0)
  - `floor_price` (DecimalField, max_digits=12, decimal_places=2, default=0, help_text="Minimum allowed price without executive exception")
  - `pricing_model` (CharField, choices: `flat`, `tier_volume`, `tier_graduated`, `markup_cost`, default="flat")
  - `min_quantity` (PositiveIntegerField, default=1)
  - `volume_tier_breaks` (JSONField, default=list, blank=True, help_text="Tier brackets: [{'min_qty': 10, 'discount_pct': 5}]")
  - `valid_from` (DateField, null=True, blank=True)
  - `valid_to` (DateField, null=True, blank=True)
  - `is_active` (BooleanField, default=True)
- **Spine FKs:** `core.Tenant`, `crm.PriceBook`, `crm.Product`

### Model 2: `SalesCustomEntityDefinition` [`SCO-`]
- **Purpose:** Extensible sales object register and formula field metadata defining custom attributes, relationships, and validation rules for sales domain models.
- **Prefix:** `SCO-` (TenantNumbered, verified FREE across repo)
- **Key Fields:**
  - `tenant` (FK `core.Tenant`)
  - `number` (CharField `SCO-000001`, unique per tenant)
  - `entity_scope` (CharField, choices: `opportunity`, `quote`, `order`, `contract`, `account`, `custom_object`, default="opportunity")
  - `api_name` (SlugField, max_length=60)
  - `display_name` (CharField, max_length=120)
  - `plural_name` (CharField, max_length=140, blank=True)
  - `field_type` (CharField, choices: `text`, `number`, `currency`, `percent`, `date`, `boolean`, `picklist`, `formula`, `lookup_relationship`, default="text")
  - `target_model` (CharField, max_length=120, blank=True, help_text="Target entity for lookups, e.g. 'crm.Opportunity'")
  - `relationship_type` (CharField, choices: `none`, `lookup_1_n`, `master_detail`, default="none")
  - `formula_expression` (TextField, blank=True, help_text="Formula calculation expression")
  - `validation_rule_expression` (TextField, blank=True, help_text="Validation rule check expression")
  - `picklist_options` (JSONField, default=list, blank=True)
  - `is_required` (BooleanField, default=False)
  - `is_searchable` (BooleanField, default=True)
  - `display_order` (PositiveIntegerField, default=1)
  - `is_active` (BooleanField, default=True)
- **Spine FKs:** `core.Tenant`

### Model 3: `SalesMethodology` [`SMD-`]
- **Purpose:** Formal sales qualification and methodology templates (MEDDIC, MEDDPICC, BANT, SPIN, Challenger, Command of the Message, Custom) with target pipeline stage mapping, qualification checklists, score weights, and mandatory gate enforcement.
- **Prefix:** `SMD-` (TenantNumbered, verified FREE across repo)
- **Key Fields:**
  - `tenant` (FK `core.Tenant`)
  - `number` (CharField `SMD-000001`, unique per tenant)
  - `pipeline` (FK `sales.Pipeline`, on_delete=SET_NULL, null=True, blank=True, related_name="methodologies")
  - `target_stage` (FK `sales.PipelineStage`, on_delete=SET_NULL, null=True, blank=True, related_name="methodology_gates")
  - `methodology_type` (CharField, choices: `meddic`, `meddpicc`, `bant`, `spin`, `challenger`, `command_message`, `sandler`, `custom`, default="meddpicc")
  - `name` (CharField, max_length=120)
  - `code` (SlugField, max_length=40)
  - `description` (TextField, blank=True)
  - `qualification_criteria` (JSONField, default=list, help_text="Checklist items: [{'code': 'EB', 'label': 'Economic Buyer Identified', 'required': true, 'weight': 15}]")
  - `min_passing_score` (PositiveIntegerField, default=70, help_text="Minimum qualification score (0-100)")
  - `mandatory_gate_enforcement` (BooleanField, default=True, help_text="Enforce all required criteria before stage advancement")
  - `coaching_guidelines` (TextField, blank=True)
  - `is_active` (BooleanField, default=True)
- **Spine FKs:** `core.Tenant`, `sales.Pipeline`, `sales.PipelineStage`

### Model 4: `SalesRegionalSetting` [`SRG-`]
- **Purpose:** Regional commercial sales configuration, currency conventions, date/number formatting, sales tax/VAT display mode (inclusive vs exclusive), legal terms, and statutory compliance parameters.
- **Prefix:** `SRG-` (TenantNumbered, verified FREE across repo)
- **Key Fields:**
  - `tenant` (FK `core.Tenant`)
  - `number` (CharField `SRG-000001`, unique per tenant)
  - `region_code` (CharField, max_length=10, db_index=True, help_text="e.g. NA, EMEA, APAC, DACH, UK")
  - `region_name` (CharField, max_length=120)
  - `primary_currency_code` (CharField, max_length=3, default="USD")
  - `supported_currencies` (JSONField, default=list, help_text="Allowed currency codes e.g. ['USD', 'EUR', 'GBP']")
  - `date_format` (CharField, choices: `YYYY-MM-DD`, `MM/DD/YYYY`, `DD/MM/YYYY`, `DD.MM.YYYY`, default="YYYY-MM-DD")
  - `number_format` (CharField, choices: `1,234.56`, `1.234,56`, `1 234,56`, default="1,234.56")
  - `tax_display_mode` (CharField, choices: `tax_exclusive`, `tax_inclusive`, default="tax_exclusive")
  - `default_quote_terms` (TextField, blank=True)
  - `legal_disclaimer` (TextField, blank=True)
  - `compliance_framework` (CharField, choices: `standard`, `gdpr_commercial`, `sox_revenue`, `fda_regulated`, `export_controlled`, `local_statutory`, default="standard")
  - `cooling_off_days` (PositiveIntegerField, default=0, help_text="Statutory buyer cancellation period in days")
  - `is_default` (BooleanField, default=False)
  - `is_active` (BooleanField, default=True)
- **Spine FKs:** `core.Tenant`

---

## 5. Belongs to sibling sub-modules (parked, not scoped here)

- **Lead Scoring Rules & Routing** $\rightarrow$ Owned by **8.1 Lead Management** (`LeadScoreRule`, `LeadAssignmentRule`).
- **Pipeline Stage Visual Kanban & Deal Rotting** $\rightarrow$ Owned by **8.2 Opportunity & Pipeline Management** (`Pipeline`, `PipelineStage`, `OpportunityPlacement`).
- **CPQ Quote Line Calculation Engine** $\rightarrow$ Owned by **8.5 Quote & Proposal Management** (`CPQQuote`, `CPQQuoteLine`). 8.19 provides the price book entries and regional settings that 8.5 consumes.
- **Sales Order Fulfillment & Order Holds** $\rightarrow$ Owned by **8.6 Order Management** (`SalesOrderHold`, `OrderSplitShipment`).
- **Territory Alignment & Quota Assignment** $\rightarrow$ Owned by **8.7 Territory & Quota Management** (`SalesTerritory`, `SalesQuota`).
- **Playbook Rich Media & Content Assets** $\rightarrow$ Owned by **8.9 Sales Enablement** (`SalesPlaybook`, `PlaybookSection`).
- **Contract Signature & Obligation Milestones** $\rightarrow$ Owned by **8.15 Contract & Subscription Management** (`CustomerContract`, `ContractObligation`).
- **Automated Workflow Escalations & Alerts** $\rightarrow$ Owned by **8.17 Workflow & Process Automation** (`SalesAssignmentRule`, `SalesAlertTrigger`, `SalesApprovalDecision`).
- **Third-Party CRM / ERP Synchronization Connectors** $\rightarrow$ Owned by **8.18 Integration & API Hub** (`SalesIntegrationConnector`, `SalesSyncJob`, `SalesSyncRun`).

---

## 6. Deferred (later passes / external integrations)

- **Real-time Live FX Rate Feed API Integration** — Automated daily exchange rate retrieval from ECB or OpenExchangeRates. (8.19 stores currency codes and static rates; automated background updates deferred to an external integration adapter).
- **Interactive Visual Dynamic Form Drag-and-Drop Builder** — Full browser-based drag-and-drop layout canvas for custom entities. (8.19 establishes declarative schema, types, formula expressions, and validation rules; canvas UI deferred).
- **AST-Compiled Sandbox Formula Interpreter** — Sandboxed Python or Javascript expression evaluator executing custom formula fields across joined tables. (8.19 stores declarative formula expressions and provides Python token evaluation; heavy compilation deferred).
- **Multilingual PO/MO Translation Pack File Importer** — Upload and auto-extraction of GNU gettext `.po` files for sales UI strings. (8.19 manages regional settings, formats, and commercial disclaimers; full i18n gettext catalog sync is handled by Django core).
