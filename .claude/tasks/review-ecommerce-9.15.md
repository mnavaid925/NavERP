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

