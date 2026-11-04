from django.urls import path

from apps.bi.views.SemanticLayer import BusinessGlossaryTerms as views

urlpatterns = [
    path("semantic/glossary/", views.business_glossary_term_list, name="business_glossary_term_list"),
    path("semantic/glossary/create/", views.business_glossary_term_create, name="business_glossary_term_create"),
    path("semantic/glossary/<int:pk>/", views.business_glossary_term_detail, name="business_glossary_term_detail"),
    path("semantic/glossary/<int:pk>/edit/", views.business_glossary_term_edit, name="business_glossary_term_edit"),
    path("semantic/glossary/<int:pk>/delete/", views.business_glossary_term_delete, name="business_glossary_term_delete"),
    path("semantic/glossary/<int:pk>/certify/", views.business_glossary_term_certify, name="business_glossary_term_certify"),
]
