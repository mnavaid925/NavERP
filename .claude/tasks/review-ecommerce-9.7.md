# Review Findings — Sub-module 9.7: Search & Product Discovery (Module 9: eCommerce Management System, `ecommerce`)

- **Sub-module:** 9.7 Search & Product Discovery
- **Module:** 9 eCommerce Management System
- **App:** `apps/ecommerce`
- **Date:** 2026-10-30
- **Changeset:** `a9a5b9525739bf487ce81e8eb50a9792c910da1d` (BASE) ... `HEAD`
- **Review Passes:**
  1. `code-reviewer` — Completed
  2. `explorer` — Completed
  3. `frontend-reviewer` — Completed
  4. `performance-reviewer` — Completed
  5. `qa-smoke-tester` — Completed (66/66 checks passed)
  6. `security-reviewer` — Completed

---

## Consolidated & Prioritized Findings for Phase 5 (`code-fixer`)

### Critical Findings

- [ ] **C1** — Broken Facet Checkbox State in Search Console Template
  - **Location:** `templates/ecommerce/searchdiscovery/console/console.html:230` and `apps/ecommerce/views/SearchDiscovery/SearchConsole.py:173-210`
  - **Description:** `{% if active_filters|dictsort:fg.config.code %}checked{% endif %}` fails silently because `dictsort` expects a sequence of dictionaries, not a dictionary. Checkboxes for active facet filters never render checked.
  - **Fix:** In `SearchConsole.py`, annotate each item in `facet_groups` with `"is_selected": (active_filters.get(fc.code) == str(itm["value"]))`. In `console.html:230`, change the condition to `{% if itm.is_selected %}checked{% endif %}`.

- [ ] **C2** — Invalid Attribute `product.category` in Search Console Grid
  - **Location:** `templates/ecommerce/searchdiscovery/console/console.html:291-293`
  - **Description:** `CatalogProduct` has `primary_category`, not `category`. Product category tags in workbench grid evaluate to None.
  - **Fix:** In `console.html:291-293`, use `{{ product.primary_category.name }}` (with `{{ product.category.name }}` fallback).

- [ ] **C3** — Database Duplication & PostgreSQL Incompatibility in Price Sorting
  - **Location:** `apps/ecommerce/views/SearchDiscovery/SearchConsole.py:252-259`
  - **Description:** Ordering `base_qs` via `order_by("variants__price").distinct()[:100]` performs an SQL `INNER JOIN` against reverse FK `ProductVariant`. Multi-variant products duplicate rows, and `SELECT DISTINCT` with `ORDER BY` on an unselected joined column fails on PostgreSQL.
  - **Fix:** Annotate `base_qs = base_qs.annotate(min_price=Min("variants__price"))` before ordering by `min_price` (for `price_asc`) or `-min_price` (for `price_desc`).

- [ ] **C4** — Duplicate Search Query Log Created on Redirect Intercepts
  - **Location:** `apps/ecommerce/views/SearchDiscovery/SearchConsole.py:67-77, 296-309`
  - **Description:** When a redirect rule is matched in workbench view without `auto_redirect=1`, a query log is created at line 77, and then another query log is created at line 309 for the same request.
  - **Fix:** Add a flag or skip the second `SearchQueryLog.objects.create` if a log was already written for this search request.

- [ ] **C5** — Merchandising Campaign Schedules Ignored in Rule Evaluation
  - **Location:** `apps/ecommerce/views/SearchDiscovery/SearchConsole.py:48-61, 213-246`
  - **Description:** Active date bounds (`start_date`, `end_date`) are omitted from merchandising rule queries, executing expired or future campaign rules.
  - **Fix:** Filter active rules with `(Q(start_date__isnull=True) | Q(start_date__lte=now)) & (Q(end_date__isnull=True) | Q(end_date__gte=now))`.

