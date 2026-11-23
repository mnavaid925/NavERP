"""Unit tests for Sub-module 13.7 Security & Access Control models."""
from datetime import timedelta
import pytest
from django.db import IntegrityError
from django.utils import timezone

from apps.documents.models.SecurityAccessControl.DocumentAccessPermissions import DocumentAccessPermission
from apps.documents.models.SecurityAccessControl.WatermarkPolicies import WatermarkPolicy
from apps.documents.models.SecurityAccessControl.DocumentDrmPolicies import DocumentDrmPolicy
from apps.documents.models.SecurityAccessControl.DlpPolicies import DlpPolicy
from apps.documents.models.SecurityAccessControl.DlpIncidents import DlpIncident


# ---------------------------------------------------------------------------
# DocumentAccessPermission Model Tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_security_access_control_document_permission_creation_and_numbering(tenant_a, admin_user, member_user, document):
    """Test DocumentAccessPermission creation, auto-number generation (DPRM-), and __str__."""
    perm = DocumentAccessPermission.objects.create(
        tenant=tenant_a,
        document=document,
        grantee_type="user",
        user=member_user,
        permission_level="viewer",
        created_by=admin_user,
    )
    assert perm.number.startswith("DPRM-")
    assert perm.grantee_type == "user"
    assert perm.permission_level == "viewer"
    assert perm.is_active is True
    assert str(perm) == f"{perm.number} ({perm.grantee_display} -> {document.title})"


@pytest.mark.django_db
def test_security_access_control_document_permission_grantee_types_and_display(tenant_a, admin_user, member_user, org_unit_a, document):
    """Test grantee display and type badge for all grantee types."""
    # User grantee
    perm_user = DocumentAccessPermission.objects.create(
        tenant=tenant_a,
        document=document,
        grantee_type="user",
        user=member_user,
        created_by=admin_user,
    )
    expected_name = member_user.get_full_name() or member_user.username
    assert perm_user.grantee_display == expected_name
    assert perm_user.grantee_type_badge == "badge-info"

    # OrgUnit grantee
    perm_ou = DocumentAccessPermission.objects.create(
        tenant=tenant_a,
        document=document,
        grantee_type="org_unit",
        org_unit=org_unit_a,
        created_by=admin_user,
    )
    assert perm_ou.grantee_display == f"OrgUnit: {org_unit_a.name}"
    assert perm_ou.grantee_type_badge == "badge-slate"

    # Role grantee
    perm_role = DocumentAccessPermission.objects.create(
        tenant=tenant_a,
        document=document,
        grantee_type="role",
        role_name="Compliance Auditor",
        created_by=admin_user,
    )
    assert perm_role.grantee_display == "Role: Compliance Auditor"
    assert perm_role.grantee_type_badge == "badge-amber"

    # Tenant-wide grantee
    perm_tw = DocumentAccessPermission.objects.create(
        tenant=tenant_a,
        document=document,
        grantee_type="tenant_wide",
        created_by=admin_user,
    )
    assert perm_tw.grantee_display == "Tenant-Wide"
    assert perm_tw.grantee_type_badge == "badge-slate"

    # Unassigned grantee
    perm_none = DocumentAccessPermission.objects.create(
        tenant=tenant_a,
        document=document,
        grantee_type="user",
        user=None,
        created_by=admin_user,
    )
    assert perm_none.grantee_display == "Unassigned"


@pytest.mark.django_db
def test_security_access_control_document_permission_level_choices_and_badges(tenant_a, admin_user, document):
    """Test permission level choices and corresponding CSS badge properties."""
    levels = {
        "viewer": "badge-slate",
        "commenter": "badge-info",
        "editor": "badge-amber",
        "manager": "badge-amber",
        "owner": "badge-green",
        "custom": "badge-muted",
    }
    for level, expected_badge in levels.items():
        perm = DocumentAccessPermission.objects.create(
            tenant=tenant_a,
            document=document,
            grantee_type="tenant_wide",
            permission_level=level,
            created_by=admin_user,
        )
        assert perm.permission_level_badge == expected_badge


