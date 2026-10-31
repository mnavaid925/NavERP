# Contract — Sub-module 9.10: Marketing & Campaign Management (Module 9: eCommerce Management System, `ecommerce`)

- **Sub-module:** 9.10 Marketing & Campaign Management · **Module:** 9 eCommerce Management System · **App:** `apps/ecommerce`
- **Date:** 2026-10-31 · **Status:** FROZEN PRE-BUILD CONTRACT · **Phase:** 3.1 Spec
- **App Status:** Extending existing `apps/ecommerce/`. Next incremental migration: `0012_...`
- **Package Layout:** `MarketingCampaign/` across `models/`, `forms/`, `views/`, `urls/`, and templates `templates/ecommerce/marketing_campaign/`.

---

## 1. Models & CHOICES Contract

All top-level models inherit from `apps.ecommerce.models._base.TenantNumbered` (`tenant`, `number`, `created_at`, `updated_at`).

### 1.1 `MarketingCampaign` (`apps/ecommerce/models/MarketingCampaign/MarketingCampaigns.py`)
- **Table:** `ecommerce_marketing_campaign`
- **Number Prefix:** `EMCP` (`EMCP-00001`)
- **CHOICES:**
  - `CAMPAIGN_TYPE_CHOICES = [('newsletter_broadcast', 'Newsletter Broadcast'), ('drip_sequence', 'Automated Drip Sequence'), ('order_alert', 'Transactional Order Alert'), ('back_in_stock', 'Back in Stock Alert'), ('abandoned_cart', 'Abandoned Cart Recovery'), ('geofenced_blast', 'Geofenced Location Blast'), ('promotional_flash', 'Promotional Flash Sale')]`
  - `CHANNEL_CHOICES = [('email', 'Email'), ('sms', 'SMS'), ('push', 'Web / Mobile Push'), ('omnichannel', 'Omnichannel (Email + SMS + Push)')]`
  - `STATUS_CHOICES = [('draft', 'Draft'), ('scheduled', 'Scheduled'), ('sending', 'Sending / In Progress'), ('sent', 'Sent / Completed'), ('paused', 'Paused'), ('cancelled', 'Cancelled')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `name`: `CharField(max_length=150)`
  - `code`: `CharField(max_length=60)`
  - `campaign_type`: `CharField(max_length=30, choices=CAMPAIGN_TYPE_CHOICES, default='newsletter_broadcast')`
  - `channel`: `CharField(max_length=20, choices=CHANNEL_CHOICES, default='email')`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default='draft')`
  - `target_segment`: `ForeignKey('ecommerce.AudienceSegment', on_delete=SET_NULL, null=True, blank=True, related_name='marketing_campaigns')`
  - `target_product`: `ForeignKey('ecommerce.CatalogProduct', on_delete=SET_NULL, null=True, blank=True, related_name='marketing_campaigns')`
  - `subject`: `CharField(max_length=200, blank=True)`
  - `preview_text`: `CharField(max_length=255, blank=True)`
  - `content_body`: `TextField()`
  - `sender_name`: `CharField(max_length=100, blank=True)`
  - `sender_address`: `CharField(max_length=120, blank=True)`
  - `scheduled_at`: `DateTimeField(null=True, blank=True)`
  - `sent_at`: `DateTimeField(null=True, blank=True)`
  - `send_throttle_window_hours`: `PositiveIntegerField(default=16)`
  - `geofence_latitude`: `DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)`
  - `geofence_longitude`: `DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)`
  - `geofence_radius_km`: `DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)`
  - `recipient_count`: `PositiveIntegerField(default=0)`
  - `delivered_count`: `PositiveIntegerField(default=0)`
  - `opened_count`: `PositiveIntegerField(default=0)`
  - `clicked_count`: `PositiveIntegerField(default=0)`
  - `bounced_count`: `PositiveIntegerField(default=0)`
  - `unsubscribed_count`: `PositiveIntegerField(default=0)`
  - `complaint_count`: `PositiveIntegerField(default=0)`
  - `revenue_attributed`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='ecommerce_emcp_tenant_num_uniq')`
  - `UniqueConstraint(fields=['tenant', 'code'], name='ecommerce_emcp_code_uniq')`
  - `Index(fields=['tenant', 'status', 'campaign_type'], name='idx_emcp_ten_stat_type')`
  - `Index(fields=['tenant', 'scheduled_at'], name='idx_emcp_ten_sched_at')`

---

### 1.2 `AffiliatePartner` (`apps/ecommerce/models/MarketingCampaign/AffiliatePartners.py`)
- **Table:** `ecommerce_affiliate_partner`
- **Number Prefix:** `EAFF` (`EAFF-00001`)
- **CHOICES:**
  - `PARTNER_TYPE_CHOICES = [('affiliate', 'Affiliate Marketer'), ('influencer', 'Social Influencer'), ('brand_ambassador', 'Brand Ambassador'), ('customer_advocate', 'Customer Referral Advocate')]`
  - `COMMISSION_TYPE_CHOICES = [('percentage_net_sales', 'Percentage of Net Sales'), ('flat_per_order', 'Flat Dollar per Order'), ('tiered', 'Tiered Sales Volume')]`
  - `STATUS_CHOICES = [('pending_approval', 'Pending Approval'), ('active', 'Active'), ('suspended', 'Suspended'), ('inactive', 'Inactive')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `name`: `CharField(max_length=120)`
  - `party`: `ForeignKey('core.Party', on_delete=CASCADE, related_name='affiliate_profiles')`
  - `customer_profile`: `ForeignKey('ecommerce.CustomerAccountProfile', on_delete=SET_NULL, null=True, blank=True, related_name='affiliate_partnerships')`
  - `partner_type`: `CharField(max_length=25, choices=PARTNER_TYPE_CHOICES, default='affiliate')`
  - `referral_code`: `CharField(max_length=50)`
  - `referral_link_slug`: `CharField(max_length=60)`
  - `commission_type`: `CharField(max_length=25, choices=COMMISSION_TYPE_CHOICES, default='percentage_net_sales')`
  - `commission_rate`: `DecimalField(max_digits=6, decimal_places=2, default=Decimal('10.00'))`
  - `cookie_duration_days`: `PositiveIntegerField(default=30)`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default='pending_approval')`
  - `payout_threshold`: `DecimalField(max_digits=10, decimal_places=2, default=Decimal('50.00'))`
  - `payment_email`: `EmailField(blank=True)`
  - `total_orders_referred`: `PositiveIntegerField(default=0)`
  - `total_revenue_generated`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))`
  - `total_commission_earned`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))`
  - `total_commission_paid`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='ecommerce_eaff_tenant_num_uniq')`
  - `UniqueConstraint(fields=['tenant', 'referral_code'], name='ecommerce_eaff_code_uniq')`
  - `UniqueConstraint(fields=['tenant', 'referral_link_slug'], name='ecommerce_eaff_slug_uniq')`
  - `Index(fields=['tenant', 'status', 'partner_type'], name='idx_eaff_ten_stat_type')`

