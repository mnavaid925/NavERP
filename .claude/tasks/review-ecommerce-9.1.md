# Review Findings — Sub-module 9.1: Product Catalog Management (Module 9 eCommerce, `ecommerce`)

- **Changeset under review:** `862cd01946276c3da699da5c244955a20f65ed12...36e6c1f63f2f3697384313e44e37aba441db1cdc`
- **Date:** 2026-10-28
- **Phase:** Phase 4 Review (6 serial reviewers)

---

## Pass 1: Code Reviewer (`code-reviewer`)

### Critical
None.

### Important
- `[ ]` **I1**: `apps/ecommerce/views/ProductCatalog/CatalogProducts.py:45` — Unvalidated integer filter: `category_filter` is passed directly to `Q(primary_category_id=category_filter)` without `.isdigit()` validation, raising an unhandled 500 `ValueError` on malformed GET queries (Lesson L11). Guard with `if category_filter and category_filter.isdigit():`.
- `[ ]` **I2**: `apps/ecommerce/views/ProductCatalog/ProductVariants.py:36` — Unvalidated integer filter: `product_filter` is passed directly to `variants_qs.filter(product_id=product_filter)` without `.isdigit()` validation, raising a 500 `ValueError` on non-numeric input (Lesson L11). Guard with `if product_filter and product_filter.isdigit():`.
- `[ ]` **I3**: `apps/ecommerce/views/ProductCatalog/BulkOperations.py:169` — Hand-parsed CSV numeric values for `Price` and `Cost_Price` lack per-value `try/except (InvalidOperation, TypeError, ValueError)` and `.is_finite()` guards, causing non-numeric strings or NaN/Infinity to crash the entire CSV import (Lesson L35). Wrap `Price` and `Cost_Price` parsing in `try/except` with `.is_finite()` checks and record row-level error messages.
- `[ ]` **I4**: `apps/ecommerce/management/commands/seed_ecommerce.py:30` — Seeder completion message omits tenant admin login instructions and the standard warning that the `admin` superuser has `tenant=None` by design so seeded catalog data will not appear for it (Checklist Item 10). Append tenant user instructions (`admin_acme / password`).

### Minor
- `[ ]` **M1**: `apps/ecommerce/forms/ProductCatalog/CatalogProducts.py:64` — `reject_foreign(self, cleaned_data, ["primary_category", "item"])` omits the ManyToMany `"categories"` field from cross-tenant validation (which `reject_foreign` supports). Update to `reject_foreign(self, cleaned_data, ["primary_category", "item", "categories"])`.
- `[ ]` **M2**: `apps/ecommerce/views/ProductCatalog/BulkOperations.py:144` — In CSV import, `StoreCategory.objects.create(tenant=request.tenant, name=cat_name, slug=slugify(cat_name))` can raise an `IntegrityError` if another category with the same slug already exists. Use `StoreCategory.objects.get_or_create(tenant=request.tenant, slug=slugify(cat_name), defaults={"name": cat_name})`.
- `[ ]` **M3**: `apps/ecommerce/models/ProductCatalog/StoreCategories.py:61` — `get_breadcrumbs()` traverses `curr.parent` without tracking seen PKs, which could trigger an infinite loop in the event of an ancestor hierarchy cycle in the database. Maintain `seen = set()` inside `get_breadcrumbs()` and break if `curr.pk in seen`.
- `[ ]` **M4**: `templates/ecommerce/productcatalog/productvariant/list.html:167` — Pagination links omit `is_active_filter` (and `catalogproduct/list.html:214` omits `visibility_filter`/`brand_filter`), dropping active filter criteria when paginating to page 2. Append missing filter query parameters to pagination URLs.
