"""Unit tests for Sub-module 13.4 Storage Repository forms."""
import json
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.core.models import OrgUnit
from apps.documents.forms.StorageRepository.DocumentFolders import DocumentFolderForm
from apps.documents.forms.StorageRepository.StorageVolumes import StorageVolumeForm
from apps.documents.forms.StorageRepository.DocumentRelationships import DocumentRelationshipForm
from apps.documents.forms.StorageRepository.DocumentBatchImports import DocumentBatchImportForm
from apps.documents.models.StorageRepository.DocumentFolders import DocumentFolder
from apps.documents.models.StorageRepository.StorageVolumes import StorageVolume
from apps.documents.models.StorageRepository.DocumentRelationships import DocumentRelationship
from apps.documents.models.StorageRepository.DocumentBatchImports import DocumentBatchImport
from apps.documents.models.VersionControl.Documents import Document


@pytest.mark.django_db
def test_storage_repository_document_folder_form_exclusions_and_scoping(
    tenant_a, tenant_b, admin_user, member_user, document_folder
):
    """Test DocumentFolderForm system exclusions and tenant FK querysets scoping."""
    form = DocumentFolderForm(tenant=tenant_a)

    # Excluded system fields
    assert "tenant" not in form.fields
    assert "number" not in form.fields
    assert "path" not in form.fields
    assert "is_system" not in form.fields

    # Tenant FK scoping
    other_folder = DocumentFolder.objects.create(
        tenant=tenant_b,
        name="Tenant B Folder",
        owner=admin_user,
    )
    assert document_folder in form.fields["parent"].queryset
    assert other_folder not in form.fields["parent"].queryset

    # When editing, instance is excluded from its own parent queryset
    edit_form = DocumentFolderForm(instance=document_folder, tenant=tenant_a)
    assert document_folder not in edit_form.fields["parent"].queryset


@pytest.mark.django_db
def test_storage_repository_document_folder_form_validation_and_cycle(
    tenant_a, admin_user, document_folder, child_document_folder
):
    """Test DocumentFolderForm self-parent and cyclical nesting validation."""
    # Test setting self as parent (excluded from valid choices in queryset)
    form = DocumentFolderForm(
        data={
            "name": document_folder.name,
            "parent": document_folder.pk,
            "owner": admin_user.pk,
            "color_code": "#3B82F6",
            "icon_name": "folder",
            "default_classification": "internal",
        },
        instance=document_folder,
        tenant=tenant_a,
    )
    assert not form.is_valid()
    assert "parent" in form.errors

    # Test cyclical nesting: setting child folder as parent of root folder
    form_cycle = DocumentFolderForm(
        data={
            "name": document_folder.name,
            "parent": child_document_folder.pk,
            "owner": admin_user.pk,
            "color_code": "#3B82F6",
            "icon_name": "folder",
            "default_classification": "internal",
        },
        instance=document_folder,
        tenant=tenant_a,
    )
    assert not form_cycle.is_valid()
    assert "Cyclical folder nesting is prohibited." in form_cycle.errors["parent"]


@pytest.mark.django_db
def test_storage_repository_document_folder_form_virtual_criteria_validation(
    tenant_a, admin_user
):
    """Test virtual folder criteria JSON validation in DocumentFolderForm."""
    # Invalid JSON string
    form_invalid_json = DocumentFolderForm(
        data={
            "name": "Smart Folder",
            "is_virtual": True,
            "virtual_criteria_json": "{invalid json}",
            "color_code": "#3B82F6",
            "icon_name": "folder",
            "owner": admin_user.pk,
            "default_classification": "internal",
        },
        tenant=tenant_a,
    )
    assert not form_invalid_json.is_valid()
    assert any("Invalid JSON criteria" in err for err in form_invalid_json.errors["virtual_criteria_json"])

    # JSON that is not a dictionary (e.g., list or scalar)
    form_not_dict = DocumentFolderForm(
        data={
            "name": "Smart Folder",
            "is_virtual": True,
            "virtual_criteria_json": json.dumps(["classification", "internal"]),
            "color_code": "#3B82F6",
            "icon_name": "folder",
            "owner": admin_user.pk,
            "default_classification": "internal",
        },
        tenant=tenant_a,
    )
    assert not form_not_dict.is_valid()
    assert "Virtual folder criteria must be a valid JSON dictionary." in form_not_dict.errors["virtual_criteria_json"]

    # Valid virtual criteria dictionary
    valid_payload = {"classification": "confidential", "status": "published"}
    form_valid = DocumentFolderForm(
        data={
            "name": "Valid Smart Folder",
            "is_virtual": True,
            "virtual_criteria_json": json.dumps(valid_payload),
            "color_code": "#3B82F6",
            "icon_name": "folder",
            "owner": admin_user.pk,
            "default_classification": "confidential",
            "is_active": True,
        },
        tenant=tenant_a,
    )
    assert form_valid.is_valid(), form_valid.errors
    saved_folder = form_valid.save()
    assert saved_folder.criteria_dict == valid_payload