---

### 1.3 `AffiliateReferralConversion` (`apps/ecommerce/models/MarketingCampaign/AffiliateReferralConversions.py`)
- **Table:** `ecommerce_affiliate_referral_conversion`
- **Number Prefix:** `EARC` (`EARC-00001`)
- **CHOICES:**
  - `ATTRIBUTION_TYPE_CHOICES = [('referral_link', 'Referral Tracking Link'), ('coupon_code', 'Affiliate Coupon Code'), ('manual_credit', 'Manual Administrative Credit')]`
  - `STATUS_CHOICES = [('pending_review', 'Pending Review'), ('approved', 'Approved for Payout'), ('paid', 'Paid / Remitted'), ('voided_refund', 'Voided / Refund Clawback')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `affiliate`: `ForeignKey('ecommerce.AffiliatePartner', on_delete=CASCADE, related_name='conversions')`
  - `order`: `ForeignKey('ecommerce.EcommerceOrder', on_delete=CASCADE, related_name='affiliate_conversions')`
  - `referred_customer`: `ForeignKey('ecommerce.CustomerAccountProfile', on_delete=SET_NULL, null=True, blank=True, related_name='affiliate_conversions')`
  - `attribution_type`: `CharField(max_length=25, choices=ATTRIBUTION_TYPE_CHOICES, default='referral_link')`
  - `order_amount`: `DecimalField(max_digits=12, decimal_places=2)`
  - `commission_rate_applied`: `DecimalField(max_digits=6, decimal_places=2)`
  - `commission_amount`: `DecimalField(max_digits=10, decimal_places=2)`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default='pending_review')`
  - `payout_reference`: `CharField(max_length=100, blank=True)`
  - `paid_at`: `DateTimeField(null=True, blank=True)`
  - `notes`: `TextField(blank=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='ecommerce_earc_tenant_num_uniq')`
  - `UniqueConstraint(fields=['tenant', 'affiliate', 'order'], name='ecommerce_earc_aff_order_uniq')`
  - `Index(fields=['tenant', 'status', 'created_at'], name='idx_earc_ten_stat_created')`

