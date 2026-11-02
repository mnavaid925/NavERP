# Review Findings — eCommerce 9.15: Analytics & Business Intelligence

Base ref: `f19d1323e9fa37e95d069c016d3457d3a87f4708`
Head: `HEAD`

---

## Executive Summary
Six specialized reviewers (`code-reviewer`, `explorer`, `frontend-reviewer`, `performance-reviewer`, `qa-smoke-tester`, `security-reviewer`) conducted an in-depth review of Sub-module 9.15 across 46 files and 5,479 lines of additions. Runtime smoke testing verified 100% pass across 65+ route permutations with zero 500 crashes and solid multi-tenant isolation. All findings (C1–C5, I1–I10, M1–M8) have been systematically resolved with individual commits and verified clean.

---

## Critical Findings

- [x] **C1** — **Audit log forensics broken on deletion (`object_id=None`)**: fixed — `8aab49c1`, `b8bc23f7`, `a250a2ea`, `f2cbbfc4`
  - *Location*:
    - `apps/ecommerce/views/AnalyticsBi/DailySalesSnapshots.py:128-137`
    - `apps/ecommerce/views/AnalyticsBi/CustomerCohortMetrics.py:124-133`
    - `apps/ecommerce/views/AnalyticsBi/ProductMerchandisingMetrics.py:133-142`
    - `apps/ecommerce/views/AnalyticsBi/AttributionTouchpoints.py:141-150`
  - *Problem*: In all four delete views, `instance.delete()` was executed before `write_audit_log(...)`. In Django, executing `.delete()` on an active model instance sets `instance.pk` to `None`. Consequently, `write_audit_log` records `object_id = None`, corrupting audit forensics.
  - *Fix*: Inverted execution order so `write_audit_log` runs before `instance.delete()`.

- [x] **C2** — **Forms omit `TenantUniqueMixin`, bypassing tenant composite uniqueness validation**: fixed — `929b02ec`, `ba3eac03`, `2be6e194`, `ff199c1e`
  - *Location*: All 4 forms in `apps/ecommerce/forms/AnalyticsBi/` (`DailySalesSnapshots.py:7`, `CustomerCohortMetrics.py:7`, `ProductMerchandisingMetrics.py:9`, `AttributionTouchpoints.py:11`).
  - *Problem*: Forms inherited from `TenantModelForm` without `TenantUniqueMixin`. Because `tenant` is excluded from form fields, Django's default `validate_unique()` excluded `tenant` from uniqueness checks and duplicate composite keys triggered raw database `IntegrityError` (500) instead of form validation errors.
  - *Fix*: Inherited from `(TenantUniqueMixin, TenantModelForm)` in all 4 forms.

- [x] **C3** — **Sub-package `__init__.py` re-exports omitted in `AnalyticsBi`**: fixed — `5d73a910`, `d929111d`, `710d3020`
  - *Location*:
    - `apps/ecommerce/models/AnalyticsBi/__init__.py`
    - `apps/ecommerce/forms/AnalyticsBi/__init__.py`
    - `apps/ecommerce/views/AnalyticsBi/__init__.py`
  - *Problem*: Unlike sibling packages, these `__init__.py` files contained only docstrings and lacked symbol re-exports and `__all__` lists.
  - *Fix*: Added standard re-exports and `__all__` in each package `__init__.py`.

- [x] **C4** — **Chained N+1 in `AttributionTouchpointForm` foreign key dropdowns (`order` & `cart`)**: fixed — `78cdb2ca`
  - *Location*: `apps/ecommerce/forms/AnalyticsBi/AttributionTouchpoints.py:52-57`
  - *Problem*: `EcommerceOrder.__str__` accesses `self.customer.name` and `Cart.__str__` accesses `self.customer`. Without `.select_related("customer")` on both form dropdown querysets, rendering `form.html` executed $1 + N$ queries per field.
  - *Fix*: Added `.select_related("customer")` to `order` and `cart` querysets in `AttributionTouchpointForm.__init__`.

- [x] **C5** — **Missing compound index on high-volume table `ecommerce_attribution_touchpoint` (`tenant`, `-touchpoint_timestamp`)**: fixed — `976c44ad`, `8915c13e`
  - *Location*: `apps/ecommerce/models/AnalyticsBi/AttributionTouchpoints.py`
  - *Problem*: Model defined `ordering = ["-touchpoint_timestamp"]` and list queries filter by tenant ordered by `-touchpoint_timestamp`, but lacked a compound index on `(tenant, -touchpoint_timestamp)`.
  - *Fix*: Added `models.Index(fields=["tenant", "-touchpoint_timestamp"], name="idx_eatt_ten_time")` and generated incremental migration `0028`.

---

## Important Findings

