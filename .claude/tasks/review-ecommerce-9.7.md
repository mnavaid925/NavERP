# Review Findings — Sub-module 9.7: Search & Product Discovery (Module 9: eCommerce Management System, `ecommerce`)

- **Sub-module:** 9.7 Search & Product Discovery
- **Module:** 9 eCommerce Management System
- **App:** `apps/ecommerce`
- **Date:** 2026-10-30
- **Changeset:** `a9a5b9525739bf487ce81e8eb50a9792c910da1d` (BASE) ... `3544600773b938dffee78f62e998e826d48ae533` (HEAD)

---

## Pass 1: `code-reviewer` Findings

### Critical
- [ ] **C1** — Broken Facet Checkbox State in Search Console Template (`templates/ecommerce/searchdiscovery/console/console.html:230`):
  `{% if active_filters|dictsort:fg.config.code %}checked{% endif %}` fails silently because `dictsort` expects a sequence of dictionaries, not a dictionary. Checkboxes for active facet filters never render checked.
- [ ] **C2** — Invalid Model Attribute `product.category` in Search Console Grid (`templates/ecommerce/searchdiscovery/console/console.html:291-293`):
  `CatalogProduct` has `primary_category` foreign key, not `category`. Product category tags in workbench grid evaluate to None.
- [ ] **C3** — Database Duplication & PostgreSQL Incompatibility in Price Sorting (`apps/ecommerce/views/SearchDiscovery/SearchConsole.py:253-259`):
  `.order_by("variants__price").distinct()` causes PostgreSQL error and SQL duplicate rows across products with multiple variants. Need annotation `Min("variants__price")`.
- [ ] **C4** — Duplicate Search Query Logs Created on Redirects (`apps/ecommerce/views/SearchDiscovery/SearchConsole.py:67-77, 296-309`):
  When a redirect rule is triggered in workbench view without auto_redirect, query log is created twice.
- [ ] **C5** — Campaign Schedule (`start_date` / `end_date`) Ignored in Rule Evaluation (`apps/ecommerce/views/SearchDiscovery/SearchConsole.py:48-61, 213-246`):
  Active date bounds (`start_date`, `end_date`) are omitted from merchandising rule queries, executing expired or future rules.

### Important
- [ ] **I1** — Missing Model-Level Multi-Tenant Validation in `clean()` (`SearchFacetConfigs.py:107`, `SearchMerchandisingRules.py:142`, `SearchQueryLogs.py:105`):
  Model `clean()` methods do not assert that foreign keys (`category_scope`, `target_category`, `boosted_product`, `customer`, `clicked_product`) match `self.tenant_id`.
- [ ] **I2** — N+1 Query on Pinned Products in `search_console` (`SearchConsole.py:213-215, 241`):
  `active_rules` lacks `select_related("boosted_product", "target_category")`.
- [ ] **I3** — Silent Omission of `variant_option` Facet Values in Sidebar (`SearchConsole.py:173-206`):
  No handler for `fc.source_type == "variant_option"` when computing facet groups.
- [ ] **I4** — Missing HTML5 `datetime-local` Format in Merchandising Form (`SearchMerchandisingRules.py:48-49`):
  `start_date` and `end_date` widgets lack `format="%Y-%m-%dT%H:%M"`, causing them to render blank on edit.
- [ ] **I5** — Inactive / Archived Products Inserted via Pin Rules (`SearchConsole.py:272-282`):
  `pinned_prod` is inserted into `product_list` without checking `pinned_prod.status == "active"`.
- [ ] **I6** — Unscoped Customer Attribution on Search Query Logs (`SearchConsole.py:307`):
  `request.user.party` is assigned without validating `party.tenant_id == tenant.id`.

### Minor
- [ ] **M1** — Non-Standard Semantic Badges in Templates (`synonym/list.html`, `facetconfig/list.html`, etc.):
  Verify badge classes against `theme.css`. Note: in `theme.css`, `.badge-info` and `.badge-muted` are valid color/theme classes in this repository, but standardize across all templates.
- [ ] **M2** — Exact Full-String-Only Matching for Synonyms (`SearchConsole.py:98`):
  Multi-word queries do not match token synonyms.
- [ ] **M3** — Nullable `category_scope` Unique Constraint in `SearchFacetConfig` (`SearchFacetConfigs.py:92-95`):
  Unique constraint allows duplicate global codes on databases where NULL!=NULL.
- [ ] **M4** — Unbound Form `SearchQueryLogFilterForm` in `searchquerylog_list` (`SearchQueryLogs.py:50`).


---

## Pass 2: `explorer` Findings

