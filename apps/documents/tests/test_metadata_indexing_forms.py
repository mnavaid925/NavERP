"""Unit tests for Sub-module 13.5 Metadata & Indexing forms."""
import json
import pytest

from apps.documents.forms.MetadataIndexing.MetadataSchemas import MetadataSchemaForm
from apps.documents.forms.MetadataIndexing.TaxonomyTerms import TaxonomyTermForm
from apps.documents.forms.MetadataIndexing.DocumentMetadataValues import DocumentMetadataValueForm
from apps.documents.forms.MetadataIndexing.DocumentOcrJobs import DocumentOcrJobForm
from apps.documents.models.MetadataIndexing.MetadataSchemas import MetadataSchema
from apps.documents.models.MetadataIndexing.TaxonomyTerms import TaxonomyTerm
from apps.documents.models.MetadataIndexing.DocumentMetadataValues import DocumentMetadataValue


@pytest.mark.django_db
def test_metadata_indexing_schema_form_excluded_system_fields():
    """Verify system-managed fields are excluded from MetadataSchemaForm (mass-assignment protection)."""
    form = MetadataSchemaForm()
    for field in ["tenant", "number", "created_at", "updated_at", "created_by"]:
        assert field not in form.fields, f"Security violation: {field} exposed in form"


@pytest.mark.django_db
def test_metadata_indexing_schema_form_valid(tenant_a):
    """Test MetadataSchemaForm with valid input data."""
    form = MetadataSchemaForm(
        tenant=tenant_a,
        data={
            "name": "Procurement Contract Specs",
            "code": "proc_specs",
            "target_type": "contract",
            "inheritance_mode": "none",
            "fields_definition_json": '[{"key": "vendor_tax_id", "label": "Vendor Tax ID", "data_type": "text"}]',
            "is_active": True,
        },
    )
    assert form.is_valid(), form.errors
    assert form.cleaned_data["code"] == "PROC_SPECS"


@pytest.mark.django_db
def test_metadata_indexing_schema_form_duplicate_code_rejected(tenant_a, admin_user, metadata_schema):
    """Test MetadataSchemaForm rejects duplicate schema code on same tenant."""
    form = MetadataSchemaForm(
        tenant=tenant_a,
        data={
            "name": "Duplicate Schema",
            "code": metadata_schema.code,  # CONTRACT_V1
            "target_type": "contract",
            "inheritance_mode": "none",
            "fields_definition_json": "[]",
        },
    )
    assert not form.is_valid()
    assert "code" in form.errors


@pytest.mark.django_db
def test_metadata_indexing_schema_form_fields_json_validation(tenant_a):
    """Test MetadataSchemaForm fields_definition_json validation rules."""
    # Malformed JSON
    form_invalid_json = MetadataSchemaForm(
        tenant=tenant_a,
        data={"name": "Bad Schema", "code": "BAD1", "fields_definition_json": "{not valid json}"},
    )
    assert not form_invalid_json.is_valid()
    assert "fields_definition_json" in form_invalid_json.errors

    # JSON is dict instead of list
    form_dict_json = MetadataSchemaForm(
        tenant=tenant_a,
        data={"name": "Dict Schema", "code": "BAD2", "fields_definition_json": '{"key": "test"}'},
    )
    assert not form_dict_json.is_valid()
    assert "fields_definition_json" in form_dict_json.errors

    # Field item missing 'key'
    form_missing_key = MetadataSchemaForm(
        tenant=tenant_a,
        data={"name": "No Key Schema", "code": "BAD3", "fields_definition_json": '[{"label": "Just Label"}]'},
    )
    assert not form_missing_key.is_valid()
    assert "fields_definition_json" in form_missing_key.errors


@pytest.mark.django_db
def test_metadata_indexing_taxonomy_term_form_excluded_system_fields():
    """Verify system-managed fields are excluded from TaxonomyTermForm."""
    form = TaxonomyTermForm()
    for field in ["tenant", "number", "created_at", "updated_at", "created_by"]:
        assert field not in form.fields, f"Security violation: {field} exposed in form"


@pytest.mark.django_db
def test_metadata_indexing_taxonomy_term_form_duplicate_code_in_category(tenant_a, taxonomy_term):
    """Test TaxonomyTermForm rejects duplicate term_code in same category."""
    form = TaxonomyTermForm(
        tenant=tenant_a,
        data={
            "name": "Duplicate Finance Term",
            "term_code": taxonomy_term.term_code,  # FIN-SERV
            "category": taxonomy_term.category,    # industry
            "is_active": True,
        },
    )
    assert not form.is_valid()
    assert "term_code" in form.errors


