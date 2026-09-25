import json
import math
import re
from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse

from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator, MaxValueValidator, MinValueValidator, RegexValidator, URLValidator
from django.db import models
from django.utils import timezone

from apps.sales.models._base import TenantEventOwned, TenantOwned, TenantNumbered, settings

ENRICHMENT_FIELD_CHOICES = [
    ("job_title", "Job title"),
    ("department", "Department"),
    ("linkedin", "LinkedIn URL"),
    ("work_email", "Work email"),
    ("phone", "Phone"),
    ("mobile", "Mobile"),
    ("website", "Website"),
    ("industry", "Industry"),
    ("employee_count", "Employee count"),
    ("annual_revenue", "Annual revenue"),
]
ENRICHMENT_FIELDS = {value for value, _label in ENRICHMENT_FIELD_CHOICES}
EXTERNAL_SOURCE_KINDS = {"provider", "email_signature", "linkedin", "import", "api"}
PERSON_ENRICHMENT_FIELDS = {
    "job_title", "department", "linkedin", "work_email", "phone", "mobile",
}
ORGANIZATION_ENRICHMENT_FIELDS = {
    "website", "industry", "employee_count", "annual_revenue",
}
MAX_ENRICHMENT_EMPLOYEES = 2_147_483_647
MAX_ENRICHMENT_REVENUE = Decimal("999999999999.99")
PHONE_VALIDATOR = RegexValidator(
    regex=r"^\+?[0-9().\- ]{3,40}$",
    message="Enter a valid phone number.",
)
URL_VALIDATOR = URLValidator(schemes=("http", "https"))
EMAIL_VALIDATOR = EmailValidator()
_CREDENTIAL_RE = re.compile(
    r"(?i)\b(?:password|passwd|token|api[_-]?key|secret|authorization)\b\s*[:=]\s*[^\s,;]+|bearer\s+[A-Za-z0-9._~+/=-]+|(?:AKIA[0-9A-Z]{16}|sk-[A-Za-z0-9]{8,})"
)
_URL_CREDENTIAL_RE = re.compile(
    r"(?i)([?&](?:access_?token|api[_-]?key|password|secret|signature)=)[^&\s]+"
)
_EMAIL_RE = re.compile(r"(?i)\b[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}\b")
_PHONE_RE = re.compile(r"(?<!\w)\+?\d[\d().\- ]{7,}\d(?!\w)")
_ERROR_CODE_RE = re.compile(r"^[A-Za-z0-9_.:-]{0,80}$")
ENRICHMENT_FIELD_MAX_LENGTHS = {
    "job_title": 120,
    "department": 120,
    "linkedin": 200,
    "work_email": 254,
    "phone": 40,
    "mobile": 40,
    "website": 200,
    "industry": 40,
}


def sanitize_enrichment_text(value, *, field_name, max_length, allow_url=True):
    text = " ".join(str(value or "").split())
    text = _CREDENTIAL_RE.sub("[redacted]", text)
    text = _URL_CREDENTIAL_RE.sub(r"\1[redacted]", text)
    text = _EMAIL_RE.sub("[redacted-email]", text)
    text = _PHONE_RE.sub("[redacted-phone]", text)
    if not allow_url:
        text = text.replace("://", "[redacted-url]")
    return text[:max_length]


def _string_value(value, field_name):
    if not isinstance(value, str):
        raise ValidationError({"changes": f"{field_name} must be text."})
    text = value.strip()
    max_length = ENRICHMENT_FIELD_MAX_LENGTHS.get(field_name, 200)
    if not text:
        raise ValidationError({"changes": f"{field_name} cannot be blank."})
    if len(text) > max_length:
        raise ValidationError({"changes": f"{field_name} exceeds {max_length} characters."})
    if any(ord(character) < 32 for character in text):
        raise ValidationError({"changes": f"{field_name} contains control characters."})
    if _CREDENTIAL_RE.search(text):
        raise ValidationError({"changes": f"{field_name} contains credential-like data."})
    return text


