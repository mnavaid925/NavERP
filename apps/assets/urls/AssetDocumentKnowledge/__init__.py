from .AssetDocuments import urlpatterns as document_urlpatterns
from .AssetKnowledgeArticles import urlpatterns as knowledge_article_urlpatterns
from .AssetOperatingProcedures import urlpatterns as operating_procedure_urlpatterns
from .AssetOperatorCertifications import urlpatterns as operator_certification_urlpatterns

urlpatterns = (
    document_urlpatterns
    + operating_procedure_urlpatterns
    + operator_certification_urlpatterns
    + knowledge_article_urlpatterns
)
