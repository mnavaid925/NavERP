---
name: ecommerce
description: Work on the eCommerce module (Module 9 — 9.1 Product Catalog, 9.2 Inventory & Stock, 9.3 Pricing & Promotion Engine, 9.4 Shopping Cart & Checkout, 9.5 Order Management System (OMS), 9.6 Customer Account & Profile, 9.7 Search & Product Discovery, 9.8 Personalization & Recommendation Engine, 9.9 Content Management System (CMS), 9.10 Marketing & Campaign Management, 9.11 Marketplace & Multi-Vendor, 9.12 Subscription & Recurring Commerce, 9.13 Reviews & User-Generated Content, 9.14 Customer Service & Support, 9.15 Analytics & Business Intelligence, 9.16 Mobile Commerce, 9.17 B2B & Wholesale Commerce, 9.18 Fraud & Risk Management: rule evaluation engines, composite transaction risk scoring, multi-tier risk decisions [allow, review, challenge, reject], chargeback dispute workflows with reason codes and representment evidence tracking, account security alerts with automated threat mitigation [mfa_required, session_revoked, account_locked], fraud risk hub cockpit, categories, products, variants, fulfillment centers, stock allocations, ATP, backorders, dynamic pricing, coupons, flash sales, competitor monitoring, carts, checkout funnels, orders, order lines, fulfillment routing rules, carrier dispatch tracking, return merchandise authorizations, customer account profiles, address preferences, wishlists, GDPR privacy requests, search synonyms, facet configurations, merchandising rules, search query telemetry, interactive search workbench console, instant autocomplete, and search discovery analytics). Use when the user asks to add/change/debug anything under apps/ecommerce or templates/ecommerce, extend the eCommerce seeder, touch eCommerce sidebar wiring (LIVE_LINKS 9.1 through 9.18), or invokes /ecommerce.
---

# eCommerce Module (Module 9: 9.1 Catalog, 9.2 Inventory & Stock, 9.3 Pricing & Promotion, 9.4 Shopping Cart & Checkout, 9.5 Order Management System, 9.6 Customer Account & Profile, 9.7 Search & Product Discovery, 9.8 Personalization & Recommendation Engine, 9.9 Content Management System, 9.10 Marketing & Campaign Management, 9.11 Marketplace & Multi-Vendor, 9.12 Subscription & Recurring Commerce, 9.13 Reviews & User-Generated Content, 9.14 Customer Service & Support, 9.15 Analytics & Business Intelligence, 9.16 Mobile Commerce, 9.17 B2B & Wholesale Commerce, 9.18 Fraud & Risk Management)

The eCommerce Management System handles online store merchandising, product catalog management, SKU variants, product relationships, multi-node fulfillment center routing, real-time stock allocations, available-to-promise (ATP) calculation, backorder/pre-order waitlists, multi-channel inventory synchronization feeds, dynamic rule-based pricing engines, coupon code promotions, lightning flash sales, competitive repricing intelligence, persistent and guest shopping carts, 1-click cart abandonment recovery, multi-step and one-page checkout conversion funnels, flexible shipping calculation matrices, payment gateway orchestration, an enterprise omnichannel Order Management System (OMS) with intelligent order fulfillment routing, carrier dispatch tracking, return merchandise authorization (RMA) workflows, an enterprise Customer Account & Profile subsystem with tiered loyalty status, multi-mode authentication, address book delivery preferences, multi-wishlist curation, statutory GDPR/CCPA privacy request management, an enterprise Search & Product Discovery engine featuring bidirectional/unidirectional synonyms, dynamic multi-select and slider facet configurations, rule-driven merchandising, query telemetry analytics, a Content Management System (CMS) featuring dynamic page building, editorial blog posts, digital asset management (DAM), reusable content blocks, live preview, an omnichannel Customer Service & Support suite with WISMO resolution, SLA tracking, an enterprise Analytics & Business Intelligence (BI) engine with daily sales snapshots, cohort retention curves, merchandising turnover velocity, multi-touch marketing attribution, a comprehensive Mobile Commerce engine (9.16) powering Progressive Web Apps (PWA) manifest generation and offline caching, native iOS/Android device registrations with APNs/FCM push telemetry, rich push notification campaigns, circular store locator geofences with curbside pickup arrival radar, an enterprise B2B & Wholesale Commerce engine (9.17) providing corporate buyer account management, tiered buyer hierarchies with approval thresholds, quote request (RFQ) negotiation state machines with order conversion and trade credit limit tracking, matrix SKU fast-entry ordering with CSV spreadsheet upload, a simulated PunchOut procurement gateway (cXML/OCI), and an enterprise Fraud & Risk Management engine (9.18) powering heuristic and velocity fraud rule evaluation, composite transaction risk assessment scoring with automated decisions and manual analyst review queues, chargeback and inquiry dispute case management with representment evidence tracking, and account security alert monitoring with automated policy responses. It integrates seamlessly with the NavERP core spine and physical supply chain:
- **Tenant Isolation**: Every model inherits `TenantNumbered` (`tenant`, `number`, `created_at`, `updated_at`). All queries and lookups are strictly tenant-scoped (`tenant=request.tenant`).
- **Physical Inventory Boundary**: Products, variants, and fulfillment centers link to `scm.Item` and `scm.Location` via string foreign keys. Module 9 does not duplicate inventory ledger balances or physical bin movements; physical warehouse stock and valuation remain anchored in `apps/scm` and `apps/inventory`, while eCommerce manages digital storefront availability, reservations, buffers, and channel broadcasting.
- **App Path**: `apps/ecommerce/`
- **Templates**: `templates/ecommerce/`
- **URL Prefix**: `/ecommerce/` (`app_name="ecommerce"`)
- **Mounted in**: `config/urls.py` as `path("ecommerce/", include("apps.ecommerce.urls", namespace="ecommerce"))`
- **Installed App**: `apps.ecommerce` in `config/settings.py`

---

## 1. App Layout & Package Architecture

All four layers (`models`, `forms`, `views`, `urls`) are organized as packages partitioned by sub-module:

```
apps/ecommerce/
├── models/
│   ├── _base.py                     # TenantNumbered abstract base model
│   ├── ProductCatalog/
│   │   ├── StoreCategories.py       # StoreCategory model (ECAT-)
│   │   ├── CatalogProducts.py       # CatalogProduct model (EPRD-)
│   │   ├── ProductVariants.py       # ProductVariant model (PVR-)
│   │   └── ProductRelationships.py  # ProductRelationship model (PRL-)
│   ├── InventoryStock/
│   │   ├── FulfillmentCenters.py    # FulfillmentCenter model (EFC-)
│   │   ├── InventoryAllocations.py  # InventoryAllocation model (EAL-)
│   │   ├── BackorderPolicies.py     # BackorderPolicy model (EBK-)
│   │   └── ChannelInventorySyncs.py # ChannelInventorySync model (ESYN-)
│   ├── PricingPromotion/
│   │   ├── DynamicPriceRules.py     # DynamicPriceRule model (EDPR-)
│   │   ├── CouponPromotions.py      # CouponPromotion model (ECPN-)
│   │   ├── FlashSales.py            # FlashSale model (EFLS-)
│   │   └── CompetitorPriceMonitors.py # CompetitorPriceMonitor model (ECPM-)
│   ├── CartCheckout/
│   │   ├── Carts.py                 # Cart (ECRT-) & CartItem models
│   │   ├── CheckoutSessions.py      # CheckoutSession model (ECKS-)
│   │   ├── ShippingMethods.py       # ShippingMethodConfig model (ESHP-)
│   │   └── PaymentMethods.py        # PaymentMethodConfig model (EPMC-)
│   ├── OrderManagement/
│   │   ├── EcommerceOrders.py       # EcommerceOrder (EORD-) & EcommerceOrderLine models
│   │   ├── OrderRoutingRules.py     # OrderRoutingRule model (EORT-)
│   │   ├── OrderFulfillments.py     # OrderFulfillment model (EFUL-)
│   │   └── ReturnMerchandiseAuthorizations.py # ReturnMerchandiseAuthorization model (ERMA-)
│   ├── CustomerProfile/
│   │   ├── CustomerAccountProfiles.py # CustomerAccountProfile model (ECAP-)
│   │   ├── CustomerAddressPreferences.py # CustomerAddressPreference model (ECAD-)
│   │   ├── CustomerWishlists.py     # CustomerWishlist (EWSL-) & CustomerWishlistItem models
│   │   └── CustomerPrivacyRequests.py # CustomerPrivacyRequest model (ECPR-)
│   ├── SearchDiscovery/
│   │   ├── SearchSynonyms.py        # SearchSynonym model (ESYM-)
│   │   ├── SearchFacetConfigs.py    # SearchFacetConfig model (ESFC-)
│   │   ├── SearchMerchandisingRules.py # SearchMerchandisingRule model (ESMR-)
│   │   └── SearchQueryLogs.py       # SearchQueryLog model (ESQL-)
│   ├── Personalization/
│   │   ├── AudienceSegments.py      # AudienceSegment model (ESEG-)
│   │   ├── RecommendationStrategies.py # RecommendationStrategy model (EREC-)
│   │   ├── PersonalizedExperiences.py # PersonalizedExperience model (EPEX-)
│   │   └── ShopperBehaviorEvents.py # ShopperBehaviorEvent model (ESBE-)
│   ├── MarketingCampaign/
│   │   ├── MarketingCampaigns.py    # MarketingCampaign model (EMCP-)
│   │   ├── AffiliatePartners.py     # AffiliatePartner model (EAFF-)
│   │   ├── AffiliateReferralConversions.py # AffiliateReferralConversion model (EARC-)
│   │   └── SeoMetadataRules.py      # SeoMetadataRule model (ESEO-)
│   ├── Marketplace/
│   │   ├── MarketplaceVendors.py    # MarketplaceVendor model (EMKV-)
│   │   ├── VendorProductListings.py # VendorProductListing model (EVPL-)
│   │   ├── VendorSubOrders.py       # VendorSubOrder model (EVSO-)
│   │   └── VendorPayouts.py         # VendorPayout model (EVPO-)
│   ├── ContentManagement/
│   │   ├── CmsPages.py              # CmsPage model (EPAG-)
│   │   ├── BlogArticles.py          # BlogArticle model (EBLG-)
│   │   ├── MediaAssets.py           # MediaAsset model (EMED-)
│   │   └── ContentBlocks.py         # ContentBlock model (EBLK-)
│   ├── AnalyticsBi/
│   │   ├── DailySalesSnapshots.py   # DailySalesSnapshot model (EDSS-)
│   │   ├── CustomerCohortMetrics.py # CustomerCohortMetric model (ECCM-)
│   │   ├── ProductMerchandisingMetrics.py # ProductMerchandisingMetric model (EPMM-)
│   │   └── AttributionTouchpoints.py # AttributionTouchpoint model (EATT-)
│   ├── MobileCommerce/
│   │   ├── MobileAppConfigs.py      # MobileAppConfig model (EMAC-)
│   │   ├── MobileDeviceRegistrations.py # MobileDeviceRegistration model (EMDR-)
│   │   ├── MobilePushCampaigns.py   # MobilePushCampaign model (EMPC-)
│   │   └── MobileLocationRules.py   # MobileLocationRule model (EMLR-)
│   ├── B2bWholesale/
│   │   ├── B2bCompanyAccounts.py    # B2bCompanyAccount model (EBCA-)
│   │   ├── B2bCompanyUsers.py       # B2bCompanyUser model (EBCU-)
│   │   ├── B2bQuoteRequests.py      # B2bQuoteRequest (EBQR-) & B2bQuoteItem models
│   │   └── B2bQuickOrderTemplates.py # B2bQuickOrderTemplate (EBQT-) & B2bQuickOrderItem models
│   ├── FraudRisk/
│   │   ├── FraudRules.py            # FraudRule model (EFRR-)
│   │   ├── TransactionRiskAssessments.py # TransactionRiskAssessment model (ETRA-)
│   │   ├── ChargebackDisputes.py    # ChargebackDispute model (ECBD-)
│   │   └── AccountSecurityAlerts.py # AccountSecurityAlert model (EASA-)
│   └── __init__.py                  # Surgical re-exports of all models
├── forms/
│   ├── _common.py                   # TenantModelForm, TenantUniqueMixin, reject_foreign
│   ├── ProductCatalog/
│   │   ├── StoreCategories.py       # StoreCategoryForm
│   │   ├── CatalogProducts.py       # CatalogProductForm
│   │   ├── ProductVariants.py       # ProductVariantForm
│   │   ├── ProductRelationships.py  # ProductRelationshipForm
│   │   └── BulkOperations.py        # ProductImportForm
│   ├── InventoryStock/
│   │   ├── FulfillmentCenters.py    # FulfillmentCenterForm
│   │   ├── InventoryAllocations.py  # InventoryAllocationForm, StockAdjustmentActionForm
│   │   ├── BackorderPolicies.py     # BackorderPolicyForm
│   │   └── ChannelInventorySyncs.py # ChannelInventorySyncForm
│   ├── PricingPromotion/
│   │   ├── DynamicPriceRules.py     # DynamicPriceRuleForm
│   │   ├── CouponPromotions.py      # CouponPromotionForm
│   │   ├── FlashSales.py            # FlashSaleForm
│   │   └── CompetitorPriceMonitors.py # CompetitorPriceMonitorForm
│   ├── CartCheckout/
│   │   ├── Carts.py                 # CartForm, CartItemForm
│   │   ├── CheckoutSessions.py      # CheckoutSessionForm, CheckoutStepAdvanceForm
│   │   ├── ShippingMethods.py       # ShippingMethodConfigForm
│   │   └── PaymentMethods.py        # PaymentMethodConfigForm
│   ├── OrderManagement/
│   │   ├── EcommerceOrders.py       # EcommerceOrderForm, EcommerceOrderLineForm
│   │   ├── OrderRoutingRules.py     # OrderRoutingRuleForm
│   │   ├── OrderFulfillments.py     # OrderFulfillmentForm
│   │   └── ReturnMerchandiseAuthorizations.py # ReturnMerchandiseAuthorizationForm
│   ├── CustomerProfile/
│   │   ├── CustomerAccountProfiles.py # CustomerAccountProfileForm
│   │   ├── CustomerAddressPreferences.py # CustomerAddressPreferenceForm
│   │   ├── CustomerWishlists.py     # CustomerWishlistForm, CustomerWishlistItemForm
│   │   └── CustomerPrivacyRequests.py # CustomerPrivacyRequestForm
│   ├── SearchDiscovery/
│   │   ├── SearchSynonyms.py        # SearchSynonymForm
│   │   ├── SearchFacetConfigs.py    # SearchFacetConfigForm
│   │   ├── SearchMerchandisingRules.py # SearchMerchandisingRuleForm
│   │   └── SearchQueryLogs.py       # SearchQueryLogForm, SearchQueryLogFilterForm
│   ├── Personalization/
│   │   ├── AudienceSegments.py      # AudienceSegmentForm
│   │   ├── RecommendationStrategies.py # RecommendationStrategyForm
│   │   ├── PersonalizedExperiences.py # PersonalizedExperienceForm
│   │   └── ShopperBehaviorEvents.py # ShopperBehaviorEventFilterForm
│   ├── Marketplace/
│   │   ├── MarketplaceVendorForms.py # MarketplaceVendorForm, KYC, Suspension
│   │   ├── VendorProductListingForms.py # VendorProductListingForm, Moderation
│   │   ├── VendorSubOrderForms.py   # VendorSubOrderForm, Fulfillment, Dispute
│   │   └── VendorPayoutForms.py     # VendorPayoutForm, PayoutApproval
│   ├── ContentManagement/
│   │   ├── CmsPages.py              # CmsPageForm
│   │   ├── BlogArticles.py          # BlogArticleForm
│   │   ├── MediaAssets.py           # MediaAssetForm
│   │   └── ContentBlocks.py         # ContentBlockForm
│   ├── AnalyticsBi/
│   │   ├── DailySalesSnapshots.py   # DailySalesSnapshotForm
│   │   ├── CustomerCohortMetrics.py # CustomerCohortMetricForm
│   │   ├── ProductMerchandisingMetrics.py # ProductMerchandisingMetricForm
│   │   └── AttributionTouchpoints.py # AttributionTouchpointForm
│   ├── MobileCommerce/
│   │   ├── MobileAppConfigs.py      # MobileAppConfigForm
│   │   ├── MobileDeviceRegistrations.py # MobileDeviceRegistrationForm
│   │   ├── MobilePushCampaigns.py   # MobilePushCampaignForm
│   │   └── MobileLocationRules.py   # MobileLocationRuleForm
│   ├── B2bWholesale/
│   │   ├── B2bCompanyAccounts.py    # B2bCompanyAccountForm
│   │   ├── B2bCompanyUsers.py       # B2bCompanyUserForm
│   │   ├── B2bQuoteRequests.py      # B2bQuoteRequestForm, B2bQuoteItemForm
│   │   └── B2bQuickOrderTemplates.py # B2bQuickOrderTemplateForm, B2bQuickOrderItemForm
│   ├── FraudRisk/
│   │   ├── FraudRules.py            # FraudRuleForm
│   │   ├── TransactionRiskAssessments.py # TransactionRiskAssessmentForm
│   │   ├── ChargebackDisputes.py    # ChargebackDisputeForm
│   │   └── AccountSecurityAlerts.py # AccountSecurityAlertForm
│   └── __init__.py                  # Re-exports of all forms
├── views/
│   ├── _common.py                   # ecommerce_scope, ecommerce_object, csv_safe, write_audit_log
│   ├── ProductCatalog/
│   │   ├── Overview.py              # catalog_overview dashboard
│   │   ├── StoreCategories.py       # storecategory CRUD
│   │   ├── CatalogProducts.py       # catalogproduct CRUD + publish action
│   │   ├── ProductVariants.py       # productvariant CRUD
│   │   ├── ProductRelationships.py  # productrelationship CRUD
│   │   └── BulkOperations.py        # product_import_csv, product_export_csv
│   ├── InventoryStock/
│   │   ├── Operations.py            # inventory_operations console dashboard
│   │   ├── FulfillmentCenters.py    # fulfillmentcenter CRUD
│   │   ├── InventoryAllocations.py  # inventoryallocation CRUD + stock adjust
│   │   ├── BackorderPolicies.py     # backorderpolicy CRUD
│   │   └── ChannelInventorySyncs.py # channelinventorysync CRUD + broadcast trigger
│   ├── PricingPromotion/
│   │   ├── DynamicPriceRules.py     # dynamicpricerule CRUD
│   │   ├── CouponPromotions.py      # couponpromotion CRUD
│   │   ├── FlashSales.py            # flashsale CRUD
│   │   └── CompetitorPriceMonitors.py # competitorpricemonitor CRUD + sync action
│   ├── CartCheckout/
│   │   ├── Carts.py                 # cart CRUD + recover action
│   │   ├── CheckoutSessions.py      # checkoutsession CRUD + advance action
│   │   ├── ShippingMethods.py       # shippingmethodconfig CRUD + toggle action
│   │   └── PaymentMethods.py        # paymentmethodconfig CRUD + toggle action
│   ├── OrderManagement/
│   │   ├── EcommerceOrders.py       # ecommerceorder CRUD + cancel action
│   │   ├── OrderRoutingRules.py     # orderroutingrule CRUD
│   │   ├── OrderFulfillments.py     # orderfulfillment CRUD + ship action
│   │   └── ReturnMerchandiseAuthorizations.py # returnmerchandiseauthorization CRUD + complete action
│   ├── CustomerProfile/
│   │   ├── CustomerAccountProfiles.py # customeraccountprofile CRUD
│   │   ├── CustomerAddressPreferences.py # customeraddresspreference CRUD
│   │   ├── CustomerWishlists.py     # customerwishlist CRUD + item_add, item_delete
│   │   └── CustomerPrivacyRequests.py # customerprivacyrequest CRUD + generate_export, anonymize
│   ├── SearchDiscovery/
│   │   ├── SearchSynonyms.py        # searchsynonym CRUD + toggle
│   │   ├── SearchFacetConfigs.py    # searchfacetconfig CRUD + toggle
│   │   ├── SearchMerchandisingRules.py # searchmerchandisingrule CRUD + toggle
│   │   ├── SearchQueryLogs.py       # searchquerylog list, detail, delete
│   │   └── SearchConsole.py         # search_console, search_autocomplete, search_analytics
│   ├── Personalization/
│   │   ├── AudienceSegments.py      # audiencesegment CRUD + toggle, recalculate
│   │   ├── RecommendationStrategies.py # recommendationstrategy CRUD + toggle
│   │   ├── PersonalizedExperiences.py # personalizedexperience CRUD + toggle
│   │   ├── ShopperBehaviorEvents.py # shopperbehaviorevent list, detail, delete
│   │   └── PersonalizationConsole.py # personalization_console, recommendation_simulate
│   ├── Marketplace/
│   │   ├── MarketplaceConsoleViews.py # marketplace_console
│   │   ├── MarketplaceVendorViews.py # marketplacevendor CRUD + kyc, suspend
│   │   ├── VendorProductListingViews.py # vendorproductlisting CRUD + moderate
│   │   ├── VendorSubOrderViews.py   # vendorsuborder CRUD + fulfill, dispute
│   │   └── VendorPayoutViews.py     # vendorpayout CRUD + execute
│   ├── ContentManagement/
│   │   ├── CmsPages.py              # cmspage CRUD + preview action
│   │   ├── BlogArticles.py          # blogarticle CRUD
│   │   ├── MediaAssets.py           # mediaasset CRUD
│   │   └── ContentBlocks.py         # contentblock CRUD
│   ├── AnalyticsBi/
│   │   ├── DailySalesSnapshots.py   # dailysalessnapshot CRUD + recalculate action
│   │   ├── CustomerCohortMetrics.py # customercohortmetric CRUD + recalculate action
│   │   ├── ProductMerchandisingMetrics.py # productmerchandisingmetric CRUD + recalculate action
│   │   ├── AttributionTouchpoints.py # attributiontouchpoint CRUD
│   │   └── AnalyticsCockpit.py      # analytics_cockpit executive monitoring dashboard
│   ├── MobileCommerce/
│   │   ├── MobileHub.py             # mobile_hub command center console
│   │   ├── MobileAppConfigs.py      # mobileappconfig CRUD + pwa_manifest_json endpoint
│   │   ├── MobileDeviceRegistrations.py # mobiledeviceregistration CRUD + telemetry ping
│   │   ├── MobilePushCampaigns.py   # mobilepushcampaign CRUD + test_send dispatch simulation
│   │   └── MobileLocationRules.py   # mobilelocationrule CRUD + geofence simulation
│   ├── B2bWholesale/
│   │   ├── B2bWholesaleHub.py       # b2b_wholesale_hub console dashboard
│   │   ├── B2bCompanyAccounts.py    # b2bcompanyaccount CRUD & punchout test
│   │   ├── B2bCompanyUsers.py       # b2bcompanyuser CRUD
│   │   ├── B2bQuoteRequests.py      # b2bquoterequest CRUD + state transitions & convert-order
│   │   └── B2bQuickOrderTemplates.py # b2bquickordertemplate CRUD, quick_order_matrix & CSV import
│   ├── FraudRisk/
│   │   ├── FraudRules.py            # fraud_risk_hub & fraudrule CRUD
│   │   ├── TransactionRiskAssessments.py # transactionriskassessment CRUD
│   │   ├── ChargebackDisputes.py    # chargebackdispute CRUD
│   │   └── AccountSecurityAlerts.py # accountsecurityalert CRUD
│   └── __init__.py                  # Re-exports of all views
├── urls/
│   ├── ProductCatalog/
│   │   ├── Overview.py              # overview & dashboard paths
│   │   ├── StoreCategories.py       # categories/ paths
│   │   ├── CatalogProducts.py       # products/ paths
│   │   ├── ProductVariants.py       # variants/ paths
│   │   ├── ProductRelationships.py  # relationships/ paths
│   │   └── BulkOperations.py        # import/ and export/ paths
│   ├── InventoryStock/
│   │   ├── Operations.py            # inventory/ console path
│   │   ├── FulfillmentCenters.py    # inventory/centers/ paths
│   │   ├── InventoryAllocations.py  # inventory/allocations/ paths
│   │   ├── BackorderPolicies.py     # inventory/backorders/ paths
│   │   └── ChannelInventorySyncs.py # inventory/sync/ paths
│   ├── PricingPromotion/
│   │   ├── DynamicPriceRules.py     # pricing/rules/ paths
│   │   ├── CouponPromotions.py      # pricing/coupons/ paths
│   │   ├── FlashSales.py            # pricing/flash-sales/ paths
│   │   └── CompetitorPriceMonitors.py # pricing/competitors/ paths
│   ├── CartCheckout/
│   │   ├── Carts.py                 # cart-checkout/carts/ paths
│   │   ├── CheckoutSessions.py      # cart-checkout/sessions/ paths
│   │   ├── ShippingMethods.py       # cart-checkout/shipping-methods/ paths
│   │   └── PaymentMethods.py        # cart-checkout/payment-methods/ paths
│   ├── OrderManagement/
│   │   ├── EcommerceOrders.py       # orders/ paths
│   │   ├── OrderRoutingRules.py     # routing-rules/ paths
│   │   ├── OrderFulfillments.py     # fulfillments/ paths
│   │   └── ReturnMerchandiseAuthorizations.py # returns/ paths
│   ├── CustomerProfile/
│   │   ├── CustomerAccountProfiles.py # customer-profiles/ paths
│   │   ├── CustomerAddressPreferences.py # address-preferences/ paths
│   │   ├── CustomerWishlists.py     # wishlists/ paths
│   │   └── CustomerPrivacyRequests.py # privacy-requests/ paths
│   ├── SearchDiscovery/
│   │   ├── SearchSynonyms.py        # discovery/synonyms/ paths
│   │   ├── SearchFacetConfigs.py    # discovery/facets/ paths
│   │   ├── SearchMerchandisingRules.py # discovery/merchandising/ paths
│   │   ├── SearchQueryLogs.py       # discovery/telemetry/ paths
│   │   └── SearchConsole.py         # discovery/search/, autocomplete, analytics paths
│   ├── Personalization/
│   │   ├── AudienceSegments.py      # personalization/segments/ paths
│   │   ├── RecommendationStrategies.py # personalization/strategies/ paths
│   │   ├── PersonalizedExperiences.py # personalization/experiences/ paths
│   │   ├── ShopperBehaviorEvents.py # personalization/telemetry/ paths
│   │   └── PersonalizationConsole.py # personalization/console/ paths
│   ├── MarketingCampaign/
│   │   ├── MarketingDashboards.py   # marketing/dashboard/, feed/ paths
│   │   ├── MarketingCampaigns.py    # marketing/campaigns/ paths
│   │   ├── AffiliatePartners.py     # marketing/affiliates/ paths
│   │   ├── AffiliateReferralConversions.py # marketing/conversions/ paths
│   │   └── SeoMetadataRules.py      # marketing/seo-rules/ paths
│   ├── Marketplace/
│   │   ├── MarketplaceConsole.py    # marketplace/console/ path
│   │   ├── MarketplaceVendors.py    # marketplace/vendors/ paths
│   │   ├── VendorProductListings.py # marketplace/listings/ paths
│   │   ├── VendorSubOrders.py       # marketplace/sub-orders/ paths
│   │   └── VendorPayouts.py         # marketplace/payouts/ paths
│   ├── ContentManagement/
│   │   ├── CmsPages.py              # cms/pages/ paths
│   │   ├── BlogArticles.py          # cms/blog/ paths
│   │   ├── MediaAssets.py           # cms/media/ paths
│   │   └── ContentBlocks.py         # cms/blocks/ paths
│   ├── AnalyticsBi/
│   │   ├── DailySalesSnapshots.py   # analytics/snapshots/ paths
│   │   ├── CustomerCohortMetrics.py # analytics/cohorts/ paths
│   │   ├── ProductMerchandisingMetrics.py # analytics/merchandising/ paths
│   │   ├── AttributionTouchpoints.py # analytics/attribution/ paths
│   │   └── AnalyticsCockpit.py      # analytics/cockpit/ path
│   ├── MobileCommerce/
│   │   ├── MobileHub.py             # mobile/hub/ path
│   │   ├── MobileAppConfigs.py      # mobile/configs/ paths & mobile/manifest.json
│   │   ├── MobileDeviceRegistrations.py # mobile/devices/ paths & ping action
│   │   ├── MobilePushCampaigns.py   # mobile/push-campaigns/ paths & test-send
│   │   └── MobileLocationRules.py   # mobile/location-rules/ paths & simulate
│   ├── B2bWholesale/
│   │   ├── B2bWholesaleHub.py       # b2b/hub/ console path
│   │   ├── B2bCompanyAccounts.py    # b2b/companies/ paths & punchout-test
│   │   ├── B2bCompanyUsers.py       # b2b/users/ paths
│   │   ├── B2bQuoteRequests.py      # b2b/quotes/ paths & action endpoints
│   │   └── B2bQuickOrderTemplates.py # b2b/templates/ & b2b/quick-order/ paths
│   ├── FraudRisk/
│   │   ├── FraudRules.py            # fraud-risk/hub/ & rules/ paths
│   │   ├── TransactionRiskAssessments.py # fraud-risk/assessments/ paths
│   │   ├── ChargebackDisputes.py    # fraud-risk/disputes/ paths
│   │   └── AccountSecurityAlerts.py # fraud-risk/alerts/ paths
│   └── __init__.py                  # Concatenates all urlpatterns with app_name="ecommerce"
├── admin.py                         # Django admin registrations
├── apps.py                          # EcommerceConfig
└── management/commands/
    └── seed_ecommerce.py            # Idempotent demo data seeder
```

