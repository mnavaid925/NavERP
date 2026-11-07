# Contract — Sub-module 10.17: Embedded & Mobile BI (Module 10: Business Intelligence, `bi`)

- **Sub-module:** 10.17 Embedded & Mobile BI • **Module:** 10 Business Intelligence • **App:** `apps/bi`
- **Date:** 2026-11-07 • **Status:** FROZEN PRE-BUILD CONTRACT • **Phase:** 3.1 Spec
- **App Status:** Existing app `apps/bi/` (extended across 10.1 through 10.15). Incremental migration: `0036_...` (previous leaf: `0035_searchdiscoveryindex_idx_bsdi_ten_feat_rw.py`).
- **Package Layout:** `EmbeddedMobileBi/` across `models/`, `forms/`, `views/`, `urls/`, and templates `templates/bi/embedded_mobile_bi/`.

---

## 1. Models & CHOICES Contract

All 4 models inherit from `apps.bi.models._base.TenantNumbered` (`tenant`, `number`, `created_at`, `updated_at`).

### 1.1 `EmbeddedAnalyticsConfig` (`apps/bi/models/EmbeddedMobileBi/EmbeddedAnalyticsConfigs.py`)
- **Table:** `bi_embedded_analytics_config`
- **Number Prefix:** `EMB` (`EMB-00001`)
- **CHOICES:**
  - `TARGET_TYPE_CHOICES = [('dashboard', 'Interactive Dashboard'), ('report', 'Operational Report'), ('semantic_model', 'Semantic Data Model')]`
  - `EMBEDDING_MODE_CHOICES = [('iframe', 'Sandboxed Iframe'), ('web_component', 'Web Component SDK (<nav-bi-embed>)'), ('headless_api', 'Headless JSON Data API')]`
  - `AUTH_MODE_CHOICES = [('public_token', 'Public Kiosk / Embed Token'), ('signed_jwt', 'Signed HMAC-SHA256 Token'), ('sso_passthrough', 'Enterprise SSO Passthrough')]`
  - `THEME_MODE_CHOICES = [('light', 'Light Theme'), ('dark', 'Dark Theme'), ('auto', 'Inherit Host Application'), ('custom', 'Custom CSS Styling')]`
  - `STATUS_CHOICES = [('active', 'Active & Serving'), ('paused', 'Temporarily Paused'), ('revoked', 'Revoked / Disabled')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `name`: `CharField(max_length=200)`
  - `slug`: `SlugField(max_length=220, blank=True)`
  - `description`: `TextField(blank=True)`
  - `target_type`: `CharField(max_length=24, choices=TARGET_TYPE_CHOICES, default='dashboard')`
  - `dashboard`: `ForeignKey('bi.BiDashboard', null=True, blank=True, on_delete=models.SET_NULL, related_name='embedded_configs')`
  - `report`: `ForeignKey('bi.ReportDefinition', null=True, blank=True, on_delete=models.SET_NULL, related_name='embedded_configs')`
  - `semantic_model`: `ForeignKey('bi.SemanticModel', null=True, blank=True, on_delete=models.SET_NULL, related_name='embedded_configs')`
  - `embedding_mode`: `CharField(max_length=24, choices=EMBEDDING_MODE_CHOICES, default='iframe')`
  - `auth_mode`: `CharField(max_length=24, choices=AUTH_MODE_CHOICES, default='signed_jwt')`
  - `status`: `CharField(max_length=16, choices=STATUS_CHOICES, default='active')`
  - `allowed_origins`: `TextField(blank=True, default='*')`
  - `theme_mode`: `CharField(max_length=16, choices=THEME_MODE_CHOICES, default='light')`
  - `primary_color`: `CharField(max_length=20, default='#1e40af')`
  - `accent_color`: `CharField(max_length=20, default='#3b82f6')`
  - `custom_css`: `TextField(blank=True)`
  - `enable_rls_filter`: `BooleanField(default=True)`
  - `default_rls_attributes`: `JSONField(default=dict, blank=True)`
  - `view_count`: `PositiveIntegerField(default=0)`
  - `last_accessed_at`: `DateTimeField(null=True, blank=True)`
  - `created_by`: `ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='bi_embedded_configs')`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='bi_emb_tenant_num_uniq')`
  - `UniqueConstraint(fields=['tenant', 'slug'], name='bi_emb_tenant_slug_uniq')`
  - `Index(fields=['tenant', 'status'], name='idx_emb_ten_stat')`
  - `Index(fields=['tenant', 'target_type'], name='idx_emb_ten_target')`
  - `Index(fields=['tenant', 'embedding_mode'], name='idx_emb_ten_mode')`
  - `Index(fields=['tenant', 'created_at'], name='idx_emb_ten_created')`

