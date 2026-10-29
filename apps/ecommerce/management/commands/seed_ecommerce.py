from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.core.models import Tenant
from apps.ecommerce.models.InventoryStock.BackorderPolicies import BackorderPolicy
from apps.ecommerce.models.InventoryStock.ChannelInventorySyncs import ChannelInventorySync
from apps.ecommerce.models.InventoryStock.FulfillmentCenters import FulfillmentCenter
from apps.ecommerce.models.InventoryStock.InventoryAllocations import InventoryAllocation
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
        v1 = ProductVariant.objects.filter(tenant=tenant, sku="TSH-NVY-M").first()
        v2 = ProductVariant.objects.filter(tenant=tenant, sku="TSH-NVY-L").first()
        v3 = ProductVariant.objects.filter(tenant=tenant, sku="TSH-BLK-M").first()
        v4 = ProductVariant.objects.filter(tenant=tenant, sku="HDPH-BLK").first()
        v5 = ProductVariant.objects.filter(tenant=tenant, sku="TOT-NAT").first()

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
                    "zone_bin": "Aisle 2, Bin B-01",
                    "quantity_on_hand": 0,
                    "quantity_allocated": 0,
                    "safety_stock_buffer": 5,
                    "low_stock_threshold": 10,
                    "restock_lead_time_days": 10,
                    "last_counted_at": now,
                    "notes": "Out of stock; awaiting factory container delivery.",
                },
            )

        if v4:
            InventoryAllocation.objects.get_or_create(
                tenant=tenant,
                variant=v4,
                fulfillment_center=fc_west,
                defaults={
                    "product": v4.product,
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
                variant=v4,
                fulfillment_center=fc_store,
                defaults={
                    "product": v4.product,
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

        if v5:
            InventoryAllocation.objects.get_or_create(
                tenant=tenant,
                variant=v5,
                fulfillment_center=fc_west,
                defaults={
                    "product": v5.product,
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

        if v3:
            BackorderPolicy.objects.get_or_create(
                tenant=tenant,
                variant=v3,
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

        if v4:
            BackorderPolicy.objects.get_or_create(
                tenant=tenant,
                variant=v4,
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

        if v4:
            ChannelInventorySync.objects.get_or_create(
                tenant=tenant,
                variant=v4,
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

        if v5:
            ChannelInventorySync.objects.get_or_create(
                tenant=tenant,
                variant=v5,
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

