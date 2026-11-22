"""Security and multi-tenant isolation unit tests for Sub-module 13.4: Document Storage & Repository."""
import pytest
from django.urls import reverse

from apps.documents.models.StorageRepository.DocumentFolders import DocumentFolder
from apps.documents.models.StorageRepository.StorageVolumes import StorageVolume
from apps.documents.models.StorageRepository.DocumentRelationships import DocumentRelationship
from apps.documents.models.StorageRepository.DocumentBatchImports import DocumentBatchImport


@pytest.mark.django_db
def test_storage_repository_unauthenticated_access_redirects(
    client, document_folder, storage_volume, document_relationship, document_batch_import
):
    """Test that all Sub-module 13.4 endpoints redirect unauthenticated requests to login."""
    endpoints = [
        reverse("documents:repository_dashboard"),
        reverse("documents:folder_list"),
        reverse("documents:folder_tree"),
        reverse("documents:folder_create"),
        reverse("documents:folder_detail", args=[document_folder.pk]),
        reverse("documents:folder_edit", args=[document_folder.pk]),
        reverse("documents:storage_volume_list"),
        reverse("documents:storage_volume_create"),
        reverse("documents:storage_volume_detail", args=[storage_volume.pk]),
        reverse("documents:storage_volume_edit", args=[storage_volume.pk]),
        reverse("documents:relationship_list"),
        reverse("documents:relationship_graph"),
        reverse("documents:relationship_create"),
        reverse("documents:relationship_detail", args=[document_relationship.pk]),
        reverse("documents:relationship_edit", args=[document_relationship.pk]),
        reverse("documents:batch_import_list"),
        reverse("documents:batch_import_create"),
        reverse("documents:batch_import_detail", args=[document_batch_import.pk]),
        reverse("documents:batch_import_edit", args=[document_batch_import.pk]),
    ]
    for url in endpoints:
        res = client.get(url)
        assert res.status_code == 302, f"Expected 302 redirect for {url}, got {res.status_code}"
        assert "/login/" in res.headers["Location"]


@pytest.mark.django_db
def test_storage_repository_storage_volume_admin_authorization(
    member_client, storage_volume
):
    """Test that non-admin member is forbidden (403) from storage volume create, edit, and delete."""
    # Create GET & POST
    create_url = reverse("documents:storage_volume_create")
    assert member_client.get(create_url).status_code == 403
    assert member_client.post(create_url, {}).status_code == 403

    # Edit GET & POST
    edit_url = reverse("documents:storage_volume_edit", args=[storage_volume.pk])
    assert member_client.get(edit_url).status_code == 403
    assert member_client.post(edit_url, {}).status_code == 403

    # Delete POST
    del_url = reverse("documents:storage_volume_delete", args=[storage_volume.pk])
    assert member_client.post(del_url).status_code == 403


@pytest.mark.django_db
def test_storage_repository_folder_and_batch_delete_owner_authorization(
    member_client, tenant_a, admin_user, document_folder, document_batch_import
):
    """Test that non-admin member cannot delete folders or batch imports owned by another user."""
    # Member user is not folder owner and not tenant admin
    fld_del_url = reverse("documents:folder_delete", args=[document_folder.pk])
    res_fld = member_client.post(fld_del_url)
    assert res_fld.status_code == 302
    assert DocumentFolder.objects.filter(pk=document_folder.pk).exists()

    # Member user is not batch import creator and not tenant admin
    batch_del_url = reverse("documents:batch_import_delete", args=[document_batch_import.pk])
    res_batch = member_client.post(batch_del_url)
    assert res_batch.status_code == 302
    assert DocumentBatchImport.objects.filter(pk=document_batch_import.pk).exists()


