"""Procurement 6.19 Document & Knowledge Management — ProcurementDocumentRevision views.

The **Version Control** bullet: the workspace-wide revision register, one revision's detail page,
the upload that mints a revision on a document, and the two verbs — approve and delete.

The chain rules this module enforces, because they are the whole point of the entity:

1. **Uploading never moves the pointer.** A new revision lands ``is_approved=False`` and sits
   behind the current one. Only approval moves ``ProcurementDocument.current_revision_no``.
2. **Approval refuses ``revision_no <= current_revision_no``.** That single rule is what keeps
   the chain linear and forward-only; without it an old revision could be re-approved and the
   pointer would walk backwards.
3. **Older approved revisions keep ``is_approved=True``.** They *were* approved. "Only the
   latest approved version is accessible" is expressed by the pointer landing on exactly one
   row, never by rewriting history.
4. **There is no edit.** No url, no view, no template — every column but ``change_note`` is
   ``editable=False`` and the only post-create write is approve's three-column stamp.

Discipline a reviewer will otherwise go looking for:

* **Every queryset is ``filter(tenant=request.tenant)``, and a revision is DOUBLE-scoped** —
  ``tenant`` on the child AND ``document__tenant`` on its parent. Never trust the child alone:
  a revision row whose parent belongs to another workspace is a data bug, and it must 404 here
  rather than render that workspace's document number.
* **Allocation runs under a lock on the PARENT row**, with the ``unique_together`` constraint as
  the backstop and one retry, mirroring ``TenantNumbered.save()``'s retry-on-IntegrityError
  idiom (one ``transaction.atomic()`` per attempt, so a broken transaction is never reused).
* **Both verbs redirect to the document detail page.** That is where the chain is rendered and
  where both buttons live, and delete cannot redirect to a page it just removed — one
  destination for both keeps the two honest.
* **Every refusal is a message and a redirect**, never a 500 and never a silent no-op.
"""
import os

from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.http import FileResponse

from apps.procurement.forms.DocumentKnowledgeManagement.Revisions import (
    ProcurementDocumentRevisionUploadForm)
# NOT-YET-WIRED entities of this SAME sub-module: import the entity MODULES directly, never
# ``from apps.procurement.models import X`` — the sub-package is not wired until the Integrator
# lands it, and a package-level re-export would be a star-import cycle at URLconf import time.
from apps.procurement.models.DocumentKnowledgeManagement.Documents import ProcurementDocument
from apps.procurement.models.DocumentKnowledgeManagement.Revisions import (
    EXTRACT_MAX_CHARS, ProcurementDocumentRevision, extract_document_text, file_sha256,
    next_revision_no)
from apps.procurement.views._common import *  # noqa: F401,F403
from apps.procurement.views._helpers import holder_name, readable_document_q

TEMPLATE_LIST = "procurement/documentknowledge/revision/list.html"
TEMPLATE_DETAIL = "procurement/documentknowledge/revision/detail.html"
#: The UPLOAD page. There is no edit template — this one is reached only through
#: ``documents/<int:pk>/revisions/add/`` and it always renders ``is_edit=False``.
TEMPLATE_FORM = "procurement/documentknowledge/revision/form.html"

#: What one register ROW renders. Pinned once so the list's select_related and the detail's
#: cannot drift apart.
_ROW_RELATIONS = ("document", "uploaded_by", "approved_by")

#: Printed on the register, the detail page and the upload page — ONE constant, so the three
#: surfaces cannot describe the chain differently.
REVISION_NOTE = (
    "A revision is immutable. Approving one makes it the document's current version; earlier "
    "approved revisions stay on the record as superseded. There is no edit."
)

#: How many documents the register's facet ``<select>`` offers. A dropdown is a navigation aid,
#: not an export: past a couple of hundred options nobody scrolls it, and every extra option is
#: a model instance built and an ``<option>`` rendered.
DOCUMENT_FACET_CAP = 200

#: The two values ``crud_list`` maps to booleans. Any other string is skipped by the filter
#: rather than matched, so a hand-edited ``?approved=`` cannot empty the register (L11).
APPROVAL_CHOICES = [("True", "Approved"), ("False", "Pending approval")]


