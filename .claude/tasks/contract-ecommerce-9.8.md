# Contract — Sub-module 9.8: Personalization & Recommendation Engine (Module 9: eCommerce Management System, `ecommerce`)

- **Sub-module:** 9.8 Personalization & Recommendation Engine · **Module:** 9 eCommerce Management System · **App:** `apps/ecommerce`
- **Date:** 2026-10-30 · **Status:** FROZEN PRE-BUILD CONTRACT · **Phase:** 3.1 Spec
- **App Status:** Extending existing `apps/ecommerce/`. Next incremental migration: `0011_...`
- **Package Layout:** `Personalization/` across `models/`, `forms/`, `views/`, `urls/`, and templates `templates/ecommerce/personalization/`.

---

## 1. Models & CHOICES Contract

All top-level models inherit from `apps.ecommerce.models._base.TenantNumbered` (`tenant`, `number`, `created_at`, `updated_at`).

### 1.1 `AudienceSegment` (`apps/ecommerce/models/Personalization/AudienceSegments.py`)
- **Table:** `ecommerce_audience_segment`
- **Number Prefix:** `ESEG` (`ESEG-00001`)
- **CHOICES:**
  - `LIFECYCLE_STAGE_CHOICES = [('all', 'All Lifecycle Stages'), ('new_visitor', 'New Visitor'), ('first_time_buyer', 'First-Time Buyer'), ('active_repeat', 'Active Repeat Customer'), ('high_value_vip', 'High-Value VIP'), ('at_risk', 'At-Risk Customer'), ('churned_lapsed', 'Churned / Lapsed Shopper')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `name`: `CharField(max_length=120)`
  - `code`: `CharField(max_length=60)`
  - `lifecycle_stage`: `CharField(max_length=30, choices=LIFECYCLE_STAGE_CHOICES, default='all')`
  - `recency_days_max`: `PositiveIntegerField(null=True, blank=True)`
  - `min_order_count`: `PositiveIntegerField(default=0)`
  - `min_lifetime_spend`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))`
  - `target_category`: `ForeignKey('ecommerce.StoreCategory', on_delete=SET_NULL, null=True, blank=True, related_name='affinity_segments')`
  - `cached_member_count`: `PositiveIntegerField(default=0)`
  - `last_evaluated_at`: `DateTimeField(null=True, blank=True)`
  - `is_active`: `BooleanField(default=True)`
  - `description`: `TextField(blank=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='ecommerce_eseg_tenant_num_uniq')`
  - `UniqueConstraint(fields=['tenant', 'code'], name='ecommerce_eseg_code_uniq')`
  - `Index(fields=['tenant', 'is_active', 'lifecycle_stage'], name='idx_eseg_ten_act_stage')`

---

