# Contract — Sub-module 10.6: Master Data Management (MDM) (Module 10: Business Intelligence, `bi`)

- **Sub-module:** 10.6 Master Data Management (MDM) · **Module:** 10 Business Intelligence · **App:** `apps/bi`
- **Date:** 2026-11-04 · **Status:** FROZEN PRE-BUILD CONTRACT · **Phase:** 3.1 Spec
- **App Status:** Existing app `apps/bi/` (scaffolded in 10.1; extended in 10.2, 10.3, 10.4, 10.5). Incremental migration: `0014_...`
- **Package Layout:** `MasterData/` across `models/`, `forms/`, `views/`, `urls/`, and templates `templates/bi/master_data/`.

---

## 1. Models & CHOICES Contract

All 4 top-level models inherit from `apps.bi.models._base.TenantNumbered` (`tenant`, `number`, `created_at`, `updated_at`).

### 1.1 `MdmGoldenRecord` (`apps/bi/models/MasterData/MdmGoldenRecords.py`)
- **Table:** `bi_mdm_golden_record`
- **Number Prefix:** `BMGR` (`BMGR-00001`)
- **CHOICES:**
  - `DOMAIN_CHOICES = [('customer', 'Customer Master'), ('vendor', 'Vendor / Supplier Master'), ('product', 'Product / Material Master'), ('asset', 'Asset / Facility Master'), ('employee', 'Employee / Personnel Master'), ('account', 'General Ledger Account Master'), ('custom', 'Custom Domain Master')]`
  - `STATUS_CHOICES = [('draft', 'Draft / Staging'), ('pending_review', 'Pending Steward Review'), ('approved', 'Approved / Certified Active'), ('in_dispute', 'In Dispute / Exception Flagged'), ('merged', 'Merged / Consolidated'), ('superseded', 'Superseded'), ('archived', 'Archived')]`
  - `TRUST_TIER_CHOICES = [('gold', 'Gold Tier (Certified, Complete)'), ('silver', 'Silver Tier (Standard Confidence)'), ('bronze', 'Bronze Tier (Partial / Unverified)')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `name`: `CharField(max_length=255)`
  - `code`: `SlugField(max_length=80)`
  - `domain`: `CharField(max_length=30, choices=DOMAIN_CHOICES, default='customer')`
  - `status`: `CharField(max_length=30, choices=STATUS_CHOICES, default='approved')`
  - `trust_tier`: `CharField(max_length=20, choices=TRUST_TIER_CHOICES, default='silver')`
  - `confidence_score`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal('100.00'))`
  - `tax_id`: `CharField(max_length=64, blank=True)`
  - `primary_email`: `EmailField(blank=True)`
  - `primary_phone`: `CharField(max_length=40, blank=True)`
  - `primary_address`: `TextField(blank=True)`
  - `party`: `ForeignKey('core.Party', null=True, blank=True, on_delete=models.SET_NULL, related_name='mdm_golden_records')`
  - `party_role`: `ForeignKey('core.PartyRole', null=True, blank=True, on_delete=models.SET_NULL, related_name='mdm_golden_records')`
  - `item`: `ForeignKey('scm.Item', null=True, blank=True, on_delete=models.SET_NULL, related_name='mdm_golden_records')`
  - `asset`: `ForeignKey('scm.Asset', null=True, blank=True, on_delete=models.SET_NULL, related_name='mdm_golden_records')`
  - `warehouse_table`: `ForeignKey('bi.WarehouseTable', null=True, blank=True, on_delete=models.SET_NULL, related_name='mdm_golden_records')`
  - `source_record_count`: `PositiveIntegerField(default=1)`
  - `golden_attributes_json`: `JSONField(default=dict)`
  - `source_crosswalks_json`: `JSONField(default=list)`
  - `merged_into_record`: `ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='absorbed_records')`
  - `merged_at`: `DateTimeField(null=True, blank=True)`
  - `assigned_steward`: `ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='assigned_golden_records')`
  - `reviewed_by`: `ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')`
  - `reviewed_at`: `DateTimeField(null=True, blank=True)`
  - `stewardship_notes`: `TextField(blank=True)`
  - `is_active`: `BooleanField(default=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'domain', 'code'], name='bi_bmgr_tenant_dom_code_uniq')`
  - `UniqueConstraint(fields=['tenant', 'number'], name='bi_bmgr_tenant_num_uniq')`
  - `Index(fields=['tenant', 'domain'], name='idx_bmgr_ten_dom')`
  - `Index(fields=['tenant', 'status'], name='idx_bmgr_ten_status')`
  - `Index(fields=['tenant', 'trust_tier'], name='idx_bmgr_ten_tier')`
  - `Index(fields=['tenant', 'party'], name='idx_bmgr_ten_party')`
  - `Index(fields=['tenant', 'item'], name='idx_bmgr_ten_item')`
  - `Index(fields=['tenant', 'tax_id'], name='idx_bmgr_ten_taxid')`
  - `Index(fields=['tenant', 'is_active'], name='idx_bmgr_ten_active')`