@pytest.mark.django_db
def test_security_access_control_document_permission_capability_flags(document_permission):
    """Test capability boolean flags on DocumentAccessPermission fixture."""
    assert document_permission.can_read is True
    assert document_permission.can_write is True
    assert document_permission.can_delete is False
    assert document_permission.can_download is True
    assert document_permission.can_print is True
    assert document_permission.can_share is False

    # Toggle capability flags
    document_permission.can_share = True
    document_permission.can_delete = True
    document_permission.save()

    document_permission.refresh_from_db()
    assert document_permission.can_share is True
    assert document_permission.can_delete is True


@pytest.mark.django_db
def test_security_access_control_document_permission_validity_and_time_bounding(tenant_a, admin_user, member_user, document):
    """Test is_currently_valid property with active state and valid_from/valid_until boundaries."""
    now = timezone.now()

    # Active without date constraints
    perm = DocumentAccessPermission.objects.create(
        tenant=tenant_a,
        document=document,
        user=member_user,
        is_active=True,
        created_by=admin_user,
    )
    assert perm.is_currently_valid is True

    # Inactive permission
    perm.is_active = False
    assert perm.is_currently_valid is False
    perm.is_active = True

    # Future permission (not yet valid)
    perm.valid_from = now + timedelta(days=1)
    assert perm.is_currently_valid is False

    # Currently valid within range
    perm.valid_from = now - timedelta(days=1)
    perm.valid_until = now + timedelta(days=1)
    assert perm.is_currently_valid is True

    # Expired permission
    perm.valid_until = now - timedelta(hours=1)
    assert perm.is_currently_valid is False


@pytest.mark.django_db
def test_security_access_control_document_permission_folder_target_and_inheritance(tenant_a, admin_user, member_user, document_folder):
    """Test DocumentAccessPermission linked to a folder with inheritance flags."""
    perm = DocumentAccessPermission.objects.create(
        tenant=tenant_a,
        folder=document_folder,
        user=member_user,
        permission_level="editor",
        is_inherited=True,
        inherited_from_folder=document_folder,
        created_by=admin_user,
    )
    assert perm.folder == document_folder
    assert perm.document is None
    assert perm.is_inherited is True
    assert perm.inherited_from_folder == document_folder
    assert document_folder.name in str(perm)


@pytest.mark.django_db
def test_security_access_control_document_permission_unique_constraint(tenant_a, admin_user, document_permission):
    """Test unique constraint on (tenant, number) for DocumentAccessPermission."""
    with pytest.raises(IntegrityError):
        DocumentAccessPermission.objects.create(
            tenant=tenant_a,
            number=document_permission.number,
            document=document_permission.document,
            user=document_permission.user,
            created_by=admin_user,
        )


# ---------------------------------------------------------------------------
# WatermarkPolicy Model Tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_security_access_control_watermark_policy_creation_and_numbering(tenant_a, admin_user):
    """Test WatermarkPolicy creation, auto-number generation (DWTR-), and defaults."""
    policy = WatermarkPolicy.objects.create(
        tenant=tenant_a,
        name="Global Internal Overlay",
        classification="internal",
        created_by=admin_user,
    )
    assert policy.number.startswith("DWTR-")
    assert policy.slug == "global-internal-overlay"
    assert policy.classification == "internal"
    assert policy.is_active is True
    assert policy.opacity_percent == 25
    assert policy.font_size == 32
    assert policy.rotation_angle == -45
    assert "Global Internal Overlay" in str(policy)


@pytest.mark.django_db
def test_security_access_control_watermark_policy_slug_generation_and_uniqueness(tenant_a, admin_user):
    """Test automatic slug collision resolution on WatermarkPolicy."""
    p1 = WatermarkPolicy.objects.create(
        tenant=tenant_a,
        name="Security Policy",
        created_by=admin_user,
    )
    p2 = WatermarkPolicy.objects.create(
        tenant=tenant_a,
        name="Security Policy",
        created_by=admin_user,
    )
    assert p1.slug == "security-policy"
    assert p2.slug == "security-policy-1"

    # Explicit slug duplicate violates unique constraint
    with pytest.raises(IntegrityError):
        WatermarkPolicy.objects.create(
            tenant=tenant_a,
            name="Another Policy",
            slug=p1.slug,
            created_by=admin_user,
        )


