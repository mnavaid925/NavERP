"""HRM 3.33 Asset Management — Asset URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # 3.33 Asset Management (asset-register/ + asset-maintenance/ — assets/ is already AssetAllocation's)
    path("asset-register/", views.asset_list, name="asset_list"),
    path("asset-register/add/", views.asset_create, name="asset_create"),
    path("asset-register/<int:pk>/", views.asset_detail, name="asset_detail"),
    path("asset-register/<int:pk>/edit/", views.asset_edit, name="asset_edit"),
    path("asset-register/<int:pk>/delete/", views.asset_delete, name="asset_delete"),
    path("asset-register/<int:pk>/assign/", views.asset_assign, name="asset_assign"),
    path("asset-register/<int:pk>/return/", views.asset_return, name="asset_return"),
    path("asset-register/<int:pk>/retire/", views.asset_retire, name="asset_retire"),
    path("asset-register/<int:pk>/dispose/", views.asset_dispose, name="asset_dispose"),
]
