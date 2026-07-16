"""HRM 3.8 Offer Management — Offerlettertemplate models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


class OfferLetterTemplate(TenantNumbered):
    """Reusable printable offer-letter template (3.8). Mirrors ``CandidateEmailTemplate``'s shape but for
    the longer-form letter body: the ``offer_letter_print`` view merges ``body_html``'s tokens against the
    offer/candidate/tenant. Keeping the body here (rather than a TextField on every ``Offer``) makes the
    boilerplate reusable + merge-tokenized across offers."""

    NUMBER_PREFIX = "OLTMPL"

    name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    body_html = models.TextField(
        help_text="Merge fields: {{candidate_name}}, {{job_title}}, {{base_salary}}, {{currency}}, "
                  "{{start_date}}, {{company_name}}, {{hiring_manager_name}}.")

    class Meta:
        ordering = ["name"]
        unique_together = ("tenant", "name")
        indexes = [
            models.Index(fields=["tenant", "is_active"], name="hrm_oltmpl_tenant_active_idx"),
        ]

    def __str__(self):
        return f"{self.number} · {self.name}" if self.number else self.name
