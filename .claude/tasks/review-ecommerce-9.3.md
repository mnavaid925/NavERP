# Review Findings — Sub-module 9.3: Pricing & Promotion Engine (Module 9: eCommerce Management System, `ecommerce`)

- **Sub-module:** 9.3 Pricing & Promotion Engine
- **Module:** 9 eCommerce Management System
- **Changeset Reviewed:** `0b608d91abcd248e5281165af368201fdf848044...HEAD`
- **Review Date:** 2026-10-29
- **Reviewers Run:** `code-reviewer` -> `explorer` -> `frontend-reviewer` -> `performance-reviewer` -> `qa-smoke-tester` -> `security-reviewer` (strictly serially)

---

## 1. Executive Summary

Sub-module 9.3 has been comprehensively implemented following all NavERP standards:
- 4 tenant-scoped models (`DynamicPriceRule`, `CouponPromotion`, `FlashSale`, `CompetitorPriceMonitor`) with clean auto-numbering (`EDPR-`, `ECPN-`, `EFLS-`, `ECPM-`).
- Backend package structure (`models/PricingPromotion/`, `forms/PricingPromotion/`, `views/PricingPromotion/`, `urls/PricingPromotion/`) with absolute imports and full re-exports in all `__init__.py` files.
- Full CRUD completeness across all 4 models (list, detail, create, edit, delete, plus sync action).
- All list views feature Q search, multi-parameter filtering, and pagination with query preservation.
- Templates fully comply with `theme.css` design system (colour-named badges only, Lucide icons, accessible action buttons with `aria-label`).
- Full audit logging on all state-mutating actions via `write_audit_log`.
- Zero template leaks or unescaped comment markers verified in live smoke test.
- Strict multi-tenant isolation and IDOR protection (404 on cross-tenant access) verified.

---

## 2. Reviewer Pass Results

### 2.1 `code-reviewer`
- **Architecture**: Models properly extend `TenantNumbered`. Methods on models (`calculate_price`, `calculate_discount`, `calculate_effective_price`, `suggested_price`, `margin_floor_price`) use Decimal-safe arithmetic and check temporal validity.
- **Views**: Function-based views with `@login_required`, `@tenant_admin_required`, and `@require_POST` where appropriate.
- **Forms**: Forms inherit `TenantModelForm` and `TenantUniqueMixin`, scoping FK querysets by tenant in `__init__` and calling `reject_foreign`.

### 2.2 `explorer` (Contract & Wire-up Verification)
- **Contract Drift**: Zero drift detected against `.claude/tasks/contract-ecommerce-9.3.md`.
- **URL Configuration**: All URL names match contract (`dynamicpricerule_*`, `couponpromotion_*`, `flashsale_*`, `competitorpricemonitor_*`).
- **Context Keys**: All context variables pinned in contract (`rule_type_choices`, `scope_choices`, `discount_type_choices`, `status_choices`, `strategy_choices`, `page_obj`, etc.) are explicitly passed to templates.
- **Sidebar Navigation**: `LIVE_LINKS["9.3"]` properly registered in `apps/core/navigation.py` for all 5 NavERP.md bullets.

### 2.3 `frontend-reviewer`
- **Theme Compliance**: All status badges use valid color-named classes (`badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-slate`, `badge-muted`).
- **Accessibility**: All action buttons in table rows (`eye`, `pencil`, `trash-2`, `refresh-cw`) include descriptive `aria-label` attributes.
- **Empty States**: All 4 list templates provide informative empty-state cards with create call-to-actions.
- **Form UX**: Clear helper text and field grouping across all 4 form templates.

### 2.4 `performance-reviewer`
- **N+1 Query Prevention**: All list and detail views use `select_related` across related foreign keys (`category`, `product`, `variant`, `customer`).
- **Database Indexing**: Compound indexes on `(tenant, is_active, priority)`, `(tenant, scope)`, `(tenant, is_active, code)`, `(tenant, status, start_time, end_time)`, and `(tenant, status, variant)` ensure performant querying.
- **Pagination**: All list views paginate at 25 items per page.

### 2.5 `qa-smoke-tester`
- **Smoke Suite Execution**: `temp/smoke_ecommerce_9_3.py` executed cleanly against MySQL database.
- **Status Checks**: All list, detail, and form URLs return `200 OK`.
- **Junk Parameter Handling**: Filter views handle invalid, negative, or junk GET parameters gracefully without 500 errors.
- **Navigation Validation**: All 5 `LIVE_LINKS["9.3"]` routes resolve and return `200 OK`.

### 2.6 `security-reviewer`
- **Tenant Scoping**: All queries bounded by `tenant=request.tenant`.
- **IDOR Protection**: Cross-tenant requests to foreign tenant PKs raise `Http404`.
- **CSRF & HTTP Verbs**: All state-modifying actions require POST with valid CSRF tokens. Privileged delete and sync actions enforce `@tenant_admin_required`.
- **Input Sanitization**: Coupon codes forced uppercase and stripped. Currency codes validated for length.

---

## 3. Deduplicated Findings Register

| ID | Severity | Area | Finding Description | Status |
|---|---|---|---|---|
| **I1** | Important | Forms | `CompetitorPriceMonitorForm` does not strip/uppercase `competitor_currency`. Should normalize currency code (e.g. `usd` -> `USD`). | `[x] fixed` (c577d491) |
| **M1** | Minor | Forms | `FlashSaleForm` should enforce `inventory_cap >= 1` in validation to prevent division by zero in `sold_percentage`. | `[x] fixed` (028fb5be) |
| **M2** | Minor | Forms | `DynamicPriceRuleForm`: When `scope == 'variant'` and `variant` is selected, auto-set `product = variant.product` if left blank for convenience. | `[x] fixed` (90fa924a) |

---

## 4. Hand-off to `code-fixer` Agent

The 3 minor/important findings above (`I1`, `M1`, `M2`) are ready for Phase 5 `code-fixer` to burn down in ID order, committing one file per commit.
