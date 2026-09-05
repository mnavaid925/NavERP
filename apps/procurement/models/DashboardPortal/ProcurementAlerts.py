"""Procurement 6.1 User Dashboard & Portal — ProcurementAlerts model.

**Task & Alert Center** bullet: one centralized inbox for the notifications a procurement user
works from — approaching requisition deadlines, PO approvals waiting, delivery updates — each with
a severity, an optional due moment and an owner, and a small open -> acknowledged -> resolved
lifecycle so the inbox can be worked rather than merely read.

This is a PROCUREMENT-owned table, deliberately separate from 4.11's ``scm.SupplyChainAlert``:
that one is the analytics engine's KPI-breach detector (dedupe keys, value-at-risk, re-raise on
recurrence) raised BY a detector run. These rows are workflow hand-raised (or seeded) facts about
work somebody has to do; they carry no metric observation and need no dedupe machinery. Folding
them into ``SupplyChainAlert`` would couple two lifecycles that resolve differently.

The later procurement sub-modules (6.3 Approval Workflow Engine above all) raise alerts INTO this
table when an approval sits idle or a deadline approaches; until those ship, rows arrive through
the CRUD here and through ``seed_procurement``, which is why manual create/edit stays available.
"""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.procurement.models._base import *  # noqa: F401,F403
from apps.procurement.models._base import ZERO