def _scalar_value(value, field_name):
    if isinstance(value, bool) or value is None:
        raise ValidationError({"changes": f"{field_name} must contain a non-boolean scalar value."})
    if isinstance(value, (dict, list, tuple, set)):
        raise ValidationError({"changes": f"{field_name} must contain a scalar value."})
    if field_name == "employee_count":
        if not isinstance(value, int) or value < 0 or value > MAX_ENRICHMENT_EMPLOYEES:
            raise ValidationError({"changes": "employee_count must be a non-negative 32-bit integer."})
        return value
    if field_name == "annual_revenue":
        try:
            revenue = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ValidationError({"changes": "annual_revenue must be a finite decimal value."}) from exc
        if not revenue.is_finite() or revenue < 0 or revenue > MAX_ENRICHMENT_REVENUE:
            raise ValidationError({"changes": "annual_revenue is outside the supported range."})
        if revenue.as_tuple().exponent < -2:
            raise ValidationError({"changes": "annual_revenue supports at most two decimal places."})
        try:
            normalized = revenue.quantize(Decimal("0.01"))
        except (InvalidOperation, ValueError) as exc:
            raise ValidationError({"changes": "annual_revenue could not be normalized safely."}) from exc
        return format(normalized, "f")
    text = _string_value(value, field_name)
    if field_name == "work_email":
        try:
            EMAIL_VALIDATOR(text)
        except ValidationError as exc:
            raise ValidationError({"changes": "work_email must be a valid email address."}) from exc
    elif field_name in {"linkedin", "website"}:
        try:
            URL_VALIDATOR(text)
        except ValidationError as exc:
            raise ValidationError({"changes": f"{field_name} must be a valid HTTP or HTTPS URL."}) from exc
        if field_name == "linkedin":
            hostname = (urlparse(text).hostname or "").lower()
            if hostname != "linkedin.com" and not hostname.endswith(".linkedin.com"):
                raise ValidationError({"changes": "linkedin must use a linkedin.com hostname."})
    elif field_name in {"phone", "mobile"}:
        try:
            PHONE_VALIDATOR(text)
        except ValidationError as exc:
            raise ValidationError({"changes": f"{field_name} must be a valid phone number."}) from exc
    elif field_name == "industry":
        from apps.crm.models.CoreData.Accounts import INDUSTRY_CHOICES
        if text not in {value for value, _label in INDUSTRY_CHOICES}:
            raise ValidationError({"changes": "industry is not a supported account industry."})
    return text


def validate_enrichment_changes(value):
    if not isinstance(value, dict):
        raise ValidationError({"changes": "Changes must be a JSON object."})
    if len(value) > len(ENRICHMENT_FIELDS):
        raise ValidationError({"changes": "Too many enrichment fields were supplied."})
    normalized = {}
    for field_name, proposal in value.items():
        if field_name not in ENRICHMENT_FIELDS:
            raise ValidationError({"changes": f"{field_name} is not an allowed enrichment field."})
        if not isinstance(proposal, dict) or set(proposal) - {"value", "confidence"}:
            raise ValidationError({"changes": "Each enrichment field must contain value and optional confidence only."})
        if "value" not in proposal:
            raise ValidationError({"changes": f"{field_name} is missing a value."})
        normalized[field_name] = {"value": _scalar_value(proposal["value"], field_name)}
        if "confidence" in proposal:
            confidence = proposal["confidence"]
            if isinstance(confidence, bool):
                raise ValidationError({"changes": f"{field_name} confidence must be between 0 and 1."})
            if not isinstance(confidence, (int, float, Decimal)):
                raise ValidationError({"changes": f"{field_name} confidence must be numeric."})
            if isinstance(confidence, float) and not math.isfinite(confidence):
                raise ValidationError({"changes": f"{field_name} confidence must be finite."})
            try:
                confidence = Decimal(str(confidence))
            except (InvalidOperation, TypeError, ValueError) as exc:
                raise ValidationError({"changes": f"{field_name} confidence must be numeric."}) from exc
            if not confidence.is_finite() or not 0 <= confidence <= 1:
                raise ValidationError({"changes": f"{field_name} confidence must be between 0 and 1."})
            normalized[field_name]["confidence"] = float(confidence)
    try:
        if len(json.dumps(normalized, default=str, allow_nan=False)) > 8192:
            raise ValidationError({"changes": "Changes exceed the 8 KiB limit."})
    except (TypeError, ValueError) as exc:
        raise ValidationError({"changes": "Changes must be valid JSON."}) from exc
    return normalized