- [ ] **C6** — Open Redirect via Unvalidated Merchandising Query Forwarding
  - **Location:** `apps/ecommerce/views/SearchDiscovery/SearchConsole.py:79-80`
  - **Description:** When `auto_redirect=1` is passed, `search_console` performs an immediate redirect to `redirect_url` without verifying that the destination host and scheme are safe via `url_has_allowed_host_and_scheme`.
  - **Fix:** Validate `redirect_url` with `url_has_allowed_host_and_scheme(url=redirect_url, allowed_hosts={request.get_host()}, require_https=request.is_secure())` before redirecting.

- [ ] **C7** — Stored XSS via Dangerous URI Schemes in Merchandising URLs
  - **Location:** `apps/ecommerce/models/SearchDiscovery/SearchMerchandisingRules.py:157-162`
  - **Description:** `redirect_url` and `banner_link_url` accept arbitrary string inputs without scheme validation, allowing `javascript:` URI payloads to be persisted and executed when clicked.
  - **Fix:** In `SearchMerchandisingRule.clean()`, validate that URLs do not start with `javascript:`, `data:`, or `vbscript:` and only use HTTP, HTTPS, or relative paths.

---

### Important Findings

- [ ] **I1** — Missing Multi-Tenant Foreign Key Scoping in Model `clean()` Methods
  - **Location:** `apps/ecommerce/models/SearchDiscovery/SearchFacetConfigs.py:107-114`, `SearchMerchandisingRules.py:142-164`, `SearchQueryLogs.py:105-111`
  - **Description:** Model `clean()` methods omit tenant validation for related foreign keys (`category_scope`, `target_category`, `boosted_product`, `customer`, `clicked_product`).
  - **Fix:** Assert `self.category_scope.tenant_id == self.tenant_id`, `self.target_category.tenant_id == self.tenant_id`, `self.boosted_product.tenant_id == self.tenant_id`, `self.customer.tenant_id == self.tenant_id`, and `self.clicked_product.tenant_id == self.tenant_id`.

- [ ] **I2** — N+1 Queries on Pinned Merchandising Products in `search_console`
  - **Location:** `apps/ecommerce/views/SearchDiscovery/SearchConsole.py:213-215, 241`
  - **Description:** `active_rules` query does not select or prefetch related product details, triggering N+1 queries when accessing `sku` and `base_price` on pinned items.
  - **Fix:** Add `.select_related("boosted_product__item", "boosted_product__primary_category").prefetch_related("boosted_product__variants")` to `active_rules`.

- [ ] **I3** — N+1 Queries on Fallback Product Recommendations
  - **Location:** `apps/ecommerce/views/SearchDiscovery/SearchConsole.py:288-294`
  - **Description:** `fallback_recommendations` lacks prefetching on `item`, `primary_category`, and `variants`, causing up to 8 additional database queries on every zero-result search.
  - **Fix:** Add `.select_related("item", "primary_category").prefetch_related("variants")` to `fallback_recommendations`.

- [ ] **I4** — Variant Option Facets Silently Excluded from Facet Groups
  - **Location:** `apps/ecommerce/views/SearchDiscovery/SearchConsole.py:173-206`
  - **Description:** `facet_groups` logic only handles `category` and `brand`, silently skipping facet configs where `source_type == "variant_option"`.
  - **Fix:** Extract variant option values/counts from `ProductVariant.options` for products matching the current query.

- [ ] **I5** — Inactive / Archived Products Inserted via Pin Rules
  - **Location:** `apps/ecommerce/views/SearchDiscovery/SearchConsole.py:272-282`
  - **Description:** Pinned products are inserted into search results without validating `pinned_prod.status == "active"`.
  - **Fix:** Check `if pinned_prod and pinned_prod.status == "active":` before inserting into `product_list`.

- [ ] **I6** — Cross-Tenant Customer Party Leakage in Search Query Telemetry
  - **Location:** `apps/ecommerce/views/SearchDiscovery/SearchConsole.py:307`
  - **Description:** `getattr(request.user, "party", None)` is assigned without verifying `party.tenant_id == tenant.pk`.
  - **Fix:** Check `customer_party = getattr(request.user, "party", None)` and ensure `customer_party.tenant_id == tenant.pk` before setting.

