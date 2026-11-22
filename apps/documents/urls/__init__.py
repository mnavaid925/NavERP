from apps.documents.urls.DocumentAuthoring.DocumentDrafts import urlpatterns as document_drafts_urls
from apps.documents.urls.DocumentAuthoring.DocumentTemplates import urlpatterns as document_templates_urls
from apps.documents.urls.DocumentAuthoring.DraftCollaborations import urlpatterns as draft_collaborations_urls
from apps.documents.urls.DocumentAuthoring.TemplateSections import urlpatterns as template_sections_urls

app_name = "documents"

urlpatterns = (
    document_templates_urls
    + template_sections_urls
    + document_drafts_urls
    + draft_collaborations_urls
)