---

## 2. Models & Entities

### Sub-module 9.1: Product Catalog Management
| Model | Prefix | Key Fields | Core / External FKs | Key Methods / Properties |
|---|---|---|---|---|
| `StoreCategory` | `ECAT-` | `name`, `slug`, `parent`, `display_order`, `is_active`, `include_in_menu` | `self` (hierarchical) | `full_path`, `get_breadcrumbs()` (cycle-safe) |
| `CatalogProduct` | `EPRD-` | `name`, `slug`, `status` (draft/active/archived), `visibility` (storefront/hidden/search_only), `brand`, `pim_completeness` | `primary_category`, `categories` (M2M), `scm.Item` | `calculate_pim_completeness()`, `price_range_display`, `active_variants` |
| `ProductVariant` | `PVR-` | `sku`, `name`, `option_values` (JSON), `price`, `compare_at_price`, `cost_price`, `is_active`, `weight_kg` | `product`, `scm.Item` | `is_on_sale`, `options_summary`, `margin_pct` |
| `ProductRelationship`| `PRL-` | `relationship_type` (cross_sell, up_sell, accessory, bundle_kit, bought_together), `discount_pct`, `is_active` | `source_product`, `target_product` | Unique per `(tenant, source, target, type)` |

### Sub-module 9.2: Inventory & Stock Management
| Model | Prefix | Key Fields | Core / External FKs | Key Methods / Properties |
|---|---|---|---|---|
| `FulfillmentCenter` | `EFC-` | `name`, `code`, `center_type`, `priority`, `is_active`, `supports_pick_pack_ship`, `supports_customer_pickup`, `daily_cutoff_time`, address fields | `scm.Location` | Unique per `(tenant, code)`. Priority routing order. |
| `InventoryAllocation` | `EAL-` | `quantity_on_hand`, `quantity_allocated`, `safety_stock_buffer`, `low_stock_threshold`, `zone_bin`, `last_counted_at` | `product`, `variant`, `fulfillment_center` | `available_to_promise` (`max(0, on_hand - allocated - safety_buffer)`), `is_low_stock_alert` |
| `BackorderPolicy` | `EBK-` | `policy_type` (deny_when_empty, allow_backorder_with_notice, pre_order_only), `storefront_message`, `expected_availability_date`, `max_backorder_quantity`, `current_backorder_count`, `auto_notify_waitlist` | `variant` (OneToOne) | Unique per `(tenant, variant)` |
| `ChannelInventorySync`| `ESYN-`| `channel_type`, `channel_name`, `sync_mode`, `allocation_buffer_pct`, `last_synced_quantity`, `sync_status`, `last_synced_at` | `variant`, `fulfillment_center` (optional) | `calculate_sync_quantity()` (applies buffer percentage to ATP) |

### Sub-module 9.3: Pricing & Promotion Engine
| Model | Prefix | Key Fields | Core / External FKs | Key Methods / Properties |
|---|---|---|---|---|
| `DynamicPriceRule` | `EDPR-` | `name`, `rule_type`, `adjustment_value`, `scope`, `customer_segment`, `loyalty_tier`, `min_quantity`, `priority`, `is_active` | `category`, `product`, `variant` | `calculate_price(base_price)`, `is_currently_valid` |
| `CouponPromotion` | `ECPN-` | `code`, `name`, `discount_type`, `discount_value`, `min_spend`, `max_discount_amount`, `usage_limit_total`, `is_active` | `customer` (`core.Party`) | `calculate_discount(cart_subtotal)`, `is_currently_valid`, `remaining_redemptions` |
| `FlashSale` | `EFLS-` | `title`, `status`, `discount_percentage`, `flash_price`, `inventory_cap`, `units_sold`, `max_units_per_order`, `start_time`, `end_time` | `product`, `variant`, `category` | `calculate_effective_price(original_price)`, `is_live`, `remaining_units`, `sold_percentage` |
| `CompetitorPriceMonitor` | `ECPM-` | `competitor_name`, `competitor_url`, `competitor_price`, `match_strategy`, `beat_by_value`, `min_margin_pct`, `floor_price`, `status` | `product`, `variant` | `margin_floor_price`, `suggested_price`, `is_margin_risk` |

### Sub-module 9.4: Shopping Cart & Checkout
| Model | Prefix | Key Fields | Core / External FKs | Key Methods / Properties |
|---|---|---|---|---|
| `Cart` | `ECRT-` | `customer`, `session_key`, `email`, `status`, `currency`, `subtotal`, `discount_total`, `tax_total`, `shipping_total`, `grand_total`, `coupon_code`, `recovery_token` | `core.Party` (`customer`) | `recalculate_totals()`, `generate_recovery_token()`, `mark_abandoned()`, `item_count` |
| `CartItem` | — | `cart`, `product`, `variant`, `quantity`, `unit_price`, `total_price`, `custom_attributes` | `ecommerce.CatalogProduct`, `ecommerce.ProductVariant` | Auto calculates `total_price = unit_price * quantity` |
| `CheckoutSession` | `ECKS-` | `cart`, `customer`, `email`, `phone`, `flow_type`, `current_step`, `status`, shipping fields, billing fields, financial totals, `payment_status`, `expires_at`, `completed_at` | `Cart`, `core.Party`, `ShippingMethodConfig`, `PaymentMethodConfig`, `accounting.TaxCode` | `advance_step()` (funnel progression), auto fills billing address |
| `ShippingMethodConfig` | `ESHP-` | `name`, `code`, `carrier`, `calculation_type`, `base_rate`, `cost_per_kg`, `free_shipping_threshold`, `destination_countries`, `is_active`, `sort_order` | — | `calculate_rate(subtotal, total_weight_kg)` (flat, weight tiered, free threshold, pickup) |
| `PaymentMethodConfig` | `EPMC-` | `name`, `provider`, `method_category`, `environment`, `is_active`, `display_order`, `fee_type`, `fee_amount`, `min_order_amount`, `max_order_amount`, `supported_currencies` | — | `calculate_surcharge(subtotal)`, `is_eligible_for_amount(subtotal)` |

### Sub-module 9.5: Order Management System (OMS)
| Model | Prefix | Key Fields | Core / External FKs | Key Methods / Properties |
|---|---|---|---|---|
| `EcommerceOrder` | `EORD-` | `customer`, `guest_email`, `currency`, `status`, `payment_status`, `fulfillment_status`, `fraud_risk_level`, `fraud_score`, `subtotal_amount`, `discount_amount`, `shipping_amount`, `tax_amount`, `total_amount`, `applied_coupon`, shipping/billing addresses | `core.Party` (`customer`), `accounting.Currency`, `CouponPromotion`, `core.Address` | `recalculate_totals()`, `can_cancel()`, `cancel_order(reason)` |
| `EcommerceOrderLine` | — | `order`, `product`, `variant`, `sku`, `product_name`, `quantity`, `fulfilled_quantity`, `returned_quantity`, `unit_price`, `unit_discount`, `line_total`, `status` | `ecommerce.CatalogProduct`, `ecommerce.ProductVariant` | Computes `line_total = (quantity * unit_price) - (quantity * unit_discount)` |
| `OrderRoutingRule` | `EORT-` | `name`, `strategy` (closest_location, fewest_splits, highest_inventory, drop_ship_preferred, manual), `priority`, `destination_country`, `destination_region`, `preferred_fulfillment_center`, `allow_split_shipment`, `enable_dropship`, `is_active` | `ecommerce.FulfillmentCenter` | Evaluates closest fulfillment nodes and split shipment allowance |
| `OrderFulfillment` | `EFUL-` | `order`, `fulfillment_center`, `carrier_name`, `tracking_number`, `tracking_url`, `status`, `shipping_cost`, `shipped_at`, `estimated_delivery_date`, `actual_delivery_date`, `shipping_label_url`, `notification_sent` | `ecommerce.FulfillmentCenter` | `mark_shipped()`, `mark_delivered()`, auto-syncs parent order fulfillment status |
| `ReturnMerchandiseAuthorization` | `ERMA-` | `order`, `customer`, `return_type` (refund, exchange, store_credit), `status`, `reason`, `restocking_fee`, `refund_amount`, `refund_status`, `restocking_status`, `restocking_center` | `core.Party` (`customer`), `ecommerce.FulfillmentCenter` | `authorize()`, `complete_settlement()`, validates restocking fee <= refund amount |

### Sub-module 9.6: Customer Account & Profile
| Model | Prefix | Key Fields | Core / External FKs | Key Methods / Properties |
|---|---|---|---|---|
| `CustomerAccountProfile` | `ECAP-` | `customer`, `user`, `tier`, `status`, `auth_mode`, `phone_number`, `phone_verified`, `preferred_currency`, `preferred_language`, `email_marketing_opt_in`, `sms_marketing_opt_in`, `notification_frequency`, `marketing_consent_at`, `unsubscribe_token`, `total_spent`, `order_count`, `last_order_at`, `internal_notes` | `core.Party` (`customer`), `settings.AUTH_USER_MODEL`, `accounting.Currency` | Unique per `(tenant, customer)`, auto-generates `unsubscribe_token` and captures consent timestamp |
| `CustomerAddressPreference` | `ECAD-` | `customer`, `address`, `label`, `is_default_shipping`, `is_default_billing`, `recipient_name`, `contact_phone`, `delivery_instructions`, `preferred_delivery_window`, `requires_signature` | `core.Party` (`customer`), `core.Address` | Manages single default shipping & billing address across customer preferences on save |
| `CustomerWishlist` | `EWSL-` | `customer`, `name`, `slug`, `visibility` (private/shared/public), `is_default`, `share_token`, `notes` | `core.Party` (`customer`) | Auto slug generation, token generation, single default wishlist flag management on save |
| `CustomerWishlistItem` | — | `wishlist`, `product`, `variant`, `desired_quantity`, `priority` (low/medium/high/highest), `comment` | `CustomerWishlist`, `ecommerce.CatalogProduct`, `ecommerce.ProductVariant` | TenantOwned, priority ranking, variant-product relationship validation |
| `CustomerPrivacyRequest` | `ECPR-` | `customer`, `request_type` (access_export, rectification, erasure_anonymize, restriction, opt_out_sale), `status`, `statutory_deadline`, `completed_at`, `requested_by_email`, `verification_method`, `data_export_payload`, `resolution_notes` | `core.Party` (`customer`) | Defaults 30-day statutory deadline, auto-stamps `completed_at`, triggers automated JSON export & account anonymization |

### Sub-module 9.7: Search & Product Discovery
| Model | Prefix | Key Fields | Core / External FKs | Key Methods / Properties |
|---|---|---|---|---|
| `SearchSynonym` | `ESYM-` | `name`, `synonym_type` (two_way, one_way, replacement), `root_term`, `synonyms`, `is_active`, `hit_count`, `notes` | — | `get_synonym_list()`, normalization & validation in `clean()` |
| `SearchFacetConfig` | `ESFC-` | `name`, `code`, `source_type` (category, brand, price, variant_option, availability, rating, tag), `option_key`, `widget_type` (checkbox, color_swatch, price_slider, rating_stars, toggle, dropdown), `filter_logic` (disjunctive, conjunctive), `display_order`, `is_collapsed_by_default`, `max_values_shown`, `is_searchable`, `category_scope`, `is_active` | `ecommerce.StoreCategory` (`category_scope`) | Unique per `(tenant, code, category_scope)`, automatic slugification of machine code, cross-tenant FK protection |
| `SearchMerchandisingRule` | `ESMR-` | `name`, `rule_type` (query, category, global), `trigger_query`, `match_type` (exact, contains, starts_with), `target_category`, `action_type` (boost, bury, pin, block, redirect, banner), `boosted_product`, `boost_weight`, `pin_position`, `redirect_url`, `banner_title`, `banner_body`, `banner_image_url`, `banner_link_url`, `priority`, `start_date`, `end_date`, `is_active` | `ecommerce.StoreCategory` (`target_category`), `ecommerce.CatalogProduct` (`boosted_product`) | URL scheme sanitization, protocol-relative check, schedule boundary enforcement, cross-tenant validation |
| `SearchQueryLog` | `ESQL-` | `query_text`, `normalized_query`, `results_count`, `is_zero_result`, `execution_time_ms`, `applied_filters`, `sort_order`, `redirected_to`, `clicked_product`, `click_position`, `session_key`, `customer`, `ip_address` | `ecommerce.CatalogProduct` (`clicked_product`), `core.Party` (`customer`) | Search telemetry, zero-result grouping, latency tracking, tenant-scoped customer attribution |




