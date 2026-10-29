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
