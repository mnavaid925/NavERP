# Contract — NavERP 8.5 Quote & Proposal Management (CPQ)

- App: `apps/sales` (**existing, live app** — no scaffold, **no `config/settings.py` edit, no `config/urls.py` edit**; `apps.sales` is already installed and the root URLconf already includes `apps/sales/urls/`).
- Sub-module: `8.5 Quote & Proposal Management (CPQ)` (NavERP.md lines **1334–1340**, five bullets).
- Research: `.claude/tasks/research-sales-8.5.md` · Plan: `.claude/tasks/todo.md` (8.5 block).
- Test namespace: `quote_proposal_cpq` (`quote_proposal_cpq_models`, `quote_proposal_cpq_forms`, `quote_proposal_cpq_views`, `quote_proposal_cpq_security`).
- Migration: **`0008`** — leaf confirmed by listing `apps/sales/migrations/`: `0007_forecastperiod_forecastscenario_forecastsubmission_and_more.py`. Next is `0008_...`.
- Read-only reference siblings: `apps/sales/models/{OpportunityPipeline/Pipelines,OpportunityOutcomes/OpportunityOutcomes,OpportunityTeams/OpportunityTeams,CompetitiveIntelligence/CompetitiveIntelligence,ContactAccountManagement/AccountPlans,SalesForecasting/ForecastSubmissions}.py`.

---

## 0. Ownership Boundaries & Principles

1. **The opportunity master belongs to CRM (`crm.Opportunity`).** 8.5 links to it (`CPQQuote.opportunity`). When a quote is marked `is_primary=True`, it syncs its total and currency back to `opportunity.amount` and `opportunity.currency`.
2. **The sales order master belongs to SCM (`scm.SalesOrder`).** 8.5 CPQ creates and populates the `scm.SalesOrder` upon conversion; it does not define a competing sales order model.
3. **No second financial ledger.** `accounting.Currency` is the only currency master; `accounting.TaxCode` is the tax rate source.
4. **Product masters:** Lines link to `crm.Product` (catalog item) and optionally to physical stock item `scm.Item` (for stock allocation & BOM/lot tracking on order conversion).
5. **Multi-tenancy:** Every model inherits from `TenantNumbered` or `TenantOwned` in `apps/sales/models/_base.py`. Every query scopes to `tenant=request.tenant`. Cross-tenant IDOR must return 404.
6. **Derived vs. Stored Pricing:**
   - Line subtotal, line tax, line total, and line margin are calculated deterministically via `cpq_recalc_quote_totals()`.
   - Quote header `subtotal`, `discount_total`, `tax_total`, `total`, `cost_total`, `margin_total`, and `margin_pct` are updated in `recalc_totals()` inside `apps/sales/cpq_services.py` and excluded from user forms to prevent tampering.

---

## 1. Naming & Package Architecture

| Item | Name | Path / Note |
|---|---|---|
| Backend package (all 4 layers) | `QuoteProposalCPQ/` | PascalCase matching other sub-modules |
| Models folder | `apps/sales/models/QuoteProposalCPQ/` | `CPQQuotes.py`, `CPQQuoteLines.py`, `ProductBundles.py`, `QuoteApprovalRules.py` |
| Forms folder | `apps/sales/forms/QuoteProposalCPQ/` | `CPQQuotes.py`, `CPQQuoteLines.py`, `ProductBundles.py`, `QuoteApprovalRules.py` |
| Views folder | `apps/sales/views/QuoteProposalCPQ/` | `CPQQuotes.py`, `CPQQuoteLines.py`, `ProductBundles.py`, `QuoteApprovalRules.py`, `QuoteOperations.py` |
| URLs folder | `apps/sales/urls/QuoteProposalCPQ/` | `CPQQuotes.py`, `CPQQuoteLines.py`, `ProductBundles.py`, `QuoteApprovalRules.py`, `QuoteOperations.py` |
| Template folder | `templates/sales/quote_proposal_cpq/` | `cpqquote/`, `cpqquoteline/`, `productbundleoption/`, `quoteapprovalrule/`, `operations/` |
| Service module | `apps/sales/cpq_services.py` | Core calculation, revision cloning, approval evaluation, order conversion |
| URL segment | `quotes/` | Top-level routes under `sales:` |
| Number prefixes | `CPQ-`, `BND-`, `QAR-` | Zero collisions across repo |

