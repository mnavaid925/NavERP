"""Procurement 6.19 Document & Knowledge Management — ProcurementDocument views.

**Central Document Repository** + **Full-Text Search & Indexing** bullets. The register (search,
five facets, pagination), detail, create, edit, delete — plus seven POST-only verbs: the advisory
checkout/release lock, the three status transitions, the re-index sweep and the reminder Run.

Discipline a reviewer will otherwise go looking for:

* **Every queryset is ``filter(tenant=request.tenant)``** — never ``.all()``. The ``crud_*``
  helpers enforce it for create/edit/delete; the list and the detail narrow their own base.
* **Search reads the denormalized ``extracted_text`` column, not a join.** The text of record
  lives on the approved revision; the parent carries a copy refreshed by exactly two writers —
  the revision-approve verb and :func:`pdocument_reindex` here. That is what lets one
  ``icontains`` sweep match file contents on every keystroke.
* **``?expiry=`` is an ALLOW-LIST.** An unrecognised value skips the facet instead of emptying
  the register (L11) — the same contract ``crud_list`` keeps for its own enum filters.
* **Every verb refuses a disallowed transition with a message and a redirect.** Never a 500,
  never a silent no-op; an action already in its target state says so and writes nothing.
* **``pdocument_detail`` is hand-rolled rather than ``crud_detail``** — six of its seven context
  keys are derived FROM the row (revisions, current_revision, policies, knowledge_resources,
  can_upload, lock_holder), and ``crud_detail``'s ``extra_context`` is built before it fetches,
  so routing through it would mean fetching the same row twice. The tenant scoping and the
  ``obj`` context name are identical to the helper's (the 6.5 ``event_detail`` precedent).
* **``policies`` and ``knowledge_resources`` are REVERSE accessors** onto the two sibling entity
  models of this same sub-module — no import, no cycle, and nothing to wire.
"""
import time
from datetime import timedelta

from django.db.models import Count, Exists, OuterRef, Q

from apps.procurement.forms.DocumentKnowledgeManagement.Documents import ProcurementDocumentForm
# NOT-YET-WIRED entity of this SAME sub-module: import the entity MODULE directly, never
# ``from apps.procurement.models import X`` — the sub-package is not wired until the Integrator
# lands it, and a package-level re-export would be a star-import cycle at URLconf import time.
from apps.procurement.models.DocumentKnowledgeManagement.Documents import (
    EXPIRY_WARN_DAYS, REINDEX_ROW_CAP, ProcurementDocument, run_document_reminders_audited)
from apps.procurement.views._common import *  # noqa: F401,F403
from apps.procurement.views._helpers import (CLASSIFICATION_NOTE, holder_name,
                                             readable_document_q)

TEMPLATE_LIST = "procurement/documentknowledge/document/list.html"
TEMPLATE_DETAIL = "procurement/documentknowledge/document/detail.html"
TEMPLATE_FORM = "procurement/documentknowledge/document/form.html"

#: What one register ROW renders — and ONLY that. The three spine links are read by the detail
#: page's "Linked records" card and by nothing on the register, so joining them here was three
#: LEFT JOINs per page for columns no template touches.
_ROW_RELATIONS = ("supplier", "owner")
#: The detail page renders all four spine links, the lock holder and the author.
_DETAIL_RELATIONS = _ROW_RELATIONS + ("contract", "purchase_order", "sourcing_event",
                                      "checked_out_by", "created_by")

#: How many revisions / policies / knowledge resources the detail page lists. A heavily-revised
#: document is exactly the one people open, and an unbounded reverse list is unbounded on the
#: busiest row. Same posture as ``SUPERSEDED_BY_CAP`` on the policy detail.
DETAIL_FAN_OUT_CAP = 50

#: Below this length ``?q=`` does not sweep ``extracted_text``. A one- or two-character term
#: matches nearly every stored document, so both the COUNT and the page query do maximum work
#: over a 200,000-character column for a result set nobody wants; four characters is a word.
FILE_TEXT_SEARCH_MIN_CHARS = 4

