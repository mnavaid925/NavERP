# Build Contract — Sub-module 8.16: Mobile Sales (Module 8: Sales Management System, `apps/sales`)

> Phase 3 Step 1. `BASE = 0de235c919024ab365ac10a999653cae1626f6f4`.
> Research: `.claude/tasks/research-sales-8.16.md`. Plan: `.claude/tasks/todo.md`.
> Next migration: **`0029_mobilesales`** (claimed).

---

## 0. Ownership Rulings (L29 / L36 / L37)

8.16 adds 4 tenant-scoped models and 1 specialized executive console (`MobileSalesDashboard`). It declares **zero duplicate customer, quote, sales order, currency, document, user, communication log, or geofence master**.

| Entity / Domain | Read-Only Master Owner | Where It Lives | 8.16's Relationship |
|---|---|---|---|
| **Customer Accounts & Visited Sites** | **core 0** | `apps/core/models/Party.py` | `core.Party` (with customer or prospect role) is the visited client/account (`FieldCheckIn.party`, `FieldCheckIn.contact`). Zero duplicate customer/client master. |
| **Street & Destination Addresses** | **core 0** | `apps/core/models/Address.py` | `core.Address` stores street addresses for customer locations. |
| **Originating & Field Quotes** | **Sales 8.5** | `apps/sales/models/QuoteProposalCPQ/CPQQuotes.py` | `sales.CPQQuote` (`CPQ-`) is linked as the on-site proposal generated from a visit (`FieldCheckIn.resulting_quote`, `MobileDealAlert.related_quote`). Zero duplicate proposal table. |
| **Sales Orders** | **SCM 4.5** | `apps/scm/models/OrderManagement/SalesOrders.py` | `scm.SalesOrder` (`SO-`) is the order header for field order collection. Zero duplicate order table. |
| **Operating Currencies** | **Accounting 2.2** | `apps/accounting/models/GeneralLedger/Currencies.py` | `accounting.Currency` governs quote/order amounts. |
| **Proof-of-Visit Photos & Attachments** | **core 0** | `apps/core/models/Document.py` | `core.Document` (`DOC-`) stores binary image proofs, shelf audit photos, and signed PDFs (`FieldCheckIn.photo_document`). Zero duplicate file table. |
| **Call Logs & Telephony Dispositions** | **CRM 1.5** | `apps/crm/models/ActivityManagement/CommunicationLogs.py` | `crm.CommunicationLog` (`COM-`) stores click-to-dial call outcomes and voicemail dispositions (`FieldCheckIn.communication_log`). |
| **Opportunities / Pipeline Deals** | **CRM 1.2** | `apps/crm/models/SalesForceAutomation/Opportunities.py` | `crm.Opportunity` (`OPP-`) is linked to field visits and mobile deal alerts (`FieldCheckIn.opportunity`, `MobileDealAlert.related_opportunity`). |
| **Sales Activity Rollups** | **Sales 8.8** | `apps/sales/models/SalesActivityTaskManagement/ActivityLogs.py` | `sales.ActivityLog` (`SAL-`) captures rep activity metrics. |
| **Users / Field Reps / Dispatchers** | **accounts 0** | `apps/accounts/models/User.py` | `settings.AUTH_USER_MODEL` (`accounts.User`) for field sales reps, route assignees, and alert recipients. Zero duplicate user master. |
| **Geofence Calculation** | **Dynamic Haversine** | Method on `FieldCheckIn` | Mathematical formula calculating GPS distance in metres dynamically, verified against target coordinates without requiring duplicate geofence catalog tables. |

---

## 1. Models — Every Field, Every Choice, Every Constraint

All models reside in `apps/sales/models/MobileSales/`.
Base: `apps.sales.models._base.TenantNumbered` (includes `tenant` FK `core.Tenant`, `number = CharField(max_length=20, editable=False)`, `created_at`, `updated_at`).