---

### Sub-module 9.8: Personalization & Recommendation Engine
| Model | Prefix | Key Fields | Core / External FKs | Key Methods / Properties |
|---|---|---|---|---|
| `AudienceSegment` | `ESEG-` | `name`, `code`, `lifecycle_stage`, `recency_days_max`, `min_order_count`, `min_lifetime_spend`, `cached_member_count`, `last_evaluated_at`, `is_active` | `StoreCategory` (`target_category`) | Auto-slugifies code, validates non-negative spend, tenant FK assertion in `clean()` |
| `RecommendationStrategy` | `EREC-` | `name`, `code`, `algorithm`, `placement`, `fallback_strategy`, `max_items`, `min_rating`, `same_brand_only`, `only_in_stock`, `is_active` | `AudienceSegment` (`target_segment`), `StoreCategory` (`target_category`) | Bound validation (max_items 1-50, rating 0-5), multi-tenant FK assertion in `clean()` |
| `PersonalizedExperience` | `EPEX-` | `name`, `experience_type`, `headline`, `subheadline`, `cta_label`, `cta_url`, `hero_image_url`, `trigger_delay_hours`, `priority`, `start_date`, `end_date`, `is_active`, metrics | `AudienceSegment` (`target_segment`), `StoreCategory` (`target_category`), `CatalogProduct` (`target_product`) | Safe URL scheme validation (rejects `javascript:`, `data:`, `vbscript:`), date boundary enforcement, multi-tenant FK assertion |
| `ShopperBehaviorEvent` | `ESBE-` | `event_type`, `session_key`, `intent_score_delta`, `referrer_url`, `ip_address`, `user_agent`, `payload_json` | `CustomerAccountProfile` (`customer_profile`), `core.Party` (`party`), `auth.User` (`user`), `CatalogProduct` (`product`), `StoreCategory` (`category`) | Behavioral clickstream telemetry stream for collaborative filtering & intent tracking |

---

### Sub-module 9.9: Content Management System (CMS)
| Model | Prefix | Key Fields | Core / External FKs | Key Methods / Properties |
|---|---|---|---|---|
| `CmsPage` | `EPAG-` | `title`, `slug`, `page_type`, `status`, `template_layout`, `meta_title`, `meta_description`, `canonical_url`, `is_indexable`, `content_json`, `raw_html_body`, `published_at`, `view_count`, `is_ab_test_active`, `ab_variant_label`, `ab_traffic_percentage` | None | Unique slug per tenant, HTML script injection protection, A/B variant traffic split (0-100), full layout choices |
| `BlogArticle` | `EBLG-` | `title`, `slug`, `author`, `category`, `excerpt`, `body_markdown`, `featured_media`, `status`, `published_at`, `view_count`, `reading_time_minutes`, `allow_comments`, `is_featured`, `tags` | `auth.User` (`author`), `MediaAsset` (`featured_media`) | Auto-slug generation, automatic published_at setting, comma-separated `tag_list` property, tenant FK isolation |
| `MediaAsset` | `EMED-` | `title`, `folder`, `media_type`, `file_url`, `alt_text`, `caption`, `mime_type`, `file_size_bytes`, `width_px`, `height_px`, `uploaded_by` | `auth.User` (`uploaded_by`) | HTTPS URL validation, file size & dimension metadata, central DAM categorization |
| `ContentBlock` | `EBLK-` | `name`, `block_type`, `headline`, `subheadline`, `body_text`, `media_asset`, `target_category`, `target_product`, `cta_label`, `cta_url`, `bg_color_class`, `text_color_class`, `custom_css_classes`, `sort_order`, `is_active` | `MediaAsset` (`media_asset`), `StoreCategory` (`target_category`), `CatalogProduct` (`target_product`) | Safe CTA link validation, modular hero/carousel/CTA/testimonial components, tenant FK isolation |

---

### Sub-module 9.10: Marketing & Campaign Management
| Model | Prefix | Key Fields | Core / External FKs | Key Methods / Properties |
|---|---|---|---|---|
| `MarketingCampaign` | `EMCP-` | `name`, `code`, `campaign_type`, `channel`, `status`, `subject`, `preview_text`, `content_body`, `sender_name`, `sender_address`, `scheduled_at`, `sent_at`, `send_throttle_window_hours`, `recipient_count`, `delivered_count`, `opened_count`, `clicked_count`, `bounced_count`, `revenue_attributed` | `AudienceSegment` (`target_segment`), `CatalogProduct` (`target_product`) | `open_rate`, `click_rate`, SMS length clean validation, Smart Sending throttle |
| `AffiliatePartner` | `EAFF-` | `party`, `customer_profile`, `name`, `partner_type`, `referral_code`, `referral_link_slug`, `commission_type`, `commission_rate`, `cookie_duration_days`, `status`, `payout_threshold`, `payment_email`, `total_orders_referred`, `total_revenue_generated`, `total_commission_earned`, `total_commission_paid` | `core.Party` (`party`), `CustomerAccountProfile` (`customer_profile`) | `unpaid_commission`, `is_eligible_for_payout`, auto-slugifies code, case-normalizes code |
| `AffiliateReferralConversion` | `EARC-` | `affiliate`, `order`, `referred_customer`, `attribution_type`, `order_amount`, `commission_rate_applied`, `commission_amount`, `status`, `payout_reference`, `paid_at`, `notes` | `AffiliatePartner` (`affiliate`), `EcommerceOrder` (`order`), `CustomerAccountProfile` (`referred_customer`) | `clean()` calculates commission amount, auto-inherits affiliate commission rate |
| `SeoMetadataRule` | `ESEO-` | `name`, `rule_type`, `target_category`, `target_product`, `url_path_pattern`, `meta_title_template`, `meta_description_template`, `json_ld_schema_type`, `canonical_url_override`, `og_title`, `og_description`, `og_image_url`, `robots_directive`, `sitemap_included`, `sitemap_priority`, `sitemap_changefreq`, `target_keyword`, `tracked_rank_position`, `rank_tracked_at`, `is_active` | `StoreCategory` (`target_category`), `CatalogProduct` (`target_product`) | `render_title(context)`, `render_description(context)`, sitemap priority range enforcement (0.00-1.00) |

---

### Sub-module 9.11: Marketplace & Multi-Vendor
| Model | Prefix | Key Fields | Core / External FKs | Key Methods / Properties |
|---|---|---|---|---|
| `MarketplaceVendor` | `EMKV-` | `party`, `owner_user`, `store_name`, `slug`, `status`, `kyc_status`, `commission_type`, `commission_rate`, `fixed_fee_per_order`, `payout_method`, `payout_account_identifier`, `min_payout_amount`, `tax_id`, `tax_form_status`, `shipping_lead_time_days`, `return_policy`, `rating_average`, `rating_count`, `is_featured`, `suspension_reason` | `core.Party` (`party`), `auth.User` (`owner_user`) | `update_rating()`, `is_active_seller`, tenant isolation |
| `VendorProductListing` | `EVPL-` | `vendor`, `product`, `variant`, `seller_sku`, `barcode`, `condition`, `condition_notes`, `asking_price`, `compare_at_price`, `cost_price`, `available_quantity`, `low_stock_threshold`, `lead_time_days`, `moderation_status`, `compliance_status`, `moderator_notes`, `rejection_reason`, `reviewed_by`, `is_active` | `MarketplaceVendor`, `CatalogProduct`, `ProductVariant`, `auth.User` (`reviewed_by`) | Cross-record variant/product match validation, non-negative pricing validation |
| `VendorSubOrder` | `EVSO-` | `vendor`, `order`, `payout`, `fulfillment_status`, `sla_status`, `payout_status`, `subtotal_amount`, `shipping_amount`, `commission_rate`, `commission_amount`, `net_vendor_amount`, `carrier_name`, `tracking_number`, `tracking_url`, `promised_dispatch_date`, `dispatched_at`, `delivered_at`, `customer_rating`, `customer_feedback`, `dispute_status`, `dispute_reason` | `MarketplaceVendor`, `EcommerceOrder`, `VendorPayout` | `calculate_financials()`, `evaluate_sla()`, auto-triggers vendor rating recalculation |
| `VendorPayout` | `EVPO-` | `vendor`, `period_start`, `period_end`, `gross_sales_amount`, `commission_deducted`, `fees_deducted`, `refunds_deducted`, `tax_withholding_amount`, `net_payout_amount`, `payout_method`, `payout_status`, `reference_code`, `tax_year`, `is_1099_reported`, `notes` | `MarketplaceVendor`, `auth.User` (`created_by`, `approved_by`) | `calculate_net()`, auto tax year assignment, atomic execution with suborder settlement |

---

### Sub-module 9.14: Customer Service & Support
| Model | Prefix | Key Fields | Core / External FKs | Key Methods / Properties |
|---|---|---|---|---|
| `CustomerSupportTicket` | `ESTK-` | `customer`, `order`, `assigned_agent`, `subject`, `customer_name`, `customer_email`, `customer_phone`, `channel`, `category`, `priority`, `status`, `initial_message`, `resolution_summary`, `internal_notes`, `sla_first_response_due_at`, `sla_resolution_due_at`, `first_responded_at`, `resolved_at`, `is_sla_breached`, `is_bot_handled`, `bot_handoff_reason` | `CustomerAccountProfile`, `EcommerceOrder`, `auth.User` (`assigned_agent`) | Auto-SLA calculation by priority, auto-breach detection, reopen resets `resolved_at`, tenant isolation |
| `KnowledgeBaseArticle` | `EKBA-` | `title`, `slug`, `category`, `summary`, `content`, `status`, `target_audience`, `is_featured`, `view_count`, `helpful_votes`, `unhelpful_votes`, `keywords`, `author` | `auth.User` (`author`) | `helpfulness_ratio`, auto-slug generation, scoped atomic `view_count` increment, heavy content deferral |
| `OrderIssueClaim` | `ECLM-` | `order`, `customer`, `ticket`, `claim_type`, `status`, `claimed_amount`, `approved_amount`, `resolution_action`, `carrier_tracking_number`, `photo_evidence_url`, `customer_notes`, `decision_notes`, `reviewed_by`, `resolved_at` | `EcommerceOrder`, `CustomerAccountProfile`, `CustomerSupportTicket`, `auth.User` (`reviewed_by`) | Non-negative financial bounds, URL scheme validation, resolution timestamping, tenant isolation |
| `CustomerSatisfactionSurvey` | `ECSF-` | `ticket`, `order`, `customer`, `survey_type`, `rating_score`, `sentiment`, `feedback_comment`, `agent_rated`, `follow_up_status`, `follow_up_notes`, `reviewed_by` | `CustomerSupportTicket`, `EcommerceOrder`, `CustomerAccountProfile`, `auth.User` (`agent_rated`, `reviewed_by`) | CSAT (1-5) and NPS (0-10) scoring, auto-sentiment classification (promoter/passive/detractor), negative review closed-loop flagging, manual override protection |

---

### Sub-module 9.15: Analytics & Business Intelligence
| Model | Prefix | Key Fields | Core / External FKs | Key Methods / Properties |
|---|---|---|---|---|
| `DailySalesSnapshot` | `EDSS-` | `snapshot_date`, `currency`, `gross_sales`, `net_sales`, `discounts_total`, `returns_total`, `tax_total`, `shipping_total`, `orders_count`, `units_sold`, `average_order_value`, `new_customers_count`, `returning_customers_count`, `conversion_rate`, `cart_abandonment_rate`, `carts_created_count`, `carts_abandoned_count`, `is_finalized`, `finalized_at` | None | `recalculate_from_orders()`, date validation, unique constraint per tenant+date+currency |
| `CustomerCohortMetric` | `ECCM-` | `cohort_month`, `period_offset_months`, `acquisition_channel_tag`, `initial_cohort_size`, `retained_customers_count`, `retention_rate`, `churn_rate`, `period_gross_revenue`, `cumulative_gross_revenue`, `cumulative_ltv`, `repeat_order_count`, `is_finalized` | None | `calculate_metrics()`, non-negative metrics, unique constraint per tenant+cohort_month+offset+channel |
| `ProductMerchandisingMetric` | `EPMM-` | `product`, `variant`, `metric_date`, `views_count`, `add_to_cart_count`, `cart_to_detail_rate`, `units_sold`, `gross_revenue`, `cost_of_goods`, `gross_margin_amount`, `gross_margin_rate`, `refunds_count`, `return_rate`, `ending_inventory_units`, `inventory_turnover_ratio`, `velocity_tier`, `notes` | `CatalogProduct`, `ProductVariant` | `calculate_merchandising_kpis()`, velocity tier classification (A/B/C/D), unique per tenant+product+variant+date |
| `AttributionTouchpoint` | `EATT-` | `order`, `customer`, `touchpoint_timestamp`, `touchpoint_position`, `channel`, `campaign_name`, `source`, `medium`, `content`, `landing_page`, `referral_url`, `device_category`, `first_touch_weight`, `last_touch_weight`, `linear_weight`, `time_decay_weight`, `position_based_weight`, `attributed_revenue_linear`, `conversion_value` | `EcommerceOrder`, `CustomerAccountProfile` | `normalize_weights()`, non-negative weights and attribution values, sargable timestamp ordering |

---

### Sub-module 9.16: Mobile Commerce
| Model | Prefix | Key Fields | Core / External FKs | Key Methods / Properties |
|---|---|---|---|---|
| `MobileAppConfig` | `EMAC-` | `app_name`, `short_name`, `theme_color`, `background_color`, `start_url`, `display_mode`, `orientation`, `enable_pwa`, `enable_apple_pay`, `apple_merchant_id`, `enable_google_pay`, `google_merchant_id`, `firebase_sender_id`, `is_active` | None | `generate_manifest_dict()`, `generate_manifest_json()`, hex color validation, unique per tenant+short_name and tenant+number |
| `MobileDeviceRegistration` | `EMDR-` | `customer_profile`, `party`, `device_uuid`, `device_platform`, `device_model`, `os_version`, `app_version`, `push_token`, `push_provider`, `push_enabled`, `last_latitude`, `last_longitude`, `last_active_at`, `is_active` | `CustomerAccountProfile`, `core.Party` | `record_activity(lat, lng)`, `reset_badge_count()`, compound indexes `(tenant, -last_active_at)` and `(tenant, is_active, push_enabled)`, unique per tenant+device_uuid |
| `MobilePushCampaign` | `EMPC-` | `campaign_name`, `title`, `body_text`, `notification_image_url`, `deep_link_url`, `campaign_type`, `target_platform`, `target_product`, `target_category`, `target_coupon`, `scheduled_at`, `sent_at`, `status`, `target_audience_count`, `sent_count`, `delivered_count`, `opened_count`, `converted_revenue`, `created_by` | `CatalogProduct`, `StoreCategory`, `CouponPromotion`, `auth.User` (`created_by`) | `dispatch_simulation(device_count)`, `open_rate_pct`, `click_through_rate_pct`, status lifecycle guards (cannot re-dispatch cancelled) |
| `MobileLocationRule` | `EMLR-` | `name`, `store_name`, `rule_type`, `latitude`, `longitude`, `radius_meters`, `trigger_action`, `notification_title`, `notification_message`, `fulfillment_center`, `linked_promotion`, `is_active` | `FulfillmentCenter`, `CouponPromotion` | `distance_to(lat, lng)` (clamped Haversine formula), `is_device_inside(lat, lng)`, boundary and coordinate range validation |

---

### Sub-module 9.17: B2B & Wholesale Commerce
| Model | Prefix | Key Fields | Core / External FKs | Key Methods / Properties |
|---|---|---|---|---|
| `B2bCompanyAccount` | `EBCA-` | `company_party`, `account_name`, `tax_id`, `tier`, `status`, `credit_limit`, `credit_used`, `payment_terms_days`, `preferred_currency`, `custom_discount_pct`, `is_tax_exempt`, `tax_exemption_cert`, `allow_quote_requests`, `notes` | `core.Party` (`company_party`), `accounting.Currency` (`preferred_currency`) | `available_credit` property, `is_credit_exceeded` flag, `clean()` validates non-negative credit and discount bounds, tenant-scoped unique constraints |
| `B2bCompanyUser` | `EBCU-` | `company_account`, `user`, `role`, `approval_threshold_amount`, `monthly_spend_limit`, `monthly_spend_current`, `can_place_orders`, `can_request_quotes`, `is_active` | `B2bCompanyAccount`, `auth.User` | `can_approve(amount)`, `remaining_monthly_budget` property, cross-tenant validation against company account, unique per `(tenant, company_account, user)` |
| `B2bQuoteRequest` | `EBQR-` | `company_account`, `requested_by`, `status`, `assigned_sales_rep`, `valid_until`, `subtotal_amount`, `discount_amount`, `total_amount`, `counter_offer_notes`, `buyer_notes`, `internal_notes`, `converted_order` | `B2bCompanyAccount`, `B2bCompanyUser`, `auth.User` (`assigned_sales_rep`), `EcommerceOrder` (`converted_order`) | `recalculate_totals()`, `convert_to_order()` atomic transaction generating `EcommerceOrder` and updating credit exposure, state transition guards |
| `B2bQuoteItem` | `None` | `quote_request`, `product`, `variant`, `sku`, `product_name`, `requested_quantity`, `target_unit_price`, `offered_unit_price`, `subtotal` | `B2bQuoteRequest`, `CatalogProduct`, `ProductVariant` | Auto-syncs product/variant name & SKU, auto-calculates line subtotal |
| `B2bQuickOrderTemplate` | `EBQT-` | `company_account`, `created_by`, `name`, `description`, `is_shared` | `B2bCompanyAccount`, `B2bCompanyUser` | `add_to_cart(cart)` creates cart items in atomic batch, total item count property |
| `B2bQuickOrderItem` | `None` | `template`, `product`, `variant`, `sku`, `product_name`, `default_quantity` | `B2bQuickOrderTemplate`, `CatalogProduct`, `ProductVariant` | Auto-syncs SKU and product details, positive integer quantity guard |

---

### Sub-module 9.18: Fraud & Risk Management
| Model | Prefix | Key Fields | Core / External FKs | Key Methods / Properties |
|---|---|---|---|---|
| `FraudRule` | `EFRR-` | `name`, `rule_type`, `evaluation_scope`, `risk_score_impact`, `action_to_take`, `is_active`, `execution_priority`, `condition_expression`, `description` | None | Priority-ordered rule evaluations, risk score modifiers, action overrides (`allow`, `review`, `challenge`, `reject`) |
| `TransactionRiskAssessment` | `ETRA-` | `order`, `customer_party`, `user`, `total_amount`, `currency_code`, `risk_score`, `risk_tier`, `recommended_action`, `actual_decision`, `analyst_user`, `reviewed_at`, `avs_result_code`, `cvv_result_code`, `ip_address`, `device_fingerprint_id`, `geolocation_country`, `rule_triggers_json`, `notes` | `EcommerceOrder` (`order`), `core.Party` (`customer_party`), `auth.User` (`user`, `analyst_user`) | Multi-variable telemetry evaluation, composite risk scoring (0–100), composite index `["tenant", "-created_at"]` |
| `ChargebackDispute` | `ECBD-` | `order`, `customer_party`, `gateway_dispute_id`, `dispute_amount`, `currency`, `stage`, `reason_category`, `reason_code`, `evidence_submitted_json`, `due_date`, `representment_submitted_at`, `is_liability_shift`, `resolution_notes` | `EcommerceOrder` (`order`), `core.Party` (`customer_party`), `accounting.Currency` (`currency`) | Statutory card network dispute lifecycle, evidence submission tracking, composite index `["tenant", "-created_at"]` |
| `AccountSecurityAlert` | `EASA-` | `party`, `user`, `alert_type`, `severity`, `status`, `automated_action_taken`, `assigned_investigator`, `resolved_by`, `resolved_at`, `ip_address`, `location_info`, `user_agent`, `incident_details`, `resolution_notes` | `core.Party` (`party`), `auth.User` (`user`, `assigned_investigator`, `resolved_by`) | Automated threat mitigation policies (`mfa_required`, `session_revoked`, `account_locked`), incident timeline, composite index `["tenant", "-created_at"]` |

