# Contract — Sub-module 9.16: Mobile Commerce (Module 9: eCommerce Management System, `ecommerce`)

- **Sub-module:** 9.16 Mobile Commerce · **Module:** 9 eCommerce Management System · **App:** `apps/ecommerce`
- **Date:** 2026-11-02 · **Status:** FROZEN PRE-BUILD CONTRACT · **Phase:** 3.1 Spec
- **App Status:** Extending existing `apps/ecommerce/`. Next incremental migration: `0030_...`
- **Package Layout:** `MobileCommerce/` across `models/`, `forms/`, `views/`, `urls/`, and templates `templates/ecommerce/mobile/`.

---

## 1. Models & CHOICES Contract

All top-level models inherit from `apps.ecommerce.models._base.TenantNumbered` (`tenant`, `number`, `created_at`, `updated_at`).

### 1.1 `MobileAppConfig` (`apps/ecommerce/models/MobileCommerce/MobileAppConfigs.py`)
- **Table:** `ecommerce_mobile_app_config`
- **Number Prefix:** `EMAC` (`EMAC-00001`)
- **CHOICES:**
  - `DISPLAY_MODE_CHOICES = [('standalone', 'Standalone (No Browser UI)'), ('fullscreen', 'Fullscreen (Immersive)'), ('minimal-ui', 'Minimal UI (Limited Controls)'), ('browser', 'Standard Browser Tab')]`
  - `ORIENTATION_CHOICES = [('portrait', 'Portrait Preferred'), ('landscape', 'Landscape Preferred'), ('any', 'Auto / Any Orientation')]`
  - `CACHE_STRATEGY_CHOICES = [('stale_while_revalidate', 'Stale While Revalidate (Fast + Background Sync)'), ('cache_first', 'Cache First (Offline Resilient)'), ('network_first', 'Network First with Cache Fallback'), ('network_only', 'Network Only (No Offline Storage)')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `app_name`: `CharField(max_length=120, default="NavERP Mobile Store", help_text="Full application name displayed on splash screens")`
  - `short_name`: `CharField(max_length=50, default="NavERP Store", help_text="Short name used on mobile home-screen icon launcher")`
  - `description`: `TextField(blank=True, default="", help_text="Description for web app manifest and app stores")`
  - `theme_color`: `CharField(max_length=7, default="#2563EB", help_text="Brand hex color for browser status bar")`
  - `background_color`: `CharField(max_length=7, default="#FFFFFF", help_text="Splash screen background hex color")`
  - `display_mode`: `CharField(max_length=20, choices=DISPLAY_MODE_CHOICES, default="standalone")`
  - `orientation`: `CharField(max_length=20, choices=ORIENTATION_CHOICES, default="portrait")`
  - `start_url`: `CharField(max_length=255, default="/", help_text="Entry route when launched from home screen")`
  - `scope`: `CharField(max_length=255, default="/", help_text="Navigation boundary for progressive web app")`
  - `icon_192_url`: `CharField(max_length=255, blank=True, default="/static/img/icons/icon-192.png", help_text="192x192 PNG launcher icon URL")`
  - `icon_512_url`: `CharField(max_length=255, blank=True, default="/static/img/icons/icon-512.png", help_text="512x512 PNG splash icon URL")`
  - `offline_cache_strategy`: `CharField(max_length=30, choices=CACHE_STRATEGY_CHOICES, default="stale_while_revalidate")`
  - `offline_fallback_html`: `TextField(blank=True, default="<div class='offline-card text-center p-8'><h2 class='text-xl font-bold mb-2'>You are offline</h2><p class='text-slate-500'>Saved items and cached catalog products remain available.</p></div>", help_text="Offline fallback HTML payload when network is unavailable")`
  - `enable_pwa`: `BooleanField(default=True, help_text="Enable progressive web app manifest and service worker")`
  - `enable_biometric_login`: `BooleanField(default=True, help_text="Allow FaceID/TouchID/Fingerprint authentication in native shell")`
  - `min_ios_version`: `CharField(max_length=16, default="15.0", help_text="Minimum supported iOS version")`
  - `min_android_version`: `CharField(max_length=16, default="10.0", help_text="Minimum supported Android API level")`
  - `apple_pay_merchant_id`: `CharField(max_length=100, blank=True, default="", help_text="Apple Pay merchant identifier (e.g. merchant.com.company.store)")`
  - `google_pay_gateway_id`: `CharField(max_length=100, blank=True, default="", help_text="Google Pay merchant gateway profile identifier")`
  - `enable_apple_pay`: `BooleanField(default=False, help_text="Enable Apple Pay native express checkout")`
  - `enable_google_pay`: `BooleanField(default=False, help_text="Enable Google Pay native express checkout")`
  - `enable_in_app_wallet`: `BooleanField(default=True, help_text="Allow customers to store prepaid account balances")`
  - `enable_express_checkout`: `BooleanField(default=True, help_text="Enable 1-tap mobile buy-now checkout bypassing cart review")`
  - `is_active`: `BooleanField(default=True, help_text="Active primary configuration for tenant")`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='ecommerce_emac_tenant_num_uniq')`
  - `Index(fields=['tenant', 'is_active'], name='idx_emac_ten_act')`
  - `Index(fields=['tenant', 'enable_pwa'], name='idx_emac_ten_pwa')`
