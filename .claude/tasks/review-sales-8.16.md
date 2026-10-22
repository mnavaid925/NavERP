# Phase 4 Review Findings — Sub-module 8.16: Mobile Sales (apps/sales)

**BASE Commit**: `0de235c919024ab365ac10a999653cae1626f6f4`
**Target Sub-module**: 8.16 Mobile Sales (`apps/sales`)

---

## Pass 1: code-reviewer

### Critical
- [ ] **C1** (`apps/sales/views/MobileSales/*.py`): Missing `@transaction.atomic` across all 16 state-mutating views (`FieldSalesRoutes`, `FieldCheckIns`, `MobileDeviceSessions`, `MobileDealAlerts`). Multi-record mutations and audit logging must be atomic.

### Important
- [ ] **I1** (`apps/sales/views/MobileSales/FieldCheckIns.py:182-184`): Inaccurate `completed_stops` decrement on check-in deletion. Deleting an in-progress or cancelled visit without checkout erroneously decrements `route.completed_stops`. Recalculate dynamically: `route.completed_stops = route.check_ins.filter(check_out_at__isnull=False).count()`.
- [ ] **I2** (`apps/sales/models/MobileSales/FieldSalesRoutes.py:87`): `FieldSalesRoute.clean()` allows `completed_stops > total_stops` when `total_stops == 0` due to `and self.total_stops > 0`. Remove `and self.total_stops > 0` to enforce contract.
- [ ] **I3** (`templates/sales/mobilesales/*/list.html`): Pagination links hardcode only `q` and one primary filter, dropping secondary GET parameters across all 4 list views.
- [ ] **I4** (`apps/sales/views/MobileSales/FieldSalesRoutes.py:155-168`): Missing status lifecycle guard on `field_sales_route_optimize`. Route sequence optimization should reject `completed` or `cancelled` routes.

### Minor
- [ ] **M1** (`apps/sales/models/MobileSales/FieldCheckIns.py:204-213`): `FieldCheckIn.clean()` omits `contact`, `opportunity`, and `communication_log` from the tenant isolation validation loop.
- [ ] **M2** (`apps/sales/views/MobileSales/FieldSalesRoutes.py:58`): Benign unused context key `status_choices` passed to template context where `filter_form.status` is rendered.
