# Review Findings: Sub-module 13.4 (Document Storage & Repository)

Changeset reviewed: `b08db857c203f0a24e635a1d1ae1c8088b6073c0...HEAD`
Reviewers:
1. `code-reviewer`
2. `explorer`
3. `frontend-reviewer`
4. `performance-reviewer`
5. `qa-smoke-tester`
6. `security-reviewer`

---

## Verdict
**PASS WITH FINDINGS**
All core contracted entities, routes, views, templates, navigation entries, migrations, and seeder logic are present, functional, and tenant-isolated. Address Critical and Important findings to ensure enterprise-grade security, ORM efficiency, and design-system compliance before finalizing tests.

---

## Findings

### Critical

- [x] **C1**: Storage Volume mutations lack `@tenant_admin_required` authorization gate.
  - **Location**: `apps/documents/views/StorageRepository/StorageVolumes.py`
  - **Problem**: `storage_volume_create`, `storage_volume_edit`, and `storage_volume_delete` allow standard tenant members to reconfigure or delete core storage infrastructure and S3 mount endpoints.
  - **Fix**: Decorate `storage_volume_create`, `storage_volume_edit`, and `storage_volume_delete` with `@tenant_admin_required`. [x] fixed — 6f60e5c1: enforce tenant_admin_required on storage volume mutation views

- [x] **C2**: Direct `.path` call in `batch_import_process` breaks remote/cloud storage backends.
  - **Location**: `apps/documents/views/StorageRepository/DocumentBatchImports.py:180`
  - **Problem**: `batch.archive_file.path` raises `NotImplementedError` on S3/Azure/GCS object storage backends.
  - **Fix**: Open the file stream directly using `batch.archive_file.open("rb")` and pass stream to `zipfile.ZipFile(archive_stream)`. [x] fixed — 3f58c3f3: use stream access instead of path for remote storage compatibility

- [ ] **C3**: Unbounded batch ingestion allows zip bombs and database denial of service.
  - **Location**: `apps/documents/views/StorageRepository/DocumentBatchImports.py:190`
  - **Problem**: Unchecked archive extraction can consume all memory and lock worker transactions.
  - **Fix**: Enforce `MAX_BATCH_FILES = 500` and `MAX_BATCH_BYTES = 100 * 1024 * 1024` (100 MB total uncompressed size limit) before processing files.

- [ ] **C4**: Recursive N+1 Query Cascade in `folder_tree`.
  - **Location**: `apps/documents/views/StorageRepository/DocumentFolders.py:78-92`
  - **Problem**: `build_tree` calls `folder.children.filter(...)` inside a recursive loop, issuing 1+N queries.
  - **Fix**: Fetch all active folders for the tenant in 1 single query and assemble the tree hierarchy in memory using a dictionary/adjacency list (`defaultdict(list)`).

---

### Important

- [ ] **I1**: Missing `__init__.py` in all four `StorageRepository` subpackages.
  - **Locations**:
    - `apps/documents/models/StorageRepository/__init__.py`
    - `apps/documents/forms/StorageRepository/__init__.py`
    - `apps/documents/views/StorageRepository/__init__.py`
    - `apps/documents/urls/StorageRepository/__init__.py`
  - **Problem**: Submodule package folders lack `__init__.py` files required by NavERP package structure standards.
  - **Fix**: Create package `__init__.py` files with docstrings in each of the four directories.

