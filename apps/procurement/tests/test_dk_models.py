"""Procurement 6.19 - Document & Knowledge Management MODEL tests.

The invariants this lane owns:

* **the revision chain**, which is where the sub-module actually lives. A document points at one
  approved revision through an integer ``current_revision_no``; a revision is immutable except for
  its ``change_note``; and - the rule the whole I1/I2/I3 family of review findings turned on - an
  **unapproved revision can never be the document of record**. ``current_revision`` filters
  ``is_approved=True``, so a pointer left naming a pending row resolves to ``None`` rather than
  presenting a file nobody signed off. ``revision.is_current`` stays number-equality only, which is
  deliberate and documented (it drives the conservative "you may still delete this" direction), so
  this lane pins BOTH halves rather than "fixing" one of them in a test;
* per-tenant ``PDOC-`` / ``PPOL-`` / ``PKR-`` auto-numbering - allocated once, surviving a re-save,
  restarting per workspace - and every ``unique_together`` that keeps a workspace's register
  coherent;
* the text pipeline: ``file_sha256`` (streamed, pointer restored before AND after) and
  ``extract_document_text``, which is **bounded** (``EXTRACT_MAX_CHARS`` / ``MAX_EXTRACT_PAGES`` /
  a character budget) and **never raises** - every failure comes back as ``("", <a sentence>)``,
  because it runs inside a user-pressed upload and inside the re-index Run;
* the policy library's supersession guard - self-supersession, a two-hop ``A -> B -> A`` loop, a
  loop that is already in the data, and a chain deeper than ``MAX_CHAIN_DEPTH`` are each refused
  with their own sentence - and the fact that a policy's thresholds are **inert documentation**: no
  model code branches on them (approval bands are 6.3's ``ApprovalRoutingRule`` rows);
* ``KnowledgeResource``'s ordering, which is a **pagination-stability** invariant rather than
  cosmetics: ``-is_featured, -created_at, -id`` with the unique id tiebreak is what stops a
  Paginator repeating one row on page 2 while dropping another;
* and the reminder engine - the module-level ``expiring_documents`` / ``run_document_reminders``
  pair (there is no scheduler in this codebase): the right rows, one alert per document, a second
  press that raises nothing in two queries, and the ``tenant is None`` guard.

Determinism (L16): every date basis here is ``timezone.localdate()`` and every datetime basis is
``timezone.now()`` - the same bases the model code uses. ``datetime.date.today()`` never appears,
or the exact-window assertions flake for the hours after local midnight. Nothing here touches the
network, and every stored byte lands under ``dk_media_root`` (pytest's ``tmp_path``).
"""
import datetime
import hashlib
import os
import re
import sys
import types
from decimal import Decimal

import pytest
from django.core.exceptions import FieldDoesNotExist, ValidationError
from django.core.files.base import ContentFile
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.procurement.models import (
    KnowledgeResource,
    ProcurementAlert,
    ProcurementDocument,
    ProcurementDocumentRevision,
    ProcurementPolicy,
    expiring_documents,
    run_document_reminders,
    run_document_reminders_audited,
)
from apps.procurement.models.DocumentKnowledgeManagement import Documents as _dk_documents_mod
from apps.procurement.models.DocumentKnowledgeManagement import (
    KnowledgeResources as _dk_resources_mod)
from apps.procurement.models.DocumentKnowledgeManagement import Policies as _dk_policies_mod
from apps.procurement.models.DocumentKnowledgeManagement import Revisions as _dk_revisions_mod
from apps.procurement.models.DocumentKnowledgeManagement.Documents import (
    EXPIRY_WARN_DAYS, REINDEX_ROW_CAP, REMINDER_WINDOW_DAYS, normalize_tags)
from apps.procurement.models.DocumentKnowledgeManagement.KnowledgeResources import FEATURED_CAP
from apps.procurement.models.DocumentKnowledgeManagement.Policies import (
    MAX_CHAIN_DEPTH, supersession_conflict)
from apps.procurement.models.DocumentKnowledgeManagement.Revisions import (
    EXTRACT_MAX_CHARS, MAX_EXTRACT_PAGES, NOTE_BAD_FILE, NOTE_NO_EXTRACTOR, NOTE_NO_TEXT_LAYER,
    NOTE_UNREADABLE_PATH, PLAIN_TEXT_EXTENSIONS, extract_document_text, file_sha256,
    next_revision_no)
from apps.procurement.tests.conftest import (
    _dk_approve, _dk_document, _dk_documents, _dk_policy, _dk_resource, _dk_revision)

pytestmark = pytest.mark.django_db


# -- local helpers ------------------------------------------------------------------------------
# Named _dk_* / _DK_* so the next sub-module appending near this file cannot shadow them and so a
# failure names its own lane (L47). The record factories come from conftest, which owns them; only
# what conftest does NOT provide is built here.

#: theme.css ships exactly these modifier classes. Anything else renders completely unstyled (L33).
_DK_BADGE_COLOURS = {
    "badge-green", "badge-red", "badge-amber", "badge-info", "badge-muted", "badge-slate",
}

#: The middot (U+00B7) that ``ProcurementDocument.__str__`` and ``KnowledgeResource.__str__`` fold
#: into their labels - kept in one constant, exactly as the 6.14 lane keeps ``_SPEND_DOT``.
_DK_DOT = "·"


def _dk_today():
    """The SAME date basis the models use (L16) - never ``datetime.date.today()``."""
    return timezone.localdate()


def _dk_days(delta):
    """``today + delta`` days, from the model's own basis."""
    return _dk_today() + datetime.timedelta(days=delta)


def _dk_field(model, name):
    return model._meta.get_field(name)


def _dk_field_names(model):
    return {f.name for f in model._meta.get_fields()}


def _dk_not_editable(model):
    return {f.name for f in model._meta.concrete_fields if not f.editable}


def _dk_index_names(model):
    return {index.name for index in model._meta.indexes}


def _dk_index_fields(model):
    return {tuple(index.fields) for index in model._meta.indexes}


def _dk_values(choices):
    return [value for value, _label in choices]


def _dk_pin_created_at(model, pks, when):
    """Force an identical ``created_at`` on several rows.

    ``auto_now_add`` cannot be set through ``save()``, and the tie is the whole point: an ordering
    that only looks stable because two rows differ by microseconds has not been tested at all.
    """
    model.objects.filter(pk__in=list(pks)).update(created_at=when)


def _dk_sourcing_event(tenant, title="Globex-only tender"):
    """A ``SourcingEvent`` in ``tenant`` - conftest has no tenant-B one, and the document's
    ``clean()`` cross-tenant loop covers this FK too."""
    from apps.procurement.models import SourcingEvent
    return SourcingEvent.objects.create(tenant=tenant, title=title, event_type="tender",
                                        status="draft")


def _dk_supplier_contract(tenant, party, title="Globex master agreement"):
    """An ``scm.SupplierContract`` in ``tenant`` - the fourth spine FK ``clean()`` guards."""
    from apps.scm.models import SupplierContract
    return SupplierContract.objects.create(tenant=tenant, party=party, title=title)


class _DkStubPage:
    """One page of the stubbed PDF, counting what the extractor actually asked it for."""

    def __init__(self, text, counter):
        self._text = text
        self._counter = counter

    def extract_text(self):
        self._counter["parsed"] += 1
        return self._text

    def flush_cache(self):
        self._counter["flushed"] += 1


class _DkStubPdf:
    def __init__(self, pages):
        self.pages = pages

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


def _dk_stub_pdfplumber(monkeypatch, page_count, text_per_page):
    """Install a fake ``pdfplumber`` and return the call counter it writes into.

    ``extract_document_text`` imports pdfplumber INSIDE the function, so putting a module object in
    ``sys.modules`` is enough - and it makes the two I9 bounds (the page cap and the character
    budget) assertable without shipping a 500-page PDF into the repository.
    """
    counter = {"parsed": 0, "flushed": 0}
    pages = [_DkStubPage(text_per_page, counter) for _ in range(page_count)]
    module = types.ModuleType("pdfplumber")
    module.open = lambda path: _DkStubPdf(pages)
    monkeypatch.setitem(sys.modules, "pdfplumber", module)
    return counter


# =================================================================================================
# ProcurementDocument - numbering, __str__, Meta
# =================================================================================================

def test_dk_document_number_is_allocated_on_first_save_with_the_pdoc_prefix(tenant_a):
    document = _dk_document(tenant_a)
    assert document.number == "PDOC-00001"
    assert ProcurementDocument.NUMBER_PREFIX == "PDOC"


def test_dk_document_numbers_advance_within_a_workspace(tenant_a):
    numbers = [_dk_document(tenant_a, title=f"Row {i}").number for i in range(1, 4)]
    assert numbers == ["PDOC-00001", "PDOC-00002", "PDOC-00003"]


def test_dk_document_numbers_do_not_collide_across_workspaces(tenant_a, tenant_b):
    """Numbering is per tenant: Globex's first document is PDOC-00001 even though Acme has one."""
    _dk_document(tenant_a)
    assert _dk_document(tenant_b).number == "PDOC-00001"


def test_dk_document_number_is_assigned_once_and_survives_a_re_save(tenant_a):
    """The number identifies the record for its whole life - a later edit must not re-mint it."""
    document = _dk_document(tenant_a)
    minted = document.number
    _dk_document(tenant_a, title="A later row")          # moves the sequence on
    document.title = "Renamed after the fact"
    document.save()
    document.refresh_from_db()
    assert document.number == minted == "PDOC-00001"


def test_dk_document_number_is_unique_per_workspace(tenant_a):
    _dk_document(tenant_a, number="PDOC-09999")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _dk_document(tenant_a, title="Duplicate number", number="PDOC-09999")


def test_dk_document_number_is_free_again_in_another_workspace(tenant_a, tenant_b):
    _dk_document(tenant_a, number="PDOC-09999")
    other = _dk_document(tenant_b, title="Globex row", number="PDOC-09999")
    assert other.pk is not None
    assert ProcurementDocument._meta.unique_together == (("tenant", "number"),)


def test_dk_document_str_reads_the_number_then_the_title(dk_document_draft_a):
    assert str(dk_document_draft_a) == (f"{dk_document_draft_a.number} {_DK_DOT} "
                                        f"Draft specification - server rack")


def test_dk_document_str_on_an_unsaved_instance_never_starts_with_the_dot():
    """A ModelForm rendering its own errors has no number yet - the page must not read " - Title"."""
    assert str(ProcurementDocument(title="Half-built")) == f"PDOC {_DK_DOT} Half-built"


