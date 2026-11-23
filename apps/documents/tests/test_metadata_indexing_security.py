"""Security and multi-tenant isolation unit tests for Sub-module 13.5: Metadata & Indexing."""
import pytest
from django.urls import reverse

from apps.documents.models.MetadataIndexing.MetadataSchemas import MetadataSchema
from apps.documents.models.MetadataIndexing.TaxonomyTerms import TaxonomyTerm
from apps.documents.models.MetadataIndexing.DocumentMetadataValues import DocumentMetadataValue
from apps.documents.models.MetadataIndexing.DocumentOcrJobs import DocumentOcrJob


@pytest.mark.django_db
def test_metadata_indexing_unauthenticated_access_redirects(
    client, metadata_schema, taxonomy_term, document_metadata_value, document_ocr_job
):
    """Test that all Sub-module 13.5 endpoints redirect unauthenticated requests to login."""
    endpoints = [
        reverse("documents:metadata_indexing_dashboard"),
        reverse("documents:metadata_schema_list"),
        reverse("documents:metadata_schema_create"),
        reverse("documents:metadata_schema_detail", args=[metadata_schema.pk]),
        reverse("documents:metadata_schema_edit", args=[metadata_schema.pk]),
        reverse("documents:taxonomy_term_list"),
        reverse("documents:taxonomy_term_tree"),
        reverse("documents:taxonomy_term_create"),
        reverse("documents:taxonomy_term_detail", args=[taxonomy_term.pk]),
        reverse("documents:taxonomy_term_edit", args=[taxonomy_term.pk]),
        reverse("documents:metadata_value_list"),
        reverse("documents:metadata_value_create"),
        reverse("documents:metadata_value_detail", args=[document_metadata_value.pk]),
        reverse("documents:metadata_value_edit", args=[document_metadata_value.pk]),
        reverse("documents:document_ocr_job_list"),
        reverse("documents:document_ocr_job_create"),
        reverse("documents:document_ocr_job_detail", args=[document_ocr_job.pk]),
        reverse("documents:document_ocr_job_viewer", args=[document_ocr_job.pk]),
    ]
    for url in endpoints:
        res = client.get(url)
        assert res.status_code == 302, f"Expected 302 redirect for {url}, got {res.status_code}"
        assert "/login/" in res.headers["Location"]


@pytest.mark.django_db
def test_metadata_indexing_cross_tenant_idor_protection(
    client_b, metadata_schema, taxonomy_term, document_metadata_value, document_ocr_job
):
    """Test that cross-tenant access to Tenant A's objects by Tenant B returns 404."""
    # Metadata Schema IDOR
    assert client_b.get(reverse("documents:metadata_schema_detail", args=[metadata_schema.pk])).status_code == 404
    assert client_b.get(reverse("documents:metadata_schema_edit", args=[metadata_schema.pk])).status_code == 404
    assert client_b.post(reverse("documents:metadata_schema_delete", args=[metadata_schema.pk])).status_code == 404

    # Taxonomy Term IDOR
    assert client_b.get(reverse("documents:taxonomy_term_detail", args=[taxonomy_term.pk])).status_code == 404
    assert client_b.get(reverse("documents:taxonomy_term_edit", args=[taxonomy_term.pk])).status_code == 404
    assert client_b.post(reverse("documents:taxonomy_term_delete", args=[taxonomy_term.pk])).status_code == 404

    # Document Metadata Value IDOR
    assert client_b.get(reverse("documents:metadata_value_detail", args=[document_metadata_value.pk])).status_code == 404
    assert client_b.get(reverse("documents:metadata_value_edit", args=[document_metadata_value.pk])).status_code == 404
    assert client_b.post(reverse("documents:metadata_value_validate", args=[document_metadata_value.pk])).status_code == 404
    assert client_b.post(reverse("documents:metadata_value_delete", args=[document_metadata_value.pk])).status_code == 404

    # Document OCR Job IDOR
    assert client_b.get(reverse("documents:document_ocr_job_detail", args=[document_ocr_job.pk])).status_code == 404
    assert client_b.get(reverse("documents:document_ocr_job_viewer", args=[document_ocr_job.pk])).status_code == 404
    assert client_b.post(reverse("documents:document_ocr_job_process", args=[document_ocr_job.pk])).status_code == 404
    assert client_b.post(reverse("documents:document_ocr_job_apply", args=[document_ocr_job.pk])).status_code == 404
    assert client_b.post(reverse("documents:document_ocr_job_delete", args=[document_ocr_job.pk])).status_code == 404


