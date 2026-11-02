from django.urls import path
from apps.ecommerce.views.B2bWholesale import B2bCompanyAccounts as views

urlpatterns = [
    path("b2b/companies/", views.b2bcompanyaccount_list, name="b2bcompanyaccount_list"),
    path("b2b/companies/new/", views.b2bcompanyaccount_create, name="b2bcompanyaccount_create"),
    path("b2b/companies/<int:pk>/", views.b2bcompanyaccount_detail, name="b2bcompanyaccount_detail"),
    path("b2b/companies/<int:pk>/edit/", views.b2bcompanyaccount_edit, name="b2bcompanyaccount_edit"),
    path("b2b/companies/<int:pk>/delete/", views.b2bcompanyaccount_delete, name="b2bcompanyaccount_delete"),
    path("b2b/companies/<int:pk>/punchout-test/", views.b2bcompanyaccount_punchout_test, name="b2bcompanyaccount_punchout_test"),
]
