from apps.documents.urls.DocumentAuthoring.DocumentDrafts import (
    urlpatterns as document_drafts_urls,
)
from apps.documents.urls.DocumentAuthoring.DocumentTemplates import (
    urlpatterns as document_templates_urls,
)
from apps.documents.urls.DocumentAuthoring.TemplateSections import (
    urlpatterns as template_sections_urls,
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
)
