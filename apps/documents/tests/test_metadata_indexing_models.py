"""Unit tests for Sub-module 13.5 Metadata & Indexing models."""
import json
import pytest
from django.db import IntegrityError

from apps.documents.models.MetadataIndexing.MetadataSchemas import MetadataSchema
from apps.documents.models.MetadataIndexing.DocumentMetadataValues import DocumentMetadataValue
from apps.documents.models.MetadataIndexing.TaxonomyTerms import TaxonomyTerm
from apps.documents.models.MetadataIndexing.DocumentOcrJobs import DocumentOcrJob


@pytest.mark.django_db
def test_metadata_indexing_schema_numbering_and_str(tenant_a, admin_user):
    """Test MetadataSchema auto-numbering with prefix DSCH- and string representation."""
    schema = MetadataSchema.objects.create(
        tenant=tenant_a,
        name="HR Onboarding Form",
        code="hr_onboard",
        target_type="document_type",
        fields_definition_json='[{"name": "employee_id", "type": "text", "required": true}]',
        created_by=admin_user,
    )
    assert schema.number.startswith("DSCH-")
    assert schema.code == "HR_ONBOARD"  # Normalization to uppercase in save()
    assert str(schema) == "HR Onboarding Form (HR_ONBOARD)"


@pytest.mark.django_db
def test_metadata_indexing_schema_parsed_fields(tenant_a, admin_user):
    """Test MetadataSchema.parsed_fields property with valid and corrupt JSON."""
    schema = MetadataSchema.objects.create(
        tenant=tenant_a,
        name="Invoice Schema",
        code="INV_SCHEMA",
        fields_definition_json='[{"name": "tax_id", "type": "text"}, {"name": "amount", "type": "decimal"}]',
        created_by=admin_user,
    )
    fields = schema.parsed_fields
    assert len(fields) == 2
    assert fields[0]["name"] == "tax_id"

    # Test invalid JSON fallback
    schema.fields_definition_json = "not-a-valid-json"
    assert schema.parsed_fields == []


@pytest.mark.django_db
def test_metadata_indexing_schema_uniqueness_per_tenant(tenant_a, admin_user):
    """Test MetadataSchema enforces unique code per tenant."""
    MetadataSchema.objects.create(
        tenant=tenant_a,
        name="Contract Standard",
        code="CONTRACT",
        created_by=admin_user,
    )
    with pytest.raises(IntegrityError):
        MetadataSchema.objects.create(
            tenant=tenant_a,
            name="Contract Duplicate",
            code="CONTRACT",
            created_by=admin_user,
        )


@pytest.mark.django_db
def test_metadata_indexing_taxonomy_term_numbering_and_str(tenant_a, admin_user):
    """Test TaxonomyTerm auto-numbering with prefix DTAX- and string representation."""
    term = TaxonomyTerm.objects.create(
        tenant=tenant_a,
        name="Medical Device Regulation",
        term_code="MDR-EU",
        category="compliance",
        created_by=admin_user,
    )
    assert term.number.startswith("DTAX-")
    assert str(term) == "Medical Device Regulation [MDR-EU]"


@pytest.mark.django_db
def test_metadata_indexing_taxonomy_term_hierarchy_and_active_children(
    tenant_a, admin_user, taxonomy_term, child_taxonomy_term
):
    """Test TaxonomyTerm parent-child relationship and active_children property."""
    assert child_taxonomy_term.parent == taxonomy_term
    active_kids = list(taxonomy_term.active_children)
    assert child_taxonomy_term in active_kids


@pytest.mark.django_db
def test_metadata_indexing_taxonomy_term_parsed_synonyms(tenant_a, admin_user):
    """Test TaxonomyTerm.parsed_synonyms property with valid JSON and invalid fallback."""
    term = TaxonomyTerm.objects.create(
        tenant=tenant_a,
        name="Artificial Intelligence",
        term_code="AI-ML",
        category="technical",
        synonyms_json='["machine learning", "deep learning", "nlp"]',
        created_by=admin_user,
    )
    synonyms = term.parsed_synonyms
    assert len(synonyms) == 3
    assert "machine learning" in synonyms

    term.synonyms_json = "invalid-json"
    assert term.parsed_synonyms == []


@pytest.mark.django_db
def test_metadata_indexing_taxonomy_term_unique_category_code(tenant_a, admin_user):
    """Test TaxonomyTerm enforces unique (tenant, category, term_code)."""
    TaxonomyTerm.objects.create(
        tenant=tenant_a,
        name="Energy Sector",
        term_code="NRG",
        category="industry",
        created_by=admin_user,
    )
    with pytest.raises(IntegrityError):
        TaxonomyTerm.objects.create(
            tenant=tenant_a,
            name="Renewable Energy",
            term_code="NRG",
            category="industry",
            created_by=admin_user,
        )


