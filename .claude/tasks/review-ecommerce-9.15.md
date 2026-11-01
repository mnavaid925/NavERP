# Review Findings — eCommerce 9.15: Analytics & Business Intelligence

Base ref: `f19d1323e9fa37e95d069c016d3457d3a87f4708`
Head: `HEAD`

---

## 1. Code Reviewer Findings

### Critical
1. **Audit log forensics broken on deletion (`object_id=None`):**
   - In all four delete views (`DailySalesSnapshots.py:128-137`, `CustomerCohortMetrics.py:124-133`, `ProductMerchandisingMetrics.py:133-142`, `AttributionTouchpoints.py:141-150`), `instance.delete()` is executed before `write_audit_log(...)`. In Django, executing `.delete()` on an active model instance sets `instance.pk` to `None`. Consequently, `write_audit_log` records `object_id = None`. Invert the execution order so `write_audit_log` runs before `instance.delete()`.
2. **Forms omit `TenantUniqueMixin`, bypassing tenant unique validation:**
   - In all 4 forms (`DailySalesSnapshots.py:7`, `CustomerCohortMetrics.py:7`, `ProductMerchandisingMetrics.py:9`, `AttributionTouchpoints.py:11`), forms inherit from `TenantModelForm` without `TenantUniqueMixin`. Because `tenant` is excluded from form fields, Django's default `validate_unique()` excludes `tenant` from the uniqueness check and duplicate composite keys trigger raw database `IntegrityError` (500) instead of form validation errors. Add `TenantUniqueMixin` to all 4 forms.
3. **Missing package `__init__.py` re-exports in `AnalyticsBi` directories:**
   - `apps/ecommerce/{models,forms,views}/AnalyticsBi/__init__.py` contain only docstrings and do not re-export their respective entities and views with `__all__`. Add standard symbol re-exports and `__all__` lists in each package `__init__.py`.

### Important
1. **Batch recalculations lack `transaction.atomic` and pass raw strings to `changes`:**
   - In `CustomerCohortMetrics.py:140-155` and `ProductMerchandisingMetrics.py:149-164`, batch recalculate/reclassify loops lack `transaction.atomic()` and pass raw strings to `changes` in `write_audit_log` instead of dicts. Wrap in `transaction.atomic()` and pass dict.
2. **Unhandled `request.tenant is None` in create and action views:**
   - In `DailySalesSnapshots.py:69, 144`, `CustomerCohortMetrics.py:59, 140`, `ProductMerchandisingMetrics.py:67, 149`, `AttributionTouchpoints.py:75`, tenant-less superuser (`tenant=None`) attempting to create or trigger actions raises raw database IntegrityError. Add guard checking `if request.tenant is None: messages.error(...); return redirect(...)`.
3. **Potential DecimalField overflow in percentage rate calculations:**
   - In `DailySalesSnapshots.py:95-98`, `ProductMerchandisingMetrics.py:64-87`, and `CustomerCohortMetrics.py:58-64`, percentage calculations using `DecimalField(max_digits=5, decimal_places=2)` can exceed 999.99 if orders > carts * 10, raising `DataError 1406`. Clamp percentages to `[0.00, 100.00]` (or `[0.00, 999.99]`). Also clamp `churn_rate_pct` to min 0.00.
4. **Manual velocity tier edits overwritten on save:**
   - In `ProductMerchandisingMetrics.py:106-109`, editing a metric calls `m.recalculate_metrics()` which overwrites user-selected `velocity_tier`. Only recalculate margin/return rates or preserve submitted tier.

### Minor
1. **Redundant duplicate Chart.js script tag:**
   - `templates/ecommerce/analytics_bi/cockpit/cockpit.html:245` includes Chart.js even though `templates/base.html:150` loads Chart.js 4.4.1 globally. Remove line 245.
2. **`units_sold` not aggregated from order lines:**
   - `DailySalesSnapshots.py:78-84` leaves `units_sold` defaulting to 0 on auto-generated snapshots. Aggregate `EcommerceOrderLine.quantity`.
3. **Filter state mismatch for `is_finalized`:**
   - `DailySalesSnapshots.py:34-38` passes `selected_finalized` as string `"true"`, but template checks `"1"`. Normalize to `"1"` / `"0"`.
4. **Batch actions lack `@tenant_admin_required`:**
   - `customercohortmetric_recalculate` and `productmerchandisingmetric_reclassify` lack `@tenant_admin_required`.
5. **Conversion funnel percentage display unbounded:**
   - `AnalyticsCockpit.py:72, 78, 84, 90` stage percentage can exceed 100%. Wrap in `min(100.0, ...)`.

---

## 2. Explorer Findings

### Critical
None. All 18 backend files and 13 templates are in place, migration 0027 is clean, routes resolve without collision, and Django check reports zero issues.

