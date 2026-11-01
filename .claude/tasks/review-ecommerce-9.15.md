# Review Findings — eCommerce 9.15: Analytics & Business Intelligence

Base ref: `f19d1323e9fa37e95d069c016d3457d3a87f4708`
Head: `HEAD`

---

## Executive Summary
Six specialized reviewers (`code-reviewer`, `explorer`, `frontend-reviewer`, `performance-reviewer`, `qa-smoke-tester`, `security-reviewer`) conducted an in-depth review of Sub-module 9.15 across 46 files and 5,479 lines of additions. Runtime smoke testing verified 100% pass across 65+ route permutations with zero 500 crashes and solid multi-tenant isolation. The findings below have been deduplicated, categorized by priority, and assigned deterministic IDs for Phase 5 remediation.

---

## Critical Findings

- [ ] **C1** — **Audit log forensics broken on deletion (`object_id=None`)**:
  - *Location*:
    - `apps/ecommerce/views/AnalyticsBi/DailySalesSnapshots.py:128-137`
    - `apps/ecommerce/views/AnalyticsBi/CustomerCohortMetrics.py:124-133`
    - `apps/ecommerce/views/AnalyticsBi/ProductMerchandisingMetrics.py:133-142`
    - `apps/ecommerce/views/AnalyticsBi/AttributionTouchpoints.py:141-150`
  - *Problem*: In all four delete views, `instance.delete()` is executed before `write_audit_log(...)`. In Django, executing `.delete()` on an active model instance sets `instance.pk` to `None`. Consequently, `write_audit_log` records `object_id = None`, corrupting audit forensics.
  - *Fix*: Invert execution order so `write_audit_log` runs before `instance.delete()`.

- [ ] **C2** — **Forms omit `TenantUniqueMixin`, bypassing tenant composite uniqueness validation**:
  - *Location*: All 4 forms in `apps/ecommerce/forms/AnalyticsBi/` (`DailySalesSnapshots.py:7`, `CustomerCohortMetrics.py:7`, `ProductMerchandisingMetrics.py:9`, `AttributionTouchpoints.py:11`).
  - *Problem*: Forms inherit from `TenantModelForm` without `TenantUniqueMixin`. Because `tenant` is excluded from form fields, Django's default `validate_unique()` excludes `tenant` from the uniqueness check and duplicate composite keys trigger raw database `IntegrityError` (500) instead of form validation errors.
  - *Fix*: Inherit from `(TenantUniqueMixin, TenantModelForm)` in all 4 forms.

- [ ] **C3** — **Sub-package `__init__.py` re-exports omitted in `AnalyticsBi`**:
  - *Location*:
    - `apps/ecommerce/models/AnalyticsBi/__init__.py`
    - `apps/ecommerce/forms/AnalyticsBi/__init__.py`
    - `apps/ecommerce/views/AnalyticsBi/__init__.py`
  - *Problem*: Unlike sibling packages, these `__init__.py` files contain only docstrings and lack symbol re-exports and `__all__` lists.
  - *Fix*: Add standard re-exports and `__all__` in each package `__init__.py`.

- [ ] **C4** — **Chained N+1 in `AttributionTouchpointForm` foreign key dropdowns (`order` & `cart`)**:
  - *Location*: `apps/ecommerce/forms/AnalyticsBi/AttributionTouchpoints.py:52-57`
  - *Problem*: `EcommerceOrder.__str__` accesses `self.customer.name` and `Cart.__str__` accesses `self.customer`. Without `.select_related("customer")` on both form dropdown querysets, rendering `form.html` executes $1 + N$ queries per field.
  - *Fix*: Add `.select_related("customer")` to `order` and `cart` querysets in `AttributionTouchpointForm.__init__`.

- [ ] **C5** — **Missing compound index on high-volume table `ecommerce_attribution_touchpoint` (`tenant`, `-touchpoint_timestamp`)**:
  - *Location*: `apps/ecommerce/models/AnalyticsBi/AttributionTouchpoints.py`
  - *Problem*: Model defines `ordering = ["-touchpoint_timestamp"]` and list queries filter by tenant ordered by `-touchpoint_timestamp`, but lacks a compound index on `(tenant, -touchpoint_timestamp)`.
  - *Fix*: Add `models.Index(fields=["tenant", "-touchpoint_timestamp"], name="idx_eatt_ten_time")` and generate incremental migration.

---

## Important Findings

