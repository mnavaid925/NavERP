# Build Contract — Sales 8.19 Master Data & Configuration (`sales`)

> Frozen 2026-10-28 against the live tree at BASE commit `d289c460e5e74689d5fee8f2c23c1e9734fefc70`.
> This contract is the single source of truth for the entity-by-entity build.
> Every variable name, field name, URL name, context key, and badge class is pinned here.
> Phase 4 reviews `d289c46...HEAD`.

---

## 0. Scope & Capability Coverage

Four NavERP.md §8.19 capability bullets (`NavERP.md:1442–1448`) map to **4 owned models + 1 Central Overview Dashboard + standard CRUD views**:

| NavERP.md bullet (character-for-character) | What 8.19 owns | URL Name |
|---|---|---|
| **Product Catalog & Pricing** — SKU management, price books, currency support, and regional pricing. | `SalesPriceBookEntry` [`PBE-`] — concrete pricing junction linking `crm.PriceBook` and `crm.Product` with SKU code, currency, list price, floor price, volume tier breaks, MOQ, and validity dates | `sales:pbe_list` |
| **Custom Fields & Objects** — Extensible data model, custom relationships, and formula fields. | `SalesCustomEntityDefinition` [`SCO-`] — metadata register for custom sales objects and extensible fields (formula expressions, lookup relationships, picklists, validation rules) | `sales:sco_list` |
| **Sales Methodology Configuration** — MEDDIC, SPIN, Challenger, or custom methodology stage mapping. | `SalesMethodology` [`SMD-`] — formal qualification methodology framework templates with pipeline stage gating, weighted criteria checklists, and coaching prompts | `sales:smd_list` |
| **Localization & Multi-Language** — Language packs, regional formats, and compliance rule localization. | `SalesRegionalSetting` [`SRG-`] — regional commercial configuration (currencies, date/number formats, tax display mode, quote terms, statutory legal disclaimers, compliance frameworks) | `sales:srg_list` |
| **Central Master Data & Configuration Overview** | KPI dashboard aggregating catalog pricing, schema extensions, qualification methodologies, and regional commercial profiles | `sales:master_data_overview` |

### Architectural Rulings & Invariants

1. **Backend Package Layout (`MasterDataConfiguration`)**:
   - Organized in `apps/sales/{models,forms,views,urls}/MasterDataConfiguration/`.
   - Layers line up one-to-one:
     - `SalesPriceBookEntries.py`
     - `SalesCustomEntityDefinitions.py`
     - `SalesMethodologies.py`
     - `SalesRegionalSettings.py`
     - `Overview.py` (for the central configuration dashboard)
2. **Number Prefixes (Verified Collision-Free Repo-Wide)**:
   - `SalesPriceBookEntry`: `PBE-`
   - `SalesCustomEntityDefinition`: `SCO-`
   - `SalesMethodology`: `SMD-`
   - `SalesRegionalSetting`: `SRG-`
3. **Multi-Tenancy & Security**:
   - Every model inherits `TenantNumbered` from `apps.sales.models._base`.
   - All querysets filtered strictly by `tenant=request.tenant`.
   - Privilege writes use `@tenant_admin_required` or `@login_required` + tenant scoping.
   - Audit trail via `write_audit_log` (`apps.core.utils`) with verbs `<= 10` chars (`create`, `update`, `delete`).
4. **Theme Design System & Badges (L33)**:
   - Badge classes strictly color-named: `.badge-green`, `.badge-red`, `.badge-amber`, `.badge-info`, `.badge-muted`, `.badge-slate`. Semantic badge classes do not exist.
   - Stat cards with icon backgrounds: `blue`, `green`, `orange`, `purple`, `slate`.
5. **Filters & State Preservation**:
   - Filter querysets evaluated before pagination.
   - Filter comparison rules: string values `{% if request.GET.field == value %}selected{% endif %}`, PK values `{% if request.GET.fk == obj.pk|stringformat:"d" %}selected{% endif %}`.

---

## 1. Verified Spine & Sibling Relationships