def test_dk_document_meta_ordering_is_newest_first_with_an_id_tiebreak(tenant_a):
    """The id tiebreak is what makes the register's paging deterministic, not decoration."""
    assert ProcurementDocument._meta.ordering == ["-created_at", "-id"]
    rows = _dk_documents(tenant_a, 4)
    _dk_pin_created_at(ProcurementDocument, [row.pk for row in rows], timezone.now())
    ordered = list(ProcurementDocument.objects.filter(tenant=tenant_a))
    assert [row.pk for row in ordered] == sorted((row.pk for row in rows), reverse=True)
    # Evaluated twice, the same order both times - an unstable sort silently duplicates a row
    # across page boundaries.
    assert ordered == list(ProcurementDocument.objects.filter(tenant=tenant_a))


def test_dk_document_meta_indexes_include_tenant_review_on():
    """I16 - the ?expiry=review_due facet and the reminder scan's review branch both need it."""
    assert ("tenant", "review_on") in _dk_index_fields(ProcurementDocument)
    assert _dk_index_names(ProcurementDocument) == {
        "prc_pdoc_tnt_status_idx", "prc_pdoc_tnt_type_idx", "prc_pdoc_tnt_expiry_idx",
        "prc_pdoc_tnt_review_idx", "prc_pdoc_tnt_sup_idx"}


def test_dk_document_reverse_accessors_are_the_three_the_detail_page_reads(dk_document_active_a,
                                                                          dk_policy_published_a,
                                                                          dk_resource_featured_a):
    assert list(dk_document_active_a.policies.all()) == [dk_policy_published_a]
    assert list(dk_document_active_a.knowledge_resources.all()) == [dk_resource_featured_a]
    assert list(dk_document_active_a.revisions.all()) == []


# =================================================================================================
# ProcurementDocument - vocabulary, badges, defaults
# =================================================================================================

def test_dk_document_choice_vocabulary_is_the_documented_one():
    assert _dk_values(ProcurementDocument.DOC_TYPE_CHOICES) == [
        "quote", "specification", "warranty", "certificate", "insurance", "sow", "drawing",
        "correspondence", "policy", "template", "other"]
    assert _dk_values(ProcurementDocument.CLASSIFICATION_CHOICES) == [
        "public", "internal", "confidential", "restricted"]
    assert _dk_values(ProcurementDocument.STATUS_CHOICES) == [
        "draft", "active", "superseded", "archived"]
    # A register FACET, not a column - there is no ``expiry`` field to filter on.
    assert _dk_values(ProcurementDocument.EXPIRY_FILTER_CHOICES) == [
        "expiring", "expired", "review_due", "over_retention"]
    assert "expiry" not in _dk_field_names(ProcurementDocument)


def test_dk_document_class_vocabulary_is_the_module_vocabulary():
    """Templates and tests reach the tuples through the class; both must be the same object."""
    assert ProcurementDocument.DOC_TYPE_CHOICES is _dk_documents_mod.DOC_TYPE_CHOICES
    assert ProcurementDocument.CLASSIFICATION_CHOICES is _dk_documents_mod.CLASSIFICATION_CHOICES
    assert ProcurementDocument.STATUS_CHOICES is _dk_documents_mod.STATUS_CHOICES
    assert ProcurementDocument.EXPIRY_WARN_DAYS == EXPIRY_WARN_DAYS == 30
    assert REMINDER_WINDOW_DAYS == 30
    assert REINDEX_ROW_CAP == 25


@pytest.mark.parametrize("status", _dk_values(ProcurementDocument.STATUS_CHOICES))
def test_dk_document_every_status_value_round_trips(status, tenant_a):
    document = ProcurementDocument(tenant=tenant_a, title="Vocabulary probe", status=status)
    document.full_clean()
    document.save()
    document.refresh_from_db()
    assert document.status == status
    assert document.get_status_display() == dict(ProcurementDocument.STATUS_CHOICES)[status]


@pytest.mark.parametrize("classification",
                         _dk_values(ProcurementDocument.CLASSIFICATION_CHOICES))
def test_dk_document_every_classification_value_round_trips(classification, tenant_a):
    document = ProcurementDocument(tenant=tenant_a, title="Vocabulary probe",
                                   classification=classification)
    document.full_clean()
    document.save()
    document.refresh_from_db()
    assert document.classification == classification


@pytest.mark.parametrize("doc_type", _dk_values(ProcurementDocument.DOC_TYPE_CHOICES))
def test_dk_document_every_doc_type_value_round_trips(doc_type, tenant_a):
    document = ProcurementDocument(tenant=tenant_a, title="Vocabulary probe", doc_type=doc_type)
    document.full_clean()
    assert document.get_doc_type_display()


def test_dk_document_rejects_a_status_outside_the_vocabulary(tenant_a):
    document = ProcurementDocument(tenant=tenant_a, title="Junk status", status="mislaid")
    with pytest.raises(ValidationError) as exc:
        document.full_clean()
    assert "status" in exc.value.message_dict


def test_dk_document_badge_maps_are_colour_named_and_total(dk_document_active_a):
    """L33 - theme.css ships no semantic badge-success/-warning/-danger; those render unstyled."""
    assert set(ProcurementDocument.STATUS_CSS) == set(
        _dk_values(ProcurementDocument.STATUS_CHOICES))
    assert set(ProcurementDocument.CLASSIFICATION_CSS) == set(
        _dk_values(ProcurementDocument.CLASSIFICATION_CHOICES))
    assert set(ProcurementDocument.STATUS_CSS.values()) <= _DK_BADGE_COLOURS
    assert set(ProcurementDocument.CLASSIFICATION_CSS.values()) <= _DK_BADGE_COLOURS
    assert dk_document_active_a.status_css == "badge-green"
    assert dk_document_active_a.classification_css == "badge-slate"


def test_dk_document_badge_helpers_fall_back_instead_of_raising():
    """A value written before a vocabulary change must still render a badge, not a KeyError."""
    stray = ProcurementDocument(title="Stray", status="mislaid", classification="mislaid")
    assert stray.status_css == "badge-slate"
    assert stray.classification_css == "badge-slate"


def test_dk_document_defaults_are_the_documented_ones(tenant_a):
    document = ProcurementDocument.objects.create(tenant=tenant_a, title="Bare row")
    document.refresh_from_db()
    assert document.doc_type == "other"
    assert document.classification == "internal"
    assert document.status == "draft"
    assert document.current_revision_no == 0
    assert document.supplier_visible is False
    assert document.extracted_text == ""
    assert document.tags == ""
    assert (document.checked_out_by_id, document.checked_out_at) == (None, None)
    assert document.owner_id is None and document.created_by_id is None
    assert document.created_at is not None and document.updated_at is not None


def test_dk_document_system_columns_are_never_form_fields():
    """L20/L22 - the pointer, the lock, the search copy and the audit stamps are machine-written."""
    assert {"number", "current_revision_no", "checked_out_by", "checked_out_at", "extracted_text",
            "created_by", "created_at", "updated_at"} <= _dk_not_editable(ProcurementDocument)
    # No FileField on the parent: bytes only ever arrive through a revision.
    assert "file" not in _dk_field_names(ProcurementDocument)


# =================================================================================================
# ProcurementDocument - life-cycle questions
# =================================================================================================

def test_dk_document_is_expiring_inside_the_window_and_not_past_it(dk_document_expiring_a):
    assert dk_document_expiring_a.is_expiring is True
    assert dk_document_expiring_a.is_expired is False


def test_dk_document_is_expired_once_the_date_is_behind_us(dk_document_expired_a):
    assert dk_document_expired_a.is_expired is True
    assert dk_document_expired_a.is_expiring is False


@pytest.mark.parametrize("offset,expiring,expired", [
    (-1, False, True),                      # yesterday - expired, and no longer "expiring"
    (0, True, False),                       # today - the last day it is still in force
    (EXPIRY_WARN_DAYS, True, False),        # the far edge of the window is inside it
    (EXPIRY_WARN_DAYS + 1, False, False),   # one day further out is neither
])
def test_dk_document_expiry_window_edges(offset, expiring, expired, tenant_a):
    document = _dk_document(tenant_a, expires_on=_dk_days(offset))
    assert (document.is_expiring, document.is_expired) == (expiring, expired)


def test_dk_document_without_dates_is_never_expiring_or_due(dk_document_draft_a):
    assert dk_document_draft_a.is_expiring is False
    assert dk_document_draft_a.is_expired is False
    assert dk_document_draft_a.is_review_due is False
    assert dk_document_draft_a.is_over_retention is False


@pytest.mark.parametrize("offset,expected", [(-1, True), (0, True), (1, False)])
def test_dk_document_is_review_due_includes_the_day_itself(offset, expected, tenant_a):
    assert _dk_document(tenant_a, review_on=_dk_days(offset)).is_review_due is expected


@pytest.mark.parametrize("offset,expected", [(-1, True), (0, False), (1, False)])
def test_dk_document_is_over_retention_is_strictly_past(offset, expected, tenant_a):
    """Retention runs THROUGH its date - the flag lights the day after, and nothing deletes."""
    assert _dk_document(tenant_a, retention_until=_dk_days(offset)).is_over_retention is expected


def test_dk_document_is_checked_out_reads_the_column_not_the_user_row(
        dk_document_locked_a, django_assert_max_num_queries):
    with django_assert_max_num_queries(0):
        assert dk_document_locked_a.is_checked_out is True


def test_dk_document_is_checked_out_is_false_when_nobody_holds_it(dk_document_active_a):
    assert dk_document_active_a.is_checked_out is False


def test_dk_document_tag_list_splits_the_normalised_string(dk_document_active_a):
    assert dk_document_active_a.tag_list == ["sow", "facilities"]
    assert ProcurementDocument(tags="").tag_list == []
    assert ProcurementDocument().tag_list == []


# =================================================================================================
# normalize_tags + ProcurementDocument.clean()
# =================================================================================================

def test_dk_normalize_tags_lowercases_strips_and_dedupes_in_first_seen_order():
    assert normalize_tags("Warranty, HVAC ,warranty") == "warranty, hvac"
    assert normalize_tags("  Facilities , SOW ,, facilities ") == "facilities, sow"


@pytest.mark.parametrize("raw", ["", None, "   ", ",,,", " , , "])
def test_dk_normalize_tags_of_nothing_is_empty(raw):
    assert normalize_tags(raw) == ""


def test_dk_document_clean_normalises_tags_in_place(tenant_a):
    """``objects.create()`` skips ``clean()`` - the normalisation is asserted through the model."""
    document = ProcurementDocument(tenant=tenant_a, title="Tagged",
                                   tags="Warranty, HVAC ,warranty")
    document.full_clean()
    assert document.tags == "warranty, hvac"
    document.save()
    document.refresh_from_db()
    assert document.tag_list == ["warranty", "hvac"]


def test_dk_document_clean_rejects_an_expiry_before_the_effective_date(tenant_a):
    document = ProcurementDocument(tenant=tenant_a, title="Backwards dates",
                                   effective_date=_dk_days(0), expires_on=_dk_days(-1))
    with pytest.raises(ValidationError) as exc:
        document.full_clean()
    assert exc.value.message_dict["expires_on"] == [
        "The expiry date cannot be before the effective date."]


