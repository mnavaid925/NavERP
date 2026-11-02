# Review Findings — eCommerce 9.17: B2B & Wholesale Commerce

Base ref: `8b479df7493e3dc3541346365f5619fef4714082`
Head: `HEAD`

---

## Executive Summary
Six specialized reviewers (`code-reviewer`, `explorer`, `frontend-reviewer`, `performance-reviewer`, `qa-smoke-tester`, `security-reviewer`) conducted an in-depth review of Sub-module 9.17: B2B & Wholesale Commerce across models, forms, views, URLs, navigation, seeder, and 14 templates.
All six passes were executed strictly serially. The review identified **8 Critical**, **15 Important**, and **10 Minor** findings.
The deduplicated and prioritized findings below are structured for resolution by the `code-fixer` agent in Phase 5.

---

## Critical Findings

- [x] **C1** — `NoReverseMatch` 500 crash in Quote Detail template on converted orders — 548f1c06
  - *Location*: `templates/ecommerce/b2b_wholesale/b2b_quote_request/detail.html:37`
  - *Problem*: Template uses `{% url 'ecommerce:order_detail' quote_request.converted_order.pk %}`. The URL pattern in `apps/ecommerce/urls/OrderManagement/EcommerceOrders.py:8` is named `ecommerceorder_detail`. Causes fatal 500 when viewing converted quotes.
  - *Fix*: Update to `{% url 'ecommerce:ecommerceorder_detail' quote_request.converted_order.pk %}`.

- [ ] **C2** — `write_audit_log` signature mismatch causes 500 on all form POST & action endpoints
  - *Location*: 15 call sites across `apps/ecommerce/views/B2bWholesale/B2bCompanyAccounts.py`, `B2bCompanyUsers.py`, `B2bQuoteRequests.py`, `B2bQuickOrderTemplates.py`
  - *Problem*: Views call `write_audit_log(request, "action", "...", object_id=...)` with invalid kwargs. Authoritative signature in `apps/core/utils.py` is `write_audit_log(user, obj, action, changes=None, tenant=None)`. Every POST submission crashes with 500.
  - *Fix*: Correct all 15 calls to `write_audit_log(request.user, obj, "action", {"number": obj.number}, tenant=request.tenant)`.

- [ ] **C3** — `EcommerceOrder.objects.create()` kwargs mismatch (`subtotal` vs `subtotal_amount`) and missing required shipping address fields
  - *Location*: `apps/ecommerce/views/B2bWholesale/B2bQuoteRequests.py:360-372`
  - *Problem*: `subtotal` raises `TypeError: unexpected keyword argument 'subtotal'`. The model field is `subtotal_amount`. Non-nullable address fields (`shipping_name`, `shipping_address_line1`, `shipping_city`, `shipping_postal_code`, `shipping_country`) have no defaults and trigger IntegrityError.
  - *Fix*: Rename `subtotal` to `subtotal_amount` and provide fallback shipping address fields.

- [ ] **C4** — Mass assignment of workflow-controlled `status` and financial totals in `B2bQuoteRequestForm`
  - *Location*: `apps/ecommerce/forms/B2bWholesale/B2bQuoteRequests.py:14-24`
  - *Problem*: `status`, `original_subtotal`, `quoted_discount_percent`, `quoted_total` are not excluded and are rendered as editable form inputs, allowing buyers to bypass sales review and set arbitrary pricing.
  - *Fix*: Add `status`, `original_subtotal`, `quoted_discount_percent`, `quoted_total` to `Meta.exclude` in `B2bQuoteRequestForm`.

- [ ] **C5** — Unhandled `decimal.InvalidOperation` 500 crash, non-finite values, and negative quote totals (L35)
  - *Location*: `apps/ecommerce/views/B2bWholesale/B2bQuoteRequests.py:141-152, 214-225, 306`
  - *Problem*: Raw `Decimal()` casting on discount and prices without catching `decimal.InvalidOperation`, checking `is_finite()`, non-negativity, or bounds.
  - *Fix*: Validate `decimal.InvalidOperation`, ensure finite and non-negative, and clamp discounts to `0 <= val <= 100`.

- [ ] **C6** — Plaintext secret exposure of `punchout_shared_secret` in form and DOM (L20)
  - *Location*: `apps/ecommerce/forms/B2bWholesale/B2bCompanyAccounts.py:34`
  - *Problem*: Rendered as `TextInput`, exposing plaintext secret in DOM attributes and browser inspection.
  - *Fix*: Use `forms.PasswordInput(render_value=False)` and retain existing secret on blank edit in `clean_punchout_shared_secret()`.

- [ ] **C7** — Nullable ForeignKeys in template filter arguments cause 500 crashes on unassigned quotes and templates (L10)
  - *Location*: `templates/ecommerce/b2b_wholesale/b2b_quote_request/detail.html:121, 128`, `list.html:153`, `b2b_company_account/detail.html:354`, `b2b_quick_order_template/detail.html:88`
  - *Problem*: `requested_by.get_full_name|default:requested_by.username` raises `VariableDoesNotExist` 500 when `requested_by`, `assigned_sales_rep`, or `created_by` is None.
  - *Fix*: Wrap all with explicit `{% if obj.fk %}...{% else %}...{% endif %}` guards.