def _build_upload_note():
    """The upload page's standing note, rendered FROM the constants it describes.

    The allowed extensions and the size cap are read out of ``apps.core.forms._common`` rather
    than retyped, so the page cannot promise a limit the form does not enforce. The import is
    function-local for the same reason ``clean_file`` keeps its own local: pulling either
    constant through ``apps.procurement.forms`` would collide with CatalogManagement's rival
    2 MB definition.
    """
    from apps.core.forms._common import ALLOWED_DOC_EXTENSIONS, MAX_UPLOAD_BYTES

    kinds = " ".join(sorted(ALLOWED_DOC_EXTENSIONS))
    megabytes = MAX_UPLOAD_BYTES // (1024 * 1024)
    return (f"Accepted file types: {kinds}. Maximum size {megabytes} MB. Text is read from PDFs "
            f"that carry a text layer and from plain-text uploads (.txt, .csv) so the register "
            f"can search inside them; a scanned image has no text to read, and the revision "
            f"says so on its own row rather than leaving you guessing.")


UPLOAD_NOTE = _build_upload_note()


def _need_tenant(request, what):
    """Refuse a tenant-less user (the superuser has ``tenant=None``) before any write.

    Mirrors ``crud_create``'s own guard so the hand-rolled paths below cannot mint a revision
    into a workspace that was never selected.
    """
    if request.tenant is None:
        messages.error(request, f"Select a tenant workspace before you {what}.")
        return redirect("dashboard:home")
    return None


def _revision_qs(request):
    """The register's base queryset — DOUBLE tenant-scoped, child and parent.

    ``document__tenant`` is not redundant belt-and-braces. Every row this page renders reaches
    through ``document`` for a number, a title and the pointer that decides its badge, so a
    child whose parent belongs elsewhere would print another workspace's data through a
    correctly-scoped child. Scoping both ends means such a row cannot appear at all.

    The parent's CLASSIFICATION governs the child for the same reason. A revision carries the
    stored file, its checksum and the text read out of it, so a confidential document whose rows
    were listed here would be readable through its own revision register — and the download view
    below fetches through this same queryset, which is what makes one rule cover the page and
    the bytes. ``readable_document_q`` is the single definition; the prefix reaches it through
    the FK.
    """
    return (ProcurementDocumentRevision.objects
            .filter(tenant=request.tenant, document__tenant=request.tenant)
            .filter(readable_document_q(request.user, "document__"))
            .select_related(*_ROW_RELATIONS))


def _documents(request):
    """The document facet's options — three columns, capped, ordered by the number people cite.

    Narrowed by the same read rule as the register itself. A ``<select>`` listing every document
    number and title in the workspace is an enumeration of the confidential ones even when their
    rows never render — the facet has to answer the same question the page does.

    ``.only()`` here is load-bearing rather than a micro-optimisation. ``ProcurementDocument``
    carries ``extracted_text``, a machine-written TextField that runs to 200,000 characters, and
    the ``<select>`` renders exactly ``pk``, ``number`` and ``title`` — so a plain queryset hauls
    the whole search corpus of the workspace into memory to draw a dropdown (measured: 59 MB and
    4.9 s of a 4.9 s request at 2,007 documents, against 0.19 s for the register itself). Three
    columns and a cap make it kilobytes.
    """
    if request.tenant is None:
        return ProcurementDocument.objects.none()
    return (ProcurementDocument.objects
            .filter(tenant=request.tenant)
            .filter(readable_document_q(request.user))
            .only("pk", "number", "title")
            .order_by("number")[:DOCUMENT_FACET_CAP])


def _get_revision(request, pk):
    """One revision, double-scoped, or 404. The single fetch every verb and the detail use."""
    return get_object_or_404(_revision_qs(request), pk=pk)