- **Ordering:** `['-is_active', '-created_at']`
- **Key Methods:** `generate_manifest_dict()`

---

### 1.2 `MobileDeviceRegistration` (`apps/ecommerce/models/MobileCommerce/MobileDeviceRegistrations.py`)
- **Table:** `ecommerce_mobile_device_registration`
- **Number Prefix:** `EMDR` (`EMDR-00001`)
- **CHOICES:**
  - `PLATFORM_CHOICES = [('ios', 'Apple iOS'), ('android', 'Google Android'), ('pwa_web', 'PWA / Mobile Web Browser')]`
  - `PUSH_PROVIDER_CHOICES = [('apns', 'Apple Push Notification Service (APNs)'), ('fcm', 'Firebase Cloud Messaging (FCM)'), ('web_push', 'W3C Web Push Protocol'), ('none', 'No Push Configured')]`
  - `LOCATION_PERMISSION_CHOICES = [('always', 'Always Allow in Background'), ('while_in_use', 'Only While Using App'), ('denied', 'Location Permission Denied'), ('not_determined', 'Prompt Not Yet Triggered')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `customer_profile`: `ForeignKey('ecommerce.CustomerAccountProfile', null=True, blank=True, on_delete=SET_NULL, related_name='mobile_devices')`
  - `party`: `ForeignKey('core.Party', null=True, blank=True, on_delete=SET_NULL, related_name='mobile_devices')`
  - `device_uuid`: `CharField(max_length=64, db_index=True, help_text="Unique installation UUID or device fingerprint")`
  - `device_platform`: `CharField(max_length=20, choices=PLATFORM_CHOICES, default="ios")`
  - `device_model`: `CharField(max_length=100, blank=True, default="", help_text="Hardware model (e.g. iPhone 15 Pro, Pixel 8)")`
  - `os_version`: `CharField(max_length=30, blank=True, default="", help_text="OS version string (e.g. iOS 17.4.1, Android 14)")`
  - `app_version`: `CharField(max_length=30, blank=True, default="1.0.0", help_text="Installed native shell or PWA build version")`
  - `push_token`: `CharField(max_length=255, blank=True, default="", help_text="Device push notification registration token")`
  - `push_provider`: `CharField(max_length=20, choices=PUSH_PROVIDER_CHOICES, default="fcm")`
  - `push_enabled`: `BooleanField(default=True, help_text="Customer notification opt-in toggle")`
  - `biometric_enrolled`: `BooleanField(default=False, help_text="Device supports and user enrolled biometric authentication")`
  - `location_permission`: `CharField(max_length=20, choices=LOCATION_PERMISSION_CHOICES, default="not_determined")`
  - `badge_count`: `PositiveIntegerField(default=0, help_text="Current unread notification app badge count")`
  - `last_latitude`: `DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, help_text="Last reported device GPS latitude")`
  - `last_longitude`: `DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, help_text="Last reported device GPS longitude")`
  - `last_active_at`: `DateTimeField(null=True, blank=True, help_text="Last recorded telemetry or API ping timestamp")`
  - `is_active`: `BooleanField(default=True, help_text="Active device capable of receiving messages")`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='ecommerce_emdr_tenant_num_uniq')`
  - `UniqueConstraint(fields=['tenant', 'device_uuid'], name='ecommerce_emdr_ten_uuid_uniq')`
  - `Index(fields=['tenant', 'device_platform'], name='idx_emdr_ten_plat')`
  - `Index(fields=['tenant', 'customer_profile'], name='idx_emdr_ten_cust')`
  - `Index(fields=['tenant', 'is_active'], name='idx_emdr_ten_act')`