- `core.Tenant` (`apps.core.models.Tenant`)
- `core.Party` (`apps.core.models.Party`)
- `crm.PriceBook` (`apps.crm.models.SalesForceAutomation.PriceBooks.PriceBook`)
- `crm.Product` (`apps.crm.models.SalesForceAutomation.Products.Product`)
- `scm.Item` (`apps.scm.models.InventoryCatalog.Items.Item` — optional link)
- `sales.Pipeline` (`apps.sales.models.OpportunityPipeline.Pipelines.Pipeline`)
- `sales.PipelineStage` (`apps.sales.models.OpportunityPipeline.Pipelines.PipelineStage`)
- `accounts.User` (`settings.AUTH_USER_MODEL`)

---

## 2. Model Specifications (`apps/sales/models/MasterDataConfiguration/`)

### 2.1 `SalesPriceBookEntry` (`SalesPriceBookEntries.py`)
- **Inheritance:** `TenantNumbered`
- **Prefix:** `NUMBER_PREFIX = "PBE"`
- **Choices:**
  - `PRICING_MODEL_CHOICES = [("flat", "Flat Unit Price"), ("tier_volume", "Volume Tier Discount"), ("tier_graduated", "Graduated / Bracket Pricing"), ("cost_markup", "Cost-Plus Markup")]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=models.CASCADE, related_name='sales_price_book_entries')`
  - `number`: `CharField(max_length=32, editable=False)`
  - `price_book`: `ForeignKey('crm.PriceBook', on_delete=models.CASCADE, related_name='sales_entries')`
  - `product`: `ForeignKey('crm.Product', on_delete=models.CASCADE, related_name='sales_price_book_entries')`
  - `item`: `ForeignKey('scm.Item', on_delete=models.SET_NULL, null=True, blank=True, related_name='sales_price_book_entries', help_text="Physical inventory SKU link")`
  - `sku_code`: `CharField(max_length=64, blank=True, default="", db_index=True)`
  - `currency_code`: `CharField(max_length=3, default="USD")`
  - `list_price`: `DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(0)])`
  - `floor_price`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"), validators=[MinValueValidator(0)])`
  - `pricing_model`: `CharField(max_length=20, choices=PRICING_MODEL_CHOICES, default="flat")`
  - `min_quantity`: `DecimalField(max_digits=10, decimal_places=2, default=Decimal("1.00"), validators=[MinValueValidator(0)])`
  - `volume_tier_breaks`: `JSONField(default=list, blank=True, help_text="List of {min_qty, discount_pct, tier_price}")`
  - `valid_from`: `DateField(null=True, blank=True)`
  - `valid_to`: `DateField(null=True, blank=True)`
  - `is_active`: `BooleanField(default=True)`
  - `notes`: `TextField(blank=True, default="")`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=["tenant", "number"], name="sales_pbe_tenant_num_uniq")`
  - `UniqueConstraint(fields=["tenant", "price_book", "product", "currency_code"], name="sales_pbe_bk_prd_cur_uniq")`
  - `Index(fields=["tenant", "is_active"], name="sales_pbe_tnt_act_idx")`
  - `Index(fields=["tenant", "sku_code"], name="sales_pbe_sku_idx")`
- **Form exclusions:** `tenant`, `number`

### 2.2 `SalesCustomEntityDefinition` (`SalesCustomEntityDefinitions.py`)
- **Inheritance:** `TenantNumbered`
- **Prefix:** `NUMBER_PREFIX = "SCO"`
- **Choices:**
  - `TARGET_MODEL_CHOICES = [("opportunity", "Opportunity (crm.Opportunity)"), ("cpq_quote", "CPQ Quote (sales.CPQQuote)"), ("sales_order", "Sales Order (scm.SalesOrder)"), ("customer_contract", "Customer Contract (sales.CustomerContract)"), ("account", "Account / Customer (core.Party)"), ("standalone_custom", "Standalone Custom Sales Object")]`
  - `FIELD_TYPE_CHOICES = [("text", "Single-line Text"), ("textarea", "Multi-line Text / Markdown"), ("number", "Numeric (Integer / Decimal)"), ("currency", "Monetary Currency Amount"), ("percent", "Percentage (0–100%)"), ("date", "Calendar Date"), ("boolean", "Checkbox / Yes-No"), ("picklist", "Single Picklist Option"), ("multi_picklist", "Multi-Select Picklist"), ("formula", "Calculated Formula Expression"), ("lookup", "Lookup Relationship (1:N)"), ("master_detail", "Master-Detail Relationship")]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=models.CASCADE, related_name='sales_custom_entity_definitions')`
  - `number`: `CharField(max_length=32, editable=False)`
  - `name`: `CharField(max_length=150)`
  - `entity_code`: `SlugField(max_length=60, help_text="Identifier code e.g. deal_profit_margin_c")`
  - `target_model`: `CharField(max_length=30, choices=TARGET_MODEL_CHOICES, default="opportunity")`
  - `field_type`: `CharField(max_length=20, choices=FIELD_TYPE_CHOICES, default="text")`
  - `is_required`: `BooleanField(default=False)`
  - `formula_expression`: `CharField(max_length=255, blank=True, default="", help_text="e.g. (amount - cost) / amount * 100")`
  - `lookup_target_model`: `CharField(max_length=100, blank=True, default="", help_text="Target entity for lookup relationships")`
  - `picklist_options`: `JSONField(default=list, blank=True, help_text="Allowed picklist values")`
  - `validation_rule`: `CharField(max_length=255, blank=True, default="")`
  - `display_order`: `PositiveIntegerField(default=10)`
  - `is_active`: `BooleanField(default=True)`
  - `description`: `TextField(blank=True, default="")`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=["tenant", "number"], name="sales_sco_tenant_num_uniq")`
  - `UniqueConstraint(fields=["tenant", "target_model", "entity_code"], name="sales_sco_tnt_tgt_code_uniq")`
  - `Index(fields=["tenant", "target_model", "is_active"], name="sales_sco_tgt_act_idx")`