### 1.1 `FieldSalesRoute` (`FieldSalesRoutes.py`) — `NUMBER_PREFIX = "FSR"`

Represents an outside sales rep's planned daily multi-stop itinerary and travel path.

```python
ROUTE_STATUS_CHOICES = [
    ("draft", "Draft"),
    ("scheduled", "Scheduled"),
    ("in_progress", "In Progress"),
    ("completed", "Completed"),
    ("cancelled", "Cancelled"),
]

OPTIMIZATION_STATUS_CHOICES = [
    ("unoptimized", "Unoptimized Sequence"),
    ("optimized", "Route Optimized"),
    ("manual_order", "Manual Custom Order"),
]
```

| Field | Type | Attributes & Clean Guards |
|---|---|---|
| `name` | `CharField(max_length=200)` | Required itinerary title. |
| `sales_rep` | `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="field_sales_routes")` | Assigned outside sales rep. |
| `route_date` | `DateField(default=timezone.now)` | Date of execution. Indexed. |
| `status` | `CharField(max_length=20, choices=ROUTE_STATUS_CHOICES, default="scheduled")` | Lifecycle state. Indexed. |
| `start_location` | `CharField(max_length=255, blank=True)` | Starting waypoint / hub. |
| `end_location` | `CharField(max_length=255, blank=True)` | Ending waypoint / return depot. |
| `total_stops` | `PositiveIntegerField(default=0)` | Count of scheduled visit stops. |
| `completed_stops` | `PositiveIntegerField(default=0)` | Count of completed check-outs. |
| `planned_distance_km` | `DecimalField(max_digits=8, decimal_places=2, default=Decimal("0.00"), validators=[MinValueValidator(0)])` | Estimated route distance. |
| `actual_distance_km` | `DecimalField(max_digits=8, decimal_places=2, default=Decimal("0.00"), validators=[MinValueValidator(0)])` | Recorded odometer / travel distance. |
| `estimated_duration_minutes` | `PositiveIntegerField(default=0)` | Estimated driving + meeting time. |
| `actual_duration_minutes` | `PositiveIntegerField(default=0)` | Recorded time from departure to completion. |
| `optimization_status` | `CharField(max_length=20, choices=OPTIMIZATION_STATUS_CHOICES, default="unoptimized")` | Routing optimization algorithm state. |
| `notes` | `TextField(blank=True)` | Route briefing / dispatcher notes. |

- `Meta.ordering = ["-route_date", "-created_at"]`
- `Meta.constraints`: `UniqueConstraint(fields=["tenant", "number"], name="sales_fsr_ten_num_uniq")`
- `Meta.indexes`:
  - `Index(fields=["tenant", "status"], name="sales_fsr_ten_stat_idx")`
  - `Index(fields=["tenant", "sales_rep"], name="sales_fsr_ten_rep_idx")`
  - `Index(fields=["tenant", "route_date"], name="sales_fsr_ten_date_idx")`
- `clean()`:
  - If `completed_stops > total_stops`, raise `ValidationError`.
  - Validate tenant isolation for `sales_rep`.
- Methods:
  - `completion_rate_pct`: returns `int(round((completed_stops / total_stops) * 100))` if `total_stops > 0` else 0.
  - `progress_display`: returns `f"{completed_stops}/{total_stops} Stops"`.

---

### 1.2 `FieldCheckIn` (`FieldCheckIns.py`) — `NUMBER_PREFIX = "CHK"`

Captures a physical client visit, GPS stamp, geofence radius compliance, on-site duration, visit outcome, and proof photo.

