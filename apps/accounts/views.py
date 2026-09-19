"""Authentication, user/role/invite management, and profile views."""
import csv
import datetime
import io

from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.conf import settings
from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpResponse
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

from apps.core.crud import crud_create, crud_delete, crud_edit, crud_list
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log

from .forms import (
    AccessDecisionForm,
    AccessRequestForm,
    AccessReviewForm,
    AccessReviewItemForm,
    ElevationGrantForm,
    ForgotPasswordForm,
    InviteAcceptForm,
    LoginForm,
    MfaChallengeForm,
    MfaSetupForm,
    PasswordPolicyForm,
    ProfileForm,
    RoleForm,
    SetPasswordForm,
    TenantRegisterForm,
    UserForm,
    UserImportForm,
    UserInviteForm,
)
from .models import (
    AccessRequest,
    AccessReview,
    AccessReviewItem,
    ElevationGrant,
    LoginAttempt,
    MfaDevice,
    PasswordPolicy,
    Role,
    User,
    UserImportBatch,
    UserInvite,
    UserSession,
)
from .security import (
    generate_backup_codes,
    generate_secret,
    hash_backup_code,
    provisioning_uri,
    risk_score,
    verify_totp,
)

UserModel = get_user_model()


# ============================================================== Authentication
def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard:home")
    form = LoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        identifier = form.cleaned_data["identifier"]
        user = authenticate(request, username=identifier,
                            password=form.cleaned_data["password"])
        if user is None:
            _record_attempt(request, user=None, identifier=identifier, success=False)
            messages.error(request, "Invalid email/username or password.")
        elif not user.is_active or user.status != "active":
            _record_attempt(request, user=user, identifier=identifier, success=False)
            messages.error(request, "This account is not active. Contact your administrator.")
        else:
            # 0.4 bullet 1: step up when — and only when — the user has a confirmed second factor.
            # A user without one follows exactly the old path, so enabling this feature cannot lock
            # anyone out. The pending marker does NOT authenticate: Django's session stays
            # anonymous until `login()` runs in the challenge view.
            device = _mfa_device_for(user)
            if device is not None:
                request.session["_mfa_pending_user"] = user.pk
                request.session["_mfa_pending_at"] = timezone.now().isoformat()
                # Carry the backend that actually authenticated them. `login()` in the challenge
                # view would otherwise raise "You have multiple authentication backends configured
                # and therefore must provide the `backend` argument", because a user fetched from
                # the DB has no `.backend` attribute — only `authenticate()` sets it.
                request.session["_mfa_pending_backend"] = getattr(user, "backend", None)
                _record_attempt(request, user=user, identifier=identifier, success=True,
                                mfa_challenged=True)
                return redirect("accounts:mfa_challenge")

            login(request, user)
            _open_session(request, user)
            _record_attempt(request, user=user, identifier=identifier, success=True)
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
        "accounts/user/list.html",
        search_fields=["email", "username", "first_name", "last_name"],
        filters=[("status", "status", False), ("role", "role_id", True)],
        extra_context={"status_choices": UserModel.STATUS_CHOICES,
                       "roles": Role.objects.filter(tenant=request.tenant)},
    )


@tenant_admin_required
def user_create(request):
    return crud_create(request, form_class=UserForm, template="accounts/user/form.html",
                       success_url="accounts:user_list")


@tenant_admin_required
def user_detail(request, pk):
    user_obj = get_object_or_404(UserModel.objects.select_related("role", "party"),
                                 pk=pk, tenant=request.tenant)
    return render(request, "accounts/user/detail.html", {"user_obj": user_obj})


@tenant_admin_required
def user_edit(request, pk):
    return crud_edit(request, model=UserModel, pk=pk, form_class=UserForm,
                     template="accounts/user/form.html", success_url="accounts:user_list")


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
        request,
        Role.objects.filter(tenant=request.tenant).annotate(perm_count=Count("permissions")).order_by("name"),
        "accounts/role/list.html", search_fields=["name", "description"],
    )


@tenant_admin_required
def role_create(request):
    return crud_create(request, form_class=RoleForm, template="accounts/role/form.html",
                       success_url="accounts:role_list")


@tenant_admin_required
def role_detail(request, pk):
    role = get_object_or_404(Role.objects.prefetch_related("permissions"), pk=pk, tenant=request.tenant)
    return render(request, "accounts/role/detail.html", {"obj": role})


@tenant_admin_required
def role_edit(request, pk):
    return crud_edit(request, model=Role, pk=pk, form_class=RoleForm,
                     template="accounts/role/form.html", success_url="accounts:role_list")


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
        "accounts/userinvite/list.html",
        search_fields=["email"],
        filters=[("status", "status", False), ("role", "role_id", True)],
        extra_context={"status_choices": UserInvite.STATUS_CHOICES,
                       "roles": Role.objects.filter(tenant=request.tenant)},
    )


@tenant_admin_required
def invite_create(request):
    if request.tenant is None:  # tenant-less superuser must not create orphan invites
        messages.error(request, "Select a tenant workspace before sending invites.")
        return redirect("dashboard:home")
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
    return render(request, "accounts/userinvite/form.html", {"form": form, "is_edit": False})


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
        with transaction.atomic():
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


# ============================================== 0.2 bullet 3: Access Request & Approval
@tenant_admin_required
def access_request_list(request):
    """Admin register: every request in the workspace."""
    return crud_list(
        request,
        AccessRequest.objects.filter(tenant=request.tenant)
        .select_related("requester", "requested_role", "decided_by"),
        "accounts/accessrequest/list.html",
        search_fields=["justification", "requester__email"],
        filters=[("status", "status", False)],
        extra_context={"status_choices": AccessRequest.STATUS_CHOICES},
    )


@login_required
def access_request_mine(request):
    """Self-service lens: a member sees only their own requests.

    Scoped to `request.user` rather than to the tenant on purpose — the whole point of the
    self-service half of bullet 3 is that a member can file and track a request without an admin
    seeing it on their behalf, and without the member seeing anyone else's.
    """
    if request.tenant is None:
        messages.info(request, "Access requests need a tenant workspace.")
        return redirect("dashboard:home")
    qs = (AccessRequest.objects.filter(tenant=request.tenant, requester=request.user)
          .select_related("requested_role", "decided_by"))
    return crud_list(
        request, qs,
        "accounts/accessrequest/mine.html",
        search_fields=["justification"],
        filters=[("status", "status", False)],
        extra_context={"status_choices": AccessRequest.STATUS_CHOICES},
    )


