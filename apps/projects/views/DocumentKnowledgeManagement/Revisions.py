"""Projects 7.10 — ProjectDocumentRevision views: the chain's only writers.

Everything that changes a revision lives here, and every invariant it defends is copied verbatim
from procurement 6.19, which paid for them:

* ``pdv_upload`` allocates ``revision_no`` from :func:`next_revision_no` **inside** the transaction
  that takes the PARENT's row lock, writes the checksum and the text of record, and lands
  ``is_approved=False`` — an upload NEVER moves the pointer and never approves itself.
* ``pdv_approve`` refuses ``revision_no <= current_revision_no``, re-checks that refusal INSIDE the
  lock (the TOCTOU the unique constraint alone cannot catch), then stamps the revision, moves the
  pointer, copies ``extracted_text`` up to the parent and lifts the parent out of ``draft`` — all in
  one audit-logged transaction.
* ``pdv_restore`` rolls FORWARD: an older approved revision's file is re-uploaded as a NEW revision,
  so history is never rewritten.
* ``pdv_delete`` is permitted only for an unapproved, non-current revision, and both guards run
  under the parent row lock.

``pdv_list`` is the cross-document revision LOG (bullet 3's "revision history" register) and
``pdv_compare`` is the metadata side-by-side — explicitly NOT a document diff (13.2).
"""
from django.db import transaction

from apps.core.crud import as_db_int
from apps.projects.forms import ProjectDocumentRevisionUploadForm
from apps.projects.models import ProjectDocument, ProjectDocumentRevision
from apps.projects.models.DocumentKnowledgeManagement.Documents import purge_stored_files
from apps.projects.models.DocumentKnowledgeManagement.Revisions import (extract_text,
                                                                        file_sha256,
                                                                        next_revision_no)
from apps.projects.views._common import *  # noqa: F401,F403
from apps.projects.views._common import (get_object_or_404, login_required, messages,
                                         redirect, render, require_POST, tenant_admin_required,
                                         timezone, write_audit_log)
from apps.projects.views._helpers import projects


@login_required
def pdv_upload(request, document_pk):
    """Upload the next revision of one document. GET renders the form, POST writes the row."""
    document = get_object_or_404(ProjectDocument, pk=document_pk, tenant=request.tenant)
    if request.method == "POST":
        form = ProjectDocumentRevisionUploadForm(request.POST, request.FILES,
                                                 tenant=request.tenant, document=document)
        if form.is_valid():
            uploaded = request.FILES.get("file")
            with transaction.atomic():
                locked = (ProjectDocument.objects.select_for_update()
                          .get(pk=document.pk, tenant=request.tenant))
                revision = form.save(commit=False)
                revision.tenant = request.tenant
                revision.document = locked
                revision.revision_no = next_revision_no(locked)
                revision.checksum = file_sha256(uploaded)
                revision.uploaded_by = request.user
                revision.is_approved = False
                revision.save()
                # Extraction reads the STORED file, so it must run AFTER save() — a raw
                # ``UploadedFile`` has no ``.path``, and reading it first stored an empty search
                # copy with a false "could not be reached on disk" note (the seeder's order).
                text, note = extract_text(revision.file)
                revision.extracted_text = text
                revision.extraction_note = note
                revision.save(update_fields=["extracted_text", "extraction_note"])
                write_audit_log(request.user, revision, "create",
                                changes={"verb": "pdv_upload",
                                         "revision_no": revision.revision_no,
                                         "chars": len(text)})
            messages.success(request, f"Revision {revision.revision_no} uploaded to "
                                      f"{document.number} — it is NOT current until somebody "
                                      f"approves it.")
            return redirect("projects:pdm_detail", pk=document.pk)
    else:
        form = ProjectDocumentRevisionUploadForm(tenant=request.tenant, document=document)
    return render(request, "projects/documentknowledge/projectdocumentrevision/form.html",
                  {"form": form, "document": document})


@login_required
@require_POST
@tenant_admin_required
def pdv_approve(request, pk):
    """Make this revision the current one — the chain's single forward-moving verb."""
    revision = get_object_or_404(ProjectDocumentRevision, pk=pk, tenant=request.tenant)
    with transaction.atomic():
        document = (ProjectDocument.objects.select_for_update()
                    .get(pk=revision.document_id, tenant=request.tenant))
        if revision.revision_no <= document.current_revision_no:
            messages.error(request, f"Revision {revision.revision_no} of {document.number} is at or "
                                    f"below the current pointer ({document.current_revision_no}) — "
                                    f"the chain only moves forward.")
            return redirect("projects:pdm_detail", pk=document.pk)
        if document.is_legal_hold:
            messages.error(request, f"{document.number} is under legal hold — a new revision may "
                                    f"not be approved onto it.")
            return redirect("projects:pdm_detail", pk=document.pk)
        previous_no = document.current_revision_no
        revision.is_approved = True
        revision.approved_by = request.user
        revision.approved_at = timezone.now()
        revision.save(update_fields=["is_approved", "approved_by", "approved_at", "updated_at"])
        document.current_revision_no = revision.revision_no
        document.extracted_text = revision.extracted_text
        if document.status in ("draft", "expected", "in_review"):
            document.status = "approved"
        document.save(update_fields=["current_revision_no", "extracted_text", "status",
                                     "updated_at"])
        write_audit_log(request.user, revision, "update",
                        changes={"verb": "pdv_approve", "from": previous_no,
                                 "to": revision.revision_no})
    messages.success(request, f"Revision {revision.revision_no} is now the current version of "
                              f"{document.number}.")
    return redirect("projects:pdm_detail", pk=document.pk)