- **Ordering:** `['-last_active_at', '-created_at']`
- **Key Methods:** `record_activity(lat, lng)`, `reset_badge_count()`

---

### 1.3 `MobilePushCampaign` (`apps/ecommerce/models/MobileCommerce/MobilePushCampaigns.py`)
- **Table:** `ecommerce_mobile_push_campaign`
- **Number Prefix:** `EMPC` (`EMPC-00001`)
- **CHOICES:**
  - `CAMPAIGN_TYPE_CHOICES = [('promotional', 'Promotional Broadcast / Flash Sale'), ('transactional', 'Transactional / Order Status Update'), ('abandoned_cart', 'Abandoned Cart Recovery'), ('price_drop', 'Wishlist Price Drop Alert'), ('back_in_stock', 'Back in Stock Notification'), ('geofence_proximity', 'Geofence Proximity Welcome')]`
  - `TARGET_PLATFORM_CHOICES = [('all', 'All Platforms (iOS, Android, PWA)'), ('ios_only', 'Apple iOS Devices Only'), ('android_only', 'Google Android Devices Only'), ('pwa_only', 'PWA Web Push Subscribers Only')]`
  - `DEEP_LINK_TYPE_CHOICES = [('home', 'Storefront Home / Dashboard'), ('product', 'Catalog Product Detail Page'), ('category', 'Category Collection Page'), ('cart', 'Shopping Cart / Checkout'), ('coupon', 'Claim Coupon Promotion'), ('custom_url', 'Custom In-App Deep Link / URL')]`
  - `STATUS_CHOICES = [('draft', 'Draft (Editing)'), ('scheduled', 'Scheduled for Broadcast'), ('sending', 'Sending in Progress'), ('sent', 'Sent / Completed'), ('cancelled', 'Cancelled')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `campaign_name`: `CharField(max_length=140, help_text="Internal operational campaign title")`
  - `campaign_type`: `CharField(max_length=30, choices=CAMPAIGN_TYPE_CHOICES, default="promotional")`
  - `target_platform`: `CharField(max_length=20, choices=TARGET_PLATFORM_CHOICES, default="all")`
  - `notification_title`: `CharField(max_length=100, help_text="Notification banner headline (max 100 chars)")`
  - `notification_body`: `TextField(help_text="Notification message body copy")`
  - `image_url`: `CharField(max_length=255, blank=True, default="", help_text="Optional rich media banner image URL")`
  - `badge_increment`: `PositiveSmallIntegerField(default=1, help_text="Increment mobile app icon badge count by N")`
  - `sound_name`: `CharField(max_length=50, default="default", help_text="Audio chime file name (or default)")`
  - `deep_link_type`: `CharField(max_length=20, choices=DEEP_LINK_TYPE_CHOICES, default="home")`
  - `deep_link_url`: `CharField(max_length=255, blank=True, default="", help_text="Specific deep link path or custom URL")`
  - `target_product`: `ForeignKey('ecommerce.CatalogProduct', null=True, blank=True, on_delete=SET_NULL, related_name='mobile_push_campaigns')`
  - `target_category`: `ForeignKey('ecommerce.StoreCategory', null=True, blank=True, on_delete=SET_NULL, related_name='mobile_push_campaigns')`
  - `target_coupon`: `ForeignKey('ecommerce.CouponPromotion', null=True, blank=True, on_delete=SET_NULL, related_name='mobile_push_campaigns')`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default="draft")`
  - `scheduled_for`: `DateTimeField(null=True, blank=True, help_text="Scheduled broadcast timestamp in UTC")`
  - `sent_at`: `DateTimeField(null=True, blank=True, help_text="Timestamp when message dispatch began")`
  - `sent_count`: `PositiveIntegerField(default=0, help_text="Total push messages dispatched")`
  - `delivered_count`: `PositiveIntegerField(default=0, help_text="Total push receipts acknowledged")`
  - `opened_count`: `PositiveIntegerField(default=0, help_text="Total taps / opens recorded")`
  - `converted_count`: `PositiveIntegerField(default=0, help_text="Total orders converted from push taps")`
  - `converted_revenue`: `DecimalField(max_digits=12, decimal_places=2, default=0.00, help_text="Total revenue attributed to campaign")`
  - `created_by`: `ForeignKey('accounts.User', null=True, blank=True, on_delete=SET_NULL, related_name='+')`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='ecommerce_empc_tenant_num_uniq')`
  - `Index(fields=['tenant', 'status'], name='idx_empc_ten_stat')`
  - `Index(fields=['tenant', 'campaign_type'], name='idx_empc_ten_type')`
  - `Index(fields=['tenant', 'scheduled_for'], name='idx_empc_ten_sched')`
- **Ordering:** `['-scheduled_for', '-created_at']`
- **Key Methods:** `calculate_open_rate_pct()`, `calculate_ctr_pct()`, `dispatch_simulation()`

---

### 1.4 `MobileLocationRule` (`apps/ecommerce/models/MobileCommerce/MobileLocationRules.py`)
- **Table:** `ecommerce_mobile_location_rule`
- **Number Prefix:** `EMLR` (`EMLR-00001`)
- **CHOICES:**
  - `RULE_TYPE_CHOICES = [('store_locator', 'Store Locator Directory Pin'), ('geofence_entry', 'Geofence Entry Trigger (Welcome)'), ('geofence_exit', 'Geofence Exit Trigger (Departure)'), ('geofence_dwell', 'Geofence Dwell Trigger (Browsing In-Store)'), ('curbside_pickup', 'Curbside Pickup Arrival Radar')]`
  - `TRIGGER_ACTION_CHOICES = [('display_store_mode', 'Switch App to In-Store Shopping Mode'), ('send_push_notification', 'Send Proximity Push Notification'), ('apply_coupon', 'Unlock Proximity Coupon Promotion'), ('notify_store_associates', 'Alert In-Store Staff for Curbside Hand-Off')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `name`: `CharField(max_length=120, help_text="Friendly rule name (e.g. Downtown Flagship Welcome Geofence)")`
  - `rule_type`: `CharField(max_length=30, choices=RULE_TYPE_CHOICES, default="store_locator")`
  - `fulfillment_center`: `ForeignKey('ecommerce.FulfillmentCenter', null=True, blank=True, on_delete=SET_NULL, related_name='location_rules', help_text="Linked physical retail store fulfillment center")`
  - `store_name`: `CharField(max_length=120, help_text="Retail store name displayed in mobile store locator")`
  - `latitude`: `DecimalField(max_digits=9, decimal_places=6, help_text="Store or geofence center GPS latitude (e.g. 40.712776)")`
  - `longitude`: `DecimalField(max_digits=9, decimal_places=6, help_text="Store or geofence center GPS longitude (e.g. -74.005974)")`
  - `radius_meters`: `PositiveIntegerField(default=500, help_text="Circular geofence radius in meters (50m to 10,000m)")`
  - `trigger_action`: `CharField(max_length=30, choices=TRIGGER_ACTION_CHOICES, default="display_store_mode")`
  - `linked_promotion`: `ForeignKey('ecommerce.CouponPromotion', null=True, blank=True, on_delete=SET_NULL, related_name='location_rules', help_text="Optional proximity discount unlocked upon arrival")`
  - `push_message`: `CharField(max_length=255, blank=True, default="", help_text="Custom push alert sent to shopper on geofence trigger")`
  - `enable_bopis_checkin`: `BooleanField(default=True, help_text="Allow customer 1-tap arrival check-in for online orders")`
  - `enable_instore_mode`: `BooleanField(default=True, help_text="Expose local aisle map and barcode scanner in app")`
  - `dwell_time_seconds`: `PositiveIntegerField(default=120, help_text="Seconds shopper must remain in radius before dwell trigger")`
  - `is_active`: `BooleanField(default=True, help_text="Rule active for mobile telemetry evaluation")`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='ecommerce_emlr_tenant_num_uniq')`
  - `Index(fields=['tenant', 'rule_type'], name='idx_emlr_ten_type')`
  - `Index(fields=['tenant', 'is_active'], name='idx_emlr_ten_act')`
  - `Index(fields=['tenant', 'fulfillment_center'], name='idx_emlr_ten_fc')`
- **Ordering:** `['store_name', '-created_at']`
- **Key Methods:** `distance_to(lat, lng)`, `is_within_geofence(lat, lng)`

---

## 2. Forms Contract & Exclusions

All ModelForms live in `apps/ecommerce/forms/MobileCommerce/` and inherit shared Tailwind styling via `FormStyleMixin` / `forms._common`.

### 2.1 `MobileAppConfigForm` (`apps/ecommerce/forms/MobileCommerce/MobileAppConfigs.py`)
- **Model:** `MobileAppConfig`
- **Excludes:** `['tenant', 'number', 'created_at', 'updated_at']`
- **Widgets:** Tailwind standard classes:
  - `theme_color`, `background_color`: `TextInput(attrs={'type': 'color', 'class': 'form-input h-10 w-24 p-1'})`
  - `description`, `offline_fallback_html`: `Textarea(attrs={'rows': 3, 'class': 'form-textarea'})`

### 2.2 `MobileDeviceRegistrationForm` (`apps/ecommerce/forms/MobileCommerce/MobileDeviceRegistrations.py`)
- **Model:** `MobileDeviceRegistration`
- **Excludes:** `['tenant', 'number', 'created_at', 'updated_at', 'last_active_at', 'badge_count']`
- **FK Querysets:** Scoped strictly to `request.tenant` in `__init__`.

### 2.3 `MobilePushCampaignForm` (`apps/ecommerce/forms/MobileCommerce/MobilePushCampaigns.py`)
- **Model:** `MobilePushCampaign`
- **Excludes:** `['tenant', 'number', 'created_at', 'updated_at', 'sent_at', 'sent_count', 'delivered_count', 'opened_count', 'converted_count', 'converted_revenue', 'created_by']`
- **FK Querysets:** `target_product`, `target_category`, `target_coupon` scoped strictly to `request.tenant` in `__init__`.
- **Widgets:**
  - `notification_body`: `Textarea(attrs={'rows': 3, 'class': 'form-textarea'})`
  - `scheduled_for`: `DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-input'})`

