"""Procurement 6.19 Document & Knowledge Management — forms sub-package init (docstring-only).

Re-exports live in ``apps/procurement/forms/__init__.py`` (6.13/6.14/6.15 precedent).

Entity modules: ``Documents`` (``ProcurementDocumentForm``), ``Revisions``
(``ProcurementDocumentRevisionUploadForm``), ``Policies`` (``ProcurementPolicyForm``) and
``KnowledgeResources`` (``KnowledgeResourceForm``).

Upload limits are imported LOCALLY from ``apps.core.forms._common`` inside the clean method that
uses them, never through ``apps.procurement.forms``: ``CatalogManagement/UploadBatches.py``
defines its own, different ``MAX_UPLOAD_BYTES`` (2 MB), and a package-level re-export would make
which limit applies depend on import order.
"""