---

## 3. URLs & Routes

All routes live under `/ecommerce/` with namespace `ecommerce`:

### 9.1 Catalog Routes
| URL Pattern | View Function | URL Name | Description |
|---|---|---|---|
| `overview/` | `catalog_overview` | `catalog_overview` | Merchandising & catalog KPI dashboard |
| `""` | `catalog_overview` | `dashboard` | Alias to overview |
| `categories/` | `storecategory_list` | `storecategory_list` | Category tree list & search |
| `categories/create/` | `storecategory_create` | `storecategory_create` | Create category |
| `categories/<int:pk>/` | `storecategory_detail` | `storecategory_detail` | Category detail with subcategories & products |
| `categories/<int:pk>/edit/`| `storecategory_edit` | `storecategory_edit` | Edit category |
| `categories/<int:pk>/delete/`| `storecategory_delete` | `storecategory_delete` | Delete category (POST only, tenant admin required) |
| `products/` | `catalogproduct_list` | `catalogproduct_list` | Product catalog grid/list with filters |
| `products/create/` | `catalogproduct_create` | `catalogproduct_create` | Create catalog product |
| `products/import/` | `product_import_csv` | `product_import_csv` | Bulk CSV product/variant import |
| `products/export/` | `product_export_csv` | `product_export_csv` | Bulk CSV export |
| `products/<int:pk>/` | `catalogproduct_detail` | `catalogproduct_detail` | Product detail with variants & relationships |
| `products/<int:pk>/edit/` | `catalogproduct_edit` | `catalogproduct_edit` | Edit catalog product |
| `products/<int:pk>/delete/`| `catalogproduct_delete` | `catalogproduct_delete` | Delete product (POST only, tenant admin required) |
| `products/<int:pk>/publish/`| `catalogproduct_publish` | `catalogproduct_publish` | Quick toggle draft/active status (POST only) |
| `variants/` | `productvariant_list` | `productvariant_list` | SKU variants list & filter |
| `variants/create/` | `productvariant_create` | `productvariant_create` | Create variant (supports `?product=<id>`) |
| `variants/<int:pk>/` | `productvariant_detail` | `productvariant_detail` | Variant detail view |
| `variants/<int:pk>/edit/` | `productvariant_edit` | `productvariant_edit` | Edit variant |
| `variants/<int:pk>/delete/`| `productvariant_delete` | `productvariant_delete` | Delete variant (POST only, tenant admin required) |
| `relationships/` | `productrelationship_list` | `productrelationship_list` | Merchandising relationships list |
| `relationships/create/` | `productrelationship_create` | `productrelationship_create` | Create relationship (supports `?source=<id>`) |
| `relationships/<int:pk>/`| `productrelationship_detail`| `productrelationship_detail`| Relationship detail view |
| `relationships/<int:pk>/edit/`| `productrelationship_edit`| `productrelationship_edit`| Edit relationship |
| `relationships/<int:pk>/delete/`| `productrelationship_delete`| `productrelationship_delete`| Delete relationship (POST only, tenant admin required) |

### 9.2 Inventory & Stock Routes
| URL Pattern | View Function | URL Name | Description |
|---|---|---|---|
| `inventory/` | `inventory_operations` | `inventory_operations` | Operations console & stock KPI overview |
| `inventory/centers/` | `fulfillmentcenter_list` | `fulfillmentcenter_list` | Centers list with type & status filters |
| `inventory/centers/create/` | `fulfillmentcenter_create` | `fulfillmentcenter_create` | Add new fulfillment center / 3PL node |
| `inventory/centers/<int:pk>/` | `fulfillmentcenter_detail` | `fulfillmentcenter_detail` | Center detail with stocked SKUs and sync feeds |
| `inventory/centers/<int:pk>/edit/` | `fulfillmentcenter_edit` | `fulfillmentcenter_edit` | Edit fulfillment center |
| `inventory/centers/<int:pk>/delete/`| `fulfillmentcenter_delete` | `fulfillmentcenter_delete` | Delete fulfillment center (POST, tenant admin) |
| `inventory/allocations/` | `inventoryallocation_list` | `inventoryallocation_list` | Stock allocation table with ATP & low stock filters |
| `inventory/allocations/create/` | `inventoryallocation_create` | `inventoryallocation_create` | Create allocation (supports `?center=` & `?variant=`) |
| `inventory/allocations/<int:pk>/` | `inventoryallocation_detail` | `inventoryallocation_detail` | Allocation detail with ATP equation & audit log |
| `inventory/allocations/<int:pk>/edit/` | `inventoryallocation_edit` | `inventoryallocation_edit` | Edit allocation parameters & safety buffers |
| `inventory/allocations/<int:pk>/adjust/` | `inventoryallocation_adjust` | `inventoryallocation_adjust` | Stock adjustment workflow (cycle count, damage, etc.) |
| `inventory/allocations/<int:pk>/delete/`| `inventoryallocation_delete` | `inventoryallocation_delete` | Delete allocation (POST, tenant admin) |
| `inventory/backorders/` | `backorderpolicy_list` | `backorderpolicy_list` | Backorder & pre-order policy list |
| `inventory/backorders/create/` | `backorderpolicy_create` | `backorderpolicy_create` | Configure backorder/pre-order policy |
| `inventory/backorders/<int:pk>/` | `backorderpolicy_detail` | `backorderpolicy_detail` | Policy detail with waitlist commitments |
| `inventory/backorders/<int:pk>/edit/` | `backorderpolicy_edit` | `backorderpolicy_edit` | Edit policy message, caps, and dates |
| `inventory/backorders/<int:pk>/delete/`| `backorderpolicy_delete` | `backorderpolicy_delete` | Delete policy (POST, tenant admin) |
| `inventory/sync/` | `channelinventorysync_list` | `channelinventorysync_list` | Multi-channel sync feeds list |
| `inventory/sync/create/` | `channelinventorysync_create` | `channelinventorysync_create` | Connect new channel inventory feed |
| `inventory/sync/<int:pk>/` | `channelinventorysync_detail` | `channelinventorysync_detail` | Feed detail with broadcast calculations & diagnostics |
| `inventory/sync/<int:pk>/edit/` | `channelinventorysync_edit` | `channelinventorysync_edit` | Edit sync mode, buffers, or status |
| `inventory/sync/<int:pk>/delete/` | `channelinventorysync_delete` | `channelinventorysync_delete` | Delete channel feed (POST, tenant admin) |
| `inventory/sync/<int:pk>/trigger/` | `channelinventorysync_trigger` | `channelinventorysync_trigger` | On-demand instant stock broadcast push (POST) |

### 9.3 Pricing & Promotion Routes
| URL Pattern | View Function | URL Name | Description |
|---|---|---|---|
| `pricing/rules/` | `dynamicpricerule_list` | `dynamicpricerule_list` | Rules list with type, scope, and segment filters |
| `pricing/rules/create/` | `dynamicpricerule_create` | `dynamicpricerule_create` | Create dynamic pricing rule |
| `pricing/rules/<int:pk>/` | `dynamicpricerule_detail` | `dynamicpricerule_detail` | Rule detail view with targeting scope and priority |
| `pricing/rules/<int:pk>/edit/` | `dynamicpricerule_edit` | `dynamicpricerule_edit` | Edit pricing rule parameters |
| `pricing/rules/<int:pk>/delete/` | `dynamicpricerule_delete` | `dynamicpricerule_delete` | Delete rule (POST, tenant admin) |
| `pricing/coupons/` | `couponpromotion_list` | `couponpromotion_list` | Coupons list with type and status filters |
| `pricing/coupons/create/` | `couponpromotion_create` | `couponpromotion_create` | Create coupon voucher code |
| `pricing/coupons/<int:pk>/` | `couponpromotion_detail` | `couponpromotion_detail` | Coupon detail with redemption stats |
| `pricing/coupons/<int:pk>/edit/` | `couponpromotion_edit` | `couponpromotion_edit` | Edit coupon limits, spend threshold, and dates |
| `pricing/coupons/<int:pk>/delete/` | `couponpromotion_delete` | `couponpromotion_delete` | Delete coupon (POST, tenant admin) |
| `pricing/flash-sales/` | `flashsale_list` | `flashsale_list` | Flash sales list with live status indicators |
| `pricing/flash-sales/create/` | `flashsale_create` | `flashsale_create` | Schedule new lightning flash sale |
| `pricing/flash-sales/<int:pk>/` | `flashsale_detail` | `flashsale_detail` | Flash sale detail with live progress bar and countdown |
| `pricing/flash-sales/<int:pk>/edit/` | `flashsale_edit` | `flashsale_edit` | Edit flash sale pricing, cap, or timing |
| `pricing/flash-sales/<int:pk>/delete/` | `flashsale_delete` | `flashsale_delete` | Delete flash sale (POST, tenant admin) |
| `pricing/competitors/` | `competitorpricemonitor_list` | `competitorpricemonitor_list` | Competitor price tracking table with margin flags |
| `pricing/competitors/create/` | `competitorpricemonitor_create` | `competitorpricemonitor_create` | Add competitor listing to monitor |
| `pricing/competitors/<int:pk>/` | `competitorpricemonitor_detail` | `competitorpricemonitor_detail` | Monitor detail with suggested repricing and margin floor |
| `pricing/competitors/<int:pk>/edit/` | `competitorpricemonitor_edit` | `competitorpricemonitor_edit` | Edit match strategy, undercut margins, and floor |
| `pricing/competitors/<int:pk>/delete/` | `competitorpricemonitor_delete` | `competitorpricemonitor_delete` | Delete monitor (POST, tenant admin) |
| `pricing/competitors/<int:pk>/sync/` | `competitorpricemonitor_sync` | `competitorpricemonitor_sync` | Trigger instant competitor price scrape check (POST) |

### 9.4 Shopping Cart & Checkout Routes
| URL Pattern | View Function | URL Name | Description |
|---|---|---|---|
| `cart-checkout/carts/` | `cart_list` | `cart_list` | Shopping carts table with search and status filters |
| `cart-checkout/carts/create/` | `cart_create` | `cart_create` | Manually initiate cart for customer or guest |
| `cart-checkout/carts/<int:pk>/` | `cart_detail` | `cart_detail` | Cart detail with items, customer, totals, and abandonment recovery |
| `cart-checkout/carts/<int:pk>/edit/` | `cart_edit` | `cart_edit` | Edit cart attributes, coupon code, status, and notes |
| `cart-checkout/carts/<int:pk>/delete/` | `cart_delete` | `cart_delete` | Delete cart (POST only, tenant admin) |
| `cart-checkout/carts/<int:pk>/recover/` | `cart_recover` | `cart_recover` | Generate recovery token & trigger recovery email (POST) |
| `cart-checkout/sessions/` | `checkoutsession_list` | `checkoutsession_list` | Checkout sessions table with flow & status filters |
| `cart-checkout/sessions/create/` | `checkoutsession_create` | `checkoutsession_create` | Launch checkout session from existing active cart |
| `cart-checkout/sessions/<int:pk>/` | `checkoutsession_detail` | `checkoutsession_detail` | Checkout session detail: shipping/billing address, tax breakdown, totals |
| `cart-checkout/sessions/<int:pk>/edit/` | `checkoutsession_edit` | `checkoutsession_edit` | Edit checkout session information |
| `cart-checkout/sessions/<int:pk>/delete/` | `checkoutsession_delete` | `checkoutsession_delete` | Delete checkout session (POST only, tenant admin) |
| `cart-checkout/sessions/<int:pk>/advance/` | `checkoutsession_advance` | `checkoutsession_advance` | Advance session to next conversion funnel step (POST) |
| `cart-checkout/shipping-methods/` | `shippingmethodconfig_list` | `shippingmethodconfig_list` | Shipping methods configuration table |
| `cart-checkout/shipping-methods/create/` | `shippingmethodconfig_create` | `shippingmethodconfig_create` | Add shipping method & carrier rate calculation rule |
| `cart-checkout/shipping-methods/<int:pk>/` | `shippingmethodconfig_detail` | `shippingmethodconfig_detail` | Shipping method detail & tier matrix breakdown |
| `cart-checkout/shipping-methods/<int:pk>/edit/` | `shippingmethodconfig_edit` | `shippingmethodconfig_edit` | Edit shipping method rates and destination rules |
| `cart-checkout/shipping-methods/<int:pk>/delete/` | `shippingmethodconfig_delete` | `shippingmethodconfig_delete` | Delete shipping method (POST only, tenant admin) |
| `cart-checkout/shipping-methods/<int:pk>/toggle/` | `shippingmethodconfig_toggle` | `shippingmethodconfig_toggle` | Quick toggle shipping method active status (POST) |
| `cart-checkout/payment-methods/` | `paymentmethodconfig_list` | `paymentmethodconfig_list` | Payment methods & gateway configuration table |
| `cart-checkout/payment-methods/create/` | `paymentmethodconfig_create` | `paymentmethodconfig_create` | Connect payment gateway / payment method rule |
| `cart-checkout/payment-methods/<int:pk>/` | `paymentmethodconfig_detail` | `paymentmethodconfig_detail` | Payment method detail & fee / threshold settings |
| `cart-checkout/payment-methods/<int:pk>/edit/` | `paymentmethodconfig_edit` | `paymentmethodconfig_edit` | Edit payment provider, fee type, or currency settings |
| `cart-checkout/payment-methods/<int:pk>/delete/` | `paymentmethodconfig_delete` | `paymentmethodconfig_delete` | Delete payment method (POST only, tenant admin) |
| `cart-checkout/payment-methods/<int:pk>/toggle/` | `paymentmethodconfig_toggle` | `paymentmethodconfig_toggle` | Quick toggle payment gateway active status (POST) |

### 9.5 Order Management System Routes
| URL Pattern | View Function | URL Name | Description |
|---|---|---|---|
| `orders/` | `ecommerceorder_list` | `ecommerceorder_list` | Omnichannel orders list with status, payment, fulfillment, and fraud filters |
| `orders/create/` | `ecommerceorder_create` | `ecommerceorder_create` | Create new customer order with line items |
| `orders/<int:pk>/` | `ecommerceorder_detail` | `ecommerceorder_detail` | Order detail with lines, fulfillments, return authorizations, and financial summary |
| `orders/<int:pk>/edit/` | `ecommerceorder_edit` | `ecommerceorder_edit` | Edit order details, shipping address, and notes |
| `orders/<int:pk>/delete/` | `ecommerceorder_delete` | `ecommerceorder_delete` | Delete order (POST only, tenant admin) |
| `orders/<int:pk>/cancel/` | `ecommerceorder_cancel` | `ecommerceorder_cancel` | Cancel order & release allocated inventory (POST) |
| `routing-rules/` | `orderroutingrule_list` | `orderroutingrule_list` | Order fulfillment routing rules with strategy filter |
| `routing-rules/create/` | `orderroutingrule_create` | `orderroutingrule_create` | Configure new fulfillment routing rule |
| `routing-rules/<int:pk>/` | `orderroutingrule_detail` | `orderroutingrule_detail` | Routing rule detail view with strategy parameters |
| `routing-rules/<int:pk>/edit/` | `orderroutingrule_edit` | `orderroutingrule_edit` | Edit routing rule priority, strategy, and nodes |
| `routing-rules/<int:pk>/delete/` | `orderroutingrule_delete` | `orderroutingrule_delete` | Delete routing rule (POST only, tenant admin) |
| `fulfillments/` | `orderfulfillment_list` | `orderfulfillment_list` | Order fulfillment packages with carrier and status filters |
| `fulfillments/create/` | `orderfulfillment_create` | `orderfulfillment_create` | Create fulfillment package for order |
| `fulfillments/<int:pk>/` | `orderfulfillment_detail` | `orderfulfillment_detail` | Fulfillment detail with tracking timeline and label links |
| `fulfillments/<int:pk>/edit/` | `orderfulfillment_edit` | `orderfulfillment_edit` | Edit fulfillment package tracking and delivery info |
| `fulfillments/<int:pk>/delete/` | `orderfulfillment_delete` | `orderfulfillment_delete` | Delete fulfillment package (POST only, tenant admin) |
| `fulfillments/<int:pk>/ship/` | `orderfulfillment_ship` | `orderfulfillment_ship` | Mark fulfillment package as shipped with carrier (POST) |
| `returns/` | `returnmerchandiseauthorization_list` | `returnmerchandiseauthorization_list` | Return merchandise authorizations (RMA) with status & type filters |
| `returns/create/` | `returnmerchandiseauthorization_create` | `returnmerchandiseauthorization_create` | Initiate customer return authorization |
| `returns/<int:pk>/` | `returnmerchandiseauthorization_detail` | `returnmerchandiseauthorization_detail` | RMA detail with inspection findings and settlement status |
| `returns/<int:pk>/edit/` | `returnmerchandiseauthorization_edit` | `returnmerchandiseauthorization_edit` | Edit return authorization parameters |
| `returns/<int:pk>/delete/` | `returnmerchandiseauthorization_delete` | `returnmerchandiseauthorization_delete` | Delete return authorization (POST only, tenant admin) |
| `returns/<int:pk>/complete/` | `returnmerchandiseauthorization_complete` | `returnmerchandiseauthorization_complete` | Finalize RMA refund settlement and restock (POST) |

### 9.6 Customer Account & Profile Routes
| URL Pattern | View Function | URL Name | Description |
|---|---|---|---|
| `customer-profiles/` | `customeraccountprofile_list` | `customeraccountprofile_list` | Customer account profiles table with tier, status, auth mode, and search filters |
| `customer-profiles/create/` | `customeraccountprofile_create` | `customeraccountprofile_create` | Create new customer account profile |
| `customer-profiles/<int:pk>/` | `customeraccountprofile_detail` | `customeraccountprofile_detail` | Profile detail with recent orders, address preferences, wishlists, and privacy requests |
| `customer-profiles/<int:pk>/edit/` | `customeraccountprofile_edit` | `customeraccountprofile_edit` | Edit customer account profile information |
| `customer-profiles/<int:pk>/delete/` | `customeraccountprofile_delete` | `customeraccountprofile_delete` | Delete customer account profile (POST only, tenant admin) |
| `address-preferences/` | `customeraddresspreference_list` | `customeraddresspreference_list` | Address preferences table with delivery window filter |
| `address-preferences/create/` | `customeraddresspreference_create` | `customeraddresspreference_create` | Create customer address preference linked to core.Address |
| `address-preferences/<int:pk>/` | `customeraddresspreference_detail` | `customeraddresspreference_detail` | Address preference detail with instructions and delivery window |
| `address-preferences/<int:pk>/edit/` | `customeraddresspreference_edit` | `customeraddresspreference_edit` | Edit address preference attributes |
| `address-preferences/<int:pk>/delete/` | `customeraddresspreference_delete` | `customeraddresspreference_delete` | Delete address preference (POST only, tenant admin) |
| `wishlists/` | `customerwishlist_list` | `customerwishlist_list` | Customer wishlists table with visibility filter |
| `wishlists/create/` | `customerwishlist_create` | `customerwishlist_create` | Create new customer wishlist |
| `wishlists/<int:pk>/` | `customerwishlist_detail` | `customerwishlist_detail` | Wishlist detail with items table, priority indicators, and item quick-add form |
| `wishlists/<int:pk>/edit/` | `customerwishlist_edit` | `customerwishlist_edit` | Edit wishlist name, visibility, and notes |
| `wishlists/<int:pk>/delete/` | `customerwishlist_delete` | `customerwishlist_delete` | Delete wishlist (POST only, tenant admin) |
| `wishlists/<int:pk>/items/add/` | `customerwishlist_item_add` | `customerwishlist_item_add` | Add product/variant item to wishlist (POST, tenant admin) |
| `wishlists/items/<int:item_pk>/delete/` | `customerwishlist_item_delete` | `customerwishlist_item_delete` | Remove item from wishlist (POST, tenant admin) |
| `privacy-requests/` | `customerprivacyrequest_list` | `customerprivacyrequest_list` | Statutory privacy requests table with type and status filters |
| `privacy-requests/create/` | `customerprivacyrequest_create` | `customerprivacyrequest_create` | Log incoming GDPR/CCPA privacy request |
| `privacy-requests/<int:pk>/` | `customerprivacyrequest_detail` | `customerprivacyrequest_detail` | Privacy request detail with timeline, payload viewer, and action buttons |
| `privacy-requests/<int:pk>/edit/` | `customerprivacyrequest_edit` | `customerprivacyrequest_edit` | Edit privacy request metadata |
| `privacy-requests/<int:pk>/delete/` | `customerprivacyrequest_delete` | `customerprivacyrequest_delete` | Delete privacy request (POST only, tenant admin) |
| `privacy-requests/<int:pk>/generate-export/` | `customerprivacyrequest_generate_export` | `customerprivacyrequest_generate_export` | Generate comprehensive JSON data portability export (POST, tenant admin) |
| `privacy-requests/<int:pk>/anonymize/` | `customerprivacyrequest_anonymize` | `customerprivacyrequest_anonymize` | Execute right-to-erasure GDPR anonymization workflow (POST, tenant admin) |

