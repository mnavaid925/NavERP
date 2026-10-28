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

---

## Pass 2: Codebase Explorer (`explorer`)

### Critical
None.

### Important
- `[ ]` **I5**: `templates/ecommerce/productcatalog/catalogproduct/list.html:33-75` — Filter UI dropdowns omitted for `visibility` and `brand`: The view implements filtering on `visibility` and `brand` and passes `visibility_choices`, `brands_list`, `visibility_filter`, and `brand_filter` in context, but the `<form>` omits `<select name="visibility">` and `<select name="brand">` elements. Add dropdowns to the filter form.
- `[ ]` **I6**: `apps/ecommerce/views/ProductCatalog/StoreCategories.py:52-53` — Category products query ignores `primary_category`: In `storecategory_detail`, `category.products.filter(...)` only traverses products where this category is in ManyToMany `categories`. Products having this category assigned as `primary_category` are omitted. Update query to `CatalogProduct.objects.filter(tenant=request.tenant).filter(Q(primary_category=category) | Q(categories=category)).distinct()`.

### Minor
- `[ ]` **M5**: `templates/ecommerce/productcatalog/productvariant/list.html:30-62` — Filter UI dropdown omitted for `is_active`: The view supports filtering on `is_active` and passes `is_active_filter` in context, but the filter form only provides `q` and `product` inputs. Add an `is_active` filter select.
- `[ ]` **M6**: `templates/ecommerce/productcatalog/storecategory/detail.html:138-190` — Context variable `products` unrendered in detail template: The view queries and passes `products` to context in accordance with the contract, but `storecategory/detail.html` does not render a products section or count badge. Add a products table section under the category detail page.

---

## Pass 3: Frontend Reviewer (`frontend-reviewer`)

### Critical
None.

### Important
- `[ ]` **I7**: `templates/ecommerce/productcatalog/catalogproduct/list.html:33-75` — Filter UI dropdowns omitted for `visibility` and `brand`: Expand grid to include `<select name="visibility">` and `<select name="brand">` matching the view context.
- `[ ]` **I8**: `templates/ecommerce/productcatalog/catalogproduct/list.html:214,219` — Pagination links drop `visibility` and `brand` query parameters (Lesson L9). Append `&visibility={{ visibility_filter }}&brand={{ brand_filter }}`.
- `[ ]` **I9**: `templates/ecommerce/productcatalog/productvariant/list.html:30-62` — Missing `is_active` filter dropdown in variant filter bar. Add `<select name="is_active">`.
- `[ ]` **I10**: `templates/ecommerce/productcatalog/productvariant/list.html:165,170` — Pagination links drop `is_active` query parameter (Lesson L9). Append `&is_active={{ is_active_filter }}`.
- `[ ]` **I11**: `templates/ecommerce/productcatalog/storecategory/detail.html:189` — Category detail page omits catalog products display. Add "Products in Category" card section below the Sub-Categories card.

### Minor
- `[ ]` **M7**: `templates/ecommerce/productcatalog/**/` — Add explicit `aria-label` attributes to all icon-only action buttons alongside `title`.
- `[ ]` **M8**: `templates/ecommerce/productcatalog/bulk_import.html:82` & form templates — Replace `space-x-*` with `gap-*` for RTL safety.


