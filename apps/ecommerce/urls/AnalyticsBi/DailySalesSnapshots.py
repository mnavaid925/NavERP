from django.urls import path

from apps.ecommerce.views.AnalyticsBi import DailySalesSnapshots as views

urlpatterns = [
    path("analytics/sales-snapshots/", views.dailysalessnapshot_list, name="dailysalessnapshot_list"),
    path("analytics/sales-snapshots/create/", views.dailysalessnapshot_create, name="dailysalessnapshot_create"),
    path("analytics/sales-snapshots/generate/", views.dailysalessnapshot_generate, name="dailysalessnapshot_generate"),
    path("analytics/sales-snapshots/<int:pk>/", views.dailysalessnapshot_detail, name="dailysalessnapshot_detail"),
    path("analytics/sales-snapshots/<int:pk>/edit/", views.dailysalessnapshot_edit, name="dailysalessnapshot_edit"),
    path("analytics/sales-snapshots/<int:pk>/delete/", views.dailysalessnapshot_delete, name="dailysalessnapshot_delete"),
]
