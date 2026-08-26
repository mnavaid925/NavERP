"""Procurement 6.9 Catalog Management — PunchOutEndpoint model.

The **Punch-out Catalog Integration** bullet: a stored connection profile into a supplier's
live catalogue — cXML, SAP OCI, or a plain manual link — so a buyer launches from this
workspace instead of retyping portal credentials. The endpoint carries connection metadata
ONLY: no handshake is ever executed here. ``record_session()`` stamps *that a session was
attempted*; executing one stays a deferred integration concern.

Ownership (L29/L36): the counterparty is a ``core.Party`` row (the unified spine) — this app
declares no vendor master of its own.
"""
from apps.procurement.models._base import *  # noqa: F401,F403


class PunchOutEndpoint(TenantNumbered):
    """One punch-out connection to a supplier's catalogue [POE-].

    There is no lifecycle: an endpoint is ordinary master data — ``enabled`` is the only
    switch, flipped straight from the form. ``last_session_at`` is derived activity evidence
    (stamped solely by ``record_session()``), never an editable field.
    """

    NUMBER_PREFIX = "POE"

    PROTOCOL_CHOICES = [
        ("cxml", "cXML"),
        ("oci", "SAP OCI"),
        ("manual_link", "Manual link"),
    ]

    party = models.ForeignKey("core.Party", on_delete=models.CASCADE,
                              related_name="procurement_punchout_endpoints",
                              help_text="Supplier this punch-out connection belongs to")
    name = models.CharField(max_length=120)
    protocol = models.CharField(max_length=20, choices=PROTOCOL_CHOICES, default="cxml")
    punchout_url = models.URLField(help_text="Entry URL of the supplier's punch-out site")
    username = models.CharField(max_length=120, blank=True)

    # WARNING: this DEMO build stores the shared secret VERBATIM in a plaintext column.
    # Production must follow the tenants.EncryptionKey precedent — persist ONLY a SHA-256
    # hash (key_hash) and compare candidate secrets by re-hashing. Regardless of storage,
    # the value is never logged, never rendered (the detail page shows a fixed placeholder
    # and the edit form pops the field), and never written to the audit trail.
    shared_secret = models.CharField(
        max_length=255, blank=True,
        help_text="Write-only: left blank on edit, stored for this workspace only.")

    enabled = models.BooleanField(default=True,
                                  help_text="Disabled endpoints stay on file but leave the "
                                            "buyer launch lists")
    last_session_at = models.DateTimeField(null=True, blank=True, editable=False,
                                           help_text="When a punch-out session was last "
                                                     "recorded against this endpoint")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "enabled"], name="prc_poe_tnt_enabled_idx"),
        ]

    # -- actions ----------------------------------------------------------------------------------

    def record_session(self):
        """Stamp that a punch-out session was attempted now — the ONLY writer of the stamp."""
        self.last_session_at = timezone.now()
        self.save(update_fields=["last_session_at", "updated_at"])

    def __str__(self):
        return f"{self.number or 'POE'} · {self.name}"
