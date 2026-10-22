# Consolidated Review Findings — Sub-module 8.16: Mobile Sales (apps/sales)

**BASE Commit**: `0de235c919024ab365ac10a999653cae1626f6f4`
**Target Sub-module**: 8.16 Mobile Sales (`apps/sales`)
**Scope**: 4 models, 9 forms, 23 views, 25 URLs, 14 templates, migration 0029, admin, navigation, seeder.
**Review Passes**:
1. `code-reviewer`: Architectural patterns, transaction atomicity, lifecycle guards.
2. `explorer`: Contract conformance, dual-layer re-exports, spine reuse, URL namespace.
3. `frontend-reviewer`: Template theme.css color badges, pagination query preservation, UI completeness.
4. `performance-reviewer`: ORM query efficiency, select_related, prefetch_related, indexing.
5. `qa-smoke-tester`: Runtime test client sweep (100/100 assertions passed), form validation defaults.
6. `security-reviewer`: Multi-tenant isolation, horizontal authorization, privilege gates, CSRF/XSS.

---

## Critical

- [ ] **C1** (`apps/sales/views/MobileSales/*.py`): Missing `@transaction.atomic` across all 16 state-mutating views (`FieldSalesRoutes`, `FieldCheckIns`, `MobileDeviceSessions`, `MobileDealAlerts`). Multi-record mutations and audit logging must be atomic.

---

## Important

- [ ] **I1** (`apps/sales/views/MobileSales/FieldCheckIns.py:182-184`): Inaccurate `completed_stops` decrement on check-in deletion. Recalculate dynamically: `route.completed_stops = route.check_ins.filter(check_out_at__isnull=False).count()`.
- [ ] **I2** (`apps/sales/models/MobileSales/FieldSalesRoutes.py:87`): `FieldSalesRoute.clean()` allows `completed_stops > total_stops` when `total_stops == 0` due to `and self.total_stops > 0`. Remove `and self.total_stops > 0` to enforce contract.
- [ ] **I3** (`templates/sales/mobilesales/*/list.html`): Pagination links hardcode only `q` and one primary filter, dropping secondary GET parameters across all 4 list views. Include all filter form GET parameters in pagination links.
- [ ] **I4** (`apps/sales/views/MobileSales/FieldSalesRoutes.py:155-168`): Missing status lifecycle guard on `field_sales_route_optimize`. Route sequence optimization should reject `completed` or `cancelled` routes with an error message.
- [ ] **I5** (`apps/sales/models/MobileSales/FieldCheckIns.py:204-213`): Cross-tenant foreign key isolation gap in `FieldCheckIn.clean()`. Add `contact`, `opportunity`, and `communication_log` to the tenant isolation validation loop.
- [ ] **I6** (`templates/sales/mobilesales/dashboard/mobile_sales_dashboard.html:147-151`): Incomplete Route Status Badge mapping on dashboard. Lumps all statuses other than `in_progress` into "Scheduled". Map all choices with fallback.
- [ ] **I7** (`apps/sales/views/MobileSales/FieldCheckIns.py:28-32`): N+1 query on contact person in `field_check_in_list`. Add `"contact"` to `select_related()` to eliminate extra query per row in list template.
- [ ] **I8** (`apps/sales/forms/MobileSales/MobileDealAlerts.py:48`): Chained N+1 via `__str__` on Device Queryset in `MobileDealAlertForm`. Add `.select_related("user")` to `self.fields["device"].queryset`.
- [ ] **I9** (`apps/sales/views/MobileSales/MobileSalesDashboards.py:48-52` & `templates/sales/mobilesales/dashboard/mobile_sales_dashboard.html:93-94`): Sliced `urgent_alerts[:6]` `.count()` fires subquery counts and caps KPI card at 6. Compute `urgent_alerts_count` on un-sliced queryset.
- [ ] **I10** (`apps/sales/forms/MobileSales/FieldSalesRoutes.py:14-31` & `apps/sales/models/MobileSales/FieldSalesRoutes.py:53-60`): Execution metrics (`actual_distance_km`, `actual_duration_minutes`, `planned_distance_km`, `estimated_duration_minutes`) default to 0 on model but lack `required=False` in `FieldSalesRouteForm`, rejecting route creation when omitted. Set `required=False`.
- [ ] **I11** (`apps/sales/forms/MobileSales/*.py`): Defaulted technical fields (`geofence_radius_m`, `verification_status` in `FieldCheckInForm`; `last_sync_status` in `MobileDeviceSessionForm`; `urgency` in `MobileDealAlertForm`) lack `required=False` in forms. Set `required=False`.
- [ ] **I12** (`apps/sales/views/MobileSales/MobileDealAlerts.py:160-183`): Horizontal authorization on alert mark-read and deletion. Restrict `mobile_deal_alert_mark_read` and `mobile_deal_alert_delete` to recipient or tenant admin (`getattr(request.user, "is_tenant_admin", False)`).
- [ ] **I13** (`apps/sales/views/MobileSales/MobileDeviceSessions.py:113-155`): Ownership/admin guards on device session deletion and edit. Enforce `device.user == request.user` or tenant admin.
- [ ] **I14** (`apps/sales/forms/MobileSales/MobileDeviceSessions.py:25`): Security governance trust bypass on `MobileDeviceSession.is_trusted`. Disable or restrict `is_trusted` editing to tenant admin.
- [ ] **I15** (`apps/sales/views/MobileSales/FieldCheckIns.py:166-187`): Unrestricted deletion of GPS visit audit records in `field_check_in_delete`. Enforce `check_in.sales_rep == request.user` or tenant admin.