@pytest.mark.django_db
def test_security_access_control_watermark_policy_render_watermark_token_interpolation(
    tenant_a, admin_user, member_user, document, watermark_policy
):
    """Test render_watermark interpolating all available dynamic tokens."""
    watermark_policy.watermark_text = (
        "USER: {{user_name}} | EMAIL: {{user_email}} | CLASS: {{classification}} | "
        "DOC: {{document_number}} | TENANT: {{tenant_name}} | IP: {{ip_address}} | TS: {{timestamp}}"
    )
    watermark_policy.save()

    rendered = watermark_policy.render_watermark(
        user=member_user,
        document=document,
        ip_address="192.168.1.100",
    )
    expected_user = member_user.get_full_name() or member_user.username
    expected_email = member_user.email or member_user.username

    assert f"USER: {expected_user}" in rendered
    assert f"EMAIL: {expected_email}" in rendered
    assert f"CLASS: {document.get_classification_display().upper()}" in rendered
    assert f"DOC: {document.number}" in rendered
    assert f"TENANT: {tenant_a.name}" in rendered
    assert "IP: 192.168.1.100" in rendered
    assert "TS: " in rendered


@pytest.mark.django_db
def test_security_access_control_watermark_policy_render_watermark_defaults(watermark_policy):
    """Test render_watermark fallback handling when user, document, or ip are omitted."""
    watermark_policy.watermark_text = "{{user_name}} | {{user_email}} | {{classification}} | {{document_number}} | {{ip_address}}"
    watermark_policy.save()

    rendered = watermark_policy.render_watermark(user=None, document=None, ip_address="")
    assert "Confidential" in rendered
    assert "user@local" in rendered
    assert "DOC-XXXXX" in rendered
    assert "127.0.0.1" in rendered


@pytest.mark.django_db
def test_security_access_control_watermark_policy_classification_badge_and_ordering(tenant_a, admin_user):
    """Test classification badges and priority ordering for WatermarkPolicy."""
    badges = {
        "all": "badge-slate",
        "public": "badge-green",
        "internal": "badge-info",
        "confidential": "badge-amber",
        "restricted": "badge-red",
    }
    for classification, expected_badge in badges.items():
        pol = WatermarkPolicy.objects.create(
            tenant=tenant_a,
            name=f"Policy {classification}",
            classification=classification,
            created_by=admin_user,
        )
        assert pol.classification_badge == expected_badge

    # Priority ordering test (ordering = ["priority", "name"])
    high_prio = WatermarkPolicy.objects.create(
        tenant=tenant_a,
        name="High Priority Policy",
        priority=5,
        created_by=admin_user,
    )
    low_prio = WatermarkPolicy.objects.create(
        tenant=tenant_a,
        name="Low Priority Policy",
        priority=50,
        created_by=admin_user,
    )
    policies = list(WatermarkPolicy.objects.filter(tenant=tenant_a).order_by("priority", "name"))
    assert policies.index(high_prio) < policies.index(low_prio)


# ---------------------------------------------------------------------------
# DocumentDrmPolicy Model Tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_security_access_control_drm_policy_creation_and_numbering(tenant_a, admin_user, document):
    """Test DocumentDrmPolicy creation, auto-number generation (DDRM-), and __str__."""
    drm = DocumentDrmPolicy.objects.create(
        tenant=tenant_a,
        name="Restricted Project DRM",
        target_document=document,
        created_by=admin_user,
    )
    assert drm.number.startswith("DDRM-")
    assert drm.slug == "restricted-project-drm"
    assert drm.is_active is True
    assert drm.is_revoked is False
    assert str(drm) == f"{drm.number} — Restricted Project DRM"