@pytest.mark.django_db
def test_metadata_indexing_document_metadata_value_numbering_and_str(
    tenant_a, document, document_version, metadata_schema
):
    """Test DocumentMetadataValue auto-numbering with prefix DMETA- and string representation."""
    val = DocumentMetadataValue.objects.create(
        tenant=tenant_a,
        document=document,
        version=document_version,
        schema=metadata_schema,
        field_name="vendor_name",
        field_label="Vendor Name",
        data_type="text",
        value_text="Acme Supplies Ltd",
        source="manual_entry",
    )
    assert val.number.startswith("DMETA-")
    assert "vendor_name = Acme Supplies Ltd" in str(val)


@pytest.mark.django_db
def test_metadata_indexing_document_metadata_value_display_value(
    tenant_a, document, document_version, metadata_schema
):
    """Test DocumentMetadataValue.display_value across different data types."""
    # Decimal
    val_num = DocumentMetadataValue.objects.create(
        tenant=tenant_a,
        document=document,
        version=document_version,
        schema=metadata_schema,
        field_name="total_amount",
        data_type="decimal",
        value_number=4500.50,
    )
    assert "4500.5" in val_num.display_value

    # Boolean
    val_bool = DocumentMetadataValue.objects.create(
        tenant=tenant_a,
        document=document,
        version=document_version,
        schema=metadata_schema,
        field_name="is_confidential",
        data_type="boolean",
        value_boolean=True,
    )
    assert val_bool.display_value == "Yes"

    # JSON
    val_json = DocumentMetadataValue.objects.create(
        tenant=tenant_a,
        document=document,
        version=document_version,
        schema=metadata_schema,
        field_name="custom_payload",
        data_type="json",
        value_json='{"status": "ok"}',
    )
    assert '{"status": "ok"}' in val_json.display_value


@pytest.mark.django_db
def test_metadata_indexing_document_metadata_value_unique_version(
    tenant_a, document, document_version, metadata_schema
):
    """Test DocumentMetadataValue enforces uniqueness per (tenant, document, version, field_name)."""
    DocumentMetadataValue.objects.create(
        tenant=tenant_a,
        document=document,
        version=document_version,
        schema=metadata_schema,
        field_name="contract_clause",
        data_type="text",
        value_text="Clause A",
    )
    with pytest.raises(IntegrityError):
        DocumentMetadataValue.objects.create(
            tenant=tenant_a,
            document=document,
            version=document_version,
            schema=metadata_schema,
            field_name="contract_clause",
            data_type="text",
            value_text="Clause Duplicate",
        )


@pytest.mark.django_db
def test_metadata_indexing_document_metadata_value_unique_null_version(
    tenant_a, document, metadata_schema
):
    """Test DocumentMetadataValue enforces uniqueness per (tenant, document, field_name) when version is NULL."""
    DocumentMetadataValue.objects.create(
        tenant=tenant_a,
        document=document,
        version=None,
        schema=metadata_schema,
        field_name="global_department",
        data_type="text",
        value_text="Legal",
    )
    with pytest.raises(IntegrityError):
        DocumentMetadataValue.objects.create(
            tenant=tenant_a,
            document=document,
            version=None,
            schema=metadata_schema,
            field_name="global_department",
            data_type="text",
            value_text="Legal Duplicate",
        )


@pytest.mark.django_db
def test_metadata_indexing_ocr_job_numbering_and_str(tenant_a, admin_user, document, document_version):
    """Test DocumentOcrJob auto-numbering with prefix DOCR- and string representation."""
    job = DocumentOcrJob.objects.create(
        tenant=tenant_a,
        document=document,
        version=document_version,
        ocr_engine="tesseract_ocr",
        status="queued",
        created_by=admin_user,
    )
    assert job.number.startswith("DOCR-")
    assert f"[{job.number}]" in str(job)


@pytest.mark.django_db
def test_metadata_indexing_ocr_job_parsed_tags(tenant_a, admin_user, document, document_version):
    """Test DocumentOcrJob.parsed_tags property with valid and fallback JSON."""
    job = DocumentOcrJob.objects.create(
        tenant=tenant_a,
        document=document,
        version=document_version,
        ocr_engine="tesseract_ocr",
        status="completed",
        suggested_tags_json='["invoice", "procurement", "q4"]',
        created_by=admin_user,
    )
    tags = job.parsed_tags
    assert len(tags) == 3
    assert "invoice" in tags

    job.suggested_tags_json = "malformed"
    assert job.parsed_tags == []

