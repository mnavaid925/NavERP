"""CRM 1.3 Marketing Automation — LandingPages URL patterns (split from apps/crm/urls.py)."""
from django.urls import path

from apps.crm import views


urlpatterns = [
    # Landing pages (1.3 Landing Pages & Forms)
    path("landing-pages/", views.landingpage_list, name="landingpage_list"),
    path("landing-pages/add/", views.landingpage_create, name="landingpage_create"),
    path("landing-pages/<int:pk>/", views.landingpage_detail, name="landingpage_detail"),
    path("landing-pages/<int:pk>/edit/", views.landingpage_edit, name="landingpage_edit"),
    path("landing-pages/<int:pk>/delete/", views.landingpage_delete, name="landingpage_delete"),
    path("landing-pages/<int:pk>/publish/", views.landingpage_publish, name="landingpage_publish"),
    path("p/<str:token>/", views.landing_public, name="landing_public"),  # public web-to-lead
]