- [ ] **I7** — Unhandled Special Decimal Literals (`NaN` / `Infinity`) in Price Filters
  - **Location:** `apps/ecommerce/views/SearchDiscovery/SearchConsole.py:148-163`
  - **Description:** `Decimal(price_min)` does not raise `ValueError` on `"NaN"` or `"Infinity"`, causing driver exceptions when querying.
  - **Fix:** Verify `min_val.is_finite() and min_val >= Decimal("0")`.

- [ ] **I8** — Full-Table Scan & Per-Item `UPDATE` Queries in Synonym Loop
  - **Location:** `apps/ecommerce/views/SearchDiscovery/SearchConsole.py:93-117`
  - **Description:** Active synonyms are scanned in Python and updated row-by-row in an unbatched loop.
  - **Fix:** Filter active synonyms in SQL using `Q(root_term=norm_q) | Q(synonyms__icontains=norm_q)` and batch `hit_count` updates outside the loop with `.filter(id__in=matched_ids).update(hit_count=F("hit_count") + 1)`.

- [ ] **I9** — Redundant Category Count Aggregation in Facet Loop Discarded by Template
  - **Location:** `apps/ecommerce/views/SearchDiscovery/SearchConsole.py:178-206`
  - **Description:** Template explicitly ignores category facet groups because categories are rendered independently, but the view executes an expensive category aggregation query anyway.
  - **Fix:** Skip querying category counts in `facet_groups` if `fc.source_type == "category"`.

- [ ] **I10** — Multiple Table Scans in `search_analytics` Dashboard
  - **Location:** `apps/ecommerce/views/SearchDiscovery/SearchConsole.py:415-426`
  - **Description:** `search_analytics` runs 3 distinct queries for total searches, zero-result searches, and avg latency.
  - **Fix:** Consolidate into a single query using conditional aggregation: `logs_qs.aggregate(total=Count("id"), zero_results=Count("id", filter=Q(is_zero_result=True)), avg_latency=Avg("execution_time_ms"))`.

- [ ] **I11** — Missing Contract-Pinned `sort_choices` Entry in Search Console
  - **Location:** `apps/ecommerce/views/SearchDiscovery/SearchConsole.py:33-38`
  - **Description:** Contract specifies `('rating', 'Customer Rating')` in `sort_choices`, but it is missing from `sort_choices` in the view.
  - **Fix:** Add `("rating", "Customer Rating")` to `sort_choices`.

- [ ] **I12** — HTML5 `datetime-local` Format Missing on Edit Forms
  - **Location:** `apps/ecommerce/forms/SearchDiscovery/SearchMerchandisingRules.py:48-49`
  - **Description:** `start_date` and `end_date` widgets lack `format="%Y-%m-%dT%H:%M"`, causing them to render blank when editing existing records.
  - **Fix:** Add `format="%Y-%m-%dT%H:%M"` to both `DateTimeInput` widgets.

- [ ] **I13** — None-Safe Display for Nullable Foreign Keys in Merchandising Templates
  - **Location:** `templates/ecommerce/searchdiscovery/merchandisingrule/list.html:125, 147-155` and `detail.html:84`
  - **Description:** `rule.target_category.name` and `rule.boosted_product.name` are accessed directly without `|default:"—"` when null.
  - **Fix:** Add `|default:"—"` or `{% if %}` checks around nullable category and product names.

---

### Minor Findings

- [ ] **M1** — Protocol-Relative URL Bypass in Merchandising Form
  - **Location:** `apps/ecommerce/forms/SearchDiscovery/SearchMerchandisingRules.py:65-69`
  - **Description:** `redirect_url` allows protocol-relative strings (`//evil.com`).
  - **Fix:** Disallow URLs starting with `//` in `clean_redirect_url`.

- [ ] **M2** — Unbounded Search Query String Length
  - **Location:** `apps/ecommerce/views/SearchDiscovery/SearchConsole.py:25, 337`
  - **Description:** Unbounded query string lengths can cause high CPU/memory consumption.
  - **Fix:** Cap search query length at 200 characters: `q = request.GET.get("q", "").strip()[:200]`.