---

### 1.2 `KioskWallboardDisplay` (`apps/bi/models/EmbeddedMobileBi/KioskWallboardDisplays.py`)
- **Table:** `bi_kiosk_wallboard_display`
- **Number Prefix:** `WALL` (`WALL-00001`)
- **CHOICES:**
  - `TRANSITION_EFFECT_CHOICES = [('fade', 'Smooth Fade (1s)'), ('slide_horizontal', 'Horizontal Slide'), ('zoom', 'Subtle Zoom In'), ('none', 'Instant Cut')]`
  - `WALLBOARD_THEME_CHOICES = [('dark_oled', 'Deep Dark OLED (#000000)'), ('dark_navy', 'Command Center Navy (#0f172a)'), ('light_high_contrast', 'High-Contrast Light (#ffffff)')]`
  - `DISPLAY_SCHEDULE_CHOICES = [('continuous_24_7', 'Continuous 24/7 Operations'), ('business_hours', 'Business Hours (08:00 - 18:00)'), ('shift_work', 'Multi-Shift Operations')]`
  - `STATUS_CHOICES = [('active', 'Active & Broadcasting'), ('standby', 'Standby / Paused'), ('offline', 'Offline')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `name`: `CharField(max_length=200)`
  - `location_description`: `CharField(max_length=255, blank=True)`
  - `kiosk_slug`: `SlugField(max_length=220, blank=True)`
  - `access_passcode`: `CharField(max_length=64, blank=True)`
  - `is_public_kiosk`: `BooleanField(default=False)`
  - `status`: `CharField(max_length=16, choices=STATUS_CHOICES, default='active')`
  - `playlist_items`: `JSONField(default=list, blank=True)`
  - `default_slide_duration_seconds`: `PositiveIntegerField(default=30)`
  - `transition_effect`: `CharField(max_length=24, choices=TRANSITION_EFFECT_CHOICES, default='fade')`
  - `theme`: `CharField(max_length=24, choices=WALLBOARD_THEME_CHOICES, default='dark_navy')`
  - `display_schedule`: `CharField(max_length=24, choices=DISPLAY_SCHEDULE_CHOICES, default='continuous_24_7')`
  - `operating_hours_json`: `JSONField(default=dict, blank=True)`
  - `auto_refresh_data_interval_seconds`: `PositiveIntegerField(default=60)`
  - `last_heartbeat_at`: `DateTimeField(null=True, blank=True)`
  - `device_ip_address`: `GenericIPAddressField(null=True, blank=True)`
  - `device_user_agent`: `CharField(max_length=255, blank=True)`
  - `created_by`: `ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='bi_kiosk_displays')`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='bi_wall_tenant_num_uniq')`
  - `UniqueConstraint(fields=['tenant', 'kiosk_slug'], name='bi_wall_tenant_slug_uniq')`
  - `Index(fields=['tenant', 'status'], name='idx_wall_ten_stat')`
  - `Index(fields=['tenant', 'theme'], name='idx_wall_ten_theme')`
  - `Index(fields=['tenant', 'last_heartbeat_at'], name='idx_wall_ten_heartbeat')`
  - `Index(fields=['tenant', 'created_at'], name='idx_wall_ten_created')`

---

