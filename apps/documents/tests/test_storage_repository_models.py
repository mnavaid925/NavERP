"""Unit tests for Sub-module 13.4 Storage Repository models."""
from decimal import Decimal
import json
import pytest
from django.db import IntegrityError

from apps.documents.models.StorageRepository.DocumentFolders import DocumentFolder
from apps.documents.models.StorageRepository.StorageVolumes import StorageVolume
from apps.documents.models.StorageRepository.DocumentRelationships import DocumentRelationship
from apps.documents.models.StorageRepository.DocumentBatchImports import DocumentBatchImport


@pytest.mark.django_db
def test_storage_repository_document_folder_numbering_and_slug(tenant_a, admin_user):
    """Test DocumentFolder auto-numbering with prefix DFLD and automatic slug generation."""
    folder = DocumentFolder.objects.create(
        tenant=tenant_a,
        name="Finance & Accounting Records",
        owner=admin_user,
    )
    assert folder.number.startswith("DFLD-")
    assert folder.slug == "finance-accounting-records"
    assert folder.path == "/finance-accounting-records/"
    assert folder.is_root is True
    assert "finance-accounting-records" in str(folder)


@pytest.mark.django_db
def test_storage_repository_document_folder_hierarchy_and_materialized_path(
    tenant_a, admin_user, document_folder, child_document_folder
):
    """Test folder parent-child relationship and nested materialized path calculation."""
    assert document_folder.is_root is True
    assert document_folder.path == f"/{document_folder.slug}/"
    assert document_folder.subfolder_count >= 1

    assert child_document_folder.parent == document_folder
    assert child_document_folder.is_root is False
    expected_path = f"/{document_folder.slug}/{child_document_folder.slug}/"
    assert child_document_folder.path == expected_path

    # Create grandchild folder
    grandchild = DocumentFolder.objects.create(
        tenant=tenant_a,
        name="Benefits",
        slug="benefits",
        parent=child_document_folder,
        owner=admin_user,
    )
    assert grandchild.path == f"/{document_folder.slug}/{child_document_folder.slug}/benefits/"


@pytest.mark.django_db
def test_storage_repository_document_folder_path_cascade_update(tenant_a, admin_user):
    """Test updating parent slug propagates path updates recursively to descendants."""
    root = DocumentFolder.objects.create(
        tenant=tenant_a,
        name="Operations",
        slug="operations",
        owner=admin_user,
    )
    child = DocumentFolder.objects.create(
        tenant=tenant_a,
        name="Logistics",
        slug="logistics",
        parent=root,
        owner=admin_user,
    )
    subchild = DocumentFolder.objects.create(
        tenant=tenant_a,
        name="Fleet",
        slug="fleet",
        parent=child,
        owner=admin_user,
    )

    assert subchild.path == "/operations/logistics/fleet/"

    # Rename root slug
    root.slug = "ops-v2"
    root.save()

    child.refresh_from_db()
    subchild.refresh_from_db()

    assert child.path == "/ops-v2/logistics/"
    assert subchild.path == "/ops-v2/logistics/fleet/"


@pytest.mark.django_db
def test_storage_repository_document_folder_virtual_criteria(tenant_a, admin_user):
    """Test virtual folder criteria parsing and helper properties."""
    criteria_payload = {"classification": "confidential", "document_type": "contract"}
    v_folder = DocumentFolder.objects.create(
        tenant=tenant_a,
        name="Confidential Contracts Smart Folder",
        owner=admin_user,
        is_virtual=True,
        virtual_criteria_json=json.dumps(criteria_payload),
    )
    assert v_folder.is_virtual is True
    assert v_folder.criteria_dict == criteria_payload

    # Test invalid json handling
    v_folder.virtual_criteria_json = "invalid-json"
    v_folder.save()
    assert v_folder.criteria_dict == {}


