from django import forms

from apps.documents.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.documents.models.DocumentAuthoring.DraftCollaborations import DraftCollaboration


class DraftCollaborationForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = DraftCollaboration
        fields = [
            "entry_type",
            "section_anchor",
            "selected_text",
            "replacement_text",
            "comment_text",
        ]
        widgets = {
            "entry_type": forms.Select(attrs={"class": "form-select"}),
            "section_anchor": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Clause 4.2 / Section 2"}),
            "selected_text": forms.Textarea(
                attrs={"class": "form-textarea font-mono text-xs", "rows": 3, "placeholder": "Quoted text under discussion..."}
            ),
            "replacement_text": forms.Textarea(
                attrs={
                    "class": "form-textarea font-mono text-xs",
                    "rows": 3,
                    "placeholder": "Proposed replacement wording (for suggestions)...",
                }
            ),
            "comment_text": forms.Textarea(attrs={"class": "form-textarea", "rows": 4, "placeholder": "Enter review feedback or rationale..."}),
        }