```python
VERIFICATION_STATUS_CHOICES = [
    ("verified", "Verified On-Site"),
    ("out_of_range", "Out of Range (>150m)"),
    ("gps_unavailable", "GPS Unavailable"),
    ("manual_override", "Manual Override"),
]

VISIT_PURPOSE_CHOICES = [
    ("prospecting", "Prospecting / Cold Call"),
    ("presentation", "Product Demo / Presentation"),
    ("quote_review", "Quote Review & Negotiation"),
    ("order_collection", "Order Taking / Restock"),
    ("relationship", "Account Review / Check-In"),
    ("audit", "Merchandising / Stock Audit"),
    ("service_check", "Service / Support Follow-Up"),
]

VISIT_OUTCOME_CHOICES = [
    ("successful", "Successful Visit"),
    ("follow_up_needed", "Follow-Up Required"),
    ("quote_requested", "Quote Requested"),
    ("order_placed", "Order Placed"),
    ("decision_maker_unavailable", "Decision Maker Unavailable"),
    ("rescheduled", "Rescheduled"),
    ("cancelled", "Cancelled"),
]
```

| Field | Type | Attributes & Clean Guards |
|---|---|---|
| `route` | `ForeignKey("sales.FieldSalesRoute", on_delete=models.SET_NULL, null=True, blank=True, related_name="check_ins")` | Parent scheduled route (optional for ad-hoc drop-ins). |
| `stop_number` | `PositiveIntegerField(default=1)` | Sequence order on the route. |
| `party` | `ForeignKey("core.Party", on_delete=models.CASCADE, related_name="field_check_ins")` | Visited customer / client account. |
| `contact` | `ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="contact_check_ins")` | Person met with on-site. |
| `opportunity` | `ForeignKey("crm.Opportunity", on_delete=models.SET_NULL, null=True, blank=True, related_name="field_check_ins")` | Pipeline deal discussed. |
| `sales_rep` | `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="field_check_ins")` | Outside sales representative. |
| `check_in_at` | `DateTimeField(default=timezone.now)` | Arrival timestamp. |
| `check_in_lat` | `DecimalField(max_digits=9, decimal_places=6)` | GPS arrival latitude (-90 to +90). |
| `check_in_lng` | `DecimalField(max_digits=9, decimal_places=6)` | GPS arrival longitude (-180 to +180). |
| `target_lat` | `DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)` | Customer address target latitude. |
| `target_lng` | `DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)` | Customer address target longitude. |
| `geofence_radius_m` | `PositiveIntegerField(default=150)` | Radius tolerance in metres. |
| `distance_from_target_m` | `DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)` | Calculated Haversine distance. |
| `is_geofence_verified` | `BooleanField(default=False)` | True if distance <= geofence_radius_m. |
| `verification_status` | `CharField(max_length=20, choices=VERIFICATION_STATUS_CHOICES, default="verified")` | Geofence verification status. |
| `check_out_at` | `DateTimeField(null=True, blank=True)` | Departure timestamp. |
| `check_out_lat` | `DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)` | Departure latitude. |
| `check_out_lng` | `DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)` | Departure longitude. |
| `duration_minutes` | `PositiveIntegerField(null=True, blank=True)` | Total on-site duration in minutes. |
| `is_force_checkout` | `BooleanField(default=False)` | True if closed via administrative override. |
| `visit_purpose` | `CharField(max_length=30, choices=VISIT_PURPOSE_CHOICES, default="presentation")` | Purpose of the visit. |
| `outcome` | `CharField(max_length=30, choices=VISIT_OUTCOME_CHOICES, default="successful")` | Result of meeting. |
| `notes` | `TextField(blank=True)` | Detailed discussion notes. |
| `next_step` | `CharField(max_length=255, blank=True)` | Actionable next step. |
| `next_step_due` | `DateField(null=True, blank=True)` | Follow-up deadline. |
| `photo_document` | `ForeignKey("core.Document", on_delete=models.SET_NULL, null=True, blank=True, related_name="check_in_photos")` | Proof-of-visit / shelf audit photo. |
| `resulting_quote` | `ForeignKey("sales.CPQQuote", on_delete=models.SET_NULL, null=True, blank=True, related_name="originating_check_ins")` | CPQ quote drafted on-site. |
| `communication_log` | `ForeignKey("crm.CommunicationLog", on_delete=models.SET_NULL, null=True, blank=True, related_name="field_check_ins")` | CRM call/visit interaction record. |