### Important
1. **Sub-Package `__init__.py` Re-exports Omitted in `AnalyticsBi`**:
   - `apps/ecommerce/models/AnalyticsBi/__init__.py`, `apps/ecommerce/forms/AnalyticsBi/__init__.py`, and `apps/ecommerce/views/AnalyticsBi/__init__.py` lack `__all__` and re-exports. (Confirms Code Reviewer Critical #3).
2. **Missing `TenantUniqueMixin` on Tenant-Scoped Forms**:
   - All four forms omit `TenantUniqueMixin`. (Confirms Code Reviewer Critical #2).

### Minor
1. **Contract Drift in `channel_attribution_summary` Dictionary Key**:
   - Contract specifies key `"orders"` while view and template use `"count"` for touchpoint events. View and template are synchronized.
2. **Filter State Dropdown Mismatch for `is_finalized`**:
   - `DailySalesSnapshots.py:34-38` passes raw string to context; normalize to `"1"` / `"0"`. (Confirms Code Reviewer Minor #3).
3. **Redundant Chart.js CDN Script Tag in Cockpit Template**:
   - `templates/ecommerce/analytics_bi/cockpit/cockpit.html:245` redundant script tag. (Confirms Code Reviewer Minor #1).

---

## 3. Frontend Reviewer Findings

### Critical
None. Zero comment leaks, all POST forms have CSRF tokens, all 28 template reverse URLs are valid, and all theme classes adhere to theme.css.

### Important
1. **Invalid Attribute Access on AffiliatePartner in `attribution_touchpoint/detail.html` (Line 134)**:
   - `templates/ecommerce/analytics_bi/attribution_touchpoint/detail.html:134` accesses `{{ touchpoint.affiliate.partner_code }} ({{ touchpoint.affiliate.company_name }})`. `AffiliatePartner` defines `referral_code` and `name` (not `partner_code` or `company_name`). Update to `{{ touchpoint.affiliate.referral_code }} ({{ touchpoint.affiliate.name }})`.
2. **Missing `{% else %}` Display Fallback on Velocity Tier Badges in `product_merchandising_metric`**:
   - In `templates/ecommerce/analytics_bi/product_merchandising_metric/list.html:108-116` and `detail.html:16-24`, the `{% else %}` clause assumes "Dead Stock" directly without an explicit `{% elif m.velocity_tier == "dead_stock" %}` and an `{% else %}` fallback of `<span class="badge badge-slate">{{ m.get_velocity_tier_display }}</span>`.

### Minor
1. **Redundant Duplicate Script Tag in `cockpit.html` (Line 245)**:
   - `templates/ecommerce/analytics_bi/cockpit/cockpit.html:245` includes Chart.js CDN script tag, already loaded by `templates/base.html:28`. (Confirms Code Reviewer Minor #1).
2. **Long Product Title Truncation on Mobile Cockpit (`cockpit.html` Line 197)**:
   - In `templates/ecommerce/analytics_bi/cockpit/cockpit.html:197`, product title link `{{ m.product.name }}` in Best Sellers widget could stretch on small screens. Add `class="truncate max-w-xs block"`.

---

## 4. Performance Reviewer Findings

### Critical
1. **Chained N+1 in `AttributionTouchpointForm` foreign key dropdowns (`order` & `cart`)**:
   - `apps/ecommerce/forms/AnalyticsBi/AttributionTouchpoints.py:52-57`: `EcommerceOrder.__str__` evaluates `self.customer.name` and `Cart.__str__` evaluates `self.customer`. Without `.select_related("customer")` on both form dropdown querysets, rendering the form executes $1 + N$ queries per field.
   - Fix: Add `.select_related("customer")` to `order` and `cart` querysets in `AttributionTouchpointForm.__init__`.
2. **Missing compound index on high-volume table `ecommerce_attribution_touchpoint` (`tenant`, `-touchpoint_timestamp`)**:
   - `apps/ecommerce/models/AnalyticsBi/AttributionTouchpoints.py`: `ordering = ["-touchpoint_timestamp"]` and list view queries by tenant ordered by `-touchpoint_timestamp`, but lacks an index on `(tenant, -touchpoint_timestamp)`.
   - Fix: Add `models.Index(fields=["tenant", "-touchpoint_timestamp"], name="idx_eatt_ten_time")` to `AttributionTouchpoint.Meta.indexes`.

### Important
1. **Cockpit query multiplication: 12 queries reducible to 7 queries via conditional aggregation**:
   - `apps/ecommerce/views/AnalyticsBi/AnalyticsCockpit.py:39-61`: 4 separate queries to `Cart` and 3 separate queries to `CheckoutSession`. Collapse into conditional `aggregate()` using `Count("id", filter=Q(...))`.
2. **Sequential row-by-row UPDATE loop in batch recalculation views**:
   - `ProductMerchandisingMetrics.py:149-157` and `CustomerCohortMetrics.py:140-148`: Iterate and call `.save()` on each instance. Use `bulk_update(metrics, [...], batch_size=500)` inside `transaction.atomic()`.
3. **Non-sargable date lookup preventing index range scan on `EcommerceOrder`**:
   - `AnalyticsCockpit.py:23-27` and `DailySalesSnapshots.py:58`: `created_at__date=today` wraps indexed column in SQL `DATE()`. Use datetime interval `created_at__gte=start_of_day, created_at__lt=start_of_next_day`.

### Minor
1. **Missing compound index on `ProductMerchandisingMetric` for default sort order**:
   - Add `models.Index(fields=["tenant", "-period_end", "-gross_revenue"], name="idx_epmm_ten_end_rev")`.
2. **Consolidate count queries in `DailySalesSnapshot.aggregate_for_tenant_date`**:
   - Consolidate `carts_created` and `carts_abandoned` into single aggregate.




