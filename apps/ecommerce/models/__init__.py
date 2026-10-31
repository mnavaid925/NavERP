from apps.ecommerce.models._base import TenantNumbered, TenantOwned
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

__all__ = [
    "TenantOwned",
    "TenantNumbered",
    # 9.1 Product Catalog
    "StoreCategory",
    "CatalogProduct",
    "ProductVariant",
    "ProductRelationship",
    # 9.2 Inventory & Stock Management
    "FulfillmentCenter",
    "InventoryAllocation",
    "BackorderPolicy",
    "ChannelInventorySync",
    # 9.3 Pricing & Promotion Engine
    "DynamicPriceRule",
    "CouponPromotion",
    "FlashSale",
    "CompetitorPriceMonitor",
    # 9.4 Shopping Cart & Checkout
    "Cart",
    "CartItem",
    "CheckoutSession",
    "ShippingMethodConfig",
    "PaymentMethodConfig",
    # 9.5 Order Management System (OMS)
    "EcommerceOrder",
    "EcommerceOrderLine",
    "OrderRoutingRule",
    "OrderFulfillment",
    "ReturnMerchandiseAuthorization",
    # 9.6 Customer Account & Profile
    "CustomerAccountProfile",
    "CustomerAddressPreference",
    "CustomerWishlist",
    "CustomerWishlistItem",
    "CustomerPrivacyRequest",
    # 9.7 Search & Product Discovery
    "SearchSynonym",
    "SearchFacetConfig",
    "SearchMerchandisingRule",
    "SearchQueryLog",
    # 9.8 Personalization & Recommendation Engine
    "AudienceSegment",
    "RecommendationStrategy",
    "PersonalizedExperience",
    "ShopperBehaviorEvent",
    # 9.10 Marketing & Campaign Management
    "MarketingCampaign",
    "AffiliatePartner",
    "AffiliateReferralConversion",
    "SeoMetadataRule",
    # 9.11 Marketplace & Multi-Vendor
    "MarketplaceVendor",
    "VendorProductListing",
    "VendorSubOrder",
    "VendorPayout",
    # 9.12 Subscription & Recurring Commerce
    "SubscriptionPlan",
    "CustomerSubscription",
    "SubscriptionBoxCuration",
    "SubscriptionRetentionAction",
]