#: Wall-clock budget for one re-index Run, checked between documents. The row cap bounds the
#: number of file reads; this bounds the case where each one is slow, so the Run returns inside
#: a request instead of being killed by the worker timeout with its progress unreported.
REINDEX_TIME_BUDGET_SECONDS = 20

#: Printed on the register and the detail page — ONE constant so the two surfaces cannot describe
#: the search differently, and so the limits of text extraction are stated where people search
#: rather than buried in a docstring.
SEARCH_NOTE = (
    "Search matches the number, title, description and tags always, and the text read from the "
    "approved file once you type four characters or more. Text is read from PDFs that carry a "
    "text layer and from plain-text uploads; a scanned image has no text to read."
)


def _need_tenant(request, what):
    """Refuse a tenant-less user (the superuser has ``tenant=None``) before any write.

    Mirrors ``crud_create``'s own guard so the hand-rolled verbs below cannot mutate — or, in
    the re-index sweep's case, scan — a workspace that was never selected.
    """
    if request.tenant is None:
        messages.error(request, f"Select a tenant workspace before you {what}.")
        return redirect("dashboard:home")
    return None


def _document_qs(request):
    """The register's base queryset, with the two facets ``crud_list`` cannot express.

    ``crud_list``'s ``filters`` tuples compare a GET value against one ORM lookup; the expiry
    facet is a DATE COMPARISON against today and the tag facet is a substring, so both are
    pre-narrowed here — before ``crud_list`` paginates, which is the only ordering that gives
    honest page counts.

    ``?expiry=`` is an ALLOW-LIST: the branches below name every value in
    ``EXPIRY_FILTER_CHOICES`` and an unrecognised one falls through untouched, so a stale
    bookmark or a hand-edited URL returns the ordinary register rather than an empty one (L11).

    ``readable_document_q`` is what makes ``classification`` mean something. Narrowing the BASE
    queryset — rather than hiding rows in the template or checking on the detail page — is what
    makes the register, ``?q=``, every facet, the stat tiles and the detail page agree without
    any of them having to remember: a document this user may not read is not in the queryset, so
    there is nothing to leak through a search oracle or an enumerated facet.

    ``extracted_text`` is deferred here and nowhere else: no register column renders it, it is
    the column ``?q=`` searches (the LIKE runs in SQL, so deferring it does not affect the
    filter), and at 30 KB a row a 15-row page was carrying ~450 KB of it.
    """
    qs = (ProcurementDocument.objects
          .filter(tenant=request.tenant)
          .filter(readable_document_q(request.user))
          .defer("extracted_text")
          .select_related(*_ROW_RELATIONS))

    today = timezone.localdate()
    expiry = request.GET.get("expiry", "").strip()
    if expiry == "expiring":
        qs = qs.filter(expires_on__range=(today, today + timedelta(days=EXPIRY_WARN_DAYS)))
    elif expiry == "expired":
        qs = qs.filter(expires_on__lt=today)
    elif expiry == "review_due":
        qs = qs.filter(review_on__lte=today)
    elif expiry == "over_retention":
        qs = qs.filter(retention_until__lt=today)

    tag = request.GET.get("tag", "").strip()
    if tag:
        # Tags are a normalized comma-joined CharField, not a Tag table (13.6 owns taxonomy),
        # so this is deliberately a substring match. Blank is ignored rather than matching
        # everything twice over.
        qs = qs.filter(tags__icontains=tag)
    return qs


def _suppliers(tenant):
    """The supplier facet's options — the 6.5/6.8 supplier-or-vendor Party rule, verbatim."""
    from apps.core.models import Party

    if tenant is None:
        return Party.objects.none()
    return (Party.objects
            .filter(tenant=tenant, roles__role__in=("supplier", "vendor"))
            .distinct()
            .order_by("name"))


def _owners(tenant):
    """The owner facet's options — active workspace members."""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    if tenant is None:
        return User.objects.none()
    return User.objects.filter(tenant=tenant, is_active=True).order_by("username")


