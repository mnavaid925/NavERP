# Contract — Sub-module 10.7: Data Catalog, Lineage & Governance (Module 10: Business Intelligence, `bi`)

- **Sub-module:** 10.7 Data Catalog, Lineage & Governance · **Module:** 10 Business Intelligence · **App:** `apps/bi`
- **Date:** 2026-11-05 · **Status:** FROZEN PRE-BUILD CONTRACT · **Phase:** 3.1 Spec
- **App Status:** Existing app `apps/bi/` (scaffolded in 10.1; extended in 10.2, 10.3, 10.4, 10.5, 10.6). Incremental migration: `0019_...`
- **Package Layout:** `DataCatalog/` across `models/`, `forms/`, `views/`, `urls/`, and templates `templates/bi/data_catalog/`.

---

## 1. Models & CHOICES Contract

All 4 top-level models inherit from `apps.bi.models._base.TenantNumbered` (`tenant`, `number`, `created_at`, `updated_at`).

### 1.1 `CatalogAsset` (`apps/bi/models/DataCatalog/CatalogAssets.py`)
- **Table:** `bi_catalog_asset`
- **Number Prefix:** `BCAT` (`BCAT-00001`)
- **CHOICES:**
  - `DOMAIN_CHOICES = [('finance', 'Finance & Accounting'), ('sales', 'Sales & CRM'), ('supply_chain', 'Supply Chain & Inventory'), ('procurement', 'Procurement & Sourcing'), ('human_resources', 'Human Resources'), ('customer', 'Customer & Marketing'), ('operations', 'Operations & Manufacturing'), ('cross_domain', 'Cross-Domain Enterprise')]`
  - `ASSET_TYPE_CHOICES = [('warehouse_table', 'Warehouse Table / View'), ('semantic_model', 'Semantic Layer Model'), ('golden_record', 'MDM Golden Record'), ('metric', 'Calculated Measure / KPI'), ('report', 'Operational / Regulatory Report'), ('pipeline', 'Ingestion / ETL Pipeline'), ('source_dataset', 'Raw Source Connector Dataset')]`
  - `SENSITIVITY_CHOICES = [('public', 'Public - Unrestricted Access'), ('internal', 'Internal - Standard Organization Access'), ('confidential', 'Confidential - Restricted Business Need'), ('restricted_pii', 'Restricted PII - Personal Data (GDPR/CCPA)'), ('highly_sensitive_pci_phi', 'Highly Sensitive - Financial / Health (PCI/PHI)')]`
  - `TIER_CHOICES = [('tier_1_mission_critical', 'Tier 1 - Mission-Critical Enterprise Data'), ('tier_2_production_core', 'Tier 2 - Production Core Analytics'), ('tier_3_departmental', 'Tier 3 - Departmental / Team Ad-Hoc'), ('tier_4_sandbox', 'Tier 4 - Exploratory / Sandbox')]`
  - `CERTIFICATION_STATUS_CHOICES = [('draft', 'Draft / Unreviewed'), ('under_review', 'Under Stewardship Review'), ('certified', 'Certified Production-Ready'), ('endorsed', 'Peer Endorsed'), ('deprecated', 'Deprecated / Retiring'), ('quarantined', 'Quarantined / Quality Breach')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `name`: `CharField(max_length=255)`
  - `code`: `SlugField(max_length=80)`
  - `domain`: `CharField(max_length=30, choices=DOMAIN_CHOICES, default='cross_domain')`
  - `asset_type`: `CharField(max_length=30, choices=ASSET_TYPE_CHOICES, default='warehouse_table')`
  - `warehouse_table`: `ForeignKey('bi.WarehouseTable', null=True, blank=True, on_delete=models.SET_NULL, related_name='catalog_assets')`
  - `semantic_model`: `ForeignKey('bi.SemanticModel', null=True, blank=True, on_delete=models.SET_NULL, related_name='catalog_assets')`
  - `golden_record`: `ForeignKey('bi.MdmGoldenRecord', null=True, blank=True, on_delete=models.SET_NULL, related_name='catalog_assets')`
  - `business_glossary_term`: `ForeignKey('bi.BusinessGlossaryTerm', null=True, blank=True, on_delete=models.SET_NULL, related_name='catalog_assets')`
  - `data_steward`: `ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='stewarded_catalog_assets')`
  - `owning_org_unit`: `ForeignKey('core.OrgUnit', null=True, blank=True, on_delete=models.SET_NULL, related_name='catalog_assets')`
  - `data_sensitivity`: `CharField(max_length=30, choices=SENSITIVITY_CHOICES, default='internal')`
  - `enterprise_tier`: `CharField(max_length=30, choices=TIER_CHOICES, default='tier_2_production_core')`
  - `certification_status`: `CharField(max_length=30, choices=CERTIFICATION_STATUS_CHOICES, default='draft')`
  - `deprecation_replacement`: `ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='deprecated_assets_replaced')`
  - `schema_columns_json`: `JSONField(default=list, blank=True)`
  - `search_tags_json`: `JSONField(default=list, blank=True)`
  - `view_count`: `PositiveIntegerField(default=0)`
  - `average_rating`: `DecimalField(max_digits=3, decimal_places=2, default=Decimal('0.00'))`
  - `quality_scorecard`: `ForeignKey('bi.DataQualityScorecard', null=True, blank=True, on_delete=models.SET_NULL, related_name='catalog_assets')`
  - `description`: `TextField(blank=True)`
  - `is_active`: `BooleanField(default=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'code'], name='bi_bcat_tenant_code_uniq')`
  - `UniqueConstraint(fields=['tenant', 'number'], name='bi_bcat_tenant_num_uniq')`
  - `Index(fields=['tenant', 'domain'], name='idx_bcat_ten_dom')`
  - `Index(fields=['tenant', 'asset_type'], name='idx_bcat_ten_atype')`
  - `Index(fields=['tenant', 'data_sensitivity'], name='idx_bcat_ten_sens')`
  - `Index(fields=['tenant', 'enterprise_tier'], name='idx_bcat_ten_tier')`
  - `Index(fields=['tenant', 'certification_status'], name='idx_bcat_ten_cert')`
  - `Index(fields=['tenant', 'is_active'], name='idx_bcat_ten_active')`

---

### 1.2 `CatalogLineageEdge` (`apps/bi/models/DataCatalog/CatalogLineageEdges.py`)
- **Table:** `bi_catalog_lineage_edge`
- **Number Prefix:** `BLIN` (`BLIN-00001`)
- **CHOICES:**
  - `LINEAGE_TYPE_CHOICES = [('table_level', 'Table-to-Table Dataset Lineage'), ('column_level', 'Column-to-Column Granular Lineage'), ('pipeline_transformation', 'ETL Pipeline Transformation'), ('semantic_abstraction', 'Semantic Model Logical Derivation'), ('report_consumption', 'BI Report / Dashboard Query')]`
  - `IMPACT_CRITICALITY_CHOICES = [('low', 'Low - Informational / Non-Breaking'), ('medium', 'Medium - Team Reporting Impact'), ('high', 'High - Key Operational Dependency'), ('critical', 'Critical - Regulatory / Financial Lineage Break')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `upstream_asset`: `ForeignKey('bi.CatalogAsset', on_delete=CASCADE, related_name='downstream_edges')`
  - `downstream_asset`: `ForeignKey('bi.CatalogAsset', on_delete=CASCADE, related_name='upstream_edges')`
  - `lineage_type`: `CharField(max_length=30, choices=LINEAGE_TYPE_CHOICES, default='table_level')`
  - `upstream_column`: `CharField(max_length=120, blank=True)`
  - `downstream_column`: `CharField(max_length=120, blank=True)`
  - `transformation_rule`: `TextField(blank=True)`
  - `etl_pipeline`: `ForeignKey('bi.EtlPipeline', null=True, blank=True, on_delete=models.SET_NULL, related_name='catalog_lineage_edges')`
  - `transformation_step`: `ForeignKey('bi.TransformationStep', null=True, blank=True, on_delete=models.SET_NULL, related_name='catalog_lineage_edges')`
  - `impact_criticality`: `CharField(max_length=20, choices=IMPACT_CRITICALITY_CHOICES, default='medium')`
  - `is_automated_extraction`: `BooleanField(default=True)`
  - `last_verified_at`: `DateTimeField(null=True, blank=True)`
  - `notes`: `TextField(blank=True)`
  - `is_active`: `BooleanField(default=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='bi_blin_tenant_num_uniq')`
  - `Index(fields=['tenant', 'upstream_asset'], name='idx_blin_ten_up')`
  - `Index(fields=['tenant', 'downstream_asset'], name='idx_blin_ten_down')`
  - `Index(fields=['tenant', 'lineage_type'], name='idx_blin_ten_type')`
  - `Index(fields=['tenant', 'impact_criticality'], name='idx_blin_ten_crit')`
  - `Index(fields=['tenant', 'is_active'], name='idx_blin_ten_active')`

---

### 1.3 `DataGovernancePolicy` (`apps/bi/models/DataCatalog/DataGovernancePolicies.py`)
- **Table:** `bi_data_governance_policy`
- **Number Prefix:** `BGOV` (`BGOV-00001`)
- **CHOICES:**
  - `POLICY_TYPE_CHOICES = [('regulatory_compliance', 'Regulatory Compliance Mandate'), ('retention_archival', 'Data Retention & Archival Schedule'), ('sensitivity_classification', 'Data Sensitivity & Tagging Policy'), ('data_masking', 'Column Masking & Redaction Rule'), ('acceptable_use', 'Data Sharing & Acceptable Use Policy'), ('sox_financial_control', 'SOX Financial Internal Control')]`
  - `REGULATORY_FRAMEWORK_CHOICES = [('gdpr_eu', 'GDPR - European Privacy Regulation'), ('hipaa_healthcare', 'HIPAA - Health Information Privacy'), ('sox_financial', 'SOX - Sarbanes-Oxley Financial Reporting'), ('pci_dss', 'PCI-DSS - Payment Card Security'), ('ccpa_cpra', 'CCPA/CPRA - California Consumer Privacy'), ('iso_27001', 'ISO 27001 - Security Standards'), ('internal_standard', 'Internal Enterprise Standard')]`
  - `ENFORCEMENT_LEVEL_CHOICES = [('advisory_informational', 'Advisory / Informational Guidelines'), ('audit_warning', 'Audit Warning / Compliance Alert'), ('strict_blocking', 'Strict Blocking / Enforcement Gate'), ('automated_masking', 'Automated Dynamic Column Masking')]`
  - `MASKING_ALGORITHM_CHOICES = [('none', 'No Masking (Plaintext)'), ('full_redaction', 'Full Redaction (***)'), ('partial_mask_email_phone', 'Partial Masking (Email / Phone)'), ('hash_sha256', 'Cryptographic SHA-256 Hash'), ('tokenization', 'Irreversible Tokenization'), ('nullify', 'Nullify / Blank Value')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `name`: `CharField(max_length=180)`
  - `code`: `SlugField(max_length=80)`
  - `policy_type`: `CharField(max_length=30, choices=POLICY_TYPE_CHOICES, default='regulatory_compliance')`
  - `regulatory_framework`: `CharField(max_length=30, choices=REGULATORY_FRAMEWORK_CHOICES, default='gdpr_eu')`
  - `enforcement_level`: `CharField(max_length=30, choices=ENFORCEMENT_LEVEL_CHOICES, default='audit_warning')`
  - `retention_period_days`: `PositiveIntegerField(null=True, blank=True)`
  - `masking_algorithm`: `CharField(max_length=30, choices=MASKING_ALGORITHM_CHOICES, default='none')`
  - `policy_owner`: `ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='owned_governance_policies')`
  - `effective_date`: `DateField()`
  - `expiration_date`: `DateField(null=True, blank=True)`
  - `review_frequency_days`: `PositiveIntegerField(default=365)`
  - `last_reviewed_at`: `DateTimeField(null=True, blank=True)`
  - `compliance_notes`: `TextField(blank=True)`
  - `description`: `TextField(blank=True)`
  - `is_active`: `BooleanField(default=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'code'], name='bi_bgov_tenant_code_uniq')`
  - `UniqueConstraint(fields=['tenant', 'number'], name='bi_bgov_tenant_num_uniq')`
  - `Index(fields=['tenant', 'policy_type'], name='idx_bgov_ten_ptype')`
  - `Index(fields=['tenant', 'regulatory_framework'], name='idx_bgov_ten_rframe')`
  - `Index(fields=['tenant', 'enforcement_level'], name='idx_bgov_ten_enforce')`
  - `Index(fields=['tenant', 'is_active'], name='idx_bgov_ten_active')`

---

### 1.4 `CatalogTrustEndorsement` (`apps/bi/models/DataCatalog/CatalogTrustEndorsements.py`)
- **Table:** `bi_catalog_trust_endorsement`
- **Number Prefix:** `BTRU` (`BTRU-00001`)
- **CHOICES:**
  - `ENDORSEMENT_TYPE_CHOICES = [('formal_certification', 'Formal Data Steward Certification'), ('peer_endorsement', 'Peer Data Practitioner Endorsement'), ('user_rating', 'Community User Review & Rating'), ('deprecation_notice', 'Deprecation Notice & Decommission Warning'), ('steward_attestation', 'Periodic Stewardship Attestation'), ('audit_clearance', 'Internal Audit Compliance Clearance')]`
  - `VERDICT_CHOICES = [('approved_certified', 'Approved & Certified Production-Ready'), ('conditionally_approved', 'Conditionally Approved (Minor Caveats)'), ('recommended', 'Recommended Best-Practice Asset'), ('deprecated_scheduled_retirement', 'Deprecated - Scheduled for Retirement'), ('rejected_unfit_for_use', 'Rejected - Unfit for Enterprise Decision-Making')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `asset`: `ForeignKey('bi.CatalogAsset', on_delete=CASCADE, related_name='endorsements')`
  - `endorsement_type`: `CharField(max_length=30, choices=ENDORSEMENT_TYPE_CHOICES, default='formal_certification')`
  - `verdict`: `CharField(max_length=35, choices=VERDICT_CHOICES, default='approved_certified')`
  - `rating_value`: `PositiveSmallIntegerField(null=True, blank=True)`
  - `attested_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='catalog_endorsements')`
  - `attested_at`: `DateTimeField(auto_now_add=True)`
  - `valid_until`: `DateField(null=True, blank=True)`
  - `criteria_checklist_json`: `JSONField(default=dict, blank=True)`
  - `review_comments`: `TextField(blank=True)`
  - `is_active`: `BooleanField(default=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='bi_btru_tenant_num_uniq')`
  - `Index(fields=['tenant', 'asset'], name='idx_btru_ten_asset')`
  - `Index(fields=['tenant', 'endorsement_type'], name='idx_btru_ten_etype')`
  - `Index(fields=['tenant', 'verdict'], name='idx_btru_ten_verdict')`
  - `Index(fields=['tenant', 'is_active'], name='idx_btru_ten_active')`

---

## 2. Forms Contract

- `apps/bi/forms/DataCatalog/CatalogAssets.py`:
  - `CatalogAssetForm`: ModelForm for `CatalogAsset`. Excludes: `tenant`, `number`, `view_count`, `average_rating`, `created_at`, `updated_at`.
- `apps/bi/forms/DataCatalog/CatalogLineageEdges.py`:
  - `CatalogLineageEdgeForm`: ModelForm for `CatalogLineageEdge`. Excludes: `tenant`, `number`, `created_at`, `updated_at`.
- `apps/bi/forms/DataCatalog/DataGovernancePolicies.py`:
  - `DataGovernancePolicyForm`: ModelForm for `DataGovernancePolicy`. Excludes: `tenant`, `number`, `created_at`, `updated_at`.
- `apps/bi/forms/DataCatalog/CatalogTrustEndorsements.py`:
  - `CatalogTrustEndorsementForm`: ModelForm for `CatalogTrustEndorsement`. Excludes: `tenant`, `number`, `attested_at`, `created_at`, `updated_at`.

---

## 3. URLs Contract

All URLs registered under `apps/bi/urls/DataCatalog/` with app namespace `bi:`:

| URL Pattern | View Name | View Function |
|---|---|---|
| `catalog/overview/` | `bi:catalog_overview` | `catalog_overview` |
| `catalog/assets/` | `bi:catalog_asset_list` | `catalog_asset_list` |
| `catalog/assets/create/` | `bi:catalog_asset_create` | `catalog_asset_create` |
| `catalog/assets/<int:pk>/` | `bi:catalog_asset_detail` | `catalog_asset_detail` |
| `catalog/assets/<int:pk>/edit/` | `bi:catalog_asset_edit` | `catalog_asset_edit` |
| `catalog/assets/<int:pk>/delete/` | `bi:catalog_asset_delete` | `catalog_asset_delete` |
| `catalog/assets/<int:pk>/certify/` | `bi:catalog_asset_certify` | `catalog_asset_certify` |
| `catalog/assets/<int:pk>/deprecate/` | `bi:catalog_asset_deprecate` | `catalog_asset_deprecate` |
| `catalog/lineage/` | `bi:catalog_lineage_edge_list` | `catalog_lineage_edge_list` |
| `catalog/lineage/create/` | `bi:catalog_lineage_edge_create` | `catalog_lineage_edge_create` |
| `catalog/lineage/<int:pk>/` | `bi:catalog_lineage_edge_detail` | `catalog_lineage_edge_detail` |
| `catalog/lineage/<int:pk>/edit/` | `bi:catalog_lineage_edge_edit` | `catalog_lineage_edge_edit` |
| `catalog/lineage/<int:pk>/delete/` | `bi:catalog_lineage_edge_delete` | `catalog_lineage_edge_delete` |
| `catalog/policies/` | `bi:data_governance_policy_list` | `data_governance_policy_list` |
| `catalog/policies/create/` | `bi:data_governance_policy_create` | `data_governance_policy_create` |
| `catalog/policies/<int:pk>/` | `bi:data_governance_policy_detail` | `data_governance_policy_detail` |
| `catalog/policies/<int:pk>/edit/` | `bi:data_governance_policy_edit` | `data_governance_policy_edit` |
| `catalog/policies/<int:pk>/delete/` | `bi:data_governance_policy_delete` | `data_governance_policy_delete` |
| `catalog/endorsements/` | `bi:catalog_trust_endorsement_list` | `catalog_trust_endorsement_list` |
| `catalog/endorsements/create/` | `bi:catalog_trust_endorsement_create` | `catalog_trust_endorsement_create` |
| `catalog/endorsements/<int:pk>/` | `bi:catalog_trust_endorsement_detail` | `catalog_trust_endorsement_detail` |
| `catalog/endorsements/<int:pk>/edit/` | `bi:catalog_trust_endorsement_edit` | `catalog_trust_endorsement_edit` |
| `catalog/endorsements/<int:pk>/delete/` | `bi:catalog_trust_endorsement_delete` | `catalog_trust_endorsement_delete` |

---

## 4. View Context Keys Contract (MANDATORY — Every Key Pinned)

### 4.1 Overview View
- **`catalog_overview`**:
  - `total_assets`: count of all active catalog assets
  - `certified_assets_count`: count of assets with `certification_status='certified'`
  - `tier1_assets_count`: count of assets with `enterprise_tier='tier_1_mission_critical'`
  - `total_lineage_edges`: count of active lineage edges
  - `column_lineage_count`: count of column-level edges
  - `total_policies`: count of active governance policies
  - `strict_policies_count`: count of policies with `enforcement_level='strict_blocking'`
  - `total_endorsements`: count of active endorsements
  - `recent_assets`: QuerySet of 6 recent `CatalogAsset`
  - `recent_edges`: QuerySet of 5 recent `CatalogLineageEdge`
  - `recent_policies`: QuerySet of 5 recent `DataGovernancePolicy`
  - `recent_endorsements`: QuerySet of 5 recent `CatalogTrustEndorsement`
  - `domain_distribution`: list/dict of domain breakdown
  - `sensitivity_distribution`: list/dict of sensitivity breakdown

### 4.2 Catalog Asset Views
- **`catalog_asset_list`**:
  - `page_obj`: paginated Page object
  - `assets`: `page_obj` alias
  - `domain_choices`: `CatalogAsset.DOMAIN_CHOICES`
  - `asset_type_choices`: `CatalogAsset.ASSET_TYPE_CHOICES`
  - `sensitivity_choices`: `CatalogAsset.SENSITIVITY_CHOICES`
  - `tier_choices`: `CatalogAsset.TIER_CHOICES`
  - `certification_status_choices`: `CatalogAsset.CERTIFICATION_STATUS_CHOICES`
  - `total_count`: total count
  - `certified_count`: count with status='certified'
  - `tier1_count`: count with enterprise_tier='tier_1_mission_critical'
  - `restricted_count`: count with sensitivity in ('restricted_pii', 'highly_sensitive_pci_phi')
- **`catalog_asset_detail`**:
  - `asset`: `CatalogAsset` instance
  - `schema_columns`: parsed list of column definitions
  - `search_tags`: parsed list of tags
  - `upstream_lineage`: QuerySet of `CatalogLineageEdge` where `downstream_asset=asset`
  - `downstream_lineage`: QuerySet of `CatalogLineageEdge` where `upstream_asset=asset`
  - `endorsements`: QuerySet of `CatalogTrustEndorsement` for this asset
  - `replacement_asset`: `asset.deprecation_replacement`
- **`catalog_asset_create`** / **`catalog_asset_edit`**:
  - `form`: `CatalogAssetForm`
  - `asset`: instance or `None`
  - `is_edit`: boolean

### 4.3 Catalog Lineage Edge Views
- **`catalog_lineage_edge_list`**:
  - `page_obj`: paginated Page object
  - `lineage_edges`: `page_obj` alias
  - `lineage_type_choices`: `CatalogLineageEdge.LINEAGE_TYPE_CHOICES`
  - `impact_choices`: `CatalogLineageEdge.IMPACT_CRITICALITY_CHOICES`
  - `total_count`: total count
  - `table_lineage_count`: count with `lineage_type='table_level'`
  - `column_lineage_count`: count with `lineage_type='column_level'`
  - `critical_count`: count with `impact_criticality='critical'`
- **`catalog_lineage_edge_detail`**:
  - `edge`: `CatalogLineageEdge` instance
- **`catalog_lineage_edge_create`** / **`catalog_lineage_edge_edit`**:
  - `form`: `CatalogLineageEdgeForm`
  - `edge`: instance or `None`
  - `is_edit`: boolean

### 4.4 Data Governance Policy Views
- **`data_governance_policy_list`**:
  - `page_obj`: paginated Page object
  - `policies`: `page_obj` alias
  - `policy_type_choices`: `DataGovernancePolicy.POLICY_TYPE_CHOICES`
  - `framework_choices`: `DataGovernancePolicy.REGULATORY_FRAMEWORK_CHOICES`
  - `enforcement_choices`: `DataGovernancePolicy.ENFORCEMENT_LEVEL_CHOICES`
  - `total_count`: total count
  - `strict_count`: count with `enforcement_level='strict_blocking'`
  - `active_count`: count of active policies
- **`data_governance_policy_detail`**:
  - `policy`: `DataGovernancePolicy` instance
- **`data_governance_policy_create`** / **`data_governance_policy_edit`**:
  - `form`: `DataGovernancePolicyForm`
  - `policy`: instance or `None`
  - `is_edit`: boolean

### 4.5 Catalog Trust Endorsement Views
- **`catalog_trust_endorsement_list`**:
  - `page_obj`: paginated Page object
  - `endorsements`: `page_obj` alias
  - `endorsement_type_choices`: `CatalogTrustEndorsement.ENDORSEMENT_TYPE_CHOICES`
  - `verdict_choices`: `CatalogTrustEndorsement.VERDICT_CHOICES`
  - `total_count`: total count
  - `certified_count`: count with `verdict='approved_certified'`
  - `deprecated_count`: count with `verdict='deprecated_scheduled_retirement'`
- **`catalog_trust_endorsement_detail`**:
  - `endorsement`: `CatalogTrustEndorsement` instance
  - `checklist_items`: parsed dict or items
- **`catalog_trust_endorsement_create`** / **`catalog_trust_endorsement_edit`**:
  - `form`: `CatalogTrustEndorsementForm`
  - `endorsement`: instance or `None`
  - `is_edit`: boolean

---

## 5. Templates Contract

All templates located under `templates/bi/data_catalog/`:
- `templates/bi/data_catalog/catalog_overview.html`
- `templates/bi/data_catalog/catalog_asset/list.html`
- `templates/bi/data_catalog/catalog_asset/detail.html`
- `templates/bi/data_catalog/catalog_asset/form.html`
- `templates/bi/data_catalog/catalog_lineage_edge/list.html`
- `templates/bi/data_catalog/catalog_lineage_edge/detail.html`
- `templates/bi/data_catalog/catalog_lineage_edge/form.html`
- `templates/bi/data_catalog/data_governance_policy/list.html`
- `templates/bi/data_catalog/data_governance_policy/detail.html`
- `templates/bi/data_catalog/data_governance_policy/form.html`
- `templates/bi/data_catalog/catalog_trust_endorsement/list.html`
- `templates/bi/data_catalog/catalog_trust_endorsement/detail.html`
- `templates/bi/data_catalog/catalog_trust_endorsement/form.html`