@pytest.mark.django_db
def test_storage_repository_document_folder_badges_and_constraints(tenant_a, admin_user):
    """Test folder CSS badges and uniqueness constraints."""
    folder = DocumentFolder.objects.create(
        tenant=tenant_a,
        name="Public Media",
        default_classification="public",
        owner=admin_user,
        is_active=True,
    )
    assert folder.classification_badge_class == "badge-green"
    assert folder.status_badge_class == "badge-green"

    folder.is_active = False
    assert folder.status_badge_class == "badge-slate"

    # Unique constraint on tenant, parent, slug (with non-null parent)
    child = DocumentFolder.objects.create(
        tenant=tenant_a,
        name="Photos",
        slug="photos",
        parent=folder,
        owner=admin_user,
    )
    with pytest.raises(IntegrityError):
        DocumentFolder.objects.create(
            tenant=tenant_a,
            name="Photos Duplicate",
            slug="photos",
            parent=folder,
            owner=admin_user,
        )

    # Unique constraint on tenant, number
    with pytest.raises(IntegrityError):
        DocumentFolder.objects.create(
            tenant=tenant_a,
            number=folder.number,
            name="Duplicate Number Folder",
            owner=admin_user,
        )


@pytest.mark.django_db
def test_storage_repository_storage_volume_numbering_and_defaults(tenant_a):
    """Test StorageVolume auto-numbering with prefix DSTG and properties."""
    volume = StorageVolume.objects.create(
        tenant=tenant_a,
        name="Archive Cold SAN",
        code="VOL-COLD-01",
        backend_type="network_nas",
        tier="cold",
        base_path="/mnt/nas/cold_archive",
        max_capacity_bytes=500 * 1024 * 1024 * 1024,
    )
    assert volume.number.startswith("DSTG-")
    assert volume.tier_badge_class == "badge-info"
    assert volume.backend_badge_class == "badge-info"
    assert "Archive Cold SAN" in str(volume)
    assert volume.utilized_percentage == Decimal("0.0")
    assert volume.is_full is False


@pytest.mark.django_db
def test_storage_repository_storage_volume_single_default_guarantee(tenant_a, tenant_b, storage_volume):
    """Test single default storage volume per tenant constraint."""
    assert storage_volume.is_default is True

    # Creating another volume marked as default in tenant_a demotes the previous default
    vol2 = StorageVolume.objects.create(
        tenant=tenant_a,
        name="Secondary Cloud Bucket",
        code="VOL-S3-01",
        backend_type="s3_compatible",
        tier="warm",
        base_path="nav-docs-bucket",
        is_default=True,
    )

    storage_volume.refresh_from_db()
    assert storage_volume.is_default is False
    assert vol2.is_default is True

    # A default volume in tenant_b must not unset tenant_a's default
    vol_b = StorageVolume.objects.create(
        tenant=tenant_b,
        name="Tenant B Store",
        code="VOL-B-01",
        backend_type="local_filesystem",
        base_path="/var/tenant_b",
        is_default=True,
    )
    vol2.refresh_from_db()
    assert vol2.is_default is True
    assert vol_b.is_default is True


@pytest.mark.django_db
def test_storage_repository_storage_volume_quota_and_utilization(tenant_a):
    """Test quota tracking, utilization percentage calculation, and warning threshold."""
    total_cap = 100 * 1024 * 1024 * 1024  # 100 GB
    used_cap = 90 * 1024 * 1024 * 1024   # 90 GB (90%)

    volume = StorageVolume.objects.create(
        tenant=tenant_a,
        name="Performance Hot Store",
        code="VOL-HOT-99",
        tier="hot",
        base_path="/data/hot",
        max_capacity_bytes=total_cap,
        utilized_bytes=used_cap,
        warning_threshold_pct=85,
    )

    assert volume.utilized_percentage == Decimal("90.00")
    assert volume.is_full is False
    assert volume.is_over_warning is True
    assert volume.max_capacity_gb == 100.0
    assert volume.utilized_gb == 90.0
    assert volume.free_gb == 10.0

    # Over quota triggers is_full
    volume.utilized_bytes = total_cap + (1024 * 1024)
    volume.save()
    assert volume.is_full is True
    assert volume.utilized_percentage == Decimal("100.00")
    assert volume.free_bytes == 0