- [ ] **C8** — N+1 query loops in Quick Order matrix, CSV upload parsing, and quote/template line item processing
  - *Location*: `apps/ecommerce/views/B2bWholesale/B2bQuickOrderTemplates.py:284-375`, `B2bQuoteRequests.py:136, 209, 377`
  - *Problem*: Sequential DB queries per row in loops inside `b2b_quick_order_matrix`, `b2bquoterequest_create/edit/convert`, and `b2bquickordertemplate_create/edit`.
  - *Fix*: Collect SKUs / IDs upfront and batch fetch using `sku__in` / `pk__in` with in-memory dictionary lookup.

---

## Important Findings

- [ ] **I1** — Unhandled `ValueError` 500 crash on non-numeric `?company=` query parameter
  - *Location*: `apps/ecommerce/views/B2bWholesale/B2bCompanyUsers.py:46`, `B2bQuoteRequests.py:58`, `B2bQuickOrderTemplates.py:62`
  - *Problem*: Passing non-numeric `?company=xyz` causes unhandled `ValueError` when Django coerces FK id.
  - *Fix*: Guard with `selected_company.isdigit()`.

- [ ] **I2** — Missing state machine guards on quote conversion and state transitions (`accept`, `reject`, `convert_order`)
  - *Location*: `apps/ecommerce/views/B2bWholesale/B2bQuoteRequests.py:324, 338, 354`
  - *Problem*: Non-accepted or draft quotes can be converted to orders; quotes in terminal states can be accepted or rejected.
  - *Fix*: Enforce `quote.status == "accepted"` for conversion and `quote.status in ["quoted", "buyer_review"]` for accept/reject.

- [ ] **I3** — Approver cross-company leakage & missing `reject_foreign` in `B2bCompanyUserForm`
  - *Location*: `apps/ecommerce/forms/B2bWholesale/B2bCompanyUsers.py:59`
  - *Problem*: `reports_to_approver` missing from `reject_foreign`, and no validation check that approver belongs to the same company.
  - *Fix*: Add to `reject_foreign` and validate `approver.company_id == company.id` and `approver.pk != self.instance.pk`.

- [ ] **I4** — Concurrency race condition on available credit limit deduction
  - *Location*: `apps/ecommerce/views/B2bWholesale/B2bQuoteRequests.py:394-398`
  - *Problem*: `available_credit` is read and updated without row-level locking.
  - *Fix*: Use `select_for_update()` inside `transaction.atomic()`.

- [ ] **I5** — Missing `@require_POST` decorator on delete views
  - *Location*: All 4 delete views in `B2bCompanyAccounts.py`, `B2bCompanyUsers.py`, `B2bQuoteRequests.py`, `B2bQuickOrderTemplates.py`
  - *Problem*: Delete endpoints accept GET requests instead of strictly requiring POST.
  - *Fix*: Decorate with `@require_POST`.

- [ ] **I6** — Missing chained relation `reports_to_approver__user` in `B2bCompanyUser` views
  - *Location*: `apps/ecommerce/views/B2bWholesale/B2bCompanyUsers.py:19, 85`
  - *Problem*: Template accesses `cu.reports_to_approver.user`, triggering N queries to `auth_user`.
  - *Fix*: Add `select_related("reports_to_approver__user")`.

- [ ] **I7** — Chained N+1 via `B2bCompanyUser.__str__` in form approver dropdown
  - *Location*: `apps/ecommerce/forms/B2bWholesale/B2bCompanyUsers.py:39-42`
  - *Problem*: Form dropdown queryset lacks `select_related("user", "company")`.
  - *Fix*: Add `.select_related("user", "company")`.

- [ ] **I8** — Prefetched cache bypassed via `.first()` in `_prepare_product_choices`
  - *Location*: `apps/ecommerce/views/B2bWholesale/B2bQuoteRequests.py:30`, `B2bQuickOrderTemplates.py:30`
  - *Problem*: `.variants.first()` executes a new SQL query per product instead of reading prefetch cache.
  - *Fix*: Read from `p.variants.all()` list.

- [ ] **I9** — Missing composite indexes on `(tenant, -created_at)` and `(tenant, company, status)`
  - *Location*: `apps/ecommerce/models/B2bWholesale/` across all 4 models
  - *Problem*: Hot list queries and cockpits lack composite indexes on tenant ordering and status filtering.
  - *Fix*: Add composite indexes with migration.

- [ ] **I10** — Non-positive and unbounded quantities accepted in Quick Order Matrix and CSV upload (L35)
  - *Location*: `apps/ecommerce/views/B2bWholesale/B2bQuickOrderTemplates.py:143, 204, 288, 344`
  - *Problem*: Negative or zero quantities can produce negative subtotals.
  - *Fix*: Enforce `1 <= qty <= 100000`.