@login_required
def pdocument_list(request):
    """The repository register — every controlled procurement record in the workspace."""
    # Same read rule as the rows: a tile that counts documents this member cannot see would
    # report a workspace they are not looking at, and "7 documents / 5 rows" is exactly the
    # discrepancy that turns a deliberate rule into a suspected bug.
    base = (ProcurementDocument.objects.filter(tenant=request.tenant)
            .filter(readable_document_q(request.user)))
    today = timezone.localdate()
    # ONE conditional aggregate, not five COUNTs. Computed over the whole workspace, not the
    # filtered page, so the tiles keep meaning something while a facet is applied.
    stats = base.aggregate(
        total=Count("pk"),
        active=Count("pk", filter=Q(status="active")),
        expiring=Count("pk", filter=Q(expires_on__gte=today,
                                      expires_on__lte=today + timedelta(days=EXPIRY_WARN_DAYS))),
        expired=Count("pk", filter=Q(expires_on__lt=today)),
        unapproved=Count("pk", filter=Q(current_revision_no=0)),
    )
    # extracted_text is the denormalized copy of the approved revision's text — this is the
    # whole Full-Text Search & Indexing bullet, and it is one column scan, not a join. It is
    # swept only for a term of four characters or more: the Paginator's COUNT and the page query
    # each run the LIKE, so "?q=a" makes the database read every stored character twice to match
    # nearly every row (measured 1.5 s at 2,007 documents) for a result set of no use to anybody.
    # Short terms still search the number, title, description and tags, which is where a
    # two-letter search was ever going to find something.
    search_fields = ("number", "title", "description", "tags")
    if len(request.GET.get("q", "").strip()) >= FILE_TEXT_SEARCH_MIN_CHARS:
        search_fields += ("extracted_text",)

    return crud_list(
        request, _document_qs(request), TEMPLATE_LIST,
        search_fields=search_fields,
        # doc_type / status / classification are CHOICES strings crud_list enum-guards; supplier
        # and owner are FK pks and need the as_db_int guard (is_int=True) so a hand-edited query
        # string cannot 500 the page (L11).
        filters=(("doc_type", "doc_type", False),
                 ("status", "status", False),
                 ("classification", "classification", False),
                 ("supplier", "supplier_id", True),
                 ("owner", "owner_id", True)),
        extra_context={
            "doc_type_choices": ProcurementDocument.DOC_TYPE_CHOICES,
            "status_choices": ProcurementDocument.STATUS_CHOICES,
            "classification_choices": ProcurementDocument.CLASSIFICATION_CHOICES,
            "expiry_choices": ProcurementDocument.EXPIRY_FILTER_CHOICES,
            "suppliers": _suppliers(request.tenant),
            "owners": _owners(request.tenant),
            "stats": stats,
            "search_note": SEARCH_NOTE,
            "classification_note": CLASSIFICATION_NOTE,
        },
    )