@login_required
def access_request_create(request):
    """A member files a request for THEMSELVES. `requester` is never taken from the form."""
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before requesting access.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = AccessRequestForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.requester = request.user
            obj.status = "pending"
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, "Access request submitted.")
            return redirect("accounts:access_request_mine")
    else:
        form = AccessRequestForm(tenant=request.tenant)
    return render(request, "accounts/accessrequest/form.html", {"form": form, "is_edit": False})


def _get_own_or_admin_request(request, pk):
    """Fetch a request the actor may see: their own, or any one if they are a tenant admin."""
    qs = AccessRequest.objects.filter(tenant=request.tenant)
    obj = get_object_or_404(qs, pk=pk)
    if obj.requester_id != request.user.pk and not _is_tenant_admin(request.user):
        return None
    return obj


def _is_tenant_admin(user):
    return bool(user.is_authenticated and (user.is_tenant_admin or user.is_superuser))


@login_required
def access_request_detail(request, pk):
    obj = _get_own_or_admin_request(request, pk)
    if obj is None:
        messages.error(request, "That access request is not yours to view.")
        return redirect("accounts:access_request_mine")
    # `can_decide` / `is_own` are computed here rather than in the template: the template would
    # otherwise have to re-derive the role rule, and the two would drift.
    return render(request, "accounts/accessrequest/detail.html", {
        "obj": obj,
        "can_decide": _is_tenant_admin(request.user),
        "is_own": obj.requester_id == request.user.pk,
    })


@login_required
def access_request_edit(request, pk):
    obj = _get_own_or_admin_request(request, pk)
    if obj is None:
        messages.error(request, "That access request is not yours to edit.")
        return redirect("accounts:access_request_mine")
    if obj.status != "pending":
        messages.error(request, "A decided request cannot be edited — raise a new one instead.")
        return redirect("accounts:access_request_detail", pk=obj.pk)
    if request.method == "POST":
        form = AccessRequestForm(request.POST, instance=obj, tenant=request.tenant)
        if form.is_valid():
            form.save()
            write_audit_log(request.user, obj, "update")
            messages.success(request, "Access request updated.")
            return redirect("accounts:access_request_detail", pk=obj.pk)
    else:
        form = AccessRequestForm(instance=obj, tenant=request.tenant)
    return render(request, "accounts/accessrequest/form.html",
                  {"form": form, "obj": obj, "is_edit": True})


@require_POST
@login_required
def access_request_delete(request, pk):
    obj = _get_own_or_admin_request(request, pk)
    if obj is None:
        messages.error(request, "That access request is not yours to delete.")
        return redirect("accounts:access_request_mine")
    if obj.status == "approved":
        messages.error(request, "An approved request is the evidence for a live grant — cancel the "
                                "access instead of deleting the record.")
        return redirect("accounts:access_request_detail", pk=obj.pk)
    write_audit_log(request.user, obj, "delete")
    obj.delete()
    messages.success(request, "Access request deleted.")
    return redirect("accounts:access_request_list" if _is_tenant_admin(request.user)
                    else "accounts:access_request_mine")


@require_POST
@tenant_admin_required
def access_request_approve(request, pk):
    """Approve AND grant, in one atomic block.

    The grant is the point of the approval, so they are one write: an approval that did not grant
    (or a grant with no approval behind it) would be a half-truth in the audit trail. `granted_until`
    is stamped from the request's own `requested_days`.
    """
    obj = get_object_or_404(AccessRequest, pk=pk, tenant=request.tenant)
    form = AccessDecisionForm(request.POST)
    if obj.status != "pending":
        messages.error(request, "Only a pending request can be decided.")
        return redirect("accounts:access_request_detail", pk=obj.pk)
    if not form.is_valid():
        messages.error(request, "Could not record that decision.")
        return redirect("accounts:access_request_detail", pk=obj.pk)

    with transaction.atomic():
        obj.status = "approved"
        obj.decided_by = request.user
        obj.decided_at = timezone.now()
        obj.decision_note = form.cleaned_data["note"]
        obj.granted_until = timezone.now() + timezone.timedelta(days=obj.requested_days)
        obj.save(update_fields=["status", "decided_by", "decided_at", "decision_note", "granted_until"])
        if obj.requested_role_id:
            requester = obj.requester
            requester.role = obj.requested_role
            requester.save(update_fields=["role"])
        # AuditLog.action is varchar(10) — the verb goes in `changes` (L41).
        write_audit_log(request.user, obj, "update", changes={"verb": "access_request_approve"})
    messages.success(request, f"Approved — access granted for {obj.requested_days} day(s).")
    return redirect("accounts:access_request_detail", pk=obj.pk)


@require_POST
@tenant_admin_required
def access_request_reject(request, pk):
    """Reject requires a stated reason — a denial nobody can act on is not a decision."""
    obj = get_object_or_404(AccessRequest, pk=pk, tenant=request.tenant)
    form = AccessDecisionForm(request.POST, require_note=True)
    if obj.status != "pending":
        messages.error(request, "Only a pending request can be decided.")
        return redirect("accounts:access_request_detail", pk=obj.pk)
    if not form.is_valid():
        for errs in form.errors.values():
            for e in errs:
                messages.error(request, e)
        return redirect("accounts:access_request_detail", pk=obj.pk)

    obj.status = "rejected"
    obj.decided_by = request.user
    obj.decided_at = timezone.now()
    obj.decision_note = form.cleaned_data["note"]
    obj.save(update_fields=["status", "decided_by", "decided_at", "decision_note"])
    write_audit_log(request.user, obj, "update", changes={"verb": "access_request_reject"})
    messages.success(request, "Request rejected.")
    return redirect("accounts:access_request_detail", pk=obj.pk)


@require_POST
@login_required
def access_request_cancel(request, pk):
    """The requester withdraws their own pending request. No role change, no grant."""
    obj = get_object_or_404(AccessRequest, pk=pk, tenant=request.tenant, requester=request.user)
    if obj.status != "pending":
        messages.error(request, "Only a pending request can be cancelled.")
    else:
        obj.status = "cancelled"
        obj.decided_at = timezone.now()
        obj.save(update_fields=["status", "decided_at"])
        write_audit_log(request.user, obj, "update", changes={"verb": "access_request_cancel"})
        messages.success(request, "Request cancelled.")
    return redirect("accounts:access_request_mine")