@pytest.mark.django_db
def test_security_access_control_drm_policy_slug_and_unique_constraints(tenant_a, admin_user, drm_policy):
    """Test unique constraint on (tenant, number) and (tenant, slug) for DocumentDrmPolicy."""
    # Collision auto-increment
    drm2 = DocumentDrmPolicy.objects.create(
        tenant=tenant_a,
        name=drm_policy.name,
        created_by=admin_user,
    )
    assert drm2.slug == f"{drm_policy.slug}-1"

    # IntegrityError on manual duplicate number
    with pytest.raises(IntegrityError):
        DocumentDrmPolicy.objects.create(
            tenant=tenant_a,
            number=drm_policy.number,
            name="Duplicate Number DRM",
            created_by=admin_user,
        )


@pytest.mark.django_db
def test_security_access_control_drm_policy_exfiltration_prevention_flags(drm_policy):
    """Test exfiltration prevention controls and cryptographic standards."""
    assert drm_policy.allow_print is False
    assert drm_policy.allow_copy_paste is False
    assert drm_policy.screen_shield_enabled is True
    assert drm_policy.secure_viewer_required is True
    assert drm_policy.require_watermark is True
    assert drm_policy.encryption_standard == "AES_256_GCM"


@pytest.mark.django_db
def test_security_access_control_drm_policy_revocation_kill_switch(admin_user, drm_policy):
    """Test revoke() emergency kill switch setting is_revoked, revoked_at, reason, and deactivating."""
    assert drm_policy.is_active is True
    assert drm_policy.is_revoked is False
    assert drm_policy.revoked_at is None

    reason_text = "Security breach detected: unapproved off-site copy"
    drm_policy.revoke(user=admin_user, reason=reason_text)

    drm_policy.refresh_from_db()
    assert drm_policy.is_revoked is True
    assert drm_policy.is_active is False
    assert drm_policy.revocation_reason == reason_text
    assert drm_policy.revoked_at is not None

    # Revoke with empty reason uses default text
    drm_policy.revoke(user=admin_user, reason="")
    drm_policy.refresh_from_db()
    assert drm_policy.revocation_reason == "Emergency administrative revocation"


@pytest.mark.django_db
def test_security_access_control_drm_policy_classification_badge_and_str(tenant_a, admin_user):
    """Test classification badges on DocumentDrmPolicy."""
    badges = {
        "all": "badge-slate",
        "public": "badge-green",
        "internal": "badge-info",
        "confidential": "badge-amber",
        "restricted": "badge-red",
    }
    for classification, expected_badge in badges.items():
        policy = DocumentDrmPolicy.objects.create(
            tenant=tenant_a,
            name=f"DRM {classification}",
            classification=classification,
            created_by=admin_user,
        )
        assert policy.classification_badge == expected_badge


# ---------------------------------------------------------------------------
# DlpPolicy Model Tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_security_access_control_dlp_policy_creation_and_numbering(tenant_a, admin_user):
    """Test DlpPolicy creation, auto-number generation (DDLP-), and defaults."""
    policy = DlpPolicy.objects.create(
        tenant=tenant_a,
        name="Credit Card Exposure Blocker",
        rule_type="built_in_pattern",
        built_in_pattern="credit_card_pci",
        action="block_save",
        severity="critical",
        created_by=admin_user,
    )
    assert policy.number.startswith("DDLP-")
    assert policy.slug == "credit-card-exposure-blocker"
    assert policy.match_threshold == 1
    assert policy.is_active is True
    assert "Credit Card Exposure Blocker" in str(policy)


@pytest.mark.django_db
def test_security_access_control_dlp_policy_slug_and_unique_constraints(tenant_a, admin_user, dlp_policy):
    """Test slug collision and unique constraints on DlpPolicy."""
    policy2 = DlpPolicy.objects.create(
        tenant=tenant_a,
        name=dlp_policy.name,
        created_by=admin_user,
    )
    assert policy2.slug == f"{dlp_policy.slug}-1"

    with pytest.raises(IntegrityError):
        DlpPolicy.objects.create(
            tenant=tenant_a,
            number=dlp_policy.number,
            name="Duplicate Number Policy",
            created_by=admin_user,
        )


