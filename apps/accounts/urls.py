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
    # Bulk provisioning — literal segments BEFORE the <int:pk> routes (0.2 bullet 2).
    path("users/export/", views.user_export, name="user_export"),
    path("users/import/", views.user_import, name="user_import"),
    path("users/import/batches/", views.user_import_list, name="user_import_list"),
    path("users/import/batches/<int:pk>/", views.user_import_detail, name="user_import_detail"),
    path("users/import/batches/<int:pk>/commit/", views.user_import_commit, name="user_import_commit"),
    path("users/<int:pk>/", views.user_detail, name="user_detail"),
    path("users/<int:pk>/edit/", views.user_edit, name="user_edit"),
    path("users/<int:pk>/delete/", views.user_delete, name="user_delete"),
    path("users/<int:pk>/deprovision/", views.user_deprovision, name="user_deprovision"),
    # Access requests — 0.2 bullet 3
    path("access-requests/mine/", views.access_request_mine, name="access_request_mine"),
    path("access-requests/new/", views.access_request_create, name="access_request_create"),
    path("access-requests/", views.access_request_list, name="access_request_list"),
    path("access-requests/<int:pk>/", views.access_request_detail, name="access_request_detail"),
    path("access-requests/<int:pk>/edit/", views.access_request_edit, name="access_request_edit"),
    path("access-requests/<int:pk>/delete/", views.access_request_delete, name="access_request_delete"),
    path("access-requests/<int:pk>/approve/", views.access_request_approve, name="access_request_approve"),
    path("access-requests/<int:pk>/reject/", views.access_request_reject, name="access_request_reject"),
    path("access-requests/<int:pk>/cancel/", views.access_request_cancel, name="access_request_cancel"),
    # Access certification — 0.2 bullet 4
    path("access-reviews/", views.access_review_list, name="access_review_list"),
    path("access-reviews/add/", views.access_review_create, name="access_review_create"),
    path("access-reviews/orphans/", views.orphan_accounts, name="orphan_accounts"),
    path("access-reviews/item/<int:pk>/attest/", views.access_review_item_attest,
         name="access_review_item_attest"),
    path("access-reviews/item/<int:pk>/revoke/", views.access_review_item_revoke,
         name="access_review_item_revoke"),
    path("access-reviews/<int:pk>/", views.access_review_detail, name="access_review_detail"),
    path("access-reviews/<int:pk>/edit/", views.access_review_edit, name="access_review_edit"),
    path("access-reviews/<int:pk>/delete/", views.access_review_delete, name="access_review_delete"),
    path("access-reviews/<int:pk>/generate/", views.access_review_generate,
         name="access_review_generate"),
    path("access-reviews/<int:pk>/close/", views.access_review_close, name="access_review_close"),
    # Privileged access management — 0.2 bullet 5
    path("elevations/", views.elevation_list, name="elevation_list"),
    path("elevations/add/", views.elevation_create, name="elevation_create"),
    path("elevations/<int:pk>/", views.elevation_detail, name="elevation_detail"),
    path("elevations/<int:pk>/edit/", views.elevation_edit, name="elevation_edit"),
    path("elevations/<int:pk>/delete/", views.elevation_delete, name="elevation_delete"),
    path("elevations/<int:pk>/approve/", views.elevation_approve, name="elevation_approve"),
    path("elevations/<int:pk>/revoke/", views.elevation_revoke, name="elevation_revoke"),
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
    # Authentication & SSO — 0.2/0.4. `mfa/challenge/` is deliberately reachable while ANONYMOUS:
    # the user is mid-login and is not signed in until the challenge passes.
    path("mfa/challenge/", views.mfa_challenge, name="mfa_challenge"),
    path("mfa/", views.mfa_manage, name="mfa_manage"),
    path("mfa/setup/", views.mfa_setup, name="mfa_setup"),
    path("mfa/setup/confirm/", views.mfa_confirm, name="mfa_confirm"),
    path("mfa/disable/", views.mfa_disable, name="mfa_disable"),
    path("mfa/backup-codes/", views.mfa_regenerate_backup, name="mfa_regenerate_backup"),
    # Session management — 0.4 bullet 4
    path("sessions/", views.session_list, name="session_list"),
    path("sessions/revoke-others/", views.session_revoke_others, name="session_revoke_others"),
    path("sessions/<int:pk>/revoke/", views.session_revoke, name="session_revoke"),
    # Security posture — 0.4 bullets 3 and 5
    path("security/", views.security_overview, name="security_overview"),
    path("security/password-policy/", views.password_policy_edit, name="password_policy_edit"),
    path("security/login-attempts/", views.login_attempt_list, name="login_attempt_list"),
]
