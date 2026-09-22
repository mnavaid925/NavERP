"""Projects 7.18 — ConnectorFieldMapping model (unnumbered).

The field-to-field map that teaches a connector which local project field answers which remote
field (the Workato/Unito/Fusion mapping UI). Unnumbered: it is a child of the connector, reached
from the connector detail page and its own register.
"""
from apps.projects.models._base import *


class ConnectorFieldMapping(TenantOwned):
    """One local→remote field mapping on a connector."""

    DIRECTION_CHOICES = [
        ("to_remote", "Local → Remote"),
        ("from_remote", "Remote → Local"),
        ("both", "Bidirectional"),
    ]
    TRANSFORM_CHOICES = [
        ("none", "None"),
        ("upper", "Uppercase"),
        ("lower", "Lowercase"),
        ("trim", "Trim"),
        ("date_iso", "ISO date"),
        ("number", "Number"),
        ("bool", "Boolean"),
    ]

    connector = models.ForeignKey(
        "projects.ProjectIntegrationConnector",
        on_delete=models.CASCADE,
        related_name="mappings",
    )
    local_field = models.CharField(max_length=100, help_text="e.g. task.status, client.name, document.title, time_entry.hours")
    remote_field = models.CharField(max_length=100, help_text="e.g. fields.status.name, Account.Name, path, timeSpentSeconds")
    direction = models.CharField(max_length=14, choices=DIRECTION_CHOICES, default="both")
    transform = models.CharField(max_length=12, choices=TRANSFORM_CHOICES, default="none")
    value_map = models.JSONField(default=dict, blank=True, help_text="local value ⇒ remote value (or the reverse per direction)")
    default_value = models.CharField(max_length=255, blank=True)
    is_key = models.BooleanField(default=False, help_text="The match/identity key for de-dupe + idempotency.")
    is_required = models.BooleanField(default=False)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["connector__name", "local_field", "id"]
        unique_together = [("tenant", "connector", "local_field", "direction")]
        indexes = [
            models.Index(fields=["tenant", "connector"], name="ixm_tnt_conn_idx"),
            models.Index(fields=["tenant", "connector", "is_key"], name="ixm_tnt_conn_key_idx"),
        ]

    def __str__(self):
        return f"{self.local_field} → {self.remote_field}"

    def clean(self):
        super().clean()
        if self.connector_id and self.connector.tenant_id != self.tenant_id:
            raise ValidationError({"connector": "Connector belongs to another workspace."})