@login_required
def pdocrevision_list(request):
    """Every revision in the workspace, newest first — the Version Control landing page.

    Ordering comes off the model (``-revision_no``, ``-id``), which reads as newest-first within
    each document and, across documents, most-recently-created first — the id tiebreak is doing
    that work.
    """
    # Same read rule as the rows (the sibling register narrows its own tile base for the same
    # reason). Without this the tiles are a counting oracle: a member who may read nothing still
    # saw "1 revision / 1 approved" over an empty table, which discloses that a confidential
    # document exists and how far along its chain is. The prefix reaches the classification
    # through the parent, exactly as _revision_qs does.
    base = (ProcurementDocumentRevision.objects
            .filter(tenant=request.tenant, document__tenant=request.tenant)
            .filter(readable_document_q(request.user, "document__")))
    # ONE conditional aggregate, not three COUNTs. Computed over the whole readable workspace
    # rather than the filtered page, so the tiles keep meaning something while a facet is applied.
    stats = base.aggregate(
        total=Count("pk"),
        approved=Count("pk", filter=Q(is_approved=True)),
        pending=Count("pk", filter=Q(is_approved=False)),
    )
    return crud_list(
        # .defer, not a narrower select_related: the joins are what keep this page's query count
        # at 4 whatever the row count, and the payload is what has to go. Neither the revision's
        # own text of record nor the parent's search copy is rendered on a register row, and at
        # 30 KB average per document a 15-row page was hauling ~900 KB (measured 6,057 KB) of
        # TextField to draw a table of filenames and dates.
        request, _revision_qs(request).defer("extracted_text", "document__extracted_text"),
        TEMPLATE_LIST,
        # sha256 is searchable on purpose: a checksum quoted in an audit note or an email is
        # exactly the thing somebody arrives here holding.
        search_fields=("document__number", "document__title", "change_note", "sha256"),
        # ``document`` is an FK pk and needs the as_db_int guard (is_int=True) so a hand-edited
        # query string cannot 500 the page (L11); ``approved`` is a BooleanField, which has no
        # choices to enum-guard, so crud_list's "True"/"False" mapping is what makes it work —
        # which is why APPROVAL_CHOICES offers literally those two strings.
        filters=(("document", "document_id", True),
                 ("approved", "is_approved", False)),
        extra_context={
            "documents": _documents(request),
            "approval_choices": APPROVAL_CHOICES,
            "stats": stats,
            "revision_note": REVISION_NOTE,
        },
    )


@login_required
def pdocrevision_detail(request, pk):
    """One revision: its file, its checksum, its approval state and the text read out of it.

    Hand-rolled rather than ``crud_detail`` because two of its four context keys are derived
    FROM the row (``document`` and ``is_current``) and ``crud_detail`` builds ``extra_context``
    before it fetches — routing through it would mean fetching the same row twice. The tenant
    scoping is stricter than the helper's (parent as well as child) and the row context key is
    the same ``obj`` (the 6.5 ``event_detail`` precedent).
    """
    obj = _get_revision(request, pk)
    return render(request, TEMPLATE_DETAIL, {
        "obj": obj,
        "document": obj.document,
        # Resolved once here rather than left to the template so the page and the verbs agree
        # about which revision the pointer is on.
        "is_current": obj.is_current,
        "revision_note": REVISION_NOTE,
    })


@login_required
def pdocrevision_download(request, pk):
    """Hand back this revision's stored bytes — authenticated, tenant-scoped, as an attachment.

    WARNING, and the reason this view exists: ``file.url`` is a raw MEDIA_URL path served by the
    web server, so linking it hands every stored document to anybody who can guess a filename —
    no login, no session, no tenant. The bytes of a ``confidential`` or ``restricted`` record are
    exactly what must not be readable that way. Every stored file linked in 6.19 links THIS route
    instead, so the same double tenant scope and the same 404 that guard the page guard the file.

    Two headers do the rest of the work:

    * ``Content-Disposition: attachment`` — the file is handed to the browser to save, never
      rendered on this origin. An uploaded ``.html`` or ``.svg`` served inline would be stored XSS
      against every logged-in member of the workspace; the extension allow-list is then no longer
      the only control standing between an upload and script execution.
    * ``X-Content-Type-Options: nosniff`` — the browser must not second-guess the declared type.
      ``SECURE_CONTENT_TYPE_NOSNIFF`` only applies outside DEBUG, so it is set here rather than
      assumed.
    """
    revision = _get_revision(request, pk)
    if not revision.file:
        messages.error(request, f"r{revision.revision_no} of {revision.document.number} has no "
                                f"stored file.")
        return redirect("procurement:pdocrevision_detail", pk=revision.pk)

    try:
        handle = revision.file.open("rb")
    except (OSError, ValueError):
        # The row can outlive its bytes: a file removed from MEDIA_ROOT behind Django's back has
        # to be a message on the page it was linked from, never a 500 on a download click.
        messages.error(request, f"The stored file for r{revision.revision_no} could not be read "
                                f"back from storage.")
        return redirect("procurement:pdocrevision_detail", pk=revision.pk)

    # The display name, with any CR/LF removed: it is attacker-supplied and it is about to be
    # written into a response header. Django escapes quotes and backslashes itself and refuses a
    # header carrying a newline outright (BadHeaderError) — stripping is what keeps that correct
    # refusal from becoming a 500 on a download anybody can trigger.
    filename = (revision.original_filename or os.path.basename(revision.file.name)
                or f"r{revision.revision_no}")
    filename = filename.replace("\r", " ").replace("\n", " ")

    response = FileResponse(handle, as_attachment=True, filename=filename)
    response["X-Content-Type-Options"] = "nosniff"
    return response


