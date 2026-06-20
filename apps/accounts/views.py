"""Authentication, user/role/invite management, and profile views."""
from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.conf import settings
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import (
    url_has_allowed_host_and_scheme,
    urlsafe_base64_decode,
    urlsafe_base64_encode,
)
from django.views.decorators.http import require_POST

from apps.core.crud import crud_create, crud_edit, crud_list
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log

from .forms import (
    ForgotPasswordForm,
    InviteAcceptForm,
    LoginForm,
    ProfileForm,
    RoleForm,
    SetPasswordForm,
    TenantRegisterForm,
    UserForm,
    UserInviteForm,
)
from .models import Role, User, UserInvite

UserModel = get_user_model()


# ============================================================== Authentication
def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard:home")
    form = LoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = authenticate(request, username=form.cleaned_data["identifier"],
                            password=form.cleaned_data["password"])
        if user is None:
            messages.error(request, "Invalid email/username or password.")
        elif not user.is_active or user.status != "active":
            messages.error(request, "This account is not active. Contact your administrator.")
        else:
            login(request, user)
            next_url = request.GET.get("next", "")
            if next_url and url_has_allowed_host_and_scheme(
                next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
            ):
                return redirect(next_url)
            return redirect("dashboard:home")
    elif request.GET.get("timeout"):
        messages.info(request, "Your session timed out. Please sign in again.")
    return render(request, "registration/login.html", {"form": form})


@require_POST
@login_required
def logout_view(request):
    logout(request)
    messages.success(request, "You have been signed out.")
    return redirect("accounts:login")


def register_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard:home")
    form = TenantRegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        auth_user = authenticate(request, username=user.email,
                                 password=form.cleaned_data["password1"])
        if auth_user is not None:
            login(request, auth_user)
        messages.success(request, f"Welcome to NavERP, {user.get_short_name()}! Your workspace is ready.")
        return redirect("tenants:onboarding")
    return render(request, "registration/register.html", {"form": form})


def forgot_password_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard:home")
    form = ForgotPasswordForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"]
        user = UserModel.objects.filter(email__iexact=email).first()
        if user is not None:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            link = request.build_absolute_uri(
                reverse("accounts:reset_password", args=[uid, token])
            )
            send_mail(
                subject="NavERP — reset your password",
                message=f"Use this link to reset your password:\n\n{link}\n\nIf you didn't request this, ignore this email.",
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
                recipient_list=[email],
                fail_silently=True,
            )
        # Never reveal whether the email exists.
        messages.success(request, "If that email is registered, a reset link has been sent.")
        return redirect("accounts:login")
    return render(request, "registration/forgot_password.html", {"form": form})


def reset_password_view(request, uidb64, token):
    user = None
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = UserModel.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, UserModel.DoesNotExist):
        user = None
    valid = user is not None and default_token_generator.check_token(user, token)
    form = SetPasswordForm(request.POST or None)
    if valid and request.method == "POST" and form.is_valid():
        user.set_password(form.cleaned_data["new_password1"])
        user.save(update_fields=["password"])
        messages.success(request, "Your password has been reset. Please sign in.")
        return redirect("accounts:login")
    return render(request, "registration/reset_password.html", {"form": form, "validlink": valid})


# ================================================================ User mgmt
@tenant_admin_required
def user_list(request):
    return crud_list(
        request, UserModel.objects.filter(tenant=request.tenant).select_related("role"),
        "accounts/user_list.html",
        search_fields=["email", "username", "first_name", "last_name"],
        filters=[("status", "status", False), ("role", "role_id", True)],
        extra_context={"status_choices": UserModel.STATUS_CHOICES,
                       "roles": Role.objects.filter(tenant=request.tenant)},
    )


@tenant_admin_required
def user_create(request):
    return crud_create(request, form_class=UserForm, template="accounts/user_form.html",
                       success_url="accounts:user_list")


@tenant_admin_required
def user_detail(request, pk):
    user_obj = get_object_or_404(UserModel.objects.select_related("role", "party"),
                                 pk=pk, tenant=request.tenant)
    return render(request, "accounts/user_detail.html", {"user_obj": user_obj})


@tenant_admin_required
def user_edit(request, pk):
    return crud_edit(request, model=UserModel, pk=pk, form_class=UserForm,
                     template="accounts/user_form.html", success_url="accounts:user_list")


@tenant_admin_required
@require_POST
def user_delete(request, pk):
    user_obj = get_object_or_404(UserModel, pk=pk, tenant=request.tenant)
    if user_obj == request.user:
        messages.error(request, "You cannot delete your own account.")
    else:
        write_audit_log(request.user, user_obj, "delete")
        user_obj.delete()
        messages.success(request, "User deleted.")
    return redirect("accounts:user_list")


