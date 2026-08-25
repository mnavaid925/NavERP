"""Inventory 5.17 Reporting & Analytics — InventoryReportSnapshot [IRS-].

The four reports in this sub-module (valuation / turnover / aging / ABC) are LIVE
computations over SCM 4.3's append-only ``StockMove`` ledger — they own no stock
figures of their own. What nothing else records is the FREEZE: a month-end or
audit-moment copy of one report's headline numbers and its top rows, taken through
the exact same engine that renders the live page, so a snapshot can never disagree
with what the page said at that instant.

A snapshot is IMMUTABLE evidence: it has no edit route, and deleting one is an
admin-gated action (it rewrites the audit trail, not just a row). The JSON it
stores is deliberately scalar-only (float/int/str/bool/None) so it re-renders
months later without recomputation — the same contract ``scm.KpiSnapshot`` proved.
"""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.inventory.models._base import TenantNumbered


class InventoryReportSnapshot(TenantNumbered):
    """One frozen run of one inventory report. ``number`` is the human IRS- id;
    ``created_at`` (from the tenant base) IS the generation moment — snapshots are
    written once and never updated."""

    NUMBER_PREFIX = "IRS"

    REPORT_TYPES = [
        ("valuation", "Inventory Valuation"),
        ("turnover", "Stock Turnover"),
        ("aging", "Aging Analysis"),
        ("abc", "ABC Analysis"),
    ]
    TYPE_CSS = {
        "valuation": "badge-info",
        "turnover": "badge-green",
        "aging": "badge-amber",
        "abc": "badge-slate",
    }

    report_type = models.CharField(max_length=12, choices=REPORT_TYPES)
    title = models.CharField(max_length=120, blank=True,
                             help_text="Optional caption; defaults to '<type> — <date>'.")
    # The window the report was computed over (turnover/ABC). Blank = the report's
    # own default window applied at generation time and recorded in summary.
    window_days = models.PositiveIntegerField(null=True, blank=True,
                                              help_text="Trailing window in days for turnover/ABC.")
    location = models.ForeignKey("scm.Location", on_delete=models.SET_NULL,
                                 null=True, blank=True, related_name="report_snapshots",
                                 help_text="Optional scope; blank = every location.")
    generated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                     null=True, blank=True, related_name="inventory_snapshots")
    # Scalar-only dict — see module docstring. Never model instances, Decimals or dates.
    summary = models.JSONField(default=dict)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "created_at"], name="inv_irs_tnt_created_idx"),
            models.Index(fields=["tenant", "report_type"], name="inv_irs_tnt_type_idx"),
        ]

    def __str__(self):
        return f"{self.number} {self.get_report_type_display()}"

    def clean(self):
        # Keyed off the *_id columns so an unset FK on CREATE doesn't 500 (repo rule).
        if self.location_id and self.tenant_id and self.location.tenant_id != self.tenant_id:
            raise ValidationError({"location": "That location belongs to another workspace."})

    @property
    def type_css(self):
        return self.TYPE_CSS.get(self.report_type, "badge-muted")

    @property
    def display_title(self):
        return self.title or f"{self.get_report_type_display()} — {self.created_at:%d %b %Y %H:%M}"