def test_dk_document_clean_accepts_an_expiry_on_the_effective_date(tenant_a):
    """A one-day cover note is a real document, not a mis-keyed one."""
    document = ProcurementDocument(tenant=tenant_a, title="Same-day cover",
                                   effective_date=_dk_days(0), expires_on=_dk_days(0))
    document.full_clean()


def test_dk_document_clean_ignores_unset_foreign_keys(tenant_a):
    """``_id`` is tested first - an unset FK must not raise RelatedObjectDoesNotExist."""
    ProcurementDocument(tenant=tenant_a, title="No links at all").full_clean()


def test_dk_document_clean_rejects_a_cross_tenant_supplier(tenant_a, dk_supplier_b):
    document = ProcurementDocument(tenant=tenant_a, title="Crafted supplier",
                                   supplier=dk_supplier_b)
    with pytest.raises(ValidationError) as exc:
        document.full_clean()
    assert exc.value.message_dict["supplier"] == ["That record belongs to another workspace."]


def test_dk_document_clean_rejects_a_cross_tenant_purchase_order(tenant_a, fulfillment_po_b):
    document = ProcurementDocument(tenant=tenant_a, title="Crafted order",
                                   purchase_order=fulfillment_po_b)
    with pytest.raises(ValidationError) as exc:
        document.full_clean()
    assert exc.value.message_dict["purchase_order"] == [
        "That record belongs to another workspace."]


def test_dk_document_clean_rejects_a_cross_tenant_sourcing_event(tenant_a, tenant_b):
    document = ProcurementDocument(tenant=tenant_a, title="Crafted event",
                                   sourcing_event=_dk_sourcing_event(tenant_b))
    with pytest.raises(ValidationError) as exc:
        document.full_clean()
    assert exc.value.message_dict["sourcing_event"] == [
        "That record belongs to another workspace."]


def test_dk_document_clean_rejects_a_cross_tenant_contract(tenant_a, tenant_b, dk_supplier_b):
    document = ProcurementDocument(
        tenant=tenant_a, title="Crafted contract",
        contract=_dk_supplier_contract(tenant_b, dk_supplier_b))
    with pytest.raises(ValidationError) as exc:
        document.full_clean()
    assert exc.value.message_dict["contract"] == ["That record belongs to another workspace."]


def test_dk_document_clean_accepts_this_workspaces_own_spine_links(tenant_a, dk_supplier_a):
    document = ProcurementDocument(tenant=tenant_a, title="Local links",
                                   supplier=dk_supplier_a,
                                   sourcing_event=_dk_sourcing_event(tenant_a, "Acme tender"),
                                   contract=_dk_supplier_contract(tenant_a, dk_supplier_a,
                                                                  "Acme master"))
    document.full_clean()


# =================================================================================================
# ProcurementDocument.current_revision - THE invariant of the sub-module (I1)
# =================================================================================================

def test_dk_current_revision_is_none_until_a_revision_is_approved(tenant_a, admin_user,
                                                                  dk_media_root):
    """Uploading never moves the pointer: a new revision sits BEHIND the current one."""
    document = _dk_document(tenant_a, title="Pending only")
    revision = _dk_revision(document, body=b"First draft of the specification.",
                            filename="r1.txt", uploaded_by=admin_user)
    document.refresh_from_db()
    assert document.current_revision_no == 0
    assert document.current_revision is None
    assert revision.is_approved is False
    assert revision.is_current is False


def test_dk_current_revision_resolves_the_pointer_to_the_approved_row(dk_document_chain_a,
                                                                      dk_revision_approved_a):
    assert dk_document_chain_a.current_revision_no == 1
    assert dk_document_chain_a.current_revision == dk_revision_approved_a
    assert dk_revision_approved_a.is_approved is True
    assert dk_revision_approved_a.is_current is True


def test_dk_current_revision_ignores_an_unapproved_pointer(dk_document_chain_a,
                                                           dk_revision_pending_a):
    """I1 - an unapproved revision can never be the document of record.

    The pointer is forced onto the still-pending r2, which is the state a deleted-and-re-uploaded
    revision or an admin reparent leaves behind. ``current_revision`` must answer ``None`` - "no
    approved revision yet" - rather than present a file nobody approved.

    ``r2.is_current`` stays ``True`` in exactly this state and that is DELIBERATE: it is
    number-equality only, it drives ``{% if not r.is_current %}`` on the delete button (the
    conservative direction), and all three templates guard the green Current badge with
    ``is_current AND is_approved``. Both halves are pinned here so neither can be "tidied".
    """
    ProcurementDocument.objects.filter(pk=dk_document_chain_a.pk).update(current_revision_no=2)
    document = ProcurementDocument.objects.get(pk=dk_document_chain_a.pk)
    pending = ProcurementDocumentRevision.objects.get(pk=dk_revision_pending_a.pk)

    assert document.current_revision_no == 2
    assert pending.is_approved is False
    assert document.current_revision is None
    assert pending.is_current is True


def test_dk_current_revision_costs_no_query_while_the_pointer_is_zero(
        dk_document_draft_a, django_assert_max_num_queries):
    """0 means "nothing approved yet" and is answered from the column already in hand."""
    with django_assert_max_num_queries(0):
        assert dk_document_draft_a.current_revision is None


def test_dk_a_reused_revision_number_never_makes_an_unapproved_row_current(tenant_a, admin_user,
                                                                          dk_media_root):
    """The end-to-end shape of I1, built the way it really happens.

    r2 is approved and pointed at, then deleted; the next upload re-allocates the number 2 because
    ``next_revision_no`` is ``MAX + 1``. The new r2 is PENDING, so the surviving pointer now names
    an unapproved row - and the document must still say "no approved revision".
    """
    document = _dk_document(tenant_a, title="Pointer outlives its revision")
    _dk_approve(_dk_revision(document, body=b"First issue.", filename="r1.txt",
                             uploaded_by=admin_user), admin_user)
    second = _dk_revision(document, body=b"Second issue.", filename="r2.txt",
                          uploaded_by=admin_user)
    _dk_approve(second, admin_user)
    document.refresh_from_db()
    assert document.current_revision_no == 2

    second.delete()
    document.refresh_from_db()
    assert document.current_revision_no == 2                 # the pointer is untouched
    assert next_revision_no(document) == 2                   # ... and the number is free again

    replacement = _dk_revision(document, body=b"Third issue, not approved.", filename="r3.txt",
                               uploaded_by=admin_user)
    assert (replacement.revision_no, replacement.is_approved) == (2, False)
    assert replacement.is_current is True                    # number equality alone says yes
    assert document.current_revision is None                 # ... the document says no (I1)


def test_dk_document_delete_takes_its_revision_chain_with_it(dk_document_chain_a):
    """CASCADE - a document's versions have no meaning without the document."""
    assert dk_document_chain_a.revisions.count() == 2
    document_pk = dk_document_chain_a.pk
    dk_document_chain_a.delete()
    assert not ProcurementDocumentRevision.objects.filter(document_id=document_pk).exists()


# =================================================================================================
# ProcurementDocumentRevision - allocation, uniqueness, __str__, Meta
# =================================================================================================

def test_dk_next_revision_no_starts_at_one(dk_document_draft_a):
    assert next_revision_no(dk_document_draft_a) == 1


def test_dk_next_revision_no_is_one_past_the_highest(dk_document_chain_a):
    assert next_revision_no(dk_document_chain_a) == 3


def test_dk_revision_number_is_unique_per_document(dk_document_chain_a, tenant_a):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            ProcurementDocumentRevision.objects.create(
                tenant=tenant_a, document=dk_document_chain_a, revision_no=1,
                change_note="A second r1")
    assert ProcurementDocumentRevision._meta.unique_together == (
        ("tenant", "document", "revision_no"),)


def test_dk_revision_number_one_exists_on_every_document(tenant_a, dk_document_chain_a):
    """The constraint is per DOCUMENT - every document has its own r1."""
    other = _dk_document(tenant_a, title="A second document")
    revision = ProcurementDocumentRevision.objects.create(
        tenant=tenant_a, document=other, revision_no=1, change_note="Its own first issue")
    assert revision.pk is not None
    assert ProcurementDocumentRevision.objects.filter(tenant=tenant_a, revision_no=1).count() == 2


def test_dk_revision_str_reads_the_parents_number(dk_document_chain_a, dk_revision_pending_a):
    assert str(dk_revision_pending_a) == f"{dk_document_chain_a.number} r2"


def test_dk_revision_str_without_a_parent_never_raises():
    """An upload form rendering its own errors has no parent attached yet."""
    assert str(ProcurementDocumentRevision(revision_no=3)) == "PDOC r3"


def test_dk_revision_meta_ordering_is_the_newest_version_first(dk_document_chain_a):
    assert ProcurementDocumentRevision._meta.ordering == ["-revision_no", "-id"]
    assert [r.revision_no for r in dk_document_chain_a.revisions.all()] == [2, 1]


def test_dk_revision_meta_has_a_single_index():
    """M20 - (tenant, document) was dropped: unique_together already carries that prefix."""
    assert _dk_index_names(ProcurementDocumentRevision) == {"prc_pdrev_tnt_appr_idx"}
    assert _dk_index_fields(ProcurementDocumentRevision) == {("tenant", "is_approved")}


def test_dk_revision_has_no_uploaded_at_column(dk_revision_approved_a):
    """``created_at`` IS the upload moment - the row is created by the upload and nothing else."""
    assert "uploaded_at" not in _dk_field_names(ProcurementDocumentRevision)
    assert dk_revision_approved_a.created_at is not None


def test_dk_revision_has_no_number_of_its_own():
    """A child row identified by its parent plus ``revision_no`` - there is no PDREV- sequence."""
    assert "number" not in _dk_field_names(ProcurementDocumentRevision)
    assert not hasattr(ProcurementDocumentRevision, "NUMBER_PREFIX")


def test_dk_revision_defaults_are_the_documented_ones(tenant_a, dk_document_draft_a):
    revision = ProcurementDocumentRevision.objects.create(tenant=tenant_a,
                                                          document=dk_document_draft_a)
    revision.refresh_from_db()
    assert revision.revision_no == 1
    assert revision.is_approved is False
    assert (revision.approved_by_id, revision.approved_at) == (None, None)
    assert (revision.uploaded_by_id, revision.change_note) == (None, "")
    assert (revision.original_filename, revision.file_size, revision.sha256) == ("", 0, "")
    assert (revision.extracted_text, revision.extraction_note) == ("", "")