- [ ] **I2**: Disallowed and Undefined Theme CSS Badge Class `badge-purple` (Violates L33).
  - **Locations**:
    - `templates/documents/storage_repository/document_folder/list.html:162`
    - `templates/documents/storage_repository/document_folder/detail.html:57`
    - `templates/documents/storage_repository/document_folder/tree.html:63, 92`
  - **Problem**: `badge-purple` is not defined in `static/css/theme.css` (only `badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, `badge-slate` exist), causing smart virtual folder badges to render unstyled.
  - **Fix**: Replace `badge-purple` with `badge-info`.

- [ ] **I3**: Non-Atomic Operations during Volume Save, Ingestion Execution, and Record Deletions.
  - **Locations**:
    - `apps/documents/views/StorageRepository/StorageVolumes.py`
    - `apps/documents/views/StorageRepository/DocumentBatchImports.py`
    - `apps/documents/views/StorageRepository/DocumentFolders.py`
  - **Problem**: Volume default flipping, batch updates, and deletions lack explicit transaction blocks.
  - **Fix**: Wrap mutations and deletions in `with transaction.atomic():`.

- [ ] **I4**: Missing `select_related("created_by")` on `batch_imports` in `storage_volume_detail`.
  - **Location**: `apps/documents/views/StorageRepository/StorageVolumes.py:98`
  - **Problem**: Causes N+1 query loop when rendering batch import author in `storage_volume/detail.html:201`.
  - **Fix**: Add `.select_related("created_by")` to `volume.batch_imports.filter(...)`.

- [ ] **I5**: Prefetch Cache Bypass via `root.children.exists` in `tree.html`.
  - **Location**: `templates/documents/storage_repository/document_folder/tree.html:77`
  - **Problem**: `.exists()` executes an explicit SQL query for every root folder, bypassing prefetched data.
  - **Fix**: Change `{% if root.children.exists %}` to `{% if root.children.all %}`.

- [ ] **I6**: Dead Database Query in `repository_dashboard`.
  - **Location**: `apps/documents/views/StorageRepository/RepositoryDashboard.py:36-39`
  - **Problem**: `top_folders` is queried with multiple JOINs but is never rendered or used in `repository_dashboard.html`.
  - **Fix**: Remove `top_folders` query from `repository_dashboard`.

- [ ] **I7**: Redundant Dual Queries for Volume Count and Aggregate Bytes in `repository_dashboard` and `storage_volume_list`.
  - **Locations**:
    - `apps/documents/views/StorageRepository/RepositoryDashboard.py:14-24`
    - `apps/documents/views/StorageRepository/StorageVolumes.py:38-48`
  - **Problem**: `.count()` and `.aggregate(Sum(...))` run as two separate queries against the same filtered queryset.
  - **Fix**: Consolidate into single `.aggregate(count=Count("id"), cap=Sum("max_capacity_bytes"), util=Sum("utilized_bytes"))`.

- [ ] **I8**: Archive ingestion safety (Windows backslash normalization and file extension whitelist).
  - **Location**: `apps/documents/views/StorageRepository/DocumentBatchImports.py:195`
  - **Problem**: Windows backslashes in zip archive entries can bypass path stripping on POSIX environments, and unvetted file extensions could be ingested.
  - **Fix**: Normalize backslashes with `replace("\\", "/")` and check extension against `ALLOWED_DOC_EXTENSIONS`.

- [ ] **I9**: Missing upload file size limit on `DocumentBatchImportForm`.
  - **Location**: `apps/documents/forms/StorageRepository/DocumentBatchImports.py:45`
  - **Problem**: Unbounded file uploads could exhaust disk space.
  - **Fix**: Validate archive size <= 50 MB (`MAX_BATCH_UPLOAD_BYTES = 50 * 1024 * 1024`).

- [ ] **I10**: Missing ownership or administrator check on folder and batch deletions.
  - **Locations**:
    - `apps/documents/views/StorageRepository/DocumentFolders.py:200`
    - `apps/documents/views/StorageRepository/DocumentBatchImports.py:160`
  - **Problem**: Standard tenant users could delete other users' folders and batch jobs.
  - **Fix**: Ensure user is owner/creator, superuser, or tenant admin.

- [ ] **I11**: Missing pagination controls on folder detail contained documents table.
  - **Location**: `templates/documents/storage_repository/document_folder/detail.html:270`
  - **Problem**: `folder_detail` paginates documents to 15 items but detail template lacks pagination links.
  - **Fix**: Add pagination controls footer when `page_obj.paginator.num_pages > 1`.

---

### Minor

- [ ] **M1**: Duplicate Route Mapping in `LIVE_LINKS["13.4"]`.
  - **Location**: `apps/core/navigation.py:3553-3554`
  - **Problem**: Both "Cloud & On-Premises Deployment" and "Storage Tiering & Optimization" point identically to `documents:storage_volume_list`.
  - **Fix**: Differentiate "Storage Tiering & Optimization" to `documents:storage_volume_list?tier=hot`.

- [ ] **M2**: Implicit FK Evaluation in `DocumentFolder.is_root`.
  - **Location**: `apps/documents/models/StorageRepository/DocumentFolders.py:130`
  - **Problem**: `return self.parent is None` causes Django to evaluate the FK relation if not prefetched.
  - **Fix**: Change to `return self.parent_id is None`.

- [ ] **M3**: Duplicate Count Query in `folder_detail`.
  - **Location**: `apps/documents/views/StorageRepository/DocumentFolders.py:155`
  - **Problem**: Calling `docs_qs.count()` and then `Paginator(docs_qs, 15)` triggers two count queries.
  - **Fix**: Use `total_files = page_obj.paginator.count`.

- [ ] **M4**: Materialized Path Update Cascade on Folder Rename/Move.
  - **Location**: `apps/documents/models/StorageRepository/DocumentFolders.py:111`
  - **Problem**: When a parent folder's slug/name changes, child folders retain old materialized path prefixes.
  - **Fix**: Recursively update children paths when folder path changes.

- [ ] **M5**: Hardcoded Extension List in `DocumentBatchImportForm`.
  - **Location**: `apps/documents/forms/StorageRepository/DocumentBatchImports.py:45`
  - **Problem**: Extension list declared locally.
  - **Fix**: Declare `ALLOWED_EXTENSIONS` as class constant.

- [ ] **M6**: Unbounded Queryset in `relationship_graph`.
  - **Location**: `apps/documents/views/StorageRepository/DocumentRelationships.py:65`
  - **Problem**: Querying all tenant relationships could cause high memory usage on very large datasets.
  - **Fix**: Limit graph query to recent links (e.g. `[:200]`).

- [ ] **M7**: Dark mode contrast and accessibility enhancements.
  - **Locations**: `templates/documents/storage_repository/`
  - **Problem**: Some hardcoded light backgrounds lack dark mode variants.
  - **Fix**: Add dark mode utility classes and `aria-current="page"` on active pagination.