- [ ] **M3** — Missing Nested `select_related` on Product Item in Merchandising Rule Detail
  - **Location:** `apps/ecommerce/views/SearchDiscovery/SearchMerchandisingRules.py:69-78`
  - **Description:** Detail view selects `boosted_product` but not `boosted_product__item`, causing extra query for `item.sku`.
  - **Fix:** Add `boosted_product__item` to `select_related`.

- [ ] **M4** — Composite Index on `SearchMerchandisingRule`
  - **Location:** `apps/ecommerce/models/SearchDiscovery/SearchMerchandisingRules.py:121-137`
  - **Description:** Missing composite index on `(tenant, is_active, -priority)`.
  - **Fix:** Add `models.Index(fields=["tenant", "is_active", "-priority"], name="idx_esmr_ten_act_prio")`.

- [ ] **M5** — Composite Index on `SearchQueryLog`
  - **Location:** `apps/ecommerce/models/SearchDiscovery/SearchQueryLogs.py:87-100`
  - **Description:** Missing composite index on `(tenant, is_zero_result, normalized_query)`.
  - **Fix:** Add `models.Index(fields=["tenant", "is_zero_result", "normalized_query"], name="idx_esql_ten_zr_norm")`.

- [ ] **M6** — Optimize Model Hydration on Keystroke Autocomplete
  - **Location:** `apps/ecommerce/views/SearchDiscovery/SearchConsole.py:345-370`
  - **Description:** Rapid keystroke autocomplete loads full model instances with all fields.
  - **Fix:** Use `.only("id", "number", "name", "brand", "item__sku")` and annotate `Min("variants__price")`.

- [ ] **M7** — Missing Accessible Labels on Search & Price Inputs
  - **Location:** `templates/ecommerce/searchdiscovery/console/console.html:48-57, 250-264`
  - **Description:** Search input and price filter inputs lack `aria-label` attributes.
  - **Fix:** Add `aria-label="Search catalog"`, `aria-label="Minimum price"`, and `aria-label="Maximum price"`.

- [ ] **M8** — Missing `filter_logic` Select Dropdown in Facet Filter Form
  - **Location:** `templates/ecommerce/searchdiscovery/facetconfig/list.html:34-75`
  - **Description:** View provides `filter_logic_choices` and `selected_logic`, but list template omits the dropdown.
  - **Fix:** Add the `filter_logic` dropdown to the filter form.

- [ ] **M9** — Design System Alignment for KPI Cards
  - **Location:** `templates/ecommerce/searchdiscovery/analytics/analytics.html:33-85`
  - **Description:** KPI stat cards should align with standard `.stat-card` styling.
  - **Fix:** Clean up stat cards to use standard NavERP `.stat-card` and `.stat-value` patterns.

- [ ] **M10** — Non-Standard Semantic Badges Standardization in Templates
  - **Location:** `templates/ecommerce/searchdiscovery/synonym/list.html`, `facetconfig/list.html`
  - **Description:** Ensure all badges use color-named classes (`badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, `badge-slate`).
  - **Fix:** Standardize all badges.

- [ ] **M11** — Pre-populate `root` Query Parameter on `searchsynonym_create`
  - **Location:** `apps/ecommerce/views/SearchDiscovery/SearchSynonyms.py:84`
  - **Description:** If `?root=` is passed in query parameters, pre-populate `root_term` initial value.
  - **Fix:** Add `initial={"root_term": request.GET.get("root", "")}` if root is provided.

- [ ] **M12** — Bind `SearchQueryLogFilterForm` in `searchquerylog_list`
  - **Location:** `apps/ecommerce/views/SearchDiscovery/SearchQueryLogs.py:50`
  - **Description:** Form was initialized unbound (`SearchQueryLogFilterForm()`) instead of binding `request.GET`.
  - **Fix:** Pass `request.GET` to bind the form: `filter_form = SearchQueryLogFilterForm(request.GET)`.
