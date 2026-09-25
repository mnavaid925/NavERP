from django.urls import path

from apps.sales import views

urlpatterns = [
    path("accounts/hierarchy/", views.account_hierarchy, name="account_hierarchy"),
    path("accounts/workspace/export/", views.account_workspace_export, name="account_workspace_export"),
    path("accounts/workspace/", views.account_workspace, name="account_workspace"),
    path("accounts/coverage/", views.account_coverage, name="account_coverage"),
    path("accounts/white-space/", views.account_white_space, name="account_white_space"),
]