def test_dk_revision_change_note_is_the_only_user_typed_column():
    """Immutability is STRUCTURAL: no ModelForm can surface a machine-written column (L20/L22).

    ``document`` and ``file`` stay editable because they are create-path only - the upload form's
    ``Meta.fields`` is ``("file", "change_note")`` and the parent arrives as a URL pk - and
    ``id``/``tenant`` are the base-class plumbing every model in this app carries.
    """
    editable = {f.name for f in ProcurementDocumentRevision._meta.concrete_fields if f.editable}
    assert editable == {"id", "tenant", "document", "file", "change_note"}
    assert {"revision_no", "original_filename", "file_size", "sha256", "is_approved",
            "approved_by", "approved_at", "uploaded_by", "extracted_text", "extraction_note",
            "created_at", "updated_at"} <= _dk_not_editable(ProcurementDocumentRevision)


def test_dk_revision_admin_never_renders_a_parent_document_input():
    """I2 - re-parenting a revision through the admin was a two-click, deterministic route into
    I1 (and, with the app-wide editable ``tenant``, out of the workspace entirely)."""
    from django.contrib import admin as django_admin
    model_admin = django_admin.site._registry[ProcurementDocumentRevision]
    assert "document" in model_admin.readonly_fields


@pytest.mark.parametrize("pointer,expected", [(0, False), (1, False), (2, True)])
def test_dk_revision_is_current_is_number_equality_only(pointer, expected, dk_document_chain_a,
                                                        dk_revision_pending_a):
    """Deliberate, and documented: it asks "is this the numbered version" and nothing else."""
    dk_document_chain_a.current_revision_no = pointer
    assert dk_revision_pending_a.is_current is expected


def test_dk_revision_is_current_is_false_without_a_parent():
    assert ProcurementDocumentRevision(revision_no=1).is_current is False


def test_dk_revision_clean_rejects_a_cross_tenant_parent(tenant_a, dk_document_b):
    revision = ProcurementDocumentRevision(tenant=tenant_a, document=dk_document_b,
                                           change_note="Crafted parent")
    with pytest.raises(ValidationError) as exc:
        revision.clean()
    assert exc.value.message_dict["document"] == ["That record belongs to another workspace."]


def test_dk_revision_clean_asks_the_database_who_owns_the_parent(tenant_a, dk_document_b):
    """The lookup is a VALUES query on ``document_id``, not ``self.document.tenant_id``: a crafted
    POST supplies the object, so the object's own answer is not evidence."""
    dk_document_b.tenant_id = tenant_a.pk          # the in-memory object now lies
    revision = ProcurementDocumentRevision(tenant=tenant_a, document=dk_document_b,
                                           change_note="Crafted parent")
    with pytest.raises(ValidationError) as exc:
        revision.clean()
    assert "document" in exc.value.message_dict


def test_dk_revision_clean_accepts_a_parent_in_the_same_workspace(tenant_a, dk_document_draft_a):
    ProcurementDocumentRevision(tenant=tenant_a, document=dk_document_draft_a,
                                change_note="Its own first issue").clean()


def test_dk_revision_clean_ignores_an_unset_parent(tenant_a):
    ProcurementDocumentRevision(tenant=tenant_a).clean()


# =================================================================================================
# file_sha256 - streamed, and the two seeks are load-bearing
# =================================================================================================

def test_dk_file_sha256_matches_the_payload_and_leaves_the_pointer_at_the_start():
    """Without the seek AFTERWARDS Django would go on to store a zero-byte file."""
    payload = b"Boiler maintenance contract, first issue."
    upload = ContentFile(payload, name="r1.txt")
    digest = file_sha256(upload)
    assert digest == hashlib.sha256(payload).hexdigest()
    assert len(digest) == 64
    assert upload.read() == payload


def test_dk_file_sha256_seeks_before_reading_a_partly_consumed_upload():
    """Without the seek BEFORE, a caller who peeked at the upload would checksum only the tail."""
    payload = b"0123456789abcdefghij"
    upload = ContentFile(payload, name="r1.txt")
    upload.read(5)
    assert file_sha256(upload) == hashlib.sha256(payload).hexdigest()


def test_dk_file_sha256_of_nothing_is_an_empty_string():
    assert file_sha256(None) == ""


def test_dk_revision_stores_its_bytes_and_a_64_character_digest(tenant_a, admin_user,
                                                                dk_media_root):
    """The checksum is measured from the payload and the payload still reaches the disk."""
    payload = b"Grounds maintenance statement of work, revision 1. Quarterly cut."
    document = _dk_document(tenant_a, title="Bytes survive the checksum")
    revision = _dk_revision(document, body=payload, filename="sow-r1.txt",
                            uploaded_by=admin_user)

    assert len(revision.sha256) == 64
    assert revision.sha256 == hashlib.sha256(payload).hexdigest()
    assert revision.file_size == len(payload)
    assert revision.original_filename == "sow-r1.txt"

    stored = ProcurementDocumentRevision.objects.get(pk=revision.pk)
    stored.file.open("rb")
    try:
        assert stored.file.read() == payload
    finally:
        stored.file.close()
    # ... and it landed in the throwaway MEDIA_ROOT, never the real media/ tree.
    assert stored.file.path.startswith(dk_media_root)


# =================================================================================================
# extract_document_text - never raises, always bounded (I9)
# =================================================================================================

def test_dk_extract_bounds_are_the_documented_ones():
    assert EXTRACT_MAX_CHARS == 200_000
    assert MAX_EXTRACT_PAGES == 500
    assert PLAIN_TEXT_EXTENSIONS == {".txt", ".csv"}


def test_dk_extraction_notes_are_four_distinct_sentences_that_fit_their_column():
    """The note is STORED on the row, so a sentence longer than the column is a write error at
    upload time - and four outcomes need four distinct wordings to be worth reading."""
    notes = [_dk_revisions_mod.NOTE_NO_EXTRACTOR, _dk_revisions_mod.NOTE_UNREADABLE_PATH,
             _dk_revisions_mod.NOTE_BAD_FILE, _dk_revisions_mod.NOTE_NO_TEXT_LAYER]
    limit = _dk_field(ProcurementDocumentRevision, "extraction_note").max_length
    assert len(set(notes)) == 4
    assert all(0 < len(note) <= limit for note in notes)


def test_dk_extract_document_text_reads_a_plain_text_upload(dk_revision_approved_a):
    text, note = extract_document_text(dk_revision_approved_a)
    assert note == ""
    assert "soleplate" in text
    # The fixture stamped exactly this pair at ingest - the row and a fresh read agree.
    assert dk_revision_approved_a.extraction_note == ""
    assert dk_revision_approved_a.extracted_text == text


def test_dk_extract_document_text_reads_a_csv(tenant_a, dk_media_root):
    revision = _dk_revision(_dk_document(tenant_a, title="Price file"),
                            body=b"sku,description,price\nBRG-40,Bearing housing,25.00\n",
                            filename="prices.csv")
    text, note = extract_document_text(revision)
    assert note == ""
    assert "BRG-40" in text


def test_dk_extract_document_text_keeps_a_latin_1_file_searchable(tenant_a, dk_media_root):
    """errors="replace" - one undecodable byte is not a reason to lose the other 200,000."""
    revision = _dk_revision(_dk_document(tenant_a, title="Legacy export"),
                            body="reference,Café supplies".encode("latin-1"),
                            filename="legacy.csv")
    text, note = extract_document_text(revision)
    assert note == ""
    assert "reference" in text and "supplies" in text


def test_dk_extract_document_text_reports_a_file_with_no_text(tenant_a, dk_media_root):
    revision = _dk_revision(_dk_document(tenant_a, title="Blank upload"),
                            body=b"   \n  \t \n", filename="blank.txt")
    assert extract_document_text(revision) == ("", NOTE_NO_TEXT_LAYER)


def test_dk_extract_document_text_truncates_at_the_character_cap(tenant_a, dk_media_root):
    revision = _dk_revision(_dk_document(tenant_a, title="A dictionary of a specification"),
                            body=b"a" * (EXTRACT_MAX_CHARS + 5_000), filename="huge.txt")
    text, note = extract_document_text(revision)
    assert note == ""
    assert len(text) == EXTRACT_MAX_CHARS
    assert len(revision.extracted_text) == EXTRACT_MAX_CHARS


def test_dk_extract_document_text_returns_a_note_for_a_row_with_no_file(dk_revision_no_file_a):
    assert extract_document_text(dk_revision_no_file_a) == ("", NOTE_UNREADABLE_PATH)


def test_dk_extract_document_text_returns_a_note_for_no_revision_at_all():
    assert extract_document_text(None) == ("", NOTE_UNREADABLE_PATH)


def test_dk_extract_document_text_survives_a_storage_backend_with_no_local_path():
    """``FieldFile.path`` RAISES on object storage - the day MEDIA_ROOT moves to S3, an upload
    must degrade to "could not be read back", not to a 500 inside the upload request."""

    class _DkPathlessFile:
        name = "procurement/documents/2026/09/remote.txt"

        def __bool__(self):
            return True

        @property
        def path(self):
            raise NotImplementedError("This backend doesn't support absolute paths.")

    class _DkPathlessRevision:
        file = _DkPathlessFile()

    assert extract_document_text(_DkPathlessRevision()) == ("", NOTE_UNREADABLE_PATH)


def test_dk_extract_document_text_never_raises_when_the_stored_file_is_gone(tenant_a,
                                                                           dk_media_root):
    """The row can outlive its bytes; the re-index Run must get a sentence, not a traceback."""
    revision = _dk_revision(_dk_document(tenant_a, title="Bytes went missing"),
                            body=b"Text that will not survive.", filename="gone.txt")
    os.remove(revision.file.path)
    assert extract_document_text(revision) == ("", NOTE_BAD_FILE)


@pytest.mark.parametrize("filename,body", [
    ("scan.png", b"\x89PNG\r\n\x1a\n scanned page"),
    ("pack.zip", b"PK\x03\x04 archive"),
    ("terms.docx", b"PK\x03\x04 word binary"),
])
def test_dk_extract_document_text_is_honest_about_a_file_it_cannot_read(filename, body, tenant_a,
                                                                       dk_media_root):
    """Accepted, stored, linked and downloadable - simply not readable as text by this server."""
    revision = _dk_revision(_dk_document(tenant_a, title="Unreadable format"), body=body,
                            filename=filename)
    assert extract_document_text(revision) == ("", NOTE_NO_TEXT_LAYER)


def test_dk_extract_document_text_reports_a_missing_pdf_extractor(monkeypatch, tenant_a,
                                                                  dk_media_root):
    """A server without pdfplumber still runs every other page in this sub-module."""
    revision = _dk_revision(_dk_document(tenant_a, title="A PDF"), body=b"%PDF-1.4 stub",
                            filename="spec.pdf")
    # ``None`` in sys.modules makes ``import pdfplumber`` raise ImportError, which is exactly the
    # condition the lazy import inside the function is written for.
    monkeypatch.setitem(sys.modules, "pdfplumber", None)
    assert extract_document_text(revision) == ("", NOTE_NO_EXTRACTOR)


