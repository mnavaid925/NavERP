from django.contrib import admin

from apps.ecommerce.models.CartCheckout.Carts import Cart, CartItem
from apps.ecommerce.models.CartCheckout.CheckoutSessions import CheckoutSession
from apps.ecommerce.models.CartCheckout.PaymentMethods import PaymentMethodConfig
from apps.ecommerce.models.CartCheckout.ShippingMethods import ShippingMethodConfig
from apps.ecommerce.models.CustomerProfile.CustomerAccountProfiles import CustomerAccountProfile
from apps.ecommerce.models.CustomerProfile.CustomerAddressPreferences import CustomerAddressPreference
from apps.ecommerce.models.CustomerProfile.CustomerPrivacyRequests import CustomerPrivacyRequest
from apps.ecommerce.models.CustomerProfile.CustomerWishlists import CustomerWishlist, CustomerWishlistItem
from apps.ecommerce.models.InventoryStock.BackorderPolicies import BackorderPolicy
from apps.ecommerce.models.InventoryStock.ChannelInventorySyncs import ChannelInventorySync
from apps.ecommerce.models.InventoryStock.FulfillmentCenters import FulfillmentCenter
from apps.ecommerce.models.InventoryStock.InventoryAllocations import InventoryAllocation
from apps.ecommerce.models.MarketingCampaign.AffiliatePartners import AffiliatePartner
from apps.ecommerce.models.MarketingCampaign.AffiliateReferralConversions import AffiliateReferralConversion
from apps.ecommerce.models.MarketingCampaign.MarketingCampaigns import MarketingCampaign
from apps.ecommerce.models.MarketingCampaign.SeoMetadataRules import SeoMetadataRule
from apps.ecommerce.models.Marketplace.MarketplaceVendors import MarketplaceVendor
from apps.ecommerce.models.Marketplace.VendorPayouts import VendorPayout
from apps.ecommerce.models.Marketplace.VendorProductListings import VendorProductListing
from apps.ecommerce.models.Marketplace.VendorSubOrders import VendorSubOrder
from apps.ecommerce.models.OrderManagement.EcommerceOrders import EcommerceOrder, EcommerceOrderLine
from apps.ecommerce.models.OrderManagement.OrderFulfillments import OrderFulfillment
from apps.ecommerce.models.OrderManagement.OrderRoutingRules import OrderRoutingRule
from apps.ecommerce.models.OrderManagement.ReturnMerchandiseAuthorizations import ReturnMerchandiseAuthorization
from apps.ecommerce.models.Personalization.AudienceSegments import AudienceSegment
from apps.ecommerce.models.Personalization.PersonalizedExperiences import PersonalizedExperience
from apps.ecommerce.models.Personalization.RecommendationStrategies import RecommendationStrategy
from apps.ecommerce.models.Personalization.ShopperBehaviorEvents import ShopperBehaviorEvent
from apps.ecommerce.models.PricingPromotion.CompetitorPriceMonitors import CompetitorPriceMonitor
from apps.ecommerce.models.PricingPromotion.CouponPromotions import CouponPromotion
from apps.ecommerce.models.PricingPromotion.DynamicPriceRules import DynamicPriceRule
from apps.ecommerce.models.PricingPromotion.FlashSales import FlashSale
from apps.ecommerce.models.ProductCatalog.CatalogProducts import CatalogProduct
from apps.ecommerce.models.ProductCatalog.ProductRelationships import ProductRelationship
from apps.ecommerce.models.ProductCatalog.ProductVariants import ProductVariant
from apps.ecommerce.models.ProductCatalog.StoreCategories import StoreCategory
from apps.ecommerce.models.SearchDiscovery.SearchFacetConfigs import SearchFacetConfig
from apps.ecommerce.models.SearchDiscovery.SearchMerchandisingRules import SearchMerchandisingRule
from apps.ecommerce.models.SearchDiscovery.SearchQueryLogs import SearchQueryLog
from apps.ecommerce.models.SearchDiscovery.SearchSynonyms import SearchSynonym
from apps.ecommerce.models.SubscriptionCommerce.CustomerSubscriptions import CustomerSubscription
from apps.ecommerce.models.SubscriptionCommerce.SubscriptionBoxCurations import SubscriptionBoxCuration
from apps.ecommerce.models.SubscriptionCommerce.SubscriptionPlans import SubscriptionPlan
from apps.ecommerce.models.SubscriptionCommerce.SubscriptionRetentionActions import SubscriptionRetentionAction


