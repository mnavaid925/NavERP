"""Procurement 6.19 - Document & Knowledge Management FORM tests.

The four forms of this sub-module are its write boundary, and this lane owns three things the
other three lanes cannot see:

* **What is NOT a field.** Every column the SYSTEM owns - ``tenant``, the ``PDOC-``/``PPOL-``/
  ``PKR-`` ``number``, the workflow ``status``, ``published_at``, ``current_revision_no``,
  ``revision_no``, ``is_approved``/``approved_by``/``approved_at``, ``sha256``/``file_size``/
  ``original_filename``, ``extracted_text``/``extraction_note``, ``usage_count``/``last_used_at``,
  ``created_by`` and the base timestamps - is absent from all four ``Meta.fields`` lists. Absence
  is asserted twice, because a field list is only half the control: the lane also BINDS a payload
  carrying every one of those names and proves the saved row came back with the system defaults,
  not the smuggled values (L20/L22). A ``status`` a POST can set is a workflow a POST can skip.
* **The upload gate.** ``ProcurementDocumentRevisionUploadForm.clean_file`` is the only way bytes
  enter 6.19. The extension allow-list is checked on the LAST segment (``a.txt.php`` is a
  ``.php``), and the size cap is the **20 MB** one from ``apps.core.forms._common`` - never the
  rival 2 MB ``MAX_UPLOAD_BYTES`` that ``forms/CatalogManagement/UploadBatches.py`` defines for a
  CSV import. That name collision is why the import is function-local, so this lane exercises a
  payload BETWEEN the two limits: under the real cap, over the rival one. A regression that
  swapped the constants would pass every other test in the repository.
* **Tenant scoping of all eight FK dropdowns** - ``supplier``, ``contract``, ``purchase_order``,
  ``sourcing_event``, ``owner``, ``document``, ``applies_to``, ``previous_version`` - on both
  layers: the narrowed ``<select>`` (UX) and ``_reject_foreign`` / the model's own ``clean()``
  (the boundary that actually holds when a crafted POST never goes near the widget). A form built
  with ``tenant=None`` offers ``.none()`` everywhere rather than leaking the whole table.

Plus the policy library's numeric and cycle guards (``NaN`` / ``Infinity`` / ``1e400`` / 17 digits
/ negative / three decimal places each land their OWN sentence, never a 500), the paired
amount-and-basis rule, and over-length or malformed input on every ``CharField`` and ``DateField``
- which matter more here than they look: the development database is not in strict SQL mode, so a
missing form-level ``max_length`` would silently TRUNCATE rather than raise. The form layer is the
only real control.

Determinism (L16): every date basis is ``timezone.localdate()``, never ``datetime.date.today()``.
Every stored byte lands under ``dk_media_root`` (pytest's ``tmp_path``); nothing touches the
network.
"""
import datetime
from decimal import Decimal

import pytest
from django import forms
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from apps.accounting.models import Currency
from apps.core.forms._common import ALLOWED_DOC_EXTENSIONS, MAX_UPLOAD_BYTES
from apps.core.models import Party
from apps.procurement.forms import (
    KnowledgeResourceForm,
    ProcurementDocumentForm,
    ProcurementDocumentRevisionUploadForm,
    ProcurementPolicyForm,
)
from apps.procurement.forms.CatalogManagement.UploadBatches import (
    MAX_UPLOAD_BYTES as _DK_RIVAL_UPLOAD_CAP)
from apps.procurement.forms.DocumentKnowledgeManagement import Revisions as _dk_upload_form_mod
from apps.procurement.models import (
    KnowledgeResource,
    ProcurementDocument,
    ProcurementDocumentRevision,
    ProcurementPolicy,
    SourcingEvent,
)
from apps.procurement.models.DocumentKnowledgeManagement.Policies import MAX_CHAIN_DEPTH
from apps.procurement.tests.conftest import _dk_policy
from apps.scm.models import SupplierContract

pytestmark = pytest.mark.django_db


# =================================================================================================
# Module-level helpers - all _dk_* / _DK_* so the next sub-module appending near this file cannot
# shadow them and so a failure names its own lane (L47). Record factories come from conftest,
# which OWNS them; only what conftest does not provide is built here.
# =================================================================================================

#: Every column the four models keep for themselves. Not one of these may appear in ANY
#: ``Meta.fields`` list: a secret, a workflow state or a derived counter that a POST can set is a
#: control the form quietly removed (L20/L22).
#:
#: ``document`` is deliberately NOT in here, because it is not one name with one meaning: on the
#: policy and the knowledge resource it is the user's own choice of controlled artifact, and on
#: the REVISION it is the parent supplied from the URL and must never be a field. That one is
#: asserted per-form, below.
_DK_SYSTEM_COLUMNS = {
    "tenant", "number", "status",
    "created_by", "created_at", "updated_at",
    # ProcurementDocument
    "current_revision_no", "checked_out_by", "checked_out_at", "extracted_text",
    # ProcurementDocumentRevision
    "revision_no", "original_filename", "file_size", "sha256",
    "is_approved", "approved_by", "approved_at", "uploaded_by", "extraction_note",
    # ProcurementPolicy
    "published_at",
    # KnowledgeResource
    "usage_count", "last_used_at",
}

#: ``ProcurementDocumentForm`` links to the file only through a revision, and neither the policy
#: nor the knowledge resource has an upload path of its own - the artifact is a
#: ``ProcurementDocument`` chosen through the ``document`` FK, so it inherits the allow-list, the
#: cap, the checksum and the approval step. A second ``file`` field anywhere would skip all four.
_DK_FILE_FIELD = "file"


def _dk_today():
    """The SAME date basis the models use (L16) - never ``datetime.date.today()``."""
    return timezone.localdate()


def _dk_days(delta):
    return _dk_today() + datetime.timedelta(days=delta)


def _dk_iso(delta=0):
    """A date string in the ONE input format ``TenantModelForm`` leaves on a DateField."""
    return _dk_days(delta).isoformat()


def _dk_document_payload(**overrides):
    """The minimum valid ``ProcurementDocumentForm`` POST, plus whatever the caller changes."""
    payload = {"title": "Chiller service agreement", "doc_type": "sow",
               "classification": "internal"}
    payload.update(overrides)
    return payload


def _dk_policy_payload(**overrides):
    """The minimum valid ``ProcurementPolicyForm`` POST."""
    payload = {"title": "Sole Source Justification Rule", "policy_type": "sole_source",
               "version_number": "1.0"}
    payload.update(overrides)
    return payload


def _dk_resource_payload(**overrides):
    """The minimum valid ``KnowledgeResourceForm`` POST."""
    payload = {"title": "Negotiation playbook - freight", "resource_type": "negotiation_playbook",
               "category": "logistics", "audience": "buyer"}
    payload.update(overrides)
    return payload


def _dk_upload(name="renewal.txt", body=b"Renewed cover through 2027."):
    """One in-memory upload whose declared size is its real byte count."""
    return SimpleUploadedFile(name=name, content=body)


class _DkSizedUpload(SimpleUploadedFile):
    """A tiny payload that DECLARES a huge size - crosses a cap without allocating the bytes.

    ``clean_file`` reads ``upload.size``, which is exactly the attribute a browser-supplied
    ``Content-Length`` populates, so declaring it is the honest way to exercise the limit.
    """

    def __init__(self, name, declared_size, content=b"declared"):
        super().__init__(name=name, content=content)
        self._declared_size = declared_size

    @property
    def size(self):
        return self._declared_size

    @size.setter
    def size(self, value):
        pass  # UploadedFile.__init__ writes the real byte count; the declaration wins here


def _dk_upload_form(files=None, data=None, tenant=None, document=None, **kwargs):
    """Build the upload form the way ``pdocument_revision_upload`` does.

    The parent comes from the URL after the view's own tenant-scoped fetch and is stamped on the
    instance - it is deliberately NOT a POST field, which is the whole point of the shape.
    """
    form = ProcurementDocumentRevisionUploadForm(data if data is not None else {},
                                                 files or {}, tenant=tenant, **kwargs)
    if document is not None:
        form.instance.document = document
    return form


def _dk_sourcing_event(tenant, title="Globex-only tender"):
    """A ``SourcingEvent`` in ``tenant`` - conftest has no tenant-B one, and the document form
    scopes this FK too."""
    return SourcingEvent.objects.create(tenant=tenant, title=title, event_type="tender",
                                        status="draft")


def _dk_supplier_contract(tenant, party, title="Master services agreement"):
    """An ``scm.SupplierContract`` in ``tenant`` - the fourth spine FK the document form scopes."""
    return SupplierContract.objects.create(tenant=tenant, party=party, title=title)


def _dk_widen(form, *names):
    """Drop the tenant narrowing off named ``ModelChoiceField``s, in place.

    A narrowed ``<select>`` refuses a foreign pk as "Select a valid choice", which is a real
    control but not the one being measured: it proves the WIDGET was scoped. Widening the
    queryset first is how a crafted POST that never went near the widget is simulated, so what
    answers is the second layer - ``_reject_foreign`` in ``clean()`` and the model's own
    ``clean()`` backstop behind it.
    """
    for name in names:
        field = form.fields[name]
        field.queryset = field.queryset.model._default_manager.all()
    return form


