from django.urls import path

from apps.bi.views.AlertsSubscriptions import BiAlertRules as views

urlpatterns = [
    path("alerts/", views.bi_alert_rule_list, name="bi_alert_rule_list"),
    path("alerts/create/", views.bi_alert_rule_create, name="bi_alert_rule_create"),
    path("alerts/<int:pk>/", views.bi_alert_rule_detail, name="bi_alert_rule_detail"),
    path("alerts/<int:pk>/edit/", views.bi_alert_rule_edit, name="bi_alert_rule_edit"),
    path("alerts/<int:pk>/delete/", views.bi_alert_rule_delete, name="bi_alert_rule_delete"),
    path("alerts/<int:pk>/evaluate/", views.bi_alert_rule_test_evaluate, name="bi_alert_rule_test_evaluate"),

    # Short aliases for contract/caller consistency
    path("alerts/", views.bi_alert_rule_list, name="alert_rule_list"),
    path("alerts/create/", views.bi_alert_rule_create, name="alert_rule_create"),
    path("alerts/<int:pk>/", views.bi_alert_rule_detail, name="alert_rule_detail"),
    path("alerts/<int:pk>/edit/", views.bi_alert_rule_edit, name="alert_rule_edit"),
    path("alerts/<int:pk>/delete/", views.bi_alert_rule_delete, name="alert_rule_delete"),
    path("alerts/<int:pk>/evaluate/", views.bi_alert_rule_test_evaluate, name="alert_rule_test_evaluate"),
]