---

### 1.4 `SeoMetadataRule` (`apps/ecommerce/models/MarketingCampaign/SeoMetadataRules.py`)
- **Table:** `ecommerce_seo_metadata_rule`
- **Number Prefix:** `ESEO` (`ESEO-00001`)
- **CHOICES:**
  - `RULE_TYPE_CHOICES = [('global_default', 'Global Storefront Default'), ('category_template', 'Category Level Dynamic Template'), ('product_template', 'Product Level Dynamic Template'), ('custom_url', 'Custom URL Specific Override')]`
  - `SCHEMA_TYPE_CHOICES = [('Product', 'Product (Schema.org)'), ('BreadcrumbList', 'BreadcrumbList (Schema.org)'), ('Organization', 'Organization (Schema.org)'), ('WebSite', 'WebSite (Schema.org)'), ('FAQPage', 'FAQPage (Schema.org)'), ('None', 'None / Disabled')]`
  - `ROBOTS_CHOICES = [('index_follow', 'index, follow'), ('noindex_follow', 'noindex, follow'), ('noindex_nofollow', 'noindex, nofollow'), ('index_nofollow', 'index, nofollow')]`
  - `CHANGEFREQ_CHOICES = [('always', 'always'), ('hourly', 'hourly'), ('daily', 'daily'), ('weekly', 'weekly'), ('monthly', 'monthly'), ('yearly', 'yearly'), ('never', 'never')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `name`: `CharField(max_length=120)`
  - `rule_type`: `CharField(max_length=25, choices=RULE_TYPE_CHOICES, default='product_template')`
  - `target_category`: `ForeignKey('ecommerce.StoreCategory', on_delete=SET_NULL, null=True, blank=True, related_name='seo_rules')`
  - `target_product`: `ForeignKey('ecommerce.CatalogProduct', on_delete=SET_NULL, null=True, blank=True, related_name='seo_rules')`
  - `url_path_pattern`: `CharField(max_length=255, blank=True)`
  - `meta_title_template`: `CharField(max_length=200)`
  - `meta_description_template`: `TextField()`
  - `json_ld_schema_type`: `CharField(max_length=30, choices=SCHEMA_TYPE_CHOICES, default='Product')`
  - `canonical_url_override`: `URLField(blank=True)`
  - `og_title`: `CharField(max_length=200, blank=True)`
  - `og_description`: `TextField(blank=True)`
  - `og_image_url`: `URLField(blank=True)`
  - `robots_directive`: `CharField(max_length=30, choices=ROBOTS_CHOICES, default='index_follow')`
  - `sitemap_included`: `BooleanField(default=True)`
  - `sitemap_priority`: `DecimalField(max_digits=3, decimal_places=2, default=Decimal('0.80'))`
  - `sitemap_changefreq`: `CharField(max_length=15, choices=CHANGEFREQ_CHOICES, default='weekly')`
  - `target_keyword`: `CharField(max_length=100, blank=True)`
  - `tracked_rank_position`: `PositiveIntegerField(null=True, blank=True)`
  - `rank_tracked_at`: `DateTimeField(null=True, blank=True)`
  - `is_active`: `BooleanField(default=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='ecommerce_eseo_tenant_num_uniq')`
  - `Index(fields=['tenant', 'is_active', 'rule_type'], name='idx_eseo_ten_act_type')`
  - `Index(fields=['tenant', 'target_keyword'], name='idx_eseo_ten_keyword')`

---

## 2. Forms Contract

### 2.1 `MarketingCampaignForm` (`apps/ecommerce/forms/MarketingCampaign/MarketingCampaigns.py`)
- **Model:** `MarketingCampaign`
- **Fields:** `['name', 'code', 'campaign_type', 'channel', 'status', 'target_segment', 'target_product', 'subject', 'preview_text', 'content_body', 'sender_name', 'sender_address', 'scheduled_at', 'send_throttle_window_hours', 'geofence_latitude', 'geofence_longitude', 'geofence_radius_km']`
- **Excluded:** `['tenant', 'number', 'sent_at', 'recipient_count', 'delivered_count', 'opened_count', 'clicked_count', 'bounced_count', 'unsubscribed_count', 'complaint_count', 'revenue_attributed', 'created_at', 'updated_at']`

### 2.2 `AffiliatePartnerForm` (`apps/ecommerce/forms/MarketingCampaign/AffiliatePartners.py`)
- **Model:** `AffiliatePartner`
- **Fields:** `['name', 'party', 'customer_profile', 'partner_type', 'referral_code', 'referral_link_slug', 'commission_type', 'commission_rate', 'cookie_duration_days', 'status', 'payout_threshold', 'payment_email']`
- **Excluded:** `['tenant', 'number', 'total_orders_referred', 'total_revenue_generated', 'total_commission_earned', 'total_commission_paid', 'created_at', 'updated_at']`

### 2.3 `AffiliateReferralConversionForm` (`apps/ecommerce/forms/MarketingCampaign/AffiliateReferralConversions.py`)
- **Model:** `AffiliateReferralConversion`
- **Fields:** `['affiliate', 'order', 'referred_customer', 'attribution_type', 'order_amount', 'commission_rate_applied', 'status', 'payout_reference', 'notes']`
- **Excluded:** `['tenant', 'number', 'commission_amount', 'paid_at', 'created_at', 'updated_at']`

### 2.4 `SeoMetadataRuleForm` (`apps/ecommerce/forms/MarketingCampaign/SeoMetadataRules.py`)
- **Model:** `SeoMetadataRule`
- **Fields:** `['name', 'rule_type', 'target_category', 'target_product', 'url_path_pattern', 'meta_title_template', 'meta_description_template', 'json_ld_schema_type', 'canonical_url_override', 'og_title', 'og_description', 'og_image_url', 'robots_directive', 'sitemap_included', 'sitemap_priority', 'sitemap_changefreq', 'target_keyword', 'is_active']`
- **Excluded:** `['tenant', 'number', 'tracked_rank_position', 'rank_tracked_at', 'created_at', 'updated_at']`

---

## 3. URLs Contract

All URLs registered under `apps/ecommerce/urls/MarketingCampaign/`:
- `marketing/` $\rightarrow$ `name='marketing_dashboard'`
- `marketing/feed/social-catalog/` $\rightarrow$ `name='social_commerce_feed'`
- `marketing/campaigns/` $\rightarrow$ `name='marketingcampaign_list'`
- `marketing/campaigns/create/` $\rightarrow$ `name='marketingcampaign_create'`
- `marketing/campaigns/<int:pk>/` $\rightarrow$ `name='marketingcampaign_detail'`
- `marketing/campaigns/<int:pk>/edit/` $\rightarrow$ `name='marketingcampaign_edit'`
- `marketing/campaigns/<int:pk>/delete/` $\rightarrow$ `name='marketingcampaign_delete'`
- `marketing/campaigns/<int:pk>/send/` $\rightarrow$ `name='marketingcampaign_send'`
- `marketing/affiliates/` $\rightarrow$ `name='affiliatepartner_list'`
- `marketing/affiliates/create/` $\rightarrow$ `name='affiliatepartner_create'`
- `marketing/affiliates/<int:pk>/` $\rightarrow$ `name='affiliatepartner_detail'`
- `marketing/affiliates/<int:pk>/edit/` $\rightarrow$ `name='affiliatepartner_edit'`
- `marketing/affiliates/<int:pk>/delete/` $\rightarrow$ `name='affiliatepartner_delete'`
- `marketing/affiliates/<int:pk>/approve/` $\rightarrow$ `name='affiliatepartner_approve'`
- `marketing/conversions/` $\rightarrow$ `name='affiliatereferralconversion_list'`
- `marketing/conversions/create/` $\rightarrow$ `name='affiliatereferralconversion_create'`
- `marketing/conversions/<int:pk>/` $\rightarrow$ `name='affiliatereferralconversion_detail'`
- `marketing/conversions/<int:pk>/edit/` $\rightarrow$ `name='affiliatereferralconversion_edit'`
- `marketing/conversions/<int:pk>/delete/` $\rightarrow$ `name='affiliatereferralconversion_delete'`
- `marketing/conversions/<int:pk>/approve/` $\rightarrow$ `name='affiliatereferralconversion_approve'`
- `marketing/conversions/<int:pk>/void/` $\rightarrow$ `name='affiliatereferralconversion_void'`
- `marketing/seo-rules/` $\rightarrow$ `name='seometadatarule_list'`
- `marketing/seo-rules/create/` $\rightarrow$ `name='seometadatarule_create'`
- `marketing/seo-rules/<int:pk>/` $\rightarrow$ `name='seometadatarule_detail'`
- `marketing/seo-rules/<int:pk>/edit/` $\rightarrow$ `name='seometadatarule_edit'`
- `marketing/seo-rules/<int:pk>/delete/` $\rightarrow$ `name='seometadatarule_delete'`
- `marketing/seo-rules/<int:pk>/toggle/` $\rightarrow$ `name='seometadatarule_toggle'`

---

## 4. View Context Keys Contract

### 4.1 Marketing Dashboard (`marketing_dashboard`)
- Context keys:
  - `kpis`: dict with `total_campaigns`, `total_delivered`, `total_revenue_attributed`, `total_affiliates`, `total_affiliate_revenue`, `active_seo_rules`
  - `recent_campaigns`: QuerySet of recent `MarketingCampaign`
  - `top_affiliates`: QuerySet of top `AffiliatePartner`
  - `recent_conversions`: QuerySet of recent `AffiliateReferralConversion`
  - `seo_rules`: QuerySet of active `SeoMetadataRule`
  - `active_tab`: str (`"overview"`, `"social"`, etc.)

### 4.2 Marketing Campaign Views
- `marketingcampaign_list`:
  - `campaigns`: paginated `Page` object
  - `channel_choices`: `MarketingCampaign.CHANNEL_CHOICES`
  - `status_choices`: `MarketingCampaign.STATUS_CHOICES`
  - `campaign_type_choices`: `MarketingCampaign.CAMPAIGN_TYPE_CHOICES`
  - `selected_channel`: `request.GET.get('channel', '')`
  - `selected_status`: `request.GET.get('status', '')`
  - `selected_type`: `request.GET.get('campaign_type', '')`
  - `search_query`: `request.GET.get('q', '')`
- `marketingcampaign_detail`:
  - `campaign`: `MarketingCampaign` instance
- `marketingcampaign_create`:
  - `form`: `MarketingCampaignForm`
- `marketingcampaign_edit`:
  - `form`: `MarketingCampaignForm`
  - `campaign`: `MarketingCampaign` instance

### 4.3 Affiliate Partner Views
- `affiliatepartner_list`:
  - `partners`: paginated `Page` object
  - `partner_type_choices`: `AffiliatePartner.PARTNER_TYPE_CHOICES`
  - `status_choices`: `AffiliatePartner.STATUS_CHOICES`
  - `commission_type_choices`: `AffiliatePartner.COMMISSION_TYPE_CHOICES`
  - `selected_type`: `request.GET.get('partner_type', '')`
  - `selected_status`: `request.GET.get('status', '')`
  - `search_query`: `request.GET.get('q', '')`
- `affiliatepartner_detail`:
  - `partner`: `AffiliatePartner` instance
  - `conversions`: related conversions queryset
- `affiliatepartner_create`:
  - `form`: `AffiliatePartnerForm`
- `affiliatepartner_edit`:
  - `form`: `AffiliatePartnerForm`
  - `partner`: `AffiliatePartner` instance

### 4.4 Affiliate Referral Conversion Views
- `affiliatereferralconversion_list`:
  - `conversions`: paginated `Page` object
  - `status_choices`: `AffiliateReferralConversion.STATUS_CHOICES`
  - `attribution_type_choices`: `AffiliateReferralConversion.ATTRIBUTION_TYPE_CHOICES`
  - `selected_status`: `request.GET.get('status', '')`
  - `selected_attribution`: `request.GET.get('attribution_type', '')`
  - `search_query`: `request.GET.get('q', '')`
- `affiliatereferralconversion_detail`:
  - `conversion`: `AffiliateReferralConversion` instance
- `affiliatereferralconversion_create`:
  - `form`: `AffiliateReferralConversionForm`
- `affiliatereferralconversion_edit`:
  - `form`: `AffiliateReferralConversionForm`
  - `conversion`: `AffiliateReferralConversion` instance

### 4.5 SEO Metadata Rule Views
- `seometadatarule_list`:
  - `rules`: paginated `Page` object
  - `rule_type_choices`: `SeoMetadataRule.RULE_TYPE_CHOICES`
  - `schema_type_choices`: `SeoMetadataRule.SCHEMA_TYPE_CHOICES`
  - `robots_choices`: `SeoMetadataRule.ROBOTS_CHOICES`
  - `selected_type`: `request.GET.get('rule_type', '')`
  - `selected_schema`: `request.GET.get('schema_type', '')`
  - `selected_active`: `request.GET.get('is_active', '')`
  - `search_query`: `request.GET.get('q', '')`
- `seometadatarule_detail`:
  - `rule`: `SeoMetadataRule` instance
- `seometadatarule_create`:
  - `form`: `SeoMetadataRuleForm`
- `seometadatarule_edit`:
  - `form`: `SeoMetadataRuleForm`
  - `rule`: `SeoMetadataRule` instance

---

## 5. Templates Mapping

Templates live under `templates/ecommerce/marketing_campaign/`:
- `campaign/list.html`, `campaign/detail.html`, `campaign/form.html`
- `affiliate/list.html`, `affiliate/detail.html`, `affiliate/form.html`
- `conversion/list.html`, `conversion/detail.html`, `conversion/form.html`
- `seo_rule/list.html`, `seo_rule/detail.html`, `seo_rule/form.html`
- `dashboard/dashboard.html`