- `Meta.ordering = ["-check_in_at"]`
- `Meta.constraints`: `UniqueConstraint(fields=["tenant", "number"], name="sales_chk_ten_num_uniq")`
- `Meta.indexes`:
  - `Index(fields=["tenant", "party"], name="sales_chk_ten_party_idx")`
  - `Index(fields=["tenant", "sales_rep"], name="sales_chk_ten_rep_idx")`
  - `Index(fields=["tenant", "check_in_at"], name="sales_chk_ten_time_idx")`
  - `Index(fields=["tenant", "route"], name="sales_chk_ten_route_idx")`
- `clean()`:
  - If `check_out_at` is set, assert `check_out_at >= check_in_at`.
  - Validate latitude (-90 to 90) and longitude (-180 to 180).
  - Calculate `distance_from_target_m` if target coordinates exist using Haversine formula; set `is_geofence_verified = (distance_from_target_m <= geofence_radius_m)`.
  - Validate tenant isolation on all FKs.
- Methods:
  - `calculate_distance(lat1, lon1, lat2, lon2)`: Haversine distance in metres.
  - `calculate_duration()`: returns integer minutes between `check_in_at` and `check_out_at`.

---

### 1.3 `MobileDeviceSession` (`MobileDeviceSessions.py`) — `NUMBER_PREFIX = "MDS"`

Registers field sales mobile devices, manages push notification tokens, and tracks offline synchronization status.

```python
PLATFORM_CHOICES = [
    ("ios", "Apple iOS Native"),
    ("android", "Google Android Native"),
    ("web_pwa", "Progressive Web App (PWA)"),
]

SYNC_STATUS_CHOICES = [
    ("success", "Synchronized"),
    ("partial", "Partial Sync"),
    ("failed", "Sync Failed"),
    ("pending", "Pending Sync"),
]
```

| Field | Type | Attributes & Clean Guards |
|---|---|---|
| `user` | `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="mobile_device_sessions")` | Authenticated field user. |
| `device_uuid` | `CharField(max_length=64, db_index=True)` | Unique device identifier or browser fingerprint. |
| `device_name` | `CharField(max_length=120)` | Model / friendly name (e.g. "iPhone 15 Pro"). |
| `platform` | `CharField(max_length=20, choices=PLATFORM_CHOICES, default="web_pwa")` | Operating system / platform. |
| `app_version` | `CharField(max_length=32, blank=True)` | Client application release. |
| `push_token` | `CharField(max_length=255, blank=True)` | APNs / FCM push notification token. |
| `is_active` | `BooleanField(default=True)` | Active device toggle. |
| `is_trusted` | `BooleanField(default=True)` | Security trust approval flag. |
| `last_sync_at` | `DateTimeField(null=True, blank=True)` | Most recent successful delta sync. |
| `last_sync_status` | `CharField(max_length=20, choices=SYNC_STATUS_CHOICES, default="pending")` | Status of last sync attempt. |
| `offline_records_cached` | `PositiveIntegerField(default=0)` | Count of entities primed locally. |
| `pending_uploads_count` | `PositiveIntegerField(default=0)` | Count of local edits waiting upload. |
| `last_ip_address` | `GenericIPAddressField(null=True, blank=True)` | Last client IP address. |
| `last_known_lat` | `DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)` | Telemetry latitude. |
| `last_known_lng` | `DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)` | Telemetry longitude. |