@admin.register(StoreCategory)
class StoreCategoryAdmin(admin.ModelAdmin):
    list_display = ["number", "name", "slug", "parent", "display_order", "is_active", "include_in_menu"]
    list_filter = ["is_active", "include_in_menu", "tenant"]
    search_fields = ["name", "slug", "number", "description"]
    ordering = ["tenant", "display_order", "name"]


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1
    fields = ["sku", "name", "price", "compare_at_price", "is_active", "sort_order"]


@admin.register(CatalogProduct)
class CatalogProductAdmin(admin.ModelAdmin):
    list_display = ["number", "name", "brand", "primary_category", "status", "visibility", "pim_completeness", "is_featured", "created_at"]
    list_filter = ["status", "visibility", "is_featured", "is_digital", "tenant"]
    search_fields = ["name", "slug", "number", "brand", "short_description"]
    ordering = ["-created_at"]
    inlines = [ProductVariantInline]


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ["number", "sku", "product", "name", "price", "compare_at_price", "is_active", "sort_order"]
    list_filter = ["is_active", "tenant"]
    search_fields = ["sku", "name", "number", "barcode", "product__name"]
    ordering = ["product", "sort_order", "sku"]


@admin.register(ProductRelationship)
class ProductRelationshipAdmin(admin.ModelAdmin):
    list_display = ["number", "source_product", "relationship_type", "target_product", "discount_pct", "is_active", "sort_order"]
    list_filter = ["relationship_type", "is_active", "tenant"]
    search_fields = ["number", "source_product__name", "target_product__name", "notes"]
    ordering = ["source_product", "sort_order"]


@admin.register(FulfillmentCenter)
class FulfillmentCenterAdmin(admin.ModelAdmin):
    list_display = ["number", "name", "code", "center_type", "priority", "city", "state", "is_active"]
    list_filter = ["center_type", "is_active", "tenant"]
    search_fields = ["name", "code", "city", "state", "number"]
    ordering = ["priority", "name"]


@admin.register(InventoryAllocation)
class InventoryAllocationAdmin(admin.ModelAdmin):
    list_display = ["number", "variant", "fulfillment_center", "zone_bin", "quantity_on_hand", "quantity_allocated", "safety_stock_buffer", "available_to_promise", "is_low_stock_alert"]
    list_filter = ["is_low_stock_alert", "fulfillment_center", "tenant"]
    search_fields = ["number", "variant__sku", "variant__name", "fulfillment_center__name", "zone_bin"]
    ordering = ["variant__sku", "fulfillment_center"]


@admin.register(BackorderPolicy)
class BackorderPolicyAdmin(admin.ModelAdmin):
    list_display = ["number", "variant", "policy_type", "expected_availability_date", "current_backorder_count", "max_backorder_quantity", "is_active"]
    list_filter = ["policy_type", "is_active", "tenant"]
    search_fields = ["number", "variant__sku", "variant__name", "storefront_message"]
    ordering = ["variant__sku"]


@admin.register(ChannelInventorySync)
class ChannelInventorySyncAdmin(admin.ModelAdmin):
    list_display = ["number", "channel_name", "channel_type", "variant", "fulfillment_center", "last_synced_quantity", "sync_status", "last_synced_at"]
    list_filter = ["channel_type", "sync_status", "sync_mode", "tenant"]
    search_fields = ["number", "channel_name", "variant__sku", "variant__name"]
    ordering = ["variant__sku", "channel_type"]


@admin.register(DynamicPriceRule)
class DynamicPriceRuleAdmin(admin.ModelAdmin):
    list_display = ["number", "name", "rule_type", "adjustment_value", "scope", "customer_segment", "priority", "is_active", "valid_from", "valid_to"]
    list_filter = ["rule_type", "scope", "customer_segment", "loyalty_tier", "is_active", "tenant"]
    search_fields = ["name", "number", "description"]
    ordering = ["-priority", "-created_at"]


@admin.register(CouponPromotion)
class CouponPromotionAdmin(admin.ModelAdmin):
    list_display = ["number", "code", "name", "discount_type", "discount_value", "min_spend", "used_count", "usage_limit_total", "is_active"]
    list_filter = ["discount_type", "is_stackable", "loyalty_tier_required", "is_active", "tenant"]
    search_fields = ["code", "name", "number"]
    ordering = ["-created_at"]


