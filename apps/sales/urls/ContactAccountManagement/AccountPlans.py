from django.urls import path

from apps.sales import views

urlpatterns = [
    path("account-plans/", views.account_plan_list, name="account_plan_list"),
    path("account-plans/add/", views.account_plan_create, name="account_plan_create"),
    path("account-plans/export/", views.account_plan_export, name="account_plan_export"),
    path("account-plans/<int:pk>/", views.account_plan_detail, name="account_plan_detail"),
    path("account-plans/<int:pk>/edit/", views.account_plan_edit, name="account_plan_edit"),
    path("account-plans/<int:pk>/delete/", views.account_plan_delete, name="account_plan_delete"),
    path("account-plans/<int:pk>/activate/", views.account_plan_activate, name="account_plan_activate"),
    path("account-plans/<int:pk>/review-due/", views.account_plan_review_due, name="account_plan_review_due"),
    path("account-plans/<int:pk>/complete/", views.account_plan_complete, name="account_plan_complete"),
    path("account-plans/<int:pk>/archive/", views.account_plan_archive, name="account_plan_archive"),
]
