from django.urls import path

from apps.bi.views.EmbeddedMobileBi import KioskWallboardDisplays as views

urlpatterns = [
    path("kiosk-displays/", views.kiosk_wallboard_display_list, name="kiosk_wallboard_display_list"),
    path("kiosk-displays/create/", views.kiosk_wallboard_display_create, name="kiosk_wallboard_display_create"),
    path("kiosk-displays/<int:pk>/", views.kiosk_wallboard_display_detail, name="kiosk_wallboard_display_detail"),
    path("kiosk-displays/<int:pk>/edit/", views.kiosk_wallboard_display_edit, name="kiosk_wallboard_display_edit"),
    path("kiosk-displays/<int:pk>/delete/", views.kiosk_wallboard_display_delete, name="kiosk_wallboard_display_delete"),
    path("kiosk-displays/<int:pk>/player/", views.kiosk_wallboard_display_player, name="kiosk_wallboard_display_player"),
    path("kiosk-displays/<int:pk>/heartbeat/", views.kiosk_wallboard_display_heartbeat, name="kiosk_wallboard_display_heartbeat"),
]