def test_dk_extract_document_text_reports_a_malformed_pdf(monkeypatch, tenant_a, dk_media_root):
    revision = _dk_revision(_dk_document(tenant_a, title="A broken PDF"),
                            body=b"%PDF-1.4 truncated", filename="broken.pdf")

    def _dk_explode(path):
        raise ValueError("malformed / encrypted / truncated")

    module = types.ModuleType("pdfplumber")
    module.open = _dk_explode
    monkeypatch.setitem(sys.modules, "pdfplumber", module)
    assert extract_document_text(revision) == ("", NOTE_BAD_FILE)


def test_dk_extract_document_text_never_raises_when_a_page_explodes(monkeypatch, tenant_a,
                                                                    dk_media_root):
    revision = _dk_revision(_dk_document(tenant_a, title="A PDF with a bad page"),
                            body=b"%PDF-1.4 stub", filename="badpage.pdf")

    class _DkAngryPage:
        def extract_text(self):
            raise RuntimeError("pdfminer gave up")

        def flush_cache(self):
            pass

    module = types.ModuleType("pdfplumber")
    module.open = lambda path: _DkStubPdf([_DkAngryPage()])
    monkeypatch.setitem(sys.modules, "pdfplumber", module)
    assert extract_document_text(revision) == ("", NOTE_BAD_FILE)


def test_dk_extract_document_text_stops_at_max_extract_pages(monkeypatch, tenant_a,
                                                             dk_media_root):
    """I9 - bounded, not merely non-raising: the worker has already spent the CPU by then."""
    revision = _dk_revision(_dk_document(tenant_a, title="A very long PDF"),
                            body=b"%PDF-1.4 stub", filename="long.pdf")
    counter = _dk_stub_pdfplumber(monkeypatch, MAX_EXTRACT_PAGES + 120, "page text")
    text, note = extract_document_text(revision)
    assert counter["parsed"] == MAX_EXTRACT_PAGES
    assert counter["flushed"] == MAX_EXTRACT_PAGES      # each page's parse cache is freed
    assert note == ""
    assert text.count("page text") == MAX_EXTRACT_PAGES


def test_dk_extract_document_text_stops_when_the_character_budget_is_met(monkeypatch, tenant_a,
                                                                        dk_media_root):
    """I9 - four fat pages meet the 200,000-character budget, so page five is never parsed."""
    revision = _dk_revision(_dk_document(tenant_a, title="A fat PDF"), body=b"%PDF-1.4 stub",
                            filename="fat.pdf")
    counter = _dk_stub_pdfplumber(monkeypatch, MAX_EXTRACT_PAGES, "x" * 60_000)
    text, note = extract_document_text(revision)
    assert counter["parsed"] == 4
    assert len(text) == EXTRACT_MAX_CHARS
    assert note == ""


def test_dk_extract_document_text_reports_a_pdf_with_no_text_layer(monkeypatch, tenant_a,
                                                                   dk_media_root):
    """A scanned image has no text to read, and the row says so instead of looking like a bug."""
    revision = _dk_revision(_dk_document(tenant_a, title="A scanned PDF"),
                            body=b"%PDF-1.4 stub", filename="scanned.pdf")
    _dk_stub_pdfplumber(monkeypatch, 3, "   ")
    assert extract_document_text(revision) == ("", NOTE_NO_TEXT_LAYER)


# =================================================================================================
# ProcurementPolicy - numbering, __str__, vocabulary, Meta
# =================================================================================================

def test_dk_policy_number_is_allocated_with_the_ppol_prefix(tenant_a):
    assert _dk_policy(tenant_a).number == "PPOL-00001"
    assert ProcurementPolicy.NUMBER_PREFIX == "PPOL"


def test_dk_policy_numbers_advance_and_restart_per_workspace(tenant_a, tenant_b):
    _dk_policy(tenant_a)
    assert _dk_policy(tenant_a, version_number="2.0").number == "PPOL-00002"
    assert _dk_policy(tenant_b).number == "PPOL-00001"


def test_dk_policy_number_survives_a_re_save(tenant_a):
    policy = _dk_policy(tenant_a)
    policy.summary = "Reworded after review."
    policy.save()
    policy.refresh_from_db()
    assert policy.number == "PPOL-00001"


def test_dk_policy_str_reads_the_title_and_version_not_the_number(dk_policy_published_a):
    """The one ``__str__`` in this sub-module that is NOT number-first - a rule is known by name."""
    assert str(dk_policy_published_a) == "Competitive Bidding Threshold v2.0"
    assert dk_policy_published_a.number not in str(dk_policy_published_a)


def test_dk_policy_review_column_is_next_review_on(dk_policy_review_due_a):
    """The field-name trap: a document and a knowledge resource carry ``review_on``; a policy
    carries ``next_review_on`` (6.17's attestation ledger already reads that name)."""
    assert _dk_field(ProcurementPolicy, "next_review_on") is not None
    with pytest.raises(FieldDoesNotExist):
        _dk_field(ProcurementPolicy, "review_on")
    assert dk_policy_review_due_a.next_review_on == _dk_days(-1)


def test_dk_policy_choice_vocabulary_is_the_documented_one():
    assert _dk_values(ProcurementPolicy.POLICY_TYPE_CHOICES) == [
        "purchasing_rule", "approval_limit", "competitive_bidding", "sole_source",
        "supplier_code_of_conduct", "ethics_conflict", "sustainability", "data_security", "other"]
    assert _dk_values(ProcurementPolicy.STATUS_CHOICES) == ["draft", "published", "archived"]
    assert _dk_values(ProcurementPolicy.THRESHOLD_BASIS_CHOICES) == [
        "per_line", "per_requisition", "per_purchase_order", "per_contract_year",
        "annual_supplier_spend"]
    assert ProcurementPolicy.ADVISORY_NOTE is _dk_policies_mod.ADVISORY_NOTE


@pytest.mark.parametrize("policy_type", _dk_values(ProcurementPolicy.POLICY_TYPE_CHOICES))
def test_dk_policy_every_policy_type_value_round_trips(policy_type, tenant_a):
    policy = ProcurementPolicy(tenant=tenant_a, title=f"Rule {policy_type}",
                               policy_type=policy_type)
    policy.full_clean()
    policy.save()
    policy.refresh_from_db()
    assert policy.policy_type == policy_type
    assert policy.get_policy_type_display()


@pytest.mark.parametrize("status", _dk_values(ProcurementPolicy.STATUS_CHOICES))
def test_dk_policy_every_status_value_round_trips(status, tenant_a):
    policy = ProcurementPolicy(tenant=tenant_a, title=f"Rule {status}", status=status)
    policy.full_clean()
    assert policy.get_status_display() == dict(ProcurementPolicy.STATUS_CHOICES)[status]


@pytest.mark.parametrize("basis", _dk_values(ProcurementPolicy.THRESHOLD_BASIS_CHOICES))
def test_dk_policy_every_threshold_basis_value_round_trips(basis, tenant_a):
    policy = ProcurementPolicy(tenant=tenant_a, title=f"Rule {basis}",
                               threshold_amount=Decimal("1000.00"), threshold_basis=basis)
    policy.full_clean()
    assert policy.get_threshold_basis_display()


def test_dk_policy_status_css_is_colour_named_and_total(dk_policy_published_a,
                                                        dk_policy_draft_a,
                                                        dk_policy_v1_archived_a):
    assert set(ProcurementPolicy.STATUS_CSS) == set(_dk_values(ProcurementPolicy.STATUS_CHOICES))
    assert set(ProcurementPolicy.STATUS_CSS.values()) <= _DK_BADGE_COLOURS
    assert dk_policy_published_a.status_css == "badge-green"
    assert dk_policy_draft_a.status_css == "badge-muted"
    assert dk_policy_v1_archived_a.status_css == "badge-slate"
    assert ProcurementPolicy(status="mislaid").status_css == "badge-slate"


def test_dk_policy_defaults_are_the_documented_ones(tenant_a):
    policy = ProcurementPolicy.objects.create(tenant=tenant_a, title="Bare rule")
    policy.refresh_from_db()
    assert policy.policy_type == "purchasing_rule"
    assert policy.version_number == "1.0"
    assert policy.status == "draft"
    assert policy.published_at is None
    assert policy.threshold_amount is None
    assert policy.threshold_basis == ""
    assert policy.threshold_currency_id is None
    assert policy.requires_acknowledgment is False
    assert (policy.summary, policy.body) == ("", "")
    assert policy.previous_version_id is None


def test_dk_policy_system_columns_are_never_form_fields():
    """L20/L22 - the number and the publish stamp are written by the verb, never typed."""
    assert {"number", "published_at", "created_by", "created_at", "updated_at"} <= \
        _dk_not_editable(ProcurementPolicy)


def test_dk_policy_meta_constraints_and_indexes():
    assert ProcurementPolicy._meta.ordering == ["-created_at", "-id"]
    assert ProcurementPolicy._meta.unique_together == (
        ("tenant", "number"), ("tenant", "title", "version_number"))
    assert _dk_index_names(ProcurementPolicy) == {
        "prc_ppol_tnt_status_idx", "prc_ppol_tnt_type_idx", "prc_ppol_tnt_review_idx"}
    assert ("tenant", "next_review_on") in _dk_index_fields(ProcurementPolicy)


def test_dk_policy_one_version_of_a_title_per_workspace(tenant_a):
    """v1.0 and v2.0 of a rule are two rows; a SECOND v2.0 is a mistake the database refuses."""
    _dk_policy(tenant_a, version_number="2.0")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _dk_policy(tenant_a, version_number="2.0")


def test_dk_policy_the_same_title_and_version_may_exist_in_another_workspace(tenant_a, tenant_b):
    _dk_policy(tenant_a, version_number="2.0")
    assert _dk_policy(tenant_b, version_number="2.0").pk is not None


# =================================================================================================
# ProcurementPolicy - the supersession chain
# =================================================================================================

def test_dk_policy_supersession_chain_walks_one_hop_each_way(dk_policy_v1_archived_a,
                                                             dk_policy_published_a,
                                                             dk_policy_draft_a):
    """Every read surface takes exactly ONE hop, which is why a cycle can never hang a page."""
    assert dk_policy_published_a.previous_version == dk_policy_v1_archived_a
    assert list(dk_policy_v1_archived_a.superseded_by.all()) == [dk_policy_published_a]
    assert list(dk_policy_published_a.superseded_by.all()) == [dk_policy_draft_a]
    assert list(dk_policy_draft_a.superseded_by.all()) == []


def test_dk_policy_deleting_a_predecessor_leaves_the_successor_in_force(dk_policy_v1_archived_a,
                                                                       dk_policy_published_a):
    """SET_NULL, not CASCADE: deleting v1.0 must not take the rule that is actually in force."""
    dk_policy_v1_archived_a.delete()
    dk_policy_published_a.refresh_from_db()
    assert dk_policy_published_a.pk is not None
    assert dk_policy_published_a.previous_version_id is None
    assert dk_policy_published_a.status == "published"


