from apps.ecommerce.urls.CartCheckout.Carts import urlpatterns as cart_patterns
from apps.ecommerce.urls.CartCheckout.CheckoutSessions import urlpatterns as session_patterns
from apps.ecommerce.urls.CartCheckout.PaymentMethods import urlpatterns as payment_patterns
from apps.ecommerce.urls.CartCheckout.ShippingMethods import urlpatterns as shipping_patterns

urlpatterns = cart_patterns + session_patterns + shipping_patterns + payment_patterns

__all__ = ["urlpatterns"]
