from apps.ecommerce.views.PricingPromotion.CompetitorPriceMonitors import (
    competitorpricemonitor_create,
    competitorpricemonitor_delete,
    competitorpricemonitor_detail,
    competitorpricemonitor_edit,
    competitorpricemonitor_list,
    competitorpricemonitor_sync,
)
from apps.ecommerce.views.PricingPromotion.CouponPromotions import (
    couponpromotion_create,
    couponpromotion_delete,
    couponpromotion_detail,
    couponpromotion_edit,
    couponpromotion_list,
)
from apps.ecommerce.views.PricingPromotion.DynamicPriceRules import (
    dynamicpricerule_create,
    dynamicpricerule_delete,
    dynamicpricerule_detail,
    dynamicpricerule_edit,
    dynamicpricerule_list,
)
from apps.ecommerce.views.PricingPromotion.FlashSales import (
    flashsale_create,
    flashsale_delete,
    flashsale_detail,
    flashsale_edit,
    flashsale_list,
)

__all__ = [
    "dynamicpricerule_list",
    "dynamicpricerule_detail",
    "dynamicpricerule_create",
    "dynamicpricerule_edit",
    "dynamicpricerule_delete",
    "couponpromotion_list",
    "couponpromotion_detail",
    "couponpromotion_create",
    "couponpromotion_edit",
    "couponpromotion_delete",
    "flashsale_list",
    "flashsale_detail",
    "flashsale_create",
    "flashsale_edit",
    "flashsale_delete",
    "competitorpricemonitor_list",
    "competitorpricemonitor_detail",
    "competitorpricemonitor_create",
    "competitorpricemonitor_edit",
    "competitorpricemonitor_delete",
    "competitorpricemonitor_sync",
]
