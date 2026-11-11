from django.urls import path

from apps.assets.views.IntegrationApiHub import AssetGlSyncBatches as views

urlpatterns = [
    path(
        "integration/gl-sync-batches/",
        views.batch_list,
        name="asset_gl_sync_batch_list",
    ),
    path(
        "integration/gl-sync-batches/create/",
        views.batch_create,
        name="asset_gl_sync_batch_create",
    ),
    path(
        "integration/gl-sync-batches/<int:pk>/",
        views.batch_detail,
        name="asset_gl_sync_batch_detail",
    ),
    path(
        "integration/gl-sync-batches/<int:pk>/edit/",
        views.batch_edit,
        name="asset_gl_sync_batch_edit",
    ),
    path(
        "integration/gl-sync-batches/<int:pk>/delete/",
        views.batch_delete,
        name="asset_gl_sync_batch_delete",
    ),
    path(
        "integration/gl-sync-batches/<int:pk>/execute/",
        views.execute_reconcile_batch,
        name="asset_gl_sync_batch_execute",
    ),
]