@admin.register(FlashSale)
class FlashSaleAdmin(admin.ModelAdmin):
    list_display = ["number", "title", "status", "discount_percentage", "flash_price", "inventory_cap", "units_sold", "start_time", "end_time"]
    list_filter = ["status", "tenant"]
    search_fields = ["title", "number", "badge_label"]
    ordering = ["-start_time"]


@admin.register(CompetitorPriceMonitor)
class CompetitorPriceMonitorAdmin(admin.ModelAdmin):
    list_display = ["number", "competitor_name", "variant", "competitor_price", "match_strategy", "min_margin_pct", "is_in_stock", "status", "last_scraped_at"]
    list_filter = ["match_strategy", "status", "is_in_stock", "tenant"]
    search_fields = ["competitor_name", "number", "variant__sku"]
    ordering = ["-last_scraped_at", "-created_at"]


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0
    fields = ["product", "variant", "quantity", "unit_price", "total_price"]


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ["number", "customer", "email", "status", "currency", "subtotal", "grand_total", "coupon_code", "last_activity_at"]
    list_filter = ["status", "currency", "tenant"]
    search_fields = ["number", "email", "session_key", "coupon_code"]
    ordering = ["-last_activity_at"]
    inlines = [CartItemInline]


@admin.register(CheckoutSession)
class CheckoutSessionAdmin(admin.ModelAdmin):
    list_display = ["number", "cart", "email", "shipping_name", "flow_type", "current_step", "status", "payment_status", "total_amount", "created_at"]
    list_filter = ["status", "flow_type", "current_step", "payment_status", "tenant"]
    search_fields = ["number", "email", "shipping_name", "cart__number"]
    ordering = ["-created_at"]


@admin.register(ShippingMethodConfig)
class ShippingMethodConfigAdmin(admin.ModelAdmin):
    list_display = ["number", "name", "code", "carrier", "calculation_type", "base_rate", "cost_per_kg", "is_active", "sort_order"]
    list_filter = ["carrier", "calculation_type", "is_active", "tenant"]
    search_fields = ["name", "code", "description"]
    ordering = ["sort_order", "name"]


@admin.register(PaymentMethodConfig)
class PaymentMethodConfigAdmin(admin.ModelAdmin):
    list_display = ["number", "name", "provider", "method_category", "environment", "fee_type", "fee_amount", "is_active", "display_order"]
    list_filter = ["provider", "method_category", "environment", "is_active", "tenant"]
    search_fields = ["name", "instructions"]
    ordering = ["display_order", "name"]


class EcommerceOrderLineInline(admin.TabularInline):
    model = EcommerceOrderLine
    extra = 0
    fields = ["product", "variant", "sku", "product_name", "quantity", "unit_price", "unit_discount", "line_total", "status"]


@admin.register(EcommerceOrder)
class EcommerceOrderAdmin(admin.ModelAdmin):
    list_display = ["number", "customer", "currency", "status", "payment_status", "fulfillment_status", "total_amount", "fraud_risk_level", "created_at"]
    list_filter = ["status", "payment_status", "fulfillment_status", "fraud_risk_level", "tenant"]
    search_fields = ["number", "customer__name", "guest_email", "shipping_name"]
    ordering = ["-created_at"]
    inlines = [EcommerceOrderLineInline]


@admin.register(OrderRoutingRule)
class OrderRoutingRuleAdmin(admin.ModelAdmin):
    list_display = ["number", "name", "strategy", "priority", "destination_country", "preferred_fulfillment_center", "allow_split_shipment", "is_active"]
    list_filter = ["strategy", "allow_split_shipment", "enable_dropship", "is_active", "tenant"]
    search_fields = ["number", "name", "destination_country", "destination_region"]
    ordering = ["priority", "name"]


@admin.register(OrderFulfillment)
class OrderFulfillmentAdmin(admin.ModelAdmin):
    list_display = ["number", "order", "fulfillment_center", "carrier_name", "tracking_number", "status", "shipping_cost", "shipped_at"]
    list_filter = ["status", "carrier_name", "fulfillment_center", "tenant"]
    search_fields = ["number", "order__number", "carrier_name", "tracking_number"]
    ordering = ["-created_at"]


