"""Projects 7.10 — Document & Knowledge Management model tests.

7.10 adds five entity files carrying FIVE tables: ``ProjectFolder`` [PFD-],
``ProjectDocument`` [PDM-], ``ProjectDocumentRevision`` (not numbered), ``DocumentTemplate`` [DTM-],
and ``KnowledgeEntry`` [KNE-]. These tests pin the model surface the views and forms present:
the numbering, the ``clean()`` invariants, the ``unique_together`` constraints, the derived
properties, and the declared ordering/indexes.

Naming: every test ``test_docmgt_*``, every helper ``_docmgt_*``.
"""
import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.projects.models import (
    DocumentTemplate,
    KnowledgeEntry,
    ProjectDocument,
    ProjectDocumentRevision,
    ProjectFolder,
)
from apps.projects.tests.conftest import (
    _docmgt_document,
    _docmgt_folder,
    _docmgt_knowledge,
    _docmgt_revision,
    _docmgt_template,
)

_NUMBERED_MODELS = [
    (ProjectFolder, "PFD"),
    (ProjectDocument, "PDM"),
    (DocumentTemplate, "DTM"),
    (KnowledgeEntry, "KNE"),
]


# ==================================================================================================
# Numbering — the prefix is the model's identity in the UI
# ==================================================================================================

@pytest.mark.parametrize("model,prefix", _NUMBERED_MODELS)
def test_docmgt_number_prefix_is_pinned(db, model, prefix):
    assert model.NUMBER_PREFIX == prefix


def test_docmgt_revision_is_not_numbered(db):
    assert not hasattr(ProjectDocumentRevision, "NUMBER_PREFIX")
    assert not hasattr(ProjectDocumentRevision, "number")


def test_docmgt_numbers_are_per_tenant_not_global(db, tenant_a, tenant_b,
                                                  planning_project_a, planning_project_b):
    a = _docmgt_folder(tenant_a, planning_project_a, name="Per-tenant A")
    b = _docmgt_folder(tenant_b, planning_project_b, name="Per-tenant B")
    assert a.number == b.number


def test_docmgt_number_is_never_blank_and_never_duplicated(db, tenant_a, planning_project_a):
    for _ in range(3):
        _docmgt_folder(tenant_a, planning_project_a, name=f"Dup guard {_}")
    numbers = list(ProjectFolder.objects.values_list("number", flat=True))
    assert "" not in numbers
    assert len(numbers) == len(set(numbers))


def test_docmgt_no_prefix_collision(db):
    from django.apps import apps
    projects_app = apps.get_app_config("projects")
    prefixes = {}
    for model in projects_app.get_models():
        prefix = getattr(model, "NUMBER_PREFIX", None)
        if prefix:
            if prefix in prefixes:
                assert prefixes[prefix] == model.__name__, (
                    f"Prefix collision: {prefix} used by {prefixes[prefix]} and {model.__name__}"
                )
            prefixes[prefix] = model.__name__
    assert prefixes["PFD"] == "ProjectFolder"
    assert prefixes["PDM"] == "ProjectDocument"
    assert prefixes["DTM"] == "DocumentTemplate"
    assert prefixes["KNE"] == "KnowledgeEntry"


# ==================================================================================================
# ProjectFolder — tree, cycle guard, duplicate root, full_path
# ==================================================================================================

def test_docmgt_folder_mints_a_pfd_number(db, docmgt_folder_root_a):
    assert docmgt_folder_root_a.number.startswith("PFD-")


def test_docmgt_folder_cycle_guard_rejects_descendant_parent(db, tenant_a, planning_project_a,
                                                             docmgt_folder_root_a,
                                                             docmgt_folder_child_a):
    """A folder cannot be moved inside its own subtree."""
    docmgt_folder_root_a.parent = docmgt_folder_child_a
    with pytest.raises(ValidationError) as exc:
        docmgt_folder_root_a.full_clean(exclude=["number"])
    assert "parent" in exc.value.message_dict


def test_docmgt_folder_is_descendant_of_returns_true_for_child(db, docmgt_folder_root_a,
                                                                docmgt_folder_child_a):
    assert docmgt_folder_root_a._is_descendant_of(docmgt_folder_child_a) is True