@login_required
@require_POST
def pdv_restore(request, pk):
    """Roll FORWARD from an older approved revision: its file is re-uploaded as a NEW revision.

    History is never rewritten and never deleted — the restore is itself a revision, with its own
    number, its own checksum and its own change note, which is what makes the chain auditable.
    """
    revision = get_object_or_404(ProjectDocumentRevision, pk=pk, tenant=request.tenant)
    if not revision.is_approved:
        messages.error(request, f"Revision {revision.revision_no} was never approved — there is "
                                f"nothing to restore from.")
        return redirect("projects:pdm_detail", pk=revision.document_id)
    with transaction.atomic():
        document = (ProjectDocument.objects.select_for_update()
                    .get(pk=revision.document_id, tenant=request.tenant))
        if document.is_legal_hold:
            messages.error(request, f"{document.number} is under legal hold — a restore would "
                                    f"change what the hold is holding.")
            return redirect("projects:pdm_detail", pk=document.pk)
        restored = ProjectDocumentRevision(
            tenant=request.tenant, document=document,
            revision_no=next_revision_no(document),
            file=revision.file, change_note=f"Restored from revision {revision.revision_no}.",
            extracted_text=revision.extracted_text, extraction_note=revision.extraction_note,
            uploaded_by=request.user)
        restored.save()
        write_audit_log(request.user, restored, "create",
                        changes={"verb": "pdv_restore", "from": revision.revision_no,
                                 "to": restored.revision_no})
    messages.success(request, f"Revision {revision.revision_no} was restored as revision "
                              f"{restored.revision_no} — approve it to make it current.")
    return redirect("projects:pdm_detail", pk=document.pk)


@login_required
@require_POST
@tenant_admin_required
def pdv_delete(request, pk):
    """Delete an unapproved, non-current revision. All three guards run under the parent row lock:
    the legal hold (which freezes the chain's pending rows too), ``is_approved`` and the pointer.
    """
    revision = get_object_or_404(ProjectDocumentRevision, pk=pk, tenant=request.tenant)
    with transaction.atomic():
        document = (ProjectDocument.objects.select_for_update()
                    .get(pk=revision.document_id, tenant=request.tenant))
        if document.is_legal_hold:
            messages.error(request, f"{document.number} is under legal hold — a revision may not "
                                    f"be deleted from it. Release the hold first.")
            return redirect("projects:pdm_detail", pk=document.pk)
        if revision.is_approved:
            messages.error(request, f"Revision {revision.revision_no} of {document.number} is "
                                    f"approved history — it is evidence and is not deleted.")
            return redirect("projects:pdm_detail", pk=document.pk)
        if revision.revision_no == document.current_revision_no:
            messages.error(request, f"Revision {revision.revision_no} is the current version of "
                                    f"{document.number} — approve a later one or archive the "
                                    f"document instead.")
            return redirect("projects:pdm_detail", pk=document.pk)
        no, doc_pk = revision.revision_no, document.pk
        doc_number = document.number
        # Captured BEFORE the delete: `Model.delete()` nulls the instance's pk, and the stored
        # payload has to be purged after the row is gone or the row counts as its own reference.
        file_name = revision.file.name
        write_audit_log(request.user, revision, "delete",
                        changes={"verb": "pdv_delete", "revision_no": no})
        revision.delete()
        purge_stored_files(ProjectDocumentRevision, [file_name])
    messages.success(request, f"Unapproved revision {no} of {doc_number} deleted.")
    return redirect("projects:pdm_detail", pk=doc_pk)


@login_required
def pdv_list(request):
    """The cross-document revision LOG — bullet 3's history register (metadata only, no bytes)."""
    qs = (ProjectDocumentRevision.objects.filter(tenant=request.tenant)
          .select_related("document", "document__project", "approved_by", "uploaded_by"))
    return crud_list(
        request, qs, "projects/documentknowledge/projectdocumentrevision/list.html",
        search_fields=["document__number", "document__title", "change_note"],
        filters=[("document", "document_id", True), ("is_approved", "is_approved", False),
                 ("project", "document__project_id", True)],
        extra_context={
            "projects": projects(request.tenant),
            "documents": (ProjectDocument.objects.filter(tenant=request.tenant)
                          .order_by("number")),
        },
    )


@login_required
def pdv_compare(request):
    """Side-by-side METADATA comparison of two revisions of one document.

    Deliberately NOT a document diff: bytes are never compared beyond the checksum, redlining and
    track-changes are 13.2's, and the page says so in its own empty state. ``?a=`` and ``?b=`` must
    be two revisions of the SAME document — a cross-document comparison is refused with a message,
    not silently rendered as if the numbers meant the same thing.
    """
    a_pk, b_pk = as_db_int(request.GET.get("a", "")), as_db_int(request.GET.get("b", ""))
    a = b = None
    if a_pk and b_pk:
        a = ProjectDocumentRevision.objects.filter(tenant=request.tenant, pk=a_pk).first()
        b = ProjectDocumentRevision.objects.filter(tenant=request.tenant, pk=b_pk).first()
        if a and b and a.document_id != b.document_id:
            messages.error(request, "Those two revisions belong to different documents — a "
                                    "comparison has to stay inside one document's chain.")
            a = b = None
        elif a and b and a.pk == b.pk:
            messages.info(request, "Pick two DIFFERENT revisions of the document to compare them.")
            a = b = None
    document = a.document if a else None
    return render(request, "projects/documentknowledge/projectdocumentrevision/compare.html", {
        "a": a, "b": b, "document": document,
        "a_query": a_pk or "", "b_query": b_pk or "",
        "same_checksum": bool(a and b and a.checksum and a.checksum == b.checksum),
    })