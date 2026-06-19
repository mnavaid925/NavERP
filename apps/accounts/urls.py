from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    # Auth
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("register/", views.register_view, name="register"),
    path("forgot-password/", views.forgot_password_view, name="forgot_password"),
    path("reset/<uidb64>/<token>/", views.reset_password_view, name="reset_password"),
    # Users
    path("users/", views.user_list, name="user_list"),
    path("users/add/", views.user_create, name="user_create"),
    path("users/<int:pk>/", views.user_detail, name="user_detail"),
    path("users/<int:pk>/edit/", views.user_edit, name="user_edit"),
    path("users/<int:pk>/delete/", views.user_delete, name="user_delete"),
    # Roles
    path("roles/", views.role_list, name="role_list"),
    path("roles/add/", views.role_create, name="role_create"),
    path("roles/<int:pk>/", views.role_detail, name="role_detail"),
    path("roles/<int:pk>/edit/", views.role_edit, name="role_edit"),
    path("roles/<int:pk>/delete/", views.role_delete, name="role_delete"),
    # Invites
    path("invites/", views.invite_list, name="invite_list"),
    path("invites/add/", views.invite_create, name="invite_create"),
    path("invites/<int:pk>/revoke/", views.invite_revoke, name="invite_revoke"),
    path("invite/<str:token>/", views.invite_accept, name="invite_accept"),
    # Profile
    path("profile/", views.profile_view, name="profile"),
]
