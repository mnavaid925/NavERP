from django.urls import path
from apps.bi.views.MasterData import MdmSurvivorshipRules as views

urlpatterns = [
    path("mdm/survivorship-rules/", views.mdm_survivorship_rule_list, name="mdm_survivorship_rule_list"),
    path("mdm/survivorship-rules/create/", views.mdm_survivorship_rule_create, name="mdm_survivorship_rule_create"),
    path("mdm/survivorship-rules/<int:pk>/", views.mdm_survivorship_rule_detail, name="mdm_survivorship_rule_detail"),
    path("mdm/survivorship-rules/<int:pk>/edit/", views.mdm_survivorship_rule_edit, name="mdm_survivorship_rule_edit"),
    path("mdm/survivorship-rules/<int:pk>/delete/", views.mdm_survivorship_rule_delete, name="mdm_survivorship_rule_delete"),
]