def validate_enrichment_fields_for_party(party, changes):
    if not isinstance(changes, dict):
        raise ValidationError({"changes": "Changes must be a JSON object."})
    if party.kind not in {"person", "organization"}:
        raise ValidationError({"party": "Enrichment requires a person or organization Party."})
    fields = set(changes or {})
    if party.kind == "person" and fields - PERSON_ENRICHMENT_FIELDS:
        invalid = ", ".join(sorted(fields - PERSON_ENRICHMENT_FIELDS))
        raise ValidationError({"changes": f"These fields cannot be applied to a person Party: {invalid}."})
    if party.kind == "organization" and fields - ORGANIZATION_ENRICHMENT_FIELDS:
        invalid = ", ".join(sorted(fields - ORGANIZATION_ENRICHMENT_FIELDS))
        raise ValidationError({"changes": f"These fields cannot be applied to an organization Party: {invalid}."})


class PartyEnrichmentEvent(TenantEventOwned):
    KIND_CHOICES = [
        ("firmographic", "Firmographic"),
        ("contact", "Contact"),
        ("email_validation", "Email validation"),
        ("phone_validation", "Phone validation"),
        ("social", "Social profile"),
        ("employment_change", "Employment change"),
        ("duplicate_check", "Duplicate check"),
    ]
    SOURCE_KIND_CHOICES = [
        ("manual", "Manual"),
        ("provider", "Provider"),
        ("email_signature", "Email signature"),
        ("linkedin", "LinkedIn"),
        ("import", "Import"),
        ("api", "API"),
    ]
    STATUS_CHOICES = [
        ("proposed", "Proposed"),
        ("applied", "Applied"),
        ("rejected", "Rejected"),
        ("no_match", "No match"),
        ("failed", "Failed"),
    ]

    party = models.ForeignKey("core.Party", on_delete=models.PROTECT, related_name="sales_enrichment_events")
    kind = models.CharField(max_length=24, choices=KIND_CHOICES)
    source_kind = models.CharField(max_length=24, choices=SOURCE_KIND_CHOICES)
    source_name = models.CharField(max_length=120, blank=True)
    source_reference = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="proposed")
    match_confidence = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("1"))],
    )
    changes = models.JSONField(default=dict, blank=True)
    legal_basis_purpose = models.ForeignKey(
        "core.ConsentPurpose",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="sales_enrichment_events",
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
        related_name="sales_requested_enrichment_events",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
        related_name="sales_reviewed_enrichment_events",
    )
    occurred_at = models.DateTimeField(default=timezone.now, editable=False)
    applied_at = models.DateTimeField(null=True, blank=True, editable=False)
    idempotency_key = models.CharField(max_length=120, null=True, blank=True)
    error_code = models.CharField(max_length=80, blank=True)
    error_summary = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-occurred_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "idempotency_key"], name="sales_pee_tenant_key_uniq"),
            models.CheckConstraint(
                condition=models.Q(match_confidence__isnull=True)
                | models.Q(match_confidence__gte=0, match_confidence__lte=1),
                name="sales_pee_confidence_valid",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "party", "-occurred_at"], name="sales_pee_tnt_party_idx"),
            models.Index(fields=["tenant", "status", "-occurred_at"], name="sales_pee_tnt_status_idx"),
            models.Index(fields=["tenant", "kind", "-occurred_at"], name="sales_pee_tnt_kind_idx"),
        ]

    def _same_tenant(self, field_name):
        relation_id = getattr(self, f"{field_name}_id", None)
        if not relation_id or not self.tenant_id:
            return True
        field = self._meta.get_field(field_name)
        return field.remote_field.model._default_manager.filter(
            pk=relation_id,
            tenant_id=self.tenant_id,
        ).exists()

    def _active_tenant_user(self, field_name):
        relation_id = getattr(self, f"{field_name}_id", None)
        if not relation_id or not self.tenant_id:
            return False
        user_model = self._meta.get_field(field_name).remote_field.model
        return user_model._default_manager.filter(
            pk=relation_id,
            tenant_id=self.tenant_id,
            is_active=True,
        ).exists()

    def _validate_data(self):
        errors = {}
        if len(str(self.source_name or "")) > 120:
            errors["source_name"] = "Source names cannot exceed 120 characters."
        if len(str(self.source_reference or "")) > 255:
            errors["source_reference"] = "Source references cannot exceed 255 characters."
        if len(str(self.error_summary or "")) > 255:
            errors["error_summary"] = "Error summaries cannot exceed 255 characters."
        self.idempotency_key = (self.idempotency_key or "").strip() or None
        self.source_name = sanitize_enrichment_text(
            self.source_name,
            field_name="source_name",
            max_length=120,
            allow_url=False,
        )
        self.source_reference = sanitize_enrichment_text(
            self.source_reference,
            field_name="source_reference",
            max_length=255,
            allow_url=False,
        )
        self.error_code = (self.error_code or "").strip()
        self.error_summary = sanitize_enrichment_text(
            self.error_summary,
            field_name="error_summary",
            max_length=255,
        )
        if self.kind not in dict(self.KIND_CHOICES):
            errors["kind"] = "Unsupported enrichment kind."
        if self.source_kind not in dict(self.SOURCE_KIND_CHOICES):
            errors["source_kind"] = "Unsupported enrichment source."
        if self.status not in dict(self.STATUS_CHOICES):
            errors["status"] = "Unsupported enrichment status."
        if not self.party_id or not self._same_tenant("party"):
            errors["party"] = "The party must belong to this workspace."
        else:
            party_model = self._meta.get_field("party").remote_field.model
            party = party_model._default_manager.filter(
                pk=self.party_id,
                tenant_id=self.tenant_id,
            ).first()
            if party is None:
                errors["party"] = "The party must belong to this workspace."
            else:
                try:
                    validate_enrichment_fields_for_party(party, self.changes)
                except ValidationError as exc:
                    errors.update(exc.message_dict)
        if not self.requested_by_id or not self._active_tenant_user("requested_by"):
            errors["requested_by"] = "An active workspace requester is required."
        if self.reviewed_by_id and not self._active_tenant_user("reviewed_by"):
            errors["reviewed_by"] = "The reviewer must be an active workspace user."
        if self.legal_basis_purpose_id:
            purpose_model = self._meta.get_field("legal_basis_purpose").remote_field.model
            if not purpose_model._default_manager.filter(
                pk=self.legal_basis_purpose_id,
                tenant_id=self.tenant_id,
                is_active=True,
            ).exists():
                errors["legal_basis_purpose"] = "Choose an active purpose from this workspace."
        if self.source_kind in EXTERNAL_SOURCE_KINDS and not self.legal_basis_purpose_id:
            errors["legal_basis_purpose"] = "External enrichment requires a lawful basis purpose."
        if self.match_confidence is not None:
            try:
                confidence = Decimal(str(self.match_confidence))
            except (InvalidOperation, TypeError, ValueError):
                confidence = Decimal("NaN")
            if not confidence.is_finite() or not 0 <= confidence <= 1:
                errors["match_confidence"] = "Match confidence must be between 0 and 1."
            else:
                self.match_confidence = confidence
        if not _ERROR_CODE_RE.fullmatch(self.error_code):
            errors["error_code"] = "Error code contains unsupported characters."
        try:
            self.changes = validate_enrichment_changes(self.changes)
        except ValidationError as exc:
            errors.update(exc.message_dict)
        persisted = None
        if self.pk:
            persisted = type(self)._default_manager.filter(pk=self.pk).first()
            if persisted is None:
                errors["status"] = "The enrichment event no longer exists."
        if persisted is None:
            if self.status != "proposed":
                errors["status"] = "New enrichment events must start as proposed."
            if self.reviewed_by_id or self.applied_at is not None:
                errors["status"] = "A proposed event cannot already be reviewed."
        else:
            immutable_fields = (
                "tenant_id", "party_id", "kind", "source_kind", "source_name", "source_reference",
                "match_confidence", "changes", "legal_basis_purpose_id", "requested_by_id",
                "occurred_at", "idempotency_key", "error_code",
            )
            if any(getattr(self, field) != getattr(persisted, field) for field in immutable_fields):
                errors["status"] = "Enrichment evidence is append-only."
            if self.status != persisted.status:
                if not getattr(self, "_allow_status_transition", False):
                    errors["status"] = "Use the enrichment review service to decide this event."
                elif persisted.status != "proposed" or self.status not in {"applied", "rejected"}:
                    errors["status"] = "That enrichment transition is not available."
            elif any((
                self.reviewed_by_id != persisted.reviewed_by_id,
                self.applied_at != persisted.applied_at,
                self.error_summary != persisted.error_summary,
            )):
                errors["status"] = "Only the proposed-to-decided transition may update a review."
        if self.status in {"applied", "rejected"} and not self.reviewed_by_id:
            errors["reviewed_by"] = "A reviewer is required for a decided event."
        if self.status == "applied" and self.applied_at is None:
            self.applied_at = timezone.now()
        if self.status != "applied":
            self.applied_at = None
        if errors:
            raise ValidationError(errors)

    def clean(self):
        super().clean()
        self._validate_data()

    def save(self, *args, **kwargs):
        self._validate_data()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.party} · {self.get_kind_display()} · {self.get_status_display()}"