@admin.register(ReturnMerchandiseAuthorization)
class ReturnMerchandiseAuthorizationAdmin(admin.ModelAdmin):
    list_display = ["number", "order", "customer", "return_type", "status", "reason", "refund_amount", "refund_status", "restocking_status"]
    list_filter = ["return_type", "status", "reason", "refund_status", "restocking_status", "tenant"]
    search_fields = ["number", "order__number", "customer__name", "return_tracking_number"]
    ordering = ["-created_at"]


@admin.register(CustomerAccountProfile)
class CustomerAccountProfileAdmin(admin.ModelAdmin):
    list_display = ["number", "customer", "user", "tier", "status", "auth_mode", "phone_number", "phone_verified", "total_spent", "order_count"]
    list_filter = ["tier", "status", "auth_mode", "phone_verified", "tenant"]
    search_fields = ["number", "customer__name", "user__username", "phone_number"]
    list_select_related = ["customer", "user"]
    ordering = ["-created_at"]


@admin.register(CustomerAddressPreference)
class CustomerAddressPreferenceAdmin(admin.ModelAdmin):
    list_display = ["number", "customer", "label", "is_default_shipping", "is_default_billing", "preferred_delivery_window", "requires_signature"]
    list_filter = ["is_default_shipping", "is_default_billing", "preferred_delivery_window", "requires_signature", "tenant"]
    search_fields = ["number", "customer__name", "label", "recipient_name"]
    list_select_related = ["customer", "address"]
    ordering = ["-created_at"]


class CustomerWishlistItemInline(admin.TabularInline):
    model = CustomerWishlistItem
    extra = 1
    fields = ["product", "variant", "desired_quantity", "priority", "comment"]


@admin.register(CustomerWishlist)
class CustomerWishlistAdmin(admin.ModelAdmin):
    list_display = ["number", "name", "customer", "visibility", "is_default", "share_token"]
    list_filter = ["visibility", "is_default", "tenant"]
    search_fields = ["number", "name", "customer__name", "share_token"]
    list_select_related = ["customer"]
    ordering = ["-created_at"]
    inlines = [CustomerWishlistItemInline]


@admin.register(CustomerWishlistItem)
class CustomerWishlistItemAdmin(admin.ModelAdmin):
    list_display = ["wishlist", "product", "variant", "desired_quantity", "priority"]
    list_filter = ["priority", "tenant"]
    search_fields = ["wishlist__name", "product__name", "comment"]
    list_select_related = ["wishlist", "product", "variant"]
    ordering = ["-created_at"]


@admin.register(CustomerPrivacyRequest)
class CustomerPrivacyRequestAdmin(admin.ModelAdmin):
    list_display = ["number", "customer", "request_type", "status", "statutory_deadline", "completed_at", "requested_by_email"]
    list_filter = ["request_type", "status", "tenant"]
    search_fields = ["number", "customer__name", "requested_by_email", "resolution_notes"]
    list_select_related = ["customer"]
    ordering = ["-created_at"]


@admin.register(SearchSynonym)
class SearchSynonymAdmin(admin.ModelAdmin):
    list_display = ["number", "name", "synonym_type", "root_term", "hit_count", "is_active", "created_at"]
    list_filter = ["synonym_type", "is_active", "tenant"]
    search_fields = ["number", "name", "root_term", "synonyms", "notes"]
    ordering = ["root_term", "-created_at"]


@admin.register(SearchFacetConfig)
class SearchFacetConfigAdmin(admin.ModelAdmin):
    list_display = ["display_order", "name", "code", "source_type", "widget_type", "filter_logic", "category_scope", "is_active"]
    list_filter = ["source_type", "widget_type", "filter_logic", "is_active", "tenant"]
    search_fields = ["name", "code", "option_key", "category_scope__name"]
    list_select_related = ["category_scope"]
    ordering = ["display_order", "name"]


@admin.register(SearchMerchandisingRule)
class SearchMerchandisingRuleAdmin(admin.ModelAdmin):
    list_display = ["priority", "name", "rule_type", "trigger_query", "action_type", "boosted_product", "is_active"]
    list_filter = ["rule_type", "action_type", "match_type", "is_active", "tenant"]
    search_fields = ["name", "trigger_query", "redirect_url", "banner_title", "boosted_product__name"]
    list_select_related = ["target_category", "boosted_product"]
    ordering = ["-priority", "-created_at"]