def test_dk_policy_attestations_cascade_which_is_why_delete_is_guarded(dk_attestation_a,
                                                                      dk_policy_published_a):
    """The model half of I7: the 6.17 sign-off records would vanish with the policy, so the
    delete verb refuses while any exists rather than relying on a person noticing."""
    from apps.procurement.models import PolicyAttestation
    assert dk_policy_published_a.attestations.count() == 1
    attestation_pk = dk_attestation_a.pk
    dk_policy_published_a.delete()
    assert not PolicyAttestation.objects.filter(pk=attestation_pk).exists()


def test_dk_supersession_conflict_allows_a_clean_predecessor(dk_policy_published_a,
                                                             dk_policy_v1_archived_a):
    assert supersession_conflict(dk_policy_published_a, dk_policy_v1_archived_a) is None


def test_dk_supersession_conflict_allows_no_candidate(dk_policy_published_a):
    assert supersession_conflict(dk_policy_published_a, None) is None


def test_dk_supersession_conflict_allows_an_unsaved_first_version(dk_policy_published_a,
                                                                  tenant_a):
    """A create form has no pk yet - it cannot be anywhere in a chain."""
    draft = ProcurementPolicy(tenant=tenant_a, title="Competitive Bidding Threshold",
                              version_number="3.0")
    assert supersession_conflict(draft, dk_policy_published_a) is None


def test_dk_supersession_conflict_refuses_self_supersession(dk_policy_published_a):
    problem = supersession_conflict(dk_policy_published_a, dk_policy_published_a)
    assert problem is not None
    assert "cannot supersede itself" in problem


def test_dk_supersession_conflict_refuses_a_two_hop_loop(dk_policy_v1_archived_a,
                                                         dk_policy_published_a):
    """v2 already points back at v1; pointing v1 at v2 would close A -> B -> A."""
    problem = supersession_conflict(dk_policy_v1_archived_a, dk_policy_published_a)
    assert problem is not None
    assert "would make the version chain loop" in problem


def test_dk_supersession_conflict_refuses_a_chain_that_already_loops(tenant_a):
    """A cycle written through the shell or the admin must not be walked - or joined."""
    first = _dk_policy(tenant_a, title="Looped rule", version_number="1.0")
    second = _dk_policy(tenant_a, title="Looped rule", version_number="2.0",
                        previous_version=first)
    ProcurementPolicy.objects.filter(pk=first.pk).update(previous_version=second)
    first.refresh_from_db()

    outsider = _dk_policy(tenant_a, title="Looped rule", version_number="3.0")
    problem = supersession_conflict(outsider, first)
    assert problem is not None
    assert "already loops" in problem


def test_dk_supersession_conflict_refuses_a_chain_deeper_than_the_cap(
        tenant_a, django_assert_max_num_queries):
    """A guard that gives up and says "probably fine" is not a guard - and the walk is bounded."""
    assert MAX_CHAIN_DEPTH == 50
    node = _dk_policy(tenant_a, title="Deep rule", version_number="1.0")
    for index in range(2, MAX_CHAIN_DEPTH + 3):
        node = _dk_policy(tenant_a, title="Deep rule", version_number=f"{index}.0",
                          previous_version=node)
    newcomer = _dk_policy(tenant_a, title="Deep rule", version_number="99.0")

    with django_assert_max_num_queries(MAX_CHAIN_DEPTH + 1):
        problem = supersession_conflict(newcomer, node)
    assert problem is not None
    assert f"longer than {MAX_CHAIN_DEPTH} versions" in problem


def test_dk_policy_clean_refuses_a_policy_that_supersedes_itself(dk_policy_published_a):
    dk_policy_published_a.previous_version = dk_policy_published_a
    with pytest.raises(ValidationError) as exc:
        dk_policy_published_a.full_clean()
    assert "cannot supersede itself" in exc.value.message_dict["previous_version"][0]


def test_dk_policy_clean_refuses_a_predecessor_that_would_close_a_loop(dk_policy_v1_archived_a,
                                                                      dk_policy_published_a):
    dk_policy_v1_archived_a.previous_version = dk_policy_published_a
    with pytest.raises(ValidationError) as exc:
        dk_policy_v1_archived_a.full_clean()
    assert "loop" in exc.value.message_dict["previous_version"][0]


# =================================================================================================
# ProcurementPolicy - thresholds are documentation, never a control
# =================================================================================================

#: A comparison or an ORM band lookup against a threshold column. Its ABSENCE from every 6.19
#: module is the invariant: an advisory number that some code quietly enforces is the worst kind
#: of control - the sort people believe in.
_DK_THRESHOLD_GATE = re.compile(
    r"threshold_(?:amount|basis)\s*(?:[<>]=?|==)"
    r"|(?:[<>]=?)\s*[\w.\"']*threshold_(?:amount|basis)"
    r"|threshold_amount__(?:gt|gte|lt|lte|range|in)\b")


def _dk_submodule_sources():
    """Every 6.19 module across the models / views / forms layers."""
    models_dir = os.path.dirname(_dk_policies_mod.__file__)
    app_dir = os.path.dirname(os.path.dirname(models_dir))
    paths = []
    for layer in ("models", "views", "forms"):
        folder = os.path.join(app_dir, layer, "DocumentKnowledgeManagement")
        paths.extend(os.path.join(folder, name) for name in sorted(os.listdir(folder))
                     if name.endswith(".py"))
    return paths


def test_dk_policy_thresholds_are_inert_documentation():
    """Nothing in 6.19 gates, blocks, routes or approves on a threshold.

    The enforceable equivalent already exists and is the only correct home for it: 6.3's
    ``ApprovalRoutingRule`` bands, which ``RequisitionApproval`` enforces under a row lock.
    """
    sources = _dk_submodule_sources()
    assert len(sources) >= 8            # the four entity modules across three layers, at least
    offenders = []
    for path in sources:
        with open(path, encoding="utf-8") as handle:
            for number, line in enumerate(handle, start=1):
                if _DK_THRESHOLD_GATE.search(line):
                    offenders.append(f"{os.path.basename(path)}:{number}")
    assert offenders == []


def test_dk_policy_exposes_no_api_that_decides_anything_from_a_threshold():
    forbidden = ("enforce", "is_over_threshold", "requires_quotes", "check_threshold",
                 "gate_", "authorize")
    assert [name for name in dir(ProcurementPolicy) if name.startswith(forbidden)] == []


def test_dk_policy_threshold_label_reads_currency_amount_and_basis(dk_policy_published_a):
    assert dk_policy_published_a.threshold_label == "USD 25,000.00 per purchase order"


def test_dk_policy_threshold_label_is_empty_without_a_figure(tenant_a):
    assert _dk_policy(tenant_a).threshold_label == ""


def test_dk_policy_threshold_label_drops_the_parts_it_does_not_have():
    bare = ProcurementPolicy(title="No currency", threshold_amount=Decimal("1500"),
                             threshold_basis="per_line")
    assert bare.threshold_label == "1,500.00 per line"
    unlabelled = ProcurementPolicy(title="No basis", threshold_amount=Decimal("1500"))
    assert unlabelled.threshold_label == "1,500.00"


def test_dk_policy_threshold_label_costs_no_query_without_a_currency(
        tenant_a, django_assert_max_num_queries):
    """It reads ``threshold_currency_id`` before the object - the register prints this per row."""
    policy = _dk_policy(tenant_a, threshold_amount=Decimal("1500.00"), threshold_basis="per_line")
    with django_assert_max_num_queries(0):
        assert policy.threshold_label == "1,500.00 per line"


@pytest.mark.parametrize("offset,expected", [(-1, True), (0, True), (1, False)])
def test_dk_policy_is_review_due_includes_the_day_itself(offset, expected, tenant_a):
    policy = _dk_policy(tenant_a, next_review_on=_dk_days(offset))
    assert policy.is_review_due is expected


def test_dk_policy_without_a_review_date_is_never_due(dk_policy_v1_archived_a):
    assert dk_policy_v1_archived_a.next_review_on is None
    assert dk_policy_v1_archived_a.is_review_due is False


# =================================================================================================
# ProcurementPolicy - clean()
# =================================================================================================

def test_dk_policy_clean_wants_a_basis_with_an_amount(tenant_a):
    """"25,000 of what?" - an amount with no basis is an unreadable rule."""
    policy = ProcurementPolicy(tenant=tenant_a, title="Amount only",
                               threshold_amount=Decimal("25000.00"))
    with pytest.raises(ValidationError) as exc:
        policy.full_clean()
    assert "threshold_basis" in exc.value.message_dict
    assert "measured against" in exc.value.message_dict["threshold_basis"][0]


def test_dk_policy_clean_wants_an_amount_with_a_basis(tenant_a):
    policy = ProcurementPolicy(tenant=tenant_a, title="Basis only",
                               threshold_basis="per_purchase_order")
    with pytest.raises(ValidationError) as exc:
        policy.full_clean()
    assert "threshold_amount" in exc.value.message_dict
    assert "basis on its own states nothing" in exc.value.message_dict["threshold_amount"][0]


def test_dk_policy_clean_accepts_neither_column(tenant_a):
    ProcurementPolicy(tenant=tenant_a, title="No figure at all").full_clean()


def test_dk_policy_clean_leaves_the_currency_optional(tenant_a):
    """The currency is a label on the number, not a third half of the pair."""
    ProcurementPolicy(tenant=tenant_a, title="Unlabelled figure",
                      threshold_amount=Decimal("25000.00"),
                      threshold_basis="per_line").full_clean()


def test_dk_policy_clean_never_calls_the_global_currency_foreign(tenant_a, usd):
    """``accounting.Currency`` has no tenant column - comparing one would reject every currency."""
    from apps.accounting.models import Currency
    assert "tenant" not in {field.name for field in Currency._meta.fields}
    ProcurementPolicy(tenant=tenant_a, title="Priced rule", threshold_amount=Decimal("25000.00"),
                      threshold_basis="per_purchase_order", threshold_currency=usd).full_clean()


def test_dk_policy_rejects_a_negative_threshold(tenant_a):
    policy = ProcurementPolicy(tenant=tenant_a, title="Negative figure",
                               threshold_amount=Decimal("-1.00"), threshold_basis="per_line")
    with pytest.raises(ValidationError) as exc:
        policy.full_clean()
    assert "threshold_amount" in exc.value.message_dict


def test_dk_policy_rejects_a_threshold_wider_than_its_column(tenant_a):
    """DecimalField(14, 2) - an over-wide figure must be a friendly error, never a driver error."""
    policy = ProcurementPolicy(tenant=tenant_a, title="Absurd figure",
                               threshold_amount=Decimal("99999999999999.99"),
                               threshold_basis="per_line")
    with pytest.raises(ValidationError) as exc:
        policy.full_clean()
    assert "threshold_amount" in exc.value.message_dict


