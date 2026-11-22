"""View unit tests for Sub-module 13.4: Document Storage & Repository."""
import io
import json
import zipfile
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.documents.models.StorageRepository.DocumentFolders import DocumentFolder
from apps.documents.models.StorageRepository.StorageVolumes import StorageVolume
from apps.documents.models.StorageRepository.DocumentRelationships import DocumentRelationship
from apps.documents.models.StorageRepository.DocumentBatchImports import DocumentBatchImport
from apps.documents.models.VersionControl.Documents import Document


def _storage_repository_create_zip_file(file_names):
    """Helper to generate an in-memory zip file for batch ingestion testing."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in file_names:
            zf.writestr(name, f"Content payload for {name}".encode("utf-8"))
    buf.seek(0)
    return SimpleUploadedFile("test_package.zip", buf.read(), content_type="application/zip")


@pytest.mark.django_db
def test_storage_repository_dashboard_view(
    client_a, tenant_a, document_folder, storage_volume, document_relationship, document_batch_import
):
    """Test repository_dashboard renders 200 OK and aggregates KPI metrics."""
    url = reverse("documents:repository_dashboard")
    res = client_a.get(url)
    assert res.status_code == 200
    assert "total_folders" in res.context
    assert res.context["total_folders"] >= 1
    assert res.context["total_volumes"] >= 1
    assert res.context["total_relationships"] >= 1
    assert res.context["total_imports"] >= 1
    assert res.context["total_capacity_bytes"] > 0
    assert "capacity_utilization_pct" in res.context


@pytest.mark.django_db
def test_storage_repository_folder_list_and_tree_views(
    client_a, tenant_a, document_folder, child_document_folder
):
    """Test folder_list with filters and folder_tree nested JSON generation."""
    # List view
    list_url = reverse("documents:folder_list")
    res = client_a.get(list_url)
    assert res.status_code == 200
    assert document_folder.name in res.content.decode()

    # Search filter
    res_search = client_a.get(list_url, {"q": "Corporate"})
    assert res_search.status_code == 200
    assert document_folder.name in res_search.content.decode()

    res_no_match = client_a.get(list_url, {"q": "NonExistentFolder123"})
    assert res_no_match.status_code == 200
    assert res_no_match.context["total_count"] == 0

    # Tree view
    tree_url = reverse("documents:folder_tree")
    res_tree = client_a.get(tree_url)
    assert res_tree.status_code == 200
    assert "tree_json" in res_tree.context
    tree_data = json.loads(res_tree.context["tree_json"])
    assert len(tree_data) >= 1
    assert any(node["name"] == document_folder.name for node in tree_data)


@pytest.mark.django_db
def test_storage_repository_folder_crud_views(client_a, tenant_a, admin_user):
    """Test folder create, detail, edit, and delete lifecycle."""
    # 1. Create GET & POST
    create_url = reverse("documents:folder_create")
    res_get = client_a.get(create_url)
    assert res_get.status_code == 200

    create_data = {
        "name": "Procurement Contracts",
        "slug": "procurement-contracts",
        "color_code": "#10B981",
        "icon_name": "folder",
        "default_classification": "confidential",
        "default_document_type": "contract",
        "owner": admin_user.pk,
        "is_active": True,
    }
    res_create = client_a.post(create_url, create_data)
    assert res_create.status_code == 302
    folder = DocumentFolder.objects.get(name="Procurement Contracts", tenant=tenant_a)
    assert folder.number.startswith("DFLD-")

    # 2. Detail
    detail_url = reverse("documents:folder_detail", args=[folder.pk])
    res_detail = client_a.get(detail_url)
    assert res_detail.status_code == 200
    assert folder.name in res_detail.content.decode()
    assert "documents" in res_detail.context

    # 3. Edit GET & POST
    edit_url = reverse("documents:folder_edit", args=[folder.pk])
    res_edit_get = client_a.get(edit_url)
    assert res_edit_get.status_code == 200

    edit_data = {
        **create_data,
        "name": "Procurement & Sourcing Contracts",
    }
    res_edit_post = client_a.post(edit_url, edit_data)
    assert res_edit_post.status_code == 302
    folder.refresh_from_db()
    assert folder.name == "Procurement & Sourcing Contracts"

    # 4. Delete GET (Method Not Allowed) & POST
    delete_url = reverse("documents:folder_delete", args=[folder.pk])
    res_del_get = client_a.get(delete_url)
    assert res_del_get.status_code == 405

    res_del_post = client_a.post(delete_url)
    assert res_del_post.status_code == 302
    assert not DocumentFolder.objects.filter(pk=folder.pk).exists()


@pytest.mark.django_db
def test_storage_repository_folder_delete_protections(client_a, tenant_a, admin_user, document_folder, child_document_folder):
    """Test folder delete protections for system folders and folders with active subfolders."""
    # Attempt to delete parent folder when it has active child folder
    del_url = reverse("documents:folder_delete", args=[document_folder.pk])
    res = client_a.post(del_url)
    assert res.status_code == 302
    assert DocumentFolder.objects.filter(pk=document_folder.pk).exists()

    # Attempt to delete a system folder
    sys_folder = DocumentFolder.objects.create(
        tenant=tenant_a,
        name="System Protected",
        is_system=True,
        owner=admin_user,
    )
    res_sys = client_a.post(reverse("documents:folder_delete", args=[sys_folder.pk]))
    assert res_sys.status_code == 302
    assert DocumentFolder.objects.filter(pk=sys_folder.pk).exists()


@pytest.mark.django_db
def test_storage_repository_storage_volume_list_and_filtering(client_a, tenant_a, storage_volume):
    """Test storage_volume_list with tier and backend_type filters."""
    url = reverse("documents:storage_volume_list")
    res = client_a.get(url)
    assert res.status_code == 200
    assert storage_volume.name in res.content.decode()
    assert res.context["total_capacity_gb"] > 0

    # Filter by backend_type
    res_filter = client_a.get(url, {"backend_type": "local_filesystem"})
    assert res_filter.status_code == 200
    assert len(res_filter.context["volumes"]) >= 1

    # Filter by tier
    res_tier = client_a.get(url, {"tier": "glacier_archive"})
    assert res_tier.status_code == 200
    assert len(res_tier.context["volumes"]) == 0


@pytest.mark.django_db
def test_storage_repository_storage_volume_crud_views(client_a, tenant_a):
    """Test storage volume create, detail, edit, and delete lifecycle."""
    # 1. Create
    create_url = reverse("documents:storage_volume_create")
    res_get = client_a.get(create_url)
    assert res_get.status_code == 200

    create_data = {
        "name": "Secondary Warm NAS",
        "code": "VOL-WARM-01",
        "backend_type": "network_nas",
        "tier": "warm",
        "base_path": "/mnt/nas/warm_store",
        "max_capacity_bytes": 200 * 1024 * 1024 * 1024,
        "warning_threshold_pct": 80,
        "compression_type": "gzip",
        "encryption_type": "aes_256",
        "is_active": True,
    }
    res_post = client_a.post(create_url, create_data)
    assert res_post.status_code == 302
    vol = StorageVolume.objects.get(code="VOL-WARM-01", tenant=tenant_a)
    assert vol.number.startswith("DSTG-")

    # 2. Detail
    detail_url = reverse("documents:storage_volume_detail", args=[vol.pk])
    res_detail = client_a.get(detail_url)
    assert res_detail.status_code == 200
    assert vol.name in res_detail.content.decode()

    # 3. Edit
    edit_url = reverse("documents:storage_volume_edit", args=[vol.pk])
    edit_data = {
        **create_data,
        "name": "Secondary Warm NAS (Expanded)",
    }
    res_edit = client_a.post(edit_url, edit_data)
    assert res_edit.status_code == 302
    vol.refresh_from_db()
    assert vol.name == "Secondary Warm NAS (Expanded)"

    # 4. Delete
    delete_url = reverse("documents:storage_volume_delete", args=[vol.pk])
    res_del_get = client_a.get(delete_url)
    assert res_del_get.status_code == 405

    res_del_post = client_a.post(delete_url)
    assert res_del_post.status_code == 302
    assert not StorageVolume.objects.filter(pk=vol.pk).exists()


@pytest.mark.django_db
def test_storage_repository_storage_volume_delete_default_protection(client_a, storage_volume):
    """Test storage_volume_delete prevents deleting the default storage volume."""
    assert storage_volume.is_default is True
    del_url = reverse("documents:storage_volume_delete", args=[storage_volume.pk])
    res = client_a.post(del_url)
    assert res.status_code == 302
    assert StorageVolume.objects.filter(pk=storage_volume.pk).exists()


@pytest.mark.django_db
def test_storage_repository_relationship_list_and_graph_views(
    client_a, tenant_a, document_relationship
):
    """Test relationship_list filtering and relationship_graph node/edge JSON structures."""
    # List view
    list_url = reverse("documents:relationship_list")
    res = client_a.get(list_url)
    assert res.status_code == 200
    assert document_relationship.source_document.title in res.content.decode()

    # Filter by type
    res_filter = client_a.get(list_url, {"relationship_type": "references"})
    assert res_filter.status_code == 200
    assert len(res_filter.context["relationships"]) >= 1

    # Graph view
    graph_url = reverse("documents:relationship_graph")
    res_graph = client_a.get(graph_url)
    assert res_graph.status_code == 200
    assert "nodes_json" in res_graph.context
    assert "links_json" in res_graph.context
    nodes = json.loads(res_graph.context["nodes_json"])
    links = json.loads(res_graph.context["links_json"])
    assert len(nodes) >= 2
    assert len(links) >= 1


@pytest.mark.django_db
def test_storage_repository_relationship_crud_views(client_a, tenant_a, admin_user, document, target_document):
    """Test relationship create, detail, edit, and delete lifecycle."""
    # 1. Create
    create_url = reverse("documents:relationship_create")
    res_get = client_a.get(create_url, {"source": document.pk})
    assert res_get.status_code == 200

    create_data = {
        "source_document": document.pk,
        "target_document": target_document.pk,
        "relationship_type": "contract_exhibit",
        "is_bidirectional": True,
        "dependency_level": "contractual",
        "description": "Exhibit link between MSA and Statement of Work",
    }
    res_post = client_a.post(create_url, create_data)
    assert res_post.status_code == 302
    rel = DocumentRelationship.objects.get(
        source_document=document,
        target_document=target_document,
        relationship_type="contract_exhibit",
        tenant=tenant_a,
    )
    assert rel.number.startswith("DREL-")

    # 2. Detail
    detail_url = reverse("documents:relationship_detail", args=[rel.pk])
    res_detail = client_a.get(detail_url)
    assert res_detail.status_code == 200
    assert rel.number in res_detail.content.decode()

    # 3. Edit
    edit_url = reverse("documents:relationship_edit", args=[rel.pk])
    res_edit = client_a.post(edit_url, {**create_data, "description": "Updated exhibit link description"})
    assert res_edit.status_code == 302
    rel.refresh_from_db()
    assert rel.description == "Updated exhibit link description"

    # 4. Delete
    delete_url = reverse("documents:relationship_delete", args=[rel.pk])
    res_del_get = client_a.get(delete_url)
    assert res_del_get.status_code == 405

    res_del_post = client_a.post(delete_url)
    assert res_del_post.status_code == 302
    assert not DocumentRelationship.objects.filter(pk=rel.pk).exists()


@pytest.mark.django_db
def test_storage_repository_batch_import_list_and_crud_views(
    client_a, tenant_a, admin_user, document_folder, storage_volume
):
    """Test batch_import_list, create, detail, edit, and delete lifecycle."""
    # 1. List
    list_url = reverse("documents:batch_import_list")
    res_list = client_a.get(list_url)
    assert res_list.status_code == 200

    # 2. Create
    create_url = reverse("documents:batch_import_create")
    res_create_get = client_a.get(create_url)
    assert res_create_get.status_code == 200

    zip_file = _storage_repository_create_zip_file(["manual_1.pdf", "manual_2.pdf"])
    create_data = {
        "batch_name": "Q1 Operational Policies Import",
        "source_type": "zip_archive",
        "target_folder": document_folder.pk,
        "storage_volume": storage_volume.pk,
    }
    res_create_post = client_a.post(create_url, {**create_data, "archive_file": zip_file})
    assert res_create_post.status_code == 302
    batch = DocumentBatchImport.objects.get(batch_name="Q1 Operational Policies Import", tenant=tenant_a)
    assert batch.number.startswith("DBLK-")
    assert batch.status == "queued"

    # 3. Detail
    detail_url = reverse("documents:batch_import_detail", args=[batch.pk])
    res_detail = client_a.get(detail_url)
    assert res_detail.status_code == 200
    assert batch.batch_name in res_detail.content.decode()

    # 4. Edit
    edit_url = reverse("documents:batch_import_edit", args=[batch.pk])
    res_edit = client_a.post(edit_url, {
        "batch_name": "Q1 Operational Policies Ingestion (Renamed)",
        "source_type": "zip_archive",
        "target_folder": document_folder.pk,
        "storage_volume": storage_volume.pk,
    })
    assert res_edit.status_code == 302
    batch.refresh_from_db()
    assert batch.batch_name == "Q1 Operational Policies Ingestion (Renamed)"

    # 5. Delete
    delete_url = reverse("documents:batch_import_delete", args=[batch.pk])
    res_del_get = client_a.get(delete_url)
    assert res_del_get.status_code == 405

    res_del_post = client_a.post(delete_url)
    assert res_del_post.status_code == 302
    assert not DocumentBatchImport.objects.filter(pk=batch.pk).exists()


@pytest.mark.django_db
def test_storage_repository_batch_import_process_execution(
    client_a, tenant_a, admin_user, document_folder, storage_volume
):
    """Test batch_import_process extracts candidate files and creates Document records."""
    zip_file = _storage_repository_create_zip_file(["policy_handbook.pdf", "safety_guidelines.docx"])

    batch = DocumentBatchImport.objects.create(
        tenant=tenant_a,
        batch_name="Batch Ingestion Process Run",
        source_type="zip_archive",
        target_folder=document_folder,
        storage_volume=storage_volume,
        archive_file=zip_file,
        created_by=admin_user,
        status="queued",
    )

    process_url = reverse("documents:batch_import_process", args=[batch.pk])
    res_get = client_a.get(process_url)
    assert res_get.status_code == 405

    res_post = client_a.post(process_url)
    assert res_post.status_code == 302

    batch.refresh_from_db()
    assert batch.status == "completed"
    assert batch.processed_files_count == 2
    assert batch.success_files_count == 2
    assert batch.total_bytes_processed > 0
    assert "Successfully filed 2 documents" in batch.log_summary

    # Verify that Document records were created in the repository
    assert Document.objects.filter(
        tenant=tenant_a,
        title="Policy Handbook",
    ).exists()
    assert Document.objects.filter(
        tenant=tenant_a,
        title="Safety Guidelines",
    ).exists()