### 2.4 `MobileLocationRuleForm` (`apps/ecommerce/forms/MobileCommerce/MobileLocationRules.py`)
- **Model:** `MobileLocationRule`
- **Excludes:** `['tenant', 'number', 'created_at', 'updated_at']`
- **FK Querysets:** `fulfillment_center`, `linked_promotion` scoped strictly to `request.tenant` in `__init__`.

---

## 3. URLs & View Context Keys Contract (L7 Pinned)

All views are function-based, decorated with `@login_required` (and `@tenant_admin_required` for write actions), and tenant-scoped via `request.tenant`.

### 3.1 URL Patterns (`apps/ecommerce/urls/MobileCommerce/`)
- Concatenated in `apps/ecommerce/urls/__init__.py`:
  - `path('mobile/hub/', views.mobile_hub, name='mobile_hub')`
  - `path('mobile/manifest.json', views.pwa_manifest_json, name='pwa_manifest_json')`
  - `path('mobile/configs/', views.mobileappconfig_list, name='mobileappconfig_list')`
  - `path('mobile/configs/new/', views.mobileappconfig_create, name='mobileappconfig_create')`
  - `path('mobile/configs/<int:pk>/', views.mobileappconfig_detail, name='mobileappconfig_detail')`
  - `path('mobile/configs/<int:pk>/edit/', views.mobileappconfig_edit, name='mobileappconfig_edit')`
  - `path('mobile/configs/<int:pk>/delete/', views.mobileappconfig_delete, name='mobileappconfig_delete')`
  - `path('mobile/devices/', views.mobiledeviceregistration_list, name='mobiledeviceregistration_list')`
  - `path('mobile/devices/new/', views.mobiledeviceregistration_create, name='mobiledeviceregistration_create')`
  - `path('mobile/devices/<int:pk>/', views.mobiledeviceregistration_detail, name='mobiledeviceregistration_detail')`
  - `path('mobile/devices/<int:pk>/edit/', views.mobiledeviceregistration_edit, name='mobiledeviceregistration_edit')`
  - `path('mobile/devices/<int:pk>/delete/', views.mobiledeviceregistration_delete, name='mobiledeviceregistration_delete')`
  - `path('mobile/devices/<int:pk>/ping/', views.mobiledeviceregistration_ping, name='mobiledeviceregistration_ping')`
  - `path('mobile/push-campaigns/', views.mobilepushcampaign_list, name='mobilepushcampaign_list')`
  - `path('mobile/push-campaigns/new/', views.mobilepushcampaign_create, name='mobilepushcampaign_create')`
  - `path('mobile/push-campaigns/<int:pk>/', views.mobilepushcampaign_detail, name='mobilepushcampaign_detail')`
  - `path('mobile/push-campaigns/<int:pk>/edit/', views.mobilepushcampaign_edit, name='mobilepushcampaign_edit')`
  - `path('mobile/push-campaigns/<int:pk>/delete/', views.mobilepushcampaign_delete, name='mobilepushcampaign_delete')`
  - `path('mobile/push-campaigns/<int:pk>/test-send/', views.mobilepushcampaign_test_send, name='mobilepushcampaign_test_send')`
  - `path('mobile/location-rules/', views.mobilelocationrule_list, name='mobilelocationrule_list')`
  - `path('mobile/location-rules/new/', views.mobilelocationrule_create, name='mobilelocationrule_create')`
  - `path('mobile/location-rules/<int:pk>/', views.mobilelocationrule_detail, name='mobilelocationrule_detail')`
  - `path('mobile/location-rules/<int:pk>/edit/', views.mobilelocationrule_edit, name='mobilelocationrule_edit')`
  - `path('mobile/location-rules/<int:pk>/delete/', views.mobilelocationrule_delete, name='mobilelocationrule_delete')`
  - `path('mobile/location-rules/<int:pk>/simulate/', views.mobilelocationrule_simulate, name='mobilelocationrule_simulate')`