- `Meta.ordering = ["-updated_at"]`
- `Meta.constraints`: `UniqueConstraint(fields=["tenant", "number"], name="sales_mds_ten_num_uniq")`
- `Meta.indexes`:
  - `Index(fields=["tenant", "user"], name="sales_mds_ten_usr_idx")`
  - `Index(fields=["tenant", "device_uuid"], name="sales_mds_ten_uuid_idx")`
  - `Index(fields=["tenant", "last_sync_status"], name="sales_mds_ten_stat_idx")`
- `clean()`: Validate tenant isolation for `user`.
- Methods:
  - `record_sync_event(status, cached_count=0, pending_count=0)`: updates timestamps and counts.
  - `is_outdated()`: returns True if last sync was > 24 hours ago.

---

### 1.4 `MobileDealAlert` (`MobileDealAlerts.py`) — `NUMBER_PREFIX = "MDA"`

High-urgency notifications delivered to outside reps for deal transitions, quote approval requests, and dispatch notices.

```python
ALERT_TYPE_CHOICES = [
    ("deal_stage_changed", "Deal Stage Advanced"),
    ("quote_approval_required", "Quote Discount Approval Required"),
    ("route_dispatched", "Daily Route Assigned"),
    ("checkin_reminder", "Check-In Reminder"),
    ("attainment_milestone", "Quota Attainment Milestone"),
    ("contract_expiring", "Contract Expiring Soon"),
]

URGENCY_CHOICES = [
    ("low", "Low Priority"),
    ("normal", "Normal"),
    ("high", "High Priority"),
    ("urgent", "Urgent Action Required"),
]

PUSH_STATUS_CHOICES = [
    ("pending", "Pending Dispatch"),
    ("sent", "Dispatched"),
    ("delivered", "Delivered"),
    ("failed", "Delivery Failed"),
]
```

| Field | Type | Attributes & Clean Guards |
|---|---|---|
| `recipient` | `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="mobile_deal_alerts")` | Field rep or manager recipient. |
| `device` | `ForeignKey("sales.MobileDeviceSession", on_delete=models.SET_NULL, null=True, blank=True, related_name="received_alerts")` | Target hardware device. |
| `alert_type` | `CharField(max_length=30, choices=ALERT_TYPE_CHOICES, default="deal_stage_changed")` | Category of alert. |
| `title` | `CharField(max_length=200)` | Notification headline. |
| `message` | `TextField()` | Detailed alert body. |
| `urgency` | `CharField(max_length=20, choices=URGENCY_CHOICES, default="normal")` | Priority weighting. |
| `related_opportunity` | `ForeignKey("crm.Opportunity", on_delete=models.SET_NULL, null=True, blank=True, related_name="mobile_alerts")` | Linked CRM deal. |
| `related_quote` | `ForeignKey("sales.CPQQuote", on_delete=models.SET_NULL, null=True, blank=True, related_name="mobile_alerts")` | Linked CPQ proposal. |
| `related_route` | `ForeignKey("sales.FieldSalesRoute", on_delete=models.SET_NULL, null=True, blank=True, related_name="mobile_alerts")` | Linked sales route. |
| `is_read` | `BooleanField(default=False)` | Read confirmation flag. |
| `read_at` | `DateTimeField(null=True, blank=True)` | Read confirmation timestamp. |
| `push_status` | `CharField(max_length=20, choices=PUSH_STATUS_CHOICES, default="pending")` | Delivery pipeline status. |
| `push_sent_at` | `DateTimeField(null=True, blank=True)` | Timestamp dispatched. |

- `Meta.ordering = ["-created_at"]`
- `Meta.constraints`: `UniqueConstraint(fields=["tenant", "number"], name="sales_mda_ten_num_uniq")`
- `Meta.indexes`:
  - `Index(fields=["tenant", "recipient"], name="sales_mda_ten_rec_idx")`
  - `Index(fields=["tenant", "alert_type"], name="sales_mda_ten_type_idx")`
  - `Index(fields=["tenant", "is_read"], name="sales_mda_ten_read_idx")`
  - `Index(fields=["tenant", "urgency"], name="sales_mda_ten_urg_idx")`