### Critical
- [ ] **E-C1** — Broken Facet Checkbox State in Search Console Template (`templates/ecommerce/searchdiscovery/console/console.html:230`):
  `{% if active_filters|dictsort:fg.config.code %}checked{% endif %}` fails silently. In `search_console` view, annotate each item in `facet_groups` with `"is_selected": (active_filters.get(fc.code) == itm["value"])`, and in template use `{% if itm.is_selected %}checked{% endif %}`.
- [ ] **E-C2** — Invalid Attribute `product.category` Causes Silent Blank (L7) (`templates/ecommerce/searchdiscovery/console/console.html:291-293`):
  `CatalogProduct` has `primary_category`, not `category`.
- [ ] **E-C3** — Duplicate Products & PostgreSQL Incompatibility in Price Sorting (`apps/ecommerce/views/SearchDiscovery/SearchConsole.py:253-259`):
  Ordering by field across 1-to-many joined table causes duplicate products and breaks on Postgres. Annotate `min_price = Min("variants__price")`.
- [ ] **E-C4** — Duplicate Search Query Log Created on Redirect Intercepts (`apps/ecommerce/views/SearchDiscovery/SearchConsole.py:67-77, 296-309`):
  Double query log creation on redirect rules.
- [ ] **E-C5** — Merchandising Campaign Schedules Ignored in Search Console (`apps/ecommerce/views/SearchDiscovery/SearchConsole.py:48-61, 213-220`):
  Rules do not filter `start_date` and `end_date`.

### Important
- [ ] **E-I1** — Contract Pinned `sort_choices` Omission in Search Console View (`apps/ecommerce/views/SearchDiscovery/SearchConsole.py:33-38`):
  `('rating', 'Customer Rating')` missing from `sort_choices`.
- [ ] **E-I2** — Missing Model-Level Cross-Tenant FK Validation in `clean()` (`SearchFacetConfigs.py:107`, `SearchMerchandisingRules.py:142`, `SearchQueryLogs.py:105`).
- [ ] **E-I3** — Variant Option Facets Silently Excluded from Facet Groups (`apps/ecommerce/views/SearchDiscovery/SearchConsole.py:173-206`):
  No handler for `fc.source_type == "variant_option"` in `facet_groups`.
- [ ] **E-I4** — N+1 Queries on Boosted Products in Search Console Rule Loop (`apps/ecommerce/views/SearchDiscovery/SearchConsole.py:213-215, 241`):
  `active_rules` lacks `select_related("boosted_product", "target_category")`.
- [ ] **E-I5** — HTML5 `datetime-local` Format Missing on Edit Forms (`apps/ecommerce/forms/SearchDiscovery/SearchMerchandisingRules.py:48-49`):
  Add `format="%Y-%m-%dT%H:%M"` to widgets.
- [ ] **E-I6** — Inactive / Draft Products Injected via Fixed Slot Pin Rules (`apps/ecommerce/views/SearchDiscovery/SearchConsole.py:241, 273-282`).
- [ ] **E-I7** — Unscoped Customer Attribution on Query Logs (`apps/ecommerce/views/SearchDiscovery/SearchConsole.py:307`).

### Minor
- [ ] **E-M1** — Unused `root` Query Parameter on `searchsynonym_create` (`apps/ecommerce/views/SearchDiscovery/SearchSynonyms.py:84`).
- [ ] **E-M2** — Nullable Unique Constraint on Global Facet Codes (`SearchFacetConfigs.py:92-95`).
- [ ] **E-M3** — Synonym Trigger Limited to Exact Full-String Equality (`SearchConsole.py:98`).
- [ ] **E-M4** — Unbound `SearchQueryLogFilterForm` in `searchquerylog_list` (`SearchQueryLogs.py:21-54`).


---

## Pass 3: `frontend-reviewer` Findings

### Important
- [ ] **FE-I1** — Dynamic Facet Checkbox UI State Retention Broken via Invalid `|dictsort` Usage (`templates/ecommerce/searchdiscovery/console/console.html:230`):
  Checkbox `{% if active_filters|dictsort:fg.config.code %}checked{% endif %}` fails silently. Add `is_selected` boolean flag to item dictionaries in `facet_groups` in `SearchConsole.py`.
- [ ] **FE-I2** — None-Safe Display (L10) for Nullable ForeignKey Fields (`templates/ecommerce/searchdiscovery/merchandisingrule/list.html:125, 147-155`, `detail.html:84`):
  `rule.target_category.name` and `rule.boosted_product.name` are accessed directly without `{% if %}` or `|default:"—"` guards when null.

### Minor
- [ ] **FE-M1** — Missing Accessible Labels on Search & Price Inputs (`templates/ecommerce/searchdiscovery/console/console.html:48-57, 250-264`):
  Add `aria-label` attributes to the workbench search box and price inputs.