### 3.2 View Context Keys Contract (L7)
- **`mobileappconfig_list`**:
  - `configs`, `page_obj`, `paginator`, `is_paginated`, `total_count`, `active_count`, `pwa_count`
- **`mobileappconfig_detail`**:
  - `config`, `object`, `manifest_json_str`
- **`mobileappconfig_create` / `_edit`**:
  - `form`, `config` (on edit), `object` (on edit), `is_edit`
- **`mobiledeviceregistration_list`**:
  - `devices`, `page_obj`, `paginator`, `is_paginated`, `platform_choices`, `provider_choices`, `selected_platform`, `selected_provider`, `selected_status`, `total_count`, `ios_count`, `android_count`, `pwa_count`, `q`
- **`mobiledeviceregistration_detail`**:
  - `device`, `object`
- **`mobiledeviceregistration_create` / `_edit`**:
  - `form`, `device` (on edit), `object` (on edit), `is_edit`
- **`mobilepushcampaign_list`**:
  - `campaigns`, `page_obj`, `paginator`, `is_paginated`, `status_choices`, `type_choices`, `platform_choices`, `selected_status`, `selected_type`, `selected_platform`, `total_count`, `sent_count`, `draft_count`, `q`
- **`mobilepushcampaign_detail`**:
  - `campaign`, `object`, `open_rate_pct`, `ctr_pct`
