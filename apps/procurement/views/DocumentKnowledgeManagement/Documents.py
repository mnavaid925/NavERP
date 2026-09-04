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
from datetime import timedelta

from django.db.models import Count, Q

from apps.procurement.forms.DocumentKnowledgeManagement.Documents import ProcurementDocumentForm
# NOT-YET-WIRED entity of this SAME sub-module: import the entity MODULE directly, never
# ``from apps.procurement.models import X`` — the sub-package is not wired until the Integrator
# lands it, and a package-level re-export would be a star-import cycle at URLconf import time.
from apps.procurement.models.DocumentKnowledgeManagement.Documents import (
    EXPIRY_WARN_DAYS, REINDEX_ROW_CAP, ProcurementDocument, run_document_reminders_audited)
from apps.procurement.views._common import *  # noqa: F401,F403

TEMPLATE_LIST = "procurement/documentknowledge/document/list.html"
TEMPLATE_DETAIL = "procurement/documentknowledge/document/detail.html"
TEMPLATE_FORM = "procurement/documentknowledge/document/form.html"

#: What one register ROW renders. Pinned once so the list's select_related and the detail's
#: cannot drift apart.
_ROW_RELATIONS = ("supplier", "owner", "contract", "purchase_order", "sourcing_event")
#: The detail page additionally names the lock holder and the author.
_DETAIL_RELATIONS = _ROW_RELATIONS + ("checked_out_by", "created_by")