def _dk_pks(form, name):
    return set(form.fields[name].queryset.values_list("pk", flat=True))


def _dk_messages(form, name):
    return " ".join(form.errors.get(name, []))


# =================================================================================================
# 1. Meta.fields - the exact lists, the instantiated fields, and what is required
# =================================================================================================

def test_dk_document_form_meta_fields_are_the_fifteen_in_the_contract():
    assert ProcurementDocumentForm.Meta.fields == [
        "title", "doc_type", "description", "tags", "classification", "owner",
        "supplier_visible", "effective_date", "expires_on", "review_on", "retention_until",
        "supplier", "contract", "purchase_order", "sourcing_event"]
    assert ProcurementDocumentForm.Meta.model is ProcurementDocument


def test_dk_upload_form_meta_fields_are_the_file_and_one_note():
    assert ProcurementDocumentRevisionUploadForm.Meta.fields == ["file", "change_note"]
    assert ProcurementDocumentRevisionUploadForm.Meta.model is ProcurementDocumentRevision


def test_dk_policy_form_meta_fields_are_the_fifteen_in_the_contract():
    assert ProcurementPolicyForm.Meta.fields == [
        "title", "policy_type", "summary", "body", "version_number", "previous_version",
        "applies_to", "owner", "document", "effective_from", "next_review_on",
        "threshold_amount", "threshold_basis", "threshold_currency", "requires_acknowledgment"]
    assert ProcurementPolicyForm.Meta.model is ProcurementPolicy


def test_dk_resource_form_meta_fields_are_the_eleven_in_the_contract():
    assert KnowledgeResourceForm.Meta.fields == [
        "title", "resource_type", "category", "audience", "summary", "body", "tags",
        "is_featured", "owner", "document", "review_on"]
    assert KnowledgeResourceForm.Meta.model is KnowledgeResource


def test_dk_every_form_instantiates_exactly_its_meta_fields(tenant_a):
    for form_class in (ProcurementDocumentForm, ProcurementDocumentRevisionUploadForm,
                       ProcurementPolicyForm, KnowledgeResourceForm):
        form = form_class(tenant=tenant_a)
        assert set(form.fields) == set(form_class.Meta.fields), form_class.__name__


def test_dk_every_form_instantiates_exactly_its_meta_fields_on_edit(
        dk_document_active_a, dk_policy_published_a, dk_resource_featured_a,
        dk_revision_pending_a, tenant_a):
    pairs = [(ProcurementDocumentForm, dk_document_active_a),
             (ProcurementDocumentRevisionUploadForm, dk_revision_pending_a),
             (ProcurementPolicyForm, dk_policy_published_a),
             (KnowledgeResourceForm, dk_resource_featured_a)]
    for form_class, instance in pairs:
        form = form_class(instance=instance, tenant=tenant_a)
        assert set(form.fields) == set(form_class.Meta.fields), form_class.__name__


def test_dk_document_form_requires_only_title_doc_type_and_classification(tenant_a):
    form = ProcurementDocumentForm(tenant=tenant_a)
    required = {name for name, field in form.fields.items() if field.required}
    assert required == {"title", "doc_type", "classification"}


def test_dk_document_form_reports_all_three_missing_required_fields_at_once(tenant_a):
    form = ProcurementDocumentForm({}, tenant=tenant_a)
    assert not form.is_valid()
    assert set(form.errors) == {"title", "doc_type", "classification"}


def test_dk_upload_form_requires_only_the_file(tenant_a):
    form = ProcurementDocumentRevisionUploadForm(tenant=tenant_a)
    required = {name for name, field in form.fields.items() if field.required}
    assert required == {"file"}


def test_dk_upload_form_without_a_file_is_a_field_error_not_a_crash(tenant_a,
                                                                   dk_document_draft_a):
    form = _dk_upload_form(data={"change_note": "No bytes attached"}, tenant=tenant_a,
                           document=dk_document_draft_a)
    assert not form.is_valid()
    assert "file" in form.errors


def test_dk_policy_form_requires_only_title_policy_type_and_version(tenant_a):
    form = ProcurementPolicyForm(tenant=tenant_a)
    required = {name for name, field in form.fields.items() if field.required}
    assert required == {"title", "policy_type", "version_number"}


def test_dk_policy_form_reports_its_missing_required_fields(tenant_a):
    form = ProcurementPolicyForm({}, tenant=tenant_a)
    assert not form.is_valid()
    assert {"title", "policy_type", "version_number"} <= set(form.errors)


def test_dk_resource_form_requires_title_type_category_and_audience(tenant_a):
    form = KnowledgeResourceForm(tenant=tenant_a)
    required = {name for name, field in form.fields.items() if field.required}
    assert required == {"title", "resource_type", "category", "audience"}


def test_dk_resource_form_reports_its_missing_required_fields(tenant_a):
    form = KnowledgeResourceForm({}, tenant=tenant_a)
    assert not form.is_valid()
    assert {"title", "resource_type", "category", "audience"} <= set(form.errors)


def test_dk_upload_form_accepts_a_blank_change_note(tenant_a, dk_document_draft_a):
    """The note is a courtesy, not a gate - an upload with nothing to say still lands."""
    form = _dk_upload_form(files={"file": _dk_upload()}, data={"change_note": ""},
                           tenant=tenant_a, document=dk_document_draft_a)
    assert form.is_valid(), form.errors


def test_dk_minimum_payloads_really_are_valid(tenant_a):
    """The negative tests below only mean something if the baseline saves."""
    assert ProcurementDocumentForm(_dk_document_payload(), tenant=tenant_a).is_valid()
    assert ProcurementPolicyForm(_dk_policy_payload(), tenant=tenant_a).is_valid()
    assert KnowledgeResourceForm(_dk_resource_payload(), tenant=tenant_a).is_valid()


def test_dk_every_form_mixes_the_tenant_stamp_in_before_the_base_form():
    """MRO order is behaviour here, not tidiness.

    ``TenantUniqueMixin`` stamps ``instance.tenant`` in ``__init__``; every one of these four
    models' ``clean()`` compares a chosen FK's tenant against ``self.tenant_id``. Mixed in AFTER
    ``TenantModelForm`` the stamp would land too late and every CREATE would be falsely rejected
    as cross-tenant.
    """
    from apps.core.forms import TenantModelForm
    from apps.procurement.forms._common import TenantUniqueMixin

    for form_class in (ProcurementDocumentForm, ProcurementDocumentRevisionUploadForm,
                       ProcurementPolicyForm, KnowledgeResourceForm):
        mro = form_class.__mro__
        assert mro.index(TenantUniqueMixin) < mro.index(TenantModelForm), form_class.__name__


def test_dk_every_form_stamps_the_tenant_at_construction_time(tenant_a):
    """The stamp is on the instance before ``is_valid()`` is ever called."""
    for form_class in (ProcurementDocumentForm, ProcurementDocumentRevisionUploadForm,
                       ProcurementPolicyForm, KnowledgeResourceForm):
        form = form_class(tenant=tenant_a)
        assert form.instance.tenant_id == tenant_a.pk, form_class.__name__


# =================================================================================================
# 2. The exclusions - the security boundary. Absent from Meta.fields AND ignored when smuggled.
# =================================================================================================

def test_dk_no_form_exposes_a_system_owned_column():
    for form_class in (ProcurementDocumentForm, ProcurementDocumentRevisionUploadForm,
                       ProcurementPolicyForm, KnowledgeResourceForm):
        leaked = _DK_SYSTEM_COLUMNS & set(form_class.Meta.fields)
        # ``file`` is legitimately on the upload form; nothing else in the set ever is.
        assert not leaked, f"{form_class.__name__} exposes {sorted(leaked)}"
    # The parent of a revision is the URL's business, never the POST's.
    assert "document" not in ProcurementDocumentRevisionUploadForm.Meta.fields


def test_dk_document_form_excludes_every_column_the_system_owns():
    fields = set(ProcurementDocumentForm.Meta.fields)
    for name in ("tenant", "number", "status", "current_revision_no", "checked_out_by",
                 "checked_out_at", "extracted_text", "created_by", "created_at", "updated_at"):
        assert name not in fields, name


def test_dk_document_form_carries_no_file_field():
    """Bytes only ever arrive through the revision upload form - there is no back door that
    attaches a file straight to the parent, and therefore no path that skips the allow-list."""
    assert _DK_FILE_FIELD not in ProcurementDocumentForm.Meta.fields
    assert _DK_FILE_FIELD not in ProcurementPolicyForm.Meta.fields
    assert _DK_FILE_FIELD not in KnowledgeResourceForm.Meta.fields


def test_dk_upload_form_excludes_the_parent_and_every_measured_column():
    fields = set(ProcurementDocumentRevisionUploadForm.Meta.fields)
    for name in ("document", "revision_no", "original_filename", "file_size", "sha256",
                 "is_approved", "approved_by", "approved_at", "uploaded_by", "tenant",
                 "extracted_text", "extraction_note", "created_at", "updated_at"):
        assert name not in fields, name


def test_dk_policy_form_excludes_number_status_and_the_publication_stamp():
    fields = set(ProcurementPolicyForm.Meta.fields)
    for name in ("tenant", "number", "status", "published_at", "created_by", "created_at",
                 "updated_at"):
        assert name not in fields, name