@pytest.mark.django_db
def test_storage_repository_cross_tenant_idor_get_protection(
    client_b, document_folder, storage_volume, document_relationship, document_batch_import
):
    """Test that tenant B cannot access tenant A repository objects (must return 404)."""
    # 1. DocumentFolder
    res_fld_detail = client_b.get(reverse("documents:folder_detail", args=[document_folder.pk]))
    assert res_fld_detail.status_code == 404
    res_fld_edit = client_b.get(reverse("documents:folder_edit", args=[document_folder.pk]))
    assert res_fld_edit.status_code == 404

    # 2. StorageVolume
    res_vol_detail = client_b.get(reverse("documents:storage_volume_detail", args=[storage_volume.pk]))
    assert res_vol_detail.status_code == 404
    res_vol_edit = client_b.get(reverse("documents:storage_volume_edit", args=[storage_volume.pk]))
    assert res_vol_edit.status_code == 404

    # 3. DocumentRelationship
    res_rel_detail = client_b.get(reverse("documents:relationship_detail", args=[document_relationship.pk]))
    assert res_rel_detail.status_code == 404
    res_rel_edit = client_b.get(reverse("documents:relationship_edit", args=[document_relationship.pk]))
    assert res_rel_edit.status_code == 404

    # 4. DocumentBatchImport
    res_batch_detail = client_b.get(reverse("documents:batch_import_detail", args=[document_batch_import.pk]))
    assert res_batch_detail.status_code == 404
    res_batch_edit = client_b.get(reverse("documents:batch_import_edit", args=[document_batch_import.pk]))
    assert res_batch_edit.status_code == 404


@pytest.mark.django_db
def test_storage_repository_cross_tenant_idor_post_mutations_protection(
    client_b, document_folder, storage_volume, document_relationship, document_batch_import
):
    """Test that tenant B cannot perform POST mutations against tenant A objects (must return 404)."""
    # 1. Folder mutations
    assert client_b.post(
        reverse("documents:folder_edit", args=[document_folder.pk]),
        {"name": "Tampered Name"},
    ).status_code == 404
    assert client_b.post(reverse("documents:folder_delete", args=[document_folder.pk])).status_code == 404

    # 2. Storage volume mutations
    assert client_b.post(
        reverse("documents:storage_volume_edit", args=[storage_volume.pk]),
        {"name": "Tampered Vol"},
    ).status_code == 404
    assert client_b.post(reverse("documents:storage_volume_delete", args=[storage_volume.pk])).status_code == 404

    # 3. Relationship mutations
    assert client_b.post(
        reverse("documents:relationship_edit", args=[document_relationship.pk]),
        {"description": "Tampered Link"},
    ).status_code == 404
    assert client_b.post(reverse("documents:relationship_delete", args=[document_relationship.pk])).status_code == 404

    # 4. Batch import mutations
    assert client_b.post(
        reverse("documents:batch_import_edit", args=[document_batch_import.pk]),
        {"batch_name": "Tampered Batch"},
    ).status_code == 404
    assert client_b.post(reverse("documents:batch_import_delete", args=[document_batch_import.pk])).status_code == 404
    assert client_b.post(reverse("documents:batch_import_process", args=[document_batch_import.pk])).status_code == 404


@pytest.mark.django_db
def test_storage_repository_cross_tenant_list_isolation(
    client_b, document_folder, storage_volume, document_relationship, document_batch_import
):
    """Test that tenant A repository objects do not appear in tenant B list views."""
    # Folder list
    res_folders = client_b.get(reverse("documents:folder_list"))
    assert res_folders.status_code == 200
    assert document_folder.name not in res_folders.content.decode()

    # Volume list
    res_volumes = client_b.get(reverse("documents:storage_volume_list"))
    assert res_volumes.status_code == 200
    assert storage_volume.name not in res_volumes.content.decode()

    # Relationship list
    res_relationships = client_b.get(reverse("documents:relationship_list"))
    assert res_relationships.status_code == 200
    assert document_relationship.source_document.title not in res_relationships.content.decode()

    # Batch import list
    res_batches = client_b.get(reverse("documents:batch_import_list"))
    assert res_batches.status_code == 200
    assert document_batch_import.batch_name not in res_batches.content.decode()
