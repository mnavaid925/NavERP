from django.contrib import admin

from .models import (
    AccessRequest,
    AccessReview,
    AccessReviewItem,
    ElevationGrant,
    Permission,
    Role,
    User,
    UserImportBatch,
    UserInvite,
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