@pytest.mark.django_db
def test_metadata_indexing_taxonomy_term_form_synonyms_parsing(tenant_a):
    """Test TaxonomyTermForm parses comma-separated list and JSON list, rejecting JSON objects."""
    # Comma-separated
    form_csv = TaxonomyTermForm(
        tenant=tenant_a,
        data={
            "name": "Legal Term",
            "term_code": "LEG-01",
            "category": "legal",
            "synonyms_json": "NDA, Confidentiality Agreement, MNDA",
        },
    )
    assert form_csv.is_valid(), form_csv.errors
    parsed = json.loads(form_csv.cleaned_data["synonyms_json"])
    assert len(parsed) == 3
    assert "MNDA" in parsed

    # JSON Object rejection
    form_obj = TaxonomyTermForm(
        tenant=tenant_a,
        data={
            "name": "Object Term",
            "term_code": "LEG-02",
            "category": "legal",
            "synonyms_json": '{"term": "NDA"}',
        },
    )
    assert not form_obj.is_valid()
    assert "synonyms_json" in form_obj.errors


@pytest.mark.django_db
def test_metadata_indexing_taxonomy_term_form_circular_hierarchy(tenant_a, taxonomy_term, child_taxonomy_term):
    """Test TaxonomyTermForm detects and blocks circular parent-child assignment."""
    # Cannot set parent to itself
    form_self = TaxonomyTermForm(
        tenant=tenant_a,
        instance=taxonomy_term,
        data={
            "name": taxonomy_term.name,
            "term_code": taxonomy_term.term_code,
            "category": taxonomy_term.category,
            "parent": taxonomy_term.pk,
        },
    )
    assert not form_self.is_valid()
    assert "parent" in form_self.errors

    # Cannot set parent to child (creating a loop)
    form_loop = TaxonomyTermForm(
        tenant=tenant_a,
        instance=taxonomy_term,
        data={
            "name": taxonomy_term.name,
            "term_code": taxonomy_term.term_code,
            "category": taxonomy_term.category,
            "parent": child_taxonomy_term.pk,
        },
    )
    assert not form_loop.is_valid()
    assert "parent" in form_loop.errors


@pytest.mark.django_db
def test_metadata_indexing_metadata_value_form_excluded_fields():
    """Verify system fields including validation_status are excluded from DocumentMetadataValueForm."""
    form = DocumentMetadataValueForm()
    for field in ["tenant", "number", "validation_status", "validation_error", "created_at", "updated_at"]:
        assert field not in form.fields, f"Security violation: {field} exposed in form"


@pytest.mark.django_db
def test_metadata_indexing_metadata_value_form_valid(tenant_a, document, document_version, metadata_schema):
    """Test DocumentMetadataValueForm with valid text input."""
    form = DocumentMetadataValueForm(
        tenant=tenant_a,
        data={
            "document": document.pk,
            "version": document_version.pk,
            "schema": metadata_schema.pk,
            "field_name": "contract_governing_law",
            "field_label": "Governing Law",
            "data_type": "text",
            "value_text": "State of New York",
            "source": "manual_entry",
        },
    )
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_metadata_indexing_metadata_value_form_json_validation(tenant_a, document, document_version):
    """Test DocumentMetadataValueForm requires valid JSON payload when data_type is 'json'."""
    # Missing payload
    form_missing = DocumentMetadataValueForm(
        tenant=tenant_a,
        data={
            "document": document.pk,
            "field_name": "specs",
            "data_type": "json",
            "value_json": "",
            "source": "manual_entry",
        },
    )
    assert not form_missing.is_valid()
    assert "value_json" in form_missing.errors

    # Malformed JSON
    form_bad = DocumentMetadataValueForm(
        tenant=tenant_a,
        data={
            "document": document.pk,
            "field_name": "specs",
            "data_type": "json",
            "value_json": "{not valid json}",
            "source": "manual_entry",
        },
    )
    assert not form_bad.is_valid()
    assert "value_json" in form_bad.errors


@pytest.mark.django_db
def test_metadata_indexing_metadata_value_form_duplicate_field_rejected(
    tenant_a, document, document_version, document_metadata_value
):
    """Test DocumentMetadataValueForm rejects duplicate field name on same document & revision."""
    form = DocumentMetadataValueForm(
        tenant=tenant_a,
        data={
            "document": document.pk,
            "version": document_version.pk,
            "field_name": document_metadata_value.field_name,  # contract_value
            "data_type": "decimal",
            "value_number": 2000.00,
            "source": "manual_entry",
        },
    )
    assert not form.is_valid()
    assert "field_name" in form.errors


@pytest.mark.django_db
def test_metadata_indexing_ocr_job_form_excluded_fields():
    """Verify system fields are excluded from DocumentOcrJobForm."""
    form = DocumentOcrJobForm()
    for field in ["tenant", "number", "status", "extracted_full_text", "confidence_score", "applied_to_document", "created_by"]:
        assert field not in form.fields, f"Security violation: {field} exposed in form"


@pytest.mark.django_db
def test_metadata_indexing_ocr_job_form_valid(tenant_a, document, document_version):
    """Test DocumentOcrJobForm with valid data."""
    form = DocumentOcrJobForm(
        tenant=tenant_a,
        data={
            "document": document.pk,
            "version": document_version.pk,
            "ocr_engine": "tesseract_ocr",
        },
    )
    assert form.is_valid(), form.errors
