from django import forms
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.core.models import OrgUnit
from apps.documents.forms._common import TenantModelForm, reject_foreign
from apps.documents.models.ApprovalWorkflow.DocumentReviewComments import DocumentReviewComment
from apps.documents.models.CollaborationSharing.DocumentTasks import DocumentTask
from apps.documents.models.VersionControl.Documents import Document
from apps.documents.models.VersionControl.DocumentVersions import DocumentVersion


class DocumentTaskForm(TenantModelForm):
    class Meta:
        model = DocumentTask
        fields = [
            "document",
            "version",
            "review_comment",
            "title",
            "description",
            "task_type",
            "priority",
            "status",
            "assigned_to",
            "assigned_org_unit",
            "due_date",
            "reminder_date",
            "completion_notes",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "e.g. Review indemnification clause"}),
            "description": forms.Textarea(attrs={"rows": 3, "placeholder": "Detailed instructions or context for this action item"}),
            "due_date": forms.DateInput(attrs={"type": "date"}),
            "reminder_date": forms.DateInput(attrs={"type": "date"}),
            "completion_notes": forms.Textarea(attrs={"rows": 2, "placeholder": "Actions taken upon task resolution"}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        if self.tenant:
            self.fields["document"].queryset = Document.objects.filter(tenant=self.tenant).order_by("title")
            self.fields["version"].queryset = DocumentVersion.objects.filter(tenant=self.tenant).select_related("document").order_by("-created_at")
            self.fields["review_comment"].queryset = DocumentReviewComment.objects.filter(tenant=self.tenant).select_related("document").order_by("-created_at")
            
            user_model = get_user_model()
            self.fields["assigned_to"].queryset = user_model.objects.filter(tenant=self.tenant, is_active=True).order_by("first_name", "username")
            self.fields["assigned_org_unit"].queryset = OrgUnit.objects.filter(tenant=self.tenant).order_by("name")

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(
            self,
            cleaned_data,
            ["document", "version", "review_comment", "assigned_to", "assigned_org_unit"],
        )

        due_date = cleaned_data.get("due_date")
        reminder_date = cleaned_data.get("reminder_date")
        if due_date and reminder_date and reminder_date > due_date:
            self.add_error("reminder_date", "Reminder date cannot be later than the task due date.")

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        if not instance.pk and self.user and self.user.is_authenticated:
            instance.assigned_by = self.user

        if instance.status == "completed" and not instance.completed_at:
            instance.completed_at = timezone.now()
            if self.user and self.user.is_authenticated:
                instance.completed_by = self.user
        elif instance.status != "completed":
            instance.completed_at = None
            instance.completed_by = None

        if commit:
            instance.save()
            self.save_m2m()
        return instance
