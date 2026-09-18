"""Projects 7.10 — DocumentTemplate forms.

``DocumentTemplateForm`` carries the standard's working data — ``name``, ``category``,
``document_type``, ``description``, ``version``, ``file``, ``is_format_locked``, ``owner`` and
``review_on``. ``tenant``, ``number``, ``is_active`` and ``created_by`` are OFF it: publishing and
retiring are ``dtm_publish``'s job alone (a Toggle), so a form cannot publish a standard that a
review was about to retire.

``is_format_locked`` IS on the form, because it is an intent the PMO records — and the model's help
text says so plainly. Nothing in this sub-module enforces authorship, so the flag is data, not a
gate (Ruling 4 / the Deltek "locked formatting" feature, honestly scoped).

``file`` is optional on EDIT (a standard may be re-published as prose with the file removed) and the
same ``validate_upload`` rules apply as everywhere else in this sub-module.
"""
from apps.projects.forms._common import *  # noqa: F401,F403
from apps.projects.forms._common import TenantModelForm, TenantUniqueMixin, _reject_foreign
from apps.projects.models import DocumentTemplate, ProjectDocument
from apps.projects.models.DocumentKnowledgeManagement.Documents import validate_upload


class DocumentTemplateForm(TenantUniqueMixin, TenantModelForm):
    document_type = forms.ChoiceField(
        choices=[("", "---")] + list(ProjectDocument.DOC_TYPE_CHOICES),
        required=False,
    )

    class Meta:
        model = DocumentTemplate
        fields = [
            "name", "category", "document_type", "description", "version", "file",
            "is_format_locked", "owner", "review_on",
        ]

    def clean_file(self):
        uploaded = self.cleaned_data.get("file")
        # File is required on create (content-only standards belong in KnowledgeEntry); optional on edit.
        if (not self.instance or not self.instance.pk) and not uploaded:
            raise ValidationError("A template file is required to create a standard.")
        if not uploaded:
            return uploaded
        message = validate_upload(uploaded)
        if message:
            raise ValidationError(message)
        return uploaded

    def clean(self):
        cleaned = super().clean()

        # `owner` is a User FK — deliberately not re-checked (the 7.8/7.9 exemption).
        _reject_foreign(self, cleaned, [])

        return cleaned