# ================================================= 0.2 bullet 5: Privileged Access Management
@tenant_admin_required
def elevation_list(request):
    return crud_list(
        request,
        ElevationGrant.objects.filter(tenant=request.tenant)
        .select_related("user", "requested_by", "approved_by"),
        "accounts/elevation/list.html",
        search_fields=["reason", "user__email"],
        filters=[("status", "status", False), ("scope", "scope", False)],
        extra_context={"status_choices": ElevationGrant.STATUS_CHOICES,
                       "scope_choices": ElevationGrant.SCOPE_CHOICES},
    )


@tenant_admin_required
def elevation_detail(request, pk):
    obj = get_object_or_404(
        ElevationGrant.objects.select_related("user", "requested_by", "approved_by", "revoked_by"),
        pk=pk, tenant=request.tenant,
    )
    return render(request, "accounts/elevation/detail.html", {"obj": obj})


@tenant_admin_required
def elevation_create(request):
    return crud_create(request, form_class=ElevationGrantForm,
                       template="accounts/elevation/form.html",
                       success_url="accounts:elevation_list")


@tenant_admin_required
def elevation_edit(request, pk):
    obj = get_object_or_404(ElevationGrant, pk=pk, tenant=request.tenant)
    if obj.status != "pending":
        messages.error(request, "A decided elevation is frozen evidence and cannot be edited.")
        return redirect("accounts:elevation_detail", pk=obj.pk)
    return crud_edit(request, model=ElevationGrant, pk=pk, form_class=ElevationGrantForm,
                     template="accounts/elevation/form.html", success_url="accounts:elevation_list")


@require_POST
@tenant_admin_required
def elevation_delete(request, pk):
    obj = get_object_or_404(ElevationGrant, pk=pk, tenant=request.tenant)
    if obj.status != "pending":
        messages.error(request, "A decided elevation is frozen evidence and cannot be deleted.")
        return redirect("accounts:elevation_detail", pk=obj.pk)
    return crud_delete(request, model=ElevationGrant, pk=pk, success_url="accounts:elevation_list")


@require_POST
@tenant_admin_required
def elevation_approve(request, pk):
    """Opens the window. Deliberately does NOT flip `User.is_tenant_admin`.

    A silent privilege change on a timer (or on approval) is worse than an explicit one: the repo
    has no scheduler, so the flag would never come back off. `is_live` reports the open window and
    the admin applies the privilege, which keeps the change auditable.
    """
    obj = get_object_or_404(ElevationGrant, pk=pk, tenant=request.tenant)
    if obj.status != "pending":
        messages.error(request, "Only a pending elevation can be approved.")
        return redirect("accounts:elevation_detail", pk=obj.pk)
    obj.status = "active"
    obj.approved_by = request.user
    obj.approved_at = timezone.now()
    obj.save(update_fields=["status", "approved_by", "approved_at"])
    write_audit_log(request.user, obj, "update", changes={"verb": "elevation_approve"})
    messages.success(request, "Elevation approved. It is live only inside its window.")
    return redirect("accounts:elevation_detail", pk=obj.pk)


@require_POST
@tenant_admin_required
def elevation_revoke(request, pk):
    obj = get_object_or_404(ElevationGrant, pk=pk, tenant=request.tenant)
    if obj.status not in ("pending", "active"):
        messages.error(request, "That elevation is already closed.")
        return redirect("accounts:elevation_detail", pk=obj.pk)
    obj.status = "revoked"
    obj.revoked_by = request.user
    obj.revoked_at = timezone.now()
    obj.save(update_fields=["status", "revoked_by", "revoked_at"])
    write_audit_log(request.user, obj, "update", changes={"verb": "elevation_revoke"})
    messages.success(request, "Elevation revoked.")
    return redirect("accounts:elevation_detail", pk=obj.pk)


# ============================================= 0.2 bullet 4: Access Certification & Reviews
@tenant_admin_required
def access_review_list(request):
    return crud_list(
        request,
        AccessReview.objects.filter(tenant=request.tenant)
        .select_related("scope_role", "created_by").annotate(item_count=Count("items")),
        "accounts/accessreview/list.html",
        search_fields=["name"],
        filters=[("status", "status", False)],
        extra_context={"status_choices": AccessReview.STATUS_CHOICES},
    )


@tenant_admin_required
def access_review_detail(request, pk):
    obj = get_object_or_404(AccessReview.objects.select_related("scope_role"), pk=pk,
                            tenant=request.tenant)
    # `select_related` on the FK and a single prefetch of the items: the detail page renders every
    # line and the attest/revoke forms read `item.user`, so an un-prefetched loop would be one
    # query per row.
    items = (obj.items.select_related("user", "role", "decided_by")
             .order_by("user__email"))
    return render(request, "accounts/accessreview/detail.html", {"obj": obj, "items": items})


@tenant_admin_required
def access_review_create(request):
    return crud_create(request, form_class=AccessReviewForm,
                       template="accounts/accessreview/form.html",
                       success_url="accounts:access_review_list")


@tenant_admin_required
def access_review_edit(request, pk):
    obj = get_object_or_404(AccessReview, pk=pk, tenant=request.tenant)
    if obj.status == "closed":
        messages.error(request, "A closed campaign is frozen evidence and cannot be edited.")
        return redirect("accounts:access_review_detail", pk=obj.pk)
    return crud_edit(request, model=AccessReview, pk=pk, form_class=AccessReviewForm,
                     template="accounts/accessreview/form.html",
                     success_url="accounts:access_review_list")


@require_POST
@tenant_admin_required
def access_review_delete(request, pk):
    obj = get_object_or_404(AccessReview, pk=pk, tenant=request.tenant)
    if obj.status == "closed":
        messages.error(request, "A closed campaign is frozen evidence and cannot be deleted.")
        return redirect("accounts:access_review_detail", pk=obj.pk)
    return crud_delete(request, model=AccessReview, pk=pk,
                       success_url="accounts:access_review_list")