@pytest.mark.django_db
def test_security_access_control_dlp_policy_inspect_text_credit_card(dlp_policy):
    """Test inspect_text detecting PCI credit card patterns with redaction."""
    text_clean = "Invoice summary for client services rendered in November 2026."
    violated, count, snippet = dlp_policy.inspect_text(text_clean)
    assert violated is False
    assert count == 0
    assert snippet == ""

    # Text containing Visa card number
    text_with_card = "Customer paid using card: 4111-2222-3333-4444 on file."
    violated, count, snippet = dlp_policy.inspect_text(text_with_card)
    assert violated is True
    assert count == 1
    assert "41" in snippet
    assert "44" in snippet
    assert "Detected 1 occurrence(s)" in snippet


@pytest.mark.django_db
def test_security_access_control_dlp_policy_inspect_text_ssn(tenant_a, admin_user):
    """Test inspect_text detecting US Social Security Number pattern."""
    policy = DlpPolicy.objects.create(
        tenant=tenant_a,
        name="PII SSN Shield",
        rule_type="built_in_pattern",
        built_in_pattern="us_ssn",
        created_by=admin_user,
    )
    text = "Employee tax ID record: 123-45-6789."
    violated, count, snippet = policy.inspect_text(text)
    assert violated is True
    assert count == 1
    assert "12" in snippet
    assert "89" in snippet


@pytest.mark.django_db
def test_security_access_control_dlp_policy_inspect_text_api_key(tenant_a, admin_user):
    """Test inspect_text detecting exposed API keys / secret tokens."""
    policy = DlpPolicy.objects.create(
        tenant=tenant_a,
        name="Secrets Blocker",
        rule_type="built_in_pattern",
        built_in_pattern="api_keys_secrets",
        created_by=admin_user,
    )
    text = "Connecting to production server with api_key: 'abcdef1234567890xyzsecret123'"
    violated, count, snippet = policy.inspect_text(text)
    assert violated is True
    assert count == 1
    assert "Detected 1 occurrence(s)" in snippet


@pytest.mark.django_db
def test_security_access_control_dlp_policy_inspect_text_sensitive_keywords(tenant_a, admin_user):
    """Test inspect_text detecting sensitive keywords case-insensitively."""
    policy = DlpPolicy.objects.create(
        tenant=tenant_a,
        name="Merger & Acquisition Confidentiality",
        rule_type="sensitive_keywords",
        sensitive_keywords=["Project Titan", "hostile takeover", "confidential merger"],
        created_by=admin_user,
    )
    text = "Board of Directors discussion regarding project titan next steps."
    violated, count, snippet = policy.inspect_text(text)
    assert violated is True
    assert count == 1
    assert "Detected 1 occurrence(s)" in snippet

    # No match
    text_safe = "Normal quarterly financial statement."
    violated, count, snippet = policy.inspect_text(text_safe)
    assert violated is False
    assert count == 0


@pytest.mark.django_db
def test_security_access_control_dlp_policy_inspect_text_custom_regex(tenant_a, admin_user):
    """Test inspect_text with custom regular expression pattern."""
    policy = DlpPolicy.objects.create(
        tenant=tenant_a,
        name="Internal Project Code Matcher",
        rule_type="custom_regex",
        custom_regex=r"\bPROJ-[A-Z]{3}-\d{4}\b",
        created_by=admin_user,
    )
    text = "Refer to classified blueprint PROJ-SEC-2026 for details."
    violated, count, snippet = policy.inspect_text(text)
    assert violated is True
    assert count == 1

    # Invalid regex handles gracefully without crashing
    policy.custom_regex = "["
    policy.save()
    violated, count, snippet = policy.inspect_text(text)
    assert violated is False
    assert count == 0


@pytest.mark.django_db
def test_security_access_control_dlp_policy_inspect_text_threshold_and_inactive(tenant_a, admin_user):
    """Test match threshold requirement and inactive policy behavior."""
    policy = DlpPolicy.objects.create(
        tenant=tenant_a,
        name="Multi-card Batch Detector",
        rule_type="built_in_pattern",
        built_in_pattern="credit_card_pci",
        match_threshold=2,
        created_by=admin_user,
    )
    text_single = "Card 1: 4111-2222-3333-4444"
    violated, count, _ = policy.inspect_text(text_single)
    assert violated is False
    assert count == 0

    text_double = "Card 1: 4111-2222-3333-4444, Card 2: 5500-0000-0000-0004"
    violated, count, snippet = policy.inspect_text(text_double)
    assert violated is True
    assert count == 2

    # Inactive policy returns False even with violations
    policy.is_active = False
    violated, count, _ = policy.inspect_text(text_double)
    assert violated is False
    assert count == 0

    # Empty text returns False
    policy.is_active = True
    assert policy.inspect_text("") == (False, 0, "")


