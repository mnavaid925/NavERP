from apps.ecommerce.forms._common import TenantUniqueMixin, reject_foreign
from apps.ecommerce.forms.InventoryStock.BackorderPolicies import BackorderPolicyForm
from apps.ecommerce.forms.InventoryStock.ChannelInventorySyncs import ChannelInventorySyncForm
from apps.ecommerce.forms.InventoryStock.FulfillmentCenters import FulfillmentCenterForm
from apps.ecommerce.forms.InventoryStock.InventoryAllocations import (
    InventoryAllocationForm,
    StockAdjustmentActionForm,
)
from apps.ecommerce.forms.PricingPromotion.CompetitorPriceMonitors import CompetitorPriceMonitorForm
from apps.ecommerce.forms.PricingPromotion.CouponPromotions import CouponPromotionForm
from apps.ecommerce.forms.PricingPromotion.DynamicPriceRules import DynamicPriceRuleForm
from apps.ecommerce.forms.PricingPromotion.FlashSales import FlashSaleForm
from apps.ecommerce.forms.ProductCatalog.BulkOperations import ProductImportForm
from apps.ecommerce.forms.ProductCatalog.CatalogProducts import CatalogProductForm
from apps.ecommerce.forms.ProductCatalog.ProductRelationships import (
    ProductRelationshipForm,
)
from apps.ecommerce.forms.ProductCatalog.ProductVariants import ProductVariantForm
from apps.ecommerce.forms.ProductCatalog.StoreCategories import StoreCategoryForm

__all__ = [
    "TenantUniqueMixin",
    "reject_foreign",
    # 9.1 Product Catalog
    "StoreCategoryForm",
    "CatalogProductForm",
    "ProductVariantForm",
    "ProductRelationshipForm",
    "ProductImportForm",
    # 9.2 Inventory & Stock Management
    "FulfillmentCenterForm",
    "InventoryAllocationForm",
    "StockAdjustmentActionForm",
    "BackorderPolicyForm",
    "ChannelInventorySyncForm",
    # 9.3 Pricing & Promotion Engine
    "DynamicPriceRuleForm",
    "CouponPromotionForm",
    "FlashSaleForm",
    "CompetitorPriceMonitorForm",
]