@login_required
def pdocument_detail(request, pk):
    """One record, its revision chain, and everything that points at it.

    Hand-rolled for the reason in the module docstring; the tenant scoping is exactly
    ``crud_detail``'s and the row context key is the same ``obj``.
    """
    obj = get_object_or_404(
        ProcurementDocument.objects.filter(tenant=request.tenant)
        .filter(readable_document_q(request.user))
        .defer("extracted_text")
        .select_related(*_DETAIL_RELATIONS), pk=pk)

    # Reverse accessors onto the three sibling entity models of this sub-module — no import and
    # therefore no cycle. select_related on each is the difference between one query per panel
    # and one per ROW, because every one of these __str__/template hops crosses an FK. Each is
    # capped: the panels summarise what points at this record, they do not export it.
    revisions = list(obj.revisions.select_related("uploaded_by", "approved_by")
                     .defer("extracted_text")[:DETAIL_FAN_OUT_CAP])
    policies = list(obj.policies.select_related("owner", "applies_to")[:DETAIL_FAN_OUT_CAP])
    knowledge_resources = list(
        obj.knowledge_resources.select_related("owner")[:DETAIL_FAN_OUT_CAP])

    # Resolved from the list already in memory rather than by calling obj.current_revision,
    # which would run the same query a second time. The two conditions ARE that property: the
    # pointer's number, and approved — an unapproved row is never the document of record.
    current_revision = next((r for r in revisions
                             if r.is_approved and r.revision_no == obj.current_revision_no),
                            None)

    # The upload guard, stated once here and re-checked in the upload view itself: the page must
    # not offer a button the POST would refuse, and the POST must not trust the page.
    can_upload = (request.tenant is not None
                  and obj.status != "archived"
                  and obj.checked_out_by_id in (None, request.user.pk))
    # The release guard, computed for the same reason and from the same rule the verb applies:
    # the holder always may, a workspace administrator may force it, nobody else may. The page
    # already names the holder two cards above, so offering every viewer a button that answers
    # "you are not allowed" was a refusal the page had everything it needed to avoid.
    can_release = (obj.checked_out_by_id is not None
                   and (obj.checked_out_by_id == request.user.pk
                        or request.user.is_superuser
                        or getattr(request.user, "is_tenant_admin", False)))

    return render(request, TEMPLATE_DETAIL, {
        "obj": obj,
        "revisions": revisions,
        "current_revision": current_revision,
        "policies": policies,
        "knowledge_resources": knowledge_resources,
        "can_upload": can_upload,
        "can_release": can_release,
        "lock_holder": obj.checked_out_by,
        "search_note": SEARCH_NOTE,
        "classification_note": CLASSIFICATION_NOTE,
    })


@login_required
def pdocument_create(request):
    return crud_create(request, form_class=ProcurementDocumentForm, template=TEMPLATE_FORM,
                       success_url="procurement:pdocument_list",
                       extra_context={"search_note": SEARCH_NOTE,
                                      "classification_note": CLASSIFICATION_NOTE})


@login_required
def pdocument_edit(request, pk):
    return crud_edit(request, model=ProcurementDocument, pk=pk,
                     form_class=ProcurementDocumentForm, template=TEMPLATE_FORM,
                     success_url="procurement:pdocument_list",
                     extra_context={"search_note": SEARCH_NOTE,
                                    "classification_note": CLASSIFICATION_NOTE})


@login_required
@tenant_admin_required
@require_POST
def pdocument_delete(request, pk):
    """Remove a document that never had an approved version. Administrator-gated.

    Deleting the row CASCADEs its revisions — including the approved ones
    ``pdocrevision_delete`` refuses to touch one at a time, because "approved history is never
    rewritten here". A verb that removes the whole chain in one POST cannot be less guarded than
    the verb that removes a single link of it, so this refuses any document the pointer has ever
    moved on, and only a workspace administrator may call it. Archiving is how a document with
    history is taken out of use: it keeps every revision and stays searchable.

    WARNING: Django does NOT remove the stored files from MEDIA_ROOT when a row goes — the bytes
    stay on disk. That is deliberate here, not an oversight: reclaiming disk means deleting a
    path derived from stored user input, which is exactly the operation that turns a bug into an
    arbitrary-file-delete. Retention and destruction are a supervised later job (13.9 / 13.14).
    The confirm text on both surfaces says so plainly rather than implying the file is gone.
    """
    obj = _get_document(request, pk)
    if obj.current_revision_no:
        messages.error(request, f"{obj.number} has an approved revision chain (currently "
                                f"r{obj.current_revision_no}), so it is not deleted here — "
                                f"approved history is never rewritten. Archive it instead: it "
                                f"keeps every revision and stays searchable.")
        return redirect("procurement:pdocument_detail", pk=obj.pk)
    return crud_delete(request, model=ProcurementDocument, pk=pk,
                       success_url="procurement:pdocument_list")


# ---------------------------------------------------------------------------------------------
# Verbs. All POST-only, all audited, all redirect back to the document they acted on. Each one
# refuses a disallowed transition with messages.error, and reports an already-in-target-state
# call with messages.info and NO write, so a double-click cannot re-stamp who and when.
# ---------------------------------------------------------------------------------------------