@pytest.mark.django_db
def test_security_access_control_dlp_policy_badges_and_str(tenant_a, admin_user):
    """Test severity and action CSS badge mappings for DlpPolicy."""
    severities = {
        "low": "badge-slate",
        "medium": "badge-info",
        "high": "badge-amber",
        "critical": "badge-red",
    }
    for sev, badge in severities.items():
        pol = DlpPolicy.objects.create(
            tenant=tenant_a,
            name=f"Policy {sev}",
            severity=sev,
            created_by=admin_user,
        )
        assert pol.severity_badge == badge

    actions = {
        "log_only": "badge-slate",
        "warn_author": "badge-info",
        "block_save": "badge-red",
        "quarantine": "badge-amber",
        "force_watermark": "badge-slate",
    }
    for act, badge in actions.items():
        pol = DlpPolicy.objects.create(
            tenant=tenant_a,
            name=f"Policy {act}",
            action=act,
            created_by=admin_user,
        )
        assert pol.action_badge == badge


# ---------------------------------------------------------------------------
# DlpIncident Model Tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_security_access_control_dlp_incident_creation_and_numbering(dlp_incident):
    """Test DlpIncident creation, auto-number generation (DINC-), and __str__."""
    assert dlp_incident.number.startswith("DINC-")
    assert dlp_incident.resolution_status == "open"
    assert dlp_incident.severity == "critical"
    assert dlp_incident.action_taken == "blocked"
    assert str(dlp_incident) == f"{dlp_incident.number} — {dlp_incident.policy.name} (Critical)"


@pytest.mark.django_db
def test_security_access_control_dlp_incident_badges_and_str(dlp_incident):
    """Test severity, action, and resolution CSS badge properties on DlpIncident."""
    assert dlp_incident.severity_badge == "badge-red"
    assert dlp_incident.action_badge == "badge-red"
    assert dlp_incident.resolution_badge == "badge-red"

    # Action badge mapping
    actions = {
        "logged": "badge-slate",
        "warned": "badge-info",
        "blocked": "badge-red",
        "quarantined": "badge-amber",
        "watermarked": "badge-slate",
    }
    for act, badge in actions.items():
        dlp_incident.action_taken = act
        assert dlp_incident.action_badge == badge


@pytest.mark.django_db
def test_security_access_control_dlp_incident_resolution_status_transitions(admin_user, dlp_incident):
    """Test resolution status workflow transitions and resolution triage badges."""
    resolutions = {
        "open": "badge-red",
        "under_investigation": "badge-amber",
        "resolved_justified": "badge-green",
        "false_positive": "badge-slate",
        "dismissed": "badge-muted",
    }
    for res_status, expected_badge in resolutions.items():
        dlp_incident.resolution_status = res_status
        assert dlp_incident.resolution_badge == expected_badge

    # Triage and resolve incident
    dlp_incident.resolution_status = "resolved_justified"
    dlp_incident.resolved_by = admin_user
    dlp_incident.resolution_notes = "Verified legitimate business test case by lead auditor."
    dlp_incident.save()

    dlp_incident.refresh_from_db()
    assert dlp_incident.resolution_status == "resolved_justified"
    assert dlp_incident.resolved_by == admin_user
    assert "Verified legitimate business test case" in dlp_incident.resolution_notes


@pytest.mark.django_db
def test_security_access_control_dlp_incident_unique_constraint(tenant_a, admin_user, dlp_incident):
    """Test unique constraint on (tenant, number) for DlpIncident."""
    with pytest.raises(IntegrityError):
        DlpIncident.objects.create(
            tenant=tenant_a,
            number=dlp_incident.number,
            policy=dlp_incident.policy,
            document=dlp_incident.document,
            triggered_by=admin_user,
        )