### 9.7 Search & Product Discovery Routes
| URL Pattern | View Function | URL Name | Description |
|---|---|---|---|
| `discovery/synonyms/` | `searchsynonym_list` | `searchsynonym_list` | Synonym mappings table with search & type filter |
| `discovery/synonyms/create/` | `searchsynonym_create` | `searchsynonym_create` | Add new synonym rule (pre-populates `?root=`) |
| `discovery/synonyms/<int:pk>/` | `searchsynonym_detail` | `searchsynonym_detail` | Synonym detail with hit counts & notes |
| `discovery/synonyms/<int:pk>/edit/` | `searchsynonym_edit` | `searchsynonym_edit` | Edit synonym mapping terms |
| `discovery/synonyms/<int:pk>/delete/` | `searchsynonym_delete` | `searchsynonym_delete` | Delete synonym rule (POST only, tenant admin) |
| `discovery/synonyms/<int:pk>/toggle/` | `searchsynonym_toggle` | `searchsynonym_toggle` | Quick toggle active status (POST only, tenant admin) |
| `discovery/facets/` | `searchfacetconfig_list` | `searchfacetconfig_list` | Facet filters table with source type and widget filters |
| `discovery/facets/create/` | `searchfacetconfig_create` | `searchfacetconfig_create` | Configure new storefront facet filter |
| `discovery/facets/<int:pk>/` | `searchfacetconfig_detail` | `searchfacetconfig_detail` | Facet config detail with category scope |
| `discovery/facets/<int:pk>/edit/` | `searchfacetconfig_edit` | `searchfacetconfig_edit` | Edit facet filter display and logic parameters |
| `discovery/facets/<int:pk>/delete/` | `searchfacetconfig_delete` | `searchfacetconfig_delete` | Delete facet config (POST only, tenant admin) |
| `discovery/facets/<int:pk>/toggle/` | `searchfacetconfig_toggle` | `searchfacetconfig_toggle` | Quick toggle active status (POST only, tenant admin) |
| `discovery/merchandising/` | `searchmerchandisingrule_list` | `searchmerchandisingrule_list` | Merchandising rules table with rule & action filters |
| `discovery/merchandising/create/` | `searchmerchandisingrule_create` | `searchmerchandisingrule_create` | Create merchandising rule (boost, pin, banner, redirect) |
| `discovery/merchandising/<int:pk>/` | `searchmerchandisingrule_detail` | `searchmerchandisingrule_detail` | Merchandising rule detail with target product & schedule |
| `discovery/merchandising/<int:pk>/edit/` | `searchmerchandisingrule_edit` | `searchmerchandisingrule_edit` | Edit merchandising rule parameters |
| `discovery/merchandising/<int:pk>/delete/` | `searchmerchandisingrule_delete` | `searchmerchandisingrule_delete` | Delete merchandising rule (POST only, tenant admin) |
| `discovery/merchandising/<int:pk>/toggle/` | `searchmerchandisingrule_toggle` | `searchmerchandisingrule_toggle` | Quick toggle active status (POST only, tenant admin) |
| `discovery/telemetry/` | `searchquerylog_list` | `searchquerylog_list` | Search query logs with zero-result filter |
| `discovery/telemetry/<int:pk>/` | `searchquerylog_detail` | `searchquerylog_detail` | Search query telemetry detail with latency and applied filters |
| `discovery/telemetry/<int:pk>/delete/` | `searchquerylog_delete` | `searchquerylog_delete` | Delete query log entry (POST only, tenant admin) |
| `discovery/search/` | `search_console` | `search_console` | Interactive Search Workbench Console with live facet filters & merchandise preview |
| `discovery/search/autocomplete/` | `search_autocomplete` | `search_autocomplete` | Search-as-you-type instant autocomplete (JSON and HTMX partials) |
| `discovery/analytics/` | `search_analytics` | `search_analytics` | Search discovery analytics: latency, null-result queries, click attribution |


---

### 9.8 Personalization & Recommendation Routes
| URL Pattern | View Function | URL Name | Description |
|---|---|---|---|
| `personalization/segments/` | `audiencesegment_list` | `audiencesegment_list` | Audience cohort segments table with lifecycle filter |
| `personalization/segments/create/` | `audiencesegment_create` | `audiencesegment_create` | Create audience cohort segment |
| `personalization/segments/<int:pk>/` | `audiencesegment_detail` | `audiencesegment_detail` | Cohort detail with member count and attached campaigns |
| `personalization/segments/<int:pk>/edit/` | `audiencesegment_edit` | `audiencesegment_edit` | Edit cohort criteria |
| `personalization/segments/<int:pk>/delete/` | `audiencesegment_delete` | `audiencesegment_delete` | Delete audience segment (POST, tenant admin) |
| `personalization/segments/<int:pk>/toggle/` | `audiencesegment_toggle` | `audiencesegment_toggle` | Quick toggle active status (POST, tenant admin) |
| `personalization/segments/<int:pk>/recalculate/` | `audiencesegment_recalculate` | `audiencesegment_recalculate` | Trigger on-demand cohort RFM evaluation (POST) |
| `personalization/strategies/` | `recommendationstrategy_list` | `recommendationstrategy_list` | Recommendation rules table with algorithm & placement filters |
| `personalization/strategies/create/` | `recommendationstrategy_create` | `recommendationstrategy_create` | Create algorithmic recommendation strategy |
| `personalization/strategies/<int:pk>/` | `recommendationstrategy_detail` | `recommendationstrategy_detail` | Strategy detail with placement parameters |
| `personalization/strategies/<int:pk>/edit/` | `recommendationstrategy_edit` | `recommendationstrategy_edit` | Edit recommendation algorithm parameters |
| `personalization/strategies/<int:pk>/delete/` | `recommendationstrategy_delete` | `recommendationstrategy_delete` | Delete recommendation strategy (POST, tenant admin) |
| `personalization/strategies/<int:pk>/toggle/` | `recommendationstrategy_toggle` | `recommendationstrategy_toggle` | Quick toggle active status (POST, tenant admin) |
| `personalization/experiences/` | `personalizedexperience_list` | `personalizedexperience_list` | Personalized experiences & banners table |
| `personalization/experiences/create/` | `personalizedexperience_create` | `personalizedexperience_create` | Create personalized banner, spotlight, or abandonment trigger |
| `personalization/experiences/<int:pk>/` | `personalizedexperience_detail` | `personalizedexperience_detail` | Experience detail with CTR & conversion metrics |
| `personalization/experiences/<int:pk>/edit/` | `personalizedexperience_edit` | `personalizedexperience_edit` | Edit experience creative & audience targeting |
| `personalization/experiences/<int:pk>/delete/` | `personalizedexperience_delete` | `personalizedexperience_delete` | Delete experience (POST, tenant admin) |
| `personalization/experiences/<int:pk>/toggle/` | `personalizedexperience_toggle` | `personalizedexperience_toggle` | Quick toggle active status (POST, tenant admin) |
| `personalization/telemetry/` | `shopperbehaviorevent_list` | `shopperbehaviorevent_list` | Shopper behavioral telemetry event stream |
| `personalization/telemetry/<int:pk>/` | `shopperbehaviorevent_detail` | `shopperbehaviorevent_detail` | Behavior event payload detail |
| `personalization/telemetry/<int:pk>/delete/` | `shopperbehaviorevent_delete` | `shopperbehaviorevent_delete` | Delete behavior log (POST, tenant admin) |
| `personalization/console/` | `personalization_console` | `personalization_console` | Personalization Workbench Console with live recommendation simulator |
| `personalization/console/simulate/` | `recommendation_simulate` | `recommendation_simulate` | HTMX recommendation algorithm simulator partial endpoint |

---

### 9.9 Content Management System Routes
| URL Pattern | View Function | URL Name | Description |
|---|---|---|---|
| `cms/pages/` | `cmspage_list` | `cmspage_list` | CMS pages table with type, status, and layout filters |
| `cms/pages/create/` | `cmspage_create` | `cmspage_create` | Create new CMS page with layout and SEO meta |
| `cms/pages/<int:pk>/` | `cmspage_detail` | `cmspage_detail` | CMS page detail with HTML preview card, A/B metrics, and SEO score |
| `cms/pages/<int:pk>/edit/` | `cmspage_edit` | `cmspage_edit` | Edit CMS page content and settings |
| `cms/pages/<int:pk>/delete/` | `cmspage_delete` | `cmspage_delete` | Delete CMS page (POST only, tenant admin) |
| `cms/pages/<int:pk>/preview/` | `cmspage_preview` | `cmspage_preview` | Live storefront simulation preview mode |
| `cms/blog/` | `blogarticle_list` | `blogarticle_list` | Blog articles table with category and status filters |
| `cms/blog/create/` | `blogarticle_create` | `blogarticle_create` | Create editorial blog article with markdown body |
| `cms/blog/<int:pk>/` | `blogarticle_detail` | `blogarticle_detail` | Article detail with rendered markdown reader, author card, and tag pills |
| `cms/blog/<int:pk>/edit/` | `blogarticle_edit` | `blogarticle_edit` | Edit editorial blog post |
| `cms/blog/<int:pk>/delete/` | `blogarticle_delete` | `blogarticle_delete` | Delete blog article (POST only, tenant admin) |
| `cms/media/` | `mediaasset_list` | `mediaasset_list` | Media assets gallery grid with folder and media type filters |
| `cms/media/create/` | `mediaasset_create` | `mediaasset_create` | Register digital asset URL and metadata |
| `cms/media/<int:pk>/` | `mediaasset_detail` | `mediaasset_detail` | Asset detail with full preview player/lightbox, dimensions, and copyable URL |
| `cms/media/<int:pk>/edit/` | `mediaasset_edit` | `mediaasset_edit` | Edit media asset details |
| `cms/media/<int:pk>/delete/` | `mediaasset_delete` | `mediaasset_delete` | Delete media asset (POST only, tenant admin) |
| `cms/blocks/` | `contentblock_list` | `contentblock_list` | Modular content blocks table with block type filter |
| `cms/blocks/create/` | `contentblock_create` | `contentblock_create` | Create reusable block (hero, grid, carousel, CTA, etc.) |
| `cms/blocks/<int:pk>/` | `contentblock_detail` | `contentblock_detail` | Block detail with live rendered component preview |
| `cms/blocks/<int:pk>/edit/` | `contentblock_edit` | `contentblock_edit` | Edit reusable content block styling and content |
| `cms/blocks/<int:pk>/delete/` | `contentblock_delete` | `contentblock_delete` | Delete content block (POST only, tenant admin) |

---

### 9.10 Marketing & Campaign Management Routes
| URL Pattern | View Function | URL Name | Description |
|---|---|---|---|
| `marketing/dashboard/` | `marketing_dashboard` | `marketing_dashboard` | Omnichannel marketing KPI dashboard with tabs for overview, campaigns, affiliates, and SEO |
| `marketing/feed/social-commerce/` | `social_commerce_feed` | `social_commerce_feed` | Syndicated product catalog JSON feed for Facebook/Instagram/Google Shopping feeds |
| `marketing/campaigns/` | `marketingcampaign_list` | `marketingcampaign_list` | Campaign broadcast table with channel and status dropdown filters |
| `marketing/campaigns/create/` | `marketingcampaign_create` | `marketingcampaign_create` | Create marketing broadcast/automation campaign |
| `marketing/campaigns/<int:pk>/` | `marketingcampaign_detail` | `marketingcampaign_detail` | Campaign dossier with deliverability and engagement metrics |
| `marketing/campaigns/<int:pk>/edit/` | `marketingcampaign_edit` | `marketingcampaign_edit` | Edit campaign targeting, content, and schedule |
| `marketing/campaigns/<int:pk>/send/` | `marketingcampaign_send` | `marketingcampaign_send` | Dispatch campaign broadcast to audience segment (POST, tenant admin) |
| `marketing/campaigns/<int:pk>/delete/` | `marketingcampaign_delete` | `marketingcampaign_delete` | Delete marketing campaign (POST only, tenant admin) |
| `marketing/affiliates/` | `affiliatepartner_list` | `affiliatepartner_list` | Affiliate partner directory with type and status filters |
| `marketing/affiliates/create/` | `affiliatepartner_create` | `affiliatepartner_create` | Onboard affiliate marketer, influencer, or advocate |
| `marketing/affiliates/<int:pk>/` | `affiliatepartner_detail` | `affiliatepartner_detail` | Affiliate dossier with referral performance and conversion history |
| `marketing/affiliates/<int:pk>/edit/` | `affiliatepartner_edit` | `affiliatepartner_edit` | Edit affiliate rates, cookie duration, and payout threshold |
| `marketing/affiliates/<int:pk>/approve/` | `affiliatepartner_approve` | `affiliatepartner_approve` | Approve affiliate partner for active status (POST, tenant admin) |
| `marketing/affiliates/<int:pk>/delete/` | `affiliatepartner_delete` | `affiliatepartner_delete` | Delete affiliate partner (POST only, tenant admin) |
| `marketing/conversions/` | `affiliatereferralconversion_list` | `affiliatereferralconversion_list` | Referral conversion audit table with status & attribution filters |
| `marketing/conversions/create/` | `affiliatereferralconversion_create` | `affiliatereferralconversion_create` | Log referral conversion against customer order |
| `marketing/conversions/<int:pk>/` | `affiliatereferralconversion_detail` | `affiliatereferralconversion_detail` | Conversion record detail with commission breakdown |
| `marketing/conversions/<int:pk>/edit/` | `affiliatereferralconversion_edit` | `affiliatereferralconversion_edit` | Edit conversion notes and rate applied |
| `marketing/conversions/<int:pk>/approve/` | `affiliatereferralconversion_approve` | `affiliatereferralconversion_approve` | Approve conversion for payout and credit affiliate total (POST, tenant admin) |
| `marketing/conversions/<int:pk>/void/` | `affiliatereferralconversion_void` | `affiliatereferralconversion_void` | Void refund/clawback conversion and adjust affiliate accumulator (POST, tenant admin) |
| `marketing/conversions/<int:pk>/delete/` | `affiliatereferralconversion_delete` | `affiliatereferralconversion_delete` | Delete referral conversion (POST only, tenant admin) |
| `marketing/seo-rules/` | `seometadatarule_list` | `seometadatarule_list` | SEO metadata rules table with rule type and schema filters |
| `marketing/seo-rules/create/` | `seometadatarule_create` | `seometadatarule_create` | Create dynamic meta template or custom URL override |
| `marketing/seo-rules/<int:pk>/` | `seometadatarule_detail` | `seometadatarule_detail` | SEO rule preview with live Google SERP snippet and JSON-LD schema visualizer |
| `marketing/seo-rules/<int:pk>/edit/` | `seometadatarule_edit` | `seometadatarule_edit` | Edit SEO template tokens, OpenGraph tags, and sitemap settings |
| `marketing/seo-rules/<int:pk>/toggle/` | `seometadatarule_toggle` | `seometadatarule_toggle` | Quick toggle rule active status (POST only, tenant admin) |
| `marketing/seo-rules/<int:pk>/delete/` | `seometadatarule_delete` | `seometadatarule_delete` | Delete SEO metadata rule (POST only, tenant admin) |

---

### 9.11 Marketplace Routes
| URL Pattern | View Function | URL Name | Description |
|---|---|---|---|
| `marketplace/console/` | `marketplace_console` | `marketplace_console` | Multi-vendor operational console & KPI queue |
| `marketplace/vendors/` | `marketplacevendor_list` | `marketplacevendor_list` | Vendor seller directory & filter table |
| `marketplace/vendors/create/` | `marketplacevendor_create` | `marketplacevendor_create` | Register new marketplace seller |
| `marketplace/vendors/<int:pk>/` | `marketplacevendor_detail` | `marketplacevendor_detail` | Vendor dossier & related listings/orders/payouts |
| `marketplace/vendors/<int:pk>/edit/` | `marketplacevendor_edit` | `marketplacevendor_edit` | Edit vendor commissions, terms & settings |
| `marketplace/vendors/<int:pk>/delete/` | `marketplacevendor_delete` | `marketplacevendor_delete` | Terminate & remove vendor account |
| `marketplace/vendors/<int:pk>/verify-kyc/` | `marketplacevendor_verify_kyc` | `marketplacevendor_verify_kyc` | KYC compliance verification approval action |
| `marketplace/vendors/<int:pk>/suspend/` | `marketplacevendor_suspend` | `marketplacevendor_suspend` | Suspend vendor account with reason |
| `marketplace/listings/` | `vendorproductlisting_list` | `vendorproductlisting_list` | Multi-vendor catalog listings & moderation filter |
| `marketplace/listings/create/` | `vendorproductlisting_create` | `vendorproductlisting_create` | Create seller product listing |
| `marketplace/listings/<int:pk>/` | `vendorproductlisting_detail` | `vendorproductlisting_detail` | Listing detail & compliance view |
| `marketplace/listings/<int:pk>/edit/` | `vendorproductlisting_edit` | `vendorproductlisting_edit` | Edit pricing, stock & condition |
| `marketplace/listings/<int:pk>/delete/` | `vendorproductlisting_delete` | `vendorproductlisting_delete` | Delete seller listing |
| `marketplace/listings/<int:pk>/moderate/` | `vendorproductlisting_moderate` | `vendorproductlisting_moderate` | Approve, reject, or request changes on listing |
| `marketplace/sub-orders/` | `vendorsuborder_list` | `vendorsuborder_list` | Consignment sub-orders fulfillment & SLA table |
| `marketplace/sub-orders/create/` | `vendorsuborder_create` | `vendorsuborder_create` | Manual consignment sub-order creation |
| `marketplace/sub-orders/<int:pk>/` | `vendorsuborder_detail` | `vendorsuborder_detail` | Sub-order consignment detail & order lines |
| `marketplace/sub-orders/<int:pk>/edit/` | `vendorsuborder_edit` | `vendorsuborder_edit` | Update sub-order details |
| `marketplace/sub-orders/<int:pk>/delete/` | `vendorsuborder_delete` | `vendorsuborder_delete` | Delete consignment sub-order |
| `marketplace/sub-orders/<int:pk>/fulfill/` | `vendorsuborder_fulfill` | `vendorsuborder_fulfill` | Update tracking & mark dispatched |
| `marketplace/sub-orders/<int:pk>/dispute/` | `vendorsuborder_dispute` | `vendorsuborder_dispute` | Record buyer dispute & withhold settlement |
| `marketplace/payouts/` | `vendorpayout_list` | `vendorpayout_list` | Disbursement payout batches table |
| `marketplace/payouts/create/` | `vendorpayout_create` | `vendorpayout_create` | Create new payout batch settlement |
| `marketplace/payouts/<int:pk>/` | `vendorpayout_detail` | `vendorpayout_detail` | Payout breakdown & settled sub-orders |
| `marketplace/payouts/<int:pk>/edit/` | `vendorpayout_edit` | `vendorpayout_edit` | Edit payout deductions & details |
| `marketplace/payouts/<int:pk>/delete/` | `vendorpayout_delete` | `vendorpayout_delete` | Delete draft payout batch & reset sub-orders |
| `marketplace/payouts/<int:pk>/execute/` | `vendorpayout_execute` | `vendorpayout_execute` | Execute disbursement & mark sub-orders paid |

---