@admin.register(SearchQueryLog)
class SearchQueryLogAdmin(admin.ModelAdmin):
    list_display = ["number", "query_text", "results_count", "execution_time_ms", "is_zero_result", "sort_order", "customer", "created_at"]
    list_filter = ["is_zero_result", "sort_order", "tenant"]
    search_fields = ["number", "query_text", "normalized_query", "redirected_to", "session_key", "customer__name"]
    list_select_related = ["customer", "clicked_product"]
    ordering = ["-created_at"]


@admin.register(AudienceSegment)
class AudienceSegmentAdmin(admin.ModelAdmin):
    list_display = ["number", "name", "code", "lifecycle_stage", "cached_member_count", "is_active", "last_evaluated_at"]
    list_filter = ["lifecycle_stage", "is_active", "tenant"]
    search_fields = ["number", "name", "code", "description"]
    list_select_related = ["target_category"]
    ordering = ["name"]


@admin.register(RecommendationStrategy)
class RecommendationStrategyAdmin(admin.ModelAdmin):
    list_display = ["number", "name", "code", "algorithm", "placement", "fallback_strategy", "max_items", "is_active"]
    list_filter = ["algorithm", "placement", "fallback_strategy", "is_active", "tenant"]
    search_fields = ["number", "name", "code", "description"]
    list_select_related = ["target_category", "target_segment"]
    ordering = ["placement", "name"]


@admin.register(PersonalizedExperience)
class PersonalizedExperienceAdmin(admin.ModelAdmin):
    list_display = ["priority", "name", "experience_type", "target_segment", "impression_count", "click_count", "is_active"]
    list_filter = ["experience_type", "is_active", "tenant"]
    search_fields = ["number", "name", "headline", "cta_label"]
    list_select_related = ["target_segment", "target_category", "target_product"]
    ordering = ["-priority", "-created_at"]


@admin.register(ShopperBehaviorEvent)
class ShopperBehaviorEventAdmin(admin.ModelAdmin):
    list_display = ["number", "event_type", "session_key", "product", "intent_score_delta", "created_at"]
    list_filter = ["event_type", "tenant"]
    search_fields = ["number", "session_key", "referrer_url", "product__name"]
    list_select_related = ["product", "category", "customer_profile", "party", "user"]
    ordering = ["-created_at"]


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ["number", "name", "code", "plan_type", "frequency", "discount_type", "discount_value", "is_active"]
    list_filter = ["plan_type", "frequency", "discount_type", "is_active", "tenant"]
    search_fields = ["number", "name", "code", "description"]
    list_select_related = ["target_product"]
    ordering = ["name"]


@admin.register(CustomerSubscription)
class CustomerSubscriptionAdmin(admin.ModelAdmin):
    list_display = ["number", "customer_profile", "plan", "product", "status", "next_billing_date", "completed_cycles_count"]
    list_filter = ["status", "plan", "tenant"]
    search_fields = ["number", "customer_profile__customer__name", "customer_profile__user__email", "product__name"]
    list_select_related = ["customer_profile", "plan", "product", "variant"]
    ordering = ["-started_at"]


@admin.register(SubscriptionBoxCuration)
class SubscriptionBoxCurationAdmin(admin.ModelAdmin):
    list_display = ["number", "name", "cycle_identifier", "plan", "primary_product", "has_surprise_item", "start_date", "end_date", "is_active"]
    list_filter = ["is_active", "has_surprise_item", "plan", "tenant"]
    search_fields = ["number", "name", "code", "cycle_identifier", "theme_title", "preference_tag"]
    list_select_related = ["plan", "primary_product"]
    ordering = ["-start_date"]


@admin.register(SubscriptionRetentionAction)
class SubscriptionRetentionActionAdmin(admin.ModelAdmin):
    list_display = ["number", "subscription", "trigger_type", "cancellation_reason", "offered_action", "outcome", "churn_risk_score", "created_at"]
    list_filter = ["trigger_type", "outcome", "cancellation_reason", "tenant"]
    search_fields = ["number", "subscription__number", "customer_profile__user__email", "notes"]
    list_select_related = ["subscription", "customer_profile"]
    ordering = ["-created_at"]


# ---------------------------------------------------------------------------
# 9.11 Marketplace & Multi-Vendor
# ---------------------------------------------------------------------------


