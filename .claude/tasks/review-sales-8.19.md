# Review Findings — Sales 8.19: Master Data & Configuration

- **Target:** Sub-module 8.19 Master Data & Configuration (`apps/sales`)
- **Base SHA:** `d289c460e5e74689d5fee8f2c23c1e9734fefc70`
- **Head SHA:** `cd25972db7052d311d2af341839da0cb66a6a08c`
- **Review Passes (Serial):** `code-reviewer` → `explorer` → `frontend-reviewer` → `performance-reviewer` → `qa-smoke-tester` → `security-reviewer`

---

## Pass 1: Code Reviewer (`code-reviewer`)

### Verdict
Commit after fixing Critical+Important findings.

### Critical
1. `apps/sales/views/MasterDataConfiguration/SalesRegionalSettings.py:84,113,140`, `SalesMethodologies.py:89,119,145`, `SalesPriceBookEntries.py:93,122,149`, `SalesCustomEntityDefinitions.py:84,114,141` — `write_audit_log` is called with transposed arguments `(request.user, action_verb, obj, changes)` instead of `(request.user, obj, action_verb, changes=...)`. Because `ContentType.objects.get_for_model(obj.__class__)` is called on the second argument, passing a string raises `AttributeError: type object 'str' has no attribute '_meta'`, crashing with an unhandled 500 error on every create, edit, and delete action across all four entities. Fix: Swap the 2nd and 3rd arguments in all 12 call sites to pass `obj` as the 2nd parameter and the action string as the 3rd parameter.
2. `apps/sales/models/MasterDataConfiguration/SalesPriceBookEntries.py:126-131` & `apps/sales/forms/MasterDataConfiguration/SalesPriceBookEntries.py:61` — In `SalesPriceBookEntry.clean()`, cross-tenant validation compares `self.price_book.tenant_id != self.tenant_id` (and for `product` and `item`). On create form validation, `self.tenant_id` is None, causing `clean()` to raise a `ValidationError` ("Price book must belong to the active workspace.") and completely preventing the creation of any new price book entry from the UI. Fix: In `SalesPriceBookEntry.clean()`, guard with `if self.tenant_id:` before checking FK tenant matches, and in `SalesPriceBookEntryForm.__init__`, set `if self.tenant and not self.instance.tenant_id: self.instance.tenant = self.tenant`.
3. `apps/sales/models/MasterDataConfiguration/SalesMethodologies.py:94-98` & `apps/sales/forms/MasterDataConfiguration/SalesMethodologies.py:51` — In `SalesMethodology.clean()`, cross-tenant validation compares `self.pipeline.tenant_id != self.tenant_id` and `self.gating_stage.tenant_id != self.tenant_id`. On create form validation, `self.tenant_id` is None, causing `clean()` to raise a `ValidationError` ("Pipeline must belong to the active workspace.") and completely preventing the creation of any new sales methodology with a pipeline or gating stage from the UI. Fix: In `SalesMethodology.clean()`, guard with `if self.tenant_id:` before checking FK tenant matches, and in `SalesMethodologyForm.__init__`, set `if self.tenant and not self.instance.tenant_id: self.instance.tenant = self.tenant`.

### Important
1. `apps/sales/forms/MasterDataConfiguration/SalesPriceBookEntries.py:66` — `self.fields["item"].queryset` attempts to import from `apps.scm.models.InventoryCatalog.Items.Item`, which does not exist (`scm.Item` resides in `apps.scm.models.InventoryManagement.Items`). The bare `except Exception:` swallows the `ModuleNotFoundError` and resets the item queryset to `.none()`, leaving the physical inventory SKU link dropdown permanently empty. Fix: Change import to `from apps.scm.models import Item`.
2. `apps/sales/views/MasterDataConfiguration/SalesRegionalSettings.py:133`, `SalesMethodologies.py:138`, `SalesPriceBookEntries.py:142`, `SalesCustomEntityDefinitions.py:134` — Master data schema, methodology, and regional configuration create/edit/delete views are protected with `@login_required` but omit `@tenant_admin_required`. Commercial terms, custom fields, and stage-gating policies are workspace administrative settings and should require tenant admin privileges (matching `IntegrationApiHub` and `WorkflowProcessAutomation`). Fix: Add `@tenant_admin_required` (from `apps.core.decorators`) to create, edit, and delete views in these modules.

### Minor
1. `templates/sales/masterdataconfiguration/pricebookentry/detail.html:121` — Template renders `{{ entry.item.number }} · {{ entry.item.name }}` for the linked inventory item, but `scm.Item` inherits `TenantOwned` and uses `sku` (has no `number` attribute), rendering the number portion blank. Fix: Change `{{ entry.item.number }}` to `{{ entry.item.sku }}`.
2. `apps/sales/management/commands/seed_sales.py:4627` — Terminal seeder summary output at the bottom of `handle()` reports `"Sales 8.1 through 8.18 seed complete."`. Fix: Update message string to `"Sales 8.1 through 8.19 seed complete."`.
3. `apps/sales/views/MasterDataConfiguration/SalesPriceBookEntries.py:53` & `templates/sales/masterdataconfiguration/pricebookentry/list.html:36-66` — `pbe_list` queries and passes `products` in the view context, but `list.html` does not include a product filter dropdown. Fix: Either add the product filter to `list.html` or remove the unused `products` queryset from the view context.

