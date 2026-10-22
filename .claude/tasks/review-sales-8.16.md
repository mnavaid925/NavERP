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

---

## Pass 2: explorer

### Critical
*(None)*

### Important
- [ ] **I5** (`apps/sales/models/MobileSales/FieldCheckIns.py:204-213`): Cross-tenant foreign key isolation gap in `FieldCheckIn.clean()`. The validation loop checks `party`, `sales_rep`, `route`, `photo_document`, and `resulting_quote`, but omits `contact`, `opportunity`, and `communication_log`. All three are tenant-scoped models and must be validated against `self.tenant_id`.

### Minor
- [ ] **M3** (`apps/sales/models/MobileSales/FieldSalesRoutes.py:105-110`): `generate_navigation_url()` returns `"https://maps.google.com"` fallback when no waypoints are set, causing the "Open Navigation" button to always render. Return `None` when locations are empty.
- [ ] **M4** (`apps/sales/models/MobileSales/FieldCheckIns.py:177-180`): Departure GPS coordinates (`check_out_lat`, `check_out_lng`) lack range validation (-90 to 90, -180 to 180) in `clean()`, unlike arrival coordinates.
- [ ] **M5** (`apps/sales/views/MobileSales/MobileDealAlerts.py:85-88, 177-183`): Audit logging omission when marking alerts as read in `mobile_deal_alert_mark_read` and auto-read in detail view.

---

## Pass 3: frontend-reviewer

### Critical
*(None)*

### Important
- [ ] **I6** (`templates/sales/mobilesales/dashboard/mobile_sales_dashboard.html:147-151`): Incomplete Route Status Badge mapping on dashboard. Lumps all statuses other than `in_progress` into "Scheduled" rather than mapping `completed` (green), `cancelled` (muted), and `draft` (info).

### Minor
- [ ] **M6** (`templates/sales/mobilesales/**/*.html`): Missing `aria-label` attributes on icon-only buttons across dashboard and list/detail action columns.
- [ ] **M7** (`templates/sales/mobilesales/**/*.html`): Stat cards use inline Tailwind background/color utilities instead of `.stat-icon.blue`, `.stat-icon.green`, `.stat-icon.orange`, `.stat-icon.purple` theme classes.

---

## Pass 4: performance-reviewer

### Critical
*(None)*

### Important
- [ ] **I7** (`apps/sales/views/MobileSales/FieldCheckIns.py:28-32`): N+1 query on contact person in `field_check_in_list`. Add `"contact"` to `select_related()` to eliminate extra query per row in list template.
- [ ] **I8** (`apps/sales/forms/MobileSales/MobileDealAlerts.py:48`): Chained N+1 via `__str__` on Device Queryset in `MobileDealAlertForm`. Add `.select_related("user")` to `self.fields["device"].queryset`.
- [ ] **I9** (`apps/sales/views/MobileSales/MobileSalesDashboards.py:48-52` & `templates/sales/mobilesales/dashboard/mobile_sales_dashboard.html:93-94`): Sliced `urgent_alerts[:6]` `.count()` fires subquery counts and caps KPI card at 6. Compute `urgent_alerts_count` on un-sliced queryset.

### Minor
- [ ] **M8** (`apps/sales/views/MobileSales/MobileSalesDashboards.py:20-25`): Multiple database round-trips for daily route aggregates. Combine into a single `.aggregate()` call.
- [ ] **M9** (`apps/sales/views/MobileSales/MobileSalesDashboards.py:27-29`): `check_in_at__date=today` lookup prevents index seek. Use datetime range bounds `check_in_at__gte` and `check_in_at__lt`.
- [ ] **M10** (`templates/sales/mobilesales/fieldsalesroute/detail.html:173`, `mobiledevicesession/detail.html:166`): Redundant `.count()` query before iterating stops/alerts; use `|length`.