### 9.14 Customer Service & Support Routes
| URL Pattern | View Function | URL Name | Description |
|---|---|---|---|
| `support/tickets/` | `customersupportticket_list` | `customersupportticket_list` | Omnichannel ticket list with channel, category, priority, status filters & search |
| `support/tickets/create/` | `customersupportticket_create` | `customersupportticket_create` | Log support ticket from customer inquiry or phone call |
| `support/tickets/<int:pk>/` | `customersupportticket_detail` | `customersupportticket_detail` | Ticket timeline dossier with shopper profile, linked order total, and internal notes |
| `support/tickets/<int:pk>/edit/` | `customersupportticket_edit` | `customersupportticket_edit` | Update ticket status, assigned agent, SLA, or resolution notes |
| `support/tickets/<int:pk>/delete/` | `customersupportticket_delete` | `customersupportticket_delete` | Delete ticket (POST only, tenant admin required) |
| `support/articles/` | `knowledgebasearticle_list` | `knowledgebasearticle_list` | Knowledge base article repository with category, status, audience filters |
| `support/articles/create/` | `knowledgebasearticle_create` | `knowledgebasearticle_create` | Author help documentation / FAQ article |
| `support/articles/<int:pk>/` | `knowledgebasearticle_detail` | `knowledgebasearticle_detail` | Article reader with rendered markdown body and view counter |
| `support/articles/<int:pk>/edit/` | `knowledgebasearticle_edit` | `knowledgebasearticle_edit` | Edit article content, audience targeting, or publishing state |
| `support/articles/<int:pk>/delete/` | `knowledgebasearticle_delete` | `knowledgebasearticle_delete` | Delete KB article (POST only, tenant admin required) |
| `support/claims/` | `orderissueclaim_list` | `orderissueclaim_list` | Order issue & transit claims register with claim type and resolution filters |
| `support/claims/create/` | `orderissueclaim_create` | `orderissueclaim_create` | Submit damage / lost package dispute claim against an order |
| `support/claims/<int:pk>/` | `orderissueclaim_detail` | `orderissueclaim_detail` | Claim adjudication dossier with photo evidence preview, claimed amount, and order total |
| `support/claims/<int:pk>/edit/` | `orderissueclaim_edit` | `orderissueclaim_edit` | Adjudicate claim, approve amount, set resolution action |
| `support/claims/<int:pk>/delete/` | `orderissueclaim_delete` | `orderissueclaim_delete` | Delete claim record (POST only, tenant admin required) |
| `support/surveys/` | `customersatisfactionsurvey_list` | `customersatisfactionsurvey_list` | CSAT and NPS feedback list with sentiment badges and follow-up status filters |
| `support/surveys/create/` | `customersatisfactionsurvey_create` | `customersatisfactionsurvey_create` | Log customer survey response with score and feedback |
| `support/surveys/<int:pk>/` | `customersatisfactionsurvey_detail` | `customersatisfactionsurvey_detail` | Survey scorecard dossier with sentiment pill, rating display, and supervisor notes |
| `support/surveys/<int:pk>/edit/` | `customersatisfactionsurvey_edit` | `customersatisfactionsurvey_edit` | Update customer recovery follow-up status and supervisor notes |
| `support/surveys/<int:pk>/delete/` | `customersatisfactionsurvey_delete` | `customersatisfactionsurvey_delete` | Delete survey entry (POST only, tenant admin required) |

---

### 9.15 Analytics & Business Intelligence Routes
| URL Pattern | View Function | URL Name | Description |
|---|---|---|---|
| `analytics/cockpit/` | `analytics_cockpit` | `analytics_cockpit` | Real-time executive BI cockpit: revenue, conversion funnel, best sellers, active carts |
| `analytics/snapshots/` | `dailysalessnapshot_list` | `dailysalessnapshot_list` | Daily sales snapshots table with date range and finalized filters |
| `analytics/snapshots/create/` | `dailysalessnapshot_create` | `dailysalessnapshot_create` | Create daily sales snapshot record |
| `analytics/snapshots/<int:pk>/` | `dailysalessnapshot_detail` | `dailysalessnapshot_detail` | Snapshot detail with sales breakdown, conversion rates, and cart abandonment |
| `analytics/snapshots/<int:pk>/edit/` | `dailysalessnapshot_edit` | `dailysalessnapshot_edit` | Edit daily snapshot values and finalized flag |
| `analytics/snapshots/<int:pk>/delete/` | `dailysalessnapshot_delete` | `dailysalessnapshot_delete` | Delete snapshot record (POST only, tenant admin required) |
| `analytics/snapshots/recalculate/` | `dailysalessnapshot_recalculate` | `dailysalessnapshot_recalculate` | On-demand aggregation from orders and carts (POST only, tenant admin) |
| `analytics/cohorts/` | `customercohortmetric_list` | `customercohortmetric_list` | Customer cohort retention matrix with month, offset, and channel filters |
| `analytics/cohorts/create/` | `customercohortmetric_create` | `customercohortmetric_create` | Create cohort retention metric record |
| `analytics/cohorts/<int:pk>/` | `customercohortmetric_detail` | `customercohortmetric_detail` | Cohort detail with retention curves, cumulative revenue, and LTV stats |
| `analytics/cohorts/<int:pk>/edit/` | `customercohortmetric_edit` | `customercohortmetric_edit` | Edit cohort retention values |
| `analytics/cohorts/<int:pk>/delete/` | `customercohortmetric_delete` | `customercohortmetric_delete` | Delete cohort record (POST only, tenant admin required) |
| `analytics/cohorts/recalculate/` | `customercohortmetric_recalculate` | `customercohortmetric_recalculate` | Recompute cohort retention and cumulative LTV (POST only, tenant admin) |
| `analytics/merchandising/` | `productmerchandisingmetric_list` | `productmerchandisingmetric_list` | Merchandising performance table with velocity tier and return rate filters |
| `analytics/merchandising/create/` | `productmerchandisingmetric_create` | `productmerchandisingmetric_create` | Create product merchandising metric record |
| `analytics/merchandising/<int:pk>/` | `productmerchandisingmetric_detail` | `productmerchandisingmetric_detail` | Merchandising detail: gross margin, inventory turnover, velocity scorecards |
| `analytics/merchandising/<int:pk>/edit/` | `productmerchandisingmetric_edit` | `productmerchandisingmetric_edit` | Edit merchandising metrics and velocity tier |
| `analytics/merchandising/<int:pk>/delete/` | `productmerchandisingmetric_delete` | `productmerchandisingmetric_delete` | Delete merchandising record (POST only, tenant admin required) |
| `analytics/merchandising/recalculate/` | `productmerchandisingmetric_recalculate` | `productmerchandisingmetric_recalculate` | Recompute merchandising turnover and margin velocity (POST only, tenant admin) |
| `analytics/attribution/` | `attributiontouchpoint_list` | `attributiontouchpoint_list` | Marketing attribution touchpoints table with channel, campaign, device filters |
| `analytics/attribution/create/` | `attributiontouchpoint_create` | `attributiontouchpoint_create` | Record new marketing touchpoint |
| `analytics/attribution/<int:pk>/` | `attributiontouchpoint_detail` | `attributiontouchpoint_detail` | Touchpoint detail with multi-touch attribution weight scorecard |
| `analytics/attribution/<int:pk>/edit/` | `attributiontouchpoint_edit` | `attributiontouchpoint_edit` | Edit touchpoint channel, weights, or attributed revenue |
| `analytics/attribution/<int:pk>/delete/` | `attributiontouchpoint_delete` | `attributiontouchpoint_delete` | Delete touchpoint record (POST only, tenant admin required) |

---

### 9.16 Mobile Commerce Routes
| URL Pattern | View Function | URL Name | Description |
|---|---|---|---|
| `mobile/hub/` | `mobile_hub` | `mobile_hub` | Mobile Commerce Command Hub console dashboard |
| `mobile/manifest.json` | `pwa_manifest_json` | `pwa_manifest_json` | Public W3C Progressive Web App manifest endpoint |
| `mobile/configs/` | `mobileappconfig_list` | `mobileappconfig_list` | Mobile app configurations table with PWA and wallet filters |
| `mobile/configs/new/` | `mobileappconfig_create` | `mobileappconfig_create` | Create mobile app configuration record |
| `mobile/configs/<int:pk>/` | `mobileappconfig_detail` | `mobileappconfig_detail` | Mobile app config detail with live W3C manifest preview |
| `mobile/configs/<int:pk>/edit/` | `mobileappconfig_edit` | `mobileappconfig_edit` | Edit mobile app configuration and theme colors |
| `mobile/configs/<int:pk>/delete/` | `mobileappconfig_delete` | `mobileappconfig_delete` | Delete app config (POST only, tenant admin required) |
| `mobile/devices/` | `mobiledeviceregistration_list` | `mobiledeviceregistration_list` | Registered mobile devices table with platform and status filters |
| `mobile/devices/new/` | `mobiledeviceregistration_create` | `mobiledeviceregistration_create` | Register new mobile device record |
| `mobile/devices/<int:pk>/` | `mobiledeviceregistration_detail` | `mobiledeviceregistration_detail` | Device detail with telemetry history and push token |
| `mobile/devices/<int:pk>/edit/` | `mobiledeviceregistration_edit` | `mobiledeviceregistration_edit` | Edit device attributes and status |
| `mobile/devices/<int:pk>/delete/` | `mobiledeviceregistration_delete` | `mobiledeviceregistration_delete` | Delete device record (POST only, tenant admin required) |
| `mobile/devices/<int:pk>/ping/` | `mobiledeviceregistration_ping` | `mobiledeviceregistration_ping` | Simulate device telemetry heartbeat ping (POST only, tenant admin) |
| `mobile/push-campaigns/` | `mobilepushcampaign_list` | `mobilepushcampaign_list` | Push campaigns table with platform and status filters |
| `mobile/push-campaigns/new/` | `mobilepushcampaign_create` | `mobilepushcampaign_create` | Create mobile push notification campaign |
| `mobile/push-campaigns/<int:pk>/` | `mobilepushcampaign_detail` | `mobilepushcampaign_detail` | Campaign detail with phone preview and conversion scorecard |
| `mobile/push-campaigns/<int:pk>/edit/` | `mobilepushcampaign_edit` | `mobilepushcampaign_edit` | Edit push notification campaign |
| `mobile/push-campaigns/<int:pk>/delete/` | `mobilepushcampaign_delete` | `mobilepushcampaign_delete` | Delete push campaign (POST only, tenant admin required) |
| `mobile/push-campaigns/<int:pk>/test-send/` | `mobilepushcampaign_test_send` | `mobilepushcampaign_test_send` | Simulate push notification dispatch (POST only, tenant admin) |
| `mobile/location-rules/` | `mobilelocationrule_list` | `mobilelocationrule_list` | Store locator and geofence rules table with trigger action filters |
| `mobile/location-rules/new/` | `mobilelocationrule_create` | `mobilelocationrule_create` | Create store locator and geofence rule |
| `mobile/location-rules//<int:pk>/` | `mobilelocationrule_detail` | `mobilelocationrule_detail` | Location rule detail with circular geofence radar simulator |
| `mobile/location-rules/<int:pk>/edit/` | `mobilelocationrule_edit` | `mobilelocationrule_edit` | Edit location rule and trigger parameters |
| `mobile/location-rules/<int:pk>/delete/` | `mobilelocationrule_delete` | `mobilelocationrule_delete` | Delete location rule (POST only, tenant admin required) |
| `mobile/location-rules/<int:pk>/simulate/` | `mobilelocationrule_simulate` | `mobilelocationrule_simulate` | Test GPS boundary simulation inside/outside geofence (POST only) |

---

### 9.17 B2B & Wholesale Commerce Routes
| URL Pattern | View Function | URL Name | Description |
|---|---|---|---|
| `b2b/hub/` | `b2b_wholesale_hub` | `b2b_wholesale_hub` | Wholesale Command Center console dashboard |
| `b2b/companies/` | `b2bcompanyaccount_list` | `b2bcompanyaccount_list` | B2B Corporate Buyer Accounts directory with tier and status filters |
| `b2b/companies/new/` | `b2bcompanyaccount_create` | `b2bcompanyaccount_create` | Register new B2B corporate company account |
| `b2b/companies/<int:pk>/` | `b2bcompanyaccount_detail` | `b2bcompanyaccount_detail` | Corporate account detail with credit utilization bar, buyer roster, and quote requests |
| `b2b/companies/<int:pk>/edit/` | `b2bcompanyaccount_edit` | `b2bcompanyaccount_edit` | Edit corporate account credit limit, terms, discount, or tax exemption |
| `b2b/companies/<int:pk>/delete/` | `b2bcompanyaccount_delete` | `b2bcompanyaccount_delete` | Delete company account (POST only, tenant admin required) |
| `b2b/companies/<int:pk>/punchout-test/` | `b2bcompanyaccount_punchout_test` | `b2bcompanyaccount_punchout_test` | Test cXML/OCI simulated PunchOut checkout session |
| `b2b/users/` | `b2bcompanyuser_list` | `b2bcompanyuser_list` | Corporate Buyer Users directory with role and status filters |
| `b2b/users/new/` | `b2bcompanyuser_create` | `b2bcompanyuser_create` | Onboard company buyer user with role and spending thresholds |
| `b2b/users/<int:pk>/` | `b2bcompanyuser_detail` | `b2bcompanyuser_detail` | Buyer user detail with monthly spend limit gauge and permissions |
| `b2b/users/<int:pk>/edit/` | `b2bcompanyuser_edit` | `b2bcompanyuser_edit` | Edit company buyer user role, approval limits, and order permissions |
| `b2b/users/<int:pk>/delete/` | `b2bcompanyuser_delete` | `b2bcompanyuser_delete` | Delete buyer user (POST only, tenant admin required) |
| `b2b/quotes/` | `b2bquoterequest_list` | `b2bquoterequest_list` | B2B Quote Requests (RFQ) register with status and account filters |
| `b2b/quotes/new/` | `b2bquoterequest_create` | `b2bquoterequest_create` | Submit custom quotation request with line items |
| `b2b/quotes/<int:pk>/` | `b2bquoterequest_detail` | `b2bquoterequest_detail` | Quote request negotiation dossier with counter-offers and order conversion action |
| `b2b/quotes/<int:pk>/edit/` | `b2bquoterequest_edit` | `b2bquoterequest_edit` | Edit quote line items, target pricing, discount, and buyer notes |
| `b2b/quotes/<int:pk>/delete/` | `b2bquoterequest_delete` | `b2bquoterequest_delete` | Delete quote request (POST only, tenant admin required) |
| `b2b/quotes/<int:pk>/submit/` | `b2bquoterequest_submit` | `b2bquoterequest_submit` | Buyer submits draft quote request for review (POST only) |
| `b2b/quotes/<int:pk>/quote/` | `b2bquoterequest_quote` | `b2bquoterequest_quote` | Sales manager counters with proposed quote discount (POST only) |
| `b2b/quotes/<int:pk>/accept/` | `b2bquoterequest_accept` | `b2bquoterequest_accept` | Buyer accepts proposed wholesale quote terms (POST only) |
| `b2b/quotes/<int:pk>/reject/` | `b2bquoterequest_reject` | `b2bquoterequest_reject` | Reject quote request or counter-offer with reason (POST only) |
| `b2b/quotes/<int:pk>/convert-order/` | `b2bquoterequest_convert_order` | `b2bquoterequest_convert_order` | Convert approved quote to live EcommerceOrder and update credit used (POST only) |
| `b2b/templates/` | `b2bquickordertemplate_list` | `b2bquickordertemplate_list` | Quick Order Requisition Kits directory with visibility filters |
| `b2b/templates/new/` | `b2bquickordertemplate_create` | `b2bquickordertemplate_create` | Create requisition order kit template with SKU items |
| `b2b/templates/<int:pk>/` | `b2bquickordertemplate_detail` | `b2bquickordertemplate_detail` | Requisition kit detail with SKU line items and 1-click cart addition |
| `b2b/templates/<int:pk>/edit/` | `b2bquickordertemplate_edit` | `b2bquickordertemplate_edit` | Edit requisition kit items and sharing permissions |
| `b2b/templates/<int:pk>/delete/` | `b2bquickordertemplate_delete` | `b2bquickordertemplate_delete` | Delete requisition template (POST only, tenant admin required) |
| `b2b/quick-order/` | `b2b_quick_order_matrix` | `b2b_quick_order_matrix` | Rapid bulk SKU matrix entry table and spreadsheet CSV import |

### 9.18 Fraud & Risk Management Routes
| URL Pattern | View Function | URL Name | Description |
|---|---|---|---|
| `fraud-risk/hub/` | `fraud_risk_hub` | `fraud_risk_hub` | Fraud & Risk Management command center hub |
| `fraud-risk/rules/` | `fraud_rule_list` | `fraud_rule_list` | Fraud rules register with scope, type, and action filters |
| `fraud-risk/rules/create/` | `fraud_rule_create` | `fraud_rule_create` | Create new fraud evaluation rule |
| `fraud-risk/rules/<int:pk>/` | `fraud_rule_detail` | `fraud_rule_detail` | Fraud rule detail with priority and trigger conditions |
| `fraud-risk/rules/<int:pk>/edit/` | `fraud_rule_edit` | `fraud_rule_edit` | Edit fraud evaluation rule and active status |
| `fraud-risk/rules/<int:pk>/delete/` | `fraud_rule_delete` | `fraud_rule_delete` | Delete fraud rule (POST only) |
| `fraud-risk/assessments/` | `transaction_risk_assessment_list` | `transaction_risk_assessment_list` | Transaction risk assessments register with tier and decision filters |
| `fraud-risk/assessments/create/` | `transaction_risk_assessment_create` | `transaction_risk_assessment_create` | Record new transaction risk assessment evaluation |
| `fraud-risk/assessments/<int:pk>/` | `transaction_risk_assessment_detail` | `transaction_risk_assessment_detail` | Transaction assessment detail with AVS/CVV signals and geolocation |
| `fraud-risk/assessments/<int:pk>/edit/` | `transaction_risk_assessment_edit` | `transaction_risk_assessment_edit` | Review risk assessment and record analyst decision |
| `fraud-risk/assessments/<int:pk>/delete/` | `transaction_risk_assessment_delete` | `transaction_risk_assessment_delete` | Delete transaction risk assessment (POST only) |
| `fraud-risk/disputes/` | `chargeback_dispute_list` | `chargeback_dispute_list` | Chargeback & inquiry disputes register with stage and reason filters |
| `fraud-risk/disputes/create/` | `chargeback_dispute_create` | `chargeback_dispute_create` | File incoming payment chargeback or retrieval dispute |
| `fraud-risk/disputes/<int:pk>/` | `chargeback_dispute_detail` | `chargeback_dispute_detail` | Dispute case dossier with network reason codes and evidence |
| `fraud-risk/disputes/<int:pk>/edit/` | `chargeback_dispute_edit` | `chargeback_dispute_edit` | Edit dispute stage, representment submission, and outcome |
| `fraud-risk/disputes/<int:pk>/delete/` | `chargeback_dispute_delete` | `chargeback_dispute_delete` | Delete chargeback dispute case (POST only) |
| `fraud-risk/alerts/` | `account_security_alert_list` | `account_security_alert_list` | Account security alerts register with severity and status filters |
| `fraud-risk/alerts/create/` | `account_security_alert_create` | `account_security_alert_create` | Log account security incident or takeover alert |
| `fraud-risk/alerts/<int:pk>/` | `account_security_alert_detail` | `account_security_alert_detail` | Security alert detail with IP telemetry and investigation notes |
| `fraud-risk/alerts/<int:pk>/edit/` | `account_security_alert_edit` | `account_security_alert_edit` | Triage security alert, assign investigator, and update status |
| `fraud-risk/alerts/<int:pk>/delete/` | `account_security_alert_delete` | `account_security_alert_delete` | Delete account security alert (POST only) |

---

## 4. Templates & Design System

Templates are stored under `templates/ecommerce/`:
- `productcatalog/` — Catalog overview, bulk import, storecategory, catalogproduct, productvariant, productrelationship templates.
- `inventorystock/`
  - `overview.html` — Operations console: ATP KPIs, low stock alerts, active fulfillment centers, connected channel syncs, and backorder queue.
  - `fulfillmentcenter/` — `list.html`, `detail.html`, `form.html`.
  - `inventoryallocation/` — `list.html` (with ATP highlights), `detail.html` (with ATP equation breakdown), `form.html`, `adjust.html` (cycle count / damage write-off workflow).
  - `backorderpolicy/` — `list.html`, `detail.html`, `form.html`.
  - `channelinventorysync/` — `list.html`, `detail.html`, `form.html`.
- `pricingpromotion/`
  - `dynamicpricerule/` — `list.html`, `detail.html`, `form.html`.
  - `couponpromotion/` — `list.html`, `detail.html`, `form.html`.
  - `flashsale/` — `list.html` (with active live badges), `detail.html` (with inventory sell-through progress bar), `form.html`.
  - `competitorpricemonitor/` — `list.html` (with margin risk warnings and suggested repricing), `detail.html` (with margin floor breakdown and instant sync button), `form.html`.
- `cartcheckout/`
  - `cart/` — `list.html` (with cart status badges and items count), `detail.html` (with line items table, financial breakdown, recovery URL trigger), `form.html`.
  - `checkoutsession/` — `list.html` (with funnel step indicators, flow types, payment statuses), `detail.html` (with step progress stepper, shipping & billing address panels, tax breakdown, advance step button), `form.html`.
  - `shippingmethod/` — `list.html` (with carrier logos/badges, rate calculation badges, active toggle), `detail.html` (with delivery estimation windows, threshold info), `form.html`.
  - `paymentmethod/` — `list.html` (with payment provider badges, environment pills, active toggle), `detail.html` (with fee structures, currency support lists, instructions), `form.html`.
