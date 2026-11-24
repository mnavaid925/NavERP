from apps.documents.urls.ApprovalWorkflow.ApprovalDashboard import (
    urlpatterns as approval_dashboard_urls,
)
from apps.documents.urls.ApprovalWorkflow.DocumentApprovalRequests import (
    urlpatterns as approval_requests_urls,
)
from apps.documents.urls.ApprovalWorkflow.DocumentApprovalWorkflows import (
    urlpatterns as approval_workflows_urls,
)
from apps.documents.urls.ApprovalWorkflow.DocumentReviewComments import (
    urlpatterns as review_comments_urls,
)
from apps.documents.urls.ApprovalWorkflow.DocumentSignatures import (
    urlpatterns as signatures_urls,
)
from apps.documents.urls.AuditReporting import (
    urlpatterns as audit_reporting_urls,
)
from apps.documents.urls.CollaborationSharing import (
    urlpatterns as collaboration_sharing_urls,
)
from apps.documents.urls.RecordsManagement import (
    urlpatterns as records_management_urls,
)
from apps.documents.urls.DocumentAuthoring.DocumentDrafts import (
    urlpatterns as document_drafts_urls,
)
from apps.documents.urls.DocumentAuthoring.DocumentTemplates import (
    urlpatterns as document_templates_urls,
)
from apps.documents.urls.DocumentAuthoring.DraftCollaborations import (
    urlpatterns as draft_collaborations_urls,
)
from apps.documents.urls.DocumentAuthoring.TemplateSections import (
    urlpatterns as template_sections_urls,
)
from apps.documents.urls.MetadataIndexing.DocumentMetadataValues import (
    urlpatterns as metadata_values_urls,
)
from apps.documents.urls.MetadataIndexing.DocumentOcrJobs import (
    urlpatterns as document_ocr_jobs_urls,
)
from apps.documents.urls.MetadataIndexing.MetadataIndexingDashboard import (
    urlpatterns as metadata_indexing_dashboard_urls,
)
from apps.documents.urls.MetadataIndexing.MetadataSchemas import (
    urlpatterns as metadata_schemas_urls,
)
from apps.documents.urls.MetadataIndexing.TaxonomyTerms import (
    urlpatterns as taxonomy_terms_urls,
)
from apps.documents.urls.SearchDiscovery.DocumentSavedSearches import (
    urlpatterns as document_saved_searches_urls,
)
from apps.documents.urls.SearchDiscovery.DocumentSearchAlerts import (
    urlpatterns as document_search_alerts_urls,
)
from apps.documents.urls.SearchDiscovery.DocumentSearchQueryLogs import (
    urlpatterns as document_search_query_logs_urls,
)
from apps.documents.urls.SearchDiscovery.DocumentSearchSynonyms import (
    urlpatterns as document_search_synonyms_urls,
)
from apps.documents.urls.SearchDiscovery.SearchHub import (
    urlpatterns as search_hub_urls,
)
from apps.documents.urls.SecurityAccessControl.DlpIncidents import (
    urlpatterns as dlp_incidents_urls,
)
from apps.documents.urls.SecurityAccessControl.DlpPolicies import (
    urlpatterns as dlp_policies_urls,
)
from apps.documents.urls.SecurityAccessControl.DocumentAccessPermissions import (
    urlpatterns as permissions_urls,
)
from apps.documents.urls.SecurityAccessControl.DocumentDrmPolicies import (
    urlpatterns as drm_policies_urls,
)
from apps.documents.urls.SecurityAccessControl.SecureViewer import (
    urlpatterns as secure_viewer_urls,
)
from apps.documents.urls.SecurityAccessControl.WatermarkPolicies import (
    urlpatterns as watermark_policies_urls,
)
from apps.documents.urls.StorageRepository.DocumentBatchImports import (
    urlpatterns as document_batch_imports_urls,
)
from apps.documents.urls.StorageRepository.DocumentFolders import (
    urlpatterns as document_folders_urls,
)
from apps.documents.urls.StorageRepository.DocumentRelationships import (
    urlpatterns as document_relationships_urls,
)
from apps.documents.urls.StorageRepository.RepositoryDashboard import (
    urlpatterns as repository_dashboard_urls,
)
from apps.documents.urls.StorageRepository.StorageVolumes import (
    urlpatterns as storage_volumes_urls,
)
from apps.documents.urls.VersionControl.DocumentBranches import (
    urlpatterns as document_branches_urls,
)
from apps.documents.urls.VersionControl.DocumentLocks import (
    urlpatterns as document_locks_urls,
)
from apps.documents.urls.VersionControl.Documents import (
    urlpatterns as documents_urls,
)
from apps.documents.urls.VersionControl.DocumentVersions import (
    urlpatterns as document_versions_urls,
)
from apps.documents.urls.WorkflowAutomation import (
    urlpatterns as workflow_automation_urls,
)

app_name = "documents"

urlpatterns = (
    documents_urls
    + document_versions_urls
    + document_locks_urls
    + document_branches_urls
    + document_templates_urls
    + template_sections_urls
    + document_drafts_urls
    + draft_collaborations_urls
    + approval_dashboard_urls
    + approval_workflows_urls
    + approval_requests_urls
    + signatures_urls
    + review_comments_urls
    + repository_dashboard_urls
    + document_folders_urls
    + storage_volumes_urls
    + document_relationships_urls
    + document_batch_imports_urls
    + metadata_indexing_dashboard_urls
    + metadata_schemas_urls
    + metadata_values_urls
    + taxonomy_terms_urls
    + document_ocr_jobs_urls
    + search_hub_urls
    + document_saved_searches_urls
    + document_search_alerts_urls
    + document_search_synonyms_urls
    + document_search_query_logs_urls
    + permissions_urls
    + watermark_policies_urls
    + drm_policies_urls
    + dlp_policies_urls
    + dlp_incidents_urls
    + secure_viewer_urls
    + collaboration_sharing_urls
    + records_management_urls
    + audit_reporting_urls
    + workflow_automation_urls
)