@pytest.mark.django_db
def test_metadata_indexing_cross_tenant_list_isolation(
    client_b, metadata_schema, taxonomy_term, document_metadata_value, document_ocr_job
):
    """Test that list views strictly filter by tenant and never leak other tenants' records."""
    # Schema List
    resp = client_b.get(reverse("documents:metadata_schema_list"))
    assert resp.status_code == 200
    assert metadata_schema.name not in resp.content.decode()

    # Taxonomy Term List
    resp = client_b.get(reverse("documents:taxonomy_term_list"))
    assert resp.status_code == 200
    assert taxonomy_term.name not in resp.content.decode()

    # Metadata Value List
    resp = client_b.get(reverse("documents:metadata_value_list"))
    assert resp.status_code == 200
    assert document_metadata_value.field_name not in resp.content.decode()

    # OCR Job List
    resp = client_b.get(reverse("documents:document_ocr_job_list"))
    assert resp.status_code == 200
    assert document_ocr_job.number not in resp.content.decode()


@pytest.mark.django_db
def test_metadata_indexing_schema_deletion_admin_gate(member_client, metadata_schema):
    """Test that standard members are forbidden from deleting enterprise metadata schemas."""
    del_url = reverse("documents:metadata_schema_delete", args=[metadata_schema.pk])
    resp = member_client.post(del_url)
    assert resp.status_code == 302
    assert MetadataSchema.objects.filter(pk=metadata_schema.pk).exists()



@pytest.mark.django_db
def test_metadata_indexing_governed_taxonomy_term_protection(member_client, taxonomy_term):
    """Test that governed taxonomy terms cannot be deleted by standard non-admin users."""
    assert taxonomy_term.is_governed is True
    del_url = reverse("documents:taxonomy_term_delete", args=[taxonomy_term.pk])
    resp = member_client.post(del_url)
    assert resp.status_code == 302
    assert TaxonomyTerm.objects.filter(pk=taxonomy_term.pk).exists()


@pytest.mark.django_db
def test_metadata_indexing_document_checkout_lock_protection(
    member_client, document, document_lock, document_ocr_job, document_metadata_value
):
    """Test that actions affecting locked documents are blocked for non-custodians."""
    assert document.is_locked is True

    # 1. OCR Job apply blocked
    apply_url = reverse("documents:document_ocr_job_apply", args=[document_ocr_job.pk])
    resp_apply = member_client.post(apply_url)
    assert resp_apply.status_code == 302
    document_ocr_job.refresh_from_db()
    assert document_ocr_job.applied_to_document is False

    # 2. Metadata value create blocked
    create_url = reverse("documents:metadata_value_create")
    resp_create = member_client.post(
        create_url,
        data={
            "document": document.pk,
            "field_name": "tamper_key",
            "data_type": "text",
            "value_text": "hacked",
            "source": "manual_entry",
        },
    )
    assert resp_create.status_code in [200, 302]
    assert not DocumentMetadataValue.objects.filter(field_name="tamper_key").exists()

    # 3. Metadata value edit blocked
    edit_url = reverse("documents:metadata_value_edit", args=[document_metadata_value.pk])
    resp_edit = member_client.post(
        edit_url,
        data={
            "document": document.pk,
            "field_name": document_metadata_value.field_name,
            "data_type": "text",
            "value_text": "tampered",
            "source": "manual_entry",
        },
    )
    assert resp_edit.status_code == 302
    document_metadata_value.refresh_from_db()
    assert document_metadata_value.value_text != "tampered"

    # 4. Metadata value delete blocked
    del_url = reverse("documents:metadata_value_delete", args=[document_metadata_value.pk])
    resp_del = member_client.post(del_url)
    assert resp_del.status_code == 302
    assert DocumentMetadataValue.objects.filter(pk=document_metadata_value.pk).exists()