- **Form exclusions:** `tenant`, `number`

### 2.3 `SalesMethodology` (`SalesMethodologies.py`)
- **Inheritance:** `TenantNumbered`
- **Prefix:** `NUMBER_PREFIX = "SMD"`
- **Choices:**
  - `FRAMEWORK_CHOICES = [("meddic", "MEDDIC (Metrics, Econ Buyer, Criteria, Process, Pain, Champ)"), ("meddpicc", "MEDDPICC (+ Paper Process & Competition)"), ("bant", "BANT (Budget, Authority, Need, Timeline)"), ("spin", "SPIN (Situation, Problem, Implication, Need-Payoff)"), ("challenger", "The Challenger Sale (Teach, Tailor, Take Control)"), ("command_message", "Command of the Message / Value Selling"), ("sandler", "Sandler Selling System (Pain, Budget, Decision)"), ("custom", "Custom Commercial Methodology")]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=models.CASCADE, related_name='sales_methodologies')`
  - `number`: `CharField(max_length=32, editable=False)`
  - `name`: `CharField(max_length=150)`
  - `framework`: `CharField(max_length=30, choices=FRAMEWORK_CHOICES, default="meddic")`
  - `pipeline`: `ForeignKey('sales.Pipeline', on_delete=models.SET_NULL, null=True, blank=True, related_name='sales_methodologies')`
  - `gating_stage`: `ForeignKey('sales.PipelineStage', on_delete=models.SET_NULL, null=True, blank=True, related_name='gated_methodologies')`
  - `min_passing_score`: `PositiveIntegerField(default=70, validators=[MinValueValidator(0), MaxValueValidator(100)])`
  - `is_mandatory_gate`: `BooleanField(default=False, help_text="Enforces qualification score before pipeline advancement")`
  - `qualification_criteria`: `JSONField(default=list, blank=True, help_text="List of {key, label, weight, is_required}")`
  - `coaching_guidelines`: `TextField(blank=True, default="")`
  - `is_active`: `BooleanField(default=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=["tenant", "number"], name="sales_smd_tenant_num_uniq")`
  - `UniqueConstraint(fields=["tenant", "name"], name="sales_smd_tnt_name_uniq")`
  - `Index(fields=["tenant", "framework", "is_active"], name="sales_smd_frw_act_idx")`
- **Form exclusions:** `tenant`, `number`