---

## 2. Models Contract

### 2.1 `CPQQuote` (`CPQ-`) — `apps/sales/models/QuoteProposalCPQ/CPQQuotes.py`
Inherits `TenantNumbered` (`NUMBER_PREFIX = "CPQ"`).

- **Fields:**
  - `name`: `CharField(max_length=255)`
  - `opportunity`: `ForeignKey("crm.Opportunity", on_delete=models.SET_NULL, null=True, blank=True, related_name="cpq_quotes")`
  - `account`: `ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="cpq_quotes")`
  - `contact`: `ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="cpq_contact_quotes")`
  - `price_book`: `ForeignKey("crm.PriceBook", on_delete=models.SET_NULL, null=True, blank=True, related_name="cpq_quotes")`
  - `currency`: `ForeignKey("accounting.Currency", on_delete=models.PROTECT, related_name="cpq_quotes")`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default="draft")`
    - `STATUS_CHOICES = [("draft", "Draft"), ("in_review", "Pending Approval"), ("approved", "Approved"), ("rejected", "Rejected"), ("presented", "Presented"), ("accepted", "Accepted"), ("declined", "Declined"), ("converted", "Converted to Order"), ("superseded", "Superseded"), ("expired", "Expired")]`
  - `approval_status`: `CharField(max_length=20, choices=APPROVAL_STATUS_CHOICES, default="not_required")`
    - `APPROVAL_STATUS_CHOICES = [("not_required", "Not Required"), ("pending", "Pending Approval"), ("approved", "Approved"), ("rejected", "Rejected")]`
  - `approval_rule`: `ForeignKey("sales.QuoteApprovalRule", on_delete=models.SET_NULL, null=True, blank=True, related_name="quotes")`
  - `approved_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_cpq_quotes")`
  - `approved_at`: `DateTimeField(null=True, blank=True)`
  - `approval_note`: `TextField(blank=True)`
  - `valid_until`: `DateField(null=True, blank=True)`
  - `quote_group_id`: `CharField(max_length=50, db_index=True)` (identifies family of revisions)
  - `revision_number`: `PositiveIntegerField(default=1)`
  - `revision_of`: `ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="revisions")`
  - `is_primary`: `BooleanField(default=False, help_text="Syncs with Opportunity amount and forecast")`
  - `header_discount_pct`: `DecimalField(max_digits=5, decimal_places=2, default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])`
  - `subtotal`: `DecimalField(max_digits=14, decimal_places=2, default=0, editable=False)`
  - `discount_total`: `DecimalField(max_digits=14, decimal_places=2, default=0, editable=False)`
  - `tax_total`: `DecimalField(max_digits=14, decimal_places=2, default=0, editable=False)`
  - `total`: `DecimalField(max_digits=14, decimal_places=2, default=0, editable=False)`
  - `cost_total`: `DecimalField(max_digits=14, decimal_places=2, default=0, editable=False)`
  - `margin_total`: `DecimalField(max_digits=14, decimal_places=2, default=0, editable=False)`
  - `margin_pct`: `DecimalField(max_digits=5, decimal_places=2, default=0, editable=False)`
  - `proposal_template`: `ForeignKey("crm.DocTemplate", on_delete=models.SET_NULL, null=True, blank=True, related_name="cpq_quotes")`
  - `proposal_rendered_content`: `TextField(blank=True, help_text="Rendered HTML snapshot for customer")`
  - `terms_and_conditions`: `TextField(blank=True)`
  - `notes`: `TextField(blank=True)`
  - `signing_token`: `CharField(max_length=64, unique=True, db_index=True, blank=True, editable=False)`
  - `signer_name`: `CharField(max_length=255, blank=True)`
  - `signer_title`: `CharField(max_length=120, blank=True)`
  - `signer_email`: `EmailField(blank=True)`
  - `signed_at`: `DateTimeField(null=True, blank=True)`
  - `signature_data`: `TextField(blank=True, help_text="Typed signature or SVG data")`
  - `converted_order`: `ForeignKey("scm.SalesOrder", on_delete=models.SET_NULL, null=True, blank=True, related_name="originating_cpq_quotes")`
  - `crm_quote`: `ForeignKey("crm.Quote", on_delete=models.SET_NULL, null=True, blank=True, related_name="cpq_quotes")`
  - `owner`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="cpq_owned_quotes")`
- **Properties & Methods:**
  - `is_editable`: returns `status in ["draft", "rejected"]`
  - `is_approved`: returns `approval_status == "approved" or approval_status == "not_required"`
  - `is_expired`: returns `bool(valid_until and valid_until < timezone.localdate() and status in ["draft", "in_review", "approved", "presented"])`
  - `can_convert`: returns `status in ["approved", "presented", "accepted"] and not converted_order`
  - `save()`: auto-generates `signing_token` via `uuid.uuid4().hex` if blank; handles `quote_group_id` default.

### 2.2 `CPQQuoteLine` — `apps/sales/models/QuoteProposalCPQ/CPQQuoteLines.py`
Inherits `TenantOwned` (`apps/sales/models/_base.py`).

- **Fields:**
  - `quote`: `ForeignKey("sales.CPQQuote", on_delete=models.CASCADE, related_name="lines")`
  - `parent_line`: `ForeignKey("self", on_delete=models.CASCADE, null=True, blank=True, related_name="bundle_children")`
  - `line_type`: `CharField(max_length=20, choices=LINE_TYPE_CHOICES, default="standard")`
    - `LINE_TYPE_CHOICES = [("standard", "Standard Item"), ("bundle_parent", "Bundle Package Header"), ("bundle_component", "Bundle Component"), ("optional_addon", "Optional Add-on")]`
  - `product`: `ForeignKey("crm.Product", on_delete=models.SET_NULL, null=True, blank=True, related_name="cpq_quote_lines")`
  - `item`: `ForeignKey("scm.Item", on_delete=models.SET_NULL, null=True, blank=True, related_name="cpq_quote_lines", help_text="Physical inventory SKU for stock reservation & order conversion")`
  - `uom`: `ForeignKey("scm.UOM", on_delete=models.SET_NULL, null=True, blank=True, related_name="cpq_quote_lines")`
  - `description`: `CharField(max_length=255)`
  - `quantity`: `DecimalField(max_digits=12, decimal_places=2, default=1, validators=[MinValueValidator(Decimal("0.01"))])`
  - `list_price`: `DecimalField(max_digits=14, decimal_places=2, default=0, validators=[MinValueValidator(0)])`
  - `discount_pct`: `DecimalField(max_digits=5, decimal_places=2, default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])`
  - `unit_price`: `DecimalField(max_digits=14, decimal_places=2, default=0, validators=[MinValueValidator(0)])`
  - `tax_code`: `ForeignKey("accounting.TaxCode", on_delete=models.SET_NULL, null=True, blank=True, related_name="cpq_quote_lines")`
  - `tax_pct`: `DecimalField(max_digits=5, decimal_places=2, default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])`
  - `unit_cost`: `DecimalField(max_digits=14, decimal_places=2, default=0, validators=[MinValueValidator(0)])`
  - `line_subtotal`: `DecimalField(max_digits=14, decimal_places=2, default=0, editable=False)`
  - `line_tax`: `DecimalField(max_digits=14, decimal_places=2, default=0, editable=False)`
  - `line_total`: `DecimalField(max_digits=14, decimal_places=2, default=0, editable=False)`
  - `line_cost`: `DecimalField(max_digits=14, decimal_places=2, default=0, editable=False)`
  - `line_margin`: `DecimalField(max_digits=14, decimal_places=2, default=0, editable=False)`
  - `margin_pct`: `DecimalField(max_digits=5, decimal_places=2, default=0, editable=False)`
  - `is_optional`: `BooleanField(default=False, help_text="Can be toggled by customer on portal")`
  - `is_selected`: `BooleanField(default=True, help_text="Included in quote pricing calculations")`
  - `sequence`: `PositiveIntegerField(default=10)`
- **Properties & Calculation:**
  - `recalculate()`: Updates `unit_price` from `list_price * (1 - discount_pct/100)` if not overridden, then computes `line_subtotal`, `line_tax`, `line_total`, `line_cost`, `line_margin`, and `margin_pct`.

### 2.3 `ProductBundleOption` (`BND-`) — `apps/sales/models/QuoteProposalCPQ/ProductBundles.py`
Inherits `TenantNumbered` (`NUMBER_PREFIX = "BND"`).

- **Fields:**
  - `name`: `CharField(max_length=255)`
  - `bundle_product`: `ForeignKey("crm.Product", on_delete=models.CASCADE, related_name="bundle_options", help_text="The parent bundle product")`
  - `component_product`: `ForeignKey("crm.Product", on_delete=models.CASCADE, related_name="component_in_bundles", help_text="The option product item")`
  - `component_item`: `ForeignKey("scm.Item", on_delete=models.SET_NULL, null=True, blank=True, related_name="component_in_bundles", help_text="Inventory SKU mapping")`
  - `option_group`: `CharField(max_length=50, default="Components", help_text="E.g., Hardware, Software, Support, Add-on")`
  - `is_required`: `BooleanField(default=False)`
  - `is_default`: `BooleanField(default=False)`
  - `min_quantity`: `DecimalField(max_digits=10, decimal_places=2, default=1, validators=[MinValueValidator(0)])`
  - `max_quantity`: `DecimalField(max_digits=10, decimal_places=2, default=10, validators=[MinValueValidator(0)])`
  - `default_quantity`: `DecimalField(max_digits=10, decimal_places=2, default=1, validators=[MinValueValidator(0)])`
  - `unit_price_override`: `DecimalField(max_digits=14, decimal_places=2, null=True, blank=True, help_text="Special bundle pricing if set")`
  - `discount_pct_override`: `DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(100)])`
  - `compatibility_rule`: `CharField(max_length=20, choices=COMPATIBILITY_CHOICES, default="none")`
    - `COMPATIBILITY_CHOICES = [("none", "None"), ("requires", "Requires"), ("excludes", "Mutually Exclusive With"), ("recommends", "Recommended With")]`
  - `depends_on_product`: `ForeignKey("crm.Product", on_delete=models.SET_NULL, null=True, blank=True, related_name="dependent_bundle_options")`
  - `sort_order`: `PositiveIntegerField(default=10)`
  - `is_active`: `BooleanField(default=True)`

### 2.4 `QuoteApprovalRule` (`QAR-`) — `apps/sales/models/QuoteProposalCPQ/QuoteApprovalRules.py`
Inherits `TenantNumbered` (`NUMBER_PREFIX = "QAR"`).

- **Fields:**
  - `name`: `CharField(max_length=255)`
  - `rule_type`: `CharField(max_length=25, choices=RULE_TYPE_CHOICES, default="max_discount")`
    - `RULE_TYPE_CHOICES = [("max_discount", "Max Discount %"), ("min_margin", "Minimum Margin %"), ("max_amount", "Max Total Amount"), ("composite", "Composite Discount & Margin")]`
  - `discount_threshold_pct`: `DecimalField(max_digits=5, decimal_places=2, default=20.00, validators=[MinValueValidator(0), MaxValueValidator(100)])`
  - `min_margin_pct`: `DecimalField(max_digits=5, decimal_places=2, default=15.00, validators=[MinValueValidator(0), MaxValueValidator(100)])`
  - `amount_threshold`: `DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)`
  - `approver_role`: `CharField(max_length=30, choices=APPROVER_ROLE_CHOICES, default="sales_manager")`
    - `APPROVER_ROLE_CHOICES = [("sales_manager", "Sales Manager"), ("sales_director", "Sales Director"), ("vp_sales", "VP of Sales"), ("finance_manager", "Finance Manager"), ("cfo", "Chief Financial Officer")]`
  - `auto_reject`: `BooleanField(default=False, help_text="Auto-reject without submission if thresholds violated severely")`
  - `priority`: `PositiveIntegerField(default=100, help_text="Evaluation order (lower evaluated first)")`
  - `is_active`: `BooleanField(default=True)`
  - `description`: `TextField(blank=True)`
- **Methods:**
  - `evaluate(quote)`: Returns `(triggered: bool, reason: str)`.

---

## 3. Forms Contract (`apps/sales/forms/QuoteProposalCPQ/`)

- Excluded from `CPQQuoteForm`: `tenant`, `number`, `quote_group_id`, `revision_number`, `revision_of`, `status`, `approval_status`, `approval_rule`, `approved_by`, `approved_at`, `approval_note`, `subtotal`, `discount_total`, `tax_total`, `total`, `cost_total`, `margin_total`, `margin_pct`, `proposal_rendered_content`, `signing_token`, `signer_name`, `signer_title`, `signer_email`, `signed_at`, `signature_data`, `converted_order`, `crm_quote`, `owner`.
- `CPQQuoteLineForm`: Excludes `tenant`, `quote`, `line_subtotal`, `line_tax`, `line_total`, `line_cost`, `line_margin`, `margin_pct`.
- `ProductBundleOptionForm`: Excludes `tenant`, `number`.
- `QuoteApprovalRuleForm`: Excludes `tenant`, `number`.
- `QuoteApprovalActionForm`: Fields `action` (choices: `approved`, `rejected`), `note` (required on rejection).
- `PortalSignForm`: Fields `signer_name`, `signer_title`, `signer_email`, `signature_data`, `agree_terms`.
- `GuidedSellingForm`: Fields `opportunity`, `bundle_product`, `selected_components`, `quantities`.

---

## 4. Views and Context Keys Contract

### 4.1 CPQ Quotes (`CPQQuotes.py`)
- `cpq_quote_list`:
  - Context keys: `quotes` (page obj), `status_choices`, `approval_status_choices`, `opportunities`, `stats` (`total`, `draft`, `pending_approval`, `approved`, `presented`, `accepted`, `converted`), `currency_symbols`.
  - Filters: `q` (search), `status`, `approval_status`, `opportunity`, `is_primary`.
- `cpq_quote_create`:
  - Context keys: `form`, `opportunity_list`, `price_books`, `currencies`.
- `cpq_quote_detail`:
  - Context keys: `quote`, `lines`, `bundle_groups`, `revisions`, `approval_history`, `audit_logs`, `can_edit`, `can_approve`, `can_convert`.
- `cpq_quote_edit`:
  - Context keys: `form`, `quote`.
- `cpq_quote_delete`: POST only, redirects to `sales:cpq_quote_list`.

### 4.2 CPQ Quote Lines (`CPQQuoteLines.py`)
- `cpq_quote_line_list`:
  - Context keys: `quote`, `lines`, `stats`.
- `cpq_quote_line_create`:
  - Context keys: `form`, `quote`, `bundle_options`.
- `cpq_quote_line_edit`:
  - Context keys: `form`, `quote`, `line`.
- `cpq_quote_line_delete`: POST only.

### 4.3 Product Bundle Options (`ProductBundles.py`)
- `product_bundle_list`:
  - Context keys: `bundles`, `bundle_products`, `stats`.
- `product_bundle_create`:
  - Context keys: `form`.
- `product_bundle_detail`:
  - Context keys: `bundle`, `options`.
- `product_bundle_edit`:
  - Context keys: `form`, `bundle`.
- `product_bundle_delete`: POST only.

### 4.4 Quote Approval Rules (`QuoteApprovalRules.py`)
- `quote_approval_rule_list`:
  - Context keys: `rules`, `rule_type_choices`, `approver_role_choices`, `stats`.
- `quote_approval_rule_create`:
  - Context keys: `form`.
- `quote_approval_rule_detail`:
  - Context keys: `rule`.
- `quote_approval_rule_edit`:
  - Context keys: `form`, `rule`.
- `quote_approval_rule_delete`: POST only.

### 4.5 Dedicated Operations (`QuoteOperations.py`)
- `quote_submit_approval`: Evaluates rules and transitions quote to `in_review` or `approved`.
- `quote_approval_queue`: Manager review dashboard (`pending_quotes`, `stats`).
- `quote_approval_action`: Approve/reject with comments.
- `quote_create_revision`: Clones quote to next revision (`rev+1`, sets old to `superseded`).
- `quote_compare_versions`: Side-by-side diff (`quote_a`, `quote_b`, `diff_lines`, `metric_deltas`).
- `quote_version_list`: Register of revision families (`quote_families`, `stats`).
- `quote_proposal_board`: Proposals register and generator (`quotes`, `templates`, `stats`).
- `quote_generate_proposal`: Renders branded HTML and generates customer signing link.
- `quote_portal_view`: Public view via `signing_token` (interactive options, e-signature).
- `quote_portal_sign`: Public POST endpoint to sign/accept quote.
- `quote_conversion_board`: Ready-to-convert approved quotes (`convertible_quotes`, `converted_quotes`).
- `quote_convert_to_order`: 1-click execution creating `scm.SalesOrder` and allocating lines.
- `cpq_guided_selling`: Interactive bundle builder wizard.

---

## 5. URLconf Hierarchy (`apps/sales/urls/QuoteProposalCPQ/`)

- `quotes/` -> `cpq_quote_list`
- `quotes/create/` -> `cpq_quote_create`
- `quotes/approval-queue/` -> `quote_approval_queue`
- `quotes/versions/` -> `quote_version_list`
- `quotes/compare/<int:pk_a>/<int:pk_b>/` -> `quote_compare_versions`
- `quotes/proposals/` -> `quote_proposal_board`
- `quotes/conversions/` -> `quote_conversion_board`
- `quotes/guided-selling/` -> `cpq_guided_selling`
- `quotes/portal/<str:token>/` -> `quote_portal_view`
- `quotes/portal/<str:token>/sign/` -> `quote_portal_sign`
- `quotes/<int:pk>/` -> `cpq_quote_detail`
- `quotes/<int:pk>/edit/` -> `cpq_quote_edit`
- `quotes/<int:pk>/delete/` -> `cpq_quote_delete`
- `quotes/<int:pk>/submit-approval/` -> `quote_submit_approval`
- `quotes/<int:pk>/approval-action/` -> `quote_approval_action`
- `quotes/<int:pk>/create-revision/` -> `quote_create_revision`
- `quotes/<int:pk>/generate-proposal/` -> `quote_generate_proposal`
- `quotes/<int:pk>/convert-order/` -> `quote_convert_to_order`
- `quotes/<int:quote_pk>/lines/` -> `cpq_quote_line_list`
- `quotes/<int:quote_pk>/lines/create/` -> `cpq_quote_line_create`
- `quotes/<int:quote_pk>/lines/<int:pk>/edit/` -> `cpq_quote_line_edit`
- `quotes/<int:quote_pk>/lines/<int:pk>/delete/` -> `cpq_quote_line_delete`
- `bundles/` -> `product_bundle_list`
- `bundles/create/` -> `product_bundle_create`
- `bundles/<int:pk>/` -> `product_bundle_detail`
- `bundles/<int:pk>/edit/` -> `product_bundle_edit`
- `bundles/<int:pk>/delete/` -> `product_bundle_delete`
- `approval-rules/` -> `quote_approval_rule_list`
- `approval-rules/create/` -> `quote_approval_rule_create`
- `approval-rules/<int:pk>/` -> `quote_approval_rule_detail`
- `approval-rules/<int:pk>/edit/` -> `quote_approval_rule_edit`
- `approval-rules/<int:pk>/delete/` -> `quote_approval_rule_delete`

---

## 6. Navigation Wire-Up (`apps/core/navigation.py`)

`LIVE_LINKS["8.5"]` mapping all 5 NavERP.md §8.5 bullets:
```python
"8.5": {
    "Quote Configuration (CPQ)": "sales:cpq_quote_list",
    "Pricing & Discount Approval": "sales:quote_approval_queue",
    "Proposal Generation & Templating": "sales:quote_proposal_board",
    "Quote Versioning & Comparison": "sales:quote_version_list",
    "Quote-to-Order Conversion": "sales:quote_conversion_board",
},
```
Secondary staff links added:
- `"Product Bundle Options"`: `"sales:product_bundle_list"`
- `"Quote Approval Rules"`: `"sales:quote_approval_rule_list"`
- `"CPQ Guided Selling"`: `"sales:cpq_guided_selling"`

---

## 7. Templates List (`templates/sales/quote_proposal_cpq/`)

1. `cpqquote/list.html`: Quotes register with metrics, filters, and actions.
2. `cpqquote/detail.html`: Comprehensive quote workspace with line items table, approval status, proposal preview, revision timeline, and conversion buttons.
3. `cpqquote/form.html`: Quote creation and header editing form.
4. `cpqquoteline/list.html`: Line items register.
5. `cpqquoteline/detail.html`: Line item detail view.
6. `cpqquoteline/form.html`: Line item add/edit form with bundle option selector.
7. `productbundleoption/list.html`: Bundle rules register.
8. `productbundleoption/detail.html`: Bundle rule configuration detail.
9. `productbundleoption/form.html`: Bundle rule create/edit form.
10. `quoteapprovalrule/list.html`: Approval rules register.
11. `quoteapprovalrule/detail.html`: Approval rule detail.
12. `quoteapprovalrule/form.html`: Approval rule create/edit form.
13. `operations/proposal_preview.html`: Branded quote presentation document.
14. `operations/portal.html`: Public customer acceptance portal with interactive line toggles and e-signature.
15. `operations/compare.html`: Side-by-side quote version comparison diff.
16. `operations/approval_queue.html`: Manager approval workbench.
17. `operations/conversion_board.html`: Quote-to-sales-order handoff and conversion board.
18. `operations/guided_selling.html`: Interactive CPQ guided selling questionnaire.

---

## 8. Verification Strategy

1. `manage.py makemigrations sales` -> produces `0008_...`.
2. `manage.py migrate` -> cleanly applies to `nav_erp`.
3. `manage.py seed_sales` x 2 -> ensures idempotent execution.
4. `manage.py check` -> 0 warnings/errors.
5. Smoke test:
   - Authenticated tenant admin access across all 8.5 routes returns 200.
   - Public customer portal route `/sales/quotes/portal/<token>/` returns 200 without authentication.
   - Cross-tenant IDOR returns 404.
   - Primary quote toggle updates opportunity total.
   - Version cloning increments revision number and retains group.
   - Order conversion creates valid `scm.SalesOrder` and prevents re-conversion.
