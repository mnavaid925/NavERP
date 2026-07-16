"""HRM 3.27 Communication Hub — KnowledgeArticles forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    HelpdeskCategory,
    KnowledgeArticle,
)


class KnowledgeArticleForm(TenantModelForm):
    # owner / view_count / helpful_count / published_at are set by the view / actions.
    class Meta:
        model = KnowledgeArticle
        fields = ["title", "category", "summary", "body", "tags", "status"]
        widgets = {"summary": forms.Textarea(attrs={"rows": 2}), "body": forms.Textarea(attrs={"rows": 10})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None and "category" in self.fields:
            self.fields["category"].queryset = (
                HelpdeskCategory.objects.filter(tenant=self.tenant).order_by("department", "name"))