# ---------------------------------------------------------------------------------------------
# Upload. The route (``documents/<int:pk>/revisions/add/``) lives in the Documents url module
# because url modules own SEGMENTS; the view lives here because the entity does.
# ---------------------------------------------------------------------------------------------


@login_required
def pdocument_revision_upload(request, pk):
    """Mint the next revision of one document from an uploaded file.

    Guards run in this order on GET **and** on POST — the page must not offer what the POST
    would refuse, and the POST must not trust the page:

    1. no workspace selected → refuse;
    2. the document is archived → refuse (an archived record is out of use; re-activate it
       first if it is back);
    3. somebody else holds the advisory checkout → refuse, naming them.

    Then the allocation, which is the delicate part. ``revision_no`` is chosen inside
    ``transaction.atomic()`` behind ``select_for_update()`` on the PARENT document row, so two
    uploads onto the same document serialize; ``unique_together (tenant, document,
    revision_no)`` is the database backstop, and an ``IntegrityError`` is retried exactly once
    before the user is told plainly to try again. The checksum, size and original filename are
    computed BEFORE ``save()`` — reading the upload afterwards would read a consumed file.

    Text extraction runs immediately AFTER the transaction commits, not inside it. Reading a
    20 MB PDF off disk while holding a row lock would block every other upload onto that
    document for the duration, and the extraction writes nothing but this revision's own two
    columns. Should the request die in that window the revision simply carries no text, which is
    the exact condition the re-index Run exists to repair.

    Uploading NEVER moves ``current_revision_no``: the new revision lands unapproved and waits.
    """
    guard = _need_tenant(request, "upload a revision")
    if guard is not None:
        return guard

    # Narrowed by the read rule as well as the tenant: uploading a revision onto a document is
    # writing to it, and a member who may not read a confidential record may not add to its
    # chain either. Same queryset shape as ``_get_document`` in the Documents view module.
    document = get_object_or_404(
        ProcurementDocument.objects
        .filter(readable_document_q(request.user))
        .select_related("checked_out_by"),
        pk=pk, tenant=request.tenant)

    if document.status == "archived":
        messages.error(request, f"{document.number} is archived, so it does not take new "
                                f"revisions. Re-activate it first if it is back in use.")
        return redirect("procurement:pdocument_detail", pk=document.pk)
    if document.checked_out_by_id not in (None, request.user.pk):
        messages.error(request, f"{holder_name(document.checked_out_by)} has {document.number} "
                                f"checked out. Ask them to release it, or have a workspace "
                                f"administrator force the release.")
        return redirect("procurement:pdocument_detail", pk=document.pk)

    if request.method == "POST":
        form = ProcurementDocumentRevisionUploadForm(request.POST, request.FILES,
                                                     tenant=request.tenant)
        if form.is_valid():
            upload = form.cleaned_data.get("file")
            # Measured from the upload BEFORE it is stored: save() consumes the file pointer,
            # and ``size``/``name`` on a saved FieldFile answer a different question.
            # WARNING: ``upload.name`` is attacker-controlled and is kept for DISPLAY only —
            # never joined onto a filesystem path. Django's storage layer derives the real path
            # from the field's ``upload_to`` and sanitizes it; ``basename`` here strips any
            # directory component a client tried to smuggle in before it is ever shown.
            digest = file_sha256(upload)
            original = os.path.basename(getattr(upload, "name", "") or "")[:255]
            size = getattr(upload, "size", 0) or 0

            revision = form.save(commit=False)
            revision.tenant = request.tenant
            revision.document = document
            revision.uploaded_by = request.user
            revision.sha256 = digest
            revision.original_filename = original
            revision.file_size = size

            # One transaction per attempt — the TenantNumbered.save() idiom. A transaction that
            # has raised IntegrityError cannot be reused, so the atomic block is INSIDE the
            # loop, not around it. The FileField writes its bytes to storage on the first
            # attempt and is marked committed, so a retry re-INSERTs the row without storing a
            # second copy of the file.
            saved = False
            for _attempt in range(2):
                try:
                    with transaction.atomic():
                        locked = (ProcurementDocument.objects.select_for_update()
                                  .get(pk=document.pk, tenant=request.tenant))
                        revision.revision_no = next_revision_no(locked)
                        revision.save()
                    saved = True
                    break
                except IntegrityError:
                    # Somebody allocated the same number between our read and our insert.
                    # Re-allocating under a fresh lock is the whole fix; a second failure is
                    # reported honestly rather than retried forever.
                    continue

            if not saved:
                messages.error(request, "Another revision of this document was uploaded at the "
                                        "same moment. Nothing was saved — please try again.")
                return redirect("procurement:pdocument_detail", pk=document.pk)

            # Outside the lock. extract_document_text never raises: a missing extractor, an
            # unreadable path and a malformed file all come back as ("", note), and the note is
            # what the row shows instead of an empty column that looks like a bug.
            text, note = extract_document_text(revision)
            revision.extracted_text = (text or "")[:EXTRACT_MAX_CHARS]
            revision.extraction_note = note
            revision.save(update_fields=["extracted_text", "extraction_note"])

            write_audit_log(request.user, document, "revision_upload",
                            {"revision_no": revision.revision_no,
                             "sha256": revision.sha256[:16],
                             "file_size": revision.file_size})
            messages.success(request, f"r{revision.revision_no} uploaded to {document.number}. "
                                      f"It is not the current version yet — a workspace "
                                      f"administrator has to approve it first.")
            return redirect("procurement:pdocument_detail", pk=document.pk)
    else:
        form = ProcurementDocumentRevisionUploadForm(tenant=request.tenant)

    return render(request, TEMPLATE_FORM, {
        "form": form,
        # Always False: this template is the upload page and a revision is never edited.
        "is_edit": False,
        "document": document,
        "upload_note": UPLOAD_NOTE,
    })