- `clean()`: Validate tenant isolation across all FKs.
- Methods:
  - `mark_as_read()`: sets `is_read=True` and `read_at=timezone.now()`.
  - `dispatch_alert()`: sets `push_status="sent"` and `push_sent_at=timezone.now()`.

---

## 2. Forms — Excluded Fields & Widgets

All forms live in `apps/sales/forms/MobileSales/`:
- `FieldSalesRoutes.py`: `FieldSalesRouteForm`, `FieldSalesRouteFilterForm`
- `FieldCheckIns.py`: `FieldCheckInForm`, `FieldCheckOutForm`, `FieldCheckInFilterForm`
- `MobileDeviceSessions.py`: `MobileDeviceSessionForm`, `MobileDeviceSessionFilterForm`
- `MobileDealAlerts.py`: `MobileDealAlertForm`, `MobileDealAlertFilterForm`

### 2.1 Form Exclusions (Mandatory — L20, L22)
- Excluded from all ModelForms: `tenant`, auto-generated `number`.
- Excluded from `FieldSalesRouteForm`: `completed_stops` (calculated dynamically from check-outs).
- Excluded from `FieldCheckInForm`: `check_in_at` (set automatically on check-in), `distance_from_target_m` (calculated by Haversine), `is_geofence_verified` (calculated by Haversine), `duration_minutes` (calculated on check-out), `is_force_checkout` (admin action only).
- Excluded from `MobileDeviceSessionForm`: `last_sync_at`, `offline_records_cached`, `pending_uploads_count`, `last_ip_address`, `last_known_lat`, `last_known_lng` (system telemetry).
- Excluded from `MobileDealAlertForm`: `is_read`, `read_at`, `push_status`, `push_sent_at`.

### 2.2 Widgets & Styling
- Dates: `forms.DateInput(attrs={"type": "date", "class": "form-input"})` (L22).
- Numbers/Decimals: `forms.NumberInput(attrs={"class": "form-input", "step": "any"})`.
- ForeignKeys / Choices: `forms.Select(attrs={"class": "form-select"})` with `tenant` filtering in `__init__`.
- TextAreas: `forms.Textarea(attrs={"class": "form-textarea", "rows": 3})`.

---

## 3. URLs — View Names & Route Patterns

URL package: `apps/sales/urls/MobileSales/`
- `FieldSalesRoutes.py`
- `FieldCheckIns.py`
- `MobileDeviceSessions.py`
- `MobileDealAlerts.py`
- `MobileSalesDashboards.py`

### Route Table
| View Name | Route Pattern | Function |
|---|---|---|
| `field_sales_route_list` | `routes/` | List, filter, paginate routes |
| `field_sales_route_create` | `routes/create/` | Create new sales route |
| `field_sales_route_detail` | `routes/<int:pk>/` | View route itinerary & stops |
| `field_sales_route_edit` | `routes/<int:pk>/edit/` | Edit route details |
| `field_sales_route_delete` | `routes/<int:pk>/delete/` | Delete route (POST only) |
| `field_sales_route_optimize` | `routes/<int:pk>/optimize/` | Trigger route sequence optimization |
| `field_check_in_list` | `check-ins/` | List, filter, paginate check-ins |
| `field_check_in_create` | `check-ins/create/` | Record arrival check-in with GPS |
| `field_check_in_detail` | `check-ins/<int:pk>/` | View check-in details & proof |
| `field_check_in_edit` | `check-ins/<int:pk>/edit/` | Edit check-in notes & outcome |
| `field_check_in_delete` | `check-ins/<int:pk>/delete/` | Delete check-in (POST only) |
| `field_check_in_checkout` | `check-ins/<int:pk>/checkout/` | Record departure check-out & duration |
| `mobile_device_session_list` | `devices/` | List registered mobile devices |
| `mobile_device_session_create` | `devices/create/` | Register mobile device |
| `mobile_device_session_detail` | `devices/<int:pk>/` | View device sync health |
| `mobile_device_session_edit` | `devices/<int:pk>/edit/` | Edit device trust & settings |
| `mobile_device_session_delete` | `devices/<int:pk>/delete/` | Delete device registration |
| `mobile_device_session_sync` | `devices/<int:pk>/sync/` | Trigger test sync manifest event |
| `mobile_deal_alert_list` | `alerts/` | List mobile push notifications |
| `mobile_deal_alert_create` | `alerts/create/` | Dispatch mobile deal alert |
| `mobile_deal_alert_detail` | `alerts/<int:pk>/` | View alert details |
| `mobile_deal_alert_edit` | `alerts/<int:pk>/edit/` | Edit alert |
| `mobile_deal_alert_delete` | `alerts/<int:pk>/delete/` | Delete alert |
| `mobile_deal_alert_mark_read` | `alerts/<int:pk>/read/` | Mark alert as read |
| `mobile_sales_dashboard` | `mobile-sales-dashboard/` | Executive field sales execution console |