### 2.4 `SalesRegionalSetting` (`SalesRegionalSettings.py`)
- **Inheritance:** `TenantNumbered`
- **Prefix:** `NUMBER_PREFIX = "SRG"`
- **Choices:**
  - `REGION_CODE_CHOICES = [("NA", "North America (US / CA)"), ("EMEA", "Europe, Middle East & Africa"), ("APAC", "Asia-Pacific"), ("DACH", "DACH (Germany, Austria, Switzerland)"), ("UK", "United Kingdom"), ("LATAM", "Latin America"), ("GLOBAL", "Global Default")]`
  - `DATE_FORMAT_CHOICES = [("YYYY-MM-DD", "ISO 8601 (YYYY-MM-DD)"), ("MM/DD/YYYY", "US Standard (MM/DD/YYYY)"), ("DD/MM/YYYY", "EU / British (DD/MM/YYYY)"), ("DD.MM.YYYY", "German / Swiss (DD.MM.YYYY)")]`
  - `NUMBER_FORMAT_CHOICES = [("1,234.56", "Comma thousand, period decimal (1,234.56)"), ("1.234,56", "Period thousand, comma decimal (1.234,56)"), ("1 234,56", "Space thousand, comma decimal (1 234,56)")]`
  - `TAX_DISPLAY_CHOICES = [("tax_exclusive", "Tax Exclusive (Subtotal + Tax = Total)"), ("tax_inclusive", "Tax Inclusive (Prices include VAT/GST)")]`
  - `COMPLIANCE_CHOICES = [("standard", "Standard Commercial Terms"), ("gdpr_commercial", "GDPR Commercial & Data Privacy Compliant"), ("sox_revenue", "SOX 404 & ASC 606 Revenue Recognition Compliant"), ("consumer_protection", "Consumer Rights & Statutory Cooling-Off Compliant"), ("export_control", "EAR / ITAR Commercial Trade & Export Compliant")]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=models.CASCADE, related_name='sales_regional_settings')`
  - `number`: `CharField(max_length=32, editable=False)`
  - `name`: `CharField(max_length=150)`
  - `region_code`: `CharField(max_length=20, choices=REGION_CODE_CHOICES, default="GLOBAL")`
  - `primary_currency`: `CharField(max_length=3, default="USD")`
  - `supported_currencies`: `JSONField(default=list, blank=True)`
  - `date_format`: `CharField(max_length=20, choices=DATE_FORMAT_CHOICES, default="YYYY-MM-DD")`
  - `number_format`: `CharField(max_length=20, choices=NUMBER_FORMAT_CHOICES, default="1,234.56")`
  - `tax_display_mode`: `CharField(max_length=20, choices=TAX_DISPLAY_CHOICES, default="tax_exclusive")`
  - `default_quote_terms`: `TextField(blank=True, default="")`
  - `statutory_disclaimer`: `TextField(blank=True, default="")`
  - `compliance_framework`: `CharField(max_length=30, choices=COMPLIANCE_CHOICES, default="standard")`
  - `cooling_off_days`: `PositiveIntegerField(default=14)`
  - `is_default`: `BooleanField(default=False)`
  - `is_active`: `BooleanField(default=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=["tenant", "number"], name="sales_srg_tenant_num_uniq")`
  - `UniqueConstraint(fields=["tenant", "region_code"], name="sales_srg_tnt_reg_uniq")`
  - `Index(fields=["tenant", "is_active", "is_default"], name="sales_srg_tnt_def_idx")`
- **Form exclusions:** `tenant`, `number`

---

## 3. URLs & Routes Contract (`apps/sales/urls/MasterDataConfiguration/`)

