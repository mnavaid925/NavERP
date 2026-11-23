"""Unit and functional view tests for Sub-module 13.5 Metadata & Indexing."""
import pytest
from django.urls import reverse

from apps.documents.models.MetadataIndexing.MetadataSchemas import MetadataSchema
from apps.documents.models.MetadataIndexing.TaxonomyTerms import TaxonomyTerm
from apps.documents.models.MetadataIndexing.DocumentMetadataValues import DocumentMetadataValue
from apps.documents.models.MetadataIndexing.DocumentOcrJobs import DocumentOcrJob


@pytest.mark.django_db
def test_metadata_indexing_dashboard_view(client_a):
    """Test Metadata & Indexing dashboard renders 200 with aggregate metrics."""
    url = reverse("documents:metadata_indexing_dashboard")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "Metadata &amp; Indexing" in resp.content.decode() or "Metadata & Indexing" in resp.content.decode()


@pytest.mark.django_db
def test_metadata_indexing_schema_crud_views(client_a, tenant_a, metadata_schema):
    """Test MetadataSchema list, detail, create, edit, delete flow."""
    # List
    list_url = reverse("documents:metadata_schema_list")
    resp = client_a.get(list_url)
    assert resp.status_code == 200
    assert metadata_schema.name in resp.content.decode()

    # Detail
    detail_url = reverse("documents:metadata_schema_detail", args=[metadata_schema.pk])
    resp = client_a.get(detail_url)
    assert resp.status_code == 200
    assert metadata_schema.code in resp.content.decode()

    # Create
    create_url = reverse("documents:metadata_schema_create")
    resp = client_a.get(create_url)
    assert resp.status_code == 200

    resp_post = client_a.post(
        create_url,
        data={
            "name": "Invoice Tax Schema",
            "code": "TAX_INV_01",
            "target_type": "financial",
            "inheritance_mode": "none",
            "fields_definition_json": '[{"key": "tax_rate", "label": "Tax Rate", "data_type": "decimal"}]',
            "is_active": True,
        },
    )
    assert resp_post.status_code == 302
    created = MetadataSchema.objects.filter(tenant=tenant_a, code="TAX_INV_01").first()
    assert created is not None

    # Edit
    edit_url = reverse("documents:metadata_schema_edit", args=[created.pk])
    resp_edit = client_a.post(
        edit_url,
        data={
            "name": "Invoice Tax Schema Updated",
            "code": "TAX_INV_01",
            "target_type": "financial",
            "inheritance_mode": "none",
            "fields_definition_json": '[{"key": "tax_rate", "label": "Tax Rate", "data_type": "decimal"}]',
            "is_active": True,
        },
    )
    assert resp_edit.status_code == 302
    created.refresh_from_db()
    assert created.name == "Invoice Tax Schema Updated"

    # Delete (admin required)
    del_url = reverse("documents:metadata_schema_delete", args=[created.pk])
    resp_del = client_a.post(del_url)
    assert resp_del.status_code == 302
    assert not MetadataSchema.objects.filter(pk=created.pk).exists()


@pytest.mark.django_db
def test_metadata_indexing_taxonomy_term_views_and_tree(client_a, tenant_a, taxonomy_term, child_taxonomy_term):
    """Test TaxonomyTerm list, tree, detail, edit, and deletion protection."""
    # List
    resp = client_a.get(reverse("documents:taxonomy_term_list"))
    assert resp.status_code == 200
    assert taxonomy_term.name in resp.content.decode()

    # Tree
    tree_url = reverse("documents:taxonomy_term_tree")
    resp = client_a.get(tree_url)
    assert resp.status_code == 200
    assert taxonomy_term.name in resp.content.decode()
    assert child_taxonomy_term.name in resp.content.decode()

    # Detail
    detail_url = reverse("documents:taxonomy_term_detail", args=[taxonomy_term.pk])
    resp = client_a.get(detail_url)
    assert resp.status_code == 200
    assert taxonomy_term.term_code in resp.content.decode()

    # Attempt to delete parent with children -> must block deletion
    del_url = reverse("documents:taxonomy_term_delete", args=[taxonomy_term.pk])
    resp_del = client_a.post(del_url)
    assert resp_del.status_code == 302
    assert TaxonomyTerm.objects.filter(pk=taxonomy_term.pk).exists()

    # Delete leaf child term
    del_child_url = reverse("documents:taxonomy_term_delete", args=[child_taxonomy_term.pk])
    resp_del_child = client_a.post(del_child_url)
    assert resp_del_child.status_code == 302
    assert not TaxonomyTerm.objects.filter(pk=child_taxonomy_term.pk).exists()