@require_POST
@tenant_admin_required
def access_review_generate(request, pk):
    """Materialise one item per member in scope, snapshotting the role they hold NOW.

    Explicit rather than implicit: the reviewed population is a recorded decision, not whatever
    the user table happens to contain when someone opens the page. Re-running is idempotent — the
    `unique_together (review, user)` means an existing item keeps its decision instead of being
    reset, so a second generate cannot wipe an attestation.
    """
    obj = get_object_or_404(AccessReview, pk=pk, tenant=request.tenant)
    if obj.status == "closed":
        messages.error(request, "A closed campaign cannot be regenerated.")
        return redirect("accounts:access_review_detail", pk=obj.pk)

    users = User.objects.filter(tenant=request.tenant)
    if obj.scope_role_id:
        users = users.filter(role=obj.scope_role)
    existing = set(obj.items.values_list("user_id", flat=True))
    created = 0
    with transaction.atomic():
        for user in users.only("id", "role_id"):
            if user.pk in existing:
                continue
            AccessReviewItem.objects.create(
                tenant=request.tenant, review=obj, user=user, role_id=user.role_id,
            )
            created += 1
        if obj.status == "draft":
            obj.status = "open"
            obj.save(update_fields=["status"])
    write_audit_log(request.user, obj, "update",
                    changes={"verb": "access_review_generate", "created": created})
    messages.success(request, f"Generated {created} review item(s).")
    return redirect("accounts:access_review_detail", pk=obj.pk)


@require_POST
@tenant_admin_required
def access_review_close(request, pk):
    obj = get_object_or_404(AccessReview, pk=pk, tenant=request.tenant)
    if obj.status == "closed":
        messages.info(request, "That campaign is already closed.")
        return redirect("accounts:access_review_detail", pk=obj.pk)
    undecided = obj.items.filter(decision="pending").count()
    obj.status = "closed"
    obj.closed_at = timezone.now()
    obj.save(update_fields=["status", "closed_at"])
    write_audit_log(request.user, obj, "update",
                    changes={"verb": "access_review_close", "undecided": undecided})
    if undecided:
        messages.warning(request, f"Campaign closed with {undecided} line(s) still undecided — "
                                  "they stay on the record as undecided.")
    else:
        messages.success(request, "Campaign closed.")
    return redirect("accounts:access_review_detail", pk=obj.pk)


@require_POST
@tenant_admin_required
def access_review_item_attest(request, pk):
    """Confirm the member should keep the entitlement. No access change."""
    item = get_object_or_404(AccessReviewItem.objects.select_related("review"), pk=pk,
                             tenant=request.tenant)
    if item.review.status == "closed":
        messages.error(request, "That campaign is closed.")
        return redirect("accounts:access_review_detail", pk=item.review_id)
    form = AccessReviewItemForm(request.POST, instance=item, tenant=request.tenant)
    item.decision = "attest"
    item.decided_by = request.user
    item.decided_at = timezone.now()
    if form.is_valid():
        item.note = form.cleaned_data.get("note", "")
    item.save(update_fields=["decision", "decided_by", "decided_at", "note"])
    write_audit_log(request.user, item, "update", changes={"verb": "access_review_item_attest"})
    messages.success(request, f"Attested access for {item.user}.")
    return redirect("accounts:access_review_detail", pk=item.review_id)


@require_POST
@tenant_admin_required
def access_review_item_revoke(request, pk):
    """Revoke the entitlement — and actually revoke it.

    A certification decision that changed nothing would be theatre, so this clears the member's
    role when it still matches the snapshot. The snapshot is what was reviewed, so a role that has
    since changed is left alone: revoking a grant nobody reviewed would be worse than the bug.
    """
    item = get_object_or_404(AccessReviewItem.objects.select_related("review", "user"), pk=pk,
                             tenant=request.tenant)
    if item.review.status == "closed":
        messages.error(request, "That campaign is closed.")
        return redirect("accounts:access_review_detail", pk=item.review_id)
    form = AccessReviewItemForm(request.POST, instance=item, tenant=request.tenant)

    with transaction.atomic():
        item.decision = "revoke"
        item.decided_by = request.user
        item.decided_at = timezone.now()
        if form.is_valid():
            item.note = form.cleaned_data.get("note", "")
        item.save(update_fields=["decision", "decided_by", "decided_at", "note"])

        cleared = False
        user = item.user
        if user.role_id is not None and user.role_id == item.role_id:
            user.role = None
            user.save(update_fields=["role"])
            cleared = True
        write_audit_log(request.user, item, "update",
                        changes={"verb": "access_review_item_revoke", "role_cleared": cleared})
    messages.success(request, f"Revoked access for {item.user}."
                     + (" Role cleared." if cleared else " Their role had already changed — left as is."))
    return redirect("accounts:access_review_detail", pk=item.review_id)


@tenant_admin_required
def orphan_accounts(request):
    """Computed orphan-account board — bullet 4's third capability. No model.

    Four shapes, each a real leak rather than a style preference:
      * an ACTIVE member holding no role (can log in, cannot do anything — usually a provisioning miss);
      * a SUSPENDED/ARCHIVED member still holding a role (the offboarding half that never ran);
      * an ACTIVE member who has never signed in (a licence that was never used);
      * an APPROVED access request whose grant window has closed while the role is still assigned
        (a time-bound grant that outlived its window — the cross-check bullet 3 and bullet 4 make
        possible only together).
    """
    base = User.objects.filter(tenant=request.tenant).select_related("role")

    no_role = base.filter(status="active", role__isnull=True)
    stale_role = base.exclude(status="active").filter(role__isnull=False)
    never_signed_in = base.filter(status="active", last_login__isnull=True)

    expired_grants = (AccessRequest.objects
                      .filter(tenant=request.tenant, status="approved", granted_until__lt=timezone.now())
                      .exclude(requester__role__isnull=True)
                      .select_related("requester", "requested_role", "decided_by"))

    context = {
        "no_role": no_role,
        "stale_role": stale_role,
        "never_signed_in": never_signed_in,
        "expired_grants": expired_grants,
        "orphan_total": no_role.count() + stale_role.count(),
    }
    return render(request, "accounts/orphans.html", context)