- [ ] **I11** — Non-existent product attributes in quote edit template
  - *Location*: `templates/ecommerce/b2b_wholesale/b2b_quote_request/form.html:123-124`
  - *Problem*: Uses `prod.retail_price` and `prod.sku` in edit loop, rendering blank.
  - *Fix*: Use `prod.display_price` and `prod.display_sku`.

- [ ] **I12** — Unrendered context variable `quick_order_templates` in Company Account detail
  - *Location*: `templates/ecommerce/b2b_wholesale/b2b_company_account/detail.html`
  - *Problem*: Context variable passed by view is omitted from detail template.
  - *Fix*: Render saved templates section in company detail page.

- [ ] **I13** — Unlabeled file and text inputs in Quick Order Matrix and interactive forms (WCAG A11y)
  - *Location*: `templates/ecommerce/b2b_wholesale/b2b_quick_order_template/quick_order_matrix.html`, `b2b_quote_request/detail.html`
  - *Problem*: Inputs lack `<label>` or `aria-label`.
  - *Fix*: Add appropriate `aria-label` and `label for` attributes.

- [ ] **I14** — Navigation target collisions in `LIVE_LINKS["9.17"]`
  - *Location*: `apps/core/navigation.py:2836-2848`
  - *Problem*: Duplicate destinations for sidebar items; Bulk Ordering links to templates instead of matrix.
  - *Fix*: Point "Bulk Ordering & Quick Order" to `ecommerce:b2b_quick_order_matrix` and differentiate query params.

- [ ] **I15** — Available credit frozen at 0 if credit limit was originally 0
  - *Location*: `apps/ecommerce/models/B2bWholesale/B2bCompanyAccounts.py:197-201`
  - *Problem*: When account is registered with limit 0, later edit does not initialize available credit.
  - *Fix*: Initialize available credit if previously 0 and limit increased.

---

## Minor Findings

- [ ] **M1** — Arbitrary product fallback on missing line item products in order conversion
  - *Location*: `apps/ecommerce/views/B2bWholesale/B2bQuoteRequests.py:377-380`
  - *Problem*: If product not found, falls back to first arbitrary product in tenant catalog.
  - *Fix*: Skip item with a warning message instead of assigning a random product.

- [ ] **M2** — Non-standard badge CSS classes across templates
  - *Location*: Various templates in `templates/ecommerce/b2b_wholesale/`
  - *Problem*: `badge-info` and `badge-muted` used instead of standard color-named classes.
  - *Fix*: Standardize to `badge-blue` and `badge-slate`.

- [ ] **M3** — Seeder volume drift from Contract Section 5
  - *Location*: `apps/ecommerce/management/commands/seed_ecommerce.py:3659-3753`
  - *Problem*: Contract specifies 3 users, 2 quote requests, 2 templates; currently seeds 1 of each.
  - *Fix*: Expand seeder to match all contract rows.

- [ ] **M4** — Subtotal overwriting when line items data is empty in `recalculate_totals()`
  - *Location*: `apps/ecommerce/models/B2bWholesale/B2bQuoteRequests.py:167-174`
  - *Problem*: Ad-hoc budget quotes without structured items have their subtotal zeroed.
  - *Fix*: Only recalculate subtotal if `self.line_items_data` is non-empty.

- [ ] **M5** — Quick Order Matrix lacks CTA button to transfer parsed items to cart/order
  - *Location*: `templates/ecommerce/b2b_wholesale/b2b_quick_order_template/quick_order_matrix.html:128-132`
  - *Problem*: Parsed matrix items have no CTA to proceed to cart.
  - *Fix*: Add "Proceed to Cart" action button.

- [ ] **M6** — Unescaped single quotes in JavaScript delete confirmation prompts
  - *Location*: `templates/ecommerce/b2b_company_account/list.html:218`, `b2b_company_user/list.html:192`
  - *Problem*: Direct interpolation of company/user names breaks JS syntax if apostrophe is present.
  - *Fix*: Filter through `|escapejs`.

- [ ] **M7** — Quick Order manual entry missing failed SKU visual row in preview table
  - *Location*: `apps/ecommerce/views/B2bWholesale/B2bQuickOrderTemplates.py:375`
  - *Problem*: Unrecognized manual SKUs only appear in error messages, not in preview table with `found=False`.
  - *Fix*: Add to `parsed_items` with `found=False`.

- [ ] **M8** — Redundant SQL `COUNT(*)` in Company Account Detail template
  - *Location*: `templates/ecommerce/b2b_wholesale/b2b_company_account/detail.html:241`
  - *Problem*: Evaluates `company_users.count` immediately before loop.
  - *Fix*: Use `company_users|length`.

- [ ] **M9** — Whole-model column loading in company filter dropdowns
  - *Location*: `apps/ecommerce/views/B2bWholesale/` list views
  - *Problem*: Loads all columns when template only needs `id` and `company_name`.
  - *Fix*: Add `.only("id", "company_name")`.

- [ ] **M10** — Rejection reason length unconstrained
  - *Location*: `apps/ecommerce/views/B2bWholesale/B2bQuoteRequests.py:338`
  - *Problem*: `rejection_reason` from POST is unconstrained.
  - *Fix*: Truncate to 1000 characters.