@pytest.mark.django_db
def test_storage_repository_document_folder_form_foreign_tenant_rejected(
    tenant_a, tenant_b, admin_user
):
    """Test reject_foreign raises validation error if parent folder belongs to another tenant."""
    foreign_parent = DocumentFolder.objects.create(
        tenant=tenant_b,
        name="Foreign Root",
        owner=admin_user,
    )
    form = DocumentFolderForm(
        data={
            "name": "Intruder Child",
            "parent": foreign_parent.pk,
            "owner": admin_user.pk,
            "default_classification": "internal",
        },
        tenant=tenant_a,
    )
    assert not form.is_valid()
    assert "parent" in form.errors


@pytest.mark.django_db
def test_storage_repository_storage_volume_form_exclusions_and_scoping(
    tenant_a, tenant_b, storage_volume
):
    """Test StorageVolumeForm field exclusions and rollover FK scoping."""
    form = StorageVolumeForm(tenant=tenant_a)

    # System and metric fields excluded
    assert "tenant" not in form.fields
    assert "number" not in form.fields
    assert "utilized_bytes" not in form.fields
    assert "utilized_percentage" not in form.fields
    assert "is_full" not in form.fields

    other_vol = StorageVolume.objects.create(
        tenant=tenant_b,
        name="Tenant B Volume",
        code="VOL-B-EXC",
        base_path="/mnt/b",
    )
    assert storage_volume in form.fields["rollover_volume"].queryset
    assert other_vol not in form.fields["rollover_volume"].queryset

    # When editing, instance is excluded from rollover_volume queryset
    edit_form = StorageVolumeForm(instance=storage_volume, tenant=tenant_a)
    assert storage_volume not in edit_form.fields["rollover_volume"].queryset


@pytest.mark.django_db
def test_storage_repository_storage_volume_form_code_cleaning_and_validation(tenant_a):
    """Test code auto-uppercase conversion, regex validation, and self-rollover rejection."""
    # Valid code with lower-case should be transformed to uppercase
    form_valid = StorageVolumeForm(
        data={
            "name": "Local Volume 1",
            "code": "vol-nvme-01",
            "backend_type": "local_filesystem",
            "tier": "hot",
            "base_path": "/var/nav_docs",
            "max_capacity_bytes": 107374182400,
            "warning_threshold_pct": 85,
            "compression_type": "none",
            "encryption_type": "aes_256",
        },
        tenant=tenant_a,
    )
    assert form_valid.is_valid(), form_valid.errors
    vol = form_valid.save()
    assert vol.code == "VOL-NVME-01"

    # Invalid code with spaces or forbidden symbols
    form_invalid_code = StorageVolumeForm(
        data={
            "name": "Invalid Code Volume",
            "code": "VOL NVME #1",
            "backend_type": "local_filesystem",
            "tier": "hot",
            "base_path": "/var/nav_docs",
            "max_capacity_bytes": 107374182400,
            "warning_threshold_pct": 85,
            "compression_type": "none",
            "encryption_type": "aes_256",
        },
        tenant=tenant_a,
    )
    assert not form_invalid_code.is_valid()
    assert "code" in form_invalid_code.errors

    # Volume cannot be its own rollover target
    form_self_rollover = StorageVolumeForm(
        data={
            "name": vol.name,
            "code": vol.code,
            "backend_type": vol.backend_type,
            "tier": vol.tier,
            "base_path": vol.base_path,
            "max_capacity_bytes": vol.max_capacity_bytes,
            "warning_threshold_pct": vol.warning_threshold_pct,
            "compression_type": vol.compression_type,
            "encryption_type": vol.encryption_type,
            "rollover_volume": vol.pk,
        },
        instance=vol,
        tenant=tenant_a,
    )
    assert not form_self_rollover.is_valid()
    assert "rollover_volume" in form_self_rollover.errors


