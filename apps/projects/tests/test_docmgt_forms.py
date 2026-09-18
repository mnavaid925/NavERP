"""Projects 7.10 — Document & Knowledge Management form tests.

Covers ``TenantModelForm`` scoping, ``_reject_foreign``, upload validation, the checkout lock,
and the edit-time disabled fields.

Naming: every test ``test_docmgt_*``, every helper ``_docmgt_*``.
"""
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.projects.forms.DocumentKnowledgeManagement.Documents import ProjectDocumentForm
from apps.projects.forms.DocumentKnowledgeManagement.ProjectFolders import ProjectFolderForm
from apps.projects.forms.DocumentKnowledgeManagement.Revisions import ProjectDocumentRevisionUploadForm
from apps.projects.models import ProjectDocument, ProjectFolder


# ==================================================================================================
# Tenant scoping — FK dropdowns contain only the request tenant
# ==================================================================================================

def test_docmgt_document_form_scopes_folder_to_project(db, tenant_a, planning_project_a,
                                                        docmgt_folder_root_a):
    form = ProjectDocumentForm(tenant=tenant_a, project_id=planning_project_a.pk)
    folder_pks = list(form.fields["folder"].queryset.values_list("pk", flat=True))
    assert docmgt_folder_root_a.pk in folder_pks


def test_docmgt_folder_form_scopes_parent_to_project(db, tenant_a, planning_project_a,
                                                      docmgt_folder_root_a):
    form = ProjectFolderForm(tenant=tenant_a, project_id=planning_project_a.pk)
    parent_pks = list(form.fields["parent"].queryset.values_list("pk", flat=True))
    assert docmgt_folder_root_a.pk in parent_pks


def test_docmgt_folder_form_rejects_foreign_project(db, tenant_a, planning_project_b):
    form = ProjectFolderForm(tenant=tenant_a, data={"project": planning_project_b.pk, "name": "Hack", "sequence": 1})
    assert not form.is_valid()
    assert "project" in form.errors


def test_docmgt_document_form_rejects_foreign_folder(db, tenant_a, planning_project_a, docmgt_folder_root_b):
    form = ProjectDocumentForm(
        tenant=tenant_a, project_id=planning_project_a.pk,
        data={"project": planning_project_a.pk, "folder": docmgt_folder_root_b.pk, "title": "Test",
              "document_type": "charter", "classification": "internal", "status": "draft"}
    )
    assert not form.is_valid()
    assert "folder" in form.errors


# ==================================================================================================
# Upload validation
# ==================================================================================================

def test_docmgt_upload_rejects_exe(db):
    from apps.projects.models.DocumentKnowledgeManagement.Documents import validate_upload
    f = SimpleUploadedFile("x.exe", b"x")
    assert validate_upload(f) is not None


def test_docmgt_upload_rejects_no_extension(db):
    from apps.projects.models.DocumentKnowledgeManagement.Documents import validate_upload
    f = SimpleUploadedFile("x", b"x")
    assert validate_upload(f) is not None


def test_docmgt_upload_rejects_svg(db):
    from apps.projects.models.DocumentKnowledgeManagement.Documents import validate_upload
    f = SimpleUploadedFile("x.svg", b"<svg/>")
    assert validate_upload(f) is not None


def test_docmgt_upload_accepts_txt(db):
    from apps.projects.models.DocumentKnowledgeManagement.Documents import validate_upload
    f = SimpleUploadedFile("x.txt", b"x")
    assert validate_upload(f) is None


# ==================================================================================================
# Checkout lock
# ==================================================================================================

def test_docmgt_upload_form_rejects_checked_out_document(db, tenant_a, planning_project_a,
                                                          admin_user, docmgt_folder_root_a):
    doc = ProjectDocument.objects.create(
        tenant=tenant_a, project=planning_project_a, folder=docmgt_folder_root_a,
        title="Locked", document_type="charter", status="draft",
        is_checked_out=True, checked_out_by=admin_user)
    form = ProjectDocumentRevisionUploadForm(
        tenant=tenant_a, document=doc, data={"change_note": "x"},
        files={"file": SimpleUploadedFile("x.txt", b"x")})
    assert not form.is_valid()
    assert "file" in form.errors


# ==================================================================================================
# Edit-time disabled fields
# ==================================================================================================

def test_docmgt_document_form_project_disabled_on_edit(db, tenant_a, planning_project_a,
                                                        docmgt_document_draft_a):
    form = ProjectDocumentForm(tenant=tenant_a, project_id=planning_project_a.pk,
                               instance=docmgt_document_draft_a)
    assert form.fields["project"].disabled is True


# ==================================================================================================
# Folder parent — self excluded, cycle refused
# ==================================================================================================

def test_docmgt_folder_form_excludes_self_from_parent(db, tenant_a, planning_project_a,
                                                       docmgt_folder_root_a):
    form = ProjectFolderForm(tenant=tenant_a, project_id=planning_project_a.pk,
                             instance=docmgt_folder_root_a)
    assert docmgt_folder_root_a.pk not in \
           list(form.fields["parent"].queryset.values_list("pk", flat=True))
