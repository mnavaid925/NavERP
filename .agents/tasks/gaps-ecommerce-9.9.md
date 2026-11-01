# Gap Register — Sub-module 9.9: Content Management System (CMS) (Module 9: eCommerce Management System, `ecommerce`)

## Summary
- **Module Slug**: `ecommerce` (Sub-module 9.9)
- **Status**: Complete — Built, reviewed (6 reviewers), fixed, ready for Phase 6 tests.
- **Review File**: [`.claude/tasks/review-ecommerce-9.9.md`](file:///c:/xampp/htdocs/NavERP/.claude/tasks/review-ecommerce-9.9.md)

---

## Gaps & Deferred Items

### GAP-ecommerce-9.9-01: Table Name Alignment for `CmsPage` (`ecommerce_cmspage` vs `ecommerce_cms_page`)
- **Owner**: `ecommerce` (Sub-module 9.9) / Database Migration Engineer
- **Waiting For / Blocked On**: Sub-module 9.9 migration `0026` is already generated and applied with table name `ecommerce_cmspage`. Renaming table via `AlterModelTable` requires dedicated migration planning to avoid disruption in multi-developer branches.
- **Status**: `[~]` Deferred to subsequent database optimization / migration normalization wave.
- **Done When**: A dedicated migration renames `db_table` on `CmsPage` to `ecommerce_cms_page` without data loss and all queries continue passing.

### GAP-ecommerce-9.9-02: Composite `(tenant, -created_at)` Indexes on CMS Models
- **Owner**: `ecommerce` (Sub-module 9.9) / Performance Engineering
- **Waiting For / Blocked On**: Non-blocking query optimization. CMS list queries currently perform cleanly on tenant indexes and primary key/creation ordering on current data scales.
- **Status**: `[~]` Deferred to database query optimization wave.
- **Done When**: Composite `(tenant, -created_at)` indexes are added to `CmsPage`, `BlogArticle`, `MediaAsset`, and `ContentBlock` via a new non-blocking migration.