# ---------------------------------------------------------------------------------------------
# Verbs. Both POST-only, both audited against the PARENT document (that is the record a person
# reads a history for), both redirecting to the document detail page where the chain lives.
# ---------------------------------------------------------------------------------------------


@login_required
@tenant_admin_required
@require_POST
def pdocrevision_approve(request, pk):
    """Make this revision the document's current version.

    Administrator-gated: approval decides which file the whole workspace — and, through
    ``supplier_visible``, eventually the vendor portal — treats as the truth.

    The refusals, in order:

    * already approved → idempotent ``messages.info`` and **no write**, so a double-click
      cannot re-stamp who approved it and when;
    * ``revision_no <= document.current_revision_no`` → **refused**. The chain is linear and
      only moves forward. This is the rule that makes the pointer meaningful: without it, an
      older revision could be re-approved and "current" would walk backwards.

    Then, under a lock on the parent row: stamp the revision, move the pointer, copy the
    revision's text up into the parent's denormalized search copy, and lift a still-draft
    document to active — its first approved file is what puts it in force. The forward-only
    check is repeated INSIDE the lock because the first one is a read that another approval can
    interleave with.

    Note what does NOT happen: earlier approved revisions are left exactly as they are. They
    were approved, and rewriting that would be a lie. "Only the latest approved version is
    accessible" is expressed by ``current_revision_no`` landing on exactly one row.
    """
    revision = _get_revision(request, pk)
    document = revision.document

    if revision.is_approved:
        messages.info(request, f"r{revision.revision_no} of {document.number} is already "
                               f"approved.")
        return redirect("procurement:pdocument_detail", pk=document.pk)
    if revision.revision_no <= document.current_revision_no:
        messages.error(request, f"{document.number} is already on r{document.current_revision_no}"
                                f". The revision chain is linear and only moves forward, so "
                                f"r{revision.revision_no} cannot be approved now — upload a new "
                                f"revision with the content you want instead.")
        return redirect("procurement:pdocument_detail", pk=document.pk)

    raced = False
    with transaction.atomic():
        locked = (ProcurementDocument.objects.select_for_update()
                  .get(pk=document.pk, tenant=request.tenant))
        if revision.revision_no <= locked.current_revision_no:
            raced = True
        else:
            revision.is_approved = True
            revision.approved_by = request.user
            revision.approved_at = timezone.now()
            # Exactly these three columns: the approve stamp is the ONLY post-create write on a
            # revision, and naming the columns is what keeps that true.
            revision.save(update_fields=["is_approved", "approved_by", "approved_at"])

            locked.current_revision_no = revision.revision_no
            # The parent's copy is a SEARCH COPY of the text of record, which lives on the
            # revision. Two writers ever touch it: this line and the re-index Run.
            locked.extracted_text = (revision.extracted_text or "")[:EXTRACT_MAX_CHARS]
            if locked.status == "draft":
                locked.status = "active"
            locked.save(update_fields=["current_revision_no", "extracted_text", "status",
                                       "updated_at"])
            document = locked

    if raced:
        messages.error(request, "Another approval moved this document forward while the page "
                                "was open. Nothing was changed — reload to see where the chain "
                                "is now.")
        return redirect("procurement:pdocument_detail", pk=document.pk)

    write_audit_log(request.user, document, "revision_approve",
                    {"revision_no": revision.revision_no, "sha256": revision.sha256[:16]})
    messages.success(request, f"r{revision.revision_no} is now the current version of "
                              f"{document.number}. Its text is what search matches; earlier "
                              f"approved revisions stay on the record as superseded.")
    return redirect("procurement:pdocument_detail", pk=document.pk)