- **`mobilepushcampaign_create` / `_edit`**:
  - `form`, `campaign` (on edit), `object` (on edit), `is_edit`
- **`mobilelocationrule_list`**:
  - `location_rules`, `page_obj`, `paginator`, `is_paginated`, `type_choices`, `action_choices`, `selected_type`, `selected_action`, `total_count`, `active_count`, `q`
- **`mobilelocationrule_detail`**:
  - `location_rule`, `object`
- **`mobilelocationrule_create` / `_edit`**:
  - `form`, `location_rule` (on edit), `object` (on edit), `is_edit`
- **`mobile_hub`**:
  - `total_devices`, `ios_devices`, `android_devices`, `pwa_devices`, `active_campaigns`, `total_push_sent`, `total_push_opened`, `active_geofences`, `pwa_enabled`, `apple_pay_enabled`, `google_pay_enabled`, `recent_devices`, `recent_campaigns`, `recent_locations`

---

## 4. Templates & Design System Badges Contract (L33)

Templates strictly reside in `templates/ecommerce/mobile/`:
- `templates/ecommerce/mobile/mobile_hub.html` (Mobile Console)
- `templates/ecommerce/mobile/mobile_app_config/{list,detail,form}.html`
- `templates/ecommerce/mobile/mobile_device_registration/{list,detail,form}.html`
- `templates/ecommerce/mobile/mobile_push_campaign/{list,detail,form}.html`
- `templates/ecommerce/mobile/mobile_location_rule/{list,detail,form}.html`