def test_dk_resource_form_excludes_the_usage_counters():
    fields = set(KnowledgeResourceForm.Meta.fields)
    for name in ("tenant", "number", "status", "usage_count", "last_used_at", "created_by",
                 "created_at", "updated_at"):
        assert name not in fields, name


def test_dk_document_form_ignores_every_smuggled_system_column(tenant_a, tenant_b, admin_b):
    """Binding the excluded names is not an error - it is simply ignored, and this pins that.

    Django drops unknown keys silently, so "the form does not have the field" and "the field
    cannot be set" are two different claims. This asserts the SECOND one against the saved row.
    """
    payload = _dk_document_payload(
        tenant=str(tenant_b.pk), number="PDOC-99999", status="archived",
        current_revision_no="7", extracted_text="smuggled searchable text",
        checked_out_by=str(admin_b.pk), checked_out_at=timezone.now().isoformat(),
        created_by=str(admin_b.pk), created_at="2001-01-01T00:00",
        updated_at="2001-01-01T00:00")
    form = ProcurementDocumentForm(payload, tenant=tenant_a)
    assert form.is_valid(), form.errors

    obj = form.save()
    obj.refresh_from_db()
    assert obj.tenant_id == tenant_a.pk
    assert obj.number.startswith("PDOC-") and obj.number != "PDOC-99999"
    assert obj.status == "draft"
    assert obj.current_revision_no == 0
    assert obj.extracted_text == ""
    assert obj.checked_out_by_id is None and obj.checked_out_at is None
    assert obj.created_by_id is None


def test_dk_policy_form_ignores_every_smuggled_system_column(tenant_a, tenant_b, admin_b):
    published_at = timezone.now() - datetime.timedelta(days=900)
    payload = _dk_policy_payload(
        tenant=str(tenant_b.pk), number="PPOL-99999", status="published",
        published_at=published_at.isoformat(), created_by=str(admin_b.pk))
    form = ProcurementPolicyForm(payload, tenant=tenant_a)
    assert form.is_valid(), form.errors

    obj = form.save()
    obj.refresh_from_db()
    assert obj.tenant_id == tenant_a.pk
    assert obj.number.startswith("PPOL-") and obj.number != "PPOL-99999"
    assert obj.status == "draft"
    assert obj.published_at is None
    assert obj.created_by_id is None


def test_dk_resource_form_ignores_every_smuggled_system_column(tenant_a, tenant_b, admin_b):
    payload = _dk_resource_payload(
        tenant=str(tenant_b.pk), number="PKR-99999", status="published",
        usage_count="4242", last_used_at=timezone.now().isoformat(),
        created_by=str(admin_b.pk))
    form = KnowledgeResourceForm(payload, tenant=tenant_a)
    assert form.is_valid(), form.errors

    obj = form.save()
    obj.refresh_from_db()
    assert obj.tenant_id == tenant_a.pk
    assert obj.number.startswith("PKR-") and obj.number != "PKR-99999"
    assert obj.status == "draft"
    assert obj.usage_count == 0
    assert obj.last_used_at is None
    assert obj.created_by_id is None


def test_dk_upload_form_ignores_every_smuggled_system_column(
        tenant_a, admin_b, dk_document_draft_a, dk_document_b, dk_media_root):
    """The parent, the version number and the whole approval stamp are all POST-proof.

    ``document`` is the one that matters most: a ``<select>`` of documents here would let a
    crafted POST hang a revision off a record the uploader was never shown. The view supplies it
    from the URL after its own tenant-scoped fetch, so the smuggled tenant-B pk is ignored.
    """
    payload = {"change_note": "First issue",
               "document": str(dk_document_b.pk), "revision_no": "9",
               "is_approved": "on", "approved_by": str(admin_b.pk),
               "approved_at": timezone.now().isoformat(),
               "uploaded_by": str(admin_b.pk),
               "sha256": "f" * 64, "file_size": "999999", "original_filename": "evil.php",
               "extracted_text": "smuggled", "extraction_note": "smuggled note",
               "tenant": "999"}
    form = _dk_upload_form(files={"file": _dk_upload()}, data=payload, tenant=tenant_a,
                           document=dk_document_draft_a)
    assert form.is_valid(), form.errors

    obj = form.save()
    obj.refresh_from_db()
    assert obj.document_id == dk_document_draft_a.pk
    assert obj.tenant_id == tenant_a.pk
    assert obj.revision_no == 1
    assert obj.is_approved is False
    assert obj.approved_by_id is None and obj.approved_at is None
    assert obj.uploaded_by_id is None
    assert obj.sha256 == "" and obj.file_size == 0 and obj.original_filename == ""
    assert obj.extracted_text == "" and obj.extraction_note == ""
    # The document itself is untouched: the pointer only moves on approval.
    dk_document_draft_a.refresh_from_db()
    assert dk_document_draft_a.current_revision_no == 0
    assert dk_document_draft_a.status == "draft"