### 1.3 `MobileBiConfiguration` (`apps/bi/models/EmbeddedMobileBi/MobileBiConfigurations.py`)
- **Table:** `bi_mobile_configuration`
- **Number Prefix:** `MOB` (`MOB-00001`)
- **CHOICES:**
  - `TOUCH_PRESET_CHOICES = [('compact', 'Compact Grid (High Density)'), ('comfortable', 'Comfortable Cards (Standard Touch)'), ('large_cards', 'Large Cards (Single Column / Accessible)')]`
  - `DIGEST_FREQUENCY_CHOICES = [('realtime', 'Instant Push on Alert Trigger'), ('hourly', 'Hourly Push Digest'), ('daily_morning', 'Daily Morning Briefing (08:00)'), ('weekly', 'Weekly Executive Digest (Monday 08:00)'), ('disabled', 'Push Insights Disabled')]`
  - `STATUS_CHOICES = [('active', 'Active Profile'), ('inactive', 'Inactive Profile')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `name`: `CharField(max_length=200)`
  - `target_user`: `ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='bi_mobile_configs')`
  - `is_default_profile`: `BooleanField(default=False)`
  - `status`: `CharField(max_length=16, choices=STATUS_CHOICES, default='active')`
  - `offline_caching_enabled`: `BooleanField(default=True)`
  - `cache_max_age_hours`: `PositiveIntegerField(default=24)`
  - `max_cache_storage_mb`: `PositiveIntegerField(default=100)`
  - `sync_on_wifi_only`: `BooleanField(default=False)`
  - `pinned_dashboard_ids`: `JSONField(default=list, blank=True)`
  - `pinned_report_ids`: `JSONField(default=list, blank=True)`
  - `touch_layout_preset`: `CharField(max_length=24, choices=TOUCH_PRESET_CHOICES, default='comfortable')`
  - `enable_push_insights`: `BooleanField(default=True)`
  - `push_digest_frequency`: `CharField(max_length=24, choices=DIGEST_FREQUENCY_CHOICES, default='daily_morning')`
  - `require_biometric_lock`: `BooleanField(default=False)`
  - `inactivity_lock_minutes`: `PositiveIntegerField(default=5)`
  - `last_synced_at`: `DateTimeField(null=True, blank=True)`
  - `created_by`: `ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='bi_created_mobile_configs')`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='bi_mob_tenant_num_uniq')`
  - `Index(fields=['tenant', 'status'], name='idx_mob_ten_stat')`
  - `Index(fields=['tenant', 'target_user'], name='idx_mob_ten_usr')`
  - `Index(fields=['tenant', 'is_default_profile'], name='idx_mob_ten_default')`
  - `Index(fields=['tenant', 'created_at'], name='idx_mob_ten_created')`

---

### 1.4 `EmbedApiToken` (`apps/bi/models/EmbeddedMobileBi/EmbedApiTokens.py`)
- **Table:** `bi_embed_api_token`
- **Number Prefix:** `EAPI` (`EAPI-00001`)
- **CHOICES:**
  - `STATUS_CHOICES = [('active', 'Active Token'), ('expired', 'Expired'), ('revoked', 'Revoked by Administrator')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `name`: `CharField(max_length=200)`
  - `token_prefix`: `CharField(max_length=16, default='eapi_live_')`
  - `token_hash`: `CharField(max_length=64)`
  - `status`: `CharField(max_length=16, choices=STATUS_CHOICES, default='active')`
  - `scopes`: `JSONField(default=list, blank=True)`
  - `embedded_config`: `ForeignKey('bi.EmbeddedAnalyticsConfig', null=True, blank=True, on_delete=models.SET_NULL, related_name='api_tokens')`
  - `injected_rls_context`: `JSONField(default=dict, blank=True)`
  - `allowed_ip_ranges`: `TextField(blank=True)`
  - `rate_limit_rpm`: `PositiveIntegerField(default=120)`
  - `expires_at`: `DateTimeField(null=True, blank=True)`
  - `total_requests_count`: `PositiveIntegerField(default=0)`
  - `last_used_at`: `DateTimeField(null=True, blank=True)`
  - `created_by`: `ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='bi_api_tokens')`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='bi_eapi_tenant_num_uniq')`
  - `Index(fields=['tenant', 'token_prefix'], name='idx_eapi_ten_pfx')`
  - `Index(fields=['tenant', 'status'], name='idx_eapi_ten_stat')`
  - `Index(fields=['tenant', 'expires_at'], name='idx_eapi_ten_exp')`
  - `Index(fields=['tenant', 'created_at'], name='idx_eapi_ten_created')`

---

## 2. Forms Contract

All forms inherit from `TenantModelForm` + `TenantUniqueMixin` (`apps/bi/forms/_common.py`).

1. `EmbeddedAnalyticsConfigForm` (`apps/bi/forms/EmbeddedMobileBi/EmbeddedAnalyticsConfigs.py`)
   - `Meta.model = EmbeddedAnalyticsConfig`
   - `Meta.fields = ['name', 'slug', 'description', 'target_type', 'dashboard', 'report', 'semantic_model', 'embedding_mode', 'auth_mode', 'status', 'allowed_origins', 'theme_mode', 'primary_color', 'accent_color', 'custom_css', 'enable_rls_filter', 'default_rls_attributes']`
   - Excluded: `tenant`, `number`, `view_count`, `last_accessed_at`, `created_by`, `created_at`, `updated_at`