@pytest.mark.django_db
def test_storage_repository_document_relationship_form_prevent_self_linking(
    tenant_a, document, target_document
):
    """Test DocumentRelationshipForm prevents self-linking source == target document."""
    form = DocumentRelationshipForm(
        data={
            "source_document": document.pk,
            "target_document": document.pk,  # Self linking!
            "relationship_type": "references",
            "dependency_level": "informational",
        },
        tenant=tenant_a,
    )
    assert not form.is_valid()
    assert "A document cannot create a relationship link to itself." in form.errors["target_document"]


@pytest.mark.django_db
def test_storage_repository_document_relationship_form_tenant_scoping_and_success(
    tenant_a, tenant_b, admin_user, document, target_document
):
    """Test DocumentRelationshipForm tenant FK scoping and successful creation."""
    foreign_doc = Document.objects.create(
        tenant=tenant_b,
        title="Tenant B Isolated Document",
        owner=admin_user,
    )

    form = DocumentRelationshipForm(tenant=tenant_a)
    assert document in form.fields["source_document"].queryset
    assert foreign_doc not in form.fields["source_document"].queryset

    # Attempt to post foreign document raises validation error
    form_foreign = DocumentRelationshipForm(
        data={
            "source_document": document.pk,
            "target_document": foreign_doc.pk,
            "relationship_type": "parent_child",
            "dependency_level": "contractual",
        },
        tenant=tenant_a,
    )
    assert not form_foreign.is_valid()
    assert "target_document" in form_foreign.errors

    # Valid relationship form
    form_valid = DocumentRelationshipForm(
        data={
            "source_document": document.pk,
            "target_document": target_document.pk,
            "relationship_type": "contract_exhibit",
            "is_bidirectional": True,
            "dependency_level": "contractual",
            "description": "Standard service agreement appendix A",
        },
        tenant=tenant_a,
    )
    assert form_valid.is_valid(), form_valid.errors
    rel = form_valid.save(commit=False)
    rel.created_by = admin_user
    rel.save()
    assert rel.relationship_type == "contract_exhibit"
    assert rel.is_bidirectional is True


@pytest.mark.django_db
def test_storage_repository_batch_import_form_extension_whitelist(tenant_a):
    """Test DocumentBatchImportForm validates allowed extensions whitelist."""
    # Disallowed extension: .exe or .py
    invalid_file = SimpleUploadedFile("malware.exe", b"MZ\x90\x00BinaryPayload", content_type="application/octet-stream")
    form_invalid = DocumentBatchImportForm(
        data={"batch_name": "Invalid File Batch", "source_type": "zip_archive"},
        files={"archive_file": invalid_file},
        tenant=tenant_a,
    )
    assert not form_invalid.is_valid()
    assert any("Unsupported batch import package format" in err for err in form_invalid.errors["archive_file"])

    # Allowed extension: .zip
    valid_file = SimpleUploadedFile("archive.zip", b"PK\x03\x04FakeZipHeader", content_type="application/zip")
    form_valid = DocumentBatchImportForm(
        data={"batch_name": "Valid ZIP Batch", "source_type": "zip_archive"},
        files={"archive_file": valid_file},
        tenant=tenant_a,
    )
    assert form_valid.is_valid(), form_valid.errors


@pytest.mark.django_db
def test_storage_repository_batch_import_form_max_size_limit(tenant_a):
    """Test DocumentBatchImportForm rejects files exceeding 50 MB limit."""
    class LargeMockUploadedFile:
        name = "huge_archive.zip"
        size = 55 * 1024 * 1024  # 55 MB > 50 MB
        def read(self):
            return b""

    form = DocumentBatchImportForm(
        data={"batch_name": "Oversized Batch", "source_type": "zip_archive"},
        files={"archive_file": LargeMockUploadedFile()},
        tenant=tenant_a,
    )
    assert not form.is_valid()
    assert "Archive file size exceeds the maximum limit of 50 MB." in form.errors["archive_file"]


@pytest.mark.django_db
def test_storage_repository_batch_import_form_zip_payload_required(tenant_a):
    """Test zip_archive source_type requires an uploaded archive file on create."""
    form = DocumentBatchImportForm(
        data={"batch_name": "Missing Zip Batch", "source_type": "zip_archive"},
        tenant=tenant_a,
    )
    assert not form.is_valid()
    assert "ZIP Archive Package requires an archive file payload." in form.errors["archive_file"]