@pytest.mark.django_db
def test_metadata_indexing_metadata_value_views(client_a, tenant_a, document, document_version, metadata_schema):
    """Test DocumentMetadataValue list, detail, create, edit, validate, and delete views."""
    # Create
    create_url = reverse("documents:metadata_value_create")
    resp = client_a.get(create_url)
    assert resp.status_code == 200

    resp_post = client_a.post(
        create_url,
        data={
            "document": document.pk,
            "version": document_version.pk,
            "schema": metadata_schema.pk,
            "field_name": "jurisdiction",
            "field_label": "Jurisdiction",
            "data_type": "text",
            "value_text": "Federal Circuit",
            "source": "manual_entry",
        },
    )
    assert resp_post.status_code == 302
    val = DocumentMetadataValue.objects.filter(tenant=tenant_a, field_name="jurisdiction").first()
    assert val is not None

    # Detail
    detail_url = reverse("documents:metadata_value_detail", args=[val.pk])
    resp = client_a.get(detail_url)
    assert resp.status_code == 200
    assert "Federal Circuit" in resp.content.decode()

    # Validate action
    val.validation_status = "pending_validation"
    val.save(update_fields=["validation_status"])
    val_url = reverse("documents:metadata_value_validate", args=[val.pk])
    resp_val = client_a.post(val_url)
    assert resp_val.status_code == 302
    val.refresh_from_db()
    assert val.validation_status == "valid"

    # Delete
    del_url = reverse("documents:metadata_value_delete", args=[val.pk])
    resp_del = client_a.post(del_url)
    assert resp_del.status_code == 302
    assert not DocumentMetadataValue.objects.filter(pk=val.pk).exists()


@pytest.mark.django_db
def test_metadata_indexing_ocr_job_views_and_actions(client_a, tenant_a, document, document_version):
    """Test DocumentOcrJob creation, detail, extraction viewer, process, and apply flow."""
    # Create OCR job
    create_url = reverse("documents:document_ocr_job_create")
    resp = client_a.get(create_url)
    assert resp.status_code == 200

    resp_post = client_a.post(
        create_url,
        data={
            "document": document.pk,
            "version": document_version.pk,
            "ocr_engine": "tesseract_ocr",
        },
    )
    assert resp_post.status_code == 302
    job = DocumentOcrJob.objects.filter(tenant=tenant_a, document=document).latest("created_at")
    assert job.status == "queued"

    # Detail view
    detail_url = reverse("documents:document_ocr_job_detail", args=[job.pk])
    resp = client_a.get(detail_url)
    assert resp.status_code == 200
    assert job.number in resp.content.decode()

    # Extract viewer
    viewer_url = reverse("documents:document_ocr_job_viewer", args=[job.pk])
    resp = client_a.get(viewer_url)
    assert resp.status_code == 200

    # Process action
    proc_url = reverse("documents:document_ocr_job_process", args=[job.pk])
    resp_proc = client_a.post(proc_url)
    assert resp_proc.status_code == 302
    job.refresh_from_db()
    assert job.status == "completed"
    assert job.extracted_full_text != ""

    # Apply action
    apply_url = reverse("documents:document_ocr_job_apply", args=[job.pk])
    resp_apply = client_a.post(apply_url)
    assert resp_apply.status_code == 302
    job.refresh_from_db()
    assert job.applied_to_document is True
    assert job.status == "reviewed"

    # Document version extracted text updated
    document_version.refresh_from_db()
    assert document_version.extracted_text == job.extracted_full_text