def test_dk_document_form_normalises_tags_through_the_model_clean(tenant_a):
    """``tags`` IS a form field - what the form must not do is store it verbatim."""
    form = ProcurementDocumentForm(
        _dk_document_payload(tags="Warranty, HVAC ,warranty"), tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.save().tags == "warranty, hvac"


def test_dk_resource_form_normalises_tags_through_the_model_clean(tenant_a):
    form = KnowledgeResourceForm(
        _dk_resource_payload(tags="Playbook , FREIGHT ,playbook"), tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.save().tags == "playbook, freight"


# =================================================================================================
# 3. clean_file - the extension allow-list and the 20 MB cap (NOT the rival 2 MB one)
# =================================================================================================

def test_dk_upload_cap_is_the_twenty_megabyte_document_limit():
    assert MAX_UPLOAD_BYTES == 20 * 1024 * 1024
    assert len(ALLOWED_DOC_EXTENSIONS) == 13


def test_dk_upload_cap_is_not_the_rival_two_megabyte_catalogue_limit():
    """Two constants named ``MAX_UPLOAD_BYTES`` live in this app's forms package.

    ``forms/CatalogManagement/UploadBatches.py`` defines a 2 MB cap for a CSV catalogue import.
    If either constant were pulled through ``apps.procurement.forms``, WHICH limit applied to a
    document revision would depend on package import order - a size cap that changes with the
    wind is not a control. The upload form therefore imports the 20 MB one function-locally, and
    that is pinned here by name and by absence.
    """
    assert _DK_RIVAL_UPLOAD_CAP == 2 * 1024 * 1024
    assert MAX_UPLOAD_BYTES != _DK_RIVAL_UPLOAD_CAP
    # Neither constant is bound at module level in the upload form's own module, so no star
    # import and no later edit can make the applicable cap depend on import order.
    assert "MAX_UPLOAD_BYTES" not in vars(_dk_upload_form_mod)
    assert "ALLOWED_DOC_EXTENSIONS" not in vars(_dk_upload_form_mod)


@pytest.mark.parametrize("filename", ["renewal.txt", "policy.pdf"])
def test_dk_upload_accepts_an_allow_listed_extension(filename, tenant_a, dk_document_draft_a):
    form = _dk_upload_form(files={"file": _dk_upload(name=filename)},
                           data={"change_note": "First issue"}, tenant=tenant_a,
                           document=dk_document_draft_a)
    assert form.is_valid(), form.errors
    assert "file" not in form.errors


@pytest.mark.parametrize("filename,expected", [
    ("shell.php", ".php"),
    ("page.html", ".html"),
    ("logo.svg", ".svg"),
    ("README", ""),
])
def test_dk_upload_refuses_an_extension_outside_the_allow_list(filename, expected, tenant_a,
                                                              dk_document_draft_a):
    form = _dk_upload_form(files={"file": _dk_upload(name=filename)},
                           data={"change_note": "Nope"}, tenant=tenant_a,
                           document=dk_document_draft_a)
    assert not form.is_valid()
    assert f"File type '{expected}' is not allowed." in form.errors["file"]


def test_dk_upload_reads_the_last_extension_segment_not_the_first(tenant_a, dk_document_draft_a):
    """``a.txt.php`` is a ``.php``. Matching on the FIRST dot is the classic bypass, and
    ``MEDIA_ROOT`` sits under the document root on this deployment, so it would be reachable as
    a same-origin URL."""
    form = _dk_upload_form(files={"file": _dk_upload(name="a.txt.php")},
                           data={"change_note": "Double barrelled"}, tenant=tenant_a,
                           document=dk_document_draft_a)
    assert not form.is_valid()
    assert "File type '.php' is not allowed." in form.errors["file"]


def test_dk_upload_extension_check_is_case_insensitive(tenant_a, dk_document_draft_a):
    form = _dk_upload_form(files={"file": _dk_upload(name="SHELL.PHP")},
                           data={"change_note": "Shouting"}, tenant=tenant_a,
                           document=dk_document_draft_a)
    assert not form.is_valid()
    assert "File type '.php' is not allowed." in form.errors["file"]


def test_dk_upload_accepts_an_allow_listed_extension_in_upper_case(tenant_a, dk_document_draft_a,
                                                                   dk_media_root):
    form = _dk_upload_form(files={"file": _dk_upload(name="RENEWAL.TXT")},
                           data={"change_note": "Shouting politely"}, tenant=tenant_a,
                           document=dk_document_draft_a)
    assert form.is_valid(), form.errors


def test_dk_upload_refuses_a_payload_over_the_twenty_megabyte_cap(tenant_a, dk_document_draft_a):
    oversized = _DkSizedUpload("huge.pdf", MAX_UPLOAD_BYTES + 1)
    form = _dk_upload_form(files={"file": oversized}, data={"change_note": "Too big"},
                           tenant=tenant_a, document=dk_document_draft_a)
    assert not form.is_valid()
    assert "File exceeds the 20 MB limit." in form.errors["file"]


def test_dk_upload_accepts_a_payload_between_the_rival_cap_and_the_real_one(
        tenant_a, dk_document_draft_a, dk_media_root):
    """THE regression guard for the constant collision.

    5 MB is over the catalogue import's 2 MB cap and comfortably under the document repository's
    20 MB one. If a future edit ever resolved ``MAX_UPLOAD_BYTES`` through
    ``apps.procurement.forms`` instead of ``apps.core.forms._common``, this upload would start
    being refused and nothing else in the suite would notice.
    """
    assert _DK_RIVAL_UPLOAD_CAP < 5 * 1024 * 1024 < MAX_UPLOAD_BYTES
    sized = _DkSizedUpload("mid-sized.pdf", 5 * 1024 * 1024)
    form = _dk_upload_form(files={"file": sized}, data={"change_note": "Five megabytes"},
                           tenant=tenant_a, document=dk_document_draft_a)
    assert form.is_valid(), form.errors


def test_dk_upload_checks_the_extension_before_the_size(tenant_a, dk_document_draft_a):
    """An oversized ``.php`` is refused as a ``.php``: the cheap gate runs first and the user is
    told the thing they can actually act on."""
    oversized = _DkSizedUpload("huge.php", MAX_UPLOAD_BYTES + 1)
    form = _dk_upload_form(files={"file": oversized}, data={"change_note": "Both wrong"},
                           tenant=tenant_a, document=dk_document_draft_a)
    assert not form.is_valid()
    assert form.errors["file"] == ["File type '.php' is not allowed."]


def test_dk_upload_accepts_a_payload_exactly_on_the_cap(tenant_a, dk_document_draft_a,
                                                        dk_media_root):
    """The comparison is strictly greater-than, so the limit itself is allowed."""
    sized = _DkSizedUpload("exactly.pdf", MAX_UPLOAD_BYTES)
    form = _dk_upload_form(files={"file": sized}, data={"change_note": "On the line"},
                           tenant=tenant_a, document=dk_document_draft_a)
    assert form.is_valid(), form.errors


def test_dk_upload_stores_nothing_when_the_extension_is_refused(tenant_a, dk_document_draft_a):
    form = _dk_upload_form(files={"file": _dk_upload(name="shell.php")},
                           data={"change_note": "Nope"}, tenant=tenant_a,
                           document=dk_document_draft_a)
    assert not form.is_valid()
    assert not ProcurementDocumentRevision.objects.filter(document=dk_document_draft_a).exists()


# =================================================================================================
# 4. Tenant scoping - all eight FK dropdowns, both layers, and the tenant-less form
# =================================================================================================

def test_dk_document_form_dropdowns_offer_only_this_workspace(
        tenant_a, tenant_b, admin_user, member_user, admin_b, dk_supplier_a, dk_supplier_b,
        fulfillment_po_a, fulfillment_po_b, sourcing_event_open_a):
    contract_a = _dk_supplier_contract(tenant_a, dk_supplier_a)
    contract_b = _dk_supplier_contract(tenant_b, dk_supplier_b, title="Globex master agreement")
    event_b = _dk_sourcing_event(tenant_b)

    form = ProcurementDocumentForm(tenant=tenant_a)
    assert _dk_pks(form, "owner") == {admin_user.pk, member_user.pk}
    assert admin_b.pk not in _dk_pks(form, "owner")
    assert _dk_pks(form, "supplier") == {dk_supplier_a.pk}
    assert dk_supplier_b.pk not in _dk_pks(form, "supplier")
    assert _dk_pks(form, "contract") == {contract_a.pk}
    assert contract_b.pk not in _dk_pks(form, "contract")
    assert _dk_pks(form, "purchase_order") == {fulfillment_po_a.pk}
    assert fulfillment_po_b.pk not in _dk_pks(form, "purchase_order")
    assert _dk_pks(form, "sourcing_event") == {sourcing_event_open_a.pk}
    assert event_b.pk not in _dk_pks(form, "sourcing_event")


def test_dk_document_form_supplier_dropdown_needs_the_supplier_role(tenant_a, dk_supplier_a):
    """A bare ``core.Party`` with no ``PartyRole`` is invisible: the dropdown asks for parties
    this workspace can BUY from, which is a role, not a row."""
    roleless = Party.objects.create(tenant=tenant_a, name="Acme Bowling League",
                                    kind="organization")
    offered = _dk_pks(ProcurementDocumentForm(tenant=tenant_a), "supplier")
    assert dk_supplier_a.pk in offered
    assert roleless.pk not in offered


def test_dk_document_form_supplier_dropdown_lists_a_two_role_party_once(tenant_a, dk_supplier_a):
    from apps.core.models import PartyRole
    PartyRole.objects.create(tenant=tenant_a, party=dk_supplier_a, role="vendor",
                             status="active")
    queryset = ProcurementDocumentForm(tenant=tenant_a).fields["supplier"].queryset
    assert list(queryset.values_list("pk", flat=True)).count(dk_supplier_a.pk) == 1


def test_dk_document_form_owner_dropdown_skips_a_deactivated_colleague(tenant_a, admin_user,
                                                                       member_user):
    member_user.is_active = False
    member_user.save(update_fields=["is_active"])
    offered = _dk_pks(ProcurementDocumentForm(tenant=tenant_a), "owner")
    assert offered == {admin_user.pk}


def test_dk_document_form_dropdowns_all_carry_the_none_empty_label(tenant_a):
    form = ProcurementDocumentForm(tenant=tenant_a)
    for name in ("owner", "supplier", "contract", "purchase_order", "sourcing_event"):
        assert form.fields[name].empty_label == "- none -", name


def test_dk_document_form_rejects_a_foreign_supplier_pk(tenant_a, dk_supplier_b):
    form = ProcurementDocumentForm(
        _dk_document_payload(supplier=str(dk_supplier_b.pk)), tenant=tenant_a)
    assert not form.is_valid()
    assert "supplier" in form.errors


def test_dk_document_form_rejects_a_foreign_owner_pk(tenant_a, admin_b):
    form = ProcurementDocumentForm(
        _dk_document_payload(owner=str(admin_b.pk)), tenant=tenant_a)
    assert not form.is_valid()
    assert "owner" in form.errors


def test_dk_document_form_rejects_a_foreign_contract_pk(tenant_a, tenant_b, dk_supplier_b):
    contract_b = _dk_supplier_contract(tenant_b, dk_supplier_b, title="Globex master agreement")
    form = ProcurementDocumentForm(
        _dk_document_payload(contract=str(contract_b.pk)), tenant=tenant_a)
    assert not form.is_valid()
    assert "contract" in form.errors


def test_dk_document_form_rejects_a_foreign_purchase_order_pk(tenant_a, fulfillment_po_b):
    form = ProcurementDocumentForm(
        _dk_document_payload(purchase_order=str(fulfillment_po_b.pk)), tenant=tenant_a)
    assert not form.is_valid()
    assert "purchase_order" in form.errors


def test_dk_document_form_rejects_a_foreign_sourcing_event_pk(tenant_a, tenant_b):
    event_b = _dk_sourcing_event(tenant_b)
    form = ProcurementDocumentForm(
        _dk_document_payload(sourcing_event=str(event_b.pk)), tenant=tenant_a)
    assert not form.is_valid()
    assert "sourcing_event" in form.errors


def test_dk_document_form_second_layer_holds_when_the_select_is_widened(
        tenant_a, tenant_b, dk_supplier_b, fulfillment_po_b):
    """The crafted POST that never went near the widget.

    With the querysets widened, ``ModelChoiceField`` accepts the foreign pk and what answers is
    ``_reject_foreign`` in ``clean()`` (backed by ``ProcurementDocument.clean()``), which is the
    layer that actually holds.
    """
    event_b = _dk_sourcing_event(tenant_b)
    contract_b = _dk_supplier_contract(tenant_b, dk_supplier_b, title="Globex master agreement")
    payload = _dk_document_payload(supplier=str(dk_supplier_b.pk),
                                   contract=str(contract_b.pk),
                                   purchase_order=str(fulfillment_po_b.pk),
                                   sourcing_event=str(event_b.pk))
    form = ProcurementDocumentForm(payload, tenant=tenant_a)
    _dk_widen(form, "supplier", "contract", "purchase_order", "sourcing_event")

    assert not form.is_valid()
    for name in ("supplier", "contract", "purchase_order", "sourcing_event"):
        assert "That record belongs to another workspace." in form.errors[name], name
    assert not ProcurementDocument.objects.filter(supplier=dk_supplier_b).exists()


def test_dk_document_form_accepts_this_workspaces_own_spine_links(
        tenant_a, admin_user, dk_supplier_a, fulfillment_po_a, sourcing_event_open_a):
    contract_a = _dk_supplier_contract(tenant_a, dk_supplier_a)
    payload = _dk_document_payload(owner=str(admin_user.pk), supplier=str(dk_supplier_a.pk),
                                   contract=str(contract_a.pk),
                                   purchase_order=str(fulfillment_po_a.pk),
                                   sourcing_event=str(sourcing_event_open_a.pk))
    form = ProcurementDocumentForm(payload, tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save()
    assert obj.supplier_id == dk_supplier_a.pk
    assert obj.contract_id == contract_a.pk
    assert obj.purchase_order_id == fulfillment_po_a.pk
    assert obj.sourcing_event_id == sourcing_event_open_a.pk
    assert obj.owner_id == admin_user.pk


def test_dk_document_form_without_a_tenant_offers_nothing(tenant_a, dk_supplier_a, admin_user,
                                                          fulfillment_po_a,
                                                          sourcing_event_open_a):
    """A tenant-less user (the superuser) must be shown an empty dropdown, not every workspace.

    The five fixtures are requested so every one of these tables has a row in it. An empty
    dropdown over an empty table proves nothing (a verified answer to the wrong question).
    """
    form = ProcurementDocumentForm()
    for name in ("owner", "supplier", "contract", "purchase_order", "sourcing_event"):
        assert not form.fields[name].queryset.exists(), name


def test_dk_document_form_without_a_tenant_refuses_a_posted_pk(tenant_a, dk_supplier_a):
    form = ProcurementDocumentForm(_dk_document_payload(supplier=str(dk_supplier_a.pk)))
    assert not form.is_valid()
    assert "supplier" in form.errors


def test_dk_policy_form_dropdowns_offer_only_this_workspace(
        tenant_a, tenant_b, admin_user, member_user, admin_b, org_unit_a, org_unit_b,
        dk_policy_published_a, dk_policy_b, dk_document_active_a, dk_document_b):
    form = ProcurementPolicyForm(tenant=tenant_a)
    assert dk_policy_published_a.pk in _dk_pks(form, "previous_version")
    assert dk_policy_b.pk not in _dk_pks(form, "previous_version")
    assert _dk_pks(form, "applies_to") == {org_unit_a.pk}
    assert org_unit_b.pk not in _dk_pks(form, "applies_to")
    assert dk_document_active_a.pk in _dk_pks(form, "document")
    assert dk_document_b.pk not in _dk_pks(form, "document")
    assert _dk_pks(form, "owner") == {admin_user.pk, member_user.pk}
    assert admin_b.pk not in _dk_pks(form, "owner")


def test_dk_policy_form_dropdowns_carry_their_own_empty_labels(tenant_a):
    form = ProcurementPolicyForm(tenant=tenant_a)
    assert form.fields["previous_version"].empty_label == "- first version -"
    assert form.fields["applies_to"].empty_label == "- the whole workspace -"
    assert form.fields["threshold_currency"].empty_label == "- not labelled -"
    assert form.fields["owner"].empty_label == "- none -"
    assert form.fields["document"].empty_label == "- none -"


def test_dk_policy_form_previous_version_excludes_the_row_being_edited(tenant_a,
                                                                       dk_policy_published_a,
                                                                       dk_policy_v1_archived_a):
    form = ProcurementPolicyForm(instance=dk_policy_published_a, tenant=tenant_a)
    offered = _dk_pks(form, "previous_version")
    assert dk_policy_published_a.pk not in offered
    assert dk_policy_v1_archived_a.pk in offered


def test_dk_policy_form_currency_dropdown_is_global_and_active_only(tenant_a, usd):
    """``accounting.Currency`` has NO tenant column - narrowing it would empty the dropdown."""
    retired = Currency.objects.create(code="ZWD", name="Zimbabwe Dollar", is_active=False)
    offered = _dk_pks(ProcurementPolicyForm(tenant=tenant_a), "threshold_currency")
    assert usd.pk in offered
    assert retired.pk not in offered


def test_dk_policy_form_never_rejects_the_global_currency_as_foreign(tenant_a, usd):
    """``accounting.Currency`` has no tenant column, so it is deliberately absent from
    ``_SCOPED_LINKS``. Re-checking it would reject every currency anybody ever chose."""
    form = ProcurementPolicyForm(
        _dk_policy_payload(threshold_amount="1000.00", threshold_basis="per_line",
                           threshold_currency=str(usd.pk)), tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.save().threshold_currency_id == usd.pk


def test_dk_policy_form_rejects_a_foreign_previous_version_pk(tenant_a, dk_policy_b):
    form = ProcurementPolicyForm(
        _dk_policy_payload(previous_version=str(dk_policy_b.pk)), tenant=tenant_a)
    assert not form.is_valid()
    assert "previous_version" in form.errors


def test_dk_policy_form_rejects_a_foreign_applies_to_pk(tenant_a, org_unit_b):
    form = ProcurementPolicyForm(
        _dk_policy_payload(applies_to=str(org_unit_b.pk)), tenant=tenant_a)
    assert not form.is_valid()
    assert "applies_to" in form.errors


def test_dk_policy_form_rejects_a_foreign_document_pk(tenant_a, dk_document_b):
    form = ProcurementPolicyForm(
        _dk_policy_payload(document=str(dk_document_b.pk)), tenant=tenant_a)
    assert not form.is_valid()
    assert "document" in form.errors


def test_dk_policy_form_rejects_a_foreign_owner_pk(tenant_a, admin_b):
    form = ProcurementPolicyForm(_dk_policy_payload(owner=str(admin_b.pk)), tenant=tenant_a)
    assert not form.is_valid()
    assert "owner" in form.errors


def test_dk_policy_form_second_layer_holds_when_the_selects_are_widened(
        tenant_a, dk_policy_b, org_unit_b, dk_document_b):
    payload = _dk_policy_payload(previous_version=str(dk_policy_b.pk),
                                 applies_to=str(org_unit_b.pk),
                                 document=str(dk_document_b.pk))
    form = ProcurementPolicyForm(payload, tenant=tenant_a)
    _dk_widen(form, "previous_version", "applies_to", "document")

    assert not form.is_valid()
    for name in ("previous_version", "applies_to", "document"):
        assert "That record belongs to another workspace." in form.errors[name], name
    assert not ProcurementPolicy.objects.filter(tenant=tenant_a,
                                                previous_version=dk_policy_b).exists()


def test_dk_policy_form_without_a_tenant_offers_nothing(tenant_a, dk_policy_published_a,
                                                        org_unit_a, dk_document_active_a, usd):
    """The fixtures put a row in each of the five tables first, so ``.none()`` is the reason the
    dropdowns are empty rather than the database being."""
    form = ProcurementPolicyForm()
    for name in ("previous_version", "applies_to", "owner", "document", "threshold_currency"):
        assert not form.fields[name].queryset.exists(), name


def test_dk_resource_form_dropdowns_offer_only_this_workspace(
        tenant_a, admin_user, member_user, admin_b, dk_document_active_a, dk_document_b):
    form = KnowledgeResourceForm(tenant=tenant_a)
    assert dk_document_active_a.pk in _dk_pks(form, "document")
    assert dk_document_b.pk not in _dk_pks(form, "document")
    assert _dk_pks(form, "owner") == {admin_user.pk, member_user.pk}
    assert admin_b.pk not in _dk_pks(form, "owner")
    assert form.fields["owner"].empty_label == "- none -"
    assert form.fields["document"].empty_label == "- none -"


def test_dk_resource_form_rejects_a_foreign_document_pk(tenant_a, dk_document_b):
    form = KnowledgeResourceForm(
        _dk_resource_payload(document=str(dk_document_b.pk)), tenant=tenant_a)
    assert not form.is_valid()
    assert "document" in form.errors


def test_dk_resource_form_rejects_a_foreign_owner_pk(tenant_a, admin_b):
    form = KnowledgeResourceForm(_dk_resource_payload(owner=str(admin_b.pk)), tenant=tenant_a)
    assert not form.is_valid()
    assert "owner" in form.errors


def test_dk_resource_form_second_layer_holds_when_the_select_is_widened(tenant_a, dk_document_b):
    form = KnowledgeResourceForm(
        _dk_resource_payload(document=str(dk_document_b.pk)), tenant=tenant_a)
    _dk_widen(form, "document")

    assert not form.is_valid()
    assert "That record belongs to another workspace." in form.errors["document"]
    assert not KnowledgeResource.objects.filter(document=dk_document_b).exists()


def test_dk_resource_form_without_a_tenant_offers_nothing(tenant_a, dk_document_active_a,
                                                          admin_user):
    """Both tables have a row before the assertion - an empty dropdown over an empty table would
    be a verified answer to the wrong question."""
    form = KnowledgeResourceForm()
    for name in ("owner", "document"):
        assert not form.fields[name].queryset.exists(), name


def test_dk_upload_form_has_no_model_choice_field_to_scope(tenant_a):
    """The absence of a queryset is the scoping: the one FK comes from the URL, not the POST."""
    form = ProcurementDocumentRevisionUploadForm(tenant=tenant_a)
    assert not [name for name, field in form.fields.items()
                if isinstance(field, forms.ModelChoiceField)]


# =================================================================================================
# 5. ProcurementPolicyForm - the numeric guards, the pairing rule and the cycle guard
# =================================================================================================

@pytest.mark.parametrize("raw", ["NaN", "Infinity", "-Infinity", "nan", "inf"])
def test_dk_policy_form_refuses_a_non_finite_threshold(raw, tenant_a):
    """A friendly field error, never a 500 - and never a row carrying a non-finite Decimal."""
    form = ProcurementPolicyForm(_dk_policy_payload(threshold_amount=raw), tenant=tenant_a)
    assert not form.is_valid()
    assert "Enter a number." in form.errors["threshold_amount"]
    assert not ProcurementPolicy.objects.filter(tenant=tenant_a,
                                                title="Sole Source Justification Rule").exists()


def test_dk_policy_form_refuses_an_exponent_that_overflows_the_column(tenant_a):
    form = ProcurementPolicyForm(_dk_policy_payload(threshold_amount="1e400"), tenant=tenant_a)
    assert not form.is_valid()
    assert any("no more than 14 digits" in message
               for message in form.errors["threshold_amount"])


def test_dk_policy_form_refuses_more_digits_than_max_digits(tenant_a):
    form = ProcurementPolicyForm(_dk_policy_payload(threshold_amount="12345678901234567"),
                                 tenant=tenant_a)
    assert not form.is_valid()
    assert any("no more than 14 digits" in message
               for message in form.errors["threshold_amount"])


def test_dk_policy_form_refuses_three_decimal_places(tenant_a):
    form = ProcurementPolicyForm(_dk_policy_payload(threshold_amount="1000.123"),
                                 tenant=tenant_a)
    assert not form.is_valid()
    assert any("no more than 2 decimal places" in message
               for message in form.errors["threshold_amount"])


def test_dk_policy_form_refuses_a_negative_threshold(tenant_a):
    """The model's ``MinValueValidator(0)`` surfaces as a FIELD error, not an IntegrityError."""
    form = ProcurementPolicyForm(
        _dk_policy_payload(threshold_amount="-5.00", threshold_basis="per_line"),
        tenant=tenant_a)
    assert not form.is_valid()
    assert any("greater than or equal to 0" in message
               for message in form.errors["threshold_amount"])


@pytest.mark.parametrize("raw", ["twenty thousand", "25,000.00", "1e", "--5", "0x10", "1/2",
                                 "٤٢٠٠٠.٥٥٥"])
def test_dk_policy_form_refuses_garbage_in_the_threshold(raw, tenant_a):
    form = ProcurementPolicyForm(_dk_policy_payload(threshold_amount=raw), tenant=tenant_a)
    assert not form.is_valid()
    assert "threshold_amount" in form.errors


def test_dk_policy_form_reads_unicode_digits_as_the_number_they_are(tenant_a):
    """``Decimal("٤٢")`` is 42 in Python - the parser accepts any Unicode decimal digit.

    Worth pinning rather than assuming: a reader would expect "not ASCII, therefore refused", and
    the truth is the opposite. It is safe (the result is still a bounded ``Decimal`` that the
    ``max_digits`` / ``decimal_places`` / ``MinValueValidator`` ladder then judges), but a future
    change that started rejecting it would be a behaviour change nobody wrote down.
    """
    form = ProcurementPolicyForm(
        _dk_policy_payload(threshold_amount="٤٢", threshold_basis="per_line"), tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.save().threshold_amount == Decimal("42.00")


def test_dk_policy_form_accepts_a_threshold_on_the_column_boundary(tenant_a, usd):
    """Twelve whole digits and two decimals is exactly ``DecimalField(14, 2)``."""
    form = ProcurementPolicyForm(
        _dk_policy_payload(threshold_amount="999999999999.99", threshold_basis="per_line",
                           threshold_currency=str(usd.pk)), tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.save().threshold_amount == Decimal("999999999999.99")


def test_dk_policy_form_accepts_a_zero_threshold(tenant_a):
    """Zero is a legitimate rule ("every purchase needs quotes") - the floor is inclusive."""
    form = ProcurementPolicyForm(
        _dk_policy_payload(threshold_amount="0", threshold_basis="per_requisition"),
        tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.save().threshold_amount == Decimal("0.00")


def test_dk_policy_form_refuses_an_amount_with_no_basis(tenant_a):
    form = ProcurementPolicyForm(_dk_policy_payload(threshold_amount="25000.00"),
                                 tenant=tenant_a)
    assert not form.is_valid()
    assert "threshold_basis" in form.errors
    assert "measured against" in _dk_messages(form, "threshold_basis")


def test_dk_policy_form_refuses_a_basis_with_no_amount(tenant_a):
    form = ProcurementPolicyForm(_dk_policy_payload(threshold_basis="per_contract_year"),
                                 tenant=tenant_a)
    assert not form.is_valid()
    assert "threshold_amount" in form.errors
    assert "states nothing" in _dk_messages(form, "threshold_amount")


def test_dk_policy_form_accepts_neither_half_of_the_threshold(tenant_a):
    form = ProcurementPolicyForm(_dk_policy_payload(), tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save()
    assert obj.threshold_amount is None and obj.threshold_basis == ""


def test_dk_policy_form_refuses_a_threshold_basis_outside_the_vocabulary(tenant_a):
    form = ProcurementPolicyForm(
        _dk_policy_payload(threshold_amount="100.00", threshold_basis="per_fortnight"),
        tenant=tenant_a)
    assert not form.is_valid()
    assert any("Select a valid choice" in message
               for message in form.errors["threshold_basis"])


def test_dk_policy_form_refuses_a_policy_superseding_itself(tenant_a, dk_policy_published_a,
                                                            dk_policy_v1_archived_a):
    """Two layers, and the row is left exactly as it was after both.

    The narrowed ``<select>`` drops the row being edited, so the ordinary POST is refused as an
    invalid choice; widened, ``ProcurementPolicy.clean()`` answers with its own sentence. Neither
    path writes.
    """
    payload = _dk_policy_payload(title=dk_policy_published_a.title,
                                 policy_type=dk_policy_published_a.policy_type,
                                 version_number=dk_policy_published_a.version_number,
                                 previous_version=str(dk_policy_published_a.pk))

    narrowed = ProcurementPolicyForm(payload, instance=dk_policy_published_a, tenant=tenant_a)
    assert not narrowed.is_valid()
    assert "previous_version" in narrowed.errors

    widened = _dk_widen(
        ProcurementPolicyForm(payload, instance=dk_policy_published_a, tenant=tenant_a),
        "previous_version")
    assert not widened.is_valid()
    assert "A policy cannot supersede itself." in _dk_messages(widened, "previous_version")

    dk_policy_published_a.refresh_from_db()
    assert dk_policy_published_a.previous_version_id == dk_policy_v1_archived_a.pk


def test_dk_policy_form_refuses_a_two_hop_supersession_loop(tenant_a, dk_policy_v1_archived_a,
                                                            dk_policy_published_a):
    """A -> B -> A. ``dk_policy_published_a`` (v2) already points at v1; pointing v1 back at v2
    would close the loop, and a cycle in a self-FK is a hung request waiting for the first piece
    of code that walks the whole chain."""
    payload = _dk_policy_payload(title=dk_policy_v1_archived_a.title,
                                 policy_type=dk_policy_v1_archived_a.policy_type,
                                 version_number=dk_policy_v1_archived_a.version_number,
                                 previous_version=str(dk_policy_published_a.pk))
    form = ProcurementPolicyForm(payload, instance=dk_policy_v1_archived_a, tenant=tenant_a)

    assert not form.is_valid()
    assert "make the version chain loop" in _dk_messages(form, "previous_version")

    dk_policy_v1_archived_a.refresh_from_db()
    assert dk_policy_v1_archived_a.previous_version_id is None


def test_dk_policy_form_refuses_a_predecessor_whose_history_already_loops(tenant_a):
    """A loop written before the guard existed must not be joinable either."""
    left = _dk_policy(tenant_a, title="Looped rule", version_number="1.0")
    right = _dk_policy(tenant_a, title="Looped rule", version_number="2.0",
                       previous_version=left)
    ProcurementPolicy.objects.filter(pk=left.pk).update(previous_version=right)

    form = ProcurementPolicyForm(
        _dk_policy_payload(previous_version=str(right.pk)), tenant=tenant_a)
    assert not form.is_valid()
    assert "already loops" in _dk_messages(form, "previous_version")


def test_dk_policy_form_refuses_a_chain_deeper_than_the_walk_will_follow(tenant_a):
    """Past ``MAX_CHAIN_DEPTH`` the guard refuses rather than saying "probably fine"."""
    previous = None
    for index in range(MAX_CHAIN_DEPTH + 2):
        previous = _dk_policy(tenant_a, title="Deep rule", version_number=f"{index}.0",
                              previous_version=previous)

    form = ProcurementPolicyForm(
        _dk_policy_payload(previous_version=str(previous.pk)), tenant=tenant_a)
    assert not form.is_valid()
    assert f"longer than {MAX_CHAIN_DEPTH} versions" in _dk_messages(form, "previous_version")


def test_dk_policy_form_accepts_an_ordinary_predecessor(tenant_a, dk_policy_published_a):
    form = ProcurementPolicyForm(
        _dk_policy_payload(previous_version=str(dk_policy_published_a.pk)), tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.save().previous_version_id == dk_policy_published_a.pk


def test_dk_policy_form_refuses_a_duplicate_title_and_version_in_one_workspace(
        tenant_a, dk_policy_published_a):
    """``unique_together = (tenant, title, version_number)`` reaches the form because
    ``TenantUniqueMixin`` puts ``tenant`` back into the check."""
    form = ProcurementPolicyForm(
        _dk_policy_payload(title=dk_policy_published_a.title,
                           version_number=dk_policy_published_a.version_number),
        tenant=tenant_a)
    assert not form.is_valid()
    assert form.non_field_errors()


def test_dk_policy_form_allows_the_same_title_and_version_in_another_workspace(
        tenant_b, dk_policy_published_a):
    form = ProcurementPolicyForm(
        _dk_policy_payload(title=dk_policy_published_a.title,
                           version_number=dk_policy_published_a.version_number),
        tenant=tenant_b)
    assert form.is_valid(), form.errors
    assert form.save().tenant_id == tenant_b.pk


# =================================================================================================
# 6. Over-length and malformed input on every CharField and DateField
# =================================================================================================
# The development database is not in strict SQL mode, so a missing form-level guard would
# TRUNCATE a 300-character title to 200 and save it. The form is the only real control, which is
# why each of these asserts a clean field error and that nothing was written.

@pytest.mark.parametrize("field,limit", [("title", 200), ("tags", 255)])
def test_dk_document_form_refuses_an_over_length_char_field(field, limit, tenant_a):
    form = ProcurementDocumentForm(_dk_document_payload(**{field: "x" * (limit + 1)}),
                                   tenant=tenant_a)
    assert not form.is_valid()
    assert any(f"at most {limit} characters" in message for message in form.errors[field])
    assert not ProcurementDocument.objects.filter(tenant=tenant_a).exists()


@pytest.mark.parametrize("field,limit", [("title", 200), ("summary", 500),
                                         ("version_number", 20)])
def test_dk_policy_form_refuses_an_over_length_char_field(field, limit, tenant_a):
    form = ProcurementPolicyForm(_dk_policy_payload(**{field: "x" * (limit + 1)}),
                                 tenant=tenant_a)
    assert not form.is_valid()
    assert any(f"at most {limit} characters" in message for message in form.errors[field])
    assert not ProcurementPolicy.objects.filter(tenant=tenant_a).exists()


@pytest.mark.parametrize("field,limit", [("title", 200), ("summary", 500), ("tags", 255)])
def test_dk_resource_form_refuses_an_over_length_char_field(field, limit, tenant_a):
    form = KnowledgeResourceForm(_dk_resource_payload(**{field: "x" * (limit + 1)}),
                                 tenant=tenant_a)
    assert not form.is_valid()
    assert any(f"at most {limit} characters" in message for message in form.errors[field])
    assert not KnowledgeResource.objects.filter(tenant=tenant_a).exists()


def test_dk_upload_form_refuses_an_over_length_change_note(tenant_a, dk_document_draft_a):
    form = _dk_upload_form(files={"file": _dk_upload()}, data={"change_note": "x" * 256},
                           tenant=tenant_a, document=dk_document_draft_a)
    assert not form.is_valid()
    assert any("at most 255 characters" in message for message in form.errors["change_note"])


@pytest.mark.parametrize("field,limit", [("title", 200), ("tags", 255)])
def test_dk_document_form_accepts_a_char_field_exactly_on_its_limit(field, limit, tenant_a):
    """The boundary itself is legal - an off-by-one guard would reject valid input."""
    value = "x" * limit
    form = ProcurementDocumentForm(_dk_document_payload(**{field: value}), tenant=tenant_a)
    assert form.is_valid(), form.errors


@pytest.mark.parametrize("field", ["effective_date", "expires_on", "review_on",
                                   "retention_until"])
@pytest.mark.parametrize("raw", ["not-a-date", "2026-13-45", "12/31/2026", "0000-00-00",
                                 "2026-02-30"])
def test_dk_document_form_refuses_a_malformed_date(field, raw, tenant_a):
    form = ProcurementDocumentForm(_dk_document_payload(**{field: raw}), tenant=tenant_a)
    assert not form.is_valid()
    assert "Enter a valid date." in form.errors[field]


@pytest.mark.parametrize("field", ["effective_from", "next_review_on"])
def test_dk_policy_form_refuses_a_malformed_date(field, tenant_a):
    form = ProcurementPolicyForm(_dk_policy_payload(**{field: "31-12-2026"}), tenant=tenant_a)
    assert not form.is_valid()
    assert "Enter a valid date." in form.errors[field]


def test_dk_resource_form_refuses_a_malformed_review_date(tenant_a):
    form = KnowledgeResourceForm(_dk_resource_payload(review_on="tomorrow"), tenant=tenant_a)
    assert not form.is_valid()
    assert "Enter a valid date." in form.errors["review_on"]


def test_dk_document_form_accepts_iso_dates_and_stores_them(tenant_a):
    form = ProcurementDocumentForm(
        _dk_document_payload(effective_date=_dk_iso(-30), expires_on=_dk_iso(180),
                             review_on=_dk_iso(90), retention_until=_dk_iso(2000)),
        tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save()
    assert obj.effective_date == _dk_days(-30)
    assert obj.expires_on == _dk_days(180)
    assert obj.review_on == _dk_days(90)


def test_dk_document_form_refuses_an_expiry_before_the_effective_date(tenant_a):
    """The model's date-order rule surfaces as a field error on ``expires_on``."""
    form = ProcurementDocumentForm(
        _dk_document_payload(effective_date=_dk_iso(10), expires_on=_dk_iso(-10)),
        tenant=tenant_a)
    assert not form.is_valid()
    assert "The expiry date cannot be before the effective date." in form.errors["expires_on"]


def test_dk_document_form_accepts_an_expiry_on_the_effective_date(tenant_a):
    form = ProcurementDocumentForm(
        _dk_document_payload(effective_date=_dk_iso(5), expires_on=_dk_iso(5)), tenant=tenant_a)
    assert form.is_valid(), form.errors


@pytest.mark.parametrize("field,raw", [("doc_type", "blueprint"),
                                       ("classification", "top_secret")])
def test_dk_document_form_refuses_a_value_outside_the_vocabulary(field, raw, tenant_a):
    form = ProcurementDocumentForm(_dk_document_payload(**{field: raw}), tenant=tenant_a)
    assert not form.is_valid()
    assert any("Select a valid choice" in message for message in form.errors[field])


@pytest.mark.parametrize("field,raw", [("resource_type", "podcast"),
                                       ("category", "aerospace"),
                                       ("audience", "everyone")])
def test_dk_resource_form_refuses_a_value_outside_the_vocabulary(field, raw, tenant_a):
    form = KnowledgeResourceForm(_dk_resource_payload(**{field: raw}), tenant=tenant_a)
    assert not form.is_valid()
    assert any("Select a valid choice" in message for message in form.errors[field])


def test_dk_policy_form_refuses_a_policy_type_outside_the_vocabulary(tenant_a):
    form = ProcurementPolicyForm(_dk_policy_payload(policy_type="vibes"), tenant=tenant_a)
    assert not form.is_valid()
    assert any("Select a valid choice" in message for message in form.errors["policy_type"])


@pytest.mark.parametrize("raw", ["abc", "0", "-1", "9" * 25, "1e5", "1 OR 1=1"])
def test_dk_document_form_refuses_junk_in_a_foreign_key_field(raw, tenant_a):
    """A junk pk is a field error, never a 500 and never a stray ``ValueError`` (L11)."""
    form = ProcurementDocumentForm(_dk_document_payload(supplier=raw), tenant=tenant_a)
    assert not form.is_valid()
    assert "supplier" in form.errors


def test_dk_document_form_treats_a_blank_foreign_key_as_none(tenant_a):
    """Blank means "- none -": every spine link is optional, so an empty value must SAVE."""
    form = ProcurementDocumentForm(
        _dk_document_payload(supplier="", contract="", purchase_order="", sourcing_event="",
                             owner=""),
        tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save()
    assert (obj.supplier_id, obj.contract_id, obj.purchase_order_id, obj.sourcing_event_id,
            obj.owner_id) == (None, None, None, None, None)


@pytest.mark.parametrize("raw", ["abc", "0", "9" * 25])
def test_dk_policy_form_refuses_junk_in_a_foreign_key_field(raw, tenant_a):
    form = ProcurementPolicyForm(_dk_policy_payload(previous_version=raw), tenant=tenant_a)
    assert not form.is_valid()
    assert "previous_version" in form.errors


@pytest.mark.parametrize("raw", ["abc", "0", "9" * 25])
def test_dk_resource_form_refuses_junk_in_a_foreign_key_field(raw, tenant_a):
    form = KnowledgeResourceForm(_dk_resource_payload(document=raw), tenant=tenant_a)
    assert not form.is_valid()
    assert "document" in form.errors


# =================================================================================================
# 7. Edit mode - prefill, and no system column reset on save
# =================================================================================================

def test_dk_document_form_prefills_from_the_instance(tenant_a, dk_document_active_a,
                                                     dk_supplier_a, admin_user):
    form = ProcurementDocumentForm(instance=dk_document_active_a, tenant=tenant_a)
    assert form.initial["title"] == dk_document_active_a.title
    assert form.initial["doc_type"] == "sow"
    assert form.initial["classification"] == "internal"
    assert form.initial["supplier"] == dk_supplier_a.pk
    assert form.initial["owner"] == admin_user.pk
    assert form.initial["effective_date"] == _dk_days(-30)
    assert form.initial["review_on"] == _dk_days(180)


def test_dk_document_form_edit_leaves_every_system_column_alone(tenant_a, dk_document_chain_a,
                                                                admin_user):
    """The row this edits carries a real pointer, real extracted text and an ``active`` status -
    all three are absent from the form, so a save must return them untouched."""
    before = {"number": dk_document_chain_a.number,
              "status": dk_document_chain_a.status,
              "pointer": dk_document_chain_a.current_revision_no,
              "text": dk_document_chain_a.extracted_text,
              "created_by": dk_document_chain_a.created_by_id}
    assert before["pointer"] == 1 and before["text"] and before["status"] == "active"

    form = ProcurementDocumentForm(
        _dk_document_payload(title="Boiler maintenance contract (2027 renewal)",
                             doc_type="sow", classification="internal",
                             status="draft", number="PDOC-00001",
                             current_revision_no="0", extracted_text=""),
        instance=dk_document_chain_a, tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save()
    obj.refresh_from_db()

    assert obj.title == "Boiler maintenance contract (2027 renewal)"
    assert obj.number == before["number"]
    assert obj.status == before["status"]
    assert obj.current_revision_no == before["pointer"]
    assert obj.extracted_text == before["text"]
    assert obj.created_by_id == before["created_by"]
    assert obj.tenant_id == tenant_a.pk


def test_dk_policy_form_prefills_from_the_instance(tenant_a, dk_policy_published_a,
                                                   dk_policy_v1_archived_a, org_unit_a, usd,
                                                   dk_document_active_a):
    form = ProcurementPolicyForm(instance=dk_policy_published_a, tenant=tenant_a)
    assert form.initial["title"] == "Competitive Bidding Threshold"
    assert form.initial["version_number"] == "2.0"
    assert form.initial["previous_version"] == dk_policy_v1_archived_a.pk
    assert form.initial["applies_to"] == org_unit_a.pk
    assert form.initial["document"] == dk_document_active_a.pk
    assert form.initial["threshold_amount"] == Decimal("25000.00")
    assert form.initial["threshold_basis"] == "per_purchase_order"
    assert form.initial["threshold_currency"] == usd.pk
    assert form.initial["requires_acknowledgment"] is True


def test_dk_policy_form_edit_leaves_the_publication_stamp_alone(tenant_a, dk_policy_published_a,
                                                                 dk_policy_v1_archived_a, usd):
    before = {"number": dk_policy_published_a.number,
              "status": dk_policy_published_a.status,
              "published_at": dk_policy_published_a.published_at,
              "created_by": dk_policy_published_a.created_by_id}
    assert before["status"] == "published" and before["published_at"] is not None

    form = ProcurementPolicyForm(
        _dk_policy_payload(title="Competitive Bidding Threshold",
                           policy_type="competitive_bidding", version_number="2.0",
                           summary="Three written quotes above the figure.",
                           previous_version=str(dk_policy_v1_archived_a.pk),
                           threshold_amount="30000.00",
                           threshold_basis="per_purchase_order",
                           threshold_currency=str(usd.pk),
                           status="draft", number="PPOL-00001",
                           published_at=""),
        instance=dk_policy_published_a, tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save()
    obj.refresh_from_db()

    assert obj.threshold_amount == Decimal("30000.00")
    assert obj.number == before["number"]
    assert obj.status == before["status"]
    assert obj.published_at == before["published_at"]
    assert obj.created_by_id == before["created_by"]


def test_dk_resource_form_prefills_from_the_instance(tenant_a, dk_resource_featured_a,
                                                     dk_document_active_a, admin_user):
    form = KnowledgeResourceForm(instance=dk_resource_featured_a, tenant=tenant_a)
    assert form.initial["title"] == "RFP template - IT services"
    assert form.initial["resource_type"] == "rfp_template"
    assert form.initial["category"] == "it_software"
    assert form.initial["audience"] == "buyer"
    assert form.initial["is_featured"] is True
    assert form.initial["document"] == dk_document_active_a.pk
    assert form.initial["owner"] == admin_user.pk


def test_dk_resource_form_edit_leaves_the_usage_counters_alone(tenant_a, dk_resource_used_a):
    """``usage_count`` is written by the "use this" verb through an atomic ``F() + 1``. A form
    save that touched it would clobber exactly the concurrent increments that expression exists
    to protect."""
    before = {"number": dk_resource_used_a.number,
              "status": dk_resource_used_a.status,
              "usage_count": dk_resource_used_a.usage_count,
              "last_used_at": dk_resource_used_a.last_used_at,
              "created_by": dk_resource_used_a.created_by_id}
    assert before["usage_count"] == 7 and before["last_used_at"] is not None

    form = KnowledgeResourceForm(
        _dk_resource_payload(title="Freight negotiation playbook (v2)",
                             resource_type="negotiation_playbook", category="logistics",
                             audience="buyer", usage_count="0", last_used_at="",
                             status="draft", number="PKR-00001"),
        instance=dk_resource_used_a, tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save()
    obj.refresh_from_db()

    assert obj.title == "Freight negotiation playbook (v2)"
    assert obj.number == before["number"]
    assert obj.status == before["status"]
    assert obj.usage_count == before["usage_count"]
    assert obj.last_used_at == before["last_used_at"]
    assert obj.created_by_id == before["created_by"]


def test_dk_upload_form_over_an_existing_revision_touches_no_measured_column(
        tenant_a, dk_revision_pending_a, dk_media_root):
    """There is no revision edit VIEW - a wrong revision is superseded by the next upload.

    This asserts the form would not become one by accident: bound over an existing row it can
    still only change the two fields it declares, and every measured or stamped column survives.
    """
    before = {"revision_no": dk_revision_pending_a.revision_no,
              "sha256": dk_revision_pending_a.sha256,
              "file_size": dk_revision_pending_a.file_size,
              "original_filename": dk_revision_pending_a.original_filename,
              "extracted_text": dk_revision_pending_a.extracted_text,
              "extraction_note": dk_revision_pending_a.extraction_note,
              "uploaded_by": dk_revision_pending_a.uploaded_by_id,
              "is_approved": dk_revision_pending_a.is_approved,
              "document": dk_revision_pending_a.document_id}
    assert before["sha256"] and before["revision_no"] == 2

    form = ProcurementDocumentRevisionUploadForm(
        {"change_note": "Note corrected", "revision_no": "99", "is_approved": "on",
         "sha256": "0" * 64},
        {"file": _dk_upload(name="boiler-r2b.txt", body=b"Replacement bytes.")},
        instance=dk_revision_pending_a, tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save()
    obj.refresh_from_db()

    assert obj.change_note == "Note corrected"
    assert obj.revision_no == before["revision_no"]
    assert obj.sha256 == before["sha256"]
    assert obj.file_size == before["file_size"]
    assert obj.original_filename == before["original_filename"]
    assert obj.extracted_text == before["extracted_text"]
    assert obj.extraction_note == before["extraction_note"]
    assert obj.uploaded_by_id == before["uploaded_by"]
    assert obj.is_approved == before["is_approved"]
    assert obj.document_id == before["document"]


def test_dk_document_form_edit_can_clear_an_optional_foreign_key(tenant_a, dk_document_active_a):
    """Blanking a ``<select>`` really does unset the link - "- none -" is not cosmetic."""
    assert dk_document_active_a.supplier_id is not None
    form = ProcurementDocumentForm(
        _dk_document_payload(title=dk_document_active_a.title, supplier=""),
        instance=dk_document_active_a, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.save().supplier_id is None


def test_dk_document_form_edit_cannot_move_a_row_into_another_workspace(tenant_a, tenant_b,
                                                                        dk_document_active_a):
    form = ProcurementDocumentForm(
        _dk_document_payload(title=dk_document_active_a.title, tenant=str(tenant_b.pk)),
        instance=dk_document_active_a, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.save().tenant_id == tenant_a.pk


def test_dk_policy_form_edit_keeps_its_own_pk_out_of_the_predecessor_list_only_on_edit(
        tenant_a, dk_policy_published_a):
    """On CREATE there is no pk to exclude, so every workspace policy is offered."""
    create = ProcurementPolicyForm(tenant=tenant_a)
    assert dk_policy_published_a.pk in _dk_pks(create, "previous_version")

    edit = ProcurementPolicyForm(instance=dk_policy_published_a, tenant=tenant_a)
    assert dk_policy_published_a.pk not in _dk_pks(edit, "previous_version")
