from apps.ecommerce.urls.PricingPromotion.CompetitorPriceMonitors import urlpatterns as competitor_patterns
from apps.ecommerce.urls.PricingPromotion.CouponPromotions import urlpatterns as coupon_patterns
from apps.ecommerce.urls.PricingPromotion.DynamicPriceRules import urlpatterns as price_rule_patterns
from apps.ecommerce.urls.PricingPromotion.FlashSales import urlpatterns as flash_patterns

urlpatterns = price_rule_patterns + coupon_patterns + flash_patterns + competitor_patterns

__all__ = ["urlpatterns"]
