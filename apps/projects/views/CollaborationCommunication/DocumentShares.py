"""Projects 7.9 — DocumentShare views: the share register, its CRUD, revoke and the edit claim.

The register's four lenses are plain ``crud_list`` ``filters`` — ``?project=<pk>`` and
``?channel=<pk>`` (int-FK lookups, ``as_db_int``-guarded and skipped when ``0``),
``?access_level=`` (an enum, whose junk values the ``_enum_values`` guard ignores rather than
silently emptying the register — L11) and ``?is_active=`` (a BooleanField).

Two verbs, each the ONE writer of its own state:

* ``dsh_revoke`` — a TOGGLE over ``is_active``/``revoked_by``/``revoked_at``. Revoking also
  releases any active claim: "I may edit this now" cannot outlive the share that granted it.
* ``dsh_claim`` / ``dsh_release`` — the single-editor marker. Only a live, ``edit``-level share
  can be claimed, and only one holder at a time (the refusal names the current holder). Release
  is open to any member on purpose: a stale claim must not be able to deadlock the document.
"""
from apps.projects.forms import DocumentShareForm
from apps.projects.models import Channel, DocumentShare
from apps.projects.views._common import *  # noqa: F401,F403
from apps.projects.views._common import (as_db_int, get_object_or_404, login_required, messages,
                                         redirect, render, require_POST, timezone,
                                         write_audit_log)
from apps.projects.views._helpers import owners, projects


def _display(user):
    """A user's label for a message — the template's ``get_full_name|default:email`` in Python."""
    if user is None:
        return "—"
    return user.get_full_name() or user.email


@login_required
def dsh_list(request):
    qs = (DocumentShare.objects.filter(tenant=request.tenant)
          .select_related("project", "channel", "document", "shared_with", "claimed_by"))
    return crud_list(
        request, qs, "projects/collaboration/documentshare/list.html",
        search_fields=["number", "note", "document__name"],
        filters=[("project", "project_id", True), ("channel", "channel_id", True),
                 ("access_level", "access_level", False), ("is_active", "is_active", False)],
        extra_context={
            "projects": projects(request.tenant),
            "channels": (Channel.objects.filter(tenant=request.tenant)
                         .select_related("project").order_by("number")),
            "access_choices": DocumentShare.ACCESS_CHOICES,
        },
    )


@login_required
def dsh_create(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = DocumentShareForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.created_by = request.user
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, f"Document share {obj.number} created.")
            return redirect("projects:dsh_detail", pk=obj.pk)
    else:
        form = DocumentShareForm(tenant=request.tenant, initial={
            "project": as_db_int(request.GET.get("project", "")),
            "channel": as_db_int(request.GET.get("channel", "")),
        })
    return render(request, "projects/collaboration/documentshare/form.html",
                  {"form": form, "is_edit": False})


@login_required
def dsh_detail(request, pk):
    return crud_detail(
        request, model=DocumentShare, pk=pk,
        template="projects/collaboration/documentshare/detail.html",
        select_related=("project", "channel", "document", "shared_with", "claimed_by",
                        "revoked_by", "created_by"))


@login_required
def dsh_edit(request, pk):
    return crud_edit(
        request, model=DocumentShare, pk=pk, form_class=DocumentShareForm,
        template="projects/collaboration/documentshare/form.html",
        success_url="projects:dsh_list")


@login_required
@require_POST
def dsh_delete(request, pk):
    return crud_delete(request, model=DocumentShare, pk=pk,
                       success_url="projects:dsh_list")


# -- lifecycle verbs ----------------------------------------------------------------------------

@login_required
@require_POST
def dsh_revoke(request, pk):
    """Toggle the share's active state — the ONE writer of ``is_active``/``revoked_*``.

    Revoking stamps all three together AND clears any active claim; restoring clears the two
    revoke stamps. ``previous`` is captured BEFORE mutating so the audit entry shows the
    direction of the flip.
    """
    obj = get_object_or_404(DocumentShare, pk=pk, tenant=request.tenant)
    previous = obj.is_active
    if previous:
        obj.is_active = False
        obj.revoked_by = request.user
        obj.revoked_at = timezone.now()
        # The claim cannot outlive the share that granted it.
        obj.claimed_by = None
        obj.claimed_at = None
    else:
        obj.is_active = True
        obj.revoked_by = None
        obj.revoked_at = None
    obj.save(update_fields=["is_active", "revoked_by", "revoked_at",
                            "claimed_by", "claimed_at", "updated_at"])
    write_audit_log(request.user, obj, "update",
                    changes={"verb": "dsh_revoke", "from": previous, "to": obj.is_active})
    if obj.is_active:
        messages.success(request, f"Restored document share {obj.number}.")
    else:
        messages.success(request, f"Revoked document share {obj.number} — its edit claim, if any, "
                                  f"was released with it.")
    return redirect("projects:dsh_detail", pk=obj.pk)


@login_required
@require_POST
def dsh_claim(request, pk):
    """Take the single-editor claim. Refused unless the share is live and shared at ``edit``."""
    obj = get_object_or_404(DocumentShare, pk=pk, tenant=request.tenant)
    if obj.is_revoked:
        messages.error(request, f"{obj.number} is revoked — restore it before claiming it.")
        return redirect("projects:dsh_detail", pk=obj.pk)
    if obj.access_level != "edit":
        messages.error(
            request,
            f"{obj.number} is shared as {obj.get_access_level_display()} — only a share with "
            f"edit access can be claimed.")
        return redirect("projects:dsh_detail", pk=obj.pk)
    if obj.claimed_by_id == request.user.pk:
        messages.info(request, f"You already hold the edit claim on {obj.number}.")
        return redirect("projects:dsh_detail", pk=obj.pk)
    if obj.claimed_by_id is not None:
        messages.error(
            request,
            f"{obj.number} is already claimed by {_display(obj.claimed_by)} — release it first.")
        return redirect("projects:dsh_detail", pk=obj.pk)
    previous = obj.claimed_by
    obj.claimed_by = request.user
    obj.claimed_at = timezone.now()
    obj.save(update_fields=["claimed_by", "claimed_at", "updated_at"])
    write_audit_log(request.user, obj, "update",
                    changes={"verb": "dsh_claim", "from": _display(previous),
                             "to": request.user.username})
    messages.success(request, f"You are now editing {obj.document.name} ({obj.number}).")
    return redirect("projects:dsh_detail", pk=obj.pk)


@login_required
@require_POST
def dsh_release(request, pk):
    """Drop the edit claim. Any member may release — a stale claim must not deadlock the file."""
    obj = get_object_or_404(DocumentShare, pk=pk, tenant=request.tenant)
    if obj.claimed_at is None:
        messages.info(request, f"{obj.number} is not claimed — nothing to release.")
        return redirect("projects:dsh_detail", pk=obj.pk)
    previous = obj.claimed_by
    obj.claimed_by = None
    obj.claimed_at = None
    obj.save(update_fields=["claimed_by", "claimed_at", "updated_at"])
    write_audit_log(request.user, obj, "update",
                    changes={"verb": "dsh_release", "from": _display(previous), "to": None})
    messages.success(request, f"Released the edit claim on {obj.number} "
                              f"(held by {_display(previous)}).")
    return redirect("projects:dsh_detail", pk=obj.pk)