# ================================================= 0.2 bullet 2: bulk provisioning
@require_POST
@tenant_admin_required
def user_deprovision(request, pk):
    """Offboarding: suspend or archive a member and close everything that granted them access.

    De-provisioning is more than a status flip — the point is that nothing they were granted keeps
    working. So one atomic action sets the status, clears the role, revokes their live elevations
    and cancels their pending requests. Approving requests stay as they are: they are the evidence
    of what was granted and when.
    """
    user_obj = get_object_or_404(UserModel, pk=pk, tenant=request.tenant)
    target_status = request.POST.get("status", "suspended")
    if target_status not in ("suspended", "archived"):
        messages.error(request, "Choose suspend or archive.")
        return redirect("accounts:user_detail", pk=user_obj.pk)
    if user_obj == request.user:
        messages.error(request, "You cannot de-provision your own account.")
        return redirect("accounts:user_detail", pk=user_obj.pk)

    with transaction.atomic():
        user_obj.status = target_status
        user_obj.role = None
        user_obj.is_tenant_admin = False
        user_obj.save(update_fields=["status", "role", "is_tenant_admin"])

        revoked = (ElevationGrant.objects
                   .filter(tenant=request.tenant, user=user_obj, status__in=("pending", "active"))
                   .update(status="revoked", revoked_at=timezone.now(), revoked_by=request.user))
        cancelled = (AccessRequest.objects
                     .filter(tenant=request.tenant, requester=user_obj, status="pending")
                     .update(status="cancelled", decided_at=timezone.now()))
        write_audit_log(request.user, user_obj, "update",
                        changes={"verb": "user_deprovision", "status": target_status,
                                 "elevations_revoked": revoked, "requests_cancelled": cancelled})
    messages.success(request, f"{user_obj} de-provisioned ({target_status}); "
                              f"{revoked} elevation(s) revoked, {cancelled} request(s) cancelled.")
    return redirect("accounts:user_detail", pk=user_obj.pk)


#: Accepted header names, in order, for the bulk import. Kept as a constant so the export and the
#: import cannot drift apart — the export writes exactly these columns.
IMPORT_COLUMNS = ["email", "username", "first_name", "last_name", "role"]


@tenant_admin_required
def user_import(request):
    """Stage a CSV of new members. Validates row by row and writes NO users yet."""
    if request.method == "POST":
        form = UserImportForm(request.POST, request.FILES)
        if form.is_valid():
            upload = form.cleaned_data["csv_file"]
            try:
                text = upload.read().decode("utf-8-sig")
            except UnicodeDecodeError:
                messages.error(request, "That file is not UTF-8 encoded.")
                return render(request, "accounts/userimport/form.html", {"form": form})

            reader = csv.DictReader(io.StringIO(text))
            missing = [c for c in ("email", "username") if c not in (reader.fieldnames or [])]
            if missing:
                messages.error(request, f"Missing required column(s): {', '.join(missing)}.")
                return render(request, "accounts/userimport/form.html", {"form": form})

            roles = {r.name.lower(): r for r in Role.objects.filter(tenant=request.tenant)}
            seen_emails, seen_usernames, staged, errors = set(), set(), [], []
            for lineno, row in enumerate(reader, start=2):  # line 1 is the header
                email = (row.get("email") or "").strip().lower()
                username = (row.get("username") or "").strip()
                role_name = (row.get("role") or "").strip().lower()

                if not email or "@" not in email:
                    errors.append({"line": lineno, "error": "missing or invalid email"})
                    continue
                if not username:
                    errors.append({"line": lineno, "error": "missing username"})
                    continue
                if email in seen_emails or UserModel.objects.filter(email=email).exists():
                    errors.append({"line": lineno, "error": f"email already exists: {email}"})
                    continue
                if username in seen_usernames or UserModel.objects.filter(username=username).exists():
                    errors.append({"line": lineno, "error": f"username already exists: {username}"})
                    continue
                role = None
                if role_name:
                    role = roles.get(role_name)
                    if role is None:
                        errors.append({"line": lineno, "error": f"unknown role: {role_name}"})
                        continue
                seen_emails.add(email)
                seen_usernames.add(username)
                staged.append({
                    "email": email, "username": username,
                    "first_name": (row.get("first_name") or "").strip(),
                    "last_name": (row.get("last_name") or "").strip(),
                    "role_id": role.pk if role else None,
                })

            batch = UserImportBatch.objects.create(
                tenant=request.tenant, file_name=upload.name, uploaded_by=request.user,
                status="validated", row_count=len(staged) + len(errors),
                error_count=len(errors), errors=errors, staged_rows=staged,
            )
            write_audit_log(request.user, batch, "create")
            messages.success(request, f"Validated {len(staged)} row(s), {len(errors)} error(s). "
                                      "Review, then commit.")
            return redirect("accounts:user_import_detail", pk=batch.pk)
    else:
        form = UserImportForm()
    return render(request, "accounts/userimport/form.html", {"form": form})


@tenant_admin_required
def user_import_list(request):
    return crud_list(
        request,
        UserImportBatch.objects.filter(tenant=request.tenant).select_related("uploaded_by"),
        "accounts/userimport/list.html",
        search_fields=["file_name"],
        filters=[("status", "status", False)],
        extra_context={"status_choices": UserImportBatch.STATUS_CHOICES},
    )


@tenant_admin_required
def user_import_detail(request, pk):
    obj = get_object_or_404(UserImportBatch.objects.select_related("uploaded_by"), pk=pk,
                            tenant=request.tenant)
    return render(request, "accounts/userimport/detail.html",
                  {"obj": obj, "columns": IMPORT_COLUMNS})


@require_POST
@tenant_admin_required
def user_import_commit(request, pk):
    """Write the staged rows as real members.

    Every created user gets an UNUSABLE password: a bulk import is a provisioning step, not a
    credential hand-out, so the account cannot be logged into until the person completes the
    invite/password-reset flow. Setting a shared default password would be the bug here.
    """
    batch = get_object_or_404(UserImportBatch, pk=pk, tenant=request.tenant)
    if batch.status == "committed":
        messages.info(request, "That batch is already committed.")
        return redirect("accounts:user_import_detail", pk=batch.pk)
    if not batch.staged_rows:
        messages.error(request, "Nothing to commit — the batch has no valid rows.")
        return redirect("accounts:user_import_detail", pk=batch.pk)

    created = 0
    with transaction.atomic():
        for row in batch.staged_rows:
            # Re-check under the write: another session may have taken the email since validation.
            if UserModel.objects.filter(email=row["email"]).exists():
                continue
            user_obj = UserModel(
                tenant=request.tenant, email=row["email"], username=row["username"],
                first_name=row.get("first_name", ""), last_name=row.get("last_name", ""),
                role_id=row.get("role_id"), status="active",
            )
            user_obj.set_unusable_password()
            user_obj.save()
            created += 1
        batch.status = "committed"
        batch.created_count = created
        batch.committed_at = timezone.now()
        batch.save(update_fields=["status", "created_count", "committed_at"])
        write_audit_log(request.user, batch, "update",
                        changes={"verb": "user_import_commit", "created": created})
    messages.success(request, f"Committed {created} member(s). They must set a password to sign in.")
    return redirect("accounts:user_import_detail", pk=batch.pk)