- [x] **I1** — **Missing `@tenant_admin_required` on batch recalculation views**: fixed — `aa8fe992`, `d78aeb13`, `99cd2831`
  - *Location*:
    - `apps/ecommerce/views/AnalyticsBi/CustomerCohortMetrics.py:138-157` (`customercohortmetric_recalculate`)
    - `apps/ecommerce/views/AnalyticsBi/ProductMerchandisingMetrics.py:147-166` (`productmerchandisingmetric_reclassify`)
    - `apps/ecommerce/views/AnalyticsBi/DailySalesSnapshots.py:142-160` (`dailysalessnapshot_generate`)
  - *Problem*: Endpoints mutate tenant-wide business intelligence data but lacked `@tenant_admin_required`.
  - *Fix*: Added `@tenant_admin_required` decorator to all three views.

- [x] **I2** — **Batch recalculation loops lack `transaction.atomic()` and `bulk_update`**: fixed — `bfa29ede`, `802becb1`
  - *Location*: `apps/ecommerce/views/AnalyticsBi/CustomerCohortMetrics.py:140-155` and `ProductMerchandisingMetrics.py:149-164`.
  - *Problem*: Both views iterated over querysets and called `.save()` on every row sequentially without an atomic transaction.
  - *Fix*: Wrapped in `with transaction.atomic():` and batch saved.

- [x] **I3** — **Unhandled `request.tenant is None` in create and action views**: fixed — `8e82aca6`, `80f2e6d1`, `ac1d3906`, `5ce49c13`
  - *Location*:
    - `apps/ecommerce/views/AnalyticsBi/DailySalesSnapshots.py:69, 144`
    - `apps/ecommerce/views/AnalyticsBi/CustomerCohortMetrics.py:59, 140`
    - `apps/ecommerce/views/AnalyticsBi/ProductMerchandisingMetrics.py:67, 149`
    - `apps/ecommerce/views/AnalyticsBi/AttributionTouchpoints.py:75`
  - *Problem*: Tenantless superuser (`tenant=None`) attempting to create records or trigger actions crashed with raw database `IntegrityError`.
  - *Fix*: Guarded with `if request.tenant is None: messages.error(request, "Select or switch to a workspace first."); return redirect(...)`.

- [x] **I4** — **Potential DecimalField overflow crash on skewed rate calculations**: fixed — `857fb1ee`, `9cf97991`, `59b696f2`
  - *Location*:
    - `DailySalesSnapshots.py:94-98` (`conversion_rate_pct`)
    - `ProductMerchandisingMetrics.py:81-85` (`conversion_rate_pct`)
    - `CustomerCohortMetrics.py:58-64` (`retention_rate_pct`, `churn_rate_pct`)
  - *Problem*: `DecimalField(max_digits=5, decimal_places=2)` caps values at 999.99. If orders/units exceed denominator by 10x, rate exceeds 999.99 causing `DataError 1406`.
  - *Fix*: Clamped percentage calculations to `[Decimal("0.00"), Decimal("100.00")]` and clamped `churn_rate_pct = max(Decimal("0.00"), ...)`.

- [x] **I5** — **Invalid attribute access on AffiliatePartner in `attribution_touchpoint/detail.html:134`**: fixed — `a08d03e7`
  - *Location*: `templates/ecommerce/analytics_bi/attribution_touchpoint/detail.html:134`
  - *Problem*: Accessed `{{ touchpoint.affiliate.partner_code }} ({{ touchpoint.affiliate.company_name }})`.
  - *Fix*: Updated to `{{ touchpoint.affiliate.referral_code }} ({{ touchpoint.affiliate.name }})`.

- [x] **I6** — **Cockpit query multiplication: 12 queries reducible to 7 queries**: fixed — `12c297ac`
  - *Location*: `apps/ecommerce/views/AnalyticsBi/AnalyticsCockpit.py:39-61`
  - *Problem*: Cockpit executed 4 separate queries to `Cart` and 3 separate queries to `CheckoutSession`.
  - *Fix*: Collapsed into conditional `aggregate()` calls with `Count("id", filter=Q(...))`.

- [x] **I7** — **Non-sargable date filter on `EcommerceOrder`**: fixed — `eb22e37c`, `116a438a`
  - *Location*: `AnalyticsCockpit.py:23-27` and `DailySalesSnapshots.py:58`
  - *Problem*: `created_at__date=today` wrapped indexed datetime column in SQL `DATE()`, preventing index seek.
  - *Fix*: Used datetime range `created_at__gte=start_of_day, created_at__lt=start_of_next_day`.

