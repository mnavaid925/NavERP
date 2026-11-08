from django.urls import path

from apps.bi.views.IntegrationHub import BiExtensionPlugins as views

urlpatterns = [
    path("plugins/", views.bi_extension_plugin_list, name="bi_extension_plugin_list"),
    path("plugins/create/", views.bi_extension_plugin_create, name="bi_extension_plugin_create"),
    path("plugins/<int:pk>/", views.bi_extension_plugin_detail, name="bi_extension_plugin_detail"),
    path("plugins/<int:pk>/edit/", views.bi_extension_plugin_edit, name="bi_extension_plugin_edit"),
    path("plugins/<int:pk>/delete/", views.bi_extension_plugin_delete, name="bi_extension_plugin_delete"),
    path("plugins/<int:pk>/toggle/", views.bi_extension_plugin_toggle, name="bi_extension_plugin_toggle"),
]