### 1.2 `RecommendationStrategy` (`apps/ecommerce/models/Personalization/RecommendationStrategies.py`)
- **Table:** `ecommerce_recommendation_strategy`
- **Number Prefix:** `EREC` (`EREC-00001`)
- **CHOICES:**
  - `ALGORITHM_CHOICES = [('related_products', 'Related Products (Content-Based)'), ('frequently_bought_together', 'Frequently Bought Together (Co-occurrence)'), ('collaborative_filtering', 'Shoppers Also Viewed / Bought'), ('trending_popular', 'Trending & Popular Items'), ('recently_viewed', 'Recently Viewed (Shopper History)'), ('replenishment', 'Repurchase & Replenishment Reminder'), ('hybrid', 'Hybrid Multi-Factor Score')]`
  - `PLACEMENT_CHOICES = [('pdp_related', 'Product Detail Page (PDP)'), ('cart_cross_sell', 'Cart Drawer / Cross-Sell'), ('homepage_feed', 'Homepage Recommendation Feed'), ('category_trending', 'Category Top Sellers / Trending'), ('checkout_upsell', 'Checkout Order Bump'), ('email_block', 'Email / Notification Block')]`
  - `FALLBACK_CHOICES = [('trending_popular', 'Site Trending & Best Sellers'), ('category_top', 'Category Top Sellers'), ('new_arrivals', 'New Arrivals'), ('none', 'No Fallback (Hide Widget)')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `name`: `CharField(max_length=120)`
  - `code`: `CharField(max_length=60)`
  - `algorithm`: `CharField(max_length=30, choices=ALGORITHM_CHOICES, default='related_products')`
  - `placement`: `CharField(max_length=30, choices=PLACEMENT_CHOICES, default='pdp_related')`
  - `fallback_strategy`: `CharField(max_length=30, choices=FALLBACK_CHOICES, default='trending_popular')`
  - `max_items`: `PositiveIntegerField(default=6)`
  - `min_rating`: `DecimalField(max_digits=3, decimal_places=2, default=Decimal('0.00'))`
  - `same_brand_only`: `BooleanField(default=False)`
  - `only_in_stock`: `BooleanField(default=True)`
  - `target_category`: `ForeignKey('ecommerce.StoreCategory', on_delete=SET_NULL, null=True, blank=True, related_name='recommendation_strategies')`
  - `target_segment`: `ForeignKey('ecommerce.AudienceSegment', on_delete=SET_NULL, null=True, blank=True, related_name='recommendation_strategies')`
  - `is_active`: `BooleanField(default=True)`
  - `description`: `TextField(blank=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='ecommerce_erec_tenant_num_uniq')`
  - `UniqueConstraint(fields=['tenant', 'code'], name='ecommerce_erec_code_uniq')`
  - `Index(fields=['tenant', 'is_active', 'placement'], name='idx_erec_ten_act_place')`

---

### 1.3 `PersonalizedExperience` (`apps/ecommerce/models/Personalization/PersonalizedExperiences.py`)
- **Table:** `ecommerce_personalized_experience`
- **Number Prefix:** `EPEX` (`EPEX-00001`)
- **CHOICES:**
  - `EXPERIENCE_TYPE_CHOICES = [('home_hero', 'Homepage Hero Banner'), ('curated_collection', 'Curated Category / Collection'), ('cart_abandonment', 'Cart Abandonment Trigger'), ('browse_abandonment', 'Browse Abandonment Trigger'), ('replenishment_reminder', 'Replenishment Reorder Trigger'), ('win_back', 'Win-Back Re-Engagement Trigger')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `name`: `CharField(max_length=120)`
  - `experience_type`: `CharField(max_length=30, choices=EXPERIENCE_TYPE_CHOICES, default='home_hero')`
  - `target_segment`: `ForeignKey('ecommerce.AudienceSegment', on_delete=CASCADE, related_name='experiences')`
  - `target_category`: `ForeignKey('ecommerce.StoreCategory', on_delete=SET_NULL, null=True, blank=True, related_name='personalized_experiences')`
  - `target_product`: `ForeignKey('ecommerce.CatalogProduct', on_delete=SET_NULL, null=True, blank=True, related_name='personalized_experiences')`
  - `headline`: `CharField(max_length=150, blank=True)`
  - `subheadline`: `TextField(blank=True)`
  - `cta_label`: `CharField(max_length=50, blank=True)`
  - `cta_url`: `CharField(max_length=255, blank=True)`
  - `hero_image_url`: `CharField(max_length=255, blank=True)`
  - `trigger_delay_hours`: `PositiveIntegerField(default=1)`
  - `priority`: `PositiveIntegerField(default=10)`
  - `start_date`: `DateTimeField(null=True, blank=True)`
  - `end_date`: `DateTimeField(null=True, blank=True)`
  - `is_active`: `BooleanField(default=True)`
  - `impression_count`: `PositiveIntegerField(default=0)`
  - `click_count`: `PositiveIntegerField(default=0)`
  - `conversion_count`: `PositiveIntegerField(default=0)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='ecommerce_epex_tenant_num_uniq')`
  - `Index(fields=['tenant', 'is_active', 'experience_type', 'priority'], name='idx_epex_ten_act_type_prio')`

---

### 1.4 `ShopperBehaviorEvent` (`apps/ecommerce/models/Personalization/ShopperBehaviorEvents.py`)
- **Table:** `ecommerce_shopper_behavior_event`
- **Number Prefix:** `ESBE` (`ESBE-00001`)
- **CHOICES:**
  - `EVENT_TYPE_CHOICES = [('page_view', 'Page View'), ('product_view', 'Product Detail View'), ('category_view', 'Category Browse'), ('search_query', 'Search Query'), ('cart_add', 'Add to Cart'), ('wishlist_add', 'Add to Wishlist'), ('checkout_start', 'Initiate Checkout'), ('order_purchase', 'Order Completed')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `session_key`: `CharField(max_length=64, db_index=True)`
  - `customer_profile`: `ForeignKey('ecommerce.CustomerAccountProfile', on_delete=SET_NULL, null=True, blank=True, related_name='behavior_events')`
  - `party`: `ForeignKey('core.Party', on_delete=SET_NULL, null=True, blank=True, related_name='shopper_behavior_events')`
  - `user`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name='shopper_behavior_events')`
  - `event_type`: `CharField(max_length=30, choices=EVENT_TYPE_CHOICES, default='page_view')`
  - `product`: `ForeignKey('ecommerce.CatalogProduct', on_delete=SET_NULL, null=True, blank=True, related_name='behavior_events')`
  - `category`: `ForeignKey('ecommerce.StoreCategory', on_delete=SET_NULL, null=True, blank=True, related_name='behavior_events')`
  - `intent_score_delta`: `IntegerField(default=1)`
  - `referrer_url`: `CharField(max_length=255, blank=True)`
  - `ip_address`: `GenericIPAddressField(null=True, blank=True)`
  - `user_agent`: `CharField(max_length=255, blank=True)`
  - `payload_json`: `JSONField(default=dict, blank=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='ecommerce_esbe_tenant_num_uniq')`
  - `Index(fields=['tenant', 'session_key', 'event_type'], name='idx_esbe_ten_sess_type')`
  - `Index(fields=['tenant', 'event_type', '-created_at'], name='idx_esbe_ten_type_created')`
  - `Index(fields=['tenant', '-created_at'], name='idx_esbe_ten_created')`

---

## 2. Forms Contract

### 2.1 `AudienceSegmentForm`
- **File:** `apps/ecommerce/forms/Personalization/AudienceSegments.py`
- **Fields:** `name`, `code`, `lifecycle_stage`, `recency_days_max`, `min_order_count`, `min_lifetime_spend`, `target_category`, `is_active`, `description`
- **Exclusions:** `tenant`, `number`, `cached_member_count`, `last_evaluated_at`, `created_at`, `updated_at`
- **Validation:** Normalizes `code` to lowercase slug. Validates `target_category` belongs to `request.tenant` (`reject_foreign`).

### 2.2 `RecommendationStrategyForm`
- **File:** `apps/ecommerce/forms/Personalization/RecommendationStrategies.py`
- **Fields:** `name`, `code`, `algorithm`, `placement`, `fallback_strategy`, `max_items`, `min_rating`, `same_brand_only`, `only_in_stock`, `target_category`, `target_segment`, `is_active`, `description`
- **Exclusions:** `tenant`, `number`, `created_at`, `updated_at`
- **Validation:** Normalizes `code` to lowercase slug. Validates `target_category` and `target_segment` belong to `request.tenant`.

### 2.3 `PersonalizedExperienceForm`
- **File:** `apps/ecommerce/forms/Personalization/PersonalizedExperiences.py`
- **Fields:** `name`, `experience_type`, `target_segment`, `target_category`, `target_product`, `headline`, `subheadline`, `cta_label`, `cta_url`, `hero_image_url`, `trigger_delay_hours`, `priority`, `start_date`, `end_date`, `is_active`
- **Exclusions:** `tenant`, `number`, `impression_count`, `click_count`, `conversion_count`, `created_at`, `updated_at`
- **Validation:** Validates foreign keys belong to `request.tenant`. Validates `end_date >= start_date` if both are provided.

### 2.4 `ShopperBehaviorEventFilterForm`
- **File:** `apps/ecommerce/forms/Personalization/ShopperBehaviorEvents.py`
- **Fields:** `event_type`, `session_key`, `date_from`, `date_to`

---

## 3. URLs & View Context Keys Contract

### 3.1 `AudienceSegment`
- List URL: `ecommerce:audiencesegment_list` (`/ecommerce/personalization/segments/`)
  - **Context Keys:** `segments`, `lifecycle_choices`, `selected_lifecycle`, `selected_active`, `search_query`
- Create URL: `ecommerce:audiencesegment_create` (`/ecommerce/personalization/segments/create/`)
  - **Context Keys:** `form`, `is_edit` (`False`)
- Detail URL: `ecommerce:audiencesegment_detail` (`/ecommerce/personalization/segments/<int:pk>/`)
  - **Context Keys:** `segment`, `experiences`, `recommendation_strategies`
- Edit URL: `ecommerce:audiencesegment_edit` (`/ecommerce/personalization/segments/<int:pk>/edit/`)
  - **Context Keys:** `form`, `segment`, `is_edit` (`True`)
- Delete URL: `ecommerce:audiencesegment_delete` (`/ecommerce/personalization/segments/<int:pk>/delete/`) (POST-only)
- Toggle URL: `ecommerce:audiencesegment_toggle` (`/ecommerce/personalization/segments/<int:pk>/toggle/`) (POST-only)
- Recalculate URL: `ecommerce:audiencesegment_recalculate` (`/ecommerce/personalization/segments/<int:pk>/recalculate/`) (POST-only)

### 3.2 `RecommendationStrategy`
- List URL: `ecommerce:recommendationstrategy_list` (`/ecommerce/personalization/strategies/`)
  - **Context Keys:** `strategies`, `algorithm_choices`, `placement_choices`, `selected_algorithm`, `selected_placement`, `selected_active`, `search_query`
- Create URL: `ecommerce:recommendationstrategy_create` (`/ecommerce/personalization/strategies/create/`)
  - **Context Keys:** `form`, `is_edit` (`False`)
- Detail URL: `ecommerce:recommendationstrategy_detail` (`/ecommerce/personalization/strategies/<int:pk>/`)
  - **Context Keys:** `strategy`
- Edit URL: `ecommerce:recommendationstrategy_edit` (`/ecommerce/personalization/strategies/<int:pk>/edit/`)
  - **Context Keys:** `form`, `strategy`, `is_edit` (`True`)
- Delete URL: `ecommerce:recommendationstrategy_delete` (`/ecommerce/personalization/strategies/<int:pk>/delete/`) (POST-only)
- Toggle URL: `ecommerce:recommendationstrategy_toggle` (`/ecommerce/personalization/strategies/<int:pk>/toggle/`) (POST-only)

### 3.3 `PersonalizedExperience`
- List URL: `ecommerce:personalizedexperience_list` (`/ecommerce/personalization/experiences/`)
  - **Context Keys:** `experiences`, `experience_type_choices`, `selected_type`, `selected_active`, `search_query`
- Create URL: `ecommerce:personalizedexperience_create` (`/ecommerce/personalization/experiences/create/`)
  - **Context Keys:** `form`, `is_edit` (`False`)
- Detail URL: `ecommerce:personalizedexperience_detail` (`/ecommerce/personalization/experiences/<int:pk>/`)
  - **Context Keys:** `experience`
- Edit URL: `ecommerce:personalizedexperience_edit` (`/ecommerce/personalization/experiences/<int:pk>/edit/`)
  - **Context Keys:** `form`, `experience`, `is_edit` (`True`)
- Delete URL: `ecommerce:personalizedexperience_delete` (`/ecommerce/personalization/experiences/<int:pk>/delete/`) (POST-only)
- Toggle URL: `ecommerce:personalizedexperience_toggle` (`/ecommerce/personalization/experiences/<int:pk>/toggle/`) (POST-only)

### 3.4 `ShopperBehaviorEvent`
- List URL: `ecommerce:shopperbehaviorevent_list` (`/ecommerce/personalization/events/`)
  - **Context Keys:** `events`, `event_type_choices`, `selected_type`, `search_query`
- Detail URL: `ecommerce:shopperbehaviorevent_detail` (`/ecommerce/personalization/events/<int:pk>/`)
  - **Context Keys:** `event`
- Delete URL: `ecommerce:shopperbehaviorevent_delete` (`/ecommerce/personalization/events/<int:pk>/delete/`) (POST-only)

### 3.5 `PersonalizationConsole`
- Console URL: `ecommerce:personalization_console` (`/ecommerce/personalization/console/`)
  - **Context Keys:** `segments`, `strategies`, `experiences`, `recent_events`, `cart_abandonment_count`, `active_vip_count`, `active_at_risk_count`, `products`, `selected_product_id`, `selected_segment_id`, `simulated_recommendations`, `simulated_experience`
- Simulate Recommendations URL: `ecommerce:recommendation_simulate` (`/ecommerce/personalization/console/simulate/`) (GET/HTMX)
  - **Context Keys:** `simulated_recommendations`, `strategy`

---

## 4. Templates Contract

- `templates/ecommerce/personalization/audiencesegment/list.html`
- `templates/ecommerce/personalization/audiencesegment/detail.html`
- `templates/ecommerce/personalization/audiencesegment/form.html`
- `templates/ecommerce/personalization/recommendationstrategy/list.html`
- `templates/ecommerce/personalization/recommendationstrategy/detail.html`
- `templates/ecommerce/personalization/recommendationstrategy/form.html`
- `templates/ecommerce/personalization/personalizedexperience/list.html`
- `templates/ecommerce/personalization/personalizedexperience/detail.html`
- `templates/ecommerce/personalization/personalizedexperience/form.html`
- `templates/ecommerce/personalization/shopperbehaviorevent/list.html`
- `templates/ecommerce/personalization/shopperbehaviorevent/detail.html`
- `templates/ecommerce/personalization/console/workbench.html`
- `templates/ecommerce/personalization/console/partials/recommendations_preview.html`