@tenant_admin_required
def user_export(request):
    """CSV export of the directory — the other half of bullet 2's import/export.

    Writes exactly `IMPORT_COLUMNS`, so an exported file can be edited and fed straight back into
    the importer without a column-mapping step.
    """
    response = HttpResponse(content_type="text/csv")
    stamp = timezone.localdate().isoformat()
    response["Content-Disposition"] = f'attachment; filename="users-{request.tenant.slug}-{stamp}.csv"'
    # No sensitive column is exported: never a password hash, token or session key.
    writer = csv.writer(response)
    writer.writerow(IMPORT_COLUMNS)
    users = (UserModel.objects.filter(tenant=request.tenant)
             .select_related("role").order_by("email"))
    for user_obj in users:
        writer.writerow([
            user_obj.email, user_obj.username, user_obj.first_name, user_obj.last_name,
            user_obj.role.name if user_obj.role else "",
        ])
    write_audit_log(request.user, None, "update",
                    changes={"verb": "user_export", "rows": users.count()})
    return response


# ==================================================== 0.4 Authentication & SSO
def _client_ip(request):
    """The client address. X-Forwarded-For is read ONLY when USE_X_FORWARDED_HOST-style trust is
    configured, because an untrusted header would let anyone forge their own risk signal."""
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded and getattr(settings, "TRUST_X_FORWARDED_FOR", False):
        return forwarded.split(",")[0].strip()[:45]
    return (request.META.get("REMOTE_ADDR") or "")[:45] or None


def _user_agent(request):
    return (request.META.get("HTTP_USER_AGENT") or "")[:255]


def _mfa_device_for(user):
    """The user's confirmed, active second factor, if any.

    Its EXISTENCE is what triggers the step-up — so a user without one is unaffected by this
    feature entirely. That is the safety property that keeps a foundation change from locking
    anyone out.
    """
    return (MfaDevice.objects.filter(user=user, is_active=True, confirmed_at__isnull=False)
            .order_by("id").first())


def _record_attempt(request, *, user, identifier, success, mfa_challenged=False):
    """Write the attempt with its risk score. Never raises: an audit write must not break a login.

    When `authenticate()` returns None we cannot tell "no such account" from "wrong password", so
    `user` arrives as None either way. Resolving the identifier back to an account here is what
    makes a failed attempt VISIBLE: `request.tenant` is None for an anonymous request, so without
    this every failure would be written with `tenant=NULL` and never appear in any workspace's
    register — which is precisely the case the register exists to surface. It leaks nothing new:
    `authenticate()` already performed this same lookup.
    """
    ip = _client_ip(request)
    ua = _user_agent(request)
    try:
        if user is None and identifier:
            user = (UserModel.objects
                    .filter(Q(email__iexact=identifier) | Q(username__iexact=identifier))
                    .order_by("id").first())
        seen_ips, seen_agents = set(), set()
        if user is not None:
            prior = (LoginAttempt.objects.filter(user=user, success=True)
                     .order_by("-created_at").values_list("ip", "user_agent")[:50])
            for p_ip, p_ua in prior:
                if p_ip:
                    seen_ips.add(p_ip)
                if p_ua:
                    seen_agents.add(p_ua)
        failures = LoginAttempt.objects.filter(
            identifier=identifier, success=False,
            created_at__gte=timezone.now() - timezone.timedelta(minutes=15)).count()
        score, reasons = risk_score(ip=ip, user_agent=ua, seen_ips=seen_ips,
                                    seen_agents=seen_agents, recent_failure_count=failures)
        LoginAttempt.objects.create(
            # Attribute to the probed account's workspace so the attempt is visible there. An
            # identifier matching NO account genuinely cannot be attributed to a tenant in a
            # shared-schema design, and is left NULL rather than guessed at.
            tenant=getattr(user, "tenant", None) or getattr(request, "tenant", None),
            user=user, identifier=(identifier or "")[:255], ip=ip, user_agent=ua,
            success=success, risk_score=score, risk_reasons=reasons,
            mfa_challenged=mfa_challenged,
        )
    except Exception:  # pragma: no cover - never let telemetry break authentication
        pass


def _open_session(request, user):
    """Register the sign-in so it can be seen and revoked.

    Called AFTER `login()`, because `login()` cycles the session key — recording before it would
    store a key that no longer exists.
    """
    try:
        if request.session.session_key:
            UserSession.objects.update_or_create(
                session_key=request.session.session_key,
                defaults={"tenant": user.tenant, "user": user,
                          "ip": _client_ip(request), "user_agent": _user_agent(request)},
            )
    except Exception:  # pragma: no cover - never let telemetry break authentication
        pass


#: How long a pending MFA challenge stays valid. A marker left open indefinitely would let a
#: half-finished login be resumed much later.
MFA_PENDING_MAX_AGE = 300


@login_required
def mfa_setup(request):
    """Enrol a TOTP device. Creates an UNCONFIRMED device, so it cannot lock anyone out.

    The device only starts being required once a code has been verified (`mfa_confirm`), which is
    what stops a mistyped or unscanned secret from locking the user out of their own account.
    """
    if request.tenant is None:
        messages.info(request, "MFA applies to a tenant workspace.")
        return redirect("dashboard:home")
    device = MfaDevice.objects.filter(user=request.user, is_active=True).first()
    if device and device.is_confirmed:
        return redirect("accounts:mfa_manage")

    if request.method == "POST":
        form = MfaSetupForm(request.POST)
        if form.is_valid():
            secret = generate_secret()
            device = device or MfaDevice(tenant=request.tenant, user=request.user)
            device.name = form.cleaned_data.get("name", "")
            device.is_active = True
            device.confirmed_at = None
            device.set_secret(secret)
            device.save()
            # The plaintext secret is shown ONCE here; only its encrypted form is stored.
            return render(request, "accounts/mfa/setup_confirm.html", {
                "device": device, "secret": secret,
                "uri": provisioning_uri(secret, request.user.email),
                "form": MfaChallengeForm(),
            })
    else:
        form = MfaSetupForm()
    return render(request, "accounts/mfa/setup.html", {"form": form})