@admin.register(MarketplaceVendor)
class MarketplaceVendorAdmin(admin.ModelAdmin):
    list_display = ["number", "store_name", "party", "status", "kyc_status", "commission_rate", "rating_average", "is_featured"]
    list_filter = ["status", "kyc_status", "commission_type", "is_featured", "tenant"]
    search_fields = ["number", "store_name", "slug", "party__name", "support_email", "tax_id"]
    list_select_related = ["party", "owner_user", "suspended_by"]
    ordering = ["store_name"]


@admin.register(VendorProductListing)
class VendorProductListingAdmin(admin.ModelAdmin):
    list_display = ["number", "product", "vendor", "seller_sku", "asking_price", "available_quantity", "moderation_status", "compliance_status", "is_active"]
    list_filter = ["moderation_status", "compliance_status", "condition", "is_active", "tenant"]
    search_fields = ["number", "seller_sku", "barcode", "product__name", "vendor__store_name"]
    list_select_related = ["product", "variant", "vendor", "reviewed_by"]
    ordering = ["-created_at"]


@admin.register(VendorSubOrder)
class VendorSubOrderAdmin(admin.ModelAdmin):
    list_display = ["number", "order", "vendor", "fulfillment_status", "sla_status", "subtotal_amount", "net_vendor_amount", "payout_status", "dispute_status"]
    list_filter = ["fulfillment_status", "sla_status", "payout_status", "dispute_status", "tenant"]
    search_fields = ["number", "order__number", "vendor__store_name", "tracking_number", "carrier_name"]
    list_select_related = ["order", "vendor", "payout"]
    ordering = ["-created_at"]


@admin.register(VendorPayout)
class VendorPayoutAdmin(admin.ModelAdmin):
    list_display = ["number", "vendor", "period_start", "period_end", "gross_sales_amount", "commission_deducted", "net_payout_amount", "payout_status", "is_1099_reported"]
    list_filter = ["payout_status", "payout_method", "is_1099_reported", "tenant"]
    search_fields = ["number", "vendor__store_name", "reference_code", "notes"]
    list_select_related = ["vendor", "approved_by"]
    ordering = ["-period_end"]


# ---------------------------------------------------------------------------
# 9.10 Marketing & Campaign Management
# ---------------------------------------------------------------------------


@admin.register(MarketingCampaign)
class MarketingCampaignAdmin(admin.ModelAdmin):
    list_display = ["number", "name", "channel", "campaign_type", "status", "scheduled_at", "recipient_count", "delivered_count", "revenue_attributed"]
    list_filter = ["channel", "campaign_type", "status", "tenant"]
    search_fields = ["number", "name", "code", "subject"]
    list_select_related = ["target_segment", "target_product"]
    ordering = ["-created_at"]


@admin.register(AffiliatePartner)
class AffiliatePartnerAdmin(admin.ModelAdmin):
    list_display = ["number", "name", "partner_type", "referral_code", "status", "commission_type", "commission_rate", "total_orders_referred", "total_revenue_generated"]
    list_filter = ["partner_type", "status", "commission_type", "tenant"]
    search_fields = ["number", "name", "referral_code", "referral_link_slug", "party__name"]
    list_select_related = ["party", "customer_profile"]
    ordering = ["name"]


@admin.register(AffiliateReferralConversion)
class AffiliateReferralConversionAdmin(admin.ModelAdmin):
    list_display = ["number", "affiliate", "order", "attribution_type", "order_amount", "commission_amount", "status", "paid_at"]
    list_filter = ["status", "attribution_type", "tenant"]
    search_fields = ["number", "affiliate__name", "order__number", "payout_reference"]
    list_select_related = ["affiliate", "order", "referred_customer"]
    ordering = ["-created_at"]


@admin.register(SeoMetadataRule)
class SeoMetadataRuleAdmin(admin.ModelAdmin):
    list_display = ["number", "name", "rule_type", "json_ld_schema_type", "robots_directive", "sitemap_included", "target_keyword", "tracked_rank_position", "is_active"]
    list_filter = ["rule_type", "json_ld_schema_type", "robots_directive", "sitemap_included", "is_active", "tenant"]
    search_fields = ["number", "name", "target_keyword", "url_path_pattern"]
    list_select_related = ["target_category", "target_product"]
    ordering = ["-created_at"]