2. `KioskWallboardDisplayForm` (`apps/bi/forms/EmbeddedMobileBi/KioskWallboardDisplays.py`)
   - `Meta.model = KioskWallboardDisplay`
   - `Meta.fields = ['name', 'location_description', 'kiosk_slug', 'access_passcode', 'is_public_kiosk', 'status', 'playlist_items', 'default_slide_duration_seconds', 'transition_effect', 'theme', 'display_schedule', 'operating_hours_json', 'auto_refresh_data_interval_seconds']`
   - Excluded: `tenant`, `number`, `last_heartbeat_at`, `device_ip_address`, `device_user_agent`, `created_by`, `created_at`, `updated_at`

3. `MobileBiConfigurationForm` (`apps/bi/forms/EmbeddedMobileBi/MobileBiConfigurations.py`)
   - `Meta.model = MobileBiConfiguration`
   - `Meta.fields = ['name', 'target_user', 'is_default_profile', 'status', 'offline_caching_enabled', 'cache_max_age_hours', 'max_cache_storage_mb', 'sync_on_wifi_only', 'pinned_dashboard_ids', 'pinned_report_ids', 'touch_layout_preset', 'enable_push_insights', 'push_digest_frequency', 'require_biometric_lock', 'inactivity_lock_minutes']`
   - Excluded: `tenant`, `number`, `last_synced_at`, `created_by`, `created_at`, `updated_at`

4. `EmbedApiTokenForm` (`apps/bi/forms/EmbeddedMobileBi/EmbedApiTokens.py`)
   - `Meta.model = EmbedApiToken`
   - `Meta.fields = ['name', 'status', 'scopes', 'embedded_config', 'injected_rls_context', 'allowed_ip_ranges', 'rate_limit_rpm', 'expires_at']`
   - Excluded: `tenant`, `number`, `token_prefix`, `token_hash`, `total_requests_count`, `last_used_at`, `created_by`, `created_at`, `updated_at`

---

## 3. URLs Contract

- `app_name = 'bi'`

| URL Pattern | Name | View Function |
|---|---|---|
| `embedded-configs/` | `embedded_analytics_config_list` | `embedded_analytics_config_list` |
| `embedded-configs/create/` | `embedded_analytics_config_create` | `embedded_analytics_config_create` |
| `embedded-configs/<int:pk>/` | `embedded_analytics_config_detail` | `embedded_analytics_config_detail` |
| `embedded-configs/<int:pk>/edit/` | `embedded_analytics_config_edit` | `embedded_analytics_config_edit` |
| `embedded-configs/<int:pk>/delete/` | `embedded_analytics_config_delete` | `embedded_analytics_config_delete` |
| `embedded-configs/<int:pk>/preview/` | `embedded_analytics_config_preview` | `embedded_analytics_config_preview` |
| `kiosk-displays/` | `kiosk_wallboard_display_list` | `kiosk_wallboard_display_list` |
| `kiosk-displays/create/` | `kiosk_wallboard_display_create` | `kiosk_wallboard_display_create` |
| `kiosk-displays/<int:pk>/` | `kiosk_wallboard_display_detail` | `kiosk_wallboard_display_detail` |
| `kiosk-displays/<int:pk>/edit/` | `kiosk_wallboard_display_edit` | `kiosk_wallboard_display_edit` |
| `kiosk-displays/<int:pk>/delete/` | `kiosk_wallboard_display_delete` | `kiosk_wallboard_display_delete` |
| `kiosk-displays/<int:pk>/player/` | `kiosk_wallboard_display_player` | `kiosk_wallboard_display_player` |
| `kiosk-displays/<int:pk>/heartbeat/` | `kiosk_wallboard_display_heartbeat` | `kiosk_wallboard_display_heartbeat` |
| `mobile-configs/` | `mobile_bi_config_list` | `mobile_bi_config_list` |
| `mobile-configs/create/` | `mobile_bi_config_create` | `mobile_bi_config_create` |
| `mobile-configs/<int:pk>/` | `mobile_bi_config_detail` | `mobile_bi_config_detail` |
| `mobile-configs/<int:pk>/edit/` | `mobile_bi_config_edit` | `mobile_bi_config_edit` |
| `mobile-configs/<int:pk>/delete/` | `mobile_bi_config_delete` | `mobile_bi_config_delete` |
| `api-tokens/` | `embed_api_token_list` | `embed_api_token_list` |
| `api-tokens/create/` | `embed_api_token_create` | `embed_api_token_create` |
| `api-tokens/<int:pk>/` | `embed_api_token_detail` | `embed_api_token_detail` |
| `api-tokens/<int:pk>/edit/` | `embed_api_token_edit` | `embed_api_token_edit` |
| `api-tokens/<int:pk>/delete/` | `embed_api_token_delete` | `embed_api_token_delete` |
| `api-tokens/<int:pk>/revoke/` | `embed_api_token_revoke` | `embed_api_token_revoke` |