def test_docmgt_folder_duplicate_root_name_rejected(db, tenant_a, planning_project_a,
                                                     docmgt_folder_root_a):
    """Two root folders with the same name in one project are forbidden."""
    dup = ProjectFolder(tenant=tenant_a, project=planning_project_a,
                        parent=None, name=docmgt_folder_root_a.name, sequence=9)
    with pytest.raises(ValidationError) as exc:
        dup.full_clean(exclude=["number"])
    assert "name" in exc.value.message_dict


def test_docmgt_folder_cross_project_parent_rejected(db, tenant_a, tenant_b,
                                                      planning_project_a, planning_project_b):
    root_b = _docmgt_folder(tenant_b, planning_project_b, name="Globex root")
    child = ProjectFolder(tenant=tenant_a, project=planning_project_a,
                          parent=root_b, name="Orphan", sequence=1)
    with pytest.raises(ValidationError) as exc:
        child.full_clean(exclude=["number"])
    assert "parent" in exc.value.message_dict


def test_docmgt_folder_full_path_root_is_name(db, docmgt_folder_root_a):
    assert docmgt_folder_root_a.full_path == docmgt_folder_root_a.name


def test_docmgt_folder_full_path_child_includes_parent(db, docmgt_folder_root_a,
                                                        docmgt_folder_child_a):
    assert docmgt_folder_child_a.full_path == f"{docmgt_folder_root_a.name} / {docmgt_folder_child_a.name}"


# ==================================================================================================
# ProjectDocument — held+archived, current_revision, latest_revision
# ==================================================================================================

def test_docmgt_document_mints_a_pdm_number(db, docmgt_document_draft_a):
    assert docmgt_document_draft_a.number.startswith("PDM-")


def test_docmgt_document_held_and_archived_rejected(db, tenant_a, planning_project_a,
                                                     docmgt_folder_root_a):
    doc = ProjectDocument(tenant=tenant_a, project=planning_project_a,
                          folder=docmgt_folder_root_a,
                          title="Test", is_legal_hold=True,
                          is_archived=True)
    with pytest.raises(ValidationError) as exc:
        doc.full_clean(exclude=["number"])
    assert "is_archived" in exc.value.message_dict or "__all__" in exc.value.message_dict


def test_docmgt_document_current_revision_matches_pointer(db, tenant_a, planning_project_a,
                                                           docmgt_folder_root_a, admin_user):
    doc = _docmgt_document(tenant_a, planning_project_a, docmgt_folder_root_a,
                           status="approved", current_revision_no=1)
    rev1 = _docmgt_revision(tenant_a, doc, is_approved=True, approved_by=admin_user)
    _docmgt_revision(tenant_a, doc, is_approved=True, approved_by=admin_user)
    # current_revision should return rev1 because current_revision_no == 1
    assert doc.current_revision.pk == rev1.pk


def test_docmgt_document_latest_revision_is_highest_number(db, tenant_a, planning_project_a,
                                                            docmgt_folder_root_a, admin_user):
    doc = _docmgt_document(tenant_a, planning_project_a, docmgt_folder_root_a,
                           status="approved", current_revision_no=1)
    _docmgt_revision(tenant_a, doc, is_approved=True, approved_by=admin_user)
    rev2 = _docmgt_revision(tenant_a, doc, is_approved=True, approved_by=admin_user)
    assert doc.latest_revision.pk == rev2.pk


def test_docmgt_document_expected_status_passes(db, tenant_a, planning_project_a,
                                                docmgt_folder_root_a):
    doc = ProjectDocument(tenant=tenant_a, project=planning_project_a,
                          folder=docmgt_folder_root_a,
                          title="Expected Slot", status="expected")
    doc.full_clean(exclude=["number"])
    doc.save()
    assert doc.pk is not None


def test_docmgt_document_share_register_url_is_hardcoded_string(db, docmgt_document_draft_a):
    url = docmgt_document_draft_a.share_register_url
    assert isinstance(url, str)
    assert url.startswith("/projects/shared-documents/")
    assert f"?project={docmgt_document_draft_a.project_id}" in url


# ==================================================================================================
# ProjectDocumentRevision — numbering, checksum, is_current, clean hold
# ==================================================================================================

def test_docmgt_revision_auto_allocates_revision_no(db, tenant_a, planning_project_a,
                                                     docmgt_folder_root_a):
    doc = _docmgt_document(tenant_a, planning_project_a, docmgt_folder_root_a)
    r1 = _docmgt_revision(tenant_a, doc)
    r2 = _docmgt_revision(tenant_a, doc)
    assert r1.revision_no == 1
    assert r2.revision_no == 2