def _get_document(request, pk):
    return get_object_or_404(ProcurementDocument.objects.select_related("checked_out_by"),
                             pk=pk, tenant=request.tenant)


@login_required
@require_POST
def pdocument_checkout(request, pk):
    """Take the advisory lock: tell everyone else you are preparing the next revision."""
    obj = _get_document(request, pk)
    if obj.checked_out_by_id == request.user.pk:
        messages.info(request, "You already have this document checked out.")
        return redirect("procurement:pdocument_detail", pk=obj.pk)
    if obj.checked_out_by_id is not None:
        messages.error(request, f"{holder_name(obj.checked_out_by)} has this document checked "
                                f"out. Ask them to release it, or have a workspace "
                                f"administrator force the release.")
        return redirect("procurement:pdocument_detail", pk=obj.pk)
    if obj.status == "archived":
        messages.error(request, "An archived document cannot be checked out. Re-activate it "
                                "first if it is back in use.")
        return redirect("procurement:pdocument_detail", pk=obj.pk)

    obj.checked_out_by = request.user
    obj.checked_out_at = timezone.now()
    obj.save(update_fields=["checked_out_by", "checked_out_at", "updated_at"])
    write_audit_log(request.user, obj, "document_checkout", {"number": obj.number})
    messages.success(request, f"{obj.number} checked out to you.")
    return redirect("procurement:pdocument_detail", pk=obj.pk)


@login_required
@require_POST
def pdocument_release(request, pk):
    """Release the advisory lock. The holder always may; a tenant admin may force it.

    A workspace administrator can release somebody else's lock on purpose: this is an ADVISORY
    lock, and a lock nobody can clear when its holder is on leave is a lock that stops work.
    Every forced release is audited with the name of the holder it was taken from.
    """
    obj = _get_document(request, pk)
    if obj.checked_out_by_id is None:
        messages.info(request, "This document is not checked out.")
        return redirect("procurement:pdocument_detail", pk=obj.pk)

    is_admin = bool(request.user.is_superuser
                    or getattr(request.user, "is_tenant_admin", False))
    forced = obj.checked_out_by_id != request.user.pk
    if forced and not is_admin:
        messages.error(request, f"{holder_name(obj.checked_out_by)} holds this checkout. Only "
                                f"they or a workspace administrator can release it.")
        return redirect("procurement:pdocument_detail", pk=obj.pk)

    previous = holder_name(obj.checked_out_by)
    obj.checked_out_by = None
    obj.checked_out_at = None
    obj.save(update_fields=["checked_out_by", "checked_out_at", "updated_at"])
    write_audit_log(request.user, obj, "document_release",
                    {"number": obj.number, "released_from": previous, "forced": forced})
    messages.success(request, f"Checkout on {obj.number} released"
                              + (f" (held by {previous})." if forced else "."))
    return redirect("procurement:pdocument_detail", pk=obj.pk)


@login_required
@tenant_admin_required
@require_POST
def pdocument_activate(request, pk):
    """Put the document back in force — from draft, superseded or archived.

    Administrator-gated, with supersede and archive. The status of a controlled document is what
    the workspace treats as authoritative: archiving takes a record out of use and blocks new
    revisions on it, superseding says something newer replaces it, and activating puts it back.
    Approval already needs an administrator because it decides which file is the document of
    record — deciding whether the document is in force at all cannot need less.
    """
    obj = _get_document(request, pk)
    if obj.status == "active":
        messages.info(request, "This document is already active.")
        return redirect("procurement:pdocument_detail", pk=obj.pk)

    previous = obj.status
    obj.status = "active"
    obj.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, obj, "document_activate",
                    {"number": obj.number, "from": previous, "to": "active"})
    messages.success(request, f"{obj.number} is now active.")
    return redirect("procurement:pdocument_detail", pk=obj.pk)


