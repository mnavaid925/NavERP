from django.urls import path

from apps.bi.views.DataQuality import DataQualityExceptions as views

urlpatterns = [
    path("data-quality/exceptions/", views.data_quality_exception_list, name="data_quality_exception_list"),
    path("data-quality/exceptions/create/", views.data_quality_exception_create, name="data_quality_exception_create"),
    path("data-quality/exceptions/<int:pk>/", views.data_quality_exception_detail, name="data_quality_exception_detail"),
    path("data-quality/exceptions/<int:pk>/edit/", views.data_quality_exception_edit, name="data_quality_exception_edit"),
    path("data-quality/exceptions/<int:pk>/delete/", views.data_quality_exception_delete, name="data_quality_exception_delete"),
    path("data-quality/exceptions/<int:pk>/remediate/", views.data_quality_exception_remediate, name="data_quality_exception_remediate"),
]