@pytest.mark.parametrize("field", ["applies_to", "document", "previous_version"])
def test_dk_policy_clean_rejects_a_cross_tenant_link(field, tenant_a, org_unit_b, dk_document_b,
                                                     dk_policy_b):
    foreign = {"applies_to": org_unit_b, "document": dk_document_b,
               "previous_version": dk_policy_b}[field]
    policy = ProcurementPolicy(tenant=tenant_a, title="Crafted link", **{field: foreign})
    with pytest.raises(ValidationError) as exc:
        policy.full_clean()
    assert exc.value.message_dict[field] == ["That record belongs to another workspace."]


def test_dk_policy_clean_does_not_walk_another_workspaces_chain(tenant_a, dk_policy_b):
    """The loop guard is skipped once the FK is already flagged foreign - one bug, one message."""
    policy = ProcurementPolicy(tenant=tenant_a, title="Crafted predecessor",
                               previous_version=dk_policy_b)
    with pytest.raises(ValidationError) as exc:
        policy.full_clean()
    assert exc.value.message_dict["previous_version"] == [
        "That record belongs to another workspace."]


def test_dk_policy_clean_ignores_unset_foreign_keys(tenant_a):
    ProcurementPolicy(tenant=tenant_a, title="No links at all").full_clean()


# =================================================================================================
# KnowledgeResource
# =================================================================================================

def test_dk_resource_number_is_allocated_with_the_pkr_prefix(tenant_a):
    assert _dk_resource(tenant_a).number == "PKR-00001"
    assert KnowledgeResource.NUMBER_PREFIX == "PKR"


def test_dk_resource_numbers_advance_and_restart_per_workspace(tenant_a, tenant_b):
    _dk_resource(tenant_a)
    assert _dk_resource(tenant_a, title="Second guide").number == "PKR-00002"
    assert _dk_resource(tenant_b).number == "PKR-00001"


def test_dk_resource_str_reads_the_number_then_the_title(dk_resource_featured_a):
    assert str(dk_resource_featured_a) == (f"{dk_resource_featured_a.number} {_DK_DOT} "
                                           f"RFP template - IT services")


def test_dk_resource_str_on_an_unsaved_instance_never_starts_with_the_dot():
    assert str(KnowledgeResource(title="Half-built")) == f"PKR {_DK_DOT} Half-built"


def test_dk_resource_choice_vocabulary_is_the_documented_one():
    assert _dk_values(KnowledgeResource.RESOURCE_TYPE_CHOICES) == [
        "rfp_template", "rfq_template", "evaluation_scorecard", "negotiation_playbook",
        "checklist", "guide", "sample_document", "training"]
    assert _dk_values(KnowledgeResource.CATEGORY_CHOICES) == [
        "general", "it_software", "facilities", "logistics", "professional_services",
        "raw_materials", "capex", "marketing", "other"]
    assert _dk_values(KnowledgeResource.AUDIENCE_CHOICES) == [
        "all", "requester", "buyer", "approver", "legal"]
    assert _dk_values(KnowledgeResource.STATUS_CHOICES) == ["draft", "published", "archived"]
    assert KnowledgeResource.FEATURED_CAP == FEATURED_CAP == 6
    assert KnowledgeResource.LIBRARY_NOTE is _dk_resources_mod.LIBRARY_NOTE


@pytest.mark.parametrize("resource_type", _dk_values(KnowledgeResource.RESOURCE_TYPE_CHOICES))
def test_dk_resource_every_resource_type_value_round_trips(resource_type, tenant_a):
    resource = KnowledgeResource(tenant=tenant_a, title=f"Guide {resource_type}",
                                 resource_type=resource_type)
    resource.full_clean()
    resource.save()
    resource.refresh_from_db()
    assert resource.resource_type == resource_type
    assert resource.get_resource_type_display()


@pytest.mark.parametrize("category", _dk_values(KnowledgeResource.CATEGORY_CHOICES))
def test_dk_resource_every_category_value_round_trips(category, tenant_a):
    resource = KnowledgeResource(tenant=tenant_a, title=f"Guide {category}", category=category)
    resource.full_clean()
    assert resource.get_category_display()


@pytest.mark.parametrize("audience", _dk_values(KnowledgeResource.AUDIENCE_CHOICES))
def test_dk_resource_every_audience_value_round_trips(audience, tenant_a):
    """A reading hint, never an access control - every value simply has to store and render."""
    resource = KnowledgeResource(tenant=tenant_a, title=f"Guide {audience}", audience=audience)
    resource.full_clean()
    assert resource.get_audience_display()


def test_dk_resource_status_css_is_colour_named_and_total(dk_resource_published_a,
                                                          dk_resource_draft_a,
                                                          dk_resource_archived_a):
    assert set(KnowledgeResource.STATUS_CSS) == set(_dk_values(KnowledgeResource.STATUS_CHOICES))
    assert set(KnowledgeResource.STATUS_CSS.values()) <= _DK_BADGE_COLOURS
    assert dk_resource_published_a.status_css == "badge-green"
    assert dk_resource_draft_a.status_css == "badge-muted"
    assert dk_resource_archived_a.status_css == "badge-slate"
    assert KnowledgeResource(status="mislaid").status_css == "badge-slate"


def test_dk_resource_defaults_are_the_documented_ones(tenant_a):
    resource = KnowledgeResource.objects.create(tenant=tenant_a, title="Bare guide")
    resource.refresh_from_db()
    assert resource.resource_type == "guide"
    assert resource.category == "general"
    assert resource.audience == "all"
    assert resource.status == "draft"
    assert resource.is_featured is False
    assert resource.usage_count == 0
    assert resource.last_used_at is None
    assert resource.review_on is None
    assert (resource.summary, resource.body, resource.tags) == ("", "", "")


def test_dk_resource_usage_columns_are_machine_written():
    """L20/L22 - the counter moves only through the verb's atomic F() + 1, never through a form."""
    assert {"usage_count", "last_used_at", "number", "created_by", "created_at", "updated_at"} <= \
        _dk_not_editable(KnowledgeResource)


def test_dk_resource_has_no_has_been_used_attribute():
    """M16 - the property was deleted; the register reads ``usage_count`` directly."""
    assert not hasattr(KnowledgeResource, "has_been_used")


def test_dk_resource_has_no_file_column_of_its_own(dk_resource_featured_a, dk_document_active_a):
    """One artifact, one place: the workbook is a ProcurementDocument, so it gets the revision
    chain, the approval step, the checksum and the text read instead of a second unversioned copy."""
    assert "file" not in _dk_field_names(KnowledgeResource)
    assert dk_resource_featured_a.document == dk_document_active_a


def test_dk_resource_document_link_survives_the_documents_deletion(dk_resource_featured_a,
                                                                   dk_document_active_a):
    """SET_NULL - losing the attachment must not destroy the guidance written around it."""
    dk_document_active_a.delete()
    dk_resource_featured_a.refresh_from_db()
    assert dk_resource_featured_a.pk is not None
    assert dk_resource_featured_a.document_id is None


def test_dk_resource_meta_constraints_and_indexes():
    assert KnowledgeResource._meta.unique_together == (("tenant", "number"),)
    assert _dk_index_names(KnowledgeResource) == {
        "prc_pkr_tnt_status_idx", "prc_pkr_tnt_type_idx", "prc_pkr_tnt_feat_idx"}


def test_dk_resource_ordering_puts_the_featured_shelf_first(tenant_a):
    """``-is_featured`` outranks recency: the starred row leads even when it is the older one."""
    assert KnowledgeResource._meta.ordering == ["-is_featured", "-created_at", "-id"]
    featured = _dk_resource(tenant_a, title="Featured", is_featured=True, status="published")
    plain = _dk_resource(tenant_a, title="Plain", status="published")
    _dk_pin_created_at(KnowledgeResource, [featured.pk, plain.pk], timezone.now())
    assert [row.pk for row in KnowledgeResource.objects.filter(tenant=tenant_a)] == [
        featured.pk, plain.pk]


def test_dk_resource_ordering_is_deterministic_when_created_at_ties(tenant_a):
    """The id tiebreak is a PAGING invariant: without it, an unstable sort under a Paginator
    repeats one row on page 2 and drops another entirely."""
    rows = [_dk_resource(tenant_a, title=f"Tied row {index}", status="published")
            for index in range(1, 8)]
    _dk_pin_created_at(KnowledgeResource, [row.pk for row in rows], timezone.now())

    register = KnowledgeResource.objects.filter(tenant=tenant_a)
    expected = sorted((row.pk for row in rows), reverse=True)
    assert [row.pk for row in register] == expected
    assert [row.pk for row in KnowledgeResource.objects.filter(tenant=tenant_a)] == expected

    paginator = Paginator(register, 3)
    paged = [obj.pk for number in paginator.page_range for obj in paginator.page(number)]
    assert paged == expected
    assert len(set(paged)) == len(paged)          # nothing repeated, nothing dropped


@pytest.mark.parametrize("offset,expected", [(-1, True), (0, True), (1, False)])
def test_dk_resource_is_review_due_includes_the_day_itself(offset, expected, tenant_a):
    assert _dk_resource(tenant_a, review_on=_dk_days(offset)).is_review_due is expected


def test_dk_resource_without_a_review_date_is_never_due(dk_resource_published_a,
                                                        dk_resource_review_due_a):
    assert dk_resource_published_a.review_on is None
    assert dk_resource_published_a.is_review_due is False
    assert dk_resource_review_due_a.is_review_due is True


def test_dk_resource_tag_list_matches_the_documents(dk_resource_featured_a):
    """One tag typed on a document and on a guide is ONE tag - the same normalizer, both sides."""
    assert dk_resource_featured_a.tag_list == ["rfp", "it"]
    assert KnowledgeResource(tags="").tag_list == []


def test_dk_resource_clean_normalises_tags_through_the_shared_normalizer(tenant_a):
    resource = KnowledgeResource(tenant=tenant_a, title="Tagged guide",
                                 tags="RFP, Services ,rfp")
    resource.full_clean()
    assert resource.tags == normalize_tags("RFP, Services ,rfp") == "rfp, services"


def test_dk_resource_clean_rejects_a_cross_tenant_document(tenant_a, dk_document_b):
    """Otherwise the detail page's download link would reach another workspace's file."""
    resource = KnowledgeResource(tenant=tenant_a, title="Crafted link", document=dk_document_b)
    with pytest.raises(ValidationError) as exc:
        resource.full_clean()
    assert exc.value.message_dict["document"] == ["That record belongs to another workspace."]


def test_dk_resource_clean_accepts_a_document_in_the_same_workspace(tenant_a,
                                                                    dk_document_active_a):
    KnowledgeResource(tenant=tenant_a, title="Local link",
                      document=dk_document_active_a).full_clean()


def test_dk_resource_clean_ignores_an_unset_document(tenant_a):
    KnowledgeResource(tenant=tenant_a, title="No attachment").full_clean()


# =================================================================================================
# The reminder engine - expiring_documents
# =================================================================================================