---

## Minor

- [ ] **M1** (`apps/sales/views/MobileSales/FieldSalesRoutes.py:58`): Benign unused context key `status_choices` passed to template context where `filter_form.status` is rendered.
- [ ] **M2** (`apps/sales/models/MobileSales/FieldSalesRoutes.py:105-110`): `generate_navigation_url()` returns `"https://maps.google.com"` fallback when no waypoints are set, causing the "Open Navigation" button to always render. Return `None` when locations are empty.
- [ ] **M3** (`apps/sales/models/MobileSales/FieldCheckIns.py:177-180`): Departure GPS coordinates (`check_out_lat`, `check_out_lng`) lack range validation (-90 to 90, -180 to 180) in `FieldCheckIn.clean()`.
- [ ] **M4** (`apps/sales/views/MobileSales/MobileDealAlerts.py:85-88, 177-183`): Audit logging omission when marking alerts as read in `mobile_deal_alert_mark_read`.
- [ ] **M5** (`templates/sales/mobilesales/**/*.html`): Missing `aria-label` attributes on icon-only action buttons.
- [ ] **M6** (`templates/sales/mobilesales/**/*.html`): Stat cards use inline Tailwind background/color utilities instead of `.stat-icon.color` classes.
- [ ] **M7** (`apps/sales/views/MobileSales/MobileSalesDashboards.py:20-25`): Multiple database round-trips for daily route aggregates. Combine into a single `.aggregate()` call.
- [ ] **M8** (`apps/sales/views/MobileSales/MobileSalesDashboards.py:27-29`): `check_in_at__date=today` lookup prevents index seek. Use datetime range bounds `check_in_at__gte` and `check_in_at__lt`.
- [ ] **M9** (`templates/sales/mobilesales/fieldsalesroute/detail.html:173`, `mobiledevicesession/detail.html:166`): Redundant `.count()` query before iterating stops/alerts; use `|length`.
- [ ] **M10** (`templates/sales/mobilesales/dashboard/mobile_sales_dashboard.html:16-17`): Console header title is "Field Sales & Mobile Execution" while navigation is "Mobile Sales". Align terminology to "Mobile Sales Console".
- [ ] **M11** (`templates/sales/mobilesales/mobiledevicesession/detail.html:147-154`): Push token plaintext display in form/detail. Mask display.
- [ ] **M12** (`apps/sales/views/MobileSales/MobileDealAlerts.py:99-102`): Validate device parameter in `mobile_deal_alert_create` belongs to tenant.