- `ordermanagement/`
  - `ecommerceorder/` — `list.html` (with order status, payment, fulfillment, and fraud badges), `detail.html` (with order overview, customer card, items table, fulfillments timeline, returns panel, cancellation modal), `form.html`.
  - `orderroutingrule/` — `list.html` (with routing strategy badges and priority pills), `detail.html` (with destination scope and preferred center), `form.html`.
  - `orderfulfillment/` — `list.html` (with carrier badges and tracking links), `detail.html` (with tracking progress, dispatch metadata, and carrier ship action), `form.html`.
  - `returnmerchandiseauthorization/` — `list.html` (with return type badges and refund statuses), `detail.html` (with inspection notes, fee deduction, restocking center, and complete settlement action), `form.html`.
- `customerprofile/`
  - `customeraccountprofile/` — `list.html` (with tier, status, and auth mode badges), `detail.html` (with customer header, loyalty stats, address preferences, wishlists, and privacy requests), `form.html`.
  - `customeraddresspreference/` — `list.html` (with default shipping/billing badges and delivery window pills), `detail.html` (with physical address details and delivery instructions), `form.html`.
  - `customerwishlist/` — `list.html` (with visibility badges and items count), `detail.html` (with items table, priority badges, and quick-add form), `form.html`.
  - `customerprivacyrequest/` — `list.html` (with request type and workflow status badges), `detail.html` (with request timeline, data export action, anonymization modal, and payload viewer), `form.html`.
- `searchdiscovery/`
  - `synonym/` — `list.html` (with synonym type badges and hit count pills), `detail.html` (with root anchor, mapped synonyms tags, and activity stats), `form.html`.
  - `facetconfig/` — `list.html` (with source type and widget badges, active toggles), `detail.html` (with category scope and filter logic breakdown), `form.html`.
  - `merchandisingrule/` — `list.html` (with rule type and action badges, priority indicators), `detail.html` (with target product card, campaign schedule, and action preview), `form.html`.
  - `querylog/` — `list.html` (with zero-result alerts, search latency pills, and sort order tags), `detail.html` (with execution metrics, shopper attribution, and applied filters viewer).
  - `console/` — `console.html` (Search Workbench: live query search, active facet checkboxes, price range slider, merchandising overrides preview, fallback zero-result suggestions), `autocomplete_results.html` (HTMX search-as-you-type instant dropdown).
  - `analytics/` — `analytics.html` (Search Telemetry: total volume, zero-result search rate, search latency cards, top zero-result queries table, and click attribution).

- `personalization/`
  - `audiencesegment/` — `list.html` (with lifecycle badges, spend thresholds, and member counts), `detail.html` (with cohort criteria, member recalculation action, and attached campaigns), `form.html`.
  - `recommendationstrategy/` — `list.html` (with algorithm and placement pills), `detail.html` (with threshold meters, brand filtering, and target category), `form.html`.
  - `personalizedexperience/` — `list.html` (with campaign type badges and CTR meters), `detail.html` (with hero artwork preview, audience cohort link, and conversion counters), `form.html`.
  - `shopperbehaviorevent/` — `list.html` (telemetry table with event type badges and simulator shortcut), `detail.html` (with JSON payload inspector).
  - `console/` — `workbench.html` (Personalization Console: VIP counts, cart triggers, 24h event volume, interactive recommendation simulator, and active campaign ribbon preview), `partials/recommendations_preview.html` (HTMX recommendation cards with artwork and rating stars).

- `marketing_campaign/`
  - `dashboard/` — `dashboard.html` (Omnichannel Marketing Hub: delivery counters, affiliate revenue, top partners, recent dispatches, SEO health).
  - `campaign/` — `list.html` (campaign broadcasts, channel and status filters), `detail.html` (broadcast stats, deliverability rates, send action), `form.html`.
  - `affiliate/` — `list.html` (partner directory, partner type and status filters), `detail.html` (partner dossier, commission totals, conversion records, approve action), `form.html`.
  - `conversion/` — `list.html` (conversions table, attribution type and status filters), `detail.html` (order details, commission calculations, approve/void actions), `form.html`.
  - `seo_rule/` — `list.html` (rules directory, rule type and schema filters), `detail.html` (Google SERP snippet preview card, Schema.org JSON-LD code block, active toggle), `form.html`.

- `marketplace/`
  - `console/` — `dashboard.html` (Marketplace Console: active sellers, pending KYC queue, pending moderation listings, SLA breach alerts, active disputes, unpaid payout volume).
  - `marketplacevendor/` — `list.html` (seller directory, status/kyc/tier filter dropdowns), `detail.html` (vendor dossier, listings tab, sub-orders, payout history, customer disputes table), `form.html` (25 fields with explicit label-for associations).
  - `vendorproductlisting/` — `list.html` (listing cards & filter table, condition/moderation filters), `detail.html` (pricing breakdown, condition badges, catalog product link, moderation action modal), `form.html`.
  - `vendorsuborder/` — `list.html` (consignment orders, SLA status badges, fulfillment badges, payout status dropdown filter), `detail.html` (order summary, customer card, order lines table, carrier fulfillment action, dispute resolution modal), `form.html`.
  - `vendorpayout/` — `list.html` (payout batches, gateway methods, disbursement status badges), `detail.html` (financial volume, commission retained, net payout calculation, settled sub-orders table, execute disbursement modal), `form.html`.

- `review_ugc/`
  - `product_review/` — `list.html` (with star ratings, sentiment badges, verified purchase indicator, status filters), `detail.html` (review dossier, star rating display, customer link, merchant response timeline, moderation action modal), `form.html`.
  - `product_question/` — `list.html` (customer inquiries, answered/pending filters, pinned badges), `detail.html` (question dossier, customer attribution, official staff answer card, respond modal), `form.html`.
  - `visual_ugc/` — `list.html` (responsive media cards grid, media type and rights status filters), `detail.html` (media preview, tagged product/variant pills, rights approval badge, shoppable toggle), `form.html`.
  - `sentiment_summary/` — `list.html` (product scorecards, average rating stars, total reviews, recalculate action), `detail.html` (star distribution progress bars, sentiment breakdown bars, keyword praise/complaints tags, actionable recommendations, recalculate button), `form.html`.

- `customer_support/`
  - `ticket/` — `list.html` (with status, priority, channel badges, and agent filter), `detail.html` (with customer card, linked order total, SLA status, internal notes, and back navigation), `form.html`.
  - `article/` — `list.html` (with category and audience badges, helpfulness stats), `detail.html` (with markdown article reader, helpful votes counter, and back navigation), `form.html`.
  - `claim/` — `list.html` (with claim type and resolution action badges, financial amounts), `detail.html` (with safe photo evidence preview, claimed vs approved amounts, and back navigation), `form.html`.
  - `survey/` — `list.html` (with sentiment-aligned score colors and follow-up pills), `detail.html` (with CSAT/NPS rating scorecard, verbatim customer quote, and back navigation), `form.html`.

- `content_management/`
  - `page/` — `list.html` (with type, status, and layout badges, live preview link), `detail.html` (with rendered HTML preview, A/B testing scorecard, SEO meta summary), `form.html` (comprehensive layout, SEO, and A/B test controls).
  - `blog/` — `list.html` (with category badges, published date, author, reading time), `detail.html` (with markdown article view, author card, tag list), `form.html` (markdown editor, featured media picker).
  - `media/` — `list.html` (with responsive media grid, dimensions pills, folder filters), `detail.html` (with preview player, dimensions, copyable URL), `form.html` (file URL, alt text, dimensions).
  - `block/` — `list.html` (with block type pills and active toggles), `detail.html` (with live rendered component preview, styling attributes), `form.html` (block configuration, target catalog linking).

- `analytics/`
  - `cockpit.html` — Executive Real-Time Operations Cockpit: 24h revenue counters, live conversion funnel progress bar, active carts counter, top best sellers ranking table, and recent traffic touchpoints.
  - `daily_sales_snapshot/` — `list.html` (with revenue and AOV KPI cards, finalized status badges, date range filter), `detail.html` (with financial breakdown, returns/discounts meters, cart abandonment rates, recalculate action), `form.html`.
  - `customer_cohort_metric/` — `list.html` (with cohort month, period offset, acquisition channel filters, retention percentage badges), `detail.html` (with cohort retention curve scorecard, cumulative LTV breakdown, recalculate action), `form.html`.
  - `product_merchandising_metric/` — `list.html` (with velocity tier color badges [A/B/C/D], turnover ratio, gross margin rate), `detail.html` (with merchandising economics, views to cart conversion, return rates, recalculate action), `form.html`.
  - `attribution_touchpoint/` — `list.html` (with channel badges, device icons, attributed revenue, campaign filter), `detail.html` (with multi-touch attribution model weight scorecard, touchpoint positioning timeline), `form.html`.
- `mobile/`
  - `mobile_hub.html` — Mobile Commerce Command Hub: total registered devices, platform distribution (iOS/Android/PWA), active push campaigns, push revenue attribution, circular geofence status, PWA and wallet toggles.
  - `mobile_app_config/` — `list.html` (with status, PWA, and wallet badges), `detail.html` (with theme color swatch, Apple/Google Pay status, live W3C `manifest.json` code block, Back button), `form.html`.
  - `mobile_device_registration/` — `list.html` (with platform badges, push provider pills, active status, customer links), `detail.html` (with device hardware specs, telemetry coordinates, read-only push token, simulated ping trigger), `form.html`.
  - `mobile_push_campaign/` — `list.html` (with campaign status badges, platform targeting pills, delivery and revenue counters), `detail.html` (with phone lockscreen notification preview card, conversion scorecard, test send dispatch action), `form.html`.
  - `mobile_location_rule/` — `list.html` (with rule type and trigger action badges, radius meters), `detail.html` (with circular geofence radar simulator, inside/outside trigger feedback, coordinates validation), `form.html`.
- `b2b_wholesale/`
  - `wholesale_hub.html` — Wholesale Command Center console: active corporate accounts, registered buyer users, pending RFQ quote queue, credit exposure monitoring, rapid matrix ordering CTA, and PunchOut e-procurement gateway simulator.
  - `company_account/` — `list.html` (with tier pills and account status badges), `detail.html` (with credit utilization progress bar, payment terms, buyer roster table, linked quote requests), `form.html` (12 fields with explicit label associations and credit limit bounding).
  - `company_user/` — `list.html` (with role badges and spend limits), `detail.html` (with approval threshold cards, monthly spend progress gauge, permissions checklist, company account dossier), `form.html` (role selection, spend limits, order/quote permissions).
  - `quote_request/` — `list.html` (with RFQ status badges and total values), `detail.html` (with quote lines pricing table, counter-offer response form, buyer notes, and convert to order action), `form.html` (company selection, target discounts, valid until dates).
  - `order_template/` — `list.html` (with shared visibility badges and item counts), `detail.html` (with SKU requisition kit items table, default quantities, and 1-click batch add to cart action), `form.html` (template name, description, shared toggle).
  - `quick_order_matrix.html` — Rapid multi-SKU fast-order matrix: dynamic SKU auto-lookup, real-time line total calculating, and CSV file upload parsing.
  - `punchout_simulator.html` — Simulated cXML/OCI e-procurement checkout: raw cXML setup payload inspector, cart transfer simulator, and return URL redirection.
- `fraud_risk/`
  - `fraud_risk_hub.html` — Fraud & Risk Management command center hub with KPI counters, active rule summary, recent assessments, dispute queue, and security alerts.
  - `fraud_rule/` — `list.html` (with evaluation scope, rule type, risk impact badges, and search/status filters), `detail.html` (with execution priority, condition expression code block, and actions), `form.html` (comprehensive rule configuration controls).
  - `transaction_risk_assessment/` — `list.html` (with risk score gauges, tier color badges, AVS/CVV signals, action filters), `detail.html` (with telemetry signals, device fingerprint hash, geolocation, rule triggers JSON, analyst notes), `form.html` (risk assessment evaluation inputs).
  - `chargeback_dispute/` — `list.html` (with dispute stage pills, reason codes, due dates, amount counters), `detail.html` (with dispute case dossier, representment evidence, network reason category, resolution notes), `form.html` (chargeback case tracking controls).
  - `account_security_alert/` — `list.html` (with alert severity badges, incident status pills, automated policy response badges), `detail.html` (with origin IP address, geolocation, user agent fingerprint, incident telemetry, investigation findings), `form.html` (security alert triage and mitigation controls).

**UI & Badge Rules:**
- Only use color-named badge classes from `static/css/theme.css`: `badge-green`, `badge-red`, `badge-amber`, `badge-blue`, `badge-slate`.
- Stat icon classes: `stat-icon blue`, `stat-icon green`, `stat-icon orange`, `stat-icon purple`, `stat-icon slate`.
- Never use semantic `-success`, `-danger`, or `-warning` classes (which render unstyled).

---

## 5. Seeder & Demo Data

Run the idempotent demo seeder:
```powershell
venv\Scripts\python.exe manage.py seed_ecommerce
```

The command provisions:
- 5 Hierarchical Categories: Electronics, Computing, Laptops, Accessories, Audio.
- 5 Catalog Products: Pro Ultra Laptop, Mechanical Keyboard, Wireless Mouse, Noise-Cancelling Headphones, Thunderbolt Dock.
- 11 Product Variants across multiple SKUs, sizes, colors, and option configurations with pricing and compare-at discounts.
- 6 Merchandising Relationships: Cross-sells, Up-sells, Accessories, and Frequently Bought Together bundles.
- 3 Fulfillment Centers: Main Distribution Hub (`DC-MAIN-01`), West Coast 3PL Partner (`3PL-WEST-02`), Downtown Flagship Store (`RET-FLAG-01`).
- 10 Inventory Allocations with on-hand, allocated, safety stock, and bin locations.
- 3 Backorder & Pre-Order Policies with waitlist tracking and customer storefront messages.
- 4 Multi-Channel Sync Feeds covering Shopify, Amazon Prime, Walmart Marketplace, and In-Store POS with buffer percentages.
- 4 Dynamic Pricing Rules: Storewide 10% Welcome, VIP 15% Audio, Wholesale Volume Tier (Min 5 units, 20% off), Laptop Flash Deal override.
- 4 Coupon Codes: `WELCOME10` (10% off), `SAVE50` ($50 off $200 min spend), `VIPFREESHIP` (Free shipping), `BLACKFRIDAY` (25% off max $100 cap).
- 3 Flash Sales: Midnight Audio Lightning Deal, Weekend Computing Blitz, Flash Clearance.
- 4 Competitor Price Monitors: Amazon US, Walmart, Best Buy, and Newegg with beat-by-fixed, beat-by-percent, and margin floor protection.
- 4 Shopping Carts: Active authenticated cart, Abandoned guest cart with recovery token, Multi-item cart in checkout, and Converted historical cart.
- 6 Cart Items with automatic total price calculation and variant pricing inheritance.
- 4 Checkout Sessions: In-progress contact step session, Shipping method selection session, Ready-for-payment session, and Completed session with order reference.
- 4 Shipping Methods: Standard Ground (Flat Rate), Express Air (Weight Tiered), Free Shipping over $100, and Store Pickup.
- 4 Payment Methods: Stripe Credit Card, PayPal Express Wallet, Klarna BNPL, and Cash on Delivery with surcharge and order limit rules.
- 4 eCommerce Orders: Validated priority order, In-fulfillment partially shipped order, Delivered & completed order, and Cancelled customer order.
- 8 eCommerce Order Lines with line discounts, quantities, and line statuses.
- 3 Order Routing Rules: Domestic Express Routing (closest location), West Coast Drop-Ship Routing (drop-ship preferred), High Stock Allocation (highest inventory).
- 4 Order Fulfillments: Carrier-dispatched FedEx Ground package with live tracking, Shipped DHL Express package, Allocated draft package, and Delivered package.
- 3 Return Merchandise Authorizations (RMA): Damaged item refund with restock quarantine, Wrong item replacement return, and Size/fit customer return with restocking fee.
- 4 Customer Account Profiles across bronze, silver, gold, and platinum tiers with marketing consent and preferences.
- 5 Customer Address Preferences with default shipping, default billing, delivery instructions, and window selections.
- 4 Customer Wishlists with private, shared, and public visibilities.
- 6 Customer Wishlist Items with priority indicators and quantity targets.
- 4 Customer Privacy Requests covering access/export, rectification, erasure/anonymization, and CCPA opt-out.
- 4 Search Synonyms: Notebook/Laptop, Earbuds/Headphones, Clicker/Mouse, Display/Monitor.
- 5 Search Facet Configurations: Brand, Category, Price Range Slider, In-Stock Availability, Color Swatches.
- 4 Search Merchandising Rules: Pin Pro Laptop to Slot 1 on 'laptop', Boost Noise-Cancelling Headphones on 'audio', Promotional Banner on 'clearance', Customer Support Redirect on 'help'.
- 6 Search Query Logs: Successful searches, zero-result queries ('vintage typewriter'), applied facet filters, and latency tracking.
- 4 Audience Segments: High-Value VIP Champions, Active Repeat Buyers, New Browsers (First-Time), and At-Risk Cart Abandoners.
- 4 Recommendation Strategies: PDP Related Products (Content-Based), Cart Cross-Sell Frequently Bought Together (Co-occurrence), Homepage Trending & Popular, and Category Best Sellers.
- 3 Personalized Experiences: VIP Homepage Hero Takeover, Cart Abandonment Recovery Popup, and Audio Category Spotlight Ribbon.
- 10 Shopper Behavior Events: Page views, PDP product inspections, cart additions, search queries, and category browses with realistic intent scores.
- 4 Marketing Campaigns: Holiday VIP Early Access (Email), Weekend Flash Sale SMS Alert (SMS), Cart Abandonment Push Notification (Push), Omnichannel Product Launch (Omnichannel).
- 4 Affiliate Partners: Sarah Tech Reviews (influencer), Fitness Gear Blog (affiliate), Audio Geek Community (brand ambassador), Super Fan Referral Program (customer advocate).
- 4 Affiliate Referral Conversions: Approved and pending referral conversions linked to customer orders with commission calculations.
- 4 SEO Metadata Rules: Global Storefront Default, Category Dynamic Template, Product Page Dynamic Rule, and Custom URL Landing Page override with Schema.org JSON-LD.
- 4 Marketplace Vendors: Apex Tech Gear (verified/active), Bloom Organics (verified/active), Artisan Crafts (verified/active), and Nordic Living (pending KYC verification).
- 8 Vendor Product Listings: New and refurbished variants with asking prices, seller SKUs, and inventory allocations.
- 6 Vendor Sub-Orders: Consignment allocations with carrier dispatch tracking, SLA status tracking, customer ratings, and dispute simulation.
- 3 Vendor Payout Batches: Settled earnings periods covering volume, platform commissions, gateway fees, and net disbursements.
- 4 Product Reviews (`EPRV-`): 5-star verified purchase with helpful votes, 4-star verified review with official merchant response, 2-star negative review, and 1-star spam-flagged review.
- 3 Product Question Answers (`EPQA-`): Answered and pinned inquiry, answered staff response inquiry, and pending customer question.
- 4 Visual UGC Media Assets (`EUGC-`): Customer photos, unboxing videos, Instagram posts, and TikTok reviews with rights management status.
- 2 Review Sentiment Summaries (`ERVM-`): Recalculated scorecards with star distributions, aggregate averages, keyword analysis, and actionable quality recommendations.
- 4 Customer Support Tickets (`ESTK-`): WISMO order tracking inquiry, damaged item return request, pre-purchase sizing inquiry, and delivery address correction.
- 4 Knowledge Base Articles (`EKBA-`): 30-Day Hassle-Free Returns & Exchanges, Domestic & International Shipping Rates, Warranty & Defective Product Replacement, and Order Tracking WISMO Guide.
- 3 Order Issue Claims (`ECLM-`): Transit carton damage with photo evidence, package lost in transit with carrier investigation, and wrong item received with reshipment resolution.
- 4 Customer Satisfaction Surveys (`ECSF-`): 5-star post-ticket CSAT (promoter), 5-star post-delivery CSAT (promoter), 10-score storefront NPS (promoter), and 2-star delivery delay CSAT (detractor with closed-loop supervisor review).
- 4 CMS Pages (`EPAG-`): About Us (published story), Summer Clearance Landing (landing page with 50/50 A/B test active and variant B headline), Return & Refund Policy (legal/policy page), Contact & Store Locator (standard page).
- 4 Blog Editorial Articles (`EBLG-`): 2026 Sustainable Tech Trends (featured guide with reading time and tags), How to Build the Ultimate Workspace (published tutorial with markdown headings and media), NavERP Summer Product Announcements (news announcement), Customer Spotlight (draft post).
- 4 Digital Media Assets (`EMED-`): Hero Banner 4K (hero image with dimensions), Workspace Showcase (product photography), Brand Intro Video (mp4 video asset), Product Catalog Summer 2026 PDF (document asset).
- 4 Reusable Content Blocks (`EBLK-`): Summer Hero Spotlight (hero block with CTA and background styling), Product Categories Showcase Grid (category grid linked to electronics), Customer Testimonial Strip (quote block), Newsletter VIP Signup CTA (lead generation bar).
- 7 Daily Sales Snapshots (`EDSS-`): Historical revenue trends, AOV, cart abandonment rates, units sold, and orders counts.
- 4 Customer Cohort Metrics (`ECCM-`): Monthly acquisition retention offsets (months 0-3), churn rates, and cumulative LTV progression.
- 5 Product Merchandising Metrics (`EPMM-`): Merchandising economics, inventory turnover ratios, gross margins, view-to-cart conversions, and velocity tiers (A/B/C/D).
- 4 Attribution Touchpoints (`EATT-`): First-touch, last-touch, linear, time-decay, and position-based multi-touch marketing attribution touchpoints.
- 1 Mobile App Configuration (`EMAC-`): Acme Mobile Store PWA & Native configuration with standalone display, Apple Pay merchant token, Google Pay express checkout, and branded `#2563EB` status bar.
- 4 Registered Mobile Devices (`EMDR-`): iPhone 16 Pro (iOS 18.2 / APNs), Samsung Galaxy S24 Ultra (Android 15 / FCM), Google Pixel 9 Pro (Android 15 / FCM), and Desktop Chrome PWA with live telemetry coordinates and active heartbeats.
- 3 Mobile Push Campaigns (`EMPC-`): Weekend Flash Sale 20% off alert, Abandoned Cart express checkout reminder, and In-Store VIP Welcome push notification with deep-links and conversion tracking.
- 3 Store Locator & Geofence Rules (`EMLR-`): Downtown Flagship Store 150m entry geofence (push discount), West Coast Distribution Center curbside pickup radar (arrival alert), and Metropolitan Store locator guide.
- 2 B2B Corporate Company Accounts (`EBCA-`): Apex Industrial Supply (Tier 1 Preferred, $100,000 credit limit, Net 30 terms, 15% custom discount) and Nexus Heavy Industries (Tier 2 Standard, $50,000 credit limit, Net 15 terms, 10% discount).
- 3 B2B Company Users (`EBCU-`): Corporate Administrator (Full order & quote approval), Procurement Manager ($25,000 threshold), and Purchasing Buyer ($5,000 threshold).
- 2 B2B Quote Requests (`EBQR-`): Draft RFQ with customer-suggested line target pricing, and Approved Quote with counter-offer discount and order conversion capability.
- 4 B2B Quote Line Items with variant SKU bindings, requested quantities, and target vs offered unit prices.
- 2 B2B Quick Order Requisition Kits (`EBQT-`): Standard Warehouse Restock Kit and Heavy Machinery Monthly Kit with shared company access.
- 4 B2B Quick Order Items with SKU references and default restock package quantities.
- All demo data is scoped to tenant `acme` and `globex`.

