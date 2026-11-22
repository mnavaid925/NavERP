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
)
