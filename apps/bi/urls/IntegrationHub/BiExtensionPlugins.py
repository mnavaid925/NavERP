from django.urls import path

from apps.bi.views.IntegrationHub import BiExtensionPlugins as views

urlpatterns = [
    path("integrations/plugins/", views.bi_extension_plugin_list, name="bi_extension_plugin_list"),
    path("integrations/plugins/create/", views.bi_extension_plugin_create, name="bi_extension_plugin_create"),
    path("integrations/plugins/<int:pk>/", views.bi_extension_plugin_detail, name="bi_extension_plugin_detail"),
    path("integrations/plugins/<int:pk>/edit/", views.bi_extension_plugin_edit, name="bi_extension_plugin_edit"),
    path("integrations/plugins/<int:pk>/delete/", views.bi_extension_plugin_delete, name="bi_extension_plugin_delete"),
    path("integrations/plugins/<int:pk>/toggle/", views.bi_extension_plugin_toggle, name="bi_extension_plugin_toggle"),
]