# ===================================================================== Roles
@tenant_admin_required
def role_list(request):
    return crud_list(
        request, Role.objects.filter(tenant=request.tenant).prefetch_related("permissions"),
        "accounts/role_list.html", search_fields=["name", "description"],
    )


@tenant_admin_required
def role_create(request):
    return crud_create(request, form_class=RoleForm, template="accounts/role_form.html",
                       success_url="accounts:role_list")


@tenant_admin_required
def role_detail(request, pk):
    role = get_object_or_404(Role.objects.prefetch_related("permissions"), pk=pk, tenant=request.tenant)
    return render(request, "accounts/role_detail.html", {"obj": role})


@tenant_admin_required
def role_edit(request, pk):
    return crud_edit(request, model=Role, pk=pk, form_class=RoleForm,
                     template="accounts/role_form.html", success_url="accounts:role_list")


@tenant_admin_required
@require_POST
def role_delete(request, pk):
    role = get_object_or_404(Role, pk=pk, tenant=request.tenant)
    if role.is_system:
        messages.error(request, "System roles cannot be deleted.")
    else:
        write_audit_log(request.user, role, "delete")
        role.delete()
        messages.success(request, "Role deleted.")
    return redirect("accounts:role_list")


# =================================================================== Invites
@tenant_admin_required
def invite_list(request):
    return crud_list(
        request, UserInvite.objects.filter(tenant=request.tenant).select_related("role", "invited_by"),
        "accounts/userinvite_list.html",
        search_fields=["email"],
        filters=[("status", "status", False), ("role", "role_id", True)],
        extra_context={"status_choices": UserInvite.STATUS_CHOICES,
                       "roles": Role.objects.filter(tenant=request.tenant)},
    )


@tenant_admin_required
def invite_create(request):
    if request.method == "POST":
        form = UserInviteForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            invite = form.save(commit=False)
            invite.tenant = request.tenant
            invite.invited_by = request.user
            invite.save()
            link = request.build_absolute_uri(reverse("accounts:invite_accept", args=[invite.token]))
            send_mail(
                subject=f"You're invited to {request.tenant.name} on NavERP",
                message=f"Accept your invitation:\n\n{link}\n\nThis link expires in 7 days.",
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
                recipient_list=[invite.email],
                fail_silently=True,
            )
            write_audit_log(request.user, invite, "create")
            messages.success(request, f"Invitation sent to {invite.email}.")
            return redirect("accounts:invite_list")
    else:
        form = UserInviteForm(tenant=request.tenant)
    return render(request, "accounts/userinvite_form.html", {"form": form, "is_edit": False})


@tenant_admin_required
@require_POST
def invite_revoke(request, pk):
    invite = get_object_or_404(UserInvite, pk=pk, tenant=request.tenant)
    invite.status = "revoked"
    invite.save(update_fields=["status"])
    messages.success(request, "Invitation revoked.")
    return redirect("accounts:invite_list")


def invite_accept(request, token):
    # Public endpoint: the token is a 64-char crypto-random secret, so tenant scoping
    # is not applicable here (the token itself authorizes the specific invite).
    invite = get_object_or_404(UserInvite, token=token)
    valid = invite.status == "pending" and not invite.is_expired()
    if invite.status == "pending" and invite.is_expired():
        invite.status = "expired"
        invite.save(update_fields=["status"])
    form = InviteAcceptForm(request.POST or None)
    if valid and request.method == "POST" and form.is_valid():
        user = UserModel.objects.create_user(
            email=invite.email,
            username=form.cleaned_data["username"],
            password=form.cleaned_data["password1"],
            first_name=form.cleaned_data["first_name"],
            last_name=form.cleaned_data.get("last_name", ""),
            tenant=invite.tenant,
            role=invite.role,
        )
        invite.status = "accepted"
        invite.accepted_at = timezone.now()
        invite.save(update_fields=["status", "accepted_at"])
        auth_user = authenticate(request, username=user.email, password=form.cleaned_data["password1"])
        if auth_user is not None:
            login(request, auth_user)
        messages.success(request, f"Welcome to {invite.tenant.name}!")
        return redirect("dashboard:home")
    return render(request, "registration/invite_accept.html",
                  {"form": form, "invite": invite, "valid": valid})


# =================================================================== Profile
@login_required
def profile_view(request):
    form = ProfileForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Profile updated.")
        return redirect("accounts:profile")
    return render(request, "accounts/profile.html", {"form": form, "user_obj": request.user})
