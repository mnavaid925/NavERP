from django import forms
from django.contrib.auth import get_user_model

from apps.ecommerce.forms._common import TenantModelForm, TenantUniqueMixin
from apps.ecommerce.models.CustomerSupport.KnowledgeBaseArticles import KnowledgeBaseArticle

User = get_user_model()


class KnowledgeBaseArticleForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = KnowledgeBaseArticle
        fields = [
            "title",
            "slug",
            "category",
            "summary",
            "content",
            "status",
            "target_audience",
            "is_featured",
            "keywords",
            "author",
        ]
        widgets = {
            "title": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "Article headline"}
            ),
            "slug": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "auto-generated-from-title"}
            ),
            "category": forms.Select(attrs={"class": "form-select"}),
            "summary": forms.Textarea(
                attrs={"class": "form-textarea", "rows": 3, "placeholder": "Concise summary for search previews"}
            ),
            "content": forms.Textarea(
                attrs={"class": "form-textarea", "rows": 10, "placeholder": "Full article documentation and markdown formatting"}
            ),
            "status": forms.Select(attrs={"class": "form-select"}),
            "target_audience": forms.Select(attrs={"class": "form-select"}),
            "is_featured": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "keywords": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "shipping, delivery, tracking, carrier, fedex"}
            ),
            "author": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["author"].queryset = User.objects.filter(is_active=True).order_by("username")
        self.fields["author"].required = False
        self.fields["slug"].required = False
        self.fields["keywords"].required = False