@login_required
@require_POST
def pdocrevision_delete(request, pk):
    """Remove an unapproved, non-current revision — a mis-upload, before anyone relied on it.

    Deletion is refused on anything approved and on whatever the document currently points at.
    An approved revision is part of the record of what was in force and when; the current one is
    the file the workspace is using. Neither is a mistake to tidy away, and superseding by
    uploading a new revision is the way forward for both.

    (The two conditions overlap by construction — the pointer only ever lands on an approved
    revision — and both are checked anyway: a pointer left dangling by any future path must not
    become a route to deleting the row it points at.)

    **Both guards run under a lock on the PARENT row, exactly as approve does.** Reading them off
    an unlocked snapshot was the whole defect: pointer=2 with r3 pending, one person POSTs delete
    on r3 (reads is_approved=False, pointer=2 — both guards pass) while an administrator approves
    r3, and the delete then destroys an APPROVED revision and leaves the document pointing at a
    row that no longer exists, reporting success. The revision is therefore re-read inside the
    transaction and re-checked against the locked parent; a row that changed underneath us is
    refused with the same message it would have been refused with a moment earlier.

    WARNING: deleting the row does NOT remove the stored file from ``MEDIA_ROOT``. Django never
    has, and that is deliberate here rather than an oversight — reclaiming the disk means
    deleting a path derived from stored user input, which is exactly the operation that turns
    one bug into an arbitrary-file-delete. Secure alternative: reclamation belongs to a
    supervised sweep that walks storage and the table together and refuses any path outside
    ``MEDIA_ROOT`` (13.9 / 13.14), never an ``os.remove`` inside a request handler. The confirm
    text on both surfaces says the record goes and the file is not reclaimed, so nobody is
    misled into thinking the bytes are gone.
    """
    revision = _get_revision(request, pk)
    document = revision.document
    label = f"r{revision.revision_no}"

    refusal = None
    with transaction.atomic():
        locked = (ProcurementDocument.objects.select_for_update()
                  .get(pk=document.pk, tenant=request.tenant))
        # Re-read the revision INSIDE the lock and scoped to the locked parent: approve stamps
        # is_approved and moves the pointer in one transaction, so a snapshot taken before it is
        # stale in exactly the window that matters.
        fresh = (ProcurementDocumentRevision.objects
                 .filter(pk=revision.pk, tenant=request.tenant, document_id=locked.pk)
                 .first())
        if fresh is None:
            refusal = (f"{label} of {locked.number} is no longer there — somebody removed it "
                       f"while the page was open.")
        elif fresh.is_approved:
            refusal = (f"{label} of {locked.number} is approved, so it stays on the record. "
                       f"Upload a new revision to supersede it — approved history is never "
                       f"rewritten here.")
        elif fresh.revision_no == locked.current_revision_no:
            refusal = (f"{locked.number} currently points at {label}, so it cannot be deleted. "
                       f"Approve a newer revision first.")
        else:
            # Audited BEFORE the delete, while the row still has a pk to record — the same order
            # ``crud_delete`` uses — and inside the same transaction, so a rolled-back delete
            # cannot leave an audit row claiming it happened.
            write_audit_log(request.user, locked, "revision_delete",
                            {"revision_no": fresh.revision_no, "sha256": fresh.sha256[:16]})
            fresh.delete()

    if refusal is not None:
        messages.error(request, refusal)
        return redirect("procurement:pdocument_detail", pk=document.pk)

    messages.success(request, f"{label} of {document.number} removed. The record is gone; the "
                              f"stored file is not reclaimed from disk here.")
    return redirect("procurement:pdocument_detail", pk=document.pk)
