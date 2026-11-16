from django.conf import settings
from django.db import models

from apps.quality.models._base import TenantNumbered


class DesignVerification(TenantNumbered):
    NUMBER_PREFIX = "QVER"

    ACTIVITY_TYPE_CHOICES = [
        ("verification", "Design Verification (Outputs meet Inputs)"),
        ("validation", "Design Validation (Conforms to User Needs)"),
        ("usability", "Usability & Human Factors Validation"),
        ("process_validation", "Process / Transfer Validation"),
    ]

    STATUS_CHOICES = [
        ("draft", "Protocol Draft"),
        ("approved_protocol", "Protocol Approved"),
        ("testing", "Testing In Progress"),
        ("passed", "Passed / Criteria Met"),
        ("failed", "Failed / Non-Conformance"),
        ("waived", "Waived / Justified"),
    ]

    TEST_METHOD_CHOICES = [
        ("inspection", "Visual / Dimensional Inspection"),
        ("lab_test", "Laboratory / Bench Testing"),
        ("analysis", "Engineering Analysis / Simulation"),
        ("clinical_trial", "Clinical Study / User Trial"),
        ("demonstration", "Operational Demonstration"),
    ]

    RESULT_CHOICES = [
        ("pending", "Pending Execution"),
        ("pass", "Pass"),
        ("fail", "Fail"),
    ]

    STATUS_CSS = {
        "draft": "badge-slate",
        "approved_protocol": "badge-info",
        "testing": "badge-amber",
        "passed": "badge-green",
        "failed": "badge-red",
        "waived": "badge-muted",
    }

    RESULT_CSS = {
        "pending": "badge-slate",
        "pass": "badge-green",
        "fail": "badge-red",
    }

    ACTIVITY_TYPE_CSS = {
        "verification": "badge-info",
        "validation": "badge-green",
        "usability": "badge-purple",
        "process_validation": "badge-amber",
    }

    project = models.ForeignKey("quality.DesignProject", on_delete=models.CASCADE, related_name="verifications")
    primary_input = models.ForeignKey("quality.DesignInput", on_delete=models.CASCADE, related_name="verifications", help_text="Design Input or User Need being verified")
    title = models.CharField(max_length=255)
    activity_type = models.CharField(max_length=28, choices=ACTIVITY_TYPE_CHOICES, default="verification", db_index=True)
    status = models.CharField(max_length=24, choices=STATUS_CHOICES, default="draft", db_index=True)
    test_method = models.CharField(max_length=24, choices=TEST_METHOD_CHOICES, default="lab_test")
    acceptance_criteria = models.TextField(help_text="Predetermined objective acceptance criteria")
    sample_size = models.PositiveIntegerField(default=1, help_text="Number of units tested with statistical justification")
    results_summary = models.TextField(blank=True, help_text="Observed test data and quantitative results")
    pass_fail_result = models.CharField(max_length=12, choices=RESULT_CHOICES, default="pending", db_index=True)
    deviation_notes = models.TextField(blank=True, help_text="Test anomalies, protocol deviations, or failure root cause")
    executed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="executed_design_tests")
    execution_date = models.DateField(null=True, blank=True)
    protocol_document = models.ForeignKey(
        "quality.ControlledDocument",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="verification_protocols",
        help_text="Approved test protocol SOP or document in Document Control",
    )
    report_document = models.ForeignKey(
        "quality.ControlledDocument",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="verification_reports",
        help_text="Approved final test report document in Document Control",
    )

    class Meta:
        ordering = ["project", "primary_input", "-created_at"]
        verbose_name = "Design Verification"
        verbose_name_plural = "Design Verifications"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="quality_qver_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "project"], name="idx_qver_ten_project"),
            models.Index(fields=["tenant", "primary_input"], name="idx_qver_ten_input"),
            models.Index(fields=["tenant", "activity_type"], name="idx_qver_ten_acttype"),
            models.Index(fields=["tenant", "status"], name="idx_qver_ten_status"),
            models.Index(fields=["tenant", "pass_fail_result"], name="idx_qver_ten_result"),
        ]

    def __str__(self):
        return f"{self.number} — {self.title} ({self.get_pass_fail_result_display()})"

    @property
    def status_css(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def result_css(self):
        return self.RESULT_CSS.get(self.pass_fail_result, "badge-slate")

    @property
    def activity_type_css(self):
        return self.ACTIVITY_TYPE_CSS.get(self.activity_type, "badge-slate")

    @property
    def is_passed(self):
        return self.pass_fail_result == "pass" and self.status == "passed"