- [x] **I8** — **Missing intra-tenant relational validation between `variant` and `product`**: fixed — `914943c8`
  - *Location*: `apps/ecommerce/forms/AnalyticsBi/ProductMerchandisingMetrics.py:57-60`
  - *Problem*: Did not verify that `variant.product == product`.
  - *Fix*: In `clean()`, validated `if variant and product and variant.product_id != product.id: self.add_error("variant", "Selected variant does not belong to the selected product.")`.

- [x] **I9** — **Manual velocity tier edits overwritten on save**: fixed — `96c5678b`
  - *Location*: `apps/ecommerce/views/AnalyticsBi/ProductMerchandisingMetrics.py:106-109`
  - *Problem*: Editing a metric called `m.recalculate_metrics()` which overwrote user-selected `velocity_tier`.
  - *Fix*: In edit view, preserved the submitted `velocity_tier`.

- [x] **I10** — **Missing `{% else %}` display fallback on velocity tier badges**: fixed — `2e3f662d`, `b9aec776`
  - *Location*: `templates/ecommerce/analytics_bi/product_merchandising_metric/list.html:108-116` and `detail.html:16-24`
  - *Problem*: `{% else %}` clause assumed "Dead Stock" directly without explicit check or fallback.
  - *Fix*: Added `{% elif m.velocity_tier == "dead_stock" %}` and fallback `<span class="badge badge-slate">{{ m.get_velocity_tier_display }}</span>`.

---

## Minor Findings

- [x] **M1** — **Redundant duplicate Chart.js script tag in `cockpit.html:245`**: fixed — `16ddcafd`
  - *Location*: `templates/ecommerce/analytics_bi/cockpit/cockpit.html:245`
  - *Problem*: Redundant `<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>` tag (already loaded in `templates/base.html:28`).
  - *Fix*: Removed line 245.

- [x] **M2** — **Audit log `changes` argument passed as string instead of dict**: fixed — `bee19ef0`, `e7f4d559`
  - *Location*: `CustomerCohortMetrics.py:153` and `ProductMerchandisingMetrics.py:162`.
  - *Problem*: Passed raw strings to `changes` in `write_audit_log`.
  - *Fix*: Passed structured dict `{"count": count}`.

- [x] **M3** — **Filter state mismatch for `is_finalized` in `DailySalesSnapshots.py:34-38`**: fixed — `046a4cd8`
  - *Location*: `apps/ecommerce/views/AnalyticsBi/DailySalesSnapshots.py:34-38`
  - *Problem*: Passed raw string `"true"` to context while template checked `"1"`.
  - *Fix*: Normalized `selected_finalized` to `"1"` / `"0"`.

- [x] **M4** — **Missing compound index on `ProductMerchandisingMetric` for default sort order**: fixed — `02c99bcf`, `775990e5`
  - *Location*: `apps/ecommerce/models/AnalyticsBi/ProductMerchandisingMetrics.py`
  - *Problem*: Lacked compound index for `ordering = ["-period_end", "-gross_revenue"]`.
  - *Fix*: Added `models.Index(fields=["tenant", "-period_end", "-gross_revenue"], name="idx_epmm_ten_end_rev")` and migration 0029.

- [x] **M5** — **Unbounded funnel percentage in Cockpit**: fixed — `04c52872`
  - *Location*: `apps/ecommerce/views/AnalyticsBi/AnalyticsCockpit.py:72, 78, 84, 90`
  - *Problem*: Stage percentages could exceed 100% in edge cases.
  - *Fix*: Wrapped stage percentages in `min(100.0, ...)`.

- [x] **M6** — **`units_sold` not aggregated from order lines in `DailySalesSnapshot.aggregate_for_tenant_date`**: fixed — `797f75db`
  - *Location*: `apps/ecommerce/models/AnalyticsBi/DailySalesSnapshots.py:78-84`
  - *Problem*: `units_sold` defaulted to 0 on auto-generated snapshots.
  - *Fix*: Aggregated `EcommerceOrderLine.objects.filter(order__in=orders).aggregate(u=Sum("quantity"))["u"] or 0`.

- [x] **M7** — **Consolidate cart count queries in `DailySalesSnapshot.aggregate_for_tenant_date`**: fixed — `797f75db`
  - *Location*: `apps/ecommerce/models/AnalyticsBi/DailySalesSnapshots.py:86-89`
  - *Problem*: `carts_created` and `carts_abandoned` issued 2 separate queries.
  - *Fix*: Consolidated into single `aggregate(created=Count('id'), abandoned=Count('id', filter=Q(status='abandoned')))`.

- [x] **M8** — **Product title truncation on mobile cockpit (`cockpit.html:197`)**: fixed — `d39ee02f`
  - *Location*: `templates/ecommerce/analytics_bi/cockpit/cockpit.html:197`
  - *Problem*: Long product title link could cause layout stretching on narrow screens.
  - *Fix*: Added `class="truncate max-w-xs block"`.