def test_docmgt_revision_checksum_computed_from_file(db, docmgt_revision_pending_a):
    assert docmgt_revision_pending_a.checksum
    assert len(docmgt_revision_pending_a.checksum) == 64  # sha256 hex


def test_docmgt_revision_is_current_matches_pointer(db, tenant_a, planning_project_a,
                                                     docmgt_folder_root_a, admin_user):
    doc = _docmgt_document(tenant_a, planning_project_a, docmgt_folder_root_a,
                           status="approved", current_revision_no=1)
    r1 = _docmgt_revision(tenant_a, doc, is_approved=True, approved_by=admin_user)
    r2 = _docmgt_revision(tenant_a, doc, is_approved=True, approved_by=admin_user)
    assert r1.is_current is True
    assert r2.is_current is False


def test_docmgt_revision_clean_rejects_held_document(db, tenant_a, planning_project_a,
                                                      docmgt_folder_root_a):
    from django.core.files.uploadedfile import SimpleUploadedFile
    doc = _docmgt_document(tenant_a, planning_project_a, docmgt_folder_root_a,
                           is_legal_hold=True, hold_reason="Litigation.")
    rev = ProjectDocumentRevision(tenant=tenant_a, document=doc, is_approved=True,
                                  file=SimpleUploadedFile("rev.txt", b"content"),
                                  change_note="Should fail.")
    with pytest.raises(ValidationError) as exc:
        rev.full_clean()
    assert "document" in exc.value.message_dict or "is_approved" in exc.value.message_dict


# ==================================================================================================
# DocumentTemplate — numbering, active/retired
# ==================================================================================================

def test_docmgt_template_mints_a_dtm_number(db, docmgt_template_active_a):
    assert docmgt_template_active_a.number.startswith("DTM-")


def test_docmgt_template_is_active_defaults_true(db, tenant_a):
    t = _docmgt_template(tenant_a)
    assert t.is_active is True


# ==================================================================================================
# KnowledgeEntry — numbering, publish/retired, featured
# ==================================================================================================

def test_docmgt_knowledge_mints_a_kne_number(db, docmgt_knowledge_draft_a):
    assert docmgt_knowledge_draft_a.number.startswith("KNE-")


def test_docmgt_knowledge_retired_and_featured_rejected(db, tenant_a):
    entry = KnowledgeEntry(tenant=tenant_a, title="Retired", summary="Retired summary",
                           status="retired", is_featured=True, kind="lesson_learned")
    with pytest.raises(ValidationError) as exc:
        entry.full_clean(exclude=["number"])
    assert "__all__" in exc.value.message_dict or "is_featured" in exc.value.message_dict


def test_docmgt_knowledge_published_empty_title_rejected(db, tenant_a):
    entry = KnowledgeEntry(tenant=tenant_a, status="published", title="",
                           kind="lesson_learned")
    with pytest.raises(ValidationError) as exc:
        entry.full_clean(exclude=["number"])
    assert "title" in exc.value.message_dict


def test_docmgt_folder_status_css(db, docmgt_folder_root_a):
    assert docmgt_folder_root_a.status_css == "badge-green"
    docmgt_folder_root_a.is_archived = True
    assert docmgt_folder_root_a.status_css == "badge-muted"


def test_docmgt_revision_is_editable_is_always_false(db, docmgt_revision_pending_a):
    assert docmgt_revision_pending_a.is_editable is False


def test_docmgt_revision_clean_rejects_approval_on_archived_doc(db, tenant_a, planning_project_a,
                                                               docmgt_folder_root_a, admin_user):
    doc = _docmgt_document(tenant_a, planning_project_a, docmgt_folder_root_a,
                           is_archived=True, status="archived")
    rev = ProjectDocumentRevision(tenant=tenant_a, document=doc, is_approved=True,
                                  approved_by=admin_user, revision_no=2)
    with pytest.raises(ValidationError) as exc:
        rev.full_clean()
    assert "is_approved" in exc.value.message_dict


def test_docmgt_folder_hierarchy_max_depth(db, tenant_a, planning_project_a):
    parent = None
    for i in range(20):
        parent = _docmgt_folder(tenant_a, planning_project_a, name=f"Level_{i}", parent=parent)
    too_deep = ProjectFolder(tenant=tenant_a, project=planning_project_a, parent=parent,
                             name="Level_21")
    with pytest.raises(ValidationError) as exc:
        too_deep.full_clean(exclude=["number"])
    assert "parent" in exc.value.message_dict

