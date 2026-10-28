from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.core.models import Tenant
from apps.ecommerce.models.ProductCatalog.CatalogProducts import CatalogProduct
from apps.ecommerce.models.ProductCatalog.ProductRelationships import (
    ProductRelationship,
)
from apps.ecommerce.models.ProductCatalog.ProductVariants import ProductVariant
from apps.ecommerce.models.ProductCatalog.StoreCategories import StoreCategory
from apps.scm.models.InventoryManagement.Items import Item


class Command(BaseCommand):
    help = "Seed demo data for eCommerce module (9.1 Product Catalog)"

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
