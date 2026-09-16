"""Projects 7.10 — ProjectDocument views: the register, its CRUD, the lock, the hold and the archive.

**The search is a denormalized copy with the 4+-character rule (Ruling 6).** ``pdm_list`` does NOT
pass ``extracted_text`` to ``crud_list``'s ``search_fields``: a 1-3 character ``?q=`` would sweep a
TextField twice per matching search (Paginator's COUNT, then the page) for results nobody wanted.
Instead the view applies its own search BEFORE ``crud_list`` — title/number/tags always, the text
copy only from 4 characters — and passes ``search_fields=[]`` (``apply_search`` no-ops on an empty
field list), so the sweep runs at most once per page render and only when it can plausibly help.
Everything else on the filter bar (``?project=``/``?folder=``/``?document_type=``/``?status=``/
``?classification=``/``?owner=``/``?archived=``) goes through ``crud_list``'s own ``filters`` spec,
which is where the L11 guards live.

**Five verbs, each the ONE writer of its own state:**

* ``pdm_checkout`` / ``pdm_checkin`` — the cooperative single-editor lock. Check-out is refused on a
  locked row (the refusal names the holder); check-in is open to any member ON PURPOSE, because a
  stale lock must not be able to deadlock a document any more than 7.9's stale claim could.
* ``pdm_archive`` — a Toggle over ``is_archived``/``archived_by``/``archived_at``/``status``, and
  the one writer of ``pre_archive_status``: archiving stamps the status the row carried so that
  un-archiving RESTORES it rather than guessing. Refused on a held row (the hold outranks the
  archive).
* ``pdm_hold`` / ``pdm_release`` — the legal hold. While held, the row refuses archive AND delete
  (the model's ``clean()`` is the second half of that guarantee; the delete view is the third).
* ``pdm_reindex`` — a guarded Runtime that re-runs extraction on the current approved revision and
  refreshes the search copy. Idempotent, and the ONLY other writer of ``extracted_text``.

**Which verbs are admin-gated, and why.** ``pdm_delete``, ``pdm_archive`` and ``pdm_release`` carry
``@tenant_admin_required``: destroying a record, retiring it from the live register and lifting
somebody else's legal hold are register-level decisions, the same class the app already gates at
``bvr_approve`` / ``pex_void``. ``pdm_hold`` stays open to any member — somebody who is worried
about a record must be able to freeze it — but the reason is REQUIRED, so the hold always has an
account of why. ``pdm_checkout``/``pdm_checkin``/``pdm_reindex`` are cooperative and stay open.
"""
from django.db.models import Q

from apps.core.crud import as_db_int
from apps.projects.forms import ProjectDocumentForm, ProjectDocumentRevisionUploadForm
from apps.projects.models import ProjectDocument, ProjectDocumentRevision
from apps.projects.models.DocumentKnowledgeManagement.Documents import purge_stored_files
from apps.projects.models.DocumentKnowledgeManagement.Revisions import extract_text
from apps.projects.views._common import *  # noqa: F401,F403
from apps.projects.views._common import (crud_list, get_object_or_404, login_required, messages,
                                         redirect, render, require_POST, tenant_admin_required,
                                         timezone, write_audit_log)
from apps.projects.views._helpers import owners, projects


def _search(qs, raw):
    """The register's search, with the 4+-character rule for the text copy (Ruling 6)."""
    q = (raw or "").strip()
    if not q:
        return qs, q
    shallow = (Q(number__icontains=q) | Q(title__icontains=q) | Q(tags__icontains=q))
    if len(q) >= 4:
        # The TextField sweep is worth it from four characters on; below that it is noise.
        shallow |= Q(extracted_text__icontains=q)
    return qs.filter(shallow), q


