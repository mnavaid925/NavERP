from decimal import Decimal

from django.db import models

from apps.assets.models._base import TenantNumbered


class AssetCyberSecurityProfile(TenantNumbered):
    """
    Asset OT/IoT Cyber Security Profile [ACS-].
    Manages industrial IoT/OT device security profiles, Purdue model network zoning (Level 0-4),
    firmware baseline tracking, industrial protocols, CVE vulnerability tracking, and CVSS scores.
    Aligned with IEC 62443 and NIST SP 800-82.
    """

    NUMBER_PREFIX = "ACS"

    DEVICE_TYPE_CHOICES = [
        ("plc_controller", "Programmable Logic Controller (PLC)"),
        ("scada_server", "SCADA / DCS Central Server"),
        ("rtu_remote_terminal", "Remote Terminal Unit (RTU)"),
        ("iot_sensor", "IoT Edge Sensor / Telemetry Node"),
        ("hmi_touchscreen", "Human-Machine Interface (HMI)"),
        ("network_switch_gateway", "Industrial Switch / Security Gateway"),
        ("vfd_drive", "Variable Frequency Drive (VFD)"),
        ("smart_meter", "Smart Power / Flow Meter"),
        ("robotic_cell", "Robotic Arm / Automated Cell"),
    ]

    NETWORK_ZONE_CHOICES = [
        ("enterprise_it", "Purdue Level 4: Enterprise IT Network"),
        ("dmz", "Purdue Level 3.5: Industrial DMZ"),
        ("supervisory_scada", "Purdue Level 3: Plant Operations & SCADA"),
        ("control_plc", "Purdue Level 2: Area Supervisory Control & PLC"),
        ("process_io", "Purdue Level 1: Basic Process I/O & Drives"),
        ("isolated_airgap", "Purdue Level 0: Physically Air-Gapped"),
    ]

    PROTOCOL_CHOICES = [
        ("modbus_tcp", "Modbus TCP / RTU"),
        ("opc_ua", "OPC UA / DA"),
        ("ethernet_ip", "EtherNet / IP (CIP)"),
        ("profinet", "PROFINET / PROFIBUS"),
        ("bacnet", "BACnet IP (Building Automation)"),
        ("dnp3", "DNP3 (Electric Utilities)"),
        ("mqtt", "MQTT / Sparkplug B"),
        ("https_rest", "HTTPS / REST API"),
        ("proprietary", "Vendor Proprietary Protocol"),
    ]

    FIRMWARE_STATUS_CHOICES = [
        ("up_to_date", "Up-to-Date (Current Baseline)"),
        ("update_available", "Update Available (Non-Critical)"),
        ("critical_patch_pending", "Critical Security Patch Pending"),
        ("end_of_life_unsupported", "End-of-Life / Unsupported Firmware"),
    ]

    EXPOSURE_LEVEL_CHOICES = [
        ("air_gapped", "Physically Air-Gapped"),
        ("isolated_vlan", "Isolated Micro-Segmented VLAN"),
        ("monitored_dmz", "Monitored DMZ Gateway"),
        ("internet_facing", "Directly Internet / Cloud-Facing"),
    ]

    POSTURE_STATUS_CHOICES = [
        ("secure", "Secure (Compliant Baseline)"),
        ("attention_required", "Attention Required (Minor Findings)"),
        ("vulnerable", "Vulnerable (Active CVE / Unpatched)"),
        ("compromised", "Compromised / Incident Investigated"),
    ]

    POSTURE_STATUS_CSS = {
        "secure": "badge-green",
        "attention_required": "badge-amber",
        "vulnerable": "badge-red",
        "compromised": "badge-red",
    }

    FIRMWARE_STATUS_CSS = {
        "up_to_date": "badge-green",
        "update_available": "badge-info",
        "critical_patch_pending": "badge-amber",
        "end_of_life_unsupported": "badge-red",
    }

    NETWORK_ZONE_CSS = {
        "enterprise_it": "badge-slate",
        "dmz": "badge-amber",
        "supervisory_scada": "badge-info",
        "control_plc": "badge-purple",
        "process_io": "badge-slate",
        "isolated_airgap": "badge-green",
    }

    EXPOSURE_LEVEL_CSS = {
        "air_gapped": "badge-green",
        "isolated_vlan": "badge-info",
        "monitored_dmz": "badge-amber",
        "internet_facing": "badge-red",
    }

    tenant = models.ForeignKey(
        "core.Tenant",
        on_delete=models.CASCADE,
        related_name="asset_cyber_profiles",
    )
    asset = models.ForeignKey(
        "scm.Asset",
        on_delete=models.CASCADE,
        related_name="cybersecurity_profiles",
        help_text="Physical equipment or connected controller",
    )
    device_type = models.CharField(
        max_length=30,
        choices=DEVICE_TYPE_CHOICES,
        default="plc_controller",
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="Static or industrial network IPv4/IPv6 address",
    )
    mac_address = models.CharField(
        max_length=50,
        blank=True,
        help_text="Hardware MAC address",
    )
    network_zone = models.CharField(
        max_length=30,
        choices=NETWORK_ZONE_CHOICES,
        default="control_plc",
    )
    firmware_version = models.CharField(
        max_length=100,
        default="1.0.0",
        help_text="Active firmware revision running on device",
    )
    latest_available_firmware = models.CharField(
        max_length=100,
        blank=True,
        help_text="Latest vendor release firmware version",
    )
    firmware_update_status = models.CharField(
        max_length=30,
        choices=FIRMWARE_STATUS_CHOICES,
        default="up_to_date",
    )
    protocol_used = models.CharField(
        max_length=30,
        choices=PROTOCOL_CHOICES,
        default="modbus_tcp",
    )
    exposure_level = models.CharField(
        max_length=30,
        choices=EXPOSURE_LEVEL_CHOICES,
        default="isolated_vlan",
    )
    known_vulnerabilities_cve = models.TextField(
        blank=True,
        help_text="Common Vulnerabilities and Exposures (CVE) IDs and advisory details",
    )
    cve_risk_score = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        default=Decimal("0.0"),
        help_text="Base CVSS score (0.0 to 10.0)",
    )
    compensating_controls = models.TextField(
        blank=True,
        help_text="Compensating security controls (firewall isolation, physical interlocks)",
    )
    last_vulnerability_scan_date = models.DateField(
        null=True,
        blank=True,
    )
    security_posture_status = models.CharField(
        max_length=30,
        choices=POSTURE_STATUS_CHOICES,
        default="secure",
    )
    patch_freeze_until = models.DateField(
        null=True,
        blank=True,
        help_text="Production blackout window blocking firmware updates",
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="assets_acs_ten_num_uniq",
            )
        ]
        indexes = [
            models.Index(fields=["tenant", "security_posture_status"], name="idx_acs_ten_post"),
            models.Index(fields=["tenant", "firmware_update_status"], name="idx_acs_ten_fw"),
            models.Index(fields=["tenant", "network_zone"], name="idx_acs_ten_zone"),
            models.Index(fields=["tenant", "asset"], name="idx_acs_ten_ast"),
        ]

    def __str__(self):
        asset_name = self.asset.name if getattr(self, "asset_id", None) else "Unlinked"
        return f"{self.number} — {asset_name} ({self.get_device_type_display()})"

    @property
    def posture_status_badge_class(self):
        return self.POSTURE_STATUS_CSS.get(self.security_posture_status, "badge-slate")

    @property
    def firmware_status_badge_class(self):
        return self.FIRMWARE_STATUS_CSS.get(self.firmware_update_status, "badge-slate")

    @property
    def network_zone_badge_class(self):
        return self.NETWORK_ZONE_CSS.get(self.network_zone, "badge-slate")

    @property
    def exposure_level_badge_class(self):
        return self.EXPOSURE_LEVEL_CSS.get(self.exposure_level, "badge-slate")
