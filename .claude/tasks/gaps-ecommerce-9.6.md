# Gap Register: eCommerce 9.6 Customer Account & Profile

## Overview
Sub-Module 9.6 covers Customer Account Profiles with loyalty tiers and multi-mode authentication, Address Preferences with automated single-default shipping/billing constraints, Curated Customer Wishlists with priority indicators and variant validation, and Statutory GDPR/CCPA Privacy Requests with automated 30-day statutory deadlines, full JSON data portability export generation, and atomic right-to-erasure account anonymization workflows.

## Register

| ID | Title | Owner | Blocked On / Prerequisite | Status | Done When |
|---|---|---|---|---|---|
| None | No open or deferred gaps | apps.ecommerce | None | `- [x]` Complete | All 9.6 features, review findings, and test suites are 100% complete and verified green. |

## Closed Items
- **C1**: Corrected `write_audit_log` call signatures across all CustomerProfile views. Closed.
- **C2**: Safely guarded `core.Address` attribute lookups in GDPR data portability exports without accessing non-existent attributes. Closed.
- **C3**: Applied explicit database-level unique constraints `(tenant, number)` across all 4 top-level customer profile models to guarantee collision-free sequence retries. Closed.
- **C4**: Wrapped GDPR anonymization in `transaction.atomic()` and validated `request_type="erasure_anonymize"`. Closed.
- **C5**: Ensured right-to-erasure workflow deactivates associated authentication user and privatizes public wishlists. Closed.
- **I1–I11**: Fixed product id validation, `@tenant_admin_required` decorators, N+1 query annotations, query optimizations, composite indexes, cross-party address validation, template attribute drift, seeder filtering, and form field exclusions. Closed.
- **M1–M6**: Fixed theme badge classes, audit log action verb lengths, variant-product form validation, stat-card CSS styling, accessibility `aria-label`s, and Django admin `list_select_related`. Closed.
- All planned 9.6 scope, entities, routes, templates, admin registrations, idempotent seeders, navigation items, review findings, and 4 test modules (588 tests in app suite) are 100% complete and verified green with 0 remaining defects.