def test_dk_expiring_documents_is_empty_without_a_tenant(dk_document_expiring_a):
    """The superuser has no tenant; the scan must answer nothing rather than scan everything."""
    assert expiring_documents(None) == []


def test_dk_expiring_documents_selects_the_in_window_rows(tenant_a, dk_document_expiring_a,
                                                          dk_document_expired_a,
                                                          dk_document_review_due_a,
                                                          dk_document_active_a):
    rows = {row["document"].pk: row for row in expiring_documents(tenant_a)}
    # dk_document_active_a's review date is 180 days out - outside the window, so it is absent.
    assert set(rows) == {dk_document_expiring_a.pk, dk_document_expired_a.pk,
                         dk_document_review_due_a.pk}
    assert (rows[dk_document_expiring_a.pk]["reason"],
            rows[dk_document_expiring_a.pk]["days_left"]) == ("expires", 7)
    assert (rows[dk_document_expired_a.pk]["reason"],
            rows[dk_document_expired_a.pk]["days_left"]) == ("expires", -3)
    assert (rows[dk_document_review_due_a.pk]["reason"],
            rows[dk_document_review_due_a.pk]["days_left"]) == ("review", -1)


def test_dk_expiring_documents_ignores_dates_beyond_the_window(tenant_a):
    _dk_document(tenant_a, title="Far off", status="active",
                 expires_on=_dk_days(REMINDER_WINDOW_DAYS + 1))
    edge = _dk_document(tenant_a, title="On the edge", status="active",
                        expires_on=_dk_days(REMINDER_WINDOW_DAYS))
    assert [row["document"].pk for row in expiring_documents(tenant_a)] == [edge.pk]


def test_dk_expiring_documents_scans_only_live_documents(tenant_a):
    """A superseded or archived record has already been dealt with; nagging about it is noise."""
    for status in ("superseded", "archived"):
        _dk_document(tenant_a, title=f"{status} row", status=status, expires_on=_dk_days(3))
    live = [_dk_document(tenant_a, title="draft row", status="draft", expires_on=_dk_days(3)),
            _dk_document(tenant_a, title="active row", status="active", expires_on=_dk_days(3))]
    assert {row["document"].pk for row in expiring_documents(tenant_a)} == {
        row.pk for row in live}


def test_dk_expiring_documents_prefers_expiry_over_review_on_one_row(tenant_a):
    """One alert per document is the contract the dedupe depends on - expiry is the louder fact."""
    document = _dk_document(tenant_a, title="Both dates", status="active",
                            expires_on=_dk_days(10), review_on=_dk_days(2))
    rows = expiring_documents(tenant_a)
    assert len(rows) == 1
    assert rows[0]["document"].pk == document.pk
    assert (rows[0]["reason"], rows[0]["days_left"]) == ("expires", 10)


def test_dk_expiring_documents_orders_dated_rows_soonest_first(tenant_a):
    later = _dk_document(tenant_a, title="Three weeks out", status="active",
                         expires_on=_dk_days(20))
    sooner = _dk_document(tenant_a, title="Two days out", status="active",
                          expires_on=_dk_days(2))
    assert [row["document"].pk for row in expiring_documents(tenant_a)] == [sooner.pk, later.pk]


def test_dk_expiring_documents_accepts_an_injected_today(tenant_a):
    """``on=`` is what makes the window testable without waiting or freezing the clock (L16)."""
    document = _dk_document(tenant_a, title="Forty days out", status="active",
                            expires_on=_dk_days(40))
    assert expiring_documents(tenant_a) == []
    rows = expiring_documents(tenant_a, on=_dk_days(20))
    assert [(row["document"].pk, row["days_left"]) for row in rows] == [(document.pk, 20)]


def test_dk_expiring_documents_never_crosses_a_workspace(tenant_a, tenant_b,
                                                         dk_document_expiring_a):
    _dk_document(tenant_b, title="Globex expiring", status="active", expires_on=_dk_days(5))
    assert [row["document"].pk for row in expiring_documents(tenant_a)] == [
        dk_document_expiring_a.pk]


# =================================================================================================
# The reminder engine - run_document_reminders
# =================================================================================================

def test_dk_run_document_reminders_raises_one_alert_per_in_window_document(
        tenant_a, admin_user, dk_document_expiring_a, dk_document_expired_a,
        dk_document_review_due_a):
    """There is no scheduler here: the 6.1 alert inbox IS the notification channel."""
    assert run_document_reminders(tenant_a, admin_user) == {"raised": 3, "skipped_open": 0}

    alerts = ProcurementAlert.objects.filter(tenant=tenant_a, kind="deadline")
    assert alerts.count() == 3
    assert {alert.link_url for alert in alerts} == {
        f"/procurement/documents/{document.pk}/"
        for document in (dk_document_expiring_a, dk_document_expired_a, dk_document_review_due_a)}
    assert {alert.status for alert in alerts} == {"open"}
    assert all(alert.due_at is None for alert in alerts)


def test_dk_run_document_reminders_is_idempotent_on_a_second_press(
        tenant_a, admin_user, dk_document_expiring_a, dk_document_expired_a,
        dk_document_review_due_a):
    """The button advertises that it is safe to press twice - and it raises nothing on the way."""
    assert run_document_reminders(tenant_a, admin_user) == {"raised": 3, "skipped_open": 0}
    assert run_document_reminders(tenant_a, admin_user) == {"raised": 0, "skipped_open": 3}
    assert ProcurementAlert.objects.filter(tenant=tenant_a, kind="deadline").count() == 3


def test_dk_run_document_reminders_second_press_costs_two_queries(
        tenant_a, admin_user, dk_document_expiring_a, dk_document_expired_a,
        dk_document_review_due_a, django_assert_max_num_queries):
    """I13 - the open-alert set is read ONCE before the loop and no row lock is taken where no row
    will be written. The all-skipped path used to cost four queries per in-window document."""
    run_document_reminders(tenant_a, admin_user)
    with django_assert_max_num_queries(2):
        assert run_document_reminders(tenant_a, admin_user) == {"raised": 0, "skipped_open": 3}


def test_dk_run_document_reminders_severity_is_critical_inside_a_week(tenant_a, admin_user):
    soon = _dk_document(tenant_a, title="Inside a week", status="active",
                        expires_on=_dk_days(7))
    later = _dk_document(tenant_a, title="Three weeks out", status="active",
                         expires_on=_dk_days(21))
    run_document_reminders(tenant_a, admin_user)
    by_link = {alert.link_url: alert
               for alert in ProcurementAlert.objects.filter(tenant=tenant_a, kind="deadline")}
    assert by_link[f"/procurement/documents/{soon.pk}/"].severity == "critical"
    assert by_link[f"/procurement/documents/{later.pk}/"].severity == "warning"


def test_dk_run_document_reminders_writes_an_alert_a_person_can_act_on(tenant_a, admin_user,
                                                                       dk_document_expiring_a):
    run_document_reminders(tenant_a, admin_user)
    alert = ProcurementAlert.objects.get(tenant=tenant_a, kind="deadline")
    assert dk_document_expiring_a.number in alert.title
    assert f"{_dk_days(7):%d %b %Y}" in alert.title
    assert "expires in 7 day(s)" in alert.message
    # A single-slash same-site path: ProcurementAlert.clean() rejects anything that could become
    # an open redirect, and this engine's links must pass it.
    alert.full_clean()


def test_dk_run_document_reminders_says_how_long_ago_a_date_passed(tenant_a, admin_user,
                                                                    dk_document_expired_a):
    run_document_reminders(tenant_a, admin_user)
    alert = ProcurementAlert.objects.get(tenant=tenant_a, kind="deadline")
    assert "3 day(s) ago" in alert.message
    assert alert.severity == "critical"


def test_dk_run_document_reminders_names_a_review_as_a_review(tenant_a, admin_user,
                                                               dk_document_review_due_a):
    run_document_reminders(tenant_a, admin_user)
    alert = ProcurementAlert.objects.get(tenant=tenant_a, kind="deadline")
    assert "is due for review" in alert.title
    assert "is due for review 1 day(s) ago" in alert.message


def test_dk_run_document_reminders_skips_an_acknowledged_alert_but_not_a_resolved_one(
        tenant_a, admin_user, dk_document_expiring_a):
    """Dedupe is against OPEN_STATUSES - closing one out lets the next Run raise a fresh one."""
    assert ProcurementAlert.OPEN_STATUSES == ("open", "acknowledged")
    run_document_reminders(tenant_a, admin_user)
    alert = ProcurementAlert.objects.get(tenant=tenant_a, kind="deadline")

    alert.status = "acknowledged"
    alert.acknowledged_at = timezone.now()
    alert.save(update_fields=["status", "acknowledged_at"])
    assert run_document_reminders(tenant_a, admin_user) == {"raised": 0, "skipped_open": 1}

    alert.status = "resolved"
    alert.resolved_at = timezone.now()
    alert.save(update_fields=["status", "resolved_at"])
    assert run_document_reminders(tenant_a, admin_user) == {"raised": 1, "skipped_open": 0}
    assert ProcurementAlert.objects.filter(tenant=tenant_a, kind="deadline").count() == 2


def test_dk_run_document_reminders_is_quiet_when_nothing_is_in_the_window(tenant_a, admin_user,
                                                                          dk_document_draft_a):
    assert run_document_reminders(tenant_a, admin_user) == {"raised": 0, "skipped_open": 0}
    assert not ProcurementAlert.objects.filter(tenant=tenant_a).exists()


def test_dk_run_document_reminders_returns_zero_without_a_tenant(admin_user,
                                                                  dk_document_expiring_a):
    assert run_document_reminders(None, admin_user) == {"raised": 0, "skipped_open": 0}
    assert not ProcurementAlert.objects.exists()


def test_dk_run_document_reminders_never_crosses_a_workspace(tenant_a, tenant_b, admin_user,
                                                              dk_document_expiring_a):
    _dk_document(tenant_b, title="Globex expiring", status="active", expires_on=_dk_days(5))
    assert run_document_reminders(tenant_a, admin_user) == {"raised": 1, "skipped_open": 0}
    assert not ProcurementAlert.objects.filter(tenant=tenant_b).exists()
    assert ProcurementAlert.objects.get(tenant=tenant_a).link_url == (
        f"/procurement/documents/{dk_document_expiring_a.pk}/")


def test_dk_run_document_reminders_audited_writes_one_audit_row(tenant_a, admin_user,
                                                                 dk_document_expiring_a):
    from apps.core.models import AuditLog
    assert run_document_reminders_audited(tenant_a, admin_user) == {"raised": 1,
                                                                    "skipped_open": 0}
    row = AuditLog.objects.get(action="document_reminders_run")
    assert row.changes == {"raised": 1, "skipped_open": 0}
    assert row.user_id == admin_user.pk
    assert row.tenant_id == tenant_a.pk
    assert ProcurementAlert.objects.filter(tenant=tenant_a, kind="deadline").count() == 1