- [ ] **I1** — **Missing `@tenant_admin_required` on batch recalculation views**:
  - *Location*:
    - `apps/ecommerce/views/AnalyticsBi/CustomerCohortMetrics.py:138-157` (`customercohortmetric_recalculate`)
    - `apps/ecommerce/views/AnalyticsBi/ProductMerchandisingMetrics.py:147-166` (`productmerchandisingmetric_reclassify`)
    - `apps/ecommerce/views/AnalyticsBi/DailySalesSnapshots.py:142-160` (`dailysalessnapshot_generate`)
  - *Problem*: Endpoints mutate tenant-wide business intelligence data but lack `@tenant_admin_required`, allowing non-admin tenant members to trigger bulk recalculations.
  - *Fix*: Add `@tenant_admin_required` decorator to all three views.

- [ ] **I2** — **Batch recalculation loops lack `transaction.atomic()` and `bulk_update`**:
  - *Location*: `apps/ecommerce/views/AnalyticsBi/CustomerCohortMetrics.py:140-155` and `ProductMerchandisingMetrics.py:149-164`.
  - *Problem*: Both views iterate over querysets and call `.save()` on every row sequentially without an atomic transaction, risking timeout and partial updates.
  - *Fix*: Wrap in `with transaction.atomic():` and use `bulk_update(metrics, [...], batch_size=500)`.

- [ ] **I3** — **Unhandled `request.tenant is None` in create and action views**:
  - *Location*:
    - `apps/ecommerce/views/AnalyticsBi/DailySalesSnapshots.py:69, 144`
    - `apps/ecommerce/views/AnalyticsBi/CustomerCohortMetrics.py:59, 140`
    - `apps/ecommerce/views/AnalyticsBi/ProductMerchandisingMetrics.py:67, 149`
    - `apps/ecommerce/views/AnalyticsBi/AttributionTouchpoints.py:75`
  - *Problem*: Tenantless superuser (`tenant=None`) attempting to create records or trigger actions crashes with raw database `IntegrityError`.
  - *Fix*: Guard with `if request.tenant is None: messages.error(request, "Select or switch to a workspace first."); return redirect(...)`.

- [ ] **I4** — **Potential DecimalField overflow crash on skewed rate calculations**:
  - *Location*:
    - `DailySalesSnapshots.py:94-98` (`conversion_rate_pct`)
    - `ProductMerchandisingMetrics.py:81-85` (`conversion_rate_pct`)
    - `CustomerCohortMetrics.py:58-64` (`retention_rate_pct`, `churn_rate_pct`)
  - *Problem*: `DecimalField(max_digits=5, decimal_places=2)` caps values at 999.99. If orders/units exceed denominator by 10x, rate exceeds 999.99 causing `DataError 1406`. Furthermore, churn rate can become negative if retention exceeds 100%.
  - *Fix*: Clamp percentage calculations to `[Decimal("0.00"), Decimal("100.00")]` (or max 999.99) and clamp `churn_rate_pct = max(Decimal("0.00"), ...)`.

- [ ] **I5** — **Invalid attribute access on AffiliatePartner in `attribution_touchpoint/detail.html:134`**:
  - *Location*: `templates/ecommerce/analytics_bi/attribution_touchpoint/detail.html:134`
  - *Problem*: Accesses `{{ touchpoint.affiliate.partner_code }} ({{ touchpoint.affiliate.company_name }})`. `AffiliatePartner` defines `referral_code` and `name`.
  - *Fix*: Update to `{{ touchpoint.affiliate.referral_code }} ({{ touchpoint.affiliate.name }})`.

- [ ] **I6** — **Cockpit query multiplication: 12 queries reducible to 7 queries**:
  - *Location*: `apps/ecommerce/views/AnalyticsBi/AnalyticsCockpit.py:39-61`
  - *Problem*: Cockpit executes 4 separate queries to `Cart` and 3 separate queries to `CheckoutSession`.
  - *Fix*: Collapse into conditional `aggregate()` calls with `Count("id", filter=Q(...))`.

- [ ] **I7** — **Non-sargable date filter on `EcommerceOrder`**:
  - *Location*: `AnalyticsCockpit.py:23-27` and `DailySalesSnapshots.py:58`
  - *Problem*: `created_at__date=today` wraps indexed datetime column in SQL `DATE()`, preventing index seek.
  - *Fix*: Use datetime range `created_at__gte=start_of_day, created_at__lt=start_of_next_day`.

