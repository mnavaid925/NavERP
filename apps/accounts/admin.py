from django.contrib import admin

from .models import (
    AccessRequest,
    AccessReview,
    AccessReviewItem,
    ElevationGrant,
    LoginAttempt,
    MfaDevice,
    PasswordHistory,
    PasswordPolicy,
    Permission,
    Role,
    User,
    UserImportBatch,
    UserInvite,
    UserSession,
)


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ["email", "username", "tenant", "role", "is_tenant_admin", "status", "is_active"]
    list_filter = ["status", "is_tenant_admin", "is_active", "tenant"]
    search_fields = ["email", "username", "first_name", "last_name"]
    readonly_fields = ["date_joined", "last_login"]
    exclude = ["password"]  # set via the app UI / management commands, not raw in admin
    filter_horizontal = ["groups", "user_permissions"]


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ["name", "tenant", "is_system"]
    list_filter = ["is_system", "tenant"]
    search_fields = ["name"]
    filter_horizontal = ["permissions"]


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ["codename", "name", "module"]
    list_filter = ["module"]
    search_fields = ["codename", "name"]


@admin.register(UserInvite)
class UserInviteAdmin(admin.ModelAdmin):
    list_display = ["email", "tenant", "role", "status", "expires_at", "invited_by"]
    list_filter = ["status", "tenant"]
    search_fields = ["email"]
    readonly_fields = ["token", "created_at", "accepted_at"]


@admin.register(AccessRequest)
class AccessRequestAdmin(admin.ModelAdmin):
    list_display = ["requester", "requested_role", "status", "requested_days", "granted_until", "tenant"]
    list_filter = ["status", "tenant"]
    search_fields = ["requester__email", "justification"]
    list_select_related = ["requester", "requested_role", "decided_by"]
    # Verb-written evidence: never hand-editable, or an approval could be forged here.
    readonly_fields = ["decided_by", "decided_at", "granted_until", "created_at"]


class AccessReviewItemInline(admin.TabularInline):
    model = AccessReviewItem
    extra = 0
    fields = ["user", "role", "decision", "decided_by", "decided_at"]
    readonly_fields = ["decided_by", "decided_at"]


@admin.register(AccessReview)
class AccessReviewAdmin(admin.ModelAdmin):
    list_display = ["name", "tenant", "scope_role", "status", "due_on", "closed_at"]
    list_filter = ["status", "tenant"]
    search_fields = ["name"]
    list_select_related = ["scope_role", "created_by"]
    readonly_fields = ["closed_at", "created_at"]
    inlines = [AccessReviewItemInline]


@admin.register(AccessReviewItem)
class AccessReviewItemAdmin(admin.ModelAdmin):
    list_display = ["review", "user", "role", "decision", "decided_by", "decided_at"]
    list_filter = ["decision", "tenant"]
    search_fields = ["user__email", "review__name"]
    list_select_related = ["review", "user", "role"]
    readonly_fields = ["decided_by", "decided_at"]


@admin.register(ElevationGrant)
class ElevationGrantAdmin(admin.ModelAdmin):
    list_display = ["user", "scope", "status", "starts_at", "expires_at", "tenant"]
    list_filter = ["status", "scope", "tenant"]
    search_fields = ["user__email", "reason"]
    list_select_related = ["user", "requested_by", "approved_by", "revoked_by"]
    readonly_fields = ["approved_by", "approved_at", "revoked_by", "revoked_at", "created_at"]


@admin.register(UserImportBatch)
class UserImportBatchAdmin(admin.ModelAdmin):
    list_display = ["file_name", "tenant", "status", "row_count", "created_count", "error_count",
                    "committed_at"]
    list_filter = ["status", "tenant"]
    search_fields = ["file_name"]
    list_select_related = ["uploaded_by"]
    # `staged_rows` holds the parsed payload and `errors` the validation outcome — both are
    # system-written; editing them by hand would desync the batch from what was uploaded.
    readonly_fields = ["row_count", "created_count", "error_count", "errors", "staged_rows",
                       "committed_at", "created_at"]


@admin.register(MfaDevice)
class MfaDeviceAdmin(admin.ModelAdmin):
    list_display = ["user", "kind", "name", "is_confirmed", "is_active", "last_used_at", "tenant"]
    list_filter = ["kind", "is_active", "tenant"]
    search_fields = ["user__email", "name"]
    list_select_related = ["user", "tenant"]
    # The secret is never rendered or edited here. `core.crypto` protects it at rest, but an admin
    # form would print the plaintext into a page and an admin action log — the one place it must
    # never appear. Recovery codes are hashes and are equally excluded.
    exclude = ["secret_encrypted", "backup_code_hashes"]
    readonly_fields = ["confirmed_at", "last_used_at", "last_counter", "created_at"]


@admin.register(PasswordPolicy)
class PasswordPolicyAdmin(admin.ModelAdmin):
    list_display = ["tenant", "is_enforced", "min_length", "max_age_days", "prevent_reuse_count"]
    list_filter = ["is_enforced", "tenant"]
    readonly_fields = ["updated_at"]


@admin.register(PasswordHistory)
class PasswordHistoryAdmin(admin.ModelAdmin):
    list_display = ["user", "set_at", "tenant"]
    list_filter = ["tenant"]
    search_fields = ["user__email"]
    list_select_related = ["user", "tenant"]
    # Hashes only, and read-only: this table is an audit of password changes, not an editable one.
    readonly_fields = ["user", "password_hash", "set_at", "tenant"]

    def has_add_permission(self, request):
        return False


@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    list_display = ["user", "ip", "created_at", "last_seen_at", "is_revoked", "tenant"]
    list_filter = ["tenant"]
    search_fields = ["user__email", "ip", "user_agent"]
    list_select_related = ["user", "tenant", "revoked_by"]
    readonly_fields = ["session_key", "ip", "user_agent", "created_at", "last_seen_at",
                       "revoked_at", "revoked_by"]


@admin.register(LoginAttempt)
class LoginAttemptAdmin(admin.ModelAdmin):
    list_display = ["identifier", "success", "risk_score", "mfa_challenged", "ip", "created_at"]
    list_filter = ["success", "mfa_challenged", "tenant"]
    search_fields = ["identifier", "ip", "user_agent"]
    list_select_related = ["user", "tenant"]
    # Append-only telemetry: it is the record of what happened, so nothing here is editable.
    readonly_fields = ["tenant", "user", "identifier", "ip", "user_agent", "success",
                       "risk_score", "risk_reasons", "mfa_challenged", "created_at"]

    def has_add_permission(self, request):
        return False