### Badge Classes (Colour-named ONLY per L33):
- **Platforms**:
  - `ios`: `badge badge-slate`
  - `android`: `badge badge-green`
  - `pwa_web`: `badge badge-info`
- **Push Campaign Status**:
  - `draft`: `badge badge-muted`
  - `scheduled`: `badge badge-amber`
  - `sending`: `badge badge-info`
  - `sent`: `badge badge-green`
  - `cancelled`: `badge badge-red`
- **Active / Inactive Status**:
  - True: `badge badge-green`
  - False: `badge badge-muted`
- **Location Rule Type**:
  - `store_locator`: `badge badge-info`
  - `geofence_entry`: `badge badge-green`
  - `geofence_exit`: `badge badge-slate`
  - `geofence_dwell`: `badge badge-amber`
  - `curbside_pickup`: `badge badge-purple` (or `badge-info`)

---

## 5. Navigation LIVE_LINKS Contract (`apps/core/navigation.py`)

`LIVE_LINKS["9.16"]` mappings:
```python
    "9.16": {
        "Progressive Web App (PWA)": "ecommerce:mobileappconfig_list",
        "Native Mobile Apps (iOS/Android)": "ecommerce:mobiledeviceregistration_list",
        "Mobile Payment Integration": "ecommerce:mobileappconfig_list",
        "Location-Based Services": "ecommerce:mobilelocationrule_list",
        "Social & Messaging Commerce": "ecommerce:mobilepushcampaign_list",
        # Extra live leaves
        "Mobile Hub": "ecommerce:mobile_hub",
        "App Configurations": "ecommerce:mobileappconfig_list",
        "Registered Devices": "ecommerce:mobiledeviceregistration_list",
        "Push Campaigns": "ecommerce:mobilepushcampaign_list",
        "Location Rules": "ecommerce:mobilelocationrule_list",
    },
```

---

## 6. Seeder Contract (`apps/ecommerce/management/commands/seed_ecommerce.py`)

Extend existing `seed_ecommerce.py` idempotently for both Acme (`admin_acme`) and Globex (`admin_globex`):
- `MobileAppConfig`: 1 active configuration per tenant (Acme: "Acme Gear Mobile Store", Globex: "Globex Retail App").
- `MobileDeviceRegistration`: 4 realistic devices per tenant (2 iOS, 1 Android, 1 PWA).
- `MobilePushCampaign`: 3 campaigns per tenant (1 sent promotional flash sale, 1 scheduled abandoned cart recovery, 1 draft geofence welcome).
- `MobileLocationRule`: 2 location rules per tenant (1 Downtown Flagship Store Locator / Geofence, 1 Suburban Curbside BOPIS Arrival Radar linked to existing FulfillmentCenters).
