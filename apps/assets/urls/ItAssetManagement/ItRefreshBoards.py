"""URL patterns for End-of-Life & Refresh Cycles Workbench (11.18)."""

from django.urls import path

from apps.assets.views.ItAssetManagement.ItRefreshBoards import (
    it_refresh_board,
    it_refresh_board_export_csv,
)

urlpatterns = [
    path("it-hardware/refresh-board/", it_refresh_board, name="it_refresh_board"),
    path("it-hardware/refresh-board/export-csv/", it_refresh_board_export_csv, name="it_refresh_board_export_csv"),
]