```python
urlpatterns = [
    # Overview Dashboard
    path("master-data/", views.master_data_overview, name="master_data_overview"),

    # Price Book Entries
    path("master-data/price-book-entries/", views.pbe_list, name="pbe_list"),
    path("master-data/price-book-entries/create/", views.pbe_create, name="pbe_create"),
    path("master-data/price-book-entries/<int:pk>/", views.pbe_detail, name="pbe_detail"),
    path("master-data/price-book-entries/<int:pk>/edit/", views.pbe_edit, name="pbe_edit"),
    path("master-data/price-book-entries/<int:pk>/delete/", views.pbe_delete, name="pbe_delete"),

    # Custom Entity Definitions
    path("master-data/custom-entities/", views.sco_list, name="sco_list"),
    path("master-data/custom-entities/create/", views.sco_create, name="sco_create"),
    path("master-data/custom-entities/<int:pk>/", views.sco_detail, name="sco_detail"),
    path("master-data/custom-entities/<int:pk>/edit/", views.sco_edit, name="sco_edit"),
    path("master-data/custom-entities/<int:pk>/delete/", views.sco_delete, name="sco_delete"),

    # Sales Methodologies
    path("master-data/methodologies/", views.smd_list, name="smd_list"),
    path("master-data/methodologies/create/", views.smd_create, name="smd_create"),
    path("master-data/methodologies/<int:pk>/", views.smd_detail, name="smd_detail"),
    path("master-data/methodologies/<int:pk>/edit/", views.smd_edit, name="smd_edit"),
    path("master-data/methodologies/<int:pk>/delete/", views.smd_delete, name="smd_delete"),

    # Regional Settings
    path("master-data/regional-settings/", views.srg_list, name="srg_list"),
    path("master-data/regional-settings/create/", views.srg_create, name="srg_create"),
    path("master-data/regional-settings/<int:pk>/", views.srg_detail, name="srg_detail"),
    path("master-data/regional-settings/<int:pk>/edit/", views.srg_edit, name="srg_edit"),
    path("master-data/regional-settings/<int:pk>/delete/", views.srg_delete, name="srg_delete"),
]
```

---

## 4. View Context Keys Contract (`apps/sales/views/MasterDataConfiguration/`)

| View Function | Template Path | Context Keys Required |
|---|---|---|
| `master_data_overview` | `sales/masterdataconfiguration/overview.html` | `kpis`, `recent_price_book_entries`, `recent_custom_entities`, `recent_methodologies`, `recent_regional_settings` |
| `pbe_list` | `sales/masterdataconfiguration/pricebookentry/list.html` | `page_obj`, `entries`, `price_books`, `products`, `pricing_models`, `q`, `selected_price_book`, `selected_pricing_model`, `selected_active` |
| `pbe_detail` | `sales/masterdataconfiguration/pricebookentry/detail.html` | `entry` |
| `pbe_create` / `pbe_edit` | `sales/masterdataconfiguration/pricebookentry/form.html` | `form`, `entry`, `is_edit` |
| `sco_list` | `sales/masterdataconfiguration/customentitydefinition/list.html` | `page_obj`, `definitions`, `target_models`, `field_types`, `q`, `selected_target_model`, `selected_field_type`, `selected_active` |
| `sco_detail` | `sales/masterdataconfiguration/customentitydefinition/detail.html` | `definition` |
| `sco_create` / `sco_edit` | `sales/masterdataconfiguration/customentitydefinition/form.html` | `form`, `definition`, `is_edit` |
| `smd_list` | `sales/masterdataconfiguration/salesmethodology/list.html` | `page_obj`, `methodologies`, `frameworks`, `pipelines`, `q`, `selected_framework`, `selected_pipeline`, `selected_active` |
| `smd_detail` | `sales/masterdataconfiguration/salesmethodology/detail.html` | `methodology` |
| `smd_create` / `smd_edit` | `sales/masterdataconfiguration/salesmethodology/form.html` | `form`, `methodology`, `is_edit` |
| `srg_list` | `sales/masterdataconfiguration/regionalsetting/list.html` | `page_obj`, `settings`, `region_codes`, `compliance_frameworks`, `q`, `selected_region`, `selected_framework`, `selected_active` |
| `srg_detail` | `sales/masterdataconfiguration/regionalsetting/detail.html` | `setting` |
| `srg_create` / `srg_edit` | `sales/masterdataconfiguration/regionalsetting/form.html` | `form`, `setting`, `is_edit` |

---

## 5. Sidebar Navigation Contract (`apps/core/navigation.py`)

`LIVE_LINKS["8.19"]` will map the 4 NavERP.md §8.19 bullets and overview routes:
```python
LIVE_LINKS["8.19"] = {
    "Configuration Overview": "sales:master_data_overview",
    "Product Catalog & Pricing": "sales:pbe_list",
    "Custom Fields & Objects": "sales:sco_list",
    "Sales Methodology Configuration": "sales:smd_list",
    "Localization & Multi-Language": "sales:srg_list",
    "Price Book Entries": "sales:pbe_list",
    "Custom Entities": "sales:sco_list",
    "Sales Methodologies": "sales:smd_list",
    "Regional Settings": "sales:srg_list",
}
```
