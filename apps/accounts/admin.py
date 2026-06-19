from django.contrib import admin

from .models import Permission, Role, User, UserInvite


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