---

### 1.2 `MdmSurvivorshipRule` (`apps/bi/models/MasterData/MdmSurvivorshipRules.py`)
- **Table:** `bi_mdm_survivorship_rule`
- **Number Prefix:** `BMSR` (`BMSR-00001`)
- **CHOICES:**
  - `DOMAIN_CHOICES = [('all', 'All Domains'), ('customer', 'Customer Master'), ('vendor', 'Vendor Master'), ('product', 'Product Master'), ('asset', 'Asset Master'), ('employee', 'Employee Master')]`
  - `SURVIVORSHIP_STRATEGY_CHOICES = [('source_priority', 'Source System Trust Precedence'), ('most_recent', 'Most Recently Updated Timestamp'), ('highest_completeness', 'Highest Completeness / Quality Score'), ('most_frequent', 'Most Frequent Value (Majority Vote)'), ('manual_pick', 'Manual Data Steward Selection'), ('oldest_original', 'Oldest Original Value (Earliest Created)')]`
  - `MATCH_ALGORITHM_CHOICES = [('exact', 'Exact Deterministic Match'), ('fuzzy_levenshtein', 'Fuzzy Levenshtein Distance'), ('fuzzy_jaro_winkler', 'Fuzzy Jaro-Winkler Similarity'), ('phonetic_soundex', 'Phonetic Soundex / Metaphone'), ('token_set_ratio', 'Token Set Ratio (Order Independent)'), ('rule_expression', 'Custom Rule Expression')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `name`: `CharField(max_length=150)`
  - `code`: `SlugField(max_length=60)`
  - `domain`: `CharField(max_length=30, choices=DOMAIN_CHOICES, default='all')`
  - `target_field`: `CharField(max_length=100, default='*')`
  - `survivorship_strategy`: `CharField(max_length=30, choices=SURVIVORSHIP_STRATEGY_CHOICES, default='source_priority')`
  - `match_algorithm`: `CharField(max_length=30, choices=MATCH_ALGORITHM_CHOICES, default='exact')`
  - `match_threshold_pct`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal('80.00'))`
  - `auto_merge_threshold_pct`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal('95.00'))`
  - `source_priority_list_json`: `JSONField(default=list)`
  - `priority_order`: `PositiveIntegerField(default=10)`
  - `steward`: `ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='stewarded_mdm_rules')`
  - `description`: `TextField(blank=True)`
  - `is_active`: `BooleanField(default=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'code'], name='bi_bmsr_tenant_code_uniq')`
  - `UniqueConstraint(fields=['tenant', 'number'], name='bi_bmsr_tenant_num_uniq')`
  - `Index(fields=['tenant', 'domain'], name='idx_bmsr_ten_dom')`
  - `Index(fields=['tenant', 'target_field'], name='idx_bmsr_ten_tfield')`
  - `Index(fields=['tenant', 'survivorship_strategy'], name='idx_bmsr_ten_strat')`
  - `Index(fields=['tenant', 'priority_order'], name='idx_bmsr_ten_porder')`
  - `Index(fields=['tenant', 'is_active'], name='idx_bmsr_ten_active')`

---

### 1.3 `MdmHierarchyNode` (`apps/bi/models/MasterData/MdmHierarchyNodes.py`)
- **Table:** `bi_mdm_hierarchy_node`
- **Number Prefix:** `BMHR` (`BMHR-00001`)
- **CHOICES:**
  - `HIERARCHY_TYPE_CHOICES = [('corporate_legal', 'Corporate & Legal Subsidiary Tree'), ('account_group', 'Sales & Account Grouping Hierarchy'), ('product_taxonomy', 'Product Category & SKU Taxonomy'), ('org_reporting', 'Organizational & Departmental Hierarchy'), ('cost_center_rollup', 'Financial Cost Center Rollup'), ('asset_location', 'Physical Facility & Asset Location Tree')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `name`: `CharField(max_length=200)`
  - `code`: `SlugField(max_length=80)`
  - `hierarchy_type`: `CharField(max_length=30, choices=HIERARCHY_TYPE_CHOICES, default='corporate_legal')`
  - `parent`: `ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE, related_name='children')`
  - `level`: `PositiveIntegerField(default=1)`
  - `path`: `CharField(max_length=500, blank=True, db_index=True)`
  - `golden_record`: `ForeignKey('bi.MdmGoldenRecord', null=True, blank=True, on_delete=models.SET_NULL, related_name='hierarchy_nodes')`
  - `party`: `ForeignKey('core.Party', null=True, blank=True, on_delete=models.SET_NULL, related_name='mdm_hierarchy_nodes')`
  - `org_unit`: `ForeignKey('core.OrgUnit', null=True, blank=True, on_delete=models.SET_NULL, related_name='mdm_hierarchy_nodes')`
  - `item_category`: `ForeignKey('scm.ItemCategory', null=True, blank=True, on_delete=models.SET_NULL, related_name='mdm_hierarchy_nodes')`
  - `relationship_kind`: `CharField(max_length=60, default='parent_child')`
  - `sort_order`: `PositiveIntegerField(default=10)`
  - `valid_from`: `DateField(null=True, blank=True)`
  - `valid_to`: `DateField(null=True, blank=True)`
  - `description`: `TextField(blank=True)`
  - `is_active`: `BooleanField(default=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'hierarchy_type', 'code'], name='bi_bmhr_tenant_type_code_uniq')`
  - `UniqueConstraint(fields=['tenant', 'number'], name='bi_bmhr_tenant_num_uniq')`
  - `Index(fields=['tenant', 'hierarchy_type'], name='idx_bmhr_ten_htype')`
  - `Index(fields=['tenant', 'parent'], name='idx_bmhr_ten_parent')`
  - `Index(fields=['tenant', 'path'], name='idx_bmhr_ten_path')`
  - `Index(fields=['tenant', 'golden_record'], name='idx_bmhr_ten_grec')`
  - `Index(fields=['tenant', 'is_active'], name='idx_bmhr_ten_active')`

---

### 1.4 `MdmReferenceCode` (`apps/bi/models/MasterData/MdmReferenceCodes.py`)
- **Table:** `bi_mdm_reference_code`
- **Number Prefix:** `BMRD` (`BMRD-00001`)
- **CHOICES:**
  - `STATUS_CHOICES = [('draft', 'Draft / Under Review'), ('active', 'Active & Canonical'), ('deprecated', 'Deprecated (Do Not Use for New Records)'), ('superseded', 'Superseded by Newer Standard'), ('inactive', 'Inactive')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `code_set`: `CharField(max_length=80, db_index=True)`
  - `canonical_code`: `CharField(max_length=60, db_index=True)`
  - `canonical_name`: `CharField(max_length=200)`
  - `source_system`: `CharField(max_length=80, blank=True)`
  - `source_code`: `CharField(max_length=80, blank=True)`
  - `category`: `CharField(max_length=80, blank=True)`
  - `status`: `CharField(max_length=25, choices=STATUS_CHOICES, default='active')`
  - `superseded_by`: `ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='superseded_codes')`
  - `effective_from`: `DateField(null=True, blank=True)`
  - `effective_to`: `DateField(null=True, blank=True)`
  - `attributes_json`: `JSONField(default=dict)`
  - `description`: `TextField(blank=True)`
  - `is_active`: `BooleanField(default=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'code_set', 'canonical_code', 'source_system', 'source_code'], name='bi_bmrd_ten_cset_ccode_src_uniq')`
  - `UniqueConstraint(fields=['tenant', 'number'], name='bi_bmrd_tenant_num_uniq')`
  - `Index(fields=['tenant', 'code_set'], name='idx_bmrd_ten_cset')`
  - `Index(fields=['tenant', 'canonical_code'], name='idx_bmrd_ten_ccode')`
  - `Index(fields=['tenant', 'status'], name='idx_bmrd_ten_status')`
  - `Index(fields=['tenant', 'source_system', 'source_code'], name='idx_bmrd_ten_src')`
  - `Index(fields=['tenant', 'is_active'], name='idx_bmrd_ten_active')`

---

## 2. Forms Contract (`apps/bi/forms/MasterData/`)

All forms inherit from `forms.ModelForm` and enforce Tailwind styling (`.form-input`, `.form-select`, `.form-textarea`, etc.).

### 2.1 `MdmGoldenRecordForm` (`apps/bi/forms/MasterData/MdmGoldenRecordForms.py`)
- **Fields:** `['name', 'code', 'domain', 'status', 'trust_tier', 'confidence_score', 'tax_id', 'primary_email', 'primary_phone', 'primary_address', 'party', 'party_role', 'item', 'asset', 'warehouse_table', 'assigned_steward', 'stewardship_notes', 'is_active']`
- **Exclusions:** `['tenant', 'number', 'merged_into_record', 'merged_at', 'reviewed_by', 'reviewed_at', 'source_record_count', 'golden_attributes_json', 'source_crosswalks_json', 'created_at', 'updated_at']`

### 2.2 `MdmGoldenRecordMergeForm` (`apps/bi/forms/MasterData/MdmGoldenRecordForms.py`)
- Non-model form for selecting surviving golden record and records to merge.
- **Fields:** `['surviving_record', 'merged_record_ids', 'stewardship_notes']`

### 2.3 `MdmSurvivorshipRuleForm` (`apps/bi/forms/MasterData/MdmSurvivorshipRuleForms.py`)
- **Fields:** `['name', 'code', 'domain', 'target_field', 'survivorship_strategy', 'match_algorithm', 'match_threshold_pct', 'auto_merge_threshold_pct', 'source_priority_list_json', 'priority_order', 'steward', 'description', 'is_active']`
- **Exclusions:** `['tenant', 'number', 'created_at', 'updated_at']`

### 2.4 `MdmHierarchyNodeForm` (`apps/bi/forms/MasterData/MdmHierarchyNodeForms.py`)
- **Fields:** `['name', 'code', 'hierarchy_type', 'parent', 'golden_record', 'party', 'org_unit', 'item_category', 'relationship_kind', 'sort_order', 'valid_from', 'valid_to', 'description', 'is_active']`
- **Exclusions:** `['tenant', 'number', 'level', 'path', 'created_at', 'updated_at']`

### 2.5 `MdmReferenceCodeForm` (`apps/bi/forms/MasterData/MdmReferenceCodeForms.py`)
- **Fields:** `['code_set', 'canonical_code', 'canonical_name', 'source_system', 'source_code', 'category', 'status', 'superseded_by', 'effective_from', 'effective_to', 'attributes_json', 'description', 'is_active']`
- **Exclusions:** `['tenant', 'number', 'created_at', 'updated_at']`

---

## 3. URLs Contract (`apps/bi/urls/MasterData/`)

App namespace: `bi`

| URL Pattern | View Name | View Function |
|---|---|---|
| `mdm/overview/` | `bi:mdm_overview` | `mdm_overview` |
| `mdm/golden-records/` | `bi:mdm_golden_record_list` | `mdm_golden_record_list` |
| `mdm/golden-records/create/` | `bi:mdm_golden_record_create` | `mdm_golden_record_create` |
| `mdm/golden-records/<int:pk>/` | `bi:mdm_golden_record_detail` | `mdm_golden_record_detail` |
| `mdm/golden-records/<int:pk>/edit/` | `bi:mdm_golden_record_edit` | `mdm_golden_record_edit` |
| `mdm/golden-records/<int:pk>/delete/` | `bi:mdm_golden_record_delete` | `mdm_golden_record_delete` |
| `mdm/golden-records/<int:pk>/merge/` | `bi:mdm_golden_record_merge` | `mdm_golden_record_merge` |
| `mdm/golden-records/<int:pk>/unmerge/` | `bi:mdm_golden_record_unmerge` | `mdm_golden_record_unmerge` |
| `mdm/golden-records/<int:pk>/approve/` | `bi:mdm_golden_record_approve` | `mdm_golden_record_approve` |
| `mdm/survivorship-rules/` | `bi:mdm_survivorship_rule_list` | `mdm_survivorship_rule_list` |
| `mdm/survivorship-rules/create/` | `bi:mdm_survivorship_rule_create` | `mdm_survivorship_rule_create` |
| `mdm/survivorship-rules/<int:pk>/` | `bi:mdm_survivorship_rule_detail` | `mdm_survivorship_rule_detail` |
| `mdm/survivorship-rules/<int:pk>/edit/` | `bi:mdm_survivorship_rule_edit` | `mdm_survivorship_rule_edit` |
| `mdm/survivorship-rules/<int:pk>/delete/` | `bi:mdm_survivorship_rule_delete` | `mdm_survivorship_rule_delete` |
| `mdm/hierarchy-nodes/` | `bi:mdm_hierarchy_node_list` | `mdm_hierarchy_node_list` |
| `mdm/hierarchy-nodes/create/` | `bi:mdm_hierarchy_node_create` | `mdm_hierarchy_node_create` |
| `mdm/hierarchy-nodes/<int:pk>/` | `bi:mdm_hierarchy_node_detail` | `mdm_hierarchy_node_detail` |
| `mdm/hierarchy-nodes/<int:pk>/edit/` | `bi:mdm_hierarchy_node_edit` | `mdm_hierarchy_node_edit` |
| `mdm/hierarchy-nodes/<int:pk>/delete/` | `bi:mdm_hierarchy_node_delete` | `mdm_hierarchy_node_delete` |
| `mdm/reference-codes/` | `bi:mdm_reference_code_list` | `mdm_reference_code_list` |
| `mdm/reference-codes/create/` | `bi:mdm_reference_code_create` | `mdm_reference_code_create` |
| `mdm/reference-codes/<int:pk>/` | `bi:mdm_reference_code_detail` | `mdm_reference_code_detail` |
| `mdm/reference-codes/<int:pk>/edit/` | `bi:mdm_reference_code_edit` | `mdm_reference_code_edit` |
| `mdm/reference-codes/<int:pk>/delete/` | `bi:mdm_reference_code_delete` | `mdm_reference_code_delete` |

---

## 4. View Context Keys Contract (MANDATORY — Every Key Pinned)

### 4.1 Overview View
- **`mdm_overview`**:
  - `total_golden_records`: count of all active golden records
  - `total_rules`: count of survivorship rules
  - `total_hierarchy_nodes`: count of hierarchy nodes
  - `total_reference_codes`: count of reference codes
  - `gold_tier_count`: count of golden records with trust_tier='gold'
  - `pending_review_count`: count of golden records with status='pending_review'
  - `domain_distribution`: list/dict of count per domain
  - `recent_golden_records`: QuerySet of recent 6 MdmGoldenRecord
  - `survivorship_rules`: QuerySet of recent 5 MdmSurvivorshipRule
  - `root_hierarchies`: QuerySet of root hierarchy nodes (level=1)
  - `code_set_counts`: list/dict of counts by code_set

### 4.2 Golden Record Views
- **`mdm_golden_record_list`**:
  - `page_obj`: paginated Page object
  - `golden_records`: `page_obj` alias
  - `domain_choices`: `MdmGoldenRecord.DOMAIN_CHOICES`
  - `status_choices`: `MdmGoldenRecord.STATUS_CHOICES`
  - `trust_tier_choices`: `MdmGoldenRecord.TRUST_TIER_CHOICES`
  - `total_count`: total count
  - `gold_count`: count with trust_tier='gold'
  - `pending_count`: count with status='pending_review'
  - `merged_count`: count with status='merged'
- **`mdm_golden_record_detail`**:
  - `golden_record`: `MdmGoldenRecord` instance
  - `crosswalks`: parsed list of source crosswalk records
  - `attributes_dict`: parsed dict of golden attribute provenance
  - `absorbed_records`: QuerySet of records merged into this golden record
  - `hierarchy_nodes`: QuerySet of linked hierarchy nodes
- **`mdm_golden_record_create`** / **`mdm_golden_record_edit`**:
  - `form`: `MdmGoldenRecordForm`
  - `golden_record`: instance or `None`
  - `is_edit`: boolean

### 4.3 Survivorship Rule Views
- **`mdm_survivorship_rule_list`**:
  - `page_obj`: paginated Page object
  - `rules`: `page_obj` alias
  - `domain_choices`: `MdmSurvivorshipRule.DOMAIN_CHOICES`
  - `strategy_choices`: `MdmSurvivorshipRule.SURVIVORSHIP_STRATEGY_CHOICES`
  - `match_choices`: `MdmSurvivorshipRule.MATCH_ALGORITHM_CHOICES`
  - `total_count`: total count
  - `active_count`: count of active rules
- **`mdm_survivorship_rule_detail`**:
  - `rule`: `MdmSurvivorshipRule` instance
  - `source_priority_list`: parsed list of strings
- **`mdm_survivorship_rule_create`** / **`mdm_survivorship_rule_edit`**:
  - `form`: `MdmSurvivorshipRuleForm`
  - `rule`: instance or `None`
  - `is_edit`: boolean

### 4.4 Hierarchy Node Views
- **`mdm_hierarchy_node_list`**:
  - `page_obj`: paginated Page object
  - `hierarchy_nodes`: `page_obj` alias
  - `hierarchy_type_choices`: `MdmHierarchyNode.HIERARCHY_TYPE_CHOICES`
  - `total_count`: total count
  - `root_nodes_count`: count with parent__isnull=True
- **`mdm_hierarchy_node_detail`**:
  - `node`: `MdmHierarchyNode` instance
  - `children`: QuerySet of child nodes
  - `ancestors`: list/QuerySet of ancestor nodes along the path
- **`mdm_hierarchy_node_create`** / **`mdm_hierarchy_node_edit`**:
  - `form`: `MdmHierarchyNodeForm`
  - `node`: instance or `None`
  - `is_edit`: boolean

### 4.5 Reference Code Views
- **`mdm_reference_code_list`**:
  - `page_obj`: paginated Page object
  - `reference_codes`: `page_obj` alias
  - `status_choices`: `MdmReferenceCode.STATUS_CHOICES`
  - `code_sets`: distinct list of `code_set` strings for tenant
  - `total_count`: total count
  - `active_count`: count with status='active'
- **`mdm_reference_code_detail`**:
  - `reference_code`: `MdmReferenceCode` instance
  - `superseded_by`: related instance if any
  - `superseding_codes`: QuerySet of codes superseded by this code
- **`mdm_reference_code_create`** / **`mdm_reference_code_edit`**:
  - `form`: `MdmReferenceCodeForm`
  - `reference_code`: instance or `None`
  - `is_edit`: boolean

---

## 5. Navigation `LIVE_LINKS["10.6"]` Contract

Mapped verbatim to `NavERP.md` 10.6 feature bullets in `apps/core/navigation.py`:
```python
"10.6": {
    "Golden Record Management": "bi:mdm_golden_record_list",
    "Match, Merge & Survivorship": "bi:mdm_survivorship_rule_list",
    "Hierarchy & Relationship Management": "bi:mdm_hierarchy_node_list",
    "Reference Data Management": "bi:mdm_reference_code_list",
    "Data Stewardship Workflows": "bi:mdm_golden_record_list",
    # Extra live leaves
    "Golden Records": "bi:mdm_golden_record_list",
    "Survivorship Rules": "bi:mdm_survivorship_rule_list",
    "Hierarchy Nodes": "bi:mdm_hierarchy_node_list",
    "Reference Codes": "bi:mdm_reference_code_list",
    "Master Data Overview": "bi:mdm_overview",
},
```
