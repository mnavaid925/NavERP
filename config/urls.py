"""NavERP URL configuration."""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.dashboard.urls")),       # /  -> dashboard:home
    path("", include("apps.accounts.urls")),        # /login/, /users/, /roles/, /profile/, ...
    path("core/", include("apps.core.urls")),       # /core/parties/, /core/org-units/, ...
    path("tenants/", include("apps.tenants.urls")),  # /tenants/subscriptions/, /tenants/stripe/webhook/, ...
    path("crm/", include("apps.crm.urls")),         # /crm/, /crm/leads/, /crm/opportunities/, ...
    path("accounting/", include("apps.accounting.urls")),  # /accounting/, GL/AP/AR/cash management
    path("hrm/", include("apps.hrm.urls")),         # /hrm/, employees/leave/attendance/shifts/holidays
    path("scm/", include("apps.scm.urls")),         # /scm/, requisitions/rfqs/orders/receipts
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
