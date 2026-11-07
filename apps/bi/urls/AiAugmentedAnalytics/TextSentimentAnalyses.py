from django.urls import path

from apps.bi.views.AiAugmentedAnalytics import TextSentimentAnalyses as views

urlpatterns = [
    path("sentiment-analyses/", views.text_sentiment_analysis_list, name="text_sentiment_analysis_list"),
    path("sentiment-analyses/new/", views.text_sentiment_analysis_create, name="text_sentiment_analysis_create"),
    path("sentiment-analyses/<int:pk>/", views.text_sentiment_analysis_detail, name="text_sentiment_analysis_detail"),
    path("sentiment-analyses/<int:pk>/edit/", views.text_sentiment_analysis_edit, name="text_sentiment_analysis_edit"),
    path("sentiment-analyses/<int:pk>/delete/", views.text_sentiment_analysis_delete, name="text_sentiment_analysis_delete"),
    path("sentiment-analyses/<int:pk>/recalculate/", views.text_sentiment_analysis_recalculate, name="text_sentiment_analysis_recalculate"),
]
