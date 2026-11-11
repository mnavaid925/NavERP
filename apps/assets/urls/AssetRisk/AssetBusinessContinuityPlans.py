from django.urls import path

from apps.assets.views.AssetRisk import AssetBusinessContinuityPlans as views

urlpatterns = [
    path("risk/continuity-plans/", views.asset_business_continuity_plan_list, name="asset_business_continuity_plan_list"),
    path("risk/continuity-plans/create/", views.asset_business_continuity_plan_create, name="asset_business_continuity_plan_create"),
    path("risk/continuity-plans/<int:pk>/", views.asset_business_continuity_plan_detail, name="asset_business_continuity_plan_detail"),
    path("risk/continuity-plans/<int:pk>/edit/", views.asset_business_continuity_plan_edit, name="asset_business_continuity_plan_edit"),
    path("risk/continuity-plans/<int:pk>/delete/", views.asset_business_continuity_plan_delete, name="asset_business_continuity_plan_delete"),
    path("risk/continuity-plans/<int:pk>/activate/", views.asset_business_continuity_plan_activate, name="asset_business_continuity_plan_activate"),
    path("risk/continuity-plans/<int:pk>/drill/", views.asset_business_continuity_plan_drill, name="asset_business_continuity_plan_drill"),
]