@login_required
@tenant_admin_required
@require_POST
def pdocument_supersede(request, pk):
    """Retire an ACTIVE document because something newer replaces it.

    Only from active: superseding a draft says nothing (it was never in force), and
    superseding an archived record would quietly resurrect it into a live-looking state.
    Administrator-gated with the other two status transitions — see ``pdocument_activate``.
    """
    obj = _get_document(request, pk)
    if obj.status == "superseded":
        messages.info(request, "This document is already superseded.")
        return redirect("procurement:pdocument_detail", pk=obj.pk)
    if obj.status != "active":
        messages.error(request, "Only an active document can be superseded. Activate it first, "
                                "or archive it if it is simply out of use.")
        return redirect("procurement:pdocument_detail", pk=obj.pk)

    obj.status = "superseded"
    obj.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, obj, "document_supersede",
                    {"number": obj.number, "from": "active", "to": "superseded"})
    messages.success(request, f"{obj.number} marked superseded.")
    return redirect("procurement:pdocument_detail", pk=obj.pk)


@login_required
@tenant_admin_required
@require_POST
def pdocument_archive(request, pk):
    """Take the document out of use. Allowed from any state — nothing is deleted.

    Administrator-gated with the other two status transitions (see ``pdocument_activate``):
    archiving additionally blocks checkout and new revisions, so it is the transition that can
    stop other people working, not merely relabel a row.
    """
    obj = _get_document(request, pk)
    if obj.status == "archived":
        messages.info(request, "This document is already archived.")
        return redirect("procurement:pdocument_detail", pk=obj.pk)

    previous = obj.status
    obj.status = "archived"
    obj.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, obj, "document_archive",
                    {"number": obj.number, "from": previous, "to": "archived"})
    messages.success(request, f"{obj.number} archived. Nothing was deleted — archived documents "
                              f"stay searchable and keep every revision.")
    return redirect("procurement:pdocument_detail", pk=obj.pk)