All URLs registered under `app_name = "sales"`.

---

## 4. Context Keys (Strict Contract — L7 / L8)

To avoid silent-blank renders (L8) and `NoReverseMatch` 500s (L7), every view must supply exactly these keys:

### 4.1 `FieldSalesRoute`
- List (`field_sales_route_list`):
  - `page_obj`: paginated queryset of routes
  - `routes`: list of routes (`page_obj.object_list`)
  - `filter_form`: `FieldSalesRouteFilterForm` instance
  - `status_choices`: `ROUTE_STATUS_CHOICES`
  - `sales_reps`: queryset of tenant sales reps
  - `total_routes_count`: integer
  - `active_routes_count`: integer
- Detail (`field_sales_route_detail`):
  - `route`: `FieldSalesRoute` instance
  - `stops`: queryset of `FieldCheckIn` records attached to this route
  - `completion_rate`: integer percentage
- Form (`field_sales_route_create`, `field_sales_route_edit`):
  - `form`: `FieldSalesRouteForm`
  - `route`: `FieldSalesRoute` instance (in edit mode; None in create)
  - `is_edit`: boolean

### 4.2 `FieldCheckIn`
- List (`field_check_in_list`):
  - `page_obj`: paginated queryset of check-ins
  - `check_ins`: list of check-ins (`page_obj.object_list`)
  - `filter_form`: `FieldCheckInFilterForm`
  - `verification_choices`: `VERIFICATION_STATUS_CHOICES`
  - `purpose_choices`: `VISIT_PURPOSE_CHOICES`
  - `outcome_choices`: `VISIT_OUTCOME_CHOICES`
  - `total_checkins_count`: integer
  - `verified_checkins_count`: integer
- Detail (`field_check_in_detail`):
  - `check_in`: `FieldCheckIn` instance
  - `duration_display`: string formatting duration
- Form (`field_check_in_create`, `field_check_in_edit`):
  - `form`: `FieldCheckInForm`
  - `check_in`: `FieldCheckIn` instance (in edit mode; None in create)
  - `is_edit`: boolean

### 4.3 `MobileDeviceSession`
- List (`mobile_device_session_list`):
  - `page_obj`: paginated queryset of devices
  - `devices`: list of devices (`page_obj.object_list`)
  - `filter_form`: `MobileDeviceSessionFilterForm`
  - `platform_choices`: `PLATFORM_CHOICES`
  - `sync_status_choices`: `SYNC_STATUS_CHOICES`
  - `total_devices_count`: integer
  - `active_devices_count`: integer
- Detail (`mobile_device_session_detail`):
  - `device`: `MobileDeviceSession` instance
  - `recent_alerts`: queryset of alerts received by this device