@login_required
def pdm_list(request):
    qs = (ProjectDocument.objects.filter(tenant=request.tenant)
          .select_related("project", "folder", "owner", "task", "milestone"))
    qs, _ = _search(qs, request.GET.get("q"))
    # `search_fields=[]` is the point: `apply_search` no-ops on an empty field list, so the
    # 4+-character rule above stays the ONLY search this register runs. The `filters` spec below is
    # `crud_list`'s, which is where the L11 guards live (a junk enum is IGNORED rather than silently
    # emptying the register; `?folder=0` is not a pk and is skipped). Hand-rolling the loop here
    # would mean hand-rolling those guards too.
    return crud_list(
        request, qs, "projects/documentknowledge/projectdocument/list.html",
        search_fields=[],
        filters=[("project", "project_id", True), ("folder", "folder_id", True),
                 ("document_type", "document_type", False), ("status", "status", False),
                 ("classification", "classification", False), ("owner", "owner_id", True),
                 ("archived", "is_archived", False)],
        extra_context={
            "projects": projects(request.tenant),
            "folders": _folder_choices(request),
            "doc_type_choices": ProjectDocument.DOC_TYPE_CHOICES,
            "status_choices": ProjectDocument.STATUS_CHOICES,
            "classification_choices": ProjectDocument.CLASSIFICATION_CHOICES,
            "owners": owners(request.tenant),
        },
    )


def _folder_choices(request):
    """The tenant's folders for the filter dropdown — one query, id-ordered for stable grouping."""
    from apps.projects.models import ProjectFolder
    return (ProjectFolder.objects.filter(tenant=request.tenant)
            .select_related("project").order_by("project__number", "name"))


@login_required
def pdm_detail(request, pk):
    obj = get_object_or_404(ProjectDocument, pk=pk, tenant=request.tenant)
    revisions = (obj.revisions.select_related("approved_by", "uploaded_by")
                 .order_by("-revision_no", "-id"))
    return render(request, "projects/documentknowledge/projectdocument/detail.html", {
        "obj": obj,
        "revisions": revisions,
        "current": obj.current_revision,
        "upload_form": ProjectDocumentRevisionUploadForm(tenant=request.tenant, document=obj),
        "share_register_url": f"/projects/shared-documents/?project={obj.project_id}",
    })


@login_required
def pdm_create(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = ProjectDocumentForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.created_by = request.user
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, f"Document {obj.number} created.")
            return redirect("projects:pdm_detail", pk=obj.pk)
    else:
        form = ProjectDocumentForm(tenant=request.tenant, initial={
            "project": as_db_int(request.GET.get("project", "")),
            "folder": as_db_int(request.GET.get("folder", "")),
        })
    return render(request, "projects/documentknowledge/projectdocument/form.html",
                  {"form": form, "is_edit": False})