class ProcurementAlert(TenantOwned):
    """One item of procurement work or news in the Task & Alert Center."""

    KIND_CHOICES = [
        ("deadline", "Deadline"),
        ("approval", "Approval"),
        ("delivery", "Delivery"),
        ("task", "Task"),
        # 6.8 Renewal & Expiration Alerts raise kind="contract" rows into this inbox.
        ("contract", "Contract"),
        # 6.17 Risk & Compliance Management raises kind="risk" rows into this inbox, from both
        # SupplierRiskSignal (a score deterioration) and PolicyAttestation (an overdue sign-off).
        # Registering it here is what makes the value FILTERABLE (the 6.1 kind <select> is built
        # from these choices), LABELLED (get_kind_display returns the raw value otherwise) and
        # EDITABLE (ProcurementAlertForm has `kind` in Meta.fields, so an unregistered value has
        # no option to select and saving would silently re-kind the alert).
        ("risk", "Risk"),
    ]
    SEVERITY_CHOICES = [
        ("info", "Info"),
        ("warning", "Warning"),
        ("critical", "Critical"),
    ]
    STATUS_CHOICES = [
        ("open", "Open"),
        ("acknowledged", "Acknowledged"),
        ("resolved", "Resolved"),
    ]
    OPEN_STATUSES = ("open", "acknowledged")

    kind = models.CharField(max_length=12, choices=KIND_CHOICES, default="task")
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default="info")
    status = models.CharField(max_length=14, choices=STATUS_CHOICES, default="open")

    title = models.CharField(max_length=200)
    message = models.TextField(blank=True, help_text="What needs doing / what happened")
    # Internal path ONLY ("/procurement/alerts/..."), never an absolute URL — this renders as an
    # href straight from staff input, and an off-site or javascript: value here would be an open
    # redirect / XSS hop. Enforced in clean(); see the WARNING there.
    link_url = models.CharField(max_length=255, blank=True,
                                help_text="Optional internal link, e.g. /scm/requisitions/5/")
    due_at = models.DateTimeField(null=True, blank=True,
                                  help_text="When the deadline hits / the alert becomes late")
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                    null=True, blank=True, related_name="procurement_alerts",
                                    help_text="Who owns this alert — blank raises it to the team")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                   null=True, blank=True, related_name="procurement_alerts_created",
                                   editable=False)

    acknowledged_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                        null=True, blank=True, related_name="+", editable=False)
    acknowledged_at = models.DateTimeField(null=True, blank=True, editable=False)
    resolved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                    null=True, blank=True, related_name="+", editable=False)
    resolved_at = models.DateTimeField(null=True, blank=True, editable=False)
    resolution_note = models.TextField(blank=True,
                                       help_text="How it was closed out")

    raised_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        ordering = ["-raised_at"]
        indexes = [
            models.Index(fields=["tenant", "status"], name="prc_alr_tnt_status_idx"),
            models.Index(fields=["tenant", "severity"], name="prc_alr_tnt_sev_idx"),
            models.Index(fields=["tenant", "kind"], name="prc_alr_tnt_kind_idx"),
            models.Index(fields=["tenant", "assigned_to"], name="prc_alr_tnt_assign_idx"),
        ]

    def clean(self):
        errors = {}
        if self.link_url:
            # WARNING: link_url is rendered as an href verbatim. Only same-site absolute paths are
            # allowed — never scheme-relative ("//evil.com") or absolute URLs, which would turn the
            # alert card into an open redirect. Backslashes are rejected too: browsers canonicalize
            # "\" to "/", so "/\evil.com" IS "//evil.com" by the time it resolves. If an external
            # reference is ever needed, store it in `message` as text instead.
            if (not self.link_url.startswith("/") or self.link_url.startswith("//")
                    or "\\" in self.link_url):
                errors["link_url"] = "Enter an internal path starting with a single slash."
        if self.status == "resolved" and not self.resolved_at:
            errors["status"] = "A resolved alert needs its resolution stamped (save via Resolve)."
        if self.due_at and self.acknowledged_at and self.due_at < self.acknowledged_at:
            # A deadline cannot already be past when it was acknowledged — almost always a
            # mis-keyed date. Resolved alerts are exempt: closing something late is normal.
            if self.status != "resolved":
                errors["due_at"] = "The deadline is before the acknowledgement time."
        if errors:
            raise ValidationError(errors)

    @property
    def is_overdue(self):
        """Past its deadline AND still unattended — acknowledged-but-late still reads as overdue."""
        return bool(self.due_at and self.status in self.OPEN_STATUSES
                    and self.due_at < timezone.now())

    def acknowledge(self, user):
        """Mark seen. A no-op on anything already past open, so double-clicks stay harmless."""
        if self.status != "open":
            return False
        self.status = "acknowledged"
        self.acknowledged_by = user
        self.acknowledged_at = timezone.now()
        self.save(update_fields=["status", "acknowledged_by", "acknowledged_at", "updated_at"])
        return True

    def resolve(self, user, note=""):
        """Close out. Allowed from either live state — resolving straight from open is normal.
        A no-op on anything already resolved (mirrors acknowledge()), so a double-click cannot
        re-stamp who/when and silently rewrite the closure audit."""
        if self.status == "resolved":
            return False
        self.status = "resolved"
        self.resolved_by = user
        self.resolved_at = timezone.now()
        if note:
            self.resolution_note = note
        self.save(update_fields=["status", "resolved_by", "resolved_at",
                                 "resolution_note", "updated_at"])
        return True

    # -- presentation helpers -----------------------------------------------------------------
    # Colour-NAMED classes only: theme.css ships badge-green/red/amber/info/muted/slate and
    # nothing else (L33 — badge-success/-warning/-danger render completely unstyled).

    @property
    def severity_css(self):
        return {"info": "badge-info", "warning": "badge-amber", "critical": "badge-red",
                }.get(self.severity, "badge-slate")

    @property
    def status_css(self):
        # Open is red because open means unattended; green only once actually closed out.
        return {"open": "badge-red", "acknowledged": "badge-amber",
                "resolved": "badge-green"}.get(self.status, "badge-slate")

    @property
    def kind_css(self):
        return {"deadline": "badge-amber", "approval": "badge-info",
                "delivery": "badge-muted", "task": "badge-slate",
                "risk": "badge-red",
                }.get(self.kind, "badge-slate")

    def __str__(self):
        return f"[{self.get_severity_display()}] {self.title}"