- Form (`mobile_device_session_create`, `mobile_device_session_edit`):
  - `form`: `MobileDeviceSessionForm`
  - `device`: `MobileDeviceSession` instance (in edit mode; None in create)
  - `is_edit`: boolean

### 4.4 `MobileDealAlert`
- List (`mobile_deal_alert_list`):
  - `page_obj`: paginated queryset of alerts
  - `alerts`: list of alerts (`page_obj.object_list`)
  - `filter_form`: `MobileDealAlertFilterForm`
  - `alert_type_choices`: `ALERT_TYPE_CHOICES`
  - `urgency_choices`: `URGENCY_CHOICES`
  - `total_alerts_count`: integer
  - `unread_alerts_count`: integer
- Detail (`mobile_deal_alert_detail`):
  - `alert`: `MobileDealAlert` instance
- Form (`mobile_deal_alert_create`, `mobile_deal_alert_edit`):
  - `form`: `MobileDealAlertForm`
  - `alert`: `MobileDealAlert` instance (in edit mode; None in create)
  - `is_edit`: boolean

### 4.5 `MobileSalesDashboard` (`mobile_sales_dashboard`)
- `total_routes_today`: integer
- `completed_stops_today`: integer
- `pending_stops_today`: integer
- `geofence_compliance_pct`: integer
- `active_routes`: queryset of today's routes
- `recent_checkins`: queryset of latest check-ins
- `urgent_alerts`: queryset of unread urgent deal alerts
- `active_devices`: queryset of trusted mobile devices

---

## 5. Templates (13 Total)

Folder layout: `templates/sales/mobilesales/`
- `fieldsalesroute/`
  - `list.html`
  - `detail.html`
  - `form.html`
- `fieldcheckin/`
  - `list.html`
  - `detail.html`
  - `form.html`
- `mobiledevicesession/`
  - `list.html`
  - `detail.html`
  - `form.html`
- `mobiledealalert/`
  - `list.html`
  - `detail.html`
  - `form.html`
- `dashboard/`
  - `mobile_sales_dashboard.html`

Badges: Color-named badges ONLY (`.badge-green`, `.badge-red`, `.badge-amber`, `.badge-info`, `.badge-muted`, `.badge-slate`). Never semantic `-success` or `-danger` (L33).

---

## 6. Navigation Wire-Up (`apps/core/navigation.py`)

Add `LIVE_LINKS["8.16"]` mapping all 5 NavERP.md feature bullets:
```python
"8.16": {
    "Mobile CRM Access": "sales:mobile_device_session_list",
    "Field Sales Tools": "sales:field_sales_route_list",
    "Mobile Quoting & Approvals": "sales:field_check_in_list",
    "Voice & Call Integration": "crm:communicationlog_list",
    "Mobile Dashboards & Alerts": "sales:mobile_sales_dashboard",
    # Extra live leaves
    "Field Sales Routes": "sales:field_sales_route_list",
    "Field Check-Ins": "sales:field_check_in_list",
    "Mobile Device Sessions": "sales:mobile_device_session_list",
    "Mobile Deal Alerts": "sales:mobile_deal_alert_list",
    "Mobile Sales Dashboard": "sales:mobile_sales_dashboard",
},
```

---

## 7. Seeder Plan (`apps/sales/management/commands/seed_sales.py`)

Extend `seed_sales.py` with `_seed_mobile_sales(self, tenant, user)`:
- Guard: `if FieldSalesRoute.objects.filter(tenant=tenant).exists(): return`
- Creates 2-3 realistic `FieldSalesRoute` records per tenant.
- Creates 4-6 `FieldCheckIn` records linked to customer parties, route stops, and GPS coordinates with verified geofences, duration, visit outcomes, and attached documents/quotes.
- Creates 2 `MobileDeviceSession` records (iOS, Android) per tenant.
- Creates 3-4 `MobileDealAlert` records with mixed urgency and read status.
- Idempotent and clean.
