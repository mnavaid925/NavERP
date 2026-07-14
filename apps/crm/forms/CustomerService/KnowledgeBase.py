"""CRM 1.4 Customer Service & Support — KnowledgeBase forms (split from apps/crm/forms.py)."""
from apps.crm.forms._common import *  # noqa: F401,F403
from apps.crm.models import (
    KnowledgeArticle,
)


class KnowledgeArticleForm(TenantModelForm):
    class Meta:
        model = KnowledgeArticle
        # helpful_count/not_helpful_count/public_token/views_count are system-managed — excluded.
        fields = ["title", "kb_category", "category", "slug", "body", "visibility", "status", "owner"]