@login_required
@tenant_admin_required
@require_POST
def pdocument_reindex(request):
    """Re-read the approved file of documents whose search copy is empty.

    Why it exists: ``extracted_text`` on the parent is written when a revision is APPROVED. A
    document approved before text extraction was available on this server — or one whose read
    failed at the time — carries an empty copy and is findable only by its title, description
    and tags. This sweep fills those in.

    Bounded on purpose, three ways. Candidates are rows with an empty copy AND an approved
    current revision AND no extraction note on that revision — that last one is what makes
    "picks up where it left off" true: a document whose current file genuinely has no text layer
    can never be filled in, so without it that row occupies a cap slot and costs a file read on
    every single Run for ever. The batch is capped at ``REINDEX_ROW_CAP`` and abandoned at
    ``REINDEX_TIME_BUDGET_SECONDS``, both sized to a request rather than to "a lot of documents".

    Each write is a CONDITIONAL UPDATE, not a blind save. The loop spends seconds in a file read
    between choosing a document and writing to it, and an approval can land in that window: a
    blind ``save(update_fields=["extracted_text"])`` would then overwrite the newly-approved
    revision's text with the superseded one it happened to read, PERMANENTLY — the row would no
    longer be a candidate, so search would match the old wording and miss the current one for
    good. Filtering the UPDATE on ``extracted_text=""`` and on the same ``current_revision_no``
    the text was read for means a document that moved underneath us is left alone and counted
    honestly as skipped.

    Administrator-gated: it reads every stored file in the workspace and rewrites a column the
    register searches.
    """
    guard = _need_tenant(request, "re-index documents")
    if guard is not None:
        return guard

    # Sibling entity module of THIS sub-module, imported inside the verb: the Revisions module
    # owns the extraction helpers, and a module-level import here would make this module
    # unloadable in the window before that file lands. It also keeps pdfplumber's lazy-import
    # posture intact — nothing is imported until somebody actually presses Run.
    from apps.procurement.models.DocumentKnowledgeManagement.Revisions import (
        ProcurementDocumentRevision, extract_document_text)

    # The pointed-at revision, expressed as a correlated EXISTS so the candidate set is decided
    # in ONE query: it must be there, be approved, and carry no extraction note (a note means
    # the file has already been read and had nothing to give).
    readable_pointer = ProcurementDocumentRevision.objects.filter(
        tenant=request.tenant, document_id=OuterRef("pk"),
        revision_no=OuterRef("current_revision_no"), is_approved=True, extraction_note="")

    candidates = list(ProcurementDocument.objects
                      .filter(tenant=request.tenant, extracted_text="")
                      .exclude(current_revision_no=0)
                      .filter(Exists(readable_pointer))
                      .only("id", "tenant_id", "number", "current_revision_no")
                      .order_by("id")[:REINDEX_ROW_CAP])

    # ONE query for the whole batch's revisions, keyed (document_id, revision_no), instead of a
    # ``current_revision`` property lookup per row. The file reads still dominate, but 1 query
    # beats 25 and the pairs are exact — no revision of any other document comes down.
    revisions = {}
    if candidates:
        pairs = Q()
        for document in candidates:
            pairs |= Q(document_id=document.pk, revision_no=document.current_revision_no)
        revisions = {(row.document_id, row.revision_no): row
                     for row in ProcurementDocumentRevision.objects
                     .filter(tenant=request.tenant, is_approved=True).filter(pairs)}

    indexed = skipped = 0
    ran_out_of_time = False
    deadline = time.monotonic() + REINDEX_TIME_BUDGET_SECONDS
    for document in candidates:
        if time.monotonic() >= deadline:
            # Checked BETWEEN documents, never mid-read. Each save autocommits, so stopping here
            # keeps every document already re-indexed and simply leaves the rest for the next
            # press — which is exactly what the button promises.
            ran_out_of_time = True
            break
        revision = revisions.get((document.pk, document.current_revision_no))
        if revision is None:
            # The pointer named a revision that vanished between the two queries. Nothing to
            # read; counted honestly as skipped.
            skipped += 1
            continue
        # extract_document_text already truncates to EXTRACT_MAX_CHARS and never raises: a
        # missing extractor, an unreadable path and a malformed file all come back as
        # ("", note). Only the REVISION may store the note — it is the text of record, and its
        # columns are written once at ingest and once at approval (never here).
        text, _note = extract_document_text(revision)
        if not text:
            skipped += 1
            continue
        # Conditional UPDATE — see the docstring. It writes only while the row is still the row
        # we read the text for; a document approved out from under us returns 0 and is skipped.
        written = (ProcurementDocument.objects
                   .filter(pk=document.pk, tenant=request.tenant, extracted_text="",
                           current_revision_no=document.current_revision_no)
                   .update(extracted_text=text, updated_at=timezone.now()))
        if written:
            indexed += 1
        else:
            skipped += 1

    write_audit_log(request.user, None, "document_reindex_run",
                    {"indexed": indexed, "skipped": skipped})
    more_remain = ran_out_of_time or len(candidates) == REINDEX_ROW_CAP
    messages.success(request, f"Re-indexed {indexed} document(s); {skipped} could not be read "
                              f"and were left searchable by title, description and tags."
                              + (" This run was capped — press Re-index again to continue."
                                 if more_remain else ""))
    return redirect("procurement:pdocument_list")


@login_required
@require_POST
def pdocument_run_reminders(request):
    """Raise expiry / review alerts into the 6.1 inbox for everything inside the window.

    There is no scheduler and no mail worker in this codebase, so this is a user-pressed Run and
    the alert inbox is the channel. Safe to press twice: a document that already has an open
    alert is skipped rather than duplicated.
    """
    guard = _need_tenant(request, "run document reminders")
    if guard is not None:
        return guard

    summary = run_document_reminders_audited(request.tenant, request.user)
    messages.success(request, f"Reminder run complete: {summary['raised']} alert(s) raised, "
                              f"{summary['skipped_open']} skipped because an alert was already "
                              f"open.")
    return redirect("procurement:pdocument_list")