---

## 6. Conventions & Gotchas

1. **Multi-Tenancy & IDOR**:
   - Every view must filter queries using `tenant=request.tenant`.
   - Single object lookups must use `ecommerce_object(Model, pk, request.tenant)` or `get_object_or_404(Model, pk=pk, tenant=request.tenant)`.
   - ModelForms must use `TenantUniqueMixin` and filter all FK querysets in `__init__` to `self.tenant`.
   - Form `clean()` methods must invoke `reject_foreign(self, cleaned_data, [...])`.
2. **Context Variable Contract**:
   - List views pass `page_obj`, `is_paginated`, filter values, and choice constants.
   - Detail views pass the singular entity name along with preloaded related collections.
3. **Available-to-Promise (ATP)**:
   - Digital storefronts must show `ATP = max(0, quantity_on_hand - quantity_allocated - safety_stock_buffer)` rather than raw on-hand stock.
4. **Audit Logging Signature**:
   - `write_audit_log(request.user, obj, action, changes_dict)` — always pass `user` first, `obj` second, short action verb third, and changes dictionary fourth.
5. **Integer Query Param Guarding (Lesson L11)**:
   - Always validate foreign key filter parameters before passing to ORM: `if param and param.isdigit():`.
6. **Open Redirect Validation**:
   - Always validate `next` and auto-redirect parameters with `url_has_allowed_host_and_scheme(url, allowed_hosts={request.get_host()})`.
7. **Pricing Engine Precedence & Margin Protection**:
   - Flash sales take highest priority during active windows.
   - Competitive repricing suggestions must never breach the `margin_floor_price` calculated from variant unit cost (`cost_price * (1 + min_margin_pct/100)`). If competitor undercuts below margin floor, monitor flags `is_margin_risk` and clamps suggested price to floor.
8. **Checkout Billing Address Inheritance**:
   - When `billing_same_as_shipping` is True, `CheckoutSession.save()` automatically clones shipping address fields into the corresponding billing fields. In forms, `billing_country` is made non-required since it is populated server-side.
9. **Single Default Address & Wishlist Constraints**:
   - `CustomerAddressPreference` and `CustomerWishlist` models enforce single-default rules on save: when `is_default_shipping`, `is_default_billing`, or `is_default` is set to True, all sibling records for that customer are automatically unset.
10. **Statutory Privacy & Anonymization Guards**:
    - Right-to-erasure workflows de-identify personal customer profiles, revoke marketing consents, deactivate associated authentication users (`user.is_active = False`), and privatize public wishlists in atomic transactions.
11. **Search Discovery Merchandising & Deduplication**:
    - Reverse FK price sorting (`variants__price`) must be annotated via `Min("variants__price")` before ordering to avoid row duplication and PostgreSQL `SELECT DISTINCT` ordering exceptions. Pinned products in merchandising rules verify `status == "active"` before insertion into rank slots.

---

12. **Cross-Record Marketplace Alignment**:
    - In `VendorSubOrder`, `payout.vendor_id` must match `vendor_id`. In `VendorProductListing`, `variant.product_id` must match `product_id`. Workflow status fields (`payout_status`, `moderation_status`, `compliance_status`) are excluded from CRUD forms to enforce authorized action transitions.
13. **Atomic Financial Settlements & Dispute Safeguards**:
    - `vendorpayout_execute`, `vendorpayout_delete`, and `vendorsuborder_dispute` are wrapped in `@transaction.atomic`. Payout execution excludes `withheld_dispute` and `refunded` sub-orders to prevent accidental disbursements.
14. **AuditLog Verb Length Limit**:
    - Audit log action strings must not exceed 10 characters (e.g. use 'dispute', 'execute', 'moderate', 'suspend'). Full details are passed in the changes payload dictionary.
15. **Sargable Time-Range Filters & Query Indexing**:
    - Avoid `created_at__date=day` in high-volume tables (which forces full-table scans by applying SQL `DATE()` functions to every row). Instead, write sargable range lookups: `created_at__gte=start_dt, created_at__lt=end_dt`. Compound indexes (`tenant`, `touchpoint_timestamp`) ensure optimal multi-tenant index lookups.
16. **Multi-Touch Marketing Attribution Model Weights**:
    - Attribution models compute conversion credit based on touchpoint sequence: First-Touch assigns 1.0 to the earliest touchpoint; Last-Touch assigns 1.0 to the latest touchpoint; Linear distributes equally (`1/N`); Time-Decay weights recent touchpoints exponentially; Position-Based (U-shaped) allocates 40% to first, 40% to last, and 20% evenly across intermediate touches. Touchpoint forms enforce `sum(weights) <= 1.0` and non-negative attribution numbers.
17. **Rate & Percentage Bounding Protection**:
    - Computed metrics (`conversion_rate`, `cart_abandonment_rate`, `retention_rate`, `gross_margin_rate`) must clamp values within database precision limits (e.g. 0.00% to 100.00% or max 999.99%) to prevent DecimalField runtime overflows.
18. **TenantUniqueMixin Constraint Integrity**:
    - Because Django `ModelForm` default validation does not check `models.UniqueConstraint` expressions on the instance before DB save, `TenantUniqueMixin` invokes `self.instance.validate_constraints(exclude=exclude)` during form validation to catch duplicate composite unique keys (such as `tenant + snapshot_date + currency`) gracefully with form field errors rather than unhandled 500 `IntegrityError` exceptions.
19. **Mobile Telemetry Coordinate Clamping & Validation (Lesson L35)**:
    - Telemetry coordinates from device heartbeats or geofence simulators must be validated with `math.isfinite()` and bounded within latitude `[-90.0, 90.0]` and longitude `[-180.0, 180.0]`. Hand-parsed numeric POST input must reject NaN, Infinity, and out-of-range floats before persisting to database DecimalFields or passing into calculations.
20. **Haversine Formula Domain Clamping**:
    - In `MobileLocationRule.distance_to()`, calculating `c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))` must clamp `a = min(1.0, max(0.0, a))` to prevent floating-point rounding errors on identical or antipodal coordinates from raising `ValueError: math domain error`.
21. **Mobile Push Lifecycle & Status Guards**:
    - Cancelled push campaigns (`status='cancelled'`) are immutable and blocked from re-dispatch in `mobilepushcampaign_test_send`. Dispatch simulations advance status to `'sent'`, record delivery and open rates, and write an audit log row with verb `'SEND'`.
22. **B2B Trade Credit Limits & Exposure Tracking**:
    - Corporate company accounts maintain strict `credit_limit` and `credit_used` balances. Orders and quote conversions calculate available credit as `credit_limit - credit_used`. If an order or conversion pushes balance past limit, account flags `is_credit_exceeded` and sets credit hold warning.
23. **B2B Tiered Buyer Roles & Authorization Thresholds**:
    - `B2bCompanyUser` roles (`company_admin`, `procurement_manager`, `buyer`, `approver`, `finance_auditor`) govern ordering and quote authorization. Purchasing buyers exceeding `approval_threshold_amount` or their `monthly_spend_limit` are blocked from direct checkout and routed to company approval.
24. **Quote Request (RFQ) State Machine & Atomic Order Conversion**:
    - `B2bQuoteRequest` enforces valid state transitions: `draft` -> `submitted` -> `under_review` -> `approved` -> `converted_to_order` (or `rejected`/`expired`). Calling `convert_to_order()` atomically provisions an `EcommerceOrder`, transfers line items with negotiated quote pricing overrides, updates account `credit_used`, links the converted order, and writes an audit log with verb `'convert'`.
25. **PunchOut e-Procurement Gateway (cXML/OCI)**:
    - PunchOut simulation implements standard POSR (PunchOutSetupRequest) session generation and PunchOutOrderMessage response XML payload construction, allowing procurement buyers from enterprise ERPs (SAP Ariba, Coupa, Jaggaer) to inspect cart items and simulate electronic procurement roundtrips.

---

## 7. Sidebar Navigation

Mounted in `apps/core/navigation.py`:
```python
LIVE_LINKS["9.1"] = ("ecommerce:catalog_overview", "9.1 Product Catalog", "ecommerce")
LIVE_LINKS["9.2"] = ("ecommerce:inventory_operations", "9.2 Inventory & Stock", "ecommerce")
LIVE_LINKS["9.3"] = {
    "Dynamic Pricing Rules": "ecommerce:dynamicpricerule_list",
    "Discount & Coupon Management": "ecommerce:couponpromotion_list",
    "Flash Sales & Limited-Time Offers": "ecommerce:flashsale_list",
    "Loyalty & Rewards Pricing": "ecommerce:couponpromotion_list",
    "Price Matching & Competitive Monitoring": "ecommerce:competitorpricemonitor_list",
}
LIVE_LINKS["9.4"] = {
    "Shopping Carts & Guest Sessions": "ecommerce:cart_list",
    "Abandoned Cart Recovery": "ecommerce:cart_list",
    "One-Page & Multi-Step Checkout": "ecommerce:checkoutsession_list",
    "Shipping Methods & Calculation": "ecommerce:shippingmethodconfig_list",
    "Payment Gateway Configuration": "ecommerce:paymentmethodconfig_list",
}
LIVE_LINKS["9.5"] = {
    "Order Lifecycle & Validation": "ecommerce:ecommerceorder_list",
    "Order Routing & Distributed Sourcing": "ecommerce:orderroutingrule_list",
    "Carrier Dispatch & Shipment Tracking": "ecommerce:orderfulfillment_list",
    "Returns & RMA Management": "ecommerce:returnmerchandiseauthorization_list",
    "Omnichannel Order Orchestration": "ecommerce:ecommerceorder_list",
}
LIVE_LINKS["9.6"] = {
    "Registration & Authentication": "ecommerce:customeraccountprofile_list",
    "Account Dashboard & Order History": "ecommerce:customeraccountprofile_list",
    "Address Book & Preferences": "ecommerce:customeraddresspreference_list",
    "Communication Preferences": "ecommerce:customeraccountprofile_list",
    "Account Security & Privacy": "ecommerce:customerprivacyrequest_list",
    "Customer Profiles": "ecommerce:customeraccountprofile_list",
    "Address Preferences": "ecommerce:customeraddresspreference_list",
    "Wishlists": "ecommerce:customerwishlist_list",
    "Privacy Requests": "ecommerce:customerprivacyrequest_list",
}
LIVE_LINKS["9.8"] = {
    "Personalization Workbench": "ecommerce:personalization_console",
    "Audience Segments": "ecommerce:audiencesegment_list",
    "Recommendation Strategies": "ecommerce:recommendationstrategy_list",
    "Personalized Experiences": "ecommerce:personalizedexperience_list",
    "Shopper Behavior Telemetry": "ecommerce:shopperbehaviorevent_list",
}
LIVE_LINKS["9.7"] = {
    "Search Workbench Console": "ecommerce:search_console",
    "Search Analytics Dashboard": "ecommerce:search_analytics",
    "Synonym Dictionaries": "ecommerce:searchsynonym_list",
    "Faceted Search Configuration": "ecommerce:searchfacetconfig_list",
    "Visual Merchandising Rules": "ecommerce:searchmerchandisingrule_list",
    "Search Query Telemetry Logs": "ecommerce:searchquerylog_list",
}
LIVE_LINKS["9.9"] = {
    "CMS Page Builder": "ecommerce:cmspage_list",
    "Blog & Articles": "ecommerce:blogarticle_list",
    "Digital Asset Manager": "ecommerce:mediaasset_list",
    "Reusable Content Blocks": "ecommerce:contentblock_list",
    "Store Navigation Menus": "ecommerce:cmspage_list",
}
LIVE_LINKS["9.10"] = {
    "Marketing Dashboard": "ecommerce:marketing_dashboard",
    "Email Marketing Automation": "ecommerce:marketingcampaign_list?channel=email",
    "SMS & Push Notification": "ecommerce:marketingcampaign_list?channel=sms",
    "Affiliate & Influencer Program": "ecommerce:affiliatepartner_list",
    "Referral Conversion Tracking": "ecommerce:affiliatereferralconversion_list",
    "Dynamic SEO & Metadata Rules": "ecommerce:seometadatarule_list",
    "Social Commerce Integration": "ecommerce:marketing_dashboard?tab=social",
}
LIVE_LINKS["9.11"] = {
    "Marketplace Console": "ecommerce:marketplace_console",
    "Seller Directory": "ecommerce:marketplacevendor_list",
    "Vendor Listings": "ecommerce:vendorproductlisting_list",
    "Consignment Orders": "ecommerce:vendorsuborder_list",
    "Vendor Payouts": "ecommerce:vendorpayout_list",
}
LIVE_LINKS["9.12"] = {
    "Subscription Plans": "ecommerce:subscriptionplan_list",
    "Subscriber Directory": "ecommerce:customersubscription_list",
    "Box Curations": "ecommerce:subscriptionboxcuration_list",
    "Retention & Deflection": "ecommerce:subscriptionretentionaction_list",
    "Subscriber Portal": "ecommerce:subscription_portal",
}
LIVE_LINKS["9.13"] = {
    "Review Collection & Moderation": "ecommerce:productreview_list",
    "Rating Aggregation & Display": "ecommerce:reviewsentimentsummary_list",
    "Q&A & Community Forums": "ecommerce:productquestionanswer_list",
    "Visual UGC & Social Proof": "ecommerce:visualugcmedia_list",
    "Review Analytics & Sentiment": "ecommerce:reviewsentimentsummary_list",
    "All Customer Reviews": "ecommerce:productreview_list",
    "Customer Q&A": "ecommerce:productquestionanswer_list",
    "Visual UGC Gallery": "ecommerce:visualugcmedia_list",
    "Sentiment Scorecards": "ecommerce:reviewsentimentsummary_list",
}
LIVE_LINKS["9.14"] = {
    "Help Desk & Ticket Management": "ecommerce:customersupportticket_list",
    "Live Chat & Chatbot": "ecommerce:customersupportticket_list?channel=chat",
    "Self-Service Knowledge Base": "ecommerce:knowledgebasearticle_list",
    "Order Inquiry & Issue Resolution": "ecommerce:orderissueclaim_list",
    "Customer Feedback & NPS": "ecommerce:customersatisfactionsurvey_list",
}
LIVE_LINKS["9.15"] = {
    "Sales Performance Dashboards": "ecommerce:dailysalessnapshot_list",
    "Customer Analytics": "ecommerce:customercohortmetric_list",
    "Product & Merchandising Analytics": "ecommerce:productmerchandisingmetric_list",
    "Marketing Attribution": "ecommerce:attributiontouchpoint_list",
    "Real-Time Operational Monitoring": "ecommerce:analytics_cockpit",
    "Sales Snapshots": "ecommerce:dailysalessnapshot_list",
    "Customer Cohorts": "ecommerce:customercohortmetric_list",
    "Merchandising Analytics": "ecommerce:productmerchandisingmetric_list",
    "Attribution Touchpoints": "ecommerce:attributiontouchpoint_list",
    "Analytics Executive Cockpit": "ecommerce:analytics_cockpit",
}
LIVE_LINKS["9.16"] = {
    "Progressive Web App (PWA)": "ecommerce:mobileappconfig_list",
    "Native Mobile Apps (iOS/Android)": "ecommerce:mobiledeviceregistration_list",
    "Mobile Payment Integration": "ecommerce:mobileappconfig_list",
    "Location-Based Services": "ecommerce:mobilelocationrule_list",
    "Social & Messaging Commerce": "ecommerce:mobilepushcampaign_list",
    "Mobile Hub": "ecommerce:mobile_hub",
    "App Configurations": "ecommerce:mobileappconfig_list",
    "Registered Devices": "ecommerce:mobiledeviceregistration_list",
    "Push Campaigns": "ecommerce:mobilepushcampaign_list",
    "Location Rules": "ecommerce:mobilelocationrule_list",
}
LIVE_LINKS["9.17"] = {
    "Company Account Management": "ecommerce:b2bcompanyaccount_list",
    "Quote Request & Negotiation": "ecommerce:b2bquoterequest_list",
    "Punch-Out Catalog Integration": "ecommerce:b2bcompanyaccount_list",
    "Credit Terms & Net Payment": "ecommerce:b2bcompanyaccount_list",
    "Bulk Ordering & Quick Order": "ecommerce:b2b_quick_order_matrix",
    "B2B Wholesale Hub": "ecommerce:b2b_wholesale_hub",
    "Company Accounts": "ecommerce:b2bcompanyaccount_list",
    "Company Buyers": "ecommerce:b2bcompanyuser_list",
    "Quote Requests (RFQ)": "ecommerce:b2bquoterequest_list",
    "Quick Order & Templates": "ecommerce:b2bquickordertemplate_list",
}
LIVE_LINKS["9.18"] = {
    "Rule-Based Fraud Detection": "ecommerce:fraud_rule_list",
    "Machine Learning Risk Scoring": "ecommerce:transaction_risk_assessment_list",
    "Chargeback & Dispute Management": "ecommerce:chargeback_dispute_list",
    "Account Takeover Protection": "ecommerce:account_security_alert_list",
    "Blacklists & Whitelists": "ecommerce:fraud_rule_list",
    "Fraud & Risk Hub": "ecommerce:fraud_risk_hub",
    "Fraud Rules": "ecommerce:fraud_rule_list",
    "Risk Assessments": "ecommerce:transaction_risk_assessment_list",
    "Chargeback Disputes": "ecommerce:chargeback_dispute_list",
    "Security Alerts": "ecommerce:account_security_alert_list",
}
```
Appears under the eCommerce section of the primary navigation bar.