---

## 4. View Context Keys Contract

### 4.1 List Views
- `embedded_analytics_config_list`:
  - `configs`: page_obj
  - `embedded_analytics_configs`: page_obj
  - `total_count`: integer
  - `active_count`: integer
  - `iframe_count`: integer
  - `component_count`: integer
  - `status_choices`: `EmbeddedAnalyticsConfig.STATUS_CHOICES`
  - `target_type_choices`: `EmbeddedAnalyticsConfig.TARGET_TYPE_CHOICES`
  - `embedding_mode_choices`: `EmbeddedAnalyticsConfig.EMBEDDING_MODE_CHOICES`

- `kiosk_wallboard_display_list`:
  - `displays`: page_obj
  - `kiosk_wallboard_displays`: page_obj
  - `total_count`: integer
  - `active_count`: integer
  - `dark_count`: integer
  - `status_choices`: `KioskWallboardDisplay.STATUS_CHOICES`
  - `theme_choices`: `KioskWallboardDisplay.WALLBOARD_THEME_CHOICES`
  - `schedule_choices`: `KioskWallboardDisplay.DISPLAY_SCHEDULE_CHOICES`

- `mobile_bi_config_list`:
  - `configs`: page_obj
  - `mobile_bi_configs`: page_obj
  - `total_count`: integer
  - `active_count`: integer
  - `offline_enabled_count`: integer
  - `status_choices`: `MobileBiConfiguration.STATUS_CHOICES`
  - `preset_choices`: `MobileBiConfiguration.TOUCH_PRESET_CHOICES`
  - `digest_choices`: `MobileBiConfiguration.DIGEST_FREQUENCY_CHOICES`

- `embed_api_token_list`:
  - `tokens`: page_obj
  - `embed_api_tokens`: page_obj
  - `total_count`: integer
  - `active_count`: integer
  - `revoked_count`: integer
  - `status_choices`: `EmbedApiToken.STATUS_CHOICES`

### 4.2 Detail Views
- `embedded_analytics_config_detail`:
  - `config`: `EmbeddedAnalyticsConfig` instance
  - `iframe_snippet`: string HTML iframe code
  - `web_component_snippet`: string `<nav-bi-embed>` code
  - `curl_snippet`: string cURL API call

- `kiosk_wallboard_display_detail`:
  - `display`: `KioskWallboardDisplay` instance
  - `playlist_items`: parsed list
  - `operating_hours`: parsed dict

- `kiosk_wallboard_display_player`:
  - `display`: `KioskWallboardDisplay` instance
  - `playlist_json`: serialized JSON string for JavaScript player engine

- `mobile_bi_config_detail`:
  - `config`: `MobileBiConfiguration` instance
  - `pinned_dashboards`: QuerySet / list of `BiDashboard`
  - `pinned_reports`: QuerySet / list of `ReportDefinition`

- `embed_api_token_detail`:
  - `token`: `EmbedApiToken` instance
  - `scopes_list`: list of strings
  - `injected_rls`: dict
  - `js_sdk_snippet`: string
  - `curl_snippet`: string
  - `new_key`: string or None (visible only once after creation)

---

## 5. Navigation `LIVE_LINKS["10.17"]` Contract

```python
    "10.17": {
        "Embedded Analytics": "bi:embedded_analytics_config_list",
        "Mobile BI App": "bi:mobile_bi_config_list",
        "Developer APIs & SDKs": "bi:embed_api_token_list",
        "Portal, Kiosk & Wallboard": "bi:kiosk_wallboard_display_list",
        "SSO & Row-Level Context": "bi:embed_api_token_list",
    },
```