- [ ] **I8** — **Missing intra-tenant relational validation between `variant` and `product`**:
  - *Location*: `apps/ecommerce/forms/AnalyticsBi/ProductMerchandisingMetrics.py:57-60`
  - *Problem*: Does not verify that `variant.product == product`.
  - *Fix*: In `clean()`, validate `if variant and product and variant.product_id != product.id: self.add_error("variant", "Selected variant does not belong to the selected product.")`.

- [ ] **I9** — **Manual velocity tier edits overwritten on save**:
  - *Location*: `apps/ecommerce/views/AnalyticsBi/ProductMerchandisingMetrics.py:106-109`
  - *Problem*: Editing a metric calls `m.recalculate_metrics()` which overwrites user-selected `velocity_tier`.
  - *Fix*: In edit view, preserve the submitted `velocity_tier` or only recalculate margin/return rates.

- [ ] **I10** — **Missing `{% else %}` display fallback on velocity tier badges**:
  - *Location*: `templates/ecommerce/analytics_bi/product_merchandising_metric/list.html:108-116` and `detail.html:16-24`
  - *Problem*: `{% else %}` clause assumes "Dead Stock" directly without explicit check or fallback.
  - *Fix*: Add `{% elif m.velocity_tier == "dead_stock" %}` and fallback `<span class="badge badge-slate">{{ m.get_velocity_tier_display }}</span>`.

---

## Minor Findings

- [ ] **M1** — **Redundant duplicate Chart.js script tag in `cockpit.html:245`**:
  - *Location*: `templates/ecommerce/analytics_bi/cockpit/cockpit.html:245`
  - *Problem*: Redundant `<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>` tag (already loaded in `templates/base.html:28`).
  - *Fix*: Remove line 245.

- [ ] **M2** — **Audit log `changes` argument passed as string instead of dict**:
  - *Location*: `CustomerCohortMetrics.py:153` and `ProductMerchandisingMetrics.py:162`.
  - *Problem*: Passes raw strings to `changes` in `write_audit_log`.
  - *Fix*: Pass structured dict `{"count": count}`.

- [ ] **M3** — **Filter state mismatch for `is_finalized` in `DailySalesSnapshots.py:34-38`**:
  - *Location*: `apps/ecommerce/views/AnalyticsBi/DailySalesSnapshots.py:34-38`
  - *Problem*: Passes raw string `"true"` to context while template checks `"1"`.
  - *Fix*: Normalize `selected_finalized` to `"1"` / `"0"`.

- [ ] **M4** — **Missing compound index on `ProductMerchandisingMetric` for default sort order**:
  - *Location*: `apps/ecommerce/models/AnalyticsBi/ProductMerchandisingMetrics.py`
  - *Problem*: Lacks compound index for `ordering = ["-period_end", "-gross_revenue"]`.
  - *Fix*: Add `models.Index(fields=["tenant", "-period_end", "-gross_revenue"], name="idx_epmm_ten_end_rev")`.

- [ ] **M5** — **Unbounded funnel percentage in Cockpit**:
  - *Location*: `apps/ecommerce/views/AnalyticsBi/AnalyticsCockpit.py:72, 78, 84, 90`
  - *Problem*: Stage percentages can exceed 100% in edge cases.
  - *Fix*: Wrap stage percentages in `min(100.0, ...)`.

- [ ] **M6** — **`units_sold` not aggregated from order lines in `DailySalesSnapshot.aggregate_for_tenant_date`**:
  - *Location*: `apps/ecommerce/models/AnalyticsBi/DailySalesSnapshots.py:78-84`
  - *Problem*: `units_sold` defaults to 0 on auto-generated snapshots.
  - *Fix*: Aggregate `EcommerceOrderLine.objects.filter(order__in=orders).aggregate(u=Sum("quantity"))["u"] or 0`.

- [ ] **M7** — **Consolidate cart count queries in `DailySalesSnapshot.aggregate_for_tenant_date`**:
  - *Location*: `apps/ecommerce/models/AnalyticsBi/DailySalesSnapshots.py:86-89`
  - *Problem*: `carts_created` and `carts_abandoned` issue 2 separate queries.
  - *Fix*: Consolidate into single `aggregate(created=Count('id'), abandoned=Count('id', filter=Q(status='abandoned')))`.

- [ ] **M8** — **Product title truncation on mobile cockpit (`cockpit.html:197`)**:
  - *Location*: `templates/ecommerce/analytics_bi/cockpit/cockpit.html:197`
  - *Problem*: Long product title link could cause layout stretching on narrow screens.
  - *Fix*: Add `class="truncate max-w-xs block"`.