@login_required
def pdm_edit(request, pk):
    obj = get_object_or_404(ProjectDocument, pk=pk, tenant=request.tenant)
    if request.method == "POST":
        form = ProjectDocumentForm(request.POST, instance=obj, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.save()
            write_audit_log(request.user, obj, "update")
            messages.success(request, f"Document {obj.number} updated.")
            return redirect("projects:pdm_detail", pk=obj.pk)
    else:
        form = ProjectDocumentForm(instance=obj, tenant=request.tenant)
    return render(request, "projects/documentknowledge/projectdocument/form.html",
                  {"form": form, "is_edit": True, "obj": obj})


@login_required
@tenant_admin_required
def pdm_delete(request, pk):
    obj = get_object_or_404(ProjectDocument, pk=pk, tenant=request.tenant)
    if request.method == "POST":
        # The legal hold is the third half of the guarantee: the model's `clean()` refuses an
        # archive while held, and the delete view refuses a delete while held. Approved revisions
        # are evidence, so a document with any of them is not deletable either.
        if obj.is_legal_hold:
            messages.error(request, f"{obj.number} is under legal hold — it may not be deleted. "
                                    f"Release the hold first ({obj.hold_reason or 'no reason recorded'}).")
            return redirect("projects:pdm_detail", pk=obj.pk)
        approved = obj.revisions.filter(is_approved=True).count()
        if approved:
            messages.error(request, f"{obj.number} carries {approved} approved revision(s) — "
                                    f"approved history is evidence and is not deleted. Retire the "
                                    f"document by archiving it instead.")
            return redirect("projects:pdm_detail", pk=obj.pk)
        number, title = obj.number, obj.title
        # Captured before the delete: the revisions cascade with the document, and the purge has to
        # run after the rows are gone or each row counts as a reference to its own payload.
        file_names = list(obj.revisions.values_list("file", flat=True))
        write_audit_log(request.user, obj, "delete",
                        changes={"verb": "pdm_delete", "title": title})
        obj.delete()
        purge_stored_files(ProjectDocumentRevision, file_names)
        messages.success(request, f"Document {number} ({title}) deleted.")
        return redirect("projects:pdm_list")
    return render(request, "projects/documentknowledge/projectdocument/delete.html", {"obj": obj})


def _display(user):
    """A user's label for a message — the template's ``get_full_name|default:email`` in Python."""
    if user is None:
        return "—"
    return user.get_full_name() or user.email


@login_required
@require_POST
def pdm_checkout(request, pk):
    """Take the cooperative edit lock. THE one writer of ``is_checked_out`` + both stamps."""
    obj = get_object_or_404(ProjectDocument, pk=pk, tenant=request.tenant)
    if obj.is_locked:
        holder = _display(obj.checked_out_by)
        if obj.checked_out_by_id == request.user.pk:
            messages.info(request, f"You already hold the check-out on {obj.number}.")
        else:
            messages.error(request, f"{obj.number} is checked out by {holder} — ask them to check "
                                    f"it in first. The lock is cooperative, not enforced.")
        return redirect("projects:pdm_detail", pk=obj.pk)
    if obj.status == "expected":
        messages.error(request, f"{obj.number} is an expected placeholder — nothing to edit until a "
                                f"first revision is uploaded.")
        return redirect("projects:pdm_detail", pk=obj.pk)
    previous = obj.checked_out_by
    obj.is_checked_out = True
    obj.checked_out_by = request.user
    obj.checked_out_at = timezone.now()
    obj.save(update_fields=["is_checked_out", "checked_out_by", "checked_out_at", "updated_at"])
    write_audit_log(request.user, obj, "update",
                    changes={"verb": "pdm_checkout", "from": _display(previous),
                             "to": request.user.username})
    messages.success(request, f"You are now editing {obj.number} — check it in to publish the "
                              f"next revision.")
    return redirect("projects:pdm_detail", pk=obj.pk)


@login_required
@require_POST
def pdm_checkin(request, pk):
    """Release the lock. Any member may — a stale lock must not deadlock a document."""
    obj = get_object_or_404(ProjectDocument, pk=pk, tenant=request.tenant)
    if not obj.is_checked_out:
        messages.info(request, f"{obj.number} is not checked out — nothing to check in.")
        return redirect("projects:pdm_detail", pk=obj.pk)
    previous = obj.checked_out_by
    obj.is_checked_out = False
    obj.checked_out_by = None
    obj.checked_out_at = None
    obj.save(update_fields=["is_checked_out", "checked_out_by", "checked_out_at", "updated_at"])
    write_audit_log(request.user, obj, "update",
                    changes={"verb": "pdm_checkin", "from": _display(previous), "to": None})
    messages.success(request, f"Checked in {obj.number} (was held by {_display(previous)}). "
                              f"Upload the next revision when it is ready.")
    return redirect("projects:pdm_detail", pk=obj.pk)


@login_required
@require_POST
@tenant_admin_required
def pdm_archive(request, pk):
    """Toggle the archive state. THE one writer of ``is_archived`` + both stamps.

    Admin-gated: archiving retires a record from the live register, which is a register-level
    decision rather than a filing one (the ``bvr_approve`` / ``chn_archive`` posture).
    """
    obj = get_object_or_404(ProjectDocument, pk=pk, tenant=request.tenant)
    previous = obj.is_archived
    if previous:
        obj.is_archived = False
        obj.archived_by = None
        obj.archived_at = None
        # RESTORE the status the row carried before the archive. The old code guessed
        # (`"approved" if obj.current_revision_no else "draft"`), which brought an `in_review` or
        # `superseded` document back as Approved with no approval action behind it. The fallback
        # only fires for a row archived before `pre_archive_status` existed.
        obj.status = obj.pre_archive_status or (
            "approved" if obj.current_revision_no else "draft")
        obj.pre_archive_status = ""
    else:
        if obj.is_legal_hold:
            messages.error(request, f"{obj.number} is under legal hold — the hold outranks the "
                                    f"archive. Release it first.")
            return redirect("projects:pdm_detail", pk=obj.pk)
        obj.pre_archive_status = obj.status
        obj.is_archived = True
        obj.archived_by = request.user
        obj.archived_at = timezone.now()
        obj.status = "archived"
    obj.save(update_fields=["is_archived", "archived_by", "archived_at", "pre_archive_status",
                            "status", "updated_at"])
    write_audit_log(request.user, obj, "update",
                    changes={"verb": "pdm_archive", "from": previous, "to": obj.is_archived})
    if obj.is_archived:
        messages.success(request, f"Document {obj.number} archived — it leaves the live register "
                                  f"and stays readable through the archive lens.")
    else:
        messages.success(request, f"Document {obj.number} restored to the live register.")
    return redirect("projects:pdm_detail", pk=obj.pk)


@login_required
@require_POST
def pdm_hold(request, pk):
    """Place the legal hold. THE one writer of ``is_legal_hold`` + the hold stamps.

    Deliberately NOT admin-gated: any member must be able to freeze a record they are worried
    about. The REASON is required, though — a hold with no stated reason is a lock with no account
    of why, and the audit row would read ``to: held``.
    """
    obj = get_object_or_404(ProjectDocument, pk=pk, tenant=request.tenant)
    if obj.is_legal_hold:
        messages.info(request, f"{obj.number} is already under legal hold.")
        return redirect("projects:pdm_detail", pk=obj.pk)
    reason = (request.POST.get("hold_reason") or "").strip()[:255]
    if not reason:
        messages.error(request, "A legal hold needs a stated reason — it freezes the record, so "
                                "whoever releases it has to know what they are releasing.")
        return redirect("projects:pdm_detail", pk=obj.pk)
    obj.is_legal_hold = True
    obj.hold_reason = reason
    obj.held_by = request.user
    obj.held_at = timezone.now()
    obj.save(update_fields=["is_legal_hold", "hold_reason", "held_by", "held_at", "updated_at"])
    write_audit_log(request.user, obj, "update",
                    changes={"verb": "pdm_hold", "to": obj.hold_reason or "held"})
    messages.success(request, f"Legal hold placed on {obj.number} — it may no longer be archived "
                              f"or deleted.")
    return redirect("projects:pdm_detail", pk=obj.pk)


@login_required
@require_POST
@tenant_admin_required
def pdm_release(request, pk):
    """Release the legal hold. THE one writer that can clear it.

    Admin-gated: releasing a hold a colleague placed is exactly the act the app's own precedent
    gates (``bvr_approve``/``pex_void``), and a plain member must not be able to lift one.
    """
    obj = get_object_or_404(ProjectDocument, pk=pk, tenant=request.tenant)
    if not obj.is_legal_hold:
        messages.info(request, f"{obj.number} is not under legal hold — nothing to release.")
        return redirect("projects:pdm_detail", pk=obj.pk)
    previous = obj.hold_reason or "held"
    obj.is_legal_hold = False
    obj.hold_reason = ""
    obj.held_by = None
    obj.held_at = None
    obj.save(update_fields=["is_legal_hold", "hold_reason", "held_by", "held_at", "updated_at"])
    write_audit_log(request.user, obj, "update",
                    changes={"verb": "pdm_release", "from": previous, "to": None})
    messages.success(request, f"Legal hold released on {obj.number}.")
    return redirect("projects:pdm_detail", pk=obj.pk)


@login_required
@require_POST
def pdm_reindex(request, pk):
    """Re-run extraction on the current APPROVED revision and refresh the search copy.

    The second of the two writers of ``extracted_text`` (the approve verb is the first). Idempotent,
    and safe to press twice: it reads what is stored and rewrites the same copy.
    """
    obj = get_object_or_404(ProjectDocument, pk=pk, tenant=request.tenant)
    current = obj.current_revision
    if current is None:
        messages.info(request, f"{obj.number} has no approved revision yet — nothing to index.")
        return redirect("projects:pdm_detail", pk=obj.pk)
    text, note = extract_text(current.file)
    obj.extracted_text = text
    obj.save(update_fields=["extracted_text", "updated_at"])
    write_audit_log(request.user, obj, "update",
                    changes={"verb": "pdm_reindex", "chars": len(text), "note": note})
    if note:
        messages.info(request, f"Re-indexed {obj.number}: {note} ({len(text)} characters stored).")
    else:
        messages.success(request, f"Re-indexed {obj.number} — {len(text)} characters of text are "
                                  f"now searchable.")
    return redirect("projects:pdm_detail", pk=obj.pk)