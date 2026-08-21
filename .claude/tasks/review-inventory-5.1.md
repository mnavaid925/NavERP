# Review — inventory 5.1 Product & Catalog Management

Changeset: `7dfbc5593de67ef66812f3f208eec9fdc0d9fa62..HEAD` · Date: 2026-08-21
Lanes: code-reviewer · frontend-reviewer · security-reviewer · qa/perf/docs-reviewer (all returned; smoke lane covered by temp/smoke_inventory.py — all green)

## Summary

| ID | Severity | Status | File(s) | Finding |
|----|----------|--------|---------|---------|
| SEC-1 | Important | [ ] open | forms/Catalog/ProductFiles.py | `ProductFileForm` lacks the tenant-stamping mixin its model `clean()` depends on — **every app-side ProductFile create is falsely rejected** ("That item belongs to another workspace") because `crud_create` stamps tenant only after `is_valid()`. Probe-verified. |
| QA-1 | Important | [ ] open | views/Catalog/ItemPrices.py:15 | Price-list N+1: template renders `obj.currency.code` but queryset only `select_related("item")`. |
| TST-1 | Important | [ ] open | apps/inventory/tests/ (absent) | Zero test files while every sibling app ships a suite. Covered by this run's TEST WAVE (models/forms/views/security), not the fixer. |
| MOD-1 | Minor | [ ] open | models/Catalog/ItemPrices.py:74-90 | `margin_pct` returns a fake 100% for an unsaved/no-item instance (docstring promises None); dead `cost is None` disjunct (`standard_cost` is non-nullable). Apply the same `not self.item_id → None` guard to `markup_pct`. |
| MOD-2 | Minor | [ ] open | models/Catalog/ProductFiles.py:11-13 vs 38-39 | Docstring claims allowlisting is "left to the shared core tooling" while the model carries its own drifted copy (`.zip` dropped). Own the local list explicitly in the docstring. |
| SEE-1 | Minor | [ ] open | management/commands/seed_inventory.py:50-51 | `--flush` help says "demo rows" but deletes ALL rows of the three tables for all tenants. Reword help text to match reality. |
| FRM-1 | Minor | [ ] open | templates/inventory/catalog/productfile/form.html:5-6 | H1 "Attach" vs breadcrumb "New" wording mismatch in create mode. |
| FRM-2 | Minor | [ ] open | templates/inventory/catalog/itemprice/list.html:55 + detail.html:7 | Clearance maps to `badge-red` (danger colour) — give clearance its own `slate` branch, keep red as the unexpected-value fallback. |
| FRM-3 | Minor | [ ] open | templates/inventory/overview.html:64-72 | Per-row "Manage" buttons all link to the same `scm:category_list`; make each row target `scm:item_list?category={{ c.pk }}`. |
| FRM-4 | Minor | [ ] open | templates/inventory/catalog/*/detail.html | No "Back to list" affordance on the three detail pages — add one to page-actions. |
| SEC-2 | Minor | [ ] open | forms/Catalog/ProductFiles.py | No upload size cap — house pattern pairs the extension allowlist with `MAX_UPLOAD_BYTES` (apps/core/forms/_common.py:22). Enforce in `clean()`. |
| SEC-3 | Minor | [ ] open | views/Catalog/{ItemAttributes,ItemPrices,ProductFiles}.py + 3 detail templates | Detail sibling tables iterate unscoped reverse relations AND include the current object itself (QA-2 folded in). Pass explicitly scoped siblings from the views: `obj.item.catalog_prices.filter(tenant=request.tenant).exclude(pk=obj.pk)` as extra_context, loop that in the templates. |
| FRM-5 | Minor | [ ] open | forms/_common.py:49-54 (+ ItemPrices form) | `_active_currencies()` drops a since-deactivated stored currency on edit → silent NULL. Union the instance's current value back (`Q(is_active=True) | Q(pk=form.instance.currency_id)`), mirroring scm's `_keep_current`. |
| MIG-1 | Minor | [ ] open | models Meta + migrations | Missing indexes: `(tenant, kind)` on ProductFile (filter dropdown), `(tenant, created_at)` backing overview's recent-files sort. Add fields to Meta.indexes and generate migration 0002. |
| DOC-1 | Minor | [ ] open | NavERP-ERD.md:467 | ERD Module 5 row still names `PriceList`; reconcile to the shipped `inventory.ItemPrice` (sell-side price rows on scm.Item). |
| MIX-1 | Minor | [~] skipped — reason | forms/Catalog/ItemPrices.py:7 | Code lane suggested removing `TenantUniqueMixin` from `ItemPriceForm` (no unique constraint). REJECTED after reconciliation: the mixin's `__init__` also stamps `instance.tenant`, which `ItemPrice.clean()`'s foreign-item check reads during `full_clean()` on CREATE — removing it would recreate SEC-1 on the price path. The mixin stays wherever a model `clean()` reads tenant; a clarifying comment goes into `forms/_common.py` as part of SEC-1's fix. |

## Verification gate for the fixer

After each fix (and at the end): `venv\Scripts\python.exe manage.py check`, then re-run `venv\Scripts\python.exe temp\smoke_inventory.py` — must stay ALL SMOKE CHECKS PASSED. For MIG-1: `makemigrations inventory` then `migrate`. Commit **one file per commit**, message prefix `fix(inventory): 5.1 ...`.
