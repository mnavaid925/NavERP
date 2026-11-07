from django.urls import path

from apps.bi.views.PredictiveAnalytics import PredictiveModels as views

urlpatterns = [
    path("predictive-models/", views.predictive_model_list, name="predictive_model_list"),
    path("predictive-models/create/", views.predictive_model_create, name="predictive_model_create"),
    path("predictive-models/<int:pk>/", views.predictive_model_detail, name="predictive_model_detail"),
    path("predictive-models/<int:pk>/edit/", views.predictive_model_edit, name="predictive_model_edit"),
    path("predictive-models/<int:pk>/delete/", views.predictive_model_delete, name="predictive_model_delete"),
    path("predictive-models/<int:pk>/train/", views.predictive_model_train, name="predictive_model_train"),
]
