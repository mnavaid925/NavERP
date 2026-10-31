from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounting.models.GeneralLedger.Currencies import Currency
from apps.core.models import Address, Party, Tenant
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
from apps.ecommerce.models.ProductCatalog.ProductRelationships import (
    ProductRelationship,
)
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
from apps.scm.models.InventoryManagement.Items import Item
from apps.scm.models.InventoryManagement.Locations import Location


class Command(BaseCommand):
    help = "Seed demo data for eCommerce module (9.1 Product Catalog & 9.2 Inventory & Stock)"


    def handle(self, *args, **options):
        tenants = Tenant.objects.filter(is_active=True)
        if not tenants.exists():
            self.stdout.write(self.style.WARNING("No active tenants found to seed eCommerce."))
            return

        for tenant in tenants:
            self.stdout.write(f"Seeding eCommerce for workspace {tenant.name} ({tenant.pk})...")
            with transaction.atomic():
                self._seed_tenant(tenant)

        self.stdout.write(self.style.SUCCESS("eCommerce seeding completed successfully."))
        self.stdout.write("Log in as a tenant admin (e.g. admin_acme / password) to view eCommerce data. The superuser (admin) has no tenant and sees no data.")

    def _seed_tenant(self, tenant):
        # 1. Categories
        apparel, _ = StoreCategory.objects.get_or_create(
            tenant=tenant,
            slug="apparel-fashion",
            defaults={
                "name": "Apparel & Fashion",
                "display_order": 10,
                "is_active": True,
                "include_in_menu": True,
                "description": "Modern apparel, essentials, and everyday lifestyle clothing.",
                "meta_title": "Apparel & Fashion Collection",
                "meta_description": "Shop modern lifestyle apparel and accessories.",
            },
        )

        mens, _ = StoreCategory.objects.get_or_create(
            tenant=tenant,
            slug="mens-clothing",
            defaults={
                "name": "Men's Clothing",
                "parent": apparel,
                "display_order": 1,
                "is_active": True,
                "include_in_menu": True,
                "description": "Men's tops, bottoms, and wardrobe essentials.",
            },
        )

        electronics, _ = StoreCategory.objects.get_or_create(
            tenant=tenant,
            slug="electronics",
            defaults={
                "name": "Consumer Electronics",
                "display_order": 20,
                "is_active": True,
                "include_in_menu": True,
                "description": "High-performance tech, audio, and computing hardware.",
            },
        )

        audio, _ = StoreCategory.objects.get_or_create(
            tenant=tenant,
            slug="audio-headphones",
            defaults={
                "name": "Audio & Headphones",
                "parent": electronics,
                "display_order": 1,
                "is_active": True,
                "include_in_menu": True,
                "description": "Audiophile grade headphones, earbuds, and studio monitors.",
            },
        )

        # 2. Existing SCM item lookups (for stock linking)
        scm_items = list(Item.objects.filter(tenant=tenant)[:5])
        item_1 = scm_items[0] if len(scm_items) > 0 else None
        item_2 = scm_items[1] if len(scm_items) > 1 else None
        item_3 = scm_items[2] if len(scm_items) > 2 else None

        # 3. Products
        p1, _ = CatalogProduct.objects.get_or_create(
            tenant=tenant,
            slug="classic-crewneck-tshirt",
            defaults={
                "name": "Classic Cotton Crewneck T-Shirt",
                "brand": "Acme Basics",
                "primary_category": mens,
                "item": item_1,
                "status": "active",
                "visibility": "storefront",
                "short_description": "Ultra-soft 100% organic combed cotton everyday crewneck.",
                "description": (
                    "Engineered for daily comfort and durability. Features pre-shrunk organic cotton, "
                    "reinforced ribbed collar, and tailored sleeve drape. Ideal as a base layer or standalone casual top."
                ),
                "is_featured": True,
                "hero_image_url": "https://images.unsplash.com/photo-1521572267360-ee0c2909d518?w=800",
                "meta_title": "Classic Cotton Crewneck T-Shirt - Acme Basics",
                "meta_description": "Buy high quality 100% organic cotton crewneck t-shirts.",
            },
        )
        p1.categories.add(apparel, mens)

        p2, _ = CatalogProduct.objects.get_or_create(
            tenant=tenant,
            slug="pro-wireless-headphones",
            defaults={
                "name": "Studio Pro Wireless ANC Headphones",
                "brand": "Apex Audio",
                "primary_category": audio,
                "item": item_2,
                "status": "active",
                "visibility": "storefront",
                "short_description": "Over-ear active noise cancelling headphones with 40h battery life.",
                "description": (
                    "Immerse yourself in precision acoustic clarity. Custom 40mm beryllium drivers "
                    "deliver deep responsive bass and crystalline highs. Hybrid active noise cancellation "
                    "blocks up to 35dB of ambient noise."
                ),
                "is_featured": True,
                "hero_image_url": "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=800",
                "meta_title": "Studio Pro Wireless ANC Headphones - Apex Audio",
                "meta_description": "Experience professional hybrid noise cancellation with Apex Audio.",
            },
        )
        p2.categories.add(electronics, audio)

        p3, _ = CatalogProduct.objects.get_or_create(
            tenant=tenant,
            slug="heavyweight-canvas-tote",
            defaults={
                "name": "Heavyweight Utility Canvas Tote",
                "brand": "Acme Basics",
                "primary_category": apparel,
                "item": item_3,
                "status": "active",
                "visibility": "storefront",
                "short_description": "Durable 16oz cotton duck canvas tote with internal key leash.",
                "description": (
                    "Built to carry your daily essentials, laptop, and groceries. Heavy-duty bar-tacked "
                    "handles and water-resistant wax treatment keep your goods secure."
                ),
                "hero_image_url": "https://images.unsplash.com/photo-1544816155-12df9643f363?w=800",
            },
        )
        p3.categories.add(apparel)

        # 4. Variants
        ProductVariant.objects.get_or_create(
            tenant=tenant,
            sku="TSH-NAVY-M",
            defaults={
                "product": p1,
                "name": "Navy / Medium",
                "option_values": {"Color": "Navy", "Size": "M"},
                "price": Decimal("28.00"),
                "compare_at_price": Decimal("35.00"),
                "cost_price": Decimal("9.50"),
                "item": item_1,
                "barcode": "890123456011",
                "weight_kg": Decimal("0.220"),
                "is_active": True,
                "sort_order": 1,
            },
        )
        ProductVariant.objects.get_or_create(
            tenant=tenant,
            sku="TSH-NAVY-L",
            defaults={
                "product": p1,
                "name": "Navy / Large",
                "option_values": {"Color": "Navy", "Size": "L"},
                "price": Decimal("28.00"),
                "compare_at_price": Decimal("35.00"),
                "cost_price": Decimal("9.80"),
                "item": item_1,
                "barcode": "890123456012",
                "weight_kg": Decimal("0.240"),
                "is_active": True,
                "sort_order": 2,
            },
        )
        ProductVariant.objects.get_or_create(
            tenant=tenant,
            sku="HDP-BLK",
            defaults={
                "product": p2,
                "name": "Matte Black",
                "option_values": {"Color": "Matte Black"},
                "price": Decimal("199.99"),
                "compare_at_price": Decimal("249.99"),
                "cost_price": Decimal("78.00"),
                "item": item_2,
                "barcode": "890123456021",
                "weight_kg": Decimal("0.580"),
                "is_active": True,
                "sort_order": 1,
            },
        )
        ProductVariant.objects.get_or_create(
            tenant=tenant,
            sku="TOT-NAT",
            defaults={
                "product": p3,
                "name": "Natural Canvas",
                "option_values": {"Color": "Natural"},
                "price": Decimal("24.00"),
                "cost_price": Decimal("7.00"),
                "item": item_3,
                "barcode": "890123456031",
                "weight_kg": Decimal("0.350"),
                "is_active": True,
                "sort_order": 1,
            },
        )

        # 5. Merchandising Relationships
        ProductRelationship.objects.get_or_create(
            tenant=tenant,
            source_product=p1,
            target_product=p3,
            relationship_type="cross_sell",
            defaults={
                "discount_pct": Decimal("10.00"),
                "is_active": True,
                "notes": "Add canvas tote with t-shirt for 10% bundle savings.",
            },
        )
        ProductRelationship.objects.get_or_create(
            tenant=tenant,
            source_product=p2,
            target_product=p1,
            relationship_type="bought_together",
            defaults={
                "discount_pct": Decimal("5.00"),
                "is_active": True,
                "notes": "Customers who purchased Studio Pro headphones frequently added casual apparel.",
            },
        )

        # 6. (9.2) Fulfillment Centers
        scm_loc = Location.objects.filter(tenant=tenant).first()

        fc_west, _ = FulfillmentCenter.objects.get_or_create(
            tenant=tenant,
            code="DC-WEST",
            defaults={
                "name": "West Coast Primary DC",
                "center_type": "internal_warehouse",
                "location": scm_loc,
                "priority": 1,
                "is_active": True,
                "supports_pick_pack_ship": True,
                "supports_customer_pickup": False,
                "daily_cutoff_time": "15:00:00",
                "address_line1": "1200 Logistics Parkway",
                "city": "Reno",
                "state": "NV",
                "postal_code": "89502",
                "country": "United States",
                "contact_email": "dc-west@example.com",
                "contact_phone": "+1 775-555-0144",
                "notes": "Primary West Coast e-commerce fulfillment node with automated pick/pack lanes.",
            },
        )

        fc_chi, _ = FulfillmentCenter.objects.get_or_create(
            tenant=tenant,
            code="3PL-CHI",
            defaults={
                "name": "ShipBob Midwest 3PL Hub",
                "center_type": "third_party_3pl",
                "location": None,
                "priority": 2,
                "is_active": True,
                "supports_pick_pack_ship": True,
                "supports_customer_pickup": False,
                "daily_cutoff_time": "14:30:00",
                "address_line1": "450 Industrial Expressway",
                "city": "Cicero",
                "state": "IL",
                "postal_code": "60804",
                "country": "United States",
                "contact_email": "fulfillment-chi@example.com",
                "contact_phone": "+1 312-555-0192",
                "notes": "Partner 3PL facility managing 2-day ground fulfillment across Midwest/East Coast.",
            },
        )

        fc_store, _ = FulfillmentCenter.objects.get_or_create(
            tenant=tenant,
            code="STORE-NY",
            defaults={
                "name": "Manhattan Flagship Store",
                "center_type": "retail_store",
                "location": None,
                "priority": 3,
                "is_active": True,
                "supports_pick_pack_ship": True,
                "supports_customer_pickup": True,
                "daily_cutoff_time": "18:00:00",
                "address_line1": "550 Broadway",
                "city": "New York",
                "state": "NY",
                "postal_code": "10012",
                "country": "United States",
                "contact_email": "soho-store@example.com",
                "contact_phone": "+1 212-555-0188",
                "notes": "Omnichannel flagship store offering local click-and-collect pickup and ship-from-store.",
            },
        )

        # 7. (9.2) Stock Allocations across Variants
        v1 = ProductVariant.objects.filter(tenant=tenant, sku="TSH-NAVY-M").first()
        v2 = ProductVariant.objects.filter(tenant=tenant, sku="TSH-NAVY-L").first()
        v3 = ProductVariant.objects.filter(tenant=tenant, sku="HDP-BLK").first()
        v4 = ProductVariant.objects.filter(tenant=tenant, sku="TOT-NAT").first()

        now = timezone.now()

        if v1:
            InventoryAllocation.objects.get_or_create(
                tenant=tenant,
                variant=v1,
                fulfillment_center=fc_west,
                defaults={
                    "product": v1.product,
                    "zone_bin": "Aisle 2, Bin A-14",
                    "quantity_on_hand": 140,
                    "quantity_allocated": 15,
                    "safety_stock_buffer": 10,
                    "low_stock_threshold": 20,
                    "restock_lead_time_days": 5,
                    "last_counted_at": now,
                    "notes": "High velocity size M t-shirts in primary pick zone.",
                },
            )
            InventoryAllocation.objects.get_or_create(
                tenant=tenant,
                variant=v1,
                fulfillment_center=fc_chi,
                defaults={
                    "product": v1.product,
                    "zone_bin": "Rack 04, Shelf 2",
                    "quantity_on_hand": 8,
                    "quantity_allocated": 4,
                    "safety_stock_buffer": 2,
                    "low_stock_threshold": 10,
                    "restock_lead_time_days": 7,
                    "last_counted_at": now,
                    "notes": "Midwest hub approaching stockout; replenishment recommended.",
                },
            )

        if v2:
            InventoryAllocation.objects.get_or_create(
                tenant=tenant,
                variant=v2,
                fulfillment_center=fc_west,
                defaults={
                    "product": v2.product,
                    "zone_bin": "Aisle 2, Bin A-15",
                    "quantity_on_hand": 85,
                    "quantity_allocated": 10,
                    "safety_stock_buffer": 5,
                    "low_stock_threshold": 15,
                    "restock_lead_time_days": 5,
                    "last_counted_at": now,
                },
            )

        if v3:
            InventoryAllocation.objects.get_or_create(
                tenant=tenant,
                variant=v3,
                fulfillment_center=fc_west,
                defaults={
                    "product": v3.product,
                    "zone_bin": "Secure Cage, Bin S-03",
                    "quantity_on_hand": 55,
                    "quantity_allocated": 8,
                    "safety_stock_buffer": 5,
                    "low_stock_threshold": 10,
                    "restock_lead_time_days": 14,
                    "last_counted_at": now,
                    "notes": "High-value electronics stored in access-controlled cage.",
                },
            )
            InventoryAllocation.objects.get_or_create(
                tenant=tenant,
                variant=v3,
                fulfillment_center=fc_store,
                defaults={
                    "product": v3.product,
                    "zone_bin": "Backroom Shelf 3",
                    "quantity_on_hand": 12,
                    "quantity_allocated": 2,
                    "safety_stock_buffer": 2,
                    "low_stock_threshold": 5,
                    "restock_lead_time_days": 3,
                    "last_counted_at": now,
                    "notes": "Store stock allocated for both walk-in retail and click & collect.",
                },
            )

        if v4:
            InventoryAllocation.objects.get_or_create(
                tenant=tenant,
                variant=v4,
                fulfillment_center=fc_west,
                defaults={
                    "product": v4.product,
                    "zone_bin": "Aisle 5, Bin C-09",
                    "quantity_on_hand": 210,
                    "quantity_allocated": 20,
                    "safety_stock_buffer": 15,
                    "low_stock_threshold": 30,
                    "restock_lead_time_days": 7,
                    "last_counted_at": now,
                },
            )

        # 8. (9.2) Backorder & Pre-Order Policies
        if v1:
            BackorderPolicy.objects.get_or_create(
                tenant=tenant,
                variant=v1,
                defaults={
                    "policy_type": "pre_order_only",
                    "storefront_message": "Pre-Order: Batch 2 shipment arriving Nov 20th. Order now to reserve.",
                    "expected_availability_date": timezone.localdate() + timezone.timedelta(days=21),
                    "max_backorder_quantity": 100,
                    "current_backorder_count": 18,
                    "auto_notify_waitlist": True,
                    "is_active": True,
                    "notes": "Special pre-order campaign for bestselling navy crewneck.",
                },
            )

        if v2:
            BackorderPolicy.objects.get_or_create(
                tenant=tenant,
                variant=v2,
                defaults={
                    "policy_type": "deny_when_empty",
                    "storefront_message": "Item is temporarily out of stock. Join waitlist for notification.",
                    "expected_availability_date": timezone.localdate() + timezone.timedelta(days=14),
                    "max_backorder_quantity": 0,
                    "current_backorder_count": 0,
                    "auto_notify_waitlist": True,
                    "is_active": True,
                    "notes": "Standard out-of-stock denial rule.",
                },
            )

        if v3:
            BackorderPolicy.objects.get_or_create(
                tenant=tenant,
                variant=v3,
                defaults={
                    "policy_type": "allow_backorder_with_notice",
                    "storefront_message": "Backordered: Expected to ship within 7-10 business days.",
                    "expected_availability_date": timezone.localdate() + timezone.timedelta(days=10),
                    "max_backorder_quantity": 50,
                    "current_backorder_count": 7,
                    "auto_notify_waitlist": True,
                    "is_active": True,
                },
            )

        # 9. (9.2) Multi-Channel Inventory Sync Feeds
        if v1:
            ChannelInventorySync.objects.get_or_create(
                tenant=tenant,
                variant=v1,
                channel_type="web_storefront",
                channel_name="Direct Online Web Store",
                defaults={
                    "fulfillment_center": None,
                    "sync_mode": "real_time",
                    "allocation_buffer_pct": Decimal("0.00"),
                    "last_synced_quantity": 117,
                    "sync_status": "synced",
                    "last_synced_at": now,
                },
            )
            ChannelInventorySync.objects.get_or_create(
                tenant=tenant,
                variant=v1,
                channel_type="amazon_marketplace",
                channel_name="US Amazon Prime Seller Feed",
                defaults={
                    "fulfillment_center": fc_west,
                    "sync_mode": "scheduled_batch",
                    "allocation_buffer_pct": Decimal("5.00"),
                    "last_synced_quantity": 109,
                    "sync_status": "synced",
                    "last_synced_at": now,
                },
            )

        if v3:
            ChannelInventorySync.objects.get_or_create(
                tenant=tenant,
                variant=v3,
                channel_type="walmart_marketplace",
                channel_name="Walmart Marketplace Storefront",
                defaults={
                    "fulfillment_center": fc_west,
                    "sync_mode": "real_time",
                    "allocation_buffer_pct": Decimal("10.00"),
                    "last_synced_quantity": 37,
                    "sync_status": "synced",
                    "last_synced_at": now,
                },
            )

        if v4:
            ChannelInventorySync.objects.get_or_create(
                tenant=tenant,
                variant=v4,
                channel_type="pos_retail",
                channel_name="SoHo Retail POS Terminal",
                defaults={
                    "fulfillment_center": fc_store,
                    "sync_mode": "real_time",
                    "allocation_buffer_pct": Decimal("0.00"),
                    "last_synced_quantity": 0,
                    "sync_status": "synced",
                    "last_synced_at": now,
                },
            )

        self._seed_pricing_promotion(tenant, now)

    def _seed_pricing_promotion(self, tenant, now):
        cat_apparel = StoreCategory.objects.filter(tenant=tenant).first()
        v1 = ProductVariant.objects.filter(tenant=tenant, sku="HDP-BLK").first()
        v2 = ProductVariant.objects.filter(tenant=tenant, sku="TSH-NAVY-M").first()
        v3 = ProductVariant.objects.filter(tenant=tenant, sku="TOT-NAT").first()
        prod_headphones = v1.product if v1 else None
        prod_tshirt = v3.product if v3 else (v2.product if v2 else None)

        # 1. DynamicPriceRule
        DynamicPriceRule.objects.get_or_create(
            tenant=tenant,
            name="VIP Autumn Clearance 15% Off",
            defaults={
                "rule_type": "percentage_discount",
                "adjustment_value": Decimal("15.0000"),
                "scope": "storewide",
                "customer_segment": "vip",
                "loyalty_tier": "gold",
                "min_quantity": 1,
                "valid_from": now - timedelta(days=5),
                "valid_to": now + timedelta(days=60),
                "priority": 20,
                "is_active": True,
                "description": "Storewide 15% discount for Gold VIP members.",
            },
        )

        DynamicPriceRule.objects.get_or_create(
            tenant=tenant,
            name="Bulk Wholesale Tier - 20% Off 10+ Units",
            defaults={
                "rule_type": "percentage_discount",
                "adjustment_value": Decimal("20.0000"),
                "scope": "storewide",
                "customer_segment": "wholesale",
                "loyalty_tier": "none",
                "min_quantity": 10,
                "valid_from": now - timedelta(days=30),
                "valid_to": now + timedelta(days=180),
                "priority": 30,
                "is_active": True,
                "description": "Quantity volume break for B2B wholesale buyers.",
            },
        )

        if cat_apparel:
            DynamicPriceRule.objects.get_or_create(
                tenant=tenant,
                name="Apparel Fixed $10 Off",
                defaults={
                    "rule_type": "fixed_discount",
                    "adjustment_value": Decimal("10.0000"),
                    "scope": "category",
                    "category": cat_apparel,
                    "customer_segment": "all",
                    "loyalty_tier": "none",
                    "min_quantity": 1,
                    "valid_from": now - timedelta(days=2),
                    "valid_to": now + timedelta(days=30),
                    "priority": 15,
                    "is_active": True,
                    "description": "Seasonal category discount on apparel.",
                },
            )

        if v1:
            DynamicPriceRule.objects.get_or_create(
                tenant=tenant,
                name="Flagship SKU Special $249 Override",
                defaults={
                    "rule_type": "fixed_price_override",
                    "adjustment_value": Decimal("249.0000"),
                    "scope": "variant",
                    "variant": v1,
                    "customer_segment": "retail",
                    "loyalty_tier": "none",
                    "min_quantity": 1,
                    "valid_from": now - timedelta(days=1),
                    "valid_to": now + timedelta(days=14),
                    "priority": 25,
                    "is_active": True,
                    "description": "Promotional retail price override for PNC-BLK.",
                },
            )

        # 2. CouponPromotion
        CouponPromotion.objects.get_or_create(
            tenant=tenant,
            code="WELCOME10",
            defaults={
                "name": "New Shopper 10% Welcome Voucher",
                "discount_type": "percentage",
                "discount_value": Decimal("10.0000"),
                "min_spend": Decimal("50.0000"),
                "usage_limit_per_customer": 1,
                "is_stackable": False,
                "loyalty_tier_required": "none",
                "valid_from": now - timedelta(days=10),
                "valid_to": now + timedelta(days=90),
                "is_active": True,
            },
        )

        CouponPromotion.objects.get_or_create(
            tenant=tenant,
            code="VIPGOLD2026",
            defaults={
                "name": "Gold Tier Exclusive 20% Off",
                "discount_type": "percentage",
                "discount_value": Decimal("20.0000"),
                "min_spend": Decimal("100.0000"),
                "max_discount_amount": Decimal("50.0000"),
                "usage_limit_total": 200,
                "used_count": 14,
                "usage_limit_per_customer": 2,
                "is_stackable": True,
                "loyalty_tier_required": "gold",
                "valid_from": now - timedelta(days=3),
                "valid_to": now + timedelta(days=45),
                "is_active": True,
            },
        )

        CouponPromotion.objects.get_or_create(
            tenant=tenant,
            code="FREESHIP",
            defaults={
                "name": "Free Standard Ground Shipping",
                "discount_type": "free_shipping",
                "discount_value": Decimal("0.0000"),
                "min_spend": Decimal("75.0000"),
                "usage_limit_per_customer": 5,
                "is_stackable": True,
                "loyalty_tier_required": "none",
                "valid_from": now - timedelta(days=7),
                "valid_to": now + timedelta(days=60),
                "is_active": True,
            },
        )

        CouponPromotion.objects.get_or_create(
            tenant=tenant,
            code="SAVE25",
            defaults={
                "name": "$25 Off Orders Over $150",
                "discount_type": "fixed_cart",
                "discount_value": Decimal("25.0000"),
                "min_spend": Decimal("150.0000"),
                "usage_limit_total": 500,
                "used_count": 42,
                "usage_limit_per_customer": 1,
                "is_stackable": False,
                "loyalty_tier_required": "none",
                "valid_from": now - timedelta(days=5),
                "valid_to": now + timedelta(days=30),
                "is_active": True,
            },
        )

        # 3. FlashSale
        FlashSale.objects.get_or_create(
            tenant=tenant,
            title="Midnight Lightning Deal - 40% Off Audio",
            defaults={
                "status": "active",
                "variant": v1,
                "product": prod_headphones,
                "discount_percentage": Decimal("40.00"),
                "inventory_cap": 50,
                "units_sold": 19,
                "max_units_per_order": 2,
                "start_time": now - timedelta(hours=6),
                "end_time": now + timedelta(hours=18),
                "badge_label": "LIGHTNING DEAL",
                "banner_bg_color": "#ef4444",
                "terms_and_conditions": "Limited stock. One deal per customer household. No rainchecks.",
            },
        )

        FlashSale.objects.get_or_create(
            tenant=tenant,
            title="Weekend Apparel Blowout",
            defaults={
                "status": "scheduled",
                "category": cat_apparel,
                "discount_percentage": Decimal("25.00"),
                "inventory_cap": 150,
                "units_sold": 0,
                "max_units_per_order": 4,
                "start_time": now + timedelta(days=2),
                "end_time": now + timedelta(days=4),
                "badge_label": "WEEKEND SPECIAL",
                "banner_bg_color": "#8b5cf6",
                "terms_and_conditions": "Valid online only across all apparel categories.",
            },
        )

        # 4. CompetitorPriceMonitor
        if v1:
            CompetitorPriceMonitor.objects.get_or_create(
                tenant=tenant,
                competitor_name="Amazon US",
                variant=v1,
                defaults={
                    "product": prod_headphones,
                    "competitor_url": "https://www.amazon.com/dp/B0EXAMPLE1",
                    "competitor_price": Decimal("279.0000"),
                    "competitor_currency": "USD",
                    "is_in_stock": True,
                    "last_scraped_at": now - timedelta(hours=2),
                    "match_strategy": "beat_by_fixed",
                    "beat_by_value": Decimal("1.0000"),
                    "min_margin_pct": Decimal("15.00"),
                    "floor_price": Decimal("220.0000"),
                    "status": "active",
                    "notes": "Amazon Prime seller listing. Auto-beat by $1 with 15% margin floor.",
                },
            )

            CompetitorPriceMonitor.objects.get_or_create(
                tenant=tenant,
                competitor_name="BestBuy Marketplace",
                variant=v1,
                defaults={
                    "product": prod_headphones,
                    "competitor_url": "https://www.bestbuy.com/site/example-audio",
                    "competitor_price": Decimal("289.9900"),
                    "competitor_currency": "USD",
                    "is_in_stock": True,
                    "last_scraped_at": now - timedelta(hours=4),
                    "match_strategy": "match_exact",
                    "beat_by_value": Decimal("0.0000"),
                    "min_margin_pct": Decimal("10.00"),
                    "status": "active",
                    "notes": "Exact match tracking for BestBuy online storefront.",
                },
            )

        if v3:
            CompetitorPriceMonitor.objects.get_or_create(
                tenant=tenant,
                competitor_name="Walmart Store",
                variant=v3,
                defaults={
                    "competitor_url": "https://www.walmart.com/ip/example-tee",
                    "competitor_price": Decimal("24.5000"),
                    "competitor_currency": "USD",
                    "is_in_stock": True,
                    "last_scraped_at": now - timedelta(hours=8),
                    "match_strategy": "beat_by_percent",
                    "beat_by_value": Decimal("5.0000"),
                    "min_margin_pct": Decimal("12.00"),
                    "status": "active",
                    "notes": "Competitor apparel tracking with 5% undercut rule.",
                },
            )

        # ----------------------------------------------------------------------
        # 9.4 Shopping Cart & Checkout Seeding
        # ----------------------------------------------------------------------
        # 1. Shipping Methods
        ship_ground, _ = ShippingMethodConfig.objects.get_or_create(
            tenant=tenant,
            code="GROUND",
            defaults={
                "name": "Standard Ground Delivery",
                "carrier": "custom",
                "calculation_type": "flat_rate",
                "base_rate": Decimal("9.99"),
                "estimated_days_min": 3,
                "estimated_days_max": 5,
                "destination_countries": "US,CA",
                "is_active": True,
                "sort_order": 1,
                "description": "Standard door-to-door ground parcel delivery via local fleet.",
            },
        )

        ship_express, _ = ShippingMethodConfig.objects.get_or_create(
            tenant=tenant,
            code="EXPRESS",
            defaults={
                "name": "Express 2-Day Air",
                "carrier": "fedex",
                "calculation_type": "weight_tiered",
                "base_rate": Decimal("19.99"),
                "cost_per_kg": Decimal("2.50"),
                "estimated_days_min": 1,
                "estimated_days_max": 2,
                "destination_countries": "US,CA,GB,DE",
                "is_active": True,
                "sort_order": 2,
                "description": "Expedited air cargo delivery via FedEx Priority.",
            },
        )

        ship_free, _ = ShippingMethodConfig.objects.get_or_create(
            tenant=tenant,
            code="FREE_75",
            defaults={
                "name": "Free Economy Shipping ($75+)",
                "carrier": "usps",
                "calculation_type": "free_threshold",
                "base_rate": Decimal("7.99"),
                "free_shipping_threshold": Decimal("75.00"),
                "estimated_days_min": 5,
                "estimated_days_max": 8,
                "destination_countries": "US",
                "is_active": True,
                "sort_order": 3,
                "description": "Complimentary economy parcel post on orders exceeding $75.",
            },
        )

        ship_pickup, _ = ShippingMethodConfig.objects.get_or_create(
            tenant=tenant,
            code="PICKUP",
            defaults={
                "name": "Local Warehouse Pickup",
                "carrier": "custom",
                "calculation_type": "local_pickup",
                "base_rate": Decimal("0.00"),
                "estimated_days_min": 1,
                "estimated_days_max": 1,
                "destination_countries": "ALL",
                "is_active": True,
                "sort_order": 4,
                "description": "Customer self-service collection at central fulfillment depot.",
            },
        )

        # 2. Payment Methods
        pay_stripe, _ = PaymentMethodConfig.objects.get_or_create(
            tenant=tenant,
            name="Credit / Debit Card (Stripe)",
            defaults={
                "provider": "stripe",
                "method_category": "credit_card",
                "environment": "sandbox",
                "is_active": True,
                "display_order": 1,
                "fee_type": "none",
                "supported_currencies": "USD,EUR,GBP",
                "instructions": "Enter card credentials securely through PCI SAQ-A compliant iframe.",
                "supports_refunds": True,
            },
        )

        pay_paypal, _ = PaymentMethodConfig.objects.get_or_create(
            tenant=tenant,
            name="PayPal Express Checkout",
            defaults={
                "provider": "paypal",
                "method_category": "wallet",
                "environment": "sandbox",
                "is_active": True,
                "display_order": 2,
                "fee_type": "none",
                "supported_currencies": "USD,EUR,GBP",
                "instructions": "Log in to PayPal to complete one-touch checkout.",
                "supports_refunds": True,
            },
        )

        pay_klarna, _ = PaymentMethodConfig.objects.get_or_create(
            tenant=tenant,
            name="Klarna Buy Now Pay Later",
            defaults={
                "provider": "klarna",
                "method_category": "bnpl",
                "environment": "sandbox",
                "is_active": True,
                "display_order": 3,
                "fee_type": "none",
                "min_order_amount": Decimal("35.00"),
                "max_order_amount": Decimal("1500.00"),
                "supported_currencies": "USD,EUR",
                "instructions": "Split purchase into 4 interest-free installments.",
                "supports_refunds": True,
            },
        )

        pay_wire, _ = PaymentMethodConfig.objects.get_or_create(
            tenant=tenant,
            name="Direct Bank Wire Transfer",
            defaults={
                "provider": "bank_transfer",
                "method_category": "bank_transfer",
                "environment": "production",
                "is_active": True,
                "display_order": 4,
                "fee_type": "none",
                "supported_currencies": "USD,EUR,GBP",
                "instructions": "Wire remittance: Routing #021000021, Account #9876543210 (NavERP Corp).",
                "supports_refunds": False,
            },
        )

        pay_cod, _ = PaymentMethodConfig.objects.get_or_create(
            tenant=tenant,
            name="Cash on Delivery (COD)",
            defaults={
                "provider": "cod",
                "method_category": "cash_on_delivery",
                "environment": "production",
                "is_active": True,
                "display_order": 5,
                "fee_type": "fixed",
                "fee_amount": Decimal("5.00"),
                "max_order_amount": Decimal("500.00"),
                "supported_currencies": "USD",
                "instructions": "Pay courier upon physical package delivery. Cash or cashier check.",
                "supports_refunds": False,
            },
        )

        # 3. Carts & Line Items
        cust_party = Party.objects.filter(tenant=tenant).order_by("id").first()

        cart_active, created = Cart.objects.get_or_create(
            tenant=tenant,
            session_key="sess_cust_active_demo",
            defaults={
                "customer": cust_party,
                "email": "customer.active@example.com",
                "status": "active",
                "currency": "USD",
                "subtotal": Decimal("598.00"),
                "grand_total": Decimal("598.00"),
                "notes": "VIP customer persistent desktop cart session.",
            },
        )
        if created and v1 and prod_headphones:
            CartItem.objects.create(
                cart=cart_active,
                product=prod_headphones,
                variant=v1,
                quantity=2,
                unit_price=v1.price,
                total_price=(v1.price * 2).quantize(Decimal("0.01")),
            )
            cart_active.recalculate_totals()

        cart_abandoned, created_ab = Cart.objects.get_or_create(
            tenant=tenant,
            session_key="sess_guest_abandoned_abc123",
            defaults={
                "email": "guest.shopper@example.com",
                "status": "abandoned",
                "currency": "USD",
                "subtotal": Decimal("25.00"),
                "grand_total": Decimal("25.00"),
                "abandoned_at": now - timedelta(hours=6),
                "recovery_token": f"recov_token_demo_{tenant.pk}_{abs(hash(tenant.name)) % 100000}",
                "recovery_sent_at": now - timedelta(hours=1),
                "notes": "Anonymous guest dropped off at checkout step 2.",
            },
        )
        if created_ab and v3 and prod_tshirt:
            CartItem.objects.create(
                cart=cart_abandoned,
                product=prod_tshirt,
                variant=v3,
                quantity=1,
                unit_price=v3.price,
                total_price=v3.price,
            )
            cart_abandoned.recalculate_totals()

        cart_checkout, created_ck = Cart.objects.get_or_create(
            tenant=tenant,
            session_key="sess_guest_checkout_999",
            defaults={
                "email": "checkout.shopper@example.com",
                "status": "locked",
                "currency": "USD",
                "subtotal": Decimal("349.00"),
                "grand_total": Decimal("358.99"),
                "notes": "Active checkout session in progress.",
            },
        )
        if created_ck and v1 and prod_headphones:
            CartItem.objects.create(
                cart=cart_checkout,
                product=prod_headphones,
                variant=v1,
                quantity=1,
                unit_price=v1.price,
                total_price=v1.price,
            )
            if v3 and prod_tshirt:
                CartItem.objects.create(
                    cart=cart_checkout,
                    product=prod_tshirt,
                    variant=v3,
                    quantity=2,
                    unit_price=v3.price,
                    total_price=(v3.price * 2).quantize(Decimal("0.01")),
                )
            cart_checkout.recalculate_totals()

        # 4. Checkout Sessions
        CheckoutSession.objects.get_or_create(
            tenant=tenant,
            cart=cart_checkout,
            defaults={
                "customer": cust_party,
                "email": "checkout.shopper@example.com",
                "phone": "+1-555-0199",
                "flow_type": "one_page",
                "current_step": "payment",
                "status": "in_progress",
                "shipping_name": "Jane Shopper",
                "shipping_address_line1": "742 Evergreen Terrace",
                "shipping_city": "Springfield",
                "shipping_state": "IL",
                "shipping_postal_code": "62704",
                "shipping_country": "US",
                "billing_same_as_shipping": True,
                "shipping_method": ship_ground,
                "payment_method": pay_stripe,
                "subtotal_amount": cart_checkout.subtotal,
                "shipping_amount": Decimal("9.99"),
                "total_amount": cart_checkout.subtotal + Decimal("9.99"),
                "payment_status": "pending",
                "expires_at": now + timedelta(hours=20),
            },
        )

        CheckoutSession.objects.get_or_create(
            tenant=tenant,
            cart=cart_active,
            defaults={
                "customer": cust_party,
                "email": "customer.active@example.com",
                "phone": "+1-555-0144",
                "flow_type": "multi_step",
                "current_step": "completed",
                "status": "completed",
                "shipping_name": "Alice Montgomery",
                "shipping_address_line1": "100 Corporate Parkway",
                "shipping_city": "Chicago",
                "shipping_state": "IL",
                "shipping_postal_code": "60601",
                "shipping_country": "US",
                "billing_same_as_shipping": True,
                "shipping_method": ship_express,
                "payment_method": pay_stripe,
                "subtotal_amount": cart_active.subtotal,
                "shipping_amount": Decimal("19.99"),
                "total_amount": cart_active.subtotal + Decimal("19.99"),
                "payment_status": "paid",
                "payment_transaction_id": "ch_stripe_demo_94883",
                "order_reference": "ORD-2026-94001",
                "expires_at": now + timedelta(days=1),
                "completed_at": now - timedelta(hours=1),
            },
        )

        # -----------------------------------------------------------------
        # 9.5 Order Management System (OMS)
        # -----------------------------------------------------------------
        fc_chi = FulfillmentCenter.objects.filter(tenant=tenant, code="3PL-CHI").first()
        fc_west = FulfillmentCenter.objects.filter(tenant=tenant, code="DC-WEST").first() or fc_chi

        usd, _ = Currency.objects.get_or_create(
            code="USD",
            defaults={"name": "US Dollar", "symbol": "$", "is_active": True},
        )

        # 1. Routing Rules
        rr_domestic, _ = OrderRoutingRule.objects.get_or_create(
            tenant=tenant,
            name="Domestic Express Routing",
            defaults={
                "strategy": "closest_location",
                "priority": 1,
                "destination_country": "US",
                "destination_region": "Midwest",
                "preferred_fulfillment_center": fc_chi,
                "allow_split_shipment": True,
                "enable_dropship": False,
                "is_active": True,
                "description": "Primary fulfillment route for domestic US midwest orders via Chicago Hub.",
            },
        )

        rr_west, _ = OrderRoutingRule.objects.get_or_create(
            tenant=tenant,
            name="West Coast Regional Sourcing",
            defaults={
                "strategy": "closest_location",
                "priority": 2,
                "destination_country": "US",
                "destination_region": "West Coast",
                "preferred_fulfillment_center": fc_west,
                "allow_split_shipment": True,
                "enable_dropship": True,
                "is_active": True,
                "description": "Dispatches Pacific and West coast orders from Oakland Distribution Hub.",
            },
        )

        rr_intl, _ = OrderRoutingRule.objects.get_or_create(
            tenant=tenant,
            name="Global Single-Node Sourcing",
            defaults={
                "strategy": "fewest_splits",
                "priority": 10,
                "destination_country": "",
                "destination_region": "",
                "preferred_fulfillment_center": fc_chi,
                "allow_split_shipment": False,
                "enable_dropship": False,
                "is_active": True,
                "description": "Fallback rule to prevent international split shipments and consolidate packages.",
            },
        )

        # 2. eCommerce Orders
        order_cust = cust_party or Party.objects.filter(tenant=tenant).first()
        prod_tshirt = CatalogProduct.objects.filter(tenant=tenant, slug="classic-crewneck-tshirt").first()
        var_tshirt_m = ProductVariant.objects.filter(tenant=tenant, sku="TSH-NAVY-M").first()
        var_hoodie = ProductVariant.objects.filter(tenant=tenant, sku="HDP-BLK").first()
        prod_hoodie = CatalogProduct.objects.filter(tenant=tenant, slug="heavyweight-pullover-hoodie").first()
        applied_promo = CouponPromotion.objects.filter(tenant=tenant).first()

        order_processing = None
        if order_cust:
            order_processing, created = EcommerceOrder.objects.get_or_create(
                tenant=tenant,
                shipping_name="Alice Montgomery",
                shipping_address_line1="100 Corporate Parkway",
                defaults={
                    "customer": order_cust,
                    "guest_email": "alice.montgomery@example.com",
                    "currency": usd,
                    "status": "processing",
                    "payment_status": "captured",
                    "fulfillment_status": "partially_fulfilled",
                    "fraud_risk_level": "low",
                    "fraud_score": 12,
                    "address_verification_status": "passed",
                    "inventory_reservation_status": "allocated",
                    "shipping_city": "Chicago",
                    "shipping_state": "IL",
                    "shipping_postal_code": "60601",
                    "shipping_country": "US",
                    "billing_name": "Alice Montgomery",
                    "billing_address_line1": "100 Corporate Parkway",
                    "billing_city": "Chicago",
                    "billing_state": "IL",
                    "billing_postal_code": "60601",
                    "billing_country": "US",
                    "discount_amount": Decimal("15.00"),
                    "shipping_amount": Decimal("12.50"),
                    "tax_amount": Decimal("8.20"),
                    "applied_coupon": applied_promo,
                    "customer_notes": "Please leave at front reception desk.",
                    "internal_notes": "High priority corporate client.",
                },
            )
            if created and prod_tshirt and var_tshirt_m:
                EcommerceOrderLine.objects.create(
                    tenant=tenant,
                    order=order_processing,
                    product=prod_tshirt,
                    variant=var_tshirt_m,
                    sku=var_tshirt_m.sku,
                    product_name=prod_tshirt.name,
                    quantity=3,
                    fulfilled_quantity=2,
                    unit_price=Decimal("38.00"),
                    unit_discount=Decimal("5.00"),
                    status="fulfilled",
                )
            if created and prod_hoodie and var_hoodie:
                EcommerceOrderLine.objects.create(
                    tenant=tenant,
                    order=order_processing,
                    product=prod_hoodie,
                    variant=var_hoodie,
                    sku=var_hoodie.sku,
                    product_name=prod_hoodie.name,
                    quantity=1,
                    fulfilled_quantity=0,
                    unit_price=Decimal("85.00"),
                    unit_discount=Decimal("0.00"),
                    status="routing",
                )
            if created:
                order_processing.recalculate_totals()

            order_delivered, created_del = EcommerceOrder.objects.get_or_create(
                tenant=tenant,
                shipping_name="Marcus Vance",
                shipping_address_line1="456 Michigan Ave",
                defaults={
                    "customer": order_cust,
                    "guest_email": "marcus.vance@example.com",
                    "currency": usd,
                    "status": "fulfilled",
                    "payment_status": "captured",
                    "fulfillment_status": "fulfilled",
                    "fraud_risk_level": "low",
                    "fraud_score": 5,
                    "address_verification_status": "passed",
                    "inventory_reservation_status": "allocated",
                    "shipping_city": "Chicago",
                    "shipping_state": "IL",
                    "shipping_postal_code": "60611",
                    "shipping_country": "US",
                    "billing_name": "Marcus Vance",
                    "billing_address_line1": "456 Michigan Ave",
                    "billing_city": "Chicago",
                    "billing_state": "IL",
                    "billing_postal_code": "60611",
                    "billing_country": "US",
                    "shipping_amount": Decimal("9.99"),
                    "tax_amount": Decimal("6.40"),
                },
            )
            if created_del and prod_tshirt and var_tshirt_m:
                EcommerceOrderLine.objects.create(
                    tenant=tenant,
                    order=order_delivered,
                    product=prod_tshirt,
                    variant=var_tshirt_m,
                    sku=var_tshirt_m.sku,
                    product_name=prod_tshirt.name,
                    quantity=2,
                    fulfilled_quantity=2,
                    unit_price=Decimal("38.00"),
                    status="fulfilled",
                )
                order_delivered.recalculate_totals()

            # 3. Fulfillments
            if order_processing:
                OrderFulfillment.objects.get_or_create(
                    tenant=tenant,
                    order=order_processing,
                    carrier_name="FedEx Ground",
                    defaults={
                        "fulfillment_center": fc_chi,
                        "tracking_number": "781299887766",
                        "tracking_url": "https://www.fedex.com/fedextrack/?trknbr=781299887766",
                        "status": "in_transit",
                        "shipping_cost": Decimal("11.80"),
                        "shipped_at": now - timedelta(hours=6),
                        "estimated_delivery_date": (now + timedelta(days=2)).date(),
                        "notification_sent": True,
                        "notes": "Package 1 of 2 for partial order fulfillment.",
                    },
                )

            if order_delivered:
                OrderFulfillment.objects.get_or_create(
                    tenant=tenant,
                    order=order_delivered,
                    carrier_name="UPS Express",
                    defaults={
                        "fulfillment_center": fc_chi,
                        "tracking_number": "1Z999AA10123456784",
                        "tracking_url": "https://www.ups.com/track?tracknum=1Z999AA10123456784",
                        "status": "delivered",
                        "shipping_cost": Decimal("14.50"),
                        "shipped_at": now - timedelta(days=3),
                        "estimated_delivery_date": (now - timedelta(days=1)).date(),
                        "actual_delivery_date": (now - timedelta(days=1)).date(),
                        "notification_sent": True,
                        "notes": "Delivered and signed at front porch.",
                    },
                )

                # 4. Returns & Exchanges (RMA)
                ReturnMerchandiseAuthorization.objects.get_or_create(
                    tenant=tenant,
                    order=order_delivered,
                    customer=order_cust,
                    defaults={
                        "return_type": "refund",
                        "status": "authorized",
                        "reason": "size_fit_issue",
                        "return_tracking_number": "1Z999RETURN8877665",
                        "return_shipping_label_url": "https://labels.example.com/rma/ERMA-00001.pdf",
                        "restocking_fee": Decimal("5.00"),
                        "refund_amount": Decimal("38.00"),
                        "refund_status": "pending",
                        "restocking_status": "pending",
                        "restocking_center": fc_chi,
                        "customer_notes": "Fit was slightly too snug, requesting standard return.",
                        "inspection_notes": "Pending receipt at Chicago facility.",
                        "authorized_at": now - timedelta(hours=4),
                    },
                )

        # -------------------------------------------------------------
        # 9.6 Customer Account & Profile
        # -------------------------------------------------------------
        if cust_party:
            usd_curr = Currency.objects.filter(code="USD").first()
            User = get_user_model()
            user_account = User.objects.filter(tenant=tenant).first()

            # 1. Customer Profiles
            CustomerAccountProfile.objects.get_or_create(
                tenant=tenant,
                customer=cust_party,
                defaults={
                    "user": user_account,
                    "tier": "gold",
                    "status": "active",
                    "auth_mode": "password",
                    "phone_number": "+1 (312) 555-0142",
                    "phone_verified": True,
                    "preferred_currency": usd_curr,
                    "preferred_language": "en",
                    "email_marketing_opt_in": True,
                    "sms_marketing_opt_in": True,
                    "notification_frequency": "weekly_digest",
                    "total_spent": Decimal("485.50"),
                    "order_count": 4,
                    "last_order_at": now - timedelta(days=2),
                    "internal_notes": "Valued enterprise VIP client; prefers morning deliveries.",
                },
            )

            # 2. Customer Address Preferences
            pref_addr = Address.objects.filter(tenant=tenant, party=cust_party).first()
            if not pref_addr:
                pref_addr = Address.objects.create(
                    tenant=tenant,
                    party=cust_party,
                    kind="shipping",
                    line1="742 Evergreen Terrace",
                    city="Springfield",
                    country="United States",
                )

            CustomerAddressPreference.objects.get_or_create(
                tenant=tenant,
                customer=cust_party,
                label="Primary Residence",
                defaults={
                    "address": pref_addr,
                    "is_default_shipping": True,
                    "is_default_billing": True,
                    "recipient_name": cust_party.name,
                    "contact_phone": "+1 (312) 555-0142",
                    "delivery_instructions": "Gate code #4092. Leave behind porch planter box.",
                    "preferred_delivery_window": "morning",
                    "requires_signature": False,
                },
            )

            # 3. Wishlists & Items
            wishlist_demo, _ = CustomerWishlist.objects.get_or_create(
                tenant=tenant,
                customer=cust_party,
                name="Winter Tech & Apparel Favorites",
                defaults={
                    "slug": "winter-tech-apparel-favorites",
                    "visibility": "shared",
                    "is_default": True,
                    "notes": "Curated selection for holiday wardrobe upgrades.",
                },
            )

            sample_prod = CatalogProduct.objects.filter(tenant=tenant).first()
            if sample_prod:
                CustomerWishlistItem.objects.get_or_create(
                    tenant=tenant,
                    wishlist=wishlist_demo,
                    product=sample_prod,
                    defaults={
                        "desired_quantity": 2,
                        "priority": "high",
                        "comment": "Prefer navy or dark slate colorway.",
                    },
                )

            # 4. Privacy & GDPR Requests
            CustomerPrivacyRequest.objects.get_or_create(
                tenant=tenant,
                customer=cust_party,
                request_type="access_export",
                defaults={
                    "status": "completed",
                    "statutory_deadline": (now + timedelta(days=25)).date(),
                    "completed_at": now - timedelta(days=1),
                    "requested_by_email": "privacy.officer@acme.example.com",
                    "verification_method": "account_login",
                    "data_export_payload": {
                        "customer": cust_party.name,
                        "tier": "gold",
                        "orders_count": 4,
                        "verified": True,
                    },
                    "resolution_notes": "Statutory GDPR portability export package compiled and delivered via secure portal.",
                },
            )

        # -------------------------------------------------------------
        # 9.7 Search & Product Discovery Seeding
        # -------------------------------------------------------------
        sample_prod = CatalogProduct.objects.filter(tenant=tenant).first()
        sample_cat = StoreCategory.objects.filter(tenant=tenant).first()

        # 1. Search Synonyms
        SearchSynonym.objects.get_or_create(
            tenant=tenant,
            root_term="sneakers",
            defaults={
                "name": "Footwear & Running Shoes",
                "synonym_type": "two_way",
                "synonyms": "trainers, running shoes, kicks, athletic footwear",
                "is_active": True,
                "hit_count": 142,
                "notes": "Standard omnichannel footwear equivalence rule.",
            },
        )
        SearchSynonym.objects.get_or_create(
            tenant=tenant,
            root_term="audio",
            defaults={
                "name": "Home Audio & Sound Devices",
                "synonym_type": "one_way",
                "synonyms": "headphones, soundbar, speakers, wireless earbuds",
                "is_active": True,
                "hit_count": 89,
                "notes": "Directional expansion from generic audio keyword.",
            },
        )
        SearchSynonym.objects.get_or_create(
            tenant=tenant,
            root_term="sammsung",
            defaults={
                "name": "Samsung Typo Correction",
                "synonym_type": "replacement",
                "synonyms": "samsung",
                "is_active": True,
                "hit_count": 31,
                "notes": "Explicit replacement for common brand misspelling.",
            },
        )

        # 2. Search Facet Configurations
        SearchFacetConfig.objects.get_or_create(
            tenant=tenant,
            code="brand",
            category_scope=None,
            defaults={
                "name": "Brand",
                "source_type": "brand",
                "widget_type": "checkbox",
                "filter_logic": "disjunctive",
                "display_order": 1,
                "is_searchable": True,
                "max_values_shown": 10,
                "is_active": True,
            },
        )
        SearchFacetConfig.objects.get_or_create(
            tenant=tenant,
            code="category",
            category_scope=None,
            defaults={
                "name": "Category Hierarchy",
                "source_type": "category",
                "widget_type": "checkbox",
                "filter_logic": "disjunctive",
                "display_order": 2,
                "is_searchable": False,
                "max_values_shown": 10,
                "is_active": True,
            },
        )
        SearchFacetConfig.objects.get_or_create(
            tenant=tenant,
            code="price",
            category_scope=None,
            defaults={
                "name": "Price Range",
                "source_type": "price",
                "widget_type": "price_slider",
                "filter_logic": "conjunctive",
                "display_order": 3,
                "is_searchable": False,
                "max_values_shown": 5,
                "is_active": True,
            },
        )
        SearchFacetConfig.objects.get_or_create(
            tenant=tenant,
            code="in_stock",
            category_scope=None,
            defaults={
                "name": "Availability",
                "source_type": "availability",
                "widget_type": "toggle",
                "filter_logic": "conjunctive",
                "display_order": 4,
                "is_searchable": False,
                "max_values_shown": 2,
                "is_active": True,
            },
        )
        SearchFacetConfig.objects.get_or_create(
            tenant=tenant,
            code="size",
            category_scope=None,
            defaults={
                "name": "Apparel Size",
                "source_type": "variant_option",
                "option_key": "Size",
                "widget_type": "checkbox",
                "filter_logic": "disjunctive",
                "display_order": 5,
                "is_searchable": False,
                "max_values_shown": 8,
                "is_active": True,
            },
        )

        # 3. Search Merchandising Rules
        if sample_prod:
            SearchMerchandisingRule.objects.get_or_create(
                tenant=tenant,
                name="Pin Hero Sneaker on Footwear Query",
                defaults={
                    "rule_type": "query",
                    "trigger_query": "sneakers",
                    "match_type": "contains",
                    "action_type": "pin",
                    "boosted_product": sample_prod,
                    "pin_position": 1,
                    "priority": 50,
                    "is_active": True,
                },
            )
            SearchMerchandisingRule.objects.get_or_create(
                tenant=tenant,
                name="Score Boost for Performance Running",
                defaults={
                    "rule_type": "query",
                    "trigger_query": "running",
                    "match_type": "contains",
                    "action_type": "boost",
                    "boosted_product": sample_prod,
                    "boost_weight": 25,
                    "priority": 30,
                    "is_active": True,
                },
            )

        SearchMerchandisingRule.objects.get_or_create(
            tenant=tenant,
            name="Redirect Customer Service Search to FAQ",
            defaults={
                "rule_type": "query",
                "trigger_query": "customer service",
                "match_type": "exact",
                "action_type": "redirect",
                "redirect_url": "/help/faq/",
                "priority": 40,
                "is_active": True,
            },
        )
        SearchMerchandisingRule.objects.get_or_create(
            tenant=tenant,
            name="Seasonal Spring Sale In-Grid Banner",
            defaults={
                "rule_type": "query",
                "trigger_query": "sale",
                "match_type": "contains",
                "action_type": "banner",
                "banner_title": "Spring Sale: Extra 20% Off at Checkout",
                "banner_body": "Use promotional discount code SPRING20 on all eligible footwear & apparel.",
                "banner_link_url": "/catalog/promotions/",
                "priority": 20,
                "is_active": True,
            },
        )

        # 4. Search Query Logs
        query_demos = [
            ("sneakers", 12, False, 18, {"category": "1"}),
            ("running shoes", 8, False, 22, {}),
            ("wireless noise cancelling headphones", 4, False, 31, {"brand": "Sony"}),
            ("sammsung galaxy phone", 6, False, 15, {}),
            ("qwerty non-existent product xyz", 0, True, 11, {}),
            ("winter warm down parka jacket", 3, False, 24, {}),
            ("clearance sale items", 15, False, 20, {}),
            ("unknown antique mechanical clockwork", 0, True, 9, {}),
        ]
        for q_text, r_count, is_zr, lat, flts in query_demos:
            if not SearchQueryLog.objects.filter(tenant=tenant, query_text=q_text).exists():
                SearchQueryLog.objects.create(
                    tenant=tenant,
                    query_text=q_text,
                    normalized_query=q_text.lower(),
                    results_count=r_count,
                    is_zero_result=is_zr,
                    execution_time_ms=lat,
                    applied_filters=flts,
                    sort_order="relevance",
                    clicked_product=sample_prod if (not is_zr and sample_prod) else None,
                    click_position=1 if (not is_zr and sample_prod) else None,
                    session_key="demo_session_analytics_key",
                )

        # =========================================================================
        # 9.8 Personalization & Recommendation Engine
        # =========================================================================
        apparel_cat = StoreCategory.objects.filter(tenant=tenant, slug="apparel-fashion").first() or StoreCategory.objects.filter(tenant=tenant).first()
        electronics_cat = StoreCategory.objects.filter(tenant=tenant, slug="electronics").first() or apparel_cat

        # 1. Audience Segments
        vip_segment, _ = AudienceSegment.objects.get_or_create(
            tenant=tenant,
            code="vip-champions",
            defaults={
                "name": "VIP Champions & High-Value Buyers",
                "lifecycle_stage": "high_value_vip",
                "min_order_count": 3,
                "min_lifetime_spend": Decimal("500.00"),
                "cached_member_count": 4,
                "last_evaluated_at": timezone.now(),
                "is_active": True,
                "description": "High-value shoppers with multiple orders and >$500 lifetime spend.",
            },
        )

        repeat_segment, _ = AudienceSegment.objects.get_or_create(
            tenant=tenant,
            code="active-repeat",
            defaults={
                "name": "Active Repeat Customers",
                "lifecycle_stage": "active_repeat",
                "recency_days_max": 30,
                "min_order_count": 2,
                "min_lifetime_spend": Decimal("100.00"),
                "cached_member_count": 7,
                "last_evaluated_at": timezone.now(),
                "is_active": True,
                "description": "Engaged shoppers purchasing within the past 30 days.",
            },
        )

        at_risk_segment, _ = AudienceSegment.objects.get_or_create(
            tenant=tenant,
            code="at-risk-lapsed",
            defaults={
                "name": "At-Risk Lapsed Shoppers",
                "lifecycle_stage": "at_risk",
                "recency_days_max": 90,
                "min_order_count": 1,
                "min_lifetime_spend": Decimal("0.00"),
                "cached_member_count": 3,
                "last_evaluated_at": timezone.now(),
                "is_active": True,
                "description": "Shoppers with past orders who have not purchased in over 90 days.",
            },
        )

        apparel_segment, _ = AudienceSegment.objects.get_or_create(
            tenant=tenant,
            code="apparel-enthusiasts",
            defaults={
                "name": "Apparel & Fashion Enthusiasts",
                "lifecycle_stage": "all",
                "target_category": apparel_cat,
                "cached_member_count": 5,
                "last_evaluated_at": timezone.now(),
                "is_active": True,
                "description": "Shoppers demonstrating strong affinity for the Apparel & Fashion category.",
            },
        )

        # 2. Recommendation Strategies
        rec_pdp, _ = RecommendationStrategy.objects.get_or_create(
            tenant=tenant,
            code="pdp-similar",
            defaults={
                "name": "PDP Related & Similar Items",
                "algorithm": "related_products",
                "placement": "pdp_related",
                "fallback_strategy": "trending_popular",
                "max_items": 6,
                "min_rating": Decimal("3.50"),
                "same_brand_only": False,
                "only_in_stock": True,
                "is_active": True,
                "description": "Recommends similar category items on product detail pages.",
            },
        )

        rec_cart, _ = RecommendationStrategy.objects.get_or_create(
            tenant=tenant,
            code="cart-fbt",
            defaults={
                "name": "Cart Frequently Bought Together",
                "algorithm": "frequently_bought_together",
                "placement": "cart_cross_sell",
                "fallback_strategy": "trending_popular",
                "max_items": 4,
                "only_in_stock": True,
                "is_active": True,
                "description": "Association co-occurrence upsell items in checkout drawer.",
            },
        )

        rec_home, _ = RecommendationStrategy.objects.get_or_create(
            tenant=tenant,
            code="home-trending",
            defaults={
                "name": "Homepage Trending & Popular Feed",
                "algorithm": "trending_popular",
                "placement": "homepage_feed",
                "fallback_strategy": "new_arrivals",
                "max_items": 8,
                "only_in_stock": True,
                "is_active": True,
                "description": "Showcases high-velocity trending items across the catalog.",
            },
        )

        # 3. Personalized Experiences
        PersonalizedExperience.objects.get_or_create(
            tenant=tenant,
            name="VIP Winter Early Access Hero",
            defaults={
                "experience_type": "home_hero",
                "target_segment": vip_segment,
                "target_category": apparel_cat,
                "headline": "VIP Exclusive: Early Access Winter Collection",
                "subheadline": "Enjoy private access and an automatic 20% loyalty reward at checkout.",
                "cta_label": "Shop VIP Collection",
                "cta_url": "/ecommerce/catalog/",
                "priority": 25,
                "is_active": True,
                "impression_count": 142,
                "click_count": 38,
                "conversion_count": 12,
            },
        )

        PersonalizedExperience.objects.get_or_create(
            tenant=tenant,
            name="1-Hour Cart Abandonment Recovery Trigger",
            defaults={
                "experience_type": "cart_abandonment",
                "target_segment": repeat_segment,
                "target_product": sample_prod,
                "headline": "Did you forget something in your cart?",
                "subheadline": "Your items are waiting for you. Complete your order before items sell out.",
                "cta_label": "Return to Cart",
                "cta_url": "/ecommerce/cart/",
                "trigger_delay_hours": 1,
                "priority": 15,
                "is_active": True,
                "impression_count": 89,
                "click_count": 27,
                "conversion_count": 9,
            },
        )

        PersonalizedExperience.objects.get_or_create(
            tenant=tenant,
            name="Lapsed Customer Win-Back Campaign",
            defaults={
                "experience_type": "win_back",
                "target_segment": at_risk_segment,
                "headline": "We miss you! Take $15 off your next order",
                "subheadline": "Explore new arrivals with code WELCOMEBACK15.",
                "cta_label": "Claim Your $15 Voucher",
                "cta_url": "/ecommerce/catalog/",
                "trigger_delay_hours": 24,
                "priority": 10,
                "is_active": True,
                "impression_count": 64,
                "click_count": 14,
                "conversion_count": 4,
            },
        )

        # 4. Behavioral Clickstream Events
        customer_profile = CustomerAccountProfile.objects.filter(tenant=tenant).first()
        behavior_events_data = [
            ("page_view", "session_user_alpha", sample_prod, apparel_cat, 1),
            ("product_view", "session_user_alpha", sample_prod, apparel_cat, 2),
            ("category_view", "session_user_alpha", None, apparel_cat, 1),
            ("cart_add", "session_user_alpha", sample_prod, apparel_cat, 5),
            ("search_query", "session_user_alpha", None, None, 1),
            ("page_view", "session_user_beta", None, electronics_cat, 1),
            ("product_view", "session_user_beta", sample_prod, electronics_cat, 2),
            ("checkout_start", "session_user_beta", sample_prod, None, 7),
            ("order_purchase", "session_user_beta", sample_prod, apparel_cat, 10),
            ("wishlist_add", "session_user_gamma", sample_prod, apparel_cat, 3),
        ]
        for ev_type, sess_k, prd, cat, score in behavior_events_data:
            if not ShopperBehaviorEvent.objects.filter(
                tenant=tenant, session_key=sess_k, event_type=ev_type, product=prd
            ).exists():
                ShopperBehaviorEvent.objects.create(
                    tenant=tenant,
                    session_key=sess_k,
                    event_type=ev_type,
                    customer_profile=customer_profile,
                    product=prd,
                    category=cat,
                    intent_score_delta=score,
                    referrer_url="https://store.example.com/",
                    payload_json={"source": "demo_seed"},
                )

        # -------------------------------------------------------------
        # 9.12 Subscription & Recurring Commerce Seed Data
        # -------------------------------------------------------------
        catalog_sample_product = CatalogProduct.objects.filter(tenant=tenant).first()
        product_sample_variant = ProductVariant.objects.filter(tenant=tenant).first()

        plan_coffee, _ = SubscriptionPlan.objects.get_or_create(
            tenant=tenant,
            code="roasters-monthly-coffee",
            defaults={
                "name": "Roaster's Choice Monthly Coffee Club",
                "plan_type": "subscribe_save",
                "frequency": "monthly",
                "interval_count": 1,
                "discount_type": "percentage",
                "discount_value": Decimal("15.00"),
                "trial_period_days": 0,
                "min_commitment_cycles": 2,
                "allow_pause": True,
                "allow_skip": True,
                "allow_swap": True,
                "max_pause_days": 90,
                "target_product": catalog_sample_product,
                "is_active": True,
                "description": "Artisan fresh-roasted single-origin coffees delivered to your doorstep every month with 15% subscriber savings.",
            },
        )

        plan_box, _ = SubscriptionPlan.objects.get_or_create(
            tenant=tenant,
            code="quarterly-artisan-box",
            defaults={
                "name": "Quarterly Gourmet Discovery Box",
                "plan_type": "curated_box",
                "frequency": "quarterly",
                "interval_count": 1,
                "discount_type": "percentage",
                "discount_value": Decimal("10.00"),
                "trial_period_days": 0,
                "min_commitment_cycles": 1,
                "allow_pause": True,
                "allow_skip": True,
                "allow_swap": True,
                "max_pause_days": 90,
                "target_product": catalog_sample_product,
                "is_active": True,
                "description": "Themed culinary and lifestyle discovery boxes curated by master artisans every season.",
            },
        )

        plan_vip, _ = SubscriptionPlan.objects.get_or_create(
            tenant=tenant,
            code="annual-vip-pass",
            defaults={
                "name": "Annual VIP Executive Membership Pass",
                "plan_type": "membership_club",
                "frequency": "annual",
                "interval_count": 1,
                "discount_type": "percentage",
                "discount_value": Decimal("20.00"),
                "trial_period_days": 14,
                "min_commitment_cycles": 1,
                "allow_pause": False,
                "allow_skip": False,
                "allow_swap": False,
                "max_pause_days": 30,
                "target_product": catalog_sample_product,
                "is_active": True,
                "description": "Exclusive member club pass with 20% off all catalog items, free expedited shipping, and VIP support.",
            },
        )

        if customer_profile and catalog_sample_product:
            sub_active, _ = CustomerSubscription.objects.get_or_create(
                tenant=tenant,
                customer_profile=customer_profile,
                plan=plan_coffee,
                defaults={
                    "product": catalog_sample_product,
                    "variant": product_sample_variant,
                    "status": "active",
                    "quantity": 2,
                    "unit_price": Decimal("24.00"),
                    "recurring_discount_pct": Decimal("15.00"),
                    "started_at": timezone.now() - timedelta(days=60),
                    "next_billing_date": (timezone.now() + timedelta(days=12)).date(),
                    "next_delivery_date": (timezone.now() + timedelta(days=15)).date(),
                    "completed_cycles_count": 2,
                    "consecutive_successful_cycles": 2,
                    "failed_payment_count": 0,
                    "shipping_address_line": "123 Market St, Suite 400, San Francisco, CA 94105",
                    "payment_method_ref": "tok_visa_4242_ending_1234",
                },
            )

            sub_paused, _ = CustomerSubscription.objects.get_or_create(
                tenant=tenant,
                customer_profile=customer_profile,
                plan=plan_box,
                defaults={
                    "product": catalog_sample_product,
                    "variant": product_sample_variant,
                    "status": "paused",
                    "quantity": 1,
                    "unit_price": Decimal("65.00"),
                    "recurring_discount_pct": Decimal("10.00"),
                    "started_at": timezone.now() - timedelta(days=120),
                    "next_billing_date": (timezone.now() + timedelta(days=45)).date(),
                    "paused_until": (timezone.now() + timedelta(days=40)).date(),
                    "completed_cycles_count": 1,
                    "consecutive_successful_cycles": 1,
                    "failed_payment_count": 0,
                    "shipping_address_line": "123 Market St, Suite 400, San Francisco, CA 94105",
                    "payment_method_ref": "tok_mastercard_5555",
                },
            )

            # Box curations
            SubscriptionBoxCuration.objects.get_or_create(
                tenant=tenant,
                plan=plan_box,
                cycle_identifier="2026-11",
                defaults={
                    "name": "Autumn Harvest Artisan Roast Curation",
                    "code": "autumn-harvest-2026-11",
                    "theme_title": "Fireside Warmth & Spiced Notes",
                    "curation_notes": "Featuring high-altitude Ethiopian Yirgacheffe and micro-batch maple glazed walnuts.",
                    "primary_product": catalog_sample_product,
                    "has_surprise_item": True,
                    "surprise_item_description": "Limited Edition Copper Coffee Scoop",
                    "preference_tag": "Medium-Dark Roast",
                    "start_date": timezone.now().date() - timedelta(days=15),
                    "end_date": timezone.now().date() + timedelta(days=45),
                    "is_active": True,
                },
            )

            SubscriptionBoxCuration.objects.get_or_create(
                tenant=tenant,
                plan=plan_box,
                cycle_identifier="2026-12",
                defaults={
                    "name": "Holiday Reserve Winter Collection",
                    "code": "holiday-reserve-2026-12",
                    "theme_title": "Winter Solstice Elegance",
                    "curation_notes": "A celebratory compilation of holiday reserve blends and cocoa dusted espresso truffles.",
                    "primary_product": catalog_sample_product,
                    "has_surprise_item": True,
                    "surprise_item_description": "Handcrafted Ceramic Tasting Cup",
                    "preference_tag": "Holiday Blend",
                    "start_date": timezone.now().date() + timedelta(days=46),
                    "end_date": timezone.now().date() + timedelta(days=105),
                    "is_active": True,
                },
            )

            # Retention actions
            if not SubscriptionRetentionAction.objects.filter(tenant=tenant, subscription=sub_active).exists():
                SubscriptionRetentionAction.objects.create(
                    tenant=tenant,
                    subscription=sub_active,
                    customer_profile=customer_profile,
                    trigger_type="cancel_intent",
                    cancellation_reason="too_much_product",
                    churn_risk_score=Decimal("45.50"),
                    offered_action="free_skip",
                    offer_discount_pct=Decimal("0.00"),
                    outcome="deflected",
                    notes="Customer had surplus inventory; accepted 1-cycle skip offer and retained subscription.",
                )

        # ------------------------------------------------------------------
        # 9.11 Marketplace & Multi-Vendor
        # ------------------------------------------------------------------
        # 1. Vendor Legal Parties
        vendor_party_1, _ = Party.objects.get_or_create(
            tenant=tenant,
            name="Apex Audio & Electronics LLC",
            defaults={"party_type": "organization"},
        )
        vendor_party_2, _ = Party.objects.get_or_create(
            tenant=tenant,
            name="Artisan Woods & Leather Co",
            defaults={"party_type": "organization"},
        )
        vendor_party_3, _ = Party.objects.get_or_create(
            tenant=tenant,
            name="Nordic Living Design Studio",
            defaults={"party_type": "organization"},
        )
        vendor_party_4, _ = Party.objects.get_or_create(
            tenant=tenant,
            name="Summit Peak Mountain Gear",
            defaults={"party_type": "organization"},
        )

        # 2. Marketplace Vendors
        v_apex, _ = MarketplaceVendor.objects.get_or_create(
            tenant=tenant,
            slug="apex-audio-direct",
            defaults={
                "party": vendor_party_1,
                "store_name": "Apex Audio Direct",
                "headline": "High-Fidelity Audio Gear & Studio Electronics",
                "description": "Authorized marketplace seller for studio monitoring headphones, audio interfaces, and digital acoustic accessories.",
                "support_email": "support@apexaudio.com",
                "support_phone": "+1 555-0144",
                "status": "active",
                "kyc_status": "verified",
                "kyc_document_type": "State Certificate of Incorporation",
                "kyc_verified_at": timezone.now() - timedelta(days=60),
                "commission_type": "percentage",
                "commission_rate": Decimal("12.00"),
                "fixed_fee_per_order": Decimal("1.50"),
                "payout_method": "stripe_connect",
                "payout_account_identifier": "acct_1N7ApexAudioMarket",
                "min_payout_amount": Decimal("50.00"),
                "tax_id": "EIN-88-2940112",
                "tax_form_status": "1099_eligible",
                "shipping_lead_time_days": 1,
                "rating_average": Decimal("4.85"),
                "rating_count": 34,
                "is_featured": True,
            },
        )

        v_artisan, _ = MarketplaceVendor.objects.get_or_create(
            tenant=tenant,
            slug="artisan-craft-collective",
            defaults={
                "party": vendor_party_2,
                "store_name": "Artisan Craft Collective",
                "headline": "Hand-Turned Hardwood Furniture & Heritage Leather Goods",
                "description": "Master crafters specializing in heirloom walnut desks, leather travel bags, and custom lifestyle accessories.",
                "support_email": "guild@artisancraft.org",
                "support_phone": "+1 555-0188",
                "status": "active",
                "kyc_status": "verified",
                "kyc_document_type": "Master Guild Artisan License",
                "kyc_verified_at": timezone.now() - timedelta(days=90),
                "commission_type": "percentage",
                "commission_rate": Decimal("15.00"),
                "payout_method": "bank_transfer",
                "payout_account_identifier": "US8800019283749283",
                "min_payout_amount": Decimal("100.00"),
                "tax_id": "EIN-34-9102938",
                "tax_form_status": "w9_received",
                "shipping_lead_time_days": 3,
                "rating_average": Decimal("4.70"),
                "rating_count": 18,
                "is_featured": True,
            },
        )

        v_nordic, _ = MarketplaceVendor.objects.get_or_create(
            tenant=tenant,
            slug="nordic-living-goods",
            defaults={
                "party": vendor_party_3,
                "store_name": "Nordic Living Design",
                "headline": "Minimalist Ceramic Homeware & Scandinavian Design",
                "description": "Clean lines, sustainable clay, and functional Scandinavian interior accents.",
                "support_email": "hello@nordicliving.se",
                "status": "under_review",
                "kyc_status": "pending",
                "kyc_document_type": "Swedish Org Registration & Passport",
                "commission_type": "percentage",
                "commission_rate": Decimal("14.00"),
                "payout_method": "paypal",
                "payout_account_identifier": "disburse@nordicliving.se",
                "min_payout_amount": Decimal("50.00"),
                "tax_form_status": "w8ben_received",
                "shipping_lead_time_days": 2,
                "rating_average": Decimal("0.00"),
                "rating_count": 0,
            },
        )

        v_summit, _ = MarketplaceVendor.objects.get_or_create(
            tenant=tenant,
            slug="summit-peak-supply",
            defaults={
                "party": vendor_party_4,
                "store_name": "Summit Peak Supply",
                "headline": "Alpine Climbing Gear & Outdoor Expeditions",
                "description": "Technical mountain hardware and all-weather trekking equipment.",
                "support_email": "support@summitpeak.co",
                "status": "suspended",
                "kyc_status": "verified",
                "commission_type": "combined",
                "commission_rate": Decimal("15.00"),
                "fixed_fee_per_order": Decimal("2.00"),
                "payout_method": "bank_transfer",
                "suspension_reason": "Multiple late dispatch SLA breaches and unresolved customer item-damaged claims.",
                "suspended_at": timezone.now() - timedelta(days=2),
                "rating_average": Decimal("2.80"),
                "rating_count": 12,
            },
        )

        # 3. Product Listings
        prod_sample = CatalogProduct.objects.filter(tenant=tenant).first()
        prod_secondary = CatalogProduct.objects.filter(tenant=tenant).exclude(pk=getattr(prod_sample, "pk", None)).first() or prod_sample

        if prod_sample:
            VendorProductListing.objects.get_or_create(
                tenant=tenant,
                vendor=v_apex,
                seller_sku="APX-AUD-PRO-01",
                defaults={
                    "product": prod_sample,
                    "condition": "new",
                    "asking_price": Decimal("189.99"),
                    "compare_at_price": Decimal("229.99"),
                    "cost_price": Decimal("120.00"),
                    "available_quantity": 42,
                    "low_stock_threshold": 8,
                    "lead_time_days": 1,
                    "moderation_status": "approved",
                    "compliance_status": "compliant",
                    "is_active": True,
                    "submitted_at": timezone.now() - timedelta(days=20),
                    "reviewed_at": timezone.now() - timedelta(days=19),
                },
            )
            VendorProductListing.objects.get_or_create(
                tenant=tenant,
                vendor=v_apex,
                seller_sku="APX-AUD-REF-02",
                defaults={
                    "product": prod_sample,
                    "condition": "refurbished",
                    "condition_notes": "Factory recertified with genuine replacement foam pads and 90-day warranty.",
                    "asking_price": Decimal("139.99"),
                    "compare_at_price": Decimal("189.99"),
                    "cost_price": Decimal("85.00"),
                    "available_quantity": 6,
                    "low_stock_threshold": 3,
                    "lead_time_days": 2,
                    "moderation_status": "approved",
                    "compliance_status": "compliant",
                    "is_active": True,
                    "submitted_at": timezone.now() - timedelta(days=15),
                    "reviewed_at": timezone.now() - timedelta(days=14),
                },
            )

        if prod_secondary:
            VendorProductListing.objects.get_or_create(
                tenant=tenant,
                vendor=v_artisan,
                seller_sku="ART-OAK-HERITAGE",
                defaults={
                    "product": prod_secondary,
                    "condition": "new",
                    "condition_notes": "Sustainably harvested white oak with natural beeswax polish.",
                    "asking_price": Decimal("340.00"),
                    "compare_at_price": Decimal("420.00"),
                    "cost_price": Decimal("210.00"),
                    "available_quantity": 14,
                    "low_stock_threshold": 4,
                    "lead_time_days": 3,
                    "moderation_status": "approved",
                    "compliance_status": "compliant",
                    "is_active": True,
                    "submitted_at": timezone.now() - timedelta(days=30),
                    "reviewed_at": timezone.now() - timedelta(days=29),
                },
            )
            VendorProductListing.objects.get_or_create(
                tenant=tenant,
                vendor=v_nordic,
                seller_sku="NOR-CERAMIC-VASE",
                defaults={
                    "product": prod_secondary,
                    "condition": "new",
                    "asking_price": Decimal("48.00"),
                    "available_quantity": 25,
                    "low_stock_threshold": 5,
                    "lead_time_days": 2,
                    "moderation_status": "pending_review",
                    "compliance_status": "pending",
                    "moderator_notes": "Awaiting merchant proof of safe transit drop-testing.",
                    "is_active": True,
                    "submitted_at": timezone.now() - timedelta(days=1),
                },
            )

        # 4. Vendor Sub-Orders
        parent_order = EcommerceOrder.objects.filter(tenant=tenant).first()
        if parent_order:
            so1, _ = VendorSubOrder.objects.get_or_create(
                tenant=tenant,
                vendor=v_apex,
                order=parent_order,
                defaults={
                    "fulfillment_status": "delivered",
                    "sla_status": "on_time",
                    "payout_status": "paid",
                    "subtotal_amount": Decimal("189.99"),
                    "shipping_amount": Decimal("9.99"),
                    "commission_rate": Decimal("12.00"),
                    "carrier_name": "FedEx Ground",
                    "tracking_number": "781299401122",
                    "promised_dispatch_date": timezone.localdate() - timedelta(days=12),
                    "dispatched_at": timezone.now() - timedelta(days=12),
                    "delivered_at": timezone.now() - timedelta(days=9),
                    "customer_rating": 5,
                    "customer_feedback": "Fastest shipping ever! Sound quality on these studio headphones is unbelievable.",
                    "seller_response": "Thank you for supporting Apex Audio Direct! Enjoy the studio sessions.",
                    "rated_at": timezone.now() - timedelta(days=8),
                },
            )
            so2, _ = VendorSubOrder.objects.get_or_create(
                tenant=tenant,
                vendor=v_artisan,
                order=parent_order,
                defaults={
                    "fulfillment_status": "shipped",
                    "sla_status": "on_time",
                    "payout_status": "accrued",
                    "subtotal_amount": Decimal("340.00"),
                    "shipping_amount": Decimal("24.00"),
                    "commission_rate": Decimal("15.00"),
                    "carrier_name": "UPS Freight",
                    "tracking_number": "1Z88291029381",
                    "promised_dispatch_date": timezone.localdate() - timedelta(days=2),
                    "dispatched_at": timezone.now() - timedelta(days=2),
                },
            )
            so3, _ = VendorSubOrder.objects.get_or_create(
                tenant=tenant,
                vendor=v_summit,
                order=parent_order,
                defaults={
                    "fulfillment_status": "unfulfilled",
                    "sla_status": "breached",
                    "payout_status": "withheld_dispute",
                    "subtotal_amount": Decimal("110.00"),
                    "shipping_amount": Decimal("12.00"),
                    "commission_rate": Decimal("15.00"),
                    "promised_dispatch_date": timezone.localdate() - timedelta(days=4),
                    "dispute_status": "disputed",
                    "dispute_reason": "Order unfulfilled after 5 business days past SLA promise",
                    "dispute_notes": "Customer opened dispute requesting immediate cancellation or priority dispatch.",
                },
            )

            # 5. Vendor Payouts
            payout_1, _ = VendorPayout.objects.get_or_create(
                tenant=tenant,
                vendor=v_apex,
                period_start=timezone.localdate() - timedelta(days=30),
                period_end=timezone.localdate() - timedelta(days=15),
                defaults={
                    "gross_sales_amount": Decimal("189.99"),
                    "commission_deducted": Decimal("24.30"),
                    "fees_deducted": Decimal("5.50"),
                    "refunds_deducted": Decimal("0.00"),
                    "tax_withholding_amount": Decimal("0.00"),
                    "payout_method": "stripe_connect",
                    "payout_status": "completed",
                    "reference_code": "tr_1N7ApexAudioDisb988",
                    "tax_year": 2026,
                    "is_1099_reported": True,
                    "notes": "Automated bi-weekly settlement disbursement executed via Stripe Connect.",
                    "processed_at": timezone.now() - timedelta(days=14),
                },
            )
            if so1.payout_id is None:
                so1.payout = payout_1
                so1.save(update_fields=["payout"])

            payout_2, _ = VendorPayout.objects.get_or_create(
                tenant=tenant,
                vendor=v_artisan,
                period_start=timezone.localdate() - timedelta(days=14),
                period_end=timezone.localdate(),
                defaults={
                    "gross_sales_amount": Decimal("340.00"),
                    "commission_deducted": Decimal("51.00"),
                    "fees_deducted": Decimal("9.86"),
                    "refunds_deducted": Decimal("0.00"),
                    "tax_withholding_amount": Decimal("0.00"),
                    "payout_method": "bank_transfer",
                    "payout_status": "pending_approval",
                    "notes": "Batch pending finance review for scheduled ACH wire transfer.",
                },
            )