---

## Pass 2: Architecture & Contract Explorer (`explorer`)

### Verdict
Commit after fixing Critical+Important findings.

### Critical
1. `apps/sales/models/MasterDataConfiguration/__init__.py`, `apps/sales/forms/MasterDataConfiguration/__init__.py`, `apps/sales/views/MasterDataConfiguration/__init__.py` — Package structure invariant violation: Three of the four newly created architecture layers lack an `__init__.py` file. Unlike sibling packages (`IntegrationApiHub`, `WorkflowProcessAutomation`, `MobileSales`), `models/MasterDataConfiguration/`, `forms/MasterDataConfiguration/`, and `views/MasterDataConfiguration/` are uninitialized namespace directories. Consequently, `apps/sales/forms/__init__.py` and `apps/sales/views/__init__.py` were forced to import individual entity modules piecemeal rather than importing package symbols through `from .MasterDataConfiguration import ...`. Fix: Create `__init__.py` in all three packages (`models/MasterDataConfiguration/__init__.py`, `forms/MasterDataConfiguration/__init__.py`, `views/MasterDataConfiguration/__init__.py`) re-exporting their respective models, forms, and views with explicit `__all__` lists, and update parent `__init__.py` files to import cleanly from `.MasterDataConfiguration`.

### Important
1. `apps/sales/views/MasterDataConfiguration/SalesPriceBookEntries.py:54-64,69-81`, `SalesCustomEntityDefinitions.py:48-58,62-73`, `SalesRegionalSettings.py:49-58,62-73`, `Overview.py:37-43` — View context keys do not provide canonical entity aliases (`price_book_entries`, `price_book_entry`, `custom_entities`, `custom_entity`, `regional_settings`, `regional_setting`, `overview_stats`). The views pass only short keys (`entries`, `entry`, `definitions`, `definition`, `settings`, `setting`, `kpis`). While current templates consume these short keys, contract expectations and Phase 6 automated view tests expect the canonical model-named variables. Fix: Supply dual context variables in the view dictionaries: pass both `entries` and `price_book_entries` in `pbe_list`; `entry` and `price_book_entry` in `pbe_detail`/form; `definitions` and `custom_entities` in `sco_list`; `definition` and `custom_entity` in `sco_detail`/form; `settings` and `regional_settings` in `srg_list`; `setting` and `regional_setting` in `srg_detail`/form; and `kpis` and `overview_stats` in `master_data_overview`.
2. `apps/sales/urls/MasterDataConfiguration/Overview.py:3`, `SalesPriceBookEntries.py:3`, `SalesCustomEntityDefinitions.py:3`, `SalesMethodologies.py:3`, `SalesRegionalSettings.py:3` — URL configuration modules import directly from `apps.sales.views.MasterDataConfiguration import <Module> as views` instead of using standard module-level package imports or relative imports. While PEP 420 namespace traversal currently resolves this in Python 3, once `apps/sales/views/MasterDataConfiguration/__init__.py` is introduced, importing submodules directly from the package without exposing them in `__all__` can lead to import resolution anomalies. Fix: In `apps/sales/urls/MasterDataConfiguration/*.py`, import views explicitly (e.g. `from apps.sales.views.MasterDataConfiguration.SalesPriceBookEntries import ...` or `from apps.sales.views.MasterDataConfiguration import ...`).

### Minor
1. `apps/sales/models/MasterDataConfiguration/SalesPriceBookEntries.py:73` vs `contract-sales-8.19.md:73` — The build contract specifies `number: CharField(max_length=32, editable=False)`, but `TenantNumbered` base class defaults `number` to `max_length=20`. While prefix `PBE-` + 8 digits fits easily within 20 characters, the contract spec and migration schema show a minor length difference. Fix: Keep as inherited from `TenantNumbered` (`max_length=20`) to remain consistent with all 22 other sales models, and note the alignment with base `TenantNumbered`.
2. `templates/sales/masterdataconfiguration/overview.html:22-38` — The configuration hub header contains navigation action buttons for Price Books, Custom Schema, Methodologies, and Regional Settings. The button for Regional Settings uses `btn btn-primary` while the other three use `btn btn-outline`, visually implying that Regional Settings is the primary call to action instead of equal peer configuration sections. Fix: Standardize all four hub navigation buttons to `btn btn-outline` (or reserve `btn btn-primary` for the most common administrative action).

---

## Pass 3: Frontend & Design System Reviewer (`frontend-reviewer`)

*(pending)*

---

## Pass 4: Performance & Database Optimization Reviewer (`performance-reviewer`)

*(pending)*

---

## Pass 5: QA & Functional Smoke Reviewer (`qa-smoke-tester`)

*(pending)*

---

## Pass 6: Security & Isolation Reviewer (`security-reviewer`)

*(pending)*

---

## Consolidated & Prioritized Findings

*(deduplicated and assigned C / I / M IDs after all 6 passes complete)*
