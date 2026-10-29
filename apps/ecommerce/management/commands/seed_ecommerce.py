from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounting.models.GeneralLedger.Currencies import Currency
from apps.core.models import Party, Tenant
from apps.ecommerce.models.CartCheckout.Carts import Cart, CartItem
from apps.ecommerce.models.CartCheckout.CheckoutSessions import CheckoutSession
from apps.ecommerce.models.CartCheckout.PaymentMethods import PaymentMethodConfig
from apps.ecommerce.models.CartCheckout.ShippingMethods import ShippingMethodConfig
from apps.ecommerce.models.InventoryStock.BackorderPolicies import BackorderPolicy
from apps.ecommerce.models.InventoryStock.ChannelInventorySyncs import ChannelInventorySync
from apps.ecommerce.models.InventoryStock.FulfillmentCenters import FulfillmentCenter
from apps.ecommerce.models.InventoryStock.InventoryAllocations import InventoryAllocation
from apps.ecommerce.models.OrderManagement.EcommerceOrders import EcommerceOrder, EcommerceOrderLine
from apps.ecommerce.models.OrderManagement.OrderFulfillments import OrderFulfillment
from apps.ecommerce.models.OrderManagement.OrderRoutingRules import OrderRoutingRule
from apps.ecommerce.models.OrderManagement.ReturnMerchandiseAuthorizations import ReturnMerchandiseAuthorization
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