#: Printed on the register and the detail page — ONE constant so the two surfaces cannot describe
#: the search differently, and so the limits of text extraction are stated where people search
#: rather than buried in a docstring.
SEARCH_NOTE = (
    "Search matches the title, description, tags and any text read from the approved file. "
    "Text is read from PDFs that carry a text layer and from plain-text uploads; a scanned "
    "image has no text to read."
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
    """
    qs = (ProcurementDocument.objects.filter(tenant=request.tenant)
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
    base = ProcurementDocument.objects.filter(tenant=request.tenant)
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
    return crud_list(
        request, _document_qs(request), TEMPLATE_LIST,
        # extracted_text is the denormalized copy of the approved revision's text — this is the
        # whole Full-Text Search & Indexing bullet, and it is one column scan, not a join.
        search_fields=("number", "title", "description", "tags", "extracted_text"),
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
        .select_related(*_DETAIL_RELATIONS), pk=pk)

    # Reverse accessors onto the three sibling entity models of this sub-module — no import and
    # therefore no cycle. select_related on each is the difference between one query per panel
    # and one per ROW, because every one of these __str__/template hops crosses an FK.
    revisions = list(obj.revisions.select_related("uploaded_by", "approved_by"))
    policies = list(obj.policies.select_related("owner", "applies_to"))
    knowledge_resources = list(obj.knowledge_resources.select_related("owner"))

    # The upload guard, stated once here and re-checked in the upload view itself: the page must
    # not offer a button the POST would refuse, and the POST must not trust the page.
    can_upload = (request.tenant is not None
                  and obj.status != "archived"
                  and obj.checked_out_by_id in (None, request.user.pk))

    return render(request, TEMPLATE_DETAIL, {
        "obj": obj,
        "revisions": revisions,
        "current_revision": obj.current_revision,
        "policies": policies,
        "knowledge_resources": knowledge_resources,
        "can_upload": can_upload,
        "lock_holder": obj.checked_out_by,
        "search_note": SEARCH_NOTE,
    })


@login_required
def pdocument_create(request):
    return crud_create(request, form_class=ProcurementDocumentForm, template=TEMPLATE_FORM,
                       success_url="procurement:pdocument_list",
                       extra_context={"search_note": SEARCH_NOTE})


@login_required
def pdocument_edit(request, pk):
    return crud_edit(request, model=ProcurementDocument, pk=pk,
                     form_class=ProcurementDocumentForm, template=TEMPLATE_FORM,
                     success_url="procurement:pdocument_list",
                     extra_context={"search_note": SEARCH_NOTE})


@login_required
@require_POST
def pdocument_delete(request, pk):
    # WARNING: deleting the row CASCADEs its revisions, and Django does NOT remove the stored
    # files from MEDIA_ROOT when a row goes — the bytes stay on disk. That is deliberate here,
    # not an oversight: reclaiming disk means deleting a path derived from stored user input,
    # which is exactly the operation that turns a bug into an arbitrary-file-delete. Retention
    # and destruction are a supervised later job (13.9 / 13.14). The confirm text on both
    # surfaces says so plainly rather than implying the file is gone.
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


def _holder_name(user):
    """A person's name for a refusal message — never a bare pk."""
    return (user.get_full_name() or user.username) if user is not None else "someone else"


@login_required
@require_POST
def pdocument_checkout(request, pk):
    """Take the advisory lock: tell everyone else you are preparing the next revision."""
    obj = _get_document(request, pk)
    if obj.checked_out_by_id == request.user.pk:
        messages.info(request, "You already have this document checked out.")
        return redirect("procurement:pdocument_detail", pk=obj.pk)
    if obj.checked_out_by_id is not None:
        messages.error(request, f"{_holder_name(obj.checked_out_by)} has this document checked "
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
        messages.error(request, f"{_holder_name(obj.checked_out_by)} holds this checkout. Only "
                                f"they or a workspace administrator can release it.")
        return redirect("procurement:pdocument_detail", pk=obj.pk)

    previous = _holder_name(obj.checked_out_by)
    obj.checked_out_by = None
    obj.checked_out_at = None
    obj.save(update_fields=["checked_out_by", "checked_out_at", "updated_at"])
    write_audit_log(request.user, obj, "document_release",
                    {"number": obj.number, "released_from": previous, "forced": forced})
    messages.success(request, f"Checkout on {obj.number} released"
                              + (f" (held by {previous})." if forced else "."))
    return redirect("procurement:pdocument_detail", pk=obj.pk)


@login_required
@require_POST
def pdocument_activate(request, pk):
    """Put the document back in force — from draft, superseded or archived."""
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
@require_POST
def pdocument_supersede(request, pk):
    """Retire an ACTIVE document because something newer replaces it.

    Only from active: superseding a draft says nothing (it was never in force), and
    superseding an archived record would quietly resurrect it into a live-looking state.
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
@require_POST
def pdocument_archive(request, pk):
    """Take the document out of use. Allowed from any state — nothing is deleted."""
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

    Bounded on purpose. Only rows with an empty copy AND an approved revision are candidates,
    capped at ``REINDEX_ROW_CAP``: the verb opens files off disk one at a time, and an unbounded
    sweep over a large workspace is a request timeout. Running it again picks up where it left
    off, which is why it is a repeatable Run rather than a one-shot migration.

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
        extract_document_text)

    indexed = skipped = 0
    # One query per document for its current revision. Deliberate: the file read dominates by
    # orders of magnitude, the Run is capped, and prefetching every revision of every document
    # to save it would cost more rows than it saves queries.
    candidates = (ProcurementDocument.objects
                  .filter(tenant=request.tenant, extracted_text="")
                  .exclude(current_revision_no=0)
                  .order_by("id")[:REINDEX_ROW_CAP])
    for document in candidates:
        revision = document.current_revision
        if revision is None:
            # current_revision_no points at a revision that is not there — a row deleted out
            # from under the pointer. Nothing to read; counted honestly as skipped.
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
        document.extracted_text = text
        document.save(update_fields=["extracted_text", "updated_at"])
        indexed += 1

    write_audit_log(request.user, None, "document_reindex_run",
                    {"indexed": indexed, "skipped": skipped})
    messages.success(request, f"Re-indexed {indexed} document(s); {skipped} had no readable "
                              f"text and were left searchable by title, description and tags.")
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