@pytest.mark.django_db
def test_storage_repository_storage_volume_rollover_and_constraints(tenant_a):
    """Test rollover volume link and uniqueness constraints on code."""
    v_overflow = StorageVolume.objects.create(
        tenant=tenant_a,
        name="Overflow Tier",
        code="VOL-OVF-01",
        base_path="/data/ovf",
    )
    v_primary = StorageVolume.objects.create(
        tenant=tenant_a,
        name="Primary Tier",
        code="VOL-PRI-01",
        base_path="/data/pri",
        rollover_volume=v_overflow,
    )
    assert v_primary.rollover_volume == v_overflow
    assert v_overflow.overflow_sources.count() == 1

    # Unique constraint on tenant and code
    with pytest.raises(IntegrityError):
        StorageVolume.objects.create(
            tenant=tenant_a,
            name="Duplicate Code",
            code="VOL-PRI-01",
            base_path="/data/dup",
        )


@pytest.mark.django_db
def test_storage_repository_document_relationship_numbering_and_linking(
    tenant_a, admin_user, document, target_document
):
    """Test DocumentRelationship autonumbering DREL and source/target document FKs."""
    rel = DocumentRelationship.objects.create(
        tenant=tenant_a,
        source_document=document,
        target_document=target_document,
        relationship_type="supersedes",
        is_bidirectional=True,
        dependency_level="strict_blocking",
        created_by=admin_user,
    )
    assert rel.number.startswith("DREL-")
    assert rel.source_document == document
    assert rel.target_document == target_document
    assert rel.type_badge_class == "badge-amber"
    assert rel.dependency_badge_class == "badge-red"
    assert "Supersedes" in str(rel)

    # Check related managers on Document
    assert document.outgoing_relationships.filter(pk=rel.pk).exists()
    assert target_document.incoming_relationships.filter(pk=rel.pk).exists()


@pytest.mark.django_db
def test_storage_repository_document_relationship_properties_and_constraints(
    tenant_a, admin_user, document, target_document
):
    """Test relationship uniqueness constraint (tenant + source + target + relationship_type)."""
    DocumentRelationship.objects.create(
        tenant=tenant_a,
        source_document=document,
        target_document=target_document,
        relationship_type="references",
        created_by=admin_user,
    )

    with pytest.raises(IntegrityError):
        DocumentRelationship.objects.create(
            tenant=tenant_a,
            source_document=document,
            target_document=target_document,
            relationship_type="references",
            created_by=admin_user,
        )


@pytest.mark.django_db
def test_storage_repository_batch_import_numbering_and_lifecycle(
    tenant_a, admin_user, document_folder, storage_volume
):
    """Test DocumentBatchImport autonumbering DBLK and status transitions."""
    batch = DocumentBatchImport.objects.create(
        tenant=tenant_a,
        batch_name="Legacy Archive 2025",
        source_type="legacy_migration",
        target_folder=document_folder,
        storage_volume=storage_volume,
        created_by=admin_user,
        status="draft",
    )
    assert batch.number.startswith("DBLK-")
    assert batch.status == "draft"
    assert batch.status_badge_class == "badge-slate"
    assert batch.source_type_badge_class == "badge-green"
    assert "Legacy Archive 2025" in str(batch)

    # Status transition to extracting then completed
    batch.status = "extracting"
    batch.save(update_fields=["status"])
    assert batch.status_badge_class == "badge-amber"

    batch.status = "completed"
    batch.save(update_fields=["status"])
    assert batch.status_badge_class == "badge-green"


@pytest.mark.django_db
def test_storage_repository_batch_import_metrics_and_properties(tenant_a, admin_user):
    """Test batch import progress percentage, success rate, and MB calculations."""
    batch = DocumentBatchImport.objects.create(
        tenant=tenant_a,
        batch_name="Import Ingestion Metrics Test",
        total_files_detected=10,
        processed_files_count=8,
        success_files_count=6,
        failed_files_count=2,
        total_bytes_processed=5 * 1024 * 1024,  # 5 MB
        created_by=admin_user,
    )
    assert batch.progress_percentage == 80.0
    assert batch.success_rate_percentage == 75.0
    assert batch.total_mb_processed == 5.0

    # Test completed status with 0 files detected returns 100%
    empty_batch = DocumentBatchImport.objects.create(
        tenant=tenant_a,
        batch_name="Empty Completed Batch",
        status="completed",
        created_by=admin_user,
    )
    assert empty_batch.progress_percentage == 100.0
    assert empty_batch.success_rate_percentage == 0.0