@login_required
def mfa_confirm(request):
    """Verify a code to activate the device. The ONLY writer of `confirmed_at`."""
    device = MfaDevice.objects.filter(user=request.user, is_active=True,
                                      confirmed_at__isnull=True).order_by("-id").first()
    if device is None:
        messages.error(request, "Start the setup again — there is no device awaiting confirmation.")
        return redirect("accounts:mfa_setup")
    if request.method != "POST":
        return redirect("accounts:mfa_setup")

    form = MfaChallengeForm(request.POST)
    if not form.is_valid():
        return render(request, "accounts/mfa/setup_confirm.html", {
            "device": device, "secret": device.get_secret(),
            "uri": provisioning_uri(device.get_secret(), request.user.email), "form": form,
        })
    counter = verify_totp(device.get_secret(), form.cleaned_data["code"])
    if counter is None:
        form.add_error("code", "That code is not valid. Check your device clock and try again.")
        return render(request, "accounts/mfa/setup_confirm.html", {
            "device": device, "secret": device.get_secret(),
            "uri": provisioning_uri(device.get_secret(), request.user.email), "form": form,
        })

    codes = generate_backup_codes()
    device.backup_code_hashes = [hash_backup_code(c) for c in codes]
    device.confirmed_at = timezone.now()
    device.last_counter = counter
    device.save(update_fields=["backup_code_hashes", "confirmed_at", "last_counter"])
    write_audit_log(request.user, device, "update", changes={"verb": "mfa_confirm"})
    # Backup codes are shown exactly once — only their hashes persist.
    return render(request, "accounts/mfa/backup_codes.html", {"codes": codes})


@login_required
def mfa_manage(request):
    device = MfaDevice.objects.filter(user=request.user, is_active=True).first()
    sessions = UserSession.objects.filter(user=request.user).select_related("revoked_by")[:20]
    return render(request, "accounts/mfa/manage.html", {"device": device, "sessions": sessions})


def mfa_challenge(request):
    """The login step-up. Unauthenticated by design — the user is not signed in yet."""
    uid = request.session.get("_mfa_pending_user")
    issued = request.session.get("_mfa_pending_at")
    if not uid:
        return redirect("accounts:login")

    # Expire a stale half-finished login rather than letting it be resumed later.
    try:
        issued_at = datetime.datetime.fromisoformat(issued)
        if (timezone.now() - issued_at).total_seconds() > MFA_PENDING_MAX_AGE:
            for key in ("_mfa_pending_user", "_mfa_pending_at", "_mfa_pending_backend"):
                request.session.pop(key, None)
            messages.error(request, "That sign-in attempt expired. Please sign in again.")
            return redirect("accounts:login")
    except (TypeError, ValueError):
        return redirect("accounts:login")

    user_obj = UserModel.objects.filter(pk=uid, is_active=True).first()
    device = _mfa_device_for(user_obj) if user_obj else None
    if user_obj is None or device is None:
        for key in ("_mfa_pending_user", "_mfa_pending_at", "_mfa_pending_backend"):
            request.session.pop(key, None)
        return redirect("accounts:login")

    form = MfaChallengeForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        raw = form.cleaned_data["code"].strip()
        counter = verify_totp(device.get_secret(), raw)
        used_backup = False
        if counter is None:
            # Fall back to a single-use backup code, consumed on match.
            digest = hash_backup_code(raw)
            if digest in (device.backup_code_hashes or []):
                remaining = [h for h in device.backup_code_hashes if h != digest]
                device.backup_code_hashes = remaining
                device.save(update_fields=["backup_code_hashes"])
                used_backup = True
        if counter is None and not used_backup:
            form.add_error("code", "That code is not valid.")
            _record_attempt(request, user=user_obj, identifier=user_obj.email, success=False,
                            mfa_challenged=True)
            return render(request, "accounts/mfa/challenge.html", {"form": form})

        if not used_backup:
            # Refuse a replay inside the same 30s window.
            if device.last_counter is not None and counter <= device.last_counter:
                form.add_error("code", "That code has already been used. Wait for the next one.")
                return render(request, "accounts/mfa/challenge.html", {"form": form})
            device.last_counter = counter
        device.last_used_at = timezone.now()
        device.save(update_fields=["last_counter", "last_used_at"])

        backend = request.session.get("_mfa_pending_backend") or settings.AUTHENTICATION_BACKENDS[0]
        for key in ("_mfa_pending_user", "_mfa_pending_at", "_mfa_pending_backend"):
            request.session.pop(key, None)
        login(request, user_obj, backend=backend)
        _open_session(request, user_obj)
        _record_attempt(request, user=user_obj, identifier=user_obj.email, success=True,
                        mfa_challenged=True)
        if used_backup:
            messages.warning(request, "Signed in with a backup code — it has now been used up.")
        return redirect("dashboard:home")
    return render(request, "accounts/mfa/challenge.html", {"form": form})


@require_POST
@login_required
def mfa_disable(request):
    """Turn MFA off for the signed-in user. Admin-gated? No — it is their own factor, but a
    tenant admin is notified via the audit log, which is the record that matters."""
    device = MfaDevice.objects.filter(user=request.user, is_active=True).first()
    if device is None:
        messages.info(request, "MFA is not enabled on your account.")
        return redirect("accounts:mfa_manage")
    device.is_active = False
    device.confirmed_at = None
    device.backup_code_hashes = []
    device.save(update_fields=["is_active", "confirmed_at", "backup_code_hashes"])
    write_audit_log(request.user, device, "update", changes={"verb": "mfa_disable"})
    messages.success(request, "Two-factor authentication disabled.")
    return redirect("accounts:mfa_manage")


@require_POST
@login_required
def mfa_regenerate_backup(request):
    """Issue a fresh set of recovery codes, invalidating the old ones."""
    device = _mfa_device_for(request.user)
    if device is None:
        messages.error(request, "Enable MFA before generating recovery codes.")
        return redirect("accounts:mfa_manage")
    codes = generate_backup_codes()
    device.backup_code_hashes = [hash_backup_code(c) for c in codes]
    device.save(update_fields=["backup_code_hashes"])
    write_audit_log(request.user, device, "update", changes={"verb": "mfa_regenerate_backup"})
    return render(request, "accounts/mfa/backup_codes.html", {"codes": codes})