- [ ] **FE-M2** — Design System Alignment for KPI Cards (`templates/ecommerce/searchdiscovery/analytics/analytics.html:33-85`):
  Adopt `.stat-card`, `.stat-value`, and `.stat-label` structure without hardcoding light-mode background classes over `.stat-icon.<color>`.
- [ ] **FE-M3** — Missing `filter_logic` Select Dropdown in Facet Filter Form (`templates/ecommerce/searchdiscovery/facetconfig/list.html:34-75`):
  Context provides `filter_logic_choices` and `selected_logic`, but form omits the dropdown.


---

## Pass 4: `performance-reviewer` Findings

### Critical
- [ ] **PERF-C1** — Cartesian Explosion & DB Incompatibility on Price Sorting (`apps/ecommerce/views/SearchDiscovery/SearchConsole.py:252-259`):
  Ordering `base_qs` via `order_by("variants__price").distinct()[:100]` creates an SQL join against reverse FK `ProductVariant`. Multi-variant products duplicate rows and `SELECT DISTINCT` with `ORDER BY` on joined column fails on PostgreSQL. Annotate `base_qs = base_qs.annotate(min_price=Min("variants__price"))` before ordering.

### Important
- [ ] **PERF-I1** — N+1 Queries on Pinned Merchandising Products in `search_console` (`apps/ecommerce/views/SearchDiscovery/SearchConsole.py:213-215, 241`):
  `active_rules` lacks `select_related("boosted_product__item", "boosted_product__primary_category")` and `prefetch_related("boosted_product__variants")`, firing individual queries per pinned rule when accessing `sku` and `base_price`.
- [ ] **PERF-I2** — N+1 Queries on Fallback Product Recommendations (`apps/ecommerce/views/SearchDiscovery/SearchConsole.py:288-294`):
  `fallback_recommendations` lacks `select_related("item", "primary_category")` and `prefetch_related("variants")`, firing up to 8 queries per zero-result search.
- [ ] **PERF-I3** — Full-Table Scan & Per-Item `UPDATE` Queries in Synonym Loop (`apps/ecommerce/views/SearchDiscovery/SearchConsole.py:93-117`):
  Pre-filter active synonyms in SQL by `Q(root_term=norm_q) | Q(synonyms__icontains=norm_q)` instead of iterating full table, and batch `hit_count` updates outside the loop.
- [ ] **PERF-I4** — Redundant Category Count Aggregation in Facet Loop Discarded by Template (`apps/ecommerce/views/SearchDiscovery/SearchConsole.py:178-206`):
  Template explicitly ignores category facet groups at line 217 because categories are rendered independently. Skip querying category counts in `facet_groups`.
- [ ] **PERF-I5** — Multiple Table Scans in `search_analytics` Dashboard (`apps/ecommerce/views/SearchDiscovery/SearchConsole.py:415-426`):
  Consolidate `count()`, zero-result count, and avg execution time into a single `aggregate()` query using conditional `Count("id", filter=Q(is_zero_result=True))`.

### Minor
- [ ] **PERF-M1** — Missing Nested `select_related` on Product Item in Merchandising Rule Detail (`apps/ecommerce/views/SearchDiscovery/SearchMerchandisingRules.py:69-78`):
  Add `boosted_product__item` to `select_related`.
- [ ] **PERF-M2** — Missing Composite Index for Rule Priority Evaluation (`apps/ecommerce/models/SearchDiscovery/SearchMerchandisingRules.py:121-137`):
  Add composite index `(tenant, is_active, -priority)` to `SearchMerchandisingRule.Meta.indexes`.
- [ ] **PERF-M3** — Missing Composite Index for Zero-Result Query Aggregation (`apps/ecommerce/models/SearchDiscovery/SearchQueryLogs.py:87-100`):
  Add composite index `(tenant, is_zero_result, normalized_query)` to `SearchQueryLog.Meta.indexes`.
- [ ] **PERF-M4** — Unnecessary Full Model Hydration on Keystroke Autocomplete (`apps/ecommerce/views/SearchDiscovery/SearchConsole.py:345-370`):
  Use `.only("id", "number", "name", "brand", "item__sku")` and annotate `Min("variants__price")`.


---

## Pass 5: `qa-smoke-tester` Findings

- **Total Verification Checks:** 66 / 66 passed.
- **Critical (0):** None. Zero 500 errors, zero crashes on junk parameters or out-of-range pagination.
- **Important (0):** None. Cross-tenant IDOR protection verified (404) across all detail, edit, delete, and toggle endpoints.
- **Minor (0):** None. Zero template comment leaks (`{#` or `{% comment`) found in rendered output or template sources.