# ---------------------------------------------------------------- sessions
@login_required
def session_list(request):
    """The signed-in user's own sessions. A tenant admin additionally sees the whole workspace."""
    if request.tenant is None:
        messages.info(request, "Sessions belong to a tenant workspace.")
        return redirect("dashboard:home")
    qs = UserSession.objects.filter(tenant=request.tenant).select_related("user", "revoked_by")
    if not _is_tenant_admin(request.user):
        qs = qs.filter(user=request.user)
    else:
        user_filter = request.GET.get("user", "").strip()
        if user_filter.isdigit():
            qs = qs.filter(user_id=int(user_filter))
    return crud_list(
        request, qs, "accounts/session/list.html",
        search_fields=["ip", "user_agent", "user__email"],
        extra_context={"current_session_key": request.session.session_key,
                       "members": UserModel.objects.filter(tenant=request.tenant).order_by("email")
                       if _is_tenant_admin(request.user) else []},
    )


@require_POST
@login_required
def session_revoke(request, pk):
    """Kill one session. Scoped to the actor: a member may only revoke their own.

    Enforcement is by DELETING the Django session row, not by a middleware. `SESSION_ENGINE` is
    `sessions.backends.db`, so the row IS the session — removing it ends that session on the
    victim's very next request, with no per-request revocation lookup added to the hot path.
    """
    from django.contrib.sessions.models import Session

    qs = UserSession.objects.filter(tenant=request.tenant)
    if not _is_tenant_admin(request.user):
        qs = qs.filter(user=request.user)
    obj = get_object_or_404(qs, pk=pk)
    if obj.is_revoked:
        messages.info(request, "That session is already revoked.")
        return redirect("accounts:session_list")

    obj.revoked_at = timezone.now()
    obj.revoked_by = request.user
    obj.save(update_fields=["revoked_at", "revoked_by"])
    Session.objects.filter(session_key=obj.session_key).delete()

    is_own = obj.session_key == request.session.session_key
    write_audit_log(request.user, obj, "update", changes={"verb": "session_revoke"})
    if is_own:
        # The actor just killed the session making this request; a redirect to a login page would
        # be the only honest next step.
        logout(request)
        messages.success(request, "That session was yours and has been signed out.")
        return redirect("accounts:login")
    messages.success(request, "Session revoked.")
    return redirect("accounts:session_list")


@require_POST
@login_required
def session_revoke_others(request):
    """Sign out everywhere else, keeping the current session."""
    from django.contrib.sessions.models import Session

    qs = UserSession.objects.filter(user=request.user, revoked_at__isnull=True)
    if request.session.session_key:
        qs = qs.exclude(session_key=request.session.session_key)
    keys = list(qs.values_list("session_key", flat=True))
    count = qs.update(revoked_at=timezone.now(), revoked_by=request.user)
    # Delete the Django sessions too, so the sign-out is immediate rather than cosmetic.
    Session.objects.filter(session_key__in=keys).delete()
    write_audit_log(request.user, None, "update",
                    changes={"verb": "session_revoke_others", "count": count})
    messages.success(request, f"Signed out {count} other session(s).")
    return redirect("accounts:session_list")


# ---------------------------------------------------------------- risk register + policy
@tenant_admin_required
def login_attempt_list(request):
    """The adaptive-auth register: every attempt with the score it earned.

    This is the surface bullet 5 actually needs. Blocking on a heuristic would be worse than
    showing it — an admin can see the pattern and act, and nothing locks a real user out.
    """
    qs = LoginAttempt.objects.filter(tenant=request.tenant).select_related("user")
    only_risky = request.GET.get("risky", "").strip()
    if only_risky in ("yes", "no"):
        from apps.accounts.security import RISK_STEP_UP_THRESHOLD
        if only_risky == "yes":
            qs = qs.filter(risk_score__gte=RISK_STEP_UP_THRESHOLD)
        else:
            qs = qs.filter(risk_score__lt=RISK_STEP_UP_THRESHOLD)
    return crud_list(
        request, qs, "accounts/loginattempt/list.html",
        search_fields=["identifier", "ip"],
        filters=[("success", "success", False)],
        extra_context={"risky_choices": [("yes", "Risky only"), ("no", "Normal only")]},
    )


@tenant_admin_required
def password_policy_edit(request):
    """Edit the workspace credential policy."""
    if request.tenant is None:
        messages.info(request, "A password policy belongs to a tenant workspace.")
        return redirect("dashboard:home")
    policy, _ = PasswordPolicy.objects.get_or_create(tenant=request.tenant)
    if request.method == "POST":
        form = PasswordPolicyForm(request.POST, instance=policy, tenant=request.tenant)
        if form.is_valid():
            form.save()
            write_audit_log(request.user, policy, "update", changes={"verb": "password_policy_edit"})
            messages.success(request, "Password policy saved.")
            return redirect("accounts:security_overview")
    else:
        form = PasswordPolicyForm(instance=policy, tenant=request.tenant)
    return render(request, "accounts/passwordpolicy/form.html", {"form": form, "obj": policy})


@tenant_admin_required
def security_overview(request):
    """Computed hub for 0.4 — no table. Reports posture and says what is NOT built."""
    if request.tenant is None:
        messages.info(request, "Security posture applies to a tenant workspace.")
        return redirect("dashboard:home")
    policy = PasswordPolicy.objects.filter(tenant=request.tenant).first()
    attempts = LoginAttempt.objects.filter(tenant=request.tenant)
    sessions = UserSession.objects.filter(tenant=request.tenant)
    from apps.accounts.security import RISK_STEP_UP_THRESHOLD
    context = {
        "policy": policy,
        "mfa_enabled_count": (MfaDevice.objects.filter(tenant=request.tenant, is_active=True,
                                                       confirmed_at__isnull=False)
                              .values("user").distinct().count()),
        "member_count": UserModel.objects.filter(tenant=request.tenant, status="active").count(),
        "session_count": sessions.filter(revoked_at__isnull=True).count(),
        "revoked_session_count": sessions.exclude(revoked_at__isnull=True).count(),
        "attempt_count": attempts.count(),
        "failed_count": attempts.filter(success=False).count(),
        "risky_count": attempts.filter(risk_score__gte=RISK_STEP_UP_THRESHOLD).count(),
        "recent_attempts": attempts.select_related("user")[:10],
        "threshold": RISK_STEP_UP_THRESHOLD,
    }
    return render(request, "accounts/security_overview.html", context)
